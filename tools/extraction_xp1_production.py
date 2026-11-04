"""Engine-selected production evidence with one shared Lua/parser algorithm."""
import ast

MODULES = ('civ6rl.native_production_catalog', 'civ6rl.native_city_production_observation',
           'civ6rl.native_saved_actions')
PARAMETERIZED = {
    MODULES[0]: ('verify_source', 'verify_replacement_source', '_preamble', 'catalog_source', 'request_source'),
    MODULES[1]: ('verify_source', 'production_snapshot_source'),
}


def _add_default(tree):
    index = int(bool(tree.body and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)))
    while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(
        'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PRODUCTION_BASE_CORE_SHA256').body


def _source_selection(node):
    index = int(bool(node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)))
    node.body[index:index] = ast.parse('''
if core_sha256 != _PRODUCTION_BASE_CORE_SHA256:
    from civ6_host.runtime.xp1_production_profile import verify_source as selected_source
    return selected_source(core_sha256)
''').body


def _ordinary_operation(tree):
    match = ast.dump(ast.parse("kind in ('production', 'production_placement', 'production_resume')", mode='eval').body)
    calls = []

    class Delegate(ast.NodeTransformer):
        def visit_If(self, node):
            self.generic_visit(node)
            if ast.dump(node.test) != match:
                return node
            calls.append(node)
            if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == 'request_source' for n in ast.walk(node)):
                raise ValueError('Existing ordinary production branch changed')
            node.test = ast.parse("kind in ('production_placement', 'production_resume')", mode='eval').body
            # Placement/resumption retains its actual existing request branch.
            # The ordinary operation is delegated once, with no dead duplicate.
            inner = [n for n in node.body if isinstance(n, ast.If)
                     and ast.dump(n.test) == ast.dump(node.test)]
            if len(inner) != 1:
                raise ValueError('Expected one placement/ordinary production split')
            inner_index = node.body.index(inner[0])
            node.body[inner_index:inner_index+1] = inner[0].body
            replacement = ast.parse('''
if kind == 'production':
    from civ6_host.runtime.explicit_production_operation import apply as apply_production
    after = apply_production(owner, p, action, turn, player_id=pid)
''').body[0]
            replacement.orelse = [node]
            return replacement

    tree = Delegate().visit(tree)
    if len(calls) != 1:
        raise ValueError('Expected one shared ordinary production execution branch')
    return tree


def parameterize(name, raw):
    if name not in MODULES:
        return raw
    tree = ast.parse(raw)
    if name == MODULES[2]:
        tree = _ordinary_operation(tree)
    else:
        targets = PARAMETERIZED[name]
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        if not set(targets) <= set(functions):
            raise ValueError('Production extraction source functions changed')
        for target in targets:
            node = functions[target]
            if any(arg.arg == 'core_sha256' for arg in node.args.kwonlyargs):
                raise ValueError('Production source was already parameterized')
            node.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
            node.args.kw_defaults.append(ast.Name(id='_PRODUCTION_BASE_CORE_SHA256', ctx=ast.Load()))
            if target in ('verify_source', 'verify_replacement_source'):
                _source_selection(node)
            else:
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in targets:
                        call.keywords.append(ast.keyword(arg='core_sha256', value=ast.Name(id='core_sha256', ctx=ast.Load())))
        _add_default(tree)
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

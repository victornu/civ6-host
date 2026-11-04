"""Select Save ABI/owner primitives; retain the shared Save and stream pipeline."""
import ast

MODULES = ('civ6rl.native_checkpoint_diagnostic', 'civ6rl.native_checkpoint_retained_save')
DEFAULT = '_CHECKPOINT_BASE_CORE_SHA256'


def _engine():
    return ast.parse("getattr(self, 'core_sha256', provider.CORE_SHA256)", mode='eval').body


def parameterize(name, raw):
    if name not in MODULES:
        return raw
    tree = ast.parse(raw)
    insert = ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}')
    if name == MODULES[0]:
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in ('bind_save', 'check_control_boundary'):
            fn = functions[name]
            if any(a.arg == 'core_sha256' for a in fn.args.kwonlyargs):
                raise ValueError('Checkpoint diagnostic already parameterized')
            fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
            fn.args.kw_defaults.append(ast.Name(id=DEFAULT, ctx=ast.Load()))
        fn = functions['check_control_boundary']
        fn.body[1:1] = ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_checkpoint_profile import control_boundary
    return control_boundary(session, read, allow_uninitialized_private=allow_uninitialized_private, core_sha256=core_sha256)
''').body
        fn = functions['bind_save']
        if ast.unparse(fn.body[1]) != 'proof = verify_source()' or 'parent = json.loads' not in ast.unparse(fn.body[2]):
            raise ValueError('Shared Save source seam changed')
        original = fn.body[1:3]
        choose = ast.parse(f'''
from civ6_host.runtime.xp1_checkpoint_profile import save_abi, bind_source
abi = save_abi(core_sha256)
if core_sha256 == {DEFAULT}:
    pass
else:
    parent = bind_source(session, memory.read, core_sha256=core_sha256)
''').body
        choose[-1].body = original
        fn.body[1:3] = choose
        constants = {7987232: 'outer_vtable_rva', 4387856: 'outer_save_rva',
                     250224: 'inner_save_rva', 4383648: 'initialized_rva'}
        counts = {k: 0 for k in constants}
        class ABI(ast.NodeTransformer):
            def visit_Constant(self, node):
                if type(node.value) is int and node.value in constants:
                    counts[node.value] += 1
                    return ast.Attribute(value=ast.Name(id='abi', ctx=ast.Load()),
                                         attr=constants[node.value], ctx=ast.Load())
                return node
        ABI().visit(fn)
        if counts != {7987232: 3, 4387856: 2, 250224: 1, 4383648: 2}:
            raise ValueError('Shared Save virtual binding changed: '+str(counts))
        returns = [node for node in ast.walk(fn) if isinstance(node, ast.Return)
                   and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2
                   and isinstance(node.value.elts[1], ast.Dict)]
        if len(returns) != 1 or {key.value for key in returns[0].value.elts[1].keys} != {
                'context', 'inner', 'inner_vtable', 'game'}:
            raise ValueError('Shared Save identity return changed')
        # Source-selected extra native owners join the same before/after
        # identity comparison. Base/XP1 return the exact previous dictionary.
        identity = returns[0].value.elts[1]
        identity.keys.append(None)
        identity.values.append(ast.parse("parent.get('native_owner_identity', {})", mode='eval').body)
    else:
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeRetainedSaveBackend')
        functions = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        counts = {'bind_save': 0, 'check_control_boundary': 0, 'require_quiescent': 0, 'provider_proof': 0}
        for name in ('prepare', 'serialize_configuration', 'verify_after_configuration', 'validate_return', 'postflight'):
            fn = functions[name]
            if name in ('serialize_configuration', 'validate_return'):
                fn.body[:0] = ast.parse('from civ6_host.runtime import xp1_checkpoint_profile as selected_checkpoint').body
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                    if ast.unparse(n.func) in ('diagnostic.bind_save', 'diagnostic.check_control_boundary'):
                        n.keywords.append(ast.keyword(arg='core_sha256', value=_engine()))
                        counts[n.func.attr] += 1
                    elif ast.unparse(n.func) == 'jobs.require_quiescent':
                        n.func.value = ast.Name(id='selected_checkpoint', ctx=ast.Load())
                        n.keywords.append(ast.keyword(arg='core_sha256', value=_engine()))
                        counts['require_quiescent'] += 1
            if name == 'serialize_configuration':
                class Proof(ast.NodeTransformer):
                    def visit_Attribute(self, node):
                        if ast.unparse(node) == 'provider.PROOF_SHA256':
                            counts['provider_proof'] += 1
                            return ast.Call(func=ast.Attribute(value=ast.Name(id='selected_checkpoint', ctx=ast.Load()),
                                            attr='provider_proof', ctx=ast.Load()), args=[_engine()], keywords=[])
                        return self.generic_visit(node)
                Proof().visit(fn)
        if counts != {'bind_save': 2, 'check_control_boundary': 3, 'require_quiescent': 2, 'provider_proof': 1}:
            raise ValueError('Shared retained Save primitives changed: '+str(counts))
    pos = int(bool(tree.body and isinstance(tree.body[0], ast.Expr)
                   and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str)))
    while pos < len(tree.body) and isinstance(tree.body[pos], ast.ImportFrom) and tree.body[pos].module == '__future__':
        pos += 1
    tree.body[pos:pos] = insert.body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

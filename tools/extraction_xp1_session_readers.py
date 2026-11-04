"""Select source profiles for shared session readers; preserve their Lua bodies."""
import ast


MODULES = ('civ6rl.native_unit_actions',)


def parameterize(name, raw):
    if name not in MODULES:
        return raw
    tree = ast.parse(raw)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'found_city_catalog_source']
    if len(functions) != 1:
        raise ValueError('Expected exactly one shared founder catalogue reader')
    node = functions[0]
    if node.args.kwonlyargs or [arg.arg for arg in node.args.args] != ['player_id', 'turn']:
        raise ValueError('Founder catalogue source signature changed')
    expected = ast.parse('''
from civ6_host.runtime.native.native_unit_skip import verify_source
verify_source()
''').body
    if [ast.dump(item) for item in node.body[1:3]] != [ast.dump(item) for item in expected]:
        raise ValueError('Shared founder source verification changed')
    node.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    node.args.kw_defaults.append(ast.Name(id='_SESSION_BASE_CORE_SHA256', ctx=ast.Load()))
    selection = ast.parse('''
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
if core_sha256 == BASE_CORE_SHA256:
    from civ6_host.runtime.native.native_unit_skip import verify_source
    verify_source()
elif core_sha256 in (XP1_CORE_SHA256, XP2_CORE_SHA256):
    from civ6_host.runtime.xp1_status_profiles import verify_source
    from civ6_host.runtime.unit_operation_ui_profile import source as unit_source
    verify_source(core_sha256)
    unit_source(core_sha256=core_sha256)
else:
    raise ValueError('Unknown engine for shared founder catalogue')
''').body
    node.body[1:3] = selection
    # Insert after any module docstring/future imports. Only the selected
    # verification preface changes; catalogue construction and parsing stay shared.
    index = int(bool(tree.body and isinstance(tree.body[0], ast.Expr)
                     and isinstance(tree.body[0].value, ast.Constant)
                     and isinstance(tree.body[0].value.value, str)))
    while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(
        'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _SESSION_BASE_CORE_SHA256').body
    return ast.unparse(ast.fix_missing_locations(tree)) + '\n'

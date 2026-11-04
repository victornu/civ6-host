"""Select the native UI binder by engine; preserve the default Base method."""
import ast

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
XP1='259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
XP2='324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'

def parameterize(name,raw):
    if name!='civ6rl.native_script_runtime':return raw
    tree=ast.parse(raw)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeScriptRuntime')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='bind_native_ui_api')
    if fn.args.kwonlyargs:raise ValueError('Native UI binding signature changed')
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant(BASE))
    fn.body[:0]=ast.parse(f'''
if core_sha256 == {XP2!r}:
    from civ6_host.runtime.xp2_ui_binding_source import bind_ui_api
    return bind_ui_api(self, game_context, ui_context, core_context, core_library)
if core_sha256 == {XP1!r}:
    from civ6_host.runtime.xp1_ui_binding import bind_xp1_ui_api
    return bind_xp1_ui_api(self, game_context, ui_context, core_context, core_library)
if core_sha256 != {BASE!r}:
    raise ValueError('Native UI binding engine is not admitted')
''').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

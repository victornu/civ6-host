"""Add one explicit profiled official binder; retain legacy engine branches."""
import ast
import copy

XP2 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'


def parameterize(tree):
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'NativeScriptRuntime']
    if len(classes) != 1:
        raise ValueError('Native script runtime boundary changed')
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef)
               and node.name == 'bind_native_game_api']
    if len(methods) != 1 or not any(a.arg == 'core_sha256' for a in methods[0].args.kwonlyargs):
        raise ValueError('Native game binder signature changed')
    method = methods[0]
    if any(isinstance(node, ast.ImportFrom) and node.module == 'civ6_host.runtime.profile_script_binding'
           for node in ast.walk(method)):
        raise ValueError('Profile script binder already selected')
    offset = 1 if isinstance(method.body[0], ast.Expr) and isinstance(method.body[0].value, ast.Constant) else 0
    method.body[offset:offset] = ast.parse(f'''
if core_sha256 == {XP2!r}:
    from civ6_host.runtime.profile_script_binding import bind_game_api
    return bind_game_api(self, context, core_context, core_library, core_sha256=core_sha256)
''').body
    return tree


def parameterize_services(tree):
    """Add guarded XP2 pointer selection, reusing the three existing binds."""
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='NativeScriptRuntime')
    bind=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='bind_core_services')
    unbind=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='unbind_services')
    if bind.args.kwonlyargs:raise ValueError('Script service signature changed')
    bind.args.kwonlyargs.extend([ast.arg(arg='core_library'),ast.arg(arg='core_sha256')])
    bind.args.kw_defaults.extend([ast.Constant(None),ast.Constant(None)])
    old=ast.parse('''
inner = C.c_void_p.from_address(context + 8).value
if not inner:
    raise RuntimeError('Native Core inner context is null')
configuration = C.c_void_p.from_address(inner + 80).value
gameplay = C.c_void_p.from_address(inner + 88).value
if not configuration or not gameplay:
    raise RuntimeError('Native Core database connections are null')
''').body
    indexes=[i for i,node in enumerate(bind.body) if ast.dump(node)==ast.dump(old[0])]
    if len(indexes)!=1:raise ValueError('Shared borrowed-service read boundary changed')
    at=indexes[0]
    if [ast.dump(n) for n in bind.body[at:at+5]] != [ast.dump(n) for n in old]:
        raise ValueError('Shared borrowed-service reads changed')
    replacement=ast.parse('''
profiled_services = None
if core_library is not None or core_sha256 is not None:
    from civ6_host.runtime.core_script_services import prepare
    profiled_services = prepare(self, native_host, context, core_library, core_sha256=core_sha256)
    inner = profiled_services.inner
    configuration = profiled_services.configuration
    gameplay = profiled_services.gameplay
else:
    pass
''').body
    replacement[1].orelse=copy.deepcopy(old)
    bind.body[at:at+5]=replacement
    if not (isinstance(bind.body[-1],ast.Expr) and isinstance(bind.body[-1].value,ast.Call)
            and ast.unparse(bind.body[-1].value.func)=='self.emit'):
        raise ValueError('Shared borrowed-service result boundary changed')
    bind.body[-1:-1]=ast.parse('''
if profiled_services is not None:
    from civ6_host.runtime.core_script_services import commit
    commit(self, profiled_services)
''').body
    start=1 if (isinstance(unbind.body[0],ast.Expr)
                and isinstance(unbind.body[0].value,ast.Constant)
                and isinstance(unbind.body[0].value.value,str)) else 0
    if ast.unparse(unbind.body[start])!='self.registry._check()':
        raise ValueError('Script service invalidation boundary changed')
    unbind.body[start+1:start+1]=ast.parse('self._profile_borrowed_services = None').body
    return tree

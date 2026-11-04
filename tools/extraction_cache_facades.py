"""Parameterize the existing cache-facade sequence and typed native backend."""
import ast
import copy

MODULES={'civ6rl.native_ui_cache_facades','civ6rl.native_ui_cache_backend'}
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
VTABLES={'OUTER_VTABLE_RVA':'outer_vtable_rva','GAME_FACADE_VTABLE_RVA':'game_facade_vtable_rva',
    'CACHE_SERVICE_VTABLE_RVA':'cache_service_vtable_rva','SYSTEM_FACADE_VTABLE_RVA':'system_facade_vtable_rva',
    'CACHE_B0_RESULT_VTABLE_RVA':'cache_b0_result_vtable_rva','CACHE_C0_RESULT_VTABLE_RVA':'cache_c0_result_vtable_rva'}


def keyword_core(fn):
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant(BASE))


def parameterize(name,tree):
    if name not in MODULES:return tree
    tree.body.insert(next(i for i,n in enumerate(tree.body) if not isinstance(n,(ast.Expr,ast.ImportFrom))),
        ast.parse('from civ6_host.runtime.cache_facade_profiles import facade_abi, verify_facade_source').body[0])
    if name.endswith('native_ui_cache_backend'):
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeCacheFacadeBackend')
        methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        ctor=methods['__init__'];keyword_core(ctor)
        ctor.body[0:0]=ast.parse('self.abi=facade_abi(core_sha256)').body
        class Backend(ast.NodeTransformer):
            def visit_Name(self,node):
                if node.id=='TARGET_RVAS':return ast.copy_location(ast.parse('self.abi.targets',mode='eval').body,node)
                return node
            def visit_Constant(self,node):
                field={0x434E30:'publish_rva',0x436640:'copy_rva'}.get(node.value) if type(node.value) is int else None
                return ast.copy_location(ast.parse('self.abi.'+field,mode='eval').body,node) if field else node
            def visit_Assign(self,node):
                if len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                    field={'getters':'getter_rvas','releases':'release_rvas'}.get(node.targets[0].id)
                    if field:
                        node.value=ast.parse('self.abi.'+field,mode='eval').body
                        return node
                return self.generic_visit(node)
        Backend().visit(cls)
        publish_branch=next(n for n in ast.walk(methods['call']) if isinstance(n,ast.If)
            and ast.unparse(n.test)=='rva == self.abi.publish_rva')
        publish_branch.body[0:0]=ast.parse("if not self.abi.full_refresh_admitted:\n    raise ValueError('Full cache population is not qualified for this engine')").body
        return tree
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    check=functions['_check_slot'];keyword_core(check)
    class Targets(ast.NodeTransformer):
        def visit_Name(self,node):
            if node.id=='TARGET_RVAS':
                return ast.copy_location(ast.parse('facade_abi(core_sha256).targets',mode='eval').body,node)
            return node
    Targets().visit(check)
    invoke=functions['_invoke'];keyword_core(invoke)
    for node in ast.walk(invoke):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='_check_slot':
            node.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeUiCacheFacades')
    methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    ctor=methods['__init__'];keyword_core(ctor)
    if ast.unparse(ctor.body[0])!='_verify_static_evidence()':raise ValueError('Facade source verification boundary changed')
    ctor.body[0:1]=ast.parse(f'''
self.abi=facade_abi(core_sha256)
if core_sha256=={BASE!r}:
    _verify_static_evidence()
else:
    verify_facade_source(backend,outer_borrowed,core_sha256=core_sha256)
''').body
    class Facades(ast.NodeTransformer):
        def visit_Name(self,node):
            field=VTABLES.get(node.id)
            if field:return ast.copy_location(ast.parse('self.abi.'+field,mode='eval').body,node)
            return node
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id in ('_invoke','_check_slot'):
                node.keywords.append(ast.keyword(arg='core_sha256',value=ast.parse('self.abi.core_sha256',mode='eval').body))
            return node
    Facades().visit(cls)
    refresh=methods['refresh']
    publish=next(i for i,n in enumerate(refresh.body) if isinstance(n,ast.Expr) and
                 isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_invoke')
    gate=next(i for i,n in enumerate(refresh.body) if isinstance(n,ast.Expr) and
              isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='self.backend.set_public_cache_gate')
    if not isinstance(refresh.body[-1],ast.Return) or gate!=len(refresh.body)-2 or gate<=publish:
        raise ValueError('Facade copy/result/gate sequence changed')
    helper=ast.parse('def _copy_cache_outputs(self):\n    pass').body[0]
    # Preserve existing copy, canary, result-replacement and release bodies.
    # The public gate belongs only to refresh after the official population.
    helper.body=copy.deepcopy(refresh.body[:publish])+copy.deepcopy(refresh.body[publish+1:gate])+[copy.deepcopy(refresh.body[-1])]
    refresh.body=refresh.body[:publish+1]+ast.parse('result=self._copy_cache_outputs()').body+[
        refresh.body[gate],ast.Return(value=ast.Name(id='result',ctx=ast.Load()))]
    refresh.body[0:0]=ast.parse("if not self.abi.full_refresh_admitted:\n    raise ValueError('Full cache population is not qualified for this engine')").body
    cls.body.insert(cls.body.index(refresh)+1,helper)
    return tree

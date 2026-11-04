"""Select ABI in the existing map owner/registry; preserve the shared algorithm."""
import ast

MODULE='civ6rl.native_combat_map_owner'
DEFAULT='_COMBAT_MAP_BASE_CORE_SHA256'


def parameterize(name,raw):
    if name!=MODULE:return raw
    tree=ast.parse(raw)
    fns={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
    owner=classes['NativeCombatMapOwner'];registry=classes['CombatMapRegistry']
    ctor=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    reg_ctor=next(n for n in registry.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    for fn in (fns['verify_source_evidence'],fns['verify_live_primitives'],ctor,reg_ctor):
        if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('Combat owner already selected')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Name(id=DEFAULT,ctx=ast.Load()))
    fns['verify_source_evidence'].body[:0]=ast.parse(f'''
if core_sha256!={DEFAULT}:
    from civ6_host.runtime.combat_map_profiles import owner_source
    return owner_source(core_sha256)
''').body
    fns['verify_live_primitives'].body[:0]=ast.parse(f'''
if core_sha256!={DEFAULT}:
    from civ6_host.runtime.combat_map_profiles import verify_live
    return verify_live(base,read,core_sha256=core_sha256)
''').body
    mapping={'VTABLE_RVA':'vtable_rva','CTOR_RVA':'constructor_rva',
             'ASSIGN_RVA':'assign_rva','DTOR_RVA':'destructor_rva'}
    class SelectOwner(ast.NodeTransformer):
        def visit_Name(self,n):
            if isinstance(n.ctx,ast.Load) and n.id in mapping:
                return ast.parse('self.abi.'+mapping[n.id],mode='eval').body
            return n
        def visit_Call(self,n):
            self.generic_visit(n)
            if isinstance(n.func,ast.Name) and n.func.id=='verify_live_primitives':
                n.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
            return n
    SelectOwner().visit(owner)
    ctor.body[:0]=ast.parse('''
from civ6_host.runtime.combat_map_profiles import profile_for_sha
self.core_sha256=core_sha256
self.abi=profile_for_sha(core_sha256)
self.core=core
''').body
    reg_ctor.body[:0]=ast.parse('self.core_sha256=core_sha256').body
    calls=[n for n in ast.walk(reg_ctor) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='verify_source_evidence']
    if len(calls)!=1:raise ValueError('Combat registry source check changed')
    calls[0].keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
    insert=next(n for n in registry.body if isinstance(n,ast.FunctionDef) and n.name=='insert')
    insert.body[:0]=ast.parse(f'''
if getattr(owner,'core_sha256',{DEFAULT})!=self.core_sha256:
    raise ValueError('Combat registry owner belongs to another engine')
''').body
    at=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)
                and isinstance(tree.body[0].value.value,str)))
    while at<len(tree.body) and isinstance(tree.body[at],ast.ImportFrom) and tree.body[at].module=='__future__':at+=1
    tree.body[at:at]=ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

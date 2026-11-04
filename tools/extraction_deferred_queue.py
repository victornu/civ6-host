"""Extract the existing queue/counter/CacheUpdate algorithms for shared owners."""
import ast
import copy

MODULES=('civ6rl.native_host_events','civ6rl.native_cache_update_dispatch')


def parameterize(name,tree):
    if name=='civ6rl.native_cache_update_dispatch':
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        fn=functions['dispatch_cache_update_payload']
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.Constant('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        # Base validation and its call/fixture seam are preserved. XP1 requires
        # an independent complete source/live profile before the same call.
        before=ast.dump(ast.parse('_validate_proof()',mode='eval').body)
        class Replace(ast.NodeTransformer):
            count=0
            def visit_Expr(self,node):
                if ast.dump(node.value)==before:
                    self.count+=1
                    return ast.parse('''
from civ6_host.runtime.cache_update_profiles import dispatch_abi, verify_dispatch_live
abi = dispatch_abi(core_sha256)
if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
    _validate_proof()
''').body
                return self.generic_visit(node)
            def visit_Name(self,node):
                field={'_OUTER_VTABLE_RVA':'outer_vtable_rva','_DISPATCH_RVA':'dispatch_rva'}.get(node.id)
                if field:return ast.copy_location(ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr=field,ctx=ast.Load()),node)
                return node
        rewrite=Replace();rewrite.visit(fn)
        if rewrite.count!=1:raise ValueError('CacheUpdate dispatcher source boundary changed')
        at=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and ast.unparse(n).startswith('outer_vtable,'))
        fn.body[at:at]=ast.parse('''
if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
    verify_dispatch_live(core_base, context, read_memory, core_sha256=core_sha256, registry_key=context_arg)
''').body
        return tree
    if name!='civ6rl.native_host_events':return tree
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeDeferredHostEvents')
    methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    names=('host_notification','host_notification_end','_enqueue','cache_update')
    shared=[methods[n] for n in names]
    for method in shared:cls.body.remove(method)
    drain=methods['_drain_empty_receivers_once']
    match=[]
    expected=ast.dump(ast.parse("int.from_bytes(record[4:8], 'little') == 0x113",mode='eval').body)
    for n in ast.walk(drain):
        if isinstance(n,ast.If) and ast.dump(n.test)==expected:match.append(n)
    if len(match)!=1:raise ValueError('CacheUpdate queue branch changed')
    branch=match[0]
    body=[];increment=None
    for n in branch.body:
        if isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id=='count':
            if increment is not None:raise ValueError('CacheUpdate commit count changed')
            increment=n
        else:body.append(copy.deepcopy(n))
    if increment is None:raise ValueError('CacheUpdate branch no longer commits a count')
    for n in ast.walk(ast.Module(body=body,type_ignores=[])):
        if isinstance(n,ast.Call) and ast.unparse(n.func)=='dispatch_cache_update_payload':
            n.keywords.append(ast.keyword(arg=None,value=ast.parse(
                "({'core_sha256': self.cache_core_sha256} if hasattr(self, 'cache_core_sha256') else {})",mode='eval').body))
    function=ast.parse('def _consume_cache_update_record(self, record, sequence):\n    pass').body[0]
    function.body=body
    shared.append(function)
    branch.body=ast.parse('self._consume_cache_update_record(record, sequence)\ncount += 1').body
    # Keep the original source-verified empty presentation consumer and commit
    # order shared. Owners still explicitly admit each record family.
    last=branch
    while len(last.orelse)==1 and isinstance(last.orelse[0],ast.If):last=last.orelse[0]
    if not last.orelse or ast.unparse(last.orelse[0])!='row = validate_empty_profile_record(record, **self.empty_receiver_state)':
        raise ValueError('Empty receiver branch changed')
    empty=ast.parse('def _consume_empty_record(self, record, sequence):\n    from civ6rl.native_deferred_empty_profile import validate_empty_profile_record').body[0]
    empty.body += [copy.deepcopy(n) for n in last.orelse if not (isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id=='count')]
    empty.args.kwonlyargs.append(ast.arg(arg='empty_receiver_state'))
    empty.args.kw_defaults.append(ast.Constant(None))
    for n in ast.walk(empty):
        if isinstance(n,ast.Call) and ast.unparse(n.func)=='validate_empty_profile_record':
            if len(n.keywords)!=1 or n.keywords[0].arg is not None:
                raise ValueError('Empty receiver profile boundary changed')
            n.keywords[0].value=ast.parse('self.empty_receiver_state if empty_receiver_state is None else empty_receiver_state',mode='eval').body
    shared.append(empty)
    last.orelse=ast.parse('self._consume_empty_record(record, sequence)\ncount += 1').body
    mixin=ast.ClassDef(name='DeferredHostQueue',bases=[],keywords=[],body=shared,decorator_list=[])
    tree.body.insert(tree.body.index(cls),mixin)
    cls.bases.insert(0,ast.Name(id='DeferredHostQueue',ctx=ast.Load()))
    controller=methods['controller_flag']
    cls.body.remove(controller)
    query=ast.ClassDef(name='HostControllerQuery',bases=[],keywords=[],body=[controller],decorator_list=[])
    tree.body.insert(tree.body.index(cls),query)
    cls.bases.append(ast.Name(id='HostControllerQuery',ctx=ast.Load()))
    return tree

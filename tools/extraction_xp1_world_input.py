"""Select XP1 source without duplicating world-click/catalogue/parser bodies."""
import ast

MODULES=('civ6rl.native_world_input','civ6rl.native_world_click','civ6rl.native_saved_combat')
TARGETS={MODULES[0]:('catalog_source','observe','apply'),
         MODULES[1]:('request_source','parse_request_result'),
         MODULES[2]:('queued_destination_source','queued_destination','queued_orders_source','queued_orders')}
DEFAULT='_WORLD_BASE_CORE_SHA256'

def parameterize(name,raw):
    if name not in MODULES:return raw
    tree=ast.parse(raw);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if not set(TARGETS[name])<=set(functions):raise ValueError('World-input extraction functions changed')
    for target in TARGETS[name]:
        fn=functions[target]
        if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('World-input source already parameterized')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Name(id=DEFAULT,ctx=ast.Load()))
        index=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                  and isinstance(fn.body[0].value.value,str)))
        for call in ast.walk(fn):
            if not isinstance(call,ast.Call):continue
            local=isinstance(call.func,ast.Name) and call.func.id in TARGETS[name]
            cross=(name==MODULES[0] and (isinstance(call.func,ast.Name) and call.func.id=='queued_destination'
                   or isinstance(call.func,ast.Attribute) and ast.unparse(call.func) in
                      ('click.request_source','click.parse_request_result')))
            if local or cross:call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
        if target=='catalog_source':
            fn.body[index:index]=ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_world_input_profile import verify_source
    verify_source(core_sha256)
''').body
        elif target=='observe':
            fn.body[index:index]=ast.parse('''
from civ6_host.runtime.xp1_world_input_profile import require_no_prompt
require_no_prompt(owner,obs['player_id'],core_sha256)
''').body
        elif target=='apply':
            fn.args.kwonlyargs.append(ast.arg(arg='snapshot_reader'));fn.args.kw_defaults.append(ast.Constant(None))
            imp=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.ImportFrom) and any(a.name=='snapshot' for a in n.names))
            fn.body[imp+1:imp+1]=ast.parse('''
if snapshot_reader is not None:
    if not callable(snapshot_reader):raise TypeError('Snapshot reader must be callable')
    snapshot=snapshot_reader
''').body
            fn.body[index:index]=ast.parse(f'''
if core_sha256 != {DEFAULT} and action.get('kind')=='world_war_response':
    raise ValueError('XP1 war confirmation is not qualified')
''').body
            matches=[]
            for node in ast.walk(fn):
                if isinstance(node,ast.Tuple) and all(isinstance(v,ast.Constant) for v in node.elts):
                    if tuple(v.value for v in node.elts)==('noop','war_prompt','declined'):
                        node.elts.append(ast.Constant('unsupported'));matches.append(node)
            if len(matches)!=1:raise ValueError('World-input UI-only invariant changed')
        elif target=='request_source':
            fn.body[index:index]=ast.parse('from civ6_host.runtime.xp1_world_input_profile import adapt_request_source').body
            returns=[n for n in ast.walk(fn) if isinstance(n,ast.Return)]
            if len(returns)!=1:raise ValueError('World-click source builder return changed')
            returns[0].value=ast.Call(func=ast.Name(id='adapt_request_source',ctx=ast.Load()),
                args=[returns[0].value,ast.Name(id='core_sha256',ctx=ast.Load())],keywords=[])
        elif target=='parse_request_result':
            fn.body[index:index]=ast.parse('from civ6_host.runtime.xp1_world_input_profile import selected_statuses').body
            class Status(ast.NodeTransformer):
                count=0
                def visit_Name(self,node):
                    if node.id!='_STATUS':return node
                    self.count+=1
                    return ast.Call(func=ast.Name(id='selected_statuses',ctx=ast.Load()),
                        args=[node,ast.Name(id='core_sha256',ctx=ast.Load())],keywords=[])
            visitor=Status();visitor.visit(fn)
            if visitor.count!=1:raise ValueError('World-click status guard changed')
        elif target=='queued_destination_source':
            stop=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Expr)
                      and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_player_id')
            original=fn.body[index:stop]
            if len(original)!=3:raise ValueError('Queued destination source proof seam changed')
            gate=ast.parse(f'''
if core_sha256 == {DEFAULT}:
    pass
else:
    from civ6_host.runtime.xp1_world_input_profile import verify_source
    verify_source(core_sha256)
''').body[0];gate.body=original;fn.body[index:stop]=[gate]
    pos=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)
                 and isinstance(tree.body[0].value.value,str)))
    while pos<len(tree.body) and isinstance(tree.body[pos],ast.ImportFrom) and tree.body[pos].module=='__future__':pos+=1
    tree.body[pos:pos]=ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

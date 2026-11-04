"""Select the existing DistrictProgressChanged algorithms' native ABI only."""
import ast

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_event_6d7163b0','native_event_6d7163b0_selector','native_host_events'}
TARGETS={'native_event_6d7163b0':('_check_object','_api','produce_records'),
         'native_event_6d7163b0_selector':('produce_auxiliary_record',)}
def _kw(call):
    if any(k.arg=='core_sha256' for k in call.keywords):raise ValueError('Placement event hook already applied')
    call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    if short=='native_host_events':
        methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields']
        if len(methods)!=1:raise ValueError('Shared dispatcher changed')
        branches=[n for n in ast.walk(methods[0]) if isinstance(n,ast.If)
                  and ast.unparse(n.test)==f'kind == {0x6d7163b0}']
        if len(branches)!=1:raise ValueError('District progress dispatch branch changed')
        calls=[n for n in ast.walk(branches[0]) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Name) and n.func.id=='produce_records']
        if len(calls)!=1:raise ValueError('District progress producer call changed')
        if any(k.arg=='core_sha256' for k in calls[0].keywords):raise ValueError('Placement dispatch already transformed')
        calls[0].keywords.append(ast.keyword(arg='core_sha256',value=ast.parse(
            f"getattr(self,'placement_core_sha256',{BASE!r})",mode='eval').body))
    else:
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for name in TARGETS[short]:
            fn=functions[name]
            if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
                raise ValueError('Placement event source already transformed')
            fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
            for call in ast.walk(fn):
                if not isinstance(call,ast.Call):continue
                target=ast.unparse(call.func)
                if target in ('_check_object','_api','query_secondary_value','read_player_civilization_type_id',
                              'produce_auxiliary_record','base._check_object','base._api'):_kw(call)
        if short=='native_event_6d7163b0':
            for n in ast.walk(functions['_check_object']):
                if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=='_TABLES':
                    n.value=ast.parse('_placement_events.select_tables(core_sha256,_TABLES)',mode='eval').body
            fn=functions['_api'];assign=[(i,n) for i,n in enumerate(fn.body) if isinstance(n,ast.Assign)
                                      and any(isinstance(t,ast.Name) and t.id=='specs' for t in n.targets)]
            if len(assign)!=1:raise ValueError('District progress native API moved')
            i,_=assign[0];fn.body[i+1:i+1]=ast.parse('specs=_placement_events.select_specs(core_sha256,specs)').body
            fn=functions['produce_records']
        else:fn=functions['produce_auxiliary_record']
        # Source bytes are admitted before the first selected pointer operation.
        checks=[i for i,n in enumerate(fn.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
                and ast.unparse(n.value.func) in ('_check_object','base._check_object')]
        if len(checks)!=1:raise ValueError('District progress first facade check moved')
        fn.body[checks[0]:checks[0]]=ast.parse('_placement_events.verify_once(core,read,core_sha256)').body
        i=0
        if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant):i=1
        while i<len(tree.body) and isinstance(tree.body[i],ast.ImportFrom) and tree.body[i].module=='__future__':i+=1
        tree.body[i:i]=ast.parse('from civ6_host.runtime import placement_event_profile as _placement_events').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

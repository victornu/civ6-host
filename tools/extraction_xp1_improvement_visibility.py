"""Select native ABI for shared early-turn ImprovementVisibility/Faith producers."""
import ast
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_event_f391d7b3','native_event_b3495127','native_host_events'}

def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    if short=='native_event_f391d7b3':
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for name in ('produce_record','produce_scoped_record'):
            fn=functions[name]
            if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
                raise ValueError('Improvement visibility already source-selected')
            fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
            calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func) in
                   ('shared.query_native_values','query_optional_position','produce_record')]
            if len(calls)!=(2 if name=='produce_record' else 1):raise ValueError('Improvement visibility query seam changed')
            for call in calls:
                if any(k.arg=='core_sha256' for k in call.keywords):raise ValueError('Duplicate engine selector')
                call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
    elif short=='native_event_b3495127':
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for name in ('_check','_api','produce_record_lease'):
            fn=functions[name]
            if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
                raise ValueError('FaithChanged already source-selected')
            fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
            for call in (n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func) in ('_check','_api')):
                call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
        for n in ast.walk(functions['_check']):
            if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=='_TABLES':
                n.value=ast.parse('_faith_events.select_tables(core_sha256,_TABLES)',mode='eval').body
        fn=functions['_api'];assign=[i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='entries' for t in n.targets)]
        if len(assign)!=1:raise ValueError('FaithChanged API dictionary seam changed')
        fn.body[assign[0]+1:assign[0]+1]=ast.parse('entries=_faith_events.select_specs(core_sha256,entries)').body
        i=0
        if isinstance(tree.body[0],ast.Expr):i=1
        while i<len(tree.body) and isinstance(tree.body[i],ast.ImportFrom) and tree.body[i].module=='__future__':i+=1
        tree.body[i:i]=ast.parse('from civ6_host.runtime import faith_event_profile as _faith_events').body
    else:
        methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields']
        if len(methods)!=1:raise ValueError('Shared event dispatcher changed')
        for kind,producer in ((0xf391d7b3,'produce_scoped_record'),(0xb3495127,'produce_record_lease')):
            branches=[n for n in ast.walk(methods[0]) if isinstance(n,ast.If) and ast.unparse(n.test)==f'kind == {kind}']
            if len(branches)!=1:raise ValueError('Early-turn shared branch changed')
            calls=[n for n in ast.walk(branches[0]) if isinstance(n,ast.Call) and ast.unparse(n.func)==producer]
            if len(calls)!=1 or any(k.arg=='core_sha256' for k in calls[0].keywords):raise ValueError('Early-turn producer seam changed')
            calls[0].keywords.append(ast.keyword(arg='core_sha256',value=ast.parse(
                f"getattr(self,'placement_core_sha256',{BASE!r})",mode='eval').body))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

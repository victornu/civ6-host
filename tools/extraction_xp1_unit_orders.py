"""Select XP1 source; preserve the shared unit-order Lua and executor."""
import ast

MODULES=('civ6rl.native_saved_unit_orders',)
TARGETS=('verify_source','verify_cancel_source','preamble','catalog_source','catalog','request_source','apply')
DEFAULT='_UNIT_ORDERS_BASE_CORE_SHA256'


def parameterize(name,raw):
    if name not in MODULES:return raw
    tree=ast.parse(raw);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if not set(TARGETS)<=set(functions):raise ValueError('Unit-order extraction functions changed')
    for target in TARGETS:
        fn=functions[target]
        if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('Unit orders already parameterized')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Name(id=DEFAULT,ctx=ast.Load()))
        index=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                  and isinstance(fn.body[0].value.value,str)))
        for call in ast.walk(fn):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in TARGETS:
                call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
        if target in ('verify_source','verify_cancel_source'):
            fn.body[index:index]=ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_unit_orders_profile import verify_source as selected_source
    return selected_source(core_sha256)
''').body
        if target=='apply':
            fn.args.kwonlyargs.append(ast.arg(arg='include_cancel'));fn.args.kw_defaults.append(ast.Constant(None))
            original=fn.body[index]
            if not isinstance(original,ast.Assign) or ast.unparse(original.targets[0])!='options':
                raise ValueError('Shared unit-order feature option changed')
            gate=ast.parse('''
if include_cancel is None:
    pass
else:
    if type(include_cancel) is not bool:raise ValueError('Exact unit cancel option required')
    options=dict(include_cancel=include_cancel)
''').body[0]
            gate.body=[original];fn.body[index]=gate
            fn.body[index:index]=ast.parse('from civ6_host.runtime.xp1_unit_orders_profile import selected_proof').body
            changed=[]
            for node in ast.walk(fn):
                if isinstance(node,ast.keyword) and node.arg in ('source_proof_sha256','cancel_source_proof_sha256'):
                    expected='PROOF_SHA' if node.arg=='source_proof_sha256' else 'CANCEL_PROOF_SHA'
                    if not isinstance(node.value,ast.Name) or node.value.id!=expected:raise ValueError('Shared unit-order receipt changed')
                    node.value=ast.Call(func=ast.Name(id='selected_proof',ctx=ast.Load()),
                        args=[node.value,ast.Name(id='core_sha256',ctx=ast.Load())],keywords=[]);changed.append(node.arg)
            if sorted(changed)!=['cancel_source_proof_sha256','source_proof_sha256']:raise ValueError('Missing unit-order receipts')
    pos=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)
                 and isinstance(tree.body[0].value.value,str)))
    while pos<len(tree.body) and isinstance(tree.body[pos],ast.ImportFrom) and tree.body[pos].module=='__future__':pos+=1
    tree.body[pos:pos]=ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

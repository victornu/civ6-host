"""Select the engine at the existing ImprovementChanged/RouteChanged seams."""
import ast
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_event_30ae2a3d','native_event_7b65ff2e','native_host_events'}
def expression(text):return ast.parse(text,mode='eval').body
def fn(tree,name):
    found=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(found)!=1:raise ValueError('Improvement/route function changed: '+name)
    return found[0]
def forward(scope,target,value):
    found=[n for n in ast.walk(scope) if isinstance(n,ast.Call) and ast.unparse(n.func)==target]
    if len(found)!=1 or any(k.arg=='core_sha256' for k in found[0].keywords):
        raise ValueError('Improvement/route shared call changed: '+target)
    found[0].keywords.append(ast.keyword(arg='core_sha256',value=expression(value)))
def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    at=next((i for i,n in enumerate(tree.body) if not isinstance(n,(ast.Import,ast.ImportFrom)) and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))),len(tree.body))
    tree.body[at:at]=ast.parse('from civ6_host.runtime import improvement_change_profile as _improvement_source').body
    if short!='native_host_events':
        function=fn(tree,'produce_record' if short=='native_event_30ae2a3d' else 'query_descriptor')
        if any(a.arg=='core_sha256' for a in (*function.args.args,*function.args.kwonlyargs)):
            raise ValueError('Improvement/route engine already present')
        function.args.kwonlyargs.append(ast.arg(arg='core_sha256'));function.args.kw_defaults.append(ast.Constant(BASE))
        at=int(bool(function.body and isinstance(function.body[0],ast.Expr) and isinstance(function.body[0].value,ast.Constant)))
        function.body[at:at]=ast.parse('_improvement_source.ensure_source(core_sha256)').body
        forward(function,'shared.query_native_values_at_position' if short=='native_event_30ae2a3d' else '_shared.query_descriptor','core_sha256')
    else:
        dispatch=fn(tree,'_dispatch_fields')
        for kind,target in ((0x30ae2a3d,'produce_record'),(0x7b65ff2e,'query_descriptor')):
            branches=[n for n in ast.walk(dispatch) if isinstance(n,ast.If) and ast.unparse(n.test)==f'kind == {kind}']
            if len(branches)!=1:raise ValueError('Improvement/route dispatch branch changed')
            branch=branches[0];engine=f"getattr(self,'improvement_core_sha256',{BASE!r})"
            forward(branch,target,engine)
            calls=[n for n in ast.walk(branch) if isinstance(n,ast.Call) and ast.unparse(n.func)=='self.emit']
            if len(calls)!=1:raise ValueError('Improvement/route receipt changed')
            proof=next((k for k in calls[0].keywords if k.arg=='source_proof_sha256'),None)
            selected=expression(f'_improvement_source.source_sha({engine},'+('PROOF_SHA256' if kind==0x30ae2a3d else repr('24157becb7c25402cd2816aa2633b6f33bcb58c6740f10080234bda80cbd13ef'))+')')
            if proof is None:calls[0].keywords.append(ast.keyword(arg='source_proof_sha256',value=selected))
            else:proof.value=selected
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

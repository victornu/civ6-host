"""Parameterize existing district producers without copying their algorithms."""
import ast
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_event_f74afc79','native_event_47261a7d','native_host_events'}


def expr(text):return ast.parse(text,mode='eval').body


def fn(tree,name):
    found=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(found)!=1:raise ValueError('District source function changed: '+name)
    return found[0]


def forward(scope,target,count=1):
    calls=[n for n in ast.walk(scope) if isinstance(n,ast.Call) and ast.unparse(n.func)==target]
    if len(calls)!=count or any(k.arg=='core_sha256' for c in calls for k in c.keywords):
        raise ValueError('District query call shape changed: '+target)
    for call in calls:call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name('core_sha256',ast.Load())))


def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    at=next((i for i,n in enumerate(tree.body) if not isinstance(n,(ast.Import,ast.ImportFrom))
        and not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))),len(tree.body))
    tree.body[at:at]=ast.parse('from civ6_host.runtime import district_damage_profile as _district_source').body
    if short!='native_host_events':
        for name in ('_check_object','build_native_api','lookup_item_lease','produce_record_lease'):
            f=fn(tree,name)
            if any(a.arg=='core_sha256' for a in (*f.args.args,*f.args.kwonlyargs)):
                raise ValueError('District query engine already selected')
            f.args.kwonlyargs.append(ast.arg(arg='core_sha256'));f.args.kw_defaults.append(ast.Constant(BASE))
            pos=int(bool(f.body and isinstance(f.body[0],ast.Expr) and isinstance(f.body[0].value,ast.Constant)))
            f.body[pos:pos]=ast.parse('_district_source.ensure_source(core_sha256)').body
        check=fn(tree,'_check_object')
        reads=[n for n in ast.walk(check) if isinstance(n,ast.Subscript) and ast.unparse(n.value)=='_TABLES']
        if len(reads)!=1:raise ValueError('District vtable selector changed')
        reads[0].value=expr('_district_source.select_tables(core_sha256,_TABLES)')
        build=fn(tree,'build_native_api')
        matches=[i for i,n in enumerate(build.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='entries' for t in n.targets)]
        if len(matches)!=1:raise ValueError('District ABI entries changed')
        build.body[matches[0]+1:matches[0]+1]=ast.parse('entries=_district_source.select_specs(core_sha256,entries)').body
        lookup=fn(tree,'lookup_item_lease');forward(lookup,'build_native_api');forward(lookup,'_check_object',4)
        produce=fn(tree,'produce_record_lease');forward(produce,'lookup_item_lease')
        checked=[i for i,n in enumerate(produce.body) if isinstance(n,ast.Expr)
                 and ast.unparse(n)=='_district_source.ensure_source(core_sha256)']
        if len(checked)!=1:raise ValueError('District source selection guard changed')
        produce.body.insert(checked[0]+1,ast.If(expr(f'core_sha256!={BASE!r}'),ast.parse('_district_source.verify_once(core,read,core_sha256=core_sha256)').body,[]))
    else:
        for name in ('_enqueue_district_damage_changed','_enqueue_district_combat_changed'):
            f=fn(tree,name)
            f.body[0:0]=ast.parse(f'core_sha256=getattr(self,"district_damage_core_sha256",{BASE!r})').body
            forward(f,'event.produce_record_lease')
            calls=[n for n in ast.walk(f) if isinstance(n,ast.Call) and ast.unparse(n.func)=='self.emit']
            if len(calls)!=2:raise ValueError('District producer receipts changed')
            for call in calls:
                proofs=[k for k in call.keywords if k.arg=='source_proof_sha256']
                if len(proofs)!=1 or ast.unparse(proofs[0].value)!='event.SOURCE_PROOF_SHA256':
                    raise ValueError('District receipt source identity changed')
                proofs[0].value=expr('_district_source.source_sha(core_sha256,event.SOURCE_PROOF_SHA256)')
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

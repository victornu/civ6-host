"""Select proof/ABI for the existing research family; preserve shared algorithms."""
import ast
from collections import Counter

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_research_actions','native_research_catalog',
         'native_player_operation_request','native_map_script'}


def _function(nodes,name):
    found=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(found)!=1:raise ValueError('Research extraction function changed: '+name)
    return found[0]


def _keyword(fn):
    if any(a.arg=='core_sha256' for a in fn.args.args+fn.args.kwonlyargs):
        raise ValueError('Research source already selected: '+fn.name)
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant(BASE))


def _forward(fn,targets,expression='core_sha256'):
    counts=Counter()
    for call in ast.walk(fn):
        if not isinstance(call,ast.Call):continue
        name=ast.unparse(call.func)
        if name not in targets:continue
        if any(k.arg=='core_sha256' for k in call.keywords):raise ValueError('Research call already selected')
        call.keywords.append(ast.keyword(arg='core_sha256',value=ast.parse(expression,mode='eval').body))
        counts[name]+=1
    if dict(counts)!=targets:raise ValueError('Research call anchors changed: '+repr(counts))


def _select_verifier(fn):
    _keyword(fn)
    at=int(bool(fn.body and isinstance(fn.body[0],ast.Expr)
        and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str)))
    fn.body[at:at]=ast.parse(f'''
if core_sha256 != {BASE!r}:
    from civ6_host.runtime.xp1_research_profile import verify_source as verify_selected_source
    return verify_selected_source(core_sha256)
''').body


def _request(tree):
    _select_verifier(_function(tree.body,'verify_source_evidence'))
    fn=_function(tree.body,'request_player_operation');_keyword(fn)
    _forward(fn,{'verify_source_evidence':1})
    # Swap only exact ABI constants within this one shared primitive. Storage,
    # ownership, typed variant validation and no-fake-archive logic stay intact.
    replacements={0x79e020:'abi.outer',0x81d838:'abi.parameters',0x81cfa0:'abi.reasons'}
    counts=Counter()
    class Select(ast.NodeTransformer):
        def visit_For(self,node):
            if isinstance(node.target,ast.Tuple) and [n.id for n in node.target.elts if isinstance(n,ast.Name)]==['vt','offset','target']:
                expected=((0x79e020,0x218,0x42f250),(0x79e020,0x220,0x42d960),
                          (0x81d838,0x130,0x74ce10),(0x81d838,0x60,0x74c5f0))
                if ast.literal_eval(node.iter)!=expected:raise ValueError('Player-operation slots changed')
                node.iter=ast.parse('abi.slots',mode='eval').body;counts['slots']+=1
            return self.generic_visit(node)
        def visit_Constant(self,node):
            if type(node.value) is int and node.value in replacements:
                counts[hex(node.value)]+=1;return ast.parse(replacements[node.value],mode='eval').body
            if node.value=='0x81d838':
                counts['vtable_result']+=1;return ast.parse('hex(abi.parameters)',mode='eval').body
            return node
        def visit_Name(self,node):
            if isinstance(node.ctx,ast.Load) and node.id in ('_METHODS','PINNED_EVIDENCE_SHA256'):
                counts[node.id]+=1
                return ast.parse('abi.methods' if node.id=='_METHODS' else 'abi.source_sha256',mode='eval').body
            return node
    Select().visit(fn)
    expected={'slots':1,'0x79e020':1,'0x81d838':1,'0x81cfa0':1,
              'vtable_result':1,'_METHODS':2,'PINNED_EVIDENCE_SHA256':1}
    if dict(counts)!=expected:raise ValueError('Player-operation ABI anchors changed: '+repr(counts))
    fn.body[1:1]=ast.parse('from civ6_host.runtime.xp1_research_profile import player_operation_abi\nabi = player_operation_abi(core_sha256, _METHODS)').body
    at=[i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='read' for t in n.targets)]
    if len(at)!=1:raise ValueError('Player-operation live read anchor changed')
    fn.body[at[0]+1:at[0]+1]=ast.parse(f'''
if core_sha256 != {BASE!r}:
    from civ6_host.runtime.xp1_research_profile import verify_live
    verify_live(base, read, core_sha256=core_sha256)
''').body


def parameterize(name,raw):
    leaf=name.rsplit('.',1)[-1]
    if leaf not in MODULES:return raw
    tree=ast.parse(raw)
    if leaf=='native_research_actions':
        _select_verifier(_function(tree.body,'verify_source'))
        mappings={'_candidate_prefix':{'verify_source':1},'candidate_source':{'_candidate_prefix':1},
            'effect_source':{'verify_source':1},'guard_case':{'candidate_source':2,'effect_source':2}}
        for name,targets in mappings.items():
            fn=_function(tree.body,name);_keyword(fn);_forward(fn,targets)
    elif leaf=='native_research_catalog':
        for name,targets in {'catalog_source':{'verify_source':1},'revalidate_choice_source':{'verify_source':1},
                'guard_case':{'catalog_source':2,'revalidate_choice_source':1}}.items():
            fn=_function(tree.body,name);_keyword(fn);_forward(fn,targets)
    elif leaf=='native_player_operation_request':_request(tree)
    else:
        classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeMapScriptPrefix']
        if len(classes)!=1:raise ValueError('Research action owner changed')
        fn=_function(classes[0].body,'inspect_player_research_choice')
        fn.args.kwonlyargs.append(ast.arg(arg='submit_preselected'))
        fn.args.kw_defaults.append(ast.Constant(False))
        matches=[n for n in fn.body if isinstance(n,ast.If)
                 and ast.unparse(n.test)=="before['confirmed']"]
        if len(matches)!=1:raise ValueError('Preselected research branch changed')
        matches[0].test=ast.parse("before['confirmed'] and not submit_preselected",mode='eval').body
        _forward(fn,{'catalog_source':1,'effect_source':1,'revalidate_choice_source':1,'request_player_operation':1},
                 f'getattr(self,"operation_core_sha256",{BASE!r})')
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

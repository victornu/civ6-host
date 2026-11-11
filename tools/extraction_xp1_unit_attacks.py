"""Select engine proofs in the retained attack algorithms, without rewriting Lua."""
import ast
from copy import deepcopy
from pathlib import Path

MODULES=('civ6rl.native_combat_actions','civ6rl.native_saved_combat','civ6rl.native_saved_city_targets')
DEFAULT='_UNIT_ATTACK_BASE_CORE_SHA256'
TARGETS={MODULES[0]:('verify_source_evidence','candidate_source','parse_candidates','request_source','build_guard_case'),
         MODULES[1]:('relationships','catalog','unit_state_source','unit_state','effect','apply'),
         MODULES[2]:('verify_source','source','catalog','request_source')}
PURE={MODULES[1]:('validate_action','validate_units','verify_observation','validate_relationships'),
      MODULES[2]:('validate_cities',)}
CONTRACT=Path(__file__).resolve().parents[1]/'src/civ6_host/contracts/capability_unit_attacks.py'


def _portable(node):
    class Convert(ast.NodeTransformer):
        def visit_Attribute(self,n):
            if isinstance(n.value,ast.Name) and n.value.id=='native' and n.attr in ('_uint','_player_id'):
                return ast.copy_location(ast.Name(id=n.attr,ctx=ast.Load()),n)
            return self.generic_visit(n)
    return Convert().visit(deepcopy(node))


def _forward(call):
    if any(k.arg=='core_sha256' for k in call.keywords):
        if not all(k.arg!='core_sha256' or ast.unparse(k.value)=='core_sha256' for k in call.keywords):
            raise ValueError('Attack source engine forwarding conflicts')
        return
    call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))


def parameterize(name,raw):
    if name not in MODULES:return raw
    tree=ast.parse(raw);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if not set(TARGETS[name])<=set(functions):raise ValueError('Attack extraction functions changed')
    # Exactly shared portable validators; changes to either source stop extraction.
    portable={n.name:n for n in ast.parse(CONTRACT.read_text()).body if isinstance(n,ast.FunctionDef)}
    for target in PURE.get(name,()):
        if ast.dump(_portable(functions[target]),include_attributes=False)!=ast.dump(portable[target],include_attributes=False):
            raise ValueError('Shared attack validator differs from portable contract: '+target)
        tree.body.remove(functions[target])
    for target in TARGETS[name]:
        fn=functions[target]
        if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('Attack function already selected')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Name(id=DEFAULT,ctx=ast.Load()))
        index=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                       and isinstance(fn.body[0].value.value,str)))
        cross={'native.verify_source_evidence','native.candidate_source','native.parse_candidates','native.request_source',
               'city_targets.catalog','city_targets.request_source'}
        for call in ast.walk(fn):
            if not isinstance(call,ast.Call):continue
            local=isinstance(call.func,ast.Name) and call.func.id in TARGETS[name]
            queued=name==MODULES[1] and isinstance(call.func,ast.Name) and call.func.id=='queued_destination'
            if local or queued or ast.unparse(call.func) in cross:_forward(call)
        if target in ('verify_source_evidence','verify_source'):
            fn.body[index:index]=ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_unit_attack_profile import verify_source as selected_source
    return selected_source(core_sha256)
''').body
        if name==MODULES[1] and target in ('relationships','effect'):
            fn.body[index:index]=ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_unit_attack_profile import verify_source as selected_source
    selected_source(core_sha256)
''').body
        if name==MODULES[1] and target=='effect':
            for argument in ('live_core','live_read'):
                fn.args.kwonlyargs.append(ast.arg(arg=argument))
                fn.args.kw_defaults.append(ast.Constant(None))
            calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                   and n.func.id=='completed_cycle']
            if len(calls)!=1:raise ValueError('Attack lifecycle fallback seam changed')
            seam=next(n for n in ast.walk(fn) if isinstance(n,ast.If) and calls[0] in list(ast.walk(n)))
            if ast.unparse(seam.test)!='not changed and delivery_window is not None':
                raise ValueError('Attack lifecycle fallback guard changed')
            seam.body[:]=ast.parse('''
from civ6_host.runtime.xp2_unit_attack_source import attack_cycle
lifecycle = attack_cycle(delivery_window, selected, pid, queued_before, queued_after,
    core_sha256=core_sha256, state_unchanged=before == after and units_before == units_after and cities_before == cities_after,
    live_core=live_core, live_read=live_read)
''').body
        if name==MODULES[1] and target=='apply':
            for argument in ('live_core','live_read'):
                fn.args.kwonlyargs.append(ast.arg(arg=argument))
                fn.args.kw_defaults.append(ast.Constant(None))
            fn.body[index:index]=ast.parse('from civ6_host.runtime.xp1_unit_attack_profile import selected_proof, selected_queued_proof').body
            calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func)=='effect']
            if len(calls)!=1:raise ValueError('Attack effect call seam changed')
            calls[0].keywords.extend(ast.parse(
                "f(live_core=live_core, live_read=live_read)"
            ).body[0].value.keywords)
            found=[]
            for keyword in (n for n in ast.walk(fn) if isinstance(n,ast.keyword)):
                expected={'queued_source_sha256':'QUEUED_SOURCE_SHA','source_proof_sha256':'native._PROOF_SHA256',
                          'city_target_source_sha256':'city_targets.SOURCE_SHA'}.get(keyword.arg)
                if expected is None:continue
                value=keyword.value.body if isinstance(keyword.value,ast.IfExp) else keyword.value
                if ast.unparse(value)!=expected:raise ValueError('Attack emitted source seam changed: '+keyword.arg)
                replacement=ast.Call(func=ast.Name(id='selected_queued_proof' if keyword.arg=='queued_source_sha256'
                    else 'selected_proof',ctx=ast.Load()),args=[value,ast.Name(id='core_sha256',ctx=ast.Load())],keywords=[])
                if isinstance(keyword.value,ast.IfExp):keyword.value.body=replacement
                else:keyword.value=replacement
                found.append(keyword.arg)
            if set(found)!={'queued_source_sha256','source_proof_sha256','city_target_source_sha256'} or len(found)!=3:
                raise ValueError('Attack receipt source count changed')
    _readiness_collection(name,functions)
    _visible_collection(name,functions)
    pos=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)
                 and isinstance(tree.body[0].value.value,str)))
    while pos<len(tree.body) and isinstance(tree.body[pos],ast.ImportFrom) and tree.body[pos].module=='__future__':pos+=1
    additions=ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}').body
    if name in PURE:
        additions+=ast.parse('from civ6_host.contracts.capability_unit_attacks import '+', '.join(PURE[name])).body
    tree.body[pos:pos]=additions
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'


def _readiness_collection(name,functions):
    """Select the source-proven XP1 readiness correction at all three seams."""
    targets=({'candidate_source':'unit_candidates','request_source':'unit_request'} if name==MODULES[0]
             else {'source':'city_source'} if name==MODULES[2] else {})
    for target,kind in targets.items():
        fn=functions[target]
        returns=[n for n in ast.walk(fn) if isinstance(n,ast.Return)]
        if len(returns)!=1:raise ValueError('Shared attack readiness return seam changed: '+target)
        pos=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                     and isinstance(fn.body[0].value.value,str)))
        fn.body[pos:pos]=ast.parse('from civ6_host.runtime.xp1_unit_attack_profile import selected_readiness_source').body
        returns[0].value=ast.Call(func=ast.Name(id='selected_readiness_source',ctx=ast.Load()),
            args=[returns[0].value,ast.Name(id='core_sha256',ctx=ast.Load()),ast.Constant(kind)],keywords=[])


def _visible_collection(name,functions):
    """The opt-in read path reuses the full collector; default/action paths stay full."""
    targets=('catalog',) if name==MODULES[1] else ('source','catalog') if name==MODULES[2] else ()
    for target in targets:
        fn=functions[target]
        if any(arg.arg=='visible_scope' for arg in fn.args.kwonlyargs):
            raise ValueError('Visible city source already selected')
        fn.args.kwonlyargs.append(ast.arg(arg='visible_scope'));fn.args.kw_defaults.append(ast.Constant(None))
        if target=='catalog':
            cross='city_targets.catalog' if name==MODULES[1] else 'source'
            calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func)==cross]
            if len(calls)!=1:raise ValueError('Shared city catalogue call seam changed')
            calls[0].keywords.append(ast.keyword(arg='visible_scope',value=ast.Name(id='visible_scope',ctx=ast.Load())))
            fn.body[:0]=ast.parse("from civ6_host.runtime.xp1_attack_visible_scope import check, checked_result\ncheck(visible_scope,prefix,turn,player_id,core_sha256)").body
            returns=[n for n in ast.walk(fn) if isinstance(n,ast.Return)]
            if len(returns)!=1:raise ValueError('Shared attack catalogue return seam changed')
            returns[0].value=ast.Call(func=ast.Name(id='checked_result',ctx=ast.Load()),
                args=[ast.Name(id=s,ctx=ast.Load()) for s in ('visible_scope','prefix','turn','player_id','core_sha256')]+[returns[0].value],keywords=[])
        else:
            fn.body[:0]=ast.parse('from civ6_host.runtime.xp1_attack_visible_scope import source_for_scope').body
            returns=[n for n in ast.walk(fn) if isinstance(n,ast.Return)]
            if len(returns)!=1:raise ValueError('Shared city source return seam changed')
            returns[0].value=ast.Call(func=ast.Name(id='source_for_scope',ctx=ast.Load()),
                args=[returns[0].value,ast.Name(id='visible_scope',ctx=ast.Load())],
                keywords=[ast.keyword(arg=s,value=ast.Name(id=s,ctx=ast.Load())) for s in ('turn','player_id','core_sha256')])

"""Add an explicit scalar supplement without widening historical catalogs."""
import ast
import copy
MODULES={'native_scalar_event_encoder','native_deferred_empty_profile','native_host_events'}


def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    if short=='native_scalar_event_encoder':
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for name,target in (('decode_core_fields','_decode_profile_fields'),('encode_record','_encode_profile_record')):
            if target in functions:raise ValueError('Scalar primitive already extracted')
            fn=functions[name];inner=copy.deepcopy(fn);inner.name=target
            matches=[i for i,n in enumerate(inner.body) if isinstance(n,ast.Assign)
                     and ast.unparse(n)=='row = candidate_for(event_kind)']
            if len(matches)!=1:raise ValueError('Scalar catalog lookup seam changed')
            del inner.body[matches[0]]
            if inner.args.args[0].arg!='event_kind':raise ValueError('Scalar primitive parameters changed')
            inner.args.args[0]=ast.arg(arg='row')
            args='row, raw_fields' if name=='decode_core_fields' else 'row, sequence, values, queue_metadata=queue_metadata'
            fn.body=ast.parse(f'row = candidate_for(event_kind)\nreturn {target}({args})').body
            tree.body.insert(tree.body.index(fn),inner)
    elif short=='native_deferred_empty_profile':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='resolve_empty_receiver_row')
        if not isinstance(fn.body[-1],ast.Return):raise ValueError('Deferred receiver lookup seam changed')
        fn.body[-1:-1]=ast.parse('''
if row is None and type(record_type) is int and record_type in (0x104,0x105):
    from civ6_host.runtime.game_history_event_profile import receiver_rows
    return receiver_rows()[record_type]
if row is None and type(record_type) is int and record_type == 0x10a:
    from civ6_host.runtime.game_era_score_event_profile import receiver_row
    return receiver_row()
if row is None and type(record_type) is int and record_type in (0x135,0x136,0x137,0x138,0x13b,0x145):
    from civ6_host.runtime.xp2_turn_event_records import receiver_rows
    return receiver_rows()[record_type]
if row is None and type(record_type) is int and record_type == 0x142:
    from civ6_host.runtime.xp2_favor_event_profile import receiver_rows
    return receiver_rows()[record_type]
if row is None and type(record_type) is int and record_type == 0xc9:
    from civ6_host.runtime.xp2_wmd_fallout_visibility import receiver_row
    return receiver_row()
''').body
    else:
        methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields']
        if len(methods)!=1:raise ValueError('Shared dispatcher seam changed')
        fn=methods[0]
        if ast.unparse(fn.body[0])!='self._require_no_f391_reentry()':
            raise ValueError('Shared producer reentry guard seam changed')
        fn.body[1:1]=ast.parse('''
if kind in (0x4710f1a4,0xf50673b7,0x788b7534):
    from civ6_host.runtime.a0_game_history_events import dispatch
    return dispatch(self,kind,raw_fields)
''').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

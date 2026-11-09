"""XP1 DistrictProgressChanged, reusing the retained shared EXE producer."""
from functools import lru_cache
from types import MappingProxyType
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
from .xp1_production_placement_profile import SOURCE, verify_source

EVENT_KIND=0x6d7163b0
TABLE_NAMES={'outer':'outer','player':'player','collection':'district_collection',
             'item':'district','map':'map','plot':'plot'}
OPERATION_NAMES={'get_player':'get_player','release_player':'release_player',
 'player_collection':'player_districts','release_collection':'release_collection',
 'collection_index':'district_by_id','release_item':'release_district',
 'item_raw':'district_type','item_variant':'district_city_descriptor',
 'item_snapshot':'district_snapshot70','free_vector':'free_snapshot_vector',
 'outer_map':'outer_map','release_map':'release_map','map_plot':'get_plot',
 'release_plot':'release_plot','plot_value':'plot_value'}


def _abi(core_sha256):
    if core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256):raise ValueError('Unqualified placement-event engine')
    from .foundation_facade_profiles import query_abi
    from .paths import resource_root
    if core_sha256 == XP1_CORE_SHA256:
        verify_source(core_sha256)
    else:
        from .xp2_placement_event_source import source as xp2_source
        xp2_source()
    return query_abi(core_sha256,resource_root())


def select_tables(core_sha256, retained):
    if core_sha256==BASE_CORE_SHA256:return retained
    abi=_abi(core_sha256);selected={}
    if set(retained)!=set(TABLE_NAMES):raise ValueError('District-progress table set changed')
    xp2_faith_tables = None
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_placement_event_source import source
        xp2_faith_tables = source()['faith_query_abi']['tables']
    for name,(_,slots) in retained.items():
        table_name=TABLE_NAMES[name]
        table,available=abi.tables[table_name]
        chosen=[]
        for slot,_ in slots:
            semantic = [(op_name, spec) for op_name, spec in abi.operations.items()
                        if spec.get('table') == table_name and spec.get('slot') == slot]
            target = semantic[0][1]['rva'] if len(semantic) == 1 else None
            # The retained outer release entry is not part of the 35-operation
            # query subset. Its XP2 slot/body is separately source-pinned by
            # the Faith facade profile and remains the same outer vtable.
            if target is None and core_sha256==XP2_CORE_SHA256 and name=='outer' and slot==8:
                target=int(xp2_faith_tables['outer']['slots']['0x8'],16)
            if target is None or available.get(slot) != target:
                raise ValueError('District-progress operation lacks a selected semantic slot: '+name+':'+hex(slot))
            chosen.append((slot,target))
        selected[name]=(table,tuple(chosen))
    return selected


def select_specs(core_sha256, retained):
    if core_sha256==BASE_CORE_SHA256:return retained
    abi=_abi(core_sha256)
    if set(retained)!=set(OPERATION_NAMES):raise ValueError('District-progress API set changed')
    return {name:(abi.rva(OPERATION_NAMES[name]),result,args)
            for name,(_,result,args) in retained.items()}


def verify_once(core,read,core_sha256):
    if core_sha256==BASE_CORE_SHA256:return
    _abi(core_sha256)
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    verify_xp1_once(core,core._handle,read,resource_root(),core_sha256=core_sha256)


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_placement_event_source import source_dependencies as selected
        return selected()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unqualified placement-event source engine')
    from .xp1_production_placement_profile import source_dependencies as sources
    from .improvement_visibility_profile import source_dependencies as visibility
    return {**sources(),**visibility()}


@lru_cache(maxsize=2)
def event_profile(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_placement_event_source import event_profile as selected
        return selected(core_sha256=core_sha256)
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unqualified placement event profile engine')
    verify_source()
    from .a0_family_source import A0FamilyProfile
    from .native.native_event_6d7163b0 import verify_source_evidence
    from .native.native_event_6d7163b0_selector import verify_source_evidence as selector
    from .native.native_deferred_empty_profile import _ROWS
    verify_source_evidence();selector()
    for kind,size in ((157,144),(163,128)):
        if tuple(_ROWS[kind]['record_sizes'])!=(size,):
            raise ValueError('District progress receiver shape changed')
    from . import improvement_visibility_profile as visibility,faith_event_profile as faith,game_history_event_profile as history
    visibility.verify_source()
    faith.verify_source()
    history.verify_source()
    from . import game_era_score_event_profile as score
    score.verify_source()
    from . import xp1_goody_hut_profile as goody
    goody.verify_source()
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    for record,row in history.receiver_rows().items():
        if resolve_empty_receiver_row(record)!=row:raise ValueError('History/era receiver changed')
    if resolve_empty_receiver_row(0x10a)!=score.receiver_row():raise ValueError('Era-score receiver changed')
    kinds={EVENT_KIND:frozenset((157,163)),visibility.EVENT_KIND:frozenset((145,)),faith.EVENT_KIND:frozenset((194,))}
    kinds.update({kind:frozenset((spec[0],)) for kind,spec in history.EVENTS.items()})
    kinds[score.EVENT_KIND]=frozenset((0x10a,))
    kinds[goody.EVENT_KIND]=frozenset((259,))
    return A0FamilyProfile(MappingProxyType(kinds),
                           MappingProxyType({157:144,163:128,145:160,194:96,259:112,260:96,261:96,266:96}),goody.SOURCE[1])


def bind_owner(backend,core,read,*,core_sha256=XP1_CORE_SHA256):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256!=core_sha256:
        raise ValueError('District-progress source owner mismatch')
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_placement_event_source import bind_owner as bind_xp2
        bind_xp2(backend,core,read)
        from .improvement_visibility_profile import bind_owner as bind_visibility
        bind_visibility(backend,core,read,core_sha256=core_sha256)
        from .faith_event_profile import bind_owner as bind_faith
        bind_faith(backend,core,read,core_sha256=core_sha256)
        from .xp1_goody_hut_profile import bind_owner as bind_goody
        bind_goody(backend,core,read,core_sha256=core_sha256)
        from .xp2_placement_event_source import event_profile as xp2_profile
        return xp2_profile(core_sha256=core_sha256,
            execution_image=getattr(core,'_civ6_host_execution_image',None))
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unqualified placement source owner engine')
    verify_once(core,read,core_sha256)
    from .improvement_visibility_profile import bind_owner as bind_visibility
    bind_visibility(backend,core,read)
    from .faith_event_profile import bind_owner as bind_faith
    bind_faith(backend,core,read)
    from .game_history_event_profile import bind_owner as bind_history
    bind_history(backend,core,read)
    from .game_era_score_event_profile import bind_owner as bind_score
    bind_score(backend,core,read)
    from .xp1_goody_hut_profile import bind_owner as bind_goody
    bind_goody(backend,core,read)
    return event_profile()

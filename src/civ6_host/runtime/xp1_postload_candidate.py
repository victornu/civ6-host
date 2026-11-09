"""Explicit +160 candidate using the retained official Load/cache owner.

No public admission, cache gate, pending state or callback result is fabricated.
The original Core performs its transition; unknown host callbacks remain fatal.
"""
import ctypes as C
import struct
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from . import postload160_source as source
from .xp1_saved_load import REFERENCE, validate_candidate_inputs

ACTIVE_STAGE='post160-candidate-active'
FINISHED_STAGE='post160-candidate-observed-awaiting-controlled-stop'
AUX90_QUALIFICATION=('evidence/host-xp1-postload-events.json',
                     '08687c30d97e6be9f83dc94cec889e7b051fd7d6ee648a62173b0a7ce905f7b8')


def _aux90_qualification():
    """Retain the transport qualification without claiming gameplay listeners."""
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from pathlib import Path
    evidence=_source(AUX90_QUALIFICATION);transport=evidence['transport']
    reference=evidence['native_receipt']
    receipt_path = resolve_path(Path(reference['path'])).resolve()
    relative = receipt_path.relative_to(resource_root()).as_posix()
    receipt=_source((relative,reference['sha256']))
    if (evidence['schema']!='civ6_host.xp1_postload_event_delivery.v1'
            or evidence['status']!='native_transport_qualified_full_load_not_admitted'
            or evidence['source']['sha256']!=source.SOURCE[1]
            or transport['source_sha256']!=source.SOURCE[1]
            or any(transport[key] is not True for key in ('real_hks_dispatch','core_scope_owned_by_core',
                'protected_stack_and_script_lock_closed','service_unknown_inputs_remain_fatal'))
            or any(transport[key] is not False for key in ('outer160_called','loaded_game_qualified',
                'official_gameplay_listeners_qualified','category2_gameplay_factory_qualified'))
            or receipt['status']!='native_aux90_group_passed' or receipt['stage']!='aux90'
            or receipt['exit_code']!=0 or receipt['reaped'] is not True
            or receipt['shared_backend_executed'] is not True or receipt['saved_game_loaded'] is not False):
        raise ValueError('Retained AUX90 transport qualification differs')
    return evidence,(relative,reference['sha256'])


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .loaded_cache_publication import source_dependencies as cache_dependencies
        from .xp2_postload_aux90_source import source_dependencies as aux_dependencies
        from .xp2_bundle_inputs import REFERENCE as xp2_reference
        from .a0_family_source import _path,verify_pinned_files
        pins=source.source_pins(core_sha256)
        pins.update(cache_dependencies(core_sha256=core_sha256))
        pins.update(aux_dependencies())
        pins[str(_path(xp2_reference[0]))]=xp2_reference[1]
        verify_pinned_files(pins)
        return pins
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown post160 candidate engine')
    from .loaded_cache_profiles import SOURCE as cache_source
    from .paths import resource_root
    from .resource_resolution import resolve_path
    pins=source.source_pins()
    proof=_source(cache_source)
    from .script_event_source import SOURCE as event_source,source as verify_events
    events=verify_events()
    _,aux_receipt=_aux90_qualification()
    refs=[cache_source,REFERENCE,event_source,AUX90_QUALIFICATION,aux_receipt]
    refs.extend((r['path'],r['sha256']) for r in proof['references'].values())
    refs.extend((r['path'],r['sha256']) for r in events['references'].values())
    for path,digest in refs:pins[str(resolve_path(resource_root()/path).resolve())]=digest
    return pins


def expected_major_ids(owner):
    core_sha256=getattr(getattr(owner,'load_abi',None),'core_sha256',XP1_CORE_SHA256)
    if core_sha256==XP2_CORE_SHA256:
        from .captured_saved_load import validate_candidate_inputs as validate_xp2
        validate_xp2(owner.inputs,owner.captured_bundle)
        if (owner.loaded_readback!=owner.captured_bundle.expected_readback
                or type(owner.loaded_roster) is not bytes):
            raise ValueError('XP2 +160 requires its captured loaded readback')
        fields=tuple(map(int,owner.loaded_roster.decode('ascii').split('|')))
        if fields!=(owner.captured_bundle.initial_turn,44,26,0,1):
            raise ValueError('XP2 +160 roster/turn/map differs from its two-major capture')
        return fields[3:]
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown post160 candidate engine')
    validate_candidate_inputs(owner.inputs,owner.captured_bundle)
    if (owner.captured_bundle.reference!=REFERENCE or owner.inputs is not owner.captured_bundle.inputs
            or owner.loaded_readback!=owner.captured_bundle.expected_readback
            or type(owner.loaded_roster) is not bytes):
        raise ValueError('XP1 +160 requires its captured loaded readback')
    fields=tuple(map(int,owner.loaded_roster.decode('ascii').split('|')))
    if fields!=(owner.captured_bundle.initial_turn,74,46,0,1,2,3,4,5):
        raise ValueError('XP1 +160 roster/turn/map differs from its six-major capture')
    return fields[3:]


def select_profile(attempt,mode):
    from .native.native_official_postload import OfficialPost160Backend
    from .native.native_official_load import OfficialLoadBackend
    from .loaded_cache_publication import LoadedCachePublication
    if mode not in ('public','candidate'):raise ValueError('Unknown postload mode')
    profile=source.profile_for_sha(attempt.owner.load_abi.core_sha256)
    if mode=='public':return source.require_runtime_admission(profile)
    b=attempt.owner
    if (type(attempt) is not OfficialPost160Backend or type(b) is not OfficialLoadBackend
            or profile.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or getattr(b,'_saved_load_candidate',False) is not True
            or hasattr(b,'_xp1_post160_attempt')):
        raise ValueError('XP1 candidate +160 requires its first exact official Load owner')
    lease=getattr(attempt.facade,'publication_owner',None)
    if type(lease) is not LoadedCachePublication or lease.owner is not b:
        raise ValueError('XP1 +160 requires the real completed cache lease')
    attempt.expected_major_ids=expected_major_ids(b)
    if profile.core_sha256==XP1_CORE_SHA256:_aux90_qualification()
    else:
        from .xp2_postload_aux90_source import source as aux_source
        aux_source()
    attempt._candidate_cache_lease=lease
    b._xp1_post160_attempt=attempt
    return profile


def _aux90(attempt):
    from .saved_load_services import SavedLoadServices
    from .script_event_service import ScriptEventService
    b=attempt.owner;p=b.prefix;e=getattr(p,'events',None)
    if (type(p) is not SavedLoadServices or type(e) is not ScriptEventService
            or p.backend is not b or p.host is not b.host or p.context!=b.context or p.core is not b.core
            or e.host is not b.host or e.runtime is not p.runtime
            or getattr(e,'aux90_installed',False) is not True or getattr(e,'aux90_poisoned',True)
            or e.dispatch_depth or p.runtime.service_owner is not b.host
            or not callable(getattr(p.runtime.host,'LAB_Aux90DispatchCategoryNull',None))):
        raise ValueError('XP1 +160 requires the actual installed AUX90 category2/NULL service')
    e._check();p.check()
    table=C.addressof(b.host.aux_vtable);binding=b.host._slot_bindings.get((table,0x90))
    if (binding is None or binding[0]!=b.host.aux_vtable[0x90//8]
            or e.installed.get(0x90)!=binding[0]
            or getattr(binding[1],'__self__',None) is not e
            or getattr(binding[1],'__func__',None) is not ScriptEventService.dispatch_postload_aux90_null):
        raise ValueError('XP1 +160 AUX90 callback ownership was replaced')
    if attempt.post160_abi.core_sha256==XP2_CORE_SHA256:
        attempt.aux90_validation=p.validate_postload_aux90()
        if attempt.aux90_validation['core_sha256']!=XP2_CORE_SHA256:
            raise ValueError('XP2 +160 AUX90 selected a different engine')


def _completed_cache(attempt):
    from .native.native_official_postload import OfficialFacadeBackend,validate_owner,validate_receipt
    from .loaded_cache_profiles import validate_copy
    b=attempt.owner;a=attempt.facade;r=attempt.facade_result
    inputs=validate_owner(b,stage='facades-candidate-observed')
    if (type(a) is not OfficialFacadeBackend or a.owner is not b or a.publication_mode!='candidate'
            or a.attempted is not True or getattr(a,'completed_result',None) is not r
            or a.receipt is not getattr(b,'raw_load_result',None)):
        raise ValueError('XP1 +160 lacks its actual retained raw-Load/cache results')
    validate_receipt(a.receipt,inputs)
    flags={'cache_facades_populated':True,'jobs_identical':True,'post160_called':False,
           'game_update_called':False,'publish190_called':False,'context_destroyed':False,
           'candidate_native_cache_only':True,'public_cache_gate_enabled':False,'post160_admitted':False,
           'owners_retained':True,'controlled_stop_required':True}
    if type(r) is not dict or any(r.get(k) is not v for k,v in flags.items()):
        raise ValueError('XP1 +160 cache result scope differs')
    p=a.publisher;lease=attempt._candidate_cache_lease
    if (p is None or p is not b.prefix.view_publisher or lease is not a.publication_owner
            or lease.publisher is not p or p.native_cache_gate is not False
            or p.full_facade_initialization_reproduced is not False
            or type(p.cache_map_snapshot) is not bytes or len(p.cache_map_snapshot)!=28
            or r.get('cache_snapshot_hex')!=p.cache_map_snapshot.hex()):
        raise ValueError('XP1 +160 retained native cache or private gate differs')
    state=validate_copy(b.core._handle,b.context,b.runtime.read,a.cache_abi,p._facades,p.cache_map_snapshot,
        expected_game=b.bound_identity['game'],expected_dimensions=(b.loaded_readback['width'],b.loaded_readback['height']))
    if state!=a.validated_candidate_cache:
        raise ValueError('XP1 +160 cache ownership/copy changed since native publication')
    lease.validate_completed_post160(attempt)
    expected_major_ids(b);_aux90(attempt)


def enter(attempt):
    from .native import native_checkpoint_postload160 as post
    from .xp1_load_capability import begin_cache_source_scope
    _completed_cache(attempt)
    post.check_live_post160(attempt.owner.core._handle,attempt.owner.runtime.read,attempt.proof,
                           core_sha256=attempt.post160_abi.core_sha256)
    attempt._facade_attempt=attempt.facade
    attempt._candidate_cache_lease.begin_post160(attempt)
    begin_cache_source_scope(attempt.facade)


def check_active(attempt):
    from .native.native_official_postload import OfficialPost160Backend
    b=attempt.owner;lease=attempt._candidate_cache_lease
    if (type(attempt) is not OfficialPost160Backend or attempt.postload_mode!='candidate'
            or b._xp1_post160_attempt is not attempt or b.stage!=ACTIVE_STAGE
            or b.busy is not True or lease.post160_attempt is not attempt
            or getattr(b,'_saved_load_job_cache_owner',None) is not lease
            or attempt._facade_attempt is not attempt.facade):
        raise ValueError('XP1 +160 candidate does not own its active cache lease')
    lease._check();_aux90(attempt)


def transition_state(attempt):
    b=attempt.owner;fields=attempt.proof['contract']['state_globals'];values={}
    for name,size in (('current',1),('pending',1),('requested',1),('remaining',4),
                      ('player_or_target',4),('stop_limit_or_parameter',4)):
        raw=b.runtime.read(b.core._handle+fields[name],size)
        if type(raw) is not bytes or len(raw)!=size:raise ValueError('Incomplete native post160 state read')
        values[name]=int.from_bytes(raw,'little')
    return values


def before_call(attempt):
    check_active(attempt)
    if attempt.native_call_attempted or attempt.owner.snapshot_phase!='before':
        raise ValueError('XP1 +160 requires one exclusive call after its actual before-job snapshot')
    attempt.transition_before=transition_state(attempt)
    label,reference=_selected_source(attempt)
    attempt.owner.emit(label+'_post160_transition_before',state=attempt.transition_before,
                       state_modified_by_host=False,source_sha256=reference[1],public_session_admitted=False)


def _selected_source(attempt):
    if attempt.post160_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_postload_source import SOURCE
        return 'xp2',SOURCE
    if attempt.post160_abi.core_sha256==XP1_CORE_SHA256:return 'xp1',source.SOURCE
    raise ValueError('Unknown post160 candidate engine')


def after_call(attempt):
    check_active(attempt);attempt.transition_after=transition_state(attempt)
    before,after=attempt.transition_before,attempt.transition_after
    if before['pending']==0:
        branch='pending_zero_no_transition';expected=before
    elif before['requested']==before['current']:
        branch='pending_cleared_same_raw_state';expected=dict(before,pending=0)
    else:
        branch='requested_raw_state_differs';expected=None
    if expected is not None and after!=expected:
        raise ValueError('Native +160 state disagrees with its observed non-Player branch')
    label,reference=_selected_source(attempt)
    attempt.candidate_diagnostics=dict(source_sha256=reference[1],before=before,after=after,
        branch_inferred_from_native_prestate=branch,non_player_branch_state_checked=expected is not None,
        transitive_player_aux_effects_qualified=False,public_session_admitted=False,
        native_return=None,void_return_ignored=True,state_modified_by_host=False)
    attempt.owner.emit(label+'_post160_transition_returned',before=attempt.transition_before,after=attempt.transition_after,
                      native_return=None,return_semantics='void-like; ignored',state_modified_by_host=False,
                      branch_inferred_from_native_prestate=branch,
                      transitive_player_effects_qualified=False,public_session_admitted=False)


def finish(attempt):
    from .xp1_load_capability import finish_cache_source_scope
    check_active(attempt)
    finish_cache_source_scope(attempt.facade)
    attempt._candidate_cache_lease.finish_post160(attempt)


def poison(attempt):
    from .xp1_load_capability import finish_cache_source_scope
    try:finish_cache_source_scope(attempt.facade)
    finally:
        lease=getattr(attempt,'_candidate_cache_lease',None)
        if lease is not None:lease.poison()

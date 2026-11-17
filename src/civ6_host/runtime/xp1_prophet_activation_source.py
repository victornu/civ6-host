"""Installed XP1 prophet-unit source admission, separate from native acceptance.

The action is UNITOPERATION_FOUND_RELIGION. Named religion selection remains a
different player operation. This profile installs no callbacks and invents no
gameplay result, empty Core subscriber list, or fallback service.
"""
from hashlib import sha256
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .execution_images import _PROFILE, _XP1_PROFILE
from . import xp2_religious_chain_source as xp2
from .xp1_saved_load import REFERENCE
from . import xp1_religion_observation_source as snapshot

SOURCE = ('work/x1trade/prophet-activation-stage/3d30226739b1ca1065abc0d4704b740e18863d17d7dda68896fe537a159d744b.json',
          '3d30226739b1ca1065abc0d4704b740e18863d17d7dda68896fe537a159d744b')
AVAILABILITY_SOURCE = ('work/x1trade/xp2-prophet-availability-static.json',
                       '35463d303388bff8ba9c7196372937212983d159bbd6de14dff64b30577d3ea0')
OPERATION_HASH = 0xc72fe8fb


def source_for(image):
    if image is _PROFILE:
        return xp2.SOURCE
    if image is _XP1_PROFILE:
        return SOURCE
    raise ValueError('Unqualified saved religion execution image')


def source_hash(core_sha256):
    verify_source(core_sha256)
    return (xp2.SOURCE if core_sha256 == XP2_CORE_SHA256 else SOURCE)[1]


def supports(reference,image):
    return (image is _XP1_PROFILE and reference == REFERENCE) or xp2.supports(reference,image)


def core_for(prefix):
    return XP2_CORE_SHA256 if is_xp2(prefix) else XP1_CORE_SHA256


def is_xp2(prefix):
    return getattr(prefix.backend.core,'_civ6_host_execution_image',None) is _PROFILE


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        return xp2.verify_source()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Prophet activation requires the selected Rise and Fall ABI')
    proof = _source(SOURCE)
    op,route = proof['operation'],proof['routing']
    if (proof['schema'] != 'civ6-host.xp1-prophet-activation-source.static.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or proof['image']['reference_abi_sha256'] != XP1_CORE_SHA256
            or op['type'] != 'UNITOPERATION_FOUND_RELIGION'
            or op['hash_u32'] != OPERATION_HASH or op['signed_hash'] != -953161477
            or op['ACTIVATE_GREAT_PERSON_substitution'] is not False
            or op['distinct_from_PlayerOperations_FOUND_RELIGION'] is not True
            or route['UI_CanStartOperation'] != '0x5dbe80'
            or route['UI_RequestOperation'] != '0x5dec40'
            or route['apply'] != '0x5862e0'
            or proof['native_execution'] is not False
            or proof['native_coverage_complete'] is not False):
        raise ValueError('Installed prophet source identity differs')
    targets=proof['callable_vtables']['prophet_operation']['target_rvas']
    if targets[2] != '0x585e30' or targets[8] != '0x5862e0' or targets[14:16] != ('0x36100','0x360f0'):
        raise ValueError('Prophet legality, normalization or effect slot differs')
    for row in proof['ui']:
        if sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Installed official prophet UI or definition source differs')
    snapshot.verify_source(core_sha256)
    return proof


def actions_qualified():
    """Known source/ABI boundary only; this is not an XP1 execution receipt."""
    proof=verify_source()
    qualification=proof['source_qualification']
    if (not all(qualification[k] is True for k in (
            'numeric_request_route_identified','normalizer_and_selected_applicator_complete',
            'shared_UI_request_and_getter_spans_match_installed_image',
            'known_host_boundaries_reuse_existing_profiles'))
            or qualification['native_acceptance_claimed'] is not False):
        return False
    for row in proof['references']:
        _source((row['path'],row['sha256']))
    from . import a0_family_source, foundation_event_profile, found_unit_event_profiles
    from . import faith_event_profile, script_event_source, xp1_saved_load_logger
    from . import unit_operation_ui_profile, xp1_unit_orders_profile
    unit_operation_ui_profile.source()
    xp1_unit_orders_profile.verify_source()
    script_event_source.source()
    xp1_saved_load_logger._checked_source(XP1_CORE_SHA256)
    found_unit_event_profiles.source()
    faith_event_profile.verify_source()
    family=a0_family_source.family_profile()
    foundation=foundation_event_profile.event_profile(execution_image=_XP1_PROFILE)
    for row in proof['external_events']:
        selected={'a0_family_source':family,'foundation_event_profile':foundation}.get(row['owner'])
        if selected is not None and row['record'] not in selected.record_types_by_kind.get(int(row['kind'],16),()):
            raise ValueError('Shared prophet event receiver differs')
    return True


def require_actions(image=None):
    if image is not None and image is not _XP1_PROFILE and image is not _PROFILE:
        raise ValueError('Unqualified saved religion execution image')
    if image is _PROFILE:
        xp2.require_actions('prophet')
        return
    if not actions_qualified():
        raise ValueError('Prophet action source dependencies are not qualified')


def source_dependencies(image, *, reference=None):
    if image is _PROFILE:
        from .paths import resource_root
        from .resource_resolution import resolve_path
        pins = xp2.source_dependencies(image,reference=reference,family='prophet')
        verify_availability_source()
        path = str(resolve_path(resource_root()/AVAILABILITY_SOURCE[0]).resolve(strict=True))
        if pins.setdefault(path,AVAILABILITY_SOURCE[1]) != AVAILABILITY_SOURCE[1]:
            raise ValueError('Gathering Storm prophet availability source dependency conflict')
        return pins
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    if image is not _XP1_PROFILE:
        raise ValueError('Prophet activation requires the exact installed Rise and Fall image')
    proof=verify_source()
    pins=snapshot.source_dependencies(image)
    for row in [dict(path=SOURCE[0],sha256=SOURCE[1]),*proof['references'],*proof['ui']]:
        path=str(resolve_path(resource_root()/row['path']).resolve())
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Prophet source dependency conflict')
    pins[str(Path(image.path).resolve())]=image.image_sha256
    verify_pinned_files(pins)
    return pins


def verify_availability_source():
    proof = _source(AVAILABILITY_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-prophet-availability-diagnosis.static.v1'
            or proof['image']['sha256'] != _PROFILE.image_sha256
            or proof['source']['activation']['sha256'] != xp2.SOURCE[1]
            or proof['native_executed'] is not False or proof['process_memory_read'] is not False
            or proof['queries']['enums'] != {'OperationResultsTypes.NO_TARGETS':2,
                'UnitOperationResults.FAILURE_REASONS':-2028665063}
            or proof['bodies']['UI_CanStartOperation']['entry_rva'] != '0x6c0390'
            or proof['bodies']['prophet_can_start']['entry_rva'] != '0x66a270'):
        raise ValueError('Gathering Storm prophet availability source differs')
    return proof


def bind_availability(prefix):
    # The catalogue already guards the retained XP2 cache, script and queue
    # owners. This overload additionally needs that owner's exact AUX+B0 map.
    from .script_map_service import MapService
    from .xp1_religious_unit_operations_source import _verify_spans
    if not is_xp2(prefix):
        raise ValueError('Prophet availability requires the exact Gathering Storm image')
    maps = getattr(prefix,'maps',None)
    core = prefix.backend.core
    if (type(maps) is not MapService or maps.closed or maps.host is not prefix.host
            or maps.runtime is not prefix.runtime or prefix.host._map_service_owner is not maps
            or maps.adapter.core is not core or maps.adapter.core_sha256 != XP2_CORE_SHA256
            or maps.adapter.transport_version != 2 or maps.adapter._installed is not True
            or maps.adapter._closed or len(maps.bindings) != 2
            or maps.bindings[1][0] != 0xb0
            or prefix.host.aux_vtable[0xb0//8] != maps.bindings[1][1]):
        raise ValueError('Prophet availability requires the owned XP2 optional-map callback')
    lifetime = (core,prefix.runtime,maps)
    previous = getattr(prefix,'_xp2_prophet_availability_lifetime',None)
    if previous is not None:
        if previous != lifetime:
            raise ValueError('Prophet availability source belongs to another saved lifetime')
        return
    proof = verify_availability_source()
    names = ('UI_CanStartOperation','resolve_current_unit_plot','append_failure_reason','prophet_can_start')
    spans = [row for name in names for row in proof['bodies'][name]['fragments']]
    enum_names = ('result_enum_registration','NO_TARGETS_literal','failure_reason_enum','failure_reason_literal')
    for name in enum_names:
        row = proof['spans'][name]
        spans.append(dict(rva=row['rva'],length=row['bytes'],sha256=row['sha256']))
    _verify_spans(core._handle,prefix.backend.runtime.read,spans)
    prefix._xp2_prophet_availability_lifetime = lifetime


def verify_live(base, read, *, image):
    """Verify complete new/reused code and relocated tables through an owned reader."""
    if image is not _XP1_PROFILE or type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Prophet source requires the installed image and exact reader')
    proof=verify_source()
    spans=[f for b in proof['code_spans'].values() for f in b['fragments']]
    spans.extend(proof['data_spans'].values())
    spans.extend(s for row in proof['reused_source_spans'].values() for s in row['instruction_spans'])
    for row in spans:
        address=base+int(row['rva'],16)
        raw=b''.join(read(address+n,min(4096,row['length']-n)) for n in range(0,row['length'],4096))
        if sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Live prophet source differs at '+row['rva'])
    for row in proof['callable_vtables'].values():
        expected=b''.join((base+int(r,16)).to_bytes(8,'little') for r in row['target_rvas'])
        if read(base+int(row['rva'],16),len(expected)) != expected:
            raise ValueError('Live prophet operation/subscriber slot differs')
    # Reuse existing binding-name, argument-type and archive-table checks too.
    from .unit_operation_ui_profile import verify_live as verify_request
    from .xp1_unit_orders_profile import verify_live as verify_getters
    verify_request(base,read,core_sha256=XP1_CORE_SHA256)
    verify_getters(base,read,core_sha256=XP1_CORE_SHA256)
    return dict(source_sha256=SOURCE[1],code_and_data_spans=len(spans),native_execution=False)


def bind_prefix(prefix, *, action=False):
    """Borrow the actual saved owners. Missing/foreign services refuse before Lua."""
    if is_xp2(prefix):
        return xp2.bind_prefix(prefix,family='prophet',action=action)
    snapshot.bind_prefix(prefix)
    from .script_event_service import ScriptEventService
    from .event_argument_service import EventArgumentService
    from .a0_family_service import A0FamilyService
    from .deferred_service import DeferredService
    from .xp1_action_transport import SavedActionTransport
    backend,core=prefix.backend,prefix.backend.core
    events=getattr(prefix,'events',None)
    arguments=getattr(prefix,'event_arguments',None)
    consumer=getattr(arguments,'consumer',None)
    if (type(events) is not ScriptEventService or events.host is not prefix.host
            or events.runtime is not prefix.runtime
            or type(arguments) is not EventArgumentService
            or type(consumer) is not A0FamilyService or consumer.arguments is not arguments
            or arguments.host is not prefix.host or arguments.deferred.core is not core
            or getattr(arguments.reader, 'core', None) is not core
            or type(prefix.deferred_events) is not DeferredService
            or consumer.deferred is not prefix.deferred_events):
        raise ValueError('Prophet activation has an unknown script or notification service owner')
    events._check()
    arguments._check()
    consumer._check()
    if action:
        require_actions()
        if (type(prefix.actions) is not SavedActionTransport or prefix.actions.services is not prefix
                or prefix.actions.backend is not backend or consumer._foundation_backend is not backend
                or consumer.foundation_event_profile is None or consumer.found_unit_event_profile is None
                or consumer.placement_event_profile is None
                or getattr(backend,'_xp1_load_logger_activation',{}).get('source_sha256') !=
                   '16d3d479d2280784ba5063bf4f29308d6b2e8ab9280da6d5de736199e83c8af7'):
            raise ValueError('Prophet action requires existing transport, unit, faith and logger owners')
        prefix.actions.require_transition()
        for row in verify_source()['external_events']:
            if not consumer.handles_kind(int(row['kind'],16)):
                raise ValueError('Prophet action has an unqualified event service: '+row['kind'])
    lifetime=(core,prefix,prefix.runtime)
    if getattr(prefix,'_xp1_prophet_source_lifetime',None) != lifetime:
        verify_live(core._handle,backend.runtime.read,image=getattr(core,'_civ6_host_execution_image',None))
        prefix._xp1_prophet_source_lifetime=lifetime

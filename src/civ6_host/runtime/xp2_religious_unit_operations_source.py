"""Gathering Storm source selection for the shared religious UnitOperations."""

from pathlib import Path

from . import xp2_bbg_inputs, xp2_bundle_inputs
from .a0_family_source import family_profile, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path
from .source_verification import file_sha256
from .source_build_identity import CURRENT_STRINGS_HOST_REFERENCE, CURRENT_UNSIGNED_LOG_HOST_REFERENCE


SOURCE = ('work/x1trade/xp2-religious-unit-operations-source/38fa412d55e4795b4845967ef2a841f0262ba32dbc0d821932f7a04540c26a9f.json',
          '38fa412d55e4795b4845967ef2a841f0262ba32dbc0d821932f7a04540c26a9f')
ORDINAL_SOURCE = ('work/x1trade/xp2-religious-unit-operations-runtime-stage/e605b49ddf79b0b6309e802b1f322683a5ec99b701c20d65739cfa3970e42d24.json',
                  'e605b49ddf79b0b6309e802b1f322683a5ec99b701c20d65739cfa3970e42d24')
_CAPTURE_FAMILIES = {
    xp2_bundle_inputs.REFERENCE: ('xp2-stock',CURRENT_UNSIGNED_LOG_HOST_REFERENCE),
    xp2_bbg_inputs.REFERENCE: ('xp2-bbg751',CURRENT_STRINGS_HOST_REFERENCE),
}
_OPERATIONS = {
    'spread_religion': ('0x673740','0xa2ba60','0x673100','0x6737c0'),
    'evangelize_belief': ('0x668e20','0xa29410','0x668ca0','0x668ea0'),
    'launch_inquisition': ('0x66ba20','0xa29f98','0x66b8a0','0x66baa0'),
    'remove_heresy': ('0x6718a0','0xa2ae48','0x6714b0','0x6737c0'),
}
_GETTERS = {
    'Unit.GetSpreadCharges':'0x6bd630',
    'Unit.GetReligionType':'0x6bd540',
    'Player.GetReligion':'0x6a9ee0',
    'PlayerReligion.HasLaunchedInquisition':'0x6b37d0',
    'PlayerReligion.GetNumBeliefsEarned':'0x6b3690',
}
_SPECIAL_EVENTS = {0xc1300ee7:'foundation',0xb3495127:'placement',0x45b517d6:'combat'}


def supports(reference,image):
    return image is _PROFILE and type(reference) is tuple and reference in tuple(_CAPTURE_FAMILIES)


def _selection(reference):
    if not supports(reference,_PROFILE):
        raise ValueError('Unqualified Gathering Storm religious operation capture')
    return _CAPTURE_FAMILIES[reference]


def verify_source():
    from .xp1_religious_unit_operations_source import OPERATIONS, SOURCE as XP1_SOURCE
    proof = _source(SOURCE)
    image = proof['image']
    if (proof['schema'] != 'civ6-host.xp2-religious-unit-operations.source-mapping.v1'
            or (image['profile_id'],image['sha256'],image['reference_abi_sha256'],image['bytes']) !=
                (_PROFILE.id,_PROFILE.image_sha256,XP2_CORE_SHA256,_PROFILE.image_size_bytes)
            or proof['parent']['sha256'] != XP1_SOURCE[1]
            or any(proof[key] is not False for key in ('native_execution','process_memory_read',
                                                       'product_modified','bbg_native_compatibility_claimed'))
            or set(proof['operations']) != set(OPERATIONS)
            or set(proof['callable_vtables']) != set(OPERATIONS)
            or {key:row['callback_rva'] for key,row in proof['getter_bindings'].items()} != _GETTERS
            or not all(row['reference_bytes_match_current'] is True for row in proof['reused_transport'])):
        raise ValueError('Installed Gathering Storm religious operation source differs')
    for kind,expected in _OPERATIONS.items():
        row,table = proof['operations'][kind],proof['callable_vtables'][kind]
        if ((row['type'],row['hash_u32']) != OPERATIONS[kind][:2]
                or tuple(row[key] for key in ('registration','vtable','legality','apply')) != expected
                or row['request_parameters'] != () or row['vtable'] != table['rva']
                or table['target_rvas'][1:3] != ('0x6832d0',row['legality'])
                or table['target_rvas'][8] != row['apply']
                or table['target_rvas'][14:16] != ('0x3ef70','0x13230')):
            raise ValueError('Installed Gathering Storm religious operation dispatch differs')
    return proof


def _ordinal_source(proof):
    ordinal = _source(ORDINAL_SOURCE)
    if (ordinal['schema'] != 'civ6-host.xp2-religious-unit-operation-ordinal.static.v1'
            or ordinal['source']['sha256'] != SOURCE[1] or ordinal['image'] != proof['image']
            or ordinal['native_execution'] is not False
            or set(ordinal['databases']) != {name for name, _ in _CAPTURE_FAMILIES.values()}
            or set(ordinal['hosts']) != set(ordinal['databases'])):
        raise ValueError('Gathering Storm religious operation ordinal proof differs')
    for capture in proof['databases']:
        family = capture['family']
        rows = ordinal['databases'][family]
        if (rows['database']['sha256'] != capture['database']['sha256']
                or set(rows['definitions']) != set(_OPERATIONS)
                or len({row['ordinal'] for row in rows['definitions'].values()}) != len(_OPERATIONS)):
            raise ValueError('Gathering Storm religious ordinal database differs')
        for kind,row in rows['definitions'].items():
            operation = proof['operations'][kind]
            captured = capture['rows'][kind]
            if (row['type'] != operation['type'] or row['hash_u32'] != operation['hash_u32']
                    or type(row['ordinal']) is not int or not 0 <= row['ordinal'] < rows['rows'] <= 2048
                    or captured['definition']['InterfaceMode'] is not None
                    or captured['definition']['VisibleInUI'] != 1
                    or captured['type_definition']['Hash'] & 0xffffffff != row['hash_u32']):
                raise ValueError('Gathering Storm religious ordinal/type identity differs')
    return ordinal


def expected_ordinal(reference,kind):
    family,_ = _selection(reference)
    return _ordinal_source(verify_source())['databases'][family]['definitions'][kind]['ordinal']


def require_actions():
    from . import combat_event_profile, faith_event_profile, foundation_event_profile
    from .native.native_event_b6b48d9c import EVENT_KIND, verify_source_evidence
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .xp2_placement_event_source import RECORDS
    proof = verify_source()
    _ordinal_source(proof)
    faith_event_profile.verify_source(core_sha256=XP2_CORE_SHA256)
    verify_source_evidence()
    profiles = {
        'shared':family_profile().record_types_by_kind,
        'foundation':foundation_event_profile.event_profile(
            core_sha256=XP2_CORE_SHA256,execution_image=_PROFILE).record_types_by_kind,
        'combat':combat_event_profile.event_profile(
            XP2_CORE_SHA256,execution_image=_PROFILE).record_types_by_kind,
        'placement':{kind:tuple(record for record,_ in rows) for kind,rows in RECORDS.items()},
    }
    for row in proof['external_boundaries']['events']:
        kind = int(row['kind'],16)
        if kind == EVENT_KIND and kind not in EXE_EVENT_CALLBACKS and 'record_type' not in row:
            continue
        if row['record_type'] not in profiles[_SPECIAL_EVENTS.get(kind,'shared')].get(kind,()):
            raise ValueError('Unqualified Gathering Storm religious notification: '+row['kind'])
    return proof


def source_dependencies(reference):
    family,expected_host = _selection(reference)
    proof = require_actions()
    ordinal = _ordinal_source(proof)
    compiled = ordinal['hosts'][family]
    if (compiled['executable']['path'],compiled['executable']['sha256']) != expected_host:
        raise ValueError('Gathering Storm religious operation GameInfo owner differs')
    selected = next(r['database'] for r in proof['databases'] if r['family']==family)
    from .native.native_event_b6b48d9c import PINNED_EVIDENCE_SHA256 as camera
    from .native.native_absent_scalar_a0 import _EVIDENCE_SHA256 as absent
    refs = [
        *(dict(path=p,sha256=h) for p,h in (SOURCE,ORDINAL_SOURCE,reference)),
        proof['image'],proof['parent'],proof['record67_source'],proof['record67_native_scope'],
        selected,proof['ui']['stock_source'],*proof['ui']['files'][:4],
        *compiled.values(),*(r['source'] for r in proof['reused_transport']),
        *proof['external_boundaries']['reused_profiles'],
        dict(path=f'evidence/native-event-b6b48d9c/{camera}.json',sha256=camera),
        dict(path=f'evidence/native-absent-scalar-a0/{absent}.json',sha256=absent),
    ]
    if family == 'xp2-bbg751':
        refs.extend((*proof['ui']['files'][4:],*proof['bbg_selected_sources']))
    pins = {}
    for row in refs:
        path = str(resolve_path(resource_root()/row['path']).resolve(strict=True))
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Gathering Storm religious operation source dependency conflict')
    verify_pinned_files(pins)
    return pins


def verify_live(base,read):
    from .xp1_religious_unit_operations_source import _verify_spans
    from .xp2_action_transport_source import verify_live as verify_transport
    proof = verify_source()
    ordinal = _ordinal_source(proof)
    spans = [span for body in proof['code_spans'].values() for span in body['fragments']]
    spans.extend(span for row in proof['reused_transport'] for span in row['fragments'])
    spans.extend(row[key] for row in proof['getter_bindings'].values() for key in ('registration','literal'))
    spans.extend(ordinal['spans'])
    _verify_spans(base,read,spans)
    for row in proof['callable_vtables'].values():
        pointers = b''.join((base+int(target,16)).to_bytes(8,'little') for target in row['target_rvas'])
        if read(base+int(row['rva'],16),len(pointers)) != pointers:
            raise ValueError('Live Gathering Storm religious operation handler table differs')
    manager = ordinal['manager_vtable']
    address = base+int(manager['rva'],16)
    for slot,target in manager['slots'].items():
        if read(address+int(slot,16),8) != (base+int(target,16)).to_bytes(8,'little'):
            raise ValueError('Live Gathering Storm religious operation manager table differs')
    verify_transport(base,read,family='unit')
    return dict(source_sha256=SOURCE[1],complete_spans=len(spans),native_execution=False)


def bind_prefix(prefix,*,action=False):
    from .a0_family_service import A0FamilyService
    from .core_script_services import check_bound
    from .deferred_service import DeferredService
    from .event_argument_service import EventArgumentService
    from .native.native_event_b6b48d9c import EVENT_KIND as camera_notice
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .native.native_script_runtime import NativeScriptRuntime
    from .profile_script_binding import _current_executable
    from .saved_load_services import SavedLoadServices
    from .script_event_service import ScriptEventService
    from .xp1_action_transport import SavedActionTransport
    from .xp2_bbg_nested_events import BBGNestedScriptRuntime

    if type(prefix) is not SavedLoadServices:
        raise ValueError('Religious operations require the actual Gathering Storm saved service owner')
    backend = prefix.backend
    backend.check_thread()
    core,runtime = backend.core,prefix.runtime
    reference = backend.captured_bundle.reference
    family,build = _selection(reference)
    runtime_type = BBGNestedScriptRuntime if family == 'xp2-bbg751' else NativeScriptRuntime
    if (type(runtime) is not runtime_type or runtime.service_owner is not prefix.host
            or prefix.closed or prefix.quarantined or prefix.host is not backend.host
            or prefix.host._saved_load_services is not prefix or backend.prefix is not prefix
            or prefix.core is not core or prefix.context != backend.context
            or prefix.core_sha256 != XP2_CORE_SHA256 or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or getattr(core,'_civ6_host_execution_image',None) is not _PROFILE):
        raise ValueError('Religious operations require the exact Gathering Storm captured Lua owner')
    prefix.check()
    runtime.registry.validate(prefix.ui_child)
    check_bound(runtime,prefix.context,core)

    events,args,deferred = prefix.events,prefix.event_arguments,prefix.deferred_events
    consumer = args.consumer if type(args) is EventArgumentService else None
    transport = prefix.actions
    if (type(events) is not ScriptEventService or events.host is not prefix.host
            or events.runtime is not runtime or type(consumer) is not A0FamilyService
            or consumer.arguments is not args or args.host is not prefix.host
            or getattr(args.reader,'core',None) is not core or type(deferred) is not DeferredService
            or args.deferred is not deferred or consumer.deferred is not deferred
            or deferred.core is not core or deferred.context != prefix.context
            or deferred.cache_core_sha256 != XP2_CORE_SHA256
            or type(transport) is not SavedActionTransport or transport.services is not prefix
            or transport.backend is not backend or transport.transport_abi.core_sha256 != XP2_CORE_SHA256):
        raise ValueError('Gathering Storm religious operations lost their script, transport or queue owner')
    events._check()
    args._check()
    consumer._check()
    transport.check()
    if action:
        if consumer._foundation_backend is not backend:
            raise ValueError('Gathering Storm religious operations need this continuation notification owner')
        transport.require_transition()
        for row in verify_source()['external_boundaries']['events']:
            kind = int(row['kind'],16)
            if kind == camera_notice and kind not in EXE_EVENT_CALLBACKS:
                continue
            if (not consumer.handles_kind(kind) or not consumer.handles_record(row['record_type'])):
                raise ValueError('Unqualified Gathering Storm religious notification owner: '+row['kind'])

    lifetime = (core,core._handle,prefix,runtime,reference)
    prior = getattr(prefix,'_xp2_religious_unit_operations_lifetime',None)
    if prior is None:
        if file_sha256(_current_executable()) != build[1]:
            raise ValueError('Gathering Storm religious operations require the exact compiled GameInfo host')
        verify_live(core._handle,backend.runtime.read)
        prefix._xp2_religious_unit_operations_lifetime = lifetime
    elif prior != lifetime:
        raise ValueError('Gathering Storm religious operation source belongs to another saved lifetime')


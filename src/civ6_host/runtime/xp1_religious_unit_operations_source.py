"""Installed expansion source and ownership checks for four religious UnitOperations."""

from hashlib import sha256
from pathlib import Path

from . import xp1_prophet_activation_source as shared
from . import xp2_religious_unit_operations_source as xp2
from .a0_family_source import family_profile, verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _PROFILE, _XP1_PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1trade/religious-unit-operations-source/9b381c14608115e2b4d0748c831589687ae2f96dd5f11c27b34e010663c62f81.json',
          '9b381c14608115e2b4d0748c831589687ae2f96dd5f11c27b34e010663c62f81')
XP2_SOURCE = xp2.SOURCE
INQUISITION_SOURCE = ('work/x1trade/religious-unit-operations-api-stage/getter-source/b133e6d71b235ee4adb09fa7f230c471b44128e480b41b79550f06c52b71d9f4.json',
                      'b133e6d71b235ee4adb09fa7f230c471b44128e480b41b79550f06c52b71d9f4')
OPERATIONS = {
    'spread_religion': ('UNITOPERATION_SPREAD_RELIGION', 1592408602, '0x58ec70', '0x58f330'),
    'evangelize_belief': ('UNITOPERATION_EVANGELIZE_BELIEF', 2762349293, '0x584810', '0x584a10'),
    'launch_inquisition': ('UNITOPERATION_LAUNCH_INQUISITION', 3166818983, '0x5873b0', '0x5875b0'),
    'remove_heresy': ('UNITOPERATION_REMOVE_HERESY', 3796842921, '0x58cf20', '0x58f330'),
}
_GETTERS = {'GetSpreadCharges': ('0x5d90a0', '0x13c'), 'GetReligionType': ('0x5d8fb0', '0x14c')}
ARCHIVE_KIND = 0x8c0f3f36


def supports(reference, image):
    return (reference == REFERENCE and image is _XP1_PROFILE) or xp2.supports(reference,image)


def source_for(image):
    if image is _XP1_PROFILE:
        return SOURCE
    if image is _PROFILE:
        return XP2_SOURCE
    raise ValueError('Religious unit operations require an exact installed expansion image')


def verify_source():
    proof = _source(SOURCE)
    image = proof['image']
    qualification = proof['source_qualification']
    if (proof['schema'] != 'civ6-host.xp1-religious-unit-operations-source.static.v1'
            or (image['sha256'], image['reference_abi_sha256']) != (_XP1_PROFILE.image_sha256, XP1_CORE_SHA256)
            or proof['native_execution'] is not False
            or proof['native_coverage_complete'] is not False
            or not all(qualification[key] is True for key in ('all_selected_bodies_complete',
                'reused_instruction_bytes_match_installed_image', 'direct_operation_ABI_closed'))
            or qualification['native_acceptance_claimed'] is not False
            or set(proof['operations']) != set(OPERATIONS)
            or set(proof['callable_vtables']) != set(OPERATIONS)):
        raise ValueError('Installed religious unit operation source differs')
    for kind, expected in OPERATIONS.items():
        row, table = proof['operations'][kind], proof['callable_vtables'][kind]
        actual = (row['type'],row['hash_u32'],row['legality'],row['apply'])
        if (actual != expected or row['request_parameters'] != ()
                or row['definition']['VisibleInUI'] != 1 or row['definition']['InterfaceMode'] is not None
                or row['vtable'] != table['rva'] or row['event_selector'] == row['hash_u32']
                or table['target_rvas'][1:3] != ('0x59ed00', row['legality'])
                or table['target_rvas'][8] != row['apply']
                or table['target_rvas'][14:16] != ('0x36100','0x360f0')):
            raise ValueError('Installed religious unit operation dispatch differs')
    getters = proof['public_reader']['getters']
    if {key:(row['callback'],row['cache_offset']) for key,row in getters.items()} != _GETTERS:
        raise ValueError('Installed religious unit getter binding differs')
    return proof


def _inquisition_source():
    proof = _source(INQUISITION_SOURCE)
    binding = proof['binding']
    if (proof['schema'] != 'civ6-host.xp1-own-inquisition-getter-source.static.v1'
            or proof['parent']['sha256'] != SOURCE[1]
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or (binding['namespace'],binding['name'],binding['callback_rva'],
                binding['typed_receiver_rva'],binding['cache_getter_rva']) !=
               ('PlayerReligion','HasLaunchedInquisition','0x5cf250','0x5cea80','0x9c4e0')
            or proof['contract']['public_field'] != 'inquisition_started'
            or proof['contract']['domain'] != 'bool'
            or proof['qualification']['source_ABI_complete'] is not True
            or proof['qualification']['native_execution'] is not False):
        raise ValueError('Installed inquisition Boolean binding differs')
    return proof


def require_actions(image=None):
    if image is _PROFILE:
        return xp2.require_actions()
    if image is not None and image is not _XP1_PROFILE:
        raise ValueError('Religious unit operations require an exact installed expansion image')
    proof = verify_source()
    _inquisition_source()
    shared.require_actions()
    from . import faith_event_profile, xp1_world_text_profile
    from .native.native_event_b6b48d9c import verify_source_evidence as camera_notice_source
    faith_event_profile.verify_source()
    xp1_world_text_profile.verify_source()
    camera_notice_source()
    family = family_profile()
    for row in proof['external_events']:
        if (row['owner'].startswith('A0FamilyService') and row['record_type'] not in
                family.record_types_by_kind.get(int(row['kind'],16), ())):
            raise ValueError('Religious unit operation has an unknown shared notification')
    return proof


def source_dependencies(image, *, reference=None):
    if image is _PROFILE:
        return xp2.source_dependencies(reference)
    if image is not _XP1_PROFILE or reference not in (None, REFERENCE):
        raise ValueError('Religious unit operations require the installed Rise and Fall image')
    proof = require_actions()
    pins = shared.source_dependencies(image)
    getter = _inquisition_source()
    from .native.native_event_b6b48d9c import PINNED_EVIDENCE_SHA256 as camera_source
    from .native.native_absent_scalar_a0 import _EVIDENCE_SHA256 as absent_resolver_source
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]),
            dict(path=INQUISITION_SOURCE[0],sha256=INQUISITION_SOURCE[1]),getter['reuse'],
            dict(path=f'evidence/native-event-b6b48d9c/{camera_source}.json',sha256=camera_source),
            dict(path=f'evidence/native-absent-scalar-a0/{absent_resolver_source}.json',
                 sha256=absent_resolver_source),
            proof['image'], proof['database'],
            *proof['references'], *proof['ui'], *(r['source'] for r in proof['reused_source_comparisons'])]
    for row in refs:
        path = Path(row['path'])
        path = str(resolve_path(path if path.is_absolute() else resource_root()/path).resolve())
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Religious unit operation source dependency conflict')
    verify_pinned_files(pins)
    return pins


def _verify_spans(base, read, spans):
    for row in spans:
        addr = base + int(row['rva'],16)
        size = row['length']
        raw = b''.join(read(addr+offset,min(4096,size-offset)) for offset in range(0,size,4096))
        if len(raw) != size or sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Live religious unit operation source differs at '+row['rva'])


def verify_live(base, read, *, image):
    source_for(image)
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Religious unit operations require the exact installed image and reader')
    if image is _PROFILE:
        return xp2.verify_live(base,read)
    proof = verify_source()
    spans = [span for function in proof['code_spans'].values() for span in function['fragments']]
    getter = _inquisition_source()
    spans.extend(getter['binding'][key] for key in ('registration','literal'))
    spans.extend(span for function in getter['code_spans'].values() for span in function['fragments'])
    spans.extend(span for function in getter['reused_source_spans'] for span in function['fragments'])
    _verify_spans(base,read,spans)
    for row in proof['callable_vtables'].values():
        pointers = b''.join((base+int(target,16)).to_bytes(8,'little') for target in row['target_rvas'])
        if read(base+int(row['rva'],16),len(pointers)) != pointers:
            raise ValueError('Live religious unit operation vtable differs')
    return dict(source_sha256=SOURCE[1],complete_spans=len(spans),native_execution=False)


def bind_prefix(prefix, *, action=False):
    if getattr(getattr(prefix,'core',None),'_civ6_host_execution_image',None) is _PROFILE:
        return xp2.bind_prefix(prefix,action=action)
    # Same live XP1 cache, UI marshalling, native action transport and A0 owner.
    shared.bind_prefix(prefix,action=action)
    if action:
        from .native.native_event_b6b48d9c import EVENT_KIND as camera_notice
        from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
        proof = require_actions()
        consumer = prefix.event_arguments.consumer
        for row in proof['external_events']:
            kind = int(row['kind'],16)
            if not consumer.handles_kind(kind):
                # The stock camera notice returns through the original
                # registered no-callback boundary rather than a queued decoder.
                if kind != camera_notice or kind in EXE_EVENT_CALLBACKS:
                    raise ValueError('Unqualified religious unit notification service: '+row['kind'])
    lifetime = (prefix.core,prefix,prefix.runtime)
    if getattr(prefix,'_xp1_religious_unit_operations_lifetime',None) != lifetime:
        verify_live(prefix.core._handle,prefix.backend.runtime.read,
                    image=prefix.core._civ6_host_execution_image)
        prefix._xp1_religious_unit_operations_lifetime = lifetime

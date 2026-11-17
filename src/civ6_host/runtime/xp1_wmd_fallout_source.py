"""Rise and Fall fallout event on the qualified empty presentation receiver."""

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity
from .xp1_saved_load import REFERENCE
from . import xp2_wmd_fallout_source as shared


SOURCE = ('evidence/host-xp1-installed-wmd-fallout-changed-source.json',
          '04ff6d0c62652ffbfb76483d78c0d9448cd0fbc7e0c06592cc1edbaf7622a0fc')
POLICY, KINDS, CALLBACKS = shared.POLICY, shared.KINDS, shared.CALLBACKS
_SCRIPT_PROFILE = dict(active_count=0, selected_and_active_empty=True,
                       selected_path_count=0, source_files=0, source_records=0)


@lru_cache(maxsize=1)
def source():
    proof = _source(SOURCE)
    contract, route, capture = (proof[name] for name in ('contract', 'same_exe_route', 'capture'))
    official = capture['official_bundle']
    exe_source = route['reference']
    tags = {hex(shared.SELECTOR_KEY): 3, hex(shared.POSITION_KEY): 0,
            hex(shared.VALUE_KEY): 2, hex(shared.STATE_KEY): 2}
    if (proof['schema'] != 'civ6-host.xp1-installed-wmd-fallout-changed.static.v1'
            or proof['image'] != identity(_XP1_PROFILE)
            or (official['path'], official['sha256']) != REFERENCE
            or capture['gameplay_scripts'] != _SCRIPT_PROFILE
            or (exe_source['path'], exe_source['sha256']) != shared.SOURCE
            or proof['executable']['sha256'] != shared._EXE_SHA
            or route['all_captured_exe_fragments_byte_equal'] is not True
            or route['all_captured_exe_registration_spans_byte_equal'] is not True
            or (route['current_callback_rva'], route['writer_rva'], route['handler_rva'])
                != (0x159050, 0x138cf0, 0xda1f0)
            or (contract['kind'], contract['selector'], contract['field_tags']) != (shared.KIND, 0, tags)
            or (contract['position_bytes'], contract['position_flags'], contract['scalar_flags'])
                != (8, 0x21000001, 0)
            or contract['core_internal_dispatch_before_host'] is not True
            or (contract['EXE_record_type'], contract['EXE_record_size'],
                contract['EXE_record_metadata_flag']) != (200, 96, 0)
            or contract['policy'] != POLICY or contract['normalizer_return'] != 0
            or contract['administrative_only'] is not True
            or contract['public_visibility_qualified'] is not False
            or contract['requires_empty_EXE_receiver'] != dict(state_pointer_nonnull=True,
                subscriber_count=0, active_flag=False, dirty_flag=False, pre_hook=None,
                post_hook=None, producer_hook=None, normalizer_transform_present=False,
                writer_metadata_callback_present=False)):
        raise ValueError('Installed Rise and Fall fallout presentation source differs')
    return proof


def source_dependencies():
    proof = source()
    capture = proof['capture']
    exe = proof['executable']
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1],
            str(Path(_XP1_PROFILE.path).resolve()): _XP1_PROFILE.image_sha256,
            str(Path(exe['path']).resolve()): exe['sha256']}
    for ref in (capture['official_bundle'], capture['prepared_capture'],
                capture['selected_gameplay_source_manifest'], proof['same_exe_route']['reference']):
        pins[str(_path(ref['path']).resolve())] = ref['sha256']
    verify_pinned_files(pins)
    return pins


def _exact_owner(backend, core):
    return (backend.core is core and backend.load_abi.core_sha256 == XP1_CORE_SHA256
            and getattr(core, '_civ6_host_execution_image', None) is _XP1_PROFILE
            and backend.inputs.official_bundle == REFERENCE
            and backend.captured_bundle.reference == REFERENCE
            and backend.captured_bundle.content_profile['gameplay_scripts'] == _SCRIPT_PROFILE)


def bind_owner(backend, core, read):
    from .capture_admission import configured_reference

    backend.check_thread()
    if (not _exact_owner(backend, core) or backend.stage != 'prepared'
            or backend.poisoned or backend.destroyed
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('Fallout presentation requires the exact prepared Rise and Fall owner')
    proof = source()
    prepared = proof['capture']['prepared_capture']
    selected = configured_reference()
    if (selected is None or selected['sha256'] != prepared['sha256']
            or Path(selected['path']).resolve() != _path(prepared['path']).resolve()):
        raise ValueError('Rise and Fall fallout presentation capture differs')
    for label, span in proof['core'].items():
        raw = shared._read_exact(read, core._handle + span['rva'], span['bytes'])
        if sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Rise and Fall fallout producer differs: ' + label)
    slot = proof['core_blob_vtable_slot']
    target = shared._read_exact(read, core._handle + slot['rva'], slot['bytes'])
    if int.from_bytes(target, 'little') != core._handle + slot['target_rva']:
        raise ValueError('Live Rise and Fall fallout blob setter differs')
    backend._xp1_wmd_fallout_core = core
    return SOURCE[1]


def validate_empty_owner(owner):
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow

    if type(owner) is not A0FamilyService:
        raise ValueError('Fallout presentation requires the real A0 owner')
    owner._check()
    backend = require_borrow(owner).owner
    empty = shared._EMPTY_STATE
    if (not _exact_owner(backend, owner.deferred.core)
            or owner._foundation_backend is not backend or backend.host is not owner.arguments.host
            or owner.active_kind not in KINDS
            or owner.arguments.reader.core_sha256 != XP1_CORE_SHA256
            or owner.deferred.cache_core_sha256 != XP1_CORE_SHA256
            or getattr(backend, '_xp1_wmd_fallout_core', None) is not backend.core
            or owner.empty_receiver_state != empty or owner._receiver_profile != empty
            or any(type(owner.empty_receiver_state[k]) is not type(v) for k, v in empty.items())
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False):
        raise ValueError('Fallout presentation requires the guarded Rise and Fall empty receiver')
    return POLICY


def decode_fields(kind, fields, read):
    source()
    return shared._decode_fields(kind, fields, read)

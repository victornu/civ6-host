"""Current-image CivicsUnlocked source binding for the shared type-208 codec."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from types import MappingProxyType

from civ6_host.runtime.a0_family_source import A0FamilyProfile
from civ6_host.runtime.configuration_profiles import _source
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path

PROFILE_REF = (
    'work/trade-common-client/xp2-current-callback-corrections.json',
    'c1df4bd61b74045faed7b17f75a734c4aa451133c7bba82c7944d11184133cd6',
)
PROFILE_SHA256 = PROFILE_REF[1]
CURRENT_PROFILE_ID = 'xp2-gamecore-current-092abfbb'
CURRENT_CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
CURRENT_EXE_SHA256 = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
KIND, RECORD_TYPE, RECORD_SIZE = 0x0a981150, 208, 96
SELECTOR_KEY, PLAYER_KEY = 0xa1e5a149, 0xd6fcf3e4


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _require_image(execution_image):
    from civ6_host.runtime.execution_images import ExecutionImageProfile, select
    if type(execution_image) is not ExecutionImageProfile:
        raise ValueError('Current policy notification requires the exact registered XP2 image')
    try:
        registered = select(CURRENT_PROFILE_ID, core_path=execution_image.path)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError('Current policy notification image path is not registered') from exc
    if (registered is not execution_image
            or execution_image.image_sha256 != CURRENT_CORE_SHA256
            or execution_image.reference_core_sha256 != '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Current policy notification requires the exact registered XP2 image pair')


def source(execution_image):
    """Load the immutable source profile for one explicitly selected image."""
    _require_image(execution_image)
    proof = _source(PROFILE_REF)
    route = proof['routes']['civics_unlocked']
    if (proof.get('schema') != 'civ6-host.xp2-current-callback-corrections.static.v1'
            or proof.get('static_only') is not True
            or proof.get('native_effect_verified') is not False
            or proof.get('execution_profile') != {
                'id': CURRENT_PROFILE_ID,
                'core_sha256': CURRENT_CORE_SHA256,
                'executable_sha256': CURRENT_EXE_SHA256,
            }
            or route['kind'] != hex(KIND)
            or route['registered_callback']['rva'] != '0x142290'
            or route['callback_body']['rva'] != '0x14c850'
            or route['writer']['rva'] != '0x1399e0'
            or route['subscriber_name'] != 'GameCoreEvent::CivicsUnlocked'
            or route['subscriber_row_va'] != '0x1412c9fb0'
            or route['handler']['rva'] != '0xda550'
            or route['record_type'] != RECORD_TYPE or route['record_size'] != RECORD_SIZE
            or proof.get('core_producer', {}).get('dispatch_kind') != '0x0a981150'
            or proof.get('core_producer', {}).get('sha256') != '3de989d0bb3f8d4bb80512937945c530defaf3fcce5805881a7c8d52dfb632cb'
            or proof['policy_payload'] != dict(input_payload_consumed_by_exe_callback=False,
                sequence_offset=80, unused_copied_bytes=(84, 88), owned_empty_subscribers_only=True)):
        raise ValueError('Current policy-notification source profile differs')

    root = resolve_path(resource_root())
    for ref in proof.get('source_references', {}).values():
        relative = Path(ref['path'].replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Current policy source path escaped resources')
        path = resolve_path(root / relative)
        if _sha_file(path) != ref['sha256']:
            raise ValueError('Current policy source reference changed: ' + ref['path'])

    producer = proof['core_producer']
    raw = bytes.fromhex(producer['raw_hex'])
    if (len(raw) != 72 or hashlib.sha256(raw).hexdigest() != producer['sha256']
            or producer['path'] != str(execution_image.path)):
        raise ValueError('Current Core producer body/profile identity differs')
    return proof


def source_dependencies(execution_image):
    """Static source closure only; the EXE is not loaded by the host process."""
    proof = source(execution_image)
    root = resolve_path(resource_root())
    refs = [dict(path=PROFILE_REF[0], sha256=PROFILE_SHA256), *proof['source_references'].values()]
    return {
        str(resolve_path(root / Path(row['path'].replace('\\', '/'))).resolve()): row['sha256']
        for row in refs
    }


def _empty_state(owner):
    state = owner.empty_receiver_state
    expected = {
        'observer_registered': False,
        'state_pointer_nonnull': True,
        'pre_hook': None,
        'post_hook': None,
        'subscriber_count': 0,
        'state_flags': 0,
    }
    if (type(state) is not dict or set(state) != set(expected)
            or any(type(state[key]) is not type(value) for key, value in expected.items())
            or state != expected or type(owner.entity_listener_count) is not int
            or owner.entity_listener_count != 0):
        raise ValueError('Current CivicsUnlocked empty receiver state differs')
    return state


def receiver_row(execution_image):
    proof = source(execution_image)
    route = proof['routes']['civics_unlocked']
    return {
        'event_name': route['subscriber_name'],
        'handler_va': hex(0x140000000 + int(route['handler']['rva'], 16)),
        'handler_body_sha256': route['handler']['sha256'],
        'record_sizes': {RECORD_SIZE},
        'source_profile_sha256': PROFILE_SHA256,
        'execution_profile_id': CURRENT_PROFILE_ID,
    }


def validate_empty_record(record, *, execution_image, receiver_state):
    """Validate this source row only under the explicitly selected current image."""
    row = receiver_row(execution_image)
    view = memoryview(record).cast('B')
    if (len(view) != RECORD_SIZE or int.from_bytes(view[0:4], 'little') != RECORD_SIZE
            or int.from_bytes(view[4:8], 'little') != RECORD_TYPE):
        raise ValueError('Current policy notification record header differs')
    expected = {
        'observer_registered': False,
        'state_pointer_nonnull': True,
        'pre_hook': None,
        'post_hook': None,
        'subscriber_count': 0,
        'state_flags': 0,
    }
    if receiver_state != expected:
        raise ValueError('Current CivicsUnlocked row is not owned-empty')
    return {'record_type': RECORD_TYPE, 'record_size': RECORD_SIZE,
            'event_name': row['event_name'], 'handler_va': row['handler_va']}


def enable_current(owner, backend, execution_image):
    """Opt into the current static branch on one idle composed A0 owner."""
    proof = source(execution_image)
    owner._check()
    backend.check_thread()
    if (owner.policy_unlock_event_profile is not None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or owner._foundation_backend is not backend or backend.stage != 'prepared'
            or backend.prefix is not None
            or backend.load_abi.core_sha256 != execution_image.reference_core_sha256
            or getattr(backend.profile, 'execution_image', None) is not execution_image
            or getattr(backend.profile, 'core_sha256', None) != CURRENT_CORE_SHA256
            or getattr(backend.profile, 'source_core_sha256', None) != execution_image.reference_core_sha256
            or getattr(backend, '_xp1_commands_requested', False) is not True
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context != owner.deferred.context or owner.handles_kind(KIND)
            or owner.handles_record(RECORD_TYPE)
            or getattr(owner.deferred.core, '_civ6_host_execution_image', None) is not execution_image
            or owner.deferred.cache_core_sha256 != execution_image.reference_core_sha256
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.normalizer_transform_present is not False
            or owner.dynamic_event_registration_present is not False):
        raise ValueError('Current policy notification requires one idle current-image owner')

    raw = bytes.fromhex(proof['core_producer']['raw_hex'])
    if owner.read(backend.core._handle + int(proof['core_producer']['rva'], 16), len(raw)) != raw:
        raise ValueError('Live current Core policy producer differs from the pinned source')
    state = _empty_state(owner)
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_record(shape, execution_image=execution_image, receiver_state=state)
    profile = A0FamilyProfile(
        MappingProxyType({KIND: frozenset({RECORD_TYPE})}),
        MappingProxyType({RECORD_TYPE: RECORD_SIZE}), PROFILE_SHA256)
    owner.policy_unlock_event_profile = owner._policy_unlock_event_profile = profile
    owner._policy_unlock_current_image_id = CURRENT_PROFILE_ID
    return owner


def consume(owner, record, sequence):
    """Consume the current typed row without applying the historical receiver."""
    deferred = owner.deferred
    execution_image = getattr(deferred.core, '_civ6_host_execution_image', None)
    if (getattr(owner, '_policy_unlock_current_image_id', None) != CURRENT_PROFILE_ID
            or not deferred._draining_empty_receivers or not deferred.pending
            or deferred.pending[0] is not record or sequence != deferred.consumed_count + 1):
        raise ValueError('Current policy notification lacks its exact owned FIFO head')
    row = validate_empty_record(record, execution_image=execution_image, receiver_state=_empty_state(owner))
    from .unit_panel_gate import observe_consumed_record
    observe_consumed_record(deferred, record)
    deferred.pending.pop(0)
    deferred.consumed_count += 1
    deferred.consumed_bytes += len(record)
    deferred.consumed_digest.update(record)
    deferred.emit('native_deferred_empty_record_consumed', sequence=sequence, **row,
                  native_handler_has_no_gameplay_callback_in_this_profile=True,
                  native_profiling_reproduced=False, eligible_for_training=False)

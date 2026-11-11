"""Current-image policy notification bindings for the shared A0 FIFO."""
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
OBSOLETE_KIND, OBSOLETE_RECORD = 0xd127ff37, 207
OBSOLETE_SOURCE = ('evidence/host-xp2-stock-policy-obsolescence-source.json',
                   'c6ae75bd612abfcf717b1ce6a82af52867f489a2409a81f5a484e6d66212c09d')
STOCK_CAPTURE = ('work/official-capture/xp2-gs-lan-rows-20261102-04/manifest.json',
                 '28cc55ad4c2d56535db8c0a1351445125fd75800ab54eefd3b0b600b41717f1d')
_OBSOLETE_RECEIVER = 'GameCoreEvent::GovernmentPolicyObsoleted'
_OBSOLETE_HANDLER = '0x1400da490'


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
    pins = {
        str(resolve_path(root / Path(row['path'].replace('\\', '/'))).resolve()): row['sha256']
        for row in refs
    }
    pins.update(obsolescence_dependencies(execution_image))
    for module in ('a0_family_service.py', 'a0_policy_unlock.py', Path(__file__).name):
        path = Path(__file__).with_name(module).resolve()
        pins[str(path)] = _sha_file(path)
    return pins


def obsolescence_source(execution_image):
    _require_image(execution_image)
    proof = _source(OBSOLETE_SOURCE)
    capture = proof['official_bundle']
    if (proof['schema'] != 'civ6-host.xp2-stock-policy-obsolescence-source.v1'
            or proof['core']['sha256'] != execution_image.image_sha256
            or proof['exe']['sha256'] != CURRENT_EXE_SHA256
            or (capture['path'], capture['sha256']) != STOCK_CAPTURE
            or proof['contract'] != dict(core_kind=hex(OBSOLETE_KIND),
                exe_semantic_kind=f'0x{KIND:08x}', event_name=_OBSOLETE_RECEIVER,
                record_type=OBSOLETE_RECORD, record_size=RECORD_SIZE,
                handler_va=_OBSOLETE_HANDLER, selector=0, payload_offsets=(84, 88),
                core_slot_mutation_before_notification=True, receiver='owned_empty',
                gameplay_rule_reimplemented=False, native_execution_verified=False)):
        raise ValueError('Current stock policy obsolescence source differs')
    return proof


def obsolescence_dependencies(execution_image):
    proof = obsolescence_source(execution_image)
    root = resolve_path(resource_root())
    pins = {}
    refs = [dict(path=OBSOLETE_SOURCE[0], sha256=OBSOLETE_SOURCE[1]),
            *(proof[key] for key in ('exe', 'frontier', 'semantic_crosswalk', 'official_bundle',
                                     'script_selection', 'gameplay_script')),
            *proof['stock_ui']]
    for row in refs:
        path = resolve_path(root / Path(row['path'])).resolve()
        if _sha_file(path) != row['sha256']:
            raise ValueError('Current policy obsolescence dependency differs: ' + str(path))
        pins[str(path)] = row['sha256']
    return pins


def _stock_scope(backend):
    return getattr(getattr(backend, 'captured_bundle', None), 'reference', None) == STOCK_CAPTURE


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
    kinds = {KIND: frozenset({RECORD_TYPE})}
    sizes = {RECORD_TYPE: RECORD_SIZE}
    if _stock_scope(backend):
        obsolescence_dependencies(execution_image)
        for span in obsolescence_source(execution_image)['core_spans'].values():
            address = backend.core._handle + int(span['rva'], 16)
            body = owner.read(address, span['bytes'])
            if len(body) != span['bytes'] or hashlib.sha256(body).hexdigest() != span['sha256']:
                raise ValueError('Live current policy obsolescence span differs at ' + span['rva'])
        kinds[OBSOLETE_KIND] = frozenset({OBSOLETE_RECORD})
        sizes[OBSOLETE_RECORD] = RECORD_SIZE
    profile = A0FamilyProfile(
        MappingProxyType(kinds), MappingProxyType(sizes), PROFILE_SHA256)
    owner.policy_unlock_event_profile = owner._policy_unlock_event_profile = profile
    owner._policy_unlock_current_image_id = CURRENT_PROFILE_ID
    return owner


def _require_obsolescence(owner):
    profile = owner.policy_unlock_event_profile
    image = getattr(owner.deferred.core, '_civ6_host_execution_image', None)
    if (profile is None or profile is not owner._policy_unlock_event_profile
            or profile.source_sha256 != PROFILE_SHA256
            or profile.record_types_by_kind.get(OBSOLETE_KIND) != frozenset({OBSOLETE_RECORD})
            or getattr(owner, '_policy_unlock_current_image_id', None) != CURRENT_PROFILE_ID
            or getattr(image, 'image_sha256', None) != CURRENT_CORE_SHA256
            or not _stock_scope(owner._foundation_backend)
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.normalizer_transform_present is not False
            or owner.dynamic_event_registration_present is not False):
        raise ValueError('Unqualified current-image record-207 producer')
    _empty_state(owner)


def _obsolescence_row(record, sequence):
    if (len(record) != RECORD_SIZE
            or struct.unpack_from('<IIII', record) != (RECORD_SIZE, OBSOLETE_RECORD, sequence, 0)
            or struct.unpack_from('<I', record, 80) != (sequence,)):
        raise ValueError('Current policy obsolescence record differs')
    return dict(record_type=OBSOLETE_RECORD, record_size=RECORD_SIZE,
                event_name=_OBSOLETE_RECEIVER, handler_va=_OBSOLETE_HANDLER)


def validate_obsolescence_enqueue(owner, record):
    _require_obsolescence(owner)
    if owner.active_kind != OBSOLETE_KIND:
        raise ValueError('Current policy obsolescence producer lacks its exact key')
    _obsolescence_row(record, owner._sequence + 1)


def dispatch_obsolescence(owner, fields):
    from .native.native_two_value_event_family import encode_core_fields

    _require_obsolescence(owner)
    if type(fields) is not dict or set(fields) != {SELECTOR_KEY, PLAYER_KEY, 0xa1fbc372}:
        raise ValueError('Current policy obsolescence requires its exact three fields')
    if (len(owner.pending) >= owner.limit or type(owner._sequence) is not int
            or not 0 <= owner._sequence < 0x7fffffff):
        raise RuntimeError('Current policy obsolescence FIFO bound exceeded')
    record = encode_core_fields(OBSOLETE_KIND, owner._sequence + 1, fields,
        optional_callback_present=False, queue_metadata_service_present=False)
    before = (owner.host_notification_counter, owner.host_metadata_counter, owner._sequence, len(owner.pending))
    owner._enqueue(record)
    notifications, metadata, sequence, count = before
    if (owner.host_notification_counter, owner.host_metadata_counter, owner._sequence, len(owner.pending)) != (
            notifications, metadata, sequence + 1, count + 1):
        raise RuntimeError('Current policy obsolescence changed its counter or FIFO semantics')
    owner.emit('xp2_stock_policy_obsolescence_enqueued', dispatch_kind=hex(OBSOLETE_KIND),
        queue_type=hex(OBSOLETE_RECORD), sequence=owner._sequence, record_hex=record.hex(),
        source_proof_sha256=OBSOLETE_SOURCE[1], payload_exposed_to_learner=False,
        gameplay_effect_substituted=False, native_dispatch_return=0)
    return 0


def consume(owner, record, sequence):
    """Consume the current typed row without applying the historical receiver."""
    deferred = owner.deferred
    execution_image = getattr(deferred.core, '_civ6_host_execution_image', None)
    if (getattr(owner, '_policy_unlock_current_image_id', None) != CURRENT_PROFILE_ID
            or not deferred._draining_empty_receivers or not deferred.pending
            or deferred.pending[0] is not record or sequence != deferred.consumed_count + 1):
        raise ValueError('Current policy notification lacks its exact owned FIFO head')
    if int.from_bytes(record[4:8], 'little') == OBSOLETE_RECORD:
        _require_obsolescence(owner)
        row = _obsolescence_row(record, sequence)
    else:
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

"""Current GameCore player-restoration presentation record."""
import struct

from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .native.native_application_mirror import decode_scalar
from .native.native_player_event_domains import validate_sequence
from .native.native_unary_event_family import _METADATA
from . import xp2_capture_notification_source as registered


SOURCE = ('evidence/host-xp2-bbg-player-restored-source.json',
          '0fbb97bdc59c43f5ddf6f75602ee5c18bb85c011c1f491ec98ddabed5885aee6')
KIND, RECORD_TYPE, RECORD_SIZE = 0xad6c0a71, 19, 96
SELECTOR, PLAYER = 0xa1e5a149, 0xf06a2af2


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-player-restored-source.v1'
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['kind'] != KIND or proof['record']['type'] != RECORD_TYPE
            or proof['record']['size'] != RECORD_SIZE or proof['record']['metadata_flag'] != 6
            or proof['record']['payload_dwords'] != ('sequence', 'F06A2AF2', 'raw_event_data')
            or proof['record']['copied_payload_fully_initialized'] is not True):
        raise ValueError('Current player restoration source differs')
    return proof


def source_dependencies(*, execution_image):
    pins = registered.source_dependencies(execution_image)
    source()
    from .a0_family_source import _path
    pins[str(_path(SOURCE[0]).resolve())] = SOURCE[1]
    return pins


def verify_live(core, read):
    registered.verify_live(core, read, source())


def receiver_row():
    row = source()['record']
    return dict(event_name=row['event_name'], handler_va=hex(0x140000000 + row['handler_rva']),
                handler_body_sha256=row['handler_sha256'], record_sizes={RECORD_SIZE})


def encode_record(sequence, fields):
    validate_sequence(sequence)
    if (type(fields) is not dict or set(fields) != {SELECTOR, PLAYER}
            or any(type(value) is not bytes or len(value) != 24 for value in fields.values())):
        raise ValueError('Current player restoration fields differ')
    player = decode_scalar(fields[PLAYER], 2)
    event_data = decode_scalar(fields[SELECTOR], 3)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I', record, 72, 6)
    struct.pack_into('<III', record, 80, sequence, player, event_data)
    return bytes(record)


def dispatch(owner, fields):
    from .a0_foundation_events import require_borrow
    from .native.native_deferred_empty_profile import validate_empty_profile_record

    backend = require_borrow(owner).owner
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    _require_image(image)
    owner._require_no_f391_reentry()
    if (owner.active_kind != KIND or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.entity_listener_count != 0 or len(owner.pending) >= owner.limit):
        raise ValueError('Player restoration requires its owned source-qualified receiver')
    record = encode_record(owner._sequence + 1, fields)
    validate_empty_profile_record(record, execution_image=image, **owner.empty_receiver_state)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND),
               queue_type=hex(RECORD_TYPE), record_hex=record.hex(), source_proof_sha256=SOURCE[1],
               payload_exposed_to_learner=False, native_dispatch_return=0)
    return 0

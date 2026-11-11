"""Current XP2 player notification selected by the registered callback."""
import struct

from .a0_policy_unlock_current import _require_image
from .native.native_application_mirror import decode_scalar
from .native.native_player_event_domains import validate_sequence
from .native.native_unary_event_family import _METADATA
from . import xp2_capture_notification_source as registered

SOURCE = registered.SOURCE
KIND, RECORD_SIZE = 0xa0a8f479, 96
DESTROYED, REVIVED = 0x110, 0x111
RECORD_TYPES = frozenset((DESTROYED, REVIVED))
SELECTOR, AVAILABLE, PLAYER = 0xa1e5a149, 0x15808e44, 0xf06a2af2
_FIELD_TAGS = {SELECTOR: 3, AVAILABLE: 1, PLAYER: 2}


def source():
    return registered.route('player_availability', KIND,
                            {(record_type, RECORD_SIZE) for record_type in RECORD_TYPES})


def verify_live(core, read):
    registered.verify_live(core, read, source())


def encode_record(sequence, fields):
    validate_sequence(sequence)
    if (type(fields) is not dict or set(fields) != set(_FIELD_TAGS)
            or any(type(raw) is not bytes for raw in fields.values())):
        raise ValueError('XP2 player notification fields differ')
    scalars = {key: decode_scalar(fields[key], tag) for key, tag in _FIELD_TAGS.items()}
    if scalars[SELECTOR] != 0:
        raise ValueError('XP2 player notification selector differs')
    record_type = REVIVED if scalars[AVAILABLE] else DESTROYED
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, record_type, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<II', record, 80, sequence, scalars[PLAYER])
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
            or len(owner.pending) >= owner.limit):
        raise ValueError('XP2 player notification requires its owned receiver')
    record = encode_record(owner._sequence + 1, fields)
    validate_empty_profile_record(record, execution_image=image, **owner.empty_receiver_state)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND),
               queue_type=hex(struct.unpack_from('<I', record, 4)[0]), record_hex=record.hex(),
               source_proof_sha256=SOURCE[1], payload_exposed_to_learner=False,
               native_queries_executed=False, eligible_for_training=False, native_dispatch_return=0)
    return 0

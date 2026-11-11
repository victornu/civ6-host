"""Current XP2 city transfer notification for the owned A0 receiver."""
import struct
from .a0_policy_unlock_current import _require_image
from . import xp2_capture_notification_source as registered


SOURCE = registered.SOURCE
KIND, RECORD_TYPE, RECORD_SIZE = 0xe05ec908, 0x73, 112
SELECTOR, CITY, PRIOR_OWNER, TRANSFER = 0xa1e5a149, 0x23739f42, 0x5150e7c3, 0x2be74a24
_FIELD_TAGS = {SELECTOR: 3, CITY: 1024, PRIOR_OWNER: 2, TRANSFER: 2}


def source():
    return registered.route('city_transfer', KIND, {(RECORD_TYPE, RECORD_SIZE)})


def verify_live(core, read):
    registered.verify_live(core, read, source())


def receiver_row():
    return registered.receiver_row(RECORD_TYPE)


def encode_record(sequence, fields, read):
    from .native.native_event_15c35863 import decode_scalar
    from .native.native_host_events import copy_eight_byte_variant
    from .native.native_player_event_domains import validate_sequence
    from .native.native_unary_event_family import _METADATA

    validate_sequence(sequence)
    if (type(fields) is not dict or set(fields) != set(_FIELD_TAGS)
            or any(type(value) is not bytes or len(value) != 24 for value in fields.values())
            or decode_scalar(fields[SELECTOR], _FIELD_TAGS[SELECTOR]) != 0):
        raise ValueError('XP2 city occupation event fields differ')
    prior_owner = decode_scalar(fields[PRIOR_OWNER], _FIELD_TAGS[PRIOR_OWNER])
    transfer_type = decode_scalar(fields[TRANSFER], _FIELD_TAGS[TRANSFER])
    descriptor = copy_eight_byte_variant(fields[CITY], read, expected_tag=_FIELD_TAGS[CITY])
    if struct.unpack_from('<H', descriptor, 2)[0] != 2:
        raise ValueError('XP2 city occupation event does not carry a city descriptor')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I4x8sII', record, 80, sequence, descriptor, prior_owner, transfer_type)
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
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0
            or len(owner.pending) >= owner.limit):
        raise ValueError('CityOccupationChanged requires its owned empty A0 receiver')
    record = encode_record(owner._sequence + 1, fields, owner.read)
    validate_empty_profile_record(record, execution_image=image, **owner.empty_receiver_state)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND),
               queue_type=hex(RECORD_TYPE), record_hex=record.hex(),
               source_proof_sha256=SOURCE[1], payload_exposed_to_learner=False,
               eligible_for_training=False)
    return 0

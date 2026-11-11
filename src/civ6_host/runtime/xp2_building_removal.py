"""Current XP2 building-removal notification on the existing plot query lease."""
from .a0_policy_unlock_current import _require_image
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_event_e074eef4 as codec
from .native.native_event_07c83dae import plot_snapshot
from . import xp2_capture_notification_source as registered

SOURCE = registered.SOURCE
KIND, RECORD_TYPE, RECORD_SIZE = codec.EVENT_KIND, codec.RECORD_TYPE, codec.RECORD_SIZE
SELECTOR, POSITION, VALUE = codec.SELECTOR_KEY, codec.POSITION_KEY, codec.SCALAR_KEY


def source():
    return registered.route('building_removed', KIND, {(RECORD_TYPE, RECORD_SIZE)})


def receiver_row():
    return registered.receiver_row(RECORD_TYPE)


def verify_live(core, read):
    registered.verify_live(core, read, source())


def decode_fields(fields, read):
    decoded = codec.decode_fields(fields, read)
    if decoded['selector'] != 0:
        raise ValueError('XP2 building removal selector differs')
    return decoded


def dispatch(owner, fields):
    from .a0_foundation_events import require_borrow
    from .native.native_deferred_empty_profile import validate_empty_profile_record

    backend = require_borrow(owner).owner
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    _require_image(image)
    owner._require_no_f391_reentry()
    if (owner.active_kind != KIND or owner.foundation_core_sha256 != XP2_CORE_SHA256
            or not owner.ui_cache_callbacks_enabled or len(owner.pending) >= owner.limit
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False):
        raise ValueError('XP2 building removal requires its active native receiver')
    state = dict(owner.empty_receiver_state, execution_image=image)
    decoded = decode_fields(fields, owner.read)
    query = dict(position_bytes=decoded['position_bytes'], x=decoded['x'], y=decoded['y'],
                 selector=decoded['selector'], source_value=0,
                 descriptor_tail=decoded['source_scalar'])
    with plot_snapshot(owner.core, owner.context, query, read=owner.read,
                       core_sha256=XP2_CORE_SHA256) as values:
        descriptor = dict(snapshot_sbyte_20=values['owner'], snapshot_dword_4=values['city_id'],
                          snapshot_dword_8=values['district_id'], plot_flag=values['flag148'])
        record = codec._pack_record(owner._sequence + 1, decoded, descriptor)
        validate_empty_profile_record(record, **state)
        owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND),
               queue_type=hex(RECORD_TYPE), record_hex=record.hex(),
               source_proof_sha256=SOURCE[1], native_queries_executed=True,
               plot_released_after_enqueue=True, payload_exposed_to_learner=False,
               eligible_for_training=False, native_dispatch_return=0)
    return 0

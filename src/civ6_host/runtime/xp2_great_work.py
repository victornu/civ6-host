"""Current XP2 Great Work notifications on the owned deferred FIFO."""

import hashlib
from pathlib import Path
import struct

from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import (
    CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image,
)
from .configuration_profiles import XP2_CORE_SHA256, _source
from .native import native_event_great_work as codec
from .native.native_application_mirror import decode_scalar
from .native.native_deferred_empty_profile import validate_empty_profile_record
from .native.native_feature_visibility_event import _copy_blob
from .native.native_player_event_domains import validate_sequence
from .native.native_unary_event_family import _METADATA
from .resource_resolution import resolve_path


SOURCE = ('work/trade-common-client/great-work-current-source/source.json',
          'f4737bcd0f832b55c2d02a3f11b5e2d6ba825346676cd00bfbe08348de9e9ed3')
_REQUIRED_CORE_SITES = (0x1c6b50, 0x5fb6d8)
MOVED_KIND, MOVED_RECORD_TYPE, MOVED_RECORD_SIZE = 0x9648f000, 0xdd, 128
MOVED_SOURCE = ('evidence/host-xp2-great-work-moved-event-source.json',
                '90c97bce5dc92c6478e7f908a628a46a7be32f302358c416c5acf6ba9f06fb69')
_MOVED_CITY_KEYS = (0x23739f42, 0x5474afd4)
_MOVED_FIELDS = {*_MOVED_CITY_KEYS, 0xa1e5a149, 0xd6fcf3e4, 0xa1fbc372}


def source_dependencies(*, execution_image):
    _require_image(execution_image)
    proof = _source(SOURCE)
    contract = proof['contract']
    images = proof['images']
    if (proof['schema'] != 'civ6-host.xp2-great-work-created-current.source.v1'
            or set(images) != {'core', 'exe'}
            or images['core']['sha256'] != CURRENT_CORE_SHA256
            or images['exe']['sha256'] != CURRENT_EXE_SHA256
            or Path(resolve_path(images['core']['path'])).resolve() != Path(execution_image.path).resolve()
            or (contract['kind'], contract['record_type'], contract['record_size'],
                contract['payload_size']) != (hex(codec.EVENT_KIND), codec.RECORD_TYPE,
                                              codec.RECORD_SIZE, 72)
            or (contract['callback_rva'], contract['writer_rva'],
                contract['receiver_row_rva'], contract['receiver_handler_rva']) !=
               ('0x148230', '0x13a910', '0x12ca1f0', '0xda9d0')):
        raise ValueError('XP2 GreatWorkCreated source contract differs')
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1],
            str(codec.PROOF_PATH.resolve()): codec.PROOF_SHA256}
    moved_source()
    pins[str(_path(MOVED_SOURCE[0]).resolve())] = MOVED_SOURCE[1]
    pins.update({str(Path(resolve_path(row['path'])).resolve()): row['sha256'] for row in images.values()})
    verify_pinned_files(pins)
    return pins


def core_fragments():
    proof = _source(SOURCE)
    core = Path(resolve_path(proof['images']['core']['path']))
    with core.open('rb') as stream:
        for site in _REQUIRED_CORE_SITES:
            rows = [row for row in proof['spans'] if row['image'] == 'core'
                    and int(row['rva'], 16) <= site < int(row['end_rva_exclusive'], 16)]
            if len(rows) != 1:
                raise ValueError('XP2 GreatWorkCreated producer coverage differs')
            row = rows[0]
            rva = int(row['rva'], 16)
            count = row['bytes']
            if not 0 < count <= 4096 or int(row['end_rva_exclusive'], 16) - rva != count:
                raise ValueError('XP2 GreatWorkCreated source span is invalid')
            stream.seek(int(row['file_offset'], 16))
            raw = stream.read(count)
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('XP2 GreatWorkCreated installed producer bytes differ')
            yield rva, raw


def verify_live(core, read):
    _require_image(getattr(core, '_civ6_host_execution_image', None))
    for rva, raw in core_fragments():
        if read(core._handle + rva, len(raw)) != raw:
            raise ValueError('XP2 GreatWorkCreated live producer differs at ' + hex(rva))


def dispatch(owner, raw_fields):
    return dispatch_record(owner, raw_fields, core_sha256=XP2_CORE_SHA256,
                           verify_producer=verify_live, proof_sha256=SOURCE[1])


def dispatch_record(owner, raw_fields, *, core_sha256, verify_producer, proof_sha256,
                    descriptor_id=None):
    from .a0_foundation_events import require_borrow
    from .native.native_event_07c83dae import plot_snapshot

    require_borrow(owner)
    owner._require_no_f391_reentry()
    if (owner.active_kind != codec.EVENT_KIND or owner.foundation_core_sha256 != core_sha256
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.host_notification_counter or owner.host_metadata_counter
            or not owner.ui_cache_callbacks_enabled or len(owner.pending) >= owner.limit):
        raise ValueError('GreatWorkCreated requires its empty metadata and cache scope')
    verify_producer(owner.core, owner.read)
    fields, descriptor = codec.decode_fields(raw_fields, owner.read)
    if fields['selector'] != 0 or struct.unpack_from('<H', descriptor, 2)[0] != 1:
        raise ValueError('GreatWorkCreated selector or component type differs')
    if descriptor_id is not None and struct.unpack_from('<I', descriptor, 4)[0] != descriptor_id:
        raise ValueError('GreatWorkCreated component identifier differs from its producer')
    # Check the owned empty receiver before taking native map/plot references.
    shape = bytearray(codec.RECORD_SIZE)
    struct.pack_into('<II', shape, 0, codec.RECORD_SIZE, codec.RECORD_TYPE)
    validate_empty_profile_record(shape, **owner.empty_receiver_state)
    with plot_snapshot(owner.core, owner.context, fields, read=owner.read,
                       include_flag148=False, core_sha256=core_sha256) as values:
        record = codec.encode_record(owner._sequence + 1, fields, descriptor, values)
        owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(codec.EVENT_KIND),
               queue_type=hex(codec.RECORD_TYPE), record_hex=record.hex(),
               pending_count=len(owner.pending), source_proof_sha256=proof_sha256,
               native_plot_snapshot_queried=True, native_plot_retained_through_enqueue=True,
               plot_released_after_enqueue=True, plot_flag148_called=False,
               unspecified_padding_policy='zero-unread-empty-receiver',
               consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
    return 0


def moved_source():
    proof = _source(MOVED_SOURCE)
    contract = proof['contract']
    if (proof['schema'] != 'civ6-host.xp2-great-work-moved-event-source.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or contract['event_name'] != 'GameCoreEvent::GreatWorkMoved'
            or (contract['kind'], contract['record_type'], contract['record_size'],
                contract['metadata_flag'], contract['city_entity_type'])
                != (MOVED_KIND, MOVED_RECORD_TYPE, MOVED_RECORD_SIZE, 0, 2)
            or not contract['empty_subscriber_receiver']
            or contract['native_gameplay_write'] is not False):
        raise ValueError('Current XP2 GreatWorkMoved source contract differs')
    return proof


def moved_receiver_row():
    proof = moved_source()
    handler = proof['exe_spans']['handler']
    return dict(event_name=proof['contract']['event_name'],
                handler_va=hex(0x140000000 + handler['rva']),
                handler_body_sha256=handler['sha256'], record_sizes={MOVED_RECORD_SIZE})


def encode_moved_record(sequence, fields, read):
    validate_sequence(sequence)
    if type(fields) is not dict or fields.keys() != _MOVED_FIELDS:
        raise ValueError('GreatWorkMoved requires exactly two city descriptors and three scalars')
    decode_scalar(fields[0xa1e5a149], 3)
    first = decode_scalar(fields[0xd6fcf3e4], 2)
    second = decode_scalar(fields[0xa1fbc372], 2)

    record = bytearray(MOVED_RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, MOVED_RECORD_SIZE, MOVED_RECORD_TYPE, sequence, 0)
    record[16:80] = _METADATA
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<I', record, 88, first)
    for offset, key in zip((96, 104), _MOVED_CITY_KEYS):
        owner, _, city_id = struct.unpack('<HHI', _copy_blob(fields[key], read, 1024))
        # The normalized city slots both have a fixed type word of 2.
        struct.pack_into('<HHI', record, offset, owner, 2, city_id)
    struct.pack_into('<I', record, 112, second)
    return bytes(record)


def dispatch_moved(owner, fields):
    from .a0_foundation_events import require_borrow

    require_borrow(owner)
    owner._require_no_f391_reentry()
    core = owner.core
    image = core._civ6_host_execution_image
    from .execution_images import _XP1_PROFILE
    if image is _XP1_PROFILE:
        from . import xp1_great_work_move_source as rise_and_fall

        source_spans = rise_and_fall.source(image)['event_spans']
        proof_sha = rise_and_fall.SOURCE[1]
    else:
        _require_image(image)
        source_spans = moved_source()['core_spans']
        proof_sha = MOVED_SOURCE[1]
    if (owner.active_kind != MOVED_KIND or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False or owner.writer_metadata_callback_present is not False
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0):
        raise ValueError('GreatWorkMoved requires its source-qualified empty notification profile')
    for span in source_spans.values():
        raw = owner.read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('GreatWorkMoved live producer differs')
    record = encode_moved_record(owner._sequence + 1, fields, owner.read)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(MOVED_KIND),
               queue_type=hex(MOVED_RECORD_TYPE), record_hex=record.hex(),
               source_proof_sha256=proof_sha, borrowed_payload_retained=False,
               payload_exposed_to_learner=False, eligible_for_training=False)
    return 0

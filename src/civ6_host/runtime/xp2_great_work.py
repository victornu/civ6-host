"""Current XP2 GreatWorkCreated using the existing plot query and FIFO codec."""

import hashlib
from pathlib import Path
import struct

from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import (
    CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image,
)
from .configuration_profiles import XP2_CORE_SHA256, _source
from .native import native_event_great_work as codec
from .native.native_deferred_empty_profile import validate_empty_profile_record
from .resource_resolution import resolve_path


SOURCE = ('work/trade-common-client/great-work-current-source/source.json',
          'f4737bcd0f832b55c2d02a3f11b5e2d6ba825346676cd00bfbe08348de9e9ed3')
_REQUIRED_CORE_SITES = (0x1c6b50, 0x5fb6d8)


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
    from .a0_foundation_events import require_borrow
    from .native.native_event_07c83dae import plot_snapshot

    require_borrow(owner)
    owner._require_no_f391_reentry()
    if (owner.active_kind != codec.EVENT_KIND or owner.foundation_core_sha256 != XP2_CORE_SHA256
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.host_notification_counter or owner.host_metadata_counter
            or not owner.ui_cache_callbacks_enabled or len(owner.pending) >= owner.limit):
        raise ValueError('XP2 GreatWorkCreated requires its empty metadata and cache scope')
    verify_live(owner.core, owner.read)
    fields, descriptor = codec.decode_fields(raw_fields, owner.read)
    if fields['selector'] != 0 or struct.unpack_from('<H', descriptor, 2)[0] != 1:
        raise ValueError('XP2 GreatWorkCreated selector or component type differs')
    # Check the owned empty receiver before taking native map/plot references.
    shape = bytearray(codec.RECORD_SIZE)
    struct.pack_into('<II', shape, 0, codec.RECORD_SIZE, codec.RECORD_TYPE)
    validate_empty_profile_record(shape, **owner.empty_receiver_state)
    with plot_snapshot(owner.core, owner.context, fields, read=owner.read,
                       include_flag148=False, core_sha256=XP2_CORE_SHA256) as values:
        record = codec.encode_record(owner._sequence + 1, fields, descriptor, values)
        owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(codec.EVENT_KIND),
               queue_type=hex(codec.RECORD_TYPE), record_hex=record.hex(),
               pending_count=len(owner.pending), source_proof_sha256=SOURCE[1],
               native_plot_snapshot_queried=True, native_plot_retained_through_enqueue=True,
               plot_released_after_enqueue=True, plot_flag148_called=False,
               unspecified_padding_policy='zero-unread-empty-receiver',
               consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
    return 0

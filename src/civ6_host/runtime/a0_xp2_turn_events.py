"""Owned XP2 weather notifications using the common A0 continuation and FIFO.

Native queries still execute in their official producer order. Host-owned
presentation arrays live until their exact empty-subscriber record is consumed;
their release is a host storage policy, not a claimed EXE gameplay post-hook.
"""
import ctypes as C
from dataclasses import dataclass
import struct

from .configuration_profiles import XP2_CORE_SHA256
from . import xp2_turn_event_profile as source
from .native.native_deferred_empty_profile import validate_empty_profile_record


@dataclass(frozen=True)
class RetainedRecord:
    record: bytes
    storage: object
    snapshot: bytes


def enable(owner, backend):
    owner._check()
    backend.check_thread()
    if (owner.climate_event_profile is not None or owner._climate_records
            or owner._foundation_backend is not backend
            or owner._foundation_borrow is not None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage != 'prepared' or backend.prefix is not None
            or getattr(backend, '_xp1_commands_requested', False) is not True
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.host is not owner.arguments.host
            or backend.core is not owner.deferred.core
            or backend.context != owner.deferred.context
            or owner.deferred.cache_core_sha256 != XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256 != XP2_CORE_SHA256
            or owner.normalizer_transform_present is not False):
        raise ValueError('Climate callbacks require the exact idle prepared XP2 owner')
    profile = source.event_profile(core_sha256=XP2_CORE_SHA256)
    if any(owner.handles_kind(kind) for kind in profile.record_types_by_kind):
        raise ValueError('Climate callback overlaps an installed A0 family')
    for kind, size in profile.record_sizes.items():
        row = bytearray(size)
        struct.pack_into('<II', row, 0, size, kind)
        validate_empty_profile_record(row, **owner.empty_receiver_state)
    source.bind_owner(backend, backend.core, owner.read)
    owner.climate_event_profile = owner._climate_event_profile = profile
    return owner


def _storm_record(sequence, fields, query):
    """Build only defined native outputs; stack padding is explicitly zeroed.

    EXE 1532A0/146D30 leave the array fields undefined for an empty vector.
    That branch remains an explicit refusal, rather than inventing a native
    zero count/pointer or reading an uninitialized coordinate output.
    """
    storm = fields.kind == source.STORM_KIND
    if fields.kind not in (source.STORM_KIND, source.DESCRIPTOR53_KIND):
        raise ValueError('Unknown native array notification')
    if not query.items or (storm and query.position is None):
        raise ValueError(f'Weather presentation outputs undefined: items={len(query.items)}, '
                         f'service_words_written={query.position is not None}')
    if not storm and query.position is not None:
        raise ValueError('Descriptor53 callback does not query the Storm pair service')
    if len(query.positions) != len(query.items):
        raise ValueError('Storm item conversions are incomplete')
    pairs = tuple(query.positions)
    if any(type(pair) is not bytes or len(pair) != 8 for pair in pairs):
        raise ValueError('Storm positions must be complete native pair copies')
    snapshot = b''.join(pairs)
    array = C.create_string_buffer(snapshot, len(snapshot))
    from .xp2_turn_event_records import make_header
    row = make_header(128 if storm else 112, 0x138 if storm else 0x13b, sequence, 4)
    struct.pack_into('<I', row, 80, sequence)
    struct.pack_into('<HHII', row, 88, 0xffff, 0x52 if storm else 0x53,
                     fields.identifier, fields.value)
    # Official helper copies the second +110 DWORD first (146ED3..146EE1).
    if storm:
        struct.pack_into('<IIIQ', row, 100, query.position[1], query.position[0],
                         len(pairs), C.addressof(array))
    else:
        struct.pack_into('<IQ', row, 100, len(pairs), C.addressof(array))
    return RetainedRecord(bytes(row), array, snapshot)


def dispatch(owner, kind, raw_fields):
    from .xp1_continuation import SavedContinuation
    from .a0_foundation_events import require_borrow
    from . import xp2_turn_event_records as codec
    from .xp2_storm_query import query_storm_objects
    from .xp2_descriptor53_query import query_descriptor53_objects
    from .xp2_weather_position import query_native_position_index
    backend = owner._foundation_backend
    token = getattr(backend, '_xp1_continuation', None)
    if (type(token) is not SavedContinuation or token.owner is not backend
            or owner._foundation_borrow is not None or owner.active_kind != kind
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or owner.climate_event_profile is None
            or owner.climate_event_profile is not owner._climate_event_profile
            or kind not in owner.climate_event_profile.record_types_by_kind):
        raise ValueError('Climate callback lacks its exact synchronous continuation')
    count = len(owner.climate_event_profile.record_types_by_kind[kind])
    if (len(owner.pending) + count > owner.limit
            or type(owner._sequence) is not int
            or not 0 <= owner._sequence < 0x7fffffff - count):
        raise RuntimeError('Climate FIFO sequence or resource bound exhausted')
    token.check(active=True)
    owner.deferred._check()
    before = (owner.host_notification_counter, owner.host_metadata_counter)
    owner._foundation_borrow = token
    try:
        require_borrow(owner)
        from . import xp2_weather_lifecycle as lifecycle
        if kind in lifecycle.KINDS:
            policy = lifecycle.validate_empty_owner(owner)
            sequence_before = owner._sequence
            pending_before = tuple(owner.pending)
            retained_before = dict(owner._climate_records)
            values = lifecycle.decode_fields(kind, raw_fields, owner.read)
            lifecycle.validate_empty_owner(owner)
            if (count != 0 or owner._sequence != sequence_before
                    or len(owner.pending) != len(pending_before)
                    or any(a is not b for a, b in zip(owner.pending, pending_before))
                    or owner._climate_records != retained_before
                    or before != (owner.host_notification_counter, owner.host_metadata_counter)):
                raise RuntimeError('Weather presentation omission changed its native FIFO or scope')
            owner.emit('native_xp2_weather_presentation_omitted', dispatch_kind=hex(kind),
                source_proof_sha256=lifecycle.SOURCE[1], dispatch_scope_sha256=source.SCOPE_SOURCE[1],
                policy=policy, administrative_arguments=values.to_admin(),
                information_scope='administrative-unfiltered', public_visibility_qualified=False,
                native_queries_executed=False, native_gameplay_written=False,
                presentation_arrays_allocated=False, records_enqueued=0,
                fifo_sequence_before=sequence_before, fifo_sequence_after=owner._sequence,
                preceding_pending_records_preserved=True, native_dispatch_return=0,
                eligible_for_training=False)
            return 0
        first = owner._sequence + 1
        event_source = source.SOURCE[1]
        if kind == codec.TERRAIN_KIND:
            if owner.normalizer_transform_present is not False:
                raise ValueError('Unqualified terrain notification normalizer')
            retained = (RetainedRecord(codec.encode_terrain(raw_fields, first, owner.read),
                                       None, b''),)
            event_source = codec.TERRAIN_SOURCE[1]
            details = dict(native_queries_executed=False, undefined_record_ranges=[])
        elif kind == source.FAVOR_KIND:
            from . import xp2_favor_event_profile as favor
            row = favor.encode(kind, raw_fields, first,
                empty_receiver_state=owner.empty_receiver_state,
                normalizer_transform_present=owner.normalizer_transform_present,
                per_thread_hook_present=False, writer_metadata_callback_present=False)
            retained = (RetainedRecord(row, None, b''),)
            event_source = favor.SOURCE[1]
            details = dict(native_queries_executed=False, undefined_record_ranges=[])
        elif kind in (source.STORM_KIND, source.DESCRIPTOR53_KIND):
            fields = codec.decode_fields(kind, raw_fields, owner.read)
            storm = kind == source.STORM_KIND
            query_fn = query_storm_objects if storm else query_descriptor53_objects
            query = query_fn(backend.core, backend.context,
                struct.pack('<HHI', 0xffff, 0x52 if storm else 0x53, fields.identifier), read=owner.read)
            retained = (_storm_record(first, fields, query),)
            details = dict(native_queries_executed=True,
                           copied_plot_indices=list(query.items),
                           copied_plot_positions=[p.hex() for p in query.positions],
                           copied_service_words=list(query.position) if storm else None,
                           undefined_record_ranges=[[84, 88]],
                           storage_release_policy='host-owned-after-empty-consumption')
        else:
            fields = codec.decode_fields(kind, raw_fields, owner.read)
            index = None
            if codec.requires_position_query(fields):
                facades = token.lease.require(token.lease.backend, token.publisher._facades)
                result = query_native_position_index(backend.core, facades,
                    fields.position, read=owner.read)
                token.lease.require(token.lease.backend, facades)
                index = result.index
            rows = codec.encode_records(kind, first, fields, position_index=index,
                empty_receiver_state=owner.empty_receiver_state,
                normalizer_transform_present=owner.normalizer_transform_present,
                per_thread_hook_present=False, writer_metadata_callback_present=False,
                undefined_payload_policy=(None if kind == codec.CLIMATE_KIND
                                          else codec.UNDEFINED_PAYLOAD_POLICY))
            retained = tuple(RetainedRecord(row, None, b'') for row in rows)
            details = dict(native_queries_executed=index is not None,
                           native_position_index=index,
                           undefined_record_ranges=codec.registration_metadata(kind)['undefined_record_ranges'])
        if len(retained) != count:
            raise ValueError('Climate callback produced an unexpected record count')
        # Validate the whole callback before publishing its first queue record.
        for entry in retained:
            validate_empty_profile_record(entry.record, **owner.empty_receiver_state)
            seq = struct.unpack_from('<I', entry.record, 8)[0]
            if seq in owner._climate_records:
                raise ValueError('Climate record ownership token is already live')
        for entry in retained:
            seq = struct.unpack_from('<I', entry.record, 8)[0]
            owner._climate_records[seq] = entry
            owner._enqueue(entry.record)
        if before != (owner.host_notification_counter, owner.host_metadata_counter):
            raise RuntimeError('Climate producer changed its enclosing notification scope')
        stage = ('native_xp2_turn_event_enqueued' if kind == source.FAVOR_KIND
                 else 'native_xp2_climate_event_enqueued')
        owner.emit(stage, dispatch_kind=hex(kind),
            source_proof_sha256=event_source,
            record_sequences=list(range(first, first + count)),
            record_hex=[entry.record.hex() for entry in retained],
            information_scope='administrative-unfiltered',
            public_visibility_qualified=False, native_dispatch_return=0,
            eligible_for_training=False, **details)
        return 0
    finally:
        owner._foundation_borrow = None


def consume(owner, record, sequence):
    """Validate storage before shared consumption; release only its own lease."""
    d = owner.deferred
    entry = owner._climate_records.get(sequence)
    if (type(entry) is not RetainedRecord or entry.record is not record
            or not d._draining_empty_receivers or not d.pending or d.pending[0] is not record
            or sequence != d.consumed_count + 1):
        raise ValueError('Climate receiver lacks its exact owned FIFO head')
    if entry.storage is not None:
        record_type = struct.unpack_from('<I', record, 4)[0]
        count_at, pointer_at = {0x138: (108, 112), 0x13b: (100, 104)}[record_type]
        if (bytes(entry.storage) != entry.snapshot
                or struct.unpack_from('<Q', record, pointer_at)[0] != C.addressof(entry.storage)
                or struct.unpack_from('<I', record, count_at)[0] * 8 != len(entry.snapshot)):
            raise ValueError('Climate presentation array changed before consumption')
    validate_empty_profile_record(record, **owner.empty_receiver_state)
    d._consume_empty_record(record, sequence, empty_receiver_state=owner.empty_receiver_state)
    # No native post-hook exists in this empty profile. Python releases only
    # its copied presentation storage after the shared FIFO commit succeeds.
    del owner._climate_records[sequence]

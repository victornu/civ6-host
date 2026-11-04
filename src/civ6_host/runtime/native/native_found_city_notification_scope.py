"""Inline native metadata transitions for the 33D/28D6 producer pair.

This changes notification metadata only; original Core queries and existing
source record encoders still produce the payload. The item used by 28D6 remains
alive through append, metadata commit and its original release.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
PROOF_SHA256 = '28f3686117c40f8c0b1e2ae3de1a93ad642ef3ca8a4a173bcc1873bb61963ca9'
RECORDS = {869823066: (154, 128), 685173694: (158, 144)}

def verify_source_evidence():
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_found_city_notification_scope.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-found-city-notification-scope' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_found_city_notification_scope.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('Found-city metadata source identity changed')
    from civ6_host.runtime.native.native_event_33d8725a import verify_source_evidence as verify_position
    from civ6_host.runtime.native.native_event_28d6ebbe import verify_source_evidence as verify_item
    verify_position()
    verify_item()
    if proof['shared_scope_contract']['metadata_flag_offset'] != 72:
        raise RuntimeError('Found-city metadata record offset changed')
    for kind, (record_type, size) in RECORDS.items():
        event = proof['events'][f'{kind:08x}']
        if event['record_type'] != record_type or event['record_size'] != size or event['record_metadata_flag_offset'] != 72 or (event['n_global']['va'] != '0x1422d7c6c') or (event['m_global']['va'] != '0x1422d7c68'):
            raise RuntimeError('Found-city metadata source contract changed')
    return proof

def _preflight(host, kind):
    verify_source_evidence()
    if kind not in RECORDS:
        raise ValueError('Unknown scoped found-city notification')
    metadata_scope_transition(host.host_notification_counter, host.host_metadata_counter)
    if type(host._sequence) is not int or not 0 <= host._sequence < 2147483647:
        raise ValueError('Found-city sequence exceeds the bounded queue profile')
    if len(host.pending) >= host.limit:
        raise RuntimeError('Native deferred queue bound exceeded')
    if type(host.entity_listener_count) is not int or host.entity_listener_count != 0:
        raise ValueError('Found-city metadata requires actual empty entity listeners')
    record_type, size = RECORDS[kind]
    shape = bytearray(size)
    struct.pack_into('<II', shape, 0, size, record_type)
    validate_empty_profile_record(shape, **host.empty_receiver_state)
    return (host._sequence, host.host_notification_counter, host.host_metadata_counter)

@contextmanager
def _position_record(host, sequence, decoded, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    from civ6_host.runtime.native.native_event_33d8725a import encode_record
    yield encode_record(sequence, decoded, notification_counter=0, notification_limit=0, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', core=host.core, context=host.context, read=host.read, core_sha256=core_sha256)

def dispatch_scoped(host, kind, raw_fields, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Fatal on query/release/reentrant failure; never retry a partial append."""
    host._require_no_f391_reentry()
    prior = _preflight(host, kind)
    host._found_city_producing = True
    try:
        if kind == 869823066:
            from civ6_host.runtime.native.native_event_33d8725a import decode_fields
            fields = decode_fields(raw_fields, host.read)
            index = fields['optional_index']
            lease = _position_record(host, prior[0] + 1, fields, core_sha256=core_sha256)
        else:
            from civ6_host.runtime.native.native_event_28d6ebbe import decode_fields
            from civ6_host.runtime.native.native_event_28d6ebbe import produce_record_lease
            fields = decode_fields(raw_fields, host.read)
            index = fields.optional_index
            lease = produce_record_lease(prior[0] + 1, host.core, host.context, fields, notification_counter=0, notification_limit=0, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='headless-zero-uninitialized-stack', read=host.read, core_sha256=core_sha256)
        queried = index is not None and index < 2147483648
        if queried and (not host.ui_cache_callbacks_enabled):
            raise ValueError('Found-city positive index requires initialized native map facade')
        with lease as unscoped:
            if (host._sequence, host.host_notification_counter, host.host_metadata_counter) != prior:
                raise RuntimeError('Found-city native query changed queue or metadata state')
            flag, next_metadata = metadata_scope_transition(prior[1], prior[2])
            if struct.unpack_from('<I', unscoped, 72)[0] != 0:
                raise RuntimeError('Found-city legacy metadata is not source zero')
            record = bytearray(unscoped)
            struct.pack_into('<I', record, 72, flag)
            record = bytes(record)
            validate_empty_profile_record(record, **host.empty_receiver_state)
            host._enqueue(record)
            host.host_metadata_counter = next_metadata
        if (host._sequence, host.host_notification_counter, host.host_metadata_counter) != (prior[0] + 1, prior[1], next_metadata):
            raise RuntimeError('Found-city native release changed queue or metadata state')
        host.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=host._sequence, notification_counter=prior[1], metadata_before=prior[2], metadata_after=next_metadata, metadata_flag=flag, source_proof_sha256=PROOF_SHA256, empty_receiver_state_verified=True, item_released_after_enqueue=kind == 685173694, eligible_for_training=False)
        host.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORDS[kind][0]), record_hex=record.hex(), pending_count=len(host.pending), native_optional_map_query_executed=queried, optional_map_index=index, native_item_queries_executed=kind == 685173694, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
        return 0
    except BaseException:
        host._found_city_poisoned = True
        raise
    finally:
        host._found_city_producing = False

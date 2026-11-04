"""Counter-neutral F26F3ACF path under its source-pinned empty receiver row."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
PROOF_SHA256 = 'd11156485cd87f78643c9ed40447b3ea5ae97efd1bf7901e95d4afd84b586736'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_f26f3acf_counter_scope.py')))).resolve().parents[1] / 'evidence/native-f26f3acf-counter-scope' / (PROOF_SHA256 + '.json')
RECORD_TYPE, RECORD_SIZE = (256, 96)
EMPTY_RECEIVER_STATE = {'observer_registered': False, 'state_pointer_nonnull': True, 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'state_flags': 0}

def verify_source_evidence():
    proof = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_f26f3acf_counter_scope361.work.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['source_recapture']['callback_counter_rip_targets']['direct_N_or_M_reference'] is not False or (proof['source_recapture']['metadata_contract'] != {'counter_dependent_flag': False, 'metadata_flag_constant': 4, 'metadata_flag_offset': '0x48', 'record_size': '0x60', 'record_type': '0x100'}) or (proof['scope_conclusion']['native_N_positive_witness'] is not False) or (proof['scope_conclusion']['native_M_positive_witness'] is not False):
        raise RuntimeError('F26 counter-neutral source contract changed')
    for parent in proof['parents'].values():
        load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_f26f3acf_counter_scope.py')))).resolve().parents[1] / parent['path'], parent['sha256'])
    from civ6_host.runtime.native.native_event_f26f3acf import verify_source_evidence
    verify_source_evidence()
    return proof

def _validate_empty_state(state):
    if type(state) is not dict or set(state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('F26 requires the exact pinned empty receiver state')
    if state['observer_registered'] is not False or state['state_pointer_nonnull'] is not True or state['pre_hook'] is not None or (state['post_hook'] is not None) or (type(state['subscriber_count']) is not int) or (state['subscriber_count'] != 0) or (type(state['state_flags']) is not int) or (state['state_flags'] != 0):
        raise ValueError('F26 requires the exact pinned empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **state)

def dispatch_scoped(host, kind, raw_fields):
    """Encode legacy-identical F26 bytes and preserve exact host N/M values."""
    verify_source_evidence()
    if type(kind) is not int or kind != 4067375823:
        raise ValueError('Unknown F26 counter-neutral event')
    host._require_no_f391_reentry()
    n, m, sequence = (host.host_notification_counter, host.host_metadata_counter, host._sequence)
    if any((type(v) is not int or not 0 <= v <= 4294967295 for v in (n, m))):
        raise ValueError('F26 requires exact uint32 notification counters')
    if type(sequence) is not int or not 0 <= sequence < 2147483647:
        raise ValueError('F26 sequence exhausted')
    if type(host.limit) is not int or host.limit < 0 or len(host.pending) >= host.limit:
        raise RuntimeError('Native deferred queue bound exceeded')
    if type(host.entity_listener_count) is not int or host.entity_listener_count != 0:
        raise ValueError('F26 requires the actual empty entity-listener profile')
    _validate_empty_state(host.empty_receiver_state)
    from civ6_host.runtime.native.native_event_f26f3acf import BLOB_KEY
    from civ6_host.runtime.native.native_event_f26f3acf import decode_fields
    from civ6_host.runtime.native.native_event_f26f3acf import encode_record
    host._found_city_producing = True
    try:
        decoded = decode_fields(raw_fields, host.read)
        if (host.host_notification_counter, host.host_metadata_counter, host._sequence) != (n, m, sequence):
            raise RuntimeError('F26 field copy changed host N/M or sequence')
        blob = raw_fields[BLOB_KEY]
        pointer = struct.unpack_from('<Q', blob, 8)[0]
        copied = decoded['entity_bytes']

        def copied_reader(address, size):
            if address != pointer or size != 8:
                raise ValueError('F26 encoder requested an unverified pointer read')
            return copied
        record = encode_record(sequence + 1, raw_fields, copied_reader, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero')
        validate_empty_profile_record(record, **host.empty_receiver_state)
        if struct.unpack_from('<I', record, 72)[0] != 4:
            raise RuntimeError('F26 constant metadata flag changed')
        if (host.host_notification_counter, host.host_metadata_counter, host._sequence) != (n, m, sequence):
            raise RuntimeError('F26 producer changed host N/M or sequence before enqueue')
        host._enqueue(record)
        if (host.host_notification_counter, host.host_metadata_counter, host._sequence) != (n, m, sequence + 1):
            raise RuntimeError('F26 enqueue changed host N/M or sequence unexpectedly')
        host.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=host._sequence, notification_counter=n, metadata_before=m, metadata_after=m, metadata_flag=4, counter_independent_producer=True, source_proof_sha256=PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
        host.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x100', record_hex=record.hex(), owner=decoded['owner'], source_type=decoded['source_type'], identifier=decoded['identifier'], pending_count=len(host.pending), metadata_flags=4, source_proof_sha256=PROOF_SHA256, native_query_executed=False, descriptor_copied_before_enqueue=True, descriptor_lease_retained=False, optional_preprocessing_hook_registered=False, queue_metadata_service_registered=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
        return 0
    except BaseException:
        host._found_city_poisoned = True
        raise
    finally:
        host._found_city_producing = False
__all__ = ['EMPTY_RECEIVER_STATE', 'PROOF_PATH', 'PROOF_SHA256', 'RECORD_SIZE', 'RECORD_TYPE', 'dispatch_scoped', 'verify_source_evidence']

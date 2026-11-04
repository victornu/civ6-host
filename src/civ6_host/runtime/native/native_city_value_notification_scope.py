"""1D355E83 N/M scope adapter for the witnessed pair-five shape.

This preserves the existing codec and admits only the exact five-field shape
for which A1FBC/38F are absent and the native optional lookup returns before
Core map acquisition.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native import native_event_1d355e83 as event
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'd3b6d86fd04383f466d46e8c1c85fe6babb35f05ba51a91aa08a3baf560046e1'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_value_notification_scope.py')))).resolve().parents[1] / 'evidence/native-nonzero-scope-closure/1d355e83' / f'{PROOF_SHA256}.json'
EMPTY_RECEIVER_STATE = {'observer_registered': False, 'state_pointer_nonnull': True, 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'state_flags': 0}
PADDING_POLICY = 'headless-zero-uninitialized-stack'

def verify_source_evidence():
    proof = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_1d355e83_counter_scope.static.v1' or proof.get('kind') != event.EVENT_KIND or proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof.get('parents', {}).get('producer', {}).get('sha256') != event.PIN) or (proof.get('parents', {}).get('probe360', {}).get('sha256') != '23ad4b2a023b7776a8685a007ebee97ddbeb1e65f2384bd39234af43037ff980') or (proof.get('counter_contract', {}).get('record_metadata_flag_offset') != '0x48') or (proof.get('counter_contract', {}).get('N_written') is not False) or (proof.get('counter_contract', {}).get('M_read_only_when_N_nonzero') is not True) or (proof.get('query_and_lifetime_contract', {}).get('only_admitted_input_shape') != 'exact pair-five-field; keys 23739F42,5B55A347,A1E5A149,D6FCF3E4,F06A2AF2') or (proof.get('query_and_lifetime_contract', {}).get('Core_map_or_plot_query_executed') is not False) or (proof.get('closed_profile', {}).get('empty_receiver_type') != 92) or (proof.get('closed_profile', {}).get('empty_receiver_size') != 128):
        raise RuntimeError('1D355E83 N/M scope evidence changed')
    event.verify_source_evidence()
    return proof

def _validate_receiver(state, entity_listener_count):
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('1D355E83 scope requires exact zero entity listeners')
    if type(state) is not dict or set(state) != set(EMPTY_RECEIVER_STATE) or type(state.get('observer_registered')) is not bool or (type(state.get('state_pointer_nonnull')) is not bool) or (type(state.get('pre_hook')) is not type(None)) or (type(state.get('post_hook')) is not type(None)) or (type(state.get('subscriber_count')) is not int) or (type(state.get('state_flags')) is not int) or (state != EMPTY_RECEIVER_STATE):
        raise ValueError('1D355E83 scope requires the exact empty type-0x5C receiver')
    shape = bytearray(event.RECORD_SIZE)
    struct.pack_into('<II', shape, 0, event.RECORD_SIZE, event.RECORD_TYPE)
    validate_empty_profile_record(shape, **state)

def encode_scoped_record(sequence, fields, *, notification_counter, metadata_counter, notification_limit, entity_listener_count, empty_receiver_state, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Encode the pair-five record and return ``(record, next_M, flag)``.

    The legacy codec is used at its proven zero-counter interface, then the
    source-derived callback metadata DWORD at +0x48 is written. M's returned
    value models the native transition; callers must keep native hook/writer
    behavior out of scope and must not imply native failure atomicity.
    """
    verify_source_evidence()
    _validate_receiver(empty_receiver_state, entity_listener_count)
    if not isinstance(fields, event.EventFields) or fields.input_shape != 'pair-five-field':
        raise ValueError('1D355E83 nonzero scope admits only the witnessed pair-five-field shape')
    if type(notification_limit) is not int or notification_limit != 0:
        raise ValueError('1D355E83 scope admits only notification limit zero')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('1D355E83 optional transform/hooks must be explicitly absent')
    flag, next_m = metadata_scope_transition(notification_counter, metadata_counter)
    record = bytearray(event.encode_record(sequence, fields, notification_counter=0, notification_limit=0, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=padding_policy, core_sha256=core_sha256))
    if struct.unpack_from('<I', record, 72)[0] != 0:
        raise RuntimeError('1D355E83 legacy codec metadata base is not zero')
    struct.pack_into('<I', record, 72, flag)
    result = bytes(record)
    validate_empty_profile_record(result, **empty_receiver_state)
    return (result, next_m, flag)

def dispatch_scoped(host, kind, raw_fields, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Copy borrowed inputs, append, and commit M in a synchronous host scope.

    The native M store precedes its writer. This host has no optional hooks or
    metadata service; a partial append/commit failure poisons the worker rather
    than claiming native failure atomicity or repairing the state.
    """
    verify_source_evidence()
    host._require_no_f391_reentry()
    if kind != event.EVENT_KIND or type(raw_fields) is not dict or set(raw_fields) != {594779970, 1532339015, 2716180809, 3606901732, 4033489650}:
        raise ValueError('Scoped city notification requires exact pair-five input')
    _validate_receiver(host.empty_receiver_state, host.entity_listener_count)
    sequence, n, m = (host._sequence, host.host_notification_counter, host.host_metadata_counter)
    metadata_scope_transition(n, m)
    if type(sequence) is not int or not 0 <= sequence < 2147483647:
        raise ValueError('City notification sequence exhausted')
    if len(host.pending) >= host.limit:
        raise RuntimeError('City notification queue bound exceeded')
    host._found_city_producing = True
    try:
        fields = event.decode_fields(raw_fields, host.read)
        record, next_m, flag = encode_scoped_record(sequence + 1, fields, notification_counter=n, metadata_counter=m, notification_limit=0, entity_listener_count=host.entity_listener_count, empty_receiver_state=host.empty_receiver_state, normalizer_transform_present=False, per_thread_hook_present=False, writer_metadata_callback_present=False, padding_policy=PADDING_POLICY, core_sha256=core_sha256)
        if (host._sequence, host.host_notification_counter, host.host_metadata_counter) != (sequence, n, m):
            raise RuntimeError('City notification state changed during borrowed input copy')
        host._enqueue(record)
        if (host._sequence, host.host_notification_counter, host.host_metadata_counter) != (sequence + 1, n, m):
            raise RuntimeError('City notification state changed during append')
        host.host_metadata_counter = next_m
        host.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=host._sequence, notification_counter=n, metadata_before=m, metadata_after=next_m, metadata_flag=flag, source_proof_sha256=PROOF_SHA256, host_policy='synchronous append then M commit; fatal on partial failure', native_failure_atomicity_claimed=False, empty_receiver_state_verified=True, eligible_for_training=False)
        host.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type='0x5c', record_hex=record.hex(), owner=fields.owner, item_id=fields.item_id, value=fields.value, pending_count=len(host.pending), input_shape=fields.input_shape, optional_query_fields_absent=True, native_query_executed=False, payload_exposed_to_learner=False, source_proof_sha256=PROOF_SHA256, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
        return 0
    except BaseException:
        host._found_city_poisoned = True
        raise
    finally:
        host._found_city_producing = False

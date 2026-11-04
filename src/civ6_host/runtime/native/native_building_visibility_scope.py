"""Source-pinned 037A1BEE metadata and retained native plot-query lifetime."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_found_city_notification_scope import PROOF_SHA256 as FOUND_CITY_SCOPE_SHA256
from civ6_host.runtime.native.native_found_city_notification_scope import verify_source_evidence as verify_existing_scope
from civ6_host.runtime.native.native_notification_metadata import metadata_scope_transition
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native import native_event_037a1bee as event037
PROOF_SHA256 = 'bcc194b6155cf79927fa09fcba8c786033eb75219193a8988e552a2d9fe0a2e6'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_building_visibility_scope.py')))).resolve().parents[1] / 'work/native-037a1bee-positive-scope356' / f'{PROOF_SHA256}.json'
RECORDS = {event037.EVENT_KIND: (event037.RECORD_TYPE, event037.RECORD_SIZE)}

def verify_source_evidence():
    proof = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    verify_existing_scope()
    event037.verify_source_evidence()
    event037.verify_positive_source_evidence()
    parents = proof.get('parents', {})
    if proof.get('schema') != 'civ6rl.native_event_037a1bee_positive_scope356.work.v1' or proof.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or parents.get('producer_037a', {}).get('sha256') != event037.PINNED_EVIDENCE_SHA256 or (parents.get('positive_037a', {}).get('sha256') != event037.POSITIVE_PROOF_SHA256) or (parents.get('found_city_scope_33d_28d', {}).get('sha256') != FOUND_CITY_SCOPE_SHA256) or (proof.get('source_recapture', {}).get('receiver_A7', {}).get('record_type') != 167) or (proof.get('source_recapture', {}).get('receiver_A7', {}).get('record_size') != 144) or (int(proof.get('source_recapture', {}).get('metadata_and_order', {}).get('record_flag_offset', '0'), 0) != 72) or (proof.get('source_recapture', {}).get('metadata_and_order', {}).get('M_store_is_before_writer') is not True) or (proof.get('source_recapture', {}).get('metadata_and_order', {}).get('post_writer_M_commit_found') is not False) or (proof.get('trace356', {}).get('sha256') != '35dbb954e2e1e39a9baef7c2a6bcfd022fa77838c47b28b5e185f13397b23885'):
        raise RuntimeError('037A1BEE positive scope contract changed')
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

def dispatch_scoped(host, kind, raw_fields, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Keep A7's native plot alive through enqueue, then release it exactly once."""
    if core_sha256 not in ('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83', '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Unqualified facade engine')
    if kind != event037.EVENT_KIND:
        raise ValueError('Unknown scoped found-city notification')
    host._require_no_f391_reentry()
    prior = _preflight(host, kind)
    host._found_city_producing = True
    try:
        fields = event037.decode_fields(raw_fields, host.read)
        index = fields['optional_index']
        optional_query = index is not None and index < 2147483648
        if optional_query and (not host.ui_cache_callbacks_enabled):
            raise ValueError('037A1BEE positive index requires initialized native map facade')
        with event037.produce_record_lease(prior[0] + 1, host.core, host.context, fields, notification_counter=0, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False, padding_policy='zero', read=host.read, native_api=getattr(host, 'native_plot_api', None), optional_native_api=getattr(host, 'optional_position_api', None), core_sha256=core_sha256) as unscoped:
            if (host._sequence, host.host_notification_counter, host.host_metadata_counter) != prior:
                raise RuntimeError('037A1BEE query changed queue or metadata state')
            flag, next_metadata = metadata_scope_transition(prior[1], prior[2])
            if struct.unpack_from('<I', unscoped, 72)[0] != 0:
                raise RuntimeError('037A1BEE legacy metadata is not source zero')
            record = bytearray(unscoped)
            struct.pack_into('<I', record, 72, flag)
            record = bytes(record)
            validate_empty_profile_record(record, **host.empty_receiver_state)
            host._enqueue(record)
            host.host_metadata_counter = next_metadata
        if (host._sequence, host.host_notification_counter, host.host_metadata_counter) != (prior[0] + 1, prior[1], next_metadata):
            raise RuntimeError('037A1BEE plot release changed queue or metadata state')
        host.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=host._sequence, notification_counter=prior[1], metadata_before=prior[2], metadata_after=next_metadata, metadata_flag=flag, source_proof_sha256=PROOF_SHA256, empty_receiver_state_verified=True, plot_released_after_enqueue=True, eligible_for_training=False)
        host.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(RECORDS[kind][0]), record_hex=record.hex(), pending_count=len(host.pending), native_optional_map_query_executed=optional_query, native_plot_queries_executed=True, optional_map_index=index, native_item_queries_executed=False, payload_exposed_to_learner=False, consumer_validated=False, eligible_for_training=False, native_dispatch_return=0)
        return 0
    except BaseException:
        host._found_city_poisoned = True
        raise
    finally:
        host._found_city_producing = False

"""Four counter-independent producers under the dedicated empty host profile.

This preserves the original encoders and their 0/4 metadata flags. It does not
infer a callback from a similar event and does not expose presentation payloads
to a learner. Nonempty receivers and optional host services remain refused.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_scalar_notification_scope.py')))).resolve().parents[1]
PROOF_SHA256 = 'f47c779f3aacec4197f6ef358d7f0069eb8ef62daa09a4684487d2f0dd569c35'
PROOF_PATH = ROOT / 'evidence/native-nonzero-scope-closure/notification-batch356' / (PROOF_SHA256 + '.json')
RECORDS = {529806097: (287, 96, 0), 1072344322: (179, 112, 4), 3209231784: (178, 112, 4), 2414808462: (288, 96, 0)}

def verify_source_evidence():
    proof = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_notification_scope_batch356.closed_profile.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['counter_contract']['native_nonzero_witness'] is not False or (proof['counter_contract']['metadata_flag_offset'] != '0x48'):
        raise RuntimeError('Scalar notification scope proof identity changed')
    profile = proof['closed_profile']
    if profile['normalizer_transform_present'] is not False or profile['per_thread_hook_present'] is not False or profile['writer_metadata_callback_present'] is not False or (profile['entity_listener_count'] != 0) or (profile['receiver_state_must_match_pinned_empty_row'] is not True):
        raise RuntimeError('Scalar notification closed profile changed')
    parents = proof['parents']
    for entry in (parents['event_registry'], parents['empty_receiver_manifest'], *parents['event_proofs'].values()):
        load_pinned_json(ROOT / entry['path'], entry['sha256'])
    events = proof['recaptured_source']['events']
    if set(events) != {hex(k) for k in RECORDS}:
        raise RuntimeError('Scalar scope event set changed')
    for kind, (record_type, size, flag) in RECORDS.items():
        event = events[hex(kind)]
        if event['record_type'] != hex(record_type) or event['record_size'] != hex(size) or event['metadata_flag'] != flag or event['direct_counter_builder_calls'] or event['F16D0_direct_calls'] or event['N_M_global_references'] or (event['empty_receiver_source']['record_type'] != hex(record_type)) or (event['empty_receiver_source']['record_size'] != hex(size)):
            raise RuntimeError('Scalar producer or receiver contract changed')
    return proof

def dispatch_scoped(host, kind, fields):
    verify_source_evidence()
    if type(kind) is not int or kind not in RECORDS:
        raise ValueError('Unknown scalar notification scope')
    host._require_no_f391_reentry()
    n, m, sequence = (host.host_notification_counter, host.host_metadata_counter, host._sequence)
    if any((type(v) is not int or not 0 <= v <= 4294967295 for v in (n, m))):
        raise ValueError('Scalar scope requires exact uint32 counters')
    if type(sequence) is not int or not 0 <= sequence < 2147483647:
        raise ValueError('Scalar notification sequence exhausted')
    if len(host.pending) >= host.limit:
        raise RuntimeError('Scalar notification queue bound exceeded')
    if type(host.entity_listener_count) is not int or host.entity_listener_count != 0:
        raise ValueError('Scalar scope requires empty entity listeners')
    record_type, size, flag = RECORDS[kind]
    shape = bytearray(size)
    struct.pack_into('<II', shape, 0, size, record_type)
    validate_empty_profile_record(shape, **host.empty_receiver_state)
    profile = dict(normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False)
    host._found_city_producing = True
    try:
        if kind == 529806097:
            from civ6_host.runtime.native.native_event_1f943311 import encode_record
            record = encode_record(sequence + 1, fields, host.read, **profile)
        elif kind == 1072344322:
            from civ6_host.runtime.native.native_event_3feaad02 import encode_record
            record = encode_record(sequence + 1, fields, **profile)
        elif kind == 3209231784:
            from civ6_host.runtime.native.native_event_bf48fda8 import encode_record
            record = encode_record(sequence + 1, fields, **profile)
        else:
            from civ6_host.runtime.native.native_event_8fef0d8e import encode_record
            record = encode_record(sequence + 1, fields, **profile, padding_policy='zero-unread-empty-receiver-payload', empty_receiver_state=host.empty_receiver_state)
        if (host.host_notification_counter, host.host_metadata_counter, host._sequence) != (n, m, sequence):
            raise RuntimeError('Scalar producer changed scope before enqueue')
        validate_empty_profile_record(record, **host.empty_receiver_state)
        if struct.unpack_from('<I', record, 72)[0] != flag:
            raise RuntimeError('Scalar producer metadata flag changed')
        host._enqueue(record)
        if (host.host_notification_counter, host.host_metadata_counter, host._sequence) != (n, m, sequence + 1):
            raise RuntimeError('Scalar producer changed scope during enqueue')
        host.emit('native_notification_metadata_transition', dispatch_kind=hex(kind), sequence=host._sequence, notification_counter=n, metadata_before=m, metadata_after=m, metadata_flag=flag, counter_independent_producer=True, source_proof_sha256=PROOF_SHA256, empty_receiver_state_verified=True, eligible_for_training=False)
        host.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(kind), queue_type=hex(record_type), record_hex=record.hex(), pending_count=len(host.pending), native_dispatch_return=0, source_proof_sha256=PROOF_SHA256, payload_exposed_to_learner=False, consumer_validated=False, undefined_value_is_native_default=False, eligible_for_training=False)
        return 0
    except BaseException:
        host._found_city_poisoned = True
        raise
    finally:
        host._found_city_producing = False

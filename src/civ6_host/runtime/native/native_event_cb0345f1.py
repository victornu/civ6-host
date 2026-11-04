"""UnitOperationSegmentComplete: source-identical A603 payload, distinct row45."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a60328c5 as sibling
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3405989361, 69, 112)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (sibling.SELECTOR_KEY, sibling.VALUE_KEY, sibling.SECOND_KEY, sibling.UNIT_KEY)
PROOF_SHA256 = '338d7be6f5364de6365f37fecc0b016f9a4092d9bc1ada3dd5f6a9ee904a17b2'
EventFields = sibling.EventFields
PADDING_POLICY = 'headless-zero-uninitialized-stack'

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('CB0345F1 complete source proof has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_cb0345f1.py')))).resolve().parents[1] / 'evidence/native-event-cb0345f1' / (PROOF_SHA256 + '.json')
    proof = load_pinned_json(path, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_cb0345f1.static.v1' or dict(proof['images']) != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}:
        raise RuntimeError('CB0345F1 source identity changed')
    sibling.verify_source_evidence()
    return proof

def decode_fields(fields, read):
    verify_source_evidence()
    return sibling.decode_fields(fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy=PADDING_POLICY, entity_listener_count, empty_receiver_state):
    verify_source_evidence()
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('CB0345F1 requires the actual empty entity-listener profile')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('CB0345F1 requires the complete empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(shape, **empty_receiver_state)
    record = bytearray(sibling.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

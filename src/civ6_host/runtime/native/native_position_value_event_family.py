"""Complete native position/DWORD callback family; fully initialized payload."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2980214136, 146, 96)
RECORD_TYPES = {2980214136: 146, 4152393721: 117, 330185301: 149}
CALLBACK_RVAS = {2980214136: 1347952, 4152393721: 1337360, 330185301: 1392416}
POSITION_KEY, SELECTOR_KEY, VALUE_KEY = (2353434172, 2716180809, 3606901732)
PROOF_SHA256 = '91d30e5e40b7a256eb979d9d832e9c83480bfd4b63a7f1fe5c4fd43a6dfa8b6a'

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('Position/value family source proof is not pinned')
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from civ6_host.runtime.native.native_deferred_empty_profile import POSITION_VALUE_RECEIVERS_SHA256
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_position_value_event_family.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-b1a27578' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_b1a27578.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['position_normalization']['sha256'] != 'd4d74903f64c7579fcece750f4d2d8323c0b8dd9c7cac35a32a87a58431365b1' or (proof['parents']['receivers']['sha256'] != POSITION_VALUE_RECEIVERS_SHA256) or (dict(proof['contract']['record_types']) != {hex(kind): value for kind, value in RECORD_TYPES.items()}) or (proof['contract']['record']['undefined_ranges'] != ()) or (proof['contract']['record']['payload_size'] != 16) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True) or (proof['complete_callback_family_scan']['permitted_difference_indices'] != (10, 27)) or (set(proof['complete_callback_family_scan']['matches']) != {hex(5368709120 + rva) for rva in CALLBACK_RVAS.values()}) or any((EXE_EVENT_CALLBACKS.get(kind) != rva for kind, rva in CALLBACK_RVAS.items())):
        raise RuntimeError('Position/value source identity changed')
    members = proof['members']
    if len(members) != 3 or {row['kind'] for row in members} != set(RECORD_TYPES):
        raise RuntimeError('Position/value complete family membership changed')
    for row in members:
        kind = row['kind']
        if row['callback_va'] != hex(5368709120 + CALLBACK_RVAS[kind]) or row['record_type'] != RECORD_TYPES[kind] or row['record_size'] != RECORD_SIZE or (row['writer_equal_after_only_header_type_normalization'] is not True) or (tuple((d['instruction_index'] for d in row['callback_differences'])) != (() if kind == EVENT_KIND else (10, 27))):
            raise RuntimeError('Position/value complete callback/writer equivalence changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    position_bytes: bytes
    x: int
    y: int
    selector: int
    value: int

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.position_bytes) is not bytes or len(fields.position_bytes) != 8 or (type(fields.x) is not int) or (type(fields.y) is not int) or (struct.unpack('<ii', fields.position_bytes) != (fields.x, fields.y)) or any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.value))):
        raise ValueError('Position/value fields need consistent coordinates and raw DWORDs')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != {POSITION_KEY, SELECTOR_KEY, VALUE_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Position/value family requires exactly three typed fields')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    fields = EventFields(position, *struct.unpack('<ii', position), selector, value)
    _fields(fields)
    return fields

def encode_record(kind, sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state):
    verify_source_evidence()
    if type(kind) is not int or kind not in RECORD_TYPES:
        raise ValueError('Unproved position/value callback kind')
    validate_sequence(sequence)
    _fields(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('Position/value callbacks require absent optional hooks/services')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Position/value callbacks require the closed empty observer profile')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('Position/value callbacks require the complete actual receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPES[kind], sequence, 0)
    validate_empty_profile_record(record, **empty_receiver_state)
    record[16:24] = b'\xff' * 8
    record[24:64] = bytes.fromhex('ffff0000ffffffff') * 5
    struct.pack_into('<I', record, 80, sequence)
    record[84:92] = fields.position_bytes
    struct.pack_into('<I', record, 92, fields.value)
    return bytes(record)

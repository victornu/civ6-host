"""Source-bounded DiplomacyRelationshipChanged producer, EXE144280.

The GameCore has already dispatched its internal effects before host+A0.
This module only constructs the deferred application record. Its three copied
stack-padding bytes may be zeroed only with the proven empty receiver.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3936998259, 137, 112)
SELECTOR_KEY, D6_KEY, A1FBC_KEY, BOOLEAN_KEY = (2716180809, 3606901732, 2717631346, 360746564)
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
PROOF_SHA256 = '9c08602b0dcef83158c261c025a7e9f4fde9085f16716197c479be0ae836dbea'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_eaa9d373.py')))).resolve().parents[1]

@dataclass(frozen=True)
class EventFields:
    selector: int
    d6_value: int
    a1fbc_value: int
    raw_boolean_byte: int

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('EAA9D373 source proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-eaa9d373' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof['contract']
    if proof.get('schema') != 'civ6rl.native_event_eaa9d373.static.v1' or proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['captures']['callback']['code_sha256'] != '7191c3deefa1bd4a6bcde53d1fe7fe0e9fe98671cc13c2430c1cdd3debcdea7a' or (proof['captures']['writer']['code_sha256'] != '74e92e5185fd5cb87bda83ad15fea2a12b7ddb5d76605101f7bd002224cb481a') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['registry']['registration']['callback_va'] != '0x140144280') or (contract['record_type'] != RECORD_TYPE) or (contract['record_size'] != RECORD_SIZE) or (contract['kind'] != EVENT_KIND) or (contract['flags'] != 0) or (set(contract['exact_keys']) != {SELECTOR_KEY, D6_KEY, A1FBC_KEY, BOOLEAN_KEY}) or (contract['tags'] != {'A1E5A149': 3, 'D6FCF3E4': 2, 'A1FBC372': 2, '15808E44': 1}) or (contract['payload'] != {'sequence_dword': 80, 'D6_dword': 84, 'A1FBC_dword': 88, 'selector_dword': 92, 'boolean_raw_byte': 96}) or (contract['undefined_record_ranges'] != ((97, 100),)) or (contract['padding_policy'] != PADDING_POLICY):
        raise RuntimeError('EAA9D373 source identity changed')
    return proof

def decode_fields(raw_fields):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, D6_KEY, A1FBC_KEY, BOOLEAN_KEY}:
        raise ValueError('EAA9D373 requires the exact four-key scalar envelope')
    raw = raw_fields[BOOLEAN_KEY]
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 1 or (struct.unpack_from('<I', raw, 20)[0] != 0):
        raise ValueError('EAA9D373 boolean requires direct tag1 with zero flags')
    return EventFields(decode_scalar(raw_fields[SELECTOR_KEY], 3), decode_scalar(raw_fields[D6_KEY], 2), decode_scalar(raw_fields[A1FBC_KEY], 2), raw[8])

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    if not isinstance(fields, EventFields):
        raise ValueError('EAA9D373 requires its decoded field profile')
    if any((type(v) is not int or not 0 <= v <= 4294967295 for v in (fields.selector, fields.d6_value, fields.a1fbc_value))):
        raise ValueError('EAA9D373 scalar values must preserve their DWORD bits')
    if type(fields.raw_boolean_byte) is not int or not 0 <= fields.raw_boolean_byte <= 255:
        raise ValueError('EAA9D373 boolean must preserve its raw byte')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('EAA9D373 sequence outside the admitted positive range')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('EAA9D373 transform/hook/metadata services are not admitted')
    if padding_policy != PADDING_POLICY:
        raise ValueError('EAA9D373 requires explicit unread stack-padding policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('EAA9D373 requires the complete empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    validate_empty_profile_record(record, **empty_receiver_state)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<IIII', record, 80, sequence, fields.d6_value, fields.a1fbc_value, fields.selector)
    record[96] = fields.raw_boolean_byte
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

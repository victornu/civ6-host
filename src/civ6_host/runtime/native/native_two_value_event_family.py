"""Conditionally encode the strict two-value EXE callback/writer family.

Admission requires the exact A1E5/D6FC(/A1FBC) field set and explicitly absent
optional callback and queue-metadata services. When A1FBC is absent, the
common native normalizer leaves its initialized DWORD zero. Only65C1D0A2 has
a native witness for that short shape; the other members are source-backed.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib, json
from pathlib import Path
from civ6_host.runtime.native.native_scalar_event_encoder import decode_core_fields as _decode
from civ6_host.runtime.native.native_scalar_event_encoder import encode_record as _encode
from civ6_host.runtime.native.native_scalar_event_encoder import _read_u32_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_PROOF_SHA256 = '0f0ba0cf89460ef782b9ceef5bf8e074042323c74cab55041983810f9c8eed60'
_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_two_value_event_family.py')))).resolve().parents[1] / 'evidence/native-two-value-event-family.json'
_raw = _resolve_resource_path(_PROOF_PATH).read_bytes()
if hashlib.sha256(_raw).hexdigest() != _PROOF_SHA256:
    raise RuntimeError('Two-value family proof hash mismatch')
_proof = json.loads(_raw)
if _proof.get('schema') != 'civ6rl.native_two_value_event_family.static.v1' or len(_proof.get('members', [])) != 25:
    raise RuntimeError('Two-value family proof incomplete')
MEMBERS = {int(row['kind'], 16): row for row in _proof['members']}
if len(MEMBERS) != 25 or any((row['record_size'] != '0x60' for row in MEMBERS.values())):
    raise RuntimeError('Two-value family member table invalid')
MISSING_B_PROOF_SHA256 = '82542c6f053560b0dbd0b9a8ad522d45d65cb88aa5abf7d410d2cb73651cda72'
_MISSING_B_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_two_value_event_family.py')))).resolve().parents[1] / 'evidence/native-two-value-event-missing-second' / (MISSING_B_PROOF_SHA256 + '.json')
_SHORT_KEYS = frozenset((2716180809, 3606901732))

def verify_missing_b_source_evidence():
    proof = load_pinned_json(_MISSING_B_PROOF_PATH, MISSING_B_PROOF_SHA256)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_two_value_event_missing_second.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['sources']['family']['sha256'] != _PROOF_SHA256) or (set(contract['admitted_kinds']) != set(MEMBERS)) or (len(contract['admitted_kinds']) != 25) or (set(contract['exact_short_keys']) != _SHORT_KEYS) or (contract['scalar_tags'] != {'A1E5A149': 3, 'D6FCF3E4': 2}) or (contract['selector_profile'] != 0) or (contract['scalar_flags'] != 0) or (contract['missing_key'] != 2717631346) or (contract['missing_second_value'] != 0) or (contract['record']['D6_offset'] != 84) or (contract['record']['second_offset'] != 88) or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['instruction_guards']['normalizer']['0x1401ca3b6'] != 'mov qword ptr [rbp + 0x17], r13') or (proof['instruction_guards']['normalizer']['0x1401ca6ec'] != 'mov dword ptr [rbp + 0x17], eax') or (proof['validation']['all_25_callback_writer_shapes_equal'] is not True):
        raise RuntimeError('Two-value missing-second source contract changed')

def decode_core_fields(event_kind: int, raw_fields: dict[int, bytes]) -> tuple[int, int, int]:
    if type(event_kind) is not int or event_kind not in MEMBERS:
        raise ValueError(f'Unknown two-value family kind: {event_kind!r}')
    if isinstance(raw_fields, dict) and set(raw_fields) == _SHORT_KEYS:
        verify_missing_b_source_evidence()
        selector = _read_u32_variant(raw_fields[2716180809], 3, 'selector')
        value_a = _read_u32_variant(raw_fields[3606901732], 2, 'value')
        value_b = 0
    else:
        selector, value_a, value_b = _decode(event_kind, raw_fields)
    if selector != 0:
        raise ValueError('Two-value family requires selector A1E5A149 == 0')
    return (selector, value_a, value_b)

def encode_core_fields(event_kind: int, sequence: int, raw_fields: dict[int, bytes], *, optional_callback_present: bool, queue_metadata_service_present: bool) -> bytes:
    if type(event_kind) is not int or event_kind not in MEMBERS:
        raise ValueError(f'Unknown two-value family kind: {event_kind!r}')
    if optional_callback_present is not False:
        raise ValueError('Optional callback hook must be explicitly absent')
    if queue_metadata_service_present is not False:
        raise ValueError('Queue-metadata service must be explicitly absent')
    _selector, value_a, value_b = decode_core_fields(event_kind, raw_fields)
    return _encode(event_kind, sequence, (value_a, value_b), queue_metadata=0)

def encode_values(event_kind: int, sequence: int, value_a: int, value_b: int, *, optional_callback_present: bool, queue_metadata_service_present: bool) -> bytes:
    if type(event_kind) is not int or event_kind not in MEMBERS:
        raise ValueError(f'Unknown two-value family kind: {event_kind!r}')
    if optional_callback_present is not False or queue_metadata_service_present is not False:
        raise ValueError('Both optional callback and queue-metadata services must be absent')
    return _encode(event_kind, sequence, (value_a, value_b), queue_metadata=0)

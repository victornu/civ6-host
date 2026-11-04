"""Generic encoder for statically qualified scalar callback/writer candidates.

The closed candidate set is tied to the generated, SHA-pinned static scan.
This module only constructs the native queue record; it does not claim dynamic
validation for every kind or model optional callback/metadata side effects.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType
_CANDIDATE_EVIDENCE_SHA256 = '783130b57f8f1dd03159ec3f0d96a0bcedd70d3e57f87d5208f86c22e22fd433'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_EVIDENCE = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_scalar_event_encoder.py')))).resolve().parents[1] / 'evidence' / 'native-scalar-event-callback-candidates.json'

def _load_catalog():
    raw = _resolve_resource_path(_EVIDENCE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _CANDIDATE_EVIDENCE_SHA256:
        raise RuntimeError('Scalar callback candidate evidence hash mismatch')
    data = json.loads(raw)
    if data.get('schema') != 'civ6rl.native_scalar_event_callback_candidates.v1' or data.get('image', {}).get('sha256') != _EXE_SHA256 or data.get('registry_source', {}).get('scanned_unique_kind_count') != 317 or (data.get('registry_source', {}).get('registered_unique_kind_count') != 317) or data.get('scan_errors') or (len(data.get('callback_matches', [])) != 38):
        raise RuntimeError('Scalar callback candidate scan is incomplete or changed')
    rows = {}
    for item in data['callback_matches']:
        kind = int(item['kind'], 16)
        if kind in rows:
            raise RuntimeError('Duplicate scalar callback candidate')
        if item['writer_record_size'] != '0x60':
            raise RuntimeError('Unexpected scalar writer record size')
        group_width = 3 if item['callback_shape_group'] == 'two_value_three_key' else 2
        if item.get('payload_value_count') != group_width - 1:
            raise RuntimeError('Callback and writer payload widths disagree')
        rows[kind] = item
    if len(rows) != 38:
        raise RuntimeError('Scalar callback candidate count changed')
    return (data, MappingProxyType(rows))
SCALAR_CANDIDATE_EVIDENCE, SCALAR_EVENT_CANDIDATES = _load_catalog()

def candidate_for(event_kind: int) -> dict:
    try:
        return SCALAR_EVENT_CANDIDATES[event_kind]
    except (KeyError, TypeError):
        raise ValueError(f'Unknown scalar event kind: {event_kind!r}') from None

def _read_u32_variant(raw, tag: int, label: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated scalar-event {label} variant')
    if struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError(f'Unverified scalar-event {label} tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'Unverified scalar-event {label} flags')
    return struct.unpack_from('<I', raw, 8)[0]

def _decode_profile_fields(row, raw_fields: dict[int, bytes]) -> tuple[int, ...]:
    """Decode only the proven A1E5/D6FC(/A1FBC) integer field profile."""
    three_keys = row['callback_shape_group'] == 'two_value_three_key'
    expected = {2716180809, 3606901732}
    if three_keys:
        expected.add(2717631346)
    if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
        raise ValueError('Unverified scalar-event Core argument keys')
    selector = _read_u32_variant(raw_fields[2716180809], 3, 'selector')
    values = [_read_u32_variant(raw_fields[3606901732], 2, 'value')]
    if three_keys:
        values.append(_read_u32_variant(raw_fields[2717631346], 2, 'value B'))
    return (selector, *values)

def decode_core_fields(event_kind: int, raw_fields: dict[int, bytes]) -> tuple[int, ...]:
    row = candidate_for(event_kind)
    return _decode_profile_fields(row, raw_fields)

def _encode_profile_record(row, sequence: int, values, *, queue_metadata: int=0) -> bytes:
    """Encode a 0x60 record using the candidate's proven writer type/layout.

    ``values`` contains payload DWORDs after the sequence slot. Metadata zero
    models an explicitly absent queue-metadata service in a headless profile.
    """
    expected_values = row['payload_value_count']
    if not isinstance(values, (tuple, list)) or len(values) != expected_values:
        raise ValueError(f'Expected {expected_values} scalar-event payload values')
    all_values = (sequence, *values, queue_metadata)
    if any((type(value) is not int or not 0 <= value <= 4294967295 for value in all_values)):
        raise ValueError('Scalar-event sequence, payload, and metadata must be uint32')
    if sequence == 0:
        raise ValueError('Scalar-event sequence must be nonzero')
    record_type = int(row['writer_record_type'], 16)
    record = bytearray(96)
    struct.pack_into('<IIII', record, 0, 96, record_type, sequence, queue_metadata)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHi', record, offset, 65535, 0, -1)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<' + 'I' * (1 + len(values)), record, 80, sequence, *values)
    return bytes(record)

def encode_record(event_kind: int, sequence: int, values, *, queue_metadata: int=0) -> bytes:
    row = candidate_for(event_kind)
    return _encode_profile_record(row, sequence, values, queue_metadata=queue_metadata)

def encode_core_fields(event_kind: int, sequence: int, raw_fields: dict[int, bytes], *, queue_metadata: int=0) -> bytes:
    decoded = decode_core_fields(event_kind, raw_fields)
    return encode_record(event_kind, sequence, decoded[1:], queue_metadata=queue_metadata)

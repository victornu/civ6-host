"""The standard-record half of the source-verified 66ADE3B3 dual producer.

The caller must also append its value to the shared private ring after this
standard record, as EXE154540 does. Encoding alone is not the full callback.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1722672051, 5, 96)
PRIVATE_RECORD_TYPE, PRIVATE_RECORD_SIZE = (87, 128)
SELECTOR_KEY, VALUE_KEY = (2716180809, 3606901732)
_PROOF_SHA = '3daeb6be868940d75adf9df0f2b3a933a888c26de350c95599ddce5a6f0c15f5'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_66ade3b3.py')))).resolve().parents[1] / 'evidence/native-event-66ade3b3' / f'{_PROOF_SHA}.json'

def verify_source_evidence() -> None:
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA:
        raise RuntimeError('Pinned 66ADE3B3 evidence changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_event_66ade3b3.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x140154540' or (proof['captures']['callback']['raw_sha256'] != '0688f5631c310ee7d40a10a064a9495ad3dc753b6768fc86a5756af38379f85d') or (proof['private_allocator']['reachable_bytes_sha256'] != '7f90e55b3b15fd3db468fb60d9fc51024bc9f2913d3b355d83c72c0901191bdf'):
        raise RuntimeError('Pinned 66ADE3B3 source identity changed')

def decode_fields(fields: dict[int, bytes]) -> dict[str, int]:
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, VALUE_KEY}:
        raise ValueError('Unverified 66ADE3B3 input fields')
    if any((not isinstance(raw, (bytes, bytearray, memoryview)) for raw in fields.values())):
        raise ValueError('Unverified 66ADE3B3 scalar bytes')
    return {'selector': decode_scalar(fields[SELECTOR_KEY], 3), 'value': decode_scalar(fields[VALUE_KEY], 2)}

def encode_record(sequence: int, fields: dict[int, bytes], *, thread_hook_present: bool, writer_metadata_callback_present: bool) -> bytes:
    """Encode the first producer only: type5, metadata flag6, sequence/value."""
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('66ADE3B3 registered native callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('66ADE3B3 sequence must be a bounded positive integer')
    value = decode_fields(fields)['value']
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 72, 6)
    struct.pack_into('<II', record, 80, sequence, value)
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'PRIVATE_RECORD_TYPE', 'PRIVATE_RECORD_SIZE', 'decode_fields', 'encode_record', 'verify_source_evidence']

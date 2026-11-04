"""Source-scoped queue encoder for EXE event callback 0x6E63A083.

The captured callback does not read its Core argument descriptor. It builds a
local zero DWORD, optionally passes its address to a per-thread receiver /
function pair, then writes a type-9 ring record. This adapter supports only
the explicit no-hook/no-queue-hook host profile.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import struct
EVENT_KIND = 1852022915
CALLBACK_RVA = 1349760
QUEUE_WRITER_RVA = 1173296
RECORD_TYPE = 9
RECORD_SIZE = 96
_EVIDENCE_SHA256 = '2ee1f5156b292c30856f26c098040d49103ba2820794903fc3362d1a11e19537'
_EVIDENCE_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_6e63a083.py')))).resolve().parents[1] / 'evidence' / 'native-event-6e63a083' / f'{_EVIDENCE_SHA256}.json'

def verify_source_pin() -> None:
    if not _EVIDENCE_SHA256:
        raise RuntimeError('0x6E63A083 immutable evidence pin is not configured')
    raw = _resolve_resource_path(_EVIDENCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _EVIDENCE_SHA256:
        raise RuntimeError('Pinned 0x6E63A083 source evidence changed')
    report = json.loads(raw)
    if report.get('schema') != 'civ6rl.native_event_6e63a083.static.v1' or report.get('event_kind') != '0x6e63a083' or report.get('callback_va') != '0x140149880':
        raise RuntimeError('Pinned 0x6E63A083 source evidence contract mismatch')

def _variant(raw: bytes, tag: int, name: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated 0x6E63A083 {name} variant')
    if struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError(f'Unverified 0x6E63A083 {name} tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'Unverified 0x6E63A083 {name} flags')
    return struct.unpack_from('<I', raw, 8)[0]

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    """Decode the witnessed two-field shape; callback ignores both values."""
    expected = {2716180809, 3606901732}
    if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
        raise ValueError('Unverified 0x6E63A083 Core argument keys')
    selector = _variant(raw_fields[2716180809], 3, 'selector')
    value = _variant(raw_fields[3606901732], 2, 'value')
    return {'selector': selector, 'value': value}

def encode_6e63a083_record(sequence: int, *, optional_callback_present: bool=False, queue_hook_present: bool=False, queue_metadata: int=0) -> bytes:
    """Build the exact 0x60-byte type-9 queue record for the null-hook path.

    The callback passes a pointer to a local DWORD initialized to zero. The
    writer copies a QWORD from that pointer; its high DWORD is uninitialized
    stack padding, so this host deterministically zero-fills it. The writer
    replaces the low payload DWORD with the incremented sequence.
    """
    verify_source_pin()
    if optional_callback_present is not False:
        raise ValueError('0x6E63A083 optional per-thread callback is not implemented')
    if queue_hook_present is not False:
        raise ValueError('0x6E63A083 optional queue hook is not implemented')
    for label, item in (('sequence', sequence), ('queue metadata', queue_metadata)):
        if type(item) is not int or not 0 <= item <= 4294967295:
            raise ValueError(f'Invalid 0x6E63A083 {label}')
    if sequence == 0:
        raise ValueError('0x6E63A083 sequence must be nonzero')
    if queue_metadata != 0:
        raise ValueError('0x6E63A083 nonzero queue metadata requires the queue hook')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    for offset in (16, 20, 28, 36, 44, 52, 60):
        struct.pack_into('<I', record, offset, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<H', record, offset, 65535)
    for offset in (26, 34, 42, 50, 58):
        struct.pack_into('<H', record, offset, 0)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 6)
    struct.pack_into('<II', record, 80, sequence, 0)
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_RVA', 'QUEUE_WRITER_RVA', 'decode_fields', 'encode_6e63a083_record', 'verify_source_pin']

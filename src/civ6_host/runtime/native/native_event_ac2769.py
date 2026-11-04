"""Source-backed encoder for Core event kind 0xAC2769A3.

The static contract is proven from the pinned Core wrapper/caller and EXE
callback/writer. Dynamic event-value validation is still pending.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
EVENT_KIND = 2888264099
CALLBACK_RVA = 1321728
QUEUE_WRITER_RVA = 1279424
RECORD_SIZE = 96
RECORD_TYPE = 191

def _typed_u32(raw, tag: int, name: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated AC2769A3 {name} variant')
    if struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError(f'Unverified AC2769A3 {name} tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'Unverified AC2769A3 {name} flags')
    return struct.unpack_from('<I', raw, 8)[0]

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    """Decode the two-key A0 contract (selector and value are uint32)."""
    expected = {2716180809, 3606901732}
    if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
        raise ValueError('Unverified AC2769A3 Core argument keys')
    return {'selector': _typed_u32(raw_fields[2716180809], 3, 'selector'), 'value': _typed_u32(raw_fields[3606901732], 2, 'value')}

def encode_ac2769a3_record(sequence: int, value: int, *, queue_metadata: int=0) -> bytes:
    for name, item in (('sequence', sequence), ('value', value), ('queue metadata', queue_metadata)):
        if type(item) is not int or not 0 <= item <= 4294967295:
            raise ValueError(f'Invalid AC2769A3 {name}')
    if sequence == 0:
        raise ValueError('AC2769A3 sequence must be nonzero')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHi', record, offset, 65535, 0, -1)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<II', record, 80, sequence, value)
    return bytes(record)

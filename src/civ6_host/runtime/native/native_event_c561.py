"""Source-scoped encoder for Core event kind 0xC5613042."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
EVENT_KIND = 3311480898
CALLBACK_RVA = 1321296
QUEUE_WRITER_RVA = 1279088
RECORD_SIZE = 96
RECORD_TYPE = 190

def _typed_u32(raw, tag: int, name: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated C5613042 {name} variant')
    if struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError(f'Unverified C5613042 {name} tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'Unverified C5613042 {name} flags')
    return struct.unpack_from('<I', raw, 8)[0]

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    expected = {2716180809, 3606901732, 2717631346}
    if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
        raise ValueError('Unverified C5613042 Core argument keys')
    selector = _typed_u32(raw_fields[2716180809], 3, 'selector')
    value_a = _typed_u32(raw_fields[3606901732], 2, 'value A')
    value_b = _typed_u32(raw_fields[2717631346], 2, 'value B')
    if selector != 0:
        raise ValueError('Unverified C5613042 selector profile')
    return {'selector': selector, 'value_a': value_a, 'value_b': value_b}

def encode_c5613042_record(sequence: int, value_a: int, value_b: int, *, queue_metadata: int=0) -> bytes:
    for name, value in (('sequence', sequence), ('value A', value_a), ('value B', value_b), ('queue metadata', queue_metadata)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Invalid C5613042 {name}')
    if sequence == 0:
        raise ValueError('C5613042 sequence must be nonzero')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHi', record, offset, 65535, 0, -1)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<III', record, 80, sequence, value_a, value_b)
    return bytes(record)

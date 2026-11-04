"""Source-scoped encoder for the EXE D35E571D deferred-event callback."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
EVENT_KIND = 3546175261
CALLBACK_RVA = 1348640
QUEUE_WRITER_RVA = 1287216
RECORD_SIZE = 96
RECORD_TYPE = 209
CALLBACK_OBJECT_MAGIC = 1682424637

def _typed_u32(raw, expected_tag: int, label: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated D35E571D {label} variant')
    if struct.unpack_from('<H', raw)[0] != expected_tag:
        raise ValueError(f'Unverified D35E571D {label} variant tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError(f'Unverified D35E571D {label} variant flags')
    return struct.unpack_from('<I', raw, 8)[0]

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    """Normalize the exact two Core tree values consumed by EXE 1CA2D0."""
    if not isinstance(raw_fields, dict) or set(raw_fields) != {2716180809, 3606901732}:
        raise ValueError('Unverified D35E571D Core argument keys')
    selector = _typed_u32(raw_fields[2716180809], 3, 'selector')
    callback_value = _typed_u32(raw_fields[3606901732], 2, 'callback value')
    if selector != 0:
        raise ValueError('Unverified D35E571D selector')
    return {'selector': selector, 'callback_value': callback_value}

def encode_d35e571d_record(sequence: int, callback_value: int, *, queue_metadata: int=0) -> bytes:
    """Encode the 0xD1 / 0x60 ring record written by EXE 13A430.

    `queue_metadata=0` models the diagnostic host profile with no registered
    queue metadata service. Bytes not initialized by the native writer are
    zeroed explicitly, matching the host's established unspecified-padding
    policy; they are not represented as native semantic fields.
    """
    for name, value in (('sequence', sequence), ('callback value', callback_value), ('queue metadata', queue_metadata)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Invalid D35E571D {name}')
    if sequence == 0:
        raise ValueError('D35E571D sequence must be nonzero')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHi', record, offset, 65535, 0, -1)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<II', record, 80, sequence, callback_value)
    return bytes(record)

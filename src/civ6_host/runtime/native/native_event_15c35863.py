"""Source-derived UnitOperationAdded fields and an explicit no-hook record.

The deferred receiver is verified separately; copied stack padding is an
explicit headless allocation choice, not a claimed native stack observation.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from dataclasses import dataclass
KIND = 365123683
SELECTOR_KEY = 2716180809
VALUE_KEY = 3606901732
BLOB_KEY = 4032072631
BLOB_FLAGS = 553648129
VARIANT_SIZE = 24
RECORD_SIZE = 112
RECORD_TYPE = 67

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    blob_pointer: int
    blob_bytes: bytes | None = None

def _u32(n: int, label: str) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or (not 0 <= n <= 4294967295):
        raise ValueError(f'{label} must be an unsigned 32-bit integer')
    return n

def encode_scalar(tag: int, value: int) -> bytes:
    if tag not in (2, 3):
        raise ValueError('only observed integer tags 2 and 3 are supported')
    _u32(value, 'value')
    return struct.pack('<I4xQII', tag, value, 0, 0)

def decode_scalar(raw: bytes, expected_tag: int) -> int:
    if len(raw) != VARIANT_SIZE:
        raise ValueError('variant must be exactly 24 bytes')
    tag, = struct.unpack_from('<H', raw)
    if tag != expected_tag or expected_tag not in (2, 3):
        raise ValueError('unexpected scalar variant tag')
    value, = struct.unpack_from('<I', raw, 8)
    flags, = struct.unpack_from('<I', raw, 20)
    if flags != 0:
        raise ValueError('scalar variant has unsupported ownership flags')
    return int(value)

def encode_blob_pointer(pointer: int) -> bytes:
    if isinstance(pointer, bool) or not isinstance(pointer, int) or (not 0 < pointer <= 18446744073709551615):
        raise ValueError('blob pointer must be a nonzero 64-bit address')
    return struct.pack('<I4xQII', 1024, pointer, 8, BLOB_FLAGS)

def decode_blob_pointer(raw: bytes) -> int:
    if len(raw) != VARIANT_SIZE:
        raise ValueError('variant must be exactly 24 bytes')
    tag, = struct.unpack_from('<H', raw)
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 1024 or not pointer or size != 8 or (flags != BLOB_FLAGS):
        raise ValueError('blob variant does not match observed 8-byte Core descriptor')
    return pointer

def decode_core_blob(raw: bytes) -> tuple[int, int, int]:
    """Decode the Core producer's 8-byte descriptor: owner, source type, entity id."""
    if len(raw) != 8:
        raise ValueError('Core blob must be exactly 8 bytes')
    owner, source_type, entity_id = struct.unpack('<HHI', raw)
    if source_type != 1:
        raise ValueError('only producer-proven source type 1 is supported')
    return (owner, source_type, entity_id)

def encode_fields(fields: EventFields) -> dict[int, bytes]:
    return {SELECTOR_KEY: encode_scalar(3, _u32(fields.selector, 'selector')), VALUE_KEY: encode_scalar(2, _u32(fields.value, 'value')), BLOB_KEY: encode_blob_pointer(fields.blob_pointer)}

def decode_fields(fields: dict[int, bytes], *, blob_contents: bytes | None=None) -> EventFields:
    if set(fields) != {SELECTOR_KEY, VALUE_KEY, BLOB_KEY}:
        raise ValueError('event field set must match the three proven Core fields exactly')
    pointer = decode_blob_pointer(fields[BLOB_KEY])
    if blob_contents is not None:
        decode_core_blob(blob_contents)
    return EventFields(selector=decode_scalar(fields[SELECTOR_KEY], 3), value=decode_scalar(fields[VALUE_KEY], 2), blob_pointer=pointer, blob_bytes=blob_contents)

def encode_queue_record(sequence: int, fields: dict[int, bytes], *, blob_contents: bytes, queue_metadata: int=0, hook_present: bool=False, padding_policy: str) -> bytes:
    """Encode the 0x14012C700 ring record for the explicit no-hook profile.

    The source copies an uninitialized DWORD at record+0x54 and leaves +0x4c..
    +0x4f and +0x68..+0x6f unwritten. This function requires the caller to opt
    into deterministic zero initialization for those bytes; it does not claim
    that stack DWORD matches an unobserved native stack value. The optional callback
    hook is rejected because its side effects are not modeled.
    """
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if type(queue_metadata) is not int or not 0 <= queue_metadata <= 4294967295:
        raise ValueError('queue_metadata must be uint32')
    if hook_present:
        raise ValueError('callback hook side effects are unsupported')
    if padding_policy != 'headless-zero-initialization':
        raise ValueError('explicit headless zero-padding policy is required')
    parsed = decode_fields(fields, blob_contents=blob_contents)
    owner, source_type, entity_id = decode_core_blob(blob_contents)
    if source_type != 1:
        raise ValueError('only the source-proven descriptor type 1 is supported')
    metadata = bytearray(60)
    struct.pack_into('<IIHHI', metadata, 0, 4294967295, 4294967295, owner, source_type, entity_id)
    for off in (16, 24, 32, 40):
        struct.pack_into('<HHI', metadata, off, 65535, 0, 4294967295)
    struct.pack_into('<Q', metadata, 48, 0)
    struct.pack_into('<I', metadata, 56, 0)
    payload = bytearray(24)
    struct.pack_into('<I', payload, 4, 0)
    struct.pack_into('<HHI', payload, 8, owner, source_type, entity_id)
    struct.pack_into('<II', payload, 16, parsed.selector, parsed.value)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    record[16:76] = metadata[:60]
    record[68:72] = b'\x00' * 4
    struct.pack_into('<I', record, 80, sequence)
    record[84:104] = payload[4:24]
    return bytes(record)

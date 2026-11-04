"""Source-scoped no-hook adapter for event 0x11C07B90."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
EVENT_KIND = 297827216
CALLBACK_RVA = 1349536
QUEUE_WRITER_RVA = 1172800
RECORD_TYPE = 8
RECORD_SIZE = 96

def _variant(raw, tag: int, name: str) -> int:
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError(f'Truncated 0x11C07B90 {name} variant')
    view = memoryview(raw).cast('B')
    if struct.unpack_from('<H', view)[0] != tag:
        raise ValueError(f'Unverified 0x11C07B90 {name} tag')
    if struct.unpack_from('<I', view, 20)[0] != 0:
        raise ValueError(f'Unverified 0x11C07B90 {name} flags')
    return struct.unpack_from('<I', view, 8)[0]

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    expected = {2716180809, 3606901732}
    if not isinstance(raw_fields, dict) or set(raw_fields) != expected:
        raise ValueError('Unverified 0x11C07B90 Core argument keys')
    selector = _variant(raw_fields[2716180809], 3, 'selector')
    value = _variant(raw_fields[3606901732], 2, 'value')
    if selector != 0:
        raise ValueError('Unverified 0x11C07B90 selector')
    return {'selector': selector, 'value': value}

def encode_11c07b90_record(sequence: int, *, selector: int=0, optional_callback_present: bool=False, queue_hook_present: bool=False, queue_metadata: int=0) -> bytes:
    """Encode the type-8 record for the explicit empty-hook profile.

    The callback initializes metadata at stack ``rbp-0x40``, passes a local
    payload whose low DWORD is zero, and the queue writer replaces that low
    DWORD with the sequence. The callback leaves the payload's upper DWORD as
    stack padding; this encoder zeroes it because the proven row-8 empty path
    never reads record payload.
    """
    if optional_callback_present is not False:
        raise ValueError('0x11C07B90 per-thread callback hook is not implemented')
    if queue_hook_present is not False:
        raise ValueError('0x11C07B90 queue hook is not implemented')
    for label, item in (('sequence', sequence), ('selector', selector), ('queue metadata', queue_metadata)):
        if type(item) is not int or not 0 <= item <= 4294967295:
            raise ValueError(f'Invalid 0x11C07B90 {label}')
    if sequence == 0:
        raise ValueError('0x11C07B90 sequence must be nonzero')
    if selector != 0:
        raise ValueError('Unverified 0x11C07B90 selector')
    if queue_metadata != 0:
        raise ValueError('0x11C07B90 absent queue hook must return zero metadata')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    for offset in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', record, 16 + offset, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<H', record, 16 + offset, 65535)
    for offset in (10, 18, 26, 34, 42):
        struct.pack_into('<H', record, 16 + offset, 0)
    struct.pack_into('<Q', record, 16 + 48, 0)
    struct.pack_into('<I', record, 16 + 56, 6)
    struct.pack_into('<II', record, 80, sequence, 0)
    return bytes(record)

def encode_fields(raw_fields: dict[int, bytes], sequence: int, **kwargs) -> bytes:
    fields = decode_fields(raw_fields)
    return encode_11c07b90_record(sequence, selector=fields['selector'], **kwargs)

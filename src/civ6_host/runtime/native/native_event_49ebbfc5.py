"""Source-scoped adapter for event kind 0x49EBBFC5.

The callback has an optional per-thread hook before its queue append. The
encoder only represents the explicit no-hook/no-queue-hook host profile; it
does not claim that the graphical EXE's hook tables are empty.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
EVENT_KIND = 1240186821
CALLBACK_RVA = 1346224
QUEUE_WRITER_RVA = 1290144
RECORD_TYPE = 218
RECORD_SIZE = 96

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    """Accept only the observed one-field Core descriptor, selector=0."""
    if not isinstance(raw_fields, dict) or set(raw_fields) != {2716180809}:
        raise ValueError('Unverified 0x49EBBFC5 Core argument keys')
    raw = raw_fields[2716180809]
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Truncated 0x49EBBFC5 selector variant')
    if struct.unpack_from('<H', raw)[0] != 3:
        raise ValueError('Unverified 0x49EBBFC5 selector tag')
    if struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError('Unverified 0x49EBBFC5 selector flags')
    selector = struct.unpack_from('<I', raw, 8)[0]
    if selector != 0:
        raise ValueError('Unverified 0x49EBBFC5 selector value')
    return {'selector': selector}

def encode_49ebbfc5_record(sequence: int, selector: int, *, optional_callback_present: bool=False, queue_hook_present: bool=False, queue_metadata: int=0) -> bytes:
    """Encode the statically sourced 0xDA/0x60 writer path.

    The EXE copies eight bytes from a local where only the low DWORD is
    initialized by the callback, and overwrites that low DWORD with sequence.
    The upper DWORD is therefore unspecified stack data. This host explicitly
    zero-fills it as padding; it is not presented as a native value.
    """
    if optional_callback_present is not False:
        raise ValueError('0x49EBBFC5 optional per-thread callback is not implemented')
    if queue_hook_present is not False:
        raise ValueError('0x49EBBFC5 optional queue hook is not implemented')
    for label, value in (('sequence', sequence), ('selector', selector), ('queue metadata', queue_metadata)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Invalid 0x49EBBFC5 {label}')
    if sequence == 0:
        raise ValueError('0x49EBBFC5 sequence must be nonzero')
    if selector != 0:
        raise ValueError('Unverified 0x49EBBFC5 selector value')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, queue_metadata)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHi', record, offset, 65535, 0, -1)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<II', record, 80, sequence, 0)
    return bytes(record)

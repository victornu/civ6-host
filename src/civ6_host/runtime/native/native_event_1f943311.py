"""Pinned 1F943311 producer: copy one eight-byte value to a type11F record.

The callback does not query or modify GameCore state. This is the explicit
absent-transform/absent-hook/absent-writer-service profile; queue ownership and
receiver validation remain the dispatcher's responsibility.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (529806097, 287, 96)
BLOB_KEY, SELECTOR_KEY = (2353434172, 2716180809)
PROOF_SHA256 = 'f500e8f3419aa3c52d5b40de7bde9ec65c241efadfdf9600016a7958b4e1ad39'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_1f943311.py')))).resolve().parents[1] / 'evidence/native-event-1f943311' / f'{PROOF_SHA256}.json'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_1f943311.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x14014c5c0' or (proof['registration']['kind'] != '0x1f943311') or (proof['captures']['callback']['raw_sha256'] != '6088ec1a28722bc76b7cbb3df01da22e47c55f4350c68a83a11ee19dab04ff6b') or (proof['captures']['writer']['raw_sha256'] != '8bb4668cb8db602acdec41b5ba4dcfc1e485796cdfef74df5f4870bf4f06fd9f') or (proof['captures']['normalizer']['raw_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned 1F943311 callback/writer/normalizer identity changed')

def _variant(raw, name: str) -> bytes:
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise ValueError(f'1F943311 {name} variant must contain bytes')
    value = bytes(raw)
    if len(value) != 24:
        raise ValueError(f'Incomplete 1F943311 {name} variant')
    return value

def decode_fields(fields: dict[int, bytes], read) -> dict:
    """Own a copy of the eight pointed bytes; their semantic meaning is unused."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
        raise ValueError('Unverified 1F943311 input fields')
    selector = decode_scalar(_variant(fields[SELECTOR_KEY], 'selector'), 3)
    raw = _variant(fields[BLOB_KEY], 'blob')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 0 or not 0 < pointer <= (1 << 63) - 8 or size != 8 or (flags != 553648129):
        raise ValueError('Unverified 1F943311 blob envelope')
    value = read(pointer, 8)
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError('Incomplete 1F943311 pointed value')
    value = bytes(value)
    if len(value) != 8:
        raise ValueError('Incomplete 1F943311 pointed value')
    return {'blob_bytes': value, 'selector': selector}

def encode_record(sequence: int, fields: dict[int, bytes], read, *, normalizer_transform_present: bool=False, thread_hook_present: bool, writer_metadata_callback_present: bool) -> bytes:
    """Encode initialized native metadata and payload with one checked copy.

    The writer creates metadata without the notification counter and zeroes
    allocation gaps. The source payload is DWORD0 followed by the raw QWORD;
    its first DWORD is replaced by the sequence at record+0x50.
    """
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('1F943311 registered native transforms/callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('1F943311 sequence must be a bounded positive integer')
    values = decode_fields(fields, read)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    record[84:92] = values['blob_bytes']
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'PROOF_SHA256', 'BLOB_KEY', 'SELECTOR_KEY', 'decode_fields', 'encode_record', 'verify_source_evidence']

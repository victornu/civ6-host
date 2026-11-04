"""Source-backed F26F3ACF producer with a copied typed entity identifier."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4067375823, 256, 96)
BLOB_KEY, SELECTOR_KEY = (3937836634, 2716180809)
_PROOF_SHA = '628f4fde76c45c92c5ecf5c3c19165b6909f36314a07a62ebb5249c6b92c073c'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f26f3acf.py')))).resolve().parents[1] / 'evidence/native-event-f26f3acf' / f'{_PROOF_SHA}.json'

def verify_source_evidence() -> None:
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA:
        raise RuntimeError('Pinned F26F3ACF evidence changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_event_f26f3acf.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x14014a380' or (proof['captures']['callback']['raw_sha256'] != 'fdbdd71ba1df2e42b56db9e284c1f82aef9ea4513fe316b57972a06fb55604eb') or (proof['captures']['writer']['raw_sha256'] != '496482ef7eea189800ebcec241400733b7ec69388b78e4150c26881d29f204b5'):
        raise RuntimeError('Pinned F26F3ACF callback/writer identity changed')

def decode_fields(fields: dict[int, bytes], read) -> dict:
    """Copy all eight live identifier bytes; the source type is not normalized."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
        raise ValueError('Unverified F26F3ACF input fields')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    raw = fields[BLOB_KEY]
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Incomplete F26F3ACF blob variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 1024 or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Unverified F26F3ACF blob envelope')
    value = read(pointer, 8)
    if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 8:
        raise ValueError('Incomplete F26F3ACF pointed value')
    owner, source_type, identifier = struct.unpack('<HHI', value)
    return {'entity_bytes': bytes(value), 'owner': owner, 'source_type': source_type, 'identifier': identifier, 'selector': selector}

def encode_record(sequence: int, fields: dict[int, bytes], read, *, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str) -> bytes:
    """Encode the source metadata flag4 and copied16-byte payload.

    This callback does not query Core or read the notification counter. Its
    copied stack padding DWORD has no defined source value; zeroing requires
    the explicit diagnostic policy. The native allocation zeroes the gap.
    """
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('F26F3ACF registered native callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('F26F3ACF sequence must be a bounded positive integer')
    if padding_policy != 'zero':
        raise ValueError('F26F3ACF requires the explicit zero padding policy')
    values = decode_fields(fields, read)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 72, 4)
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = values['entity_bytes']
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'decode_fields', 'encode_record', 'verify_source_evidence']

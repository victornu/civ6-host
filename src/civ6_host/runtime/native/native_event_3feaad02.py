"""Source-bounded scalar record codec for EXE event 0x3FEAAD02.

This encodes the callback/writer record shape only. It does not dispatch the
Core event, model receiver behavior, or interpret any scalar's gameplay meaning.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 1072344322
CALLBACK_VA = '0x140142830'
WRITER_VA = '0x140137440'
RECORD_TYPE = 179
RECORD_SIZE = 112
SELECTOR_KEY = 2716180809
D6_KEY = 3606901732
A1FBC_KEY = 2717631346
VALUE_38F_KEY = 955421384
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CALLBACK_CODE_SHA256 = 'f24a2b3feddfe153b40cfbdf08c956f8a07fa59862d77e55d2e2278447f8692c'
WRITER_CODE_SHA256 = '1a67a9e7f78b318c423bc6629d667d4436a052ee134a7c9d9f9ab1a93515c1dc'
PINNED_EVIDENCE_SHA256 = '8d182878e54fb9ec59aaf5d9b529e1e17d990d143659d83049954b7a18eacc15'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_3feaad02.py')))).resolve().parents[1] / 'evidence/native-event-3feaad02' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    captures = proof.get('captures', {})
    registration = proof.get('registration', {})
    if proof.get('schema') != 'civ6rl.native_event_3feaad02.static.v1' or proof.get('exe_sha256') != EXE_SHA256 or registration.get('kind') != '0x3feaad02' or (registration.get('callback_va') != CALLBACK_VA) or (captures.get('callback', {}).get('raw_sha256') != CALLBACK_CODE_SHA256) or (captures.get('writer', {}).get('raw_sha256') != WRITER_CODE_SHA256) or (captures.get('normalizer', {}).get('raw_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('Pinned 3FEAAD02 source identity changed')

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    """Decode exactly four 24-byte scalar variants with their native tags."""
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, D6_KEY, A1FBC_KEY, VALUE_38F_KEY}:
        raise ValueError('3FEAAD02 requires exactly A1E5A149, D6FCF3E4, A1FBC372 and 38F292C8')
    return {'selector': decode_scalar(raw_fields[SELECTOR_KEY], 3), 'd6_value': decode_scalar(raw_fields[D6_KEY], 2), 'a1fbc_value': decode_scalar(raw_fields[A1FBC_KEY], 2), 'value_38f': decode_scalar(raw_fields[VALUE_38F_KEY], 2)}

def encode_record(sequence: int, raw_fields: dict[int, bytes], *, normalizer_transform_present: bool=False, thread_hook_present: bool, writer_metadata_callback_present: bool) -> bytes:
    """Encode the exact 0x70/B3 record for the four-key, no-hook profile."""
    verify_source_evidence()
    fields = decode_fields(raw_fields)
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('3FEAAD02 sequence must be in 1..0x7fffffff')
    if normalizer_transform_present is not False:
        raise ValueError('3FEAAD02 normalizer transform path is unsupported')
    if thread_hook_present is not False:
        raise ValueError('3FEAAD02 thread hook path is unsupported')
    if writer_metadata_callback_present is not False:
        raise ValueError('3FEAAD02 writer metadata callback path is unsupported')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    for offset in (0, 4, 12, 20, 28, 36, 44):
        struct.pack_into('<I', record, 16 + offset, 4294967295)
    for offset in (8, 16, 24, 32, 40):
        struct.pack_into('<H', record, 16 + offset, 65535)
    for offset in (10, 18, 26, 34, 42):
        struct.pack_into('<H', record, 16 + offset, 0)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 4)
    struct.pack_into('<IIIII', record, 80, sequence, fields['d6_value'], fields['selector'], fields['a1fbc_value'], fields['value_38f'])
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_VA', 'WRITER_VA', 'RECORD_TYPE', 'RECORD_SIZE', 'SELECTOR_KEY', 'D6_KEY', 'A1FBC_KEY', 'VALUE_38F_KEY', 'decode_fields', 'encode_record', 'verify_source_evidence']

"""Source-backed eight-byte blob producer for host event265857F7."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (643323895, 141, 96)
BLOB_KEY, SELECTOR_KEY = (2353434172, 2716180809)
IGNORED_ARGUMENT_KEY = 1959145256
_PROOF_SHA = 'e322fd9efee018d03a9c0f1b0951dae3c2930bd66f5e71fa1444b15d1d707793'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_265857f7.py')))).resolve().parents[1] / 'evidence/native-event-265857f7' / f'{_PROOF_SHA}.json'
VARIANT_PROOF_SHA256 = '6d60d999c79f3a10893c65ef71841739e663ab6447a97572fe74f57114bf3027'
_VARIANT_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_265857f7.py')))).resolve().parents[1] / 'evidence/native-event-265857f7-variant246.json'

def verify_source_evidence() -> None:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_PROOF, _PROOF_SHA)
    if proof.get('schema') != 'civ6rl.native_event_265857f7.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x140152260' or (proof['captures']['callback']['raw_sha256'] != '792ca3d269f094a9fa2cae697cafe2e5ae722c9fa1163d7aa4caf94010d2b129') or (proof['captures']['writer']['raw_sha256'] != 'b892d67b16c137dbf3ee4f4d95cf7d5edf82cd8ec2d8b76c245efa06a47e87d4'):
        raise RuntimeError('Pinned265857F7 callback/writer identity changed')

def verify_variant_source_evidence() -> None:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_VARIANT_PROOF, VARIANT_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_265857f7.variant246.static.v1' or proof['base_proof']['sha256'] != _PROOF_SHA or proof['images']['core']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['images']['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63') or (proof['normalizer_branch_proof']['ignored_key'] != '0x74c62f28') or (proof['captures']['core_producer']['raw_sha256'] != 'e243e9772865bc3bfe36f59ba2a787d0aaf9ea4d14059e13c38fd4465e4e597d') or (proof['unchanged_EXE_contract']['record_type'] != '0x8d'):
        raise RuntimeError('Pinned265857F7 typed-position variant changed')

def decode_fields(fields: dict[int, bytes], read, *, normalizer_transform_present=False) -> dict:
    """Copy the exact typed pointer value, without interpreting its two DWORDs."""
    verify_source_evidence()
    if normalizer_transform_present is not False:
        raise ValueError('265857F7 normalizer transform is not modeled')
    if not isinstance(fields, dict) or set(fields) not in ({BLOB_KEY, SELECTOR_KEY}, {BLOB_KEY, SELECTOR_KEY, IGNORED_ARGUMENT_KEY}):
        raise ValueError('Unverified265857F7 input fields')
    typed_position = IGNORED_ARGUMENT_KEY in fields
    ignored_argument = None
    if typed_position:
        verify_variant_source_evidence()
        ignored_argument = decode_scalar(fields[IGNORED_ARGUMENT_KEY], 2)
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    raw = fields[BLOB_KEY]
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Incomplete265857F7 blob variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != (13 if typed_position else 0) or not pointer or size != 8 or (flags != 553648129):
        raise ValueError('Unverified265857F7 blob envelope')
    value = read(pointer, 8)
    if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 8:
        raise ValueError('Incomplete265857F7 pointed value')
    result = {'blob_bytes': bytes(value), 'selector': selector}
    if typed_position:
        result.update(ignored_argument=ignored_argument, variant_evidence_sha256=VARIANT_PROOF_SHA256)
    return result

def encode_record(sequence: int, fields: dict[int, bytes], read, *, thread_hook_present: bool, writer_metadata_callback_present: bool, normalizer_transform_present: bool=False) -> bytes:
    """Encode the native default metadata and initialized12-byte payload.

    The source callback has no notification-counter-dependent metadata and no
    cache gate. Writer allocation zeroes the two gaps; no source-stack padding
    is copied. The explicit profile has neither optional callback registered.
    """
    record, _ = encode_record_with_fields(sequence, fields, read, thread_hook_present=thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, normalizer_transform_present=normalizer_transform_present)
    return record

def encode_record_with_fields(sequence: int, raw_fields: dict[int, bytes], read, *, thread_hook_present: bool, writer_metadata_callback_present: bool, normalizer_transform_present: bool=False) -> tuple[bytes, dict]:
    """Validate/copy the event once and return its record with those fresh fields.

    The returned mapping is derived from this call's validated raw fields; it
    is never accepted as input to an encoder or retained across callbacks.
    """
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('265857F7 registered native callbacks are not modeled')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('265857F7 sequence must be a bounded positive integer')
    values = decode_fields(raw_fields, read, normalizer_transform_present=normalizer_transform_present)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 80, sequence)
    record[84:92] = values['blob_bytes']
    return (bytes(record), values)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'decode_fields', 'encode_record', 'encode_record_with_fields', 'verify_source_evidence']

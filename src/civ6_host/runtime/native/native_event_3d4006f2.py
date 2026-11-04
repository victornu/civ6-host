"""Source-derived encoder for deferred host event 0x3D4006F2.

This only models the absent producer-hook profile. Padding not initialized by
the native callback/writer is deterministically zeroed under an explicit
headless policy; that does not claim those bytes' native runtime values.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from dataclasses import dataclass
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 1027606258
CALLBACK_RVA = 1409968
WRITER_RVA = 1231104
NORMALIZER_RVA = 1876688
RECORD_SIZE = 112
RECORD_TYPE = 68
SELECTOR_KEY = 2716180809
VALUE_KEY = 3606901732
ENTITY_KEY = 4032072631
ENTITY_FLAGS = 553648129
VARIANT_SIZE = 24
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PINNED_EVIDENCE_SHA256 = '68bd7febb97be6e1f75f39d2b16cf7bf0a8acc061728cb9573bd86822c6f90a1'
MISSING_VALUE_PROOF_SHA256 = '92c9dab39af1711e7e7de2bdccb6d21f07f810299abdda6186c619f9ccc50f62'

def verify_missing_value_source():
    if not MISSING_VALUE_PROOF_SHA256:
        raise RuntimeError('3D4006F2 missing-value source proof has not been pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_3d4006f2.py')))).resolve().parents[1] / 'evidence/native-event-3d4006f2-missing-value' / (MISSING_VALUE_PROOF_SHA256 + '.json')
    proof = load_pinned_json(path, MISSING_VALUE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_3d4006f2_missing_value.static.v1' or proof['images']['exe_sha256'] != EXE_SHA256 or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        raise RuntimeError('3D4006F2 missing-value source identity changed')
    return proof

def verify_source_evidence() -> None:
    """Require the immutable source proof before encoding or decoding."""
    if not PINNED_EVIDENCE_SHA256:
        raise RuntimeError('3D4006F2 evidence is not pinned')
    path = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_3d4006f2.py')))).resolve().parents[1] / 'evidence' / 'native-event-3d4006f2' / f'{PINNED_EVIDENCE_SHA256}.json'
    proof = load_pinned_json(path, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_3d4006f2.v1' or proof.get('image', {}).get('exe_sha256') != EXE_SHA256 or proof.get('registration', {}).get('callback_va') != '0x1401583b0' or (proof.get('writer_contract', {}).get('record_type') != '0x44') or (proof.get('writer_contract', {}).get('record_size') != '0x70'):
        raise RuntimeError('3D4006F2 evidence identity changed')

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    entity_pointer: int
    value_present: bool = True

def _u32(value: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be an unsigned 32-bit integer')
    return value

def encode_scalar(tag: int, value: int) -> bytes:
    verify_source_evidence()
    if tag not in (2, 3):
        raise ValueError('only source-proven integer variant tags 2 and 3 are supported')
    return struct.pack('<I4xQII', tag, _u32(value, 'value'), 0, 0)

def decode_scalar(raw: bytes, expected_tag: int) -> int:
    verify_source_evidence()
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != VARIANT_SIZE:
        raise ValueError('scalar variant must be exactly 24 bytes')
    tag, = struct.unpack_from('<H', raw)
    flags, = struct.unpack_from('<I', raw, 20)
    if tag != expected_tag or expected_tag not in (2, 3) or flags != 0:
        raise ValueError('unsupported scalar tag or ownership flags')
    return struct.unpack_from('<I', raw, 8)[0]

def encode_entity_pointer(pointer: int) -> bytes:
    verify_source_evidence()
    if type(pointer) is not int or not 0 < pointer <= 18446744073709551615:
        raise ValueError('entity blob pointer must be a nonzero uint64')
    return struct.pack('<I4xQII', 1024, pointer, 8, ENTITY_FLAGS)

def decode_entity_pointer(raw: bytes) -> int:
    verify_source_evidence()
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != VARIANT_SIZE:
        raise ValueError('entity variant must be exactly 24 bytes')
    tag, = struct.unpack_from('<H', raw)
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 1024 or not pointer or size != 8 or (flags != ENTITY_FLAGS):
        raise ValueError('entity variant does not match source-proven tag/size/flags')
    return pointer

def decode_entity_blob(raw: bytes) -> tuple[int, int, int]:
    """Decode bytes actually consumed from the 8-byte raw host blob.

    The normalizer reads the first owner WORD and DWORD at +4. Bytes +2..+3
    are ignored; normalized entity type is the preinitialized value 1.
    """
    verify_source_evidence()
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 8:
        raise ValueError('entity blob must be exactly eight bytes')
    owner, = struct.unpack_from('<H', raw, 0)
    entity_id, = struct.unpack_from('<I', raw, 4)
    return (owner, 1, entity_id)

def decode_fields(fields: dict[int, bytes]) -> EventFields:
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) not in ({SELECTOR_KEY, VALUE_KEY, ENTITY_KEY}, {SELECTOR_KEY, ENTITY_KEY}):
        raise ValueError('3D4006F2 requires selector/entity and optional source DWORD D6')
    present = VALUE_KEY in fields
    if not present:
        verify_missing_value_source()
    return EventFields(selector=decode_scalar(fields[SELECTOR_KEY], 3), value=decode_scalar(fields[VALUE_KEY], 2) if present else 0, entity_pointer=decode_entity_pointer(fields[ENTITY_KEY]), value_present=present)

def encode_fields(fields: EventFields) -> dict[int, bytes]:
    verify_source_evidence()
    if not isinstance(fields, EventFields):
        raise TypeError('fields must be EventFields')
    if type(fields.value_present) is not bool:
        raise ValueError('3D4006F2 value presence must be an explicit Boolean')
    value = _u32(fields.value, 'value')
    result = {SELECTOR_KEY: encode_scalar(3, _u32(fields.selector, 'selector')), ENTITY_KEY: encode_entity_pointer(fields.entity_pointer)}
    if fields.value_present:
        result[VALUE_KEY] = encode_scalar(2, value)
    else:
        verify_missing_value_source()
        if value != 0:
            raise ValueError('Absent3D4006F2 D6 preserves the source-initialized zero')
    return result

def encode_queue_record(sequence: int, fields: dict[int, bytes], *, entity_blob: bytes, producer_hook_present: bool=False, writer_service_present: bool=False, padding_policy: str, entity_listener_count: int | None=None, normalizer_transform_present: bool | None=None, empty_receiver_state: dict | None=None) -> bytes:
    """Encode the native 0x44 record for a no-producer-hook profile.

    The 0x14012C900 writer copies 0x3c metadata bytes and a 24-byte callback
    payload. It overwrites the first payload DWORD with its sequence counter.
    The native callback's payload DWORD at +4 is uninitialized and uses the
    explicit headless padding policy. Record+0x68..+0x6f remains source-zero
    from the writer's allocation. Missing D6 retains the normalizer's zero.
    """
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if producer_hook_present is not False:
        raise ValueError('optional producer hook side effects are not modeled')
    if writer_service_present is not False:
        raise ValueError('optional writer-service callback is not modeled')
    if padding_policy != 'headless-zero-initialization':
        raise ValueError('explicit headless zero-padding policy is required')
    parsed = decode_fields(fields)
    if not parsed.value_present and (type(entity_listener_count) is not int or entity_listener_count != 0 or normalizer_transform_present is not False):
        raise ValueError('3D4006F2 absent D6 requires explicit empty entity listeners and no transform')
    if not parsed.value_present:
        from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
        if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
            raise ValueError('3D4006F2 absent D6 requires the actual empty receiver state')
        shape = bytearray(RECORD_SIZE)
        struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
        validate_empty_profile_record(shape, **empty_receiver_state)
    owner, entity_type, entity_id = decode_entity_blob(entity_blob)
    metadata = bytearray(60)
    struct.pack_into('<IIHHI', metadata, 0, 4294967295, 4294967295, owner, entity_type, entity_id)
    for offset in (16, 24, 32, 40):
        struct.pack_into('<HHI', metadata, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', metadata, 48, 0)
    struct.pack_into('<I', metadata, 56, 0)
    payload = bytearray(24)
    struct.pack_into('<HHI', payload, 8, owner, entity_type, entity_id)
    struct.pack_into('<II', payload, 16, parsed.selector, parsed.value)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    record[16:76] = metadata
    record[68:72] = b'\x00' * 4
    record[80:104] = payload
    struct.pack_into('<I', record, 80, sequence)
    if not parsed.value_present:
        validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

"""Narrow, empty-receiver equivalent record codec for UnitMoved (BE121408).

This preserves callback-initialized fields, zeroes the six stack-gap bytes,
and is valid only when all EXE hooks/subscribers and observer dispatch are
absent. It is not byte-for-byte faithful to uninitialized stack contents and
does not implement UnitMoved listeners.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3188855816, 23, 128)
POSITION_KEY = 2353434172
BOOL_A_KEY = 1198250499
BOOL_B_KEY = 3332537204
SELECTOR_KEY = 360746564
UNIT_DESCRIPTOR_KEY = 4032072631
_KEYS = frozenset((POSITION_KEY, BOOL_A_KEY, BOOL_B_KEY, SELECTOR_KEY, UNIT_DESCRIPTOR_KEY))
PINNED_EVIDENCE_SHA256 = '6d30780797428774e4b0ba5e9c4707d1f4fc32bd85e72849b6c14a40e6806b2e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_be121408.py')))).resolve().parents[1] / 'evidence/native-event-be121408' / f'{PINNED_EVIDENCE_SHA256}.json'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CALLBACK_SHA256 = 'e0aaded22d753d7f68554abbbd07af19c0e07624653900319477d1f864b8b245'
_WRITER_SHA256 = '16d5f6dfe54f914548da85a39a7bc80734500ba169cb2ceb130e856dd1760353'
_NORMALIZER_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
_HANDLER_SHA256 = '1aa8396d50ab2d13e9a33a1c9d1adb9f730a7a5fbf40a4f05935a804dc75e13a'
_DISPATCH_SHA256 = '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'
_STACK_GAP_POLICY = 'headless-empty-unitmoved-zero-unread-stack-gaps'

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    receiver = proof['unit_moved_receiver']
    type17_rows = proof['receiver_profile']['type_0x17_rows']
    if proof.get('schema') != 'civ6rl.native_event_be121408.static.v1' or proof.get('exe_sha256') != _EXE_SHA256 or proof['registry']['registration']['kind'] != EVENT_KIND or (proof['registry']['registration']['callback_va'] != '0x1401578b0') or (proof['captures']['callback_0x1401578b0']['code_sha256'] != _CALLBACK_SHA256) or (proof['captures']['writer_0x1401271c0']['code_sha256'] != _WRITER_SHA256) or (proof['captures']['host_a0_normalizer_0x1401ca2d0']['code_sha256'] != _NORMALIZER_SHA256) or (receiver['registration']['event_name']['text'] != 'GameCoreEvent::UnitMoved') or (receiver['registration']['row_index'] != RECORD_TYPE) or (receiver['registration']['handler_va'] != '0x1400d6850') or (len(type17_rows) != 1) or (type17_rows[0]['event_name'] != 'GameCoreEvent::UnitMoved') or (type17_rows[0]['handler_va'] != '0x1400d6850') or (receiver['handler']['code_sha256'] != _HANDLER_SHA256) or (receiver['subscriber_dispatch']['code_sha256'] != _DISPATCH_SHA256):
        raise RuntimeError('Pinned BE121408 producer/receiver evidence changed')
    mapping = proof['contract']['a0_normalizer']
    if mapping['normalized_frame_base'] != 'RBP-0x39 is passed as the normalized RDX argument to 0x1401445F0.' or 'type 1 at +0xA' not in mapping['normalized_defaults'] or 'stores them at normalized+8 and normalized+0xC' not in mapping['0xF0548BB7'] or ('stores it at normalized+0x48' not in mapping['0x8C468E3C']):
        raise RuntimeError('Pinned BE121408 A0 normalization mapping changed')

@dataclass(frozen=True)
class EventFields:
    x: int
    y: int
    position_qword: int
    unit_descriptor: bytes
    bool_a_raw: int
    bool_b_raw: int
    selector: int
    entity_descriptor: bytes

def _variant_header(raw: bytes, expected_tag: int) -> tuple[int, int]:
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('BE121408 requires complete 24-byte variants')
    tag = struct.unpack_from('<H', raw, 0)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != expected_tag or flags != 553648129 or size != 8 or (pointer == 0):
        raise ValueError('BE121408 variant tag or blob envelope differs from source witness')
    return (pointer, size)

def _decode_raw_boolean(raw: bytes) -> int:
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('BE121408 boolean input must be a complete variant')
    tag = struct.unpack_from('<H', raw, 0)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if tag != 1 or flags != 0:
        raise ValueError('BE121408 callback boolean requires raw tag-1 input')
    return raw[8]

def decode_fields(raw_fields: dict[int, bytes], read) -> EventFields:
    """Reproduce only the source-mapped fields needed by the callback.

    EXE A0 maps F0548BB7 to normalized +8/+0xC (unit descriptor fields),
    and maps 8C468E3C to normalized +0x48 (position QWORD). RDX passed to
    the Core callback is a normalized object; this API maps from the raw tree
    using the pinned A0 instructions and never treats the tree as that object.
    """
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != _KEYS:
        raise ValueError('BE121408 requires exactly the five witnessed keys')
    position = copy_eight_byte_variant(raw_fields[POSITION_KEY], read, expected_tag=0)
    unit_descriptor = copy_eight_byte_variant(raw_fields[UNIT_DESCRIPTOR_KEY], read, expected_tag=1024)
    x, y = struct.unpack('<II', position)
    position_qword = struct.unpack('<Q', position)[0]
    bool_a = _decode_raw_boolean(raw_fields[BOOL_A_KEY])
    bool_b = _decode_raw_boolean(raw_fields[BOOL_B_KEY])
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    descriptor = struct.pack('<HHI', 65535, 0, 4294967295)
    unit_owner = struct.unpack_from('<H', unit_descriptor, 0)[0]
    unit_id = struct.unpack_from('<I', unit_descriptor, 4)[0]
    normalized_unit = struct.pack('<HHI', unit_owner, 1, unit_id)
    result = EventFields(x, y, position_qword, normalized_unit, bool_a, bool_b, selector, descriptor)
    _validate(result)
    return result

def _validate(fields: EventFields) -> None:
    if not isinstance(fields, EventFields) or any((type(value) is not int or not 0 <= value <= 4294967295 for value in (fields.x, fields.y, fields.selector))) or type(fields.position_qword) is not int or (not 0 <= fields.position_qword <= 18446744073709551615) or (type(fields.unit_descriptor) is not bytes) or (len(fields.unit_descriptor) != 8) or any((type(value) is not int or not 0 <= value <= 255 for value in (fields.bool_a_raw, fields.bool_b_raw))) or (type(fields.entity_descriptor) is not bytes) or (len(fields.entity_descriptor) != 8) or (fields.entity_descriptor != struct.pack('<HHI', 65535, 0, 4294967295)):
        raise ValueError('BE121408 decoded fields violate the pinned callback contract')
    if struct.unpack('<II', struct.pack('<Q', fields.position_qword)) != (fields.x, fields.y):
        raise ValueError('BE121408 x/y fields must match the normalized position QWORD')
    owner, descriptor_type, unit_id = struct.unpack('<HHI', fields.unit_descriptor)
    if descriptor_type != 1:
        raise ValueError('BE121408 normalized unit descriptor type must retain the initialized value 1')

def encode_record(sequence: int, fields: EventFields, *, normalizer_transform_present: bool, per_thread_hook_present: bool, writer_metadata_callback_present: bool, observer_registered: bool, state_pointer_nonnull: bool, pre_hook: int | None, post_hook: int | None, subscriber_count: int, state_flags: int, padding_policy: str) -> bytes:
    """Encode only the equivalent no-listener UnitMoved receiver path.

    The event row forwards record+0x50 to the generic dispatcher, but its
    zero-hook/zero-subscriber branch never dereferences that argument. The
    callback's initialized payload fields are preserved; exactly the two
    stack gaps are zeroed. This profile must be revalidated at consumption.
    """
    verify_source_evidence()
    _validate(fields)
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False or (observer_registered is not False):
        raise ValueError('BE121408 supports only the no-transform/no-hook/no-metadata/no-observer profile')
    if state_pointer_nonnull is not True or pre_hook is not None or post_hook is not None or (type(subscriber_count) is not int) or (subscriber_count != 0) or (type(state_flags) is not int) or (state_flags & 3):
        raise ValueError('BE121408 receiver is not in the verified empty state')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('BE121408 sequence must be a nonzero uint32')
    if padding_policy != _STACK_GAP_POLICY:
        raise ValueError('BE121408 requires the explicit zero policy for its two unread stack gaps')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    metadata = bytearray(60)
    struct.pack_into('<II', metadata, 0, 4294967295, 4294967295)
    unit_owner, _unit_type, unit_id = struct.unpack('<HHI', fields.unit_descriptor)
    struct.pack_into('<HHI', metadata, 8, unit_owner, 1, unit_id)
    for offset in (16, 24, 32, 40):
        struct.pack_into('<HHI', metadata, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', metadata, 48, 0)
    struct.pack_into('<I', metadata, 56, 0)
    record[16:76] = metadata
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields.unit_descriptor
    struct.pack_into('<Q', record, 96, fields.position_qword)
    record[104] = fields.bool_a_raw
    record[105] = fields.bool_b_raw
    struct.pack_into('<I', record, 108, fields.selector)
    record[112:120] = fields.entity_descriptor
    return bytes(record)

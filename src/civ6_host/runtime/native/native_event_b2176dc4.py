"""Source-bounded encoder for the B2176DC4 / UnitChargesChanged queue record."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = '193bde3d5529c7f09022b5ee2e3eab61503a16e539af24b9b785e4a8fe4b56f6'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_b2176dc4.py')))).resolve().parents[1] / 'evidence/native-event-b2176dc4' / f'{PINNED_EVIDENCE_SHA256}.json'
EVENT_KIND = 2987879876
RECORD_TYPE = 46
RECORD_SIZE = 112
SELECTOR_KEY = 2716180809
SECOND_KEY = 2717631346
VALUE_KEY = 3606901732
UNIT_KEY = 4032072631
EMPTY_RECEIVER_PROFILE = 'unit-charges-changed-row-2e-empty'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_b2176dc4.static.v1' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof.get('targets', {}).get('callback') != '0x140155760') or (proof.get('targets', {}).get('queue_writer') != '0x140129d00') or (proof.get('receiver', {}).get('record_type') != '0x2e') or (proof.get('receiver', {}).get('record_size') != '0x70'):
        raise RuntimeError('B2176DC4 source identity changed')
    expected = {'callback': '978039c4387e5262a0c09bc4b8ae6482c8456803739b0dea48a60e158f448440', 'queue_writer': '1a060e27c9d6d1b1d18f17c92c1e51db06f5e314901a7acd8645e03f4a8e90e6', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'}
    for name, digest in expected.items():
        if proof.get('captures', {}).get(name, {}).get('code_sha256') != digest:
            raise RuntimeError(f'B2176DC4 {name} source body changed')
    receiver = proof['receiver']
    if receiver.get('event_name', {}).get('text') != 'GameCoreEvent::UnitChargesChanged':
        raise RuntimeError('B2176DC4 receiver row identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    second: int
    value: int
    owner: int
    unit_id: int
    normalized_unit_type: int = 1

def _u32(value, label):
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be an unsigned DWORD')

def _validate_fields(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('Expected decoded B2176DC4 fields')
    for value, label in ((fields.selector, 'selector'), (fields.second, 'A1FBC372'), (fields.value, 'D6FCF3E4'), (fields.unit_id, 'unit id')):
        _u32(value, label)
    if type(fields.owner) is not int or not 0 <= fields.owner <= 65535:
        raise ValueError('unit owner must be a WORD')
    if type(fields.normalized_unit_type) is not int or fields.normalized_unit_type != 1:
        raise ValueError('normalizer source profile supplies unit type 1')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY, SECOND_KEY, VALUE_KEY, UNIT_KEY}:
        raise ValueError('Unverified B2176DC4 field envelope')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    second = decode_scalar(raw_fields[SECOND_KEY], 2)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    blob = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
    owner, raw_type, unit_id = struct.unpack('<HHI', blob)
    fields = EventFields(selector, second, value, owner, unit_id, 1)
    _validate_fields(fields)
    return fields

def _validate_empty_receiver(state):
    expected = {'profile': EMPTY_RECEIVER_PROFILE, 'record_type': RECORD_TYPE, 'event_name': 'GameCoreEvent::UnitChargesChanged', 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'subscriber_list_empty': True, 'deferred_flag': 0}
    if not isinstance(state, dict) or state != expected or any((type(state[key]) is not type(value) for key, value in expected.items())):
        raise ValueError('B2176DC4 requires the exact initialized-empty 0x2E receiver profile')

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state, padding_policy):
    verify_source_evidence()
    _validate_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('B2176DC4 sequence must be a nonzero DWORD')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('B2176DC4 optional native callbacks are outside the admitted profile')
    _validate_empty_receiver(empty_receiver_state)
    if padding_policy != PADDING_POLICY:
        raise ValueError('B2176DC4 requires explicit empty-receiver stack-padding zeroing')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, fields.owner, 1, fields.unit_id)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<QI', record, 64, 0, 0)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHIII', record, 88, fields.owner, 1, fields.unit_id, fields.value, fields.second)
    return bytes(record)

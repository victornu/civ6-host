"""DiplomacyMeet record, produced after the Core's own internal dispatch.

This adapter encodes the EXE notification only. It neither performs a meeting
nor exposes the diagnostic unit metadata to a learner.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (322781468, 129, 96)
SELECTOR_KEY, VALUE_KEY, SECOND_KEY, UNIT_KEY = (2716180809, 3606901732, 2717631346, 4032072631)
PROOF_SHA256 = 'b7c838284999c176668feb23d4ac92da65a5af71c5eed41c15197a0790c80275'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_133d411c.py')))).resolve().parents[1]
ABSENT_DESCRIPTOR_PROOF_SHA256 = 'ba5e545000e750c2efad63bd81e1e18439b750500c817097b69224aad9629388'
ABSENT_DESCRIPTOR_PROOF = ROOT / 'evidence/native-diplomacy-missing-descriptor' / (ABSENT_DESCRIPTOR_PROOF_SHA256 + '.json')

def verify_absent_descriptor_source():
    p = load_pinned_json(ABSENT_DESCRIPTOR_PROOF, ABSENT_DESCRIPTOR_PROOF_SHA256)
    if p['schema'] != 'civ6rl.native_diplomacy_missing_descriptor.static.v1' or p['parents']['0x133d411c'] != PROOF_SHA256 or p['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e' or (p['contract']['absent_owner_word'] != 65535) or (p['contract']['absent_unit_id'] != 4294967295) or (p['contract']['metadata_type'] != 1) or (p['validation']['all_captured_instructions_match_pinned_pe'] is not True):
        raise ValueError('Absent diplomacy descriptor source differs')
    return p

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('133D411C complete source proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-133d411c' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_133d411c.static.v1' or proof.get('images') != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof.get('captures', {}).get('writer', {}).get('code_sha256') != 'a34a3007e26b5879a8c2f9db93fe9774d76f1a5554a8b4aa278c6f6bc252e5ad' or (proof.get('captures', {}).get('normalizer', {}).get('code_sha256') != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'):
        raise RuntimeError('133D411C source identity changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    value: int
    second: int
    owner: int
    unit_id: int

def _validate(fields):
    if not isinstance(fields, EventFields):
        raise ValueError('133D411C requires decoded fields')
    for value in (fields.selector, fields.value, fields.second, fields.unit_id):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError('133D411C requires raw DWORD values')
    if type(fields.owner) is not int or not 0 <= fields.owner <= 65535:
        raise ValueError('133D411C requires a raw owner WORD')

def decode_fields(raw_fields, read):
    verify_source_evidence()
    required = {SELECTOR_KEY, VALUE_KEY, SECOND_KEY}
    if type(raw_fields) is not dict or set(raw_fields) not in (required, required | {UNIT_KEY}):
        raise ValueError('133D411C requires three scalars and an optional typed descriptor')
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    value = decode_scalar(raw_fields[VALUE_KEY], 2)
    second = decode_scalar(raw_fields[SECOND_KEY], 2)
    if UNIT_KEY in raw_fields:
        blob = copy_eight_byte_variant(raw_fields[UNIT_KEY], read, expected_tag=1024)
        owner, unused_input_type, unit_id = struct.unpack('<HHI', blob)
    else:
        verify_absent_descriptor_source()
        owner, unit_id = (65535, 4294967295)
    fields = EventFields(selector, value, second, owner, unit_id)
    _validate(fields)
    return fields

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state):
    verify_source_evidence()
    _validate(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('133D411C requires a nonzero DWORD sequence')
    if normalizer_transform_present is not False or per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('133D411C optional hook/transform paths are not admitted')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('133D411C requires the actual empty entity listener profile')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('133D411C requires the complete empty receiver state')
    record = _encode_source_record(sequence, fields)
    validate_empty_profile_record(record, **empty_receiver_state)
    return record

def _encode_source_record(sequence, fields):
    """Pure source serializer; it makes no claim about a live receiver row."""
    verify_source_evidence()
    _validate(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('133D411C requires a nonzero DWORD sequence')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHI', record, 16, 4294967295, 4294967295, fields.owner, 1, fields.unit_id)
    for offset in (32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', record, 72, 4)
    struct.pack_into('<III', record, 80, sequence, fields.value, fields.second)
    return bytes(record)

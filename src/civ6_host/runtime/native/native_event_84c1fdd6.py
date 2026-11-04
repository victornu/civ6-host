"""WORK-only, source-bounded codec draft for native kind 0x84C1FDD6.

This is deliberately not wired into the runtime. It supports only the captured
normalizer/callback/writer path and the explicitly empty receiver profile.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
EVENT_KIND = 2227305942
RECORD_TYPE, RECORD_SIZE = (44, 112)
SELECTOR_KEY, D6_KEY, UNIT_KEY = (2716180809, 3606901732, 4032072631)
FIELD_KEYS = frozenset((SELECTOR_KEY, D6_KEY, UNIT_KEY))
PADDING_POLICY = 'zero-unread-stack-only-under-verified-empty-receiver'
SOURCE_PROOF_SHA256 = '2a5167998c1a1e2b53c668274ab497c262df21881647ca62b5eed488f24d6cb2'
RECEIVER_PROOF_SHA256 = 'b63d67dd276fb267b494673cbf6c846536248b090176d6c5d080787f6924bc82'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_LAB = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_84c1fdd6.py')))).resolve().parents[1]
_SOURCE = _LAB / 'evidence/native-event-84c1fdd6-source' / f'{SOURCE_PROOF_SHA256}.json'
_RECEIVER = _LAB / 'work/native-84c1fdd6-receiver402.json'
EMPTY_RECEIVER_STATE = {'observer_registered': False, 'state_pointer_nonnull': True, 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'state_flags': 0}

def _pinned_json(path: Path, expected_sha: str) -> dict:
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError(f'pinned evidence changed: {path}')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError('pinned evidence is not an object')
    return value

def verify_source_evidence() -> dict:
    proof = _pinned_json(_SOURCE, SOURCE_PROOF_SHA256)
    receiver = _pinned_json(_RECEIVER, RECEIVER_PROOF_SHA256)
    bodies = proof.get('captured_bodies', {})
    if proof.get('schema') != 'civ6rl.native_84c1fdd6_source.static.v1' or proof.get('kind') != EVENT_KIND or proof.get('sources', {}).get('exe_sha256') != EXE_SHA256 or (proof.get('sources', {}).get('core_sha256') != CORE_SHA256) or (proof.get('sources', {}).get('receiver402', {}).get('receiver_proof_sha256') != RECEIVER_PROOF_SHA256) or (proof.get('registration', {}).get('callback_va') != '0x140155d20') or (int(proof.get('registration', {}).get('kind', -1)) != EVENT_KIND) or (bodies.get('core_event_producer_29cd80', {}).get('start_va') != '0x18029cd80') or (bodies.get('core_event_dispatch_4858f0', {}).get('start_va') != '0x1804858f0') or (bodies.get('exe_normalizer_1ca2d0', {}).get('raw_code_sha256') is None) or (bodies.get('exe_callback_resolver_1445f0', {}).get('raw_code_sha256') is None) or (bodies.get('exe_callback_155d20', {}).get('raw_code_sha256') != '9063dd16a70388b669d7b0e0c145fcad5805e3153cf10e3cf4deb7ea47b72115') or (bodies.get('exe_writer_129900', {}).get('raw_code_sha256') != '3018a040b6191231b1eeb55bfbbaab3f27d05893314acc99557dfd60cd26edac') or (receiver.get('schema') != 'civ6rl.native_84c1fdd6_receiver.static.v1') or (receiver.get('receiver', {}).get('record_type') != '0x2c') or (receiver.get('receiver', {}).get('record_size') != '0x70') or (receiver.get('receiver', {}).get('callback_va') != '0x140155d20') or (receiver.get('receiver', {}).get('writer_va') != '0x140129900'):
        raise RuntimeError('84C1FDD6 producer/receiver source contract changed')
    return proof

def _variant(raw, *, tag: int, name: str, flags: int=0) -> bytes:
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'{name} must be one complete 24-byte native variant')
    if struct.unpack_from('<H', raw)[0] != tag:
        raise ValueError(f'{name} has the wrong variant tag')
    if struct.unpack_from('<I', raw, 20)[0] != flags:
        raise ValueError(f'{name} has unsupported ownership flags')
    return raw

def _scalar(raw, *, tag: int, name: str) -> int:
    variant = _variant(raw, tag=tag, name=name)
    return struct.unpack_from('<I', variant, 8)[0]

def _validate_receiver(state, entity_listener_count, inline_node_value_present, writer_metadata_callback_present, normalizer_transform_present, notification_counter, metadata_counter):
    if type(state) is not dict or set(state) != set(EMPTY_RECEIVER_STATE):
        raise ValueError('requires the exact proven empty 0x2C receiver state')
    if state['observer_registered'] is not False or state['state_pointer_nonnull'] is not True or state['pre_hook'] is not None or (state['post_hook'] is not None) or (type(state['subscriber_count']) is not int) or (state['subscriber_count'] != 0) or (type(state['state_flags']) is not int) or (state['state_flags'] != 0):
        raise ValueError('0x2C receiver is not exactly empty')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('entity listener count must be exact int zero')
    if type(normalizer_transform_present) is not bool or normalizer_transform_present:
        raise ValueError('a transform-enabled normalizer profile is not admitted')
    if type(writer_metadata_callback_present) is not bool or writer_metadata_callback_present:
        raise ValueError('writer metadata callback must be absent')
    if type(inline_node_value_present) is not bool or inline_node_value_present:
        raise ValueError('optional inline-node callback is not modeled')
    if type(notification_counter) is not int or notification_counter != 0:
        raise ValueError('notification counter must be exact int zero')
    if type(metadata_counter) is not int or metadata_counter != 0:
        raise ValueError('metadata counter must be exact int zero')

def decode_fields(raw_fields: dict, read) -> dict:
    """Validate all envelopes, then copy the sole borrowed 8-byte unit blob."""
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS:
        raise ValueError('84C1FDD6 requires exactly A1E5A149, D6FCF3E4, and F0548BB7')
    selector = _scalar(raw_fields[SELECTOR_KEY], tag=3, name='A1E5A149')
    d6_value = _scalar(raw_fields[D6_KEY], tag=2, name='D6FCF3E4')
    unit = _variant(raw_fields[UNIT_KEY], tag=1024, name='F0548BB7', flags=553648129)
    pointer, size, flags = struct.unpack_from('<QII', unit, 8)
    if pointer == 0 or size != 8 or flags != 553648129:
        raise ValueError('F0548BB7 is outside the captured nonnull 8-byte blob profile')
    if not callable(read):
        raise TypeError('read must be a bounded memory reader')
    copied = read(pointer, 8)
    if type(copied) is not bytes or len(copied) != 8:
        raise ValueError('F0548BB7 pointer read did not return exactly 8 bytes')
    owner, raw_descriptor_type, unit_id = struct.unpack('<HHI', copied)
    if owner >= 64:
        raise ValueError("unit owner is outside the host's supported 0..63 domain")
    return {'selector': selector, 'd6_value': d6_value, 'unit_owner': owner, 'raw_descriptor_type': raw_descriptor_type, 'unit_type': 1, 'unit_id': unit_id, 'unit_active': d6_value != 0}

def encode_record(sequence: int, raw_fields: dict, read, *, receiver_state, entity_listener_count, inline_node_value_present, notification_counter, metadata_counter, writer_metadata_callback_present=False, normalizer_transform_present=False, padding_policy: str | None=None) -> bytes:
    """Encode the witnessed row under explicit callback/receiver assumptions.

    The bytearray's zero fill represents only callback-stack bytes not written
    by the native source. It is admitted solely for the verified empty row.
    """
    verify_source_evidence()
    _validate_receiver(receiver_state, entity_listener_count, inline_node_value_present, writer_metadata_callback_present, normalizer_transform_present, notification_counter, metadata_counter)
    if padding_policy != PADDING_POLICY:
        raise ValueError('explicit zero-unread-stack padding policy is required')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be an exact positive uint32')
    fields = decode_fields(raw_fields, read)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    struct.pack_into('<HHI', record, 24, fields['unit_owner'], 1, fields['unit_id'])
    struct.pack_into('<HHI', record, 32, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 40, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 48, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 56, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    struct.pack_into('<I', record, 72, 0)
    struct.pack_into('<I', record, 68, 0)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields['unit_owner'], 1, fields['unit_id'])
    record[96] = int(fields['unit_active'])
    return bytes(record)

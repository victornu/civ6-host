"""Source-verified codec for the 1D103404 CityCommandStarted callback.

This encodes the diagnostic deferred record only. It does not claim that the
record was consumed or that a gameplay command succeeded.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_host_events import copy_eight_byte_variant
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 487601156
RECORD_TYPE, RECORD_SIZE = (109, 112)
NORMALIZER_RETURN = 0
EVENT_NAME = 'GameCoreEvent::CityCommandStarted'
SELECTOR_KEY, VALUE_KEY, SECOND_VALUE_KEY = (2716180809, 3606901732, 2717631346)
FIRST_DESCRIPTOR_KEY, SECOND_DESCRIPTOR_KEY = (594779970, 4081310810)
FIELD_KEYS = frozenset((SELECTOR_KEY, VALUE_KEY, SECOND_VALUE_KEY, FIRST_DESCRIPTOR_KEY, SECOND_DESCRIPTOR_KEY))
PADDING_POLICY = 'zero-uninitialized-callback-stack-with-verified-empty-receiver'
SOURCE_PROOF_SHA256 = '42673636f7f74889abecad15febf014d1fd31c1e0f31b4b01eda272e716585a7'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_1d103404.py')))).resolve().parents[1]
_PROOF = _ROOT / 'evidence/native-event-1d103404-source' / (SOURCE_PROOF_SHA256 + '.json')
_CALLBACK_SHA256 = '1fc9f2afd7f84c019270826a766a2d508159ffea4400865d8f417a7e36c3678a'
_WRITER_SHA256 = '964069ad581a7c2484b6903b7283d4b0440655e24b3df8f4c0d151e0b020c628'
_NORMALIZER_SHA256 = 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e'
RECEIVER_PROOF_SHA256 = '915a73532cdee77c5053dcd94216dff7db40558f70b2428027819dad06d8c6c8'
_RECEIVER_PROOF = _ROOT / 'evidence/native-1d103404-receiver' / (RECEIVER_PROOF_SHA256 + '.json')

def verify_source_evidence():
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if not SOURCE_PROOF_SHA256:
        raise RuntimeError('1D103404 source proof is not pinned')
    proof = load_pinned_json(_PROOF, SOURCE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_1d103404_source.static.v1' or proof['sources']['exe_sha256'] != EXE_SHA256 or proof['sources']['core_sha256'] != CORE_SHA256 or (proof['registration']['kind'] != EVENT_KIND) or (proof['registration']['callback_va'] != '0x1401411a0') or (EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1315232) or (proof['callback_and_writer']['callback_body_sha256'] != _CALLBACK_SHA256) or (proof['callback_and_writer']['writer_body_sha256'] != _WRITER_SHA256) or (proof['callback_and_writer']['record_type'] != '0x6d') or (proof['callback_and_writer']['record_size_bytes'] != RECORD_SIZE) or (proof['normalization']['normalizer_va'] != '0x1401ca2d0') or (proof['host_a0']['normalizer_body_sha256'] != _NORMALIZER_SHA256) or ('executes xor eax,eax at 0x1401CA7CA and returns with EAX=0' not in proof['host_a0']['return_contract']) or (proof['captured_bodies']['exe']['a0_normalizer_1ca2d0']['code_bytes_sha256'] != _NORMALIZER_SHA256) or (proof['normalization']['key_offsets_and_values'][hex(SELECTOR_KEY)]['destination'] != '+0x04 DWORD') or (proof['normalization']['key_offsets_and_values'][hex(FIRST_DESCRIPTOR_KEY)]['destination'] != '+0x18 owner WORD / +0x1c id DWORD; fixed output type WORD at +0x1a is initialized to 2') or (proof['normalization']['key_offsets_and_values'][hex(SECOND_DESCRIPTOR_KEY)]['destination'] != '+0x28 owner WORD / +0x2c id DWORD; fixed output type WORD at +0x2a is initialized to 3') or (proof['normalization']['key_offsets_and_values'][hex(VALUE_KEY)]['destination'] != '+0x50 DWORD') or (proof['normalization']['key_offsets_and_values'][hex(SECOND_VALUE_KEY)]['destination'] != '+0x54 DWORD') or (set((int(key, 16) for key in proof['witness']['fields'])) != FIELD_KEYS):
        raise RuntimeError('1D103404 source identity or field mapping changed')
    receiver = load_pinned_json(_RECEIVER_PROOF, RECEIVER_PROOF_SHA256)
    row = receiver['receiver']['row']
    if receiver.get('schema') != 'civ6rl.native_1d103404_receiver.static.v1' or receiver['images'].get('exe_sha256') != EXE_SHA256 or receiver['event']['kind'] != EVENT_KIND or (row['record_type'] != RECORD_TYPE) or (row['record_size'] != RECORD_SIZE) or (row['row_va'] != '0x1412c7d20') or (row['setup_va'] != '0x1400cd420') or (row['handler_va'] != '0x1400d87d0') or (row['event_name']['text'] != EVENT_NAME) or (row['handler_body_sha256'] != '970c4e483d897eb6e83da08298fd738ea45b80158dc8965480ddfcb41fdd4923'):
        raise RuntimeError('1D103404 empty-receiver source identity changed')
    return proof

def _decode_scalar_field(raw, tag, label):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'1D103404 {label} must be a complete 24-byte variant')
    return decode_scalar(raw, tag)

def _decode_descriptor_variant(raw, label):
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError(f'1D103404 {label} must be a complete 24-byte variant')
    tag = struct.unpack_from('<H', raw)[0]
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if tag != 1024 or pointer == 0 or size != 8 or (flags != 553648129):
        raise ValueError(f'1D103404 {label} is outside the native blob profile')
    return raw

def decode_fields(raw_fields, read):
    verify_source_evidence()
    if type(raw_fields) is not dict or set(raw_fields) != FIELD_KEYS:
        raise ValueError('1D103404 requires exactly its five source fields')
    selector = _decode_scalar_field(raw_fields[SELECTOR_KEY], 3, 'selector')
    value = _decode_scalar_field(raw_fields[VALUE_KEY], 2, 'D6 value')
    second_value = _decode_scalar_field(raw_fields[SECOND_VALUE_KEY], 2, 'A1FBC value')
    first_raw = _decode_descriptor_variant(raw_fields[FIRST_DESCRIPTOR_KEY], 'first descriptor')
    second_raw = _decode_descriptor_variant(raw_fields[SECOND_DESCRIPTOR_KEY], 'second descriptor')
    first = copy_eight_byte_variant(first_raw, read, expected_tag=1024)
    second = copy_eight_byte_variant(second_raw, read, expected_tag=1024)
    first_owner, _raw_type, first_id = struct.unpack('<HHI', first)
    second_owner, _raw_type, second_id = struct.unpack('<HHI', second)
    result = {'selector': selector, 'value': value, 'second_value': second_value, 'first_owner': first_owner, 'first_id': first_id, 'second_owner': second_owner, 'second_id': second_id}
    _validate_fields(result)
    return result

def _validate_fields(fields):
    if type(fields) is not dict or set(fields) != {'selector', 'value', 'second_value', 'first_owner', 'first_id', 'second_owner', 'second_id'}:
        raise ValueError('1D103404 requires its complete decoded field map')
    for name in ('selector', 'value', 'second_value', 'first_id', 'second_id'):
        value = fields[name]
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'1D103404 {name} must be an exact uint32')
    for name in ('first_owner', 'second_owner'):
        value = fields[name]
        if type(value) is not int or not 0 <= value < 64:
            raise ValueError(f'1D103404 {name} must be a supported player id 0..63')

def _validate_profile(receiver_state, entity_listener_count, notification_counter, metadata_counter, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present):
    if type(normalizer_transform_present) is not bool or normalizer_transform_present or type(thread_hook_present) is not bool or thread_hook_present or (type(writer_metadata_callback_present) is not bool) or writer_metadata_callback_present:
        raise ValueError('1D103404 requires the absent transform/hook/writer-service profile')
    if type(entity_listener_count) is not int or entity_listener_count != 0 or type(notification_counter) is not int or (notification_counter != 0) or (type(metadata_counter) is not int) or (metadata_counter != 0):
        raise ValueError('1D103404 requires zero listeners and neutral notification counters')
    if type(receiver_state) is not dict or set(receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('1D103404 requires the complete verified empty receiver state')
    if receiver_state['observer_registered'] is not False or receiver_state['state_pointer_nonnull'] is not True or receiver_state['pre_hook'] is not None or (receiver_state['post_hook'] is not None) or (type(receiver_state['subscriber_count']) is not int) or (receiver_state['subscriber_count'] != 0) or (type(receiver_state['state_flags']) is not int) or (receiver_state['state_flags'] != 0):
        raise ValueError('1D103404 receiver is not in its exact empty state')

def encode_record(sequence, raw_fields, read, *, receiver_state, entity_listener_count, notification_counter, metadata_counter, normalizer_transform_present=False, thread_hook_present=False, writer_metadata_callback_present=False):
    """Encode the 0x6D record, zeroing its unread callback-stack gap only under the closed empty profile."""
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    validate_sequence(sequence)
    _validate_profile(receiver_state, entity_listener_count, notification_counter, metadata_counter, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present)
    fields = decode_fields(raw_fields, read)
    _validate_fields(fields)
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 56, fields['first_owner'], 2, fields['first_id'])
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHI', record, 88, fields['first_owner'], 2, fields['first_id'])
    struct.pack_into('<HHI', record, 96, fields['second_owner'], 3, fields['second_id'])
    struct.pack_into('<II', record, 104, fields['value'], fields['second_value'])
    validate_empty_profile_record(record, **receiver_state)
    return bytes(record)

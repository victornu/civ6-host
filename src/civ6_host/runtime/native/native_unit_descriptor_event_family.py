"""Exact native callback/writer aliases for descriptor-only unit notifications."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_d8adfd71 as descriptor_codec
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '4bfb2d0013624172c77d510e75bf7e0e0fc2249daea01caa5cc0568f8f3a1445'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_descriptor_event_family.py')))).resolve().parents[1]
RECORD_SIZE = 96
RECORD_TYPES = {3635281265: 29, 2638488821: 34, 1467939621: 41, 473910965: 42, 4178559211: 43, 2620687093: 76, 4061177196: 78, 895056929: 81, 3058947620: 82, 4202025642: 84, 993573825: 85, 2691445918: 278}
NEW_EVENT_KINDS = frozenset(RECORD_TYPES) - {3635281265, 2620687093}
SELECTOR_KEY, DESCRIPTOR_KEY, IGNORED_VALUE_KEY = (2716180809, 4032072631, 3606901732)
PADDING_POLICY = 'zero-unread-unit-descriptor-gap-empty-receiver'
EventFields = descriptor_codec.EventFields

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import UNIT_DESCRIPTOR_RECEIVERS_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    proof = load_pinned_json(ROOT / 'evidence/native-unit-descriptor-event-family' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_unit_descriptor_event_family.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['D8_serialization']['sha256'] != descriptor_codec.PINNED_EVIDENCE_SHA256 or (proof['parents']['receivers']['sha256'] != UNIT_DESCRIPTOR_RECEIVERS_SHA256) or (proof['registry']['sha256'] != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['comparison']['exact_member_count'] != len(RECORD_TYPES)) or (proof['comparison']['callback_instruction_count'] != 65) or (proof['comparison']['writer_instruction_count'] != 137) or (proof['comparison']['all_registered_callback_bodies_examined'] is not True) or (proof['validation']['all_captured_instructions_match_pinned_pe'] is not True) or (proof['validation']['callback_scan_unique_body_count'] != 312) or (len(proof['members']) != len(RECORD_TYPES)) or ({m['kind']: m['record_type'] for m in proof['members']} != RECORD_TYPES):
        raise RuntimeError('Unit descriptor family source changed')
    for member in proof['members']:
        if EXE_EVENT_CALLBACKS.get(member['kind']) != int(member['callback_va'], 16) - 5368709120 or member['record_size'] != RECORD_SIZE or member['writer_after_type_abstraction_equal'] is not True or (int(member['hook_va'], 16) != int(member['receiver_source']['row_va'], 16) + 16) or any((d['index'] not in (32, 55) for d in member['callback_differences'])) or any((not d['base'].startswith('mov dword ptr [rbx + 4], ') for d in member['writer_differences'])):
            raise RuntimeError('Unit descriptor family binding or complete-body comparison changed')
    descriptor_codec.verify_source_evidence()
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    required = {SELECTOR_KEY, DESCRIPTOR_KEY}
    if type(raw_fields) is not dict or set(raw_fields) not in (required, required | {IGNORED_VALUE_KEY}):
        raise ValueError('Unit descriptor family requires its exact two/three-field envelope')
    decode_scalar(raw_fields[SELECTOR_KEY], 3)
    if IGNORED_VALUE_KEY in raw_fields:
        decode_scalar(raw_fields[IGNORED_VALUE_KEY], 2)
    return descriptor_codec.decode_fields({k: raw_fields[k] for k in required}, read)

def encode_record(event_kind, sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    if type(event_kind) is not int or event_kind not in RECORD_TYPES:
        raise ValueError('Unproved unit descriptor callback kind')
    validate_sequence(sequence)
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Unit descriptor family requires actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('Unit descriptor family requires its explicit unread-gap policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('Unit descriptor family requires the complete empty receiver state')
    record = bytearray(descriptor_codec.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack'))
    struct.pack_into('<I', record, 4, RECORD_TYPES[event_kind])
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

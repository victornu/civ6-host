"""Two exact city descriptor callback aliases, with their own receivers.

The native Core has already applied its city changes before these events.
This module transports the borrowed descriptor; it neither repeats those
changes nor interprets a notification return value as action success.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_city_descriptor_events as descriptor_codec
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_99e85ec6 import decode_fields as decode_city_fields
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '96efd3318c478f1c683c8c1655934d6075b33474a461195ac03a7e4b10e4d93c'
RECORD_TYPES = {3892879390: 177, 2313036916: 239}
CALLBACK_RVAS = {3892879390: 1315712, 2313036916: 1316320}
RECORD_SIZE = 96
SELECTOR_KEY, DESCRIPTOR_KEY = (2716180809, 594779970)
PADDING_POLICY = 'zero-unread-city-descriptor-alias-payload-empty-receiver'
NormalizedDescriptor = descriptor_codec.NormalizedDescriptor

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import E808_RECEIVER_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_descriptor_aliases.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-event-e808a01e' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract = proof['contract']
    scan = proof['complete_callback_family_scan']
    if proof['schema'] != 'civ6rl.native_event_e808a01e.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['city_normalization']['sha256'] != descriptor_codec.NORMALIZER_PROOF_SHA256 or (proof['parents']['existing_city_family']['sha256'] != 'da7f0481304e7efb27b0d5d164593073ec9a733a34050a8cc3e4dc6f95369b2b') or (proof['parents']['entity_observer_lifecycle']['sha256'] != '8e221c6ff8a02f77293ef9ce8f62d38cc9b39a545bde8e1740199a630318dd3e') or (proof['parents']['new_receivers']['sha256'] != E808_RECEIVER_SHA256) or (E808_RECEIVER_SHA256 != 'd52cf1865f7d035c3af0cb15c01ad9eec2e037db2474bf6c5a4a37c9d85d6d7a') or (set(proof['new_event_kinds']) != set(RECORD_TYPES)) or (set(contract['field_keys']) != {SELECTOR_KEY, DESCRIPTOR_KEY}) or (contract['tags'] != {'23739F42': 1024, 'A1E5A149': 3}) or (contract['blob_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (contract['record'] != {'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 16, 'metadata_flag': 0, 'undefined_ranges': ((84, 88),), 'allocation_zero_ranges': ((76, 80),)}) or (scan['callback_count'] != 312) or (len(scan['matches']) != 10) or (scan['kind_count'] != 11) or (len(proof['members']) != 11) or (scan['callback_instruction_count'] != 38) or (scan['writer_instruction_count'] != 90) or (scan['permitted_difference_indices'] != (12, 29)) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('City descriptor alias source identity changed')
    candidates = {}
    for member in proof['members']:
        kind = member['kind']
        if EXE_EVENT_CALLBACKS.get(kind) != int(member['callback_va'], 16) - 5368709120 or member['record_size'] != RECORD_SIZE or member['writer_equal_after_only_header_type_normalization'] is not True or any((row['instruction_index'] not in (12, 29) for row in member['callback_differences'])):
            raise RuntimeError('Complete city descriptor callback comparison changed')
        if member['new_admission_candidate']:
            candidates[kind] = member['record_type']
            if EXE_EVENT_CALLBACKS.get(kind) != CALLBACK_RVAS.get(kind):
                raise RuntimeError('City descriptor alias registry binding changed')
    if candidates != RECORD_TYPES:
        raise RuntimeError('City descriptor alias candidates changed')
    descriptor_codec.verify_source_evidence()
    return proof

def _kind(kind):
    if type(kind) is not int or kind not in RECORD_TYPES:
        raise ValueError('Unproved city descriptor alias kind')

def decode_fields(kind, raw_fields, read):
    verify_source_evidence()
    _kind(kind)
    if type(raw_fields) is not dict or set(raw_fields) != {SELECTOR_KEY, DESCRIPTOR_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('City descriptor alias requires exactly two complete typed variants')
    decode_scalar(raw_fields[SELECTOR_KEY], 3)
    fields = decode_city_fields(raw_fields, read)
    return NormalizedDescriptor(fields.owner, 2, fields.item_id)

def encode_record(kind, sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    _kind(kind)
    validate_sequence(sequence)
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('City descriptor aliases require actual empty entity listeners')
    if not isinstance(fields, NormalizedDescriptor) or type(fields.descriptor_type) is not int or fields.descriptor_type != 2:
        raise ValueError('City descriptor normalization must retain native type two')
    if padding_policy != PADDING_POLICY:
        raise ValueError('City descriptor aliases require explicit unread-gap handling')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('City descriptor alias requires its actual complete empty receiver state')
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPES[kind])
    validate_empty_profile_record(shape, **empty_receiver_state)
    record = bytearray(descriptor_codec.encode_record(2075911904, sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack'))
    struct.pack_into('<I', record, 4, RECORD_TYPES[kind])
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

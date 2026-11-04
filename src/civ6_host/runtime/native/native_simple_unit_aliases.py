"""Three complete native unit callback aliases, with independent receivers."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_e992f3cd as removed_codec
from civ6_host.runtime.native import native_event_a60328c5 as scalar_codec
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'd916ef880d846c8159d2265dee99386c443d2db2cdb3e0562222fb3ca642b3cd'
RECORD_TYPES = {902065822: 32, 1716139958: 37, 2603175280: 238}
RECORD_SIZES = {902065822: 96, 1716139958: 112, 2603175280: 112}
SELECTOR_KEY, UNIT_KEY, VALUE_KEY, SECOND_KEY = (2716180809, 4032072631, 3606901732, 2717631346)
PADDING_POLICY = 'zero-unread-simple-unit-alias-payload-empty-receiver'

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import SIMPLE_UNIT_ALIAS_RECEIVERS_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_simple_unit_aliases.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence/native-simple-unit-aliases' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_simple_unit_aliases.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['unit_removed']['sha256'] != removed_codec.PINNED_EVIDENCE_SHA256 or (proof['parents']['two_values_codec']['sha256'] != scalar_codec.PINNED_EVIDENCE_SHA256) or (SIMPLE_UNIT_ALIAS_RECEIVERS_SHA256 != '5c893fa164a3271fb46037a63432b1ebbb912f3f3525b166525e1a65b4bccd39') or (set(proof['contract']['candidate_kinds']) != set(RECORD_TYPES)) or (proof['contract']['receiver_admission_proved_here'] is not False) or (proof['contract']['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (proof['verification'] != {'all_captured_instructions_match_pinned_pe': True, 'instructions_rechecked': 6057, 'parent_instructions_rechecked': 15154, 'callback_scan_instructions_rechecked': 20696}):
        raise RuntimeError('Simple unit alias source identity changed')
    candidates = {}
    for family_name, expected_count, offsets in (('unit_removed', 2, (24, 55)), ('two_values', 7, (36, 59))):
        family = proof['families'][family_name]
        if len(family['members']) != expected_count or family['complete_scan']['permitted_difference_indices'] != offsets:
            raise RuntimeError('Simple unit alias full-family scan changed')
        for member in family['members']:
            if EXE_EVENT_CALLBACKS.get(member['kind']) != int(member['callback_va'], 16) - 5368709120 or member['writer_differences_after_type_normalization'] != () or any((d['index'] not in offsets for d in member['callback_differences_from_parent'])) or (int(member['hook_pair_va'], 16) != int(member['row_va'], 16) + 16):
                raise RuntimeError('Simple unit alias callback/writer equivalence changed')
            if member['candidate']:
                candidates[member['kind']] = (member['record_type'], member['record_size'])
    if candidates != {kind: (record_type, RECORD_SIZES[kind]) for kind, record_type in RECORD_TYPES.items()}:
        raise RuntimeError('Simple unit alias candidate bindings changed')
    removed_codec.verify_source_evidence()
    scalar_codec.verify_source_evidence()
    return proof

def _kind(kind):
    if type(kind) is not int or kind not in RECORD_TYPES:
        raise ValueError('Unproved simple unit alias kind')

def decode_fields(kind, raw_fields, read):
    verify_source_evidence()
    _kind(kind)
    scalar_tags = {SELECTOR_KEY: 3}
    if kind != 902065822:
        scalar_tags.update({VALUE_KEY: 2, SECOND_KEY: 2})
    if type(raw_fields) is not dict or set(raw_fields) != set(scalar_tags) | {UNIT_KEY} or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('Simple unit alias requires its exact complete typed field shape')
    for key, tag in scalar_tags.items():
        decode_scalar(raw_fields[key], tag)
    codec = removed_codec if kind == 902065822 else scalar_codec
    return codec.decode_fields(raw_fields, read)

def encode_record(kind, sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    _kind(kind)
    validate_sequence(sequence)
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Simple unit aliases require actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('Simple unit aliases require explicit unread-gap handling')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('Simple unit alias requires the actual complete empty receiver state')
    shape = bytearray(RECORD_SIZES[kind])
    struct.pack_into('<II', shape, 0, len(shape), RECORD_TYPES[kind])
    validate_empty_profile_record(shape, **empty_receiver_state)
    codec = removed_codec if kind == 902065822 else scalar_codec
    record = bytearray(codec.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy='headless-zero-uninitialized-stack'))
    struct.pack_into('<I', record, 4, RECORD_TYPES[kind])
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

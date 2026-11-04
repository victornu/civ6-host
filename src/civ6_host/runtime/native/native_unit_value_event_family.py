"""Native unit/one-DWORD notifications with proven complete callback aliases."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_a96df790 as ability_codec
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_value_event_family.py')))).resolve().parents[1]
PROOF_SHA256 = 'ee8d7f3ff4f41d76318b6f42eeff8fa123af5c6d4776e7f9c859ee7a6b21fec0'
RECORD_SIZE = 112
RECORD_TYPES = {1712392665: 45, 1265909993: 47, 2842556304: 65, 1920266315: 66}
NEW_EVENT_KINDS = frozenset((1712392665, 1265909993))
SELECTOR_KEY, VALUE_KEY, UNIT_KEY = (2716180809, 3606901732, 4032072631)
PADDING_POLICY = 'zero-unread-unit-value-stack-gaps-empty-receiver'
EventFields = ability_codec.EventFields

def verify_source_evidence():
    from civ6_host.runtime.native.native_deferred_empty_profile import UNIT_PROMOTION_RECEIVER_SHA256
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if not PROOF_SHA256:
        raise RuntimeError('Unit value family source proof has not been pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-661109d9' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_661109d9.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['parents']['ability_gained']['sha256'] != ability_codec.PINNED_EVIDENCE_SHA256 or (proof['parents']['receiver']['sha256'] != UNIT_PROMOTION_RECEIVER_SHA256) or (proof['registry']['sha256'] != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5') or (proof['registry']['complete_callback_body_count'] != 312) or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (len(proof['family_members']) != len(RECORD_TYPES)) or ({m['kind']: m['record_type'] for m in proof['family_members']} != RECORD_TYPES) or (proof['complete_family_scan']['semantic_differences'] != ()) or (proof['complete_family_scan']['only_permitted_callback_difference_indices'] != (34, 57)) or (set(proof['contract']['new_event_kinds']) != NEW_EVENT_KINDS) or (set(proof['contract']['input_keys']) != {SELECTOR_KEY, VALUE_KEY, UNIT_KEY}) or (proof['contract']['tags'] != {'A1E5A149': 3, 'D6FCF3E4': 2, 'F0548BB7': 1024}) or (proof['contract']['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (proof['verification'] != {'instructions_rechecked': 7442, 'parent_instructions_rechecked': 11936, 'callback_scan_instructions_rechecked': 20696}) or (proof['contract']['record'] != {'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 24, 'metadata_flag': 0, 'undefined_ranges': ((84, 88), (100, 104)), 'allocation_zero_ranges': ((76, 80), (104, 112))}):
        raise RuntimeError('Unit value family source identity changed')
    bindings = {1712392665: (1410848, 1219328, 5388398896), 1265909993: (1413232, 1220352, 5388398992), 2842556304: (1394352, 1229568, 5388399856), 1920266315: (1394640, 1230080, 5388399904)}
    for member in proof['family_members']:
        callback, writer, hook = bindings[member['kind']]
        expected_differences = () if member['kind'] == 2842556304 else ({'index': 34, 'member': f'lea rax, [{hex(hook)}]', 'a96': 'lea rax, [0x1412c74f0]'}, {'index': 57, 'member': f'call {hex(5368709120 + writer)}', 'a96': 'call 0x14012c300'})
        if EXE_EVENT_CALLBACKS.get(member['kind']) != callback or member['callback_va'] != hex(5368709120 + callback) or member['writer_va'] != hex(5368709120 + writer) or (member['hook_pair_va'] != hex(hook)) or (member['record_size'] != RECORD_SIZE) or (member['callback_differences_from_a96'] != expected_differences) or (member['writer_differences_after_type_normalization'] != ()):
            raise RuntimeError('Unit value family binding or complete-body equivalence changed')
    ability_codec.verify_source_evidence()
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return ability_codec.decode_fields(raw_fields, read)

def encode_record(event_kind, sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    if type(event_kind) is not int or event_kind not in RECORD_TYPES:
        raise ValueError('Unproved unit value callback kind')
    ability_codec._validate_fields(fields)
    validate_sequence(sequence)
    if any((value is not False for value in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('Unit value family requires absent callback services')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('Unit value family requires actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('Unit value family requires its explicit unread-gap policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('Unit value family requires the complete actual empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPES[event_kind], sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<HHI', record, 24, fields.owner, 1, fields.unit_id)
    struct.pack_into('<I', record, 80, sequence)
    struct.pack_into('<HHII', record, 88, fields.owner, 1, fields.unit_id, fields.value)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

"""UnitEnterFormation: native unit pair in both metadata and payload."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_754cbd1b as pair
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1914843435, 38, 112)
SELECTOR_KEY, FIRST_KEY, SECOND_KEY = (pair.SELECTOR_KEY, pair.FIRST_KEY, pair.SECOND_KEY)
FIELD_KEYS, EventFields = (pair.FIELD_KEYS, pair.EventFields)
PADDING_POLICY = 'zero-unread-unit-pair-gap-empty-receiver'
PROOF_SHA256 = '654c7442299f8e02ef1261f5fa4067f46409959d9175ab028982b8576584e1c1'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_7222312b.py')))).resolve().parents[1]

def verify_source_evidence():
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from civ6_host.runtime.native.native_deferred_empty_profile import UNIT_ENTER_FORMATION_RECEIVER_SHA256
    proof = load_pinned_json(ROOT / 'evidence/native-event-7222312b' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_event_7222312b.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1400384 or (proof['kind'] != EVENT_KIND) or (proof['registry']['registration']['callback_va'] != '0x140155e40') or (proof['registry']['registration']['kind'] != EVENT_KIND) or (proof['parents']['receiver']['sha256'] != UNIT_ENTER_FORMATION_RECEIVER_SHA256) or (proof['parents']['two_unit_normalization']['sha256'] != pair.PROOF_SHA256) or (proof['parents']['callback_writer_alias']['sha256'] != 'e3c46cba1182fd6e895124118ff41a17d22ff314c4c9c5236a050b8443166676') or (proof['captures']['callback']['code_sha256'] != 'dccce0147708385b61228d18834513030d1bd15aad6e8167cbae3062aa7d48a3') or (proof['captures']['writer']['code_sha256'] != '2d4733a13d5419bec1b83d133cc7e6f0266380899712fdceaba40ba7855b4888') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (set(proof['contract']['input_keys']) != FIELD_KEYS) or (proof['contract']['tags'] != {'A1E5A149': 3, 'F0548BB7': 1024, '8753BB21': 1024}) or (proof['contract']['descriptor_envelope'] != {'size': 8, 'flags': 553648129, 'nonnull_pointer': True}) or (proof['contract']['selector_domain'] != (0, 4294967295)) or (proof['contract']['selector_consumed'] is not False) or (proof['contract']['invalid_descriptor_sentinel_guard'] is not False) or (proof['contract']['native_queries'] != 0) or (proof['contract']['retained_interfaces'] != 0) or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['payload_size'] != 24) or (proof['contract']['record']['metadata_flag'] != 0) or (proof['contract']['record']['undefined_ranges'] != ((84, 88),)) or (proof['contract']['record']['allocation_zero_ranges'] != ((76, 80), (104, 112))) or (proof['contract']['metadata']['0x18'] != 'FIRST F054 owner/type1/id') or (proof['contract']['metadata']['0x20'] != 'SECOND8753 owner/type1/id') or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('7222312B source identity changed')
    for parent in proof['parents'].values():
        load_pinned_json(ROOT / parent['path'], parent['sha256'])
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return pair.decode_fields(raw_fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, padding_policy, empty_receiver_state):
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    verify_source_evidence()
    pair._validate_fields(fields)
    validate_sequence(sequence)
    if any((value is not False for value in (normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present))):
        raise ValueError('7222312B requires the absent-service profile')
    if type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('7222312B requires actual empty entity listeners')
    if padding_policy != PADDING_POLICY:
        raise ValueError('7222312B requires its explicit unread-gap policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('7222312B requires the complete actual empty receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<II', record, 16, 4294967295, 4294967295)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    for metadata, payload, owner, item_id in ((24, 88, fields.first_owner, fields.first_id), (32, 96, fields.second_owner, fields.second_id)):
        struct.pack_into('<HHI', record, metadata, owner, 1, item_id)
        struct.pack_into('<HHI', record, payload, owner, 1, item_id)
    struct.pack_into('<I', record, 80, sequence)
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)

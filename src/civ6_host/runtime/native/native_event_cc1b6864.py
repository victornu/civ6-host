"""Source-pinned same-callback alias for UnitExitFormation."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native import native_event_45b4e4f8 as original
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 3424348260
RECORD_TYPE, RECORD_SIZE = (original.RECORD_TYPE, original.RECORD_SIZE)
SELECTOR_KEY, VALUE_KEY = (original.SELECTOR_KEY, original.VALUE_KEY)
UNIT_KEY, SECOND_KEY = (original.UNIT_KEY, original.SECOND_KEY)
REQUIRED_KEYS, OPTIONAL_KEYS = (original.REQUIRED_KEYS, original.OPTIONAL_KEYS)
EventFields = original.EventFields
EMPTY_RECEIVER_PROFILE, PADDING_POLICY = (original.EMPTY_RECEIVER_PROFILE, original.PADDING_POLICY)
PAIR_PROOF_SHA256 = original.PAIR_PROOF_SHA256
PROOF_SHA256 = '7e663aa6e2fbb3be2af791371ecf159c1a67072df0465e139e441fd394ad2c49'
PINNED_EVIDENCE_SHA256 = PROOF_SHA256
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_cc1b6864.py')))).resolve().parents[1]

def verify_source_evidence():
    from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
    original.verify_pair_source_evidence()
    proof = load_pinned_json(ROOT / 'evidence/native-event-cc1b6864' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    contract, equivalence = (proof['contract'], proof['alias_equivalence'])
    if proof['schema'] != 'civ6rl.native_event_cc1b6864.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['kind'] != EVENT_KIND or (EXE_EVENT_CALLBACKS.get(EVENT_KIND) != 1400960) or (EXE_EVENT_CALLBACKS.get(original.EVENT_KIND) != 1400960) or (proof['registry']['registration']['kind'] != EVENT_KIND) or (proof['registry']['registration']['callback_va'] != '0x140156080') or (proof['registry']['alias_registration']['kind'] != original.EVENT_KIND) or (proof['parents']['exact_callback_alias']['sha256'] != PAIR_PROOF_SHA256) or (proof['parents']['two_key_core_producer']['sha256'] != 'dea3dfa82a9924acb6d740d10d8de9d1c5b8a5f9f5caa6cec17f5aec201ab428') or (proof['captures']['callback']['code_sha256'] != '55b353ab355113b4507d389fd259106fa215ad79513bd568d750a9a51c575459') or (proof['captures']['writer']['code_sha256'] != '911c9d05e564076834f9b6c8997a21d34aeb47c9ab30f504fbbcb018ebfd41fd') or (equivalence['complete_same_address'] is not True) or (equivalence['callback_va'] != '0x140156080') or (equivalence['writer_va'] != '0x140129130') or (equivalence['callback_differences'] != ()) or (equivalence['writer_differences'] != ()) or (equivalence['receiver_type_change'] is not False) or (contract['callback_kind_consumed'] is not False) or (contract['normalized_header_magic'] != 1682424637) or (contract['normalized_header_is_dispatch_kind'] is not False) or (set(contract['required_keys']) != REQUIRED_KEYS) or (set(contract['optional_keys']) != OPTIONAL_KEYS) or (contract['record']['type'] != RECORD_TYPE) or (contract['record']['size'] != RECORD_SIZE) or (proof['empty_receiver_source']['record_type'] != RECORD_TYPE) or (proof['empty_receiver_source']['event_name'] != 'GameCoreEvent::UnitExitFormation') or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('CC1B6864 same-callback source identity changed')
    for parent in proof['parents'].values():
        load_pinned_json(ROOT / parent['path'], parent['sha256'])
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return original.decode_fields(raw_fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, entity_listener_count, empty_receiver_state, padding_policy):
    verify_source_evidence()
    return original.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, entity_listener_count=entity_listener_count, empty_receiver_state=empty_receiver_state, padding_policy=padding_policy)

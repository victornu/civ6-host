"""Source-pinned DWORD domains for scalar player notifications and live C1 lookup.

A value passing these checks is transport data, not an existing player or an
eligible learner actor. C1 must pass it to native outer+B8: the native function
checks its 65-slot domain and actual presence, and its null return is preserved.
This module performs no lookup, substitutes no result, and owns no interfaces.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = 'ddbfe3f9ef5b32a60912957f15dd14fc590c3e4f4ce021059b117f2d4ff1e270'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CONFIGURATION_PLAYER_COUNT = 64
NATIVE_PLAYER_LOOKUP_COUNT = 65
BOOLEAN_UNDEFINED_RECORD_RANGE = (89, 92)
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_player_event_domains.py')))).resolve().parents[1]
_PROOF = _ROOT / 'evidence/native-player-event-domains' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    contract = proof.get('contract', {})
    record = contract.get('records', {})
    if proof.get('schema') != 'civ6rl.native_player_event_domains.static.v1' or proof.get('native_execution') is not False or proof.get('images') != {'core_sha256': CORE_SHA256, 'exe_sha256': EXE_SHA256} or (contract.get('configuration_player_count') != CONFIGURATION_PLAYER_COUNT) or (contract.get('scalar_transport_domain') != (0, 4294967295)) or (contract.get('lookup_input_domain') != (0, 4294967295)) or (contract.get('lookup_existable_slot_domain') != (0, NATIVE_PLAYER_LOOKUP_COUNT - 1)) or (record.get('0x10c', {}).get('undefined_record_ranges') != (BOOLEAN_UNDEFINED_RECORD_RANGE,)) or (record.get('0x109', {}).get('undefined_record_ranges') != ()) or (record.get('0xc1', {}).get('undefined_record_ranges') != ()) or (proof.get('validation', {}).get('all_captured_instructions_match_pinned_pe') is not True):
        raise RuntimeError('Native scalar player event domain proof changed')
    for kind, flag in (('0x10c', 4), ('0x109', 6), ('0xc1', 0)):
        if record[kind]['size'] != 96 or record[kind]['metadata_flag'] != flag:
            raise RuntimeError('Native scalar player record shape changed')
    return proof

def _uint32(value, label):
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(label + ' must be an exact uint32')
    return value

def validate_player_transport_value(player):
    """Preserve the DWORD copied by the 10C/109 callbacks; do not classify it."""
    return _uint32(player, 'Player transport value')

def validate_player_query_input(player):
    """Validate the native +B8 DWORD argument, including natively null indices.

    In particular 65 and FFFFFFFF are not rejected or turned into None here.
    The caller must invoke the real getter and retain its actual null/pointer.
    """
    return _uint32(player, 'Native player query input')

def validate_player_index(player, requires_interface=False):
    """Compatibility spelling; requires_interface selects intent, not a filter."""
    if type(requires_interface) is not bool:
        raise ValueError('requires_interface must be bool')
    validator = validate_player_query_input if requires_interface else validate_player_transport_value
    return validator(player)

def validate_scalar_value(value):
    """Preserve every A1FBC DWORD bit; the 10C caller applies value != 0."""
    return _uint32(value, 'Scalar event value')

def validate_sequence(sequence):
    """Retain the existing diagnostic positive-int32 sequence policy.

    This is a bounded host policy, not the native atomic counter's full domain.
    """
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('Diagnostic event sequence must be a positive int32')
    return sequence
verify_source_evidence()

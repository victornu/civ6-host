"""Pinned public path-preview representation; movement rules stay in GameCore."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_move_path_contract.py')))).resolve().parents[1]
PINNED_EVIDENCE_SHA256 = '9bb8e252ac99249b2e1da5370a74d4983dd8ebd0e2db632e3fcda74312e49889'
_PROOF = _ROOT / 'evidence/native-move-path-contract' / (PINNED_EVIDENCE_SHA256 + '.json')

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    callbacks = {'GetMoveToPathEx': '0x1805486f0', 'GetReachableMovement': '0x180549510', 'CanStartOperation': '0x180547840', 'RequestOperation': '0x18054a600'}
    if proof['schema'] != 'civ6rl.native_move_path_contract.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['native_execution'] is not False or any((proof['registrations'][name]['callback_va'] != address for name, address in callbacks.items())) or (proof['captures']['get_move_to_path_ex']['complete_instruction_bytes_sha256'] != '736c2eb2e7b5b5fb4b13648de18366090162bda5a0495aaa9a261c054d1a6810') or (set(proof['field_name_literals']) != {'plots', 'turns', 'obstacles', 'entrancePortals', 'exitPortals'}) or (proof['contract']['tables']['plots']['array_index_base'] != 1) or (proof['contract']['tables']['turns']['array_index_base'] != 1):
        raise RuntimeError('Native movement path contract changed')
    return proof

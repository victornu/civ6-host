"""Typed observation of host+168; no capability/ownership result is invented."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_capability_status.py')))).resolve().parents[1]
PROOF_SHA256 = '77ed09ed4c69e5f23c83e72e45bad0d0ee5aec62bcebc66dfe3d4dff526ba620'
CATALOGUE_SHA256 = '7af856728f9cd45337bcd07b7bd10418415048b0823b08427f6bce44f2540c34'

def verify_source():
    proof = load_pinned_json(ROOT / 'evidence/native-host-capability-status' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_host_capability_status.static.v1' or proof['images']['core']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['images']['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['binding'] != {'callback_va': '0x1401c94b0', 'host_vtable_va': '0x140fc79d0', 'raw_slot_hex': 'b0941c4001000000', 'slot': '0x168'}) or (proof['exe_functions']['host_168_callback']['code_sha256'] != '92eb3278c3074ac9d440a7c061f8dfac50f4e71e124c64b6931f14b2500ed039') or (proof['abi']['result'] != 'EAX status DWORD') or (proof['source_revalidation']['all_instruction_bytes_match_pinned_pe'] is not True):
        raise RuntimeError('Host capability-status ABI source differs')
    return proof

def request_details(player, capability, *, candidate_backend=None):
    """Preserve native DWORDs; catalogue names are labels, never permission."""
    if any((type(value) is not int or not 0 <= value <= 4294967295 for value in (player, capability))):
        raise ValueError('Capability query arguments must be native unsigned DWORDs')
    if candidate_backend is None:
        verify_source()
        catalogue = load_pinned_json(ROOT / 'evidence/native-capability-catalogue' / (CATALOGUE_SHA256 + '.json'), CATALOGUE_SHA256)
    else:
        from civ6_host.runtime.xp1_load_capability import candidate_label_catalogue
        catalogue = candidate_label_catalogue(candidate_backend)
    names = [row['name'] for row in catalogue['capabilities'] if row['hash_u32'] == capability]
    if len(names) > 1:
        raise ValueError('Capability catalogue hash is ambiguous')
    return {'player_id_u32': player, 'capability_u32': capability, 'capability_hex': f'0x{capability:08x}', 'base_catalogue_name': names[0] if names else None, 'base_catalogue_sha256': CATALOGUE_SHA256, 'source_proof_sha256': PROOF_SHA256, 'capability_status_returned': False, 'active_ownership_registry_verified': False, 'eligible_for_training': False}

def install_typed_refusal(host, *, base, read, candidate_backend=None):
    """Bind the pinned Base ABI after comparing its loaded consumer bytes."""
    if getattr(host, '_capability_status_probe_installed', False):
        raise ValueError('Capability query probe is already installed')
    proof = verify_source()
    if candidate_backend is not None:
        from civ6_host.runtime.xp1_load_capability import verify_candidate_live
        if candidate_backend.host is not host or candidate_backend.core._handle != base:
            raise ValueError('XP1 capability probe owner differs')
        verify_candidate_live(candidate_backend)
    else:
        for fragment in proof['core_functions']['refresh_capabilities']['fragments']:
            for instruction in fragment['instructions']:
                expected = bytes.fromhex(instruction['bytes'])
                address = base + int(instruction['va'], 16) - 6442450944
                if read(address, len(expected)) != expected:
                    raise ValueError('Loaded native capability consumer differs')

    def refusal(this, player, capability):
        host._check(this)
        if candidate_backend is None:
            details = request_details(player, capability)
        else:
            from civ6_host.runtime.xp1_load_capability import candidate_details
            details = candidate_details(candidate_backend, player, capability)
        host.emit('native_host_capability_status_requested', **details)
        host._fatal('AppOwnership capability status is not connected', interface='host', slot='0x168', **details)
        raise RuntimeError('Capability refusal unexpectedly returned')
    host._bind(host.vtable, 360, C.c_uint32, [C.c_void_p, C.c_uint32, C.c_uint32], refusal)
    host._capability_status_probe_installed = True
    host.emit('native_host_capability_status_probe_installed', source_proof_sha256=PROOF_SHA256, returns_capability_status=False, typed_refusal_only=True)

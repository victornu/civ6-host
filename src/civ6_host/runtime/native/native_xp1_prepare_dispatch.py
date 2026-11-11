"""Verified XP1 Prepare dispatch. This is not a complete host or a game runner.

The caller owns localization, all callback implementations, and teardown. Unknown
host methods must remain fatal. This module does not enable the absent-Tuner
diagnostic or substitute Base addresses for XP1 addresses.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
PREFERRED_BASE = 6442450944
MAX_U64 = (1 << 64) - 1
PROOF_PINS = {'boundary': ('evidence/native-expansion-init-boundary/fc1786d5b274a0e184e2314cbe0b30da8076a6b784f5a09a423496885f2937f6.json', 'fc1786d5b274a0e184e2314cbe0b30da8076a6b784f5a09a423496885f2937f6'), 'capture': ('work/native-xp1-prepare813/capture813-v2.json', 'c2fdcb3351c43427267c72a624bfbfdf19e1e1c6468f322df4ea0305b6b82091')}
SOURCE_PINS = {'civ6rl/native_core_context_profiles.py': '8f5aed71ecf614d6fa25d52b94b7fec4a0bb4bcec190f8f144b04c4cf541d676', 'civ6rl/native_xp1_context_init.py': '6e3172c2a69168bda640aba91284d828b89e0b1b5e02b2e5ecc417d6b08f547e', 'civ6rl/native_host.py': 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6', 'civ6rl/native_localization.py': '7ddac11af2a3ec117db11de262eec450665c2a8606851dfedb0a8df84d771721', 'civ6rl/native_setup.py': '5fb54924ceba00572003e395b6b49013847e41cf4ecc9f0c1c3f3dd5bad88432', 'civ6rl/native_xp1_teardown_adapter.py': '3fcde8a9ab8f26363ba44ffa7fba60661c1bdd2439587732ac74abf2e0df4b3d'}

def verify_source(project_root):
    root = _resolve_resource_path(_resolve_resource_path(Path(project_root))).resolve()
    for rel, sha in SOURCE_PINS.items():
        if hashlib.sha256(_resolve_resource_path(root / rel).read_bytes()).hexdigest() != sha:
            raise ValueError(f'XP1 Prepare dependency changed: {rel}')
    proofs = {}
    for name, (rel, sha) in PROOF_PINS.items():
        raw = _resolve_resource_path(root / rel).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError(f'XP1 Prepare proof changed: {rel}')
        proofs[name] = json.loads(raw)
    boundary = proofs['boundary']['rulesets']['xp1']
    method = boundary['methods']['prepare']
    capture = proofs['capture']
    if boundary['gamecore_sha256'] != CORE_SHA256 or capture['binary']['sha256'] != CORE_SHA256 or method['context_slot'] != '0x40' or (method['target_rva'] != '0x4be6a0') or (method['forwards_to_inner_slot'] != '0x50') or (method['inner_target_rva'] != '0x3db40'):
        raise ValueError('XP1 Prepare dispatch differs from the pinned ABI')
    return proofs

def _read(read, address, size):
    if type(address) is not int or type(size) is not int or address <= 0 or (not 0 < size <= 65536) or (address > MAX_U64 - size + 1):
        raise ValueError('Invalid bounded XP1 memory read')
    data = read(address, size)
    if type(data) is not bytes or len(data) != size:
        raise ValueError('Incomplete XP1 memory read')
    return data

def _pointer(read, address):
    return struct.unpack('<Q', _read(read, address, 8))[0]

def verify_dispatch(core_base, context, read, proofs):
    """Read-only verification of both relocated vtables and executable bodies."""
    if type(core_base) is not int or not 0 < core_base <= MAX_U64 - 10485760:
        raise ValueError('Invalid XP1 module base')
    boundary = proofs['boundary']['rulesets']['xp1']
    method = boundary['methods']['prepare']
    inner = _pointer(read, context + 8)
    if not inner:
        raise ValueError('XP1 inner context is null')
    outer_vtable = _pointer(read, context)
    inner_vtable = _pointer(read, inner)
    outer = boundary['context_vtable_capture']
    inner_table = next((row for row in proofs['capture']['vtables'] if row['rva'] == '0x8d7168'))
    for observed, record in ((outer_vtable, outer), (inner_vtable, inner_table)):
        raw = bytes.fromhex(record['raw_hex'])
        if len(raw) % 8 or hashlib.sha256(raw).hexdigest() != record['sha256'] or observed != core_base + int(record['rva'], 16):
            raise ValueError('XP1 context vtable identity mismatch')
        pointers = struct.unpack('<' + 'Q' * (len(raw) // 8), raw)
        relocated = b''.join((struct.pack('<Q', core_base + ptr - PREFERRED_BASE) for ptr in pointers))
        if _read(read, observed, len(raw)) != relocated:
            raise ValueError('XP1 context vtable contents changed')
    for body in (method['target_body'], method['inner_target_body']):
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            if _read(read, core_base + int(fragment['start_rva'], 16), len(raw)) != raw:
                raise ValueError('XP1 Prepare executable bytes changed')
    if _pointer(read, inner + 96):
        raise ValueError('XP1 Prepare requires a context whose game services are not constructed')
    return {'outer': context, 'inner': inner, 'target': core_base + 4974240}

def prepare_xp1_context(core, context, host, *, project_root, module_paths, emit, null_tuner_diagnostic=False):
    """Call the original XP1 Prepare after explicit host/localization setup.

    There is no claim that the caller has implemented every service. A missing
    service must stop its isolated worker; returning here only observes Prepare.
    """
    from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_modules
    from civ6_host.runtime.native.native_xp1_context_init import _native_virtual
    from civ6_host.runtime.native.native_xp1_context_init import XP1_SLOTS
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_host import DiagnosticHost
    proofs = verify_source(project_root)
    from civ6_host.runtime.xp1_saved_load import select_context, teardown_core_identity
    profile = select_context(core, getattr(host, '_xp1_saved_load_bundle', None), profile_for_core)
    validate_loaded_modules(profile, module_paths)
    if type(host) is not DiagnosticHost or getattr(host, 'localization_initialized', False) is not True:
        raise ValueError('XP1 Prepare requires retained native localization and owned host')
    if getattr(host, 'tuner_unavailable_probe', False):
        from civ6_host.runtime.xp1_prepare import require_null_tuner_diagnostic
        require_null_tuner_diagnostic(host, null_tuner_diagnostic)
    elif null_tuner_diagnostic:
        raise ValueError('NULL Tuner diagnostic requires the explicit host probe')
    if getattr(host, '_xp1_prepare_entered', False):
        raise ValueError('XP1 Prepare has already been entered in this worker')
    binding = getattr(host, '_xp1_teardown_binding', {})
    if binding.get('installed') is not True or binding.get('core_sha256') != teardown_core_identity(host) or binding.get('context_pointer') != hex(context) or (binding.get('core_module_base') != hex(core._handle)) or (binding.get('host_pointer') != hex(host.pointer)):
        raise ValueError('XP1 Prepare requires the matching retained teardown binding')
    read = local_reader()
    dispatch = verify_dispatch(core._handle, context, read, proofs)
    if _pointer(read, core._handle + 10430016) != host.pointer:
        raise ValueError('XP1 Prepare host global changed')
    getter = _native_virtual(core, context, 56, XP1_SLOTS[56], C.c_bool)
    if getter(context) is not True:
        raise ValueError('XP1 Prepare requires successful native Init')
    emit('before_xp1_prepare', outer_slot='0x40', inner_slot='0x50', target_rva='0x4be6a0')
    host._xp1_prepare_entered = True
    C.WINFUNCTYPE(None, C.c_void_p)(dispatch['target'])(context)
    services = _pointer(read, dispatch['inner'] + 96)
    receipt = {'schema': 'civ6rl.native_xp1_prepare_dispatch826.v1', 'returned': True, 'services_nonnull': bool(services), 'game_created': False, 'newgame_called': False, 'eligible_for_training': False, 'complete_host_contract_verified': False}
    emit('xp1_prepare_returned', receipt=receipt)
    if not services:
        raise RuntimeError('XP1 Prepare returned without its game services')
    return receipt

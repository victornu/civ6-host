"""Bounded XP1 autoarchive getter/removal binding; registration stays fatal.

Install after a successful, retained XP1 Init receipt and before the observed
Prepare getter call.  This module never invokes XP1 callbacks, Prepare, or
Destroy, and does not claim a complete archive-registration lifecycle.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
DESCRIPTOR_PROOF_SHA256 = '978c6f5b7ee222ca30c632bc8e7973c15105aea5342ca3e2a55b55957f974cd9'
DESCRIPTOR_PROOF_RELATIVE = 'work/native-xp1-descriptor842/descriptor842-v3.json'
AUDIT_PROOF_SHA256 = 'bd9529daeb7872ea325025ff3630a69f4217897d518a0fe62e468cb3123c05c1'
AUDIT_PROOF_RELATIVE = 'work/native-xp1-descriptor843/analysis843-v3.json'
BASE_SOURCE_PINS = {'civ6rl/native_host.py': 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6', 'civ6rl/native_xp1_context_init.py': '6e3172c2a69168bda640aba91284d828b89e0b1b5e02b2e5ecc417d6b08f547e', 'civ6rl/native_core_context_profiles.py': '8f5aed71ecf614d6fa25d52b94b7fec4a0bb4bcec190f8f144b04c4cf541d676', 'civ6rl/native_xp1_teardown_adapter.py': '3fcde8a9ab8f26363ba44ffa7fba60661c1bdd2439587732ac74abf2e0df4b3d'}

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def _pinned_json(root: Path, relative: str, expected: str) -> dict:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f'Pinned XP1 archive proof changed: {relative}')
    value = json.loads(_resolve_resource_path(path).read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError('Pinned XP1 archive proof is not an object')
    return value

def verify_source(project_root) -> dict:
    """Verify the byte-pinned XP1 getter/removal contract and host sources."""
    root = _resolve_resource_path(_resolve_resource_path(Path(project_root))).resolve()
    source_hashes = {}
    for relative, expected in BASE_SOURCE_PINS.items():
        actual = _sha256(root / relative)
        if actual != expected:
            raise ValueError(f'XP1 archive dependency changed: {relative}')
        source_hashes[relative] = actual
    proof = _pinned_json(root, DESCRIPTOR_PROOF_RELATIVE, DESCRIPTOR_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_xp1_descriptor842.static.v3' or proof.get('binary', {}).get('sha256') != XP1_CORE_SHA256:
        raise ValueError('XP1 descriptor proof image/schema mismatch')
    thunk = proof.get('host108_thunk', {})
    if thunk.get('rva') != '0x393e0' or thunk.get('raw_hex') != '488b0d59929b00488b0148ffa008010000' or 'pointer-sized return' not in thunk.get('abi_observation', ''):
        raise ValueError('XP1 host+0x108 getter proof changed')
    wrapper = proof.get('returned_object_consumer', {})
    selected = {row.get('rva'): row for row in wrapper.get('selected_instructions', [])}
    if wrapper.get('helper_rva') != '0x83b7d0' or selected.get('0x83b85e', {}).get('bytes') != '48897350' or selected.get('0x83b88c', {}).get('bytes') != '48894358' or ('0x00000000ffffffff' not in selected.get('0x83b88c', {}).get('text', '')):
        raise ValueError('XP1 returned descriptor pointer/key layout proof changed')
    unregister = proof.get('unregister_path', {})
    unreg_rows = {row.get('rva'): row for row in unregister.get('instructions', [])}
    if unregister.get('destructor_rva') != '0x83b970' or unreg_rows.get('0x83b99c', {}).get('bytes') != 'ff5008' or unreg_rows.get('0x83b97f', {}).get('bytes') != '80794800' or (unreg_rows.get('0x83b99f', {}).get('bytes') != 'c6474800'):
        raise ValueError('XP1 descriptor +8 removal proof changed')
    disposition = proof.get('decision', {})
    if 'interface+0' not in disposition.get('registration_status', '') or 'do not infer' not in disposition.get('remaining_gap', '').lower():
        raise ValueError('XP1 registration gap is no longer explicit in proof')
    audit = _pinned_json(root, AUDIT_PROOF_RELATIVE, AUDIT_PROOF_SHA256)
    confirmed = audit.get('confirmed_contract', {})
    unresolved = audit.get('unresolved_contract', {})
    if audit.get('schema') != 'civ6rl.native_xp1_descriptor843.audit.v3' or audit.get('xp1_binary_sha256') != XP1_CORE_SHA256 or confirmed.get('host_getter_slot') != '0x108' or (confirmed.get('remove_slot') != '0x08') or (unresolved.get('registration_slot') != '0x00') or ('unsupported/fatal' not in unresolved.get('status', '')):
        raise ValueError('XP1 getter/remove-only audit contract changed')
    return {'schema': 'civ6rl.native_xp1_archive_access_source.v1', 'project_root': str(root), 'source_sha256': source_hashes, 'descriptor_proof_sha256': DESCRIPTOR_PROOF_SHA256, 'audit_proof_sha256': AUDIT_PROOF_SHA256, 'xp1_core_sha256': XP1_CORE_SHA256, 'supported_slots': {'host': '0x108', 'descriptor': ['0x08']}, 'unsupported_fatal_slots': {'descriptor': ['0x00']}, 'eligible_for_training': False}

def _check_teardown_receipt(receipt, host, core_base: int) -> None:
    from civ6_host.runtime.xp1_saved_load import teardown_core_identity
    if type(receipt) is not dict or receipt.get('schema') != 'civ6rl.native_xp1_teardown_adapter_installation.v1':
        raise ValueError('XP1 archive binding requires the retained 821 teardown receipt')
    if getattr(host, '_xp1_teardown_binding', None) is not receipt:
        raise ValueError('XP1 teardown receipt is not the one retained by this host')
    if receipt.get('installed') is not True or receipt.get('core_sha256') != teardown_core_identity(host) or receipt.get('core_module_base') != hex(core_base) or (receipt.get('host_pointer') != hex(host.pointer)) or (receipt.get('initialized_getter_observed') is not True) or (receipt.get('destroy_called') is not False) or (receipt.get('game_created') is not False) or (receipt.get('newgame_called') is not False) or (receipt.get('eligible_for_training') is not False):
        raise ValueError('XP1 teardown receipt is failed, mismatched, or out of scope')
    if receipt.get('init_receipt_schema') != 'civ6rl.native_xp1_context_init_receipt.v1' or receipt.get('context_pointer') in (None, '0x0') or receipt.get('callback_references_retained') is not True or (type(receipt.get('type_names_allowed')) is not list) or (receipt.get('type_names_allowed') != ['Unit', 'Formation', 'City::Instance', 'Trade::Edge', 'Control::Contract', 'District::Instance', 'AI::CityBuild', 'BehaviorTree', 'AI::Operation', 'DynamicModifier']) or (not callable(getattr(host, 'native_aligned_free', None))):
        raise ValueError('XP1 teardown binding is not retained/complete for this host')
    globals_verified = receipt.get('host_globals_verified')
    if type(globals_verified) is not dict or globals_verified.get('0x9f2640') != hex(host.pointer) or globals_verified.get('0x9f2648') != hex(C.addressof(host.aux_object)) or (globals_verified.get('0x9f2650') != hex(C.addressof(host.logger_object))):
        raise ValueError('XP1 teardown receipt does not retain the exact host interfaces')

def _check_host(host):
    from civ6_host.runtime.native.native_host import DiagnosticHost
    if type(host) is not DiagnosticHost:
        raise ValueError('XP1 archive binding accepts only the retained DiagnosticHost')
    if getattr(host, '_xp1_archive_access_binding', None) is not None:
        raise ValueError('XP1 archive getter/removal callbacks are already installed')
    if getattr(host, '_xp1_prepare_entered', False) is True:
        raise ValueError('XP1 archive callbacks must be installed before Prepare begins')
    if not callable(getattr(host, '_bind', None)) or not callable(getattr(host, '_descriptor_context', None)) or (not callable(getattr(host, '_archive_remove', None))) or (not hasattr(host, 'descriptor_object')) or (not hasattr(host, 'descriptor_vtable')) or (not hasattr(host, 'vtable')) or (not isinstance(getattr(host, 'functions', None), list)) or (getattr(host, 'archives', None) is None) or (getattr(host, 'archives', None).entries != {}):
        raise ValueError('XP1 archive host state is not empty/retained as required')
    if host.pointer != C.addressof(host.object) or int(host.object[0] or 0) != C.addressof(host.vtable) or int(host.descriptor_object[0] or 0) != C.addressof(host.descriptor_vtable) or (len(host.vtable) <= 264 // 8) or (len(host.descriptor_vtable) <= 8 // 8):
        raise ValueError('XP1 archive host/descriptor object layout mismatch')
    retained = {int(C.cast(fn, C.c_void_p).value or 0) for fn in host.functions}
    old_pointers = (int(host.vtable[264 // 8] or 0), int(host.descriptor_vtable[0] or 0), int(host.descriptor_vtable[1] or 0))
    if not all((pointer and pointer in retained for pointer in old_pointers)):
        raise ValueError('XP1 prebinding callbacks are not retained by the owned host')

def install_xp1_archive_access(host, core_base, teardown_receipt, *, project_root, emit=None):
    """Install the proven XP1 host getter and +8 remover only.

    Descriptor-interface +0 is deliberately not rebound: it remains the
    Init-installed unsupported/fatal callback because XP1's registration
    call/AL-to-active behavior has not been proven.
    """
    source = verify_source(project_root)
    _check_host(host)
    if type(core_base) is not int or not 0 < core_base <= 18446744073709551615:
        raise ValueError('Invalid XP1 core module base')
    _check_teardown_receipt(teardown_receipt, host, core_base)
    host_before = tuple((int(value or 0) for value in host.vtable))
    descriptor_before = tuple((int(value or 0) for value in host.descriptor_vtable))
    unsupported_register = descriptor_before[0]
    unsupported_remove = descriptor_before[1]
    getter_before = host_before[264 // 8]
    if not unsupported_register or not unsupported_remove or (not getter_before):
        raise ValueError('XP1 Init did not leave all unapproved archive slots bound')
    state = {'getter_calls': 0, 'remove_calls': 0, 'descriptor_register_slot_pointer': unsupported_register, 'getter_previous_pointer': getter_before, 'remove_previous_pointer': unsupported_remove, 'host_pointer': host.pointer, 'descriptor_pointer': C.addressof(host.descriptor_object), 'functions_start': len(host.functions), 'registration_supported': False, 'eligible_for_training': False}

    def getter(this):
        state['getter_calls'] += 1
        return host._descriptor_context(this)

    def remove(this, descriptor):
        state['remove_calls'] += 1
        return host._archive_remove(this, descriptor)
    try:
        host._bind(host.descriptor_vtable, 8, None, [C.c_void_p, C.c_void_p], remove)
        host._bind(host.vtable, 264, C.c_void_p, [C.c_void_p], getter)
    except BaseException:
        host.descriptor_vtable[8 // 8] = unsupported_remove
        host.vtable[264 // 8] = getter_before
        raise
    host_after = tuple((int(value or 0) for value in host.vtable))
    descriptor_after = tuple((int(value or 0) for value in host.descriptor_vtable))
    allowed_host = {264 // 8}
    allowed_descriptor = {8 // 8}
    if len(host_after) != len(host_before) or any((host_after[i] != host_before[i] for i in range(len(host_before)) if i not in allowed_host)) or len(descriptor_after) != len(descriptor_before) or any((descriptor_after[i] != descriptor_before[i] for i in range(len(descriptor_before)) if i not in allowed_descriptor)) or (descriptor_after[0] != unsupported_register) or (not host_after[264 // 8]) or (not descriptor_after[1]):
        raise RuntimeError('XP1 archive adapter changed a callback outside its two proven slots')
    state['descriptor_register_slot_pointer_after'] = descriptor_after[0]
    state['getter_pointer_after'] = host_after[264 // 8]
    state['remove_pointer_after'] = descriptor_after[1]
    state['installed'] = True
    state['source'] = source
    host._xp1_archive_access_binding = state
    if emit is not None:
        emit('xp1_archive_access_installed', receipt=xp1_archive_registry_receipt(host))
    return xp1_archive_registry_receipt(host)

def xp1_archive_registry_receipt(host) -> dict:
    """Return a detached diagnostic view of this adapter's counters/registry."""
    state = getattr(host, '_xp1_archive_access_binding', None)
    if type(state) is not dict or state.get('installed') is not True:
        raise ValueError('XP1 archive access adapter is not installed')
    entries = getattr(getattr(host, 'archives', None), 'entries', None)
    if type(entries) is not dict:
        raise ValueError('XP1 archive registry state is unavailable')
    copied = [{'key': int(key), 'pointer': int(pointer)} for key, pointer in sorted(entries.items())]
    return {'schema': 'civ6rl.native_xp1_archive_access_receipt.v1', 'installed': True, 'getter_calls': int(state['getter_calls']), 'remove_calls': int(state['remove_calls']), 'registered_count': len(copied), 'entries': copied, 'descriptor_register_slot_0_unchanged': int(host.descriptor_vtable[0] or 0) == state['descriptor_register_slot_pointer'], 'registration_supported': False, 'eligible_for_training': False}
__all__ = ['verify_source', 'install_xp1_archive_access', 'xp1_archive_registry_receipt']

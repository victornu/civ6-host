"""Fail-closed XP1 Prepare type registry; callback addresses stay opaque."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
CONTRACT_REL = 'work/native-xp1-prepare-contract817/analysis817.json'
CONTRACT_SHA256 = '4eced64ea188219b218faaecf1b86ecce71b695f77453765ff48dfe51e12db02'
CONTRACT_MANIFEST_REL = 'work/native-xp1-prepare-contract817/manifest817.json'
CONTRACT_MANIFEST_SHA256 = '6a8af754b5122ad367e5209e06daf6a5fefb123d5ad7c034cfd3b03c3c58db7c'
HOST_SHA256 = 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6'
INIT_SHA256 = '6e3172c2a69168bda640aba91284d828b89e0b1b5e02b2e5ecc417d6b08f547e'
TEARDOWN_SHA256 = '3fcde8a9ab8f26363ba44ffa7fba60661c1bdd2439587732ac74abf2e0df4b3d'
TEARDOWN_PROOF_SHA256 = '74fcd326dcc48c7b3b4e04ed02941083cf99a31bb1e3b3ae897f79dea5f60728'
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
TYPE_NAMES = ('Unit', 'Formation', 'City::Instance', 'Trade::Edge', 'Control::Contract', 'District::Instance', 'AI::CityBuild', 'BehaviorTree', 'AI::Operation', 'DynamicModifier')
CALLBACK_RVAS = ((5676688, 5676896), (5676576, 5676816), (1104448, 1106960), (3123072, 3123664), (3456080, 3456688), (1104576, 1107040), (3299392, 3299616), (4790432, 4790720), (4194912, 4195280), (8337232, 8341152))
TEARDOWN_INSTALL_SCHEMA = 'civ6rl.native_xp1_teardown_adapter_installation.v1'
REGISTRY_SCHEMA = 'civ6rl.native_xp1_prepare_type_registry.v1'

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _read_pinned_json(path: Path, expected: str):
    if _sha256(path) != expected:
        raise ValueError(f'Pinned XP1 Prepare contract changed: {path}')
    value = json.loads(_resolve_resource_path(path).read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError('XP1 Prepare contract must be an object')
    return value

def verify_source(project_root) -> dict:
    root = _resolve_resource_path(_resolve_resource_path(Path(project_root))).resolve()
    pins = {'civ6rl/native_host.py': HOST_SHA256, 'civ6rl/native_xp1_context_init.py': INIT_SHA256, 'civ6rl/native_xp1_teardown_adapter.py': TEARDOWN_SHA256, 'evidence/native-xp1-teardown818-v2.json': TEARDOWN_PROOF_SHA256}
    observed = {}
    for rel, expected in pins.items():
        actual = _sha256(root / rel)
        if actual != expected:
            raise ValueError(f'XP1 Prepare host source changed: {rel}')
        observed[rel] = actual
    manifest = _read_pinned_json(root / CONTRACT_MANIFEST_REL, CONTRACT_MANIFEST_SHA256)
    proof = _read_pinned_json(root / CONTRACT_REL, CONTRACT_SHA256)
    if manifest.get('schema') != 'civ6rl.native_xp1_prepare_contract817.manifest.v1' or manifest.get('files', {}).get('analysis817.json') != CONTRACT_SHA256 or proof.get('schema') != 'civ6rl.native_xp1_prepare_contract817.v1':
        raise ValueError('XP1 Prepare source proof identity changed')
    rows = proof.get('registrations', {}).get('requests')
    if type(rows) is not list or len(rows) != len(TYPE_NAMES):
        raise ValueError('XP1 Prepare registration rows are incomplete')
    for i, (row, name, pair) in enumerate(zip(rows, TYPE_NAMES, CALLBACK_RVAS)):
        if type(row) is not dict or row.get('name') != name or row.get('callback_pair_rva') != [hex(pair[0]), hex(pair[1])]:
            raise ValueError(f'XP1 Prepare row {i} differs from pinned RVAs/order')
    if proof.get('binary', {}).get('sha256') != XP1_CORE_SHA256:
        raise ValueError('XP1 Prepare binary identity changed')
    reg = proof.get('registrations', {})
    if reg.get('host_vtable_slot') != '0x110' or reg.get('registration_interface_vtable_slot') != '0' or reg.get('count') != 10 or (reg.get('same_order_as_bootstrap') is not True):
        raise ValueError('XP1 Prepare call shape differs from pinned source')
    return {'schema': 'civ6rl.native_xp1_prepare_type_registry_source.v1', 'source_sha256': observed, 'contract_sha256': CONTRACT_SHA256, 'contract_manifest_sha256': CONTRACT_MANIFEST_SHA256, 'callback_rvas': [[hex(a), hex(b)] for a, b in CALLBACK_RVAS], 'type_names': list(TYPE_NAMES)}

def _fatal(host, message, **fields):
    host._fatal(message, **fields)
    raise RuntimeError('DiagnosticHost._fatal unexpectedly returned')

def _pointer(value, what):
    if type(value) is not int or not 0 < value <= 18446744073709551615:
        raise ValueError(f'{what} must be a nonzero unsigned 64-bit pointer')
    return value

def install_prepare_type_registry(host, core_base, teardown_receipt, *, project_root) -> dict:
    """Bind only registrar+0 after 821 and validate all ten ordered registrations.

    The original host callback copies each verified descriptor into TypeRegistry
    and frees its allocation through the retained XP1 _aligned_free from 821.
    Callback addresses are stored as opaque integers; this module never invokes them.
    """
    from civ6_host.runtime.xp1_saved_load import teardown_core_identity
    source = verify_source(project_root)
    base = _pointer(core_base, 'XP1 core base')
    max_rva = max((max(pair) for pair in CALLBACK_RVAS))
    if base > 18446744073709551615 - max_rva:
        raise ValueError('XP1 core base plus callback RVA overflows an unsigned 64-bit address')
    if type(teardown_receipt) is not dict or teardown_receipt.get('schema') != TEARDOWN_INSTALL_SCHEMA:
        raise ValueError('XP1 Prepare registry requires the successful 821 teardown binding')
    if getattr(host, '_xp1_teardown_binding', None) is not teardown_receipt or teardown_receipt.get('installed') is not True or teardown_receipt.get('core_sha256') != teardown_core_identity(host) or (teardown_receipt.get('core_module_base') != hex(base)) or (teardown_receipt.get('host_pointer') != hex(getattr(host, 'pointer', 0))) or (teardown_receipt.get('registrar_remove_slot') != '0x08') or (teardown_receipt.get('type_names_allowed') != list(TYPE_NAMES)) or (teardown_receipt.get('callback_references_retained') is not True) or (teardown_receipt.get('destroy_called') is not False) or (teardown_receipt.get('aligned_free_function_pointer') in (None, '0x0')) or (teardown_receipt.get('aligned_free_iat_va') != hex(base + 8771192)):
        raise ValueError('XP1 Prepare binding does not match the retained 821 XP1 host/free owner')
    adapter_source = teardown_receipt.get('source')
    if type(adapter_source) is not dict or adapter_source.get('schema') != 'civ6rl.native_xp1_teardown_adapter_source.v1' or adapter_source.get('proof_sha256') != TEARDOWN_PROOF_SHA256 or (adapter_source.get('prepare_proof_sha256') != CONTRACT_SHA256):
        raise ValueError('XP1 Prepare binding lacks the source-verified 821 proof receipt')
    if not callable(getattr(host, 'native_aligned_free', None)):
        raise ValueError('XP1 Prepare registry requires the retained XP1 aligned_free callback')
    if getattr(host, '_xp1_prepare_registry_binding', None) is not None or not callable(getattr(host, '_register_type', None)) or (not callable(getattr(host, '_copy_type_name', None))) or (not callable(getattr(host, '_fatal', None))):
        raise ValueError('XP1 host registrar behavior is missing or already wrapped')
    try:
        from civ6_host.runtime.native.native_host import BOOTSTRAP_TYPE_NAMES
        if frozenset(TYPE_NAMES) != BOOTSTRAP_TYPE_NAMES or host.types.allowed_names != BOOTSTRAP_TYPE_NAMES:
            raise ValueError('Host TypeRegistry allowlist differs from pinned XP1 Prepare names')
        if host.types.entries:
            raise ValueError('XP1 Prepare type registry must start empty')
    except AttributeError as exc:
        raise ValueError('XP1 host has no validated TypeRegistry') from exc
    if not hasattr(host, 'registrar_object') or not hasattr(host, 'registrar_vtable') or int(host.registrar_object[0] or 0) != C.addressof(host.registrar_vtable) or (len(host.registrar_vtable) < 2):
        raise ValueError('XP1 registrar interface layout is not the pinned host layout')
    old_register = int(host.registrar_vtable[0] or 0)
    retained = {C.cast(fn, C.c_void_p).value for fn in getattr(host, 'functions', ())}
    if not old_register or old_register not in retained:
        raise ValueError('XP1 registrar+0 does not point to a retained host callback')
    old_remove = int(host.registrar_vtable[1] or 0)
    if not old_remove or old_remove not in retained:
        raise ValueError('XP1 registrar+0x08 remove callback is not retained by 821')
    state = {'next_index': 0, 'original': host._register_type, 'receipt': None}

    def register(this, descriptor, callback1, callback2):
        index = state['next_index']
        if this != C.addressof(host.registrar_object):
            _fatal(host, 'XP1 Prepare registrar received wrong interface pointer')
        if index >= len(TYPE_NAMES):
            _fatal(host, 'XP1 Prepare registered more than ten source-proven types', index=index)
        try:
            _, name = host._copy_type_name(descriptor)
        except BaseException as exc:
            _fatal(host, 'XP1 Prepare received invalid native type string', index=index, error=repr(exc))
        expected_name = TYPE_NAMES[index]
        pair = (base + CALLBACK_RVAS[index][0], base + CALLBACK_RVAS[index][1])
        if name != expected_name or type(callback1) is not int or type(callback2) is not int or ((callback1, callback2) != pair):
            _fatal(host, 'XP1 Prepare name/callback pair differs from source-pinned order', index=index, expected_name=expected_name, actual_name=name, expected_callbacks=[hex(x) for x in pair], actual_callbacks=[hex(x) if type(x) is int and x else None for x in (callback1, callback2)])
        state['original'](this, descriptor, callback1, callback2)
        from civ6_host.runtime.native.native_host import type_name_hash
        expected_entry = (expected_name, pair[0], pair[1])
        if host.types.entries.get(type_name_hash(expected_name)) != expected_entry:
            _fatal(host, 'XP1 TypeRegistry did not retain the exact verified callback pair', index=index)
        state['next_index'] = index + 1
        state['receipt']['registered_count'] = index + 1
        state['receipt']['next_expected'] = TYPE_NAMES[index + 1] if index + 1 < len(TYPE_NAMES) else None
    host._bind(host.registrar_vtable, 0, None, [C.c_void_p] * 4, register)
    receipt = {'schema': REGISTRY_SCHEMA, 'installed': True, 'core_base': hex(base), 'registrar_register_slot': '0x00', 'registrar_remove_slot': '0x08', 'type_names': list(TYPE_NAMES), 'expected_callback_rvas': [[hex(a), hex(b)] for a, b in CALLBACK_RVAS], 'expected_count': 10, 'registered_count': 0, 'next_expected': TYPE_NAMES[0], 'registered_function_pointers_invoked': False, 'native_string_allocator': '821 XP1 _aligned_free', 'source': source, 'previous_register_slot_pointer': hex(old_register), 'remove_slot_pointer_unchanged': hex(old_remove)}
    state['receipt'] = receipt
    host._xp1_prepare_registry_binding = {'receipt': receipt, 'state': state, 'callback': register}
    return receipt

def prepare_registration_receipt(host) -> dict:
    binding = getattr(host, '_xp1_prepare_registry_binding', None)
    if type(binding) is not dict or type(binding.get('receipt')) is not dict:
        raise ValueError('XP1 Prepare type registry is not installed')
    state = binding['state']
    index = state['next_index']
    if index != len(TYPE_NAMES):
        raise ValueError(f'XP1 Prepare returned after {index}/{len(TYPE_NAMES)} registered types')
    if len(host.types.entries) != len(TYPE_NAMES):
        raise ValueError('XP1 Prepare TypeRegistry entry count differs from ten')
    out = dict(binding['receipt'])
    out.update({'registered_count': index, 'next_expected': None, 'order_complete': True, 'registered_function_pointers_invoked': False, 'registry_entry_count': len(host.types.entries)})
    return out
__all__ = ['verify_source', 'install_prepare_type_registry', 'prepare_registration_receipt', 'TYPE_NAMES', 'CALLBACK_RVAS']

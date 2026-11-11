"""XP1 Destroy-only registrar binding installed after verified successful Init."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
XP1_CONFIG_SHA256 = '95b68bf37549690e6771925cfa189da87e810c94a09c6508059fa3f6583f3faf'
XP1_GAMEPLAY_SHA256 = '637f3f53b4d8609bc0325de5dac2008f80f7a7437d3ef4b6d26d31576563717e'
TEARDOWN_PROOF_SHA256 = '74fcd326dcc48c7b3b4e04ed02941083cf99a31bb1e3b3ae897f79dea5f60728'
TEARDOWN_PROOF_RELATIVE = 'evidence/native-xp1-teardown818-v2.json'
PREPARE_PROOF_SHA256 = '4eced64ea188219b218faaecf1b86ecce71b695f77453765ff48dfe51e12db02'
DESTROY_REPORT_SHA256 = '12c39aa5159223eef2a1ae64b2553ce0f2d00d81c61af589801a111c30b8f585'
DESTROY_LEDGER_SHA256 = '2f6d694ad5fa93e8ad84ff002e695d2c521ab623815bb9c079c6bcb1df922732'
ALIGNED_FREE_IAT_RVA = 8771192
EXPECTED_REBOUND_COUNT = 218
EXPECTED_REBOUND_SHA256 = 'd42b63ed06c872eac7194058222b48698a09d579873338dc2796185c3994a0a3'
TYPE_NAMES = ('Unit', 'Formation', 'City::Instance', 'Trade::Edge', 'Control::Contract', 'District::Instance', 'AI::CityBuild', 'BehaviorTree', 'AI::Operation', 'DynamicModifier')
SOURCE_PINS = {'civ6rl/native_host.py': 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6', 'civ6rl/native_xp1_context_init.py': '6e3172c2a69168bda640aba91284d828b89e0b1b5e02b2e5ecc417d6b08f547e', 'civ6rl/native_core_context_profiles.py': '8f5aed71ecf614d6fa25d52b94b7fec4a0bb4bcec190f8f144b04c4cf541d676'}

def _sha256(path):
    h = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _load_json(path, expected):
    if _sha256(path) != expected:
        raise ValueError(f'Pinned XP1 teardown proof changed: {path}')
    value = json.loads(_resolve_resource_path(_resolve_resource_path(Path(path))).read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError('XP1 teardown proof must be an object')
    return value

def _verify_teardown_proof(root):
    path = _resolve_resource_path(Path(root)) / TEARDOWN_PROOF_RELATIVE
    proof = _load_json(path, TEARDOWN_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_xp1_teardown_contract818.v1' or proof.get('image', {}).get('sha256') != XP1_CORE_SHA256 or proof.get('registration_source', {}).get('sha256') != PREPARE_PROOF_SHA256:
        raise ValueError('XP1 Destroy/Prepare proof identity changed')
    witness = proof.get('observed_failure_context', {})
    if witness.get('supervisor_report_sha256') != DESTROY_REPORT_SHA256 or witness.get('event_ledger_sha256') != DESTROY_LEDGER_SHA256 or witness.get('destroy_fatal_event', {}).get('slot') != '0x110':
        raise ValueError('XP1 unsupported Destroy witness changed')
    thunk = proof.get('destroy_export', {}).get('window', {}).get('instructions', [])
    if not any((r.get('va') == '0x1806384d0' and r.get('bytes') == 'e96b46e8ff' and (r.get('text') == 'jmp 0x1804bcb40') for r in thunk)):
        raise ValueError('XP1 Destroy export thunk changed')
    rows = proof.get('ordered_type_removals')
    if type(rows) is not list or len(rows) != len(TYPE_NAMES):
        raise ValueError('XP1 Destroy removal list incomplete')
    for n, (row, name) in enumerate(zip(rows, TYPE_NAMES)):
        a = row.get('host_registrar_accessor_call', {})
        r = row.get('interface_remove_call', {})
        if row.get('ordinal') != n or row.get('name') != name or a.get('bytes') != 'ff9010010000' or (a.get('text') != 'call qword ptr [rax + 0x110]') or (r.get('bytes') != '41ff5008') or (r.get('text') != 'call qword ptr [r8 + 8]'):
            raise ValueError('XP1 Destroy callback slots/names/order changed')
    imp = proof.get('allocator_imports', {}).get('0x18085d678', {})
    if imp != {'dll': 'api-ms-win-crt-heap-l1-1-0.dll', 'iat_va': '0x18085d678', 'name': '_aligned_free'}:
        raise ValueError('XP1 aligned-free import proof changed')
    return {'proof_path': str(path), 'proof_sha256': TEARDOWN_PROOF_SHA256, 'prepare_proof_sha256': PREPARE_PROOF_SHA256, 'destroy_report_sha256': DESTROY_REPORT_SHA256, 'destroy_ledger_sha256': DESTROY_LEDGER_SHA256, 'type_names': list(TYPE_NAMES)}

def verify_source(project_root):
    root = _resolve_resource_path(_resolve_resource_path(Path(project_root))).resolve()
    hashes = {}
    for relative, expected in SOURCE_PINS.items():
        actual = _sha256(root / relative)
        if actual != expected:
            raise ValueError(f'XP1 teardown dependency changed: {relative}')
        hashes[relative] = actual
    return {'schema': 'civ6rl.native_xp1_teardown_adapter_source.v1', 'project_root': str(root), 'source_sha256': hashes, **_verify_teardown_proof(root)}

def _check_init_receipt(receipt, host, *, candidate_bundle=None, core_sha256=XP1_CORE_SHA256):
    if type(receipt) is not dict or receipt.get('schema') != 'civ6rl.native_xp1_context_init_receipt.v1':
        raise ValueError('XP1 Destroy binding requires the official Init receipt')
    if receipt.get('status') != 'xp1_context_initialized_diagnostic_only' or receipt.get('core_sha256') != core_sha256 or receipt.get('init_called') is not True or (receipt.get('init_returned') is not True) or (receipt.get('initialized_after') is not True) or (receipt.get('host_setter_called') is not True) or (receipt.get('context_may_require_destroy') is not True) or (receipt.get('game_created') is not False) or (receipt.get('newgame_called') is not False) or (receipt.get('prepare_called') is not False) or (receipt.get('simulation_ready') is not False) or (receipt.get('eligible_for_training') is not False):
        raise ValueError('XP1 Destroy binding refuses failed or expanded-scope Init')
    configuration_sha, gameplay_sha = (XP1_CONFIG_SHA256, XP1_GAMEPLAY_SHA256)
    if candidate_bundle is not None:
        from civ6_host.runtime.xp1_saved_init import validate_init_receipt_binding
        binding = validate_init_receipt_binding(candidate_bundle, host, receipt)
        configuration_sha = binding['databases']['configuration']['sha256']
        gameplay_sha = binding['databases']['gameplay']['sha256']
    inputs = receipt.get('inputs')
    connections = receipt.get('connections')
    if type(inputs) is not dict or inputs.get('configuration_sha256') != configuration_sha or inputs.get('gameplay_sha256') != gameplay_sha or (type(connections) is not dict) or (connections.get('configuration_slot') != 'inner+0x50') or (connections.get('configuration_nonnull') is not True) or (connections.get('gameplay_slot') != 'inner+0x58') or (connections.get('gameplay_nonnull') is not True):
        raise ValueError('XP1 Init receipt lacks non-null configuration/gameplay connections')
    surface = receipt.get('host_callback_surface')
    if type(surface) is not dict or '0x110' in surface.get('preserved_allowlist', {}).get('host', []):
        raise ValueError('XP1 Init receipt does not restrict host+0x110')
    from civ6_host.runtime.native.native_xp1_context_init import XP1_HOST_VTABLE_ALLOWLIST
    from civ6_host.runtime.native.native_xp1_context_init import XP1_AUX_VTABLE_ALLOWLIST
    from civ6_host.runtime.native.native_xp1_context_init import XP1_LOGGER_VTABLE_ALLOWLIST
    from civ6_host.runtime.native.native_xp1_context_init import _require_exact_xp1_declarations
    tables = (('host', host.vtable, XP1_HOST_VTABLE_ALLOWLIST), ('auxiliary', host.aux_vtable, XP1_AUX_VTABLE_ALLOWLIST), ('logger', host.logger_vtable, XP1_LOGGER_VTABLE_ALLOWLIST), ('type registrar', host.registrar_vtable, set()), ('autoarchive registry', host.descriptor_vtable, set()))
    rebound = [f'{interface}+{hex(i * 8)}' for interface, table, allowed in tables for i in range(len(table)) if i * 8 not in allowed]
    count = len(rebound)
    digest = hashlib.sha256('\n'.join(rebound).encode('ascii')).hexdigest()
    if count != EXPECTED_REBOUND_COUNT or digest != EXPECTED_REBOUND_SHA256 or surface.get('rebound_unsupported_count') != count or (surface.get('rebound_unsupported_sha256') != digest):
        raise ValueError('Init receipt does not match the derived restricted callback surface')
    observed = _require_exact_xp1_declarations(host)
    if receipt.get('event_filter_declarations') != observed:
        raise ValueError('Init receipt differs from retained XP1 event declarations')

def _check_host(host):
    from civ6_host.runtime.native.native_host import BOOTSTRAP_TYPE_NAMES
    from civ6_host.runtime.native.native_host import DiagnosticHost
    if getattr(host, '_xp1_teardown_binding', None) is not None:
        raise ValueError('XP1 Destroy callbacks were already installed')
    if type(host) is not DiagnosticHost:
        raise ValueError('XP1 Destroy adapter accepts only the owned DiagnosticHost')
    if not isinstance(getattr(host, 'functions', None), list) or not hasattr(host, 'object') or (not hasattr(host, 'vtable')) or (not hasattr(host, 'aux_object')) or (not hasattr(host, 'aux_vtable')) or (not hasattr(host, 'logger_object')) or (not hasattr(host, 'logger_vtable')) or (not hasattr(host, 'registrar_object')) or (not hasattr(host, 'registrar_vtable')) or (not hasattr(host, 'descriptor_vtable')) or (getattr(host, 'native_aligned_free', None) is not None) or (getattr(getattr(host, 'types', None), 'allowed_names', None) != BOOTSTRAP_TYPE_NAMES):
        raise ValueError('XP1 host ownership/callback registry state is not eligible')
    if host.pointer != C.addressof(host.object) or int(host.object[0] or 0) != C.addressof(host.vtable) or int(host.registrar_object[0] or 0) != C.addressof(host.registrar_vtable) or (len(host.vtable) <= 272 // 8) or (len(host.registrar_vtable) <= 8 // 8):
        raise ValueError('XP1 host interface pointer/layout mismatch')
    if any((not callable(getattr(host, n, None)) for n in ('_bind', '_registrar', '_remove_type'))):
        raise ValueError('XP1 host does not expose retained registrar callbacks')

def _default_owner_verifier(address, module_paths):
    if os.name != 'nt':
        raise RuntimeError('XP1 aligned-free owner check requires Windows')
    k = C.WinDLL('kernel32', use_last_error=True)
    gm = k.GetModuleHandleExW
    gm.argtypes = [C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p)]
    gm.restype = C.c_int
    module = C.c_void_p()
    if not gm(6, C.c_void_p(address), C.byref(module)):
        raise OSError(C.get_last_error(), 'GetModuleHandleExW failed')
    gn = k.GetModuleFileNameW
    gn.argtypes = [C.c_void_p, C.c_wchar_p, C.c_uint32]
    gn.restype = C.c_uint32
    buf = C.create_unicode_buffer(32768)
    size = gn(module, buf, len(buf))
    if not size or size >= len(buf):
        raise OSError(C.get_last_error(), 'GetModuleFileNameW failed')
    owner = _resolve_resource_path(_resolve_resource_path(Path(buf.value))).resolve()
    loaded = {os.path.normcase(str(_resolve_resource_path(_resolve_resource_path(Path(p))).resolve())) for p in module_paths}
    if os.path.normcase(str(owner)) not in loaded:
        raise ValueError('_aligned_free owner is not an enumerated loaded module')
    gp = k.GetProcAddress
    gp.argtypes = [C.c_void_p, C.c_char_p]
    gp.restype = C.c_void_p
    if int(gp(module, b'_aligned_free') or 0) != address:
        raise ValueError('IAT pointer differs from owner _aligned_free export')
    return {'module_path': str(owner), 'export': '_aligned_free', 'address': hex(address)}

def _aligned_free_callable(address):
    if type(address) is not int or not 0 < address <= 18446744073709551615:
        raise ValueError('Invalid XP1 aligned-free pointer')
    return C.CFUNCTYPE(None, C.c_void_p)(address)

def install_xp1_teardown_callbacks(core, context, host, init_receipt, *, project_root, module_paths, read=None, emit=None, profile_loader=None, modules_validator=None, context_validator=None, initialized_getter=None, owner_verifier=None, aligned_free_factory=None, candidate_bundle=None):
    """Install only XP1 Destroy callbacks after verified Init; never calls Destroy."""
    from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_context
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_modules
    source = verify_source(project_root)
    _check_host(host)
    if type(context) is not int or context <= 0:
        raise ValueError('Missing retained XP1 context address')
    profile_loader = profile_loader or profile_for_core
    modules_validator = modules_validator or validate_loaded_modules
    context_validator = context_validator or validate_loaded_context
    owner_verifier = owner_verifier or _default_owner_verifier
    aligned_free_factory = aligned_free_factory or _aligned_free_callable
    from civ6_host.runtime.xp1_saved_load import select_context
    profile = select_context(core, candidate_bundle, profile_loader)
    _check_init_receipt(init_receipt, host, candidate_bundle=candidate_bundle,
                        core_sha256=profile.core_sha256)
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0:
        raise ValueError('Missing actual loaded XP1 GameCore base')
    modules_validator(profile, module_paths)
    if read is None:
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
    context_validator(profile, base, context, read)
    if initialized_getter is None:
        from civ6_host.runtime.native.native_xp1_context_init import XP1_SLOTS
        from civ6_host.runtime.native.native_xp1_context_init import _native_virtual
        initialized = _native_virtual(core, context, 56, XP1_SLOTS[56], C.c_bool)(context)
    else:
        initialized = initialized_getter(core, context)
    if type(initialized) is not bool or initialized is not True:
        raise ValueError('XP1 initialized-state getter is not true before teardown binding')
    expected = {10430016: host.pointer, 10430024: C.addressof(host.aux_object), 10430032: C.addressof(host.logger_object)}
    observed = {}
    for rva, pointer in expected.items():
        actual = struct.unpack('<Q', read(base + rva, 8))[0]
        if actual != pointer:
            raise ValueError('XP1 host globals no longer reference retained interfaces')
        observed[hex(rva)] = hex(actual)
    iat_va = base + ALIGNED_FREE_IAT_RVA
    free_address = struct.unpack('<Q', read(iat_va, 8))[0]
    if not free_address:
        raise ValueError('XP1 _aligned_free IAT entry is null')
    owner = owner_verifier(free_address, module_paths)
    free_fn = aligned_free_factory(free_address)
    if not callable(free_fn):
        raise ValueError('XP1 aligned-free factory did not return a callable')
    old_host = int(host.vtable[272 // 8] or 0)
    old_remove = int(host.registrar_vtable[8 // 8] or 0)
    host.native_aligned_free = free_fn
    host._bind(host.registrar_vtable, 8, None, [C.c_void_p, C.c_void_p], host._remove_type)
    host._bind(host.vtable, 272, C.c_void_p, [C.c_void_p], host._registrar)
    receipt = {'schema': 'civ6rl.native_xp1_teardown_adapter_installation.v1', 'installed': True, 'core_sha256': profile.core_sha256, 'core_path': str(profile.core_path), 'core_module_base': hex(base), 'context_pointer': hex(context), 'initialized_getter_observed': True, 'init_receipt_schema': init_receipt['schema'], 'host_pointer': hex(host.pointer), 'host_globals_verified': observed, 'host_slot': '0x110', 'registrar_remove_slot': '0x08', 'type_names_allowed': list(TYPE_NAMES), 'previous_host_slot_pointer': hex(old_host), 'previous_remove_slot_pointer': hex(old_remove), 'aligned_free_iat_va': hex(iat_va), 'aligned_free_function_pointer': hex(free_address), 'aligned_free_runtime_owner': owner, 'callback_references_retained': True, 'destroy_called': False, 'game_created': False, 'newgame_called': False, 'eligible_for_training': False, 'source': source}
    host._xp1_teardown_binding = receipt
    if emit is not None:
        emit('xp1_teardown_adapter_installed', receipt=receipt)
    return receipt
__all__ = ['verify_source', 'install_xp1_teardown_callbacks', 'SOURCE_PINS', 'TEARDOWN_PROOF_SHA256', 'TYPE_NAMES', 'ALIGNED_FREE_IAT_RVA']

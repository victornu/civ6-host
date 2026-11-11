"""XP1 descriptor+0 registration binding, separate from getter/remove access.

Install after the verified XP1 Init/teardown binding and 844 getter/remove
adapter, before Prepare. The callback forwards the real Base registry boolean
unchanged; GameCore, not this adapter, sets descriptor+0x48 when AL is true.
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
AUDIT843_SHA256 = 'bd9529daeb7872ea325025ff3630a69f4217897d518a0fe62e468cb3123c05c1'
AUDIT843_RELATIVE = 'work/native-xp1-descriptor843/analysis843-v3.json'
REGISTRATION_PROOF_SHA256 = 'e6d577442249af6a18e94a895ef02e1744afe422624c3a5c293bbd2762e68e23'
REGISTRATION_PROOF_RELATIVE = 'work/native-xp1-archive-register846/analysis846-v2.json'
HOST_PROOF_SHA256 = '95d3e1fd0b7cddc838a4a59eb61bdf409325be5338e5e170d801c4f5fa5cd937'
HOST_PROOF_RELATIVE = 'work/native-archive-host-semantics848/analysis848-v3.json'
ACCESS_MODULE_SHA256 = '3e68f86916a87232e305dc331e80e41b6661b3652b8d5e103a5d2c3a1cde96a7'
ORIGINAL_ARCHIVE_HOST_SHA256 = 'f654046847e70b3306e2a2b371a3c39268d35d8e3b1639ab2faeedbe005bbec1'
SOURCE_PINS = {'work/native-tuner-ablation888/host-revision888.json': '2430cf7849d48f4badbff6e78ab787a2f9ec8f6d2e55fed099cc5290eaa4704e', 'civ6rl/native_host.py': 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6', 'civ6rl/native_xp1_context_init.py': '6e3172c2a69168bda640aba91284d828b89e0b1b5e02b2e5ecc417d6b08f547e', 'civ6rl/native_core_context_profiles.py': '8f5aed71ecf614d6fa25d52b94b7fec4a0bb4bcec190f8f144b04c4cf541d676', 'civ6rl/native_xp1_teardown_adapter.py': '3fcde8a9ab8f26363ba44ffa7fba60661c1bdd2439587732ac74abf2e0df4b3d', 'civ6rl/native_xp1_archive_access.py': ACCESS_MODULE_SHA256}

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def _pinned_json(root: Path, relative: str, expected: str) -> dict:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f'Pinned XP1 archive-registration proof changed: {relative}')
    value = json.loads(_resolve_resource_path(path).read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError('Pinned XP1 archive-registration proof is not an object')
    return value

def verify_source(project_root) -> dict:
    """Verify byte-pinned getter/remove and registration ABI before binding."""
    root = _resolve_resource_path(_resolve_resource_path(Path(project_root))).resolve()
    source_hashes = {}
    for relative, expected in SOURCE_PINS.items():
        actual = _sha256(root / relative)
        if actual != expected:
            raise ValueError(f'XP1 archive-registration dependency changed: {relative}')
        source_hashes[relative] = actual
    revision = _pinned_json(root, 'work/native-tuner-ablation888/host-revision888.json', SOURCE_PINS['work/native-tuner-ablation888/host-revision888.json'])
    if revision.get('old_sha256') != ORIGINAL_ARCHIVE_HOST_SHA256 or revision.get('new_sha256') != 'daac085ea97d94d2d9ceded07ef90bcc9d7a1f2ab6aa301f3efa155b8cea8db5' or revision.get('removing_exact_four_metadata_lines_restores_entire_original_text') is not True or (revision.get('archive_registry_and_all_other_host_behaviors_text_unchanged') is not True):
        raise ValueError('Native host archive source revision is not justified')
    getter_proof = _pinned_json(root, DESCRIPTOR_PROOF_RELATIVE, DESCRIPTOR_PROOF_SHA256)
    if getter_proof.get('schema') != 'civ6rl.native_xp1_descriptor842.static.v3' or getter_proof.get('binary', {}).get('sha256') != XP1_CORE_SHA256:
        raise ValueError('XP1 getter/remove proof identity changed')
    audit = _pinned_json(root, AUDIT843_RELATIVE, AUDIT843_SHA256)
    if audit.get('schema') != 'civ6rl.native_xp1_descriptor843.audit.v3' or audit.get('xp1_binary_sha256') != XP1_CORE_SHA256 or audit.get('confirmed_contract', {}).get('host_getter_slot') != '0x108' or (audit.get('confirmed_contract', {}).get('remove_slot') != '0x08') or (audit.get('unresolved_contract', {}).get('registration_slot') != '0x00') or ('unsupported/fatal' not in audit.get('unresolved_contract', {}).get('status', '')):
        raise ValueError('XP1 getter/remove audit is not the expected predecessor')
    proof = _pinned_json(root, REGISTRATION_PROOF_RELATIVE, REGISTRATION_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_xp1_archive_registration846.static.v1' or proof.get('binary', {}).get('sha256') != XP1_CORE_SHA256 or proof.get('predecessor', {}).get('sha256') != DESCRIPTOR_PROOF_SHA256:
        raise ValueError('XP1 registration proof identity changed')
    helper = proof.get('captures', {}).get('register_helper_83c820', {})
    helper_hex = helper.get('raw_hex')
    if helper.get('rva') != '0x83c820' or helper.get('sha256') != '37835c992dde1ce38148674011b2ec344d40dc8752488e06ef0dbeaa494eb4dc' or type(helper_hex) is not str or (len(helper_hex) != 190) or any((char not in '0123456789abcdef' for char in helper_hex)) or (hashlib.sha256(bytes.fromhex(helper_hex)).hexdigest() != helper['sha256']) or (helper.get('size') != 95):
        raise ValueError('XP1 descriptor register helper bytes changed')
    key_proof = proof.get('constructor_key_correction_v2', {})
    if key_proof.get('derived_little_endian_key') != '0x000000000004ffff' or key_proof.get('constructor_function', {}).get('sha256') != 'da8029db5296786d46db0c3292f9f35d7994de9131e6b433c10a6ef0c20710b0':
        raise ValueError('XP1 archive descriptor initial key proof changed')
    host_proof = _pinned_json(root, HOST_PROOF_RELATIVE, HOST_PROOF_SHA256)
    methods = {row.get('name'): row for row in host_proof.get('methods', [])}
    register = methods.get('register', {})
    remove = methods.get('remove', {})
    host_model = host_proof.get('source', {}).get('host_model', {})
    if host_proof.get('schema') != 'native_archive_host_semantics_review.v3' or host_proof.get('source', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or host_model.get('path') != 'civ6rl/native_host.py' or (host_model.get('sha256') != ORIGINAL_ARCHIVE_HOST_SHA256) or (register.get('rva') != '0x7f5e70') or (register.get('body_sha256') != 'd38d8e53e57c789ee66d886eac4fa3327b32bae4df294d6132a4e1006c87939c') or (remove.get('rva') != '0x7f78b0') or ([row.get('sha256') for row in remove.get('fragments', [])] != ['e68e2d34a6aec21b80966bacf9404ab83eab18d1d1120b95480443f48079e63f', '068cddbaa7ca94745cdd4c06443a49ae5c47f4e492f144ad10ad60aea9af53b7', '22fb3981e9484006abfbdf0d1023046a2e534a1a2c9cddc7cace38ac4f18139d']) or (register.get('conclusion', {}).get('same_key_same_pointer') != 'accepted/idempotent at this map layer; key lookup finds existing node, stored descriptor pointer equals incoming R14, existing node value is set to the same pointer, AL=1 at 0x7f68df') or (register.get('conclusion', {}).get('same_key_different_pointer') != 'rejected; pointer identity mismatch at 0x7f6123 enters collision diagnostic path 0x7f688c; bytes e9bcfcffff at 0x7f689c join false return 0x7f655d (bytes 32c0); existing node value is not overwritten') or (register.get('conclusion', {}).get('new_nonzero_key_nonnull_descriptor') != 'inserted; bucket-end path at 0x7f68e9 calls helper 0x7f15f0, then stores descriptor pointer and sets AL=1 at 0x7f6914') or (remove.get('conclusion', {}).get('key_found_pointer_match_active') != 'After the active-byte, nonzero-key and exact pointer-identity gates, helper 0x7f84d0 unlinks the matched node and decrements registry count. It passes the node and size 0x18 to helper 0x19d350; allocator/destructor semantics are not established here.'):
        raise ValueError('Pinned EXE ArchiveRegistry register/remove semantics changed')
    instructions = {row.get('rva'): row for row in proof.get('instruction_path', [])}
    expected = {'0x83c86a': ('ff10', 'call interface vtable+0x00 with RCX=interface, RDX=descriptor'), '0x83c86c': ('84c0', 'test AL,AL: callback return is consumed as boolean'), '0x83c86e': ('7404', 'AL==0 skips active-byte update'), '0x83c870': ('c6434801', 'AL!=0 stores byte 1 at descriptor+0x48')}
    for rva, (raw, operation) in expected.items():
        row = instructions.get(rva, {})
        if row.get('bytes') != raw or row.get('operation') != operation:
            raise ValueError(f'XP1 registration instruction changed at {rva}')
    conclusion = proof.get('conclusion', {})
    if conclusion.get('registration_slot_0') != 'source-proven at this XP1 call path: thiscall-like Win64 ABI RCX=interface, RDX=descriptor; AL is the boolean result; descriptor+0x48 becomes 1 only for nonzero AL.':
        raise ValueError('XP1 registration AL/active-byte contract changed')
    if proof.get('runtime_witness', {}).get('unsupported_slot') != '0x0':
        raise ValueError('XP1 registration witness boundary changed')
    return {'schema': 'civ6rl.native_xp1_archive_registration_source.v1', 'project_root': str(root), 'source_sha256': source_hashes, 'descriptor_proof_sha256': DESCRIPTOR_PROOF_SHA256, 'getter_remove_audit_sha256': AUDIT843_SHA256, 'registration_proof_sha256': REGISTRATION_PROOF_SHA256, 'archive_host_proof_sha256': HOST_PROOF_SHA256, 'xp1_core_sha256': XP1_CORE_SHA256, 'registration': {'interface_slot': '0x00', 'abi': 'bool(interface, descriptor)', 'return': 'preserve actual AL result', 'active_byte_writer': 'GameCore descriptor+0x48'}, 'eligible_for_training': False}

def _check_teardown_receipt(receipt, host, core_base):
    from civ6_host.runtime.xp1_saved_load import teardown_core_identity
    if type(receipt) is not dict or receipt.get('schema') != 'civ6rl.native_xp1_teardown_adapter_installation.v1':
        raise ValueError('XP1 archive registration requires the retained 821 teardown receipt')
    if getattr(host, '_xp1_teardown_binding', None) is not receipt:
        raise ValueError('XP1 teardown receipt is not retained by this host')
    if receipt.get('installed') is not True or receipt.get('core_sha256') != teardown_core_identity(host) or receipt.get('core_module_base') != hex(core_base) or (receipt.get('host_pointer') != hex(host.pointer)) or (receipt.get('initialized_getter_observed') is not True) or (receipt.get('destroy_called') is not False) or (receipt.get('game_created') is not False) or (receipt.get('newgame_called') is not False) or (receipt.get('eligible_for_training') is not False) or (receipt.get('callback_references_retained') is not True):
        raise ValueError('XP1 teardown receipt is mismatched, failed, or out of scope')
    globals_verified = receipt.get('host_globals_verified')
    expected_globals = {'0x9f2640': hex(host.pointer), '0x9f2648': hex(C.addressof(host.aux_object)), '0x9f2650': hex(C.addressof(host.logger_object))}
    if globals_verified != expected_globals:
        raise ValueError('XP1 retained host globals differ from the teardown receipt')

def _access_state(host):
    state = getattr(host, '_xp1_archive_access_binding', None)
    if type(state) is not dict or state.get('installed') is not True:
        raise ValueError('XP1 844 getter/remove adapter is not installed')
    from civ6_host.runtime.native.native_xp1_archive_access import xp1_archive_registry_receipt
    old_receipt = xp1_archive_registry_receipt(host)
    if old_receipt.get('registration_supported') is not False or old_receipt.get('descriptor_register_slot_0_unchanged') is not True or old_receipt.get('registered_count') != 0 or (old_receipt.get('entries') != []):
        raise ValueError('XP1 getter/remove adapter receipt is inconsistent or registry is not empty')
    if int(host.descriptor_vtable[0] or 0) != int(state.get('descriptor_register_slot_pointer', 0)) or int(host.vtable[264 // 8] or 0) != int(state.get('getter_pointer_after', 0)) or int(host.descriptor_vtable[1] or 0) != int(state.get('remove_pointer_after', 0)):
        raise ValueError('XP1 getter/remove callback pointers changed after 844 install')
    return (state, old_receipt)

def _check_host(host):
    from civ6_host.runtime.native.native_host import DiagnosticHost
    if type(host) is not DiagnosticHost:
        raise ValueError('XP1 archive registration accepts only the retained DiagnosticHost')
    if getattr(host, '_xp1_archive_registration_binding', None) is not None:
        raise ValueError('XP1 archive registration callback is already installed')
    if getattr(host, '_xp1_prepare_entered', False) is True:
        raise ValueError('XP1 archive registration must be installed before Prepare')
    if not callable(getattr(host, '_bind', None)) or not callable(getattr(host, '_archive_register', None)) or (not hasattr(host, 'descriptor_object')) or (not hasattr(host, 'descriptor_vtable')) or (not isinstance(getattr(host, 'functions', None), list)) or (getattr(getattr(host, 'archives', None), 'entries', None) != {}):
        raise ValueError('XP1 archive registration host/registry state is invalid or nonempty')
    if host.pointer != C.addressof(host.object) or int(host.object[0] or 0) != C.addressof(host.vtable) or int(host.descriptor_object[0] or 0) != C.addressof(host.descriptor_vtable) or (len(host.vtable) <= 264 // 8) or (len(host.descriptor_vtable) <= 8 // 8):
        raise ValueError('XP1 archive registration interface layout mismatch')

def install_xp1_archive_registration(host, core_base, teardown_receipt, *, project_root, emit=None):
    """Enable only descriptor+0 registration, forwarding ArchiveRegistry's bool."""
    source = verify_source(project_root)
    _check_host(host)
    if type(core_base) is not int or not 0 < core_base <= 18446744073709551615:
        raise ValueError('Invalid XP1 core module base')
    _check_teardown_receipt(teardown_receipt, host, core_base)
    access_state, access_receipt = _access_state(host)
    if access_receipt['getter_calls'] != 0 or access_receipt['remove_calls'] != 0:
        raise ValueError('XP1 registration must be installed before archive callbacks are used')
    before_host = tuple((int(value or 0) for value in host.vtable))
    before_descriptor = tuple((int(value or 0) for value in host.descriptor_vtable))
    old_register = before_descriptor[0]
    if not old_register:
        raise ValueError('XP1 Init-installed fatal registration callback is missing')
    retained = {int(C.cast(fn, C.c_void_p).value or 0) for fn in host.functions}
    prebound = (old_register, before_host[264 // 8], before_descriptor[1])
    if any((not pointer or pointer not in retained for pointer in prebound)):
        raise ValueError('XP1 pre-registration getter/remove/register callbacks are not all retained')
    state = {'installed': False, 'register_calls': 0, 'accepted_calls': 0, 'rejected_calls': 0, 'previous_register_pointer': old_register, 'getter_pointer': before_host[264 // 8], 'remove_pointer': before_descriptor[1], 'host_pointer': host.pointer, 'descriptor_pointer': C.addressof(host.descriptor_object), 'functions_start': len(host.functions), 'getter_calls_at_install': access_receipt['getter_calls'], 'remove_calls_at_install': access_receipt['remove_calls'], 'registration_supported': True, 'eligible_for_training': False}

    def register(this, descriptor):
        state['register_calls'] += 1
        result = host._archive_register(this, descriptor)
        if type(result) is not bool:
            raise TypeError('XP1 descriptor registration callback must return its native bool')
        if result:
            state['accepted_calls'] += 1
        else:
            state['rejected_calls'] += 1
        return result
    try:
        host._bind(host.descriptor_vtable, 0, C.c_bool, [C.c_void_p, C.c_void_p], register)
    except BaseException:
        host.descriptor_vtable[0] = old_register
        raise
    after_host = tuple((int(value or 0) for value in host.vtable))
    after_descriptor = tuple((int(value or 0) for value in host.descriptor_vtable))
    if after_host != before_host or len(after_descriptor) != len(before_descriptor) or any((after_descriptor[index] != before_descriptor[index] for index in range(len(before_descriptor)) if index != 0)) or (after_descriptor[0] == old_register) or (int(host.vtable[264 // 8] or 0) != state['getter_pointer']) or (int(host.descriptor_vtable[1] or 0) != state['remove_pointer']):
        host.descriptor_vtable[0] = old_register
        raise RuntimeError('XP1 archive registration changed an unapproved callback slot')
    state['installed'] = True
    state['register_pointer'] = after_descriptor[0]
    state['source'] = source
    host._xp1_archive_registration_binding = state
    receipt = archive_registration_receipt(host)
    if emit is not None:
        emit('xp1_archive_registration_installed', receipt=receipt)
    return receipt

def archive_registration_receipt(host) -> dict:
    """Return copied XP1 registration counters and current registry identities."""
    state = getattr(host, '_xp1_archive_registration_binding', None)
    if type(state) is not dict or state.get('installed') is not True:
        raise ValueError('XP1 archive registration adapter is not installed')
    from civ6_host.runtime.native.native_xp1_archive_access import xp1_archive_registry_receipt
    access = xp1_archive_registry_receipt(host)
    entries = getattr(getattr(host, 'archives', None), 'entries', None)
    if type(entries) is not dict:
        raise ValueError('XP1 archive registry state is unavailable')
    copied = [{'key': int(key), 'pointer': int(pointer)} for key, pointer in sorted(entries.items())]
    teardown = getattr(host, '_xp1_teardown_binding', {})
    expected_globals = {'0x9f2640': hex(host.pointer), '0x9f2648': hex(C.addressof(host.aux_object)), '0x9f2650': hex(C.addressof(host.logger_object))}
    retained = {int(C.cast(fn, C.c_void_p).value or 0) for fn in getattr(host, 'functions', [])}
    current_callbacks = (int(host.vtable[264 // 8] or 0), int(host.descriptor_vtable[0] or 0), int(host.descriptor_vtable[1] or 0))
    globals_match = type(teardown) is dict and teardown.get('host_globals_verified') == expected_globals
    pointers_match = globals_match and current_callbacks[0] == state['getter_pointer'] and (current_callbacks[1] == state['register_pointer']) and (current_callbacks[2] == state['remove_pointer']) and all((pointer and pointer in retained for pointer in current_callbacks)) and (host.pointer == state['host_pointer']) and (C.addressof(host.descriptor_object) == state['descriptor_pointer'])
    return {'schema': 'civ6rl.native_xp1_archive_registration_receipt.v1', 'installed': True, 'getter_calls': access['getter_calls'], 'remove_calls': access['remove_calls'], 'register_calls': int(state['register_calls']), 'accepted_calls': int(state['accepted_calls']), 'rejected_calls': int(state['rejected_calls']), 'registered_count': len(copied), 'entries': copied, 'callbacks_match_installation': bool(pointers_match), 'host_globals_match_teardown_receipt': bool(globals_match), 'registration_supported': True, 'eligible_for_training': False}
__all__ = ['verify_source', 'install_xp1_archive_registration', 'archive_registration_receipt']

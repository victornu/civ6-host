"""Bounded XP1-only context setter/Init/getter adapter.

This module does not call Prepare, GameInit, or NewGame. It binds a private
configuration DB and a private Gameplay DB through the already-proved context
host interface, then observes the exact initialized-state getter. It does not
certify either database as canonical or prove a playable game.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import os
import struct
from functools import lru_cache
from pathlib import Path
from typing import Callable
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
XP1_CONFIG_SHA256 = '95b68bf37549690e6771925cfa189da87e810c94a09c6508059fa3f6583f3faf'
XP1_CONFIG_BYTES = 765952
XP1_GAMEPLAY_SHA256 = '637f3f53b4d8609bc0325de5dac2008f80f7a7437d3ef4b6d26d31576563717e'
XP1_GAMEPLAY_BYTES = 6901760
SQLITE_HEADER = b'SQLite format 3\x00'
PROOF_PINS = {'context': ('evidence/native-expansion-context/6f808ce7420c461ee4e0b7cb1cab46d90c7df4b4c1120cf2958c3477f0773cc1.json', '6f808ce7420c461ee4e0b7cb1cab46d90c7df4b4c1120cf2958c3477f0773cc1'), 'constructors': ('evidence/native-expansion-context-constructors/127fdfff335b79415a665c57bb76e2f44a253d42aec27445f6d5fd970269591d.json', '127fdfff335b79415a665c57bb76e2f44a253d42aec27445f6d5fd970269591d'), 'init_boundary': ('evidence/native-expansion-init-boundary/fc1786d5b274a0e184e2314cbe0b30da8076a6b784f5a09a423496885f2937f6.json', 'fc1786d5b274a0e184e2314cbe0b30da8076a6b784f5a09a423496885f2937f6'), 'host_callbacks': ('evidence/native-expansion-host-callbacks/7a538a9bebc950bfce185d0e858753df837b0099b8a755922763766da7032ca5.json', '7a538a9bebc950bfce185d0e858753df837b0099b8a755922763766da7032ca5'), 'gameplay_path': ('work/native-xp1-context-init802/xp1-gameplay-path799.json', 'cae910a58a785a4901ca956f2d9d6ecbba1dc7db588b6de997ad72402d53684f'), 'config_candidate': ('work/native-expansion-configuration-diagnostic/run-after275b/xp1_explicit/native-db-backup-aifvllac/provenance.json', '8de3131bfbb27fe753f0a420bc2138b5e5674aec977c364eb083558ad7b3587e'), 'gameplay_candidate': ('evidence/native-xp1-candidate801.json', '29c4737fda3b462abbae629c2d8c956f1dbfa29f5873fa680dbf479b4c11b117'), 'host_declarations': ('work/native-xp1-host-declarations809/declarations809.json', 'fd69cb8856b24eddf64d8657f54fdc635cb1f8e04b2e1111116cf267e825384d'), 'logger_slot28_811': ('evidence/native-xp1-logger811/analysis811.json', '3cbe257ae60500b114911462f33547488882d69fad5b2c922baad117c3eb902a'), 'phase28_logger_origin': ('evidence/phase28-logger-origin.json', '2f9b0075dceee65745afaa0ebfca6405d352a3a85e7586459234e49c9f301f57'), 'phase29_logger_enabled': ('evidence/phase29-logger-enabled.json', 'a6ac6b834ca99bcc17f686eb5d4d82ac251547488617ec09928d969a0511a0b7')}
SOURCE_PINS = {'civ6rl/native_core_context_profiles.py': '8f5aed71ecf614d6fa25d52b94b7fec4a0bb4bcec190f8f144b04c4cf541d676', 'civ6rl/native_host.py': 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6', 'civ6rl/native_setup.py': '5fb54924ceba00572003e395b6b49013847e41cf4ecc9f0c1c3f3dd5bad88432'}
XP1_SLOTS = {40: 4969520, 56: 4969632, 96: 4973952}
XP1_HOST_GLOBALS = (10430016, 10430024, 10430032)
XP1_HOST_VTABLE_ALLOWLIST = {0, 8, 16, 24, 152, 312, 320}
XP1_AUX_VTABLE_ALLOWLIST = set()
XP1_LOGGER_VTABLE_ALLOWLIST = {40, 64}
XP1_EVENT_DECLARATIONS = ((3241152231, 4032072631, 1), (2785224901, 4032072631, 1), (3795521837, 4032072631, 1), (3305989846, 4032072631, 1), (3918721997, 4032072631, 1), (1854549907, 4032072631, 1), (490036867, 594779970, 1), (675466772, 594779970, 1), (1294624025, 594779970, 1), (830651534, 594779970, 1), (272736031, 594779970, 1), (1372081338, 594779970, 1), (2582142662, 594779970, 1), (1099678774, 594779970, 1), (3270739392, 594779970, 1), (4148886649, 4081310810, 1))

class XP1ContextInitError(RuntimeError):
    """A diagnostic Init failure carrying the last observed state."""

    def __init__(self, receipt: dict, message: str):
        super().__init__(message)
        self.receipt = receipt

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def _load_json_pinned(root: Path, relative: str, expected_sha: str) -> dict:
    path = root / relative
    if _sha256_file(path) != expected_sha:
        raise ValueError(f'Pinned XP1 context proof changed: {relative}')
    value = json.loads(_resolve_resource_path(path).read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError(f'Pinned proof is not an object: {relative}')
    return value

def verify_source(project_root: str | os.PathLike[str]) -> dict:
    """Verify the XP1 profile, context ABI, +0x138 path, and candidate pins."""
    root = _resolve_resource_path(_resolve_resource_path(Path(project_root))).resolve()
    source_hashes = {}
    for relative, expected in SOURCE_PINS.items():
        actual = _sha256_file(root / relative)
        if actual != expected:
            raise ValueError(f'XP1 Init source module changed: {relative}')
        source_hashes[relative] = actual
    evidence = {name: _load_json_pinned(root, path, digest) for name, (path, digest) in PROOF_PINS.items()}
    context = evidence['context']
    constructors = evidence['constructors']
    boundary = evidence['init_boundary']
    if context.get('images', {}).get('xp1', {}).get('sha256') != XP1_CORE_SHA256:
        raise ValueError('Lifecycle proof does not pin the XP1 GameCore image')
    chain = constructors.get('ruleset_constructor_chains', {}).get('xp1', {})
    if chain.get('context_vtable', {}).get('capture', {}).get('size') != 64:
        raise ValueError('XP1 constructor does not contain the expected context vtable prefix')
    if chain.get('context_vtable', {}).get('slot_0x38_target_rva') != '0x4bd4a0':
        raise ValueError('XP1 initialized-state getter slot changed')
    xp1 = boundary.get('rulesets', {}).get('xp1', {})
    init = xp1.get('methods', {}).get('init', {})
    if xp1.get('gamecore_sha256') != XP1_CORE_SHA256 or init.get('context_slot') != '0x28' or init.get('target_rva') != '0x4bd430' or (init.get('inner_target_rva') != '0x3ccf0'):
        raise ValueError('XP1 Init dispatch evidence changed')
    call = [row for row in init.get('inner_calls_and_jumps', []) if row.get('va') == '0x18003cda0']
    if len(call) != 1 or call[0].get('instruction') != 'call qword ptr [rax + 0x138]':
        raise ValueError('XP1 Init no longer calls the +0x138 host path callback')
    logger_proof = evidence['logger_slot28_811']
    phase28 = evidence['phase28_logger_origin']
    phase29 = evidence['phase29_logger_enabled']
    callsite = logger_proof.get('xp1_call_path', {}).get('callsite', {})
    helper = logger_proof.get('xp1_call_path', {}).get('log_enable_callee_body', {})
    helper_rows = {row.get('rva'): row for row in helper.get('instructions', [])}
    setter = logger_proof.get('xp1_call_path', {}).get('logger_pointer_origin', {})
    setter_body = setter.get('set_host_body', {})
    setter_rows = {row.get('rva'): row for row in setter_body.get('instructions', [])}
    if logger_proof.get('schema') != 'civ6rl.native_xp1_logger_slot28_analysis811.v1' or logger_proof.get('source_images', {}).get('xp1_gamecore', {}).get('sha256') != XP1_CORE_SHA256 or helper.get('start_rva') != '0x500cb0' or (helper.get('length') != 114) or (helper.get('sha256') != 'be057dae4fbd027f0e8f9b461757a74251aba787042913d77292ee872a94af5b') or (helper_rows.get('0x500cf7', {}).get('bytes') != 'ff5040') or (helper_rows.get('0x500d08', {}).get('bytes') != 'ff5028') or (callsite.get('registers') != {'RCX': 'logger object pointer', 'EDX': '0x0d1c6135 channel id', 'R8B': '1'}) or (callsite.get('rva') != '0x500d08') or (callsite.get('bytes') != 'ff5028') or (setter.get('xp1_logger_global_va') != '0x1809f2650') or (setter_rows.get('0x3c054', {}).get('text') != 'call qword ptr [rax + 0x18]') or (setter_rows.get('0x3c05f', {}).get('rip_targets') != ['0x1809f2650']) or (logger_proof.get('runtime_failure_evidence', {}).get('outcome', '').find('did not claim XP1 initialization success') < 0):
        raise ValueError('XP1 logger +0x28 callsite/ownership proof changed')
    if phase28.get('artifact', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or phase28.get('logger_methods', {}).get('slot_0x28_enable') != '0x14015b700' or phase28.get('complete_function_disassembly', {}).get('channel_enable_slot_28', {}).get('complete') is not True or ('existing channel' not in phase28.get('channel_contract', {}).get('slot_0x28_enable', '')) or (phase29.get('exe', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63') or (next((row.get('target') for row in phase29.get('exe', {}).get('logger_vtable', {}).get('entries', []) if row.get('slot') == '0x28'), None) != '0x14015b700'):
        raise ValueError('Pinned EXE logger +0x28 implementation proof changed')
    set_host = xp1.get('methods', {}).get('set_host', {})
    setter_tails = [row for row in set_host.get('out_of_line_tail_jumps', []) if row.get('target_rva') == '0x3bff0']
    if set_host.get('context_slot') != '0x60' or set_host.get('target_rva') != '0x4be580' or len(setter_tails) != 1 or (setter_tails[0].get('body', {}).get('fragments', [{}])[0].get('sha256') != '05718dd84ed98f1422d61a72f7115fadcd0e24e3e58a48480e4fd28ffe559a41'):
        raise ValueError('XP1 host setter/null-global lifecycle proof changed')
    path_proof = evidence['gameplay_path']
    if path_proof.get('schema') != 'civ6rl.native_xp1_gameplay_path_slot.static.v1' or path_proof.get('image', {}).get('sha256') != XP1_CORE_SHA256 or path_proof.get('consumer', {}).get('rva') != '0x3cda0' or (path_proof.get('consumer', {}).get('label_ascii') != 'Gameplay') or (path_proof.get('consumer', {}).get('label_bytes') != '47616d65706c617900') or (path_proof.get('consumer', {}).get('result_stored_at_inner_offset') != '0x58'):
        raise ValueError('XP1 +0x138 Gameplay path witness changed')
    host = evidence['host_callbacks']
    if host.get('schema') != 'civ6rl.native_expansion_host_callbacks.static.v1':
        raise ValueError('XP1 host callback proof schema changed')
    host_impl = host.get('host_implementation', {}).get('source_contract', {})
    xp1_callbacks = host.get('rulesets', {}).get('xp1', {})
    if host_impl.get('logger_object', '').find('logger_vtable slot 0x40') < 0 or host_impl.get('configuration_path', '').find('slot 0x140') < 0 or xp1_callbacks.get('logger_register', {}).get('call_rva') != '0x3cd33' or (xp1_callbacks.get('configuration_path', {}).get('call_rva') != '0x3cd47'):
        raise ValueError('XP1 Init callback allowlist evidence changed')
    declarations = evidence['host_declarations']
    normalized = tuple(((int(row['event'], 16), int(row['filter_id'], 16), row['value']) for row in declarations.get('ordered_declarations', [])))
    if declarations.get('schema') != 'civ6rl.native_xp1_host_declarations809.static.v1' or declarations.get('core_sha256') != XP1_CORE_SHA256 or declarations.get('native_execution') is not False or (declarations.get('parent_proof_sha256') != PROOF_PINS['init_boundary'][1]) or (normalized != XP1_EVENT_DECLARATIONS):
        raise ValueError('XP1 host +0x98 ordered declaration evidence changed')
    config = evidence['config_candidate']
    config_artifact = config.get('database_artifact', {})
    if config.get('profile') != 'xp1_explicit' or config_artifact.get('sha256') != XP1_CONFIG_SHA256 or config_artifact.get('byte_count') != XP1_CONFIG_BYTES or (config_artifact.get('native_backup_returned_true') is not True) or (config_artifact.get('logical_table_equality_verified') is not False) or (config.get('native_selection_observed') is not False) or (config.get('xp_gameplay_certified') is not False) or (config.get('eligible_for_training') is not False):
        raise ValueError('XP1 configuration candidate provenance changed')
    gameplay = evidence['gameplay_candidate']
    backup = gameplay.get('diagnostic_backup', {}).get('file', {})
    if backup.get('sha256') != XP1_GAMEPLAY_SHA256 or backup.get('bytes') != XP1_GAMEPLAY_BYTES or gameplay.get('candidate_persisted') is not True or (gameplay.get('native_game_initialized') is not False) or (gameplay.get('newgame_called') is not False) or (gameplay.get('complete_game_demonstrated') is not False) or (gameplay.get('canonical_database_certified') is not False) or (gameplay.get('eligible_for_training') is not False):
        raise ValueError('XP1 Gameplay candidate provenance changed')
    return {'schema': 'civ6rl.native_xp1_context_init_source.v1', 'core_sha256': XP1_CORE_SHA256, 'source_sha256': source_hashes, 'proof_sha256': {name: digest for name, (_, digest) in PROOF_PINS.items()}, 'xp1_slots': {hex(slot): hex(rva) for slot, rva in XP1_SLOTS.items()}, 'gameplay_callback': {'slot': '0x138', 'label': 'Gameplay', 'inner_connection_offset': '0x58'}, 'logger_enable': {'slot': '0x28', 'channel': '0x0d1c6135', 'enabled_byte': 1}, 'event_filter_declarations': len(XP1_EVENT_DECLARATIONS), 'configuration_candidate_sha256': XP1_CONFIG_SHA256, 'gameplay_candidate_sha256': XP1_GAMEPLAY_SHA256, 'canonical_database_certified': False, 'eligible_for_training': False}

def _path_text(host, offset: int, reader: Callable[[int], bytes] | None) -> str:
    paths = getattr(host, 'paths', None)
    if type(paths) is not dict or set(paths) != {312, 320}:
        raise ValueError('XP1 host must expose only the pinned Gameplay/Configuration path callbacks')
    buffer = paths[offset]
    if reader is not None:
        address = C.addressof(buffer) if not type(buffer) is int else buffer
        raw = reader(address)
    elif type(buffer) is bytes:
        raw = buffer
    elif isinstance(buffer, C.Array):
        raw = bytes(buffer.value)
    else:
        raise ValueError('XP1 host path callback storage has an unsupported representation')
    if type(raw) is not bytes or not raw or b'\x00' in raw:
        raise ValueError('XP1 host path callback returned malformed bytes')
    return os.fsdecode(raw)

def validate_private_inputs(host, configuration_path, gameplay_path, private_root, *, path_reader=None, file_hash=_sha256_file, candidate_bundle=None, candidate_family='xp1-lan') -> dict:
    """Require the two pinned, distinct DB copies to be private to one run."""
    if candidate_family not in ('xp1-lan', 'xp2-lan') or (candidate_family == 'xp2-lan' and candidate_bundle is None):
        raise ValueError('Captured Init requires an exact expansion input family and owner')
    root = _resolve_resource_path(_resolve_resource_path(Path(private_root))).resolve()
    config = _resolve_resource_path(_resolve_resource_path(Path(configuration_path))).resolve()
    gameplay = _resolve_resource_path(_resolve_resource_path(Path(gameplay_path))).resolve()
    configuration_sha, configuration_bytes = (XP1_CONFIG_SHA256, XP1_CONFIG_BYTES)
    gameplay_sha, gameplay_bytes = (XP1_GAMEPLAY_SHA256, XP1_GAMEPLAY_BYTES)
    captured_binding = None
    if candidate_bundle is not None:
        from civ6_host.runtime.captured_init_inputs import selected_database_input_binding as database_input_binding
        captured_binding = database_input_binding(candidate_bundle, host, configuration_path, gameplay_path, private_root, family=candidate_family)
        configuration_pin = captured_binding['databases']['configuration']
        gameplay_pin = captured_binding['databases']['gameplay']
        configuration_sha, configuration_bytes = (configuration_pin['sha256'], configuration_pin['size_bytes'])
        gameplay_sha, gameplay_bytes = (gameplay_pin['sha256'], gameplay_pin['size_bytes'])
    if config == gameplay:
        raise ValueError('XP1 Configuration and Gameplay candidates must be distinct files')
    for path in (config, gameplay):
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError('XP1 context inputs must be private copies under the run directory') from exc
        if not _resolve_resource_path(path).is_file():
            raise ValueError('XP1 context input is missing')
    if _resolve_resource_path(config).stat().st_size != configuration_bytes or file_hash(config) != configuration_sha:
        raise ValueError('XP1 Configuration candidate differs from its pinned private diagnostic input')
    if _resolve_resource_path(gameplay).stat().st_size != gameplay_bytes or file_hash(gameplay) != gameplay_sha:
        raise ValueError('XP1 Gameplay candidate differs from its pinned private diagnostic input')
    for label, path in (('Configuration', config), ('Gameplay', gameplay)):
        with _resolve_resource_path(path).open('rb') as stream:
            if stream.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                raise ValueError(f'XP1 {label} candidate is not a SQLite database')
    host_pointer = getattr(host, 'pointer', None)
    if type(host_pointer) is not int or host_pointer <= 0:
        raise ValueError('XP1 context requires a live, retained host interface')
    aligned_free = getattr(host, 'native_aligned_free', None)
    if aligned_free is not None:
        raise ValueError('XP1 Init has no proven native aligned-free callback; keep it unbound')
    recorder = getattr(host, 'event_recorder', None)
    if recorder is not None and getattr(recorder, 'installed', False) is True:
        raise ValueError('Base-oriented NativeEventRecorder installation is outside this XP1 Init adapter')
    callback_slots = getattr(host, 'vtable', None)
    if callback_slots is None:
        raise ValueError('XP1 host does not expose its callback vtable')
    for offset in (312, 320):
        try:
            callback = callback_slots[offset // 8]
        except (IndexError, TypeError) as exc:
            raise ValueError('XP1 path callback slot is unavailable') from exc
        if not callback:
            raise ValueError('XP1 path callback slot is unbound')
    logger_vtable = getattr(host, 'logger_vtable', None)
    logger_object = getattr(host, 'logger_object', None)
    try:
        logger_register = logger_vtable[64 // 8]
        logger_vtable_pointer = logger_object[0]
    except (IndexError, TypeError) as exc:
        raise ValueError('XP1 logger registration interface is unavailable') from exc
    try:
        logger_enable = logger_vtable[40 // 8]
    except (IndexError, TypeError) as exc:
        raise ValueError('XP1 logger enable interface is unavailable') from exc
    if not logger_register or not logger_enable or (not logger_vtable_pointer):
        raise ValueError('XP1 logger registration/enable callback is unbound')
    if isinstance(logger_vtable, C.Array) and logger_vtable_pointer != C.addressof(logger_vtable):
        raise ValueError('XP1 logger object does not reference its retained vtable')
    filters = getattr(host, 'filters', None)
    if filters is None or getattr(filters, 'entries', None) != {}:
        raise ValueError('XP1 host event filter registry must be empty before Init')
    gameplay_callback = _resolve_resource_path(_resolve_resource_path(Path(_path_text(host, 312, path_reader)))).resolve()
    configuration_callback = _resolve_resource_path(_resolve_resource_path(Path(_path_text(host, 320, path_reader)))).resolve()
    if gameplay_callback != gameplay or configuration_callback != config:
        raise ValueError('XP1 host path callbacks do not match the two pinned private candidates')
    return {**({'captured_input_binding': captured_binding} if captured_binding is not None else {}), 'configuration_path': str(config), 'configuration_sha256': configuration_sha, 'gameplay_path': str(gameplay), 'gameplay_sha256': gameplay_sha, 'gameplay_path_callback': '0x138', 'configuration_path_callback': '0x140', 'host_callbacks_allowlist': ['host+0x00', 'host+0x08', 'host+0x10', 'host+0x18', 'host+0x98', 'logger+0x28', 'logger+0x40', 'host+0x138', 'host+0x140'], 'private_root': str(root)}

@lru_cache(maxsize=1)
def _checked_local_reader():
    from civ6_host.runtime.native.native_setup import local_reader
    return local_reader()

def _native_reader(address: int, size: int) -> bytes:
    return _checked_local_reader()(address, size)

def _rebind_unapproved_host_callbacks(host):
    from civ6_host.runtime.context_initialization import restrict_callbacks
    return restrict_callbacks(host, host_slots=XP1_HOST_VTABLE_ALLOWLIST, auxiliary_slots=XP1_AUX_VTABLE_ALLOWLIST, logger_slots=XP1_LOGGER_VTABLE_ALLOWLIST)

def _require_empty_xp1_host_globals(core, read):
    from civ6_host.runtime.context_initialization import require_empty_globals
    return require_empty_globals(core, read, XP1_HOST_GLOBALS)

def _require_installed_xp1_host_globals(core, host, read):
    from civ6_host.runtime.context_initialization import require_installed_globals
    return require_installed_globals(core, host, read, XP1_HOST_GLOBALS)

def _require_exact_xp1_declarations(host):
    from civ6_host.runtime.context_initialization import require_declarations
    return require_declarations(host, XP1_EVENT_DECLARATIONS)

def _native_virtual(core, object_pointer, slot, expected_rva, result, *arguments):
    vtable = C.c_void_p.from_address(object_pointer).value
    address = C.c_void_p.from_address(vtable + slot).value
    if address != core._handle + expected_rva:
        raise ValueError(f'Unverified XP1 context method at slot {hex(slot)}')
    return C.WINFUNCTYPE(result, C.c_void_p, *arguments)(address)

def initialize_xp1_context(core, context, host, *, configuration_path, gameplay_path, private_root, module_paths, emit=None, read=_native_reader, profile_loader=None, modules_validator=None, context_validator=None, virtual_factory=None, path_reader=None, source_check=None, input_validator=validate_private_inputs, candidate_bundle=None) -> dict:
    """Install the host, call XP1 Init once, and read its official state getter.

    Dependencies are injectable only to make bounded pure tests possible. The
    production defaults use the existing hash-pinned XP1 profile and ABI.
    """
    from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_context
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_modules
    from civ6_host.runtime.native.native_host import virtual as host_virtual
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_xp1_context_init.py')))).resolve().parents[1]
    source = source_check(root) if source_check is not None else verify_source(root)
    profile_loader = profile_loader or profile_for_core
    modules_validator = modules_validator or validate_loaded_modules
    context_validator = context_validator or validate_loaded_context
    virtual_factory = virtual_factory or host_virtual
    from civ6_host.runtime.xp1_saved_load import select_context
    profile = select_context(core, candidate_bundle, profile_loader)
    modules_validator(profile, module_paths)
    callback_receipt = _rebind_unapproved_host_callbacks(host)
    if candidate_bundle is None:
        input_receipt = input_validator(host, configuration_path, gameplay_path, private_root, path_reader=path_reader)
    else:
        if input_validator is not validate_private_inputs:
            raise ValueError('Captured XP1 Init requires the existing private input validator')
        input_receipt = validate_private_inputs(host, configuration_path, gameplay_path, private_root, path_reader=path_reader, candidate_bundle=candidate_bundle)
    from civ6_host.runtime.context_initialization import initialize
    boundary = _load_json_pinned(root, *PROOF_PINS['init_boundary'])
    receipt = initialize(core, context, host, profile=profile, source=source, input_receipt=input_receipt, callback_receipt=callback_receipt, slots=XP1_SLOTS, globals_rvas=XP1_HOST_GLOBALS, declarations=XP1_EVENT_DECLARATIONS, vtable_bytes=bytes.fromhex(boundary['rulesets']['xp1']['context_vtable_capture']['raw_hex']), context_validator=context_validator, virtual_factory=virtual_factory, read=read, emit=emit, error_type=XP1ContextInitError)
    if getattr(profile, 'execution_image', None) is not None:
        host._xp1_saved_load_bundle = candidate_bundle
    return receipt

__all__ = ['XP1ContextInitError', 'verify_source', 'validate_private_inputs', 'initialize_xp1_context', 'PROOF_PINS', 'SOURCE_PINS', 'XP1_HOST_VTABLE_ALLOWLIST', 'XP1_LOGGER_VTABLE_ALLOWLIST', 'XP1_EVENT_DECLARATIONS']

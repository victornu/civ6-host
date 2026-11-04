"""XP1 native Lua API registration, independent of the Base-only binder.

This is not the auxiliary Tuner factory and does not claim Prepare/gameplay
readiness. Only call in an isolated, resource-limited native host process.
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
PROOF = 'work/native-xp1-script854/capture854.json'
PROOF_SHA256 = 'f95eeca73153fab0d28b220583a0fab2cdebfdbb03306133f7f3b3f00fed1d5f'
PREREQUISITE_PROOF = 'work/native-xp1-script856/capture856.json'
PREREQUISITE_SHA256 = 'bc1c4839f6ca52995a4b5e6da3dd2d836ab92a893dbcc9069a0512dd71c8c1aa'

def source_profile(project_root):
    raw = _resolve_resource_path(_resolve_resource_path(Path(project_root)) / PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise ValueError('XP1 script interface source proof changed')
    proof = json.loads(raw)
    if proof['schema'] != 'civ6rl.native_xp1_script_interface854.static.v1' or proof['binary']['sha256'] != CORE_SHA256 or proof['singleton']['computed_vtable_rva'] != '0x8aaf10' or (proof['game_api']['thunk']['rva'] != '0x4cbe40'):
        raise ValueError('XP1 script interface profile mismatch')
    prerequisite_raw = _resolve_resource_path(_resolve_resource_path(Path(project_root)) / PREREQUISITE_PROOF).read_bytes()
    if hashlib.sha256(prerequisite_raw).hexdigest() != PREREQUISITE_SHA256:
        raise ValueError('XP1 script prerequisite source changed')
    prerequisite = json.loads(prerequisite_raw)
    if prerequisite['core_sha256'] != CORE_SHA256 or prerequisite['computed_global_rva'] != '0x9f5948':
        raise ValueError('XP1 script prerequisite profile mismatch')
    proof['prerequisite'] = prerequisite
    return proof

def _read(read, address, size):
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete native script-interface read')
    return raw

def _pointer(read, address):
    return struct.unpack('<Q', _read(read, address, 8))[0]

def verify_getter(read, base, context, proof):
    if type(base) is not int or not 0 < base <= 18446744073709551615 - 10551296 or type(context) is not int or (not 0 < context <= 18446744073709551615 - 16):
        raise ValueError('Invalid native script-interface owner')
    if _pointer(read, context) != base + 9080304:
        raise ValueError('XP1 outer-context identity mismatch')
    if _pointer(read, base + 9080304 + 104) != base + 4969088:
        raise ValueError('XP1 script getter target mismatch')
    bodies = [proof['outer_getter']['body'], proof['singleton']['constructor'], proof['game_api']['thunk'], proof['game_api']['registration']]
    for body in bodies:
        raw = bytes.fromhex(body['hex'])
        if len(raw) != body['bytes'] or hashlib.sha256(raw).hexdigest() != body['sha256'] or _read(read, base + int(body['rva'], 16), len(raw)) != raw:
            raise ValueError('XP1 script executable bytes differ from source proof')
    return base + 4969088

def verify_interface(read, base, interface):
    if type(interface) is not int or interface != base + 10446480:
        raise ValueError('XP1 script getter returned a foreign pointer')
    if _pointer(read, interface) != base + 9088784 or _pointer(read, base + 9088784 + 16) != base + 5029440:
        raise ValueError('XP1 script-interface vtable mismatch')

def verify_registration_owner(read, base, proof):
    """Refuse the uninitialized owner before any native binder mutation.

    Passing this check does not establish that all registration prerequisites
    are ready. The isolated native probe remains mandatory.
    """
    if type(base) is not int or not 0 < base <= 18446744073709551615 - 10551296:
        raise ValueError('Invalid XP1 module base')
    getter = proof['prerequisite']['captures'][0]
    raw = bytes.fromhex(getter['hex'])
    if _read(read, base + 2663504, len(raw)) != raw or hashlib.sha256(raw).hexdigest() != getter['sha256']:
        raise ValueError('XP1 registration prerequisite getter changed')
    owner = _pointer(read, base + 10443080)
    if not owner:
        raise ValueError('XP1 registration prerequisite global9f5948 is null; binder refused')
    return owner

def bind_xp1_game_api(runtime, child, core_context, core, *, project_root, module_paths):
    from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
    from civ6_host.runtime.native.native_core_context_profiles import validate_loaded_modules
    from civ6_host.runtime.native.native_setup import local_reader
    proof = source_profile(project_root)
    profile = profile_for_core(core._name, mode='context')
    if profile.ruleset != 'xp1' or profile.core_sha256 != CORE_SHA256:
        raise ValueError('XP1 script API refuses other rulesets')
    validate_loaded_modules(profile, module_paths)
    pointer = runtime.registry.validate(child)
    if getattr(runtime, '_xp1_script_bind_entered', False) or not runtime.database_bound or (not runtime.configuration_bound) or (not runtime.locale_bound):
        raise ValueError('XP1 script registration requires fresh, bound native services')
    read = local_reader()
    getter = verify_getter(read, core._handle, core_context, proof)
    verify_registration_owner(read, core._handle, proof)
    interface = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(getter)(core_context)
    verify_interface(read, core._handle, interface)
    install = runtime.host.LAB_XP1ScriptCoreBindingsInstall
    install.argtypes, install.restype = ([C.c_void_p] * 4, C.c_int)
    runtime.emit('before_xp1_script_api_bind', getter_rva='0x4bd280', vtable_rva='0x8aaf10', method_rva='0x4cbe40')
    runtime._xp1_script_bind_entered = True
    status = install(runtime.root, pointer, interface, core._handle)
    runtime._status(runtime.root if runtime.lua['gettop'](runtime.root) else pointer, status, 'XP1 native GameCore API registration')
    if runtime.lua['gettop'](runtime.root) or runtime.lua['gettop'](pointer):
        raise RuntimeError('XP1 API registration left a nonempty Lua stack')
    receipt = {'schema': 'civ6rl.native_xp1_script_binding854.v1', 'returned': True, 'getter_rva': '0x4bd280', 'vtable_rva': '0x8aaf10', 'method_rva': '0x4cbe40', 'official_core_callbacks': True, 'complete_api_verified': False, 'auxiliary_factory_installed': False, 'prepare_called': False, 'game_created': False, 'eligible_for_training': False}
    runtime.emit('xp1_script_api_bind_returned', receipt=receipt)
    return receipt

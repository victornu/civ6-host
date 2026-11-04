"""Protected official Core registration selected by a source-qualified profile.

This binds the installed engine's own Lua API; it does not implement its rules.
The caller must own an isolated, bounded native process. A returned outer frame
does not establish that every nested registration or gameplay API succeeded.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path

from . import script_binding_profiles as profiles
from .source_build_identity import verify_source_build

# Authored protected-frame implementation and its unchanged shared environment.
PROFILE_COMPONENT_SHA = '433439165e1376da8d087a55ac23cf0fb043859d9a2c735d3d5f7f8dee4b1d35'
SHARED_COMPONENT_SHA = '77a750aa17b5c78f5d1e4813007637374259b5b46492c8fbccc0e3b090b113a5'


def _current_executable():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    function = kernel.GetModuleFileNameW
    function.argtypes, function.restype = [C.c_void_p, C.c_wchar_p, C.c_uint32], C.c_uint32
    buffer = C.create_unicode_buffer(32768)
    count = function(None, buffer, len(buffer))
    if not 0 < count < len(buffer):
        raise RuntimeError('Current native host executable path is unavailable')
    return Path(buffer.value).resolve(strict=True)


def bind_game_api(runtime, child, core_context, core, *, core_sha256):
    """Use the same managed root/child and protected Core registration path."""
    from .native.native_core_context_profiles import profile_for_core, validate_loaded_modules
    from .native.native_probe import Windows
    from .native.native_setup import local_reader

    if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
        raise ValueError('Native script registration requires Windows x64')
    abi = profiles.profile_for_sha(core_sha256)
    selected = profile_for_core(core._name, mode='context')
    if selected.core_sha256 != abi.core_sha256 or selected.ruleset != abi.ruleset:
        raise ValueError('Script binding profile differs from the actual Core')
    validate_loaded_modules(selected, Windows().modules())
    pointer = runtime.registry.validate(child)
    if (getattr(runtime, '_profile_script_bind_attempted', False)
            or runtime.database_bound is not True or runtime.configuration_bound is not True
            or runtime.locale_bound is not True or getattr(runtime, 'service_owner', None) is None
            or runtime.lua['gettop'](runtime.root) or runtime.lua['gettop'](pointer)):
        raise ValueError('Profile registration requires fresh bound services and empty owned stacks')
    for name in ('LAB_ProfileScriptCoreBindingsVersion', 'LAB_ProfileScriptCoreBindingsInstall'):
        if not hasattr(runtime.host, name):
            raise ValueError('Native host lacks its source-qualified profile registration export')
    native_build = verify_source_build(_current_executable(), required_components={
        'script_core_binding_profiles.inc': PROFILE_COMPONENT_SHA,
        'script_core_bindings.inc': SHARED_COMPONENT_SHA,
    })
    read = local_reader()
    getter = profiles.verify_live(abi, core._handle, core_context, read)
    version = runtime.host.LAB_ProfileScriptCoreBindingsVersion
    version.argtypes, version.restype = [], C.c_uint32
    if version() != 1:
        raise ValueError('Unsupported protected script profile ABI version')
    from .core_script_services import check_bound
    services = check_bound(runtime, core_context, core)
    runtime.emit('before_profile_script_api_bind', ruleset=abi.ruleset,
                 core_sha256=abi.core_sha256, source_sha256=profiles.SOURCE_SHA,
                 getter_rva=hex(abi.getter_rva), method_rva=hex(abi.method_rva),
                 native_host_sha256=native_build['host_sha256'])
    # The official getter can initialize its static interface. Consume this
    # attempt before crossing that boundary, including when later checks fail.
    runtime._profile_script_bind_attempted = True
    interface = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(getter)(core_context)
    profiles.verify_interface(abi, core._handle, interface, read)
    install = runtime.host.LAB_ProfileScriptCoreBindingsInstall
    install.argtypes, install.restype = [C.c_void_p] * 4 + [C.c_uint32], C.c_int
    status = install(runtime.root, pointer, interface, core._handle, abi.profile_id)
    error_state = runtime.root if runtime.lua['gettop'](runtime.root) else pointer
    runtime._status(error_state, status, 'profile-selected official GameCore API registration')
    if runtime.lua['gettop'](runtime.root) or runtime.lua['gettop'](pointer):
        raise RuntimeError('Profile registration left a nonempty Lua stack')
    receipt = dict(schema='civ6-host.script-api-binding-result.v1',
        ruleset=abi.ruleset, core_sha256=abi.core_sha256, profile_id=abi.profile_id,
        source_sha256=profiles.SOURCE_SHA, native_host_sha256=native_build['host_sha256'],
        service_init_source_sha256=services.init_source_sha256,
        service_type_source_sha256=services.type_source_sha256,
        outer_protected_status=status, registration_returned=True,
        complete_api_verified=False, game_created=False, saved_load_admitted=False)
    runtime.emit('profile_script_api_bind_returned', receipt=receipt)
    return receipt

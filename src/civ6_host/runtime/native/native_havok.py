"""Bounded diagnostics of the installed Havok Lua VM, not a Civ6 script host.

Only call this inside native_probe's isolated child. No GameCore services or
gameplay bindings are substituted by this module.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import time
HAVOK_SHA256 = '9fb4e34afa6666aafb519d6edb9c1e4e9add9cce2cecaa3b1e5bb8f08b168532'
EXPORTS = {'newstate': ('?luaL_newstate@@YAPEAUlua_State@@XZ', 247488, [], C.c_void_p), 'openlibs': ('?luaL_openlibs@@YAXPEAUlua_State@@@Z', 247696, [C.c_void_p], None), 'loadbuffer': ('?luaL_loadbuffer@@YAHPEAUlua_State@@PEBD_K1@Z', 209728, [C.c_void_p, C.c_char_p, C.c_size_t, C.c_char_p], C.c_int), 'pcall': ('?lua_pcall@@YAHPEAUlua_State@@HHH@Z', 251024, [C.c_void_p, C.c_int, C.c_int, C.c_int], C.c_int), 'gettop': ('?lua_gettop@@YAHPEAUlua_State@@@Z', 250496, [C.c_void_p], C.c_int), 'settop': ('?lua_settop@@YAXPEAUlua_State@@H@Z', 224416, [C.c_void_p, C.c_int], None), 'type': ('?lua_type@@YAHPEAUlua_State@@H@Z', 251440, [C.c_void_p, C.c_int], C.c_int), 'tonumber': ('?lua_tonumber@@YANPEAUlua_State@@H@Z', 251376, [C.c_void_p, C.c_int], C.c_double), 'tolstring': ('?lua_tolstring@@YAPEBDPEAUlua_State@@HPEA_K@Z', 251360, [C.c_void_p, C.c_int, C.POINTER(C.c_size_t)], C.c_void_p), 'close': ('?lua_close@@YAXPEAUlua_State@@@Z', 248400, [C.c_void_p], None)}
SCRIPT = b"\nlocal items = {9, 2, 5}\ntable.sort(items)\nlocal function make_adder(n) return function(x) return n+x end end\nassert(items[1] == 2 and items[3] == 9)\nassert(string.upper('civ') == 'CIV')\nlocal co = coroutine.create(function() coroutine.yield(7); return 8 end)\nlocal ok, first = coroutine.resume(co)\nassert(ok and first == 7)\nlocal ok2, second = coroutine.resume(co)\nassert(ok2 and second == 8 and coroutine.status(co) == 'dead')\nreturn make_adder(33)(items[3])\n"

def bind(library, *, shared_dependency_profile=None):
    selected_rvas = None
    if shared_dependency_profile is not None:
        from civ6_host.runtime.native.native_shared_dependency_profiles import NativeSharedDependencyProfile
        if type(shared_dependency_profile) is not NativeSharedDependencyProfile:
            raise ValueError('Expected the explicit XP2 shared dependency profile')
        shared_dependency_profile.verify_library_path('HavokScript_FinalRelease.dll', library._name)
        selected_rvas = shared_dependency_profile.havok_export_rvas
    functions = {}
    for key, (export, rva, args, result) in EXPORTS.items():
        function = getattr(library, export)
        expected_rva = rva if selected_rvas is None else selected_rvas.get(export)
        if type(expected_rva) is not int or C.cast(function, C.c_void_p).value != library._handle + expected_rva:
            raise RuntimeError(f'Unexpected Havok export address: {key}')
        function.argtypes, function.restype = (args, result)
        functions[key] = function
    return functions

def run_vm_diagnostic(library, emit, *, shared_dependency_profile=None):
    api = bind(library, shared_dependency_profile=shared_dependency_profile)
    emit('before_havok_vm_create', scope='Standalone VM; no Civ6 bindings')
    start = time.perf_counter()
    state = api['newstate']()
    if not state:
        raise RuntimeError('Native Havok Lua state is null')

    def error_text():
        length = C.c_size_t()
        pointer = api['tolstring'](state, -1, C.byref(length))
        return C.string_at(pointer, min(length.value, 4096)).decode('utf-8', 'replace') if pointer else 'non-string Lua error'
    try:
        emit('havok_vm_created', operation_seconds=time.perf_counter() - start)
        api['openlibs'](state)
        if api['gettop'](state) != 0:
            raise RuntimeError('Unexpected stack after opening native Lua libraries')
        emit('havok_vm_libraries_opened')
        start = time.perf_counter()
        status = api['loadbuffer'](state, SCRIPT, len(SCRIPT), b'@civ6rl_vm_diagnostic')
        if status:
            raise RuntimeError(f'Native Lua compile failed ({status}): {error_text()}')
        status = api['pcall'](state, 0, 1, 0)
        if status:
            raise RuntimeError(f'Native Lua execution failed ({status}): {error_text()}')
        if api['gettop'](state) != 1 or api['type'](state, -1) != 3:
            raise RuntimeError('Native Lua diagnostic did not return exactly one number')
        value = api['tonumber'](state, -1)
        if value != 42.0:
            raise RuntimeError(f'Unexpected native Lua result: {value!r}')
        emit('havok_vm_script_verified', operation_seconds=time.perf_counter() - start, result=value, script_sha256=hashlib.sha256(SCRIPT).hexdigest(), checks=['tables', 'sorting', 'closures', 'strings', 'coroutines'], game_created=False, native_turns_executed=0)
        api['settop'](state, 0)
        bad_script = b"error('civ6rl_expected_diagnostic_error')"
        if api['loadbuffer'](state, bad_script, len(bad_script), b'@civ6rl_vm_error'):
            raise RuntimeError('Could not compile expected-error diagnostic')
        status = api['pcall'](state, 0, 0, 0)
        message = error_text() if status else ''
        if not status or 'civ6rl_expected_diagnostic_error' not in message:
            raise RuntimeError('Native Lua protected call did not contain the expected error')
        api['settop'](state, 0)
        if api['gettop'](state) != 0:
            raise RuntimeError('Lua stack was not restored after protected error')
        emit('havok_vm_protected_error_verified', lua_status=status, error=message)
    finally:
        try:
            emit('before_havok_vm_close')
        finally:
            api['close'](state)
        emit('havok_vm_closed', native_turns_executed=0)

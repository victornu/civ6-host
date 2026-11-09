"""EXE-compatible root allocation and GC kernel; NOT a Map Script factory.

Only executed inside native_probe's bounded Windows child, with the compiled
host. The remaining root initialization callback, per-context creation and
Civ6 namespaces are deliberately not replaced by an empty Lua environment.
This kernel cannot be returned to GameCore as a configured script service.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from civ6_host.runtime.native.native_havok import bind
EXPORTS = {'newstate': ('?lua_newstate@@YAPEAUlua_State@@P6APEAXPEAX0_K1@Z0@Z', 250704, [C.c_void_p, C.c_void_p], C.c_void_p), 'gc': ('?lua_gc@@YAHPEAUlua_State@@HH@Z', 101712, [C.c_void_p, C.c_int, C.c_int], C.c_int)}
SCRIPT = b'local t={9,2,5}; local function add(x) return x+33 end; return add(t[1])'
ERROR_SCRIPT = b'local missing; return missing()'

def bind_kernel(library, *, shared_dependency_profile=None):
    api = bind(library, shared_dependency_profile=shared_dependency_profile)
    selected_rvas = None if shared_dependency_profile is None else shared_dependency_profile.havok_export_rvas
    for key, (name, rva, arguments, result) in EXPORTS.items():
        function = getattr(library, name)
        expected_rva = rva if selected_rvas is None else selected_rvas.get(name)
        if type(expected_rva) is not int or C.cast(function, C.c_void_p).value != library._handle + expected_rva:
            raise RuntimeError(f'Unexpected Havok kernel export: {key}')
        function.argtypes, function.restype = (arguments, result)
        api[key] = function
    return api

def bind_heap(host):
    api = {}
    for key, name, arguments, result in (('create', 'LAB_HavokHeapCreate', [], C.c_int), ('allocate', 'LAB_HavokAllocate', [C.c_void_p, C.c_void_p, C.c_size_t, C.c_size_t], C.c_void_p), ('counter', 'LAB_HavokHeapCounter', [C.c_uint], C.c_size_t), ('destroy', 'LAB_HavokHeapDestroy', [], C.c_int)):
        function = getattr(host, name)
        function.argtypes, function.restype = (arguments, result)
        api[key] = function
    return api

def check_heap_contract(heap):
    if heap['create']() != 0:
        raise RuntimeError('Overlapping heap ownership was accepted')
    pointer = heap['allocate'](None, None, 0, 32)
    if not pointer:
        raise RuntimeError('Diagnostic allocation failed')
    try:
        payload = bytes(range(32))
        C.memmove(pointer, payload, len(payload))
        if heap['destroy']() != 0:
            raise RuntimeError('Heap with live allocation was destroyed')
        resized = heap['allocate'](None, pointer, 32, 64)
        if not resized:
            raise RuntimeError('Diagnostic reallocation failed')
        pointer = resized
        if C.string_at(pointer, len(payload)) != payload:
            raise RuntimeError('Heap reallocation lost the original bytes')
    finally:
        heap['allocate'](None, pointer, 64, 0)
    if heap['counter'](0) != 0:
        raise RuntimeError('Diagnostic heap allocation remained live')

def run_kernel_diagnostic(library, emit, host=None):
    api = bind_kernel(library)
    if host is None:
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [C.c_wchar_p]
        kernel.GetModuleHandleW.restype = C.c_void_p
        module = kernel.GetModuleHandleW(None)
        if not module:
            raise C.WinError(C.get_last_error())
        host = C.WinDLL('', handle=module)
    heap = bind_heap(host)
    if heap['create']() != 1:
        raise RuntimeError('Could not create an exclusively owned Havok heap')
    state = None
    try:
        emit('script_kernel_heap_created', heap_initial_bytes=67108864, heap_maximum_bytes=0, heap_compatibility_mode=2, scope='Root allocation/GC kernel only; no Civ6 script bindings')
        check_heap_contract(heap)
        emit('script_kernel_heap_verified', checks=['exclusive_owner', 'grow_preserves_bytes', 'refuse_destroy_with_live_allocation', 'free_returns_live_count_to_zero'])
        state = api['newstate'](C.cast(heap['allocate'], C.c_void_p), None)
        if not state:
            raise RuntimeError('Native lua_newstate returned NULL')
        emit('script_kernel_state_created', userdata_null=True, factory_rva='0x3d350', live_blocks=heap['counter'](0))
        previous_pause = api['gc'](state, 6, 110)
        previous_step = api['gc'](state, 7, 5)
        if api['gc'](state, 6, 110) != 110 or api['gc'](state, 7, 5) != 5:
            raise RuntimeError('Native GC configuration did not retain EXE settings')
        emit('script_kernel_gc_configured', pause=110, step_multiplier=5, previous_pause=previous_pause, previous_step_multiplier=previous_step)
        if api['gettop'](state) != 0:
            raise RuntimeError('Unexpected root VM initial stack')
        status = api['loadbuffer'](state, SCRIPT, len(SCRIPT), b'@civ6rl_root_kernel')
        if status or api['pcall'](state, 0, 1, 0):
            raise RuntimeError('Root kernel script failed')
        if api['gettop'](state) != 1 or api['type'](state, -1) != 3 or api['tonumber'](state, -1) != 42.0:
            raise RuntimeError('Unexpected root kernel script result')
        api['settop'](state, 0)
        if api['loadbuffer'](state, ERROR_SCRIPT, len(ERROR_SCRIPT), b'@civ6rl_root_kernel_error'):
            raise RuntimeError('Expected-error script did not compile')
        status = api['pcall'](state, 0, 0, 0)
        if not status or api['gettop'](state) != 1 or api['type'](state, -1) != 4:
            raise RuntimeError('Native protected error was not retained on stack')
        api['settop'](state, 0)
        if api['gettop'](state) != 0:
            raise RuntimeError('Native stack not restored after error')
        emit('script_kernel_verified', result=42.0, protected_error_status=status, script_sha256=hashlib.sha256(SCRIPT).hexdigest(), game_created=False, native_turns_executed=0, map_script_factory_ready=False)
    finally:
        try:
            if state:
                api['close'](state)
        finally:
            counters = {name: heap['counter'](i) for i, name in enumerate(('live_blocks', 'allocation_calls', 'reallocation_calls', 'free_calls'))}
            if heap['destroy']() != 1:
                raise RuntimeError(f'Havok heap teardown refused: {counters}')
        emit('script_kernel_closed', **counters, map_script_factory_ready=False, native_turns_executed=0)

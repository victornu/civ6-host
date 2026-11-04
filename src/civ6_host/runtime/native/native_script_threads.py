"""Native thread-registry subset, not the complete Civ6 script environment.

Run only in native_probe's bounded child. Lua threads share a VM; these are
not independent games or operating-system threads. No child calls lua_close.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
import threading
from civ6_host.runtime.native.native_script_kernel import bind_kernel
from civ6_host.runtime.native.native_script_kernel import bind_heap

def bind_threads(host):
    api = {}
    for key, symbol, arguments, result in (('initialize', 'LAB_ThreadAPIInitialize', [C.c_void_p], C.c_int), ('install', 'LAB_ThreadRegistryInstall', [C.c_void_p], C.c_int), ('acquire', 'LAB_ThreadAcquire', [C.c_void_p, C.POINTER(C.c_void_p)], C.c_int), ('release', 'LAB_ThreadRelease', [C.c_void_p, C.c_void_p], C.c_int), ('forget', 'LAB_ThreadRegistryForget', [C.c_void_p], C.c_int)):
        function = getattr(host, symbol)
        function.argtypes, function.restype = (arguments, result)
        api[key] = function
    return api

@dataclass(eq=False)
class ScriptContext:
    pointer: int
    active: bool = True

class ThreadRegistry:

    def __init__(self, root, library, host, lua):
        if not root:
            raise ValueError('Null root VM')
        self.root, self.lua = (root, lua)
        self.owner = threading.get_ident()
        self.native = bind_threads(host)
        self.contexts = {}
        self._claims = {}
        self.closed = False
        if self.native['initialize'](library._handle) != 1:
            raise RuntimeError('Thread API exports did not match the pinned ABI')
        self._status(self.native['install'](root), 'registry installation')

    def _check(self):
        if self.closed or threading.get_ident() != self.owner:
            raise RuntimeError('Closed registry or cross-thread VM access')

    def _status(self, status, operation):
        if status:
            size = C.c_size_t()
            pointer = self.lua['tolstring'](self.root, -1, C.byref(size)) if self.lua['gettop'](self.root) and self.lua['type'](self.root, -1) == 4 else None
            message = C.string_at(pointer, min(size.value, 2048)).decode('utf-8', 'replace') if pointer else ''
            self.lua['settop'](self.root, 0)
            raise RuntimeError(f'{operation}: native status {status}: {message}')

    def acquire(self):
        self._check()
        pointer = C.c_void_p()
        self._status(self.native['acquire'](self.root, C.byref(pointer)), 'thread acquire')
        if not pointer.value or pointer.value in self.contexts:
            raise RuntimeError('Null or duplicate thread handle')
        context = ScriptContext(pointer.value)
        self.contexts[pointer.value] = context
        return context

    def validate(self, context):
        self._check()
        if not isinstance(context, ScriptContext) or not context.active or self.contexts.get(context.pointer) is not context:
            raise ValueError('Unknown, released or foreign script context')
        return context.pointer

    def claim(self, context, owner):
        pointer = self.validate(context)
        if owner is None or pointer in self._claims:
            raise RuntimeError('Script context already retained or missing owner')
        self._claims[pointer] = owner

    def release(self, context, *, owner=None):
        pointer = self.validate(context)
        if self._claims.get(pointer) is not owner:
            raise RuntimeError('Script context is retained by another owner')
        self._status(self.native['release'](self.root, pointer), 'thread release')
        self._claims.pop(pointer, None)
        del self.contexts[pointer]
        context.active = False

    def forget_after_root_close(self):
        self._check()
        if self._claims:
            raise RuntimeError('Retained script contexts must be released before root close')
        if self.native['forget'](self.root) != 1:
            raise RuntimeError('Root registry ownership mismatch')
        for context in self.contexts.values():
            context.active = False
        self.contexts.clear()
        self.closed = True

def run_thread_diagnostic(library, emit):
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
    host = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    lua, heap = (bind_kernel(library), bind_heap(host))
    if heap['create']() != 1:
        raise RuntimeError('Thread diagnostic could not own its heap')
    root = None
    registry = None

    def evaluate(state, source, expected_type=3):
        if lua['gettop'](state) != 0:
            raise RuntimeError('Unbalanced Lua stack before script')
        script = source.encode('utf-8')
        if lua['loadbuffer'](state, script, len(script), b'@civ6rl_thread_registry') or lua['pcall'](state, 0, 1, 0):
            length = C.c_size_t()
            pointer = lua['tolstring'](state, -1, C.byref(length))
            message = C.string_at(pointer, min(length.value, 2048)).decode('utf-8', 'replace') if pointer else ''
            raise RuntimeError(f'Thread script failed: {message}')
        if lua['gettop'](state) != 1 or lua['type'](state, -1) != expected_type:
            raise RuntimeError('Unexpected thread script result type or stack size')
        value = lua['tonumber'](state, -1) if expected_type == 3 else None
        lua['settop'](state, 0)
        return value

    def sizes():
        return evaluate(root, 'local n,w=0,0; for t,e in pairs(Threads) do assert(type(t)=="thread" and type(e)=="table"); n=n+1 end; for t,b in pairs(WeakThreads) do assert(type(t)=="thread" and b==true); w=w+1 end; assert(getmetatable(WeakThreads).__mode=="k"); return n*1000+w')
    try:
        root = lua['newstate'](C.cast(heap['allocate'], C.c_void_p), None)
        if not root:
            raise RuntimeError('Root creation failed')
        lua['gc'](root, 6, 110)
        lua['gc'](root, 7, 5)
        lua['openlibs'](root)
        registry = ThreadRegistry(root, library, host, lua)
        emit('script_threads_installed', full_root_initializer=False, map_script_factory_ready=False)
        contexts = [registry.acquire() for _ in range(3)]
        if len({c.pointer for c in contexts}) != 3 or sizes() != 3003:
            raise RuntimeError('Native registry did not retain three distinct contexts')
        for index, context in enumerate(contexts):
            pointer = registry.validate(context)
            evaluate(pointer, 'return marker', expected_type=0)
            evaluate(pointer, 'return pairs', expected_type=0)
            if evaluate(pointer, f'marker={index + 101}; return marker') != index + 101:
                raise RuntimeError('Per-context global assignment failed')
        for index, context in enumerate(contexts):
            if evaluate(registry.validate(context), 'return marker') != index + 101:
                raise RuntimeError('Globals leaked between thread environments')
        evaluate(root, 'return marker', expected_type=0)
        lua['gc'](root, 2, 0)
        if sizes() != 3003:
            raise RuntimeError('Strong registry lost a live thread during collection')
        emit('script_threads_isolation_verified', contexts=3, strong_references_survive_gc=True, separate_environments=True, native_turns_executed=0)
        if evaluate(root, 'saved={}; for t,e in pairs(Threads) do saved[#saved+1]=e; if e.marker==101 then held=t end end; return #saved') != 3:
            raise RuntimeError('Could not retain environment witnesses')
        for context in contexts:
            registry.release(context)
            try:
                registry.validate(context)
            except ValueError:
                pass
            else:
                raise RuntimeError('Released context still accepted')
        lua['gc'](root, 2, 0)
        if sizes() != 1:
            raise RuntimeError('Externally retained thread did not remain in weak registry')
        evaluate(root, 'for _,e in ipairs(saved) do assert(next(e)==nil) end; held=nil; saved=nil; return 1')
        lua['gc'](root, 2, 0)
        if sizes() != 0:
            raise RuntimeError('Weak registry kept released threads after collection')
        if registry.native['release'](root, contexts[0].pointer) != -1003:
            raise RuntimeError('Native duplicate-release guard failed')
        emit('script_threads_collection_verified', strong_entries=0, weak_entries=0, duplicate_release_rejected=True, environments_cleared_in_place=True, external_reference_retained_until_dropped=True)
        evaluate(root, '_SavedCreate=_CreateThread; _CreateThread=function() error("expected_create_error") end; return 1')
        try:
            registry.acquire()
        except RuntimeError as exc:
            if 'expected_create_error' not in str(exc):
                raise
        else:
            raise RuntimeError('Create failure was silently accepted')
        evaluate(root, '_CreateThread=_SavedCreate; _SavedCreate=nil; return 1')
        final = registry.acquire()
        if evaluate(registry.validate(final), 'return 7') != 7:
            raise RuntimeError('Registry could not recover after protected error')
        evaluate(root, '_SavedCreate=_CreateThread; _CreateThread=function() for t in pairs(Threads) do return t end end; return 1')
        try:
            registry.acquire()
        except RuntimeError as exc:
            if 'native status -1004' not in str(exc):
                raise
        else:
            raise RuntimeError('Duplicate native thread was accepted')
        evaluate(root, '_CreateThread=_SavedCreate; _SavedCreate=nil; return 1')
        if registry.validate(final) != final.pointer or sizes() != 1001:
            raise RuntimeError('Duplicate refusal damaged existing ownership')
        evaluate(root, '_SavedCreate=_CreateThread; _CreateThread=function() return coroutine.create(function() end) end; return 1')
        try:
            registry.acquire()
        except RuntimeError as exc:
            if 'absent from native registry' not in str(exc):
                raise
        else:
            raise RuntimeError('Unregistered coroutine was accepted')
        evaluate(root, '_CreateThread=_SavedCreate; _SavedCreate=nil; _SavedDestroy=_DestroyThread; _DestroyThread=function() end; return 1')
        try:
            registry.release(final)
        except RuntimeError as exc:
            if 'still registered after destroy' not in str(exc):
                raise
        else:
            raise RuntimeError('No-op destroy falsely released native ownership')
        if registry.validate(final) != final.pointer or sizes() != 1001:
            raise RuntimeError('Failed destroy lost the owned context')
        evaluate(root, '_DestroyThread=_SavedDestroy; _SavedDestroy=nil; return 1')
        registry.release(final)
        lua['gc'](root, 2, 0)
        if sizes() != 0:
            raise RuntimeError('Recovered context was retained')
        emit('script_threads_protected_error_verified', recovered=True, duplicate_acquire_rejected=True, unregistered_thread_rejected=True, false_release_rejected=True, map_script_factory_ready=False, game_created=False, native_turns_executed=0)
    finally:
        try:
            if root:
                lua['close'](root)
                if registry:
                    registry.forget_after_root_close()
        finally:
            counters = {name: heap['counter'](i) for i, name in enumerate(('live_blocks', 'allocation_calls', 'reallocation_calls', 'free_calls'))}
            if heap['destroy']() != 1:
                raise RuntimeError(f'Thread diagnostic heap teardown failed: {counters}')
        emit('script_threads_closed', **counters, map_script_factory_ready=False, native_turns_executed=0)

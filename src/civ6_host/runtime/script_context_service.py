"""Owned GameplayScripts callbacks, independent of NewGame diagnostics.

The caller supplies the resolved, versioned script selection and a bootstrap
function. This service does not pretend that a partial bootstrap is the entire
EXE script environment. File/execute errors are strict host refusals, unlike the
EXE's log-and-continue path. No path redirection or missing script is invented.
"""
from __future__ import annotations

import ctypes as C
import hashlib
from pathlib import Path, PureWindowsPath

from .native.native_context_lifetime import RetainedScriptContexts
from .native.native_context_notify import NativeContextNotification
from .native.native_include_registry import MAX_SOURCE_BYTES, MAX_TOTAL_BYTES
from .script_wire_paths import bind_wire_sources


def script_name(path):
    """Pinned loader derives the basename, removing its final extension."""
    output = bytearray()
    for char in PureWindowsPath(path).name.rsplit('.', 1)[0]:
        encoded = char.encode('utf-8')
        if len(output) + len(encoded) > 259:
            break
        output.extend(encoded)
    if not output or b'\0' in output:
        raise ValueError('Gameplay script name is empty or contains NUL')
    return bytes(output)


def snapshot_scripts(registry, expected_hashes):
    """One bounded immutable file snapshot; exact selection, no asset scanning."""
    paths = tuple(registry.paths)
    if set(paths) != set(expected_hashes):
        raise ValueError('Script hashes must cover exactly the resolved selection')
    result = {}; total = 0
    for path in paths:
        script_name(path)
        if path in result:
            continue  # Count/index still retain duplicate entries in the registry.
        expected = expected_hashes[path]
        if type(expected) is not str or len(expected) != 64:
            raise ValueError('Missing script source identity')
        with path.open('rb') as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
        total += len(data)
        if len(data) > MAX_SOURCE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('Gameplay script snapshot exceeds its byte budget')
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Gameplay script differs from its selected identity')
        result[path] = data
    return result


def bootstrap_cached_context(runtime, child, name, *, include=False):
    """Reuse the existing gameplay bootstrap against the registered Core cache.

    No second Core registration, replacement API, guessed include roots or
    empty namespace is created. Missing caches/bindings remain native errors.
    The resolved include snapshot, when needed, belongs to the runtime owner.
    """
    if (type(name) is not bytes or not name or b'\0' in name or len(name)>259
            or type(include) is not bool):
        raise ValueError('Invalid cached script bootstrap name or include mode')
    runtime.registry.validate(child)
    runtime.attach_standard_libraries(child)
    runtime.attach_game_events(child)
    if include:
        runtime.attach_include(child)
    for namespace in ('DB','GameInfo','GlobalParameters','Path','Locale'):
        runtime.namespaces.register(child,namespace)
    runtime.attach_native_game_api(child)
    from .native.native_script_parameters import lua_string
    runtime.execute(child,('StateName='+lua_string(name)).encode('ascii'),b'@gameplay_context_name')


class ScriptContextService:
    # +10 is separately owned by the reused notification adapter.
    SLOTS = (0x00, 0x08, 0x18, 0x20, 0x28, 0x30, 0xD0, 0xD8)

    def __init__(self, host, runtime, registry, *, expected_hashes, bootstrap, read,
                 execution_image=None):
        runtime.registry._check()
        if getattr(host, '_script_context_service', None) is not None:
            raise RuntimeError('Gameplay script callbacks already have an owner')
        if not callable(bootstrap) or not callable(read):
            raise TypeError('An explicit context bootstrap and bounded reader are required')
        self.sources = snapshot_scripts(registry, expected_hashes)
        self.host, self.runtime, self.registry = host, runtime, registry
        self.bootstrap, self.read = bootstrap, read
        self.paths = tuple(registry.paths)
        self.wire_paths = tuple(registry.wire_paths)
        self.wire_sources = bind_wire_sources(self.paths, self.wire_paths)
        self.names = {}; self.loaded = set()
        self.closed = self.quarantined = False
        self.depth = self.lock_depth = 0
        self.receiver = C.addressof(host.aux_object)
        self.lifetime = RetainedScriptContexts(runtime, project_root=self._root(),
                                               execution_image=execution_image)
        table = C.addressof(host.aux_vtable)
        bindings = getattr(host, '_slot_bindings', {})
        self.previous = {s:(host.aux_vtable[s//8], bindings.get((table,s))) for s in self.SLOTS}
        before = len(host.functions)
        # Any partial installation is an isolated-worker failure, not rollback.
        host._script_context_service = self
        self.notification = NativeContextNotification(runtime, host, project_root=self._root(),
                                                      execution_image=execution_image)
        signatures = (
            (0x00,C.c_void_p,[C.c_void_p,C.c_char_p,C.c_uint8],self.acquire),
            (0x08,None,[C.c_void_p,C.c_void_p],self.release),
            (0x18,C.c_uint8,[C.c_void_p,C.c_void_p,C.c_void_p],self.load),
            (0x20,C.c_uint8,[C.c_void_p,C.c_void_p,C.c_uint8],self.file_exists),
            (0x28,C.c_uint32,[C.c_void_p],self.script_count),
            (0x30,C.c_void_p,[C.c_void_p,C.c_int],self.script_path),
            (0xD0,None,[C.c_void_p],self.lock),
            (0xD8,None,[C.c_void_p],self.unlock),
        )
        for slot,result,args,method in signatures:
            host._bind(host.aux_vtable,slot,result,args,method)
        self.installed = {s:host.aux_vtable[s//8] for s in self.SLOTS}
        self.functions = tuple(host.functions[before:])

    @staticmethod
    def _root():
        from .paths import resource_root
        return resource_root()

    def check(self, this):
        self.runtime.registry._check()
        if self.closed or self.quarantined or self.host._script_context_service is not self:
            raise RuntimeError('Script contexts closed, replaced or quarantined')
        if this != self.receiver:
            raise ValueError('Wrong script context receiver')
        if tuple(self.registry.paths) != self.paths or tuple(self.registry.wire_paths) != self.wire_paths:
            raise RuntimeError('Gameplay script selection changed while retained')

    def _path(self, address):
        if not address:
            raise ValueError('Null gameplay script path')
        data = bytearray()
        for i in range(260):
            unit = self.read(address+2*i,2)
            if len(unit) != 2:
                raise ValueError('Incomplete gameplay path read')
            if unit == b'\0\0':
                path = data.decode('utf-16-le','strict')
                if path not in self.wire_sources:
                    raise ValueError('Unresolved or unselected gameplay script path')
                return path
            data.extend(unit)
        raise ValueError('Gameplay script path lacks bounded terminator')

    def script_count(self, this):
        self.check(this)
        return self.registry.count()

    def script_path(self, this, index):
        self.check(this)
        return self.registry.get(index)

    def file_exists(self, this, path, redirected):
        self.check(this)
        if redirected != 1:
            raise ValueError('Unqualified script path resolution mode')
        selected = self._path(path)
        # The selection contains already-resolved absolute regular files.
        # A stale/missing file must not silently remove gameplay rules.
        if not self.wire_sources[selected].is_file():
            raise ValueError('Selected gameplay script disappeared')
        return 1

    def acquire(self, this, name, flags):
        self.check(this)
        if flags != 0 or name not in {script_name(p) for p in self.wire_paths}:
            raise ValueError('Unqualified script context name or flags')
        self.depth += 1
        try:
            child = self.lifetime.acquire()
            self.names[child.pointer] = name
            self.bootstrap(child, name)
            self.host.emit('native_gameplay_context_acquired',script_name=name.decode('utf-8'),
                           complete_exe_factory=False)
            return child.pointer
        except BaseException:
            self.quarantined = True
            raise
        finally:
            self.depth -= 1

    def load(self, this, pointer, path):
        self.check(this)
        selected = self._path(path)
        source = self.wire_sources[selected]
        if pointer not in self.names or self.names[pointer] != script_name(selected) or pointer in self.loaded:
            raise ValueError('Gameplay script does not match its fresh owned context')
        child = self.lifetime._contexts[pointer]
        self.depth += 1
        try:
            self.runtime.execute(child,self.sources[source],selected.encode('utf-8'))
            self.loaded.add(pointer)
            self.host.emit('native_gameplay_context_loaded',script_name=self.names[pointer].decode('utf-8'),
                           sha256=hashlib.sha256(self.sources[source]).hexdigest(),strict_load_errors=True)
            return 1
        except BaseException:
            self.quarantined = True
            raise
        finally:
            self.depth -= 1

    def release(self, this, pointer):
        self.check(this)
        if pointer not in self.names:
            raise ValueError('Unknown or already released gameplay context')
        try:
            self.lifetime.release(pointer)
        except BaseException:
            self.quarantined = True
            raise
        del self.names[pointer]
        self.loaded.discard(pointer)
        self.host.emit('native_gameplay_context_released')

    def lock(self, this):
        self.check(this)
        fn = self.runtime.host.LAB_ScriptLockEnter
        fn.argtypes,fn.restype = [],C.c_int
        if fn() != 1:
            self.quarantined = True
            raise RuntimeError('Script critical section acquisition failed')
        self.lock_depth += 1

    def unlock(self, this):
        self.check(this)
        if not self.lock_depth:
            raise RuntimeError('Script critical section release without ownership')
        fn = self.runtime.host.LAB_ScriptLockLeave
        fn.argtypes,fn.restype = [],C.c_int
        if fn() != 1:
            self.quarantined = True
            raise RuntimeError('Script critical section release failed')
        self.lock_depth -= 1

    def close(self):
        self.runtime.registry._check()
        if self.closed:
            return
        self.check(self.receiver)
        if self.depth or self.lock_depth or self.names or self.lifetime.handles:
            raise RuntimeError('Gameplay script contexts still owned by their native consumer')
        if any(self.host.aux_vtable[s//8] != v for s,v in self.installed.items()):
            raise RuntimeError('Gameplay script callback ownership changed')
        self.notification.close()
        self.lifetime.close()
        table = C.addressof(self.host.aux_vtable)
        for slot,(address,binding) in self.previous.items():
            self.host.aux_vtable[slot//8] = address
            if binding is None:
                self.host._slot_bindings.pop((table,slot),None)
            else:
                self.host._slot_bindings[table,slot] = binding
        owned = {id(f) for f in self.functions}
        self.host.functions[:] = [f for f in self.host.functions if id(f) not in owned]
        self.host._script_context_service = None
        self.closed = True
        self.sources.clear()
        self.functions = ()

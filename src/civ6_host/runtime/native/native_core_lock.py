"""Source-backed EXE GameCore lock ownership service; no graphics involved."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import threading

class NativeCoreLock:

    def __init__(self, host, executable):
        from civ6_host.runtime.native.native_host_slot48 import verify_source_evidence
        verify_source_evidence()
        self.host = host
        self.calls = {}
        for operation, name in (('create', 'Create'), ('owned', 'Owned'), ('acquire', 'Acquire'), ('try_acquire', 'TryAcquire'), ('release', 'Release'), ('destroy', 'Destroy')):
            call = getattr(executable, 'LAB_CoreLock' + name)
            call.argtypes, call.restype = ([], C.c_int)
            self.calls[operation] = call
        if self.calls['create']() != 1:
            raise RuntimeError('GameCore execution lock already owned by another adapter')
        host._bind(host.vtable, 48, C.c_bool, [C.c_void_p], self.owned)
        host._bind(host.vtable, 56, None, [C.c_void_p], self.release)
        host._bind(host.vtable, 64, None, [C.c_void_p], self.acquire)
        host._bind(host.vtable, 72, C.c_bool, [C.c_void_p], self.try_acquire)
        if self.calls['owned']() != 0:
            raise RuntimeError('New Core lock has an unexpected owner')
        self.acquire(host.pointer)
        self.acquire(host.pointer)
        if not self.owned(host.pointer):
            raise RuntimeError('Core recursive lock ownership missing')
        self.release(host.pointer)
        if not self.owned(host.pointer):
            raise RuntimeError('Core lock lost its recursive owner')
        self.release(host.pointer)
        if self.owned(host.pointer):
            raise RuntimeError('Core lock retained its owner after release')
        self._verify_try_acquire()
        host.emit('native_core_execution_lock_enabled', recursive_ownership_verified=True, initial_worker_ownership=False, exe_stall_logging_reproduced=False, recursive_try_acquire_verified=True, contended_try_returns_false=True, failed_try_preserves_owner=True, other_thread_release_verified=True)

    def _verify_try_acquire(self):
        """Exercise the actual nonblocking result while another thread owns it."""

        def other_thread_try():
            result = self.calls['try_acquire']()
            owned = self.calls['owned']()
            if result == 1:
                released = self.calls['release']()
            else:
                released = None
            return (result, owned, released, self.calls['owned']())

        def run_thread():
            output = []

            def worker():
                try:
                    output.append(other_thread_try())
                except BaseException as exc:
                    output.append(exc)
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            thread.join(2)
            if thread.is_alive() or len(output) != 1 or isinstance(output[0], BaseException):
                raise RuntimeError('Core try-lock contention diagnostic did not return')
            return output[0]
        if not self.try_acquire(self.host.pointer):
            raise RuntimeError('Unowned Core lock could not be acquired')
        try:
            if not self.try_acquire(self.host.pointer):
                raise RuntimeError('Recursive Core try-lock failed')
            self.release(self.host.pointer)
            if run_thread() != (0, 0, None, 0) or not self.owned(self.host.pointer):
                raise RuntimeError('Failed Core try-lock changed ownership')
        finally:
            self.release(self.host.pointer)
        if run_thread() != (1, 1, 1, 0) or self.owned(self.host.pointer):
            raise RuntimeError('Core try-lock transfer/release contract differs')

    def owned(self, this):
        self.host._check(this)
        result = self.calls['owned']()
        if result not in (0, 1):
            raise RuntimeError('Core lock used outside its lifetime')
        return bool(result)

    def acquire(self, this):
        self.host._check(this)
        if self.calls['acquire']() != 1:
            raise RuntimeError('Core execution lock acquisition failed')

    def try_acquire(self, this):
        self.host._check(this)
        result = self.calls['try_acquire']()
        if result not in (0, 1):
            raise RuntimeError('Core try-lock used outside its lifetime')
        return bool(result)

    def release(self, this):
        self.host._check(this)
        if self.calls['release']() != 1:
            raise RuntimeError('Core execution lock release is unbalanced')

    def close(self):
        if self.calls['destroy']() != 1:
            raise RuntimeError('Core execution lock still owned at destruction')

"""Current-process Host41 job observer factory. No Core or job export is called."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import os
from pathlib import Path
from civ6_host.runtime.native import native_checkpoint_jobs as jobs

class CurrentProcessApi:
    """Only kernel32 process identity getters; never loads the target executable."""

    def __init__(self):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('Current executable observation requires Win64')
        self.kernel32 = C.WinDLL('kernel32', use_last_error=True)
        self.module = self.kernel32.GetModuleHandleW
        self.module.argtypes, self.module.restype = ([C.c_wchar_p], C.c_void_p)
        self.filename = self.kernel32.GetModuleFileNameW
        self.filename.argtypes, self.filename.restype = ([C.c_void_p, C.c_wchar_p, C.c_uint32], C.c_uint32)
        self.thread = self.kernel32.GetCurrentThreadId
        self.thread.argtypes, self.thread.restype = ([], C.c_uint32)

    def main_module(self):
        pointer = int(self.module(None) or 0)
        if not pointer:
            raise RuntimeError('GetModuleHandleW(NULL) failed')
        return pointer

    def module_filename(self, module):
        output = C.create_unicode_buffer(32768)
        used = int(self.filename(module, output, len(output)))
        if not 0 < used < len(output):
            raise RuntimeError('GetModuleFileNameW failed or truncated the executable path')
        return output.value

    def current_thread_id(self):
        return int(self.thread())

def _path(path):
    if not isinstance(path, (str, os.PathLike)) or not str(path):
        raise ValueError('An explicit executable path is required')
    result = _resolve_resource_path(Path(path))
    if not result.is_absolute():
        raise ValueError('Executable path must be absolute')
    result = _resolve_resource_path(result).resolve()
    if not _resolve_resource_path(result).is_file():
        raise ValueError('Executable path is not an existing file')
    return result

class JobObserver:
    """Repeated strict snapshots of one current executable on its owner thread.

    exclusive_owner_entry is a callable supplied by the checkpoint orchestrator.
    It must admit only the two top-level snapshot phases around synchronous Save,
    never a callback, query, job, drain or arbitrary threaded caller.
    """

    def __init__(self, read, *, expected_executable_path, owner_thread_id, profile, exclusive_owner_entry, os_api=None, read_image=None):
        if not callable(read) or not callable(exclusive_owner_entry):
            raise ValueError('Safe reader and explicit checkpoint entry predicate required')
        if profile != jobs.PROFILE:
            raise ValueError('Unrecognized serial host profile')
        jobs._positive_int(owner_thread_id, 'native host owner thread', 4294967295)
        jobs.verify_source()
        self.read = read
        self.api = CurrentProcessApi() if os_api is None else os_api
        self.read_image = (lambda p: _resolve_resource_path(p).read_bytes()) if read_image is None else read_image
        if not callable(self.read_image):
            raise ValueError('Image reader must be callable')
        self.expected_path = _path(expected_executable_path)
        self.owner_thread_id, self.profile = (owner_thread_id, profile)
        self.exclusive_owner_entry = exclusive_owner_entry
        self.busy = False
        self.identity = self._identity()
        self._image_bytes()

    def _identity(self):
        base = self.api.main_module()
        jobs._positive_int(base, 'actual executable base')
        thread = self.api.current_thread_id()
        jobs._positive_int(thread, 'actual current Win32 thread ID', 4294967295)
        if thread != self.owner_thread_id:
            raise RuntimeError('Job observer is on a foreign Win32 thread')
        actual = _path(self.api.module_filename(base))
        if os.path.normcase(str(actual)) != os.path.normcase(str(self.expected_path)):
            raise RuntimeError('Actual executable path differs from the expected worker host')
        return dict(host_base=base, executable_path=str(actual), os_thread_id=thread)

    def _image_bytes(self):
        data = self.read_image(self.expected_path)
        if type(data) is not bytes or hashlib.sha256(data).hexdigest() != jobs.HOST_SHA256:
            raise RuntimeError('Actual executable file is not pinned Host41')
        return data

    def __call__(self):
        if self.busy or self.exclusive_owner_entry() is not True:
            raise RuntimeError('Job snapshot requires a nonreentrant exclusive checkpoint phase')
        self.busy = True
        try:
            identity = self._identity()
            if identity != self.identity:
                raise RuntimeError('Actual executable identity changed')
            snapshot = jobs.capture_snapshot(self.read, identity['host_base'], self._image_bytes(), identity['os_thread_id'], profile=self.profile, exclusive_owner_entry=True)
            jobs.require_quiescent(snapshot)
            if self._identity() != identity or self.exclusive_owner_entry() is not True:
                raise RuntimeError('Checkpoint identity or admission changed during snapshot')
            return dict(snapshot, current_executable=identity)
        finally:
            self.busy = False

def make_job_observer(read, **kwargs):
    return JobObserver(read, **kwargs)

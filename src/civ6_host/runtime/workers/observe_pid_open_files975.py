"""Read-only Win64 witness for requested files held open by one PID.

Only requested roles are returned. This proves a process has an open handle to
the same file object, not that SQLite used it for a database connection.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import os
from pathlib import Path
import time
from typing import Mapping
PROCESS_DUP_HANDLE = 64
PROCESS_QUERY_INFORMATION = 1024
PROCESS_QUERY_LIMITED_INFORMATION = 4096
STATUS_INFO_LENGTH_MISMATCH = 3221225476
FILE_ID_INFO_CLASS = 18
GENERIC_READ = 2147483648
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = C.c_void_p(-1).value
MAX_SYSTEM_HANDLE_BYTES = 128 * 1024 * 1024
MAX_PROCESS_HANDLES = 100000

class OpenFileObservationError(RuntimeError):
    """A complete, identity-stable handle scan could not be established."""

class FILE_ID_INFO(C.Structure):
    _fields_ = [('VolumeSerialNumber', C.c_uint64), ('FileId', C.c_ubyte * 16)]

class PROCESS_HANDLE_TABLE_ENTRY_INFO(C.Structure):
    _fields_ = [('HandleValue', C.c_void_p), ('HandleCount', C.c_size_t), ('PointerCount', C.c_size_t), ('GrantedAccess', C.c_ulong), ('ObjectTypeIndex', C.c_ulong), ('HandleAttributes', C.c_ulong), ('Reserved', C.c_ulong)]

def _identity(kernel32, handle, pid: int) -> dict:
    exit_code = C.c_uint32()
    if not kernel32.GetExitCodeProcess(handle, C.byref(exit_code)) or exit_code.value != 259:
        raise OpenFileObservationError('PID is not running')
    created, exited, kernel_time, user_time = (C.c_uint64() for _ in range(4))
    if not kernel32.GetProcessTimes(handle, C.byref(created), C.byref(exited), C.byref(kernel_time), C.byref(user_time)):
        raise C.WinError(C.get_last_error())
    size = C.c_uint32(32768)
    image = C.create_unicode_buffer(size.value)
    if not kernel32.QueryFullProcessImageNameW(handle, 0, image, C.byref(size)):
        raise C.WinError(C.get_last_error())
    return {'pid': pid, 'creation_filetime': created.value, 'image_path': image.value}

def _query_process_handle_table(ntdll, process, deadline: float):
    query = ntdll.NtQueryInformationProcess
    query.argtypes = [C.c_void_p, C.c_int, C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong)]
    query.restype = C.c_long
    size = 1024 * 1024
    while size <= MAX_SYSTEM_HANDLE_BYTES:
        if time.monotonic() > deadline:
            raise TimeoutError('System handle enumeration timed out')
        storage = C.create_string_buffer(size)
        needed = C.c_ulong()
        status = query(process, 51, storage, size, C.byref(needed))
        if status == 0:
            if not needed.value or needed.value > size:
                raise OpenFileObservationError('Process handle query returned an invalid byte length')
            return (storage, needed.value)
        if C.c_uint32(status).value != STATUS_INFO_LENGTH_MISMATCH:
            raise OpenFileObservationError(f'NtQueryInformationProcess failed: 0x{C.c_uint32(status).value:08x}')
        size = max(size * 2, needed.value)
    raise OpenFileObservationError('System handle table exceeds scan bound')

def _file_id(kernel32, handle) -> tuple[int, bytes] | None:
    info = FILE_ID_INFO()
    if not kernel32.GetFileInformationByHandleEx(handle, FILE_ID_INFO_CLASS, C.byref(info), C.sizeof(info)):
        return None
    return (int(info.VolumeSerialNumber), bytes(info.FileId))

def _open_target_handles(kernel32, paths: Mapping[str, Path]):
    opened = {}
    try:
        for role, path in paths.items():
            source = _resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True)
            if not _resolve_resource_path(source).is_file():
                raise ValueError(f'{role} is not a regular file: {source}')
            handle = kernel32.CreateFileW(str(source), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, None, OPEN_EXISTING, 0, None)
            if handle == INVALID_HANDLE_VALUE:
                raise C.WinError(C.get_last_error())
            ident = _file_id(kernel32, handle)
            if ident is None:
                kernel32.CloseHandle(handle)
                raise OpenFileObservationError(f'Could not read file identity for requested role {role}')
            opened[role] = (ident, handle)
        return opened
    except Exception:
        for _ident, handle in opened.values():
            kernel32.CloseHandle(handle)
        raise

def _process_handle_entries(storage, used: int) -> list[PROCESS_HANDLE_TABLE_ENTRY_INFO]:
    if used < 2 * C.sizeof(C.c_size_t):
        raise OpenFileObservationError('Truncated process handle table')
    count = C.c_size_t.from_buffer(storage, 0).value
    if count > MAX_PROCESS_HANDLES:
        raise OpenFileObservationError('Process handle count exceeds scan bound')
    entry_size = C.sizeof(PROCESS_HANDLE_TABLE_ENTRY_INFO)
    offset = 2 * C.sizeof(C.c_size_t)
    if offset + count * entry_size > used or used > len(storage):
        raise OpenFileObservationError('Process handle table length is inconsistent')
    return [PROCESS_HANDLE_TABLE_ENTRY_INFO.from_buffer(storage, offset + i * entry_size) for i in range(count)]

def observe_pid_open_files(pid: int, paths: Mapping[str, Path], *, expected_identity: dict | None=None, timeout_seconds: float=20.0) -> dict:
    """Return open/closed for requested roles after a complete stable scan.

    Windows handle enumeration is inherently racy. Any inaccessible handle,
    process identity change, scan bound, or timeout refuses the observation;
    it never converts an incomplete scan into a negative result.
    """
    if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
        raise RuntimeError('Requested-file handle witness requires Win64')
    if type(pid) is not int or not 0 < pid < 2 ** 32:
        raise ValueError('Invalid explicit process id')
    if pid == os.getpid():
        raise ValueError('The observer cannot inspect itself because its reference handles would be false evidence')
    if not paths or len(paths) > 32 or any((not isinstance(k, str) or not k for k in paths)):
        raise ValueError('Provide 1..32 named file roles')
    if type(timeout_seconds) not in (int, float) or not 0.1 <= timeout_seconds <= 60:
        raise ValueError('Timeout must be between 0.1 and 60 seconds')
    deadline = time.monotonic() + timeout_seconds
    kernel = C.WinDLL('kernel32', use_last_error=True)
    ntdll = C.WinDLL('ntdll')
    kernel.OpenProcess.argtypes = [C.c_uint32, C.c_int, C.c_uint32]
    kernel.OpenProcess.restype = C.c_void_p
    kernel.CloseHandle.argtypes = [C.c_void_p]
    kernel.CloseHandle.restype = C.c_int
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = C.c_void_p
    kernel.DuplicateHandle.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p), C.c_uint32, C.c_int, C.c_uint32]
    kernel.DuplicateHandle.restype = C.c_int
    kernel.GetExitCodeProcess.argtypes = [C.c_void_p, C.POINTER(C.c_uint32)]
    kernel.GetExitCodeProcess.restype = C.c_int
    kernel.GetProcessTimes.argtypes = [C.c_void_p, *[C.POINTER(C.c_uint64)] * 4]
    kernel.GetProcessTimes.restype = C.c_int
    kernel.QueryFullProcessImageNameW.argtypes = [C.c_void_p, C.c_uint32, C.c_wchar_p, C.POINTER(C.c_uint32)]
    kernel.QueryFullProcessImageNameW.restype = C.c_int
    kernel.GetFileInformationByHandleEx.argtypes = [C.c_void_p, C.c_int, C.c_void_p, C.c_uint32]
    kernel.GetFileInformationByHandleEx.restype = C.c_int
    kernel.GetFileType.argtypes = [C.c_void_p]
    kernel.GetFileType.restype = C.c_uint32
    kernel.SetLastError.argtypes = [C.c_uint32]
    kernel.SetLastError.restype = None
    kernel.CreateFileW.argtypes = [C.c_wchar_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p]
    kernel.CreateFileW.restype = C.c_void_p
    opened_targets = _open_target_handles(kernel, paths)
    wanted = {role: value[0] for role, value in opened_targets.items()}
    process = kernel.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_DUP_HANDLE, False, pid)
    if not process:
        for _ident, target_handle in opened_targets.values():
            kernel.CloseHandle(target_handle)
        raise C.WinError(C.get_last_error())
    current = kernel.GetCurrentProcess()
    try:
        local_storage, local_used = _query_process_handle_table(ntdll, current, deadline)
        local_entries = _process_handle_entries(local_storage, local_used)
        wanted_handles = {int(handle): ident for ident, handle in opened_targets.values()}
        file_type_indices = {int(entry.ObjectTypeIndex) for entry in local_entries if int(entry.HandleValue or 0) in wanted_handles}
        if not file_type_indices:
            raise OpenFileObservationError('Could not identify local file handle type')
        if len(file_type_indices) != 1:
            raise OpenFileObservationError('Requested paths resolved to inconsistent kernel file types')
        before = _identity(kernel, process, pid)
        if expected_identity is not None and before != expected_identity:
            raise OpenFileObservationError('PID creation/image differs from expected identity')
        storage, used = _query_process_handle_table(ntdll, process, deadline)
        process_handles = [int(entry.HandleValue) for entry in _process_handle_entries(storage, used) if int(entry.ObjectTypeIndex) in file_type_indices]
        matches: dict[str, tuple[int, bytes]] = {}
        for number, remote_value in enumerate(process_handles):
            if time.monotonic() > deadline:
                raise TimeoutError('Target process handle scan timed out')
            duplicate = C.c_void_p()
            if not kernel.DuplicateHandle(process, C.c_void_p(remote_value), current, C.byref(duplicate), 0, False, 2):
                error = C.get_last_error()
                raise OpenFileObservationError(f'A target-process handle could not be duplicated (WinError {error}); scan incomplete')
            try:
                kernel.SetLastError(0)
                file_type = kernel.GetFileType(duplicate)
                if file_type == 0:
                    if C.get_last_error() != 0:
                        raise OpenFileObservationError('A file-object type query failed; scan incomplete')
                    continue
                if file_type != 1:
                    continue
                ident = _file_id(kernel, duplicate)
                if ident is None:
                    raise OpenFileObservationError('A disk handle identity could not be read; scan incomplete')
                for role, expected_id in wanted.items():
                    if ident == expected_id:
                        matches[role] = ident
            finally:
                kernel.CloseHandle(duplicate)
        after = _identity(kernel, process, pid)
        if after != before:
            raise OpenFileObservationError('PID identity changed during handle scan')
        if expected_identity is not None and after != expected_identity:
            raise OpenFileObservationError('PID identity changed from expected capture identity')
        roles = {}
        for role, expected_id in wanted.items():
            matched = matches.get(role)
            roles[role] = {'open': matched is not None, 'file_identity_sha256': hashlib.sha256(expected_id[0].to_bytes(8, 'little') + expected_id[1]).hexdigest()}
        return {'process_identity': before, 'process_identity_stable': True, 'complete_scan': True, 'requested_roles': roles}
    finally:
        kernel.CloseHandle(process)
        for _ident, target_handle in opened_targets.values():
            kernel.CloseHandle(target_handle)

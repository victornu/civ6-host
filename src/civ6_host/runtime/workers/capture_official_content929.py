"""Read resolved content from an already-running, hash-pinned Civ6 process.

Never starts/stops/suspends a process, injects code, writes memory, or controls a
window. Its output is an unbound capture, not a reusable training bundle yet.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import argparse
import ctypes as C
import hashlib
import json
import os
import sys
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/capture_official_content929.py')))).resolve().parents[1]
from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
from civ6_host.runtime.native.native_resolved_content import EXE_SHA
from civ6_host.runtime.native.native_resolved_content import read_resolved_content
from civ6_host.runtime.native.native_resolved_content import source_profile
PROCESS_QUERY_INFORMATION = 1024
PROCESS_VM_READ = 16

class ModuleEntry(C.Structure):
    _fields_ = [('dwSize', C.c_uint32), ('th32ModuleID', C.c_uint32), ('th32ProcessID', C.c_uint32), ('GlblcntUsage', C.c_uint32), ('ProccntUsage', C.c_uint32), ('modBaseAddr', C.c_void_p), ('modBaseSize', C.c_uint32), ('hModule', C.c_void_p), ('szModule', C.c_wchar * 256), ('szExePath', C.c_wchar * 260)]

class ReadOnlyProcess:
    """Small Windows memory transport with QUERY_INFORMATION|VM_READ only."""

    def __init__(self, pid):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('Read-only capture requires Win64')
        if type(pid) is not int or not 0 < pid < 2 ** 32:
            raise ValueError('Invalid explicit process id')
        self.pid, self.handle = (pid, None)
        self.k = C.WinDLL('kernel32', use_last_error=True)
        signatures = {'OpenProcess': ([C.c_uint32, C.c_int, C.c_uint32], C.c_void_p), 'CloseHandle': ([C.c_void_p], C.c_int), 'ReadProcessMemory': ([C.c_void_p, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)], C.c_int), 'QueryFullProcessImageNameW': ([C.c_void_p, C.c_uint32, C.c_wchar_p, C.POINTER(C.c_uint32)], C.c_int), 'GetProcessTimes': ([C.c_void_p, *[C.POINTER(C.c_uint64)] * 4], C.c_int), 'GetExitCodeProcess': ([C.c_void_p, C.POINTER(C.c_uint32)], C.c_int), 'CreateToolhelp32Snapshot': ([C.c_uint32, C.c_uint32], C.c_void_p), 'Module32FirstW': ([C.c_void_p, C.POINTER(ModuleEntry)], C.c_int), 'Module32NextW': ([C.c_void_p, C.POINTER(ModuleEntry)], C.c_int)}
        for name, (args, restype) in signatures.items():
            fn = getattr(self.k, name)
            fn.argtypes, fn.restype = (args, restype)

    def __enter__(self):
        if self.handle:
            raise RuntimeError('Process handle already open')
        self.handle = self.k.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, self.pid)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        return self

    def __exit__(self, *unused):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None

    def identity(self):
        if not self.handle:
            raise RuntimeError('Process handle closed')
        code = C.c_uint32()
        if not self.k.GetExitCodeProcess(self.handle, C.byref(code)):
            raise C.WinError(C.get_last_error())
        if code.value != 259:
            raise RuntimeError('Source process has exited')
        created, exited, kernel, user = (C.c_uint64() for _ in range(4))
        if not self.k.GetProcessTimes(self.handle, C.byref(created), C.byref(exited), C.byref(kernel), C.byref(user)):
            raise C.WinError(C.get_last_error())
        size = C.c_uint32(32768)
        path = C.create_unicode_buffer(size.value)
        if not self.k.QueryFullProcessImageNameW(self.handle, 0, path, C.byref(size)):
            raise C.WinError(C.get_last_error())
        return {'pid': self.pid, 'creation_filetime': created.value, 'image_path': path.value}

    def modules(self):
        self.identity()
        snapshot = self.k.CreateToolhelp32Snapshot(8 | 16, self.pid)
        if snapshot == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            entry = ModuleEntry()
            entry.dwSize = C.sizeof(entry)
            if not self.k.Module32FirstW(snapshot, C.byref(entry)):
                raise C.WinError(C.get_last_error())
            result = []
            while True:
                result.append({'name': entry.szModule, 'path': entry.szExePath, 'base': int(entry.modBaseAddr), 'bytes': entry.modBaseSize})
                if len(result) > 4096:
                    raise RuntimeError('Module enumeration bound exceeded')
                if not self.k.Module32NextW(snapshot, C.byref(entry)):
                    if C.get_last_error() != 18:
                        raise C.WinError(C.get_last_error())
                    return result
        finally:
            self.k.CloseHandle(snapshot)

    def read(self, address, size):
        if not self.handle:
            raise RuntimeError('Process handle closed')
        if type(size) is not int or not 0 < size <= 1024 * 1024:
            raise ValueError('Memory transport read bound exceeded')
        buffer = C.create_string_buffer(size)
        copied = C.c_size_t()
        if not self.k.ReadProcessMemory(self.handle, address, buffer, size, C.byref(copied)):
            raise C.WinError(C.get_last_error())
        if copied.value != size:
            raise RuntimeError('Partial ReadProcessMemory result')
        return buffer.raw

def capture(pid, *, executable_sha256=EXE_SHA):
    expected = _resolve_resource_path(_resolve_resource_path(Path(source_profile(executable_sha256)['image']['path']))).resolve(strict=True)
    if hashlib.sha256(_resolve_resource_path(expected).read_bytes()).hexdigest() != executable_sha256:
        raise ValueError('Installed Civ6 image differs from pinned source')
    with ReadOnlyProcess(pid) as process:
        identity = process.identity()
        if _resolve_resource_path(_resolve_resource_path(Path(identity['image_path']))).resolve(strict=True) != expected:
            raise ValueError('PID does not identify the pinned CivilizationVI executable')
        modules = process.modules()
        main = [m for m in modules if _resolve_resource_path(_resolve_resource_path(Path(m['path']))).resolve() == expected]
        if len(main) != 1:
            raise ValueError('Main image module is ambiguous')
        gamecores = [m for m in modules if m['name'].lower().startswith('gamecore_') and m['name'].lower().endswith('.dll')]
        if len(gamecores) != 1:
            raise ValueError('Capture requires exactly one loaded GameCore image')
        core = gamecores[0]
        core_sha = hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(core['path']))).read_bytes()).hexdigest()
        state = read_resolved_content(process.read, main[0]['base'], executable_sha256=executable_sha256)
        if process.identity() != identity:
            raise RuntimeError('Process identity changed during capture')
        after = process.modules()
        for module in [*main, *gamecores]:
            if module not in after:
                raise RuntimeError('A relevant module changed during capture')
        if hashlib.sha256(_resolve_resource_path(expected).read_bytes()).hexdigest() != executable_sha256:
            raise RuntimeError('EXE file changed during capture')
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(core['path']))).read_bytes()).hexdigest() != core_sha:
            raise RuntimeError('GameCore file changed during capture')
    return {'schema': 'civ6rl.official_resolved_content929.capture.v2' if executable_sha256 == CURRENT_EXE_SHA else 'civ6rl.official_resolved_content929.capture.v1', 'process': identity, 'exe_module': main[0], 'gamecore_module': {**core, 'sha256': core_sha}, 'snapshot': state, 'read_only_process_rights': PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 'game_executable_launched': False, 'remote_code_executed': False, 'process_suspended': False, 'memory_written': False, 'save_database_script_bundle_qualified': False, 'strategic_training_ready': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--executable-sha256', choices=(EXE_SHA, CURRENT_EXE_SHA), default=EXE_SHA)
    args = parser.parse_args()
    out = _resolve_resource_path(args.output).resolve()
    if not out.is_relative_to(ROOT / 'work') or _resolve_resource_path(out).exists():
        raise ValueError('Use a fresh output path beneath project work/')
    result = capture(args.pid, executable_sha256=args.executable_sha256)
    out.parent.mkdir(parents=True, exist_ok=True)
    with _resolve_resource_path(out).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'path': str(out), 'strategic_training_ready': False, 'components_read': len(result['snapshot']['ordered_component_handles'])}))
if __name__ == '__main__':
    main()

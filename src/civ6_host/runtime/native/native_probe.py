"""Isolated, version-pinned probes for the native Civ6 GameCore (Windows x64).

Loading a context is NOT running a game. Verified diagnostic rounds are counted
separately from complete games; this module does not report strategic throughput.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
import ctypes as C
from ctypes import wintypes as W
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import threading
import time
import shutil
import uuid
BASE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
DEFAULT_DLL = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Binaries\\Win64Steam\\GameCore_Base_FinalRelease.dll"))
DEPENDENCIES = {'database': 'DatabaseDLL_FinalRelease.dll', 'localization': 'Localization_FinalRelease.dll', 'havok': 'HavokScript_FinalRelease.dll'}
LOCAL_PLAYER_MODE = 'trace-newgame-local-player-no-tuner'
SCRIPT_CORE_MODE = 'trace-script-core-services-no-tuner'
SCRIPT_MAP_MODE = 'trace-newgame-script-prefix-no-tuner'
BASE_PROVIDER_MODE = 'trace-base-embedded-provider-import'
CONFIGURATION_ONLY_MODE = 'trace-checkpoint-configuration-only'
CHECKPOINT_LOAD_MODE = 'trace-checkpoint-load-only'
CHECKPOINT_FACADES_MODE = 'trace-checkpoint-load-facades'
CHECKPOINT_POST160_MODE = 'trace-checkpoint-load-post160'
CHECKPOINT_RETAINED121_POST160_MODE = 'trace-checkpoint-load-retained121-post160'
CHECKPOINT_RETAINED150_POST160_MODE = 'trace-checkpoint-load-retained150-post160'
CHECKPOINT_RETAINED150_OWNED_MODE = 'trace-checkpoint-load-retained150-owned-state'
CHECKPOINT_RETAINED121_RESUME_MODE = 'trace-checkpoint-resume-retained121-one-round'
CHECKPOINT_RETAINED150_RESUME_MODE = 'trace-checkpoint-resume-retained150-one-round'
CHECKPOINT_RETAINED182_RESUME_MODE = 'trace-checkpoint-resume-retained182-one-round'
CHECKPOINT_PREVICTORY12_RESUME_MODE = 'trace-checkpoint-resume-previctory12-one-round'
CHECKPOINT_RESUME_MODE = 'trace-checkpoint-resume-one-round'
CHECKPOINT_LATE_RESUME_MODE = 'trace-checkpoint-resume-late114-one-round'
CHECKPOINT_LATE_ROUNDS_MODE = 'trace-checkpoint-resume-late114-bounded-rounds'
CHECKPOINT_RETAINED_RESUME_MODE = 'trace-checkpoint-resume-retained118-one-round'
CHECKPOINT_RETAINED_ROUNDS_MODE = 'trace-checkpoint-resume-retained118-bounded-rounds'
CHECKPOINT_RETAINED_LONG_ROUNDS_MODE = 'trace-checkpoint-resume-retained118-long-bounded-rounds'
CHECKPOINT_RETAINED150_LONG_ROUNDS_MODE = 'trace-checkpoint-resume-retained150-long-bounded-rounds'
CHECKPOINT_RETAINED_SAVE_MODE = 'trace-checkpoint-resume-late114-save118'
CHECKPOINT_RETAINED121_SAVE_MODE = 'trace-checkpoint-resume-retained118-save121'
CHECKPOINT_RETAINED150_SAVE_MODE = 'trace-checkpoint-resume-retained118-save150'
CHECKPOINT_RETAINED150_SAVE182_MODE = 'trace-checkpoint-resume-retained150-save182'
PREVICTORY12_SAVE_CHECKPOINT = 'save-config-pre-victory12'
CHECKPOINT_RETAINED_SAVE_MODES = (CHECKPOINT_RETAINED_SAVE_MODE, CHECKPOINT_RETAINED121_SAVE_MODE, CHECKPOINT_RETAINED150_SAVE_MODE, CHECKPOINT_RETAINED150_SAVE182_MODE)
CHECKPOINT_LATE_CHAIN_MODES = (CHECKPOINT_LATE_ROUNDS_MODE, *CHECKPOINT_RETAINED_SAVE_MODES, CHECKPOINT_RETAINED_ROUNDS_MODE, CHECKPOINT_RETAINED_LONG_ROUNDS_MODE, CHECKPOINT_RETAINED150_LONG_ROUNDS_MODE)
CHECKPOINT_RESUME_MODES = (CHECKPOINT_RESUME_MODE, CHECKPOINT_LATE_RESUME_MODE, CHECKPOINT_RETAINED_RESUME_MODE, CHECKPOINT_RETAINED121_RESUME_MODE, CHECKPOINT_RETAINED150_RESUME_MODE, CHECKPOINT_RETAINED182_RESUME_MODE, CHECKPOINT_PREVICTORY12_RESUME_MODE, *CHECKPOINT_LATE_CHAIN_MODES)
CHECKPOINT_HOST41_SHA256 = '2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334'
CHECKPOINT_LOAD_MODES = (CHECKPOINT_LOAD_MODE, CHECKPOINT_FACADES_MODE, CHECKPOINT_POST160_MODE, CHECKPOINT_RETAINED121_POST160_MODE, CHECKPOINT_RETAINED150_POST160_MODE, CHECKPOINT_RETAINED150_OWNED_MODE, *CHECKPOINT_RESUME_MODES)
CHECKPOINT_RESTORE_MODES = (CONFIGURATION_ONLY_MODE, *CHECKPOINT_LOAD_MODES)
COMPACT_QUEUE_MODES = (SCRIPT_MAP_MODE, CHECKPOINT_RETAINED121_POST160_MODE, CHECKPOINT_RETAINED150_POST160_MODE, CHECKPOINT_RETAINED150_OWNED_MODE, *CHECKPOINT_RESUME_MODES)
SCRIPT_KERNEL_MODES = ('script-kernel', 'trace-script-kernel')
SCRIPT_THREAD_MODES = ('script-threads', 'trace-script-threads')
SCRIPT_PRIMITIVE_MODES = ('script-primitives', 'trace-script-primitives')
SCRIPT_NAMESPACE_MODES = ('script-namespaces', 'trace-script-namespaces')
SCRIPT_PARAMETER_MODES = ('script-globalparameters', 'trace-script-globalparameters')
GAMEPLAY_MEMORY_MODES = ('gameplay-memory', 'trace-gameplay-memory', 'trace-base-source-import', 'trace-base-configuration-import')
GAMEINFO_MODES = ('script-gameinfo', 'trace-script-gameinfo')
SCRIPT_DB_MODES = ('script-db', 'trace-script-db')
SCRIPT_EXECUTION_MODES = ('script-execution', 'trace-script-execution')
SCRIPT_LOCALE_MODES = ('script-locale', 'trace-script-locale')
HAVOK_VM_MODES = ('havok-vm', 'trace-havok-vm', *SCRIPT_KERNEL_MODES, *SCRIPT_THREAD_MODES, *SCRIPT_PRIMITIVE_MODES, *SCRIPT_NAMESPACE_MODES, *SCRIPT_PARAMETER_MODES, *GAMEPLAY_MEMORY_MODES, *GAMEINFO_MODES, *SCRIPT_DB_MODES, *SCRIPT_EXECUTION_MODES, *SCRIPT_LOCALE_MODES)
EMPTY_PERFORMANCE_MODES = ('trace-newgame-empty-performance-no-tuner', LOCAL_PLAYER_MODE)
MODES = ('baseline', 'load', 'trace-load', 'context', 'trace-context', 'init', 'trace-init', 'init-localization', 'trace-init-localization', 'prepare', 'trace-prepare', 'prepare-no-tuner', 'trace-prepare-no-tuner', 'trace-inspect-setup-no-tuner', 'trace-configure-map-no-tuner', 'trace-newgame-boundary-no-tuner', *EMPTY_PERFORMANCE_MODES, SCRIPT_CORE_MODE, SCRIPT_MAP_MODE, BASE_PROVIDER_MODE, *CHECKPOINT_RESTORE_MODES, *HAVOK_VM_MODES, *DEPENDENCIES)
INIT_MODES = ('init', 'trace-init', 'init-localization', 'trace-init-localization', 'prepare', 'trace-prepare', 'prepare-no-tuner', 'trace-prepare-no-tuner', 'trace-inspect-setup-no-tuner', 'trace-configure-map-no-tuner', 'trace-newgame-boundary-no-tuner', *EMPTY_PERFORMANCE_MODES, SCRIPT_CORE_MODE, SCRIPT_MAP_MODE, BASE_PROVIDER_MODE)
TUNER_FAULT_MODES = ('prepare-no-tuner', 'trace-prepare-no-tuner', 'trace-inspect-setup-no-tuner', 'trace-configure-map-no-tuner', 'trace-newgame-boundary-no-tuner', *EMPTY_PERFORMANCE_MODES, SCRIPT_CORE_MODE, SCRIPT_MAP_MODE)
MIB = 1024 ** 2

def digest(path: Path) -> str:
    result = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()

def prepare_init_fixture_copies(manifest_path: Path, instances: int, *, isolation_root: Path | None=None):
    """Create a persistent, byte-verified database fixture for each Init worker.

    Runtime output is confined to this project's ``work`` tree and is never
    removed by the probe. Repeats reuse each worker's own copy sequentially;
    concurrently running workers never share a SQLite file.
    """
    total_started = time.perf_counter()
    timings = {}
    if not 1 <= instances <= 16:
        raise ValueError('Init fixture worker count must be between 1 and 16')
    from civ6_host.runtime.native.native_host import validate_fixture
    phase_started = time.perf_counter()
    allowed_work = _resolve_resource_path(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_probe.py')))).resolve().parent.parent / 'work').resolve()
    root = _resolve_resource_path(isolation_root or allowed_work).resolve()
    if not root.is_relative_to(allowed_work):
        raise ValueError('Init isolation directory must remain under project work')
    root.mkdir(parents=True, exist_ok=True)
    original_path = _resolve_resource_path(_resolve_resource_path(Path(manifest_path))).resolve()
    original_sha = digest(original_path)
    normalized = validate_fixture(original_path)
    raw = json.loads(_resolve_resource_path(original_path).read_text(encoding='utf-8-sig'))
    if digest(original_path) != original_sha:
        raise ValueError('Fixture manifest changed during validation')
    timings['manifest_validation_seconds'] = time.perf_counter() - phase_started
    source_databases = normalized['databases']
    if not {'configuration', 'gameplay'}.issubset(source_databases):
        raise ValueError('Diagnostic fixture must include configuration and gameplay databases')
    phase_started = time.perf_counter()
    source_records = {}
    total_copy_bytes = 0
    for name, entry in source_databases.items():
        source_file = _resolve_resource_path(_resolve_resource_path(Path(entry['path']))).resolve()
        if not source_file.is_relative_to(allowed_work):
            raise ValueError(f'{name} fixture must remain under project work')
        if digest(source_file) != entry['sha256']:
            raise ValueError(f'Changed {name} database during fixture preparation')
        with _resolve_resource_path(source_file).open('rb') as stream:
            if stream.read(16) != b'SQLite format 3\x00':
                raise ValueError(f'Invalid {name} SQLite header in source fixture')
        source_records[name] = source_file
        total_copy_bytes += _resolve_resource_path(source_file).stat().st_size
    free_bytes = shutil.disk_usage(root).free
    required_copy_bytes = total_copy_bytes * instances
    if free_bytes < required_copy_bytes + 64 * MIB:
        raise OSError('Insufficient free disk space for isolated Init fixtures')
    timings['source_database_verification_and_capacity_seconds'] = time.perf_counter() - phase_started
    run_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex
    run_root = root / f'native-init-fixtures-{run_id}'
    run_root.mkdir(exist_ok=False)
    workers = []
    copy_seconds_by_database = {}
    copy_started = time.perf_counter()
    for worker_index in range(instances):
        worker_root = run_root / f'worker-{worker_index:02d}'
        worker_root.mkdir()
        cloned_databases = {}
        for name, source_entry in source_databases.items():
            database_started = time.perf_counter()
            source_file = source_records[name]
            expected_sha = source_entry['sha256']
            if digest(source_file) != expected_sha:
                raise ValueError(f'Changed {name} database during fixture preparation')
            clone_path = worker_root / f'{name}.sqlite'
            shutil.copyfile(source_file, clone_path)
            clone_sha = digest(clone_path)
            if clone_sha != expected_sha:
                raise ValueError(f'Copy verification failed for {name} database')
            with _resolve_resource_path(clone_path).open('rb') as stream:
                if stream.read(16) != b'SQLite format 3\x00':
                    raise ValueError(f'Invalid {name} SQLite header in copied fixture')
            cloned_databases[name] = {**source_entry, 'path': str(_resolve_resource_path(clone_path).resolve()), 'source_path': str(source_file), 'sha256': clone_sha, 'source_manifest_entry': _source_manifest_entry(raw, name)}
            copy_seconds_by_database[name] = copy_seconds_by_database.get(name, 0.0) + (time.perf_counter() - database_started)
        timings['database_copy_hash_and_header_seconds'] = time.perf_counter() - copy_started
        phase_started = time.perf_counter()
        isolated_manifest = {**raw, 'databases': cloned_databases, 'isolation': {'source_manifest_path': str(original_path), 'source_manifest_sha256': original_sha, 'worker_index': worker_index, 'worker_count': instances, 'copies_created_before_worker_launch': True}}
        manifest_copy = worker_root / 'manifest.json'
        manifest_copy.write_text(json.dumps(isolated_manifest, indent=2) + '\n', encoding='utf-8')
        worker_manifest_sha = digest(manifest_copy)
        validate_fixture(manifest_copy)
        workers.append({'worker_index': worker_index, 'manifest_path': str(_resolve_resource_path(manifest_copy).resolve()), 'manifest_sha256': worker_manifest_sha, 'databases': {name: {'source_path': entry['source_path'], 'copy_path': entry['path'], 'sha256': entry['sha256']} for name, entry in cloned_databases.items()}})
        timings['manifest_write_and_revalidation_seconds'] = timings.get('manifest_write_and_revalidation_seconds', 0.0) + (time.perf_counter() - phase_started)
    clone_paths = [entry['copy_path'] for worker in workers for entry in worker['databases'].values()]
    if len(clone_paths) != len(set(clone_paths)):
        raise RuntimeError('Init workers unexpectedly share a database fixture copy')
    timings['database_copy_seconds_by_name'] = copy_seconds_by_database
    timings['total_seconds'] = time.perf_counter() - total_started
    return {'root': str(_resolve_resource_path(run_root).resolve()), 'source_manifest_path': str(original_path), 'source_manifest_sha256': original_sha, 'worker_count': instances, 'workers': workers, 'timings_seconds': timings}

def _source_manifest_entry(raw_manifest, normalized_name):
    """Return the original nested entry so source and copy provenance survive."""
    database_map = raw_manifest.get('databases', {})
    nested_key = {'configuration': 'DebugConfiguration', 'gameplay': 'DebugGameplay', 'localization': 'DebugLocalization'}.get(normalized_name)
    if nested_key and nested_key in database_map:
        return database_map[nested_key]
    return database_map.get(normalized_name)

class MemoryCounters(C.Structure):
    _fields_ = [('cb', W.DWORD), ('PageFaultCount', W.DWORD)] + [(name, C.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]

class MemoryStatus(C.Structure):
    _fields_ = [('dwLength', W.DWORD), ('dwMemoryLoad', W.DWORD)] + [(name, C.c_ulonglong) for name in ('ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile', 'ullAvailPageFile', 'ullTotalVirtual', 'ullAvailVirtual', 'ullAvailExtendedVirtual')]

class BasicLimit(C.Structure):
    _fields_ = [('PerProcessUserTimeLimit', C.c_longlong), ('PerJobUserTimeLimit', C.c_longlong), ('LimitFlags', W.DWORD), ('MinimumWorkingSetSize', C.c_size_t), ('MaximumWorkingSetSize', C.c_size_t), ('ActiveProcessLimit', W.DWORD), ('Affinity', C.c_size_t), ('PriorityClass', W.DWORD), ('SchedulingClass', W.DWORD)]

class IoCounters(C.Structure):
    _fields_ = [(n, C.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

class ExtendedLimit(C.Structure):
    _fields_ = [('BasicLimitInformation', BasicLimit), ('IoInfo', IoCounters), ('ProcessMemoryLimit', C.c_size_t), ('JobMemoryLimit', C.c_size_t), ('PeakProcessMemoryUsed', C.c_size_t), ('PeakJobMemoryUsed', C.c_size_t)]

class ExceptionRecord(C.Structure):
    _fields_ = [('code', W.DWORD), ('flags', W.DWORD), ('record', C.c_void_p), ('address', C.c_void_p), ('count', W.DWORD), ('information', C.c_size_t * 15)]

class ExceptionPointers(C.Structure):
    _fields_ = [('record', C.POINTER(ExceptionRecord)), ('context', C.c_void_p)]

class Windows:

    def __init__(self):
        if os.name != 'nt' or struct.calcsize('P') != 8:
            raise RuntimeError('The pinned GameCore probe requires 64-bit Windows Python')
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.psapi = C.WinDLL('psapi', use_last_error=True)
        signatures = {'GetCurrentProcess': ([], W.HANDLE), 'CloseHandle': ([W.HANDLE], W.BOOL), 'SetErrorMode': ([W.UINT], W.UINT), 'GlobalMemoryStatusEx': ([C.POINTER(MemoryStatus)], W.BOOL), 'CreateJobObjectW': ([C.c_void_p, W.LPCWSTR], W.HANDLE), 'SetInformationJobObject': ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL), 'AssignProcessToJobObject': ([W.HANDLE, W.HANDLE], W.BOOL), 'TerminateJobObject': ([W.HANDLE, W.UINT], W.BOOL)}
        for name, (args, result) in signatures.items():
            fn = getattr(self.kernel, name)
            fn.argtypes, fn.restype = (args, result)
        self.psapi.GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(MemoryCounters), W.DWORD]
        self.psapi.GetProcessMemoryInfo.restype = W.BOOL
        self.psapi.EnumProcessModulesEx.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), W.DWORD]
        self.psapi.EnumProcessModulesEx.restype = W.BOOL
        self.psapi.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]
        self.psapi.GetModuleFileNameExW.restype = W.DWORD

    def memory(self, process=None):
        mem = MemoryCounters()
        mem.cb = C.sizeof(mem)
        handle = self.kernel.GetCurrentProcess() if process is None else process
        if not self.psapi.GetProcessMemoryInfo(handle, C.byref(mem), C.sizeof(mem)):
            raise C.WinError(C.get_last_error())
        return {'private_bytes': mem.PrivateUsage, 'working_set_bytes': mem.WorkingSetSize, 'peak_working_set_bytes': mem.PeakWorkingSetSize, 'peak_commit_bytes': mem.PeakPagefileUsage}

    def available(self):
        status = MemoryStatus()
        status.dwLength = C.sizeof(status)
        if not self.kernel.GlobalMemoryStatusEx(C.byref(status)):
            raise C.WinError(C.get_last_error())
        return {'physical_total_bytes': status.ullTotalPhys, 'physical_available_bytes': status.ullAvailPhys, 'commit_available_bytes': status.ullAvailPageFile}

    def modules(self):
        modules = (W.HMODULE * 2048)()
        needed = W.DWORD()
        handle = self.kernel.GetCurrentProcess()
        if not self.psapi.EnumProcessModulesEx(handle, modules, C.sizeof(modules), C.byref(needed), 3):
            raise C.WinError(C.get_last_error())
        if needed.value > C.sizeof(modules):
            raise RuntimeError('Module inventory truncated')
        result = []
        for module in modules[:needed.value // C.sizeof(W.HMODULE)]:
            name = C.create_unicode_buffer(32768)
            if not self.psapi.GetModuleFileNameExW(handle, module, name, len(name)):
                raise C.WinError(C.get_last_error())
            result.append(name.value)
        return result

    def job(self, process, memory_limit):
        handle = self.kernel.CreateJobObjectW(None, None)
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            limits = ExtendedLimit()
            limits.BasicLimitInformation.LimitFlags = 8192 | 256
            limits.ProcessMemoryLimit = memory_limit
            if not self.kernel.SetInformationJobObject(handle, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            if not self.kernel.AssignProcessToJobObject(handle, int(process._handle)):
                raise C.WinError(C.get_last_error())
            return handle
        except BaseException:
            self.kernel.CloseHandle(handle)
            raise

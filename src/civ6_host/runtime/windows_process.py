"""Bounded Windows process and Job Object controls.

Importing this module is portable. Windows DLLs are loaded only when a
``WindowsProcessRuntime`` instance is explicitly created on 64-bit Windows.
The caller owns process creation; this class only assigns, monitors,
terminates, and closes a bounded Job Object.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
import struct


class MemoryCounters(C.Structure):
    _fields_ = [("cb", W.DWORD), ("PageFaultCount", W.DWORD)] + [
        (name, C.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


class MemoryStatus(C.Structure):
    _fields_ = [("dwLength", W.DWORD), ("dwMemoryLoad", W.DWORD)] + [
        (name, C.c_ulonglong) for name in (
            "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
            "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]


class BasicLimit(C.Structure):
    _fields_ = [("PerProcessUserTimeLimit", C.c_longlong), ("PerJobUserTimeLimit", C.c_longlong),
                ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", C.c_size_t),
                ("MaximumWorkingSetSize", C.c_size_t), ("ActiveProcessLimit", W.DWORD),
                ("Affinity", C.c_size_t), ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]


class IoCounters(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimit(C.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", C.c_size_t), ("JobMemoryLimit", C.c_size_t),
                ("PeakProcessMemoryUsed", C.c_size_t), ("PeakJobMemoryUsed", C.c_size_t)]


class WindowsProcessRuntime:
    """Windows x64 process accounting and bounded Job Object operations."""

    def __init__(self):
        if os.name != "nt" or struct.calcsize("P") != 8:
            raise RuntimeError("Windows process controls require 64-bit Windows")
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.psapi = C.WinDLL("psapi", use_last_error=True)
        signatures = {
            "GetCurrentProcess": ([], W.HANDLE),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "GlobalMemoryStatusEx": ([C.POINTER(MemoryStatus)], W.BOOL),
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.kernel, name)
            fn.argtypes, fn.restype = args, result
        self.psapi.GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(MemoryCounters), W.DWORD]
        self.psapi.GetProcessMemoryInfo.restype = W.BOOL

    def memory(self, process=None):
        """Return the Windows process-memory counters used by the supervisor."""
        mem = MemoryCounters()
        mem.cb = C.sizeof(mem)
        handle = self.kernel.GetCurrentProcess() if process is None else process
        if not self.psapi.GetProcessMemoryInfo(handle, C.byref(mem), C.sizeof(mem)):
            raise C.WinError(C.get_last_error())
        return {"private_bytes": mem.PrivateUsage, "working_set_bytes": mem.WorkingSetSize,
                "peak_working_set_bytes": mem.PeakWorkingSetSize,
                "peak_commit_bytes": mem.PeakPagefileUsage}

    def available(self):
        """Return physical and commit availability from GlobalMemoryStatusEx."""
        status = MemoryStatus()
        status.dwLength = C.sizeof(status)
        if not self.kernel.GlobalMemoryStatusEx(C.byref(status)):
            raise C.WinError(C.get_last_error())
        return {"physical_total_bytes": status.ullTotalPhys,
                "physical_available_bytes": status.ullAvailPhys,
                "commit_available_bytes": status.ullAvailPageFile}

    def job(self, process, memory_limit):
        """Assign a process to a kill-on-close Job with a per-process commit cap."""
        handle = self.kernel.CreateJobObjectW(None, None)
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            limits = ExtendedLimit()
            # Preserve the lab supervisor's JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            # and JOB_OBJECT_LIMIT_PROCESS_MEMORY behavior.
            limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x100
            limits.ProcessMemoryLimit = memory_limit
            if not self.kernel.SetInformationJobObject(handle, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            if not self.kernel.AssignProcessToJobObject(handle, int(process._handle)):
                raise C.WinError(C.get_last_error())
            return handle
        except BaseException:
            # Match the source supervisor: cleanup failure must not mask the
            # exception that caused Job Object setup to abort.
            self.kernel.CloseHandle(handle)
            raise

    def terminate_job(self, job, exit_code):
        """Terminate every process in a previously created Job Object."""
        return bool(self.kernel.TerminateJobObject(job, exit_code))

    def close_job(self, job):
        """Close a Job Object handle; kill-on-close semantics are preserved."""
        return bool(self.kernel.CloseHandle(job))


__all__ = ["WindowsProcessRuntime"]

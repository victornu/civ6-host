"""Static and import-time checks for extracted Windows process support."""
from __future__ import annotations

import ast
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class WindowsProcessExtractionTests(unittest.TestCase):
    def test_package_import_does_not_load_windows_dlls(self):
        sys.modules.pop("civ6_host.runtime.windows_process", None)
        sys.modules.pop("civ6_host.runtime", None)
        with mock.patch("ctypes.WinDLL", side_effect=AssertionError("DLL load at import"), create=True):
            runtime = importlib.import_module("civ6_host.runtime")
            self.assertTrue(callable(runtime.WindowsProcessRuntime))

    def test_non_windows_construction_fails_before_dll_loading(self):
        from civ6_host.runtime import WindowsProcessRuntime
        with mock.patch("civ6_host.runtime.windows_process.os.name", "posix"), \
             mock.patch("ctypes.WinDLL", side_effect=AssertionError("DLL load before platform check"), create=True):
            with self.assertRaisesRegex(RuntimeError, "64-bit Windows"):
                WindowsProcessRuntime()

    def test_module_has_no_learner_or_gamecore_dependencies(self):
        path = ROOT / "src" / "civ6_host" / "runtime" / "windows_process.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"torch", "civ6rl", "numpy"}.intersection(imports))
        runtime = next(node for node in tree.body
                       if isinstance(node, ast.ClassDef) and node.name == "WindowsProcessRuntime")
        initializer = next(node for node in runtime.body
                           if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        win_dll_calls = [node for node in ast.walk(initializer)
                         if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                         and node.func.attr == "WinDLL"]
        self.assertEqual(2, len(win_dll_calls))
        for method in (node for node in runtime.body
                       if isinstance(node, ast.FunctionDef) and node.name != "__init__"):
            self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                 and node.func.attr == "WinDLL" for node in ast.walk(method)))

    def test_job_limits_remain_kill_on_close_and_per_process_memory(self):
        import ctypes as C
        from types import SimpleNamespace
        from civ6_host.runtime import windows_process as module

        class FakeKernel:
            def __init__(self):
                self.closed = []
                self.terminated = []
                self.limit = None

            def CreateJobObjectW(self, *_args): return 71
            def SetInformationJobObject(self, _job, info_class, pointer, size):
                value = C.cast(pointer, C.POINTER(module.ExtendedLimit)).contents
                self.limit = (info_class, size, value.BasicLimitInformation.LimitFlags,
                              value.ProcessMemoryLimit)
                return True
            def AssignProcessToJobObject(self, _job, process): return process == 84
            def TerminateJobObject(self, job, code):
                self.terminated.append((job, code)); return True
            def CloseHandle(self, job): self.closed.append(job); return True

        runtime = object.__new__(module.WindowsProcessRuntime)
        runtime.kernel = FakeKernel()
        process = SimpleNamespace(_handle=84)
        self.assertEqual(71, runtime.job(process, 512 * 1024 * 1024))
        info_class, size, flags, memory_limit = runtime.kernel.limit
        self.assertEqual(9, info_class)
        self.assertEqual(C.sizeof(module.ExtendedLimit), size)
        self.assertEqual(0x2000 | 0x100, flags)
        self.assertEqual(512 * 1024 * 1024, memory_limit)
        self.assertTrue(runtime.terminate_job(71, 124))
        self.assertEqual([(71, 124)], runtime.kernel.terminated)
        self.assertTrue(runtime.close_job(71))
        self.assertEqual([71], runtime.kernel.closed)

    def test_job_setup_failure_closes_handle_and_preserves_setup_error(self):
        import ctypes as C
        from types import SimpleNamespace
        from civ6_host.runtime import windows_process as module

        class FakeKernel:
            closed = []
            def CreateJobObjectW(self, *_args): return 72
            def SetInformationJobObject(self, *_args): return False
            def AssignProcessToJobObject(self, *_args): raise AssertionError("assignment after failure")
            def CloseHandle(self, job): self.closed.append(job); return True

        runtime = object.__new__(module.WindowsProcessRuntime)
        runtime.kernel = FakeKernel()
        with mock.patch.object(C, "get_last_error", return_value=5), \
             mock.patch.object(C, "WinError", side_effect=OSError("setup failed"), create=True):
            with self.assertRaisesRegex(OSError, "setup failed"):
                runtime.job(SimpleNamespace(_handle=84), 1024)
        self.assertEqual([72], runtime.kernel.closed)


if __name__ == "__main__":
    unittest.main()

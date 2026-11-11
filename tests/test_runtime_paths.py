"""Configuration tests for private host resource paths; no game imports."""
from __future__ import annotations

import ast
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from civ6_host.runtime import paths


class RuntimePathsTests(unittest.TestCase):
    def load_with_environment(self, values):
        environment = mock.patch.dict(os.environ, values, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        return importlib.reload(paths)

    def test_missing_or_blank_resource_root_is_rejected(self):
        module = self.load_with_environment({})
        with self.assertRaisesRegex(RuntimeError, "CIV6_HOST_RESOURCE_ROOT is required"):
            module.resource_root()
        module = self.load_with_environment({"CIV6_HOST_RESOURCE_ROOT": "  "})
        with self.assertRaisesRegex(RuntimeError, "is required"):
            module.resource_root()

    def test_environment_must_be_set_before_import(self):
        module = self.load_with_environment({})
        with mock.patch.dict(os.environ, {"CIV6_HOST_RESOURCE_ROOT": str(ROOT)}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "before importing"):
                module.resource_root()

    def test_relative_missing_and_non_directory_paths_are_rejected(self):
        module = self.load_with_environment({"CIV6_HOST_RESOURCE_ROOT": "relative/resources"})
        with self.assertRaisesRegex(ValueError, "absolute path"):
            module.resource_root()
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            module = self.load_with_environment({"CIV6_HOST_RESOURCE_ROOT": str(missing)})
            with self.assertRaisesRegex(ValueError, "existing directory"):
                module.resource_root()
            file_path = Path(temporary) / "file"
            file_path.write_text("not a directory", encoding="utf-8")
            module = self.load_with_environment({"CIV6_HOST_RESOURCE_ROOT": str(file_path)})
            with self.assertRaisesRegex(ValueError, "existing directory"):
                module.resource_root()

    def test_root_is_absolute_canonical_and_stable_for_the_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            configured = Path(temporary)
            nested = configured / "nested"
            nested.mkdir()
            alias = nested / ".."
            module = self.load_with_environment({"CIV6_HOST_RESOURCE_ROOT": str(alias)})
            resolved = module.resource_root()
            self.assertEqual(configured.resolve(), resolved)
            self.assertTrue(resolved.is_absolute())
            self.assertEqual(resolved, module.resource_root())
            other = Path(temporary) / "other"
            other.mkdir()
            with mock.patch.dict(os.environ, {"CIV6_HOST_RESOURCE_ROOT": str(other)}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "before importing"):
                    module.resource_root()
            self.assertEqual(resolved, module.resource_root())

    @unittest.skipUnless(os.name == 'nt', 'the native backend is Windows-only')
    def test_backend_preserves_an_already_imported_path_spelling(self):
        from civ6_host.runtime.backend import _prepare_runtime

        configured = ROOT.as_posix()
        module = self.load_with_environment({'CIV6_HOST_RESOURCE_ROOT': configured})
        self.assertEqual(module.resource_root(), ROOT)
        with (mock.patch('civ6_host.runtime.resource_resolution.configure'),
              mock.patch('civ6_host.runtime.capture_admission.configure'),
              mock.patch('civ6_host.runtime.import_boundary.enable'),
              mock.patch('civ6_host.runtime.provenance.verify_installation', return_value='verified')):
            self.assertEqual(_prepare_runtime(ROOT, None, None), 'verified')
            self.assertEqual(os.environ['CIV6_HOST_RESOURCE_ROOT'], configured)
            with self.assertRaisesRegex(ValueError, 'different private resource root'):
                _prepare_runtime(ROOT / 'src', None, None)

    def test_resource_root_does_not_depend_on_repository_or_current_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            unrelated = Path(temporary).resolve()
            module = self.load_with_environment({"CIV6_HOST_RESOURCE_ROOT": str(unrelated)})
            with mock.patch("pathlib.Path.cwd", side_effect=AssertionError("cwd fallback")):
                self.assertEqual(unrelated, module.resource_root())
        source = (ROOT / "src" / "civ6_host" / "runtime" / "paths.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"civ6rl", "torch", "numpy"}.intersection(imports))
        self.assertNotIn("cwd(", source)
        self.assertNotIn("getcwd(", source)


if __name__ == "__main__":
    unittest.main()

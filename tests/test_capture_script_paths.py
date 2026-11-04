"""Targeted offline/capture-time tests for the pending script-path adapter.

Fixtures never observe a process or execute gameplay.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Mapping
from civ6_host.runtime.paths import resource_root

from civ6_host.runtime.capture_script_paths import (
    ProcessIdentity,
    ScriptPathError,
    load_context,
    resolve_path,
    validate_context,
)


class CaptureScriptPathsTests(unittest.TestCase):
    selected_name = "../../../DLC/Expansion2/Scripts/WorldCongress.lua"
    phase42_path = resource_root() / "evidence" / "phase42-map-setup.json"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root / "Game"
        self.cwd = self.game / "Base" / "Binaries" / "Win64Steam"
        self.cwd.mkdir(parents=True)
        self.source = self.game / "DLC" / "Expansion2" / "Scripts" / "WorldCongress.lua"
        self.source.parent.mkdir(parents=True)
        self.source_bytes = b"GameEvents.CanUseResolutions.Add(function() return true end)\n"
        self.source.write_bytes(self.source_bytes)
        self.identity = ProcessIdentity(17592, 134380170124816753, str(self.game / "CivilizationVI.exe"))
        self.process = {
            "pid": self.identity.pid,
            "creation_filetime": self.identity.creation_filetime,
            "image_path": self.identity.image_path,
        }
        self.proofs = {
            "selection_witness": self._proof("runtime-selections-before.json", b"{}\n"),
            "resolver_source": {
                "path": str(self.phase42_path), "bytes": 211343,
                "sha256": "47fd60ba8222c43436a07ec1e0919673d797cf1e095a48202a0f9a2512a3535c",
            },
            "observer": self._proof("observe-script-path-base.py", b"injected observer\n"),
        }
        self.witness_path = self.root / "script-path-base-witness.json"
        self.witness = self._witness(self.selected_name, self.source)
        self._write_witness()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _proof(self, name: str, data: bytes) -> dict[str, object]:
        path = self.root / name
        path.write_bytes(data)
        return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def _witness(self, selected: str, source: Path) -> dict[str, object]:
        selection_data = json.dumps({
            "gameplay_selection994": {
                "process": dict(self.process),
                "exe_module": {"path": self.identity.image_path, "base": 0x140000000, "bytes": 57688064},
                "gamecore_module": {"sha256": "324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c"},
                "snapshot": {"executable_sha256": "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63", "selected_paths": [selected]},
            }
        }).encode("utf-8")
        self.proofs["selection_witness"] = self._proof("runtime-selections-before.json", selection_data)
        data = source.read_bytes()
        return {
            "schema": "civ6-host.official-script-path-base.v1",
            "status": "same_process_cwd_and_native_path_copy_service_observed",
            "process": dict(self.process),
            "cwd": str(self.cwd),
            "selected": [selected],
            "resolved_sources": [{
                "path": str(source), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            }],
            **self.proofs,
            "resolver_live": {"singleton": 5830359248, "vtable": 5386810600, "method": 5384554528},
            "psutil_version": "7.1.0",
            "native_function_called": False,
            "game_memory_written": False,
            "process_environment_read": False,
            "filesystem_search_used": False,
            "historical_execution_bytes_proven": False,
        }

    def _write_witness(self) -> None:
        self.witness_path.write_text(json.dumps(self.witness), encoding="utf-8")

    def _reader(self, *, cwd: str | None = None, process: dict[str, object] | None = None):
        observation = {"process": process or dict(self.process), "cwd": cwd or str(self.cwd)}

        def read(expected: Mapping[str, object]):
            self.assertEqual(dict(expected), self.process)
            return observation

        return read

    def test_offline_validation_preserves_original_name_and_mapping(self) -> None:
        context = validate_context(self._witness_pin(), self.identity)
        self.assertEqual(context.selected_order, (self.selected_name,))
        self.assertEqual(context.source_by_selected[self.selected_name].resolved_path, str(self.source))

        result = resolve_path(self.selected_name, context, [self.game], cwd_reader=self._reader())
        self.assertEqual(result.selected_name, self.selected_name)
        self.assertEqual(result.resolved_path, self.source.resolve())
        self.assertEqual(result.sha256, hashlib.sha256(self.source_bytes).hexdigest())

    @unittest.skipUnless(os.name == "nt", "Windows drive-qualified path boundary")
    def test_root_relative_cwd_is_not_an_absolute_process_directory(self) -> None:
        self.witness["cwd"] = "\\unqualified-working-directory"
        self._write_witness()
        with self.assertRaisesRegex(ScriptPathError, "qualified local path"):
            validate_context(self._witness_pin(), self.process)

    def test_load_rechecks_exact_process_and_cwd(self) -> None:
        with self.assertRaises(ScriptPathError):
            load_context(
                self._witness_pin(),
                self.identity,
                cwd_reader=self._reader(cwd=str(self.game)),
            )
        wrong = dict(self.process)
        wrong["creation_filetime"] = int(self.identity.creation_filetime) + 1
        with self.assertRaises(ScriptPathError):
            load_context(
                self._witness_pin(),
                self.identity,
                cwd_reader=self._reader(process=wrong),
            )

    def test_unknown_or_drive_relative_names_do_not_fall_back(self) -> None:
        context = validate_context(self._witness_pin(), self.identity)
        with self.assertRaises(ScriptPathError):
            resolve_path("../../../DLC/Other.lua", context, [self.game], cwd_reader=self._reader())
        for invalid in ("C:relative.lua", "C:\\absolute.lua", "\\\\server\\share\\file.lua"):
            with self.subTest(invalid=invalid), self.assertRaises(ScriptPathError):
                resolve_path(invalid, context, [self.game], cwd_reader=self._reader())

    def test_mapping_outside_approved_root_is_rejected(self) -> None:
        outside = self.root / "outside.lua"
        outside.write_bytes(b"outside")
        escaping_name = "../../../../outside.lua"
        self.witness = self._witness(escaping_name, outside)
        self._write_witness()
        context = validate_context(self._witness_pin(), self.identity)
        with self.assertRaises(ScriptPathError):
            resolve_path(escaping_name, context, [self.game], cwd_reader=self._reader())

    @unittest.skipUnless(os.name == "nt", "Windows Workshop path")
    def test_absolute_workshop_selection_requires_its_approved_root(self) -> None:
        workshop = self.root / "workshop" / "2865001760"
        workshop.mkdir(parents=True)
        source = workshop / "bbg_script.lua"
        source.write_bytes(b"return true\n")
        name = source.as_posix()
        self.witness = self._witness(name, source)
        self._write_witness()
        context = validate_context(self._witness_pin(), self.identity)
        self.assertEqual(context.selected_order, (name,))
        self.assertEqual(
            resolve_path(name, context, [self.game, workshop], cwd_reader=self._reader()).resolved_path,
            source.resolve(),
        )
        with self.assertRaisesRegex(ScriptPathError, "escapes all approved roots"):
            resolve_path(name, context, [self.game], cwd_reader=self._reader())

    def test_changed_source_bytes_fail_offline_validation(self) -> None:
        self.source.write_bytes(b"changed after capture")
        with self.assertRaises(ScriptPathError):
            validate_context(self._witness_pin(), self.identity)

    def _witness_pin(self) -> dict[str, object]:
        raw = self.witness_path.read_bytes()
        return {"path": str(self.witness_path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


if __name__ == "__main__":
    unittest.main()

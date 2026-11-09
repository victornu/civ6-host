"""Targeted offline/capture-time tests for the pending script-path adapter.

Fixtures never observe a process or execute gameplay.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from typing import Mapping
from unittest.mock import patch
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import capture_script_paths as path_module

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

    @staticmethod
    def _read_pe_rva(image: Path, rva: int, size: int) -> bytes:
        raw = image.read_bytes()
        pe_offset = struct.unpack_from("<I", raw, 0x3C)[0]
        if raw[pe_offset:pe_offset + 4] != b"PE\0\0":
            raise AssertionError("invalid PE signature")
        section_count = struct.unpack_from("<H", raw, pe_offset + 6)[0]
        optional_size = struct.unpack_from("<H", raw, pe_offset + 20)[0]
        optional = pe_offset + 24
        image_base = struct.unpack_from("<Q", raw, optional + 24)[0]
        if image_base != 0x140000000:
            raise AssertionError("unexpected current EXE image base")
        sections = optional + optional_size
        for index in range(section_count):
            row = sections + index * 40
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", raw, row + 8)
            if virtual_address <= rva and rva + size <= virtual_address + max(virtual_size, raw_size):
                offset = raw_offset + rva - virtual_address
                return raw[offset:offset + size]
        raise AssertionError(f"RVA {rva:#x} is not backed by a PE section")

    def test_current_path_profile_matches_pinned_pe_bytes_and_rva_arithmetic(self) -> None:
        artifact_path = resource_root() / path_module.CURRENT_BINDINGS_PATH
        artifact_raw = artifact_path.read_bytes()
        self.assertEqual(len(artifact_raw), path_module.CURRENT_BINDINGS_BYTES)
        self.assertEqual(hashlib.sha256(artifact_raw).hexdigest(), path_module.CURRENT_BINDINGS_SHA256)
        artifact = json.loads(artifact_raw)
        image = Path(artifact["current_image"]["path"])
        image_raw = image.read_bytes()
        self.assertEqual(len(image_raw), 21189480)
        self.assertEqual(hashlib.sha256(image_raw).hexdigest(), path_module.CURRENT_EXE_SHA256)
        self.assertEqual(artifact["current_profile"]["runtime_gamecore_sha256"], path_module.CURRENT_CORE_SHA256)
        base = int(artifact["current_image"]["image_base"], 16)
        profile = artifact["current_profile"]
        global_rva = int(profile["singleton_global_rva"], 16)
        self.assertEqual(global_rva, 0x143587CC8 - base)
        self.assertEqual(global_rva, path_module.CURRENT_SINGLETON_GLOBAL_RVA)
        accessor = artifact["current_functions"]["accessor"]
        global_references = [target for instruction in accessor["instructions"]
                             for target in instruction.get("rip_target_rvas", [])]
        self.assertIn(hex(global_rva), global_references)
        self.assertEqual(
            self._read_pe_rva(image, int(profile["vtable_rva"], 16), 24).hex(),
            profile["vtable_raw_hex"],
        )
        for row in artifact["current_functions"].values():
            actual = self._read_pe_rva(image, int(row["start_rva"], 16), row["length"])
            self.assertEqual(actual.hex(), row["raw_hex"])
            self.assertEqual(hashlib.sha256(actual).hexdigest(), row["sha256"])
        caller_path = resource_root() / path_module.CURRENT_CALLER_BINDINGS_PATH
        caller_raw = caller_path.read_bytes()
        self.assertEqual(len(caller_raw), path_module.CURRENT_CALLER_BINDINGS_BYTES)
        self.assertEqual(hashlib.sha256(caller_raw).hexdigest(), path_module.CURRENT_CALLER_BINDINGS_SHA256)
        caller = json.loads(caller_raw)
        self.assertEqual(caller["parent_corrected_path_profile"]["sha256"], path_module.CURRENT_BINDINGS_SHA256)
        manager_table = caller["current_manager_vtable"]
        table_raw = self._read_pe_rva(image, int(manager_table["rva"], 16), 0x60)
        self.assertEqual(table_raw.hex(), manager_table["raw_hex"])
        slot = int(manager_table["slot_plus_0x30_rva"], 16)
        target = struct.unpack("<Q", self._read_pe_rva(image, slot, 8))[0]
        self.assertEqual(target - base, path_module.CURRENT_SCRIPT_MANAGER_WRAPPER_RVA)
        for row in caller["current_function_spans"].values():
            actual = self._read_pe_rva(image, int(row["start_rva"], 16), row["length"])
            self.assertEqual(actual.hex(), row["raw_hex"])
            self.assertEqual(hashlib.sha256(actual).hexdigest(), row["sha256"])

    def test_current_observer_composes_aslr_rvas_with_mocked_read_only_memory(self) -> None:
        pid = 17592
        creation = 134380170124816753
        exe_path = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\CivilizationVI.exe"
        core_path = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"
        cwd = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam"
        image_base = 0x7FF600000000
        singleton = 0x7FF700001000
        script_manager = 0x7FF700002000
        vtable = image_base + path_module.CURRENT_VTABLE_RVA
        method = image_base + path_module.CURRENT_METHOD_RVA
        manager_vtable = image_base + path_module.CURRENT_SCRIPT_MANAGER_VTABLE_RVA
        manager_slot_30 = image_base + path_module.CURRENT_SCRIPT_MANAGER_WRAPPER_RVA
        identity = {"pid": pid, "creation_filetime": creation, "image_path": exe_path,
                    "profile_id": path_module.CURRENT_PROFILE_ID,
                    "exe_sha256": path_module.CURRENT_EXE_SHA256,
                    "gamecore_sha256": path_module.CURRENT_CORE_SHA256,
                    "caller_bindings_sha256": path_module.CURRENT_CALLER_BINDINGS_SHA256}

        class FakeProcess:
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def identity(self): return {key: identity[key] for key in ("pid", "creation_filetime", "image_path")}
            def modules(self):
                return [
                    {"name": "CivilizationVI.exe", "path": exe_path, "base": image_base, "bytes": 0x3700000},
                    {"name": "GameCore_XP2_FinalRelease.dll", "path": core_path,
                     "base": 0x7FFA00000000, "bytes": 0xC50000},
                ]
            def read(self, address, size):
                pointers = {
                    image_base + path_module.CURRENT_SINGLETON_GLOBAL_RVA: singleton,
                    singleton: vtable,
                    vtable + 0x10: method,
                    image_base + path_module.CURRENT_SCRIPT_MANAGER_GLOBAL_RVA: script_manager,
                    script_manager: manager_vtable,
                    manager_vtable + path_module.CURRENT_SCRIPT_MANAGER_SLOT_OFFSET: manager_slot_30,
                }
                if size != 8 or address not in pointers:
                    raise AssertionError("unexpected memory read")
                return pointers[address].to_bytes(8, "little")

        class FakePsutil:
            __version__ = "7.1.0"
            @staticmethod
            def Process(_pid):
                return SimpleNamespace(cwd=lambda: cwd)

        fake_worker = SimpleNamespace(ReadOnlyProcess=lambda _pid: FakeProcess())
        def import_module(name):
            if name == "psutil": return FakePsutil
            if name == "civ6_host.runtime.workers.capture_official_content929": return fake_worker
            raise AssertionError(f"unexpected import {name}")
        def image_digest(path):
            if str(path) == exe_path:
                return path_module.CURRENT_EXE_SIZE_BYTES, path_module.CURRENT_EXE_SHA256
            if str(path) == core_path:
                return 12941080, path_module.CURRENT_CORE_SHA256
            raise AssertionError(f"unexpected image path {path}")

        with patch.object(path_module.importlib, "import_module", side_effect=import_module), \
             patch.object(path_module, "_image_digest", side_effect=image_digest):
            result = path_module.observe_process_cwd(identity)
        self.assertEqual(result["cwd"], cwd)
        self.assertEqual(result["profile_id"], path_module.CURRENT_PROFILE_ID)
        self.assertEqual(dict(result["resolver_live"]),
                         {"singleton": singleton, "vtable": vtable, "method": method,
                          "script_manager": script_manager,
                          "script_manager_vtable": manager_vtable,
                          "script_manager_slot_30": manager_slot_30})

    def test_current_v3_override_proof_and_observer_use_actual_live_slot(self) -> None:
        override_path = resource_root() / path_module.CURRENT_OVERRIDE_BINDINGS_PATH
        override_raw = override_path.read_bytes()
        self.assertEqual(len(override_raw), path_module.CURRENT_OVERRIDE_BINDINGS_BYTES)
        self.assertEqual(hashlib.sha256(override_raw).hexdigest(),
                         path_module.CURRENT_OVERRIDE_BINDINGS_SHA256)
        override = json.loads(override_raw)
        self.assertEqual(override["schema"], "civ6-host.current-exe-script-path-actual-override.v1")
        self.assertEqual(override["actual_manager_vtable"]["rva"],
                         hex(path_module.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA))
        self.assertEqual(override["actual_manager_vtable"]["slot_plus_0x30_target_rva"],
                         hex(path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA))
        image = Path(override["current_image"]["path"])
        table = self._read_pe_rva(image, path_module.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA, 0x80)
        self.assertEqual(table.hex(), override["actual_manager_vtable"]["raw_hex"])
        method_row = override["function_spans"][hex(path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)]
        method = self._read_pe_rva(image, int(method_row["start_rva"], 16), method_row["length"])
        self.assertEqual(hashlib.sha256(method).hexdigest(), method_row["sha256"])

        pid, creation = 17808, 134384525467770582
        exe_path = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\CivilizationVI.exe"
        core_path = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"
        cwd = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam"
        base = 0x7FF600000000
        path_singleton = 0x7FF700001000
        manager = 0x7FF700002000
        identity = {"pid": pid, "creation_filetime": creation, "image_path": exe_path,
                    "profile_id": path_module.CURRENT_V3_PROFILE_ID,
                    "exe_sha256": path_module.CURRENT_EXE_SHA256,
                    "gamecore_sha256": path_module.CURRENT_CORE_SHA256,
                    "override_bindings_sha256": path_module.CURRENT_OVERRIDE_BINDINGS_SHA256}

        class FakeProcess:
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def identity(self): return {key: identity[key] for key in ("pid", "creation_filetime", "image_path")}
            def modules(self):
                return [
                    {"name": "CivilizationVI.exe", "path": exe_path, "base": base, "bytes": 0x3700000},
                    {"name": "GameCore_XP2_FinalRelease.dll", "path": core_path,
                     "base": 0x7FFA00000000, "bytes": 0xC50000},
                ]
            def read(self, address, size):
                table = base + path_module.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA
                pointers = {
                    base + path_module.CURRENT_SINGLETON_GLOBAL_RVA: path_singleton,
                    path_singleton: base + path_module.CURRENT_VTABLE_RVA,
                    base + path_module.CURRENT_VTABLE_RVA + 0x10: base + path_module.CURRENT_METHOD_RVA,
                    base + path_module.CURRENT_SCRIPT_MANAGER_GLOBAL_RVA: manager,
                    manager: table,
                    table + path_module.CURRENT_SCRIPT_MANAGER_SLOT_OFFSET:
                        base + path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA,
                }
                if size != 8 or address not in pointers:
                    raise AssertionError("unexpected memory read")
                return pointers[address].to_bytes(8, "little")

        class FakePsutil:
            __version__ = "7.1.0"
            @staticmethod
            def Process(_pid): return SimpleNamespace(cwd=lambda: cwd)

        worker = SimpleNamespace(ReadOnlyProcess=lambda _pid: FakeProcess())
        def import_module(name):
            if name == "psutil": return FakePsutil
            if name == "civ6_host.runtime.workers.capture_official_content929": return worker
            raise AssertionError(f"unexpected import {name}")
        def image_digest(path):
            if str(path) == exe_path:
                return path_module.CURRENT_EXE_SIZE_BYTES, path_module.CURRENT_EXE_SHA256
            if str(path) == core_path:
                return 12941080, path_module.CURRENT_CORE_SHA256
            raise AssertionError(f"unexpected image path {path}")

        with patch.object(path_module.importlib, "import_module", side_effect=import_module), \
             patch.object(path_module, "_image_digest", side_effect=image_digest):
            result = path_module.observe_process_cwd(identity)
        self.assertEqual(result["profile_id"], path_module.CURRENT_V3_PROFILE_ID)
        self.assertEqual(result["resolver_live"]["script_manager_vtable"],
                         base + path_module.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA)
        self.assertEqual(result["resolver_live"]["script_manager_slot_30"],
                         base + path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)

    def test_v3_native_resolution_report_is_ordered_nonce_bound_and_cwd_resolved(self) -> None:
        identity = ProcessIdentity(17736, 134384525467770582,
                                   r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\CivilizationVI.exe")
        process = {"pid": identity.pid, "creation_filetime": identity.creation_filetime,
                   "image_path": identity.image_path}
        cwd = str(self.cwd)
        selected = [self.selected_name]
        output = r"DLC\Expansion2\Scripts\WorldCongress.lua"
        candidate_build_path = resource_root() / "work/official-capture/current-image-adapter/path-build-root/official-script-path-build.json"
        candidate_build_raw = candidate_build_path.read_bytes()
        candidate_build_doc = json.loads(candidate_build_raw)
        pins = {
            "build": {"path": str(candidate_build_path), "bytes": len(candidate_build_raw),
                      "sha256": hashlib.sha256(candidate_build_raw).hexdigest()},
            "helper_module": candidate_build_doc["dll"],
            "helper_source": candidate_build_doc["source"],
        }
        assets = dict(path_module.CURRENT_V3_ASSET_PINS)
        selection_doc = {"gameplay_selection994": {
            "schema": "civ6rl.official_gameplay_selection994.capture.v2",
            "process": process,
            "exe_module": {"path": identity.image_path, "base": 0x7FF600000000,
                           "bytes": 0x3700000},
            "gamecore_module": {"sha256": path_module.CURRENT_CORE_SHA256},
            "snapshot": {"schema": "civ6rl.gameplay_selection994.memory_snapshot.v2",
                         "executable_sha256": path_module.CURRENT_EXE_SHA256,
                         "current_correspondence_sha256": path_module.CURRENT_SELECTION_SOURCE_SHA256,
                         "selected_paths": selected},
        }}
        selection_raw = json.dumps(selection_doc).encode("utf-8")
        selection_file = self._proof("v3-selection.json", selection_raw)
        override = resource_root() / path_module.CURRENT_OVERRIDE_BINDINGS_PATH
        override_raw = override.read_bytes()
        override_pin = {"path": str(override), "bytes": len(override_raw),
                        "sha256": hashlib.sha256(override_raw).hexdigest()}
        manager = 0x6113ABD0
        response = {
            "schema": "civ6-host.official_script_path_resolution.v1", "status": "ok",
            "nonce": "a" * 32, "pid": identity.pid, "creation_filetime": identity.creation_filetime,
            "thread_id": 1234, "manager_address": hex(manager),
            "manager_vtable_rva": hex(path_module.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA),
            "method_rva": hex(path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA),
            "capacity_utf16_units": 260,
            "input_utf16le_hex": (selected[0] + "\0").encode("utf-16-le").hex(),
            "output_utf16le_hex": (output + "\0").encode("utf-16-le").hex(),
            "executable_sha256": path_module.CURRENT_EXE_SHA256,
            "lua_scope": "root",
            "lua_cs_owned": True, "native_method_called": True,
            "gamecore_function_called_by_helper": False,
            "output_file_opened_by_helper": False, "path_exists_checked": False,
            "exe_method_may_delegate_to_content_resolver": True,
            "nested_resolver_side_effects_asserted_absent": False,
        }
        report = {
            "schema": path_module.CURRENT_V3_REPORT_SCHEMA, "status": "ok",
            "process": process,
            "execution_profile": {
                "profile_id": "xp2-exe-current-d1a0-core-092abfbb-native-path",
                "executable_sha256": path_module.CURRENT_EXE_SHA256,
                "runtime_gamecore_sha256": path_module.CURRENT_CORE_SHA256,
                "selection_source_sha256": path_module.CURRENT_SELECTION_SOURCE_SHA256,
            },
            "capture_id": "b" * 32, "build": pins["build"],
            "helper_module": pins["helper_module"], "helper_source": pins["helper_source"],
            "override_proof": override_pin,
            "records": [{"selected_name": selected[0], "response": response}],
            "root_transport_proofs": [],
            "player_observation": False, "training_ready": False,
        }
        registration_nonce = "c" * 32
        prepare_receipt = {
            "schema": "civ6rl.localization_query_preparation.v1", "status": "ok",
            "nonce": registration_nonce, "database_function_called": False,
            "module_file_pins_retained": True,
        }
        prepare_line = "CIV6RL_SCRIPT_PATH_PREPARED:" + registration_nonce + ":" + json.dumps(
            prepare_receipt, separators=(",", ":"))
        result_line = "CIV6RL_SCRIPT_PATH_RESULT:" + response["nonce"] + ":" + json.dumps(
            response, separators=(",", ":"))
        module_path = pins["helper_module"]["path"]
        registration = {
            "schema": "civ6-host.official-script-path-root-registration.v1",
            "nonce": registration_nonce, "status": "completed", "process": process,
            "selection": selection_file, "build": pins["build"],
            "owner_before": {"pid": 99, "creation_filetime": 123},
            "owner_after": {"pid": 99, "creation_filetime": 123},
            "exe_module": {"path": identity.image_path, "name": "CivilizationVI.exe",
                           "base": 0x140000000, "bytes": 0x3700000},
            "gamecore_module": {"path": "C:\\GameCore_XP2_FinalRelease.dll",
                                "name": "GameCore_XP2_FinalRelease.dll", "base": 0x7FF600000000,
                                "bytes": 10, "sha256": path_module.CURRENT_CORE_SHA256},
            "command": "registration command", "environment_key": "helper-key",
            "prepare_lines": [prepare_line],
            "native_receipt": prepare_receipt,
            "helper_module": {"path": module_path, "name": "civ6rl-official-script-path.dll",
                              "base": 0x7FF610000000, "bytes": 0x30000,
                              "sha256": pins["helper_module"]["sha256"]},
            "root_state_index": 7, "records": report["records"],
            "attempted_nonces": [response["nonce"]],
            "native_calls": [{"index": 0, "selected_name": selected[0],
                              "nonce": response["nonce"], "status": "ok",
                              "raw_lines": [result_line], "response": response}],
            "records_completed": 1,
        }
        registration_path = self.root / "root-registration.json"
        registration_path.write_text(json.dumps(registration), encoding="utf-8")
        original_registration_raw = registration_path.read_bytes()
        transcript_path = self.root / "tuner.jsonl"
        events = [
            {"time": 0.5, "direction": "sent", "tag": 3,
             "payload": (f'CMD:7:prepare {path_module._lua_string_literal(registration_nonce)} '
                         f'civ6rl_localization_query_prepare {path_module._lua_string_literal(module_path)} '
                         f'{path_module._lua_string_literal(pins["helper_module"]["sha256"])} '
                         f'{path_module._lua_string_literal(str(identity.pid))} '
                         f'{path_module._lua_string_literal(str(identity.creation_filetime))}')},
            {"time": 1.0, "direction": "received", "tag": 3, "payload": "O\x00Main: " + prepare_line},
            {"time": 2.0, "direction": "sent", "tag": 3,
             "payload": (f'CMD:7:resolve {path_module._lua_string_literal(selected[0])} '
                         f'{path_module._lua_string_literal(response["nonce"])} '
                         f'{path_module._lua_string_literal(pins["helper_module"]["sha256"])} '
                         f'{path_module._lua_string_literal(str(identity.pid))} '
                         f'{path_module._lua_string_literal(str(identity.creation_filetime))}')},
            {"time": 3.0, "direction": "received", "tag": 3, "payload": "O\x00Main: " + result_line},
        ]
        transcript_path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
        report["root_transport_proofs"] = [
            selection_file,
            {"path": str(registration_path), "bytes": registration_path.stat().st_size,
             "sha256": hashlib.sha256(registration_path.read_bytes()).hexdigest()},
            {"path": str(transcript_path), "bytes": transcript_path.stat().st_size,
             "sha256": hashlib.sha256(transcript_path.read_bytes()).hexdigest()},
        ]
        with patch.dict(path_module.CURRENT_V3_ASSET_PINS, assets):
            resolved, proof_rows, capture_id = path_module._validate_v3_resolution_report(
                report, identity, selected, cwd, manager,
                (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))
            self.assertEqual(resolved, (path_module._cwd_join(cwd, output),))
            self.assertNotEqual(resolved[0], path_module._cwd_join(cwd, selected[0]))
            self.assertEqual(capture_id, "b" * 32)
            self.assertEqual(len(proof_rows), 11)
            direct_transport_proofs = report["root_transport_proofs"]

            # The current world may close the direct Tuner path after Load. The
            # menu registration remains rooted; a UI inbox only triggers the
            # retained root listener and carries its response back.
            reg_nonce = "f" * 32
            event_name = "Civ6RL_OfficialScriptPathResolve_" + reg_nonce
            root_command = (f'local root_lookup=Locale.Lookup; local event=LuaEvents["{event_name}"]; '
                            f'local helper={path_module._lua_string_literal(module_path)}; '
                            f'local digest={path_module._lua_string_literal(pins["helper_module"]["sha256"])}; '
                            f'local pid={path_module._lua_string_literal(str(identity.pid))}; '
                            f'local creation={path_module._lua_string_literal(str(identity.creation_filetime))}; '
                            f'local expected={{{path_module._lua_string_literal(selected[0])}}}; '
                            'local resolve=box.resolve; event.Add(listener)')
            event_prepare = {
                "schema": "civ6rl.localization_query_preparation.v1", "status": "ok",
                "nonce": reg_nonce, "database_function_called": False,
                "module_file_pins_retained": True,
            }
            event_prepare_line = "CIV6RL_SCRIPT_PATH_PREPARED:" + reg_nonce + ":" + json.dumps(
                event_prepare, separators=(",", ":"))
            event_registration = {
                "schema": "civ6-host.official-script-path-root-registration.v2",
                "transport": "root_event_via_ui_inbox", "nonce": reg_nonce,
                "status": "completed", "process": process, "selection": selection_file,
                "menu_selection": selection_file,
                "build": pins["build"], "owner_before": {"owner": 1},
                "owner_after": {"owner": 1},
                "exe_module": registration["exe_module"],
                "gamecore_module": registration["gamecore_module"],
                "command": root_command,
                "environment_key": "Civ6RLOfficialScriptPath_" + pins["helper_module"]["sha256"],
                "event_name": event_name, "prepare_lines": [event_prepare_line],
                "native_receipt": event_prepare, "helper_module": registration["helper_module"],
                "root_state_index": 7, "selected_names": selected,
                "records": report["records"], "attempted_nonces": [response["nonce"]],
                "native_calls": [{"index": 0, "selected_name": selected[0],
                                  "nonce": response["nonce"], "status": "ok",
                                  "raw_lines": [], "response": response}],
                "records_completed": 1,
            }
            event_registration_path = self.root / "event" / "root-registration.json"
            event_registration_path.parent.mkdir()
            event_prep_transcript = event_registration_path.parent / "tuner.jsonl"
            prep_events = [
                {"time": 1.0, "direction": "sent", "tag": 3,
                 "payload": f"CMD:7:{root_command}"},
                {"time": 2.0, "direction": "received", "tag": -1,
                 "payload": "O\x00Main: " + event_prepare_line},
            ]
            event_prep_transcript.write_text("\n".join(json.dumps(row) for row in prep_events) + "\n",
                                             encoding="utf-8")
            event_tuner_pin = {"path": str(event_prep_transcript),
                               "bytes": event_prep_transcript.stat().st_size,
                               "sha256": hashlib.sha256(event_prep_transcript.read_bytes()).hexdigest()}
            event_ack = "Lua: CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + response["nonce"] + ":" + json.dumps(
                response, separators=(",", ":"))
            event_registration["native_calls"][0]["raw_lines"] = [event_ack]
            event_registration_path.write_text(json.dumps(event_registration), encoding="utf-8")
            event_registration_pin = {"path": str(event_registration_path),
                                      "bytes": event_registration_path.stat().st_size,
                                      "sha256": hashlib.sha256(event_registration_path.read_bytes()).hexdigest()}
            event_done = "Lua: CIV6RL_SCRIPT_PATH_INBOX_RESULT:" + response["nonce"] + ":true captured"
            window_bytes = (event_ack + "\r\n" + event_done + "\r\n").encode("utf-8")
            window_path = self.root / "event-log-window.bin"
            window_path.write_bytes(window_bytes)
            window_pin = {"path": str(window_path), "bytes": len(window_bytes),
                          "sha256": hashlib.sha256(window_bytes).hexdigest()}
            command_text = (f'assert(Game.GetLocalPlayer()==0 and Game.GetCurrentGameTurn()==25 and UI.IsGameCoreBusy()==false); '
                            f'local ev=LuaEvents["{event_name}"]; local box={{registration_nonce="{reg_nonce}",'
                            f'index=0,selected_name={path_module._lua_string_literal(selected[0])},'
                            f'nonce={path_module._lua_string_literal(response["nonce"])},'
                            f'pid="{identity.pid}",creation="{identity.creation_filetime}"}}; ev.Call(box); '
                            f'print({path_module._lua_string_literal("CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + response["nonce"] + ":")}); '
                            f'print({path_module._lua_string_literal("CIV6RL_SCRIPT_PATH_INBOX_RESULT:" + response["nonce"] + ":")})')
            command_path = self.root / "commands" / f"path-0000-{response['nonce']}.lua"
            command_path.parent.mkdir()
            command_path.write_text(command_text, encoding="ascii")
            command_pin = {"path": str(command_path), "bytes": command_path.stat().st_size,
                           "sha256": hashlib.sha256(command_path.read_bytes()).hexdigest()}
            event_inbox = {
                "schema": "civ6-host.official-script-path-inbox-transport.v1",
                "registration": event_registration_pin, "process": process,
                "player_id": 0, "turn": 25, "inbox_path": str(self.root / "Civ6RLInbox.lua"),
                "log_source_path": str(self.root / "Lua.log"), "inbox_restored": True,
                "records": [{
                    "index": 0, "selected_name": selected[0], "nonce": response["nonce"],
                    "command_pin": command_pin, "log_window": window_pin, "log_offset": 100,
                    "ack_line": event_ack, "result_line": event_done,
                    "inbox_before_sha256": "1" * 64, "inbox_written_sha256": command_pin["sha256"],
                    "inbox_restored_sha256": "1" * 64, "inbox_restored": True,
                    "log_source_metadata": {
                        "path": str(self.root / "Lua.log"), "file_device": 1, "file_id": 2,
                        "size_before": 1000, "mtime_ns_before": 50, "size_after": 3000,
                        "mtime_ns_after": 50, "offset": 100, "window_bytes": len(window_bytes),
                        "window_sha256": window_pin["sha256"],
                        "live_slice_sha256": window_pin["sha256"], "live_slice_matches": True,
                    },
                }],
            }
            event_inbox_path = self.root / "inbox-transport.json"
            event_inbox_path.write_text(json.dumps(event_inbox), encoding="utf-8")
            event_inbox_pin = {"path": str(event_inbox_path), "bytes": event_inbox_path.stat().st_size,
                               "sha256": hashlib.sha256(event_inbox_path.read_bytes()).hexdigest()}
            report["root_transport_proofs"] = [selection_file, event_registration_pin,
                                               event_tuner_pin, event_inbox_pin]
            event_resolved, event_proofs, event_capture_id = path_module._validate_v3_resolution_report(
                report, identity, selected, cwd, manager,
                (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))
            self.assertEqual(event_resolved, resolved)
            self.assertEqual(event_capture_id, capture_id)
            self.assertEqual(len(event_proofs), 15)
            event_inbox["records"][0]["log_source_metadata"]["live_slice_matches"] = False
            event_inbox_path.write_text(json.dumps(event_inbox), encoding="utf-8")
            report["root_transport_proofs"][3] = {
                "path": str(event_inbox_path), "bytes": event_inbox_path.stat().st_size,
                "sha256": hashlib.sha256(event_inbox_path.read_bytes()).hexdigest(),
            }
            with self.assertRaisesRegex(ScriptPathError, "does not bind the captured live slice"):
                path_module._validate_v3_resolution_report(
                    report, identity, selected, cwd, manager,
                    (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))
            report["root_transport_proofs"] = [
                *direct_transport_proofs,
            ]

            bad_registration = json.loads(original_registration_raw)
            bad_registration["native_calls"][0]["nonce"] = "d" * 32
            registration_path.write_text(json.dumps(bad_registration), encoding="utf-8")
            report["root_transport_proofs"][1] = {
                "path": str(registration_path), "bytes": registration_path.stat().st_size,
                "sha256": hashlib.sha256(registration_path.read_bytes()).hexdigest(),
            }
            with self.assertRaisesRegex(ScriptPathError, "native call 0 does not match"):
                path_module._validate_v3_resolution_report(
                    report, identity, selected, cwd, manager,
                    (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))
            registration_path.write_bytes(original_registration_raw)
            report["root_transport_proofs"][1] = {
                "path": str(registration_path), "bytes": registration_path.stat().st_size,
                "sha256": hashlib.sha256(registration_path.read_bytes()).hexdigest(),
            }

            original_transcript_raw = transcript_path.read_bytes()
            bad_events = [json.loads(line) for line in original_transcript_raw.decode("utf-8").splitlines()]
            bad_events[-1]["payload"] = bad_events[-1]["payload"].replace(response["nonce"], "e" * 32)
            transcript_path.write_text("\n".join(json.dumps(event) for event in bad_events) + "\n",
                                       encoding="utf-8")
            report["root_transport_proofs"][2] = {
                "path": str(transcript_path), "bytes": transcript_path.stat().st_size,
                "sha256": hashlib.sha256(transcript_path.read_bytes()).hexdigest(),
            }
            with self.assertRaisesRegex(ScriptPathError, "not present exactly once"):
                path_module._validate_v3_resolution_report(
                    report, identity, selected, cwd, manager,
                    (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))
            transcript_path.write_bytes(original_transcript_raw)
            report["root_transport_proofs"][2] = {
                "path": str(transcript_path), "bytes": transcript_path.stat().st_size,
                "sha256": hashlib.sha256(transcript_path.read_bytes()).hexdigest(),
            }

            bad = json.loads(json.dumps(report))
            bad["records"][0]["response"]["input_utf16le_hex"] = "00"
            with self.assertRaisesRegex(ScriptPathError, "input does not exactly match"):
                path_module._validate_v3_resolution_report(bad, identity, selected, cwd, manager,
                    (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))

            bad = json.loads(json.dumps(report))
            bad["records"][0]["response"]["nonce"] = "not-a-nonce"
            with self.assertRaisesRegex(ScriptPathError, "nonces must be unique"):
                path_module._validate_v3_resolution_report(bad, identity, selected, cwd, manager,
                    (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))

            bad = json.loads(json.dumps(report))
            bad["records"][0]["response"]["native_method_called"] = False
            with self.assertRaisesRegex(ScriptPathError, "native_method_called"):
                path_module._validate_v3_resolution_report(bad, identity, selected, cwd, manager,
                    (selection_file["path"], selection_file["bytes"], selection_file["sha256"]))

            native_file = self.cwd / "DLC" / "Expansion2" / "Scripts" / "WorldCongress.lua"
            native_file.parent.mkdir(parents=True)
            native_file.write_bytes(self.source_bytes)
            selection_path = Path(selection_file["path"])
            selection_pin = {"path": str(selection_path), "bytes": len(selection_raw),
                             "sha256": hashlib.sha256(selection_raw).hexdigest()}
            report_raw = json.dumps(report).encode("utf-8")
            report_path = self.root / "v3-path-report.json"
            report_path.write_bytes(report_raw)
            report_pin = {"path": str(report_path), "bytes": len(report_raw),
                          "sha256": hashlib.sha256(report_raw).hexdigest()}
            resolver_path = resource_root() / path_module.CURRENT_BINDINGS_PATH
            resolver_raw = resolver_path.read_bytes()
            caller_path = resource_root() / path_module.CURRENT_CALLER_BINDINGS_PATH
            caller_raw = caller_path.read_bytes()
            observer_path = Path(path_module.__file__).resolve()
            observer_raw = observer_path.read_bytes()
            image_base = 0x7FF600000000
            path_singleton = 0x7FF700001000
            actual_vtable = image_base + path_module.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA
            witness = {
                "schema": path_module.CURRENT_V3_SCHEMA, "status": path_module.CURRENT_V3_STATUS,
                "process": process, "cwd": cwd, "selected": selected,
                "resolved_sources": [{"path": str(native_file), "bytes": len(self.source_bytes),
                                      "sha256": hashlib.sha256(self.source_bytes).hexdigest()}],
                "selection_witness": selection_pin,
                "resolver_source": {"path": str(resolver_path), "bytes": len(resolver_raw),
                                    "sha256": hashlib.sha256(resolver_raw).hexdigest()},
                "caller_source": {"path": str(resource_root() / path_module.CURRENT_CALLER_BINDINGS_PATH),
                                  "bytes": len(caller_raw), "sha256": hashlib.sha256(caller_raw).hexdigest()},
                "override_source": override_pin, "path_resolution_report": report_pin,
                "capture_id": report["capture_id"],
                "observer": {"path": str(observer_path), "bytes": len(observer_raw),
                             "sha256": hashlib.sha256(observer_raw).hexdigest()},
                "resolver_live": {
                    "singleton": path_singleton,
                    "vtable": image_base + path_module.CURRENT_VTABLE_RVA,
                    "method": image_base + path_module.CURRENT_METHOD_RVA,
                    "script_manager": manager, "script_manager_vtable": actual_vtable,
                    "script_manager_slot_30": image_base + path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA,
                },
                "psutil_version": "7.1.0", "native_function_called": True,
                "native_method_called": True, "game_memory_written": None,
                "external_process_memory_write_performed": False,
                "native_resolver_state_changes_proven_absent": False,
                "filesystem_search_scope": "capture_python_only",
                "process_environment_read": False, "filesystem_search_used": False,
                "historical_execution_bytes_proven": False,
            }
            context = path_module._parse_context(witness, "0" * 64, identity)
            self.assertEqual(context.profile_id, path_module.CURRENT_V3_PROFILE_ID)
            self.assertEqual(context.source_by_selected[selected[0]].resolved_path,
                             path_module._cwd_join(cwd, output))
            overstated_scope = dict(witness, game_memory_written=False)
            with self.assertRaisesRegex(ScriptPathError, "scope its native method call"):
                path_module._parse_context(overstated_scope, "0" * 64, identity)
            host_root = Path(path_module.__file__).resolve().parents[3]
            tool_spec = importlib.util.spec_from_file_location(
                "capture_script_path_witness_fixture", host_root / "tools/capture_script_path_witness.py")
            self.assertIsNotNone(tool_spec)
            tool_module = importlib.util.module_from_spec(tool_spec)
            assert tool_spec.loader is not None
            tool_spec.loader.exec_module(tool_module)
            capture = tool_module.capture
            live_observation = {
                "process": process, "cwd": cwd,
                "resolver_live": {
                    "singleton": path_singleton,
                    "vtable": image_base + path_module.CURRENT_VTABLE_RVA,
                    "method": image_base + path_module.CURRENT_METHOD_RVA,
                    "script_manager": manager, "script_manager_vtable": actual_vtable,
                    "script_manager_slot_30": image_base + path_module.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA,
                },
                "profile_id": path_module.CURRENT_V3_PROFILE_ID, "psutil_version": "7.1.0",
            }
            def observer(expected_identity):
                self.assertEqual(expected_identity["profile_id"], path_module.CURRENT_V3_PROFILE_ID)
                self.assertEqual(expected_identity["override_bindings_sha256"],
                                 path_module.CURRENT_OVERRIDE_BINDINGS_SHA256)
                return live_observation
            captured_raw = capture(
                selection_path, hashlib.sha256(selection_raw).hexdigest(), [self.game],
                path_resolution_report=report_path,
                path_resolution_sha256=hashlib.sha256(report_raw).hexdigest(),
                observer=observer,
            )
            captured = json.loads(captured_raw)
            self.assertEqual(captured["schema"], path_module.CURRENT_V3_SCHEMA)
            self.assertTrue(captured["native_method_called"])
            self.assertIsNone(captured["game_memory_written"])
            self.assertFalse(captured["external_process_memory_write_performed"])
            self.assertFalse(captured["native_resolver_state_changes_proven_absent"])
            self.assertEqual(captured["filesystem_search_scope"], "capture_python_only")
            self.assertEqual(captured["resolved_sources"][0]["path"],
                             path_module._cwd_join(cwd, output))

    def test_v3_root_helper_build_and_module_match_reviewed_pins(self) -> None:
        lab_root = resource_root()
        locations = {
            "build": lab_root / "work/official-capture/current-image-adapter/path-build-root/official-script-path-build.json",
            "helper_module": lab_root / "work/official-capture/current-image-adapter/path-build-root/civ6rl-official-script-path.dll",
            "helper_source": lab_root / "work/official-capture/current-image-adapter/path-build-root/official_script_path_receipt.c",
        }
        build = json.loads(locations["build"].read_bytes())
        self.assertEqual(build["lua_scope"], "root")
        for label, path in locations.items():
            expected_path, expected_bytes, expected_sha = path_module.CURRENT_V3_ASSET_PINS[label]
            raw = path.read_bytes()
            self.assertTrue(str(path).replace("\\", "/").endswith(expected_path), label)
            self.assertEqual(len(raw), expected_bytes, label)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_sha, label)

    def test_current_witness_parser_requires_the_joined_caller_receipt(self) -> None:
        identity = ProcessIdentity(23456, 134380170124816754,
                                   r"C:\Program Files (x86)\Steam\CivilizationVI.exe")
        process = {"pid": identity.pid, "creation_filetime": identity.creation_filetime,
                   "image_path": identity.image_path}
        image_base = 0x7FF600000000
        selected = [self.selected_name]
        selection_doc = {"gameplay_selection994": {
            "schema": "civ6rl.official_gameplay_selection994.capture.v2",
            "process": process,
            "exe_module": {"path": identity.image_path, "base": image_base, "bytes": 0x3700000},
            "gamecore_module": {"sha256": path_module.CURRENT_CORE_SHA256},
            "snapshot": {"schema": "civ6rl.gameplay_selection994.memory_snapshot.v2",
                         "executable_sha256": path_module.CURRENT_EXE_SHA256,
                         "current_correspondence_sha256": path_module.CURRENT_SELECTION_SOURCE_SHA256,
                         "selected_paths": selected},
        }}
        selection_raw = json.dumps(selection_doc).encode("utf-8")
        selection_path = self.root / "current-runtime-selection.json"
        selection_path.write_bytes(selection_raw)
        path = self._cwd_join_for_test(self.cwd, self.selected_name)
        source_raw = self.source_bytes
        singleton = 0x7FF700001000
        manager = 0x7FF700002000
        vtable = image_base + path_module.CURRENT_VTABLE_RVA
        manager_vtable = image_base + path_module.CURRENT_SCRIPT_MANAGER_VTABLE_RVA
        pins = {
            "selection_witness": {"path": str(selection_path), "bytes": len(selection_raw),
                                  "sha256": hashlib.sha256(selection_raw).hexdigest()},
            "resolver_source": {"path": str(resource_root() / path_module.CURRENT_BINDINGS_PATH),
                                "bytes": path_module.CURRENT_BINDINGS_BYTES,
                                "sha256": path_module.CURRENT_BINDINGS_SHA256},
            "caller_source": {"path": str(resource_root() / path_module.CURRENT_CALLER_BINDINGS_PATH),
                              "bytes": path_module.CURRENT_CALLER_BINDINGS_BYTES,
                              "sha256": path_module.CURRENT_CALLER_BINDINGS_SHA256},
            "observer": {"path": str(Path(path_module.__file__).resolve()),
                         "bytes": Path(path_module.__file__).stat().st_size,
                         "sha256": hashlib.sha256(Path(path_module.__file__).read_bytes()).hexdigest()},
        }
        witness = {"schema": path_module.CURRENT_SCHEMA, "status": path_module.STATUS,
                   "process": process, "cwd": str(self.cwd), "selected": selected,
                   "resolved_sources": [{"path": path, "bytes": len(source_raw),
                                         "sha256": hashlib.sha256(source_raw).hexdigest()}],
                   **pins,
                   "resolver_live": {"singleton": singleton,
                                     "vtable": vtable,
                                     "method": image_base + path_module.CURRENT_METHOD_RVA,
                                     "script_manager": manager,
                                     "script_manager_vtable": manager_vtable,
                                     "script_manager_slot_30": image_base + path_module.CURRENT_SCRIPT_MANAGER_WRAPPER_RVA},
                   "psutil_version": "7.1.0", "native_function_called": False,
                   "game_memory_written": False, "process_environment_read": False,
                   "filesystem_search_used": False, "historical_execution_bytes_proven": False}
        context = path_module._parse_context(witness, "0" * 64, identity)
        self.assertEqual(context.profile_id, path_module.CURRENT_PROFILE_ID)
        self.assertEqual(context.script_manager_vtable, manager_vtable)
        self.assertEqual(context.script_manager_slot_30,
                         image_base + path_module.CURRENT_SCRIPT_MANAGER_WRAPPER_RVA)
        del witness["caller_source"]
        with self.assertRaisesRegex(ScriptPathError, "caller proof is missing"):
            path_module._parse_context(witness, "0" * 64, identity)

    @staticmethod
    def _cwd_join_for_test(cwd: Path, selected: str) -> str:
        from civ6_host.runtime.capture_script_paths import _cwd_join
        return _cwd_join(str(cwd), selected)

    def _witness_pin(self) -> dict[str, object]:
        raw = self.witness_path.read_bytes()
        return {"path": str(self.witness_path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


if __name__ == "__main__":
    unittest.main()

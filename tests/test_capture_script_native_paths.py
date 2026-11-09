"""Composed offline fixture for menu-root to post-Load inbox path capture."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime

from civ6_host.runtime import capture_script_paths as paths
from civ6_host.runtime.native import native_localization_export as export
from civ6_host.runtime.paths import resource_root


HOST = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_script_native_paths_fixture", HOST / "tools/capture_script_native_paths.py")
producer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(producer)


class _ReadOnlyProcess:
    def __init__(self, identity, modules):
        self._identity = identity
        self._modules = modules if callable(modules) else lambda: modules

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False

    def identity(self):
        return dict(self._identity)

    def modules(self):
        return [dict(row) for row in self._modules()]


class _Harness:
    def __init__(self, pid, creation, *, fail_first=False, lua_scope="root"):
        self.pid, self.creation = pid, creation
        self.fail_first = fail_first
        self.lua_scope = lua_scope
        self.current_scope = "root"
        self.prepared = False
        self.prepare_calls = 0
        self.path_calls = []
        self.load_calls = []
        self.lines = []
        self.command_count = 0
        self.root_index = 4
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals()._fixture_print = lambda line: self.lines.append(line)
        self.lua.globals()._fixture_prepare = self.prepare
        self.lua.globals()._fixture_resolve = self.resolve
        self.lua.globals()._fixture_load = self.load
        self.lua.globals()._fixture_scope = self.set_scope
        self.lua.execute("""
            print = _fixture_print
            Locale = { Lookup = function(s) return s end }
            Game = { GetLocalPlayer=function() return 1 end,
                     GetCurrentGameTurn=function() return 17 end }
            UI = { IsGameCoreBusy=function() return false end }
            LuaEvents = setmetatable({}, {__index=function(t,k)
                local event = {}
                event.Add=function(listener) event.listener=listener end
                event.Call=function(box) assert(type(event.listener)=="function"); local prior=_fixture_scope(); _fixture_scope("root"); local ok,result=pcall(event.listener,box); _fixture_scope(prior); if not ok then error(result) end; return result end
                rawset(t,k,event); return event
            end})
            package.loadlib = function(path, symbol)
                _fixture_load(path, symbol)
                if symbol == "civ6rl_localization_query_prepare" then
                    return function(...) return _fixture_prepare(...) end
                elseif symbol == "civ6rl_official_script_path" then
                    return function(...) return _fixture_resolve(...) end
                end
                return nil, "unexpected symbol"
            end
        """)

    def set_scope(self, scope=None):
        previous = self.current_scope
        if scope is not None:
            self.current_scope = scope
        return previous

    def load(self, path, symbol):
        self.load_calls.append((path, symbol))

    def prepare(self, nonce, pid, creation):
        if self.path_calls or self.prepared:
            raise AssertionError("root preparation occurred late or more than once")
        if self.current_scope != "root":
            raise AssertionError("helper preparation was not in root scope")
        if (pid, creation) != (str(self.pid), str(self.creation)):
            raise AssertionError("root preparation identity differs")
        self.prepare_calls += 1
        self.prepared = True
        return json.dumps({
            "schema": "civ6rl.localization_query_preparation.v1", "status": "ok",
            "nonce": nonce, "database_function_called": False,
            "module_file_pins_retained": True,
        }, separators=(",", ":"))

    def resolve(self, selected_name, nonce, pid, creation, lookup):
        if not self.prepared:
            raise AssertionError("root path callback ran before preparation")
        if (pid, creation) != (str(self.pid), str(self.creation)) or not callable(lookup):
            raise AssertionError("root path callback identity/Locale.Lookup differs")
        if self.current_scope != self.lua_scope:
            raise AssertionError("path callback ran in the wrong Lua scope")
        self.path_calls.append((selected_name, nonce))
        if self.fail_first:
            raise RuntimeError("simulated root helper refusal")
        resolved = "C:\\Resolved\\" + selected_name.rsplit("/", 1)[-1]
        response = {
            "schema": "civ6-host.official_script_path_resolution.v1", "status": "ok",
            "nonce": nonce, "pid": self.pid, "creation_filetime": self.creation,
            "thread_id": 177, "manager_address": "0x123456789abc",
            "manager_vtable_rva": hex(paths.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA),
            "method_rva": hex(paths.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA),
            "capacity_utf16_units": 260,
            "input_utf16le_hex": (selected_name + "\0").encode("utf-16-le").hex(),
            "output_utf16le_hex": (resolved + "\0").encode("utf-16-le").hex(),
            "executable_sha256": producer.EXE_SHA, "lua_scope": self.lua_scope,
            "lua_cs_owned": True, "native_method_called": True,
            "gamecore_function_called_by_helper": False,
            "output_file_opened_by_helper": False,
            "exe_method_may_delegate_to_content_resolver": True,
            "nested_resolver_side_effects_asserted_absent": False,
            "path_exists_checked": False,
        }
        return json.dumps(response, separators=(",", ":"))


class _MenuTuner:
    def __init__(self, harness, transcript):
        self.harness = harness
        self.transcript = Path(transcript)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False

    def state_index(self, context):
        if context not in ("Main State", self.harness.root_index):
            raise AssertionError("producer left Main State")
        return self.harness.root_index

    def execute(self, code, *, context="InGame", timeout=None):
        if context != self.harness.root_index:
            raise AssertionError("menu registration was not sent to Main State")
        self.harness.command_count += 1
        self.harness.set_scope("root")
        self.harness.lines.clear()
        wrapped = f"CMD:{self.harness.root_index}:{code}"
        self._event("sent", 3, wrapped)
        self.harness.lua.execute(code)
        for line in self.harness.lines:
            self._event("received", 3, "O\x00fixture: " + line)
        return list(self.harness.lines)

    def _event(self, direction, tag, payload):
        row = {"time": float(self.harness.command_count), "direction": direction,
               "tag": tag, "payload": payload}
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=True) + "\n")


class CaptureScriptNativePathsFixture(unittest.TestCase):
    def test_menu_root_event_two_ordered_inbox_calls_and_single_shot_failure(self):
        root = resource_root()
        build_path = root / "work/official-capture/current-image-adapter/path-build-root/official-script-path-build.json"
        build, _, module_pin, _ = producer._check_build(build_path)
        exe_row = next(row for row in build["source_evidence"]
                       if Path(row["path"]).name.casefold() == "civilizationvi.exe")
        exe_path = Path(exe_row["path"])
        pid, creation = 29736, 134384578846013017
        identity = {"pid": pid, "creation_filetime": creation, "image_path": str(exe_path)}
        selected_names = ["Mods/Alpha.lua", "Mods/Beta.lua"]
        owner = {"source": "fixture", "pid": pid, "port": 4318,
                 "server_endpoints": [{"LocalAddress": "127.0.0.1", "LocalPort": 4318,
                                       "RemoteAddress": "0.0.0.0", "RemotePort": 0,
                                       "OwningProcess": pid}], "tcp_state_interpreted": False}
        helper_module = {"name": Path(module_pin["path"]).name, "path": module_pin["path"],
                         "base": 0x7FF700000000, "bytes": module_pin["bytes"],
                         "sha256": module_pin["sha256"]}

        with tempfile.TemporaryDirectory(dir=root / "work") as temp_name:
            temp = Path(temp_name)
            core_path = temp / "GameCore_XP2_FinalRelease.dll"
            core_path.write_bytes(b"fixture current Core")
            exe_module = {"name": "CivilizationVI.exe", "path": str(exe_path),
                          "base": 0x140000000, "bytes": 21189480}
            menu_core = {"name": "GameCore_XP2_FinalRelease.dll", "path": str(core_path),
                         "base": 0x7FF500000000, "bytes": core_path.stat().st_size,
                         "sha256": producer.CORE_SHA}
            live_core = {**menu_core, "base": 0x7FF600000000}
            live_core.pop("sha256")
            menu_selection = {"gameplay_selection994": {
                "schema": "civ6rl.official_gameplay_selection994.capture.v2",
                "process": identity, "exe_module": exe_module,
                "gamecore_module": menu_core,
                "snapshot": {"executable_sha256": producer.EXE_SHA,
                             "current_correspondence_sha256": producer.SELECTION_SHA,
                             "selected_paths": selected_names},
            }}
            fresh_selection = {"gameplay_selection994": {
                **menu_selection["gameplay_selection994"],
                "gamecore_module": {**live_core, "sha256": producer.CORE_SHA},
            }}
            menu_path, fresh_path = temp / "menu-selection.json", temp / "fresh-selection.json"
            menu_raw = (json.dumps(menu_selection, separators=(",", ":")) + "\n").encode()
            fresh_raw = (json.dumps(fresh_selection, separators=(",", ":")) + "\n").encode()
            menu_path.write_bytes(menu_raw)
            fresh_path.write_bytes(fresh_raw)
            menu_sha = hashlib.sha256(menu_raw).hexdigest()
            fresh_sha = hashlib.sha256(fresh_raw).hexdigest()
            modules = [exe_module]
            harness = _Harness(pid, creation)
            real_reference = export.reference

            def reference(path):
                path = Path(path)
                if path.resolve() == exe_path.resolve():
                    return {"path": str(exe_path), "bytes": exe_row["bytes"], "sha256": producer.EXE_SHA}
                if path.resolve() == core_path.resolve():
                    return {"path": str(core_path), "bytes": core_path.stat().st_size,
                            "sha256": producer.CORE_SHA}
                return real_reference(path)

            def process_factory(_pid):
                return _ReadOnlyProcess(identity, modules)

            with patch.object(producer, "ReadOnlyProcess", side_effect=process_factory), \
                 patch.object(producer, "_primary_tuner_owner", return_value=owner), \
                 patch.object(producer, "TunerClient", side_effect=lambda **kwargs: _MenuTuner(harness, kwargs["transcript"])), \
                 patch.object(export, "reference", side_effect=reference), \
                 patch.object(export, "_helper_module", return_value=helper_module):
                output = temp / "official-path-capture"
                prepared = producer.prepare_at_menu(menu_path, menu_sha, build_path, output)
                registration_path = Path(prepared["registration"]["path"])
                registration = json.loads(registration_path.read_text(encoding="utf-8"))
                self.assertEqual(registration["status"], "prepared_at_menu")
                self.assertEqual(registration["menu_selection"], registration["selection"])
                self.assertEqual(harness.prepare_calls, 1)
                self.assertEqual(harness.path_calls, [])
                self.assertEqual(harness.command_count, 1)
                self.assertEqual([item[1] for item in harness.load_calls], [
                    producer.PREPARE_EXPORT, producer.RESOLVE_EXPORT])

                # Load can change module base and provide Core only after the saved game is opened.
                modules[:] = [exe_module, live_core]
                inbox = temp / "Civ6RLInbox.lua"
                inbox.write_bytes(b"previous mounted inbox\n")
                log = temp / "Lua.log"
                log.write_bytes(b"")
                initial_inbox = inbox.read_bytes()
                stop = threading.Event()
                watcher_error = []
                seen = set()

                def watch_inbox(expected_count):
                    while not stop.is_set() and len(seen) < expected_count:
                        try:
                            raw = inbox.read_bytes()
                            digest = hashlib.sha256(raw).hexdigest()
                            if raw != initial_inbox and digest not in seen:
                                seen.add(digest)
                                harness.lines.clear()
                                harness.lua.execute(raw.decode("ascii"))
                                with log.open("ab") as stream:
                                    for line in harness.lines:
                                        stream.write(line.encode("utf-8") + b"\n")
                        except Exception as exc:
                            watcher_error.append(exc)
                            return
                        time.sleep(0.01)

                watcher = threading.Thread(target=watch_inbox, args=(2,), daemon=True)
                watcher.start()
                try:
                    report_result = producer.capture_after_load(
                        registration_path, fresh_path, fresh_sha, inbox, log,
                        player_id=1, turn=17, timeout=3)
                except Exception as exc:
                    self.fail(f"capture failed: {exc}; watcher={watcher_error}; log={log.read_bytes()!r}; calls={harness.path_calls!r}")
                stop.set()
                watcher.join(timeout=2)
                self.assertFalse(watcher_error)
                self.assertEqual(inbox.read_bytes(), initial_inbox)
                self.assertEqual([row[0] for row in harness.path_calls], selected_names)
                self.assertEqual(harness.command_count, 1)
                report = json.loads(Path(report_result["path"]).read_text(encoding="utf-8"))
                self.assertEqual([row["selected_name"] for row in report["records"]], selected_names)
                self.assertEqual(report["root_transport_proofs"][0]["sha256"], fresh_sha)
                self.assertNotEqual(registration["selection"]["sha256"], fresh_sha)
                self.assertEqual(len(report["root_transport_proofs"]), 4)
                final_registration = json.loads(registration_path.read_text(encoding="utf-8"))
                self.assertEqual(final_registration["menu_selection"], registration["menu_selection"])
                self.assertEqual(final_registration["selection"]["sha256"], fresh_sha)
                self.assertEqual(final_registration["native_calls"][1]["response"], report["records"][1]["response"])
                validated, _pins, capture_id = paths._validate_v3_resolution_report(
                    report, paths.ProcessIdentity(pid, creation, str(exe_path)), selected_names,
                    r"C:\Fixture\Main", int("123456789abc", 16),
                    (report["root_transport_proofs"][0]["path"],
                     report["root_transport_proofs"][0]["bytes"],
                     report["root_transport_proofs"][0]["sha256"]))
                self.assertEqual(validated, (r"C:\Resolved\Alpha.lua", r"C:\Resolved\Beta.lua"))
                self.assertEqual(capture_id, report["capture_id"])

                # A first-call refusal remains single-shot and produces no success report.
                failed_harness = _Harness(pid, creation, fail_first=True)
                failed_folder = temp / "failed-capture"
                modules[:] = [exe_module]
                with patch.object(producer, "TunerClient",
                                  side_effect=lambda **kwargs: _MenuTuner(failed_harness, kwargs["transcript"])):
                    failed_prepared = producer.prepare_at_menu(menu_path, menu_sha, build_path, failed_folder)
                modules[:] = [exe_module, live_core]
                failed_inbox = temp / "FailedInbox" / "Civ6RLInbox.lua"
                failed_inbox.parent.mkdir()
                failed_inbox.write_bytes(b"previous failed inbox\n")
                failed_log = temp / "FailedLua.log"
                failed_log.write_bytes(b"")
                failed_initial = failed_inbox.read_bytes()
                failed_stop = threading.Event()
                failed_seen = set()

                def watch_failed_inbox():
                    while not failed_stop.is_set() and not failed_seen:
                        try:
                            raw = failed_inbox.read_bytes()
                            digest = hashlib.sha256(raw).hexdigest()
                            if raw != failed_initial and digest not in failed_seen:
                                failed_seen.add(digest)
                                failed_harness.lines.clear()
                                failed_harness.lua.execute(raw.decode("ascii"))
                                with failed_log.open("ab") as stream:
                                    for line in failed_harness.lines:
                                        stream.write(line.encode("utf-8") + b"\n")
                        except Exception as exc:
                            watcher_error.append(exc)
                            return
                        time.sleep(0.01)

                failed_watcher = threading.Thread(target=watch_failed_inbox, daemon=True)
                failed_watcher.start()
                with self.assertRaises(ValueError):
                    producer.capture_after_load(
                        Path(failed_prepared["registration"]["path"]), fresh_path, fresh_sha,
                        failed_inbox, failed_log, player_id=1, turn=17, timeout=2)
                failed_stop.set()
                failed_watcher.join(timeout=2)
                self.assertFalse(watcher_error)
                self.assertEqual(failed_inbox.read_bytes(), failed_initial)
                self.assertEqual(len(failed_harness.path_calls), 1)
                self.assertFalse((failed_folder / "report.json").exists())

    def test_ui_scoped_callback_is_handed_off_then_called_from_ui_once_per_name(self):
        root = resource_root()
        build_path = root / "work/official-capture/current-image-adapter/path-build-ui/official-script-path-build.json"
        build, _, module_pin, _ = producer._check_build(build_path)
        exe_row = next(row for row in build["source_evidence"]
                       if Path(row["path"]).name.casefold() == "civilizationvi.exe")
        exe_path = Path(exe_row["path"])
        pid, creation = 11028, 134384613941212438
        template_pid, template_creation = 29736, 134384578846013017
        identity = {"pid": pid, "creation_filetime": creation, "image_path": str(exe_path)}
        template_identity = {"pid": template_pid, "creation_filetime": template_creation,
                             "image_path": str(exe_path)}
        selected_names = ["../../../DLC/Expansion2/Scripts/WorldCongress.lua",
                          "C:/Program Files (x86)/Steam/steamapps/workshop/content/289070/2865001760/scripts/bbg_script.lua"]
        owner = {"source": "fixture", "pid": pid, "port": 4318,
                 "server_endpoints": [{"LocalAddress": "127.0.0.1", "LocalPort": 4318,
                                       "RemoteAddress": "0.0.0.0", "RemotePort": 0,
                                       "OwningProcess": pid}], "tcp_state_interpreted": False}
        helper_module = {"name": Path(module_pin["path"]).name, "path": module_pin["path"],
                         "base": 0x7FF700000000, "bytes": module_pin["bytes"],
                         "sha256": module_pin["sha256"]}

        with tempfile.TemporaryDirectory(dir=root / "work") as temp_name:
            temp = Path(temp_name)
            core_path = temp / "GameCore_XP2_FinalRelease.dll"
            core_path.write_bytes(b"fixture current Core")
            exe_module = {"name": "CivilizationVI.exe", "path": str(exe_path),
                          "base": 0x140000000, "bytes": 21189480}
            core_module = {"name": "GameCore_XP2_FinalRelease.dll", "path": str(core_path),
                           "base": 0x7FF600000000, "bytes": core_path.stat().st_size,
                           "sha256": producer.CORE_SHA}
            live_core = {key: value for key, value in core_module.items() if key != "sha256"}

            def selection(identity_for_file, with_core):
                doc = {"gameplay_selection994": {
                    "schema": "civ6rl.official_gameplay_selection994.capture.v2",
                    "process": identity_for_file, "exe_module": exe_module,
                    "gamecore_module": core_module if with_core else {
                        **core_module, "base": 0x7FF500000000},
                    "snapshot": {"executable_sha256": producer.EXE_SHA,
                                 "current_correspondence_sha256": producer.SELECTION_SHA,
                                 "selected_paths": selected_names},
                }}
                raw = (json.dumps(doc, separators=(",", ":")) + "\n").encode()
                return doc, raw

            template_doc, template_raw = selection(template_identity, False)
            fresh_doc, fresh_raw = selection(identity, True)
            template_path, fresh_path = temp / "menu-template.json", temp / "fresh-selection.json"
            template_path.write_bytes(template_raw)
            fresh_path.write_bytes(fresh_raw)
            template_sha = hashlib.sha256(template_raw).hexdigest()
            fresh_sha = hashlib.sha256(fresh_raw).hexdigest()
            modules = [exe_module]
            harness = _Harness(pid, creation, lua_scope="ui")
            real_reference = export.reference

            def reference(path):
                path = Path(path)
                if path.resolve() == exe_path.resolve():
                    return {"path": str(exe_path), "bytes": exe_row["bytes"], "sha256": producer.EXE_SHA}
                if path.resolve() == core_path.resolve():
                    return {"path": str(core_path), "bytes": core_path.stat().st_size,
                            "sha256": producer.CORE_SHA}
                return real_reference(path)

            def process_factory(_pid):
                return _ReadOnlyProcess(identity, modules)

            with patch.object(producer, "ReadOnlyProcess", side_effect=process_factory), \
                 patch.object(producer, "_primary_tuner_owner", return_value=owner), \
                 patch.object(producer, "TunerClient", side_effect=lambda **kwargs: _MenuTuner(harness, kwargs["transcript"])), \
                 patch.object(export, "reference", side_effect=reference), \
                 patch.object(export, "_helper_module", return_value=helper_module):
                output = temp / "ui-path-capture"
                prepared = producer.prepare_at_menu(template_path, template_sha, build_path,
                                                     output, pid=pid)
                registration_path = Path(prepared["registration"]["path"])
                registration = json.loads(registration_path.read_text(encoding="utf-8"))
                self.assertEqual(registration["status"], "prepared_at_menu")
                self.assertEqual(registration["process"], identity)
                self.assertEqual(registration["template_process"], template_identity)
                self.assertEqual(registration["menu_selection_role"], "expected_names_template")
                self.assertEqual(registration["callback_scope"], "ui")
                self.assertEqual(harness.prepare_calls, 1)
                self.assertEqual(harness.path_calls, [])
                self.assertIn("box.callback=resolve", registration["command"])
                self.assertNotIn("resolve(box.selected_name", registration["command"])

                modules[:] = [exe_module, live_core]
                inbox = temp / "Civ6RLInbox.lua"
                inbox.write_bytes(b"previous UI inbox\n")
                log = temp / "Lua.log"
                log.write_bytes(b"")
                initial_inbox = inbox.read_bytes()
                stop = threading.Event()
                watcher_error = []
                seen = set()

                def watch_inbox(expected_count):
                    while not stop.is_set() and len(seen) < expected_count:
                        try:
                            raw = inbox.read_bytes()
                            digest = hashlib.sha256(raw).hexdigest()
                            if raw != initial_inbox and digest not in seen:
                                seen.add(digest)
                                harness.set_scope("ui")
                                harness.lines.clear()
                                harness.lua.execute(raw.decode("ascii"))
                                with log.open("ab") as stream:
                                    for line in harness.lines:
                                        stream.write(line.encode("utf-8") + b"\n")
                        except Exception as exc:
                            watcher_error.append(exc)
                            return
                        time.sleep(0.01)

                watcher = threading.Thread(target=watch_inbox, args=(2,), daemon=True)
                watcher.start()
                try:
                    report_result = producer.capture_after_load(
                        registration_path, fresh_path, fresh_sha, inbox, log,
                        player_id=1, turn=17, timeout=3)
                except Exception as exc:
                    self.fail(f"UI capture failed: {exc}; watcher={watcher_error}; log={log.read_bytes()!r}; calls={harness.path_calls!r}")
                stop.set()
                watcher.join(timeout=2)
                self.assertFalse(watcher_error)
                self.assertEqual(inbox.read_bytes(), initial_inbox)
                self.assertEqual([row[0] for row in harness.path_calls], selected_names)
                report = json.loads(Path(report_result["path"]).read_text(encoding="utf-8"))
                self.assertEqual(report["execution_profile"]["profile_id"], producer.UI_PROFILE_ID)
                self.assertEqual([row["selected_name"] for row in report["records"]], selected_names)
                self.assertTrue(all(row["response"]["lua_scope"] == "ui" for row in report["records"]))
                self.assertEqual(report["root_transport_proofs"][0]["sha256"], fresh_sha)
                self.assertEqual(len(report["root_transport_proofs"]), 4)
                final_registration = json.loads(registration_path.read_text(encoding="utf-8"))
                self.assertEqual(final_registration["selection"]["sha256"], fresh_sha)
                self.assertEqual(final_registration["menu_selection"]["sha256"], template_sha)
                self.assertEqual(final_registration["native_calls"][0]["handoff_nonce"], registration["nonce"])
                self.assertEqual(final_registration["native_calls"][0]["callback_scope"], "ui")
                self.assertTrue(all(row["handoff_nonce"] == registration["nonce"]
                                    and row["callback_scope"] == "ui"
                                    for row in json.loads((output / "inbox-transport.json").read_text())["records"]))
                proof = report["root_transport_proofs"][0]
                resolved, _pins, capture_id = paths._validate_v3_resolution_report(
                    report, paths.ProcessIdentity(pid, creation, str(exe_path)), selected_names,
                    r"C:\Fixture\Main", int("123456789abc", 16),
                    (proof["path"], proof["bytes"], proof["sha256"]))
                self.assertEqual(resolved, (
                    r"C:\Resolved\WorldCongress.lua", r"C:\Resolved\bbg_script.lua"))
                self.assertEqual(capture_id, report["capture_id"])

                # A UI callback error must reach Lua.log and the producer must not replay it.
                modules[:] = [exe_module]
                failed_harness = _Harness(pid, creation, fail_first=True, lua_scope="ui")
                failed_folder = temp / "ui-failed-capture"
                with patch.object(producer, "TunerClient",
                                  side_effect=lambda **kwargs: _MenuTuner(failed_harness, kwargs["transcript"])):
                    failed_prepared = producer.prepare_at_menu(
                        template_path, template_sha, build_path, failed_folder, pid=pid)
                modules[:] = [exe_module, live_core]
                failed_inbox = temp / "FailedUIInbox" / "Civ6RLInbox.lua"
                failed_inbox.parent.mkdir()
                failed_inbox.write_bytes(b"previous failed UI inbox\n")
                failed_log = temp / "FailedUILua.log"
                failed_log.write_bytes(b"")
                failed_initial = failed_inbox.read_bytes()
                failed_stop = threading.Event()
                failed_seen = set()

                def watch_failed_ui_inbox():
                    while not failed_stop.is_set() and not failed_seen:
                        try:
                            raw = failed_inbox.read_bytes()
                            digest = hashlib.sha256(raw).hexdigest()
                            if raw != failed_initial and digest not in failed_seen:
                                failed_seen.add(digest)
                                failed_harness.set_scope("ui")
                                failed_harness.lines.clear()
                                failed_harness.lua.execute(raw.decode("ascii"))
                                with failed_log.open("ab") as stream:
                                    for line in failed_harness.lines:
                                        stream.write(line.encode("utf-8") + b"\n")
                        except Exception as exc:
                            watcher_error.append(exc)
                            return
                        time.sleep(0.01)

                failed_watcher = threading.Thread(target=watch_failed_ui_inbox, daemon=True)
                failed_watcher.start()
                with self.assertRaisesRegex(ValueError, "UI inbox callback failed"):
                    producer.capture_after_load(
                        Path(failed_prepared["registration"]["path"]), fresh_path, fresh_sha,
                        failed_inbox, failed_log, player_id=1, turn=17, timeout=3)
                failed_stop.set()
                failed_watcher.join(timeout=2)
                self.assertFalse(watcher_error)
                self.assertEqual(failed_inbox.read_bytes(), failed_initial)
                self.assertEqual(len(failed_harness.path_calls), 1)
                self.assertFalse((failed_folder / "report.json").exists())
                failed_transport = json.loads((failed_folder / "inbox-transport.json").read_text())
                self.assertIn(":false ", failed_transport["records"][0]["failure_result_line"])

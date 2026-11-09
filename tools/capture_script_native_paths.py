"""Resolve the exact selected Civ VI script names through the guarded native helper.

This producer is opt-in and single shot. It does not launch the game, inspect
script files, or retry a Tuner command whose outcome is uncertain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

from civ6_host.runtime import capture_script_paths as paths
from civ6_host.runtime.native import native_localization_export as export
from civ6_host.runtime.native.native_localization_query import _primary_tuner_owner
from civ6_host.runtime.native.tuner import TunerClient
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess


EXE_SHA = "d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe"
CORE_SHA = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
PROFILE_ID = "xp2-exe-current-d1a0-core-092abfbb-native-path"
UI_PROFILE_ID = "current-d1a0-official-script-path-ui-v1"
SELECTION_SHA = "b7a84db116b87f28890f89622553768c8024c2def153cf935df155ea09b7e0ca"
REPORT_SCHEMA = "civ6-host.official_script_path_resolutions.v1"
PREPARE_EXPORT = "civ6rl_localization_query_prepare"
RESOLVE_EXPORT = "civ6rl_official_script_path"
PREPARE_SCHEMA = "civ6rl.localization_query_preparation.v1"
RESPONSE_SCHEMA = "civ6-host.official_script_path_resolution.v1"
MAX_SELECTION_BYTES = 4 * 1024 * 1024
MAX_BUILD_BYTES = 4 * 1024 * 1024
UI_BUILD_PIN = ("work/official-capture/current-image-adapter/path-build-ui/official-script-path-build.json",
                9275, "a368d4d67e2d1bc808ad1bb6623fb876279456ca96425e49b6900033bfe5a08d")
UI_SOURCE_PIN = ("outputs/civ6-host/native/official_script_path_receipt.c",
                 7456, "1b7157269ce1b45c7d49df690715abb60dec83c63a0a32572247ebc9e742085d")
UI_MODULE_PIN = ("work/official-capture/current-image-adapter/path-build-ui/civ6rl-official-script-path.dll",
                 36352, "675adbb938a94b53e1fc569fd79d5d98c200047dc6dd9cfd4342ac229180579f")

RESPONSE_FIELDS = {
    "schema", "status", "nonce", "pid", "creation_filetime", "thread_id",
    "manager_address", "manager_vtable_rva", "method_rva", "capacity_utf16_units",
    "input_utf16le_hex", "output_utf16le_hex", "executable_sha256", "lua_scope",
    "lua_cs_owned", "native_method_called", "gamecore_function_called_by_helper",
    "output_file_opened_by_helper", "path_exists_checked",
    "exe_method_may_delegate_to_content_resolver",
    "nested_resolver_side_effects_asserted_absent",
}


def _strict_json(raw: bytes, label: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key in {label}")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON number in {label}")))


def _pin(path: Path, raw: bytes | None = None) -> dict:
    path = path.resolve(strict=True)
    if raw is None:
        raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _write_new(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")


def _check_build(build_path: Path):
    build_path = build_path.resolve(strict=True)
    build_pin = export.reference(build_path)
    raw = paths._read_bytes(str(build_path), "native script path build", limit=MAX_BUILD_BYTES)
    build = _strict_json(raw, "native script path build")
    abi = build.get("verified_current_abi", {})
    scope = build.get("lua_scope")
    if (build.get("schema") != "civ6-host.official_script_path_build.v1"
            or build.get("returncode") != 0
            or build.get("helper_loaded") is not False
            or build.get("game_invoked") is not False
            or build.get("native_method_called") is not False
            or build.get("source_overlay_from_query_build") is not True
            or abi.get("manager_global_rva") != hex(paths.CURRENT_SCRIPT_MANAGER_GLOBAL_RVA)
            or abi.get("manager_vtable_rva") != hex(paths.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA)
            or abi.get("slot_0x30_target_rva") != hex(paths.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)
            or abi.get("method_span", {}).get("sha256") != "5227bb0dfcd8a8fe71124d1f9f6ef7dd14d41f60d33a9a08e5d8dba3f26d4539"
            or abi.get("wfullpath_iat_rva") != "0xf985a0"
            or abi.get("wfullpath_import") != "api-ms-win-crt-filesystem-l1-1-0.dll!_wfullpath"):
        raise ValueError("Native path helper build profile differs")
    if scope == "root":
        paths._pin_native_asset(build_pin, "build")
    elif scope == "ui":
        if (build.get("execution_profile_id") != UI_PROFILE_ID
                or build.get("scope_contract", {}).get("prepare_scope") != "RootTunerMainState remains unchanged and owns the existing Lua CS preparation"
                or build.get("scope_contract", {}).get("only") != "UI Lua state for one bounded path-resolution receipt after explicit root preparation"
                or build.get("scope_contract", {}).get("guard") != "lua_scope_kind(L, exe, 0) validates exact UI-state identity and owned Lua critical section; Locale.Lookup/process/module/vtable guards remain exact"
                or Path(str(build_path)).as_posix().replace("\\", "/").endswith(UI_BUILD_PIN[0]) is False
                or (len(raw), build_pin["sha256"]) != UI_BUILD_PIN[1:]):
            raise ValueError("UI-scoped native path helper is not the exact reviewed build")
    else:
        raise ValueError("Native path helper has no explicitly admitted Lua scope")
    if scope == "root":
        source_tuple = paths._pin_native_asset(build["source"], "helper_source")
        source_pin = {"path": source_tuple[0], "bytes": source_tuple[1], "sha256": source_tuple[2]}
        module_pin = export.reference(Path(build["dll"]["path"]))
        paths._pin_native_asset(module_pin, "helper_module")
    else:
        source_pin = export.reference(Path(build["source"]["path"]))
        module_pin = export.reference(Path(build["dll"]["path"]))
        if (source_pin["bytes"], source_pin["sha256"]) != UI_SOURCE_PIN[1:] or not Path(source_pin["path"]).as_posix().replace("\\", "/").endswith(UI_SOURCE_PIN[0]):
            raise ValueError("UI helper source differs from its reviewed exact pin")
        if (module_pin["bytes"], module_pin["sha256"]) != UI_MODULE_PIN[1:] or not Path(module_pin["path"]).as_posix().replace("\\", "/").endswith(UI_MODULE_PIN[0]):
            raise ValueError("UI helper module differs from its reviewed exact pin")
    if ((source_pin["bytes"], source_pin["sha256"])
            != (build["source"]["bytes"], build["source"]["sha256"])
            or module_pin != build["dll"]):
        raise ValueError("Helper source or module bytes differ from the build receipt")
    evidence = build.get("source_evidence", [])
    live_row = next((row for row in evidence if Path(row.get("path", "")).as_posix().replace("\\", "/").endswith(paths.CURRENT_V3_LIVE_POINTER_PIN[0])), None)
    exe_row = next((row for row in evidence if Path(row.get("path", "")).name.casefold() == "civilizationvi.exe"), None)
    live = paths._read_file_pin(live_row, "native helper live-pointer evidence") if live_row else None
    if (live is None or live[1:] != paths.CURRENT_V3_LIVE_POINTER_PIN[1:]
            or type(exe_row) is not dict
            or (exe_row.get("bytes"), exe_row.get("sha256")) != (paths.CURRENT_EXE_SIZE_BYTES, EXE_SHA)):
        raise ValueError("Helper build current-image/live-pointer evidence differs")
    query_snapshots = [paths._read_file_pin(row, "native helper query snapshot")
                       for row in build.get("query_snapshots", [])]
    query_build = paths._read_file_pin(build.get("query_build"), "native helper query build")
    if (query_build[1:] != paths.CURRENT_V3_QUERY_BUILD_PIN[1:]
            or len(query_snapshots) != len(paths.CURRENT_V3_QUERY_SNAPSHOT_PINS)
            or any(actual[1:] != expected[1:]
                   for actual, expected in zip(query_snapshots, paths.CURRENT_V3_QUERY_SNAPSHOT_PINS, strict=True))):
        raise ValueError("Helper build localization query lineage differs")
    return build, build_pin, module_pin, source_pin


def _selection(selection_path: Path, expected_sha256: str):
    selection_path = selection_path.resolve(strict=True)
    raw = paths._read_bytes(str(selection_path), "pinned runtime selection", limit=MAX_SELECTION_BYTES)
    selection_pin = _pin(selection_path, raw)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or selection_pin["sha256"] != expected_sha256:
        raise ValueError("Runtime-selection JSON does not match the caller's exact file pin")
    document = _strict_json(raw, "runtime selection")
    try:
        captured = document["gameplay_selection994"]
        process = captured["process"]
        snapshot = captured["snapshot"]
        selected = snapshot["selected_paths"]
    except (TypeError, KeyError) as exc:
        raise ValueError("Runtime selection lacks the gameplay_selection994 capture") from exc
    if (captured.get("schema") != "civ6rl.official_gameplay_selection994.capture.v2"
            or captured.get("gamecore_module", {}).get("sha256") != CORE_SHA
            or snapshot.get("executable_sha256") != EXE_SHA
            or snapshot.get("current_correspondence_sha256") != SELECTION_SHA
            or type(selected) is not list or not selected or len(selected) > 1024):
        raise ValueError("Runtime selection does not match the current EXE/Core profile")
    paths._identity(process)
    for name in selected:
        paths._validate_selected_name(name)
    return document, captured, process, list(selected), selection_pin


def _lua_registration(build, identity, nonce):
    quote = export._lua_string
    path = quote(build["dll"]["path"])
    digest = quote(build["dll"]["sha256"])
    key = quote("Civ6RLOfficialScriptPath_" + build["dll"]["sha256"])
    prepare_nonce = nonce
    prefix = "CIV6RL_SCRIPT_PATH_PREPARED:" + nonce + ":"
    code = f'''local env=getfenv(1); assert(rawget(env,{key})==nil,"path helper already registered"); assert(package and type(package.loadlib)=="function","root loader unavailable"); local prepare,err=package.loadlib({path},{quote(PREPARE_EXPORT)}); assert(type(prepare)=="function",tostring(err)); local resolve,err=package.loadlib({path},{quote(RESOLVE_EXPORT)}); assert(type(resolve)=="function",tostring(err)); local receipt=prepare({quote(prepare_nonce)},{quote(str(identity["pid"]))},{quote(str(identity["creation_filetime"]))}); assert(type(receipt)=="string","preparation receipt missing"); rawset(env,{key},{{path={path},sha256={digest},resolve=resolve,pid={quote(str(identity["pid"]))},creation={quote(str(identity["creation_filetime"]))},prepare_nonce={quote(prepare_nonce)}}}); print({quote(prefix)}..receipt)'''
    return code, prefix, key


def _lua_resolve(build, identity, registration_nonce, name, nonce):
    quote = export._lua_string
    key = quote("Civ6RLOfficialScriptPath_" + build["dll"]["sha256"])
    prefix = "CIV6RL_SCRIPT_PATH_RESULT:" + nonce + ":"
    code = f'''local env=getfenv(1); local box=rawget(env,{key}); assert(type(box)=="table" and box.path=={quote(build["dll"]["path"])} and box.sha256=={quote(build["dll"]["sha256"])} and box.pid=={quote(str(identity["pid"]))} and box.creation=={quote(str(identity["creation_filetime"]))} and box.prepare_nonce=={quote(registration_nonce)} and type(box.resolve)=="function","registered path helper differs"); assert(Locale and type(Locale.Lookup)=="function","official Locale.Lookup unavailable"); local result=box.resolve({quote(name)},{quote(nonce)},{quote(str(identity["pid"]))},{quote(str(identity["creation_filetime"]))},Locale.Lookup); assert(type(result)=="string","native path helper returned no receipt"); print({quote(prefix)}..result)'''
    return code, prefix


def _parse_one(lines, prefix, label):
    if type(lines) is not list or len(lines) != 1 or type(lines[0]) is not str or not lines[0].startswith(prefix):
        raise ValueError(f"Unexpected {label} acknowledgement; outcome is not safe to replay")
    return _strict_json(lines[0][len(prefix):].encode("utf-8"), label)


def _validate_prepare(receipt, nonce):
    expected = {
        "schema": PREPARE_SCHEMA, "status": "ok", "nonce": nonce,
        "database_function_called": False, "module_file_pins_retained": True,
    }
    if type(receipt) is not dict or receipt != expected:
        raise ValueError("Native helper preparation receipt differs from the root-only contract")


def _validate_response(response, nonce, selected_name, identity, *, lua_scope="root"):
    if type(response) is not dict or set(response) != RESPONSE_FIELDS:
        raise ValueError("Native path response fields differ from the reviewed helper contract")
    expected = {
        "schema": RESPONSE_SCHEMA, "status": "ok", "nonce": nonce,
        "pid": identity["pid"], "creation_filetime": identity["creation_filetime"],
        "manager_vtable_rva": hex(paths.CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA),
        "method_rva": hex(paths.CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA),
        "capacity_utf16_units": 260, "executable_sha256": EXE_SHA,
        "lua_scope": lua_scope, "lua_cs_owned": True, "native_method_called": True,
        "gamecore_function_called_by_helper": False,
        "output_file_opened_by_helper": False, "path_exists_checked": False,
        "exe_method_may_delegate_to_content_resolver": True,
        "nested_resolver_side_effects_asserted_absent": False,
    }
    for key, value in expected.items():
        if response.get(key) != value:
            raise ValueError(f"Native path response {key} differs from the guarded profile")
    address = response.get("manager_address")
    if (type(address) is not str or not re.fullmatch(r"0x[0-9a-f]+", address)
            or not 0x10000 <= int(address, 16) < 2**47):
        raise ValueError("Native path response has no valid live manager address")
    if type(response.get("thread_id")) is not int or response["thread_id"] <= 0:
        raise ValueError("Native path response has no valid thread id")
    expected_input = (selected_name + "\0").encode("utf-16-le").hex()
    if response.get("input_utf16le_hex") != expected_input:
        raise ValueError("Native path response input differs from the exact selected name")
    paths._decode_native_utf16_path(response.get("output_utf16le_hex"), "native output")


def _module_set(process, selection, core_sha=CORE_SHA):
    identity_expected = selection.get("process", selection)
    identity = process.identity()
    if identity != {key: identity_expected[key] for key in ("pid", "creation_filetime", "image_path")}:
        raise ValueError("Runtime-selection identity no longer matches the live process")
    image_pin = export.reference(Path(identity["image_path"]))
    if image_pin["sha256"] != EXE_SHA:
        raise ValueError("Live EXE does not match the pinned current image")
    modules = process.modules()
    exe_path = Path(identity["image_path"]).resolve(strict=True)
    exe_modules = [row for row in modules if Path(row["path"]).resolve(strict=True) == exe_path]
    cores = [row for row in modules if row["name"].casefold().startswith("gamecore_")
             and row["name"].casefold().endswith(".dll")]
    if len(exe_modules) != 1 or len(cores) != 1:
        raise ValueError("Live EXE or GameCore module is missing or ambiguous")
    core_pin = export.reference(Path(cores[0]["path"]))
    if core_pin["sha256"] != core_sha:
        raise ValueError("Live GameCore does not match the pinned current image")
    if (selection.get("exe_module") is None or selection.get("gamecore_module") is None
            or not all(selection["exe_module"].get(key) == exe_modules[0].get(key)
                       for key in ("name", "base", "bytes"))
            or not all(selection["gamecore_module"].get(key) == cores[0].get(key)
                       for key in ("name", "base", "bytes"))
            or Path(selection["exe_module"].get("path", "")).resolve(strict=True) != exe_path
            or Path(selection["gamecore_module"].get("path", "")).resolve(strict=True)
                != Path(cores[0]["path"]).resolve(strict=True)):
        raise ValueError("Runtime-selection EXE/Core module inventory differs from the live process")
    return identity, exe_modules[0], {**cores[0], "sha256": core_pin["sha256"]}


def _root_event_registration_command(build, identity, registration_nonce, selected_names):
    quote = export._lua_string
    path = quote(build["dll"]["path"])
    digest = quote(build["dll"]["sha256"])
    key_value = "Civ6RLOfficialScriptPath_" + build["dll"]["sha256"]
    key = quote(key_value)
    event_name = "Civ6RL_OfficialScriptPathResolve_" + registration_nonce
    event = quote(event_name)
    prefix = "CIV6RL_SCRIPT_PATH_PREPARED:" + registration_nonce + ":"
    names = "{" + ",".join(quote(name) for name in selected_names) + "}"
    code = (f"-- helper_path={build['dll']['path']} helper_sha256={build['dll']['sha256']}\n"
            + f'''local env=getfenv(1); assert(rawget(env,{key})==nil,"path helper already registered"); assert(package and type(package.loadlib)=="function" and LuaEvents and Locale and type(Locale.Lookup)=="function","root loader/context unavailable"); local prepare,err=package.loadlib({path},{quote(PREPARE_EXPORT)}); assert(type(prepare)=="function",tostring(err)); local resolve,err=package.loadlib({path},{quote(RESOLVE_EXPORT)}); assert(type(resolve)=="function",tostring(err)); local receipt=prepare({quote(registration_nonce)},{quote(str(identity["pid"]))},{quote(str(identity["creation_filetime"]))}); assert(type(receipt)=="string","preparation receipt missing"); local root_lookup=Locale.Lookup; local event=LuaEvents[{event}]; assert(event and type(event.Add)=="function","root resolve event unavailable"); local expected={names}; local next_index=1; local seen={{}}; local pid={quote(str(identity["pid"]))}; local created={quote(str(identity["creation_filetime"]))}; local registration_nonce={quote(registration_nonce)}; local listener=function(box) assert(type(box)=="table" and box.registration_nonce==registration_nonce and box.pid==pid and box.creation==created and box.index+1==next_index and expected[next_index]==box.selected_name,"root path selection/order/process"); assert(type(box.nonce)=="string" and string.len(box.nonce)==32 and string.match(box.nonce,"^[0-9a-f]+$") and not seen[box.nonce],"root path nonce"); assert(box.response==nil and box.received==nil,"root path box reused"); seen[box.nonce]=true; local response=resolve(box.selected_name,box.nonce,pid,created,root_lookup); assert(type(response)=="string","root helper returned no response"); box.response=response; box.received=box.nonce; next_index=next_index+1 end; rawset(env,{key},{{path={path},sha256={digest},resolve=resolve,listener=listener,event=event,registration_nonce=registration_nonce,pid=pid,creation=created,selected_names=expected}}); event.Add(listener); print({quote(prefix)}..receipt)''')
    return code, prefix, key_value, event_name


def _ui_callback_registration_command(build, identity, registration_nonce, selected_names):
    """Prepare at root and register only a callback handoff for the later UI inbox."""
    quote = export._lua_string
    path = quote(build["dll"]["path"])
    digest = quote(build["dll"]["sha256"])
    key_value = "Civ6RLOfficialScriptPath_" + build["dll"]["sha256"]
    key = quote(key_value)
    event_name = "Civ6RL_OfficialScriptPathResolve_" + registration_nonce
    event = quote(event_name)
    prefix = "CIV6RL_SCRIPT_PATH_PREPARED:" + registration_nonce + ":"
    names = "{" + ",".join(quote(name) for name in selected_names) + "}"
    code = (f"-- helper_path={build['dll']['path']} helper_sha256={build['dll']['sha256']} scope=ui\n"
            + f'''local env=getfenv(1); assert(rawget(env,{key})==nil,"path helper already registered"); assert(package and type(package.loadlib)=="function" and LuaEvents,"root loader/context unavailable"); local prepare,err=package.loadlib({path},{quote(PREPARE_EXPORT)}); assert(type(prepare)=="function",tostring(err)); local resolve,err=package.loadlib({path},{quote(RESOLVE_EXPORT)}); assert(type(resolve)=="function",tostring(err)); local receipt=prepare({quote(registration_nonce)},{quote(str(identity["pid"]))},{quote(str(identity["creation_filetime"]))}); assert(type(receipt)=="string","preparation receipt missing"); local event=LuaEvents[{event}]; assert(event and type(event.Add)=="function","UI callback handoff event unavailable"); local expected={names}; local next_index=1; local seen={{}}; local pid={quote(str(identity["pid"]))}; local created={quote(str(identity["creation_filetime"]))}; local registration_nonce={quote(registration_nonce)}; local listener=function(box) assert(type(box)=="table" and box.registration_nonce==registration_nonce and box.pid==pid and box.creation==created and box.index+1==next_index and expected[next_index]==box.selected_name,"UI callback selection/order/process"); assert(type(box.nonce)=="string" and string.len(box.nonce)==32 and string.match(box.nonce,"^[0-9a-f]+$") and not seen[box.nonce],"UI callback nonce"); assert(box.callback==nil and box.received==nil and box.handoff_nonce==nil,"UI callback box reused"); seen[box.nonce]=true; box.callback=resolve; box.received=box.nonce; box.handoff_nonce=registration_nonce; next_index=next_index+1 end; rawset(env,{key},{{path={path},sha256={digest},resolve=resolve,listener=listener,event=event,registration_nonce=registration_nonce,pid=pid,creation=created,selected_names=expected,callback_scope="ui"}}); event.Add(listener); print({quote(prefix)}..receipt)''')
    return code, prefix, key_value, event_name


def prepare_at_menu(selection_path: Path, selection_sha256: str, build_path: Path,
                    output_folder: Path, *, timeout: float = 20.0, pid: int | None = None):
    """Load and prepare the guarded root callback once while primary Tuner is at the menu."""
    root = resource_root().resolve(strict=True)
    output_folder = output_folder.resolve()
    if not output_folder.is_relative_to(root / "work") or output_folder.exists():
        raise ValueError("Preparation requires a fresh folder beneath project work/")
    _document, selected_capture, selection_identity, selected_names, selection_pin = _selection(
        selection_path, selection_sha256)
    build, build_pin, module_pin, source_pin = _check_build(build_path)
    if pid is not None and (build["lua_scope"] != "ui" or type(pid) is not int or not 0 < pid < 2**32):
        raise ValueError("A PID template is admitted only for the exact UI-scoped helper profile")
    override_path = root / paths.CURRENT_OVERRIDE_BINDINGS_PATH
    override_raw = paths._read_bytes(str(override_path), "actual override proof")
    override_proof = _pin(override_path, override_raw)
    if (override_proof["bytes"] != paths.CURRENT_OVERRIDE_BINDINGS_BYTES
            or override_proof["sha256"] != paths.CURRENT_OVERRIDE_BINDINGS_SHA256):
        raise ValueError("Actual override proof differs from its exact current profile pin")
    output_folder.parent.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir()
    registration_path = output_folder / "root-registration.json"
    transcript = output_folder / "tuner.jsonl"
    registration_nonce = uuid.uuid4().hex
    registration = None
    try:
        process_pid = selection_identity["pid"] if pid is None else pid
        with ReadOnlyProcess(process_pid) as process:
            identity = process.identity()
            if pid is None and identity != selection_identity:
                raise ValueError("Runtime-selection identity no longer matches the live process")
            if pid is not None and (identity.get("pid") != pid
                    or not isinstance(identity.get("creation_filetime"), int)
                    or not isinstance(identity.get("image_path"), str)):
                raise ValueError("Requested menu-time PID identity is incomplete")
            image_pin = export.reference(Path(identity["image_path"]))
            if image_pin["sha256"] != EXE_SHA:
                raise ValueError("Menu-time EXE does not match the pinned current image")
            modules = process.modules()
            exe_path = Path(identity["image_path"]).resolve(strict=True)
            exe_rows = [row for row in modules if Path(row["path"]).resolve(strict=True) == exe_path]
            if len(exe_rows) != 1:
                raise ValueError("Menu-time EXE module is missing or ambiguous")
            exe_module = exe_rows[0]
            owner_before = _primary_tuner_owner(identity["pid"])
            if build["lua_scope"] == "root":
                transport = "root_event_via_ui_inbox"
                registration_schema = "civ6-host.official-script-path-root-registration.v2"
                code, prefix, environment_key, event_name = _root_event_registration_command(
                    build, identity, registration_nonce, selected_names)
            else:
                transport = "root_event_ui_callback_via_ui_inbox"
                registration_schema = "civ6-host.official-script-path-ui-registration.v1"
                code, prefix, environment_key, event_name = _ui_callback_registration_command(
                    build, identity, registration_nonce, selected_names)
            registration = {
                "schema": registration_schema,
                "transport": transport, "nonce": registration_nonce,
                "status": "pending", "process": identity,
                "selection": selection_pin, "menu_selection": selection_pin,
                "build": build_pin,
                "owner_before": owner_before, "owner_after": owner_before,
                "exe_module": exe_module, "gamecore_module": None,
                "command": code, "environment_key": environment_key,
                "event_name": event_name, "prepare_lines": [],
                "native_receipt": None, "helper_module": None,
                "root_state_index": None, "selected_names": selected_names,
                "records": [], "attempted_nonces": [], "native_calls": [],
                "records_completed": 0,
            }
            if build["lua_scope"] == "ui":
                registration.update(registration_scope="root", callback_scope="ui",
                                    execution_profile_id=UI_PROFILE_ID,
                                    menu_selection_role=("same_process" if pid is None else "expected_names_template"),
                                    template_process=selection_identity)
            _write_new(registration_path, registration)
            with TunerClient(port=4318, timeout=timeout, transcript=transcript) as tuner:
                root_index = tuner.state_index("Main State")
                lines = tuner.execute(code, context=root_index, timeout=timeout)
                registration["prepare_lines"] = lines
                registration["root_state_index"] = root_index
                _write_sidecar(registration_path, registration)
            receipt = _parse_one(lines, prefix, "root preparation")
            _validate_prepare(receipt, registration_nonce)
            helper_loaded = export._helper_module(process, build)
            if _primary_tuner_owner(identity["pid"]) != owner_before:
                raise ValueError("Primary Tuner owner changed during root preparation")
            if process.identity() != identity:
                raise ValueError("Process identity changed during root preparation")
            registration.update(status="prepared_at_menu", native_receipt=receipt,
                                helper_module=helper_loaded, root_state_index=root_index)
            _write_sidecar(registration_path, registration)
    except Exception as exc:
        if registration is not None:
            registration["status"] = "refused_or_uncertain"
            registration["error"] = type(exc).__name__ + ": " + str(exc)
            _write_sidecar(registration_path, registration)
        raise
    return {"registration": _pin(registration_path), "transcript": _pin(transcript),
            "event_name": event_name, "status": registration["status"],
            "training_ready": False}


def _script_path_inbox_command(registration, index, selected_name, nonce, player_id, turn):
    quote = export._lua_string
    marker = "CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + nonce + ":"
    result_marker = "CIV6RL_SCRIPT_PATH_INBOX_RESULT:" + nonce + ":"
    event = quote(registration["event_name"])
    registration_nonce = quote(registration["nonce"])
    process = registration["process"]
    if registration["transport"] == "root_event_via_ui_inbox":
        callback = f'''event.Call(box); assert(box.received=={quote(nonce)} and type(box.response)=="string","root path response missing"); local response=box.response'''
    elif registration["transport"] == "root_event_ui_callback_via_ui_inbox":
        callback = f'''event.Call(box); assert(box.received=={quote(nonce)} and box.handoff_nonce=={registration_nonce} and type(box.callback)=="function","UI callback handoff missing"); assert(Locale and type(Locale.Lookup)=="function","official UI Locale.Lookup unavailable"); local response=box.callback({quote(selected_name)},{quote(nonce)},{quote(str(process["pid"]))},{quote(str(process["creation_filetime"]))},Locale.Lookup); assert(type(response)=="string","UI path callback returned no response")'''
    else:
        raise ValueError("Unsupported script path inbox transport")
    code = f'''Civ6RL_Inbox={{transport_version=1,op="idle"}}\nif Civ6RL_OfficialScriptPathNonce~={quote(nonce)} then Civ6RL_OfficialScriptPathNonce={quote(nonce)}; local ok,result=pcall(function() assert(Game and Game.GetLocalPlayer and Game.GetCurrentGameTurn,"Game unavailable"); assert(Game.GetLocalPlayer()=={player_id} and Game.GetCurrentGameTurn()=={turn},"player/turn drift"); assert(UI and UI.IsGameCoreBusy and UI.IsGameCoreBusy()==false,"GameCore busy"); local box={{registration_nonce={registration_nonce},pid={quote(str(process["pid"]))},creation={quote(str(process["creation_filetime"]))},index={index},selected_name={quote(selected_name)},nonce={quote(nonce)}}}; local event=LuaEvents[{event}]; assert(event and type(event.Call)=="function","path callback event unavailable"); {callback}; assert(UI.IsGameCoreBusy()==false and Game.GetLocalPlayer()=={player_id} and Game.GetCurrentGameTurn()=={turn},"player/turn changed"); print({quote(marker)}..response); return "captured" end); print({quote(result_marker)}..tostring(ok).." "..tostring(result)) end\n'''.encode("ascii")
    return code, marker.encode("ascii"), result_marker.encode("ascii")


def _atomic_inbox_replace(inbox: Path, data: bytes, expected: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=inbox.parent, prefix=".civ6rl-script-path-", suffix=".tmp", delete=False) as stream:
        temp_path = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    deadline = time.monotonic() + 1.0
    try:
        while True:
            if inbox.read_bytes() != expected:
                raise ValueError("Another writer changed the mounted inbox")
            try:
                os.replace(temp_path, inbox)
                return
            except OSError as exc:
                if getattr(exc, "winerror", None) not in (5, 32, 33) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
    finally:
        temp_path.unlink(missing_ok=True)


class _InboxAckFailure(ValueError):
    def __init__(self, message, *, result_line=None):
        super().__init__(message)
        self.result_line = result_line


def _wait_inbox_ack(log: Path, offset: int, nonce: str, *, timeout: float = 25.0):
    ack_marker = ("CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + nonce + ":").encode("ascii")
    result_marker = ("CIV6RL_SCRIPT_PATH_INBOX_RESULT:" + nonce + ":").encode("ascii")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        before = log.stat()
        if before.st_size < offset:
            raise ValueError("Lua log was truncated during script path capture")
        if before.st_size - offset > 4 * 1024 * 1024:
            raise ValueError("Lua log output exceeded the bounded inbox acknowledgement window")
        with log.open("rb") as stream:
            stream.seek(offset)
            raw = stream.read(4 * 1024 * 1024 + 1)
        after = log.stat()
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Lua log acknowledgement window exceeded its bound")
        rows = raw.splitlines(keepends=True)
        decoded = [row.decode("utf-8", errors="replace").rstrip("\r\n") for row in rows]
        ack_indices = [i for i, row in enumerate(rows) if ack_marker in row]
        result_indices = [i for i, row in enumerate(rows) if result_marker in row]
        if ack_indices or result_indices:
            if len(result_indices) == 1 and not ack_indices:
                result_line = decoded[result_indices[0]]
                if not result_line.endswith("true captured"):
                    raise _InboxAckFailure("UI inbox callback failed: " + result_line,
                                           result_line=result_line)
            if len(ack_indices) != 1 or len(result_indices) != 1 or ack_indices[0] >= result_indices[0]:
                raise _InboxAckFailure("Inbox acknowledgement is missing or ambiguous",
                                       result_line=decoded[result_indices[0]] if len(result_indices) == 1 else None)
            ack_index, result_index = ack_indices[0], result_indices[0]
            ack_line, result_line = decoded[ack_index], decoded[result_index]
            if not ack_line.split(ack_marker.decode("ascii"), 1)[1].startswith("{\"schema\":"):
                raise ValueError("Root event response acknowledgement is malformed")
            if not result_line.endswith("true captured"):
                raise ValueError("UI inbox command did not complete the event call")
            source_offset = offset + sum(len(row) for row in rows[:ack_index])
            window = b"".join(rows[ack_index:result_index + 1])
            with log.open("rb") as stream:
                stream.seek(source_offset)
                live_slice = stream.read(len(window))
            final = log.stat()
            if (live_slice != window or before.st_dev != after.st_dev or before.st_ino != after.st_ino
                    or before.st_dev != final.st_dev or before.st_ino != final.st_ino):
                raise ValueError("Archived Lua log window differs from its live source slice")
            digest = hashlib.sha256(window).hexdigest()
            metadata = {
                "path": str(log), "file_device": int(final.st_dev), "file_id": int(final.st_ino),
                "size_before": int(before.st_size), "mtime_ns_before": int(before.st_mtime_ns),
                "size_after": int(final.st_size), "mtime_ns_after": int(final.st_mtime_ns),
                "offset": source_offset, "window_bytes": len(window), "window_sha256": digest,
                "live_slice_sha256": hashlib.sha256(live_slice).hexdigest(),
                "live_slice_matches": True,
            }
            return ack_line, result_line, window, metadata
        time.sleep(0.1)
    raise TimeoutError("Inbox path capture acknowledgement timed out; do not replay")


def capture_after_load(registration_path: Path, selection_path: Path, selection_sha256: str,
                       inbox_path: Path, log_path: Path, *, player_id: int, turn: int,
                       timeout: float = 25.0):
    """Call the prepared root listener from the mounted UI inbox, once per selected path."""
    root = resource_root().resolve(strict=True)
    registration_path = registration_path.resolve(strict=True)
    if not registration_path.is_relative_to(root / "work"):
        raise ValueError("Root registration must remain beneath project work/")
    folder = registration_path.parent
    report_path = folder / "report.json"
    inbox = Path(inbox_path).resolve(strict=True)
    log = Path(log_path).resolve(strict=True)
    if (report_path.exists() or inbox.name != "Civ6RLInbox.lua" or not inbox.is_file()
            or not log.is_file() or type(player_id) is not int or not 0 <= player_id < 64
            or type(turn) is not int or not 0 <= turn <= 1_000_000):
        raise ValueError("Invalid fresh output, mounted inbox/log, or expected player-turn boundary")
    paths._reject_reparse_components(inbox)
    paths._reject_reparse_components(log)
    registration_raw = paths._read_bytes(str(registration_path), "menu root registration", limit=MAX_BUILD_BYTES)
    registration = _strict_json(registration_raw, "menu root registration")
    if type(registration) is not dict or registration.get("status") != "prepared_at_menu":
        raise ValueError("No completed menu-time path callback preparation")
    _document, selected_capture, selection_identity, selected_names, selection_pin = _selection(
        selection_path, selection_sha256)
    if (registration.get("process") != selection_identity
            or registration.get("selected_names") != selected_names):
        raise ValueError("Fresh post-Load selection differs from the prepared process or ordered names")
    build_path = Path(registration["build"]["path"])
    build, build_pin, module_pin, source_pin = _check_build(build_path)
    if registration.get("build") != build_pin:
        raise ValueError("Prepared listener build pin changed")
    if build["lua_scope"] == "root":
        expected_transport = "root_event_via_ui_inbox"
        expected_registration_schema = "civ6-host.official-script-path-root-registration.v2"
        expected_inbox_schema = "civ6-host.official-script-path-inbox-transport.v1"
    else:
        expected_transport = "root_event_ui_callback_via_ui_inbox"
        expected_registration_schema = "civ6-host.official-script-path-ui-registration.v1"
        expected_inbox_schema = "civ6-host.official-script-path-ui-inbox-transport.v1"
    if (registration.get("transport") != expected_transport
            or registration.get("schema") != expected_registration_schema
            or (build["lua_scope"] == "ui" and (
                registration.get("registration_scope") != "root"
                or registration.get("callback_scope") != "ui"
                or registration.get("execution_profile_id") != UI_PROFILE_ID))):
        raise ValueError("Prepared callback transport does not match its exact helper scope")
    if build["lua_scope"] == "ui":
        menu_pin = registration.get("menu_selection")
        if not isinstance(menu_pin, dict) or set(menu_pin) != {"path", "bytes", "sha256"}:
            raise ValueError("UI registration has no exact pinned selected-name template")
        menu_path = Path(menu_pin["path"]).resolve(strict=True)
        menu_raw = paths._read_bytes(str(menu_path), "menu selected-name template", limit=MAX_SELECTION_BYTES)
        if _pin(menu_path, menu_raw) != menu_pin:
            raise ValueError("Menu selected-name template differs from its registration pin")
        menu_doc = _strict_json(menu_raw, "menu selected-name template")
        try:
            menu_capture = menu_doc["gameplay_selection994"]
            menu_identity = menu_capture["process"]
            menu_names = menu_capture["snapshot"]["selected_paths"]
        except (KeyError, TypeError) as exc:
            raise ValueError("UI menu template lacks process identity or selected names") from exc
        role = registration.get("menu_selection_role")
        if (menu_identity != registration.get("template_process")
                or menu_names != selected_names
                or role not in ("same_process", "expected_names_template")
                or (role == "same_process" and menu_identity != selection_identity)
                or (role == "expected_names_template"
                    and (menu_identity.get("image_path") != selection_identity["image_path"]
                         or menu_identity.get("pid") == selection_identity["pid"]))):
            raise ValueError("UI menu template role/process does not match the fresh post-Load selection")
    override_path = root / paths.CURRENT_OVERRIDE_BINDINGS_PATH
    override_raw = paths._read_bytes(str(override_path), "actual override proof")
    override_proof = _pin(override_path, override_raw)
    if (override_proof["bytes"] != paths.CURRENT_OVERRIDE_BINDINGS_BYTES
            or override_proof["sha256"] != paths.CURRENT_OVERRIDE_BINDINGS_SHA256):
        raise ValueError("Actual override proof differs from its exact current profile pin")
    if (registration.get("native_receipt") != {
            "schema": PREPARE_SCHEMA, "status": "ok", "nonce": registration.get("nonce"),
            "database_function_called": False, "module_file_pins_retained": True}
            or type(registration.get("nonce")) is not str
            or not re.fullmatch(r"[0-9a-f]{32}", registration["nonce"])
            or registration.get("owner_before") != registration.get("owner_after")):
        raise ValueError("Menu-time root preparation receipt is not qualified")
    transcript = folder / "tuner.jsonl"
    if not transcript.is_file():
        raise ValueError("Menu-time Tuner preparation transcript is missing")
    registration_pin = _pin(registration_path, registration_raw)
    transcript_pin = _pin(transcript)
    inbox_sidecar_path = folder / "inbox-transport.json"
    inbox_transport = {
        "schema": expected_inbox_schema,
        "registration": registration_pin, "process": registration["process"],
        "player_id": player_id, "turn": turn, "inbox_path": str(inbox),
        "log_source_path": str(log), "records": [], "inbox_restored": False,
    }
    if build["lua_scope"] == "ui":
        inbox_transport["transport"] = expected_transport
    command_dir = folder / "commands"
    log_window_dir = folder / "log-evidence"
    command_dir.mkdir(exist_ok=True)
    log_window_dir.mkdir(exist_ok=True)
    attempted: list[str] = []
    completed_records: list[dict] = []
    lock = inbox.with_suffix(".lua.lock")
    owns_lock = False
    with ReadOnlyProcess(selection_identity["pid"]) as process:
        identity, exe_module, core_module = _module_set(process, selected_capture)
        if identity != registration["process"]:
            raise ValueError("Process identity changed since menu preparation")
        registration["selection"] = selection_pin
        registration["exe_module"] = exe_module
        registration["gamecore_module"] = core_module
        helper_loaded = export._helper_module(process, build)
        if helper_loaded != registration.get("helper_module"):
            raise ValueError("Prepared helper module changed before Load capture")
        previous = None
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            owns_lock = True
            previous = inbox.read_bytes()
            for index, selected_name in enumerate(selected_names):
                nonce = uuid.uuid4().hex
                attempted.append(nonce)
                code, ack_marker, result_marker = _script_path_inbox_command(
                    registration, index, selected_name, nonce, player_id, turn)
                command_path = command_dir / f"path-{index:04d}-{nonce}.lua"
                with command_path.open("xb") as stream:
                    stream.write(code)
                    stream.flush()
                    os.fsync(stream.fileno())
                command_pin = _pin(command_path)
                inbox_record = {
                    "index": index, "selected_name": selected_name, "nonce": nonce,
                    "command_pin": command_pin, "log_offset": log.stat().st_size,
                    "inbox_before_sha256": hashlib.sha256(previous).hexdigest(),
                    "inbox_written_sha256": hashlib.sha256(code).hexdigest(),
                    "inbox_restored_sha256": None, "inbox_restored": False,
                }
                if build["lua_scope"] == "ui":
                    inbox_record.update(handoff_nonce=registration["nonce"], callback_scope="ui")
                inbox_transport["records"].append(inbox_record)
                _write_sidecar(inbox_sidecar_path, inbox_transport)
                _atomic_inbox_replace(inbox, code, previous)
                try:
                    ack_line, result_line, log_window, source_metadata = _wait_inbox_ack(
                        log, inbox_record["log_offset"], nonce, timeout=timeout)
                finally:
                    current = inbox.read_bytes()
                    if current == code:
                        _atomic_inbox_replace(inbox, previous, code)
                    restored = inbox.read_bytes() == previous
                    inbox_record["inbox_restored_sha256"] = hashlib.sha256(inbox.read_bytes()).hexdigest()
                    inbox_record["inbox_restored"] = restored
                    inbox_transport["inbox_restored"] = restored
                    _write_sidecar(inbox_sidecar_path, inbox_transport)
                if not restored:
                    raise ValueError("Mounted inbox was not restored to its exact previous bytes")
                log_window_path = log_window_dir / f"{index:04d}-{nonce}.logbytes"
                with log_window_path.open("xb") as stream:
                    stream.write(log_window)
                inbox_record.update(ack_line=ack_line, result_line=result_line,
                                    log_window=_pin(log_window_path),
                                    log_source_metadata=source_metadata)
                inbox_record["log_offset"] = source_metadata["offset"]
                marker = "CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + nonce + ":"
                ack_json = ack_line.split(marker, 1)[1]
                response = _strict_json(ack_json.encode("utf-8"), "path callback response")
                _validate_response(response, nonce, selected_name, identity,
                                   lua_scope=build["lua_scope"])
                if build["lua_scope"] == "ui":
                    inbox_transport["records"][-1]["handoff_nonce"] = registration["nonce"]
                    inbox_transport["records"][-1]["callback_scope"] = "ui"
                if export._helper_module(process, build) != helper_loaded:
                    raise ValueError("Prepared helper module changed after a root listener callback")
                completed_records.append({"selected_name": selected_name, "response": response})
                registration["attempted_nonces"] = list(attempted)
                registration["records"] = list(completed_records)
                registration["native_calls"] = [
                    {"index": row["index"], "selected_name": row["selected_name"],
                     "nonce": row["nonce"], "status": "ok",
                     "raw_lines": [row["ack_line"]], "response": record["response"]}
                    for row, record in zip(inbox_transport["records"], completed_records, strict=True)]
                if build["lua_scope"] == "ui":
                    for call in registration["native_calls"]:
                        call.update(handoff_nonce=registration["nonce"], callback_scope="ui")
                registration["records_completed"] = len(completed_records)
                inbox_transport["records"][-1]["ack_line"] = ack_line
                inbox_transport["records"][-1]["result_line"] = result_line
                inbox_transport["records"][-1]["log_window"] = _pin(log_window_path)
                inbox_transport["records"][-1]["log_source_metadata"] = source_metadata
                _write_sidecar(inbox_sidecar_path, inbox_transport)
                registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            if process.identity() != identity:
                raise ValueError("Process identity changed during inbox capture")
            final_modules = process.modules()
            if (exe_module not in final_modules or
                    {key: value for key, value in core_module.items() if key != "sha256"} not in final_modules
                    or export._helper_module(process, build) != helper_loaded):
                raise ValueError("A pinned EXE, GameCore, or helper module changed during capture")
            if (export.reference(Path(identity["image_path"]))["sha256"] != EXE_SHA
                    or export.reference(Path(core_module["path"]))["sha256"] != CORE_SHA):
                raise ValueError("Pinned EXE or GameCore bytes changed during inbox capture")
        except Exception as exc:
            inbox_transport["status"] = "refused_or_uncertain"
            inbox_transport["error"] = type(exc).__name__ + ": " + str(exc)
            if attempted and inbox_transport["records"]:
                result_line = getattr(exc, "result_line", None)
                if result_line is not None:
                    inbox_transport["records"][-1]["failure_result_line"] = result_line
            _write_sidecar(inbox_sidecar_path, inbox_transport)
            registration["status"] = "refused_or_uncertain"
            registration["attempted_nonces"] = attempted
            registration["records"] = completed_records
            registration["records_completed"] = len(completed_records)
            registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            raise
        finally:
            if owns_lock:
                lock.unlink(missing_ok=True)

    registration["status"] = "completed"
    registration["attempted_nonces"] = attempted
    registration["records"] = completed_records
    registration["native_calls"] = [
        {"index": row["index"], "selected_name": row["selected_name"],
         "nonce": row["nonce"], "status": "ok", "raw_lines": [row["ack_line"]],
         "response": record["response"]}
        for row, record in zip(inbox_transport["records"], completed_records, strict=True)]
    if build["lua_scope"] == "ui":
        for call in registration["native_calls"]:
            call.update(handoff_nonce=registration["nonce"], callback_scope="ui")
    registration["records_completed"] = len(completed_records)
    registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    inbox_transport["registration"] = _pin(registration_path)
    inbox_transport["inbox_restored"] = all(row["inbox_restored"] is True for row in inbox_transport["records"])
    if inbox_transport["inbox_restored"] is not True:
        raise ValueError("At least one per-call inbox restoration was not proven")
    _write_sidecar(inbox_sidecar_path, inbox_transport)
    report = {
        "schema": REPORT_SCHEMA, "status": "ok", "process": identity,
        "execution_profile": {"profile_id": UI_PROFILE_ID if build["lua_scope"] == "ui" else PROFILE_ID, "executable_sha256": EXE_SHA,
                              "runtime_gamecore_sha256": CORE_SHA,
                              "selection_source_sha256": SELECTION_SHA},
        "capture_id": uuid.uuid4().hex, "build": build_pin,
        "helper_module": module_pin, "helper_source": source_pin,
        "override_proof": override_proof, "records": completed_records,
        "root_transport_proofs": [selection_pin, _pin(registration_path),
                                   transcript_pin, _pin(inbox_sidecar_path)],
        "player_observation": False, "training_ready": False,
    }
    _write_new(report_path, report)
    return {"path": str(report_path), "bytes": report_path.stat().st_size,
            "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "records": len(completed_records), "training_ready": False}


def _write_sidecar(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def capture(selection_path: Path, selection_sha256: str, build_path: Path, output_folder: Path,
            *, timeout: float = 20.0):
    root = resource_root().resolve(strict=True)
    output_folder = output_folder.resolve()
    if not output_folder.is_relative_to(root / "work") or output_folder.exists():
        raise ValueError("Output must be a fresh folder beneath the configured project work directory")
    _, selected_capture, selection_process, selected_names, selection_pin = _selection(selection_path, selection_sha256)
    build, build_pin, module_pin, source_pin = _check_build(build_path)
    if build["lua_scope"] != "root":
        raise ValueError("Direct Tuner capture remains root-only; use the prepared UI-inbox mode for a UI helper")
    override_path = root / paths.CURRENT_OVERRIDE_BINDINGS_PATH
    override_raw = paths._read_bytes(str(override_path), "actual override proof")
    override_proof = _pin(override_path, override_raw)
    if (override_proof["bytes"] != paths.CURRENT_OVERRIDE_BINDINGS_BYTES
            or override_proof["sha256"] != paths.CURRENT_OVERRIDE_BINDINGS_SHA256):
        raise ValueError("Actual override proof differs from its exact current profile pin")

    output_folder.parent.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir()
    transcript = output_folder / "tuner.jsonl"
    registration_path = output_folder / "root-registration.json"
    registration_nonce = uuid.uuid4().hex
    registration = {
        "schema": "civ6-host.official-script-path-root-registration.v1",
        "nonce": registration_nonce, "status": "pending", "process": selection_process,
        "selection": selection_pin, "build": build_pin,
    }
    registration_saved = False
    try:
        with ReadOnlyProcess(selection_process["pid"]) as process:
            identity = process.identity()
            if identity != {key: selection_process[key] for key in ("pid", "creation_filetime", "image_path")}:
                raise ValueError("Runtime-selection identity no longer matches the live process")
            image_pin = export.reference(Path(identity["image_path"]))
            if image_pin["sha256"] != EXE_SHA:
                raise ValueError("Live EXE does not match the pinned current image")
            modules = process.modules()
            exe_path = Path(identity["image_path"]).resolve(strict=True)
            exe_modules = [row for row in modules if Path(row["path"]).resolve(strict=True) == exe_path]
            cores = [row for row in modules if row["name"].casefold().startswith("gamecore_")
                     and row["name"].casefold().endswith(".dll")]
            if len(exe_modules) != 1 or len(cores) != 1:
                raise ValueError("Live EXE or GameCore module is missing or ambiguous")
            core_pin = export.reference(Path(cores[0]["path"]))
            if core_pin["sha256"] != CORE_SHA:
                raise ValueError("Live GameCore does not match the pinned current image")
            def same_module(selected_row, live_row):
                return (type(selected_row) is dict
                        and all(selected_row.get(key) == live_row.get(key)
                                for key in ("name", "base", "bytes"))
                        and Path(selected_row.get("path", "")).resolve(strict=True)
                            == Path(live_row["path"]).resolve(strict=True))
            if (not same_module(selected_capture.get("gamecore_module"), cores[0])
                    or not same_module(selected_capture.get("exe_module"), exe_modules[0])):
                raise ValueError("Runtime selection module bases differ from the live module inventory")
            owner_before = _primary_tuner_owner(identity["pid"])
            registration.update(process=identity, owner_before=owner_before,
                                exe_module=exe_modules[0], gamecore_module={**cores[0], "sha256": core_pin["sha256"]})
            code, prefix, key = _lua_registration(build, identity, registration_nonce)
            registration.update(command=code, environment_key=key)
            _write_new(registration_path, registration)
            registration_saved = True
            with TunerClient(port=4318, timeout=timeout, transcript=transcript) as tuner:
                root_index = tuner.state_index("Main State")
                lines = tuner.execute(code, context=root_index, timeout=timeout)
                registration["prepare_lines"] = lines
                registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            receipt = _parse_one(lines, prefix, "root preparation")
            _validate_prepare(receipt, registration_nonce)
            registration.update(status="prepared", native_receipt=receipt,
                                helper_module=export._helper_module(process, build), root_state_index=root_index)
            registration["records"] = []
            registration["attempted_nonces"] = []
            registration["native_calls"] = []
            registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            records = []
            nonces = {registration_nonce}
            manager_address = None
            # One Tuner command per exact ordered name; a failure ends this capture.
            with TunerClient(port=4318, timeout=timeout, transcript=transcript) as tuner:
                if tuner.state_index("Main State") != root_index:
                    raise ValueError("Main State index changed after helper registration")
                for index, selected_name in enumerate(selected_names):
                    nonce = uuid.uuid4().hex
                    while nonce in nonces:
                        nonce = uuid.uuid4().hex
                    nonces.add(nonce)
                    registration["attempted_nonces"].append(nonce)
                    native_call = {"index": index, "selected_name": selected_name,
                                   "nonce": nonce, "status": "pending"}
                    registration["native_calls"].append(native_call)
                    registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
                    if export._helper_module(process, build) != registration["helper_module"]:
                        raise ValueError("Pinned helper module changed before a path callback")
                    code, prefix = _lua_resolve(build, identity, registration_nonce, selected_name, nonce)
                    lines = tuner.execute(code, context=root_index, timeout=timeout)
                    native_call["raw_lines"] = lines
                    registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
                    response = _parse_one(lines, prefix, "native path resolution")
                    _validate_response(response, nonce, selected_name, identity)
                    if export._helper_module(process, build) != registration["helper_module"]:
                        raise ValueError("Pinned helper module changed after a path callback")
                    if manager_address is None:
                        manager_address = response["manager_address"]
                    elif response["manager_address"] != manager_address:
                        raise ValueError("Native ScriptManager address changed within the ordered selection")
                    records.append({"selected_name": selected_name, "response": response})
                    native_call["response"] = response
                    native_call["status"] = "ok"
                    registration["records"] = records
                    registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            if identity != process.identity():
                raise ValueError("Process identity changed during path capture")
            final_modules = process.modules()
            if (exe_modules[0] not in final_modules or cores[0] not in final_modules
                    or export._helper_module(process, build) != registration["helper_module"]):
                raise ValueError("A pinned EXE, GameCore, or helper module changed during path capture")
            if (export.reference(Path(identity["image_path"]))["sha256"] != EXE_SHA
                    or export.reference(Path(cores[0]["path"]))["sha256"] != CORE_SHA):
                raise ValueError("Pinned EXE or GameCore file bytes changed during path capture")
            if _primary_tuner_owner(identity["pid"]) != owner_before:
                raise ValueError("Primary Tuner owner changed during path capture")
            registration["owner_after"] = owner_before
            registration["records_completed"] = len(records)
            registration["status"] = "completed"
            registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    except Exception as exc:
        if registration_saved:
            # Preserve the command and any received acknowledgement; never replay.
            registration["status"] = "refused_or_uncertain"
            registration["error"] = type(exc).__name__ + ": " + str(exc)
            registration_path.write_text(json.dumps(registration, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        raise

    registration_pin = _pin(registration_path)
    transcript_pin = _pin(transcript)
    report = {
        "schema": REPORT_SCHEMA, "status": "ok", "process": identity,
        "execution_profile": {
            "profile_id": PROFILE_ID, "executable_sha256": EXE_SHA,
            "runtime_gamecore_sha256": CORE_SHA, "selection_source_sha256": SELECTION_SHA,
        },
        "capture_id": uuid.uuid4().hex, "build": build_pin,
        "helper_module": module_pin, "helper_source": source_pin,
        "override_proof": override_proof,
        "records": records,
        "root_transport_proofs": [selection_pin, registration_pin, transcript_pin],
        "player_observation": False, "training_ready": False,
    }
    report_path = output_folder / "report.json"
    _write_new(report_path, report)
    return {"path": str(report_path), "bytes": report_path.stat().st_size,
            "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "records": len(records), "training_ready": False}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    modes = {"prepare-at-menu", "capture-after-load"}
    if argv and argv[0] in modes:
        parser = argparse.ArgumentParser(description=__doc__)
        subparsers = parser.add_subparsers(dest="mode", required=True)
        prep = subparsers.add_parser("prepare-at-menu", help="Prepare the root listener at the menu via primary Tuner")
        prep.add_argument("selection", type=Path, help="Pinned runtime selection used only for identity and expected name order")
        prep.add_argument("--selection-sha256", required=True)
        prep.add_argument("--build", type=Path, required=True)
        prep.add_argument("--output-folder", type=Path, required=True)
        prep.add_argument("--timeout", type=float, default=20.0)
        prep.add_argument("--pid", type=int,
                          help="For the exact UI helper only, use this live menu PID with the pinned selection as a names/order template")
        after = subparsers.add_parser("capture-after-load", help="Capture through the mounted UI inbox after Load")
        after.add_argument("registration", type=Path)
        after.add_argument("selection", type=Path, help="Fresh runtime selection from the post-Load process")
        after.add_argument("--selection-sha256", required=True)
        after.add_argument("--inbox", type=Path, required=True)
        after.add_argument("--log", type=Path, required=True)
        after.add_argument("--player-id", type=int, required=True)
        after.add_argument("--turn", type=int, required=True)
        after.add_argument("--timeout", type=float, default=25.0)
        args = parser.parse_args(argv)
        if args.mode == "prepare-at-menu":
            if not (0 < args.timeout <= 30):
                raise ValueError("Tuner command timeout must be positive and at most 30 seconds")
            result = prepare_at_menu(args.selection, args.selection_sha256, args.build,
                                     args.output_folder, timeout=args.timeout, pid=args.pid)
        else:
            if not (0 < args.timeout <= 120):
                raise ValueError("Inbox capture timeout must be positive and at most 120 seconds")
            result = capture_after_load(args.registration, args.selection,
                                       args.selection_sha256, args.inbox, args.log,
                                       player_id=args.player_id, turn=args.turn,
                                       timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=True))
        return
    # Preserve the previous one-stage direct-primary-Tuner invocation.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", type=Path, help="Pinned runtime-selections-before.json")
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--build", type=Path, required=True, help="Reviewed root-only helper build receipt")
    parser.add_argument("--output-folder", type=Path, required=True, help="New folder beneath project work/")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)
    if not (0 < args.timeout <= 30):
        raise ValueError("Tuner command timeout must be positive and at most 30 seconds")
    print(json.dumps(capture(args.selection, args.selection_sha256, args.build,
                             args.output_folder, timeout=args.timeout), ensure_ascii=True))


if __name__ == "__main__":
    main()

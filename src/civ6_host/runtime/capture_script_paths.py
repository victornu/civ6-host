"""Validate and resolve selected GameplayScripts paths from a pinned capture witness.

It uses only the supplied process/CWD observer and the exact selected-to-resolved
mapping captured by the official process. It never searches for a file or rewrites
the original selected name.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import ntpath
import os
import re
import stat
import struct
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.paths import resource_root

SCHEMA = "civ6-host.official-script-path-base.v1"
CURRENT_SCHEMA = "civ6-host.official-script-path-current.v2"
STATUS = "same_process_cwd_and_native_path_copy_service_observed"
MAX_UTF16_UNITS = 259  # reserve one of the native 0x104 units for NUL
MAX_WITNESS_BYTES = 256 * 1024
MAX_PROOF_BYTES = 4 * 1024 * 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_BYTES = 128 * 1024 * 1024
MAX_SELECTION_BYTES = 4 * 1024 * 1024
REPARSE_POINT = 0x400

# Source-backed Path_Redirector contract from the retained Phase 42 EXE record.
PHASE42_SCHEMA = "civ6rl.phase42.map_setup.v1"
PHASE42_SHA256 = "47fd60ba8222c43436a07ec1e0919673d797cf1e095a48202a0f9a2512a3535c"
EXE_SHA256 = "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63"
XP2_SHA256 = "324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c"
EXE_IMAGE_BASE = 0x140000000
PATH_SINGLETON_GLOBAL_VA = 0x143586CC8
PATH_VTABLE_VA = 0x1411434E8
PATH_METHOD_VA = 0x140F1C820
PATH_VTABLE_ENTRIES = (0x140F1C730, 0x140F1C7D0, PATH_METHOD_VA)
CURRENT_PROFILE_ID = "xp2-exe-current-d1a0-core-092abfbb"
CURRENT_EXE_SHA256 = "d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe"
CURRENT_CORE_SHA256 = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
CURRENT_SELECTION_SOURCE_SHA256 = "b7a84db116b87f28890f89622553768c8024c2def153cf935df155ea09b7e0ca"
CURRENT_REFERENCE_CORE_SHA256 = XP2_SHA256
CURRENT_EXE_IMAGE_BASE = 0x140000000
CURRENT_EXE_SIZE_BYTES = 21189480
CURRENT_BINDINGS_PATH = "work/official-capture/current-exe-script-path-bindings.json"
CURRENT_BINDINGS_BYTES = 29459
CURRENT_BINDINGS_SHA256 = "7c426bd1d3d6a7e70338e85ad65a195c554f51e989a2d53ff3919ca250a1cd76"
CURRENT_SINGLETON_GLOBAL_RVA = 0x3587CC8
CURRENT_VTABLE_RVA = 0x1144548
CURRENT_METHOD_RVA = 0xF1C1F0
CURRENT_CALLER_BINDINGS_PATH = "work/official-capture/current-exe-script-path-caller-bindings.json"
CURRENT_CALLER_BINDINGS_BYTES = 53579
CURRENT_CALLER_BINDINGS_SHA256 = "8930fc441144aedcc6e7eea0b9fa4f87f26e40130eb119e01d039e1e4b8a22f5"
CURRENT_OVERRIDE_BINDINGS_PATH = "work/official-capture/current-exe-script-path-actual-override.json"
CURRENT_OVERRIDE_BINDINGS_BYTES = 13049
CURRENT_OVERRIDE_BINDINGS_SHA256 = "6464042b43fe53dc4a04eec78b64ba9bc1ec71e912f9d0bb517b10953946a4c3"
CURRENT_V3_PROFILE_ID = "xp2-exe-current-d1a0-core-092abfbb-script-path-v3"
CURRENT_V3_SCHEMA = "civ6-host.official-script-path-current.v3"
CURRENT_V3_STATUS = "native_current_exe_script_path_resolution_observed"
CURRENT_V3_REPORT_SCHEMA = "civ6-host.official_script_path_resolutions.v1"
CURRENT_V3_REPORT_STATUS = "ok"
CURRENT_V3_UI_PROFILE_ID = "current-d1a0-official-script-path-ui-v1"
CURRENT_V3_ASSET_PINS: dict[str, tuple[str | None, int | None, str | None]] = {
    "build": ("work/official-capture/current-image-adapter/path-build-root/official-script-path-build.json",
              8106, "e73c5c3214036812d2ce23e1c0dc2d3aa370d4e5bb0c91faac121762fe623c2e"),
    "helper_module": ("work/official-capture/current-image-adapter/path-build-root/civ6rl-official-script-path.dll",
                      36352, "93cbb58274b227ff06494d4caca42232c20fc13e6e7bde23ae873e2488c1c701"),
    "helper_source": ("work/official-capture/current-image-adapter/path-build-root/official_script_path_receipt.c",
                      7408, "d45564bb2e2b934f150c1b2f0848de25dcc35ad8f761862a5ad867f78cd478ad"),
}
CURRENT_V3_UI_ASSET_PINS: dict[str, tuple[str | None, int | None, str | None]] = {
    "build": ("work/official-capture/current-image-adapter/path-build-ui/official-script-path-build.json",
              9275, "a368d4d67e2d1bc808ad1bb6623fb876279456ca96425e49b6900033bfe5a08d"),
    "helper_module": ("work/official-capture/current-image-adapter/path-build-ui/civ6rl-official-script-path.dll",
                      36352, "675adbb938a94b53e1fc569fd79d5d98c200047dc6dd9cfd4342ac229180579f"),
    "helper_source": ("native/official_script_path_receipt.c",
                      7456, "1b7157269ce1b45c7d49df690715abb60dec83c63a0a32572247ebc9e742085d"),
}
CURRENT_V3_UI_PREVIOUS_ROOT_SOURCE_PIN = (
    "work/official-capture/current-image-adapter/path-build-root/official_script_path_receipt.c", 7408,
    "d45564bb2e2b934f150c1b2f0848de25dcc35ad8f761862a5ad867f78cd478ad",
)
CURRENT_V3_UI_PREVIOUS_ROOT_BUILD_PIN = (
    "work/official-capture/current-image-adapter/path-build-root/official-script-path-build.json",
    8106, "e73c5c3214036812d2ce23e1c0dc2d3aa370d4e5bb0c91faac121762fe623c2e",
)
CURRENT_V3_UI_PREVIOUS_ROOT_DLL_PIN = (
    "work/official-capture/current-image-adapter/path-build-root/civ6rl-official-script-path.dll",
    36352, "93cbb58274b227ff06494d4caca42232c20fc13e6e7bde23ae873e2488c1c701",
)
CURRENT_V3_ROOT_ORIGINAL_SOURCE_PATH = "native/official_script_path_receipt.c"
CURRENT_V3_QUERY_BUILD_PIN = (
    "work/official-capture/current-image-adapter/path-build-root/build.json",
    25692, "07036e5ce7821963e12857320877f70280e29992af13abadf39cad0d35876069",
)
CURRENT_V3_QUERY_SNAPSHOT_PINS = (
    ("work/official-capture/current-image-adapter/path-build-root/localization_query.c",
     13646, "a4b6ff5342bacffef1c196bd401d55eb05b0350787dcf469cfaa2989cf536f61"),
    ("work/official-capture/current-image-adapter/path-build-root/localization-export.c",
     20869, "b57fa042564b5798310ccbe5fa4548d52a79418c166e23fa51b11a4d38a8f5bb"),
)
CURRENT_V3_LIVE_POINTER_PIN = (
    "work/official-capture/bbg751-world-A-current-invocation/script-manager-live-pointers.json",
    1136, "47333ae6cdfb6715c14dcace1d054a310ba523588386b9d9d8d323222bbd49c2",
)
CURRENT_SCRIPT_MANAGER_GLOBAL_RVA = 0x2D09F88
CURRENT_SCRIPT_MANAGER_VTABLE_RVA = 0x1062FD0
CURRENT_SCRIPT_MANAGER_SLOT_OFFSET = 0x30
CURRENT_SCRIPT_MANAGER_WRAPPER_RVA = 0x972BC0
CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA = 0xFEAD18
CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA = 0x4D4510


class ScriptPathError(ValueError):
    """The witness, process observation, source mapping, or resolved path is invalid."""


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    creation_filetime: int
    image_path: str


@dataclass(frozen=True)
class ScriptSource:
    selected_name: str
    resolved_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class ScriptPathContext:
    witness_sha256: str
    process_identity: ProcessIdentity
    cwd: str
    selected_order: tuple[str, ...]
    source_by_selected: Mapping[str, ScriptSource]
    proof_files: tuple[tuple[str, int, str], ...]
    source_files: tuple[ScriptSource, ...]
    profile_id: str = "xp2-exe-phase42-base"
    exe_base: int = EXE_IMAGE_BASE
    resolver_singleton: int = 0
    script_manager: int = 0
    script_manager_vtable: int = 0
    script_manager_slot_30: int = 0
    execution_proven: bool = False
    load_admitted: bool = False


@dataclass(frozen=True)
class ResolvedScriptPath:
    selected_name: str
    resolved_path: Path
    bytes: int
    sha256: str

    def __fspath__(self) -> str:
        return os.fspath(self.resolved_path)


def _strict_int(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ScriptPathError(f"{label} must be an integer in the allowed range")
    return value


def _identity(value: Any) -> ProcessIdentity:
    if isinstance(value, ProcessIdentity):
        result = value
    elif isinstance(value, Mapping):
        try:
            result = ProcessIdentity(
                _strict_int(value["pid"], "process PID", minimum=1, maximum=0xFFFFFFFF),
                _strict_int(value["creation_filetime"], "process creation FILETIME", minimum=1),
                value["image_path"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ScriptPathError("process identity must include pid, creation_filetime, image_path") from exc
    else:
        try:
            result = ProcessIdentity(
                _strict_int(value.pid, "process PID", minimum=1, maximum=0xFFFFFFFF),
                _strict_int(value.creation_filetime, "process creation FILETIME", minimum=1),
                value.image_path,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ScriptPathError("unsupported process identity value") from exc
    if (type(result.pid) is not int or type(result.creation_filetime) is not int
            or not isinstance(result.image_path, str) or not result.image_path):
        raise ScriptPathError("process identity fields must be nonempty and positive")
    _validate_absolute_local(result.image_path, "process image path")
    return result


def _is_unc(path: str) -> bool:
    return path.startswith(("\\\\", "//")) or PureWindowsPath(path).drive.startswith("\\")


def _qualified_absolute(path: str) -> bool:
    if not path or "\0" in path or _is_unc(path):
        return False
    wp = PureWindowsPath(path)
    if os.name == "nt":
        return bool(wp.drive and wp.root)
    if wp.drive and wp.root:
        return True
    return os.path.isabs(path) and not wp.drive


def _validate_absolute_local(path: str, label: str) -> str:
    if not _qualified_absolute(path):
        raise ScriptPathError(f"{label} must be an absolute, qualified local path")
    return path


def expected_module_address(va: int, *, module_base: int = EXE_IMAGE_BASE,
                            image_base: int = EXE_IMAGE_BASE) -> int:
    """Translate a pinned EXE VA to the runtime address for its loaded image."""
    return module_base + (va - image_base)


def _read_file_pin(row: Mapping[str, Any], label: str) -> tuple[str, int, str]:
    if not isinstance(row, Mapping) or set(row) != {"path", "bytes", "sha256"}:
        raise ScriptPathError(f"{label} must be an explicit path/bytes/sha256 pin")
    try:
        path = row["path"]
        expected_bytes = row["bytes"]
        expected_sha = row["sha256"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ScriptPathError(f"{label} pin is incomplete") from exc
    if not isinstance(path, str) or not isinstance(expected_sha, str):
        raise ScriptPathError(f"{label} path and SHA-256 must be strings")
    _validate_absolute_local(path, f"{label} path")
    _strict_int(expected_bytes, f"{label} byte count", minimum=0, maximum=MAX_PROOF_BYTES)
    expected_sha = expected_sha.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ScriptPathError(f"{label} byte count or SHA-256 is invalid")
    from civ6_host.runtime.script_observer_sources import retained_observer_path
    physical = retained_observer_path(path, expected_bytes, expected_sha) if label == 'observer' else path
    raw = _read_bytes(physical, label, limit=MAX_PROOF_BYTES)
    if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ScriptPathError(f"{label} no longer matches its pinned size and SHA-256")
    return path, expected_bytes, expected_sha


def _read_bytes(path: str, label: str, *, limit: int = MAX_PROOF_BYTES) -> bytes:
    from civ6_host.runtime.resource_resolution import resolve_path
    physical = resolve_path(Path(path))
    _reject_reparse_components(physical)
    try:
        with physical.open("rb") as stream:
            raw = stream.read(limit + 1)
    except OSError as exc:
        raise ScriptPathError(f"cannot read pinned {label}") from exc
    if len(raw) > limit:
        raise ScriptPathError(f"pinned {label} exceeds the bounded read limit")
    return raw


def _load_witness(pin: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(pin, Mapping) or set(pin) != {"path", "bytes", "sha256"}:
        raise ScriptPathError("pinned_witness must be an explicit {path, bytes, sha256} pin")
    path, expected_bytes, expected_sha = pin["path"], pin["bytes"], pin["sha256"]
    if not isinstance(path, str) or not isinstance(expected_sha, str):
        raise ScriptPathError("witness pin path and SHA-256 must be strings")
    expected_bytes = _strict_int(expected_bytes, "witness byte count", minimum=1, maximum=MAX_WITNESS_BYTES)
    expected_sha = expected_sha.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ScriptPathError("witness pin SHA-256 is invalid")
    _validate_absolute_local(path, "path-base witness path")
    raw = _read_bytes(path, "path-base witness", limit=MAX_WITNESS_BYTES)
    if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ScriptPathError("path-base witness differs from its caller pin")
    try:
        witness = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScriptPathError("path-base witness is not valid JSON") from exc
    if not isinstance(witness, dict):
        raise ScriptPathError("path-base witness root must be an object")
    return witness, hashlib.sha256(raw).hexdigest()


def _cwd_join(cwd: str, selected_name: str) -> str:
    if PureWindowsPath(selected_name).is_absolute():
        return ntpath.normpath(selected_name)
    wp_cwd = PureWindowsPath(cwd)
    if wp_cwd.drive and wp_cwd.root:
        return ntpath.normpath(ntpath.join(cwd, selected_name.replace("/", "\\")))
    native_name = selected_name.replace("\\", os.sep).replace("/", os.sep)
    return os.path.normpath(os.path.join(cwd, native_name))


def _validate_selected_name(value: Any) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ScriptPathError("selected script name must be a nonempty string")
    win = PureWindowsPath(value)
    absolute = bool(re.match(r"^[A-Za-z]:[/\\]", value)) and win.is_absolute()
    if _is_unc(value) or ((win.drive or win.root or os.path.isabs(value)) and not absolute):
        raise ScriptPathError("selected script name must be relative or a drive-qualified local path")
    if (":" in (value[2:] if absolute else value)
            or (absolute and ".." in win.parts)):
        raise ScriptPathError("selected script path contains an alternate stream or parent segment")
    units = len(value.encode("utf-16-le")) // 2
    if units > MAX_UTF16_UNITS:
        raise ScriptPathError("selected script name exceeds the native UTF-16 path bound")
    return value


def _utf16_bound(path: str) -> None:
    if len(path.encode("utf-16-le")) // 2 > MAX_UTF16_UNITS:
        raise ScriptPathError("resolved script path exceeds the native UTF-16 path bound")


def _file_digest(path: Path) -> tuple[int, str]:
    if not path.is_file():
        raise ScriptPathError("resolved source is missing or is not a regular file")
    try:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
                size += len(block)
                if size > MAX_SOURCE_BYTES:
                    raise ScriptPathError("resolved source exceeds the bounded source-file limit")
        return size, digest.hexdigest()
    except OSError as exc:
        raise ScriptPathError("cannot verify resolved source bytes") from exc


def _image_digest(path: Path) -> tuple[int, str]:
    """Hash a bounded image file without applying the smaller Lua-source limit."""
    if not path.is_file():
        raise ScriptPathError("pinned image is missing or is not a regular file")
    try:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
                size += len(block)
                if size > MAX_IMAGE_BYTES:
                    raise ScriptPathError("pinned image exceeds the bounded image-file limit")
        return size, digest.hexdigest()
    except OSError as exc:
        raise ScriptPathError("cannot verify pinned image bytes") from exc


def _reject_reparse_components(path: Path) -> None:
    """Reject symlinks and Windows reparse points in every existing path component."""
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    cursor = Path(absolute.anchor)
    for part in parts[1:]:
        cursor = cursor / part
        try:
            info = cursor.lstat()
        except OSError as exc:
            raise ScriptPathError("resolved path has a missing or unreadable component") from exc
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & REPARSE_POINT:
            raise ScriptPathError("resolved path contains a symlink or reparse component")


def _within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((os.path.normcase(path), os.path.normcase(root))) == os.path.normcase(root)
    except ValueError:
        # Different Windows drives cannot be under one another.
        return False


def _pin_native_asset(row: Any, label: str, *, scope: str = "root") -> tuple[str, int, str]:
    pins = CURRENT_V3_UI_ASSET_PINS if scope == "ui" else CURRENT_V3_ASSET_PINS
    expected_path, expected_bytes, expected_sha = pins[label]
    if expected_path is None or expected_bytes is None or expected_sha is None:
        raise ScriptPathError("v3 helper build/module/source identity pins are not installed")
    if scope == "root" and label == "helper_source":
        if not isinstance(row, Mapping) or set(row) != {"path", "bytes", "sha256"}:
            raise ScriptPathError("root helper source pin is incomplete")
        path = row["path"]
        if (not isinstance(path, str)
                or not (Path(path).as_posix().replace("\\", "/").endswith(expected_path)
                        or Path(path).as_posix().replace("\\", "/").endswith(
                            CURRENT_V3_ROOT_ORIGINAL_SOURCE_PATH))
                or row["bytes"] != expected_bytes or row["sha256"] != expected_sha):
            raise ScriptPathError("root helper source pin differs from the archived root-scope source")
        archive_path = resource_root() / expected_path
        archive_pin = _read_file_pin({"path": str(archive_path), "bytes": expected_bytes,
                                      "sha256": expected_sha}, "archived root helper source")
        return archive_pin
    pin = _read_file_pin(row, label)
    if (Path(pin[0]).as_posix().replace("\\", "/").endswith(expected_path) is False
            or pin[1:] != (expected_bytes, expected_sha)):
        raise ScriptPathError(f"v3 {label} pin differs from the reviewed helper delivery")
    return pin


def _decode_native_utf16_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1040 or len(value) % 4:
        raise ScriptPathError(f"native {label} must be bounded lowercase UTF-16LE hex")
    if not re.fullmatch(r"(?:[0-9a-f]{4})+", value):
        raise ScriptPathError(f"native {label} contains noncanonical UTF-16LE hex")
    raw = bytes.fromhex(value)
    if len(raw) > 520:
        raise ScriptPathError(f"native {label} exceeds the 260-unit buffer")
    units = struct.unpack("<" + "H" * (len(raw) // 2), raw)
    if units[-1] != 0 or 0 in units[:-1]:
        raise ScriptPathError(f"native {label} must have one terminal NUL and no embedded NUL")
    try:
        decoded = raw[:-2].decode("utf-16-le", errors="strict")
    except UnicodeDecodeError as exc:
        raise ScriptPathError(f"native {label} is not well-formed UTF-16LE") from exc
    if not decoded:
        raise ScriptPathError(f"native {label} must be nonempty")
    _utf16_bound(decoded)
    return decoded


def _absolute_reported_path(cwd: str, output_path: str) -> str:
    _validate_selected_name(output_path)
    if PureWindowsPath(output_path).is_absolute():
        resolved = ntpath.normpath(output_path)
    else:
        resolved = _cwd_join(cwd, output_path)
    _validate_absolute_local(resolved, "native resolved script path")
    _utf16_bound(resolved)
    return resolved


def _strict_json_document(raw: bytes, label: str) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ScriptPathError(f"{label} contains a duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ScriptPathError(f"{label} contains an invalid JSON number")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScriptPathError(f"{label} is not valid JSON") from exc


def _lua_string_literal(value: str) -> str:
    return '"' + "".join(chr(byte) if 32 <= byte <= 126 and byte not in (34, 92)
                         else "\\%03d" % byte for byte in value.encode("utf-8")) + '"'


def _validate_v3_transport_join(
    transport_pins: list[tuple[str, int, str]], selection_pin: tuple[str, int, str],
    report: Mapping[str, Any], identity: ProcessIdentity, selected: list[str],
) -> tuple[tuple[str, int, str], ...]:
    if len(transport_pins) == 4:
        is_ui = (isinstance(report.get("execution_profile"), Mapping)
                 and report["execution_profile"].get("profile_id") == CURRENT_V3_UI_PROFILE_ID)
        return _validate_v3_root_event_transport_join(
            transport_pins, selection_pin, report, identity, selected, ui_scope=is_ui)
    if len(transport_pins) != 3:
        raise ScriptPathError("v3 root transport must pin selection, registration, and Tuner transcript")
    selection_rows = [pin for pin in transport_pins if pin == selection_pin]
    registration_rows = [pin for pin in transport_pins
                         if Path(pin[0]).name.casefold() == "root-registration.json"]
    transcript_rows = [pin for pin in transport_pins
                       if Path(pin[0]).name.casefold() == "tuner.jsonl"]
    if (len(selection_rows) != 1 or selection_rows[0] != selection_pin
            or len(registration_rows) != 1 or len(transcript_rows) != 1):
        raise ScriptPathError("v3 transport pins do not identify the exact selection/registration/transcript")

    registration_raw = _read_bytes(registration_rows[0][0], "root registration", limit=MAX_PROOF_BYTES)
    registration = _strict_json_document(registration_raw, "root registration")
    expected_keys = {
        "schema", "nonce", "status", "process", "selection", "build", "owner_before",
        "exe_module", "gamecore_module", "command", "environment_key", "prepare_lines",
        "native_receipt", "helper_module", "root_state_index", "records",
        "attempted_nonces", "native_calls", "owner_after", "records_completed",
    }
    if (not isinstance(registration, Mapping) or set(registration) != expected_keys
            or registration.get("schema") != "civ6-host.official-script-path-root-registration.v1"
            or registration.get("status") != "completed"
            or _identity(registration.get("process")) != identity
            or registration.get("selection") != {
                "path": selection_pin[0], "bytes": selection_pin[1], "sha256": selection_pin[2]}
            or registration.get("build") != report.get("build")
            or registration.get("records") != report.get("records")
            or registration.get("records_completed") != len(selected)
            or registration.get("owner_before") != registration.get("owner_after")):
        raise ScriptPathError("v3 root registration does not join to the exact report/process/selection")
    root_index = _strict_int(registration.get("root_state_index"), "registered root state index", minimum=0)
    registration_nonce = registration.get("nonce")
    if not isinstance(registration_nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", registration_nonce):
        raise ScriptPathError("v3 root registration nonce is malformed")
    module = registration.get("helper_module")
    if (not isinstance(module, Mapping) or set(module) != {"path", "name", "base", "bytes", "sha256"}
            or module.get("sha256") != report["helper_module"]["sha256"]
            or not isinstance(module.get("path"), str)
            or os.path.normcase(os.path.normpath(module["path"]))
                != os.path.normcase(os.path.normpath(report["helper_module"]["path"]))
            or not isinstance(module.get("name"), str)
            or module["name"].casefold() != Path(module["path"]).name.casefold()
            or _strict_int(module.get("base"), "loaded helper base", minimum=0x10000) % 0x10000
            or _strict_int(module.get("bytes"), "loaded helper size", minimum=1) <= 0):
        raise ScriptPathError("v3 registered helper module differs from the pinned helper delivery")
    for label, expected_sha in (("exe_module", None), ("gamecore_module", CURRENT_CORE_SHA256)):
        live_image = registration.get(label)
        if (not isinstance(live_image, Mapping)
                or set(live_image) != ({"path", "name", "base", "bytes"} if expected_sha is None
                                      else {"path", "name", "base", "bytes", "sha256"})
                or not isinstance(live_image.get("path"), str)
                or not isinstance(live_image.get("name"), str)
                or (expected_sha is not None and (
                    not re.fullmatch(r"[0-9a-f]{64}", str(live_image.get("sha256", "")))
                    or live_image["sha256"] != expected_sha))
                or _strict_int(live_image.get("base"), f"{label} base", minimum=0x10000) % 0x10000
                or _strict_int(live_image.get("bytes"), f"{label} size", minimum=1) <= 0):
            raise ScriptPathError(f"v3 root registration {label} identity is malformed")
    if (os.path.normcase(os.path.normpath(registration["exe_module"]["path"]))
            != os.path.normcase(os.path.normpath(identity.image_path))):
        raise ScriptPathError("v3 root registration EXE path differs from the process identity")
    if (registration["exe_module"]["name"].casefold() != "civilizationvi.exe"
            or not registration["gamecore_module"]["name"].casefold().startswith("gamecore_")
            or not registration["gamecore_module"]["name"].casefold().endswith(".dll")):
        raise ScriptPathError("v3 root registration EXE/GameCore module names differ from the current profile")
    receipt = registration.get("native_receipt")
    prepare_lines = registration.get("prepare_lines")
    if (not isinstance(receipt, Mapping)
            or receipt != {
                "schema": "civ6rl.localization_query_preparation.v1", "status": "ok",
                "nonce": registration_nonce, "database_function_called": False,
                "module_file_pins_retained": True,
            } or not isinstance(prepare_lines, list) or len(prepare_lines) != 1
            or not isinstance(prepare_lines[0], str)):
        raise ScriptPathError("v3 helper preparation receipt is not tied to the registration nonce")
    prepare_prefix = "CIV6RL_SCRIPT_PATH_PREPARED:" + registration_nonce + ":"
    if not prepare_lines[0].startswith(prepare_prefix) or _strict_json_document(
            prepare_lines[0][len(prepare_prefix):].encode("utf-8"), "root preparation receipt") != receipt:
        raise ScriptPathError("v3 helper preparation acknowledgement differs from its retained receipt")

    calls = registration.get("native_calls")
    attempted = registration.get("attempted_nonces")
    rows = report["records"]
    if (not isinstance(calls, list) or len(calls) != len(selected)
            or not isinstance(attempted, list) or len(attempted) != len(selected)
            or len(set(attempted)) != len(attempted)
            or registration_nonce in attempted):
        raise ScriptPathError("v3 root registration lacks one completed call per selected name")
    expected_raw_lines: list[str] = [prepare_lines[0]]
    for index, (call, row, name) in enumerate(zip(calls, rows, selected, strict=True)):
        response = row["response"]
        nonce = response["nonce"]
        if (not isinstance(call, Mapping)
                or set(call) != {"index", "selected_name", "nonce", "status", "raw_lines", "response"}
                or call.get("index") != index or call.get("selected_name") != name
                or call.get("nonce") != nonce or attempted[index] != nonce
                or call.get("status") != "ok" or call.get("response") != response):
            raise ScriptPathError(f"v3 root native call {index} does not match report order/nonce/response")
        raw_lines = call.get("raw_lines")
        prefix = "CIV6RL_SCRIPT_PATH_RESULT:" + nonce + ":"
        if (not isinstance(raw_lines, list) or len(raw_lines) != 1
                or not isinstance(raw_lines[0], str) or not raw_lines[0].startswith(prefix)
                or _strict_json_document(raw_lines[0][len(prefix):].encode("utf-8"),
                                         f"root response {index}") != response):
            raise ScriptPathError(f"v3 root native call {index} raw acknowledgement differs from its response")
        expected_raw_lines.append(raw_lines[0])

    transcript_raw = _read_bytes(transcript_rows[0][0], "root Tuner transcript", limit=MAX_PROOF_BYTES)
    try:
        transcript_lines = transcript_raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as exc:
        raise ScriptPathError("v3 Tuner transcript is not UTF-8") from exc
    events = [_strict_json_document(line.encode("utf-8"), f"Tuner transcript row {i}")
              for i, line in enumerate(transcript_lines)]
    received_lines: list[str] = []
    sent_commands: list[str] = []
    for event in events:
        if not isinstance(event, Mapping) or set(event) != {"time", "direction", "tag", "payload"}:
            raise ScriptPathError("v3 Tuner transcript event fields differ from the transport contract")
        if event["direction"] == "received":
            if event["tag"] == 3 and isinstance(event["payload"], str) and event["payload"].startswith("O\x00"):
                text = event["payload"][2:].partition(": ")
                received_lines.append(text[2] if text[1] else event["payload"][2:])
        elif event["direction"] == "sent" and event["tag"] == 3 and isinstance(event["payload"], str):
            sent_commands.append(event["payload"])
    for line in expected_raw_lines:
        if received_lines.count(line) != 1:
            raise ScriptPathError("v3 sidecar acknowledgement is not present exactly once in the Tuner transcript")
    prepare_commands = [payload for payload in sent_commands
                        if payload.startswith(f"CMD:{root_index}:")
                        and _lua_string_literal(registration_nonce) in payload
                        and "civ6rl_localization_query_prepare" in payload
                        and _lua_string_literal(report["helper_module"]["path"]) in payload
                        and _lua_string_literal(report["helper_module"]["sha256"]) in payload
                        and _lua_string_literal(str(identity.pid)) in payload
                        and _lua_string_literal(str(identity.creation_filetime)) in payload]
    if len(prepare_commands) != 1:
        raise ScriptPathError("v3 Tuner transcript does not join the root registration command")
    for index, (name, row) in enumerate(zip(selected, rows, strict=True)):
        nonce = row["response"]["nonce"]
        candidates = [payload for payload in sent_commands
                      if payload.startswith(f"CMD:{root_index}:")
                      and _lua_string_literal(nonce) in payload
                      and _lua_string_literal(name) in payload
                      and _lua_string_literal(report["helper_module"]["sha256"]) in payload
                      and _lua_string_literal(str(identity.pid)) in payload
                      and _lua_string_literal(str(identity.creation_filetime)) in payload]
        if len(candidates) != 1:
            raise ScriptPathError(f"v3 Tuner transcript command {index} does not join to its selected name/nonce")
    return ()


def _validate_v3_root_event_transport_join(
    transport_pins: list[tuple[str, int, str]], selection_pin: tuple[str, int, str],
    report: Mapping[str, Any], identity: ProcessIdentity, selected: list[str], *, ui_scope: bool = False,
) -> tuple[tuple[str, int, str], ...]:
    selection_rows = [pin for pin in transport_pins if pin == selection_pin]
    registration_rows = [pin for pin in transport_pins
                         if Path(pin[0]).name.casefold() == "root-registration.json"]
    transcript_rows = [pin for pin in transport_pins if Path(pin[0]).name.casefold() == "tuner.jsonl"]
    inbox_rows = [pin for pin in transport_pins if Path(pin[0]).name.casefold() == "inbox-transport.json"]
    if (len(transport_pins) != 4 or len(selection_rows) != 1 or len(registration_rows) != 1
            or len(transcript_rows) != 1 or len(inbox_rows) != 1):
        raise ScriptPathError("v3 root-event transport must pin selection, registration, Tuner, and inbox evidence")
    registration_pin, transcript_pin, inbox_pin = registration_rows[0], transcript_rows[0], inbox_rows[0]

    registration = _strict_json_document(
        _read_bytes(registration_pin[0], "root-event registration", limit=MAX_PROOF_BYTES),
        "root-event registration")
    expected_registration_keys = {
        "schema", "transport", "nonce", "status", "process", "selection", "menu_selection", "build",
        "owner_before", "owner_after", "exe_module", "gamecore_module", "command",
        "environment_key", "event_name", "prepare_lines", "native_receipt", "helper_module",
        "root_state_index", "selected_names", "records", "attempted_nonces", "native_calls",
        "records_completed",
    }
    if ui_scope:
        expected_registration_keys |= {
            "registration_scope", "callback_scope", "execution_profile_id",
            "menu_selection_role", "template_process",
        }
    expected_registration_schema = ("civ6-host.official-script-path-ui-registration.v1" if ui_scope
                                    else "civ6-host.official-script-path-root-registration.v2")
    expected_transport = ("root_event_ui_callback_via_ui_inbox" if ui_scope
                          else "root_event_via_ui_inbox")
    if (not isinstance(registration, Mapping) or set(registration) != expected_registration_keys
            or registration.get("schema") != expected_registration_schema
            or registration.get("transport") != expected_transport
            or registration.get("status") != "completed"
            or _identity(registration.get("process")) != identity
            or registration.get("selection") != {
                "path": selection_pin[0], "bytes": selection_pin[1], "sha256": selection_pin[2]}
            or not isinstance(registration.get("menu_selection"), Mapping)
            or registration.get("build") != report.get("build")
            or registration.get("selected_names") != selected
            or registration.get("records") != report.get("records")
            or registration.get("records_completed") != len(selected)
            or registration.get("owner_before") != registration.get("owner_after")):
        raise ScriptPathError("v3 root-event registration does not join to report/process/selection")
    if ui_scope and (registration.get("registration_scope") != "root"
                     or registration.get("callback_scope") != "ui"
                     or registration.get("execution_profile_id") != CURRENT_V3_UI_PROFILE_ID):
        raise ScriptPathError("v3 UI helper registration/callback scopes differ from the pinned profile")
    menu_selection_pin = _read_file_pin(registration["menu_selection"], "root-event menu selection")
    menu_selection_doc = _strict_json_document(
        _read_bytes(menu_selection_pin[0], "root-event menu selection", limit=MAX_SELECTION_BYTES),
        "root-event menu selection")
    try:
        menu_capture = menu_selection_doc["gameplay_selection994"]
        menu_identity = _identity(menu_capture["process"])
        menu_names = menu_capture["snapshot"]["selected_paths"]
    except (KeyError, TypeError) as exc:
        raise ScriptPathError("root-event menu selection lacks process or ordered names") from exc
    if ui_scope:
        template_role = registration.get("menu_selection_role")
        template_process = _identity(registration.get("template_process"))
        if (template_role not in ("same_process", "expected_names_template")
                or template_process != menu_identity or menu_names != selected
                or (template_role == "same_process" and menu_identity != identity)):
            raise ScriptPathError("v3 UI menu selection role/process/order is unsupported")
        try:
            template_capture = menu_capture
            template_snapshot = template_capture["snapshot"]
            template_gamecore_sha = template_capture["gamecore_module"]["sha256"]
            template_exe_path = template_capture["exe_module"]["path"]
        except (KeyError, TypeError) as exc:
            raise ScriptPathError("v3 UI names template lacks its pinned current image fields") from exc
        if (template_snapshot.get("executable_sha256") != CURRENT_EXE_SHA256
                or template_snapshot.get("current_correspondence_sha256") != CURRENT_SELECTION_SOURCE_SHA256
                or template_gamecore_sha != CURRENT_CORE_SHA256
                or os.path.normcase(os.path.normpath(template_exe_path))
                    != os.path.normcase(os.path.normpath(identity.image_path))):
            raise ScriptPathError("v3 UI names template does not belong to the current executable profile")
    elif menu_identity != identity or menu_names != selected:
        raise ScriptPathError("root-event menu selection differs from current process or selected order")
    registration_nonce = registration.get("nonce")
    if not isinstance(registration_nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", registration_nonce):
        raise ScriptPathError("v3 root-event registration nonce is malformed")
    event_name = "Civ6RL_OfficialScriptPathResolve_" + registration_nonce
    if registration.get("event_name") != event_name:
        raise ScriptPathError("v3 root-event name is not bound to its registration nonce")
    root_index = _strict_int(registration.get("root_state_index"), "registered root state index", minimum=0)
    module = registration.get("helper_module")
    if (not isinstance(module, Mapping) or set(module) != {"path", "name", "base", "bytes", "sha256"}
            or module.get("sha256") != report["helper_module"]["sha256"]
            or not isinstance(module.get("path"), str)
            or os.path.normcase(os.path.normpath(module["path"]))
                != os.path.normcase(os.path.normpath(report["helper_module"]["path"]))
            or not isinstance(module.get("name"), str)
            or module["name"].casefold() != Path(module["path"]).name.casefold()
            or _strict_int(module.get("base"), "loaded helper base", minimum=0x10000) % 0x10000
            or _strict_int(module.get("bytes"), "loaded helper size", minimum=1) <= 0):
        raise ScriptPathError("v3 root-event helper module differs from its pinned delivery")
    for label, expected_sha in (("exe_module", None), ("gamecore_module", CURRENT_CORE_SHA256)):
        live_image = registration.get(label)
        if (not isinstance(live_image, Mapping)
                or set(live_image) != ({"path", "name", "base", "bytes"} if expected_sha is None
                                      else {"path", "name", "base", "bytes", "sha256"})
                or not isinstance(live_image.get("path"), str)
                or not isinstance(live_image.get("name"), str)
                or (expected_sha is not None and (
                    not re.fullmatch(r"[0-9a-f]{64}", str(live_image.get("sha256", "")))
                    or live_image["sha256"] != expected_sha))
                or _strict_int(live_image.get("base"), f"{label} base", minimum=0x10000) % 0x10000
                or _strict_int(live_image.get("bytes"), f"{label} size", minimum=1) <= 0):
            raise ScriptPathError(f"v3 root-event {label} identity is malformed")
    if (os.path.normcase(os.path.normpath(registration["exe_module"]["path"]))
            != os.path.normcase(os.path.normpath(identity.image_path))
            or registration["exe_module"]["name"].casefold() != "civilizationvi.exe"
            or not registration["gamecore_module"]["name"].casefold().startswith("gamecore_")
            or not registration["gamecore_module"]["name"].casefold().endswith(".dll")):
        raise ScriptPathError("v3 root-event EXE/GameCore identity differs from current profile")

    receipt = registration.get("native_receipt")
    prepare_lines = registration.get("prepare_lines")
    if (not isinstance(receipt, Mapping)
            or receipt != {
                "schema": "civ6rl.localization_query_preparation.v1", "status": "ok",
                "nonce": registration_nonce, "database_function_called": False,
                "module_file_pins_retained": True,
            } or not isinstance(prepare_lines, list) or len(prepare_lines) != 1
            or not isinstance(prepare_lines[0], str)):
        raise ScriptPathError("v3 root-event preparation receipt differs from helper contract")
    prepare_prefix = "CIV6RL_SCRIPT_PATH_PREPARED:" + registration_nonce + ":"
    if (not prepare_lines[0].startswith(prepare_prefix)
            or _strict_json_document(prepare_lines[0][len(prepare_prefix):].encode("utf-8"),
                                     "root-event preparation receipt") != receipt):
        raise ScriptPathError("v3 root-event preparation acknowledgement is not nonce-bound")
    command = registration.get("command")
    required_listener_source = (("box.callback=resolve", "box.handoff_nonce=registration_nonce")
                                if ui_scope else ("root_lookup=Locale.Lookup",))
    if (not isinstance(command, str) or not command or len(command) > 256 * 1024
            or any(source not in command for source in required_listener_source)
            or "LuaEvents" not in command or "event.Add" not in command or event_name not in command
            or _lua_string_literal(report["helper_module"]["path"]) not in command
            or _lua_string_literal(report["helper_module"]["sha256"]) not in command
            or _lua_string_literal(str(identity.pid)) not in command
            or _lua_string_literal(str(identity.creation_filetime)) not in command):
        raise ScriptPathError("v3 root-event registration command lacks captured root resolver identity")
    helper_key = "Civ6RLOfficialScriptPath_" + report["helper_module"]["sha256"]
    selected_literal_table = "{" + ",".join(_lua_string_literal(name) for name in selected) + "}"
    if (registration.get("environment_key") != helper_key
            or (not ui_scope and "Locale.Lookup" not in command)
            or "resolve" not in command or selected_literal_table not in command):
        raise ScriptPathError("v3 root-event registration does not retain the root helper and lookup")

    # The pre-Load Tuner trace proves only root registration/preparation. The
    # helper method result is separately tied to the post-Load inbox transcript.
    tuner_raw = _read_bytes(transcript_pin[0], "root-event Tuner transcript", limit=MAX_PROOF_BYTES)
    tuner_events = [_strict_json_document(line.encode("utf-8"), f"Tuner transcript row {i}")
                    for i, line in enumerate(tuner_raw.decode("utf-8", errors="strict").splitlines())]
    prep_received: list[str] = []
    prep_sent: list[str] = []
    for event in tuner_events:
        if not isinstance(event, Mapping) or set(event) != {"time", "direction", "tag", "payload"}:
            raise ScriptPathError("v3 root-event Tuner transcript event differs from transport format")
        if (event["direction"] == "received" and event["tag"] in (3, -1)
                and isinstance(event["payload"], str) and event["payload"].startswith("O\x00")):
            content = event["payload"][2:].partition(": ")
            prep_received.append(content[2] if content[1] else event["payload"][2:])
        elif (event["direction"] == "sent" and event["tag"] == 3
              and isinstance(event["payload"], str)):
            prep_sent.append(event["payload"])
    if (prep_received.count(prepare_lines[0]) != 1
            or sum(payload.startswith(f"CMD:{root_index}:") and command in payload
                   for payload in prep_sent) != 1):
        raise ScriptPathError("v3 root-event prep acknowledgement/command is absent from Main State trace")

    inbox = _strict_json_document(
        _read_bytes(inbox_pin[0], "root-event inbox transport", limit=MAX_PROOF_BYTES),
        "root-event inbox transport")
    expected_inbox_keys = {
        "schema", "registration", "process", "player_id", "turn", "inbox_path",
        "log_source_path", "records", "inbox_restored",
    }
    if ui_scope:
        expected_inbox_keys.add("transport")
    if (not isinstance(inbox, Mapping) or set(inbox) != expected_inbox_keys
            or inbox.get("schema") != ("civ6-host.official-script-path-ui-inbox-transport.v1" if ui_scope
                                        else "civ6-host.official-script-path-inbox-transport.v1")
            or (ui_scope and inbox.get("transport") != expected_transport)
            or inbox.get("registration") != {"path": registration_pin[0], "bytes": registration_pin[1],
                                             "sha256": registration_pin[2]}
            or _identity(inbox.get("process")) != identity
            or inbox.get("inbox_restored") is not True
            or not isinstance(inbox.get("inbox_path"), str)
            or Path(inbox["inbox_path"]).name != "Civ6RLInbox.lua"
            or not isinstance(inbox.get("log_source_path"), str)):
        raise ScriptPathError("v3 inbox transport sidecar does not join to its root registration/process")
    _validate_absolute_local(inbox["inbox_path"], "captured inbox path")
    _validate_absolute_local(inbox["log_source_path"], "captured Lua.log source path")
    _strict_int(inbox.get("player_id"), "inbox UI player id", minimum=0, maximum=63)
    _strict_int(inbox.get("turn"), "inbox UI turn", minimum=0)
    inbox_records = inbox.get("records")
    calls = registration.get("native_calls")
    attempted = registration.get("attempted_nonces")
    if (not isinstance(inbox_records, list) or len(inbox_records) != len(selected)
            or not isinstance(calls, list) or len(calls) != len(selected)
            or not isinstance(attempted, list) or len(attempted) != len(selected)
            or len(set(attempted)) != len(attempted) or registration_nonce in attempted):
        raise ScriptPathError("v3 root-event sidecars do not contain one unique call per selected name")

    nested_pins: list[tuple[str, int, str]] = []
    previous_log_end = -1
    for index, (name, report_row, call, inbox_row, nonce) in enumerate(
            zip(selected, report["records"], calls, inbox_records, attempted, strict=True)):
        response = report_row["response"]
        if (not isinstance(call, Mapping)
                or set(call) != ({"index", "selected_name", "nonce", "status", "raw_lines", "response",
                                  "handoff_nonce", "callback_scope"} if ui_scope else
                                 {"index", "selected_name", "nonce", "status", "raw_lines", "response"})
                or call.get("index") != index or call.get("selected_name") != name
                or call.get("nonce") != nonce or call.get("status") != "ok"
                or call.get("response") != response):
            raise ScriptPathError(f"v3 root-event call {index} does not match ordered report row")
        if ui_scope and (call.get("handoff_nonce") != registration_nonce
                         or call.get("callback_scope") != "ui"):
            raise ScriptPathError(f"v3 UI native call {index} lacks the exact root handoff")
        inbox_row_keys = {
            "index", "selected_name", "nonce", "command_pin", "log_window", "log_offset",
            "ack_line", "result_line", "inbox_before_sha256", "inbox_written_sha256",
            "inbox_restored_sha256", "inbox_restored", "log_source_metadata",
        }
        if ui_scope:
            inbox_row_keys |= {"handoff_nonce", "callback_scope"}
        if (not isinstance(inbox_row, Mapping) or set(inbox_row) != inbox_row_keys
                or inbox_row.get("index") != index or inbox_row.get("selected_name") != name
                or inbox_row.get("nonce") != nonce or inbox_row.get("inbox_restored") is not True):
            raise ScriptPathError(f"v3 inbox call {index} does not join by order/name/nonce")
        if ui_scope and (inbox_row.get("handoff_nonce") != registration_nonce
                         or inbox_row.get("callback_scope") != "ui"):
            raise ScriptPathError(f"v3 UI inbox call {index} does not join to the root handoff")
        command_pin = _read_file_pin(inbox_row["command_pin"], f"root-event command {index}")
        command_path = Path(command_pin[0]).as_posix().replace("\\", "/")
        expected_command_suffix = f"commands/path-{index:04d}-{nonce}.lua"
        if not command_path.endswith(expected_command_suffix):
            raise ScriptPathError(f"v3 inbox command {index} path differs from its index/nonce")
        command_bytes = _read_bytes(command_pin[0], f"root-event command {index}", limit=MAX_PROOF_BYTES)
        try:
            command_text = command_bytes.decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise ScriptPathError(f"v3 inbox command {index} is not ASCII") from exc
        required_command_literals = (
            event_name, registration_nonce, _lua_string_literal(name),
            _lua_string_literal(nonce), _lua_string_literal(str(identity.pid)),
            _lua_string_literal(str(identity.creation_filetime)), "LuaEvents",
            "Game.GetLocalPlayer", "Game.GetCurrentGameTurn", "UI.IsGameCoreBusy",
            _lua_string_literal("CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + nonce + ":"),
            _lua_string_literal("CIV6RL_SCRIPT_PATH_INBOX_RESULT:" + nonce + ":"),
            str(inbox["player_id"]), str(inbox["turn"]),
        )
        if ui_scope:
            required_command_literals += (
                "box.handoff_nonce", "box.callback", "Locale.Lookup",
                _lua_string_literal(registration_nonce),
            )
        if any(literal not in command_text for literal in required_command_literals):
            raise ScriptPathError(f"v3 inbox command {index} lacks the root-event request identity")
        if (inbox_row.get("inbox_written_sha256") != command_pin[2]
                or inbox_row.get("inbox_before_sha256") != inbox_row.get("inbox_restored_sha256")
                or not re.fullmatch(r"[0-9a-f]{64}", str(inbox_row.get("inbox_before_sha256", "")))):
            raise ScriptPathError(f"v3 inbox command {index} does not prove byte restoration")

        window_pin = _read_file_pin(inbox_row["log_window"], f"root-event log window {index}")
        window_bytes = _read_bytes(window_pin[0], f"root-event log window {index}", limit=MAX_PROOF_BYTES)
        offset = _strict_int(inbox_row.get("log_offset"), f"root-event log offset {index}", minimum=0)
        metadata = inbox_row.get("log_source_metadata")
        metadata_keys = {
            "path", "file_device", "file_id", "size_before", "mtime_ns_before", "size_after",
            "mtime_ns_after", "offset", "window_bytes", "window_sha256", "live_slice_sha256",
            "live_slice_matches",
        }
        if (not isinstance(metadata, Mapping) or set(metadata) != metadata_keys
                or metadata.get("path") != inbox["log_source_path"]
                or _strict_int(metadata.get("offset"), f"Lua.log source offset {index}", minimum=0) != offset
                or _strict_int(metadata.get("window_bytes"), f"Lua.log window size {index}", minimum=1) != len(window_bytes)
                or metadata.get("window_sha256") != window_pin[2]
                or metadata.get("live_slice_sha256") != window_pin[2]
                or metadata.get("live_slice_matches") is not True
                or _strict_int(metadata.get("file_device"), "Lua.log device", minimum=0) < 0
                or _strict_int(metadata.get("file_id"), "Lua.log file id", minimum=0) < 0
                or _strict_int(metadata.get("size_before"), "Lua.log size before", minimum=0) < offset
                or _strict_int(metadata.get("size_after"), "Lua.log size after", minimum=0) < offset + len(window_bytes)
                or _strict_int(metadata.get("mtime_ns_before"), "Lua.log mtime before", minimum=0) < 0
                or _strict_int(metadata.get("mtime_ns_after"), "Lua.log mtime after", minimum=0) < 0):
            raise ScriptPathError(f"v3 log-window metadata {index} does not bind the captured live slice")
        if offset < previous_log_end:
            raise ScriptPathError("v3 log windows are not in selected invocation order")
        previous_log_end = offset + len(window_bytes)
        try:
            window_text = window_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ScriptPathError(f"v3 log window {index} is not UTF-8") from exc
        ack_line = inbox_row.get("ack_line")
        result_line = inbox_row.get("result_line")
        ack_prefix = "CIV6RL_SCRIPT_PATH_INBOX_RESPONSE:" + nonce + ":"
        result_marker = "CIV6RL_SCRIPT_PATH_INBOX_RESULT:" + nonce + ":true captured"
        if (not isinstance(ack_line, str) or ack_prefix not in ack_line
                or not isinstance(result_line, str) or result_marker not in result_line
                or window_text.count(ack_line) != 1 or window_text.count(result_line) != 1
                or window_text.find(ack_line) >= window_text.find(result_line)):
            raise ScriptPathError(f"v3 log window {index} lacks ordered inbox acknowledgement markers")
        ack_payload = ack_line.split(ack_prefix, 1)[1]
        parsed_response = _strict_json_document(ack_payload.encode("utf-8"), f"inbox response {index}")
        if parsed_response != response or call.get("raw_lines") != [ack_line]:
            raise ScriptPathError(f"v3 inbox acknowledgement {index} differs from the root native response")
        nested_pins.extend((command_pin, window_pin))
    return (menu_selection_pin, *nested_pins)


def _validate_v3_resolution_report(
    report: Any,
    identity: ProcessIdentity,
    selected: list[str],
    cwd: str,
    manager_address: int,
    selection_pin: tuple[str, int, str],
) -> tuple[tuple[str, ...], tuple[tuple[str, int, str], ...], str]:
    if not isinstance(report, Mapping):
        raise ScriptPathError("v3 native path-resolution report must be an object")
    expected_keys = {
        "schema", "status", "process", "execution_profile", "capture_id", "build",
        "helper_module", "helper_source", "override_proof", "records",
        "root_transport_proofs", "player_observation", "training_ready",
    }
    if set(report) != expected_keys:
        raise ScriptPathError("v3 path-resolution report fields differ from the reviewed schema")
    if report["schema"] != CURRENT_V3_REPORT_SCHEMA or report["status"] != CURRENT_V3_REPORT_STATUS:
        raise ScriptPathError("v3 path-resolution report schema/status is unsupported")
    if _identity(report["process"]) != identity:
        raise ScriptPathError("v3 path-resolution process identity differs from the selection")
    profile = report["execution_profile"]
    if not isinstance(profile, Mapping):
        raise ScriptPathError("v3 path-resolution execution profile is malformed")
    ui_scope = profile.get("profile_id") == CURRENT_V3_UI_PROFILE_ID
    expected_profile_id = (CURRENT_V3_UI_PROFILE_ID if ui_scope else
                            "xp2-exe-current-d1a0-core-092abfbb-native-path")
    if (not isinstance(profile, Mapping)
            or set(profile) != {"profile_id", "executable_sha256", "runtime_gamecore_sha256", "selection_source_sha256"}
            or profile["profile_id"] != expected_profile_id
            or profile["executable_sha256"] != CURRENT_EXE_SHA256
            or profile["runtime_gamecore_sha256"] != CURRENT_CORE_SHA256
            or profile["selection_source_sha256"] != CURRENT_SELECTION_SOURCE_SHA256):
        raise ScriptPathError("v3 path-resolution execution profile differs from the current image")
    capture_id = report["capture_id"]
    if not isinstance(capture_id, str) or not re.fullmatch(r"[0-9a-f]{32}", capture_id):
        raise ScriptPathError("v3 capture_id must be 32 lowercase hexadecimal characters")
    if report["player_observation"] is not False or report["training_ready"] is not False:
        raise ScriptPathError("v3 path-resolution report cannot claim a player observation or training readiness")

    proof_rows: list[tuple[str, int, str]] = []
    for label in ("build", "helper_module", "helper_source"):
        proof_rows.append(_pin_native_asset(report[label], label, scope="ui" if ui_scope else "root"))
    build_pin = proof_rows[0]
    try:
        build_doc = json.loads(_read_bytes(build_pin[0], "v3 path helper build receipt",
                                           limit=MAX_PROOF_BYTES))
        build_static_profile = (
            build_doc["schema"] == "civ6-host.official_script_path_build.v1"
            and build_doc["returncode"] == 0
            and build_doc["helper_loaded"] is False
            and build_doc["game_invoked"] is False
            and build_doc["native_method_called"] is False
            and build_doc["lua_scope"] == ("ui" if ui_scope else "root")
            and (not ui_scope or build_doc["execution_profile_id"] == CURRENT_V3_UI_PROFILE_ID)
            and build_doc["source_overlay_from_query_build"] is True
            and build_doc["verified_current_abi"]["image_base"] == hex(CURRENT_EXE_IMAGE_BASE)
            and build_doc["verified_current_abi"]["manager_global_rva"] == hex(CURRENT_SCRIPT_MANAGER_GLOBAL_RVA)
            and build_doc["verified_current_abi"]["manager_vtable_rva"] == hex(CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA)
            and build_doc["verified_current_abi"]["manager_vtable_sha256"]
                == "d52891161a36500d1255b8e3a43b18cfedd197c078a97de391da829b1e3f7fe0"
            and build_doc["verified_current_abi"]["slot_0x30_target_rva"] == hex(CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)
            and build_doc["verified_current_abi"]["callback_rva"] == "0x974190"
            and build_doc["verified_current_abi"]["dispatcher_rva"] == "0x972790"
            and build_doc["verified_current_abi"]["dispatcher_callsite_rva"] == "0x9727f5"
            and build_doc["verified_current_abi"]["method_span"]["sha256"]
                == "5227bb0dfcd8a8fe71124d1f9f6ef7dd14d41f60d33a9a08e5d8dba3f26d4539"
            and build_doc["verified_current_abi"]["lua_lookup_rva"] == "0x4c9c30"
            and build_doc["verified_current_abi"]["root_manager_rva"] == hex(CURRENT_SCRIPT_MANAGER_GLOBAL_RVA)
            and build_doc["verified_current_abi"]["lua_cs_rva"] == "0x3553fa0"
            and build_doc["verified_current_abi"]["wfullpath_iat_rva"] == "0xf985a0"
            and build_doc["verified_current_abi"]["wfullpath_import"]
                == "api-ms-win-crt-filesystem-l1-1-0.dll!_wfullpath"
        )
        if ui_scope:
            source_pin = _read_file_pin(build_doc["source"], "v3 UI build helper source")
        else:
            source_row = build_doc["source"]
            if (not isinstance(source_row, Mapping)
                    or source_row.get("bytes") != CURRENT_V3_ASSET_PINS["helper_source"][1]
                    or source_row.get("sha256") != CURRENT_V3_ASSET_PINS["helper_source"][2]
                    or not isinstance(source_row.get("path"), str)
                    or not Path(source_row["path"]).as_posix().replace("\\", "/").endswith(
                        CURRENT_V3_ROOT_ORIGINAL_SOURCE_PATH)):
                raise ScriptPathError("root build receipt source record differs from its archived source")
            source_pin = _pin_native_asset(source_row, "helper_source", scope="root")
        module_pin = _read_file_pin(build_doc["dll"], "v3 build helper module")
        query_build_pin = _read_file_pin(build_doc["query_build"], "v3 base query build")
        query_snapshot_pins = tuple(_read_file_pin(row, f"v3 query snapshot {i}")
                                    for i, row in enumerate(build_doc["query_snapshots"]))
        evidence = build_doc["source_evidence"]
        live_pointer_row = next(row for row in evidence
                                if Path(row["path"]).as_posix().replace("\\", "/").endswith(
                                    CURRENT_V3_LIVE_POINTER_PIN[0]))
        live_pointer_pin = _read_file_pin(live_pointer_row, "v3 live ScriptManager pointer receipt")
        exe_row = next(row for row in evidence
                       if isinstance(row.get("path"), str) and row["path"].casefold().endswith("civilizationvi.exe"))
        abi_image_matches = (exe_row["bytes"] == CURRENT_EXE_SIZE_BYTES
                             and exe_row["sha256"] == CURRENT_EXE_SHA256)
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ScriptPathError("v3 helper build receipt is malformed") from exc
    if ui_scope:
        try:
            scope_contract = build_doc["scope_contract"]
            static_validation = build_doc["static_validation"]
            ui_static_profile = (
                scope_contract["prepare_scope"] == "RootTunerMainState remains unchanged and owns the existing Lua CS preparation"
                and "exact UI-state identity and owned Lua critical section" in scope_contract["guard"]
                and static_validation["ui_scope_guard_present"] is True
                and static_validation["ui_receipt_scope_present"] is True
                and static_validation["root_preparation_unchanged"] is True
                and static_validation["unprepared_call_returns_without_lua_api"] is True
                and static_validation["gamecore_module_imported_by_helper"] is False
                and set(static_validation["required_exports"]) == {
                    "civ6rl_localization_export", "civ6rl_localization_prepare",
                    "civ6rl_localization_query", "civ6rl_localization_query_prepare",
                    "civ6rl_official_script_path",
                }
            )
            prior_root_source = _read_file_pin(
                build_doc["archived_previous_root_source"], "archived previous root helper source")
            prior_root_build = _read_file_pin(
                build_doc["previous_root_scope_build"], "previous root-scope build receipt")
            prior_root_dll = _read_file_pin(
                build_doc["previous_root_scope_dll"], "previous root-scope helper DLL")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ScriptPathError("v3 UI helper scope/lineage receipt is malformed") from exc
        if (not ui_static_profile
                or prior_root_source[1:] != CURRENT_V3_UI_PREVIOUS_ROOT_SOURCE_PIN[1:]
                or not Path(prior_root_source[0]).as_posix().replace("\\", "/").endswith(
                    CURRENT_V3_UI_PREVIOUS_ROOT_SOURCE_PIN[0])
                or prior_root_build[1:] != CURRENT_V3_UI_PREVIOUS_ROOT_BUILD_PIN[1:]
                or not Path(prior_root_build[0]).as_posix().replace("\\", "/").endswith(
                    CURRENT_V3_UI_PREVIOUS_ROOT_BUILD_PIN[0])
                or prior_root_dll[1:] != CURRENT_V3_UI_PREVIOUS_ROOT_DLL_PIN[1:]
                or not Path(prior_root_dll[0]).as_posix().replace("\\", "/").endswith(
                    CURRENT_V3_UI_PREVIOUS_ROOT_DLL_PIN[0])):
            raise ScriptPathError("v3 UI helper scope or prior-root lineage differs")
    if (not build_static_profile or source_pin != proof_rows[2] or module_pin != proof_rows[1]
            or query_build_pin[1:] != CURRENT_V3_QUERY_BUILD_PIN[1:]
            or not Path(query_build_pin[0]).as_posix().replace("\\", "/").endswith(CURRENT_V3_QUERY_BUILD_PIN[0])
            or len(query_snapshot_pins) != len(CURRENT_V3_QUERY_SNAPSHOT_PINS)
            or any(pin[1:] != expected[1:]
                   or not Path(pin[0]).as_posix().replace("\\", "/").endswith(expected[0])
                   for pin, expected in zip(query_snapshot_pins, CURRENT_V3_QUERY_SNAPSHOT_PINS, strict=True))
            or live_pointer_pin[1:] != CURRENT_V3_LIVE_POINTER_PIN[1:]
            or not Path(live_pointer_pin[0]).as_posix().replace("\\", "/").endswith(CURRENT_V3_LIVE_POINTER_PIN[0])
            or not abi_image_matches):
        raise ScriptPathError("v3 helper build lineage or current ABI proof differs")
    proof_rows.extend((query_build_pin, *query_snapshot_pins, live_pointer_pin))
    if ui_scope:
        proof_rows.extend((prior_root_source, prior_root_build, prior_root_dll))
    override_pin = _read_file_pin(report["override_proof"], "actual override proof")
    if (Path(override_pin[0]).as_posix().replace("\\", "/").endswith(CURRENT_OVERRIDE_BINDINGS_PATH) is False
            or override_pin[1:] != (CURRENT_OVERRIDE_BINDINGS_BYTES, CURRENT_OVERRIDE_BINDINGS_SHA256)):
        raise ScriptPathError("v3 actual override proof differs from its exact current-image pin")
    proof_rows.append(override_pin)

    transport = report["root_transport_proofs"]
    if not isinstance(transport, list) or len(transport) not in (3, 4):
        raise ScriptPathError("v3 root transport proofs must use one reviewed transport profile")
    seen_proofs: set[str] = set()
    for index, row in enumerate(transport):
        pin = _read_file_pin(row, f"root transport proof {index}")
        if pin[0] in seen_proofs:
            raise ScriptPathError("v3 root transport proof pins must be unique")
        seen_proofs.add(pin[0])
        proof_rows.append(pin)

    rows = report["records"]
    if not isinstance(rows, list) or len(rows) != len(selected):
        raise ScriptPathError("v3 records must match the selected script count")
    resolved_paths: list[str] = []
    nonces: set[str] = set()
    response_fields = {
        "schema", "status", "nonce", "pid", "creation_filetime", "thread_id",
        "manager_address", "manager_vtable_rva", "method_rva", "capacity_utf16_units",
        "input_utf16le_hex", "output_utf16le_hex", "executable_sha256", "lua_scope", "lua_cs_owned",
        "native_method_called", "gamecore_function_called_by_helper",
        "output_file_opened_by_helper", "path_exists_checked",
        "exe_method_may_delegate_to_content_resolver", "nested_resolver_side_effects_asserted_absent",
    }
    for index, (row, selected_name) in enumerate(zip(rows, selected, strict=True)):
        if not isinstance(row, Mapping) or set(row) != {"selected_name", "response"}:
            raise ScriptPathError(f"v3 record {index} fields differ from the reviewed schema")
        name = _validate_selected_name(row["selected_name"])
        if name != selected_name:
            raise ScriptPathError("v3 records do not preserve the exact ordered selection")
        response = row["response"]
        if not isinstance(response, Mapping) or set(response) != response_fields:
            raise ScriptPathError(f"v3 response {index} fields differ from the helper contract")
        nonce = response["nonce"]
        if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce) or nonce in nonces:
            raise ScriptPathError("v3 response nonces must be unique 32-character lowercase hex")
        nonces.add(nonce)
        if (response["schema"] != "civ6-host.official_script_path_resolution.v1"
                or response["status"] != "ok"
                or _strict_int(response["pid"], "native response PID", minimum=1, maximum=0xFFFFFFFF) != identity.pid
                or _strict_int(response["creation_filetime"], "native response creation FILETIME", minimum=1) != identity.creation_filetime
                or _strict_int(response["thread_id"], "native response thread ID", minimum=1, maximum=0xFFFFFFFF) == 0
                or _strict_int(response["capacity_utf16_units"], "native response path capacity", minimum=1) != 260
                or response["manager_address"] != hex(manager_address)
                or response["manager_vtable_rva"] != hex(CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA)
                or response["method_rva"] != hex(CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)
                or response["executable_sha256"] != CURRENT_EXE_SHA256
                or response["lua_scope"] != ("ui" if ui_scope else "root")):
            raise ScriptPathError(f"v3 native response {index} identity or method profile differs")
        for key, expected_value in (
            ("lua_cs_owned", True), ("native_method_called", True),
            ("gamecore_function_called_by_helper", False),
            ("output_file_opened_by_helper", False), ("path_exists_checked", False),
            ("exe_method_may_delegate_to_content_resolver", True),
            ("nested_resolver_side_effects_asserted_absent", False),
        ):
            if response[key] is not expected_value:
                raise ScriptPathError(f"v3 native response {index} has an unsupported {key} scope flag")
        expected_input = (name + "\0").encode("utf-16-le").hex()
        if response["input_utf16le_hex"] != expected_input:
            raise ScriptPathError(f"v3 native response {index} input does not exactly match the selected name")
        output_name = _decode_native_utf16_path(response["output_utf16le_hex"], f"response {index} output path")
        resolved_paths.append(_absolute_reported_path(cwd, output_name))
    nested_transport_pins = _validate_v3_transport_join(
        proof_rows[-len(transport):], selection_pin, report, identity, selected)
    proof_rows.extend(nested_transport_pins)
    return tuple(resolved_paths), tuple(proof_rows), capture_id


def _parse_context(witness: dict[str, Any], witness_sha: str, expected: ProcessIdentity) -> ScriptPathContext:
    witness_schema = witness.get("schema")
    supported = (SCHEMA, CURRENT_SCHEMA, CURRENT_V3_SCHEMA)
    expected_status = CURRENT_V3_STATUS if witness_schema == CURRENT_V3_SCHEMA else STATUS
    if witness_schema not in supported or witness.get("status") != expected_status:
        raise ScriptPathError("unsupported or incomplete script-path witness")
    current_profile = witness_schema in (CURRENT_SCHEMA, CURRENT_V3_SCHEMA)
    current_v3 = witness_schema == CURRENT_V3_SCHEMA
    try:
        identity = _identity(witness["process"])
        cwd = witness["cwd"]
        selected = witness["selected"]
        resolved = witness["resolved_sources"]
    except (KeyError, TypeError) as exc:
        raise ScriptPathError("script-path witness is missing process/path fields") from exc
    if identity != expected:
        raise ScriptPathError("requested process identity does not match the pinned witness")
    if not isinstance(cwd, str):
        raise ScriptPathError("witness CWD must be a string")
    _validate_absolute_local(cwd, "witness CWD")
    resolver_live = witness.get("resolver_live")
    if not isinstance(resolver_live, Mapping):
        raise ScriptPathError("path-copy service live observation is missing")
    try:
        live_values = {key: _strict_int(resolver_live[key], f"resolver {key}", minimum=1)
                       for key in ("singleton", "vtable", "method")}
    except (KeyError, TypeError, ValueError) as exc:
        raise ScriptPathError("path-copy service live observation is incomplete") from exc
    if current_profile:
        try:
            live_values.update({key: _strict_int(resolver_live[key], f"resolver {key}", minimum=1)
                                for key in ("script_manager", "script_manager_vtable",
                                            "script_manager_slot_30")})
        except (KeyError, TypeError, ValueError) as exc:
            raise ScriptPathError("current ScriptManager slot witness is incomplete") from exc
    if not isinstance(selected, list) or not selected or not isinstance(resolved, list) or len(selected) != len(resolved):
        raise ScriptPathError("selected names and resolved sources must be nonempty, ordered one-to-one lists")

    proof_rows = []
    for key in ("selection_witness", "resolver_source", "observer"):
        row = witness.get(key)
        if not isinstance(row, Mapping):
            raise ScriptPathError(f"missing {key} source proof")
        proof_rows.append(_read_file_pin(row, key))

    # Keep the historical contract pinned, and admit the new EXE only through
    # its separate bounded current-image correspondence receipt.
    if current_profile:
        expected_proof_path = CURRENT_BINDINGS_PATH
        if (Path(proof_rows[1][0]).as_posix().replace("\\", "/").endswith(expected_proof_path) is False
                or proof_rows[1][1:] != (CURRENT_BINDINGS_BYTES, CURRENT_BINDINGS_SHA256)):
            raise ScriptPathError("current resolver proof pin differs")
        try:
            resolver_doc = json.loads(_read_bytes(proof_rows[1][0], "resolver source", limit=MAX_PROOF_BYTES))
            profile = resolver_doc["current_profile"]
            static_profile = (
                resolver_doc["schema"] == "civ6-host.current-exe-script-path-bindings.v1"
                and resolver_doc["current_image"]["sha256"] == CURRENT_EXE_SHA256
                and profile["profile_id"] == CURRENT_PROFILE_ID
                and profile["executable_sha256"] == CURRENT_EXE_SHA256
                and profile["runtime_gamecore_sha256"] == CURRENT_CORE_SHA256
                and profile["abi_reference_gamecore_sha256"] == CURRENT_REFERENCE_CORE_SHA256
                and int(profile["image_base"], 16) == CURRENT_EXE_IMAGE_BASE
                and int(profile["singleton_global_rva"], 16) == CURRENT_SINGLETON_GLOBAL_RVA
                and int(profile["vtable_rva"], 16) == CURRENT_VTABLE_RVA
                and int(profile["method_plus_0x10_rva"], 16) == CURRENT_METHOD_RVA
                and resolver_doc["current_source_derivation"]["register_contract_matches_phase42"] is True
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ScriptPathError("current resolver proof is malformed") from exc
        if not static_profile:
            raise ScriptPathError("current resolver proof does not match the selected image profile")
        caller_row = witness.get("caller_source")
        if not isinstance(caller_row, Mapping):
            raise ScriptPathError("current ScriptManager caller proof is missing")
        caller_pin = _read_file_pin(caller_row, "current caller source")
        proof_rows.append(caller_pin)
        if (Path(caller_pin[0]).as_posix().replace("\\", "/").endswith(CURRENT_CALLER_BINDINGS_PATH) is False
                or caller_pin[1:] != (CURRENT_CALLER_BINDINGS_BYTES, CURRENT_CALLER_BINDINGS_SHA256)):
            raise ScriptPathError("current ScriptManager caller proof pin differs")
        try:
            caller_doc = json.loads(_read_bytes(caller_pin[0], "current caller source", limit=MAX_PROOF_BYTES))
            manager = caller_doc["current_script_manager_dispatch"]
            manager_table = caller_doc["current_manager_vtable"]
            wrapper = caller_doc["current_wrapper"]
            caller_static_profile = (
                caller_doc["schema"] == "civ6-host.current-exe-script-path-caller-bindings.v1"
                and caller_doc["current_image"]["sha256"] == CURRENT_EXE_SHA256
                and caller_doc["parent_corrected_path_profile"]["sha256"] == CURRENT_BINDINGS_SHA256
                and int(manager["manager_global_rva"], 16) == CURRENT_SCRIPT_MANAGER_GLOBAL_RVA
                and int(manager["callsite_rva"], 16) == 0x9727F5
                and manager["callsite_instruction"] == "call qword ptr [rax + 0x30]"
                and int(manager_table["rva"], 16) == CURRENT_SCRIPT_MANAGER_VTABLE_RVA
                and int(manager_table["slot_plus_0x30_rva"], 16)
                    == CURRENT_SCRIPT_MANAGER_VTABLE_RVA + CURRENT_SCRIPT_MANAGER_SLOT_OFFSET
                and int(manager_table["slot_plus_0x30_target_rva"], 16)
                    == CURRENT_SCRIPT_MANAGER_WRAPPER_RVA
                and int(wrapper["rva"], 16) == CURRENT_SCRIPT_MANAGER_WRAPPER_RVA
                and caller_doc["static_assertions"]["current_manager_vtable_slot_0x30_equals_wrapper"] is True
                and caller_doc["static_assertions"]["path_buffer_reaches_createfilew_filename_argument"] is True
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ScriptPathError("current ScriptManager caller proof is malformed") from exc
        if not caller_static_profile:
            raise ScriptPathError("current ScriptManager caller proof does not match the selected profile")
        if current_v3:
            override_row = witness.get("override_source")
            if not isinstance(override_row, Mapping):
                raise ScriptPathError("current v3 actual ScriptManager override proof is missing")
            override_pin = _read_file_pin(override_row, "current actual override source")
            proof_rows.append(override_pin)
            if (Path(override_pin[0]).as_posix().replace("\\", "/").endswith(CURRENT_OVERRIDE_BINDINGS_PATH) is False
                    or override_pin[1:] != (CURRENT_OVERRIDE_BINDINGS_BYTES, CURRENT_OVERRIDE_BINDINGS_SHA256)):
                raise ScriptPathError("current v3 actual override proof pin differs")
            try:
                override_doc = json.loads(_read_bytes(override_pin[0], "current actual override source",
                                                     limit=MAX_PROOF_BYTES))
                actual_table = override_doc["actual_manager_vtable"]
                override_live = override_doc["live_pointer_observation"]
                override_static_profile = (
                    override_doc["schema"] == "civ6-host.current-exe-script-path-actual-override.v1"
                    and override_doc["current_image"]["sha256"] == CURRENT_EXE_SHA256
                    and override_doc["base_only_proof"]["sha256"] == CURRENT_CALLER_BINDINGS_SHA256
                    and int(actual_table["rva"], 16) == CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA
                    and int(actual_table["slot_plus_0x30_target_rva"], 16)
                        == CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA
                    and actual_table["entries"][6]["target_rva"]
                        == hex(CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)
                    and override_doc["callback_and_dispatch"]["manager_global_rva"]
                        == hex(CURRENT_SCRIPT_MANAGER_GLOBAL_RVA)
                    and override_doc["callback_and_dispatch"]["actual_slot_rva"]
                        == hex(CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)
                    and override_doc["static_assertions"]["live_observation_table_matches_current_pe_table"] is True
                    and override_doc["static_assertions"]["live_observation_slot_plus_0x30_matches_current_pe_table"] is True
                    and override_live["path"].endswith("script-manager-live-pointers.json")
                    and override_live["bytes"] == CURRENT_V3_LIVE_POINTER_PIN[1]
                    and override_live["sha256"] == CURRENT_V3_LIVE_POINTER_PIN[2]
                    and override_live["table_rva"] == hex(CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA)
                    and override_live["slot_0x30_rva"] == hex(CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA)
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ScriptPathError("current v3 actual override proof is malformed") from exc
            if not override_static_profile:
                raise ScriptPathError("current v3 actual override proof does not match the selected profile")
        profile_id = CURRENT_V3_PROFILE_ID if current_v3 else CURRENT_PROFILE_ID
        profile_exe_sha = CURRENT_EXE_SHA256
        profile_core_sha = CURRENT_CORE_SHA256
        expected_vtable = None
        expected_method = None
    else:
        try:
            resolver_doc = json.loads(_read_bytes(proof_rows[1][0], "resolver source", limit=MAX_PROOF_BYTES))
            accessor = resolver_doc["path_redirector_service"]["accessor"]
            method = resolver_doc["path_redirector_service"]["vtable_method_plus_0x10"]
            static_entries = tuple(int(item, 16) for item in accessor["vtable_entries"])
            static_profile = (
                resolver_doc["schema"] == PHASE42_SCHEMA
                and resolver_doc["images"]["exe"]["sha256"] == EXE_SHA256
                and int(resolver_doc["images"]["exe"]["image_base"], 16) == EXE_IMAGE_BASE
                and int(accessor["singleton_global_va"], 16) == PATH_SINGLETON_GLOBAL_VA
                and int(accessor["vtable_va"], 16) == PATH_VTABLE_VA
                and static_entries == PATH_VTABLE_ENTRIES
                and int(method["function_va"], 16) == PATH_METHOD_VA
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ScriptPathError("resolver proof is not the retained Phase 42 Path_Redirector profile") from exc
        if proof_rows[1][1:] != (211343, PHASE42_SHA256) or not static_profile:
            raise ScriptPathError("resolver proof hash or source-backed address profile differs")
        profile_id = "xp2-exe-phase42-base"
        profile_exe_sha = EXE_SHA256
        profile_core_sha = XP2_SHA256
        expected_vtable = expected_module_address(PATH_VTABLE_VA)
        expected_method = expected_module_address(PATH_METHOD_VA)
    if live_values["singleton"] & 7:
        raise ScriptPathError("live path-copy singleton is not pointer aligned")
    if witness.get("psutil_version") != "7.1.0":
        raise ScriptPathError("witness process observer version is unsupported")
    if current_v3:
        if (witness.get("native_function_called") is not True
                or witness.get("native_method_called") is not True
                or witness.get("game_memory_written") is not None
                or witness.get("external_process_memory_write_performed") is not False
                or witness.get("native_resolver_state_changes_proven_absent") is not False
                or witness.get("filesystem_search_used") is not False
                or witness.get("filesystem_search_scope") != "capture_python_only"
                or any(witness.get(k) is not False for k in (
                    "process_environment_read", "historical_execution_bytes_proven",
                ))):
            raise ScriptPathError("v3 witness does not explicitly scope its native method call")
    elif any(witness.get(k) is not False for k in (
        "native_function_called", "game_memory_written", "process_environment_read",
        "filesystem_search_used", "historical_execution_bytes_proven",
    )):
        raise ScriptPathError("witness process/source scope flags are unsupported")

    # Bind the witness's ordered names and process identity back to the retained
    # memory-selection record, rather than trusting a separately edited list.
    selection_raw = _read_bytes(proof_rows[0][0], "selection witness", limit=MAX_SELECTION_BYTES)
    try:
        selection_doc = json.loads(selection_raw)
        selection_capture = selection_doc["gameplay_selection994"]
        selection_identity = _identity(selection_capture["process"])
        selection_paths = selection_capture["snapshot"]["selected_paths"]
        exe_module = selection_capture["exe_module"]
        snapshot = selection_capture["snapshot"]
        exe_path = exe_module["path"]
        exe_base = _strict_int(exe_module["base"], "selection EXE base", minimum=1)
        exe_size = _strict_int(exe_module["bytes"], "selection EXE size", minimum=1, maximum=MAX_IMAGE_BYTES)
        selection_exe_sha = snapshot["executable_sha256"]
        gamecore_sha = selection_capture["gamecore_module"]["sha256"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ScriptPathError("selection source proof lacks its ordered live selection") from exc
    if (selection_identity != identity or selection_paths != selected
            or not isinstance(exe_path, str) or os.path.normcase(os.path.normpath(exe_path)) != os.path.normcase(os.path.normpath(identity.image_path))
            or not isinstance(selection_exe_sha, str) or selection_exe_sha.lower() != profile_exe_sha
            or not isinstance(gamecore_sha, str) or gamecore_sha.lower() != profile_core_sha):
        raise ScriptPathError("selection source proof does not match witness process/order")
    if current_profile:
        expected_manager_vtable = (CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA if current_v3
                                   else CURRENT_SCRIPT_MANAGER_VTABLE_RVA)
        expected_manager_method = (CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA if current_v3
                                   else CURRENT_SCRIPT_MANAGER_WRAPPER_RVA)
        if (selection_capture.get("schema") != "civ6rl.official_gameplay_selection994.capture.v2"
                or snapshot.get("schema") != "civ6rl.gameplay_selection994.memory_snapshot.v2"
                or snapshot.get("current_correspondence_sha256") != CURRENT_SELECTION_SOURCE_SHA256
                or exe_base % 0x10000 or exe_size <= CURRENT_SINGLETON_GLOBAL_RVA + 8
                or live_values["vtable"] != exe_base + CURRENT_VTABLE_RVA
                or live_values["method"] != exe_base + CURRENT_METHOD_RVA
                or live_values["script_manager_vtable"] != exe_base + expected_manager_vtable
                or live_values["script_manager_slot_30"] != exe_base + expected_manager_method):
            raise ScriptPathError("current EXE dimensions or resolver addresses differ")
    elif exe_base != EXE_IMAGE_BASE or exe_size <= 0:
        raise ScriptPathError("selection EXE module dimensions are invalid")
    elif (live_values["vtable"] != expected_vtable or live_values["method"] != expected_method):
        raise ScriptPathError("live path-copy service differs from the historical EXE profile")

    native_resolved_paths: tuple[str, ...] | None = None
    if current_v3:
        report_row = witness.get("path_resolution_report")
        if not isinstance(report_row, Mapping):
            raise ScriptPathError("current v3 native path-resolution report pin is missing")
        report_pin = _read_file_pin(report_row, "current v3 path-resolution report")
        proof_rows.append(report_pin)
        report_raw = _read_bytes(report_pin[0], "current v3 path-resolution report", limit=MAX_PROOF_BYTES)
        if hashlib.sha256(report_raw).hexdigest() != report_pin[2] or len(report_raw) != report_pin[1]:
            raise ScriptPathError("current v3 path-resolution report changed while reading")
        try:
            report_doc = json.loads(report_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScriptPathError("current v3 path-resolution report is not valid JSON") from exc
        native_resolved_paths, native_proofs, capture_id = _validate_v3_resolution_report(
            report_doc, identity, selected, cwd, live_values["script_manager"], proof_rows[0]
        )
        if witness.get("capture_id") != capture_id:
            raise ScriptPathError("current v3 witness capture_id differs from its helper report")
        proof_rows.extend(native_proofs)

    selected_order: list[str] = []
    sources: list[ScriptSource] = []
    source_map: dict[str, ScriptSource] = {}
    for index, (raw_name, raw_source) in enumerate(zip(selected, resolved, strict=True)):
        name = _validate_selected_name(raw_name)
        if not isinstance(raw_source, Mapping):
            raise ScriptPathError(f"resolved source entry {index} is not an object")
        try:
            path = raw_source["path"]
            size = raw_source["bytes"]
            digest = raw_source["sha256"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ScriptPathError(f"resolved source entry {index} is incomplete") from exc
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ScriptPathError("resolved source path and SHA-256 must be strings")
        size = _strict_int(size, "resolved source byte count", minimum=0, maximum=MAX_SOURCE_BYTES)
        _validate_absolute_local(path, "resolved source path")
        digest = digest.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ScriptPathError("resolved source size or SHA-256 is invalid")
        expected_path = (native_resolved_paths[index] if native_resolved_paths is not None
                         else _cwd_join(cwd, name))
        if os.path.normcase(os.path.normpath(path)) != os.path.normcase(os.path.normpath(expected_path)):
            raise ScriptPathError("resolved source does not match the exact selected path")
        _utf16_bound(path)
        source = ScriptSource(name, path, size, digest)
        if name in source_map and source_map[name] != source:
            raise ScriptPathError("duplicate selected name maps to conflicting resolved sources")
        selected_order.append(name)
        sources.append(source)
        source_map[name] = source

    immutable_map = MappingProxyType(source_map)
    return ScriptPathContext(
        witness_sha256=witness_sha,
        process_identity=identity,
        cwd=cwd,
        selected_order=tuple(selected_order),
        source_by_selected=immutable_map,
        proof_files=tuple(proof_rows),
        source_files=tuple(sources),
        profile_id=profile_id,
        exe_base=exe_base,
        resolver_singleton=live_values["singleton"],
        script_manager=live_values.get("script_manager", 0),
        script_manager_vtable=live_values.get("script_manager_vtable", 0),
        script_manager_slot_30=live_values.get("script_manager_slot_30", 0),
    )


def validate_context(witness_pin: Any, processIdentity: Any) -> ScriptPathContext:
    """Validate a saved witness without consulting a live process or current directory."""
    witness, witness_sha = _load_witness(witness_pin)
    context = _parse_context(witness, witness_sha, _identity(processIdentity))
    _rehash_context_files(context)
    return context


def _check_live_observation(context: ScriptPathContext, cwd_reader: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> None:
    if not callable(cwd_reader):
        raise ScriptPathError("cwd_reader must be a callable process/CWD observer")
    try:
        expected_values = {
            "pid": context.process_identity.pid,
            "creation_filetime": context.process_identity.creation_filetime,
            "image_path": context.process_identity.image_path,
        }
        if context.profile_id in (CURRENT_PROFILE_ID, CURRENT_V3_PROFILE_ID):
            expected_values.update(profile_id=context.profile_id,
                                   exe_sha256=CURRENT_EXE_SHA256,
                                   gamecore_sha256=CURRENT_CORE_SHA256)
            if context.profile_id == CURRENT_V3_PROFILE_ID:
                expected_values["override_bindings_sha256"] = CURRENT_OVERRIDE_BINDINGS_SHA256
            else:
                expected_values["caller_bindings_sha256"] = CURRENT_CALLER_BINDINGS_SHA256
        expected = MappingProxyType(expected_values)
        observation = cwd_reader(expected)
    except Exception as exc:
        raise ScriptPathError("could not recheck the captured process identity and CWD") from exc
    if not isinstance(observation, Mapping) or not isinstance(observation.get("process"), Mapping):
        raise ScriptPathError("cwd_reader must return process identity and CWD")
    observed_identity = _identity(observation["process"])
    if observed_identity != context.process_identity:
        raise ScriptPathError("live process identity differs from the pinned process")
    if observation.get("cwd") != context.cwd:
        raise ScriptPathError("live process CWD differs from the pinned CWD")
    if context.profile_id in (CURRENT_PROFILE_ID, CURRENT_V3_PROFILE_ID):
        if observation.get("profile_id") != context.profile_id:
            raise ScriptPathError("live observer used a different resolver profile")
        live = observation.get("resolver_live")
        expected_manager_vtable_rva = (CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA
                                       if context.profile_id == CURRENT_V3_PROFILE_ID
                                       else CURRENT_SCRIPT_MANAGER_VTABLE_RVA)
        expected_manager_method_rva = (CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA
                                       if context.profile_id == CURRENT_V3_PROFILE_ID
                                       else CURRENT_SCRIPT_MANAGER_WRAPPER_RVA)
        if (not isinstance(live, Mapping)
                or live.get("vtable") != context.exe_base + CURRENT_VTABLE_RVA
                or live.get("method") != context.exe_base + CURRENT_METHOD_RVA
                or type(live.get("singleton")) is not int or live["singleton"] & 7
                or live["singleton"] != context.resolver_singleton
                or live.get("script_manager") != context.script_manager
                or live.get("script_manager_vtable") != context.exe_base + expected_manager_vtable_rva
                or live.get("script_manager_slot_30") != context.exe_base + expected_manager_method_rva
                or context.script_manager_vtable != context.exe_base + expected_manager_vtable_rva
                or context.script_manager_slot_30 != context.exe_base + expected_manager_method_rva):
            raise ScriptPathError("live current resolver pointers differ from the selected profile")


def _rehash_context_files(context: ScriptPathContext) -> None:
    from civ6_host.runtime.script_observer_sources import retained_observer_path

    for path, size, digest in context.proof_files:
        raw = _read_bytes(retained_observer_path(path, size, digest), "source proof")
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ScriptPathError("pinned source proof changed")
    seen: set[tuple[str, str]] = set()
    for source in context.source_files:
        key = (os.path.normcase(source.resolved_path), source.sha256)
        if key in seen:
            continue
        seen.add(key)
        _reject_reparse_components(Path(source.resolved_path))
        size, digest = _file_digest(Path(source.resolved_path))
        if size != source.bytes or digest != source.sha256:
            raise ScriptPathError("resolved source file differs from its pinned bytes and SHA-256")


def recheck_context(
    context: ScriptPathContext,
    *,
    cwd_reader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> ScriptPathContext:
    """Recheck process/CWD at capture time; never require the process in offline validation."""
    if not isinstance(context, ScriptPathContext):
        raise ScriptPathError("context was not produced by validate_context/load_context")
    _check_live_observation(context, cwd_reader)
    _rehash_context_files(context)
    return context


def load_context(
    pinned_witness: Any,
    processIdentity: Any,
    *,
    cwd_reader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> ScriptPathContext:
    """Validate a pinned witness and recheck its process/CWD during active capture."""
    context = validate_context(pinned_witness, processIdentity)
    return recheck_context(context, cwd_reader=cwd_reader)


def resolve_path(
    selected_name: str,
    context: ScriptPathContext,
    approved_roots: Sequence[str | os.PathLike[str]],
    *,
    cwd_reader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> ResolvedScriptPath:
    """Return the exact mapped Lua file after live identity, CWD, bounds, and root checks."""
    name = _validate_selected_name(selected_name)
    recheck_context(context, cwd_reader=cwd_reader)
    if name not in context.selected_order:
        raise ScriptPathError("selected name is absent from the pinned ordered selection")
    source = context.source_by_selected.get(name)
    if source is None or source.selected_name != name:
        raise ScriptPathError("selected name has no exact mapped source")

    candidate = Path(source.resolved_path)
    _reject_reparse_components(candidate)
    try:
        canonical = candidate.resolve(strict=True)
    except OSError as exc:
        raise ScriptPathError("mapped source cannot be canonicalized") from exc
    _validate_absolute_local(str(canonical), "canonical source path")
    _utf16_bound(str(canonical))
    if os.path.normcase(os.path.normpath(str(canonical))) != os.path.normcase(os.path.normpath(source.resolved_path)):
        raise ScriptPathError("canonical source path differs from the pinned exact mapping")

    if isinstance(approved_roots, (str, os.PathLike)) or not approved_roots:
        raise ScriptPathError("at least one explicit approved root is required")
    roots: list[str] = []
    for raw_root in approved_roots:
        root_text = os.fspath(raw_root)
        _validate_absolute_local(root_text, "approved root")
        root = Path(root_text)
        _reject_reparse_components(root)
        try:
            canonical_root = root.resolve(strict=True)
        except OSError as exc:
            raise ScriptPathError("approved root does not exist") from exc
        if not canonical_root.is_dir():
            raise ScriptPathError("approved root is not a directory")
        roots.append(str(canonical_root))
    if not any(_within(str(canonical), root) for root in roots):
        raise ScriptPathError("mapped source escapes all approved roots")

    size, digest = _file_digest(canonical)
    if size != source.bytes or digest != source.sha256:
        raise ScriptPathError("mapped Lua source no longer matches its pinned size and SHA-256")
    return ResolvedScriptPath(name, canonical, size, digest)


def observe_process_cwd(expected_identity: Any) -> Mapping[str, Any]:
    """Read process identity, CWD, and the selected path-copy pointers without writes."""
    expected = _identity(expected_identity)
    selected_profile = (expected_identity.get("profile_id")
                        if isinstance(expected_identity, Mapping) else None)
    current_profile = selected_profile in (CURRENT_PROFILE_ID, CURRENT_V3_PROFILE_ID)
    if current_profile and (
        expected_identity.get("exe_sha256") != CURRENT_EXE_SHA256
        or expected_identity.get("gamecore_sha256") != CURRENT_CORE_SHA256
    ):
        raise ScriptPathError("current resolver observation requires its exact EXE/Core identity")
    if selected_profile == CURRENT_PROFILE_ID and expected_identity.get(
        "caller_bindings_sha256"
    ) != CURRENT_CALLER_BINDINGS_SHA256:
        raise ScriptPathError("current v2 resolver observation requires its base caller proof identity")
    if selected_profile == CURRENT_V3_PROFILE_ID and expected_identity.get(
        "override_bindings_sha256"
    ) != CURRENT_OVERRIDE_BINDINGS_SHA256:
        raise ScriptPathError("current v3 resolver observation requires its actual override proof identity")
    if selected_profile not in (None, "xp2-exe-phase42-base", CURRENT_PROFILE_ID, CURRENT_V3_PROFILE_ID):
        raise ScriptPathError("unsupported script-path resolver profile")
    try:
        psutil = importlib.import_module("psutil")
        if getattr(psutil, "__version__", None) != "7.1.0":
            raise ScriptPathError("capture observer requires pinned psutil 7.1.0")
        worker = importlib.import_module("civ6_host.runtime.workers.capture_official_content929")
        ReadOnlyProcess = worker.ReadOnlyProcess
        with ReadOnlyProcess(expected.pid) as process:
            before = process.identity()
            if _identity(before) != expected:
                raise ScriptPathError("observed PID does not match expected process identity")
            modules = process.modules()
            matches = [m for m in modules if isinstance(m, Mapping)
                       and isinstance(m.get("path"), str)
                       and os.path.normcase(os.path.normpath(m["path"])) == os.path.normcase(os.path.normpath(expected.image_path))]
            if len(matches) != 1:
                raise ScriptPathError("expected exactly one pinned CivilizationVI EXE module")
            module = matches[0]
            base = _strict_int(module.get("base"), "EXE module base", minimum=1)
            image_bytes = _strict_int(module.get("bytes"), "EXE module bytes", minimum=1, maximum=MAX_IMAGE_BYTES)
            if current_profile:
                if (base % 0x10000 or image_bytes <= CURRENT_SINGLETON_GLOBAL_RVA + 8
                        or _image_digest(Path(expected.image_path)) != (CURRENT_EXE_SIZE_BYTES, CURRENT_EXE_SHA256)):
                    raise ScriptPathError("loaded current EXE differs from its pinned image")
                cores = [m for m in modules if isinstance(m, Mapping)
                         and isinstance(m.get("name"), str)
                         and m["name"].casefold().startswith("gamecore_")
                         and m["name"].casefold().endswith(".dll")]
                if len(cores) != 1 or _image_digest(Path(cores[0].get("path", ""))) != (12941080, CURRENT_CORE_SHA256):
                    raise ScriptPathError("loaded current GameCore differs from its pinned image")
                singleton_rva = CURRENT_SINGLETON_GLOBAL_RVA
                vtable_rva = CURRENT_VTABLE_RVA
                method_rva = CURRENT_METHOD_RVA
            else:
                if image_bytes < (PATH_SINGLETON_GLOBAL_VA - EXE_IMAGE_BASE):
                    raise ScriptPathError("loaded EXE module is too small for the pinned resolver global")
                singleton_rva = PATH_SINGLETON_GLOBAL_VA - EXE_IMAGE_BASE
                vtable_rva = PATH_VTABLE_VA - EXE_IMAGE_BASE
                method_rva = PATH_METHOD_VA - EXE_IMAGE_BASE
            def qword(address: int) -> int:
                return int.from_bytes(process.read(address, 8), "little", signed=False)
            singleton_storage = base + singleton_rva
            singleton = qword(singleton_storage)
            if singleton <= 0 or singleton & 7:
                raise ScriptPathError("live resolver singleton pointer is null or unaligned")
            table = qword(singleton)
            method = qword(table + 0x10) if table else 0
            expected_table = base + vtable_rva
            expected_method = base + method_rva
            if table != expected_table or method != expected_method:
                raise ScriptPathError("live resolver singleton/vtable/method differs from fixed Phase 42 profile")
            script_manager = script_manager_vtable = script_manager_slot_30 = 0
            if current_profile:
                script_manager = qword(base + CURRENT_SCRIPT_MANAGER_GLOBAL_RVA)
                if script_manager <= 0 or script_manager & 7:
                    raise ScriptPathError("current ScriptManager singleton is null or unaligned")
                script_manager_vtable = qword(script_manager)
                script_manager_slot_30 = qword(script_manager_vtable + CURRENT_SCRIPT_MANAGER_SLOT_OFFSET)
                expected_manager_vtable_rva = (CURRENT_V3_SCRIPT_MANAGER_VTABLE_RVA
                                               if selected_profile == CURRENT_V3_PROFILE_ID
                                               else CURRENT_SCRIPT_MANAGER_VTABLE_RVA)
                expected_manager_method_rva = (CURRENT_V3_SCRIPT_MANAGER_METHOD_RVA
                                               if selected_profile == CURRENT_V3_PROFILE_ID
                                               else CURRENT_SCRIPT_MANAGER_WRAPPER_RVA)
                if (script_manager_vtable != base + expected_manager_vtable_rva
                        or script_manager_slot_30 != base + expected_manager_method_rva):
                    raise ScriptPathError("live ScriptManager vtable slot +0x30 differs from its current EXE binding")
            native = psutil.Process(expected.pid)
            cwd_before = native.cwd()
            _validate_absolute_local(cwd_before, "observed process CWD")
            cwd_after = native.cwd()
            after = process.identity()
            pointers_after = (qword(singleton_storage), qword(singleton), qword(table + 0x10))
            if current_profile:
                manager_after = qword(base + CURRENT_SCRIPT_MANAGER_GLOBAL_RVA)
                manager_vtable_after = qword(manager_after) if manager_after else 0
                manager_slot_after = (qword(manager_vtable_after + CURRENT_SCRIPT_MANAGER_SLOT_OFFSET)
                                      if manager_vtable_after else 0)
                manager_pointers_after = (manager_after, manager_vtable_after, manager_slot_after)
            else:
                manager_pointers_after = (0, 0, 0)
            if (_identity(after) != expected or cwd_after != cwd_before
                    or pointers_after != (singleton, table, method)
                    or (current_profile and manager_pointers_after !=
                        (script_manager, script_manager_vtable, script_manager_slot_30))):
                raise ScriptPathError("process identity, CWD, or resolver pointers changed during observation")
        return MappingProxyType({
            "process": MappingProxyType(dict(before)),
            "cwd": cwd_before,
            "resolver_live": MappingProxyType({
                "singleton": singleton, "vtable": table, "method": method,
                **({"script_manager": script_manager,
                    "script_manager_vtable": script_manager_vtable,
                    "script_manager_slot_30": script_manager_slot_30}
                   if current_profile else {}),
            }),
            "profile_id": selected_profile or "xp2-exe-phase42-base",
            "psutil_version": psutil.__version__,
        })
    except ScriptPathError:
        raise
    except Exception as exc:
        raise ScriptPathError("read-only process/CWD observer failed") from exc

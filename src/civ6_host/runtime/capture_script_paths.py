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
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "civ6-host.official-script-path-base.v1"
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


def expected_module_address(va: int) -> int:
    """Translate a pinned EXE VA to the runtime address for its loaded image."""
    return EXE_IMAGE_BASE + (va - EXE_IMAGE_BASE)


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
    raw = _read_bytes(path, label, limit=MAX_PROOF_BYTES)
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


def _parse_context(witness: dict[str, Any], witness_sha: str, expected: ProcessIdentity) -> ScriptPathContext:
    if witness.get("schema") != SCHEMA or witness.get("status") != STATUS:
        raise ScriptPathError("unsupported or incomplete script-path witness")
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
    if not isinstance(selected, list) or not selected or not isinstance(resolved, list) or len(selected) != len(resolved):
        raise ScriptPathError("selected names and resolved sources must be nonempty, ordered one-to-one lists")

    proof_rows = []
    for key in ("selection_witness", "resolver_source", "observer"):
        row = witness.get(key)
        if not isinstance(row, Mapping):
            raise ScriptPathError(f"missing {key} source proof")
        proof_rows.append(_read_file_pin(row, key))

    # Verify the fixed, hash-pinned Phase 42 contract and its exact VA profile.
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
    expected_vtable = expected_module_address(PATH_VTABLE_VA)
    expected_method = expected_module_address(PATH_METHOD_VA)
    if live_values["vtable"] != expected_vtable or live_values["method"] != expected_method:
        raise ScriptPathError("live path-copy service vtable/method differs from the pinned EXE profile")
    if live_values["singleton"] & 7:
        raise ScriptPathError("live path-copy singleton is not pointer aligned")
    if witness.get("psutil_version") != "7.1.0" or any(witness.get(k) is not False for k in (
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
            or not isinstance(selection_exe_sha, str) or selection_exe_sha.lower() != EXE_SHA256
            or not isinstance(gamecore_sha, str) or gamecore_sha.lower() != XP2_SHA256):
        raise ScriptPathError("selection source proof does not match witness process/order")
    if exe_base != EXE_IMAGE_BASE or exe_size <= 0:
        raise ScriptPathError("selection EXE module dimensions are invalid")

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
        expected_path = _cwd_join(cwd, name)
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
        expected = MappingProxyType({
            "pid": context.process_identity.pid,
            "creation_filetime": context.process_identity.creation_filetime,
            "image_path": context.process_identity.image_path,
        })
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


def _rehash_context_files(context: ScriptPathContext) -> None:
    for path, size, digest in context.proof_files:
        raw = _read_bytes(path, "source proof")
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
    """Read process identity, CWD, and the fixed path-copy pointers without writes."""
    expected = _identity(expected_identity)
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
            if image_bytes < (PATH_SINGLETON_GLOBAL_VA - EXE_IMAGE_BASE):
                raise ScriptPathError("loaded EXE module is too small for the pinned resolver global")
            def qword(address: int) -> int:
                return int.from_bytes(process.read(address, 8), "little", signed=False)
            singleton_storage = base + (PATH_SINGLETON_GLOBAL_VA - EXE_IMAGE_BASE)
            singleton = qword(singleton_storage)
            if singleton <= 0 or singleton & 7:
                raise ScriptPathError("live resolver singleton pointer is null or unaligned")
            table = qword(singleton)
            method = qword(table + 0x10) if table else 0
            expected_table = base + (PATH_VTABLE_VA - EXE_IMAGE_BASE)
            expected_method = base + (PATH_METHOD_VA - EXE_IMAGE_BASE)
            if table != expected_table or method != expected_method:
                raise ScriptPathError("live resolver singleton/vtable/method differs from fixed Phase 42 profile")
            native = psutil.Process(expected.pid)
            cwd_before = native.cwd()
            _validate_absolute_local(cwd_before, "observed process CWD")
            cwd_after = native.cwd()
            after = process.identity()
            pointers_after = (qword(singleton_storage), qword(singleton), qword(table + 0x10))
            if (_identity(after) != expected or cwd_after != cwd_before
                    or pointers_after != (singleton, table, method)):
                raise ScriptPathError("process identity, CWD, or resolver pointers changed during observation")
        return MappingProxyType({
            "process": MappingProxyType(dict(before)),
            "cwd": cwd_before,
            "resolver_live": MappingProxyType({"singleton": singleton, "vtable": table, "method": method}),
            "psutil_version": psutil.__version__,
        })
    except ScriptPathError:
        raise
    except Exception as exc:
        raise ScriptPathError("read-only process/CWD observer failed") from exc

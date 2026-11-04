"""Read-only planning for relocatable private host resource bundles.

This module parses proof JSON and hashes explicitly pinned files. It never
imports or executes laboratory Python, copies resources, or chooses actions.
All roots are explicit so a plan cannot silently fall back to cwd or the lab.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ROOT_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
DEFAULT_HASH_BUFFER_BYTES = 1024 * 1024
MAX_PLAN_EXAMPLES = 24


class ResourcePlanError(ValueError):
    """The proof chain or explicit root configuration is invalid."""


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResourcePlanError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ResourcePlanError(f"non-finite JSON constant: {value}")


def _parse_json_object(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"),
                           object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ResourcePlanError(f"{label} is not readable JSON") from exc
    if type(value) is not dict:
        raise ResourcePlanError(f"{label} root must be an object")
    return value


def _sha256_text(value: object, label: str) -> str:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise ResourcePlanError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _absolute_directory(value: str | os.PathLike[str], label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ResourcePlanError(f"{label} must be an explicit absolute path")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourcePlanError(f"{label} must be an existing directory") from exc
    if not resolved.is_dir():
        raise ResourcePlanError(f"{label} must be an existing directory")
    return resolved


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _identity(stat_result) -> tuple[int, int, int, int]:
    return (stat_result.st_dev, stat_result.st_ino, stat_result.st_size,
            getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1e9)))


def _stream_hash(path: Path, buffer_bytes: int) -> tuple[str, int]:
    """Hash one resolved regular file, refusing replacement or mutation mid-read."""
    before = path.stat()
    try:
        with path.open("rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if _identity(opened) != _identity(before) or path.resolve(strict=True) != path:
                raise ResourcePlanError("file identity changed before hashing")
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = stream.read(buffer_bytes)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            after_open = os.fstat(stream.fileno())
        after_path = path.stat()
        if (_identity(opened) != _identity(after_open)
                or _identity(after_open) != _identity(after_path)
                or path.resolve(strict=True) != path):
            raise ResourcePlanError("file changed while hashing")
        if size != after_path.st_size:
            raise ResourcePlanError("file size changed while hashing")
        return digest.hexdigest(), size
    except (OSError, RuntimeError) as exc:
        raise ResourcePlanError("pinned file could not be read stably") from exc


def _read_hashed_json(path: Path, expected_sha256: str, expected_bytes: int | None,
                      label: str, buffer_bytes: int) -> tuple[dict, dict]:
    before = path.stat()
    digest = hashlib.sha256()
    chunks = []
    actual_bytes = 0
    try:
        with path.open("rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if _identity(opened) != _identity(before) or path.resolve(strict=True) != path:
                raise ResourcePlanError(f"{label} changed before verification")
            while True:
                chunk = stream.read(buffer_bytes)
                if not chunk:
                    break
                digest.update(chunk)
                chunks.append(chunk)
                actual_bytes += len(chunk)
            after_open = os.fstat(stream.fileno())
        after_path = path.stat()
        if (_identity(opened) != _identity(after_open)
                or _identity(after_open) != _identity(after_path)
                or path.resolve(strict=True) != path
                or actual_bytes != after_path.st_size):
            raise ResourcePlanError(f"{label} changed while being verified")
    except (OSError, RuntimeError) as exc:
        raise ResourcePlanError(f"{label} could not be read stably") from exc
    actual_sha = digest.hexdigest()
    if actual_sha != expected_sha256:
        raise ResourcePlanError(f"{label} digest differs")
    if expected_bytes is not None and actual_bytes != expected_bytes:
        raise ResourcePlanError(f"{label} byte count differs")
    value = _parse_json_object(b"".join(chunks), label)
    return value, {"path": str(path), "sha256": actual_sha, "bytes": actual_bytes}


def _explicit_path(raw: object, *, base: Path, label: str) -> Path:
    if isinstance(raw, os.PathLike):
        raw = os.fspath(raw)
    if type(raw) is not str or not raw:
        raise ResourcePlanError(f"{label} path must be a nonempty string")
    windows = PureWindowsPath(raw)
    parts = raw.replace("\\", "/").split("/")
    if ".." in parts:
        raise ResourcePlanError(f"{label} path contains parent traversal")
    if windows.drive and not Path(raw).is_absolute():
        raise ResourcePlanError(f"{label} Windows path cannot be resolved on this host")
    candidate = Path(raw) if Path(raw).is_absolute() else base / Path(raw.replace("\\", os.sep))
    if not candidate.is_absolute():
        raise ResourcePlanError(f"{label} path is not absolute after anchoring")
    try:
        return candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourcePlanError(f"{label} path does not exist") from exc


def _path_scope(raw: object, *, lab_root: Path, external_roots: dict[str, Path]):
    if type(raw) is not str or not raw:
        raise ResourcePlanError("pinned path must be a nonempty string")
    if ".." in raw.replace("\\", "/").split("/"):
        raise ResourcePlanError("pinned path contains parent traversal")
    raw_path = Path(raw)
    win_path = PureWindowsPath(raw)
    if win_path.drive and not raw_path.is_absolute():
        raise ResourcePlanError("Windows absolute pin cannot be resolved on this host")
    if raw_path.is_absolute():
        lexical = raw_path
    else:
        if win_path.root:
            raise ResourcePlanError("pinned path has a root without an explicit drive")
        lexical = lab_root / Path(raw.replace("\\", os.sep))
    matches = [("lab_local", lab_root)] if _within(lexical, lab_root) else []
    matches.extend((f"external:{name}", root) for name, root in external_roots.items()
                   if _within(lexical, root))
    if len(matches) != 1:
        return lexical, None, "unclassified_external" if raw_path.is_absolute() else "local_escape"
    classification, root = matches[0]
    try:
        canonical = lexical.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourcePlanError("pinned file is missing or cannot be resolved") from exc
    if not _within(canonical, root):
        return canonical, root, "symlink_escape"
    if not canonical.is_file():
        raise ResourcePlanError("pinned path is not a regular file")
    return canonical, root, classification


def _pin_role(raw: str, classification: str, lab_root: Path, native_run: Path) -> str:
    if classification.startswith("external:"):
        label = classification.split(":", 1)[1]
        if label == "game_installation":
            return "external_game_installation"
        if label == "user_mod_installation":
            return "external_user_mod"
        if label == "host_installation":
            return "installed_host_source_witness"
        return "external_dependency"
    path = Path(raw)
    if path.is_absolute():
        try:
            relative = path.relative_to(lab_root)
        except ValueError:
            return "local_path_reference"
    else:
        relative = Path(raw.replace("\\", os.sep))
    parts = [part.lower() for part in relative.parts]
    suffix = relative.suffix.lower()
    if _within(path if path.is_absolute() else lab_root / relative, native_run):
        return "old_session_output"
    if any(part in ("native-init-fixtures",) for part in parts):
        return "old_session_fixture_copy"
    if parts and parts[0] in ("civ6rl", "native", "tools"):
        return "historical_source_or_tool"
    if suffix in (".sqlite", ".db", ".dat", ".civ6save", ".lua", ".xml", ".dll"):
        return "resource_candidate"
    if parts and parts[0] in ("evidence", "work"):
        return "proof_or_historical_artifact"
    return "pinned_local_input"


def _pin_prefix(raw: str, classification: str, approved_root: Path) -> str:
    path = Path(raw)
    lexical = path if path.is_absolute() else approved_root / Path(raw.replace("\\", os.sep))
    try:
        relative = lexical.relative_to(approved_root)
    except ValueError:
        return classification
    parts = [part for part in relative.parts if part not in ("", ".")]
    return "/".join(parts[:3]) if parts else "."


def _controlled_close_exit(validation: dict, supervisor: dict) -> bool:
    """Accept worker exit 90 only when the proof records the requested close."""
    if (type(supervisor.get("exit_code")) is not int
            or supervisor.get("exit_code") != 90
            or supervisor.get("reaped") is not True
            or supervisor.get("timed_out") is not False
            or supervisor.get("error") is not None
            or supervisor.get("termination_inferred_from_process_exit") is not False):
        return False
    unchanged = supervisor.get("source_unchanged")
    if type(unchanged) is not dict or not unchanged or any(value is not True for value in unchanged.values()):
        return False
    comparisons = validation.get("comparisons")
    if (validation.get("status") != "installed_backend_native_parity_verified"
            or validation.get("backend_finished") is not True
            or validation.get("worker_reaped") is not True
            or type(comparisons) is not list):
        return False
    required = {"public_observation_equal", "catalogue_equal_except_episode_identity",
                "applied_action_equal", "outcome_equal"}
    return any(type(item) is dict and item.get("operation") == "close"
               and all(item.get(key) is True for key in required)
               for item in comparisons)


def plan_private_resources(*, validation_path: str | os.PathLike[str],
        expected_validation_sha256: str, expected_supervisor_sha256: str,
        expected_closure_sha256: str, lab_root: str | os.PathLike[str],
        external_roots: dict[str, str | os.PathLike[str]],
        hash_buffer_bytes: int = DEFAULT_HASH_BUFFER_BYTES) -> dict:
    """Verify a native-validation -> supervisor -> closure chain and pin files.

    ``external_roots`` is an explicit mapping such as ``game_installation`` or
    ``host_installation`` to absolute existing roots. No ambient cwd search or
    inferred external root is used. The returned plan is not a copy manifest:
    a separate consumer/use map must select runtime resources from proofs and
    historical source pins before any package is created.
    """
    expected_validation_sha256 = _sha256_text(expected_validation_sha256, "validation digest")
    expected_supervisor_sha256 = _sha256_text(expected_supervisor_sha256, "supervisor digest")
    expected_closure_sha256 = _sha256_text(expected_closure_sha256, "closure digest")
    if type(hash_buffer_bytes) is not int or not 4096 <= hash_buffer_bytes <= 16 * 1024 * 1024:
        raise ResourcePlanError("hash buffer must be bounded between 4 KiB and 16 MiB")
    lab = _absolute_directory(lab_root, "lab root")
    if type(external_roots) is not dict:
        raise ResourcePlanError("external roots must be an explicit name-to-path mapping")
    external = {}
    for name, value in external_roots.items():
        if type(name) is not str or not _ROOT_NAME.fullmatch(name) or name == "lab_local":
            raise ResourcePlanError("invalid external root name")
        external[name] = _absolute_directory(value, f"external root {name}")
    roots = {"lab_local": lab, **{f"external:{name}": path for name, path in external.items()}}
    root_items = list(roots.items())
    for index, (name, path) in enumerate(root_items):
        for other_name, other_path in root_items[index + 1:]:
            if _within(path, other_path) or _within(other_path, path):
                raise ResourcePlanError(f"resource roots overlap: {name} and {other_name}")

    validation_file = _explicit_path(validation_path, base=lab, label="native-validation")
    if not _within(validation_file, lab):
        raise ResourcePlanError("native-validation must remain inside lab root")
    validation, validation_record = _read_hashed_json(
        validation_file, expected_validation_sha256, None, "native-validation", hash_buffer_bytes)
    if type(validation.get("native_run")) is not str or type(validation.get("supervisor")) is not dict:
        raise ResourcePlanError("native-validation lacks its run or supervisor reference")
    run_path = _explicit_path(validation["native_run"], base=lab, label="native run")
    supervisor_ref = validation["supervisor"]
    supervisor_path = _explicit_path(supervisor_ref.get("path"), base=lab, label="supervisor")
    if (not _within(run_path, lab) or not _within(supervisor_path, run_path)
            or supervisor_path.parent != run_path):
        raise ResourcePlanError("supervisor path is outside the designated native run")
    if supervisor_ref.get("sha256") != expected_supervisor_sha256:
        raise ResourcePlanError("supervisor digest does not match the validation proof")
    supervisor, supervisor_record = _read_hashed_json(supervisor_path,
        expected_supervisor_sha256, supervisor_ref.get("bytes"), "supervisor", hash_buffer_bytes)
    closure_path = run_path / "closure.json"
    if not _within(closure_path, lab):
        raise ResourcePlanError("closure path is outside lab root")
    closure, closure_record = _read_hashed_json(closure_path, expected_closure_sha256,
        None, "designated closure", hash_buffer_bytes)
    closure_sha, closure_bytes = closure_record["sha256"], closure_record["bytes"]
    if type(closure) is not dict or type(closure.get("pins")) is not dict:
        raise ResourcePlanError("designated closure must contain a pin map")

    blockers: list[dict] = []
    blocker_counts: dict[str, int] = {}
    def add_blocker(code: str, detail: str):
        blocker_counts[code] = blocker_counts.get(code, 0) + 1
        if len(blockers) < MAX_PLAN_EXAMPLES:
            blockers.append({"code": code, "detail": detail[:500]})

    source_unchanged = supervisor.get("source_unchanged")
    supervisor_exit = supervisor.get("exit_code")
    controlled_close = supervisor_exit == 90 and _controlled_close_exit(validation, supervisor)
    if ((supervisor_exit != 0 and not controlled_close) or supervisor.get("reaped") is not True
            or supervisor.get("timed_out") is not False or supervisor.get("error") is not None
            or type(source_unchanged) is not dict or not source_unchanged
            or any(value is not True for value in source_unchanged.values())):
        add_blocker("supervisor_not_clean", "supervisor completion/source-integrity fields are not all successful")

    # The pinned artifacts are retained as proof references, not copied by this planner.
    proof_refs = [validation_record, supervisor_record,
                  {"path": str(closure_path), "sha256": closure_sha, "bytes": closure_bytes}]
    hash_cache: dict[Path, tuple[str, int]] = {
        validation_file: (validation_record["sha256"], validation_record["bytes"]),
        supervisor_path: (supervisor_record["sha256"], supervisor_record["bytes"]),
        closure_path.resolve(strict=True): (closure_sha, closure_bytes),
    }

    def verify_reference(raw_path, expected_hash, expected_bytes, label, expected_root=lab):
        try:
            candidate = _explicit_path(raw_path, base=lab, label=label)
            if not _within(candidate, expected_root):
                raise ResourcePlanError(f"{label} escapes its declared root")
            digest, size = hash_cache.get(candidate, (None, None))
            if digest is None:
                digest, size = _stream_hash(candidate, hash_buffer_bytes)
                hash_cache[candidate] = (digest, size)
            expected = _sha256_text(expected_hash, f"{label} digest")
            if digest != expected or (expected_bytes is not None and size != expected_bytes):
                raise ResourcePlanError(f"{label} digest or byte count differs")
            proof_refs.append({"path": str(candidate), "sha256": digest, "bytes": size})
        except ResourcePlanError as exc:
            add_blocker("proof_reference_invalid", f"{label}: {exc}")

    events = validation.get("reference_events")
    if type(events) is dict:
        verify_reference(events.get("path"), events.get("sha256"), events.get("bytes"),
                         "retained reference event proof")
    delivery = validation.get("reference_delivery")
    if type(delivery) is dict:
        verify_reference(delivery.get("path"), delivery.get("sha256"), delivery.get("bytes"),
                         "reference delivery proof")
    parent_locale = closure.get("parent_localization_validation")
    if type(parent_locale) is dict:
        verify_reference(parent_locale.get("path"), parent_locale.get("sha256"),
                         parent_locale.get("bytes"), "parent localization validation")
    official_bundle = closure.get("official_bundle")
    if type(official_bundle) is dict:
        verify_reference(official_bundle.get("path"), official_bundle.get("sha256"), None,
                         "official bundle manifest")
    fixture_info = closure.get("fixture_isolation")
    if type(fixture_info) is dict:
        verify_reference(fixture_info.get("source_manifest_path"),
                         fixture_info.get("source_manifest_sha256"), None,
                         "source fixture manifest")
        workers = fixture_info.get("workers")
        if type(workers) is list:
            for index, worker in enumerate(workers):
                if type(worker) is dict:
                    verify_reference(worker.get("manifest_path"), worker.get("manifest_sha256"), None,
                        f"worker fixture manifest {index}")

    logical_count = len(closure["pins"])
    role_counts: dict[str, int] = {}
    scope_counts: dict[str, int] = {}
    unique_bytes: dict[str, int] = {}
    unique_files: dict[str, int] = {}
    alias_count = 0
    verified_pin_count = 0
    verified_bytes = 0
    verified_by_scope: dict[str, int] = {}
    seen_canonical: dict[Path, tuple[str, str]] = {}
    pin_hashes_valid = True
    role_bytes: dict[str, int] = {}
    prefix_counts: dict[str, int] = {}
    prefix_bytes: dict[str, int] = {}
    absolute_prefix_counts: dict[str, int] = {}
    absolute_prefix_bytes: dict[str, int] = {}
    absolute_pin_entries = 0

    for raw, expected_digest in closure["pins"].items():
        if type(raw) is not str or type(expected_digest) is not str or not _SHA256.fullmatch(expected_digest):
            pin_hashes_valid = False
            add_blocker("invalid_pin_entry", "pin path or digest has an invalid type/format")
            continue
        try:
            canonical, approved_root, scope = _path_scope(raw, lab_root=lab, external_roots=external)
        except ResourcePlanError as exc:
            pin_hashes_valid = False
            add_blocker("invalid_pin_path", f"{raw}: {exc}")
            continue
        if scope in ("unclassified_external", "local_escape", "symlink_escape"):
            pin_hashes_valid = False
            add_blocker(scope, raw)
            continue
        role = _pin_role(raw, scope, lab, run_path)
        prefix = _pin_prefix(raw, scope, approved_root)
        scope_counts[scope] = scope_counts.get(scope, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
        raw_is_absolute = Path(raw).is_absolute() or PureWindowsPath(raw).is_absolute()
        if raw_is_absolute:
            absolute_pin_entries += 1
            absolute_prefix_counts[prefix] = absolute_prefix_counts.get(prefix, 0) + 1
        previous = seen_canonical.get(canonical)
        if previous is not None:
            alias_count += 1
            if previous[0] != expected_digest:
                pin_hashes_valid = False
                add_blocker("conflicting_alias_hashes", str(canonical))
            continue
        seen_canonical[canonical] = (expected_digest, scope)
        try:
            observed_digest, size = hash_cache.get(canonical, (None, None))
            if observed_digest is None:
                observed_digest, size = _stream_hash(canonical, hash_buffer_bytes)
                hash_cache[canonical] = (observed_digest, size)
            if observed_digest != expected_digest:
                pin_hashes_valid = False
                add_blocker("pin_hash_mismatch", raw)
                continue
            verified_pin_count += 1
            verified_bytes += size
            unique_files[scope] = unique_files.get(scope, 0) + 1
            unique_bytes[scope] = unique_bytes.get(scope, 0) + size
            role_bytes[role] = role_bytes.get(role, 0) + size
            prefix_bytes[prefix] = prefix_bytes.get(prefix, 0) + size
            if raw_is_absolute:
                absolute_prefix_bytes[prefix] = absolute_prefix_bytes.get(prefix, 0) + size
        except ResourcePlanError as exc:
            pin_hashes_valid = False
            add_blocker("pin_unreadable_or_unstable", f"{raw}: {exc}")

    if verified_pin_count < len(seen_canonical):
        pin_hashes_valid = False
    status = "verified_plan" if not blockers and verified_pin_count == len(seen_canonical) else "blocked"
    return {
        "schema": "civ6-host.private-resource-plan.v1",
        "status": status,
        "copy_performed": False,
        "lab_python_executed": False,
        "native_process_launched": False,
        "package_ready": False,
        "resource_selection_complete": False,
        "proofs": {
            "native_validation": validation_record,
            "supervisor": supervisor_record,
            "closure": {"path": str(closure_path), "sha256": closure_sha, "bytes": closure_bytes},
            "referenced_proofs_verified": proof_refs,
            "event_stream_policy": "retained in the lab as a private proof reference; not copied by this planner",
            "controlled_worker_close_exit": controlled_close,
        },
        "run": {
            "path": str(run_path),
            "schema": closure.get("schema"),
            "input_profile": closure.get("input_profile"),
            "rounds": closure.get("rounds"),
            "lifetime_seconds": closure.get("lifetime_seconds"),
            "official_bundle": official_bundle,
            "fixture": closure.get("fixture"),
            "pin_entries": logical_count,
            "unique_canonical_files_verified": verified_pin_count,
            "canonical_aliases": alias_count,
            "verified_bytes_streamed": verified_bytes,
        },
        "roots": {"lab_local": str(lab),
                  **{f"external:{name}": str(path) for name, path in external.items()}},
        "pin_scope_counts": dict(sorted(scope_counts.items())),
        "unique_files_by_scope": dict(sorted(unique_files.items())),
        "unique_bytes_by_scope": dict(sorted(unique_bytes.items())),
        "pin_role_counts": dict(sorted(role_counts.items())),
        "unique_bytes_by_role": dict(sorted(role_bytes.items())),
        "pin_prefix_summary": [
            {"prefix": prefix, "pin_entries": count,
             "unique_bytes_verified": prefix_bytes.get(prefix, 0)}
            for prefix, count in sorted(prefix_counts.items(),
                key=lambda item: (-item[1], item[0]))[:48]
        ],
        "absolute_path_pin_entries": absolute_pin_entries,
        "absolute_pin_prefix_summary": [
            {"prefix": prefix, "pin_entries": count,
             "unique_bytes_verified": absolute_prefix_bytes.get(prefix, 0)}
            for prefix, count in sorted(absolute_prefix_counts.items(),
                key=lambda item: (-item[1], item[0]))[:48]
        ],
        "pin_hashes_valid": pin_hashes_valid,
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "blockers": blockers,
        "relocation_analysis": {
            "absolute_path_references_require_mapping": True,
            "closure_and_supervisor_hashes_are_preserved_as_proof_data": True,
            "source_pin_map_is_not_rewritten": True,
            "resource_selection_reason": "The closure pin map mixes runtime inputs, historical source witnesses, evidence, and old-session outputs; use explicit consumer/resource manifests before selecting package contents.",
            "external_roots_are_references_not_copy_authority": True,
            "next_blockers": [
                "Build an explicit consumer map for installed host sources, official database/localization inputs, external game files, and old session copies/outputs.",
                "Add a separate relocation manifest mapping historical absolute pin keys to package-relative paths while keeping the original closure and proof hashes immutable.",
                "Recreate the disposable worker fixture from the identified source bundle only after the relocation manifest is reviewed."
            ],
        },
    }


def write_plan(plan: dict, output_path: str | os.PathLike[str]) -> Path:
    """Write a plan JSON to an explicit absolute path; never copy its inputs."""
    output = Path(output_path)
    if not output.is_absolute():
        raise ResourcePlanError("plan output path must be absolute")
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    temporary = output.with_name(output.name + ".tmp")
    encoded = json.dumps(plan, sort_keys=True, indent=2, ensure_ascii=False,
                         allow_nan=False).encode("utf-8") + b"\n"
    with temporary.open("wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(output)
    return output


def _external_root_argument(value: str) -> tuple[str, str]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("external root must be NAME=ABSOLUTE_PATH")
    return name, path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify and plan a private resource closure; does not copy files")
    parser.add_argument("--validation", required=True, help="native-validation JSON (absolute or lab-relative)")
    parser.add_argument("--validation-sha256", required=True)
    parser.add_argument("--supervisor-sha256", required=True)
    parser.add_argument("--closure-sha256", required=True)
    parser.add_argument("--lab-root", required=True)
    parser.add_argument("--external-root", action="append", type=_external_root_argument, default=[])
    parser.add_argument("--output", required=True, help="explicit absolute plan JSON output")
    args = parser.parse_args(argv)
    external = {}
    for name, path in args.external_root:
        if name in external:
            parser.error(f"duplicate external root: {name}")
        external[name] = path
    try:
        plan = plan_private_resources(validation_path=args.validation,
            expected_validation_sha256=args.validation_sha256,
            expected_supervisor_sha256=args.supervisor_sha256,
            expected_closure_sha256=args.closure_sha256,
            lab_root=args.lab_root, external_roots=external)
        path = write_plan(plan, args.output)
    except ResourcePlanError as exc:
        parser.error(str(exc))
    print(json.dumps({"status": plan["status"], "plan": str(path),
                      "verified_pin_files": plan["run"]["unique_canonical_files_verified"],
                      "blockers": plan["blocker_counts"]}, sort_keys=True))
    return 0 if plan["status"] == "verified_plan" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ResourcePlanError", "plan_private_resources", "write_plan", "main"]

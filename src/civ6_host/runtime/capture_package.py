"""Create and verify a compact private package from an admitted capture.

This module accepts a PreparedBundle already admitted by read_bundle. It does
not discover bundles, load native code, or execute laboratory Python.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat

SCHEMA = "civ6-host.prepared-capture.v1"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 4 * 1024 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024
_HEX = frozenset("0123456789abcdef")
_FILE_PATHS = {
    "configuration_stream": "configuration.bin",
    "gamecore_stream": "gamecore.bin",
    "database_configuration": "databases/configuration.sqlite",
    "database_gameplay": "databases/gameplay.sqlite",
    "database_localization": "databases/localization.sqlite",
    "icu_data": "icu.dat",
    "origin_manifest": "origin-manifest.json",
}
_DATABASE_ROLES = {
    "configuration": "database_configuration",
    "gameplay": "database_gameplay",
    "localization": "database_localization",
}


class CapturePackageError(ValueError):
    """The admitted capture or its package does not satisfy the wire format."""


def _sha256(value: object, label: str) -> str:
    if (type(value) is not str or len(value) != 64
            or any(char not in _HEX for char in value)):
        raise CapturePackageError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CapturePackageError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise CapturePackageError(f"non-finite JSON constant: {value}")


def _json_object(raw: bytes, label: str) -> dict:
    try:
        result = json.loads(raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs_no_duplicates, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CapturePackageError(f"{label} is not valid JSON") from exc
    if type(result) is not dict:
        raise CapturePackageError(f"{label} root must be an object")
    return result


def _json_value(value, label: str):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")
        if len(encoded) > MAX_MANIFEST_BYTES:
            raise CapturePackageError(f"{label} exceeds the manifest size limit")
        json.loads(encoded.decode("ascii"), object_pairs_hook=_pairs_no_duplicates,
                   parse_constant=_reject_constant)
        return value
    except CapturePackageError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CapturePackageError(f"{label} is not JSON-compatible") from exc


def _identity(info) -> tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size,
            getattr(info, "st_mtime_ns", int(info.st_mtime * 1e9)))


def _require_new_package_target(target: Path) -> None:
    root = target.parent.parent if target.parent.name == "databases" else target.parent
    try:
        if root.resolve(strict=True) != root or target.parent.resolve(strict=True) != target.parent:
            raise CapturePackageError("package output path was redirected")
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError("package output parent is unavailable") from exc
    if not _within(target.parent, root) or target.exists() or target.is_symlink():
        raise CapturePackageError("package output target is not a new in-root file")


def _canonical_file(value: object, label: str) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise CapturePackageError(f"{label} path must be a string or Path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise CapturePackageError(f"{label} path must be absolute without parent traversal")
    try:
        resolved = path.resolve(strict=True)
        info = path.lstat()
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError(f"{label} file is unavailable") from exc
    if resolved != path or stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise CapturePackageError(f"{label} must be a canonical regular file, not a redirected link")
    if info.st_size < 0 or info.st_size > MAX_FILE_BYTES:
        raise CapturePackageError(f"{label} exceeds the file size limit")
    return path


def _origin_source_path(reference_path: object, expected_sha: str,
                        dependencies: object) -> Path:
    if type(reference_path) is not str or not reference_path:
        raise CapturePackageError("bundle origin path must be a nonempty reference string")
    relative = PureWindowsPath(reference_path.replace("/", "\\"))
    if ".." in relative.parts:
        raise CapturePackageError("bundle origin reference contains parent traversal")
    if relative.is_absolute() or relative.drive:
        candidate = _canonical_file(reference_path, "bundle origin manifest")
        if _hash_file(candidate)[0] != expected_sha:
            raise CapturePackageError("source manifest changed after bundle admission")
        return candidate
    if type(dependencies) is not dict:
        raise CapturePackageError("admitted bundle lacks its source dependency pins")
    suffix = tuple(part.casefold() for part in relative.parts)
    matches = []
    for raw_path, digest in dependencies.items():
        if type(raw_path) is not str or digest != expected_sha:
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            continue
        candidate_parts = tuple(part.casefold() for part in candidate.parts)
        if len(candidate_parts) >= len(suffix) and candidate_parts[-len(suffix):] == suffix:
            matches.append(candidate)
    canonical = {_canonical_file(path, "bundle origin manifest") for path in matches}
    if len(canonical) != 1:
        raise CapturePackageError("bundle origin reference does not resolve to one pinned dependency")
    origin_path = next(iter(canonical))
    if _hash_file(origin_path)[0] != expected_sha:
        raise CapturePackageError("source manifest changed after bundle admission")
    return origin_path


def _copy_stream(source: Path, target: Path, expected_sha: str,
                 expected_bytes: int) -> dict:
    source = _canonical_file(source, "capture input")
    _require_new_package_target(target)
    if type(expected_bytes) is not int or not 0 < expected_bytes <= MAX_FILE_BYTES:
        raise CapturePackageError("capture input byte count is outside the package limit")
    before = source.stat()
    digest = hashlib.sha256()
    copied = 0
    try:
        with source.open("rb", buffering=0) as reader, target.open("xb", buffering=0) as writer:
            opened = os.fstat(reader.fileno())
            if _identity(before) != _identity(opened):
                raise CapturePackageError("capture input changed before copy")
            while True:
                chunk = reader.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                writer.write(chunk)
                digest.update(chunk)
                copied += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
            after_open = os.fstat(reader.fileno())
        after_path = source.stat()
        if (_identity(opened) != _identity(after_open)
                or _identity(after_open) != _identity(after_path)
                or source.resolve(strict=True) != source or copied != after_path.st_size):
            raise CapturePackageError("capture input changed while copying")
    except CapturePackageError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError("capture input could not be copied stably") from exc
    actual = digest.hexdigest()
    if actual != expected_sha or copied != expected_bytes:
        raise CapturePackageError("capture input hash or size differs from admitted bundle")
    return {"path": _FILE_PATHS_FOR_TARGET(target), "sha256": actual, "bytes": copied}


def _FILE_PATHS_FOR_TARGET(target: Path) -> str:
    # The caller writes only fixed package paths; this keeps file records relative.
    name = target.name
    if target.parent.name == "databases":
        return f"databases/{name}"
    return name


def _copy_bytes(data: bytes, target: Path, expected_sha: str,
                expected_bytes: int) -> dict:
    _require_new_package_target(target)
    if type(data) is not bytes or type(expected_bytes) is not int:
        raise CapturePackageError("in-memory capture stream has invalid type")
    if not 0 < len(data) <= MAX_FILE_BYTES or len(data) != expected_bytes:
        raise CapturePackageError("in-memory capture stream size differs or exceeds the limit")
    digest = hashlib.sha256()
    try:
        with target.open("xb", buffering=0) as writer:
            view = memoryview(data)
            for offset in range(0, len(data), HASH_CHUNK_BYTES):
                chunk = view[offset:offset + HASH_CHUNK_BYTES]
                writer.write(chunk)
                digest.update(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    except OSError as exc:
        raise CapturePackageError("in-memory capture stream could not be written") from exc
    actual = digest.hexdigest()
    if actual != expected_sha:
        raise CapturePackageError("in-memory capture stream hash differs from admitted bundle")
    return {"path": _FILE_PATHS_FOR_TARGET(target), "sha256": actual, "bytes": len(data)}


def _file_record(value: object, label: str) -> tuple[Path, str, int]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        raise CapturePackageError(f"{label} record has an unexpected shape")
    path = _canonical_file(value["path"], label)
    digest = _sha256(value["sha256"], f"{label} digest")
    size = value["size_bytes"]
    if type(size) is not int or not 0 < size <= MAX_FILE_BYTES:
        raise CapturePackageError(f"{label} byte count is outside the package limit")
    return path, digest, size


def _icu_record(value: object) -> tuple[Path, str, int]:
    if type(value) is not dict or not {"path", "sha256"}.issubset(value):
        raise CapturePackageError("ICU data record is malformed")
    if set(value) - {"path", "sha256", "bytes", "size_bytes"}:
        raise CapturePackageError("ICU data record has unexpected fields")
    path = _canonical_file(value["path"], "ICU data")
    digest = _sha256(value["sha256"], "ICU data digest")
    observed_size = path.stat().st_size
    for field in ("bytes", "size_bytes"):
        if field in value and (type(value[field]) is not int or value[field] != observed_size):
            raise CapturePackageError("ICU data byte count differs from captured identity")
    if not 0 < observed_size <= MAX_FILE_BYTES:
        raise CapturePackageError("ICU data byte count is outside the package limit")
    return path, digest, observed_size


def _read_stable_bytes(path: Path, limit: int, label: str) -> tuple[bytes, str, int]:
    path = _canonical_file(path, label)
    before = path.stat()
    digest = hashlib.sha256()
    chunks = []
    size = 0
    try:
        with path.open("rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if _identity(before) != _identity(opened):
                raise CapturePackageError(f"{label} changed before reading")
            while True:
                chunk = stream.read(min(HASH_CHUNK_BYTES, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise CapturePackageError(f"{label} exceeds its size limit")
                digest.update(chunk)
                chunks.append(chunk)
            after_open = os.fstat(stream.fileno())
        after_path = path.stat()
    except CapturePackageError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError(f"{label} could not be read stably") from exc
    if (_identity(opened) != _identity(after_open)
            or _identity(after_open) != _identity(after_path)
            or path.resolve(strict=True) != path or size != after_path.st_size):
        raise CapturePackageError(f"{label} changed while reading")
    return b"".join(chunks), digest.hexdigest(), size


def _manifest_bytes(manifest: dict) -> bytes:
    try:
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CapturePackageError("package manifest is not JSON-compatible") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise CapturePackageError("package manifest exceeds the size limit")
    return raw


def _validate_readback(value: object, initial_turn: int) -> None:
    if type(value) is not dict or set(value) != {
            "turn", "width", "height", "player_id", "gold", "city_count", "units"}:
        raise CapturePackageError("expected readback has an unexpected shape")
    if (type(value["turn"]) is not int or value["turn"] != initial_turn
            or type(value["width"]) is not int or not 1 <= value["width"] <= 16384
            or type(value["height"]) is not int or not 1 <= value["height"] <= 16384
            or value["width"] * value["height"] > 16384
            or type(value["player_id"]) is not int or value["player_id"] != 0
            or type(value["gold"]) is not int or not 0 <= value["gold"] <= 2**31 - 1
            or type(value["city_count"]) is not int or not 0 <= value["city_count"] <= 16384):
        raise CapturePackageError("expected readback values are outside supported bounds")
    units = value["units"]
    unit_fields = {"id", "type", "x", "y", "damage", "moves"}
    if type(units) is not list or len(units) > 16384:
        raise CapturePackageError("expected readback unit list exceeds its bound")
    identifiers = set()
    for unit in units:
        if type(unit) is not dict or set(unit) != unit_fields:
            raise CapturePackageError("expected readback unit has an unexpected shape")
        if any(type(unit[key]) is not int for key in unit_fields):
            raise CapturePackageError("expected readback unit fields must be integers")
        if (not 0 <= unit["id"] <= 2**31 - 1 or not 0 <= unit["type"] <= 2**31 - 1
                or not 0 <= unit["x"] < value["width"] or not 0 <= unit["y"] < value["height"]
                or not 0 <= unit["damage"] <= 100 or not 0 <= unit["moves"] <= 2**31 - 1
                or unit["id"] in identifiers):
            raise CapturePackageError("expected readback unit values are outside supported bounds")
        identifiers.add(unit["id"])


def export_capture(bundle, destination, *, source_manifest_bytes,
                   validation_identity, _xp1_candidate=False, _candidate_profile=None) -> dict:
    """Write a new private package from an already-admitted PreparedBundle."""
    if type(source_manifest_bytes) is not bytes or not 0 < len(source_manifest_bytes) <= MAX_MANIFEST_BYTES:
        raise CapturePackageError("source manifest must be bounded immutable bytes")
    source_manifest = _json_object(source_manifest_bytes, "source manifest")
    del source_manifest
    validation_identity = _json_value(validation_identity, "validation identity")

    try:
        reference_path, reference_sha = bundle.reference
        inputs = bundle.inputs
        profile = inputs.profile
        fixture = bundle.fixture
        dependencies = bundle.dependencies
        databases = fixture["databases"]
        localization = fixture["localization_bootstrap"]
        engine_path = Path(bundle.engine_path)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise CapturePackageError("bundle is not an admitted PreparedBundle shape") from exc

    reference_sha = _sha256(reference_sha, "bundle origin digest")
    origin_manifest_sha = hashlib.sha256(source_manifest_bytes).hexdigest()
    if origin_manifest_sha != reference_sha:
        raise CapturePackageError("provided source manifest bytes differ from bundle reference")
    origin_path = _origin_source_path(reference_path, reference_sha, dependencies)
    if type(fixture) is not dict or set(databases) != set(_DATABASE_ROLES):
        raise CapturePackageError("bundle fixture does not contain the three required databases")
    input_profile = fixture.get("input_profile")
    from .capture_profiles import CAPTURE_MODES
    from .capture_candidates import select_private_candidate
    try:
        candidate = select_private_candidate(xp1_candidate=_xp1_candidate,
                                              candidate_profile=_candidate_profile)
    except ValueError as exc:
        raise CapturePackageError(str(exc)) from exc
    modes = dict(CAPTURE_MODES)
    if candidate is not None:
        if bundle.reference != candidate.reference:
            label = 'XP1' if candidate.family == 'xp1-lan' else 'XP2'
            raise CapturePackageError('Candidate package must name the exact ' + label + ' capture')
        candidate.validate_inputs(inputs, bundle)
        modes = {candidate.family: 'LAN'}
    if type(input_profile) is not str or input_profile not in modes:
        raise CapturePackageError("unsupported input profile")
    expected_mode = modes[input_profile]
    if getattr(profile, "mode_name", None) != expected_mode:
        raise CapturePackageError("bundle input profile differs from its admitted loader profile")
    initial_turn = bundle.initial_turn
    if type(initial_turn) is not int or not 1 <= initial_turn <= 100000:
        raise CapturePackageError("initial turn is outside the package bound")
    if type(inputs.configuration) is not bytes or type(inputs.game) is not bytes:
        raise CapturePackageError("bundle streams must be immutable bytes")
    configuration_sha = hashlib.sha256(inputs.configuration).hexdigest()
    gamecore_sha = hashlib.sha256(inputs.game).hexdigest()
    expected_readback = _json_value(bundle.expected_readback, "expected readback")
    content_profile = _json_value(bundle.content_profile, "content profile")
    if type(expected_readback) is not dict or type(content_profile) is not dict:
        raise CapturePackageError("readback and content profile must be objects")
    _validate_readback(expected_readback, initial_turn)
    if content_profile.get("schema") != "civ6rl.official_content_profile.v1":
        raise CapturePackageError("bundle content profile schema is unsupported")
    map_values = inputs.map_values
    if type(map_values) not in (tuple, list) or len(map_values) != 4:
        raise CapturePackageError("bundle map values must contain the four admitted settings")
    serialized_maps = []
    for pair in map_values:
        if type(pair) not in (tuple, list) or len(pair) != 2:
            raise CapturePackageError("bundle map value must be a name/value pair")
        name, value = pair
        if type(name) is not str or (value is not None and type(value) is not int):
            raise CapturePackageError("bundle map value has an invalid type")
        if value is not None and not -(2**31) <= value <= 2**31 - 1:
            raise CapturePackageError("bundle map value exceeds the signed integer bound")
        serialized_maps.append([name, value])
    if len({item[0] for item in serialized_maps}) != 4:
        raise CapturePackageError("bundle map values contain duplicate names")
    if {item[0] for item in serialized_maps} != {"start", "world_age", "RANDOM_SEED", "MAP_SIZE"}:
        raise CapturePackageError("bundle map values do not match the admitted settings")

    engine_path = _canonical_file(engine_path, "external engine")
    try:
        engine_sha = _sha256(dependencies[str(engine_path)], "engine dependency digest")
        content_engine_sha = _sha256(content_profile["engine"]["gamecore_sha256"],
                                     "content profile engine digest")
    except (KeyError, TypeError) as exc:
        raise CapturePackageError("admitted bundle does not pin its external engine") from exc
    if engine_sha != content_engine_sha:
        raise CapturePackageError("engine pins differ between bundle and content profile")
    observed_engine_sha, _observed_engine_bytes = _hash_file(engine_path)
    if observed_engine_sha != engine_sha:
        raise CapturePackageError("external engine changed after bundle admission")

    if type(localization) is not dict or type(localization.get("icu_data")) is not dict:
        raise CapturePackageError("bundle localization bootstrap is malformed")
    _json_value(localization, "localization bootstrap")
    if (type(localization.get("locale")) is not str or not 0 < len(localization["locale"]) <= 128
            or type(localization.get("dictionary_flag")) is not bool):
        raise CapturePackageError("bundle localization identity is malformed")
    icu_path, icu_sha, icu_bytes = _icu_record(localization["icu_data"])
    expected_localization_profile = {"locale": localization["locale"],
        "dictionary_flag": localization["dictionary_flag"], "icu_sha256": icu_sha}
    if content_profile.get("localization_bootstrap") != expected_localization_profile:
        raise CapturePackageError("bundle localization bootstrap differs from content profile")
    database_records = {role: _file_record(databases[role], f"{role} database")
                        for role in _DATABASE_ROLES}
    total_size = (len(inputs.configuration) + len(inputs.game) + len(source_manifest_bytes)
                  + icu_bytes
                  + sum(item[2] for item in database_records.values()))
    if total_size > MAX_TOTAL_FILE_BYTES:
        raise CapturePackageError("capture package inputs exceed the aggregate size limit")

    destination = Path(destination)
    if not destination.is_absolute() or destination.name in ("", ".", ".."):
        raise CapturePackageError("package destination must be an explicit absolute directory")
    try:
        parent = destination.parent.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError("package destination parent must exist") from exc
    if destination.parent != parent:
        raise CapturePackageError("package destination parent must be canonical")
    if destination.exists() or destination.is_symlink():
        raise CapturePackageError("package destination already exists")
    try:
        destination.mkdir()
    except OSError as exc:
        raise CapturePackageError("package destination could not be created exclusively") from exc
    database_dir = destination / "databases"
    database_dir.mkdir()
    try:
        files = {}
        files["configuration_stream"] = _copy_bytes(inputs.configuration, destination / "configuration.bin",
            configuration_sha, len(inputs.configuration))
        files["gamecore_stream"] = _copy_bytes(inputs.game, destination / "gamecore.bin",
            gamecore_sha, len(inputs.game))
        for source_role, file_role in _DATABASE_ROLES.items():
            source, digest, size = database_records[source_role]
            files[file_role] = _copy_stream(source, destination / _FILE_PATHS[file_role],
                                             digest, size)
        files["icu_data"] = _copy_stream(icu_path, destination / _FILE_PATHS["icu_data"],
                                         icu_sha, icu_bytes)
        files["origin_manifest"] = _copy_bytes(source_manifest_bytes,
            destination / _FILE_PATHS["origin_manifest"], origin_manifest_sha,
            len(source_manifest_bytes))

        localization_copy = json.loads(json.dumps(localization, sort_keys=True,
            ensure_ascii=True, allow_nan=False))
        localization_copy["icu_data"]["path"] = _FILE_PATHS["icu_data"]
        localization_copy["icu_data"]["bytes"] = icu_bytes
        manifest = {
            "schema": SCHEMA,
            "origin": {"path": reference_path, "sha256": reference_sha},
            "origin_manifest_sha256": origin_manifest_sha,
            "input_profile": input_profile,
            "initial_turn": initial_turn,
            "expected_readback": expected_readback,
            "content_profile": content_profile,
            "map_values": serialized_maps,
            "engine": {"path": str(engine_path), "sha256": engine_sha},
            "validation_identity": validation_identity,
            "localization_bootstrap": localization_copy,
            "files": files,
        }
        raw_manifest = _manifest_bytes(manifest)
        manifest_path = destination / "manifest.json"
        _require_new_package_target(manifest_path)
        with manifest_path.open("xb", buffering=0) as stream:
            stream.write(raw_manifest)
            stream.flush()
            os.fsync(stream.fileno())
        return {"path": str(manifest_path), "sha256": hashlib.sha256(raw_manifest).hexdigest()}
    except BaseException:
        # Leave failed output for inspection; no reference is returned and a new
        # destination is required for the next attempt.
        raise


def _hash_file(path: Path) -> tuple[str, int]:
    path = _canonical_file(path, "file")
    before = path.stat()
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if _identity(before) != _identity(opened):
                raise CapturePackageError("file changed before hashing")
            while True:
                chunk = stream.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
            after_open = os.fstat(stream.fileno())
        after_path = path.stat()
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError("file could not be hashed stably") from exc
    if (_identity(opened) != _identity(after_open) or _identity(after_open) != _identity(after_path)
            or path.resolve(strict=True) != path or size != after_path.st_size):
        raise CapturePackageError("file changed while hashing")
    return digest.hexdigest(), size


def _relative_package_file(root: Path, value: object, expected: str) -> Path:
    if type(value) is not str or value != expected:
        raise CapturePackageError("package file role has an unexpected relative path")
    pure = PureWindowsPath(value)
    path = Path(value)
    if pure.is_absolute() or path.is_absolute() or ".." in pure.parts or ".." in path.parts:
        raise CapturePackageError("package file path escapes its root")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        info = candidate.lstat()
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError("package file is unavailable") from exc
    if (not _within(resolved, root) or resolved != candidate or stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)):
        raise CapturePackageError("package file is a symlink or escapes its root")
    return candidate


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def read_package(reference, *, _xp1_candidate=False, _candidate_profile=None) -> tuple[dict, Path, dict[str, Path]]:
    """Verify the package manifest, every local file and its external engine."""
    if type(reference) is not dict or set(reference) != {"path", "sha256"}:
        raise CapturePackageError("package reference has an unexpected shape")
    manifest_sha = _sha256(reference["sha256"], "package manifest digest")
    manifest_path = _canonical_file(reference["path"], "package manifest")
    if manifest_path.name != "manifest.json":
        raise CapturePackageError("package reference must name manifest.json")
    root = manifest_path.parent
    try:
        root_resolved = root.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CapturePackageError("package root is unavailable") from exc
    if root != root_resolved:
        raise CapturePackageError("package root is redirected")
    raw_manifest, observed_manifest_sha, _ = _read_stable_bytes(
        manifest_path, MAX_MANIFEST_BYTES, "package manifest")
    if observed_manifest_sha != manifest_sha:
        raise CapturePackageError("package manifest hash differs")
    manifest = _json_object(raw_manifest, "package manifest")
    if manifest.get("schema") != SCHEMA:
        raise CapturePackageError("unsupported capture package schema")
    expected_keys = {"schema", "origin", "origin_manifest_sha256", "input_profile",
        "initial_turn", "expected_readback", "content_profile", "map_values", "engine",
        "validation_identity", "localization_bootstrap", "files"}
    if set(manifest) != expected_keys:
        raise CapturePackageError("package manifest has unexpected fields")
    origin = manifest.get("origin")
    origin_sha = _sha256(manifest.get("origin_manifest_sha256"), "origin manifest digest")
    origin_path = origin.get("path") if type(origin) is dict else None
    origin_relative = PureWindowsPath(origin_path.replace("/", "\\")) if type(origin_path) is str else None
    if (type(origin) is not dict or set(origin) != {"path", "sha256"}
            or type(origin_path) is not str or not origin_path
            or (not origin_relative.is_absolute()
                and (origin_relative.drive or ".." in origin_relative.parts))
            or _sha256(origin.get("sha256"), "origin reference digest") != origin_sha):
        raise CapturePackageError("package origin reference is malformed or inconsistent")
    profile = manifest.get("input_profile")
    turn = manifest.get("initial_turn")
    from .capture_profiles import CAPTURE_MODES
    from .capture_candidates import select_private_candidate
    try:
        candidate = select_private_candidate(xp1_candidate=_xp1_candidate,
                                              candidate_profile=_candidate_profile)
    except ValueError as exc:
        raise CapturePackageError(str(exc)) from exc
    modes = dict(CAPTURE_MODES)
    if candidate is not None:
        if (origin['path'], origin['sha256']) != candidate.reference:
            label = 'XP1' if candidate.family == 'xp1-lan' else 'XP2'
            raise CapturePackageError('Candidate package must name the exact ' + label + ' capture')
        modes = {candidate.family: 'LAN'}
    if type(profile) is not str or profile not in modes or type(turn) is not int or not 1 <= turn <= 100000:
        raise CapturePackageError("package profile or turn is outside the supported bound")
    if type(manifest.get("expected_readback")) is not dict or type(manifest.get("content_profile")) is not dict:
        raise CapturePackageError("package readback/content profile must be objects")
    _validate_readback(manifest["expected_readback"], turn)
    if manifest["content_profile"].get("schema") != "civ6rl.official_content_profile.v1":
        raise CapturePackageError("package content profile schema is unsupported")
    maps = manifest.get("map_values")
    if (type(maps) is not list or len(maps) != 4
            or any(type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str
                   or (pair[1] is not None and type(pair[1]) is not int) for pair in maps)
            or len({pair[0] for pair in maps}) != 4
            or {pair[0] for pair in maps} != {"start", "world_age", "RANDOM_SEED", "MAP_SIZE"}
            or any(pair[1] is not None and not -(2**31) <= pair[1] <= 2**31 - 1 for pair in maps)):
        raise CapturePackageError("package map values are malformed")
    _json_value(manifest.get("validation_identity"), "validation identity")
    localization = manifest.get("localization_bootstrap")
    if (type(localization) is not dict or type(localization.get("icu_data")) is not dict
            or type(localization.get("locale")) is not str
            or not 0 < len(localization["locale"]) <= 128
            or type(localization.get("dictionary_flag")) is not bool):
        raise CapturePackageError("package localization bootstrap is malformed")
    if localization["icu_data"].get("path") != _FILE_PATHS["icu_data"]:
        raise CapturePackageError("package ICU path was not relocated")
    icu_digest = _sha256(localization["icu_data"].get("sha256"), "package ICU digest")
    if type(localization["icu_data"].get("bytes")) is not int or not 0 < localization["icu_data"]["bytes"] <= MAX_FILE_BYTES:
        raise CapturePackageError("package ICU size is malformed")
    if manifest["content_profile"].get("localization_bootstrap") != {
            "locale": localization["locale"],
            "dictionary_flag": localization["dictionary_flag"],
            "icu_sha256": icu_digest}:
        raise CapturePackageError("package localization bootstrap differs from content profile")
    engine = manifest.get("engine")
    if type(engine) is not dict or set(engine) != {"path", "sha256"}:
        raise CapturePackageError("external engine reference is malformed")
    engine_path = _canonical_file(engine["path"], "external engine")
    engine_sha = _sha256(engine["sha256"], "external engine digest")
    try:
        if _sha256(manifest["content_profile"]["engine"]["gamecore_sha256"],
                   "content profile engine digest") != engine_sha:
            raise CapturePackageError("external engine differs from content profile")
    except (KeyError, TypeError) as exc:
        raise CapturePackageError("content profile does not pin external engine") from exc
    if _hash_file(engine_path)[0] != engine_sha:
        raise CapturePackageError("external engine changed since package export")

    files = manifest.get("files")
    if type(files) is not dict or set(files) != set(_FILE_PATHS):
        raise CapturePackageError("package file role map is incomplete or unexpected")
    verified_files = {}
    total = 0
    for role, expected_path in _FILE_PATHS.items():
        record = files[role]
        if type(record) is not dict or set(record) != {"path", "sha256", "bytes"}:
            raise CapturePackageError(f"package file record is malformed: {role}")
        path = _relative_package_file(root, record["path"], expected_path)
        expected_digest = _sha256(record["sha256"], f"{role} digest")
        expected_bytes = record["bytes"]
        if type(expected_bytes) is not int or not 0 < expected_bytes <= MAX_FILE_BYTES:
            raise CapturePackageError(f"package file byte count is outside bound: {role}")
        actual_digest, actual_bytes = _hash_file(path)
        if actual_digest != expected_digest or actual_bytes != expected_bytes:
            raise CapturePackageError(f"package file differs from manifest: {role}")
        total += actual_bytes
        if total > MAX_TOTAL_FILE_BYTES:
            raise CapturePackageError("package files exceed aggregate size limit")
        verified_files[role] = path

    origin_copy = verified_files["origin_manifest"]
    if (files["origin_manifest"]["sha256"] != origin_sha
            or files["origin_manifest"]["bytes"] > MAX_MANIFEST_BYTES):
        raise CapturePackageError("copied origin manifest digest differs from the origin reference")
    origin_raw, origin_copy_sha, origin_copy_bytes = _read_stable_bytes(
        origin_copy, MAX_MANIFEST_BYTES, "copied origin manifest")
    if origin_copy_sha != origin_sha or origin_copy_bytes != files["origin_manifest"]["bytes"]:
        raise CapturePackageError("copied origin manifest changed after file verification")
    _json_object(origin_raw, "copied origin manifest")
    icu_file = files["icu_data"]
    if icu_file["sha256"] != icu_digest or icu_file["bytes"] != localization["icu_data"]["bytes"]:
        raise CapturePackageError("package ICU identity differs across manifest references")
    return manifest, root, verified_files


__all__ = ["CapturePackageError", "export_capture", "read_package"]

"""Copy and verify an explicitly selected private resource file set.

No discovery, execution, external-resource handling, or lab-specific imports
are performed here. Paths are preserved relative to the source root.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat

SCHEMA = "civ6-host.private-resources.v1"
MANIFEST_NAME = "private-resources.json"
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                     *(f"lpt{i}" for i in range(1, 10))}


class ResourceBundleError(ValueError):
    """The selected resource set or its copied package is invalid."""


def _digest(value: object, label: str) -> str:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise ResourceBundleError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identity(info) -> tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size,
            getattr(info, "st_mtime_ns", int(info.st_mtime * 1e9)))


def _canonical_directory(value: object, label: str) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ResourceBundleError(f"{label} must be an absolute directory path")
    path = Path(value)
    if not path.is_absolute():
        raise ResourceBundleError(f"{label} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError(f"{label} must exist") from exc
    if path != resolved or not resolved.is_dir():
        raise ResourceBundleError(f"{label} must be a canonical directory")
    return resolved


def _relative_parts(raw: object) -> tuple[str, ...]:
    if type(raw) is not str or not raw or "\\" in raw or "\x00" in raw:
        raise ResourceBundleError("resource path must be a nonempty POSIX relative path")
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    parts = posix.parts
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or not parts or "/".join(parts) != raw
            or any(part in ("", ".", "..") for part in parts)):
        raise ResourceBundleError("resource path must not be absolute or traverse directories")
    for part in parts:
        windows_stem = part.split(".", 1)[0].rstrip(" .").casefold()
        if (part.endswith((".", " ")) or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                or windows_stem in _WINDOWS_RESERVED):
            raise ResourceBundleError("resource path is not portable to Windows")
    return parts


def _validate_path_set(paths) -> list[tuple[str, tuple[str, ...]]]:
    if type(paths) is not dict:
        raise ResourceBundleError("files must map relative paths to SHA-256 digests")
    rows = []
    folded = {}
    component_spellings = {}
    for raw, digest in paths.items():
        parts = _relative_parts(raw)
        key = "/".join(part.casefold() for part in parts)
        if key == MANIFEST_NAME.casefold() or key.startswith(MANIFEST_NAME.casefold() + "/"):
            raise ResourceBundleError("resource path collides with the reserved package manifest")
        _digest(digest, f"resource digest for {raw}")
        if key in folded:
            raise ResourceBundleError(f"resource paths collide on Windows: {folded[key]} and {raw}")
        folded[key] = raw
        for index, component in enumerate(parts):
            prefix = "/".join(part.casefold() for part in parts[:index + 1])
            spelling = "/".join(parts[:index + 1])
            previous_spelling = component_spellings.get(prefix)
            if previous_spelling is not None and previous_spelling != spelling:
                raise ResourceBundleError(f"resource directory spellings collide on Windows: {previous_spelling} and {spelling}")
            component_spellings[prefix] = spelling
        rows.append((raw, parts))
    # A file cannot also be an ancestor directory of another selected file.
    for raw, parts in rows:
        for index in range(1, len(parts)):
            ancestor = "/".join(part.casefold() for part in parts[:index])
            if ancestor in folded:
                raise ResourceBundleError(f"resource file/directory paths collide: {folded[ancestor]} and {raw}")
    rows.sort(key=lambda item: item[0])
    return rows


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _source_file(root: Path, raw: str, parts: tuple[str, ...]) -> Path:
    path = root.joinpath(*parts)
    try:
        resolved = path.resolve(strict=True)
        info = path.lstat()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError(f"selected source is missing or redirected: {raw}") from exc
    if not _within(resolved, root) or resolved != path or stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ResourceBundleError(f"selected source is not a canonical in-root regular file: {raw}")
    return path


def _copy_hash(source: Path, target: Path, expected: str) -> tuple[int, str]:
    before = source.stat()
    digest = hashlib.sha256()
    size = 0
    try:
        with source.open("rb", buffering=0) as reader, target.open("xb", buffering=0) as writer:
            opened = os.fstat(reader.fileno())
            if _identity(before) != _identity(opened):
                raise ResourceBundleError("source changed before copying")
            while True:
                chunk = reader.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                writer.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
            after_open = os.fstat(reader.fileno())
        after_path = source.stat()
        if (_identity(opened) != _identity(after_open)
                or _identity(after_open) != _identity(after_path)
                or source.resolve(strict=True) != source or size != after_path.st_size):
            raise ResourceBundleError("source changed while copying")
    except ResourceBundleError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError("source could not be copied stably") from exc
    actual = digest.hexdigest()
    if actual != expected:
        raise ResourceBundleError("source hash differs from selected pin")
    # Historical capture receipts also record source mtimes. Preserve this
    # metadata as a copy operation, without rewriting their immutable JSON.
    os.utime(target, ns=(after_path.st_atime_ns, after_path.st_mtime_ns))
    if target.stat().st_mtime_ns != after_path.st_mtime_ns:
        raise ResourceBundleError("source modification time could not be preserved")
    return size, actual


def _ensure_output_parent(root: Path, parts: tuple[str, ...]) -> Path:
    current = root
    for component in parts[:-1]:
        current = current / component
        try:
            current.mkdir(exist_ok=True)
            resolved = current.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ResourceBundleError("package path parent could not be created") from exc
        if resolved != current or not resolved.is_dir():
            raise ResourceBundleError("package path parent was redirected")
    target = root.joinpath(*parts)
    if target.exists() or target.is_symlink():
        raise ResourceBundleError("package destination file already exists")
    return target


def _stable_read(path: Path, limit: int) -> tuple[bytes, str]:
    before = path.stat()
    if before.st_size > limit:
        raise ResourceBundleError("resource manifest exceeds its size limit")
    digest = hashlib.sha256()
    chunks = []
    size = 0
    try:
        with path.open("rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if _identity(before) != _identity(opened):
                raise ResourceBundleError("resource manifest changed before reading")
            while True:
                chunk = stream.read(min(HASH_CHUNK_BYTES, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise ResourceBundleError("resource manifest exceeds its size limit")
                digest.update(chunk)
                chunks.append(chunk)
            after_open = os.fstat(stream.fileno())
        after_path = path.stat()
    except ResourceBundleError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError("resource manifest could not be read stably") from exc
    if (_identity(opened) != _identity(after_open) or _identity(after_open) != _identity(after_path)
            or path.resolve(strict=True) != path or size != after_path.st_size):
        raise ResourceBundleError("resource manifest changed while reading")
    return b"".join(chunks), digest.hexdigest()


def _parse_manifest(raw: bytes) -> dict:
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ResourceBundleError(f"duplicate manifest key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ResourceBundleError(f"invalid manifest number: {value}")

    try:
        value = json.loads(raw.decode("utf-8", errors="strict"),
                           object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ResourceBundleError("resource manifest is not valid JSON") from exc
    if type(value) is not dict:
        raise ResourceBundleError("resource manifest root must be an object")
    return value


def export_resources(*, source_root: Path, destination: Path,
                     files: dict[str, str]) -> dict[str, str]:
    """Copy a caller-selected relative file set into a new private directory."""
    source = _canonical_directory(source_root, "source root")
    destination = Path(destination)
    if not destination.is_absolute() or destination.name in ("", ".", ".."):
        raise ResourceBundleError("destination must be an explicit absolute directory")
    try:
        parent = destination.parent.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError("destination parent must already exist") from exc
    if parent != destination.parent:
        raise ResourceBundleError("destination parent must be canonical")
    if destination.exists() or destination.is_symlink():
        raise ResourceBundleError("destination already exists")
    if _within(destination, source) or _within(source, destination):
        raise ResourceBundleError("source and destination roots must be disjoint")
    rows = _validate_path_set(files)
    source_files = [(raw, parts, _source_file(source, raw, parts), _digest(digest, raw))
                    for raw, parts in rows for digest in (files[raw],)]
    try:
        destination.mkdir()
    except OSError as exc:
        raise ResourceBundleError("destination could not be created exclusively") from exc

    records = []
    for raw, parts, source_file, expected in source_files:
        target = _ensure_output_parent(destination, parts)
        size, actual = _copy_hash(source_file, target, expected)
        records.append({"path": raw, "sha256": actual, "bytes": size})

    manifest = {"schema": SCHEMA, "source_root": str(source), "files": records}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ResourceBundleError("resource manifest exceeds its size limit")
    manifest_path = destination / MANIFEST_NAME
    if manifest_path.exists() or manifest_path.is_symlink():
        raise ResourceBundleError("reserved manifest destination already exists")
    try:
        with manifest_path.open("xb", buffering=0) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ResourceBundleError("resource manifest could not be written") from exc
    return {"path": str(manifest_path), "sha256": hashlib.sha256(encoded).hexdigest()}


def read_resources(reference: dict[str, str], *, resource_root: Path) -> dict:
    """Verify a private resource manifest and every listed copy in place."""
    root = _canonical_directory(resource_root, "resource root")
    if type(reference) is not dict or set(reference) != {"path", "sha256"}:
        raise ResourceBundleError("resource reference must contain path and SHA-256")
    expected_manifest_sha = _digest(reference["sha256"], "resource manifest digest")
    manifest_path = Path(reference["path"]) if type(reference["path"]) is str else Path()
    if (not manifest_path.is_absolute() or manifest_path.name.casefold() != MANIFEST_NAME.casefold()
            or manifest_path.parent != root):
        raise ResourceBundleError("reference must point to the manifest in the explicit resource root")
    try:
        if manifest_path.resolve(strict=True) != manifest_path:
            raise ResourceBundleError("resource manifest path is redirected")
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError("resource manifest is unavailable") from exc
    raw, actual_manifest_sha = _stable_read(manifest_path, MAX_MANIFEST_BYTES)
    if actual_manifest_sha != expected_manifest_sha:
        raise ResourceBundleError("resource manifest digest differs")
    manifest = _parse_manifest(raw)
    if set(manifest) != {"schema", "source_root", "files"} or manifest.get("schema") != SCHEMA:
        raise ResourceBundleError("unsupported resource manifest schema or fields")
    original_root = manifest.get("source_root")
    if (type(original_root) is not str or not original_root
            or not Path(original_root).is_absolute() or ".." in Path(original_root).parts):
        raise ResourceBundleError("manifest source root must remain an absolute original path")
    rows = manifest.get("files")
    if type(rows) is not list:
        raise ResourceBundleError("manifest files must be an array")
    pins = {}
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"}:
            raise ResourceBundleError("resource manifest file record has an unexpected shape")
        raw_path = row["path"]
        _relative_parts(raw_path)
        pins[raw_path] = _digest(row["sha256"], f"resource digest for {raw_path}")
        if type(row["bytes"]) is not int or row["bytes"] < 0:
            raise ResourceBundleError("resource file byte count is malformed")
    if len(pins) != len(rows):
        raise ResourceBundleError("resource manifest contains duplicate paths")
    _validate_path_set(pins)

    for row in rows:
        raw_path = row["path"]
        parts = _relative_parts(raw_path)
        candidate = root.joinpath(*parts)
        try:
            resolved = candidate.resolve(strict=True)
            info = candidate.lstat()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ResourceBundleError(f"packaged resource is missing or redirected: {raw_path}") from exc
        if (not _within(resolved, root) or resolved != candidate or stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)):
            raise ResourceBundleError(f"packaged resource escapes root or is a symlink: {raw_path}")
        actual_size, actual_sha = _hash_only(candidate)
        if actual_size != row["bytes"] or actual_sha != row["sha256"]:
            raise ResourceBundleError(f"packaged resource hash or size differs: {raw_path}")
    return manifest


def _hash_only(path: Path) -> tuple[int, str]:
    before = path.stat()
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb", buffering=0) as stream:
            opened = os.fstat(stream.fileno())
            if _identity(before) != _identity(opened):
                raise ResourceBundleError("packaged resource changed before hashing")
            while True:
                chunk = stream.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
            after_open = os.fstat(stream.fileno())
        after_path = path.stat()
    except ResourceBundleError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise ResourceBundleError("packaged resource could not be hashed stably") from exc
    if (_identity(opened) != _identity(after_open) or _identity(after_open) != _identity(after_path)
            or path.resolve(strict=True) != path or size != after_path.st_size):
        raise ResourceBundleError("packaged resource changed while hashing")
    return size, digest.hexdigest()


__all__ = ["ResourceBundleError", "export_resources", "read_resources"]


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Copy or verify a selected private resource set.")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--source-root", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    export.add_argument("--selection", type=Path, required=True,
                        help="JSON object mapping relative POSIX paths to SHA-256 digests")
    verify = commands.add_parser("verify")
    verify.add_argument("--resources", type=Path, required=True)
    verify.add_argument("--sha256", required=True, help="Expected digest from the export reference")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            selection = args.selection.resolve(strict=True)
            if not selection.is_file():
                raise ResourceBundleError("selection must be a regular file")
            raw, _ = _stable_read(selection, MAX_MANIFEST_BYTES)
            report = export_resources(source_root=args.source_root, destination=args.destination,
                                      files=_parse_manifest(raw))
        else:
            reference = {"path": str(args.resources / MANIFEST_NAME), "sha256": args.sha256}
            manifest = read_resources(reference, resource_root=args.resources)
            report = {"reference": reference, "file_count": len(manifest["files"]),
                      "total_bytes": sum(row["bytes"] for row in manifest["files"])}
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Resource bundle error: {exc}\n")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pack, verify or extract an explicitly selected PRIVATE contributor archive.

No discovery, network transfer, game launch or modification of proof contents.
The archive preserves nanosecond modification times outside ZIP's coarse dates.
It must never be uploaded to a public source repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from civ6_host.runtime.resource_bundle import _validate_path_set, _ensure_output_parent

SCHEMA = "civ6-host.private-handoff.v1"
MANIFEST = "HANDOFF.json"
CHUNK = 1024 * 1024
MAX_MANIFEST = 16 * CHUNK


def _json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise ValueError("Selection exceeds metadata limit")
    return json.loads(raw)


def _paths(rows):
    names = [row["path"] for row in rows]
    if len(names) != len(set(names)) or any(n.casefold() == MANIFEST.casefold() for n in names):
        raise ValueError("Duplicate or reserved archive path")
    # Existing resource manifest names are payloads here, not the outer manifest.
    checked = {"payload/" + r["path"]: r["sha256"] for r in rows}
    _validate_path_set(checked)


def pack(selection, destination):
    plan = _json(selection)
    _paths(plan["files"])
    records = []
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        for row in plan["files"]:
            source = Path(row["source"])
            if not source.is_absolute() or source.resolve(strict=True) != source or not source.is_file():
                raise ValueError("Source is missing or redirected: " + row["path"])
            before = source.stat()
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as reader, archive.open(row["path"], "w", force_zip64=True) as writer:
                while chunk := reader.read(CHUNK):
                    writer.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            after = source.stat()
            if (digest.hexdigest() != row["sha256"] or size != before.st_size
                    or before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size
                    or source.resolve(strict=True) != source):
                raise ValueError("Source changed or differs from pin: " + row["path"])
            records.append(dict(path=row["path"], sha256=digest.hexdigest(),
                                bytes=size, mtime_ns=before.st_mtime_ns))
        manifest = dict(schema=SCHEMA, private=True, scope=plan.get("scope", {}), files=records)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    return dict(files=len(records), bytes=sum(r["bytes"] for r in records), private=True)


def unpack(path, destination=None):
    root = None
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [m.filename for m in members]
        if names.count(MANIFEST) != 1 or len(names) != len(set(names)):
            raise ValueError("Missing manifest or duplicate ZIP entries")
        if archive.getinfo(MANIFEST).file_size > MAX_MANIFEST:
            raise ValueError("Archive manifest exceeds limit")
        raw = archive.read(MANIFEST)
        manifest = json.loads(raw)
        if manifest.get("schema") != SCHEMA or manifest.get("private") is not True:
            raise ValueError("Unknown private handoff schema")
        rows = manifest["files"]
        _paths(rows)
        if set(names) != {MANIFEST, *(r["path"] for r in rows)}:
            raise ValueError("ZIP entries differ from explicit selection")
        for row in rows:
            info = archive.getinfo(row["path"])
            if (type(row["bytes"]) is not int or row["bytes"] < 0
                    or type(row["mtime_ns"]) is not int or row["mtime_ns"] < 0
                    or info.file_size != row["bytes"]
                    or stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG)):
                raise ValueError("Invalid archive member metadata")
        if destination is not None:
            candidate = Path(destination)
            if not candidate.is_absolute() or candidate.exists() or candidate.is_symlink():
                raise ValueError("Destination must be a new absolute directory")
            if candidate.resolve() != candidate:
                raise ValueError("Destination is redirected")
            candidate.mkdir(parents=True, exist_ok=False)
            root = candidate.resolve(strict=True)
        for row in rows:
            target = _ensure_output_parent(root, tuple(row["path"].split("/"))) if root else None
            writer = target.open("xb") if target else None
            digest = hashlib.sha256()
            size = 0
            try:
                with archive.open(row["path"]) as reader:
                    while chunk := reader.read(CHUNK):
                        size += len(chunk)
                        if size > row["bytes"]:
                            raise ValueError("Archive member exceeds declared size")
                        digest.update(chunk)
                        if writer:
                            writer.write(chunk)
            finally:
                if writer:
                    writer.close()
            if size != row["bytes"] or digest.hexdigest() != row["sha256"]:
                raise ValueError("Archive member digest differs: " + row["path"])
            if target:
                os.utime(target, ns=(row["mtime_ns"], row["mtime_ns"]))
                if target.stat().st_mtime_ns != row["mtime_ns"]:
                    raise ValueError("Destination filesystem did not preserve modification time")
        if root:
            (root / MANIFEST).write_bytes(raw)  # Completion marker is written last.
        return dict(files=len(rows), bytes=sum(r["bytes"] for r in rows),
                    hashes_verified=True, native_readiness_verified=False, extracted=root is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("pack")
    create.add_argument("--selection", type=Path, required=True)
    create.add_argument("--archive", type=Path, required=True)
    for command in ("verify", "extract"):
        action = sub.add_parser(command)
        action.add_argument("--archive", type=Path, required=True)
        if command == "extract":
            action.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = (pack(args.selection, args.archive) if args.command == "pack" else
              unpack(args.archive, getattr(args, "destination", None)))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

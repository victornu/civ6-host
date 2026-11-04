"""Build an installable runtime sdist from the shared repository source tree."""

import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

from setuptools import build_meta

build_wheel = build_meta.build_wheel
get_requires_for_build_wheel = build_meta.get_requires_for_build_wheel
prepare_metadata_for_build_wheel = build_meta.prepare_metadata_for_build_wheel
build_editable = build_meta.build_editable
get_requires_for_build_editable = build_meta.get_requires_for_build_editable
prepare_metadata_for_build_editable = build_meta.prepare_metadata_for_build_editable
get_requires_for_build_sdist = build_meta.get_requires_for_build_sdist


def _normalize_sdist(path, epoch):
    """Normalize setuptools' tar metadata and the enclosing gzip header."""
    with TemporaryDirectory(prefix=".sdist-", dir=path.parent) as directory:
        output = Path(directory) / path.name
        with (tarfile.open(path, "r:gz") as original,
              output.open("wb") as stream,
              gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=epoch) as compressed,
              tarfile.open(fileobj=compressed, mode="w") as archive):
            for member in sorted(original.getmembers(), key=lambda entry: entry.name):
                if not (member.isfile() or member.isdir()):
                    raise ValueError("Unexpected source archive member type")
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mtime = epoch
                member.mode = 0o755 if member.isdir() else 0o644
                member.pax_headers = {}
                if member.isfile():
                    with original.extractfile(member) as payload:
                        archive.addfile(member, payload)
                else:
                    archive.addfile(member)
        output.replace(path)


def build_sdist(sdist_directory, config_settings=None):
    # setuptools omits the runtime when its package directory is outside
    # the project root. Stage only the same source payload as the wheel.
    project = Path(__file__).resolve().parent
    source = project.parents[1] / "src" / "civ6_host" / "runtime"
    destination = Path(sdist_directory).resolve()
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None:
        epoch = int(epoch)
        if not 0 <= epoch <= 0xFFFFFFFF:
            raise ValueError("SOURCE_DATE_EPOCH is outside the gzip timestamp range")
    with TemporaryDirectory(prefix="civ6-host-runtime-sdist-") as directory:
        stage = Path(directory)
        config = (project / "pyproject.toml").read_text(encoding="utf-8")
        config = config.replace('build-backend = "runtime_build"\nbackend-path = ["."]',
                                'build-backend = "setuptools.build_meta"')
        config = config.replace('"../../src"', '"src"')
        (stage / "pyproject.toml").write_text(config, encoding="utf-8")
        shutil.copy2(project / "LICENSE-pydt-civ6-save-parser.txt", stage)
        for path in source.rglob("*.py"):
            target = stage / "src" / "civ6_host" / "runtime" / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        shutil.copy2(source / "source-map.json", stage / "src" / "civ6_host" / "runtime")
        name = subprocess.check_output(
            [sys.executable, "-c",
             "import json, sys; from setuptools.build_meta import build_sdist; "
             "print(build_sdist(sys.argv[1], json.loads(sys.argv[2])))",
             str(destination), json.dumps(config_settings)],
            cwd=stage, text=True,
        ).splitlines()[-1]
        if epoch is not None:
            _normalize_sdist(destination / name, epoch)
        return name

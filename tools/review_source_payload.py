"""Build a local source review archive from the host's build inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

from build_native_host import PROFILE_MANIFESTS, source_inputs
from review_wheel_payload import _SECRET_MARKERS, _source_payload


_ROOT = Path(__file__).resolve().parents[1]
_REVIEW_MANIFEST = 'SOURCE-REVIEW.json'
_PRIVATE_PATHS = re.compile(r'(?i)(?:[a-z]:[/\\]+users[/\\]+[a-z0-9._-]+|/home/[a-z0-9._-]+)')
_BUILD_FILES = (
    'README.md', 'README-history-20261030.md', 'pyproject.toml',
    'distributions/runtime/pyproject.toml', 'distributions/runtime/runtime_build.py',
    'distributions/runtime/LICENSE-pydt-civ6-save-parser.txt',
    'tools/build_native_host.py', 'tools/review_wheel_payload.py', 'tools/review_source_payload.py',
    'examples/local_session.py',
    'docs/backend.md', 'docs/capture-package.md', 'docs/client.md',
    'docs/native-build.md', 'docs/resource-bundle.md', 'docs/resources.md',
    'docs/runtime-paths.md', 'docs/xp1-services.md', 'docs/xp2-capture-inputs.md',
)


def _source_bytes(root, name):
    path = root / name
    if not path.is_relative_to(root) or path.resolve(strict=True) != path or not path.is_file():
        raise ValueError('Source path is redirected or outside the checkout: ' + name)
    with path.open('rb') as stream:
        raw = stream.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError('Source member exceeds the review bound: ' + name)
    text = raw.decode('utf-8-sig')
    if b'\0' in raw or _SECRET_MARKERS.search(text) or _PRIVATE_PATHS.search(text):
        raise ValueError('Binary, credential marker or personal home path in source member: ' + name)
    return raw


def _source_payloads(root):
    names = set(_BUILD_FILES)
    for package in ('client', 'runtime'):
        names.update('src/' + name for name in _source_payload(root, package))
    payloads = {name: _source_bytes(root, name) for name in sorted(names)}
    for manifest_name in PROFILE_MANIFESTS.values():
        manifest_bytes = _source_bytes(root, manifest_name)
        manifest = json.loads(manifest_bytes)
        if manifest.get('schema') != 'civ6-host.native-source.v1':
            raise ValueError('Unexpected native source manifest: ' + manifest_name)
        checked = source_inputs(root, manifest)
        payloads[manifest_name] = manifest_bytes
        for row in manifest['sources']:
            name = row['path']
            if name not in payloads:
                payloads[name] = _source_bytes(root, name)
            if Path(name).suffix not in ('.c', '.h', '.inc') or checked[root / name] != payloads[name]:
                raise ValueError('Native source differs from its build manifest: ' + name)
    if len(payloads) > 2048 or len({name.casefold() for name in payloads}) != len(payloads):
        raise ValueError('Source review exceeds the file count or contains Windows path collisions')
    if sum(map(len, payloads.values())) > 64 * 1024**2:
        raise ValueError('Source review exceeds the aggregate size bound')
    mapping = json.loads(payloads['src/civ6_host/runtime/source-map.json'])
    for row in mapping['sources']:
        name = row['destination']
        if name not in payloads or hashlib.sha256(payloads[name]).hexdigest() != row['destination_sha256']:
            raise ValueError('Mapped source differs from its recorded destination digest: ' + name)
    return payloads


def export_source_review(root, archive_path):
    root = Path(root).resolve(strict=True)
    archive_path = Path(archive_path)
    payloads = _source_payloads(root)
    review = {
        'schema': 'civ6-host.source-review.v1',
        'status': 'local_review_candidate',
        'native_build_profiles': list(PROFILE_MANIFESTS),
        'omitted': ['private runtime resources and research records', 'game files and binaries',
                    'local build products', 'developer-only fixtures and extraction tools', 'learner'],
        'publication_review_required': ['source provenance and licensing', 'independent private input preparation'],
        'files': [{'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                  for name, raw in sorted(payloads.items())],
    }
    payloads[_REVIEW_MANIFEST] = (json.dumps(review, indent=2) + '\n').encode('utf-8')
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payloads.items()):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED)
    with archive_path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(archive_path.resolve()), sha256=digest,
                files=len(review['files']), native_build_profiles=len(PROFILE_MANIFESTS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_source_review(_ROOT, args.archive), indent=2))


if __name__ == '__main__':
    main()

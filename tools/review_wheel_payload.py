"""Review host wheel contents locally before a distribution review."""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


_SECRET_MARKERS = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----|"
    r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|AKIA[A-Z0-9]{16})\b"
)
_DIST_NAME = re.compile(r"civ6_host_(client|runtime)-[A-Za-z0-9.]+\.dist-info")
_METADATA = {'METADATA', 'WHEEL', 'RECORD', 'top_level.txt', 'LICENSE-pydt-civ6-save-parser.txt'}


def _source_payload(root, distribution):
    package = root / 'src' / 'civ6_host'
    if distribution == 'runtime':
        paths = [*(package / 'runtime').rglob('*.py'), package / 'runtime' / 'source-map.json']
    else:
        paths = [*package.glob('*.py'), *(package / 'contracts').rglob('*.py')]
    if not paths or not package.is_dir():
        raise ValueError('Expected the civ6-host source tree')
    payload = {}
    for path in paths:
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError('Source payload path is redirected: ' + str(path))
        payload[path.relative_to(root / 'src').as_posix()] = path
    return payload


def review(path, *, source_root=None):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    with zipfile.ZipFile(path) as wheel:
        members = wheel.infolist()
        if not members or len(members) > 2048 or sum(row.file_size for row in members) > 64 * 1024**2:
            raise ValueError('Wheel exceeds the review bounds')
        metadata = {row.filename.split('/')[0] for row in members
                    if row.filename.split('/')[0].endswith('.dist-info')}
        match = _DIST_NAME.fullmatch(next(iter(metadata))) if len(metadata) == 1 else None
        if match is None:
            raise ValueError('Wheel lacks one expected host distribution identity')
        distribution = match.group(1)
        root = source_root.resolve(strict=True) if source_root is not None else None
        sources = _source_payload(root, distribution) if root is not None else None
        notice = 'LICENSE-pydt-civ6-save-parser.txt'
        notice_verified = False
        seen = set()
        record_name = f'{match.group(0)}/RECORD'
        record_rows = None
        expected_records = {}
        for member in members:
            name = member.filename
            parts = PurePosixPath(name).parts
            if (not parts or name != '/'.join(parts) or '\\' in name
                    or '..' in parts or name.startswith('/') or name.casefold() in seen
                    or stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG)):
                raise ValueError('Unsafe or duplicate wheel member: ' + name)
            seen.add(name.casefold())
            if parts[0] in metadata:
                allowed = (len(parts) == 2 and parts[1] in _METADATA
                    or len(parts) == 3 and parts[1:] == ('licenses', 'LICENSE-pydt-civ6-save-parser.txt'))
            elif distribution == 'runtime':
                allowed = (parts[:2] == ('civ6_host', 'runtime')
                    and (name.endswith('.py') or parts == ('civ6_host', 'runtime', 'source-map.json')))
            else:
                allowed = (parts[0] == 'civ6_host' and name.endswith('.py')
                    and (len(parts) == 2 or parts[1] == 'contracts'))
            if not allowed:
                raise ValueError('Unexpected wheel payload: ' + name)
            payload = wheel.read(member)
            if b'\0' in payload or _SECRET_MARKERS.search(payload.decode('utf-8-sig')):
                raise ValueError('Binary or credential marker in wheel member: ' + name)
            if sources is not None and parts[0] == 'civ6_host':
                source = sources.pop(name, None)
                if source is None or source.stat().st_size != len(payload) or source.read_bytes() != payload:
                    raise ValueError('Wheel member differs from source tree: ' + name)
            if root is not None and parts[0] in metadata and parts[-1] == notice:
                if (distribution != 'runtime' or notice_verified
                        or payload != (root / 'distributions' / 'runtime' / notice).read_bytes()):
                    raise ValueError('Unexpected or mismatched wheel notice')
                notice_verified = True
            if name == record_name:
                record_rows = payload.decode('utf-8')
                expected_records[name] = ('', '')
            else:
                encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode('ascii')
                expected_records[name] = ('sha256=' + encoded.rstrip('='), str(len(payload)))
        if not all(f'{match.group(0)}/{name}'.casefold() in seen for name in ('METADATA', 'WHEEL', 'RECORD')):
            raise ValueError('Wheel is missing required packaging metadata')
        if record_rows is None:
            raise ValueError('Wheel RECORD name differs from distribution metadata')
        for row in csv.reader(io.StringIO(record_rows, newline=''), strict=True):
            if len(row) != 3 or expected_records.pop(row[0], None) != tuple(row[1:]):
                raise ValueError('Wheel RECORD has an unknown, repeated or mismatched entry')
        if expected_records:
            raise ValueError('Wheel RECORD does not cover every member')
        if sources:
            raise ValueError('Wheel omits source members: ' + ', '.join(sorted(sources)[:5]))
        if root is not None and distribution == 'runtime' and not notice_verified:
            raise ValueError('Runtime wheel omits its source notice')
    return dict(wheel=path.name, sha256=digest, distribution=distribution,
                members=len(members), inspected_bytes=sum(row.file_size for row in members),
                record_sha256_verified=True, source_bytes_verified=root is not None,
                third_party_notice_verified=notice_verified)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', nargs='+', type=Path)
    parser.add_argument('--source-root', type=Path)
    args = parser.parse_args()
    print(json.dumps([review(path, source_root=args.source_root) for path in args.wheel], indent=2))


if __name__ == '__main__':
    main()

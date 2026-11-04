"""Resolve immutable historical references through an explicit private package.

JSON evidence bytes are never rewritten. Only filesystem references beneath the
declared old root are relocated, with no fallback to that old directory.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys

ENV = 'CIV6_HOST_PRIVATE_RESOURCES'
_UNSET = object()
_CHOICE = _UNSET
_MANIFEST = None
_FILES = None
_RECORDS = None
_DIRECTORIES = None
_BOUNDARY = False


def configured_reference():
    global _CHOICE
    raw = os.environ.get(ENV)
    value = None if raw is None else json.loads(raw)
    if value is not None:
        if type(value) is not dict or set(value) != {'path', 'sha256'}:
            raise ValueError('Private resources require an explicit manifest path and SHA-256')
        if type(value['path']) is not str or not Path(value['path']).is_absolute():
            raise ValueError('Private resource manifest must have an absolute path')
    if _CHOICE is _UNSET:
        _CHOICE = copy.deepcopy(value)
    if value != _CHOICE:
        raise RuntimeError('Private resource selection changed; use a new process')
    return copy.deepcopy(value)


def configure(reference):
    previous = os.environ.get(ENV)
    if previous is not None and json.loads(previous) != reference:
        raise ValueError('Private resource environment differs from explicit configuration')
    if reference is not None:
        os.environ[ENV] = json.dumps(reference, sort_keys=True)
    if configured_reference() != reference:
        raise ValueError('Private resource configuration differs')
    return manifest()


def manifest():
    global _MANIFEST, _FILES, _DIRECTORIES, _RECORDS
    reference = configured_reference()
    if reference is None:
        return None
    if _MANIFEST is None:
        from .paths import resource_root
        from .resource_bundle import read_resources
        result = read_resources(reference, resource_root=resource_root())
        source = Path(result['source_root'])
        if not source.is_absolute() or source == resource_root():
            raise ValueError('Relocation requires distinct absolute source and resource roots')
        if resource_root().is_relative_to(source) or source.is_relative_to(resource_root()):
            raise ValueError('Relocated resources must not overlap their historical root')
        _FILES = {row['path'] for row in result['files']}
        _RECORDS = {row['path']: row for row in result['files']}
        _DIRECTORIES = {'.'}
        for name in _FILES:
            _DIRECTORIES.update(p.as_posix() for p in Path(name).parents)
        _MANIFEST = result
    return _MANIFEST


def resolve_path(value):
    """Map only Path values; other receivers in generated code are unchanged."""
    if not isinstance(value, Path):
        return value
    selected = manifest()
    if selected is None or not value.is_absolute():
        return value
    source = Path(selected['source_root'])
    # abspath is lexical: never query the historical directory, even to resolve
    # symlinks. read_resources has already checked the new package's paths.
    lexical = Path(os.path.abspath(value))
    if not lexical.is_relative_to(source):
        return value
    relative = lexical.relative_to(source).as_posix()
    if relative not in _FILES and relative not in _DIRECTORIES:
        raise ValueError('Historical resource was not packaged: ' + relative)
    from .paths import resource_root
    target = resource_root() / relative
    if target.resolve() != target or not target.is_relative_to(resource_root()):
        raise ValueError('Relocated resource escaped its package: ' + relative)
    return target


def recorded_path(value: Path) -> Path:
    """Return the original path of an explicitly packaged file."""
    selected = manifest()
    if selected is not None and value.is_absolute():
        from .paths import resource_root

        root = resource_root()
        if value.is_relative_to(root):
            relative = value.relative_to(root).as_posix()
            if relative in _FILES:
                return Path(selected['source_root']) / relative
    return value


def enable_read_boundary():
    """Reject accidental reads of the original lab once relocation is selected."""
    global _BOUNDARY
    selected = manifest()
    if selected is None or _BOUNDARY:
        return
    source = Path(selected['source_root'])
    def refuse_historical_reads(event, args):
        if event not in ('open', 'os.listdir', 'os.scandir') or not args:
            return
        value = args[0]
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        candidate = Path(os.path.abspath(os.fsdecode(value)))
        if candidate.is_relative_to(source):
            raise RuntimeError('Historical resource read forbidden after relocation: ' + str(candidate))
    sys.addaudithook(refuse_historical_reads)
    _BOUNDARY = True


def historical_reference(record):
    """Keep the origin identity of a verified copied capture-provenance record.

Only the two historical file-reference producers use this helper. Live output
files and worker closure paths keep their real current locations.
"""
    selected = manifest()
    if selected is None or type(record) is not dict or type(record.get('path')) is not str:
        return record
    from .paths import resource_root
    path = Path(record['path'])
    if not path.is_absolute() or not path.is_relative_to(resource_root()):
        return record
    relative = path.relative_to(resource_root()).as_posix()
    if relative not in _FILES:
        return record
    pin = _RECORDS[relative]
    if record.get('sha256') != pin['sha256'] or record.get('bytes') != pin['bytes']:
        raise ValueError('Copied capture reference bytes differ from its packaged origin')
    return dict(record, path=str(Path(selected['source_root']) / relative))


def closure_reference():
    """The worker must pin the same resource manifest as its parent."""
    selected = manifest()
    return None if selected is None else configured_reference()


def configure_closure(closure):
    reference = closure_reference()
    if reference is None:
        return
    closure['private_resources'] = reference
    closure['pins'][reference['path']] = reference['sha256']


def validate_closure(closure):
    reference = closure_reference()
    if closure.get('private_resources') != reference:
        raise ValueError('Worker private resources differ from the parent closure')
    if reference is not None and closure['pins'].get(reference['path']) != reference['sha256']:
        raise ValueError('Worker private resource manifest is not pinned')

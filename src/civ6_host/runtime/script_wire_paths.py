"""Exact native script names, separate from explicitly approved source files.

A wire name is an identifier, never a filesystem resolution instruction. The
existing registry still validates every physical source beneath its roots.
"""
from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
import time


def encode_wire_path(value):
    if type(value) is not str or not value or '\0' in value:
        raise ValueError('Gameplay script wire path must be nonempty NUL-free text')
    path = PureWindowsPath(value)
    if path.suffix.casefold() != '.lua' or not path.stem:
        raise ValueError('Gameplay script wire path must name a Lua source')
    encoded = value.encode('utf-16-le', 'strict')
    if len(encoded) > 259 * 2:
        raise ValueError('Gameplay script wire path exceeds 259 UTF-16 units')
    return encoded


def selected_wire_paths(values, count):
    if values is None:
        return None
    if isinstance(values, (str, bytes)):
        raise TypeError('Selected wire paths require an explicit ordered collection')
    result = tuple(values)
    if len(result) != count:
        raise ValueError('Physical and native script selections differ in length')
    for value in result:
        encode_wire_path(value)
    return result


def bind_wire_sources(paths, names):
    if len(paths) != len(names):
        raise ValueError('Physical and native script selections differ in length')
    result = {}
    for path, name in zip(paths, names):
        encode_wire_path(name)
        if name in result and result[name] != path:
            raise ValueError('One native script name maps to different physical sources')
        result[name] = path
    return result


def registry_from_capture(reference, *, process):
    """Reuse captured source validation and preserve every selected wire name.

    The manifest, working-directory witness and original/copy hashes are
    revalidated. No asset scan, path guessing, script execution or native Load
    occurs. Private copied files are the only physical sources in the registry.
    """
    from .native.native_official_bundle import _file
    from .native.native_gameplay_source_capture import recheck_selected_sources
    from .native.native_gameplay_script_registry import NativeGameplayScriptRegistry, GameplayScriptEntry
    from .resource_resolution import resolve_path
    from .script_observer_sources import retained_observer_path
    dependencies = {}
    report = json.loads(_file(reference, dependencies, maximum=4 * 1024 ** 2))
    folder = resolve_path(Path(reference['path'])).resolve(strict=True).parent
    records = report.get('records')
    files = report.get('files')
    if (type(records) is not list or type(files) is not dict
            or report.get('selected_paths') != [row.get('source_path') for row in records if type(row) is dict]
            or len(records) != len(report['selected_paths'])):
        raise ValueError('Captured script records and ordered names differ')
    if type(process) is not dict or type(process.get('identity')) is not dict:
        raise ValueError('Captured registry requires its full retained process report')
    if records:
        context = report.get('path_resolution', {}).get('context', {})
        if context.get('process') != process['identity']:
            raise ValueError('Captured script path witness belongs to another process')
    recheck_selected_sources(report, folder, deadline=time.monotonic() + 15)
    selected = []
    hashes = {}
    expected_files = {}
    for row in records:
        name = row['copy']
        source = row['source_state']
        if name != source['sha256'] + '.lua' or Path(name).name != name:
            raise ValueError('Captured script copy name differs from its source hash')
        pin = dict(bytes=source['bytes'], sha256=source['sha256'])
        if name in expected_files and expected_files[name] != pin:
            raise ValueError('Conflicting captured script source identity')
        expected_files[name] = pin
        _file(dict(path=str(folder / name), **pin), dependencies)
        selected.append(GameplayScriptEntry(folder, name))
        hashes[folder / name] = source['sha256']
    if files != expected_files:
        raise ValueError('Captured source files do not exactly cover the selected records')
    for pin in report.get('path_resolution', {}).get('dependencies', []):
        physical = retained_observer_path(pin['path'], pin['bytes'], pin['sha256'])
        _file(dict(pin, path=physical), dependencies, workspace=False, maximum=4 * 1024 ** 2)
    registry = NativeGameplayScriptRegistry((folder,), selected_scripts=selected,
                                            wire_paths=report['selected_paths'])
    return registry, hashes, dependencies

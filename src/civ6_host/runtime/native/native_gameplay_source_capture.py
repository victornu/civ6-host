"""Preserve selected GameplayScripts bytes without resolving or executing mods.

The caller supplies the official ordered selection. Relative virtual paths
cannot be resolved by searching for a similarly named file. These are disk
witnesses, not evidence of the bytes previously executed in a live process.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import time
from pathlib import Path
from civ6_host.runtime.native.native_gameplay_script_registry import MAX_SELECTED_SCRIPTS
from civ6_host.runtime.native.native_gameplay_script_registry import _approved_root
from civ6_host.runtime.native.native_include_registry import _reject_reparse_components
SCHEMA = 'civ6rl.selected_gameplay_source_capture.v1'
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024

def approved_roots(values):
    values = tuple(values)
    if len(values) > 32:
        raise ValueError('Too many approved gameplay source roots')
    roots = tuple((_approved_root(_resolve_resource_path(Path(value))) for value in values))
    if len(set(roots)) != len(roots):
        raise ValueError('Duplicate approved gameplay source root')
    return roots

def _read(path, roots, deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Gameplay source capture deadline exceeded')
    if not path.is_absolute() or path.suffix.casefold() != '.lua' or '..' in path.parts:
        raise ValueError('Gameplay selection requires an absolute resolved Lua path; no filename search')
    _reject_reparse_components(path)
    if not any((path.is_relative_to(root) for root in roots)):
        raise ValueError('Selected gameplay file is outside approved roots')
    before = _resolve_resource_path(path).stat()
    if not _resolve_resource_path(path).is_file() or before.st_size > MAX_FILE_BYTES:
        raise ValueError('Gameplay source is not a bounded regular file')
    data = bytearray()
    with _resolve_resource_path(path).open('rb') as stream:
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('Gameplay source capture deadline exceeded')
            chunk = stream.read(256 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError('Gameplay source grew beyond its bound')
    after = _resolve_resource_path(path).stat()
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if identity(before) != identity(after) or len(data) != before.st_size:
        raise ValueError('Gameplay source changed during read')
    return (bytes(data), dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), device=after.st_dev, inode=after.st_ino, mtime_ns=after.st_mtime_ns))

def capture_selected_sources(selected_paths, destination, *, roots, deadline, script_path_context=None, script_path_cwd_reader=None):
    """Copy each selected file; preserve every selection record and its order."""
    if type(selected_paths) is not list or len(selected_paths) > MAX_SELECTED_SCRIPTS or any((type(name) is not str or not name or '\x00' in name for name in selected_paths)):
        raise ValueError('Invalid ordered gameplay selection')
    roots = approved_roots(roots)
    path_context, path_reader = _load_script_path_context(script_path_context, script_path_cwd_reader, live=True)
    _validate_script_path_roots(path_context, roots)
    if path_context is not None and selected_paths != list(path_context.selected_order):
        raise ValueError('Selected script order differs from its pinned context')
    destination = _resolve_resource_path(Path(destination))
    destination.mkdir(exist_ok=False)
    report = dict(schema=SCHEMA, status='incomplete', selected_paths=selected_paths.copy(), approved_roots=[str(root) for root in roots], records=[], files={}, disk_bytes_only=True, in_memory_execution_bytes_proven=False, includes_and_dependencies_captured=False, training_eligible=False)
    if path_context is not None:
        report['path_resolution'] = _script_path_provenance(script_path_context, path_context)
    total = 0
    seen_sources = {}
    try:
        for index, name in enumerate(selected_paths):
            if path_context is not None:
                mapped_path, mapped_pin = _selected_script_path(name, path_context, roots, path_reader)
                raw, state = _read(mapped_path, roots, deadline)
                if {k: state[k] for k in ('bytes', 'sha256')} != mapped_pin:
                    raise ValueError('Mapped script bytes differ from their pinned context')
            else:
                raw, state = _read(_resolve_resource_path(Path(name)), roots, deadline)
            copy_name = state['sha256'] + '.lua'
            previous = seen_sources.get(name)
            if previous is not None and previous != state:
                raise ValueError('Repeated gameplay selection changed between reads')
            seen_sources[name] = state
            if copy_name not in report['files']:
                total += len(raw)
                if total > MAX_TOTAL_BYTES:
                    raise ValueError('Selected gameplay source total exceeds bound')
                with _resolve_resource_path(destination / copy_name).open('xb') as stream:
                    stream.write(raw)
                report['files'][copy_name] = {k: state[k] for k in ('bytes', 'sha256')}
            report['records'].append(dict(index=index, source_path=name, source_state=state, copy=copy_name))
            if path_context is not None:
                report['records'][-1]['resolved_path'] = str(mapped_path)
        report['status'] = 'selected_disk_sources_copied'
        return report
    except Exception as exc:
        report.update(status='refused', error=str(exc))
        raise
    finally:
        report['total_unique_bytes'] = total
        with _resolve_resource_path(destination / 'manifest.json').open('x', encoding='utf8') as stream:
            json.dump(report, stream, ensure_ascii=True, indent=2)

def recheck_selected_sources(report, destination, *, deadline, script_path_context=None, script_path_cwd_reader=None):
    """Check original files and retained copies after the official save request."""
    if report.get('schema') != SCHEMA or report.get('status') != 'selected_disk_sources_copied':
        raise ValueError('Completed gameplay source capture required')
    saved_resolution = report.get('path_resolution')
    if saved_resolution is not None:
        saved_context = saved_resolution.get('context')
        if script_path_context is not None and script_path_context != saved_context:
            raise ValueError('Selected-source context differs from its retained provenance')
        script_path_context = saved_context
    elif script_path_context is not None:
        raise ValueError('Selected-source report has no explicit path-resolution provenance')
    path_context, path_reader = _load_script_path_context(script_path_context, script_path_cwd_reader, live=script_path_cwd_reader is not None)
    if path_context is not None:
        if report['selected_paths'] != list(path_context.selected_order) or saved_resolution != _script_path_provenance(script_path_context, path_context):
            raise ValueError('Retained selected path order or resolution provenance differs')
    roots = approved_roots(report['approved_roots'])
    _validate_script_path_roots(path_context, roots)
    if report['selected_paths'] != [r['source_path'] for r in report['records']]:
        raise ValueError('Gameplay source order differs')
    for index, row in enumerate(report['records']):
        if path_context is not None:
            mapped_path, mapped_pin = _selected_script_path(row['source_path'], path_context, roots, path_reader)
            if row.get('resolved_path') != str(mapped_path):
                raise ValueError('Retained resolved path differs from its exact mapping')
            raw, state = _read(mapped_path, roots, deadline)
            if {k: state[k] for k in ('bytes', 'sha256')} != mapped_pin:
                raise ValueError('Resolved script bytes changed')
        else:
            raw, state = _read(_resolve_resource_path(Path(row['source_path'])), roots, deadline)
        if row['index'] != index or (state != row['source_state'] if path_context is None or path_reader is not None else any((state[k] != row['source_state'][k] for k in ('bytes', 'sha256')))):
            raise ValueError('Selected gameplay source changed across save')
        if row['copy'] != state['sha256'] + '.lua':
            raise ValueError('Selected gameplay copy identity differs')
        copied = _resolve_resource_path(Path(destination)) / row['copy']
        copied_raw, _ = _read(copied, (_resolve_resource_path(Path(destination)),), deadline)
        if copied_raw != raw:
            raise ValueError('Retained gameplay source copy differs')
    return dict(ordered_records=len(report['records']), original_and_copy_bytes_unchanged=True, disk_bytes_only=True, in_memory_execution_bytes_proven=False)

def _load_script_path_context(value, reader=None, *, live=False, process=None):
    if value is None:
        if reader is not None:
            raise ValueError('A script CWD observer requires an explicit script-path context')
        return (None, None)
    if type(value) is not dict or set(value) != {'witness', 'process'} or type(value['witness']) is not dict or (set(value['witness']) != {'path', 'bytes', 'sha256'}) or (type(value['process']) is not dict) or (set(value['process']) != {'pid', 'creation_filetime', 'image_path'}):
        raise ValueError('Script paths require an explicit pinned witness and exact process identity')
    if process is not None and value['process'] != process:
        raise ValueError('Script-path context differs from the actual capture process')
    from civ6_host.runtime import capture_script_paths as paths
    if live:
        if reader is None:
            reader = paths.observe_process_cwd
        context = paths.load_context(value['witness'], value['process'], cwd_reader=reader)
    else:
        context = paths.validate_context(value['witness'], value['process'])
    return (context, reader)

def _script_path_provenance(value, context):
    dependencies = [dict(value['witness'])]
    dependencies.extend((dict(path=path, bytes=size, sha256=sha) for path, size, sha in context.proof_files))
    dependencies.extend((dict(path=source.resolved_path, bytes=source.bytes, sha256=source.sha256) for source in context.source_files))
    return dict(context=dict(witness=dict(value['witness']), process=dict(value['process'])), witness_sha256=context.witness_sha256, cwd=context.cwd, selected_order=list(context.selected_order), dependencies=dependencies, disk_bytes_only=True, execution_proven=False, load_admitted=False)

def _validate_script_path_roots(context, roots):
    if context is None:
        return
    if not roots:
        raise ValueError('Relative selected scripts require explicit approved source roots')
    if len(context.selected_order) > MAX_SELECTED_SCRIPTS:
        raise ValueError('Selected script context exceeds the existing selection bound')
    unique = {}
    for source in context.source_files:
        candidate = _resolve_resource_path(Path(source.resolved_path))
        _reject_reparse_components(candidate)
        canonical = _resolve_resource_path(candidate).resolve(strict=True)
        if not candidate.is_absolute() or '..' in candidate.parts or candidate.suffix.casefold() != '.lua' or (canonical != candidate) or (not 0 <= source.bytes <= MAX_FILE_BYTES) or (not any((canonical.is_relative_to(root) for root in roots))):
            raise ValueError('Mapped selected script is not canonical beneath approved roots')
        unique[source.sha256] = source.bytes
    if sum(unique.values()) > MAX_TOTAL_BYTES:
        raise ValueError('Selected script context exceeds the existing total byte bound')

def _selected_script_path(name, context, roots, reader):
    from civ6_host.runtime import capture_script_paths as paths
    source = context.source_by_selected.get(name)
    if source is None:
        raise ValueError('Selected script is absent from its exact context mapping')
    if reader is not None:
        resolved = paths.resolve_path(name, context, roots, cwd_reader=reader)
        return (resolved.resolved_path, dict(bytes=resolved.bytes, sha256=resolved.sha256))
    resolved = _resolve_resource_path(_resolve_resource_path(Path(source.resolved_path))).resolve(strict=True)
    return (resolved, dict(bytes=source.bytes, sha256=source.sha256))

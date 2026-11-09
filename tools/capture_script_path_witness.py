"""Pin the exact selected XP2 script paths from an already-running official game."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from civ6_host.runtime import capture_script_paths as paths
from civ6_host.runtime.native.native_gameplay_source_capture import (
    MAX_SELECTED_SCRIPTS, MAX_TOTAL_BYTES, _read, approved_roots,
)
from civ6_host.runtime.paths import resource_root


def _pin(path, raw):
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def capture(selection_path, selection_sha256, roots, *, path_resolution_report=None,
            path_resolution_sha256=None, observer=paths.observe_process_cwd):
    """Produce the existing capture994 witness schema without scanning assets."""
    deadline = time.monotonic() + 15
    selection_path = selection_path.absolute()
    raw = paths._read_bytes(str(selection_path), 'runtime selection', limit=paths.MAX_SELECTION_BYTES)
    selection = _pin(selection_path, raw)
    if selection['sha256'] != selection_sha256:
        raise ValueError('Runtime selection does not match the requested SHA-256')
    selected_capture = json.loads(raw)['gameplay_selection994']
    process = selected_capture['process']
    snapshot = selected_capture['snapshot']
    current = (snapshot.get('executable_sha256') == paths.CURRENT_EXE_SHA256
               and selected_capture['gamecore_module']['sha256'] == paths.CURRENT_CORE_SHA256)
    historical = (snapshot.get('executable_sha256') == paths.EXE_SHA256
                  and selected_capture['gamecore_module']['sha256'] == paths.XP2_SHA256)
    if not (current or historical):
        raise ValueError('Runtime selection must match one explicit supported XP2 path profile')
    if current and (path_resolution_report is None or path_resolution_sha256 is None):
        raise ValueError('Current EXE captures require the guarded v3 native path-resolution report')
    selected = snapshot['selected_paths']
    if type(selected) is not list or not 0 < len(selected) <= MAX_SELECTED_SCRIPTS:
        raise ValueError('Expected a bounded nonempty native script selection')
    for name in selected:
        paths._validate_selected_name(name)
    roots = approved_roots(roots)
    observer_identity = dict(process)
    if current:
        observer_identity.update(profile_id=paths.CURRENT_V3_PROFILE_ID,
                                 exe_sha256=paths.CURRENT_EXE_SHA256,
                                 gamecore_sha256=paths.CURRENT_CORE_SHA256,
                                 override_bindings_sha256=paths.CURRENT_OVERRIDE_BINDINGS_SHA256)
    first = observer(observer_identity)
    if first.get('process') != process:
        raise ValueError('Observed process does not own the runtime selection')
    cwd = first['cwd']
    paths._validate_absolute_local(cwd, 'observed process CWD')
    native_paths = None
    path_report_pin = None
    capture_id = None
    if current:
        report_path = Path(path_resolution_report).absolute()
        report_raw = paths._read_bytes(str(report_path), 'native path-resolution report',
                                       limit=paths.MAX_PROOF_BYTES)
        if hashlib.sha256(report_raw).hexdigest() != path_resolution_sha256:
            raise ValueError('Native path-resolution report does not match the requested SHA-256')
        try:
            path_report = json.loads(report_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('Native path-resolution report is not valid JSON') from exc
        native_paths, _nested_proofs, capture_id = paths._validate_v3_resolution_report(
            path_report, paths._identity(process), selected, cwd,
            first['resolver_live']['script_manager'],
            (selection['path'], selection['bytes'], selection['sha256']),
        )
        path_report_pin = _pin(report_path, report_raw)
    sources = {}
    total = 0
    resolved_order = []
    for index, name in enumerate(selected):
        resolved_path = native_paths[index] if native_paths is not None else paths._cwd_join(cwd, name)
        candidate = Path(resolved_path)
        paths._utf16_bound(str(candidate))
        if candidate not in sources:
            _, source = _read(candidate, roots, deadline)
            total += source['bytes']
            if total > MAX_TOTAL_BYTES:
                raise ValueError('Selected sources exceed the capture byte bound')
            sources[candidate] = dict(path=str(candidate), bytes=source['bytes'], sha256=source['sha256'])
        resolved_order.append(sources[candidate])
    if time.monotonic() >= deadline or observer(observer_identity) != first:
        raise ValueError('Process, CWD or resolver changed during the source read')

    proof_path = (resource_root() / paths.CURRENT_BINDINGS_PATH if current else
                  resource_root() / 'evidence/phase42-map-setup.json')
    proof = _pin(proof_path, paths._read_bytes(str(proof_path), 'resolver proof'))
    caller_proof = None
    override_proof = None
    if current:
        caller_path = resource_root() / paths.CURRENT_CALLER_BINDINGS_PATH
        caller_proof = _pin(caller_path, paths._read_bytes(str(caller_path), 'current caller proof'))
        override_path = resource_root() / paths.CURRENT_OVERRIDE_BINDINGS_PATH
        override_proof = _pin(override_path, paths._read_bytes(str(override_path), 'current actual override proof'))
    observer_path = Path(paths.__file__).resolve(strict=True)
    observer_pin = _pin(observer_path, paths._read_bytes(str(observer_path), 'process observer'))
    record = dict(schema=paths.CURRENT_V3_SCHEMA if current else paths.SCHEMA,
                  status=paths.CURRENT_V3_STATUS if current else paths.STATUS,
                  at=datetime.now(timezone.utc).isoformat(),
                  process=process, cwd=cwd, selected=selected,
                  resolved_sources=resolved_order,
                  selection_witness=selection, resolver_source=proof,
                  **({'caller_source': caller_proof} if caller_proof is not None else {}),
                  **({'override_source': override_proof,
                      'path_resolution_report': path_report_pin,
                      'capture_id': capture_id} if current else {}),
                  resolver_live=dict(first['resolver_live']), observer=observer_pin,
                  psutil_version=first['psutil_version'], native_function_called=current,
                  **({'native_method_called': True} if current else {}),
                  game_memory_written=None if current else False,
                  **({'external_process_memory_write_performed': False,
                      'native_resolver_state_changes_proven_absent': False,
                      'filesystem_search_scope': 'capture_python_only'} if current else {}),
                  process_environment_read=False, filesystem_search_used=False,
                  historical_execution_bytes_proven=False)
    raw = json.dumps(record, indent=2).encode('utf-8') + b'\n'
    if len(raw) > paths.MAX_WITNESS_BYTES:
        raise ValueError('Produced witness exceeds the capture byte bound')
    paths._parse_context(record, hashlib.sha256(raw).hexdigest(), paths._identity(process))
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection', type=Path, help='Pinned runtime-selection JSON from the same process')
    parser.add_argument('--sha256', required=True, help='Exact runtime-selection JSON digest')
    parser.add_argument('--path-resolution-report', type=Path,
                        help='Reviewed v3 helper report for the current EXE profile')
    parser.add_argument('--path-resolution-sha256',
                        help='Exact SHA-256 of the v3 helper report')
    parser.add_argument('--script-root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True, help='New witness JSON path')
    args = parser.parse_args()
    raw = capture(args.selection, args.sha256, args.script_root,
                  path_resolution_report=args.path_resolution_report,
                  path_resolution_sha256=args.path_resolution_sha256)
    output = args.output.absolute()
    paths._reject_reparse_components(output.parent)
    with output.open('xb') as stream:
        stream.write(raw)
    print(json.dumps(_pin(output, raw)))


if __name__ == '__main__':
    main()

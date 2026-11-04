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


def capture(selection_path, selection_sha256, roots, *, observer=paths.observe_process_cwd):
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
    if (snapshot.get('executable_sha256') != paths.EXE_SHA256
            or selected_capture['gamecore_module']['sha256'] != paths.XP2_SHA256):
        raise ValueError('Runtime selection must come from the supported official XP2 process')
    selected = snapshot['selected_paths']
    if type(selected) is not list or not 0 < len(selected) <= MAX_SELECTED_SCRIPTS:
        raise ValueError('Expected a bounded nonempty native script selection')
    for name in selected:
        paths._validate_selected_name(name)
    roots = approved_roots(roots)
    first = observer(process)
    if first.get('process') != process:
        raise ValueError('Observed process does not own the runtime selection')
    cwd = first['cwd']
    paths._validate_absolute_local(cwd, 'observed process CWD')
    sources = {}
    total = 0
    for name in selected:
        candidate = Path(paths._cwd_join(cwd, name))
        paths._utf16_bound(str(candidate))
        if candidate not in sources:
            _, source = _read(candidate, roots, deadline)
            total += source['bytes']
            if total > MAX_TOTAL_BYTES:
                raise ValueError('Selected sources exceed the capture byte bound')
            sources[candidate] = dict(path=str(candidate), bytes=source['bytes'], sha256=source['sha256'])
    if time.monotonic() >= deadline or observer(process) != first:
        raise ValueError('Process, CWD or resolver changed during the source read')

    proof_path = resource_root() / 'evidence/phase42-map-setup.json'
    proof = _pin(proof_path, paths._read_bytes(str(proof_path), 'resolver proof'))
    observer_path = Path(paths.__file__).resolve(strict=True)
    observer_pin = _pin(observer_path, paths._read_bytes(str(observer_path), 'process observer'))
    record = dict(schema=paths.SCHEMA, status=paths.STATUS, at=datetime.now(timezone.utc).isoformat(),
                  process=process, cwd=cwd, selected=selected,
                  resolved_sources=[sources[Path(paths._cwd_join(cwd, name))] for name in selected],
                  selection_witness=selection, resolver_source=proof,
                  resolver_live=dict(first['resolver_live']), observer=observer_pin,
                  psutil_version=first['psutil_version'], native_function_called=False,
                  game_memory_written=False, process_environment_read=False,
                  filesystem_search_used=False, historical_execution_bytes_proven=False)
    raw = json.dumps(record, indent=2).encode('utf-8') + b'\n'
    if len(raw) > paths.MAX_WITNESS_BYTES:
        raise ValueError('Produced witness exceeds the capture byte bound')
    paths._parse_context(record, hashlib.sha256(raw).hexdigest(), paths._identity(process))
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection', type=Path, help='Pinned runtime-selection JSON from the same process')
    parser.add_argument('--sha256', required=True, help='Exact runtime-selection JSON digest')
    parser.add_argument('--script-root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True, help='New witness JSON path')
    args = parser.parse_args()
    raw = capture(args.selection, args.sha256, args.script_root)
    output = args.output.absolute()
    paths._reject_reparse_components(output.parent)
    with output.open('xb') as stream:
        stream.write(raw)
    print(json.dumps(_pin(output, raw)))


if __name__ == '__main__':
    main()

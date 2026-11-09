"""Capture a stable, still-unqualified phase-1 Civ6 evidence bundle.

This command only attaches to an explicitly named, already-running game
process. It never launches, suspends, writes to, or controls the game. Captures
are published only after source files and process/module identity remain
unchanged over the checked capture interval. The result is intentionally not
training-eligible: this tool does not prove that a save used the captured
database or scripts, nor that component application succeeded.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
from datetime import datetime
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/capture_phase1_bundle974.py')))).resolve().parents[1]
if str(ROOT) not in sys.path:
    pass
from civ6_host.runtime.native.official_save import MAX_SAVE_BYTES
DATABASE_ROLES = ('DebugConfiguration', 'DebugGameplay', 'DebugLocalization')
LOG_ROLES = ('Modding.log', 'Database.log', 'Startup.log', 'GameCoreAppConfig.log')
MAX_DATABASE_BYTES = 512 * 1024 * 1024
MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_AUXILIARY_BYTES = 3 * MAX_DATABASE_BYTES + len(LOG_ROLES) * MAX_LOG_BYTES
MAX_CAPTURE_SECONDS = 240.0
CHUNK_BYTES = 1024 * 1024

class BundleCaptureRefused(RuntimeError):
    """Capture stopped because identity or input stability was not proven."""

def _sha256_file(path: Path, deadline: float) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('Capture exceeded its time bound')
            block = stream.read(CHUNK_BYTES)
            if not block:
                return digest.hexdigest()
            digest.update(block)

def _file_state(path: Path, deadline: float, limit: int) -> dict:
    from civ6_host.runtime.resource_resolution import historical_reference
    from civ6_host.runtime.resource_resolution import historical_reference
    source = _resolve_resource_path(path).resolve(strict=True)
    if not _resolve_resource_path(source).is_file():
        raise ValueError(f'Not a regular input file: {source}')
    before = _resolve_resource_path(source).stat()
    if before.st_size > limit:
        raise ValueError(f'Input exceeds byte bound ({before.st_size}>{limit}): {source}')
    digest = _sha256_file(source, deadline)
    after = _resolve_resource_path(source).stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise BundleCaptureRefused(f'Input changed while hashing: {source}')
    return historical_reference({'path': str(source), 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest})

def _copy_checked(source: Path, destination: Path, expected: dict, deadline: float) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0
    with _resolve_resource_path(source).open('rb') as reader, _resolve_resource_path(destination).open('xb') as writer:
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('Capture exceeded its time bound while copying')
            block = reader.read(CHUNK_BYTES)
            if not block:
                break
            written += len(block)
            if written > expected['bytes']:
                raise BundleCaptureRefused(f'Input grew during copy: {source}')
            writer.write(block)
            digest.update(block)
        writer.flush()
        os.fsync(writer.fileno())
    copied_sha = digest.hexdigest()
    if written != expected['bytes'] or copied_sha != expected['sha256']:
        raise BundleCaptureRefused(f'Copied bytes do not match preflight hash: {source}')
    return {'bytes': written, 'sha256': copied_sha}

def _normal(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))

def _validate_inputs(save: Path, databases: dict[str, Path], logs: dict[str, Path], output: Path, root: Path, deadline: float) -> tuple[dict, dict, int]:
    if set(databases) != set(DATABASE_ROLES):
        raise ValueError('Provide exactly one path for each required database role: ' + ', '.join(DATABASE_ROLES))
    if set(logs) != set(LOG_ROLES):
        raise ValueError('Provide exactly one path for each required log: ' + ', '.join(LOG_ROLES))
    root = _resolve_resource_path(root).resolve()
    work = _resolve_resource_path(root / 'work').resolve()
    final = output if output.is_absolute() else root / output
    final = _resolve_resource_path(final).resolve()
    if not final.is_relative_to(work) or _resolve_resource_path(final).exists():
        raise ValueError('Output must be a fresh directory beneath project work/')
    if final.name in ('', '.', '..'):
        raise ValueError('Invalid output directory name')
    paths = {'save': save, **{f'database:{key}': value for key, value in databases.items()}, **{f'log:{key}': value for key, value in logs.items()}}
    resolved = {}
    seen = set()
    for role, value in paths.items():
        source = _resolve_resource_path(_resolve_resource_path(Path(value))).resolve(strict=True)
        if not _resolve_resource_path(source).is_file():
            raise ValueError(f'{role} input is not a regular file: {source}')
        normalized = _normal(source)
        if normalized in seen:
            raise ValueError(f'Input paths must be distinct; duplicate at {role}: {source}')
        seen.add(normalized)
        if source == final or source.is_relative_to(final):
            raise ValueError(f'Input overlaps output directory: {source}')
        resolved[role] = source
    database_sidecars = {}
    for name in DATABASE_ROLES:
        db_path = resolved[f'database:{name}']
        for suffix in ('-wal', '-shm', '-journal'):
            sidecar = _resolve_resource_path(Path(str(db_path) + suffix))
            if _resolve_resource_path(sidecar).exists():
                sidecar = _resolve_resource_path(sidecar).resolve(strict=True)
                normalized = _normal(sidecar)
                if normalized in seen:
                    raise ValueError(f'Database sidecar duplicates another input: {sidecar}')
                seen.add(normalized)
                resolved[f'database-sidecar:{name}{suffix}'] = sidecar
                database_sidecars[f'{name}{suffix}'] = _file_state(resolved[f'database-sidecar:{name}{suffix}'], deadline, MAX_DATABASE_BYTES)
    save_state = _file_state(resolved['save'], deadline, MAX_SAVE_BYTES)
    database_states = {name: _file_state(resolved[f'database:{name}'], deadline, MAX_DATABASE_BYTES) for name in DATABASE_ROLES}
    log_states = {name: _file_state(resolved[f'log:{name}'], deadline, MAX_LOG_BYTES) for name in LOG_ROLES}
    total = save_state['bytes'] + sum((x['bytes'] for x in database_states.values())) + sum((x['bytes'] for x in log_states.values())) + sum((x['bytes'] for x in database_sidecars.values()))
    if total > MAX_AUXILIARY_BYTES + MAX_SAVE_BYTES:
        raise ValueError('Total input set exceeds aggregate file capture bound')
    return ({'save': save_state, 'databases': database_states, 'database_sidecars': database_sidecars, 'logs': log_states}, resolved, total)

class _OfficialBackend:
    """Thin adapters over the two already-reviewed read-only capture tools."""

    def __init__(self, *, executable_sha256=None):
        from civ6_host.runtime.workers import capture_official_content929 as content929
        from civ6_host.runtime.workers import capture_official_save907 as save907
        from civ6_host.runtime.native.native_resolved_content import EXE_SHA
        from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
        executable_sha256 = EXE_SHA if executable_sha256 is None else executable_sha256
        if executable_sha256 not in (EXE_SHA, CURRENT_EXE_SHA):
            raise BundleCaptureRefused('Unsupported official capture executable')
        self.executable_sha256 = executable_sha256
        self.content929 = content929
        self.save907 = save907

    def pinned_executable(self) -> tuple[Path, str]:
        from civ6_host.runtime.native.native_resolved_content import EXE_SHA
        from civ6_host.runtime.native.native_resolved_content import source_profile
        return (_resolve_resource_path(_resolve_resource_path(Path(source_profile(self.executable_sha256)['image']['path']))).resolve(strict=True), self.executable_sha256)

    def snapshot_process(self, pid: int, deadline: float) -> dict:
        expected, expected_sha = self.pinned_executable()
        if _sha256_file(expected, deadline) != expected_sha:
            raise BundleCaptureRefused('Installed executable differs from the pinned official image')
        with self.content929.ReadOnlyProcess(pid) as process:
            identity = process.identity()
            modules = process.modules()
            if process.identity() != identity:
                raise BundleCaptureRefused('PID/creation identity changed during module enumeration')
        if identity['pid'] != pid or _normal(identity['image_path']) != _normal(expected):
            raise BundleCaptureRefused('PID does not identify the pinned CivilizationVI.exe')
        main = [m for m in modules if _normal(m['path']) == _normal(expected)]
        gamecores = [m for m in modules if m['name'].casefold().startswith('gamecore_') and m['name'].casefold().endswith('.dll')]
        if len(main) != 1 or len(gamecores) != 1:
            raise BundleCaptureRefused('Expected exactly one pinned main image and one GameCore module')
        core_path = _resolve_resource_path(_resolve_resource_path(Path(gamecores[0]['path']))).resolve(strict=True)
        core_sha = _sha256_file(core_path, deadline)
        if not _resolve_resource_path(core_path).is_file():
            raise BundleCaptureRefused('Loaded GameCore image path is not a regular file')
        return {'identity': identity, 'exe_module': main[0], 'exe_sha256': expected_sha, 'gamecore_module': {**gamecores[0], 'path': str(core_path), 'sha256': core_sha}, 'module_inventory': sorted(({'name': m['name'], 'path': str(_resolve_resource_path(_resolve_resource_path(Path(m['path']))).resolve(strict=False)), 'base': m['base'], 'bytes': m['bytes']} for m in modules), key=lambda x: (x['name'].casefold(), x['path'].casefold(), x['base']))}

    def capture_content(self, pid: int) -> dict:
        return self.content929.capture(pid, executable_sha256=self.executable_sha256)

    def capture_save(self, source: Path, output_dir: Path) -> dict:
        return self.save907.capture(source, output_dir)

def _tool_source_pins(deadline: float) -> dict[str, str]:
    paths = {'tools/capture_phase1_bundle974.py': _resolve_resource_path(Path(_historical_source_file('tools/capture_phase1_bundle974.py'))), 'tools/capture_official_save907.py': ROOT / 'tools/capture_official_save907.py', 'tools/capture_official_content929.py': ROOT / 'tools/capture_official_content929.py', 'tools/extract_active_content928.py': ROOT / 'tools/extract_active_content928.py', 'civ6rl/native_resolved_content.py': ROOT / 'civ6rl/native_resolved_content.py', 'civ6rl/native_gameplay_script_profile.py': ROOT / 'civ6rl/native_gameplay_script_profile.py'}
    return {name: _sha256_file(path, deadline) for name, path in paths.items()}

def _capture_with_backend(*, pid: int, save: Path, databases: dict[str, Path], logs: dict[str, Path], output: Path, root: Path, backend, monotonic=time.monotonic) -> dict:
    if type(pid) is not int or not 0 < pid < 2 ** 32:
        raise ValueError('An explicit positive 32-bit --pid is required')
    started = monotonic()
    deadline = started + MAX_CAPTURE_SECONDS
    input_states, resolved, total_bytes = _validate_inputs(_resolve_resource_path(Path(save)), databases, logs, _resolve_resource_path(Path(output)), _resolve_resource_path(Path(root)), deadline)
    tool_source_pins = _tool_source_pins(deadline)
    final = _resolve_resource_path(Path(output)) if _resolve_resource_path(Path(output)).is_absolute() else _resolve_resource_path(Path(root)) / _resolve_resource_path(Path(output))
    final = _resolve_resource_path(final).resolve()
    stage = final.with_name(f'.{final.name}.partial-{uuid.uuid4().hex}')
    process_before = backend.snapshot_process(pid, deadline)
    stage.parent.mkdir(parents=True, exist_ok=True)
    stage.mkdir()
    try:
        content = backend.capture_content(pid)
        if monotonic() > deadline:
            raise TimeoutError('Content capture exceeded time bound')
        content_identity = content.get('process')
        if content_identity != process_before['identity']:
            raise BundleCaptureRefused('929 capture identity differs from the initial PID snapshot')
        content_core = content.get('gamecore_module', {})
        initial_main = process_before['exe_module']
        captured_main = content.get('exe_module', {})
        same_main = initial_main.get('name') == captured_main.get('name') and _normal(initial_main.get('path', '')) == _normal(captured_main.get('path', '')) and (initial_main.get('base') == captured_main.get('base')) and (initial_main.get('bytes') == captured_main.get('bytes'))
        if not same_main or _normal(content_core.get('path', '')) != _normal(process_before['gamecore_module']['path']) or content_core.get('base') != process_before['gamecore_module']['base'] or (content_core.get('bytes') != process_before['gamecore_module']['bytes']) or (content_core.get('sha256') != process_before['gamecore_module']['sha256']):
            raise BundleCaptureRefused('929 executable/GameCore module evidence differs from initial snapshot')
        save_dir = stage / 'save-capture'
        save_dir.mkdir()
        save_capture = backend.capture_save(resolved['save'], save_dir)
        if save_capture.get('sha256') != input_states['save']['sha256']:
            raise BundleCaptureRefused('907 save hash differs from the initial source hash')
        if monotonic() > deadline:
            raise TimeoutError('Save capture exceeded time bound')
        copied_databases = {}
        for name in DATABASE_ROLES:
            state = input_states['databases'][name]
            target = stage / 'databases' / f"{name}{resolved[f'database:{name}'].suffix}"
            copied_databases[name] = {**state, 'copy': _copy_checked(resolved[f'database:{name}'], target, state, deadline)}
            copied_databases[name]['copy']['path'] = target.relative_to(stage).as_posix()
        copied_logs = {}
        for name in LOG_ROLES:
            state = input_states['logs'][name]
            target = stage / 'logs' / name
            copied_logs[name] = {**state, 'copy': _copy_checked(resolved[f'log:{name}'], target, state, deadline)}
            copied_logs[name]['copy']['path'] = target.relative_to(stage).as_posix()
        copied_sidecars = {}
        for name, state in input_states['database_sidecars'].items():
            source = resolved[f'database-sidecar:{name}']
            target = stage / 'databases' / source.name
            copied_sidecars[name] = {**state, 'copy': _copy_checked(source, target, state, deadline)}
            copied_sidecars[name]['copy']['path'] = target.relative_to(stage).as_posix()
        after_states, _, _ = _validate_inputs(_resolve_resource_path(Path(save)), databases, logs, _resolve_resource_path(Path(output)), _resolve_resource_path(Path(root)), deadline)
        if after_states != input_states:
            raise BundleCaptureRefused('One or more source input hashes or metadata changed during capture')
        process_after = backend.snapshot_process(pid, deadline)
        if process_after != process_before:
            raise BundleCaptureRefused('PID, creation time, executable or loaded module inventory changed')
        if _tool_source_pins(deadline) != tool_source_pins:
            raise BundleCaptureRefused('Capture or script-profile source changed during capture')
        if not content.get('snapshot', {}).get('observed_ranges_unchanged', False):
            raise BundleCaptureRefused('929 did not verify resolved-content memory ranges unchanged')
        content_path = stage / 'resolved-content929.json'
        with _resolve_resource_path(content_path).open('x', encoding='utf-8') as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        manifest = {'schema': 'civ6rl.phase1_capture_bundle974.v1', 'status': 'captured_unqualified', 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'training_eligible': False, 'explicit_pid': pid, 'tool_source_sha256': tool_source_pins, 'capture_bounds': {'max_seconds': MAX_CAPTURE_SECONDS, 'elapsed_seconds': monotonic() - started, 'max_auxiliary_bytes': MAX_AUXILIARY_BYTES, 'input_bytes': total_bytes, 'database_file_limit_bytes': MAX_DATABASE_BYTES, 'log_file_limit_bytes': MAX_LOG_BYTES, 'max_save_bytes': MAX_SAVE_BYTES}, 'process_identity': {'before': process_before, 'after': process_after, 'same_pid_creation_exe_core_and_module_inventory': True}, 'save_capture907': save_capture, 'resolved_content_capture929': {'path': content_path.name, 'snapshot_schema': content.get('snapshot', {}).get('schema'), 'content_application_success_proven': False, 'save_identity_bound': False, 'database_identity_bound': False, 'gameplay_scripts_bound': False}, 'database_copies': copied_databases, 'database_sidecar_copies': copied_sidecars, 'log_copies': copied_logs, 'input_stability': {'pre_and_post_sha256_and_mtime_size_equal': True, 'all_copied_hashes_match_preflight': True, 'atomic_snapshot_proven': False}, 'gameplay_script_evidence': {'resolved_component_vectors': ['configured_mod_handles', 'active_mod_handles', 'ordered_component_handles'], 'resolved_content_source_pins': {'provider_source_sha256': '195332488e5f10d5144992d7113d9da225866791bcfd5bd61d361e7fa72ad730', 'active_population_source_sha256': '1834968828bc7ab614f29eae7458e56dfadddcf6dd9b3d65b36d4c3b169b6583'}, 'reuse_mechanism': 'capture_official_content929.capture(pid) returns pinned, ordered resolved component/mod handle vectors; native_gameplay_script_profile.plan_standard_base can select explicitly supplied ordered script files only for its pinned RULESET_STANDARD/Base/Continents profile after caller resolves each component applicability.', 'not_proven': ['component application succeeded', 'actual gameplay Lua files loaded or executed', 'all DLC/mod applicability and script gates resolved'], 'static_finding': 'extract_active_content928.py identifies active-vector population before the apply pipeline; it is static analysis and does not witness successful application or script execution.'}, 'association_gaps': ['save-to-current-process association is not proven by co-capture alone', 'final database/log build provenance and save-to-database ruleset association are not proven', 'actual gameplay script inventory and successful component application are not proven', 'scenario identity and map seed must be separately recorded for a panel', 'no artifact qualification verifier is implemented'], 'unresolved': ['same-run save/database/content association', 'current-run final database build proof', 'actual gameplay script inventory and activation witness', 'ruleset and scenario/map-seed qualification']}
        manifest['bundle_path'] = final.relative_to(_resolve_resource_path(_resolve_resource_path(Path(root))).resolve()).as_posix()
        manifest['manifest_path'] = (final / 'manifest.json').relative_to(_resolve_resource_path(_resolve_resource_path(Path(root))).resolve()).as_posix()
        if save_capture.get('sha256'):
            manifest['save_capture907']['manifest'] = (final / 'save-capture' / save_capture['sha256'] / 'manifest.json').relative_to(_resolve_resource_path(_resolve_resource_path(Path(root))).resolve()).as_posix()
        manifest_path = stage / 'manifest.json'
        with _resolve_resource_path(manifest_path).open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        if _resolve_resource_path(final).exists():
            raise ValueError('Output directory appeared before publication')
        os.replace(stage, final)
        return manifest
    except Exception as exc:
        refusal = {'schema': 'civ6rl.phase1_capture_bundle974.refusal.v1', 'status': 'capture_refused', 'training_eligible': False, 'pid': pid, 'reason': f'{type(exc).__name__}: {exc}', 'partial_path': str(stage), 'published': False, 'created_at_utc': datetime.now(timezone.utc).isoformat()}
        try:
            stage.mkdir(parents=True, exist_ok=True)
            with _resolve_resource_path(stage / 'capture-refusal.json').open('x', encoding='utf-8') as stream:
                json.dump(refusal, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        except Exception:
            pass
        if isinstance(exc, (ValueError, BundleCaptureRefused, TimeoutError)):
            raise BundleCaptureRefused(refusal['reason']) from exc
        raise

def capture_bundle(*, pid: int, save: Path, databases: dict[str, Path], logs: dict[str, Path], output: Path, root: Path=ROOT) -> dict:
    """Run one explicit capture using only the pinned 907 and 929 readers."""
    return _capture_with_backend(pid=pid, save=save, databases=databases, logs=logs, output=output, root=root, backend=_OfficialBackend())

def _named_paths(values: list[str], roles: tuple[str, ...], option: str) -> dict[str, Path]:
    result = {}
    for value in values:
        if '=' not in value:
            raise ValueError(f'{option} values must be ROLE=PATH')
        name, path = value.split('=', 1)
        if name not in roles or not path.strip() or name in result:
            raise ValueError(f'Invalid or duplicate {option} role: {name}')
        result[name] = _resolve_resource_path(Path(path))
    if set(result) != set(roles):
        raise ValueError(f"{option} requires exactly: {', '.join(roles)}")
    return result

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', required=True, type=int, help='Explicit PID of an already-running pinned Civ6 process')
    parser.add_argument('--save', required=True, type=Path, help='Existing Civ6 save path')
    parser.add_argument('--database', action='append', required=True, metavar='ROLE=PATH', help='Repeat once for DebugConfiguration, DebugGameplay and DebugLocalization')
    parser.add_argument('--log', action='append', required=True, metavar='ROLE=PATH', help='Repeat once for Modding.log, Database.log, Startup.log and GameCoreAppConfig.log')
    parser.add_argument('--output', required=True, type=Path, help='Fresh final bundle directory beneath project work/')
    args = parser.parse_args(argv)
    try:
        result = capture_bundle(pid=args.pid, save=args.save, databases=_named_paths(args.database, DATABASE_ROLES, '--database'), logs=_named_paths(args.log, LOG_ROLES, '--log'), output=args.output)
    except Exception as exc:
        print(json.dumps({'status': 'capture_refused', 'training_eligible': False, 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

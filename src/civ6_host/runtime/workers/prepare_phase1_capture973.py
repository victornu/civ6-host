"""Read-only dry-run planner for a future, process-bound Civ6 capture panel.

This preflight never starts the game, reads process memory, copies a save/cache,
or writes outputs. It reports which existing capture commands could be used
later and which identity/script capture work is still missing.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
import ctypes as C
from datetime import datetime
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/prepare_phase1_capture973.py')))).resolve().parents[1]
if str(ROOT) not in sys.path:
    pass
MAX_SAVES = 16
PANEL_MIN_SCENARIOS = 3
PROCESS_QUERY_LIMITED_INFORMATION = 4096
TH32CS_SNAPPROCESS = 2
TH32CS_SNAPMODULE = 8
TH32CS_SNAPMODULE32 = 16
ERROR_NO_MORE_FILES = 18

class _ProcessEntry(C.Structure):
    _fields_ = [('dwSize', C.c_uint32), ('cntUsage', C.c_uint32), ('th32ProcessID', C.c_uint32), ('th32DefaultHeapID', C.c_size_t), ('th32ModuleID', C.c_uint32), ('cntThreads', C.c_uint32), ('th32ParentProcessID', C.c_uint32), ('pcPriClassBase', C.c_long), ('dwFlags', C.c_uint32), ('szExeFile', C.c_wchar * 260)]

class _ModuleEntry(C.Structure):
    _fields_ = [('dwSize', C.c_uint32), ('th32ModuleID', C.c_uint32), ('th32ProcessID', C.c_uint32), ('GlblcntUsage', C.c_uint32), ('ProccntUsage', C.c_uint32), ('modBaseAddr', C.c_void_p), ('modBaseSize', C.c_uint32), ('hModule', C.c_void_p), ('szModule', C.c_wchar * 256), ('szExePath', C.c_wchar * 260)]

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _normalized_path(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))

def _expected_executable() -> tuple[str | None, str | None]:
    try:
        from civ6_host.runtime.native.native_resolved_content import source_profile
        image_path = source_profile()['image']['path']
        return (str(_resolve_resource_path(_resolve_resource_path(Path(image_path))).resolve(strict=False)), None)
    except Exception as exc:
        return (None, f'{type(exc).__name__}: {exc}')

def _query_process_image(kernel32, pid: int) -> dict:
    kernel32.OpenProcess.argtypes = [C.c_uint32, C.c_int, C.c_uint32]
    kernel32.OpenProcess.restype = C.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [C.c_void_p, C.c_uint32, C.c_wchar_p, C.POINTER(C.c_uint32)]
    kernel32.QueryFullProcessImageNameW.restype = C.c_int
    kernel32.GetProcessTimes.argtypes = [C.c_void_p, C.POINTER(C.c_uint64), C.POINTER(C.c_uint64), C.POINTER(C.c_uint64), C.POINTER(C.c_uint64)]
    kernel32.GetProcessTimes.restype = C.c_int
    kernel32.CloseHandle.argtypes = [C.c_void_p]
    kernel32.CloseHandle.restype = C.c_int
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return {'pid': pid, 'query_status': 'inaccessible', 'error_code': C.get_last_error()}
    try:
        buffer = C.create_unicode_buffer(32768)
        length = C.c_uint32(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(length)):
            return {'pid': pid, 'query_status': 'image_path_unavailable', 'error_code': C.get_last_error()}
        created, exited, kernel, user = (C.c_uint64() for _ in range(4))
        if not kernel32.GetProcessTimes(handle, C.byref(created), C.byref(exited), C.byref(kernel), C.byref(user)):
            return {'pid': pid, 'query_status': 'creation_identity_unavailable', 'image_path': buffer.value, 'error_code': C.get_last_error()}
        return {'pid': pid, 'query_status': 'queried', 'image_path': buffer.value, 'creation_filetime': created.value}
    finally:
        kernel32.CloseHandle(handle)

def _snapshot_process_ids(kernel32) -> list[tuple[int, str]]:
    kernel32.CreateToolhelp32Snapshot.argtypes = [C.c_uint32, C.c_uint32]
    kernel32.CreateToolhelp32Snapshot.restype = C.c_void_p
    kernel32.Process32FirstW.argtypes = [C.c_void_p, C.POINTER(_ProcessEntry)]
    kernel32.Process32FirstW.restype = C.c_int
    kernel32.Process32NextW.argtypes = [C.c_void_p, C.POINTER(_ProcessEntry)]
    kernel32.Process32NextW.restype = C.c_int
    kernel32.CloseHandle.argtypes = [C.c_void_p]
    kernel32.CloseHandle.restype = C.c_int
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        entry = _ProcessEntry()
        entry.dwSize = C.sizeof(entry)
        if not kernel32.Process32FirstW(snapshot, C.byref(entry)):
            raise C.WinError(C.get_last_error())
        result = []
        while True:
            result.append((int(entry.th32ProcessID), entry.szExeFile))
            if len(result) > 32768:
                raise RuntimeError('Process snapshot exceeded its bound')
            C.set_last_error(0)
            if not kernel32.Process32NextW(snapshot, C.byref(entry)):
                error = C.get_last_error()
                if error != ERROR_NO_MORE_FILES:
                    raise C.WinError(error)
                return result
    finally:
        kernel32.CloseHandle(snapshot)

def _snapshot_modules(pid: int) -> list[dict]:
    if os.name != 'nt':
        return []
    kernel32 = C.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [C.c_uint32, C.c_uint32]
    kernel32.CreateToolhelp32Snapshot.restype = C.c_void_p
    kernel32.Module32FirstW.argtypes = [C.c_void_p, C.POINTER(_ModuleEntry)]
    kernel32.Module32FirstW.restype = C.c_int
    kernel32.Module32NextW.argtypes = [C.c_void_p, C.POINTER(_ModuleEntry)]
    kernel32.Module32NextW.restype = C.c_int
    kernel32.CloseHandle.argtypes = [C.c_void_p]
    kernel32.CloseHandle.restype = C.c_int
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        entry = _ModuleEntry()
        entry.dwSize = C.sizeof(entry)
        if not kernel32.Module32FirstW(snapshot, C.byref(entry)):
            raise C.WinError(C.get_last_error())
        result = []
        while True:
            result.append({'name': entry.szModule, 'path': entry.szExePath, 'base': int(entry.modBaseAddr or 0), 'bytes': int(entry.modBaseSize)})
            if len(result) > 4096:
                raise RuntimeError('Module snapshot exceeded its bound')
            C.set_last_error(0)
            if not kernel32.Module32NextW(snapshot, C.byref(entry)):
                error = C.get_last_error()
                if error != ERROR_NO_MORE_FILES:
                    raise C.WinError(error)
                return result
    finally:
        kernel32.CloseHandle(snapshot)

def _process_inventory(pid: int | None, expected_exe: str | None) -> dict:
    if expected_exe is None:
        return {'status': 'source_profile_unavailable', 'candidates': [], 'method': 'Win32 process/image-path query only; no memory reads'}
    if os.name != 'nt':
        return {'status': 'platform_unavailable', 'candidates': [], 'method': 'Win32 process/image-path query only; no memory reads'}
    kernel32 = C.WinDLL('kernel32', use_last_error=True)
    try:
        if pid is None:
            exe_name = _resolve_resource_path(Path(expected_exe)).name.casefold()
            ids = [(candidate_pid, name) for candidate_pid, name in _snapshot_process_ids(kernel32) if name.casefold() == exe_name]
            if not ids:
                return {'status': 'absent', 'candidates': [], 'query_proof': {'process_snapshot_completed': True, 'matching_executable_name_count': 0}, 'method': 'Toolhelp process snapshot plus limited image-path queries; no memory reads'}
            pids = [candidate_pid for candidate_pid, _ in ids]
        else:
            pids = [pid]
        candidates = []
        for candidate_pid in pids:
            row = _query_process_image(kernel32, candidate_pid)
            if row['query_status'] != 'queried':
                candidates.append(row)
                continue
            exact = _normalized_path(row['image_path']) == _normalized_path(expected_exe)
            row['matches_pinned_executable_path'] = exact
            if exact:
                try:
                    modules = _snapshot_modules(candidate_pid)
                    gamecores = [m for m in modules if m['name'].lower().startswith('gamecore_') and m['name'].lower().endswith('.dll')]
                    row['loaded_gamecore_module_count'] = len(gamecores)
                    row['loaded_gamecore_modules'] = []
                    for module in gamecores:
                        record = dict(module)
                        path = _resolve_resource_path(Path(module['path']))
                        try:
                            record['disk_sha256'] = _sha256_file(path)
                        except OSError as exc:
                            record['disk_sha256_error'] = f'{type(exc).__name__}: {exc}'
                        row['loaded_gamecore_modules'].append(record)
                except Exception as exc:
                    row['module_query_error'] = f'{type(exc).__name__}: {exc}'
                    row['loaded_gamecore_module_count'] = None
            candidates.append(row)
        exact_candidates = [row for row in candidates if row.get('matches_pinned_executable_path') is True]
        if pid is not None:
            if len(exact_candidates) == 1:
                status = 'explicit_pid_matches_pinned_executable'
            elif candidates and candidates[0].get('query_status') != 'queried':
                status = 'explicit_pid_unverifiable'
            else:
                status = 'explicit_pid_not_pinned_executable'
        elif not exact_candidates:
            status = 'no_pinned_executable_process'
        elif len(exact_candidates) == 1:
            status = 'one_process_detected_pid_selection_required'
        else:
            status = 'multiple_processes_pid_selection_required'
        return {'status': status, 'candidates': candidates, 'query_proof': {'explicit_pid_supplied': pid is not None, 'process_identity_queried': True, 'process_memory_read': False}, 'method': 'Toolhelp snapshot and PROCESS_QUERY_LIMITED_INFORMATION only; no memory reads'}
    except Exception as exc:
        return {'status': 'query_failed', 'candidates': [], 'error': f'{type(exc).__name__}: {exc}', 'method': 'Win32 process/image-path query only; no memory reads'}

def _inspect_save(path: Path) -> dict:
    from civ6_host.runtime.native.official_save import MAX_SAVE_BYTES
    from civ6_host.runtime.native.official_save import inspect_save
    try:
        source = _resolve_resource_path(path).resolve(strict=True)
        before = _resolve_resource_path(source).stat()
        if before.st_size > MAX_SAVE_BYTES:
            return {'path': str(source), 'status': 'too_large', 'bytes': before.st_size}
        raw = _resolve_resource_path(source).read_bytes()
        after = _resolve_resource_path(source).stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return {'path': str(source), 'status': 'changed_during_preflight'}
        report, _sections = inspect_save(raw)
        if _sha256_file(source) != report['sha256']:
            return {'path': str(source), 'status': 'changed_during_preflight'}
        return {'path': str(source), 'status': 'structurally_inspected', 'bytes': len(raw), 'sha256': report['sha256'], 'gamecore_candidate_count': report['gamecore_candidate_count'], 'ruleset_string_hints': report['ruleset_string_hints'], 'active_ruleset_proven': False, 'matched_database_fixture': None, 'capture_performed': False}
    except FileNotFoundError:
        return {'path': str(path), 'status': 'not_found', 'capture_performed': False}
    except Exception as exc:
        return {'path': str(path), 'status': 'inspection_failed', 'error': f'{type(exc).__name__}: {exc}', 'capture_performed': False}

def _historical_cache_snapshot(root: Path) -> dict:
    manifest_path = root / 'work/phase23-native-fixture01/manifest.json'
    if not _resolve_resource_path(manifest_path).is_file():
        return {'status': 'historical_manifest_missing', 'process_bound': False, 'training_eligible': False}
    try:
        manifest = json.loads(_resolve_resource_path(manifest_path).read_text(encoding='utf-8'))
    except Exception as exc:
        return {'status': 'historical_manifest_invalid', 'error': f'{type(exc).__name__}: {exc}', 'process_bound': False, 'training_eligible': False}
    databases = {}
    for name, record in manifest.get('databases', {}).items():
        copy_record = record.get('copy', {})
        copied_path = _resolve_resource_path(Path(copy_record.get('path', '')))
        error = None
        try:
            copied_path = _resolve_resource_path(copied_path).resolve(strict=True)
            if not copied_path.is_relative_to(_resolve_resource_path(root / 'work').resolve()):
                raise ValueError('Historical copy path escaped work/')
            current_sha = _sha256_file(copied_path)
            matches = current_sha == copy_record.get('sha256') == record.get('source', {}).get('sha256')
            status = 'historical_copy_hash_matches' if matches else 'historical_copy_hash_mismatch'
        except Exception as exc:
            current_sha = None
            matches = False
            status = 'copy_unavailable_or_unverifiable'
            error = f'{type(exc).__name__}: {exc}'
        row = {'status': status, 'sha256_in_manifest': copy_record.get('sha256'), 'source_sha256_in_manifest': record.get('source', {}).get('sha256'), 'matches_historical_source_and_copy': matches, 'current_sha256': current_sha}
        if not matches:
            row['error'] = error or 'hash mismatch'
        databases[name] = row
    logs = manifest.get('provenance', {}).get('logs', {})
    log_summary = {name: {'recorded_sha256': row.get('sha256'), 'recorded_mtime_utc': row.get('mtime_utc'), 'path': row.get('path'), 'bound_to_phase1_pid': False} for name, row in logs.items()}
    return {'status': 'historical_diagnostic_cache_only', 'manifest_path': manifest_path.relative_to(root).as_posix(), 'manifest_sha256': _sha256_file(manifest_path), 'purpose': manifest.get('purpose'), 'eligible_for_training': manifest.get('eligible_for_training', False), 'source_provenance_ambiguous': manifest.get('provenance', {}).get('ambiguous'), 'process_bound': False, 'databases': databases, 'logs': log_summary, 'diagnostic_mod_note': manifest.get('provenance', {}).get('modding_log_observed'), 'final_database_identity_for_current_save_proven': False}

def _fresh_work_output(value: str | Path | None, root: Path) -> dict:
    base = _resolve_resource_path(root / 'work').resolve()
    if value is None:
        path = base / 'phase1-learning973' / ('capture-output-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        suffix = 0
        while _resolve_resource_path(path).exists():
            suffix += 1
            path = path.with_name(f'{path.name}-{suffix:02d}')
    else:
        candidate = _resolve_resource_path(Path(value))
        path = _resolve_resource_path(candidate if candidate.is_absolute() else root / candidate).resolve()
    valid = path.is_relative_to(base) and (not _resolve_resource_path(path).exists())
    return {'path': path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path), 'valid_fresh_work_path': valid, 'created': False, 'reason': None if valid else 'output_must_be_new_and_beneath_project_work'}

def _save_command(saves: list[dict], output_path: str) -> str | None:
    if not saves or not all((row.get('status') == 'structurally_inspected' for row in saves)):
        return None
    hashes = [row.get('sha256') for row in saves]
    if len(set(hashes)) != len(hashes):
        return None
    args = [sys.executable, 'tools/capture_official_save907.py']
    for row in saves:
        args.extend(['--save', row['path']])
    args.extend(['--output', output_path])
    return subprocess.list2cmdline(args)

def build_plan(*, pid: int | None=None, saves: list[str] | None=None, output: str | Path | None=None, root: Path=ROOT, expected_exe: str | None=None, process_inventory: dict | None=None, cache_snapshot: dict | None=None) -> dict:
    """Build a plan without launching capture tools or writing any files."""
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    if pid is not None and (type(pid) is not int or not 0 < pid < 2 ** 32):
        raise ValueError('pid must be a positive 32-bit integer')
    save_paths = [] if saves is None else list(saves)
    if len(save_paths) > MAX_SAVES:
        raise ValueError(f'At most {MAX_SAVES} save paths can be planned')
    if any((type(path) is not str or not path.strip() for path in save_paths)):
        raise ValueError('save paths must be non-empty strings')
    profile_error = None
    if expected_exe is None:
        expected_exe, profile_error = _expected_executable()
    process = process_inventory if process_inventory is not None else _process_inventory(pid, expected_exe)
    saves_preflight = [_inspect_save(_resolve_resource_path(Path(path))) for path in save_paths]
    cache = cache_snapshot if cache_snapshot is not None else _historical_cache_snapshot(root)
    destination = _fresh_work_output(output, root)
    exact_process_rows = [row for row in process.get('candidates', []) if row.get('matches_pinned_executable_path') is True]
    selected_process = next((row for row in exact_process_rows if row.get('pid') == pid), None)
    if pid is not None and selected_process is not None:
        gamecore_count = selected_process.get('loaded_gamecore_module_count')
        content_ready = gamecore_count == 1
        content_reason = 'one pinned Civ6 executable and one loaded GameCore module observed' if content_ready else 'expected exactly one loaded GameCore module'
    else:
        content_ready = False
        content_reason = 'explicit --pid required to select detected process' if exact_process_rows else 'pinned CivilizationVI.exe process not verified'
    save_command = _save_command(saves_preflight, destination['path']) if destination['valid_fresh_work_path'] else None
    content_command = None
    if content_ready and destination['valid_fresh_work_path']:
        content_path = f"{destination['path'].rstrip('/')}/resolved-content-{pid}.json"
        content_command = subprocess.list2cmdline([sys.executable, 'tools/capture_official_content929.py', '--pid', str(pid), '--output', content_path])
    blockers = []
    if expected_exe is None:
        blockers.append('pinned_executable_profile_unavailable')
    if pid is None:
        blockers.append('explicit_pid_not_supplied')
    if not exact_process_rows:
        blockers.append('pinned_game_process_not_found_or_not_verified')
    if not saves_preflight:
        blockers.append('save_path_not_supplied')
    elif any((row.get('status') != 'structurally_inspected' for row in saves_preflight)):
        blockers.append('one_or_more_save_inputs_not_inspectable')
    blockers.extend(['save_capture_not_performed', 'save_to_same_process_identity_not_recorded', 'current_run_final_database_bundle_not_captured', 'database_build_logs_not_bound_to_pid_and_save', 'actual_gameplay_script_files_and_activation_not_captured', 'content_application_success_not_verified', 'scenario_seed_panel_not_recorded', 'artifact_qualification_verifier_not_present'])
    if not destination['valid_fresh_work_path']:
        blockers.append('proposed_output_path_invalid_or_not_fresh')
    actions = [{'id': 'save_container_capture', 'state': 'available_after_preflight' if save_command else 'blocked_missing_or_invalid_save', 'command': save_command, 'source': 'tools/capture_official_save907.py', 'facts': 'Accepts repeated --save (1..16) and required fresh --output under work/. Hashes and extracts the save container read-only, but writes capture artifacts when run. Its manifest intentionally leaves matched_database_fixture and configuration_component null; ruleset hints are not proof.'}, {'id': 'resolved_content_capture', 'state': 'available_after_preflight' if content_command else 'blocked_process_identity_or_gamecore_missing', 'command': content_command, 'source': 'tools/capture_official_content929.py', 'facts': 'Requires --pid and --output, validates pinned CivilizationVI.exe path, reads resolved ordered components and enabled-mod state with QUERY_INFORMATION|VM_READ, and checks identity/modules before and after. This is a read-only active capture, deliberately not run by this planner; it does not capture a save, final DB files, script files, or successful component application.'}, {'id': 'final_database_and_logs_bundle', 'state': 'not_automated_by_existing_capture_cli', 'existing_data': cache, 'reuse': ['civ6rl.native_host.validate_fixture', 'civ6rl.native_probe.prepare_init_fixture_copies', 'civ6rl.official_database_compare.compare_snapshots'], 'facts': 'The fixture-copy helper only consumes a pre-existing work/ manifest and writes private copies; compare_official_cache912.py compares two frozen fixtures and writes a fixed evidence path. Neither captures a current game-process-bound database/log bundle. The historical phase23 fixture is diagnostic and process_bound=false.'}, {'id': 'loaded_gameplay_script_inventory', 'state': 'implementation_required', 'existing_static_tool': 'tools/extract_active_content928.py', 'facts': '928 is static EXE/source analysis and explicitly does not execute UpdateContent or observe runtime activation. 929 reports resolved component handles/mod IDs, not the script-file set actually loaded or executed. Need a process-bound inventory of script paths/hashes plus a source-backed loader/registry activation witness; do not equate enabled mods with loaded scripts.'}, {'id': 'same_run_identity_manifest', 'state': 'implementation_required', 'facts': 'Join explicit PID plus creation time, executable/GameCore paths and hashes, save SHA/capture manifest, all final DB hashes, database/log build records, script inventory/activation, ruleset and scenario seed/map-seed into one immutable run manifest. Digests by themselves do not establish association.'}]
    return {'schema': 'civ6rl.phase1_capture_preflight973.v1', 'mode': 'dry_run_read_only_preflight', 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'side_effects': {'game_launched': False, 'process_memory_read': False, 'capture_tools_invoked': False, 'files_written': False}, 'pinned_executable': {'path': expected_exe, 'source_profile_error': profile_error}, 'process_preflight': process, 'explicit_pid': pid, 'save_inputs': saves_preflight, 'proposed_output': destination, 'historical_cache_preflight': cache, 'actions': actions, 'future_scenario_panel': {'minimum_distinct_scenarios': PANEL_MIN_SCENARIOS, 'minimum_distinct_map_seeds': PANEL_MIN_SCENARIOS, 'turn_135_required': False, 'seed_and_map_seed_source': 'record explicitly from scenario setup; do not infer from save-string hints', 'current_panel_qualified': False, 'scenario_ids': []}, 'eligibility': {'metadata_complete': False, 'training_eligible': False, 'blockers': list(dict.fromkeys(blockers)), 'rule': 'This planner never returns training_eligible=true. File hashes and caller declarations do not verify artifact association, script activation, task value, or held-out evidence.'}, 'existing_cli_contracts': {'capture_official_save907': 'python tools/capture_official_save907.py --save SAVE [--save SAVE ...] --output FRESH_WORK_DIR', 'capture_official_content929': 'python tools/capture_official_content929.py --pid PID --output FRESH_WORK_JSON', 'capture_content_help_verified': True, 'cache_tools_are_cli_capture_tools': False}}

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, help='Existing CivilizationVI.exe PID to inspect; never launched.')
    parser.add_argument('--save', type=Path, action='append', default=[], help='Existing save path to inspect locally; repeat for a future panel (max 16).')
    parser.add_argument('--output', type=Path, help='Proposed fresh directory under project work/; never created by dry-run.')
    args = parser.parse_args(argv)
    plan = build_plan(pid=args.pid, saves=[str(path) for path in args.save], output=args.output)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

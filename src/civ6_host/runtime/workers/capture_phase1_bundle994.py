"""Explicit official-session capture; never starts the game or installs a mod.

preflight is read-only. capture sends diagnostic requests and creates one NEW
save through FileClient.save_snapshot. No gameplay actions are submitted.
The result is a correlated evidence bundle, not scenario/training admission.
"""
from __future__ import annotations
from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
from civ6_host.runtime.native.native_resolved_content import CURRENT_LAYOUT_SHA
from civ6_host.runtime.native.native_resolved_content import CURRENT_POPULATION_SHA
from civ6_host.runtime.native.native_resolved_content import CURRENT_FRAMEWORK_SHA
from civ6_host.runtime import localization_bulk_export as bulk_export
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
from dataclasses import replace
from datetime import datetime
from datetime import timezone
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import re
import sys
import time
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/capture_phase1_bundle994.py')))).resolve().parents[1]
if str(ROOT) not in sys.path:
    pass
from civ6_host.runtime.native.database_capture992 import require
from civ6_host.runtime.native.database_capture992 import validate_request
from civ6_host.runtime.native.database_capture_bundle993 import Limits
from civ6_host.runtime.native.database_capture_bundle993 import capture_bundle
from civ6_host.runtime.native.database_capture_bundle993 import compare_sqlite_export
from civ6_host.runtime.native.database_capture_bundle993 import verify_bundle
from civ6_host.runtime.native.file_client import FileClient
from civ6_host.runtime.native.response_file_client import ResponseFileClient
from civ6_host.runtime.native.protocol import validate_observation
from civ6_host.runtime.native.native_resolved_content import ACTIVE_SHA
from civ6_host.runtime.native.native_resolved_content import EXE_SHA
from civ6_host.runtime.native.native_resolved_content import MAX_HANDLES
from civ6_host.runtime.native.native_resolved_content import PROVIDER_SHA
from civ6_host.runtime.workers import capture_phase1_bundle974 as legacy
from civ6_host.runtime.workers import prepare_phase1_capture973 as preparation
from civ6_host.runtime.workers.observe_pid_open_files975 import observe_pid_open_files
BRIDGE_FILES = ('Civ6RL.modinfo', 'UI/Civ6RL.lua', 'UI/Civ6RL.xml', 'UI/Civ6RLIncludeProbe.lua', 'UI/Civ6RLFileTransport.lua', 'UI/Civ6RLDatabaseCapture992.lua', 'UI/Civ6RLUIAvailability.lua')
MAX_SECONDS = 1500.0
MAX_LOGICAL_CAPTURE_SECONDS = 9000.0
TOOL_FILES = ('tools/capture_phase1_bundle994.py', 'tools/capture_phase1_bundle974.py', 'tools/prepare_phase1_capture973.py', 'tools/observe_pid_open_files975.py', 'tools/capture_official_content929.py', 'tools/capture_official_save907.py', 'civ6rl/database_capture992.py', 'civ6rl/database_capture_bundle993.py', 'civ6rl/file_client.py', 'civ6rl/log_tail.py', 'civ6rl/log_frames.py', 'civ6rl/protocol.py', 'civ6rl/native_resolved_content.py', 'civ6rl/native_gameplay_selection994.py', 'civ6rl/native_gameplay_empty.py', 'work/official-content929/current-exe-source.json', 'work/official-content929/current-exe-content-completion.json', 'work/official-content929/current-exe-provider-framework-binding.json', 'work/official-bundle/scripts-empty-source.json', 'civ6rl/native_ui_availability.py', 'work/ui-availability/source.json', 'work/ui-availability/source-v2.json', 'civ6rl/native_ui_local_state.py', 'work/ui-availability/local-state-source.json', 'civ6rl/native_gameplay_source_capture.py', 'civ6rl/native_localization_capture.py', 'work/official-capture/current-localization-shared-bindings.json', 'work/official-capture/current-localization-query-getters.json', 'work/official-capture/current-exe-localization-bindings.json', 'work/official-capture/localization-tuner-route.json', 'civ6rl/native_localization_export.py', 'civ6rl/tuner.py', 'civ6rl/native_localization_logical_export.py', 'civ6rl/native_localization_query.py', 'work/official-capture/localization-export.c', 'work/official-capture/localization-build.py', 'work/official-capture/localization-export-build02/build.json', 'work/official-capture/localization-export-build02/civ6rl-localization-export.dll', 'work/official-capture/localization-lookup-lifetime.json', 'evidence/phase35-thread-context.json', 'evidence/native-database-backup/5d19fa3f7c4348e24fcf66fe4f4eb05b0a9bb6f8b5a76bd93ae0b122840ea06e.json', 'civ6rl/native_gameplay_script_registry.py', 'civ6rl/native_include_registry.py')
CONTENT_VECTORS = ('configured_mod_handles', 'active_mod_handles', 'ordered_component_handles')
RESPONSE_TOOL_FILES = ('civ6rl/response_file_client.py', 'civ6rl/native_response_file_writer.py', 'mod/UI/Civ6RL.lua', 'mod/UI/Civ6RLFileTransport.lua')

class OfficialBackend(legacy._OfficialBackend):

    def inventory(self):
        path, _ = self.pinned_executable()
        return preparation._process_inventory(None, str(path))

    def capture_gameplay_selection(self, pid):
        from civ6_host.runtime.native.native_gameplay_selection994 import capture as capture_selection
        return capture_selection(pid, executable_sha256=self.executable_sha256, include_resolved_content=self.executable_sha256 == CURRENT_EXE_SHA)

    def capture_gameplay_empty(self, pid):
        from civ6_host.runtime.native.native_gameplay_empty import capture as capture_empty
        return capture_empty(pid, executable_sha256=self.executable_sha256) if self.executable_sha256 == CURRENT_EXE_SHA else capture_empty(pid)

    def capture_localization(self, pid, output, timeout_seconds):
        from civ6_host.runtime.native.native_localization_capture import capture as capture_localization
        return capture_localization(pid, output, timeout_seconds=timeout_seconds, executable_sha256=self.executable_sha256)

    def export_localization(self, pid, output, **kwargs):
        from civ6_host.runtime.native.native_localization_export import capture_export
        return capture_export(pid, output, **kwargs)

    def prepare_localization_export(self, pid, **kwargs):
        from civ6_host.runtime.native.native_localization_export import prepare_export_runtime
        return prepare_export_runtime(pid, **kwargs)

    def export_localization_logically(self, client, pid, output, **kwargs):
        from civ6_host.runtime.native.native_localization_logical_export import export_localization
        from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
        with ReadOnlyProcess(pid) as process:
            return export_localization(client, process, output, **kwargs)

    def capture_ui_local_state(self, pid, **kwargs):
        from civ6_host.runtime.native.native_ui_local_state import capture as capture_local_state
        from civ6_host.runtime.native.tuner import TunerClient
        with TunerClient(port=kwargs.get('tuner_port', 4318), timeout=kwargs['timeout_seconds']) as tuner:
            kwargs.pop('tuner_port', None)
            return capture_local_state(tuner, **kwargs)

def _join_native_report(report, process, schema):
    require(type(report) is dict and report.get('schema') == schema, 'Unexpected runtime selection report')
    require(report.get('process') == process['identity'], 'Runtime selection PID/creation identity differs')
    for name in ('exe_module', 'gamecore_module'):
        actual, expected = (report.get(name, {}), process[name])
        require(all((actual.get(k) == expected.get(k) for k in ('name', 'base', 'bytes'))) and legacy._normal(actual.get('path', '')) == legacy._normal(expected.get('path', '')), 'Runtime selection EXE/Core module differs')
    require(report['gamecore_module'].get('sha256') == process['gamecore_module']['sha256'], 'Runtime selection GameCore hash differs')

def _content_semantics(snapshot, process):
    current = process.get('exe_sha256') == CURRENT_EXE_SHA
    require(type(snapshot) is dict and snapshot.get('schema') == ('civ6rl.resolved_content929.memory_snapshot.v2' if current else 'civ6rl.resolved_content929.memory_snapshot.v1'), 'Missing resolved-content memory snapshot')
    require(snapshot.get('source_sha256') == PROVIDER_SHA and snapshot.get('active_population_source_sha256') == ACTIVE_SHA and (snapshot.get('executable_sha256') == process['exe_sha256']) and (process['exe_sha256'] in (EXE_SHA, CURRENT_EXE_SHA)) and (snapshot.get('image_base') == hex(process['exe_module']['base'])), 'Resolved-content source/image context differs')
    require(snapshot.get('observed_ranges_unchanged') is True and snapshot.get('read_only') is True, 'Resolved-content ranges were not verified stable')
    for flag in ('atomic_snapshot_proven', 'content_application_success_proven', 'save_identity_bound', 'database_identity_bound', 'gameplay_scripts_bound', 'strategic_training_ready', 'player_observation'):
        require(snapshot.get(flag) is False, 'Resolved-content report overclaims ' + flag)
    vectors = {}
    for name in CONTENT_VECTORS[1:] if current else CONTENT_VECTORS:
        value = snapshot.get(name)
        require(type(value) is list and len(value) <= MAX_HANDLES and all((type(x) is int and 0 <= x < 2 ** 32 for x in value)), 'Invalid ordered content vector')
        vectors[name] = value
    headers = snapshot.get('vector_headers_hex')
    require(type(headers) is dict and set(headers) == set(vectors) and all((type(v) is str and re.fullmatch('[0-9a-f]{48}', v) for v in headers.values())), 'Resolved-content vector headers missing')
    for field in ('manager_address', 'provider_address'):
        require(type(snapshot.get(field)) is str and re.fullmatch('0x[0-9a-f]+', snapshot[field]), 'Missing resolved-content context address')
    result = dict(manager_address=snapshot['manager_address'], provider_address=snapshot['provider_address'], vector_headers_hex=headers, **vectors)
    if current:
        require(snapshot.get('current_layout_source_sha256') == CURRENT_LAYOUT_SHA and snapshot.get('current_population_source_sha256') == CURRENT_POPULATION_SHA and (snapshot.get('current_framework_source_sha256') == CURRENT_FRAMEWORK_SHA) and (snapshot.get('provider_registry_relation_checked') is True) and (snapshot.get('opaque_manager_fields_interpreted') is False), 'Current resolved-content correspondence differs')
        opaque = snapshot.get('opaque_manager_headers')
        require(type(opaque) is dict and set(opaque) == {'manager_plus_0x1d8'} and (type(opaque['manager_plus_0x1d8']) is str) and (re.fullmatch('[0-9a-f]{48}', opaque['manager_plus_0x1d8']) is not None), 'Current unclassified manager field was interpreted or omitted')
        result['opaque_manager_headers'] = opaque
    return result

def _selection_semantics(selection, process, semantic):
    from civ6_host.runtime.native.native_gameplay_selection994 import AUX_SHA256
    from civ6_host.runtime.native.native_gameplay_selection994 import MAX_ROWS
    from civ6_host.runtime.native.native_gameplay_selection994 import ROUTE_SHA256
    from civ6_host.runtime.native.native_gameplay_selection994 import CURRENT_SOURCE_SHA256
    current = process.get('exe_sha256') == CURRENT_EXE_SHA
    _join_native_report(selection, process, 'civ6rl.official_gameplay_selection994.capture.v2' if current else 'civ6rl.official_gameplay_selection994.capture.v1')
    require(type(selection.get('consumer_core_matches_base_proof')) is bool, 'Gameplay selection consumer proof scope missing')
    state = selection.get('snapshot', {})
    require(state.get('schema') == ('civ6rl.gameplay_selection994.memory_snapshot.v2' if current else 'civ6rl.gameplay_selection994.memory_snapshot.v1') and state.get('observed_ranges_unchanged') is True and (state.get('atomic_snapshot_proven') is False) and (state.get('execution_proven') is False) and (state.get('save_identity_bound') is False), 'Gameplay selection lacks stable read or overclaims execution')
    require(state.get('route_source_sha256') == ROUTE_SHA256 and state.get('getter_source_sha256') == AUX_SHA256 and (state.get('executable_sha256') == process['exe_sha256']) and (state.get('image_base') == hex(process['exe_module']['base'])) and (state.get('read_only') is True), 'Gameplay selection source/image context differs')
    if current:
        require(state.get('current_correspondence_sha256') == CURRENT_SOURCE_SHA256 and state.get('resolved_content_captured') is True, 'Current selection lacks the explicit content bracket')
    for flag in ('source_file_bytes_bound', 'database_identity_bound', 'training_eligible', 'player_observation'):
        require(state.get(flag) is False, 'Gameplay selection overclaims ' + flag)
    require(_content_semantics(state.get('resolved_content'), process) == semantic and state.get('manager_address') == semantic['manager_address'], 'Gameplay selection belongs to another resolved-content context')
    header, records, paths = (state.get('vector_header_hex'), state.get('records'), state.get('selected_paths'))
    require(type(header) is str and re.fullmatch('[0-9a-f]{32}', header), 'Invalid gameplay vector header')
    require(type(records) is list and len(records) <= MAX_ROWS and (type(paths) is list) and (type(state.get('record_count')) is int) and (state['record_count'] == len(records)), 'Missing ordered gameplay selection')
    for index, row in enumerate(records):
        require(type(row) is dict and type(row.get('index')) is int and (row['index'] == index) and (type(row.get('consumer_skips')) is bool) and (row.get('path') is None or type(row['path']) is str) and (row['consumer_skips'] == (row.get('path') is None or row['path'] == '')) and (type(row.get('path_pointer')) is str) and re.fullmatch('0x[0-9a-f]+', row['path_pointer']), 'Gameplay records are unordered or incomplete')
    selected = [row.get('path') for row in records if row['consumer_skips'] is False]
    require(paths == selected and all((type(path) is str and path for path in paths)), 'Selected gameplay paths differ from ordered records')
    return dict(content=semantic, manager_address=state['manager_address'], vector_header_hex=header, records=records, selected_paths=paths)

def _capture_runtime_selections(backend, pid, process):
    from civ6_host.runtime.native.native_gameplay_selection994 import BASE_CORE_SHA256
    from civ6_host.runtime.native.native_gameplay_empty import SCHEMA
    from civ6_host.runtime.native.native_gameplay_empty import stable_capture_identity
    content = backend.capture_content(pid)
    _join_native_report(content, process, 'civ6rl.official_resolved_content929.capture.v2' if process.get('exe_sha256') == CURRENT_EXE_SHA else 'civ6rl.official_resolved_content929.capture.v1')
    content_state = _content_semantics(content.get('snapshot'), process)
    selection = backend.capture_gameplay_selection(pid)
    semantic = _selection_semantics(selection, process, content_state)
    absence = None
    from civ6_host.runtime.gameplay_active_profiles import SUPPORTED_CORES
    if process['gamecore_module']['sha256'] in SUPPORTED_CORES:
        absence = backend.capture_gameplay_empty(pid)
        _join_native_report(absence, process, SCHEMA)
        identity = stable_capture_identity(absence)
        require(_selection_semantics(absence['selection'], process, content_state) == semantic, 'Gameplay active-list witness belongs to another selection')
        semantic['active_gameplay_list'] = identity
    else:
        semantic['active_gameplay_list'] = None
    return dict(content929=content, gameplay_selection994=selection, gameplay_active_list=absence, semantic=semantic)

def _write(path, value):
    with _resolve_resource_path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write('\n')

def _localization_semantics(report, process, folder, deadline):
    """Join copied runtime ICU/settings, without accepting a database claim."""
    from civ6_host.runtime.native.native_localization_capture import ROUTE_SHA
    from civ6_host.runtime.native.native_localization_capture import source_profile
    from civ6_host.runtime.native.native_localization_capture import MAX_ICU_BYTES
    current = process.get('exe_sha256') == CURRENT_EXE_SHA
    profile = source_profile(process['exe_sha256'])
    require(type(report) is dict and report.get('schema') == ('civ6rl.localization_capture.v2' if current else 'civ6rl.localization_capture.v1') and (report.get('process') == process['identity']) and (report.get('route_source_sha256') == ROUTE_SHA), 'Localization process or source differs')
    require(report.get('process_identity_unchanged_before_after') is True and report.get('module_set_unchanged_before_after') is True and (report.get('runtime_memory_copied') is True), 'Localization runtime memory was not verified stable')
    for field in ('native_export_allowed', 'database_lifetime_lease_proven', 'game_executable_launched', 'remote_code_executed', 'memory_written', 'save_database_script_bundle_qualified', 'strategic_training_ready'):
        require(report.get(field) is False, 'Localization capture overclaims ' + field)
    require(report.get('database') is None, 'The read-only Localization producer cannot export a database')
    modules = report.get('modules', {})
    _join_native_report(dict(schema='localization_join', process=report['process'], exe_module=modules.get('exe'), gamecore_module=modules.get('gamecore')), process, 'localization_join')
    for kind in ('exe', 'localization', 'database', 'havok'):
        actual = modules.get(kind, {})
        expected = profile['images'][kind]
        require(actual.get('sha256') == expected['sha256'] and legacy._normal(actual.get('path', '')) == legacy._normal(expected['path']), 'Localization module source differs: ' + kind)
        matching = [module for module in process['module_inventory'] if legacy._normal(module.get('path', '')) == legacy._normal(actual['path'])]
        require(len(matching) == 1 and all((matching[0].get(key) == actual.get(key) for key in ('name', 'base', 'bytes'))), 'Localization module inventory differs: ' + kind)
    require(modules['exe']['sha256'] == process['exe_sha256'], 'Localization executable differs')
    state = report.get('snapshot', {})
    require(state.get('schema') == ('civ6rl.localization_memory_snapshot.v2' if current else 'civ6rl.localization_memory_snapshot.v1') and state.get('route_source_sha256') == ROUTE_SHA and (state.get('observed_ranges_unchanged') is True), 'Localization snapshot source/stability differs')
    if current:
        from civ6_host.runtime.native.native_localization_export import runtime_identity
        runtime_identity(report)
    for field in ('atomic_snapshot_proven', 'database_exported', 'database_lifetime_lease_proven', 'save_identity_bound', 'training_eligible'):
        require(state.get(field) is False, 'Localization snapshot overclaims ' + field)
    require(type(state.get('dictionary_flag')) is bool and report.get('dictionary_flag') == state['dictionary_flag'] and (report.get('locale') == state.get('locale')) and (type(state['locale']) is str) and re.fullmatch('[A-Za-z][A-Za-z0-9_@.\\-]{0,62}', state['locale']), 'Localization language/initializer differs')
    policy = 'strict' if state['dictionary_flag'] else 'priorities'
    require(state.get('fallback_policy') == policy and state.get('fallback_policy_sql') == profile['lookup_sql'][policy]['text'] and (state.get('fallback_policy_sql_sha256') == profile['lookup_sql'][policy]['sha256']), 'Localization fallback SQL differs')
    icu = report.get('icu_data', {})
    require(type(icu.get('path')) is str and _resolve_resource_path(_resolve_resource_path(Path(icu['path']))).resolve() == _resolve_resource_path(folder / 'loaded-icu.dat').resolve(), 'Loaded ICU copy escaped its capture folder')
    retained = _file(icu['path'], deadline, MAX_ICU_BYTES)
    require(retained['bytes'] == icu.get('bytes') == state.get('icu_bytes') and retained['sha256'] == icu.get('sha256') == state.get('icu_sha256'), 'Loaded ICU copy differs from runtime memory')
    fields = ('locale', 'dictionary_flag', 'fallback_policy_sql_sha256', 'dictionary_address', 'connection_address', 'lookup_result_address', 'auxiliary_result_address', 'statement_address', 'icu_address', 'icu_bytes', 'icu_sha256', 'language_address', 'language_index', 'languages_begin', 'languages_end')
    require(all((field in state for field in fields)), 'Incomplete Localization context')
    return {field: state[field] for field in fields}

def _localization_export_reference(result, process, expected_localization, output, deadline):
    reference = result.get('reference') if type(result) is dict else None
    require(type(reference) is dict and set(reference) == {'path', 'sha256', 'bytes'} and (type(reference.get('path')) is str) and (_resolve_resource_path(_resolve_resource_path(Path(reference['path']))).resolve().parent == _resolve_resource_path(output).resolve()), 'Localization export manifest escaped its new capture directory')
    actual = _file(reference['path'], deadline, 4 * 1024 * 1024)
    require(actual['bytes'] == reference['bytes'] and actual['sha256'] == reference['sha256'], 'Localization export reference changed')
    validate_export_manifest = _localization_export_validator(reference)
    verified = validate_export_manifest(reference, expected_process=process['identity'])
    identity = verified['runtime_identity']
    required = {'locale', 'dictionary_flag', 'dictionary_address', 'connection_address', 'icu_address', 'icu_bytes', 'icu_sha256', 'fallback_policy_sql_sha256'}
    require(type(identity) is dict and required.issubset(identity) and all((expected_localization['snapshot'].get(key) == value for key, value in identity.items())), 'Localization export belongs to another runtime dictionary/ICU')
    database = verified['database']
    require(type(database.get('bytes')) is int and 100 <= database['bytes'] <= 512 * 1024 * 1024 and (type(database.get('sha256')) is str) and re.fullmatch('[0-9a-f]{64}', database['sha256']), 'Localization export lacks exact database identity')
    return (dict(reference), verified)

def _localization_export_validator(reference):
    """Select an explicit producer contract; never retry another export route."""
    from civ6_host.runtime.native import native_localization_export as backup
    from civ6_host.runtime.native import native_localization_logical_export as logical
    path = _resolve_resource_path(Path(reference['path']))
    require(0 < _resolve_resource_path(path).stat().st_size <= 4 * 1024 * 1024, 'Unbounded Localization manifest')
    value = json.loads(_resolve_resource_path(path).read_text(encoding='utf8'))
    if value.get('schema') == logical.SCHEMA:
        return logical.validate_export_manifest
    require(value.get('schema') == backup.SCHEMA, 'Unknown Localization export contract')
    return backup.validate_export_manifest

def _file(path, deadline, limit=legacy.MAX_DATABASE_BYTES):
    return legacy._file_state(_resolve_resource_path(Path(path)), deadline, limit)

def _identity(snapshot, pid):
    identity = snapshot.get('identity', {})
    require(type(identity.get('pid')) is int and identity['pid'] == pid and (type(identity.get('creation_filetime')) is int) and (identity['creation_filetime'] > 0), 'Process snapshot has no exact PID/creation identity')
    require(_resolve_resource_path(Path(identity.get('image_path', ''))).name.casefold() == 'civilizationvi.exe', 'Wrong process image')
    for key in ('exe_sha256',):
        require(re.fullmatch('[0-9a-f]{64}', snapshot.get(key, '')), 'Missing pinned EXE hash')
    core = snapshot.get('gamecore_module', {})
    require(re.fullmatch('[0-9a-f]{64}', core.get('sha256', '')) and core.get('base') and core.get('bytes'), 'Missing GameCore identity')
    require(snapshot.get('exe_module', {}).get('base') and snapshot['exe_module'].get('bytes'), 'Missing EXE module identity')
    return identity

def _sole_process(backend, identity):
    inventory = backend.inventory()
    candidates = inventory.get('candidates')
    require(type(candidates) is list and len(candidates) == 1, 'Official process inventory absent, ambiguous or inaccessible')
    candidate = candidates[0]
    require(candidate.get('query_status') == 'queried' and candidate.get('matches_pinned_executable_path') is True and (candidate.get('pid') == identity['pid']) and (candidate.get('creation_filetime') == identity['creation_filetime']) and (legacy._normal(candidate.get('image_path', '')) == legacy._normal(identity['image_path'])), 'Process inventory differs from PID instance')
    return inventory

def _log_witness(observer, pid, log, identity, seconds):
    require(seconds >= 0.1, 'Time budget exhausted before log-handle scan')
    result = observer(pid, {'bridge_log': log}, expected_identity=identity, timeout_seconds=min(60.0, seconds))
    roles = result.get('requested_roles', {})
    require(result.get('complete_scan') is True and result.get('process_identity_stable') is True and (result.get('process_identity') == identity) and (set(roles) == {'bridge_log'}) and (roles['bridge_log'].get('open') is True) and re.fullmatch('[0-9a-f]{64}', roles['bridge_log'].get('file_identity_sha256', '')), 'Bridge Lua.log file object is not witnessed in the selected PID')
    return result

def _paths(*, inbox, log, save_directory, name, output, exports, root):
    require(type(name) is str and re.fullmatch('Civ6RLLab_[A-Za-z0-9_-]{1,90}', name), 'Invalid fresh save name')
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve(strict=True)
    inbox, log = (_resolve_resource_path(_resolve_resource_path(Path(inbox))).resolve(strict=True), _resolve_resource_path(_resolve_resource_path(Path(log))).resolve(strict=True))
    require(inbox.name == 'Civ6RLInbox.lua' and inbox.parent.name == 'UI' and _resolve_resource_path(inbox).is_file(), 'Invalid installed inbox')
    require(log.name == 'Lua.log' and _resolve_resource_path(log).is_file(), 'Explicit existing Lua.log required')
    require(not _resolve_resource_path(inbox.with_suffix('.lua.lock')).exists(), 'Bridge writer lock already exists')
    saves = _resolve_resource_path(_resolve_resource_path(Path(save_directory))).resolve(strict=True)
    require(_resolve_resource_path(saves).is_dir(), 'Save directory must already exist')
    target = saves / (name + '.Civ6Save')
    require(not _resolve_resource_path(target).exists(), 'Save already exists; no overwrite is permitted')
    output = _resolve_resource_path(root / output).resolve() if not _resolve_resource_path(Path(output)).is_absolute() else _resolve_resource_path(_resolve_resource_path(Path(output))).resolve()
    require(output.is_relative_to(root / 'work') and (not _resolve_resource_path(output).exists()), 'Use a fresh output beneath project work/')
    require(type(exports) is dict and set(exports) <= {'gameplay', 'configuration'}, 'Unknown export connection')
    resolved = {role: _resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True) for role, path in exports.items()}
    sources = [inbox, log, target, *resolved.values()]
    require(len({legacy._normal(p) for p in sources}) == len(sources), 'Input paths overlap')
    require(all((not p.is_relative_to(output) for p in sources)), 'Input path overlaps capture output')
    for path in resolved.values():
        require(_resolve_resource_path(path).is_file(), 'Export is not a regular file')
        require(all((not _resolve_resource_path(_resolve_resource_path(Path(str(path) + suffix))).exists() for suffix in ('-wal', '-shm', '-journal'))), 'Export has journal/WAL sidecars; provide standalone snapshots')
    return dict(inbox=inbox, log=log, save_directory=saves, save=target, output=output, exports=resolved, installed_mod=inbox.parent.parent)

def _bridge_pins(installed_mod, deadline):
    pins = {}
    for relative in BRIDGE_FILES:
        source = _file(bulk_export.bridge_source(relative, ROOT / 'mod' / relative, installed_mod / relative), deadline, 4 * 1024 * 1024)
        installed = _file(installed_mod / relative, deadline, 4 * 1024 * 1024)
        require(source['sha256'] == installed['sha256'] and source['bytes'] == installed['bytes'], 'Installed bridge differs from prepared source: ' + relative)
        pins[relative] = dict(source=source, installed=installed)
    return pins

def _tool_pins(deadline):
    pins = {name: _file(ROOT / name, deadline, 4 * 1024 * 1024) for name in TOOL_FILES}
    from civ6_host.runtime.provenance import installed_source_pins
    for path, expected in installed_source_pins().items():
        current = _file(_resolve_resource_path(Path(path)), deadline, 4 * 1024 * 1024)
        require(current['sha256'] == expected, 'Installed capture source changed during pinning')
        pins['installed:' + path] = current
    return pins

def _response_file_provenance(installation, process, deadline, *, predecessor=None):
    """Revalidate the retained writer handoff and its complete source closure."""
    from civ6_host.runtime.native import native_response_file_writer as writer
    if type(installation) is not dict:
        installation = writer.reference(_resolve_resource_path(_resolve_resource_path(Path(installation))).resolve(strict=True))
    require(set(installation) == {'path', 'bytes', 'sha256'} and writer.reference(installation['path']) == installation, 'Response writer installation pin differs')
    report = writer._json(_resolve_resource_path(_resolve_resource_path(Path(installation['path']))).read_bytes())
    checked = writer.validate_installation(report)
    require(checked['process'] == process['identity'], 'Response writer process identity differs')
    registration = writer._json(_resolve_resource_path(_resolve_resource_path(Path(checked['registration']['path']))).read_bytes())
    build = writer.verify_build(registration['build']['path'])
    dependencies = [installation, checked['registration'], registration['build'], *build['sources'], *build['snapshots'], build['dll']]
    for item in dependencies:
        observed = _file(_resolve_resource_path(Path(item['path'])), deadline, 4 * 1024 * 1024)
        require({key: observed[key] for key in ('path', 'bytes', 'sha256')} == item, 'Response writer dependency changed')
    result = dict(schema='civ6rl.response_file_transport_provenance.v1', mode='response_file_v1', installation=installation, registration=checked['registration'], build=registration['build'], dependencies=dependencies, prepared=checked['prepared'], process=checked['process'], player_id=report['player_id'], turn=report['turn'], implementation_sources={name: _file(ROOT / name, deadline, 4 * 1024 * 1024) for name in RESPONSE_TOOL_FILES})
    if predecessor is not None:
        from civ6_host.runtime.capture_response_continuation import validate_predecessor
        if type(predecessor) is not dict:
            predecessor = writer.reference(_resolve_resource_path(_resolve_resource_path(Path(predecessor))).resolve(strict=True))
        continued = validate_predecessor(predecessor, installation, exact_directory=False)
        require(continued['process'] == process['identity'], 'Continuation process identity differs')
        require(continued['prepared'] == checked['prepared'], 'Continuation writer identity differs')
        result['predecessor'] = dict(predecessor)
        result['predecessor_dependencies'] = [dict(predecessor), continued['prefix_snapshot'], *[row['response'] for row in continued['receipts']]]
        for item in result['predecessor_dependencies']:
            observed = _file(_resolve_resource_path(Path(item['path'])), deadline, 64 * 1024 * 1024)
            require({key: observed[key] for key in ('path', 'bytes', 'sha256')} == item, 'Capture predecessor dependency changed')
    return result

def preflight(*, pid, inbox, log, save_directory, name, output, exports=None, root=ROOT, backend=None, observer=observe_pid_open_files, timeout_seconds=120.0, script_roots=(), response_file_installation=None, response_file_predecessor=None, script_path_context=None, script_path_cwd_reader=None):
    """Inspect paths, hashes and an already-running process; no bridge command."""
    if script_path_context is None and script_path_cwd_reader is not None:
        raise ValueError('A script CWD observer requires an explicit script-path context')
    from civ6_host.runtime.native.native_gameplay_source_capture import _load_script_path_context
    from civ6_host.runtime.native.native_gameplay_source_capture import _script_path_provenance
    from civ6_host.runtime.native.native_gameplay_source_capture import _validate_script_path_roots
    require(response_file_predecessor is None or response_file_installation is not None, 'Capture continuation requires its explicit writer installation')
    require(type(pid) is int and 0 < pid < 2 ** 32, 'An explicit positive PID is required')
    require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and (1 <= timeout_seconds <= MAX_SECONDS), 'Invalid preflight timeout')
    started, deadline = (time.monotonic(), time.monotonic() + timeout_seconds)
    from civ6_host.runtime.native.native_gameplay_source_capture import approved_roots
    script_roots = approved_roots(script_roots)
    paths = _paths(inbox=inbox, log=log, save_directory=save_directory, name=name, output=output, exports=exports or {}, root=root)
    backend = backend or OfficialBackend()
    pins = _bridge_pins(paths['installed_mod'], deadline)
    tool_pins = _tool_pins(deadline)
    before = backend.snapshot_process(pid, deadline)
    identity = _identity(before, pid)
    path_context, _ = _load_script_path_context(script_path_context, process=identity)
    _validate_script_path_roots(path_context, script_roots)
    inventory = _sole_process(backend, identity)
    handle = _log_witness(observer, pid, paths['log'], identity, deadline - time.monotonic())
    require(backend.snapshot_process(pid, deadline) == before, 'Process changed during preflight')
    export_states = {role: _file(path, deadline) for role, path in paths['exports'].items()}
    response = None if response_file_installation is None else _response_file_provenance(response_file_installation, before, deadline, predecessor=response_file_predecessor)
    result = dict(schema='civ6rl.phase1_preflight994.v1', status='preflight_passed_capture_not_run', training_eligible=False, process=before, process_inventory=inventory, bridge_log_handle=handle, installed_bridge=pins, tool_source_pins=tool_pins, exports=export_states, selected_script_source_roots=[str(path) for path in script_roots], paths={k: str(v) for k, v in paths.items() if k != 'exports'}, elapsed_seconds=time.monotonic() - started, game_commands_sent=0, limitations=['Installed bytes do not prove the loaded UI context uses them.', 'A Lua.log handle does not identify the process emitting each log record.', 'No active connection read or save request was made by preflight.'])
    if response is not None:
        result['response_file_transport'] = response
    if path_context is not None:
        result['script_path_resolution'] = _script_path_provenance(script_path_context, path_context)
    return result

def _database_semantics(bundle):
    result = []
    for connection in bundle['passes'][0]:
        result.append(dict(connection=connection['connection'], metadata=connection['metadata'], objects=connection['objects'], tables=[dict(name=t['name'], columns=t['columns'], row_count=t['row_count'], rows_sha256=t['rows_sha256']) for t in connection['tables']]))
    return result

def capture(*, pid, inbox, log, save_directory, name, output, expected_player_id, expected_turn, exports=None, root=ROOT, backend=None, observer=observe_pid_open_files, client_factory=FileClient, limits=Limits(), timeout_seconds=MAX_SECONDS, ui_availability=False, script_roots=(), localization_state=False, localization_export_ui_context=None, ui_local_state=False, tuner_port=4318, localization_query_installation=None, localization_cache=None, response_file_installation=None, response_file_predecessor=None, script_path_context=None, script_path_cwd_reader=None):
    """Explicit correlated capture; refuses drift instead of silently joining it."""
    if script_path_context is None and script_path_cwd_reader is not None:
        raise ValueError('A script CWD observer requires an explicit script-path context')
    from civ6_host.runtime.native.native_gameplay_source_capture import _load_script_path_context
    from civ6_host.runtime.native.native_gameplay_source_capture import _script_path_provenance
    from civ6_host.runtime.native.native_gameplay_source_capture import _validate_script_path_roots
    require(response_file_predecessor is None or response_file_installation is not None, 'Capture continuation requires its explicit writer installation')
    limits.validate()
    require(response_file_installation is None or client_factory is FileClient, 'Explicit response-file transport cannot use an alternate client factory')
    require(type(ui_availability) is bool, 'UI availability capture option must be boolean')
    require(type(ui_local_state) is bool, 'UI local state capture option must be boolean')
    require(type(tuner_port) is int and 1 <= tuner_port <= 65535, 'Tuner port must be between 1 and 65535')
    require(type(localization_state) is bool, 'Localization capture option must be boolean')
    logical_export = localization_query_installation is not None
    require(logical_export == (localization_cache is not None), 'Logical Localization export requires both installation and cache candidate')
    require(not (logical_export and localization_export_ui_context is not None), 'Select exactly one Localization export route')
    if logical_export:
        from civ6_host.runtime.native.native_localization_export import reference
        localization_query_installation = reference(_resolve_resource_path(_resolve_resource_path(Path(localization_query_installation))).resolve(strict=True))
        localization_cache = _resolve_resource_path(_resolve_resource_path(Path(localization_cache))).resolve(strict=True)
        localization_state = True
    has_localization_export = logical_export or localization_export_ui_context is not None
    if localization_export_ui_context is not None:
        require(type(localization_export_ui_context) is str and 0 < len(localization_export_ui_context) <= 256 and ('\x00' not in localization_export_ui_context), 'Localization export requires one explicit UI context name')
        localization_state = True
    if ui_availability:
        from civ6_host.runtime.native.native_ui_availability import verify_source as verify_ui_source
        verify_ui_source()
    if ui_local_state:
        from civ6_host.runtime.native.native_ui_local_state import verify_source as verify_local_source
        verify_local_source()
    validate_request(dict(operation='metadata', connection='gameplay', expected_player_id=expected_player_id, expected_turn=expected_turn))
    require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and (1 <= timeout_seconds <= (MAX_LOGICAL_CAPTURE_SECONDS if logical_export else MAX_SECONDS)), 'Invalid capture timeout')
    started, deadline = (time.monotonic(), time.monotonic() + timeout_seconds)
    from civ6_host.runtime.native.native_gameplay_source_capture import approved_roots
    from civ6_host.runtime.native.native_gameplay_source_capture import capture_selected_sources
    from civ6_host.runtime.native.native_gameplay_source_capture import recheck_selected_sources
    script_roots = approved_roots(script_roots)
    backend = backend or OfficialBackend()
    paths = _paths(inbox=inbox, log=log, save_directory=save_directory, name=name, output=output, exports=exports or {}, root=root)
    localization_preparation = None
    if localization_export_ui_context is not None:
        _bridge_pins(paths['installed_mod'], deadline)
        _tool_pins(deadline)
        localization_preparation = backend.prepare_localization_export(pid, ui_context=localization_export_ui_context, timeout_seconds=min(30.0, deadline - time.monotonic()), tuner_port=tuner_port)
    checked = preflight(pid=pid, inbox=inbox, log=log, save_directory=save_directory, name=name, output=output, exports=exports, root=root, backend=backend, observer=observer, timeout_seconds=min(120.0, timeout_seconds), script_roots=script_roots, response_file_installation=response_file_installation, response_file_predecessor=response_file_predecessor, script_path_context=script_path_context, script_path_cwd_reader=script_path_cwd_reader)
    response = checked.get('response_file_transport')
    if response is not None:
        require(response['player_id'] == expected_player_id and response['turn'] == expected_turn, 'Response writer was installed at another player/turn boundary')
    destination = paths['output']
    destination.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema='civ6rl.phase1_capture994.v1', status='incomplete', training_eligible=False, strategic_training_ready=False, atomic_snapshot=False, preflight=checked, explicit_pid=pid, bridge_events=[], artifacts={}, export_matches={}, capture_operations=[], capture_operation_scope='Localization exports and official save request only')
    if localization_preparation is not None:
        manifest['localization_runtime_preparation'] = localization_preparation
    if response is not None:
        manifest['response_file_transport'] = response
    client, nonces, sequence = (None, set(), -1)
    verified_exports = {}

    def remaining():
        value = deadline - time.monotonic()
        require(value > 0, 'Capture time budget exhausted')
        return value

    def record(kind, value):
        nonlocal sequence
        require(type(value) is dict and type(value.get('player_id')) is int and (value['player_id'] == expected_player_id) and (type(value.get('turn')) is int) and (value['turn'] == expected_turn), 'Bridge boundary changed')
        nonce, seq = (value.get('request_id'), value.get('sequence'))
        require(type(nonce) is str and re.fullmatch('[A-Za-z0-9_.:-]{1,128}', nonce) and (nonce not in nonces) and (type(seq) is int) and (seq > sequence), 'Bridge nonce reused or sequence did not increase')
        nonces.add(nonce)
        sequence = seq
        manifest['bridge_events'].append(dict(kind=kind, nonce=nonce, sequence=seq))
        return value

    def observe():
        client.timeout = min(limits.request_timeout_seconds, remaining())
        value = record('observation', client.observe())
        require(value.get('type') == 'observation', 'Expected player observation')
        validate_observation(value.get('observation'))
        return value

    def database_reader(request, *, timeout):
        return record('database_capture', client.read_active_database(request, timeout=min(timeout, remaining())))

    def ui_reader():
        from civ6_host.runtime.native.native_ui_availability import validate_response as validate_ui_response
        value = record('ui_availability', client.read_ui_availability(expected_player_id=expected_player_id, expected_turn=expected_turn, timeout=min(limits.request_timeout_seconds, remaining())))
        require(value.get('type') == 'transport_status' and value.get('status') == 'ok' and (value.get('reason') == 'ui_availability_read'), 'UI availability acknowledgement differs')
        details = value.get('diagnostics', {})
        require(details.get('request_id') == value['request_id'] and details.get('completion') == 'read_only_current_ui' and (details.get('native_game_core_busy') is False), 'UI availability readback differs')
        validate_ui_response(details.get('ui_availability'), dict(expected_player_id=expected_player_id, expected_turn=expected_turn))
        return value

    def artifact(name, value):
        path = destination / name
        _write(path, value)
        manifest['artifacts'][name] = _file(path, deadline)

    def read_ui_locals():
        from civ6_host.runtime.native.native_ui_local_state import validate_capture
        require(backend.snapshot_process(pid, deadline) == checked['process'], 'Process changed before UI local state read')
        _sole_process(backend, checked['process']['identity'])
        value = backend.capture_ui_local_state(pid, expected_player_id=expected_player_id, expected_turn=expected_turn, timeout_seconds=min(30.0, remaining()), tuner_port=tuner_port)
        validate_capture(value, expected_player_id=expected_player_id, expected_turn=expected_turn)
        require(backend.snapshot_process(pid, deadline) == checked['process'], 'Process changed during UI local state read')
        _sole_process(backend, checked['process']['identity'])
        remaining()
        semantic = {kind: {key: item for key, item in context.items() if key != 'nonce'} for kind, context in value['contexts'].items()}
        return (value, semantic)

    def operation(kind, **details):
        manifest['capture_operations'].append(dict(index=len(manifest['capture_operations']), kind=kind, elapsed_seconds=time.monotonic() - started, **details))

    def export_localization(side, expected):
        folder = destination / ('localization-export-' + side)
        if logical_export:
            proxy = bulk_export.capture_proxy(client, paths['inbox'], database_reader, record, remaining)
            value = backend.export_localization_logically(proxy, pid, folder, installation_ref=localization_query_installation, cache_path=localization_cache, expected_player_id=expected_player_id, expected_turn=expected_turn, expected_localization=expected, timeout_seconds=min(3600.0, remaining()))
        else:
            value = backend.export_localization(pid, folder, ui_context=localization_export_ui_context, expected_player_id=expected_player_id, expected_turn=expected_turn, expected_localization=expected, timeout_seconds=min(30.0, remaining()), tuner_port=tuner_port)
        reference, verified = _localization_export_reference(value, checked['process'], expected, folder, deadline)
        require(verified['manifest']['expected_player_id'] == expected_player_id and verified['manifest']['expected_turn'] == expected_turn and (verified['manifest']['ui_context']['name'] == ('Civ6RL' if logical_export else localization_export_ui_context)), 'Localization export UI/player/turn differs from capture request')
        nonce = verified['manifest']['nonce']
        require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce) and all((other['manifest']['nonce'] != nonce for other in verified_exports.values())), 'Localization export nonce missing or reused')
        if side == 'after':
            bulk_export.same_profile(verified_exports['before']['manifest'], verified['manifest'])
            before_db, after_db = (verified_exports['before']['database'], verified['database'])
            require(all((before_db.get(key) == after_db.get(key) for key in ('sha256', 'bytes'))), 'Active Localization database changed across save')
        verified_exports[side] = verified
        manifest.setdefault('localization_exports', {})[side] = reference
        operation('localization_export', side=side, reference=reference, nonce=nonce)
        return value
    try:
        require(backend.snapshot_process(pid, deadline) == checked['process'], 'Process changed before bridge connection')
        client_options = dict(timeout=min(limits.request_timeout_seconds, remaining()))
        factory = client_factory
        if response is not None:
            factory = ResponseFileClient
            if response.get('predecessor') is not None:
                from civ6_host.runtime.capture_response_continuation import ContinuedResponseFileClient
                factory = ContinuedResponseFileClient
                client_options['predecessor'] = response['predecessor']
            client_options.update(installation=response['installation'], resume_hotseat=False)
        client = factory(paths['inbox'], paths['log'], **client_options)
        client.connect()
        require(type(client.session) is str and re.fullmatch('[0-9a-f]{32}', client.session), 'Invalid bridge session nonce')
        manifest['bridge_session'] = client.session
        require(response is None or client.session == response['prepared']['session_id'], 'Response writer and capture session differ')
        observation_before = observe()
        artifact('observation-before.json', observation_before)
        if ui_availability:
            ui_before = ui_reader()
            artifact('ui-availability-before.json', ui_before)
        if ui_local_state:
            ui_locals_before, ui_locals_identity = read_ui_locals()
            artifact('ui-local-state-before.json', ui_locals_before)
        if script_path_context is not None:
            path_context, path_reader = _load_script_path_context(script_path_context, script_path_cwd_reader, live=True, process=checked['process']['identity'])
            script_path_cwd_reader = path_reader
            _validate_script_path_roots(path_context, script_roots)
            runtime_before = _capture_runtime_selections(backend, pid, checked['process'])
            require(runtime_before['semantic']['selected_paths'] == list(path_context.selected_order), 'Raw selected script order differs from its pinned context before database capture')
            remaining()
            artifact('runtime-selections-before.json', runtime_before)
            manifest['script_path_resolution'] = checked['script_path_resolution']
        before = capture_bundle(database_reader, destination / 'databases-before', expected_player_id=expected_player_id, expected_turn=expected_turn, limits=replace(limits, timeout_seconds=min(limits.timeout_seconds, remaining())))
        verify_bundle(destination / 'databases-before')
        if script_path_context is None:
            runtime_before = _capture_runtime_selections(backend, pid, checked['process'])
            remaining()
            artifact('runtime-selections-before.json', runtime_before)
        if localization_state:
            localization_before = backend.capture_localization(pid, destination / 'localization-before', min(30.0, remaining()))
            localization_identity = _localization_semantics(localization_before, checked['process'], destination / 'localization-before', deadline)
            artifact('localization-before.json', localization_before)
            if has_localization_export:
                export_localization('before', localization_before)
        selected_paths = runtime_before['semantic']['selected_paths']
        script_files = None
        if script_roots or not selected_paths:
            script_files = capture_selected_sources(selected_paths, destination / 'selected-gameplay-sources', roots=script_roots, deadline=deadline, **{} if script_path_context is None else dict(script_path_context=script_path_context, script_path_cwd_reader=script_path_cwd_reader))
            manifest['selected_gameplay_sources'] = dict(manifest=_file(destination / 'selected-gameplay-sources/manifest.json', deadline), status=script_files['status'], disk_bytes_only=True, in_memory_execution_bytes_proven=False, includes_and_dependencies_captured=False)
        else:
            manifest['selected_gameplay_sources'] = dict(status='not_captured_no_approved_source_roots', selected_records=len(selected_paths), in_memory_execution_bytes_proven=False)
        require(backend.snapshot_process(pid, deadline) == checked['process'], 'Process changed before save request')
        require(not _resolve_resource_path(paths['save']).exists(), 'Save already exists immediately before request')
        client.timeout = min(limits.request_timeout_seconds, remaining())
        operation('official_save_request', name=name, expected_player_id=expected_player_id, expected_turn=expected_turn)
        saved = client.save_snapshot(name, save_directory=paths['save_directory'], expected_player_id=expected_player_id, expected_turn=expected_turn, timeout=min(120.0, remaining()))
        ack = record('save_snapshot', saved.get('acknowledgement'))
        require(ack.get('type') == 'transport_status' and ack.get('status') == 'ok' and (ack.get('reason') == 'save_snapshot_requested'), 'Save acknowledgement differs')
        require(legacy._normal(saved.get('path', '')) == legacy._normal(paths['save']), 'Save returned another path')
        state = _file(paths['save'], deadline, legacy.MAX_SAVE_BYTES)
        require(state['sha256'] == saved.get('sha256') and state['bytes'] == saved.get('bytes') and (state['bytes'] > 0), 'Saved bytes do not match the bridge receipt')
        artifact('save-receipt.json', saved)
        operation('official_save_acknowledged', request_id=ack['request_id'], sequence=ack['sequence'], player_id=ack['player_id'], turn=ack['turn'], save_sha256=state['sha256'])
        runtime_after = _capture_runtime_selections(backend, pid, checked['process'])
        remaining()
        artifact('runtime-selections-after.json', runtime_after)
        if localization_state:
            localization_after = backend.capture_localization(pid, destination / 'localization-after', min(30.0, remaining()))
            require(_localization_semantics(localization_after, checked['process'], destination / 'localization-after', deadline) == localization_identity, 'Localization context or loaded ICU changed across save')
            artifact('localization-after.json', localization_after)
            if has_localization_export:
                export_localization('after', localization_after)
            manifest['localization_runtime'] = dict(before_artifact='localization-before.json', after_artifact='localization-after.json', observed_context_and_loaded_icu_equal=True, source_database_exported=has_localization_export, database_lifetime_lease_proven=False, atomic_snapshot_proven=False, headless_bootstrap_qualified=False)
        require(runtime_after['semantic'] == runtime_before['semantic'], 'Resolved content or ordered gameplay selection changed across the save request')
        if script_files is not None:
            manifest['selected_gameplay_sources']['post_save_check'] = recheck_selected_sources(script_files, destination / 'selected-gameplay-sources', deadline=deadline, **{} if script_path_context is None else dict(script_path_context=script_path_context, script_path_cwd_reader=script_path_cwd_reader))
        after = capture_bundle(database_reader, destination / 'databases-after', expected_player_id=expected_player_id, expected_turn=expected_turn, limits=replace(limits, timeout_seconds=min(limits.timeout_seconds, remaining())))
        verify_bundle(destination / 'databases-after')
        require(_database_semantics(before) == _database_semantics(after), 'Active databases changed across the save request')
        observation_after = observe()
        artifact('observation-after.json', observation_after)
        require(observation_after['observation'] == observation_before['observation'], 'Player-observable state changed across save capture')
        if ui_availability:
            from civ6_host.runtime.native.native_ui_availability import capture_limits
            ui_after = ui_reader()
            artifact('ui-availability-after.json', ui_after)
            manifest['ui_availability'] = dict(before_artifact='ui-availability-before.json', after_artifact='ui-availability-after.json', observed_states_equal=ui_before['diagnostics']['ui_availability'] == ui_after['diagnostics']['ui_availability'], current_ui_only=True, headless_actions_qualified=False, same_bridge_session=True, limits=capture_limits(ui_after['diagnostics']['ui_availability']))
        if ui_local_state:
            ui_locals_after, after_identity = read_ui_locals()
            artifact('ui-local-state-after.json', ui_locals_after)
            require(ui_locals_before['nonce'] != ui_locals_after['nonce'], 'UI local state nonce reused')
            require(after_identity == ui_locals_identity, 'UI local closure or state changed across save')
            manifest['ui_local_state'] = dict(before_artifact='ui-local-state-before.json', after_artifact='ui-local-state-after.json', process_identity=checked['process']['identity'], observed_closures_and_states_equal=True, source_runtime_correspondence_qualified=False, direct_tuner_pid_attribution=False, headless_actions_qualified=False, actor_input=False, provenance='Sole exact process and unchanged modules around direct named Tuner contexts; no OS attribution of Tuner replies')
        save_copy = destination / 'save-capture'
        save_copy.mkdir()
        extracted = backend.capture_save(paths['save'], save_copy)
        require(extracted.get('sha256') == state['sha256'] and extracted.get('bytes') == state['bytes'] and (extracted.get('original_rehashed_unchanged') is True), 'Extracted save differs from receipt')
        manifest['save'] = dict(source=state, extraction907=extracted, absent_before_request=True, request_nonce=ack['request_id'], new_load_or_reset_qualified=False)
        for role, source in paths['exports'].items():
            original = _file(source, deadline)
            target = destination / ('export-' + role + '.sqlite')
            legacy._copy_checked(source, target, original, deadline)
            match = compare_sqlite_export(destination / 'databases-after', target, connection=role)
            require(_file(source, deadline) == original, 'Export changed during copy/comparison')
            require(all((not _resolve_resource_path(_resolve_resource_path(Path(str(source) + suffix))).exists() for suffix in ('-wal', '-shm', '-journal'))), 'Export acquired a journal during capture')
            manifest['export_matches'][role] = dict(source=original, copy=_file(target, deadline), comparison=match)
        process_after = backend.snapshot_process(pid, deadline)
        require(process_after == checked['process'], 'PID, creation time, EXE/Core or modules changed')
        manifest['process_after'] = process_after
        manifest['inventory_after'] = _sole_process(backend, process_after['identity'])
        log_after = _log_witness(observer, pid, paths['log'], process_after['identity'], remaining())
        require(log_after['requested_roles'] == checked['bridge_log_handle']['requested_roles'], 'Bridge log file object changed')
        manifest['log_handle_after'] = log_after
        require(_bridge_pins(paths['installed_mod'], deadline) == checked['installed_bridge'], 'Installed bridge changed during capture')
        require(_tool_pins(deadline) == checked['tool_source_pins'], 'Capture source changed during capture')
        if response is not None:
            require(_response_file_provenance(response['installation'], checked['process'], deadline, predecessor=response_file_predecessor) == response, 'Response writer provenance changed during capture')
        require(_file(paths['save'], deadline, legacy.MAX_SAVE_BYTES) == state, 'New save changed after extraction')
        require(client.session == manifest['bridge_session'], 'Bridge session changed during capture')
        if script_files is not None:
            manifest['selected_gameplay_sources']['final_check'] = recheck_selected_sources(script_files, destination / 'selected-gameplay-sources', deadline=deadline, **{} if script_path_context is None else dict(script_path_context=script_path_context, script_path_cwd_reader=script_path_cwd_reader))
        if localization_state:
            for side, report in (('before', localization_before), ('after', localization_after)):
                require(_localization_semantics(report, checked['process'], destination / ('localization-' + side), deadline) == localization_identity, 'Retained Localization capture changed')
                if has_localization_export:
                    _localization_export_reference(dict(reference=manifest['localization_exports'][side]), checked['process'], report, destination / ('localization-export-' + side), deadline)
        remaining()
        manifest['status'] = 'correlated_capture_unqualified'
        manifest['active_database_witness'] = dict(connections=['gameplay', 'configuration'], main_only=True, repeated_reads_per_side=2, equal_before_after_new_save=True, before_manifest=_file(destination / 'databases-before/manifest.json', deadline), after_manifest=_file(destination / 'databases-after/manifest.json', deadline))
        manifest['runtime_selections'] = dict(before_artifact='runtime-selections-before.json', after_artifact='runtime-selections-after.json', same_pid_exe_core=True, same_manager_context_and_ordered_lists=True, selected_paths=runtime_before['semantic']['selected_paths'], consumer_core_matches_base_proof=runtime_before['gameplay_selection994']['consumer_core_matches_base_proof'], content_application_success_proven=False, gameplay_execution_proven=False, scope='Observed manager content vectors and ordered gameplay path records; no calls into the loader')
        absence = runtime_before['gameplay_active_list']
        manifest['runtime_selections']['gameplay_active_list'] = dict(status=absence['status'] if absence else 'unsupported_gamecore', selected_and_active_empty=absence['selected_and_active_empty'] if absence else None, observed_on_both_sides=absence is not None, load_completion_proven=False, historical_execution_proven=False, scope='Base current selection and retained active-list absence; no script execution history or load certificate')
        manifest['unknown'] = ['Applied catalogue/content and actual gameplay-script activation', 'Selected script disk bytes do not prove historical in-memory bytes or included dependencies', *(['Localization active connection'] if not has_localization_export else []), 'GameCore replay/load of this newly created save', 'Full game state stability and a transactional save/database association', 'Direct OS attribution of each bridge log write to PID; handle plus sole game instance is a correlation']
        manifest['scope'] = 'One identified game instance held the bridge log file; one nonce session read both active main databases around a newly requested save. Manager content and gameplay path selections were read at that PID before/after. No DebugGameplay-open-file requirement; selections are not execution witnesses.'
        return manifest
    except Exception as exc:
        manifest['status'] = 'capture_refused'
        manifest['error'] = type(exc).__name__ + ': ' + str(exc)[:2048]
        raise
    finally:
        close_failure = None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                close_failure = exc
                manifest['status'] = 'capture_refused'
                manifest['close_error'] = type(exc).__name__ + ': ' + str(exc)[:2048]
        manifest['elapsed_seconds'] = time.monotonic() - started
        manifest['bounds'] = dict(overall_seconds=timeout_seconds, database_limits=limits.__dict__, timeout_scope='Cooperative API and protocol wait bounds, not cancellation of in-flight engine SQL')
        _write(destination / 'manifest.json', manifest)
        if close_failure is not None:
            raise RuntimeError('Capture could not close the bridge transport; see retained manifest') from close_failure

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'capture'))
    parser.add_argument('--pid', required=True, type=int)
    for option in ('inbox', 'log', 'save-directory', 'output'):
        parser.add_argument('--' + option, required=True, type=Path)
    parser.add_argument('--name', required=True, help='New Civ6RLLab_... save name without extension')
    parser.add_argument('--export', action='append', default=[], metavar='CONNECTION=PATH')
    parser.add_argument('--expected-player-id', type=int)
    parser.add_argument('--expected-turn', type=int)
    parser.add_argument('--ui-availability', action='store_true', help='Also read current UI controls; does not qualify headless availability')
    parser.add_argument('--ui-local-state', action='store_true', help='Read production/citizen UI closure locals directly; refuse missing debug APIs, no headless qualification')
    parser.add_argument('--script-root', action='append', default=[], type=Path, help='Approved installed game/mod root for copying exactly selected absolute Lua files')
    parser.add_argument('--script-path-context', type=json.loads, help='Explicit JSON {witness:{path,bytes,sha256},process:{pid,creation_filetime,image_path}}; no path search')
    parser.add_argument('--localization-state', action='store_true', help='Copy actual loaded ICU and language settings; active Localization database remains separate')
    parser.add_argument('--localization-export-ui-context', help='Explicit official UI context for native Localization export; also captures runtime ICU/settings')
    parser.add_argument('--localization-query-installation', type=Path, help='Retained installed read-only provider receipt; no Tuner call or installation')
    parser.add_argument('--localization-cache', type=Path, help='Candidate official cache; accepted only after complete active-table equality')
    parser.add_argument('--response-file-installation', type=Path, help='Explicit retained writer installation for private-file responses; no installation or fallback')
    parser.add_argument('--response-file-predecessor', type=Path, help='Explicit authenticated closed response prefix; no command replay or automatic fallback')
    parser.add_argument('--timeout-seconds', type=float, default=MAX_SECONDS, help='Explicit bounded capture budget; larger budgets require logical export')
    parser.add_argument('--tuner-port', type=int, default=4318, help='Explicit FireTuner TCP port (default: 4318); capture only, no port probing')
    parser.add_argument('--executable-sha256', choices=(EXE_SHA, CURRENT_EXE_SHA), default=EXE_SHA)
    args = parser.parse_args(argv)
    try:
        require(1 <= args.tuner_port <= 65535, 'Tuner port must be between 1 and 65535')
        exports = {}
        for item in args.export:
            role, path = item.split('=', 1)
            require(role in ('gameplay', 'configuration') and role not in exports and path, 'Invalid export role/path')
            exports[role] = _resolve_resource_path(Path(path))
        common = dict(pid=args.pid, inbox=args.inbox, log=args.log, save_directory=args.save_directory, name=args.name, output=args.output, exports=exports, script_roots=args.script_root, response_file_installation=args.response_file_installation, response_file_predecessor=args.response_file_predecessor, script_path_context=args.script_path_context)
        if args.executable_sha256 != EXE_SHA:
            common['backend'] = OfficialBackend(executable_sha256=args.executable_sha256)
        result = preflight(**common) if args.mode == 'preflight' else capture(**common, expected_player_id=args.expected_player_id, expected_turn=args.expected_turn, ui_availability=args.ui_availability, localization_state=args.localization_state, localization_export_ui_context=args.localization_export_ui_context, ui_local_state=args.ui_local_state, tuner_port=args.tuner_port, localization_query_installation=args.localization_query_installation, localization_cache=args.localization_cache, timeout_seconds=args.timeout_seconds)
    except Exception as exc:
        print(json.dumps(dict(status='refused', training_eligible=False, error=type(exc).__name__ + ': ' + str(exc)), ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())

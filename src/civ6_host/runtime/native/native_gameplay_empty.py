"""Read the Base GameplayScripts active-list absence without calling game code.

An empty current selection plus an empty retained list is an absence witness,
not a history of successful Lua execution. Save/database/load-generation joins
belong to the enclosing official capture. Nonempty and unsupported engines stay
explicitly unqualified. No records, Lua values, or player observations are read.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
import hashlib
import json
import struct
import time
from civ6_host.runtime.native.native_resolved_content import ROOT
from civ6_host.runtime.native.native_resolved_content import EXE_SHA
from civ6_host.runtime.native.native_resolved_content import MAX_USER_ADDRESS
from civ6_host.runtime.native.native_resolved_content import ContentSnapshotError
from civ6_host.runtime.native.native_gameplay_selection994 import BASE_CORE_SHA256
from civ6_host.runtime.native.native_gameplay_selection994 import MAX_CAPTURE_SECONDS
from civ6_host.runtime.native.native_gameplay_selection994 import _Deadline
from civ6_host.runtime.native.native_gameplay_selection994 import _file_digest
from civ6_host.runtime.native.native_gameplay_selection994 import capture_process as capture_selection_process
from civ6_host.runtime.gameplay_active_profiles import SUPPORTED_CORES as _active_supported
from civ6_host.runtime.gameplay_active_profiles import expansion_profile as _active_profile
from civ6_host.runtime.gameplay_active_profiles import source_digest as _active_source_sha
from civ6_host.runtime.gameplay_active_profiles import state_schema as _active_state_schema
SCHEMA = 'civ6rl.official_gameplay_empty.capture.v1'
STATE_SCHEMA = 'civ6rl.base_gameplay_active_list.memory_snapshot.v1'
SOURCE_SHA256 = '78bcfe0876a1bdc5062c5f53726e3e3b43d3548893079eca11f4f2e78897dbf2'
SOURCE_PATH = ROOT / 'work/official-bundle/scripts-empty-source.json'
MAX_READER_SECONDS = 2.0
MAX_READ_CALLS = 128
MAX_READ_BYTES = 16384
MAX_JOURNAL_RANGES = 64
MAX_ACTIVE_CONTEXTS = 8192

def source_profile(core_sha256=BASE_CORE_SHA256):
    if core_sha256 != BASE_CORE_SHA256:
        return _active_profile(core_sha256)
    raw = _resolve_resource_path(SOURCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ContentSnapshotError('Gameplay empty-list source changed')
    value = json.loads(raw)
    if value.get('schema') != 'civ6rl.gameplay_scripts_empty_source.v1' or value.get('status') != 'base_empty_active_list_and_load_consumption_source_verified' or value['image']['sha256'] != BASE_CORE_SHA256 or (not value.get('checks')) or (not all((check is True for check in value['checks'].values()))):
        raise ContentSnapshotError('Gameplay empty-list source is not qualified')
    return value

def read_gameplay_state(read_memory, core_base, *, core_sha256=BASE_CORE_SHA256, expected_inner=None, expected_auxiliary_vtable=None, timeout_seconds=MAX_READER_SECONDS, clock=time.monotonic):
    """Return only a stable bounded header; never infer success from a handle.

    Requires a current initialized Base Game and loading=false. This rejects a
    menu-only or in-progress load; it deliberately does not claim that observing
    the flags proves a particular load completed. The reader performs no calls.
    """
    deadline = _Deadline(timeout_seconds, clock, MAX_READER_SECONDS)
    if not callable(read_memory) or type(core_base) is not int or core_base % 65536 or (not 65536 <= core_base <= MAX_USER_ADDRESS - 16777216):
        raise ContentSnapshotError('Invalid Base image or memory reader')
    for pointer in (expected_inner, expected_auxiliary_vtable):
        if pointer is not None and (type(pointer) is not int or pointer % 8 or (not 65536 <= pointer <= MAX_USER_ADDRESS - 8192)):
            raise ContentSnapshotError('Invalid expected gameplay identity')
    source = source_profile(core_sha256)
    deadline.check()
    layout = source['layout']
    journal = []
    calls = 0
    consumed = 0

    def read(address, size, label, *, remember=True):
        nonlocal calls, consumed
        deadline.check()
        if type(address) is not int or type(size) is not int or size <= 0 or (not 65536 <= address <= MAX_USER_ADDRESS - size) or (calls >= MAX_READ_CALLS) or (consumed + size > MAX_READ_BYTES) or (remember and len(journal) >= MAX_JOURNAL_RANGES):
            raise ContentSnapshotError('Gameplay state read exceeds bounds: ' + label)
        result = read_memory(address, size)
        calls += 1
        consumed += size
        deadline.check()
        if type(result) is not bytes or len(result) != size:
            raise ContentSnapshotError('Incomplete gameplay state read: ' + label)
        if remember:
            journal.append((address, result, label))
        return result

    def pointer(address, label, *, nullable=False):
        value = struct.unpack('<Q', read(address, 8, label))[0]
        if nullable and value == 0:
            return value
        if not 65536 <= value <= MAX_USER_ADDRESS - 8192 or value % 8:
            raise ContentSnapshotError('Absent or invalid gameplay pointer: ' + label)
        return value
    preferred = int(source['image']['image_base'], 16)
    for function in source['functions'].values():
        for fragment in function.get('fragments', [function]):
            instructions = fragment['instructions']
            raw = bytes.fromhex(''.join((row['bytes'] for row in instructions)))
            if len(raw) != fragment['length'] or hashlib.sha256(raw).hexdigest() != fragment['raw_sha256']:
                raise ContentSnapshotError('Gameplay source fragment has inconsistent bytes')
            address = core_base + int(fragment['start_va'], 16) - preferred
            if read(address, len(raw), 'Base method') != raw:
                raise ContentSnapshotError('Loaded Base method differs from source')
    for offset, target in source['load_vtable_slots']['slots'].items():
        address = core_base + layout['inner_vtable_rva'] + int(offset, 16)
        if pointer(address, 'Load dispatch') != core_base + int(target, 16) - preferred:
            raise ContentSnapshotError('Loaded Base dispatch differs from source')
    inner = pointer(core_base + layout['inner_global_rva'], 'inner context')
    if expected_inner is not None and inner != expected_inner:
        raise ContentSnapshotError('Gameplay context differs from expected load owner')
    if pointer(inner, 'inner vtable') != core_base + layout['inner_vtable_rva']:
        raise ContentSnapshotError('Gameplay inner context type differs')
    context_initialized = read(inner + layout['context_initialized_offset'], 1, 'context initialized')[0]
    loading = read(inner + layout['loading_offset'], 1, 'loading')[0]
    game = pointer(inner + layout['game_offset'], 'Game')
    if pointer(game, 'Game vtable') != core_base + layout['game_vtable_rva']:
        raise ContentSnapshotError('Gameplay Game type differs')
    game_initialized = read(game + layout['game_initialized_offset'], 1, 'Game initialized')[0]
    if (context_initialized, game_initialized, loading) != (1, 1, 0):
        raise ContentSnapshotError('Gameplay state is uninitialized or loading')
    auxiliary = pointer(core_base + layout['auxiliary_global_rva'], 'script service')
    auxiliary_vtable = pointer(auxiliary, 'script service vtable')
    if expected_auxiliary_vtable is not None and auxiliary_vtable != expected_auxiliary_vtable:
        raise ContentSnapshotError('Gameplay script service differs from official interface')
    manager = pointer(inner + layout['script_manager_offset'], 'script manager')
    storage = pointer(manager + layout['storage_offset'], 'record storage', nullable=True)
    header = read(manager + layout['active_count_offset'], 12, 'active list header')
    count, head, tail = struct.unpack('<III', header)
    sentinel = layout['sentinel']
    if count > MAX_ACTIVE_CONTEXTS:
        raise ContentSnapshotError('Active gameplay contexts exceed bounded profile')
    if count == 0:
        if (head, tail) != (sentinel, sentinel):
            raise ContentSnapshotError('Empty gameplay count has nonempty list links')
    elif storage == 0 or not (head < sentinel and tail < sentinel):
        raise ContentSnapshotError('Nonempty gameplay list has missing storage or links')
    for address, raw, label in reversed(journal):
        if read(address, len(raw), label, remember=False) != raw:
            raise ContentSnapshotError('Gameplay state changed during capture: ' + label)
    return dict(schema=_active_state_schema(core_sha256), source_sha256=_active_source_sha(core_sha256), core_sha256=core_sha256, core_base=hex(core_base), inner_address=hex(inner), game_address=hex(game), manager_address=hex(manager), auxiliary_address=hex(auxiliary), auxiliary_vtable=hex(auxiliary_vtable), storage_address=hex(storage), active_count=count, head_index=head, tail_index=tail, active_list_empty=count == 0, context_initialized=True, game_initialized=True, loading=False, observed_ranges_unchanged=True, atomic_snapshot_proven=False, load_completion_proven=False, execution_proven=False, training_eligible=False, read_only=True, player_observation=False, memory_read_calls=calls, memory_bytes_read=consumed, journal_ranges=len(journal))

def _selection_identity(value):
    """Ignore only the elapsed-budget metadata, never observed native fields."""
    return {key: item for key, item in value.items() if key not in ('bounds',)}

def capture_process(process, *, timeout_seconds=MAX_CAPTURE_SECONDS, clock=time.monotonic):
    """Capture selection and active-list headers using one VM_READ-only handle.

    The 994 wrapper verifies PID creation identity, module set and image hashes
    on both sides. Repeated Core headers additionally detect observed lifecycle
    changes. A caller watchdog is still required for blocked OS operations.
    """
    deadline = _Deadline(timeout_seconds, clock, MAX_CAPTURE_SECONDS)
    original_modules = process.modules()
    deadline.check()
    first = capture_selection_process(process, timeout_seconds=deadline.check(), clock=clock)
    state = None
    core = first['gamecore_module']
    supported = core['sha256'] in _active_supported
    expected_vtable = first['exe_module']['base'] + source_profile(core['sha256'] if supported else BASE_CORE_SHA256)['layout']['auxiliary_exe_vtable_rva']
    if supported:
        state = read_gameplay_state(process.read, core['base'], core_sha256=core['sha256'], expected_auxiliary_vtable=expected_vtable, timeout_seconds=min(MAX_READER_SECONDS, deadline.check()), clock=clock)
    second = capture_selection_process(process, timeout_seconds=deadline.check(), clock=clock)
    for key in ('process', 'exe_module', 'gamecore_module'):
        if first[key] != second[key]:
            raise ContentSnapshotError('Official gameplay capture identity changed: ' + key)
    if _selection_identity(first['snapshot']) != _selection_identity(second['snapshot']):
        raise ContentSnapshotError('Official gameplay selection changed around Core snapshot')
    if supported:
        final = read_gameplay_state(process.read, core['base'], core_sha256=core['sha256'], expected_inner=int(state['inner_address'], 16), expected_auxiliary_vtable=expected_vtable, timeout_seconds=min(MAX_READER_SECONDS, deadline.check()), clock=clock)
        if state != final:
            raise ContentSnapshotError('Official gameplay active list changed around selection')
    if process.identity() != first['process']:
        raise ContentSnapshotError('Official process changed after final active-list read')
    final_modules = process.modules()
    deadline.check()
    module_key = lambda m: (m['base'], m['name'], m['path'], m['bytes'])
    if sorted(original_modules, key=module_key) != sorted(final_modules, key=module_key) or first['exe_module'] not in final_modules or {k: v for k, v in core.items() if k != 'sha256'} not in final_modules:
        raise ContentSnapshotError('Official modules changed after final active-list read')
    if _file_digest(first['exe_module']['path'], deadline.check) != EXE_SHA or _file_digest(core['path'], deadline.check) != core['sha256']:
        raise ContentSnapshotError('Official module file changed after final active-list read')
    if process.identity() != first['process']:
        raise ContentSnapshotError('Official process changed after final module read')
    deadline.check()
    empty_selection = first['snapshot']['record_count'] == 0 and first['snapshot']['selected_paths'] == [] and (first['snapshot']['records'] == [])
    absent = empty_selection and state['active_list_empty'] if supported else None
    return dict(schema=SCHEMA, status='selected_and_active_empty_observed' if absent is True else 'nonempty_profile_unqualified' if supported else 'unsupported_gamecore', process=first['process'], exe_module=first['exe_module'], gamecore_module=core, selection=first, state=state, selected_and_active_empty=absent, source_sha256=_active_source_sha(core['sha256']), observations_repeated=True, atomic_snapshot_proven=False, execution_proven=False, load_completion_proven=False, save_database_script_bundle_qualified=False, training_eligible=False, strategic_training_ready=False, read_only_process_rights=1024 | 16, game_executable_launched=False, remote_code_executed=False, memory_written=False, scope='Current Base GameplayScripts selection and retained active-list absence only; no historical execution certificate' if not supported or core['sha256'] == BASE_CORE_SHA256 else 'Current hash-pinned GameplayScripts selection and retained active-list absence only; no historical execution certificate')

def stable_capture_identity(report):
    """Validate the report's joins and return stable observations only.

    This comparison projection does not certify loading or execution. It keeps
    all observed selection fields, roots, flags and headers; only duration/read
    accounting and duplicated negative claims are omitted.
    """
    core_module = report.get('gamecore_module') if type(report) is dict else None
    core_sha = core_module.get('sha256') if type(core_module) is dict else None
    required = {'schema', 'status', 'process', 'exe_module', 'gamecore_module', 'selection', 'state', 'selected_and_active_empty', 'source_sha256', 'observations_repeated', 'atomic_snapshot_proven', 'execution_proven', 'load_completion_proven', 'save_database_script_bundle_qualified', 'training_eligible', 'strategic_training_ready', 'read_only_process_rights', 'game_executable_launched', 'remote_code_executed', 'memory_written', 'scope'}
    if type(report) is not dict or set(report) != required or report['schema'] != SCHEMA or (report['source_sha256'] != _active_source_sha(core_sha)) or (report['observations_repeated'] is not True) or (type(report['read_only_process_rights']) is not int) or (report['read_only_process_rights'] != 1040) or any((report[k] is not False for k in ('atomic_snapshot_proven', 'execution_proven', 'load_completion_proven', 'save_database_script_bundle_qualified', 'training_eligible', 'strategic_training_ready', 'game_executable_launched', 'remote_code_executed', 'memory_written'))):
        raise ContentSnapshotError('Invalid gameplay empty capture contract')
    for name in ('process', 'exe_module', 'gamecore_module'):
        if type(report[name]) is not dict:
            raise ContentSnapshotError('Invalid gameplay empty capture identity')
    for name in ('exe_module', 'gamecore_module'):
        module = report[name]
        fields = {'name', 'path', 'base', 'bytes'} | ({'sha256'} if name == 'gamecore_module' else set())
        if set(module) != fields or type(module['base']) is not int or module['base'] % 65536 or (not 65536 <= module['base'] <= MAX_USER_ADDRESS - 16777216) or (type(module['bytes']) is not int) or (module['bytes'] <= 0) or (type(module['name']) is not str) or (not module['name']) or (type(module['path']) is not str) or (not module['path']):
            raise ContentSnapshotError('Invalid gameplay empty capture module')
    core_sha = report['gamecore_module']['sha256']
    if type(core_sha) is not str or len(core_sha) != 64 or any((c not in '0123456789abcdef' for c in core_sha)):
        raise ContentSnapshotError('Invalid gameplay empty capture image hash')
    selection = report['selection']
    if type(selection) is not dict or selection.get('schema') != 'civ6rl.official_gameplay_selection994.capture.v1' or any((selection.get(k) != report[k] for k in ('process', 'exe_module', 'gamecore_module'))) or (selection.get('execution_proven') is not False):
        raise ContentSnapshotError('Gameplay empty capture selection join differs')
    snapshot = selection.get('snapshot')
    if type(snapshot) is not dict or snapshot.get('schema') != 'civ6rl.gameplay_selection994.memory_snapshot.v1' or type(snapshot.get('record_count')) is not int or (not 0 <= snapshot['record_count'] <= 8192) or (type(snapshot.get('records')) is not list) or (len(snapshot['records']) != snapshot['record_count']) or (type(snapshot.get('selected_paths')) is not list):
        raise ContentSnapshotError('Invalid gameplay empty capture selection')
    paths = []
    for index, row in enumerate(snapshot['records']):
        if type(row) is not dict or set(row) != {'index', 'path_pointer', 'path', 'consumer_skips'} or type(row['index']) is not int or (row['index'] != index) or (not (row['path'] is None or type(row['path']) is str)) or (row['consumer_skips'] is not (row['path'] in (None, ''))):
            raise ContentSnapshotError('Invalid gameplay empty capture selection row')
        if not row['consumer_skips']:
            paths.append(row['path'])
    if paths != snapshot['selected_paths']:
        raise ContentSnapshotError('Gameplay empty capture ordered paths differ')
    state = report['state']
    supported = core_sha in _active_supported
    if supported:
        state_fields = {'schema', 'source_sha256', 'core_sha256', 'core_base', 'inner_address', 'game_address', 'manager_address', 'auxiliary_address', 'auxiliary_vtable', 'storage_address', 'active_count', 'head_index', 'tail_index', 'active_list_empty', 'context_initialized', 'game_initialized', 'loading', 'observed_ranges_unchanged', 'atomic_snapshot_proven', 'load_completion_proven', 'execution_proven', 'training_eligible', 'read_only', 'player_observation', 'memory_read_calls', 'memory_bytes_read', 'journal_ranges'}
        if type(state) is not dict or set(state) != state_fields or state.get('schema') != _active_state_schema(core_sha) or (state.get('source_sha256') != _active_source_sha(core_sha)) or (state.get('core_sha256') != core_sha) or (state.get('core_base') != hex(report['gamecore_module']['base'])) or (type(state.get('active_count')) is not int) or (not 0 <= state['active_count'] <= MAX_ACTIVE_CONTEXTS) or (state.get('active_list_empty') is not (state['active_count'] == 0)) or any((state.get(k) is not True for k in ('context_initialized', 'game_initialized', 'observed_ranges_unchanged', 'read_only'))) or any((state.get(k) is not False for k in ('loading', 'atomic_snapshot_proven', 'load_completion_proven', 'execution_proven', 'training_eligible', 'player_observation'))):
            raise ContentSnapshotError('Invalid Base gameplay empty capture state')
        for name in ('inner_address', 'game_address', 'manager_address', 'auxiliary_address', 'auxiliary_vtable', 'storage_address'):
            address = state[name]
            try:
                pointer_value = int(address, 16) if type(address) is str else -1
            except ValueError:
                pointer_value = -1
            if address != hex(pointer_value) or pointer_value % 8 or (not (name == 'storage_address' and pointer_value == 0 or 65536 <= pointer_value <= MAX_USER_ADDRESS - 8192)):
                raise ContentSnapshotError('Invalid Base gameplay empty capture pointer')
        layout = source_profile(core_sha)['layout']
        sentinel = layout['sentinel']
        if state['auxiliary_vtable'] != hex(report['exe_module']['base'] + layout['auxiliary_exe_vtable_rva']):
            raise ContentSnapshotError('Base gameplay empty capture auxiliary interface differs')
        for name in ('head_index', 'tail_index'):
            if type(state[name]) is not int or not 0 <= state[name] <= sentinel:
                raise ContentSnapshotError('Invalid Base gameplay empty capture list link')
        if state['active_count'] == 0 and (state['head_index'], state['tail_index']) != (sentinel, sentinel) or (state['active_count'] > 0 and (state['head_index'] == sentinel or state['tail_index'] == sentinel or state['storage_address'] == '0x0')):
            raise ContentSnapshotError('Base gameplay empty capture header is inconsistent')
        for name, maximum in (('memory_read_calls', MAX_READ_CALLS), ('memory_bytes_read', MAX_READ_BYTES), ('journal_ranges', MAX_JOURNAL_RANGES)):
            if type(state[name]) is not int or not 0 < state[name] <= maximum:
                raise ContentSnapshotError('Invalid Base gameplay empty capture read accounting')
        if state['memory_read_calls'] != state['journal_ranges'] * 2:
            raise ContentSnapshotError('Base gameplay empty capture repeat accounting differs')
        absent = snapshot['record_count'] == 0 and state['active_list_empty']
        status = 'selected_and_active_empty_observed' if absent else 'nonempty_profile_unqualified'
    else:
        if state is not None:
            raise ContentSnapshotError('Unsupported GameCore must retain unknown state')
        absent = None
        status = 'unsupported_gamecore'
    if report['selected_and_active_empty'] is not absent or report['status'] != status:
        raise ContentSnapshotError('Gameplay empty capture conclusion differs from observations')
    accounting = {'bounds', 'memory_bytes_read', 'memory_read_calls', 'journal_ranges'}
    return copy.deepcopy({'process': report['process'], 'exe_module': report['exe_module'], 'gamecore_module': report['gamecore_module'], 'source_sha256': _active_source_sha(core_sha), 'selection': {k: v for k, v in snapshot.items() if k not in accounting}, 'state': None if state is None else {k: v for k, v in state.items() if k not in accounting}, 'selected_and_active_empty': absent, 'status': status})

def capture(pid, *, timeout_seconds=MAX_CAPTURE_SECONDS, clock=time.monotonic):
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    with ReadOnlyProcess(pid) as process:
        return capture_process(process, timeout_seconds=timeout_seconds, clock=clock)

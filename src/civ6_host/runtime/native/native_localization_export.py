"""Explicit official UI-context export of the active Localization database.

The existing Tuner dispatcher executes one synchronous C Lua callback, transferred
through the official root Threads registry. This is an opt-in diagnostic capture,
not an injected thread, game launch, or a new initialization pipeline. The callback
borrows the dictionary under the same UI call scope as official Locale.Lookup.
It proves neither a counted lifetime lease nor an atomic save/database snapshot.
The SQLite backup is synchronous: a transport timeout does NOT cancel it. Never
retry an uncertain export automatically. No capture happens on import.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
import math
import re
import time
import uuid
from civ6_host.runtime.native import native_localization_capture as runtime
from civ6_host.runtime.native.native_resolved_content import ROOT
BUILD_PATH = ROOT / 'work/official-capture/localization-export-build02/build.json'
BUILD_SHA = '4a9374a5b896764aa143d02e65960eca27d9eb86d6af786265519384762b7bed'
READER_SHA = '9998cba445fc6a6e195190b59c84c22ce494f29ed2dad9d7245e42bebf4b12f4'
CURRENT_READER_SHA = '61b6cefcc2cbb100806097793f96df4d6342f8b91ebd0dd73e0710f22d9d6065'
SCHEMA = 'civ6rl.localization_export.v1'
NATIVE_SCHEMA = 'civ6rl.localization_native_export.v1'
MAX_DB_BYTES = 512 * 1024 * 1024
IDENTITY_FIELDS = ('locale', 'dictionary_flag', 'fallback_policy_sql_sha256', 'dictionary_address', 'connection_address', 'lookup_result_address', 'auxiliary_result_address', 'statement_address', 'icu_address', 'icu_bytes', 'icu_sha256', 'language_address', 'language_index', 'languages_begin', 'languages_end')
NATIVE_FIELDS = tuple((k for k in IDENTITY_FIELDS if k not in ('fallback_policy_sql_sha256', 'icu_sha256')))
SCOPED_BORROW = 'official_ui_locale_lookup_synchronous_callback'

class LocalizationExportError(ValueError):
    pass

def _require(ok, message):
    if not ok:
        raise LocalizationExportError(message)

def _sha(path):
    digest = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def reference(path):
    path = _resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True)
    return dict(path=str(path), sha256=_sha(path), bytes=_resolve_resource_path(path).stat().st_size)

def _file(ref, *, parent=None, limit=4 * 1024 * 1024):
    _require(type(ref) is dict and type(ref.get('path')) is str and re.fullmatch('[0-9a-f]{64}', str(ref.get('sha256', ''))) and (type(ref.get('bytes')) is int) and (0 < ref['bytes'] <= limit), 'Invalid bounded export file reference')
    path = _resolve_resource_path(Path(ref['path']))
    _require(path.is_absolute() and (not path.is_symlink()), 'Export file must be absolute and not a link')
    resolved = _resolve_resource_path(path).resolve(strict=True)
    _require(parent is None or resolved.is_relative_to(_resolve_resource_path(_resolve_resource_path(Path(parent))).resolve()), 'Export file escaped its folder')
    _require(_resolve_resource_path(resolved).is_file() and _resolve_resource_path(resolved).stat().st_size == ref['bytes'] and (_sha(resolved) == ref['sha256']), 'Export file bytes/hash changed')
    return resolved

def _json(ref, **kwargs):
    path = _file(ref, **kwargs)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'Duplicate JSON key in export evidence')
            result[key] = value
        return result
    return json.loads(_resolve_resource_path(path).read_text(encoding='utf8'), object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(LocalizationExportError('Nonfinite JSON')))

def verify_build():
    _require(_sha(BUILD_PATH) == BUILD_SHA, 'Localization native build changed')
    build = json.loads(_resolve_resource_path(BUILD_PATH).read_text(encoding='utf8'))
    _require(build.get('schema') == 'civ6rl.localization_export_build.v1' and build.get('returncode') == 0, 'Localization callback has no successful build')
    for item in build['sources']:
        _file(item, limit=4 * 1024 * 1024)
    _file(build['source_snapshot'])
    _file(build['dll'])
    _require(_sha(_resolve_resource_path(Path(_historical_module_file(runtime)))) in {READER_SHA, CURRENT_READER_SHA}, 'Frozen Localization reader changed')
    return build

def _process(identity):
    _require(type(identity) is dict and set(identity) == {'pid', 'creation_filetime', 'image_path'} and (type(identity['pid']) is int) and (0 < identity['pid'] < 2 ** 32) and (type(identity['creation_filetime']) is int) and (0 < identity['creation_filetime'] < 2 ** 64) and (type(identity['image_path']) is str), 'Invalid exact process identity')

def runtime_identity(report):
    """Validated settings projection shared with capture994 (no query counters)."""
    _require(type(report) is dict, 'Runtime Localization producer/source differs')
    executable = report.get('modules', {}).get('exe', {}).get('sha256')
    _require(executable in (runtime.EXE_SHA, runtime.CURRENT_EXE_SHA), 'Unsupported Localization runtime executable')
    current = executable == runtime.CURRENT_EXE_SHA
    profile = runtime.source_profile(executable)
    accepted_readers = {CURRENT_READER_SHA} if current else {READER_SHA, CURRENT_READER_SHA}
    _require(report.get('schema') == ('civ6rl.localization_capture.v2' if current else 'civ6rl.localization_capture.v1') and report.get('route_source_sha256') == runtime.ROUTE_SHA and (report.get('collector_source_sha256') in accepted_readers), 'Runtime Localization producer/source differs')
    if current:
        _require(report.get('current_shared_source_sha256') == runtime.CURRENT_SHARED_SHA and report.get('executable_sha256') == executable, 'Current Localization correspondence differs')
    _process(report.get('process'))
    _require(report.get('runtime_memory_copied') is True and report.get('process_identity_unchanged_before_after') is True and (report.get('module_set_unchanged_before_after') is True), 'Runtime Localization capture is not stable')
    for flag in ('native_export_allowed', 'database_lifetime_lease_proven', 'game_executable_launched', 'remote_code_executed', 'memory_written', 'save_database_script_bundle_qualified', 'strategic_training_ready'):
        _require(report.get(flag) is False, 'Read-only Localization capture overclaims ' + flag)
    _require(report.get('database') is None, 'Runtime-only capture cannot claim a database')
    state = report.get('snapshot', {})
    _require(state.get('schema') == ('civ6rl.localization_memory_snapshot.v2' if current else 'civ6rl.localization_memory_snapshot.v1') and state.get('route_source_sha256') == runtime.ROUTE_SHA and (state.get('observed_ranges_unchanged') is True), 'Unknown Localization snapshot')
    if current:
        _require(state.get('current_shared_source_sha256') == runtime.CURRENT_SHARED_SHA and state.get('executable_sha256') == executable, 'Current Localization snapshot correspondence differs')
    for flag in ('atomic_snapshot_proven', 'database_exported', 'database_lifetime_lease_proven', 'save_identity_bound', 'training_eligible'):
        _require(state.get(flag) is False, 'Runtime Localization snapshot overclaims ' + flag)
    _require(all((k in state for k in IDENTITY_FIELDS)), 'Incomplete runtime Localization identity')
    _require(type(state['locale']) is str and re.fullmatch('[A-Za-z][A-Za-z0-9_@.\\-]{0,62}', state['locale']) and (type(state['dictionary_flag']) is bool) and (state['locale'] == report.get('locale')) and (state['dictionary_flag'] is report.get('dictionary_flag')), 'Invalid locale/fallback identity')
    policy = 'strict' if state['dictionary_flag'] else 'priorities'
    _require(state.get('fallback_policy') == policy and state.get('fallback_policy_sql') == profile['lookup_sql'][policy]['text'] and (state['fallback_policy_sql_sha256'] == profile['lookup_sql'][policy]['sha256']), 'Localization fallback SQL differs')
    for field in ('dictionary_address', 'connection_address', 'lookup_result_address', 'auxiliary_result_address', 'statement_address', 'icu_address', 'language_address', 'languages_begin', 'languages_end'):
        text = state[field]
        _require(type(text) is str and re.fullmatch('0x[0-9a-f]+', text) and (65536 <= int(text, 16) < 2 ** 47) and (int(text, 16) % 8 == 0), 'Invalid runtime pointer: ' + field)
    _require(type(state['icu_bytes']) is int and 0 < state['icu_bytes'] <= runtime.MAX_ICU_BYTES and (type(state['language_index']) is int) and (0 <= state['language_index'] < 1024) and re.fullmatch('[0-9a-f]{64}', str(state['icu_sha256'])), 'Invalid runtime language/ICU size')
    begin, end = (int(state['languages_begin'], 16), int(state['languages_end'], 16))
    _require(end > begin and (end - begin) % 400 == 0 and ((end - begin) // 400 <= 1024) and (begin + state['language_index'] * 400 == int(state['language_address'], 16)) and (int(state['language_address'], 16) < end), 'Runtime language vector differs')
    modules = report.get('modules', {})
    _require(set(modules) == {'exe', 'localization', 'database', 'havok', 'gamecore'}, 'Runtime module set differs')
    for kind, module in modules.items():
        _require(type(module) is dict and type(module.get('base')) is int and (module['base'] >= 65536) and (type(module.get('bytes')) is int) and (module['bytes'] > 0) and (type(module.get('path')) is str) and (type(module.get('name')) is str) and re.fullmatch('[0-9a-f]{64}', str(module.get('sha256', ''))), 'Invalid runtime module')
        if kind != 'gamecore':
            pin = profile['images'][kind]
            _require(module['sha256'] == pin['sha256'] and _resolve_resource_path(_resolve_resource_path(Path(module['path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(pin['path']))).resolve(), 'Runtime module identity differs: ' + kind)
    _require(_resolve_resource_path(_resolve_resource_path(Path(report['process']['image_path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(modules['exe']['path']))).resolve(), 'Runtime EXE is not source process')
    return {k: state[k] for k in IDENTITY_FIELDS}

def _runtime_file(ref, folder):
    report = _json(ref, parent=folder)
    identity = runtime_identity(report)
    path = _file(report['icu_data'], parent=_resolve_resource_path(Path(ref['path'])).parent, limit=runtime.MAX_ICU_BYTES)
    _require(path.name == 'loaded-icu.dat' and report['icu_data']['sha256'] == identity['icu_sha256'] and (report['icu_data']['bytes'] == identity['icu_bytes']), 'Complete loaded ICU copy differs')
    return (report, identity)

def _lua_string(value):
    return '"' + ''.join((chr(b) if 32 <= b <= 126 and b not in (34, 92) else '\\%03d' % b for b in str(value).encode('utf8'))) + '"'

def _prepared_key(build):
    return 'Civ6RLLocalizationPrepared_' + build['dll']['sha256']

def transfer_commands(*, nonce, dll_path, output_path, process, player_id, turn):
    """Three one-shot chunks, in UI → root → same UI order; no retries."""
    _process(process)
    _require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce), 'Invalid export nonce')
    _require(type(player_id) is int and 0 <= player_id < 64 and (type(turn) is int) and (0 <= turn < 2 ** 31), 'Invalid expected player/turn')
    key = 'Civ6RLLocalization_' + nonce
    quoted = _lua_string(key)
    check = f'assert(Game and Game.GetLocalPlayer and Game.GetCurrentGameTurn, "Game unavailable"); assert(Game.GetLocalPlayer()=={player_id} and Game.GetCurrentGameTurn()=={turn}, "player/turn drift"); assert(Locale and type(Locale.Lookup)=="function", "official Locale unavailable"); '
    mark = check + 'local env=getfenv(1); ' + f"""assert(rawget(env,{quoted})==nil,"nonce already present"); rawset(env,{quoted},{{nonce={_lua_string(nonce)}}}); print({_lua_string('CIV6RL_LOC_MARK:' + nonce)})"""
    build = verify_build()
    _require(dll_path == build['dll']['path'], 'Callback path differs from frozen build')
    install = f"""assert(type(Threads)=="table", "root Threads unavailable"); local found=nil; local n=0; for thread,env in pairs(Threads) do if type(env)=="table" then local box=rawget(env,{quoted}); if type(box)=="table" and box.nonce=={_lua_string(nonce)} then n=n+1; found=env end end end; assert(n==1,"missing or ambiguous UI nonce"); local box=rawget(found,{quoted}); assert(box.callback==nil and found.Locale and type(found.Locale.Lookup)=="function", "UI context changed"); local prepared=rawget(getfenv(1),{_lua_string(_prepared_key(build))}); assert(type(prepared)=="table" and prepared.path=={_lua_string(dll_path)} and prepared.sha256=={_lua_string(build['dll']['sha256'])} and type(prepared.callback)=="function", "helper not prepared"); box.callback=prepared.callback; print({_lua_string('CIV6RL_LOC_READY:' + nonce)})"""
    invoke = check + 'local env=getfenv(1); ' + f"""local box=rawget(env,{quoted}); assert(type(box)=="table" and box.nonce=={_lua_string(nonce)} and type(box.callback)=="function", "callback unavailable"); local callback=box.callback; rawset(env,{quoted},nil); local result=callback({_lua_string(nonce)},{_lua_string(output_path)},{_lua_string(process['pid'])},{_lua_string(process['creation_filetime'])},Locale.Lookup); assert(type(result)=="string", "native export returned no receipt"); """ + check + f"print({_lua_string('CIV6RL_LOC_RESULT:' + nonce + ':')}..result)"
    return [mark, install, invoke]

def _helper_module(process, build):
    matches = [m for m in process.modules() if _resolve_resource_path(_resolve_resource_path(Path(m['path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(build['dll']['path']))).resolve()]
    _require(len(matches) == 1 and type(matches[0].get('base')) is int and (matches[0]['base'] >= 65536) and (type(matches[0].get('bytes')) is int) and (matches[0]['bytes'] > 0), 'Prepared helper module is absent or ambiguous')
    _file(build['dll'])
    return {**matches[0], 'sha256': build['dll']['sha256']}

def _prepare_runtime(tuner, process, *, ui_context, timeout_seconds=30):
    """Load/retain helper and warm its CNG hashing before frozen module inventory.

    The explicit preparation callback hashes files and checks process/root Lua
    identity only. It never calls a Database function or reads the dictionary.
    """
    _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and (0 < timeout_seconds <= 30), 'Invalid preparation deadline')
    _require(type(ui_context) is str and ui_context and (ui_context != 'Main State'), 'Explicit UI context required')
    build = verify_build()
    identity = process.identity()
    _process(identity)
    expected_exe = runtime.source_profile()['images']['exe']
    _require(_resolve_resource_path(_resolve_resource_path(Path(identity['image_path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(expected_exe['path']))).resolve() and _sha(identity['image_path']) == expected_exe['sha256'], 'Preparation requires the pinned official EXE')
    tuner.refresh_states()
    index, root_index = (tuner.state_index(ui_context), tuner.state_index('Main State'))
    _require(index != root_index, 'Preparation UI context is root')
    nonce = uuid.uuid4().hex
    key = _lua_string(_prepared_key(build))
    path, digest = (_lua_string(build['dll']['path']), _lua_string(build['dll']['sha256']))
    command = f"""assert(package and type(package.loadlib)=="function" and type(Threads)=="table", "root loader unavailable"); local env=getfenv(1); local prepared=rawget(env,{key}); if prepared==nil then local callback,err=package.loadlib({path},"civ6rl_localization_export"); assert(type(callback)=="function",tostring(err)); prepared={{path={path},sha256={digest},callback=callback}}; rawset(env,{key},prepared) end; assert(type(prepared)=="table" and prepared.path=={path} and prepared.sha256=={digest} and type(prepared.callback)=="function","prepared helper differs"); local warm,err=package.loadlib({path},"civ6rl_localization_prepare"); assert(type(warm)=="function",tostring(err)); local result=warm({_lua_string(nonce)},{_lua_string(identity['pid'])},{_lua_string(identity['creation_filetime'])}); assert(type(result)=="string","preparation returned no receipt"); print({_lua_string('CIV6RL_LOC_PREPARED:' + nonce + ':')}..result)"""
    lines = tuner.execute(command, context=root_index, timeout=timeout_seconds)
    prefix = f'CIV6RL_LOC_PREPARED:{nonce}:'
    _require(type(lines) is list and len(lines) == 1 and (type(lines[0]) is str) and lines[0].startswith(prefix), 'Helper preparation acknowledgement differs')
    receipt = json.loads(lines[0][len(prefix):])
    _require(receipt.get('schema') == 'civ6rl.localization_native_preparation.v1' and receipt.get('status') == 'ok' and (receipt.get('nonce') == nonce) and (type(receipt.get('pid')) is int) and (receipt['pid'] == identity['pid']) and (type(receipt.get('creation_filetime')) is int) and (receipt['creation_filetime'] == identity['creation_filetime']) and (type(receipt.get('thread_id')) is int) and (receipt['thread_id'] > 0), 'Native preparation status/process differs')
    for key in ('lua_cs_owned', 'root_state_verified', 'module_hashes_verified', 'crypto_hashing_completed'):
        _require(receipt.get(key) is True, 'Native preparation did not qualify ' + key)
    for key in ('database_function_called', 'export_callback_invoked', 'dictionary_read'):
        _require(receipt.get(key) is False, 'Native preparation overclaims ' + key)
    helper = _helper_module(process, build)
    _require(process.identity() == identity, 'Process changed during helper preparation')
    return dict(schema='civ6rl.localization_export_preparation.v1', process=identity, nonce=nonce, helper_module=helper, build=reference(BUILD_PATH), ui_context=dict(name=ui_context, index=index, root_index=root_index), command=command, lines=lines, native_receipt=receipt, helper_callback_invoked=True, preparation_callback_invoked=True, export_callback_invoked=False, database_exported=False, game_executable_launched=False, remote_thread_created=False)

def prepare_export_runtime(pid, *, ui_context, timeout_seconds=30, tuner_port=4318):
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    from civ6_host.runtime.native.tuner import TunerClient
    _require(type(tuner_port) is int and 1 <= tuner_port <= 65535, 'Invalid FireTuner port')
    with ReadOnlyProcess(pid) as process, TunerClient(port=tuner_port, timeout=timeout_seconds) as tuner:
        return _prepare_runtime(tuner, process, ui_context=ui_context, timeout_seconds=timeout_seconds)

def _receipt(receipt, process, nonce, identity):
    _require(type(receipt) is dict and receipt.get('schema') == NATIVE_SCHEMA and (receipt.get('status') == 'ok'), 'Native Localization export did not succeed')
    _require(receipt.get('nonce') == nonce and type(receipt.get('pid')) is int and (receipt['pid'] == process['pid']) and (type(receipt.get('creation_filetime')) is int) and (receipt['creation_filetime'] == process['creation_filetime']), 'Native export PID/creation/nonce differs')
    _require(receipt.get('official_lookup_rva') == '0x4ca5d0' and receipt.get('lua_cs_owned') is True and (type(receipt.get('thread_id')) is int) and (receipt['thread_id'] > 0) and re.fullmatch('0x[0-9a-f]+', str(receipt.get('lua_state', ''))), 'Native official callback scope absent')
    for flag in ('backup_returned_true', 'destination_released', 'sqlite_header_verified'):
        _require(receipt.get(flag) is True, 'Native export not complete: ' + flag)
    for flag in ('source_refcount_modified', 'atomic_snapshot_proven', 'database_lifetime_lease_proven'):
        _require(receipt.get(flag) is False, 'Native export overclaims ' + flag)
    before, after = (receipt.get('source_before', {}), receipt.get('source_after', {}))
    _require(before == after and set(before) == set(NATIVE_FIELDS) | {'sqlite_address'}, 'Native Localization source changed/incomplete')
    _require(all((type(before[k]) is type(identity[k]) and before[k] == identity[k] for k in NATIVE_FIELDS)), 'Native export differs from copied runtime identity')
    _require(re.fullmatch('0x[0-9a-f]+', str(before['sqlite_address'])) and 65536 <= int(before['sqlite_address'], 16) < 2 ** 47, 'Invalid native SQLite owner')
    _require(type(receipt.get('database_size_bytes')) is int and 100 <= receipt['database_size_bytes'] <= MAX_DB_BYTES and re.fullmatch('[0-9a-f]{64}', str(receipt.get('database_sha256', ''))) and (type(receipt.get('backup_milliseconds')) is int) and (receipt['backup_milliseconds'] >= 0), 'Invalid native database result')

def validate_export_manifest(ref, *, expected_process=None, expected_nonce=None):
    """Offline strict validation of retained producer evidence; never calls Lua.

    ``runtime_identity`` matches the frozen runtime reader's exact semantic keys.
    Database returns both ``bytes`` (capture994) and ``size_bytes`` (bootstrap).
    Caller still must join independent before/after exports to its save boundary.
    """
    build = verify_build()
    report = _json(ref)
    folder = _resolve_resource_path(_resolve_resource_path(Path(ref['path']))).resolve().parent
    _require(report.get('schema') == SCHEMA and report.get('status') == 'exported', 'No completed Localization export')
    _process(report.get('process'))
    _require(expected_process is None or report['process'] == expected_process, 'Export process differs')
    nonce = report.get('nonce')
    _require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce) and (expected_nonce is None or nonce == expected_nonce), 'Export nonce differs')
    _require(report.get('build') == reference(BUILD_PATH) and report.get('helper') == build['dll'] and (report.get('producer_source_sha256') == _sha(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_localization_export.py'))))), 'Export helper/producer identity differs')
    _require(report.get('borrowed_lifetime_scope') == SCOPED_BORROW and report.get('process_identity_unchanged') is True, 'Export callback identity not bound')
    for flag in ('atomic_snapshot_proven', 'database_lifetime_lease_proven', 'save_identity_bound', 'strategic_training_ready', 'transport_timeout_cancels_native_backup', 'game_executable_launched', 'remote_thread_created', 'source_refcount_modified', 'logical_table_equality_verified'):
        _require(report.get(flag) is False, 'Export overclaims ' + flag)
    before, identity = _runtime_file(report.get('runtime_before'), folder)
    after, after_identity = _runtime_file(report.get('runtime_after'), folder)
    _require(before['process'] == after['process'] == report['process'] and before['modules'] == after['modules'] and (identity == after_identity) and (report.get('runtime_identity') == identity), 'Runtime Localization changed across native export')
    _require(before['nonce'] == after['nonce'] == nonce, 'Runtime export nonces differ')
    receipt = report.get('native_receipt')
    _receipt(receipt, report['process'], nonce, identity)
    database = report.get('database')
    path = _file(database, parent=folder, limit=MAX_DB_BYTES)
    _require(path.name == 'localization.sqlite' and path.parent == folder and (database['sha256'] == receipt['database_sha256']) and (database['bytes'] == receipt['database_size_bytes']), 'Retained native database differs')
    with _resolve_resource_path(path).open('rb') as stream:
        _require(stream.read(16) == b'SQLite format 3\x00', 'Missing exported SQLite header')
    context = report.get('ui_context', {})
    _require(set(context) == {'name', 'index', 'root_index'} and type(context['name']) is str and (context['name'] != 'Main State') and (type(context['index']) is int) and (type(context['root_index']) is int) and (context['index'] != context['root_index']), 'Invalid exact UI context')
    commands = transfer_commands(nonce=nonce, dll_path=build['dll']['path'], output_path=str(path), process=report['process'], player_id=report.get('expected_player_id'), turn=report.get('expected_turn'))
    expected_lines = [[f'CIV6RL_LOC_MARK:{nonce}'], [f'CIV6RL_LOC_READY:{nonce}']]
    transcript = report.get('commands')
    _require(type(transcript) is list and len(transcript) == 3, 'Export command transcript incomplete')
    for i, (entry, command) in enumerate(zip(transcript, commands)):
        index = context['root_index'] if i == 1 else context['index']
        _require(set(entry) == {'index', 'code', 'lines'} and entry['index'] == index and (entry['code'] == command) and (type(entry['lines']) is list) and (len(entry['lines']) == 1), 'Export Lua transcript differs')
        if i < 2:
            _require(entry['lines'] == expected_lines[i], 'Export transfer acknowledgement differs')
        else:
            prefix = f'CIV6RL_LOC_RESULT:{nonce}:'
            _require(type(entry['lines'][0]) is str and entry['lines'][0].startswith(prefix), 'Native receipt prefix differs')
            _require(json.loads(entry['lines'][0][len(prefix):]) == receipt, 'Native receipt transcript differs')
    icu = after['icu_data']
    bootstrap = dict(locale=identity['locale'], dictionary_flag=identity['dictionary_flag'], icu_data=dict(path=icu['path'], sha256=icu['sha256']))
    _require(report.get('bootstrap') == bootstrap, 'Export bootstrap differs from actual runtime bytes')
    return dict(database={**database, 'size_bytes': database['bytes']}, bootstrap=bootstrap, runtime_identity=identity, manifest=report)

def export_localization(tuner, process, output_folder, *, ui_context, expected_player_id, expected_turn, expected_localization, timeout_seconds=30, nonce=None, clock=time.monotonic):
    """Capture from an existing process and connected Tuner; injectable for tests."""
    _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and (0 < timeout_seconds <= 30), 'Export timeout must be finite and at most 30 seconds')
    deadline = clock() + timeout_seconds

    def remaining():
        value = deadline - clock()
        _require(value > 0, 'Export deadline expired; native outcome may be unknown; do not retry')
        return min(value, 30)
    build = verify_build()
    _require(type(ui_context) is str and ui_context and (ui_context != 'Main State'), 'Explicit official UI context required')
    nonce = uuid.uuid4().hex if nonce is None else nonce
    identity = process.identity()
    _process(identity)
    _helper_module(process, build)
    expected = runtime_identity(expected_localization)
    _require(expected_localization['process'] == identity, 'Expected Localization belongs to another process')
    folder = _resolve_resource_path(Path(output_folder))
    _require(folder.is_absolute() and (not _resolve_resource_path(folder).exists()), 'Export output must be a fresh absolute folder')
    parent = _resolve_resource_path(folder.parent).resolve(strict=True)
    _require(parent.is_relative_to(_resolve_resource_path(ROOT / 'work').resolve()), 'Export output must remain inside project work/')
    folder = parent / folder.name
    destination = folder / 'localization.sqlite'
    _require(str(destination).isascii() and len(str(destination)) < 2048, 'Unsupported native destination path')
    states = tuner.refresh_states()
    index, root_index = (tuner.state_index(ui_context), tuner.state_index('Main State'))
    _require(index != root_index and states[index] == ui_context and (states[root_index] == 'Main State'), 'Tuner context identity differs')
    commands = transfer_commands(nonce=nonce, dll_path=build['dll']['path'], output_path=str(destination), process=identity, player_id=expected_player_id, turn=expected_turn)
    folder.mkdir()
    before = runtime.capture_process(process, folder / 'runtime-before', nonce=nonce, timeout_seconds=remaining(), clock=clock)
    _require(runtime_identity(before) == expected and before['modules'] == expected_localization['modules'], 'Localization changed before export dispatch')
    transcript = []
    from contextlib import nullcontext
    with getattr(tuner, '_lock', nullcontext()):
        for i, command in enumerate(commands):
            _require(process.identity() == identity, 'Process changed before export command')
            target = root_index if i == 1 else index
            lines = tuner.execute(command, context=target, timeout=remaining())
            entry = dict(index=target, code=command, lines=lines)
            transcript.append(entry)
            with _resolve_resource_path(folder / f'command-{i}.json').open('x', encoding='utf8') as stream:
                json.dump(entry, stream, indent=2)
            prefix = f'CIV6RL_LOC_MARK:{nonce}' if i == 0 else f'CIV6RL_LOC_READY:{nonce}'
            if i < 2:
                _require(lines == [prefix], 'UI transfer acknowledgement missing/ambiguous')
    prefix = f'CIV6RL_LOC_RESULT:{nonce}:'
    lines = transcript[-1]['lines']
    _require(type(lines) is list and len(lines) == 1 and (type(lines[0]) is str) and lines[0].startswith(prefix), 'Native export receipt missing/ambiguous')
    receipt = json.loads(lines[0][len(prefix):])
    _receipt(receipt, identity, nonce, expected)
    after = runtime.capture_process(process, folder / 'runtime-after', nonce=nonce, timeout_seconds=remaining(), clock=clock)
    _require(runtime_identity(after) == expected and after['modules'] == before['modules'] and (process.identity() == identity), 'Localization changed after export')
    database = reference(destination)
    _require(database['bytes'] == receipt['database_size_bytes'] and database['sha256'] == receipt['database_sha256'], 'Native export file changed before publication')
    bootstrap = dict(locale=expected['locale'], dictionary_flag=expected['dictionary_flag'], icu_data=dict(path=after['icu_data']['path'], sha256=after['icu_data']['sha256']))
    report = dict(schema=SCHEMA, status='exported', process=identity, nonce=nonce, ui_context=dict(name=ui_context, index=index, root_index=root_index), expected_player_id=expected_player_id, expected_turn=expected_turn, build=reference(BUILD_PATH), helper=build['dll'], producer_source_sha256=_sha(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_localization_export.py')))), runtime_before=reference(folder / 'runtime-before/localization-manifest.json'), runtime_after=reference(folder / 'runtime-after/localization-manifest.json'), runtime_identity=expected, native_receipt=receipt, commands=transcript, database=database, bootstrap=bootstrap, borrowed_lifetime_scope=SCOPED_BORROW, process_identity_unchanged=True, atomic_snapshot_proven=False, database_lifetime_lease_proven=False, save_identity_bound=False, strategic_training_ready=False, transport_timeout_cancels_native_backup=False, game_executable_launched=False, remote_thread_created=False, source_refcount_modified=False, logical_table_equality_verified=False)
    remaining()
    target = folder / 'localization-export.json'
    with _resolve_resource_path(target).open('x', encoding='utf8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    ref = reference(target)
    validate_export_manifest(ref, expected_process=identity, expected_nonce=nonce)
    return {**report, 'reference': ref}

def capture_export(pid, output_folder, *, ui_context, expected_player_id, expected_turn, expected_localization, timeout_seconds=30, tuner_port=4318):
    """Explicit PID wrapper. Never starts or finds a game process automatically."""
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    from civ6_host.runtime.native.tuner import TunerClient
    _require(type(tuner_port) is int and 1 <= tuner_port <= 65535, 'Invalid FireTuner port')
    with ReadOnlyProcess(pid) as process, TunerClient(port=tuner_port, timeout=timeout_seconds) as tuner:
        return export_localization(tuner, process, output_folder, ui_context=ui_context, expected_player_id=expected_player_id, expected_turn=expected_turn, expected_localization=expected_localization, timeout_seconds=timeout_seconds)

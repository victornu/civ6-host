"""Export active Localization rows into a private official schema template.

This is a logical export, not Database::Backup. The official connection stays
borrowed and its transaction is untouched. Importing or validating this module
never invokes a native callback. Repeated reads do not establish atomicity or
association with a save; the caller must retain its own save boundary.
"""
from civ6_host.runtime import localization_bulk_export as bulk_export
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import nullcontext
import json
import math
from pathlib import Path
import re
import shutil
import time
import uuid
from civ6_host.runtime.native import database_capture_bundle993 as tables
from civ6_host.runtime.native import native_localization_query as provider
from civ6_host.runtime.native.native_localization_export import ROOT
from civ6_host.runtime.native.native_localization_export import MAX_DB_BYTES
from civ6_host.runtime.native.native_localization_export import SCOPED_BORROW
from civ6_host.runtime.native.native_localization_export import LocalizationExportError
from civ6_host.runtime.native.native_localization_export import _file
from civ6_host.runtime.native.native_localization_export import _json
from civ6_host.runtime.native.native_localization_export import _lua_string
from civ6_host.runtime.native.native_localization_export import _process
from civ6_host.runtime.native.native_localization_export import _require
from civ6_host.runtime.native.native_localization_export import _runtime_file
from civ6_host.runtime.native.native_localization_export import _sha
from civ6_host.runtime.native.native_localization_export import _helper_module
from civ6_host.runtime.native.native_localization_export import reference
from civ6_host.runtime.native.native_localization_export import runtime
from civ6_host.runtime.native.native_localization_export import runtime_identity
SCHEMA = 'civ6rl.localization_logical_export.v1'
MATERIALIZED = 'verified_native_rows_into_private_template_v1'
BUILD_PATH = ROOT / 'work/official-capture/localization-query/build03/build.json'
BUILD_SHA = '6b5cacf3a4714bca8637bc092faa37ce00244a678da119830804b59fc45f21bd'
PROVIDER_SHA = '857c6c1ed49cfbad6a70e487e181280fdb98bbc32e7e59f4c2edd7f323477134'
CURRENT_PROVIDER_SHA = '580da00f3bbf5dc5688ef615fee39c35b9b6198d92ccc09d3e9863cd4ed1c5ca'
CURRENT_BUILD_PATH = ROOT / 'work/official-capture/current-image-adapter/query-build/build.json'
CURRENT_BUILD_SHA = '40fbfcbb181b97886336cf6bca5d340672d0c84e5b3209328e93dc0fe9bd4bf3'
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_SECONDS = 3600
SOURCE_PATHS = ('civ6rl/native_localization_logical_export.py', 'civ6rl/native_localization_query.py', 'civ6rl/native_localization_export.py', 'civ6rl/native_localization_capture.py', 'civ6rl/database_capture992.py', 'civ6rl/database_capture_bundle993.py', 'civ6rl/file_client.py', 'mod/UI/Civ6RLDatabaseCapture992.lua')
HISTORICAL_SOURCE_ARCHIVE = ROOT / 'work/response-file-integration/capture10-sources.zip'
HISTORICAL_SOURCE_ARCHIVE_SHA256 = '163d4ae915c6f770ea3cbafb31327bbe5497b1045d814d1347a3f67b6822d398'
HISTORICAL_SOURCE_ARCHIVE_FILES = {'civ6rl/native_localization_logical_export.py': ('6da105c067ae69bdc48da69b23ef8aa1d7b0714a1ccf572529cd3b933e5e2585', 25010), 'civ6rl/database_capture_bundle993.py': ('2a66e204ad95b9e54b90751a2e85e5bf8bcc55e291d7db68ae6a3a03af93b177', 35541)}
HISTORICAL_SOURCE_ARCHIVE_ROOT = ROOT / 'work/phase1-exercise-development/source-archive/historical-localization-producer-capture10'
FALSE_FLAGS = ('atomic_snapshot_proven', 'database_lifetime_lease_proven', 'save_identity_bound', 'training_eligible', 'strategic_training_ready', 'game_executable_launched', 'remote_thread_created', 'source_refcount_modified', 'source_transactions_modified', 'native_backup_called', 'transport_timeout_cancels_native_query', 'native_per_page_nonce_attested')

def _nonce(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{32}', value), 'Invalid logical export nonce')
    return value

def _boundary(player, turn):
    _require(type(player) is int and 0 <= player < 64 and (type(turn) is int) and (0 <= turn <= 1000000), 'Invalid logical export player/turn')

def _build(ref=None):
    path, digest = (BUILD_PATH, BUILD_SHA)
    if ref is not None:
        if _resolve_resource_path(_resolve_resource_path(Path(ref['path']))).resolve() == _resolve_resource_path(CURRENT_BUILD_PATH).resolve() and ref['sha256'] == CURRENT_BUILD_SHA:
            path, digest = (CURRENT_BUILD_PATH, CURRENT_BUILD_SHA)
        else:
            _require(ref == reference(BUILD_PATH), 'Unknown Localization query build reference')
    _require(_sha(path) == digest and _sha(_resolve_resource_path(Path(_historical_module_file(provider)))) in {PROVIDER_SHA, CURRENT_PROVIDER_SHA}, 'Unknown Localization query build or provider')
    build = provider.verify_build(path)
    if path == CURRENT_BUILD_PATH:
        _require(build.get('execution_profile') == provider.current_image_profile(), 'Current Localization query build profile differs')
    return build

def _module(record, build):
    _require(type(record) is dict and type(record.get('base')) is int and (65536 <= record['base'] < 2 ** 47) and (type(record.get('bytes')) is int) and (record['bytes'] > 0) and (record.get('sha256') == build['dll']['sha256']) and (record.get('path') == build['dll']['path']) and (record.get('name') == _resolve_resource_path(Path(build['dll']['path'])).name), 'Helper module identity differs')

def _installation_command(registration, installation):
    nonce = _nonce(installation.get('nonce'))
    marker = 'CIV6RL_QUERY_INSTALL_' + nonce
    body = provider.install_command(registration, player_id=installation.get('player_id'), turn=installation.get('turn'))
    return f"""Civ6RL_Inbox={{transport_version=1,op="idle"}}\nif Civ6RL_LocalizationQueryInstallNonce~={_lua_string(nonce)} then Civ6RL_LocalizationQueryInstallNonce={_lua_string(nonce)}; local ok,result=pcall(function() {body}; return "installed" end); print({_lua_string(marker + ' RESULT ')}..tostring(ok).." "..tostring(result)) end\n""".encode('ascii')

def _installation(ref):
    """Replay the exact menu registration and later UI installation receipts."""
    installed = _json(ref)
    folder = _resolve_resource_path(_resolve_resource_path(Path(ref['path']))).resolve().parent
    _require(installed.get('schema') == 'civ6rl.localization_query_installation.v1' and installed.get('status') == 'ui_provider_installed_and_first_query_verified', 'No verified UI Localization provider installation')
    process = installed.get('process')
    _process(process)
    _boundary(installed.get('player_id'), installed.get('turn'))
    nonce = _nonce(installed.get('nonce'))
    _require(installed.get('inbox_restored') is True and installed.get('game_actions_issued') == 0 and (type(installed.get('game_actions_issued')) is int) and (installed.get('atomic_snapshot_proven') is False) and (installed.get('training_eligible') is False), 'Installation claims or inbox receipt differ')
    registered = _json(installed.get('registration'))
    build = bulk_export.selected_build(registered.get('build'))
    if build is None:
        build = _build(registered.get('build'))
    _process(registered.get('process'))
    reg_nonce = _nonce(registered.get('nonce'))
    _require(registered.get('schema') == 'civ6rl.localization_query_registration.v1' and registered.get('status') == 'registered_at_menu' and (registered.get('training_eligible') is False) and (registered['process'] == process), 'Registration process/build differs')
    _file(registered['build'])
    event, command = provider.registration_command(build, process, reg_nonce)
    _require(registered.get('event') == event and registered.get('command') == command, 'Registration command differs')
    receipt = dict(schema='civ6rl.localization_query_preparation.v1', status='ok', nonce=reg_nonce, database_function_called=False, module_file_pins_retained=True)
    _require(registered.get('native_receipt') == receipt, 'Native preparation receipt differs')
    lines = registered.get('lines')
    prefix = 'CIV6RL_LOC_QUERY_PREPARED:' + reg_nonce + ':'
    _require(type(lines) is list and len(lines) == 1 and (type(lines[0]) is str) and lines[0].startswith(prefix), 'Registration acknowledgement differs')
    _require(json.loads(lines[0][len(prefix):]) == receipt, 'Registration receipt join differs')
    _module(registered.get('helper_module'), build)
    _module(installed.get('helper_module'), build)
    _require(registered['helper_module'] == installed['helper_module'], 'Helper changed after registration')
    command_path = _file(installed.get('command'), parent=folder)
    _require(_resolve_resource_path(command_path).read_bytes() == _installation_command(registered, installed), 'Installation command differs')
    marker = 'CIV6RL_QUERY_INSTALL_' + nonce + ' RESULT '
    lines = installed.get('lines')
    _require(type(lines) is list and len(lines) == 1 and (type(lines[0]) is str) and (lines[0] == 'Civ6RL: ' + marker + 'true installed'), 'Installation acknowledgement differs')
    before, identity = _runtime_file(installed.get('runtime_before'), folder)
    after, after_identity = _runtime_file(installed.get('runtime_after'), folder)
    _require(before['process'] == after['process'] == process and before['nonce'] == after['nonce'] == nonce and (before['modules'] == after['modules']) and (identity == after_identity == installed.get('runtime_identity')), 'Installation runtime join differs')
    return (installed, registered, build, after)

def _sources():
    return [reference(ROOT / name) for name in SOURCE_PATHS]

def producer_dependencies(source_pins):
    """Validate current or one archived producer tuple and return closure pins.

    Historical report pins remain identity data. For the two files whose
    current consumer bytes changed, closure pins point to separately retained,
    hash-checked source copies and their pinned source archive.
    """
    current = _sources()
    if source_pins == current:
        return dict(version='current', producer_sources=source_pins, dependency_references=current)
    historical = [dict(pin) for pin in current]
    indexes = {name: index for index, name in enumerate(SOURCE_PATHS)}
    for name, (digest, size) in HISTORICAL_SOURCE_ARCHIVE_FILES.items():
        pin = historical[indexes[name]]
        pin['sha256'], pin['bytes'] = (digest, size)
    _require(source_pins == historical, 'Logical export source pins differ')
    archive = reference(HISTORICAL_SOURCE_ARCHIVE)
    _require(archive['sha256'] == HISTORICAL_SOURCE_ARCHIVE_SHA256, 'Historical producer source archive differs')
    dependencies = list(current)
    for name, (digest, size) in HISTORICAL_SOURCE_ARCHIVE_FILES.items():
        archived = reference(HISTORICAL_SOURCE_ARCHIVE_ROOT / name)
        _require(archived['sha256'] == digest and archived['bytes'] == size, 'Archived historical producer source differs')
        dependencies[indexes[name]] = archived
    dependencies.append(archive)
    return dict(version='capture09_10_archived_producer_v1', producer_sources=source_pins, dependency_references=dependencies)

def _candidate_shape(ref):
    _require(type(ref) is dict and set(ref) == {'path', 'sha256', 'bytes'} and (type(ref['path']) is str) and _resolve_resource_path(Path(ref['path'])).is_absolute() and (type(ref['bytes']) is int) and (100 <= ref['bytes'] <= MAX_DB_BYTES) and re.fullmatch('[0-9a-f]{64}', str(ref['sha256'])), 'Invalid cache copy receipt')

def _tables_manifest(ref, folder, player, turn, *, with_evidence=False):
    manifest = _json(ref, parent=folder, limit=MAX_MANIFEST_BYTES)
    selected = bulk_export.tables_manifest(manifest, ref, folder, player, turn, with_evidence=with_evidence)
    if selected is not None:
        return selected
    directory = _resolve_resource_path(Path(ref['path'])).parent
    _require(directory == folder / 'tables' and _resolve_resource_path(Path(ref['path'])).name == 'manifest.json', 'Tables bundle location differs')
    _require(manifest.get('connections') == ['localization'] and manifest.get('expected_player_id') == player and (manifest.get('expected_turn') == turn), 'Tables player/turn/connection join differs')
    limits = tables.Limits(**manifest['limits']).validate()
    _require(limits.page_size == 64 and limits.localization_row_pagination == 'rowid_seek_v1' and (limits.max_requests <= 20000) and (limits.max_bytes <= 512 * 1024 * 1024) and (limits.timeout_seconds <= MAX_SECONDS), 'Tables capture bounds differ')
    files = manifest.get('files')
    _require(type(files) is list and len(files) <= 40000, 'Tables file count exceeds bound')
    total = 0
    for pin in files:
        _require(type(pin) is dict and type(pin.get('path')) is str and re.fullmatch('[0-9]{6}\\.(request|response)\\.json', pin['path']), 'Invalid journal file reference')
        total += pin['bytes']
        _require(total <= limits.max_bytes, 'Tables journal exceeds byte bound')
    _require(type(manifest.get('passes')) is list and len(manifest['passes']) == 2, 'Two complete captures are required')
    for repeat in manifest['passes']:
        _require(type(repeat) is list and len(repeat) == 1 and (repeat[0].get('connection') == 'localization'), 'Localization pass differs')
        databases = repeat[0]['metadata']['databases']
        _require(len(databases) == 1 and databases[0]['name'] == 'main' and (databases[0]['seq'] == 0), 'Attached Localization content is not captured; refusing partial export')
    verified = tables._verify_bundle(directory)
    _require(verified.manifest == manifest, 'Verified tables journal differs from pinned manifest')
    return (directory, verified) if with_evidence else directory

def validate_export_manifest(ref, *, expected_process=None, expected_nonce=None, _with_verified_tables=False, _retained_sources=None):
    """Offline validation: replay capture and exact comparison, never call Lua."""
    report = _json(ref)
    folder = _resolve_resource_path(_resolve_resource_path(Path(ref['path']))).resolve().parent
    _require(report.get('schema') == SCHEMA and report.get('status') == 'exported', 'No completed logical Localization export')
    _process(report.get('process'))
    nonce = _nonce(report.get('nonce'))
    _boundary(report.get('expected_player_id'), report.get('expected_turn'))
    _require(type(report.get('player_id')) is int and type(report.get('turn')) is int and (report['player_id'] == report['expected_player_id']) and (report['turn'] == report['expected_turn']) and (report.get('ui_context') == dict(name='Civ6RL', transport='mounted_file_luaevents')), 'Logical export UI identity differs')
    _require(expected_process is None or expected_process == report['process'], 'Export process differs')
    _require(expected_nonce is None or expected_nonce == nonce, 'Export nonce differs')
    producer_dependencies(report.get('producer_sources'))
    for flag in FALSE_FLAGS:
        _require(report.get(flag) is False, 'Logical export overclaims ' + flag)
    _require(report.get('logical_table_equality_verified') is True and report.get('process_identity_unchanged') is True and (report.get('borrowed_lifetime_scope') == SCOPED_BORROW), 'Logical export contract differs')
    installed, registered, build, install_runtime = _installation(report.get('installation'))
    _require(report.get('registration') == installed['registration'] and report.get('build') == registered['build'] and (report.get('provider_nonce') == registered['nonce']) and (report.get('helper_module') == installed['helper_module']) and (report['process'] == installed['process']) and (report['expected_player_id'] == installed['player_id']) and (report['expected_turn'] == installed['turn']), 'Export installation join differs')
    _module(report['helper_module'], build)
    before, identity = _runtime_file(report.get('runtime_before'), folder)
    after, after_identity = _runtime_file(report.get('runtime_after'), folder)
    _require(before['process'] == after['process'] == report['process'] and before['nonce'] == after['nonce'] == nonce and (before['modules'] == after['modules'] == install_runtime['modules']) and (identity == after_identity == installed['runtime_identity'] == report.get('runtime_identity')), 'Logical export runtime join differs')
    collector = _file(report.get('installed_collector'))
    _require(collector.name == 'Civ6RLDatabaseCapture992.lua' and _sha(collector) == _sha(ROOT / SOURCE_PATHS[-1]), 'Installed collector differs')
    database = report.get('database')
    path = _file(database, parent=folder, limit=MAX_DB_BYTES)
    _require(path == folder / 'localization.sqlite', 'Private Localization copy location differs')
    with _resolve_resource_path(path).open('rb') as stream:
        _require(stream.read(16) == b'SQLite format 3\x00', 'Private cache is not SQLite')
    copy = report.get('cache_copy', {})
    _candidate_shape(copy.get('source_before'))
    _candidate_shape(copy.get('source_after'))
    _require(copy['source_before'] == copy['source_after'], 'Cache copy pins differ')
    production = report.get('database_production', 'verified_cache_copy_v1')
    if production == MATERIALIZED:
        template = report.get('template')
        template_path = _file(template, parent=folder, limit=MAX_DB_BYTES)
        _require(template_path == folder / 'localization-template.sqlite' and copy.get('destination') == template and (copy['source_before']['sha256'] == template['sha256']) and (copy['source_before']['bytes'] == template['bytes']), 'Private template copy pins differ')
        materialization = report.get('materialization', {})
        _require(materialization.get('schema') == 'civ6rl.database_materialization993.v1' and materialization.get('connection') == 'localization' and (materialization.get('database_production') == MATERIALIZED) and (materialization.get('template') == template) and (materialization.get('template_after') == template) and (materialization.get('template_unchanged') is True) and (materialization.get('database') == database) and (materialization.get('comparison') == report.get('comparison')) and (materialization.get('captured_schema_sql_executed') is False) and (materialization.get('trigger_or_view_execution_allowed') is False) and (materialization.get('atomic_snapshot') is False) and (materialization.get('save_process_scripts_associated') is False), 'Materialization receipt differs')
    elif production == 'verified_cache_copy_v1':
        _require(copy.get('destination') == database and copy['source_before']['sha256'] == database['sha256'] and (copy['source_before']['bytes'] == database['bytes']), 'Cache copy pins differ')
    else:
        raise LocalizationExportError('Unknown logical database production method')
    directory, verified_tables = _tables_manifest(report.get('tables_bundle'), folder, report['expected_player_id'], report['expected_turn'], with_evidence=True)
    comparison = tables.compare_sqlite_export(directory, path, connection='localization', _verified=verified_tables)
    _require(comparison == report.get('comparison'), 'Retained logical comparison differs from replay')
    bulk_export.validate_sources(report, verified_tables, build, retained_sources=_retained_sources)
    icu = after['icu_data']
    bootstrap = dict(locale=identity['locale'], dictionary_flag=identity['dictionary_flag'], icu_data=dict(path=icu['path'], sha256=icu['sha256']))
    _require(report.get('bootstrap') == bootstrap, 'Logical export bootstrap differs')
    result = dict(database={**database, 'size_bytes': database['bytes']}, bootstrap=bootstrap, runtime_identity=identity, manifest=report)
    if _with_verified_tables:
        result['_verified_tables'] = verified_tables
    return result

def dependency_references(ref):
    """Validated retained-file closure, excluding the mutable cache origin."""
    report = validate_export_manifest(ref)['manifest']
    installed = _json(report['installation'])
    registered = _json(report['registration'])
    build = _json(report['build'])
    bundle = _json(report['tables_bundle'], limit=MAX_MANIFEST_BYTES)
    refs = [ref, report['installation'], report['registration'], report['build'], report['database'], report['installed_collector'], report['tables_bundle'], installed['command']]
    if report.get('database_production') == MATERIALIZED:
        refs.append(report['template'])
    refs += bulk_export.extra_dependencies(report)
    refs += producer_dependencies(report['producer_sources'])['dependency_references']
    refs += build['sources'] + build['snapshots'] + [build['dll']]
    for runtime_ref in (report['runtime_before'], report['runtime_after'], installed['runtime_before'], installed['runtime_after']):
        refs += [runtime_ref, _json(runtime_ref)['icu_data']]
    directory = _resolve_resource_path(Path(report['tables_bundle']['path'])).parent
    refs += [{**pin, 'path': str(directory / pin['path'])} for pin in bundle['files']]
    _require(registered['build'] == report['build'], 'Dependency build join differs')
    unique = {}
    for pin in refs:
        previous = unique.setdefault(pin['path'], pin)
        _require(previous == pin, 'Conflicting dependency file pins')
    return list(unique.values())

def export_localization(client, process, folder, *, installation_ref, cache_path, expected_player_id, expected_turn, expected_localization, timeout_seconds):
    """Capture through an already installed provider; no install or game action."""
    _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds) and (0 < timeout_seconds <= MAX_SECONDS), 'Invalid logical export deadline')
    _boundary(expected_player_id, expected_turn)
    deadline = time.monotonic() + timeout_seconds

    def remaining(maximum=MAX_SECONDS):
        value = deadline - time.monotonic()
        _require(value > 0, 'Logical export deadline expired; no automatic retry')
        return min(value, maximum)
    installed, registered, build, install_runtime = _installation(installation_ref)
    process_identity = process.identity()
    _process(process_identity)
    expected = runtime_identity(expected_localization)
    _require(process_identity == installed['process'] == expected_localization['process'] and expected == installed['runtime_identity'] and (expected_localization['modules'] == install_runtime['modules']) and (expected_player_id == installed['player_id']) and (expected_turn == installed['turn']), 'Expected process/runtime/player/turn differs from installation')
    _require(_helper_module(process, build) == installed['helper_module'], 'Loaded helper differs')
    folder = _resolve_resource_path(Path(folder))
    _require(folder.is_absolute() and (not _resolve_resource_path(folder).exists()), 'Fresh absolute export folder required')
    parent = _resolve_resource_path(folder.parent).resolve(strict=True)
    _require(parent.is_relative_to(_resolve_resource_path(ROOT / 'work').resolve()), 'Export must stay inside project work')
    folder = parent / folder.name
    cache_path = _resolve_resource_path(_resolve_resource_path(Path(cache_path))).resolve(strict=True)
    _require(_resolve_resource_path(cache_path).is_file() and _resolve_resource_path(cache_path).stat().st_size <= MAX_DB_BYTES, 'Invalid cache candidate')
    for suffix in ('-wal', '-journal'):
        _require(not _resolve_resource_path(_resolve_resource_path(Path(str(cache_path) + suffix))).exists(), 'Cache has a live journal/WAL')
    collector = _resolve_resource_path(Path(client.inbox)).parent / 'Civ6RLDatabaseCapture992.lua'
    _require(_resolve_resource_path(collector).read_bytes() == _resolve_resource_path(ROOT / SOURCE_PATHS[-1]).read_bytes(), 'Installed collector differs')
    sources = _sources()
    nonce = uuid.uuid4().hex
    folder.mkdir()
    report = dict(schema=SCHEMA, status='incomplete', nonce=nonce, process=process_identity, expected_player_id=expected_player_id, expected_turn=expected_turn, player_id=expected_player_id, turn=expected_turn, ui_context=dict(name='Civ6RL', transport='mounted_file_luaevents'), installation=installation_ref, registration=installed['registration'], build=registered['build'], provider_nonce=registered['nonce'], helper_module=installed['helper_module'], producer_sources=sources, installed_collector=reference(collector), borrowed_lifetime_scope=SCOPED_BORROW, **{flag: False for flag in FALSE_FLAGS})
    target = folder / 'localization-export.json'
    bulk_export.declare_sources(client, build, report)
    try:
        before = runtime.capture_process(process, folder / 'runtime-before', nonce=nonce, timeout_seconds=remaining(30), executable_sha256=expected_localization['modules']['exe']['sha256'])
        report['runtime_before'] = reference(folder / 'runtime-before/localization-manifest.json')
        _require(runtime_identity(before) == expected and before['modules'] == expected_localization['modules'], 'Runtime changed before logical capture')
        candidate = reference(cache_path)
        _candidate_shape(candidate)
        destination = folder / 'localization.sqlite'
        template_path = folder / 'localization-template.sqlite'
        shutil.copyfile(cache_path, template_path)
        template = reference(template_path)
        source_after = reference(cache_path)
        _require(source_after == candidate and template['sha256'] == candidate['sha256'] and (template['bytes'] == candidate['bytes']), 'Cache changed during private copy')
        for suffix in ('-wal', '-journal'):
            _require(not _resolve_resource_path(_resolve_resource_path(Path(str(cache_path) + suffix))).exists(), 'Cache journal appeared during copy')
        report.update(database_production=MATERIALIZED, template=template, cache_copy=dict(source_before=candidate, source_after=source_after, destination=template))
        with getattr(client, '_lock', nullcontext()):

            def read(request, *, timeout):
                _require(process.identity() == process_identity, 'Process changed during logical capture')
                return client.read_active_database(request, timeout=min(timeout, remaining(15)))
            bulk_export.capture_tables(read, folder / 'tables', expected_player_id=expected_player_id, expected_turn=expected_turn, connections=('localization',), limits=tables.Limits(page_size=64, localization_row_pagination='rowid_seek_v1', timeout_seconds=remaining()), client=client, process=process, build=build, registered=registered, identity=expected, remaining=remaining)
        report['tables_bundle'] = reference(folder / 'tables/manifest.json')
        after = runtime.capture_process(process, folder / 'runtime-after', nonce=nonce, timeout_seconds=remaining(30), executable_sha256=expected_localization['modules']['exe']['sha256'])
        report['runtime_after'] = reference(folder / 'runtime-after/localization-manifest.json')
        _require(runtime_identity(after) == expected and before['modules'] == after['modules'] and (before['process'] == after['process'] == process_identity) and (process.identity() == process_identity), 'Runtime changed across logical capture')
        _require(_helper_module(process, build) == installed['helper_module'] and sources == _sources() and (reference(collector) == report['installed_collector']), 'Provider/collector changed across logical capture')
        bulk_export.check_live_sources(client, build, report)
        _tables_manifest(report['tables_bundle'], folder, expected_player_id, expected_turn)
        materialization = tables.materialize_sqlite_export(folder / 'tables', template_path, destination, connection='localization')
        _require(reference(template_path) == template, 'Private template changed during materialization')
        database = reference(destination)
        _require(materialization.get('template') == template and materialization.get('database') == database, 'Materialized file receipts differ')
        comparison = materialization['comparison']
        remaining()
        report.update(status='exported', database=database, materialization=materialization, comparison=comparison, runtime_identity=expected, process_identity_unchanged=True, logical_table_equality_verified=True, bootstrap=dict(locale=expected['locale'], dictionary_flag=expected['dictionary_flag'], icu_data=dict(path=after['icu_data']['path'], sha256=after['icu_data']['sha256'])))
    except Exception as exc:
        report.update(status='refused', error=type(exc).__name__ + ': ' + str(exc)[:2048])
        raise
    finally:
        with _resolve_resource_path(target).open('x', encoding='utf8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
    return {**report, 'reference': reference(target)}

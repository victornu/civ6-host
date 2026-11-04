"""Inspect explicitly selected XP2 inputs without opening a native session."""
import argparse
from hashlib import file_digest, sha256
import json
from pathlib import Path
import time

from .native import native_official_bundle as bundle
from .native import database_capture_bundle993 as tables
from .native import native_gameplay_empty
from .native.official_save import inspect_save
from .resource_resolution import resolve_path
from .workers import capture_phase1_bundle994 as capture
from . import xp2_bundle_inputs as xp2

SCHEMA = 'civ6-host.xp2-capture-selection.v1'
COMPLETE_SCHEMA = 'civ6-host.xp2-capture-input-review.v1'
MAX_ARTIFACT = 16 * 1024**2
MAX_IMAGE = 128 * 1024**2


def _image(path, expected):
    resolved = resolve_path(Path(path)).resolve(strict=True)
    if not resolved.is_file() or not 0 < resolved.stat().st_size <= MAX_IMAGE:
        raise ValueError('Captured executable or GameCore is unavailable or oversized')
    with resolved.open('rb') as stream:
        if file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('Installed executable or GameCore differs from the captured build')
    return {'sha256': expected, 'name': resolved.name}


def _component(raw):
    return {'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}


def _capture_file(folder, relative, pin, dependencies, *, maximum=MAX_ARTIFACT):
    path = resolve_path(bundle.ROOT / pin['path']).resolve(strict=True)
    if path != folder / relative:
        raise ValueError('Captured artifact belongs to another path or capture: ' + relative)
    return bundle._file(pin, dependencies, maximum=maximum)


def _database_event_sides(events, before, acknowledgement, after):
    sequence = -1
    positions = {}
    for index, event in enumerate(events):
        nonce, current = event['nonce'], event['sequence']
        if (type(nonce) is not str or not nonce or nonce in positions
                or type(current) is not int or current <= sequence):
            raise ValueError('Capture bridge events have duplicate nonces or inconsistent order')
        positions[nonce] = index
        sequence = current
    boundaries = []
    for kind, record in (('observation', before), ('save_snapshot', acknowledgement), ('observation', after)):
        index = positions[record['request_id']]
        if events[index] != dict(kind=kind, nonce=record['request_id'], sequence=record['sequence']):
            raise ValueError('Database capture boundary differs from its bridge receipt')
        boundaries.append(index)
    left, save, right = boundaries
    if not left < save < right:
        raise ValueError('Database capture must bracket the official Save')
    return ([e['nonce'] for e in events[left + 1:save] if e['kind'] == 'database_capture'],
            [e['nonce'] for e in events[save + 1:right] if e['kind'] == 'database_capture'])


def _final_databases(manifest, folder, boundary, event_sides, dependencies):
    before_semantics = None
    for side, events in zip(('before', 'after'), event_sides):
        relative = f'databases-{side}/manifest.json'
        pin = manifest['active_database_witness'][side + '_manifest']
        journal = json.loads(_capture_file(folder, relative, pin, dependencies))
        if (journal['schema'] != tables.SCHEMA or journal['connections'] != ['gameplay', 'configuration']
                or (journal['expected_player_id'], journal['expected_turn']) != boundary):
            raise ValueError('Active database journal differs from the selected capture boundary')
        nonces = [entry['nonce'] for entry in journal['journal']]
        expected = events[:len(nonces)] if side == 'before' else events[len(events) - len(nonces):]
        if not nonces or nonces != expected:
            raise ValueError('Active database journal differs from the bridge exchanges on the ' + side + ' side')
        verified = tables._verify_bundle((folder / relative).parent)
        if verified.manifest != journal:
            raise ValueError('Active database journal changed during replay')
        semantics = [tables._semantic(row) for row in journal['passes'][0]]
        if side == 'before':
            before_semantics = semantics
        elif semantics != before_semantics:
            raise ValueError('Active databases changed across the official Save')

    databases = {}
    for role in ('configuration', 'gameplay'):
        row = manifest['export_matches'][role]
        path = f'export-{role}.sqlite'
        raw = _capture_file(folder, path, row['copy'], dependencies, maximum=128 * 1024**2)
        if not raw.startswith(b'SQLite format 3\x00'):
            raise ValueError('Invalid captured database: ' + role)
        comparison = tables.compare_sqlite_export(verified.directory, folder / path,
                                                  connection=role, _verified=verified)
        if comparison != row['comparison']:
            raise ValueError('Recorded active database export comparison differs: ' + role)
        databases[role] = _component(raw)
    return databases


def _selected_scripts(manifest, process, folder, dependencies):
    witnesses = []
    for side in ('before', 'after'):
        name = 'runtime-selections-' + side + '.json'
        row = json.loads(_capture_file(folder, name, manifest['artifacts'][name], dependencies))
        content = row['content929']
        capture._join_native_report(content, process, 'civ6rl.official_resolved_content929.capture.v1')
        selection = capture._selection_semantics(row['gameplay_selection994'], process,
                                                 capture._content_semantics(content['snapshot'], process))
        active = row['gameplay_active_list']
        capture._join_native_report(active, process, native_gameplay_empty.SCHEMA)
        xp2.validate_selection_scope(row)
        if capture._selection_semantics(active['selection'], process, selection['content']) != selection:
            raise ValueError('Active gameplay scripts differ from the selected order')
        witnesses.append((selection, native_gameplay_empty.stable_capture_identity(active)))
    if witnesses[0] != witnesses[1]:
        raise ValueError('Resolved content or gameplay scripts changed across the official Save')
    xp2.validate_summary_scope(manifest['runtime_selections'])
    relative = 'selected-gameplay-sources/manifest.json'
    row = manifest['selected_gameplay_sources']
    scripts = json.loads(_capture_file(folder, relative, row['manifest'], dependencies, maximum=4 * 1024**2))
    xp2.validate_scripts(scripts, (folder / relative).parent, process, dependencies)
    return scripts, witnesses[0][0], active


def _prepared_bundle(reference, streams, maps, engine_path, observation,
                     databases, bootstrap, content_profile, dependencies):
    from .native.native_official_load import OfficialInputs

    state = observation['observation']
    fields = ('id', 'type', 'x', 'y', 'damage', 'moves')
    expected = dict(turn=observation['turn'], width=state['map']['width'], height=state['map']['height'],
                    player_id=observation['player_id'], gold=state['economy']['gold'],
                    city_count=len(state['cities']),
                    units=sorted(({key: unit[key] for key in fields} for unit in state['units']),
                                 key=lambda unit: unit['id']))
    fixture = dict(schema='civ6rl.native-fixture.v1', purpose='diagnostic selected official bundle',
                   eligible_for_training=False, databases=databases, localization_bootstrap=bootstrap,
                   official_bundle={'path': reference[0], 'sha256': reference[1]}, input_profile='xp2-lan')
    configuration, game = streams
    inputs = OfficialInputs(configuration, game, maps, xp2.XP2_LAN_PROFILE, official_bundle=reference)
    return bundle.PreparedBundle(reference, inputs, expected['turn'], engine_path, fixture,
                                 dependencies, expected, content_profile)


def _prepare_private_inputs(run, selected, scripts):
    from .capture_package import _copy_bytes, _copy_stream
    from .captured_session_profile import saved_geometry
    from .native.native_localization import ICU_SHA256
    from .native.native_host import validate_fixture
    from .xp1_saved_load import validate_private_bootstrap
    from .xp1_session_inputs import prepare_private_fixture, saved_load_pin

    bootstrap = selected.fixture['localization_bootstrap']
    if bootstrap['icu_data']['sha256'] != ICU_SHA256:
        raise ValueError('Unrecognized ICU data version')
    geometry = saved_geometry(selected)
    run.mkdir(exist_ok=False)
    pins = {}
    private_manifest, isolation = prepare_private_fixture(run, selected, pins)
    prepared = validate_fixture(private_manifest)
    if prepared['official_bundle'] != selected.fixture['official_bundle']:
        raise ValueError('Private fixture belongs to another capture')
    validate_private_bootstrap(prepared, bootstrap, private_root=private_manifest.parent)
    worker = isolation['workers'][0]
    private_streams = {}
    for role, name, data in (('configuration', 'configuration.bin', selected.inputs.configuration),
                             ('gamecore', 'gamecore.bin', selected.inputs.game)):
        identity = _component(data)
        target = private_manifest.parent / name
        _copy_bytes(data, target, identity['sha256'], identity['bytes'])
        saved_load_pin(pins, target, identity['sha256'])
        private_streams[role] = {'path': str(target), **identity}
    script_copies = []
    for source, row in scripts:
        target = private_manifest.parent / source.name
        _copy_stream(source, target, row['sha256'], row['bytes'])
        saved_load_pin(pins, target, row['sha256'])
        script_copies.append({**row, 'copy_path': str(target)})
    return {'fixture': str(private_manifest), 'fixture_sha256': worker['manifest_sha256'],
            'expected_readback': selected.expected_readback, 'saved_geometry': geometry,
            'database_copies': worker['databases'],
            'icu_copy': worker['icu_copy'], 'streams': private_streams, 'script_copies': script_copies,
            'copy_timings_seconds': isolation['timings_seconds']}


def _inspect(reference, manifest, localization_sources, private_run):
    process = manifest['preflight']['process']
    identity = capture._identity(process, process['identity']['pid'])
    if manifest['process_after'] != process:
        raise ValueError('Capture process identity changed across Save')
    core_sha = xp2.validate_process(process)
    executable = _image(identity['image_path'], process['exe_sha256'])
    core = _image(process['gamecore_module']['path'], core_sha)
    if resolve_path(Path(process['exe_module']['path'])).resolve() != resolve_path(Path(identity['image_path'])).resolve():
        raise ValueError('Capture executable module belongs to another image')

    capture_folder = resolve_path(bundle.ROOT / reference[0]).resolve(strict=True).parent
    dependencies = {str(capture_folder / Path(reference[0]).name): reference[1]}

    def artifact(name):
        return json.loads(_capture_file(capture_folder, name, manifest['artifacts'][name], dependencies))

    before, after = artifact('observation-before.json'), artifact('observation-after.json')
    turn = before['turn']
    if (any(type(value) is not int for value in (turn, after['turn'], before['player_id'], after['player_id']))
            or not 1 <= turn <= 100000 or before['player_id'] != 0 or after['player_id'] != 0
            or after['turn'] != turn or before['observation'] != after['observation']):
        raise ValueError('Capture does not have one unchanged player-zero boundary')
    dimensions = before['observation']['map']
    width, height = dimensions['width'], dimensions['height']
    if (any(type(value) is not int or not 1 <= value <= 512 for value in (width, height))
            or width * height > 16384):
        raise ValueError('Captured map dimensions are invalid or outside the host bound')

    saved = manifest['save']
    extraction = saved['extraction907']
    receipt = artifact('save-receipt.json')
    acknowledgement = receipt['acknowledgement']
    if (saved['absent_before_request'] is not True or saved['new_load_or_reset_qualified'] is not False
            or extraction['original_rehashed_unchanged'] is not True
            or acknowledgement['status'] != 'ok' or acknowledgement['reason'] != 'save_snapshot_requested'
            or acknowledgement['request_id'] != saved['request_nonce']
            or any(type(acknowledgement[key]) is not int for key in ('player_id', 'turn'))
            or acknowledgement['player_id'] != 0 or acknowledgement['turn'] != turn):
        raise ValueError('Official Save acknowledgement or extraction provenance differs')
    extraction_path = resolve_path(bundle.ROOT / extraction['manifest']).resolve(strict=True)
    if (not extraction_path.is_relative_to(capture_folder)
            or not extraction_path.is_file() or not 0 < extraction_path.stat().st_size <= 4 * 1024**2):
        raise ValueError('Save extraction manifest escaped the selected capture or its byte bound')
    report = json.loads(extraction_path.read_bytes())
    save_path = extraction_path.with_name('source.Civ6Save')
    saved_identity = {key: saved['source'][key] for key in ('bytes', 'sha256')}
    if any({key: witness[key] for key in saved_identity} != saved_identity
           for witness in (receipt, extraction, report)):
        raise ValueError('Save receipt, extraction and capture describe different bytes')
    raw = bundle._file(dict(path=str(save_path), **saved_identity), dependencies)
    _, sections = inspect_save(raw)
    rows = report['sections']
    games = [section for section in sections if section.kind == 'gamecore_stream_candidate']
    if (len(games) != 1 or len(sections) != len(rows)
            or any(dict(section.receipt(), extracted_file=row['extracted_file']) != row
                   for section, row in zip(sections, rows))):
        raise ValueError('GameCore stream differs from the retained Save extraction')
    configuration, maps = bundle._configuration(raw, manifest, 'LAN', expected_ruleset=xp2.RULESET)
    result = {
        'schema': SCHEMA,
        'capture': {'path': reference[0], 'sha256': reference[1]},
        'engine': {'executable': executable, 'gamecore': core},
        'boundary': {'ruleset': xp2.RULESET, 'mode': 'LAN', 'player_id': 0, 'turn': turn,
                     'width': width, 'height': height, 'map_values': dict(maps)},
        'official_save': saved_identity,
        'components': {'configuration': _component(configuration), 'gamecore': _component(games[0].payload)},
        'final_databases_and_scripts_validated': False,
        'native_session_admitted': False,
    }
    if localization_sources is not None:
        bundle._response_transport(manifest, dependencies)
        sides = _database_event_sides(manifest['bridge_events'], before, acknowledgement, after)
        scripts, selection, active = _selected_scripts(manifest, process, capture_folder, dependencies)
        databases = _final_databases(manifest, capture_folder, (0, turn), sides, dependencies)
        localization, bootstrap = bundle._localization_uncached(
            manifest, dependencies, _retained_sources=localization_sources)
        databases['localization'] = {'bytes': localization['size_bytes'], 'sha256': localization['sha256']}
        result.update(schema=COMPLETE_SCHEMA, final_databases_and_scripts_validated=True,
                      final_databases=databases,
                      ordered_gameplay_scripts=[{'selected_path': row['source_path'], **scripts['files'][row['copy']]}
                                                for row in scripts['records']],
                      localization_bootstrap={'locale': bootstrap['locale'],
                                              'icu_sha256': bootstrap['icu_data']['sha256']})
        if private_run is not None:
            final_databases = {
                role: {'path': str(capture_folder / f'export-{role}.sqlite'),
                       'sha256': entry['sha256'], 'size_bytes': entry['bytes']}
                for role, entry in databases.items() if role != 'localization'
            }
            final_databases['localization'] = localization
            profile = bundle.build_content_profile(
                process=process, databases=final_databases, localization_bootstrap=bootstrap,
                resolved_content=selection['content'], gameplay_selection=selection,
                active_state={'active_count': active['state']['active_count'],
                              'selected_and_active_empty': active['selected_and_active_empty']},
                script_manifest=scripts)
            engine_path = resolve_path(Path(process['gamecore_module']['path'])).resolve(strict=True)
            dependencies[str(engine_path)] = core_sha
            script_sources = [(capture_folder / 'selected-gameplay-sources' / row['copy'], descriptor)
                              for row, descriptor in zip(scripts['records'], result['ordered_gameplay_scripts'])]
            selected = _prepared_bundle(reference, (configuration, games[0].payload), maps, engine_path,
                                        before, final_databases, bootstrap, profile, dependencies)
            result['private_inputs'] = _prepare_private_inputs(private_run, selected, script_sources)
    return result


def inspect_capture(reference, *, localization_sources=None, private_run=None):
    """Review the save pair and, with pinned producer sources, the final inputs."""
    try:
        if private_run is not None:
            if localization_sources is None:
                raise ValueError('Private preparation requires the full captured Localization provenance')
            work = resolve_path(bundle.ROOT / 'work').resolve(strict=True)
            run = work / Path(private_run)
            parent = run.parent.resolve(strict=True)
            if (parent != run.parent or not parent.is_relative_to(work)
                    or run.exists() or run.is_symlink()):
                raise ValueError('Private preparation requires a new directory under private work')
            private_run = run
        normalized, manifest = bundle._manifest(reference)
        return _inspect(normalized, manifest, localization_sources, private_run)
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError('Missing or invalid official XP2 capture evidence') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, help='Capture manifest under the private work directory')
    parser.add_argument('--sha256', required=True, help='Expected digest of the capture manifest')
    parser.add_argument('--localization-sources', help='Explicit retained Localization producer manifest')
    parser.add_argument('--localization-sources-sha256', help='Expected digest of the producer manifest')
    parser.add_argument('--prepare-private', help='Fresh worker directory relative to private work')
    args = parser.parse_args()
    if (args.localization_sources is None) != (args.localization_sources_sha256 is None):
        parser.error('Provide both the Localization producer manifest and its digest')
    sources = None
    if args.localization_sources is not None:
        path = resolve_path(bundle.ROOT / args.localization_sources)
        sources = {'path': str(path), 'sha256': args.localization_sources_sha256, 'bytes': path.stat().st_size}
    print(json.dumps(inspect_capture({'path': args.capture, 'sha256': args.sha256},
                                     localization_sources=sources, private_run=args.prepare_private), indent=2))


if __name__ == '__main__':
    main()

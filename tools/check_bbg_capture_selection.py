"""Screen an exact official XP2 capture for the locally identified BBG 7.5.1 profile."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import time


_XP2 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
_BBG_WORKSHOP = '2865001760'
_BBG_CORE_SCRIPT = 'scripts/bbg_script.lua'
_BBG_WORKSHOP_ROOT = ('steamapps', 'workshop', 'content', '289070', _BBG_WORKSHOP)
# AddGameplayScripts from the pinned 7.5.1 manifest. The game's live selection
# determines which optional entries apply under the captured settings.
_BBG_GAMEPLAY_SCRIPTS = {
    _BBG_CORE_SCRIPT: (162086, '6538613569e4ab38b271104e800b54959192472a5ae3f2b3ea92ca3d4813cc6d'),
    'lua/bbg_expanded/thule.lua': (2922, '6d9ef0eb802c161098ec7c7bc30f02aaca142bb1539baeeed97d5357933c03fc'),
    'lua/bbg_expanded/te_kinich.lua': (5421, 'e7956430220ae150e577ba57a8fc58051053274775d5d6df00493c7ecc64edec'),
    'lua/bbg_expanded/al_hasan.lua': (7342, '3957d7a251f54006a9d66ccc3a4353a7fe0134c3f859dc8553d1f731ecac14fe'),
    'lua/bbg_expanded/olympia.lua': (7642, '5587eb8a0bc133eb2c6025cca21eb3b768f14687c07d9625e474b33ab130ff6a'),
    'lua/bbg_expanded/goth.lua': (3018, 'fb5cd0cd14e02dcc52a72ee11485d81a7c19feb49fb66e433ac30bcc1e4192ed'),
}


def _read_pinned(path, digest, limit):
    if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Expected an explicit SHA-256')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Capture artifact exceeds its bound or changed identity')
    return raw


def _read_capture_file(path, pin, limit):
    if (path.resolve(strict=True) != path or not path.is_file()
            or type(pin['bytes']) is not int or not 0 <= pin['bytes'] <= limit
            or path.stat().st_size != pin['bytes']):
        raise ValueError('Capture file differs from its recorded path or size')
    raw = _read_pinned(path, pin['sha256'], limit)
    if len(raw) != pin['bytes']:
        raise ValueError('Capture file size changed during read')
    return raw


def _verify_selection(root, document, process):
    from civ6_host.runtime.native.native_gameplay_empty import SCHEMA, stable_capture_identity
    from civ6_host.runtime.workers.capture_phase1_bundle994 import (
        _content_semantics, _join_native_report, _selection_semantics,
    )

    sides = []
    for side in ('before', 'after'):
        name = f'runtime-selections-{side}.json'
        artifact = json.loads(_read_capture_file(root / name, document['artifacts'][name], 16 * 1024**2))
        content = artifact['content929']
        from civ6_host.runtime.workers.capture_phase1_bundle994 import CURRENT_EXE_SHA
        _join_native_report(content, process,
            'civ6rl.official_resolved_content929.capture.v2' if process.get('exe_sha256') == CURRENT_EXE_SHA
            else 'civ6rl.official_resolved_content929.capture.v1')
        semantic = _content_semantics(content['snapshot'], process)
        selected = _selection_semantics(artifact['gameplay_selection994'], process, semantic)
        active = artifact['gameplay_active_list']
        _join_native_report(active, process, SCHEMA)
        if _selection_semantics(active['selection'], process, semantic) != selected:
            raise ValueError('Active scripts belong to another selection')
        sides.append((selected, stable_capture_identity(active)))
    if sides[0] != sides[1] or sides[0][0]['selected_paths'] != document['runtime_selections']['selected_paths']:
        raise ValueError('Runtime content or ordered script selection changed across the save')
    return sides[0][1]['state']['active_count']


def _verify_databases(root, document, acknowledgement):
    witness = document['active_database_witness']
    if (witness['connections'] != ['gameplay', 'configuration']
            or witness['equal_before_after_new_save'] is not True or witness['main_only'] is not True):
        raise ValueError('Capture lacks stable configuration and gameplay database witnesses')
    for side in ('before', 'after'):
        raw = _read_capture_file(root / f'databases-{side}' / 'manifest.json', witness[f'{side}_manifest'], 16 * 1024**2)
        database_witness = json.loads(raw)
        if (database_witness['expected_player_id'] != acknowledgement['player_id']
                or database_witness['expected_turn'] != acknowledgement['turn']
                or database_witness['connections'] != witness['connections']):
            raise ValueError('Database witness belongs to another save boundary')
    result = {}
    for role in ('configuration', 'gameplay'):
        export = document['export_matches'][role]
        copy, comparison = export['copy'], export['comparison']
        recorded = comparison['export']
        if (comparison['status'] != 'exact_main_content_match' or comparison['connection'] != role
                or comparison['capture_manifest_sha256'] != witness['after_manifest']['sha256']
                or (recorded['bytes'], recorded['sha256']) != (copy['bytes'], copy['sha256'])):
            raise ValueError('Final database copy is not linked to its capture witness')
        raw = _read_capture_file(root / f'export-{role}.sqlite', copy, 128 * 1024**2)
        if not raw.startswith(b'SQLite format 3\0'):
            raise ValueError('Invalid final SQLite copy')
        result[role] = copy['sha256']
    return result


def _verify_localization(root, document, capture_digest, retained_sources):
    from civ6_host.runtime import xp2_bundle_inputs
    from civ6_host.runtime.native.native_official_bundle import _localization_uncached
    from civ6_host.runtime.resource_resolution import resolve_path

    # The shared validator follows embedded paths. Require the Localization
    # and save witnesses to refer to the same capture tree screened above.
    references = document.get('localization_exports')
    if type(references) is not dict or set(references) != {'before', 'after'}:
        raise ValueError('Capture requires both active Localization exports')
    for side, reference in references.items():
        folder = root / f'localization-export-{side}'
        if resolve_path(Path(reference['path'])).resolve(strict=True).parent != folder:
            raise ValueError('Localization export belongs to another capture tree')
    for name in ('save-receipt.json', 'observation-before.json', 'observation-after.json',
                 'localization-before.json', 'localization-after.json'):
        embedded = resolve_path(Path(document['artifacts'][name]['path'])).resolve(strict=True)
        if embedded != root / name:
            raise ValueError('Localization witness belongs to another capture tree')

    if retained_sources is None and capture_digest == xp2_bundle_inputs.REFERENCE[1]:
        retained_sources = xp2_bundle_inputs.retained_localization_sources()
    database, _ = _localization_uncached(document, {}, _retained_sources=retained_sources)
    return database['sha256']


def _verify_script_origins(source, folder, document, process):
    from civ6_host.runtime.native.native_gameplay_source_capture import recheck_selected_sources

    resolution = source.get('path_resolution')
    if source['records'] and (
            type(resolution) is not dict or resolution != document.get('script_path_resolution')
            or resolution.get('context', {}).get('process') != process['identity']):
        raise ValueError('Selected gameplay source witness belongs to another capture process')
    recheck_selected_sources(source, folder, deadline=time.monotonic() + 15)


def _bbg_script_selection(records):
    matched, unmatched = [], []
    for row in records:
        parts = tuple(part.casefold() for part in PureWindowsPath(row['resolved_path']).parts)
        width = len(_BBG_WORKSHOP_ROOT)
        for index in range(len(parts) - width):
            if parts[index:index + width] == _BBG_WORKSHOP_ROOT:
                relative = '/'.join(parts[index + width:])
                break
        else:
            continue
        entry = dict(index=row['index'], package_path=relative)
        state = row['source_state']
        if _BBG_GAMEPLAY_SCRIPTS.get(relative) == (state['bytes'], state['sha256']):
            matched.append(entry)
        else:
            unmatched.append(entry)
    return matched, unmatched


def _saved_lan_map(path, digest):
    from civ6_host.runtime.native.native_official_bundle import parse_configuration
    from civ6_host.runtime.native.official_application_configuration import extract_application_configuration
    from civ6_host.runtime.native.official_save import MAX_SAVE_BYTES

    configuration, receipt = extract_application_configuration(_read_pinned(path, digest, MAX_SAVE_BYTES))
    if receipt['content_declaration']['declared_ruleset'] != 'RULESET_EXPANSION_2':
        raise ValueError('Map comparison requires a Gathering Storm save')
    _, map_values = parse_configuration(configuration, 'LAN')
    return dict(save_sha256=receipt['save_sha256'], configuration_sha256=receipt['sha256'],
                gamecore_sha256=receipt['gamecore_payload_sha256'], map_seed=dict(map_values)['RANDOM_SEED'])


def compare_saved_maps(candidate, candidate_sha256, reference, reference_sha256):
    """Exclude reused map seeds and GameCore streams before an official capture."""
    first = _saved_lan_map(candidate, candidate_sha256)
    second = _saved_lan_map(reference, reference_sha256)
    return dict(candidate=first, reference=second,
                map_seed_distinct=first['map_seed'] != second['map_seed'],
                gamecore_stream_distinct=first['gamecore_sha256'] != second['gamecore_sha256'],
                independent_official_generation_verified=False)


def inspect(manifest, sha256, *, expected_save_sha256=None, retained_localization_sources=None,
            different_map_from=None, execution_image=None):
    from civ6_host.runtime.session_configuration import inspect_official_save
    from civ6_host.runtime.xp2_bbg_inputs import declared_bbg

    manifest = manifest.resolve(strict=True)
    root = manifest.parent
    document = json.loads(_read_pinned(manifest, sha256, 4 * 1024**2))
    runtime = document['runtime_selections']
    process = document['process_after']
    if (document['schema'] != 'civ6rl.phase1_capture994.v1'
            or document['status'] != 'correlated_capture_unqualified'
            or document['preflight']['process'] != process
            or runtime['same_pid_exe_core'] is not True
            or runtime['same_manager_context_and_ordered_lists'] is not True):
        raise ValueError('Expected the stable official XP2 capture and selection')
    from civ6_host.runtime.xp2_bundle_inputs import validate_process
    core_sha = validate_process(process, **({'execution_image': execution_image}
                                           if execution_image is not None else {}))

    save = document['save']
    origin, extraction = save['source'], save['extraction907']
    save_sha256 = origin['sha256']
    if not re.fullmatch('[0-9a-f]{64}', save_sha256):
        raise ValueError('Invalid captured save SHA-256')
    if expected_save_sha256 is not None and expected_save_sha256 != save_sha256:
        raise ValueError('Capture does not contain the nominated exact save')
    receipt = json.loads(_read_capture_file(root / 'save-receipt.json', document['artifacts']['save-receipt.json'], 1024**2))
    ack = receipt['acknowledgement']
    if ((extraction['sha256'], extraction['bytes']) != (save_sha256, origin['bytes'])
            or (receipt['sha256'], receipt['bytes']) != (save_sha256, origin['bytes'])
            or ack['status'] != 'ok' or ack['reason'] != 'save_snapshot_requested'
            or ack['request_id'] != save['request_nonce']
            or save['absent_before_request'] is not True
            or extraction['original_rehashed_unchanged'] is not True):
        raise ValueError('Capture save, extraction and request receipt differ')
    boundaries = []
    for side in ('before', 'after'):
        name = f'observation-{side}.json'
        row = json.loads(_read_capture_file(root / name, document['artifacts'][name], 16 * 1024**2))
        if (row['player_id'], row['turn']) != (ack['player_id'], ack['turn']):
            raise ValueError('Captured observation belongs to another save boundary')
        boundaries.append(row['observation'])
    if boundaries[0] != boundaries[1]:
        raise ValueError('Captured observation changed across the save')
    save_path = root / 'save-capture' / save_sha256 / 'source.Civ6Save'
    if (save_path.resolve(strict=True) != save_path or not save_path.is_file()
            or save_path.stat().st_size != origin['bytes']):
        raise ValueError('Captured save copy differs from its recorded path or size')
    saved = inspect_official_save(dict(path=str(save_path), sha256=save_sha256))
    if saved['declared_content']['ruleset'] != 'RULESET_EXPANSION_2':
        raise ValueError('Captured XP2 save declares another ruleset')
    map_comparison = None
    if different_map_from is not None:
        reference, reference_sha256 = different_map_from
        map_comparison = compare_saved_maps(save_path, save_sha256, reference, reference_sha256)
        if not map_comparison['map_seed_distinct'] or not map_comparison['gamecore_stream_distinct']:
            raise ValueError('Candidate reuses the reference map seed or GameCore stream')
    declared = declared_bbg(saved['declared_mod_metadata'])
    active_count = _verify_selection(root, document, process)
    databases = _verify_databases(root, document, ack)

    source_ref = document['selected_gameplay_sources']['manifest']
    source_root = root / 'selected-gameplay-sources'
    source = json.loads(_read_capture_file(source_root / 'manifest.json', source_ref, 4 * 1024**2))
    if (source['schema'] != 'civ6rl.selected_gameplay_source_capture.v1'
            or source['status'] != 'selected_disk_sources_copied'
            or source['selected_paths'] != runtime['selected_paths']
            or source['disk_bytes_only'] is not True
            or len(source['records']) != len(source['selected_paths'])):
        raise ValueError('Selected gameplay paths do not agree')

    checked, ordered = set(), []
    total_bytes = 0
    for index, (row, path) in enumerate(zip(source['records'], source['selected_paths'])):
        if row['index'] != index or row['source_path'] != path:
            raise ValueError('Selected gameplay source order differs')
        digest = row['source_state']['sha256']
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid selected gameplay source digest')
        name = digest + '.lua'
        pin = dict(sha256=digest, bytes=row['source_state']['bytes'])
        if row['copy'] != name or source['files'][name] != pin:
            raise ValueError('Selected gameplay copy record differs')
        if name not in checked:
            if type(pin['bytes']) is not int or not 0 <= pin['bytes'] <= 4 * 1024**2:
                raise ValueError('Selected gameplay source exceeds its byte bound')
            total_bytes += pin['bytes']
            if total_bytes > 64 * 1024**2:
                raise ValueError('Selected gameplay source set exceeds its byte bound')
            _read_capture_file(source_root / name, pin, 4 * 1024**2)
            checked.add(name)
        ordered.append(dict(index=index, path=path, sha256=digest))
    if checked != set(source['files']) or total_bytes != source['total_unique_bytes']:
        raise ValueError('Gameplay source manifest contains unselected copies')
    _verify_script_origins(source, source_root, document, process)
    bbg_matches, bbg_unknown = _bbg_script_selection(source['records'])
    matched = [row['index'] for row in bbg_matches if row['package_path'] == _BBG_CORE_SCRIPT]
    exact_bbg = bool(len(matched) == 1 and not bbg_unknown and declared and declared['identity_matches']
                     and declared['exact_title_matches'])
    databases['localization'] = _verify_localization(
        root, document, sha256, retained_localization_sources)
    result = dict(schema='civ6-host.bbg-official-capture-selection.v4',
                capture_sha256=sha256, save_sha256=save_sha256,
                configuration_sha256=saved['configuration_sha256'], core_sha256=core_sha,
                final_database_copy_sha256=databases, verified_script_copies=len(checked),
                selected_gameplay_sources=ordered, active_gameplay_context_count=active_count,
                workshop_id=_BBG_WORKSHOP, saved_bbg=declared,
                expected_mod_version='70501', matched_selection_indices=matched,
                matched_bbg_gameplay_entries=bbg_matches, unmatched_bbg_gameplay_entries=bbg_unknown,
                exact_bbg_gameplay_source_selected=bool(matched),
                exact_bbg_gameplay_candidate=exact_bbg, localization_revalidated=True,
                includes_and_ui_scripts_verified=False,
                bbg_ui_context_verified=False, bbg_profile_qualified=False)
    if map_comparison is not None:
        result['map_seed_comparison'] = map_comparison
    if execution_image is not None:
        from civ6_host.runtime.execution_images import identity
        result['execution_image'] = identity(execution_image)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path, help='Official capture manifest or, with --save-only, the save')
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--expected-save-sha256', help='Require this exact captured save')
    parser.add_argument('--different-map-from', type=Path, help='Compare with this exact LAN reference save')
    parser.add_argument('--different-map-from-sha256', help='SHA-256 of the LAN reference save')
    parser.add_argument('--save-only', action='store_true', help='Check the two saves before capturing databases')
    parser.add_argument('--localization-sources', type=Path,
                        help='Retained producer manifest for the captured Localization export')
    parser.add_argument('--localization-sources-sha256', help='Exact retained producer manifest digest')
    parser.add_argument('--execution-image', help='Explicit installed execution-image profile')
    args = parser.parse_args()
    if (args.different_map_from is None) != (args.different_map_from_sha256 is None):
        parser.error('Supply the reference save and its digest together')
    different_map_from = ((args.different_map_from, args.different_map_from_sha256)
                          if args.different_map_from is not None else None)
    if (args.localization_sources is None) != (args.localization_sources_sha256 is None):
        parser.error('Supply the retained producer manifest and its digest together')
    if args.save_only:
        if different_map_from is None or args.localization_sources is not None or args.expected_save_sha256 is not None:
            parser.error('--save-only requires a reference save and accepts no manifest options')
        comparison = compare_saved_maps(args.capture, args.sha256, *different_map_from)
        print(json.dumps(comparison, indent=2))
        raise SystemExit(0 if comparison['map_seed_distinct'] and comparison['gamecore_stream_distinct'] else 2)
    retained = None
    if args.localization_sources is not None:
        path = args.localization_sources.absolute()
        raw = _read_pinned(path, args.localization_sources_sha256, 1024**2)
        retained = dict(path=str(path), sha256=args.localization_sources_sha256, bytes=len(raw))
    image = None
    if args.execution_image is not None:
        from civ6_host.runtime.execution_images import select, known_path
        image = select(args.execution_image, core_path=known_path(args.execution_image))
    result = inspect(args.capture, args.sha256, expected_save_sha256=args.expected_save_sha256,
                     retained_localization_sources=retained, different_map_from=different_map_from,
                     execution_image=image)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['exact_bbg_gameplay_candidate'] else 1)

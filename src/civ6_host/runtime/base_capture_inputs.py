"""Prepare the retained Base hotseat inputs for the installed Core."""

import json
from pathlib import Path

from .capture_admission import _check_localization, _files, _pin_original, _verify_content_profile
from .capture_package import SCHEMA as PACKAGE_SCHEMA
from .configuration_profiles import _copy, _source
from .execution_images import _BASE_PROFILE, base_capture_execution, from_identity, identity
from .native import native_official_bundle as original
from .native.native_official_load import HOTSEAT_FOUR_PROFILE, OfficialInputs
from .paths import resource_root
from .resource_resolution import resolve_path


REFERENCE = (
    'work/official-capture/hotseat4-20261027-file09/manifest.json',
    '35234a1ff8420992b27753acd443313b35f5074b84318c08008cec5f9adc3b3a',
)
PACKAGE = (
    'work/host-capture-package/capture09/manifest.json',
    'e9c6bb04ef477a8189e6d280a0be617f77f5f8aff11b31084b2cfbfc3043098b',
)
QUALIFICATION = (
    'work/host-capture-package/native-validation.json',
    '6bd28ad02119b0eb1c32e1fd99382737b8042b4c8e0df27c5cb64892ea17d2b8',
)
VALIDATOR_DIRECTORY = 'work/base-current-image/capture09-original-validators'


def read_bundle(reference, *, execution_image, input_profile):
    """Reauthenticate the previously qualified package and the new execution pair."""
    origin, capture = original._manifest(reference)
    if origin != REFERENCE or input_profile != 'hotseat-four':
        raise ValueError('Installed Base inputs require the exact retained hotseat capture')
    process = capture['preflight']['process']
    if capture['process_after'] != process:
        raise ValueError('Base capture producer changed across the save')
    engine, dependencies = base_capture_execution(execution_image, process)
    root = resource_root()
    manifest = _copy(_source(PACKAGE))
    qualification = _source(QUALIFICATION)
    package = root / PACKAGE[0]
    if (manifest['schema'] != PACKAGE_SCHEMA
            or manifest['origin'] != dict(path=origin[0], sha256=origin[1])
            or manifest['input_profile'] != input_profile
            or manifest['engine']['sha256'] != execution_image.reference_core_sha256
            or qualification['status'] != 'installed_backend_native_parity_verified'
            or qualification['prepared_capture']['sha256'] != PACKAGE[1]
            or not any(row['operation'] == 'reset' and row['public_observation_equal'] is True
                       for row in qualification['comparisons'])):
        raise ValueError('Installed Base package differs from its exact native qualification')
    for path, digest in (origin, PACKAGE, QUALIFICATION):
        dependencies[str(resolve_path(root / path))] = digest
    from .native.native_app_ownership import CURRENT_XP2_INVENTORY_PATH, CURRENT_XP2_INVENTORY_SHA256
    inventory = _source((CURRENT_XP2_INVENTORY_PATH, CURRENT_XP2_INVENTORY_SHA256))
    dependencies[str(resolve_path(root / CURRENT_XP2_INVENTORY_PATH))] = CURRENT_XP2_INVENTORY_SHA256
    for item in inventory['current_inventory']:
        if 'private_copy' in item:
            entry = item['private_copy']
            original._file(dict(path=str(root / entry['path']), sha256=entry['sha256'], bytes=entry['byte_length']),
                           dependencies, prefix_bytes=0)

    # The preserved reader sources are proof data. Current code checks the inputs.
    validators = manifest['validation_identity']['original_validator_sources']
    validator_root = resolve_path(root / VALIDATOR_DIRECTORY)
    for name in original._PREPARED_BUNDLE_VALIDATOR_PATHS:
        path = resolve_path(validator_root / name)
        original._file(dict(path=str(path), sha256=validators[name], bytes=path.stat().st_size),
                       dependencies, maximum=4 * 1024**2, prefix_bytes=0)

    folder = resolve_path(package).parent
    files = _files(manifest, folder)
    for role, row in files.items():
        if not Path(row['path']).is_relative_to(folder):
            raise ValueError('Prepared Base input escaped its package')
        # Materialize only the streams and copied origin manifest.
        as_bytes = role in ('configuration_stream', 'gamecore_stream', 'origin_manifest')
        raw = original._file(dict(path=row['path'], bytes=row['size_bytes'], sha256=row['sha256']),
                             dependencies, prefix_bytes=None if as_bytes else 0)
        if as_bytes:
            row['data'] = raw
    if files['origin_manifest']['data'] != resolve_path(root / origin[0]).read_bytes():
        raise ValueError('Prepared Base manifest differs from its retained capture')

    configuration, maps = original.parse_configuration(
        files['configuration_stream']['data'], HOTSEAT_FOUR_PROFILE.mode_name)
    if [list(item) for item in maps] != manifest['map_values']:
        raise ValueError('Prepared Base map settings differ')
    inputs = OfficialInputs(configuration, files['gamecore_stream']['data'], maps,
                            HOTSEAT_FOUR_PROFILE, official_bundle=origin)
    original.validate_inputs(inputs)
    save = (root / capture['save']['extraction907']['manifest']).parent / 'source.Civ6Save'
    source = capture['save']['source']
    original._file(dict(path=str(save), bytes=source['bytes'], sha256=source['sha256']),
                   dependencies, prefix_bytes=0)

    databases = {role: files['database_' + role] for role in ('configuration', 'gameplay', 'localization')}
    for role in ('configuration', 'gameplay'):
        captured_db = capture['export_matches'][role]['copy']
        if databases[role]['sha256'] != captured_db['sha256'] or databases[role]['size_bytes'] != captured_db['bytes']:
            raise ValueError('Prepared Base database differs from the official capture: ' + role)
    bootstrap = _check_localization(manifest, folder, capture, dependencies)
    runtimes = [json.loads(_pin_original(capture['artifacts'][name], dependencies))
                for name in ('runtime-selections-before.json', 'runtime-selections-after.json')]
    scripts = json.loads(_pin_original(capture['selected_gameplay_sources']['manifest'], dependencies))
    content = manifest['content_profile']
    _verify_content_profile(content, process, databases, bootstrap, runtimes, scripts)

    fixture = dict(schema='civ6rl.native-fixture.v1', purpose='diagnostic retained official Base hotseat inputs',
                   eligible_for_training=False, databases=databases, localization_bootstrap=bootstrap,
                   official_bundle=dict(path=origin[0], sha256=origin[1]), input_profile=input_profile)
    return original.PreparedBundle(origin, inputs, manifest['initial_turn'], engine, fixture, dependencies,
                                   manifest['expected_readback'], content, execution_image=execution_image)


def prepare_bundle(reference, *, execution_image, input_profile, output_directory):
    """Create a new private fixture manifest for the existing worker-copy pipeline."""
    bundle = read_bundle(reference, execution_image=execution_image, input_profile=input_profile)
    directory = resolve_path(Path(output_directory)).resolve()
    if not directory.is_relative_to(resource_root() / 'work'):
        raise ValueError('Base fixture must remain under private work')
    directory.mkdir(parents=True)
    manifest = directory / 'manifest.json'
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(bundle.fixture, stream, indent=2)
        stream.write('\n')
    return bundle, manifest


def process_host(execution_image):
    if execution_image is not _BASE_PROFILE:
        raise ValueError('Installed Base requires the exact registered execution image')
    return resolve_path(resource_root() / execution_image.native_host_build.executable_path).resolve(strict=True)


def bind_worker(closure, bundle):
    from .stdout_transport_profiles import selected_profile, source_dependencies

    image = bundle.execution_image
    build = image.native_host_build
    closure['execution_image'] = identity(image)
    closure['stdout_transport'] = selected_profile(image.image_sha256, build.executable_sha256)
    closure['pins'].update(source_dependencies(core_sha256=image.image_sha256))


def locale_number_source_pins(image):
    """Bind the existing number-format ABI proof to the installed Base Localization DLL."""
    from .native import native_locale_number982 as number
    from .native.native_source_cache import load_pinned_json

    if image is not _BASE_PROFILE:
        raise ValueError('Installed Base Localization requires its exact execution image')
    library = next(row for row in image.shared_dependencies if row.name == 'Localization_FinalRelease.dll')
    historical = load_pinned_json(number.SOURCE_PROOF, number.SOURCE_PROOF_SHA256)
    current = _source(number._CURRENT_LOCALE_BODY_PROOF)
    required_exports = {name: hex(rva) for name, rva in number._EXPORT_RVAS.items()}
    if (historical['exports'] != required_exports
            or historical['localization_image']['sha256'] != library.reference_sha256
            or current['reference_image']['sha256'] != library.reference_sha256
            or current['current_image']['sha256'] != library.sha256
            or Path(current['current_image']['path']) != Path(library.path)
            or {name: row['current_export_rva'] for name, row in current['exports'].items()} != required_exports
            or any(row['current_function']['complete_pdata_body'] is not True for row in current['exports'].values())):
        raise ValueError('Installed Base number formatter differs from its shared Localization ABI proof')
    paths = {
        number.SOURCE_PROOF: number.SOURCE_PROOF_SHA256,
        resource_root() / number._CURRENT_LOCALE_BODY_PROOF[0]: number._CURRENT_LOCALE_BODY_PROOF[1],
        Path(library.path): library.sha256,
    }
    paths.update({resource_root() / row['path']: row['sha256'] for row in historical['sources']})
    return paths


def validate_localization_fixture(bundle, manifest):
    """Check the Base Runtime's supported package, settings and private database."""
    if (type(bundle) is not original.PreparedBundle or bundle.execution_image is not _BASE_PROFILE
            or bundle.reference != REFERENCE
            or manifest['official_bundle'] != bundle.fixture['official_bundle']
            or manifest['input_profile'] != 'hotseat-four'
            or manifest['localization_bootstrap'] != bundle.fixture['localization_bootstrap']):
        raise ValueError('Installed Base Localization does not belong to its official capture')
    source = bundle.fixture['databases']['localization']
    actual = manifest['databases']['localization']
    if (actual['sha256'] != source['sha256'] or actual['size_bytes'] != source['size_bytes']
            or Path(actual['path']).resolve(strict=True) == Path(source['path']).resolve(strict=True)):
        raise ValueError('Installed Base Localization requires an exact private database copy')


def checkpoint_enabled(closure):
    """Admit Save only for the exact installed Base Capture09 session."""
    enabled = closure.get('checkpoint_on_close', False)
    if type(enabled) is not bool:
        raise ValueError('Checkpoint option must be Boolean')
    if enabled and (closure.get('input_profile') != 'hotseat-four'
            or closure.get('execution_image') != identity(_BASE_PROFILE)
            or original.normalize_reference(closure.get('official_bundle')) != REFERENCE
            or closure.get('resume_checkpoint') is not None
            or closure.get('network_checkpoint') is not None
            or closure.get('world_input_diagnostic', False) is not False):
        raise ValueError('Checkpoint requires the installed Base Capture09 session')
    return enabled


def checkpoint_source_pins():
    from .native import native_checkpoint_jobs as jobs
    from .native import native_checkpoint_provider as provider
    from .native import native_checkpoint_stream as stream

    return {
        stream.PROOF_PATH.relative_to(resource_root()).as_posix(): stream.PROOF_SHA256,
        'work/native-checkpoint-stream-contract341.json': stream.PARENT_SHA256,
        'evidence/native-checkpoint-configuration-stream-v3/' + provider.PROOF_SHA256 + '.json': provider.PROOF_SHA256,
        jobs.PROOF_PATH.relative_to(resource_root()).as_posix(): jobs.PROOF_SHA256,
    }



def checkpoint_manifest(reference):
    """Read an immutable checkpoint under the exact Capture09 profile."""
    from .native.native_checkpoint_retained_save import MAX_BYTES
    from .native.native_session_checkpoint import HOTSEAT_SCHEMA
    from .native.native_session_resume import MAX_CHAIN_DEPTH, normalize_reference
    from .native.native_official_hotseat import PLAYERS
    from .native.native_source_cache import load_pinned_json

    canonical = normalize_reference(dict(path=reference[0], sha256=reference[1]))
    if canonical != reference:
        raise ValueError('Hotseat checkpoint reference is not canonical')
    manifest = load_pinned_json(resource_root() / reference[0], reference[1])
    actor = manifest.get('player_id')
    turn = manifest.get('observed_game_turn')
    depth = manifest.get('lineage_depth', 0)
    parent = manifest.get('parent_checkpoint')
    if (manifest.get('schema') != HOTSEAT_SCHEMA
            or manifest.get('input_profile') != HOTSEAT_FOUR_PROFILE.name
            or manifest.get('source_official_bundle') != dict(zip(('path', 'sha256'), REFERENCE))
            or manifest.get('execution_image') != identity(_BASE_PROFILE)
            or manifest.get('core_sha256') != _BASE_PROFILE.reference_core_sha256
            or manifest.get('native_save_status') != 0 or manifest.get('stream_closed') is not True
            or manifest.get('game_version_prefix') != '05000000'
            or manifest.get('jobs_quiescent_unchanged') is not True
            or type(actor) is not int or actor not in PLAYERS
            or type(turn) is not int or not 1 <= turn <= 100_000
            or type(depth) is not int or not 0 <= depth <= MAX_CHAIN_DEPTH
            or (parent is None) != (depth == 0)
            or manifest.get('host_placement_tracking') != ()
            or manifest['observation']['player_id'] != actor or manifest['decisions']['player_id'] != actor
            or turn != manifest['observation']['turn'] or turn != manifest['decisions']['turn']):
        raise ValueError('Hotseat resume requires a quiescent Capture09 checkpoint')
    directory = Path(reference[0]).parent
    for role, name in (('gamecore', 'game.raw'), ('application_configuration', 'configuration.raw')):
        row = manifest['components'][role]
        if (row['path'] != (directory / name).as_posix() or type(row['bytes']) is not int
                or not 4 <= row['bytes'] <= MAX_BYTES):
            raise ValueError('Hotseat checkpoint component path or size differs')
    return manifest


def checkpoint_lineage(reference):
    """Validate each edge independently of the root capture and private DB checks."""
    from .native.native_session_resume import MAX_CHAIN_DEPTH, normalize_reference, plain

    nodes = []
    while reference is not None:
        if len(nodes) > MAX_CHAIN_DEPTH:
            raise ValueError('Hotseat checkpoint lineage exceeds its bound')
        manifest = checkpoint_manifest(reference)
        nodes.append((reference, manifest))
        parent = manifest.get('parent_checkpoint')
        reference = normalize_reference(plain(parent)) if parent is not None else None
    for (_, child), (_, parent) in zip(nodes, nodes[1:]):
        if (child['lineage_depth'] != parent.get('lineage_depth', 0) + 1
                or child['observed_game_turn'] < parent['observed_game_turn']
                or child['input_components_sha256'] != {
                    kind: row['sha256'] for kind, row in parent['components'].items()}):
            raise ValueError('Hotseat checkpoint ancestry has a different parent or turn')
    return nodes


def checkpoint_dependencies(nodes):
    """Pin parent metadata and output streams in the worker's input closure."""
    dependencies = {}
    for reference, manifest in nodes:
        dependencies[reference[0]] = reference[1]
        for row in (*manifest['components'].values(), manifest['session_closure'], manifest['fixture']):
            if dependencies.setdefault(row['path'], row['sha256']) != row['sha256']:
                raise ValueError('Hotseat checkpoint ancestry disagrees on a source hash')
    return dependencies


def validate_resumed_inputs(inputs):
    from .native.native_official_load import sha

    manifest = checkpoint_manifest(inputs.checkpoint)
    if (inputs.official_bundle != REFERENCE or inputs.profile is not HOTSEAT_FOUR_PROFILE
            or any(sha(raw) != manifest['components'][kind]['sha256']
                   for kind, raw in (('gamecore', inputs.game),
                                     ('application_configuration', inputs.configuration)))):
        raise ValueError('Hotseat loaded component pair differs from the checkpoint')
    return manifest


def resume_bundle(bundle, closure, worker_fixture):
    from dataclasses import replace
    from .native.official_configuration import compare_provider_roundtrip
    from .native.native_session_resume import _lineage_json, checked_file, normalize_reference, plain
    from .native.native_official_load import sha

    reference = normalize_reference(closure['hotseat_checkpoint'])
    if reference != (closure['hotseat_checkpoint']['path'], closure['hotseat_checkpoint']['sha256']):
        raise ValueError('Hotseat checkpoint reference is not canonical')
    nodes = checkpoint_lineage(reference)
    manifest = nodes[0][1]
    if (manifest['observed_game_turn'] != closure['initial_turn']
            or any(closure['pins'].get(path) != digest
                   for path, digest in checkpoint_dependencies(nodes).items())):
        raise ValueError('Hotseat resume closure differs from its checkpoint')
    origin = original._manifest(bundle.reference)[1]
    parent_ref, parent_turn = None, bundle.initial_turn
    seen_databases = {resolve_path(Path(row['path'])).resolve()
                      for row in worker_fixture['databases'].values()}
    for relative, checkpoint in reversed(nodes):
        old_closure = plain(_lineage_json(checkpoint['session_closure']))
        old_fixture = _lineage_json(checkpoint['fixture'])
        producing_run = resolve_path(resource_root() / relative[0]).resolve().parent.parent
        old_fixture_path = resolve_path(resource_root() / checkpoint['fixture']['path']).resolve()
        if (not checkpoint_enabled(old_closure)
                or checkpoint['origin_official_save_sha256'] != origin['save']['source']['sha256']
                or old_closure['initial_turn'] != parent_turn
                or old_closure.get('hotseat_checkpoint') != parent_ref
                or resolve_path(resource_root() / checkpoint['session_closure']['path']).resolve() != producing_run / 'closure.json'
                or resolve_path(Path(old_closure['fixture'])).resolve() != old_fixture_path
                or set(old_fixture['databases']) != set(worker_fixture['databases'])):
            raise ValueError('Hotseat checkpoint does not descend from the exact captured session')
        for role, row in worker_fixture['databases'].items():
            prior = old_fixture['databases'][role]
            path = resolve_path(Path(prior['path'])).resolve()
            if row['sha256'] != prior['sha256'] or path in seen_databases:
                raise ValueError('Hotseat resume requires distinct private databases with the same content')
            seen_databases.add(path)
        parent_ref = dict(path=relative[0], sha256=relative[1])
        parent_turn = checkpoint['observed_game_turn']
    root = nodes[-1][1]
    if root['input_components_sha256'] != dict(
            gamecore=sha(bundle.inputs.game), application_configuration=sha(bundle.inputs.configuration)):
        raise ValueError('Hotseat checkpoint root differs from the original component pair')

    configuration = checked_file(manifest['components']['application_configuration'])
    game = checked_file(manifest['components']['gamecore'])
    compare_provider_roundtrip(bundle.inputs.configuration, configuration)
    if game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('Hotseat resume native stream version differs')
    inputs = replace(bundle.inputs, configuration=configuration, game=game, checkpoint=reference)
    validate_resumed_inputs(inputs)
    obs = plain(manifest['observation'])
    readback = dict(turn=obs['turn'], width=obs['width'], height=obs['height'], player_id=obs['player_id'],
                    gold=obs['economy']['gold'], city_count=len(obs['cities']),
                    units=sorted(({k: row[k] for k in ('id','type','x','y','damage','moves')}
                                  for row in obs['units']), key=lambda row: row['id']))
    return replace(bundle, inputs=inputs, initial_turn=obs['turn'], expected_readback=readback)


def verify_worker(closure, *, executable):
    """Confirm the actual child and its copied inputs before mapping GameCore."""
    from .native.native_host import validate_fixture
    from .native.native_hotseat_session import NativeHotseatActionSession
    from .base_public_locale import source_files as locale_files
    from .stdout_transport_profiles import selected_profile, source_dependencies

    image = from_identity(closure['execution_image'])
    if (image is not _BASE_PROFILE or closure['schema'] != NativeHotseatActionSession.closure_schema
            or closure['input_profile'] != NativeHotseatActionSession.input_profile
            or closure.get('resume_checkpoint') is not None
            or closure.get('network_checkpoint') is not None):
        raise ValueError('Installed Base worker requires its exact hotseat reset closure')
    save_on_close = checkpoint_enabled(closure)
    if Path(executable).resolve(strict=True) != process_host(image):
        raise ValueError('Running worker is not the registered installed Base host')
    bundle = read_bundle(closure['official_bundle'], execution_image=image, input_profile=closure['input_profile'])
    if closure.get('hotseat_checkpoint') is None and closure['initial_turn'] != bundle.initial_turn:
        raise ValueError('Installed Base worker initial turn differs from its capture')
    dependencies = bundle.dependencies | source_dependencies(core_sha256=image.image_sha256)
    dependencies.update({str(path): digest for path, digest in locale_files(image).items()})
    if save_on_close:
        dependencies.update(checkpoint_source_pins())
    if any(closure['pins'].get(path) != digest for path, digest in dependencies.items()):
        raise ValueError('Installed Base worker is missing an exact input or service proof')
    if closure['stdout_transport'] != selected_profile(image.image_sha256, image.native_host_build.executable_sha256):
        raise ValueError('Installed Base stdout transport belongs to another image or host')

    fixture_path = resolve_path(Path(closure['fixture'])).resolve(strict=True)
    if not fixture_path.is_relative_to(resource_root() / 'work'):
        raise ValueError('Installed Base worker fixture escaped private work')
    fixture = validate_fixture(fixture_path)
    workers = closure['fixture_isolation']['workers']
    if (len(workers) != 1 or Path(workers[0]['manifest_path']).resolve() != fixture_path
            or fixture['official_bundle'] != bundle.fixture['official_bundle']
            or fixture['input_profile'] != bundle.fixture['input_profile']
            or fixture['localization_bootstrap'] != bundle.fixture['localization_bootstrap']
            or set(fixture['databases']) != set(bundle.fixture['databases'])
            or set(workers[0]['databases']) != set(bundle.fixture['databases'])):
        raise ValueError('Installed Base worker fixture does not belong to the retained capture')
    for role, expected in bundle.fixture['databases'].items():
        actual = fixture['databases'][role]
        private = Path(actual['path']).resolve(strict=True)
        source = Path(expected['path']).resolve(strict=True)
        isolated = workers[0]['databases'][role]
        if (private == source or private.parent != fixture_path.parent
                or isolated != dict(source_path=str(source), copy_path=str(private), sha256=expected['sha256'])
                or actual['sha256'] != expected['sha256'] or actual['size_bytes'] != expected['size_bytes']):
            raise ValueError('Installed Base worker requires an exact private copy of ' + role)
        header = original._file(dict(path=str(private), bytes=expected['size_bytes'], sha256=expected['sha256']),
                                {}, prefix_bytes=16)
        if header != b'SQLite format 3\x00':
            raise ValueError('Installed Base worker database does not have a SQLite header: ' + role)
    if closure.get('hotseat_checkpoint') is not None:
        return resume_bundle(bundle, closure, fixture)
    return bundle

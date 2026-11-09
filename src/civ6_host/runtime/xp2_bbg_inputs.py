"""Private BBG 7.5.1 PoC inputs for the existing XP2 saved-Load owner."""

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path, PureWindowsPath

from .paths import resource_root
from .resource_resolution import resolve_path
from . import xp2_bundle_inputs as xp2

CAPTURE = 'work/official-capture/xp2-bbg751-correlated-20261104'
REFERENCE = (f'{CAPTURE}/recovered-exact-inputs.json',
             '6bdcd32192781f3f92d26ee4632ce2539ccf2a95baa6b25d34f4616f26b1805a')
CAPTURE_ENV = 'CIV6_HOST_BBG751_OFFICIAL_CAPTURE'
UI_HOST = ('work/native-host-xp2-bbg-ui-build03/civ6rl-native-python.exe',
           '61953897b696b45a7998126392f5759c7b34ed045551ff7d597ffa3eaa2fafda')
UI_HOSTS = (
    UI_HOST,
    ('work/native-host-xp2-bbg-ui-build02/civ6rl-native-python.exe',
     '01e6cd9c49af96cc3f1a58aac5f111722cdf02e037916d7de811b005a461ea6f'),
    ('work/native-host-xp2-bbg-ui-build01/civ6rl-native-python.exe',
     '383bbbdbe57f3ccb453c2584faf98476659c180035a597ae70c8ce5ea78c8da5'),
)
from .source_build_identity import CURRENT_HAVOK_HOST_REFERENCE, CURRENT_STRINGS_HOST_REFERENCE
UI_HOSTS = (*UI_HOSTS, CURRENT_HAVOK_HOST_REFERENCE, CURRENT_STRINGS_HOST_REFERENCE)


def selected_ui_host(execution_image=None):
    if execution_image is None:
        return UI_HOST
    from .execution_images import identity
    selected = identity(execution_image)
    if (selected['profile_id'] != 'xp2-gamecore-current-092abfbb'
            or selected['reference_core_sha256'] != xp2.XP2_CORE_SHA256):
        raise ValueError('No compiled BBG host for this execution image')
    return CURRENT_STRINGS_HOST_REFERENCE


SCRIPT_SHA256 = '6538613569e4ab38b271104e800b54959192472a5ae3f2b3ea92ca3d4813cc6d'
MOD_ID = 'cb84075d-5007-4207-b662-c35a5f7be260'
MOD_TITLE = 'Better Balanced Game 7.5.1'
WORKSHOP_ID = '2865001760'
WORKSHOP_ROOT = ('steamapps', 'workshop', 'content', '289070', WORKSHOP_ID)
_XP2_MODS = frozenset(('1b28771a-c749-434b-9053-d1380c553de9',
                       '4873eb62-8ccc-4574-b784-dda455e74e68', MOD_ID))
_BRIDGE_MOD = '29c609c4-0bfc-4b2d-9cdb-2e59556f4560'
SAVE_SHA256 = '7398be39ce368355d4c3be74b7368d363a5983b64a26038dedd167e587ed7d41'
CONFIGURATION_SHA256 = 'faad70775b94c1d7187b93f115b900704427b5a0821cd316388608e907d5f7d5'
GAME_SHA256 = '79556bfe2071560b40cf9ef9ed68abbeb9b16b20548b4ec932f1b45c5d0e0183'
DATABASE_PINS = {
    'configuration': dict(sha256='5c8c8e30e22e5490da6351f536844fba9edbbc0731b4a189c9efaea02b7aacf4', size_bytes=901120),
    'gameplay': dict(sha256='7b38a8f1fb26d272278cd14b80abbe3b189a2474ec938c1ba7fff2edbcd9de83', size_bytes=10842112),
    'localization': dict(sha256='3980b4f32ff656863322f9d2dd817ed9e8ba0f6babf233fab09b2d83e5f01c79', size_bytes=105500672),
}
SUPPORT_PATH = 'Base/Assets/UI/SupportFunctions.lua'
SUPPORT_SHA256 = '8c49e8f9a28f73c5da9e4258f813d5d0ff66863fd02cb0ca43cb397a1711c93b'


def prepared_reference():
    """Identify the local recovered handoff; read_bundle verifies its inputs."""
    return dict(path=str(resolve_path(resource_root() / REFERENCE[0]).resolve()), sha256=REFERENCE[1])


def registered_reference():
    """Select one explicitly pinned completed BBG capture for this process."""
    value = os.environ.get(CAPTURE_ENV)
    return _parse_registration(value) if value is not None else None


@lru_cache(maxsize=1)
def _parse_registration(value):
    from .native.native_official_bundle import normalize_reference
    reference = normalize_reference(json.loads(value))
    path = PureWindowsPath(reference[0])
    if (path.is_absolute() or path.parts[:2] != ('work', 'official-capture')
            or path.name != 'manifest.json'):
        raise ValueError('Registered BBG capture must be an official capture manifest')
    return reference


def is_reference(reference):
    if type(reference) is dict and set(reference) == {'path', 'sha256'}:
        reference = (reference['path'], reference['sha256'])
    return reference == REFERENCE or reference is not None and reference == registered_reference()


def _complete_capture(reference):
    from .native.native_official_bundle import _manifest
    if reference is None or reference != registered_reference():
        raise ValueError('BBG complete capture requires an explicitly registered identity')
    return _manifest(reference)[1]


def origin_save_sha256(reference):
    return SAVE_SHA256 if reference == REFERENCE else _complete_capture(reference)['save']['source']['sha256']


def verify_original_streams(inputs, capture, dependencies):
    """Rejoin the compact streams to the official save, without replaying SQL capture."""
    from .native.native_official_bundle import ROOT, _file, parse_configuration
    from .native.official_application_configuration import extract_application_configuration
    from .native.official_save import inspect_save

    saved = capture['save']
    path = (ROOT / saved['extraction907']['manifest']).parent / 'source.Civ6Save'
    source = saved['source']
    raw = _file(dict(path=str(path), sha256=source['sha256'], bytes=source['bytes']), dependencies)
    configuration, receipt = extract_application_configuration(raw)
    verify_saved_content(receipt['content_declaration'])
    _, maps = parse_configuration(configuration, 'LAN')
    _, sections = inspect_save(raw)
    game = [section.payload for section in sections if section.kind == 'gamecore_stream_candidate']
    if (configuration != inputs.configuration or maps != inputs.map_values or game != [inputs.game]
            or receipt['save_sha256'] != source['sha256']):
        raise ValueError('Registered BBG inputs differ from their official saved streams')


def _complete_localization(capture):
    from .native.native_official_bundle import _file
    reference = capture['localization_exports']['after']
    export = json.loads(_file(reference, {}, maximum=4 * 1024**2))
    row = export['database']
    database = dict(path=row['path'], sha256=row['sha256'], size_bytes=row['bytes'])
    bootstrap = dict(export['bootstrap'], official_export=reference)
    # Package ICU copies carry a byte count. Rejoin that immutable value to
    # the pinned runtime receipt instead of comparing it to an un-sized row.
    runtime = json.loads(_file(export['runtime_after'], {}, maximum=4 * 1024**2))
    icu = runtime['icu_data']
    if (type(icu.get('bytes')) is not int or not 0 < icu['bytes'] <= 64 * 1024**2
            or any(bootstrap['icu_data'].get(key) != icu.get(key) for key in ('path', 'sha256'))
            or 'bytes' in bootstrap['icu_data'] and bootstrap['icu_data']['bytes'] != icu['bytes']):
        raise ValueError('BBG Localization ICU bootstrap differs from its pinned runtime receipt')
    bootstrap['icu_data'] = dict(bootstrap['icu_data'], bytes=icu['bytes'])
    return database, bootstrap


def database_pins(reference):
    if reference == REFERENCE:
        return DATABASE_PINS
    capture = _complete_capture(reference)
    localization, _ = _complete_localization(capture)
    rows = capture['export_matches']
    sources = {role: dict(sha256=rows[role]['copy']['sha256'], size_bytes=rows[role]['copy']['bytes'])
               for role in ('configuration', 'gameplay')}
    sources['localization'] = {key: localization[key] for key in ('sha256', 'size_bytes')}
    return sources


def _json(path, digest, dependencies):
    from .native.native_official_bundle import _file
    path = resolve_path(resource_root() / path)
    return json.loads(_file(dict(path=str(path), sha256=digest, bytes=path.stat().st_size),
                            dependencies, maximum=4 * 1024**2))


def _capture(dependencies):
    record = _json(*REFERENCE, dependencies)
    if (record['schema'] != 'civ6-host.bbg751-correlated-inputs-recovery.v1'
            or record['status'] != 'exact_main_databases_and_ordered_selection_verified'
            or record['training_eligible'] is not False or record['core_sha256'] != xp2.XP2_CORE_SHA256):
        raise ValueError('BBG PoC recovery scope differs')
    preflight = _json(CAPTURE + '-invocation/preflight.json',
                      'a2c3aaef6024d6463a63c2bdbb275a11090aaf56af4578d616e70147f1bbfc5b', dependencies)
    process = preflight['process']
    xp2.validate_process(process)
    if process['identity'] != record['process']:
        raise ValueError('BBG PoC capture process differs')
    return record, process


def validate_localization_fixture(manifest):
    from .xp1_saved_load import validate_private_bootstrap

    reference = manifest.get('official_bundle')
    if manifest.get('input_profile') != 'xp2-lan' or not is_reference(reference):
        raise ValueError('BBG Localization requires an explicitly selected capture')
    reference = (reference['path'], reference['sha256'])
    if reference == REFERENCE:
        record, _ = _capture({})
        source_row, bootstrap = record['database_copies']['localization'], record['localization_bootstrap']
        expected = DATABASE_PINS['localization']
    else:
        source_row, bootstrap = _complete_localization(_complete_capture(reference))
        expected = {key: source_row[key] for key in ('sha256', 'size_bytes')}
    actual = manifest['databases']['localization']
    source = resolve_path(Path(source_row['path']))
    path = resolve_path(Path(actual['path']))
    root = path.resolve(strict=True).parent
    if (any(actual.get(key) != value for key, value in expected.items())
            or path.resolve(strict=True) != path or path.samefile(source)
            or path.stat().st_size != expected['size_bytes']):
        raise ValueError('BBG Localization requires an independent exact database copy')
    validate_private_bootstrap(manifest, bootstrap, private_root=root)


def declared_bbg(mods):
    for row in mods or ():
        if row['mod_id'].lower() != MOD_ID:
            continue
        fields = row['optional']
        title = fields.get('MOD_TITLE_KEY')
        try:
            titles = json.loads(title) if title else None
        except json.JSONDecodeError:
            titles = None
        title_matches = title == MOD_TITLE or (type(titles) is dict and set(titles) == {MOD_TITLE})
        return dict(mod_id=row['mod_id'], workshop_id=fields.get('MOD_SUBSCRIPTION_ID'),
                    saved_version_field=row['version'], exact_title_matches=title_matches,
                    identity_matches=fields.get('MOD_SUBSCRIPTION_ID') == WORKSHOP_ID)
    return None


def verify_saved_content(declaration):
    mods = declaration['declared_mods']
    ids = {row['mod_id'].lower() for row in mods}
    bbg = declared_bbg(mods)
    if (declaration['declared_ruleset'] != xp2.RULESET
            or len(ids) != len(mods) or ids - {_BRIDGE_MOD} != _XP2_MODS
            or any(row['version'] != '1' for row in mods)
            or bbg is None or not bbg['exact_title_matches'] or not bbg['identity_matches']):
        raise ValueError('Save does not declare the qualified BBG 7.5.1 content scope')


def captured_script_binding(reference, *, process):
    """Verify the exact source pair used by the existing BBG gameplay adapters."""
    from .script_wire_paths import registry_from_capture

    registry, hashes, dependencies = registry_from_capture(reference, process=process)
    names = registry.wire_paths
    bbg_path = PureWindowsPath(names[1]) if len(names) == 2 else None
    expected_suffix = (*WORKSHOP_ROOT, 'scripts', 'bbg_script.lua')
    if (bbg_path is None or not bbg_path.is_absolute()
            or tuple(part.casefold() for part in bbg_path.parts[-len(expected_suffix):]) != expected_suffix
            or names[0] != xp2.SELECTED_PATHS[0]
            or list(hashes.values()) != [xp2.SCRIPT_SHA256, SCRIPT_SHA256]):
        raise ValueError('Captured gameplay scripts differ from the qualified BBG 7.5.1 pair')
    return registry, hashes, dependencies


def script_binding(bundle):
    if bundle.reference != REFERENCE:
        capture = _complete_capture(bundle.reference)
        return captured_script_binding(capture['selected_gameplay_sources']['manifest'],
                                       process=capture['preflight']['process'])
    dependencies = {}
    record, process = _capture(dependencies)
    registry, hashes, script_dependencies = captured_script_binding(record['script_manifest'], process=process)
    dependencies.update(script_dependencies)
    if list(registry.wire_paths) != record['script_order']:
        raise ValueError('BBG PoC ordered registry differs from the recovered sources')
    return registry, hashes, dependencies


def validate_candidate_inputs(inputs, bundle):
    from .native.native_official_bundle import PreparedBundle, parse_configuration
    from .native.native_official_load import OfficialInputs
    from . import xp2_bundle_inputs as xp2
    if type(bundle) is not PreparedBundle or type(inputs) is not OfficialInputs:
        raise ValueError('BBG requires its exact XP2 LAN input identity')
    current_capture = None
    engine_identity = bundle.content_profile.get('engine')
    actual_core = engine_identity.get('gamecore_sha256') if type(engine_identity) is dict else None
    if actual_core == xp2.CURRENT_XP2_CORE_SHA256:
        registered = registered_reference()
        if bundle.reference == REFERENCE or registered is None or bundle.reference != registered:
            raise ValueError('Current BBG inputs require the exact registered capture origin')
        current_capture = _complete_capture(bundle.reference)
        process = current_capture.get('preflight', {}).get('process')
        if (type(process) is not dict or current_capture.get('process_after') != process
                or process.get('exe_sha256') != xp2.CURRENT_EXE_SHA256
                or type(process.get('gamecore_module')) is not dict
                or process['gamecore_module'].get('sha256') != xp2.CURRENT_XP2_CORE_SHA256
                or engine_identity.get('executable_sha256') != xp2.CURRENT_EXE_SHA256):
            raise ValueError('Current BBG capture process and content image differ')
        selected = xp2.verify_current_execution_image(
            bundle.execution_image, core_path=process['gamecore_module'].get('path'))
        if Path(bundle.engine_path).resolve() != Path(selected.path).resolve():
            raise ValueError('Current BBG engine path differs from its execution-image profile')
    elif actual_core != xp2.XP2_CORE_SHA256:
        raise ValueError('BBG requires an exact XP2 runtime image')
    elif type(bundle) is PreparedBundle and bundle.execution_image is not None:
        xp2.verify_current_execution_image(bundle.execution_image,
                                            core_path=str(bundle.engine_path))
    if (type(bundle) is not PreparedBundle or type(inputs) is not OfficialInputs
            or bundle.inputs is not inputs or not is_reference(bundle.reference)
            or inputs.official_bundle != bundle.reference or inputs.profile is not xp2.XP2_LAN_PROFILE
            or type(bundle.initial_turn) is not int or not 1 <= bundle.initial_turn <= 100000
            or bundle.content_profile.get('final_databases') != database_pins(bundle.reference)
            or tuple(bundle.expected_readback[key] for key in ('turn', 'width', 'height', 'player_id'))
               != (bundle.initial_turn, 44, 26, 0)):
        raise ValueError('BBG requires its exact XP2 LAN input identity')
    if inputs.checkpoint is None:
        if bundle.reference == REFERENCE:
            if (bundle.initial_turn != 1
                    or hashlib.sha256(inputs.configuration).hexdigest() != CONFIGURATION_SHA256
                    or hashlib.sha256(inputs.game).hexdigest() != GAME_SHA256):
                raise ValueError('BBG original saved components differ')
        else:
            verify_original_streams(inputs, current_capture or _complete_capture(bundle.reference), {})
    else:
        from .xp1_session_checkpoint import validate_resumed_inputs
        validate_resumed_inputs(inputs, bundle)
    if parse_configuration(inputs.configuration, 'LAN')[1] != inputs.map_values:
        raise ValueError('BBG map values differ')
    return inputs.profile


def read_bundle(*, execution_image=None):
    """Admit this pin for the private worker only, without changing stock capture994."""
    from .native import native_official_bundle as official
    from .native.official_application_configuration import extract_application_configuration
    from .native.official_save import inspect_save
    from .xp2_capture_selection import _prepared_bundle

    dependencies = {}
    record, process = _capture(dependencies)
    raw = official._file(record['save'], dependencies, maximum=16 * 1024**2)
    configuration = official._file(record['configuration'], dependencies, maximum=1024**2)
    game = official._file(record['gamecore_stream'], dependencies, maximum=16 * 1024**2)
    expected, proof = extract_application_configuration(raw)
    _, sections = inspect_save(raw)
    game_sections = [section.payload for section in sections if section.kind == 'gamecore_stream_candidate']
    if (configuration != expected or game_sections != [game] or proof['save_sha256'] != SAVE_SHA256
            or proof['content_declaration']['declared_ruleset'] != xp2.RULESET):
        raise ValueError('Recovered BBG components differ from the exact official save')
    verify_saved_content(proof['content_declaration'])
    _, maps = official.parse_configuration(configuration, 'LAN')
    core = resolve_path(Path(process['gamecore_module']['path'])).resolve(strict=True)
    expected_image = xp2.XP2_CORE_SHA256
    if execution_image is not None:
        from .execution_images import identity, from_identity, verify
        # A selected image cannot change the captured process, content or ABI.
        selected = from_identity(identity(execution_image))
        if selected.reference_core_sha256 != expected_image or Path(selected.path).resolve() != core:
            raise ValueError('Execution image does not match the captured XP2 source interface')
        verify(selected)
        expected_image = selected.image_sha256
    with core.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_image:
            raise ValueError('Installed XP2 engine differs')
    dependencies[str(core)] = expected_image
    databases = {}
    for role, pin in DATABASE_PINS.items():
        row = record['database_copies'][role]
        if row['sha256'] != pin['sha256'] or row['bytes'] != pin['size_bytes']:
            raise ValueError('BBG database identity differs: ' + role)
        if official._file(row, dependencies, prefix_bytes=16) != b'SQLite format 3\0':
            raise ValueError('BBG database header differs: ' + role)
        databases[role] = dict(path=row['path'], **pin)
    bootstrap = record['localization_bootstrap']
    icu = resolve_path(Path(bootstrap['icu_data']['path']))
    official._file(dict(**bootstrap['icu_data'], bytes=icu.stat().st_size), dependencies, prefix_bytes=0)
    observation = _json(CAPTURE + '/observation-before.json',
                        '6fa091ae4171d9cdada785e6ccf9c66c35cb0a2a4142efcd68eacb57029603ca', dependencies)
    report = _json(CAPTURE + '/runtime-selections-before.json',
                   'af865d7437e391d0fd7a1a98c483a8ed361b3066c971d2859b3048242527e9f4', dependencies)
    script_manifest = json.loads(official._file(record['script_manifest'], dependencies))
    active = dict(report['gameplay_active_list']['state'],
                  selected_and_active_empty=report['gameplay_active_list']['selected_and_active_empty'])
    selection = report['semantic']
    content = official.build_content_profile(process=process, databases=databases,
        localization_bootstrap=bootstrap, resolved_content=selection['content'],
        gameplay_selection=selection, active_state=active, script_manifest=script_manifest)
    bundle = _prepared_bundle(REFERENCE, (configuration, game), maps, core, observation,
                              databases, bootstrap, content, dependencies)
    if execution_image is not None:
        from dataclasses import replace
        bundle = replace(bundle, execution_image=selected)
    validate_candidate_inputs(bundle.inputs, bundle)
    _, _, scripts = script_binding(bundle)
    dependencies.update(scripts)
    return official._remember_prepared_bundle(bundle, 'xp2-lan',
        official._prepared_bundle_validator_digests(), _token=official._PARENT_ADMISSION_TOKEN,
        _input_only=True)


"""Shared preparation of the exact XP1 saved inputs and executable.

No engine execution or profile admission occurs here. The qualifier and the
persistent session use these same source checks and private input copies.
"""
import hashlib
import json
import shutil
from pathlib import Path
from .paths import resource_root
from .provenance import installed_source_pins
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .source_verification import file_sha256, verification_scope

REPO = Path(__file__).resolve().parents[3]


def digest(data):
    return hashlib.sha256(data).hexdigest()


SAVED_LOAD_HOST = ('work/native-host-xp1-jobs-build01/civ6rl-native-python.exe',
                   '09b7a2e1f049120d8483e01c81859d2796d0cd7882897587f66980c27a4ec7a6')


SAVED_LOAD_BUILD = ('work/native-host-xp1-jobs-build01/build.json',
                    'a3f0dea1be0bd59f66d8e02615997da766c189e2f6ff561215bd7dee4feb2b8b')


SAVED_LOAD_MANIFEST = (REPO/'native/profiles/xp1-jobs/source-manifest.json',
                       '75d2965e3d9602c7f9a576157de45bd04b54e1467d7c5d0dd73b72ace63c9052')


SAVED_LOAD_CLOSURE_ENV = 'CIV6_HOST_XP1_SAVED_LOAD_CLOSURE_SHA'


SAVED_UI_HOST = ('work/native-host-xp1-ui-build01/civ6rl-native-python.exe',
                 '949949ddca0ec61a55e3368bf062f46fcdb4b2f7dc52f25a49acc4758664224f')


SAVED_UI_BUILD = ('work/native-host-xp1-ui-build01/build.json',
                  '842ee9a916b247e23c68e55fed10e6edb00413ce4762b9fe706baa018c074010')


SAVED_UI_MANIFEST = (REPO/'native/profiles/xp1-ui/source-manifest.json',
                     '6da2aba65afe87cb8c304eb2a0b59d83a511d330a5e51a6ca07686360dd9449a')


def saved_load_pin(pins, path, expected=None):
    from civ6_host.runtime.resource_resolution import resolve_path
    path = resolve_path(Path(path)).resolve()
    actual = file_sha256(path)
    if expected is not None and actual != expected:
        raise ValueError('Saved Load source/build/input changed: '+str(path))
    if str(path) in pins and pins[str(path)] != actual:
        raise ValueError('Saved Load pin identity changed: '+str(path))
    pins[str(path)] = actual
    return path


CURRENT_XP1_SESSION_JOIN = (
    'work/trade-common-client/xp1-installed-session-source-joins.json',
    '27290d6e1c5657b94f057085fd340ee27fb9b6101cdb626653390e144a1796fb',
)


def current_session_join(image):
    from .configuration_profiles import _source
    from .execution_images import _XP1_PROFILE, identity
    if image is not _XP1_PROFILE:
        raise ValueError('Expected the registered installed XP1 session image')
    proof = _source(CURRENT_XP1_SESSION_JOIN)
    if (proof['schema'] != 'civ6-host.xp1-installed-session-source-joins.v1'
            or proof['execution_image'] != identity(image)):
        raise ValueError('XP1 session source join differs from its selected image')
    return proof


def materialize_xp1_session_pins(pins, image):
    from .found_unit_event_profiles import source as found_unit_source
    from .resource_resolution import resolve_path
    from .runtime_source_dependencies import materialize_runtime_source_pins
    proof = current_session_join(image)
    result = {}
    for name, expected in pins.items():
        path = str(resolve_path(Path(name)).resolve())
        if path in result and result[path] != expected:
            raise ValueError('XP1 session source dependency identity conflicts')
        result[path] = expected
    events = proof['events']
    event_path = events['current']['path']
    if result.get(event_path) == events['previous']:
        result[event_path] = events['current']['sha256']
        result[proof['archive']['path']] = proof['archive']['sha256']
    path, digest = CURRENT_XP1_SESSION_JOIN
    result[str(resource_root()/path)] = digest
    return materialize_runtime_source_pins(result, execution_image=image,
                                           provenance_images=found_unit_source(resource_root())['images'].values())


def verify_xp1_session_pins(pins, core, *, family):
    """Verify a live reader's inputs using the same image projection as preparation."""
    from .resource_resolution import resolve_path
    image = getattr(core, '_civ6_host_execution_image', None)
    if image is not None:
        pins = materialize_xp1_session_pins(pins, image)
        if Path(core._name).resolve() != Path(image.path).resolve():
            raise ValueError('XP1 reader module differs from its selected image')
    for name, expected in pins.items():
        if file_sha256(resolve_path(Path(name))) != expected:
            raise ValueError(f'XP1 {family} dependency changed: {name}')


def saved_load_build_pins(pins, *, ui=False, core_sha256=XP1_CORE_SHA256, official_bundle=None, execution_image=None):
    if type(ui) is not bool:raise ValueError('Native build selection must be explicit')
    if execution_image is not None and core_sha256 == XP1_CORE_SHA256:
        from .execution_images import _XP1_PROFILE, _verify_native_host_build
        from .native.native_official_bundle import normalize_reference
        from .xp1_saved_load import REFERENCE
        origin = official_bundle if type(official_bundle) is tuple else normalize_reference(official_bundle)
        if execution_image is not _XP1_PROFILE or origin != REFERENCE:
            raise ValueError('Selected XP1 host requires its exact retained capture')
        build = _verify_native_host_build(execution_image)
        for name, expected in build['build_dependencies'].items():
            saved_load_pin(pins, resource_root()/name, expected)
        host = execution_image.native_host_build
        return saved_load_pin(pins, resource_root()/host.executable_path, host.executable_sha256)
    if execution_image is not None and core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Selected execution-image host requires its exact source ABI')
    if core_sha256 == XP2_CORE_SHA256:
        if not ui:raise ValueError('Shared XP2 sessions require the qualified UI host build')
        from .xp2_session_inputs import XP2_UI_HOST
        from .source_build_identity import (verify_source_build, XP2_HOST_COMPONENT_SHA,
                                            xp2_component_requirements, CURRENT_UNSIGNED_LOG_HOST_REFERENCE)
        from .xp2_ui_binding_source import UI_COMPONENT_SHA
        from . import xp2_bbg_inputs as bbg
        bbg_capture=bbg.is_reference(official_bundle)
        stock_current=False
        if execution_image is not None and not bbg_capture:
            from .capture_admission import _stock_xp2_execution
            stock_current=_stock_xp2_execution(execution_image,origin=official_bundle)
        if stock_current:
            host = CURRENT_UNSIGNED_LOG_HOST_REFERENCE
        else:
            host = bbg.selected_ui_host(execution_image) if bbg_capture else XP2_UI_HOST
        executable=saved_load_pin(pins,resource_root()/host[0],host[1])
        build=verify_source_build(executable,required_components=xp2_component_requirements(executable, {
            'gamecore_python_host.c':XP2_HOST_COMPONENT_SHA,
            'script_core_ui_binding_profiles.inc':UI_COMPONENT_SHA}))
        for name, expected in build['build_dependencies'].items():
            saved_load_pin(pins,resource_root()/name,expected)
        return executable
    if core_sha256 != XP1_CORE_SHA256:raise ValueError('Unknown saved session build engine')
    host,build_ref,manifest_ref = ((SAVED_UI_HOST,SAVED_UI_BUILD,SAVED_UI_MANIFEST) if ui
                                 else (SAVED_LOAD_HOST,SAVED_LOAD_BUILD,SAVED_LOAD_MANIFEST))
    if ui:
        from .source_build_identity import verify_source_build
        executable = saved_load_pin(pins, resource_root()/host[0], host[1])
        verified = verify_source_build(executable, required_components={
            'script_core_bindings_xp1.inc': '1ec54d12e6c014a8ba9b2f97e68edf7ad2d775e9129a16eaa092db2159affc9f'})
        if tuple(verified['build_reference']) != build_ref:
            for path, expected in verified['build_dependencies'].items():
                saved_load_pin(pins, resource_root()/path, expected)
            return executable
    profile='xp1-official-ui-bindings' if ui else 'xp1-explicit-job-core'
    paths = [saved_load_pin(pins, resource_root()/name, expected)
             for name, expected in (host,build_ref,manifest_ref)]
    build = json.loads(paths[1].read_bytes())
    manifest = json.loads(paths[2].read_bytes())
    if (build['profile'] != profile
            or build['source_manifest_sha256'] != manifest_ref[1]
            or build['executable']['sha256'] != host[1]
            or manifest['profile'] != build['profile']):
        raise ValueError('Saved Load native build/profile identity differs')
    for row in manifest['sources']:
        saved_load_pin(pins, REPO/row['path'], row['sha256'])
    for row in build['sources']:
        saved_load_pin(pins, row['path'], row['sha256'])
        saved_load_pin(pins, row['source_path'], row['sha256'])
    return paths[0]


def saved_load_private_icu(fixture, pins, private):
    """The existing copier owns DBs; copy ICU without changing its metadata."""
    value = json.loads(fixture.read_bytes())
    icu = value['localization_bootstrap']['icu_data']
    source = saved_load_pin(pins, icu['path'], icu['sha256'])
    target = fixture.parent/'icudt56l.dat'
    if target.exists() or source == target:
        raise ValueError('Saved Load ICU needs a new independent private copy')
    shutil.copyfile(source, target)
    saved_load_pin(pins, source, icu['sha256'])
    saved_load_pin(pins, target, icu['sha256'])
    icu['path'] = str(target)
    fixture.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    private['manifest_sha256'] = digest(fixture.read_bytes())
    private['icu_copy'] = dict(source_path=str(source), copy_path=str(target), sha256=icu['sha256'])


def _prepare_xp2_sources(captured, package, unit_commands):
    from .xp2_session_inputs import xp2_saved_load_source_dependencies
    from .captured_saved_load import validate_candidate_inputs
    validate_candidate_inputs(captured.inputs, captured)
    pins = {}
    execution = getattr(captured, 'execution_image', None)
    for group in (installed_source_pins(), captured.dependencies,
                  xp2_saved_load_source_dependencies(postload160=True, observe_player=True,
                    official_bundle=captured.reference, execution_image=execution)):
        for name, expected in group.items():
            saved_load_pin(pins, resource_root()/name, expected)
    from . import xp2_bbg_inputs as bbg
    if bbg.is_reference(captured.reference):
        from .xp2_bbg_property_table import SOURCES as property_sources
        from .xp2_bbg_view_ready import _SOURCE as view_ready_source
        from .xp2_bbg_nested_events import SOURCE as nested_events_source
        for name, expected in (*property_sources, view_ready_source, nested_events_source):
            saved_load_pin(pins, resource_root()/name, expected)
        from .native.native_core_context_profiles import profile_for_core
        profile = profile_for_core(captured.engine_path, mode='context',
            **({'execution_image': execution} if execution is not None else {}))
        saved_load_pin(pins, profile.shared_dependency_directory.parents[2]/bbg.SUPPORT_PATH,
                       bbg.SUPPORT_SHA256)
    from .stdout_transport_profiles import source_dependencies as stdout_dependencies
    for name, expected in stdout_dependencies(core_sha256=XP2_CORE_SHA256).items():
        saved_load_pin(pins, name, expected)
    if unit_commands:
        execution_options = ({'execution_image': execution}
                             if execution is not None else {})
        from .xp2_government_source import source_dependencies as policy_dependencies
        for name, expected in policy_dependencies(**execution_options).items():
            saved_load_pin(pins, name, expected)
        from .xp2_policy_relocation import source_dependencies as relocation_dependencies
        for name, expected in relocation_dependencies(**execution_options).items():
            saved_load_pin(pins, name, expected)
        for name, expected in command_source_dependencies(XP2_CORE_SHA256, **execution_options).items():
            saved_load_pin(pins, name, expected)
        from .xp1_loaded_lifetime import source_dependencies as lifetime_dependencies
        for name, expected in lifetime_dependencies(XP2_CORE_SHA256, postload=True,
                continuation=True, **execution_options).items():
            saved_load_pin(pins, name, expected)
    saved_load_pin(pins, package['path'], package['sha256'])
    if execution is not None:
        from .execution_images import source_dependencies as execution_dependencies
        for path, expected in execution_dependencies(execution).items():
            saved_load_pin(pins, path, expected)
    return pins, saved_load_build_pins(pins, ui=True, core_sha256=XP2_CORE_SHA256,
        official_bundle=captured.reference, execution_image=execution)


def prepare_sources(captured, package, *, postload160, publish_cache,
                    close_loaded, observe_player, unit_commands, core_sha256=XP1_CORE_SHA256):
    """Pin actual source dependencies for the requested retained owner phases."""
    flags = (postload160, publish_cache, close_loaded, observe_player, unit_commands)
    if any(type(flag) is not bool for flag in flags):
        raise ValueError('XP1 source phases require exact Boolean values')
    if ((publish_cache or close_loaded) and not postload160
            or observe_player and not (publish_cache and close_loaded)
            or unit_commands and not observe_player):
        raise ValueError('XP1 requested phases lack their required owners')
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown captured session source engine')
    if core_sha256 == XP2_CORE_SHA256:
        if not (postload160 and publish_cache and close_loaded and observe_player):
            raise ValueError('Shared XP2 preparation requires the full observed loaded lifecycle')
        with verification_scope():
            return _prepare_xp2_sources(captured, package, unit_commands)
    pins = {}
    for name, expected in installed_source_pins().items():
        saved_load_pin(pins, name, expected)
    for name, expected in captured.dependencies.items():
        saved_load_pin(pins, resource_root()/name, expected)
    from .native.native_xp1_context_init import PROOF_PINS as context_proofs, SOURCE_PINS as context_sources
    for name, expected in (*context_proofs.values(), *context_sources.items()):
        saved_load_pin(pins, resource_root()/name, expected)
    from .xp1_prepare import source_dependencies as prepare_dependencies
    for name, expected in prepare_dependencies():
        saved_load_pin(pins, resource_root()/name, expected)
    from .native.native_host_slot48 import PINNED_EVIDENCE_SHA256 as lock_proof
    saved_load_pin(pins, resource_root()/'evidence/native-host-slot48'/(lock_proof + '.json'), lock_proof)
    from .native import native_checkpoint_configuration_normalization as normalization
    for folder, expected in (
        ('native-checkpoint-empty-string-normalization', normalization.PROOF_SHA256),
        ('native-checkpoint-configuration-stream-v3', normalization.PROVIDER_PROOF_SHA256),
    ):
        saved_load_pin(pins, resource_root()/'evidence'/folder/(expected + '.json'), expected)
    from civ6_host.runtime.stdout_transport_profiles import source_dependencies as stdout_dependencies
    for name, expected in stdout_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.xp1_load_capability import source_dependencies
    for name, expected in source_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.application_mirror_profiles import source_dependencies as mirror_dependencies
    for name, expected in mirror_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.xp1_load_options import source_dependencies as options_dependencies
    for name, expected in options_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.xp1_saved_load_logger import source_dependencies as logger_dependencies
    for name, expected in logger_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.a0_emergencies_updated import source_dependencies as publication_event_dependencies
    for name, expected in publication_event_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.a0_notification_scope_source import source_dependencies as notification_dependencies
    for name, expected in notification_dependencies().items():
        saved_load_pin(pins, name, expected)
    from civ6_host.runtime.xp1_absent_event_families import source_dependencies as absent_event_dependencies
    image = getattr(captured, 'execution_image', None)
    for name, expected in absent_event_dependencies(execution_image=image).items():
        saved_load_pin(pins, name, expected)
    if postload160:
        from civ6_host.runtime.xp1_postload_candidate import source_dependencies as post160_dependencies
        for name, expected in post160_dependencies().items():
            saved_load_pin(pins, name, expected)
    if publish_cache:
        from civ6_host.runtime.xp1_cache_publication import source_dependencies as publication_dependencies
        for name, expected in publication_dependencies().items():
            saved_load_pin(pins, name, expected)
    if close_loaded:
        from civ6_host.runtime.a0_district_removed import source_dependencies as district_dependencies
        for name, expected in district_dependencies().items():
            saved_load_pin(pins, name, expected)
        from civ6_host.runtime.xp1_loaded_lifetime import source_dependencies as lifetime_dependencies
        for name, expected in lifetime_dependencies().items():
            saved_load_pin(pins, name, expected)
    if observe_player:
        from civ6_host.runtime.xp1_ui_binding import source_dependencies as ui_dependencies
        for name,expected in ui_dependencies().items():saved_load_pin(pins,name,expected)
    if unit_commands:
        from civ6_host.runtime.action_transport_profiles import source_dependencies as transport_dependencies
        from civ6_host.runtime.unit_operation_ui_profile import source_dependencies as unit_dependencies
        from civ6_host.runtime.xp1_log_event_profile import source_dependencies as event_dependencies
        from civ6_host.runtime.found_unit_event_profiles import source_dependencies as found_event_dependencies
        from civ6_host.runtime.foundation_event_profile import source_dependencies as foundation_dependencies
        from civ6_host.runtime.city_scalar_event_profiles import source_dependencies as city_scalar_dependencies
        from civ6_host.runtime.xp1_private_notification_profile import source_dependencies as private_dependencies
        from civ6_host.runtime.turn_unit_event_profile import source_dependencies as turn_unit_dependencies
        from civ6_host.runtime.xp1_turn_profile import source_dependencies as turn_dependencies
        from civ6_host.runtime.xp1_host_thread_gate import source_dependencies as thread_dependencies
        from civ6_host.runtime.xp1_host_slot78 import source_dependencies as slot78_dependencies
        from civ6_host.runtime.placement_event_profile import source_dependencies as placement_dependencies
        from civ6_host.runtime.combat_event_profile import source_dependencies as combat_dependencies
        from civ6_host.runtime.improvement_change_profile import source_dependencies as improvement_change_dependencies
        from civ6_host.runtime.placement_inventory_profile import source_dependencies as inventory_dependencies
        from civ6_host.runtime.xp1_unit_attack_profile import source_dependencies as attack_dependencies
        from civ6_host.runtime.district_damage_profile import source_dependencies as district_damage_dependencies
        for dependencies in (transport_dependencies(),unit_dependencies(),event_dependencies(),found_event_dependencies(),foundation_dependencies(),city_scalar_dependencies(),private_dependencies(),turn_unit_dependencies(),turn_dependencies(),thread_dependencies(),slot78_dependencies(),placement_dependencies(),combat_dependencies(),improvement_change_dependencies(),inventory_dependencies(),attack_dependencies(),district_damage_dependencies()):
            if image is not None:
                dependencies = materialize_xp1_session_pins(dependencies, image)
            for name,expected in dependencies.items():saved_load_pin(pins,name,expected)
        from .execution_images import _XP1_PROFILE
        if image is _XP1_PROFILE:
            from .control_input_source import reactivation_source_pins
            for name,expected in reactivation_source_pins().items():
                saved_load_pin(pins,name,expected)
    saved_load_pin(pins, package['path'], package['sha256'])
    if image is None:
        return pins, saved_load_build_pins(pins, ui=observe_player)
    from .execution_images import source_dependencies as image_dependencies
    for path, expected in image_dependencies(image).items():
        saved_load_pin(pins, path, expected)
    from .native.native_app_ownership import CURRENT_XP2_INVENTORY_PATH, CURRENT_XP2_INVENTORY_SHA256
    inventory = saved_load_pin(pins, resource_root()/CURRENT_XP2_INVENTORY_PATH,
                              CURRENT_XP2_INVENTORY_SHA256)
    for row in json.loads(inventory.read_bytes())['current_inventory']:
        private = row.get('private_copy')
        if private is not None:
            saved_load_pin(pins, resource_root()/private['path'], private['sha256'])
    return pins, saved_load_build_pins(pins, ui=observe_player, official_bundle=captured.reference,
                                      execution_image=image)


def command_source_dependencies(core_sha256, *, execution_image=None):
    """Initial saved action graph only; later XP1 families retain their own joins."""
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown saved command source engine')
    if execution_image is not None and core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires the XP2 command source ABI')
    execution_options = ({'execution_image': execution_image}
                         if execution_image is not None else {})
    from importlib import import_module
    references = {}

    def collect(dependencies):
        for path, expected in dependencies.items():
            if references.setdefault(path, expected) != expected:
                raise ValueError('Conflicting saved command source pin: '+str(path))

    for name in ('action_transport_profiles','unit_operation_ui_profile',
            'xp1_log_event_profile','found_unit_event_profiles','foundation_event_profile',
            'city_scalar_event_profiles','xp1_private_notification_profile',
            'turn_unit_event_profile','xp1_turn_profile','xp1_host_thread_gate','xp1_host_slot78',
            'xp1_absent_event_families','xp2_history_event_profile','xp2_turn_event_profile'):
        module=import_module('civ6_host.runtime.'+name)
        options = ({'execution_image': execution_image}
                   if execution_image is not None and name in
                   ('action_transport_profiles', 'unit_operation_ui_profile',
                    'xp1_log_event_profile', 'found_unit_event_profiles',
                    'foundation_event_profile', 'xp1_absent_event_families',
                    'xp2_history_event_profile', 'xp2_turn_event_profile',
                    'turn_unit_event_profile', 'xp1_turn_profile',
                    'xp1_host_thread_gate', 'xp1_host_slot78') else {})
        collect(module.source_dependencies(core_sha256=core_sha256, **options))
    if core_sha256==XP2_CORE_SHA256:
        from .xp1_unit_attack_profile import source_dependencies as attack_dependencies
        collect(attack_dependencies(core_sha256=core_sha256, **execution_options))
        from .xp2_natural_wonder_source import source_dependencies as wonder_dependencies
        collect(wonder_dependencies())
        from .xp2_world_unit_event_source import source_dependencies as input_event_dependencies
        collect(input_event_dependencies(**execution_options))
        from .xp2_production_queue_event_source import source_dependencies as queue_event_dependencies
        collect(queue_event_dependencies(**execution_options))
        from .xp2_placement_event_source import source_dependencies as placement_event_dependencies
        collect(placement_event_dependencies(**execution_options))
        from .xp2_host_slot20_source import source_dependencies as achievement_dependencies
        collect(achievement_dependencies(**execution_options))
        from .improvement_change_profile import source_dependencies as improvement_dependencies
        collect(improvement_dependencies(core_sha256=core_sha256, **execution_options))
        from .xp2_feature_reveal_source import source_dependencies as feature_dependencies
        collect(feature_dependencies())
        if execution_image is not None:
            from .control_input_source import reactivation_source_pins
            collect(reactivation_source_pins(execution_image))
            from .xp2_congress_presentation import source_dependencies as congress_dependencies
            collect(congress_dependencies())
            from .xp2_wmd_fallout_source import source_dependencies as fallout_dependencies
            collect(fallout_dependencies())
            from .xp2_congress_notice_source import source_dependencies as congress_notice_dependencies
            collect(congress_notice_dependencies())
        from .district_damage_profile import source_dependencies as district_dependencies
        collect(district_dependencies(core_sha256=core_sha256, **execution_options))
        from .combat_event_profile import source_dependencies as combat_dependencies
        collect(combat_dependencies(core_sha256=core_sha256, **execution_options))
    pins = {}
    for path, expected in references.items():
        saved_load_pin(pins, path, expected)
    return pins


def _write_once(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True, default=str) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
    return {'path':str(path),'bytes':len(data),'sha256':digest(data)}


def prepare_private_fixture(run, captured, pins):
    """Use the existing DB copier and one private ICU copy per new process."""
    from .native.native_probe import prepare_init_fixture_copies
    fixture_source = run/'source-fixture.json'
    _write_once(fixture_source, captured.fixture)
    isolation = prepare_init_fixture_copies(fixture_source, 1, isolation_root=run)
    private = isolation['workers'][0]
    fixture = Path(private['manifest_path']).resolve()
    saved_load_private_icu(fixture, pins, private)
    saved_load_pin(pins, fixture_source)
    saved_load_pin(pins, fixture, private['manifest_sha256'])
    for row in private['databases'].values():
        saved_load_pin(pins, row['source_path'], row['sha256'])
        saved_load_pin(pins, row['copy_path'], row['sha256'])
    return fixture, isolation

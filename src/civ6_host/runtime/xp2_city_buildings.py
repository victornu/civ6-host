"""Own-city building completion and pillage for pinned XP2 LAN captures."""

from hashlib import sha256
from pathlib import Path

from . import xp1_city_buildings, xp2_bbg_inputs, xp2_bundle_inputs, xp2_great_works_inventory
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .core_script_services import check_bound
from .execution_images import _PROFILE
from .native.native_script_runtime import NativeScriptRuntime
from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_services import SavedLoadServices


SOURCE = ('evidence/host-xp2-city-building-panel-binding-scout.json',
          '16ecc2a14f84c356ff53266c33926469060d2c8d480f8a17227609ffb80bdf3b')
BBG_SOURCE = ('evidence/host-xp2-bbg-city-building-panel-source.json',
              'f7896ab04569d5f23f5c32a2ee3935325944e6073b57fe5f983ad63034d3454c')
BBG_GREAT_WORK_SOURCE = ('evidence/host-xp2-bbg-great-work-profile-source.json',
                         '769d5f2a4dcc4936cf8175330911b2147189d95875c925c00d86723f29e8291d')


def supports(reference, image):
    return image is _PROFILE and reference in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE)


def verify_source():
    proof = _source(SOURCE)
    comparison = proof['xp1_reference']
    if (proof['schema'] != 'civ6-host.xp2-city-building-panel-binding-scout.v1'
            or (proof['execution_image'], proof['engine_sha256']) != (_PROFILE.id, _PROFILE.image_sha256)
            or (comparison['path'], comparison['sha256']) != xp1_city_buildings.SOURCE
            or set(proof['bindings']) != set(xp1_city_buildings._CALLBACKS)
            or proof['static_only'] is not True or proof['native_execution'] is not False):
        raise ValueError('Gathering Storm city building panel source differs')
    return proof


def source_dependencies(image, *, reference):
    from . import xp2_great_work_commands
    from .native import native_player_operation_request

    if not supports(reference, image):
        raise ValueError('Gathering Storm city buildings require an admitted capture and image')
    proof = verify_source()
    root = resource_root()
    steam = Path(image.path).parents[4]
    pins = [(root / SOURCE[0], SOURCE[1]), (Path(image.path), image.image_sha256),
            (root / reference[0], reference[1])]
    comparison = proof['xp1_reference']
    pins.append((root / comparison['path'], comparison['sha256']))
    pins.extend((steam / path, row['sha256']) for path, row in proof['ui_files'].items())
    pins.extend((Path(path), digest) for path, digest in xp2_great_works_inventory.dependencies(image).items())
    xp2_great_works_inventory.theming_spans(image)
    theme = xp2_great_works_inventory.THEME_SOURCE
    pins.append((root / theme[0], theme[1]))
    for module in (xp2_great_works_inventory, xp2_great_work_commands, native_player_operation_request):
        source = Path(module.__file__)
        pins.append((source, sha256(source.read_bytes()).hexdigest()))
    if reference == xp2_bundle_inputs.REFERENCE:
        capture = proof['prepared_stock_capture']
        pins.append((root / capture['path'], capture['sha256']))
    else:
        bbg = _source(BBG_SOURCE)
        capture, binding = bbg['capture'], bbg['binding_source']
        if (bbg['schema'] != 'civ6-host.xp2-bbg-city-building-panel-source.v1'
                or (capture['path'], capture['sha256']) != reference
                or (binding['path'], binding['sha256']) != SOURCE
                or (bbg['execution_image'], bbg['engine_sha256']) != (image.id, image.image_sha256)
                or (bbg['mod_id'], bbg['mod_version']) != (xp2_bbg_inputs.MOD_ID, '70501')
                or bbg['no_city_buildings_panel_or_helper_replacement'] is not True
                or bbg['native_execution'] is not False):
            raise ValueError('BBG city building panel source differs')
        pins.append((root / BBG_SOURCE[0], BBG_SOURCE[1]))
        pins.extend((root / row['path'], row['sha256'])
                    for row in (bbg['bbg_modinfo'], bbg['gameplay_scripts'], *bbg['additional_ui']))
        works = _source(BBG_GREAT_WORK_SOURCE)
        files = works['files']
        declared = works['capture']
        if (works['schema'] != 'civ6-host.xp2-bbg-great-work-profile.source.v1'
                or (declared['path'], declared['sha256']) != reference
                or (works['image_id'], works['image_sha256']) != (image.id, image.image_sha256)
                or (works['mod_id'], works['mod_version']) != (bbg['mod_id'], bbg['mod_version'])
                or works['modinfo'] != bbg['bbg_modinfo'] or files['script_manifest'] != bbg['gameplay_scripts']
                or works['no_panel_or_capability_override'] is not True
                or works['no_move_script_hook_found'] is not True):
            raise ValueError('BBG Great Work profile source differs')
        pins.append((root / BBG_GREAT_WORK_SOURCE[0], BBG_GREAT_WORK_SOURCE[1]))
        pins.extend((root / row['path'], row['sha256']) for row in (
            files['bbg_gameplay'], files['cv_rule'], files['notification_source'], *files['script_copies']))
    dependencies = {str(resolve_path(path).resolve(strict=True)): digest for path, digest in pins}
    verify_pinned_files(dependencies)
    return dependencies


def verify_live(base, read):
    proof = verify_source()
    spans = [row['body']['xp2'] for row in proof['native_bodies'].values()]
    for row in proof['bindings'].values():
        spans.extend((row['callback']['xp2'], row['registration']))
    for span in spans:
        payload = read(base + span['rva'], span['bytes'])
        if (type(payload) is not bytes or len(payload) != span['bytes']
                or sha256(payload).hexdigest() != span['sha256']):
            raise ValueError(f"Live Gathering Storm city building binding differs at {span['rva']:#x}")


def read(saved, observation, *, borrowed=False, active=False):
    from .xp2_bbg_nested_events import BBGNestedScriptRuntime

    if borrowed:
        from .xp1_session_view import _borrowed_xp2_reference
        _borrowed_xp2_reference(saved, observation['player_id'])
    elif active:
        saved._check_active()
    else:
        saved._check_query()
    backend, prefix = saved.backend, saved.prefix
    core, runtime = backend.core, prefix.runtime
    reference = backend.captured_bundle.reference
    expected_runtime = BBGNestedScriptRuntime if reference == xp2_bbg_inputs.REFERENCE else NativeScriptRuntime
    if (getattr(saved, 'xp2_city_buildings', False) is not True
            or type(prefix) is not SavedLoadServices or type(runtime) is not expected_runtime
            or prefix.closed or prefix.quarantined or backend.prefix is not prefix
            or prefix.core is not core or prefix.context != backend.context
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or not supports(reference, getattr(core, '_civ6_host_execution_image', None))):
        raise ValueError('Gathering Storm city buildings require the exact saved Lua owner')
    lease = check_bound(runtime, backend.context, core)
    runtime.registry.validate(prefix.ui_child)
    lifetime = (core, prefix, runtime, prefix.ui_child, lease, reference)
    previous = getattr(saved, '_xp2_city_buildings_lifetime', None)
    if previous is None:
        verify_live(core._handle, backend.runtime.read)
        xp2_great_works_inventory.verify_theming_bindings(_PROFILE, core._handle, backend.runtime.read)
        saved._xp2_great_work_rules = xp2_great_works_inventory.rules(_PROFILE)
        saved._xp2_city_buildings_lifetime = lifetime
    elif previous != lifetime:
        raise ValueError('Gathering Storm city buildings require the same saved Lua lifetime')
    inventory = xp1_city_buildings.read_inventory(prefix, observation, b'@xp2_city_building_inventory')
    return xp2_great_works_inventory.read(prefix, observation, inventory, saved._xp2_great_work_rules)

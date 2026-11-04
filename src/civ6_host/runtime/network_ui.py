"""Captured LAN interface gates, separate from hotseat UI-profile admission.

This closes source-backed interface gates for the retained exact content.
It does not instantiate a graphical input router or qualify arbitrary mods,
modal listeners, waiting-phase controls, or all future interface actions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FORCED_ROUTE = ('work/forced-endturn924/ui-route.json',
                'a83eb79e0d70a4da8c04aa5b04507e9a346593c66a5d9d27517737511ee298a1')
BRIDGE_ID = '29c609c4-0bfc-4b2d-9cdb-2e59556f4560'
TUTORIAL_ID = '17462E0F-1EE1-4819-AAAA-052B5896B02A'
CITY_SOURCE = ('work/host-simultaneous/city-management/standard-lan-city-ui-source.json',
               '71a3a9546317b2fc6259e665dbb371384f4aba05297bf5320054b73341a15314')
CITY_GATES = ('city_focus', 'city_citizens', 'production_queue')
MAP_FEATURES = ('world_input', 'unit_order_cancel')
MAP_SOURCES = (
    ('work/host-simultaneous/map-actions/plot-purchase-ui-source.json',
     'c54e6118d5017eff295401049eb6e68c2c81d080fa55577e6d3f72e8ba4247d1'),
    ('work/host-simultaneous/map-actions/world-input-ui-source.json',
     '08d190f0762cc581f4e8d0d57e4fd297e2e456d511613056b0e10f6fa5ebdd40'),
)


def map_source_files():
    """Additional source-case pins; native route dependencies use their factories."""
    from .native.native_ui_availability import verify_source
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    source = verify_source()
    common = next(row for row in source['sources'] + source['additions']
                  if row['relative'] == 'Civ6Common.lua')
    game = Path(common['path']).parents[3]
    pins = {}
    for relative, digest in MAP_SOURCES:
        path = resource_root() / relative
        proof = _read(dict(path=str(path), sha256=digest))
        pins[str(path)] = digest
        # PlotInfo/CityPanel/capability sources complement the already pinned
        # movement functions, UnitPanel and shared tutorial source case.
        for row in proof.get('sources', []):
            if not row['path'].startswith('Base/'):
                continue
            path = resolve_path(game / row['path'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('LAN map interface source changed: ' + row['path'])
            pins[str(path)] = row['sha256']
    from .unit_panel_gate import source_files as unit_panel_sources
    pins.update(unit_panel_sources())
    return pins


def gold_capability(owner):
    """The shipped HasCapability predicate against this loaded native table."""
    p = owner.prefix
    raw = p.runtime.evaluate_text(p.ui_child,
        b"assert(GameInfo and GameInfo.GameCapabilities, 'Native capabilities unavailable'); "
        b"return GameInfo.GameCapabilities['CAPABILITY_GOLD'] ~= nil and '1' or '0'",
        b'@lan_gold_capability', capacity=4)
    if raw not in (b'0', b'1'):
        raise ValueError('Native gold capability readback is invalid')
    return raw == b'1'


def city_source_files():
    """Verify the source case once per session; return immutable closure pins.

    The proof's historical adapter hashes remain evidence, not executed-source
    pins. The supervisor separately pins the current extracted implementation.
    """
    from .native.native_ui_availability import verify_source
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    source = verify_source()
    common = next(row for row in source['sources'] + source['additions']
                  if row['relative'] == 'Civ6Common.lua')
    game = Path(common['path']).parents[3]
    proof_path = resource_root() / CITY_SOURCE[0]
    proof = _read(dict(path=str(proof_path), sha256=CITY_SOURCE[1]))
    pins = {str(proof_path): CITY_SOURCE[1]}
    for row in proof['sources']:
        relative = row['path']
        if relative.startswith('Base/'):
            path = game / relative
        elif relative.startswith('LAB/mod/'):
            path = resource_root() / relative[4:]
        else:
            continue
        path = resolve_path(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('LAN city interface source changed: ' + relative)
        pins[str(path)] = row['sha256']
    if len(pins) != 12:
        raise ValueError('LAN city source dependency set changed')
    from .city_growth import source_files as growth_sources
    pins.update(growth_sources())
    from .production_inputs import source_files as production_sources
    pins.update(production_sources())
    from .locale_text import source_files as locale_sources
    pins.update(locale_sources()[0])
    return pins


def validate_city_witness(ui):
    """Noncompact normal UI route, not a perpetual selected-city grant."""
    false = {'status': 'observed', 'value': False}
    for name in ('city_citizens', 'city_production', 'city_yields', 'production_queue_tab'):
        control = ui['controls'][name]
        if control['disabled'] != false or control['hidden'] != false:
            raise ValueError('LAN city interface control is unavailable or unknown: ' + name)


def _read(reference):
    from .resource_resolution import resolve_path
    path = resolve_path(Path(reference['path']))
    raw = path.read_bytes()
    if (len(raw) > 4 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != reference['sha256']
            or ('bytes' in reference and len(raw) != reference['bytes'])):
        raise ValueError('Captured LAN UI source/reference changed')
    return json.loads(raw)


def validate_tutorial_witness(ui, *, player_id, turn):
    from .native.native_ui_availability import validate_response
    validate_response(ui, dict(expected_player_id=player_id, expected_turn=turn))
    observed = {'status': 'observed', 'value': False}
    if (ui['tutorial']['active'] != observed
            or ui['tutorial']['manager_active'] != observed
            or ui['tutorial']['overlay_enabled'] != observed
            or ui['tutorial']['any_multiplayer'] != {'status':'observed', 'value':True}):
        raise ValueError('Captured LAN tutorial gate is active or unknown')


def admit(owner):
    from .capture_profiles import LAN_PROFILE
    from .native.native_ui_availability import verify_source
    from .native.official_saved_content import inspect_content
    from .provenance import resource_root
    if owner.inputs.profile is not LAN_PROFILE:
        raise ValueError('LAN UI gates cannot substitute a hotseat profile')
    # The owner has already joined this invocation to its exact save/bundle.
    manifest_ref = owner.network_reference['invocation']['manifest']
    manifest = _read(manifest_ref)
    if manifest['ui_availability']['observed_states_equal'] is not True:
        raise ValueError('Captured UI changed around the official save')
    content = inspect_content(owner.inputs.configuration)['identity']
    if content != {'ruleset':'RULESET_STANDARD',
                   'mods':[{'mod_id':BRIDGE_ID, 'version':'1'}]}:
        raise ValueError('LAN UI gate does not cover this content/mod combination')
    source = verify_source()
    common = next(row for row in source['sources'] + source['additions']
                  if row['relative'] == 'Civ6Common.lua')
    text = Path(common['path']).read_text(encoding='utf-8')
    if TUTORIAL_ID not in text or 'return Modding.IsModActive(TUTORIAL_UUID)' not in text:
        raise ValueError('Official tutorial predicate source changed')
    route = _read(dict(path=str(resource_root()/FORCED_ROUTE[0]), sha256=FORCED_ROUTE[1]))
    panel = route['source_files'][0]
    if hashlib.sha256(Path(panel['path']).read_bytes()).hexdigest() != panel['sha256']:
        raise ValueError('Official forced-turn handler source changed')
    receipts = []
    city_sources = city_source_files()
    map_sources = map_source_files()
    for name in ('ui-availability-before.json', 'ui-availability-after.json'):
        reference = manifest['artifacts'][name]
        value = _read(reference)
        if value['status'] != 'ok' or value['diagnostics']['completion'] != 'read_only_current_ui':
            raise ValueError('LAN UI witness was not a completed read')
        validate_tutorial_witness(value['diagnostics']['ui_availability'],
            player_id=owner.network_reference['state']['player_id'],
            turn=owner.network_reference['state']['turn'])
        validate_city_witness(value['diagnostics']['ui_availability'])
        receipts.append(dict(path=reference['path'], sha256=reference['sha256']))
    from .unit_panel_gate import SOURCE as UNIT_PANEL_SOURCE
    admission = dict(schema='civ6-host.lan-ui-gates.v4',
        configuration_sha256=hashlib.sha256(owner.inputs.configuration).hexdigest(),
        bundle_reference=tuple(owner.inputs.official_bundle),
        captured_tutorial_inactive=True, force_end_turn=True,
        unit_panel_source_sha256=UNIT_PANEL_SOURCE[1],
        unit_panel_route='source_bound_native_event_processing_guard_and_normal_own_unit_selection',
        source_sha256=FORCED_ROUTE[1], witnesses=receipts,
        gates={name: True for name in CITY_GATES},
        city_source_sha256=CITY_SOURCE[1], city_source_files=city_sources,
        map_source_sha256=[row[1] for row in MAP_SOURCES], map_source_files=map_sources,
        map_features={name: True for name in MAP_FEATURES}, gold_capability=gold_capability(owner),
        map_ui_route='explicit_normal_unit_selection_order_and_normal_city_purchase_lens',
        city_ui_route='select_owned_city_then_normal_selection_without_simulation_command',
        full_content_execution_qualified=False,
        scope='Retained standard Base LAN content with no tutorial; active human decision boundary only',
        graphical_input_routing_qualified=False, strategic_training_ready=False)
    owner.network_ui_admission = admission
    owner.emit('official_lan_ui_gate_admission', **admission)
    return admission


def _admission(owner):
    """Immutable per-loaded-content gate; native activity is checked separately."""
    from .capture_profiles import LAN_PROFILE
    admission = getattr(owner, 'network_ui_admission', None)
    if admission is None:
        return None
    if (owner.inputs.profile is not LAN_PROFILE
            or admission['schema'] not in ('civ6-host.lan-ui-gates.v1', 'civ6-host.lan-ui-gates.v2', 'civ6-host.lan-ui-gates.v3', 'civ6-host.lan-ui-gates.v4')
            or admission['configuration_sha256'] != hashlib.sha256(owner.inputs.configuration).hexdigest()
            or admission['bundle_reference'] != tuple(owner.inputs.official_bundle)):
        raise ValueError('LAN UI gate belongs to another loaded configuration')
    return admission


def force_available(owner):
    admission = _admission(owner)
    return (admission is not None and admission['force_end_turn'] is True
            and admission['captured_tutorial_inactive'] is True)


def gate_available(owner, name):
    """City adapters still revalidate actor, own city, state and native targets."""
    # Forced turn is composed by network_owner after the legacy catalogue.
    # Enabling its legacy Hotseat gate would invoke the wrong turn scheduler.
    if name == 'plot_purchase':
        admission = _admission(owner)
        return _map_admitted(admission) and admission['gold_capability'] is True
    if name not in CITY_GATES:
        return False
    admission = _admission(owner)
    if admission is None or admission['schema'] == 'civ6-host.lan-ui-gates.v1':
        return False
    if admission['city_source_sha256'] != CITY_SOURCE[1]:
        raise ValueError('LAN city source admission differs')
    return (admission['captured_tutorial_inactive'] is True
            and admission['gates'].get(name) is True)


def _map_admitted(admission):
    if admission is None or admission['schema'] not in ('civ6-host.lan-ui-gates.v3', 'civ6-host.lan-ui-gates.v4'):
        return False
    if admission['map_source_sha256'] != [row[1] for row in MAP_SOURCES]:
        raise ValueError('LAN map source admission differs')
    return admission['captured_tutorial_inactive'] is True


def feature_enabled(owner, name):
    """Keep legacy opt-ins; LAN requires a separate source-admitted feature."""
    from .capture_profiles import LAN_PROFILE
    if name not in MAP_FEATURES:
        raise ValueError('Unknown map action feature: ' + str(name))
    diagnostic = getattr(owner, name + '_diagnostic', False)
    if type(diagnostic) is not bool:
        raise ValueError('Exact action-feature diagnostic flag required')
    if diagnostic:
        return True
    if getattr(getattr(owner, 'inputs', None), 'profile', None) is not LAN_PROFILE:
        return False
    admission = _admission(owner)
    return (_map_admitted(admission) and admission['map_features'].get(name) is True)

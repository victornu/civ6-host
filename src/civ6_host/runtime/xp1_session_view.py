"""Fresh player/session reads on the retained captured expansion owners.

This adapter exposes qualified families without fabricating absent information
groups. It neither schedules players nor changes the native readiness flags.
The parent adapter admits the exact captured bundle and attaches its reference.
"""
from copy import deepcopy

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .xp1_bundle_inputs import XP1_LAN_PROFILE
from .xp1_saved_load import REFERENCE


def _reference(saved, player_id):
    """Check the retained admission, not reconstruct or replay the game state."""
    b = saved.backend
    bundle = b.captured_bundle
    ref = saved.network_reference
    from .lan_load import _LAN_MODE, _SIMULTANEOUS_PHASE
    from .captured_session_profile import for_backend
    selected = for_backend(b)
    if (saved.inputs.profile is not selected.candidate.profile or bundle.inputs is not saved.inputs
            or saved.inputs.official_bundle != selected.candidate.reference
            or ref.get('capture_manifest_sha256') != selected.candidate.reference[1]):
        raise ValueError('XP1 session reference is not joined to its exact admitted capture')
    state = ref['state']
    if (type(state.get('game_mode_u32')) is not int or state['game_mode_u32'] != _LAN_MODE
            or type(state.get('turn_phase_u32')) is not int
            or state['turn_phase_u32'] != _SIMULTANEOUS_PHASE):
        raise ValueError('XP1 session reference has an unqualified network mode')
    from .network_owner import roster
    ids = roster(ref['major_player_ids'])
    humans = ref['human_player_ids']
    if (type(humans) is not tuple or not humans
            or any(type(pid) is not int or pid not in ids for pid in humans)
            or len(set(humans)) != len(humans)
            or type(player_id) is not int or player_id not in humans
            or type(state.get('player_id')) is not int or state['player_id'] != player_id
            or type(state.get('observer_id')) is not int or state['observer_id'] != player_id):
        raise ValueError('XP1 view requires the actual captured local human perspective')
    return ref, ids


def _borrowed_xp2_reference(saved, player_id):
    saved._check_active()
    if saved.backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Borrowed human reads require Gathering Storm')
    primary = saved.network_reference['state']['player_id']
    ref, ids = _reference(saved, primary)
    if type(player_id) is not int or player_id == primary or player_id not in ref['human_player_ids']:
        raise ValueError('Borrowed human reads require a captured secondary seat')
    return ref, ids


def read_founders(prefix, player_id, turn, *, core_sha256):
    from .native.native_unit_actions import found_city_catalog_source, parse_founders
    source = found_city_catalog_source(player_id, turn, core_sha256=core_sha256)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@native_found_city_catalog',
                                       capacity=131072)
    return parse_founders(raw, player_id, turn)


def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    execution_options = {}
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
        if execution_image.reference_core_sha256 != core_sha256:
            raise ValueError('Session view execution image does not match its source ABI')
        if core_sha256 == XP2_CORE_SHA256:
            execution_options = {'execution_image': execution_image}
    from .captured_session_profile import select
    from .xp1_status_profiles import source_dependencies as status_dependencies
    from .unit_operation_ui_profile import source_dependencies as unit_dependencies
    from .xp1_research_profile import source_dependencies as research_dependencies
    from .xp1_production_profile import source_dependencies as production_dependencies
    from .xp1_turn_ui_profile import source_dependencies as turn_ui_dependencies
    selected=select(core_sha256)
    groups=[status_dependencies(core_sha256=core_sha256,**execution_options),
            unit_dependencies(core_sha256=core_sha256,**execution_options),
            research_dependencies(core_sha256=core_sha256,**execution_options),
            production_dependencies(core_sha256=core_sha256,**execution_options),
            turn_ui_dependencies(core_sha256=core_sha256,**execution_options)]
    from .xp1_world_input_profile import source_dependencies as world_dependencies
    from .xp1_unit_orders_profile import source_dependencies as order_dependencies
    from .xp1_production_queue_profile import source_dependencies as queue_dependencies
    from .xp1_production_placement_profile import source_dependencies as placement_dependencies
    from .placement_inventory_profile import source_dependencies as inventory_dependencies
    from .execution_images import _PROFILE
    inventory_options = ({'include_pillage': True}
                         if core_sha256 == XP2_CORE_SHA256 and execution_image is _PROFILE else {})
    groups.extend([world_dependencies(core_sha256,**execution_options),
                   order_dependencies(core_sha256,**execution_options),
                   queue_dependencies(core_sha256,**execution_options),
                   placement_dependencies(core_sha256,**execution_options),
                   inventory_dependencies(core_sha256,**execution_options,**inventory_options)])
    if selected.candidate.family in ('xp1-lan','xp2-lan'):
        from .xp1_unit_attack_profile import source_dependencies as attack_dependencies
        groups.append(attack_dependencies(core_sha256,**execution_options))
    if core_sha256 == XP2_CORE_SHA256:
        from pathlib import Path
        from .native import native_city_range_attack as city_range, native_combat_actions as combat
        from .native import native_saved_city_shot, native_saved_district_shot, native_saved_unit_work
        from .native import native_saved_city_targets as city_targets
        from .native.native_source_cache import load_pinned_json
        from .resource_resolution import resolve_path
        from .unit_work_info import xp2_source_dependencies as work_info_dependencies
        from .production_inputs import source_files as production_display_dependencies
        from .locale_text import source_files as length_locale_dependencies
        from .xp2_plot_purchases import source_dependencies as plot_purchase_dependencies
        from .xp2_promotions import source_dependencies as promotion_dependencies
        from .xp2_unit_upgrades import source_dependencies as upgrade_dependencies
        from .xp2_strategic_resources import source_dependencies as resource_dependencies
        for codec in (native_saved_city_shot, native_saved_district_shot):
            proof = codec.verify_source()
            groups.append({str(codec.PROOF.resolve()): codec.PROOF_SHA,
                           **{str(resolve_path(Path(row['path'])).resolve()): row['sha256']
                              for row in proof['official_ui'].values()}})
        # Both shot codecs also validate the shared route and Base city-target
        # sources. Those static references are dependencies, not XP2 admission.
        groups.extend({str(resolve_path(path).resolve()): digest} for path, digest in (
            (city_range.RANGE_ROUTE, city_range.RANGE_ROUTE_SHA256),
            (city_range.NOTIFICATION, city_range.NOTIFICATION_SHA256),
            (city_range.PLAYER_OBSERVATION, city_range.PLAYER_OBSERVATION_SHA256),
            (combat._PROOF_PATH, combat._PROOF_SHA256),
            (city_targets.SOURCE, city_targets.SOURCE_SHA),
        ))
        target_proof = load_pinned_json(city_targets.SOURCE, city_targets.SOURCE_SHA)
        groups.extend({str(resolve_path(Path(row['path'])).resolve()): row['sha256']}
                      for row in target_proof['installed_sources'].values())
        groups.append({str((native_saved_unit_work.ROOT / 'work/unit-work932/source.json').resolve()):
                       native_saved_unit_work.SOURCE_SHA})
        groups.append(work_info_dependencies(**execution_options))
        groups.append(production_display_dependencies(xp2=True,**execution_options))
        groups.append(length_locale_dependencies(**execution_options)[0])
        groups.append(plot_purchase_dependencies(**execution_options))
        groups.append(promotion_dependencies(**execution_options))
        groups.append(upgrade_dependencies(**execution_options))
        groups.append(resource_dependencies(**execution_options))
        from .xp2_envoys import source_dependencies as envoy_dependencies
        groups.append(envoy_dependencies(**execution_options))
        if execution_image is not None:
            from .xp2_statement_source import source_dependencies as statement_dependencies
            from .xp2_diplomacy_display_source import source_dependencies as dialogue_dependencies
            groups.append(statement_dependencies(**execution_options))
            groups.append(dialogue_dependencies(**execution_options))
    if core_sha256 == XP1_CORE_SHA256:
        from .execution_images import _XP1_PROFILE
        if execution_image is _XP1_PROFILE:
            from .xp1_production_info import source_dependencies as production_info_dependencies
            groups.append(production_info_dependencies(execution_image))
    result={}
    for group in groups:
        for path,digest in group.items():
            if path in result and result[path]!=digest:
                raise ValueError('Captured session source dependency identity conflicts')
            result[path]=digest
    if execution_image is not None:
        if core_sha256 == XP1_CORE_SHA256:
            from .xp1_session_inputs import materialize_xp1_session_pins
            result = materialize_xp1_session_pins(result, execution_image)
        else:
            from .runtime_source_dependencies import materialize_runtime_source_pins
            result = materialize_runtime_source_pins(result, execution_image=execution_image)
    if core_sha256 == XP1_CORE_SHA256 and execution_image is _XP1_PROFILE:
        # Merge exact installed pins after the historical image compatibility projection.
        from .xp1_city_religion import source_dependencies as city_religion_dependencies
        for path,digest in city_religion_dependencies(execution_image).items():
            if path in result and result[path] != digest:
                raise ValueError('Installed city religion source dependency identity conflicts')
            result[path] = digest
    return result


def _prepare(saved, player_id, *, allow_diplomacy=False):
    from .xp1_saved_load_owner import SavedLoadOwner
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP1 session view requires the retained SavedLoadOwner')
    saved._check('commands', requested='unit_commands_candidate')
    saved.continuation.check(active=False)
    if type(allow_diplomacy) is not bool:
        raise ValueError('Exact saved diplomacy read mode required')
    if allow_diplomacy:
        from .xp2_diplomacy import _SavedDialogueContext
        context = getattr(saved, '_xp2_diplomacy', None)
        if type(context) is not _SavedDialogueContext or context.saved is not saved:
            raise RuntimeError('Diplomacy read mode requires its validated retained context')
        context.validate(saved.backend)
    ref, ids = _reference(saved, player_id)
    b = saved.backend
    from .xp1_status_profiles import bind_owner
    bind_owner(b, b.core, b.runtime.read)
    saved.continuation.transport.require_empty_native_queue()
    b.control(empty=True, allow_diplomacy=allow_diplomacy)
    return ref, ids


def _read_saved_diplomacy(saved, player_id, sequence, *, actions_closed=False):
    """Read a retained XP2 modal without opening ordinary action queries."""
    from .xp2_diplomacy import read as read_diplomacy
    from .network_timer import read as read_timer
    from civ6_host.contracts import network_turn as contract
    from .native.native_episode_identity import require_episode

    context = getattr(saved, '_xp2_diplomacy', None)
    if context is None or context.saved is not saved:
        raise RuntimeError('XP2 diplomacy view lost its retained saved owner')
    context.validate(saved.backend)
    observation, catalogue = read_diplomacy(saved, sequence)
    if (catalogue.get('player_id') != player_id
            or catalogue.get('turn') != saved.continuation.observation.get('turn')
            or catalogue.get('schema') != 'civ6rl.diplomacy_decisions948.v1'):
        raise RuntimeError('Retained XP2 dialogue belongs to another actor or boundary')
    ref, ids = _prepare(saved, player_id, allow_diplomacy=True)
    b, p = saved.backend, saved.prefix
    core_sha256 = b.load_abi.core_sha256
    with saved._attempt():
        session, activity = _read_state(saved, player_id, ref, ids)
        rows = {row['player_id']: row for row in activity['rows']}
        actual_observation = _observe_activity(saved, player_id, activity)
        if (actual_observation != observation
                or activity['turn'] != catalogue['turn']):
            raise RuntimeError('Retained XP2 dialogue read crossed its native observation')
        row = rows[player_id]
        controls = dict(schema=contract.TURN_CONTROLS_SCHEMA, player_id=player_id,
            turn=activity['turn'], active=row['active'],
            active_complete=row['active_complete'], can_unready=row['can_unready'],
            timer_elapsed=read_timer(b, core_sha256=core_sha256))
        identity = require_episode(p)
        from civ6_host.contracts.diplomacy_decisions import build
        decisions=build(identity,sequence,observation,controls,catalogue,
            public_display=context.public_display,
            display_source_sha256=context.public_display_source_sha256,
            actions_closed=actions_closed)
        contract.validate_catalogue(decisions, identity, sequence, activity['turn'],
            player_id=player_id, actions_closed=actions_closed,
            observation=observation)
        saved.continuation.transport.require_empty_native_queue()
        b.control(empty=True, allow_diplomacy=True)
        saved.continuation.check(active=False)
    context.validate(b)
    saved._check('commands', requested='unit_commands_candidate')
    return session, observation, decisions


def _read_state(saved, player_id, ref, ids, *, inactive_player_id=None):
    from .lan_load import human_status_readback_source, _parse_humans
    from .network_turns import read_activity
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.game_child, human_status_readback_source(ids),
                                  b'@lan_session_humans', capacity=1024)
    humans = _parse_humans(raw, ids)
    if humans != ref['human_player_ids']:
        raise RuntimeError('XP1 native human ownership differs from admitted capture')
    activity = read_activity(saved, core_sha256=saved.backend.load_abi.core_sha256,
                             inactive_player_id=inactive_player_id)
    expected_observer = player_id if inactive_player_id is None else None
    if activity['local_player_id'] != player_id or activity['observer_id'] != expected_observer:
        raise RuntimeError('XP1 native local identity or observer changed')
    session = dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS',
        turn=activity['turn'], local_player_id=activity['local_player_id'],
        human_player_ids=list(humans), active_human_player_ids=[
            item['player_id'] for item in activity['rows']
            if item['active'] and item['player_id'] in humans])
    return session, activity


def state(saved, *, inactive_player_id=None):
    """Read current native session identity/activity before any terminal teardown."""
    from .xp1_saved_load_owner import SavedLoadOwner
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP1 session state requires the retained SavedLoadOwner')
    saved._check('commands', requested='unit_commands_candidate')
    player_id = saved.network_reference['state']['player_id']
    if inactive_player_id is not None and (type(inactive_player_id) is not int
                                           or inactive_player_id != player_id):
        raise ValueError('Inactive LAN status requires the captured local human')
    ref, ids = _prepare(saved, player_id)
    with saved._attempt():
        session, _ = _read_state(saved, player_id, ref, ids,
                                 inactive_player_id=inactive_player_id)
        saved.continuation.transport.require_empty_native_queue()
        saved.backend.control(empty=True)
        saved.continuation.check(active=False)
    saved._check('commands', requested='unit_commands_candidate')
    return session


def _turn_gates(saved, player_id):
    from .xp1_turn_ui_profile import read as read_turn_ui
    try:
        return read_turn_ui(saved, player_id, saved.continuation.observation['turn'])
    except BaseException:
        saved._poison()
        raise


def _observe_activity(saved, player_id, activity):
    from .native.native_player_observation import observe_player
    p = saved.prefix
    observation = observe_player(p.runtime, p.ui_child, player_id)
    retained = saved.continuation.observation
    if (observation['turn'] != activity['turn']
            or (observation['width'], observation['height']) != (retained['width'], retained['height'])):
        raise RuntimeError('XP1 session and player observation cross different boundaries')
    return observation


def _read_command_permissions(saved, player_id, turn, sequence):
    """Read the native command gates separately from the real turn activity.

    _prepare and _turn_gates bind the selected status/turn UI profiles before
    this query. A false gate does not change player activity or close Congress.
    """
    from .native.native_saved_unit_orders import uint
    for value, name, maximum in ((player_id, 'player', 63), (turn, 'turn', 0xffffffff),
                                  (sequence, 'sequence', 0xffffffff)):
        uint(value, name, maximum)
    p = saved.prefix
    source = (f'local pid,expectedTurn={player_id},{turn}\n'.encode() + b"""
local function same()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
  Game.GetCurrentGameTurn()==expectedTurn,'command permission perspective changed')
end
same()
local strategic=Game.IsAllowStrategicCommands(pid)
local tactical=Game.IsAllowTacticalCommands(pid)
assert(type(strategic)=='boolean' and type(tactical)=='boolean','native command permissions are not Boolean')
same()
return (strategic and '1' or '0')..','..(tactical and '1' or '0')
""")
    raw = p.runtime.evaluate_text(p.ui_child, source, b'@native_command_permissions', capacity=32)
    if raw not in (b'0,0', b'0,1', b'1,0', b'1,1'):
        raise ValueError('Malformed native command permissions')
    return dict(player_id=player_id, turn=turn, sequence=sequence,
                allow_strategic=raw[0:1] == b'1', allow_tactical=raw[2:3] == b'1')


def read_turn_preflight(saved, player_id, kind):
    """Revalidate an XP2 turn request without querying unrelated action families."""
    ref, ids = _prepare(saved, player_id)
    b = saved.backend
    if (b.load_abi.core_sha256 != XP2_CORE_SHA256
            or kind not in ('end_turn', 'force_end_turn', 'unready_turn')):
        raise ValueError('Unqualified XP2 turn preflight')
    gates = _turn_gates(saved, player_id)
    with saved._attempt():
        _, activity = _read_state(saved, player_id, ref, ids)
        observation = _observe_activity(saved, player_id, activity)
        available = gates['turn_availability'][kind] is True
        saved.continuation.transport.require_empty_native_queue()
        b.control(empty=True)
        saved.continuation.check(active=False)
    saved._check('commands', requested='unit_commands_candidate')
    return observation, available


def _add_dedications(saved, observation, decisions, *, actions_closed, previous_schema, target_schema):
    from civ6_host.contracts import dedications, network_turn
    from .xp2_dedications import catalogue

    if decisions['schema'] != previous_schema:
        raise ValueError('Dedication query requires its expansion capability boundary')
    unavailable = network_turn.family_query_unavailable(
        decisions, dedications.KIND, actions_closed=actions_closed)
    state = None if unavailable else catalogue(saved, observation)
    rows = [dict(candidate_id=network_turn.digest(action), action=action)
            for action in dedications.candidates(state)]
    decisions['candidates'].extend(rows)
    decisions['schema'] = target_schema
    decisions['dedications'] = state
    decisions['families'][dedications.KIND] = (
        dict(status='unqualified', reason='session_closed' if actions_closed else
             'native_dedication_acting_boundary_unavailable') if unavailable else
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows]))


def _add_trade(decisions, trade_view, *, actions_closed):
    from civ6_host.contracts import network_turn, trade

    decisions.update(trade_view)
    for kind, field, choices in (
            ('make_trade_route', 'trade_routes', trade.route_actions),
            ('change_trade_origin', 'trade_origins', trade.origin_actions)):
        value = trade_view[field]
        if value is None:
            reason = 'session_closed' if actions_closed else 'native_trade_acting_boundary_unavailable'
            decisions['families'][kind] = dict(status='unqualified', reason=reason)
            continue
        rows = [dict(candidate_id=network_turn.digest(action), action=action)
                for action in choices(value)]
        decisions['candidates'].extend(rows)
        decisions['families'][kind] = dict(
            status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])


def _add_xp1_plot_purchases(saved, observation, decisions, *, acting, actions_closed):
    from civ6_host.contracts import network_turn, plot_purchases
    from .xp1_plot_purchases import catalogue

    decisions['schema'] = network_turn.XP1_PLOT_PURCHASE_SCHEMA_BY_BASE[decisions['schema']]
    quotes = catalogue(saved, observation) if acting else None
    decisions['plot_purchases'] = quotes
    items = None
    has_items = getattr(saved, 'xp1_city_purchase', False) is True
    allow_faith = getattr(saved, 'xp1_faith_purchase', False) is True
    if has_items:
        from .xp1_city_purchases import catalogue as city_catalogue
        decisions['schema'] = network_turn.XP1_CITY_PURCHASE_SCHEMA_BY_BASE[decisions['schema']]
        if allow_faith:
            decisions['schema'] = network_turn.XP1_FAITH_PURCHASE_SCHEMA_BY_BASE[decisions['schema']]
        items = city_catalogue(saved, observation) if acting else None
        decisions['city_purchases'] = items
    if quotes is None:
        decisions['families']['purchase'] = dict(status='unqualified',
            reason='session_closed' if actions_closed else 'native_purchase_acting_boundary_unavailable')
        return
    rows = [dict(candidate_id=network_turn.digest(action), action=action)
            for action in plot_purchases.actions(quotes + (items or []))]
    decisions['candidates'].extend(rows)
    gaps = (plot_purchases.CITY_FAITH_GAPS if allow_faith else
            plot_purchases.CITY_GAPS if has_items else plot_purchases.GAPS)
    decisions['families']['purchase'] = dict(status='queried_partial',
        candidate_ids=[row['candidate_id'] for row in rows], unqualified=list(gaps))


def _add_promotions(saved, observation, decisions, read_promotions, *, acting, actions_closed):
    from civ6_host.contracts import network_turn

    saved.explicit_promotions = None
    state = read_promotions(saved, observation) if acting else None
    decisions['unit_promotions'] = state
    if state is None:
        decisions['families']['promote_unit'] = dict(status='unqualified',
            reason='session_closed' if actions_closed else 'native_promotion_acting_boundary_unavailable')
        return
    rows = [dict(candidate_id=network_turn.digest(action), action=action) for action in state['offers']]
    decisions['candidates'].extend(rows)
    decisions['families']['promote_unit'] = dict(status='queried_complete',
        candidate_ids=[row['candidate_id'] for row in rows])


def _add_upgrades(saved,observation,decisions,read_upgrades,*,acting,actions_closed):
    from civ6_host.contracts import network_turn, unit_upgrades

    state = read_upgrades(saved,observation) if acting else None
    decisions['unit_upgrades'] = state
    if state is None:
        decisions['families']['upgrade_unit'] = dict(status='unqualified',
            reason='session_closed' if actions_closed else 'native_upgrade_acting_boundary_unavailable')
        return
    rows = [dict(candidate_id=network_turn.digest(action),action=action) for action in unit_upgrades.actions(state)]
    decisions['candidates'].extend(rows)
    decisions['families']['upgrade_unit'] = dict(status='queried_complete',
        candidate_ids=[row['candidate_id'] for row in rows])


def _add_xp1_government_policies(saved, observation, decisions, *, acting, actions_closed):
    from civ6_host.contracts import capability_policies, government, network_turn
    from .xp2_government import read as read_government
    from .xp2_policies import read as read_policies

    policy_catalogue = read_policies(saved, observation) if acting else None
    government_catalogue = read_government(saved, observation) if acting else None
    for kind, catalogue, actions, gaps in (
            ('policies', policy_catalogue, capability_policies.actions(policy_catalogue),
                ('paid_policy_unlock', 'active_policy_relocation', 'unchanged_policy_confirmation')),
            ('government', government_catalogue, government.actions(government_catalogue),
                ('anarchy_transition',))):
        decisions[kind] = catalogue
        if catalogue is None:
            reason = 'session_closed' if actions_closed else 'native_' + kind + '_acting_boundary_unavailable'
            decisions['families'][kind] = dict(status='unqualified', reason=reason)
            continue
        rows = [dict(candidate_id=network_turn.digest(action), action=action) for action in actions]
        decisions['candidates'].extend(rows)
        decisions['families'][kind] = dict(status='queried_partial',
            candidate_ids=[row['candidate_id'] for row in rows], unqualified=list(gaps))


def _attach_installed_xp1_information(saved, observation, decisions):
    """Leave historical and other image profiles on their existing catalogue."""
    from .execution_images import _XP1_PROFILE
    from civ6_host.contracts import network_turn as contract
    backend = saved.backend
    if (backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or getattr(backend.core,'_civ6_host_execution_image',None) is not _XP1_PROFILE):
        return
    if decisions['schema'] in contract.XP1_PRODUCTION_INFO_SCHEMA_BY_BASE:
        from .xp1_production_info import attach as attach_production_info
        attach_production_info(saved, observation, decisions)
    if decisions['schema'] in contract.XP1_CITY_RELIGION_SCHEMA_BY_BASE:
        from .xp1_city_religion import attach as attach_city_religion
        attach_city_religion(saved, observation, decisions)


def _add_xp1_city_religion_details(saved, observation, decisions):
    from civ6_host.contracts import network_turn as contract
    from .xp1_city_religion import read_details
    if 'city_religion' not in decisions:
        return
    prior = decisions['city_religion']
    contract.add_xp1_city_religion_details(
        decisions,read_details(saved,observation,expected_majority=prior))


def _add_xp2_city_religion_details(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract
    from .xp1_city_religion import read_details
    if actions_closed:
        return
    if decisions['schema'] not in contract.XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE:
        raise ValueError('City religion requires its preceding Gathering Storm catalogue')
    # This own-city reader is valid while waiting and without strategic
    # command permission. It does not query action eligibility.
    contract.add_xp2_city_religion_details(decisions,read_details(saved,observation))


def _add_xp1_pantheon(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract
    from .xp1_pantheon import catalogue
    saved.explicit_pantheon = None
    # Close omits the entire captured-city/XP1 optional catalogue chain above.
    # Preserve that existing terminal contract; no action/query is available.
    if actions_closed and decisions['schema'] not in contract.XP1_PANTHEON_SCHEMA_BY_BASE:
        return
    unavailable = contract.family_query_unavailable(decisions, 'pantheon', actions_closed=actions_closed)
    state = None if unavailable else catalogue(saved, observation)
    contract.add_xp1_pantheon(decisions, state, actions_closed=actions_closed)


def _add_xp1_religion_beliefs(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religion_beliefs
    from .xp1_religion_beliefs import catalogue
    saved.explicit_religion_beliefs = None
    if actions_closed and decisions['schema'] not in contract.XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE:
        return
    unavailable=contract.family_query_unavailable(decisions,'add_belief',actions_closed=actions_closed)
    state=None
    if not unavailable:
        native=catalogue(saved,observation)
        pid,turn=observation['player_id'],observation['turn']
        state=dict(schema=religion_beliefs.SCHEMA,player_id=pid,turn=turn,
            own=religion_beliefs.project_snapshot(native['own'],pid,turn,observation=observation),
            beliefs=deepcopy(native['beliefs']))
    contract.add_xp1_religion_beliefs(decisions,state,actions_closed=actions_closed)


def _add_xp1_religion_founding(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religion_founding, religion_beliefs
    from .xp1_religion_founding import catalogue
    saved.explicit_religion_founding = None
    if actions_closed and decisions['schema'] not in contract.XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE:
        return
    unavailable=contract.family_query_unavailable(decisions,'found_religion',actions_closed=actions_closed)
    state=None
    if not unavailable:
        native=catalogue(saved,observation)
        pid,turn=observation['player_id'],observation['turn']
        state=dict(schema=religion_founding.SCHEMA,player_id=pid,turn=turn,
            own=religion_beliefs.project_snapshot(native['own'],pid,turn,observation=observation),
            foundation=deepcopy(native['foundation']))
    contract.add_xp1_religion_founding(decisions,state,actions_closed=actions_closed)


def _add_xp1_religion_custom_names(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religion_custom_names
    from .xp1_religion_custom_names import catalogue
    saved.explicit_religion_custom_names = None
    if actions_closed and decisions['schema'] not in contract.XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE:
        return
    unavailable = contract.family_query_unavailable(decisions, religion_custom_names.KIND,
                                                     actions_closed=actions_closed)
    state = None
    if not unavailable:
        native = catalogue(saved, observation)
        state = religion_custom_names.project(native, observation['player_id'], observation['turn'],
                                               observation=observation)
    contract.add_xp1_religion_custom_names(decisions, state, actions_closed=actions_closed)


def _add_xp1_great_person_activation(saved, observation, decisions, *, actions_closed=False, xp2=False):
    from civ6_host.contracts import network_turn as contract, great_person_activation
    from .xp1_great_person_activation import catalogue
    saved.explicit_great_person_activation = None
    schemas = (contract.XP2_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE if xp2
               else contract.XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE)
    if actions_closed and decisions['schema'] not in schemas:
        return
    unavailable = contract.family_query_unavailable(decisions,great_person_activation.KIND,
                                                     actions_closed=actions_closed)
    state = None
    if not unavailable:
        native = catalogue(saved,observation)
        state = great_person_activation.project(native,observation['player_id'],observation['turn'],
                                                  observation=observation)
    attach = contract.add_xp2_great_person_activation if xp2 else contract.add_xp1_great_person_activation
    attach(decisions,state,actions_closed=actions_closed)


def _add_xp1_religious_unit_operations(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religious_unit_operations
    from .xp1_religious_unit_operations import catalogue
    saved.explicit_religious_unit_operations = None
    if actions_closed and decisions['schema'] not in contract.XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE:
        return
    unavailable = any(contract.family_query_unavailable(decisions,kind,actions_closed=actions_closed)
                      for kind in religious_unit_operations.KINDS)
    state = None
    if not unavailable:
        native = catalogue(saved,observation)
        state = religious_unit_operations.project(native,observation['player_id'],observation['turn'],
                                                   observation=observation)
    contract.add_xp1_religious_unit_operations(decisions,state,actions_closed=actions_closed)


def _add_xp2_religious_unit_operations(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religious_unit_operations
    from .xp1_religious_unit_operations import catalogue
    saved.explicit_religious_unit_operations = None
    if actions_closed and decisions['schema'] not in contract.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE:
        return
    unavailable = any(contract.family_query_unavailable(decisions,kind,actions_closed=actions_closed)
                      for kind in religious_unit_operations.KINDS)
    state = None
    if not unavailable:
        native = catalogue(saved,observation)
        state = religious_unit_operations.project(native,observation['player_id'],observation['turn'],
                                                   observation=observation)
    contract.add_xp2_religious_unit_operations(decisions,state,actions_closed=actions_closed)


def _add_xp1_prophet_activation(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, prophet_activation, religion_beliefs
    from .xp1_prophet_activation import catalogue
    saved.explicit_prophet_activation = None
    if actions_closed and decisions['schema'] not in contract.XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE:
        return
    unavailable=contract.family_query_unavailable(decisions,'activate_prophet',actions_closed=actions_closed)
    state=None
    if not unavailable:
        native=catalogue(saved,observation)
        pid,turn=observation['player_id'],observation['turn']
        state=dict(schema=prophet_activation.SCHEMA,player_id=pid,turn=turn,
            own=religion_beliefs.project_snapshot(native['own'],pid,turn,observation=observation),
            activation=deepcopy(native['activation']))
    contract.add_xp1_prophet_activation(decisions,state,actions_closed=actions_closed)


def _add_xp2_pantheon(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, pantheon
    from .xp1_pantheon import catalogue, read_pantheon_index
    saved.explicit_pantheon = None
    if actions_closed and decisions['schema'] not in contract.XP2_PANTHEON_SCHEMA_BY_BASE:
        return
    unavailable = contract.family_query_unavailable(decisions, 'pantheon', actions_closed=actions_closed)
    state = None
    if not unavailable:
        native = catalogue(saved, observation)
        index = read_pantheon_index(saved, observation)
        state = dict(schema=pantheon.STATE_SCHEMA, player_id=observation['player_id'],
                     turn=observation['turn'], pantheon_index=index, catalogue=deepcopy(native))
    contract.add_xp2_pantheon(decisions, state, actions_closed=actions_closed)


def _add_xp2_prophet_activation(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, prophet_activation, religion_beliefs
    from .xp1_prophet_activation import catalogue
    saved.explicit_prophet_activation = None
    if actions_closed and decisions['schema'] not in contract.XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE:
        return
    unavailable=contract.family_query_unavailable(decisions,'activate_prophet',actions_closed=actions_closed)
    state=None
    if not unavailable:
        native=catalogue(saved,observation)
        pid,turn=observation['player_id'],observation['turn']
        state=dict(schema=prophet_activation.SCHEMA,player_id=pid,turn=turn,
            own=religion_beliefs.project_snapshot(native['own'],pid,turn,observation=observation),
            activation=deepcopy(native['activation']))
    contract.add_xp2_prophet_activation(decisions,state,actions_closed=actions_closed)


def _add_xp2_religion_founding(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religion_founding, religion_beliefs
    from .xp1_religion_founding import catalogue
    saved.explicit_religion_founding = None
    if actions_closed and decisions['schema'] not in contract.XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE:
        return
    unavailable=contract.family_query_unavailable(decisions,'found_religion',actions_closed=actions_closed)
    state=None
    if not unavailable:
        native=catalogue(saved,observation)
        pid,turn=observation['player_id'],observation['turn']
        state=dict(schema=religion_founding.SCHEMA,player_id=pid,turn=turn,
            own=religion_beliefs.project_snapshot(native['own'],pid,turn,observation=observation),
            foundation=deepcopy(native['foundation']))
    contract.add_xp2_religion_founding(decisions,state,actions_closed=actions_closed)


def _add_xp2_religion_beliefs(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract, religion_beliefs
    from .xp1_religion_beliefs import catalogue
    saved.explicit_religion_beliefs = None
    if actions_closed and decisions['schema'] not in contract.XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE:
        return
    unavailable=contract.family_query_unavailable(decisions,'add_belief',actions_closed=actions_closed)
    state=None
    if not unavailable:
        native=catalogue(saved,observation)
        pid,turn=observation['player_id'],observation['turn']
        state=dict(schema=religion_beliefs.SCHEMA,player_id=pid,turn=turn,
            own=religion_beliefs.project_snapshot(native['own'],pid,turn,observation=observation),
            beliefs=deepcopy(native['beliefs']))
    contract.add_xp2_religion_beliefs(decisions,state,actions_closed=actions_closed)



def _add_xp1_great_people(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract
    commands_enabled = getattr(saved, 'xp1_great_people_actions', False) is True
    if commands_enabled:
        from .xp1_great_people_commands import catalogue as read_people
        saved.explicit_great_people_actions = None
    else:
        from .xp1_great_people import read as read_people
    if actions_closed and decisions['schema'] not in contract.XP1_GREAT_PEOPLE_SCHEMA_BY_BASE:
        return
    unavailable = actions_closed or contract.is_waiting(decisions['turn_controls'])
    state = None if unavailable else read_people(saved, observation)
    contract.add_xp1_great_people(decisions, state, actions_closed=actions_closed)


def _add_xp2_great_people(saved, observation, decisions, *, actions_closed=False):
    from civ6_host.contracts import network_turn as contract

    if actions_closed and decisions['schema'] not in contract.XP2_GREAT_PEOPLE_SCHEMA_BY_BASE:
        return
    commands_enabled = getattr(saved, 'xp2_great_people_actions', False) is True
    if commands_enabled:
        from .xp1_great_people_commands import catalogue as read_people
        saved.explicit_great_people_actions = None
    else:
        from .xp1_great_people import read as read_people
    unavailable = contract.family_query_unavailable(decisions, 'great_people', actions_closed=actions_closed)
    state = None if unavailable else read_people(saved, observation, xp2=True)
    contract.add_xp2_great_people(decisions, state, actions_closed=actions_closed)
    if commands_enabled:
        contract.add_xp2_great_people_actions(decisions, actions_closed=actions_closed)


def _add_unit_work(saved, observation, decisions, *, actions_closed):
    from civ6_host.contracts import network_turn as contract, unit_work
    from .unit_work_info import read_catalog
    from .unit_work_state import observe
    from .xp2_lan_unit_work import primary_adjacent_enabled

    acting = not actions_closed and not contract.is_waiting(decisions['turn_controls'])
    adjacent = primary_adjacent_enabled(saved)
    catalogue, info = (read_catalog(saved.prefix, observation['turn'],
                                    player_id=observation['player_id'], processing=True, adjacent=adjacent)
                       if acting else (None, None))
    state = observe(saved, observation, catalogue, include_plot=True) if acting else None
    decisions.update(unit_work=catalogue, unit_work_state=state, unit_work_info=info)
    rows = [dict(candidate_id=contract.digest(action), action=action)
            for action in unit_work.actions(catalogue)] if acting else []
    decisions['candidates'].extend(rows)
    reason = 'session_closed' if actions_closed else 'native_unit_work_acting_boundary_unavailable'
    decisions['families'].update(unit_work.network_families(catalogue, rows, adjacent=adjacent,
                                                           unavailable_reason=reason))


def read(saved, player_id, sequence, *, actions_closed=False, specialist_diagnostic=False):
    """Return session, player observation, and an honest partial family catalogue.

    ``sequence`` is the common protocol revision, not a turn or command count.
    Every call reads current human ownership, activity, timer and observation.
    An empty qualified founder family exists only after the official query ran.
    """
    review_requested = getattr(saved, 'world_congress_review_diagnostic', False)
    stock_congress = (review_requested is True and getattr(saved, 'stock_dedications', False) is True)
    if (type(review_requested) is not bool
            or review_requested and getattr(saved, 'world_congress_diagnostic', False) is not True):
        raise ValueError('Congress review view requires its exact Boolean Congress group')
    if type(sequence) is not int or sequence < 0 or type(actions_closed) is not bool:
        raise ValueError('Invalid XP1 session revision or closure state')
    if getattr(saved, '_xp2_diplomacy', None) is not None:
        return _read_saved_diplomacy(saved, player_id, sequence,
                                     actions_closed=actions_closed)
    ref, ids = _prepare(saved, player_id)
    continuation = saved.continuation
    b, p = saved.backend, saved.prefix
    core_sha256=b.load_abi.core_sha256
    xp1_unit_work = core_sha256 == XP1_CORE_SHA256 and getattr(saved, '_xp1_unit_work_core', None) is b.core
    attack_families=core_sha256 in (XP1_CORE_SHA256,XP2_CORE_SHA256)
    city_flags=getattr(saved,'_expansion_city_controls_requested',None)
    city_controls_enabled=city_flags is not None
    if city_controls_enabled:
        from .expansion_city_controls import requested
        if requested(dict(zip(('city_focus_diagnostic','city_management_diagnostic'),city_flags)))!=city_flags:
            raise ValueError('City-control session opt-ins changed')
    common_input_families=core_sha256 in (XP1_CORE_SHA256,XP2_CORE_SHA256)
    # SavedContinuation already checked the official unit UI code once against
    # this exact module and retains its receipt; no per-query instruction scan.
    from .unit_operation_ui_profile import SOURCE as UNIT_SOURCE, CALLBACKS
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_action_transport_source import SOURCE as UNIT_SOURCE, CALLBACKS
    if (continuation.unit_source.get('source_sha256') != UNIT_SOURCE[1]
            or continuation.unit_source.get('callbacks') != CALLBACKS):
        raise ValueError('XP1 session lost its original unit-operation source receipt')
    from .network_timer import read as read_timer
    from civ6_host.contracts import network_turn as contract
    turn_gates = None if actions_closed else _turn_gates(saved, player_id)

    with saved._attempt():
        session, activity = _read_state(saved, player_id, ref, ids)
        rows = {row['player_id']: row for row in activity['rows']}
        row = rows[player_id]
        timer_elapsed = read_timer(b, core_sha256=core_sha256)
        observation = _observe_activity(saved, player_id, activity)
        permissions = (_read_command_permissions(saved, player_id, activity['turn'], sequence)
                       if stock_congress or review_requested and not actions_closed else None)
        strategic_allowed = permissions is None or permissions['allow_strategic']
        inventory=None
        if common_input_families:
            from .placement_inventory_profile import bind_owner as bind_inventory, source_reference
            from .placement_inventory import read as read_inventory
            from .execution_images import _PROFILE
            inventory_options = ({'include_pillage': True}
                if core_sha256 == XP2_CORE_SHA256
                and getattr(b.core,'_civ6_host_execution_image',None) is _PROFILE else {})
            INVENTORY_SOURCE=source_reference(core_sha256,**inventory_options)
            bind_inventory(b, b.core, b.runtime.read,**inventory_options)
            inventory = read_inventory(p, player_id, activity['turn'], observation,
                                       core_sha256=core_sha256,**inventory_options)
            saved.emit('native_placement_inventory_readback',
                episode_id=continuation.identity.episode_id,
                game_generation=continuation.identity.game_generation,
                sequence=sequence, player_id=player_id, turn=activity['turn'],
                inventory=inventory, source_proof_sha256=INVENTORY_SOURCE[1],
                host_tracking_used=False, native_gameplay_mutated=False)
        controls = dict(schema=contract.TURN_CONTROLS_SCHEMA, player_id=player_id,
            turn=activity['turn'], active=row['active'],
            active_complete=row['active_complete'], can_unready=row['can_unready'],
            timer_elapsed=timer_elapsed)
        if (core_sha256 == XP2_CORE_SHA256
                and continuation.world_input_prompts.get(player_id) is not None):
            if actions_closed:
                raise ValueError('An unresolved war prompt cannot be presented as a closed ordinary catalogue')
            from .xp2_world_war import read as read_war_modal
            decisions = read_war_modal(saved, observation, controls, sequence)
            return session, observation, decisions
        candidates = []
        availability={kind:None for kind in ('end_turn','force_end_turn','unready_turn')}
        turn_families={}
        if turn_gates is not None:
            availability=dict(turn_gates['turn_availability'])
        for kind,available in availability.items():
            if available is None:
                turn_families[kind]=dict(status='unqualified',reason=(
                    'session_closed' if actions_closed else 'native_turn_ui_gate_unknown'))
            else:
                selected=[]
                if available:
                    action=dict(kind=kind);candidate_id=contract.digest(action)
                    candidates.append(dict(candidate_id=candidate_id,action=action))
                    selected.append(candidate_id)
                turn_families[kind]=dict(status='queried_complete',candidate_ids=selected)
        city_focus_catalogs=citizen_catalogs=None
        city_families={kind:dict(status='unqualified',reason=(
            'session_closed' if actions_closed else 'native_city_control_acting_boundary_unavailable'))
            for kind in ('city_focus','city_citizen')}
        choice_state = None
        world_state=queued_orders=None
        unit_orders=None
        unit_attacks=None
        attack_family=dict(status='unqualified',reason=(
            'session_closed' if actions_closed else 'native_unit_attack_acting_boundary_unavailable'))
        production_queues=None
        placement_offers=placements=placement_scope=None
        from civ6_host.contracts.placement import GAPS as placement_gaps
        placement_families={kind:dict(status='unqualified',reason=(
            'session_closed' if actions_closed else 'native_placement_acting_boundary_unavailable'))
            for kind in placement_gaps}
        queue_kinds=('queue_append','queue_remove','queue_swap')
        queue_families={kind:dict(status='unqualified',reason=(
            'session_closed' if actions_closed else 'native_production_queue_acting_boundary_unavailable'))
            for kind in queue_kinds}
        from civ6_host.contracts.capability_unit_orders import UNQUALIFIED_UNIT_ORDERS
        order_family=dict(status='unqualified',reason=(
            'session_closed' if actions_closed else 'native_unit_orders_acting_boundary_unavailable'))
        from civ6_host.contracts.capability_world_input import WORLD_KINDS, UNQUALIFIED_WORLD_CLICK
        world_families={kind:dict(status='unqualified',reason=(
            'session_closed' if actions_closed else 'native_world_input_acting_boundary_unavailable'))
            for kind in sorted(WORLD_KINDS)}
        choice_families = {kind: dict(status='unqualified', reason=(
            'session_closed' if actions_closed else 'native_choice_acting_boundary_unavailable'))
            for kind in ('research', 'civic', 'production')}
        if actions_closed:
            foundation = dict(status='unqualified', reason='session_closed')
        elif contract.is_waiting(controls) or not strategic_allowed:
            foundation = dict(status='unqualified', reason=(
                'native_foundation_acting_boundary_unavailable' if strategic_allowed else
                contract.NATIVE_STRATEGIC_READER_UNAVAILABLE))
        else:
            actions = read_founders(p, player_id, activity['turn'], core_sha256=core_sha256)
            founders = [dict(candidate_id=contract.digest(action), action=action)
                        for action in actions]
            candidates.extend(founders)
            foundation = dict(status='queried_complete',
                candidate_ids=[candidate['candidate_id'] for candidate in founders])
        if not actions_closed and not contract.is_waiting(controls):
            from .xp1_choice_queries import read as read_choices
            choices, choice_families, choice_state = read_choices(saved, observation)
            candidates.extend(choices)
            if city_controls_enabled:
                from .expansion_city_controls import read as read_city_controls
                city_result=read_city_controls(saved,observation)
                city_focus_catalogs=city_result['city_focus_catalogs']
                citizen_catalogs=city_result['citizen_catalogs']
                for kind,key in (('city_focus','city_focus_catalogs'),('city_citizen','citizen_catalogs')):
                    if city_result[key] is not None:
                        rows=[dict(candidate_id=contract.digest(action),action=action)
                              for action in city_result['actions'] if action['kind']==kind]
                        candidates.extend(rows)
                        city_families[kind]=dict(status='queried_complete',candidate_ids=[r['candidate_id'] for r in rows])
                    else:
                        city_families[kind]=dict(status='unqualified',reason='city_management_not_requested')
            if common_input_families and strategic_allowed:
                from .xp1_production_queue import read as read_queues
                from civ6_host.contracts.production_queue import UNQUALIFIED_APPEND
                queue_result=read_queues(saved,observation)
                production_queues=queue_result['production_queues']
                for kind in queue_kinds:
                    rows=[dict(candidate_id=contract.digest(action),action=action)
                          for action in queue_result['actions'] if action['kind']==kind]
                    candidates.extend(rows)
                    family=dict(status='queried_complete',candidate_ids=[row['candidate_id'] for row in rows])
                    if kind=='queue_append':
                        family.update(status='queried_partial',unqualified=list(UNQUALIFIED_APPEND))
                    queue_families[kind]=family
            if common_input_families:
                from .xp1_production_placement import read as read_placements
                placement_result=read_placements(saved,observation)
                placement_offers=placement_result['placement_offers']
                placements=placement_result['placements']
                placement_scope=placement_result['placement_observation_scope']
                for kind,gaps in placement_gaps.items():
                    rows=[dict(candidate_id=contract.digest(action),action=action)
                          for action in placement_result['actions'] if action['kind']==kind]
                    candidates.extend(rows)
                    placement_families[kind]=dict(status='queried_partial',
                        candidate_ids=[row['candidate_id'] for row in rows],unqualified=list(gaps))
            if common_input_families and strategic_allowed:
                from .xp1_world_input import read as read_world
                world=read_world(saved,observation)
                world_state,queued_orders=world['world_input'],world['queued_orders']
                for kind in sorted(WORLD_KINDS):
                    rows=[dict(candidate_id=contract.digest(action),action=action)
                          for action in world['actions'] if action['kind']==kind]
                    candidates.extend(rows)
                    family=dict(status='queried_complete',candidate_ids=[row['candidate_id'] for row in rows])
                    if kind=='world_plot_click':
                        family.update(status='queried_partial',unqualified=list(UNQUALIFIED_WORLD_CLICK))
                    world_families[kind]=family
                from .xp1_unit_orders import read as read_orders
                orders=read_orders(saved,observation)
                unit_orders=orders['unit_orders']
                order_rows=[dict(candidate_id=contract.digest(action),action=action)
                            for action in orders['actions']]
                candidates.extend(order_rows)
                order_family=dict(status='queried_partial',
                    candidate_ids=[row['candidate_id'] for row in order_rows],
                    unqualified=list(UNQUALIFIED_UNIT_ORDERS))
            if attack_families and strategic_allowed:
                from .xp1_unit_attacks import read as read_attacks
                from civ6_host.contracts.capability_unit_attacks import UNQUALIFIED_UNIT_ATTACKS
                attack_result=read_attacks(saved,observation)
                unit_attacks=attack_result['unit_attacks']
                if attack_result['queued_orders']!=queued_orders:
                    raise ValueError('Unit attacks and world input read different native queued orders')
                attack_rows=[dict(candidate_id=contract.digest(action),action=action)
                             for action in attack_result['actions']]
                candidates.extend(attack_rows)
                attack_family=dict(status='queried_partial',
                    candidate_ids=[row['candidate_id'] for row in attack_rows],
                    unqualified=list(UNQUALIFIED_UNIT_ATTACKS))
        identity = continuation.identity
        decisions = dict(schema=contract.CAPABILITY_COMBAT_READINESS_SCHEMA, episode_id=identity.episode_id,
            game_generation=identity.game_generation, sequence=sequence, player_id=player_id,
            turn=activity['turn'], turn_controls=controls, candidates=candidates,
            choice_state=choice_state,turn_availability=availability,
            world_input=world_state,queued_orders=queued_orders,
            unit_orders=unit_orders,
            unit_attacks=unit_attacks,
            production_queues=production_queues,
            placement_offers=placement_offers,placements=placements,placement_observation_scope=placement_scope,
            placement_inventory=inventory,
            families=dict(found_city=foundation, **choice_families, **turn_families, **world_families, **queue_families, **placement_families,
                unit_order=order_family,unit_attack=attack_family,
                other_human_actions=dict(status='unqualified', reason='not_an_exhaustive_inventory')),
            family_inventory_complete=False, complete_action_space=False)
        if not attack_families:
            # An explicit older capability schema says which queries were made.
            # Unported families remain listed as unqualified, never empty offers.
            decisions['schema']=contract.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA
            del decisions['unit_attacks']
            for kind in ('unit_attack',):
                decisions['families'][kind]=dict(status='unqualified',
                    reason='xp2_family_profile_not_yet_qualified')
        if city_controls_enabled:
            # Rise and Fall composes its existing feature branches from v11.
            # City queries are an optional group in those same views.
            if core_sha256 != XP1_CORE_SHA256:
                decisions['schema']=contract.CAPABILITY_CITY_CONTROLS_SCHEMA
            decisions.update(city_focus_catalogs=city_focus_catalogs,citizen_catalogs=citizen_catalogs)
            decisions['families'].update(city_families)
        if core_sha256 == XP2_CORE_SHA256:
            from .native import native_saved_city_shot, native_saved_district_shot
            from .native import native_saved_city_targets as defenses
            from .production_inputs import read_current as read_current_production
            from .xp2_plot_purchases import catalogue as read_plot_purchases
            from .xp2_promotions import catalogue as read_promotions
            from .xp2_unit_upgrades import catalogue as read_upgrades
            from .xp2_strategic_resources import observe as read_strategic_resources
            from civ6_host.contracts import plot_purchases
            decisions['schema'] = contract.CAPABILITY_XP2_ENVOYS_SCHEMA
            from .xp2_policies import read as read_policies
            from civ6_host.contracts import capability_policies
            policy_catalogue = read_policies(saved, observation) if (
                not actions_closed and not contract.is_waiting(controls) and strategic_allowed) else None
            decisions['policies'] = policy_catalogue
            policy_rows = [dict(candidate_id=contract.digest(action), action=action)
                           for action in capability_policies.actions(policy_catalogue,
                               allow_relocation=True, allow_unchanged=True)]
            candidates.extend(policy_rows)
            decisions['families']['policies'] = (
                dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in policy_rows])
                if policy_catalogue is not None else dict(status='unqualified', reason=(
                    'session_closed' if actions_closed else 'native_policy_acting_boundary_unavailable')))
            from .xp2_policy_unlock import read as read_unlock
            from civ6_host.contracts import policy_unlock
            unlock = read_unlock(saved, observation) if policy_catalogue is not None else None
            decisions['policy_unlock'] = unlock
            rows = [dict(candidate_id=contract.digest(action), action=action)
                    for action in policy_unlock.actions(unlock)]
            candidates.extend(rows)
            decisions['families']['policy_unlock'] = (
                dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
                if unlock is not None else dict(status='unqualified', reason=(
                    'session_closed' if actions_closed else 'native_policy_acting_boundary_unavailable')))
            from .xp2_government import read as read_government
            from civ6_host.contracts import government as government_contract
            government = read_government(saved, observation) if policy_catalogue is not None else None
            decisions['government'] = government
            government_rows = [dict(candidate_id=contract.digest(action),action=action)
                               for action in government_contract.actions(government)]
            candidates.extend(government_rows)
            decisions['families']['government'] = (
                dict(status='queried_partial',candidate_ids=[row['candidate_id'] for row in government_rows],
                     unqualified=['anarchy_transition'])
                if government is not None else dict(status='unqualified',reason=(
                    'session_closed' if actions_closed else 'native_government_acting_boundary_unavailable')))
            decisions['strategic_resources'] = (
                None if actions_closed else read_strategic_resources(saved, observation))
            continuation.explicit_ranged_shots = {}
            continuation.explicit_city_shot_defenses = None
            acting = not actions_closed and not contract.is_waiting(controls)
            _add_promotions(saved, observation, decisions, read_promotions, acting=acting, actions_closed=actions_closed)
            saved.explicit_unit_upgrades = saved.xp2_unit_upgrades = None
            _add_upgrades(saved,observation,decisions,read_upgrades,
                          acting=acting and strategic_allowed,actions_closed=actions_closed)
            plot_catalogue, city_catalogue = read_plot_purchases(saved, observation, allow_faith=True) if acting else (None, None)
            decisions['plot_purchases'] = plot_catalogue
            decisions['city_purchases'] = city_catalogue
            if plot_catalogue is None:
                decisions['families']['purchase'] = dict(status='unqualified',
                    reason='session_closed' if actions_closed else 'native_purchase_acting_boundary_unavailable')
            else:
                purchase_rows = [dict(candidate_id=contract.digest(action), action=action)
                                 for action in plot_purchases.actions(plot_catalogue + city_catalogue)]
                candidates.extend(purchase_rows)
                decisions['families']['purchase'] = dict(status='queried_partial',
                    candidate_ids=[row['candidate_id'] for row in purchase_rows],
                    unqualified=list(plot_purchases.CITY_FAITH_GAPS))
            decisions['production_current'] = (
                read_current_production(p, observation, production_queues, xp2=True)
                if production_queues is not None else None)
            for shooter, codec in (('city', native_saved_city_shot), ('district', native_saved_district_shot)):
                kind = shooter + '_range_attack'
                shot_acting = acting and strategic_allowed
                shots = codec.catalog(p, activity['turn'], player_id=player_id) if shot_acting else None
                decisions[shooter + '_shots'] = shots
                continuation.explicit_ranged_shots[kind] = shots
                if not shot_acting:
                    decisions['families'][kind] = dict(status='unqualified',
                        reason='session_closed' if actions_closed else 'native_' + shooter + '_shot_acting_boundary_unavailable')
                    continue
                codec.compare_own_cities(shots, observation)
                shot_rows = [dict(candidate_id=contract.digest(action), action=action)
                             for action in codec.actions(shots)]
                candidates.extend(shot_rows)
                if shot_rows and continuation.explicit_city_shot_defenses is None:
                    continuation.explicit_city_shot_defenses = defenses.catalog(
                        p, activity['turn'], player_id=player_id, collect=False)['cities']
                decisions['families'][kind] = dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in shot_rows])
        if core_sha256 == XP2_CORE_SHA256 or xp1_unit_work:
            _add_unit_work(saved, observation, decisions, actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256:
            from .xp2_envoys import catalogue as read_envoys
            acting = not actions_closed and not contract.is_waiting(controls)
            envoys = read_envoys(saved, observation) if acting and strategic_allowed else None
            contract.add_envoy_choices(decisions, envoys, actions_closed=actions_closed)
        if getattr(saved, 'governors_diagnostic', False):
            if core_sha256 != XP2_CORE_SHA256:
                raise ValueError('Governor query option requires the selected XP2 core')
            from .xp2_governors import catalogue as read_governors
            from civ6_host.contracts import governors as governor_contract
            acting = not actions_closed and not contract.is_waiting(controls)
            governor_catalogue = read_governors(saved, observation) if acting else None
            decisions['schema'] = contract.CAPABILITY_XP2_GOVERNORS_SCHEMA
            decisions['governors'] = governor_catalogue
            governor_rows = [dict(candidate_id=contract.digest(action), action=action)
                             for action in governor_contract.actions(governor_catalogue)]
            candidates.extend(governor_rows)
            for kind in governor_contract.ACTION_FIELDS:
                decisions['families'][kind] = (dict(status='unqualified', reason=(
                    'session_closed' if actions_closed else 'native_governor_acting_boundary_unavailable'))
                    if governor_catalogue is None else dict(status='queried_complete', candidate_ids=[
                        row['candidate_id'] for row in governor_rows if row['action']['kind'] == kind]))
        standard_trade = getattr(saved, 'standard_trade', False)
        initial_diplomacy = getattr(saved, 'diplomacy_overview_diagnostic', False)
        if initial_diplomacy and not standard_trade:
            if (core_sha256 != XP2_CORE_SHA256
                    or decisions['schema'] != contract.CAPABILITY_XP2_GOVERNORS_SCHEMA):
                raise ValueError('Initial diplomacy requires its complete XP2 v32 input group')
            from .xp2_diplomacy_overview import catalogue as read_initial_diplomacy
            from civ6_host.contracts.diplomacy_overview import candidates as initial_choices
            acting = not actions_closed and not contract.is_waiting(controls)
            overview = (read_initial_diplomacy(saved, observation, sequence=sequence,
                                               public_relationships=True) if acting else None)
            decisions['schema'] = contract.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA
            decisions['diplomacy_overview'] = overview
            rows = [dict(candidate_id=contract.digest(action), action=action)
                    for action in ([] if overview is None else initial_choices(overview))]
            candidates.extend(rows)
            decisions['families']['diplomacy_initiate'] = (
                dict(status='unqualified', reason='session_closed' if actions_closed else
                     'native_initial_diplomacy_acting_boundary_unavailable')
                if overview is None else dict(status='queried_partial',
                    candidate_ids=[row['candidate_id'] for row in rows],
                    unqualified=list(contract.INITIAL_DIPLOMACY_GAPS)))
        if getattr(saved, 'trade_diagnostic', False) or standard_trade:
            base = (contract.CAPABILITY_XP2_ENVOYS_SCHEMA if standard_trade
                    else contract.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA)
            if decisions['schema'] != base:
                raise ValueError('Trade requires its selected XP2 base query group')
            from .xp2_trade import catalogue as read_trade

            acting = not actions_closed and not contract.is_waiting(controls)
            if standard_trade:
                from .xp2_trade_overview import read_stock
                panel, status = read_stock(saved, observation, sequence) if acting else (None, 'waiting_or_closed')
                decisions.update(trade_overview=panel, trade_overview_status=status)
                acting = acting and status != 'ui_boundary_unavailable'
            trade_view = (read_trade(saved, observation, **(
                            {'include_origins': strategic_allowed} if permissions is not None else {})) if acting else
                          dict(trade_routes=None, trade_origins=None))
            decisions['schema'] = (contract.CAPABILITY_XP2_STANDARD_TRADE_SCHEMA if standard_trade
                                   else contract.CAPABILITY_XP2_TRADE_SCHEMA)
            _add_trade(decisions, trade_view, actions_closed=actions_closed)
        if getattr(saved, 'unit_formations', False):
            from .xp2_unit_formations import catalogue as read_formations
            if decisions['schema'] != contract.CAPABILITY_XP2_STANDARD_TRADE_SCHEMA:
                raise ValueError('Formation query requires the stock trade capability boundary')
            state = (read_formations(saved, observation)
                     if not actions_closed and not contract.is_waiting(controls) and strategic_allowed else None)
            rows = [dict(candidate_id=contract.digest(action), action=action)
                    for action in ([] if state is None else state['offers'])]
            candidates.extend(rows)
            decisions['schema'] = contract.CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA
            decisions['unit_formations'] = state
            decisions['families']['unit_formation'] = (
                dict(status='unqualified', reason='session_closed' if actions_closed else
                     'native_unit_formation_acting_boundary_unavailable') if state is None else
                dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows]))
        if getattr(saved, 'stock_dedications', False):
            _add_dedications(saved, observation, decisions, actions_closed=actions_closed,
                previous_schema=contract.CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA,
                target_schema=contract.CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA)
        if getattr(saved, 'espionage_diagnostic', False):
            if core_sha256 != XP2_CORE_SHA256:
                raise ValueError('Espionage requires the selected XP2 engine')
            from .xp2_espionage import catalogue as read_espionage
            acting = not actions_closed and not contract.is_waiting(controls)
            espionage = read_espionage(saved, observation) if acting else None
            # This is the same decision envelope and native session; no second
            # scheduler or training-specific projection is involved.
            decisions = contract.upgrade_espionage_catalogue(
                decisions, espionage, observation=observation)
            from .xp2_spy_completion import catalogue as read_spy_completion
            completion = (read_spy_completion(saved, observation, waiting=not acting)
                          if not actions_closed else None)
            decisions = contract.upgrade_spy_completion_catalogue(
                decisions, completion, observation=observation)
        if getattr(saved, 'world_congress_diagnostic', False):
            if core_sha256 != XP2_CORE_SHA256:
                raise ValueError('Congress requires the selected XP2 engine')
            from .xp2_world_congress import catalogue as read_congress, check_model_admission
            check_model_admission(saved)
            congress = (read_congress(saved, observation, sequence=sequence)
                        if not actions_closed and not contract.is_waiting(controls) else None)
            decisions = contract.upgrade_world_congress_catalogue(
                decisions, congress, observation=observation,
                stock_permissions=permissions if stock_congress else None, actions_closed=actions_closed)
        if review_requested:
            from .xp2_world_congress_review import catalogue as read_congress_review
            review = read_congress_review(saved, observation, sequence=sequence,
                congress=decisions['world_congress'])
            decisions = contract.upgrade_review_catalogue(decisions,
                review['world_congress_review'], observation=observation,
                status=review['world_congress_review_status'])
            if permissions is not None:
                if _read_command_permissions(saved, player_id, activity['turn'], sequence) != permissions:
                    raise ValueError('Native command permissions changed during catalogue collection')
                if not strategic_allowed:
                    for family in contract.STRATEGIC_READER_FAMILIES:
                        if family in decisions['families']:
                            decisions['families'][family] = dict(status='unqualified',
                                reason=contract.NATIVE_STRATEGIC_READER_UNAVAILABLE)
                if not stock_congress:
                    decisions = contract.upgrade_command_permissions_catalogue(
                        decisions, permissions, observation=observation, actions_closed=actions_closed)
                from .xp2_world_congress_active_effects import catalogue as read_congress_active_effects
                effects = read_congress_active_effects(saved, observation, sequence=sequence,
                    congress=decisions['world_congress'])
                decisions = contract.upgrade_active_effects_catalogue(decisions,
                    effects['world_congress_active_effects'], observation=observation,
                    status=effects['world_congress_active_effects_status'])
        if (getattr(saved, 'trade_overview_ui_selected', False)
                and decisions['schema'] == contract.CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA):
            from .xp2_trade_overview import read as read_trade_overview
            panel, status = read_trade_overview(saved, observation, decisions)
            decisions = contract.upgrade_trade_overview_catalogue(
                decisions, panel, observation=observation, status=status)
        if not actions_closed and getattr(continuation, 'captured_city_core', None) is not None:
            from .captured_city_session import read as read_captured_city
            captured_city = read_captured_city(saved, observation, controls=controls,
                                              actions_closed=actions_closed)
            decisions = contract.upgrade_captured_city_catalogue(
                decisions, captured_city, actions_closed=actions_closed)
            if getattr(continuation, 'city_shot_core', None) is b.core:
                from .native import native_saved_city_shot, native_saved_district_shot
                acting = strategic_allowed and not contract.is_waiting(controls)
                image = b.core._civ6_host_execution_image
                continuation.explicit_ranged_shots = {}
                continuation.explicit_city_shot_defenses = None
                for kind, shot, upgrade in (
                    ('city_range_attack', native_saved_city_shot, contract.upgrade_xp1_city_shot_catalogue),
                    ('district_range_attack', native_saved_district_shot, contract.upgrade_xp1_district_shot_catalogue),
                ):
                    shots = (shot.catalog(p, activity['turn'], player_id=player_id, execution_image=image)
                             if acting else None)
                    continuation.explicit_ranged_shots[kind] = shots
                    if shots is not None:
                        shot.compare_own_cities(shots, observation)
                        if shot.actions(shots) and continuation.explicit_city_shot_defenses is None:
                            if continuation.explicit_combat_cities is None:
                                raise ValueError('Rise and Fall ranged shot lacks current visible defenses')
                            continuation.explicit_city_shot_defenses = deepcopy(
                                continuation.explicit_combat_cities)
                    decisions = upgrade(decisions, shots)
                if getattr(saved, 'xp1_governors_enabled', False):
                    from .xp2_governors import catalogue as read_governors
                    from .xp1_city_state_envoys import read as read_city_state_envoys
                    from .xp1_city_state_levies import catalogue as read_city_state_levies, unit_flags
                    from .xp2_envoys import catalogue as read_envoys
                    waiting = contract.is_waiting(controls)
                    governor_catalogue = None if waiting else read_governors(saved, observation)
                    decisions = contract.upgrade_xp1_governor_catalogue(decisions, governor_catalogue)
                    influence = None if waiting else read_city_state_envoys(saved, observation)
                    decisions = contract.upgrade_xp1_city_state_envoys_catalogue(decisions, influence)
                    envoys = None if waiting else read_envoys(saved, observation)
                    decisions['schema'] = contract.CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA
                    contract.add_envoy_choices(decisions, envoys, actions_closed=actions_closed)
                    levies = None if waiting else read_city_state_levies(saved, observation)
                    contract.add_xp1_city_state_levies(decisions, levies)
                    contract.add_xp1_unit_levies(decisions, None if waiting else unit_flags(saved, observation))
                    if getattr(saved, 'xp1_dedications_enabled', False):
                        _add_dedications(saved, observation, decisions, actions_closed=actions_closed,
                            previous_schema=contract.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                            target_schema=contract.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
                    if getattr(saved, 'xp1_trade', False):
                        if decisions['schema'] != contract.CAPABILITY_XP1_DEDICATIONS_SCHEMA:
                            raise ValueError('Rise and Fall trade requires its previous public catalogue')
                        from .xp2_trade import catalogue as read_trade
                        trade_view = (dict(trade_routes=None, trade_origins=None) if waiting else
                                      read_trade(saved, observation))
                        decisions['schema'] = contract.CAPABILITY_XP1_TRADE_SCHEMA
                        _add_trade(decisions, trade_view, actions_closed=actions_closed)
                        if getattr(saved, 'xp1_trade_overview', False):
                            from .xp2_trade_overview import read_stock
                            panel, status = (None, 'waiting_or_closed') if waiting else read_stock(
                                saved, observation, sequence)
                            decisions = contract.upgrade_trade_overview_catalogue(
                                decisions, panel, observation=observation, status=status)
                    if getattr(saved, 'xp1_government', False):
                        decisions['schema'] = contract.XP1_GOVERNMENT_SCHEMA_BY_BASE[decisions['schema']]
                        _add_xp1_government_policies(saved, observation, decisions,
                            acting=not waiting, actions_closed=actions_closed)
                    if getattr(saved, 'xp1_plot_purchase', False):
                        _add_xp1_plot_purchases(saved, observation, decisions,
                            acting=not waiting, actions_closed=actions_closed)
                    if getattr(saved, 'xp1_city_buildings', False):
                        from .xp1_city_buildings import read as read_city_buildings
                        from .xp2_great_work_commands import public_panel

                        decisions['schema'] = contract.XP1_CITY_BUILDINGS_SCHEMA_BY_BASE[decisions['schema']]
                        decisions['city_buildings'] = public_panel(
                            saved, read_city_buildings(saved, observation), can_act=not waiting and not actions_closed)
                        contract.add_great_work_choices(decisions, decisions['city_buildings'])
                    if getattr(saved, 'xp1_promotions', False):
                        from .xp1_promotions import catalogue as read_promotions
                        decisions['schema'] = contract.XP1_PROMOTION_SCHEMA_BY_BASE[decisions['schema']]
                        _add_promotions(saved, observation, decisions, read_promotions,
                                        acting=not waiting, actions_closed=actions_closed)
                    if getattr(saved,'xp1_unit_upgrades',False):
                        from .xp1_unit_upgrades import catalogue as read_upgrades
                        decisions['schema'] = contract.XP1_UPGRADE_SCHEMA_BY_BASE[decisions['schema']]
                        saved.explicit_unit_upgrades = None
                        _add_upgrades(saved,observation,decisions,read_upgrades,
                                      acting=not waiting,actions_closed=actions_closed)
        if core_sha256 == XP1_CORE_SHA256:
            _attach_installed_xp1_information(saved, observation, decisions)
            if getattr(saved,'xp1_pantheon',False):
                _add_xp1_pantheon(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_religion_beliefs',False):
                _add_xp1_religion_beliefs(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_religion_founding',False):
                _add_xp1_religion_founding(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_great_people',False):
                _add_xp1_great_people(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_prophet_activation',False):
                _add_xp1_prophet_activation(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_great_people_actions',False) is True and 'great_people' in decisions:
                contract.add_xp1_great_people_actions(decisions,actions_closed=actions_closed)
                if getattr(saved,'xp1_great_people_reject',False) is True:
                    contract.add_xp1_great_people_reject(decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_religion_custom_names',False) is True:
                _add_xp1_religion_custom_names(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_great_person_activation',False) is True:
                _add_xp1_great_person_activation(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_religious_unit_operations',False) is True:
                _add_xp1_religious_unit_operations(saved,observation,decisions,actions_closed=actions_closed)
            if getattr(saved,'xp1_city_religion_details',False) is True:
                _add_xp1_city_religion_details(saved,observation,decisions)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved, 'xp2_city_state_levies_enabled', False):
            from civ6_host.contracts.city_state_levies import ACTION as LEVY
            from .xp1_city_state_levies import catalogue as read_city_state_levies, unit_flags
            available = not contract.family_query_unavailable(decisions, LEVY, actions_closed=actions_closed)
            levies = read_city_state_levies(saved, observation) if available else None
            flags = None if actions_closed or contract.is_waiting(controls) else unit_flags(saved, observation)
            contract.add_xp2_levies(decisions, levies, flags)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved,'xp2_religious_unit_operations',False) is True:
            _add_xp2_religious_unit_operations(saved,observation,decisions,actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved,'xp2_prophet_activation',False) is True:
            _add_xp2_prophet_activation(saved,observation,decisions,actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved,'xp2_religion_founding',False) is True:
            _add_xp2_religion_founding(saved,observation,decisions,actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved,'xp2_religion_beliefs',False) is True:
            _add_xp2_religion_beliefs(saved,observation,decisions,actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved,'xp2_pantheon',False) is True:
            _add_xp2_pantheon(saved,observation,decisions,actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved,'xp2_city_religion_details',False) is True:
            _add_xp2_city_religion_details(saved,observation,decisions,actions_closed=actions_closed)
        if (core_sha256 == XP2_CORE_SHA256 and getattr(saved, 'xp2_city_buildings', False)
                and not actions_closed):
            from .xp2_city_buildings import read as read_city_buildings
            from .xp2_great_work_commands import public_panel
            from civ6_host.contracts.city_buildings import GREAT_WORK_COMMAND_SCHEMAS

            decisions['schema'] = contract.XP2_CITY_BUILDINGS_SCHEMA_BY_BASE[decisions['schema']]
            panel = public_panel(saved, read_city_buildings(saved, observation),
                                 can_act=strategic_allowed and not contract.is_waiting(controls))
            decisions['city_buildings'] = panel
            if panel['schema'] in GREAT_WORK_COMMAND_SCHEMAS:
                contract.add_great_work_choices(decisions, panel)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved, 'xp2_great_people', False) is True:
            _add_xp2_great_people(saved, observation, decisions, actions_closed=actions_closed)
        if core_sha256 == XP2_CORE_SHA256 and getattr(saved, 'xp2_great_person_activation', False) is True:
            _add_xp1_great_person_activation(saved, observation, decisions, actions_closed=actions_closed, xp2=True)
        if getattr(saved, '_world_score_core', None) is not None:
            from . import world_score
            decisions['world_score'] = None if actions_closed else world_score.read(saved, observation)
        if getattr(saved, '_xp2_build_route_core', None) is not None:
            from . import xp2_build_route

            routes = [] if actions_closed or contract.is_waiting(controls) else xp2_build_route.read(saved, observation)
            contract.add_build_route_choices(decisions, routes, actions_closed)
        if getattr(saved, '_xp2_air_operations_core', None) is not None:
            from . import xp2_air_operations

            air = [] if actions_closed or contract.is_waiting(controls) else xp2_air_operations.read(saved, observation)
            contract.add_air_choices(decisions, air, actions_closed)
        if getattr(saved, '_xp2_designate_park', None) is not None:
            from . import xp2_designate_park

            parks = ([] if actions_closed or contract.is_waiting(controls)
                     else xp2_designate_park.read(saved, observation))
            contract.add_park_designation_choices(decisions, parks, actions_closed)
        if getattr(saved, '_xp2_rock_bands', None) is not None:
            from . import xp2_rock_bands
            panel = None if actions_closed else xp2_rock_bands.read_panel(saved, observation)
            contract.add_rock_band_choices(decisions, panel, actions_closed)
        if getattr(saved, '_archaeology_core', None) is not None:
            from . import xp2_archaeology

            decisions['archaeology'] = None if actions_closed else xp2_archaeology.read(
                saved, observation, panel=decisions.get('city_buildings'))
            if xp2_archaeology.commands_enabled(saved):
                from .xp2_archaeology_excavation import read as read_excavations

                excavations = [] if actions_closed or contract.is_waiting(controls) else read_excavations(saved, observation)
                contract.add_archaeology_choices(decisions, actions_closed=actions_closed, excavations=excavations)
        if getattr(saved, '_expansion_city_growth', None) is not None:
            from . import expansion_city_growth
            decisions['city_growth'] = None if actions_closed else expansion_city_growth.read(saved, observation)
        if getattr(saved, '_expansion_city_loyalty', None) is not None:
            from . import expansion_city_loyalty
            decisions['city_loyalty'] = None if actions_closed else expansion_city_loyalty.read(saved, observation)
        if getattr(saved, '_expansion_national_parks', None) is not None:
            from . import expansion_national_parks
            decisions['national_parks'] = None if actions_closed else expansion_national_parks.read(saved, observation)
        if initial_diplomacy and standard_trade:
            from .xp2_diplomacy_overview import catalogue as read_initial_diplomacy
            from civ6_host.contracts.diplomacy_overview import candidates as initial_choices
            available = not actions_closed and not contract.is_waiting(controls) and strategic_allowed
            overview = read_initial_diplomacy(saved, observation, sequence=sequence) if available else None
            decisions['diplomacy_overview'] = overview
            rows = [dict(candidate_id=contract.digest(action), action=action)
                    for action in ([] if overview is None else initial_choices(overview))]
            decisions['candidates'].extend(rows)
            decisions['families']['diplomacy_initiate'] = (
                dict(status='queried_partial', candidate_ids=[row['candidate_id'] for row in rows],
                     unqualified=list(contract.STOCK_CITY_STATE_PEACE_GAPS)) if available else
                dict(status='unqualified', reason=('session_closed' if actions_closed else
                     'native_initial_diplomacy_acting_boundary_unavailable')))
        decisions.pop('decision_id', None)
        decisions['decision_id'] = contract.digest(decisions)
        contract.validate_capability_catalogue(decisions, identity, sequence, activity['turn'],
            player_id=player_id, actions_closed=actions_closed, observation=observation)
        if unit_attacks is not None:
            from .xp1_unit_attacks import administrative_readback
            event=administrative_readback(saved,observation,sequence)
            saved.emit(event['stage'],**{k:v for k,v in event.items() if k!='stage'})
            if not hasattr(saved,'combat_administrative_by_player'):
                saved.combat_administrative_by_player={}
            saved.combat_administrative_by_player[player_id]=deepcopy(event)
        elif hasattr(saved,'combat_administrative_by_player'):
            saved.combat_administrative_by_player.pop(player_id,None)
        if (specialist_diagnostic and core_sha256==XP2_CORE_SHA256 and city_controls_enabled and not actions_closed
                and row['active'] is True and row['active_complete'] is True
                and inventory is not None):
            from .placement_inventory import read_building_presence
            holy_sites=[r for r in inventory['rows'] if r['category']=='district'
                        and r['item_type']=='DISTRICT_HOLY_SITE' and r['complete']]
            for district in holy_sites:
                building=read_building_presence(p,player_id,activity['turn'],observation,
                    district['city_id'],'BUILDING_SHRINE',core_sha256=core_sha256)
                saved.emit('native_city_specialist_preparation_readback',
                    episode_id=identity.episode_id,game_generation=identity.game_generation,
                    sequence=sequence,player_id=player_id,turn=activity['turn'],
                    source_proof_sha256=INVENTORY_SOURCE[1],core_sha256=core_sha256,
                    diagnostic_only=True,building=building,district_plot_id=district['plot_id'])
        continuation.transport.require_empty_native_queue()
        b.control(empty=True)
        continuation.check(active=False)
    saved._check('commands', requested='unit_commands_candidate')
    return session, observation, decisions

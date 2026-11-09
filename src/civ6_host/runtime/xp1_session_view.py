"""Fresh player/session reads on the retained captured expansion owners.

This adapter exposes qualified families without fabricating absent information
groups. It neither schedules players nor changes the native readiness flags.
The parent adapter admits the exact captured bundle and attaches its reference.
"""
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


def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    execution_options = {}
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
        if (core_sha256 != XP2_CORE_SHA256
                or execution_image.reference_core_sha256 != core_sha256):
            raise ValueError('Session view execution image does not match its XP2 source ABI')
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
    groups.extend([world_dependencies(core_sha256,**execution_options),
                   order_dependencies(core_sha256,**execution_options),
                   queue_dependencies(core_sha256,**execution_options),
                   placement_dependencies(core_sha256,**execution_options),
                   inventory_dependencies(core_sha256,**execution_options)])
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
    result={}
    for group in groups:
        for path,digest in group.items():
            if path in result and result[path]!=digest:
                raise ValueError('Captured session source dependency identity conflicts')
            result[path]=digest
    if execution_image is not None:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        result=materialize_runtime_source_pins(result,execution_image=execution_image)
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


def _read_state(saved, player_id, ref, ids):
    from .lan_load import human_status_readback_source, _parse_humans
    from .network_turns import read_activity
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.game_child, human_status_readback_source(ids),
                                  b'@lan_session_humans', capacity=1024)
    humans = _parse_humans(raw, ids)
    if humans != ref['human_player_ids']:
        raise RuntimeError('XP1 native human ownership differs from admitted capture')
    activity = read_activity(saved, core_sha256=saved.backend.load_abi.core_sha256)
    if activity['local_player_id'] != player_id or activity['observer_id'] != player_id:
        raise RuntimeError('XP1 native local identity or observer changed')
    session = dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS',
        turn=activity['turn'], local_player_id=activity['local_player_id'],
        human_player_ids=list(humans), active_human_player_ids=[
            item['player_id'] for item in activity['rows']
            if item['active'] and item['player_id'] in humans])
    return session, activity


def state(saved):
    """Read current native session identity/activity before any terminal teardown."""
    from .xp1_saved_load_owner import SavedLoadOwner
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP1 session state requires the retained SavedLoadOwner')
    saved._check('commands', requested='unit_commands_candidate')
    player_id = saved.network_reference['state']['player_id']
    ref, ids = _prepare(saved, player_id)
    with saved._attempt():
        session, _ = _read_state(saved, player_id, ref, ids)
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


def read(saved, player_id, sequence, *, actions_closed=False, specialist_diagnostic=False):
    """Return session, player observation, and an honest partial family catalogue.

    ``sequence`` is the common protocol revision, not a turn or command count.
    Every call reads current human ownership, activity, timer and observation.
    An empty qualified founder family exists only after the official query ran.
    """
    review_requested = getattr(saved, 'world_congress_review_diagnostic', False)
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
    from .native.native_unit_actions import found_city_catalog_source, parse_founders
    from civ6_host.contracts import network_turn as contract
    turn_gates = None if actions_closed else _turn_gates(saved, player_id)

    with saved._attempt():
        session, activity = _read_state(saved, player_id, ref, ids)
        rows = {row['player_id']: row for row in activity['rows']}
        row = rows[player_id]
        timer_elapsed = read_timer(b, core_sha256=core_sha256)
        observation = _observe_activity(saved, player_id, activity)
        permissions = (_read_command_permissions(saved, player_id, activity['turn'], sequence)
                       if review_requested and not actions_closed else None)
        strategic_allowed = permissions is None or permissions['allow_strategic']
        inventory=None
        if common_input_families:
            from .placement_inventory_profile import bind_owner as bind_inventory, source_reference
            from .placement_inventory import read as read_inventory
            INVENTORY_SOURCE=source_reference(core_sha256)
            bind_inventory(b, b.core, b.runtime.read)
            inventory = read_inventory(p, player_id, activity['turn'], observation,
                                       core_sha256=core_sha256)
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
            source = found_city_catalog_source(player_id, activity['turn'],
                                               core_sha256=core_sha256)
            raw = p.runtime.evaluate_text(p.ui_child, source, b'@native_found_city_catalog',
                                          capacity=131072)
            actions = parse_founders(raw, player_id, activity['turn'])
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
            decisions['schema']=contract.CAPABILITY_CITY_CONTROLS_SCHEMA
            decisions.update(city_focus_catalogs=city_focus_catalogs,citizen_catalogs=citizen_catalogs)
            decisions['families'].update(city_families)
        if core_sha256 == XP2_CORE_SHA256:
            from .native import native_saved_city_shot, native_saved_district_shot
            from .native import native_saved_city_targets as defenses
            from .native.native_saved_unit_work import actions as work_actions
            from .unit_work_info import read_catalog as read_work_catalogue
            from .unit_work_state import observe as observe_work_state
            from .production_inputs import read_current as read_current_production
            from civ6_host.contracts.unit_work import NETWORK_GAPS
            from .xp2_plot_purchases import catalogue as read_plot_purchases
            from .xp2_promotions import catalogue as read_promotions
            from .xp2_unit_upgrades import catalogue as read_upgrades
            from .xp2_strategic_resources import observe as read_strategic_resources
            from civ6_host.contracts import plot_purchases, unit_upgrades
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
            saved.explicit_promotions = None
            promotions = read_promotions(saved, observation) if acting else None
            decisions['unit_promotions'] = promotions
            if promotions is None:
                decisions['families']['promote_unit'] = dict(status='unqualified',
                    reason='session_closed' if actions_closed else 'native_promotion_acting_boundary_unavailable')
            else:
                promotion_rows = [dict(candidate_id=contract.digest(action), action=action)
                                  for action in promotions['offers']]
                candidates.extend(promotion_rows)
                decisions['families']['promote_unit'] = dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in promotion_rows])
            saved.explicit_unit_upgrades = saved.xp2_unit_upgrades = None
            upgrades = read_upgrades(saved, observation) if acting and strategic_allowed else None
            decisions['unit_upgrades'] = upgrades
            if upgrades is None:
                decisions['families']['upgrade_unit'] = dict(status='unqualified',
                    reason='session_closed' if actions_closed else 'native_upgrade_acting_boundary_unavailable')
            else:
                upgrade_rows = [dict(candidate_id=contract.digest(action), action=action)
                                for action in unit_upgrades.actions(upgrades)]
                candidates.extend(upgrade_rows)
                decisions['families']['upgrade_unit'] = dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in upgrade_rows])
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
            work_catalogue, work_info = (
                read_work_catalogue(p, activity['turn'], player_id=player_id, processing=True)
                if acting else (None, None))
            decisions['unit_work'] = work_catalogue
            decisions['unit_work_info'] = work_info
            decisions['unit_work_state'] = (observe_work_state(saved, observation, work_catalogue,
                                            include_plot=True) if acting else None)
            work_rows = ([dict(candidate_id=contract.digest(action), action=action)
                          for action in work_actions(work_catalogue)] if acting else [])
            candidates.extend(work_rows)
            for kind, gaps in NETWORK_GAPS.items():
                if work_catalogue is None:
                    decisions['families'][kind] = dict(status='unqualified',
                        reason='session_closed' if actions_closed else 'native_unit_work_acting_boundary_unavailable')
                    continue
                decisions['families'][kind] = dict(status='queried_partial',
                    candidate_ids=[row['candidate_id'] for row in work_rows if row['action']['kind'] == kind],
                    unqualified=list(gaps))
        if core_sha256 == XP2_CORE_SHA256:
            from .xp2_envoys import catalogue as read_envoys
            from civ6_host.contracts.envoys import actions as envoy_actions
            acting = not actions_closed and not contract.is_waiting(controls)
            envoys = read_envoys(saved, observation) if acting and strategic_allowed else None
            decisions['envoys'] = envoys
            envoy_rows = [dict(candidate_id=contract.digest(action), action=action)
                          for action in envoy_actions(envoys)]
            candidates.extend(envoy_rows)
            for kind in ('send_envoy', 'retain_envoys'):
                decisions['families'][kind] = (dict(status='unqualified', reason=(
                    'session_closed' if actions_closed else 'native_envoy_acting_boundary_unavailable'))
                    if envoys is None else dict(status='queried_complete', candidate_ids=[
                        row['candidate_id'] for row in envoy_rows if row['action']['kind'] == kind]))
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
        if getattr(saved, 'diplomacy_overview_diagnostic', False):
            if (core_sha256 != XP2_CORE_SHA256
                    or decisions['schema'] != contract.CAPABILITY_XP2_GOVERNORS_SCHEMA):
                raise ValueError('Initial diplomacy requires its complete XP2 v32 input group')
            from .xp2_diplomacy_overview import catalogue as read_initial_diplomacy
            from civ6_host.contracts.diplomacy_overview import candidates as initial_choices
            acting = not actions_closed and not contract.is_waiting(controls)
            overview = read_initial_diplomacy(saved, observation, sequence=sequence) if acting else None
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
        if getattr(saved, 'trade_diagnostic', False):
            if decisions['schema'] != contract.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA:
                raise ValueError('Trade requires the selected XP2 v33 query group')
            from civ6_host.contracts import trade
            from .xp2_trade import catalogue as read_trade

            acting = not actions_closed and not contract.is_waiting(controls)
            trade_view = (read_trade(saved, observation, **(
                            {'include_origins': strategic_allowed} if permissions is not None else {})) if acting else
                          dict(trade_routes=None, trade_origins=None))
            decisions['schema'] = contract.CAPABILITY_XP2_TRADE_SCHEMA
            decisions.update(trade_view)
            for kind, field, choices in (
                    ('make_trade_route', 'trade_routes', trade.route_actions),
                    ('change_trade_origin', 'trade_origins', trade.origin_actions)):
                value = trade_view[field]
                rows = [dict(candidate_id=contract.digest(action), action=action)
                        for action in ([] if value is None else choices(value))]
                candidates.extend(rows)
                decisions['families'][kind] = (
                    dict(status='unqualified', reason='session_closed' if actions_closed else
                         'native_trade_acting_boundary_unavailable') if value is None else
                    dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows]))
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
            completion = read_spy_completion(saved, observation) if acting else None
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
                decisions, congress, observation=observation)
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
                decisions = contract.upgrade_command_permissions_catalogue(
                    decisions, permissions, observation=observation, actions_closed=actions_closed)
                from .xp2_world_congress_active_effects import catalogue as read_congress_active_effects
                effects = read_congress_active_effects(saved, observation, sequence=sequence,
                    congress=decisions['world_congress'])
                decisions = contract.upgrade_active_effects_catalogue(decisions,
                    effects['world_congress_active_effects'], observation=observation,
                    status=effects['world_congress_active_effects_status'])
        decisions.pop('decision_id', None)
        decisions['decision_id'] = contract.digest(decisions)
        contract.validate_capability_catalogue(decisions, identity, sequence, activity['turn'],
            player_id=player_id, actions_closed=actions_closed, observation=observation)
        if unit_attacks is not None:
            from .xp1_unit_attacks import administrative_readback
            event=administrative_readback(saved,observation,sequence)
            saved.emit(event['stage'],**{k:v for k,v in event.items() if k!='stage'})
            from copy import deepcopy
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

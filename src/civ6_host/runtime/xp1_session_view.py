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


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    from .captured_session_profile import select
    from .xp1_status_profiles import source_dependencies as status_dependencies
    from .unit_operation_ui_profile import source_dependencies as unit_dependencies
    from .xp1_research_profile import source_dependencies as research_dependencies
    from .xp1_production_profile import source_dependencies as production_dependencies
    from .xp1_turn_ui_profile import source_dependencies as turn_ui_dependencies
    selected=select(core_sha256)
    groups=[status_dependencies(core_sha256=core_sha256),
            unit_dependencies(core_sha256=core_sha256),
            research_dependencies(core_sha256=core_sha256),
            production_dependencies(core_sha256=core_sha256),
            turn_ui_dependencies(core_sha256=core_sha256)]
    from .xp1_world_input_profile import source_dependencies as world_dependencies
    from .xp1_unit_orders_profile import source_dependencies as order_dependencies
    from .xp1_production_queue_profile import source_dependencies as queue_dependencies
    from .xp1_production_placement_profile import source_dependencies as placement_dependencies
    from .placement_inventory_profile import source_dependencies as inventory_dependencies
    groups.extend([world_dependencies(core_sha256),order_dependencies(core_sha256),
                   queue_dependencies(core_sha256),placement_dependencies(core_sha256),
                   inventory_dependencies(core_sha256)])
    if selected.candidate.family in ('xp1-lan','xp2-lan'):
        from .xp1_unit_attack_profile import source_dependencies as attack_dependencies
        groups.append(attack_dependencies(core_sha256))
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
        groups.append(work_info_dependencies())
        groups.append(production_display_dependencies(xp2=True))
        groups.append(length_locale_dependencies()[0])
        groups.append(plot_purchase_dependencies())
        groups.append(promotion_dependencies())
        groups.append(upgrade_dependencies())
        groups.append(resource_dependencies())
    result={}
    for group in groups:
        for path,digest in group.items():
            if path in result and result[path]!=digest:
                raise ValueError('Captured session source dependency identity conflicts')
            result[path]=digest
    return result


def _prepare(saved, player_id):
    from .xp1_saved_load_owner import SavedLoadOwner
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP1 session view requires the retained SavedLoadOwner')
    saved._check('commands', requested='unit_commands_candidate')
    saved.continuation.check(active=False)
    ref, ids = _reference(saved, player_id)
    b = saved.backend
    from .xp1_status_profiles import bind_owner
    bind_owner(b, b.core, b.runtime.read)
    saved.continuation.transport.require_empty_native_queue()
    b.control(empty=True)
    return ref, ids


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


def read(saved, player_id, sequence, *, actions_closed=False, specialist_diagnostic=False):
    """Return session, player observation, and an honest partial family catalogue.

    ``sequence`` is the common protocol revision, not a turn or command count.
    Every call reads current human ownership, activity, timer and observation.
    An empty qualified founder family exists only after the official query ran.
    """
    if type(sequence) is not int or sequence < 0 or type(actions_closed) is not bool:
        raise ValueError('Invalid XP1 session revision or closure state')
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
    from .native.native_player_observation import observe_player
    from .native.native_unit_actions import found_city_catalog_source, parse_founders
    from civ6_host.contracts import network_turn as contract
    from .xp1_turn_ui_profile import read as read_turn_ui
    try:
        turn_gates=(None if actions_closed else read_turn_ui(saved,player_id,continuation.observation['turn']))
    except BaseException:
        saved._poison()
        raise

    with saved._attempt():
        session, activity = _read_state(saved, player_id, ref, ids)
        rows = {row['player_id']: row for row in activity['rows']}
        row = rows[player_id]
        timer_elapsed = read_timer(b, core_sha256=core_sha256)
        observation = observe_player(p.runtime, p.ui_child, player_id)
        if (observation['turn'] != activity['turn']
                or (observation['width'], observation['height']) !=
                    (continuation.observation['width'], continuation.observation['height'])):
            raise RuntimeError('XP1 session and player observation cross different boundaries')
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
        elif contract.is_waiting(controls):
            foundation = dict(status='unqualified', reason='native_foundation_acting_boundary_unavailable')
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
            if common_input_families:
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
            if common_input_families:
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
            if attack_families:
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
            decisions['schema'] = contract.CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA
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
            upgrades = read_upgrades(saved, observation) if acting else None
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
            plot_catalogue, city_catalogue = read_plot_purchases(saved, observation) if acting else (None, None)
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
                    unqualified=list(plot_purchases.CITY_GAPS))
            decisions['production_current'] = (
                read_current_production(p, observation, production_queues, xp2=True)
                if production_queues is not None else None)
            for shooter, codec in (('city', native_saved_city_shot), ('district', native_saved_district_shot)):
                kind = shooter + '_range_attack'
                shots = codec.catalog(p, activity['turn'], player_id=player_id) if acting else None
                decisions[shooter + '_shots'] = shots
                continuation.explicit_ranged_shots[kind] = shots
                if not acting:
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

"""Route a second human's explicit unit orders and turns through the LAN protocol."""

from civ6_host.contracts import network_turn
from civ6_host.contracts import archaeology, great_people_actions
from civ6_host.contracts.great_person_activation import KIND as ACTIVATE_PERSON
from civ6_host.contracts import city_buildings, dedications, espionage, governors, pantheon, spy_completion, unit_formations
from civ6_host.contracts.captured_city import KIND as OCCUPATION

from .configuration_profiles import XP2_CORE_SHA256
from .xp2_human_perspective import read_network_boundary, unit_command_effect_observed
from . import xp2_lan_city_controls, xp2_lan_unit_attacks, xp2_lan_unit_development, xp2_lan_world_input
from . import xp2_lan_ranged_shots
from . import xp2_lan_government
from . import xp2_lan_religion
from . import xp2_lan_city_states
from . import xp2_lan_unit_work
from . import xp2_lan_congress
from . import xp2_trade
from .xp2_plot_purchases import borrowed_enabled as purchases_enabled
from .captured_city_session import borrowed_enabled as occupation_enabled
from .xp2_lan_production_queue import FIELDS as QUEUE_KINDS


def public_decisions(saved, boundary, identity, sequence, player_id):
    """Project the same secondary catalogue for a live reply or checkpoint read."""
    from .network_timer import read as read_timer

    if boundary.outcome['episode_terminated']:
        return None
    turn = boundary.state['turn']
    row = next(row for row in boundary.state['rows'] if row['player_id'] == player_id)
    gates = boundary.gates
    timer = (read_timer(saved.backend, core_sha256=XP2_CORE_SHA256)
             if gates is None else gates['diagnostics']['timer_elapsed'])
    controls = dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=player_id, turn=turn,
        active=row['active'], active_complete=row['active_complete'],
        can_unready=row['can_unready'], timer_elapsed=timer)
    if boundary.war_state is not None:
        from . import xp2_world_war

        return xp2_world_war.public_decisions(boundary.war_state, boundary.view['observation'],
            identity, sequence, controls, expected_source=saved.war_source_sha256)
    diplomacy = getattr(boundary, 'diplomacy', None)
    if diplomacy is not None:
        from civ6_host.contracts.diplomacy_decisions import build

        choices, display, source = diplomacy
        return build(identity, sequence, boundary.view['observation'], controls, choices,
                     public_display=display, display_source_sha256=source)
    schema = (network_turn.CAPABILITY_SECONDARY_CITY_CONTROLS_SCHEMA
              if xp2_lan_city_controls.enabled(saved) else network_turn.CAPABILITY_SECONDARY_QUEUE_SCHEMA)
    if xp2_lan_world_input.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_WORLD_SCHEMA
    if xp2_lan_unit_development.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_DEVELOPMENT_SCHEMA
    if xp2_lan_unit_attacks.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_COMBAT_SCHEMA
    if occupation_enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_OCCUPATION_SCHEMA
    if xp2_lan_ranged_shots.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_RANGED_SHOTS_SCHEMA
    if purchases_enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_PURCHASE_SCHEMA
    if xp2_lan_government.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_GOVERNMENT_SCHEMA
    if xp2_lan_city_states.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_CITY_STATES_SCHEMA
    if xp2_lan_unit_work.enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_UNIT_WORK_SCHEMA
    if xp2_lan_unit_work.adjacent_enabled(saved):
        schema = network_turn.CAPABILITY_SECONDARY_ADJACENT_WORK_SCHEMA
    decisions = network_turn.secondary_unit_catalogue(identity, sequence, turn, player_id, controls,
        boundary.unit_orders, observation=boundary.view['observation'], schema=schema,
        research_choices=boundary.research, founders=boundary.founders,
        production_choices=boundary.production, production_queues=boundary.queues,
        city_focus_catalogs=boundary.city_focus_catalogs, citizen_catalogs=boundary.citizen_catalogs,
        world_input=boundary.world_input, queued_orders=boundary.queued_orders,
        unit_promotions=boundary.unit_promotions, unit_upgrades=boundary.unit_upgrades,
        unit_attacks=boundary.unit_attacks, occupation=boundary.captured_city,
        city_shots=boundary.city_shots, district_shots=boundary.district_shots,
        plot_purchases=boundary.plot_purchases, city_purchases=boundary.city_purchases,
        government_state=boundary.government, policy_state=boundary.policies, unlock_state=boundary.policy_unlock,
        envoy_state=boundary.envoys, city_state_levies=boundary.city_state_levies, unit_levies=boundary.unit_levies,
        city_state_peace=getattr(boundary, 'city_state_peace', None),
        city_state_peace_enabled=getattr(boundary, 'city_state_peace_enabled', False),
        world_score_state=getattr(boundary, 'world_score', None),
        world_score_enabled=getattr(boundary, 'world_score_enabled', False),
        archaeology_state=getattr(boundary, 'archaeology', None),
        archaeology_mode=getattr(boundary, 'archaeology_mode', 'off'),
        excavation_actions=getattr(boundary, 'excavation_actions', None),
        work_catalog=boundary.unit_work, work_state=boundary.unit_work_state, work_info=boundary.unit_work_info,
        city_panels=boundary.city_panels, great_people_state=boundary.great_people,
        great_people_mode=boundary.great_people_mode,
        pantheon_state=boundary.pantheon, pantheon_enabled=boundary.pantheon_enabled,
        governor_state=boundary.governors, governors_enabled=boundary.governors_enabled,
        espionage_state=boundary.espionage, espionage_enabled=boundary.espionage_enabled,
        completion_state=boundary.spy_completion, spy_completion_enabled=boundary.spy_completion_enabled,
        religion_states=boundary.religion, trade_states=boundary.trade,
        formation_state=boundary.formations, formation_enabled=boundary.formation_enabled,
        dedication_state=boundary.dedications, dedication_enabled=boundary.dedication_enabled,
        congress=getattr(boundary, 'congress', None),
        unit_panel_actions=getattr(boundary, 'unit_panel_actions', None),
        turn_availability=None if gates is None else gates['turn_availability'])
    if getattr(boundary, 'great_person_activation_enabled', False):
        network_turn.add_xp2_great_person_activation(decisions, boundary.great_person_activation)
        del decisions['decision_id']
        decisions['decision_id'] = network_turn.digest(decisions)
    return decisions


def read_reply(saved, protocol, request, view_players):
    """Build the secondary actor's native view and receipt at the requested revision."""
    pid, operation = request['player_id'], request['operation']
    local = saved.network_reference['state']['player_id']
    humans = saved.network_reference['human_player_ids']
    if (protocol.core_sha256 != XP2_CORE_SHA256 or pid == local or pid not in view_players
            or pid not in humans or operation not in ('observe', 'act')):
        raise ValueError('LAN secondary unit routing requires an authorized human observe or act')
    action = protocol.selected(request) if operation == 'act' else None
    city_state = None
    if action is not None and action['kind'] == 'production':
        city_state = next(row for row in protocol.catalogues[pid]['production_choices']['current']
                          if row['city_id'] == action['city_id'])
    elif action is not None and action['kind'] in QUEUE_KINDS:
        city_state = next(row for row in protocol.catalogues[pid]['production_queues']
                          if row['city_id'] == action['city_id'])
    elif action is not None and action['kind'] in xp2_lan_city_controls.CATALOGUE_FIELDS:
        field = xp2_lan_city_controls.CATALOGUE_FIELDS[action['kind']]
        city_state = next(row for row in protocol.catalogues[pid][field]
                          if row['city_id'] == action['city_id'])
    elif action is not None and action['kind'] in xp2_lan_world_input.WORLD_KINDS:
        prior = protocol.catalogues[pid]
        city_state = prior['world_input'], prior['queued_orders']
    elif action is not None and action['kind'] == 'world_war_response':
        city_state = protocol.catalogues[pid]['world_input']
    elif action is not None and action['kind'] == 'diplomacy_response':
        city_state = protocol.catalogues[pid]
    elif action is not None and xp2_lan_city_states.is_peace(action):
        city_state = protocol.catalogues[pid]['city_state_peace']
    elif action is not None and action['kind'] in xp2_lan_unit_development.FIELDS:
        field = xp2_lan_unit_development.FIELDS[action['kind']]
        city_state = protocol.catalogues[pid][field]
    elif action is not None and action['kind'] == 'unit_attack':
        city_state = protocol.catalogues[pid]['unit_attacks']
    elif action is not None and action['kind'] == OCCUPATION:
        city_state = protocol.catalogues[pid]['captured_city']
    elif action is not None and action['kind'] in xp2_lan_ranged_shots.FIELDS:
        field = xp2_lan_ranged_shots.FIELDS[action['kind']]
        city_state = protocol.catalogues[pid][field]
    elif action is not None and action['kind'] in xp2_lan_government.FIELDS:
        field = xp2_lan_government.FIELDS[action['kind']]
        city_state = protocol.catalogues[pid][field]
    elif action is not None and action['kind'] in xp2_lan_city_states.FIELDS:
        field = xp2_lan_city_states.FIELDS[action['kind']]
        city_state = protocol.catalogues[pid][field]
    elif action is not None and action['kind'] in great_people_actions.KINDS:
        city_state = protocol.catalogues[pid]['great_people']
    elif action is not None and action['kind'] == ACTIVATE_PERSON:
        city_state = protocol.catalogues[pid]['great_person_activation']
    elif action is not None and action['kind'] == pantheon.KIND:
        city_state = protocol.catalogues[pid]['pantheon']
    elif action is not None and action['kind'] in governors.ACTION_FIELDS:
        city_state = protocol.catalogues[pid]['governors']
    elif action is not None and action['kind'] in espionage.ACTION_FIELDS:
        city_state = protocol.catalogues[pid]['espionage']
    elif action is not None and action['kind'] in spy_completion.ACTION_FIELDS:
        city_state = protocol.catalogues[pid]['spy_completion']
    elif action is not None and action['kind'] in xp2_trade.FIELDS:
        city_state = protocol.catalogues[pid][xp2_trade.FIELDS[action['kind']]]
    elif action is not None and action['kind'] == unit_formations.KIND:
        city_state = protocol.catalogues[pid]['unit_formations']
    elif action is not None and action['kind'] == city_buildings.GREAT_WORK_MOVE:
        city_state = protocol.catalogues[pid]['city_buildings']
    elif action is not None and action['kind'] == archaeology.KIND:
        city_state = protocol.catalogues[pid]['archaeology']
    elif action is not None and action['kind'] == dedications.KIND:
        city_state = protocol.catalogues[pid]['dedications']
    elif action is not None and action['kind'] in xp2_lan_religion.FIELDS:
        city_state = protocol.catalogues[pid][xp2_lan_religion.FIELDS[action['kind']]]
    elif action is not None and action['kind'] in xp2_lan_congress.ACTIONS:
        city_state = protocol.catalogues[pid]['world_congress']
    options = {} if xp2_lan_congress.mode(saved) == 'off' else {'congress_sequence': request['sequence']}
    if getattr(saved, '_xp2_borrowed_war', None) is not None or (
            action is not None and action['kind'] == 'world_war_response'):
        options['dialogue_sequence'] = request['sequence']
    boundary = read_network_boundary(saved, pid, action, expected_city_state=city_state, **options)
    result, state, effect = boundary.outcome, boundary.state, boundary.unit_effect
    turn = state['turn']
    if turn != protocol.session['turn']:
        raise RuntimeError('Borrowed unit route crossed the current LAN turn')
    session = dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=turn,
        local_player_id=local, human_player_ids=list(humans),
        active_human_player_ids=[row['player_id'] for row in state['rows']
                                 if row['active'] and row['player_id'] in humans])
    decisions = public_decisions(saved, boundary, protocol.identity, request['sequence'], pid)
    observation = None if decisions is None else boundary.view['observation']
    if action is None:
        command = dict(status='none', reason=None, requested_action=None)
    elif action['kind'] != 'unit_order':
        command = boundary.receipt or dict(status='refused', reason=('native_terminal' if result['episode_terminated']
            else 'secondary_native_choice_unavailable'), requested_action=action)
    elif effect is None:
        command = dict(status='refused', reason=('native_terminal' if result['episode_terminated']
            else 'native_unit_command_unavailable'), requested_action=action)
    elif unit_command_effect_observed(effect):
        command = dict(status='completed', reason=None, requested_action=action)
    else:
        command = dict(status='submitted', reason='native_unit_effect_unresolved', requested_action=action)
    return result, session, observation, decisions, command

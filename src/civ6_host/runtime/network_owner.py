"""LAN admission around the existing public readers and native action adapters.

This module does not schedule players, change human flags, or implement rules.
The first admitted capture has one human. The LAN cycle reuses native requests
and updates; two-human transport, timed modes and full interface parity remain
separate qualification requirements.
"""
from __future__ import annotations

from .capture_profiles import LAN_PROFILE
from .lan_load import reference_state, human_status_readback_source, _parse_humans

STAGE = 'official-network-decision-ready'


def roster(player_ids):
    """Syntax bound only; owner admission separately checks the saved roster."""
    if (type(player_ids) is not tuple or not 1 <= len(player_ids) <= 64
            or any(type(p) is not int or not 0 <= p < 64 for p in player_ids)
            or len(set(player_ids)) != len(player_ids)):
        raise ValueError('Expected unique bounded native player IDs')
    return player_ids


def state(owner):
    owner.check_thread()
    if owner.inputs.profile is not LAN_PROFILE or owner.stage != STAGE:
        raise ValueError('Not an admitted LAN decision boundary')
    ref = owner.network_reference
    p = owner.prefix
    ids = ref['major_player_ids']
    raw = p.runtime.evaluate_text(p.game_child, human_status_readback_source(ids),
                                  b'@lan_session_humans', capacity=1024)
    if _parse_humans(raw, ids) != ref['human_player_ids']:
        raise RuntimeError('LAN human ownership changed')
    from .network_turns import read_activity
    observed = read_activity(owner)
    if (observed['local_player_id'] != ref['state']['player_id']
            or observed['observer_id'] != ref['state']['observer_id']):
        raise RuntimeError('LAN local identity/perspective differs from capture')
    rows = observed['rows']
    if tuple(row['player_id'] for row in rows) != ids:
        raise RuntimeError('LAN activity roster differs from capture')
    owner.network_turn_rows = {row['player_id']: row for row in rows}
    return dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS',
                turn=observed['turn'],
                local_player_id=observed['local_player_id'],
                human_player_ids=list(ref['human_player_ids']),
                active_human_player_ids=[r['player_id'] for r in rows
                    if r['active'] and r['player_id'] in ref['human_player_ids']])


def require_actor(owner, player_id, player_ids, *, require_active=True):
    roster(player_ids)
    if type(player_id) is not int or player_id not in player_ids:
        raise ValueError('Invalid LAN actor')
    ref = getattr(owner, 'network_reference', None)
    if ref is None or player_ids != ref['major_player_ids']:
        raise ValueError('LAN action roster was not admitted from the exact save')
    session = state(owner)
    if player_id not in session['human_player_ids']:
        raise ValueError('Requested LAN actor is not a captured human')
    if require_active and player_id not in session['active_human_player_ids']:
        raise ValueError('Requested LAN actor is not an active captured human')
    # This capture has a single human; do not use a human-control setter to
    # manufacture additional controllable actors or private views.
    if player_id != session['local_player_id']:
        raise ValueError('Additional LAN human perspective remains unqualified')
    return session


def read(owner, sequence, rounds, *, player_id, round_limit, closed=False):
    """Public view plus the native acting/waiting controls for this human."""
    from .network_turns import controls
    from .native.native_saved_actions import read_decisions, digest
    from .native.native_player_observation import observe_player
    from .native import native_saved_player_map as player_map
    from .native.native_episode_identity import require_episode
    ids = owner.network_reference['major_player_ids']
    session = require_actor(owner, player_id, ids, require_active=False)
    turn = controls(owner, session, player_id)
    dialogue = getattr(owner, 'turn_continuation', None) is not None
    if dialogue:
        from .network_dialogue import validate
        from .native.native_diplomacy_choices import read as read_dialogue
        retained = validate(owner)
        if retained.pending.session['player_id'] != player_id:
            raise ValueError('LAN dialogue belongs to another human')
        observation, decisions = read_dialogue(owner, sequence,
            closed=closed or rounds >= round_limit)
        decisions['base_schema'] = decisions['schema']
    elif turn['active'] and turn['active_complete'] and not turn['can_unready']:
        observation, decisions = read_decisions(owner, sequence, rounds,
            closed=closed, round_limit=round_limit, player_id=player_id, player_ids=ids)
        decisions['base_schema'] = decisions['schema']
        if decisions.get('world_input', {}).get('war_prompt') is None:
            from .network_dialogue import read_overview
            from .diplomacy_overview import candidates as initial_choices
            overview = read_overview(owner, player_id, observation['turn'])
            decisions['diplomacy_overview'] = overview
            if not closed and rounds < round_limit:
                decisions['candidates'].extend(dict(candidate_id=digest(action), action=action)
                                              for action in initial_choices(overview))
    else:
        p = owner.prefix
        observation = observe_player(p.runtime, p.ui_child, player_id)
        identity = require_episode(p)
        decisions = dict(base_schema=None, episode_id=identity.episode_id,
            game_generation=identity.game_generation, sequence=sequence,
            player_id=player_id, turn=observation['turn'],
            player_map=player_map.observe(p, observation), candidates=[],
            unsupported=['network_waiting_full_human_interface_unqualified'],
            complete_action_space=False)
    if turn['timer_elapsed'] is None:
        decisions['unsupported'].append('timer_elapsed_projection_unqualified')
    if (not dialogue and not closed and rounds < round_limit
            and decisions['base_schema'] is not None
            and decisions.get('world_input', {}).get('war_prompt') is None):
        from .network_ui import force_available
        if force_available(owner):
            action = dict(kind='force_end_turn')
            decisions['candidates'].append(dict(candidate_id=digest(action), action=action))
    from civ6_host.contracts.network_turn import LATEST_SCHEMA as SCHEMA
    if decisions['base_schema'] is not None and not dialogue:
        from .unit_work_state import observe as observe_work_state
        decisions['unit_work_state'] = observe_work_state(owner,observation,decisions['unit_work'])
        from civ6_host.contracts.unit_work_info import validate as validate_work_info
        decisions['unit_work_info'] = validate_work_info(
            owner.unit_work_information_by_player[player_id],player_id,observation['turn'],
            work_catalog=decisions['unit_work'],observation=observation)
        from .city_growth import observe as observe_growth
        decisions['city_growth']=observe_growth(owner,observation,sequence)
        from .production_inputs import attach as attach_production_inputs
        attach_production_inputs(owner,observation,decisions,sequence)
    else:
        decisions['unit_work_state'] = None
        decisions['unit_work_info'] = None
        decisions['city_growth'] = None
    decisions['schema'] = SCHEMA
    decisions['turn_controls'] = turn
    if not dialogue and not closed and rounds < round_limit and turn['can_unready'] and turn['timer_elapsed'] is False:
        action = dict(kind='unready_turn')
        decisions['candidates'].append(dict(candidate_id=digest(action), action=action))
    decisions['decision_id'] = digest({k:v for k,v in decisions.items() if k != 'decision_id'})
    from .network_dialogue import control
    control(owner)
    return observation, decisions


def prepare(owner, initial):
    """Admit the live boundary and return its optional checkpoint comparator."""
    if (owner.inputs.profile is not LAN_PROFILE
            or owner.stage != 'official-public-observed-awaiting-controlled-stop'):
        raise ValueError('LAN setup requires the exact completed official load')
    ref = reference_state(owner.captured_bundle)
    if (initial['player_id'] != ref['state']['player_id']
            or initial['turn'] != owner.captured_bundle.initial_turn):
        raise ValueError('LAN initial player/turn differs from captured reference')
    from .native.native_controller_state import prepare_session_controller
    prepare_session_controller(owner)
    owner.network_reference = ref
    owner.stage = STAGE
    from .network_ui import admit
    admit(owner)
    compare_initial = None
    if owner.inputs.checkpoint is not None:
        from .network_checkpoint import prepare_owner
        compare_initial = prepare_owner(owner, initial)
    session = require_actor(owner, initial['player_id'], ref['major_player_ids'])
    owner.control(empty=True)
    owner.emit('official_lan_decision_boundary', session=session,
               synthetic_turn_event=False, native_flags_written=False,
               simultaneous_cycle_qualified=False, strategic_training_ready=False)
    return session, compare_initial


def execute(owner, action, *, player_id, sequence, rounds, round_limit):
    """Requery native availability immediately before using an existing adapter.

    A global RPC revision change alone never refuses the action. The fresh
    catalogue revalidates legality and activates this player's current context.
    """
    from .native.native_saved_actions import read_decisions, apply_choice
    from .native import native_policy_catalog as policies
    from civ6_host.contracts.policies import PolicyAssignmentUnavailable
    ids = owner.network_reference['major_player_ids']
    session = require_actor(owner, player_id, ids, require_active=False)
    if getattr(owner, 'turn_continuation', None) is not None:
        from .network_dialogue import validate
        from .native.native_diplomacy_choices import read as read_dialogue, apply
        retained = validate(owner)
        if (retained.pending.session['player_id'] != player_id
                or action['kind'] != 'diplomacy_response'):
            return dict(status='refused', reason='native_dialogue_choice_required',
                        requested_action=action)
        _, current = read_dialogue(owner, sequence)
        if action not in [r['action'] for r in current['candidates']]:
            return dict(status='refused', reason='native_availability_changed',
                        requested_action=action)
        after = apply(owner, action)
        if after is None or after['player_id'] != player_id:
            raise RuntimeError('LAN response returned no matching public effect')
        return dict(status='completed', reason=None, requested_action=action)
    # Fast network routes below bypass legacy apply_choice. They must not
    # bypass the same explicit war-popup choice gate as ordinary commands.
    if (getattr(owner, 'world_input_prompts', {}).get(player_id) is not None
            and action['kind'] != 'world_war_response'):
        return dict(status='refused', reason='world_war_choice_required',
                    requested_action=action)
    if action['kind'] == 'unready_turn':
        from .network_turns import submit
        return submit(owner, action, player_id)
    if player_id not in session['active_human_player_ids']:
        return dict(status='refused', reason='native_actor_no_longer_active', requested_action=action)
    if action['kind'] == 'diplomacy_initiate':
        from .network_dialogue import initiate
        return initiate(owner, action, player_id, session['turn'])
    if action['kind'] == 'force_end_turn':
        from .network_ui import force_available
        from .network_turns import submit, controls
        if not force_available(owner):
            return dict(status='refused', reason='native_forced_turn_gate_unavailable',
                        requested_action=action)
        turn = controls(owner, session, player_id)
        if not turn['active_complete'] or turn['can_unready']:
            return dict(status='refused', reason='native_forced_turn_gate_unavailable',
                        requested_action=action)
        # Shift+Enter bypasses normal blockers. Do not fill in missing choices.
        return submit(owner, action, player_id)
    observation, current = read_decisions(owner, sequence, rounds,
        round_limit=round_limit, player_id=player_id, player_ids=ids)
    offers = [row['action'] for row in current['candidates']]
    admitted = action in offers
    if action['kind'] == 'policies':
        choices = [a for a in offers if a['kind'] == 'policies']
        candidate = action.get('candidate', {})
        try:
            admitted = (len(choices) == 1 and candidate.get('player_id') == player_id
                and candidate == policies.choose(choices[0]['slots'],
                    [h & 0xffffffff for _, h in candidate.get('assignments', [])],
                    player_id, observation['turn']))
        except PolicyAssignmentUnavailable:
            admitted = False
    if not admitted:
        return dict(status='refused', reason='native_availability_changed',
                    requested_action=action)
    if action['kind'] == 'end_turn':
        from .network_turns import submit
        return submit(owner, action, player_id)
    after = apply_choice(owner, action, session['turn'],
                         player_id=player_id, player_ids=ids)
    if after is None or after['player_id'] != player_id:
        raise RuntimeError('LAN action returned no matching public effect')
    return dict(status='completed', reason=None, requested_action=action)

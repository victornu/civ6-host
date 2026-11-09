"""Portable network catalogue for an explicit XP2 war-confirmation modal.

This is a temporary two-button decision surface, not a replacement for the
actor's ordinary XP2 capability catalogue. It authenticates public shape and
identity only; the host must still revalidate and submit the native response.
"""
from __future__ import annotations

import copy
import json

from . import capability_world_input as world_v1
from . import xp2_war_confirmation

SCHEMA = 'civ6-host.network-world-war-decisions.v1'
WORLD_INPUT_SCHEMA = 'civ6rl.world_input.v3'
_FIELDS = frozenset({
    'schema', 'episode_id', 'game_generation', 'sequence', 'player_id', 'turn',
    'turn_controls', 'complete_action_space', 'world_input', 'candidates',
    'decision_id',
})
_WORLD_INPUT_FIELDS = frozenset({
    'schema', 'player_id', 'turn', 'width', 'height', 'units',
    'selected_unit_id', 'war_prompt', 'war_display',
})


def is_catalogue(value):
    return type(value) is dict and value.get('schema') == SCHEMA


def validate(value, identity, sequence, turn, *, player_id, observation,
             expected_source_sha256, actions_closed=False):
    """Validate one current modal view against its independent source pin.

    ``observation`` is the sibling public player observation in the network
    response. ``expected_source_sha256`` must come from the selected
    renderer profile, never from the catalogue payload itself.
    """
    if type(actions_closed) is not bool or actions_closed:
        raise ValueError('A closed session cannot contain a live war decision modal')
    if (type(identity) not in (dict,) and not hasattr(identity, 'episode_id')):
        raise ValueError('Network episode identity is absent')
    expected_episode = (identity.get('episode_id') if type(identity) is dict
                        else getattr(identity, 'episode_id', None))
    expected_generation = (identity.get('game_generation') if type(identity) is dict
                           else getattr(identity, 'game_generation', None))
    if (type(expected_episode) is not str or not expected_episode
            or type(expected_generation) is not str or not expected_generation):
        raise ValueError('Network episode identity is malformed')
    if (type(value) is not dict or set(value) != _FIELDS
            or value.get('schema') != SCHEMA):
        raise ValueError('Unexpected network war-modal fields')
    if (value['episode_id'] != expected_episode
            or value['game_generation'] != expected_generation
            or type(value['episode_id']) is not str
            or type(value['game_generation']) is not str):
        raise ValueError('Stale or foreign war-modal episode')
    for name, expected, maximum in (
            ('sequence', sequence, 0x7fffffff),
            ('player_id', player_id, 63), ('turn', turn, 0xffffffff)):
        if (type(expected) is not int or not 0 <= expected <= maximum
                or type(value[name]) is not int or value[name] != expected):
            raise ValueError('Stale or foreign war-modal ' + name)
    if type(value['complete_action_space']) is not bool or value['complete_action_space'] is not False:
        raise ValueError('A war modal is not a complete gameplay action catalogue')
    if (type(observation) is not dict
            or type(observation.get('player_id')) is not int
            or observation['player_id'] != player_id
            or type(observation.get('turn')) is not int
            or observation['turn'] != turn):
        raise ValueError('War modal and sibling public observation differ')

    from .network_turn import digest, is_waiting, validate_turn_controls
    controls = validate_turn_controls(value['turn_controls'], player_id, turn)
    if is_waiting(controls):
        raise ValueError('World-war modal requires the actor-ready turn-control phase')

    state = value['world_input']
    if type(state) is not dict or set(state) != _WORLD_INPUT_FIELDS or state.get('schema') != WORLD_INPUT_SCHEMA:
        raise ValueError('Invalid XP2 v3 world-input modal state')
    if (type(state.get('player_id')) is not int or state['player_id'] != player_id
            or type(state.get('turn')) is not int or state['turn'] != turn):
        raise ValueError('World-input modal identity differs from its catalogue')

    prompt = xp2_war_confirmation.validate_prompt(state['war_prompt'], player_id)
    # Reuse the v1 own-roster, selection and complete-grid checks without
    # letting the modal prompt masquerade as ordinary world-input state.
    roster = copy.deepcopy(state)
    roster.pop('war_display')
    roster['schema'] = world_v1.SCHEMA
    roster['war_prompt'] = None
    world_v1.validate_state(roster, player_id, turn, observation=observation)

    defenders = [prompt['defending_player']]
    try:
        raw_display = json.dumps(state['war_display'], ensure_ascii=False,
            separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError('Malformed XP2 war display object') from exc
    xp2_war_confirmation.parse_display(raw_display, player_id, turn, defenders,
        prompt['war_type'], expected_source_sha256=expected_source_sha256)

    expected_actions = xp2_war_confirmation.actions(prompt, player_id)
    # Python equality would treat ``0`` as ``False``. Validate exact action
    # types and candidate envelopes before comparing the ordered catalogue.
    candidates = value['candidates']
    if type(candidates) is not list or len(candidates) != 2:
        raise ValueError('War modal must offer exactly Cancel then Confirm')
    for row in candidates:
        if (type(row) is not dict or set(row) != {'candidate_id', 'action'}
                or type(row['candidate_id']) is not str):
            raise ValueError('Malformed world-war response candidate')
        xp2_war_confirmation.validate_action(row['action'])
    expected_candidates = [dict(candidate_id=digest(action), action=action)
                           for action in expected_actions]
    if candidates != expected_candidates:
        raise ValueError('War modal must offer exactly Cancel then Confirm')
    expected_id = digest({key: item for key, item in value.items() if key != 'decision_id'})
    if type(value['decision_id']) is not str or value['decision_id'] != expected_id:
        raise ValueError('Network war-modal decision digest differs')
    return value


__all__ = ['SCHEMA', 'WORLD_INPUT_SCHEMA', 'is_catalogue', 'validate']

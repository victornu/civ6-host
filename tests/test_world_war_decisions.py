import unittest
from types import SimpleNamespace

from civ6_host.contracts import network_turn
from civ6_host.contracts import world_war_decisions as modal
from civ6_host.contracts import xp2_war_confirmation as display_codec


PIN = 'a' * 64
IDENTITY = SimpleNamespace(episode_id='episode-1', game_generation='generation-1')
OBSERVATION = {
    'player_id': 0, 'turn': 47, 'width': 3, 'height': 2,
    'units': [{'id': 101}],
}
PROMPT = {'attacking_player': 0, 'defending_player': 2, 'war_type': 1133958949}


def make_catalogue():
    world_input = {
        'schema': modal.WORLD_INPUT_SCHEMA, 'player_id': 0, 'turn': 47,
        'width': 3, 'height': 2,
        'units': [{'unit_id': 101, 'ignore_moves': False}],
        'selected_unit_id': 101, 'war_prompt': dict(PROMPT),
        'war_display': {
            'schema': display_codec.DISPLAY_SCHEMA,
            'player_id': 0, 'turn': 47, 'defender_player_ids': [2],
            'war_type': PROMPT['war_type'],
            'targets': [{'player_id': 2, 'display_name': 'Target', 'icon_name': 'ICON'}],
            'message': 'Declare war?', 'consequences': 'Consequences',
            'buttons': [{'accept': False, 'text': 'Cancel'},
                        {'accept': True, 'text': 'Confirm'}],
            'static_text': {'title': 'War', 'warmonger_heading': 'Warmonger'},
            'source_sha256': PIN,
        },
    }
    candidates = [dict(candidate_id=network_turn.digest(action), action=action)
                  for action in display_codec.actions(PROMPT, 0)]
    value = {
        'schema': modal.SCHEMA, 'episode_id': IDENTITY.episode_id,
        'game_generation': IDENTITY.game_generation, 'sequence': 8,
        'player_id': 0, 'turn': 47,
        'turn_controls': {
            'schema': network_turn.TURN_CONTROLS_SCHEMA, 'player_id': 0,
            'turn': 47, 'active': True, 'active_complete': True,
            'can_unready': False, 'timer_elapsed': None,
        },
        'complete_action_space': False, 'world_input': world_input,
        'candidates': candidates,
    }
    value['decision_id'] = network_turn.digest(value)
    return value


def validate(value=None, *, pin=PIN, closed=False, observation=OBSERVATION):
    return modal.validate(value or make_catalogue(), IDENTITY, 8, 47,
        player_id=0, observation=observation, expected_source_sha256=pin,
        actions_closed=closed)


class WorldWarDecisionsTests(unittest.TestCase):
    def test_valid_explicit_two_button_modal(self):
        value = make_catalogue()
        self.assertIs(validate(value), value)
        self.assertIs(network_turn.validate_catalogue(value, IDENTITY, 8, 47,
            player_id=0, observation=OBSERVATION,
            expected_war_source_sha256=PIN), value)

    def test_modal_requires_independent_source_pin(self):
        value = make_catalogue()
        with self.assertRaisesRegex(ValueError, 'pinned renderer'):
            network_turn.validate_catalogue(value, IDENTITY, 8, 47,
                player_id=0, observation=OBSERVATION)
        with self.assertRaisesRegex(ValueError, 'source digest mismatch'):
            validate(value, pin='b' * 64)

    def test_modal_keeps_actor_ready_turn_phase(self):
        value = make_catalogue()
        value['turn_controls']['active'] = False
        value['decision_id'] = network_turn.digest(
            {key: item for key, item in value.items() if key != 'decision_id'})
        with self.assertRaisesRegex(ValueError, 'actor-ready'):
            validate(value)

    def test_rejects_stale_identity_and_strict_integer_types(self):
        for field, replacement in (('sequence', 9), ('player_id', True), ('turn', True)):
            value = make_catalogue()
            value[field] = replacement
            value['decision_id'] = network_turn.digest(
                {key: item for key, item in value.items() if key != 'decision_id'})
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(value)
        value = make_catalogue()
        value['episode_id'] = 'old-episode'
        value['decision_id'] = network_turn.digest(
            {key: item for key, item in value.items() if key != 'decision_id'})
        with self.assertRaisesRegex(ValueError, 'Stale or foreign'):
            validate(value)

    def test_rejects_candidate_reordering_bad_boolean_and_private_fields(self):
        value = make_catalogue()
        value['candidates'].reverse()
        value['decision_id'] = network_turn.digest(
            {key: item for key, item in value.items() if key != 'decision_id'})
        with self.assertRaisesRegex(ValueError, 'exactly Cancel then Confirm'):
            validate(value)
        value = make_catalogue()
        value['candidates'][0]['action']['accept'] = 0
        value['candidates'][0]['candidate_id'] = network_turn.digest(
            value['candidates'][0]['action'])
        value['decision_id'] = network_turn.digest(
            {key: item for key, item in value.items() if key != 'decision_id'})
        with self.assertRaisesRegex(ValueError, 'explicit war confirmation'):
            validate(value)
        value = make_catalogue()
        value['private_debug'] = 'must not cross the boundary'
        with self.assertRaisesRegex(ValueError, 'Unexpected network war-modal fields'):
            validate(value)

    def test_rejects_prompt_display_roster_and_closed_mismatches(self):
        value = make_catalogue()
        value['world_input']['war_prompt']['defending_player'] = 0
        with self.assertRaisesRegex(ValueError, 'targets the attacking player'):
            validate(value)
        value = make_catalogue()
        value['world_input']['war_display']['warmonger_text'] = 'private/raw'
        with self.assertRaisesRegex(ValueError, 'XP2 war display identity or schema mismatch'):
            validate(value)
        value = make_catalogue()
        value['world_input']['units'][0]['unit_id'] = 102
        with self.assertRaisesRegex(ValueError, 'roster differs'):
            validate(value)
        with self.assertRaisesRegex(ValueError, 'closed session'):
            validate(make_catalogue(), closed=True)


if __name__ == '__main__':
    unittest.main()

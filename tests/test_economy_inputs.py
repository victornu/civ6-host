"""Pure contract tests for public and administrative economy snapshots."""
from __future__ import annotations

import copy
import unittest

from civ6_host.contracts import economy_inputs


def fixture():
    observation = {
        'schema': 'civ6rl-player-observation-v1', 'player_id': 0, 'turn': 7,
        'width': 2, 'height': 1, 'plots': [], 'units': [],
        'visible_enemy_units': [], 'cities': [
            {'id': 11, 'owner': 0, 'yields': {
                'food': 2.39, 'production': 3.0, 'gold': 1.25,
                'science': 4.49, 'culture': 1.01, 'faith': 0.0}},
            {'id': 22, 'owner': 1, 'yields': {
                'food': 99.0, 'production': 99.0, 'gold': 99.0,
                'science': 99.0, 'culture': 99.0, 'faith': 99.0}},
        ],
        'economy': {'science': 4.25, 'culture': 1.5, 'gold': 25.0, 'faith': 0.25},
    }
    display = {'schema': 'civ6rl.native_treasury_display980.v1', 'gold_balance': 25,
               'gold_yield': '+2.3', 'gold_expense': '-1.1', 'net_gold_yield': '+1.2'}
    treasury = {'schema': 'civ6rl.native_saved_treasury980.v1', 'player_id': 0,
                'turn': 7, 'gold_balance': 25.0, 'gold_yield': 2.34,
                'total_maintenance': 1.1, 'net_gold_yield': 2.34 - 1.1,
                'public_display': display}
    yield_display = {
        'schema': 'civ6rl.native_yield_display982.v1', 'player_id': 0, 'turn': 7,
        'raw': {'science': 4.25, 'culture': 1.5, 'faith': 0.25, 'faith_yield': 0.3},
        'public_display': {'science': '+4.2', 'culture': '+1.5', 'faith': '0.2',
                           'faith_yield': '+0.3'},
        'cities': [{'city_id': 11,
            'raw': {'food': 2.39, 'production': 3.0, 'gold': 1.25, 'science': 4.49,
                    'culture': 1.01, 'faith': 0.0},
            'public_display': {'food': '+2.3', 'production': '+3.0', 'gold': '+1.2',
                               'science': '+4.4', 'culture': '+1.0', 'faith': '0'}}],
    }
    research_info = {'schema': 'civ6rl.native_research_info983.v1', 'player_id': 0,
                     'turn': 7}
    choices = {}
    for topic, index, native_turns, shown in [('technology', 3, 1500, 999),
                                               ('civic', 4, 4, 4)]:
        row = {'index': index, 'hash': 1000 + index, 'cost': 50,
               'raw_turns': native_turns, 'turns_display': shown, 'boosted': True}
        research_info[topic] = {'selected': index, 'selected_info': row,
                                'choices': [row]}
        choices[topic] = row
    progress = {'schema': 'civ6rl.native_saved_research_progress971.v1',
                'player_id': 0, 'turn': 7,
                'technology': {'index': 3, 'cost': 50, 'progress': 20, 'remaining': 30},
                'civic': {'index': 4, 'cost': 50, 'progress': 10, 'remaining': 40}}
    decisions = {'research': {'research': 3, 'civic': 4},
                 'candidates': [
                     {'candidate_id': 'research:3', 'action': {'kind': 'research', 'index': 3, 'hash': 1003}},
                     {'candidate_id': 'civic:4', 'action': {'kind': 'civic', 'index': 4, 'hash': 1004}}],
                 'treasury': treasury, 'yield_display': yield_display,
                 'research_info': research_info, 'research_progress': progress}
    return observation, decisions


class EconomyInputsTests(unittest.TestCase):
    def test_project_is_numeric_public_projection_without_raw_or_locale_text(self):
        observation, decisions = fixture()
        before = copy.deepcopy((observation, decisions))
        value = economy_inputs.project(observation, decisions)
        self.assertEqual(value['schema'], economy_inputs.SCHEMA)
        self.assertEqual(value['treasury'], {'gold_balance': 25, 'gold_yield': 2.3,
                         'gold_expense': -1.1, 'net_gold_yield': 1.2})
        self.assertEqual(value['global_yields']['science'], 4.2)
        self.assertEqual([city['city_id'] for city in value['cities']], [11])
        self.assertEqual(value['cities'][0]['yields']['food'], 2.3)
        self.assertEqual(value['research']['technology']['choices'][0], {
            'index': 3, 'hash': 1003, 'cost': 50, 'turns_left': 999,
            'boosted': True, 'turns_capped': True})
        self.assertEqual(value, economy_inputs.validate(value, 0, 7, observation,
                                                        decisions['candidates']))
        self.assertEqual((observation, decisions), before)
        self.assertNotIn('raw', repr(value))
        self.assertNotIn('+2.3', repr(value))
        self.assertNotIn('raw_turns', repr(value))
        self.assertNotIn('research_progress', repr(value))

    def test_administrative_query_labels_and_preserves_native_snapshots(self):
        observation, decisions = fixture()
        before = copy.deepcopy((observation, decisions))
        value = economy_inputs.administrative(observation, decisions)
        self.assertEqual(value['schema'], economy_inputs.ADMIN_SCHEMA)
        self.assertIs(value['actor_channel'], False)
        self.assertEqual(value['treasury'], decisions['treasury'])
        self.assertEqual(value['yield_display'], decisions['yield_display'])
        self.assertEqual(value['research_info'], decisions['research_info'])
        self.assertEqual(value['research_progress'], decisions['research_progress'])
        self.assertEqual(value['economy'], observation['economy'])
        self.assertEqual(value['city_yields'][0]['yields'], observation['cities'][0]['yields'])
        self.assertEqual((observation, decisions), before)

    def test_public_validator_rejects_admin_raw_strings_and_bad_arithmetic(self):
        observation, decisions = fixture()
        value = economy_inputs.project(observation, decisions)
        injected = copy.deepcopy(value); injected['treasury']['raw'] = 2.34
        with self.assertRaisesRegex(ValueError, 'unknown or missing'):
            economy_inputs.validate(injected, 0, 7)
        bad = copy.deepcopy(value); bad['treasury']['net_gold_yield'] = 2.6
        with self.assertRaisesRegex(ValueError, 'net gold yield'):
            economy_inputs.validate(bad, 0, 7)
        bad = copy.deepcopy(value); bad['research']['technology']['choices'][0]['raw_turns'] = 1500
        with self.assertRaisesRegex(ValueError, 'unknown or missing'):
            economy_inputs.validate(bad, 0, 7)

    def test_rejects_caps_identity_own_city_and_candidate_mismatch(self):
        observation, decisions = fixture()
        value = economy_inputs.project(observation, decisions)
        bad = copy.deepcopy(value)
        bad['research']['technology']['choices'][0]['turns_capped'] = False
        with self.assertRaisesRegex(ValueError, 'turns_capped'):
            economy_inputs.validate(bad, 0, 7)
        with self.assertRaisesRegex(ValueError, 'identity'):
            economy_inputs.validate(value, 1, 7)
        with self.assertRaisesRegex(ValueError, 'roster'):
            economy_inputs.validate(value, 0, 7, dict(observation, cities=[]))
        with self.assertRaisesRegex(ValueError, 'candidates'):
            economy_inputs.validate(value, 0, 7, candidates=[])

    def test_display_precision_independent_rounding_and_negative_gold_balance(self):
        observation, decisions = fixture()
        decisions['treasury']['gold_yield'] = 2.34
        decisions['treasury']['total_maintenance'] = 1.16
        decisions['treasury']['net_gold_yield'] = 2.34 - 1.16
        decisions['treasury']['public_display']['gold_expense'] = '-1.1'
        decisions['treasury']['public_display']['net_gold_yield'] = '+1.1'
        result = economy_inputs.project(observation, decisions)
        self.assertEqual(result['treasury']['net_gold_yield'], 1.1)
        bad_precision = copy.deepcopy(result)
        bad_precision['global_yields']['science'] = 4.21
        with self.assertRaisesRegex(ValueError, 'one decimal'):
            economy_inputs.validate(bad_precision, 0, 7)

        observation['economy']['gold'] = -2.4
        decisions['treasury']['gold_balance'] = -2.4
        decisions['treasury']['public_display']['gold_balance'] = -3
        negative = economy_inputs.project(observation, decisions)
        self.assertEqual(negative['treasury']['gold_balance'], -3)

    def test_rejects_malformed_or_duplicate_candidates_and_progress_mismatch(self):
        observation, decisions = fixture()
        malformed = copy.deepcopy(decisions)
        malformed['candidates'] = [{}]
        with self.assertRaises(ValueError):
            economy_inputs.project(observation, malformed)
        duplicated = copy.deepcopy(decisions)
        duplicated['candidates'].append(copy.deepcopy(duplicated['candidates'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            economy_inputs.project(observation, duplicated)
        bad_progress = copy.deepcopy(decisions)
        bad_progress['research_progress']['technology']['cost'] = 100
        bad_progress['research_progress']['technology']['remaining'] = 80
        with self.assertRaisesRegex(ValueError, 'cost differs'):
            economy_inputs.administrative(observation, bad_progress)

    def test_rejects_duplicate_observation_city_and_bad_treasury_display(self):
        observation, decisions = fixture()
        duplicate = copy.deepcopy(observation)
        duplicate['cities'].append(copy.deepcopy(duplicate['cities'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate city'):
            economy_inputs.project(duplicate, decisions)
        altered = copy.deepcopy(decisions)
        altered['treasury']['public_display']['net_gold_yield'] = '+9.9'
        with self.assertRaisesRegex(ValueError, 'displayed net_gold_yield'):
            economy_inputs.project(observation, altered)


if __name__ == '__main__':
    unittest.main()

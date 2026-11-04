"""Contract-only checks for named public information groups."""
from __future__ import annotations

import copy
import unittest

from civ6_host.contracts import information, production_info988, production_inputs


def observation():
    return {'schema': 'civ6rl-player-observation-v1', 'player_id': 0, 'turn': 7,
            'width': 10, 'height': 1, 'plots': [
                {'index': 3, 'visible': True}],
            'units': [{'id': 9, 'owner': 0, 'x': 3, 'y': 0, 'moves': 0}],
            'visible_enemy_units': [], 'cities': [
                {'id': 11, 'owner': 0, 'population': 2}],
            'economy': {'science': 0.0, 'culture': 0.0, 'gold': 0.0, 'faith': 0.0}}


def production_decisions():
    candidate = {'candidate_id': 'prod', 'action': {'kind': 'production', 'city_id': 11,
        'category': 'building', 'index': 1, 'hash': 100, 'item_type': 'BUILDING_MONUMENT'}}
    quote = {'city_id': 11, 'category': 'building', 'index': 1, 'hash': 100,
        'item_type': 'BUILDING_MONUMENT',
        'public': {'cost': 30, 'progress': 2, 'turns_left': 4,
                   'never_completes': False, 'cost_kind': 'production'}}
    quote_input = {'schema': production_inputs.INFO_SCHEMA, 'player_id': 0, 'turn': 7,
        'source_sha256': production_info988.PROOF_SHA256,
        'ui_sha256': production_info988.PANEL_SHA256,
        'tooltip_sha256': production_info988.TOOLTIP_SHA256, 'rows': [quote]}
    current = {'schema': production_inputs.CURRENT_SCHEMA, 'player_id': 0, 'turn': 7,
        'cities': [{'city_id': 11, 'state': 'current', 'item': {
            'category': 'building', 'index': 1, 'hash': 100,
            'item_type': 'BUILDING_MONUMENT', 'name': 'Monument', 'formation': None,
            'progress': 2, 'cost': 30, 'turns_left': 4, 'never_completes': False}}]}
    queue = {'schema': 'civ6rl.production_queue.public.v2', 'player_id': 0, 'turn': 7,
        'city_id': 11, 'enabled': True,
        'entries': [{'position': 0, 'category': 'building', 'index': 1, 'hash': 100,
                     'formation': None, 'formation_display': None}],
        'offers': []}
    return {'production': current, 'production_info': quote_input,
            'production_queues': [queue], 'candidates': [candidate]}


def response_boundary(decisions, obs=None):
    return {'episode_id': 'episode-1', 'game_generation': 'native-episode-1',
            'sequence': 3, 'observation': observation() if obs is None else obs,
            'decisions': decisions}


def production_admin_event(response):
    raw_info = {'schema': production_info988.SCHEMA, 'player_id': 0, 'turn': 7,
        'source_sha256': production_info988.PROOF_SHA256,
        'ui_sha256': production_info988.PANEL_SHA256,
        'tooltip_sha256': production_info988.TOOLTIP_SHA256,
        'rows': [{'city_id': 11, 'category': 'building', 'index': 1, 'hash': 100,
            'item_type': 'BUILDING_MONUMENT',
            'raw': {'cost': 30, 'progress': 2, 'turns_left': 4,
                    'formation_type': None, 'base_cost': None,
                    'base_cost_visible': False},
            'public': {'cost': 30, 'progress': 2, 'turns_left': 4,
                       'never_completes': False, 'cost_kind': 'production'}}]}
    raw_production = {'player_id': 0, 'game_turn': 7, 'cities': [{
        'city_id': 11, 'owner_id': 0, 'queue_size': 1,
        'current_production_hash': 100, 'previous_production_hash': 0,
        'production_yield': 3, 'has_production_progress': True,
        'turns_left': 4, 'kind': 'B', 'item_index': 1, 'cost': 30,
        'progress': 2, 'formation': None}]}
    return {'stage': 'native_production_administrative_readback',
        'episode_id': response['episode_id'], 'game_generation': response['game_generation'],
        'player_id': 0, 'sequence': 3, 'turn': 7, 'source_sha256': 'a' * 64,
        'actor_channel': False, 'production': raw_production,
        'production_info': raw_info,
        'public_production': response['decisions']['production']}


def growth_value():
    text_fields = ('FoodPerTurnNum', 'FoodConsumption', 'NetFoodPerTurn', 'GrowthLongLabel',
        'FoodNeededForGrowth', 'OccupationMultiplier', 'HappinessBonus', 'OtherGrowthBonuses',
        'HousingMultiplier', 'TurnsUntilBornLost', 'FoodSurplusDeficitLabel',
        'ModifiedGrowthFoodPerTurn', 'TotalFoodSurplus')
    display = {key: '2.0' for key in text_fields}; display['GrowthLongNum'] = 4
    return {'schema': 'civ6-host.city-growth.v1', 'player_id': 0, 'turn': 7,
        'cities': [{'city_id': 11, 'population': 2, 'occupied': False, 'housing': 5.0,
            'amenities': 0.0, 'amenities_needed': 1.0, 'happiness': 3, 'display': display,
            'starving': False,
            'growth_icon': {'color': 'StatGoodCSGlow', 'u': 0, 'v': 150}}]}


def work_decisions():
    action = {'unit_id': 9, 'plot_id': 3, 'charges': 2, 'moves_token': '0',
              'operation': 8, 'kind': 'work'}
    work = {'player_id': 0, 'turn': 7, 'enabled': True,
            'offers': [{'action': action.copy(), 'legal': False}]}
    state = {'schema': 'civ6-host.unit-work-state.v1', 'player_id': 0, 'turn': 7,
             'units': [{'unit_id': 9, 'plot_id': 3, 'charges': 2, 'moves_token': '0'}]}
    info = {'schema': 'civ6-host.unit-work-info.v1', 'player_id': 0, 'turn': 7,
        'offers': [{'action': action.copy(), 'legal': False, 'action_name': 'Harvest',
                    'feature': {'index': 2, 'name': 'Woods'},
                    'descriptions': ['Gain 10'], 'failure_reasons': ['Research first']}],
        'targets': [{'unit_id': 9, 'plot_id': 3, 'improvement': -1,
                     'improvement_pillaged': False, 'route': 1, 'route_pillaged': True}]}
    return {'unit_work': work, 'unit_work_state': state, 'unit_work_info': info}


class InformationGroupsTests(unittest.TestCase):
    def test_public_group_names_and_required_fields(self):
        self.assertEqual(information.PUBLIC_GROUPS, ('economy', 'production', 'growth', 'unit_work', 'combat', 'display'))
        from civ6_host.contracts.network_turn import CAPABILITY_UNIT_WORK_STATE_SCHEMA
        self.assertEqual(information.required_fields('unit_work'),
                         ('unit_work_state', 'unit_work_info', 'unit_work'))
        self.assertEqual(information.required_fields('unit_work', CAPABILITY_UNIT_WORK_STATE_SCHEMA),
                         ('unit_work_state', 'unit_work'))
        self.assertEqual(information.required_fields('combat'), ('unit_attacks','queued_orders'))
        self.assertEqual(information.required_fields('production'),
                         ('production', 'production_info', 'production_queues', 'candidates'))
        with self.assertRaisesRegex(ValueError, 'Unknown public information group'):
            information.required_fields('critic')
        with self.assertRaisesRegex(ValueError, 'Unknown public information group'):
            information.project('unknown', observation(), {})

    def test_production_preserves_current_quotes_and_canonical_queues(self):
        obs = observation(); decisions = production_decisions()
        before = copy.deepcopy(decisions)
        value = information.project('production', obs, decisions)
        self.assertEqual(value['schema'], information.PRODUCTION_GROUP_SCHEMA)
        self.assertEqual(value['current']['cities'][0]['item']['name'], 'Monument')
        self.assertEqual(value['quotes']['rows'][0]['public']['progress'], 2)
        self.assertEqual(value['queues'][0]['entries'][0]['formation_display'], None)
        self.assertEqual(decisions, before)
        value['queues'][0]['entries'].clear()
        self.assertEqual(decisions['production_queues'][0]['entries'], before['production_queues'][0]['entries'])

    def test_growth_reuses_exact_observation_and_preserves_display_fields(self):
        obs = observation(); value = growth_value()
        out = information.project('growth', obs, {'city_growth': value})
        self.assertEqual(out['schema'], value['schema'])
        self.assertEqual(out['cities'][0]['display']['GrowthLongLabel'], '2.0')
        self.assertEqual(out['cities'][0]['growth_icon']['v'], 150)
        foreign = copy.deepcopy(value); foreign['player_id'] = 1
        with self.assertRaises(ValueError):
            information.project('growth', obs, {'city_growth': foreign})

    def test_unit_work_combines_state_and_information_without_losing_labels(self):
        obs = observation(); decisions = work_decisions()
        out = information.project('unit_work', obs, decisions)
        self.assertEqual(out['schema'], information.UNIT_WORK_GROUP_SCHEMA)
        self.assertEqual(out['state']['units'][0]['charges'], 2)
        self.assertEqual(out['info']['offers'][0]['failure_reasons'], ['Research first'])
        self.assertTrue(out['info']['targets'][0]['route_pillaged'])
        decisions['unit_work_info']['targets'][0]['plot_id'] = 8
        self.assertEqual(out['info']['targets'][0]['plot_id'], 3)
        with self.assertRaises(ValueError):
            information.project('unit_work', obs, decisions)

    def test_missing_group_fields_and_foreign_boundaries_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'missing city_growth'):
            information.project('growth', observation(), {})
        obs = observation()
        decisions = production_decisions()
        with self.assertRaises(ValueError):
            information.project('production', dict(obs, player_id=1), decisions)
        bad = production_decisions(); bad['production_queues'][0]['entries'][0]['hash'] = 101
        # The current-production contract binds the queue head to its displayed item.
        with self.assertRaises(ValueError):
            information.project('production', obs, bad)

    def test_production_administrative_readback_is_same_boundary_and_detached(self):
        decisions = production_decisions(); response = response_boundary(decisions)
        event = production_admin_event(response)
        before = copy.deepcopy(event)
        checked = information.validate_administrative('production', event, response,
                                                       source_sha256='a' * 64)
        self.assertEqual(checked, event)
        checked['production']['cities'][0]['progress'] = 999
        self.assertEqual(event, before)
        for edit in (lambda e: e.update(actor_channel=True),
                     lambda e: e.update(extra=True),
                     lambda e: e.update(turn=8),
                     lambda e: e.update(source_sha256='b' * 64)):
            changed = copy.deepcopy(event); edit(changed)
            with self.assertRaises(ValueError):
                information.validate_administrative('production', changed, response,
                                                     source_sha256='a' * 64)

    def test_growth_administrative_readback_checks_raw_values_and_own_roster(self):
        obs = observation(); public = growth_value()
        response = response_boundary({'city_growth': public}, obs)
        event = {'stage': 'native_city_growth_administrative_readback',
            'episode_id': response['episode_id'], 'game_generation': response['game_generation'],
            'player_id': 0, 'sequence': 3, 'turn': 7, 'source_sha256': 'c' * 64,
            'actor_channel': False, 'cities': [{'city_id': 11, 'food_stock': 4.12345,
                'growth_threshold': 20.0, 'food_surplus': 2.34,
                'turns_until_growth': 7, 'turns_until_starvation': -1}]}
        checked = information.validate_administrative('growth', event, response,
                                                       source_sha256='c' * 64)
        self.assertEqual(checked, event)
        wrong = copy.deepcopy(event); wrong['cities'][0]['food_stock'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            information.validate_administrative('growth', wrong, response)
        wrong = copy.deepcopy(event); wrong['cities'][0]['turns_until_growth'] = 1.5
        with self.assertRaisesRegex(ValueError, 'turns_until_growth'):
            information.validate_administrative('growth', wrong, response)
        wrong = copy.deepcopy(event); wrong['cities'][0]['city_id'] = 12
        with self.assertRaisesRegex(ValueError, 'roster'):
            information.validate_administrative('growth', wrong, response)


if __name__ == '__main__':
    unittest.main()

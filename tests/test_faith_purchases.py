from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import network_turn, plot_purchases


class FaithPurchaseContractTests(unittest.TestCase):
    def setUp(self):
        # Reuse the retained XP2 v28 public replay, which already carries the
        # city-purchase query and all intervening capability groups.
        from civ6_host.runtime.paths import resource_root
        path = resource_root() / 'work' / 'bbg751-policy-relocation' / 'native03' / 'public-replay.jsonl'
        if not path.is_file():
            self.skipTest('Retained v28 XP2 public replay required')
        retained = json.loads(path.read_text(encoding='utf-8').splitlines()[0])['view']
        self.observation = retained['observation']
        self.saved = deepcopy(retained['decisions'])
        if self.saved['schema'] != network_turn.CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA:
            self.skipTest('Retained public replay does not contain the expected v28 catalogue')
        self.live = deepcopy(self.saved)
        self.live['schema'] = network_turn.CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA
        city_id = (self.live['city_purchases'][-1]['city_id']
                   if self.live['city_purchases'] else self.observation['cities'][0]['id'])
        self.gold = dict(kind='purchase', city_id=city_id, category='unit', index=0xfffffffe,
                         hash=0xfffffffd, item_type='UNIT_SCOUT', currency='YIELD_GOLD', price_token='60')
        self.faith = dict(self.gold, currency='YIELD_FAITH', price_token='120')
        offers = [dict(action=action, command_legal=True, can_afford=True)
                  for action in (self.gold, self.faith)]
        if self.live['city_purchases'] is None:
            self.live['city_purchases'] = [dict(player_id=self.live['player_id'],
                turn=self.live['turn'], city_id=city_id, offers=[])]
        city = next(row for row in self.live['city_purchases'] if row['city_id'] == city_id)
        city['offers'].extend(offers)
        for action in (self.gold, self.faith):
            self.live['candidates'].append(dict(candidate_id=network_turn.digest(action),
                                                action=action))
        family = self.live['families']['purchase']
        family['candidate_ids'].extend(network_turn.digest(action) for action in (self.gold, self.faith))
        family['unqualified'] = list(plot_purchases.CITY_FAITH_GAPS)
        self.saved = deepcopy(self.live)
        self.saved['schema'] = network_turn.CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA
        saved_city = next(row for row in self.saved['city_purchases'] if row['city_id'] == city_id)
        saved_city['offers'] = [row for row in saved_city['offers']
                                if row['action']['currency'] != 'YIELD_FAITH']
        faith_id = network_turn.digest(self.faith)
        self.saved['candidates'] = [row for row in self.saved['candidates']
                                    if row['candidate_id'] != faith_id]
        saved_family = self.saved['families']['purchase']
        saved_family['candidate_ids'] = [key for key in saved_family['candidate_ids'] if key != faith_id]
        saved_family['unqualified'] = list(plot_purchases.CITY_GAPS)
        self.saved.pop('decision_id', None)
        self.saved['decision_id'] = network_turn.digest(self.saved)

    def validate(self, value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)
        identity = SimpleNamespace(episode_id=value['episode_id'],
                                   game_generation=value['game_generation'])
        return network_turn.validate_capability_catalogue(value, identity, value['sequence'],
            value['turn'], player_id=value['player_id'], observation=self.observation)

    def test_legacy_contracts_reject_faith(self):
        with self.assertRaises(ValueError):
            plot_purchases.validate_city_action(self.faith)
        with self.assertRaises(ValueError):
            plot_purchases.validate_purchase_action(self.faith)
        catalogue = [dict(player_id=self.live['player_id'], turn=self.live['turn'],
            city_id=self.faith['city_id'], offers=[dict(action=self.faith,
                command_legal=True, can_afford=True)])]
        with self.assertRaises(ValueError):
            plot_purchases.validate_catalogue(catalogue, self.live['player_id'],
                self.live['turn'], city_items=True)

    def test_v30_allows_same_city_item_in_both_currencies(self):
        self.validate(self.live)
        duplicate = deepcopy(self.live)
        duplicate['city_purchases'][0]['offers'].append(
            dict(action=self.gold, command_legal=True, can_afford=True))
        with self.assertRaises(ValueError):
            self.validate(duplicate)

    def test_plot_purchase_stays_gold_only(self):
        plot = deepcopy(self.live['plot_purchases'][0]['offers'][0]['action'])
        plot['currency'] = 'YIELD_FAITH'
        with self.assertRaises(ValueError):
            plot_purchases.validate_action(plot)

    def test_candidates_follow_only_can_start_and_can_afford_flags(self):
        value = deepcopy(self.live)
        city = next(row for row in value['city_purchases']
                    if row['city_id'] == self.faith['city_id'])
        unavailable = dict(self.faith, index=0xfffffffd, hash=0xfffffffc, item_type='UNIT_SLINGER',
                           price_token='140')
        city['offers'].extend([
            dict(action=unavailable, command_legal=False, can_afford=True),
            dict(action=dict(unavailable, index=0xfffffffc, hash=0xfffffffb, item_type='UNIT_ARCHER'),
                 command_legal=True, can_afford=False),
        ])
        self.validate(value)
        self.assertEqual([row['action'] for row in value['candidates']
                          if row['action'].get('kind') == 'purchase'
                          and 'plot_id' not in row['action']],
                         [row['action'] for row in self.live['candidates']
                          if row['action'].get('kind') == 'purchase'
                          and 'plot_id' not in row['action']])

    def test_v30_to_v29_projection_is_historical_and_does_not_mutate(self):
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        self.validate(self.live)
        before = deepcopy(self.live)
        projected, transition = network_turn.checkpoint_catalogue(
            self.live, self.saved, self.observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, self.saved)
        self.assertEqual(self.live, before)
        self.assertEqual(transition['source_schema'], self.saved['schema'])
        self.assertEqual(transition['target_schema'], network_turn.CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA)
        self.assertIn('faith_unit_building_purchase', transition['added_action_families'])
        self.assertNotIn('faith_purchase_native_effect', transition['added_action_families'])


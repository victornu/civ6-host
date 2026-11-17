from copy import deepcopy
from hashlib import sha256
from struct import pack
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn
from civ6_host.runtime import xp1_plot_purchases, xp1_session_view, xp2_dedications
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue


class RiseAndFallPlotPurchaseTests(unittest.TestCase):
    def test_visible_offers_are_filtered_by_legal_and_affordable_and_project_back(self):
        observation, original = expansion_catalogue()
        actor, turn = observation['player_id'], observation['turn']
        dedication = xp2_dedications.parse_state(f'{actor}|{turn}|0|normal|0'.encode(), actor, turn)
        with patch.object(xp2_dedications, 'catalogue', return_value=dedication):
            xp1_session_view._add_dedications(None, observation, original, actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        seal(original)
        city, = observation['cities']
        def offer(x, price, legal, affordable):
            action = dict(kind='purchase', city_id=city['id'], plot_id=x, x=x, y=0,
                          currency='YIELD_GOLD', price_token=price)
            return dict(action=action, command_legal=legal, can_afford=affordable)

        offers = [offer(0, '50', True, True), offer(1, '60', True, False), offer(2, '60', False, True)]
        quotes = [dict(player_id=actor, turn=turn, city_id=city['id'], offers=offers)]
        current = deepcopy(original)
        with patch.object(xp1_plot_purchases, 'catalogue', return_value=quotes):
            xp1_session_view._add_xp1_plot_purchases(None, observation, current, acting=True,
                                                      actions_closed=False)
        seal(current)
        row, = [r for r in current['candidates'] if r['action']['kind'] == 'purchase']
        self.assertEqual(row['action'], offers[0]['action'])
        self.assertEqual(current['plot_purchases'], quotes)
        self.assertEqual(network_turn.select_capability(current,dict(decision_id=current['decision_id'],
            candidate_id=row['candidate_id'])), row['action'])
        projected, transition = network_turn.checkpoint_catalogue(current, original, observation,
                                                                  core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected, original)
        self.assertEqual(transition['added_public_fields'], ['plot_purchases'])
        self.assertEqual(transition['added_action_families'], ['purchase'])
        with self.assertRaisesRegex(ValueError, 'requires Rise and Fall'):
            network_turn.checkpoint_catalogue(current, original, observation, core_sha256=XP2_CORE_SHA256)

    def test_purchase_requires_exact_city_command_archive(self):
        action = dict(kind='purchase', city_id=65536, plot_id=521, x=37, y=11,
                      currency='YIELD_GOLD', price_token='45')
        words = [0x346b0a13,0,2,65536,0,0,1,0,4,0xffffffff,37,11]
        valid = pack('<IHH9I',*words)
        self.assertEqual(xp1_plot_purchases.validate_archive(valid,0,action),sha256(valid).hexdigest())
        for field in (1,3,4,5,7,8,10,11):
            changed = list(words)
            changed[field] ^= 1
            with self.assertRaisesRegex(ValueError, 'differs from the admitted city command'):
                xp1_plot_purchases.validate_archive(pack('<IHH9I',*changed),0,action)

    def test_waiting_state_does_not_query_prices_or_offer_orders(self):
        value = dict(schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA, candidates=[], families={})
        with patch.object(xp1_plot_purchases, 'catalogue') as read:
            xp1_session_view._add_xp1_plot_purchases(None, {}, value, acting=False, actions_closed=False)
        read.assert_not_called()
        self.assertEqual(value['candidates'], [])
        self.assertIsNone(value['plot_purchases'])
        self.assertEqual(value['families']['purchase']['status'], 'unqualified')


if __name__ == '__main__':
    unittest.main()

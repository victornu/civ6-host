from copy import deepcopy
from hashlib import sha256
from struct import pack
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn
from civ6_host.runtime import xp1_city_purchases, xp1_plot_purchases, xp1_session_view, xp2_dedications
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native import native_saved_purchases
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue


class RiseAndFallCityPurchaseTests(unittest.TestCase):
    def test_adds_gold_items_while_retaining_plot_offers_and_checkpoint(self):
        observation, prior = expansion_catalogue()
        actor, turn = observation['player_id'], observation['turn']
        dedication = xp2_dedications.parse_state(f'{actor}|{turn}|0|normal|0'.encode(), actor, turn)
        with patch.object(xp2_dedications, 'catalogue', return_value=dedication):
            xp1_session_view._add_dedications(None, observation, prior, actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        city, = observation['cities']
        city_id = city['id']
        tile = dict(kind='purchase', city_id=city_id, plot_id=0, x=0, y=0,
                    currency='YIELD_GOLD', price_token='40')
        scout = dict(kind='purchase', city_id=city_id, category='unit', index=20, hash=32,
                     item_type='UNIT_SCOUT', currency='YIELD_GOLD', price_token='60')
        granary = dict(kind='purchase', city_id=city_id, category='building', index=3, hash=77,
                       item_type='BUILDING_GRANARY', currency='YIELD_GOLD', price_token='130')
        missionary = dict(kind='purchase', city_id=city_id, category='unit', index=55, hash=99,
                          item_type='UNIT_MISSIONARY', currency='YIELD_FAITH', price_token='75')

        def quotes(*actions):
            return [dict(player_id=actor, turn=turn, city_id=city_id, offers=[
                dict(action=action, command_legal=True, can_afford=action != granary) for action in actions])]

        current = deepcopy(prior)
        faith = deepcopy(prior)
        with (patch.object(xp1_plot_purchases, 'catalogue', return_value=quotes(tile)),
              patch.object(xp1_city_purchases, 'catalogue', return_value=quotes(scout, granary))):
            xp1_session_view._add_xp1_plot_purchases(None, observation, prior, acting=True, actions_closed=False)
            xp1_session_view._add_xp1_plot_purchases(SimpleNamespace(xp1_city_purchase=True), observation,
                                                     current, acting=True, actions_closed=False)
        with (patch.object(xp1_plot_purchases, 'catalogue', return_value=quotes(tile)),
              patch.object(xp1_city_purchases, 'catalogue', return_value=quotes(scout, granary, missionary))):
            xp1_session_view._add_xp1_plot_purchases(
                SimpleNamespace(xp1_city_purchase=True, xp1_faith_purchase=True), observation,
                faith, acting=True, actions_closed=False)
        seal(prior)
        seal(current)
        self.assertEqual([row['action'] for row in current['candidates'] if row['action']['kind']=='purchase'],
                         [tile, scout])
        self.assertEqual(current['city_purchases'], quotes(scout, granary))
        projected, receipt = network_turn.checkpoint_catalogue(current, prior, observation,
                                                               core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(receipt['added_public_fields'], ['city_purchases'])
        seal(faith)
        self.assertEqual([row['action'] for row in faith['candidates'] if row['action']['kind']=='purchase'],
                         [tile, scout, missionary])
        projected, receipt = network_turn.checkpoint_catalogue(faith, current, observation,
                                                               core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected, current)
        self.assertEqual(receipt['added_action_families'], ['faith_unit_building_purchase'])

    def test_archive_requires_exact_mode_item_formation_and_currency(self):
        header = pack('<IHH5I', 0x346b0a13, 0, 2, 65536, 0, 0, 1, 0)
        for category, name, fields in (
                ('unit','UNIT_SCOUT',[0,20,0xffffffff,2,0xffffd8f1,0xffffd8f1]),
                ('building','BUILDING_GRANARY',[1,3,2,0xffffd8f1,0xffffd8f1])):
            action = dict(kind='purchase', city_id=65536, category=category, index=fields[1], hash=32,
                          item_type=name, currency='YIELD_GOLD', price_token='60')
            archive = header + pack(f'<{len(fields)}I', *fields)
            self.assertEqual(xp1_city_purchases.validate_archive(archive, 0, action), sha256(archive).hexdigest())
            for offset in (4, 12, 28, 32, 36, len(archive)-4):
                altered = bytearray(archive)
                altered[offset] ^= 1
                with self.assertRaisesRegex(ValueError, 'differs from the selected item'):
                    xp1_city_purchases.validate_archive(bytes(altered), 0, action)

    def test_gold_only_lua_requests_no_faith_quote(self):
        gold = native_saved_purchases.catalog_source(0, 65536, 22, gold_only=True)
        legacy = native_saved_purchases.catalog_source(0, 65536, 22)
        self.assertIn(b"ipairs({'YIELD_GOLD'})", gold)
        self.assertIn(b"ipairs({'YIELD_GOLD','YIELD_FAITH'})", legacy)

    def test_faith_archive_is_explicit_and_uses_its_own_currency_index(self):
        header = pack('<IHH5I', 0x346b0a13, 0, 2, 65536, 0, 0, 1, 0)
        for category, name, tail in (
                ('unit', 'UNIT_MISSIONARY', pack('<IIiIii', 0, 55, -1, 5, -9999, -9999)),
                ('building', 'BUILDING_MONUMENT', pack('<IIIii', 1, 55, 5, -9999, -9999))):
            action = dict(kind='purchase', city_id=65536, category=category, index=55, hash=99,
                          item_type=name, currency='YIELD_FAITH', price_token='75')
            archive = header + tail
            with self.assertRaises(ValueError):
                xp1_city_purchases.validate_archive(archive, 0, action)
            self.assertEqual(xp1_city_purchases.validate_archive(archive, 0, action, allow_faith=True),
                             sha256(archive).hexdigest())
            with self.assertRaisesRegex(ValueError, 'differs from the selected item'):
                xp1_city_purchases.validate_archive(archive, 0, dict(action, currency='YIELD_GOLD'),
                                                    allow_faith=True)


if __name__ == '__main__':
    unittest.main()

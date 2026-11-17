from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import information, network_turn, trade, trade_overview
from civ6_host.runtime import xp1_session_view, xp1_trade_source, xp2_dedications, xp2_trade
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.xp1_saved_load import REFERENCE
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue


class RiseAndFallTradeTests(unittest.TestCase):
    def test_two_trade_families_and_old_checkpoint_comparison(self):
        observation, original = expansion_catalogue()
        actor, turn = observation['player_id'], observation['turn']
        dedication = xp2_dedications.parse_state(f'{actor}|{turn}|0|normal|0'.encode(), actor, turn)
        with patch.object(xp2_dedications, 'catalogue', return_value=dedication):
            xp1_session_view._add_dedications(None, observation, original, actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        seal(original)
        city = observation['cities'][0]
        unit = next(u for u in observation['units'] if u['owner'] == actor)
        boundary = {key: observation[key] for key in ('player_id', 'turn', 'width', 'height')}
        quote = dict(values=[1], majority_religion=-1, religion_pressure=0, path_bonus=False, tooltip='')
        destination = dict(owner=4, city_id=3, x=0, y=0, name='Port', path=[0],
            portal_entrances=[], portal_exits=[], repeat_route=False, can_confirm=True,
            has_post=False, origin_yields=quote, destination_yields=quote)
        routes = dict(**boundary, traders=[dict(unit_id=unit['id'], x=unit['x'], y=unit['y'],
            origin_owner=actor, origin_city=city['id'], destinations=[destination])], active_routes=[])
        origins = dict(**boundary, units=[])
        current = deepcopy(original)
        current['schema'] = network_turn.CAPABILITY_XP1_TRADE_SCHEMA
        xp1_session_view._add_trade(current, dict(trade_routes=routes, trade_origins=origins), actions_closed=False)
        seal(current)
        public = information.project('trade', observation, current)
        self.assertEqual(public, dict(schema=trade.GROUP_SCHEMA, player_id=actor, turn=turn,
                                      routes=routes, origins=origins))
        action, = trade.route_actions(routes)
        self.assertEqual(network_turn.select_capability(current, {
            'decision_id': current['decision_id'], 'candidate_id': network_turn.digest(action)}), action)
        projected, transition = network_turn.checkpoint_catalogue(
            current, original, observation, core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected, original)
        self.assertEqual(transition['added_action_families'], ['make_trade_route', 'change_trade_origin'])
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(current, original, observation, core_sha256=XP2_CORE_SHA256)
        from civ6_host.runtime.network_checkpoint import _semantic_decisions
        panel = dict(schema=trade_overview.SCHEMA, profile=trade_overview.STOCK_PROFILE,
                     player_id=actor, turn=turn, sequence=current['sequence'], active_count=0,
                     capacity=1, idle_trader_ids=[unit['id']], produce_trader_slots=0,
                     own_routes=[], incoming_routes=[], available_routes=[])
        upgraded = network_turn.upgrade_trade_overview_catalogue(
            current, panel, observation=observation, status='available')
        self.assertEqual(information.project('trade_overview', observation, upgraded), panel)
        self.assertEqual(information.project('trade', observation, upgraded), public)
        previous, changes = network_turn.checkpoint_catalogue(
            upgraded, current, observation, core_sha256=XP1_CORE_SHA256)
        self.assertEqual(previous, current)
        self.assertEqual(changes['added_public_fields'], ['trade_overview', 'trade_overview_status'])
        rebound = deepcopy(upgraded)
        rebound['sequence'] += 1
        rebound['trade_overview']['sequence'] += 1
        seal(rebound)
        self.assertEqual(_semantic_decisions(upgraded, observation), _semantic_decisions(rebound, observation))
        rebound['trade_overview']['capacity'] += 1
        self.assertNotEqual(_semantic_decisions(upgraded, observation), _semantic_decisions(rebound, observation))
        current['families']['change_trade_origin'] = dict(status='unqualified', reason='skipped')
        seal(current)
        with self.assertRaisesRegex(ValueError, 'trade family'):
            network_turn.checkpoint_catalogue(current, original, observation, core_sha256=XP1_CORE_SHA256)

    def test_stock_route_requires_exact_capture_and_both_readers(self):
        self.assertTrue(xp1_trade_source.supports(REFERENCE, _XP1_PROFILE))
        self.assertIn(xp1_trade_source.SOURCE[1], xp1_trade_source.source_dependencies(_XP1_PROFILE).values())
        observation = dict(player_id=0, turn=22)
        transport = SimpleNamespace(require_empty_native_queue=lambda: None)
        continuation = SimpleNamespace(sequence=1, observation=observation, transport=transport)
        backend = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            core=SimpleNamespace(_civ6_host_execution_image=_XP1_PROFILE),
            captured_bundle=SimpleNamespace(reference=REFERENCE), control=lambda **_: None)
        saved = SimpleNamespace(xp1_trade=False)
        with patch.object(xp2_trade, '_owner', return_value=(backend, continuation, object(), object())):
            with self.assertRaisesRegex(ValueError, 'exact stock'):
                xp2_trade.catalogue(saved, observation)
            saved.xp1_trade = True
            with self.assertRaisesRegex(ValueError, 'exact stock'):
                xp2_trade.catalogue(saved, observation, include_origins=False)


if __name__ == '__main__':
    unittest.main()

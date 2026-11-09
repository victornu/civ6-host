"""Synthetic v34 trade protocol checks over the retained native v31 base."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn, trade


class XP2TradeProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_initial_diplomacy_capabilities import InitialDiplomacyCapabilityTests
        cls.fixture = InitialDiplomacyCapabilityTests()
        cls.fixture.setUpClass()

    def _active(self):
        value, obs, _ = self.fixture._fixture().v32()
        value['schema'] = network_turn.CAPABILITY_XP2_TRADE_SCHEMA
        value['diplomacy_overview'] = self.fixture._overview(player_id=value['player_id'], turn=value['turn'])
        from test_initial_diplomacy_capabilities import UNQUALIFIED_INITIAL
        value['families']['diplomacy_initiate'] = dict(status='queried_partial', candidate_ids=[],
                                                        unqualified=list(UNQUALIFIED_INITIAL))
        pid, turn = value['player_id'], value['turn']
        obs['units'] = [dict(id=9, owner=pid, x=0, y=0)]
        obs['cities'] = [dict(id=11, owner=pid, x=0, y=0), dict(id=12, owner=pid, x=2, y=0)]
        obs['width'], obs['height'] = 3, 2
        boundary = dict(player_id=pid, turn=turn, width=3, height=2)
        quote = dict(values=[1.0], majority_religion=-1, religion_pressure=0.0,
                     path_bonus=False, tooltip='')
        destination = dict(owner=pid, city_id=12, x=2, y=0, name='Port', path=[0, 1, 2],
            portal_entrances=[], portal_exits=[], repeat_route=False, can_confirm=True,
            has_post=False, origin_yields=deepcopy(quote), destination_yields=deepcopy(quote))
        routes = dict(**boundary, traders=[dict(unit_id=9, x=0, y=0, origin_owner=pid,
            origin_city=11, destinations=[destination])], active_routes=[])
        target = dict(city_id=12, x=2, y=0, plot_id=2, name='Port')
        origins = dict(**boundary, units=[dict(unit_id=9, origin_city=11, x=0, y=0,
            available=True, targets=[target], map_targets=[2])])
        value['trade_routes'], value['trade_origins'] = routes, origins
        actions = trade.route_actions(routes) + trade.origin_actions(origins)
        rows = [dict(candidate_id=network_turn.digest(a), action=a) for a in actions]
        value['candidates'].extend(rows)
        for kind in ('make_trade_route', 'change_trade_origin'):
            ids = [row['candidate_id'] for row in rows if row['action']['kind'] == kind]
            value['families'][kind] = dict(status='queried_complete', candidate_ids=ids)
        value.pop('decision_id')
        value['decision_id'] = network_turn.digest(value)
        return value, obs

    def _validate(self, value, obs, *, closed=False):
        identity = SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation'])
        return network_turn.validate_capability_catalogue(value, identity, value['sequence'], value['turn'],
            player_id=value['player_id'], observation=obs, actions_closed=closed)

    def _seal(self, value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)

    def test_v34_requires_both_catalogues_and_exact_offered_action_coverage(self):
        value, obs = self._active()
        self._validate(value, None)
        bad = deepcopy(value)
        bad['candidates'] = [r for r in bad['candidates'] if r['action']['kind'] != 'make_trade_route']
        bad['families']['make_trade_route']['candidate_ids'] = []
        self._seal(bad)
        with self.assertRaisesRegex(ValueError, 'native catalogue'):
            self._validate(bad, None)
        bad = deepcopy(value)
        bad['trade_origins'] = None
        self._seal(bad)
        with self.assertRaisesRegex(ValueError, 'acting boundary'):
            self._validate(bad, None)

    def test_waiting_and_closed_v34_trade_fields_are_explicitly_unknown(self):
        value, obs = self._active()
        waiting, wait_obs, _ = self.fixture._fixture().v32(state='waiting')
        waiting['schema'] = network_turn.CAPABILITY_XP2_TRADE_SCHEMA
        waiting['diplomacy_overview'] = None
        waiting['families']['diplomacy_initiate'] = dict(status='unqualified', reason='waiting for active player')
        waiting['governors'] = None
        for kind in ('appoint_governor', 'promote_governor', 'assign_governor', 'consider_governor_titles'):
            if kind in waiting['families']:
                waiting['families'][kind] = dict(status='unqualified', reason='waiting for active player')
        waiting['trade_routes'] = waiting['trade_origins'] = None
        forced = dict(kind='force_end_turn')
        waiting['candidates'] = [dict(candidate_id=network_turn.digest(forced), action=forced)]
        waiting['families']['force_end_turn'] = dict(status='queried_complete',
                                                       candidate_ids=[network_turn.digest(forced)])
        for kind in ('make_trade_route', 'change_trade_origin'):
            waiting['families'][kind] = dict(status='unqualified', reason='waiting for active player')
        self._seal(waiting)
        self._validate(waiting, None)

        self.assertIsNone(waiting['trade_routes'])
        self.assertIsNone(waiting['trade_origins'])

    def test_v34_remains_readable_through_public_trade_information_group(self):
        from civ6_host.contracts import information
        value, obs = self._active()
        projection = information.project('trade', obs, value)
        self.assertEqual(projection['routes'], value['trade_routes'])
        self.assertEqual(projection['origins'], value['trade_origins'])

    def test_checkpoint_comparison_projects_only_trade_fields_and_candidates(self):
        value, obs = self._active()
        saved = deepcopy(value)
        saved['schema'] = network_turn.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA
        for field in ('trade_routes', 'trade_origins'):
            del saved[field]
        for kind in ('make_trade_route', 'change_trade_origin'):
            del saved['families'][kind]
        saved['candidates'] = [row for row in saved['candidates']
                               if row['action']['kind'] in saved['families']]
        self._seal(saved)
        # The tiny protocol fixture has trade units/cities only. The native
        # readback test supplies the other families' full observations.
        def validate_trade_protocol(current, identity, sequence, turn, *, player_id, observation):
            validate(current, identity, sequence, turn, player_id=player_id)

        validate = network_turn.validate_capability_catalogue
        with patch.object(network_turn, 'validate_capability_catalogue', validate_trade_protocol):
            projection, evidence = network_turn.checkpoint_catalogue(
                value, saved, obs, core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(projection, saved)
        self.assertEqual(evidence['added_public_fields'], ['trade_routes', 'trade_origins'])
        self.assertEqual(evidence['added_action_families'], ['make_trade_route', 'change_trade_origin'])


if __name__ == '__main__':
    unittest.main()

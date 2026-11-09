"""Synthetic v35 espionage integration over retained native public v31 data."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, SessionClient
from civ6_host.client import ProtocolError
from civ6_host.contracts import espionage, information, network_turn

import test_initial_diplomacy_capabilities as initial_diplomacy_fixtures
from test_session_client import Backend as SessionBackend


class EspionageClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initial_diplomacy_fixtures.InitialDiplomacyCapabilityTests.setUpClass()
        cls.initial = initial_diplomacy_fixtures.InitialDiplomacyCapabilityTests()

    @staticmethod
    def _seal(value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)

    def _v34(self, state='reset'):
        if state == 'reset':
            value, observation = self.initial._active_v33()
            # This retained boundary has no units. Add one synthetic spy to
            # every existing all-unit query, so the full v34 validators still
            # compare the same owned roster before espionage is enabled.
            self.assertEqual(observation['units'], [])
            plot = observation['plots'][0]
            unit_id, x, y = 9, plot['x'], plot['y']
            observation['units'] = [dict(id=unit_id, type=91, owner=observation['player_id'],
                x=x, y=y, damage=0, moves=0, max_moves=2)]
            value['world_input']['units'] = [dict(unit_id=unit_id, ignore_moves=True)]
            value['queued_orders']['units'] = [dict(unit_id=unit_id, plot_id=None)]
            value['unit_orders']['units'] = [dict(unit_id=unit_id, activity_type=0,
                                                fortify_turns=0, ready=False)]
            value['unit_attacks']['units'] = [dict(unit_id=unit_id, unit_type=91,
                x=x, y=y, damage=0, moves=0, attacks_remaining=0)]
            value['unit_promotions']['units'] = [dict(unit_id=unit_id,
                experience_points=0, promotions=[])]
            terrain = dict(unit_id=unit_id, plot_id=plot['index'], improvement=-1,
                           improvement_pillaged=False, route=-1, route_pillaged=False)
            value['unit_work_state']['units'] = [dict(**terrain, charges=0, moves_token='0')]
            value['unit_work_info']['targets'] = [deepcopy(terrain)]
        else:
            value, observation, _ = self.initial._fixture().v32(state, available=False)
            value['diplomacy_overview'] = None
            value['families']['diplomacy_initiate'] = dict(
                status='unqualified', reason='native_acting_boundary_unavailable')
        value['schema'] = network_turn.CAPABILITY_XP2_TRADE_SCHEMA
        available = state == 'reset'
        boundary = {key: observation[key] for key in ('player_id', 'turn', 'width', 'height')}
        value['trade_routes'] = dict(**boundary, traders=[], active_routes=[]) if available else None
        value['trade_origins'] = dict(**boundary, units=[]) if available else None
        for kind in ('make_trade_route', 'change_trade_origin'):
            value['families'][kind] = (dict(status='queried_complete', candidate_ids=[])
                if available else dict(status='unqualified', reason='native_acting_boundary_unavailable'))
        self._seal(value)
        return value, observation

    def _espionage(self, observation):
        unit = observation['units'][0]
        width, height = observation['width'], observation['height']
        x, y = unit['x'], 1 if height > 1 else 0
        actions = [
            dict(kind='spy_travel', unit_id=unit['id'], city_owner=1,
                 city_id=41, x=x, y=y),
            dict(kind='spy_mission', unit_id=unit['id'], operation_type='UNITOPERATION_SPY_STEAL_TECH_BOOST',
                 operation_hash=0xf0000011, mode='start', x=x, y=y, plot_id=y * width + x),
            dict(kind='spy_cancel', unit_id=unit['id']),
            dict(kind='spy_escape', unit_id=unit['id'], district_index=2),
        ]
        return dict(schema=espionage.SCHEMA, player_id=observation['player_id'],
            turn=observation['turn'], width=width, height=height, capacity=1,
            spies=[dict(unit_id=unit['id'], name='Ada', level=1, x=unit['x'], y=unit['y'],
                        operation=-1, turns_remaining=-1)],
            captured=[], off_map=[], history=[],
            offers=[dict(action=action, turns=-1, success_percent=-1, failure_percent=-1,
                         captured_or_killed_percent=-1) for action in actions])

    def _v35(self, state='reset'):
        value, observation = self._v34(state)
        catalogue = self._espionage(observation) if state == 'reset' else None
        return network_turn.upgrade_espionage_catalogue(value, catalogue, observation), observation

    @staticmethod
    def _validate(value, observation, *, closed=False):
        return network_turn.validate_capability_catalogue(value,
            SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation']),
            value['sequence'], value['turn'], player_id=value['player_id'],
            actions_closed=closed, observation=observation)

    def test_opt_in_preserves_v34_and_copies_all_native_offers(self):
        old, observation = self._v34()
        before = deepcopy(old)
        self._validate(old, observation)
        catalogue = self._espionage(observation)
        current = network_turn.upgrade_espionage_catalogue(old, catalogue, observation)
        self._validate(current, observation)
        self.assertEqual(old, before)
        self.assertNotIn('espionage', old)
        self.assertFalse(current['complete_action_space'])
        for kind in espionage.ACTION_FIELDS:
            self.assertEqual(current['families'][kind]['status'], 'queried_partial')
            self.assertEqual(current['families'][kind]['unqualified'],
                             ['spy_completion_repeat_pending_identity'])
        self.assertEqual(current['candidates'][:len(old['candidates'])], old['candidates'])
        self.assertEqual([row['action'] for row in current['candidates'][len(old['candidates']):]],
                         espionage.actions(catalogue))
        catalogue['spies'][0]['name'] = 'Changed'
        self.assertEqual(current['espionage']['spies'][0]['name'], 'Ada')

    def test_old_revision_rejects_new_field_and_new_actions(self):
        old, observation = self._v34()
        changed = deepcopy(old)
        changed['espionage'] = self._espionage(observation)
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)
        current, _ = self._v35()
        current['schema'] = network_turn.CAPABILITY_XP2_TRADE_SCHEMA
        del current['espionage']
        self._seal(current)
        with self.assertRaises(ValueError):
            self._validate(current, observation)

    def test_v35_requires_exact_offers_and_own_public_provenance(self):
        value, observation = self._v35()
        changed = deepcopy(value)
        changed['families']['spy_mission']['status'] = 'queried_complete'
        del changed['families']['spy_mission']['unqualified']
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)
        changed = deepcopy(value)
        changed['candidates'] = [row for row in changed['candidates']
                                 if row['action']['kind'] != 'spy_cancel']
        changed['families']['spy_cancel']['candidate_ids'] = []
        self._seal(changed)
        with self.assertRaisesRegex(ValueError, 'Espionage candidates'):
            self._validate(changed, observation)
        changed = deepcopy(value)
        changed['espionage']['player_id'] = 1
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)
        changed = deepcopy(value)
        changed['espionage']['spies'][0]['unit_id'] = 0xffffffff
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)

    def test_waiting_and_closed_queries_are_unknown_and_have_no_spy_choices(self):
        for state in ('waiting', 'close'):
            with self.subTest(state=state):
                value, observation = self._v35(state)
                self._validate(value, observation, closed=state == 'close')
                self.assertIsNone(value['espionage'])
                self.assertTrue(all(value['families'][kind]['status'] == 'unqualified'
                                    for kind in espionage.ACTION_FIELDS))
                self.assertFalse(any(row['action']['kind'] in espionage.ACTION_FIELDS
                                     for row in value['candidates']))
                with self.assertRaises(ValueError):
                    information.project('espionage', observation, value)

    def test_checkpoint_transition_removes_only_the_new_comparison_fields(self):
        old, observation = self._v34()
        old_before = deepcopy(old)
        current = network_turn.upgrade_espionage_catalogue(old, self._espionage(observation), observation)
        current_before = deepcopy(current)
        comparable, transition = network_turn.checkpoint_catalogue(
            current, old, observation, core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(comparable, old)
        self.assertEqual(old, old_before)
        self.assertEqual(current, current_before)
        self.assertEqual(transition['added_public_fields'], ['espionage'])
        self.assertEqual(transition['added_action_families'], list(espionage.ACTION_FIELDS))
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(current, old, observation, core_sha256='0' * 64)

    def _client(self, *, enabled=True):
        fixture = self

        class Backend(SessionBackend):
            def _reply(self, operation, sequence, **kwargs):
                response = super()._reply(operation, sequence, **kwargs)
                value, observation = fixture._v35() if enabled else fixture._v34()
                self.turn = observation['turn']
                for key in ('episode_id', 'game_generation', 'sequence'):
                    value[key] = response[key]
                fixture._seal(value)
                response['session']['turn'] = self.turn
                response['observation'] = observation
                response['decisions'] = value
                return response

        backend = Backend()
        client = SessionClient(backend, allow_administrative=True)
        return client, backend, client.reset()

    def test_information_is_detached_cached_public_state_and_action_uses_exact_choice(self):
        client, backend, view = self._client()
        info = client.information('espionage')
        self.assertEqual(info['group'], 'espionage')
        self.assertEqual(info['data'], view['decisions']['espionage'])
        self.assertEqual(backend.calls, [])
        info['data']['spies'][0]['name'] = 'Changed'
        self.assertEqual(client.information('espionage')['data']['spies'][0]['name'], 'Ada')
        with self.assertRaises(InformationUnavailable):
            client.information('espionage', channel='administrative')
        candidate = next(row for row in view['decisions']['candidates']
                         if row['action']['kind'] == 'spy_mission')
        with self.assertRaises(ProtocolError):
            client.act(0, 'stale-decision', candidate['candidate_id'])
        self.assertEqual(backend.calls, [])
        result = client.act(0, view['decisions']['decision_id'], candidate['candidate_id'])
        self.assertEqual(result['applied_action'], candidate['action'])
        self.assertEqual(backend.calls[0]['selection'], dict(
            decision_id=view['decisions']['decision_id'], candidate_id=candidate['candidate_id']))

    def test_disabled_query_is_unavailable_and_malformed_requested_action_is_rejected(self):
        client, _, _ = self._client(enabled=False)
        with self.assertRaises(InformationUnavailable):
            client.information('espionage')
        client, backend, view = self._client()
        candidate = next(row for row in view['decisions']['candidates']
                         if row['action']['kind'] == 'spy_cancel')
        backend.fault = 'requested_type'
        with self.assertRaises(ProtocolError):
            client.act(0, view['decisions']['decision_id'], candidate['candidate_id'])
        self.assertTrue(backend.aborts)


if __name__ == '__main__':
    unittest.main()

"""Synthetic v36 completion choices over the complete v35 public fixture."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, SessionClient
from civ6_host.client import ProtocolError
from civ6_host.contracts import espionage, information, network_turn, spy_completion
import test_espionage_client as espionage_fixtures
from test_session_client import Backend as SessionBackend


class SpyCompletionClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        espionage_fixtures.EspionageClientTests.setUpClass()
        cls.spy = espionage_fixtures.EspionageClientTests()

    @staticmethod
    def _seal(value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)

    @staticmethod
    def _completion(observation, *, current=True):
        value = dict(schema=spy_completion.SCHEMA,
            **{key: observation[key] for key in ('player_id', 'turn', 'width', 'height')},
            current=None, offers=[])
        if not current:
            return value
        unit = observation['units'][0]
        x, y = unit['x'], 1 if observation['height'] > 1 else 0
        plot_id = y * observation['width'] + x
        identity = dict(event_sequence=19, mission_id=7)
        value['current'] = dict(**identity, name='Ada', level=1, operation=12,
            completion_turn=observation['turn'] - 1, initial_result=1, escape_result=-1,
            city_name='Paris', plot_id=plot_id, loot_info=25)
        actions = [dict(kind='spy_renew', unit_id=unit['id'], **identity,
            operation_type='UNITOPERATION_SPY_STEAL_TECH_BOOST', operation_hash=0xfedcba98,
            x=x, y=y, plot_id=plot_id), dict(kind='spy_completion_dismiss', **identity)]
        value['offers'] = [dict(action=action, turns=-1, success_percent=-1,
            failure_percent=-1, captured_or_killed_percent=-1) for action in actions]
        return value

    def _v36(self, state='reset', *, current=True):
        value, observation = self.spy._v35(state)
        completion = self._completion(observation, current=current) if state == 'reset' else None
        return network_turn.upgrade_spy_completion_catalogue(value, completion, observation), observation

    @staticmethod
    def _validate(value, observation, *, closed=False):
        return network_turn.validate_capability_catalogue(value,
            SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation']),
            value['sequence'], value['turn'], player_id=value['player_id'],
            actions_closed=closed, observation=observation)

    def test_v36_preserves_the_v35_input_and_revises_only_versioned_spy_gaps(self):
        old, observation = self.spy._v35()
        original = deepcopy(old)
        self._validate(old, observation)
        completion = self._completion(observation)
        current = network_turn.upgrade_spy_completion_catalogue(old, completion, observation)
        self._validate(current, observation)
        self.assertEqual(old, original)
        self.assertNotIn('spy_completion', old)
        self.assertFalse(current['complete_action_space'])
        self.assertEqual(current['candidates'][:len(old['candidates'])], old['candidates'])
        self.assertEqual([row['action'] for row in current['candidates'][len(old['candidates']):]],
                         spy_completion.actions(completion))
        for kind in (*espionage.ACTION_FIELDS, *spy_completion.ACTION_FIELDS):
            self.assertEqual(current['families'][kind]['status'], 'queried_partial')
            self.assertEqual(current['families'][kind]['unqualified'],
                ['spy_popup_interface_mode_lifetime', 'spy_notification_reactivation'])
        for kind in espionage.ACTION_FIELDS:
            self.assertEqual(old['families'][kind]['unqualified'],
                             ['spy_completion_repeat_pending_identity'])
        completion['current']['name'] = 'Changed'
        self.assertEqual(current['spy_completion']['current']['name'], 'Ada')

    def test_v35_rejects_new_fields_and_actions_and_v36_requires_exact_gap_metadata(self):
        old, observation = self.spy._v35()
        changed = deepcopy(old)
        changed['spy_completion'] = self._completion(observation)
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)
        current, _ = self._v36()
        changed = deepcopy(current)
        changed['schema'] = network_turn.CAPABILITY_XP2_ESPIONAGE_SCHEMA
        del changed['spy_completion']
        for kind in espionage.ACTION_FIELDS:
            changed['families'][kind]['unqualified'] = list(network_turn.ESPIONAGE_GAPS)
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)
        for kind in ('spy_mission', 'spy_renew', 'spy_completion_dismiss'):
            changed = deepcopy(current)
            changed['families'][kind]['unqualified'] = list(network_turn.ESPIONAGE_GAPS)
            self._seal(changed)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self._validate(changed, observation)
            with self.subTest(checkpoint=kind), self.assertRaises(ValueError):
                network_turn.checkpoint_catalogue(changed, old, observation,
                    core_sha256=network_turn._XP2_COMBAT_CORE)

    def test_current_offers_and_completion_identity_are_required_exactly(self):
        current, observation = self._v36()
        changed = deepcopy(current)
        changed['candidates'] = [row for row in changed['candidates']
                                 if row['action']['kind'] != 'spy_renew']
        changed['families']['spy_renew']['candidate_ids'] = []
        self._seal(changed)
        with self.assertRaisesRegex(ValueError, 'Spy completion candidates'):
            self._validate(changed, observation)
        changed = deepcopy(current)
        changed['spy_completion']['offers'][0]['action']['event_sequence'] += 1
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)
        changed = deepcopy(current)
        changed['families']['spy_renew']['status'] = 'queried_complete'
        del changed['families']['spy_renew']['unqualified']
        self._seal(changed)
        with self.assertRaises(ValueError):
            self._validate(changed, observation)

    def test_waiting_closed_and_empty_current_event_have_distinct_availability(self):
        active, observation = self._v36(current=False)
        self._validate(active, observation)
        self.assertIsNone(active['spy_completion']['current'])
        self.assertEqual(active['spy_completion']['offers'], [])
        self.assertEqual(information.project('spy_completion', observation, active),
                         active['spy_completion'])
        for state in ('waiting', 'close'):
            with self.subTest(state=state):
                value, observation = self._v36(state)
                self._validate(value, observation, closed=state == 'close')
                self.assertIsNone(value['spy_completion'])
                self.assertTrue(all(value['families'][kind]['status'] == 'unqualified'
                                    for kind in spy_completion.ACTION_FIELDS))
                with self.assertRaises(ValueError):
                    information.project('spy_completion', observation, value)

    def test_checkpoint_projection_restores_exact_v35_gaps_and_historical_fields(self):
        old, observation = self.spy._v35()
        current = network_turn.upgrade_spy_completion_catalogue(old, self._completion(observation), observation)
        old_before, current_before = deepcopy(old), deepcopy(current)
        projected, transition = network_turn.checkpoint_catalogue(
            current, old, observation, core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(projected, old)
        self.assertEqual(old, old_before)
        self.assertEqual(current, current_before)
        self.assertEqual(transition['added_public_fields'], ['spy_completion'])
        self.assertEqual(transition['added_action_families'], list(spy_completion.ACTION_FIELDS))
        self.assertEqual(transition['espionage_comparison_gaps'], list(network_turn.ESPIONAGE_GAPS))
        v34, _ = self.spy._v34()
        projected, transition = network_turn.checkpoint_catalogue(
            current, v34, observation, core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(projected, v34)
        self.assertEqual(transition['added_public_fields'], ['espionage', 'spy_completion'])
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(current, old, observation, core_sha256='0' * 64)

    def _client(self, *, enabled=True):
        fixture = self

        class Backend(SessionBackend):
            def _reply(self, operation, sequence, **kwargs):
                response = super()._reply(operation, sequence, **kwargs)
                value, observation = fixture._v36() if enabled else fixture.spy._v35()
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

    def test_information_is_public_detached_cached_and_retains_both_schema_identities(self):
        client, backend, view = self._client()
        result = client.information('spy_completion')
        self.assertEqual(result['group'], 'spy_completion')
        self.assertEqual(result['data'], view['decisions']['spy_completion'])
        self.assertEqual(result['source_contracts']['spy_completion'], spy_completion.SCHEMA)
        self.assertEqual(result['source_contracts']['decision_catalogue'],
                         network_turn.CAPABILITY_XP2_SPY_COMPLETION_SCHEMA)
        self.assertEqual(backend.calls, [])
        result['data']['current']['name'] = 'Changed'
        self.assertEqual(client.information('spy_completion')['data']['current']['name'], 'Ada')
        with self.assertRaises(InformationUnavailable):
            client.information('spy_completion', channel='administrative')
        older, _, _ = self._client(enabled=False)
        with self.assertRaises(InformationUnavailable):
            older.information('spy_completion')

    def test_explicit_renew_and_dismiss_use_current_offers_and_reject_stale_decisions(self):
        for kind in spy_completion.ACTION_FIELDS:
            with self.subTest(kind=kind):
                client, backend, view = self._client()
                candidate = next(row for row in view['decisions']['candidates']
                                 if row['action']['kind'] == kind)
                with self.assertRaises(ProtocolError):
                    client.act(0, 'stale-decision', candidate['candidate_id'])
                self.assertEqual(backend.calls, [])
                result = client.act(0, view['decisions']['decision_id'], candidate['candidate_id'])
                self.assertEqual(result['applied_action'], candidate['action'])
                self.assertEqual(backend.calls[0]['selection'], dict(
                    decision_id=view['decisions']['decision_id'], candidate_id=candidate['candidate_id']))

    def test_malformed_requested_completion_action_poisoning_is_preserved(self):
        for kind in spy_completion.ACTION_FIELDS:
            with self.subTest(kind=kind):
                client, backend, view = self._client()
                candidate = next(row for row in view['decisions']['candidates']
                                 if row['action']['kind'] == kind)
                backend.fault = 'requested_type'
                with self.assertRaises(ProtocolError):
                    client.act(0, view['decisions']['decision_id'], candidate['candidate_id'])
                self.assertTrue(backend.aborts)


if __name__ == '__main__':
    unittest.main()

"""Versioned Congress client composition with synthetic data; no GameCore."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, SessionClient
from civ6_host.client import ProtocolError
from civ6_host.contracts import information, network_turn, world_congress as congress
from test_world_congress_contract import catalogue, ballot_parameters
import test_spy_completion_client as previous_fixtures
from test_session_client import Backend as SessionBackend


class WorldCongressClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous_fixtures.SpyCompletionClientTests.setUpClass()
        cls.previous = previous_fixtures.SpyCompletionClientTests()

    def _v37(self, state='reset'):
        old, observation = self.previous._v36(state)
        data = catalogue(pid=old['player_id'], turn=old['turn'], sequence=old['sequence']) if state == 'reset' else None
        return network_turn.upgrade_world_congress_catalogue(old, data, observation), observation

    @staticmethod
    def _seal(value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)

    @staticmethod
    def _validate(value, observation, closed=False):
        return network_turn.validate_capability_catalogue(value,
            SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation']),
            value['sequence'], value['turn'], player_id=value['player_id'],
            observation=observation, actions_closed=closed)

    def test_v37_outside_session_appends_domains_without_mutating_v36(self):
        old, observation = self.previous._v36()
        before = deepcopy(old)
        data = catalogue('ordinary', pid=old['player_id'], turn=old['turn'], sequence=old['sequence'])
        current = network_turn.upgrade_world_congress_catalogue(old, data, observation)
        self._validate(current, observation)
        self.assertEqual(old, before)
        self.assertEqual(current['candidates'][:len(old['candidates'])], old['candidates'])
        self.assertFalse(current['complete_action_space'])
        for kind in congress.CANDIDATE_FIELDS:
            self.assertEqual(current['families'][kind]['status'], 'queried_partial')
            self.assertEqual(current['families'][kind]['unqualified'], list(congress.GAPS))
        data['proposals'][0]['name'] = 'External mutation'
        self.assertNotEqual(current['world_congress']['proposals'][0]['name'], 'External mutation')

    def test_in_session_read_only_candidates_removed_but_native_observations_retained(self):
        old, observation = self.previous._v36()
        before = deepcopy(old)
        data = catalogue(pid=old['player_id'], turn=old['turn'], sequence=old['sequence'])
        current = network_turn.upgrade_world_congress_catalogue(old, data, observation)
        self._validate(current, observation)
        readonly = network_turn.CONGRESS_READ_ONLY_KINDS
        removed = [r for r in old['candidates'] if r['action']['kind'] in readonly]
        self.assertTrue(removed)
        self.assertFalse(any(r['action']['kind'] in readonly for r in current['candidates']))
        for key in ('government', 'policies', 'policy_unlock', 'governors'):
            self.assertEqual(current[key], before[key])
        self.assertTrue(current['governors']['can_appoint'])
        self.assertEqual(old, before)
        for kind in readonly:
            self.assertTrue(network_turn.congress_action_read_only(current, kind))
            self.assertFalse(network_turn.congress_action_read_only(old, kind))
        for kind in ('research', 'civic', 'spy_mission', 'envoy_changes', 'congress_confirm_ballot'):
            self.assertFalse(network_turn.congress_action_read_only(current, kind))
        for action in [r['action'] for r in removed] + [
                dict(kind='retain_government', index=old['government']['current_index']),
                dict(kind='policies', slots=[]),
                dict(kind='policy_unlock', cost=0, currency='YIELD_GOLD')]:
            bad = deepcopy(current)
            row = dict(candidate_id=network_turn.digest(action), action=deepcopy(action))
            bad['candidates'].append(row)
            family = 'government' if action['kind'] == 'retain_government' else action['kind']
            bad['families'][family]['candidate_ids'].append(row['candidate_id'])
            self._seal(bad)
            with self.subTest(kind=action['kind']), self.assertRaisesRegex(ValueError, 'read-only'):
                self._validate(bad, observation)

    def test_old_version_foreign_sequence_missing_domain_and_completion_claim_refused(self):
        value, observation = self._v37()
        for change in ('old_revision', 'sequence', 'missing_candidate', 'complete'):
            bad = deepcopy(value)
            if change == 'old_revision': bad['schema'] = network_turn.CAPABILITY_XP2_SPY_COMPLETION_SCHEMA
            elif change == 'sequence': bad['world_congress']['sequence'] += 1
            elif change == 'missing_candidate':
                bad['candidates'] = [r for r in bad['candidates'] if r['action']['kind'] != 'congress_confirm_ballot']
                bad['families']['congress_confirm_ballot']['candidate_ids'] = []
            else:
                family = bad['families']['congress_confirm_ballot']
                family['status'] = 'queried_complete'; family.pop('unqualified')
            self._seal(bad)
            with self.subTest(change=change), self.assertRaises(ValueError): self._validate(bad, observation)

    def test_complete_form_selection_rejects_hidden_player_parameter(self):
        value, observation = self._v37()
        row = next(r for r in value['candidates'] if r['action']['kind'] == 'congress_confirm_ballot')
        picked = dict(decision_id=value['decision_id'], candidate_id=row['candidate_id'],
                      parameters=ballot_parameters(value['world_congress'], resolution_votes=2, discussion_votes=-2))
        actual = network_turn.select_capability(value, picked)
        self.assertEqual(actual, {**row['action'], **picked['parameters']})
        picked['parameters']['resolutions'][0]['target_player_id'] = 17
        with self.assertRaises(ValueError): network_turn.select_capability(value, picked)
        with self.assertRaises(ValueError): network_turn.select_capability(value,
            dict(decision_id=value['decision_id'], candidate_id=row['candidate_id']))

    def test_waiting_closed_and_checkpoint_read_only_intersection(self):
        for state in ('waiting', 'close'):
            value, observation = self._v37(state)
            self._validate(value, observation, closed=state == 'close')
            self.assertIsNone(value['world_congress'])
            with self.assertRaises(ValueError): information.project('world_congress', observation, value)
        current, observation = self._v37()
        old, _ = self.previous._v36()
        with self.assertRaisesRegex(ValueError, 'read-only action intersection'):
            network_turn.checkpoint_catalogue(current, old, observation, core_sha256=network_turn._XP2_COMBAT_CORE)
        data = catalogue('ordinary', pid=old['player_id'], turn=old['turn'], sequence=old['sequence'])
        outside = network_turn.upgrade_world_congress_catalogue(old, data, observation)
        projected, transition = network_turn.checkpoint_catalogue(outside, old, observation,
            core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(projected, old)
        self.assertTrue(transition['historical_fields_unchanged'])
        self.assertEqual(transition['added_public_fields'], ['world_congress'])

    def _client(self, stage='regular', presentation=None):
        fixture = self

        class Backend(SessionBackend):
            def request(self, request):
                self.selected = None
                if request['operation'] == 'act':
                    self.selected = network_turn.select_capability(self.current['decisions'], request['selection'])
                return super().request(request)

            def _reply(self, operation, sequence, **kwargs):
                nonlocal presentation
                if operation == 'act':
                    self.requested_action = deepcopy(self.selected)
                    if kwargs.get('status') == 'completed': kwargs['applied'] = deepcopy(self.selected)
                    if self.selected['kind'] == 'congress_open': presentation = 'available_proposals'
                    elif self.selected['kind'] == 'congress_close': presentation = 'closed'
                response = super()._reply(operation, sequence, **kwargs)
                old, observation = fixture.previous._v36('close' if operation == 'close' else 'reset')
                self.turn = observation['turn']
                for key in ('episode_id', 'game_generation', 'sequence'): old[key] = response[key]
                fixture._seal(old)
                data = None if operation == 'close' else catalogue(stage, pid=old['player_id'],
                    turn=old['turn'], sequence=sequence)
                if data is not None and presentation is not None:
                    data['presentation'] = presentation
                    opened = presentation == 'available_proposals'
                    data['offers'] = dict(open=not opened, confirm_ballot=False,
                        confirm_proposals=opened, close=opened)
                response['decisions'] = network_turn.upgrade_world_congress_catalogue(old, data, observation)
                response['observation'] = observation
                response['session']['turn'] = self.turn
                return response

        backend = Backend()
        client = SessionClient(backend)
        return client, backend, client.reset()

    def test_information_is_pure_and_explicit_open_uses_one_actor_command(self):
        client, backend, view = self._client('ordinary', 'closed')
        self.assertEqual(client.information('world_congress')['data']['presentation'], 'closed')
        self.assertEqual(backend.calls, [])
        decision = view['decisions']
        candidates = [r for r in decision['candidates'] if r['action']['kind'].startswith('congress_')]
        self.assertEqual([r['action']['kind'] for r in candidates], ['congress_open'])
        client.act(0, decision['decision_id'], candidates[0]['candidate_id'])
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(client.information('world_congress')['data']['presentation'], 'available_proposals')

    def test_cached_information_local_draft_and_pending_rpc_are_distinct(self):
        client, backend, view = self._client()
        value = view['decisions']['world_congress']
        info = client.information('world_congress')
        self.assertEqual(info['data'], value)
        info['data']['resolutions'][0]['name'] = 'External'
        self.assertNotEqual(client.information('world_congress')['data']['resolutions'][0]['name'], 'External')
        draft = client.congress_ballot_draft(0, ballot_parameters(value, resolution_votes=2, discussion_votes=-2))
        self.assertIs(draft['native_submission_issued'], False)
        self.assertEqual(backend.calls, [])
        backend.next_status = 'pending'
        decision = view['decisions']
        candidate = next(r for r in decision['candidates'] if r['action']['kind'] == 'congress_confirm_ballot')
        response = client.act(0, decision['decision_id'], candidate['candidate_id'],
                              parameters=ballot_parameters(value, resolution_votes=2, discussion_votes=-2))
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(client.command_result['status'], 'pending')
        self.assertIsNone(response['applied_action'])
        self.assertEqual(client.command_result['requested_action']['resolutions'][0]['target_index'], 1)

    def test_bad_selection_is_rejected_before_rpc(self):
        client, backend, view = self._client()
        decision = view['decisions']
        row = next(r for r in decision['candidates'] if r['action']['kind'] == 'congress_confirm_ballot')
        with self.assertRaises(ProtocolError):
            client.act(0, decision['decision_id'], row['candidate_id'],
                       parameters=dict(resolutions=[dict(resolution_hash=0xffffffff, option=1, target_index=True, votes=1)], discussions=[dict(discussion_index=0, votes=1)]))
        self.assertEqual(backend.calls, [])

    def test_substituted_concrete_receipt_is_rejected(self):
        client, backend, view = self._client()
        original = backend._reply
        def substitute(operation, sequence, **kwargs):
            response = original(operation, sequence, **kwargs)
            if operation == 'act':
                response['command_result']['requested_action']['resolutions'][0]['target_index'] = 0
            return response
        backend._reply = substitute
        decision = view['decisions']
        row = next(r for r in decision['candidates'] if r['action']['kind'] == 'congress_confirm_ballot')
        with self.assertRaisesRegex(ProtocolError, 'substituted'):
            client.act(0, decision['decision_id'], row['candidate_id'],
                       parameters=ballot_parameters(decision['world_congress']))


if __name__ == '__main__':
    unittest.main()

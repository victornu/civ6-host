import copy
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from civ6_host.client import ProtocolError, _digest
from civ6_host.session_client import SCHEMA, SessionClient
from civ6_host.contracts import policies


class Backend:
    def __init__(self):
        self.calls = []
        self.aborts = []
        self.next_status = 'completed'
        self.fault = None
        self.return_player = None

    def _reply(self, operation, sequence, *, pid, applied=None, status='none', reason=None,
               terminated=False, truncated=False):
        episode = self.episode
        generation = 'native-' + episode
        identity = dict(episode_id=episode, game_generation=generation, sequence=sequence)
        observation = dict(player_id=pid, turn=self.turn, cities=[], units=[])
        decisions = dict(**identity, player_id=pid, turn=self.turn, candidates=[
            dict(candidate_id=f'{pid}-move', action=dict(kind='move', unit_id=pid)),
            dict(candidate_id=f'{pid}-policies', action=dict(kind='policies', slots=[
                dict(slot=0, prior_index=-1, options=[
                    dict(index=2, hash=4294967295, native_hash=-1, policy_type='POLICY_FIXTURE')
                ])
            ])),
        ])
        if operation == 'close' or terminated or truncated:
            decisions['candidates'] = []
        decisions['decision_id'] = _digest(decisions)
        command = dict(status=status, reason=reason,
                       requested_action=self.requested_action if operation == 'act' else None)
        return dict(stage='official_session_response', schema=SCHEMA, nonce=self.nonce,
            **identity, operation=operation, observation=observation, rounds=0,
            outcome=dict(terminated=terminated, truncated=truncated,
                         reason='requested_close' if truncated else None,
                         native_victory={'internal_only': True}),
            automatic_choices_applied=False, action_interface_complete=False,
            strategic_training_ready=False, decisions=decisions, applied_action=applied,
            session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=self.turn,
                local_player_id=0, human_player_ids=[0, 1], active_human_player_ids=[0, 1]),
            command_result=command)

    def reset(self):
        self.episode = str(uuid4())
        self.nonce = uuid4().hex
        self.turn = 1
        self.seq = 0
        self.current = self._reply('reset', 0, pid=0)
        return copy.deepcopy(self.current)

    def request(self, request):
        self.calls.append(copy.deepcopy(request))
        if self.fault == 'lost':
            raise TimeoutError('reply lost after possible application')
        self.seq = request['sequence']
        self.requested_action = None
        applied = None
        status = 'none'
        reason = None
        operation = request['operation']
        pid = request['player_id']
        if operation == 'act':
            prior = self.current
            # The caller may submit a view retained across another actor's RPC.
            pid = request['player_id']
            candidate = request['selection']['candidate_id']
            self.requested_action = next(row['action'] for row in prior['decisions']['candidates']
                if row['candidate_id'] == candidate) if prior['observation']['player_id'] == pid else dict(kind='move', unit_id=pid)
            if self.requested_action['kind'] == 'policies':
                self.requested_action = dict(kind='policies', candidate=policies.choose(
                    self.requested_action['slots'], request['selection']['parameters']['assignments'], pid, self.turn))
            status = self.next_status
            reason = 'fixture-status' if status == 'refused' else None
            if status == 'completed':
                applied = self.requested_action
        returned_pid = self.return_player if self.return_player is not None else pid
        self.current = self._reply(operation, self.seq, pid=returned_pid, applied=applied,
                                   status=status, reason=reason,
                                   truncated=operation == 'close')
        result = copy.deepcopy(self.current)
        if self.fault == 'foreign_episode':
            result['episode_id'] = str(uuid4())
        elif self.fault == 'bool_player':
            result['session']['active_human_player_ids'] = [True, 1]
        elif self.fault == 'conflicting_action':
            result['command_result']['status'] = 'refused'
            result['applied_action'] = dict(kind='move', unit_id=pid)
        elif self.fault == 'extra_private':
            result['private_sidecar'] = {'enemy_gold': 55}
        elif self.fault == 'foreign_requested_action':
            result['command_result']['requested_action'] = {'kind': 'move', 'unit_id': 63}
        elif self.fault == 'foreign_policy_assignment':
            result['command_result']['requested_action']['candidate']['assignments'] = [[0, 7]]
        elif self.fault in ('requested_type', 'applied_type'):
            record = (result['command_result']['requested_action'] if self.fault == 'requested_type'
                      else result['applied_action'])
            record['unit_id'] = False
        return result

    def abort(self, reason):
        self.aborts.append(reason)


class SessionClientTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.client = SessionClient(self.backend)
        self.initial = self.client.reset()

    def test_multi_actor_catalogues_survive_global_revision(self):
        d0 = self.initial['decisions']
        view1 = self.client.observe(1)
        d1 = view1['decisions']
        self.assertEqual(view1['sequence'], 1)
        self.assertEqual(set(self.backend.calls[-1]),
            {'schema', 'nonce', 'episode_id', 'game_generation', 'sequence', 'operation', 'player_id'})
        self.assertNotIn('selection', self.backend.calls[-1])
        self.assertEqual(self.client.view(0)['decisions']['decision_id'], d0['decision_id'])
        self.assertEqual(self.client.view(1)['decisions']['decision_id'], d1['decision_id'])
        moved = self.client.act(0, d0['decision_id'], '0-move')
        self.assertEqual(self.backend.calls[-1]['sequence'], 2)
        self.assertEqual(self.backend.calls[-1]['player_id'], 0)
        self.assertEqual(self.backend.calls[-1]['selection']['candidate_id'], '0-move')
        self.assertEqual(set(self.backend.calls[-1]),
            {'schema', 'nonce', 'episode_id', 'game_generation', 'sequence', 'operation', 'player_id', 'selection'})
        self.assertEqual(moved['sequence'], 2)
        self.assertEqual(self.client.view(1)['decisions']['decision_id'], d1['decision_id'])

    def test_next_turn_discards_other_actors_catalogue_without_rpc(self):
        prior = self.client.observe(1)['decisions']
        self.backend.turn = 2
        self.client.poll(0)
        sent = len(self.backend.calls)
        with self.assertRaisesRegex(RuntimeError, 'No cached actor view'):
            self.client.view(1)
        with self.assertRaisesRegex(ProtocolError, 'No cached catalogue'):
            self.client.act(1, prior['decision_id'], '1-move')
        self.assertEqual(len(self.backend.calls), sent)
        self.assertEqual(self.backend.aborts, [])
        self.assertEqual(self.client.observe(1)['observation']['turn'], 2)

    def test_action_receipts_keep_their_actor_and_sequence_across_other_replies(self):
        self.backend.next_status = 'submitted'
        self.client.act(0, self.initial['decisions']['decision_id'], '0-move')
        second = self.client.observe(1)
        self.backend.next_status = 'refused'
        self.client.act(1, second['decisions']['decision_id'], '1-move')
        self.backend.turn = 2
        self.client.poll(1)
        first_receipt = self.client.last_command_receipt(0)
        second_receipt = self.client.last_command_receipt(1)
        self.assertEqual(first_receipt, dict(schema='civ6-host.command-receipt.v1',
            episode_id=self.initial['episode_id'], game_generation=self.initial['game_generation'],
            player_id=0, sequence=1, decision_turn=1, response_turn=1,
            selection=dict(decision_id=self.initial['decisions']['decision_id'], candidate_id='0-move'),
            command_result=dict(status='submitted', reason=None,
                                requested_action=self.initial['decisions']['candidates'][0]['action'])))
        self.assertEqual((second_receipt['player_id'], second_receipt['sequence']), (1, 3))
        self.assertEqual(second_receipt['command_result']['status'], 'refused')
        first_receipt['selection'].clear()
        self.assertEqual(self.client.last_command_receipt(0)['selection']['candidate_id'], '0-move')
        self.assertEqual(self.client.command_result['status'], 'none')
        self.client.reset()
        self.assertIsNone(self.client.last_command_receipt(0))

    def test_action_reply_cannot_return_another_actors_view(self):
        self.backend.return_player = 1
        with self.assertRaisesRegex(ProtocolError, 'another actor'):
            self.client.act(0, self.initial['decisions']['decision_id'], '0-move')
        self.assertEqual(self.backend.aborts, ['session_client_exchange_failed'])

    def test_reset_starts_a_fresh_episode_and_global_sequence(self):
        previous = self.client.view()
        current = self.client.reset()
        self.assertEqual(current['sequence'], 0)
        self.assertNotEqual(current['episode_id'], previous['episode_id'])

    def test_actor_view_and_admin_state_are_detached_and_separate(self):
        view = self.client.view()
        self.assertEqual(view['turn_mode'], 'simultaneous')
        self.assertNotIn('session', view)
        self.assertNotIn('nonce', view)
        self.assertNotIn('native_victory', view['outcome'])
        self.assertNotIn('command_result', view)
        state = self.client.session_state
        state['human_player_ids'].clear()
        self.assertEqual(self.client.session_state['human_player_ids'], [0, 1])
        view['observation']['player_id'] = 42
        self.assertEqual(self.client.view(0)['observation']['player_id'], 0)

    def test_session_rejects_foreign_identity_and_boolean_ids(self):
        for fault in ('foreign_episode', 'bool_player', 'extra_private'):
            with self.subTest(fault=fault):
                self.client.reset()
                self.backend.fault = fault
                with self.assertRaises(ProtocolError):
                    self.client.observe(1)
                self.backend.fault = None
        with self.assertRaises(ProtocolError):
            self.client.observe(True)

    def test_conflicting_command_and_applied_action_are_rejected(self):
        self.backend.fault = 'conflicting_action'
        d = self.initial['decisions']
        with self.assertRaises(ProtocolError):
            self.client.act(0, d['decision_id'], '0-move')
        self.assertTrue(self.backend.aborts)

    def test_action_receipt_cannot_substitute_boolean_for_integer(self):
        for fault in ('requested_type', 'applied_type'):
            with self.subTest(fault=fault):
                decisions = self.client.reset()['decisions']
                self.backend.fault = fault
                with self.assertRaisesRegex(ProtocolError, 'action differs'):
                    self.client.act(0, decisions['decision_id'], '0-move')

    def test_refused_and_pending_never_claim_applied_action(self):
        d = self.initial['decisions']
        for status in ('refused', 'pending', 'submitted'):
            with self.subTest(status=status):
                self.client.reset()
                d = self.client.view(0)['decisions']
                self.backend.next_status = status
                view = self.client.act(0, d['decision_id'], '0-move')
                self.assertIsNone(view['applied_action'])
                self.assertEqual(self.client.command_result['status'], status)
        self.backend.next_status = 'completed'

    def test_policy_parameters_and_invalid_parameters(self):
        decisions = self.initial['decisions']
        with self.assertRaises(ProtocolError):
            self.client.act(0, decisions['decision_id'], '0-policies')
        self.assertEqual(self.backend.calls, [])
        params = {'assignments': [4294967295]}
        self.client.act(0, decisions['decision_id'], '0-policies', params)
        self.assertEqual(self.backend.calls[-1]['selection']['parameters'], params)
        self.assertEqual(self.client.view()['applied_action']['kind'], 'policies')
        self.assertEqual(self.client.view()['applied_action']['candidate']['assignments'], [[0, -1]])
        self.backend.fault = 'foreign_policy_assignment'
        decisions = self.client.view()['decisions']
        with self.assertRaisesRegex(ProtocolError, 'Policy choice was substituted'):
            self.client.act(0, decisions['decision_id'], '0-policies', params)

    def test_refused_action_receipt_cannot_name_another_choice(self):
        self.backend.next_status = 'refused'
        self.backend.fault = 'foreign_requested_action'
        decisions = self.initial['decisions']
        with self.assertRaisesRegex(ProtocolError, 'Requested action differs'):
            self.client.act(0, decisions['decision_id'], '0-move')

    def test_uncertain_transport_aborts_without_retry(self):
        decisions = self.initial['decisions']
        self.backend.fault = 'lost'
        with self.assertRaises(TimeoutError):
            self.client.act(0, decisions['decision_id'], '0-move')
        self.assertEqual(len(self.backend.calls), 1)
        self.assertTrue(self.backend.aborts)

    def test_close_defaults_to_last_actor(self):
        self.client.observe(1)
        closed = self.client.close()
        self.assertEqual(self.backend.calls[-1]['operation'], 'close')
        self.assertEqual(self.backend.calls[-1]['player_id'], 1)
        self.assertTrue(closed['outcome']['truncated'])

    def test_inactive_human_can_submit_native_unready_catalogue(self):
        class WaitingBackend(Backend):
            def _reply(self, *args, **kwargs):
                response = super()._reply(*args, **kwargs)
                old = response['decisions']
                action = {'kind': 'unready_turn'}
                response['session']['active_human_player_ids'] = [1]
                current = {k:old[k] for k in ('episode_id','game_generation','sequence','player_id','turn')}
                current.update(schema='civ6-host.network-decisions.v1', base_schema=None,
                    player_map={}, unsupported=['fixture'], complete_action_space=False,
                    candidates=[dict(candidate_id=_digest(action),action=action)],
                    turn_controls=dict(schema='civ6-host.turn-controls.v1',player_id=0,
                        turn=self.turn,active=False,active_complete=False,can_unready=True,
                        timer_elapsed=False))
                current['decision_id'] = _digest(current)
                response['decisions'] = current
                return response
        backend = WaitingBackend()
        client = SessionClient(backend)
        first = client.reset()['decisions']
        client.act(0, first['decision_id'], first['candidates'][0]['candidate_id'])
        self.assertEqual(backend.calls[-1]['player_id'], 0)
        self.assertEqual(client.command_result['requested_action'], {'kind':'unready_turn'})

    def test_inactive_human_can_answer_only_an_offered_dialogue(self):
        class DialogueBackend(Backend):
            def _reply(self, *args, **kwargs):
                response = super()._reply(*args, **kwargs)
                old = response['decisions']
                action = dict(kind='diplomacy_response', session_id=3,
                              statement_sequence=7, choice='CHOICE_POSITIVE')
                response['session']['active_human_player_ids'] = [1]
                current = {k:old[k] for k in ('episode_id','game_generation','sequence','player_id','turn')}
                current.update(schema='civ6-host.network-decisions.v1',
                    base_schema='civ6rl.diplomacy_decisions987.v1',
                    player_map={}, unsupported=['fixture'], complete_action_space=False,
                    candidates=[dict(candidate_id=_digest(action), action=action)],
                    turn_controls=dict(schema='civ6-host.turn-controls.v1',player_id=0,
                        turn=self.turn, active=False, active_complete=False,
                        can_unready=False, timer_elapsed=False))
                current['decision_id'] = _digest(current)
                response['decisions'] = current
                return response
        backend = DialogueBackend()
        client = SessionClient(backend)
        first = client.reset()['decisions']
        client.act(0, first['decision_id'], first['candidates'][0]['candidate_id'])
        self.assertEqual(client.command_result['requested_action']['choice'], 'CHOICE_POSITIVE')
        self.assertEqual([r['operation'] for r in backend.calls], ['act'])

        # A modal catalogue must not be a way to authorize ordinary unit orders.
        invalid = backend.current['decisions']
        invalid['candidates'][0]['action'] = dict(kind='move',unit_id=0)
        invalid['decision_id'] = _digest({k:v for k,v in invalid.items() if k!='decision_id'})
        from civ6_host.contracts.network_turn import validate_catalogue
        from types import SimpleNamespace
        with self.assertRaisesRegex(ValueError, 'unrelated LAN commands'):
            validate_catalogue(invalid, SimpleNamespace(episode_id=backend.episode,
                game_generation='native-'+backend.episode),invalid['sequence'],1,player_id=0)


if __name__ == '__main__':
    unittest.main()

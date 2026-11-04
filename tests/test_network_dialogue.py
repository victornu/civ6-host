import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from civ6_host.runtime import network_dialogue
from civ6_host.runtime import network_owner
from civ6_host.runtime.capture_profiles import LAN_PROFILE
from civ6_host.runtime.native.native_pending_diplomacy import DiplomacyChoicePending
from civ6_host.runtime.native.native_turn_continuation import TurnContinuation


class NetworkDialogueTests(unittest.TestCase):
    def setUp(self):
        self.statement = {
            'event_sequence': 19,
            'fields': {'SessionID': 31, 'FromPlayer': 2, 'ToPlayer': 0},
        }
        self.session = {
            'player_id': 0,
            'session_id': 31,
            'from_player': 2,
            'to_player': 0,
            'is_open': True,
        }
        self.pending = DiplomacyChoicePending(self.statement, self.session)
        self.state = {
            'turn': 7,
            'local_player_id': 0,
            'human_player_ids': [0],
            'active_human_player_ids': [],
        }
        self.identity = object()
        self.ledger = [self.statement]
        self.actions = SimpleNamespace(
            pending=[], update_game_once=Mock(), request_end_turn=Mock())
        self.owner = SimpleNamespace(
            inputs=SimpleNamespace(profile=LAN_PROFILE),
            stage=network_owner.STAGE,
            busy=False,
            poisoned=False,
            destroyed=False,
            bound_identity=self.identity,
            network_reference={
                'major_player_ids': tuple(range(6)),
                'human_player_ids': (0,),
                'state': {'player_id': 0, 'observer_id': 0},
            },
            prefix=SimpleNamespace(
                deferred_events=SimpleNamespace(
                    pending_diplomacy_statements=self.ledger),
                actions=self.actions,
                runtime=Mock(),
                ui_child=object(),
            ),
            check_thread=Mock(),
            topology=Mock(return_value=self.identity),
            game_flag=Mock(return_value=1),
            control=Mock(),
            emit=Mock(),
            turn_continuation=None,
        )

    def _actor_boundary(self):
        return patch.object(network_owner, 'require_actor',
                            return_value=self.state)

    def test_initial_overview_registers_same_borrowed_db_namespace_only_once(self):
        runtime = self.owner.prefix.runtime
        runtime.database_bound=True
        network_dialogue.attach_database(self.owner)
        network_dialogue.attach_database(self.owner)
        runtime.namespaces.register.assert_called_once_with(self.owner.prefix.ui_child,'DB')
        self.assertTrue(self.owner.diplomacy_database_namespace_attached)
        self.assertEqual(self.owner.emit.call_count,1)

    def test_overview_does_not_mark_database_attached_when_registration_fails(self):
        runtime=self.owner.prefix.runtime
        runtime.database_bound=True
        runtime.namespaces.register.side_effect=RuntimeError('native factory refused')
        with self.assertRaisesRegex(RuntimeError,'native factory refused'):
            network_dialogue.attach_database(self.owner)
        self.assertFalse(getattr(self.owner,'diplomacy_database_namespace_attached',False))
        self.owner.emit.assert_not_called()

    def test_even_an_attached_database_must_still_be_bound(self):
        self.owner.diplomacy_database_namespace_attached=True
        self.owner.prefix.runtime.database_bound=False
        with self.assertRaisesRegex(RuntimeError,'not bound'):
            network_dialogue.attach_database(self.owner)
        self.owner.prefix.runtime.namespaces.register.assert_not_called()

    def test_initial_diplomacy_refusal_has_no_side_effect(self):
        from test_diplomacy_overview_contract import fixture
        data=fixture()
        action=dict(kind='diplomacy_initiate',target_player_id=3,
                    choice='CHOICE_DECLARE_FRIENDSHIP')
        with patch.object(network_dialogue,'read_overview',return_value=data):
            result=network_dialogue.initiate(self.owner,action,0,1)
        self.assertEqual(result['status'],'refused')
        self.owner.prefix.runtime.evaluate_text.assert_not_called()

    def test_initial_request_uses_shared_delivery_without_gameupdate(self):
        from test_diplomacy_overview_contract import fixture
        data=fixture()
        action=dict(kind='diplomacy_initiate',target_player_id=2,
                    choice='CHOICE_DECLARE_FRIENDSHIP')
        self.owner.prefix.runtime.evaluate_text.return_value=b'requested'
        self.owner.prefix.deferred_events.drain_empty_receivers=Mock()
        self.owner.prefix.view_publisher=SimpleNamespace(publish=Mock())
        with patch.object(network_dialogue,'read_overview',return_value=data), \
             patch('civ6_host.runtime.diplomacy_overview.read_configuration',return_value={}), \
             patch('civ6_host.runtime.diplomacy_overview.request_source',return_value=b'official'), \
             patch('civ6_host.runtime.native.native_diplomacy_choices.deliver_statement_request') as deliver, \
             patch.object(network_dialogue,'retain',return_value=True) as retain, \
             patch.object(network_dialogue,'control'):
            result=network_dialogue.initiate(self.owner,action,0,1)
        self.assertEqual(result['status'],'completed')
        deliver.assert_called_once_with(self.owner.prefix.actions)
        retain.assert_called_once_with(self.owner)
        self.owner.prefix.actions.update_game_once.assert_not_called()
        self.owner.prefix.actions.request_end_turn.assert_not_called()
        self.assertFalse(self.owner.busy)

    def test_initial_request_error_poisoned_without_retry(self):
        from test_diplomacy_overview_contract import fixture
        data=fixture()
        action=dict(kind='diplomacy_initiate',target_player_id=2,
                    choice='CHOICE_DECLARE_FRIENDSHIP')
        self.owner.prefix.runtime.evaluate_text.side_effect=RuntimeError('native refusal')
        with patch.object(network_dialogue,'read_overview',return_value=data), \
             patch('civ6_host.runtime.diplomacy_overview.read_configuration',return_value={}), \
             patch('civ6_host.runtime.diplomacy_overview.request_source',return_value=b'official'), \
             patch.object(network_dialogue,'retain') as retain:
            with self.assertRaisesRegex(RuntimeError,'native refusal'):
                network_dialogue.initiate(self.owner,action,0,1)
        self.assertTrue(self.owner.poisoned)
        self.assertEqual(self.owner.stage,'poisoned')
        self.assertFalse(self.owner.busy)
        retain.assert_not_called()

    def test_initial_request_does_not_bypass_pending_war_confirmation(self):
        self.owner.world_input_prompts={0:dict(defending_player=2)}
        with patch.object(network_dialogue,'read_overview') as read:
            result=network_dialogue.initiate(self.owner,dict(kind='diplomacy_initiate'),0,1)
        self.assertEqual(result['reason'],'native_world_prompt_choice_required')
        read.assert_not_called()

    def _continuation(self, *, pending=None, turn=7):
        return TurnContinuation(
            steps=None,
            turn=turn,
            pending=self.pending if pending is None else pending,
            origin='network',
            return_stage=network_owner.STAGE,
        )

    def test_retain_returns_false_when_there_is_no_statement(self):
        self.ledger.clear()
        with patch.object(network_dialogue, '_boundary') as boundary:
            self.assertFalse(network_dialogue.retain(self.owner))
        boundary.assert_not_called()
        self.assertIsNone(self.owner.turn_continuation)

    def test_retain_uses_the_existing_continuation_and_exact_statement(self):
        with self._actor_boundary(), patch.object(
                network_dialogue, '_pending', return_value=self.pending) as make_pending:
            self.assertTrue(network_dialogue.retain(self.owner))

        continuation = self.owner.turn_continuation
        self.assertIs(type(continuation), TurnContinuation)
        self.assertEqual(continuation.origin, 'network')
        self.assertIsNone(continuation.steps)
        self.assertEqual(continuation.return_stage, network_owner.STAGE)
        self.assertEqual(continuation.turn, 7)
        self.assertIs(continuation.pending, self.pending)
        self.assertEqual(continuation.pending.statement, self.statement)
        make_pending.assert_called_once_with(self.owner, self.statement, 0)
        self.owner.emit.assert_called_once()

    def test_validate_accepts_a_quiescent_local_statement(self):
        continuation = self._continuation()
        self.owner.turn_continuation = continuation
        with self._actor_boundary():
            self.assertIs(network_dialogue.validate(self.owner), continuation)
        self.owner.check_thread.assert_called_once_with()
        self.owner.control.assert_called_once_with(empty=True, allow_diplomacy=True)

    def test_validate_rejects_invalid_profile_stage_and_native_identity(self):
        cases = (
            ('profile', lambda: setattr(self.owner.inputs, 'profile', object())),
            ('stage', lambda: setattr(self.owner, 'stage', 'wrong-stage')),
            ('topology', lambda: self.owner.topology.configure_mock(
                return_value=object())),
            ('game-flag', lambda: self.owner.game_flag.configure_mock(
                return_value=0)),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.setUp()
                self.owner.turn_continuation = self._continuation()
                mutate()
                with self._actor_boundary(), self.assertRaises(RuntimeError):
                    network_dialogue.validate(self.owner)

    def test_validate_rejects_wrong_thread_busy_poisoned_or_destroyed_owner(self):
        cases = (
            ('thread', lambda: setattr(self.owner.check_thread, 'side_effect',
                                       RuntimeError('foreign thread'))),
            ('busy', lambda: setattr(self.owner, 'busy', True)),
            ('poisoned', lambda: setattr(self.owner, 'poisoned', True)),
            ('destroyed', lambda: setattr(self.owner, 'destroyed', True)),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.setUp()
                self.owner.turn_continuation = self._continuation()
                mutate()
                with self._actor_boundary(), self.assertRaises(RuntimeError):
                    network_dialogue.validate(self.owner)

    def test_validate_rejects_wrong_continuation_turn_or_foreign_local_actor(self):
        cases = (
            ('turn', lambda: self.state.__setitem__('turn', 8)),
            ('local-actor', lambda: self.owner.network_reference['state'].__setitem__(
                'player_id', 1)),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.setUp()
                self.owner.turn_continuation = self._continuation()
                mutate()
                with self._actor_boundary(), self.assertRaises(RuntimeError):
                    network_dialogue.validate(self.owner)

    def test_validate_rejects_statement_that_is_no_longer_first(self):
        self.owner.turn_continuation = self._continuation()
        other = {'event_sequence': 20}
        self.ledger[:] = [other, self.statement]
        with self._actor_boundary(), self.assertRaisesRegex(RuntimeError, 'no longer first'):
            network_dialogue.validate(self.owner)

    def test_resume_refuses_until_the_retained_statement_is_consumed(self):
        self.owner.turn_continuation = self._continuation()
        with self._actor_boundary(), self.assertRaisesRegex(RuntimeError, 'before the native statement'):
            network_dialogue.resume(self.owner)
        self.assertIs(self.owner.turn_continuation.pending, self.pending)

    def test_resume_retains_an_exact_followup_statement(self):
        self.owner.turn_continuation = self._continuation()
        self.ledger.clear()
        followup = {'event_sequence': 20, 'fields': {'SessionID': 32}}
        self.ledger.append(followup)
        followup_pending = DiplomacyChoicePending(
            followup, dict(self.session, session_id=32))
        with self._actor_boundary(), patch.object(
                network_dialogue, '_pending', return_value=followup_pending) as make_pending:
            result = network_dialogue.resume(self.owner)

        self.assertIsNone(result)
        self.assertIs(self.owner.turn_continuation.pending, followup_pending)
        self.assertEqual(self.owner.turn_continuation.pending.statement, followup)
        make_pending.assert_called_once_with(self.owner, followup, 0)
        self.actions.update_game_once.assert_not_called()
        self.actions.request_end_turn.assert_not_called()

    def test_resume_finishes_after_consumption_without_pumping_or_ending_turn(self):
        continuation = self._continuation()
        self.owner.turn_continuation = continuation
        self.ledger.clear()
        observation = {'player_id': 0, 'turn': 7, 'public': 'view'}
        with self._actor_boundary(), patch(
                'civ6_host.runtime.native.native_player_observation.observe_player',
                return_value=observation) as observe:
            result = network_dialogue.resume(self.owner)

        self.assertEqual(result, observation)
        observe.assert_called_once_with(self.owner.prefix.runtime,
                                        self.owner.prefix.ui_child, 0)
        self.assertIsNone(self.owner.turn_continuation)
        self.assertTrue(continuation.finished)
        self.owner.control.assert_any_call(empty=True)
        self.actions.update_game_once.assert_not_called()
        self.actions.request_end_turn.assert_not_called()

    def test_resume_rejects_an_observation_from_another_turn(self):
        continuation = self._continuation()
        self.owner.turn_continuation = continuation
        self.ledger.clear()
        with self._actor_boundary(), patch(
                'civ6_host.runtime.native.native_player_observation.observe_player',
                return_value={'player_id': 0, 'turn': 8}), self.assertRaises(RuntimeError):
            network_dialogue.resume(self.owner)
        self.assertIs(self.owner.turn_continuation, continuation)
        self.actions.update_game_once.assert_not_called()
        self.actions.request_end_turn.assert_not_called()

    def test_turn_continuation_validate_dispatches_network_origin(self):
        from civ6_host.runtime.native import native_turn_continuation

        continuation = self._continuation()
        self.owner.turn_continuation = continuation
        validated = object()
        with patch('civ6_host.runtime.network_dialogue.validate',
                   return_value=validated) as validate_network:
            result = native_turn_continuation.validate(self.owner)

        self.assertIs(result, validated)
        validate_network.assert_called_once_with(self.owner)

    def test_turn_continuation_resume_dispatches_network_origin(self):
        from civ6_host.runtime.native import native_turn_continuation

        continuation = self._continuation()
        self.owner.turn_continuation = continuation
        observation = {'player_id': 0, 'turn': 7}
        with patch('civ6_host.runtime.network_dialogue.resume',
                   return_value=observation) as resume_network:
            result = native_turn_continuation.resume(self.owner)

        self.assertIs(result, observation)
        resume_network.assert_called_once_with(self.owner)


if __name__ == '__main__':
    unittest.main()

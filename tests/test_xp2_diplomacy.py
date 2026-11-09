from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_diplomacy
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner


class XP2DiplomacyAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.saved = object.__new__(SavedLoadOwner)
        self.backend = SimpleNamespace(
            load_abi=SimpleNamespace(core_sha256=xp2_diplomacy.XP2_CORE_SHA256),
            stage='xp1-continuation-ready', busy=False, poisoned=False, destroyed=False,
            control=Mock())
        self.transport = SimpleNamespace(backend=self.backend,
            require_empty_native_queue=Mock())
        self.continuation = object.__new__(SavedContinuation)
        self.continuation.owner = self.backend
        self.continuation.transport = self.transport
        self.continuation.observation = dict(player_id=0, turn=47)
        self.backend._xp1_continuation = self.continuation
        self.deferred = SimpleNamespace(pending_diplomacy_statements=[])
        self.prefix = SimpleNamespace(deferred_events=self.deferred, actions=self.transport)
        self.saved.backend = self.backend
        self.saved.continuation = self.continuation
        self.saved.prefix = self.prefix
        self.saved.emit = Mock()
        self.saved._check = Mock()

    def test_retain_refuses_unwired_type132_receiver_without_native_read(self):
        with patch.object(SavedContinuation, 'check'), \
             patch.object(self.saved.prefix, 'runtime', create=True) as runtime:
            with self.assertRaisesRegex(RuntimeError, 'receiver and statement ledger are not wired'):
                xp2_diplomacy.retain(self.saved)
        runtime.evaluate_text.assert_not_called()
        self.saved._check.assert_called_once_with('commands', requested='unit_commands_candidate')
        self.backend.control.assert_not_called()
        self.assertFalse(hasattr(self.saved, '_xp2_diplomacy'))

    def test_empty_ledger_is_no_dialogue_only_after_receiver_is_owned(self):
        self.deferred.diplomacy_statement_receiver = self.deferred
        with patch.object(SavedContinuation, 'check'):
            self.assertFalse(xp2_diplomacy.retain(self.saved))
        self.assertFalse(hasattr(self.saved, '_xp2_diplomacy'))


class XP2DiplomacyConfigurationTests(unittest.TestCase):
    def test_xp2_reader_uses_only_profile_selected_leader_and_slotstatus(self):
        from civ6_host.runtime.native import native_diplomacy_configuration as config
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, configuration_abi

        app = SimpleNamespace(
            _configuration_abi=configuration_abi(XP2_CORE_SHA256),
            snapshot=Mock(return_value=dict(players={2: 0x2000, 5: 0x5000})),
            require_context=Mock())
        backend = SimpleNamespace(
            load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256), owner=app,
            core=SimpleNamespace(_handle=0x1000), runtime=SimpleNamespace(read=Mock(), call=None),
            context=0x1234, emit=Mock())
        statement = dict(fields=dict(FromPlayer=2, Initiator=5))
        source = dict(provider_source_sha256='a' * 64, shared_exe_source_sha256='b' * 64)
        calls = []

        def value(_base, pointer, key, _reader, _call, _source):
            calls.append((pointer, key))
            return b'variant'

        with patch.object(config, 'verify_source', side_effect=AssertionError('Base reader used')), \
             patch('civ6_host.runtime.xp2_world_configuration.verify_source', return_value=source), \
             patch('civ6_host.runtime.xp2_world_configuration._live_getter'), \
             patch('civ6_host.runtime.xp2_world_configuration._value', side_effect=value), \
             patch('civ6_host.runtime.native.native_world_configuration.human', return_value=True), \
             patch.object(config, 'leader', return_value='LEADER_TEST'):
            rows = config.read(backend, statement, core_sha256=XP2_CORE_SHA256)

        self.assertEqual(rows, {2: {'leader': 'LEADER_TEST'}, 5: {'human': True}})
        self.assertEqual(calls, [(0x2000, 'SLOT_STATUS'),
                                 (0x2000, 'LEADER_TYPE_NAME'),
                                 (0x5000, 'SLOT_STATUS')])
        self.assertEqual(app.snapshot.call_count, 2)
        self.assertEqual(app.require_context.call_count, 2)

    def test_saved_context_composes_real_choice_read_and_apply_without_base_displays(self):
        from civ6_host.runtime.native import native_diplomacy_choices as choices
        from civ6_host.runtime.native import native_saved_player_map as player_map
        from civ6_host.runtime.native import native_diplomacy_display986 as display
        from civ6_host.runtime.native import native_saved_yield_display982 as yield_display
        from civ6_host.runtime.native.native_turn_continuation import TurnContinuation
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        statement = dict(event_sequence=11, automatic_response=False,
            fields=dict(SessionID=77, FromPlayer=1, ToPlayer=0))
        pending = SimpleNamespace(statement=statement,
            session=dict(player_id=0, session_id=77))
        state = TurnContinuation(None, 47, pending=pending,
            origin='xp2_saved_load', return_stage='xp1-continuation-ready')
        observation = dict(player_id=0, turn=47, width=2, height=1, plots=[])
        identity = SimpleNamespace(episode_id='episode', game_generation='native-episode')
        runtime = SimpleNamespace(database_bound=True,
            evaluate_text=Mock(side_effect=[b'menu', b'menu', b'accepted']),
            namespaces=SimpleNamespace(register=Mock()), ui_child=object())
        ledger = [statement]
        actions = SimpleNamespace(pending=[])
        prefix = SimpleNamespace(runtime=runtime, ui_child=runtime.ui_child,
            deferred_events=SimpleNamespace(pending_diplomacy_statements=ledger,
                drain_empty_receivers=Mock()), actions=actions,
            view_publisher=SimpleNamespace(publish=Mock()))
        backend = SimpleNamespace(prefix=prefix, load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256),
            explicit_diplomacy=None, diplomacy_database_namespace_attached=True,
            busy=False, poisoned=False, stage='xp1-continuation-ready', emit=Mock(),
            check_thread=Mock(), jobs_snapshot=Mock(return_value={'jobs': 0}))

        class Context:
            origin = 'xp2_saved_load'
            turn = 47
            pending = state.pending
            def validate(self, owner):
                self.assert_owner(owner)
                return state
            def assert_owner(self, owner):
                if owner is not backend or state.pending is None:
                    raise RuntimeError('foreign test dialogue')
            def begin_response(self, owner):
                self.assert_owner(owner)
                self.started = True
            def end_response(self, owner):
                self.assert_owner(owner)
                self.finished = True
            def poison(self, owner):
                raise AssertionError('synthetic native response should succeed')
            def resume(self, owner):
                self.assert_owner(owner)
                state.pending = None
                return observation

        context = Context()
        data = dict(session=dict(player_id=0, session_id=77, from_player=1,
            to_player=0, statement_type='MAKE_DEAL', statement_subtype='NONE', response_type=None),
            statement_text='deal', mood=0, selections=[dict(key='CHOICE_EXIT', sort=0,
                text='Close', tooltip=None, diplomatic_action_type=None, disabled=False)])
        saved_map = dict(schema='test-map', player_id=0, turn=47)
        with patch.object(choices, 'parse', return_value=data), \
             patch.object(choices, 'lua_source', return_value=b'menu-source'), \
             patch.object(choices, 'deliver_response') as deliver, \
             patch.object(choices.pending, 'source', return_value=b'check-session'), \
             patch.object(choices, '_snapshot', return_value={'jobs': 0}) as snapshot, \
             patch('civ6_host.runtime.native.native_player_observation.observe_player', return_value=observation), \
             patch.object(player_map, 'observe', return_value=saved_map) as map_observe, \
             patch('civ6_host.runtime.native.native_diplomacy_configuration.read', return_value={1: {'leader': 'LEADER_TEST'}, 0: {'human': True}}) as config_read, \
             patch('civ6_host.runtime.native.native_episode_identity.require_episode', return_value=identity), \
             patch.object(display, 'read', side_effect=AssertionError('Base-only display reader used')), \
             patch.object(yield_display, 'observe', side_effect=AssertionError('unqualified yield reader used')):
            observation_read, catalogue = choices.read(backend, 0, saved_context=context)
            action = catalogue['candidates'][0]['action']
            effect = choices.apply(backend, action, saved_context=context)

        self.assertEqual(observation_read, observation)
        self.assertEqual(catalogue['schema'], choices.SCHEMA)
        self.assertNotIn('public_display', catalogue)
        self.assertNotIn('yield_display', catalogue)
        self.assertEqual(effect, observation)
        self.assertTrue(context.started and context.finished)
        self.assertEqual(ledger, [])
        self.assertEqual(deliver.call_count, 1)
        self.assertEqual(config_read.call_count, 2)
        self.assertTrue(all(call.kwargs['core_sha256'] == XP2_CORE_SHA256
                            for call in config_read.call_args_list))
        self.assertEqual(map_observe.call_count, 2)
        self.assertGreaterEqual(snapshot.call_count, 6)

    def test_composed_saved_snapshot_uses_real_owner_and_job_observer_after_finished_context(self):
        from civ6_host.runtime.native import native_diplomacy_choices as choices
        from test_xp2_war_read_owner import WarReadOwnerTests
        from test_world_war_producer import quiescent

        helper = WarReadOwnerTests()
        self.addCleanup(helper.doCleanups)
        fixture, observer = helper.fixture()
        saved, backend = fixture.saved, fixture.backend
        saved._running = False
        backend.snapshot_phase = 'preserved-phase'
        context = SimpleNamespace(saved=saved, finished=True,
            state=SimpleNamespace(finished=True, pending=None))
        during = []

        def capture(*_args):
            during.append((backend.snapshot_phase, backend.busy, backend.stage,
                           saved._running, observer._query_owner, observer._exclusive()))
            return quiescent()

        with patch('civ6_host.runtime.saved_load_job_observer.capture_registry', capture):
            before = choices._snapshot(backend, 'before', context)
            after = choices._snapshot(backend, 'after', context)

        self.assertEqual(before, after)
        self.assertEqual([row[0] for row in during], ['before', 'after'])
        self.assertTrue(all(row[1] is False for row in during))
        self.assertTrue(all(row[2] == 'xp1-continuation-ready' for row in during))
        self.assertTrue(all(row[3] is True for row in during))
        self.assertTrue(all(row[4] is saved and row[5] is True for row in during))
        self.assertFalse(saved._running)
        self.assertFalse(backend.busy)
        self.assertEqual(backend.stage, 'xp1-continuation-ready')
        self.assertEqual(backend.snapshot_phase, 'preserved-phase')
        self.assertIsNone(observer._query_owner)

    def test_saved_view_publishes_only_the_retained_native_dialogue_candidates(self):
        from civ6_host.runtime import xp1_session_view as view
        from civ6_host.contracts import network_turn
        from civ6_host.contracts import diplomacy_decisions
        from civ6_host.runtime.native import native_diplomacy_choices as choices

        action = dict(kind='diplomacy_response', session_id=77,
                      statement_sequence=11, choice='CHOICE_EXIT')
        observation = dict(player_id=0, turn=47, width=2, height=1, plots=[])
        identity = SimpleNamespace(episode_id='episode', game_generation='native-episode')
        activity = dict(turn=47, local_player_id=0, observer_id=0,
            rows=[dict(player_id=0, active=False, active_complete=False, can_unready=False)])
        session = dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=47,
            local_player_id=0, human_player_ids=[0], active_human_player_ids=[])
        candidate = dict(candidate_id=diplomacy_decisions.digest(action), action=action)
        statement = dict(event_sequence=11, automatic_response=False,
            fields=dict(SessionID=77, FromPlayer=1, ToPlayer=0))
        native_choices = [dict(key='CHOICE_EXIT', sort=0, text='Close', tooltip=None,
            diplomatic_action_type=None, disabled=False)]
        catalogue = dict(schema=choices.SCHEMA,
            episode_id='episode', game_generation='native-episode', sequence=8,
            player_id=0, turn=47, origin_turn=47, player_map={}, statement=statement,
            data=dict(session=dict(player_id=0, session_id=77, from_player=1,
                to_player=0, is_open=True, statement_type='MAKE_DEAL',
                statement_subtype='NONE', response_type=None), selections=native_choices),
            unsupported=['native_dialogue_space_incomplete'], complete_action_space=False,
            candidates=[candidate], decision_id='native-private-digest',
            source_sha256=choices.PROOF_SHA256, ui_support_sha256=choices.SUPPORT_SHA)
        saved = SimpleNamespace(_running=False)
        class Attempt:
            def __enter__(self):
                saved._running = True
            def __exit__(self, *_args):
                saved._running = False
        class Context:
            saved = None
            public_display = None
            public_display_source_sha256 = None
            def __init__(self): self.validate_calls = 0
            def validate(self, _backend):
                if saved._running:
                    raise AssertionError('Context validation ran inside saved._attempt')
                self.validate_calls += 1
        context = Context()
        saved._xp2_diplomacy = context
        saved._attempt = Mock(side_effect=Attempt)
        saved._check = Mock()
        saved.backend = SimpleNamespace(
                load_abi=SimpleNamespace(core_sha256=xp2_diplomacy.XP2_CORE_SHA256),
                control=Mock())
        saved.prefix = SimpleNamespace()
        saved.continuation = SimpleNamespace(
                observation=observation, identity=identity,
                transport=SimpleNamespace(require_empty_native_queue=Mock()),
                check=Mock())
        context.saved = saved
        with patch.object(view, '_prepare', return_value=({}, (0,))), \
             patch.object(xp2_diplomacy, 'read', return_value=(observation, catalogue)), \
             patch.object(view, '_read_state', return_value=(session, activity)), \
             patch.object(view, '_observe_activity', return_value=observation), \
             patch('civ6_host.runtime.network_timer.read', return_value=False), \
             patch('civ6_host.runtime.native.native_episode_identity.require_episode',
                   return_value=identity):
            got_session, got_observation, decisions = view.read(saved, 0, 8)

        self.assertEqual(got_session, session)
        self.assertEqual(got_observation, observation)
        self.assertEqual(decisions['schema'], diplomacy_decisions.SCHEMA)
        self.assertEqual(decisions['base_schema'], catalogue['schema'])
        self.assertEqual(decisions['dialogue'], dict(session_id=77,
            statement_sequence=11, from_player=1, to_player=0))
        self.assertEqual(decisions['choices'], [dict(key='CHOICE_EXIT', disabled=False)])
        self.assertIsNone(decisions['public_display'])
        self.assertIsNone(decisions['public_display_source_sha256'])
        self.assertEqual(decisions['candidates'], [candidate])
        self.assertEqual(decisions['turn_controls']['active'], False)
        self.assertEqual(decisions['turn_controls']['can_unready'], False)
        self.assertIn(diplomacy_decisions.PUBLIC_DISPLAY_GAP, decisions['unsupported'])
        self.assertEqual(context.validate_calls, 2)
        self.assertEqual(saved.backend.control.call_args.kwargs,
                         dict(empty=True, allow_diplomacy=True))

    def test_worker_routes_response_directly_and_retains_only_after_quiescence(self):
        from civ6_host.runtime.workers import network_worker
        from civ6_host.runtime.network_protocol import SCHEMA, NetworkProtocol, validate_network_response
        from civ6_host.contracts import network_turn
        from test_network_protocol import NetworkProtocolTests
        action = dict(kind='diplomacy_response', session_id=77,
            statement_sequence=11, choice='CHOICE_EXIT')
        saved = SimpleNamespace(_xp2_diplomacy=object(),
            continuation=SimpleNamespace(observation={'player_id':0,'turn':47}),
            execute=Mock(side_effect=AssertionError('must bypass saved.execute')))
        effect = dict(status='completed', reason=None, requested_action=action,
            observation={'private':'must-not-leak'}, receipt={'archive_hex':'private'},
            pending_statement_retained=False, game_update_called=False)
        with patch('civ6_host.runtime.xp2_diplomacy.respond', return_value=effect) as respond:
            command = network_worker._execute_xp1(saved, action, 0, 9, 'unused')
        respond.assert_called_once_with(saved, action, saved.continuation.observation)
        saved.execute.assert_not_called()
        self.assertEqual(command, dict(status='completed', reason=None, requested_action=action))
        self.assertEqual(set(command), {'status', 'reason', 'requested_action'})
        self.assertFalse(network_worker._poll_xp1(saved, 9, 'unused'))

        fixture = NetworkProtocolTests()
        fixture.setUp()
        self.addCleanup(fixture._stop_patches)
        fixture._accept_initial()
        protocol = fixture.protocol
        base = dict(schema='civ6rl.diplomacy_decisions948.v1',
            episode_id=protocol.identity.episode_id,
            game_generation=protocol.identity.game_generation, sequence=0,
            player_id=0, turn=10, player_map={}, unsupported=[],
            complete_action_space=False,
            candidates=[dict(candidate_id=network_turn.digest(action), action=action)])
        base['decision_id'] = network_turn.digest(base)
        decisions = {key:value for key,value in base.items() if key != 'decision_id'}
        decisions.update(schema=network_turn.LATEST_SCHEMA, base_schema=base['schema'],
            turn_controls=fixture._controls(0, active=False, active_complete=False),
            unit_work_state=None, unit_work_info=None, city_growth=None)
        decisions['decision_id'] = network_turn.digest(decisions)
        protocol.catalogues[0] = decisions
        protocol.observations[0] = {'player_id':0, 'turn':10}
        selection = dict(decision_id=decisions['decision_id'],
                         candidate_id=network_turn.digest(action))
        request = fixture._request('act', 1, 0, selection)
        response = fixture._reply('act', 1, 0, selected=action, status='completed')
        response['command_result'] = command
        validate_network_response(response, protocol, 'act', request=request)

        deferred = SimpleNamespace(pending_diplomacy_statements=[dict(event_sequence=11)],
            diplomacy_statement_receiver=None)
        saved.backend = SimpleNamespace(
            load_abi=SimpleNamespace(core_sha256=xp2_diplomacy.XP2_CORE_SHA256),
            busy=False, stage='xp1-continuation-ready')
        saved.prefix = SimpleNamespace(deferred_events=deferred)
        with self.assertRaisesRegex(RuntimeError, 'exact retained receiver'):
            network_worker._retain_xp2_diplomacy_if_ready(saved)
        deferred.diplomacy_statement_receiver = deferred
        with patch('civ6_host.runtime.xp2_diplomacy.retain', return_value=True) as retain:
            self.assertTrue(network_worker._retain_xp2_diplomacy_if_ready(saved))
        retain.assert_called_once_with(saved)
        saved.backend.busy = True
        with patch('civ6_host.runtime.xp2_diplomacy.retain') as retain:
            with self.assertRaisesRegex(RuntimeError, 'active transition'):
                network_worker._retain_xp2_diplomacy_if_ready(saved)
        retain.assert_not_called()

    def test_worker_poll_advances_normally_without_a_retained_dialogue(self):
        from civ6_host.runtime.workers import network_worker
        saved = SimpleNamespace(_xp2_diplomacy=None)
        with patch.object(network_worker, '_advance_xp1') as advance:
            self.assertTrue(network_worker._poll_xp1(saved, 4, 'unused'))
        advance.assert_called_once_with(saved, 4, 'unused')

    def test_worker_reads_fresh_native_outcome_with_exact_dialogue_mode(self):
        from civ6_host.runtime.workers import network_worker
        saved = SimpleNamespace(_xp2_diplomacy=None)
        native = dict(episode_terminated=False)
        with patch('civ6_host.runtime.xp1_session_result.read', return_value=native) as read:
            self.assertIs(network_worker._read_xp1_outcome(saved, 0), native)
        read.assert_called_once_with(saved, player_id=0)
        saved._xp2_diplomacy = object()
        with patch('civ6_host.runtime.xp1_session_result.read', return_value=native) as read:
            self.assertIs(network_worker._read_xp1_outcome(saved, 0), native)
        read.assert_called_once_with(saved, player_id=0, allow_diplomacy=True)


if __name__ == '__main__':
    unittest.main()

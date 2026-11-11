"""Composed API routing; substituted native boundaries do not qualify GameCore."""
from contextlib import ExitStack
from copy import deepcopy
import json
import re
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_world_war as war
from civ6_host.runtime import xp1_continuation as continuation
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, XP1_CORE_SHA256
import test_world_war_producer as fixtures
import test_xp1_world_input as ui_fixture
from test_world_war_decisions import PIN, PROMPT


class ResponseTests(unittest.TestCase):
    def fixture(self, stack, *, major=False):
        producer = fixtures.ProducerTests()
        case, obs, saved, owners = producer.fixture()
        producer.patches(stack, case, owners)
        war.read(saved, obs, case['turn_controls'], 8)
        prefix, backend = saved.prefix, saved.backend
        calls = NS(at_war=False)
        backend.jobs_snapshot = Mock(side_effect=lambda phase: fixtures.quiescent())
        backend.core, backend.context = object(), object()
        prefix.actions = NS(pending=[])
        def deliver():
            prefix.actions.pending.pop(0)
            calls.at_war = True
        prefix.actions.deliver_one = Mock(side_effect=deliver)
        prefix.deferred_events = NS(pending=[], drain=Mock())
        prefix.view_publisher = NS(publish=Mock())
        saved.emit = Mock()
        def evaluate(child, code, tag, **kwargs):
            if tag == b'@xp2_war_target_kind':
                return b'true' if major else b'false'
            if tag == b'@xp2_explicit_war_state':
                return json.dumps(dict(player_id=0, turn=obs['turn'], defender_player_id=2,
                    at_war=calls.at_war, operation=9876, player_one_key=10, player_two_key=20)).encode()
            if tag == b'@xp2_official_world_war_response':
                status = 'minor_route' if code.endswith(b'true') else 'declined'
                return f'{status},0,{obs["turn"]},2,{PROMPT["war_type"]},-,-,{PIN}'.encode()
            raise AssertionError(('unexpected native query', tag))
        prefix.runtime.evaluate_text = Mock(side_effect=evaluate)
        stack.enter_context(patch('civ6_host.runtime.native.native_player_observation.observe_player', return_value=obs))
        config = stack.enter_context(patch('civ6_host.runtime.xp2_world_configuration.read', return_value={}))
        stack.enter_context(patch('civ6_host.runtime.xp2_world_configuration.lua_bindings', return_value=b''))
        stack.enter_context(patch('civ6_host.runtime.native.native_world_click._war_function', return_value=b''))
        stack.enter_context(patch('civ6_host.runtime.native.native_world_click._war_source_hash', return_value=PIN))
        source = stack.enter_context(patch('civ6_host.runtime.native.native_world_click.war_response_source',
            side_effect=lambda pid, turn, target, kind, accept: b'true' if accept else b'false'))
        def operation(*args, **kwargs):
            prefix.actions.pending.append((3294486831).to_bytes(4, 'little') + b'native-fixture')
            return dict(can_start=True, request_invoked=True)
        request = stack.enter_context(patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation', side_effect=operation))
        return obs, saved, source, config, request

    def test_decline_clears_only_modal_without_submitting_a_game_request(self):
        with ExitStack() as stack:
            obs, saved, source, config, request = self.fixture(stack)
            result = war.respond(saved, dict(kind='world_war_response', accept=False), obs)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['observation'], obs)
            self.assertIsNone(saved.continuation.world_input_prompts[0])
            self.assertIsNone(saved.continuation.explicit_world_input)
            self.assertFalse(result['receipt']['native_callback_invoked'])
            self.assertFalse(result['receipt']['archive_delivered'])
            config.assert_not_called()
            request.assert_not_called()
            saved.prefix.actions.deliver_one.assert_not_called()

    def test_minor_accept_delivers_exact_native_parameters_then_checks_war(self):
        with ExitStack() as stack:
            obs, saved, source, config, request = self.fixture(stack)
            result = war.respond(saved, dict(kind='world_war_response', accept=True), obs)
            self.assertEqual(result['status'], 'completed')
            self.assertTrue(result['receipt']['native_war_state_after']['at_war'])
            self.assertFalse(result['receipt']['native_war_state_before']['at_war'])
            request.assert_called_once_with(saved.backend.core, saved.backend.context,
                0, 9876, {10: 0, 20: 2}, core_sha256=XP2_CORE_SHA256)
            saved.prefix.actions.deliver_one.assert_called_once()
            saved.prefix.deferred_events.drain.assert_called_once()
            saved.prefix.view_publisher.publish.assert_called_once()
            self.assertFalse(result['receipt']['automatic_choices_applied'])

    def test_minor_accept_publishes_observation_after_native_bbg_feedback(self):
        with ExitStack() as stack:
            obs, saved, _, _, _ = self.fixture(stack)
            pending = [(239, 'governor', (0, 2, 65536, -1))]
            saved.continuation.trade_feedback = NS(events=pending)
            settled = deepcopy(obs)
            settled['economy'] = {'gold': 99}

            def flush():
                saved.prefix.actions.deliver_one.assert_called_once()
                self.assertEqual(len(pending), 1)
                pending.clear()
                return []

            def observe(*args):
                self.assertFalse(pending)
                return settled

            saved.continuation.flush_trade_feedback = Mock(side_effect=flush)
            stack.enter_context(patch('civ6_host.runtime.native.native_player_observation.observe_player',
                                      side_effect=observe))
            result = war.respond(saved, dict(kind='world_war_response', accept=True), obs)
            self.assertTrue(result['receipt']['bbg_feedback_flushed'])
            self.assertTrue(result['receipt']['native_war_state_after']['at_war'])
            self.assertEqual(result['observation'], settled)
            self.assertEqual(result['receipt']['observation_after'], settled)
            saved.continuation.flush_trade_feedback.assert_called_once_with()

    def test_major_is_refused_before_any_unwired_session_callback(self):
        with ExitStack() as stack:
            obs, saved, source, config, request = self.fixture(stack, major=True)
            result = war.respond(saved, dict(kind='world_war_response', accept=True), obs)
            self.assertEqual(result['status'], 'refused')
            self.assertEqual(result['refusal_code'], 'xp2_war_major_continuation_unqualified')
            self.assertEqual(saved.continuation.world_input_prompts[0], PROMPT)
            source.assert_not_called()
            request.assert_not_called()
            saved.prefix.actions.deliver_one.assert_not_called()

    def major_fixture(self,stack,*,statements=1,is_open=True):
        obs,saved,source,config,request=self.fixture(stack,major=True)
        prefix=saved.prefix
        saved.backend.control=Mock(wraps=saved.backend.control)
        statement=dict(event_sequence=17,fields=dict(SessionID=77,FromPlayer=0,ToPlayer=2))
        prefix.deferred_events.pending_diplomacy_statements=[]
        prefix.actions.pending=[]
        stack.enter_context(patch('civ6_host.runtime.a0_diplomacy_statement.require_receiver',return_value=True))
        saved.backend.core=NS(_handle=0x180000000,_civ6_host_execution_image=object())
        saved.backend.runtime=NS(read=Mock())
        stack.enter_context(patch('civ6_host.runtime.xp2_statement_factory.verify_request',
            return_value=dict(registry_entry_verified=True,native_factory_invoked=False)))
        source.side_effect=None;source.return_value=b'fixture-major-request'
        def evaluate(child,code,name,**kwargs):
            if name==b'@xp2_war_target_kind':return b'true'
            if name==b'@xp2_official_world_war_response':
                prefix.actions.pending.append((0xa4172391).to_bytes(4,'little')+b'native-fixture')
                return b'fixture-response'
            if name==b'@xp2_world_war_pending_session':return b'fixture-open-session'
            raise AssertionError(name)
        prefix.runtime.evaluate_text.side_effect=evaluate
        stack.enter_context(patch('civ6_host.runtime.native.native_world_click.parse_war_response_result',
            return_value=dict(status='session_request',native_callback_invoked=True,session='DECLARE_SURPRISE_WAR')))
        def deliver(transport):
            self.assertEqual(int.from_bytes(transport.pending[0][:4],'little'),0xa4172391)
            transport.pending.pop(0)
            prefix.deferred_events.pending_diplomacy_statements.extend([deepcopy(statement) for _ in range(statements)])
        send=stack.enter_context(patch('civ6_host.runtime.native.native_diplomacy_choices.deliver_statement_request',side_effect=deliver))
        stack.enter_context(patch('civ6_host.runtime.native.native_pending_diplomacy.source',return_value=b'fixture-session-read'))
        stack.enter_context(patch('civ6_host.runtime.native.native_pending_diplomacy.parse',return_value=dict(
            player_id=0,session_id=77,from_player=0,to_player=2,is_open=is_open,statement_type='DECLARE_SURPRISE_WAR')))
        return obs,saved,request,send

    def test_major_delivers_one_native_request_and_retains_explicit_statement(self):
        with ExitStack() as stack:
            obs,saved,request,send=self.major_fixture(stack)
            result=war.respond(saved,dict(kind='world_war_response',accept=True),obs)
            self.assertEqual(result['status'],'completed')
            self.assertTrue(result['pending_statement_retained'])
            self.assertTrue(result['receipt']['archive_delivered'])
            self.assertFalse(result['receipt']['automatic_choices_applied'])
            self.assertEqual(len(saved.prefix.deferred_events.pending_diplomacy_statements),1)
            self.assertEqual(saved.prefix.actions.pending,[])
            saved.backend.control.assert_any_call(empty=True,allow_diplomacy=True)
            self.assertIsNone(saved.continuation.world_input_prompts[0])
            request.assert_not_called();send.assert_called_once_with(saved.prefix.actions)

    def test_foreign_factory_refuses_before_source_generation_or_request(self):
        with ExitStack() as stack:
            obs,saved,request,send=self.major_fixture(stack)
            with patch('civ6_host.runtime.xp2_statement_factory.verify_request',
                       side_effect=ValueError('Registered statement factory differs')):
                with self.assertRaisesRegex(ValueError,'factory differs'):
                    war.respond(saved,dict(kind='world_war_response',accept=True),obs)
            request.assert_not_called()
            send.assert_not_called()
            self.assertFalse(any(
                call.args[2]==b'@xp2_official_world_war_response'
                for call in saved.prefix.runtime.evaluate_text.call_args_list))
            self.assertEqual(saved.continuation.world_input_prompts[0],PROMPT)
            self.assertEqual(saved.prefix.actions.pending,[])

    def test_major_does_not_invent_a_closed_or_ambiguous_dialogue(self):
        for count,is_open in ((0,True),(2,True),(1,False)):
            with self.subTest(count=count,is_open=is_open),ExitStack() as stack:
                obs,saved,request,send=self.major_fixture(stack,statements=count,is_open=is_open)
                with self.assertRaisesRegex(RuntimeError,'explicit native statement|closed native dialogue'):
                    war.respond(saved,dict(kind='world_war_response',accept=True),obs)
                self.assertEqual(len(saved.prefix.deferred_events.pending_diplomacy_statements),count)
                self.assertEqual(saved.continuation.world_input_prompts[0],PROMPT)
                request.assert_not_called()

    def test_stale_prompt_and_changed_renderer_never_submit(self):
        for change in ('prompt', 'pin'):
            with self.subTest(change=change), ExitStack() as stack:
                obs, saved, source, config, request = self.fixture(stack)
                if change == 'prompt':
                    saved.continuation.world_input_prompts[0] = dict(PROMPT, defending_player=3)
                else:
                    saved.war_source_sha256 = 'b' * 64
                with self.assertRaises(ValueError):
                    war.respond(saved, dict(kind='world_war_response', accept=True), obs)
                request.assert_not_called()

    def test_selected_prompt_source_keeps_unknown_operations_guarded(self):
        from civ6_host.runtime.native.native_world_click import request_source
        # This evaluates only source generation, not the native callbacks.
        raw = request_source(0, 47, 101, 4, core_sha256=XP2_CORE_SHA256)
        self.assertIn(b'if unqualified or warPrompt~=nil then', raw)
        with patch('civ6_host.runtime.xp2_world_war_display.verify_source', return_value={'source_sha256': PIN}):
            generated = war.request_source(NS(war_source_sha256=PIN), 0, 47, 101, 4, core_sha256=XP2_CORE_SHA256)
            self.assertNotIn(b'if unqualified or warPrompt~=nil then', generated)
            self.assertIn(b'if unqualified then', generated)
            self.assertIn(b"operationName~='MOVE_TO' and operationName~='SWAP_UNITS'", generated)
            self.assertIn(b"return outcome('war_prompt'", generated)
            with self.assertRaises(ValueError):
                war.request_source(NS(war_source_sha256=None), 0, 47, 101, 4, core_sha256=XP2_CORE_SHA256)

    @unittest.skipUnless(ui_fixture.LuaRuntime, 'Lua fixture dependency unavailable')
    def test_official_lua_prompt_branch_submits_nothing_and_other_guards_remain(self):
        from civ6_host.runtime.native.native_world_click import parse_request_result
        rows = [('visible=true;war=true', 'war_prompt', 0),
                ('ranged=true;enabled=20', 'unsupported', 0),
                ('visible=false;war=true', 'request', 1)]
        with patch('civ6_host.runtime.xp2_world_war_display.verify_source', return_value={'source_sha256': PIN}):
            source = war.request_source(NS(war_source_sha256=PIN), 0, 8, 17, 6,
                                        core_sha256=XP2_CORE_SHA256).decode()
        source = re.sub(r':\s*(?:number|table|string|boolean)\b', '', source)
        for declaration, status, sent in rows:
            with self.subTest(status=status):
                script = declaration + '\n' + ui_fixture.LUA_SETUP
                script += '\nlocal function run_click()\n' + source + '\nend\nreturn run_click(),sent\n'
                raw, actual_sent = ui_fixture.LuaRuntime(max_memory=4*1024*1024).execute(script)
                result = parse_request_result(raw.encode(), 0, 8, 17, 6, core_sha256=XP2_CORE_SHA256)
                self.assertEqual((result['status'], actual_sent), (status, sent))
                if status == 'war_prompt':
                    self.assertEqual(result['defender_player_id'], 9)
                    self.assertFalse(result['native_callback_invoked'])

    def test_continuation_requires_modal_response_and_exact_xp2_selection(self):
        current = continuation.SavedContinuation.__new__(continuation.SavedContinuation)
        current.owner = NS(load_abi=NS(core_sha256=XP2_CORE_SHA256))
        current.world_input_prompts = {0: dict(PROMPT)}
        current.observation = dict(player_id=0)
        current._transition = Mock(return_value={'fixture': True})
        with self.assertRaisesRegex(ValueError, 'explicit response first'):
            current.execute({'kind': 'force_end_turn'})
        with self.assertRaisesRegex(ValueError, 'explicitly selected'):
            current.execute({'kind': 'world_war_response', 'accept': False}, session=NS(war_source_sha256=None))
        current.owner.load_abi.core_sha256 = XP1_CORE_SHA256
        with self.assertRaisesRegex(ValueError, 'explicitly selected'):
            current.execute({'kind': 'world_war_response', 'accept': False}, session=NS(war_source_sha256=PIN))
        current._transition.assert_not_called()


class WorkerRoutingTests(unittest.TestCase):
    def test_popup_query_uses_actual_read_only_owner_control_without_action_receipts(self):
        from civ6_host.runtime import xp1_world_input as world
        backend=NS(load_abi=NS(core_sha256=XP2_CORE_SHA256),control=Mock(return_value={'actual':True}))
        continuation=NS(world_input_prompts={0:dict(PROMPT)})
        saved=NS(war_source_sha256=PIN)
        owner=world._BoundWorldOwner(saved,active=False)
        with patch.object(world,'_owner',return_value=(backend,continuation,object(),object())), \
             patch.object(war,'source_pin',return_value=PIN):
            self.assertEqual(owner.control(empty=True),{'actual':True})
            backend.control.assert_called_once_with(empty=True)
            with self.assertRaisesRegex(ValueError,'query cannot publish'):
                owner.emit('official_world_input_result')
            backend.control.reset_mock();continuation.world_input_prompts={}
            with self.assertRaisesRegex(ValueError,'selected pending XP2 war popup'):
                owner.control(empty=True)
            backend.control.assert_not_called()

    def test_response_is_revalidated_and_infrastructure_refusal_is_not_success(self):
        from civ6_host.runtime.workers.network_worker import _execute_xp1
        from test_world_war_decisions import make_catalogue, OBSERVATION
        case = make_catalogue()
        action = case['candidates'][1]['action']
        current = NS(explicit_world_input=deepcopy(case['world_input']), observation=deepcopy(OBSERVATION),
                     world_input_prompts={0: dict(PROMPT)})
        saved = NS(backend=NS(load_abi=NS(core_sha256=XP2_CORE_SHA256)),
            prefix=NS(deferred_events=NS(pending_diplomacy_statements=[])),
            continuation=current, emit=Mock(), execute=Mock(return_value=dict(action=action,
            effect=dict(status='refused', refusal_code='xp2_war_major_continuation_unqualified'))))
        with patch('civ6_host.runtime.xp1_session_view.read', return_value=(None, OBSERVATION, case)), \
                patch('civ6_host.runtime.xp1_session_inputs._write_once', return_value={'fixture': True}):
            result = _execute_xp1(saved, action, 0, 8, 'fixture/session.json')
        self.assertEqual(result, dict(status='refused', reason='xp2_war_major_continuation_unqualified', requested_action=action))
        saved.execute.assert_called_once_with(action)

    def test_force_end_cannot_bypass_pending_modal_via_fast_preflight(self):
        from civ6_host.runtime.workers.network_worker import _execute_xp1
        from test_world_war_decisions import make_catalogue, OBSERVATION
        saved = NS(backend=NS(load_abi=NS(core_sha256=XP2_CORE_SHA256)),
            continuation=NS(world_input_prompts={0: dict(PROMPT)}), execute=Mock())
        with patch('civ6_host.runtime.xp1_session_view.read_turn_preflight') as fast, \
                patch('civ6_host.runtime.xp1_session_view.read', return_value=(None, OBSERVATION, make_catalogue())):
            result = _execute_xp1(saved, {'kind': 'force_end_turn'}, 0, 8, 'fixture/session.json')
        self.assertEqual(result['status'], 'refused')
        fast.assert_not_called()
        saved.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()

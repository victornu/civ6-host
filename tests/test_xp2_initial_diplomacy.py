"""Composed retained-owner guards; configuration/Lua/native delivery are fixtures."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import json
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_diplomacy_overview as adapter
from civ6_host.runtime import xp2_bbg_inputs
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import ACTIVE, READY
import test_xp2_continuation_lifetime as lifetime_fixture


class InitialDiplomacyOwnerTests(unittest.TestCase):
    def fixture(self, *, active=False, requested=True, offered=True, pending=1):
        f,b,p,lease,token,transport = lifetime_fixture.ContinuationLifetimeTests().graph()
        # Retain the actual XP2 owner/continuation/cache/transport graph. The
        # input data is synthetic, not a claimed native BBG Load.
        inputs = replace(b.inputs, official_bundle=xp2_bbg_inputs.REFERENCE)
        b.inputs = lease.inputs = inputs
        b._saved_load_candidate = b._xp1_commands_requested = b._xp2_postload_requested = True
        b.raw_load_result = {}
        saved = SavedLoadOwner.__new__(SavedLoadOwner)
        saved.thread = threading.get_ident()
        saved.backend = saved._backend = b
        saved._engine_sha256 = b.load_abi.core_sha256
        b._saved_stage_owner = saved
        saved.prefix, saved.core, saved.host = p,b.core,b.host
        saved.context, saved.inputs, saved.receipt = b.context,inputs,b.raw_load_result
        saved.phase, saved.poisoned, saved._running = 'commands',False,True
        saved.requested = dict(unit_commands_candidate=True,post160_candidate=True)
        saved.facade = saved.post = None
        saved.publication, saved.player_view, saved.continuation = token.publication,token.view,token
        b.saved_load_publication_attempt = token.publication
        saved.emit = Mock()
        saved.diplomacy_overview_diagnostic = saved.governors_diagnostic = True
        saved.war_source_sha256 = 'fixture-selected-source'
        p.deferred_events.pending_diplomacy_statements = []
        b.busy, b.stage = active,ACTIVE if active else READY
        token.world_input_prompts = {}
        observation = deepcopy(token.observation)
        pid,turn = observation['player_id'],observation['turn']
        action = dict(kind='diplomacy_initiate',target_player_id=1,
                      choice='CHOICE_DIPLOMATIC_DELEGATION')
        overview = dict(schema='civ6-host.diplomacy-overview.v1',player_id=pid,turn=turn,
            capability=True,paused=False,targets=[dict(player_id=1,selections=[
                dict(key=action['choice'],disabled=not offered,supported=True,
                     text='Send delegation',tooltip=None,diplomatic_action_type=None)])],
            complete_action_space=False)
        native_calls=[]
        def evaluate(_child, code, tag, **kwargs):
            native_calls.append(tag)
            if tag==b'@xp2_initial_diplomacy_overview':
                return json.dumps(overview).encode()
            if tag==b'@xp2_initial_diplomacy_request':
                if requested:
                    transport.pending.append((0xa4172391).to_bytes(4,'little')+b'fixture-native-archive')
                    return b'requested'
                return b'not_requested'
            raise AssertionError(tag)
        p.runtime.evaluate_text=Mock(side_effect=evaluate)
        def deliver_one():
            self.assertEqual(int.from_bytes(transport.pending[0][:4],'little'),0xa4172391)
            transport.pending.pop(0)
            p.deferred_events.pending_diplomacy_statements.extend([
                dict(fields=dict(FromPlayer=pid,ToPlayer=1),event_sequence=n+1)
                for n in range(pending)])
        transport.deliver_one=Mock(side_effect=deliver_one)
        p.deferred_events.drain=Mock()
        p.view_publisher.publish=Mock()
        stack=ExitStack();self.addCleanup(stack.close)
        for name in ('civ6_host.runtime.xp2_diplomacy_display_source.verify_live',
                     'civ6_host.runtime.xp2_initial_query_source.verify_live',
                     'civ6_host.runtime.xp2_initial_statement_factory.verify_image',
                     'civ6_host.runtime.network_dialogue.attach_database'):
            stack.enter_context(patch(name))
        stack.enter_context(patch.object(adapter,'_configuration',return_value=dict(
            initiator=1,players={pid:dict(leader='LEADER_TEST'),1:dict(human=True)},paused=False)))
        factory=stack.enter_context(patch.object(adapter.factories,'verify_request',
            return_value=dict(expected_registration=True,observed_registration=True)))
        receiver=stack.enter_context(patch(
            'civ6_host.runtime.a0_diplomacy_statement.require_receiver',return_value=True))
        return NS(saved=saved,backend=b,prefix=p,token=token,transport=transport,
                  observation=observation,action=action,overview=overview,
                  factory=factory,receiver=receiver,native_calls=native_calls)

    def test_ready_query_uses_real_saved_owner_guard_without_faking_busy(self):
        f=self.fixture()
        value=adapter.catalogue(f.saved,f.observation,sequence=12)
        self.assertEqual(value,f.overview)
        self.assertFalse(f.backend.busy)
        self.assertEqual(f.backend.stage,READY)
        self.assertEqual(f.saved.emit.call_args.kwargs['sequence'],12)
        self.assertEqual(f.transport.pending,[])

    def test_direct_request_delivers_real_shared_archive_pipeline_without_auto_response(self):
        f=self.fixture(active=True)
        result=adapter.initiate(f.saved,f.action,f.observation)
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['pending_statement_retained'])
        f.transport.deliver_one.assert_called_once()
        f.prefix.deferred_events.drain.assert_called_once()
        f.prefix.view_publisher.publish.assert_called_once()
        self.assertEqual(len(f.prefix.deferred_events.pending_diplomacy_statements),1)
        self.assertEqual(f.transport.pending,[])

    def test_native_false_is_refusal_without_inventing_or_delivering_an_archive(self):
        f=self.fixture(active=True,requested=False)
        result=adapter.initiate(f.saved,f.action,f.observation)
        self.assertEqual(result['status'],'refused')
        self.assertEqual(result['refusal_code'],'native_session_request_returned_false')
        f.transport.deliver_one.assert_not_called()
        f.prefix.view_publisher.publish.assert_not_called()
        self.assertEqual(f.prefix.deferred_events.pending_diplomacy_statements,[])

    def test_disabled_or_missing_receiver_refuses_before_request(self):
        for offered in (False,True):
            with self.subTest(offered=offered):
                f=self.fixture(active=True,offered=offered)
                if offered:f.receiver.return_value=False
                result=adapter.initiate(f.saved,f.action,f.observation)
                self.assertEqual(result['status'],'refused')
                self.assertNotIn(b'@xp2_initial_diplomacy_request',f.native_calls)
                f.factory.assert_not_called()

    def test_changed_factory_refuses_before_request(self):
        f=self.fixture(active=True)
        f.factory.side_effect=ValueError('foreign factory')
        with self.assertRaisesRegex(ValueError,'foreign factory'):
            adapter.initiate(f.saved,f.action,f.observation)
        self.assertNotIn(b'@xp2_initial_diplomacy_request',f.native_calls)
        f.transport.deliver_one.assert_not_called()

    def test_wrong_phase_foreign_owner_disabled_option_and_modal_are_rejected(self):
        for mutate in (
            lambda f:setattr(f.backend,'busy',True),
            lambda f:setattr(f.saved,'_backend',object()),
            lambda f:setattr(f.saved,'diplomacy_overview_diagnostic',False),
            lambda f:f.prefix.deferred_events.pending_diplomacy_statements.append({}),
            lambda f:f.token.world_input_prompts.update({0:{'defending_player':1}}),
        ):
            with self.subTest(change=mutate):
                f=self.fixture();mutate(f)
                with self.assertRaises((ValueError,RuntimeError)):
                    adapter.catalogue(f.saved,f.observation)
                self.assertEqual(f.native_calls,[])

    def test_multiple_pending_statements_are_not_an_invented_single_dialogue(self):
        f=self.fixture(active=True,pending=2)
        with self.assertRaisesRegex(RuntimeError,'multiple'):
            adapter.initiate(f.saved,f.action,f.observation)

    def test_war_effect_is_read_after_explicit_dialogue_closure_not_while_blocked(self):
        f=self.fixture(active=True)
        f.action['choice']='CHOICE_DECLARE_SURPRISE_WAR'
        f.overview['targets'][0]['selections'][0]['key']=f.action['choice']
        state=dict(player_id=0,turn=f.observation['turn'],defender_player_id=1,at_war=False)
        with patch('civ6_host.runtime.xp2_world_war._read_state',
                   side_effect=[state,dict(state,at_war=True)]) as read:
            result=adapter.initiate(f.saved,f.action,f.observation)
            self.assertTrue(result['pending_statement_retained'])
            self.assertEqual(read.call_count,1)
            self.assertEqual(f.saved._xp2_initial_war_verification,(0,1,f.observation['turn']))
            # Substitute the native result of the caller's explicit close.
            f.prefix.deferred_events.pending_diplomacy_statements.clear()
            f.backend.busy,f.backend.stage=False,READY
            adapter.catalogue(f.saved,f.observation,sequence=13)
            self.assertEqual(read.call_count,2)
            self.assertFalse(hasattr(f.saved,'_xp2_initial_war_verification'))
        self.assertTrue(any(call.args[0]=='native_xp2_initial_war_effect_verified'
                            for call in f.saved.emit.call_args_list))

    def test_false_war_request_does_not_schedule_an_invented_effect_readback(self):
        f=self.fixture(active=True,requested=False)
        f.action['choice']='CHOICE_DECLARE_SURPRISE_WAR'
        f.overview['targets'][0]['selections'][0]['key']=f.action['choice']
        with patch('civ6_host.runtime.xp2_world_war._read_state',
                   return_value=dict(at_war=False)) as read:
            result=adapter.initiate(f.saved,f.action,f.observation)
        self.assertEqual(result['status'],'refused')
        self.assertEqual(read.call_count,1)
        self.assertFalse(hasattr(f.saved,'_xp2_initial_war_verification'))


if __name__=='__main__':
    unittest.main()

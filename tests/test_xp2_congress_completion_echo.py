"""Congress owner and real transport methods; only native memory/calls mocked."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import ctypes as C
import struct
from types import SimpleNamespace as NS, MethodType
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_world_congress as world
from civ6_host.runtime import xp2_world_congress_source as source
from civ6_host.runtime import xp2_action_transport_source as action_source
from civ6_host.runtime import xp2_turn_source as turn_source
from civ6_host.runtime.native import native_action_transport as transport
from civ6_host.runtime.native import native_saved_world_congress as native
from civ6_host.runtime.native import native_player_operation_request as requests
from civ6_host.runtime.native import native_player_observation as observations
from civ6_host.runtime.native.native_host import DiagnosticHost
import test_xp2_congress_cycle as cycle_fixture
import test_xp2_turn_services as turn_fixture

ECHO = bytes.fromhex('5c4fdb1b00000000')


class CompletionEchoTests(unittest.TestCase):
    def setup_graph(self):
        helper = cycle_fixture.CycleTests()
        g, public = helper.started()
        g.saved.network_reference = dict(state=dict(player_id=0), major_player_ids=(0, 1))
        g.continuation.publication_count = 0
        g.timeline, g.delivered, g.native_events = [], [], []
        private = helper.private_form(g, public)
        private.update(enums=source.enum_values(),
            discussions={0:dict(sender=7, target=0, discussion_type=9)}, proposals={},
            order=dict(resolutions=[r['resolution_hash'] for r in public['resolutions']],
                       discussions=[0], proposals=[]),
            popup=dict(capability=True, current_era=3, initial_era=2, has_emergency_proposals=False))
        record = g.continuation._xp2_world_congress_catalogue
        g.continuation._xp2_world_congress_catalogue = replace(record, private=private)
        g.envelope, g.public, g.helper = dict(public=public, private=private), public, helper
        class Memory(turn_fixture.Memory):
            base = g.backend.core._handle
            context = g.backend.context
        g.memory_transport = m = Memory()
        t = transport.NativeActionTransport.__new__(transport.NativeActionTransport)
        t.backend, t.host, t.core, t.context = g.backend, g.backend.host, g.backend.core, g.backend.context
        t.host._check = MethodType(DiagnosticHost._check, t.host)
        t.transport_abi, t.pending, t.read = action_source.ABI, [], m.read
        m.transport = t
        g.prefix.actions = g.continuation.transport = t
        def empty():
            if t.pending or m.read(m.sentinel,16) != struct.pack('<QQ',m.sentinel,m.sentinel):
                raise ValueError('Fixture retained native queue is not empty')
        t.require_empty_native_queue = empty
        def emit(stage, **fields):
            g.native_events.append(dict(stage=stage, **fields))
            if stage == 'native_command_received_in_core_queue':
                g.delivered.append(bytes.fromhex(fields['archive_hex']))
                g.timeline.append('deliver_echo' if g.delivered[-1] == ECHO else 'deliver')
            g.event.emit(stage, **fields)
        t.emit = emit
        def flush():
            g.timeline.append('flush')
            return []
        g.continuation.trade_feedback = NS(flush=flush, check_checkpoint=lambda:None)
        return g

    def apply(self, g, *, payloads=(ECHO,), flags=b'\1\1\0\0', stop_request=None,
              inject_before_end=False, echo_residual=False, deferred_residual=False):
        t, m = g.prefix.actions, g.memory_transport
        action = cycle_fixture.ballot(g.public)
        request_count = 0
        emitted = False
        def request(core, context, pid, operation, values, **kwargs):
            nonlocal request_count
            source.authorize_request(kwargs['congress_permit'], core, context, pid, operation, values,
                core_sha256=kwargs['core_sha256'], submit=True, allow_empty=kwargs['allow_empty'])
            request_count += 1
            if request_count == stop_request:
                return dict(request_invoked=True)
            t.capture(t.host.pointer, m.make_archive(struct.pack('<III',0xc45de12f,pid,operation)))
            return dict(request_invoked=True)
        def virtual(core, pointer, slot, rva, result, *args):
            original = m.virtual(core,pointer,slot,rva,result,*args)
            if rva != action_source.ABI.drain_rva:
                return original
            def drain(context):
                nonlocal emitted
                original(context)
                kind = struct.unpack_from('<I',g.delivered[-1])[0]
                if not emitted and (kind == 0xd7c02786 or inject_before_end):
                    emitted = True
                    for payload in payloads:
                        t.capture(t.host.pointer, m.make_archive(payload))
                    m.put(m.base+turn_source.ABI.processor_flags_rva, flags)
                elif kind == 0x1bdb4f5c:
                    if echo_residual:
                        t.capture(t.host.pointer, m.make_archive(ECHO))
                    if deferred_residual:
                        g.prefix.deferred_events.pending.append(b'unknown-native-feedback')
            return drain
        def publish():
            g.timeline.append('publish'); g.continuation.publication_count += 1
        original_drain = g.prefix.deferred_events.drain_empty_receivers
        def drain_events():
            g.timeline.append('drain')
            if deferred_residual and g.delivered and g.delivered[-1] == ECHO:
                return 0
            return original_drain()
        m.original_factory = C.WINFUNCTYPE
        original_buffer = C.create_string_buffer
        def buffer(*args):
            value = original_buffer(*args); m.own(value); return value
        with ExitStack() as stack:
            stack.enter_context(g.helper.mode(g,active=True))
            stack.enter_context(patch.object(g.backend,'control',side_effect=lambda **kw:t.require_empty_native_queue()))
            stack.enter_context(patch.object(native,'query',return_value=deepcopy(g.envelope)))
            stack.enter_context(patch.object(requests,'request_player_operation',side_effect=request))
            stack.enter_context(patch.object(observations,'observe_player',return_value=deepcopy(g.continuation.observation)))
            stack.enter_context(patch.object(g.prefix.view_publisher,'publish',side_effect=publish))
            stack.enter_context(patch.object(g.prefix.deferred_events,'drain_empty_receivers',side_effect=drain_events))
            stack.enter_context(patch.object(transport,'virtual',side_effect=virtual))
            stack.enter_context(patch.object(C,'WINFUNCTYPE',side_effect=m.factory))
            stack.enter_context(patch.object(C,'create_string_buffer',side_effect=buffer))
            return world.apply(g.saved,action,deepcopy(g.continuation.observation))

    def test_retained_echo_uses_real_transport_and_one_final_publication(self):
        g = self.setup_graph(); result = self.apply(g)
        self.assertEqual(g.delivered[-2:], [bytes.fromhex('8627c0d7000000008412fab6'), ECHO])
        self.assertEqual(g.timeline[-4:], ['deliver_echo','drain','flush','publish'])
        self.assertEqual(g.timeline.count('publish'), 1)
        self.assertEqual(g.continuation.publication_count, 1)
        self.assertEqual(g.prefix.actions.pending, [])
        self.assertEqual(result['status'], 'pending')
        self.assertFalse(result['receipt']['native_effect_readback'])
        self.assertFalse(result['receipt']['congress_completion_claimed'])
        self.assertTrue(all(r['delivered'] for r in result['receipt']['native_journal']))
        self.assertEqual(result['receipt']['native_journal'][-1]['operation'], 'end_turn')
        self.assertEqual(len(result['receipt']['native_journal']), len(g.delivered)-1)
        self.assertEqual(sum(e['stage']=='native_game_turn_complete_echo_verified' for e in g.native_events),1)
        self.assertFalse(any(e['stage']=='before_native_game_update' for e in g.native_events))

    def test_no_echo_preserves_the_existing_single_publication(self):
        g = self.setup_graph(); result = self.apply(g,payloads=())
        self.assertEqual(result['status'],'pending')
        self.assertEqual(g.timeline.count('publish'),1)
        self.assertNotIn('deliver_echo',g.timeline)

    def test_unknown_archive_foreign_player_multiple_and_late_flags_refuse(self):
        for payloads, flags in (((b'unknown!',),b'\1\1\0\0'),
                ((struct.pack('<II',0x1bdb4f5c,1),),b'\1\1\0\0'),
                ((ECHO,ECHO),b'\1\1\0\0'), ((ECHO,),b'\1\0\0\0')):
            with self.subTest(payloads=payloads,flags=flags):
                g = self.setup_graph()
                with self.assertRaises((RuntimeError,ValueError)):
                    self.apply(g,payloads=payloads,flags=flags)
                self.assertEqual(g.prefix.actions.pending,list(payloads))
                self.assertNotIn('publish',g.timeline)
                self.assertNotIn('deliver_echo',g.timeline)

    def test_partial_confirmation_never_consumes_an_unrelated_echo(self):
        g = self.setup_graph()
        with self.assertRaisesRegex(RuntimeError,'unqualified native completion'):
            self.apply(g,stop_request=2,inject_before_end=True)
        self.assertEqual(g.prefix.actions.pending,[ECHO])
        self.assertNotIn('publish',g.timeline)
        self.assertNotIn('deliver_echo',g.timeline)
        self.assertTrue(g.continuation._xp2_world_congress_confirmation['partial_submission'])

    def test_residual_native_or_deferred_work_refuses_before_publication(self):
        for native_residual in (False,True):
            with self.subTest(native_residual=native_residual):
                g = self.setup_graph()
                with self.assertRaises(RuntimeError):
                    self.apply(g,echo_residual=native_residual,deferred_residual=not native_residual)
                self.assertNotIn('publish',g.timeline)
                self.assertIn('deliver_echo',g.timeline)


if __name__=='__main__':
    unittest.main()

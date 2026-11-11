import ctypes as C
from contextlib import contextmanager, nullcontext
import sys
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from civ6_host.runtime.network_turns import parse_activity, advance, submit


class NetworkTurnTests(unittest.TestCase):
    def test_multiple_active_humans_have_no_fixed_order(self):
        parsed = parse_activity(b'4|0|0|0,1,1,0;1,1,1,0;2,0,0,0', (0,1,2))
        self.assertEqual([r['player_id'] for r in parsed['rows'] if r['active']], [0,1])
        self.assertEqual(parsed['turn'], 4)

    def test_activity_rejects_out_of_range_identity_and_malformed_expected_roster(self):
        for raw, roster in ((b'4|64|0|0,1,1,0', (0,)),
                            (b'4|0|64|0,1,1,0', (0,)),
                            (b'4|0|0|64,1,1,0', (64,)),
                            (b'4|0|0|0,1,1,0', (False,))):
            with self.subTest(raw=raw, roster=roster), self.assertRaises(ValueError):
                parse_activity(raw, roster)

    def test_readiness_is_not_inferred_from_activity_or_human_flag(self):
        parsed = parse_activity(b'4|0|0|0,1,0,1;1,0,0,0', (0,1))
        self.assertTrue(parsed['rows'][0]['can_unready'])
        self.assertFalse(parsed['rows'][0]['active_complete'])
        with self.assertRaises(ValueError):
            parse_activity(b'4|0|0|0,1,2,0', (0,))

    def test_unknown_timer_never_approves_unready(self):
        owner = SimpleNamespace(prefix=SimpleNamespace(actions=Mock(pending=[]),
            deferred_events=Mock(pending=[])))
        with patch('civ6_host.runtime.network_owner.state', return_value={}), \
             patch('civ6_host.runtime.network_turns.controls', return_value={
                 'can_unready': True, 'timer_elapsed': None}):
            receipt = submit(owner, {'kind':'unready_turn'}, 0)
        self.assertEqual(receipt['status'], 'refused')
        owner.prefix.actions.request_unready_turn.assert_not_called()

    def test_poll_is_one_native_update_not_a_round_or_actor_loop(self):
        prefix = SimpleNamespace(actions=Mock(pending=[]), deferred_events=Mock(pending=[], pending_diplomacy_statements=[]),
                                 view_publisher=Mock())
        owner = SimpleNamespace(prefix=prefix, control=Mock(), emit=Mock())
        with patch('civ6_host.runtime.native.native_ai_round_pump.verify_source_evidence'), \
             patch('civ6_host.runtime.network_dialogue.retain', return_value=False):
            advance(owner)
        prefix.actions.update_game_once.assert_called_once_with()
        prefix.actions.request_end_turn.assert_not_called()
        event, = owner.emit.call_args.args
        self.assertEqual(event, 'native_lan_update_timing')
        self.assertGreaterEqual(owner.emit.call_args.kwargs['update_seconds'], 0)
        self.assertEqual(owner.emit.call_args.kwargs['guarded_host_callbacks']['outer_calls'], 0)

    def test_guarded_callback_timing_does_not_double_count_nested_callbacks(self):
        from civ6_host.runtime.callback_timing import measure
        from civ6_host.runtime.native.native_host import DiagnosticHost

        host = DiagnosticHost.__new__(DiagnosticHost)
        host.vtable = (C.c_void_p * 2)()
        host.functions = []
        def return_value():
            return 7

        host._bind(host.vtable, 8, C.c_uint32, [], return_value)
        inner = C.WINFUNCTYPE(C.c_uint32)(host.vtable[1])

        def call_twice():
            return inner() + inner()

        host._bind(host.vtable, 0, C.c_uint32, [], call_twice)
        outer = C.WINFUNCTYPE(C.c_uint32)(host.vtable[0])
        with patch('civ6_host.runtime.callback_timing.perf_counter_ns',
                   side_effect=[10, 60, 70, 110]), measure() as timing:
            self.assertEqual(outer(), 14)
            self.assertEqual(inner(), 7)
        self.assertTrue(all(sys.monitoring.get_tool(slot) is None for slot in (3, 4)))
        self.assertEqual(timing.report(), {
            'scope': 'update-thread-guarded-vtable-callbacks',
            'available': True, 'complete': True,
            'outer_calls': 2, 'nested_calls': 2, 'seconds': 90 / 1_000_000_000,
            'slots': {f'{call_twice.__qualname__}@0x0': {'calls': 1, 'seconds': 50 / 1_000_000_000},
                      f'{return_value.__qualname__}@0x8': {'calls': 1, 'seconds': 40 / 1_000_000_000}},
        })

    def test_xp2_source_proof_covers_fifo_and_publication_but_reader_does_not(self):
        from civ6_host.runtime import xp2_cache_source
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        phases = []
        reader_active = False

        @contextmanager
        def reader_scope(*unused):
            nonlocal reader_active
            reader_active = True
            try:
                yield
            finally:
                reader_active = False

        proof = xp2_cache_source.source()

        def step(name, repeats, expected_reader):
            self.assertIs(reader_active, expected_reader)
            for _ in range(repeats):
                self.assertIs(xp2_cache_source.source(), proof)
            phases.append(name)

        prefix = SimpleNamespace(
            actions=Mock(pending=[], update_game_once=lambda: step('update', 3, True)),
            event_arguments=SimpleNamespace(reader=SimpleNamespace(base=123, read=Mock())),
            deferred_events=Mock(pending=[], drain_empty_receivers=lambda: step('fifo', 50, False)),
            view_publisher=Mock(publish=lambda: step('publish', 3, False)))
        owner = SimpleNamespace(prefix=prefix, emit=Mock())
        boundary = SimpleNamespace(core_sha256=XP2_CORE_SHA256, verify_update=Mock(),
                                   retain=Mock(return_value=False), control=Mock())
        with patch.object(xp2_cache_source, '_verified_source', return_value=proof) as verify, \
             patch('civ6_host.runtime.xp2_preload_source.event_reader_scope', reader_scope), \
             patch('civ6_host.runtime.network_turns._completion'):
            advance(owner, boundary=boundary)
            self.assertEqual(verify.call_count, 2)
            self.assertIs(xp2_cache_source.source(), proof)
            self.assertEqual(verify.call_count, 3)  # No proof survives the interval.
        self.assertEqual(phases, ['update', 'fifo', 'publish'])
        boundary.control.assert_called_once_with(owner)
        self.assertEqual(owner.emit.call_args.args, ('native_lan_update_timing',))

    def test_xp2_changed_publication_source_refuses_interval_before_success(self):
        from civ6_host.runtime import xp2_cache_source
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        prefix = SimpleNamespace(actions=Mock(pending=[]),
            event_arguments=SimpleNamespace(reader=SimpleNamespace(base=123, read=Mock())),
            deferred_events=Mock(pending=[]), view_publisher=Mock())
        owner = SimpleNamespace(prefix=prefix, emit=Mock())
        boundary = SimpleNamespace(core_sha256=XP2_CORE_SHA256, verify_update=Mock(),
                                   retain=Mock(return_value=False), control=Mock())
        proof = xp2_cache_source.source()
        with patch.object(xp2_cache_source, '_verified_source',
                          side_effect=[proof, ValueError('changed source in publication')]), \
             patch('civ6_host.runtime.xp2_preload_source.event_reader_scope',
                   return_value=nullcontext()), \
             patch('civ6_host.runtime.network_turns._completion') as complete:
            with self.assertRaisesRegex(ValueError, 'changed source in publication'):
                advance(owner, boundary=boundary)
        prefix.actions.update_game_once.assert_called_once_with()
        prefix.deferred_events.drain_empty_receivers.assert_called_once_with()
        prefix.view_publisher.publish.assert_called_once_with()
        complete.assert_called_once_with(owner, core_sha256=XP2_CORE_SHA256)
        boundary.control.assert_not_called()
        owner.emit.assert_not_called()
        self.assertIsNone(xp2_cache_source._UPDATE_SOURCE.get())

    def test_poll_with_retained_dialogue_does_not_advance_or_choose(self):
        prefix = SimpleNamespace(actions=Mock(pending=[]), deferred_events=Mock(pending=[]),
                                 view_publisher=Mock())
        owner = SimpleNamespace(prefix=prefix, control=Mock())
        with patch('civ6_host.runtime.native.native_ai_round_pump.verify_source_evidence'), \
             patch('civ6_host.runtime.network_dialogue.retain', return_value=True):
            advance(owner)
        prefix.actions.update_game_once.assert_not_called()
        prefix.actions.request_end_turn.assert_not_called()

    def test_forced_turn_reuses_native_transport_with_userforced_reason(self):
        prefix = SimpleNamespace(actions=Mock(pending=[]), deferred_events=Mock(pending=[], pending_diplomacy_statements=[]),
                                 view_publisher=Mock())
        owner = SimpleNamespace(prefix=prefix, control=Mock(), emit=Mock(),
            network_reference={'major_player_ids':(0,1)})
        before = dict(turn=2, active=True, active_complete=True, can_unready=False)
        after = dict(turn=2, active=False, active_complete=False, can_unready=False)
        with patch('civ6_host.runtime.network_owner.state', return_value={}), \
             patch('civ6_host.runtime.network_ui.force_available', return_value=True), \
             patch('civ6_host.runtime.network_turns.controls', side_effect=[before,after]):
            receipt = submit(owner, {'kind':'force_end_turn'}, 0)
        self.assertEqual(receipt['status'], 'completed')
        prefix.actions.request_end_turn.assert_called_once_with(0,
            player_ids=(0,1), user_forced=True)
        prefix.actions.deliver_one.assert_called_once_with()

    def test_repeated_xp1_forced_turn_reports_submission_not_effect_or_ack(self):
        from civ6_host.runtime.xp1_turn_boundary import SavedTurnBoundary
        boundary = SavedTurnBoundary()
        before = dict(turn=2, active=False, active_complete=False, can_unready=False,
                      timer_elapsed=False)
        after = dict(before, timer_elapsed=True)
        prefix = SimpleNamespace(actions=Mock(pending=[]), deferred_events=Mock(pending=[]), view_publisher=Mock())
        owner = SimpleNamespace(prefix=prefix, _check_active=Mock(), emit=Mock(),
            network_reference={'major_player_ids':(0,1)})
        with patch.object(boundary,'state',return_value={}), \
             patch.object(boundary,'controls',side_effect=[before,after]), \
             patch.object(boundary,'refusal',return_value=None), \
             patch.object(boundary,'retain'), patch.object(boundary,'control'):
            receipt = submit(owner, {'kind':'force_end_turn'}, 0, boundary=boundary)
        self.assertEqual(receipt, dict(status='submitted',reason='native_turn_controls_unchanged',
                                      requested_action={'kind':'force_end_turn'}))
        prefix.actions.deliver_one.assert_called_once_with()
        prefix.actions.update_game_once.assert_not_called()
        self.assertEqual(owner.emit.call_args.args, ('official_lan_turn_request_submitted',))
        self.assertIs(owner.emit.call_args.kwargs['network_ack_inferred'], False)

    def test_unchanged_policy_does_not_generalize_to_other_requests_or_profiles(self):
        from civ6_host.runtime.xp1_turn_boundary import SavedTurnBoundary
        from civ6_host.runtime.network_turns import BASE_BOUNDARY
        owner = SimpleNamespace(_check_active=Mock())
        waiting = dict(turn=2, active=False, active_complete=False, can_unready=False)
        active = dict(waiting,active=True)
        for boundary,kind,controls in ((BASE_BOUNDARY,'force_end_turn',waiting),
                (SavedTurnBoundary(),'end_turn',waiting), (SavedTurnBoundary(),'unready_turn',waiting),
                (SavedTurnBoundary(),'force_end_turn',active)):
            with self.subTest(kind=kind,boundary=type(boundary).__name__), self.assertRaisesRegex(RuntimeError,'unresolved'):
                boundary.unchanged_request(owner, {'kind':kind}, controls, dict(controls))

    def test_active_expansion_turn_requires_fresh_matching_reactivation(self):
        from civ6_host.runtime.xp1_turn_boundary import BOUNDARY, XP2_BOUNDARY
        for boundary in (BOUNDARY, XP2_BOUNDARY):
            with self.subTest(core=boundary.core_sha256):
                self.check_active_reactivation(boundary)

    def check_active_reactivation(self, boundary):
        controls = dict(turn=13, active=True, active_complete=True, can_unready=False,
                        timer_elapsed=False)
        prefix = SimpleNamespace(actions=Mock(pending=[]), deferred_events=Mock(pending=[]),
                                 view_publisher=Mock())
        owner = SimpleNamespace(prefix=prefix, _check_active=Mock(), emit=Mock(),
                                network_reference={'major_player_ids':(0,1)})
        action = {'kind':'force_end_turn'}
        controller = Mock(reactivation_count=4)
        controller.reactivated_since.side_effect = [True,False]
        with patch.object(boundary,'state',return_value={}), \
             patch.object(boundary,'controls',return_value=controls), \
             patch.object(boundary,'refusal',return_value=None), \
             patch.object(boundary,'reactivation_owner',return_value=controller), \
             patch.object(boundary,'retain'), patch.object(boundary,'control'):
            self.assertEqual(submit(owner,action,0,boundary=boundary),
                             dict(status='submitted',reason='native_turn_reactivated_same_turn',
                                  requested_action=action))
            self.assertIs(owner.emit.call_args.kwargs['turn_advanced'],False)
            controller.reactivated_since.assert_called_once_with(4,0)
            with self.assertRaisesRegex(RuntimeError,'unresolved'):
                submit(owner,action,0,boundary=boundary)


if __name__ == '__main__':
    unittest.main()

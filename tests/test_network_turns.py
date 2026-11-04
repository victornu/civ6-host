import ctypes as C
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


if __name__ == '__main__':
    unittest.main()

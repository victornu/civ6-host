from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_spy_completion as runtime
from civ6_host.runtime.native import native_spy_completion as native
from test_xp2_espionage import SpySession


class CompletionQueueTests(unittest.TestCase):
    def setUp(self):
        self.c = NS(prefix=object(), identity=object(), observation={'player_id': 0},
                    owner=NS(busy=True, emit=Mock()), check=Mock())
        self.queue = runtime.CompletionQueue(self.c)
        self.shows = []
        self.results = {}
        def show(prefix, player, mission, sequence):
            self.shows.append((player, mission, sequence))
            return self.results.get(mission, 'shown')
        p = patch.object(native, 'display_state', side_effect=show)
        p.start(); self.addCleanup(p.stop)

    def test_first_immediate_then_one_newest_on_each_explicit_close(self):
        for seq, mission in ((10, 51), (11, 52), (14, 53)):
            self.queue.receive(seq, 0, mission)
        self.assertEqual(self.shows, [(0, 51, 10)])
        self.assertEqual(self.queue.visible(), dict(event_sequence=10, mission_id=51))
        self.queue.close(self.queue.visible())
        self.assertEqual(self.shows[-1], (0, 53, 14))
        self.queue.close(self.queue.visible())
        self.assertEqual(self.shows[-1], (0, 52, 11))
        self.queue.close(self.queue.visible())
        self.assertIsNone(self.queue.visible())
        self.queue.check_checkpoint()

    def test_suppressed_popped_record_does_not_drain_older_records(self):
        self.results[53] = 'suppressed'
        for seq, mission in ((10, 51), (11, 52), (14, 53)):
            self.queue.receive(seq, 0, mission)
        self.queue.close(self.queue.visible())
        self.assertIsNone(self.queue.visible())
        self.assertEqual(self.queue.pending, [dict(event_sequence=11, mission_id=52)])
        self.assertEqual(self.shows, [(0, 51, 10), (0, 53, 14)])
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            self.queue.check_checkpoint()
        # A later new event displays directly, retaining the old queue exactly.
        self.queue.receive(15, 0, 54)
        self.queue.close(self.queue.visible())
        self.assertEqual(self.shows[-1], (0, 52, 11))

    def test_foreign_missing_and_duplicate_events_never_create_history_choices(self):
        self.queue.receive(1, 2, 20)
        self.assertEqual(self.shows, [])
        self.results[21] = 'missing'
        self.queue.receive(2, 0, 21)
        self.assertIsNone(self.queue.visible())
        for seq in (1, 2, True, -1, 0x100000000):
            with self.subTest(seq=seq), self.assertRaises(ValueError):
                self.queue.receive(seq, 0, 22)
        self.queue.check_checkpoint()

    def test_occurrence_is_detached_stale_close_refused_and_episode_bound(self):
        self.queue.receive(5, 0, 30)
        view = self.queue.visible();view['mission_id'] = 31
        with self.assertRaises(ValueError):self.queue.close(view)
        with self.assertRaises(ValueError):self.queue.check_checkpoint()
        self.c.identity = object()
        with self.assertRaisesRegex(ValueError, 'owner'):self.queue.visible()

    def test_existing_bbg_feedback_delivers_gameplay_once_then_retains_identity(self):
        from civ6_host.runtime.xp2_bbg_trade_feedback import TradeFeedback
        self.c.publishing = False
        self.c.prefix = NS(deferred_events=NS(pending=[], _draining_empty_receivers=False))
        q = runtime.CompletionQueue(self.c)
        feedback = TradeFeedback(self.c, object(), object())
        feedback.spy_completions = q
        feedback._deliver_spy = Mock()
        feedback.spy(8, 0, 42)
        self.assertEqual(feedback.flush(), [])
        feedback._deliver_spy.assert_called_once_with(8, 0, 0, 42)
        q.close(q.visible())
        feedback._deliver_spy.assert_called_once()


class CompletionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.s = s = SpySession();self.addCleanup(s.close)
        s.backend.emit = s.emit
        s.continuation.trade_feedback = NS(spy_completions=runtime.CompletionQueue(s.continuation))
        self.q = s.continuation.trade_feedback.spy_completions
        self.q.current = dict(event_sequence=30, mission_id=51)
        self.current = dict(**self.q.current, name='Ada', level=1, operation=12,
            completion_turn=17, initial_result=1, escape_result=-1, city_name='Harbor',
            plot_id=6, loot_info=-1)
        self.renew = dict(kind='spy_renew', unit_id=9, **self.q.current,
            operation_type='UNITOPERATION_SPY_LISTENING_POST', operation_hash=0xf0000011,
            x=2, y=1, plot_id=6)
        self.dismiss = dict(kind='spy_completion_dismiss', **self.q.current)
        self.value = dict(schema='civ6-host.spy-completion.v1', player_id=0, turn=17,
            width=4, height=3, current=self.current,
            offers=[dict(action=a, turns=-1, success_percent=-1, failure_percent=-1,
                         captured_or_killed_percent=-1) for a in (self.dismiss, self.renew)])
        self.patcher = patch.object(native, 'catalog', return_value=deepcopy(self.value))
        self.patcher.start();self.addCleanup(self.patcher.stop)
        runtime.catalogue(s.saved, s.observation)
        s.continuation.explicit_espionage = deepcopy(s.before)
        s.activate();s.calls.clear()

    def test_dismissal_is_explicit_local_state_not_a_fabricated_native_order(self):
        result = runtime.apply(self.s.saved, self.dismiss, self.s.observation)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['observation'], self.s.observation)
        self.assertTrue(result['receipt']['local_presentation_completed'])
        self.assertFalse(result['receipt']['native_archive_delivered'])
        self.assertFalse(result['receipt']['simulation_request_issued'])
        self.assertEqual(self.s.delivered, [])
        self.assertEqual(self.s.continuation.publication_count, 0)
        self.assertIsNone(self.q.current)
        with self.assertRaises(ValueError):
            runtime.apply(self.s.saved, self.dismiss, self.s.observation)

    def test_renew_closes_before_delivery_even_when_application_remains_pending(self):
        s = self.s
        self.q.pending = [dict(event_sequence=31, mission_id=52)]
        def display(*args):
            s.calls.append('completion_display')
            self.assertEqual(len(s.prefix.actions.pending), 1)
            self.assertEqual(s.delivered, [])
            return 'shown'
        original = s.prefix.runtime.evaluate_text
        def evaluate(child, source, name, **kwargs):
            if name == b'@xp2_spy_completion_request':
                s.prefix.actions.pending.append(s.archive)
                return b'submitted'
            return original(child, source, name, **kwargs)
        with patch.object(s.prefix.runtime, 'evaluate_text', side_effect=evaluate), \
                patch.object(native, 'request_source', return_value=b'fixture_request'), \
                patch.object(native, 'display_state', side_effect=display), \
                patch.object(native, 'read_effect', return_value=dict(applied=False, pending=True)):
            result = runtime.apply(s.saved, self.renew, s.observation)
        self.assertEqual(result['status'], 'pending')
        self.assertTrue(result['receipt']['native_archive_delivered'])
        self.assertFalse(result['receipt']['native_effect_readback'])
        self.assertFalse(result['receipt']['mission_completion_claimed'])
        self.assertEqual(self.q.current, dict(event_sequence=31, mission_id=52))
        self.assertEqual(s.delivered, [s.archive])

    def test_foreign_current_occurrence_is_not_a_renewable_history_record(self):
        self.q.current = dict(event_sequence=33, mission_id=51)
        with self.assertRaisesRegex(ValueError, 'stale or foreign'):
            runtime.apply(self.s.saved, self.renew, self.s.observation)
        self.assertEqual(self.s.delivered, [])


if __name__ == '__main__':
    unittest.main()

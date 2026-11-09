import sys
import unittest
import pstats
from unittest.mock import patch

from civ6_host.runtime.command_profiling import CommandProfiler


IDENTITY = {'episode_id': 'episode-1', 'game_generation': 'generation-1'}


class CommandProfilerTests(unittest.TestCase):
    def test_profiles_only_command_and_response_for_first_eligible_request(self):
        events = []
        profiler = CommandProfiler(True,
            lambda name, **fields: events.append((name, fields)), IDENTITY)
        with profiler.measure('command', 'act', 1, 0):
            sum(range(8))
        with profiler.measure('response', 'act', 1, 0):
            sum(range(12))
        with profiler.measure('command', 'act', 2, 0):
            sum(range(32))
        with profiler.measure('response', 'close', 0, 0):
            sum(range(32))

        self.assertEqual([name for name, _ in events], [
            'native_command_python_profile', 'native_command_python_profile'])
        for (_, record), phase in zip(events, ('command', 'response')):
            self.assertEqual(record['phase'], phase)
            self.assertEqual(record['episode_id'], 'episode-1')
            self.assertEqual(record['game_generation'], 'generation-1')
            self.assertEqual((record['player_id'], record['sequence'], record['operation']),
                             (0, 1, 'act'))
            self.assertFalse(record['actor_channel'])
            self.assertGreaterEqual(record['wall_seconds'], 0)
            self.assertLessEqual(record['reported_function_count'], 80)
            self.assertEqual(record['reported_function_count'], len(record['functions']))
            self.assertEqual(record['truncated'],
                             record['total_function_count'] > record['reported_function_count'])
            self.assertTrue(all('args' not in row for row in record['functions']))

    def test_disabled_path_does_not_construct_cprofile(self):
        events = []
        profiler = CommandProfiler(False, lambda name, **fields: events.append(name), IDENTITY)
        import cProfile
        with patch.object(cProfile, 'Profile', side_effect=AssertionError('constructed')):
            with profiler.measure('command', 'act', 1, 0):
                pass
        self.assertEqual(events, [])

    def test_callback_exception_is_emitted_and_original_exception_propagates(self):
        events = []
        profiler = CommandProfiler(True,
            lambda name, **fields: events.append((name, fields)), IDENTITY)
        failure = LookupError('target failure')
        with self.assertRaises(LookupError) as caught:
            with profiler.measure('command', 'poll', 7, 1):
                raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(events[0][1]['outcome'], 'error')

    def test_emit_failure_does_not_mask_target_exception(self):
        failure = LookupError('target failure')
        def emit(_name, **_fields):
            raise RuntimeError('emit failure')
        profiler = CommandProfiler(True, emit, IDENTITY)
        with self.assertRaises(LookupError) as caught:
            with profiler.measure('command', 'act', 1, 0):
                raise failure
        self.assertIs(caught.exception, failure)

    def test_external_profiler_refuses_before_target_invocation(self):
        events = []
        profiler = CommandProfiler(True,
            lambda name, **fields: events.append((name, fields)), IDENTITY)
        called = []
        with patch.object(sys, 'getprofile', return_value=lambda *_: None):
            with self.assertRaisesRegex(RuntimeError, 'another profiler'):
                with profiler.measure('command', 'act', 1, 0):
                    called.append(True)
        self.assertEqual(called, [])
        self.assertEqual(events, [])

    def test_metadata_validation_is_strict(self):
        with self.assertRaises(TypeError):
            CommandProfiler(1, lambda *_args, **_kwargs: None, IDENTITY)
        with self.assertRaises(ValueError):
            CommandProfiler(True, lambda *_args, **_kwargs: None, {})
        profiler = CommandProfiler(False, lambda *_args, **_kwargs: None, IDENTITY)
        for fields in (('Command', 'act', 1, 0), ('command', 'act', True, 0),
                       ('command', 'act', 1, False)):
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError):
                    with profiler.measure(*fields):
                        pass

    def test_profile_strings_are_bounded_and_report_truncation(self):
        profiler = CommandProfiler(True, lambda *_args, **_kwargs: None, IDENTITY)
        fake = type('FakeProfile', (), {})()
        # Exercise the pure formatter without creating a large source file or
        # running a profiled workload.
        class FakeStats:
            stats = {('f' * 300, 2, 'g' * 200): (1, 2, 0.1, 0.2, {})}
            total_tt = 0.1
        with patch.object(pstats, 'Stats', return_value=FakeStats()):
            row = profiler._record(fake, 0.2, 'command', 'act', 1, 0, False)['functions'][0]
        self.assertEqual(len(row['filename']), 256)
        self.assertEqual(len(row['function']), 160)
        self.assertTrue(row['filename_truncated'])
        self.assertTrue(row['function_truncated'])


if __name__ == '__main__':
    unittest.main()

"""Bounded Python-only tests for the opt-in current XP2 Load profile seam."""
import cProfile
import inspect
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from civ6_host.runtime.command_profiling import CommandProfiler
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
from civ6_host.runtime.native.native_official_load import _load_raw_with_optional_profile
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.workers.network_worker import _emit_native_load_profile


IMAGE = select('xp2-gamecore-current-092abfbb',
               core_path=known_path('xp2-gamecore-current-092abfbb'))
PROFILE = profile_for_core(known_path('xp2-gamecore-current-092abfbb'),
    mode='context', execution_image=IMAGE)
CORE_IDENTITY = dict(actual_core_sha256=PROFILE.core_sha256,
    reference_core_sha256=PROFILE.reference_core_sha256,
    execution_profile_id=PROFILE.execution_image.id,
    execution_image_sha256=PROFILE.execution_image.image_sha256)
EPISODE = '6a65f42c-28fe-49dd-9333-04d42bb9449f'
IDENTITY = DiagnosticEpisodeIdentity(EPISODE, 'native-' + EPISODE)


def backend(load_raw, enabled=True):
    return SimpleNamespace(command_profile_diagnostic=enabled,
        profile=PROFILE,
        load_abi=SimpleNamespace(core_sha256=PROFILE.reference_core_sha256),
        load_raw=load_raw)


class NativeLoadProfilingTests(unittest.TestCase):
    def test_opt_in_profiles_only_load_and_captures_current_reference_identity(self):
        native = Mock(return_value=7)
        owner = backend(native)
        self.assertEqual(_load_raw_with_optional_profile(owner), 7)
        native.assert_called_once_with()
        captured = owner._command_load_profile
        self.assertFalse(captured['callback_failed'])
        self.assertGreaterEqual(captured['wall_seconds'], 0)
        self.assertEqual(captured['core_identity'], CORE_IDENTITY)
        self.assertIsInstance(captured['profiler'], cProfile.Profile)

    def test_load_exception_object_is_preserved_and_never_marked_success(self):
        failure = LookupError('load callback failure')
        native = Mock(side_effect=failure)
        owner = backend(native)
        with self.assertRaises(LookupError) as caught:
            _load_raw_with_optional_profile(owner)
        self.assertIs(caught.exception, failure)
        self.assertTrue(owner._command_load_profile['callback_failed'])

    def test_load_exception_survives_profiler_and_backend_handoff_failures(self):
        failure = LookupError('original load failure')

        class BrokenProfiler:
            def enable(self):
                pass
            def disable(self):
                raise RuntimeError('disable failure')

        class BrokenBackend:
            command_profile_diagnostic = True
            profile = PROFILE
            load_abi = SimpleNamespace(core_sha256=PROFILE.reference_core_sha256)
            def load_raw(self):
                raise failure
            def __setattr__(self, name, value):
                if name == '_command_load_profile':
                    raise RuntimeError('handoff failure')
                object.__setattr__(self, name, value)

        owner = BrokenBackend()
        with patch.object(cProfile, 'Profile', return_value=BrokenProfiler()):
            with self.assertRaises(LookupError) as caught:
                _load_raw_with_optional_profile(owner)
        self.assertIs(caught.exception, failure)

    def test_normal_path_diagnostic_handoff_failure_is_explicit(self):
        class BrokenBackend:
            command_profile_diagnostic = True
            profile = PROFILE
            load_abi = SimpleNamespace(core_sha256=PROFILE.reference_core_sha256)
            def load_raw(self):
                return 7
            def __setattr__(self, name, value):
                if name == '_command_load_profile':
                    raise RuntimeError('handoff failure')
                object.__setattr__(self, name, value)

        with self.assertRaisesRegex(RuntimeError, 'handoff failure'):
            _load_raw_with_optional_profile(BrokenBackend())

    def test_external_profiler_refuses_before_load(self):
        native = Mock(return_value=7)
        owner = backend(native)
        with patch.object(sys, 'getprofile', return_value=lambda *_args: None):
            with self.assertRaisesRegex(RuntimeError, 'another profiler'):
                _load_raw_with_optional_profile(owner)
        native.assert_not_called()
        self.assertFalse(hasattr(owner, '_command_load_profile'))

    def test_disabled_path_does_not_construct_profile(self):
        native = Mock(return_value=7)
        owner = backend(native, enabled=False)
        with patch.object(cProfile, 'Profile', side_effect=AssertionError('constructed')):
            self.assertEqual(_load_raw_with_optional_profile(owner), 7)
        native.assert_called_once_with()
        self.assertFalse(hasattr(owner, '_command_load_profile'))

    def test_handoff_emits_once_with_real_identity_and_discards_profile(self):
        profile = cProfile.Profile()
        profile.enable()
        sum(range(20))
        profile.disable()
        continuation = SavedContinuation.__new__(SavedContinuation)
        continuation.identity = IDENTITY
        owner = SimpleNamespace(backend=SimpleNamespace(_command_load_profile=dict(
            profiler=profile, wall_seconds=0.01, callback_failed=False,
            core_identity=CORE_IDENTITY)),
            continuation=continuation)
        protocol = SimpleNamespace(identity=IDENTITY)
        events = []
        emitted = _emit_native_load_profile(owner, protocol, 0,
            lambda name, **fields: events.append((name, fields)))
        self.assertTrue(emitted)
        self.assertEqual(len(events), 1)
        name, record = events[0]
        self.assertEqual(name, 'native_load_python_profile')
        self.assertEqual((record['episode_id'], record['game_generation']),
                         (EPISODE, 'native-' + EPISODE))
        self.assertEqual((record['operation'], record['phase'], record['sequence']),
                         ('reset', 'load', 0))
        self.assertEqual(record['core_identity'], CORE_IDENTITY)
        self.assertFalse(record['actor_channel'])
        self.assertLessEqual(record['reported_function_count'], 80)
        self.assertFalse(any('args' in row for row in record['functions']))
        self.assertFalse(hasattr(owner.backend, '_command_load_profile'))

    def test_handoff_refuses_identity_or_failure_mismatch_and_always_discards_capture(self):
        for failed, identity in ((True, IDENTITY), (False, object())):
            with self.subTest(failed=failed, identity=identity):
                continuation = SavedContinuation.__new__(SavedContinuation)
                continuation.identity = identity
                owner = SimpleNamespace(backend=SimpleNamespace(_command_load_profile=dict(
                    profiler=cProfile.Profile(), wall_seconds=0.0,
                    callback_failed=failed, core_identity=CORE_IDENTITY)),
                    continuation=continuation)
                events = []
                with self.assertRaises(RuntimeError):
                    _emit_native_load_profile(owner, SimpleNamespace(identity=IDENTITY), 0,
                        lambda name, **fields: events.append((name, fields)))
                self.assertEqual(events, [])
                self.assertFalse(hasattr(owner.backend, '_command_load_profile'))

    def test_load_profile_handoff_occurs_after_saved_commands_begin(self):
        from civ6_host.runtime.workers import network_worker

        open_lines = inspect.getsource(network_worker._open_xp1).splitlines()
        begin_line = next(i for i, line in enumerate(open_lines)
                          if 'saved.begin_commands()' in line)
        return_line = next(i for i, line in enumerate(open_lines)
                           if 'return saved, compare_initial' in line)
        self.assertLess(begin_line, return_line)
        main_lines = inspect.getsource(network_worker.main).splitlines()
        open_call = next(i for i, line in enumerate(main_lines)
                         if '_open_xp1(closure, path, emit, win)' in line)
        profile_call = next(i for i, line in enumerate(main_lines)
                            if '_emit_native_load_profile(owner, protocol, local_player, emit)' in line)
        self.assertLess(open_call, profile_call)


if __name__ == '__main__':
    unittest.main()

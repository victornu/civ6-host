"""Exercise the saved-session query snapshot lease on its retained owner graph."""
from pathlib import Path
from types import SimpleNamespace as NS
import threading
import unittest
from unittest.mock import patch

from civ6_host.runtime.saved_load_job_observer import SavedLoadJobObserver
from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from test_xp1_world_input_owner import Fixture
from test_world_war_producer import quiescent


class WarReadOwnerTests(unittest.TestCase):
    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        observer = SavedLoadJobObserver.__new__(SavedLoadJobObserver)
        observer.backend = f.backend
        observer.busy = False
        observer._query_owner = None
        observer.last_snapshots = {}
        observer.identity = dict(
            host_base=0x12340000,
            executable_path=str(Path(__file__).resolve()),
            os_thread_id=f.backend.thread[1],
        )
        observer.core = dict(profile=2, sha256=f.backend.load_abi.core_sha256,
                             source_sha256=jobs.SOURCE_HASH_BY_PROFILE[2],
                             source_build='fixture-build')
        observer.build = dict(host_sha256='fixture-host')
        observer.layout_words = tuple(range(28))
        observer._layout = lambda: observer.layout_words
        observer.api = NS(
            main_module=lambda: observer.identity['host_base'],
            current_thread_id=lambda: f.backend.thread[1],
            module_filename=lambda _base: observer.identity['executable_path'],
        )
        f.backend.jobs = observer
        f.backend.snapshot_phase = None
        return f, observer

    def test_query_snapshot_uses_exact_ready_owner_without_active_flags(self):
        f, observer = self.fixture()
        backend, saved = f.backend, f.saved
        backend.snapshot_phase = 'prior-phase'
        snapshots = []

        def capture(*_args):
            snapshots.append((backend.snapshot_phase, backend.busy, backend.stage,
                              observer._query_owner, observer._exclusive()))
            return quiescent()

        with patch('civ6_host.runtime.saved_load_job_observer.capture_registry', capture):
            before = observer.query_snapshot(saved, 'before')
            after = observer.query_snapshot(saved, 'after')

        self.assertEqual(before, after)
        self.assertEqual([row[0] for row in snapshots], ['before', 'after'])
        self.assertTrue(all(row[1] is False for row in snapshots))
        self.assertTrue(all(row[2] == 'xp1-continuation-ready' for row in snapshots))
        self.assertTrue(all(row[3] is saved and row[4] is True for row in snapshots))
        self.assertIs(backend.busy, False)
        self.assertEqual(backend.stage, 'xp1-continuation-ready')
        self.assertEqual(backend.snapshot_phase, 'prior-phase')
        self.assertIsNone(observer._query_owner)

    def test_real_observer_call_rejects_query_without_lease(self):
        _f, observer = self.fixture()
        with self.assertRaisesRegex(RuntimeError, 'exclusive saved Load boundary'):
            observer()

    def test_wrong_saved_owner_and_backend_owner_are_rejected(self):
        f, observer = self.fixture()
        wrong_saved = SavedLoadOwner.__new__(SavedLoadOwner)
        wrong_saved.backend = object()
        with self.assertRaises(ValueError):
            observer.query_snapshot(wrong_saved, 'before')

        other_observer = SavedLoadJobObserver.__new__(SavedLoadJobObserver)
        other_observer.backend = object()
        with self.assertRaises(ValueError):
            other_observer.query_snapshot(f.saved, 'before')

    def test_invalid_phase_nested_query_and_existing_observer_lease_are_rejected(self):
        f, observer = self.fixture()
        with self.assertRaises(ValueError):
            observer.query_snapshot(f.saved, 'during')

        observer._query_owner = f.saved
        with self.assertRaises(ValueError):
            observer.query_snapshot(f.saved, 'before')
        observer._query_owner = None

        observer.busy = True
        with self.assertRaises(ValueError):
            observer.query_snapshot(f.saved, 'before')
        observer.busy = False

    def test_exception_restores_query_lease_and_snapshot_phase(self):
        f, observer = self.fixture()
        backend = f.backend
        backend.snapshot_phase = 'kept'

        def fail(*_args):
            self.assertIs(observer._query_owner, f.saved)
            self.assertTrue(observer._exclusive())
            raise LookupError('fixture registry read failed')

        with patch('civ6_host.runtime.saved_load_job_observer.capture_registry', fail):
            with self.assertRaisesRegex(LookupError, 'fixture registry read failed'):
                observer.query_snapshot(f.saved, 'after')
        self.assertEqual(backend.snapshot_phase, 'kept')
        self.assertIsNone(observer._query_owner)
        self.assertIs(backend.busy, False)
        self.assertEqual(backend.stage, 'xp1-continuation-ready')

    def test_tampered_stage_or_wrong_thread_fails_actual_query_guard(self):
        f, observer = self.fixture()
        backend, saved = f.backend, f.saved
        original_stage = backend.stage
        backend.stage = 'copied'
        with self.assertRaises(ValueError):
            observer.query_snapshot(saved, 'before')
        backend.stage = original_stage

        errors = []
        def query_on_other_thread():
            try:
                observer.query_snapshot(saved, 'before')
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=query_on_other_thread)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertIsNone(observer._query_owner)


if __name__ == '__main__':
    unittest.main()

"""Collector plumbing on retained offline fixtures; no game or Tuner calls."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from types import ModuleType
import sys
import unittest
from unittest.mock import patch

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.workers import capture_phase1_bundle994 as tool
from civ6_host.runtime import capture_response_continuation as continuation


@lru_cache(maxsize=1)
def retained_fixtures():
    """Reuse the existing fake database/process/client, importing hosted code."""
    root = resource_root()
    def load(name, filename, extra=None):
        path = root / 'tests' / filename
        source = path.read_text(encoding='utf-8')
        source = source.replace('from civ6rl.', 'from civ6_host.runtime.native.')
        source = source.replace('from civ6rl import ', 'from civ6_host.runtime.native import ')
        source = source.replace('from tools import capture_phase1_bundle994 as tool',
                                'from civ6_host.runtime.workers import capture_phase1_bundle994 as tool')
        source = source.replace('from tests.test_database_capture_bundle993 import Reader', '')
        source = source.replace('from tests.test_native_localization_capture import Process', '')
        source = source.replace('from tests.test_native_localization_logical_export import installation_fixture, Process',
                                'from _host_capture_localization_fixtures import installation_fixture, Process')
        module = ModuleType(name)
        module.__file__ = str(path)
        module.__dict__.update(extra or {})
        sys.modules[name] = module
        exec(compile(source, str(path), 'exec'), module.__dict__)
        return module
    database = load('_host_capture_database_fixtures', 'test_database_capture_bundle993.py')
    localization = load('_host_capture_process_fixtures', 'test_native_localization_capture.py')
    load('_host_capture_localization_fixtures', 'test_native_localization_logical_export.py',
         {'Reader': database.Reader, 'Process': localization.Process})
    return load('_host_capture_collector_fixtures', 'test_phase1_capture994.py', {'Reader': database.Reader})


class CaptureContinuationIntegration(unittest.TestCase):
    def fixture(self):
        original = retained_fixtures()
        case = original.Phase1Capture994Tests('runTest')
        case.setUp()
        self.addCleanup(case.doCleanups)
        return original, case

    def predecessor(self, case):
        path = case.root / 'predecessor.json'
        data = b'{}'
        path.write_bytes(data)
        return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def test_default_preflight_keeps_original_provenance_and_does_not_validate_prefix(self):
        original, case = self.fixture()
        installation = original.response_installation_fixture(case.root / 'writer', case.backend.source['identity'])
        with patch.object(continuation, 'validate_predecessor', side_effect=AssertionError('unexpected continuation')):
            result = tool.preflight(**case.options, response_file_installation=installation)
        self.assertNotIn('predecessor', result['response_file_transport'])
        self.assertFalse(case.client.connected)

    def test_predecessor_without_installation_refuses_before_process_access(self):
        _, case = self.fixture()
        predecessor = self.predecessor(case)
        with patch.object(case.backend, 'snapshot_process', side_effect=AssertionError('process accessed')):
            with self.assertRaisesRegex(ValueError, 'requires its explicit writer installation'):
                tool.preflight(**case.options, response_file_predecessor=predecessor)
            with self.assertRaisesRegex(ValueError, 'requires its explicit writer installation'):
                tool.capture(**case.options, expected_player_id=0, expected_turn=146,
                             response_file_predecessor=predecessor)
        self.assertFalse(case.client.connected)

    def test_prefix_process_mismatch_refuses_before_client_connection(self):
        original, case = self.fixture()
        installation = original.response_installation_fixture(case.root / 'writer', case.backend.source['identity'])
        wrong = dict(case.backend.source['identity'], pid=9999)
        with patch.object(continuation, 'validate_predecessor', return_value={'process': wrong}):
            with self.assertRaisesRegex(ValueError, 'Continuation process identity differs'):
                tool.preflight(**case.options, response_file_installation=installation,
                               response_file_predecessor=self.predecessor(case))
        self.assertFalse(case.client.connected)

    def test_full_collector_selects_explicit_continued_client_and_keeps_save_bracketing(self):
        original, case = self.fixture()
        calls, options = case.logical_export_fixture()
        installation = original.response_installation_fixture(case.root / 'writer', case.backend.source['identity'])
        record = json.loads(Path(installation['path']).read_bytes())
        registration = json.loads(Path(record['registration']['path']).read_bytes())
        predecessor = self.predecessor(case)
        snapshot = case.root / 'prefix.log'
        snapshot.write_bytes(b'fixture snapshot')
        snapshot_pin = dict(path=str(snapshot), bytes=snapshot.stat().st_size,
                            sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
        checked = dict(process=case.backend.source['identity'], prepared=registration['prepared'],
                       prefix_snapshot=snapshot_pin, receipts=[])
        with patch.object(continuation, 'validate_predecessor', return_value=checked) as validated, \
                patch.object(continuation, 'ContinuedResponseFileClient', side_effect=case.client.factory) as selected, \
                patch.object(tool, 'ResponseFileClient', side_effect=AssertionError('fresh transport selected')):
            result = case.capture(**options, response_file_installation=installation,
                                  response_file_predecessor=predecessor, client_factory=tool.FileClient)
            from civ6_host.runtime.native import native_official_bundle
            dependencies = {}
            native_official_bundle._response_transport(result, dependencies)
        self.assertEqual(selected.call_count, 1)
        self.assertEqual(selected.call_args.kwargs['predecessor'], predecessor)
        self.assertEqual(selected.call_args.kwargs['installation'], installation)
        self.assertTrue(all(c.kwargs == {'exact_directory': False} for c in validated.call_args_list))
        self.assertEqual(result['response_file_transport']['predecessor'], predecessor)
        self.assertEqual(result['response_file_transport']['predecessor_dependencies'], [predecessor, snapshot_pin])
        self.assertEqual(dependencies[str(snapshot)], snapshot_pin['sha256'])
        self.assertEqual(result['response_file_transport'], result['preflight']['response_file_transport'])
        self.assertEqual([c['saved'] for c in calls], [False, True])
        self.assertEqual(case.client.save_calls, 1)
        self.assertTrue(case.client.closed)


if __name__ == '__main__':
    unittest.main()

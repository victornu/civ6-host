"""Read-only regression of the retained XP2 T2/Unload/Destroy receipt.

The old supervisor remains a refusal. A copy of its pre-close-review state is
used to exercise the corrected reviewer; no native result is rewritten.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native.network_session import NativeNetworkSession, xp1_loaded_close_evidence
from civ6_host.runtime.native.native_action_session import NativeActionSession

RUN = resource_root()/'work/xp2-client-sessions/run-aaf5be223aac4d2cae611caf076b15c9'
STAGES = ('before_xp1_saved_loaded_close', 'before_xp2_loaded_unload',
          'xp2_loaded_unload_returned', 'before_xp2_loaded_destroy',
          'xp2_loaded_destroy_returned', 'xp2_loaded_lifetime_closed',
          'xp1_saved_loaded_close_returned', 'official_session_response',
          'official_session_controlled_stop')
PINS = {
    'closure.json': 'e3b07d9cda47b2acd9b3306cec7c7217da9c4acccf895a2a0c84ec389aeb089f',
    'supervisor.json': 'f4f0ef86cfd31803b93ed58b8a7576df54802e1bb07a85a4abda30cab7acf764',
    'events.jsonl': '808142be2a86d06c63280beb08effbd78fc4a75d4bf8b16e383e4a49b5c46c8b',
    'loaded-lifetime-result.json': '52ba3cd41db0df64a14e3e73b9a165a99b5fcb33a2c8a2ef94e24788593036ef',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless((RUN/'supervisor.json').is_file(), 'Retained private XP2 attempt08 required')
class XP2CloseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert {name: digest(RUN/name) for name in PINS} == PINS
        cls.original_report = json.loads((RUN/'supervisor.json').read_bytes())
        cls.closure_raw = (RUN/'closure.json').read_bytes()
        cls.closure = json.loads(cls.closure_raw)
        cls.original_result = json.loads((RUN/'loaded-lifetime-result.json').read_bytes())
        cls.events = []
        for line in (RUN/'events.jsonl').read_bytes().splitlines():
            event = json.loads(line)
            if event['stage'] in STAGES and (event['stage'] != 'official_session_response'
                                             or event.get('operation') == 'close'):
                cls.events.append(event)

    def original(self):
        report = deepcopy(self.original_report)
        self.assertEqual(report['stop_reason'], 'xp1_loaded_close_unverified')
        self.assertEqual(report['error'], "ValueError('XP1 close markers are missing, repeated or out of order')")
        # Undo only this known parent-review annotation in memory. All child
        # supervision, source flags and native receipts remain the retained data.
        report.update(error=None, stop_reason=None)
        pins = dict(self.closure['pins'])
        pins[str(RUN/'closure.json')] = PINS['closure.json']
        return report, pins

    def fixture(self, run):
        report, pins = self.original()
        (run/'closure.json').write_bytes(self.closure_raw)
        pins[str(run/'closure.json')] = pins.pop(str(RUN/'closure.json'))
        report['source_unchanged'] = {key: True for key in pins}
        result, events = deepcopy(self.original_result), deepcopy(self.events)
        self.write_fixture(run, result, events)
        return report, pins, result, events

    def write_fixture(self, run, result, events):
        target = run/'loaded-lifetime-result.json'
        target.write_text(json.dumps(result), encoding='utf-8')
        for event in events:
            if event['stage'] == 'xp2_loaded_lifetime_closed':
                event.clear(); event.update(stage='xp2_loaded_lifetime_closed', **deepcopy(result))
            if event['stage'] == 'xp1_saved_loaded_close_returned':
                event['receipt'] = dict(path=str(target), bytes=target.stat().st_size, sha256=digest(target))
        self.write_events(run, events)

    def write_events(self, run, events):
        (run/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events), encoding='utf-8')

    def test_retained_xp2_close_authenticates_end_to_end_without_rewriting_attempt(self):
        report, pins = self.original()
        result = xp1_loaded_close_evidence(RUN, report, pins, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(result['schema'], 'civ6-host.xp2-loaded-close-evidence.v1')
        self.assertEqual(result['transcript_sha256'], PINS['events.jsonl'])
        self.assertEqual(result['receipt']['sha256'], PINS['loaded-lifetime-result.json'])
        self.assertEqual(len(result['ordered_marker_lines']), 9)
        self.assertTrue(result['native_unload_and_destroy_returned'])
        self.assertFalse(result['native_calls_during_verification'])
        self.assertFalse(result['full_job_ledger_requalified'])
        self.assertFalse(report['normal_destroy_called'])
        self.assertEqual({name: digest(RUN/name) for name in PINS}, PINS)

    def test_original_refusal_is_not_overridden_or_relabelled_as_xp1(self):
        report, pins = self.original()
        with self.assertRaisesRegex(ValueError, 'clean bounded supervision'):
            xp1_loaded_close_evidence(RUN, self.original_report, pins, core_sha256=XP2_CORE_SHA256)
        with self.assertRaisesRegex(ValueError, 'source/capture identity'):
            xp1_loaded_close_evidence(RUN, report, pins)
        with self.assertRaises(ValueError):
            xp1_loaded_close_evidence(RUN, report, pins, core_sha256='unknown')

    def test_every_engine_marker_rejects_missing_duplicate_wrong_order_or_foreign_engine(self):
        for index in range(1, 6):
            for change in ('missing', 'duplicate', 'reorder', 'foreign', 'extra_foreign'):
                with self.subTest(index=index, change=change), tempfile.TemporaryDirectory() as folder:
                    run = Path(folder).resolve()
                    report, pins, _, events = self.fixture(run)
                    if change == 'missing':
                        events.pop(index)
                    elif change == 'duplicate':
                        events.insert(index, deepcopy(events[index]))
                    elif change == 'reorder':
                        events[index], events[index+1] = events[index+1], events[index]
                    elif change == 'foreign':
                        events[index]['stage'] = events[index]['stage'].replace('xp2', 'xp1')
                    else:
                        foreign = deepcopy(events[index])
                        foreign['stage'] = foreign['stage'].replace('xp2', 'xp1')
                        events.insert(index, foreign)
                    self.write_events(run, events)
                    with self.assertRaises(ValueError):
                        xp1_loaded_close_evidence(run, report, pins, core_sha256=XP2_CORE_SHA256)

    def test_xp2_source_unload_receipt_command_owner_jobs_and_boundary_stay_strict(self):
        for change in ('marker_source', 'unload_rva', 'receipt_hash', 'receipt_value',
                       'steps', 'command_owner', 'command_source', 'jobs_engine', 'nonce', 'after_stop'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                run = Path(folder).resolve()
                report, pins, result, events = self.fixture(run)
                if change == 'marker_source': events[1]['source_sha256'] = '0'*64
                elif change == 'unload_rva': events[1]['target_rva'] = '0x4be690'
                elif change == 'receipt_hash': events[6]['receipt']['sha256'] = '0'*64
                elif change == 'receipt_value': events[5]['native_destroy_called'] = False
                elif change == 'nonce': events[7]['nonce'] = '0'*32
                elif change == 'after_stop': events.append(dict(stage='unexpected_tail'))
                else:
                    if change == 'steps': result['steps'][1:3] = result['steps'][1:3][::-1]
                    elif change == 'command_owner': result['continuation_closed'] = False
                    elif change == 'command_source': result['command_source_sha256'] = '0'*64
                    else: result['jobs_before']['core_identity']['sha256'] = XP1_CORE_SHA256
                    self.write_fixture(run, result, events)
                self.write_events(run, events)
                with self.assertRaises(ValueError):
                    xp1_loaded_close_evidence(run, report, pins, core_sha256=XP2_CORE_SHA256)

    def test_parent_finish_uses_selected_xp2_review_and_error_name(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as folder:
                run = Path(folder).resolve()
                report, pins, _, _ = self.fixture(run)
                if corrupt:
                    (run/'loaded-lifetime-result.json').write_bytes(b'changed')
                session = object.__new__(NativeNetworkSession)
                session.input_profile, session.finished, session.run, session.pins = 'xp2-lan', False, run, pins
                def finish_base(s):
                    s.report = deepcopy(report); s.finished = True
                with patch.object(NativeActionSession, '_finish', finish_base), patch(
                        'civ6_host.runtime.native.native_saved_session.write_json') as write:
                    session._finish()
                write.assert_called_once_with(run/'supervisor.json', session.report)
                self.assertEqual(session.report['normal_destroy_called'], not corrupt)
                if corrupt:
                    self.assertEqual(session.report['stop_reason'], 'xp2_loaded_close_unverified')
                else:
                    self.assertEqual(session.report['native_lifetime']['schema'],
                                     'civ6-host.xp2-loaded-close-evidence.v1')


if __name__ == '__main__':
    unittest.main()

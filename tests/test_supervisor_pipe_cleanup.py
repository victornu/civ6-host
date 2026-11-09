from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import time
import unittest

from civ6_host.runtime.supervisor_cleanup import close_reaped_process_pipes
from civ6_host.runtime.native.native_saved_session import NativeSavedSession


class FailedFlush:
    closed = False
    def close(self):
        self.closed = True
        raise OSError(22, 'Invalid argument')


class PipeCleanupTests(unittest.TestCase):
    def owner(self, error):
        s = object.__new__(NativeSavedSession)
        s.finished=False; s.done=Mock(); s.threads=[]; s.job=7
        s.win=NS(kernel=NS(CloseHandle=Mock()))
        s.process=NS(pid=123,poll=Mock(return_value=89),wait=Mock(),returncode=89,
                     stdin=FailedFlush(),stdout=Mock(),stderr=Mock())
        s.command_log=Mock();s.pins={};s.run=Path('fixture-run');s.started=time.perf_counter()
        s.error=error;s.stop_reason='command_failed' if error else None
        s.lifetime_seconds=900;s.stdout_limit_bytes=67108864;s.close_context=None
        s.samples=0;s.peak={};s.stdout_native_records=0;s.protocol=None
        s.reset_timings_seconds={};s.reset_resource_samples=[]
        return s

    def test_dead_child_flush_error_preserves_primary_failure_and_containment(self):
        s=self.owner('worker source refusal')
        with patch('civ6_host.runtime.native.native_saved_session.write_json') as write:
            s._finish();s._finish()
            write.assert_called_once()
        self.assertTrue(s.finished)
        self.assertTrue(s.report['job_assigned'])
        self.assertEqual(s.report['error'],'worker source refusal')
        self.assertEqual(s.report['pipe_cleanup_errors'][0]['pipe'],'stdin')
        self.assertTrue(s.report['pipe_cleanup_errors'][0]['closed'])
        s.process.stdout.close.assert_called_once();s.process.stderr.close.assert_called_once()
        s.win.kernel.CloseHandle.assert_called_once_with(7)

    def test_cleanup_error_never_turns_into_a_clean_close(self):
        s=self.owner(None)
        with patch('civ6_host.runtime.native.native_saved_session.write_json'):
            s._finish()
        self.assertEqual(s.report['stop_reason'],'pipe_cleanup_failed')
        self.assertIn('Native pipe cleanup failed',s.report['error'])
        self.assertFalse(s.report['normal_destroy_called'])

    def test_live_child_is_not_treated_as_reaped(self):
        process=NS(poll=lambda:None,stdin=Mock())
        with self.assertRaisesRegex(RuntimeError,'running native child'):
            close_reaped_process_pipes(process)
        process.stdin.close.assert_not_called()


if __name__=='__main__':unittest.main()

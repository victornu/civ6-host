"""One bounded Windows process-control check; no game or learner."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))


@unittest.skipUnless(os.name == 'nt', 'Windows Job Object integration')
class ProcessControlIntegration(unittest.TestCase):
    def test_assign_measure_terminate_and_reap(self):
        from civ6_host.runtime import WindowsProcessRuntime
        runtime = WindowsProcessRuntime()
        job = None
        process = subprocess.Popen([sys.executable,'-I','-c',
            'import sys; sys.stdin.buffer.read(1)'], stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job = runtime.job(process,128*1024*1024)
            self.assertGreater(runtime.available()['physical_total_bytes'],0)
            self.assertGreaterEqual(runtime.memory(int(process._handle))['private_bytes'],0)
            runtime.terminate_job(job,137)
            self.assertEqual(process.wait(timeout=5),137)
        finally:
            if job is not None:runtime.close_job(job)
            if process.poll() is None:process.kill()
            process.wait(timeout=5)
            process.stdin.close()


if __name__ == '__main__':
    unittest.main()

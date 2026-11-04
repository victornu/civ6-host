"""Multiple explicit commands stay on one authenticated transcript."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from qualify_xp1_configuration import saved_load_events


class Intervals(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'events.jsonl'
        self.rows=[dict(stage='xp1_saved_player_view_returned')]
        for seq in (1,3):
            self.rows.extend([dict(stage='before_xp1_saved_unit_commands',protocol_sequence=seq),
                dict(stage='native_command_archive_queued',archive_hex='aa'),
                dict(stage='xp1_saved_unit_commands_returned',protocol_sequence=seq)])

    def write(self,rows):
        raw=b''.join(json.dumps(row).encode()+b'\n' for row in rows)
        self.path.write_bytes(raw);return hashlib.sha256(raw).hexdigest()

    def test_selected_commands_share_full_transcript_and_distinct_exact_intervals(self):
        sha=self.write(self.rows)
        results=[]
        for seq in (1,3):
            count,events=saved_load_events(self.path,require_interval='unit_commands',command_sequence=seq)
            interval=events['unit_commands_job_interval']
            self.assertEqual(count,7);self.assertEqual(interval['stdout_sha256'],sha)
            self.assertEqual(events['xp1_saved_unit_commands_returned']['protocol_sequence'],seq)
            self.assertEqual(len(events['_command_intervals']),2)
            results.append(interval)
        self.assertLess(results[0]['returned']['line'],results[1]['begin']['line'])
        self.assertNotEqual(results[0]['interval_sha256'],results[1]['interval_sha256'])
        with self.assertRaises(ValueError):saved_load_events(self.path,require_interval='unit_commands')
        with self.assertRaises(ValueError):saved_load_events(self.path,require_interval='unit_commands',allow_multiple_commands=True)

    def test_missing_foreign_overlap_duplicate_and_incomplete_markers_refuse(self):
        mutations=[lambda r:r[3].update(protocol_sequence=2),
                   lambda r:r[4].pop('protocol_sequence'),
                   lambda r:r[4].update(protocol_sequence=1),
                   lambda r:r.insert(3,deepcopy(r[4])),
                   lambda r:r.pop()]
        for mutate in mutations:
            rows=deepcopy(self.rows);mutate(rows);self.write(rows)
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                saved_load_events(self.path,require_interval='unit_commands',command_sequence=1)


if __name__=='__main__':unittest.main()

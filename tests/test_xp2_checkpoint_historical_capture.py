"""Static historical XP2 checkpoint checks; no engine or native calls."""

import unittest
from unittest.mock import patch

from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime import xp2_bbg_inputs as bbg


class HistoricalXP2CaptureTests(unittest.TestCase):
    def test_source_only_capture_reads_retained_streams_and_database_identities(self):
        original = checkpoint._read_original_xp2_capture(
            bbg.prepared_reference(), bbg.REFERENCE)

        self.assertEqual(original.reference, bbg.REFERENCE)
        self.assertEqual(set(original.fixture['databases']), set(bbg.DATABASE_PINS))
        self.assertTrue(original.inputs.configuration)
        self.assertTrue(original.inputs.game)
        self.assertTrue(original.inputs.map_values)
        for role, pin in bbg.DATABASE_PINS.items():
            row = original.fixture['databases'][role]
            self.assertEqual(row['sha256'], pin['sha256'])
            self.assertEqual(row['size_bytes'], pin['size_bytes'])

    def test_source_only_capture_rejects_noncanonical_handoff(self):
        prepared = bbg.prepared_reference()
        prepared['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'exact recovered input handoff'):
            checkpoint._read_original_xp2_capture(prepared, bbg.REFERENCE)

    def test_configure_closure_forwards_selected_execution_image(self):
        image = object()
        closure = {'official_bundle': bbg.REFERENCE, 'pins': {}}
        result = {'observed_game_turn': 50}
        with patch.object(checkpoint, '_validate_lineage', return_value=result) as validate:
            checkpoint.configure_closure(closure, ('work/checkpoint.json', 'a' * 64),
                                         execution_image=image)

        self.assertIs(validate.call_args.kwargs['execution_image'], image)
        self.assertEqual(closure['initial_turn'], 50)
        self.assertEqual(closure['network_checkpoint'],
                         {'path': 'work/checkpoint.json', 'sha256': 'a' * 64})


if __name__ == '__main__':
    unittest.main()

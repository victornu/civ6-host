from pathlib import Path
import unittest

from extraction_foundation_facades import transform as transform_facades
from extraction_foundation_queries import transform as transform_queries
from extraction_civilization_getter import transform as transform_civilization


ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'civ6-rl-lab'


class FoundationFacadeExtractionTests(unittest.TestCase):
    def test_fa5_shared_query_and_civilization_reader_select_xp2_explicitly(self):
        source = (LAB / 'civ6rl' / 'native_event_fa5b1159.py').read_text(encoding='utf-8')
        original = source
        result = transform_facades('civ6rl.native_event_fa5b1159', source)
        result = transform_queries('civ6rl.native_event_fa5b1159', result)
        result = transform_civilization('civ6rl.native_event_fa5b1159', result)
        self.assertIn("query_abi(core_sha256, resource_root())", result)
        self.assertIn("_foundation_abi.slot('plot_owner')", result)
        self.assertIn("_foundation_abi.slot('outer_map')", result)
        self.assertIn('PAIR_SECONDARY_VTABLE = _foundation_abi.service_secondary_vtable', result)
        self.assertIn("'324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'", result)
        self.assertIn('read_civilization_result(application, player_index, expected_hash=expected_hash, core_sha256=core_sha256)', result)
        self.assertIn('XP1 civilization query requires its bound application configuration', result)
        self.assertEqual(source, original)

    def test_unselected_module_is_byte_unchanged(self):
        source = 'def other():\n    return 1\n'
        self.assertEqual(transform_facades('civ6rl.other', source), source)


if __name__ == '__main__':
    unittest.main()

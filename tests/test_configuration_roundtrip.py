"""Exact representation relation on retained native bytes, without DLL runs."""
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime.configuration_roundtrip import compare_provider_roundtrip
from civ6_host.runtime.saved_load_profiles import BASE_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import xp2_normalization_source as source
from civ6_host.runtime.configuration_profiles import _copy


def provider(flags=0x20000000, *, size=1):
    return struct.pack('<IIHHIII', 1, 7, 5, 0, flags, size, 0)


class ConfigurationRoundtrip(unittest.TestCase):
    def test_xp2_contract_and_incomplete_leaf_refuse_before_comparison(self):
        original = source.verify_source()
        for mutation in ('foreign_engine', 'broadened_shape', 'missing_iterator_branch',
                         'changed_reader_bytes'):
            proof = _copy(original)
            if mutation == 'foreign_engine':
                proof['image']['sha256'] = BASE_CORE_SHA256
            elif mutation == 'broadened_shape':
                proof['contract']['input_exact']['size'] = 0
            elif mutation == 'missing_iterator_branch':
                proof['bodies']['provider_next_node_helper']['length'] = 36
            else:
                proof['bodies']['variant_value_reader']['fragments'][0]['raw_hex'] = '00'
            with self.subTest(mutation=mutation), patch.object(source, '_source', return_value=proof):
                with self.assertRaises(ValueError):
                    compare_provider_roundtrip(provider(), provider(0), core_sha256=XP2_CORE_SHA256)

    def test_engine_selected_relation_preserves_raw_inequality(self):
        before, after = provider(), provider(0)
        for engine in (BASE_CORE_SHA256, XP2_CORE_SHA256):
            with self.subTest(engine=engine):
                report = compare_provider_roundtrip(before, after, core_sha256=engine)
                self.assertEqual(report['core_sha256'], engine)
                self.assertEqual(report['changed_offsets'], [15])
                self.assertEqual(report['known_normalization_count'], 1)
                self.assertFalse(report['exact_bytes_equal'])
                self.assertTrue(report['engine_source_qualified'])
                self.assertFalse(report['full_game_restored'])
        self.assertEqual(before, provider())

    def test_unproved_differences_and_unqualified_engine_refuse(self):
        scalar = struct.pack('<IIHHIII', 1, 7, 2, 0, 0, 0, 9)
        cases = [(provider(0), provider()), (provider(size=0), provider(0, size=0)),
                 (provider(), provider(0) + b'\0'),
                 (scalar, scalar[:-1] + b'\1')]
        for before, after in cases:
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                compare_provider_roundtrip(before, after, core_sha256=XP2_CORE_SHA256)
        with self.assertRaises(ValueError):
            compare_provider_roundtrip(provider(), provider(), core_sha256='unknown')

    def test_retained_xp2_native_streams(self):
        host = Path(__file__).resolve().parents[1]
        before = (host/'work/xp2-bundle-inputs/configuration.bin').read_bytes()
        after = (resource_root()/'work/native-xp2-configuration/'
                 'run-20261102T092527Z-1fca62ada8ba/configuration-output.bin').read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(),
                         'e9f5cf20b75932169b5b1c8bdd800ce349a0cea99c755cc1ab1d099c64eaf116')
        self.assertEqual(hashlib.sha256(after).hexdigest(),
                         '3075d816739ee63a86362e3fb46796394dd405d30f44b928baf4c9f1393958ef')
        report = compare_provider_roundtrip(before, after, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(report['changed_offsets'], [19205, 19360])
        self.assertEqual(report['values_compared'], 984)
        self.assertTrue(report['other_bytes_equal'])
        self.assertNotEqual(report['normalization_proof_sha256'],
                            report['comparison_algorithm_proof_sha256'])
        self.assertFalse(report['saved_game_loaded'])


if __name__ == '__main__':
    unittest.main()

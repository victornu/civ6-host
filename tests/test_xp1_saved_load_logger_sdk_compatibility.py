"""Static SDK-host compatibility checks; no DLL or GameCore is loaded."""
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_saved_load_logger as logger
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path


class SavedLoadLoggerSdkCompatibilityTests(unittest.TestCase):
    def test_sdk_transition_pins_exact_archive_and_unchanged_logger_class(self):
        proof = logger._checked_host_sdk_compatibility()
        self.assertEqual(proof['schema'], 'civ6-host.logger-sdk-host-compatibility.v1')
        self.assertEqual(proof['prior_host_sha256'],
                         '5ad8100cd6f06497f967a451855a3369aded4cf307a058a161094c154d7d99b7')
        self.assertEqual(proof['current_host_sha256'],
                         '04f7314f8518a5ffeca0e143184d19f7a542a62f0475250e63cdc086932b10bd')
        self.assertTrue(proof['diagnostic_host']['byte_identical'])
        self.assertEqual(tuple(proof['changed_top_level_exact']),
                         ('finish_database', 'initialize_context'))

    def test_source_dependencies_pin_supplement_and_immutable_archive(self):
        pins = logger.source_dependencies()
        root = resource_root()
        proof = logger._checked_host_sdk_compatibility()
        for row in (
            dict(path=logger.HOST_SDK_COMPATIBILITY[0],
                 sha256=logger.HOST_SDK_COMPATIBILITY[1]),
            proof['archive_native_host'],
            proof['archive_manifest'],
        ):
            path = resolve_path(root / row['path']).resolve(strict=True)
            self.assertEqual(pins[str(path)], row['sha256'])

    def test_stale_sdk_supplement_is_rejected(self):
        original = logger._source

        def stale(pair):
            proof = original(pair)
            if pair == logger.HOST_SDK_COMPATIBILITY:
                return dict(proof, current_host_sha256='0' * 64)
            return proof

        with patch.object(logger, '_source', side_effect=stale):
            with self.assertRaisesRegex(ValueError, 'compatibility chain changed'):
                logger._checked_host_sdk_compatibility()

    def test_sdk_source_dependency_digest_is_exact(self):
        proof_path = resolve_path(resource_root() / logger.HOST_SDK_COMPATIBILITY[0])
        self.assertEqual(hashlib.sha256(Path(proof_path).read_bytes()).hexdigest(),
                         logger.HOST_SDK_COMPATIBILITY[1])


if __name__ == '__main__':
    unittest.main()

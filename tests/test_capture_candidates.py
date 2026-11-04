"""Private XP1/XP2 package routing; no GameCore process or raw bundle replay."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import capture_candidates as candidates
from civ6_host.runtime import capture_admission, capture_package
from civ6_host.runtime import capture_profiles, xp1_saved_load, xp2_bundle_inputs as xp2
from civ6_host.runtime.saved_load_profiles import (
    XP2_CORE_SHA256, profile_for_sha, require_saved_load_admission,
)
from civ6_host.runtime.native import native_official_bundle as original
from civ6_host.runtime.native.native_official_load import OfficialInputs


HOST = Path(__file__).resolve().parents[1]
LAB = resource_root()
XP1_PREPARED_REFERENCE = {
    'path': str(LAB / 'work/host-prepared-captures/xp1-lan-20261030/manifest.json'),
    'sha256': 'be65f4900a0e32edcee471ebfc0f697d299a86a839c5798c3d1a324a031c0665',
}


class CaptureCandidateTests(unittest.TestCase):
    def test_private_candidate_selection_is_explicit_and_family_scoped(self):
        self.assertIsNone(candidates.select_private_candidate())
        self.assertIsNone(candidates.select_private_candidate(xp1_candidate=False))

        xp1_legacy = candidates.select_private_candidate(xp1_candidate=True)
        xp1_explicit = candidates.select_private_candidate(candidate_profile='xp1-lan')
        xp2_explicit = candidates.select_private_candidate(candidate_profile='xp2-lan')
        self.assertEqual(xp1_legacy.family, 'xp1-lan')
        self.assertEqual(xp1_legacy.reference, xp1_saved_load.REFERENCE)
        self.assertIs(xp1_legacy.profile, xp1_explicit.profile)
        self.assertIs(xp2_explicit.profile, xp2.XP2_LAN_PROFILE)
        self.assertEqual(xp2_explicit.reference, xp2.REFERENCE)
        self.assertEqual(xp2_explicit.core_sha256, XP2_CORE_SHA256)

        for kwargs in (
            {'xp1_candidate': True, 'candidate_profile': 'xp2-lan'},
            {'xp1_candidate': True, 'candidate_profile': 'xp1-lan'},
            {'xp1_candidate': 1},
            {'xp1_candidate': None},
            {'candidate_profile': 'XP2-LAN'},
            {'candidate_profile': 2},
            {'candidate_profile': b'xp2-lan'},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                candidates.select_private_candidate(**kwargs)

    def test_explicit_xp2_candidate_does_not_extend_public_capture_or_load_profiles(self):
        selected = candidates.select_private_candidate(candidate_profile='xp2-lan')
        self.assertEqual(selected.family, 'xp2-lan')
        self.assertNotIn('xp2-lan', capture_profiles.CAPTURE_MODES)
        with self.assertRaises(ValueError):
            capture_profiles.profile_for_capture('xp2-lan')
        with self.assertRaises(ValueError):
            require_saved_load_admission(profile_for_sha(XP2_CORE_SHA256))

    def test_xp2_configuration_and_game_pair_match_retained_extracted_bytes(self):
        capture = json.loads((LAB / xp2.REFERENCE[0]).read_text(encoding='utf-8'))
        extraction_ref = capture['save']['extraction907']['manifest']
        extraction_path = LAB / Path(extraction_ref)
        extraction = json.loads(extraction_path.read_text(encoding='utf-8'))
        game_rows = [row for row in extraction['sections']
                     if row.get('kind') == 'gamecore_stream_candidate']
        self.assertEqual(len(game_rows), 1)
        configuration = (HOST / 'work/xp2-bundle-inputs/configuration.bin').read_bytes()
        game = (extraction_path.parent / game_rows[0]['extracted_file']).read_bytes()

        self.assertIsNone(xp2.validate_components(configuration, game))
        self.assertEqual(hashlib.sha256(configuration).hexdigest(), xp2.CONFIGURATION_SHA256)
        self.assertEqual(hashlib.sha256(game).hexdigest(), xp2.GAME_SHA256)
        with self.assertRaises(ValueError):
            xp2.validate_components(configuration + b'x', game)
        with self.assertRaises(ValueError):
            xp2.validate_components(configuration, game + b'x')

    def _wrong_origin_registered_bundle(self):
        wrong_reference = ('work/official-capture/not-xp2/manifest.json', '0' * 64)
        inputs = OfficialInputs(
            b'configuration placeholder', b'GameCore placeholder', (),
            xp2.XP2_LAN_PROFILE, official_bundle=wrong_reference,
        )
        bundle = original.PreparedBundle(
            reference=wrong_reference, inputs=inputs, initial_turn=1,
            engine_path=Path(__file__).resolve(), fixture={}, dependencies={},
            expected_readback={}, content_profile={},
        )
        validators = {name: 'a' * 64 for name in original._PREPARED_BUNDLE_VALIDATOR_PATHS}
        input_pins = {'xp2-test-validator': 'b' * 64}
        with patch.object(original, '_prepared_bundle_validator_digests', return_value=validators), \
                patch.object(xp2, 'reader_validator_digests', return_value=input_pins):
            original._remember_prepared_bundle(
                bundle, 'xp2-lan', validators, _token=original._PARENT_ADMISSION_TOKEN,
                _input_only=True,
            )
        self.addCleanup(original._PREPARED_BUNDLE_ADMISSIONS.pop, bundle, None)
        return bundle, validators, input_pins

    def test_prepare_handoff_refuses_unadmitted_or_wrong_origin_bundle_before_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, bundle in enumerate((object(), self._wrong_origin_registered_bundle()[0])):
                destination = Path(temporary) / ('case-' + str(index))
                with self.subTest(bundle_type=type(bundle).__name__), \
                        patch.object(capture_admission, 'configured_reference', return_value=None), \
                        patch.object(capture_admission, 'validation_identity', return_value={'runtime': 'pinned'}), \
                        patch.object(original, 'read_bundle') as raw_reader, \
                        patch.object(capture_package, 'export_capture') as exporter:
                    try:
                        if bundle is not None and type(bundle) is original.PreparedBundle:
                            validators = {name: 'a' * 64 for name in original._PREPARED_BUNDLE_VALIDATOR_PATHS}
                            input_pins = {'xp2-test-validator': 'b' * 64}
                            with patch.object(original, '_prepared_bundle_validator_digests', return_value=validators), \
                                    patch.object(xp2, 'reader_validator_digests', return_value=input_pins):
                                with self.assertRaises(ValueError):
                                    candidates.prepare_input_handoff('xp2-lan', destination, bundle=bundle)
                        else:
                            with self.assertRaises(ValueError):
                                candidates.prepare_input_handoff('xp2-lan', destination, bundle=bundle)
                    finally:
                        raw_reader.assert_not_called()
                        exporter.assert_not_called()
                        self.assertFalse(destination.exists())

    def test_consume_wrong_family_package_stops_before_bundle_reader(self):
        self.assertTrue(Path(XP1_PREPARED_REFERENCE['path']).is_file())
        with patch.object(capture_admission, 'configured_reference', return_value=XP1_PREPARED_REFERENCE), \
                patch.object(capture_admission, 'configure') as configure, \
                patch.object(original, 'read_bundle') as raw_reader, \
                patch.object(capture_package, 'export_capture') as exporter:
            with self.assertRaises(capture_package.CapturePackageError):
                candidates.consume_input_handoff('xp2-lan', XP1_PREPARED_REFERENCE)
        configure.assert_called_once_with(XP1_PREPARED_REFERENCE)
        raw_reader.assert_not_called()
        exporter.assert_not_called()


if __name__ == '__main__':
    unittest.main()

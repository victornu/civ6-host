"""Bounded admission tests for the one retained prepared XP1 package."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from civ6_host.runtime import capture_admission as admission
from civ6_host.runtime import xp1_prepared_reader_transition as transition
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp1_bundle_inputs import reader_validator_digests


class XP1PreparedReaderTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = Path(__file__).resolve().parents[1]
        cls.package_path = resource_root() / 'work/host-prepared-captures/xp1-lan-20261030/manifest.json'
        cls.manifest = json.loads(cls.package_path.read_bytes())
        cls.reference = dict(path=str(cls.package_path.resolve()),
                             sha256='be65f4900a0e32edcee471ebfc0f697d299a86a839c5798c3d1a324a031c0665')
        cls.producer = cls.manifest['validation_identity']
        cls.consumer = admission.validation_identity()
        cls.provenance = admission.admit_producer(cls.producer, cls.consumer)

    def _validators(self):
        package = Path(admission.__file__).resolve().parents[1]
        validators = {Path(p).resolve().relative_to(package).as_posix(): digest
                      for p, digest in reader_validator_digests().items()}
        validators.update({
            key: admission._sha((package / key).read_bytes())
            for key in (
                'runtime/capture_package.py', 'runtime/native/official_save.py',
                'runtime/native/official_configuration.py',
                'runtime/native/database_capture_bundle993.py',
                'runtime/native/native_gameplay_source_capture.py',
                'runtime/native/native_localization_logical_export.py',
                'runtime/native/native_localization.py', 'runtime/native/native_source_cache.py',
                'runtime/native/native_checkpoint_provider.py',
                'runtime/native/native_game_configuration.py')})
        return validators

    def test_exact_retained_package_uses_six_source_migration_and_current_consumer_identity(self):
        rows = admission._check_xp1_prepared_reader(
            self.producer, self.consumer, self.provenance, self.manifest, self.reference)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['transition'], 'xp1_retained_prepared_package_legacy_reader_v1')
        self.assertEqual(row['producer_identity_sha256'], '5317ec0a1c1b4054173d58cb10e95b3437d427e6dfd2eded8092425a6937e01a')
        self.assertEqual(row['package'], self.reference)
        self.assertEqual(row['reviewed_source_pairs'], 6)
        self.assertEqual(row['components_byte_equal'], 6)
        self.assertEqual(row['selected_script_paths'], 0)
        self.assertFalse(row['full_raw_reader_replayed'])
        self.assertFalse(row['native_session_admitted'])
        self.assertFalse(row['producer_identity_substituted'])
        self.assertEqual(row['consumer_identity_sha256'], admission._sha(
            __import__('json').dumps(self.consumer, sort_keys=True, separators=(',', ':')).encode()))
        # Preserve the historical four-argument private tuple call: for the
        # exact retained producer it resolves to this same pinned package.
        legacy_call = admission._check_xp1_prepared_reader(
            self.producer, self.consumer, self.provenance, self.manifest)
        self.assertEqual(legacy_call, rows)

    def test_actual_package_reader_and_closure_admission_retain_all_package_checks(self):
        closure = {
            'prepared_capture': self.reference,
            'pins': {self.reference['path']: self.reference['sha256']},
            'official_bundle': copy.deepcopy(self.manifest['origin']),
            'input_profile': 'xp1-lan',
        }
        with patch.object(admission, 'configured_reference', return_value=self.reference):
            receipt = admission.consume_prepared_closure(
                closure, environment={}, _xp1_candidate=True)
        self.assertEqual(receipt['package'], self.reference)
        self.assertEqual(len(receipt['input_parser_transitions']), 1)
        self.assertFalse(receipt['input_parser_transitions'][0]['native_session_admitted'])

    def test_unrelated_validator_source_change_is_not_in_migration(self):
        producer = copy.deepcopy(self.producer)
        key = 'runtime/native/official_save.py'
        producer['runtime_sources'][key] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'producer identity changed'):
            admission._check_xp1_prepared_reader(
                producer, self.consumer, self.provenance, self.manifest, self.reference)

    def test_changed_parser_pair_is_not_generalized(self):
        consumer = copy.deepcopy(self.consumer)
        key = 'runtime/native/native_localization_logical_export.py'
        consumer['runtime_sources'][key] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'current input validator changed'):
            admission._check_xp1_prepared_reader(
                self.producer, consumer, self.provenance, self.manifest, self.reference)

    def test_package_profile_origin_and_reference_mutations_refuse(self):
        for field, value in (
            ('input_profile', 'xp2-lan'),
            ('origin', {'path': 'work/official-capture/other/manifest.json', 'sha256': 'c' * 64}),
        ):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                admission._check_xp1_prepared_reader(
                    self.producer, self.consumer, self.provenance, manifest, self.reference)
        for reference in (
            dict(self.reference, sha256='d' * 64),
            dict(self.reference, path=str(self.package_path.with_name('other.json'))),
        ):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                admission._check_xp1_prepared_reader(
                    self.producer, self.consumer, self.provenance, self.manifest, reference)

    def test_current_reader_validator_scope_is_exact_and_unmodified_outside_six_pairs(self):
        validators = self._validators()
        self.assertEqual(len(validators), 17)
        pairs = {key for key in validators
                 if self.producer['runtime_sources'].get(key) != self.consumer['runtime_sources'].get(key)}
        self.assertEqual(pairs, {
            'runtime/native/native_official_bundle.py', 'runtime/capture_package.py',
            'runtime/native/database_capture_bundle993.py',
            'runtime/native/native_gameplay_source_capture.py',
            'runtime/native/native_localization_logical_export.py',
            'runtime/workers/capture_phase1_bundle994.py'})

    def test_bulk_format_and_nonempty_script_claims_refuse(self):
        review = self.host / 'work/xp2-ui-integration/reader-review'
        components = transition._read_pinned_json(
            review / 'xp1-input-components-revalidation-v1.json', transition.COMPONENT_REPORT_SHA256)
        branches = transition._read_pinned_json(
            review / 'xp1-selected-branch-equivalence-v1.json', transition.BRANCH_REPORT_SHA256)
        changes = (
            lambda row: row['retained_code_evidence']['current_manifest_gates']['localization_exports'].__setitem__('schema', 'civ6rl.database_bulk_capture.v1'),
            lambda row: row['retained_code_evidence']['current_manifest_gates'].__setitem__('selected_gameplay_paths', ['WorldCongress.lua']),
            lambda row: row['retained_code_evidence']['current_manifest_gates'].__setitem__('selected_script_records', 1),
        )
        for change in changes:
            mutated = copy.deepcopy(branches)
            change(mutated)
            with self.subTest(change=change), patch.object(
                    transition, '_read_pinned_json', side_effect=[components, mutated]), \
                    self.assertRaisesRegex(ValueError, 'selected legacy branches'):
                transition._validate_evidence(self.host, self.manifest,
                    self.producer, self.consumer, self._validators())


if __name__ == '__main__':
    unittest.main()

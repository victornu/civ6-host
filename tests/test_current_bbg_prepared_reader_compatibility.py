"""Exact, read-only input-reader transition for current BBG World A."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest
import zipfile
from unittest.mock import patch

from civ6_host.runtime import capture_admission as admission
from civ6_host.runtime.paths import resource_root


ORIGIN = {
    'path': 'work/official-capture/bbg751-world-A-ui/manifest.json',
    'sha256': '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d',
}
PACKAGE_RELATIVE = 'work/host-prepared-captures/bbg751-world-A-current-icu/manifest.json'
PACKAGE_SHA256 = 'b4404de5ec63ac9a958ff1c9a84a6c3312eab160f9d1e7cb70454d01bea4d35c'
PRODUCER_SHA256 = '99cf8602fcd4725ae5fec5bd2731f82985c21d70d890294fa77c5cf3747fb31f'
SOURCE_EVIDENCE = 'work/official-capture/bbg751-world-A-headless-admission'
ARCHIVE_SHA256 = '5971579ea40819015ac7825b46c19cefb3e405e49ed5d51340b22d40caa467c6'
PINS_SHA256 = 'a41ad53c0971a714dd2fe4b01548207cefca574e2c3c9701f34f79a0570313bb'
QUALIFICATION_SHA256 = '95f2a08e7053124528424dfc5cf6b2d58247952bf94d49030739fe6836145913'


class CurrentBBGPreparedReaderCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = resource_root()
        cls.package_path = root / PACKAGE_RELATIVE
        raw = cls.package_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != PACKAGE_SHA256:
            raise AssertionError('retained current BBG prepared package changed')
        cls.manifest = json.loads(raw)
        cls.producer = cls.manifest['validation_identity']
        cls.consumer = admission.validation_identity()
        cls.reference = dict(path=str(cls.package_path.resolve()), sha256=PACKAGE_SHA256)

    def test_exact_producer_package_origin_and_current_reader_hashes_join(self):
        receipt = admission.admit_producer(self.producer, self.consumer)
        self.assertEqual(receipt['mode'], 'retained_qualified_producer')
        self.assertEqual(receipt['producer_identity_sha256'], PRODUCER_SHA256)
        self.assertEqual(receipt['origin_path'], ORIGIN['path'])
        self.assertEqual(receipt['origin_sha256'], ORIGIN['sha256'])
        self.assertEqual(receipt['package_sha256'], PACKAGE_SHA256)
        self.assertEqual(receipt['package_path'], PACKAGE_RELATIVE)
        self.assertEqual(receipt['qualification_evidence_sha256'], QUALIFICATION_SHA256)
        self.assertEqual(receipt['qualification_scope'],
                         'world-A single saved-load, offered-action, reset interval')

        transition = admission._check_current_bbg_prepared_reader(
            self.producer, self.consumer, self.manifest, self.reference)
        self.assertEqual(len(transition), 1)
        self.assertFalse(transition[0]['producer_identity_substituted'])
        self.assertFalse(transition[0]['native_session_admitted'])
        proof = transition[0]['reader_source_proof']
        self.assertEqual(proof['archive_sha256'], ARCHIVE_SHA256)
        self.assertEqual(proof['pins_sha256'], PINS_SHA256)
        self.assertEqual(proof['archived_input_module_count'], 17)
        self.assertEqual(set(proof['unchanged_reader_functions']), {
            '_reference', '_bootstrap', '_same_origin', '_pin_original', '_files',
            '_check_localization', '_verify_content_profile'})

    def test_unknown_input_reader_or_package_drift_is_refused(self):
        changed = copy.deepcopy(self.consumer)
        changed['runtime_sources']['runtime/capture_package.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'current input validator changed'):
            admission._check_current_bbg_prepared_reader(
                self.producer, changed, self.manifest, self.reference)

        with self.assertRaisesRegex(ValueError, 'package or origin differs'):
            admission._check_current_bbg_prepared_reader(
                self.producer, self.consumer, self.manifest,
                dict(self.reference, sha256='0' * 64))
        changed_manifest = dict(self.manifest, origin=dict(ORIGIN, sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'package or origin differs'):
            admission._check_current_bbg_prepared_reader(
                self.producer, self.consumer, changed_manifest, self.reference)

    def test_changed_reader_and_orchestration_bodies_are_refused(self):
        source = Path(admission.__file__).read_bytes()
        mutation = source.replace(b'if content != expected:',
                                  b'if content is not expected:', 1)
        self.assertNotEqual(mutation, source)
        changed = copy.deepcopy(self.consumer)
        changed['runtime_sources']['runtime/capture_admission.py'] = hashlib.sha256(mutation).hexdigest()
        with self.assertRaisesRegex(ValueError, '_verify_content_profile'):
            admission._check_current_bbg_reader_source(
                self.producer, changed, current_source=mutation)

        mutation = source.replace(b'return reference,manifest,folder,files,json.loads(raw)',
                                  b'return reference,manifest,folder,files,raw', 1)
        self.assertNotEqual(mutation, source)
        changed = copy.deepcopy(self.consumer)
        changed['runtime_sources']['runtime/capture_admission.py'] = hashlib.sha256(mutation).hexdigest()
        with self.assertRaisesRegex(ValueError, '_load'):
            admission._check_current_bbg_reader_source(
                self.producer, changed, current_source=mutation)

    def test_current_registered_load_reuses_package_reader_and_emits_parser_transition(self):
        from civ6_host.runtime import capture_package, capture_candidates, xp2_bbg_inputs
        candidate = type('Candidate', (), {'family': 'xp2-lan', 'reference': (
            ORIGIN['path'], ORIGIN['sha256'])})()
        with patch.object(admission, 'configured_reference', return_value=self.reference), \
             patch.object(capture_candidates, 'select_private_candidate', return_value=candidate), \
             patch.object(xp2_bbg_inputs, 'registered_reference', return_value=candidate.reference), \
             patch.object(admission, '_prepared_xp2_execution', return_value=True), \
             patch.object(admission, '_check_current_bbg_prepared_reader',
                          wraps=admission._check_current_bbg_prepared_reader) as reader_check, \
             patch.object(capture_package, 'read_package', return_value=(
                 self.manifest, self.package_path.parent, {})) as read_package, \
             patch('civ6_host.runtime.native.native_official_bundle.read_bundle',
                   side_effect=AssertionError('raw SQL capture is forbidden')):
            loaded = admission._load(_candidate_profile='xp2-lan', execution_image=object())
        self.assertEqual(loaded[0], self.reference)
        self.assertEqual(loaded[1]['origin'], ORIGIN)
        reader_check.assert_called_once()
        self.assertEqual(read_package.call_args.kwargs['execution_image'].__class__, object)

    def test_same_runtime_new_registered_package_skips_only_the_historical_a_transition(self):
        from types import SimpleNamespace
        from civ6_host.runtime import capture_package, capture_candidates, xp2_bbg_inputs

        consumer = admission.validation_identity()
        manifest = dict(origin=ORIGIN, validation_identity=consumer)
        package = dict(path=str(resource_root() / 'work/host-prepared-captures/world-B-fixture/manifest.json'),
                       sha256='d' * 64)
        candidate = SimpleNamespace(family='xp2-lan', reference=(ORIGIN['path'], ORIGIN['sha256']))
        with patch.object(admission, 'configured_reference', return_value=package), \
             patch.object(admission, 'validation_identity', return_value=consumer), \
             patch.object(capture_candidates, 'select_private_candidate', return_value=candidate), \
             patch.object(xp2_bbg_inputs, 'registered_reference', return_value=candidate.reference), \
             patch.object(admission, '_prepared_xp2_execution', return_value=True), \
             patch.object(capture_package, 'read_package', return_value=(
                 manifest, self.package_path.parent, {})) as read_package, \
             patch.object(admission, '_check_current_bbg_prepared_reader',
                          side_effect=AssertionError('historical World A transition must not run')), \
             patch.object(admission, '_check_xp2_prepared_reader',
                          side_effect=AssertionError('retained transition must not run')):
            loaded = admission._load(_candidate_profile='xp2-lan', execution_image=object())
        self.assertEqual(loaded[0], package)
        self.assertEqual(loaded[1]['validation_identity'], consumer)
        read_package.assert_called_once()

        foreign_path = resource_root() / 'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'
        foreign = json.loads(foreign_path.read_bytes())['validation_identity']
        with self.assertRaisesRegex(ValueError, 'no exact producer proof'):
            admission._check_current_bbg_prepared_reader(
                foreign, consumer, dict(origin=ORIGIN), self.reference)

    def test_reader_archive_and_pin_receipt_match_the_producer_and_live_sources(self):
        root = resource_root()
        evidence = root / SOURCE_EVIDENCE
        qualification = root / 'evidence/host-current-bbg751-world-a-headless.json'
        archive_path = evidence / 'installed-sources-icu.zip'
        pins_path = evidence / 'installed-source-pins-icu.json'
        self.assertEqual(hashlib.sha256(qualification.read_bytes()).hexdigest(),
                         QUALIFICATION_SHA256)
        archive_bytes = archive_path.read_bytes()
        pins_bytes = pins_path.read_bytes()
        self.assertEqual(hashlib.sha256(archive_bytes).hexdigest(), ARCHIVE_SHA256)
        self.assertEqual(hashlib.sha256(pins_bytes).hexdigest(), PINS_SHA256)
        pins = json.loads(pins_bytes)
        package_root = Path(admission.__file__).resolve().parents[1]
        module_names = admission._XP2_PREPARED_INPUT_MODULES
        with zipfile.ZipFile(archive_path) as archive:
            for name in module_names:
                with self.subTest(module=name):
                    member = 'src/civ6_host/' + name
                    raw = archive.read(member)
                    digest = hashlib.sha256(raw).hexdigest()
                    installed = package_root / name
                    self.assertEqual(pins[str(installed.resolve())], digest)
                    self.assertEqual(self.producer['runtime_sources'][name], digest)
                    self.assertEqual(self.consumer['runtime_sources'][name], digest)

            # capture_admission.py changed only in admission orchestration and
            # explicit proof data. The original origin/file readers are AST-identical.
            archived_admission = archive.read('src/civ6_host/runtime/capture_admission.py')
            archived_sha = hashlib.sha256(archived_admission).hexdigest()
            source_name = 'runtime/capture_admission.py'
            installed_admission = package_root / source_name
            self.assertEqual(pins[str(installed_admission.resolve())], archived_sha)
            self.assertEqual(self.producer['runtime_sources'][source_name], archived_sha)

        current_tree = ast.parse(Path(admission.__file__).read_text(encoding='utf-8'))
        archived_tree = ast.parse(archived_admission.decode('utf-8'))
        for function in admission._CURRENT_BBG_UNCHANGED_READER_FUNCTIONS:
            with self.subTest(function=function):
                current_node = next(n for n in current_tree.body
                                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                    and n.name == function)
                archived_node = next(n for n in archived_tree.body
                                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                     and n.name == function)
                self.assertEqual(ast.dump(current_node, include_attributes=False),
                                 ast.dump(archived_node, include_attributes=False))


if __name__ == '__main__':
    unittest.main()

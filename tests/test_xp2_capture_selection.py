"""Independent selection of retained official inputs without native execution."""
from hashlib import file_digest, sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import unittest

from civ6_host.runtime import xp2_capture_selection as selection
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp2_bundle_inputs import REFERENCE, retained_localization_sources


class XP2CaptureSelectionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = resource_root() / REFERENCE[0]
        if not self.manifest.is_file():
            self.skipTest('Retained private official capture required')
        self.raw = self.manifest.read_bytes()
        self.assertEqual(sha256(self.raw).hexdigest(), REFERENCE[1])

    def inspect_temporary_reference(self, raw, **kwargs):
        with NamedTemporaryFile(dir=self.manifest.parent, suffix='.json', delete=False) as stream:
            stream.write(raw)
            path = Path(stream.name)
        try:
            return selection.inspect_capture({'path': str(path), 'sha256': sha256(raw).hexdigest()}, **kwargs)
        finally:
            path.unlink()

    def test_nonhistorical_manifest_path_selects_the_same_exact_native_components(self):
        chosen = self.inspect_temporary_reference(self.raw)
        self.assertNotEqual(chosen['capture']['path'], REFERENCE[0])
        self.assertEqual(chosen['boundary']['mode'], 'LAN')
        self.assertEqual(chosen['boundary']['ruleset'], 'RULESET_EXPANSION_2')
        self.assertEqual(chosen['components']['configuration']['sha256'],
                         'e9f5cf20b75932169b5b1c8bdd800ce349a0cea99c755cc1ab1d099c64eaf116')
        self.assertEqual(chosen['components']['gamecore']['sha256'],
                         '66dd00e4e6f88e2ea2b87318a7b833ebeeed15f545ef050ccf6931f5c24cf3ee')
        self.assertFalse(chosen['native_session_admitted'])
        self.assertFalse(chosen['final_databases_and_scripts_validated'])

    def test_rehashed_manifest_cannot_mix_a_different_official_save(self):
        modified = json.loads(self.raw)
        modified['save']['source']['sha256'] = 'e6b504e4eb096e4933fa1314e6492d142c70fe3f75ef0024807e995e64f4aedc'
        with self.assertRaisesRegex(ValueError, 'different bytes'):
            self.inspect_temporary_reference(json.dumps(modified).encode())

    def test_refused_capture_is_not_selectable(self):
        path = self.manifest.parent.parent / 'xp2-gs-lan-rows-20261102-03/manifest.json'
        if not path.is_file():
            self.skipTest('Retained refused capture required')
        with self.assertRaisesRegex(ValueError, 'correlated capture994'):
            selection.inspect_capture({'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()})

    def test_different_bbg_save_and_stream_can_reuse_the_reference_map_seed(self):
        from tools.check_bbg_capture_selection import compare_saved_maps
        from civ6_host.runtime.xp2_bbg_inputs import CAPTURE, SAVE_SHA256

        captures = resource_root() / 'work/official-capture'
        early_digest = '7623d1bf90591bcf4664791b654e9e846e12c98d65eccf0f16e30def074cb8dd'
        early = captures / 'xp2-bbg751-lan-20261104-02/save' / early_digest / 'source.Civ6Save'
        reference = (resource_root() / CAPTURE / 'recovered-save-components'
                     / SAVE_SHA256 / 'source.Civ6Save')
        if not early.is_file() or not reference.is_file():
            self.skipTest('Retained BBG saves required')
        matched = compare_saved_maps(early, early_digest, reference, SAVE_SHA256)
        self.assertFalse(matched['map_seed_distinct'])
        self.assertTrue(matched['gamecore_stream_distinct'])
        self.assertEqual(matched['candidate']['map_seed'], 2095665172)
        self.assertFalse(matched['independent_official_generation_verified'])
        with self.assertRaisesRegex(ValueError, 'changed identity'):
            compare_saved_maps(early, SAVE_SHA256, reference, SAVE_SHA256)

        stock_digest = '48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430'
        stock = self.manifest.parent / 'save-capture' / stock_digest / 'source.Civ6Save'
        distinct = compare_saved_maps(stock, stock_digest, reference, SAVE_SHA256)
        self.assertTrue(distinct['map_seed_distinct'])
        self.assertTrue(distinct['gamecore_stream_distinct'])
        self.assertFalse(distinct['independent_official_generation_verified'])

    def test_same_map_rejected_before_database_capture_verification(self):
        from tools.check_bbg_capture_selection import inspect

        digest = '48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430'
        save = self.manifest.parent / 'save-capture' / digest / 'source.Civ6Save'
        with self.assertRaisesRegex(ValueError, 'reuses the reference map seed or GameCore stream'):
            inspect(self.manifest, REFERENCE[1], different_map_from=(save, digest))

    def test_bbg_input_review_requires_exact_content_and_localization_provenance(self):
        reference = dict(zip(('path', 'sha256'), REFERENCE))
        with self.assertRaisesRegex(ValueError, 'requires full captured Localization provenance'):
            selection.inspect_capture(reference, bbg751=True)
        with self.assertRaisesRegex(ValueError, 'qualified BBG 7.5.1 content scope'):
            selection.inspect_capture(reference, localization_sources=retained_localization_sources(), bbg751=True)

    def test_selected_capture_stages_the_verified_inputs_in_one_private_worker(self):
        with TemporaryDirectory(dir=resource_root() / 'work') as workspace:
            run = Path(workspace) / 'worker-run'
            chosen = self.inspect_temporary_reference(self.raw, localization_sources=retained_localization_sources(),
                                                      private_run=run)
            private = chosen['private_inputs']
            fixture_path = Path(private['fixture'])
            self.assertTrue(fixture_path.is_relative_to(run))
            fixture = json.loads(fixture_path.read_bytes())
            self.assertEqual(fixture['official_bundle'], chosen['capture'])
            self.assertFalse(fixture['eligible_for_training'])
            self.assertEqual(private['expected_readback']['turn'], chosen['boundary']['turn'])
            for role, db in private['database_copies'].items():
                self.assertEqual(db['sha256'], chosen['final_databases'][role]['sha256'])
                self.assertEqual(fixture['databases'][role]['path'], db['copy_path'])
            for role, stream in private['streams'].items():
                self.assertEqual({key: stream[key] for key in ('sha256', 'bytes')}, chosen['components'][role])
            self.assertEqual(private['icu_copy']['sha256'], chosen['localization_bootstrap']['icu_sha256'])
            for artifact in [*private['database_copies'].values(), private['icu_copy'], *private['script_copies']]:
                copied = Path(artifact['copy_path'])
                self.assertEqual(copied.parent, fixture_path.parent)
                if 'source_path' in artifact:
                    self.assertNotEqual(copied, Path(artifact['source_path']))
                with copied.open('rb') as stream:
                    self.assertEqual(file_digest(stream, 'sha256').hexdigest(), artifact['sha256'])
            for artifact in private['streams'].values():
                with Path(artifact['path']).open('rb') as stream:
                    self.assertEqual(file_digest(stream, 'sha256').hexdigest(), artifact['sha256'])
            self.assertEqual(sha256(fixture_path.read_bytes()).hexdigest(), private['fixture_sha256'])

        manifest = json.loads(self.raw)
        self.assertEqual(chosen['schema'], selection.COMPLETE_SCHEMA)
        self.assertNotEqual(chosen['capture']['path'], REFERENCE[0])
        self.assertTrue(chosen['final_databases_and_scripts_validated'])
        self.assertFalse(chosen['native_session_admitted'])
        self.assertEqual(set(chosen['final_databases']), {'configuration', 'gameplay', 'localization'})
        for role, row in manifest['export_matches'].items():
            self.assertEqual(chosen['final_databases'][role]['sha256'], row['copy']['sha256'])
        self.assertEqual(chosen['ordered_gameplay_scripts'], [{
            'selected_path': '../../../DLC/Expansion2/Scripts/WorldCongress.lua',
            'bytes': 17340,
            'sha256': '26a2eeac85f64a13aed985f9d11ae3ac26c51b6abe50f0e5a89ded63e439c032',
        }])

    def test_private_preparation_refuses_incomplete_review_or_existing_destination(self):
        with TemporaryDirectory(dir=resource_root() / 'work') as workspace:
            run = Path(workspace) / 'worker-run'
            reference = {'path': REFERENCE[0], 'sha256': REFERENCE[1]}
            with self.assertRaisesRegex(ValueError, 'full captured Localization provenance'):
                selection.inspect_capture(reference, private_run=run)
            self.assertFalse(run.exists())
            with self.assertRaisesRegex(ValueError, 'new directory under private work'):
                selection.inspect_capture(reference, localization_sources=retained_localization_sources(),
                                          private_run=workspace)

    def test_same_turn_database_journal_must_match_the_captured_bridge_exchanges(self):
        modified = json.loads(self.raw)
        first_database_event = next(row for row in modified['bridge_events'] if row['kind'] == 'database_capture')
        first_database_event['nonce'] = '00000000000000000000000000000000'
        with self.assertRaisesRegex(ValueError, 'bridge exchanges on the before side'):
            self.inspect_temporary_reference(json.dumps(modified).encode(),
                                             localization_sources=retained_localization_sources())

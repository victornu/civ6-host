"""Private XP2 saved-input admission guards; no native Load or game process."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_profiles import (
    XP2_CORE_SHA256, profile_for_sha, require_saved_load_admission,
)
from civ6_host.runtime.native import native_official_bundle as bundle_reader
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime import xp1_bundle_inputs
from civ6_host.runtime import xp2_bundle_inputs as xp2
from civ6_host.runtime import localization_bulk_export


LAB = resource_root()
CAPTURE_DIR = LAB / 'work/official-capture/xp2-gs-lan-rows-20261102-04'
CAPTURE_PATH = CAPTURE_DIR / 'manifest.json'
CAPTURE_SHA256 = '28cc55ad4c2d56535db8c0a1351445125fd75800ab54eefd3b0b600b41717f1d'
SAVE_SHA256 = '48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430'
CONFIGURATION_SHA256 = 'e9f5cf20b75932169b5b1c8bdd800ce349a0cea99c755cc1ab1d099c64eaf116'
GAME_SHA256 = '66dd00e4e6f88e2ea2b87318a7b833ebeeed15f545ef050ccf6931f5c24cf3ee'
WORLD_CONGRESS_SHA256 = '26a2eeac85f64a13aed985f9d11ae3ac26c51b6abe50f0e5a89ded63e439c032'


class XP2BundleInputsTests(unittest.TestCase):
    def test_parent_dependency_owners_declare_nested_xp2_sources(self):
        from civ6_host.runtime.foundation_event_profile import source_dependencies as foundation
        from civ6_host.runtime.xp1_session_view import source_dependencies as session_view

        expected = (
            (foundation, (
                'work/native-e660-aa-consumer555/correction-note-v2.md',
                'work/native399-boundary550.json',
                'work/native400-baseline/civ6rl/native_deferred_empty_profile.py',
            )),
            (session_view, (
                'evidence/native-city-attack-notification.json',
                'evidence/native-city-range-attack-route/264ce2c209d1d30f9ebc371caca8d835fbc89ca3c5975a1c74e281347a15ec9f.json',
                'evidence/native-combat-action-api/9f0a1734d2cfb80fdc9b1c399270859c7de0e7b3ec5a8cabffbef02dd8c09d1f.json',
                'work/city-targets936/source.json',
            )),
        )
        for owner, names in expected:
            pins = owner(core_sha256=XP2_CORE_SHA256)
            for name in names:
                with self.subTest(name=name):
                    path = (LAB / name).resolve(strict=True)
                    self.assertEqual(pins[str(path)], hashlib.sha256(path.read_bytes()).hexdigest())

    @classmethod
    def setUpClass(cls):
        raw = CAPTURE_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CAPTURE_SHA256:
            raise AssertionError('retained XP2 capture manifest changed')
        cls.capture = json.loads(raw)
        cls.process = cls.capture['preflight']['process']
        cls.runtime = []
        for name in ('runtime-selections-before.json', 'runtime-selections-after.json'):
            ref = cls.capture['artifacts'][name]
            cls.runtime.append(json.loads(Path(ref['path']).read_text(encoding='utf-8')))
        cls.scripts_ref = cls.capture['selected_gameplay_sources']['manifest']
        cls.scripts = json.loads(Path(cls.scripts_ref['path']).read_text(encoding='utf-8'))

    def test_retained_xp2_bundle_reader_extracts_exact_input_only_pair(self):
        self.assertEqual(xp2.REFERENCE, ('work/official-capture/xp2-gs-lan-rows-20261102-04/manifest.json', CAPTURE_SHA256))
        self.assertEqual(xp2.SELECTED_PATHS, ('../../../DLC/Expansion2/Scripts/WorldCongress.lua',))
        self.assertIsNone(xp2.validate_reference(xp2.REFERENCE))
        with self.assertRaises(ValueError):
            xp2.validate_reference((xp2.REFERENCE[0], '0' * 64))
        self.assertEqual(xp2.validate_process(self.process), XP2_CORE_SHA256)
        for runtime in self.runtime:
            self.assertIsNone(xp2.validate_selection_scope(runtime))
        self.assertIsNone(xp2.validate_summary_scope(self.capture['runtime_selections']))

        pins = {}
        self.assertIsNone(xp2.validate_scripts(self.scripts, Path(self.scripts_ref['path']).parent,
            self.process, pins))
        self.assertIn(WORLD_CONGRESS_SHA256, pins.values())

        prepared = bundle_reader.read_bundle(xp2.REFERENCE, input_profile='xp2-lan')
        self.assertIs(prepared.inputs.profile, xp2.XP2_LAN_PROFILE)
        self.assertEqual(prepared.inputs.official_bundle, prepared.reference)
        self.assertIsNone(xp2.validate_components(prepared.inputs.configuration, prepared.inputs.game))
        self.assertEqual(hashlib.sha256(prepared.inputs.configuration).hexdigest(), CONFIGURATION_SHA256)
        self.assertEqual(hashlib.sha256(prepared.inputs.game).hexdigest(), GAME_SHA256)
        self.assertEqual(prepared.inputs.profile.mode_name, 'LAN')
        self.assertEqual(prepared.initial_turn, 1)
        self.assertIs(prepared.content_profile['gameplay_scripts']['selected_and_active_empty'], False)
        self.assertIs(bundle_reader._reuse_prepared_bundle(prepared, xp2.REFERENCE,
            'xp2-lan', _input_only=True), prepared)
        with self.assertRaises(ValueError):
            bundle_reader._reuse_prepared_bundle(prepared, xp2.REFERENCE,
                'xp2-lan', _input_only=False)
        with self.assertRaises(ValueError):
            xp2.validate_components(prepared.inputs.configuration + b'changed', prepared.inputs.game)

    def test_process_selection_summary_and_script_mutations_are_refused(self):
        for changed in (
            {**self.process, 'exe_sha256': '0' * 64},
            {**self.process, 'gamecore_module': {**self.process['gamecore_module'], 'sha256': '0' * 64}},
        ):
            with self.subTest(process=changed.get('exe_sha256', changed['gamecore_module'].get('sha256'))), self.assertRaises(ValueError):
                xp2.validate_process(changed)

        changed_runtime = deepcopy(self.runtime[0])
        changed_runtime['gameplay_selection994']['snapshot']['selected_paths'] = []
        with self.assertRaises(ValueError):
            xp2.validate_selection_scope(changed_runtime)
        changed_runtime = deepcopy(self.runtime[1])
        changed_runtime['gameplay_active_list']['selection']['snapshot']['selected_paths'] = []
        with self.assertRaises(ValueError):
            xp2.validate_selection_scope(changed_runtime)
        changed_runtime = deepcopy(self.runtime[0])
        changed_runtime['gameplay_active_list']['state']['active_count'] = 0
        with self.assertRaises(ValueError):
            xp2.validate_selection_scope(changed_runtime)
        changed_runtime['gameplay_active_list']['state']['active_count'] = True
        with self.assertRaises(ValueError):
            xp2.validate_selection_scope(changed_runtime)

        changed_summary = deepcopy(self.capture['runtime_selections'])
        changed_summary['gameplay_execution_proven'] = True
        with self.assertRaises(ValueError):
            xp2.validate_summary_scope(changed_summary)

        changed_scripts = deepcopy(self.scripts)
        changed_scripts['selected_paths'] = []
        with self.assertRaises(ValueError):
            xp2.validate_scripts(changed_scripts, Path(self.scripts_ref['path']).parent,
                self.process, {})
        changed_scripts = deepcopy(self.scripts)
        changed_scripts['includes_and_dependencies_captured'] = True
        with self.assertRaises(ValueError):
            xp2.validate_scripts(changed_scripts, Path(self.scripts_ref['path']).parent,
                self.process, {})
        changed_scripts = deepcopy(self.scripts)
        changed_scripts['path_resolution']['context']['process']['pid'] += 1
        with self.assertRaises(ValueError):
            xp2.validate_scripts(changed_scripts, Path(self.scripts_ref['path']).parent,
                self.process, {})

        with tempfile.TemporaryDirectory(dir=LAB / 'work') as temporary:
            copied = Path(temporary)
            for row in self.scripts['files']:
                shutil.copy2(Path(self.scripts_ref['path']).parent / row, copied / row)
            first = next(iter(self.scripts['files']))
            (copied / first).write_bytes((copied / first).read_bytes() + b'changed')
            with self.assertRaises(ValueError):
                xp2.validate_scripts(self.scripts, copied, self.process, {})

    def test_current_execution_image_is_an_explicit_xp2_abi_selection(self):
        from civ6_host.runtime.execution_images import known_path, select

        current_manifest = LAB / 'work/official-capture/bbg751-world-A-ui/manifest.json'
        raw = current_manifest.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d')
        current_process = json.loads(raw)['preflight']['process']
        profile_id = xp2.CURRENT_EXECUTION_PROFILE_ID
        image = select(profile_id, core_path=known_path(profile_id))
        self.assertEqual(image.image_sha256, xp2.CURRENT_XP2_CORE_SHA256)
        self.assertEqual(image.reference_core_sha256, XP2_CORE_SHA256)
        self.assertEqual(xp2.validate_process(current_process, execution_image=image),
                         xp2.CURRENT_XP2_CORE_SHA256)

        with self.assertRaises(ValueError):
            xp2.validate_process(current_process)
        with self.assertRaises(ValueError):
            xp2.validate_process({**current_process, 'exe_sha256': '0' * 64},
                                 execution_image=image)
        with self.assertRaises(ValueError):
            xp2.validate_process({**current_process, 'gamecore_module': {
                **current_process['gamecore_module'], 'sha256': XP2_CORE_SHA256}},
                execution_image=image)
        with self.assertRaises(ValueError):
            xp2.validate_process(self.process, execution_image=image)
        altered = dict(image.__dict__)
        altered['reference_core_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            xp2.validate_process(current_process, execution_image=altered)

    def test_reader_source_pins_and_public_base_xp1_guards_remain_closed(self):
        digests = xp2.reader_validator_digests()
        self.assertTrue(digests)
        xp2.recheck_reader_validators(digests)
        altered = dict(digests)
        key = next(iter(altered))
        altered[key] = '0' * 64
        with self.assertRaises(ValueError):
            xp2.recheck_reader_validators(altered)

        with self.assertRaises(ValueError):
            official.validate_profile(xp2.XP2_LAN_PROFILE)
        with self.assertRaises(ValueError):
            require_saved_load_admission(profile_for_sha(XP2_CORE_SHA256))
        with self.assertRaises(ValueError):
            xp1_bundle_inputs.validate_process(self.process)
        with self.assertRaises(ValueError):
            xp1_bundle_inputs.validate_selection_scope(self.runtime[0])
        with self.assertRaises(ValueError):
            bundle_reader.read_bundle(xp2.REFERENCE, input_profile='lan')

    def test_retained_localization_dependencies_use_pinned_private_copies(self):
        reference = xp2.retained_localization_sources()
        manifest_path = Path(reference['path'])
        report = json.loads(manifest_path.read_text(encoding='utf-8'))
        profile = report['profile']

        dependencies = localization_bulk_export.retained_dependencies(profile, reference)
        self.assertIsInstance(dependencies, list)
        dependency_paths = {Path(item['path']).resolve() for item in dependencies}
        self.assertIn(manifest_path.resolve(), dependency_paths)
        for row in report['files']:
            copied = Path(row['copy']['path']).resolve()
            self.assertIn(copied, dependency_paths)
            self.assertTrue(copied.is_relative_to(manifest_path.parent.resolve() / 'sources'))
        live_transport = Path(profile['transport']['path']).resolve()
        self.assertNotIn(live_transport, dependency_paths)
        self.assertTrue(all(path.is_relative_to(LAB.resolve() / 'work') for path in dependency_paths))

        bad_digest = dict(reference, sha256='0' * 64)
        with self.assertRaises(ValueError):
            localization_bulk_export.retained_dependencies(profile, bad_digest)
        altered_profile = deepcopy(profile)
        altered_profile['transport']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            localization_bulk_export.retained_dependencies(altered_profile, reference)

        # Redirect only a temporary manifest and copies. The retained originals
        # and the official capture remain untouched while exercising file-pin checks.
        with tempfile.TemporaryDirectory(dir=LAB / 'work') as temporary:
            copied_root = Path(temporary) / 'snapshot'
            shutil.copytree(manifest_path.parent, copied_root)
            copied_report = deepcopy(report)
            for row in copied_report['files']:
                filename = Path(row['copy']['path']).name
                row['copy']['path'] = str(copied_root / 'sources' / filename)
            copied_manifest = copied_root / 'manifest.json'
            copied_manifest.write_text(json.dumps(copied_report), encoding='utf-8')
            copied_reference = {
                'path': str(copied_manifest),
                'sha256': hashlib.sha256(copied_manifest.read_bytes()).hexdigest(),
                'bytes': copied_manifest.stat().st_size,
            }
            changed_copy = Path(copied_report['files'][0]['copy']['path'])
            changed_copy.write_bytes(changed_copy.read_bytes() + b'changed')
            with self.assertRaises(ValueError):
                localization_bulk_export.retained_dependencies(profile, copied_reference)

    def test_xp2_candidate_cannot_prepare_a_native_fixture_or_write_files(self):
        with tempfile.TemporaryDirectory(dir=LAB / 'work') as temporary:
            output = Path(temporary) / 'fixture'
            with patch.object(bundle_reader, 'read_bundle') as read:
                with self.assertRaises(ValueError):
                    bundle_reader.prepare_official_bundle(xp2.REFERENCE,
                        input_profile='xp2-lan', output_directory=output)
            read.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()

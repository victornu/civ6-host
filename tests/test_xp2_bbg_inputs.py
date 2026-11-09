"""Regression checks for the exact private BBG input owner."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_bbg_inputs as bbg
from civ6_host.runtime import xp2_bundle_inputs as stock
from civ6_host.runtime.captured_saved_load import validate_candidate_inputs
from civ6_host.runtime.native.native_official_bundle import _file, _reuse_prepared_bundle, validate_fixture
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp1_session_inputs import prepare_private_fixture


@unittest.skipUnless((resource_root() / bbg.REFERENCE[0]).is_file(), 'Private BBG capture absent')
class BBGInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = bbg.read_bundle()

    def test_private_admission_keeps_stock_scope(self):
        bundle = self.bundle
        self.assertIs(validate_candidate_inputs(bundle.inputs, bundle), stock.XP2_LAN_PROFILE)
        self.assertIs(_reuse_prepared_bundle(bundle, bbg.REFERENCE, 'xp2-lan', _input_only=True), bundle)
        with self.assertRaises(ValueError):
            _reuse_prepared_bundle(bundle, bbg.REFERENCE, 'xp2-lan')
        with self.assertRaises(ValueError):
            stock.validate_reference(bundle.reference)

    def test_client_selection_is_bound_to_the_exact_reference(self):
        from civ6_host.runtime.captured_session_profile import for_family
        self.assertEqual(for_family('xp2-lan').candidate.reference, stock.REFERENCE)
        self.assertEqual(for_family('xp2-lan', official_bundle=bbg.REFERENCE).candidate.reference,
                         bbg.REFERENCE)
        altered = (bbg.REFERENCE[0], stock.REFERENCE[1])
        self.assertEqual(for_family('xp2-lan', official_bundle=altered).candidate.reference,
                         stock.REFERENCE)

    def test_registered_capture_selects_bbg_services_but_stock_streams_are_refused(self):
        from civ6_host.runtime.capture_candidates import select_private_candidate
        from civ6_host.runtime.native.native_official_bundle import _manifest
        from civ6_host.runtime.xp2_saved_init import input_identity

        reference = dict(zip(('path', 'sha256'), stock.REFERENCE))
        with patch.dict('os.environ', {bbg.CAPTURE_ENV: json.dumps(reference)}):
            selected = select_private_candidate(candidate_profile='xp2-lan')
            self.assertEqual(selected.reference, stock.REFERENCE)
            self.assertIs(selected.validate_inputs, bbg.validate_candidate_inputs)
            self.assertEqual(input_identity(replace(self.bundle, reference=stock.REFERENCE))[0], stock.REFERENCE)
            self.assertFalse(bbg.is_reference((stock.REFERENCE[0], bbg.REFERENCE[1])))
            with self.assertRaisesRegex(ValueError, 'qualified BBG 7.5.1 content scope'):
                bbg.verify_original_streams(self.bundle.inputs, _manifest(stock.REFERENCE)[1], {})

    def test_registered_stream_rejoin_reads_actual_official_bbg_bytes(self):
        record, _ = bbg._capture({})
        source = record['save']
        # The real BBG recovery predates a completed capture994. Supply the
        # complete reader's save envelope over the original official bytes.
        capture = {'save': {'source': source, 'extraction907': {
            'manifest': str(Path(source['path']).with_name('manifest.json'))}}}
        dependencies = {}
        bbg.verify_original_streams(self.bundle.inputs, capture, dependencies)
        self.assertIn(bbg.SAVE_SHA256, dependencies.values())
        wrong = replace(self.bundle.inputs, game=self.bundle.inputs.game[:-1])
        with self.assertRaisesRegex(ValueError, 'official saved streams'):
            bbg.verify_original_streams(wrong, capture, {})

    def test_registered_source_audit_requires_the_same_pinned_package(self):
        from civ6_host.runtime import capture_admission, provenance

        origin = dict(zip(('path', 'sha256'), stock.REFERENCE))
        package = resource_root() / 'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'
        pin = dict(path=str(package), sha256='6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020')
        with patch.dict('os.environ', {bbg.CAPTURE_ENV: json.dumps(origin)}), patch.object(
                capture_admission, 'configured_reference', return_value=pin) as configured:
            self.assertFalse(provenance._audit_historical_by_default())
            configured.return_value = dict(pin, sha256='0' * 64)
            with self.assertRaisesRegex(ValueError, 'manifest hash differs'):
                provenance._audit_historical_by_default()

    def test_recovered_worker_handoff_checks_the_launch_binding(self):
        from civ6_host.runtime import capture_admission
        reference = bbg.prepared_reference()
        closure = dict(official_bundle=dict(zip(('path', 'sha256'), bbg.REFERENCE)),
                       input_profile='xp2-lan', pins={reference['path']: reference['sha256']})
        with patch.object(capture_admission, 'configured_reference', return_value=reference):
            self.assertTrue(capture_admission.configure_prepared_closure(closure, self.bundle))
            receipt = capture_admission.consume_prepared_closure(
                closure, environment={}, _candidate_profile='xp2-lan')
            self.assertEqual(receipt['authority'], 'exact_bbg751_recovered_capture_revalidation')
            closure[capture_admission.XP2_LAUNCH_FIELD]['saved_geometry']['turn'] += 1
            with self.assertRaisesRegex(ValueError, 'launch binding differs'):
                capture_admission.consume_prepared_closure(
                    closure, environment={}, _candidate_profile='xp2-lan')

    def test_tampered_game_stream_is_refused(self):
        original = self.bundle
        inputs = replace(original.inputs, game=original.inputs.game[:-1])
        forged = replace(original, inputs=inputs)
        with self.assertRaisesRegex(ValueError, 'saved components'):
            validate_candidate_inputs(inputs, forged)

    def test_streamed_header_authenticates_the_tail(self):
        with tempfile.TemporaryDirectory(dir=resource_root() / 'work') as directory:
            path = Path(directory) / 'fixture.sqlite'
            header = b'SQLite format 3\0'
            data = header + bytes(2 * 1024 ** 2)
            path.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            row = dict(path=str(path), bytes=len(data), sha256=sha)
            dependencies = {}
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('full read')):
                self.assertEqual(_file(row, dependencies, prefix_bytes=len(header)), header)
                self.assertEqual(_file(row, dependencies, prefix_bytes=0), b'')
                with path.open('r+b') as stream:
                    stream.seek(-1, 2)
                    stream.write(b'X')
                with self.assertRaisesRegex(ValueError, 'Bundle file hash differs'):
                    _file(row, {}, prefix_bytes=len(header))
            self.assertEqual(dependencies, {str(path.resolve()): sha})

    def test_private_fixture_and_two_script_pins(self):
        registry, hashes, _ = bbg.script_binding(self.bundle)
        self.assertEqual(registry.wire_paths[0], stock.SELECTED_PATHS[0])
        self.assertTrue(registry.wire_paths[1].endswith('/scripts/bbg_script.lua'))
        self.assertEqual(list(hashes.values()), [stock.SCRIPT_SHA256, bbg.SCRIPT_SHA256])
        with tempfile.TemporaryDirectory(dir=resource_root() / 'work') as directory:
            fixture, _ = prepare_private_fixture(Path(directory), self.bundle, {})
            validate_fixture(self.bundle, fixture)

    def test_official_bbg_script_witnesses_join_shared_private_preparation(self):
        from civ6_host.runtime.xp2_capture_selection import _prepare_private_inputs, _selected_scripts

        root = resource_root()
        folder = root / bbg.CAPTURE
        record, process = bbg._capture({})
        script_pin = record['script_manifest']
        artifact_names = [f'runtime-selections-{side}.json' for side in ('before', 'after')]
        artifacts = {name: dict(path=(folder / name).relative_to(root).as_posix(),
                                sha256='af865d7437e391d0fd7a1a98c483a8ed361b3066c971d2859b3048242527e9f4',
                                bytes=(folder / name).stat().st_size) for name in artifact_names}
        # The interrupted capture has these exact witnesses, not a completed
        # capture994 manifest. Supply just this stage's envelope.
        summary = dict(selected_paths=record['script_order'], consumer_core_matches_base_proof=False,
                       content_application_success_proven=False, gameplay_execution_proven=False,
                       gameplay_active_list=dict(status='nonempty_profile_unqualified', selected_and_active_empty=False,
                                                 observed_on_both_sides=True, load_completion_proven=False,
                                                 historical_execution_proven=False))
        manifest = dict(artifacts=artifacts, runtime_selections=summary,
                        selected_gameplay_sources=dict(manifest=script_pin))
        scripts, selection, active = _selected_scripts(manifest, process, folder, {}, bbg751=True)
        self.assertEqual(selection['selected_paths'], record['script_order'])
        self.assertEqual(active['state']['active_count'], 2)
        sources = [(folder / 'selected-gameplay-sources' / row['copy'], scripts['files'][row['copy']])
                   for row in scripts['records']]
        with tempfile.TemporaryDirectory(dir=root / 'work') as directory:
            staged = _prepare_private_inputs(Path(directory) / 'run', self.bundle, sources)
            self.assertEqual(staged['expected_readback'], self.bundle.expected_readback)
            self.assertEqual(list(staged['streams']), ['configuration', 'gamecore'])
            self.assertEqual(set(staged['database_copies']), {'configuration', 'gameplay', 'localization'})
            self.assertEqual([row['sha256'] for row in staged['script_copies']],
                             [stock.SCRIPT_SHA256, bbg.SCRIPT_SHA256])
            for row in staged['script_copies']:
                self.assertEqual(hashlib.sha256(Path(row['copy_path']).read_bytes()).hexdigest(), row['sha256'])
        summary['selected_paths'] = list(reversed(summary['selected_paths']))
        with self.assertRaisesRegex(ValueError, 'witnessed native order'):
            _selected_scripts(manifest, process, folder, {}, bbg751=True)


class CurrentBBGInputImageTests(unittest.TestCase):
    def test_registered_current_content_uses_only_explicit_reference_abi_profile(self):
        from civ6_host.runtime.execution_images import known_path, select
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        from civ6_host.runtime.native.native_official_load import OfficialInputs
        from civ6_host.runtime.gameplay_active_profiles import CURRENT_XP2_CORE_SHA256

        origin = ('work/official-capture/bbg751-world-A-ui/manifest.json',
                  '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d')
        profile_id = 'xp2-gamecore-current-092abfbb'
        image = select(profile_id, core_path=known_path(profile_id))
        process = dict(exe_sha256=stock.CURRENT_EXE_SHA256,
                       gamecore_module=dict(sha256=CURRENT_XP2_CORE_SHA256, path=image.path))
        capture = dict(preflight=dict(process=process), process_after=process)
        maps = (('MapSize', 4),)
        inputs = OfficialInputs(configuration=b'config', game=b'game', map_values=maps,
                                profile=stock.XP2_LAN_PROFILE, official_bundle=origin)
        pins = {'configuration': {'sha256': '1' * 64, 'size_bytes': 1},
                'gameplay': {'sha256': '2' * 64, 'size_bytes': 2},
                'localization': {'sha256': '3' * 64, 'size_bytes': 3}}
        bundle = PreparedBundle(
            reference=origin, inputs=inputs, initial_turn=1, engine_path=Path(image.path),
            fixture={}, dependencies={}, expected_readback=dict(turn=1, width=44, height=26, player_id=0),
            content_profile=dict(engine=dict(executable_sha256=stock.CURRENT_EXE_SHA256,
                                             gamecore_sha256=CURRENT_XP2_CORE_SHA256),
                                 final_databases=pins), execution_image=image)

        with patch.object(bbg, 'registered_reference', return_value=origin), \
             patch.object(bbg, '_complete_capture', return_value=capture), \
             patch.object(bbg, 'database_pins', return_value=pins), \
             patch.object(bbg, 'verify_original_streams') as verify_streams, \
             patch('civ6_host.runtime.native.native_official_bundle.parse_configuration',
                   return_value=(b'config', maps)):
            self.assertIs(bbg.validate_candidate_inputs(inputs, bundle), stock.XP2_LAN_PROFILE)
            verify_streams.assert_called_once_with(inputs, capture, {})
            with self.assertRaises(ValueError):
                bbg.validate_candidate_inputs(inputs, replace(bundle, execution_image=None))
            with self.assertRaisesRegex(ValueError, 'process and content image differ'):
                wrong = dict(capture, preflight=dict(process={**process, 'exe_sha256': '0' * 64}))
                with patch.object(bbg, '_complete_capture', return_value=wrong):
                    bbg.validate_candidate_inputs(inputs, bundle)
            with self.assertRaises(ValueError):
                wrong_content = dict(bundle.content_profile)
                wrong_content['engine'] = dict(bundle.content_profile['engine'],
                                               gamecore_sha256='0' * 64)
                bbg.validate_candidate_inputs(inputs, replace(bundle, content_profile=wrong_content))
        with patch.object(bbg, 'registered_reference', return_value=(origin[0], '0' * 64)):
            with self.assertRaisesRegex(ValueError, 'exact registered capture origin'):
                bbg.validate_candidate_inputs(inputs, bundle)


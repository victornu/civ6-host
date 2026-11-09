"""Current official BBG input joins, without executing native game code."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import capture_admission as admission, capture_candidates
from civ6_host.runtime import xp2_bbg_inputs as bbg, xp2_capture_selection as selection
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.paths import resource_root


ORIGIN = ('work/official-capture/bbg751-world-A-ui/manifest.json',
          '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d')
IMAGE = select('xp2-gamecore-current-092abfbb',
               core_path=known_path('xp2-gamecore-current-092abfbb'))
PACKAGE = dict(path=str(resource_root() / 'work/current-bbg-fixture/manifest.json'), sha256='e' * 64)


class CurrentBBGCaptureAdmissionTests(unittest.TestCase):
    def test_current_localization_bootstrap_keeps_the_runtime_icu_byte_count(self):
        from tempfile import TemporaryDirectory
        import shutil
        folder, manifest = self.retained()
        with patch.dict(os.environ, {bbg.CAPTURE_ENV: json.dumps(dict(zip(('path', 'sha256'), ORIGIN)))}):
            _, bootstrap = bbg._complete_localization(manifest)
            self.assertEqual(bootstrap['icu_data']['bytes'], 25037248)
            # Reuse the already materialized package; the installed bridge has
            # been restored, so its mutable paths are not producer authority.
            package = resource_root() / 'work/host-prepared-captures/bbg751-world-A-current'
            if not (package / 'manifest.json').is_file():
                self.skipTest('Retained prepared current package required')
            saved = json.loads((package / 'manifest.json').read_bytes())
            with TemporaryDirectory(dir=resource_root() / 'work') as directory:
                private = Path(directory)
                localization = saved['files']['database_localization']
                icu = saved['files']['icu_data']
                database_path = private / 'localization.sqlite'
                icu_path = private / 'icudt56l.dat'
                shutil.copyfile(package / localization['path'], database_path)
                shutil.copyfile(package / icu['path'], icu_path)
                fixture = dict(input_profile='xp2-lan', official_bundle=dict(zip(('path', 'sha256'), ORIGIN)),
                    databases={'localization':dict(path=str(database_path), sha256=localization['sha256'],
                                                  size_bytes=localization['bytes'])},
                    localization_bootstrap={**bootstrap, 'icu_data':{**bootstrap['icu_data'], 'path':str(icu_path)}})
                bbg.validate_localization_fixture(fixture)
                fixture['localization_bootstrap']['icu_data']['bytes'] += 1
                with self.assertRaisesRegex(ValueError, 'immutable settings differ'):
                    bbg.validate_localization_fixture(fixture)

    def test_current_dispatch_binds_registered_origin_and_distinct_package(self):
        with patch.object(bbg, 'registered_reference', return_value=ORIGIN), \
             patch.object(admission, 'configured_reference', return_value=PACKAGE), \
             patch.object(admission, '_stock_xp2_execution', side_effect=AssertionError('stock route')):
            self.assertTrue(admission._prepared_xp2_execution(IMAGE, reference=PACKAGE, origin=ORIGIN))
            with self.assertRaisesRegex(ValueError, 'exact registered origin and prepared package'):
                admission._prepared_xp2_execution(IMAGE,
                    reference=dict(PACKAGE, sha256='f' * 64), origin=ORIGIN)
            self.assertFalse(admission._prepared_xp2_execution(None, reference=PACKAGE, origin=ORIGIN))

    def test_other_origin_keeps_the_strict_stock_route(self):
        other = (ORIGIN[0], '0' * 64)
        with patch.object(bbg, 'registered_reference', return_value=ORIGIN), \
             patch.object(admission, '_stock_xp2_execution', side_effect=ValueError('stock guard')) as stock:
            with self.assertRaisesRegex(ValueError, 'stock guard'):
                admission._prepared_xp2_execution(IMAGE, reference=PACKAGE, origin=other)
        stock.assert_called_once_with(IMAGE, reference=PACKAGE, origin=other)

    def test_common_handoff_forwards_registered_current_image(self):
        bundle = SimpleNamespace(inputs=object())
        candidate = SimpleNamespace(reference=ORIGIN, family='xp2-lan', validate_inputs=lambda *_: None)
        with patch.object(bbg, 'registered_reference', return_value=ORIGIN), \
             patch.object(admission, 'configure'), \
             patch.object(capture_candidates, 'select_private_candidate', return_value=candidate), \
             patch.object(admission, 'try_bundle', return_value=bundle) as consume:
            self.assertIs(capture_candidates.consume_input_handoff('xp2-lan', PACKAGE,
                official_bundle=ORIGIN, execution_image=IMAGE), bundle)
        self.assertEqual(consume.call_args.args, (ORIGIN,))
        self.assertIs(consume.call_args.kwargs['execution_image'], IMAGE)

    def retained(self):
        from hashlib import sha256
        path = resource_root() / ORIGIN[0]
        if not path.is_file():
            self.skipTest('Retained private current official capture required')
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), ORIGIN[1])
        return path.parent, json.loads(raw)

    def test_retained_current_scripts_join_to_the_actual_two_contexts(self):
        folder, manifest = self.retained()
        dependencies = {}
        scripts, selected, active = selection._selected_scripts(manifest, manifest['preflight']['process'],
                                                                folder, dependencies, bbg751=True)
        self.assertEqual(len(scripts['records']), 2)
        self.assertEqual(selected['selected_paths'], manifest['runtime_selections']['selected_paths'])
        self.assertEqual(active['state']['active_count'], 2)
        self.assertNotIn('configured_mod_handles', selected['content'])
        self.assertEqual(set(selected['content']['opaque_manager_headers']), {'manager_plus_0x1d8'})
        self.assertFalse(manifest['runtime_selections']['gameplay_execution_proven'])
        self.assertTrue(dependencies)

    def test_current_content_is_recomputed_from_both_retained_sides(self):
        from civ6_host.runtime.native import native_official_bundle as original
        from civ6_host.runtime.workers.capture_phase1_bundle994 import _content_semantics, _selection_semantics
        folder, manifest = self.retained()
        runtimes = [json.loads((folder / ('runtime-selections-' + side + '.json')).read_bytes())
                    for side in ('before', 'after')]
        scripts = json.loads((folder / 'selected-gameplay-sources/manifest.json').read_bytes())
        exported = json.loads(Path(manifest['localization_exports']['after']['path']).read_bytes())
        databases = {role: dict(sha256=row['copy']['sha256'], size_bytes=row['copy']['bytes'])
                     for role, row in manifest['export_matches'].items()}
        databases['localization'] = dict(sha256=exported['database']['sha256'],
                                         size_bytes=exported['database']['bytes'])
        process = manifest['preflight']['process']; runtime = runtimes[0]
        resolved = _content_semantics(runtime['content929']['snapshot'], process)
        selected = _selection_semantics(runtime['gameplay_selection994'], process, resolved)
        active = runtime['gameplay_active_list']
        profile = original.build_content_profile(process=process, databases=databases,
            localization_bootstrap=exported['bootstrap'], resolved_content=resolved, gameplay_selection=selected,
            active_state=dict(active_count=active['state']['active_count'],
                              selected_and_active_empty=active['selected_and_active_empty']), script_manifest=scripts)
        admission._verify_content_profile(profile, process, databases, exported['bootstrap'], runtimes, scripts)
        self.assertEqual(profile['engine']['gamecore_sha256'], IMAGE.image_sha256)
        self.assertEqual(profile['schema'], 'civ6rl.official_content_profile.v2')
        forged = copy.deepcopy(profile)
        forged['engine']['gamecore_sha256'] = IMAGE.reference_core_sha256
        with self.assertRaisesRegex(ValueError, 'differs from pinned native runtime evidence'):
            admission._verify_content_profile(forged, process, databases, exported['bootstrap'], runtimes, scripts)


if __name__ == '__main__':
    unittest.main()

"""Review the built SDK relocation and capture/execution identity separation."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import execution_images, source_build_identity as builds
from civ6_host.runtime import xp2_bbg_inputs as bbg
from civ6_host.runtime.native.native_official_bundle import PreparedBundle, _prepared_bundle_fingerprint
from civ6_host.runtime.paths import resource_root


class CurrentHavokHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = Path(__file__).resolve().parents[1]
        cls.lab = resource_root()
        cls.profile = execution_images.select('xp2-gamecore-current-092abfbb',
            core_path=execution_images.known_path('xp2-gamecore-current-092abfbb'))

    def test_compiled_host_keeps_exact_parent_components_except_sdk_guards(self):
        before = json.loads((self.host/'native/profiles/xp2-bbg/source-manifest.json').read_bytes())
        after = json.loads((self.lab/'work/native-host-xp2-current-havok-build01/build.json').read_bytes())
        self.assertEqual(after['compiler_exit_code'], 0)
        self.assertTrue(after['compiler_reaped'])
        self.assertFalse(after['gamecore_loaded'])
        old = {row.get('build_path', row['path']): row['sha256'] for row in before['sources']}
        current = {row['build_path']: row['sha256'] for row in after['sources']}
        self.assertEqual(set(old), set(current))
        changed = {key for key in old if old[key] != current[key]}
        self.assertEqual(changed, {'gamecore_python_host.c', 'script_game_event_aggregators.inc',
            'script_game_event_result_map.inc', 'script_aux_b8.inc'})
        executable = self.lab/builds.CURRENT_HAVOK_HOST_REFERENCE[0]
        actual = builds.verify_source_build(executable, required_components=
            builds.xp2_component_requirements(executable,
                {key: old[key] for key in changed}))
        self.assertEqual(actual['host_sha256'], after['executable']['sha256'])
        self.assertTrue(all(actual['sources'][key] == current[key] for key in changed))
        self.assertFalse(actual['native_compatibility_claimed'])

    def test_old_host_is_default_and_current_host_needs_explicit_image(self):
        self.assertEqual(bbg.selected_ui_host(), bbg.UI_HOST)
        self.assertEqual(bbg.selected_ui_host(self.profile), builds.CURRENT_STRINGS_HOST_REFERENCE)
        executable = self.lab/bbg.UI_HOST[0]
        required = {'gamecore_python_host.c': builds.XP2_HOST_COMPONENT_SHA}
        self.assertEqual(builds.xp2_component_requirements(executable, required), required)
        builds.verify_source_build(executable, required_components=required)

    def test_current_host_does_not_accept_an_unknown_component_transition(self):
        for reference in (builds.CURRENT_HAVOK_HOST_REFERENCE,
                          builds.CURRENT_STRINGS_HOST_REFERENCE):
            with self.subTest(host=reference[0]):
                with self.assertRaisesRegex(ValueError, 'no transition'):
                    builds.xp2_component_requirements(self.lab/reference[0],
                        {'gamecore_python_host.c': 'a'*64})
        with self.assertRaisesRegex(ValueError, 'not the registered'):
            execution_images.identity(replace(self.profile, image_sha256='b'*64))

    def test_strings_manifest_changes_only_dispatch_and_result_map_and_keeps_history(self):
        parent_path = self.host/'native/profiles/xp2-current-havok/source-manifest.json'
        manifest_path = self.host/'native/profiles/xp2-current-strings/source-manifest.json'
        parent = json.loads(parent_path.read_bytes())
        manifest = json.loads(manifest_path.read_bytes())
        self.assertEqual(manifest['profile'], builds.CURRENT_STRINGS_BUILD_PROFILE)
        self.assertEqual(manifest['parent_manifest'], {
            'path': 'native/profiles/xp2-current-havok/source-manifest.json',
            'sha256': '502731d5db3592d62391b7d2b5eeadc1706ac45eee8ffe1e84b8dd38e618fe4d',
        })
        self.assertEqual(hashlib.sha256(parent_path.read_bytes()).hexdigest(),
                         manifest['parent_manifest']['sha256'])
        old = {row['build_path']: row for row in parent['sources']}
        current = {row['build_path']: row for row in manifest['sources']}
        expected = {
            'script_game_event_dispatch_legacy.inc': (
                'native/profiles/xp2-current-strings/script_game_event_dispatch.inc',
                '34b1949f2383b776cc59ebfedabeadd5ddb2a3510348505e1e16bb0395093fd0'),
            'script_game_event_result_map.inc': (
                'native/profiles/xp2-current-strings/script_game_event_result_map.inc',
                'ab7fa2c648238f8b3f6c1eb2ea53897ecfe718df045625788889d2bc29610c1e'),
        }
        self.assertEqual(set(current), set(old))
        self.assertEqual({name for name in old if current[name] != old[name]}, set(expected))
        for name, (path, digest) in expected.items():
            with self.subTest(component=name):
                row = current[name]
                self.assertEqual((row['path'], row['sha256']), (path, digest))
                raw = (self.host/path).read_bytes()
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                                 (row['bytes'], digest))
                self.assertEqual(hashlib.sha256((self.host/old[name]['path']).read_bytes()).hexdigest(),
                                 old[name]['sha256'])
        required = {name: row['sha256'] for name, row in current.items()}
        result = builds.verify_source_build(self.lab/builds.CURRENT_STRINGS_HOST_REFERENCE[0],
                                           required_components=required)
        self.assertEqual(result['profile'], 'xp2-current-strings-source-v1')
        self.assertEqual(result['source_manifest_sha256'],
                         hashlib.sha256(manifest_path.read_bytes()).hexdigest())
        self.assertFalse(result['native_compatibility_claimed'])
        # Keep the exact predecessors registered with their own provenance.
        for host_sha, receipt_sha, manifest_sha, profile in (
            ('c8fa420876ffbdaafaf4df82dfe4ad72187ceb146995afb65f98f5242267e52f',
             '4df115a7abcc3a6906730b7febed4735ca381cfb685d648d04ad9c451808d175',
             '502731d5db3592d62391b7d2b5eeadc1706ac45eee8ffe1e84b8dd38e618fe4d',
             'xp2-bbg-current-havok-201979'),
            ('61953897b696b45a7998126392f5759c7b34ed045551ff7d597ffa3eaa2fafda',
             '0c01abf9c1afc8db20a25cfdc5c1ce54151fd20bb7ac3512f94417679132bd11',
             '4ede5cab72b03ba0261f4e0275df48bf99fc3501af6053666b651cb3ff6374d3',
             'xp2-bbg-private-property-table'),
        ):
            with self.subTest(historical_host=host_sha):
                registered = builds.SOURCE_BUILDS[host_sha]
                self.assertEqual((registered['reference'][1], registered['manifest_sha256'],
                                  registered['profile']), (receipt_sha, manifest_sha, profile))
                retained = (self.lab/registered['reference'][0]).read_bytes()
                self.assertEqual(hashlib.sha256(retained).hexdigest(), receipt_sha)

    def test_bundle_fingerprint_binds_execution_without_rewriting_capture(self):
        origin = ('original-capture.json', 'a'*64)
        profile = NS(mode_name='LAN', config_sha='c'*64, game_sha='d'*64, save_sha='e'*64)
        inputs = NS(profile=profile, configuration=b'config', game=b'game', map_values=(),
                    official_bundle=origin, checkpoint=None)
        content = {'engine': {'gamecore_sha256': self.profile.reference_core_sha256}}
        bundle = PreparedBundle(origin, inputs, 1, Path(self.profile.path), {}, {}, {}, content)
        original = deepcopy(content)
        historical = _prepared_bundle_fingerprint(bundle)
        selected = replace(bundle, execution_image=self.profile)
        self.assertNotEqual(historical, _prepared_bundle_fingerprint(selected))
        self.assertEqual(bundle.content_profile, original)
        self.assertEqual(selected.content_profile, original)
        self.assertEqual(selected.execution_image.image_sha256, self.profile.image_sha256)
        self.assertEqual(_prepared_bundle_fingerprint(replace(selected, execution_image=None)), historical)

    def test_real_bbg_input_bundle_keeps_capture_reference_with_selected_image(self):
        bundle = bbg.read_bundle(execution_image=self.profile)
        self.assertIs(bundle.execution_image, self.profile)
        self.assertEqual(bundle.content_profile['engine']['gamecore_sha256'],
                         self.profile.reference_core_sha256)
        self.assertEqual(bundle.engine_path, Path(self.profile.path))
        self.assertEqual(bundle.dependencies[str(bundle.engine_path)], self.profile.image_sha256)

    def test_complete_bbg_command_preparation_pins_the_selected_runtime(self):
        from civ6_host.runtime.xp1_session_inputs import prepare_sources
        bundle = bbg.read_bundle(execution_image=self.profile)
        pins, executable = prepare_sources(bundle, bbg.prepared_reference(),
            postload160=True, publish_cache=True, close_loaded=True,
            observe_player=True, unit_commands=True,
            core_sha256=self.profile.reference_core_sha256)
        self.assertEqual(pins[self.profile.path], self.profile.image_sha256)
        self.assertEqual(executable, self.lab/builds.CURRENT_STRINGS_HOST_REFERENCE[0])
        self.assertEqual(pins[str(executable)], builds.CURRENT_STRINGS_HOST_REFERENCE[1])
        self.assertEqual(bundle.content_profile['engine']['gamecore_sha256'],
                         self.profile.reference_core_sha256)

    def test_real_reset_prepares_the_whole_closure_before_the_launch_boundary(self):
        # Capture selection is immutable within a production process. Exercise
        # this path in a fresh interpreter, independent of other fixture imports.
        env = dict(os.environ)
        host_tests = str(self.host/'tests')
        env['PYTHONPATH'] = os.pathsep.join((str(self.host/'src'), host_tests,
                                           env.get('PYTHONPATH', '')))
        run = subprocess.run([sys.executable, '-P', '-c',
            'from test_current_havok_host import CurrentHavokHostTests as T; '
            'T.setUpClass(); T()._prepare_real_reset_before_launch()'],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', timeout=180)
        self.assertEqual(run.returncode, 0, run.stdout)

    def _prepare_real_reset_before_launch(self):
        from civ6_host.runtime.backend import NetworkBackend
        checkpoint = json.loads((self.lab/
            'work/actual-core-092-integration/native/checkpoint-origin.json').read_bytes())['checkpoint']
        backend = NetworkBackend(resources=self.lab,
            run_root=self.lab/'work/actual-core-092-integration/parent-preflight-runs',
            official_bundle=dict(zip(('path','sha256'), bbg.REFERENCE)),
            prepared_capture=bbg.prepared_reference(),
            input_profile='xp2-lan', checkpoint=checkpoint, checkpoint_on_close=True,
            checkpoint_compatibility='xp2-reference-abi-to-selected-runtime.v1',
            lifetime_seconds=900, round_limit=2, stdout_limit_mib=128,
            execution_image_profile=self.profile.id)
        session = backend._session
        prepared = {}

        def stop_before_launch(owner, executable, worker, closure, env, captured, started):
            self.assertIs(owner, session)
            self.assertIs(captured.execution_image, self.profile)
            self.assertEqual(executable, self.lab/builds.CURRENT_STRINGS_HOST_REFERENCE[0])
            prepared.update(closure)
            return 'parent_preparation_only_no_native_launch'

        with patch('civ6_host.runtime.session_launch.launch', side_effect=stop_before_launch) as launch:
            result = session.reset()
        launch.assert_called_once()
        self.assertEqual(result, 'parent_preparation_only_no_native_launch')
        self.assertIsNone(session.process)
        self.assertEqual(prepared['pins'][self.profile.path], self.profile.image_sha256)
        self.assertTrue((session.run/'closure.json').is_file())


if __name__ == '__main__':
    unittest.main()

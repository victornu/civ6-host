"""Offline input guards; no native calls or complete-bundle success simulation.

The retained before report exercises the existing XP1 active-list reader.
Controlled contract mutations check refusals. Exact final-capture acceptance is
a separate integration check and is deliberately not claimed by this group.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import capture_profiles, gameplay_active_profiles, saved_load_profiles
from civ6_host.runtime import xp1_bundle_inputs as xp1
from civ6_host.runtime.native import native_official_bundle as bundle
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime.native import native_gameplay_empty as empty
from civ6_host.runtime.native import official_application_configuration as application
from civ6_host.runtime.paths import resource_root


BEFORE_PATH = 'work/official-capture/xp1-lan-20261030/runtime-selections-before.json'
BEFORE_SHA = 'e706c026d760c6b02defd7ab3bcd86d91d48d9303c67461955ddb52391a840ad'


class XP1InputContractTests(unittest.TestCase):
    def test_actual_xp1_database_manifest_retains_size_and_hash_guards(self):
        capture=resource_root()/'work/official-capture/xp1-lan-20261030/manifest.json'
        raw=capture.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '475f74f15dc4921b3281c9eece768afadbff924c6384f0507d3ea92413c48fcf')
        manifest=json.loads(raw)
        for side in ('before_manifest','after_manifest'):
            pin=manifest['active_database_witness'][side]
            self.assertGreater(pin['bytes'],4*1024**2)
            dependencies={}
            value=bundle._file(pin,dependencies,maximum=xp1.DATABASE_WITNESS_MAX_BYTES)
            self.assertEqual(hashlib.sha256(value).hexdigest(),pin['sha256'])
            self.assertEqual(len(dependencies),1)
            with self.assertRaisesRegex(ValueError,'Malformed or unbounded'):
                bundle._file(pin,{},maximum=4*1024**2)
            with self.assertRaisesRegex(ValueError,'Malformed or unbounded'):
                bundle._file(dict(pin,bytes=xp1.DATABASE_WITNESS_MAX_BYTES+1),{},
                             maximum=xp1.DATABASE_WITNESS_MAX_BYTES)
            with self.assertRaisesRegex(ValueError,'hash differs'):
                bundle._file(dict(pin,sha256='0'*64),{},
                             maximum=xp1.DATABASE_WITNESS_MAX_BYTES)

    def test_engine_and_executable_must_both_match_exact_xp1_sources(self):
        process = dict(exe_sha256=application.EXE_SHA256,
                       gamecore_module=dict(sha256=gameplay_active_profiles.XP1_CORE_SHA256))
        self.assertEqual(xp1.validate_process(process), gameplay_active_profiles.XP1_CORE_SHA256)
        variants = [dict(process, exe_sha256='0' * 64)]
        for core in (gameplay_active_profiles.BASE_CORE_SHA256,
                     gameplay_active_profiles.XP2_CORE_SHA256, '0' * 64):
            variants.append(dict(process, gamecore_module=dict(sha256=core)))
        for value in variants:
            with self.subTest(value=value), patch.object(xp1, 'expansion_profile') as source:
                with self.assertRaisesRegex(ValueError, 'exact source-pinned EXE and GameCore'):
                    xp1.validate_process(value)
                source.assert_not_called()

    def test_active_layout_source_failure_is_not_replaced(self):
        process = dict(exe_sha256=application.EXE_SHA256,
                       gamecore_module=dict(sha256=gameplay_active_profiles.XP1_CORE_SHA256))
        with patch.object(xp1, 'expansion_profile', side_effect=ValueError('source changed')):
            with self.assertRaisesRegex(ValueError, 'source changed'):
                xp1.validate_process(process)

    def test_ruleset_and_save_join_are_checked_before_provider_parse(self):
        manifest = dict(save=dict(source=dict(sha256='a' * 64)))
        receipt = dict(save_sha256='a' * 64,
                       content_declaration=dict(declared_ruleset='RULESET_EXPANSION_1'))
        with patch.object(application, 'extract_application_configuration',
                          return_value=(b'provider-unit-fixture', receipt)), \
             patch.object(bundle, 'parse_configuration', return_value='parsed-provider') as parse:
            self.assertEqual(bundle._configuration(b'save-unit-fixture', manifest, 'LAN',
                              expected_ruleset='RULESET_EXPANSION_1'), 'parsed-provider')
            parse.assert_called_once_with(b'provider-unit-fixture', 'LAN')
            parse.reset_mock()
            with self.assertRaisesRegex(ValueError, 'ruleset differs'):
                bundle._configuration(b'save-unit-fixture', manifest, 'LAN')
            parse.assert_not_called()
            receipt['content_declaration']['declared_ruleset'] = 'RULESET_STANDARD'
            with self.assertRaisesRegex(ValueError, 'ruleset differs'):
                bundle._configuration(b'save-unit-fixture', manifest, 'LAN',
                                      expected_ruleset='RULESET_EXPANSION_1')
            parse.assert_not_called()
            self.assertEqual(bundle._configuration(b'save-unit-fixture', manifest, 'LAN'),
                             'parsed-provider')
            parse.assert_called_once_with(b'provider-unit-fixture', 'LAN')
            parse.reset_mock()
            receipt['content_declaration']['declared_ruleset'] = 'RULESET_EXPANSION_1'
            receipt['save_sha256'] = 'b' * 64
            with self.assertRaisesRegex(ValueError, 'another save'):
                bundle._configuration(b'save-unit-fixture', manifest, 'LAN',
                                      expected_ruleset='RULESET_EXPANSION_1')
            parse.assert_not_called()

    def test_xp1_input_family_is_outside_existing_capture_and_session_profiles(self):
        self.assertEqual(set(capture_profiles.CAPTURE_MODES), {'single', 'hotseat-four', 'lan'})
        with self.assertRaises(ValueError):
            capture_profiles.profile_for_capture('xp1-lan')
        with self.assertRaisesRegex(ValueError, 'frozen official Base'):
            official.validate_profile(xp1.XP1_LAN_PROFILE)
        inputs = official.OfficialInputs(b'configuration', b'game', (), xp1.XP1_LAN_PROFILE,
                                         official_bundle=('unit-reference', 'a' * 64))
        with patch.object(bundle, 'validate_inputs') as native_input_reader:
            with self.assertRaisesRegex(ValueError, 'frozen official Base'):
                official.validate_inputs(inputs)
            native_input_reader.assert_not_called()

    def test_native_load_abi_remains_refused_before_backend_setup(self):
        profile = saved_load_profiles.profile_for_sha(gameplay_active_profiles.XP1_CORE_SHA256)
        with self.assertRaisesRegex(ValueError, 'Expansion saved Load is not admitted'):
            saved_load_profiles.require_saved_load_admission(profile)
        from civ6_host.runtime.native import native_checkpoint_load as checkpoint
        with patch.object(checkpoint.configuration._NativeBackend, '__init__') as native_setup:
            with self.assertRaisesRegex(ValueError, 'Expansion saved Load is not admitted'):
                checkpoint.NativeLoadBackend(None, None, None, None,
                    SimpleNamespace(core_sha256=gameplay_active_profiles.XP1_CORE_SHA256), None, None)
            native_setup.assert_not_called()

    def test_fixture_preparation_refuses_before_reader_or_filesystem_mutation(self):
        for admitted in (None, object()):
            with self.subTest(admitted=admitted is not None), \
                 patch.object(bundle, 'read_bundle') as read, \
                 patch.object(bundle, '_reuse_prepared_bundle') as reuse, \
                 patch.object(Path, 'mkdir') as mkdir:
                with self.assertRaisesRegex(ValueError, 'do not admit official fixture preparation'):
                    bundle.prepare_official_bundle({}, input_profile='xp1-lan',
                        output_directory='unused', _admitted_bundle=admitted)
                read.assert_not_called()
                reuse.assert_not_called()
                mkdir.assert_not_called()

    def test_xp1_raw_reader_cannot_borrow_prepared_package(self):
        from civ6_host.runtime import capture_admission
        with patch.object(capture_admission, 'try_bundle') as prepared, \
             patch.object(bundle, '_prepared_bundle_validator_digests', return_value={}), \
             patch.object(xp1, 'reader_validator_digests', return_value={}), \
             patch.object(bundle, '_manifest', side_effect=ValueError('raw-manifest-boundary')):
            with self.assertRaisesRegex(ValueError, 'raw-manifest-boundary'):
                bundle.read_bundle({}, input_profile='xp1-lan')
            prepared.assert_not_called()

    def test_base_prepared_fast_path_keeps_its_existing_identity(self):
        from civ6_host.runtime import capture_admission
        sentinel = object()
        for name, profile in (('single', official.SINGLE_PROFILE),
                              ('hotseat-four', official.HOTSEAT_FOUR_PROFILE),
                              ('lan', capture_profiles.LAN_PROFILE)):
            with self.subTest(name=name), \
                 patch.object(capture_admission, 'try_bundle', return_value=sentinel), \
                 patch.object(xp1, 'reader_validator_digests', side_effect=AssertionError('XP1 identity used')):
                self.assertIs(capture_profiles.profile_for_capture(name), profile)
                self.assertIs(bundle.read_bundle({}, input_profile=name), sentinel)

    def test_input_only_bundle_is_not_eligible_for_parent_cache_registration(self):
        candidate = bundle.PreparedBundle(('unit-reference', 'a' * 64), None, 1, Path('.'), {}, {}, {}, {})
        digests = {name: 'a' * 64 for name in bundle._PREPARED_BUNDLE_VALIDATOR_PATHS}
        with self.assertRaisesRegex(ValueError, 'malformed prepared bundle admission'):
            bundle._remember_prepared_bundle(candidate, 'xp1-lan', digests,
                                             _token=bundle._PARENT_ADMISSION_TOKEN)
        with self.assertRaisesRegex(ValueError, 'parent-admitted instance'):
            bundle._reuse_prepared_bundle(candidate, candidate.reference, 'xp1-lan')

    def test_xp1_validator_identity_includes_both_new_scope_and_existing_layout(self):
        base_before = bundle._prepared_bundle_validator_digests()
        pins = xp1.reader_validator_digests()
        for module in (xp1, gameplay_active_profiles, empty, bundle):
            path = Path(module.__file__).resolve()
            self.assertEqual(pins[str(path)], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(bundle._prepared_bundle_validator_digests(), base_before)
        self.assertNotIn('xp1_bundle_inputs.py', '\n'.join(base_before))
        self.assertNotIn('gameplay_active_profiles.py', '\n'.join(base_before))

    def test_changed_xp1_validator_or_layout_identity_refuses(self):
        for module in (xp1, gameplay_active_profiles):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as directory:
                candidate = Path(directory) / 'validator-unit-fixture.py'
                candidate.write_bytes(b'first validator bytes\n')
                with patch.object(module, '__file__', str(candidate)):
                    pins = xp1.reader_validator_digests()
                    xp1.recheck_reader_validators(pins)
                    candidate.write_bytes(b'changed validator bytes\n')
                    with self.assertRaisesRegex(ValueError, 'sources changed during admission'):
                        xp1.recheck_reader_validators(pins)

    def test_summary_keeps_base_consumer_and_execution_claims_false(self):
        value = dict(consumer_core_matches_base_proof=False,
                     content_application_success_proven=False, gameplay_execution_proven=False)
        xp1.validate_summary_scope(value)
        for name in value:
            for changed in (True, None, 0):
                with self.subTest(name=name, changed=changed), self.assertRaises(ValueError):
                    xp1.validate_summary_scope(dict(value, **{name: changed}))


class RetainedXP1EmptyWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (resource_root() / BEFORE_PATH).read_bytes()
        if hashlib.sha256(raw).hexdigest() != BEFORE_SHA:
            raise AssertionError('Retained XP1 before-witness changed')
        cls.retained = json.loads(raw)

    def test_real_retained_before_witness_keeps_false_base_proof_and_empty_xp1_state(self):
        value = copy.deepcopy(self.retained)
        before = copy.deepcopy(value)
        xp1.validate_selection_scope(value)
        identity = empty.stable_capture_identity(value['gameplay_active_list'])
        self.assertEqual(value, before)
        self.assertIs(value['gameplay_selection994']['consumer_core_matches_base_proof'], False)
        self.assertEqual(identity['source_sha256'], gameplay_active_profiles.SOURCE[1])
        self.assertEqual(identity['state']['active_count'], 0)
        self.assertIs(identity['selected_and_active_empty'], True)

    def test_claimed_base_proof_cannot_replace_xp1_witness_in_either_report(self):
        for side in ('outer', 'embedded'):
            for flag in (True, None, 0):
                value = copy.deepcopy(self.retained)
                selection = value['gameplay_selection994'] if side == 'outer' else value['gameplay_active_list']['selection']
                selection['consumer_core_matches_base_proof'] = flag
                with self.subTest(side=side, flag=flag), self.assertRaisesRegex(ValueError, 'Base consumer proof scope'):
                    xp1.validate_selection_scope(value)

    def test_nonempty_selected_records_paths_and_active_count_refuse(self):
        mutations = (
            ('selection', 'record_count', 1),
            ('selection', 'record_count', False),
            ('selection', 'records', [dict(index=0)]),
            ('selection', 'selected_paths', ['unit-negative-only.lua']),
            ('state', 'active_count', 1),
            ('state', 'active_count', False),
            ('state', 'active_list_empty', False),
            ('active', 'selected_and_active_empty', False),
        )
        for side, field, changed in mutations:
            value = copy.deepcopy(self.retained)
            target = (value['gameplay_selection994']['snapshot'] if side == 'selection'
                      else value['gameplay_active_list']['state'] if side == 'state'
                      else value['gameplay_active_list'])
            target[field] = changed
            with self.subTest(side=side, field=field, changed=changed), self.assertRaisesRegex(ValueError, 'empty selected and retained active'):
                xp1.validate_selection_scope(value)

    def test_shared_reader_still_refuses_wrong_source_state_and_uninitialized_game(self):
        mutations = (
            ('report', 'source_sha256', gameplay_active_profiles.BASE_SOURCE_SHA256),
            ('state', 'source_sha256', gameplay_active_profiles.BASE_SOURCE_SHA256),
            ('state', 'core_sha256', gameplay_active_profiles.BASE_CORE_SHA256),
            ('state', 'schema', gameplay_active_profiles.BASE_STATE_SCHEMA),
            ('state', 'game_initialized', False),
            ('state', 'loading', True),
        )
        for side, field, changed in mutations:
            report = copy.deepcopy(self.retained['gameplay_active_list'])
            (report if side == 'report' else report['state'])[field] = changed
            with self.subTest(side=side, field=field), self.assertRaises(ValueError):
                empty.stable_capture_identity(report)


if __name__ == '__main__':
    unittest.main()

"""Offline candidate-boundary tests; none call GameCore or open a process."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import tempfile
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_saved_load as boundary
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime.native.native_official_bundle import PreparedBundle
from civ6_host.runtime.saved_load_profiles import (
    XP1_CORE_SHA256, profile_for_sha, require_saved_load_admission,
)
from civ6_host.runtime.saved_load_services import SavedLoadServices


class XP1SavedLoadBoundaryTests(unittest.TestCase):
    def test_private_icu_copy_preserves_immutable_settings_and_ownership(self):
        from copy import deepcopy
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            root = Path(folder).resolve()
            source = root / 'source.dat'; source.write_bytes(b'icu-test-bytes')
            private = root / 'worker'; private.mkdir()
            copied = private / 'icu.dat'; copied.write_bytes(source.read_bytes())
            expected = dict(language='en_US', icu_data=dict(path=str(source),
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(), bytes=source.stat().st_size))
            actual = deepcopy(expected); actual['icu_data']['path'] = str(copied)
            manifest = {'localization_bootstrap': actual}
            self.assertTrue(boundary.validate_private_bootstrap(manifest, expected, private_root=private))
            actual['language'] = 'fr_FR'
            with self.assertRaisesRegex(ValueError, 'immutable settings'):
                boundary.validate_private_bootstrap(manifest, expected, private_root=private)
            actual['language'] = expected['language']; actual['icu_data']['path'] = str(source)
            with self.assertRaisesRegex(ValueError, 'canonical private'):
                boundary.validate_private_bootstrap(manifest, expected, private_root=private)
            actual['icu_data']['path'] = str(copied); copied.write_bytes(b'icu-fake-bytes')
            with self.assertRaisesRegex(ValueError, 'ICU bytes changed'):
                boundary.validate_private_bootstrap(manifest, expected, private_root=private)

    def fixture(self):
        configuration = b'configuration-fixture'
        game = b'\x05\0\0\0game-fixture'
        maps = (('MAP_SIZE', 23),)
        for name, value in (
                ('CONFIGURATION_BYTES', len(configuration)),
                ('CONFIGURATION_SHA256', hashlib.sha256(configuration).hexdigest()),
                ('GAME_BYTES', len(game)),
                ('GAME_SHA256', hashlib.sha256(game).hexdigest())):
            p = patch.object(boundary, name, value); p.start(); self.addCleanup(p.stop)
        p = patch('civ6_host.runtime.native.native_official_bundle.parse_configuration',
                  return_value=(configuration, maps))
        p.start(); self.addCleanup(p.stop)
        inputs = official.OfficialInputs(configuration, game, maps,
            boundary.XP1_LAN_PROFILE, official_bundle=boundary.REFERENCE)
        bundle = PreparedBundle(boundary.REFERENCE, inputs, 1, Path('XP1.dll'),
            {'input_profile': 'xp1-lan'}, {'source': 'a' * 64},
            dict(turn=1, width=74, height=46, player_id=0),
            {'engine': {'gamecore_sha256': XP1_CORE_SHA256}})
        return inputs, bundle

    def test_public_admission_stays_closed_with_valid_candidate_inputs(self):
        inputs, bundle = self.fixture()
        with self.assertRaisesRegex(ValueError, 'not admitted'):
            require_saved_load_admission(profile_for_sha(XP1_CORE_SHA256))
        with self.assertRaisesRegex(ValueError, 'Base'):
            official.validate_inputs(inputs)
        self.assertIs(official.validate_inputs(inputs, candidate_bundle=bundle), boundary.XP1_LAN_PROFILE)

    def test_exact_pair_owner_and_metadata_are_required(self):
        inputs, bundle = self.fixture()
        self.assertIs(boundary.validate_candidate_inputs(inputs, bundle), boundary.XP1_LAN_PROFILE)
        for invalid in (replace(inputs), replace(inputs, game=inputs.game + b'x'),
                        replace(inputs, checkpoint=('other', '0' * 64))):
            with self.assertRaises(ValueError):
                boundary.validate_candidate_inputs(invalid, bundle)
        with self.assertRaises(ValueError):
            boundary.validate_candidate_inputs(inputs, replace(bundle, initial_turn=True))
        with self.assertRaises(ValueError):
            boundary.validate_candidate_inputs(inputs, replace(bundle, reference=('other', boundary.REFERENCE[1])))

    def test_constructor_reuses_owned_input_receipt_without_replaying_raw_reader(self):
        _, bundle = self.fixture()
        profile = NS(core_sha256=XP1_CORE_SHA256, ruleset='xp1', mode='context')
        from civ6_host.runtime.native import native_official_bundle as original
        target = 'civ6_host.runtime.native.native_official_bundle.'
        validators = {key: 'a' * 64 for key in original._PREPARED_BUNDLE_VALIDATOR_PATHS}
        with patch(target + '_prepared_bundle_validator_digests', return_value=validators), \
                patch('civ6_host.runtime.xp1_bundle_inputs.reader_validator_digests', return_value={'input-code': 'b' * 64}), \
                patch(target + 'read_bundle') as read, patch(target + 'validate_fixture') as fixture:
            with self.assertRaisesRegex(ValueError, 'parent-admitted'):
                boundary.bind_candidate(bundle, profile, 'private-manifest')
            fixture.assert_not_called()
            original._remember_prepared_bundle(bundle, 'xp1-lan', validators,
                _token=original._PARENT_ADMISSION_TOKEN, _input_only=True)
            self.assertIs(boundary.bind_candidate(bundle, profile, 'private-manifest'),
                          profile_for_sha(XP1_CORE_SHA256))
            fixture.assert_called_once_with(bundle, 'private-manifest')
            read.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'input-only scope'):
                original._reuse_prepared_bundle(bundle, boundary.REFERENCE, 'xp1-lan')
            bundle.dependencies['changed'] = 'c' * 64
            with self.assertRaisesRegex(ValueError, 'contents changed'):
                boundary.bind_candidate(bundle, profile, 'private-manifest')
            self.assertEqual(fixture.call_count, 1)
            read.assert_not_called()

    def test_input_registration_invalidates_changed_validator_code(self):
        _, bundle = self.fixture()
        from civ6_host.runtime.native import native_official_bundle as original
        validators = {key: 'a' * 64 for key in original._PREPARED_BUNDLE_VALIDATOR_PATHS}
        target = 'civ6_host.runtime.native.native_official_bundle.'
        with patch(target + '_prepared_bundle_validator_digests', return_value=validators), \
                patch('civ6_host.runtime.xp1_bundle_inputs.reader_validator_digests', return_value={'input-code': 'b' * 64}) as code:
            original._remember_prepared_bundle(bundle, 'xp1-lan', validators,
                _token=original._PARENT_ADMISSION_TOKEN, _input_only=True)
            code.return_value = {'input-code': 'c' * 64}
            with self.assertRaisesRegex(ValueError, 'validator sources changed'):
                original._reuse_prepared_bundle(bundle, boundary.REFERENCE, 'xp1-lan', _input_only=True)

    def test_private_package_opt_in_keeps_public_read_closed_and_hashes_runtime_bytes(self):
        from test_capture_package import CapturePackageTests
        from civ6_host.runtime import capture_package
        fixture = CapturePackageTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.bundle.fixture['input_profile'] = 'xp1-lan'
        fixture.bundle.inputs.profile = boundary.XP1_LAN_PROFILE
        identity = {'test-runtime': 'x'}
        with patch.object(boundary, 'REFERENCE', fixture.bundle.reference), \
                patch.object(boundary, 'validate_candidate_inputs'):
            with self.assertRaisesRegex(ValueError, 'unsupported input profile'):
                capture_package.export_capture(fixture.bundle, fixture.destination,
                    source_manifest_bytes=fixture.origin_bytes, validation_identity=identity)
            reference = capture_package.export_capture(fixture.bundle, fixture.destination,
                source_manifest_bytes=fixture.origin_bytes, validation_identity=identity, _xp1_candidate=True)
            with self.assertRaisesRegex(ValueError, 'profile or turn'):
                capture_package.read_package(reference)
            manifest, _, files = capture_package.read_package(reference, _xp1_candidate=True)
            self.assertEqual(manifest['input_profile'], 'xp1-lan')
            files['gamecore_stream'].write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'file differs'):
                capture_package.read_package(reference, _xp1_candidate=True)

    def test_candidate_handoff_rejects_producer_change_before_original_input_read(self):
        from civ6_host.runtime import capture_admission, capture_package
        with patch.object(capture_admission, 'configured_reference', return_value={'path': 'package', 'sha256': 'a' * 64}), \
                patch.object(capture_admission, 'validation_identity', return_value={'runtime': 'current'}), \
                patch.object(capture_package, 'read_package', return_value=({'validation_identity': {'runtime': 'old'}}, None, None)):
            with self.assertRaisesRegex(ValueError, 'producer is not compatible'):
                capture_admission._load(_xp1_candidate=True)

    def test_worker_consumes_registered_prepared_bundle_without_raw_validation(self):
        _, bundle = self.fixture()
        from civ6_host.runtime import capture_admission
        package = {'path': 'manifest.json', 'sha256': 'a' * 64}
        with patch.object(capture_admission, 'configure') as configure, \
                patch.object(capture_admission, 'try_bundle', return_value=bundle) as consume, \
                patch('civ6_host.runtime.native.native_official_bundle.read_bundle') as raw:
            self.assertIs(boundary.consume_input_handoff(package), bundle)
            configure.assert_called_once_with(package)
            consume.assert_called_once_with(boundary.REFERENCE, input_profile='xp1-lan', _xp1_candidate=True)
            raw.assert_not_called()

    def test_prepare_reuses_context_path_and_refuses_wrong_phase_before_call(self):
        inputs, bundle = self.fixture()
        from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
        backend = NS(inputs=inputs, captured_bundle=bundle, stage='B-restored-sealed',
            topology=Mock(), host=NS(enable_tuner_unavailable_probe=Mock()),
            core=object(), context=123, emit=Mock(), profile=object(), game_flag=Mock(return_value=0))
        with patch('civ6_host.runtime.native.native_host.prepare_context', return_value={'prepared': True}) as call:
            boundary.prepare_candidate(backend, required_ownership_mode=game_configuration_hash('LAN'))
            call.assert_called_once_with(backend.core, 123, backend.emit,
                context_profile=backend.profile, null_tuner_diagnostic=True)
            self.assertEqual(backend.stage, 'prepared')
            with self.assertRaisesRegex(ValueError, 'restored LAN'):
                boundary.prepare_candidate(backend, required_ownership_mode=game_configuration_hash('LAN'))
            self.assertEqual(call.call_count, 1)

    def test_composition_reuses_actual_service_owner_and_empty_captured_selection(self):
        inputs, bundle = self.fixture()
        backend = NS(inputs=inputs, captured_bundle=bundle)
        service = SavedLoadServices.__new__(SavedLoadServices)
        service.backend = backend
        service.saved_config_sha = boundary.CONFIGURATION_SHA256
        service.saved_map_values = inputs.map_values
        service.contexts = NS(paths=(), sources={})
        service.attach = Mock()
        boundary.attach_services(backend, service)
        service.attach.assert_called_once_with(backend)
        service.contexts.paths = ('invented.lua',)
        with self.assertRaisesRegex(ValueError, 'captured SavedLoadServices'):
            boundary.attach_services(backend, service)
        self.assertEqual(service.attach.call_count, 1)

    def test_control_rejects_action_scope_and_missing_real_owners(self):
        backend = NS(check_thread=Mock(), prefix=None)
        for kwargs in ({'allow_diplomacy': True}, {'pending_round_actor': 0}):
            with self.assertRaisesRegex(ValueError, 'action/interrupted-turn'):
                boundary.control_snapshot(backend, empty=True, **kwargs)
        backend.check_thread.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'actual saved service owner'):
            boundary.control_snapshot(backend, empty=True)
        with self.assertRaises(TypeError):
            boundary.control_snapshot(backend, empty=1)

    def test_control_reads_the_real_queue_and_never_creates_an_action_queue(self):
        from civ6_host.runtime.deferred_service import DeferredService
        from civ6_host.runtime.control_input_service import ControlInputService
        from civ6_host.runtime.event_argument_service import EventArgumentService
        from civ6_host.runtime.a0_family_service import A0FamilyService
        backend = NS(check_thread=Mock(), core=object(), context=123)
        service = SavedLoadServices.__new__(SavedLoadServices)
        backend.prefix = service
        service.backend = backend
        service.host = NS()
        service.check = Mock()
        queue = DeferredService.__new__(DeferredService)
        queue.host, queue.core, queue.context = service.host, backend.core, backend.context
        queue._check = Mock()
        queue._sequence = queue.consumed_count = 0
        queue.host_notification_counter = queue.host_metadata_counter = 0
        queue.pending, queue.limit, queue._draining_empty_receivers = [], 16, False
        controller = ControlInputService.__new__(ControlInputService)
        controller.deferred, controller.local_player_id, controller._check = queue, 0, Mock()
        arguments = EventArgumentService.__new__(EventArgumentService)
        arguments.deferred, arguments.depth, arguments._check = queue, 0, Mock()
        a0 = A0FamilyService.__new__(A0FamilyService)
        a0.arguments, a0.controller_owner, a0._check = arguments, controller, Mock()
        a0.active_kind = a0._active_notification_scope = None
        a0.private_notification_profile = None
        a0._city_command_started_producing = a0._city_command_started_poisoned = False
        a0._84c1fdd6_producing = a0._84c1fdd6_poisoned = False
        service.host._a0_family_owner = a0
        service.deferred_events, service.control_inputs, service.event_arguments = queue, controller, arguments
        service.events = NS(_check=Mock(), dispatch_depth=0, script_arguments=NS(live_count=0))
        service.contexts = NS(check=Mock(), receiver=321, depth=0, lock_depth=0)
        service.map_arguments = NS(check=Mock(), live={})
        self.assertEqual(boundary.control_snapshot(backend, empty=True)['pending_count'], 0)
        self.assertFalse(hasattr(service, 'actions'))
        queue.pending.append(bytes(12)); queue._sequence = 1
        receipt = boundary.control_snapshot(backend, empty=False)
        self.assertEqual((receipt['pending_count'], receipt['sequence'], receipt['consumed']), (1, 1, 0))
        with self.assertRaisesRegex(RuntimeError, 'fully consumed'):
            boundary.control_snapshot(backend, empty=True)
        queue.host_notification_counter = 1
        with self.assertRaisesRegex(RuntimeError, 'closed notification'):
            boundary.control_snapshot(backend, empty=False)
        queue._check.assert_called()

    def test_native_roster_requires_exact_map_and_human_flags(self):
        inputs, bundle = self.fixture()
        backend = NS(inputs=inputs, captured_bundle=bundle,
                     host=NS(configured_local_player_id=0))
        roster = b'1|74|46|0|1|2|3|4|5'
        humans = b'0=1|1=0|2=0|3=0|4=0|5=0'
        receipt = boundary.validate_loaded_roster(backend, roster, humans)
        self.assertEqual(receipt['human_player_ids'], [0])
        self.assertFalse(receipt['public_session_admitted'])
        for changed_roster, changed_humans in (
                (b'1|75|46|0|1|2|3|4|5', humans),
                (roster, b'0=1|1=1|2=0|3=0|4=0|5=0')):
            with self.assertRaises(ValueError):
                boundary.validate_loaded_roster(backend, changed_roster, changed_humans)

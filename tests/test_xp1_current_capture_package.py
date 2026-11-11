"""Read the retained XP1 capture with its explicit installed image."""
from dataclasses import replace
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime.capture_package import CapturePackageError, read_package
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp1_prepared_reader_transition import PACKAGE_RELATIVE, PACKAGE_SHA256


class CurrentXP1CaptureTests(unittest.TestCase):
    def test_current_worker_refuses_cross_engine_or_unsupported_later_stage(self):
        from civ6_host.runtime.execution_images import identity
        from civ6_host.runtime.workers.run_official_postload909 import open_official_backend
        closure = dict(schema='civ6-host.xp1-saved-load-candidate.v1',
                       input_profile='xp1-lan', execution_image=identity(_XP1_PROFILE),
                       raw_only_candidate=True)
        with self.assertRaisesRegex(ValueError, 'exact expansion owner'):
            open_official_backend(dict(closure, input_profile='xp2-lan'), None, None)
        for later in ({'unit_commands_candidate': True}, {'checkpoint_on_close': True},
                      {'network_checkpoint': {}}):
            with self.subTest(later=later):
                with self.assertRaisesRegex(ValueError, 'bounded private Load or LAN session'):
                    open_official_backend(dict(closure, **later), None, None)
        with self.assertRaisesRegex(ValueError, 'capability dependencies are incomplete'):
            open_official_backend(dict(closure, observe_player_candidate=True), None, None)

    def test_installed_session_uses_current_binary_and_pinned_historical_sources(self):
        from civ6_host.runtime import stdout_transport_profiles as stdout
        from civ6_host.runtime.xp1_log_event_profile import source_dependencies
        from civ6_host.runtime.xp1_session_inputs import materialize_xp1_session_pins

        historical = source_dependencies()
        pins = materialize_xp1_session_pins(historical, _XP1_PROFILE)
        self.assertEqual(pins[_XP1_PROFILE.path], _XP1_PROFILE.image_sha256)
        self.assertTrue(any(Path(p).name == 'CivilizationVI.exe' for p in historical))
        self.assertFalse(any(Path(p).name == 'CivilizationVI.exe' for p in pins))
        recorder = next(p for p in historical if Path(p).name == 'native_events.py')
        self.assertNotEqual(pins[recorder], historical[recorder])
        profile = stdout.selected_profile(
            _XP1_PROFILE.reference_core_sha256, _XP1_PROFILE.native_host_build.executable_sha256)
        stdout.validate_profile(profile)

    def test_action_transport_checks_installed_identity_before_xp1_live_abi(self):
        from civ6_host.runtime import action_transport_profiles as transport

        core = SimpleNamespace(_name=_XP1_PROFILE.path, _handle=0x180000000,
                               _civ6_host_execution_image=_XP1_PROFILE)
        reader = object()
        with patch.object(transport, 'verify_xp1') as verify:
            transport.transport_profile(_XP1_PROFILE.reference_core_sha256, core, 1, reader)
            verify.assert_called_once_with(core._handle, 1, reader)
            core._civ6_host_execution_image = _PROFILE
            with self.assertRaisesRegex(ValueError, 'path differs'):
                transport.transport_profile(_XP1_PROFILE.reference_core_sha256, core, 1, reader)

    def test_installed_lan_readers_check_projected_sources_and_instruction_bytes(self):
        import pefile
        from civ6_host.runtime import (
            placement_inventory_profile, xp1_production_placement_profile,
            xp1_production_queue_profile, xp1_unit_attack_profile,
        )
        from civ6_host.runtime.source_verification import verification_scope
        from civ6_host.runtime.xp1_session_inputs import verify_xp1_session_pins

        image = _XP1_PROFILE
        core = SimpleNamespace(_name=image.path, _civ6_host_execution_image=image)
        profiles = (xp1_production_placement_profile, placement_inventory_profile,
                    xp1_production_queue_profile, xp1_unit_attack_profile)
        with pefile.PE(image.path, fast_load=True) as pe, verification_scope():
            base = pe.OPTIONAL_HEADER.ImageBase

            def read(address, size):
                return pe.get_data(address - base, size)

            for profile in profiles:
                family = profile.__name__.rsplit('.', 1)[1]
                with self.subTest(family=family):
                    pins = profile.source_dependencies()
                    verify_xp1_session_pins(pins, core, family=family)
                    self.assertGreater(profile.verify_live(base, read), 0)
            core._name = str(Path(image.path).with_name('unqualified.dll'))
            with self.assertRaisesRegex(ValueError, 'module differs'):
                verify_xp1_session_pins({}, core, family='placement')

    def test_found_unit_query_keeps_the_installed_xp1_source_abi(self):
        from civ6_host.runtime.found_unit_event_profiles import query_abi
        from civ6_host.runtime.native.native_found_city_event import unit_query_contract

        source = _XP1_PROFILE.reference_core_sha256
        self.assertEqual(query_abi(source, execution_image=_XP1_PROFILE), query_abi(source))
        self.assertEqual(unit_query_contract(execution_image=_XP1_PROFILE),
                         unit_query_contract(core_sha256=source))
        with self.assertRaisesRegex(ValueError, 'differs from the FoundUnit source ABI'):
            query_abi(source, execution_image=_PROFILE)

    def test_explicit_pair_reads_the_capture_with_its_reference_engine(self):
        path = resource_root() / PACKAGE_RELATIVE
        reference = dict(path=str(path), sha256=PACKAGE_SHA256)
        before = path.read_bytes()
        manifest, folder, files = read_package(
            reference, _candidate_profile='xp1-lan', execution_image=_XP1_PROFILE)
        self.assertEqual(folder, path.parent)
        self.assertEqual(manifest['engine']['sha256'], _XP1_PROFILE.reference_core_sha256)
        self.assertEqual(Path(manifest['engine']['path']), Path(_XP1_PROFILE.path))
        self.assertEqual(set(files), {
            'configuration_stream', 'gamecore_stream', 'database_configuration',
            'database_gameplay', 'database_localization', 'icu_data', 'origin_manifest',
        })
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaisesRegex(CapturePackageError, 'exact retained Rise and Fall package'):
            read_package(reference, _candidate_profile='xp1-lan', execution_image=_PROFILE)
        with self.assertRaisesRegex(CapturePackageError, 'external engine changed'):
            read_package(reference, _candidate_profile='xp1-lan')

    def test_current_xp1_handoff_preserves_producer_and_checks_worker_pins(self):
        from civ6_host.runtime import capture_admission as admission
        from civ6_host.runtime.capture_candidates import consume_input_handoff
        from civ6_host.runtime.xp1_prepared_reader_transition import PRODUCER_IDENTITY_SHA256
        from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
        from civ6_host.runtime.xp1_saved_load import REFERENCE, validate_context_identity
        reference = dict(path=str(resource_root() / PACKAGE_RELATIVE), sha256=PACKAGE_SHA256)
        origin = dict(path=REFERENCE[0], sha256=REFERENCE[1])
        with (patch.dict(os.environ), patch.object(admission, '_SETTING', admission._UNSET),
              patch.object(admission, '_STOCK_XP2_EXECUTION_ASSOCIATION', None)):
            os.environ.pop(admission.ENV, None)
            bundle = consume_input_handoff('xp1-lan', reference, official_bundle=origin,
                                           execution_image=_XP1_PROFILE)
            profile = profile_for_core(bundle.engine_path, mode='context',
                                       execution_image=_XP1_PROFILE)
            validate_context_identity(profile, bundle)
            with self.assertRaisesRegex(ValueError, 'exact captured execution pair'):
                validate_context_identity(profile, None)
            with self.assertRaisesRegex(ValueError, 'exact captured execution pair'):
                validate_context_identity(replace(profile, core_sha256=profile.source_core_sha256), bundle)
            self.assertEqual(bundle.content_profile['engine']['gamecore_sha256'],
                             _XP1_PROFILE.reference_core_sha256)
            closure = dict(input_profile='xp1-lan', official_bundle=origin, pins=dict(bundle.dependencies))
            self.assertTrue(admission.configure_prepared_closure(closure, bundle))
            receipt = admission.consume_prepared_closure(closure, _candidate_profile='xp1-lan')
            self.assertTrue(receipt['runtime_bytes_revalidated'])
            self.assertEqual(receipt['producer']['producer_identity_sha256'], PRODUCER_IDENTITY_SHA256)
            self.assertFalse(receipt['producer']['producer_identity_substituted'])
            closure['pins'][_XP1_PROFILE.path] = _XP1_PROFILE.reference_core_sha256
            with self.assertRaisesRegex(ValueError, 'XP1 worker pins differ'):
                admission.consume_prepared_closure(closure, _candidate_profile='xp1-lan')


if __name__ == '__main__':
    unittest.main()

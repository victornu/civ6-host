"""Explicit current-Core source closure for command notification families."""
from contextlib import nullcontext
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import a0_foundation_events
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime import xp1_log_event_profile
from civ6_host.runtime import found_unit_event_profiles
from civ6_host.runtime import foundation_event_profile
from civ6_host.runtime import xp1_absent_event_families
from civ6_host.runtime import xp2_history_event_profile
from civ6_host.runtime.native import native_event_e660_building_pillaged


PROFILE_ID = 'xp2-gamecore-current-092abfbb'


class XP2CommandEventSourcePinsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execution_image = select(PROFILE_ID, core_path=known_path(PROFILE_ID))

    def test_all_five_actual_providers_pin_selected_core_and_skip_capture_images(self):
        from civ6_host.runtime.a0_policy_unlock_current import CURRENT_EXE_SHA256

        providers = (
            xp1_log_event_profile,
            found_unit_event_profiles,
            foundation_event_profile,
            xp1_absent_event_families,
            xp2_history_event_profile,
        )
        for provider in providers:
            with self.subTest(provider=provider.__name__):
                pins = provider.source_dependencies(
                    core_sha256=XP2_CORE_SHA256,
                    execution_image=self.execution_image)
                self.assertEqual(pins[self.execution_image.path],
                                 self.execution_image.image_sha256)
                self.assertTrue(all(sha == CURRENT_EXE_SHA256 for path, sha in pins.items()
                                    if path.endswith('CivilizationVI.exe')))
                self.assertFalse(any(path.endswith('GameCore_XP2_FinalRelease.dll')
                                     and path != self.execution_image.path
                                     for path in pins))

    def test_e660_provenance_skip_requires_registered_profile(self):
        with self.assertRaisesRegex(ValueError, 'registered immutable identity'):
            native_event_e660_building_pillaged.source_dependencies(
                execution_image=object())
        with self.assertRaisesRegex(ValueError, 'registered immutable identity'):
            native_event_e660_building_pillaged.verify_source_evidence(
                execution_image=object())

    def test_selected_profile_flows_through_foundation_and_history_install_profiles(self):
        foundation = foundation_event_profile.event_profile(
            core_sha256=XP2_CORE_SHA256,
            execution_image=self.execution_image)
        history = xp2_history_event_profile.event_profile(
            core_sha256=XP2_CORE_SHA256,
            execution_image=self.execution_image)
        self.assertTrue(foundation.record_types_by_kind)
        self.assertTrue(history.record_types_by_kind)

    def test_occupation_consumer_and_statement_presentation_join_the_same_session_closure(self):
        from civ6_host.runtime import xp1_session_view, xp2_city_occupation_event, xp2_statement_source
        view_pins = xp1_session_view.source_dependencies(
            core_sha256=XP2_CORE_SHA256, execution_image=self.execution_image)
        command_pins = foundation_event_profile.source_dependencies(
            core_sha256=XP2_CORE_SHA256, execution_image=self.execution_image)
        self.assertIn(xp2_statement_source.PRESENTATION[1], view_pins.values())
        self.assertIn(xp2_city_occupation_event.SOURCE[1], command_pins.values())

    def test_current_building_pillage_preserves_image_at_dispatch_and_encode(self):
        codec = native_event_e660_building_pillaged
        pending = []
        owner = SimpleNamespace(core=SimpleNamespace(_civ6_host_execution_image=self.execution_image),
            context=2000, ui_cache_callbacks_enabled=True, active_kind=codec.EVENT_KIND,
            entity_listener_count=0, pending=pending, limit=16, _sequence=0,
            deferred=SimpleNamespace(_check=Mock()), empty_receiver_state=dict(codec.EMPTY_STATE),
            normalizer_transform_present=False, host_notification_counter=0, host_metadata_counter=0,
            _enqueue=pending.append, emit=Mock())
        borrowed = {0x1000: struct.pack('<ii', 11, 17), 0x2000: struct.pack('<HHI', 0, 2, 131073)}
        owner.read = lambda pointer, size: borrowed[pointer][:size]
        fields = {0x23739f42: struct.pack('<H6xQII', 1024, 0x2000, 8, 0x21000001),
                  0x8c468e3c: struct.pack('<H6xQII', 0, 0x1000, 8, 0x21000001),
                  0xa1e5a149: struct.pack('<H6xI8xI', 3, codec.SELECTOR, 0),
                  0xa1fbc372: struct.pack('<H6xI8xI', 2, 1, 0),
                  0xd6fcf3e4: struct.pack('<H6xI8xI', 2, 5, 0)}
        with (patch.object(a0_foundation_events, 'require_borrow'),
              patch.object(codec.snapshot, 'plot_snapshot',
                           return_value=nullcontext(dict(owner=0, district_id=3, flag148=0))) as snapshot):
            self.assertEqual(a0_foundation_events.dispatch_building_pillage(owner, fields), 0)
        snapshot.assert_called_once()
        self.assertEqual(snapshot.call_args.kwargs['core_sha256'], XP2_CORE_SHA256)
        self.assertEqual(struct.unpack_from('<III', pending[0]), (128, 170, 1))



if __name__ == '__main__':
    unittest.main()

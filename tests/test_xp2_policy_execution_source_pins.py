"""Actual XP2 action/policy source dependency maps under an explicit image pin."""
from types import SimpleNamespace as NS
from pathlib import Path
import unittest
from unittest.mock import patch

from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime import action_transport_profiles
from civ6_host.runtime import xp1_research_profile
from civ6_host.runtime import xp2_action_transport_source as transport_source
from civ6_host.runtime import xp2_initial_choice_source as initial_source
from civ6_host.runtime import unit_operation_ui_profile
from civ6_host.runtime import xp2_policy_source as policy
from civ6_host.runtime import xp2_policy_controls_source as controls
from civ6_host.runtime import xp2_government_source as government
from civ6_host.runtime import xp2_policy_relocation as relocation
from civ6_host.runtime import a0_policy_unlock


PROFILE_ID = 'xp2-gamecore-current-092abfbb'


class XP2PolicyExecutionSourcePinsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execution_image = select(PROFILE_ID, core_path=known_path(PROFILE_ID))

    def assert_current_core_pin(self, pins):
        self.assertEqual(pins[self.execution_image.path], self.execution_image.image_sha256)
        self.assertFalse(any(path.endswith('GameCore_XP2_FinalRelease.dll')
                             and path != self.execution_image.path for path in pins))

    def test_actual_action_source_chain_materializes_only_the_current_core_pin(self):
        calls = (
            transport_source.source_dependencies(execution_image=self.execution_image),
            action_transport_profiles.source_dependencies(
                core_sha256=XP2_CORE_SHA256, execution_image=self.execution_image),
            initial_source.source_dependencies('research', execution_image=self.execution_image),
            unit_operation_ui_profile.source_dependencies(
                core_sha256=XP2_CORE_SHA256, execution_image=self.execution_image),
            xp1_research_profile.source_dependencies(
                XP2_CORE_SHA256, execution_image=self.execution_image),
        )
        for pins in calls:
            self.assert_current_core_pin(pins)

    def test_all_four_policy_provider_maps_pass_with_real_pinned_files(self):
        maps = (
            policy.source_dependencies(execution_image=self.execution_image),
            controls.source_dependencies(execution_image=self.execution_image),
            government.source_dependencies(execution_image=self.execution_image),
            relocation.source_dependencies(execution_image=self.execution_image),
        )
        for pins in maps:
            self.assert_current_core_pin(pins)
            self.assertFalse(any(path.endswith('CivilizationVI.exe') for path in pins))
        event_pins = a0_policy_unlock.source_dependencies(execution_image=self.execution_image)
        self.assert_current_core_pin(event_pins)
        self.assertIn(a0_policy_unlock.SOURCE[1], event_pins.values())
        self.assertNotIn('CivilizationVI.exe', '\n'.join(event_pins))
        # The static producer proof retains its historical EXE attribution.
        self.assertEqual(a0_policy_unlock.source()['exe']['sha256'], a0_policy_unlock.EXE_SHA256)

    def test_legacy_event_pins_keep_the_historical_exe_and_current_runtime_refuses_it(self):
        seen = {}

        def capture(pins):
            seen.update(pins)

        with patch('civ6_host.runtime.a0_family_source.verify_pinned_files', side_effect=capture):
            pins = a0_policy_unlock.source_dependencies()
        self.assertEqual(pins, seen)
        self.assertIn(a0_policy_unlock.EXE_SHA256, pins.values())
        self.assertEqual(pins[a0_policy_unlock.source()['core']['path']], XP2_CORE_SHA256)

    def test_transport_runtime_accepts_only_the_core_selected_by_its_profile(self):
        core = NS(_handle=0x10000000, _name=str(self.execution_image.path),
                  _civ6_host_execution_image=self.execution_image)
        with patch.object(transport_source, 'verify_live', return_value={}):
            abi = action_transport_profiles.transport_profile(
                XP2_CORE_SHA256, core, 0x20000000, lambda address, size: b'\0' * size)
        self.assertIs(abi, transport_source.ABI)
        core._name = str(Path(self.execution_image.path).parent / 'foreign.dll')
        with patch.object(transport_source, 'verify_live', return_value={}):
            with self.assertRaisesRegex(ValueError, 'Core path'):
                action_transport_profiles.transport_profile(
                    XP2_CORE_SHA256, core, 0x20000000,
                    lambda address, size: b'\0' * size)


if __name__ == '__main__':
    unittest.main()

"""Current XP2 source closures retain ABI provenance but select real runtime pins."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import select
from civ6_host.runtime import combat_event_profile, district_damage_profile, improvement_change_profile


class XP2EventFamilyExecutionPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = select(
            'xp2-gamecore-current-092abfbb',
            core_path=(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI"
                       r"\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"),
        )

    def test_event_source_closures_pin_selected_core_and_keep_exe_as_provenance(self):
        current_core = str(Path(self.profile.path).resolve())
        providers = (
            improvement_change_profile.source_dependencies,
            district_damage_profile.source_dependencies,
            combat_event_profile.source_dependencies,
        )
        for provider in providers:
            with self.subTest(provider=provider.__module__):
                pins = provider(core_sha256=XP2_CORE_SHA256, execution_image=self.profile)
                self.assertEqual(pins[current_core], self.profile.image_sha256)
                self.assertFalse(any(path.lower().endswith('.exe') for path in pins))

    def test_event_profiles_remain_canonical_for_runtime_identity_checks(self):
        self.assertIs(
            improvement_change_profile.event_profile(core_sha256=XP2_CORE_SHA256,
                                                     execution_image=self.profile),
            improvement_change_profile.event_profile(core_sha256=XP2_CORE_SHA256),
        )
        self.assertIs(
            district_damage_profile.event_profile(core_sha256=XP2_CORE_SHA256,
                                                   execution_image=self.profile),
            district_damage_profile.event_profile(core_sha256=XP2_CORE_SHA256),
        )
        self.assertIs(
            combat_event_profile.event_profile(XP2_CORE_SHA256, execution_image=self.profile),
            combat_event_profile.event_profile(XP2_CORE_SHA256),
        )

    def test_bind_consumers_take_the_selected_image_from_the_real_core_owner(self):
        core = SimpleNamespace(_civ6_host_execution_image=self.profile)
        owner = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256))
        calls = []
        read = object()
        with patch('civ6_host.runtime.xp2_improvement_event_source.bind_owner',
                   side_effect=lambda *args, **kwargs: calls.append(('improvement', kwargs))):
            improvement_change_profile.bind_owner(owner, core, read)
        with patch('civ6_host.runtime.xp2_district_damage_event_source.bind_owner',
                   side_effect=lambda *args, **kwargs: calls.append(('district', kwargs))):
            district_damage_profile.bind_owner(owner, core, read)

        backend = SimpleNamespace(core=core, load_abi=owner.load_abi, check_thread=lambda: None)
        with patch('civ6_host.runtime.xp2_combat_event_source.bind_owner',
                   side_effect=lambda *args, **kwargs: calls.append(('combat', kwargs))), \
             patch('civ6_host.runtime.xp1_world_text_profile.bind_owner',
                   side_effect=lambda *args, **kwargs: calls.append(('world_text', kwargs))), \
             patch('civ6_host.runtime.combat_event_profile.event_profile', return_value=object()):
            combat_event_profile.bind_owner(backend, core, read)

        self.assertEqual([name for name, _ in calls],
                         ['improvement', 'district', 'combat', 'world_text'])
        self.assertTrue(all(kwargs.get('execution_image') is self.profile for _, kwargs in calls))


if __name__ == '__main__':
    unittest.main()

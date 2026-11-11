"""XP2 checkpoint source closure selects runtime bytes without changing its ABI."""
from pathlib import Path
import unittest

from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE, select
from civ6_host.runtime.xp1_checkpoint_profile import save_abi, source_dependencies, verify_source


class XP2CheckpointExecutionPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = select(
            'xp2-gamecore-current-092abfbb',
            core_path=(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI"
                       r"\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"),
        )

    def test_current_runtime_pin_is_separate_from_checkpoint_abi_reference(self):
        pins = source_dependencies(core_sha256=XP2_CORE_SHA256, execution_image=self.profile)
        core_path = str(Path(self.profile.path).resolve())
        self.assertEqual(pins[core_path], self.profile.image_sha256)
        self.assertFalse(any(path.lower().endswith('.exe') for path in pins))

        proof = verify_source(XP2_CORE_SHA256)
        self.assertEqual(proof['image']['sha256'], XP2_CORE_SHA256)
        self.assertEqual(save_abi(XP2_CORE_SHA256).core_sha256, XP2_CORE_SHA256)
        self.assertNotEqual(self.profile.image_sha256, save_abi(XP2_CORE_SHA256).core_sha256)

    def test_xp1_checkpoint_sources_require_the_registered_xp1_image(self):
        with self.assertRaisesRegex(ValueError, 'registered installed XP1 session image'):
            source_dependencies(core_sha256=XP1_CORE_SHA256, execution_image=self.profile)
        pins = source_dependencies(core_sha256=XP1_CORE_SHA256, execution_image=_XP1_PROFILE)
        self.assertEqual(pins[_XP1_PROFILE.path], _XP1_PROFILE.image_sha256)
        self.assertEqual(save_abi(XP1_CORE_SHA256).core_sha256, _XP1_PROFILE.reference_core_sha256)


if __name__ == '__main__':
    unittest.main()

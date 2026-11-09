"""Current shared-DLL identity and selected interface receipt; no DLL loading."""
from dataclasses import replace
from pathlib import Path
import unittest
import inspect

from civ6_host.runtime.native.native_shared_dependency_profiles import (
    ACTUAL_IMAGE_SHA256,
    INTERFACE_REFERENCE_SHA256,
    profile_for_shared_dependencies,
)


class NativeSharedDependencyProfilesTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(
            r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI"
            r"\Base\Binaries\Win64Steam"
        )

    def test_explicit_current_reference_pair_verifies_only_three_pinned_files(self):
        profile = profile_for_shared_dependencies(
            self.directory,
            actual_image_sha256=ACTUAL_IMAGE_SHA256,
            interface_reference_sha256=INTERFACE_REFERENCE_SHA256,
        )
        paths = profile.verify_files()
        self.assertEqual(set(paths), {
            'DatabaseDLL_FinalRelease.dll',
            'Localization_FinalRelease.dll',
            'HavokScript_FinalRelease.dll',
        })
        self.assertEqual(profile.havok_shim_rva_mismatches, 48)
        self.assertEqual(profile.havok_export_rvas['?lua_gc@@YAHPEAUlua_State@@HH@Z'], 0x149d0)
        self.assertEqual(profile.havok_export_rvas['?lua_close@@YAXPEAUlua_State@@@Z'], 0x3a380)
        self.assertEqual(profile.havok_export_rvas['?lua_newstate@@YAPEAUlua_State@@P6APEAXPEAX0_K1@Z0@Z'], 0x3aba0)
        self.assertEqual(profile.localization_export_rvas[
            '?Initialize@Localization@@YA_NPEB_SPEAVIDatabaseConnection1@Database@@PEBD_NPEAVILocalizationLogger@1@@Z'
        ], 0x192f0)
        self.assertEqual(profile.database_interface['selected_slots_match_reference'], True)

    def test_unknown_or_aliased_image_pairs_refuse(self):
        for actual, reference in (
            ('0' * 64, INTERFACE_REFERENCE_SHA256),
            (ACTUAL_IMAGE_SHA256, ACTUAL_IMAGE_SHA256),
            (ACTUAL_IMAGE_SHA256, '0' * 64),
        ):
            with self.subTest(actual=actual, reference=reference):
                with self.assertRaises(ValueError):
                    profile_for_shared_dependencies(
                        self.directory,
                        actual_image_sha256=actual,
                        interface_reference_sha256=reference,
                    )

    def test_directory_and_profile_identity_are_rechecked(self):
        profile = profile_for_shared_dependencies(
            self.directory,
            actual_image_sha256=ACTUAL_IMAGE_SHA256,
            interface_reference_sha256=INTERFACE_REFERENCE_SHA256,
        )
        with self.assertRaisesRegex(ValueError, 'directory'):
            replace(profile, directory=self.directory.parent).verify_files()
        with self.assertRaisesRegex(ValueError, 'pair changed'):
            replace(profile, actual_image_sha256=INTERFACE_REFERENCE_SHA256).verify_files()

    def test_current_dependency_consumers_require_an_explicit_profile_argument(self):
        from civ6_host.runtime.native.native_havok import bind
        from civ6_host.runtime.native.native_script_kernel import bind_kernel
        from civ6_host.runtime.native.native_localization import initialize_localization, finish_localization
        for function in (bind, bind_kernel, initialize_localization, finish_localization):
            self.assertIn('shared_dependency_profile', inspect.signature(function).parameters)


if __name__ == '__main__':
    unittest.main()

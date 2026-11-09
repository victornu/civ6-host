"""Static identity and correspondence tests; no native image is loaded."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from unittest.mock import patch

from civ6_host.runtime import execution_images
from civ6_host.runtime.execution_images import (
    ExecutionImageVerificationError,
    from_identity,
    identity,
    known_path,
    runtime_source_pins,
    select,
    source_dependencies,
    verify,
)
from civ6_host.runtime.native.native_core_context_profiles import (
    NativeCoreContextProfile,
    require_executable_profile,
)


PROFILE_ID = 'xp2-gamecore-current-092abfbb'
CORE_PATH = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI"
    r"\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"
)
CURRENT_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
REFERENCE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'


class ExecutionImageTests(unittest.TestCase):
    def test_explicit_selection_keeps_current_image_and_reference_abi_distinct(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        self.assertEqual(profile.id, PROFILE_ID)
        self.assertEqual(profile.path, CORE_PATH)
        self.assertEqual(profile.image_sha256, CURRENT_SHA256)
        self.assertEqual(profile.image_size_bytes, 12941080)
        self.assertEqual(profile.reference_core_sha256, REFERENCE_SHA256)
        self.assertNotEqual(profile.image_sha256, profile.reference_core_sha256)
        self.assertTrue(profile.executable)
        self.assertEqual(profile.state, 'candidate_for_bounded_native_trial')
        self.assertFalse(profile.missing_groups)
        with self.assertRaises(FrozenInstanceError):
            profile.path = 'C:\\other\\GameCore.dll'

    def test_path_and_profile_selection_are_exact(self):
        for wrong_id, path in (
            ('xp2', CORE_PATH),
            (PROFILE_ID, CORE_PATH + '.old'),
            (PROFILE_ID, ''),
        ):
            with self.subTest(profile_id=wrong_id, path=path):
                with self.assertRaises(ValueError):
                    select(wrong_id, core_path=path)
        self.assertEqual(str(known_path(PROFILE_ID)), CORE_PATH)
        with self.assertRaises(ValueError):
            known_path(CURRENT_SHA256)

    def test_pinned_capture_groups_sum_to_manifest_and_are_all_matched(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        self.assertEqual(profile.correspondence_manifest_sha256,
                         '34e6ddc19ae70cd9c2b910bb6f6af0b629dee1ad6f7ddd654250989b225e9bd3')
        self.assertEqual(profile.correspondence_manifest_spans, 1727)
        self.assertEqual(profile.matching_correspondence_spans, 1727)
        self.assertEqual(sum(row.captured_spans for row in profile.source_proofs), 1727)
        self.assertTrue(all(row.captured_spans == row.matching_spans
                            for row in profile.source_proofs))
        self.assertEqual(profile.covered_groups, tuple(row.group for row in profile.source_proofs))
        self.assertEqual(profile.covered_groups, (
            'native_context_factory_destructor',
            'native_context_constructor_and_vtable',
            'saved_load_dispatch_xp2',
            'saved_load_prepare_xp2',
            'saved_load_active_list_xp2',
            'xp2_context_initialization',
            'xp2_prepare_services',
            'xp2_configuration_provider',
            'xp2_configuration_copy',
        ))

    def test_identity_round_trip_reselects_only_the_local_pin(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        payload = identity(profile)
        self.assertEqual(set(payload), {
            'profile_id', 'image_sha256', 'reference_core_sha256', 'path',
        })
        self.assertIs(from_identity(payload), profile)
        for changed in (
            {**payload, 'image_sha256': REFERENCE_SHA256},
            {**payload, 'reference_core_sha256': CURRENT_SHA256},
            {**payload, 'unexpected': 'value'},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    from_identity(changed)

    def test_source_dependency_pins_include_only_core_dependencies_and_proofs(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        pins = source_dependencies(profile)
        self.assertEqual(len(pins), 54)  # Images, proof inputs, exact overlay executable and staged sources.
        self.assertEqual(pins[CORE_PATH], CURRENT_SHA256)
        self.assertNotIn('CivilizationVI.exe', '\n'.join(pins))
        self.assertTrue(any(path.endswith('civ6rl-native-python.exe') for path in pins))
        self.assertFalse(any('\\civ6-host\\src\\' in path for path in pins))
        self.assertTrue(all(path.startswith('C:\\') for path in pins))
        self.assertIn(
            'C:\\Users\\victo\\Documents\\Codex\\2026-10-10\\l\\outputs\\civ6-rl-lab'
            '\\work\\bbg751-turn-source-scope\\war-confirmation\\'
            'current-build-capture-comparison-v1.json', pins)
        self.assertIn(
            'C:\\Users\\victo\\Documents\\Codex\\2026-10-10\\l\\outputs\\civ6-rl-lab'
            '\\work\\bbg751-turn-source-scope\\shared-dependencies\\'
            'current-shared-dependency-interfaces-v1.json', pins)

    def test_runtime_source_pins_only_translate_the_exact_admitted_core_pair(self):
        original = {CORE_PATH: REFERENCE_SHA256, 'C:\\proof.json': 'a' * 64}
        no_admission = runtime_source_pins(original)
        self.assertEqual(no_admission, original)
        self.assertIsNot(no_admission, original)

        profile = select(PROFILE_ID, core_path=CORE_PATH)
        translated = runtime_source_pins(original, execution_image=profile)
        self.assertEqual(translated, {CORE_PATH: CURRENT_SHA256, 'C:\\proof.json': 'a' * 64})
        self.assertEqual(original[CORE_PATH], REFERENCE_SHA256)
        self.assertIsNot(translated, original)

    def test_runtime_source_pins_reject_unadmitted_or_conflicting_core_identity(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        with self.assertRaisesRegex(ValueError, 'exact reference-image pair'):
            runtime_source_pins({CORE_PATH: '0' * 64}, execution_image=profile)
        self.assertEqual(runtime_source_pins({'C:\\proof.json': 'a' * 64},
                                             execution_image=profile),
                         {'C:\\proof.json': 'a' * 64})
        with self.assertRaisesRegex(ValueError, 'canonical registered profile'):
            runtime_source_pins({CORE_PATH: REFERENCE_SHA256}, execution_image=replace(
                profile, path=CORE_PATH + '.elsewhere'))
        with self.assertRaisesRegex(ValueError, 'canonical alias'):
            runtime_source_pins({CORE_PATH: REFERENCE_SHA256,
                                 CORE_PATH.lower(): REFERENCE_SHA256},
                                execution_image=profile)

    def test_exact_dependencies_and_overlay_admit_only_a_bounded_trial(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        self.assertEqual(profile.missing_groups, ())
        self.assertEqual(profile.matched_interface_groups, (
            'database_exports_ordinals_and_consumed_vtable_slots_match_reference',
            'localization_selected_exports_and_host_locale_bridge_rvas_match_reference',
        ))
        self.assertEqual(profile.matched_build_groups, (
            'havok_current_rva_thread_import_overlay_and_tonumber_guards_exact_build',
        ))
        self.assertEqual(len(profile.shared_dependencies), 3)
        receipt = verify(profile)
        self.assertTrue(receipt.executable)
        self.assertEqual(receipt.admission_scope, 'bounded_native_trial')
        self.assertFalse(receipt.game_qualified)
        self.assertFalse(receipt.native_execution_performed)
        self.assertEqual(receipt.missing_groups, ())
        self.assertEqual(receipt.native_host_executable_sha256,
                         '106018516854f1e28d34814f24e08d3834eee0272f143b3daba0d4a5c571bc5e')
        self.assertEqual(receipt.native_host_build_record_sha256,
                         '391f78fcb31aff04b3c552122fb1143e3380fdca94ad6bbdb639ffbf63d50fa3')
        self.assertEqual(receipt.native_host_build_manifest_sha256,
                         '7e67158f208f19cd9d29c36ce940a8c6082096ae750bf925884a63ce51f7b303')
        self.assertEqual(receipt.verified_groups, (
            *profile.covered_groups,
            *profile.matched_interface_groups,
            *profile.matched_build_groups,
        ))
        self.assertIn('semantic behavior is not qualified', ' '.join(receipt.limitations))

    def test_verification_rechecks_current_core_hash_and_size(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        for disk_identity in (
            ('0' * 64, 12941080),
            (CURRENT_SHA256, 12941079),
        ):
            with self.subTest(disk_identity=disk_identity):
                original = execution_images._hash_file_and_size
                def changed_core_only(path):
                    if execution_images.os.path.normcase(path) == execution_images.os.path.normcase(CORE_PATH):
                        return disk_identity
                    return original(path)
                with patch.object(execution_images, '_hash_file_and_size',
                                  side_effect=changed_core_only):
                    with self.assertRaisesRegex(ExecutionImageVerificationError,
                                                'pinned source/image SHA|byte size'):
                        verify(profile)

    def test_empty_context_or_forged_profile_cannot_create_ready_status(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        empty_context_copy = replace(
            profile, covered_groups=(), source_proofs=(), missing_groups=(),
            matched_interface_groups=(), matched_build_groups=(),
            correspondence_manifest_spans=0, matching_correspondence_spans=0,
        )
        self.assertEqual(empty_context_copy.state, 'blocked')
        self.assertFalse(empty_context_copy.executable)
        with self.assertRaisesRegex(ExecutionImageVerificationError,
                                   'registered immutable identity'):
            verify(empty_context_copy)
        self.assertTrue(profile.executable)
        self.assertEqual(profile.state, 'candidate_for_bounded_native_trial')

    def test_additional_required_group_is_explicitly_refused(self):
        profile = select(PROFILE_ID, core_path=CORE_PATH)
        with self.assertRaises(ExecutionImageVerificationError) as caught:
            verify(profile, required_groups=('future_saved_restore_caller',))
        self.assertIn('future_saved_restore_caller', caught.exception.missing_groups)

    def test_context_profile_keeps_execution_and_reference_hashes_and_trial_guard(self):
        image = select(PROFILE_ID, core_path=CORE_PATH)
        profile = NativeCoreContextProfile(
            ruleset='xp2', mode='context', core_path=Path(CORE_PATH),
            core_sha256=CURRENT_SHA256, create_context_rva=1,
            destroy_context_rva=2, context_vtable_rva=3,
            context_vtable_bytes=b'\0' * 64, initialized_getter_rva=4,
            initialized_getter_bytes=b'\x90',
            shared_dependency_directory=Path(CORE_PATH).parent,
            dependency_sha256={}, reference_core_sha256=REFERENCE_SHA256,
            execution_image=image,
        )
        self.assertEqual(profile.core_sha256, CURRENT_SHA256)
        self.assertEqual(profile.source_core_sha256, REFERENCE_SHA256)
        self.assertTrue(profile.executable)
        require_executable_profile(profile)

        legacy = replace(profile, core_sha256=REFERENCE_SHA256,
                         reference_core_sha256=None, execution_image=None)
        self.assertEqual(legacy.source_core_sha256, REFERENCE_SHA256)
        self.assertTrue(legacy.executable)
        require_executable_profile(legacy)


if __name__ == '__main__':
    unittest.main()

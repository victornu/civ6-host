"""Static identity and correspondence tests; no native image is loaded."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
    profile_for_core,
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
    def test_installed_base_context_binds_the_exact_image_for_the_saved_load_trial(self):
        profile_id = 'base-gamecore-current-160875db'
        path = known_path(profile_id)
        selected = select(profile_id, core_path=path)
        self.assertIs(from_identity(identity(selected)), selected)
        self.assertIs(execution_images.select_pair(
            selected.image_sha256, selected.reference_core_sha256), selected)
        build = selected.native_host_build
        self.assertEqual(build.profile_id, 'base-current-havok-201979')
        pinned = source_dependencies(selected)
        self.assertEqual(pinned[str(Path(selected.path))], selected.image_sha256)
        self.assertIn(build.executable_sha256, pinned.values())
        self.assertIn(build.build_record_sha256, pinned.values())
        self.assertIn(execution_images._BASE_LOAD_BODIES.sha256, pinned.values())
        self.assertTrue(selected.executable)
        trial = verify(selected)
        self.assertEqual(trial.admission_scope, 'bounded_native_trial')
        self.assertIn('base_native_load_services', trial.verified_groups)
        self.assertFalse(trial.native_execution_performed)
        self.assertFalse(trial.game_qualified)
        with self.assertRaises(ValueError):
            execution_images.select_pair(selected.image_sha256, REFERENCE_SHA256)
        with self.assertRaisesRegex(ValueError, 'without retained execution identity'):
            profile_for_core(path, mode='context')

        context = profile_for_core(path, mode='context', execution_image=selected)
        self.assertEqual(context.ruleset, 'base')
        self.assertEqual(context.core_sha256, selected.image_sha256)
        self.assertEqual(context.source_core_sha256, selected.reference_core_sha256)
        self.assertEqual((context.create_context_rva, context.destroy_context_rva,
                          context.context_vtable_rva, context.initialized_getter_rva),
                         (0x58dd30, 0x58dd40, 0x79e020, 0x42e3a0))
        self.assertEqual(dict(context.dependency_sha256),
                         {row.name: row.sha256 for row in selected.shared_dependencies})
        self.assertEqual(context.shared_dependency_profile.actual_image_sha256, selected.image_sha256)
        self.assertFalse(context.executable)
        with self.assertRaisesRegex(ValueError, 'scoped to the official Init/Load worker'):
            require_executable_profile(context)
        init = profile_for_core(path, mode='init', execution_image=selected)
        self.assertTrue(init.executable)
        require_executable_profile(init)
        with self.assertRaisesRegex(ValueError, 'required static correspondence'):
            verify(selected, required_groups=('base_gameplay_qualified',))

    def test_installed_base_hotseat_can_opt_in_to_the_guarded_memory_budget(self):
        from civ6_host.runtime.base_capture_inputs import REFERENCE
        from civ6_host.runtime.native.native_hotseat_session import NativeHotseatActionSession

        options = dict(execution_image_profile='base-gamecore-current-160875db',
                       official_bundle=dict(zip(('path', 'sha256'), REFERENCE)))
        default = NativeHotseatActionSession(**options)
        guarded = NativeHotseatActionSession(**options, reduced_memory_reserve=True)
        self.assertEqual(default.memory_reserve_mib, 2048)
        self.assertEqual(guarded.memory_reserve_mib, 1280)
        with self.assertRaisesRegex(ValueError, 'explicit installed Base hotseat'):
            NativeHotseatActionSession(reduced_memory_reserve=True)
        with self.assertRaisesRegex(ValueError, 'explicit installed Base hotseat'):
            NativeHotseatActionSession(**options, reduced_memory_reserve=1)
        with self.assertRaisesRegex(ValueError, 'exact execution profile and capture'):
            NativeHotseatActionSession(execution_image_profile=options['execution_image_profile'],
                                       reduced_memory_reserve=True)

        guarded.reset_started = time.perf_counter()
        required = 1792 * 1024**2
        guarded.win = Mock()
        guarded.win.memory.return_value = {'private_bytes': 48 * 1024**2}
        available = {'physical_available_bytes': required, 'commit_available_bytes': required}
        guarded.win.available.return_value = available
        guarded._check_reset_resources('before_spawn')
        self.assertTrue(guarded.reset_resource_samples[-1]['admitted'])
        available['physical_available_bytes'] -= 1
        with self.assertRaisesRegex(RuntimeError, '512 MiB child budget plus 1280 MiB'):
            guarded._check_reset_resources('before_spawn')
        self.assertFalse(guarded.reset_resource_samples[-1]['admitted'])

    def test_installed_base_ui_receipt_binds_parent_worker_and_decision_owner(self):
        from civ6_host.runtime.base_capture_inputs import REFERENCE
        from civ6_host.runtime.native.native_hotseat_session import NativeHotseatActionSession
        from civ6_host.runtime.native.native_ui_profile import PROFILE_ID, gate_admitted
        from civ6_host.runtime.workers.official_hotseat_worker923 import ui_profile_admission

        reference = dict(zip(('path', 'sha256'), REFERENCE))
        image = execution_images._BASE_PROFILE
        session = NativeHotseatActionSession(official_bundle=reference, ui_profile=PROFILE_ID,
                                             execution_image_profile=image.id)
        closure = dict(pins={}, official_bundle=reference, input_profile=session.input_profile,
                       execution_image=identity(image))
        session._configure_closure(closure)
        receipt = ui_profile_admission(closure)
        self.assertEqual(receipt, session.ui_profile_admission)
        self.assertEqual(receipt['execution_image'], identity(image))
        self.assertFalse(receipt['runtime_context_sources_verified'])
        self.assertIn(receipt['evidence']['forced_turn_delivery']['path'], closure['pins'])
        owner = SimpleNamespace(profile=SimpleNamespace(execution_image=image),
                                ui_profile_admission=receipt)
        for name in ('force_end_turn', 'city_citizens', 'city_focus', 'production_queue', 'plot_purchase'):
            self.assertTrue(gate_admitted(owner, name))
        owner.profile.execution_image = execution_images._XP1_PROFILE
        with self.assertRaisesRegex(ValueError, 'belongs to another execution image'):
            gate_admitted(owner, 'force_end_turn')
        forged = dict(closure, execution_image={**identity(image), 'image_sha256': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'serialized execution-image identity differs'):
            ui_profile_admission(forged)

    def test_installed_base_public_witness_requires_the_exact_hotseat_core_and_host(self):
        from civ6_host.runtime.base_capture_inputs import REFERENCE, bind_worker
        from civ6_host.runtime.native.native_hotseat_session import NativeHotseatActionSession
        from civ6_host.runtime.native.native_public_objective_witness import PROOF, ROOT, sources_from_closure

        reference = dict(zip(('path', 'sha256'), REFERENCE))
        image = execution_images._BASE_PROFILE
        session = NativeHotseatActionSession(official_bundle=reference, execution_image_profile=image.id,
                                             public_objective_players=[0, 1, 2, 3])
        closure = dict(pins={}, official_bundle=reference, input_profile=session.input_profile)
        bind_worker(closure, SimpleNamespace(execution_image=image))
        session._configure_closure(closure)
        self.assertEqual(closure['public_objective_players'], [0, 1, 2, 3])
        sources = sources_from_closure(closure)
        self.assertEqual(sources, session.public_continuity_sources)
        self.assertEqual(sources['gamecore_sha256'], image.image_sha256)
        self.assertEqual(sources['host_sha256'], image.native_host_build.executable_sha256)

        forged = dict(closure, stdout_transport={**closure['stdout_transport'], 'host_sha256': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'Core and host pair'):
            sources_from_closure(forged)
        forged = dict(closure, pins=dict(closure['pins']))
        forged['pins'].pop(str(PROOF.relative_to(ROOT)))
        with self.assertRaisesRegex(ValueError, 'getter proof in the closure'):
            sources_from_closure(forged)

    def test_installed_base_founding_uses_the_pinned_unit_query_abi(self):
        from civ6_host.runtime.found_unit_event_profiles import query_abi
        from civ6_host.runtime.native.native_found_city_event import unit_query_contract

        image = execution_images._BASE_PROFILE
        base = query_abi(image.reference_core_sha256)
        self.assertEqual(query_abi(image.reference_core_sha256, execution_image=image), base)
        self.assertEqual(unit_query_contract(execution_image=image), unit_query_contract())
        with self.assertRaisesRegex(ValueError, 'differs from the FoundUnit source ABI'):
            query_abi(image.reference_core_sha256, execution_image=replace(image))
        with self.assertRaisesRegex(ValueError, 'differs from the FoundUnit source ABI'):
            query_abi(execution_images._XP1_PROFILE.reference_core_sha256, execution_image=image)

    def test_installed_base_input_preparation_keeps_both_cores_and_checks_the_producer(self):
        selected = select('base-gamecore-current-160875db',
                          core_path=known_path('base-gamecore-current-160875db'))
        comparison = execution_images.verify_base_context_correspondence(selected)
        original_exe = comparison['executable']['reference']
        original_core = comparison['reference_core']
        producer = {
            'gamecore_module': {'path': selected.path, 'sha256': original_core['sha256']},
            'exe_sha256': original_exe['sha256'],
        }
        installed, pins = execution_images.base_capture_execution(selected, producer)
        self.assertEqual(pins[str(installed)], selected.image_sha256)
        self.assertEqual(pins[original_core['path']], original_core['sha256'])
        self.assertEqual(pins[original_exe['path']], original_exe['sha256'])
        with self.assertRaisesRegex(ValueError, 'does not match the reviewed reference'):
            execution_images.base_capture_execution(selected, {**producer, 'exe_sha256': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'exact registered installed Base image'):
            execution_images.base_capture_execution(replace(selected), producer)
        dependency = selected.shared_dependencies[0]
        hash_file = execution_images._hash_file_and_size

        def changed_dependency(path):
            return ('0' * 64, 0) if path == dependency.path else hash_file(path)

        with patch.object(execution_images, '_hash_file_and_size', side_effect=changed_dependency):
            with self.assertRaisesRegex(ValueError, 'Installed Base shared dependency changed'):
                execution_images.base_capture_execution(selected, producer)

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

    def test_retained_base_capture_inputs_bind_exact_pair_and_preserve_content(self):
        from civ6_host.runtime import base_capture_inputs

        selected = select('base-gamecore-current-160875db',
                          core_path=known_path('base-gamecore-current-160875db'))
        reference = base_capture_inputs.REFERENCE
        bundle = base_capture_inputs.read_bundle(reference, execution_image=selected, input_profile='hotseat-four')
        self.assertIs(bundle.execution_image, selected)
        self.assertEqual(bundle.dependencies[str(bundle.engine_path)], selected.image_sha256)
        self.assertEqual(bundle.inputs.official_bundle, reference)
        self.assertEqual(bundle.content_profile['engine']['gamecore_sha256'], selected.reference_core_sha256)
        self.assertEqual(set(bundle.fixture['databases']), {'configuration', 'gameplay', 'localization'})
        self.assertTrue(bundle.content_profile['gameplay_scripts']['selected_and_active_empty'])
        self.assertEqual((bundle.initial_turn, bundle.expected_readback['player_id']), (1, 0))
        with self.assertRaisesRegex(ValueError, 'exact retained hotseat capture'):
            base_capture_inputs.read_bundle(reference, execution_image=selected, input_profile='lan')

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

    def test_installed_xp1_selects_typed_log_bridge_and_keeps_archived_stdout_readable(self):
        from civ6_host.runtime.source_build_identity import (
            CURRENT_STRINGS_HOST_REFERENCE,
            CURRENT_UNSIGNED_LOG_HOST_REFERENCE,
        )
        from civ6_host.runtime.stdout_transport_profiles import XP1_SOURCE, selected_profile

        profile_id = 'xp1-gamecore-current-63c17d9'
        profile = select(profile_id, core_path=known_path(profile_id))
        receipt = verify(profile)
        self.assertEqual(receipt.native_host_executable_sha256, CURRENT_UNSIGNED_LOG_HOST_REFERENCE[1])
        self.assertFalse(receipt.native_execution_performed)
        self.assertFalse(receipt.game_qualified)
        for _, digest in (CURRENT_STRINGS_HOST_REFERENCE, CURRENT_UNSIGNED_LOG_HOST_REFERENCE):
            stdout = selected_profile(profile.reference_core_sha256, digest)
            self.assertEqual((stdout['host_sha256'], stdout['source_sha256']), (digest, XP1_SOURCE[1]))
        with self.assertRaisesRegex(ValueError, 'No qualified stdout source'):
            selected_profile(profile.reference_core_sha256, '0' * 64)

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

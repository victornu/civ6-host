"""Selected current Core flows through the saved session source collectors."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime import xp1_session_view, xp1_session_result, xp1_session_admission


PROFILE_ID = 'xp2-gamecore-current-092abfbb'


class XP2SessionViewExecutionImageSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execution_image = select(PROFILE_ID, core_path=known_path(PROFILE_ID))

    def assert_selected_core_only(self, pins):
        self.assertEqual(pins[self.execution_image.path], self.execution_image.image_sha256)
        self.assertFalse(any(path.endswith('GameCore_XP2_FinalRelease.dll')
                             and path != self.execution_image.path for path in pins))
        self.assertFalse(any(path.endswith('CivilizationVI.exe') for path in pins))

    def test_session_view_closure_uses_one_selected_core_and_no_exe_pin(self):
        pins = xp1_session_view.source_dependencies(
            core_sha256=XP2_CORE_SHA256,
            execution_image=self.execution_image)
        self.assert_selected_core_only(pins)
        self.assertGreater(len(pins), 200)

    def test_result_and_admission_collectors_accept_the_same_profile(self):
        result = xp1_session_result.source_dependencies(
            core_sha256=XP2_CORE_SHA256,
            execution_image=self.execution_image)
        self.assert_selected_core_only(result)
        admission = xp1_session_admission.source_dependencies(
            execution_image=self.execution_image)
        self.assertFalse(any(path.endswith('GameCore_XP2_FinalRelease.dll')
                             or path.endswith('CivilizationVI.exe') for path in admission))

    def test_collectors_reject_noncanonical_profiles(self):
        with self.assertRaisesRegex(ValueError, 'registered immutable identity'):
            xp1_session_view.source_dependencies(
                core_sha256=XP2_CORE_SHA256, execution_image=object())
        with self.assertRaisesRegex(ValueError, 'registered immutable identity'):
            xp1_session_admission.source_dependencies(execution_image=object())

    def test_late_production_binders_forward_core_execution_image(self):
        from civ6_host.runtime import xp2_production_queue_source as queue
        from civ6_host.runtime import xp2_production_placement_source as placement
        from civ6_host.runtime import xp2_placement_inventory_source as inventory
        from civ6_host.runtime import xp2_world_input_source as world
        from civ6_host.runtime.native.native_official_load import OfficialLoadBackend

        core=SimpleNamespace(_handle=0x180000000,
                             _civ6_host_execution_image=self.execution_image)
        read=lambda address,size:b'\0'*size
        owner=object.__new__(OfficialLoadBackend)
        owner.core=core
        owner.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
        owner.runtime=SimpleNamespace(read=read)
        owner.destroyed=False;owner.poisoned=False
        owner.inputs=object();owner.captured_bundle=SimpleNamespace(inputs=owner.inputs)
        owner.check_thread=lambda:None

        with patch('civ6_host.runtime.captured_saved_load.validate_candidate_inputs'), \
             patch('civ6_host.runtime.xp1_production_profile.bind_owner'), \
             patch.object(queue,'source_dependencies') as queue_pins, \
             patch.object(queue,'verify_live',return_value=1):
            queue.bind_owner(owner,core,read)
        queue_pins.assert_called_once_with(execution_image=self.execution_image)

        queue_receipt=object();world_receipt=object()
        with patch.object(queue,'bind_owner',return_value=queue_receipt), \
             patch.object(world,'bind_owner',return_value=world_receipt), \
             patch.object(placement,'source_dependencies') as placement_pins, \
             patch.object(placement,'verify_live',return_value=1):
            placement.bind_owner(owner,core,read)
        placement_pins.assert_called_once_with(
            XP2_CORE_SHA256,execution_image=self.execution_image)

        placement_receipt=object()
        with patch.object(placement,'bind_owner',return_value=placement_receipt), \
             patch.object(inventory,'source_dependencies') as inventory_pins, \
             patch.object(inventory,'verify_live',return_value=1):
            inventory.bind_owner(owner,core,read)
        inventory_pins.assert_called_once_with(
            XP2_CORE_SHA256,execution_image=self.execution_image)


if __name__ == '__main__':
    unittest.main()

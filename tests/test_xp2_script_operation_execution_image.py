"""Stop before allocation/native requests while checking the two profile seams."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_script_operation as operation
from civ6_host.runtime.execution_images import select, known_path


class StopBeforeNative(Exception):
    pass


class ScriptOperationImageTests(unittest.TestCase):
    def setUp(self):
        self.image = select('xp2-gamecore-current-092abfbb',
                            core_path=known_path('xp2-gamecore-current-092abfbb'))

    def test_submission_forwards_its_core_owned_image_before_allocations(self):
        core = SimpleNamespace(_handle=0x180000000, _civ6_host_execution_image=self.image)
        read = Mock()
        with patch.object(operation, '_script_parameters', side_effect=StopBeforeNative) as parameters:
            with self.assertRaises(StopBeforeNative):
                operation.submit_script_operation(core, 0x10000, 0, {b'OnStart':b'OnStart'}, read=read)
        self.assertIs(parameters.call_args.kwargs['execution_image'], self.image)
        read.assert_not_called()

    def test_parameter_builder_forwards_the_image_to_the_real_source_boundary(self):
        with patch.object(operation, 'verify_live', side_effect=StopBeforeNative) as verify:
            with self.assertRaises(StopBeforeNative):
                with operation._script_parameters(0x180000000, {b'OnStart':b'OnStart'},
                        read=Mock(), execution_image=self.image):
                    self.fail('Native parameter allocation must not be reached')
        self.assertIs(verify.call_args.kwargs['execution_image'], self.image)

    def test_shared_player_operation_preserves_the_core_owned_image(self):
        from civ6_host.runtime.native.native_player_operation_request import request_player_operation
        core = SimpleNamespace(_handle=0x180000000, _civ6_host_execution_image=self.image)
        with patch('civ6_host.runtime.xp1_research_profile.verify_live',
                   side_effect=StopBeforeNative) as verify:
            with self.assertRaises(StopBeforeNative):
                request_player_operation(core, 0x10000, 0, 1, {1:2}, read=Mock(),
                    core_sha256=self.image.reference_core_sha256)
        self.assertIs(verify.call_args.kwargs['execution_image'], self.image)


if __name__ == '__main__':
    unittest.main()

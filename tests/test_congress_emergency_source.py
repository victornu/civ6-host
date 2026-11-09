"""The real pinned source cache must preserve the emergency-call guard."""
import unittest
from unittest.mock import patch

from civ6_host.runtime import configuration_profiles
from civ6_host.runtime.execution_images import known_path,select
from civ6_host.runtime.native import native_world_congress_active_effects as native


class EmergencySourceTests(unittest.TestCase):
    def test_real_frozen_source_is_admitted_but_an_added_indirect_call_is_not(self):
        original=configuration_profiles._source
        proof=original(native.UI_SOURCE)
        self.assertIsInstance(proof['direct_dependency_inventory']['other_indirect_calls'],tuple)
        name='xp2-gamecore-current-092abfbb'
        image=select(name,core_path=known_path(name))
        self.assertIn(native.UI_SOURCE[1],native.source_dependencies(execution_image=image).values())
        changed=dict(proof)
        changed['direct_dependency_inventory']=dict(proof['direct_dependency_inventory'],
            other_indirect_calls=(dict(call_rva='0xa3170',operand='unknown fixture call'),))
        def source(reference):
            return changed if reference==native.UI_SOURCE else original(reference)
        with patch.object(configuration_profiles,'_source',side_effect=source):
            with self.assertRaisesRegex(ValueError,'emergency UI registration source differs'):
                native.source_dependencies(execution_image=image)
        self.assertIs(original(native.UI_SOURCE),proof)
        self.assertEqual(proof['direct_dependency_inventory']['other_indirect_calls'],())


if __name__=='__main__':unittest.main()

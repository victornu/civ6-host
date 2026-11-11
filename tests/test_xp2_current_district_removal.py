import unittest

from civ6_host.runtime import xp2_district_removed_current as district
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row


class CurrentDistrictRemovalTests(unittest.TestCase):
    def test_current_profile_keeps_native_district_removal_record(self):
        profile = district.event_profile(_PROFILE)
        self.assertEqual(profile.record_types_by_kind[district.KIND], frozenset((0xa0,)))
        self.assertEqual(profile.record_sizes[0xa0], 128)
        row = resolve_empty_receiver_row(0xa0, execution_image=_PROFILE)
        self.assertEqual(row['event_name'], 'GameCoreEvent::DistrictRemovedFromMap')
        self.assertEqual(row['handler_va'], '0x1400d9230')
        self.assertEqual(row['record_sizes'], {128})

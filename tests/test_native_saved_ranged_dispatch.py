from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.native import native_saved_city_shot as city
from civ6_host.runtime.native import native_saved_district_shot as district


class NativeSavedRangedDispatchTests(unittest.TestCase):
    def test_both_adapters_refuse_a_changed_shooter_catalogue_before_submission(self):
        for adapter, kind in ((city, 'city'), (district, 'district')):
            with self.subTest(kind=kind):
                owner = SimpleNamespace(**{f'explicit_{kind}_shots': {'turn': 21}})
                prefix = SimpleNamespace(runtime=Mock())
                action = dict(kind=f'{kind}_range_attack', plot_id=1, x=1, y=0,
                              **{f'{kind}_id': 7})
                before = dict(width=8, height=8)
                with patch.object(adapter, 'catalog', return_value={'turn': 22}) as catalog, \
                     patch.object(adapter, 'compare_own_cities'):
                    with self.assertRaisesRegex(RuntimeError, f'Stale {kind}-shot decision'):
                        adapter.apply(owner, prefix, action, 22, before, player_id=1)
                catalog.assert_called_once_with(prefix, 22, player_id=1)
                prefix.runtime.evaluate_text.assert_not_called()

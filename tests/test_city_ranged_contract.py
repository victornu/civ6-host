import unittest

from civ6_host.contracts import city_ranged


class CityRangedContractTests(unittest.TestCase):
    def test_city_and_district_can_share_a_numeric_id_and_target(self):
        scope = dict(player_id=1, turn=22, width=6, height=4)
        city = dict(city_id=7, district_id=4, x=1, y=1, available=True, targets=[15])
        district = dict(district_id=7, city_id=7, type_index=2, x=2, y=1,
                        complete=True, banner_eligible=True, available=True, targets=[15])
        cities = dict(scope, cities=[city])
        districts = dict(scope, districts=[district])
        observation = dict(scope, cities=[dict(id=7, x=1, y=1)])
        city_ranged.city_compare_own_cities(cities, observation)
        city_ranged.district_compare_own_cities(districts, observation)
        self.assertEqual(city_ranged.city_actions(cities),
                         [dict(kind='city_range_attack', city_id=7, plot_id=15, x=3, y=2)])
        self.assertEqual(city_ranged.district_actions(districts),
                         [dict(kind='district_range_attack', district_id=7, plot_id=15, x=3, y=2)])
        with self.assertRaisesRegex(ValueError, 'Foreign district-shot catalogue'):
            city_ranged.district_validate_catalog(districts, 0, 22)
        with self.assertRaisesRegex(ValueError, 'bypasses banner'):
            city_ranged.district_actions(dict(scope, districts=[dict(district, banner_eligible=False)]))

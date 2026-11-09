"""Portable governor catalogue validation and action projection."""
from copy import deepcopy
import unittest

from civ6_host.contracts import governors


class GovernorContractTests(unittest.TestCase):
    def catalogue(self):
        return dict(
            player_id=0, current_game_turn=17, points_obtained=2,
            points_spent=1, can_appoint=True, titles_considered=True,
            governors=[
                dict(index=4, hash=0x12345678, appointed=False,
                     can_ever_appoint=True, can_promote=False,
                     assignment_open=False, turns_to_establish=5, status=None,
                     promotions=[], assignment_targets=[]),
                dict(index=9, hash=0x87654321, appointed=True,
                     can_ever_appoint=False, can_promote=False,
                     assignment_open=True, turns_to_establish=6,
                     status=dict(neutralized_turns=0, established=False,
                                 turns_to_establish=6, turns_on_site=2,
                                 assigned_city=dict(owner=0, city_id=12),
                                 govern_city_state=False, can_assign_to_major_civ=False),
                     promotions=[
                         dict(index=2, hash=0xaabbccdd, owned=False,
                              can_earn=True, hidden=True, base_ability=False,
                              level=1),
                         dict(index=5, hash=0xbbccddee, owned=False,
                              can_earn=False, hidden=False, base_ability=False,
                              level=2),
                     ],
                     assignment_targets=[
                         dict(owner=0, city_id=12, can_assign=False),
                         dict(owner=0, city_id=31, can_assign=True),
                         dict(owner=19, city_id=8, can_assign=True),
                     ]),
            ],
        )

    def test_inaccessible_catalogue_is_empty_but_empty_catalogue_can_offer_consider(self):
        self.assertEqual(governors.actions(None), [])
        empty = self.catalogue()
        empty.update(governors=[], titles_considered=False)
        self.assertEqual(governors.actions(empty), [dict(kind='consider_governor_titles')])
        empty['titles_considered'] = True
        self.assertEqual(governors.actions(empty), [])

    def test_disabled_visible_rows_are_not_actions_and_native_order_is_preserved(self):
        catalogue = self.catalogue()
        before = deepcopy(catalogue)
        self.assertEqual(governors.validate_catalogue(catalogue, 0, 17), before)
        self.assertEqual(governors.actions(catalogue), [
            dict(kind='appoint_governor', governor_index=4, governor_hash=0x12345678),
            dict(kind='promote_governor', governor_index=9, governor_hash=0x87654321,
                 promotion_index=2, promotion_hash=0xaabbccdd),
            dict(kind='assign_governor', governor_index=9, governor_hash=0x87654321,
                 city_owner=0, city_id=31),
            dict(kind='assign_governor', governor_index=9, governor_hash=0x87654321,
                 city_owner=19, city_id=8),
        ])
        self.assertEqual(catalogue, before)

    def test_hidden_earnable_promotion_survives_false_can_promote_and_negative_points(self):
        catalogue = self.catalogue()
        catalogue['can_appoint'] = False
        catalogue['points_obtained'] = -2
        catalogue['points_spent'] = 7
        offered = governors.actions(catalogue)
        self.assertEqual([a['kind'] for a in offered],
                         ['promote_governor', 'assign_governor', 'assign_governor'])
        self.assertEqual(offered[0]['promotion_hash'], 0xaabbccdd)
        self.assertNotIn('label', offered[0])

    def test_non_appointable_visible_type_is_not_an_action(self):
        catalogue = self.catalogue()
        catalogue['governors'][0]['can_ever_appoint'] = False
        self.assertNotIn('appoint_governor',
                         [action['kind'] for action in governors.actions(catalogue)])

    def test_base_level_zero_and_owned_rows_are_not_ui_gestures(self):
        catalogue = self.catalogue()
        catalogue['governors'][1]['promotions'] = [
            dict(index=10, hash=10, owned=False, can_earn=True, hidden=False,
                 base_ability=True, level=1),
            dict(index=11, hash=11, owned=False, can_earn=True, hidden=False,
                 base_ability=False, level=0),
            dict(index=12, hash=12, owned=True, can_earn=True, hidden=False,
                 base_ability=False, level=2),
        ]
        self.assertEqual(governors.actions(catalogue), [
            dict(kind='appoint_governor', governor_index=4, governor_hash=0x12345678),
            dict(kind='assign_governor', governor_index=9, governor_hash=0x87654321,
                 city_owner=0, city_id=31),
            dict(kind='assign_governor', governor_index=9, governor_hash=0x87654321,
                 city_owner=19, city_id=8),
        ])

    def test_catalogue_provenance_flags_ranges_and_exact_fields(self):
        valid = self.catalogue()
        governors.validate_catalogue(valid, 0, 17)
        invalids = [
            (dict(valid, player_id=True), 0, 17),
            (valid, 1, 17),
            (valid, 0, 18),
            (dict(valid, unexpected=1), 0, 17),
            (dict(valid, points_obtained=True), 0, 17),
            (dict(valid, can_appoint=1), 0, 17),
            (dict(valid, points_spent=0x80000000), 0, 17),
        ]
        for value, player_id, turn in invalids:
            with self.subTest(value=value), self.assertRaises(ValueError):
                governors.validate_catalogue(value, player_id, turn)

    def test_duplicate_governor_promotion_and_city_identities_are_rejected(self):
        catalogue = self.catalogue()
        catalogue['governors'].append(deepcopy(catalogue['governors'][0]))
        with self.assertRaises(ValueError):
            governors.validate_catalogue(catalogue, 0, 17)

        catalogue = self.catalogue()
        catalogue['governors'][1]['promotions'].append(
            dict(index=7, hash=0xaabbccdd, owned=False, can_earn=False,
                 hidden=False, base_ability=False, level=2))
        with self.assertRaises(ValueError):
            governors.validate_catalogue(catalogue, 0, 17)

        catalogue = self.catalogue()
        catalogue['governors'][1]['assignment_targets'].append(
            dict(owner=0, city_id=31, can_assign=False))
        with self.assertRaises(ValueError):
            governors.validate_catalogue(catalogue, 0, 17)

    def test_appointment_status_coherence_and_strict_bool_types(self):
        catalogue = self.catalogue()
        catalogue['governors'][0]['status'] = dict(
            neutralized_turns=0, established=False, turns_to_establish=0,
            turns_on_site=0, assigned_city=None, govern_city_state=False,
            can_assign_to_major_civ=False)
        with self.assertRaises(ValueError):
            governors.validate_catalogue(catalogue, 0, 17)

        catalogue = self.catalogue()
        catalogue['governors'][1]['promotions'][0]['hidden'] = 1
        with self.assertRaises(ValueError):
            governors.validate_catalogue(catalogue, 0, 17)

        catalogue = self.catalogue()
        catalogue['governors'][1]['promotions'][0]['level'] = True
        with self.assertRaises(ValueError):
            governors.validate_catalogue(catalogue, 0, 17)

    def test_actions_keep_distinct_index_hash_and_owner_city_values(self):
        action = dict(kind='assign_governor', governor_index=9,
                      governor_hash=0x87654321, city_owner=19, city_id=8)
        self.assertIs(governors.validate_action(action), action)
        promote = dict(kind='promote_governor', governor_index=9,
                       governor_hash=0x87654321, promotion_index=2,
                       promotion_hash=0xaabbccdd)
        self.assertIs(governors.validate_action(promote), promote)

    def test_action_shapes_and_excess_parameters_are_rejected(self):
        for action in (
                dict(kind='appoint_governor', governor_index=True, governor_hash=1),
                dict(kind='promote_governor', governor_index=0, governor_hash=1,
                     promotion_index=0, promotion_hash=-1),
                dict(kind='assign_governor', governor_index=0, governor_hash=1,
                     city_owner=0, city_id=0, extra=1),
                dict(kind='consider_governor_titles', governor_index=0),
                dict(kind='assign_governor', governor_index=0, governor_hash=1,
                     city_owner=True, city_id=0),
                dict(kind='unknown'),
        ):
            with self.subTest(action=action), self.assertRaises(ValueError):
                governors.validate_action(action)


if __name__ == '__main__':
    unittest.main()

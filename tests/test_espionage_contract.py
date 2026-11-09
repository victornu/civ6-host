"""Portable espionage boundaries, own-player provenance, and offered choices."""

from copy import deepcopy
import unittest

from civ6_host.contracts import espionage


def mission(mode='start', x=2, y=1, unit_id=9):
    return dict(kind='spy_mission', unit_id=unit_id,
                operation_type='UNITOPERATION_SPY_STEAL_TECH_BOOST',
                operation_hash=0xfedcba98, mode=mode, x=x, y=y, plot_id=y * 3 + x)


def offer(action, **kwargs):
    value = dict(action=action, turns=-1, success_percent=-1,
                 failure_percent=-1, captured_or_killed_percent=-1)
    value.update(kwargs)
    return value


def catalogue():
    return dict(
        schema=espionage.SCHEMA, player_id=2, turn=73, width=3, height=2,
        capacity=3,
        spies=[dict(unit_id=9, name='Aline', level=1, x=0, y=0,
                    operation=-1, turns_remaining=-1)],
        captured=[dict(owner=2, captor=6, name_index=4, name='Marcel', level=2),
                  dict(owner=5, captor=2, name_index=4, name='René', level=None)],
        off_map=[dict(name='Louise', level=1, return_turn=76, x=2, y=1)],
        history=[dict(name='Aline', level=1, operation=7, completion_turn=72,
                      initial_result=1, escape_result=-1, city_name='Paris', plot_id=5,
                      loot_info=25)],
        offers=[
            offer(dict(kind='spy_travel', unit_id=9, city_owner=6, city_id=0xffffffff,
                       x=2, y=1), turns=3),
            offer(mission(), turns=8, success_percent=75, failure_percent=20,
                  captured_or_killed_percent=5),
            offer(mission('counterspy', 0, 0)),
            offer(mission('renew', 0, 0)),
            offer(dict(kind='spy_cancel', unit_id=9)),
            offer(dict(kind='spy_escape', unit_id=9, district_index=4)),
        ],
    )


def observation():
    return dict(player_id=2, turn=73, width=3, height=2,
                units=[dict(id=9, owner=2, x=0, y=0),
                       dict(id=31, owner=2, x=2, y=1)])


class EspionageContractTests(unittest.TestCase):
    def test_every_action_branch_and_player_visible_prisoner_direction(self):
        value = catalogue()
        before = deepcopy(value)
        self.assertIs(espionage.validate_catalogue(value, 2, 73), value)
        self.assertIs(espionage.compare_own(value, observation()), value)
        result = espionage.actions(value)
        self.assertEqual(result, [row['action'] for row in value['offers']])
        for action in result:
            self.assertIs(espionage.validate_action(action, 3, 2), action)
        self.assertEqual(value, before)
        self.assertTrue(all(type(fields) is frozenset
                            for fields in espionage.ACTION_FIELDS.values()))
        self.assertEqual(set(espionage.ACTION_FIELDS),
                         {'spy_travel', 'spy_mission', 'spy_cancel', 'spy_escape'})

    def test_action_projection_preserves_order_and_does_not_alias(self):
        value = catalogue()
        value['offers'].reverse()
        actions = espionage.actions(value)
        self.assertEqual(actions[0], dict(kind='spy_escape', unit_id=9, district_index=4))
        actions[0]['district_index'] = 99
        actions.clear()
        self.assertEqual(value['offers'][0]['action']['district_index'], 4)
        self.assertEqual(len(value['offers']), 6)

    def test_absent_and_empty_catalogues_offer_nothing(self):
        self.assertEqual(espionage.actions(None), [])
        value = catalogue()
        value.update(capacity=0, spies=[], captured=[], off_map=[], history=[], offers=[])
        self.assertEqual(espionage.actions(value), [])
        espionage.compare_own(value, observation())

    def test_distinct_mission_modes_and_target_plots_survive(self):
        value = catalogue()
        value['offers'] = [offer(mission(mode, x, 0))
                           for mode in ('start', 'counterspy', 'renew') for x in (0, 1)]
        self.assertEqual(len(espionage.actions(value)), 6)
        self.assertEqual({action['mode'] for action in espionage.actions(value)},
                         {'start', 'counterspy', 'renew'})

    def test_duplicate_actions_are_rejected_even_with_different_quotes(self):
        value = catalogue()
        value['offers'].append(offer(deepcopy(value['offers'][1]['action']), turns=99))
        with self.assertRaises(ValueError):
            espionage.validate_catalogue(value, 2, 73)

    def test_history_is_native_order_and_signed_state_is_preserved(self):
        value = catalogue()
        first = deepcopy(value['history'][0])
        second = dict(first, completion_turn=71, initial_result=-0x80000000,
                      escape_result=0x7fffffff, plot_id=-1, operation=-1, level=-1,
                      loot_info=-0x80000000)
        first['loot_info'] = 0x7fffffff
        value['history'] = [first, second]
        value['spies'][0]['turns_remaining'] = -0x80000000
        value['off_map'][0]['return_turn'] = -2
        espionage.validate_catalogue(value, 2, 73)
        value['history'].reverse()
        espionage.validate_catalogue(value, 2, 73)
        self.assertEqual(value['history'][0]['plot_id'], -1)

    def test_player_turn_and_schema_provenance_are_strict(self):
        for key, bad in (('schema', 'civ6-host.espionage.v2'), ('schema', True),
                         ('player_id', 3), ('player_id', True), ('turn', 74),
                         ('turn', 73.0)):
            value = catalogue()
            value[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)
        for pid, turn in ((True, 73), (64, 73), (-1, 73), (2, True),
                          (2, -1), (2, 0x80000000)):
            with self.subTest(pid=pid, turn=turn), self.assertRaises(ValueError):
                espionage.validate_catalogue(catalogue(), pid, turn)

    def test_exact_shapes_reject_missing_extra_and_wrong_container_types(self):
        for name in ('spies', 'captured', 'off_map', 'history', 'offers'):
            for mutation in ('extra', 'missing', 'wrong_type'):
                value = catalogue()
                row = value[name][0]
                if mutation == 'extra':
                    row['private_native_pointer'] = 17
                elif mutation == 'missing':
                    row.pop(next(iter(row)))
                else:
                    value[name][0] = []
                with self.subTest(name=name, mutation=mutation), self.assertRaises(ValueError):
                    espionage.validate_catalogue(value, 2, 73)
        for value in ([], {}, dict(catalogue(), unexpected=1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                espionage.actions(value)

    def test_geometry_capacity_and_list_limits(self):
        for key, bad in (('width', 0), ('height', 0), ('width', 16385),
                         ('height', True), ('capacity', True), ('capacity', -1),
                         ('capacity', 0x80000000)):
            value = catalogue()
            value[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)
        value = catalogue()
        value.update(width=129, height=128)
        with self.assertRaises(ValueError):
            espionage.validate_catalogue(value, 2, 73)
        for name in ('spies', 'captured', 'off_map', 'history', 'offers'):
            value = catalogue()
            value[name] = [None] * (11 if name == 'history' else 4097)
            with self.subTest(name=name), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)
            value[name] = ()
            with self.subTest(name=name, shape='tuple'), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)

    def test_empty_catalogue_accepts_maximum_map_area(self):
        value = catalogue()
        value.update(width=16384, height=1, spies=[], captured=[], off_map=[],
                     history=[], offers=[])
        espionage.validate_catalogue(value, 2, 73)
        espionage.validate_action(dict(kind='spy_cancel', unit_id=0xffffffff))

    def test_spy_identity_scalar_coordinates_and_name_boundaries(self):
        for key, bad in (('unit_id', True), ('unit_id', -1), ('unit_id', 0x100000000),
                         ('level', True), ('level', -1), ('x', 3), ('y', -1),
                         ('operation', -2), ('operation', 0x80000000),
                         ('turns_remaining', -0x80000001), ('turns_remaining', True),
                         ('name', 123), ('name', 'é' * 16385)):
            value = catalogue()
            value['spies'][0][key] = bad
            with self.subTest(key=key, bad=repr(bad)[:50]), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)
        value = catalogue()
        value['spies'][0]['name'] = 'é' * 16384
        espionage.validate_catalogue(value, 2, 73)

    def test_foreign_prisoners_and_malformed_captured_identity_are_rejected(self):
        for updates in (dict(owner=3, captor=4), dict(owner=True), dict(captor=64),
                        dict(name_index=-1), dict(name_index=True), dict(level=True)):
            value = catalogue()
            value['captured'][0].update(updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)

    def test_enemy_captive_levels_are_hidden_and_own_captive_levels_required(self):
        for level in (0, 1, False, -1, 'unknown'):
            value = catalogue()
            value['captured'][1]['level'] = level
            with self.subTest(level=level), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)
        value = catalogue()
        value['captured'][0]['level'] = None
        with self.assertRaises(ValueError):
            espionage.validate_catalogue(value, 2, 73)

    def test_off_map_and_history_boundaries(self):
        for collection, key, bad in (
                ('off_map', 'return_turn', 0x80000000), ('off_map', 'level', True),
                ('off_map', 'return_turn', -1),
                ('off_map', 'x', -1), ('off_map', 'y', 2), ('off_map', 'name', None),
                ('history', 'operation', 0x80000000), ('history', 'completion_turn', True),
                ('history', 'initial_result', -0x80000001), ('history', 'escape_result', 1.0),
                ('history', 'plot_id', -2), ('history', 'plot_id', 6),
                ('history', 'loot_info', True), ('history', 'loot_info', 0x80000000),
                ('history', 'city_name', None)):
            value = catalogue()
            value[collection][0][key] = bad
            with self.subTest(collection=collection, key=key, bad=bad), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)

    def test_duplicate_roster_and_history_rows_are_rejected(self):
        for name in ('spies', 'captured', 'off_map', 'history'):
            value = catalogue()
            value[name].append(deepcopy(value[name][0]))
            with self.subTest(name=name), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)
        value = catalogue()
        value['captured'].append(dict(value['captured'][0], captor=7, name='Other'))
        with self.assertRaises(ValueError):
            espionage.validate_catalogue(value, 2, 73)

    def test_all_offers_including_escape_must_refer_to_roster(self):
        for index in range(len(catalogue()['offers'])):
            value = catalogue()
            value['offers'][index]['action']['unit_id'] = 31
            with self.subTest(index=index), self.assertRaises(ValueError):
                espionage.validate_catalogue(value, 2, 73)

    def test_quote_unknown_values_and_percentage_bounds(self):
        value = catalogue()
        value['offers'][0].update(turns=0, success_percent=0, failure_percent=100,
                                  captured_or_killed_percent=-1)
        espionage.validate_catalogue(value, 2, 73)
        for key in ('turns', 'success_percent', 'failure_percent', 'captured_or_killed_percent'):
            for bad in (-2, True, 1.0, 0x80000000 if key == 'turns' else 101):
                value = catalogue()
                value['offers'][0][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    espionage.validate_catalogue(value, 2, 73)

    def test_action_envelopes_are_exact_and_boolean_ids_are_rejected(self):
        for valid in [row['action'] for row in catalogue()['offers']]:
            invalids = [dict(valid, unexpected=1), dict(valid, unit_id=True),
                        dict(valid, unit_id=-1), dict(valid, unit_id=0x100000000)]
            missing = dict(valid)
            missing.pop('unit_id')
            invalids.append(missing)
            for action in invalids:
                with self.subTest(action=action), self.assertRaises(ValueError):
                    espionage.validate_action(action, 3, 2)
        for action in (None, [], {}, dict(kind=[]), dict(kind='spy_unknown', unit_id=9)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                espionage.validate_action(action)

    def test_action_specific_ranges_and_mission_geometry(self):
        cases = [
            (catalogue()['offers'][0]['action'], 'city_owner', True),
            (catalogue()['offers'][0]['action'], 'city_owner', 64),
            (catalogue()['offers'][0]['action'], 'city_id', -1),
            (catalogue()['offers'][0]['action'], 'x', 3),
            (mission(), 'operation_type', 'SPY_STEAL_TECH_BOOST'),
            (mission(), 'operation_type', True), (mission(), 'operation_hash', True),
            (mission(), 'operation_hash', -1), (mission(), 'mode', 'travel'),
            (mission(), 'mode', []), (mission(), 'plot_id', 4),
            (mission(), 'plot_id', -1), (mission(), 'y', 2),
            (catalogue()['offers'][-1]['action'], 'district_index', -1),
            (catalogue()['offers'][-1]['action'], 'district_index', True),
        ]
        for valid, key, bad in cases:
            action = dict(valid, **{key: bad})
            with self.subTest(action=action), self.assertRaises(ValueError):
                espionage.validate_action(action, 3, 2)
        for width, height in ((True, 2), (3, 0), (16385, 2)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                espionage.validate_action(dict(kind='spy_cancel', unit_id=9), width, height)

    def test_standalone_mission_validation_does_not_assume_map_width(self):
        action = mission(x=2, y=1)
        self.assertIs(espionage.validate_action(action), action)
        self.assertIs(espionage.validate_action(action, 3, 2), action)
        with self.assertRaises(ValueError):
            espionage.validate_action(action, 4, 2)
        for updates in (dict(plot_id=16384), dict(x=16384), dict(y=16384)):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                espionage.validate_action(dict(action, **updates))
        for dimensions in ((None, 2), (3, None)):
            with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                espionage.validate_action(action, *dimensions)

    def test_observation_must_match_owner_position_provenance_and_map(self):
        for updates in (dict(player_id=3), dict(turn=74), dict(width=4),
                        dict(height=True), dict(units=[])):
            obs = dict(observation(), **updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                espionage.compare_own(catalogue(), obs)
        for updates in (dict(owner=3), dict(owner=True), dict(x=1), dict(y=1),
                        dict(x=False), dict(id=31)):
            obs = observation()
            obs['units'][0].update(updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                espionage.compare_own(catalogue(), obs)
        for obs in (None, {}, dict(observation(), units=[{}])):
            with self.subTest(obs=obs), self.assertRaises(ValueError):
                espionage.compare_own(catalogue(), obs)


if __name__ == '__main__':
    unittest.main()

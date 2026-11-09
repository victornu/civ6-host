"""Portable completion identity and offered renewal/dismissal contracts."""
from copy import deepcopy
import unittest

from civ6_host.contracts import spy_completion


def offer(action, **quote):
    return dict(action=action, **dict(dict(turns=-1, success_percent=-1,
        failure_percent=-1, captured_or_killed_percent=-1), **quote))


def catalogue(*, renew=True):
    identity = dict(event_sequence=19, mission_id=7)
    current = dict(**identity, name='Ada', level=1, operation=12,
        completion_turn=71, initial_result=1, escape_result=-1,
        city_name='Paris', plot_id=5, loot_info=25)
    offers = [offer(dict(kind='spy_completion_dismiss', **identity))]
    if renew:
        offers.insert(0, offer(dict(kind='spy_renew', unit_id=9, **identity,
            operation_type='UNITOPERATION_SPY_STEAL_TECH_BOOST',
            operation_hash=0xfedcba98, x=2, y=1, plot_id=5), turns=6,
            success_percent=75, failure_percent=20, captured_or_killed_percent=5))
    return dict(schema=spy_completion.SCHEMA, player_id=2, turn=73,
                width=3, height=2, current=current, offers=offers)


def observation():
    # A counterspy can be at the city center while its mission targets another
    # district. Neither current position nor movement points decide renewal.
    return dict(player_id=2, turn=73, width=3, height=2,
                units=[dict(id=9, owner=2, x=0, y=0, moves=0)])


class SpyCompletionContractTests(unittest.TestCase):
    def test_current_event_and_exact_action_order_are_preserved(self):
        value = catalogue()
        original = deepcopy(value)
        self.assertIs(spy_completion.validate_catalogue(value, 2, 73), value)
        self.assertIs(spy_completion.compare_own(value, observation()), value)
        projected = spy_completion.actions(value)
        self.assertEqual(projected, [row['action'] for row in value['offers']])
        for action in projected:
            self.assertIs(spy_completion.validate_action(action, 3, 2), action)
        self.assertEqual(value, original)
        self.assertEqual(set(spy_completion.ACTION_FIELDS), {'spy_renew', 'spy_completion_dismiss'})
        self.assertTrue(all(type(fields) is frozenset for fields in spy_completion.ACTION_FIELDS.values()))
        projected[0]['unit_id'] = 22
        projected.clear()
        self.assertEqual(value['offers'][0]['action']['unit_id'], 9)

    def test_absent_or_empty_current_event_never_creates_choices(self):
        self.assertEqual(spy_completion.actions(None), [])
        value = catalogue()
        value.update(current=None, offers=[])
        self.assertEqual(spy_completion.actions(value), [])
        self.assertIs(spy_completion.compare_own(value, observation()), value)
        value['offers'] = catalogue()['offers']
        with self.assertRaises(ValueError):
            spy_completion.validate_catalogue(value, 2, 73)

    def test_dismissal_is_required_once_and_renewal_is_optional_at_most_once(self):
        value = catalogue(renew=False)
        value['current']['plot_id'] = -1
        self.assertEqual(len(spy_completion.actions(value)), 1)
        for rows in ([], [catalogue()['offers'][0]],
                     [catalogue(renew=False)['offers'][0]] * 2,
                     catalogue()['offers'] + [catalogue()['offers'][0]]):
            value = catalogue()
            value['offers'] = deepcopy(rows)
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                spy_completion.validate_catalogue(value, 2, 73)

    def test_each_action_requires_the_exact_current_event_identity(self):
        for index in (0, 1):
            for key in ('event_sequence', 'mission_id'):
                value = catalogue()
                value['offers'][index]['action'][key] += 1
                with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                    spy_completion.validate_catalogue(value, 2, 73)

    def test_renewal_targets_the_historical_plot_without_own_coordinate_or_move_filter(self):
        value = catalogue()
        self.assertIs(spy_completion.compare_own(value, observation()), value)
        unit = observation()
        unit['units'][0].update(x=1, y=0, moves=0)
        self.assertIs(spy_completion.compare_own(value, unit), value)
        for plot_id in (-1, 4):
            changed = deepcopy(value)
            changed['current']['plot_id'] = plot_id
            with self.subTest(plot_id=plot_id), self.assertRaises(ValueError):
                spy_completion.validate_catalogue(changed, 2, 73)

    def test_renewal_requires_own_observed_unit_and_matching_name_when_present(self):
        for units in ([], [dict(id=10, owner=2)], [dict(id=9, owner=3)],
                      [dict(id=9, owner=2, name='Other')], [dict(id=9, owner=2, name=None)]):
            state = observation()
            state['units'] = units
            with self.subTest(units=units), self.assertRaises(ValueError):
                spy_completion.compare_own(catalogue(), state)
        state = observation()
        state['units'][0]['name'] = 'Ada'
        spy_completion.compare_own(catalogue(), state)
        state['units'] = []
        spy_completion.compare_own(catalogue(renew=False), state)

    def test_history_signed32_scalars_and_native_event_sequence_width(self):
        for edge in (-0x80000000, 0x7fffffff):
            value = catalogue(renew=False)
            for key in ('level', 'operation', 'completion_turn', 'initial_result', 'escape_result', 'loot_info'):
                value['current'][key] = edge
            value['current']['event_sequence'] = 0xffffffff
            value['offers'][0]['action']['event_sequence'] = 0xffffffff
            spy_completion.validate_catalogue(value, 2, 73)
        for key, bad in (('event_sequence', -1), ('event_sequence', 0x100000000),
                         ('event_sequence', True), ('mission_id', -1), ('mission_id', True),
                         ('mission_id', 0x80000000), ('loot_info', -0x80000001),
                         ('loot_info', 0x80000000), ('initial_result', False)):
            value = catalogue()
            value['current'][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                spy_completion.validate_catalogue(value, 2, 73)

    def test_standalone_actions_accept_actual_linear_plot_but_supplied_map_checks_it(self):
        action = catalogue()['offers'][0]['action']
        spy_completion.validate_action(action)
        spy_completion.validate_action(action, 3, 2)
        with self.assertRaises(ValueError):
            spy_completion.validate_action(action, 4, 2)
        for width, height in ((3, None), (None, 2), (0, 2), (True, 2), (3, 16385)):
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                spy_completion.validate_action(action, width, height)

    def test_action_shape_scalar_and_target_bounds_are_exact(self):
        for key, bad in (('kind', 'spy_mission'), ('unit_id', -1), ('unit_id', True),
                         ('unit_id', 0x100000000), ('event_sequence', 0x100000000),
                         ('mission_id', -1), ('operation_type', 'UNITOPERATION_'),
                         ('operation_type', 'UNITOPERATION_spy'), ('operation_hash', -1),
                         ('operation_hash', True), ('operation_hash', 0x100000000),
                         ('x', 3), ('y', 2), ('plot_id', 4), ('plot_id', True)):
            action = catalogue()['offers'][0]['action']
            action[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                spy_completion.validate_action(action, 3, 2)
        for index in (0, 1):
            for mutate in ('missing', 'extra'):
                action = catalogue()['offers'][index]['action']
                if mutate == 'missing':
                    action.pop('mission_id')
                else:
                    action['private_pointer'] = 123
                with self.subTest(index=index, mutation=mutate), self.assertRaises(ValueError):
                    spy_completion.validate_action(action)

    def test_schema_player_turn_map_and_container_shapes_are_strict(self):
        for key, bad in (('schema', 'civ6-host.spy-completion.v2'), ('player_id', True),
                         ('player_id', 3), ('turn', 74), ('turn', 73.0),
                         ('width', 0), ('height', True), ('width', 16385),
                         ('current', []), ('offers', ())):
            value = catalogue()
            value[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                spy_completion.validate_catalogue(value, 2, 73)
        value = catalogue()
        value.update(width=129, height=128)
        with self.assertRaises(ValueError):
            spy_completion.validate_catalogue(value, 2, 73)
        for target in ('catalogue', 'current', 'offer'):
            for mutate in ('extra', 'missing'):
                value = catalogue()
                row = value if target == 'catalogue' else value['current'] if target == 'current' else value['offers'][0]
                if mutate == 'extra':
                    row['private_native_state'] = 1
                else:
                    row.pop(next(iter(row)))
                with self.subTest(target=target, mutation=mutate), self.assertRaises(ValueError):
                    spy_completion.validate_catalogue(value, 2, 73)

    def test_text_and_quote_bounds_allow_unknown_values_without_rounding(self):
        value = catalogue(renew=False)
        value['current']['name'] = 'é' * 16384
        value['offers'][0].update(turns=0, success_percent=0,
                                  failure_percent=100, captured_or_killed_percent=-1)
        spy_completion.validate_catalogue(value, 2, 73)
        for key in ('name', 'city_name'):
            for bad in (None, 'é' * 16385):
                value = catalogue()
                value['current'][key] = bad
                with self.subTest(key=key), self.assertRaises(ValueError):
                    spy_completion.validate_catalogue(value, 2, 73)
        for key in ('turns', 'success_percent', 'failure_percent', 'captured_or_killed_percent'):
            for bad in (-2, True, 1.0, 0x80000000 if key == 'turns' else 101):
                value = catalogue()
                value['offers'][0][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    spy_completion.validate_catalogue(value, 2, 73)

    def test_observation_provenance_and_duplicate_units_are_rejected(self):
        for key, bad in (('player_id', 1), ('turn', 74), ('width', 4), ('height', True), ('units', ())):
            state = observation()
            state[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                spy_completion.compare_own(catalogue(), state)
        state = observation()
        state['units'].append(deepcopy(state['units'][0]))
        with self.assertRaises(ValueError):
            spy_completion.compare_own(catalogue(), state)


if __name__ == '__main__':
    unittest.main()

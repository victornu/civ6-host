"""Current Great People observations only; public client and additive schemas."""
import ast
from copy import deepcopy
from itertools import product
from pathlib import Path
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, great_people as contract
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_religion_founding_public import preceding as religion_preceding, state as foundation_state
from test_xp1_religion_beliefs_public import validate, unavailable, terminal_v11


def state(obs, *, empty=False):
    quote = dict(cost=550, native_can_patronize=True, visible=True, available=True, no_patronage=False)
    named = dict(individual_index=117, item_type='GREAT_PERSON_INDIVIDUAL_ZOROASTER',
        class_index=4, era_index=1, claimed=True, claimant_player_id=None,
        recruitment=dict(cost=60, native_can_recruit=False, available=False),
        rejection=dict(cost=None, native_can_reject=False, available=False),
        patronage=dict(YIELD_GOLD=quote, YIELD_FAITH=dict(cost=1000000,
            native_can_patronize=True, visible=False, available=False, no_patronage=True)))
    placeholder = dict(individual_index=None, item_type=None, class_index=5, era_index=2,
        claimed=False, claimant_player_id=None, recruitment=None, rejection=None, patronage=None)
    return dict(schema=contract.SCHEMA, player_id=obs['player_id'], turn=obs['turn'],
        capabilities=dict(recruit=True, reject=True, YIELD_GOLD=True, YIELD_FAITH=True),
        no_patronage=dict(YIELD_GOLD=False, YIELD_FAITH=True),
        own_points=[dict(class_index=4, class_type='GREAT_PERSON_CLASS_PROPHET',
            max_instances=1, instances_earned=0, points_total=17.00390625, points_per_turn=2.0),
            dict(class_index=5, class_type='GREAT_PERSON_CLASS_SCIENTIST',
            max_instances=None, instances_earned=2, points_total=0.0, points_per_turn=0.0)],
        timeline=[] if empty else [named, placeholder])


def preceding(value, obs, options, *, waiting=False):
    pantheon, beliefs, foundation = options
    religion_preceding(value, obs, pantheon=pantheon, beliefs=beliefs, waiting=waiting)
    if foundation:
        network.add_xp1_religion_founding(value, None if waiting else foundation_state(obs))
    return seal(value)


class GreatPeopleBackend(ReligionBackend):
    def __init__(self, *, options=(True, True, True), waiting=False, empty=False):
        super().__init__()
        self.options, self.waiting, self.empty = options, waiting, empty

    def _reply(self, operation, sequence, player, requested=None):
        if operation == 'close':
            value = super()._reply('observe', sequence, player, requested)
            closed = super()._reply('close', sequence, player, requested)
            value.update(operation='close', outcome=closed['outcome'])
            value['decisions'] = terminal_v11(value['decisions'])
            return value
        value = super()._reply(operation, sequence, player, requested)
        dec, obs = value['decisions'], value['observation']
        if self.waiting:
            unavailable(dec)
            value['session']['active_human_player_ids'] = []
        preceding(dec, obs, self.options, waiting=self.waiting)
        network.add_xp1_great_people(dec, None if self.waiting else state(obs, empty=self.empty))
        seal(dec)
        return value


class XP1GreatPeoplePublicTests(unittest.TestCase):
    def test_scope_portability_and_exact_controlled_copy_of_reader_data(self):
        obs, _, _, _ = religion_fixture()
        value = state(obs)
        self.assertEqual(contract.SCOPE, ('current_timeline', 'own_points'))
        tree = ast.parse(Path(contract.__file__).read_text(encoding='utf-8'))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names]
        self.assertEqual(set(modules), {'copy', 're'})
        projected = contract.project(value, obs['player_id'], obs['turn'], observation=obs)
        self.assertEqual(projected, value)
        self.assertEqual(projected['own_points'][0]['points_total'], 17.00390625)
        self.assertTrue(projected['timeline'][0]['claimed'])
        self.assertIsNone(projected['timeline'][0]['claimant_player_id'])
        self.assertEqual(projected['timeline'][0]['patronage']['YIELD_FAITH'], value['timeline'][0]['patronage']['YIELD_FAITH'])
        projected['timeline'][0]['patronage']['YIELD_GOLD']['cost'] = 999
        projected['own_points'].clear()
        self.assertEqual(value['timeline'][0]['patronage']['YIELD_GOLD']['cost'], 550)
        self.assertEqual(len(value['own_points']), 2)

    def test_exact_identity_types_and_native_fixed_point_precision(self):
        obs, _, _, _ = religion_fixture()
        for points in (-8388608, -0.00390625, 0, 8388607.99609375):
            value = state(obs)
            value['own_points'][0]['points_total'] = points
            contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
        for points in (True, '17', None, float('nan'), float('inf'), -float('inf'),
                       0.1, 8388608, -8388608.00390625):
            value = state(obs)
            value['own_points'][0]['points_total'] = points
            with self.subTest(points=points), self.assertRaises(ValueError):
                contract.validate(value, obs['player_id'], obs['turn'])
        for key, bad in (('player_id', True), ('player_id', 64), ('turn', True), ('turn', 2**31)):
            value = state(obs)
            value[key] = bad
            with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                contract.validate(value, obs['player_id'], obs['turn'])
        with self.assertRaises(ValueError):
            contract.validate(state(obs), obs['player_id'], obs['turn'], observation=dict(obs, turn=True))

    def test_bounds_claimants_placeholders_and_no_foreign_point_payload(self):
        obs, _, _, _ = religion_fixture()
        contract.validate(state(obs, empty=True), obs['player_id'], obs['turn'])
        for mutation in ('empty_points', 'too_many_classes', 'too_many_rows', 'duplicate_class',
                         'duplicate_individual', 'unknown_class', 'claimant', 'false_claim',
                         'placeholder', 'foreign_points', 'past', 'quote', 'flag', 'type_key'):
            value = state(obs)
            if mutation == 'empty_points': value['own_points'] = []
            elif mutation == 'too_many_classes': value['own_points'] *= 33
            elif mutation == 'too_many_rows': value['timeline'] = [value['timeline'][1]]*4097
            elif mutation == 'duplicate_class': value['own_points'].append(deepcopy(value['own_points'][0]))
            elif mutation == 'duplicate_individual': value['timeline'].append(deepcopy(value['timeline'][0]))
            elif mutation == 'unknown_class': value['timeline'][0]['class_index'] = 77
            elif mutation == 'claimant': value['timeline'][0]['claimant_player_id'] = 64
            elif mutation == 'false_claim': value['timeline'][1]['claimant_player_id'] = 1
            elif mutation == 'placeholder': value['timeline'][1]['item_type'] = 'GREAT_PERSON_INDIVIDUAL_TEST'
            elif mutation == 'foreign_points': value['own_points'][0]['player_id'] = 1
            elif mutation == 'past': value['past_timeline'] = []
            elif mutation == 'quote': value['timeline'][0]['patronage']['YIELD_GOLD']['cost'] = True
            elif mutation == 'flag': value['timeline'][0]['recruitment']['available'] = 1
            else: value['own_points'][0]['class_type'] = 'other'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate(value, obs['player_id'], obs['turn'])

    def test_eight_schema_combinations_preserve_every_old_field_and_action(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=3):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            native = state(obs)
            network.add_xp1_great_people(value, native)
            validate(obs, value)
            for key in set(prior)-{'schema', 'decision_id'}:
                self.assertEqual(value[key], prior[key], (options, key))
            self.assertNotIn('great_people', value['families'])
            self.assertIn(value['schema'], network.XP1_GREAT_PEOPLE_SCHEMAS)
            self.assertEqual(value['schema'] in network.XP1_PANTHEON_SCHEMAS, options[0])
            self.assertEqual(value['schema'] in network.XP1_RELIGION_BELIEFS_SCHEMAS, options[1])
            self.assertEqual(value['schema'] in network.XP1_RELIGION_FOUNDING_SCHEMAS, options[2])
            native['timeline'].clear()
            self.assertEqual(len(value['great_people']['timeline']), 2)
            with self.assertRaises(ValueError): network.add_xp1_great_people(value, state(obs))

    def test_checkpoint_projection_removes_only_the_new_observation(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=3):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            network.add_xp1_great_people(value, state(obs))
            validate(obs, value)
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(receipt['added_public_fields'], ['great_people'])
            self.assertEqual(receipt.get('added_action_families', []), [])
            projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, city)
            self.assertEqual(receipt.get('added_action_families', []),
                (['pantheon'] if options[0] else [])+(['add_belief'] if options[1] else [])+(['found_religion'] if options[2] else []))
            self.assertEqual(receipt['added_public_fields'][-1], 'great_people')
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            changed = deepcopy(value)
            changed['choice_state']['research']['research'] = 123
            seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs, core_sha256=XP1_CORE_SHA256)[0], prior)

    def test_real_client_information_preserves_optional_groups_without_backend_calls(self):
        for options in product((False, True), repeat=3):
            backend = GreatPeopleBackend(options=options)
            client = SessionClient(backend, allow_administrative=True)
            frame = client.reset()
            info = client.information('great_people')
            self.assertEqual(info['data'], state(frame['observation']))
            self.assertEqual(info['native_decision_id'], frame['decisions']['decision_id'])
            self.assertEqual(info['source_contracts'], dict(great_people=contract.SCHEMA,
                decision_catalogue=frame['decisions']['schema']))
            self.assertEqual(backend.calls, [])
            for enabled, group in zip(options, ('pantheon', 'religion_beliefs', 'religion_founding')):
                if enabled: client.information(group)
                else:
                    with self.assertRaises(InformationUnavailable): client.information(group)
            client.information('city_religion')
            client.information('production')
            info['data']['own_points'][0]['points_total'] = 999
            self.assertEqual(client.information('great_people')['data']['own_points'][0]['points_total'], 17.00390625)
            self.assertFalse(any(r['action']['kind'].startswith('great_') for r in frame['decisions']['candidates']))

    def test_empty_timeline_waiting_legacy_and_reduced_close_remain_distinct(self):
        empty = SessionClient(GreatPeopleBackend(empty=True))
        frame = empty.reset()
        self.assertEqual(empty.information('great_people')['data']['timeline'], [])
        waiting = SessionClient(GreatPeopleBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['great_people'])
        with self.assertRaises(InformationUnavailable): waiting.information('great_people')
        legacy = SessionClient(ReligionBackend())
        legacy.reset()
        with self.assertRaises(InformationUnavailable): legacy.information('great_people')
        client = SessionClient(GreatPeopleBackend())
        client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('great_people', closed['decisions'])
        with self.assertRaises(InformationUnavailable): client.information('great_people')
        with self.assertRaises(ValueError): network.add_xp1_great_people(closed['decisions'], None, actions_closed=True)
        obs, _, _, dec = religion_fixture()
        with self.assertRaises(ValueError): network.add_xp1_great_people(dec, None)
        unavailable(dec)
        with self.assertRaises(ValueError): network.add_xp1_great_people(dec, state(obs))

    def test_client_enforces_actor_channel_schema_and_cached_value_identity(self):
        client = SessionClient(GreatPeopleBackend(), allow_administrative=True)
        frame = client.reset()
        with self.assertRaises(InformationUnavailable): client.information('great_people', player_id=1)
        with self.assertRaises(InformationUnavailable): client.information('great_people', channel='administrative')
        for mutation in ('stale', 'bool_quote', 'old_schema'):
            dec = client._views[0]['decisions'] = deepcopy(frame['decisions'])
            if mutation == 'stale': dec['great_people']['turn'] += 1
            elif mutation == 'bool_quote': dec['great_people']['timeline'][0]['patronage']['YIELD_GOLD']['cost'] = True
            else: dec['schema'] = network._XP1_GREAT_PEOPLE_BASE_BY_SCHEMA[dec['schema']]
            with self.subTest(mutation=mutation), self.assertRaises(ProtocolError):
                client.information('great_people')


if __name__ == '__main__':
    unittest.main()

"""Versioned own-city numeric religion details through the existing client."""
from copy import deepcopy
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import city_religion as contract, network_turn as network
from civ6_host.contracts.information import project as information_project
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend, state as majority_state
from test_xp1_great_person_activation_public import combinations
from test_xp1_religious_unit_operations_public import (
    ReligiousBackend, preceding, state as operation_state)
from test_xp1_religion_beliefs_public import validate


def details(obs, previous=None, mode='populated'):
    value = deepcopy(previous if previous is not None else majority_state(obs))
    value['schema'] = contract.DETAILS_SCHEMA
    for city in value['cities']:
        city['religions'] = ([] if mode == 'empty' else
            [dict(religion_index=1, followers=0, pressure_per_turn=3, lifetime_pressure=125),
             dict(religion_index=13, followers=2, pressure_per_turn=0, lifetime_pressure=0)])
    return contract.validate_details(value, obs['player_id'], obs['turn'], observation=obs)


class DetailsBackend(ReligiousBackend):
    def __init__(self, *, empty=False, waiting=False):
        super().__init__(waiting=waiting)
        self.empty = empty

    def _reply(self, operation, sequence, player, requested=None):
        value = super()._reply(operation, sequence, player, requested)
        if operation != 'close':
            dec, obs = value['decisions'], value['observation']
            network.add_xp1_city_religion_details(dec, details(
                obs, dec['city_religion'], 'empty' if self.empty else 'populated'))
            seal(dec)
        return value


class XP1CityReligionDetailsPublicTests(unittest.TestCase):
    def test_signed_counts_and_already_rounded_pressure_are_preserved_exactly(self):
        obs = religion_fixture()[0]
        for followers in (-0x80000000, -1, 0, 1, 0x7fffffff):
            for pressure in (-8388608, -1, 0, 1, 8388608):
                value = details(obs)
                row = value['cities'][0]['religions'][0]
                row.update(followers=followers, pressure_per_turn=pressure, lifetime_pressure=-pressure)
                self.assertIs(contract.validate(value, obs['player_id'], obs['turn'], observation=obs), value)
                self.assertEqual(row['followers'], followers)
                self.assertEqual(row['pressure_per_turn'], pressure)
        value = details(obs)
        value['cities'][0]['religions'][-1]['religion_index'] = 0x7fffffff
        contract.validate_details(value, obs['player_id'], obs['turn'], observation=obs)
        self.assertEqual(contract.project_majority(value, obs['player_id'], obs['turn'], observation=obs), majority_state(obs))
        for field, bad in (('followers', True), ('followers', 0x80000000), ('followers', -0x80000001),
                           ('pressure_per_turn', 1.0), ('pressure_per_turn', .5),
                           ('pressure_per_turn', 8388609), ('lifetime_pressure', -8388609),
                           ('lifetime_pressure', None), ('lifetime_pressure', False),
                           ('religion_index', -1), ('religion_index', 0x80000000), ('religion_index', True)):
            broken = details(obs)
            broken['cities'][0]['religions'][0][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                contract.validate_details(broken, obs['player_id'], obs['turn'], observation=obs)

    def test_exact_own_city_roster_order_and_uninvented_empty_rows(self):
        obs = deepcopy(religion_fixture()[0])
        other = deepcopy(obs['cities'][0])
        other['id'] += 1
        obs['cities'].append(other)
        value = details(obs)
        for mutation in ('missing', 'foreign', 'order', 'duplicate_city', 'foreign_owner', 'actor',
                         'turn', 'extra_field', 'nil_rows', 'duplicate_religion', 'religion_order'):
            bad, own = deepcopy(value), deepcopy(obs)
            city = bad['cities'][0]
            if mutation == 'missing': bad['cities'].pop()
            elif mutation == 'foreign': city['city_id'] += 99
            elif mutation == 'order': bad['cities'].reverse()
            elif mutation == 'duplicate_city': bad['cities'][1] = deepcopy(city)
            elif mutation == 'foreign_owner': own['cities'][0]['owner'] += 1
            elif mutation == 'actor': bad['player_id'] = False
            elif mutation == 'turn': bad['turn'] += 1
            elif mutation == 'extra_field': city['outward_pressure'] = 0
            elif mutation == 'nil_rows': city['religions'] = None
            elif mutation == 'duplicate_religion': city['religions'][1] = deepcopy(city['religions'][0])
            else: city['religions'].reverse()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate_details(bad, obs['player_id'], obs['turn'], observation=own)
        empty = details(obs, mode='empty')
        # Majority and active rows are independent native reads: no fabricated consistency rule.
        empty['cities'][0]['majority_religion'] = 13
        self.assertIs(contract.validate_details(empty, obs['player_id'], obs['turn'], observation=obs), empty)
        obs['cities'] = []
        self.assertEqual(details(obs)['cities'], [])

    def test_old_v1_validation_client_and_unknown_versions_remain_distinct(self):
        obs = religion_fixture()[0]
        for index in (-0x80000000, -1, 0, 0x7fffffff):
            old = majority_state(obs, index)
            self.assertIs(contract.validate(old, obs['player_id'], obs['turn'], observation=obs), old)
            self.assertEqual(contract.project_majority(old, obs['player_id'], obs['turn']), old)
        legacy_backend = ReligionBackend()
        legacy = SessionClient(legacy_backend)
        legacy.reset()
        self.assertEqual(legacy.information('city_religion')['data']['schema'], contract.SCHEMA)
        self.assertEqual(legacy_backend.calls, [])
        for malformed in (None, {}, dict(details(obs), schema='civ6-host.city-religion.v3'),
                          dict(details(obs), schema=contract.SCHEMA),
                          dict(majority_state(obs), schema=contract.DETAILS_SCHEMA)):
            with self.subTest(malformed=str(malformed)[:60]), self.assertRaises(ValueError):
                contract.validate(malformed, obs['player_id'], obs['turn'], observation=obs)

    def test_all_384_existing_option_combinations_keep_every_choice_and_old_field(self):
        obs, _, _, city = religion_fixture()
        count = 0
        for options in combinations():
            for gp_activation in (False, True):
                for operations in (False, True):
                    prior = preceding(deepcopy(city), obs, options, gp_activation=gp_activation)
                    if operations:
                        network.add_xp1_religious_unit_operations(prior, operation_state(obs))
                    seal(prior)
                    value = deepcopy(prior)
                    network.add_xp1_city_religion_details(value, details(obs, prior['city_religion']))
                    validate(obs, value)
                    self.assertEqual(value['candidates'], prior['candidates'])
                    self.assertEqual(value['families'], prior['families'])
                    for key in set(prior)-{'schema','decision_id','city_religion'}:
                        self.assertEqual(value[key], prior[key], (options, key))
                    self.assertEqual(contract.project_majority(value['city_religion'], obs['player_id'], obs['turn']), prior['city_religion'])
                    self.assertEqual(value['schema'] in network.XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS, operations)
                    self.assertEqual(value['schema'] in network.XP1_GREAT_PERSON_ACTIVATION_SCHEMAS, gp_activation)
                    self.assertEqual(value['schema'] in network.XP1_RELIGION_CUSTOM_NAMES_SCHEMAS, options[5])
                    self.assertFalse(value['complete_action_space'])
                    with self.assertRaises(ValueError):
                        network.add_xp1_city_religion_details(value, value['city_religion'])
                    count += 1
        self.assertEqual(count, 384)

    def test_checkpoint_projection_removes_only_details_and_detects_majority_changes(self):
        obs, older, _, city = religion_fixture()
        for full in (False, True):
            prior = deepcopy(city)
            if full:
                preceding(prior, obs)
                network.add_xp1_religious_unit_operations(prior, operation_state(obs))
            seal(prior)
            value = deepcopy(prior)
            network.add_xp1_city_religion_details(value, details(obs, prior['city_religion']))
            validate(obs, value)
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(receipt['added_public_fields'], ['city_religion.cities[].religions'])
            self.assertNotIn('added_action_families', receipt)
            self.assertEqual(receipt['public_schema_upgrades'], [dict(field='city_religion',
                source_schema=contract.SCHEMA, target_schema=contract.DETAILS_SCHEMA)])
            for target in (city, older):
                projected, receipt = network.checkpoint_catalogue(value, target, obs, core_sha256=XP1_CORE_SHA256)
                self.assertEqual(projected, target)
                self.assertEqual(receipt['added_public_fields'][-1], 'city_religion.cities[].religions')
            self.assertEqual(network.checkpoint_catalogue(value, value, obs, core_sha256=XP1_CORE_SHA256), (value, None))
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            changed = deepcopy(value)
            changed['city_religion']['cities'][0]['majority_religion'] = 13
            seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs, core_sha256=XP1_CORE_SHA256)[0], prior)

    def test_real_client_information_detaches_and_does_not_change_dispatch(self):
        backend = DetailsBackend()
        client = SessionClient(backend, allow_administrative=True)
        frame = client.reset()
        info = client.information('city_religion')
        self.assertEqual(info['data'], frame['decisions']['city_religion'])
        self.assertEqual(info['source_contracts']['city_religion'], contract.DETAILS_SCHEMA)
        self.assertEqual(info['native_decision_id'], frame['decisions']['decision_id'])
        self.assertEqual(backend.calls, [])
        info['data']['cities'][0]['religions'][0]['followers'] = 999
        self.assertEqual(client.information('city_religion')['data']['cities'][0]['religions'][0]['followers'], 0)
        for group in ('religious_unit_operations','great_person_activation','religion_custom_names',
                      'religion_founding','religion_beliefs','pantheon','great_people','production'):
            client.information(group)
        offered = next(row for row in frame['decisions']['candidates'] if row['action']['kind'] == 'spread_religion')
        reply = client.act(0, frame['decisions']['decision_id'], offered['candidate_id'])
        self.assertEqual(reply['applied_action'], offered['action'])
        self.assertEqual(client.information('city_religion')['data']['schema'], contract.DETAILS_SCHEMA)
        with self.assertRaises(InformationUnavailable): client.information('city_religion', player_id=1)
        with self.assertRaises(InformationUnavailable): client.information('city_religion', channel='administrative')

    def test_waiting_retains_majority_and_details_and_terminal_v11_stays_reduced(self):
        waiting = SessionClient(DetailsBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['religious_unit_operations'])
        self.assertEqual(waiting.information('city_religion')['data'], details(frame['observation']))
        empty = SessionClient(DetailsBackend(empty=True))
        empty.reset()
        self.assertEqual(empty.information('city_religion')['data']['cities'][0]['religions'], [])
        closed = empty.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('city_religion', closed['decisions'])
        with self.assertRaises(InformationUnavailable): empty.information('city_religion')
        with self.assertRaises(ValueError): network.add_xp1_city_religion_details(closed['decisions'], None)

    def test_unqueried_unknown_or_wrong_revision_details_refuse_instead_of_disappearing(self):
        obs, _, _, city = religion_fixture()
        for state in (None, majority_state(obs)):
            original = deepcopy(city)
            with self.assertRaises(ValueError): network.add_xp1_city_religion_details(original, state)
            self.assertEqual(original, city)
        changed = details(obs)
        changed['cities'][0]['majority_religion'] = 1
        with self.assertRaisesRegex(ValueError, 'existing majority'):
            network.add_xp1_city_religion_details(deepcopy(city), changed)
        wrong = deepcopy(city)
        wrong['city_religion'] = details(obs)
        with self.assertRaises(ValueError): validate(obs, wrong)
        with self.assertRaises(ValueError): information_project('city_religion', obs, wrong)
        current = deepcopy(city)
        network.add_xp1_city_religion_details(current, details(obs))
        current['city_religion'] = majority_state(obs)
        with self.assertRaises(ValueError): validate(obs, current)
        client = SessionClient(DetailsBackend())
        client.reset()
        client._views[0]['decisions']['city_religion']['cities'][0]['religions'][0]['pressure_per_turn'] = .5
        with self.assertRaises(ProtocolError): client.information('city_religion')


if __name__ == '__main__':
    unittest.main()

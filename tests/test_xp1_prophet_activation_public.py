"""Explicit Prophet activation public data, retained groups and actual client."""
from copy import deepcopy
from itertools import product
import json
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, prophet_activation as contract
from civ6_host.contracts import religion_beliefs, religion_founding
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_religion_observation as reader
from civ6_host.runtime.native import native_prophet_activation as choices
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_pantheon_public import offered as pantheon_offered
from test_xp1_religion_beliefs_public import state as belief_state, validate, unavailable, terminal_v11
from test_xp1_religion_founding_public import state as foundation_state
from test_xp1_great_people_public import state as great_people_state


def native_own(obs, mode='offered'):
    pid, turn, city = obs['player_id'], obs['turn'], obs['cities'][0]['id']
    if mode == 'founded':
        wire = f'religion-observation-v1|{pid}|{turn}|3|1|2|{pid}|2|{city}|1|3|{pid}|1|24'
    elif mode == 'consumed':
        wire = f'religion-observation-v1|{pid}|{turn}|-1|1|2|{pid}|2|{city}|0|-1|-1|0'
    else:
        wire = f'religion-observation-v1|{pid}|{turn}|-1|{int(mode != "no_unit")}|0|-1|2|-1|0|-1|-1|0'
    return reader.parse_observation(wire.encode(), pid, turn)


def state(obs, mode='offered'):
    pid, turn = obs['player_id'], obs['turn']
    own = contract.project_snapshot(native_own(obs, mode), pid, turn, observation=obs)
    sub = None
    if mode in ('offered', 'empty'):
        unit = obs['units'][0]
        tail = '0' if mode == 'empty' else f'1,{unit["id"]}:{unit["x"]}:{unit["y"]}'
        wire = f'catalog,{pid},{turn},{choices.OPERATION_HASH},6,{tail}'
        sub = json.loads(json.dumps(choices.parse_catalog(wire.encode(), pid, turn)))
    return dict(schema=contract.SCHEMA, player_id=pid, turn=turn, own=own, activation=sub)


def preceding(value, obs, options, *, mode='offered', waiting=False):
    pantheon, beliefs, foundation, gp = options
    own = state(obs, mode)['own']
    pid, turn = obs['player_id'], obs['turn']
    if pantheon:
        network.add_xp1_pantheon(value, None if waiting else pantheon_offered(obs))
    if beliefs:
        sub = belief_state(obs)['beliefs'] if mode == 'founded' else None
        network.add_xp1_religion_beliefs(value, None if waiting else
            dict(schema=religion_beliefs.SCHEMA, player_id=pid, turn=turn, own=own, beliefs=sub))
    if foundation:
        sub = foundation_state(obs)['foundation'] if mode == 'consumed' else None
        network.add_xp1_religion_founding(value, None if waiting else
            dict(schema=religion_founding.SCHEMA, player_id=pid, turn=turn, own=own, foundation=sub))
    if gp:
        network.add_xp1_great_people(value, None if waiting else great_people_state(obs))
    return seal(value)


class ProphetBackend(ReligionBackend):
    def __init__(self, *, options=(True, True, True, True), mode='offered', waiting=False):
        super().__init__()
        self.options, self.mode, self.waiting = options, mode, waiting

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
        preceding(dec, obs, self.options, mode=self.mode, waiting=self.waiting)
        network.add_xp1_prophet_activation(dec, None if self.waiting else state(obs, self.mode))
        seal(dec)
        return value


class XP1ProphetActivationPublicTests(unittest.TestCase):
    def test_shared_projection_and_native_parser_scalar_domains_without_gp_id(self):
        obs, _, _, _ = religion_fixture()
        self.assertIs(contract.project_snapshot, religion_beliefs.project_snapshot)
        value = state(obs)
        contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
        self.assertFalse(set(value['own']) & religion_beliefs._NATIVE_META)
        self.assertEqual(set(contract.actions(value)[0]), {'kind', 'unit_id', 'x', 'y'})
        unit = obs['units'][0]
        self.assertEqual(contract.actions(value), [dict(kind='activate_prophet', unit_id=unit['id'], x=unit['x'], y=unit['y'])])
        wire = f'catalog,{obs["player_id"]},{obs["turn"]},{choices.OPERATION_HASH},2147483647,2,0:-2147483648:2147483647,4294967295:2147483647:-2147483648'
        value['activation'] = json.loads(json.dumps(choices.parse_catalog(wire.encode(), obs['player_id'], obs['turn'])))
        contract.validate(value, obs['player_id'], obs['turn'])
        for action in contract.actions(value): contract.validate_action(action)
        for action in (dict(contract.actions(value)[0], unit_id=True),
                       dict(contract.actions(value)[0], x=-(2**31)-1),
                       dict(contract.actions(value)[0], y=2**31),
                       dict(contract.actions(value)[0], individual_index=117),
                       dict(contract.actions(value)[0], city_id=65536)):
            with self.assertRaises(ValueError): contract.validate_action(action)

    def test_absence_native_not_due_and_consumed_true_flag_are_distinct(self):
        obs, _, _, _ = religion_fixture()
        for mode in ('empty', 'no_unit', 'consumed', 'founded'):
            value = state(obs, mode)
            contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
            self.assertEqual(contract.actions(value), [])
            if mode == 'empty': self.assertEqual(value['activation']['status'], 'not_due')
            else: self.assertIsNone(value['activation'])
            if mode == 'consumed':
                self.assertTrue(value['own']['has_religious_founding_unit'])
                self.assertTrue(value['own']['holy_city_present'])
                self.assertEqual(value['own']['religion_type_created'], -1)
        value = state(obs)
        value['activation'] = None
        with self.assertRaises(ValueError): contract.validate(value, obs['player_id'], obs['turn'])

    def test_exact_native_shape_and_actor_unit_identity(self):
        obs, _, _, _ = religion_fixture()
        for mutation in ('actor', 'turn', 'meta', 'foreign_id', 'coordinates', 'duplicate', 'status', 'index_bool', 'operation_bool'):
            value = state(obs)
            if mutation == 'actor': value['player_id'] = True
            elif mutation == 'turn': value['turn'] += 1
            elif mutation == 'meta': value['own']['eligible_for_training'] = False
            elif mutation == 'foreign_id': value['activation']['candidates'][0]['unit_id'] += 2000
            elif mutation == 'coordinates': value['activation']['candidates'][0]['x'] += 1
            elif mutation == 'duplicate': value['activation']['candidates'] *= 2
            elif mutation == 'status': value['activation']['status'] = 'not_due'
            elif mutation == 'index_bool': value['activation']['prophet_type_index'] = True
            else: value['activation']['operation'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
        foreign = deepcopy(obs)
        foreign['units'][0]['owner'] = 1
        with self.assertRaises(ValueError): contract.validate(state(obs), obs['player_id'], obs['turn'], observation=foreign)

    def test_sixteen_independent_wrappers_preserve_gp_and_existing_families(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=4):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            native = state(obs)
            network.add_xp1_prophet_activation(value, native)
            validate(obs, value)
            self.assertEqual(value['candidates'][:-1], prior['candidates'])
            self.assertEqual({k:v for k,v in value['families'].items() if k != 'activate_prophet'}, prior['families'])
            for group in ('pantheon', 'religion_beliefs', 'religion_founding', 'great_people'):
                self.assertEqual(value.get(group), prior.get(group))
            for enabled, schemas in zip(options, (network.XP1_PANTHEON_SCHEMAS, network.XP1_RELIGION_BELIEFS_SCHEMAS,
                    network.XP1_RELIGION_FOUNDING_SCHEMAS, network.XP1_GREAT_PEOPLE_SCHEMAS)):
                self.assertEqual(value['schema'] in schemas, enabled)
            self.assertEqual(value['families']['activate_prophet']['status'], 'queried_complete')
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(receipt['added_public_fields'], ['prophet_activation'])
            self.assertEqual(receipt['added_action_families'], ['activate_prophet'])
            projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, city)
            self.assertEqual(receipt['added_action_families'],
                (['pantheon'] if options[0] else [])+(['add_belief'] if options[1] else [])+
                (['found_religion'] if options[2] else [])+['activate_prophet'])
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            native['activation']['candidates'].clear()
            self.assertEqual(len(value['prophet_activation']['activation']['candidates']), 1)

    def test_actual_client_reads_and_selects_exact_unit_with_optional_groups(self):
        for options in product((False, True), repeat=4):
            backend = ProphetBackend(options=options)
            client = SessionClient(backend, allow_administrative=True)
            frame = client.reset()
            info = client.information('prophet_activation')
            self.assertEqual(info['data'], state(frame['observation']))
            self.assertEqual(info['native_decision_id'], frame['decisions']['decision_id'])
            self.assertEqual(info['source_contracts'], dict(prophet_activation=contract.SCHEMA,
                decision_catalogue=frame['decisions']['schema']))
            self.assertEqual(backend.calls, [])
            for enabled, group in zip(options, ('pantheon', 'religion_beliefs', 'religion_founding', 'great_people')):
                if enabled: client.information(group)
                else:
                    with self.assertRaises(InformationUnavailable): client.information(group)
            info['data']['own']['num_beliefs_earned'] = 999
            self.assertEqual(client.information('prophet_activation')['data']['own']['num_beliefs_earned'], 0)
            with self.assertRaises(InformationUnavailable): client.information('prophet_activation', player_id=1)
            with self.assertRaises(InformationUnavailable): client.information('prophet_activation', channel='administrative')
            rows = [row for row in frame['decisions']['candidates'] if row['action']['kind'] == 'activate_prophet']
            self.assertEqual([r['action'] for r in rows], contract.actions(state(frame['observation'])))
            client.act(0, frame['decisions']['decision_id'], rows[0]['candidate_id'])

    def test_waiting_empty_legacy_and_reduced_terminal_v11(self):
        for mode in ('empty', 'no_unit', 'consumed', 'founded'):
            client = SessionClient(ProphetBackend(mode=mode))
            frame = client.reset()
            info = client.information('prophet_activation')
            self.assertEqual(contract.actions(info['data']), [])
            self.assertEqual(frame['decisions']['families']['activate_prophet'], dict(status='queried_complete', candidate_ids=[]))
        waiting = SessionClient(ProphetBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['prophet_activation'])
        with self.assertRaises(InformationUnavailable): waiting.information('prophet_activation')
        legacy = SessionClient(ReligionBackend())
        legacy.reset()
        with self.assertRaises(InformationUnavailable): legacy.information('prophet_activation')
        client = SessionClient(ProphetBackend())
        client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertEqual(closed['decisions']['candidates'], [])
        self.assertNotIn('prophet_activation', closed['decisions'])
        with self.assertRaises(InformationUnavailable): client.information('prophet_activation')
        with self.assertRaises(ValueError): network.add_xp1_prophet_activation(closed['decisions'], None, actions_closed=True)

    def test_exact_offer_family_status_and_cached_identity_cannot_change(self):
        obs, _, _, value = religion_fixture()
        network.add_xp1_prophet_activation(value, state(obs))
        validate(obs, value)
        for mutation in ('missing', 'extra', 'partial', 'unavailable', 'old_schema'):
            bad = deepcopy(value)
            family = bad['families']['activate_prophet']
            if mutation == 'missing':
                bad['candidates'].pop()
                family['candidate_ids'].pop()
            elif mutation == 'extra':
                action = dict(kind='activate_prophet', unit_id=999, x=0, y=0)
                key = network.digest(action)
                bad['candidates'].append(dict(candidate_id=key, action=action))
                family['candidate_ids'].append(key)
            elif mutation == 'partial': family.update(status='queried_partial', unqualified=['missing'])
            elif mutation == 'unavailable': bad['prophet_activation'] = None
            else: bad['schema'] = network._XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA[bad['schema']]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(obs, bad)
        client = SessionClient(ProphetBackend())
        client.reset()
        client._views[0]['decisions']['prophet_activation']['turn'] += 1
        with self.assertRaises(ProtocolError): client.information('prophet_activation')


if __name__ == '__main__':
    unittest.main()

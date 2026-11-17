"""Partial predefined-name foundation contract and real public SessionClient."""
from copy import deepcopy
import json
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, religion_founding as contract
from civ6_host.contracts import religion_beliefs
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_religion_observation as reader
from civ6_host.runtime.native import native_religion_founding as choices
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_pantheon_public import offered as pantheon_offered
from test_xp1_religion_beliefs_public import state as belief_state, validate, unavailable, terminal_v11


def native_own(obs, mode='offered'):
    pid, turn, city = obs['player_id'], obs['turn'], obs['cities'][0]['id']
    if mode == 'no_site':
        wire = f'religion-observation-v1|{pid}|{turn}|-1|1|0|-1|2|-1|0|-1|-1|0'
    elif mode == 'already_founded':
        wire = f'religion-observation-v1|{pid}|{turn}|3|1|2|{pid}|2|{city}|1|3|{pid}|1|24'
    else:
        wire = f'religion-observation-v1|{pid}|{turn}|-1|1|2|{pid}|2|{city}|0|-1|-1|0'
    return reader.parse_observation(wire.encode(), pid, turn)


def state(obs, mode='offered'):
    pid, turn = obs['player_id'], obs['turn']
    own = contract.project_snapshot(native_own(obs, mode), pid, turn, observation=obs)
    sub = None
    if mode in ('offered', 'empty'):
        tail = '0' if mode == 'empty' else '2,9:4294967295,12:0'
        wire = (f'catalog,{pid},{turn},2,{pid},2,{obs["cities"][0]["id"]},0,'
                f'{choices.FOUND_RELIGION},{choices.PARAM_RELIGION_TYPE},'
                f'{choices.PARAM_INSERT_MODE},{choices.VALUE_EXCLUSIVE},{tail}')
        sub = json.loads(json.dumps(choices.parse_catalog(wire.encode(), pid, turn)))
    return dict(schema=contract.SCHEMA, player_id=pid, turn=turn, own=own, foundation=sub)


def preceding(value, obs, *, pantheon, beliefs, waiting=False, mode='offered'):
    if pantheon:
        network.add_xp1_pantheon(value, None if waiting else pantheon_offered(obs))
    if beliefs:
        if waiting:
            native = None
        elif mode == 'already_founded':
            native = belief_state(obs)
        else:
            native = dict(schema=religion_beliefs.SCHEMA, player_id=obs['player_id'],
                turn=obs['turn'], own=state(obs, mode)['own'], beliefs=None)
        network.add_xp1_religion_beliefs(value, native)
    return seal(value)


class FoundingBackend(ReligionBackend):
    def __init__(self, *, mode='offered', pantheon=True, beliefs=True, waiting=False):
        super().__init__()
        self.mode, self.pantheon, self.beliefs, self.waiting = mode, pantheon, beliefs, waiting

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
        preceding(dec, obs, pantheon=self.pantheon, beliefs=self.beliefs,
            waiting=self.waiting, mode=self.mode)
        network.add_xp1_religion_founding(dec, None if self.waiting else state(obs, self.mode))
        seal(dec)
        return value


class XP1ReligionFoundingPublicTests(unittest.TestCase):
    def test_shared_projection_and_exact_public_identity_types(self):
        obs, _, _, _ = religion_fixture()
        self.assertIs(contract.project_snapshot, religion_beliefs.project_snapshot)
        native = native_own(obs)
        projected = contract.project_snapshot(native, obs['player_id'], obs['turn'], observation=obs)
        self.assertFalse(set(projected) & religion_beliefs._NATIVE_META)
        self.assertTrue(projected['has_religious_founding_unit'])
        value = state(obs)
        contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
        for mutation in ('actor', 'turn', 'meta', 'site', 'index_bool', 'hash_bool', 'duplicate', 'order', 'custom', 'unqueried'):
            bad = deepcopy(value)
            if mutation == 'actor': bad['player_id'] = True
            elif mutation == 'turn': bad['turn'] += 1
            elif mutation == 'meta': bad['own']['source_proof_sha256'] = '0'*64
            elif mutation == 'site': bad['foundation']['founding_site']['player'] = True
            elif mutation == 'index_bool': bad['foundation']['candidates'][0]['index'] = True
            elif mutation == 'hash_bool': bad['foundation']['candidates'][0]['hash'] = True
            elif mutation == 'duplicate': bad['foundation']['candidates'].append(deepcopy(bad['foundation']['candidates'][0]))
            elif mutation == 'order': bad['foundation']['candidates'].reverse()
            elif mutation == 'custom': bad['foundation']['candidates'][0]['name'] = 'custom'
            else: bad['foundation'] = None
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate(bad, obs['player_id'], obs['turn'], observation=obs)
        for mode in ('empty', 'no_site', 'already_founded'):
            value = state(obs, mode)
            contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
            self.assertEqual(contract.actions(value), [])

    def test_all_independent_combinations_and_additive_checkpoint_projection(self):
        obs, _, _, city = religion_fixture()
        for pantheon in (False, True):
            for beliefs in (False, True):
                with self.subTest(pantheon=pantheon, beliefs=beliefs):
                    prior = preceding(deepcopy(city), obs, pantheon=pantheon, beliefs=beliefs)
                    value = deepcopy(prior)
                    native = state(obs)
                    network.add_xp1_religion_founding(value, native)
                    validate(obs, value)
                    self.assertEqual(value['candidates'][:-2], prior['candidates'])
                    self.assertEqual({k:v for k,v in value['families'].items() if k != 'found_religion'}, prior['families'])
                    self.assertEqual(value['schema'] in network.XP1_PANTHEON_SCHEMAS, pantheon)
                    self.assertEqual(value['schema'] in network.XP1_RELIGION_BELIEFS_SCHEMAS, beliefs)
                    self.assertIn(value['schema'], network.XP1_CITY_RELIGION_SCHEMAS)
                    family = value['families']['found_religion']
                    self.assertEqual(family['status'], 'queried_partial')
                    self.assertEqual(family['unqualified'], ['custom_religion_names'])
                    projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
                    self.assertEqual(projected, prior)
                    self.assertEqual(receipt['added_public_fields'], ['religion_founding'])
                    self.assertEqual(receipt['added_action_families'], ['found_religion'])
                    projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
                    self.assertEqual(projected, city)
                    self.assertEqual(receipt['added_action_families'],
                        (['pantheon'] if pantheon else []) + (['add_belief'] if beliefs else []) + ['found_religion'])
                    with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                        network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
                    changed = deepcopy(value)
                    changed['choice_state']['research']['research'] = 123
                    seal(changed)
                    self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs,
                        core_sha256=XP1_CORE_SHA256)[0], prior)
                    native['foundation']['candidates'].clear()
                    self.assertEqual(len(value['religion_founding']['foundation']['candidates']), 2)

    def test_real_client_information_selection_and_retained_families(self):
        for pantheon in (False, True):
            for beliefs in (False, True):
                backend = FoundingBackend(pantheon=pantheon, beliefs=beliefs)
                client = SessionClient(backend, allow_administrative=True)
                frame = client.reset()
                info = client.information('religion_founding')
                self.assertEqual(info['data'], state(frame['observation']))
                self.assertEqual(info['native_decision_id'], frame['decisions']['decision_id'])
                self.assertEqual(info['source_contracts'], dict(religion_founding=contract.SCHEMA,
                    decision_catalogue=frame['decisions']['schema']))
                self.assertEqual(backend.calls, [])
                if pantheon: self.assertEqual(client.information('pantheon')['data'], pantheon_offered(frame['observation']))
                if beliefs: self.assertIsNone(client.information('religion_beliefs')['data']['beliefs'])
                self.assertEqual(client.information('production')['data']['schema'], 'civ6-host.production-inputs.v3')
                client.information('city_religion')
                info['data']['own']['num_beliefs_earned'] = 999
                self.assertNotEqual(client.information('religion_founding')['data']['own']['num_beliefs_earned'], 999)
                with self.assertRaises(InformationUnavailable): client.information('religion_founding', channel='administrative')
                with self.assertRaises(InformationUnavailable): client.information('religion_founding', player_id=1)
                rows = [r for r in frame['decisions']['candidates'] if r['action']['kind'] == 'found_religion']
                self.assertEqual([r['action'] for r in rows], contract.actions(state(frame['observation'])))
                client.act(0, frame['decisions']['decision_id'], rows[1]['candidate_id'])

    def test_empty_and_absent_foundation_queries_remain_partial_and_available(self):
        for mode in ('empty', 'no_site', 'already_founded'):
            client = SessionClient(FoundingBackend(mode=mode))
            frame = client.reset()
            info = client.information('religion_founding')
            self.assertEqual(info['data'], state(frame['observation'], mode))
            self.assertEqual(contract.actions(info['data']), [])
            self.assertEqual(frame['decisions']['families']['found_religion'],
                dict(status='queried_partial', candidate_ids=[], unqualified=['custom_religion_names']))
            if mode == 'already_founded':
                self.assertTrue(client.information('religion_beliefs')['data']['beliefs']['candidates'])
            elif mode == 'empty':
                self.assertEqual(info['data']['foundation']['status'], 'not_due')
            else:
                self.assertIsNone(info['data']['foundation'])

    def test_waiting_legacy_and_reduced_v11_close_are_unavailable(self):
        waiting = SessionClient(FoundingBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['religion_founding'])
        self.assertEqual(frame['decisions']['families']['found_religion']['status'], 'unqualified')
        with self.assertRaises(InformationUnavailable): waiting.information('religion_founding')
        legacy = SessionClient(ReligionBackend())
        legacy.reset()
        with self.assertRaises(InformationUnavailable): legacy.information('religion_founding')
        client = SessionClient(FoundingBackend())
        client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertEqual(closed['decisions']['candidates'], [])
        for key in ('religion_founding', 'religion_beliefs', 'pantheon'):
            self.assertNotIn(key, closed['decisions'])
            with self.assertRaises(InformationUnavailable): client.information(key)
        with self.assertRaises(ValueError):
            network.add_xp1_religion_founding(closed['decisions'], None, actions_closed=True)

    def test_partial_limit_and_exact_offers_cannot_be_removed_or_fabricated(self):
        obs, _, _, value = religion_fixture()
        network.add_xp1_religion_founding(value, state(obs))
        validate(obs, value)
        for change in ('missing_offer', 'extra_offer', 'complete', 'wrong_limit', 'unavailable', 'schema'):
            bad = deepcopy(value)
            family = bad['families']['found_religion']
            if change == 'missing_offer':
                bad['candidates'].pop()
                family['candidate_ids'].pop()
            elif change == 'extra_offer':
                action = dict(kind='found_religion', index=23, hash=23)
                key = network.digest(action)
                bad['candidates'].append(dict(candidate_id=key, action=action))
                family['candidate_ids'].append(key)
            elif change == 'complete':
                family['status'] = 'queried_complete'
                del family['unqualified']
            elif change == 'wrong_limit': family['unqualified'] = ['something_else']
            elif change == 'unavailable': bad['religion_founding'] = None
            else: bad['schema'] = network._XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA[bad['schema']]
            with self.subTest(change=change), self.assertRaises(ValueError): validate(obs, bad)
        client = SessionClient(FoundingBackend())
        client.reset()
        client._views[0]['decisions']['religion_founding']['turn'] += 1
        with self.assertRaises(ProtocolError): client.information('religion_founding')


if __name__ == '__main__':
    unittest.main()

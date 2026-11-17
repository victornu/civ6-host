"""Public XP2 pantheon index/choices; synthetic choices are not native proof."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import information, network_turn as network, pantheon
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_pantheon_public import offered, PantheonBackend as XP1Backend
from test_xp2_religious_chain_public import preceding, added as add_chain, validate, ChainBackend
from test_xp2_religious_unit_operations_public import permissions_preceding


def state(obs, mode='offered'):
    native = offered(obs)
    index = -1
    if mode != 'offered':
        index = 7 if mode == 'owned' else -1
        native = dict(status='not_due', player_id=obs['player_id'], current_game_turn=obs['turn'],
                      reason='already_has_pantheon' if mode == 'owned' else 'cannot_create')
    return dict(schema=pantheon.STATE_SCHEMA, player_id=obs['player_id'], turn=obs['turn'],
                pantheon_index=index, catalogue=native)


def added(prior, obs, mode='offered', *, closed=False):
    value = deepcopy(prior)
    network.add_xp2_pantheon(value, None if mode is None else state(obs, mode), actions_closed=closed)
    return seal(value)


class Backend(ChainBackend):
    def __init__(self, mode='offered', **kwargs):
        super().__init__(**kwargs)
        self.pantheon_mode = mode

    def _reply(self, operation, sequence, **kwargs):
        value = super()._reply(operation, sequence, **kwargs)
        if operation != 'close':
            value['decisions'] = added(value['decisions'], value['observation'], self.pantheon_mode)
        return value


class XP2PantheonPublicTests(unittest.TestCase):
    def test_native_index_reason_actor_and_nested_catalogue_identity(self):
        _, obs = preceding()
        for mode, index in (('offered', -1), ('cannot_create', -1), ('owned', 7)):
            value = state(obs, mode)
            self.assertIs(pantheon.validate_state(value, obs['player_id'], obs['turn']), value)
            self.assertEqual(value['pantheon_index'], index)
            self.assertEqual(pantheon.state_actions(value), pantheon.actions(value['catalogue']))
        for fault in ('actor', 'turn', 'nested_actor', 'nested_turn', 'bool', 'range', 'reason', 'private'):
            bad = state(obs)
            if fault == 'actor': bad['player_id'] += 1
            elif fault == 'turn': bad['turn'] += 1
            elif fault == 'nested_actor': bad['catalogue']['player_id'] += 1
            elif fault == 'nested_turn': bad['catalogue']['current_game_turn'] += 1
            elif fault == 'bool': bad['pantheon_index'] = False
            elif fault == 'range': bad['pantheon_index'] = -2
            elif fault == 'reason': bad['pantheon_index'] = 7
            else: bad['source_sha256'] = 'private'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                pantheon.validate_state(bad, obs['player_id'], obs['turn'])
        bad = state(obs, 'owned'); bad['pantheon_index'] = -1
        with self.assertRaises(ValueError): pantheon.validate_state(bad, obs['player_id'], obs['turn'])

    def test_exact_predecessors_preserve_all_independent_chain_fields(self):
        expected = set(network.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE)
        expected.update(network._XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA)
        for mapping in (network.XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE,
                        network.XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE,
                        network.XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE):
            expected.update(mapping.values())
        self.assertEqual(len(expected), 640)
        self.assertEqual(set(network.XP2_PANTHEON_SCHEMA_BY_BASE), expected)
        for base, wrapped in network.XP2_PANTHEON_SCHEMA_BY_BASE.items():
            self.assertEqual(network._capability_version(base), network._capability_version(wrapped))
            self.assertIn(wrapped, network.SUPPORTED_SCHEMAS)
            for name in ('PROPHET_ACTIVATION_SCHEMAS', 'RELIGION_FOUNDING_SCHEMAS',
                         'RELIGION_BELIEFS_SCHEMAS', 'RELIGIOUS_UNIT_OPERATIONS_SCHEMAS',
                         'NATIVE_COMMAND_PERMISSIONS_SCHEMAS', 'STOCK_TRADE_CAPABILITY_SCHEMAS'):
                schemas = getattr(network, name)
                self.assertEqual(base in schemas, wrapped in schemas, (base, name))
        for index, units, options in product(range(3), (False, True), product((False, True), repeat=3)):
            prior, obs = preceding(index, levy=True, unit_operations=units)
            prior = add_chain(prior, obs, options=options)
            snapshot = deepcopy(prior)
            current = added(prior, obs)
            validate(current, obs)
            self.assertEqual(prior, snapshot)
            self.assertEqual(current['candidates'][:-2], prior['candidates'])
            self.assertEqual({k:v for k,v in current['families'].items() if k != 'pantheon'}, prior['families'])
            for key in set(prior)-{'schema', 'decision_id', 'candidates', 'families'}:
                self.assertEqual(current[key], prior[key])
            with self.assertRaises(ValueError): network.add_xp2_pantheon(current, state(obs))

    def test_additive_checkpoint_and_legacy_v1_remain_exact(self):
        prior, obs = preceding(2, levy=True, unit_operations=True)
        prior = add_chain(prior, obs, mode='beliefs')
        current = added(prior, obs, 'owned')
        projected, receipt = network.checkpoint_catalogue(current, prior, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(receipt['added_public_fields'], ['pantheon'])
        self.assertEqual(receipt['added_action_families'], ['pantheon'])
        self.assertEqual(network.checkpoint_catalogue(current, current, obs, core_sha256=XP2_CORE_SHA256), (current, None))
        for core in (None, XP1_CORE_SHA256):
            with self.assertRaisesRegex(ValueError, 'Gathering Storm'):
                network.checkpoint_catalogue(current, prior, obs, core_sha256=core)
        client = SessionClient(XP1Backend(), allow_administrative=True)
        frame = client.reset()
        self.assertIn(frame['decisions']['schema'], network.XP1_PANTHEON_SCHEMAS)
        self.assertEqual(client.information('pantheon')['data'], offered(frame['observation']))
        with self.assertRaises(ValueError): network.add_xp2_pantheon(frame['decisions'], state(frame['observation']))

    def test_waiting_closed_permissions_and_native_not_due_are_distinct(self):
        for strategic, tactical in product((False, True), repeat=2):
            prior, obs = permissions_preceding(strategic=strategic, tactical=tactical)
            current = added(prior, obs, 'offered' if strategic else None)
            validate(current, obs)
            self.assertEqual(current['pantheon'] is None, not strategic)
            with self.assertRaises(ValueError): added(prior, obs, None if strategic else 'offered')
        for phase in ('waiting', 'closed'):
            prior, obs = permissions_preceding(state=phase)
            current = added(prior, obs, None, closed=phase == 'closed')
            validate(current, obs, closed=phase == 'closed')
            self.assertIsNone(current['pantheon'])
            with self.assertRaises(ValueError): information.project('pantheon', obs, current)
        prior, obs = preceding()
        for mode in ('owned', 'cannot_create'):
            current = added(prior, obs, mode)
            validate(current, obs)
            self.assertEqual(current['families']['pantheon'], dict(status='queried_complete', candidate_ids=[]))
            self.assertEqual(information.project('pantheon', obs, current), state(obs, mode))

    def test_client_explicit_choice_index_readback_isolation_and_terminal(self):
        backend = Backend(); client = SessionClient(backend)
        frame = client.reset()
        self.assertEqual(client.information('pantheon')['data'], state(frame['observation']))
        row = next(r for r in reversed(frame['decisions']['candidates']) if r['action']['kind'] == 'pantheon')
        for params in ({}, {'index': 7}):
            with self.assertRaises(ProtocolError): client.act(0, frame['decisions']['decision_id'], row['candidate_id'], params)
        self.assertEqual(backend.calls, [])
        frame = client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
        self.assertEqual(frame['applied_action'], row['action'])
        backend.pantheon_mode = 'owned'
        frame = client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
        self.assertEqual(client.information('pantheon')['data']['pantheon_index'], 7)
        leaked = client.information('pantheon'); leaked['data']['pantheon_index'] = 999
        self.assertEqual(client.information('pantheon')['data']['pantheon_index'], 7)
        with self.assertRaises(InformationUnavailable): client.information('pantheon', player_id=1)
        closed = client.close()
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('pantheon', closed['decisions'])
        with self.assertRaises(InformationUnavailable): client.information('pantheon')

    def test_missing_or_added_candidates_and_old_schema_refuse(self):
        prior, obs = preceding()
        for fault in ('missing', 'hash', 'primitive', 'schema'):
            current = added(prior, obs)
            if fault == 'missing':
                row = current['candidates'].pop()
                current['families']['pantheon']['candidate_ids'].remove(row['candidate_id'])
            elif fault == 'schema': current['schema'] = prior['schema']
            else:
                row = current['candidates'][-1]
                row['action']['hash' if fault == 'hash' else 'index'] = 99 if fault == 'hash' else True
                row['candidate_id'] = network.digest(row['action'])
                current['families']['pantheon']['candidate_ids'][-1] = row['candidate_id']
            seal(current)
            with self.subTest(fault=fault), self.assertRaises(ValueError): validate(current, obs)


if __name__ == '__main__': unittest.main()

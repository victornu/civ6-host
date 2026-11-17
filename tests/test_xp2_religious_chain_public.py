"""XP2 religious choice contracts over retained public fields, without an engine.

Choice data and command outcomes are synthetic and are not native acceptance.
The existing portable fixture readers retain their own path/hash checks.
"""
from copy import deepcopy
from itertools import product
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import information, network_turn as network
from civ6_host.contracts import prophet_activation, religion_founding, religion_beliefs
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_client import Backend as SessionBackend
from test_session_capabilities import seal
from test_xp1_prophet_activation_public import state as activation_state, ProphetBackend
from test_xp1_religion_founding_public import state as foundation_state
from test_xp1_religion_beliefs_public import state as belief_state, terminal_v11
from test_xp2_religious_unit_operations_public import (
    preceding as unit_preceding, added as add_units, permissions_preceding,
)


GROUPS = ('prophet_activation', 'religion_founding', 'religion_beliefs')
CONTRACTS = (prophet_activation, religion_founding, religion_beliefs)
KINDS = tuple(module.KIND for module in CONTRACTS)


def preceding(index=0, *, levy=False, unit_operations=False):
    """Portable stock/BBG/captured-city predecessor with independent options."""
    value, obs = unit_preceding(index, levy=levy)
    if unit_operations:
        value = add_units(value, obs)
    return value, obs


def state(obs, mode='activation'):
    """Three groups with one consistent synthetic own-religion snapshot."""
    if mode == 'activation':
        active = activation_state(obs)
    elif mode == 'foundation':
        active = foundation_state(obs)
    elif mode in ('beliefs', 'spent'):
        active = belief_state(obs, 'spent' if mode == 'spent' else 'offered')
    elif mode == 'absent':
        active = activation_state(obs, 'no_unit')
    else:
        raise ValueError('Unknown religious fixture phase')
    own = active['own']
    states = {
        group: dict(schema=module.SCHEMA, player_id=obs['player_id'], turn=obs['turn'],
                    own=deepcopy(own), **{field: None})
        for group, module, field in zip(GROUPS, CONTRACTS, ('activation', 'foundation', 'beliefs'))
    }
    if mode in ('activation', 'absent'):
        states['prophet_activation'] = active
    elif mode == 'foundation':
        states['religion_founding'] = active
    else:
        states['religion_beliefs'] = active
    return states


def added(value, obs, *, options=(True, True, True), mode='activation', closed=False):
    current = deepcopy(value)
    states = None if mode is None else state(obs, mode)
    for enabled, group in zip(options, GROUPS):
        if enabled:
            getattr(network, 'add_xp2_' + group)(
                current, None if states is None else states[group], actions_closed=closed)
    return seal(current)


def validate(value, obs, *, closed=False):
    return network.validate_capability_catalogue(value,
        SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation']),
        value['sequence'], obs['turn'], player_id=obs['player_id'], observation=obs,
        actions_closed=closed)


class ChainBackend(SessionBackend):
    def __init__(self, *, mode='activation', options=(True, True, True), unit_operations=True):
        super().__init__()
        self.mode, self.options = mode, options
        self.prior, self.obs = preceding(unit_operations=unit_operations)

    def _reply(self, operation, sequence, **kwargs):
        self.turn = self.obs['turn']
        response = super()._reply(operation, sequence, **kwargs)
        value, obs = deepcopy(self.prior), deepcopy(self.obs)
        for key in ('episode_id', 'game_generation', 'sequence'):
            value[key] = response[key]
        if operation == 'close':
            value = terminal_v11(value)
        else:
            seal(value)
            value = added(value, obs, options=self.options, mode=self.mode)
        response.update(observation=obs, decisions=value)
        return response


class XP2ReligiousChainPublicTests(unittest.TestCase):
    def test_exact_predecessors_independent_layers_and_inherited_memberships(self):
        bases = set(network.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE)
        bases.update(network.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE.values())
        activation = network.XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE
        founding = network.XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE
        beliefs = network.XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE
        self.assertEqual(len(bases), 80)
        self.assertEqual(set(activation), bases)
        self.assertEqual(set(founding), bases | set(activation.values()))
        self.assertEqual(set(beliefs), bases | set(activation.values()) | set(founding.values()))
        memberships = (
            'ATTACK_CAPABILITY_SCHEMAS', 'PUBLIC_COMBAT_CAPABILITY_SCHEMAS',
            'COMBAT_READINESS_CAPABILITY_SCHEMAS', 'CURRENT_PRODUCTION_CAPABILITY_SCHEMAS',
            'NATIVE_COMMAND_PERMISSIONS_SCHEMAS', 'ESPIONAGE_CAPABILITY_SCHEMAS',
            'SPY_COMPLETION_CAPABILITY_SCHEMAS', 'WORLD_CONGRESS_CAPABILITY_SCHEMAS',
            'WORLD_CONGRESS_REVIEW_CAPABILITY_SCHEMAS', 'CONGRESS_ACTIVE_EFFECTS_CAPABILITY_SCHEMAS',
            'STOCK_FORMATION_SCHEMAS', 'DEDICATION_SCHEMAS', 'STOCK_TRADE_CAPABILITY_SCHEMAS',
            'CITY_STATE_LEVY_SCHEMAS', 'UNIT_LEVY_SCHEMAS', 'RELIGIOUS_UNIT_OPERATIONS_SCHEMAS',
        )
        for group, mapping in zip(GROUPS, (activation, founding, beliefs)):
            for base, wrapped in mapping.items():
                self.assertEqual(wrapped, base + '.' + group.replace('_', '-') + '.v1')
                self.assertEqual(network._capability_version(wrapped), network._capability_version(base))
                self.assertTrue(network.is_capability_catalogue({'schema': wrapped}))
                self.assertIn(wrapped, network.SUPPORTED_SCHEMAS)
                for name in memberships:
                    schemas = getattr(network, name)
                    self.assertEqual(base in schemas, wrapped in schemas, (name, base))
            self.assertNotIn(network.CAPABILITY_COMBAT_READINESS_SCHEMA, mapping)
            self.assertFalse(set(mapping) & set(network.XP1_CITY_RELIGION_SCHEMAS))
        self.assertTrue(set(KINDS) <= network.STRATEGIC_READER_FAMILIES)

    def test_retained_stock_bbg_fields_candidates_and_each_flag_survive(self):
        for index, levy, units in product(range(3), (False, True), (False, True)):
            prior, obs = preceding(index, levy=levy, unit_operations=units)
            before = deepcopy(prior)
            current = added(prior, obs)
            validate(current, obs)
            self.assertEqual(before, prior)
            self.assertEqual(current['candidates'][:-1], prior['candidates'])
            self.assertEqual({k:v for k,v in current['families'].items() if k not in KINDS}, prior['families'])
            for key in set(prior) - {'schema', 'decision_id', 'families', 'candidates'}:
                self.assertEqual(current[key], prior[key], (index, levy, units, key))
            for group in GROUPS:
                self.assertEqual(information.project(group, obs, current), state(obs)[group])
            self.assertEqual(current['families']['found_religion']['unqualified'], ['custom_religion_names'])
            self.assertEqual(current['families']['found_religion']['status'], 'queried_partial')
            self.assertFalse(current['complete_action_space'])
            self.assertFalse(current['family_inventory_complete'])
            for forbidden in ('pantheon', 'great_people', 'religion_custom_names', 'great_person_activation'):
                self.assertNotIn(forbidden, current)
        prior, obs = preceding()
        for options in product((False, True), repeat=3):
            current = added(prior, obs, options=options)
            validate(current, obs)
            for enabled, group, kind in zip(options, GROUPS, KINDS):
                self.assertEqual(group in current, enabled)
                self.assertEqual(kind in current['families'], enabled)
                if enabled:
                    with self.assertRaises(ValueError):
                        getattr(network, 'add_xp2_' + group)(current, state(obs)[group])

    def test_checkpoints_project_only_added_layers_and_require_xp2(self):
        prior, obs = preceding(2, levy=True, unit_operations=True)
        current = added(prior, obs, mode='beliefs')
        projected, receipt = network.checkpoint_catalogue(current, prior, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(receipt['added_public_fields'], list(GROUPS))
        self.assertEqual(receipt['added_action_families'], list(KINDS))
        same, change = network.checkpoint_catalogue(current, current, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(same, current)
        self.assertIsNone(change)
        partial = added(prior, obs, options=(True, False, False), mode='beliefs')
        projected, receipt = network.checkpoint_catalogue(current, partial, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, partial)
        self.assertEqual(receipt['added_public_fields'], list(GROUPS[1:]))
        for core in (None, XP1_CORE_SHA256):
            with self.assertRaisesRegex(ValueError, 'Gathering Storm'):
                network.checkpoint_catalogue(current, prior, obs, core_sha256=core)
        oldest, _ = preceding(2)
        projected, receipt = network.checkpoint_catalogue(current, oldest, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, oldest)
        self.assertEqual(receipt['added_public_fields'][-3:], list(GROUPS))
        self.assertIn('religious_unit_operations', receipt['added_public_fields'])

    def test_waiting_closed_permissions_and_real_not_due_are_distinct(self):
        for strategic, tactical in product((False, True), repeat=2):
            prior, obs = permissions_preceding(strategic=strategic, tactical=tactical)
            current = added(prior, obs, mode='activation' if strategic else None)
            validate(current, obs)
            for group, kind in zip(GROUPS, KINDS):
                self.assertEqual(network.family_query_unavailable(current, kind), not strategic)
                self.assertEqual(current[group] is None, not strategic)
            with self.assertRaises(ValueError):
                added(prior, obs, mode=None if strategic else 'activation')
        for phase in ('waiting', 'closed'):
            prior, obs = permissions_preceding(state=phase)
            current = added(prior, obs, mode=None, closed=phase == 'closed')
            validate(current, obs, closed=phase == 'closed')
            for group, kind in zip(GROUPS, KINDS):
                self.assertIsNone(current[group])
                self.assertEqual(current['families'][kind]['status'], 'unqualified')
                with self.assertRaises(ValueError): information.project(group, obs, current)
        prior, obs = preceding()
        for mode in ('spent', 'absent'):
            current = added(prior, obs, mode=mode)
            validate(current, obs)
            for group, module in zip(GROUPS, CONTRACTS):
                self.assertIsNotNone(current[group])
                self.assertEqual(module.actions(current[group]), [])
            if mode == 'spent':
                self.assertEqual(current['religion_beliefs']['beliefs']['status'], 'not_due')

    def test_client_three_actions_information_and_command_outcomes(self):
        for mode, kind in zip(('activation', 'foundation', 'beliefs'), KINDS):
            for status in ('completed', 'refused', 'submitted'):
                backend = ChainBackend(mode=mode)
                backend.next_status = status
                client = SessionClient(backend)
                frame = client.reset()
                for group, module in zip(GROUPS, CONTRACTS):
                    view = client.information(group)
                    self.assertEqual(view['data'], state(frame['observation'], mode)[group])
                    self.assertEqual(view['source_contracts'][group], module.SCHEMA)
                row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == kind)
                for parameters in ({}, {'name': 'custom'}, {'index': 13}):
                    with self.assertRaises(ProtocolError):
                        client.act(0, frame['decisions']['decision_id'], row['candidate_id'], parameters)
                self.assertEqual(backend.calls, [])
                frame = client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
                self.assertEqual(client.command_result['requested_action'], row['action'])
                self.assertEqual(client.command_result['status'], status)
                self.assertEqual(frame['applied_action'], row['action'] if status == 'completed' else None)
                # Refusal/submission does not poison a subsequent explicit choice.
                client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
                copy = client.information('religion_beliefs')
                copy['data']['own']['num_beliefs_earned'] = 999
                self.assertNotEqual(client.information('religion_beliefs')['data']['own']['num_beliefs_earned'], 999)
                with self.assertRaises(InformationUnavailable):
                    client.information('religion_beliefs', player_id=1)

    def test_actor_primitive_choice_and_projection_corruption_refuse(self):
        prior, obs = preceding(unit_operations=True)
        for mode, group, module in zip(('activation', 'foundation', 'beliefs'), GROUPS, CONTRACTS):
            current = added(prior, obs, mode=mode)
            for fault in ('actor', 'private', 'missing_choice', 'old_schema', 'wrong_primitive'):
                bad = deepcopy(current)
                data = bad[group]
                if fault == 'actor': data['player_id'] += 1
                elif fault == 'private': data['own']['source_sha256'] = 'private'
                elif fault == 'old_schema': bad['schema'] = prior['schema']
                elif fault == 'missing_choice':
                    row = next(r for r in bad['candidates'] if r['action']['kind'] == module.KIND)
                    bad['candidates'].remove(row)
                    bad['families'][module.KIND]['candidate_ids'].remove(row['candidate_id'])
                else:
                    row = next(r for r in bad['candidates'] if r['action']['kind'] == module.KIND)
                    row['action']['unit_id' if mode == 'activation' else 'index'] = False
                seal(bad)
                with self.subTest(mode=mode, fault=fault), self.assertRaises(ValueError):
                    validate(bad, obs)
        bad = added(prior, obs, mode='foundation')
        bad['families']['found_religion'].update(status='queried_complete')
        bad['families']['found_religion'].pop('unqualified')
        seal(bad)
        with self.assertRaises(ValueError): validate(bad, obs)
        backend = ChainBackend()
        client = SessionClient(backend)
        frame = client.reset()
        row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == 'activate_prophet')
        backend.fault = 'requested_type'
        with self.assertRaises(ProtocolError):
            client.act(0, frame['decisions']['decision_id'], row['candidate_id'])

    def test_legacy_xp1_and_reduced_terminal_do_not_acquire_xp2_layers(self):
        old = SessionClient(ChainBackend(options=(False, False, False)))
        legacy = old.reset()
        for group in GROUPS:
            self.assertNotIn(group, legacy['decisions'])
            with self.assertRaises(InformationUnavailable): old.information(group)
        xp1 = SessionClient(ProphetBackend())
        retained = xp1.reset()
        self.assertIn(retained['decisions']['schema'], network.XP1_PROPHET_ACTIVATION_SCHEMAS)
        self.assertNotIn(retained['decisions']['schema'], network.XP2_PROPHET_ACTIVATION_SCHEMAS)
        self.assertIsNotNone(xp1.information('prophet_activation')['data'])
        with self.assertRaises(ValueError):
            network.add_xp2_prophet_activation(retained['decisions'], state(retained['observation'])['prophet_activation'])
        client = SessionClient(ChainBackend())
        client.reset()
        closed = client.close()
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['candidates'], [])
        for group in GROUPS:
            self.assertNotIn(group, closed['decisions'])
            with self.assertRaises(InformationUnavailable): client.information(group)
            with self.assertRaises(ValueError):
                getattr(network, 'add_xp2_' + group)(closed['decisions'], None, actions_closed=True)


if __name__ == '__main__':
    unittest.main()

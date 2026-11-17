"""XP2 religious choices over retained public states; no native execution.

The new religious data and command outcomes are synthetic. Existing stock/BBG
fields come from hash-checked retained fixtures; this is not native acceptance.
"""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import information, network_turn as network
from civ6_host.contracts import religious_unit_operations as contract
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
import test_native_command_permissions as permissions
import test_xp2_military_levy_catalogue as levies
import test_xp1_city_religion_details_public as city_details
from test_session_client import Backend as SessionBackend
from test_session_capabilities import seal
from test_xp1_religious_unit_operations_public import native_state, state
from test_xp1_religion_beliefs_public import terminal_v11


def preceding(index=0, *, levy=False):
    """Portable retained stock/BBG predecessor plus optional synthetic levy."""
    relative, expected = levies.FIXTURES[index]
    path = Path(os.environ['CIV6_HOST_RESOURCE_ROOT']) / relative
    if path.stat().st_size >= 1024**2:
        raise ValueError('Retained public checkpoint exceeds metadata bound')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('Retained public checkpoint changed')
    saved = json.loads(raw.decode('utf-8'))
    value, obs = saved['decisions'], saved['observation']
    if levy:
        value = levies.XP2MilitaryLevyCatalogueTests().added(value, obs)
    return value, obs


def permissions_preceding(*, strategic=True, tactical=True, state='active'):
    """v39 fixture with explicit native-permission results, not inferred rules."""
    response = permissions.NativeCommandPermissionsTests().retained_v38('waiting' if state == 'closed' else state)
    value, obs = response['decisions'], response['observation']
    if not strategic:
        value = permissions.unavailable_readers(value)
    value = network.upgrade_command_permissions_catalogue(
        value, permissions.permissions(value, strategic, tactical), obs)
    if state == 'closed':
        # Source fixture retains active/waiting only. Model closure explicitly;
        # the separate client test preserves the actual reduced-v11 terminal.
        value['strategic_resources'] = None
        value['candidates'] = []
        value['turn_availability'] = {key:None for key in value['turn_availability']}
        value['families'] = {key:dict(status='unqualified', reason='session_closed') for key in value['families']}
        seal(value)
    return value, obs


def validate(value, obs, *, closed=False):
    return network.validate_capability_catalogue(value,
        SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation']),
        value['sequence'], obs['turn'], player_id=obs['player_id'], observation=obs,
        actions_closed=closed)


def added(value, obs, *, data='offered', closed=False):
    current = deepcopy(value)
    network.add_xp2_religious_unit_operations(
        current, None if data is None else state(obs, data), actions_closed=closed)
    return seal(current)


class ReligiousBackend(SessionBackend):
    """Real client with retained v34 fields and synthetic religious replies."""
    def __init__(self, *, mode='offered', enabled=True):
        super().__init__()
        self.mode, self.enabled = mode, enabled
        self.prior, self.obs = preceding()

    def _reply(self, operation, sequence, **kwargs):
        self.turn = self.obs['turn']
        response = super()._reply(operation, sequence, **kwargs)
        value, obs = deepcopy(self.prior), deepcopy(self.obs)
        for name in ('episode_id', 'game_generation', 'sequence'):
            value[name] = response[name]
        if operation == 'close':
            value = terminal_v11(value)
        else:
            seal(value)
            if self.enabled:
                value = added(value, obs, data=self.mode)
        response.update(observation=obs, decisions=value)
        if operation == 'act':
            status = response['command_result']['status']
            if status == 'refused':
                response['command_result']['reason'] = 'native_religious_unit_operation_can_start_false'
            elif status == 'submitted':
                response['command_result']['reason'] = 'native_religious_unit_operation_processed_effect_unconfirmed'
        return response


class XP2ReligiousUnitOperationsPublicTests(unittest.TestCase):
    def test_bounded_schema_map_preserves_every_inherited_capability_membership(self):
        mapping = network.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE
        self.assertEqual(len(mapping), 40)
        self.assertEqual(len(set(mapping.values())), 40)
        for base, wrapped in mapping.items():
            self.assertEqual(wrapped, base + '.religious-unit-operations.v1')
            self.assertTrue(network.is_capability_catalogue({'schema': wrapped}))
            self.assertEqual(network._capability_version(wrapped), network._capability_version(base))
            for name in ('ATTACK_CAPABILITY_SCHEMAS', 'PUBLIC_COMBAT_CAPABILITY_SCHEMAS',
                         'COMBAT_READINESS_CAPABILITY_SCHEMAS', 'CURRENT_PRODUCTION_CAPABILITY_SCHEMAS',
                         'NATIVE_COMMAND_PERMISSIONS_SCHEMAS', 'ESPIONAGE_CAPABILITY_SCHEMAS',
                         'SPY_COMPLETION_CAPABILITY_SCHEMAS', 'WORLD_CONGRESS_CAPABILITY_SCHEMAS',
                         'WORLD_CONGRESS_REVIEW_CAPABILITY_SCHEMAS', 'CONGRESS_ACTIVE_EFFECTS_CAPABILITY_SCHEMAS',
                         'STOCK_FORMATION_SCHEMAS', 'DEDICATION_SCHEMAS', 'STOCK_TRADE_CAPABILITY_SCHEMAS',
                         'CITY_STATE_LEVY_SCHEMAS', 'UNIT_LEVY_SCHEMAS'):
                schemas = getattr(network, name)
                self.assertEqual(base in schemas, wrapped in schemas, (name, base))
        for unsupported in (network.CAPABILITY_COMBAT_READINESS_SCHEMA,
                            network.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,
                            *network.XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS):
            self.assertNotIn(unsupported, mapping)
        # Contracts describe wire formats; source/image/capture admission is runtime-owned.
        self.assertTrue(set(contract.KINDS) <= network.STRATEGIC_READER_FAMILIES)

    def test_retained_stock_bbg_captured_city_and_levies_keep_old_fields_and_candidates(self):
        for index in range(3):
            for levy in (False, True):
                prior, obs = preceding(index, levy=levy)
                before = deepcopy(prior)
                current = added(prior, obs)
                validate(current, obs)
                self.assertEqual(prior, before)
                self.assertEqual(current['candidates'][:-4], prior['candidates'])
                self.assertEqual({k:v for k,v in current['families'].items() if k not in contract.KINDS}, prior['families'])
                for key in set(prior) - {'schema', 'decision_id', 'families', 'candidates'}:
                    self.assertEqual(current[key], prior[key], (index, levy, key))
                self.assertEqual(information.project('religious_unit_operations', obs, current), state(obs))
                if levy:
                    for group in ('city_state_levies', 'unit_levies'):
                        self.assertEqual(information.project(group, obs, current), prior[group])
                if 'captured_city' in prior:
                    self.assertEqual(current['captured_city'], prior['captured_city'])
                self.assertFalse(current['complete_action_space'])
                self.assertFalse(current['family_inventory_complete'])
                with self.assertRaises(ValueError):
                    network.add_xp2_religious_unit_operations(current, state(obs))

    def test_permissions_waiting_and_closed_do_not_become_successful_empty_queries(self):
        for strategic in (False, True):
            for tactical in (False, True):
                prior, obs = permissions_preceding(strategic=strategic, tactical=tactical)
                current = added(prior, obs, data='offered' if strategic else None)
                validate(current, obs)
                self.assertEqual(network.is_waiting(current['turn_controls']), False)
                for kind in contract.KINDS:
                    self.assertEqual(network.family_query_unavailable(current, kind), not strategic)
                    self.assertEqual(current['families'][kind]['status'], 'queried_complete' if strategic else 'unqualified')
                with self.assertRaises(ValueError):
                    added(prior, obs, data=None if strategic else 'hidden')
        for phase in ('waiting', 'closed'):
            prior, obs = permissions_preceding(state=phase)
            current = added(prior, obs, data=None, closed=phase == 'closed')
            validate(current, obs, closed=phase == 'closed')
            self.assertIsNone(current['religious_unit_operations'])
            with self.assertRaises(ValueError): information.project('religious_unit_operations', obs, current)
        prior, obs = preceding()
        for mode in ('hidden', 'blocked'):
            current = added(prior, obs, data=mode); validate(current, obs)
            self.assertIsNotNone(current['religious_unit_operations'])
            self.assertEqual(contract.actions(current['religious_unit_operations']), [])
            self.assertTrue(all(current['families'][kind]['status'] == 'queried_complete' for kind in contract.KINDS))

    def test_checkpoint_projection_is_additive_and_requires_correct_engine(self):
        for index in range(3):
            for levy in (False, True):
                prior, obs = preceding(index, levy=levy)
                current = added(prior, obs)
                projected, receipt = network.checkpoint_catalogue(current, prior, obs, core_sha256=XP2_CORE_SHA256)
                self.assertEqual(projected, prior)
                self.assertEqual(receipt['added_public_fields'], ['religious_unit_operations'])
                self.assertEqual(receipt['added_action_families'], list(contract.KINDS))
                same, change = network.checkpoint_catalogue(current, current, obs, core_sha256=XP2_CORE_SHA256)
                self.assertEqual(same, current); self.assertIsNone(change)
                for wrong in (None, XP1_CORE_SHA256):
                    with self.assertRaisesRegex(ValueError, 'Gathering Storm'):
                        network.checkpoint_catalogue(current, prior, obs, core_sha256=wrong)
                if levy:
                    oldest, _ = preceding(index)
                    projected, receipt = network.checkpoint_catalogue(current, oldest, obs, core_sha256=XP2_CORE_SHA256)
                    self.assertEqual(projected, oldest)
                    self.assertEqual(receipt['added_public_fields'], ['city_state_levies', 'unit_levies', 'religious_unit_operations'])
                    self.assertEqual(receipt['added_action_families'][-4:], list(contract.KINDS))

    def test_client_four_actions_information_and_completed_refused_submitted_receipts(self):
        for status in ('completed', 'refused', 'submitted'):
            backend = ReligiousBackend(); backend.next_status = status
            client = SessionClient(backend); frame = client.reset()
            info = client.information('religious_unit_operations')
            self.assertEqual(info['data'], state(frame['observation']))
            self.assertEqual(info['source_contracts']['religious_unit_operations'], contract.SCHEMA)
            self.assertEqual(backend.calls, [])
            for kind in contract.KINDS:
                row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == kind)
                count = len(backend.calls)
                for params in ({}, {'x': row['action']['x']}, {'operation_index': 1}):
                    with self.assertRaises(ProtocolError):
                        client.act(0, frame['decisions']['decision_id'], row['candidate_id'], params)
                self.assertEqual(len(backend.calls), count)
                frame = client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
                self.assertEqual(client.command_result['requested_action'], row['action'])
                self.assertEqual(client.command_result['status'], status)
                self.assertEqual(frame['applied_action'], row['action'] if status == 'completed' else None)
                self.assertEqual(client.last_command_receipt(0)['command_result'], client.command_result)
                if status == 'submitted':
                    self.assertEqual(client.command_result['reason'], 'native_religious_unit_operation_processed_effect_unconfirmed')
            info['data']['units'][0]['spread_charges'] = 99
            self.assertEqual(client.information('religious_unit_operations')['data']['units'][0]['spread_charges'], -1)
            with self.assertRaises(InformationUnavailable): client.information('religious_unit_operations', player_id=1)

    def test_unknown_foreign_offers_roster_and_fractional_precision_are_rejected(self):
        prior, obs = preceding()
        fractional = deepcopy(obs); fractional['units'][0]['moves'] = 1/256
        self.assertEqual(state(fractional)['units'][0]['moves_remaining'], 1/256)
        value = added(prior, obs); validate(value, obs)
        for change in ('actor', 'unit', 'position', 'precision', 'inquisition', 'missing_offer',
                       'extra_offer', 'family', 'old_schema', 'unknown_field'):
            bad = deepcopy(value); data = bad['religious_unit_operations']
            if change == 'actor': data['player_id'] += 1
            elif change == 'unit': data['units'][0]['unit_id'] += 1
            elif change == 'position': data['units'][0]['x'] += 1
            elif change == 'precision': data['units'][0]['moves_remaining'] = .1
            elif change == 'inquisition': data['inquisition_started'] = 1
            elif change == 'missing_offer':
                removed = bad['candidates'].pop(); bad['families'][removed['action']['kind']]['candidate_ids'].pop()
            elif change == 'extra_offer':
                action = dict(bad['candidates'][-1]['action'], x=99)
                key = network.digest(action)
                bad['candidates'].append(dict(candidate_id=key, action=action))
                bad['families'][action['kind']]['candidate_ids'].append(key)
            elif change == 'family':
                bad['families'][contract.KINDS[0]].update(status='queried_partial', unqualified=['omitted'])
            elif change == 'old_schema': bad['schema'] = prior['schema']
            else: data['enemy_religions'] = []
            seal(bad)
            with self.subTest(change=change), self.assertRaises(ValueError): validate(bad, obs)
        for fault in ('requested_type', 'applied_type', 'conflicting_action'):
            backend = ReligiousBackend(); client = SessionClient(backend); frame = client.reset()
            row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == contract.KINDS[0])
            backend.fault = fault
            with self.subTest(fault=fault), self.assertRaises(ProtocolError):
                client.act(0, frame['decisions']['decision_id'], row['candidate_id'])

    def test_legacy_client_and_reduced_v11_terminal_remain_unchanged(self):
        legacy = SessionClient(ReligiousBackend(enabled=False)); old = legacy.reset()
        self.assertNotIn('religious_unit_operations', old['decisions'])
        with self.assertRaises(InformationUnavailable): legacy.information('religious_unit_operations')
        client = SessionClient(ReligiousBackend()); client.reset(); closed = client.close()
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertIsNotNone(closed['observation'])
        self.assertNotIn('religious_unit_operations', closed['decisions'])
        self.assertEqual(closed['decisions']['candidates'], [])
        with self.assertRaises(InformationUnavailable): client.information('religious_unit_operations')
        with self.assertRaises(ValueError):
            network.add_xp2_religious_unit_operations(closed['decisions'], None, actions_closed=True)

    def test_xp1_religious_and_city_details_revision_still_composes_without_xp2(self):
        client = SessionClient(city_details.DetailsBackend()); frame = client.reset()
        value, obs = frame['decisions'], frame['observation']
        validate(value, obs)
        self.assertIn(value['schema'], network.XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
        self.assertNotIn(value['schema'], network.XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
        self.assertEqual(client.information('religious_unit_operations')['data'], state(obs))
        self.assertEqual(client.information('city_religion')['data']['schema'], 'civ6-host.city-religion.v2')
        self.assertEqual(len([r for r in value['candidates'] if r['action']['kind'] in contract.KINDS]), 4)
        with self.assertRaises(ValueError): network.add_xp2_religious_unit_operations(value, state(obs))


if __name__ == '__main__':
    unittest.main()

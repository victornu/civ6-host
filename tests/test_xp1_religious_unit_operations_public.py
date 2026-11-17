"""Public own-unit religious choices over the real client, without native calls."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, religious_unit_operations as contract
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.session_client import _validate_command
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_great_person_activation_public import (
    preceding as old_preceding, combinations as old_combinations, state as gp_state)
from test_xp1_religion_beliefs_public import validate, unavailable, terminal_v11


def native_state(obs, mode='offered'):
    rows = []
    for index, unit in enumerate(sorted(obs['units'], key=lambda row: row['id'])):
        operations = []
        if index == 0 and unit['moves'] > 0 and mode != 'hidden':
            operations = [dict(operation=kind, visible=True, available=mode != 'blocked')
                          for kind in contract.KINDS]
        rows.append(dict(unit_id=unit['id'], x=unit['x'], y=unit['y'],
                         moves_remaining=unit['moves'], religion_type=-1,
                         spread_charges=-1, operations=operations))
    return dict(player_id=obs['player_id'], current_game_turn=obs['turn'],
                inquisition_started=False, units=rows)


def state(obs, mode='offered'):
    return contract.project(native_state(obs, mode), obs['player_id'], obs['turn'], observation=obs)


def preceding(value, obs, options=(True, True, True, 3, True, True), *,
              gp_activation=True, waiting=False):
    old_preceding(value, obs, options, waiting=waiting)
    if gp_activation:
        network.add_xp1_great_person_activation(value, None if waiting else gp_state(obs))
    return seal(value)


class ReligiousBackend(ReligionBackend):
    def __init__(self, *, mode='offered', waiting=False):
        super().__init__()
        self.mode, self.waiting = mode, waiting

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
        preceding(dec, obs, waiting=self.waiting)
        network.add_xp1_religious_unit_operations(dec, None if self.waiting else state(obs, self.mode))
        seal(dec)
        if operation == 'act' and self.status == 'refused':
            value['command_result']['reason'] = 'native_religious_unit_operation_can_start_false'
        if operation == 'act' and self.status == 'submitted':
            value['command_result']['reason'] = 'native_religious_unit_operation_processed_effect_unconfirmed'
        return value


class XP1ReligiousUnitOperationsPublicTests(unittest.TestCase):
    def test_native_projection_preserves_q8_signed_values_and_actor_boolean(self):
        obs = deepcopy(religion_fixture()[0])
        for movement in (-(2**23), -1/256, 0, 1/256, 1.5, (2**31-1)/256):
            obs['units'][0]['moves'] = movement
            for scalar in (-(2**31), -1, 0, 2**31-1):
                raw = native_state(obs)
                raw['units'][0].update(religion_type=scalar, spread_charges=scalar)
                raw['inquisition_started'] = True
                value = contract.project(raw, obs['player_id'], obs['turn'], observation=obs)
                self.assertEqual(value['units'], raw['units'])
                self.assertIs(value['inquisition_started'], True)
                raw['units'][0]['spread_charges'] = 7
                self.assertEqual(value['units'][0]['spread_charges'], scalar)
        for bad in (True, None, '1', float('nan'), float('inf'), .1, 2**23, -(2**23)-1/256, 10**400):
            value = state(religion_fixture()[0])
            value['units'][0]['moves_remaining'] = bad
            with self.subTest(moves=repr(bad)[:50]), self.assertRaises(ValueError):
                contract.validate(value, value['player_id'], value['turn'])
        self.assertEqual(contract.actions(None), [])

    def test_visible_subset_retains_native_unavailability_and_exact_ui_movement_gate(self):
        obs = religion_fixture()[0]
        for selected in product((False, True), repeat=4):
            value = state(obs)
            value['units'][0]['operations'] = [dict(operation=k, visible=True, available=True)
                for k, include in zip(contract.KINDS, selected) if include]
            contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
            self.assertEqual([a['kind'] for a in contract.actions(value)],
                             [k for k, include in zip(contract.KINDS, selected) if include])
        blocked = state(obs, 'blocked')
        self.assertEqual(len(blocked['units'][0]['operations']), 4)
        self.assertEqual(contract.actions(blocked), [])
        self.assertEqual(state(obs, 'hidden')['units'][0]['operations'], [])
        # Negative charges/religion are source scalar domains, not Python admission rules.
        self.assertEqual(len(contract.actions(state(obs))), 4)
        stopped = deepcopy(obs)
        stopped['units'][0]['moves'] = 0
        self.assertEqual(state(stopped)['units'][0]['operations'], [])
        bad = state(stopped)
        bad['units'][0]['operations'] = [dict(operation=contract.KINDS[0], visible=True, available=False)]
        with self.assertRaises(ValueError):
            contract.validate(bad, stopped['player_id'], stopped['turn'], observation=stopped)

    def test_roster_identity_scope_order_and_types_cannot_be_widened(self):
        obs = religion_fixture()[0]
        value = state(obs)
        for mutation in ('actor', 'turn', 'missing', 'foreign', 'position', 'moves', 'owner',
                         'duplicate', 'extra', 'charge_bool', 'charge_over', 'religion_over',
                         'flag_int', 'inquisition_int', 'invisible', 'op_duplicate', 'op_order', 'op_unknown'):
            bad, own = deepcopy(value), deepcopy(obs)
            row = bad['units'][0]
            if mutation == 'actor': bad['player_id'] = True
            elif mutation == 'turn': bad['turn'] += 1
            elif mutation == 'missing': bad['units'].pop()
            elif mutation == 'foreign': row['unit_id'] += 1000
            elif mutation == 'position': row['x'] += 1
            elif mutation == 'moves': row['moves_remaining'] += 1/256
            elif mutation == 'owner': own['units'][0]['owner'] += 1
            elif mutation == 'duplicate': bad['units'].append(deepcopy(row))
            elif mutation == 'extra': row['class_index'] = 4
            elif mutation == 'charge_bool': row['spread_charges'] = True
            elif mutation == 'charge_over': row['spread_charges'] = 2**31
            elif mutation == 'religion_over': row['religion_type'] = -(2**31)-1
            elif mutation == 'flag_int': row['operations'][0]['available'] = 1
            elif mutation == 'inquisition_int': bad['inquisition_started'] = 1
            elif mutation == 'invisible': row['operations'][0]['visible'] = False
            elif mutation == 'op_duplicate': row['operations'][1] = deepcopy(row['operations'][0])
            elif mutation == 'op_order': row['operations'].reverse()
            else: row['operations'][0]['operation'] = 'unit_order'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate(bad, obs['player_id'], obs['turn'], observation=own)
        with self.assertRaises(ValueError): contract.project(native_state(obs), obs['player_id']+1, obs['turn'])
        action = dict(kind=contract.KINDS[0], unit_id=0xffffffff, x=-(2**31), y=2**31-1)
        self.assertEqual(contract.validate_action(action), action)
        for change in ({'unit_id': True}, {'unit_id': 2**32}, {'x': 2**31}, {'y': 1.5},
                       {'parameters': {}}, {'target_city_id': 1}, {'kind': 'activate_prophet'}):
            with self.assertRaises(ValueError): contract.validate_action(dict(action, **change))

    def test_all_192_predecessors_keep_old_data_families_and_choices(self):
        obs, _, _, city = religion_fixture()
        count = 0
        for options in old_combinations():
            for gp_activation in (False, True):
                prior = preceding(deepcopy(city), obs, options, gp_activation=gp_activation)
                value = deepcopy(prior)
                network.add_xp1_religious_unit_operations(value, state(obs))
                validate(obs, value)
                self.assertEqual(value['candidates'][:-4], prior['candidates'])
                self.assertEqual({k:v for k,v in value['families'].items() if k not in contract.KINDS}, prior['families'])
                for key in set(prior)-{'schema','decision_id','families','candidates'}:
                    self.assertEqual(value[key], prior[key], (options, gp_activation, key))
                for schemas, expected in ((network.XP1_GREAT_PERSON_ACTIVATION_SCHEMAS, gp_activation),
                                          (network.XP1_RELIGION_CUSTOM_NAMES_SCHEMAS, options[5]),
                                          (network.XP1_GREAT_PEOPLE_REJECT_SCHEMAS, options[3] >= 3),
                                          (network.XP1_PROPHET_ACTIVATION_SCHEMAS, options[4])):
                    self.assertEqual(value['schema'] in schemas, expected)
                self.assertFalse(value['complete_action_space'])
                self.assertFalse(value['family_inventory_complete'])
                with self.assertRaises(ValueError): network.add_xp1_religious_unit_operations(value, state(obs))
                count += 1
        self.assertEqual(count, 192)

    def test_checkpoints_remove_only_new_information_and_four_families(self):
        obs, _, _, city = religion_fixture()
        for options in ((False,False,False,0,False,False), (True,True,True,3,True,True)):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            network.add_xp1_religious_unit_operations(value, state(obs))
            validate(obs, value)
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(receipt['added_public_fields'], ['religious_unit_operations'])
            self.assertEqual(receipt['added_action_families'], list(contract.KINDS))
            projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, city)
            self.assertEqual(receipt['added_public_fields'][-1], 'religious_unit_operations')
            self.assertEqual(receipt['added_action_families'][-4:], list(contract.KINDS))
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            changed = deepcopy(value)
            changed['choice_state']['research']['research'] = 123
            seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs, core_sha256=XP1_CORE_SHA256)[0], prior)

    def test_client_four_dispatches_completed_refused_and_submitted_allow_next_choice(self):
        for status in ('completed', 'refused', 'submitted'):
            backend = ReligiousBackend()
            backend.status = status
            client = SessionClient(backend)
            frame = client.reset()
            info = client.information('religious_unit_operations')
            self.assertEqual(info['data'], state(frame['observation']))
            self.assertEqual(info['source_contracts']['religious_unit_operations'], contract.SCHEMA)
            for group in ('great_person_activation','religion_custom_names','religion_founding',
                          'great_people','prophet_activation','pantheon','religion_beliefs'):
                client.information(group)
            for kind in contract.KINDS:
                row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == kind)
                calls_before = len(backend.calls)
                for parameters in ({}, {'x': row['action']['x']}, {'target_city_id': 1}):
                    with self.assertRaises(ProtocolError):
                        client.act(0, frame['decisions']['decision_id'], row['candidate_id'], parameters)
                self.assertEqual(len(backend.calls), calls_before)
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

    def test_waiting_empty_hidden_blocked_absent_and_reduced_v11_are_distinct(self):
        obs = deepcopy(religion_fixture()[0])
        obs['units'] = []
        self.assertEqual(state(obs)['units'], [])
        for mode in ('hidden', 'blocked'):
            client = SessionClient(ReligiousBackend(mode=mode))
            frame = client.reset()
            self.assertEqual(client.information('religious_unit_operations')['data'], state(frame['observation'], mode))
            for kind in contract.KINDS:
                self.assertEqual(frame['decisions']['families'][kind], dict(status='queried_complete', candidate_ids=[]))
        waiting = SessionClient(ReligiousBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['religious_unit_operations'])
        for kind in contract.KINDS: self.assertEqual(frame['decisions']['families'][kind]['status'], 'unqualified')
        with self.assertRaises(InformationUnavailable): waiting.information('religious_unit_operations')
        legacy = SessionClient(ReligionBackend())
        legacy.reset()
        with self.assertRaises(InformationUnavailable): legacy.information('religious_unit_operations')
        client = SessionClient(ReligiousBackend())
        client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('religious_unit_operations', closed['decisions'])
        with self.assertRaises(InformationUnavailable): client.information('religious_unit_operations')
        with self.assertRaises(ValueError): network.add_xp1_religious_unit_operations(closed['decisions'], None, actions_closed=True)

    def test_exact_offer_sets_and_receipts_reject_omission_or_substitution(self):
        obs, _, _, city = religion_fixture()
        value = deepcopy(city)
        network.add_xp1_religious_unit_operations(value, state(obs))
        validate(obs, value)
        for mutation in ('omitted', 'position', 'unavailable', 'old_schema', 'partial'):
            bad = deepcopy(value)
            row = bad['candidates'][-1]
            kind = row['action']['kind']
            if mutation == 'omitted': bad['candidates'].pop(); bad['families'][kind]['candidate_ids'] = []
            elif mutation == 'position':
                row['action']['x'] += 1
                row['candidate_id'] = network.digest(row['action'])
                bad['families'][kind]['candidate_ids'] = [row['candidate_id']]
            elif mutation == 'unavailable': bad['religious_unit_operations']['units'][0]['operations'][-1]['available'] = False
            elif mutation == 'old_schema': bad['schema'] = city['schema']
            else: bad['families'][kind].update(status='queried_partial', unqualified=['missing'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(obs, bad)
        for action in contract.actions(state(obs)):
            for status in ('completed', 'refused', 'submitted'):
                receipt = dict(status=status, reason=None, requested_action=action)
                self.assertEqual(_validate_command(receipt), receipt)
            for changes in ({'unit_id': True}, {'x': 2**31}, {'operation': 123}, {'target_city_id': 1}):
                with self.assertRaises(ProtocolError):
                    _validate_command(dict(status='completed', reason=None, requested_action=dict(action, **changes)))
        backend = ReligiousBackend()
        client = SessionClient(backend)
        frame = client.reset()
        row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == contract.KINDS[0])
        def corrupt(reply):
            reply['command_result']['requested_action']['unit_id'] += 1
            reply['applied_action']['unit_id'] = reply['command_result']['requested_action']['unit_id']
        backend.fault = corrupt
        with self.assertRaisesRegex(ProtocolError, 'Requested action differs'):
            client.act(0, frame['decisions']['decision_id'], row['candidate_id'])


if __name__ == '__main__':
    unittest.main()

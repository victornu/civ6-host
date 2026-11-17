"""Opt-in native rejection quotes, additive versioning and real client dispatch."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, great_people_actions as contract
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.session_client import _validate_command
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture
from test_xp1_great_people_actions_public import CommandsBackend, preceding, state
from test_xp1_religion_beliefs_public import validate


def prior_catalogue(obs, city, options=(True, True, True, True), *, cost=-9):
    value = preceding(deepcopy(city), obs, options)
    value['great_people']['timeline'][2]['rejection']['cost'] = cost
    network.add_xp1_great_people_actions(value)
    return seal(value)


class RejectBackend(CommandsBackend):
    def __init__(self, *, refused=False, **kwargs):
        super().__init__(**kwargs)
        self.refused = refused

    def _reply(self, operation, sequence, player, requested=None):
        value = super()._reply(operation, sequence, player, requested)
        dec = value['decisions']
        if 'great_people' in dec:
            if dec['great_people'] is not None and self.mode == 'offers':
                dec['great_people']['timeline'][2]['rejection']['cost'] = -9
            network.add_xp1_great_people_reject(dec, actions_closed=operation == 'close')
            seal(dec)
        if self.refused and operation == 'act':
            value['command_result'].update(status='refused', reason='native_can_start_false')
            value['applied_action'] = None
        return value


class XP1GreatPeopleRejectPublicTests(unittest.TestCase):
    def test_signed_quote_and_opt_in_preserve_legacy_native_offers(self):
        obs = religion_fixture()[0]
        value = state(obs)
        legacy = contract.actions(value)
        for cost in (-(2**31), -9, -1, 0, 2, 2**31-1):
            value['timeline'][2]['rejection']['cost'] = cost
            expected = dict(kind=contract.REJECT, individual_index=51, cost=cost)
            self.assertEqual(contract.actions(value), legacy)
            self.assertEqual(contract.actions(value, include_reject=True), legacy+[expected])
            self.assertFalse(value['timeline'][2]['recruitment']['available'])
        # Public code copies native flags; a second offered rejection is not
        # suppressed because Python considers another action more desirable.
        value['timeline'][0]['rejection'].update(available=True, cost=-2)
        choices = contract.actions(value, include_reject=True)
        self.assertEqual(choices[2], dict(kind=contract.REJECT, individual_index=117, cost=-2))
        self.assertEqual([a for a in choices if a['kind'] != contract.REJECT], legacy)
        value['timeline'][2]['rejection']['available'] = False
        self.assertFalse(any(a['individual_index'] == 51 for a in contract.actions(value, include_reject=True)))

    def test_strict_signed_int32_identity_and_quote_validation(self):
        valid = dict(kind=contract.REJECT, individual_index=51, cost=-9)
        self.assertEqual(contract.validate_action(valid), valid)
        for key, invalid in (('cost', True), ('cost', None), ('cost', -(2**31)-1),
                             ('cost', 2**31), ('cost', -1.5), ('individual_index', -1),
                             ('individual_index', True), ('individual_index', 2**31)):
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                contract.validate_action(dict(valid, **{key:invalid}))
        for extra in ({'currency':'YIELD_FAITH'}, {'player_id':0}, {'hash':1}):
            with self.assertRaises(ValueError): contract.validate_action(dict(valid, **extra))
        with self.assertRaises(ValueError): contract.actions(None, include_reject=1)
        value = state(religion_fixture()[0])
        value['timeline'][2]['rejection']['cost'] = None
        with self.assertRaises(ValueError): contract.actions(value, include_reject=True)
        # The old nonnegative acquisition quotes retain their prior contract.
        for kind in contract.LEGACY_KINDS:
            bad = dict(kind=kind, individual_index=51, cost=-1)
            if kind == contract.PATRONIZE: bad['currency'] = 'YIELD_FAITH'
            with self.assertRaises(ValueError): contract.validate_action(bad)

    def test_sixteen_predecessors_retain_data_families_and_legacy_schema(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=4):
            prior = prior_catalogue(obs, city, options)
            validate(obs, prior)
            self.assertNotIn(contract.REJECT, prior['families'])
            value = deepcopy(prior)
            network.add_xp1_great_people_reject(value)
            validate(obs, value)
            self.assertEqual(set(value), set(prior))
            self.assertEqual(value['candidates'][:-1], prior['candidates'])
            self.assertEqual({k:v for k,v in value['families'].items() if k != contract.REJECT}, prior['families'])
            for key in set(prior)-{'schema','decision_id','families','candidates'}:
                self.assertEqual(value[key], prior[key], (options,key))
            self.assertEqual(value['schema'], network.XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE[prior['schema']])
            for schemas in (network.XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS, network.XP1_GREAT_PEOPLE_SCHEMAS,
                            network.XP1_CITY_RELIGION_SCHEMAS):
                self.assertIn(value['schema'], schemas)
            self.assertEqual(value['schema'] in network.XP1_PROPHET_ACTIVATION_SCHEMAS, options[3])
            self.assertFalse(value['complete_action_space'])
            self.assertFalse(value['family_inventory_complete'])
            self.assertNotIn('activate_great_person', value['families'])
            with self.assertRaises(ValueError): network.add_xp1_great_people_reject(value)
        with self.assertRaises(ValueError): network.add_xp1_great_people_reject(deepcopy(city))

    def test_checkpoint_projection_removes_only_rejection_before_prior_layers(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=4):
            prior = prior_catalogue(obs, city, options)
            value = deepcopy(prior)
            network.add_xp1_great_people_reject(value)
            validate(obs, value)
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(receipt['added_action_families'], [contract.REJECT])
            self.assertEqual(receipt.get('added_public_fields', []), [])
            projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, city)
            self.assertEqual(receipt['added_action_families'][-3:], list(contract.KINDS))
            self.assertIn('great_people', receipt['added_public_fields'])
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            changed = deepcopy(value)
            changed['great_people']['own_points'][0]['points_total'] = 19
            seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs, core_sha256=XP1_CORE_SHA256)[0], prior)

    def test_actual_client_dispatches_signed_rejection_and_preserves_information(self):
        for refused in (False, True):
            backend = RejectBackend(refused=refused)
            client = SessionClient(backend)
            frame = client.reset()
            before = client.information('great_people')
            for group in ('pantheon','religion_beliefs','religion_founding','prophet_activation'):
                client.information(group)
            row = next(r for r in frame['decisions']['candidates'] if r['action']['kind'] == contract.REJECT)
            self.assertEqual(row['action']['cost'], -9)
            with self.assertRaises(ProtocolError):
                client.act(0, frame['decisions']['decision_id'], row['candidate_id'], parameters={'cost':0})
            self.assertEqual(backend.calls, [])
            reply = client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
            self.assertEqual(reply['applied_action'], None if refused else row['action'])
            self.assertEqual(client.command_result['requested_action'], row['action'])
            self.assertEqual(client.command_result['status'], 'refused' if refused else 'completed')
            self.assertEqual(client.last_command_receipt(0)['command_result'], client.command_result)
            self.assertEqual(client.information('great_people')['data'], before['data'])

    def test_rejection_candidates_must_match_native_set_cost_and_revision(self):
        obs, _, _, city = religion_fixture()
        value = prior_catalogue(obs, city)
        network.add_xp1_great_people_reject(value)
        validate(obs, value)
        for mutation in ('omitted','extra','cost','index','old_schema','partial'):
            bad = deepcopy(value)
            row = bad['candidates'][-1]
            if mutation == 'omitted':
                bad['candidates'].pop()
                bad['families'][contract.REJECT]['candidate_ids'] = []
            elif mutation == 'extra':
                action = dict(kind=contract.REJECT, individual_index=50, cost=-9)
                key = network.digest(action)
                bad['candidates'].append(dict(candidate_id=key, action=action))
                bad['families'][contract.REJECT]['candidate_ids'].append(key)
            elif mutation in ('cost','index'):
                row['action']['cost' if mutation == 'cost' else 'individual_index'] = 0
                row['candidate_id'] = network.digest(row['action'])
                bad['families'][contract.REJECT]['candidate_ids'] = [row['candidate_id']]
            elif mutation == 'old_schema': bad['schema'] = network._XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA[bad['schema']]
            else: bad['families'][contract.REJECT].update(status='queried_partial', unqualified=['missing'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(obs, bad)

    def test_waiting_empty_disabled_and_terminal_v11_remain_distinct(self):
        for mode in ('empty','disabled'):
            client = SessionClient(RejectBackend(mode=mode))
            frame = client.reset()
            self.assertEqual(frame['decisions']['families'][contract.REJECT],
                             dict(status='queried_complete', candidate_ids=[]))
            self.assertIsNotNone(client.information('great_people')['data'])
        waiting = SessionClient(RejectBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['great_people'])
        self.assertEqual(frame['decisions']['families'][contract.REJECT]['status'], 'unqualified')
        with self.assertRaises(InformationUnavailable): waiting.information('great_people')
        client = SessionClient(RejectBackend())
        client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn(contract.REJECT, closed['decisions']['families'])
        with self.assertRaises(ValueError): network.add_xp1_great_people_reject(closed['decisions'], actions_closed=True)

    def test_command_receipts_validate_signed_domain_and_exact_shape(self):
        action = dict(kind=contract.REJECT, individual_index=51, cost=-(2**31))
        for status in ('completed','refused'):
            receipt = dict(status=status, reason=None, requested_action=action)
            self.assertEqual(_validate_command(receipt), receipt)
        for bad in (dict(action, cost=True), dict(action, cost=-(2**31)-1),
                    dict(action, individual_index=-1), dict(action, currency='YIELD_FAITH')):
            with self.assertRaises(ProtocolError):
                _validate_command(dict(status='completed', reason=None, requested_action=bad))


if __name__ == '__main__':
    unittest.main()

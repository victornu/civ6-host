"""Exact native GP acquisition offers, two public families and client dispatch."""
from copy import deepcopy
from itertools import product
import json
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, great_people_actions as contract
from civ6_host.runtime import xp1_great_people as reader
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.session_client import _validate_command
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_prophet_activation_public import preceding as religious_preceding, state as prophet_state
from test_xp1_religion_beliefs_public import validate, unavailable, terminal_v11


def state(obs, mode='offers'):
    pid, turn = obs['player_id'], obs['turn']
    flags = '0|0|0|0' if mode == 'disabled' else '1|1|1|1'
    wire = (f'great-people-v1|{pid}|{turn}|{flags}|0|0\n'
            'P|4|GREAT_PERSON_CLASS_PROPHET|1|0|17.00390625|2\n'
            'P|5|GREAT_PERSON_CLASS_SCIENTIST|-|2|0|0')
    if mode != 'empty':
        wire += ('\nI|117|GREAT_PERSON_INDIVIDUAL_ZOROASTER|4|1|-|60|0|0|-|1|550|1|70'
                 '\nI|50|GREAT_PERSON_INDIVIDUAL_TEST_50|5|1|0|40|1|0|-|1|550|1|70'
                 '\nI|51|GREAT_PERSON_INDIVIDUAL_TEST_51|5|1|21|40|0|1|2|1|550|1|70'
                 '\nT|5|2|-')
    return reader.parse(wire.encode(), pid, turn)


def preceding(value, obs, options, *, mode='offers', waiting=False):
    pantheon, beliefs, founding, activation = options
    religious_preceding(value, obs, (pantheon, beliefs, founding, True), waiting=waiting)
    value['great_people'] = None if waiting else state(obs, mode)
    if activation:
        network.add_xp1_prophet_activation(value, None if waiting else prophet_state(obs))
    return seal(value)


class CommandsBackend(ReligionBackend):
    def __init__(self, *, options=(True, True, True, True), mode='offers', waiting=False):
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
        network.add_xp1_great_people_actions(dec)
        seal(dec)
        return value


class XP1GreatPeopleActionsPublicTests(unittest.TestCase):
    def test_native_reader_offers_preserve_timeline_currency_order_and_exact_costs(self):
        obs, _, _, _ = religion_fixture()
        value = state(obs)
        expected = [dict(kind='patronize_great_person', individual_index=117, cost=550, currency='YIELD_GOLD'),
                    dict(kind='patronize_great_person', individual_index=117, cost=70, currency='YIELD_FAITH'),
                    dict(kind='recruit_great_person', individual_index=50, cost=40)]
        self.assertEqual(contract.actions(value), expected)
        self.assertEqual(contract.actions(json.loads(json.dumps(value, sort_keys=True))), expected)
        self.assertEqual(contract.actions(None), [])
        self.assertEqual(contract.actions(state(obs, 'empty')), [])
        self.assertEqual(contract.actions(state(obs, 'disabled')), [])
        # Exact supplied availability controls choices; no strategic judgment
        # about class, balance, ownership of another Prophet or desired religion.
        value['own_points'][0]['instances_earned'] = 1
        value['timeline'][0]['patronage']['YIELD_FAITH']['cost'] = 0
        expected[1]['cost'] = 0
        self.assertEqual(contract.actions(value), expected)
        self.assertFalse(any(a['individual_index'] == 51 for a in expected))

    def test_strict_explicit_action_domains_and_no_silent_bad_quote_filter(self):
        obs, _, _, _ = religion_fixture()
        base = contract.actions(state(obs))[0]
        for key in ('individual_index', 'cost'):
            for bad in (True, None, -1, 0x80000000, 1.5):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    contract.validate_action(dict(base, **{key: bad}))
        for action in (dict(base, currency='YIELD_CULTURE'), dict(base, player_id=1),
                       dict(base, kind='reject_great_person'), dict(base, kind='activate_great_person'),
                       dict(base, hash=123)):
            with self.assertRaises(ValueError): contract.validate_action(action)
        recruit = dict(kind='recruit_great_person', individual_index=0x7fffffff, cost=0x7fffffff)
        contract.validate_action(recruit)
        with self.assertRaises(ValueError): contract.validate_action(dict(recruit, currency='YIELD_GOLD'))
        value = state(obs)
        value['timeline'][0]['patronage']['YIELD_GOLD']['cost'] = None
        with self.assertRaises(ValueError): contract.actions(value)

    def test_sixteen_predecessors_keep_all_data_and_existing_action_families(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=4):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            network.add_xp1_great_people_actions(value)
            validate(obs, value)
            self.assertEqual(set(value), set(prior))
            self.assertEqual(value['candidates'][:-3], prior['candidates'])
            self.assertEqual({k:v for k,v in value['families'].items() if k not in contract.LEGACY_KINDS}, prior['families'])
            for key in set(prior)-{'schema', 'decision_id', 'families', 'candidates'}:
                self.assertEqual(value[key], prior[key], (options, key))
            self.assertEqual([r['action'] for r in value['candidates'][-3:]], contract.actions(value['great_people']))
            self.assertIn(value['schema'], network.XP1_GREAT_PEOPLE_SCHEMAS)
            self.assertIn(value['schema'], network.XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS)
            self.assertEqual(value['schema'] in network.XP1_PROPHET_ACTIVATION_SCHEMAS, options[3])
            for kind in contract.LEGACY_KINDS: self.assertEqual(value['families'][kind]['status'], 'queried_complete')
            self.assertFalse(value['complete_action_space'])
            self.assertFalse(value['family_inventory_complete'])
            self.assertNotIn('reject_great_person', value['families'])
            self.assertNotIn('activate_great_person', value['families'])
            with self.assertRaises(ValueError): network.add_xp1_great_people_actions(value)
        with self.assertRaises(ValueError): network.add_xp1_great_people_actions(deepcopy(city))

    def test_checkpoint_projection_removes_only_commands_then_recurses_to_old_data(self):
        obs, _, _, city = religion_fixture()
        for options in product((False, True), repeat=4):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            network.add_xp1_great_people_actions(value)
            validate(obs, value)
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(projected['great_people'], value['great_people'])
            self.assertEqual(receipt.get('added_public_fields', []), [])
            self.assertEqual(receipt['added_action_families'], list(contract.LEGACY_KINDS))
            projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, city)
            self.assertIn('great_people', receipt['added_public_fields'])
            self.assertEqual(receipt['added_action_families'][-2:], list(contract.LEGACY_KINDS))
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            changed = deepcopy(value)
            changed['great_people']['own_points'][0]['points_total'] = 18
            seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs, core_sha256=XP1_CORE_SHA256)[0], prior)

    def test_actual_client_dispatches_each_native_choice_and_keeps_information(self):
        for kind, currency in (('recruit_great_person', None), ('patronize_great_person', 'YIELD_GOLD'),
                               ('patronize_great_person', 'YIELD_FAITH')):
            backend = CommandsBackend()
            client = SessionClient(backend)
            frame = client.reset()
            info = client.information('great_people')
            self.assertEqual(info['data'], state(frame['observation']))
            self.assertEqual(backend.calls, [])
            for group in ('pantheon', 'religion_beliefs', 'religion_founding', 'prophet_activation'):
                client.information(group)
            row = next(r for r in frame['decisions']['candidates']
                       if r['action']['kind'] == kind and r['action'].get('currency') == currency)
            with self.assertRaises(ProtocolError):
                client.act(0, frame['decisions']['decision_id'], row['candidate_id'], parameters={'cost': 0})
            self.assertEqual(backend.calls, [])
            reply = client.act(0, frame['decisions']['decision_id'], row['candidate_id'])
            self.assertEqual(reply['applied_action'], row['action'])
            self.assertEqual(client.command_result['requested_action'], row['action'])
            self.assertEqual(client.command_result['status'], 'completed')
            self.assertEqual(client.information('great_people')['data'], info['data'])

    def test_exact_candidate_set_prices_currency_and_family_status_are_validated(self):
        obs, _, _, city = religion_fixture()
        value = preceding(deepcopy(city), obs, (True, True, True, True))
        network.add_xp1_great_people_actions(value)
        validate(obs, value)
        for mutation in ('omit', 'extra', 'cost', 'currency', 'partial', 'old_schema'):
            bad = deepcopy(value)
            kind = bad['candidates'][-3]['action']['kind']
            if mutation == 'omit':
                removed = bad['candidates'].pop(-3)
                bad['families'][kind]['candidate_ids'].remove(removed['candidate_id'])
            elif mutation == 'extra':
                action = dict(kind='recruit_great_person', individual_index=51, cost=40)
                key = network.digest(action)
                bad['candidates'].append(dict(candidate_id=key, action=action))
                bad['families'][action['kind']]['candidate_ids'].append(key)
            elif mutation in ('cost', 'currency'):
                row = bad['candidates'][-3]
                old = row['candidate_id']
                row['action'][mutation] = 0 if mutation == 'cost' else 'YIELD_FAITH'
                row['candidate_id'] = network.digest(row['action'])
                ids = bad['families'][kind]['candidate_ids']
                ids[ids.index(old)] = row['candidate_id']
            elif mutation == 'partial': bad['families'][kind].update(status='queried_partial', unqualified=['omitted'])
            else: bad['schema'] = network._XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA[bad['schema']]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(obs, bad)

    def test_waiting_empty_disabled_and_reduced_v11_close_preserve_query_meaning(self):
        for mode in ('empty', 'disabled'):
            client = SessionClient(CommandsBackend(mode=mode))
            frame = client.reset()
            self.assertEqual(client.information('great_people')['data'], state(frame['observation'], mode))
            for kind in contract.LEGACY_KINDS:
                self.assertEqual(frame['decisions']['families'][kind], dict(status='queried_complete', candidate_ids=[]))
        waiting = SessionClient(CommandsBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['great_people'])
        for kind in contract.LEGACY_KINDS: self.assertEqual(frame['decisions']['families'][kind]['status'], 'unqualified')
        with self.assertRaises(InformationUnavailable): waiting.information('great_people')
        client = SessionClient(CommandsBackend())
        client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'], network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        for kind in contract.LEGACY_KINDS: self.assertNotIn(kind, closed['decisions']['families'])
        with self.assertRaises(ValueError): network.add_xp1_great_people_actions(closed['decisions'], actions_closed=True)

    def test_command_receipts_validate_exact_native_selection_shape(self):
        obs, _, _, _ = religion_fixture()
        for action in contract.actions(state(obs)):
            for status in ('completed', 'refused'):
                receipt = dict(status=status, reason=None, requested_action=action)
                self.assertEqual(_validate_command(receipt), receipt)
            for bad in (dict(action, cost=True), dict(action, individual_index=-1), dict(action, extra='value')):
                with self.assertRaises(ProtocolError):
                    _validate_command(dict(status='completed', reason=None, requested_action=bad))


if __name__ == '__main__':
    unittest.main()

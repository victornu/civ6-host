"""Parameterized native custom-name choices and portable public composition."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, religion_custom_names as contract
from civ6_host.contracts import religion_beliefs
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.session_client import _validate_command
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_prophet_activation_public import preceding as religious_preceding, state as prophet_state
from test_xp1_religion_founding_public import native_own
from test_xp1_religion_beliefs_public import validate, unavailable, terminal_v11

_UNSET = object()


def native_state(obs, *, rename=True, mode='offered', default='Nom officiel'):
    own = native_own(obs, mode if mode in ('no_site','already_founded') else 'offered')
    icons = [dict(index=20, hash=0xffffffff, default_name=default),
             dict(index=21, hash=0, default_name='Autre symbole')] if mode == 'offered' else []
    return dict(status='catalog' if icons else 'not_due', own=own,
                own_custom_name='' if mode == 'already_founded' else None,
                rename_allowed=rename, placeholder='Saisissez le nom', custom_icons=icons)


def state(obs, **kwargs):
    return contract.project(native_state(obs, **kwargs), obs['player_id'], obs['turn'], observation=obs)


def preceding(value, obs, options=(True, True, 3, True), *, waiting=False):
    pantheon, beliefs, gp_level, activation = options
    religious_preceding(value, obs, (pantheon, beliefs, True, gp_level > 0),
                        mode='consumed', waiting=waiting)
    if activation:
        network.add_xp1_prophet_activation(value, None if waiting else prophet_state(obs, 'consumed'))
    if gp_level >= 2:
        network.add_xp1_great_people_actions(value)
    if gp_level >= 3:
        network.add_xp1_great_people_reject(value)
    return seal(value)


class CustomNamesBackend(ReligionBackend):
    def __init__(self, *, rename=True, waiting=False, mode='offered', default='Nom officiel', own_name=_UNSET):
        super().__init__()
        self.rename, self.waiting, self.mode, self.default = rename, waiting, mode, default
        self.own_name = own_name

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
        custom = None if self.waiting else state(obs, rename=self.rename, mode=self.mode, default=self.default)
        if custom is not None and self.own_name is not _UNSET:
            custom['own_custom_name'] = self.own_name
        if custom is not None and self.mode in ('no_site','already_founded'):
            # These no-choice native contexts also apply to the preceding
            # foundation reader; do not fabricate a foundation opportunity.
            dec['religion_founding'].update(own=deepcopy(custom['own']), foundation=None)
            dec['candidates'] = [row for row in dec['candidates'] if row['action']['kind'] != 'found_religion']
            dec['families']['found_religion']['candidate_ids'] = []
        network.add_xp1_religion_custom_names(dec, custom)
        seal(dec)
        if operation == 'act' and self.status == 'refused':
            value['command_result']['reason'] = 'religion_custom_name_invalid'
        return value


def candidate(frame):
    return next(row for row in frame['decisions']['candidates'] if row['action']['kind'] == contract.KIND)


class XP1ReligionCustomNamesPublicTests(unittest.TestCase):
    def test_native_own_name_absence_null_empty_and_named_projection_and_client(self):
        obs = religion_fixture()[0]
        cases = (('no_site', None), ('already_founded', None),
                 ('already_founded', ''), ('already_founded', '  É\U0001f642\n '*90))
        for mode, name in cases:
            with self.subTest(mode=mode, name=repr(name)):
                raw = native_state(obs, mode=mode)
                raw['own_custom_name'] = name
                projected = contract.project(raw, obs['player_id'], obs['turn'], observation=obs)
                self.assertEqual(projected['own_custom_name'], name)
                client = SessionClient(CustomNamesBackend(mode=mode, own_name=name))
                frame = client.reset()
                self.assertEqual(frame['decisions']['religion_custom_names']['own_custom_name'], name)
                self.assertEqual(client.information('religion_custom_names')['data']['own_custom_name'], name)
        for name in ('', 'A name'):
            raw = native_state(obs, mode='no_site')
            raw['own_custom_name'] = name
            with self.assertRaises(ValueError):
                contract.project(raw, obs['player_id'], obs['turn'], observation=obs)

    def test_shared_native_projection_strips_only_diagnostics_and_detaches(self):
        obs = religion_fixture()[0]
        raw = native_state(obs)
        value = contract.project(raw, obs['player_id'], obs['turn'], observation=obs)
        self.assertIs(contract.project_snapshot, religion_beliefs.project_snapshot)
        self.assertFalse(set(value['own']) & religion_beliefs._NATIVE_META)
        self.assertTrue(value['own']['has_religious_founding_unit'])
        self.assertEqual(value['custom_icons'], raw['custom_icons'])
        self.assertEqual(set(contract.actions(value)[0]), {'kind','index','hash'})
        raw['custom_icons'][0]['default_name'] = 'changed'
        self.assertEqual(value['custom_icons'][0]['default_name'], 'Nom officiel')
        value['placeholder'] = ''
        contract.validate(value, obs['player_id'], obs['turn'], observation=obs)
        founded = state(obs, mode='already_founded')
        self.assertEqual(founded['own_custom_name'], '')
        founded['own_custom_name'] = '  É\U0001f642\n '*90
        contract.validate(founded, obs['player_id'], obs['turn'], observation=obs)
        self.assertGreater(len(founded['own_custom_name'].encode('utf-8')), 512)
        for mutation in ('actor','turn','own_meta','rename_bool','icon_bool','duplicate','order','status','default_null','surrogate'):
            bad = deepcopy(value)
            if mutation == 'actor': bad['player_id'] = True
            elif mutation == 'turn': bad['turn'] += 1
            elif mutation == 'own_meta': bad['own']['source_sha256'] = '0'*64
            elif mutation == 'rename_bool': bad['rename_allowed'] = 1
            elif mutation == 'icon_bool': bad['custom_icons'][0]['index'] = True
            elif mutation == 'duplicate': bad['custom_icons'].append(deepcopy(bad['custom_icons'][0]))
            elif mutation == 'order': bad['custom_icons'].reverse()
            elif mutation == 'status': bad['status'] = 'not_due'
            elif mutation == 'default_null': bad['custom_icons'][0]['default_name'] += '\0'
            else: bad['placeholder'] = '\ud800'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                contract.validate(bad, obs['player_id'], obs['turn'], observation=obs)

    def test_exact_input_scalar_limit_preserves_unicode_controls_and_spacing(self):
        obs = religion_fixture()[0]
        value = state(obs)
        template = contract.actions(value)[0]
        names = ['a', ' a ', 'é'*32, '\U0001f642'*32, 'e\u0301'*16, '\t', '\r\n', '\x01',
                 value['placeholder'], 'ıİß', '\U0001f642\r\n e\u0301 ']
        for name in names:
            result = contract.choose(value, template, {'name':name})
            self.assertEqual(result, dict(template, custom_name=name))
            self.assertEqual(result['custom_name'].encode('utf-8'), name.encode('utf-8'))
        # No Python uppercase, trim, normalization, byte-count or grapheme rule.
        for name in ('', ' '*32, 'x'*33, '\U0001f642'*33, 'e\u0301'*17, 'a\0b', '\ud800', '\udfff'):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                contract.choose(value, template, {'name':name})
        for params in (None, {}, {'name':1}, {'custom_name':'x'}, {'name':'x','extra':0}):
            with self.assertRaises(ValueError): contract.choose(value, template, params)

    def test_nonrename_default_is_exact_without_input_or_universal_byte_limit(self):
        obs = religion_fixture()[0]
        long_default = 'Défaut officiel '*80
        self.assertGreater(len(long_default.encode('utf-8')), 512)
        value = state(obs, rename=False, default=long_default)
        template = contract.actions(value)[0]
        action = contract.choose(value, template)
        self.assertEqual(action, dict(template, custom_name=long_default))
        self.assertEqual(contract.validate_action(action), action)
        for params in ({}, {'name':long_default}, {'name':'short'}):
            with self.assertRaises(ValueError): contract.choose(value, template, params)
        self.assertEqual(contract.validate_template(template), template)
        with self.assertRaises(ValueError): contract.validate_action(template)
        with self.assertRaises(ValueError): contract.validate_template(action)
        for bad in (dict(action, custom_name=''), dict(action, custom_name='\0'),
                    dict(action, custom_name='\ud800'), dict(action, custom_name=1)):
            with self.assertRaises(ValueError): contract.validate_action(bad)

    def test_thirtytwo_foundation_predecessors_preserve_old_families_and_fields(self):
        obs, _, _, city = religion_fixture()
        for options in product((False,True), (False,True), range(4), (False,True)):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            network.add_xp1_religion_custom_names(value, state(obs))
            validate(obs, value)
            self.assertEqual(value['candidates'][:-2], prior['candidates'])
            self.assertEqual({k:v for k,v in value['families'].items() if k != contract.KIND}, prior['families'])
            self.assertEqual(value['families']['found_religion'], prior['families']['found_religion'])
            for key in set(prior)-{'schema','decision_id','families','candidates'}:
                self.assertEqual(value[key], prior[key], (options,key))
            self.assertEqual(value['schema'] in network.XP1_GREAT_PEOPLE_SCHEMAS, options[2]>0)
            self.assertEqual(value['schema'] in network.XP1_GREAT_PEOPLE_REJECT_SCHEMAS, options[2]>=3)
            self.assertEqual(value['schema'] in network.XP1_PROPHET_ACTIVATION_SCHEMAS, options[3])
            self.assertFalse(value['complete_action_space'])
            self.assertFalse(value['family_inventory_complete'])
            with self.assertRaises(ValueError): network.add_xp1_religion_custom_names(value, state(obs))
        with self.assertRaises(ValueError): network.add_xp1_religion_custom_names(deepcopy(city), state(obs))

    def test_additive_checkpoint_projects_only_new_names_then_older_layers(self):
        obs, _, _, city = religion_fixture()
        for options in ((False,False,0,False), (True,True,3,True)):
            prior = preceding(deepcopy(city), obs, options)
            value = deepcopy(prior)
            network.add_xp1_religion_custom_names(value, state(obs))
            validate(obs, value)
            projected, receipt = network.checkpoint_catalogue(value, prior, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, prior)
            self.assertEqual(receipt['added_public_fields'], ['religion_custom_names'])
            self.assertEqual(receipt['added_action_families'], [contract.KIND])
            projected, receipt = network.checkpoint_catalogue(value, city, obs, core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected, city)
            self.assertEqual(receipt['added_public_fields'][-1], 'religion_custom_names')
            self.assertEqual(receipt['added_action_families'][-1], contract.KIND)
            with self.assertRaisesRegex(ValueError, 'Rise and Fall'):
                network.checkpoint_catalogue(value, prior, obs, core_sha256=XP2_CORE_SHA256)
            changed = deepcopy(value)
            changed['choice_state']['research']['research'] = 123
            seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed, prior, obs, core_sha256=XP1_CORE_SHA256)[0], prior)

    def test_actual_client_information_parameter_expansion_and_refusal_receipt(self):
        for rename, status in product((False,True), ('completed','refused')):
            backend = CustomNamesBackend(rename=rename, default='Nom officiel '*40)
            backend.status = status
            client = SessionClient(backend)
            frame = client.reset()
            info = client.information('religion_custom_names')
            self.assertEqual(info['source_contracts']['religion_custom_names'], contract.SCHEMA)
            self.assertEqual(backend.calls, [])
            self.assertNotIn('source_proof_sha256', info['data']['own'])
            for group in ('religion_founding','religion_beliefs','pantheon','great_people','prophet_activation'):
                client.information(group)
            row = candidate(frame)
            params = {'name':'  É\U0001f642\r\n e\u0301 '} if rename else None
            badparams = None if rename else {'name':'substituted'}
            with self.assertRaises(ProtocolError):
                client.act(0, frame['decisions']['decision_id'], row['candidate_id'], badparams)
            self.assertEqual(backend.calls, [])
            expected = contract.choose(info['data'], row['action'], params)
            reply = client.act(0, frame['decisions']['decision_id'], row['candidate_id'], params)
            self.assertEqual(client.command_result['requested_action'], expected)
            self.assertEqual(client.command_result['status'], status)
            self.assertEqual(reply['applied_action'], expected if status == 'completed' else None)
            self.assertEqual(client.last_command_receipt(0)['command_result'], client.command_result)
            info['data']['custom_icons'].clear()
            self.assertEqual(len(client.information('religion_custom_names')['data']['custom_icons']), 2)

    def test_real_client_rejects_substituted_name_or_icon_in_receipt(self):
        for key,replacement in (('custom_name','Other'), ('index',21), ('hash',0)):
            backend = CustomNamesBackend()
            client = SessionClient(backend)
            frame = client.reset()
            row = candidate(frame)
            def corrupt(reply, key=key, replacement=replacement):
                reply['command_result']['requested_action'][key] = replacement
                reply['applied_action'][key] = replacement
            backend.fault = corrupt
            with self.assertRaisesRegex(ProtocolError, 'substituted'):
                client.act(0, frame['decisions']['decision_id'], row['candidate_id'], {'name':'Chosen'})
        for bad in (dict(kind=contract.KIND,index=20,hash=1),
                    dict(kind=contract.KIND,index=20,hash=1,custom_name='\ud800')):
            with self.assertRaises(ProtocolError):
                _validate_command(dict(status='completed',reason=None,requested_action=bad))

    def test_exact_templates_query_context_and_parameter_presence(self):
        obs, _, _, city = religion_fixture()
        prior = preceding(deepcopy(city), obs)
        value = deepcopy(prior)
        network.add_xp1_religion_custom_names(value, state(obs))
        validate(obs, value)
        row = value['candidates'][-2]
        selection = dict(decision_id=value['decision_id'], candidate_id=row['candidate_id'], parameters={'name':'Name'})
        self.assertEqual(network.select_capability(value,selection), dict(row['action'],custom_name='Name'))
        for mutation in ('omit','rename','own','old_schema','expanded_template','missing_parameter'):
            bad = deepcopy(value)
            if mutation == 'omit':
                removed = bad['candidates'].pop()
                bad['families'][contract.KIND]['candidate_ids'].remove(removed['candidate_id'])
            elif mutation == 'rename': bad['religion_custom_names']['rename_allowed'] = 1
            elif mutation == 'own': bad['religion_custom_names']['own']['num_beliefs_earned'] += 1
            elif mutation == 'old_schema': bad['schema'] = prior['schema']
            elif mutation == 'expanded_template':
                changed = bad['candidates'][-1]
                old = changed['candidate_id']
                changed['action']['custom_name'] = 'hidden default'
                changed['candidate_id'] = network.digest(changed['action'])
                ids = bad['families'][contract.KIND]['candidate_ids']; ids[ids.index(old)] = changed['candidate_id']
            else:
                with self.assertRaises(ValueError): network.select_capability(bad, {k:v for k,v in selection.items() if k!='parameters'})
                continue
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): validate(obs,bad)
        no_rename = deepcopy(prior)
        network.add_xp1_religion_custom_names(no_rename, state(obs,rename=False))
        seal(no_rename)
        row = no_rename['candidates'][-1]
        with self.assertRaises(ValueError):
            network.select_capability(no_rename,dict(decision_id=no_rename['decision_id'],candidate_id=row['candidate_id'],parameters=None))

    def test_waiting_not_due_absent_and_reduced_terminal_v11(self):
        for mode in ('empty','no_site','already_founded'):
            client = SessionClient(CustomNamesBackend(mode=mode))
            frame = client.reset()
            info = client.information('religion_custom_names')
            self.assertEqual(info['data']['status'],'not_due')
            self.assertEqual(info['data']['custom_icons'],[])
            self.assertEqual(info['data']['own_custom_name'], '' if mode == 'already_founded' else None)
            self.assertEqual(frame['decisions']['families'][contract.KIND],dict(status='queried_complete',candidate_ids=[]))
        waiting = SessionClient(CustomNamesBackend(waiting=True))
        frame = waiting.reset()
        self.assertIsNone(frame['decisions']['religion_custom_names'])
        self.assertEqual(frame['decisions']['families'][contract.KIND]['status'],'unqualified')
        with self.assertRaises(InformationUnavailable): waiting.information('religion_custom_names')
        legacy = SessionClient(ReligionBackend()); legacy.reset()
        with self.assertRaises(InformationUnavailable): legacy.information('religion_custom_names')
        client = SessionClient(CustomNamesBackend()); client.reset()
        closed = client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'],network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('religion_custom_names',closed['decisions'])
        with self.assertRaises(ValueError): network.add_xp1_religion_custom_names(closed['decisions'],None,actions_closed=True)


if __name__ == '__main__':
    unittest.main()

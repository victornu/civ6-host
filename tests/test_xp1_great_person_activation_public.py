"""Exact native Great Person command offers over existing public boundaries."""
from copy import deepcopy
from itertools import product
import unittest

from civ6_host import InformationUnavailable, ProtocolError, SessionClient
from civ6_host.contracts import network_turn as network, great_person_activation as contract
from civ6_host.contracts import religion_custom_names
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.session_client import _validate_command
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture, ReligionBackend
from test_xp1_prophet_activation_public import preceding as religious_preceding, state as prophet_state
from test_xp1_religion_custom_names_public import native_state as custom_native_state
from test_xp1_religion_beliefs_public import validate, unavailable, terminal_v11


def native_state(obs, mode='offered'):
    units = []
    if mode != 'empty':
        unit = sorted(obs['units'], key=lambda row:row['id'])[0]
        units.append(dict(unit_id=unit['id'], x=unit['x'], y=unit['y'],
                          individual_index=149, class_index=6, charges=-1,
                          visible=mode != 'hidden', available=mode != 'blocked'))
    return dict(player_id=obs['player_id'], current_game_turn=obs['turn'],
                operation=contract.OPERATION, units=units)


def state(obs, mode='offered'):
    return contract.project(native_state(obs,mode), obs['player_id'], obs['turn'], observation=obs)


def preceding(value, obs, options=(True,True,True,3,True,True), *, waiting=False):
    pantheon, beliefs, founding, gp_level, prophet, custom = options
    religious_preceding(value, obs, (pantheon,beliefs,founding,gp_level>0), mode='consumed', waiting=waiting)
    if prophet:
        network.add_xp1_prophet_activation(value,None if waiting else prophet_state(obs,'consumed'))
    if gp_level >= 2: network.add_xp1_great_people_actions(value)
    if gp_level >= 3: network.add_xp1_great_people_reject(value)
    if custom:
        native = None if waiting else religion_custom_names.project(custom_native_state(obs),obs['player_id'],obs['turn'],observation=obs)
        network.add_xp1_religion_custom_names(value,native)
    return seal(value)


def combinations():
    for pantheon,beliefs,founding,gp_level,prophet in product((False,True),(False,True),(False,True),range(4),(False,True)):
        for custom in ((False,True) if founding else (False,)):
            yield pantheon,beliefs,founding,gp_level,prophet,custom


class ActivationBackend(ReligionBackend):
    def __init__(self, *, mode='offered', waiting=False):
        super().__init__()
        self.mode,self.waiting = mode,waiting

    def _reply(self,operation,sequence,player,requested=None):
        if operation=='close':
            value=super()._reply('observe',sequence,player,requested)
            closed=super()._reply('close',sequence,player,requested)
            value.update(operation='close',outcome=closed['outcome'])
            value['decisions']=terminal_v11(value['decisions'])
            return value
        value=super()._reply(operation,sequence,player,requested)
        dec,obs=value['decisions'],value['observation']
        if self.waiting:
            unavailable(dec)
            value['session']['active_human_player_ids']=[]
        preceding(dec,obs,waiting=self.waiting)
        network.add_xp1_great_person_activation(dec,None if self.waiting else state(obs,self.mode))
        seal(dec)
        if operation=='act' and self.status=='refused':
            value['command_result']['reason']='native_great_person_activation_can_start_false'
        return value


class XP1GreatPersonActivationPublicTests(unittest.TestCase):
    def test_native_projection_copies_exact_signed_scalars_and_detaches(self):
        obs=religion_fixture()[0]
        for charges in (-(2**31),-1,0,1,2**31-1):
            raw=native_state(obs)
            raw['units'][0]['charges']=charges
            raw['units'][0]['individual_index']=2**31-1
            raw['units'][0]['class_index']=2**31-1
            value=contract.project(raw,obs['player_id'],obs['turn'],observation=obs)
            self.assertEqual(value['units'],raw['units'])
            self.assertEqual(value['units'][0]['charges'],charges)
            self.assertEqual(set(contract.actions(value)[0]),contract.FIELDS)
            raw['units'][0]['charges']=42
            self.assertEqual(value['units'][0]['charges'],charges)
        action=dict(kind=contract.KIND,unit_id=0xffffffff,x=-(2**31),y=2**31-1)
        self.assertEqual(contract.validate_action(action),action)
        for key,bad in (('unit_id',True),('unit_id',-1),('unit_id',2**32),
                        ('x',2**31),('y',-(2**31)-1),('x',1.5)):
            with self.assertRaises(ValueError): contract.validate_action(dict(action,**{key:bad}))
        for extra in ({'parameters':{}},{'target_id':1},{'individual_index':149}):
            with self.assertRaises(ValueError): contract.validate_action(dict(action,**extra))

    def test_both_official_flags_determine_offers_without_class_charge_or_moves_filter(self):
        obs=deepcopy(religion_fixture()[0]);obs['units'][0]['moves']=0
        for visible,available in product((False,True),repeat=2):
            raw=native_state(obs)
            raw['units'][0].update(visible=visible,available=available,class_index=4,charges=0)
            value=contract.project(raw,obs['player_id'],obs['turn'],observation=obs)
            self.assertEqual(len(contract.actions(value)),int(visible and available))
            self.assertEqual(value['units'][0]['class_index'],4)
        # Class4 is deliberately a transport fixture, not a claim of Prophet
        # command eligibility. The real native FoundReligion predicate decides.
        self.assertEqual(contract.actions(None),[])
        self.assertEqual(contract.actions(state(obs,'empty')),[])

    def test_own_unit_position_identity_boolean_and_duplicate_guards(self):
        obs,_,_,_=religion_fixture()
        value=state(obs)
        for mutation in ('actor','turn','operation','foreign','position','owner','duplicate','extra','charge_bool','charge_over','index_negative','flag_int'):
            bad=deepcopy(value);observation=deepcopy(obs)
            row=bad['units'][0]
            if mutation=='actor': bad['player_id']=True
            elif mutation=='turn': bad['turn']+=1
            elif mutation=='operation': bad['operation']=0xc72fe8fb
            elif mutation=='foreign': row['unit_id']+=1000
            elif mutation=='position': row['x']+=1
            elif mutation=='owner': observation['units'][0]['owner']+=1
            elif mutation=='duplicate': bad['units'].append(deepcopy(row))
            elif mutation=='extra': row['moves']=0
            elif mutation=='charge_bool': row['charges']=True
            elif mutation=='charge_over': row['charges']=2**31
            elif mutation=='index_negative': row['individual_index']=-1
            else: row['visible']=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                contract.validate(bad,obs['player_id'],obs['turn'],observation=observation)
        with self.assertRaises(ValueError): contract.project(native_state(obs),obs['player_id']+1,obs['turn'])

    def test_all_ninetysix_existing_option_combinations_keep_every_old_family_and_query(self):
        obs,_,_,city=religion_fixture()
        count=0
        for options in combinations():
            prior=preceding(deepcopy(city),obs,options)
            value=deepcopy(prior)
            network.add_xp1_great_person_activation(value,state(obs))
            validate(obs,value)
            self.assertEqual(value['candidates'][:-1],prior['candidates'])
            self.assertEqual({k:v for k,v in value['families'].items() if k!=contract.KIND},prior['families'])
            for key in set(prior)-{'schema','decision_id','families','candidates'}:
                self.assertEqual(value[key],prior[key],(options,key))
            self.assertEqual(value['schema'] in network.XP1_RELIGION_CUSTOM_NAMES_SCHEMAS,options[5])
            self.assertEqual(value['schema'] in network.XP1_GREAT_PEOPLE_REJECT_SCHEMAS,options[3]>=3)
            self.assertEqual(value['schema'] in network.XP1_PROPHET_ACTIVATION_SCHEMAS,options[4])
            self.assertFalse(value['complete_action_space'])
            self.assertFalse(value['family_inventory_complete'])
            with self.assertRaises(ValueError): network.add_xp1_great_person_activation(value,state(obs))
            count+=1
        self.assertEqual(count,96)

    def test_checkpoint_strips_only_activation_before_recursing_to_historical_fields(self):
        obs,_,_,city=religion_fixture()
        for options in ((False,False,False,0,False,False),(True,True,True,3,True,True)):
            prior=preceding(deepcopy(city),obs,options)
            value=deepcopy(prior);network.add_xp1_great_person_activation(value,state(obs));validate(obs,value)
            projected,receipt=network.checkpoint_catalogue(value,prior,obs,core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected,prior)
            self.assertEqual(receipt['added_public_fields'],['great_person_activation'])
            self.assertEqual(receipt['added_action_families'],[contract.KIND])
            projected,receipt=network.checkpoint_catalogue(value,city,obs,core_sha256=XP1_CORE_SHA256)
            self.assertEqual(projected,city)
            self.assertEqual(receipt['added_public_fields'][-1],'great_person_activation')
            self.assertEqual(receipt['added_action_families'][-1],contract.KIND)
            with self.assertRaisesRegex(ValueError,'Rise and Fall'):
                network.checkpoint_catalogue(value,prior,obs,core_sha256=XP2_CORE_SHA256)
            changed=deepcopy(value);changed['choice_state']['research']['research']=123;seal(changed)
            self.assertNotEqual(network.checkpoint_catalogue(changed,prior,obs,core_sha256=XP1_CORE_SHA256)[0],prior)

    def test_actual_client_dispatch_has_no_parameters_and_accepts_completed_or_native_refusal(self):
        for status in ('completed','refused'):
            backend=ActivationBackend();backend.status=status
            client=SessionClient(backend);frame=client.reset()
            info=client.information('great_person_activation')
            self.assertEqual(info['data'],state(frame['observation']))
            self.assertEqual(info['source_contracts']['great_person_activation'],contract.SCHEMA)
            for group in ('religion_custom_names','religion_founding','great_people','prophet_activation','pantheon','religion_beliefs'):
                client.information(group)
            row=next(r for r in frame['decisions']['candidates'] if r['action']['kind']==contract.KIND)
            for parameters in ({},{'x':row['action']['x']},{'target_id':1}):
                with self.assertRaises(ProtocolError): client.act(0,frame['decisions']['decision_id'],row['candidate_id'],parameters)
            self.assertEqual(backend.calls,[])
            reply=client.act(0,frame['decisions']['decision_id'],row['candidate_id'])
            self.assertEqual(client.command_result['requested_action'],row['action'])
            self.assertEqual(client.command_result['status'],status)
            self.assertEqual(reply['applied_action'],row['action'] if status=='completed' else None)
            self.assertEqual(client.last_command_receipt(0)['command_result'],client.command_result)
            info['data']['units'][0]['charges']=99
            self.assertEqual(client.information('great_person_activation')['data']['units'][0]['charges'],-1)

    def test_exact_native_offer_set_and_version_are_not_silently_filtered(self):
        obs,_,_,city=religion_fixture();value=deepcopy(city)
        network.add_xp1_great_person_activation(value,state(obs));validate(obs,value)
        for mutation in ('omitted','position','hidden','old_schema','partial'):
            bad=deepcopy(value);row=bad['candidates'][-1]
            if mutation=='omitted':bad['candidates'].pop();bad['families'][contract.KIND]['candidate_ids']=[]
            elif mutation=='position':
                row['action']['x']+=1;row['candidate_id']=network.digest(row['action'])
                bad['families'][contract.KIND]['candidate_ids']=[row['candidate_id']]
            elif mutation=='hidden':bad['great_person_activation']['units'][0]['visible']=False
            elif mutation=='old_schema':bad['schema']=city['schema']
            else:bad['families'][contract.KIND].update(status='queried_partial',unqualified=['missing'])
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate(obs,bad)

    def test_waiting_empty_hidden_blocked_absent_and_reduced_v11_terminal(self):
        for mode in ('empty','hidden','blocked'):
            client=SessionClient(ActivationBackend(mode=mode));frame=client.reset()
            info=client.information('great_person_activation')
            self.assertEqual(info['data'],state(frame['observation'],mode))
            self.assertEqual(frame['decisions']['families'][contract.KIND],dict(status='queried_complete',candidate_ids=[]))
        waiting=SessionClient(ActivationBackend(waiting=True));frame=waiting.reset()
        self.assertIsNone(frame['decisions']['great_person_activation'])
        self.assertEqual(frame['decisions']['families'][contract.KIND]['status'],'unqualified')
        with self.assertRaises(InformationUnavailable):waiting.information('great_person_activation')
        legacy=SessionClient(ReligionBackend());legacy.reset()
        with self.assertRaises(InformationUnavailable):legacy.information('great_person_activation')
        client=SessionClient(ActivationBackend());client.reset();closed=client.close()
        self.assertIsNotNone(closed['observation'])
        self.assertEqual(closed['decisions']['schema'],network.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertNotIn('great_person_activation',closed['decisions'])
        with self.assertRaises(ValueError):network.add_xp1_great_person_activation(closed['decisions'],None,actions_closed=True)

    def test_command_receipts_validate_exact_shape_and_client_detects_substitution(self):
        obs=religion_fixture()[0];action=contract.actions(state(obs))[0]
        for status in ('completed','refused'):
            receipt=dict(status=status,reason=None,requested_action=action)
            self.assertEqual(_validate_command(receipt),receipt)
        for bad in (dict(action,unit_id=True),dict(action,x=2**31),dict(action,operation=contract.OPERATION),dict(action,target_id=1)):
            with self.assertRaises(ProtocolError):_validate_command(dict(status='completed',reason=None,requested_action=bad))
        backend=ActivationBackend();client=SessionClient(backend);frame=client.reset()
        row=next(r for r in frame['decisions']['candidates'] if r['action']['kind']==contract.KIND)
        def corrupt(reply):
            reply['command_result']['requested_action']['unit_id']+=1
            reply['applied_action']['unit_id']=reply['command_result']['requested_action']['unit_id']
        backend.fault=corrupt
        with self.assertRaisesRegex(ProtocolError,'Requested action differs'):
            client.act(0,frame['decisions']['decision_id'],row['candidate_id'])


if __name__=='__main__':
    unittest.main()

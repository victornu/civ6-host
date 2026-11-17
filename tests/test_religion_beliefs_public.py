"""Pure public projection checked against the retained independent native parsers."""
from copy import deepcopy
import json
import unittest

from civ6_host.contracts import religion_beliefs as contract
from civ6_host.runtime.native import native_religion_observation as reader
from civ6_host.runtime.native import native_religion_beliefs as choices


def fixture(*, founded=True, spent=False):
    observation=dict(player_id=0,turn=40,cities=[dict(id=7,owner=0)])
    earned=1 if spent else 2
    payload=(f'religion-observation-v1|0|40|3|1|{earned}|0|2|7|1|3|0|1|24'
             if founded else 'religion-observation-v1|0|40|-1|0|0|-1|2|-1|0|-1|-1|0')
    native=reader.parse_observation(payload.encode(),0,40)
    sub=None
    if founded:
        if spent:
            payload=b'not_due,0,40,3,1,1,no_unspent_belief'
        else:
            prefix=f'catalog,0,40,3,2,1,1,{choices.ADD_BELIEF},{choices.PARAM_BELIEF_TYPE},{choices.PARAM_INSERT_MODE},{choices.VALUE_EXCLUSIVE},1,2'
            payload=(prefix+',o24,c34:888:BELIEF_CLASS_FOUNDER,c36:999:BELIEF_CLASS_ENHANCER').encode()
        sub=json.loads(json.dumps(choices.parse_catalog(payload,0,40)))
    value=dict(schema=contract.SCHEMA,player_id=0,turn=40,
        own=contract.project_snapshot(native,0,40,observation=observation),beliefs=sub)
    return observation,native,value


class ReligionBeliefsPublicTests(unittest.TestCase):
    def test_snapshot_projection_preserves_native_flags_and_removes_metadata(self):
        observation,native,value=fixture()
        self.assertIs(contract.validate(value,0,40,observation=observation),value)
        self.assertTrue(value['own']['has_religious_founding_unit'])
        self.assertFalse(set(value['own'])&contract._NATIVE_META)
        native['own_religion']['belief_indices'].append(99)
        self.assertEqual(value['own']['own_religion']['belief_indices'],[24])

    def test_absent_and_spent_native_states_do_not_invent_choices(self):
        for founded,spent in ((False,False),(True,True)):
            observation,_,value=fixture(founded=founded,spent=spent)
            contract.validate(value,0,40,observation=observation)
            self.assertEqual(contract.actions(value),[])
            if founded:
                self.assertEqual(value['beliefs']['equipped_beliefs'],[])
                self.assertEqual(value['own']['own_religion']['belief_indices'],[24])
        self.assertEqual(contract.actions(None),[])

    def test_all_native_offers_keep_index_hash_and_class(self):
        _,_,value=fixture()
        expected=[dict(kind='add_belief',index=34,hash=888,**{'class':'BELIEF_CLASS_FOUNDER'}),
                  dict(kind='add_belief',index=36,hash=999,**{'class':'BELIEF_CLASS_ENHANCER'})]
        self.assertEqual(contract.actions(value),expected)
        for action in expected:
            self.assertIs(contract.validate_action(action),action)
        for key,bad in (('index',True),('hash',-1),('class','secret score'),('kind','found_religion')):
            action=deepcopy(expected[0]);action[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):contract.validate_action(action)

    def test_foreign_or_inconsistent_state_and_hidden_fields_refuse(self):
        observation,_,original=fixture()
        for mutation in ('player','turn','holy_owner','holy_missing','founder','earned','candidate_bool',
                         'candidate_duplicate','candidate_order','candidate_owned','extra','bad_counter'):
            value=deepcopy(original)
            if mutation=='player':value['player_id']=1
            elif mutation=='turn':value['turn']=41
            elif mutation=='holy_owner':value['own']['holy_city']['player']=1
            elif mutation=='holy_missing':value['own']['holy_city']['id']=9
            elif mutation=='founder':value['own']['own_religion']['founder']=1
            elif mutation=='earned':value['beliefs']['num_beliefs_earned']=3
            elif mutation=='candidate_bool':value['beliefs']['candidates'][0]['hash']=True
            elif mutation=='candidate_duplicate':value['beliefs']['candidates'][1]['hash']=888
            elif mutation=='candidate_order':value['beliefs']['candidates'].reverse()
            elif mutation=='candidate_owned':value['beliefs']['candidates'][0]['index']=24
            elif mutation=='extra':value['own']['opponent_religions']=[123]
            else:value['beliefs']['num_beliefs_earned']='2'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                contract.validate(value,0,40,observation=observation)

    def test_projection_rejects_extra_channels_and_stale_native_identity(self):
        observation,native,_=fixture()
        for mutation in ('extra','actor','turn','source'):
            value=deepcopy(native)
            if mutation=='extra':value['hidden_cities']=[99]
            elif mutation=='actor':value['player_id']=1
            elif mutation=='turn':value['current_game_turn']=39
            else:value['source_proof_sha256']='unverified'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                contract.project_snapshot(value,0,40,observation=observation)
        for mutation in ('turn','bool_turn','bool_player','bool_city','bool_owner'):
            bad=deepcopy(observation)
            if mutation=='turn':bad['turn']=41
            elif mutation=='bool_turn':bad['turn']=True
            elif mutation=='bool_player':bad['player_id']=False
            elif mutation=='bool_city':bad['cities'][0]['id']=True
            else:bad['cities'][0]['owner']=False
            with self.subTest(observation=mutation),self.assertRaises(ValueError):
                contract.project_snapshot(native,0,40,observation=bad)


if __name__=='__main__':unittest.main()

"""Portable native-inventory wire fixtures; no native availability claim."""
from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys
import unittest

from civ6_host.contracts import network_turn as contract, placement_inventory as inventory
from civ6_host.session_client import SessionClient
import test_capability_placement as placement_tests
from test_session_capabilities import seal


def native_inventory(obs):
    rows=[]
    if obs['cities']:
        city=obs['cities'][0]['id']
        rows=[dict(city_id=city,category='district',index=1,hash=201,item_type='DISTRICT_HOLY_SITE',
                   plot_id=28,x=4,y=3,complete=False,district_id=41),
              dict(city_id=city,category='building',index=2,hash=202,item_type='BUILDING_ORACLE',
                   plot_id=28,x=4,y=3,complete=True,district_id=None)]
    return dict(schema=inventory.SCHEMA,scope=inventory.SCOPE,player_id=obs['player_id'],turn=obs['turn'],rows=rows)


def extend(value,obs,*,unavailable=False):
    value['schema']=contract.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA
    value['placement_inventory']=None if unavailable else native_inventory(obs)
    return seal(value)


class InventoryBackend(placement_tests.PlacementBackend):
    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation!='close':extend(reply['decisions'],reply['observation'])
        return reply


class PlacementInventoryContract(unittest.TestCase):
    def setUp(self):
        self.fixture=placement_tests.PlacementContract();self.fixture.setUp()
        self.obs=self.fixture.fixture.obs

    def value(self,*,unavailable=False,**kwargs):
        return extend(self.fixture.value(**kwargs),self.obs,unavailable=unavailable)

    def validate(self,value,*,closed=False):
        return self.fixture.validate(value,closed=closed)

    def test_native_existing_constructs_do_not_invent_tracked_history_or_actions(self):
        prior=self.fixture.value();value=extend(deepcopy(prior),self.obs);self.validate(value)
        self.assertEqual(value['placements'],[])
        self.assertEqual(value['placement_observation_scope'],'host_tracked')
        self.assertEqual(value['candidates'],prior['candidates']);self.assertEqual(value['families'],prior['families'])
        self.assertEqual([r['complete'] for r in value['placement_inventory']['rows']],[False,True])
        self.assertTrue(all('placement_turn' not in r for r in value['placement_inventory']['rows']))
        self.assertFalse(value['family_inventory_complete']);self.assertEqual(contract.LATEST_SCHEMA,contract.PRODUCTION_SCHEMA)
        self.assertNotIn(contract.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,contract.MAP_SCHEMAS)

    def test_null_and_empty_are_distinct_and_waiting_or_closed_can_observe(self):
        for kwargs in ({},{'waiting':True},{'closed':True},{'missing':True}):
            for unavailable in (False,True):
                value=self.value(**kwargs,unavailable=unavailable)
                self.validate(value,closed=kwargs.get('closed',False))
                if kwargs:self.assertIsNone(value['placements'])
                self.assertEqual(value['placement_inventory'] is None,unavailable)
        absent=self.value(unavailable=True);empty=self.value();empty['placement_inventory']['rows']=[]
        self.validate(empty);self.assertNotEqual(seal(empty)['decision_id'],absent['decision_id'])
        bad=self.value();bad.pop('placement_inventory')
        with self.assertRaises(ValueError):self.validate(bad)

    def test_inventory_identity_exact_types_visibility_ownership_and_row_uniqueness(self):
        envelope=(dict(schema='unknown'),dict(scope='all_constructs'),dict(player_id=True),
                  dict(player_id=1),dict(turn=2),dict(turn=True),dict(private_state={}))
        row_changes=(dict(city_id=55),dict(city_id=True),dict(index=-1),dict(index=1<<31),
            dict(hash=True),dict(hash=1<<32),dict(complete=1),dict(category='unit'),
            dict(item_type='BUILDING_WRONG'),dict(plot_id=29,x=5),dict(x=1),dict(x=True),
            dict(district_id=None),dict(district_id=True),dict(placement_turn=0))
        for changes in envelope:
            value=self.value();value['placement_inventory'].update(changes)
            with self.subTest(envelope=changes),self.assertRaises(ValueError):self.validate(value)
        for changes in row_changes:
            value=self.value();value['placement_inventory']['rows'][0].update(changes)
            with self.subTest(row=changes),self.assertRaises(ValueError):self.validate(value)
        value=self.value();value['placement_inventory']['rows'][1]['district_id']=41
        with self.assertRaises(ValueError):self.validate(value)
        value=self.value();duplicate=deepcopy(value['placement_inventory']['rows'][0]);duplicate['index']=9
        value['placement_inventory']['rows'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.validate(value)
        value=self.value();value['placement_inventory']['rows']*=inventory.MAX_ROWS
        with self.assertRaisesRegex(ValueError,'Malformed'):self.validate(value)
        value=self.value();self.obs['plots']=[]
        with self.assertRaises(ValueError):self.validate(value)

    def test_v7_remains_exact_and_inventory_digest_cannot_be_changed_unnoticed(self):
        old=self.fixture.value();self.fixture.validate(old)
        old['placement_inventory']=None
        with self.assertRaises(ValueError):self.validate(old)
        value=self.value();value['placement_inventory']['rows'][0]['complete']=True
        f=self.fixture.fixture
        with self.assertRaisesRegex(ValueError,'digest'):
            contract.validate_catalogue(value,f.identity,0,1,player_id=0,observation=self.obs)

    def test_checkpoint_projection_preserves_old_fields_without_mutating_receipts(self):
        v7=self.fixture.value();v6=self.fixture.fixture.value()
        v5=deepcopy(v6);v5.pop('production_queues');v5['schema']=contract.CAPABILITY_UNIT_ORDERS_SCHEMA
        v5['families']={k:v for k,v in v5['families'].items() if not k.startswith('queue_')}
        v5['candidates']=[r for r in v5['candidates'] if not r['action']['kind'].startswith('queue_')];seal(v5)
        for old in (v7,v6,v5):
            current=self.value();before=deepcopy(current);saved_before=deepcopy(old)
            projected,transition=contract.checkpoint_catalogue(current,old,self.obs)
            self.assertEqual(projected,old);self.assertEqual(current,before);self.assertEqual(old,saved_before)
            self.assertEqual(transition['source_schema'],old['schema'])
            self.assertEqual(transition['target_schema'],contract.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA)
            self.assertTrue(transition['historical_fields_unchanged'])
            self.assertIn('placement_inventory',transition['added_public_fields'])
            self.assertNotIn('placement_inventory',transition['added_action_families'])
        invalid=self.value();invalid['placement_inventory']['turn']=2;seal(invalid)
        with self.assertRaises(ValueError):contract.checkpoint_catalogue(invalid,v7,self.obs)
        changed=self.value();changed['choice_state']['research']['research']=17;seal(changed)
        projected,_=contract.checkpoint_catalogue(changed,v7,self.obs)
        self.assertNotEqual(projected['choice_state'],v7['choice_state'])
        # Historical forward/unsupported transitions remain mismatches, not fabricated migrations.
        unchanged,transition=contract.checkpoint_catalogue(v6,v7,self.obs)
        self.assertIs(unchanged,v6);self.assertIsNone(transition)

    def test_client_server_keeps_inventory_through_actions_and_forced_inactive_refusal(self):
        backend=InventoryBackend();backend.city_fixture=True;client=SessionClient(backend);view=client.reset()
        dec=view['decisions'];row=next(r for r in dec['candidates'] if r['action']['kind']=='production_resume')
        view=client.act(0,dec['decision_id'],row['candidate_id'])
        self.assertEqual(view['applied_action'],row['action'])
        self.assertEqual(backend.protocol.catalogues[0]['placement_inventory'],view['decisions']['placement_inventory'])
        self.assertEqual(backend.aborts,[]);client.close()
        waiting=InventoryBackend(waiting=True);waiting.city_fixture=True;client=SessionClient(waiting);view=client.reset()
        for status in ('submitted','refused'):
            waiting.status=status;dec=view['decisions']
            row=next(r for r in dec['candidates'] if r['action']=={'kind':'force_end_turn'})
            self.assertTrue(contract.offered_forced_turn(dec,row['action']))
            self.assertIsNotNone(dec['placement_inventory']);self.assertIsNone(dec['placements'])
            view=client.act(0,dec['decision_id'],row['candidate_id'])
            self.assertIsNone(view['applied_action']);self.assertEqual(client.command_result['status'],status)
        self.assertEqual(waiting.aborts,[]);client.close()

    def test_client_import_needs_neither_native_runtime_resources_nor_learner(self):
        script='''import sys,importlib.abc
class Refuse(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith(('civ6_host.runtime','torch')):raise AssertionError(fullname)
sys.meta_path.insert(0,Refuse())
from civ6_host.session_client import SessionClient
from civ6_host.contracts import network_turn,placement_inventory
assert network_turn.CAPABILITY_PLACEMENT_INVENTORY_SCHEMA.endswith('.v8')
placement_inventory.validate(dict(schema=placement_inventory.SCHEMA,scope=placement_inventory.SCOPE,player_id=0,turn=1,rows=[]),0,1)
'''
        env=os.environ.copy();env.pop('CIV6_HOST_RESOURCE_ROOT',None)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        done=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(done.returncode,0,done.stderr)


if __name__=='__main__':unittest.main()

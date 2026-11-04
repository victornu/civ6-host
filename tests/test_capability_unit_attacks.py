"""Portable v9 fixtures: exact public state/offers, never simulated legality."""
from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys
import unittest

from civ6_host.contracts import network_turn as contract, capability_unit_attacks as attacks
from civ6_host.session_client import SessionClient
import test_capability_placement_inventory as inventory_tests
from test_session_capabilities import seal


def combat_observation(obs):
    obs['visible_enemy_units']=[dict(owner=1,id=27,type=2,x=4,y=4,damage=0,visible=True)]
    base=deepcopy(obs['plots'][0])
    obs['plots'].extend(dict(base,index=plot,x=plot%obs['width'],y=plot//obs['width'],owner=1) for plot in (36,37))


def state(obs):
    units=[dict(unit_id=u['id'],unit_type=u['type'],x=u['x'],y=u['y'],damage=u['damage'],moves=u['moves'],attacks_remaining=1) for u in obs['units']]
    cities=[dict(owner=1,city_id=77,district_id=78,plot_id=37,x=5,y=4,
                 garrison_damage=2,garrison_max=200,outer_damage=1,outer_max=100,defense_strength=22)]
    offers=[]
    for u in units:
        for plot,routes in ((36,('enemy_flag','dedicated_ranged')),(37,('world_plot','dedicated_ranged'))):
            for route in routes:
                for operation in (('RANGE_ATTACK',) if route=='dedicated_ranged' else ('MOVE_TO','RANGE_ATTACK')):
                    offers.append(dict(kind='unit_attack',unit_id=u['unit_id'],operation=operation,input_route=route,
                                       plot_id=plot,x=plot%obs['width'],y=plot//obs['width']))
    return dict(player_id=obs['player_id'],turn=obs['turn'],width=obs['width'],height=obs['height'],units=units,
                relationships=[dict(owner=1,at_war=True)],cities=cities,offers=offers)


def extend(dec,obs,*,unavailable=False):
    dec['schema']=contract.CAPABILITY_UNIT_ATTACKS_SCHEMA
    value=None if unavailable else state(obs);dec['unit_attacks']=value
    rows=[] if unavailable else [dict(candidate_id=contract.digest(a),action=deepcopy(a)) for a in value['offers']]
    dec['candidates'].extend(rows)
    dec['families']['unit_attack']=(dict(status='unqualified',reason='native_attack_query_unavailable') if unavailable else
        dict(status='queried_partial',candidate_ids=[r['candidate_id'] for r in rows],unqualified=list(attacks.UNQUALIFIED_UNIT_ATTACKS)))
    return seal(dec)


class AttackBackend(inventory_tests.InventoryBackend):
    def _reply(self,operation,sequence,player,requested=None):
        result=super()._reply(operation,sequence,player,requested)
        if operation!='close':
            combat_observation(result['observation'])
            extend(result['decisions'],result['observation'],unavailable=self.waiting)
        return result


class UnitAttackContract(unittest.TestCase):
    def setUp(self):
        self.fixture=inventory_tests.PlacementInventoryContract();self.fixture.setUp()
        self.obs=self.fixture.obs;combat_observation(self.obs)

    def value(self,*,unavailable=False,**kw):
        return extend(self.fixture.value(**kw),self.obs,unavailable=unavailable or kw.get('waiting',False) or kw.get('closed',False))

    def validate(self,value,*,closed=False):return self.fixture.validate(value,closed=closed)

    def test_exact_shared_shapes_and_routes_never_select_a_defender(self):
        value=self.value();self.validate(value)
        self.assertEqual(len(value['unit_attacks']['offers']),6)
        self.assertEqual({a['input_route'] for a in attacks.actions(value['unit_attacks'])},{'enemy_flag','dedicated_ranged','world_plot'})
        self.assertTrue(all(set(a)==attacks.FIELDS for a in value['unit_attacks']['offers']))
        self.assertFalse(value['complete_action_space']);self.assertFalse(value['family_inventory_complete'])
        self.assertEqual(value['families']['unit_attack']['status'],'queried_partial')

    def test_owner_visibility_war_and_roster_joins_refuse_privileged_or_stale_state(self):
        changes=(lambda d:d['unit_attacks'].update(player_id=True),lambda d:d['unit_attacks'].update(turn=2),
            lambda d:d['unit_attacks']['units'][0].update(unit_id=99),
            lambda d:d['unit_attacks']['units'][0].update(attacks_remaining=True),
            lambda d:d['unit_attacks']['units'][0].update(damage=float('inf')),
            lambda d:d['unit_attacks']['cities'][0].update(plot_id=38,x=6),
            lambda d:d['unit_attacks']['cities'][0].update(garrison_damage=201),
            lambda d:d['unit_attacks']['cities'][0].update(secret_garrison=9),
            lambda d:d['unit_attacks']['relationships'][0].update(at_war=False),
            lambda d:d['unit_attacks']['relationships'].append(dict(owner=2,at_war=True)),
            lambda d:d['unit_attacks']['offers'][0].update(target_id=27),
            lambda d:d['unit_attacks']['offers'][0].update(unit_id=True),
            lambda d:d['unit_attacks']['offers'][0].update(plot_id=38,x=6),
            lambda d:d['queued_orders']['units'][0].update(unit_id=88))
        for change in changes:
            value=self.value();change(value)
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(value)
        value=self.value();value['unit_attacks']['offers'].append(deepcopy(value['unit_attacks']['offers'][0]))
        with self.assertRaises(ValueError):self.validate(value)
        value=self.value();value['unit_attacks']['offers'].pop()
        with self.assertRaisesRegex(ValueError,'exact recorded native offers'):self.validate(value)

    def test_no_host_strategy_filter_and_unavailable_is_not_empty(self):
        # Numeric state never overrides the recorded native offer list.
        value=self.value();self.obs['units'][0]['moves']=0;value['unit_attacks']['units'][0]['moves']=0
        value['unit_attacks']['units'][0]['attacks_remaining']=0
        self.validate(value)
        for kw in (dict(waiting=True),dict(closed=True),dict(unavailable=True)):
            value=self.value(**kw);self.validate(value,closed=kw.get('closed',False))
            self.assertIsNone(value['unit_attacks']);self.assertEqual(value['families']['unit_attack']['status'],'unqualified')
        value=self.value();value['families']['unit_attack']['unqualified'].pop()
        with self.assertRaises(ValueError):self.validate(value)
        value=self.value();value['families']['unit_attack']['status']='queried_complete'
        with self.assertRaises(ValueError):self.validate(value)

    def test_v8_stays_exact_and_checkpoint_projection_drops_only_validated_additions(self):
        saved=self.fixture.value();self.fixture.validate(saved)
        bad=deepcopy(saved);bad['unit_attacks']=None
        with self.assertRaises(ValueError):self.validate(bad)
        current=self.value();before=deepcopy(current)
        projected,transition=contract.checkpoint_catalogue(current,saved,self.obs)
        self.assertEqual(projected,saved);self.assertEqual(current,before)
        self.assertEqual(transition['added_public_fields'],['unit_attacks'])
        self.assertEqual(transition['added_action_families'],['unit_attack'])
        for target in (contract.CAPABILITY_PLACEMENT_SCHEMA,contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA,contract.CAPABILITY_UNIT_ORDERS_SCHEMA):
            older=deepcopy(saved)
            older.pop('placement_inventory');older['schema']=contract.CAPABILITY_PLACEMENT_SCHEMA;seal(older)
            if target!=older['schema']:
                target_stub=dict(schema=target)
                older,_=contract.checkpoint_catalogue(older,target_stub,self.obs)
            projected,_=contract.checkpoint_catalogue(current,older,self.obs)
            self.assertEqual(projected,older)
        bad=self.value();bad['unit_attacks']['offers'][0]['x']=0;seal(bad)
        with self.assertRaises(ValueError):contract.checkpoint_catalogue(bad,saved,self.obs)

    def test_client_server_attack_routes_and_forced_inactive_refusal(self):
        backend=AttackBackend();backend.city_fixture=True;client=SessionClient(backend);view=client.reset()
        for route in ('enemy_flag','dedicated_ranged','world_plot'):
            dec=view['decisions'];row=next(r for r in dec['candidates'] if r['action'].get('input_route')==route)
            view=client.act(0,dec['decision_id'],row['candidate_id']);self.assertEqual(view['applied_action'],row['action'])
            self.assertEqual(backend.protocol.catalogues[0]['unit_attacks'],view['decisions']['unit_attacks'])
        backend.status='refused';dec=view['decisions'];row=next(r for r in dec['candidates'] if r['action']['kind']=='unit_attack')
        view=client.act(0,dec['decision_id'],row['candidate_id']);self.assertIsNone(view['applied_action'])
        self.assertEqual(client.command_result['status'],'refused');client.close()
        waiting=AttackBackend(waiting=True);waiting.city_fixture=True;waiting.status='submitted'
        client=SessionClient(waiting);view=client.reset();dec=view['decisions']
        row=next(r for r in dec['candidates'] if r['action']=={'kind':'force_end_turn'})
        self.assertTrue(contract.offered_forced_turn(dec,row['action']))
        view=client.act(0,dec['decision_id'],row['candidate_id']);self.assertIsNone(view['decisions']['unit_attacks'])
        self.assertIsNone(view['applied_action']);self.assertEqual(waiting.aborts,[]);client.close()

    def test_portable_imports_do_not_load_native_runtime_or_torch(self):
        script='''import sys,importlib.abc
class Refuse(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith(('civ6_host.runtime','torch')):raise AssertionError(fullname)
sys.meta_path.insert(0,Refuse())
from civ6_host.session_client import SessionClient
from civ6_host.contracts import network_turn,capability_unit_attacks
assert network_turn.CAPABILITY_UNIT_ATTACKS_SCHEMA.endswith('.v9')
capability_unit_attacks.validate_action(dict(kind='unit_attack',unit_id=1,operation='MOVE_TO',input_route='enemy_flag',plot_id=1,x=1,y=0),8,8)
'''
        env=os.environ.copy();env.pop('CIV6_HOST_RESOURCE_ROOT',None)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        done=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(done.returncode,0,done.stderr)


if __name__=='__main__':unittest.main()

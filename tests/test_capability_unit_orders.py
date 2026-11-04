"""Portable v5 wire fixtures; no native legality or gameplay claim."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import sys
import unittest

from civ6_host.contracts import network_turn as contract
from civ6_host.contracts import capability_unit_orders as orders
from civ6_host.session_client import SessionClient
from test_capability_world_contract import value as world_value, WorldBackend
from test_session_capabilities import observation, seal


def native_catalog(obs):
    units=[];offers=[]
    for unit in obs['units']:
        units.append(dict(unit_id=unit['id'],activity_type=-2147483648,
            fortify_turns=2147483647,ready=False))
        for route,names in orders.NAMES.items():
            for name in names:
                if name == orders.SKIP_TURN:
                    continue
                offers.append(dict(action=dict(kind='unit_order',unit_id=unit['id'],
                    route=route,item_type=name,hash=0xffffffff-len(offers)),legal=True))
    return dict(player_id=obs['player_id'],turn=obs['turn'],units=units,offers=offers)


def extend(dec,obs,*,unavailable=False):
    dec['schema']=contract.CAPABILITY_UNIT_ORDERS_SCHEMA
    state=None if unavailable else native_catalog(obs)
    dec['unit_orders']=state
    rows=[] if unavailable else [dict(candidate_id=contract.digest(a),action=deepcopy(a)) for a in orders.actions(state)]
    dec['candidates'].extend(rows)
    dec['families']['unit_order']=(dict(status='unqualified',reason='native_unit_orders_unavailable') if unavailable else
        dict(status='queried_partial',candidate_ids=[r['candidate_id'] for r in rows],
             unqualified=list(orders.UNQUALIFIED_UNIT_ORDERS)))
    return seal(dec)


class OrderBackend(WorldBackend):
    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation!='close':extend(reply['decisions'],reply['observation'],unavailable=self.waiting)
        return reply


class UnitOrderCapabilities(unittest.TestCase):
    def setUp(self):
        self.identity=SimpleNamespace(episode_id='orders-episode',game_generation='orders-generation')
        self.obs=observation();self.obs['units'][0]['moves']=0

    def value(self,*,waiting=False,closed=False,missing=False,selected=None,obs=None):
        obs=self.obs if obs is None else obs
        return extend(world_value(self.identity,obs,waiting=waiting,closed=closed,selected=selected),obs,
            unavailable=waiting or closed or missing)

    def validate(self,dec,*,closed=False,obs=None):
        return contract.validate_capability_catalogue(seal(dec),self.identity,0,1,
            player_id=0,observation=self.obs if obs is None else obs,actions_closed=closed)

    def reconcile(self,dec):
        dec['candidates']=[r for r in dec['candidates'] if r['action']['kind']!='unit_order']
        rows=[dict(candidate_id=contract.digest(a),action=deepcopy(a)) for a in orders.actions(dec['unit_orders'])]
        dec['candidates'].extend(rows)
        dec['families']['unit_order']['candidate_ids']=[r['candidate_id'] for r in rows]
        return seal(dec)

    def test_six_exact_native_routes_legal_only_without_readiness_or_moves_filter(self):
        dec=self.value();self.validate(dec)
        self.assertEqual(len(orders.actions(dec['unit_orders'])),6)
        self.assertFalse(dec['unit_orders']['units'][0]['ready'])
        self.assertEqual(self.obs['units'][0]['moves'],0)
        disabled=dec['unit_orders']['offers'][0]
        disabled['legal']=False;self.reconcile(dec);self.validate(dec)
        self.assertEqual(len(orders.actions(dec['unit_orders'])),5)
        self.assertIn(disabled,dec['unit_orders']['offers'])
        # A disabled offer cannot become an action just by changing its digest
        # or the family's list; the native Boolean remains authoritative.
        bad=deepcopy(dec);a=deepcopy(disabled['action']);row=dict(candidate_id=contract.digest(a),action=a)
        bad['candidates'].append(row);bad['families']['unit_order']['candidate_ids'].append(row['candidate_id'])
        with self.assertRaisesRegex(ValueError,'legal native offers'):self.validate(bad)
        bad=deepcopy(dec)
        removed=next(r for r in bad['candidates'] if r['action']['kind']=='unit_order')
        bad['candidates'].remove(removed);bad['families']['unit_order']['candidate_ids'].remove(removed['candidate_id'])
        with self.assertRaisesRegex(ValueError,'legal native offers'):self.validate(bad)

    def test_public_roster_signed_activity_unsigned_fields_and_no_private_extras(self):
        dec=self.value()
        mutations=(lambda v:v['unit_orders'].update(player_id=True),
            lambda v:v['unit_orders'].update(turn=2),lambda v:v['unit_orders'].update(private_units=[]),
            lambda v:v['unit_orders']['units'][0].update(unit_id=18),
            lambda v:v['unit_orders']['units'][0].update(activity_type=-2147483649),
            lambda v:v['unit_orders']['units'][0].update(activity_type=2147483648),
            lambda v:v['unit_orders']['units'][0].update(activity_type=True),
            lambda v:v['unit_orders']['units'][0].update(fortify_turns=2147483648),
            lambda v:v['unit_orders']['units'][0].update(ready=1),
            lambda v:v['unit_orders']['units'][0].update(hidden_target=3),
            lambda v:v['unit_orders']['units'].append(deepcopy(v['unit_orders']['units'][0])),
            lambda v:v['unit_orders']['offers'][0].update(legal=1),
            lambda v:v['unit_orders']['offers'][0]['action'].update(unit_id=88),
            lambda v:v['unit_orders']['offers'].append(deepcopy(v['unit_orders']['offers'][0])))
        for mutate in mutations:
            bad=deepcopy(dec);mutate(bad)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.validate(bad)
        bad=deepcopy(dec);bad['unit_orders']['units']=[];bad['unit_orders']['offers']=[];self.reconcile(bad)
        with self.assertRaisesRegex(ValueError,'roster'):self.validate(bad)
        with self.assertRaisesRegex(ValueError,'rosters'):
            contract.validate_capability_catalogue(seal(bad),self.identity,0,1,player_id=0)

    def test_action_names_routes_types_and_hashes_are_strict(self):
        for route,names in orders.NAMES.items():
            for name in names:
                orders.validate_action(dict(kind='unit_order',unit_id=0xffffffff,route=route,item_type=name,hash=0))
        action=native_catalog(self.obs)['offers'][0]['action']
        mutations=(dict(unit_id=True),dict(hash=-1),dict(hash=1<<32),dict(hash=True),
            dict(item_type='UNITCOMMAND_DELETE'),dict(item_type='UNITCOMMAND_CANCEL_SPY'),
            dict(item_type='UNITOPERATION_SLEEP'),dict(route='operation'),dict(route=True),
            dict(item_type=[]),dict(kind='move'),dict(target=7))
        for changes in mutations:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                orders.validate_action(dict(action,**changes))

    def test_xp2_v19_projection_only_removes_skip_from_retained_v18_catalogue(self):
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
        from civ6_host.runtime.paths import resource_root

        path = resource_root() / (
            'work/xp2-client-sessions/run-ad7f3a87560347138e0048fd67aa971b/checkpoint/checkpoint.json')
        if not path.is_file():
            self.skipTest('Retained private XP2 v18 witness required')
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'a19f5719aa03accf74afaf1d471925230bd4ac94fcb99bca575457d9048fbb6b')
        witness = json.loads(raw)
        saved = witness['decisions']
        live = deepcopy(saved)
        live['schema'] = contract.CAPABILITY_XP2_UNIT_SKIP_SCHEMA
        actor = live['unit_orders']['units'][0]['unit_id']
        skip = dict(kind='unit_order', unit_id=actor, route='operation',
                    item_type=orders.SKIP_TURN, hash=7)
        live['unit_orders']['offers'].append(dict(action=skip, legal=True))
        key = contract.digest(skip)
        live['candidates'].append(dict(action=skip, candidate_id=key))
        live['families']['unit_order']['candidate_ids'].append(key)
        seal(live)
        unchanged_live = deepcopy(live)
        restored, transition = contract.checkpoint_catalogue(
            live, saved, witness['observation'], core_sha256=XP2_CORE_SHA256)
        self.assertEqual(restored, saved)
        self.assertEqual(live, unchanged_live)
        self.assertEqual(transition['added_unit_order'], orders.SKIP_TURN)
        with self.assertRaisesRegex(ValueError, 'requires Gathering Storm'):
            contract.checkpoint_catalogue(live, saved, witness['observation'], core_sha256=XP1_CORE_SHA256)
        with self.assertRaisesRegex(ValueError, 'requires the v19 catalogue'):
            orders.validate_catalog(live['unit_orders'], saved['player_id'], saved['turn'], allow_skip=False)

    def test_partial_family_requires_explicit_other_orders_and_spy_gap(self):
        dec=self.value();self.validate(dec)
        for mutate in (lambda v:v['families'].pop('unit_order'),
                lambda v:v['families']['unit_order'].update(status='queried_complete'),
                lambda v:v['families']['unit_order'].update(unqualified=['spy_cancel_dialogue']),
                lambda v:v['families']['unit_order'].update(unqualified=['other_unit_commands_and_operations']),
                lambda v:v['families']['unit_order'].update(unqualified=['not_implemented']),
                lambda v:v.update(unit_orders=None)):
            bad=deepcopy(dec);mutate(bad)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.validate(bad)
        for offer in dec['unit_orders']['offers']:offer['legal']=False
        self.reconcile(dec);self.validate(dec)
        self.assertEqual(dec['families']['unit_order']['status'],'queried_partial')
        self.assertEqual(dec['families']['unit_order']['candidate_ids'],[])

    def test_unavailable_null_is_independent_of_world_reader_and_old_schemas_stay_exact(self):
        for kwargs in (dict(waiting=True),dict(closed=True),dict(missing=True)):
            dec=self.value(**kwargs);self.validate(dec,closed=kwargs.get('closed',False))
            self.assertIsNone(dec['unit_orders'])
            bad=deepcopy(dec);bad['unit_orders']=native_catalog(self.obs)
            with self.assertRaises(ValueError):self.validate(bad,closed=kwargs.get('closed',False))
        dec=self.value()
        dec['world_input']=dec['queued_orders']=None
        dec['candidates']=[r for r in dec['candidates'] if r['action']['kind'] not in ('world_select_unit','world_deselect_unit','world_plot_click')]
        for kind in ('world_select_unit','world_deselect_unit','world_plot_click'):
            dec['families'][kind]=dict(status='unqualified',reason='independent_world_query_unavailable')
        self.validate(dec)
        for schema in (contract.CAPABILITY_SCHEMA,contract.CAPABILITY_CHOICES_SCHEMA,
                       contract.CAPABILITY_TURNS_SCHEMA,contract.CAPABILITY_WORLD_SCHEMA):
            bad=self.value();bad['schema']=schema
            with self.subTest(schema=schema),self.assertRaises(ValueError):self.validate(bad)
        bad=self.value();bad.pop('unit_orders')
        with self.assertRaises(ValueError):self.validate(bad)

    def test_grid_budget_keeps_ordinary_limit_with_added_orders(self):
        obs=deepcopy(self.obs);obs.update(width=128,height=128)
        dec=self.value(obs=obs,selected=17);self.validate(dec,obs=obs)
        self.assertEqual(len(dec['families']['world_plot_click']['candidate_ids']),16384)
        # Six offers plus one selection per own unit must share the existing
        # ordinary budget, regardless of the separately allowed grid cells.
        obs=deepcopy(self.obs);template=obs['units'][0]
        obs['units']=[dict(template,id=i) for i in range(600)]
        dec=self.value(obs=obs)
        with self.assertRaisesRegex(ValueError,'Ordinary action catalogue'):self.validate(dec,obs=obs)

    def test_client_server_roundtrip_each_order_refused_and_forced_inactive(self):
        backend=OrderBackend();client=SessionClient(backend);view=client.reset()
        names=[(route,name) for route,values in orders.NAMES.items() for name in values
               if name != orders.SKIP_TURN]
        for route,name in names:
            dec=view['decisions'];row=next(r for r in dec['candidates'] if r['action'].get('item_type')==name)
            view=client.act(0,dec['decision_id'],row['candidate_id'])
            self.assertEqual(view['applied_action'],row['action'])
            self.assertEqual(backend.protocol.catalogues[0]['unit_orders'],view['decisions']['unit_orders'])
        backend.status='refused';dec=view['decisions']
        row=next(r for r in dec['candidates'] if r['action']['kind']=='unit_order')
        view=client.act(0,dec['decision_id'],row['candidate_id'])
        self.assertIsNone(view['applied_action']);self.assertEqual(client.command_result['status'],'refused')
        self.assertEqual(backend.aborts,[])
        waiting=OrderBackend(waiting=True);waiting.status='submitted';client=SessionClient(waiting);view=client.reset()
        dec=view['decisions'];row=next(r for r in dec['candidates'] if r['action']=={'kind':'force_end_turn'})
        self.assertTrue(contract.offered_forced_turn(dec,row['action']))
        view=client.act(0,dec['decision_id'],row['candidate_id'])
        self.assertIsNone(view['applied_action']);self.assertEqual(client.command_result['status'],'submitted')
        self.assertIsNone(view['decisions']['unit_orders']);self.assertEqual(waiting.aborts,[])

    def test_portable_imports_do_not_require_runtime_or_torch(self):
        script='''import sys,importlib.abc
class Refuse(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith(('civ6_host.runtime','torch')):raise AssertionError(fullname)
sys.meta_path.insert(0,Refuse())
from civ6_host.session_client import SessionClient
from civ6_host.contracts import network_turn,capability_unit_orders
assert network_turn.CAPABILITY_UNIT_ORDERS_SCHEMA.endswith('.v5')
capability_unit_orders.validate_action(dict(kind='unit_order',unit_id=1,route='command',item_type='UNITCOMMAND_WAKE',hash=0))
'''
        env=os.environ.copy();env.pop('CIV6_HOST_RESOURCE_ROOT',None)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()

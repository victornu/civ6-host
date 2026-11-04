"""Portable world-input v4 through the existing client and server protocol.

Responses are explicit wire fixtures, not native admission or gameplay proof.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import sys
import unittest

from civ6_host.contracts import network_turn as contract
from civ6_host.contracts import capability_world_input as world
from civ6_host.client import ProtocolError
from test_session_capabilities import catalogue, observation, seal, CapabilityBackend, SessionClient
from test_session_capabilities import validate_network_response


def value(identity, obs, *, sequence=0, selected=None, waiting=False, closed=False, missing=False):
    pid=obs['player_id']
    unavailable=waiting or closed or missing
    dec=catalogue(identity,sequence,pid,queried=not(waiting or closed),choices=False)
    dec['schema']=contract.CAPABILITY_WORLD_SCHEMA
    dec['choice_state']=None if waiting or closed else dict(research=dict(research=None,civic=None),production=[])
    if waiting:dec['turn_controls'].update(active=False,active_complete=False,can_unready=False)
    dec['turn_availability']=dict(end_turn=None if closed else False,
        force_end_turn=None if closed else True,unready_turn=None if closed else False)
    for kind,available in dec['turn_availability'].items():
        rows=[]
        if available is True:
            action=dict(kind=kind);rows=[dict(candidate_id=contract.digest(action),action=action)]
        dec['candidates'].extend(rows)
        dec['families'][kind]=(dict(status='unqualified',reason='closed') if available is None else
            dict(status='queried_complete',candidate_ids=[row['candidate_id'] for row in rows]))
    dec['world_input']=None if unavailable else dict(schema=world.SCHEMA,player_id=pid,turn=obs['turn'],
        width=obs['width'],height=obs['height'],units=[dict(unit_id=u['id'],ignore_moves=False) for u in obs['units']],
        selected_unit_id=selected,war_prompt=None)
    dec['queued_orders']=None if unavailable else dict(player_id=pid,turn=obs['turn'],width=obs['width'],height=obs['height'],
        units=[dict(unit_id=u['id'],plot_id=None) for u in obs['units']])
    actions=[] if unavailable else world.actions(dec['world_input'])
    for kind in sorted(world.WORLD_KINDS):
        rows=[dict(candidate_id=contract.digest(a),action=a) for a in actions if a['kind']==kind]
        dec['candidates'].extend(rows)
        family=dict(status='unqualified',reason='native_world_reader_unavailable') if unavailable else dict(
            status='queried_partial' if kind=='world_plot_click' else 'queried_complete',
            candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable and kind=='world_plot_click':family['unqualified']=list(world.UNQUALIFIED_WORLD_CLICK)
        dec['families'][kind]=family
    return seal(dec)


class WorldBackend(CapabilityBackend):
    def __init__(self,*,waiting=False):
        super().__init__();self.waiting=waiting;self.selected={};self.queued={}

    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation=='close':return reply
        obs=reply['observation']
        if player in self.queued:obs['units'][0]['moves']=0
        reply['decisions']=value(self.identity,obs,sequence=sequence,
            selected=self.selected.get(player),waiting=self.waiting)
        if not self.waiting and player in self.queued:
            reply['decisions']['queued_orders']['units'][0]['plot_id']=self.queued[player]
            seal(reply['decisions'])
        if self.waiting:reply['session']['active_human_player_ids']=[]
        return reply

    def request(self,request):
        self.calls.append(deepcopy(request))
        operation=self.protocol.validate(request)
        action=self.protocol.selected(request) if operation=='act' else None
        if action is not None and self.status=='completed':
            pid=request['player_id']
            if action['kind']=='world_select_unit':self.selected[pid]=action['unit_id']
            elif action['kind']=='world_deselect_unit':self.selected[pid]=None
            elif action['kind']=='world_plot_click':self.queued[pid]=action['plot_id']
        reply=self._reply(operation,request['sequence'],request['player_id'],action)
        validate_network_response(reply,self.protocol,operation,request=request)
        self.protocol.commit_reply(request,reply);self.protocol.accept_response(reply)
        if self.fault is not None:self.fault(reply)
        return reply


class WorldCapabilities(unittest.TestCase):
    def setUp(self):
        self.identity=SimpleNamespace(episode_id='world-episode',game_generation='world-generation')
        self.obs=observation()

    def validate(self,dec,*,obs=None,closed=False):
        return contract.validate_capability_catalogue(seal(dec),self.identity,0,1,
            player_id=0,observation=self.obs if obs is None else obs,actions_closed=closed)

    def test_large_whole_grid_budget_and_hidden_zero_moves_are_not_filtered(self):
        obs=deepcopy(self.obs);obs.update(width=128,height=128)
        obs['units'][0]['moves']=0
        dec=value(self.identity,obs,selected=17);self.validate(dec,obs=obs)
        clicks=[r['action'] for r in dec['candidates'] if r['action']['kind']=='world_plot_click']
        self.assertEqual(len(clicks),16384)
        self.assertEqual({a['plot_id'] for a in clicks},set(range(16384)))
        self.assertEqual(obs['plots'],[])
        for omitted in (0,9000,16383):
            bad=deepcopy(dec)
            bad['candidates']=[r for r in bad['candidates'] if r['action'].get('plot_id')!=omitted]
            bad['families']['world_plot_click']['candidate_ids']=[r['candidate_id'] for r in bad['candidates'] if r['action']['kind']=='world_plot_click']
            with self.subTest(omitted=omitted),self.assertRaisesRegex(ValueError,'full-grid'):
                self.validate(bad,obs=obs)
        too_many=value(self.identity,self.obs)
        too_many['world_input']['units']=[dict(unit_id=i,ignore_moves=False) for i in range(4096)]
        too_many['queued_orders']['units']=[dict(unit_id=i,plot_id=None) for i in range(4096)]
        rows=[dict(candidate_id=contract.digest(a),action=a) for a in world.actions(too_many['world_input'])]
        too_many['candidates']=[r for r in too_many['candidates'] if r['action']['kind'] not in world.WORLD_KINDS]+rows
        too_many['families']['world_select_unit']['candidate_ids']=[r['candidate_id'] for r in rows]
        with self.assertRaisesRegex(ValueError,'Ordinary action catalogue'):
            contract.validate_capability_catalogue(seal(too_many),self.identity,0,1,player_id=0)

    def test_exact_family_completeness_and_explicit_nonmove_war_gaps(self):
        dec=value(self.identity,self.obs,selected=17);self.validate(dec)
        changes=(lambda v:v['families']['world_plot_click'].update(status='queried_complete'),
            lambda v:v['families']['world_plot_click'].update(unqualified=['war_confirmation']),
            lambda v:v['families']['world_select_unit'].update(status='queried_partial',unqualified=['arbitrary']),
            lambda v:v['families'].pop('world_deselect_unit'),
            lambda v:v['world_input'].update(war_prompt=dict(attacking_player=0,defending_player=1,war_type=0)),
            lambda v:v['world_input'].update(schema='civ6rl.world_input.v2'),
            lambda v:v['world_input'].update(hidden_paths=[]),
            lambda v:v['world_input'].update(selected_unit_id=18))
        for mutate in changes:
            bad=deepcopy(dec);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.validate(bad)
        # IgnoreMoves is a source-defined unit-type property, not moves remaining.
        ignored=value(self.identity,self.obs)
        ignored['world_input']['units'][0]['ignore_moves']=True
        ignored['candidates']=[r for r in ignored['candidates'] if r['action']['kind']!='world_select_unit']
        ignored['families']['world_select_unit']['candidate_ids']=[]
        self.validate(ignored)

    def test_waiting_closed_and_unqueried_are_null_not_empty_success(self):
        for kwargs in (dict(waiting=True),dict(closed=True),dict(missing=True)):
            dec=value(self.identity,self.obs,**kwargs);self.validate(dec,closed=kwargs.get('closed',False))
            self.assertIsNone(dec['world_input']);self.assertIsNone(dec['queued_orders'])
            for field in ('world_input','queued_orders'):
                bad=deepcopy(dec);bad[field]=value(self.identity,self.obs)[field]
                with self.subTest(kwargs=kwargs,field=field),self.assertRaises(ValueError):
                    self.validate(bad,closed=kwargs.get('closed',False))
            bad=deepcopy(dec);bad['families']['world_select_unit']=dict(status='queried_complete',candidate_ids=[])
            with self.assertRaises(ValueError):self.validate(bad,closed=kwargs.get('closed',False))

    def test_owned_rosters_queue_geometry_types_and_exact_actions(self):
        dec=value(self.identity,self.obs,selected=17)
        mutations=(lambda v:v['world_input'].update(width=9),
            lambda v:v['world_input'].update(player_id=True),lambda v:v['world_input'].update(turn=2),
            lambda v:v['world_input']['units'][0].update(unit_id=18),
            lambda v:v['world_input']['units'][0].update(ignore_moves=0),
            lambda v:v['queued_orders']['units'][0].update(plot_id=64),
            lambda v:v['queued_orders']['units'][0].update(plot_id=True),
            lambda v:v['queued_orders']['units'][0].update(unit_id=18),
            lambda v:v['queued_orders']['units'].append(dict(unit_id=17,plot_id=None)),
            lambda v:v['queued_orders'].update(turn=2))
        for mutate in mutations:
            bad=deepcopy(dec);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.validate(bad)
        click=dict(kind='world_plot_click',unit_id=17,plot_id=63,x=7,y=7)
        world.validate_action(click);world.validate_action(click,width=8,height=8)
        for bad in (dict(click,unit_id=True),dict(click,unit_id=-1),dict(click,plot_id=16384),
                dict(click,x=512),dict(click,y=True),dict(click,operation='MOVE_TO'),
                dict(kind='world_war_response',accept=True)):
            with self.subTest(action=bad),self.assertRaises(ValueError):world.validate_action(bad)
        with self.assertRaises(ValueError):world.validate_action(dict(click,plot_id=62),width=8,height=8)

    def test_v1_v2_v3_do_not_admit_new_fields_or_actions(self):
        for schema in (contract.CAPABILITY_SCHEMA,contract.CAPABILITY_CHOICES_SCHEMA,contract.CAPABILITY_TURNS_SCHEMA):
            dec=value(self.identity,self.obs,selected=17);dec['schema']=schema
            with self.subTest(schema=schema),self.assertRaises(ValueError):self.validate(dec)
        self.assertNotIn(contract.CAPABILITY_WORLD_SCHEMA,contract.MAP_SCHEMAS)
        self.assertEqual(contract.LATEST_SCHEMA,contract.PRODUCTION_SCHEMA)

    def test_portable_client_server_select_click_queue_refusal_deselect(self):
        backend=WorldBackend();client=SessionClient(backend);view=client.reset()
        def choose(kind,**fields):
            dec=client.view()['decisions']
            row=next(r for r in dec['candidates'] if r['action']['kind']==kind and all(r['action'].get(k)==v for k,v in fields.items()))
            return client.act(0,dec['decision_id'],row['candidate_id'])
        view=choose('world_select_unit',unit_id=17)
        self.assertEqual(view['decisions']['world_input']['selected_unit_id'],17)
        view=choose('world_plot_click',plot_id=63)
        self.assertEqual(view['decisions']['queued_orders']['units'],[dict(unit_id=17,plot_id=63)])
        self.assertEqual(view['observation']['units'][0]['moves'],0)
        self.assertEqual(len(view['decisions']['families']['world_plot_click']['candidate_ids']),64)
        queued=deepcopy(view['decisions']['queued_orders']);backend.status='refused'
        view=choose('world_plot_click',plot_id=0)
        self.assertIsNone(view['applied_action']);self.assertEqual(client.command_result['status'],'refused')
        self.assertEqual(view['decisions']['queued_orders'],queued)
        backend.status='completed';view=choose('world_deselect_unit')
        self.assertIsNone(view['decisions']['world_input']['selected_unit_id'])
        self.assertEqual(view['decisions']['families']['world_plot_click']['candidate_ids'],[])
        self.assertEqual(backend.aborts,[]);client.close()

    def test_inactive_force_v4_crosses_client_server_and_never_claims_applied(self):
        backend=WorldBackend(waiting=True);backend.status='submitted'
        client=SessionClient(backend);view=client.reset()
        for status in ('submitted','refused'):
            backend.status=status;dec=view['decisions']
            row=next(r for r in dec['candidates'] if r['action']=={'kind':'force_end_turn'})
            self.assertTrue(contract.offered_forced_turn(dec,row['action']))
            view=client.act(0,dec['decision_id'],row['candidate_id'])
            self.assertEqual(client.command_result['status'],status)
            self.assertIsNone(view['applied_action']);self.assertIsNone(view['decisions']['world_input'])
        self.assertEqual(len(backend.calls),2);self.assertEqual(backend.aborts,[])

    def test_client_only_imports_do_not_need_runtime_resources_or_torch(self):
        source=Path(__file__).resolve().parents[1]/'src'
        script='''import sys, importlib.abc
class Refuse(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith(('civ6_host.runtime','torch')): raise AssertionError(fullname)
sys.meta_path.insert(0,Refuse())
from civ6_host.session_client import SessionClient
from civ6_host.contracts import network_turn,capability_world_input
assert network_turn.CAPABILITY_WORLD_SCHEMA.endswith('.v4')
capability_world_input.validate_action({'kind':'world_deselect_unit'})
'''
        env=os.environ.copy();env.pop('CIV6_HOST_RESOURCE_ROOT',None);env['PYTHONPATH']=str(source)
        done=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(done.returncode,0,done.stderr)


if __name__=='__main__':unittest.main()

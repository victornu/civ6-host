"""Portable queue capability fixtures, not native availability evidence."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import ast
import importlib.util
import unittest

from civ6_host.contracts import network_turn as contract, production_queue as queue
from civ6_host.session_client import SessionClient, InformationUnavailable
import test_capability_unit_orders as unit_tests
from test_capability_world_contract import value as world_value
from test_session_capabilities import observation, seal


def entry(index,position):
    return dict(position=position,category='unit',index=index,hash=100+index,formation=0,
                formation_display=dict(is_corps=False,is_army=False))


def extend(dec,obs,*,size=2,unavailable=False,enabled=True):
    dec['schema']=contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA
    values=None if unavailable else []
    if not unavailable:
        for city in obs['cities']:
            cid=city['id'];entries=[entry(i,i) for i in range(size)]
            offers=[]
            if enabled:
                offers.append(dict(kind='queue_append',city_id=cid,category='unit',index=10,hash=110,
                                   item_type='UNIT_SCOUT',mode='replace_tail' if size==8 else 'append'))
                offers.extend(dict(kind='queue_remove',city_id=cid,position=i) for i in range(size))
                offers.extend(dict(kind='queue_swap',city_id=cid,source_position=i,destination_position=j)
                              for i in range(size) for j in range(size) if i!=j)
            values.append(dict(schema=queue.PUBLIC_SCHEMA,player_id=obs['player_id'],turn=obs['turn'],
                               city_id=cid,enabled=enabled,entries=entries,offers=offers))
        dec['choice_state']['production']=[dict(city_id=q['city_id'],queue_size=size,
            kind='U' if size else 'N',item_index=0 if size else None,hash=100 if size else 0,
            formation=0 if size else None) for q in values]
    dec['production_queues']=values
    if unavailable and dec['choice_state'] is not None:
        dec['choice_state']['production']=[dict(city_id=c['id'],queue_size=0,kind='N',item_index=None,hash=0,formation=None)
                                           for c in obs['cities']]
    for kind in queue.FIELDS:
        rows=[] if values is None else [dict(candidate_id=contract.digest(a),action=deepcopy(a))
                                      for q in values for a in q['offers'] if a['kind']==kind]
        dec['candidates'].extend(rows)
        family=(dict(status='unqualified',reason='fixture_native_query_unavailable') if unavailable else
                dict(status='queried_complete',candidate_ids=[r['candidate_id'] for r in rows]))
        if not unavailable and kind=='queue_append':family.update(status='queried_partial',unqualified=list(queue.UNQUALIFIED_APPEND))
        dec['families'][kind]=family
    return seal(dec)


class QueueBackend(unit_tests.OrderBackend):
    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation!='close':
            if getattr(self,'city_fixture',False):
                reply['observation']['cities']=[dict(id=23,x=3,y=4,owner=player,population=1,
                    yields=dict(food=2,production=1,gold=1,science=1,culture=1,faith=0))]
            extend(reply['decisions'],reply['observation'],unavailable=self.waiting)
        return reply


class QueueCapabilities(unittest.TestCase):
    def setUp(self):
        self.identity=SimpleNamespace(episode_id='queue-fixture',game_generation='queue-generation')
        self.obs=observation()
        self.obs['cities']=[dict(id=23,x=3,y=4,owner=0,population=1,
            yields=dict(food=2,production=1,gold=1,science=1,culture=1,faith=0))]

    def value(self,*,size=2,waiting=False,closed=False,missing=False,enabled=True):
        d=world_value(self.identity,self.obs,waiting=waiting,closed=closed)
        d=unit_tests.extend(d,self.obs,unavailable=waiting or closed)
        return extend(d,self.obs,size=size,unavailable=waiting or closed or missing,enabled=enabled)

    def validate(self,d,*,closed=False):
        return contract.validate_capability_catalogue(seal(d),self.identity,0,1,player_id=0,
                                                     observation=self.obs,actions_closed=closed)

    def test_exact_existing_public_schema_and_full_eighth_slot_mode(self):
        for size in (0,2,8):
            d=self.value(size=size);self.validate(d)
            self.assertEqual(d['production_queues'][0]['schema'],queue.PUBLIC_SCHEMA)
            self.assertEqual(d['production_queues'][0]['offers'][0]['mode'],'replace_tail' if size==8 else 'append')
        self.assertEqual(contract.LATEST_SCHEMA,contract.PRODUCTION_SCHEMA)

    def test_unavailable_none_is_distinct_from_native_empty_or_disabled_query(self):
        self.validate(self.value(missing=True))
        self.validate(self.value(waiting=True))
        self.validate(self.value(closed=True),closed=True)
        d=self.value(enabled=False);self.validate(d)
        self.assertEqual(d['production_queues'][0]['offers'],[])
        self.assertEqual(d['families']['queue_remove']['status'],'queried_complete')
        d=self.value(missing=True);d['production_queues']=[]
        with self.assertRaises(ValueError):self.validate(d)

    def test_roster_head_size_order_and_formation_are_exact(self):
        for mode in ('owner','head','size','order','formation','schema','bool'):
            d=self.value();q=d['production_queues'][0]
            if mode=='owner':q['city_id']=24
            elif mode=='head':q['entries'][0]['hash']+=1
            elif mode=='size':q['entries'].pop()
            elif mode=='order':q['entries'].reverse()
            elif mode=='formation':q['entries'][0]['formation']=1
            elif mode=='schema':q.pop('schema')
            else:q['entries'][0]['position']=False
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate(d)

    def test_exact_offers_no_strategy_filter_no_fake_full_family(self):
        for mode in ('omit','duplicate','unoffered','complete','gap'):
            d=self.value()
            if mode=='omit':d['production_queues'][0]['offers'].pop()
            elif mode=='duplicate':d['production_queues'][0]['offers'].append(deepcopy(d['production_queues'][0]['offers'][0]))
            elif mode=='unoffered':d['candidates'][-1]['action']['source_position']=0
            elif mode=='complete':d['families']['queue_append']=dict(status='queried_complete',candidate_ids=d['families']['queue_append']['candidate_ids'])
            else:d['families']['queue_append']['unqualified']=[]
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate(d)

    def test_invalid_mode_position_self_swap_and_boolean_rejected(self):
        examples=[dict(kind='queue_remove',city_id=23,position=8),
            dict(kind='queue_swap',city_id=23,source_position=1,destination_position=1),
            dict(kind='queue_remove',city_id=True,position=0),
            dict(kind='queue_append',city_id=23,category='unit',index=1,hash=101,item_type='UNIT_SCOUT',mode='push')]
        for a in examples:
            with self.subTest(action=a),self.assertRaises(ValueError):queue.validate_action(a)

    def test_common_client_accepts_v6_without_inventing_production_information(self):
        b=QueueBackend();b.city_fixture=True;client=SessionClient(b);v=client.reset()
        self.assertEqual(v['decisions']['schema'],contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA)
        # These are wire responses, not a claim of queue effects (those are
        # checked separately against native result receipts by the reviewer).
        for kind in queue.FIELDS:
            row=next(r for r in v['decisions']['candidates'] if r['action']['kind']==kind)
            v=client.act(v['observation']['player_id'],v['decisions']['decision_id'],row['candidate_id'])
            self.assertEqual(v['applied_action'],row['action'])
            self.assertEqual(b.calls[-1]['selection']['candidate_id'],row['candidate_id'])
        with self.assertRaises(InformationUnavailable):client.information('production')
        client.close()

    def test_extraction_delegates_exact_pure_bodies_and_refuses_drift(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('queue_extraction',root/'tools/extraction_contract_production_queue.py')
        hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
        raw=(root.parent/'civ6-rl-lab/civ6rl/native_saved_production_queue.py').read_text(encoding='utf8')
        transformed=hook.parameterize('civ6rl.native_saved_production_queue',raw)
        tree=ast.parse(transformed)
        self.assertFalse(any(isinstance(n,ast.FunctionDef) and n.name in hook.TARGETS for n in tree.body))
        self.assertIn('from civ6_host.contracts.production_queue import',transformed)
        mutated=raw.replace("maximum=0xffffffff","maximum=42")
        self.assertNotEqual(mutated,raw)
        with self.assertRaises(ValueError):hook.parameterize('civ6rl.native_saved_production_queue',mutated)


if __name__=='__main__':unittest.main()

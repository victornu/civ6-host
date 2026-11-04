"""Portable v7 wire fixtures, not native placement legality or availability."""
from copy import deepcopy
from pathlib import Path
import ast
import importlib.util
import unittest

from civ6_host.contracts import network_turn as contract, placement
from civ6_host.session_client import SessionClient
import test_capability_production_queue as queue_tests
from test_session_capabilities import seal


def visible_plot(obs):
    obs['plots']=[dict(index=28,x=4,y=3,visible=True,revealed=True,terrain_type=0,feature_type=-1,
                       owner=obs['player_id'],water=False,impassable=False)]


def extend(dec,obs,*,unavailable=False):
    dec['schema']=contract.CAPABILITY_PLACEMENT_SCHEMA
    offers=None if unavailable else []
    if not unavailable and obs['cities']:
        cid=obs['cities'][0]['id']
        offers=[dict(kind='production_placement',city_id=cid,category='district',index=1,hash=201,
            item_type='DISTRICT_HOLY_SITE',mode='place',plot_id=28,x=4,y=3),
            dict(kind='production_resume',city_id=cid,category='building',index=2,hash=202,item_type='BUILDING_ORACLE')]
    dec.update(placement_offers=offers,placements=None if unavailable else [],
               placement_observation_scope=None if unavailable else placement.OBSERVATION_SCOPE)
    for kind in placement.ACTION_FIELDS:
        rows=[] if unavailable else [dict(candidate_id=contract.digest(a),action=deepcopy(a)) for a in offers if a['kind']==kind]
        dec['candidates'].extend(rows)
        dec['families'][kind]=(dict(status='unqualified',reason='fixture_reader_unavailable') if unavailable else
            dict(status='queried_partial',candidate_ids=[r['candidate_id'] for r in rows],unqualified=list(placement.GAPS[kind])))
    return seal(dec)


class PlacementBackend(queue_tests.QueueBackend):
    def _reply(self,operation,sequence,player,requested=None):
        reply=super()._reply(operation,sequence,player,requested)
        if operation!='close':
            visible_plot(reply['observation']);extend(reply['decisions'],reply['observation'],unavailable=self.waiting)
        return reply


class PlacementContract(unittest.TestCase):
    def setUp(self):
        self.fixture=queue_tests.QueueCapabilities();self.fixture.setUp();visible_plot(self.fixture.obs)

    def value(self,**kw):
        d=self.fixture.value(**kw)
        return extend(d,self.fixture.obs,unavailable=any(kw.get(k) for k in ('waiting','closed','missing')))

    def validate(self,d,*,closed=False):return self.fixture.validate(seal(d),closed=closed)

    def test_actual_base_action_shapes_and_tracked_scope_no_complete_claim(self):
        d=self.value();self.validate(d)
        self.assertNotIn('plot_id',d['placement_offers'][1])
        self.assertEqual(d['placement_observation_scope'],'host_tracked')
        self.assertFalse(d['complete_action_space'])
        self.assertEqual(contract.LATEST_SCHEMA,contract.PRODUCTION_SCHEMA)

    def test_public_ownership_visibility_exact_offers_and_resume_no_new_plot(self):
        for mode in ('owner','hidden','coordinate','duplicate','scope','resume_coords','boolean','omit'):
            d=self.value()
            if mode=='owner':d['placement_offers'][0]['city_id']=25
            elif mode=='hidden':d['placement_offers'][0].update(plot_id=29,x=5)
            elif mode=='coordinate':d['placement_offers'][0]['x']=1
            elif mode=='duplicate':d['placement_offers'].append(deepcopy(d['placement_offers'][0]))
            elif mode=='scope':d['placement_observation_scope']='all_native_placements'
            elif mode=='resume_coords':d['placement_offers'][1]['plot_id']=28
            elif mode=='boolean':d['placement_offers'][0]['hash']=True
            else:d['placement_offers'].pop()
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate(d)

    def test_null_unavailable_is_not_successful_empty_query_and_old_schemas_remain_exact(self):
        for kw in (dict(waiting=True),dict(closed=True),dict(missing=True)):
            d=self.value(**kw);self.validate(d,closed=kw.get('closed',False))
            bad=deepcopy(d);bad['placements']=[]
            with self.assertRaises(ValueError):self.validate(bad,closed=kw.get('closed',False))
        d=self.value();d['families']['production_resume']['status']='queried_complete'
        with self.assertRaises(ValueError):self.validate(d)
        d=self.value();d['families']['production_placement']['unqualified'].pop()
        with self.assertRaises(ValueError):self.validate(d)
        d=self.value();d['schema']=contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA
        with self.assertRaises(ValueError):self.validate(d)

    def test_tracked_progress_has_native_boolean_identity_and_current_visible_plot(self):
        row=dict(city_id=23,category='district',index=1,item_type='DISTRICT_HOLY_SITE',plot_id=28,x=4,y=3,
                 placement_turn=1,observed_turn=1,exists=True,complete=False)
        d=self.value();d['placements']=[row];self.validate(d)
        for patch in (dict(complete=1),dict(exists=False,complete=True),dict(observed_turn=2),dict(plot_id=0),dict(city_id=50)):
            bad=self.value();bad['placements']=[dict(row,**patch)]
            with self.subTest(patch=patch),self.assertRaises(ValueError):self.validate(bad)

    def test_shared_client_routes_both_explicit_inputs_without_legacy_catalogue(self):
        backend=PlacementBackend();backend.city_fixture=True;client=SessionClient(backend);v=client.reset()
        for kind in placement.ACTION_FIELDS:
            row=next(r for r in v['decisions']['candidates'] if r['action']['kind']==kind)
            v=client.act(0,v['decisions']['decision_id'],row['candidate_id'])
            self.assertEqual(v['applied_action'],row['action'])
            self.assertEqual(backend.calls[-1]['selection']['candidate_id'],row['candidate_id'])
        client.close()

    def test_pure_extraction_preserves_four_exact_legacy_validator_bodies(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('placement_hook',root/'tools/extraction_contract_placement.py')
        hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
        raw=(root.parent/'civ6-rl-lab/civ6rl/native_saved_placement.py').read_text(encoding='utf8')
        transformed=hook.parameterize('civ6rl.native_saved_placement',raw)
        tree=ast.parse(transformed)
        self.assertFalse(any(isinstance(n,ast.FunctionDef) and n.name in hook.TARGETS for n in tree.body))
        mutated=raw.replace('len(rows)>256','len(rows)>255')
        self.assertNotEqual(raw,mutated)
        with self.assertRaises(ValueError):hook.parameterize('civ6rl.native_saved_placement',mutated)

    def test_checkpoint_projection_only_removes_freshly_validated_additions(self):
        for target in (contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA,contract.CAPABILITY_UNIT_ORDERS_SCHEMA):
            current=self.value();saved=deepcopy(self.fixture.value())
            if target==contract.CAPABILITY_UNIT_ORDERS_SCHEMA:
                saved.pop('production_queues')
                saved['families']={k:v for k,v in saved['families'].items() if not k.startswith('queue_')}
                saved['candidates']=[r for r in saved['candidates'] if not r['action']['kind'].startswith('queue_')]
                saved['schema']=target;seal(saved)
            before=deepcopy(current)
            projected,transition=contract.checkpoint_catalogue(current,saved,self.fixture.obs)
            self.assertEqual(projected,saved);self.assertEqual(current,before)
            self.assertEqual(transition['source_schema'],target);self.assertTrue(transition['historical_fields_unchanged'])
            mutated=deepcopy(current);mutated['placement_offers'][0]['x']=0;seal(mutated)
            with self.assertRaises(ValueError):contract.checkpoint_catalogue(mutated,saved,self.fixture.obs)
            changed=deepcopy(current);changed['choice_state']['research']['research']=17;seal(changed)
            projected,_=contract.checkpoint_catalogue(changed,saved,self.fixture.obs)
            self.assertNotEqual(projected['choice_state'],saved['choice_state'])


if __name__=='__main__':unittest.main()

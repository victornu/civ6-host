"""Reviewer input joins only: retained evidence/fixtures, no native execution."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn as contract, placement, production_queue
from civ6_host.runtime import network_checkpoint
import test_capability_placement as placement_tests
from test_capability_world_contract import value as world_value
import test_capability_unit_orders as unit_tests
import test_capability_production_queue as queue_tests
from test_session_capabilities import seal

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=dict(path='work/reviewer-fixture/checkpoint.json',sha256='a'*64)
ORIGIN=dict(path='work/reviewer-fixture/official.json',sha256='b'*64)
EPISODE='00000000-0000-4000-8000-000000000017'


def functions():
    ns={}
    source=ROOT/'tools/review_xp1_session.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)
           and n.name in ('review_lifetime_seconds','review_placement_input')]
    review=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='review')
    # Execute the actual full public-schema admission block, including the
    # portable validator. This catches the former accidental truthy tuple.
    block=next(n for n in ast.walk(review) if isinstance(n,ast.If)
               and isinstance(n.test,ast.Name) and n.test.id=='input_group'
               and any(isinstance(x,ast.ImportFrom) for x in n.body))
    wrapper=ast.parse('def validate_public(view, order_group=False, checkpoint_group=False, queue_group=False, placement_group=False, inventory_group=False, attack_group=False):\n pass').body[0]
    wrapper.body=ast.parse("seq=view['sequence']").body+block.body;nodes.append(wrapper)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(source),'exec'),ns)
    source=ROOT/'tools/qualify_xp1_configuration.py'
    nodes=[n for n in ast.parse(source.read_text(encoding='utf-8')).body
           if isinstance(n,ast.FunctionDef) and n.name in ('saved_load_validate_supervision','saved_load_events')]
    import hashlib
    ns.update(Path=Path,json=json,hashlib=hashlib)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
    return ns


def turn_tree(value, turn):
    if type(value) is dict:
        return {k:(turn if k in ('turn','observed_turn','current_game_turn') else turn_tree(v,turn)) for k,v in value.items()}
    if type(value) is list:return [turn_tree(v,turn) for v in value]
    return value


def fixture(turn=2, saved_schema=contract.CAPABILITY_PLACEMENT_SCHEMA):
    f=placement_tests.PlacementContract();f.setUp()
    f.fixture.identity=SimpleNamespace(episode_id=EPISODE,game_generation='native-'+EPISODE)
    observation=turn_tree(deepcopy(f.fixture.obs),turn)
    current=seal(turn_tree(f.value(),turn));old=deepcopy(current)
    if saved_schema!=current['schema']:
        old['schema']=saved_schema
        for key in ('placements','placement_offers','placement_observation_scope'):old.pop(key)
        kinds=set(placement.ACTION_FIELDS)
        if saved_schema==contract.CAPABILITY_UNIT_ORDERS_SCHEMA:
            old.pop('production_queues');kinds.update(production_queue.FIELDS)
        for kind in kinds:old['families'].pop(kind)
        old['candidates']=[row for row in old['candidates'] if row['action']['kind'] not in kinds]
        seal(old)
    initial=dict(observation=observation,decisions=current,sequence=0,
                 episode_id=current['episode_id'],game_generation=current['game_generation'],
                 outcome=dict(terminated=False,truncated=False))
    _,transition=contract.checkpoint_catalogue(current,old,observation)
    closure=dict(network_checkpoint=deepcopy(REFERENCE),official_bundle=deepcopy(ORIGIN),
                 checkpoint_on_close=False,initial_turn=turn,lifetime_seconds=300)
    marker=dict(checkpoint=list(REFERENCE.values()),turn=turn,public_observation_equal=True,
                public_decisions_equal=transition is None,saved_decision_fields_equal=True,
                catalogue_transition=transition,identity_rebound=True,
                complete_state_compared=False,strategic_training_ready=False)
    events=dict(official_lan_checkpoint_reloaded=marker,_event_lines=dict(
        xp1_saved_player_view_returned=10,official_lan_checkpoint_reloaded=12,
        before_xp1_saved_unit_commands=30,before_xp1_saved_loaded_close=40),
        _transition_intervals=[dict(first_line=20),dict(first_line=30)])
    manifest=dict(observed_game_turn=turn,observation=deepcopy(observation),decisions=old)
    return closure,events,initial,manifest


class ReviewerInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ns=functions()

    def test_actual_schema_admission_accepts_supported_versions_and_refuses_invalid_boundary(self):
        f=placement_tests.PlacementContract();f.setUp();obs=f.fixture.obs
        f.fixture.identity=SimpleNamespace(episode_id=EPISODE,game_generation='native-'+EPISODE)
        world_obs=deepcopy(obs);world_obs['cities']=[]
        d=world_value(f.fixture.identity,world_obs)
        versions=[deepcopy(d)]
        unit_tests.extend(d,world_obs);versions.append(deepcopy(d))
        queue_tests.extend(d,world_obs);versions.append(deepcopy(d))
        versions.append(f.value())
        for d in versions:
            view=dict(observation=obs if d['schema']==contract.CAPABILITY_PLACEMENT_SCHEMA else world_obs,
                      decisions=d,sequence=0,episode_id=d['episode_id'],
                      game_generation=d['game_generation'],outcome=dict(terminated=False,truncated=False))
            self.ns['validate_public'](view)
            if d['schema']==contract.CAPABILITY_PLACEMENT_SCHEMA:
                self.ns['validate_public'](view,placement_group=True)
                bad=deepcopy(view);bad['decisions'].pop('placements')
                with self.assertRaises(ValueError):self.ns['validate_public'](bad,placement_group=True)
            else:
                with self.assertRaises(ValueError):self.ns['validate_public'](view,placement_group=True)
        bad=deepcopy(view);bad['decisions']['schema']='unknown'
        with self.assertRaises(ValueError):self.ns['validate_public'](bad)

    def test_exact_run_budget_and_unchanged_supervision_guards(self):
        pins={'fixture.py':'a'*64}
        report=dict(reaped=True,job_assigned=True,exit_code=90,error=None,timed_out=False,
                    memory_limit_bytes=512*1024*1024,stdout_limit_bytes=64*1024*1024,
                    source_unchanged={'fixture.py':True})
        for seconds in (45,60,120,300,420):
            r=dict(report,timeout_seconds=seconds);c=dict(lifetime_seconds=seconds)
            value=self.ns['review_lifetime_seconds'](c,r)
            self.ns['saved_load_validate_supervision'](r,pins,lifetime_seconds=value)
        for seconds in (True,120.0,'300',301,600):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):
                self.ns['review_lifetime_seconds'](dict(lifetime_seconds=seconds),dict(report,timeout_seconds=seconds))
        with self.assertRaises(ValueError):
            self.ns['review_lifetime_seconds'](dict(lifetime_seconds=300),dict(report,timeout_seconds=120))
        for change in (dict(timed_out=True),dict(reaped=False),dict(memory_limit_bytes=1024*1024*1024),
                       dict(error='failure'),dict(source_unchanged={'fixture.py':False}),dict(timeout_seconds=120)):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.ns['saved_load_validate_supervision'](dict(report,timeout_seconds=300)|change,pins,lifetime_seconds=300)

    def test_review_admission_keeps_v10_exact_and_accepts_validated_v11_supersets(self):
        from test_capability_combat_precision import CombatPrecisionTests
        f=CombatPrecisionTests();f.setUp()
        for schema in (contract.CAPABILITY_COMBAT_PUBLIC_SCHEMA,contract.CAPABILITY_COMBAT_READINESS_SCHEMA):
            decisions=deepcopy(f.current);decisions['schema']=schema;seal(decisions)
            view=dict(observation=f.obs,decisions=decisions,sequence=decisions['sequence'],
                episode_id=decisions['episode_id'],game_generation=decisions['game_generation'],
                outcome=dict(terminated=False,truncated=False))
            for family in ('order_group','checkpoint_group','queue_group','placement_group','inventory_group','attack_group'):
                self.ns['validate_public'](view,**{family:True})
            bad=deepcopy(view);bad['decisions']['unit_attacks']['cities'][0]['defense_strength']=22.5
            seal(bad['decisions'])
            with self.subTest(schema=schema),self.assertRaises(ValueError):
                self.ns['validate_public'](bad,attack_group=True)

    def verify(self,closure,events,initial,manifest):
        with patch.object(network_checkpoint,'normalize',return_value=tuple(REFERENCE.values())), \
             patch.object(network_checkpoint,'manifest',return_value=manifest) as checked:
            result=self.ns['review_placement_input'](closure,events,initial)
            checked.assert_called_once_with(closure['network_checkpoint'],official_bundle=closure['official_bundle'])
            return result

    def test_later_turn_and_legacy_catalogue_projection_join_exact_checkpoint(self):
        for turn in (2,17):
            for schema in (contract.CAPABILITY_UNIT_ORDERS_SCHEMA,contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA,
                           contract.CAPABILITY_PLACEMENT_SCHEMA):
                args=fixture(turn,schema);original=deepcopy(args[-1]);self.ns['validate_public'](args[2],placement_group=True)
                result=self.verify(*args)
                self.assertEqual(result['turn'],turn);self.assertEqual(result['checkpoint'],REFERENCE)
                self.assertFalse(result['native_save_in_this_group']);self.assertEqual(args[-1],original)
        c,e,v,_=fixture(turn=1);c['network_checkpoint']=None;e.pop('official_lan_checkpoint_reloaded')
        result=self.ns['review_placement_input'](c,e,v)
        self.assertEqual(result,dict(official_bundle=ORIGIN,checkpoint=None,turn=1))
        c['checkpoint_on_close']=True
        with self.assertRaises(ValueError):self.ns['review_placement_input'](c,e,v)

    def test_checkpoint_reference_turn_public_state_flags_and_event_order_are_not_substituted(self):
        for mode in ('path','hash','closure_turn','boolean_turn','saved_turn','marker_turn','marker_reference',
                     'observation','action','transition','false_flag','early_marker','late_marker','save_on_close'):
            c,e,v,m=fixture(saved_schema=contract.CAPABILITY_PRODUCTION_QUEUE_SCHEMA)
            marker=e['official_lan_checkpoint_reloaded']
            if mode=='path':c['network_checkpoint']['path']='work/other.json'
            elif mode=='hash':c['network_checkpoint']['sha256']='c'*64
            elif mode=='closure_turn':c['initial_turn']=1
            elif mode=='boolean_turn':c['initial_turn']=True
            elif mode=='saved_turn':m['observed_game_turn']=1
            elif mode=='marker_turn':marker['turn']=1
            elif mode=='marker_reference':marker['checkpoint'][0]='work/other.json'
            elif mode=='observation':m['observation']['turn']=1
            elif mode=='action':m['decisions']['candidates'][0]['action']['unexpected']=True
            elif mode=='transition':marker['catalogue_transition']=None
            elif mode=='false_flag':marker['saved_decision_fields_equal']=False
            elif mode=='early_marker':e['_event_lines']['official_lan_checkpoint_reloaded']=9
            elif mode=='late_marker':e['_event_lines']['official_lan_checkpoint_reloaded']=25
            else:c['checkpoint_on_close']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.verify(c,e,v,m)

    def test_retained_checkpoint_input_and_120_second_proof_remain_accepted_read_only(self):
        review_path=ROOT/'work/xp1-turn-integration/native-session15/native-review.json'
        if not review_path.exists():self.skipTest('Private native witness absent')
        retained=json.loads(review_path.read_bytes());row=retained['runs'][1];run=Path(row['run'])
        closure=json.loads((run/'closure.json').read_bytes());report=json.loads((run/'supervisor.json').read_bytes())
        initial=json.loads((run/'public-0000.json').read_bytes())
        self.assertEqual(self.ns['review_lifetime_seconds'](closure,report),120)
        pins=dict(closure['pins']);import hashlib
        pins[str((run/'closure.json').resolve())]=hashlib.sha256((run/'closure.json').read_bytes()).hexdigest()
        self.ns['saved_load_validate_supervision'](report,pins,lifetime_seconds=120)
        _,events=self.ns['saved_load_events'](run/'events.jsonl',allow_multiple_commands=True,
            allow_turn_updates=True,allow_world_input=True,allow_unit_orders=True,allow_checkpoint=True)
        # Real hash/ancestry/component validation, not a replacement manifest.
        result=self.ns['review_placement_input'](closure,events,initial)
        self.assertEqual(result['checkpoint'],closure['network_checkpoint'])
        self.assertEqual(result['turn'],initial['observation']['turn'])


if __name__=='__main__':unittest.main()

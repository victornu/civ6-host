"""Placement review/acceptance fixtures. No engine, legality or completion proof."""
import ast
import copy
import json
from pathlib import Path
import unittest

from civ6_host.contracts import placement as placed
from civ6_host.runtime.native import native_production_placement as native
from civ6_host.runtime.native.native_saved_placement import action as public_action
from civ6_host.runtime.native.native_session_resume import restore_placement_choice
from civ6_host.runtime.native import native_district_completion as districts, native_wonder_completion as wonders
from civ6_host.contracts.network_turn import CAPABILITY_PLACEMENT_SCHEMA
import test_xp1_session_queue_review as queue_tests
import test_xp1_session_turn_review as turn_tests

REPO=Path(__file__).resolve().parents[1]
PLACEMENT_SOURCE=('fixture-placement','placement-source')


def functions():
    ns=queue_tests.functions();ns.update(placed=placed,parse_effect=native.parse_effect,public_action=public_action,
        restore_placement_choice=restore_placement_choice,PLACEMENT_SOURCE=PLACEMENT_SOURCE)
    for filename,names in {
        'qualify_xp1_configuration.py':{'saved_load_validate_placement'},
        'review_xp1_session.py':{'validate_placement_public_transition','validate_placement_group'},
        'accept_session.py':{'exercise_placement_group'},
    }.items():
        path=REPO/'tools'/filename
        nodes=[n for n in ast.parse(path.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in names]
        if len(nodes)!=len(names):raise AssertionError('Missing shared placement function')
        if filename=='qualify_xp1_configuration.py':
            class FixtureImports(ast.NodeTransformer):
                def visit_Import(self,node):return ast.copy_location(ast.Pass(),node)
                def visit_ImportFrom(self,node):return ast.copy_location(ast.Pass(),node)
            nodes=[FixtureImports().visit(n) for n in nodes]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),ns)
    return ns


class PlacementFixture(queue_tests.QueueFixture):
    def __init__(self,ns,*,category='district',available=True):
        self.category=category;self.available=available;self.tracked=[];self.placed_choice=None
        self.current=dict(city_id=23,owner_id=0,queue_size=1,kind='U',item_index=0,current_production_hash=100,formation=0,progress=0)
        super().__init__(ns,city=True)

    def choice(self,mode):
        name='DISTRICT_HOLY_SITE' if self.category=='district' else 'BUILDING_ORACLE'
        coords='4:0:1' if mode=='place' else '-1:-1:-1'
        raw=('placement-v1|0|23|1|catalog|1|7|12|90|13|14|16|17|18|31|4|3|1|'
             +self.category+':'+name+':1:201:'+mode+':'+coords).encode()
        return native.choose(native.parse_catalog(raw,0,23,1),self.category,1,4 if mode=='place' else -1)

    def make_view(self,applied):
        view=super().make_view(applied);c=self.current
        view['decisions']['schema']=CAPABILITY_PLACEMENT_SCHEMA
        view['decisions']['choice_state']=dict(research=dict(research=None,civic=None),production=[dict(
            city_id=c['city_id'],queue_size=c['queue_size'],kind=c['kind'],item_index=c['item_index'],
            hash=c['current_production_hash'],formation=c['formation'])])
        offers=[]
        if self.available and (not self.tracked or self.current['kind']=='U'):
            choice=self.choice('resume' if self.tracked else 'place');offers=[public_action(23,choice,player_id=0)]
        view['decisions'].update(placements=copy.deepcopy(self.tracked),placement_offers=offers,placement_observation_scope='host_tracked')
        ordinary=dict(kind='production',city_id=23,category='unit',index=0,hash=100,item_type='UNIT_SCOUT')
        actions=[*offers,*([ordinary] if c['kind']!='U' else [])]
        view['decisions']['candidates']=[dict(candidate_id='placement-'+str(i),action=a) for i,a in enumerate(actions)]
        return view

    def progress_event(self):
        choice=self.placed_choice;s=self.tracked[0]
        common=['0','23','1','1','201','4','0','1']
        if self.category=='district':
            raw='|'.join(['district-completion-v1',*common,'45','1','0','23','0','0']).encode()
            nr=districts.parse_readback(raw,choice,1)
        else:
            raw='|'.join(['wonder-completion-v1',*common,'0','23','0','1','0']).encode()
            nr=wonders.parse_readback(raw,choice,1)
        return dict(stage='official_explicit_placement_progress',summary=copy.deepcopy(s),native_receipt=nr,
                    native_gameplay_mutated=False,source_proof_sha256=PLACEMENT_SOURCE[1])

    def choose(self,kind,**match):
        prior=copy.deepcopy(self.view);old=copy.deepcopy(self.current)
        action=next(r['action'] for r in prior['decisions']['candidates'] if r['action']['kind']==kind
                    and all(r['action'].get(k)==v for k,v in match.items()))
        before=copy.deepcopy(self.ob);choice=None;events=[]
        if kind=='production':
            self.current.update(kind='U',item_index=0,current_production_hash=100,formation=0,progress=0)
            effect=dict(fixture_native_current_production=True);phase=dict(explicit_choice_applied=True,kind='production')
        else:
            resume=kind=='production_resume';choice=self.choice('resume' if resume else 'place')
            if resume:events.append(self.progress_event())
            self.current.update(kind='D' if self.category=='district' else 'B',item_index=1,current_production_hash=201,
                                formation=None,progress=7 if resume else 0)
            if not resume:
                self.placed_choice=copy.deepcopy(choice)
                self.tracked=[dict(city_id=23,category=self.category,index=1,item_type=choice['item_type'],plot_id=4,x=0,y=1,
                                   placement_turn=1,observed_turn=1,exists=True,complete=False)]
            payload=['placement-effect-v1',*[choice[k] for k in ('player_id','city_id','current_game_turn','kind','index','hash','mode','plot_id','x','y')],
                     1,-1 if resume else 1,-1 if resume else 0]
            receipt=dict(action=copy.deepcopy(action),choice=json.loads(json.dumps(choice)),
                effect=native.parse_effect('|'.join(map(str,payload)).encode(),choice),
                observation_before=before,observation_after=copy.deepcopy(self.ob),automatic_choices_applied=False)
            archive='11223344';events.extend([turn_tests.TurnReceipts.queued(archive),*turn_tests.TurnReceipts.delivered(archive)])
            events.append(dict(stage='official_explicit_production_effect',choice=receipt['choice'],production_before=old,
                               production=copy.deepcopy(self.current),item_completed=False))
            if resume:
                receipt.update(production_before=old,production_after=copy.deepcopy(self.current),progress_before=7,progress_after=7,
                               placements_before=copy.deepcopy(self.tracked),placements_after=copy.deepcopy(self.tracked))
                events.append(self.progress_event())
            events.append(dict(stage='official_explicit_production_resume_effect' if resume else 'official_explicit_placement_effect',**copy.deepcopy(receipt)))
            effect=dict(status='completed',refusal_code=None,observation=copy.deepcopy(self.ob),receipt=receipt)
        previous=dict(episode_id=prior['episode_id'],game_generation=prior['game_generation'],sequence=self.internal,
                      publication_count=self.publications,observation=before)
        self.sequence+=1;self.internal+=1;self.publications+=1
        result=dict(action=copy.deepcopy(action),effect=effect,observation_before=before,observation_after=copy.deepcopy(self.ob),
            jobs_before={'fixture':1},jobs_after={'fixture':1},episode_id=prior['episode_id'],game_generation=prior['game_generation'],
            sequence=self.internal,publication_count=self.publications,unit_source={'source_sha256':'unit-source'},
            public_runtime_admitted=False,complete_action_space=False,game_update_called=False,same_save_official_transition_compared=False)
        interval=dict(begin={'event':{'protocol_sequence':self.sequence}},returned={'event':{'protocol_sequence':self.sequence}},commands=events,jobs=[])
        self.ns['saved_load_validate_transition'](result,interval,previous,update=False)
        if kind!='production':phase=self.ns['saved_load_validate_placement'](result,interval,result['jobs_before'])
        self.view=self.make_view(action);self.ns['validate_placement_public_transition'](result,prior,self.view,phase)
        command=self.ns['review_command_result'](result,phase)
        self.commands.append(command);self.native.append(result);self.intervals.append(interval)
        self.ledgers.append(dict(protocol_sequence=self.sequence,action=copy.deepcopy(action),ledger=dict(phase_receipt=phase),
                                command_result=command,turn_before=1,turn_after=1));self.views.append(copy.deepcopy(self.view))
        return copy.deepcopy(command)

    def group_rows(self):
        rows=super().group_rows()
        for v,s in zip(self.views,rows[0]['public']):
            for k in ('choice_state','placements','placement_offers','placement_observation_scope'):s[k]=copy.deepcopy(v['decisions'][k])
        for k in ('choice_state','placements','placement_offers','placement_observation_scope'):rows[1]['public'][0][k]=copy.deepcopy(self.initial['decisions'][k])
        return rows


class PlacementReview(unittest.TestCase):
    def setUp(self):self.ns=functions()

    def group(self,category='district'):
        f=PlacementFixture(self.ns,category=category)
        group=self.ns['exercise_placement_group'](lambda:f.view,f.choose,category=category)
        return f,dict(status='native_capability_placement_group_reset_verified',placement_group=group)

    def test_separate_district_and_wonder_fixtures_follow_three_actual_shapes(self):
        for category in ('district','building'):
            f,a=self.group(category);summary=self.ns['validate_placement_group'](a,f.group_rows())
            self.assertEqual(summary['category'],category);self.assertEqual(summary['command_count'],3)
            self.assertEqual(summary['retained_progress'],7);self.assertFalse(summary['completion_qualified'])
            self.assertNotIn('status',f.native[1]['effect'])

    def test_no_empty_catalogue_fallback_or_unoffered_replacement(self):
        f=PlacementFixture(self.ns,available=False)
        with self.assertRaisesRegex(RuntimeError,'no offered'):self.ns['exercise_placement_group'](lambda:f.view,f.choose,category='district')
        self.assertFalse(f.commands)

    def test_checkpoint_preparation_defers_resumption_without_losing_offer(self):
        f=PlacementFixture(self.ns)
        group=self.ns['exercise_placement_group'](lambda:f.view,f.choose,category='district',defer_resume=True)
        self.assertEqual([s['action']['kind'] for s in group['steps']],['production_placement','production'])
        self.assertTrue(any(a['kind']=='production_resume' for a in f.view['decisions']['placement_offers']))
        self.assertEqual(len(f.commands),2)

    def test_native_effect_coordinates_source_and_fifo_tampering_refused(self):
        f,_=self.group();r0,e0=f.native[0],f.intervals[0]
        for mode in ('plot','completion','archive','missing','refusal'):
            r,e=copy.deepcopy(r0),copy.deepcopy(e0)
            if mode=='plot':r['effect']['receipt']['effect']['plot_owner']=1
            elif mode=='completion':r['effect']['receipt']['effect']['item_completed']=True
            elif mode=='archive':e['commands'][1]['archive_hex']='00'
            elif mode=='missing':e['commands'].pop(3)
            else:r['effect']['refusal_code']='fake_success'
            if mode in ('plot','completion'):e['commands'][-1]=dict(stage='official_explicit_placement_effect',**r['effect']['receipt'])
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['saved_load_validate_placement'](r,e,r['jobs_before'])

    def test_resume_requires_real_before_after_progress_reads_and_unchanged_retention(self):
        f,_=self.group();r0,e0=f.native[-1],f.intervals[-1]
        for mode in ('value','source','summary','read','choice','production'):
            r,e=copy.deepcopy(r0),copy.deepcopy(e0)
            if mode=='value':r['effect']['receipt']['progress_after']=8
            elif mode=='source':e['commands'][0]['source_proof_sha256']='base-not-selected'
            elif mode=='summary':e['commands'][0]['summary']['complete']=True
            elif mode=='read':e['commands'].pop(0)
            elif mode=='choice':r['effect']['receipt']['choice']['x']=0
            else:r['effect']['receipt']['production_after']['progress']=99
            if mode in ('value','choice','production'):e['commands'][-1]=dict(stage='official_explicit_production_resume_effect',**r['effect']['receipt'])
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['saved_load_validate_placement'](r,e,r['jobs_before'])

    def test_public_tracking_scope_identity_and_unoffered_action_cannot_drift(self):
        f,_=self.group();r=f.native[0];phase=f.ledgers[0]['ledger']['phase_receipt']
        for mode in ('scope','plot','offer','production'):
            a,b=copy.deepcopy(f.views[0]),copy.deepcopy(f.views[1])
            if mode=='scope':b['decisions']['placement_observation_scope']='complete'
            elif mode=='plot':b['decisions']['placements'][0]['plot_id']=5
            elif mode=='offer':a['decisions']['placement_offers']=[]
            else:b['decisions']['choice_state']['production'][0]['hash']=100
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['validate_placement_public_transition'](r,a,b,phase)

    def test_group_cannot_claim_other_category_completion_or_changed_reset(self):
        f,original=self.group();original_rows=f.group_rows()
        for mode in ('category','completion','reset','action','poll'):
            a,rows=copy.deepcopy(original),copy.deepcopy(original_rows)
            if mode=='category':a['placement_group']['category']='building'
            elif mode=='completion':a['placement_group']['completion_witnessed']=True
            elif mode=='reset':rows[1]['public'][0]['placements']=None
            elif mode=='action':a['placement_group']['steps'][2]['action']['hash']=999
            else:rows[0]['ledger']['updates']=[dict(fixture=True)]
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['validate_placement_group'](a,rows)


if __name__=='__main__':unittest.main()

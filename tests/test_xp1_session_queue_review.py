"""Queue acceptance/review fixtures; no native availability or simulation claim."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from civ6_host.contracts import production_queue as queues
from civ6_host.contracts.network_turn import CAPABILITY_PRODUCTION_QUEUE_SCHEMA
import test_xp1_session_world_review as world_tests
import test_xp1_session_turn_review as turn_tests

REPO=Path(__file__).resolve().parents[1]
QUEUE_SOURCE=('fixture-source','queue-source')


def functions():
    ns=world_tests.functions();ns.update(queues=queues,QUEUE_SOURCE=QUEUE_SOURCE)
    for name,names in {
        'qualify_xp1_configuration.py':{'saved_load_validate_production_queue'},
        'review_xp1_session.py':{'validate_queue_public_transition','validate_production_queue_group','review_command_result'},
        'accept_session.py':{'exercise_production_queue_group'},
    }.items():
        path=REPO/'tools'/name
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name in names]
        if len(nodes)!=len(names):raise AssertionError('Missing shared queue function')
        if name=='qualify_xp1_configuration.py':
            # Namespace dependencies also cover nested engine-selected imports.
            class FixtureImports(ast.NodeTransformer):
                def visit_Import(self,node):return ast.copy_location(ast.Pass(),node)
                def visit_ImportFrom(self,node):return ast.copy_location(ast.Pass(),node)
            nodes=[FixtureImports().visit(n) for n in nodes]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),ns)
    return ns


class QueueFixture(world_tests.WorldFixture):
    def __init__(self,ns,*,city=False,two_items=True):
        self.city=city;self.entries=[];self.two_items=two_items
        super().__init__(ns)

    def make_view(self,applied):
        if self.city:
            self.ob['cities']=[dict(id=23,owner=0,x=1,y=0)]
            self.ob['units']=[u for u in self.ob['units'] if u['id']!=18]
            self.queues.pop(18,None)
        view=super().make_view(applied);offers=[];state=[]
        if self.city:
            for index in range(2 if self.two_items else 1):
                offers.append(dict(kind='queue_append',city_id=23,category='unit',index=index,hash=100+index,
                    item_type=('UNIT_SCOUT','UNIT_WARRIOR')[index],mode='replace_tail' if len(self.entries)==8 else 'append'))
            offers.extend(dict(kind='queue_remove',city_id=23,position=i) for i in range(len(self.entries)))
            offers.extend(dict(kind='queue_swap',city_id=23,source_position=i,destination_position=j)
                          for i in range(len(self.entries)) for j in range(len(self.entries)) if i!=j)
            state=[dict(schema=queues.PUBLIC_SCHEMA,player_id=0,turn=1,city_id=23,enabled=True,
                        entries=copy.deepcopy(self.entries),offers=offers)]
            queues.validate_all(state,0,1)
        view['decisions'].update(schema=CAPABILITY_PRODUCTION_QUEUE_SCHEMA,production_queues=state,
                                unit_orders=dict(player_id=0,turn=1,units=[],offers=[]))
        if self.city:
            view['decisions']['candidates']=[r for r in view['decisions']['candidates'] if r['action']['kind']!='found_city']
        view['decisions']['candidates'].extend(dict(candidate_id='queue-'+str(i),action=a) for i,a in enumerate(offers))
        return view

    def choose(self,kind,**match):
        prior=copy.deepcopy(self.view);before=copy.deepcopy(self.ob)
        action=next(r['action'] for r in prior['decisions']['candidates'] if r['action']['kind']==kind
                    and all(r['action'].get(k)==v for k,v in match.items()))
        old=copy.deepcopy(prior['decisions']['production_queues'])
        if kind=='found_city':self.city=True
        elif kind=='queue_append':
            item=dict(position=7 if len(self.entries)==8 else len(self.entries),category=action['category'],
                index=action['index'],hash=action['hash'],formation=0,formation_display=dict(is_corps=False,is_army=False))
            if action['mode']=='replace_tail':self.entries[-1]=item
            else:self.entries.append(item)
        elif kind=='queue_remove':self.entries.pop(action['position'])
        elif kind=='queue_swap':
            a,b=action['source_position'],action['destination_position'];self.entries[a],self.entries[b]=self.entries[b],self.entries[a]
        else:raise AssertionError('Unexpected fixture command')
        for i,r in enumerate(self.entries):r['position']=i
        previous=dict(episode_id=world_tests.EPISODE,game_generation='native-'+world_tests.EPISODE,
            sequence=self.internal,publication_count=self.publications,observation=before)
        self.sequence+=1;self.internal+=1;self.publications+=1;self.view=self.make_view(action)
        command=dict(status='completed',reason=None,requested_action=copy.deepcopy(action))
        if kind=='found_city':
            phase={'foundation_fixture':True};result=None;interval=None
        else:
            receipt=dict(action=copy.deepcopy(action),queue_before=old[0],queue_after=copy.deepcopy(self.view['decisions']['production_queues'][0]),
                native_archive_delivered=True,automatic_choices_applied=False,source_proof_sha256=QUEUE_SOURCE[1],
                public_source_proof_sha256=QUEUE_SOURCE[1],tutorial_gate_qualified=True,strategic_training_ready=False)
            result=dict(action=copy.deepcopy(action),effect=dict(status='completed',refusal_code=None,
                observation=copy.deepcopy(self.ob),receipt=receipt),observation_before=before,observation_after=copy.deepcopy(self.ob),
                jobs_before={'fixture':1},jobs_after={'fixture':1},episode_id=world_tests.EPISODE,
                game_generation='native-'+world_tests.EPISODE,sequence=self.internal,publication_count=self.publications,
                unit_source={'source_sha256':'unit-source'},public_runtime_admitted=False,complete_action_space=False,
                game_update_called=False,same_save_official_transition_compared=False)
            archive='11223344';events=[turn_tests.TurnReceipts.queued(archive),*turn_tests.TurnReceipts.delivered(archive),
                dict(stage='official_explicit_production_queue_effect',**copy.deepcopy(receipt))]
            interval=dict(begin={'event':{'protocol_sequence':self.sequence}},returned={'event':{'protocol_sequence':self.sequence}},
                          commands=events,jobs=[])
            self.ns['saved_load_validate_transition'](result,interval,previous,update=False)
            phase=self.ns['saved_load_validate_production_queue'](result,interval,result['jobs_before'])
            self.ns['validate_queue_public_transition'](result,prior,self.view)
        self.commands.append(command);self.native.append(result);self.intervals.append(interval)
        self.ledgers.append(dict(protocol_sequence=self.sequence,action=copy.deepcopy(action),ledger=dict(phase_receipt=phase),
            command_result=command,turn_before=1,turn_after=1))
        self.views.append(copy.deepcopy(self.view));return copy.deepcopy(command)

    def group_rows(self):
        rows=super().group_rows()
        for v,s in zip(self.views,rows[0]['public']):
            for k in ('production_queues','unit_orders','candidates'):s[k]=copy.deepcopy(v['decisions'][k])
        for k in ('production_queues','unit_orders','candidates'):rows[1]['public'][0][k]=copy.deepcopy(self.initial['decisions'][k])
        return rows


class QueueReview(unittest.TestCase):
    def setUp(self):self.ns=functions()

    def group(self,**kwargs):
        f=QueueFixture(self.ns,**kwargs)
        group=self.ns['exercise_production_queue_group'](lambda:f.view,f.choose)
        acceptance=dict(status='native_capability_production_queue_group_reset_verified',production_queue_group=group)
        return f,acceptance

    def validate(self,result,interval):
        return self.ns['saved_load_validate_production_queue'](result,interval,result['jobs_before'])

    def test_complete_offered_permutations_with_and_without_foundation(self):
        for city in (False,True):
            f,a=self.group(city=city);summary=self.ns['validate_production_queue_group'](a,f.group_rows())
            self.assertEqual(summary['command_count'],11+int(not city));self.assertEqual(summary['queue_edit_count'],11)
            self.assertTrue(summary['eighth_slot_replaced']);self.assertFalse(summary['complete_append_catalogue'])
            self.assertEqual([len(r['queue_after']['entries']) for r in a['production_queue_group']['steps']],list(range(1,9))+[8,8,7])

    def test_mixed_foundation_and_queue_preserve_their_distinct_native_effect_shapes(self):
        f,a=self.group();foundation=a['production_queue_group']['foundation']
        result=dict(action=foundation['action'],effect=dict(city_id=23,consumed_unit_id=18,player_id=0,population=1,x=1,y=0))
        actual=self.ns['review_command_result'](result,dict(explicit_unit_command_applied=True))
        self.assertEqual(actual,foundation['command_result'])
        self.assertNotIn('status',result['effect'])
        with self.assertRaisesRegex(ValueError,'authenticated native effect'):
            self.ns['review_command_result'](result,{})
        for row,native in zip(f.ledgers[1:],f.native[1:]):
            actual=self.ns['review_command_result'](native,row['ledger']['phase_receipt'])
            self.assertEqual(actual,row['command_result'])
        with self.assertRaises(KeyError):
            self.ns['review_command_result'](dict(action=dict(kind='queue_remove'),effect={}),{})

    def test_no_missing_offer_or_identical_swap_is_invented(self):
        f=QueueFixture(self.ns,city=True,two_items=False)
        with self.assertRaisesRegex(RuntimeError,'distinct repeatable'):
            self.ns['exercise_production_queue_group'](lambda:f.view,f.choose)
        self.assertEqual(len(f.commands),1)

    def test_research_civic_and_production_use_the_authenticated_choice_family(self):
        for kind in ('research','civic','production'):
            action=dict(kind=kind,index=4,hash=123)
            result=dict(action=action,effect=dict(confirmed=True))
            phase=dict(explicit_choice_applied=True,kind=kind)
            with self.subTest(kind=kind):
                self.assertEqual(self.ns['review_command_result'](result,phase),
                    dict(status='completed',reason=None,requested_action=action))
                for wrong in ({},dict(phase,kind='other'),
                              dict(phase,explicit_choice_applied=False),
                              dict(phase,explicit_choice_applied=1)):
                    with self.assertRaisesRegex(ValueError,'authenticated native effect'):
                        self.ns['review_command_result'](result,wrong)

    def test_receipt_source_gate_shape_and_foreign_city_tampering(self):
        f,_=self.group(city=True);source,events=f.native[0],f.intervals[0]
        for field,value in [('source_proof_sha256','wrong'),('public_source_proof_sha256','wrong'),
                            ('tutorial_gate_qualified',False),('native_archive_delivered',False),('automatic_choices_applied',True)]:
            r,e=copy.deepcopy(source),copy.deepcopy(events);r['effect']['receipt'][field]=value
            e['commands'][-1]=dict(stage='official_explicit_production_queue_effect',**r['effect']['receipt'])
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(r,e)
        for key in ('queue_before','queue_after'):
            r,e=copy.deepcopy(source),copy.deepcopy(events);r['effect']['receipt'][key]['city_id']=24
            e['commands'][-1]=dict(stage='official_explicit_production_queue_effect',**r['effect']['receipt'])
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(r,e)
        r=copy.deepcopy(source);r['effect']['refusal_code']='not_completed'
        with self.assertRaises(ValueError):self.validate(r,events)

    def test_fifo_missing_reordered_duplicate_and_false_effect_are_refused(self):
        f,_=self.group(city=True);source,events=f.native[0],f.intervals[0]
        for mode in ('drop','reorder','duplicate','bytes','entry'):
            r,e=copy.deepcopy(source),copy.deepcopy(events)
            if mode=='drop':e['commands'].pop(1)
            elif mode=='reorder':e['commands'].insert(0,e['commands'].pop())
            elif mode=='duplicate':e['commands'].append(copy.deepcopy(e['commands'][-1]))
            elif mode=='bytes':e['commands'][1]['archive_hex']='00'
            else:
                r['effect']['receipt']['queue_after']['entries'][0]['hash']=999
                e['commands'][-1]=dict(stage='official_explicit_production_queue_effect',**r['effect']['receipt'])
            with self.subTest(mode=mode),self.assertRaises((ValueError,RuntimeError)):self.validate(r,e)

    def test_public_order_and_offers_must_match_native_readback(self):
        f,_=self.group(city=True);r=f.native[0];before=f.views[0];after=f.views[1]
        for mode in ('queue','offer','selection','roster'):
            b,a=copy.deepcopy(before),copy.deepcopy(after)
            if mode=='queue':a['decisions']['production_queues'][0]['entries'][0]['hash']=999
            elif mode=='offer':b['decisions']['candidates']=[]
            elif mode=='selection':a['decisions']['world_input']['selected_unit_id']=17
            else:a['decisions']['production_queues'].append(dict(city_id=999,entries=[]))
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['validate_queue_public_transition'](r,b,a)

    def test_group_rejects_omitted_command_false_tail_and_reset_drift(self):
        f,original=self.group();original_rows=f.group_rows()
        for mode in ('omit','tail','reset','poll','unqualified'):
            a,rows=copy.deepcopy(original),copy.deepcopy(original_rows)
            if mode=='omit':a['production_queue_group']['steps'].pop()
            elif mode=='tail':a['production_queue_group']['replace_tail_sequence']=1
            elif mode=='reset':rows[1]['public'][0]['production_queues']=None
            elif mode=='poll':a['production_queue_group']['poll_calls']=1
            else:a['production_queue_group']['complete_append_catalogue_claimed']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['validate_production_queue_group'](a,rows)

    def test_exact_single_publication_required(self):
        f,_=self.group(city=True);result=copy.deepcopy(f.native[0]);interval=f.intervals[0]
        previous=dict(episode_id=result['episode_id'],game_generation=result['game_generation'],sequence=0,
                      publication_count=0,observation=result['observation_before'])
        for count in (0,2):
            result['publication_count']=count
            with self.assertRaisesRegex(ValueError,'single native delivery'):
                self.ns['saved_load_validate_transition'](result,interval,previous,update=False)

    def test_parser_preserves_strict_default_and_explicit_queue_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events.jsonl'
            rows=[dict(stage='xp1_saved_player_view_returned'),
                  dict(stage='before_xp1_saved_unit_commands',protocol_sequence=1),
                  dict(stage='official_explicit_production_queue_effect',fixture=True),
                  dict(stage='xp1_saved_unit_commands_returned',protocol_sequence=1)]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            kw=dict(require_interval='unit_commands',allow_turn_updates=True,command_sequence=1)
            self.assertEqual(self.ns['saved_load_events'](path,**kw)[1]['unit_commands_job_interval']['commands'],[])
            e=self.ns['saved_load_events'](path,allow_production_queue=True,**kw)[1]
            self.assertEqual(e['unit_commands_job_interval']['commands'],[rows[2]])


if __name__=='__main__':unittest.main()

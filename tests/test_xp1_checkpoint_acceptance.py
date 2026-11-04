"""Checkpoint reviewer fixtures: no DLL, Save, Load or compatibility admission."""
import ast
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from civ6_host.runtime.native.native_session_resume import semantic_decisions
import test_xp1_session_order_review as order_tests

REPO=Path(__file__).resolve().parents[1]
REFERENCE=dict(path='work/fixture/checkpoint.json',sha256='a'*64,bytes=123)


def functions():
    ns=order_tests.functions()
    ns.update(XP1_LAN_PROFILE=SimpleNamespace(name='xp1-lan-official-capture-inputs'),
              semantic_decisions=semantic_decisions)
    for filename,names in {
        'qualify_xp1_configuration.py':{'saved_load_validate_checkpoint','saved_load_reconcile_later'},
        'review_xp1_session.py':{'validate_checkpoint_group'},
        'accept_session.py':{'compare_checkpoint_public','checkpoint_rest_action'},
    }.items():
        path=REPO/'tools'/filename
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body
               if isinstance(n,ast.FunctionDef) and n.name in names]
        if len(nodes)!=len(names):raise AssertionError('Missing shared checkpoint function')
        for n in nodes:
            if filename=='qualify_xp1_configuration.py':
                n.body=[s for s in n.body if not isinstance(s,(ast.Import,ast.ImportFrom))]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),ns)
    return ns


class SaveFixture:
    def __init__(self,ns):
        self.ns=ns
        self.control=dict(pending_count=0,sequence=3,consumed=3,notification_counter=0,
            metadata_counter=0,scope='saved owner services',actions_admitted=False,timers_admitted=False,
            candidate_command_transport_present=True,pending_command_count=0)
        self.previous=dict(episode_id='fixture',game_generation='fixture-generation',sequence=2,
                           publication_count=1,observation={'player_id':0,'turn':1})
        self.jobs={'fixture_snapshot':1}
        self.saved=dict(manifest=copy.deepcopy(REFERENCE),components={'gamecore':{},'application_configuration':{}},
            observed_game_turn=1,native_save_status=0,stream_closed=True,
            native_load_of_new_pair_validated=False,controlled_stop_required=True)
        self.result=dict(save_result=copy.deepcopy(self.saved),jobs_before=self.jobs,jobs_after=self.jobs,
            **{k:self.previous[k] for k in ('episode_id','game_generation','sequence','publication_count')},
            observation_before=self.previous['observation'],observation_after=self.previous['observation'],
            control_before=copy.deepcopy(self.control),control_after=copy.deepcopy(self.control))
        self.manifest=dict(input_profile='xp1-lan-official-capture-inputs',core_sha256=ns['XP1_CORE_SHA256'],
            observation=self.previous['observation'],components=self.saved['components'],observed_game_turn=1,
            configuration_receipt={'fixture_configuration':True},jobs_before=self.jobs,jobs_after=self.jobs,
            jobs_quiescent_unchanged=True,full_civ6save_container=False)
        self.events={
            'before_native_session_checkpoint':dict(stage='before_native_session_checkpoint',turn=1,
                configuration=self.manifest['configuration_receipt'],raw_components_only=True,strategic_training_ready=False),
            'native_session_checkpoint_finalized':dict(stage='native_session_checkpoint_finalized',**self.saved,
                strategic_training_ready=False),
            '_event_lines':dict(before_native_session_checkpoint=11,native_session_checkpoint_finalized=13)}
        self.interval=dict(begin=dict(line=10,event={'protocol_sequence':3}),
            returned=dict(line=14,event={'protocol_sequence':3}),jobs=[],commands=[],
            stdout_sha256='transcript',interval_sha256='interval',interval_bytes=100,stdout_lines=20)
        ns['network_checkpoint']=SimpleNamespace(manifest=lambda ref:self.manifest)

    def validate(self):
        return self.ns['saved_load_validate_checkpoint'](self.result,self.interval,self.jobs,self.events,self.previous)


def checkpoint_group(ns,release='UNITCOMMAND_CANCEL'):
    f=order_tests.OrderFixture(ns,release=release,fortify_only=True)
    action=ns['checkpoint_rest_action'](f.view)
    f.choose('unit_order',**{k:v for k,v in action.items() if k!='kind'})
    rested=copy.deepcopy(f.order_states)
    f.choose('world_select_unit',unit_id=action['unit_id'])
    saved=copy.deepcopy(f.view)
    second=order_tests.OrderFixture(ns,release=release,fortify_only=True)
    second.order_states=rested;second.selected=action['unit_id']
    second.view=second.make_view(None);second.initial=copy.deepcopy(second.view);second.views=[copy.deepcopy(second.view)]
    second.choose('unit_order',item_type=release,unit_id=action['unit_id'])
    second.choose('world_deselect_unit')
    # Same actual fixture catalogue, with new public protocol identities.
    rows=[]
    for index,(fixture,views) in enumerate(((f,f.views),(second,second.views),(None,[saved]))):
        public=[]
        for i,v in enumerate(views):
            v=copy.deepcopy(v)
            if fixture is None:v['sequence']=0;v['applied_action']=None
            v['episode_id']='fixture-episode-'+str(index)
            v['game_generation']='fixture-generation-'+str(index)
            d=v['decisions'];d.update(episode_id=v['episode_id'],game_generation=v['game_generation'],
                                     sequence=v['sequence'],decision_id='fixture-'+str(i))
            public.append(dict(episode_id=v['episode_id'],generation=v['game_generation'],sequence=v['sequence'],
                turn=1,observation=v['observation'],world_input=d['world_input'],decisions=d))
        ledger=dict(commands=copy.deepcopy(fixture.ledgers) if fixture else [],updates=[])
        rows.append(dict(run='fixture-run-'+str(index),public=public,ledger=ledger,
            checkpoint_on_close=index==0,checkpoint_input=None if index==0 else
            {k:REFERENCE[k] for k in ('path','sha256')},checkpoint_reloaded=None if index==0 else
            dict(checkpoint=[REFERENCE['path'],REFERENCE['sha256']],turn=1,public_observation_equal=True,
                 public_decisions_equal=True,saved_decision_fields_equal=True,catalogue_transition=None,
                 identity_rebound=True,complete_state_compared=False,strategic_training_ready=False)))
    rows[0]['ledger']['checkpoint']=dict(phase_receipt=dict(manifest_reference=copy.deepcopy(REFERENCE)))
    group=dict(unit_id=action['unit_id'],rest_action=action,rest_sequence=1,selection_sequence=2,
        release_action=second.native[0]['action'],release_sequence=1,deselection_sequence=2,
        checkpoint=copy.deepcopy(REFERENCE),save_count=1,poll_calls=0,
        resumed_episode=rows[1]['public'][0]['episode_id'],reset_episode=rows[2]['public'][0]['episode_id'],
        turn=1,complete_hidden_state_compared=False)
    return dict(checkpoint_cycle=group,checkpoints=[copy.deepcopy(REFERENCE)],commands=f.commands+second.commands),rows


class CheckpointReview(unittest.TestCase):
    def setUp(self):self.ns=functions()

    def test_checkpoint_outer_interval_covers_configuration_jobs_and_stream_close(self):
        rows=[dict(stage='xp1_saved_player_view_returned'),
            dict(stage='before_xp1_saved_checkpoint',protocol_sequence=3),
            dict(stage='fixture_configuration_job'),dict(stage='before_native_session_checkpoint'),
            dict(stage='fixture_save_job'),dict(stage='native_session_checkpoint_finalized'),
            dict(stage='xp1_saved_checkpoint_returned',protocol_sequence=3)]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.jsonl'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            parse=self.ns['saved_load_events']
            with self.assertRaisesRegex(ValueError,'Unknown saved native interval'):
                parse(path,require_interval='checkpoint')
            e=parse(path,allow_checkpoint=True,require_interval='checkpoint')[1]
            self.assertEqual(e['checkpoint_job_interval']['jobs'],[rows[2],rows[4]])
            for bad in (rows[:-1],rows[:3]+[dict(stage='before_xp1_saved_loaded_close')]+rows[3:],
                        rows[:3]+[dict(stage='before_xp1_saved_unit_commands',protocol_sequence=4)]+rows[3:]):
                path.write_text(''.join(json.dumps(r)+'\n' for r in bad),encoding='utf-8')
                with self.assertRaises(ValueError):parse(path,allow_checkpoint=True,allow_turn_updates=True)

    def test_save_does_not_advance_continuation_or_publication(self):
        f=SaveFixture(self.ns);receipt=f.validate()
        self.assertTrue(receipt['continuation_not_advanced']);self.assertFalse(receipt['native_load_of_pair_claimed'])
        self.ns['saved_load_validate_supervision']=lambda *a,**kw:None
        prior=dict(ledger_provenance_authenticated=True,stdout_sha256='transcript',last_line=8,final_jobs=f.jobs)
        f.events['checkpoint_job_interval']=f.interval
        ledger=self.ns['saved_load_reconcile_later']({}, {}, {},f.result,f.events,prior,
            phase='checkpoint',lifetime_seconds=120,previous_transition=f.previous)
        self.assertEqual(ledger['continuation'],dict(f.previous,protocol_sequence=3))
        self.assertEqual(ledger['final_jobs'],f.jobs)

    def test_save_rejects_sequence_state_control_jobs_and_unclosed_stream(self):
        for key,value in [('sequence',3),('publication_count',2),('game_generation','other'),
                          ('observation_after',{'turn':2}),('control_after',{}),('jobs_after',{}),
                          ('control_before',None)]:
            with self.subTest(key=key):
                f=SaveFixture(self.ns);f.result[key]=value
                with self.assertRaises(ValueError):f.validate()
        f=SaveFixture(self.ns);f.result['save_result']['stream_closed']=False
        f.events['native_session_checkpoint_finalized']['stream_closed']=False
        with self.assertRaises(ValueError):f.validate()

    def test_save_exact_profile_component_configuration_and_markers_are_joined(self):
        for key,value in [('input_profile','xp1-lan'),('core_sha256','base'),('components',{}),
                          ('configuration_receipt',{}),('jobs_before',{})]:
            with self.subTest(key=key):
                f=SaveFixture(self.ns);f.manifest[key]=value
                with self.assertRaises(ValueError):f.validate()
        f=SaveFixture(self.ns);f.events['_event_lines']['native_session_checkpoint_finalized']=15
        with self.assertRaises(ValueError):f.validate()
        f=SaveFixture(self.ns);f.interval['commands']=[{'stage':'native_command_received_in_core_queue'}]
        with self.assertRaises(ValueError):f.validate()

    def test_three_lifetimes_one_save_actual_cancel_or_wake_after_resume(self):
        for release in ('UNITCOMMAND_CANCEL','UNITCOMMAND_WAKE'):
            with self.subTest(release=release):
                a,rows=checkpoint_group(self.ns,release)
                r=self.ns['validate_checkpoint_group'](a,rows)
                self.assertEqual(r['independent_loads'],2);self.assertEqual(r['release_action']['item_type'],release)
                self.assertFalse(r['complete_hidden_state_compared'])

    def test_resume_requires_same_public_catalogue_queue_selection_and_new_identity(self):
        for field in ('observation','selected','catalogue','generation','marker','reference'):
            a,rows=checkpoint_group(self.ns);view=rows[1]['public'][0]
            if field=='observation':view['observation']['width']+=1
            elif field=='selected':view['decisions']['world_input']['selected_unit_id']=None
            elif field=='catalogue':view['decisions']['unit_orders']['units'][0]['activity_type']+=1
            elif field=='generation':view['generation']=rows[0]['public'][0]['generation']
            elif field=='marker':rows[1]['checkpoint_reloaded']['complete_state_compared']=True
            else:rows[1]['checkpoint_input']['sha256']='f'*64
            with self.subTest(field=field),self.assertRaises(ValueError):self.ns['validate_checkpoint_group'](a,rows)

    def test_group_refuses_extra_save_poll_missing_reset_and_wrong_release(self):
        for mode in ('save','poll','reset','release','turn'):
            a,rows=checkpoint_group(self.ns)
            if mode=='save':rows[1]['ledger']['checkpoint']={}
            elif mode=='poll':rows[1]['ledger']['updates']=[{}]
            elif mode=='reset':rows.pop()
            elif mode=='release':a['checkpoint_cycle']['release_action']['item_type']='UNITCOMMAND_DELETE'
            else:rows[2]['public'][0]['turn']=2
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.ns['validate_checkpoint_group'](a,rows)

    def test_acceptance_compares_public_semantics_and_only_selects_offered_rest(self):
        f=order_tests.OrderFixture(self.ns,fortify_only=True)
        action=self.ns['checkpoint_rest_action'](f.view)
        self.assertEqual(action['unit_id'],17);self.assertEqual(action['item_type'],'UNITOPERATION_FORTIFY')
        expected=copy.deepcopy(f.view);actual=copy.deepcopy(expected)
        actual.update(episode_id='other',game_generation='other-generation',sequence=0)
        for v in (expected,actual):
            v['decisions'].update(episode_id=v['episode_id'],game_generation=v['game_generation'],
                                  sequence=v['sequence'],decision_id='fixture-identity')
        self.ns['compare_checkpoint_public'](expected,actual)
        actual['decisions']['unit_orders']['units'][0]['activity_type']+=1
        with self.assertRaises(RuntimeError):self.ns['compare_checkpoint_public'](expected,actual)
        f.view['decisions']['candidates']=[r for r in f.view['decisions']['candidates']
            if r['action']['kind']!='unit_order']
        with self.assertRaises(ValueError):self.ns['checkpoint_rest_action'](f.view)


if __name__=='__main__':unittest.main()

"""Changed world-input acceptance/reviewer seams, entirely without GameCore.

The official request parser, FIFO replay, interval parser and public input
contracts run unchanged. Native observation/job contents are explicit fixtures;
these checks do not prove movement, native noninterference or runtime admission.
"""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from civ6_host.contracts import capability_world_input as world
from civ6_host.contracts.network_turn import CAPABILITY_WORLD_SCHEMA
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.native.native_world_click import parse_request_result, _SOURCE_HASH
from test_xp1_session_turn_review import functions as turn_functions, EPISODE
import test_xp1_session_turn_review as retained_turn_tests

REPO=Path(__file__).resolve().parents[1]


def functions():
    ns=turn_functions()
    ns.update(copy=copy,validate_action=world.validate_action,
              parse_request_result=parse_request_result,XP1_CORE_SHA256=XP1_CORE_SHA256,
              XP2_CORE_SHA256=XP2_CORE_SHA256)
    groups={
        'qualify_xp1_configuration.py':{'saved_load_validate_world_request','saved_load_validate_world_input'},
        'review_xp1_session.py':{'validate_world_public_transition','validate_world_group'},
        'accept_session.py':{'exercise_world_input_group'},
    }
    for name,names in groups.items():
        path=REPO/'tools'/name
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body
               if isinstance(n,ast.FunctionDef) and n.name in names]
        if len(nodes)!=len(names):raise AssertionError('Missing authored reviewer function')
        for fn in nodes:
            if name=='qualify_xp1_configuration.py':
                fn.body=[n for n in fn.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),ns)
    return ns


def observation():
    return dict(player_id=0,turn=1,width=4,height=3,cities=[],visible_enemy_units=[],
        units=[dict(id=17,type=1,x=0,y=0,owner=0,moves=2),dict(id=18,type=0,x=1,y=0,owner=0,moves=2)],
        plots=[dict(index=i,x=i%4,y=i//4,visible=True,water=False,impassable=False) for i in (0,1,4,5,8)])


class WorldFixture:
    """Public fixture client; no native calls and no inferred engine legality."""
    def __init__(self,ns,*,refuse_first=False):
        self.ns=ns;self.ob=observation();self.sequence=0;self.internal=0;self.publications=0
        self.selected=None;self.queues={17:None,18:None};self.refuse_first=refuse_first
        self.refused=False;self.views=[];self.commands=[];self.native=[];self.intervals=[];self.ledgers=[]
        self.view=self.make_view(None);self.initial=copy.deepcopy(self.view);self.views.append(copy.deepcopy(self.view))

    def make_view(self,applied):
        ob=self.ob
        state=dict(schema=world.SCHEMA,player_id=0,turn=1,width=4,height=3,
            units=[dict(unit_id=u['id'],ignore_moves=False) for u in ob['units']],
            selected_unit_id=self.selected,war_prompt=None)
        queue=dict(player_id=0,turn=1,width=4,height=3,
                   units=[dict(unit_id=uid,plot_id=p) for uid,p in sorted(self.queues.items())])
        actions=[dict(kind='found_city',unit_id=18,x=1,y=0),*world.actions(state)]
        return dict(episode_id=EPISODE,game_generation='native-'+EPISODE,sequence=self.sequence,
            observation=copy.deepcopy(ob),applied_action=copy.deepcopy(applied),
            decisions=dict(schema=CAPABILITY_WORLD_SCHEMA,world_input=state,queued_orders=queue,
                candidates=[dict(candidate_id=str(i),action=a) for i,a in enumerate(actions)]))

    def choose(self,kind,*,_expected_status='completed',**match):
        prior=copy.deepcopy(self.view)
        action=next(r['action'] for r in prior['decisions']['candidates']
                    if r['action']['kind']==kind and all(r['action'].get(k)==v for k,v in match.items()))
        before=copy.deepcopy(self.ob);request=None;archive=None;queued=None;status='completed';reason=None
        if kind=='world_select_unit':self.selected=action['unit_id']
        elif kind=='world_deselect_unit':self.selected=None
        else:
            u=next(u for u in self.ob['units'] if u['id']==action['unit_id'])
            route='noop' if (u['x'],u['y'])==(action['x'],action['y']) else 'request'
            if self.refuse_first and not self.refused and route=='request':
                route='unsupported';self.refused=True
            request=dict(status=route,player_id=0,turn=1,unit_id=u['id'],destination_plot_id=action['plot_id'],
                         width=4,height=3,source_sha256=_SOURCE_HASH,native_callback_invoked=route=='request')
            if route=='request':
                request.update(operation_name='MOVE_TO',operation=123,
                               parameters=[['x',11,action['x']],['y',12,action['y']],['modifiers',13,0]])
                archive='12340000';u.update(x=action['x'],y=action['y'],moves=1)
                self.queues[u['id']]=action['plot_id'];self.publications+=1
            elif route=='unsupported':status='refused';reason='native_world_input_branch_unqualified'
            queued=dict(unit_present=True,plot_id=self.queues[u['id']])
        receipt=dict(action=copy.deepcopy(action),request=request,archive_hex=archive,
            archive_delivered=archive is not None,delegated_minor_war=False,queued_destination_after=queued,
            observation_before=before,observation_after=copy.deepcopy(self.ob),
            base_observation_changed=before!=self.ob,action_dialogue_retained=False,
            automatic_choices_applied=False,strategic_training_ready=False)
        self.sequence+=1;self.internal+=1
        result=dict(action=copy.deepcopy(action),effect=dict(status=status,refusal_code=reason,
            observation=copy.deepcopy(self.ob),receipt=receipt),observation_before=before,
            observation_after=copy.deepcopy(self.ob),jobs_before={'fixture':1},jobs_after={'fixture':1},
            episode_id=EPISODE,game_generation='native-'+EPISODE,sequence=self.internal,
            publication_count=self.publications,unit_source={'source_sha256':'unit-source'},
            public_runtime_admitted=False,complete_action_space=False,game_update_called=False,
            same_save_official_transition_compared=False)
        rows=[] if archive is None else [retained_turn_tests.TurnReceipts.queued(archive),
                                        *retained_turn_tests.TurnReceipts.delivered(archive)]
        rows.append(dict(stage='official_world_input_result',**copy.deepcopy(receipt)))
        interval=dict(begin={'event':{'protocol_sequence':self.sequence}},
                      returned={'event':{'protocol_sequence':self.sequence}},commands=rows,jobs=[])
        previous=dict(episode_id=EPISODE,game_generation='native-'+EPISODE,
            sequence=self.internal-1,publication_count=self.publications-int(archive is not None),observation=before)
        self.ns['saved_load_validate_transition'](result,interval,previous,update=False)
        phase=self.ns['saved_load_validate_world_input'](result,interval,result['jobs_before'])
        command=dict(status=status,reason=reason,requested_action=copy.deepcopy(action))
        self.view=self.make_view(action if status=='completed' else None)
        self.ns['validate_world_public_transition'](result,prior,self.view)
        expected=(_expected_status,) if type(_expected_status) is str else _expected_status
        if status not in expected:raise AssertionError('Unexpected fixture command status')
        self.commands.append(command);self.native.append(result);self.intervals.append(interval)
        self.ledgers.append(dict(protocol_sequence=self.sequence,action=copy.deepcopy(action),
            ledger=dict(phase_receipt=phase),command_result=command,turn_before=1,turn_after=1))
        self.views.append(copy.deepcopy(self.view))
        return copy.deepcopy(command)

    def group_rows(self):
        def summary(v):
            return dict(sequence=v['sequence'],episode_id=v['episode_id'],generation=v['game_generation'],
                turn=v['observation']['turn'],observation=v['observation'],
                world_input=v['decisions']['world_input'],queued_orders=v['decisions']['queued_orders'],
                turn_availability={'end_turn':False,'force_end_turn':True,'unready_turn':False})
        reset=summary(copy.deepcopy(self.initial));reset['episode_id']='fresh';reset['generation']='fresh'
        return [dict(public=[summary(v) for v in self.views],ledger=dict(commands=self.ledgers,updates=[],transitions=self.ledgers)),
                dict(public=[reset],ledger=dict(commands=[],updates=[],transitions=[]))]


class WorldReview(unittest.TestCase):
    def setUp(self):self.ns=functions();self.fixture=WorldFixture(self.ns)

    def movement(self):
        self.fixture.choose('world_select_unit',unit_id=17)
        self.fixture.choose('world_plot_click',unit_id=17,plot_id=4)
        return self.fixture.native[-1],self.fixture.intervals[-1]

    def validate(self,result,interval):
        return self.ns['saved_load_validate_world_input'](result,interval,result['jobs_before'])

    def test_request_uses_shared_parser_fifo_and_public_queued_destination(self):
        result,interval=self.movement();receipt=self.validate(result,interval)
        self.assertTrue(receipt['native_request_delivered']);self.assertFalse(receipt['network_ack_inferred'])
        self.assertEqual(receipt['queued_destination_after'],dict(unit_present=True,plot_id=4))

    def test_ui_selection_deselection_and_native_noop_do_not_require_publication(self):
        self.fixture.choose('world_select_unit',unit_id=17)
        self.fixture.choose('world_plot_click',unit_id=17,plot_id=0)
        self.fixture.choose('world_deselect_unit')
        self.assertEqual([r['publication_count'] for r in self.fixture.native],[0,0,0])
        self.assertTrue(all(r['observation_before']==r['observation_after'] for r in self.fixture.native))
        result=self.fixture.native[-1];interval=self.fixture.intervals[-1]
        result['jobs_after']={'fixture':2}
        with self.assertRaisesRegex(ValueError,'changed simulation'):self.validate(result,interval)

    def test_unsupported_is_refused_and_next_explicit_action_still_works(self):
        f=WorldFixture(self.ns,refuse_first=True)
        f.choose('world_select_unit',unit_id=17)
        f.choose('world_plot_click',unit_id=17,plot_id=4,_expected_status='refused')
        result,interval=f.native[-1],f.intervals[-1]
        self.assertEqual(result['publication_count'],0)
        result['effect']['status']='completed';result['effect']['refusal_code']=None
        with self.assertRaisesRegex(ValueError,'confuses unsupported'):self.validate(result,interval)
        f.choose('world_deselect_unit')
        self.assertIsNone(f.view['decisions']['world_input']['selected_unit_id'])

    def test_request_identity_source_parameters_and_payload_forgery_are_refused(self):
        source,events=self.movement()
        for field,value in [('unit_id',18),('source_sha256','0'*64),('native_callback_invoked',False),
                            ('operation_name','RANGE_ATTACK'),('width',True),('defender_player_id',2)]:
            result=copy.deepcopy(source);interval=copy.deepcopy(events)
            result['effect']['receipt']['request'][field]=value
            interval['commands'][-1]=dict(stage='official_world_input_result',**result['effect']['receipt'])
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(result,interval)

    def test_missing_receive_reordered_archive_and_result_before_drain_are_refused(self):
        source,events=self.movement()
        for change in ('drop','bytes','order','receipt'):
            result=copy.deepcopy(source);interval=copy.deepcopy(events);rows=interval['commands']
            if change=='drop':rows.pop(1)
            elif change=='bytes':rows[1]['archive_hex']='ff'
            elif change=='order':rows.insert(0,rows.pop())
            else:result['effect']['receipt']['archive_hex']='ff'
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(result,interval)

    def test_public_readback_cannot_claim_another_queue_selection_or_unoffered_input(self):
        result,_=self.movement();before=self.fixture.views[-2];after=self.fixture.views[-1]
        for change in ('queue','selection','offered'):
            prior=copy.deepcopy(before);current=copy.deepcopy(after)
            if change=='queue':current['decisions']['queued_orders']['units'][0]['plot_id']=8
            elif change=='selection':current['decisions']['world_input']['selected_unit_id']=18
            else:prior['decisions']['candidates']=[]
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.ns['validate_world_public_transition'](result,prior,current)

    def test_world_event_capture_is_opt_in_and_interval_sequence_stays_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'events.jsonl'
            rows=[dict(stage='xp1_saved_player_view_returned'),
                  dict(stage='before_xp1_saved_unit_commands',protocol_sequence=2),
                  dict(stage='official_world_input_result',fixture=True),
                  dict(stage='xp1_saved_unit_commands_returned',protocol_sequence=2)]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            kwargs=dict(allow_turn_updates=True,require_interval='unit_commands',command_sequence=2)
            old=self.ns['saved_load_events'](path,**kwargs)[1]
            new=self.ns['saved_load_events'](path,allow_world_input=True,**kwargs)[1]
            self.assertEqual(old['unit_commands_job_interval']['commands'],[])
            self.assertEqual(new['unit_commands_job_interval']['commands'],[rows[2]])

    def test_acceptance_selects_public_nonfounder_and_complete_group_has_no_poll(self):
        f=self.fixture
        group=self.ns['exercise_world_input_group'](lambda:f.view,f.choose)
        self.assertEqual(group['unit_id'],17);self.assertEqual(group['poll_calls'],0)
        report=self.ns['validate_world_group'](dict(commands=f.commands,world_input_group=group),f.group_rows())
        self.assertEqual(report['native_requests'],1);self.assertEqual(report['own_cell_native_route'],'noop')
        self.assertFalse(report['full_movement_or_combat_qualified'])

    def test_acceptance_keeps_refusal_distinct_then_authenticates_later_request(self):
        f=WorldFixture(self.ns,refuse_first=True)
        group=self.ns['exercise_world_input_group'](lambda:f.view,f.choose)
        report=self.ns['validate_world_group'](dict(commands=f.commands,world_input_group=group),f.group_rows())
        self.assertEqual(report['refused_inputs'],1);self.assertEqual(report['native_requests'],1)
        self.assertEqual([r['command_result']['status'] for r in group['click_attempts']],['refused','completed'])

    def test_group_cannot_invent_effect_reset_target_or_suppress_refusal(self):
        f=self.fixture;group=self.ns['exercise_world_input_group'](lambda:f.view,f.choose)
        for change in ('target','effect','reset','poll','command'):
            claim=copy.deepcopy(group);rows=copy.deepcopy(f.group_rows());commands=copy.deepcopy(f.commands)
            if change=='target':claim['click_attempts'][0]['target']['index']=9
            elif change=='effect':rows[0]['ledger']['commands'][1]['ledger']['phase_receipt']['native_request_delivered']=False
            elif change=='reset':rows[1]['public'][0]['queued_orders']['units'][0]['plot_id']=4
            elif change=='poll':claim['poll_calls']=1
            else:commands[1]['status']='refused'
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.ns['validate_world_group'](dict(commands=commands,world_input_group=claim),rows)


if __name__=='__main__':unittest.main()

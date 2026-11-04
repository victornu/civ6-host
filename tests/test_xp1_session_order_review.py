"""Unit-order group fixtures: actual shared review bodies, no native engine."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from civ6_host.contracts.network_turn import CAPABILITY_UNIT_ORDERS_SCHEMA
from civ6_host.runtime.native import native_saved_unit_orders as orders
import test_xp1_session_world_review as world_tests
import test_xp1_session_turn_review as turn_tests

REPO=Path(__file__).resolve().parents[1]
ORDER_SOURCE=('work/host-extensions/xp1-unit-orders-static/unit-orders-source-v1.json',
              'af79a05f7d352284dbbab6f2846935bc3effd0f4fe1d6eec564692329cd11587')


def functions():
    ns=world_tests.functions();world_validate=ns['validate_action']
    ns.update(ORDER_SOURCE=ORDER_SOURCE,CANCEL_NAME=orders.CANCEL_NAME,
              validate_catalog=orders.validate_catalog,
              validate_action=lambda a,**kw:orders.validate_action(a) if a.get('kind')=='unit_order' else world_validate(a,**kw))
    for filename,names in {
        'qualify_xp1_configuration.py':{'saved_load_validate_unit_order'},
        'review_xp1_session.py':{'validate_order_public_transition','validate_order_group'},
        'accept_session.py':{'exercise_unit_order_group'},
    }.items():
        path=REPO/'tools'/filename
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body
               if isinstance(n,ast.FunctionDef) and n.name in names]
        if len(nodes)!=len(names):raise AssertionError('Missing authored order group function')
        if filename=='qualify_xp1_configuration.py':
            # This fixture provides explicit namespace dependencies, including
            # engine-selected imports nested in the actual validator body.
            class FixtureImports(ast.NodeTransformer):
                def visit_Import(self,node):return ast.copy_location(ast.Pass(),node)
                def visit_ImportFrom(self,node):return ast.copy_location(ast.Pass(),node)
            nodes=[FixtureImports().visit(n) for n in nodes]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),ns)
    return ns


class OrderFixture(world_tests.WorldFixture):
    def __init__(self,ns,*,queue=True,heal=False,release='UNITCOMMAND_WAKE',healing_release=True,fortify_only=False):
        self.order_states={uid:dict(unit_id=uid,activity_type=1,fortify_turns=0,ready=True) for uid in (17,18)}
        self.heal=heal;self.release=release;self.healing_release=healing_release;self.fortify_only=fortify_only
        super().__init__(ns)
        if not queue:
            class EmptyQueue(dict):
                def __setitem__(self,key,value):super().__setitem__(key,None)
            self.queues=EmptyQueue(self.queues)

    def make_view(self,applied):
        view=super().make_view(applied);offers=[]
        for uid,state in sorted(self.order_states.items()):
            if state['activity_type']!=1:
                names=[self.release] if self.release is not None and (state['activity_type']!=3 or self.healing_release) else []
            else:
                names=['UNITOPERATION_FORTIFY'] if self.fortify_only and uid==17 else ['UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY']
            if self.heal and state['activity_type']==1 and uid==17:names.append('UNITOPERATION_HEAL')
            if self.queues[uid] is not None:names.append('UNITCOMMAND_CANCEL')
            for name in names:
                action=dict(kind='unit_order',unit_id=uid,route='command' if name.startswith('UNITCOMMAND') else 'operation',
                            item_type=name,hash=sum(name.encode()))
                offers.append(dict(action=action,legal=True))
        catalog=dict(player_id=0,turn=1,units=copy.deepcopy(list(self.order_states.values())),offers=offers)
        orders.validate_catalog(catalog,0,1)
        view['decisions'].update(schema=CAPABILITY_UNIT_ORDERS_SCHEMA,unit_orders=catalog)
        view['decisions']['candidates'].extend(dict(candidate_id='order-'+str(i),action=r['action']) for i,r in enumerate(offers))
        return view

    def choose(self,kind,*,_expected_status='completed',**match):
        if kind!='unit_order':return super().choose(kind,_expected_status=_expected_status,**match)
        prior=copy.deepcopy(self.view);before=copy.deepcopy(self.ob)
        action=next(r['action'] for r in prior['decisions']['candidates']
            if r['action']['kind']==kind and all(r['action'].get(k)==v for k,v in match.items()))
        uid=action['unit_id'];old=copy.deepcopy(self.order_states[uid]);name=action['item_type']
        if name=='UNITCOMMAND_CANCEL':
            self.queues[uid]=None
            if self.order_states[uid]['activity_type']!=1:self.order_states[uid].update(activity_type=1,ready=True)
        else:self.order_states[uid].update(activity_type=1 if name=='UNITCOMMAND_WAKE' else 3 if name=='UNITOPERATION_HEAL' else 2,
                                          ready=name=='UNITCOMMAND_WAKE')
        current=copy.deepcopy(self.order_states[uid])
        receipt=dict(action=copy.deepcopy(action),unit_before=old,unit_after=current,state_changed=old!=current,
            observation_before=before,observation_after=copy.deepcopy(self.ob),source_proof_sha256=ORDER_SOURCE[1],
            native_archive_delivered=True,automatic_choices_applied=False,strategic_training_ready=False)
        if name=='UNITCOMMAND_CANCEL':receipt['cancel_source_proof_sha256']=ORDER_SOURCE[1]
        previous=dict(episode_id=world_tests.EPISODE,game_generation='native-'+world_tests.EPISODE,
            sequence=self.internal,publication_count=self.publications,observation=before)
        self.sequence+=1;self.internal+=1;self.publications+=1
        result=dict(action=copy.deepcopy(action),effect=dict(status='completed',refusal_code=None,observation=copy.deepcopy(self.ob),receipt=receipt),
            observation_before=before,observation_after=copy.deepcopy(self.ob),jobs_before={'fixture':1},jobs_after={'fixture':1},
            episode_id=world_tests.EPISODE,game_generation='native-'+world_tests.EPISODE,
            sequence=self.internal,publication_count=self.publications,unit_source={'source_sha256':'unit-source'},
            public_runtime_admitted=False,complete_action_space=False,game_update_called=False,
            same_save_official_transition_compared=False)
        archive='aabbccdd';rows=[turn_tests.TurnReceipts.queued(archive),*turn_tests.TurnReceipts.delivered(archive),
                                dict(stage='official_explicit_unit_order_effect',**copy.deepcopy(receipt))]
        interval=dict(begin={'event':{'protocol_sequence':self.sequence}},returned={'event':{'protocol_sequence':self.sequence}},
                      commands=rows,jobs=[])
        self.ns['saved_load_validate_transition'](result,interval,previous,update=False)
        phase=self.ns['saved_load_validate_unit_order'](result,interval,result['jobs_before'])
        self.view=self.make_view(action);self.ns['validate_order_public_transition'](result,prior,self.view)
        command=dict(status='completed',reason=None,requested_action=copy.deepcopy(action))
        self.commands.append(command);self.native.append(result);self.intervals.append(interval)
        self.ledgers.append(dict(protocol_sequence=self.sequence,action=copy.deepcopy(action),
            ledger=dict(phase_receipt=phase),command_result=command,turn_before=1,turn_after=1))
        self.views.append(copy.deepcopy(self.view));return copy.deepcopy(command)

    def group_rows(self):
        rows=super().group_rows()
        for v,summary in zip(self.views,rows[0]['public']):summary['unit_orders']=v['decisions']['unit_orders']
        rows[1]['public'][0]['unit_orders']=self.initial['decisions']['unit_orders']
        return rows


class OrderReview(unittest.TestCase):
    def setUp(self):self.ns=functions()

    def group(self,**options):
        f=OrderFixture(self.ns,**options)
        group=self.ns['exercise_unit_order_group'](lambda:f.view,f.choose)
        acceptance=dict(status='native_capability_unit_order_group_reset_verified' if group['complete'] else
                        'native_capability_unit_order_group_incomplete',commands=f.commands,unit_order_group=group)
        report=self.ns['validate_order_group'](acceptance,f.group_rows())
        return f,acceptance,report

    def test_rest_wake_then_nonempty_cancel_with_unchanged_activity(self):
        f,a,report=self.group();self.assertTrue(report['complete']);self.assertTrue(report['queued_destination_cleared'])
        self.assertEqual(report['executed_orders'],['UNITOPERATION_SLEEP','UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL'])
        cancel=next(r for r in f.native if r['action'].get('item_type')=='UNITCOMMAND_CANCEL')
        self.assertFalse(cancel['effect']['receipt']['state_changed'])
        self.assertEqual(cancel['observation_before'],cancel['observation_after'])
        self.assertIsNotNone(a['unit_order_group']['cancel']['queued_before'])

    def test_no_queued_goal_is_incomplete_but_reset_still_authenticated(self):
        f,a,report=self.group(queue=False)
        self.assertFalse(report['complete']);self.assertFalse(report['queued_destination_cleared'])
        self.assertEqual(report['incomplete_reason'],'native_queued_destination_not_witnessed')
        self.assertTrue(1<=len(a['unit_order_group']['click_attempts'])<=4)
        self.assertNotIn('UNITCOMMAND_CANCEL',report['executed_orders'])
        self.assertIsNone(f.view['decisions']['world_input']['selected_unit_id'])

    def test_optional_healing_executes_only_offered_selected_unit_order(self):
        f,a,report=self.group(heal=True)
        self.assertEqual(report['native_healing_orders'],['UNITOPERATION_HEAL'])
        self.assertFalse(report['healing_over_turns_qualified'])
        self.assertFalse(a['unit_order_group']['healing'][1]['executed'])
        self.assertTrue(all(r['action']['unit_id']==17 for r in f.native if r['action']['kind']=='unit_order'))

    def test_fortify_uses_offered_cancel_release_without_inventing_wake(self):
        f,a,report=self.group(release='UNITCOMMAND_CANCEL',fortify_only=True)
        self.assertTrue(report['complete'])
        self.assertEqual(report['release_action']['item_type'],'UNITCOMMAND_CANCEL')
        self.assertEqual(report['executed_orders'],['UNITOPERATION_FORTIFY','UNITCOMMAND_CANCEL','UNITCOMMAND_CANCEL'])
        self.assertNotIn('wake_sequence',a['unit_order_group'])

    def test_missing_rest_or_healing_release_finishes_explicitly_incomplete(self):
        for options,reason in (({'release':None},'native_rest_release_not_offered'),
                               ({'heal':True,'healing_release':False},'native_healing_release_not_offered')):
            f,a,report=self.group(**options)
            with self.subTest(options=options):
                self.assertFalse(report['complete']);self.assertEqual(report['incomplete_reason'],reason)
                self.assertEqual(report['world_click_attempts'],0)
                self.assertIsNone(a['unit_order_group']['selection_sequence'])

    def test_effect_requires_exact_real_four_keys_and_null_refusal_code(self):
        f,_,_=self.group();source=f.native[0];interval=f.intervals[0]
        for change in ('missing','false_reason','extra'):
            result=copy.deepcopy(source)
            if change=='missing':result['effect'].pop('refusal_code')
            elif change=='false_reason':result['effect']['refusal_code']='pretend_refusal'
            else:result['effect']['invented']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.ns['saved_load_validate_unit_order'](result,interval,result['jobs_before'])

    def test_unit_event_source_receipt_and_transport_tampering_are_refused(self):
        f,_,_=self.group();idx=next(i for i,r in enumerate(f.native) if r['action'].get('item_type')=='UNITCOMMAND_CANCEL')
        for change in ('source','cancel_source','unit','state','archive','no_receive'):
            result=copy.deepcopy(f.native[idx]);interval=copy.deepcopy(f.intervals[idx]);receipt=result['effect']['receipt']
            if change=='source':receipt['source_proof_sha256']='0'*64
            elif change=='cancel_source':receipt['cancel_source_proof_sha256']='0'*64
            elif change=='unit':receipt['unit_after']['unit_id']=18
            elif change=='state':receipt['state_changed']=True
            elif change=='archive':receipt['native_archive_delivered']=False
            else:interval['commands'].pop(1)
            interval['commands'][-1]=dict(stage='official_explicit_unit_order_effect',**receipt)
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.ns['saved_load_validate_unit_order'](result,interval,result['jobs_before'])

    def test_public_order_offer_activity_and_selection_cannot_be_fabricated(self):
        f,_,_=self.group();result=f.native[0];old=f.views[0];new=f.views[1]
        for change in ('offer','legal','activity','selection'):
            prior=copy.deepcopy(old);current=copy.deepcopy(new)
            if change=='offer':prior['decisions']['candidates']=[]
            elif change=='legal':
                for r in prior['decisions']['unit_orders']['offers']:r['legal']=False
            elif change=='activity':current['decisions']['unit_orders']['units'][0]['activity_type']=9
            else:current['decisions']['world_input']['selected_unit_id']=18
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.ns['validate_order_public_transition'](result,prior,current)

    def test_cancel_claim_cannot_use_empty_prior_queue_or_hide_reset_change(self):
        f,a,_=self.group()
        for change in ('empty','not_cleared','reset','optional','omitted','publication'):
            claim=copy.deepcopy(a);rows=copy.deepcopy(f.group_rows());group=claim['unit_order_group'];seq=group['cancel']['sequence']
            if change=='empty':
                p=max((p for p in rows[0]['public'] if p['sequence']<seq),key=lambda p:p['sequence'])
                p['queued_orders']['units'][0]['plot_id']=None
            elif change=='not_cleared':next(p for p in rows[0]['public'] if p['sequence']==seq)['queued_orders']['units'][0]['plot_id']=4
            elif change=='reset':rows[1]['public'][0]['unit_orders']['units'][0]['ready']=False
            elif change=='optional':group['healing'][0]['executed']=True
            elif change=='omitted':group['orders'].pop()
            else:group['complete']=False
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                self.ns['validate_order_group'](claim,rows)

    def test_unit_order_publication_requires_exactly_one_native_publish(self):
        f,_,_=self.group();result=f.native[0];interval=f.intervals[0]
        prior=dict(episode_id=result['episode_id'],game_generation=result['game_generation'],sequence=0,
                   publication_count=0,observation=result['observation_before'])
        for count in (0,2,True):
            changed=copy.deepcopy(result);changed['publication_count']=count
            with self.subTest(count=count),self.assertRaises(ValueError):
                self.ns['saved_load_validate_transition'](changed,interval,prior,update=False)

    def test_unit_event_capture_is_explicit_and_old_world_route_stays_usable_on_v5(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'events.jsonl';rows=[dict(stage='xp1_saved_player_view_returned'),
                dict(stage='before_xp1_saved_unit_commands',protocol_sequence=1),
                dict(stage='official_explicit_unit_order_effect',fixture=True),
                dict(stage='xp1_saved_unit_commands_returned',protocol_sequence=1)]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            kw=dict(allow_turn_updates=True,require_interval='unit_commands',command_sequence=1)
            self.assertEqual(self.ns['saved_load_events'](path,**kw)[1]['unit_commands_job_interval']['commands'],[])
            self.assertEqual(self.ns['saved_load_events'](path,allow_unit_orders=True,**kw)[1]['unit_commands_job_interval']['commands'],[rows[2]])
        f=OrderFixture(self.ns);group=self.ns['exercise_world_input_group'](lambda:f.view,f.choose)
        self.assertEqual(group['unit_id'],17);self.assertEqual(group['poll_calls'],0)


if __name__=='__main__':unittest.main()

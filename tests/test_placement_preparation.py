"""Explicit public-client fixtures for the bounded placement qualifier only."""
import copy
import unittest

import accept_session as accept
import review_xp1_session as review
import test_xp1_session_placement_review as placement

IDENTITY=dict(technology_type='TECH_ASTROLOGY',action_hash=2325542178,
              target_type='DISTRICT_HOLY_SITE',database_cost=50,database={'fixture':True})
FOUND=dict(kind='found_city',unit_id=18,x=1,y=0)
ASTROLOGY=dict(kind='research',index=4,hash=2325542178)
PRODUCTION=dict(kind='production',city_id=23,category='unit',index=0,hash=100,item_type='UNIT_SCOUT')


class PublicPreparation:
    def __init__(self,*,ready_turn=2,stall=False):
        self.turn=1;self.seq=0;self.city=False;self.selected=None;self.production=False
        self.active=True;self.ready_turn=ready_turn;self.stall=stall;self.views=[];self.commands=[]
        self.refresh()

    def refresh(self):
        offers=[dict(kind='force_end_turn')]
        if not self.city:offers.append(FOUND)
        offers.append(ASTROLOGY)
        if self.city and not self.production:offers.append(PRODUCTION)
        place=[dict(kind='production_placement',category='district')] if self.city and self.turn>=self.ready_turn else []
        self.view=dict(sequence=self.seq,observation=dict(turn=self.turn,cities=[dict(id=23)] if self.city else []),
            outcome=dict(terminated=False,truncated=False),decisions=dict(candidates=[dict(action=a) for a in offers],
                placement_offers=place,turn_controls=dict(active=self.active,active_complete=self.active,
                    can_unready=False,timer_elapsed=False),choice_state=dict(research=dict(research=self.selected,civic=0),
                    production=[dict(city_id=23,queue_size=int(self.production))] if self.city else [])))
        self.views.append(copy.deepcopy(self.view))

    def choose(self,kind,**match):
        action=next(r['action'] for r in self.view['decisions']['candidates'] if r['action']['kind']==kind
                    and all(r['action'].get(k)==v for k,v in match.items()))
        if kind=='found_city':self.city=True
        elif kind=='research':self.selected=action['index']
        elif kind=='production':self.production=True
        elif kind=='force_end_turn':self.active=False
        else:raise AssertionError('Unrequested fixture action')
        self.seq+=1;self.refresh();result=dict(status='completed',reason=None,requested_action=copy.deepcopy(action))
        self.commands.append(result);return result

    def poll(self):
        if not self.stall:self.turn+=1;self.active=True
        self.seq+=1;self.refresh()

    def prepare(self,*,max_turns=2,remaining=lambda:500):
        self.receipt={}
        return accept.prepare_placement_boundary(lambda:self.view,self.choose,self.poll,
            max_turns=max_turns,remaining=remaining,identity=IDENTITY,receipt=self.receipt)


class PlacementPreparation(unittest.TestCase):
    def test_current_offer_needs_no_turn_and_missing_city_uses_public_astrology(self):
        available=PublicPreparation(ready_turn=1);available.city=True;available.refresh()
        receipt=available.prepare()
        self.assertEqual(receipt['prepared_boundary'],dict(sequence=0,turn=1));self.assertEqual(receipt['transitions'],[])
        fixture=PublicPreparation();receipt=fixture.prepare()
        self.assertEqual([r['requested_action']['kind'] for r in fixture.commands],
                         ['found_city','research','production','force_end_turn'])
        self.assertEqual(fixture.commands[1]['requested_action'],ASTROLOGY)
        self.assertEqual(receipt['prepared_boundary'],dict(sequence=5,turn=2))
        self.assertEqual((receipt['turns_advanced'],receipt['poll_calls']),(1,1))
        self.assertEqual((receipt['total_group_seconds'],receipt['reset_reserve_seconds']),(1200,180))
        self.assertFalse(receipt['checkpoint_used'])

    def test_turn_poll_and_deadline_limits_refuse_without_synthetic_unlock(self):
        for mode in ('turn','poll','deadline'):
            fixture=PublicPreparation(ready_turn=99,stall=mode=='poll')
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):
                fixture.prepare(max_turns=1,remaining=(lambda:59) if mode=='deadline' else (lambda:500))
            self.assertIsNone(fixture.receipt['prepared_boundary'])
            self.assertFalse(any(a['requested_action']['kind']=='production_placement' for a in fixture.commands))
            if mode=='poll':self.assertEqual(fixture.receipt['poll_calls'],32)
            if mode=='deadline':self.assertFalse(fixture.commands)

    def prepared_group(self):
        # Reuse the three existing placement shapes after a typed public prefix.
        # These dictionaries never become a written acceptance/native receipt.
        policy=PublicPreparation();prep=policy.prepare()
        ns=placement.functions();f=placement.PlacementFixture(ns)
        group=accept.exercise_placement_group(lambda:f.view,f.choose,category='district')
        rows=f.group_rows();original=copy.deepcopy(rows[0]['public'][0]);prefix=[];transitions=[]
        for view in policy.views[:-1]:
            summary=copy.deepcopy(original);summary.update(sequence=view['sequence'],turn=view['observation']['turn'],
                candidates=copy.deepcopy(view['decisions']['candidates']),turn_controls=copy.deepcopy(view['decisions']['turn_controls']))
            summary['choice_state']['research']=copy.deepcopy(view['decisions']['choice_state']['research'])
            if not view['observation']['cities']:summary['observation']['cities']=[]
            prefix.append(summary)
        offset=prep['prepared_boundary']['sequence']
        for summary in rows[0]['public']:
            summary['sequence']+=offset;summary['turn']=2;summary['observation']['turn']=2
            summary['choice_state']['research']['research']=4
            summary['turn_controls']=copy.deepcopy(policy.view['decisions']['turn_controls'])
        rows[0]['public']=prefix+rows[0]['public']
        for step in group['steps']:step['sequence']+=offset
        group.update(initial_turn=2,final_turn=2)
        for row in rows[0]['ledger']['commands']:
            row['protocol_sequence']+=offset;row.update(turn_before=2,turn_after=2)
        for record in prep['transitions']:
            transitions.append(dict(protocol_sequence=record['sequence'],action=copy.deepcopy(record['action']),
                command_result=copy.deepcopy(record['command_result']),turn_before=record['turn_before'],
                turn_after=record['turn_after'],phase='turn_update' if record['action'] is None else 'unit_commands'))
        rows[0]['ledger']['commands']=[r for r in transitions if r['action'] is not None]+rows[0]['ledger']['commands']
        rows[0]['ledger']['updates']=[r for r in transitions if r['action'] is None]
        rows[0]['ledger']['transitions']=transitions+rows[0]['ledger']['commands'][-3:]
        fresh=copy.deepcopy(rows[0]['public'][0]);fresh.update(episode_id='fresh',generation='fresh-generation')
        rows[1]['public'][0]=fresh
        acceptance=dict(placement_group=group,placement_preparation=prep,seconds=100,
            commands=[copy.deepcopy(r['command_result']) for r in rows[0]['ledger']['commands']])
        return acceptance,rows

    def test_prepared_boundary_is_distinct_from_original_capture_reset(self):
        acceptance,rows=self.prepared_group();actual=review.validate_placement_group(acceptance,rows)
        self.assertEqual(actual['turn'],2);self.assertEqual(actual['preparation']['initial_turn'],1)
        self.assertEqual(actual['preparation']['command_count'],4);self.assertEqual(actual['preparation']['poll_calls'],1)
        self.assertTrue(actual['preparation']['reset_to_original_capture'])
        for mode in ('missing','boundary','reset','limit','extra_update'):
            altered,events=copy.deepcopy(acceptance),copy.deepcopy(rows)
            if mode=='missing':altered['placement_preparation']['transitions'].pop(0)
            elif mode=='boundary':altered['placement_preparation']['prepared_boundary']['sequence']=4
            elif mode=='reset':events[1]['public'][0]['observation']['cities']=[dict(id=23)]
            elif mode=='limit':altered['seconds']=1201
            else:events[0]['ledger']['updates'].append(dict(protocol_sequence=99))
            with self.subTest(mode=mode),self.assertRaises(ValueError):review.validate_placement_group(altered,events)
        historical=copy.deepcopy(acceptance)
        historical['placement_preparation']['total_group_seconds']=840
        historical['placement_preparation'].pop('reset_reserve_seconds')
        self.assertEqual(review.validate_placement_group(historical,rows)['turn'],2)
        historical['seconds']=841
        with self.assertRaises(ValueError):review.validate_placement_group(historical,rows)

    def test_in_session_inventory_witness_does_not_claim_checkpoint_survival(self):
        acceptance,rows=self.prepared_group();action=acceptance['placement_group']['steps'][0]['action']
        native={k:action[k] for k in ('city_id','category','index','hash','item_type','plot_id','x','y')}
        native.update(complete=False,district_id=45)
        placed_sequence=acceptance['placement_group']['steps'][0]['sequence']
        for i,row in enumerate(rows):
            # Readback source and identity joins are exercised independently by
            # test_xp2_session_placement_review through the real parser.
            row['inventory_receipts']={'offline_readback_fixture':True}
            for value in row['public']:
                value['placement_inventory']={'rows':[copy.deepcopy(native)] if i==0 and value['sequence']>=placed_sequence else []}
        result=review.validate_placement_group(acceptance,rows)['native_inventory']
        self.assertTrue(result['positive_in_session']);self.assertTrue(result['original_and_reset_empty'])
        self.assertFalse(result['checkpoint_survival_claimed']);self.assertFalse(result['host_tracking_used'])
        rows[1]['public'][0]['placement_inventory']['rows']=[native]
        with self.assertRaisesRegex(ValueError,'inventory'):review.validate_placement_group(acceptance,rows)


if __name__=='__main__':unittest.main()

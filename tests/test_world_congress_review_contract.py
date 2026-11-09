"""Portable historical-result validation; fixture contents do not assert an ACK."""
from copy import deepcopy
import unittest

from civ6_host.contracts import world_congress_review as review


def catalogue(player_id=0, turn=52, sequence=0, turn_segment=1278700307):
    known=dict(player_id=player_id,label='Own leader')
    hidden=dict(player_id=None,label='LOC_DIPLOPANEL_UNMET_PLAYER')
    own_target=dict(player_id=player_id,value=str(player_id),label='Own leader')
    hidden_target=dict(player_id=None,value=None,label='LOC_DIPLOPANEL_UNMET_PLAYER')
    return dict(schema=review.SCHEMA,player_id=player_id,turn=turn,sequence=sequence,
        turn_segment=turn_segment,history_kind='last_results',resolutions=[dict(index=0,
            resolution_type='RESOLUTION_FIXTURE',name='Historical resolution',target_type='PlayerType',
            chosen_option='Accepted',chosen_label='A',chosen_target=own_target,
            rejected_option='Rejected',rejected_label='B',is_new=False,votes_a=2,votes_b=3,tied=False,
            votes=[dict(voter=known,option=1,votes=2,target=own_target,option_label='A'),
                   dict(voter=hidden,option=2,votes=3,target=hidden_target,option_label='B')])],
        discussions=[dict(index=0,category_type='PROPOSAL_FIXTURE',category_name='Emergency',
            type_name='HISTORICAL_DISCUSSION',name='Historical proposal',description='Public description',
            target=hidden,is_new=True,votes_up=3,votes_down=2,passed=True,
            votes=[dict(voter=known,votes=-2,reason=''),dict(voter=hidden,votes=3,reason='')])])


class ReviewContractTests(unittest.TestCase):
    def test_public_history_has_no_ack_or_session_identity(self):
        value=catalogue()
        self.assertIs(review.validate_catalogue(value,0,52,0),value)
        self.assertIs(review.compare_own(value,dict(player_id=0,turn=52),0),value)
        self.assertEqual(value['history_kind'],'last_results')
        self.assertNotIn('session_id',value)
        self.assertNotIn('acknowledged',value)
        self.assertIsNone(value['resolutions'][0]['votes'][1]['target']['value'])

    def test_foreign_observation_identity_and_nonintegral_types_refused(self):
        for field,new in (('player_id',1),('turn',53),('sequence',1),('sequence',False)):
            value=catalogue();value[field]=new
            with self.subTest(field=field,new=new),self.assertRaises(ValueError):
                review.validate_catalogue(value,0,52,0)
        with self.assertRaises(ValueError): review.validate_catalogue(catalogue(),False,52,0)

    def test_hidden_identity_and_additional_raw_fields_refused(self):
        mutations=[lambda v:v.update(session_id=4),
            lambda v:v['resolutions'][0]['votes'][1]['target'].update(value='17'),
            lambda v:v['resolutions'][0]['votes'][1]['voter'].update(raw_player_id=17),
            lambda v:v['discussions'][0].update(sender=17),
            lambda v:v['discussions'][0]['votes'][0].update(submitted=True)]
        for change in mutations:
            value=catalogue();change(value)
            with self.assertRaises(ValueError): review.validate_catalogue(value,0,52,0)

    def test_signed_votes_totals_and_order_are_strict_without_filtering(self):
        value=catalogue()
        vote=value['discussions'][0]['votes'][0]
        vote['votes']=-2147483648
        value['discussions'][0].update(votes_down=2147483648,passed=False)
        review.validate_catalogue(value,0,52,0)
        for change in (lambda v:v['discussions'][0].update(votes_down=2),
                       lambda v:v['resolutions'][0].update(index=8),
                       lambda v:v['discussions'][0]['votes'][0].update(votes=-2147483649)):
            bad=deepcopy(value);change(bad)
            with self.assertRaises(ValueError): review.validate_catalogue(bad,0,52,0)

    def test_raw_signed_option_domain_and_official_one_else_totals(self):
        for option in (-0x80000000,-1,0,1,2,3,0x7fffffff):
            value=catalogue();row=value['resolutions'][0]
            row['votes'][0]['option']=option
            row.update(votes_a=2 if option==1 else 0,votes_b=3 if option==1 else 5,tied=False)
            self.assertIs(review.validate_catalogue(value,0,52,0),value)
            self.assertEqual(row['votes'][0]['option'],option)
        for option in (-0x80000001,0x80000000,True,1.0,'0',None):
            value=catalogue();value['resolutions'][0]['votes'][0]['option']=option
            with self.subTest(option=option),self.assertRaises(ValueError):review.validate_catalogue(value,0,52,0)

    def test_signed_resolution_votes_and_64_player_totals_are_exact(self):
        from copy import deepcopy
        for option in (1,0,2):
            for count in (-0x80000000,-1,0,0x7fffffff):
                value=catalogue();row=value['resolutions'][0];base=deepcopy(row['votes'][0])
                row['votes']=[]
                for pid in range(64):
                    vote=deepcopy(base);vote.update(option=option,votes=count);vote['voter']['player_id']=pid
                    row['votes'].append(vote)
                row.update(votes_a=64*count if option==1 else 0,votes_b=0 if option==1 else 64*count,tied=count==0)
                review.validate_catalogue(value,0,52,0)
                row['votes_b']+=1
                with self.assertRaises(ValueError):review.validate_catalogue(value,0,52,0)
        for count in (-0x80000001,0x80000000,True,1.0):
            value=catalogue();value['resolutions'][0]['votes'][0]['votes']=count
            with self.assertRaises(ValueError):review.validate_catalogue(value,0,52,0)

    def test_empty_results_are_valid_history_only(self):
        value=catalogue();value.update(resolutions=[],discussions=[])
        self.assertEqual(review.validate_catalogue(value,0,52,0),value)


if __name__=='__main__': unittest.main()

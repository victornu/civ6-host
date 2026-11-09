"""Portable v40 additions on retained prior public replies; no native calls."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest

from civ6_host import SessionClient,InformationUnavailable
from civ6_host.contracts import network_turn as nt
from civ6_host.contracts import world_congress_active_effects as effects
import test_native_command_permissions as permissions
import test_world_congress_review_client as previous


def catalogue(pid=0,turn=52,sequence=0,segment=1278700307):
    return dict(schema=effects.SCHEMA,player_id=pid,turn=turn,sequence=sequence,turn_segment=segment,
        meeting_turns_left=5,proposals=[],proposals_status=effects.PROPOSALS_STATUS,
        resolutions=[dict(index=0,resolution_type='RESOLUTION_FIXTURE',name='Resolution',target_type='PlayerType',
            chosen_option='Public effect',chosen_label='Native label',is_new=False,turns_left=6,
            chosen_target=dict(player_id=None,value=None,label='LOC_DIPLOPANEL_UNMET_PLAYER'))])


def retained_v39():
    response=permissions.NativeCommandPermissionsTests().retained_v38()
    old=response['decisions']
    response['decisions']=nt.upgrade_command_permissions_catalogue(old,permissions.permissions(old),response['observation'])
    return response


class ActiveEffectsContractTests(unittest.TestCase):
    def upgraded(self):
        response=retained_v39();old=deepcopy(response['decisions'])
        value=catalogue(old['player_id'],old['turn'],old['sequence'],old['world_congress']['turn_segment'])
        response['decisions']=nt.upgrade_active_effects_catalogue(old,value,response['observation'])
        return response,old

    def test_native_duration_domain_hidden_targets_and_exact_summary_availability(self):
        for turns in (-0x80000000,-1,0,0x7fffffff):
            value=catalogue();value['meeting_turns_left']=turns;value['resolutions'][0]['turns_left']=turns+1
            effects.validate_catalogue(value,0,52,0)
        changes=[lambda v:v.update(proposals=None),lambda v:v.update(proposals_status='summary_source_unqualified'),
            lambda v:v['resolutions'][0].update(turns_left=0),lambda v:v['resolutions'][0].update(is_new=1),
            lambda v:v['resolutions'][0].update(target_type=None),
            lambda v:v['resolutions'][0]['chosen_target'].update(value='7'),
            lambda v:v['resolutions'][0].update(raw_target_id=7),lambda v:v.update(sequence=True)]
        for change in changes:
            value=catalogue();change(value)
            with self.assertRaises(ValueError):effects.validate_catalogue(value,0,52,0)

    def test_v40_preserves_all_prior_fields_choices_and_permission_behavior(self):
        response,old=self.upgraded();value=response['decisions']
        previous.validate(value,response['observation'])
        for key in old:
            if key not in ('schema','decision_id'):self.assertEqual(value[key],old[key])
        self.assertEqual(value['candidates'],old['candidates']);self.assertEqual(value['families'],old['families'])
        self.assertFalse(value['complete_action_space']);self.assertNotEqual(value['decision_id'],old['decision_id'])
        for row in old['candidates']:
            if row['action']['kind'].startswith('congress_') or row['action']['kind']=='policies':continue
            self.assertEqual(nt.select_capability(value,dict(decision_id=value['decision_id'],candidate_id=row['candidate_id'])),
                             nt.select_capability(old,dict(decision_id=old['decision_id'],candidate_id=row['candidate_id'])))

    def test_information_is_cached_detached_and_v39_is_explicitly_unavailable(self):
        response,old=self.upgraded();backend=previous.ReplayBackend(response);client=SessionClient(backend)
        client.reset();public=client.information('world_congress_active_effects')
        self.assertEqual(public['data'],response['decisions']['world_congress_active_effects'])
        self.assertEqual(public['data']['proposals'],[])
        self.assertEqual(public['source_contracts']['world_congress_active_effects'],effects.SCHEMA)
        public['data']['resolutions'].clear()
        self.assertEqual(len(client.information('world_congress_active_effects')['data']['resolutions']),1)
        self.assertFalse(backend.calls)
        response['decisions']=old;client=SessionClient(previous.ReplayBackend(response));client.reset()
        with self.assertRaises(InformationUnavailable):client.information('world_congress_active_effects')

    def test_proposal_cards_preserve_displayed_details_and_refuse_hidden_fields(self):
        value=catalogue();row=dict(index=0,category_type='PROPOSAL_EMERGENCY',category_name='Emergency',
            type_name='WC_EMERGENCY_FIXTURE',name='Visible title',target=dict(player_id=None,label='Unmet'),
            is_new=True,description='Native final description',turns_left=-0x80000000,
            emergency_type='EMERGENCY_FIXTURE',goals=[dict(name='Visible goal',completed=False)],
            crisis_details=['Goal'],rewards_details=['Reward'])
        value['proposals']=[row];effects.validate_catalogue(value,0,52,0)
        for change in (lambda r:r.update(Sender=7),lambda r:r.update(PerPlayerVotes={}),
                       lambda r:r.update(is_new=-1),lambda r:r.update(turns_left=0x80000000),
                       lambda r:r['target'].update(raw_target=7),lambda r:r['goals'][0].update(name=''),
                       lambda r:r['goals'][0].update(completed=1)):
            bad=deepcopy(value);change(bad['proposals'][0])
            with self.assertRaises(ValueError):effects.validate_catalogue(bad,0,52,0)

    def test_foreign_stale_phase_and_missing_availability_are_refused(self):
        response,old=self.upgraded();value=response['decisions']['world_congress_active_effects']
        for key,new in (('player_id',1),('turn',old['turn']+1),('sequence',old['sequence']+1),('turn_segment',0)):
            bad=deepcopy(value);bad[key]=new
            with self.assertRaises(ValueError):nt.upgrade_active_effects_catalogue(old,bad)
        with self.assertRaisesRegex(ValueError,'explicit status'):nt.upgrade_active_effects_catalogue(old,None)
        unavailable=nt.upgrade_active_effects_catalogue(old,None,status='active_effects_ui_unavailable')
        previous.validate(unavailable,response['observation'])
        with self.assertRaises(ValueError):nt.upgrade_active_effects_catalogue(old,value,status='active_effects_ui_unavailable')

    def test_checkpoint_removes_only_new_public_metadata(self):
        response,old=self.upgraded();current=response['decisions']
        projected,transition=nt.checkpoint_catalogue(current,old,response['observation'],core_sha256=nt._XP2_COMBAT_CORE)
        self.assertEqual(projected,old)
        self.assertEqual(transition['added_public_fields'],['world_congress_active_effects','world_congress_active_effects_status'])
        self.assertNotIn('added_action_families',transition)

    def test_checkpoint_rebinds_only_observation_sequence_and_keeps_effect_contents(self):
        from civ6_host.runtime.network_checkpoint import _semantic_decisions
        from civ6_host.contracts.world_congress import CANDIDATE_FIELDS
        response,_=self.upgraded();first=response['decisions'];second=deepcopy(first)
        second['sequence']=7
        for key in ('world_congress','world_congress_review','native_command_permissions','world_congress_active_effects'):
            if second[key] is not None:second[key]['sequence']=7
        rebound={}
        for row in second['candidates']:
            if row['action']['kind'] in CANDIDATE_FIELDS:
                old=row['candidate_id'];row['action']['sequence']=7
                row['candidate_id']=nt.digest(row['action']);rebound[old]=row['candidate_id']
        for family in second['families'].values():
            if 'candidate_ids' in family:
                family['candidate_ids']=[rebound.get(key,key) for key in family['candidate_ids']]
        previous.seal(second)
        a=_semantic_decisions(first,response['observation']);b=_semantic_decisions(second,response['observation'])
        self.assertEqual(a,b)
        second['world_congress_active_effects']['resolutions'][0]['chosen_label']='Changed native effect'
        previous.seal(second)
        self.assertNotEqual(a,_semantic_decisions(second,response['observation']))


if __name__=='__main__':unittest.main()

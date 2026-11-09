"""Known saved objects and explicitly derived identity-rebind fixtures.

The failed native run did not retain its full restored catalogue. These tests
do not invent that missing witness or certify equality of its gameplay data.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from civ6_host.contracts import network_turn, world_congress
from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime.native.native_session_resume import semantic_decisions as historical
import test_world_congress_client as previous
from test_world_congress_review_contract import catalogue as review_catalogue


def saved_checkpoint():
    path=Path(os.environ['CIV6_HOST_RESOURCE_ROOT'])/'work/host-simultaneous/native-runs/run-8b9ed16820ba449abf4183ee97f8c8de/checkpoint/checkpoint.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='0ac1b25db4b0a7dc766e786a3639649927e3f4010de7e5f98906f5344bdde658':
        raise ValueError('Retained T61 checkpoint changed')
    return json.loads(raw)


def seal(value):
    value.pop('decision_id',None);value['decision_id']=network_turn.digest(value)


def reset_identity(value,sequence=0):
    """Synthetic identity-only fixture, explicitly not the missing native read."""
    result=deepcopy(value)
    result.update(episode_id='1a19889c-456f-422d-b95a-b28f5a452b93',
        game_generation='native-1a19889c-456f-422d-b95a-b28f5a452b93',sequence=sequence)
    if result['world_congress'] is not None:result['world_congress']['sequence']=sequence
    if result.get('world_congress_review') is not None:result['world_congress_review']['sequence']=sequence
    for row in result['candidates']:
        if row['action']['kind'] in world_congress.CANDIDATE_FIELDS:
            old=row['candidate_id'];row['action']['sequence']=sequence
            row['candidate_id']=network_turn.digest(row['action'])
            family=result['families'][row['action']['kind']]
            family['candidate_ids']=[row['candidate_id'] if key==old else key for key in family['candidate_ids']]
    seal(result)
    return result


class CongressCheckpointIdentityTests(unittest.TestCase):
    def test_v39_rebinds_permission_sequence_without_erasing_native_flags(self):
        m = saved_checkpoint()
        v38 = network_turn.upgrade_review_catalogue(m['decisions'], None,
            observation=m['observation'], status='review_ui_unavailable')
        permissions = dict(player_id=v38['player_id'], turn=v38['turn'],
            sequence=v38['sequence'], allow_strategic=True, allow_tactical=True)
        saved = network_turn.upgrade_command_permissions_catalogue(v38, permissions,
            observation=m['observation'])
        reset = reset_identity(saved)
        reset['native_command_permissions']['sequence'] = 0
        seal(reset)
        self.assertEqual(checkpoint._semantic_decisions(saved, m['observation']),
                         checkpoint._semantic_decisions(reset, m['observation']))
        reset['native_command_permissions']['allow_tactical'] = False
        seal(reset)
        self.assertNotEqual(checkpoint._semantic_decisions(saved, m['observation']),
                            checkpoint._semantic_decisions(reset, m['observation']))

    def test_actual_last_public_reply_and_saved_manifest_are_identical(self):
        root=Path(os.environ['CIV6_HOST_RESOURCE_ROOT'])/'work/trade-common-client/congress-checkpoint-diff'
        proof=json.loads((root/'source.json').read_bytes())['actual_producer_reply']
        raw=(root/'producer-public-response.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),proof['sha256'])
        response=json.loads(raw);saved=saved_checkpoint()
        self.assertEqual(response['observation'],saved['observation'])
        self.assertEqual(response['decisions'],saved['decisions'])
        self.assertEqual(checkpoint._semantic_decisions(response['decisions'],response['observation']),
                         checkpoint._semantic_decisions(saved['decisions'],saved['observation']))

    def owner(self,m):
        events=[]
        owner=NS(inputs=NS(profile=NS(name=m['input_profile']),checkpoint=('work/retained/checkpoint.json','a'*64)),
            backend=NS(load_abi=NS(core_sha256=m['core_sha256'])),emit=lambda stage,**data:events.append((stage,data)))
        return owner,events

    def test_actual_saved_t61_proves_nested_sequence_is_not_removed_by_legacy_comparator(self):
        m=saved_checkpoint();saved=m['decisions'];reset=reset_identity(saved)
        self.assertEqual(saved['sequence'],77)
        self.assertEqual(saved['world_congress']['sequence'],77)
        difference=checkpoint._comparison_differences(historical(saved),historical(reset))
        self.assertEqual([r['path'] for r in difference['differences']],['/world_congress/sequence'])
        self.assertEqual(checkpoint._semantic_decisions(saved,m['observation']),
                         checkpoint._semantic_decisions(reset,m['observation']))
        owner,events=self.owner(m)
        checkpoint._compare_decisions(owner,m,m['observation'],reset)
        self.assertEqual(events[-1][0],'official_lan_checkpoint_reloaded')
        self.assertTrue(events[-1][1]['identity_rebound'])

    def test_real_data_differences_still_refuse_and_emit_exact_bounded_path(self):
        m=saved_checkpoint();restored=reset_identity(m['decisions'])
        restored['world_congress']['meeting']['turns_left']=1;seal(restored)
        owner,events=self.owner(m)
        with self.assertRaisesRegex(ValueError,'public decision catalogue differs'):
            checkpoint._compare_decisions(owner,m,m['observation'],restored)
        stage,data=events[-1]
        self.assertEqual(stage,'official_lan_checkpoint_comparison_mismatch')
        self.assertEqual(data['decision_difference']['differences'],[dict(
            path='/world_congress/meeting/turns_left',expected=dict(type='int',value=0),actual=dict(type='int',value=1))])
        self.assertTrue(data['strict_comparison_retained'])
        self.assertFalse(data['full_objects_emitted'])

    def test_active_ballot_candidate_sequence_and_family_digest_are_rebound_together(self):
        previous.WorldCongressClientTests.setUpClass();fixture=previous.WorldCongressClientTests()
        saved,observation=fixture._v37();reset=reset_identity(saved,17)
        row=next(r for r in saved['candidates'] if r['action']['kind']=='congress_confirm_ballot')
        new=next(r for r in reset['candidates'] if r['action']['kind']=='congress_confirm_ballot')
        self.assertNotEqual(row['candidate_id'],new['candidate_id'])
        self.assertEqual(checkpoint._semantic_decisions(saved,observation),checkpoint._semantic_decisions(reset,observation))
        changed=deepcopy(reset);changed['world_congress']['resolutions'][0]['effect_a']='Different real effect';seal(changed)
        self.assertNotEqual(checkpoint._semantic_decisions(saved,observation),checkpoint._semantic_decisions(changed,observation))
        forged=deepcopy(reset);forged['families']['congress_confirm_ballot']['candidate_ids']=[row['candidate_id']];seal(forged)
        with self.assertRaises(ValueError):checkpoint._semantic_decisions(forged,observation)
        self.assertEqual(saved['candidates'][saved['candidates'].index(row)],row)

    def test_v38_review_observation_sequence_rebounds_but_history_and_spy_event_do_not(self):
        m=saved_checkpoint();old=m['decisions']
        review=review_catalogue(old['player_id'],old['turn'],old['sequence'],old['world_congress']['turn_segment'])
        saved=network_turn.upgrade_review_catalogue(old,review,m['observation'])
        reset=reset_identity(saved)
        self.assertEqual(checkpoint._semantic_decisions(saved,m['observation']),checkpoint._semantic_decisions(reset,m['observation']))
        changed=deepcopy(reset);changed['world_congress_review']['resolutions'][0]['name']='Different history';seal(changed)
        self.assertNotEqual(checkpoint._semantic_decisions(saved,m['observation']),checkpoint._semantic_decisions(changed,m['observation']))
        # Native completion identities are never mistaken for RPC sequence.
        fixture=dict(schema='legacy-fixture',episode_id='a',game_generation='a',sequence=9,decision_id='x',
                     candidates=[],spy_completion=dict(current=dict(event_sequence=77)))
        changed=deepcopy(fixture);changed['spy_completion']['current']['event_sequence']=0
        self.assertNotEqual(checkpoint._semantic_decisions(fixture,{}),checkpoint._semantic_decisions(changed,{}))

    def test_mismatched_nested_sequence_is_rejected_before_normalization(self):
        m=saved_checkpoint();wrong=reset_identity(m['decisions'])
        wrong['world_congress']['sequence']=77;seal(wrong)
        with self.assertRaisesRegex(ValueError,'Stale Congress catalogue sequence'):
            checkpoint._semantic_decisions(wrong,m['observation'])

    def test_historical_protocols_keep_the_exact_previous_comparator(self):
        value=dict(schema='capacity-fixture',episode_id='old',game_generation='old',sequence=4,decision_id='old',
            candidates=[dict(candidate_id='opaque',action=dict(kind='move',unit_id=1))],other_sequence=22)
        self.assertEqual(checkpoint._semantic_decisions(value,{}),historical(value))

    def test_failure_diagnostic_limits_paths_types_and_scalar_sizes(self):
        left={str(i):'x'*1000 for i in range(100)};right={str(i):i for i in range(100)}
        diff=checkpoint._comparison_differences(left,right,limit=4)
        self.assertEqual(len(diff['differences']),4)
        self.assertTrue(diff['truncated'])
        self.assertFalse(diff['full_objects_emitted'])
        self.assertEqual(len(diff['differences'][0]['expected']['value']),128)


if __name__=='__main__':unittest.main()

"""Retained native v37 envelopes with synthetic historical Review contents.

No GameCore or runtime imports. Fixtures remain private lab evidence; nothing
here claims that the new v38 native read has executed.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from civ6_host import SessionClient, InformationUnavailable
from civ6_host.client import ProtocolError
from civ6_host.contracts import information, network_turn
from test_world_congress_review_contract import catalogue
import test_world_congress_client as previous
from test_world_congress_contract import ballot_parameters


def retained(name='active'):
    root=Path(os.environ['CIV6_HOST_RESOURCE_ROOT'])/'work/trade-common-client/congress-review-staging/api/fixtures'
    proof=json.loads((root/'source.json').read_bytes())['files'][name]
    raw=(root/f'retained-v37-{name}.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=proof['sha256']: raise ValueError('Retained public fixture changed')
    return json.loads(raw)


def history(value):
    return catalogue(value['player_id'],value['turn'],value['sequence'],value['world_congress']['turn_segment'])


def validate(value,observation,closed=False):
    return network_turn.validate_capability_catalogue(value,
        NS(episode_id=value['episode_id'],game_generation=value['game_generation']),
        value['sequence'],value['turn'],player_id=value['player_id'],observation=observation,
        actions_closed=closed)


def seal(value):
    value.pop('decision_id',None);value['decision_id']=network_turn.digest(value)


class ReplayBackend:
    def __init__(self,response):
        self.response=deepcopy(response);self.calls=[];self.aborts=[]
    def reset(self): return deepcopy(self.response)
    def request(self,request):
        self.calls.append(deepcopy(request));raise AssertionError('Information must not issue RPC')
    def abort(self,reason):self.aborts.append(reason)


class ReviewClientTests(unittest.TestCase):
    def current(self):
        response=retained();old=response['decisions'];before=deepcopy(old)
        response['decisions']=network_turn.upgrade_review_catalogue(old,history(old),response['observation'])
        self.assertEqual(old,before)
        return response,old

    def test_retained_v37_projection_preserves_every_choice_and_historical_field(self):
        response,old=self.current();current=response['decisions']
        validate(current,response['observation'])
        self.assertEqual(current['candidates'],old['candidates'])
        self.assertEqual(current['families'],old['families'])
        self.assertFalse(current['complete_action_space'])
        self.assertNotEqual(current['decision_id'],old['decision_id'])
        for key in old:
            if key not in ('schema','decision_id'): self.assertEqual(current[key],old[key])
        projected,transition=network_turn.checkpoint_catalogue(current,old,response['observation'],
            core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(projected,old)
        self.assertEqual(transition['added_public_fields'],['world_congress_review','world_congress_review_status'])
        self.assertNotIn('added_action_families',transition)

    def test_session_information_is_cached_public_and_detached(self):
        response,_=self.current();backend=ReplayBackend(response);client=SessionClient(backend)
        initial=client.reset()
        info=client.information('world_congress_review')
        self.assertEqual(info['data'],response['decisions']['world_congress_review'])
        self.assertEqual(info['native_decision_id'],initial['decisions']['decision_id'])
        self.assertEqual(info['source_contracts']['world_congress_review'],'civ6-host.world-congress-review.v1')
        info['data']['resolutions'][0]['name']='External mutation'
        self.assertNotEqual(client.information('world_congress_review')['data']['resolutions'][0]['name'],'External mutation')
        self.assertFalse(backend.calls)

    def test_old_v37_information_remains_explicitly_unavailable(self):
        response=retained();backend=ReplayBackend(response);client=SessionClient(backend)
        view=client.reset();self.assertEqual(view['decisions'],response['decisions'])
        with self.assertRaises(InformationUnavailable): client.information('world_congress_review')
        self.assertFalse(backend.calls)

    def test_real_waiting_reply_and_source_ui_unavailability_are_distinct(self):
        response=retained('waiting');old=response['decisions']
        current=network_turn.upgrade_review_catalogue(old,None,response['observation'])
        validate(current,response['observation'])
        self.assertEqual(current['world_congress_review_status'],'waiting_or_closed')
        self.assertIsNone(current['world_congress_review'])
        active=retained();old=active['decisions']
        with self.assertRaisesRegex(ValueError,'explicit status'):
            network_turn.upgrade_review_catalogue(old,None)
        active['decisions']=network_turn.upgrade_review_catalogue(old,None,status='review_ui_unavailable')
        validate(active['decisions'],active['observation'])
        client=SessionClient(ReplayBackend(active));client.reset()
        with self.assertRaises(InformationUnavailable):client.information('world_congress_review')

    def test_foreign_stale_segment_hidden_fields_and_status_forgery_refused(self):
        response,old=self.current()
        for change in ('player','turn','sequence','segment','hidden','status','old_revision'):
            bad=deepcopy(response['decisions']);review=bad['world_congress_review']
            if change=='player':review['player_id']=1
            elif change=='turn':review['turn']+=1
            elif change=='sequence':review['sequence']+=1
            elif change=='segment':review['turn_segment']+=1
            elif change=='hidden':review['discussions'][0]['sender']=23
            elif change=='status':bad['world_congress_review_status']='review_ui_unavailable'
            else:bad['schema']=network_turn.CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA
            seal(bad)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(bad,response['observation'])
        bad_response=deepcopy(response);bad_response['decisions']['world_congress_review']['sequence']+=1
        seal(bad_response['decisions'])
        with self.assertRaisesRegex(ValueError,'crossed observation identity'):
            SessionClient(ReplayBackend(bad_response)).reset()

    def test_all_inherited_simple_candidate_ids_resolve_the_same_action(self):
        response,old=self.current();current=response['decisions']
        checked=0
        for row in old['candidates']:
            if row['action']['kind'] in ('policies',) or row['action']['kind'].startswith('congress_'):continue
            expected=network_turn.select_capability(old,dict(decision_id=old['decision_id'],candidate_id=row['candidate_id']))
            actual=network_turn.select_capability(current,dict(decision_id=current['decision_id'],candidate_id=row['candidate_id']))
            self.assertEqual(actual,expected);checked+=1
        self.assertGreater(checked,0)
        with self.assertRaises(ValueError):network_turn.select_capability(current,
            dict(decision_id=old['decision_id'],candidate_id=current['candidates'][0]['candidate_id']))

    def test_v38_inherits_session_readonly_and_complete_ballot_selection(self):
        previous.WorldCongressClientTests.setUpClass();fixture=previous.WorldCongressClientTests()
        old,observation=fixture._v37()
        current=network_turn.upgrade_review_catalogue(old,None,observation,status='review_ui_unavailable')
        validate(current,observation)
        for kind in network_turn.CONGRESS_READ_ONLY_KINDS:
            self.assertTrue(network_turn.congress_action_read_only(current,kind))
        self.assertEqual(current['candidates'],old['candidates'])
        candidate=next(r for r in current['candidates'] if r['action']['kind']=='congress_confirm_ballot')
        parameters=ballot_parameters(old['world_congress'])
        for value in (old,current):
            chosen=network_turn.select_capability(value,dict(decision_id=value['decision_id'],
                candidate_id=candidate['candidate_id'],parameters=parameters))
            self.assertEqual(chosen,{**candidate['action'],**parameters})
        with self.assertRaisesRegex(ValueError,'UI phase'):
            network_turn.upgrade_review_catalogue(old,history(old),observation)


if __name__=='__main__':unittest.main()

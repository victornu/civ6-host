"""Explicit v30→v31 comparison projection; fixtures are not native receipts."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import envoys, network_turn


class EnvoyCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from civ6_host.runtime.paths import resource_root
        p=resource_root()/'work/bbg751-city-controls/native/public-replay.jsonl'
        if not p.is_file():
            raise unittest.SkipTest('Private public-v30 receipt required')
        if sha256(p.read_bytes()).hexdigest()!='5220947cf214c1c5a9a897749701ffe35843b6241557dde12d6cdd8a01c48e65':
            raise ValueError('Retained v30 exchange changed')
        cls.old=json.loads(p.read_bytes().splitlines()[0])['view']

    def fixture(self):
        value=deepcopy(self.old['decisions'])
        value['schema']=network_turn.CAPABILITY_XP2_ENVOYS_SCHEMA
        value['envoys']=dict(player_id=value['player_id'],current_game_turn=value['turn'],
            tokens_to_give=3,can_give_influence=True,considered=False,
            giving_tokens_blocker_present=True,
            targets=[dict(target_player_id=19,can_give=True,tokens_received=2)])
        for kind in ('send_envoy','retain_envoys'):
            rows=[dict(action=a,candidate_id=network_turn.digest(a)) for a in envoys.actions(value['envoys'])
                  if a['kind']==kind]
            value['candidates'].extend(rows)
            value['families'][kind]=dict(status='queried_complete',candidate_ids=[r['candidate_id'] for r in rows])
        value.pop('decision_id');value['decision_id']=network_turn.digest(value)
        observation=deepcopy(self.old['observation'])
        from civ6_host.contracts.player_display import RAW_OBSERVATION_SCHEMA
        observation['schema']=RAW_OBSERVATION_SCHEMA
        return value,observation

    def test_new_family_projection_preserves_the_exact_historical_catalogue(self):
        current,observation=self.fixture()
        projected,receipt=network_turn.checkpoint_catalogue(current,self.old['decisions'],observation,
            core_sha256='324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c')
        self.assertEqual(projected,self.old['decisions'])
        self.assertEqual(receipt['added_action_families'],['send_envoy','retain_envoys'])
        self.assertEqual(receipt['added_public_fields'],['envoys'])
        self.assertIn('envoys',current)
        self.assertNotIn('envoys',self.old['decisions'])

    def test_preexisting_data_cannot_be_removed_by_an_envoy_projection(self):
        current,observation=self.fixture()
        item=current['production_current']['cities'][0]['item']
        self.assertIsNotNone(item)
        item['turns_left']+=1
        current.pop('decision_id');current['decision_id']=network_turn.digest(current)
        projected,_=network_turn.checkpoint_catalogue(current,self.old['decisions'],observation,
            core_sha256='324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c')
        self.assertNotEqual(projected,self.old['decisions'])
        self.assertEqual(projected['production_current'],current['production_current'])


if __name__=='__main__':
    unittest.main()

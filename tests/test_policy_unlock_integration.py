"""Contract migration fixture using a retained v25 public response."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import network_turn as contract, policy_unlock
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root


class PolicyUnlockCatalogueTests(unittest.TestCase):
    def test_v26_preserves_v25_and_exposes_only_the_queried_unlock(self):
        path = resource_root()/'work/bbg751-policies-resume/public-replay.jsonl'
        if not path.is_file():
            self.skipTest('Private retained v25 public trace required')
        before = json.loads(path.read_bytes().splitlines()[0])['view']
        saved = deepcopy(before['decisions'])
        self.assertEqual(saved['schema'], contract.CAPABILITY_XP2_POLICIES_SCHEMA)
        # Synthetic paid window on the retained layout, not a native result.
        saved['policies']['reason'] = 'not_free'
        for slot in saved['policies']['slots']:
            slot['options'] = []
        saved['candidates'] = [row for row in saved['candidates'] if row['action']['kind'] != 'policies']
        saved['families']['policies']['candidate_ids'] = []
        del saved['decision_id']
        saved['decision_id'] = contract.digest(saved)
        current = deepcopy(saved)
        current['schema'] = contract.CAPABILITY_XP2_POLICY_UNLOCK_SCHEMA
        current['policy_unlock'] = dict(player_id=0, turn=21, cost=25, currency='YIELD_GOLD',
                                        reason='available', can_unlock=True)
        (action,) = policy_unlock.actions(current['policy_unlock'])
        candidate = dict(candidate_id=contract.digest(action), action=action)
        current['candidates'].append(candidate)
        current['families']['policy_unlock'] = dict(status='queried_complete',
            candidate_ids=[candidate['candidate_id']])
        current['families']['policies']['unqualified'] = ['active_policy_relocation']
        del current['decision_id']
        current['decision_id'] = contract.digest(current)
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        contract.validate_capability_catalogue(current, identity, 0, 21,
            player_id=0, observation=before['observation'])
        self.assertEqual(contract.select_capability(current, dict(decision_id=current['decision_id'],
                         candidate_id=candidate['candidate_id'])), action)
        projected, transition = contract.checkpoint_catalogue(current, saved, before['observation'],
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['added_public_fields'], ['policy_unlock'])
        self.assertEqual(transition['added_action_families'], ['policy_unlock'])

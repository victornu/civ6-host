from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import government, network_turn
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root


class GovernmentCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = resource_root() / 'work' / 'bbg751-policy-unlock' / 'public-replay.jsonl'
        if not path.is_file():
            raise unittest.SkipTest('Retained v26 public replay required')
        cls.view = json.loads(path.read_text(encoding='utf-8').splitlines()[0])['view']
        cls.saved = deepcopy(cls.view['decisions'])
        cls.observation = cls.view['observation']
        cls.identity = SimpleNamespace(episode_id=cls.saved['episode_id'],
                                       game_generation=cls.saved['game_generation'])

    def government_catalogue(self):
        return dict(player_id=self.saved['player_id'], turn=self.saved['turn'],
            current_index=5, can_change=True, changed=False, civic_completed=True,
            considered=False, consideration_blocker=True,
            choices=[
                dict(index=5, hash=505, unlocked=True, can_change=True, anarchy_turns=0),
                dict(index=8, hash=808, unlocked=True, can_change=True, anarchy_turns=0),
                dict(index=10, hash=1010, unlocked=True, can_change=True, anarchy_turns=2),
                dict(index=12, hash=1212, unlocked=False, can_change=True, anarchy_turns=0),
            ])

    def v27(self):
        value = deepcopy(self.saved)
        value['schema'] = network_turn.CAPABILITY_XP2_GOVERNMENT_SCHEMA
        value['government'] = self.government_catalogue()
        actions = government.actions(value['government'])
        for action in actions:
            value['candidates'].append(dict(candidate_id=network_turn.digest(action), action=action))
        value['families']['government'] = dict(status='queried_partial',
            candidate_ids=[network_turn.digest(action) for action in actions],
            unqualified=['anarchy_transition'])
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)
        return value, actions

    def validate(self, value):
        network_turn.validate_capability_catalogue(value, self.identity, value['sequence'],
            value['turn'], player_id=value['player_id'], observation=self.observation)

    def test_retained_v26_view_validates_as_v27_and_projects_back(self):
        self.validate(self.saved)
        current, actions = self.v27()
        self.assertEqual(actions, [
            dict(kind='government', index=8, hash=808),
            dict(kind='retain_government', index=5),
        ])
        self.validate(current)
        projected, transition = network_turn.checkpoint_catalogue(
            current, self.saved, self.observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, self.saved)
        self.assertEqual(transition['source_schema'], self.saved['schema'])
        self.assertEqual(transition['target_schema'], current['schema'])
        self.assertEqual(transition['added_public_fields'], ['government'])
        self.assertEqual(transition['added_action_families'], ['government', 'retain_government'])

    def test_catalogue_requires_exact_fields_types_and_current_choice(self):
        valid = self.government_catalogue()
        government.validate_catalogue(valid, valid['player_id'], valid['turn'])
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            government.validate_catalogue(valid, 1, valid['turn'])
        invalids = []
        bad = deepcopy(valid); bad['extra'] = True; invalids.append(bad)
        bad = deepcopy(valid); bad['changed'] = 1; invalids.append(bad)
        bad = deepcopy(valid); bad['choices'][1]['extra'] = 0; invalids.append(bad)
        bad = deepcopy(valid); bad['choices'][1]['index'] = 5; invalids.append(bad)
        bad = deepcopy(valid); bad['choices'][1]['hash'] = 505; invalids.append(bad)
        bad = deepcopy(valid); bad['current_index'] = 4; invalids.append(bad)
        bad = deepcopy(valid); bad['choices'][0]['anarchy_turns'] = 100001; invalids.append(bad)
        for bad in invalids:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                government.validate_catalogue(bad, valid['player_id'], valid['turn'])

    def test_candidate_crosscheck_rejects_mismatch_and_waiting_keeps_old_shape(self):
        current, actions = self.v27()
        self.validate(current)
        bad = deepcopy(current)
        bad['government']['choices'][1]['unlocked'] = False
        bad.pop('decision_id', None); bad['decision_id'] = network_turn.digest(bad)
        with self.assertRaisesRegex(ValueError, 'Government candidates differ'):
            self.validate(bad)
        self.assertNotIn('government', self.saved)
        self.assertEqual(self.saved['schema'], network_turn.CAPABILITY_XP2_POLICY_UNLOCK_SCHEMA)

    def test_direct_choices_require_native_predicates_and_zero_anarchy(self):
        value = self.government_catalogue()
        self.assertEqual(government.actions(value), [
            dict(kind='government', index=8, hash=808),
            dict(kind='retain_government', index=5),
        ])
        value['changed'] = True
        self.assertEqual(government.actions(value), [dict(kind='retain_government', index=5)])
        value['changed'] = False; value['civic_completed'] = False
        self.assertEqual(government.actions(value), [dict(kind='retain_government', index=5)])
        value['considered'] = True
        self.assertEqual(government.actions(value), [])


if __name__ == '__main__':
    unittest.main()

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import network_turn


class PromotionCatalogueTests(unittest.TestCase):
    def setUp(self):
        from civ6_host.runtime.paths import resource_root

        path = resource_root() / ('work/xp2-client-sessions/'
            'run-697aab565fa04308b2292bcd12ee016c/checkpoint/checkpoint.json')
        if not path.is_file():
            self.skipTest('Retained private XP2 v21 witness required')
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         '16709c6dd5b099722cba43a827717084a424b36c7a067fe15d205c48fcd08214')
        checkpoint = json.loads(raw)
        self.saved = checkpoint['decisions']
        self.observation = checkpoint['observation']
        self.live = deepcopy(self.saved)
        self.live['schema'] = network_turn.CAPABILITY_XP2_PROMOTION_SCHEMA
        units = sorted(self.observation['units'], key=lambda unit: unit['id'])
        self.action = dict(kind='promote_unit', unit_id=units[0]['id'], index=7,
                           hash=3461640876, item_type='PROMOTION_BATTLECRY')
        self.live['unit_promotions'] = dict(player_id=self.live['player_id'], turn=self.live['turn'],
            units=[dict(unit_id=unit['id'], experience_points=15 if i == 0 else 0, promotions=[])
                   for i, unit in enumerate(units)], offers=[self.action])
        key = network_turn.digest(self.action)
        self.live['candidates'].append(dict(candidate_id=key, action=self.action))
        self.live['families']['promote_unit'] = dict(status='queried_complete', candidate_ids=[key])

    def validate(self, value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)
        identity = SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation'])
        network_turn.validate_capability_catalogue(value, identity, value['sequence'],
            value['turn'], player_id=value['player_id'], observation=self.observation)

    def test_v22_checkpoint_comparison_preserves_every_v21_field(self):
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        self.validate(self.live)
        before = deepcopy(self.live)
        projected, transition = network_turn.checkpoint_catalogue(
            self.live, self.saved, self.observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, self.saved)
        self.assertEqual(transition['added_action_families'], ['promote_unit'])
        self.assertEqual(self.live, before)

    def test_promotion_candidate_must_match_the_current_own_unit_offer(self):
        invalid = deepcopy(self.live)
        invalid['unit_promotions']['offers'] = []
        with self.assertRaisesRegex(ValueError, 'differ from their native catalogue'):
            self.validate(invalid)
        invalid = deepcopy(self.live)
        invalid['unit_promotions']['units'][0]['promotions'] = [self.action['index']]
        with self.assertRaisesRegex(ValueError, 'acquired promotion offer'):
            self.validate(invalid)
        invalid = deepcopy(self.live)
        invalid['unit_promotions']['units'].pop()
        with self.assertRaisesRegex(ValueError, 'own-unit observation'):
            self.validate(invalid)

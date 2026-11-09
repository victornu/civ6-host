"""Portable envoy catalogue/choice checks, without native data or rules."""
from copy import deepcopy
import unittest

from civ6_host.contracts import envoys


class EnvoyContractTests(unittest.TestCase):
    def catalogue(self):
        return dict(player_id=0, current_game_turn=20, tokens_to_give=3,
                    can_give_influence=True, considered=False,
                    giving_tokens_blocker_present=True,
                    targets=[dict(target_player_id=19, can_give=True, tokens_received=2),
                             dict(target_player_id=17, can_give=False, tokens_received=1),
                             dict(target_player_id=22, can_give=True, tokens_received=5)])

    def test_all_native_available_targets_and_retention_preserve_order(self):
        catalogue = self.catalogue()
        before = deepcopy(catalogue)
        envoys.validate_catalogue(catalogue, 0, 20)
        self.assertEqual(envoys.actions(catalogue), [dict(kind='send_envoy',target_player_id=19),
            dict(kind='send_envoy',target_player_id=22),dict(kind='retain_envoys')])
        self.assertEqual(catalogue, before)

    def test_global_native_gate_and_tokens_are_not_inferred_from_targets(self):
        for change in (dict(can_give_influence=False),dict(tokens_to_give=0)):
            catalogue = dict(self.catalogue(), **change)
            self.assertEqual(envoys.actions(catalogue), [dict(kind='retain_envoys')])
        for change in (dict(considered=True),dict(giving_tokens_blocker_present=False)):
            catalogue = dict(self.catalogue(), **change)
            self.assertEqual([a['kind'] for a in envoys.actions(catalogue)], ['send_envoy','send_envoy'])
        self.assertEqual(envoys.actions(None), [])

    def test_duplicate_foreign_and_malformed_targets_refused(self):
        for field, value in (('player_id', True),('current_game_turn',19),
                             ('tokens_to_give',True),('considered',1)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                envoys.validate_catalogue(dict(self.catalogue(), **{field:value}),0,20)
        for target in (dict(target_player_id=19,can_give=True,tokens_received=2),
                       dict(target_player_id=0,can_give=True,tokens_received=2),
                       dict(target_player_id=23,can_give=1,tokens_received=2)):
            catalogue=self.catalogue(); catalogue['targets'].append(target)
            with self.assertRaises(ValueError):
                envoys.validate_catalogue(catalogue,0,20)

    def test_action_shapes_are_exact(self):
        for action in (dict(kind='send_envoy',target_player_id=19),dict(kind='retain_envoys')):
            self.assertEqual(envoys.validate_action(action),action)
        for action in (dict(kind='send_envoy',target_player_id=True),dict(kind='send_envoy',target_player_id=64),
                       dict(kind='retain_envoys',target_player_id=19),dict(kind='send_envoy')):
            with self.assertRaises(ValueError):
                envoys.validate_action(action)


if __name__ == '__main__':
    unittest.main()

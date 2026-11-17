"""Software tests over preserved native XP2 catalogues, with test levy rows."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import city_state_levies as levy, information, network_turn
from civ6_host.runtime.network_checkpoint import _semantic_decisions
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256


FIXTURES = (
    ('work/host-simultaneous/native-runs/run-a33e6e03fff4461ca5217c907acb0668/checkpoint/checkpoint.json',
     '270bdaf9f3f6b01157354fc7bd1f01c6bc58b0c68fc95f283eaa05c40a34180e'),
    ('work/x2pv10/run-d14c7e50abc14665bc5c13993dbdb7fe/checkpoint/checkpoint.json',
     '35ffd487b1fa3a37d0348add596327848832772763347a64bfcfa2937be74627'),
    ('work/x2stockocc/run-1f3192b6cf8a4f4f96b02a1d4724d1c9/checkpoint/checkpoint.json',
     '8c81bcf91764bbd31f9991df092c1d62b2a7c47ef7962c8da2285b236d58287a'),
)


class XP2MilitaryLevyCatalogueTests(unittest.TestCase):
    def load(self, ref):
        name, digest = ref
        path = resource_root() / name
        self.assertLess(path.stat().st_size, 1024**2)
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), digest)
        data = json.loads(raw)
        return data['decisions'], data['observation']

    def added(self, old, observation, *, extra_target=None, flags=()):
        player, turn = observation['player_id'], observation['turn']
        targets = [row['target_player_id'] for row in old['envoys']['targets']]
        if extra_target is not None:
            targets = sorted((*targets, extra_target))
        catalogue = dict(schema=levy.SCHEMA, player_id=player, turn=turn, military_enabled=True,
            city_states=[dict(player_id=target, can_levy=target == targets[0], gold_cost=100,
                              turn_limit=30, own_levy_active=False) for target in targets])
        unit_flags = dict(schema=levy.UNIT_SCHEMA, player_id=player, turn=turn, units=list(flags))
        current = deepcopy(old)
        network_turn.add_xp2_levies(current, catalogue, unit_flags)
        self.seal(current)
        return current

    def seal(self, decisions):
        decisions.pop('decision_id')
        decisions['decision_id'] = network_turn.digest(decisions)

    def validate(self, decisions, observation):
        identity = SimpleNamespace(episode_id=decisions['episode_id'],
                                   game_generation=decisions['game_generation'])
        return network_turn.validate_capability_catalogue(
            decisions, identity, decisions['sequence'], observation['turn'],
            player_id=observation['player_id'], observation=observation)

    def test_each_xp2_branch_preserves_its_catalogue_and_save_comparison(self):
        for ref in FIXTURES:
            with self.subTest(path=ref[0]):
                old, observation = self.load(ref)
                current = self.added(old, observation)
                self.validate(current, observation)
                self.assertIn(current['schema'], network_turn.ATTACK_CAPABILITY_SCHEMAS)
                self.assertEqual(network_turn.xp2_levy_base_schema(current['schema']), old['schema'])
                projection, change = network_turn.checkpoint_catalogue(
                    current, old, observation, core_sha256=XP2_CORE_SHA256)
                self.assertEqual(projection, old)
                self.assertEqual(change['added_public_fields'], ['city_state_levies', 'unit_levies'])
                self.assertEqual(change['added_action_families'], [levy.ACTION])
                exact, change = network_turn.checkpoint_catalogue(
                    current, current, observation, core_sha256=XP2_CORE_SHA256)
                self.assertEqual(exact, current)
                self.assertIsNone(change)
                semantic = _semantic_decisions(current, observation)
                if semantic.get('native_command_permissions') is not None:
                    self.assertEqual(semantic['native_command_permissions']['sequence'], 0)
                if semantic.get('trade_overview') is not None:
                    self.assertEqual(semantic['trade_overview']['sequence'], 0)
                self.assertEqual(information.project('city_state_levies', observation, current),
                                 current['city_state_levies'])
                self.assertEqual(information.project('unit_levies', observation, current),
                                 current['unit_levies'])
                with self.assertRaisesRegex(ValueError, 'exact engine'):
                    network_turn.checkpoint_catalogue(current, old, observation, core_sha256=None)

    def test_rejects_hidden_units_and_unmet_city_states(self):
        old, observation = self.load(FIXTURES[0])
        self.assertNotIn(63, [row['target_player_id'] for row in old['envoys']['targets']])
        with self.assertRaisesRegex(ValueError, 'met city-states'):
            self.validate(self.added(old, observation, extra_target=63), observation)
        hidden = dict(owner=63, unit_id=0xffffffff, original_owner=2, turns_remaining=12)
        with self.assertRaisesRegex(ValueError, 'outside the public roster'):
            self.validate(self.added(old, observation, flags=(hidden,)), observation)

    def test_strategic_permission_does_not_replace_the_native_levy_predicate(self):
        old, observation = self.load(FIXTURES[1])
        current = self.added(old, observation)
        current['native_command_permissions']['allow_strategic'] = False
        self.assertFalse(network_turn.family_query_unavailable(current, levy.ACTION))
        self.assertTrue(network_turn.family_query_unavailable(current, 'send_envoy'))
        self.assertFalse(network_turn.is_waiting(current['turn_controls']))
        self.assertEqual(information.project('unit_levies', observation, current),
                         current['unit_levies'])


if __name__ == '__main__':
    unittest.main()

"""Protocol v32 governor-family integration; all v32 additions are synthetic."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import governors, network_turn


XP2_CORE = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'


class GovernorCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the retained, genuinely native v31 replay for active, waiting,
        # and closed bases. Only the added governor field/families below are
        # synthetic; this is not a native governor receipt.
        from civ6_host.runtime.paths import resource_root
        path = resource_root() / 'work/bbg751-envoys/earned-envoy-fixed/public-replay.jsonl'
        raw = path.read_bytes()
        if (len(raw) != 674560
                or sha256(raw).hexdigest() != 'd3c1f79033315379a5c21fddf1bab9c3b22957ae2ffb064ce15b50ea02c4487f'):
            raise ValueError('Retained native v31 envoy replay changed')
        cls.native_rows = [json.loads(line) for line in raw.splitlines() if line]
        cls.native_views = {row['operation']: row['view'] for row in cls.native_rows
                            if row['operation'] in ('reset', 'close')}
        cls.native_views['waiting'] = next(
            row['view'] for row in cls.native_rows
            if row['operation'] == 'poll'
            and row['view']['decisions']['turn_controls']['active'] is False)

    def _base(self, state='reset'):
        view = deepcopy(self.native_views[state])
        observation = view['observation']
        from civ6_host.contracts.player_display import RAW_OBSERVATION_SCHEMA
        observation['schema'] = RAW_OBSERVATION_SCHEMA
        return deepcopy(view['decisions']), observation

    def v31(self):
        return self._base('reset')

    def governor_catalogue(self, player_id, turn):
        return dict(
            player_id=player_id, current_game_turn=turn,
            points_obtained=-2, points_spent=7, can_appoint=True,
            titles_considered=False,
            governors=[
                dict(index=2, hash=0x10203040, appointed=False,
                     can_ever_appoint=True, can_promote=False,
                     assignment_open=False, turns_to_establish=4,
                     status=None, promotions=[], assignment_targets=[]),
                dict(index=6, hash=0x50607080, appointed=True,
                     can_ever_appoint=False, can_promote=False,
                     assignment_open=True, turns_to_establish=5,
                     status=dict(neutralized_turns=0, established=False,
                                 turns_to_establish=5, turns_on_site=1,
                                 assigned_city=dict(owner=player_id, city_id=21),
                                 govern_city_state=True,
                                 can_assign_to_major_civ=False),
                     promotions=[dict(index=8, hash=0xffffffff, owned=False,
                                      can_earn=True, hidden=True,
                                      base_ability=False, level=2)],
                     assignment_targets=[dict(owner=player_id, city_id=22,
                                              can_assign=True)]),
            ],
        )

    def v32(self, state='reset', *, available=True):
        value, observation = self._base(state)
        before_value, before_observation = deepcopy(value), deepcopy(observation)
        value['schema'] = network_turn.CAPABILITY_XP2_GOVERNORS_SCHEMA
        catalogue = (self.governor_catalogue(value['player_id'], value['turn'])
                     if available else None)
        value['governors'] = catalogue
        governor_actions = [] if catalogue is None else governors.actions(catalogue)
        for kind in governors.ACTION_FIELDS:
            rows = [dict(action=action, candidate_id=network_turn.digest(action))
                    for action in governor_actions if action['kind'] == kind]
            if available:
                value['candidates'].extend(rows)
                value['families'][kind] = dict(
                    status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
            else:
                value['families'][kind] = dict(
                    status='unqualified', reason='native_query_unavailable')
        value.pop('decision_id')
        value['decision_id'] = network_turn.digest(value)
        self.assertEqual((before_value, before_observation), self._base(state))
        return value, observation, before_value

    def validate(self, value, observation, *, actions_closed=False):
        identity = SimpleNamespace(episode_id=value['episode_id'],
                                   game_generation=value['game_generation'])
        return network_turn.validate_capability_catalogue(
            value, identity, value['sequence'], value['turn'],
            player_id=value['player_id'], actions_closed=actions_closed,
            observation=observation)

    def test_v31_still_valid_without_governors_and_v32_requires_active_query(self):
        value, observation = self.v31()
        self.assertEqual(value['schema'], network_turn.CAPABILITY_XP2_ENVOYS_SCHEMA)
        self.assertNotIn('governors', value)
        self.validate(value, observation)

        current, current_observation, _ = self.v32()
        current['governors'] = None
        current.pop('decision_id')
        current['decision_id'] = network_turn.digest(current)
        with self.assertRaises(ValueError):
            self.validate(current, current_observation)

    def test_v32_active_catalogue_requires_four_completed_families_and_exact_candidates(self):
        value, observation, old_value = self.v32()
        self.validate(value, observation)
        expected = governors.actions(value['governors'])
        offered = [row['action'] for row in value['candidates']
                   if row['action']['kind'] in governors.ACTION_FIELDS]
        self.assertEqual(offered, expected)
        self.assertEqual(set(governors.ACTION_FIELDS), {
            'appoint_governor', 'promote_governor',
            'assign_governor', 'consider_governor_titles',
        })
        for kind in governors.ACTION_FIELDS:
            family = value['families'][kind]
            rows = [row for row in value['candidates'] if row['action']['kind'] == kind]
            self.assertEqual(family['status'], 'queried_complete')
            self.assertEqual(family['candidate_ids'], [row['candidate_id'] for row in rows])
            self.assertEqual([row['candidate_id'] for row in rows],
                             [network_turn.digest(row['action']) for row in rows])
        promote = next(action for action in expected if action['kind'] == 'promote_governor')
        self.assertEqual(promote['promotion_hash'], 0xffffffff)
        self.assertTrue(value['governors']['governors'][1]['promotions'][0]['hidden'])
        self.assertFalse(value['governors']['governors'][1]['can_promote'])
        self.assertEqual(value['governors']['points_obtained'], -2)
        self.assertNotIn('governors', old_value)

    def test_candidate_digest_family_and_query_provenance_are_enforced(self):
        value, observation, _ = self.v32()
        mutations = (
            lambda v: v['governors'].update(current_game_turn=v['turn'] + 1),
            lambda v: v['families']['promote_governor'].update(candidate_ids=[]),
            lambda v: v['governors']['governors'][1].update(hash=0x50607081),
        )
        bad = deepcopy(value)
        bad['candidates'][-1]['candidate_id'] = '0' * 64
        bad.pop('decision_id')
        bad['decision_id'] = network_turn.digest(bad)
        with self.assertRaises(ValueError):
            self.validate(bad, observation)
        for mutate in mutations:
            bad = deepcopy(value)
            mutate(bad)
            bad.pop('decision_id')
            bad['decision_id'] = network_turn.digest(bad)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.validate(bad, observation)

    def test_waiting_and_closed_v32_keep_governor_query_unknown(self):
        waiting, observation, _ = self.v32('waiting', available=False)
        self.assertIsNone(waiting['governors'])
        self.validate(waiting, observation)
        self.assertTrue(all(waiting['families'][kind]['status'] == 'unqualified'
                            for kind in governors.ACTION_FIELDS))

        closed, observation, _ = self.v32('close', available=False)
        self.assertIsNone(closed['governors'])
        self.validate(closed, observation, actions_closed=True)
        self.assertTrue(all(closed['families'][kind]['status'] == 'unqualified'
                            for kind in governors.ACTION_FIELDS))

    def test_checkpoint_v32_to_v31_removes_only_governor_additions(self):
        current, observation, _ = self.v32()
        saved, _ = self.v31()
        original_current, original_saved = deepcopy(current), deepcopy(saved)
        projected, receipt = network_turn.checkpoint_catalogue(
            current, saved, observation, core_sha256=XP2_CORE)
        self.assertEqual(projected, saved)
        self.assertEqual(receipt['source_schema'], saved['schema'])
        self.assertEqual(receipt['target_schema'], network_turn.CAPABILITY_XP2_GOVERNORS_SCHEMA)
        self.assertEqual(receipt['added_public_fields'], ['governors'])
        self.assertEqual(receipt['added_action_families'], list(governors.ACTION_FIELDS))
        self.assertEqual(current, original_current)
        self.assertEqual(saved, original_saved)

    def test_checkpoint_transition_refuses_wrong_core(self):
        current, observation, _ = self.v32()
        saved, _ = self.v31()
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(
                current, saved, observation, core_sha256='0' * 64)


if __name__ == '__main__':
    unittest.main()

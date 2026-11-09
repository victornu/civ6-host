from copy import deepcopy
import unittest
from types import SimpleNamespace
import json

from civ6_host.contracts import capability_policies, network_turn, policies
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root


def slot(slot_id, prior, options):
    return dict(slot=slot_id, prior_index=prior, options=[
        dict(index=index, hash=policy_hash, native_hash=policy_hash,
             policy_type=f'POLICY_TEST_{index}')
        for index, policy_hash in options])


class CapabilityPolicyTests(unittest.TestCase):
    def test_changed_matching_agrees_with_exhaustive_small_graphs(self):
        from itertools import permutations
        from civ6_host.contracts import policies

        # An independent bounded oracle covers dead ends and alternating cycles
        # without duplicating the implementation's matching algorithm.
        choices = list(permutations(range(4), 3))
        for graph in range(1 << 12):
            slots = [slot(i, i, [(j, 100+j) for j in range(4)
                                if graph & (1 << (4*i+j))]) for i in range(3)]
            expected = any(candidate != (0, 1, 2) and all(
                graph & (1 << (4*i+policy)) for i, policy in enumerate(candidate))
                for candidate in choices)
            self.assertEqual(policies.can_change(slots, allow_relocation=True), expected, graph)

    def test_bbg_policy_identifiers_are_valid_without_the_base_prefix(self):
        slots = [slot(0, -1, [(2, 102)])]
        slots[0]['options'][0]['policy_type'] = 'BBG_MODERN_DRILL'
        catalogue = dict(player_id=0, turn=7, reason='available', slots=slots)
        capability_policies.validate_catalogue(catalogue, 0, 7)
        self.assertEqual(capability_policies.actions(catalogue), [dict(kind='policies', slots=slots)])
        slots[0]['options'][0]['policy_type'] = 'BBG_BAD:POLICY'
        with self.assertRaises(ValueError):
            capability_policies.validate_catalogue(catalogue, 0, 7)

    def setUp(self):
        self.slots = [slot(0, 0, [(0, 100), (2, 102)]),
                      slot(1, 1, [(1, 101), (3, 103)])]
        self.catalogue = dict(player_id=0, turn=7, reason='available', slots=self.slots)

    def test_candidate_is_one_factorized_action_only_when_changed_assignment_exists(self):
        capability_policies.validate_catalogue(self.catalogue, 0, 7)
        self.assertEqual(capability_policies.actions(self.catalogue),
                         [dict(kind='policies', slots=self.slots)])
        unchanged = dict(player_id=0, turn=7, reason='available', slots=[
            slot(0, 0, [(0, 100)]), slot(1, 1, [(1, 101)])])
        self.assertEqual(capability_policies.actions(unchanged), [])

    def test_selection_resolves_explicit_assignment_without_enumerating_choices(self):
        action = dict(kind='policies', slots=self.slots)
        value = dict(schema=network_turn.CAPABILITY_XP2_POLICIES_SCHEMA,
                     decision_id='decision', player_id=0, turn=7,
                     candidates=[dict(candidate_id=network_turn.digest(action), action=action)])
        selected = network_turn.select_capability(value, dict(
            decision_id='decision', candidate_id=network_turn.digest(action),
            parameters=dict(assignments=[102, 103])))
        expected = dict(kind='policies', candidate=dict(status='candidate', player_id=0,
            turn=7, slot_count=2, assignments=[[0, 102], [1, 103]], prior_indices=[0, 1]))
        self.assertEqual(selected, expected)
        self.assertEqual(capability_policies.validate_explicit_action(selected, 0, 7), expected)

    def test_parameters_are_exact_and_policy_assignments_must_be_complete(self):
        action = dict(kind='policies', slots=self.slots)
        value = dict(schema=network_turn.CAPABILITY_XP2_POLICIES_SCHEMA,
                     decision_id='decision', player_id=0, turn=7,
                     candidates=[dict(candidate_id=network_turn.digest(action), action=action)])
        request = dict(decision_id='decision', candidate_id=network_turn.digest(action),
                       parameters=dict(assignments=[102, 103], extra=True))
        with self.assertRaises(ValueError):
            network_turn.select_capability(value, request)
        request['parameters'] = dict(assignments=[102])
        with self.assertRaises(ValueError):
            network_turn.select_capability(value, request)

    def test_catalogue_rejects_inconsistent_closed_reason_or_boundary(self):
        bad = deepcopy(self.catalogue)
        bad['reason'] = 'window_closed'
        with self.assertRaisesRegex(ValueError, 'contradicts'):
            capability_policies.validate_catalogue(bad, 0, 7)
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            capability_policies.validate_catalogue(self.catalogue, 1, 7)

    def test_retained_reset_v24_shape_validates_as_v25_and_projects_back(self):
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.paths import resource_root

        path = (resource_root() / 'work' / 'bbg751-reg' / 'runs' /
                'run-b07614bf742f4b379b28bacffe7795bd' / 'events.jsonl')
        if not path.is_file():
            self.skipTest('Retained public reset replay required')
        response = None
        for line in path.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            decisions = record.get('decisions')
            if (record.get('stage') == 'official_session_response'
                    and record.get('operation') == 'reset'
                    and type(decisions) is dict
                    and decisions.get('schema') == network_turn.CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA):
                response = record
                break
        if response is None:
            self.skipTest('Retained replay has no v24 public reset response')

        saved = deepcopy(response['decisions'])
        observation = response['observation']
        current = deepcopy(saved)
        current['schema'] = network_turn.CAPABILITY_XP2_POLICIES_SCHEMA
        # Synthetic catalog values exercise the v25 contract on the retained
        # public v24 reset shape; no native policy result is claimed here.
        synthetic_slots = [slot(0, -1, [(2, 102), (3, 103)])]
        current['policies'] = dict(player_id=current['player_id'], turn=current['turn'],
                                   reason='available', slots=synthetic_slots)
        action = dict(kind='policies', slots=synthetic_slots)
        candidate_id = network_turn.digest(action)
        current['candidates'].append(dict(candidate_id=candidate_id, action=action))
        current['families']['policies'] = dict(status='queried_partial',
            candidate_ids=[candidate_id],
            unqualified=['paid_policy_unlock', 'active_policy_relocation'])
        current.pop('decision_id', None)
        current['decision_id'] = network_turn.digest(current)
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'],
            observation['turn'], player_id=observation['player_id'], observation=observation)
        projected, transition = network_turn.checkpoint_catalogue(
            current, saved, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['source_schema'], saved['schema'])
        self.assertEqual(transition['target_schema'], current['schema'])
        self.assertEqual(transition['added_public_fields'], ['policies'])
        self.assertEqual(transition['added_action_families'], ['policies'])

    def test_two_active_cards_can_swap_only_under_relocation_opt_in(self):
        slots = [slot(0, 0, [(0, 100), (1, 101), (2, 102)]),
                 slot(1, 2, [(0, 100), (2, 102)])]
        with self.assertRaisesRegex(ValueError, 'relocation'):
            policies.validate_slots(slots)
        with self.assertRaisesRegex(ValueError, 'relocation'):
            policies.choose(slots, [102, 100], 0, 9)

        policies.validate_slots(slots, allow_relocation=True)
        choice = policies.choose(slots, [102, 100], 0, 9, allow_relocation=True)
        self.assertEqual(choice['assignments'], [[0, 102], [1, 100]])
        self.assertEqual(choice['prior_indices'], [0, 2])
        action = dict(kind='policies', candidate=choice)
        self.assertEqual(capability_policies.validate_explicit_action(action, 0, 9), action)
        for invalid_prior in ([0, 0], [-1, -1], [0]):
            invalid = deepcopy(action)
            invalid['candidate']['prior_indices'] = invalid_prior
            with self.subTest(prior=invalid_prior), self.assertRaises(ValueError):
                capability_policies.validate_explicit_action(invalid, 0, 9)
        with self.assertRaises(policies.PolicyAssignmentUnavailable):
            policies.choose(slots, [100, 100], 0, 9, allow_relocation=True)
        with self.assertRaises(policies.PolicyAssignmentUnavailable):
            policies.choose(slots, [100, 102], 0, 9, allow_relocation=True)
        offered = dict(kind='policies', slots=slots)
        candidate_id = network_turn.digest(offered)
        selection = dict(decision_id='decision', candidate_id=candidate_id,
                         parameters=dict(assignments=[102, 100]))
        old = dict(schema=network_turn.CAPABILITY_XP2_GOVERNMENT_SCHEMA,
                   decision_id='decision', player_id=0, turn=9,
                   candidates=[dict(candidate_id=candidate_id, action=offered)])
        with self.assertRaises(ValueError):
            network_turn.select_capability(old, selection)
        new = dict(old, schema=network_turn.CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA)
        self.assertEqual(network_turn.select_capability(new, selection)['candidate']['prior_indices'],
                         [0, 2])

    def test_changed_matching_rejects_dead_end_and_accepts_cycles_or_unmatched_choices(self):
        dead_end = [slot(0, 0, [(0, 100)]),
                    slot(1, 1, [(0, 100), (1, 101)])]
        self.assertFalse(policies.can_change(dead_end, allow_relocation=True))

        two_card_cycle = [slot(0, 0, [(0, 100), (1, 101)]),
                          slot(1, 1, [(0, 100), (1, 101)])]
        self.assertTrue(policies.can_change(two_card_cycle, allow_relocation=True))

        three_card_cycle = [slot(0, 0, [(0, 100), (2, 102)]),
                            slot(1, 1, [(0, 100), (1, 101)]),
                            slot(2, 2, [(1, 101), (2, 102)])]
        self.assertTrue(policies.can_change(three_card_cycle, allow_relocation=True))

        unmatched_option = [slot(0, 0, [(0, 100), (1, 101)])]
        self.assertTrue(policies.can_change(unmatched_option, allow_relocation=True))

        self.assertFalse(policies.can_change([], allow_relocation=True))
        no_complete_assignment = [slot(0, 0, [(0, 100)]), slot(1, 1, [(0, 100)])]
        self.assertFalse(policies.can_change(no_complete_assignment, allow_relocation=True))
        duplicate = [slot(0, 0, [(0, 100), (0, 100)])]
        with self.assertRaisesRegex(ValueError, 'Duplicate or unordered'):
            policies.can_change(duplicate, allow_relocation=True)

    def test_unchanged_complete_assignment_is_available_only_in_v29(self):
        unchanged_slots = [slot(0, 0, [(0, 100)])]
        catalogue = dict(player_id=0, turn=9, reason='available', slots=unchanged_slots)
        self.assertEqual(capability_policies.actions(catalogue, allow_relocation=True), [])
        action, = capability_policies.actions(catalogue, allow_relocation=True,
                                              allow_unchanged=True)
        self.assertEqual(action, dict(kind='policies', slots=unchanged_slots))
        with self.assertRaises(policies.PolicyAssignmentUnavailable):
            policies.choose(unchanged_slots, [100], 0, 9, allow_relocation=True)
        candidate = policies.choose(unchanged_slots, [100], 0, 9,
                                    allow_relocation=True, allow_unchanged=True)
        self.assertEqual(candidate['assignments'], [[0, 100]])
        self.assertEqual(candidate['prior_indices'], [0])

        candidate_id = network_turn.digest(action)
        selection = dict(decision_id='decision', candidate_id=candidate_id,
                         parameters=dict(assignments=[100]))
        v28 = dict(schema=network_turn.CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA,
                   decision_id='decision', player_id=0, turn=9,
                   candidates=[dict(candidate_id=candidate_id, action=action)])
        with self.assertRaisesRegex(ValueError, 'assignment is unchanged'):
            network_turn.select_capability(v28, selection)
        v29 = dict(v28, schema=network_turn.CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA)
        self.assertEqual(network_turn.select_capability(v29, selection)['candidate'], candidate)

        duplicate_slots = [slot(0, 0, [(0, 100), (1, 101)]),
                           slot(1, 1, [(1, 101), (2, 102)])]
        with self.assertRaises(policies.PolicyAssignmentUnavailable):
            policies.choose(duplicate_slots, [101, 101], 0, 9,
                            allow_relocation=True, allow_unchanged=True)

    def test_v29_unchanged_candidate_projects_to_retained_v28_view(self):
        path = resource_root() / 'work' / 'bbg751-policy-relocation' / 'native03' / 'public-replay.jsonl'
        if not path.is_file():
            self.skipTest('Retained v28 government public replay required')
        retained = json.loads(path.read_text(encoding='utf-8').splitlines()[0])['view']
        saved = deepcopy(retained['decisions'])
        observation = retained['observation']
        self.assertEqual(saved['schema'], network_turn.CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA)

        unchanged_slots = [slot(0, 0, [(0, 100)])]
        saved['policies'] = dict(player_id=saved['player_id'], turn=saved['turn'],
                                 reason='available', slots=unchanged_slots)
        # The separate unlock query reports the free-change window, with no
        # paid unlock action, while the synthetic assignment remains unchanged.
        saved['policy_unlock'].update(reason='no_cost', cost=0, can_unlock=False)
        saved['candidates'] = [row for row in saved['candidates']
                               if row['action']['kind'] != 'policies']
        saved['families']['policies'] = dict(status='queried_complete', candidate_ids=[])
        saved.pop('decision_id', None); saved['decision_id'] = network_turn.digest(saved)

        current = deepcopy(saved)
        current['schema'] = network_turn.CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA
        (action,) = capability_policies.actions(current['policies'], allow_relocation=True,
                                                allow_unchanged=True)
        row = dict(candidate_id=network_turn.digest(action), action=action)
        current['candidates'].append(row)
        current['families']['policies']['candidate_ids'] = [row['candidate_id']]
        current.pop('decision_id', None); current['decision_id'] = network_turn.digest(current)
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'],
            current['turn'], player_id=current['player_id'], observation=observation)
        projected, transition = network_turn.checkpoint_catalogue(current, saved, observation,
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['source_schema'], saved['schema'])
        self.assertEqual(transition['target_schema'], current['schema'])
        self.assertEqual(transition['added_action_families'], ['unchanged_policy_confirmation'])

    def test_v28_projection_restores_v27_relocation_gap_and_catalog(self):
        path = resource_root() / 'work' / 'bbg751-government' / 'progress' / 'public-replay.jsonl'
        if not path.is_file():
            self.skipTest('Retained v27 government public replay required')
        retained = json.loads(path.read_text(encoding='utf-8').splitlines()[0])['view']
        saved = deepcopy(retained['decisions'])
        observation = retained['observation']
        self.assertEqual(saved['schema'], network_turn.CAPABILITY_XP2_GOVERNMENT_SCHEMA)

        # Use a synthetic two-active-card state based on the retained v27 view.
        option = lambda index, policy_hash: dict(index=index, hash=policy_hash,
            native_hash=policy_hash, policy_type=f'POLICY_TEST_{index}')
        saved_slots = [
            dict(slot=0, prior_index=0, options=[option(0, 100), option(1, 101)]),
            dict(slot=1, prior_index=2, options=[option(2, 102), option(3, 103)]),
        ]
        saved['policies'] = dict(player_id=saved['player_id'], turn=saved['turn'],
                                 reason='available', slots=saved_slots)
        saved['candidates'] = [row for row in saved['candidates']
                               if row['action']['kind'] != 'policies']
        (saved_action,) = capability_policies.actions(saved['policies'])
        saved_row = dict(candidate_id=network_turn.digest(saved_action), action=saved_action)
        saved['candidates'].append(saved_row)
        saved['families']['policies'] = dict(status='queried_partial',
            candidate_ids=[saved_row['candidate_id']], unqualified=['active_policy_relocation'])
        saved.pop('decision_id', None); saved['decision_id'] = network_turn.digest(saved)

        current = deepcopy(saved)
        current['schema'] = network_turn.CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA
        current_slots = current['policies']['slots']
        current_slots[0]['options'].append(option(2, 102))
        current_slots[1]['options'].append(option(0, 100))
        current_slots[0]['options'].sort(key=lambda row: row['index'])
        current_slots[1]['options'].sort(key=lambda row: row['index'])
        current['candidates'] = [row for row in current['candidates']
                                 if row['action']['kind'] != 'policies']
        (current_action,) = capability_policies.actions(current['policies'], allow_relocation=True)
        current_row = dict(candidate_id=network_turn.digest(current_action), action=current_action)
        current['candidates'].append(current_row)
        current['families']['policies'] = dict(status='queried_complete',
            candidate_ids=[current_row['candidate_id']])
        current.pop('decision_id', None); current['decision_id'] = network_turn.digest(current)
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'],
            current['turn'], player_id=current['player_id'], observation=observation)
        projected, transition = network_turn.checkpoint_catalogue(current, saved, observation,
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['source_schema'], saved['schema'])
        self.assertEqual(transition['target_schema'], current['schema'])
        self.assertEqual(transition['added_action_families'], ['active_policy_relocation'])


if __name__ == '__main__':
    unittest.main()

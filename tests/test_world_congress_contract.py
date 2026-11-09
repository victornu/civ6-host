"""Synthetic public Congress data: no native process or source ABI claim."""
from copy import deepcopy
import math
import unittest

from civ6_host.contracts import world_congress as congress


def catalogue(stage='regular', *, pid=0, turn=61, sequence=3):
    player = dict(player_id=pid, label='Local player')
    hidden = dict(player_id=None, label='Unmet player')
    cost = dict(max_votes=4, costs=[0, 10, 30])
    value = dict(schema=congress.SCHEMA, player_id=pid, turn=turn, sequence=sequence,
        turn_segment=0xf0000011, stage=stage, paused=False,
        in_session=stage != 'ordinary', local_alive=True, turn_active=True,
        presentation='available_proposals' if stage == 'ordinary' else 'closed',
        meeting=dict(turns_left=-1, percentage=25.5) if stage == 'ordinary' else None,
        favor=100.5, current_favor=100.5, vote_cost=deepcopy(cost) if stage == 'regular' else None,
        resolutions=None, discussions=None, proposals=None,
        offers=dict(open=False, confirm_ballot=False, confirm_proposals=False, close=False),
        unavailable=list(congress.GAPS))
    if stage == 'regular':
        value['resolutions'] = [dict(resolution_hash=0xffffffff,
            resolution_type='WC_RES_FIXTURE', name='Fixture resolution',
            effect_a='A effect', effect_b='B effect', target_type='PlayerType',
            targets=[dict(index=0, value=str(pid), label='Local', player_id=pid),
                     dict(index=1, value=None, label='Unmet', player_id=None)])]
        value['offers']['confirm_ballot'] = True
    if stage in ('regular', 'special'):
        value['discussions'] = [dict(index=0, type_name='WC_EMERGENCY_FIXTURE',
            sender=deepcopy(hidden), target=deepcopy(player), name='Discussion',
            description='Public description', disabled=False, no_upvote=False,
            no_downvote=False, blocker=None, vote_cost=dict(max_votes=3, costs=[0, 7, 21]))]
        value['offers']['confirm_ballot'] = True
    if stage == 'ordinary':
        value['proposals'] = [dict(index=0, type_name='WC_EMERGENCY_FIXTURE',
            sender=deepcopy(player), target=deepcopy(hidden), name='Proposal',
            description='Public description', disabled=False, blocker=None,
            favor_cost=15.5, target_key=0)]
        value['offers']['confirm_proposals'] = True
    return value


def ballot_parameters(value, *, resolution_votes=1, discussion_votes=1):
    return dict(resolutions=[dict(resolution_hash=r['resolution_hash'], option=2,
        target_index=len(r['targets']) - 1, votes=resolution_votes) for r in (value['resolutions'] or [])],
        discussions=[dict(discussion_index=r['index'], votes=discussion_votes)
            for r in (value['discussions'] or []) if not r['disabled']
            and not (r['no_upvote'] and r['no_downvote'])])


def confirm(value, **votes):
    return congress.choose(value, congress.actions(value)[0], ballot_parameters(value, **votes))


class WorldCongressContractTests(unittest.TestCase):
    def test_explicit_open_is_local_and_requires_review_domain_without_native_activity_gate(self):
        value = catalogue('ordinary')
        value['presentation'] = 'closed'
        value['offers'] = dict(open=True, confirm_ballot=False, confirm_proposals=False, close=False)
        value['turn_active'] = False
        action = congress.choose(value, congress.actions(value)[0])
        self.assertEqual(action, dict(kind='congress_open', sequence=3))
        plan = congress.operation_plan(value, action)
        self.assertEqual(plan['operations'], [])
        self.assertEqual(plan['following_ui_action'], 'OpenAvailableProposals')
        for field, invalid in (('paused', True), ('presentation', 'available_proposals'), ('proposals', [])):
            bad = deepcopy(value); bad[field] = invalid
            with self.subTest(field=field), self.assertRaises(ValueError): congress.actions(bad)
        for flag in ('confirm_proposals', 'close'):
            bad = deepcopy(value); bad['offers']['open'] = False; bad['offers'][flag] = True
            with self.subTest(flag=flag), self.assertRaises(ValueError): congress.actions(bad)
        bad = catalogue(); bad['presentation'] = 'available_proposals'
        with self.assertRaises(ValueError): congress.actions(bad)

    def test_complete_ballot_resolves_once_and_primitives_are_never_actor_candidates(self):
        value = catalogue()
        self.assertEqual(congress.actions(value), [dict(kind='congress_confirm_ballot', sequence=3)])
        action = confirm(value, resolution_votes=3, discussion_votes=-2)
        plan = congress.operation_plan(value, action)
        self.assertFalse(plan['atomic'])
        self.assertFalse(plan['actor_decisions_between_operations'])
        self.assertEqual([r['kind'] for r in plan['operations']],
            ['congress_resolution_vote', 'congress_discussion_vote', 'congress_submit'])
        self.assertEqual(plan['operations'][0]['target_index'], 1)
        self.assertEqual(plan['operations'][0]['option'], 2)
        self.assertEqual(plan['operations'][1]['votes'], -2)
        self.assertEqual(plan['following_ui_action'], 'ACTION_ENDTURN')
        for primitive in plan['operations']:
            self.assertIs(congress.validate_operation(primitive), primitive)
            with self.assertRaises(ValueError): congress.validate_action(primitive)
            with self.assertRaises(ValueError): congress.choose(value, primitive)

    def test_full_form_is_checked_before_first_operation_plan(self):
        value = catalogue(); action = confirm(value)
        for key in ('resolutions', 'discussions'):
            bad = deepcopy(action); bad[key] = []
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'every offered'):
                congress.operation_plan(value, bad)
        bad = deepcopy(action); bad['discussions'][0]['votes'] = 4
        with self.assertRaisesRegex(ValueError, 'cost domain'): congress.operation_plan(value, bad)
        bad = deepcopy(action); bad['resolutions'][0]['target_index'] = 2
        with self.assertRaisesRegex(ValueError, 'not offered'): congress.operation_plan(value, bad)

    def test_integer_boolean_ranges_extra_fields_and_nonfinite_data(self):
        value = catalogue()
        for key, invalid in (('sequence', True), ('player_id', 64), ('favor', math.nan),
                             ('favor', math.inf), ('favor', 10**1000), ('turn_segment', -1),
                             ('current_favor', True), ('current_favor', math.nan), ('current_favor', -1)):
            bad = deepcopy(value); bad[key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                congress.validate_catalogue(bad, 0, 61)
        for field, invalid in (('option', True), ('target_index', -1), ('votes', 0)):
            parameters = ballot_parameters(value); parameters['resolutions'][0][field] = invalid
            with self.subTest(field=field), self.assertRaises(ValueError):
                congress.choose(value, congress.actions(value)[0], parameters)
        bad = deepcopy(value); bad['private_ballots'] = []
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)

    def test_unmet_targets_remain_present_without_foreign_identity(self):
        value = catalogue(); action = confirm(value)
        self.assertEqual(action['resolutions'][0]['target_index'], 1)
        self.assertNotIn('player_id', action['resolutions'][0])
        bad = deepcopy(value); bad['resolutions'][0]['targets'][1]['value'] = '17'
        with self.assertRaisesRegex(ValueError, 'identity'): congress.validate_catalogue(bad, 0, 61)
        bad = deepcopy(value); bad['resolutions'][0]['targets'].reverse()
        with self.assertRaisesRegex(ValueError, 'native order'): congress.validate_catalogue(bad, 0, 61)

    def test_phase_nulls_and_empty_phase_auto_path_do_not_invent_actor_choice(self):
        for stage in ('regular', 'special', 'ordinary', 'resolving'):
            value = catalogue(stage)
            self.assertIs(congress.validate_catalogue(value, 0, 61, 3), value)
        special = catalogue('special'); action = confirm(special)
        self.assertEqual(action['resolutions'], [])
        self.assertIsNone(special['vote_cost'])
        empty = catalogue(); empty['resolutions'] = []; empty['discussions'] = []
        with self.assertRaisesRegex(ValueError, 'automatic'): congress.validate_catalogue(empty, 0, 61)
        empty['offers']['confirm_ballot'] = False
        self.assertEqual(congress.actions(empty), [])
        plan = congress.empty_phase_plan(empty)
        self.assertEqual(plan['operations'], [dict(kind='congress_submit', sequence=3)])
        self.assertEqual(plan['following_ui_action'], 'ACTION_ENDTURN')
        with self.assertRaises(ValueError): congress.empty_phase_plan(catalogue())

    def test_proposals_confirm_together_with_budget_target_and_close_seam(self):
        value = catalogue('ordinary')
        second = deepcopy(value['proposals'][0]); second.update(index=1, type_name='OTHER')
        value['proposals'].append(second)
        candidate = congress.actions(value)[0]
        with self.assertRaisesRegex(ValueError, 'one target'):
            congress.choose(value, candidate, dict(proposal_indices=[0, 1]))
        value['proposals'][1]['target_key'] = 1
        action = congress.choose(value, candidate, dict(proposal_indices=[1, 0]))
        plan = congress.operation_plan(value, action)
        self.assertEqual([r['proposal_index'] for r in plan['operations']], [0, 1])
        self.assertEqual(plan['following_ui_action'], 'ClosePopup')
        value['favor'] = 20
        # Each proposal is affordable, the complete confirmed form is not.
        with self.assertRaisesRegex(ValueError, 'combined'):
            congress.choose(value, candidate, dict(proposal_indices=[0, 1]))

    def test_close_is_separate_source_gated_ui_action_not_a_native_opcode_candidate(self):
        value = catalogue('ordinary'); value['offers']['close'] = True
        close = congress.choose(value, congress.actions(value)[-1])
        self.assertEqual(close, dict(kind='congress_close', sequence=3))
        self.assertEqual(congress.operation_plan(value, close)['operations'],
                         [dict(kind='congress_looked_at_available', sequence=3)])
        # ClosePopup visibility is separate from native request admission.
        value.update(paused=True, local_alive=False, turn_active=False)
        value['offers']['confirm_proposals'] = False
        self.assertEqual(congress.actions(value), [close])
        bad = catalogue(); bad['offers']['close'] = True
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)

    def test_disabled_proposal_retains_its_source_target_lock_without_being_sent(self):
        value = catalogue('ordinary')
        disabled = deepcopy(value['proposals'][0]); disabled.update(index=1, disabled=True)
        value['proposals'].append(disabled)
        with self.assertRaisesRegex(ValueError, 'no selectable'):
            congress.validate_catalogue(value, 0, 61)
        independent = deepcopy(value['proposals'][0]); independent.update(index=2, target_key=1)
        value['proposals'].append(independent)
        candidate = congress.actions(value)[0]
        with self.assertRaisesRegex(ValueError, 'locked'):
            congress.choose(value, candidate, dict(proposal_indices=[0]))
        action = congress.choose(value, candidate, dict(proposal_indices=[2]))
        self.assertEqual(congress.operation_plan(value, action)['operations'],
            [dict(kind='congress_discussion_selection', sequence=3, proposal_index=2)])
        value['favor'] = 0
        with self.assertRaisesRegex(ValueError, 'no selectable'):
            congress.validate_catalogue(value, 0, 61)

    def test_distinct_category_costs_combined_favor_and_direction_constraints(self):
        value = catalogue()
        draft = congress.ballot_draft(value, ballot_parameters(value, resolution_votes=3, discussion_votes=-3))
        self.assertEqual(draft['total_favor_cost'], 51)
        value['favor'] = value['current_favor'] = 40
        with self.assertRaisesRegex(ValueError, 'combined'):
            confirm(value, resolution_votes=3, discussion_votes=-3)
        value['discussions'][0]['no_downvote'] = True
        with self.assertRaisesRegex(ValueError, 'direction'): confirm(value, discussion_votes=-1)
        value['discussions'][0]['no_upvote'] = True
        self.assertEqual(confirm(value)['discussions'], [])

    def test_owned_review_keeps_starting_budget_separate_from_current_favor(self):
        value = catalogue('ordinary'); value.update(favor=20, current_favor=0)
        candidate = congress.actions(value)[0]
        parameters = dict(proposal_indices=[0])
        self.assertEqual(congress.choose(value, candidate, parameters)['proposal_indices'], [0])
        self.assertEqual(congress.ballot_draft(value, parameters)['total_favor_cost'], 15.5)
        value.update(favor=10, current_favor=100)
        value['offers']['confirm_proposals'] = False
        self.assertIs(congress.validate_catalogue(value, 0, 61), value)
        with self.assertRaisesRegex(ValueError, 'absent'): congress.choose(value, candidate, parameters)
        value['presentation'] = 'closed'
        with self.assertRaisesRegex(ValueError, 'outside owned review'):
            congress.validate_catalogue(value, 0, 61)
        regular = catalogue(); regular['current_favor'] += 1
        with self.assertRaisesRegex(ValueError, 'outside owned review'):
            congress.validate_catalogue(regular, 0, 61)

    def test_zero_signed_transport_is_not_a_voluntary_ui_abstention(self):
        operation = dict(kind='congress_discussion_vote', sequence=3, discussion_index=0, votes=0)
        self.assertIs(congress.validate_operation(operation), operation)
        operation['votes'] = -0x80000000
        self.assertIs(congress.validate_operation(operation), operation)
        operation['votes'] -= 1
        with self.assertRaises(ValueError): congress.validate_operation(operation)
        value = catalogue()
        with self.assertRaisesRegex(ValueError, 'nonzero'): confirm(value, discussion_votes=0)

    def test_draft_review_metadata_has_no_individually_executable_steps(self):
        value = catalogue(); draft = congress.ballot_draft(value, ballot_parameters(value))
        review = congress.draft_plan(value, draft)
        self.assertFalse(review['native_submission_issued'])
        self.assertFalse(review['atomic'])
        self.assertFalse(review['actor_decisions_between_operations'])
        self.assertEqual(review['request_count'], 3)
        self.assertNotIn('operations', review)
        self.assertNotIn('steps', review)
        for key, invalid in (('sequence', True), ('native_submission_issued', True), ('total_favor_cost', False)):
            bad = deepcopy(draft); bad[key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError): congress.draft_plan(value, bad)
        value['sequence'] += 1
        with self.assertRaises(ValueError): congress.draft_plan(value, draft)

    def test_duplicates_ownership_bounds_and_inactive_actor(self):
        value = catalogue()
        with self.assertRaises(ValueError): congress.validate_catalogue(value, 1, 61)
        with self.assertRaises(ValueError): congress.validate_catalogue(value, 0, 61, 4)
        bad = deepcopy(value); bad['resolutions'].append(deepcopy(bad['resolutions'][0]))
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)
        bad = deepcopy(value); bad['vote_cost']['costs'] = [0] * 4097
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)
        bad = deepcopy(value); bad['discussions'][0]['index'] = True
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)
        bad = deepcopy(value); bad['unavailable'] = []
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)
        bad = deepcopy(value); bad['turn_active'] = False
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)
        bad['offers'] = {k: False for k in bad['offers']}
        self.assertEqual(congress.actions(bad), [])
        bad = deepcopy(value); bad['sent'] = {'resolution_hashes': [], 'discussion_indices': []}
        with self.assertRaises(ValueError): congress.validate_catalogue(bad, 0, 61)


if __name__ == '__main__':
    unittest.main()

"""Synthetic allowlist fixtures; no native legality, evidence or gameplay claim.

Every action below is built as a minimal dict in the shape its own contract
module validates, and is handed to that validator before it is used, so a
contract shape change breaks this file instead of silently passing.
"""
import unittest

from civ6_host.contracts import (
    air_operations,
    capability_choices,
    capability_city_controls,
    capability_unit_attacks,
    capability_unit_orders,
    capability_world_input,
    diplomacy_overview,
    placement,
    production_queue,
    rock_bands,
    unit_work,
    war_confirmation,
    world_congress,
)
from civ6_host.contracts import qualified_families as allowlist


WIDTH = 44
HOLY_SITE = dict(kind='production_placement', city_id=1, category='district',
                 index=2, hash=3, item_type='DISTRICT_HOLY_SITE', mode='place',
                 plot_id=13 * WIDTH + 11, x=11, y=13)


def _checked(action, validator):
    validator(action)
    return action


#: One contract-shaped action per qualified decision kind we can build directly.
QUALIFIED_ACTIONS = {
    'research': _checked(dict(kind='research', index=3, hash=0x11),
                         capability_choices.validate_action),
    'civic': _checked(dict(kind='civic', index=4, hash=0x12),
                      capability_choices.validate_action),
    'production': _checked(
        dict(kind='production', city_id=1, category='unit', index=5, hash=0x13,
             item_type='UNIT_BUILDER'), capability_choices.validate_action),
    'found_city': _checked(dict(kind='found_city', unit_id=7, x=10, y=12),
                           capability_choices.validate_founder_action),
    'build_improvement': _checked(
        dict(kind='build_improvement', unit_id=7, x=11, y=13,
             plot_id=13 * WIDTH + 11, charges=2, moves_token='2', index=6,
             hash=0x14, item_type='IMPROVEMENT_FARM', selector=1),
        unit_work.validate_action),
    'city_focus': _checked(
        dict(kind='city_focus', city_id=1, yield_type='YIELD_PRODUCTION',
             yield_index=1, favored=True, disfavored=False),
        capability_city_controls.validate_action),
    'city_citizen': _checked(
        dict(kind='city_citizen', city_id=1, plot_id=13 * WIDTH + 11, x=11,
             y=13, occupied=True, locked=True, workers=1, capacity=2),
        capability_city_controls.validate_action),
    'queue_append': _checked(
        dict(kind='queue_append', city_id=1, category='unit', index=7, hash=0x15,
             item_type='UNIT_SLINGER', mode='append'),
        production_queue.validate_action),
    'queue_remove': _checked(dict(kind='queue_remove', city_id=1, position=3),
                             production_queue.validate_action),
    'queue_swap': _checked(
        dict(kind='queue_swap', city_id=1, source_position=2,
             destination_position=4), production_queue.validate_action),
    'production_placement': _checked(dict(HOLY_SITE), placement.validate_action),
    'production_resume': _checked(
        dict(kind='production_resume', city_id=1, category='district', index=2,
             hash=3, item_type='DISTRICT_HOLY_SITE'), placement.validate_action),
    'unit_attack': _checked(
        dict(kind='unit_attack', unit_id=5, operation='RANGE_ATTACK',
             input_route='dedicated_ranged', plot_id=13 * WIDTH + 11, x=11, y=13),
        capability_unit_attacks.validate_action),
    'unit_order': _checked(
        dict(kind='unit_order', unit_id=5, route='operation',
             item_type='UNITOPERATION_HEAL', hash=9),
        capability_unit_orders.validate_action),
    'world_plot_click': _checked(
        dict(kind='world_plot_click', unit_id=5, plot_id=13 * WIDTH + 11, x=11,
             y=13), capability_world_input.validate_action),
    'world_war_response': _checked(dict(kind=war_confirmation.ACTION_KIND,
                                        accept=True),
                                   war_confirmation.validate_action),
    'diplomacy_initiate': _checked(
        dict(kind='diplomacy_initiate', target_player_id=3,
             choice='CHOICE_OFFER_DELEGATION'), diplomacy_overview.validate_action),
    'congress_confirm_ballot': _checked(
        dict(kind='congress_confirm_ballot', sequence=3),
        world_congress.validate_candidate),
    'congress_open': _checked(dict(kind='congress_open', sequence=3),
                              world_congress.validate_candidate),
    'congress_confirm_proposals': _checked(
        dict(kind='congress_confirm_proposals', sequence=3),
        world_congress.validate_candidate),
    'congress_close': _checked(dict(kind='congress_close', sequence=3),
                               world_congress.validate_candidate),
    'force_end_turn': dict(kind='force_end_turn'),
    'end_turn': dict(kind='end_turn'),
    'unready_turn': dict(kind='unready_turn'),
    # Documented as unqualified: shapes only, no receipt.
    'air_operation': dict(kind=air_operations.KIND, operation='AIR_ATTACK',
                          unit_id=5, plot_id=13 * WIDTH + 11, x=11, y=13),
    'perform_rock_concert': dict(kind=rock_bands.KIND, unit_id=5, x=11, y=13),
    'declare_war_minor': dict(kind='declare_war_minor', target_player_id=3),
}

EXPECTED_FAMILIES = frozenset((
    'found_city', 'research', 'civic', 'builder_production', 'farm_build',
    'city_focus', 'city_citizen_lock', 'production_queue_edit',
    'holy_site_placement', 'unit_attack', 'unit_order_heal', 'swap_units',
    'war_confirmation', 'surprise_war', 'initial_diplomacy',
    'world_congress_ballot', 'force_end_turn', 'terminal_response',
    'checkpoint_save_resume', 'espionage_diagnostic',
))

NULL_TURNS = dict.fromkeys(allowlist.TURN_KINDS)


def candidate(prefix, kind, index=0):
    action = QUALIFIED_ACTIONS.get(kind, dict(kind=kind))
    return dict(candidate_id='%s-%d' % (prefix, index), action=dict(action))


def frame(kinds, *, turn_availability=None):
    rows = [candidate(kind, kind, index) for index, kind in enumerate(kinds)]
    value = dict(candidates=rows)
    if turn_availability is not None:
        value['turn_availability'] = dict(turn_availability)
    return value


class AllowlistData(unittest.TestCase):
    def test_families_are_exactly_the_qualified_list(self):
        self.assertEqual(frozenset(allowlist.QUALIFIED_FAMILIES),
                         EXPECTED_FAMILIES)

    def test_every_family_names_its_contract_kinds_and_receipts(self):
        for name, entry in allowlist.QUALIFIED_FAMILIES.items():
            with self.subTest(family=name):
                self.assertEqual(set(entry), {'contract', 'kinds', 'evidence', 'note'})
                self.assertTrue(entry['contract'].startswith('civ6_host.contracts.'))
                self.assertIsInstance(entry['kinds'], frozenset)
                self.assertTrue(entry['evidence'], 'a family without a receipt')
                for receipt in entry['evidence']:
                    self.assertTrue(receipt.startswith('evidence/host-'))
                    self.assertTrue(receipt.endswith('.json'))

    def test_no_kind_is_claimed_by_two_families(self):
        claimed = {}
        for name, entry in allowlist.QUALIFIED_FAMILIES.items():
            for kind in entry['kinds']:
                self.assertNotIn(kind, claimed, kind)
                claimed[kind] = name
        self.assertEqual({kind: names[0]
                          for kind, names in allowlist.KIND_FAMILIES.items()},
                         claimed)
        for kind, name in claimed.items():
            self.assertEqual(allowlist.families_for_kind(kind), (name,))
            self.assertTrue(allowlist.is_qualified_kind(kind))

    def test_every_qualified_kind_has_a_contract_shaped_fixture(self):
        missing = set(allowlist.KIND_FAMILIES) - set(QUALIFIED_ACTIONS)
        self.assertEqual(missing, set())

    def test_session_only_families_add_no_decision_kind(self):
        for name in ('terminal_response', 'checkpoint_save_resume',
                     'espionage_diagnostic'):
            self.assertEqual(allowlist.QUALIFIED_FAMILIES[name]['kinds'], frozenset())

    def test_documented_unqualified_kinds_are_masked(self):
        self.assertFalse(allowlist.UNQUALIFIED_KINDS & set(allowlist.KIND_FAMILIES))
        self.assertFalse(allowlist.is_qualified_kind(air_operations.KIND))
        self.assertFalse(allowlist.is_qualified_kind(rock_bands.KIND))
        self.assertIn('complete_action_space=true', allowlist.UNQUALIFIED_NOTE)


class QualifiedPassThrough(unittest.TestCase):
    def test_every_qualified_kind_passes_through_in_frame_order(self):
        kinds = sorted(allowlist.KIND_FAMILIES)
        value = frame(kinds, turn_availability=dict(NULL_TURNS))
        allowed, masked = allowlist.mask_unqualified(value)
        self.assertEqual(allowed, [row['candidate_id'] for row in value['candidates']])
        self.assertEqual(masked, ())
        self.assertEqual(len(allowed), len(kinds))

    def test_qualified_frame_masks_nothing(self):
        value = frame(['research', 'civic', 'found_city', 'city_focus'])
        self.assertEqual(allowlist.mask_unqualified(value),
                         ([row['candidate_id'] for row in value['candidates']], ()))

    def test_single_kind_frames(self):
        for kind in sorted(allowlist.KIND_FAMILIES):
            with self.subTest(kind=kind):
                if kind in allowlist.TURN_KINDS:
                    value = frame([kind], turn_availability=dict(NULL_TURNS))
                else:
                    value = frame([kind])
                allowed, masked = allowlist.mask_unqualified(value)
                self.assertEqual(allowed, ['%s-0' % kind])
                self.assertEqual(masked, ())


class UnqualifiedMasked(unittest.TestCase):
    def test_unqualified_kinds_are_masked_and_reported(self):
        value = frame(['research', 'air_operation', 'perform_rock_concert',
                       'declare_war_minor', 'sky_pirates'])
        allowed, masked = allowlist.mask_unqualified(value)
        self.assertEqual(allowed, ['research-0', 'declare_war_minor-3'])
        self.assertEqual(masked, ('air_operation', 'perform_rock_concert',
                                  'sky_pirates'))

    def test_unready_turn_is_never_admitted(self):
        for flag in (True, False, None):
            with self.subTest(unready=flag):
                value = frame(['unready_turn'], turn_availability=dict(
                    end_turn=True, force_end_turn=True, unready_turn=flag))
                self.assertEqual(allowlist.mask_unqualified(value),
                                 ([], ('unready_turn',)))

    def test_masked_names_are_reported_once_even_when_repeated(self):
        value = frame(['air_operation', 'air_operation', 'research',
                       'air_operation'])
        self.assertEqual(allowlist.mask_unqualified(value),
                         (['research-2'], ('air_operation',)))

    def test_candidate_without_a_kind_is_masked(self):
        value = dict(candidates=[dict(candidate_id='x-0', action={}),
                                 dict(candidate_id='x-1')])
        self.assertEqual(allowlist.mask_unqualified(value),
                         ([], (allowlist.UNKNOWN_KIND,)))


class NullEndTurn(unittest.TestCase):
    def test_null_end_turn_admits_force_end_turn(self):
        value = frame(['end_turn', 'force_end_turn', 'unready_turn'],
                      turn_availability=dict(NULL_TURNS))
        allowed, masked = allowlist.mask_unqualified(value)
        self.assertEqual(allowed, ['force_end_turn-1'])
        self.assertEqual(masked, ('end_turn', 'unready_turn'))
        self.assertTrue(allowlist.turn_branch_allows('force_end_turn', NULL_TURNS))
        self.assertFalse(allowlist.turn_branch_allows('end_turn', NULL_TURNS))

    def test_null_force_flag_with_true_end_turn_does_not_admit_forced_turn(self):
        availability = dict(NULL_TURNS, end_turn=True)
        self.assertFalse(allowlist.turn_branch_allows('force_end_turn', availability))
        self.assertTrue(allowlist.turn_branch_allows('end_turn', availability))

    def test_explicit_true_force_flag_is_admitted(self):
        availability = dict(NULL_TURNS, force_end_turn=True)
        self.assertTrue(allowlist.turn_branch_allows('force_end_turn', availability))
        value = frame(['force_end_turn'], turn_availability=availability)
        self.assertEqual(allowlist.mask_unqualified(value), (['force_end_turn-0'], ()))

    def test_false_flags_admit_no_turn_candidate(self):
        availability = dict.fromkeys(allowlist.TURN_KINDS, False)
        value = frame(['end_turn', 'force_end_turn'], turn_availability=availability)
        self.assertEqual(allowlist.mask_unqualified(value),
                         ([], ('end_turn', 'force_end_turn')))

    def test_missing_availability_behaves_as_the_null_branch(self):
        value = frame(['force_end_turn'])
        self.assertEqual(allowlist.mask_unqualified(value), (['force_end_turn-0'], ()))

    def test_turn_branch_rejects_non_turn_kinds(self):
        with self.assertRaises(ValueError):
            allowlist.turn_branch_allows('research')


class EmptyAndMalformed(unittest.TestCase):
    def test_empty_decisions_give_an_empty_mask(self):
        for value in ({}, dict(candidates=[]), dict(candidates=[], families={}),
                      dict(candidates=None, turn_availability=dict(NULL_TURNS))):
            with self.subTest(value=value):
                self.assertEqual(allowlist.mask_unqualified(value), ([], ()))

    def test_malformed_frames_are_refused(self):
        for value in (None, [], 'decisions',
                      dict(candidates='rows'),
                      dict(candidates=[1]),
                      dict(candidates=[dict(candidate_id=7, action={})]),
                      dict(candidates=[dict(action={'kind': 'research'})]),
                      dict(candidates=[], turn_availability=[]),
                      dict(candidates=[], turn_availability={'end_turn': 'yes'}),
                      dict(candidates=[], turn_availability={'extra_turn': True})):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    allowlist.mask_unqualified(value)

    def test_the_frame_is_not_modified(self):
        value = frame(['research', 'air_operation'])
        before = {k: (list(v) if isinstance(v, list) else v)
                  for k, v in value.items()}
        allowlist.mask_unqualified(value)
        self.assertEqual(value, before)


if __name__ == '__main__':
    unittest.main()

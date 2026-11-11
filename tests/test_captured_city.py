import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from civ6_host.contracts import captured_city, network_turn


class CapturedCityContractTests(unittest.TestCase):
    def setUp(self):
        self.observation = dict(player_id=0, turn=43, cities=[dict(id=777, x=27, y=14, owner=0)])
        self.native = dict(
            player_id=0, turn=43, directives=['KEEP', 'LIBERATE_FOUNDER'],
            city=dict(city_id=777, x=27, y=14, original_owner=5, previous_owner=4, conquered_from=4),
        )

    def test_public_city_only_exposes_a_recipient_for_an_offered_liberation(self):
        state = captured_city.project_public(self.native, observation=self.observation)
        self.assertEqual(state['city'], dict(
            city_id=777, x=27, y=14, liberation_recipients={'LIBERATE_FOUNDER': 5}))
        captured_city.validate_public_catalog(state, 0, 43, observation=self.observation)
        self.assertEqual(captured_city.public_actions(state), [
            dict(kind='resolve_captured_city', city_id=777, directive='KEEP'),
            dict(kind='resolve_captured_city', city_id=777, directive='LIBERATE_FOUNDER'),
        ])
        state['city']['liberation_recipients']['LIBERATE_PREVIOUS_OWNER'] = 4
        with self.assertRaisesRegex(ValueError, 'recipients differ'):
            captured_city.validate_public_catalog(state, 0, 43, observation=self.observation)

    def test_public_city_must_match_the_players_observation(self):
        state = captured_city.project_public(self.native, observation=self.observation)
        state['city']['x'] += 1
        with self.assertRaisesRegex(ValueError, 'own-city observation'):
            captured_city.validate_public_catalog(state, 0, 43, observation=self.observation)
        with self.assertRaisesRegex(ValueError, 'Unknown captured-city action'):
            captured_city.validate_action(dict(kind='resolve_captured_city', city_id=777, directive='REJECT'))

    def test_queried_empty_is_distinct_from_unavailable(self):
        base = dict(schema=network_turn.CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA,
                    families={}, candidates=[], decision_id='old')
        state = dict(player_id=0, turn=43, city=None, directives=[])
        available = network_turn.upgrade_captured_city_catalogue(base, state, actions_closed=False)
        self.assertEqual(available['families'][captured_city.KIND],
                         dict(status='queried_complete', candidate_ids=[]))
        self.assertEqual(available['captured_city'], state)
        waiting = network_turn.upgrade_captured_city_catalogue(base, None, actions_closed=False)
        self.assertEqual(waiting['families'][captured_city.KIND]['status'], 'unqualified')
        self.assertIsNone(waiting['captured_city'])
        self.assertEqual(base['families'], {})

    def test_stock_catalogue_preserves_query_groups_and_offers_native_directives(self):
        state = captured_city.project_public(self.native, observation=self.observation)
        groups = (
            network_turn.STOCK_TRADE_CAPABILITY_SCHEMAS,
            network_turn.STOCK_FORMATION_SCHEMAS,
            network_turn.STOCK_DEDICATION_SCHEMAS,
            network_turn.WORLD_CONGRESS_CAPABILITY_SCHEMAS,
            network_turn.WORLD_CONGRESS_REVIEW_CAPABILITY_SCHEMAS,
            network_turn.NATIVE_COMMAND_PERMISSIONS_SCHEMAS,
            network_turn.CONGRESS_ACTIVE_EFFECTS_CAPABILITY_SCHEMAS,
        )
        action = dict(kind='move', unit_id=8)
        candidate = dict(candidate_id=network_turn.digest(action), action=action)
        for schema in (
                network_turn.CAPABILITY_XP2_STANDARD_TRADE_SCHEMA,
                network_turn.CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA,
                network_turn.CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA,
                network_turn.CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA):
            with self.subTest(schema=schema):
                base = dict(schema=schema, families={}, candidates=[candidate], decision_id='old')
                extended = network_turn.upgrade_captured_city_catalogue(base, state, actions_closed=False)
                self.assertNotEqual(extended['schema'], schema)
                for group in groups:
                    self.assertEqual(extended['schema'] in group, schema in group)
                self.assertEqual(extended['candidates'][0], candidate)
                choices = extended['families'][captured_city.KIND]['candidate_ids']
                self.assertEqual(
                    [network_turn.select_capability(extended, dict(
                        decision_id=extended['decision_id'], candidate_id=choice)) for choice in choices],
                    captured_city.public_actions(state))
                self.assertEqual(base['candidates'], [candidate])


class NativeOccupationReceiptTests(unittest.TestCase):
    def test_completion_requires_transfer_to_the_offered_recipient(self):
        from civ6_host.runtime.native import native_saved_captured_city as native

        before = dict(player_id=0, turn=43, cities=[dict(id=777, x=27, y=14, owner=0)])
        after = dict(player_id=0, turn=43, cities=[])
        city = dict(city_id=777, x=27, y=14, original_owner=5, previous_owner=4, conquered_from=6)
        choices = ['LIBERATE_FOUNDER', 'LIBERATE_PREVIOUS_OWNER']
        available = dict(player_id=0, turn=43, city=city, directives=choices)
        empty = dict(player_id=0, turn=43, city=None, directives=[])

        for directive, recipient in zip(choices, (5, 4)):
            for readback in (b'verified', b'mismatch'):
                with self.subTest(directive=directive, readback=readback):
                    actions = SimpleNamespace(pending=[])
                    actions.deliver_one = Mock(side_effect=actions.pending.clear)
                    owner = SimpleNamespace(explicit_captured_city=available, emit=Mock())
                    prefix = SimpleNamespace(
                        ui_child=object(), game_child=object(), actions=actions,
                        deferred_events=SimpleNamespace(pending=[], drain_empty_receivers=Mock()),
                        view_publisher=SimpleNamespace(publish=Mock()),
                        runtime=SimpleNamespace(),
                    )

                    def evaluate(child, source, name, **options):
                        if name == b'@explicit_captured_city_request':
                            self.assertIs(child, prefix.ui_child)
                            actions.pending.append(object())
                            return b'submitted'
                        self.assertIs(child, prefix.game_child)
                        self.assertEqual(name, b'@explicit_captured_city_liberation_effect')
                        self.assertIn(f'43, 27, 14, {recipient}'.encode(), source)
                        self.assertIn(b'city:GetOwner() == recipient', source)
                        return readback

                    prefix.runtime.evaluate_text = Mock(side_effect=evaluate)
                    action = dict(kind='resolve_captured_city', city_id=777, directive=directive)
                    with (patch.object(native, 'catalog', side_effect=(available, empty)),
                          patch.object(native, 'request_source', return_value=b'request'),
                          patch.object(native, 'observe_player', return_value=after)):
                        if readback == b'verified':
                            self.assertIs(native.apply(owner, prefix, action, 43, before), after)
                            self.assertEqual(owner.emit.call_args.kwargs['verified_liberation_recipient'],
                                             recipient)
                        else:
                            with self.assertRaisesRegex(RuntimeError, 'offered recipient'):
                                native.apply(owner, prefix, action, 43, before)
                            owner.emit.assert_not_called()
                    actions.deliver_one.assert_called_once()
                    self.assertEqual(prefix.runtime.evaluate_text.call_count, 2)

    def test_raze_requires_native_target_before_and_empty_tile_after(self):
        from civ6_host.runtime.native import native_saved_captured_city as native

        before = dict(player_id=0, turn=43, cities=[dict(id=777, x=27, y=14, owner=0)])
        after = dict(player_id=0, turn=43, cities=[])
        city = dict(city_id=777, x=27, y=14, original_owner=4, previous_owner=4, conquered_from=4)
        available = dict(player_id=0, turn=43, city=city, directives=['RAZE'])
        empty = dict(player_id=0, turn=43, city=None, directives=[])
        action = dict(kind='resolve_captured_city', city_id=777, directive='RAZE')
        for before_readback, after_readback in (
                (b'verified', b'verified'), (b'mismatch', b'verified'), (b'verified', b'mismatch')):
            with self.subTest(before=before_readback, after=after_readback):
                actions = SimpleNamespace(pending=[])
                actions.deliver_one = Mock(side_effect=actions.pending.clear)
                owner = SimpleNamespace(explicit_captured_city=available, emit=Mock())
                prefix = SimpleNamespace(
                    ui_child=object(), game_child=object(), actions=actions,
                    deferred_events=SimpleNamespace(pending=[], drain_empty_receivers=Mock()),
                    view_publisher=SimpleNamespace(publish=Mock()), runtime=SimpleNamespace())

                def evaluate(child, source, name, **options):
                    if name == b'@explicit_captured_city_request':
                        self.assertIs(child, prefix.ui_child)
                        actions.pending.append(object())
                        return b'submitted'
                    self.assertIs(child, prefix.game_child)
                    self.assertIn(b'43, 27, 14, 0', source)
                    self.assertIn(b'Cities.GetCityInPlot(x, y)', source)
                    if name == b'@explicit_captured_city_raze_before':
                        self.assertIn(b'city:GetID() == 777 and city:GetOwner() == 0', source)
                        return before_readback
                    self.assertEqual(name, b'@explicit_captured_city_raze_effect')
                    self.assertIn(b'if city == nil', source)
                    return after_readback

                prefix.runtime.evaluate_text = Mock(side_effect=evaluate)
                with (patch.object(native, 'catalog', side_effect=(available, empty)),
                      patch.object(native, 'request_source', return_value=b'request'),
                      patch.object(native, 'observe_player', return_value=after)):
                    if before_readback == after_readback == b'verified':
                        self.assertIs(native.apply(owner, prefix, action, 43, before), after)
                        self.assertEqual(owner.emit.call_args.kwargs['verified_razed_city_plot'],
                                         dict(x=27, y=14))
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'city to raze differs|city still present'):
                            native.apply(owner, prefix, action, 43, before)
                        owner.emit.assert_not_called()
                self.assertEqual(actions.deliver_one.call_count, int(before_readback == b'verified'))


if __name__ == '__main__':
    unittest.main()

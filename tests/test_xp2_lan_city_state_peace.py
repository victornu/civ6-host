"""Exercise secondary-seat peace through public choices and the shared archive."""

from copy import deepcopy
from dataclasses import replace
import json
from struct import pack
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import diplomacy_overview, network_turn
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint, xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime import xp2_governors, xp2_lan_city_states, xp2_lan_government, xp2_lan_ranged_shots
from civ6_host.runtime import xp2_lan_unit_attacks, xp2_lan_unit_development, xp2_plot_purchases
from civ6_host.runtime import xp2_trade
from civ6_host.runtime.captured_session_profile import select as select_capture
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from test_xp2_lan_war_confirmation import WarFixture


ACTION = dict(kind='diplomacy_initiate', target_player_id=2, choice=diplomacy_overview.MAKE_PEACE)


class PeaceFixture(WarFixture):
    operation = 0x19a71b70

    def __init__(self, *, stock=False):
        super().__init__()
        self.at_war = True
        self.can_make_peace = True
        self.saved._xp2_lan_city_states_enabled = True
        self.saved.diplomacy_overview_diagnostic = True
        self.saved.governors_diagnostic = not stock
        self.saved.standard_trade = stock
        reference = xp2_bundle_inputs.REFERENCE if stock else xp2_bbg_inputs.REFERENCE
        self.backend.captured_bundle = replace(self.backend.captured_bundle, reference=reference)
        self.saved.inputs.profile = select_capture(XP2_CORE_SHA256, official_bundle=reference).candidate.profile
        self.saved.inputs.official_bundle = reference
        self.saved.network_reference['capture_manifest_sha256'] = reference[1]
        # The test installs the already-qualified surrounding LAN schema;
        # effects and catalogue construction for peace remain real Python.
        self.saved._xp2_lan_ranged_shots_enabled = True
        self.saved._xp2_lan_purchases_enabled = True
        self.saved._xp2_lan_government_enabled = True
        self.saved._xp2_lan_unit_development_enabled = True
        self.saved._xp2_lan_unit_attacks_enabled = True
        self.stack.enter_context(patch.object(xp2_lan_ranged_shots, 'read', return_value={}))
        self.stack.enter_context(patch.object(xp2_plot_purchases, 'borrowed_catalogue', return_value=None))
        self.stack.enter_context(patch.object(xp2_lan_government, 'read', return_value={}))
        self.stack.enter_context(patch.object(xp2_lan_unit_attacks, 'read', return_value=None))
        self.stack.enter_context(patch.object(xp2_lan_unit_development, 'read', return_value={}))
        self.stack.enter_context(patch.object(xp2_lan_city_states, 'read', return_value={}))
        self.stack.enter_context(patch.object(xp2_governors, 'borrowed_enabled', return_value=False))
        if stock:
            self.stack.enter_context(patch.object(xp2_trade, 'read_borrowed',
                                                  return_value=dict.fromkeys(xp2_trade.FIELDS.values())))

    def evaluate(self, child, source, name, **options):
        if name in (b'@xp2_city_state_peace_panel', b'@xp2_city_state_peace_operation'):
            assert self.player == 1 and child is self.token.ui_child
            assert b'local pid,turn=1,8\n' in source
            if name == b'@xp2_city_state_peace_operation':
                assert b'PlayerOperations.DIPLOMACY_MAKE_PEACE' in source
                return json.dumps([self.operation, self.attacker_key, self.defender_key]).encode()
            return json.dumps(dict(military_enabled=True, targets=[dict(
                player_id=2, at_war=self.at_war,
                can_make_peace=self.at_war and self.can_make_peace)])).encode()
        return super().evaluate(child, source, name, **options)

    def submit(self, core, context, player, operation, parameters, *, read, core_sha256):
        assert read == self.backend.runtime.read
        return super().submit(core, context, player, operation, parameters, core_sha256=core_sha256)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or not self.queued:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            assert self.player == 1
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            self.queued = self.at_war = False

        return drain


class SecondaryCityStatePeaceTests(TestCase):
    def fixture(self, *, stock=False):
        fixture = PeaceFixture(stock=stock)
        self.addCleanup(fixture.close)
        return fixture

    def test_public_choice_executes_for_second_seat_and_reprojects_on_resume(self):
        f = self.fixture()
        saved = f.saved
        original = deepcopy(f.observations[0])
        before, decisions, _ = f.reply(1)
        row, = [row for row in decisions['candidates'] if row['action'] == ACTION]
        self.assertEqual(decisions['families']['diplomacy_initiate']['candidate_ids'], [row['candidate_id']])
        self.assertTrue(decisions['city_state_peace']['targets'][0]['at_war'])

        after, next_decisions, receipt = f.reply(2, ACTION)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=ACTION))
        self.assertFalse(next_decisions['city_state_peace']['targets'][0]['at_war'])
        self.assertEqual(next_decisions['families']['diplomacy_initiate']['candidate_ids'], [])
        self.assertEqual(after, before)
        self.assertEqual(sum(row[0] == 'receive' for row in f.machine), 1)
        self.assertEqual(f.player, 0)
        self.assertEqual(f.token.observation, original)

        boundary = xp1_session_checkpoint.boundary(saved)
        current = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
        legacy = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                       city_state_peace_enabled=False)
        self.assertIs(current['city_state_peace_enabled'], True)
        self.assertNotIn('city_state_peace_enabled', legacy)
        state = dict(observation=original, decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary,
                     checkpoint_public_views=current, host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (current, legacy):
            manifest = dict(state, checkpoint_public_views=views)
            with patch.object(network_checkpoint, 'manifest', return_value=manifest):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        self.assertEqual(network_checkpoint._checkpoint_view_scope(state), ((0, 1), (1,)))
        invalid = dict(state, checkpoint_public_views=dict(current, city_state_peace_enabled=False))
        with self.assertRaisesRegex(ValueError, 'city-state peace scope'):
            network_checkpoint._checkpoint_view_scope(invalid)

    def test_changed_offer_refuses_before_archive_and_retains_original_seat(self):
        f = self.fixture()
        f.reply(1)
        f.can_make_peace = False
        _, decisions, receipt = f.reply(2, ACTION)
        self.assertEqual((receipt['status'], receipt['reason']), ('refused', 'native_city_state_peace_changed'))
        self.assertEqual(decisions['families']['diplomacy_initiate']['candidate_ids'], [])
        f.request_war.assert_not_called()
        self.assertEqual(f.player, 0)

    def test_stock_secondary_can_make_peace_without_bbg(self):
        f = self.fixture(stock=True)
        _, before, _ = f.reply(1)
        self.assertIn(ACTION, [row['action'] for row in before['candidates']])
        _, after, receipt = f.reply(2, ACTION)
        self.assertEqual(receipt['status'], 'completed')
        self.assertFalse(after['city_state_peace']['targets'][0]['at_war'])
        self.assertEqual(f.player, 0)

    def test_foreign_sender_refuses_before_delivery(self):
        f = self.fixture()
        f.reply(1)
        f.sender = 0
        with self.assertRaisesRegex(RuntimeError, 'archive differs from native sender'):
            f.reply(2, ACTION)
        self.assertTrue(f.at_war)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

    def test_contract_cannot_inject_an_unoffered_target(self):
        f = self.fixture()
        observation, decisions, _ = f.reply(1)
        fake = dict(ACTION, target_player_id=3)
        choices = decisions['families']['diplomacy_initiate']['candidate_ids']
        choices.append(network_turn.digest(fake))
        decisions['candidates'].append(dict(candidate_id=choices[-1], action=fake))
        del decisions['decision_id']
        decisions['decision_id'] = network_turn.digest(decisions)
        with self.assertRaisesRegex(ValueError, 'differs from its offers'):
            network_turn.validate_catalogue(decisions, f.token.identity, 1, 8, player_id=1,
                                            observation=observation)

"""Great Person activation through the authenticated secondary LAN actor."""

from struct import pack
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import great_person_activation as public
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
from civ6_host.runtime import xp1_great_person_activation as activation
from civ6_host.runtime import xp2_great_person_activation_source as source
from test_xp2_lan_trade import TradeFixture


ACTION = dict(kind=public.KIND, unit_id=28, x=3, y=1)


class ActivationFixture(TradeFixture):
    def __init__(self):
        super().__init__(stock=True)
        self.saved.xp2_great_person_activation = True
        self.saved.explicit_great_person_activation = {'primary': 'retained'}
        self.charges = 2
        self.consume_charge = True
        self.archive_player = 1
        self.activation_requests = 0
        self.activation_queued = False
        self.stack.enter_context(patch.object(source, 'bind_prefix', side_effect=self.bind_activation))
        self.stack.enter_context(patch.object(activation, '_post_command', side_effect=self.activation_marker))

    def bind_activation(self, prefix, *, action=False):
        assert prefix is self.saved.prefix and self.player == 1

    def activation_marker(self, prefix, player, unit):
        assert prefix is self.saved.prefix and self.player == player == 1 and unit == 28
        assert not self.activation_queued
        return prefix.deferred_events.consumed_count + 1

    def evaluate(self, child, source_text, tag, **options):
        if tag not in (b'@explicit_xp1_gp_activation_catalogue', b'@explicit_xp1_gp_activation_request'):
            return super().evaluate(child, source_text, tag, **options)
        assert child is self.token.ui_child and self.player == 1
        assert b'local pid,turn=1,8' in source_text
        if tag == b'@explicit_xp1_gp_activation_catalogue':
            return f'28|3|1|173|6|{self.charges}|1|1'.encode('ascii')
        self.activation_requests += 1
        self.activation_queued = True
        self.token.transport.pending.append(pack('<IHHIII', 0x493830af, self.archive_player, 1, 28, 7, 0))
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or not self.activation_queued:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            self.activation_queued = False
            if self.consume_charge:
                self.charges -= 1
        return drain


class SecondaryActivationTests(TestCase):
    def fixture(self):
        fixture = ActivationFixture()
        self.addCleanup(fixture.close)
        return fixture

    def test_activation_checks_exact_seat_choice_effect_and_checkpoint_scope(self):
        f = self.fixture()
        obs, choices, _ = f.reply(1)
        self.assertEqual(public.actions(project('great_person_activation', obs, choices)), [ACTION])
        f.charges = 1
        _, _, receipt = f.reply(2, ACTION)
        self.assertEqual(receipt['reason'], activation.OFFER_CHANGED)
        self.assertEqual(f.activation_requests, 0)

        obs, choices, receipt = f.reply(3, ACTION)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=ACTION))
        self.assertEqual(project('great_person_activation', obs, choices)['units'][0]['charges'], 0)
        self.assertEqual(f.player, 0)
        self.assertEqual(f.saved.explicit_great_person_activation, {'primary': 'retained'})

        boundary = xp1_session_checkpoint.boundary(f.saved)
        options = dict(decision_players=(1,))
        current = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), **options)
        old = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1),
                                                   great_person_activation_enabled=False, **options)
        self.assertIs(current['great_person_activation_enabled'], True)
        self.assertNotIn('great_person_activation_enabled', old)
        self.assertEqual(current['players'][0], old['players'][0])
        self.assertNotEqual(current['players'][1]['decisions_sha256'], old['players'][1]['decisions_sha256'])
        state = dict(observation=f.token.observation, decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary)
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (old, current):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))

    def test_strategic_gate_keeps_secondary_activation_unavailable(self):
        f = self.fixture()
        f.strategic_allowed = False
        _, choices, _ = f.reply(1)
        self.assertIsNone(choices['great_person_activation'])
        self.assertEqual(choices['families'][public.KIND], dict(status='unqualified', reason=activation.UNAVAILABLE))
        self.assertFalse(any(row['action']['kind'] == public.KIND for row in choices['candidates']))
        self.assertEqual(f.activation_requests, 0)

    def test_processed_without_effect_stays_submitted(self):
        f = self.fixture()
        f.reply(1)
        f.consume_charge = False
        _, _, receipt = f.reply(2, ACTION)
        self.assertEqual(receipt, dict(status='submitted', reason=activation.UNCONFIRMED, requested_action=ACTION))
        self.assertEqual(f.player, 0)

    def test_foreign_archive_never_reaches_delivery(self):
        f = self.fixture()
        f.reply(1)
        f.archive_player = 0
        with self.assertRaisesRegex(RuntimeError, 'archive lost its owned unit'):
            f.reply(2, ACTION)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

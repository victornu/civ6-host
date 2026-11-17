"""Check the secondary-seat governor API against the retained XP2 wire format."""

from copy import deepcopy
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import governors, network_turn
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
from civ6_host.runtime import network_timer, xp2_governors_source, xp2_lan_unit_commands
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native import native_player_operation_request
from test_xp2_governors import _catalogue, _wire
from test_xp2_lan_secondary_commands import SecondaryPurchaseFixture


class SecondaryGovernorFixture(SecondaryPurchaseFixture):
    def __init__(self, kind):
        super().__init__()
        self.saved.governors_diagnostic = True
        self.token.explicit_governors = {'primary': 'retained'}
        self.kind = kind
        self.applied = False
        self.stale = False
        self.refused = False
        self.archive_sender = 1
        self.requests = []
        self.publications = []
        self.governor_pending = False
        publisher = self.token.publisher
        publish = publisher.publish

        def publish_governors():
            self.publications.append(self.player)
            return publish()

        self.stack.enter_context(patch.object(publisher, 'publish', side_effect=publish_governors))
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        self.stack.enter_context(patch.object(xp2_governors_source, 'bind_owner'))
        self.stack.enter_context(patch.object(xp2_governors_source, 'support_source', return_value=b'-- fixture'))
        self.stack.enter_context(patch.object(native_player_operation_request, 'request_player_operation',
                                             side_effect=self.request_governor))
        self.protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=self.token.identity,
                                        session={'turn': 8}, catalogues={})
        self.protocol.selected = lambda request: network_turn.select_capability(
            self.protocol.catalogues[1], request['selection'])

    def evaluate(self, child, source, name, **kw):
        if name == b'@xp2_governor_catalogue':
            assert (self.player, child) == (1, self.token.ui_child)
            assert b'local pid=1; local expectedTurn=8' in source
            value = _catalogue(self.kind, phase='after' if self.applied else 'before')
            value.update(player_id=1, current_game_turn=8)
            if self.stale:
                value['can_appoint'] = False
            return _wire(value)
        if name == b'@xp2_governor_title_consideration':
            assert (self.player, child, self.kind) == (1, self.token.ui_child, 'consider_governor_titles')
            self.applied = True
            return b'considered'
        return super().evaluate(child, source, name, **kw)

    def request_governor(self, core, context, pid, operation, parameters, *, core_sha256):
        assert (core, context, pid, self.player) == (self.backend.core, self.backend.context, 1, 1)
        assert core_sha256 == XP2_CORE_SHA256
        op, args = {
            'appoint_governor': (0xa68659ab, {0xaf5e1625: 4}),
            'assign_governor': (0xf97c278b, {0xaf5e1625: 4, 0x0483191c: 0, 0xe5f2cf9b: 12}),
            'promote_governor': (0x7d3da99d, {0xaf5e1625: 4, 0x6d4bd4ea: 2}),
        }[self.kind]
        assert (operation, parameters) == (op, args)
        self.requests.append((pid, op))
        if self.refused:
            return dict(can_start=False, request_invoked=False)
        payload = pack('<6I', 0xc45de12f, self.archive_sender, op, 2, 0x80000001, len(args))
        payload += b''.join(pack('<IHH10xI', k, 0, 2, v) for k, v in args.items())
        self.token.transport.pending.append(payload)
        self.governor_pending = True
        return dict(can_start=True, request_invoked=True)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or not self.governor_pending:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            self.governor_pending = False
            self.applied = True
        return drain

    def reply(self, sequence, action=None):
        request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
        if action is not None:
            request['selection'] = dict(decision_id=self.protocol.catalogues[1]['decision_id'],
                                        candidate_id=network_turn.digest(action))
        _, session, observation, decisions, receipt = xp2_lan_unit_commands.read_reply(
            self.saved, self.protocol, request, (0, 1))
        network_turn.validate_catalogue(decisions, self.token.identity, sequence, 8,
                                        player_id=1, observation=observation)
        self.protocol.session, self.protocol.catalogues[1] = session, decisions
        return decisions, receipt


class SecondaryGovernorTests(TestCase):
    def test_all_four_public_gestures_use_the_secondary_seat_and_verify_the_effect(self):
        for kind in governors.ACTION_FIELDS:
            with self.subTest(kind=kind):
                f = SecondaryGovernorFixture(kind)
                try:
                    before, _ = f.reply(1)
                    action, = governors.actions(before['governors'])
                    self.assertIn(action, [row['action'] for row in before['candidates']])
                    f.publications.clear()
                    after, receipt = f.reply(2, action)
                    self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=action))
                    self.assertNotEqual(after['governors'], before['governors'])
                    self.assertEqual(f.publications, [1, 1, 0])
                    self.assertEqual(len(f.requests), int(kind != 'consider_governor_titles'))
                    self.assertEqual((f.player, f.token.observation['player_id']), (0, 0))
                    self.assertEqual(f.token.explicit_governors, {'primary': 'retained'})
                finally:
                    f.close()

    def test_stale_choice_and_native_refusal_keep_the_owner_and_block_wrong_sender(self):
        f = SecondaryGovernorFixture('appoint_governor')
        self.addCleanup(f.close)
        before, _ = f.reply(1)
        action, = governors.actions(before['governors'])
        f.stale = True
        after, receipt = f.reply(2, action)
        self.assertEqual(receipt['reason'], 'native_governor_choice_changed')
        self.assertFalse(f.requests)
        self.assertEqual(governors.actions(after['governors']), [])
        f.stale = False
        f.reply(3)
        f.refused = True
        f.publications.clear()
        _, receipt = f.reply(4, action)
        self.assertEqual(receipt['reason'], 'native_governor_can_start_false')
        self.assertEqual((f.player, f.publications), (0, [1, 0]))
        f.refused = False
        f.archive_sender = 0
        with self.assertRaisesRegex(RuntimeError, 'archive header differs'):
            f.reply(5, action)
        self.assertFalse(f.applied)

    def test_checkpoint_recompares_governors_and_preserves_previous_receipts(self):
        f = SecondaryGovernorFixture('assign_governor')
        self.addCleanup(f.close)
        before, _ = f.reply(1)
        action, = governors.actions(before['governors'])
        f.reply(2, action)
        saved = f.saved
        boundary = xp1_session_checkpoint.boundary(saved)
        live = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
        old = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                  governors_enabled=False)
        self.assertIs(live['governors_enabled'], True)
        self.assertNotIn('governors_enabled', old)
        self.assertNotEqual(live['players'][1]['decisions_sha256'], old['players'][1]['decisions_sha256'])
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary, host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (live, old):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        f.applied = False
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=live)):
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(saved, f.token.observation)

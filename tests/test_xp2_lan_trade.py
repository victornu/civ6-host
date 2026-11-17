"""Secondary LAN trade through the retained perspective and command transport."""

from copy import deepcopy
import json
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from civ6_host.contracts import network_turn, trade
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, network_timer, player_views, xp1_session_checkpoint
from civ6_host.runtime import xp2_lan_production, xp2_lan_unit_commands, xp2_trade
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native import native_locale_arguments
from civ6_host.runtime.native.native_saved_trade import literal
from civ6_host.runtime.network_protocol import NetworkProtocol
from test_xp2_human_perspective import PerspectiveFixture


class TradeFixture(PerspectiveFixture):
    def __init__(self, *, stock=False):
        super().__init__()
        self.enable_turn_fixture()
        self.enable_research_fixture()
        self.turn_rows[2] = (0, 0, 0)
        self.saved.standard_trade = stock
        self.saved.trade_diagnostic = not stock
        self.flush = Mock(return_value=[])
        if not stock:
            self.token.trade_feedback = SimpleNamespace(flush=self.flush, secondary_spy_completions={})
        self.token._xp2_trade_catalogue = {'primary': 'kept'}
        self.token.explicit_trade_routes = {'primary': 'kept'}
        self.attach = self.stack.enter_context(patch.object(native_locale_arguments, 'attach'))
        self.stack.enter_context(patch.object(xp2_lan_production, 'read', return_value=None))
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        self.stack.enter_context(patch.object(xp2_trade, 'source_dependencies', return_value={}))
        self.stack.enter_context(patch.object(xp2_trade, '_bbg_display', return_value=False))
        self.running = False
        self.submitted = None
        self.sender = 1
        self.route_gold = 2
        observation = self.observations[1]
        self.source_city = 65544
        self.relocation_city = 65545
        observation['units'][0].update(x=3, y=1)
        yields = dict(food=0, production=0, gold=0, science=0, culture=0, faith=0)
        observation['cities'] = [
            dict(id=self.source_city, owner=1, x=3, y=1, population=1, yields=yields),
            dict(id=self.relocation_city, owner=1, x=5, y=2, population=1, yields=yields),
        ]
        self.protocol = NetworkProtocol(self.token.identity, 'a' * 32, initial_turn=8,
                                        core_sha256=XP2_CORE_SHA256)
        self.protocol.session = {'turn': 8}

    def states(self):
        obs = self.observations[1]
        width = obs['width']
        base = dict(player_id=1, turn=8, width=width, height=obs['height'])
        active = dict(unit_id=28, origin_owner=1, origin_city=self.source_city,
                      destination_owner=2, destination_city=96)
        yields = dict(values=[0, 0, self.route_gold], majority_religion=-1,
                      religion_pressure=-1, path_bonus=False, tooltip='')
        destination = dict(owner=2, city_id=96, x=6, y=1, name='Known city',
                           path=[width + x for x in (3, 4, 5, 6)],
                           portal_entrances=[], portal_exits=[], repeat_route=False, can_confirm=True,
                           has_post=False, origin_yields=yields, destination_yields=yields)
        trader = dict(unit_id=28, x=3, y=1, origin_owner=1, origin_city=self.source_city,
                      destinations=[destination])
        second = dict(city_id=self.relocation_city, x=5, y=2, plot_id=2 * width + 5, name='Own city')
        origin = dict(unit_id=28, origin_city=self.source_city, x=3, y=1, available=True,
                      targets=[second], map_targets=[second['plot_id']])
        available = bool(obs['units'][0]['moves']) and not self.running
        return (dict(base, traders=[trader] if available else [],
                     active_routes=[active] if self.running else []),
                dict(base, units=[origin] if available else []))

    def evaluate(self, child, source, name, **options):
        route = name in (b'@explicit_trade_catalog', b'@xp2_trade_route_request')
        origin = name in (b'@explicit_trade_origin', b'@xp2_trade_origin_request')
        if not (route or origin):
            return super().evaluate(child, source, name, **options)
        assert self.player == 1 and child is self.token.ui_child and b'local pid,turn=1,8' in source
        routes, origins = self.states()
        if name.startswith(b'@explicit'):
            return json.dumps(routes if route else origins).encode()
        action, = trade.route_actions(routes) if route else trade.origin_actions(origins)
        assert f'local selected={literal(action)}'.encode() in source
        self.submitted = action
        if route:
            archive = pack('<IHH12I', 0x8c0f3f36, self.sender, 1, 28, 18, 0xffffffff, 0, 1, 0,
                           6, 1, 3, 1, 0xffffffff, 0)
        else:
            archive = pack('<IHH9I', 0x8c0f3f36, self.sender, 1, 28, 51, 0xffffffff, 0, 1, 5, 2, 0, 0)
        self.token.transport.pending.append(archive)
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.submitted is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            if self.submitted['kind'] == 'make_trade_route':
                self.running = True
            else:
                self.observations[1]['units'][0].update(x=5, y=2, moves=0)
            self.submitted = None
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
        self.protocol.observations[1] = observation
        return observation, decisions, receipt


class SecondaryTradeTests(TestCase):
    def fixture(self, **options):
        f = TradeFixture(**options)
        self.addCleanup(f.close)
        return f

    def test_selected_route_uses_native_feedback_and_exact_outgoing_readback(self):
        f = self.fixture()
        observation, decisions, _ = f.reply(1)
        action, = trade.route_actions(project('trade', observation, decisions)['routes'])
        f.route_gold = 4
        _, _, refused = f.reply(2, action)
        self.assertEqual(refused['reason'], 'native_trade_choice_changed')
        self.assertFalse(f.running)
        observation, decisions, receipt = f.reply(3, action)
        self.assertEqual(receipt['status'], 'completed')
        active, = project('trade', observation, decisions)['routes']['active_routes']
        self.assertEqual((active['origin_owner'], active['destination_owner']), (1, 2))
        f.flush.assert_called_once()
        self.assertEqual(f.player, 0)
        self.assertEqual(f.token.explicit_trade_routes, {'primary': 'kept'})

    def test_relocation_and_legacy_checkpoint_scope(self):
        f = self.fixture(stock=True)
        observation, decisions, _ = f.reply(1)
        action, = trade.origin_actions(project('trade', observation, decisions)['origins'])
        observation, _, receipt = f.reply(2, action)
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual((observation['units'][0]['x'], observation['units'][0]['y']), (5, 2))
        f.flush.assert_not_called()
        boundary = xp1_session_checkpoint.boundary(f.saved)
        live = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,))
        old = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,),
                                                  trade_enabled=False)
        self.assertIs(live['trade_enabled'], True)
        self.assertNotIn('trade_enabled', old)
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary)
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (live, old):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))

    def test_foreign_native_sender_is_refused_before_delivery(self):
        f = self.fixture(stock=True)
        f.strategic_allowed = False
        observation, decisions, _ = f.reply(1)
        panel = project('trade', observation, decisions)
        self.assertIsNone(panel['origins'])
        action, = trade.route_actions(panel['routes'])
        f.sender = 0
        with self.assertRaisesRegex(RuntimeError, 'Trade archive differs'):
            f.reply(2, action)
        self.assertFalse(f.running)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

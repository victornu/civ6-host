"""Secondary LAN espionage, with native boundaries backed by saved receipts."""

from copy import deepcopy
import json
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import espionage, network_turn
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, network_timer, player_views, xp1_session_checkpoint
from civ6_host.runtime import xp2_lan_unit_commands
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_saved_trade import literal
from test_xp2_lan_secondary_commands import SecondaryPurchaseFixture


MISSION = dict(kind='spy_mission', mode='counterspy', unit_id=28, x=3, y=0, plot_id=3,
               operation_hash=2289040593, operation_type='UNITOPERATION_SPY_COUNTERSPY')
CANCEL = dict(kind='spy_cancel', unit_id=28)


class EspionageFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        self.saved.espionage_diagnostic = True
        self.token.explicit_espionage = {'primary': 'retained'}
        self.token.trade_feedback = SimpleNamespace(flush=lambda: [])
        self.running = False
        self.submitted = None
        self.confirm = True
        self.refused = False
        self.hide = False
        self.sender = 1
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        self.protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=self.token.identity,
                                        session={'turn': 8}, catalogues={})
        self.protocol.selected = lambda request: network_turn.select_capability(
            self.protocol.catalogues[1], request['selection'])

    def evaluate(self, child, source, name, **options):
        labels = (b'@explicit_espionage_catalog', b'@xp2_espionage_request', b'@explicit_espionage_effect')
        if name not in labels:
            return super().evaluate(child, source, name, **options)
        assert child is self.token.ui_child and self.player == 1 and b'local pid,turn=1,8' in source
        obs = self.observations[1]
        action = CANCEL if self.running else MISSION
        if name == b'@explicit_espionage_catalog':
            offers = [] if self.hide else [dict(action=action, turns=4, success_percent=-1,
                                                failure_percent=-1, captured_or_killed_percent=-1)]
            state = dict(schema=espionage.SCHEMA, player_id=1, turn=8, capacity=1,
                width=obs['width'], height=obs['height'], captured=[], off_map=[], history=[], offers=offers,
                spies=[dict(unit_id=28, name='Local spy', level=1, x=3, y=0,
                            operation=39 if self.running else -1, turns_remaining=4 if self.running else -1)])
            return json.dumps(state).encode()
        if name == b'@xp2_espionage_request':
            assert f'local selected={literal(action)}'.encode() in source
            if self.refused:
                return b'refused'
            self.submitted = action['kind']
            if action is CANCEL:
                archive = pack('<IHH3I', 0x493830af, self.sender, 1, 28, 1, 0)
            else:
                archive = pack('<IHH9I', 0x8c0f3f36, self.sender, 1, 28, 39, 0xffffffff, 0, 1, 3, 0, 0, 0)
            self.token.transport.pending.append(archive)
            return b'submitted'
        assert b'local selected,old=' in source
        selected, = (item for item in (MISSION, CANCEL)
                     if f'local selected,old={literal(item)},'.encode() in source)
        selected_kind = selected['kind']
        return json.dumps(dict(schema='civ6-host.espionage-effect.v1', player_id=1, turn=8,
            kind=selected_kind, unit_id=28, confirmed=self.confirm,
            expected_operation=39 if selected_kind == 'spy_mission' else -1)).encode()

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.submitted is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            if self.confirm:
                self.running = self.submitted == 'spy_mission'
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
        return observation, decisions, receipt


class SecondaryEspionageTests(TestCase):
    def test_start_cancel_compares_the_secondary_scope_and_preserves_old_receipts(self):
        f = EspionageFixture()
        self.addCleanup(f.close)
        f.strategic_allowed = False
        obs, decisions, _ = f.reply(1)
        self.assertIsNone(decisions['unit_orders'])
        self.assertEqual(espionage.actions(project('espionage', obs, decisions)), [MISSION])
        obs, decisions, receipt = f.reply(2, MISSION)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=MISSION))
        self.assertEqual(espionage.actions(project('espionage', obs, decisions)), [CANCEL])
        obs, decisions, receipt = f.reply(3, CANCEL)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=CANCEL))
        self.assertEqual(project('espionage', obs, decisions)['spies'][0]['operation'], -1)
        self.assertEqual((f.player, f.token.observation['player_id']), (0, 0))
        self.assertEqual(f.token.explicit_espionage, {'primary': 'retained'})

        boundary = xp1_session_checkpoint.boundary(f.saved)
        live = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,))
        old = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,),
                                                  espionage_enabled=False)
        self.assertIs(live['espionage_enabled'], True)
        self.assertNotIn('espionage_enabled', old)
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary, host_secondary_world_selections=[])
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (live, old):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))
        f.running = True
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=live)):
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(f.saved, f.token.observation)

    def test_revalidates_offer_and_distinguishes_native_submission_from_effect(self):
        f = EspionageFixture()
        self.addCleanup(f.close)
        f.reply(1)
        f.hide = True
        _, _, receipt = f.reply(2, MISSION)
        self.assertEqual(receipt['status'], 'refused')
        self.assertIsNone(f.submitted)
        f.hide = False
        f.reply(3)
        f.refused = True
        _, _, receipt = f.reply(4, MISSION)
        self.assertEqual(receipt['reason'], 'native_spy_choice_unavailable')
        self.assertIsNone(f.submitted)
        f.refused = False
        f.confirm = False
        _, _, receipt = f.reply(5, MISSION)
        self.assertEqual(receipt['status'], 'submitted')
        self.assertFalse(f.running)
        f.sender = 0
        with self.assertRaisesRegex(RuntimeError, 'selected route or actor'):
            f.reply(6, MISSION)
        self.assertFalse(f.running)

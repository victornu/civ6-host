"""Exercise native event ownership, secondary decisions and renewal delivery."""

from copy import deepcopy
import json
from struct import pack
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.contracts import spy_completion
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
from civ6_host.runtime.native import native_spy_completion
from civ6_host.runtime.xp1_continuation import ACTIVE, READY
from civ6_host.runtime.xp2_bbg_trade_feedback import TradeFeedback
from civ6_host.runtime.xp2_spy_completion import CompletionQueue
from test_xp2_lan_espionage import EspionageFixture, MISSION


class CompletionFixture(EspionageFixture):
    def __init__(self):
        super().__init__()
        self.feedback = TradeFeedback(self.token, None, None, spy_event_players=(0, 1))
        self.feedback._deliver_spy = Mock()
        self.primary = self.feedback.spy_completions = CompletionQueue(self.token, player_id=0)
        self.secondary = self.feedback.secondary_spy_completions[1] = CompletionQueue(self.token, player_id=1)
        self.token.trade_feedback = self.feedback
        self.token.explicit_spy_completion = {'primary': 'retained'}
        self.displays = []
        self.order_reads = []

    def receive(self, *events):
        with self.saved._attempt():
            self.backend.stage, self.backend.busy = ACTIVE, True
            for sequence, owner, mission in events:
                self.feedback.spy(sequence, owner, mission)
            self.feedback.flush()
            self.backend.stage, self.backend.busy = READY, False
            self.saved._finish('commands')

    def evaluate(self, child, source, name, **options):
        if name == b'@spy_completion_display':
            assert b'foreign completion event seat' in source
            header = source.split(b'local pid,missionID,eventSequence=')[1].splitlines()[0]
            player, mission, event = map(int, header.split(b','))
            self.displays.append((self.player, player, mission, event))
            return b'suppressed' if mission == 52 else b'shown'
        if name == b'@bbg751_trade_buffer_count':
            return b'0'
        if name not in (b'@spy_completion_catalog', b'@xp2_spy_completion_request', b'@spy_completion_effect',
                        b'@spy_completion_order_state'):
            return super().evaluate(child, source, name, **options)
        assert child is self.token.ui_child and self.player == 1 and b'local pid,turn=1,8' in source
        observation = self.observations[1]
        if name == b'@spy_completion_catalog':
            occurrence = self.secondary.current
            current, offers = None, []
            if occurrence is not None:
                current = dict(occurrence, name='Local spy', level=1, operation=39,
                    completion_turn=8, initial_result=1, escape_result=0, city_name='Own city', plot_id=3, loot_info=-1)
                actions = [dict(kind='spy_completion_dismiss', **occurrence), dict(
                    occurrence, kind='spy_renew', unit_id=28, x=3, y=0, plot_id=3,
                    operation_hash=MISSION['operation_hash'], operation_type=MISSION['operation_type'])]
                offers = [dict(action=action, turns=-1, success_percent=-1,
                    failure_percent=-1, captured_or_killed_percent=-1) for action in actions]
            return json.dumps(dict(schema=spy_completion.SCHEMA, player_id=1, turn=8, current=current,
                width=observation['width'], height=observation['height'], offers=offers)).encode()
        if name == b'@xp2_spy_completion_request':
            if self.refused:
                return b'refused'
            self.requested = self.secondary.current
            self.submitted = 'spy_mission'
            self.token.transport.pending.append(
                pack('<IHH9I', 0x8c0f3f36, self.sender, 1, 28, 39, 0xffffffff, 0, 1, 3, 0, 0, 0))
            return b'submitted'
        if name == b'@spy_completion_order_state':
            self.order_reads.append(39 if self.running else -1)
            return json.dumps(dict(player_id=1, turn=8, unit_id=28, expected_operation=39,
                operation=self.order_reads[-1], turns_remaining=4 if self.running else 0)).encode()
        assert self.secondary.current != self.requested, 'Renewal must close the original result before delivery'
        return json.dumps(dict(self.requested, player_id=1, turn=8, unit_id=28,
                               operation=39, applied=self.confirm)).encode()


class SecondaryCompletionTests(TestCase):
    def test_each_human_retains_own_occurrences_and_reloads_only_settled_choices(self):
        f = CompletionFixture()
        self.addCleanup(f.close)
        f.receive((1, 0, 9), (2, 1, 51), (3, 1, 53), (4, 1, 52), (5, 2, 99))
        self.assertEqual(f.displays, [(0, 0, 9, 1), (0, 1, 51, 2)])
        self.assertEqual(f.feedback._deliver_spy.call_count, 5)
        f.primary.close(f.primary.visible())
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            f.feedback.check_checkpoint()
        observation, decisions, _ = f.reply(1)
        first = project('spy_completion', observation, decisions)
        self.assertEqual(first['current']['mission_id'], 51)
        _, renew = spy_completion.actions(first)
        f.refused = True
        _, unchanged, receipt = f.reply(2, renew)
        self.assertEqual(receipt['status'], 'refused')
        self.assertEqual(unchanged['spy_completion'], first)
        f.refused = False
        observation, decisions, receipt = f.reply(3, renew)
        self.assertEqual(receipt['status'], 'completed')
        self.assertTrue(f.running)
        self.assertIsNone(project('spy_completion', observation, decisions)['current'])
        self.assertEqual(f.displays[-1], (1, 1, 52, 4))
        self.assertEqual(f.secondary.pending, [dict(event_sequence=3, mission_id=53)])
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            f.feedback.check_checkpoint()
        f.receive((6, 1, 54))
        _, decisions, _ = f.reply(4)
        dismiss, _ = spy_completion.actions(decisions['spy_completion'])
        _, decisions, receipt = f.reply(5, dismiss)
        self.assertEqual(receipt['status'], 'completed')
        self.assertIsNone(f.submitted)
        self.assertEqual(decisions['spy_completion']['current']['mission_id'], 53)
        dismiss, _ = spy_completion.actions(decisions['spy_completion'])
        f.reply(6, dismiss)
        f.feedback.check_checkpoint()
        self.assertEqual(f.token.explicit_spy_completion, {'primary': 'retained'})
        boundary = xp1_session_checkpoint.boundary(f.saved)
        current = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,))
        previous = player_views.checkpoint_view_digests(
            f.saved, boundary, (0, 1), decision_players=(1,), spy_completion_enabled=False)
        self.assertIs(current['spy_completion_enabled'], True)
        self.assertNotIn('spy_completion_enabled', previous)
        self.assertNotEqual(current['players'][1]['decisions_sha256'], previous['players'][1]['decisions_sha256'])
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary, host_secondary_world_selections=[])
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (current, previous):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))
        self.assertEqual(f.player, 0)

    def test_wrong_sender_never_dismisses_or_delivers_a_renewal(self):
        f = CompletionFixture()
        self.addCleanup(f.close)
        f.receive((1, 1, 51),)
        _, decisions, _ = f.reply(1)
        _, renew = spy_completion.actions(decisions['spy_completion'])
        f.sender = 0
        with self.assertRaisesRegex(RuntimeError, 'selected route or actor'):
            f.reply(2, renew)
        self.assertFalse(f.running)
        self.assertEqual(f.secondary.current, dict(event_sequence=1, mission_id=51))

    def test_waiting_player_can_clear_and_renew_current_results(self):
        f = CompletionFixture()
        self.addCleanup(f.close)
        f.turn_rows[1] = (0, 0, 0)
        observation, decisions, _ = f.reply(1)
        self.assertIsNone(decisions['espionage'])
        self.assertIsNone(decisions['spy_completion'])
        f.receive((1, 1, 51), (2, 1, 53))
        observation, decisions, _ = f.reply(2)
        dismiss, _ = spy_completion.actions(project('spy_completion', observation, decisions))
        observation, decisions, receipt = f.reply(3, dismiss)
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(f.order_reads, [])
        _, renew = spy_completion.actions(project('spy_completion', observation, decisions))
        _, decisions, receipt = f.reply(4, renew)
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(f.order_reads, [-1, 39])
        self.assertIsNone(decisions['espionage'])
        self.assertIsNone(decisions['spy_completion'])
        self.assertEqual(f.turn_rows[1], (0, 0, 0))
        f.feedback.check_checkpoint()

    def test_display_checks_own_mission_and_native_activity_at_delivery_time(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(b'''
Game = { GetLocalPlayer = function() return 0 end }
local player = {}
active, human, operation = false, true, 4
function player:IsHuman() return human end
function player:GetID() return 1 end
function player:IsTurnActive() return active end
function player:GetDiplomacy()
  return { GetMission = function(_,pid,id)
    assert(pid==1 and id==51)
    return {Operation=operation}
  end }
end
Players = { [1]=player }
UnitOperationTypes = { SPY_COUNTERSPY=13 }
GameInfo = { UnitOperations = { [4]={Hash=13}, [5]={Hash=19} } }
''')
        with patch.object(native_spy_completion, 'verify_source', return_value={}):
            local = native_spy_completion.display_source(1, 51, 2)
            captured = native_spy_completion.display_source(1, 51, 2, event_seat=True)
        with self.assertRaises(LuaError):
            lua.execute(local)
        self.assertEqual(lua.execute(captured), b'suppressed')
        lua.execute(b'operation=5')
        self.assertEqual(lua.execute(captured), b'shown')
        lua.execute(b'human=false')
        with self.assertRaises(LuaError):
            lua.execute(captured)

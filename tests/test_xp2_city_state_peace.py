from copy import deepcopy
import json
from struct import pack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import diplomacy_overview as contract, network_turn
from civ6_host.runtime import xp2_city_state_peace as peace, xp2_diplomacy_overview as adapter
import test_initial_diplomacy_capabilities as fixture_module
from test_xp2_military_levy_catalogue import FIXTURES, XP2MilitaryLevyCatalogueTests

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


ACTION = dict(kind='diplomacy_initiate', target_player_id=3, choice=contract.MAKE_PEACE)
PEACE_PANEL = dict(military_enabled=True, targets=[dict(player_id=3, at_war=True, can_make_peace=True)])
LUA = '''
local actor=0
local diplom={
 HasMet=function(_,id) return id~=5 end,
 IsAtWarWith=function(_,id) assert(id==3 or id==4); return id==3 end,
 CanMakePeaceWith=function(_,id) assert(id==3); return true end}
local function yes() return true end
local function minor(id)
 return {GetID=function() return id end, GetInfluence=function()
  assert(id~=5, 'unmet minor read')
  return {CanReceiveInfluence=function() return id~=6 end}
 end}
end
Game={GetLocalPlayer=function() return actor end, GetLocalObserver=function() return actor end,
 GetCurrentGameTurn=function() return 8 end, IsAllowStrategicCommands=yes}
GameCapabilities={HasCapability=function(name) assert(name=='CAPABILITY_MILITARY'); return true end}
Players={[0]={IsAlive=yes, IsTurnActive=yes, IsTurnActiveComplete=yes,
 GetDiplomacy=function() return diplom end}}
PlayerManager={GetAliveMinors=function() return {minor(6),minor(4),minor(5),minor(3)} end}
'''


def stock_overview(pid, turn, *, major=2):
    choice = dict(key=contract.MAKE_PEACE, disabled=False, supported=True,
                  text=None, tooltip=None, diplomatic_action_type=None)
    return dict(schema=contract.STOCK_PROMISE_STATUS_SCHEMA, player_id=pid, turn=turn,
                capability=True, paused=False, complete_action_space=False,
                targets=[dict(player_id=major, selections=[choice], relationship=None, active_promises=[])],
                major_deals=[dict(player_id=major, pending=False, terms=[], counterparty_is_human=False,
                                  open_borders=dict(outgoing=False, incoming=False))])


class CityStatePeaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_module.InitialDiplomacyCapabilityTests.setUpClass()
        cls.fixture = fixture_module.InitialDiplomacyCapabilityTests()

    def test_public_action_and_historical_checkpoint(self):
        v1, observation = self.fixture._active_v33()
        v2 = deepcopy(v1)
        old_overview = v2['diplomacy_overview']
        old_overview['schema'] = contract.RELATIONSHIPS_SCHEMA
        for row in old_overview['targets']:
            row['relationship'] = None
        self.fixture._redigest(v2)
        current = deepcopy(v2)
        overview = current['diplomacy_overview']
        overview.update(schema=contract.CITY_STATE_PEACE_SCHEMA, city_state_peace=deepcopy(PEACE_PANEL))
        row = dict(action=ACTION, candidate_id=network_turn.digest(ACTION))
        current['candidates'].append(row)
        current['families']['diplomacy_initiate']['candidate_ids'].append(row['candidate_id'])
        self.fixture._redigest(current)
        self.fixture._validate(current, observation)
        self.assertIn(ACTION, contract.candidates(overview))
        for earlier in (v1, v2):
            projected, transition = network_turn.checkpoint_catalogue(
                current, earlier, observation, core_sha256=fixture_module.XP2_CORE)
            self.assertEqual(projected, earlier)
            self.assertEqual(transition['added_action_variants'], ['diplomacy_initiate.city_state_peace'])
        self.assertEqual(contract.candidates(dict(overview, paused=True)), [])
        invalid = deepcopy(overview)
        invalid['targets'][0]['selections'].append(self.fixture._selection(contract.MAKE_PEACE))
        with self.assertRaises(ValueError):
            contract.candidates(invalid)

    @unittest.skipIf(LuaRuntime is None, 'Lua fixture unavailable')
    def test_only_met_city_states_with_influence_are_read(self):
        lua = LuaRuntime()
        lua.execute(LUA)
        wire = lua.execute(peace._source_at(0, 8, peace._PANEL).decode('ascii'))
        actual = json.loads(wire)
        self.assertEqual(actual, dict(military_enabled=True, targets=[
            PEACE_PANEL['targets'][0], dict(player_id=4, at_war=False, can_make_peace=False)]))

    def test_application_requires_an_offer_and_verified_game_effect(self):
        overview = dict(self.fixture._overview(), schema=contract.CITY_STATE_PEACE_SCHEMA,
                        targets=[], city_state_peace=deepcopy(PEACE_PANEL))
        archive = pack('<6I', 0xc45de12f, 0, 0x11, 2, 0x80000001, 2)
        archive += pack('<IHH10xI', 0x12, 0, 2, 0) + pack('<IHH10xI', 0x13, 0, 2, 3)
        prefix = SimpleNamespace(runtime=Mock(), ui_child=9, actions=Mock(),
                                 deferred_events=Mock(), view_publisher=Mock())
        prefix.actions.pending = []
        prefix.runtime.evaluate_text.return_value = b'[17,18,19]'
        backend, saved = Mock(), Mock()
        with patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation') as request:
            rejected = peace.apply(saved, backend, prefix, dict(ACTION, target_player_id=2), overview)
            self.assertEqual(rejected['status'], 'refused')
            request.assert_not_called()
            request.return_value = dict(request_invoked=False)
            self.assertEqual(peace.apply(saved, backend, prefix, ACTION, overview)['status'], 'refused')
            prefix.actions.deliver_one.assert_not_called()

            def fake_native_request(*args, **_):
                self.assertEqual(args[2:], (0, 17, {18: 0, 19: 3}))
                prefix.actions.pending.append(archive)
                return dict(request_invoked=True)

            request.side_effect = fake_native_request
            prefix.actions.deliver_one.side_effect = prefix.actions.pending.pop
            with patch.object(peace, 'panel', return_value=PEACE_PANEL):
                with self.assertRaisesRegex(RuntimeError, 'no observed native'):
                    peace.apply(saved, backend, prefix, ACTION, overview)
            saved.emit.assert_not_called()
            after = dict(military_enabled=True,
                         targets=[dict(player_id=3, at_war=False, can_make_peace=False)])
            with patch.object(peace, 'panel', return_value=after):
                self.assertEqual(peace.apply(saved, backend, prefix, ACTION, overview)['status'], 'completed')
            self.assertEqual(saved.emit.call_args.args, ('native_xp2_city_state_peace_effect',))

    def test_stock_public_checkpoint_keeps_major_peace_and_promise_fields(self):
        preceding, obs = XP2MilitaryLevyCatalogueTests().load(FIXTURES[2])
        pid, turn = obs['player_id'], obs['turn']
        old_overview = stock_overview(pid, turn)
        current_overview = dict(old_overview, schema=contract.STOCK_CITY_STATE_PEACE_SCHEMA,
                                city_state_peace=deepcopy(PEACE_PANEL))
        candidates = [row for row in preceding['candidates'] if row['action']['kind'] != 'diplomacy_initiate']

        def with_overview(overview, gaps):
            added = [dict(action=action, candidate_id=network_turn.digest(action))
                     for action in contract.candidates(overview)]
            value = dict(preceding, diplomacy_overview=overview, candidates=candidates + added,
                families=dict(preceding['families'], diplomacy_initiate=dict(
                    status='queried_partial', unqualified=list(gaps),
                    candidate_ids=[row['candidate_id'] for row in added])))
            self.fixture._redigest(value)
            self.fixture._validate(value, obs)
            return value

        saved = with_overview(old_overview, network_turn.STOCK_PROMISE_GAPS)
        current = with_overview(current_overview, network_turn.STOCK_CITY_STATE_PEACE_GAPS)
        comparable, transition = network_turn.checkpoint_catalogue(
            current, saved, obs, core_sha256=fixture_module.XP2_CORE)
        self.assertEqual(comparable, saved)
        self.assertEqual(transition['added_action_variants'], ['diplomacy_initiate.city_state_peace'])
        self.assertEqual(transition['added_public_fields'], ['diplomacy_overview.city_state_peace'])
        self.assertIn(dict(ACTION, target_player_id=2), contract.candidates(comparable['diplomacy_overview']))

    def test_stock_minor_dispatch_reuses_shared_operation_without_opening_major_deal(self):
        old = stock_overview(0, 8)
        current = dict(old, schema=contract.STOCK_CITY_STATE_PEACE_SCHEMA, city_state_peace=PEACE_PANEL)
        saved, backend, prefix = Mock(), Mock(), Mock()
        observation = dict(player_id=0, turn=8)
        with (patch.object(adapter, '_bind', return_value=(backend, prefix, None, True)),
              patch.object(adapter, 'catalogue', return_value=current),
              patch.object(peace, 'apply', return_value={'status': 'completed'}) as direct,
              patch.object(adapter.draft, 'verify_request') as major):
            self.assertEqual(adapter.initiate(saved, ACTION, observation)['status'], 'completed')
            direct.assert_called_once_with(saved, backend, prefix, ACTION, current)
            major.assert_not_called()


if __name__ == '__main__':
    unittest.main()

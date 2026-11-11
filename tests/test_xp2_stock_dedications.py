from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import dedications as contract
from civ6_host.contracts import information, network_turn
from civ6_host.runtime import xp2_dedications as runtime

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


class DedicationContractTests(unittest.TestCase):
    def setUp(self):
        self.state = runtime.parse_state(
            b'0|61|1|heroic|2\nchoice|8|DEDICATION_A\nchoice|9|DEDICATION_B'
            b'\nchoice|10|DEDICATION_C\nactive|7|DEDICATION_D', 0, 61)
        candidate = contract.CANDIDATE
        candidate_id = network_turn.digest(candidate)
        self.decisions = dict(schema=network_turn.CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA,
                              decision_id='decision', dedications=self.state,
                              candidates=[dict(candidate_id=candidate_id, action=candidate)])
        self.selection = dict(decision_id='decision', candidate_id=candidate_id,
                              parameters={'indices': [10, 8]})

    def test_selection_preserves_order_and_refuses_foreign_or_repeated_indices(self):
        action = network_turn.select_capability(self.decisions, self.selection)
        self.assertEqual(action, dict(kind=contract.KIND, indices=[10, 8]))
        for parameters in (None, {'indices': [8, 8]}, {'indices': [8]},
                           {'indices': [8, 44]}, {'indices': [True, 8]}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                network_turn.select_capability(self.decisions, dict(self.selection, parameters=parameters))
        with self.assertRaises(ValueError):
            network_turn.select_capability(self.decisions, dict(self.selection, decision_id='stale'))

    def test_effect_requires_exact_new_active_choices_and_consumed_count(self):
        action = network_turn.select_capability(self.decisions, self.selection)
        after = deepcopy(self.state)
        after['active'] += [self.state['choices'][2], self.state['choices'][0]]
        after.update(remaining=0, choices=[])
        runtime.verify_effect(self.state, after, action)
        self.assertEqual(contract.candidates(after), [])
        for unverified in (self.state, dict(after, active=list(reversed(after['active']))),
                           dict(after, remaining=1), dict(after, age='normal')):
            with self.assertRaises(RuntimeError):
                runtime.verify_effect(self.state, unverified, action)

    def test_public_group_is_detached_and_bound_to_the_player(self):
        observation = dict(player_id=0, turn=61)
        output = information.project('dedications', observation, self.decisions)
        self.assertEqual(output, self.state)
        output['choices'].clear()
        self.assertEqual(len(self.state['choices']), 3)
        with self.assertRaises(ValueError):
            information.project('dedications', dict(observation, player_id=1), self.decisions)

    def test_worker_revalidates_confirmation_parameters_against_the_fresh_native_catalogue(self):
        from civ6_host.runtime.workers.network_worker import _execute_xp1

        action = network_turn.select_capability(self.decisions, self.selection)
        observation = dict(player_id=0, turn=61)
        receipt = dict(action=action, native_archive_delivered=True,
                       native_archive_sha256=['a' * 64, 'b' * 64], native_effect_readback=True)
        saved = SimpleNamespace(continuation=SimpleNamespace(observation=observation),
                                execute=Mock(return_value=dict(action=action,
                                    effect=dict(status='completed', receipt=receipt))), emit=Mock())
        with (patch('civ6_host.runtime.xp1_session_view.read',
                    return_value=(None, observation, self.decisions)),
              patch('civ6_host.runtime.xp1_session_inputs._write_once'),
              patch('civ6_host.runtime.workers.network_worker._retain_xp2_diplomacy_if_ready',
                    return_value=False)):
            result = _execute_xp1(saved, action, 0, 1, 'unused-closure.json')
            self.assertEqual(result, dict(status='completed', reason=None, requested_action=action))
            saved.execute.assert_called_once_with(action)
            self.state['choices'].pop()
            stale = _execute_xp1(saved, action, 0, 1, 'unused-closure.json')
            self.assertEqual(stale['reason'], 'native_action_no_longer_available')
            saved.execute.assert_called_once()


@unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture runtime unavailable')
class DedicationLuaTests(unittest.TestCase):
    def test_cache_query_checks_the_local_player_and_reads_the_native_domain(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(b"""
local function yes() return true end
local function no() return false end
local eras={GetCurrentEra=function() return 1 end,
  HasHeroicGoldenAge=no, HasGoldenAge=yes, HasDarkAge=no,
  GetPlayerNumAllowedCommemorations=function(_, p) assert(p==0); return 1 end,
  GetPlayerCommemorateChoices=function(_, p) assert(p==0); return {9, 8} end,
  GetPlayerActiveCommemorations=function(_, p) assert(p==0); return {7} end}
Players={[0]={IsAlive=yes, IsTurnActive=yes, IsTurnActiveComplete=yes}}
Game={GetEras=function() return eras end, GetCurrentGameTurn=function() return 61 end,
  GetLocalPlayer=function() return 0 end, GetLocalObserver=function() return 0 end}
GameInfo={CommemorationTypes={}}
for i=7,9 do GameInfo.CommemorationTypes[i]={Index=i, CommemorationType='DEDICATION_'..i} end
""")
        prefix = SimpleNamespace(ui_child=None, runtime=SimpleNamespace(
            evaluate_text=lambda child, chunk, tag, capacity: lua.execute(chunk)))
        state = runtime._query(prefix, dict(player_id=0, turn=61), start_turn=1)
        self.assertEqual(state['age'], 'golden')
        self.assertEqual([row['index'] for row in state['choices']], [9, 8])
        self.assertEqual(state['active'], [dict(index=7, type='DEDICATION_7')])
        with self.assertRaisesRegex(Exception, 'foreign dedication perspective'):
            runtime._query(prefix, dict(player_id=1, turn=61), start_turn=1)
        opening = runtime._query(prefix, dict(player_id=0, turn=61), start_turn=61)
        self.assertEqual(opening['remaining'], 0)
        self.assertEqual(opening['choices'], [])

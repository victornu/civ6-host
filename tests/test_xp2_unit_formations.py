import copy
from types import SimpleNamespace
import unittest

from civ6_host.contracts import unit_formations as contract
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime import xp2_unit_formations as runtime

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


FIXTURE = b"""
local units={}
local function unit(id)
 return {id=id,group=-1,GetID=function(self)return self.id end,GetOwner=function()return 0 end,
  GetFormationID=function(self)return self.group end,
  GetFormationUnitCount=function(self)return self.group==-1 and 1 or 2 end,
  GetFormationMovesRemaining=function()return 1.5 end,GetFormationMaxMoves=function()return 2 end}
end
units[9]=unit(9);units[10]=unit(10)
local collection={Members=function()return pairs(units) end,FindID=function(_,id)return units[id]end}
local player={GetID=function()return 0 end,GetUnits=function()return collection end,IsAlive=function()return true end,
 IsTurnActive=function()return true end,IsTurnActiveComplete=function()return true end}
Players={[0]=player}
Game={GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return 0 end,
 GetCurrentGameTurn=function()return 49 end,IsAllowStrategicCommands=function()return true end}
Map={GetGridSize=function()return 10,10 end,GetPlotCount=function()return 100 end}
UnitCommandTypes={ENTER_FORMATION=-913294208,EXIT_FORMATION=-50443187,PARAM_UNIT_PLAYER=101,PARAM_UNIT_ID=102}
UnitCommandResults={UNITS=7}
GameInfo={UnitCommands={UNITCOMMAND_ENTER_FORMATION={Hash=-913294208,VisibleInUI=true},
 UNITCOMMAND_EXIT_FORMATION={Hash=-50443187,VisibleInUI=true}}}
UnitManager={}
function UnitManager.CanStartCommand(unit,kind,visible,details)
 if kind==UnitCommandTypes.ENTER_FORMATION then
  assert(visible==nil and details==true)
  local other=unit.id==9 and 10 or 9
  return unit.group==-1,{[7]={{player=0,id=other}}}
 end
 assert(visible==true and details==nil or visible==false and details==true)
 return unit.group~=-1
end
function UnitManager.RequestCommand(unit,kind,args)
 if kind==UnitCommandTypes.ENTER_FORMATION then
  assert(args[101]==0 and args[102]~=unit.id)
  unit.group=17; units[args[102]].group=17
 else
  assert(kind==UnitCommandTypes.EXIT_FORMATION and args==nil)
  units[9].group=-1;units[10].group=-1
 end
end
"""


@unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture runtime unavailable')
class StockFormationTests(unittest.TestCase):
    def test_shared_continuation_admits_the_exact_opt_in(self):
        observation = dict(player_id=0)
        session = SimpleNamespace(unit_formations=True)
        action = dict(kind='unit_formation', command='enter', unit_id=9, partner_id=10)
        state = SimpleNamespace(
            observation=observation, world_input_prompts={},
            owner=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)),
            _transition=lambda action, *, session, pump: (action, session, pump),
        )
        self.assertEqual(SavedContinuation.execute(state, action, session=session), (action, session, False))
        with self.assertRaisesRegex(ValueError, 'selected stock'):
            SavedContinuation.execute(state, action, session=SimpleNamespace(unit_formations=False))
        with self.assertRaisesRegex(ValueError, 'itself'):
            SavedContinuation.execute(state, dict(action, partner_id=9), session=session)

    def test_native_choices_payload_and_private_join_identity(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(FIXTURE)
        prefix = SimpleNamespace(
            runtime=SimpleNamespace(evaluate_text=lambda child, src, tag, capacity: lua.execute(src)),
            ui_child=None,
        )
        observation = dict(player_id=0, turn=49, units=[dict(id=9, owner=0), dict(id=10, owner=0)])
        before, public = runtime._native_catalogue(prefix, observation)
        self.assertNotIn('formation_id', public['units'][0])
        self.assertEqual(public['units'][0]['moves'], 1.5)
        enter = public['offers'][0]
        self.assertEqual(enter['partner_id'], 10)
        self.assertEqual(lua.execute(runtime._request_source(enter, before)), b'submitted')
        joined, public = runtime._native_catalogue(prefix, observation)
        self.assertTrue(runtime._effect(enter, before, joined))
        self.assertFalse(runtime._effect(enter, before, before))
        unrelated = copy.deepcopy(joined)
        unrelated['units'][1]['formation_id'] = 42
        self.assertFalse(runtime._effect(enter, before, unrelated))
        exit_action = public['offers'][0]
        self.assertIsNone(exit_action['partner_id'])
        self.assertEqual(lua.execute(runtime._request_source(exit_action, joined)), b'submitted')
        left, public = runtime._native_catalogue(prefix, observation)
        self.assertTrue(runtime._effect(exit_action, joined, left))
        self.assertEqual(left, before)
        public['offers'][0]['partner_id'] = 11
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            contract.validate(public, 0, 49, observation=observation)

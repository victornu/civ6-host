import unittest

from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.runtime.native import native_saved_unit_work as work


FIXTURE = b"""
Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 7 end}
local u={GetOwner=function() return 0 end,GetID=function() return 10 end,
 GetMovesRemaining=function() return 2 end,GetX=function() return 2 end,
 GetY=function() return 3 end,GetBuildCharges=function() return 2 end}
Players={[0]={IsAlive=function() return true end,IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,
 GetUnits=function() return {Members=function() return ipairs({u}) end} end}}
PlayersVisibility={[0]={IsVisible=function(x,y) return not hidden or x==2 end,
 IsRevealed=function() return true end}}
local source={GetIndex=function() return 32 end}
local target={GetIndex=function() return 33 end,GetX=function() return 3 end,
 GetY=function() return 3 end}
Map={GetPlot=function(x,y) return x==2 and source or target end,
 GetPlotByIndex=function(id) assert(id==33);return target end,
 IsPlot=function(id) return id==33 end}
UnitOperationTypes={BUILD_IMPROVEMENT=1,BUILD_IMPROVEMENT_ADJACENT=5,
 PARAM_X=2,PARAM_Y=3,PARAM_IMPROVEMENT_TYPE=4}
UnitOperationResults={IMPROVEMENTS='improvements',PLOTS='plots'}
GameInfo={UnitOperations={},Improvements={[12]={Index=21,Hash=-42,
 ImprovementType='IMPROVEMENT_MOUNTAIN_ROAD'}}}
UnitManager={
 CanStartOperation=function(unit,op,_,arg,details)
  assert(unit==u)
  if op==1 then return false end
  assert(op==5)
  if details then assert(next(arg)==nil);return true,{improvements={12}} end
  assert(arg[2]==3 and arg[3]==3 and arg[4]==-42)
  return not refused
 end,
 GetOperationTargets=function(unit,op,arg)
  assert(unit==u and op==5 and arg[4]==-42 and arg[2]==nil and arg[3]==nil)
  return {plots={33}}
 end,
 RequestOperation=function(unit,op,arg)
  assert(unit==u and op==5 and arg[2]==3 and arg[3]==3 and arg[4]==-42)
  requests=(requests or 0)+1
 end}
"""


class AdjacentUnitWorkTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(encoding=None)
        self.lua.execute(FIXTURE)

    def test_native_parameters_and_exact_revalidation(self):
        raw = self.lua.execute(work.catalog_source(0, 7, adjacent=True))
        action, = work.actions(work.parse_catalog(raw, 0, 7, adjacent=True))
        self.assertEqual((action['source_plot_id'], action['plot_id'], action['selector'],
                          action['index'], action['hash']), (32, 33, 12, 21, 2**32 - 42))
        with self.assertRaises(ValueError):
            work.parse_catalog(raw, 0, 7)
        self.assertEqual(self.lua.execute(work.request_source(action, 0, 7)), b'submitted')
        self.lua.execute(b'refused=true')
        with self.assertRaises(LuaError):
            self.lua.execute(work.request_source(action, 0, 7))
        self.assertEqual(self.lua.eval(b'requests'), 1)

    def test_disabled_by_default_and_hidden_target_refused(self):
        self.assertEqual(self.lua.execute(work.catalog_source(0, 7)), b'work-v1|0|7')
        self.lua.execute(b'hidden=true')
        with self.assertRaises(LuaError):
            self.lua.execute(work.catalog_source(0, 7, adjacent=True))

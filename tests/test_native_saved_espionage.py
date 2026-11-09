"""Lua5.1 fixtures for the public boundary and native request signatures.

These replace all engine getters/archive writers and do not qualify gameplay.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST / 'src'))
sys.path.append(str(HOST.parent / 'civ6-rl-lab' / 'work' / 'lua-test-deps'))
from civ6_host.runtime.native import native_saved_espionage as native

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


SETUP = r'''
state={pid=0,observer=0,turn=8,alive=true,active=true,complete=true,moves=2,
 x=1,y=1,op=-1,endTurn=8,onmap=true,travel=true,mission=true,apply=false,
 escaping=false,escapeID=7,notificationOwner=0,dismissed=false,blockers={},requests={},
 offmap={{Name='Transit',Level=1,ReturnTurn=10,XLocation=4,YLocation=1},
 {Name='Removed',Level=4,ReturnTurn=-1,XLocation=-1,YLocation=-1}}}
local function members(rows)return function()local i=0;return function()i=i+1;if rows[i]then return i,rows[i]end end end end
local spy={GetID=function()return 7 end,GetOwner=function()return 0 end,GetUnitType=function()return 1 end,
 GetName=function()return 'Agent "A"'end,GetX=function()return state.x end,GetY=function()return state.y end,
 GetExperience=function()return {GetLevel=function()return 2 end}end,
 GetSpyOperation=function()return state.op end,GetSpyOperationEndTurn=function()return state.endTurn end,
 GetMovesRemaining=function()return state.moves end}
local plots={}
for i=0,31 do local n=i;plots[n]={GetX=function()return n%8 end,GetY=function()return math.floor(n/8)end,GetIndex=function()return n end}end
Map={GetGridSize=function()return 8,4 end,GetPlotCount=function()return 32 end,
 GetPlot=function(x,y)return plots[y*8+x]end,GetPlotByIndex=function(i)return plots[i]end}
local function city(owner,id,x)
 return {GetOwner=function()return owner end,GetID=function()return id end,GetX=function()return x end,GetY=function()return 1 end,
 GetDistricts=function()return {HasDistrict=function(_,index,a,b)assert(a==true and b==true);return index==2 end}end}
end
ownCity=city(0,10,1);foreignCity=city(1,20,4);minorCity=city(2,30,6);hiddenCity=city(2,31,7)
alliedCity=city(3,40,2);teamCity=city(4,50,3);freeCity=city(5,60,5)
Cities={GetPlotPurchaseCity=function(plot)
 local x=plot:GetX();if x==1 or x==2 then return ownCity elseif x==4 or x==5 then return foreignCity elseif x==6 then return minorCity end
end}
local captured={
 [0]={{OwningPlayer=1,NameIndex=31,Name='Enemy',Level=999}},
 [1]={{OwningPlayer=0,NameIndex=21,Name='Prisoner',Level=3},{OwningPlayer=2,NameIndex=22,Name='Secret',Level=4}}}
local history={
 {Name='Agent "A"',LevelAfter=2,Operation=2,CompletionTurn=7,InitialResult=1,EscapeResult=0,CityName='Known',PlotIndex=12,LootInfo=50},
 {Name='Pending',LevelAfter=2,Operation=2,CompletionTurn=8,InitialResult=2,EscapeResult=0,CityName='Secret unresolved',PlotIndex=12,LootInfo=100}}
local function diplo(id)
 return {GetSpyCapacity=function()return 5 end,GetNumSpiesCaptured=function()return #(captured[id]or {})end,
 GetNthCapturedSpy=function(_,owner,n)assert(owner==id);return (captured[id]or {})[n+1]end,
 GetNumSpiesOffMap=function()assert(id==0);return #state.offmap end,
 GetNthOffMapSpy=function(_,owner,n)assert(owner==id);return state.offmap[n+1]end,
 GetRecentMissions=function(_,owner,count,start)assert(owner==id and count==10 and start==0);return history end,
 GetNextEscapingSpyID=function()assert(state.escaping and not state.dismissed,'unguarded next spy');return state.escapeID end}
end
local cityLists={{ownCity},{foreignCity},{minorCity,hiddenCity},{alliedCity},{teamCity},{freeCity}}
Players={};local allPlayers={}
for i=0,5 do
 local id=i;local team=id==4 and 0 or id
 local p={GetID=function()return id end,GetTeam=function()return team end,IsFreeCities=function()return id==5 end,
  IsAlive=function()return state.alive end,IsTurnActive=function()return state.active end,IsTurnActiveComplete=function()return state.complete end,
  GetDiplomacy=function()return diplo(id)end,GetDiplomaticAI=function()return {GetDiplomaticStateIndex=function(_,other)assert(other==0);return id==3 and 1 or 0 end}end,
  GetCities=function()return {Members=members(cityLists[id+1])}end,
  GetUnits=function()return {Members=function()return members(state.onmap and {spy}or {})()end,
   FindID=function(_,wanted)if state.onmap and wanted==7 then return spy end end}end}
 Players[id]=p;allPlayers[#allPlayers+1]=p
end
Game={GetLocalPlayer=function()return state.pid end,GetLocalObserver=function()return state.observer end,
 GetCurrentGameTurn=function()return state.turn end,GetPlayers=function()return allPlayers end}
PlayersVisibility={[0]={IsRevealed=function(_,x,y)return x~=7 end}}
UnitOperationTypes={SPY_TRAVEL_NEW_CITY=101,SPY_COUNTERSPY=102,PARAM_X=11,PARAM_Y=12}
UnitCommandTypes={CANCEL=201};UnitOperationResults={PLOTS=301};OperationResultsTypes={NO_TARGETS=401}
PlayerOperations={SET_ESCAPE_ROUTE=501,PARAM_DISTRICT_TYPE=502}
EspionageResultTypes={SUCCESS_MUST_ESCAPE=2,FAIL_MUST_ESCAPE=3,NO_RESULT=0}
NotificationTypes={SPY_CHOOSE_ESCAPE_ROUTE=601,SPY_CHOOSE_DRAGNET_PRIORITY=602}
EndTurnBlockingTypes={ENDTURN_BLOCKING_SPY_CHOOSE_ESCAPE_ROUTE=701,ENDTURN_BLOCKING_SPY_CHOOSE_DRAGNET_PRIORITY=702}
NotificationManager={GetAllEndTurnBlocking=function(id)assert(id==0);return state.blockers end,
 FindType=function(kind,id)
  assert(id==0);if state.escaping and kind==601 then
   return {GetPlayerID=function()return state.notificationOwner end,GetType=function()return kind end,IsDismissed=function()return state.dismissed end}
  end
 end}
local operations={
 {OperationType='UNITOPERATION_SPY_TRAVEL_NEW_CITY',Hash=101,Index=0,VisibleInUI=true},
 {OperationType='UNITOPERATION_SPY_COUNTERSPY',Hash=102,Index=1,VisibleInUI=true},
 {OperationType='UNITOPERATION_SPY_SIPHON_FUNDS',Hash=-103,Index=2,VisibleInUI=true,CategoryInUI='OFFENSIVESPY'}}
local opTable={};for _,op in ipairs(operations)do opTable[op.OperationType]=op;opTable[op.Hash]=op;opTable[op.Index]=op end
setmetatable(opTable,{__call=function()local i=0;return function()i=i+1;return operations[i]end end})
GameInfo={Units={[1]={Spy=true}},UnitOperations=opTable,DiplomaticStates={[0]={StateType='DIPLO_STATE_NEUTRAL'},[1]={StateType='DIPLO_STATE_ALLIED'}},Districts={}}
for i,name in ipairs({'DISTRICT_AERODROME','DISTRICT_HARBOR','DISTRICT_COMMERCIAL_HUB','DISTRICT_CITY_CENTER'})do
 GameInfo.Districts[name]={Index=i,TravelTime=i}
end
UnitManager={
 CanStartCommand=function(u,cmd,loose,results)
  assert(u==spy and cmd==201);if not loose and state.cancelNow==false then return false end
  return state.op~=-1
 end,
 CanStartOperation=function(u,op,plot,arg,wants)
  assert(u==spy)
  if op==101 then
   if plot then assert(type(arg)=='table' and arg[11]==plot:GetX() and arg[12]==plot:GetY());assert(plot:GetX()~=7,'hidden city queried')end
   return state.travel and state.op==-1
  end
  if not state.mission or state.op~=-1 then return false,{}end
  if plot then
   assert(arg==false and wants==true)
   if op==102 then return true,{[301]={9,10}}end
   return true,{[301]={13}}
  end
  return true
 end,
 GetTravelTime=function(u,c)return 3 end,GetEstablishInCityTime=function(u,c)return 2 end,
 GetTimeToComplete=function(index,u)assert(index==1 or index==2);return 7 end,
 GetResultProbability=function(index,u,target)assert(index==2);return {
  ESPIONAGE_SUCCESS_UNDETECTED=.4,ESPIONAGE_SUCCESS_MUST_ESCAPE=.2,
  ESPIONAGE_FAIL_UNDETECTED=.1,ESPIONAGE_FAIL_MUST_ESCAPE=.1}end,
 RequestOperation=function(...)
  local u,op,params=...;state.requests[#state.requests+1]={kind='operation',count=select('#',...),op=op,params=params}
  if state.apply then
   if op==101 then state.onmap=false;state.offmap[#state.offmap+1]={Name=spy:GetName(),Level=2,ReturnTurn=13,XLocation=params[11],YLocation=params[12]}
   else state.op=opTable[op].Index;state.endTurn=15 end
  end
 end,
 RequestCommand=function(...)
  local u,cmd=...;state.requests[#state.requests+1]={kind='command',count=select('#',...),op=cmd}
  if state.apply then state.op=-1 end
 end}
UI={RequestPlayerOperation=function(...)
 local id,op,params=...;assert(id==0);state.requests[#state.requests+1]={kind='player',count=select('#',...),op=op,params=params}
 if state.apply then state.escaping=false;state.blockers={}end
end}
'''


@unittest.skipIf(LuaRuntime is None, 'existing Lua5.1 fixture dependency unavailable')
class EspionageLuaTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(encoding=None, max_memory=8 * 1024 * 1024)
        self.lua.execute(SETUP.encode())
        self.pins = patch.object(native, 'verify_source', return_value={})
        self.pins.start()
        self.addCleanup(self.pins.stop)

    def query(self):
        raw = self.lua.execute(native.source(8, 0) + b'local out=snapshot();return encode(out)')
        return native.parse(raw, 8, 0)

    def action(self, value, kind, **fields):
        return next(row['action'] for row in value['offers']
                    if row['action']['kind'] == kind
                    and all(row['action'].get(k) == v for k, v in fields.items()))

    def submit(self, action, value):
        return self.lua.execute(native.request_source(action, value))

    def effect(self, action, before):
        return json.loads(self.lua.execute(native.effect_source(action, before)))

    def test_public_roster_captives_offmap_history_and_hidden_city(self):
        value = self.query()
        self.assertEqual(value['spies'][0]['name'], 'Agent "A"')
        self.assertEqual(value['capacity'], 5)
        self.assertEqual({r['name'] for r in value['captured']}, {'Enemy', 'Prisoner'})
        self.assertIsNone(next(r for r in value['captured'] if r['name'] == 'Enemy')['level'])
        self.assertEqual([r['name'] for r in value['off_map']], ['Transit'])
        self.assertEqual([r['name'] for r in value['history']], ['Agent "A"'])
        self.assertEqual(value['history'][0]['loot_info'], 50)
        self.assertEqual({r['action']['city_owner'] for r in value['offers'] if r['action']['kind'] == 'spy_travel'}, {1, 2})
        self.assertFalse(any(r['action'].get('mode') == 'renew' for r in value['offers']))
        self.assertEqual(self.lua.eval(b'#state.requests'), 0)

    def test_counterspy_has_district_params_and_native_effect_is_separate(self):
        before = self.query();action = self.action(before, 'spy_mission', mode='counterspy', x=2)
        self.assertEqual(self.submit(action, before), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].count'), 3)
        self.assertEqual(self.lua.eval(b'state.requests[1].params[11]'), 2)
        self.assertFalse(self.effect(action, before)['confirmed'])
        self.lua.execute(b'state.apply=true')
        self.assertEqual(self.submit(action, before), b'submitted')
        effect = self.effect(action, before)
        self.assertTrue(effect['confirmed']);self.assertEqual(effect['expected_operation'], 1)

    def test_offensive_request_uses_no_target_parameters_and_grouped_odds(self):
        self.lua.execute(b'state.x=4')
        before = self.query();action = self.action(before, 'spy_mission', mode='start')
        row = next(r for r in before['offers'] if r['action'] == action)
        self.assertEqual((row['success_percent'], row['failure_percent'], row['captured_or_killed_percent']), (60, 20, 20))
        self.assertEqual(action['operation_hash'], (-103) & 0xffffffff)
        self.assertEqual(action['plot_id'], 13)
        self.assertEqual(self.submit(action, before), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].count'), 2)
        self.assertEqual(self.lua.eval(b'state.requests[1].op'), -103)

    def test_travel_request_and_offmap_effect(self):
        before = self.query();action = self.action(before, 'spy_travel', city_owner=2)
        self.lua.execute(b'state.apply=true')
        self.assertEqual(self.submit(action, before), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].params[11]'), 6)
        self.assertTrue(self.effect(action, before)['confirmed'])

    def test_cancel_without_moves_uses_unit_command(self):
        self.lua.execute(b'state.op=2;state.moves=0;state.endTurn=6;state.cancelNow=false')
        before = self.query();action = self.action(before, 'spy_cancel')
        self.assertEqual(before['spies'][0]['turns_remaining'], 0)
        self.assertFalse(any(r['action']['kind'] != 'spy_cancel' for r in before['offers']))
        self.lua.execute(b'state.apply=true')
        self.assertEqual(self.submit(action, before), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].kind'), b'command')
        self.assertEqual(self.lua.eval(b'state.requests[1].count'), 2)
        self.assertTrue(self.effect(action, before)['confirmed'])

    def test_stale_offer_refuses_without_archive_but_unrelated_state_is_allowed(self):
        before = self.query();action = self.action(before, 'spy_travel')
        self.lua.execute(b'state.offmap[1].ReturnTurn=11')
        self.assertEqual(self.submit(action, before), b'submitted')
        self.lua.execute(b'state.travel=false;state.requests={}')
        self.assertEqual(self.submit(action, before), b'refused')
        self.assertEqual(self.lua.eval(b'#state.requests'), 0)

    def test_escape_requires_notification_and_uses_player_operation(self):
        self.lua.execute(b'state.escaping=true;state.blockers={701}')
        before = self.query()
        self.assertEqual({r['action']['district_index'] for r in before['offers'] if r['action']['kind'] == 'spy_escape'}, {2, 4})
        action = self.action(before, 'spy_escape', district_index=2)
        self.lua.execute(b'state.apply=true')
        self.assertEqual(self.submit(action, before), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].kind'), b'player')
        self.assertEqual(self.lua.eval(b'state.requests[1].op'), 501)
        self.assertEqual(self.lua.eval(b'state.requests[1].params[502]'), 2)
        self.assertTrue(self.effect(action, before)['confirmed'])

    def test_unresolved_or_foreign_escape_notifications_refuse(self):
        for change in (b'state.blockers={701}', b'state.escaping=true;state.notificationOwner=1',
                       b'state.escaping=true;state.escapeID=-1',
                       b'state.escaping=true;state.dismissed=true;state.blockers={701}'):
            with self.subTest(change=change):
                self.lua.execute(SETUP.encode());self.lua.execute(change)
                with self.assertRaises(LuaError):self.query()
                self.assertEqual(self.lua.eval(b'#state.requests'), 0)

    def test_no_escape_getter_call_without_live_notification(self):
        self.lua.execute(b'state.escapeID=-1')
        self.assertFalse(any(r['action']['kind'] == 'spy_escape' for r in self.query()['offers']))

    def test_context_and_moves_gates(self):
        for change in (b'state.pid=1', b'state.observer=1', b'state.turn=9', b'state.alive=false', b'state.active=false', b'state.complete=false'):
            with self.subTest(change=change):
                self.lua.execute(SETUP.encode());self.lua.execute(change)
                with self.assertRaises(LuaError):self.query()
        self.lua.execute(SETUP.encode());self.lua.execute(b'state.moves=0')
        self.assertEqual(self.query()['offers'], [])

    def test_renewal_is_never_inferred_from_history(self):
        before = self.query();action = self.action(before, 'spy_mission')
        action = dict(action, mode='renew')
        modified = copy.deepcopy(before)
        modified['offers'][0]['action'] = action
        with self.assertRaisesRegex(ValueError, 'completion notification'):
            native.request_source(action, modified)

    def test_parse_rejects_duplicate_foreign_or_private_fields(self):
        before = self.query()
        for value in (dict(before, player_id=1), dict(before, private_counterspy=3)):
            with self.assertRaises(ValueError):native.parse(json.dumps(value).encode(), 8, 0)
        raw = json.dumps(before).encode()
        with self.assertRaises(ValueError):native.parse(raw[:-1] + b',"capacity":8}', 8, 0)


class EspionageSourceTests(unittest.TestCase):
    def test_installed_dependency_pins_and_source_correspondence(self):
        dependencies = native.verify_source()
        self.assertEqual(len(dependencies), 14)
        chooser = (native.GAME_ROOT / 'Base/Assets/UI/Choosers/EspionageChooser.lua').read_text()
        popup = (native.GAME_ROOT / 'Base/Assets/UI/Popups/EspionagePopup.lua').read_text()
        expansion = (native.GAME_ROOT / 'DLC/Expansion2/UI/Replacements/EspionageChooser_Expansion1.lua').read_text()
        self.assertIn('localPlayerVis:IsRevealed(city:GetX(), city:GetY())', chooser)
        self.assertIn('UnitManager.RequestOperation(m_spy, m_operation.Hash);', popup)
        self.assertIn('if (not player:IsFreeCities()) then', expansion)
        self.assertNotIn('player:IsMajor()', expansion)


if __name__ == '__main__':
    unittest.main()

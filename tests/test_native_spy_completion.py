"""Native completion popup fixtures; every GameCore getter/writer is replaced."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST / 'src'))
sys.path.append(str(HOST.parent / 'civ6-rl-lab' / 'work' / 'lua-test-deps'))

from civ6_host.runtime.native import native_saved_espionage as espionage_native
from civ6_host.runtime.native import native_spy_completion as native
from test_native_saved_espionage import SETUP as ESPIONAGE_SETUP

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


SETUP = ESPIONAGE_SETUP + r'''
state.mission={Name='Agent "A"',LevelAfter=2,Operation=1,CompletionTurn=8,
 InitialResult=1,EscapeResult=0,CityName='Capital',PlotIndex=10,LootInfo=-1}
state.detail='';state.locale='Listening post details';state.localeCalls=0;state.missionCalls=0
local diplomacyBase=Players[0].GetDiplomacy
Players[0].GetDiplomacy=function(...)
 local d=diplomacyBase(...)
 d.GetMission=function(_,pid,id)
  assert(pid==0 and id==12,'arbitrary mission lookup');assert(not state.noMissionReads)
  state.missionCalls=state.missionCalls+1;return state.mission
 end
 return d
end
UnitOperationTypes.SPY_LISTENING_POST=104
local listening={OperationType='UNITOPERATION_SPY_LISTENING_POST',Hash=104,Index=3,CategoryInUI='OFFENSIVESPY'}
GameInfo.UnitOperations[3]=listening;GameInfo.UnitOperations[104]=listening;GameInfo.UnitOperations[listening.OperationType]=listening
GameInfo.Districts[4]={Name='LOC_DISTRICT_CITY_CENTER_NAME',DistrictType='DISTRICT_CITY_CENTER'}
Map.GetPlotByIndex(10).GetDistrictType=function()return 4 end
Locale={Lookup=function(key)
 assert(key=='LOC_SPYMISSIONDETAILS_UNITOPERATION_SPY_LISTENING_POST')
 state.localeCalls=state.localeCalls+1;return state.locale
end}
UnitManager.GetOperationDetailText=function(index,unit,plot)
 assert(index==3 and plot:GetIndex()==9);return state.detail
end
local timeBase=UnitManager.GetTimeToComplete
UnitManager.GetTimeToComplete=function(index,unit)if index==3 then return 5 end;return timeBase(index,unit)end
local probabilityBase=UnitManager.GetResultProbability
UnitManager.GetResultProbability=function(index,unit,target)
 if index==3 then return {ESPIONAGE_SUCCESS_UNDETECTED=.55,ESPIONAGE_SUCCESS_MUST_ESCAPE=.2,ESPIONAGE_FAIL_UNDETECTED=.25}end
 return probabilityBase(index,unit,target)
end
'''

OCCURRENCE = {'event_sequence': 23, 'mission_id': 12}


@unittest.skipIf(LuaRuntime is None, 'existing Lua5.1 fixture dependency unavailable')
class SpyCompletionTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(encoding=None, max_memory=8 * 1024 * 1024)
        self.lua.execute(SETUP.encode())
        for module in (native, espionage_native):
            pin = patch.object(module, 'verify_source', return_value={})
            pin.start();self.addCleanup(pin.stop)
        self.prefix = SimpleNamespace(
            runtime=SimpleNamespace(evaluate_text=lambda child, source, label, **kwargs: self.lua.execute(source)),
            ui_child=123,
        )

    def query(self, occurrence=OCCURRENCE):
        return native.catalog(self.prefix, 8, 0, occurrence)

    def renew(self, catalogue):
        return next(row['action'] for row in catalogue['offers'] if row['action']['kind'] == 'spy_renew')

    def espionage(self):
        raw = self.lua.execute(espionage_native.source(8, 0) + b'local out=snapshot();return encode(out)')
        return espionage_native.parse(raw, 8, 0)

    def test_display_admission_allows_inactive_callbacks_and_suppresses_only_counterspy(self):
        self.assertEqual(native.display_state(self.prefix, 0, 12, 23), 'shown')
        self.lua.execute(b'state.active=false;state.complete=false;state.alive=false')
        self.assertEqual(native.display_state(self.prefix, 0, 12, 23), 'suppressed')
        self.lua.execute(b'state.mission.Operation=3')
        self.assertEqual(native.display_state(self.prefix, 0, 12, 23), 'shown')
        self.lua.execute(b'state.mission=0')
        self.assertEqual(native.display_state(self.prefix, 0, 12, 23), 'missing')
        self.lua.execute(b'state.mission=nil')
        with self.assertRaises(LuaError):native.display_state(self.prefix, 0, 12, 23)
        self.assertEqual(self.lua.eval(b'#state.requests'), 0)

    def test_display_filters_foreign_perspective_without_observer_or_turn_requirements(self):
        self.lua.execute(b'state.turn=9;state.observer=1;state.complete=false')
        self.assertEqual(native.display_state(self.prefix, 0, 12, 0xffffffff), 'shown')
        self.lua.execute(b'state.pid=1')
        with self.assertRaises(LuaError):native.display_state(self.prefix, 0, 12, 23)

    def test_no_occurrence_means_no_history_or_mission_query(self):
        self.lua.execute(b'state.noMissionReads=true')
        value = self.query(None)
        self.assertIsNone(value['current']);self.assertEqual(value['offers'], [])
        self.assertEqual(self.lua.eval(b'state.missionCalls'), 0)

    def test_current_identity_and_mission_projection(self):
        value = self.query()
        self.assertEqual(value['current'], dict(OCCURRENCE, name='Agent "A"', level=2, operation=1,
            completion_turn=8, initial_result=1, escape_result=0, city_name='Capital', plot_id=10, loot_info=-1))
        self.assertEqual([row['action']['kind'] for row in value['offers']], ['spy_renew', 'spy_completion_dismiss'])
        self.assertEqual(self.lua.eval(b'#state.requests'), 0)

    def test_existing_shown_occurrence_is_not_resuppressed_when_actor_becomes_inactive(self):
        self.lua.execute(b'state.active=false;state.complete=false;state.alive=false;state.moves=0')
        value = self.query()
        self.assertEqual(self.renew(value)['unit_id'], 7)
        self.assertEqual(self.lua.execute(native.request_source(self.renew(value), value)), b'submitted')

    def test_counterspy_renew_has_historical_district_params_and_no_moves_gate(self):
        self.lua.execute(b'state.moves=0')
        value = self.query();action = self.renew(value)
        self.assertEqual(action['x'], 2);self.assertEqual(action['plot_id'], 10)
        self.assertEqual(self.lua.execute(native.request_source(action, value)), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].op'), 102)
        self.assertEqual(self.lua.eval(b'state.requests[1].count'), 3)
        self.assertEqual(self.lua.eval(b'state.requests[1].params[11]'), 2)
        self.assertEqual(self.lua.eval(b'state.requests[1].params[12]'), 1)

    def test_listening_post_locale_fallback_and_only_visible_probability(self):
        self.lua.execute(b'state.mission.Operation=3;state.moves=0')
        value = self.query();row = next(row for row in value['offers'] if row['action']['kind'] == 'spy_renew')
        self.assertEqual((row['turns'], row['success_percent'], row['failure_percent'], row['captured_or_killed_percent']), (5, 75, -1, -1))
        self.assertEqual(self.lua.eval(b'state.localeCalls'), 1)
        self.assertEqual(self.lua.execute(native.request_source(row['action'], value)), b'submitted')
        self.assertEqual(self.lua.eval(b'state.requests[1].op'), 104)
        self.assertEqual(self.lua.eval(b'state.requests[1].count'), 3)
        self.assertEqual(self.lua.eval(b'state.requests[1].params[11]'), 2)
        self.lua.execute(b'state.detail="native detail";state.localeCalls=0')
        self.renew(self.query());self.assertEqual(self.lua.eval(b'state.localeCalls'), 0)
        self.lua.execute(b'state.detail="";state.locale=""')
        self.assertEqual([r['action']['kind'] for r in self.query()['offers']], ['spy_completion_dismiss'])

    def test_last_matching_spy_is_selected_without_location_equality(self):
        self.lua.execute(b'''
local base=Players[0].GetUnits
Players[0].GetUnits=function(...)
 local units=base(...);local first=units:FindID(7)
 local last=setmetatable({GetID=function()return 9 end,GetX=function()return 6 end,GetMovesRemaining=function()return 0 end},{__index=first})
 units.Members=function()local i=0;local rows={first,last};return function()i=i+1;if rows[i]then return i,rows[i]end end end
 return units
end
UnitManager.CanStartOperation=function(unit,hash,plot,a,b)
 assert(unit:GetID()==9 and hash==102 and plot:GetIndex()==9 and a==false and b==true);return true,{}
end
''')
        action = self.renew(self.query())
        self.assertEqual(action['unit_id'], 9)
        self.assertEqual(action['x'], 2)

    def test_nonrenewable_or_missing_spy_keeps_dismissal(self):
        self.lua.execute(b'state.mission.Operation=2')
        self.assertEqual([r['action']['kind'] for r in self.query()['offers']], ['spy_completion_dismiss'])
        self.lua.execute(b'state.mission.Operation=1;state.onmap=false')
        self.assertEqual([r['action']['kind'] for r in self.query()['offers']], ['spy_completion_dismiss'])
        self.lua.execute(b'state.mission=0')
        self.assertIsNone(self.query()['current'])

    def test_stale_renew_refuses_and_dismissal_never_emits_archive(self):
        value = self.query();action = self.renew(value)
        self.lua.execute(b'UnitManager.CanStartOperation=function()return false,{}end')
        self.assertEqual(self.lua.execute(native.request_source(action, value)), b'refused')
        dismiss = next(row['action'] for row in value['offers'] if row['action']['kind'] == 'spy_completion_dismiss')
        with self.assertRaisesRegex(ValueError, 'local UI action'):native.request_source(dismiss, value)
        self.assertEqual(self.lua.eval(b'#state.requests'), 0)

    def test_occurrence_identity_does_not_alias_history_or_another_event(self):
        value = self.query();action = self.renew(value)
        for fields in ({'event_sequence': 24}, {'mission_id': 13}):
            with self.subTest(fields=fields):
                altered = dict(action, **fields)
                with self.assertRaises(ValueError):native.request_source(altered, value)
        with self.assertRaisesRegex(ValueError, 'owned occurrence'):
            native.parse(json.dumps(value).encode(), 8, 0, {'event_sequence': 24, 'mission_id': 12})
        with self.assertRaises(ValueError):native.parse(json.dumps(value).encode(), 8, 0, None)

    def test_effect_requires_native_transition_and_after_observation(self):
        before = self.espionage();value = self.query();action = self.renew(value)
        self.assertEqual(self.lua.execute(native.request_source(action, value)), b'submitted')
        self.assertEqual(native.read_effect(self.prefix, action, before, self.espionage()), {'applied': False, 'pending': True})
        self.lua.execute(b'state.apply=true')
        self.assertEqual(self.lua.execute(native.request_source(action, value)), b'submitted')
        after = self.espionage()
        self.assertEqual(native.read_effect(self.prefix, action, before, after), {'applied': True, 'pending': False})
        self.assertEqual(native.read_effect(self.prefix, action, before, before), {'applied': False, 'pending': True})
        # A successfully applied assignment removes the renewed native offer.
        self.assertEqual(self.lua.execute(native.request_source(action, value)), b'refused')

    def test_malformed_target_or_native_mission_does_not_become_an_offer(self):
        self.lua.execute(b'state.mission.PlotIndex=31')
        with self.assertRaises(LuaError):self.query()
        self.lua.execute(b'state.mission=false')
        with self.assertRaises(LuaError):self.query()

    def test_parse_rejects_duplicate_and_private_keys(self):
        value = self.query();raw = json.dumps(value).encode()
        with self.assertRaises(ValueError):native.parse(raw[:-1] + b',"turn":8}', 8, 0, OCCURRENCE)
        malformed = copy.deepcopy(value);malformed['current']['private_data'] = 7
        with self.assertRaises(ValueError):native.parse(json.dumps(malformed).encode(), 8, 0, OCCURRENCE)


class SpyCompletionSourceTests(unittest.TestCase):
    def test_same_installed_source_pins_are_reused(self):
        self.assertIs(native.verify_source, espionage_native.verify_source)
        self.assertEqual(len(native.verify_source()), 14)


if __name__ == '__main__':
    unittest.main()

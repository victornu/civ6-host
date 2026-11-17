
"""Focused installed-source and Lua checks for the XP1 religious operations."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.runtime import xp1_religious_unit_operations as adapter
from civ6_host.runtime import xp1_world_text_profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native import native_absent_scalar_a0, native_event_b6b48d9c
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.xp1_session_inputs import materialize_xp1_session_pins


_LUA = br"""
local units={}
for _,row in ipairs(unit_rows) do
 local u = {
  GetOwner=function() return 0 end,
  GetID=function() return row[1] end,
  GetX=function() return row[2] end,
  GetY=function() return row[3] end,
  GetMovesRemaining=function() return row[4] end,
  GetReligionType=function() return row[5] end,
  GetSpreadCharges=function() return row[6] end
 }
 units[#units+1]=u
end
local Players=setmetatable({},{
 __index=function(_,owner)
  assert(owner==0,'foreign player read')
  return {
   IsAlive=function() return true end,
   IsTurnActive=function() return true end,
   IsTurnActiveComplete=function() return true end,
   GetReligion=function()
    return {HasLaunchedInquisition=function() return inquisition end}
   end,
   GetUnits=function() return {Members=function() return ipairs(units) end} end
  }
 end
})
local Game={
 GetLocalPlayer=function() return 0 end,
 GetLocalObserver=function() return observer() end,
 GetCurrentGameTurn=function() return 8 end,
 IsAllowStrategicCommands=function(actor) return actor==0 end
}
local GameInfo={UnitOperations=definitions}
local UnitOperationTypes={TYPE=1}
local UnitManager={
 CanStartOperation=function(unit,hash,...)
  local plot,visible = ...
  assert(select('#',...)==2 and plot==nil and type(visible)=='boolean',
         'operation query gained a target, result map or parameters')
  return can_start(unit:GetID(),hash,visible)
 end,
 RequestOperation=function(unit,hash,...)
  assert(select('#',...)==0,'operation gained parameters')
  request(unit:GetID(),hash)
 end
}
"""


class ReligiousUnitOperationsRuntimeTests(unittest.TestCase):
    def test_installed_dispatch_pins_and_world_text_parent(self):
        source = adapter.source
        pinned = source.source_dependencies(source._XP1_PROFILE)
        self.assertIn(source.SOURCE[1], pinned.values())
        self.assertIn(source.INQUISITION_SOURCE[1], pinned.values())
        self.assertIn(native_event_b6b48d9c.PINNED_EVIDENCE_SHA256, pinned.values())
        self.assertIn(native_absent_scalar_a0._EVIDENCE_SHA256, pinned.values())
        # The saved session already closes the shared WorldText profile. Both
        # closures must select the installed image, not two different Core SHAs.
        shared = materialize_xp1_session_pins(
            xp1_world_text_profile.source_dependencies(XP1_CORE_SHA256),
            source._XP1_PROFILE,
        )
        overlap = set(pinned) & set(shared)
        self.assertIn(source._XP1_PROFILE.path, overlap)
        self.assertEqual({k: pinned[k] for k in overlap}, {k: shared[k] for k in overlap})
        with self.assertRaises(ValueError):
            source.source_dependencies(None)

    def test_official_rows_drive_lua_queries_and_parameterless_request(self):
        source = adapter.source
        proof = source.verify_source()['database']
        path = resolve_path(Path(proof['path']))
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), proof['sha256'])
        names = [entry[0] for entry in source.OPERATIONS.values()]
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
            rows = db.execute(
                'SELECT u.rowid,u.OperationType,t.Hash,u.VisibleInUI,u.InterfaceMode,t.Kind '
                'FROM UnitOperations u JOIN Types t ON t.Type=u.OperationType '
                'WHERE u.OperationType IN (?,?,?,?)', names,
            ).fetchall()
        self.assertCountEqual([row[1] for row in rows], names)
        self.assertTrue(all((visible, mode, kind)==(1,None,'KIND_UNITOPERATION')
                            for _,_,_,visible,mode,kind in rows))
        by_name = {name: (index-1, value) for index,name,value,_,_,_ in rows}
        spread, evangelize, inquisition, remove = (by_name[name][1] for name in names)
        self.assertLess(evangelize, 0)

        lua = LuaRuntime(encoding=None)
        globals_ = lua.globals()
        globals_.unit_rows = lua.table_from([
            lua.table_from([25,6,7,0,-1,0]),
            lua.table_from([23,4,5,1.5,2,3]),
        ])
        definitions = lua.table()
        for index,name,value,visible,mode,_ in rows:
            definitions[name.encode('ascii')] = lua.table_from({
                b'OperationType': name.encode('ascii'), b'Hash': value, b'Index': index-1,
                b'VisibleInUI': bool(visible), b'InterfaceMode': mode,
            })
        globals_.definitions = definitions
        globals_.inquisition = True
        calls, requests = [], []
        current_observer = 0
        allowed = {spread: False, evangelize: True, inquisition: True, remove: False}
        visible = {spread: True, evangelize: True, inquisition: False, remove: True}
        def can_start(unit_id, op_hash, loose):
            calls.append((unit_id, op_hash, loose))
            return (visible if loose else allowed)[op_hash]
        globals_.observer = lambda: current_observer
        globals_.can_start = can_start
        globals_.request = lambda uid, op_hash: requests.append((uid, op_hash))

        raw = lua.execute(_LUA + adapter.catalog_source(0,8))
        catalogue = adapter.parse_catalog(raw,0,8)
        self.assertIs(catalogue['inquisition_started'],True)
        selected, depleted = catalogue['units']
        self.assertEqual((selected['unit_id'],selected['moves_remaining']), (23,1.5))
        self.assertEqual(depleted['operations'], [])
        self.assertEqual(calls, [(23,spread,True),(23,spread,False),
                                 (23,evangelize,True),(23,evangelize,False),
                                 (23,inquisition,True),
                                 (23,remove,True),(23,remove,False)])
        action, = adapter.actions(catalogue)
        self.assertEqual(action, dict(kind='evangelize_belief',unit_id=23,x=4,y=5))
        query = _LUA + adapter.request_source(selected,action,0,8)
        self.assertEqual(lua.execute(query), b'submitted|'+str(by_name[names[1]][0]).encode('ascii'))
        self.assertEqual(requests,[(23,evangelize)])

        allowed[evangelize] = False
        self.assertEqual(lua.execute(query), b'refused')
        self.assertEqual(requests,[(23,evangelize)])
        current_observer = 1
        with self.assertRaisesRegex(LuaError,'stale religious unit perspective'):
            lua.execute(query)
        self.assertEqual(requests,[(23,evangelize)])

        current_observer = 0
        definitions[names[1].encode('ascii')][b'Hash'] = evangelize+1
        with self.assertRaisesRegex(LuaError,'installed religious operation changed'):
            lua.execute(query)
        self.assertEqual(requests,[(23,evangelize)])


    def test_evangelization_reads_own_entitlement_when_holy_city_has_changed_owner(self):
        lua = LuaRuntime(encoding=None)
        globals_ = lua.globals()
        state = dict(owner=0, observer=0, turn=8, earned=2, holy_city_owner=1)
        reads = []
        globals_.current_owner = lambda: state['owner']
        globals_.current_observer = lambda: state['observer']
        globals_.current_turn = lambda: state['turn']
        globals_.holy_city_owner = lambda: state['holy_city_owner']
        def read_earned():
            reads.append(state['earned'])
            return state['earned']
        globals_.earned = read_earned
        env = br"""
local function forbidden() error('unrelated religion or city read') end
local player = {
 IsAlive=function() return true end,
 IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,
 GetCities=forbidden,
 GetReligion=function()
  return {
   GetNumBeliefsEarned=function() return earned() end,
   GetHolyCityID=function() return {player=holy_city_owner(),type=2,id=65536} end
  }
 end
}
local Players={[0]=player}
local Game={
 GetLocalPlayer=current_owner,
 GetLocalObserver=current_observer,
 GetCurrentGameTurn=current_turn,
 GetReligion=forbidden,
 IsAllowStrategicCommands=function(owner) return owner==0 end
}
"""
        child = object()
        def evaluate(actual, source, name, *, capacity):
            self.assertIs(actual, child)
            self.assertEqual(name, b'@explicit_xp1_religious_unit_entitlement')
            self.assertEqual(capacity, 16)
            return lua.execute(env + source)
        prefix = SimpleNamespace(ui_child=child, runtime=SimpleNamespace(evaluate_text=evaluate))
        self.assertEqual(adapter._own_entitlement(prefix,0,8), 2)
        state['earned'] = 3
        self.assertEqual(adapter._own_entitlement(prefix,0,8), 3)
        for key,wrong in (('owner',1),('observer',1),('turn',9)):
            with self.subTest(key=key), self.assertRaisesRegex(LuaError,'stale religious unit perspective'):
                old = state[key]
                state[key] = wrong
                try:
                    adapter._own_entitlement(prefix,0,8)
                finally:
                    state[key] = old
        self.assertEqual(reads, [2,3])
        for value in (-2**31, 2**31-1):
            state['earned'] = value
            self.assertEqual(adapter._own_entitlement(prefix,0,8), value)
        for value in (2**31, 1.25, True):
            state['earned'] = value
            with self.assertRaisesRegex(LuaError,'invalid religious operation beliefs earned'):
                adapter._own_entitlement(prefix,0,8)

        # The worker's receipt validator accepts exactly the same signed
        # domain and still needs the selected native event and observed +1.
        action = dict(kind='evangelize_belief',unit_id=23,x=4,y=5)
        before = dict(player_id=0,turn=8,width=10,height=10,units=[
            dict(id=23,owner=0,x=4,y=5,moves=1),
        ])
        after = dict(before,units=[])
        receipt = dict(
            archive=dict(archive_sha256='a'*64,size_bytes=28,operation_index=10,parameters={}),
            operation_hash=adapter.source.OPERATIONS[action['kind']][1],
            consumed_before=0,consumed_after=1,operation_added_sequence=1,
            inquisition_started_before=False,inquisition_started_after=False,
            unit_before=dict(unit_id=23,x=4,y=5,moves_remaining=1,religion_type=2,spread_charges=3,
                operations=[dict(operation=action['kind'],visible=True,available=True)]),
            unit_after=None,beliefs_earned_before=-1,beliefs_earned_after=0,
        )
        self.assertIs(adapter.confirmation(receipt,action,before,after),True)
        receipt['beliefs_earned_after'] = 1
        self.assertIs(adapter.confirmation(receipt,action,before,after),False)
        receipt['beliefs_earned_after'] = True
        with self.assertRaisesRegex(RuntimeError,'lost the actual belief entitlement'):
            adapter.confirmation(receipt,action,before,after)


if __name__ == '__main__':
    unittest.main()

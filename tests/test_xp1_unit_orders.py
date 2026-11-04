"""Shared Lua/parser and source selection checks, without a native engine."""
import ast
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1];LAB=HOST.parent/'civ6-rl-lab'
sys.path.append(str(LAB/'work/lua-test-deps'))
from lupa.lua51 import LuaRuntime
from civ6_host.runtime import xp1_unit_orders_profile as profile
from civ6_host.runtime.native import native_saved_unit_orders as shared
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1,BASE_CORE_SHA256 as BASE

LUA_SETUP=r'''
activity,fortify,moves,spy,enabled,requests=0,0,2,false,true,0
local unit={}
function unit:GetOwner()return 0 end
function unit:GetID()return 17 end
function unit:GetType()return 3 end
function unit:GetFortifyTurns()return fortify end
function unit:IsReadyToSelect()return activity==0 end
function unit:GetMovesRemaining()return moves end
Game={GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return 0 end,
 GetCurrentGameTurn=function()return 8 end,IsAllowStrategicCommands=function()return enabled end}
local player={}
function player:IsAlive()return true end
function player:IsTurnActive()return true end
function player:IsTurnActiveComplete()return true end
function player:GetUnits()return {Members=function()return ipairs({unit}) end} end
Players={[0]=player};GameInfo={Units={[3]={Spy=false}},UnitCommands={},UnitOperations={}}
for i,name in ipairs({'WAKE','CANCEL'}) do GameInfo.UnitCommands['UNITCOMMAND_'..name]={Hash=i,VisibleInUI=true} end
for i,name in ipairs({'SLEEP','FORTIFY','HEAL','RELIGIOUS_HEAL'}) do GameInfo.UnitOperations['UNITOPERATION_'..name]={Hash=i+2,VisibleInUI=true} end
InterfaceModeTypes={NONE=0};OperationResultsTypes={NO_TARGETS=0};DB={MakeHash=function()return 0 end}
UnitManager={GetActivityType=function(u)assert(u==unit);return activity end,
 CanStartCommand=function(u,h,v,l)assert(u==unit and type(v)=='boolean' and (l==nil or l==true));return true end,
 CanStartOperation=function(u,h,p,v,r)assert(u==unit and p==nil and type(v)=='boolean' and (r==nil or r==0));return true end,
 RequestCommand=function(u,h)assert(u==unit);requests=requests+1;if request_python then request_python('command',h) end end,
 RequestOperation=function(u,h)assert(u==unit);requests=requests+1;if request_python then request_python('operation',h) end end}
'''


class UnitOrdersTests(unittest.TestCase):
    def test_source_and_loaded_byte_guards_include_command_archive(self):
        p=profile.verify_source();self.assertEqual(len(p['bindings']),7)
        from civ6_host.runtime.xp1_status_profiles import _instruction_spans
        from civ6_host.runtime.configuration_profiles import _source
        base=0x250000000;memory={}
        for proof in (p,_source(profile.TRANSPORT_SOURCE)):
            for rva,raw in _instruction_spans(proof):
                memory.update({base+rva+i:v for i,v in enumerate(raw)})
        for name,row in p['bindings'].items():
            raw=name.split('.')[1].encode()+b'\0';address=base+int(row['name_va'],16)-0x180000000
            memory.update({address+i:v for i,v in enumerate(raw)})
        table,entries=profile.COMMAND_TABLE
        raw=b''.join(struct.pack('<Q',base+rva) for rva in entries)
        memory.update({base+table+i:v for i,v in enumerate(raw)})
        read=lambda address,size:bytes(memory[address+i] for i in range(size))
        self.assertGreater(profile.verify_live(base,read),0)
        memory[base+table]^=1
        with self.assertRaisesRegex(ValueError,'vtable changed'):profile.verify_live(base,read)
        with self.assertRaises(ValueError):profile.verify_source(BASE)

    def test_shared_lua_identical_for_base_and_xp1_and_keywords_propagated(self):
        self.assertEqual(shared.catalog_source(0,8,include_cancel=True),
                         shared.catalog_source(0,8,include_cancel=True,core_sha256=XP1))
        raw=Path(shared.__file__).read_text();tree=ast.parse(raw)
        targets={'verify_source','verify_cancel_source','preamble','catalog_source','catalog','request_source','apply'}
        for fn in [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in targets]:
            for call in ast.walk(fn):
                if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in targets:
                    self.assertEqual([(k.arg,ast.unparse(k.value)) for k in call.keywords if k.arg=='core_sha256'],
                                     [('core_sha256','core_sha256')])
        self.assertEqual(profile.selected_proof('retained-base',BASE),'retained-base')
        self.assertEqual(profile.selected_proof('retained-base',XP1),profile.SOURCE[1])

    def test_actual_shared_lua_offers_and_requests_all_six_orders(self):
        for item in ('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL','UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY',
                     'UNITOPERATION_HEAL','UNITOPERATION_RELIGIOUS_HEAL'):
            with self.subTest(item=item):
                lua=LuaRuntime(max_memory=4*1024*1024);lua.execute(LUA_SETUP)
                raw=lua.execute(shared.catalog_source(0,8,include_cancel=True,core_sha256=XP1).decode()).encode()
                state=shared.parse_catalog(raw,0,8)
                action=next(a for a in shared.actions(state) if a['item_type']==item)
                result=lua.execute(shared.request_source(action,0,8,include_cancel=True,core_sha256=XP1).decode())
                self.assertEqual(result,'submitted');self.assertEqual(lua.globals().requests,1)
        lua=LuaRuntime(max_memory=4*1024*1024);lua.execute(LUA_SETUP);lua.globals().moves=0
        read=lambda:shared.parse_catalog(lua.execute(shared.catalog_source(0,8,include_cancel=True,core_sha256=XP1).decode()).encode(),0,8)
        self.assertEqual({a['item_type'] for a in shared.actions(read())},{'UNITCOMMAND_CANCEL','UNITCOMMAND_WAKE'})
        lua.execute('GameInfo.Units[3].Spy=true')
        self.assertEqual({a['item_type'] for a in shared.actions(read())},{'UNITCOMMAND_WAKE'})
        lua.globals().enabled=False
        with self.assertRaisesRegex(Exception,'strategic orders unavailable'):read()


if __name__=='__main__':unittest.main()

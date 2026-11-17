"""Faith admission on actual saved owners, purchase adapters and transport.

Native memory, Lua globals and machine calls are fixtures, not acceptance.
Shared purchase Lua, requote, archive checks, publication and readback execute.
"""
import ast
from pathlib import Path
from contextlib import nullcontext
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaError, LuaRuntime
from civ6_host.runtime import xp1_continuation as continuation
from civ6_host.runtime import xp1_load_capability, xp1_city_purchases, xp2_plot_purchases
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_saved_purchases as purchases
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from test_xp1_prophet_activation import Fixture as ExistingFixture
from test_xp1_world_input_owner import Fixture as TransportFixture


ACTION = dict(kind='purchase', city_id=65536, category='unit', index=3,
              hash=1133470466, item_type='UNIT_MISSIONARY', currency='YIELD_FAITH', price_token='70')

ENV = b'''
local row={UnitType='UNIT_MISSIONARY',Index=3,Hash=1133470466,PurchaseYield='YIELD_FAITH'}
local function rows(value)
 return setmetatable(value and {UNIT_MISSIONARY=value} or {},{__call=function()
  local done=false;return function() if done then return end;done=true;return value end end})
end
local city={GetOwner=function() return CITYOWNER end,GetID=function() return 65536 end}
local gold={IsUnitFaithPurchaseEnabled=function() return true end,
 IsBuildingFaithPurchaseEnabled=function() return false end,
 GetPurchaseCost=function(_,yield,hash,formation) assert(yield==5 and hash==row.Hash);return host_price() end}
function city:GetGold() return gold end
local player={IsAlive=function() return true end,IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,
 GetCities=function() return {Members=function() local done=false;return function()
  if not done then done=true;return 1,city end end end} end,
 GetReligion=function() return {CanAfford=function(_,id,hash) assert(id==65536 and hash==row.Hash);return true end} end}
local Players={[0]=player}
local Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 8 end}
local GameInfo={Units=rows(row),Buildings=rows(nil),Yields={YIELD_GOLD={Index=2},YIELD_FAITH={Index=5}}}
local CityCommandTypes={PURCHASE=41,PARAM_UNIT_TYPE=101,PARAM_BUILDING_TYPE=102,
 PARAM_YIELD_TYPE=103,PARAM_MILITARY_FORMATION_TYPE=104}
local MilitaryFormationTypes={STANDARD_MILITARY_FORMATION=0}
local CityManager={CanStartCommand=function(c,command,visible,params,test)
 assert(c==city and command==41 and params[101]==row.Hash and params[103]==5)
 assert(params[104]==nil and test==not visible);return true end,
 RequestCommand=function(c,command,params)
 assert(c==city and command==41 and params[101]==row.Hash and params[103]==5 and params[104]==0)
 host_request() end}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.saved.xp1_plot_purchase=self.saved.xp1_city_purchase=self.saved.xp1_faith_purchase=True
        self.backend.core._civ6_host_execution_image=_XP1_PROFILE
        self.saved._running=False
        self.token.world_input_prompts={};self.token.trade_feedback=None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        self.token.unit_source=verify_live(self.backend.core._handle,self.backend.runtime.read,core_sha256=XP1_CORE_SHA256)
        self.observation['cities']=[dict(id=65536,owner=0)]
        self.observation['economy']=dict(gold=50,faith=100)
        self.token.observation=deepcopy(self.observation)
        self.city_owner=0;self.request_price=70;self.request_count=0
        self.choice=deepcopy(ACTION)
        self.payload=(struct.pack('<IHH5I',0x346b0a13,0,2,65536,0,0,1,0)
                      +struct.pack('<IIiIii',0,3,-1,5,-9999,-9999))
        self.stack.enter_context(patch.object(purchases,'observe_player',self.observe_native))
        # Source closure serialization is documentary; selected purchase profiles
        # and exact installed XP1 live-code comparisons remain active below.
        self.stack.enter_context(patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()))

    def evaluate(self,child,code,name,**kwargs):
        if child is not self.token.ui_child:raise AssertionError('Foreign purchase child')
        if name not in (b'@xp1_purchase_yields',b'@explicit_purchase_catalog',b'@explicit_purchase_request'):
            return super().evaluate(child,code,name,**kwargs)
        self.machine.append(('lua',name))
        lua=LuaRuntime(encoding=None)
        lua.globals()[b'host_price']=lambda:self.request_price if name==b'@explicit_purchase_request' else 70
        def request():
            self.request_count+=1
            self.token.transport.pending.append(self.payload)
        lua.globals()[b'host_request']=request
        return lua.execute(ENV.replace(b'CITYOWNER',str(self.city_owner).encode())+code)

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva!=self.token.transport.transport_abi.drain_rva:
            return TransportFixture.virtual(self,core,pointer,slot,rva,result,*args)
        def drain(ctx):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
            self.observation['units'].append(dict(id=19,owner=0,type=3,x=0,y=0))
            self.observation['economy']['faith']-=70
        return drain


class FaithContinuationTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_default_and_strict_flag_gold_plot_remain_closed(self):
        for flag in (False,0,1,None,'true'):
            with self.subTest(flag=flag),self.assertRaises(ValueError):
                continuation.validate_command(ACTION,allow_faith=flag)
        with self.assertRaises(ValueError):continuation.validate_command(ACTION)
        continuation.validate_command(ACTION,allow_faith=True)
        continuation.validate_command(dict(ACTION,currency='YIELD_GOLD'))
        plot=dict(kind='purchase',city_id=65536,plot_id=1,x=1,y=0,currency='YIELD_FAITH',price_token='70')
        with self.assertRaises(ValueError):continuation.validate_command(plot,allow_faith=True)
        continuation.validate_command(dict(plot,currency='YIELD_GOLD'),allow_faith=True)

    def test_actual_owner_and_token_reach_shared_native_purchase(self):
        f=self.fixture()
        self.assertIs(type(f.saved),SavedLoadOwner)
        self.assertIs(type(f.token),continuation.SavedContinuation)
        with patch.object(purchases,'apply',wraps=purchases.apply) as provider:
            result=f.saved.execute(deepcopy(ACTION))
        provider.assert_called_once()
        args,kwargs=provider.call_args
        self.assertIs(args[0],f.saved);self.assertIs(args[1],f.saved.prefix)
        self.assertEqual(args[2],ACTION);self.assertIs(kwargs['allow_faith'],True)
        self.assertEqual(result['effect']['receipt']['faith_debit'],70)
        self.assertTrue(result['effect']['receipt']['native_item_confirmed'])
        self.assertEqual((f.request_count,f.token.sequence,f.token.publication_count),(1,1,1))
        self.assertEqual((f.token.transport.pending,f.deferred.pending),([],[]))
        self.assertFalse(f.saved.poisoned);self.assertFalse(f.backend.busy)
        f.token.check_close()

    def test_disabled_nonbool_and_missing_or_foreign_owner_do_not_submit(self):
        f=self.fixture()
        for flag in (False,0,1,None,'true'):
            f.saved.xp1_faith_purchase=flag
            with self.subTest(flag=flag),self.assertRaises(ValueError):f.saved.execute(ACTION)
        f.saved.xp1_faith_purchase=True
        for owner in (None,SimpleNamespace(xp1_faith_purchase=True),SavedLoadOwner.__new__(SavedLoadOwner)):
            if type(owner) is SavedLoadOwner:
                owner.continuation=object();owner.backend=f.backend
            with self.subTest(owner=type(owner).__name__),self.assertRaises(ValueError):
                f.token.execute(ACTION,session=owner)
        with self.assertRaisesRegex(ValueError,'actual active saved session'):
            f.token.execute(ACTION,session=f.saved)
        self.assertEqual(f.machine,[]);self.assertEqual(f.request_count,0)
        self.assertFalse(f.saved.poisoned)

    def test_city_profile_and_native_requote_guards_survive_admission(self):
        for mode in ('city_flag','plot_flag','profile','foreign_city','changed_price','faith_plot'):
            with self.subTest(mode=mode):
                f=self.fixture();action=deepcopy(ACTION)
                if mode=='city_flag':f.saved.xp1_city_purchase=False
                elif mode=='plot_flag':f.saved.xp1_plot_purchase=False
                elif mode=='profile':f.backend.core._civ6_host_execution_image=None
                elif mode=='foreign_city':f.city_owner=1
                elif mode=='changed_price':f.request_price=71
                else:action=dict(kind='purchase',city_id=65536,plot_id=1,x=1,y=0,currency='YIELD_FAITH',price_token='70')
                with self.assertRaises((ValueError,RuntimeError,LuaError)):f.saved.execute(action)
                self.assertEqual(f.request_count,0)
                self.assertEqual((f.token.transport.pending,f.deferred.pending),([],[]))
                f.close()

    def test_xp2_keeps_existing_faith_route_without_xp1_flags(self):
        f=self.fixture()
        f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
        f.saved._engine_sha256=XP2_CORE_SHA256
        f.backend._xp2_postload_requested=True;f.saved.requested['post160_candidate']=True
        for name in ('xp1_plot_purchase','xp1_city_purchase','xp1_faith_purchase'):setattr(f.saved,name,False)
        # Replace the native transition/XP2 live-binding seams only. Execute
        # the actual purchase-routing block extracted from that transition;
        # this is admission/adapter regression coverage, not XP2 native replay.
        tree=ast.parse(Path(continuation.__file__).read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SavedContinuation')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_transition')
        branch=next(n for n in ast.walk(method) if isinstance(n,ast.If)
                    and isinstance(n.test,ast.Name) and n.test.id=='is_purchase')
        wrapper=ast.parse('def route(b,session,action,before_observation):\n pass').body[0]
        wrapper.body=branch.body+[ast.Return(value=ast.Name(id='effect',ctx=ast.Load()))]
        scope=dict(continuation.__dict__)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),
                     str(continuation.__file__),'exec'),scope)
        def transition(action,*,session,pump):
            self.assertIs(session,f.saved);self.assertIs(pump,False)
            self.assertTrue(session._running)
            return scope['route'](f.backend,session,action,deepcopy(f.token.observation))
        with (patch.object(f.token,'_transition',side_effect=transition) as selected,
              patch.object(xp2_plot_purchases,'_bind') as bind,
              patch.object(purchases,'apply',return_value=deepcopy(f.observation)) as provider):
            result=f.saved.execute(ACTION)
        selected.assert_called_once_with(ACTION,session=f.saved,pump=False)
        bind.assert_called_once_with(f.saved,active=True)
        provider.assert_called_once();self.assertEqual(provider.call_args.args[2],ACTION)
        self.assertIs(provider.call_args.args[0],f.saved)
        self.assertEqual(result,dict(observation=f.observation));self.assertFalse(f.saved.poisoned)



if __name__=='__main__':unittest.main()

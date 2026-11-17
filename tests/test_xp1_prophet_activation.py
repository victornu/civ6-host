"""Prophet activation on shared saved owners/FIFO with Lua 5.1 fixtures.

GameCore calls and state effects are fixtures; this is not native acceptance.
Historical Base/foundation/belief non-regression is retained in the private
runtime-stage receipt, independently of this portable product test.
"""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime
from civ6_host.runtime import xp1_prophet_activation as adapter
from civ6_host.runtime import xp1_prophet_activation_source as source
from civ6_host.runtime.native import native_prophet_activation as builders
from civ6_host.runtime.native import native_saved_religion as shared
from civ6_host.runtime.native import native_religion_diagnostic as commands
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.deferred_service import DeferredService
from test_xp1_pantheon import Fixture as ExistingFixture
from test_xp1_world_input_owner import Fixture as TransportFixture

ENV=b'''
local pid,observer,turn=PID,OBSERVER,TURN
local created,earned,holy=CREATED,EARNED,HOLY
local city={GetOwner=function() return CITYOWNER end,GetID=function() return 65536 end}
local units={}
for _,id in ipairs({17,18}) do
 if id~=REMOVED then
  units[#units+1]={GetOwner=function() return UNITOWNER end,GetID=function() return id end,
   GetType=function() return UNITTYPE end,GetX=function() return id==17 and UNITX or 1 end,
   GetY=function() return 0 end,GetMovesRemaining=function() return MOVES end}
 end
end
local religion={GetReligionTypeCreated=function() return created end,
 GetNumBeliefsEarned=function() return earned end,HasReligiousFoundingUnit=function() return HASPROPHET end,
 GetHolyCityID=function() if holy then return {player=CITYOWNER,type=2,id=65536} end
  return {player=-1,type=2,id=-1} end}
local player={GetID=function() return 0 end,IsAlive=function() return true end,
 IsTurnActive=function() return true end,IsTurnActiveComplete=function() return true end,
 GetReligion=function() return religion end,
 GetUnits=function() return {Members=function() local i=0;return function()
  i=i+1;if units[i] then return i,units[i] end end end} end,
 GetCities=function() return {Members=function() local i=0;return function()
  i=i+1;if i==1 then return i,city end end end} end}
local Players={[0]=player}
local Game={GetLocalPlayer=function() return pid end,GetLocalObserver=function() return observer end,
 GetCurrentGameTurn=function() return turn end,IsAllowStrategicCommands=function(p) return p==0 end,
 GetReligion=function() return {GetReligions=function()
  if created<0 then return {} end;return {{Founder=0,Religion=created,Beliefs={}}} end} end}
local GameInfo={Units={UNIT_GREAT_PROPHET={UnitType='UNIT_GREAT_PROPHET',Index=6}},
 UnitOperations={UNITOPERATION_FOUND_RELIGION={OperationType='UNITOPERATION_FOUND_RELIGION',Hash=-953161477}}}
local UnitManager={CanStartOperation=function(u,hash,args,visible)
 assert(hash==-953161477 and args==nil and visible==false)
 return host_can_start(u:GetID()) end,
 RequestOperation=function(u,hash,...)
 assert(hash==-953161477 and select('#',...)==0)
 host_request(u:GetID(),hash) end}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.created=-1;self.earned=0;self.holy=False;self.city_owner=0
        self.removed=-1;self.has_prophet=True;self.unit_owner=0;self.unit_type=6;self.moves=2
        self.x=0;self.pid=0;self.observer=0;self.turn=8
        self.delta=3;self.apply_native=True;self.deny_request=False;self.bad_after_units=False
        self.requested_uid=None;self.evaluations=[];self.move_on_drain=False
        self.payload=struct.pack('<I',0x8c0f3f36)+b'fixture-unit-operation-archive'
        self.observation['units']=[dict(id=17,x=0,y=0),dict(id=18,x=1,y=0)]
        self.token.observation=deepcopy(self.observation)
        self.choice=dict(kind='activate_prophet',unit_id=18,x=1,y=0)
        self.stack.enter_context(patch.object(shared,'observe_player',self.observe_native))
        # Complete the established __new__ fixture's constructor state with
        # real selected profiles. Native callback installation itself is not
        # exercised; source/live-code checks and owner checks remain active.
        self.arguments.reader.core=self.backend.core
        from civ6_host.runtime import foundation_event_profile, placement_event_profile
        from civ6_host.runtime.a0_family_source import A0FamilyProfile
        from civ6_host.runtime.found_unit_event_profiles import SOURCE as FOUND_SOURCE
        from types import MappingProxyType
        f=foundation_event_profile.event_profile(execution_image=_XP1_PROFILE)
        self.owner.foundation_event_profile=self.owner._foundation_event_profile=f
        p=placement_event_profile.event_profile()
        self.owner.placement_event_profile=self.owner._placement_event_profile=p
        f=A0FamilyProfile(MappingProxyType({0xe23b112d:frozenset((0x23,))}),
            MappingProxyType({0x23:128}),FOUND_SOURCE[1])
        self.owner.found_unit_event_profile=self.owner._found_unit_event_profile=f
        self.backend._xp1_load_logger_activation=dict(source_sha256=
            '16d3d479d2280784ba5063bf4f29308d6b2e8ab9280da6d5de736199e83c8af7')

    def evaluate(self,child,code,name,**kwargs):
        if child is not self.token.ui_child:raise AssertionError('Foreign Lua child')
        self.evaluations.append(name)
        if name in (b'@religion_observation_guards',b'@native_prophet_guards'):
            return LuaRuntime(encoding=None).execute(code)
        if name==b'@native_religion_observation_turn':return str(self.turn).encode()
        allowed=(b'@native_own_religion_observation',b'@explicit_prophet_activation',
                 b'@native_prophet_catalog',b'@native_prophet_revalidation',
                 b'@native_prophet_request',b'@native_prophet_effect')
        if name not in allowed:raise AssertionError('Unexpected Lua boundary '+repr(name))
        env=ENV
        values={b'PID':self.pid,b'OBSERVER':self.observer,b'TURN':self.turn,
            b'CREATED':self.created,b'EARNED':self.earned,b'HOLY':self.holy,
            b'CITYOWNER':self.city_owner,b'REMOVED':self.removed,b'UNITOWNER':self.unit_owner,
            b'UNITTYPE':self.unit_type,b'MOVES':self.moves,b'HASPROPHET':self.has_prophet,b'UNITX':self.x}
        for key,value in values.items():env=env.replace(key,str(value).lower().encode())
        lua=LuaRuntime(encoding=None)
        def legal(uid):
            self.machine.append(('can_start',name,uid))
            return self.can_start and not (self.deny_request and name==b'@native_prophet_request')
        def request(uid,operation):
            self.machine.append(('request',uid,operation))
            self.requested_uid=uid
            self.token.transport.pending.append(self.payload)
        lua.globals()[b'host_can_start']=legal
        lua.globals()[b'host_request']=request
        return lua.execute(env+code)

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva==self.token.transport.transport_abi.drain_rva:
            parent=TransportFixture.virtual(self,core,pointer,slot,rva,result,*args)
            def drain(ctx):
                parent(ctx)  # Real shared A0 codec enqueues; real FIFO drains later.
                if self.apply_native:
                    self.removed=self.requested_uid;self.holy=True;self.earned+=self.delta
                    if not self.bad_after_units:
                        self.observation['units']=[u for u in self.observation['units'] if u['id']!=self.removed]
            return drain
        return super().virtual(core,pointer,slot,rva,result,*args)


class RuntimeTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_selected_builders_and_unchanged_base_guards(self):
        self.assertTrue(source.actions_qualified())
        for core in (builders.CORE_SHA256,XP1_CORE_SHA256):
            self.assertEqual(LuaRuntime(encoding=None).execute(builders.guard_case(core_sha256=core)),
                             b'prophet-activation-guards-ok')
        with self.assertRaises(ValueError):builders.catalog_source(0,8,core_sha256='unknown')

    def test_catalogue_explicit_unit_positions_native_site_and_clone(self):
        f=self.fixture();value=adapter.catalogue(f.saved,f.token.observation)
        self.assertIs(type(f.backend.prefix),SavedLoadServices)
        self.assertIs(type(f.backend.prefix.runtime),NativeScriptRuntime)
        self.assertIs(type(f.token.transport),SavedActionTransport)
        self.assertIs(type(f.deferred),DeferredService)
        self.assertEqual(set(value),{'own','activation'})
        self.assertEqual(value['own']['holy_city'],dict(player=-1,type=2,id=-1))
        self.assertEqual(adapter.actions(value),[dict(kind='activate_prophet',unit_id=17,x=0,y=0),f.choice])
        value['activation']['candidates'].clear()
        self.assertEqual(len(adapter.actions(f.saved.explicit_prophet_activation)),2)
        self.assertNotIn(('request',),f.machine)
        f.can_start=False
        self.assertEqual(adapter.actions(adapter.catalogue(f.saved,f.token.observation)),[])
        f.holy=True
        self.assertIsNone(adapter.catalogue(f.saved,f.token.observation)['activation'])

    def test_actual_saved_facade_transport_fifo_effect_and_second_candidate(self):
        f=self.fixture();adapter.catalogue(f.saved,f.token.observation);f.set_active(True)
        result=adapter.apply(f.saved,f.choice,f.token.observation)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['unit_id'],18)
        self.assertEqual(result['founding_site'],dict(player=0,type=2,id=65536))
        self.assertEqual([u['id']for u in result['observation']['units']],[17])
        self.assertEqual(f.earned,3)  # Actual readback, not the historical +2.
        self.assertTrue(f.saved.explicit_prophet_activation['own']['has_religious_founding_unit'])
        self.assertEqual(f.token.publication_count,1)
        self.assertEqual(f.deferred.consumed_count,1)
        self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
        f.token.transport.require_empty_native_queue()
        self.assertEqual([r for r in f.machine if r[0]=='request'],[('request',18,-953161477)])
        effects=[d for event,d in f.emitted if event=='native_prophet_activation_effect_verified']
        self.assertEqual(effects[-1]['effect']['source_proof_sha256'],source.SOURCE[1])
        self.assertFalse(effects[-1]['effect']['named_religion_founded'])

    def test_official_false_before_recheck_or_request_is_refused(self):
        for phase in ('revalidation','request'):
            with self.subTest(phase=phase):
                f=self.fixture();adapter.catalogue(f.saved,f.token.observation);f.set_active(True)
                if phase=='revalidation':f.can_start=False
                else:f.deny_request=True
                result=adapter.apply(f.saved,f.choice,f.token.observation)
                self.assertEqual(result['status'],'refused')
                self.assertEqual(result['refusal_code'],'native_prophet_can_start_false')
                self.assertFalse(result['request']['can_start']);self.assertFalse(result['request']['request_invoked'])
                self.assertEqual(result['observation'],f.token.observation)
                self.assertFalse(any(r[0]=='request'for r in f.machine))
                self.assertEqual(f.token.publication_count,0);self.assertEqual(f.removed,-1)
                self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
                f.close()

    def test_stale_or_foreign_identifiers_and_missing_service_do_not_request(self):
        for change in ('position','type','owner','turn','unit','implicit','transport','service'):
            with self.subTest(change=change):
                f=self.fixture();adapter.catalogue(f.saved,f.token.observation);f.set_active(True)
                choice=dict(kind='activate_prophet',unit_id=17,x=0,y=0)
                if change=='position':f.x=9
                elif change=='type':f.unit_type=7
                elif change=='owner':f.unit_owner=1
                elif change=='turn':f.turn=9
                elif change=='unit':choice['unit_id']=99
                elif change=='implicit':choice['unit_id']=None
                elif change=='transport':
                    from dataclasses import replace
                    f.token.transport.transport_abi=replace(f.token.transport.transport_abi,core_sha256='unknown')
                else:f.backend.prefix.events=object()
                with self.assertRaises(Exception):adapter.apply(f.saved,choice,f.token.observation)
                self.assertFalse(any(r[0]=='request'for r in f.machine))
                self.assertEqual(f.token.publication_count,0)
                f.close()

    def test_no_completion_without_unit_removal_or_consistent_publication(self):
        for mode in ('no_effect','unit_still_observed'):
            with self.subTest(mode=mode):
                f=self.fixture();adapter.catalogue(f.saved,f.token.observation);f.set_active(True)
                if mode=='no_effect':f.apply_native=False
                else:f.bad_after_units=True
                with self.assertRaises(Exception):adapter.apply(f.saved,f.choice,f.token.observation)
                self.assertEqual(f.token.publication_count,1)
                self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
                f.close()


if __name__ == '__main__':
    unittest.main()

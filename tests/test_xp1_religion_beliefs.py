"""ADD_BELIEF shared builders and real saved owners, replacing machine calls."""
import ctypes as C
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime

from civ6_host.runtime import xp1_religion_beliefs as adapter
from civ6_host.runtime import xp1_religion_beliefs_source as source
from civ6_host.runtime.native import native_religion_beliefs as builders
from civ6_host.runtime.native import native_saved_religion as shared
from civ6_host.runtime.native import native_player_operation_request as request
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.deferred_service import DeferredService
from test_xp1_pantheon import Fixture as ExistingFixture


ENV=b'''
local created,earned=CREATED,2
local equipped={EQUIPPED}
local city={GetOwner=function() return 0 end,GetID=function() return 65536 end}
local foreign=setmetatable({Founder=1},{__index=function(_,key) error('foreign field '..key) end})
local religion={GetReligionTypeCreated=function() return created end,
 GetNumBeliefsEarned=function() return earned end,
 HasReligiousFoundingUnit=function() return true end,
 GetHolyCityID=function() return {player=0,type=2,id=65536} end}
local player={IsAlive=function() return true end,IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,GetReligion=function() return religion end,
 GetCities=function() return {Members=function()
  local i=0;return function() i=i+1;if i==1 then return i,city end end end} end}
local function has(i) for _,v in ipairs(equipped) do if i==v then return true end end;return false end
local global={GetReligions=function()
 if created==-1 then return {foreign} end
 return {foreign,{Religion=created,Founder=0,Beliefs=equipped}}
 end,IsInSomePantheon=function() return false end,
 IsInSomeReligion=function(_,i) return has(i) end,
 IsTooManyForReligion=function(_,i,r) assert(r==4);return i==4 end}
local definitions={{Index=1,Hash=11,BeliefClassType='BELIEF_CLASS_FOUNDER'},
 {Index=2,Hash=-1,BeliefClassType='BELIEF_CLASS_FOLLOWER'},
 {Index=3,Hash=3,BeliefClassType='BELIEF_CLASS_PANTHEON'},
 {Index=4,Hash=4,BeliefClassType='BELIEF_CLASS_FOLLOWER'},
 {Index=5,Hash=5,BeliefClassType='BELIEF_CLASS_WORSHIP'}}
local callable=setmetatable({}, {__call=function()
 local i=0;return function() i=i+1;return definitions[i] end end})
for _,row in ipairs(definitions) do callable[row.Index]=row end
local GameInfo={Beliefs=callable}
local Players={[0]=player}
local Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 8 end,IsAllowStrategicCommands=function(p) return p==0 end,
 GetReligion=function() return global end}
local PlayerOperations={ADD_BELIEF=-125661660,PARAM_BELIEF_TYPE=-1538578169,
 PARAM_INSERT_MODE=-1406149623,VALUE_EXCLUSIVE=-1744919098}
local function forbidden() error('Lua builder submitted an operation') end
local UI={RequestPlayerOperation=forbidden}
local UnitManager={RequestOperation=forbidden}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.created=4
        self.equipped=[]
        self.native_selected=2
        self.evaluations=[]
        self.choice=dict(kind='add_belief',index=2,hash=0xffffffff,**{'class':'BELIEF_CLASS_FOLLOWER'})
        self.stack.enter_context(patch.object(shared,'observe_player',self.observe_native))

    def evaluate(self,child,code,name,**kwargs):
        if child is not self.token.ui_child:
            raise AssertionError('Foreign Lua child')
        self.evaluations.append(name)
        if name in (b'@religion_observation_guards',b'@native_religion_belief_guards'):
            return LuaRuntime(encoding=None).execute(code)
        if name==b'@native_religion_observation_turn':
            return b'8'
        if name in (b'@native_own_religion_observation',b'@explicit_religion_beliefs',
                    b'@native_religion_belief_catalog',b'@native_religion_belief_revalidation',
                    b'@native_religion_belief_effect'):
            env=ENV.replace(b'CREATED',str(self.created).encode()).replace(b'EQUIPPED',','.join(map(str,self.equipped)).encode())
            return LuaRuntime(encoding=None).execute(env+code)
        raise AssertionError('Unexpected native Lua boundary '+repr(name))

    def factory(self,result,*args):
        from civ6_host.runtime.xp1_research_profile import player_operation_abi
        abi=player_operation_abi(XP1_CORE_SHA256,request._METHODS)
        parent=super().factory(result,*args)
        def bind(address):
            if address-self.memory.base!=abi.methods['can_start'][0]:
                return parent(address)
            def call(*values):
                self.machine.append(('can_start',))
                if values[1:3]!=(0,builders.ADD_BELIEF) or values[4] is not False:
                    raise AssertionError('Native belief CanStart arguments changed')
                return int(self.can_start)
            return call
        return bind

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva==self.token.transport.transport_abi.drain_rva:
            parent=super().virtual(core,pointer,slot,rva,result,*args)
            def drain(ctx):
                parent(ctx)
                self.equipped.append(self.native_selected)
            return drain
        return super().virtual(core,pointer,slot,rva,result,*args)


class BeliefTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_selected_source_and_base_default_lua_and_metadata(self):
        self.assertTrue(source.actions_qualified())
        self.assertTrue(source.source_dependencies(_XP1_PROFILE))
        self.assertEqual(builders.catalog_source(0,60),builders.catalog_source(0,60,core_sha256=XP1_CORE_SHA256))
        for profile in (builders.CORE_SHA256,XP1_CORE_SHA256):
            self.assertEqual(LuaRuntime(encoding=None).execute(builders.guard_case(core_sha256=profile)),b'native-add-belief-guard-ok')
        with self.assertRaises(ValueError):
            builders.catalog_source(0,60,core_sha256='unknown')

    def test_catalogue_preserves_native_preconditions_filters_and_slots(self):
        f=self.fixture()
        value=adapter.catalogue(f.saved,f.token.observation)
        self.assertEqual(set(value),{'own','beliefs'})
        self.assertEqual(adapter.actions(value),[f.choice])
        value['beliefs']['candidates'].clear()
        self.assertEqual(adapter.actions(f.saved.explicit_religion_beliefs),[f.choice])
        f.created=-1
        value=adapter.catalogue(f.saved,f.token.observation)
        self.assertIsNone(value['beliefs'])
        self.assertEqual(adapter.actions(value),[])
        f.created=4;f.equipped=[2,5]
        value=adapter.catalogue(f.saved,f.token.observation)
        self.assertEqual(value['beliefs']['reason'],'no_unspent_belief')
        self.assertEqual(adapter.actions(value),[])
        self.assertEqual(f.machine,[])

    def test_actual_registered_owner_applies_or_refuses_before_archive(self):
        for allowed in (True,False):
            with self.subTest(can_start=allowed):
                f=self.fixture();p=f.backend.prefix
                self.assertIs(type(p),SavedLoadServices)
                self.assertIs(type(p.runtime),NativeScriptRuntime)
                self.assertFalse(hasattr(p.runtime,'read'))
                self.assertIs(type(p.actions),SavedActionTransport)
                self.assertIs(type(p.deferred_events),DeferredService)
                adapter.catalogue(f.saved,f.token.observation)
                f.can_start=allowed;f.set_active(True)
                result=adapter.apply(f.saved,f.choice,f.token.observation)
                self.assertEqual(result['status'],'completed' if allowed else 'refused')
                self.assertEqual(f.equipped,[2] if allowed else [])
                self.assertEqual(f.token.publication_count,1 if allowed else 0)
                self.assertEqual(p.actions.pending,[])
                self.assertEqual(p.deferred_events.pending,[])
                p.actions.require_empty_native_queue()
                if allowed:
                    self.assertEqual((result['selected_index'],result['selected_hash'],result['selected_class']),
                                     (2,0xffffffff,'BELIEF_CLASS_FOLLOWER'))
                else:
                    self.assertNotIn(('request',),f.machine)
                    self.assertNotIn(b'@native_religion_belief_effect',f.evaluations)
                f.close()

    def test_stale_identity_and_other_families_refuse_without_request(self):
        f=self.fixture();adapter.catalogue(f.saved,f.token.observation);f.set_active(True)
        for action in (dict(f.choice,hash=1),dict(f.choice,index=True),dict(f.choice,**{'class':'BELIEF_CLASS_WORSHIP'}),
                       dict(kind='found_religion',index=4,hash=4)):
            with self.assertRaises((ValueError,RuntimeError)):
                adapter.apply(f.saved,action,f.token.observation)
        with self.assertRaisesRegex(RuntimeError,'hash or class changed'):
            f.backend.prefix.inspect_religion_belief_choice(0,selected_index=2,selected_hash=1,
                                                          selected_class='BELIEF_CLASS_FOLLOWER')
        self.assertNotIn(('request',),f.machine)

    def test_missing_action_admission_and_wrong_image_refuse(self):
        f=self.fixture();f.set_active(True)
        with patch.object(source,'actions_qualified',return_value=False):
            with self.assertRaisesRegex(ValueError,'not qualified'):
                adapter.apply(f.saved,f.choice,f.token.observation)
        f.backend.core._civ6_host_execution_image=None
        with self.assertRaises(ValueError):
            adapter.apply(f.saved,f.choice,f.token.observation)
        self.assertEqual(f.evaluations,[])
        self.assertEqual(f.machine,[])


if __name__=='__main__':
    unittest.main()

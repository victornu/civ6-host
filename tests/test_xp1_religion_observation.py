"""Real saved owners plus isolated Lua; no GameCore process or gameplay."""
from hashlib import sha256
from pathlib import Path
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime
from civ6_host.runtime import xp1_religion_observation as adapter
from civ6_host.runtime import xp1_religion_observation_source as source
from civ6_host.runtime.native import native_religion_observation as shared
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.explicit_saved_operations import ExplicitSavedOperations
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.deferred_service import DeferredService
from test_xp1_pantheon import Fixture as ExistingFixture


_ENV = b'''
local pid,turn=0,8
local city={GetOwner=function() return 0 end,GetID=function() return 65536 end}
local holy={player=HOLY_OWNER,type=2,id=65536}
local religion={GetReligionTypeCreated=function() return CREATED end,
 HasReligiousFoundingUnit=function() return true end,
 GetNumBeliefsEarned=function() return 2 end,GetHolyCityID=function() return holy end}
local player={IsAlive=function() return true end,IsTurnActive=function() return true end,
 IsTurnActiveComplete=function() return true end,GetReligion=function() return religion end,
 GetCities=function() return {Members=function()
  local i=0;return function() i=i+1;if i==1 then return i,city end end end} end}
local Players={[0]=player}
local foreign=setmetatable({Founder=1},{__index=function(_,key)
 error('foreign religion data read: '..key) end})
local Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return turn end,
 GetReligion=function() return {GetReligions=function()
  if CREATED==-1 then return {foreign} end
  return {foreign,{Religion=CREATED,Founder=0,Beliefs={24,34}}}
 end} end}
local function forbidden() error('snapshot attempted native action') end
local UnitManager={RequestOperation=forbidden,CanStartOperation=forbidden}
local UI={RequestPlayerOperation=forbidden}
local Map={GetPlotByIndex=forbidden,GetPlot=forbidden}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.created = -1
        self.holy_owner = 0
        self.evaluations = []

    def evaluate(self, child, code, name, **kwargs):
        if child is not self.token.ui_child:
            raise AssertionError('Foreign UI child')
        self.evaluations.append(name)
        if name == b'@religion_observation_guards':
            return LuaRuntime(encoding=None).execute(code)
        if name == b'@native_religion_observation_turn':
            return b'8'
        if name == b'@native_own_religion_observation':
            self.assert_capacity(kwargs)
            env = _ENV.replace(b'HOLY_OWNER',str(self.holy_owner).encode()).replace(b'CREATED',str(self.created).encode())
            return LuaRuntime(encoding=None).execute(env+code)
        raise AssertionError('Unexpected Lua call: '+repr(name))

    @staticmethod
    def assert_capacity(kwargs):
        if kwargs != dict(capacity=shared.MAX_RESPONSE):
            raise AssertionError('Readback bound changed')


class ReligionObservationTests(unittest.TestCase):
    def fixture(self):
        f=Fixture()
        self.addCleanup(f.close)
        return f

    def test_source_pins_complete_bodies_and_explicit_profile(self):
        proof=source.verify_source()
        self.assertEqual(proof['functions']['GetReligions']['fragment_count'],7)
        self.assertEqual(proof['functions']['GetReligions']['total_length'],1075)
        self.assertFalse(proof['action_abi_qualified'])
        for path,digest in source.source_dependencies(_XP1_PROFILE).items():
            self.assertEqual(sha256(Path(path).read_bytes()).hexdigest(),digest)
        with self.assertRaises(ValueError):
            source.source_dependencies(None)
        with self.assertRaises(ValueError):
            shared.build_source(0,8,core_sha256='unknown')

    def test_base_default_and_xp1_use_identical_lua_and_selected_source(self):
        self.assertEqual(shared.build_source(0,8),shared.build_source(0,8,core_sha256=XP1_CORE_SHA256))
        for profile in (shared.BASE_CORE_SHA256,XP1_CORE_SHA256):
            marker=LuaRuntime(encoding=None).execute(shared.guard_case(core_sha256=profile))
            self.assertEqual(marker,b'native-religion-observation-guards-ok')
        payload=b'religion-observation-v1|0|8|-1|1|2|0|2|65536|0|-1|-1|0'
        self.assertEqual(shared.parse_observation(payload,0,8)['source_proof_sha256'],shared.PROOF_SHA256)
        self.assertEqual(shared.parse_observation(payload,0,8,core_sha256=XP1_CORE_SHA256)['source_proof_sha256'],source.SOURCE[1])

    def test_actual_owner_composition_preserves_true_after_consumption(self):
        f=self.fixture();p=f.backend.prefix
        self.assertIs(type(p),SavedLoadServices)
        self.assertIsInstance(p,ExplicitSavedOperations)
        self.assertIs(type(p.runtime),NativeScriptRuntime)
        self.assertFalse(hasattr(p.runtime,'read'))
        self.assertIs(type(p.actions),SavedActionTransport)
        self.assertIs(type(p.deferred_events),DeferredService)
        value=adapter.snapshot(f.saved,f.token.observation)
        self.assertTrue(value['has_religious_founding_unit'])
        self.assertEqual(value['num_beliefs_earned'],2)
        self.assertEqual(value['religion_type_created'],-1)
        self.assertTrue(value['holy_city_present'])
        self.assertIsNone(value['own_religion'])
        self.assertFalse(value['action_effect_verified'])
        self.assertEqual(value['source_proof_sha256'],source.SOURCE[1])
        f.created=1
        value=adapter.snapshot(f.saved,f.token.observation)
        self.assertEqual(value['own_religion'],dict(religion_index=1,founder=0,belief_indices=[24,34]))
        self.assertTrue(value['has_religious_founding_unit'])
        self.assertEqual(f.evaluations.count(b'@religion_observation_guards'),1)
        self.assertEqual(f.machine,[])
        self.assertEqual(p.actions.pending,[])
        self.assertEqual(p.deferred_events.pending,[])

    def test_partial_holy_city_scope_and_actor_guards_are_explicit(self):
        f=self.fixture()
        f.holy_owner=1
        with self.assertRaisesRegex(Exception,'holy city is not owned'):
            adapter.snapshot(f.saved,f.token.observation)
        f.holy_owner=0
        for identity in (dict(player_id=True,turn=8),dict(player_id=0,turn=True)):
            with self.assertRaises(ValueError):
                adapter.snapshot(f.saved,identity)
        with self.assertRaisesRegex(ValueError,'turn changed'):
            adapter.snapshot(f.saved,dict(player_id=0,turn=9))
        self.assertEqual(f.machine,[])

    def test_wrong_image_live_binding_and_pending_fifo_refuse_before_read(self):
        f=self.fixture();p=f.backend.prefix
        f.backend.core._civ6_host_execution_image=None
        with self.assertRaises(ValueError):
            p.inspect_own_religion_snapshot(0)
        f.backend.core._civ6_host_execution_image=_XP1_PROFILE
        with patch.object(f.backend.runtime,'read',return_value=b'changed'):
            with self.assertRaisesRegex(ValueError,'binding differs'):
                p.inspect_own_religion_snapshot(0)
        p.actions.pending.append(b'queued-native-request')
        with self.assertRaisesRegex(RuntimeError,'drained queues'):
            p.inspect_own_religion_snapshot(0)
        p.actions.pending.clear()
        self.assertEqual(f.evaluations,[])


if __name__ == '__main__':
    unittest.main()

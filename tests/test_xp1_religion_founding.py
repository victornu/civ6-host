"""Predefined foundation on real saved owners and queue; no engine execution."""
import ctypes as C
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime

from civ6_host.runtime import xp1_religion_founding as adapter
from civ6_host.runtime import xp1_religion_founding_source as source
from civ6_host.runtime.native import native_religion_founding as builders
from civ6_host.runtime.native import native_saved_religion as shared
from civ6_host.runtime.native import native_player_operation_request as request
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.deferred_service import DeferredService
from test_xp1_pantheon import Fixture as ExistingFixture


ENV = b'''
local created,earned,holyPresent,foreignHoly,claimed=CREATED,EARNED,HOLY,FOREIGN,CLAIMED
local city={GetOwner=function() return 0 end,GetID=function() return 65536 end}
local foreign=setmetatable({Founder=1},{__index=function(_,key) error('foreign field '..key) end})
local religion={GetReligionTypeCreated=function() return created end,
 GetNumBeliefsEarned=function() return earned end,
 HasReligiousFoundingUnit=function() return true end,
 GetHolyCityID=function()
 if not holyPresent then return {player=-1,type=2,id=-1} end
 return {player=foreignHoly and 1 or 0,type=2,id=65536} end}
local player={GetID=function() return 0 end,IsAlive=function() return true end,
 IsTurnActive=function() return true end,IsTurnActiveComplete=function() return true end,
 GetReligion=function() return religion end,
 GetCities=function() return {Members=function()
  local i=0;return function() i=i+1;if i==1 then return i,city end end end} end}
local global={GetReligions=function()
 if created==-1 then return {foreign} end
 return {foreign,{Religion=created,Founder=0,Beliefs={}}} end,
 HasBeenFounded=function(_,i) return i==4 or i==created or claimed end}
local definitions={{Index=12,Hash=0,Pantheon=false,RequiresCustomName=false},
 {Index=0,Hash=10,Pantheon=true,RequiresCustomName=false},
 {Index=1,Hash=1,Pantheon=false,RequiresCustomName=true},
 {Index=4,Hash=4,Pantheon=false,RequiresCustomName=false},
 {Index=9,Hash=-1,Pantheon=false,RequiresCustomName=false}}
local callable=setmetatable({}, {__call=function()
 local i=0;return function() i=i+1;return definitions[i] end end})
for _,row in ipairs(definitions) do callable[row.Index]=row end
local GameInfo={Religions=callable}
local Players={[0]=player}
local Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 8 end,IsAllowStrategicCommands=function(p) return p==0 end,
 GetReligion=function() return global end}
local PlayerOperations={FOUND_RELIGION=-1529151563,PARAM_RELIGION_TYPE=581065611,
 PARAM_INSERT_MODE=-1406149623,VALUE_EXCLUSIVE=-1744919098}
local function forbidden() error('Lua builder submitted an operation') end
local UI={RequestPlayerOperation=forbidden}
local UnitManager={RequestOperation=forbidden}
'''


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__()
        self.created = -1
        self.earned = 2
        self.holy = True
        self.foreign_holy = False
        self.claimed = False
        self.apply_native = True
        self.native_selected = 9
        self.evaluations = []
        self.choice = dict(kind='found_religion', index=9, hash=0xffffffff)
        self.stack.enter_context(patch.object(shared, 'observe_player', self.observe_native))

    def evaluate(self, child, code, name, **kwargs):
        if child is not self.token.ui_child:
            raise AssertionError('Foreign Lua child')
        self.evaluations.append(name)
        if name in (b'@religion_observation_guards', b'@native_religion_founding_guards'):
            return LuaRuntime(encoding=None).execute(code)
        if name == b'@native_religion_observation_turn':
            return b'8'
        if name in (b'@native_own_religion_observation', b'@explicit_religion_foundation',
                    b'@native_religion_founding_catalog', b'@native_religion_founding_revalidation',
                    b'@native_religion_founding_effect'):
            env = ENV
            for key, value in ((b'CREATED', self.created), (b'EARNED', self.earned),
                    (b'HOLY', self.holy), (b'FOREIGN', self.foreign_holy), (b'CLAIMED', self.claimed)):
                env = env.replace(key, str(value).lower().encode())
            return LuaRuntime(encoding=None).execute(env+code)
        raise AssertionError('Unexpected Lua boundary '+repr(name))

    def factory(self, result, *args):
        from civ6_host.runtime.xp1_research_profile import player_operation_abi
        abi = player_operation_abi(XP1_CORE_SHA256, request._METHODS)
        parent = super().factory(result, *args)
        def bind(address):
            if address-self.memory.base != abi.methods['can_start'][0]:
                return parent(address)
            def call(*values):
                self.machine.append(('can_start',))
                if values[1:3] != (0, builders.FOUND_RELIGION) or values[4] is not False:
                    raise AssertionError('Native foundation CanStart arguments changed')
                actual = {key: int.from_bytes(C.string_at(ptr+8, 4), 'little')
                          for key, ptr in self.maps[values[3]].items()}
                if actual != {builders.PARAM_INSERT_MODE: builders.VALUE_EXCLUSIVE,
                              builders.PARAM_RELIGION_TYPE: self.choice['hash']}:
                    raise AssertionError('Native foundation scalar parameters changed')
                return int(self.can_start)
            return call
        return bind

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva == self.token.transport.transport_abi.drain_rva:
            parent = super().virtual(core, pointer, slot, rva, result, *args)
            def drain(ctx):
                parent(ctx)
                if self.apply_native:
                    self.created = self.native_selected
            return drain
        return super().virtual(core, pointer, slot, rva, result, *args)


class FoundationTests(unittest.TestCase):
    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        return f

    def test_source_profile_base_default_and_lua_guards(self):
        self.assertTrue(source.actions_qualified())
        self.assertTrue(source.source_dependencies(_XP1_PROFILE))
        self.assertEqual(builders.catalog_source(0, 60),
                         builders.catalog_source(0, 60, core_sha256=XP1_CORE_SHA256))
        for profile in (builders.CORE_SHA256, XP1_CORE_SHA256):
            self.assertEqual(LuaRuntime(encoding=None).execute(builders.guard_case(core_sha256=profile)),
                             b'native-religion-founding-guard-ok')
        with self.assertRaises(ValueError):
            builders.catalog_source(0, 60, core_sha256='unknown')
        with self.assertRaises(ValueError):
            source.source_dependencies(None)

    def test_all_predefined_choices_native_preconditions_and_custom_name_limit(self):
        f = self.fixture()
        value = adapter.catalogue(f.saved, f.token.observation)
        self.assertEqual(set(value), {'own', 'foundation'})
        self.assertEqual(adapter.actions(value), [f.choice, dict(kind='found_religion', index=12, hash=0)])
        self.assertTrue(value['own']['has_religious_founding_unit'])
        self.assertEqual(f.machine, [])
        value['foundation']['candidates'].clear()
        self.assertEqual(len(adapter.actions(f.saved.explicit_religion_founding)), 2)
        f.claimed = True
        value = adapter.catalogue(f.saved, f.token.observation)
        self.assertEqual(value['foundation']['status'], 'not_due')
        self.assertEqual(adapter.actions(value), [])
        f.claimed = False
        for mode in ('already_founded', 'no_site'):
            f.created = 9 if mode == 'already_founded' else -1
            f.holy = mode != 'no_site'
            value = adapter.catalogue(f.saved, f.token.observation)
            self.assertIsNone(value['foundation'])
            self.assertEqual(adapter.actions(value), [])
        f.holy = True
        f.earned = 0
        with self.assertRaisesRegex(Exception, 'no earned religion beliefs'):
            adapter.catalogue(f.saved, f.token.observation)
        f.earned = 2
        f.foreign_holy = True
        with self.assertRaises(Exception):
            adapter.catalogue(f.saved, f.token.observation)

    def test_real_registered_owner_transport_lifetime_and_refusal_without_archive(self):
        for allowed in (True, False):
            with self.subTest(can_start=allowed):
                f = self.fixture()
                p = f.backend.prefix
                self.assertIs(type(p), SavedLoadServices)
                self.assertIs(type(p.runtime), NativeScriptRuntime)
                self.assertFalse(hasattr(p.runtime, 'read'))
                self.assertIs(type(p.actions), SavedActionTransport)
                self.assertIs(type(p.deferred_events), DeferredService)
                adapter.catalogue(f.saved, f.token.observation)
                f.can_start = allowed
                f.set_active(True)
                result = adapter.apply(f.saved, f.choice, f.token.observation)
                self.assertEqual(result['status'], 'completed' if allowed else 'refused')
                self.assertEqual(result['source_sha256'], source.SOURCE[1])
                self.assertEqual(f.created, 9 if allowed else -1)
                self.assertEqual(f.token.publication_count, 1 if allowed else 0)
                self.assertEqual(f.maps, {})  # owned maps destroyed on both paths
                self.assertEqual(p.actions.pending, [])
                self.assertEqual(p.deferred_events.pending, [])
                p.actions.require_empty_native_queue()
                if allowed:
                    self.assertEqual((result['selected_index'], result['selected_hash']), (9, 0xffffffff))
                    own = p.inspect_own_religion_snapshot(0)
                    self.assertTrue(own['has_religious_founding_unit'])
                    self.assertEqual(own['own_religion']['belief_indices'], [])
                    self.assertEqual(own['num_beliefs_earned'], 2)
                else:
                    self.assertNotIn(('request',), f.machine)
                    self.assertNotIn(b'@native_religion_founding_effect', f.evaluations)
                f.close()

    def test_changed_offer_hash_and_implicit_or_foreign_choices_never_submit(self):
        f = self.fixture()
        adapter.catalogue(f.saved, f.token.observation)
        f.set_active(True)
        for action in (dict(f.choice, hash=1), dict(f.choice, index=True),
                       dict(f.choice, custom_name='example'), dict(kind='add_belief', index=2, hash=2, **{'class': 'BELIEF_CLASS_FOLLOWER'})):
            with self.assertRaises((ValueError, RuntimeError)):
                adapter.apply(f.saved, action, f.token.observation)
        with self.assertRaisesRegex(RuntimeError, 'hash changed'):
            f.backend.prefix.inspect_religion_founding_choice(0, selected_index=9, selected_hash=1)
        with self.assertRaises(ValueError):
            f.backend.prefix.inspect_religion_founding_choice(0, selected_index=None, selected_hash=1)
        f.claimed = True
        with self.assertRaisesRegex(RuntimeError, 'stale or unavailable'):
            adapter.apply(f.saved, f.choice, f.token.observation)
        self.assertNotIn(('request',), f.machine)

    def test_missing_effect_or_wrong_effect_is_not_completed(self):
        for selected in (None, 12):
            f = self.fixture()
            adapter.catalogue(f.saved, f.token.observation)
            f.set_active(True)
            f.apply_native = selected is not None
            f.native_selected = selected
            with self.subTest(selected=selected), self.assertRaises(Exception):
                adapter.apply(f.saved, f.choice, f.token.observation)
            self.assertIn(('request',), f.machine)
            self.assertEqual(f.maps, {})
            f.close()

    def test_action_admission_exact_image_and_live_foundation_source(self):
        f = self.fixture()
        f.set_active(True)
        with patch.object(source, 'actions_qualified', return_value=False):
            with self.assertRaisesRegex(ValueError, 'not qualified'):
                adapter.apply(f.saved, f.choice, f.token.observation)
        f.backend.core._civ6_host_execution_image = None
        with self.assertRaises(ValueError):
            adapter.apply(f.saved, f.choice, f.token.observation)
        self.assertEqual(f.machine, [])
        self.assertEqual(f.evaluations, [])
        f.close()
        f = self.fixture()
        span = source.verify_source()['code_spans']['found_religion']['fragments'][0]
        address = f.memory.base+int(span['rva'], 16)
        raw = f.backend.runtime.read(address, span['length'])
        # The existing memory fixture overlays whole reads, not individual
        # bytes inside a larger PE-backed read. Replace the complete span.
        f.memory.put(address, bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(ValueError, 'Live installed'):
            adapter.catalogue(f.saved, f.token.observation)
        self.assertEqual(f.evaluations, [])


if __name__ == '__main__':
    unittest.main()

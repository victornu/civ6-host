"""Exercise the real Lua chunks and exact Locale ABI boundary offline."""

import ctypes as C
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lupa.lua51 import LuaRuntime

from civ6_host.runtime import xp1_religion_custom_names as names
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_locale_diagnostic as locale
from civ6_host.runtime.native import native_religion_observation as own_reader


_GUARD = br"""
local available={
 {Index=4,Hash=-4,Pantheon=false,RequiresCustomName=true,Name='LOC_RELIGION_CUSTOM'},
 {Index=6,Hash=6,Pantheon=true,RequiresCustomName=true},
 {Index=5,Hash=99,Pantheon=false,RequiresCustomName=false},
 {Index=9,Hash=123,Pantheon=false,RequiresCustomName=true,Name='LOC_RELIGION_CUSTOM'}
}
local hidden=setmetatable({Founder=1},{__index=function(_,key) error('foreign '..key) end})
local published=created==-1 and {hidden} or {
 hidden, {Founder=0,Religion=created,Beliefs={},CustomName=custom}
}
local religion={
 GetReligionTypeCreated=function() return created end,
 HasReligiousFoundingUnit=function() return false end,
 GetNumBeliefsEarned=function() return earned end,
 GetHolyCityID=function() return {player=0,type=2,id=23} end
}
local player={GetID=function()return 0 end,IsAlive=function()return true end,
 IsTurnActive=function()return true end,IsTurnActiveComplete=function()return true end,
 GetReligion=function()return religion end,
 GetCities=function() return {Members=function()
  local done=false
  return function()
   if not done then
    done=true
    return 1,{GetOwner=function()return 0 end,GetID=function()return 23 end}
   end
  end
 end} end}
local gameReligion={GetReligions=function()return published end,
 HasBeenFounded=function(_,idx)return idx==9 or idx==created end}
local Game={
 GetLocalPlayer=function()return 0 end,
 GetLocalObserver=function()return observer end,
 GetCurrentGameTurn=function()return 62 end,
 IsAllowStrategicCommands=function(id)return id==0 end,
 GetReligion=function()return gameReligion end
}
local Players={[0]=player}
local GameInfo={GameCapabilities=rename and {CAPABILITY_RENAME={}} or {},
 Religions=setmetatable({[4]=available[1],[9]=available[4]},{__call=function()
  local i=0
  return function() i=i+1 return available[i] end
 end})}
local PlayerOperations={FOUND_RELIGION=2765815733,PARAM_RELIGION_TYPE=581065611,
 PARAM_INSERT_MODE=2888817673,VALUE_EXCLUSIVE=2550048198,PARAM_RELIGION_CUSTOM_NAME=182311263}
local Locale={Lookup=function(tag)
 if tag=='LOC_UI_RELIGION_CHOOSE_RELIGION_NAME' then return placeholder end
 if tag=='LOC_RELIGION_CUSTOM' then return localized end
 error('unexpected localized field')
end}
"""


class LuaFixture:
    def __init__(self, *, created=-1, custom=None, rename=True, localized='Religion personnalisée'):
        self.lua = LuaRuntime(encoding=None)
        globals_ = self.lua.globals()
        for key, value in dict(created=created, custom=None if custom is None else custom.encode(),
                rename=rename, observer=0, earned=2, localized=localized.encode(),
                placeholder='Nommer la religion'.encode()).items():
            globals_[key.encode()] = value
        self.observe = dict(player_id=0, turn=62, cities=[dict(owner=0,id=23)])
        prefix, status = b'religion-observation-v1|0|62|', b'|0|2|0|2|23|'
        suffix = b'0|-1|-1|0' if created==-1 else b'1|4|0|0'
        self.own = own_reader.parse_observation(prefix + str(created).encode() + status + suffix,
            0,62,core_sha256=names.XP1_CORE_SHA256)
        service_owner=SimpleNamespace(manifest={'localization_bootstrap':
                                               {'locale':'fr_FR','dictionary_flag':False}})
        self.prefix = SimpleNamespace(ui_child=object(),
                                      runtime=SimpleNamespace(evaluate_text=self.evaluate,service_owner=service_owner),
                                      inspect_own_religion_snapshot=lambda _pid: self.own)

    def evaluate(self, _child, source, _name, **kwargs):
        return self.lua.execute(_GUARD + source)


class NameRuntime(TestCase):
    def catalogue(self, fixture):
        with patch.object(names,'attach_locale'):
            return names._catalogue(fixture.prefix,fixture.observe)

    def test_actual_sources_pinned_for_xp1(self):
        pins = names.source_dependencies(_XP1_PROFILE)
        self.assertIn(names.SOURCE[1], pins.values())
        self.assertIn(names._PROGRAMMATIC_SOURCE[1], pins.values())

    def test_actual_lua_catalogue_and_unicode_input(self):
        c = self.catalogue(LuaFixture())
        expected=dict(kind=names.KIND,index=4,hash=0xfffffffc)
        self.assertEqual(names.actions(c), [expected])
        self.assertEqual(c['placeholder'],'Nommer la religion')
        self.assertIsNone(c['own_custom_name'])
        sample = 'e\u0301🌙\t\r\n\x01{\\'
        self.assertEqual(names.choose(c,expected,{'name':sample}),dict(expected,custom_name=sample))

    def test_programmatic_default_can_exceed_interactive_limit(self):
        c = self.catalogue(LuaFixture(rename=False,localized='é'*100))
        [candidate]=names.actions(c)
        self.assertEqual(names.choose(c,candidate)['custom_name'],'é'*100)
        with self.assertRaises(ValueError):
            names.choose(c,candidate,{'name':'supplied'})
        with self.assertRaisesRegex(ValueError,'Unqualified programmatic'):
            self.catalogue(LuaFixture(rename=False,localized='é'*128))

    def test_readback_nil_empty_and_bytes_untouched(self):
        for expected in (None, '', 'e\u0301🌙\t\r\n\x01{\\'):
            with self.subTest(expected=expected):
                fixture=LuaFixture(created=4,custom=expected)
                c=self.catalogue(fixture)
                self.assertEqual(c['own_custom_name'],expected)
                self.assertEqual(c['status'],'not_due')
                self.assertEqual(names._read_own_custom_name(fixture.prefix,fixture.own,0,62,
                    expected_hash=0xfffffffc),expected)
                fixture.lua.globals()[b'observer']=1
                with self.assertRaisesRegex(Exception,'foreign|observer'):
                    names._read_own_custom_name(fixture.prefix,fixture.own,0,62)

    def test_wrong_definition_hash_refused_on_effect(self):
        fixture=LuaFixture(created=4,custom='Religio')
        with self.assertRaisesRegex(Exception,'definition changed'):
            names._read_own_custom_name(fixture.prefix,fixture.own,0,62,expected_hash=9)

    def test_official_placeholder_rejected_without_invoking_player_operation(self):
        fixture=LuaFixture()
        c=self.catalogue(fixture)
        [candidate]=names.actions(c)
        action=names.choose(c,candidate,{'name':c['placeholder'].lower()})
        saved=SimpleNamespace(explicit_religion_custom_names=c)
        with patch.object(names,'_bind',return_value=fixture.prefix), \
             patch.object(names,'attach_locale'), \
             patch.object(names,'_uppercase',return_value=b'FROM_OFFICIAL_NATIVE_TRANSFORM') as uppercase, \
             patch.object(names,'request_player_operation') as request:
            outcome=names.apply(saved,action,fixture.observe)
        request.assert_not_called()
        self.assertEqual([row.args[1] for row in uppercase.call_args_list],
            [action['custom_name'],c['placeholder']])
        self.assertEqual(outcome,dict(status='refused',observation=fixture.observe,
            refusal_code=names.UI_INVALID,request=None,source_sha256=names.SOURCE[1]))


class LocaleABI(TestCase):
    def test_explicit_format_constructor_and_counted_readback(self):
        base=0x180000000
        trace=[]
        class Function:
            def __init__(self,rva,func):
                self.rva,self.func=rva,func
            def __call__(self,*args):
                trace.append((self.rva,*args))
                return self.func(*args)

        expected=b'A\0C\xf0\x9f\x8c\x99'
        data=C.create_string_buffer(expected)
        def to_utf8(_obj,count,mode):
            self.assertEqual(mode,1)
            C.cast(count,C.POINTER(C.c_uint)).contents.value=len(expected)
            return C.addressof(data)
        lib=SimpleNamespace(_handle=base)
        for key,rva,func in (
                (locale._CONSTRUCT_STRING,0xbfb0,lambda obj,source,count:obj.value),
                (locale._PUSH_STRING,0xda70,lambda obj,data:True),
                (locale._TO_UTF8,0xecb0,to_utf8),(locale._DESTROY,0xc130,lambda _:None)):
            setattr(lib,key,Function(rva,func))
        native_cast=C.cast
        with patch.object(locale.C,'cast', side_effect=lambda obj,ptype:
                C.c_void_p(base+obj.rva) if isinstance(obj,Function) else native_cast(obj,ptype)):
            actual=locale._native_string_bytes(lib,b'{1: upper}',(b'a\t\x01',),
                explicit_length=True,constructor_rva=0xbfb0)
        self.assertEqual(actual,expected)  # Embedded output NUL cannot be truncated by comparison.
        self.assertEqual(trace[0][2:],(b'{1: upper}',10))
        self.assertEqual(trace[1][2:],(b'a\t\x01',))
        self.assertEqual([row[0] for row in trace],[0xbfb0,0xda70,0xecb0,0xc130])
        self.assertEqual(len({row[1].value for row in trace}),1)

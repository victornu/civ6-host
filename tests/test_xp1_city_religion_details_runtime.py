
"""XP1 own-city religion detail ABI closure and protected Lua boundary."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from struct import unpack_from
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.contracts import city_religion
from civ6_host.runtime import xp1_city_religion as reader
from civ6_host.runtime.resource_resolution import resolve_path


_LUA = br'''
local function no_other_owner() error('Foreign religious read') end
local Game={
 GetLocalPlayer=function() return 0 end,
 GetLocalObserver=function() return local_observer() end,
 GetCurrentGameTurn=function() return local_turn() end,
 GetReligion=no_other_owner,
 IsAllowStrategicCommands=function() return false end
}
local Map={
 GetGridSize=function() return 4,3 end,
 GetPlotCount=function() return 12 end
}
local owned={
 {GetID=function()return 65538 end, GetOwner=function()return 0 end,
   GetReligion=function()return {GetMajorityReligion=function()return -1 end,
     GetReligionsInCity=function()return {} end,
     GetTotalPressureOnCity=no_other_owner} end},
 {GetID=function()return 65536 end, GetOwner=function()return city_owner() end,
   GetReligion=function()return {GetMajorityReligion=function()return 3 end,
     GetReligionsInCity=function()
      if malformed() then return {[2]={Religion=0,Followers=0,Pressure=1}} end
      return {{Religion=3,Followers=4,Pressure=8388608},
              setmetatable({Religion=-1},{__index=no_other_owner}),
              {Religion=0,Followers=0,Pressure=0.5},
              {Religion=2,Followers=1,Pressure=-8388608}}
     end,
     GetTotalPressureOnCity=function(_,index) return incoming(index) end,
     GetPressureFromCity=no_other_owner, GetReligiousPressureSources=no_other_owner,
     GetNextReligion=no_other_owner} end}
}
local Players=setmetatable({
 [0]={GetCities=function() return {Members=function()return ipairs(owned) end} end}
},{__index=no_other_owner})
'''

def file_reader(payload):
    """Project PE disk sections to their RVAs without mapping or executing it."""
    pe,=unpack_from('<I',payload,0x3c)
    count,=unpack_from('<H',payload,pe+6)
    optional_bytes,=unpack_from('<H',payload,pe+20)
    sections=[]
    for i in range(count):
        at=pe+24+optional_bytes+i*40
        virtual_size,start,raw_size,offset=unpack_from('<IIII',payload,at+8)
        sections.append((start,offset,raw_size))
    def spoof_read(address,length):
        rva=address-0x180000000
        for start,offset,size in sections:
            if start<=rva and rva+length<=start+size:
                at=offset+rva-start
                return payload[at:at+length]
        raise ValueError('Test read escaped the filed PE sections')
    return spoof_read


class CityReligionDetailsRuntimeTests(TestCase):
    def test_detail_closure_and_live_gate_use_filed_exact_xp1_image(self):
        plain=reader.source_dependencies(reader._XP1_PROFILE)
        extended=reader.source_dependencies(reader._XP1_PROFILE,include_details=True)
        self.assertTrue(plain.items() <= extended.items())
        self.assertNotIn(reader.DETAILS_SOURCE[1],plain.values())
        self.assertIn(reader.DETAILS_SOURCE[1],extended.values())
        self.assertEqual(len(extended)-len(plain),5)
        with self.assertRaisesRegex(ValueError,'exact installed'):
            reader.source_dependencies(None,include_details=True)
        with self.assertRaisesRegex(ValueError,'Boolean'):
            reader.source_dependencies(reader._XP1_PROFILE,include_details=1)

        core=SimpleNamespace(_handle=0x180000000,_civ6_host_execution_image=reader._XP1_PROFILE)
        payload=resolve_path(Path(reader._XP1_PROFILE.path)).read_bytes()
        self.assertEqual(sha256(payload).hexdigest(),reader._XP1_PROFILE.image_sha256)
        machine=Mock(side_effect=file_reader(payload))
        saved=SimpleNamespace(_check_query=Mock(),
            backend=SimpleNamespace(core=core,load_abi=SimpleNamespace(core_sha256=reader.XP1_CORE_SHA256),
                captured_bundle=SimpleNamespace(reference=reader.REFERENCE),runtime=SimpleNamespace(read=machine)),
            prefix=object())
        reader._bind_details(saved)
        count=machine.call_count
        self.assertGreater(count,20)
        reader._bind_details(saved)
        self.assertEqual(machine.call_count,count)
        saved.prefix=object()
        valid=file_reader(payload)
        bad=0x180000000+0x5ad9db  # GetTotalPressureOnCity registrar window.
        machine.side_effect=lambda at,size: bytes(size) if at==bad else valid(at,size)
        with self.assertRaisesRegex(ValueError,'binding differs at 0x5ad9db'):
            reader._bind_details(saved)

    def test_protected_owned_city_numbers_match_display_and_keep_v1_majority(self):
        obs=dict(player_id=0,turn=42,width=4,height=3,plots=[],
                 cities=[dict(id=65536,owner=0),dict(id=65538,owner=0)])
        expected=dict(schema=city_religion.SCHEMA,player_id=0,turn=42,
            cities=[dict(city_id=65536,majority_religion=3),dict(city_id=65538,majority_religion=-1)])
        lua=LuaRuntime(encoding=None)
        controls=dict(owner=0,turn=42,observer=0,malformed=False)
        values={0:0.5,2:-0.50390625,3:-0.5}
        calls=[]
        def incoming(index):
            calls.append(index)
            return values[index]
        g=lua.globals()
        g.city_owner=lambda:controls['owner']
        g.local_turn=lambda:controls['turn']
        g.local_observer=lambda:controls['observer']
        g.malformed=lambda:controls['malformed']
        g.incoming=incoming
        def execute(chunk):
            return lua.execute(_LUA+chunk)
        first=reader.readback_source(0,42,obs)
        self.assertEqual(reader.parse_readback(execute(first),0,42,obs),expected)
        self.assertEqual(calls,[])
        details=reader.readback_source(0,42,obs,include_details=True)
        native=execute(details)
        value=reader.parse_details(native,0,42,obs)
        self.assertEqual(calls,[3,0,2])  # No query for non-displayed sentinel.
        self.assertEqual(value['cities'][0]['religions'],[
            dict(religion_index=0,followers=0,pressure_per_turn=1,lifetime_pressure=1),
            dict(religion_index=2,followers=1,pressure_per_turn=-1,lifetime_pressure=-8388608),
            dict(religion_index=3,followers=4,pressure_per_turn=0,lifetime_pressure=8388608),
        ])
        self.assertEqual(value['cities'][1]['religions'],[])
        self.assertEqual(city_religion.project_majority(value,0,42,observation=obs),expected)
        self.assertEqual(reader.parse_details(b'city-religion-v2|0|42',0,42,dict(obs,cities=[]))['cities'],[])
        for damaged in (
            native.replace(b'|4|0|8388608',b'|4|0|8388609'),
            native.replace(b'|4|0|8388608',b'|4|0.5|8388608'),
            native.replace(b'65536|3|3',b'65536|3|5'),
            native.replace(b'65538|-1|0',b'65538|-1|1'),
            native.replace(b'3|4|0|8388608',b'2|4|0|8388608'),
            native.replace(b'65538|-1|0',b'65540|-1|0'),
            native.replace(b'city-religion-v2|0|42',b'city-religion-v2|1|42'),
        ):
            with self.assertRaises(ValueError):
                reader.parse_details(damaged,0,42,obs)
        for key,bad in (('owner',1),('turn',43),('observer',1),('malformed',True)):
            old=controls[key]
            controls[key]=bad
            with self.subTest(key=key),self.assertRaises(LuaError):
                execute(details)
            controls[key]=old
        values[2]=float('nan')
        with self.assertRaisesRegex(LuaError,'invalid city religion pressure'):
            execute(details)

        # Exercise the actual reader's protected-evaluation call and handoff;
        # source admission is independently checked against the file above.
        from unittest.mock import patch
        child=object()
        saved=SimpleNamespace(prefix=SimpleNamespace(ui_child=child,
            runtime=SimpleNamespace(evaluate_text=Mock(return_value=native))))
        with patch.object(reader,'_bind_details') as bound:
            self.assertEqual(reader.read_details(saved,obs,expected_majority=expected),value)
            bound.assert_called_once_with(saved)
            self.assertEqual(saved.prefix.runtime.evaluate_text.call_args.args,
                             (child,details,b'@xp1_own_city_religion_details'))
            changed=deepcopy(expected)
            changed['cities'][0]['majority_religion']=2
            with self.assertRaisesRegex(ValueError,'changed the current own majorities'):
                reader.read_details(saved,obs,expected_majority=changed)

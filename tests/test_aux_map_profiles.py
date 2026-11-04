"""Reuse retained Base decoder cases and exercise explicit XP1/V2 boundaries."""
import ctypes as C
import struct
import types
import unittest
from unittest.mock import Mock

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import aux_map_profiles as profiles
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _body
from civ6_host.runtime.native import native_aux_map_conversion as m
from civ6_host.runtime.native.native_aux_map_adapter import NativeAuxMapAdapter

path = resource_root()/'tests/test_native_aux_map_conversion.py'
text = path.read_text(encoding='utf-8')
old = 'from civ6rl import native_aux_map_conversion as m'
if text.count(old)!=1:
    raise ValueError('Retained decoder fixture import changed')
retained = types.ModuleType('retained_map_cases')
retained.__file__ = str(path)
exec(compile(text.replace(old,'from civ6_host.runtime.native import native_aux_map_conversion as m'),str(path),'exec'),retained.__dict__)


def evaluate(wire):
    stack=[];offset=0
    while offset<len(wire):
        kind,arg,payload=struct.unpack_from('<IIQ',wire,offset);offset+=16
        if kind==m.TABLE:stack.append({})
        elif kind==m.NUMBER:stack.append(struct.unpack('<d',struct.pack('<Q',payload))[0])
        elif kind==m.BOOLEAN:stack.append(bool(arg))
        elif kind==m.NIL:stack.append(None)
        elif kind==m.STRING_BYTES:
            stack.append(wire[offset:offset+arg]);offset+=((arg+16)//16)*16
        elif kind in (m.RAWSET,m.RAWSETI):
            value=stack.pop();key=stack.pop() if kind==m.RAWSET else arg
            if value is not None:stack[-1][key]=value
            else:stack[-1].pop(key,None)
        else:raise AssertionError(kind)
    assert len(stack)==1
    return stack[0]


class MapProfileTests(unittest.TestCase):
    def xp1(self, fields):
        memory=retained.Memory(fields)
        profile=profiles.profile_for_sha(XP1_CORE_SHA256)
        struct.pack_into('<Q',memory.parts[memory.map],0,memory.base+profile.vtable_rva)
        for slot,rva in profile.slots:
            memory.parts[memory.base+profile.vtable_rva+slot]=struct.pack('<Q',memory.base+rva)
        return memory

    def snapshot(self,memory,**kwargs):
        return m.snapshot_parameter_map(memory.base,memory.map,memory.read,
            use_string_keys=False,core_sha256=XP1_CORE_SHA256,**kwargs)

    def test_engine_is_explicit_and_unknown_refuses_without_native_reads(self):
        memory=self.xp1({1:retained.scalar(2,0xffffffff)})
        self.assertEqual(evaluate(self.snapshot(memory).transport),{1:-1})
        with self.assertRaisesRegex(ValueError,'vtable'):
            m.snapshot_parameter_map(memory.base,memory.map,memory.read,use_string_keys=False)
        read=Mock()
        for engine in ('unknown',None):
            with self.assertRaises(ValueError):
                m.snapshot_parameter_map(memory.base,memory.map,read,use_string_keys=False,core_sha256=engine)
        read.assert_not_called()

    def test_utf16_null_byte_strings_and_nested_nil_require_v2(self):
        data='é漢😀\ud800Z'.encode('utf-16-le','surrogatepass')+b'\0\0'
        memory=self.xp1({1:retained.array(6,0xA0000,data,1),
                        2:retained.array(6,0,b'',0),3:retained.array(5,0,b'',0),
                        4:retained.variant_list(0xB0000)})
        memory.parts[0xA0000]=data
        retained.store_list(memory,0xB0000,[retained.array(6,0,b'',0),retained.scalar(2,7)])
        with self.assertRaises(ValueError):self.snapshot(memory)
        snap=self.snapshot(memory,transport_version=2)
        self.assertEqual(evaluate(snap.transport),{1:'é漢😀\ud800Z'.encode('utf-8','surrogatepass'),4:{2:7}})
        self.assertEqual(snap.field_count,4)
        with self.assertRaises(ValueError):self.snapshot(memory,transport_version=True)

    def test_utf16_matches_fixed_native_prefix_and_checks_source_stability(self):
        text='a'*1022+'éz';data=text.encode('utf-16-le')+b'\0\0'
        memory=self.xp1({7:retained.array(6,0xA0000,data,1)})
        memory.parts[0xA0000]=data
        self.assertEqual(evaluate(self.snapshot(memory,transport_version=2).transport),{7:b'a'*1022})
        normal=memory.read
        def changed(address,size):
            result=normal(address,size)
            return b'X'+result[1:] if address==0xA0000 and size==len(data) else result
        memory.read=changed
        with self.assertRaisesRegex(ValueError,'changed during snapshot'):
            self.snapshot(memory,transport_version=2)

    def test_live_source_and_receiver_checks_refuse_altered_code_or_absent_owner(self):
        base=0x200000000;cells={};profile=profiles.profile_for_sha(XP1_CORE_SHA256)
        for value in profiles.source()['functions']['xp1'].values():
            for fragment in _body(value)['fragments']:
                for instruction in fragment['instructions']:
                    raw=bytes.fromhex(instruction['bytes'])
                    cells[base+int(instruction['va'],16)-0x180000000,len(raw)]=raw
        for offset,rva in (*profile.slots,(0x18,profile.name_getter_rva)):
            cells[base+profile.vtable_rva+offset,8]=struct.pack('<Q',base+rva)
        read=lambda address,size:cells[address,size]
        profiles.verify_live(profile,base,read)
        cells[base+0x9F2628,8]=bytes(8)
        with self.assertRaisesRegex(ValueError,'not prepared'):profiles.prepared_game_properties(base,read)
        first=next(iter(cells));cells[first]=bytes(first[1])
        with self.assertRaisesRegex(ValueError,'code differs'):profiles.verify_live(profile,base,read)

    def test_unknown_native_transport_version_refuses_before_callback_install(self):
        install=Mock(return_value=1);version=Mock(return_value=9)
        host=types.SimpleNamespace(LAB_AuxMapInstall=install,LAB_AuxMapTransportVersion=version)
        adapter=NativeAuxMapAdapter(host,object(),types.SimpleNamespace(_handle=0x1000),0x2000,Mock(),read=Mock())
        with self.assertRaisesRegex(ValueError,'version'):adapter.install()
        install.assert_not_called()


def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromTestCase(retained.NativeAuxMapTests))
    return tests

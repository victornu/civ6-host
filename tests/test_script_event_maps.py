import ctypes as C
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import test_aux_map_profiles as map_tests
from test_aux_map_profiles import evaluate, retained
from test_script_event_service import Host
from civ6_host.runtime import script_map_argument_source as source
from civ6_host.runtime.configuration_profiles import _body
from civ6_host.runtime.script_event_service import ScriptEventService
from civ6_host.runtime.script_event_maps import ParameterMapArgument, pack_maps, require_map_transport
from civ6_host.runtime.native import native_aux_map_conversion as m
from civ6_host.runtime.aux_map_profiles import profile_for_sha
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256


def map_value(pointer):
    value=bytearray(24);struct.pack_into('<H',value,0,10)
    struct.pack_into('<QII',value,8,pointer,0,0x05000000)
    return value


def add_map(memory,pointer,fields,resolver=0):
    profile=profile_for_sha(XP1_CORE_SHA256)
    header=bytearray(84);struct.pack_into('<Q',header,0,memory.base+profile.vtable_rva)
    struct.pack_into('<Q',header,32,resolver)
    fields=sorted(fields.items());first=pointer+0x100 if fields else pointer+48
    struct.pack_into('<QQ',header,56,first,first if fields else 0)
    struct.pack_into('<I',header,80,len(fields));memory.parts[pointer]=header
    for i,(key,value) in enumerate(fields):
        address=pointer+0x100+i*0x100;node=bytearray(64)
        struct.pack_into('<QQQ',node,0,address+0x100 if i+1<len(fields) else 0,0,
                         pointer+48 if i==0 else address-0x100)
        struct.pack_into('<I',node,32,key);node[40:64]=value;memory.parts[address]=node


class ScriptMapTests(unittest.TestCase):
    def test_scalar_evidence_keeps_single_pass_iterables(self):
        from civ6_host.runtime.native.native_script_arguments import argument_evidence
        self.assertEqual(argument_evidence(iter((7,0xffffffff))),
            {'arguments_typed':[{'type':'uint32','raw':7},{'type':'uint32','raw':0xffffffff}],
             'arguments_uint32':[7,0xffffffff]})

    def snapshot(self,memory,*,names=False,**extra):
        return m.snapshot_parameter_map(memory.base,memory.map,memory.read,use_string_keys=names,
            core_sha256=XP1_CORE_SHA256,transport_version=2,allow_nested_maps=True,**extra)

    def memory(self):
        memory=map_tests.MapProfileTests().xp1({1:map_value(0xA0000),2:map_value(0)})
        add_map(memory,0xA0000,{7:retained.scalar(2,0xffffffff)})
        return memory

    def test_nested_maps_and_null_direct_value_preserve_table_stack(self):
        memory=self.memory()
        self.assertEqual(evaluate(self.snapshot(memory).transport),{1:{7:-1}})
        with self.assertRaisesRegex(ValueError,'Unverified.*variant'):
            m.snapshot_parameter_map(memory.base,memory.map,memory.read,use_string_keys=False,
                core_sha256=XP1_CORE_SHA256,transport_version=2)

    def test_cycles_and_copy_extents_refuse_before_native_allocation(self):
        memory=self.memory();add_map(memory,0xA0000,{7:map_value(memory.map)})
        with self.assertRaisesRegex(ValueError,'cycle'):self.snapshot(memory)
        memory=map_tests.MapProfileTests().xp1({1:retained.array(5,0xA0000,b'x\0',2,stored_size=0xffffffff)})
        memory.parts[0xA0000]=b'x\0'
        self.assertEqual(evaluate(self.snapshot(memory).transport),{1:b'x'})
        with self.assertRaisesRegex(ValueError,'allocation budget'):
            self.snapshot(memory,native_copy_budget=True)

    def test_each_map_uses_its_live_resolver(self):
        memory=map_tests.MapProfileTests().xp1({1:map_value(0xA0000)})
        profile=profile_for_sha(XP1_CORE_SHA256)
        memory.parts[memory.base+profile.vtable_rva+24]=struct.pack('<Q',memory.base+profile.name_getter_rva)
        memory.parts[memory.base+profile.name_getter_rva]=bytes.fromhex('488b4120c3')
        struct.pack_into('<Q',memory.parts[memory.map],32,0xB0000)
        add_map(memory,0xA0000,{1:retained.scalar(2,7)},resolver=0xC0000)
        def resolver(pointer,name):
            memory.parts[pointer+32]=struct.pack('<Q',pointer+0x100)
            memory.parts[pointer+80]=struct.pack('<Q',pointer+0x200)
            member=bytearray(36);struct.pack_into('<I',member,32,1);memory.parts[pointer+0x100]=member
            named=bytearray(48);struct.pack_into('<I',named,32,1)
            struct.pack_into('<Q',named,40,pointer+0x300);memory.parts[pointer+0x200]=named
            memory.parts[pointer+0x300]=name+b'\0'
        resolver(0xB0000,b'outer');resolver(0xC0000,b'inner')
        self.assertEqual(evaluate(self.snapshot(memory,names=True).transport),{b'outer':{b'inner':7}})
        memory.parts[0xC0300]=b'later\0'
        self.assertEqual(evaluate(self.snapshot(memory,names=True).transport),{b'outer':{b'later':7}})

    def test_loaded_native_copy_code_and_slots_are_required(self):
        base=0x200000000;cells={};proof=source.source()
        for body in source.live_bodies(proof).values():
            for fragment in _body(body)['fragments']:
                for ins in fragment['instructions']:
                    raw=bytes.fromhex(ins['bytes']);cells[base+int(ins['va'],16)-0x180000000,len(raw)]=raw
        for offset,target in proof['contract']['xp1_native_owner']['required_slots'].items():
            cells[base+0x93F590+int(offset,16),8]=struct.pack('<Q',base+int(target,16))
        self.assertFalse(source.verify_xp1(base,lambda a,n:cells[a,n])['native_execution'])
        cells[base+0x93F590+0x1D0,8]=bytes(8)
        with self.assertRaisesRegex(ValueError,'slot'):source.verify_xp1(base,lambda a,n:cells[a,n])

    def test_packing_defers_snapshot_and_retains_transport_buffers(self):
        value=ParameterMapArgument.__new__(ParameterMapArgument)
        value.snapshot=Mock(return_value=SimpleNamespace(transport=self.snapshot(self.memory()).transport))
        args,maps,buffers=pack_maps((0xffffffff,value,True))
        value.snapshot.assert_called_once()
        self.assertEqual([(x.kind,x.value) for x in args],[(0,0xffffffff),(2,0),(1,1)])
        self.assertEqual(C.sizeof(maps[0]),16)
        self.assertEqual(evaluate(C.string_at(maps[0].ops,maps[0].count*16)),{1:{7:-1}})
        self.assertEqual(len(buffers),1)

    def test_payload_release_closes_owned_maps_and_unknown_version_refuses_install(self):
        host=Host();runtime=SimpleNamespace(registry=SimpleNamespace(_check=Mock()),host=SimpleNamespace(
            LAB_GameEventsMapArgumentVersion=Mock(return_value=9),LAB_AuxMapTransportVersion=Mock(return_value=2),
            LAB_GameEventsDispatchMapsResult=Mock()))
        value=ParameterMapArgument.__new__(ParameterMapArgument);value.close=Mock()
        factory=Mock(return_value=value)
        with self.assertRaisesRegex(ValueError,'version'):ScriptEventService(host,runtime,map_factory=factory)
        self.assertIsNone(getattr(host,'_script_event_owner',None))
        runtime.host.LAB_GameEventsMapArgumentVersion.return_value=1
        service=ScriptEventService(host,runtime,map_factory=factory);owner=C.addressof(host.aux_object)
        payload=service.script_arguments._create(owner)
        self.assertEqual(service.script_arguments._append_map(payload,payload,0x1000),0)
        with self.assertRaisesRegex(ValueError,'live payload'):service.close()
        service.script_arguments._release(owner,payload);value.close.assert_called_once()
        service.close()


if __name__=='__main__':unittest.main()

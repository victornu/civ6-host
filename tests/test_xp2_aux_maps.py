"""XP2 source/reader/adapter composition fixtures; no engine or HKS executes."""
import ctypes as C
from dataclasses import replace
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import aux_map_profiles as profiles
from civ6_host.runtime import xp2_aux_map_profile as xp2
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.script_event_maps import MapArgumentFactory, ParameterMapArgument, pack_maps
from civ6_host.runtime.native.native_aux_map_adapter import NativeAuxMapAdapter
from civ6_host.runtime.native import native_aux_map_conversion as decoder
from civ6_host.runtime.native import native_configuration_finalization as native_calls
from test_aux_map_profiles import retained,evaluate
from test_script_event_maps import map_value


def memory(fields):
    result=retained.Memory(fields)
    p=profiles.profile_for_sha(XP2_CORE_SHA256)
    struct.pack_into('<Q',result.parts[result.map],0,result.base+p.vtable_rva)
    for body in xp2.source()['bodies']:
        result.parts[result.base+body['rva']]=bytes.fromhex(body['raw_hex'])
    for slot,rva in (*p.slots,(0x18,p.name_getter_rva)):
        result.parts[result.base+p.vtable_rva+slot]=struct.pack('<Q',result.base+rva)
    return result


def add_map(mem,pointer,fields,resolver=0):
    other=memory(fields)
    # Relocate only fixture data, never the selected code or vtable addresses.
    header=bytearray(other.parts[other.map])
    struct.pack_into('<Q',header,32,resolver)
    first=pointer+0x100 if fields else pointer+48
    struct.pack_into('<QQ',header,56,first,first if fields else 0)
    mem.parts[pointer]=header
    for index,(key,variant) in enumerate(sorted(fields.items())):
        address=pointer+0x100+index*0x100
        node=bytearray(64)
        struct.pack_into('<QQQ',node,0,address+0x100 if index+1<len(fields) else 0,0,
                         pointer+48 if index==0 else address-0x100)
        struct.pack_into('<I',node,32,key);node[40:64]=variant;mem.parts[address]=node


def snapshot(mem,*,names=False,**kwargs):
    return decoder.snapshot_parameter_map(mem.base,mem.map,mem.read,use_string_keys=names,
        core_sha256=XP2_CORE_SHA256,transport_version=2,allow_nested_maps=True,**kwargs)


def add_names(mem, pointer, names):
    for root_offset, nodes_offset, with_names in ((32, 0x100, False), (80, 0x500, True)):
        first = pointer + nodes_offset
        mem.parts[pointer + root_offset] = struct.pack('<Q', first)
        for index, (key, name) in enumerate(sorted(names.items())):
            address = first + index * 64
            text = pointer + 0x900 + index * 64
            node = bytearray(48 if with_names else 36)
            if index + 1 < len(names):
                struct.pack_into('<Q', node, 0, address + 64)
            struct.pack_into('<I', node, 32, key)
            if with_names:
                struct.pack_into('<Q', node, 40, text)
                mem.parts[text] = name + b'\0'
            mem.parts[address] = node


class XP2MapTests(unittest.TestCase):
    def test_execute_script_shaped_event_preserves_named_nested_parameters(self):
        event = b'GameplaySetAmaniProperty\0'
        mem = memory({1: retained.array(5, 0xd0000, event, 1),
                      2: retained.scalar(2, 3), 3: map_value(0xa0000)})
        mem.parts[0xd0000] = event
        struct.pack_into('<Q', mem.parts[mem.map], 32, 0xb0000)
        add_map(mem, 0xa0000, {1: retained.scalar(2, 41), 2: retained.scalar(2, 7),
                              3: retained.scalar(2, 0xffffffff)}, resolver=0xc0000)
        add_names(mem, 0xb0000, {1: b'OnStart', 2: b'iGovernorOwnerID', 3: b'tAmani'})
        add_names(mem, 0xc0000, {1: b'iCityID', 2: b'iMinorID', 3: b'Status'})
        argument = ParameterMapArgument.__new__(ParameterMapArgument)
        argument.snapshot = lambda: snapshot(mem, names=True, native_copy_budget=True)

        args, maps, buffers = pack_maps((3, argument))

        self.assertEqual([(item.kind, item.value) for item in args], [(0, 3), (2, 0)])
        self.assertEqual(len(buffers), 1)
        self.assertEqual(evaluate(C.string_at(maps[0].ops, maps[0].count * 16)), {
            b'OnStart': event[:-1], b'iGovernorOwnerID': 3,
            b'tAmani': {b'iCityID': 41, b'iMinorID': 7, b'Status': -1},
        })

    def test_exact_profile_live_guards_and_source_dependencies(self):
        mem=memory({});p=profiles.profile_for_sha(XP2_CORE_SHA256)
        self.assertIs(p,xp2.profile())
        profiles.verify_live(p,mem.base,mem.read)
        self.assertIn(xp2.SOURCE[1],xp2.source_dependencies().values())
        with self.assertRaises(ValueError):profiles.verify_live(replace(p),mem.base,mem.read)
        for body in xp2.source()['bodies']:
            with self.subTest(body=body['name']):
                address=mem.base+body['rva'];old=mem.parts[address]
                mem.parts[address]=bytes([old[0]^1])+old[1:]
                with self.assertRaisesRegex(ValueError,'code differs'):profiles.verify_live(p,mem.base,mem.read)
                mem.parts[address]=old
        for slot,rva in (*p.slots,(0x18,p.name_getter_rva)):
            address=mem.base+p.vtable_rva+slot;old=mem.parts[address]
            mem.parts[address]=struct.pack('<Q',mem.base+rva+8)
            with self.assertRaisesRegex(ValueError,'dispatch differs'):profiles.verify_live(p,mem.base,mem.read)
            mem.parts[address]=old

    def test_balanced_tree_mixed_values_nested_maps_lists_and_utf16(self):
        text='é漢😀'.encode('utf-16-le')+b'\0\0'
        mem=memory({1:retained.scalar(2,0xffffffff),2:retained.variant_list(0xa0000),
                    3:map_value(0xb0000),4:map_value(0)})
        retained.store_list(mem,0xa0000,[retained.scalar(3,7),retained.array(6,0xc0000,text,1),map_value(0xd0000)])
        mem.parts[0xc0000]=text
        add_map(mem,0xb0000,{11:retained.scalar(4,2.5)})
        add_map(mem,0xd0000,{17:retained.array(5,0xe0000,b'abc\0',1)})
        mem.parts[0xe0000]=b'abc\0'
        # A three-level tree exercises both source-proven child directions.
        root=mem.parts[mem.map];struct.pack_into('<Q',root,64,0x60200)
        struct.pack_into('<QQQ',mem.parts[0x60200],0,0x60300,0x60100,mem.map+48)
        struct.pack_into('<QQQ',mem.parts[0x60100],0,0,0x60000,0x60200)
        struct.pack_into('<QQQ',mem.parts[0x60000],0,0,0,0x60100)
        struct.pack_into('<QQQ',mem.parts[0x60300],0,0,0,0x60200)
        self.assertEqual(evaluate(snapshot(mem).transport),
            {1:-1,2:{1:7,2:'é漢😀'.encode(),3:{17:b'abc'}},3:{11:2.5}})
        self.assertEqual(snapshot(mem).field_count,4)

    def test_nested_unsupported_and_unstable_data_refuse_without_fallback(self):
        mem=memory({1:retained.variant_list(0xa0000)})
        retained.store_list(mem,0xa0000,[map_value(mem.map)])
        with self.assertRaisesRegex(ValueError,'cycle'):snapshot(mem)
        retained.store_list(mem,0xa0000,[retained.scalar(0xffff,1)])
        with self.assertRaisesRegex(ValueError,'no result substituted'):snapshot(mem)
        retained.store_list(mem,0xa0000,[retained.scalar(2,1)])
        original=mem.read;counts={}
        def changing(address,size):
            raw=original(address,size);counts[address,size]=counts.get((address,size),0)+1
            return b'X'+raw[1:] if address==0xa0028 and counts[address,size]>1 else raw
        mem.read=changing
        with self.assertRaisesRegex(ValueError,'changed during snapshot'):snapshot(mem)

    def test_every_nested_map_uses_its_own_live_name_resolver(self):
        mem=memory({1:map_value(0xa0000)})
        struct.pack_into('<Q',mem.parts[mem.map],32,0xb0000)
        add_map(mem,0xa0000,{1:retained.scalar(2,7)},resolver=0xc0000)
        for pointer,name in ((0xb0000,b'outer'),(0xc0000,b'inner')):
            mem.parts[pointer+32]=struct.pack('<Q',pointer+0x100)
            mem.parts[pointer+80]=struct.pack('<Q',pointer+0x200)
            member=bytearray(36);struct.pack_into('<I',member,32,1);mem.parts[pointer+0x100]=member
            named=bytearray(48);struct.pack_into('<I',named,32,1)
            struct.pack_into('<Q',named,40,pointer+0x300);mem.parts[pointer+0x200]=named
            mem.parts[pointer+0x300]=name+b'\0'
        self.assertEqual(evaluate(snapshot(mem,names=True).transport),{b'outer':{b'inner':7}})

    def test_existing_adapter_negotiates_nested_transport_and_copies_owned_result_buffer(self):
        mem=memory({1:map_value(0xa0000)})
        add_map(mem,0xa0000,{5:retained.scalar(2,9)})
        child=object();state=0x70000;owner=0x80000
        runtime=NS(registry=NS(contexts={state:child},validate=Mock(return_value=state)))
        host=NS(LAB_AuxMapInstall=Mock(return_value=1),LAB_AuxMapTransportVersion=Mock(return_value=2))
        events=[]
        adapter=NativeAuxMapAdapter(host,runtime,NS(_handle=mem.base),owner,
            lambda stage,**data:events.append((stage,data)),read=mem.read,
            core_sha256=XP2_CORE_SHA256,allow_nested_maps=True)
        adapter.install()
        output=C.c_void_p();count=C.c_uint32()
        ok=adapter._snapshot_callback(owner,state,mem.map,0,C.pointer(output),C.pointer(count))
        self.assertEqual(ok,1)
        self.assertEqual(evaluate(C.string_at(output.value,count.value*16)),{1:{5:9}})
        old_pointer=output.value
        self.assertIsNotNone(adapter._buffer)
        self.assertEqual(adapter._snapshot_callback(owner,state+8,mem.map,0,C.pointer(output),C.pointer(count)),0)
        self.assertIsNone(output.value);self.assertEqual(count.value,0)
        self.assertTrue(any(name=='native_aux_map_snapshot_refused' and data['fallback_used'] is False for name,data in events))
        adapter.close()
        self.assertTrue(old_pointer);self.assertIsNone(adapter._buffer)
        self.assertEqual(host.LAB_AuxMapInstall.call_count,2)

    def test_nested_adapter_refuses_v1_and_invalid_option_before_registration(self):
        mem=memory({});host=NS(LAB_AuxMapInstall=Mock(return_value=1))
        with self.assertRaisesRegex(ValueError,'Boolean'):
            NativeAuxMapAdapter(host,object(),NS(_handle=mem.base),0x80000,Mock(),read=mem.read,
                core_sha256=XP2_CORE_SHA256,allow_nested_maps=1)
        adapter=NativeAuxMapAdapter(host,object(),NS(_handle=mem.base),0x80000,Mock(),read=mem.read,
            core_sha256=XP2_CORE_SHA256,allow_nested_maps=True)
        with self.assertRaisesRegex(ValueError,'requires native V2'):adapter.install()
        host.LAB_AuxMapInstall.assert_not_called()

    def test_factory_selects_xp2_source_and_refuses_changed_code_before_native_copy(self):
        mem=memory({1:retained.scalar(2,7)});core=NS(_handle=mem.base)
        factory=MapArgumentFactory(core,core_sha256=XP2_CORE_SHA256,read=mem.read)
        self.assertEqual(factory.proof['core_sha256'],XP2_CORE_SHA256)
        self.assertEqual(evaluate(factory.snapshot(mem.map,names=False).transport),{1:7})
        factory.close()
        with self.assertRaisesRegex(ValueError,'closed'):factory(mem.map)
        body=xp2.source()['bodies'][0];address=mem.base+body['rva']
        mem.parts[address]=b'\0'*body['bytes']
        with patch.object(native_calls,'_invoke',side_effect=AssertionError('Unexpected native call')):
            with self.assertRaisesRegex(ValueError,'code differs'):
                MapArgumentFactory(core,core_sha256=XP2_CORE_SHA256,read=mem.read)


if __name__=='__main__':unittest.main(verbosity=2)

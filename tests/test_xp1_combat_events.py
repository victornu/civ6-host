"""Composed saved owner and combat/experience producers; native calls are fixtures."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
import sys
from types import MethodType
import unittest

from test_xp1_placement_events import Fixture as PlacementFixture,LAB,NATIVE_CALLBACK
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import a0_combat_events as admission
from civ6_host.runtime import xp1_combat_profile as source
from civ6_host.runtime import combat_event_profile as profile
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE,XP1_CORE_SHA256 as XP1
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native import native_event_8256dbe1 as combat
from civ6_host.runtime.native import native_event_a479f83f as experience
from civ6_host.runtime.native import native_unit_promotion_query as promotion
from civ6_host.runtime.native.native_host import DiagnosticHost


class Fixture(PlacementFixture):
    def enable(self):
        super().enable()
        # The retained fixture builds DeferredService with __new__; install
        # precisely the two constructor-owned fields added for this family.
        self.deferred.combat_map_registry=self.deferred.combat_receiver=None
        self.deferred.cache_core_sha256=XP1
        sys.path.insert(0,str(LAB/'tools'))
        from extract_phase31_next_export import pefile
        pe=pefile.PE(source.verify_source()['image']['path'],fast_load=True)
        old=self.owner.read
        def read(address,size):
            rva=address-self.memory.base
            if 0<=rva and rva+size<=pe.OPTIONAL_HEADER.SizeOfImage:
                raw=pe.get_data(rva,size)
                if len(raw)==size:return raw
            return old(address,size)
        self.owner.read=read
        try:admission.enable(self.owner,self.backend)
        finally:self.owner.read=old;pe.close()

    def __init__(self):
        super().__init__()
        self.combat_calls=[];self.next_by_node={};self.maps=[];self.fail_at=None
        self.query_result=0;self.result_shape='typed';self.promotion_value=23
        self.service=0x79500000;self.result_variant=0x79500100;self.result_value=0x79500200
        self.pointer_cursor=0x7a000000
        self.memory.put(self.service,struct.pack('<QI',self.memory.base+0x8ab1e8,1))
        self.memory.put(self.memory.base+0x9f5948,struct.pack('<Q',0x79600000))
        self.arguments.reader=EventArgumentReader(self.backend.core,core_sha256=XP1,read=self.read)
        self.arguments.consumer=self.owner
        self.host._check=MethodType(DiagnosticHost._check,self.host)

    def factory(self,result,*args):
        def bind(target):
            if callable(target):return NATIVE_CALLBACK(result,*args)(target)
            rva=target-self.backend.core._handle
            if rva==0x83afa0:
                assert result is C.c_void_p and args==(C.c_void_p,)
                return lambda node:self.next_by_node[node]
            if rva==0x4c3ed0:
                assert result is C.c_uint8 and args==(C.c_void_p,C.c_int32)
                def predicate(receiver,owner):
                    assert receiver==self.token.publisher._facades.game_facade
                    self.combat_calls.append(('predicate',owner));return int(owner==63)
                return predicate
            names={0x844460:'map_ctor',0x844580:'map_dtor',0x84b5d0:'map_assign',
                   0x4bd300:'get_service',0x1843b0:'release_outer',0x4cc8e0:'query',
                   0x4cc910:'release_service',0x845540:'lookup'}
            if rva in names:
                return lambda receiver,*values:self.machine_call(names[rva],result,args,receiver,*values)
            return super(Fixture,self).factory(result,*args)(target)
        return bind

    def machine_call(self,name,result,argtypes,receiver,*values):
        self.combat_calls.append((name,receiver,*values))
        if name==self.fail_at:raise RuntimeError('fixture native '+name+' failure')
        if name=='map_ctor':
            assert result is C.c_void_p and argtypes==(C.c_void_p,) and not values
            C.memmove(receiver,bytes(88),88);C.memmove(receiver,struct.pack('<Q',self.memory.base+0x93f590),8)
            self.maps.append(receiver);return receiver
        if name=='map_assign':
            assert result is C.c_void_p and argtypes==(C.c_void_p,C.c_void_p)
            C.memmove(receiver,self.read(values[0],88),88);return receiver
        if name=='map_dtor':
            assert result is None and argtypes==(C.c_void_p,) and receiver in self.maps
            return None
        if name=='get_service':
            assert receiver==self.backend.context and result is C.c_void_p
            return self.service
        if name=='release_outer':assert receiver==self.backend.context and result is None;return None
        if name=='query':
            descriptor,command,args,flags,out=values
            assert receiver==self.service and result is C.c_uint8
            assert (command,flags)==(0xb4edd43f,1)
            assert self.read(descriptor,8)==struct.pack('<HHI',3,1,17)
            assert [struct.unpack_from('<I',r,4)[0] for r in self.deferred.pending][-1]==74
            assert args in self.maps and out in self.maps
            return self.query_result
        if name=='lookup':
            assert receiver in self.maps and values==(0x315247e7,)
            if self.result_shape=='absent':return 0
            tag=2 if self.result_shape=='typed' else 4
            self.memory.put(self.result_variant,struct.pack('<H6xQII',tag,self.result_value,0,0x20000001))
            self.memory.put(self.result_value,struct.pack('<I',self.promotion_value))
            return self.result_variant
        if name=='release_service':assert receiver==self.service and result is None;return None
        raise AssertionError(name)

    def add_map(self,fields):
        pointer=self.pointer_cursor;self.pointer_cursor+=0x2000
        header=bytearray(88);sentinel=pointer+0x30
        struct.pack_into('<Q',header,0,self.memory.base+0x93f590)
        struct.pack_into('<QQ',header,0x30,sentinel,pointer+0x100 if fields else sentinel)
        struct.pack_into('<I',header,0x50,len(fields));self.memory.put(pointer,header)
        for index,(key,value) in enumerate(fields.items()):
            node=pointer+0x100+index*0x40;raw=bytearray(64)
            struct.pack_into('<I',raw,0x20,key);raw[0x28:]=value;self.memory.put(node,raw)
            self.next_by_node[node]=node+0x40 if index+1<len(fields) else sentinel
        return pointer

    def combat_fields(self,*,missing=False,extra_child=False):
        p=source.verify_source();fields={int(row['key'],16):scalar(row['variant_tag'],0)
                                      for row in p['root_fields']}
        from civ6_host.runtime.native.native_combat_argument_snapshot import CHILD_KEYS
        descriptors=[]
        for index,key in enumerate(CHILD_KEYS):
            descriptor=struct.pack('<HHI',65535 if missing else (3,63,4,5)[index],1 if index<2 else 2,
                                   0xffffffff if missing else 17+index)
            descriptors.append(descriptor)
            values={k:scalar(2,0) for k in combat.CHILD_SCALAR_KEYS}
            values[0x57c6ed30]=self.make_blob(descriptor,1024)
            values[0x95f2cf6e]=self.make_blob(struct.pack('<ii',index,index+1),13)
            if extra_child and index==0:values[0x12345678]=scalar(2,0)
            pointer=self.add_map(values)
            fields[key]=struct.pack('<H6xQII',10,pointer,0,0x05000000)
        return fields,tuple(descriptors)

    def dispatch(self,kind,fields):
        pointer=self.add_map(fields)
        result=self.arguments.dispatch(self.host.pointer,kind,pointer)
        return result,pointer

    def experience_fields(self):
        return {experience.SELECTOR_KEY:scalar(3,0),
                experience.DESCRIPTOR_KEY:self.make_blob(struct.pack('<HHI',3,1,17),1024)}


class CombatEventTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_source_dependencies_and_selected_methods_are_exact(self):
        pins=profile.source_dependencies()
        for path,digest in pins.items():
            with Path(path).open('rb') as stream:self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),digest,path)
        self.assertEqual({0x8256dbe1,0xa479f83f,0x45b517d6},set(profile.event_profile().record_types_by_kind))
        layout=source.promotion_layout(XP1,promotion.METHODS,promotion.SLOTS)
        self.assertEqual(layout.methods['query'][0],0x4cc8e0)
        self.assertIs(source.promotion_layout(BASE,promotion.METHODS,promotion.SLOTS).methods,promotion.METHODS)
        with self.assertRaises(ValueError):source.ensure_source('unknown')

    def test_real_composed_reader_copy_predicate_fifo_and_destructor(self):
        f=self.fixture();fields,descriptors=f.combat_fields()
        self.assertEqual(f.dispatch(0x8256dbe1,fields)[0],0)
        row=f.deferred.pending[0];self.assertEqual(struct.unpack_from('<IIII',row),(128,248,1,0))
        self.assertEqual(row[88:120],b''.join(descriptors));self.assertEqual(struct.unpack_from('<I',row,72)[0],0x12)
        registry=f.owner.combat_map_registry;owned=registry.lookup(1)
        self.assertIs(owned.core,f.backend.core);self.assertEqual(owned.core_sha256,XP1)
        self.assertEqual([r[0] for r in f.combat_calls],['map_ctor','map_assign','predicate','predicate'])
        self.assertEqual([r[1] for r in f.combat_calls if r[0]=='predicate'],[3,63])
        self.assertFalse(owned.closed);self.assertEqual(f.deferred.drain(),1)
        self.assertTrue(owned.closed);self.assertEqual(registry.entries,{})
        self.assertEqual(f.combat_calls[-1][0],'map_dtor');self.assertIsNone(f.owner._foundation_borrow)

    def test_missing_descriptors_skip_native_predicate_and_metadata_scopes_remain_explicit(self):
        f=self.fixture();fields,_=f.combat_fields(missing=True)
        f.deferred.host_metadata_counter=2
        self.assertEqual(f.dispatch(0x8256dbe1,fields)[0],0)
        self.assertFalse(any(r[0]=='predicate' for r in f.combat_calls))
        f.deferred.host_metadata_counter=0;self.assertEqual(f.deferred.drain(),1)
        f=self.fixture();fields,_=f.combat_fields();f.deferred.host_notification_counter=1
        with self.assertRaisesRegex(ValueError,'metadata scope'):f.dispatch(0x8256dbe1,fields)
        self.assertEqual(f.combat_calls,[]);self.assertEqual(f.deferred.pending,[])

    def test_unqualified_child_or_native_failure_retains_uncertain_ownership(self):
        f=self.fixture();fields,_=f.combat_fields(extra_child=True)
        with self.assertRaisesRegex(ValueError,'fourteen-field'):f.dispatch(0x8256dbe1,fields)
        self.assertTrue(f.owner._combat_producer_poisoned);self.assertTrue(f.owner.quarantined)
        self.assertEqual(f.deferred.pending,[]);self.assertEqual(len(f.owner.combat_map_registry.entries),1)
        self.assertNotIn('map_dtor',[r[0] for r in f.combat_calls])
        f=self.fixture();fields,_=f.combat_fields();f.fail_at='map_assign'
        with self.assertRaisesRegex(RuntimeError,'map_assign failure') as error:f.dispatch(0x8256dbe1,fields)
        self.assertTrue(error.exception.native_combat_map_owner.poisoned)
        self.assertEqual(f.deferred.pending,[]);self.assertNotIn('map_dtor',[r[0] for r in f.combat_calls])

    def test_experience_query_order_and_conditional_promotion_typed_and_absent_results(self):
        for result,shape,value,types in ((0,'typed',None,[74]),(1,'typed',23,[74,79]),
                                        (1,'absent',0xffffffff,[74,79]),(1,'wrong_type',0xffffffff,[74,79])):
            with self.subTest(result=result,shape=shape):
                f=self.fixture();f.query_result=result;f.result_shape=shape
                self.assertEqual(f.dispatch(0xa479f83f,f.experience_fields())[0],0)
                self.assertEqual([struct.unpack_from('<I',r,4)[0] for r in f.deferred.pending],types)
                if value is not None:self.assertEqual(struct.unpack_from('<I',f.deferred.pending[-1],96)[0],value)
                calls=[r[0] for r in f.combat_calls]
                self.assertEqual(calls[:5],['get_service','release_outer','map_ctor','map_ctor','query'])
                self.assertEqual(calls[-3:],['map_dtor','map_dtor','release_service'])
                receipts=[v for k,v in f.emitted if k=='native_experience_callback_completed']
                self.assertEqual(receipts[-1]['source_proof_sha256'],source.SOURCE[1])
                self.assertEqual(f.deferred.drain(),len(types))

    def test_promotion_failure_does_not_undo_experience_or_guess_destruction(self):
        f=self.fixture();f.fail_at='query'
        with self.assertRaisesRegex(RuntimeError,'query failure') as error:f.dispatch(0xa479f83f,f.experience_fields())
        self.assertEqual(len(error.exception.native_promotion_storage),3)
        self.assertEqual([struct.unpack_from('<I',r,4)[0] for r in f.deferred.pending],[74])
        self.assertTrue(f.owner._experience_producer_poisoned)
        self.assertNotIn('map_dtor',[r[0] for r in f.combat_calls])
        self.assertFalse(any(k=='native_experience_callback_completed' for k,_ in f.emitted))


if __name__=='__main__':unittest.main()

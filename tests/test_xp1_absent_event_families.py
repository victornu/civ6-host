"""Real saved owner, argument-tree reader, absent normalizers and deferred FIFO."""
import ast
import ctypes as C
import hashlib
from pathlib import Path
import struct
import threading
from types import MethodType
import unittest

from test_xp1_placement_events import Fixture as PlacementFixture,LAB
from test_goody_hut_reward import scalar
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime import xp1_absent_event_families as profile
from civ6_host.runtime.native import native_absent_d70ba51f as two
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256

UNIT=0xf0548bb7;B4=0xb4f9542d;SELECTOR=0xa1e5a149;VALUE=0xd6fcf3e4


class Fixture(PlacementFixture):
    def set_active(self,value):
        # Supply the real owner identity once when this historical fixture
        # first creates SavedLoadOwner via __new__; later swaps still refuse.
        if not hasattr(self.saved,'_engine_sha256'):
            self.saved._engine_sha256=XP1_CORE_SHA256
            self.backend._saved_stage_owner=self.saved
        return super().set_active(value)

    def __init__(self):
        self.nodes={};self.all_reads=[];self.native_feedback=[]
        super().__init__()
        self.host._check=MethodType(DiagnosticHost._check,self.host)
        self.arguments.reader=EventArgumentReader(self.backend.core,core_sha256=XP1_CORE_SHA256,read=self.native_read)
        self.deferred.cache_core_sha256=XP1_CORE_SHA256
        self.deferred.read=self.native_read;self.deferred.cache_update_callback_pair=None

    def native_read(self,address,size):
        self.all_reads.append((address,size));return self.read(address,size)

    def factory(self,result,*args):
        inherited=super().factory(result,*args)
        def bind(target):
            if not callable(target) and target==self.memory.base+0x83afa0:
                return lambda node:self.nodes[node]
            if not callable(target) and target==self.memory.base+0x4be750:
                def dispatch(context,values):
                    self.saved._check_active()
                    assert context==self.backend.context
                    self.native_feedback.append(tuple(int(values[i]) for i in range(4)))
                return dispatch
            return inherited(target)
        return bind

    def tree(self,fields):
        pointer=0x7a100000;first=pointer+0x1000
        header=bytearray(88)
        struct.pack_into('<Q',header,0,self.memory.base+0x93f590)
        struct.pack_into('<Q',header,56,first);struct.pack_into('<I',header,80,len(fields))
        self.memory.put(pointer,header)
        for index,(key,value) in enumerate(sorted(fields.items())):
            node=first+index*0x100;raw=bytearray(64)
            struct.pack_into('<I',raw,32,key);raw[40:64]=value
            self.memory.put(node,raw);self.nodes[node]=node+0x100 if index+1<len(fields) else pointer+48
        return pointer

    def fields(self,descriptor=UNIT,tag=2,*,two_fields=False,pointer=0x7a200000):
        result={SELECTOR:scalar(3,0),descriptor:struct.pack('<HHIQII',0x400,0,1,pointer,8,0x21000001)}
        if not two_fields:result[VALUE]=scalar(tag,0xffc00001 if tag==4 else 0xffffffff)
        if descriptor==UNIT:self.memory.put(pointer,struct.pack('<HHI',0xffff,99,0xfffffffe))
        return result

    def dispatch(self,kind,fields):
        return self.arguments.dispatch(self.host.pointer,kind,self.tree(fields))

    def registry(self,kind):
        buckets,node,vector=0x7a300000,0x7a301000,0x7a302000
        self.memory.put(self.memory.base+0x9cddb0,struct.pack('<QII',buckets,1,1))
        self.memory.put(buckets,struct.pack('<QQ',node,0))
        raw=bytearray(48);struct.pack_into('<I',raw,0,kind)
        struct.pack_into('<QQQ',raw,8,vector,vector+32,vector+32)
        self.memory.put(node,raw)
        # The real shared dispatcher checks a nonempty native subscriber vector;
        # only its final machine invocation is a fixture, never a fake empty list.
        self.memory.put(vector,struct.pack('<4Q',0,0,0x7a303000,self.memory.base+0x70b10))


class AbsentEventTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_b4_preserves_preceding_b0_record_and_native_feedback(self):
        f=self.fixture();kind=0xc52231ab;f.registry(kind)
        f.deferred.host_notification_counter=2;f.deferred.host_metadata_counter=3
        self.assertEqual(f.deferred.cache_update(f.host.pointer,kind,(23<<32)|0x15d11e18),0)
        before=list(f.deferred.pending);self.assertEqual(len(before),1)
        for tag,event in ((2,kind),(4,0x3d75b3ed)):
            fields=f.fields(B4,tag,pointer=0xdeadbeef)
            self.assertEqual(f.dispatch(event,fields),0)
            self.assertEqual(f.deferred.pending,before);self.assertEqual(f.deferred._sequence,1)
            self.assertFalse(any(address==0xdeadbeef for address,_ in f.all_reads))
        self.assertEqual(f.arguments.count,2)
        self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(2,3))
        receipts=[r for stage,r in f.emitted if stage=='native_shared_absent_descriptor_event']
        self.assertEqual([r['normalized_fields']['scalar_tag'] for r in receipts],[2,4])
        self.assertEqual([r['normalized_fields']['scalar_bits'] for r in receipts],[0xffffffff,0xffc00001])
        self.assertTrue(all(not r['normalized_fields']['descriptor_target_read'] for r in receipts))
        self.assertEqual(f.deferred.drain(),1);self.assertEqual(f.deferred.drain(),0)
        self.assertEqual(f.native_feedback,[(kind,0,0x15d11e18,23)])
        self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.deferred.consumed_count,1)

    def test_unit_two_and_three_fields_copy_once_without_fifo_mutation(self):
        f=self.fixture();cases=((True,2,0x7b4264e9),(False,2,0xc52231ab),(False,4,0x3d75b3ed))
        for index,(two_fields,tag,kind) in enumerate(cases):
            pointer=0x7a200000+index*0x100;fields=f.fields(UNIT,tag,two_fields=two_fields,pointer=pointer)
            before=len(f.all_reads);self.assertEqual(f.dispatch(kind,fields),0)
            self.assertEqual([r for r in f.all_reads[before:] if r[0]==pointer],[(pointer,8)])
            f.memory.blocks.pop(pointer)
            receipt=next(r for stage,r in reversed(f.emitted) if stage=='native_shared_absent_descriptor_event')
            normalized=receipt['normalized_fields']
            self.assertEqual(normalized['kind'],kind)
            self.assertEqual(normalized['normalized_descriptor_hex'],struct.pack('<HHI',0xffff,1,0xfffffffe).hex())
            self.assertEqual(normalized['queue_records_produced'],0)
            self.assertFalse(normalized['gameplay_success_asserted'])
            self.assertEqual(set(fields),{SELECTOR,UNIT} if two_fields else {SELECTOR,UNIT,VALUE})
        self.assertEqual(f.arguments.count,3);self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.deferred._sequence,0);self.assertEqual(f.deferred.drain(),0)
        self.assertEqual(f.native_feedback,[]);self.assertEqual(f.calls,[])

    def test_closed_registry_profile_and_bad_borrows_refuse(self):
        profile.verify_source()
        messages={'registered':'absent from the captured registry','unknown_shape':'scalar descriptor keys',
            'bad_flags':'native blob representation','short_read':'Incomplete native blob copy',
            'listeners':'profile changed','transform':'profile changed','registrations':'profile changed',
            'foreign_reader':'foreign owner or source reader'}
        for case in ('registered','unknown_shape','bad_flags','short_read','listeners','transform','registrations','foreign_reader'):
            with self.subTest(case=case):
                f=self.fixture();fields=f.fields();kind=0xc52231ab
                if case=='registered':
                    kind=0x45b517d6
                    self.assertFalse(f.owner.handles_kind(kind))
                if case=='unknown_shape':fields[0x12345678]=scalar(2,0)
                if case=='bad_flags':fields[UNIT]=struct.pack('<HHIQII',0x400,0,1,0x7a200000,8,0)
                if case=='short_read':
                    read=f.arguments.reader.read
                    f.arguments.reader.read=lambda p,n,old=read:bytes(7) if p==0x7a200000 else old(p,n)
                if case=='listeners':f.owner.entity_listener_count=1
                if case=='transform':f.owner.normalizer_transform_present=True
                if case=='registrations':f.owner.dynamic_event_registration_present=True
                if case=='foreign_reader':f.arguments.reader.core=object()
                with self.assertRaisesRegex((ValueError,RuntimeError),messages[case]):f.dispatch(kind,fields)
                self.assertEqual(f.arguments.count,0);self.assertTrue(f.arguments.quarantined)
                self.assertEqual(f.arguments.depth,0);self.assertEqual(f.deferred.pending,[])
                self.assertEqual(f.deferred._sequence,0);self.assertEqual(f.native_feedback,[])

    def test_every_registered_kind_excluded_by_each_shared_absent_validator(self):
        from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
        f=self.fixture();options=dict(normalizer_transform_present=f.owner.normalizer_transform_present,
            registry_profile=f.owner.callback_registry_profile,
            dynamic_registration_present=f.owner.dynamic_event_registration_present,
            entity_listener_count=f.owner.entity_listener_count)
        unit_fields=f.fields();two_fields=f.fields(two_fields=True);b4_fields=f.fields(B4)
        self.assertEqual(len(EXE_EVENT_CALLBACKS),317)
        before=len(f.all_reads)
        for kind in EXE_EVENT_CALLBACKS:
            with self.subTest(kind=hex(kind)):
                with self.assertRaises(ValueError):profile.unit.validate_absent_event(kind,unit_fields,f.native_read,**options)
                with self.assertRaises(ValueError):profile.b4.validate_absent_event(kind,b4_fields,**options)
                with self.assertRaises(ValueError):two._validate_profile_event(kind,two_fields,f.native_read,**options)
        self.assertEqual(len(f.all_reads),before);self.assertEqual(f.deferred.pending,[])

    def test_source_dependency_files_match_exact_pins(self):
        dependencies=profile.source_dependencies()
        for relative,digest in (profile.SOURCE,profile.TWO_SOURCE):
            self.assertEqual(dependencies[str((LAB/relative).resolve())],digest)
        self.assertGreaterEqual(len(dependencies),12)
        for name,expected in dependencies.items():
            with self.subTest(path=name):
                with Path(name).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
                self.assertEqual(actual,expected)

    def test_original_domain_and_shared_body_preserved_live_source_guarded(self):
        from civ6_host.runtime.provenance import historical_source_file
        old=ast.parse(Path(historical_source_file('civ6rl/native_absent_d70ba51f.py')).read_text(encoding='utf8'))
        current=ast.parse(Path(two.__file__).read_text(encoding='utf8'))
        original=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='validate_absent_event')
        shared=next(n for n in current.body if isinstance(n,ast.FunctionDef) and n.name=='_validate_profile_event')
        self.assertEqual([ast.dump(n) for n in original.body[3:]],[ast.dump(n) for n in shared.body[3:]])
        f=self.fixture();fields=f.fields(two_fields=True)
        options=dict(normalizer_transform_present=False,registry_profile=two.REGISTRY_PROFILE,
                     dynamic_registration_present=False,entity_listener_count=0)
        with self.assertRaisesRegex(ValueError,'D70BA51F'):two.validate_absent_event(0x7b4264e9,fields,f.native_read,**options)
        self.assertEqual(two.validate_absent_event(two.EVENT_KIND,fields,f.native_read,**options)['kind'],two.EVENT_KIND)
        # Corrupt only captured native bytes before the new profile is bound.
        source=profile.verify_source();ref=source['references']['builder']
        from civ6_host.runtime.configuration_profiles import _source
        row=profile._rows(_source((ref['path'],ref['sha256'])))[0]
        raw=bytes.fromhex(row['bytes']);address=f.memory.base+int(row['va'],16)-0x180000000
        f.memory.put(address,bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(ValueError,'live instructions'):f.dispatch(0xc52231ab,f.fields(B4))
        self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.arguments.count,0)


if __name__=='__main__':unittest.main()

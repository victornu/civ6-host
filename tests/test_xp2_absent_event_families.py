"""Actual XP2 argument reader, owners, unchanged EXE codecs and deferred FIFO."""
import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import test_xp2_preload_services as preload
from test_a0_family_service import PROFILE,scalar
from civ6_host.runtime import xp1_absent_event_families as profile
from civ6_host.runtime import xp2_absent_event_source as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,_copy
from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload

UNIT=0xf0548bb7;B4=0xb4f9542d;SELECTOR=0xa1e5a149;VALUE=0xd6fcf3e4


class XP2AbsentEvents(unittest.TestCase):
    def graph(self):
        f=preload.XP2PreloadServices();self.addCleanup(f.doCleanups)
        h,d,ctl,a=f.compose()
        p=source.source()
        for b in p['functions'].values():
            for part in b['fragments']:f.put(f.base+int(part['start_rva'],16),bytes.fromhex(part['raw_hex']))
        for slot,target in p['parameter_vtable']['slots'].items():
            f.put(f.base+p['parameter_vtable']['rva']+int(slot),struct.pack('<Q',f.base+target))
        owner=a.install_consumers(receiver_state=dict(PROFILE),pre_turn_immediate_state=dict(PROFILE),entity_listener_count=0)
        f.host,f.deferred,f.arguments,f.owner,f.control=h,d,a,owner,ctl
        f.events=[];a.emit=lambda stage,**kw:f.events.append((stage,kw))
        original=f.read;f.reads=[]
        def read(address,size):f.reads.append((address,size));return original(address,size)
        a.reader.read=read;owner.read=read;d.read=read
        f.source_read=original
        return f

    def fields(self,f,descriptor=UNIT,tag=2,*,two=False,pointer=0x9000):
        values={SELECTOR:scalar(3,0),descriptor:struct.pack('<HHIQII',1024,0,1,pointer,8,0x21000001)}
        if not two:values[VALUE]=scalar(tag,0xffc00001 if tag==4 else 0xffffffff)
        if descriptor==UNIT:f.put(pointer,struct.pack('<HHI',0xffff,99,0xfffffffe))
        return values

    def send(self,f,kind,values):
        pointer,f.arguments.reader.next_node=f.tree(values)
        return f.arguments.dispatch(f.host.pointer,kind,pointer)

    def test_real_map_normalizes_two_three_fields_without_queries_or_fifo_mutation(self):
        f=self.graph()
        for i,(two,tag,kind) in enumerate(((True,2,0x7b4264e9),(False,2,0xc52231ab),(False,4,0x3d75b3ed))):
            pointer=0x9000+i*0x100;values=self.fields(f,two=two,tag=tag,pointer=pointer)
            before=len(f.reads)
            self.assertEqual(self.send(f,kind,values),0)
            self.assertEqual([r for r in f.reads[before:] if r[0]==pointer],[(pointer,8)])
            receipt=f.events[-1][1];result=receipt['normalized_fields']
            self.assertEqual(receipt['core_sha256'],XP2_CORE_SHA256)
            self.assertEqual(receipt['source_sha256'],source.SOURCE[1]);self.assertNotIn('xp1_source_sha256',receipt)
            self.assertEqual(result['normalized_descriptor_hex'],struct.pack('<HHI',0xffff,1,0xfffffffe).hex())
            self.assertFalse(result['gameplay_success_asserted']);self.assertEqual(result['queue_records_produced'],0)
        self.assertEqual((f.arguments.count,f.deferred._sequence,len(f.deferred.pending)),(3,0,0))
        f.arguments.close();f.control.close();f.deferred.close()

    def test_b4_does_not_read_pointee_and_retains_real_preceding_b0_feedback(self):
        f=self.graph();d=f.deferred;kind=0xc52231ab
        f.put(0x3100,struct.pack('<I',kind))
        d.host_notification_counter=2;d.host_metadata_counter=3
        self.assertEqual(d.cache_update(f.host.pointer,kind,(23<<32)|0x15d11e18),0)
        before=tuple(d.pending)
        for tag in (2,4):
            self.assertEqual(self.send(f,kind,self.fields(f,B4,tag,pointer=0xdeadbeef)),0)
            self.assertEqual(tuple(d.pending),before)
        self.assertFalse(any(a==0xdeadbeef for a,_ in f.reads))
        self.assertEqual((d._sequence,d.host_notification_counter,d.host_metadata_counter),(1,2,3))
        seen=[]
        def invoke(target,receiver,args):
            self.assertEqual((target,receiver),(f.base+0x591920,f.context));seen.append(tuple(args))
        def dispatch(*args,**kwargs):return dispatch_cache_update_payload(*args,**kwargs,invoke=invoke)
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',side_effect=dispatch):
            self.assertEqual(d.drain(),1);self.assertEqual(d.drain(),0)
        self.assertEqual(seen,[(kind,0,0x15d11e18,23)]);self.assertEqual(d.consumed_count,1)
        self.assertEqual([r['normalized_fields']['scalar_bits'] for _,r in f.events],[0xffffffff,0xffc00001])

    def test_wrong_source_owner_or_actual_listener_state_refuses(self):
        for case in ('engine','core','read_identity','code','slot','listeners','transform','registration','selector','flags'):
            with self.subTest(case=case):
                f=self.graph();values=self.fields(f,two=case=='selector')
                if case=='engine':f.deferred.cache_core_sha256=XP1_CORE_SHA256
                if case=='core':f.arguments.reader.core=object()
                if case=='read_identity':
                    self.send(f,0xc52231ab,values)
                    old=f.arguments.reader.read;f.arguments.reader.read=lambda a,n:old(a,n)
                if case=='code':f.put(f.base+0x5fb9b5,b'\0') # guarded refusal after the first RET
                if case=='slot':f.put(f.base+0xabf080+0xb0,b'\0'*8)
                if case=='listeners':f.owner.entity_listener_count=1
                if case=='transform':f.owner.normalizer_transform_present=True
                if case=='registration':f.owner.dynamic_event_registration_present=True
                if case=='selector':values[SELECTOR]=scalar(3,1)
                if case=='flags':values[UNIT]=struct.pack('<HHIQII',1024,0,1,0x9000,8,0)
                with self.assertRaises((ValueError,RuntimeError)):self.send(f,0xc52231ab,values)
                self.assertTrue(f.arguments.quarantined);self.assertEqual(f.arguments.depth,0)
                self.assertEqual(f.deferred.pending,[])

    def test_every_registered_kind_is_still_excluded_and_no_field_is_synthesized(self):
        from civ6_host.runtime.native.native_host_event_registry import EXE_EVENT_CALLBACKS
        f=self.graph();options=dict(normalizer_transform_present=False,registry_profile=f.owner.callback_registry_profile,
                                   dynamic_registration_present=False,entity_listener_count=0)
        fields=self.fields(f);fields2=self.fields(f,two=True);fieldsb=self.fields(f,B4)
        before=len(f.reads)
        for kind in EXE_EVENT_CALLBACKS:
            with self.assertRaises(ValueError):profile.unit.validate_absent_event(kind,fields,f.arguments.reader.read,**options)
            with self.assertRaises(ValueError):profile.unit_two._validate_profile_event(kind,fields2,f.arguments.reader.read,**options)
            with self.assertRaises(ValueError):profile.b4.validate_absent_event(kind,fieldsb,**options)
        self.assertEqual(len(f.reads),before)
        fields[0x12345678]=scalar(2,0)
        with self.assertRaises(ValueError):self.send(f,0xc52231ab,fields)
        self.assertEqual(f.deferred.pending,[])

    def test_complete_sources_engine_selection_and_exact_pins(self):
        p=profile.verify_source(core_sha256=XP2_CORE_SHA256)
        self.assertEqual((len(p['functions']),p['validation']['total_bytes']),(38,12095))
        self.assertEqual(profile.verify_source()['images']['xp1']['sha256'],XP1_CORE_SHA256)
        with self.assertRaises(ValueError):profile.source_dependencies(core_sha256='foreign')
        pins=profile.source_dependencies(core_sha256=XP2_CORE_SHA256)
        self.assertIn(source.SOURCE[1],pins.values())
        for path,digest in pins.items():
            with Path(path).open('rb') as stream:self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),digest)
        changed=_copy(p);changed['functions']['0x5fb890']['fragments'][-1]['raw_hex']='00'
        with patch.object(source,'_source',return_value=changed),self.assertRaises(ValueError):source.source()


if __name__=='__main__':unittest.main()

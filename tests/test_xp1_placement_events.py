"""Placement dependencies on the real saved owner and A0/FIFO; no DLL runs."""
import ctypes as C
import struct
import sys
from types import MethodType
import unittest

from test_xp1_session_checkpoint_owner import Fixture as CheckpointFixture, ABI, LAB, NATIVE_CALLBACK
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import a0_foundation_events as admission
from civ6_host.runtime import placement_event_profile as profile
from civ6_host.runtime import xp1_production_placement_profile as source
from civ6_host.runtime.foundation_facade_profiles import query_abi
from civ6_host.runtime.native import native_event_6d7163b0 as event
from civ6_host.runtime.native import native_event_6d7163b0_selector as selector
from civ6_host.runtime.native.native_host import DiagnosticHost, ArchiveRegistry
from civ6_host.runtime.script_event_service import ScriptEventService
from civ6_host.runtime import script_event_source


class Fixture(CheckpointFixture):
    def enable(self):
        super().enable()
        # The enclosing saved-owner fixture installs its disk reader later.
        # Retain the actual profile binder here, with exact image bytes only.
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
        try:admission.enable_placements(self.owner,self.backend)
        finally:self.owner.read=old;pe.close()

    def __init__(self):
        super().__init__()
        self.abi=query_abi(profile.XP1_CORE_SHA256,LAB)
        self.calls=[];self.live={};self.snapshot_count=0;self.fail_snapshot=0
        names=set(profile.TABLE_NAMES.values())|{'type_service'}
        self.objects={name:0x76000000+i*0x100 for i,name in enumerate(sorted(names))}
        self.objects['outer']=self.backend.context
        for name,address in self.objects.items():
            # The XP1 type-service is exactly 8 bytes (no Base +8 interface).
            raw=struct.pack('<Q',self.memory.base+self.abi.table(name))
            if name=='district':raw+=struct.pack('<Q',0x76100000)
            self.memory.put(address,raw)
        self.civilization=0x12345678
        self.host.configured_player_identity_hashes={0:self.civilization}
        self.civilization_cell=0x76200000
        self.memory.put(self.civilization_cell,struct.pack('<H6xQ4xI',3,self.civilization,0x05000000))
        self.regions.append((C.addressof(self.backend.owner.storage),C.addressof(self.backend.owner.storage)+C.sizeof(self.backend.owner.storage)))
        self.saved._running=True;self.set_active(True)

    def factory(self,result,*args):
        def bind(target):
            if callable(target):return NATIVE_CALLBACK(result,*args)(target)
            base=self.backend.core._handle
            if target==base+ABI.lookup_rva:return super(Fixture,self).factory(result,*args)(target)
            if target==base+0x845600:
                def get(pointer,key):
                    assert pointer in [struct.unpack_from('<Q',self.read(v,24),8)[0] for v in self.providers[self.backend.owner.pointer].values()]
                    assert key==3352777051
                    self.calls.append(('civilization',pointer));return self.civilization_cell
                return get
            names={**profile.OPERATION_NAMES,'outer_service':'outer_service','release_service':'release_service',
                   'player_type':'player_type','service_player_type_hash':'service_player_type_hash'}
            found=[name for name,native in names.items() if target==base+self.abi.rva(native)]
            if not found:raise AssertionError('Unselected native placement target '+hex(target-base))
            name=found[0]
            return lambda *values:self.native(name,*values)
        return bind

    def acquire(self,name):
        self.live[name]=self.live.get(name,0)+1;return self.objects[name]

    def native(self,name,pointer,*args):
        self.calls.append((name,pointer,*args));o=self.objects
        released={'release_player':'player','release_collection':'district_collection','release_item':'district',
                  'release_map':'map','release_plot':'plot','release_service':'type_service'}
        if name in released:
            label=released[name];assert pointer==o[label] and self.live[label]>0
            self.live[label]-=1;return None
        if name=='get_player':assert pointer==o['outer'] and args==(0,);return self.acquire('player')
        if name=='outer_service':assert pointer==o['outer'];return self.acquire('type_service')
        if name=='player_type':assert pointer==o['player'];return 4
        if name=='service_player_type_hash':assert pointer==o['type_service'] and args==(4,);return 0x1776
        if name=='player_collection':assert pointer==o['player'];return self.acquire('district_collection')
        if name=='collection_index':assert pointer==o['district_collection'] and args==(13,);return self.acquire('district')
        if name=='item_snapshot':
            assert pointer==o['district'] and args[1]==0
            self.snapshot_count+=1;out=args[0];raw=bytearray(64);raw[29]=self.snapshot_count
            struct.pack_into('<QI',raw,40,0x76300000+self.snapshot_count*0x100,2);struct.pack_into('<I',raw,56,1)
            C.memmove(out,bytes(raw),64)
            if self.fail_snapshot==self.snapshot_count:raise ValueError('fixture native snapshot failure')
            return 1
        if name=='item_variant':
            assert pointer==o['district'];C.memmove(args[0],struct.pack('<HHI',0,2,65536),8);return args[0]
        if name=='item_raw':assert pointer==o['district'];return 13
        if name=='free_vector':assert pointer in (0x76300100,0x76300200,0x76300300);return None
        if name=='outer_map':assert pointer==o['outer'];return self.acquire('map')
        if name=='map_plot':assert pointer==o['map'] and args==(3,4);return self.acquire('plot')
        if name=='plot_value':assert pointer==o['plot'];return 35
        raise AssertionError(name)

    def emit(self,stage,**details):
        if stage=='native_deferred_host_event_enqueued' and details.get('dispatch_kind')==hex(profile.EVENT_KIND):
            assert self.live['district']==1
            if details['queue_type']=='0x9d':assert self.live['plot']==1
            assert self.live.get('player',0)==self.live.get('district_collection',0)==self.live.get('map',0)==0
            self.calls.append(('enqueued',details['queue_type']))
        return super().emit(stage,**details)

    def fields(self,selected):
        return {event.POSITION_KEY:self.make_blob(struct.pack('<ii',3,4),0),
                event.DESCRIPTOR_KEY:self.make_blob(struct.pack('<HHI',0,3,13),1024),
                event.SELECTOR_KEY:scalar(3,selected),event.A1FBC_KEY:scalar(2,9),event.D6_KEY:scalar(2,0)}


class PlacementEventsTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_all_selector_plans_actual_owner_query_abi_independent_passes_and_fifo(self):
        for selected,types in ((1,[157]),(0xccb6d5be,[157,157]),(selector.AUX_SELECTOR,[157,163])):
            with self.subTest(selector=hex(selected)):
                f=self.fixture();self.assertEqual(f.owner.dispatch(profile.EVENT_KIND,f.fields(selected),0),0)
                self.assertEqual([struct.unpack_from('<I',x,4)[0] for x in f.deferred.pending],types)
                self.assertEqual(f.snapshot_count,len(types));self.assertTrue(all(v==0 for v in f.live.values()))
                self.assertEqual(sum(row[0]=='civilization' for row in f.calls),types.count(157))
                self.assertEqual(sum(row[0]=='free_vector' for row in f.calls),len(types))
                self.assertEqual(sum(row[0]=='service_player_type_hash' for row in f.calls),types.count(157))
                if selected==0xccb6d5be:self.assertEqual([x[136] for x in f.deferred.pending],[1,2])
                if selected==selector.AUX_SELECTOR:self.assertEqual(f.deferred.pending[-1][125:128],struct.pack('<I',f.civilization)[1:])
                self.assertIsNone(f.owner._foundation_borrow)
                self.assertEqual(f.deferred.drain(),len(types));self.assertEqual(f.deferred.pending,[])

    def test_second_pass_failure_releases_without_replaying_first_or_inventing_completion(self):
        f=self.fixture();f.fail_snapshot=2
        with self.assertRaisesRegex(ValueError,'snapshot failure'):f.owner.dispatch(profile.EVENT_KIND,f.fields(0xccb6d5be),0)
        self.assertEqual(len(f.deferred.pending),1);self.assertEqual(f.snapshot_count,2)
        self.assertTrue(all(v==0 for v in f.live.values()));self.assertEqual(sum(x[0]=='free_vector' for x in f.calls),2)
        self.assertTrue(f.owner.quarantined);self.assertIsNone(f.owner._foundation_borrow)
        self.assertFalse(any(stage=='native_district_progress_notification_completed' for stage,_ in f.emitted))

    def test_native_profile_bytes_and_foreign_lifetime_refused(self):
        f=self.fixture();p=source.verify_source();self.assertEqual(len(p['bindings']),11)
        receipt=source.bind_owner(f.backend,f.backend.core,f.read)
        self.assertIs(source.bind_owner(f.backend,f.backend.core,f.read),receipt)
        self.assertGreater(receipt.instruction_read_spans,0)
        with self.assertRaisesRegex(ValueError,'owner mismatch'):source.bind_owner(f.backend,object(),f.read)
        one=next(iter(p['functions'].values()))['instructions'][0]
        address=f.memory.base+int(one['va'],16)-0x180000000
        old=f.read
        def bad(ptr,size):
            raw=old(ptr,size)
            if ptr<=address<ptr+size:
                raw=bytearray(raw);raw[address-ptr]^=1;return bytes(raw)
            return raw
        with self.assertRaisesRegex(ValueError,'instruction changed'):source.verify_live(f.memory.base,bad)
        self.assertIs(profile.select_tables(profile.BASE_CORE_SHA256,event._TABLES),event._TABLES)

    def test_wonder_non_a0_shared_script_payload_and_archive_identity(self):
        f=self.fixture();h=f.host;p=f.backend.prefix
        # Fill the fixture host's actual interfaces, without replacing the saved
        # graph or source/admission guards. HKS execution alone is a native seam.
        h._bind=MethodType(DiagnosticHost._bind,h);h._check=MethodType(DiagnosticHost._check,h)
        h.aux_vtable=(C.c_void_p*32)();h.aux_object=(C.c_void_p*2)(C.addressof(h.aux_vtable),1)
        h.functions=[];h._script_event_owner=None;h.emit=f.emit
        h.descriptor_object=(C.c_void_p*2)();h.archives=ArchiveRegistry()
        h._fatal=lambda *a,**k:(_ for _ in ()).throw(AssertionError((a,k)))
        f.memory.put(f.memory.base+0x9f2648,struct.pack('<Q',C.addressof(h.aux_object)))
        script_event_source.verify_xp1(f.memory.base,f.read,host_pointer=h.pointer,auxiliary_pointer=C.addressof(h.aux_object))
        seen=[]
        def dispatch(name,values,**kwargs):
            f.saved._check_active();seen.append((name,values,kwargs));return False,0
        p.runtime.dispatch_game_event_result=dispatch
        service=ScriptEventService(h,p.runtime);p.events=service
        # The production service is installed before the loaded-cache lease.
        # Capture that same completed binding set in this composed fixture.
        f.token.lease.bindings=dict(h._slot_bindings)
        f.token.lease.tables=((h.vtable,tuple(h.vtable)),(h.aux_vtable,tuple(h.aux_vtable)))
        owner=C.addressof(h.aux_object);payload=service.script_arguments._create(owner)
        for value in (1,13,67,16):service.script_arguments._append(payload,payload,value)
        out=C.c_uint8(0xa5)
        self.assertFalse(service.game_event_call(owner,b'OnDistrictConstructed',payload,C.addressof(out)))
        self.assertEqual(out.value,0);self.assertEqual(seen[0][0:2],(b'OnDistrictConstructed',(1,13,67,16)))
        service.script_arguments._release(owner,payload);self.assertEqual(service.script_arguments.live_count,0)
        descriptor=C.create_string_buffer(96);ptr=C.addressof(descriptor);key=0x3000200030001
        struct.pack_into('<Q',descriptor,88,key);descriptor[72]=b'\1'
        registry=DiagnosticHost._descriptor_context(h,h.pointer)
        self.assertTrue(DiagnosticHost._archive_register(h,registry,ptr))
        self.assertTrue(DiagnosticHost._archive_register(h,registry,ptr))
        other=C.create_string_buffer(bytes(descriptor));self.assertFalse(DiagnosticHost._archive_register(h,registry,C.addressof(other)))
        DiagnosticHost._archive_remove(h,registry,ptr);self.assertEqual(h.archives.entries,{})
        service.close();self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.token.publication_count,0)


if __name__=='__main__':unittest.main()

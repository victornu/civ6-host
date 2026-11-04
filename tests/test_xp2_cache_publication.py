"""XP2 shared cache/lease/publication fixtures; native memory/calls only, no DLL."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256,profile_for_sha
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime import xp2_cache_source as source
from civ6_host.runtime import cache_facade_profiles as facade_profile
from civ6_host.runtime import loaded_cache_profiles as loaded
from civ6_host.runtime import loaded_cache_publication as lease_module
from civ6_host.runtime import xp1_cache_publication as publication
from civ6_host.runtime import a0_emergencies_updated as event
from civ6_host.runtime.native import native_player_view as view
from civ6_host.runtime.native.native_ui_cache_facades import NativeUiCacheFacades
from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
from civ6_host.runtime.native.native_retained_game_getter import read_retained_game_value
from civ6_host.runtime.native.native_official_postload import OfficialPost160Backend
from test_cache_facade_profiles import XP1FixtureBackend
import test_loaded_cache_publication as cache_fixtures
import test_xp2_preload_services as service_fixtures
from test_xp1_publication_events import STATE,fields


class XP2FixtureBackend(XP1FixtureBackend):
    def __init__(self):
        self.abi=facade_profile.facade_abi(XP2_CORE_SHA256)
        self.memory={};self.calls=[];self.gates=[];self.alive=True;self.overrun=False;self.retained=None
        self.b0_results=[0x74000,0x74100];self.c0_results=[0x75000,0x75100]
        self.output=struct.pack('<iii',74,46,3404)+bytes(range(12))+struct.pack('<I',0xFECDA581)
        p=source.source();a=p['profile'];o=a['ownership']
        for _,body in source.bodies(p):
            for f in body['fragments']:
                for row in f['instructions']:
                    rva=int(row['rva'],16) if 'rva' in row else int(row['va'],16)-0x180000000
                    self.put(self.core_base+rva,bytes.fromhex(row['bytes']))
        for row in p['slots']:self.q(self.core_base+row['vtable_rva']+row['slot'],self.core_base+row['target_rva'])
        for address,value in ((self.outer,self.core_base+a['outer_vtable_rva']),(self.outer+8,self.inner),
            (self.inner,self.core_base+a['inner_vtable_rva']),(self.core_base+o['inner_global_rva'],self.inner),
            (self.inner+0x1A68,self.service),(self.core_base+o['service_global_rva'],self.service),
            (self.service,self.core_base+o['service_vtable_rva']),(self.service+8,self.owner),
            (self.owner,self.core_base+o['owner_vtable_rva']),(self.owner+0x20,self.service),
            (self.inner+0x60,self.game),(self.core_base+o['game_global_rva'],self.game),
            (self.owner+o['owner_cache_member_offset'],self.member),(self.member,self.core_base+o['cache_member_vtable_rva']),
            (self.member+0x20,self.owner)):
            self.q(address,value)
        self.put(self.game+0x2A4,b'\1');self.put(self.owner+0x38,b'\1');self.q(self.owner+0x58,0x99000)
        self.put(self.member+0x28,self.output)
        self.identity=facade_profile.context_state(self.core_base,self.outer,self.read,core_sha256=XP2_CORE_SHA256)
        for ptr,vt,key in ((0x71000,self.abi.game_facade_vtable_rva,'owner'),(0x72000,self.abi.cache_service_vtable_rva,'member'),
            (0x73000,self.abi.system_facade_vtable_rva,'system_member'),
            *((p,self.abi.cache_b0_result_vtable_rva,'b0_result_owner') for p in self.b0_results),
            *((p,self.abi.cache_c0_result_vtable_rva,'c0_result_owner') for p in self.c0_results)):
            self.put(ptr,struct.pack('<QQQI',self.core_base+vt,0,self.identity[key],1)+b'\xCD'*4)

    def acquire(self):
        self.retained=NativeUiCacheFacades(self,self.outer,core_sha256=XP2_CORE_SHA256)
        return self.retained


class XP2CacheTests(unittest.TestCase):
    def graph(self):
        old,a=cache_fixtures.LoadedCacheTests().ownership_fixture();f=XP2FixtureBackend();b=a.owner
        b.runtime.read=f.read;b.load_abi=profile_for_sha(XP2_CORE_SHA256)
        a.cache_abi=loaded.loaded_cache_abi(XP2_CORE_SHA256)
        b.loaded_readback=dict(width=74,height=46,turn=0)
        for rva,pointer in zip(source.source()['profile']['host_globals'],
                (b.host.pointer,C.addressof(b.host.aux_object),C.addressof(b.host.logger_object))):
            f.q(f.core_base+rva,pointer)
        lease=lease_module.LoadedCachePublication(a)
        return f,a,lease

    def test_exact_pins_complete_bodies_and_canonical_abi(self):
        p=source.source();self.assertGreater(len(p['functions']),200)
        for path,digest in lease_module.source_dependencies(core_sha256=XP2_CORE_SHA256).items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        a=loaded.loaded_cache_abi(XP2_CORE_SHA256)
        self.assertEqual(a.map_view_vtable_rva,0x9BB538)
        self.assertFalse(facade_profile.facade_abi(XP2_CORE_SHA256).full_refresh_admitted)
        with self.assertRaises(ValueError):loaded.require_mode(a,'public')
        with self.assertRaises(ValueError):facade_profile.facade_abi('0'*64)

    def test_full_source_and_slots_reject_late_body_tampering(self):
        f=XP2FixtureBackend();source.verify_live(f.core_base,f.read)
        row=source.source()['functions']['kind4_refresh']['body']['fragments'][-1]['instructions'][-1]
        address=f.core_base+int(row['rva'],16) if 'rva' in row else int(row['va'],16)
        f.memory[address]^=1
        with self.assertRaisesRegex(ValueError,'instructions'):source.verify_live(f.core_base,f.read)
        f.memory[address]^=1;f.memory[f.core_base+0xA45040+0xA8]^=1
        with self.assertRaisesRegex(ValueError,'virtual'):source.verify_live(f.core_base,f.read)

    def test_shared_copy_replacement_release_and_signed_getter(self):
        f=XP2FixtureBackend();facades=f.acquire()
        first=facades._copy_cache_outputs();second=facades._copy_cache_outputs()
        self.assertEqual(first.output,f.output);self.assertEqual(second.copied_value,0xFECDA581)
        self.assertEqual(read_retained_game_value(facades,f.read,core_sha256=XP2_CORE_SHA256,
            invoke=lambda target,receiver: -1),-1)
        state=loaded.validate_copy(f.core_base,f.outer,f.read,loaded.loaded_cache_abi(XP2_CORE_SHA256),facades,
            f.output,expected_game=f.game,expected_dimensions=(74,46))
        self.assertEqual(state['view'],f.member);self.assertEqual(f.gates,[])
        with self.assertRaises(ValueError):facades.refresh()
        facades.close()
        released=[r[1] for r in f.calls if type(r[0]) is int and r[0]-f.core_base in f.abi.release_rvas]
        self.assertEqual(released,[0x74000,0x75000,0x74100,0x75100,0x71000,0x72000,0x73000])

    def test_shared_lease_requires_same_engine_live_game_and_callback_tables(self):
        f,a,lease=self.graph();lease._check()
        a.owner.load_abi=profile_for_sha(XP1_CORE_SHA256)
        with self.assertRaises(RuntimeError):lease._check()
        a.owner.load_abi=profile_for_sha(XP2_CORE_SHA256)
        f.q(f.core_base+0xB8AA88,a.owner.host.pointer)
        with self.assertRaisesRegex(ValueError,'host global'):lease._check()

    def test_real_publication_token_routes_void_kind4_once(self):
        f,a,lease=self.graph();b=a.owner;facades=f.acquire();facades._copy_cache_outputs()
        buffers={};actual=C.create_string_buffer
        def buffer(*args):
            result=actual(*args);buffers[C.addressof(result)]=result;return result
        def read(address,n):return C.string_at(address,n) if address in buffers else f.read(address,n)
        p=view.NativePlayerViewPublisher(b.core,b.context,Mock(),read=read,core_sha256=XP2_CORE_SHA256)
        a.publisher=b.prefix.view_publisher=p
        backend=NativeCacheFacadeBackend(b.core,Mock(),context_alive=lambda:True,read=f.read,
            core_sha256=XP2_CORE_SHA256,publication_owner=lease)
        lease.attach(p,backend);p._facades=facades;facades.backend=backend
        a.publication_owner=lease;lease.entered=lease.returned=lease.copied=True
        post=OfficialPost160Backend.__new__(OfficialPost160Backend)
        post.owner=b;post.facade=a;post.postload_mode='candidate';post._candidate_cache_lease=lease
        post.attempted=post.native_call_attempted=True;post.candidate_diagnostics={'void_return_ignored':True}
        b._xp1_post160_attempt=post;lease.post160_attempt=post;lease.post160_finished=True
        b.stage=publication.FINISHED_STAGE;b.busy=False
        attempt=publication.SavedCachePublication(post);lease.begin_publication(attempt)
        calls=[]
        def virtual(core,receiver,slot,target,result,*arguments):
            calls.append((slot,target,result,arguments))
            return (lambda receiver:f.owner) if slot==0x80 else Mock()
        with patch.object(view.C,'create_string_buffer',side_effect=buffer),patch.object(view,'virtual',side_effect=virtual):
            self.assertEqual(p.publish(publication_owner=attempt),(74,46,3404))
            with self.assertRaisesRegex(ValueError,'cannot retry'):p.publish(publication_owner=attempt)
        self.assertEqual([(r[0],r[1]) for r in calls],[(8,0xA590),(0x80,0x956030),(0x190,0x591930)])
        self.assertIsNone(calls[-1][2]);self.assertEqual(calls[-1][3],(C.c_void_p,C.c_uint8))
        self.assertTrue(attempt.native_returned);self.assertFalse(p.native_cache_gate)
        self.assertFalse(p.full_facade_initialization_reproduced)

    def test_xp2_emergency_uses_same_composed_fifo_and_source_guards(self):
        fixture=service_fixtures.XP2PreloadServices();self.addCleanup(fixture.doCleanups)
        h,d,ctl,a=fixture.compose()
        c=a.install_consumers(receiver_state=dict(STATE),pre_turn_immediate_state=dict(STATE),entity_listener_count=0)
        b=NS(core=d.core,context=d.context,prefix=NS(event_arguments=a,deferred_events=d),
            stage=publication.FINISHED_STAGE,busy=False,poisoned=False,destroyed=False,
            runtime=NS(read=fixture.read),load_abi=profile_for_sha(XP2_CORE_SHA256))
        p=publication.SavedCachePublication.__new__(publication.SavedCachePublication)
        p.owner=b;p.native_attempted=False;b._xp1_publication_attempt=p
        base=b.core._handle
        for _,body in source.bodies():
            for frag in body['fragments']:
                for row in frag['instructions']:
                    rva=int(row['rva'],16) if 'rva' in row else int(row['va'],16)-0x180000000
                    fixture.put(base+rva,bytes.fromhex(row['bytes']))
        address=base+0x5FA9B0;prior=fixture.read(address,1);fixture.put(address,bytes([prior[0]^1]))
        with self.assertRaisesRegex(ValueError,'emitter changed'):c.enable_publication_events(p)
        fixture.put(address,prior);c.enable_publication_events(p)
        self.assertEqual(c.publication_event_profile.source_sha256,source.SOURCE[1])
        pointer,a.reader.next_node=fixture.tree(fields())
        self.assertEqual(a.dispatch(h.pointer,event.EVENT_KIND,pointer),0)
        self.assertEqual(len(d.pending),1)
        self.assertEqual(struct.unpack_from('<I',d.pending[0],4)[0],event.RECORD_TYPE)
        self.assertEqual(d.drain(),1);self.assertEqual(len(d.pending),0)
        a.close();ctl.close();d.close()

    def test_prepared_service_and_retained_lease_forward_selected_engine(self):
        from civ6_host.runtime.cache_facade_service import CacheFacadeService
        from civ6_host.runtime.retained_game_service import RetainedGameLease
        f=XP2FixtureBackend();core=NS(_handle=f.core_base)
        with patch.object(NativeCacheFacadeBackend,'_call',side_effect=f.call):
            service=CacheFacadeService(core,f.outer,core_sha256=XP2_CORE_SHA256,read=f.read,context_alive=lambda:True)
            self.assertEqual(service.backend.abi.core_sha256,XP2_CORE_SHA256)
            self.assertEqual(service.copy_cached_metadata().output,f.output)
            service.close()
        f=XP2FixtureBackend()
        def factory(result,*args):
            def target(address):
                if address==f.core_base+0x597A90:return lambda receiver:-1
                return lambda *values:f.call(address,*values)
            return target
        with patch.object(C,'WINFUNCTYPE',side_effect=factory):
            lease=RetainedGameLease(core,f.outer,f.read,core_sha256=XP2_CORE_SHA256,context_alive=lambda:True)
            self.assertEqual(lease.value(),-1);lease.close();self.assertTrue(lease._closed)

    def test_generated_source_verifier_selects_xp2_exactly(self):
        from civ6_host.runtime.native import native_checkpoint_postload_facades as generated
        f=XP2FixtureBackend();proof=generated.verify_source(core_sha256=XP2_CORE_SHA256)
        self.assertEqual(proof,source.source())
        generated.check_live_code(f.core_base,f.read,proof,core_sha256=XP2_CORE_SHA256)
        with self.assertRaises(ValueError):generated.check_live_code(f.core_base,f.read,loaded.source(),core_sha256=XP2_CORE_SHA256)

if __name__=='__main__':unittest.main()

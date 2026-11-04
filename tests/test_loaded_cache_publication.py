"""Grouped source/ownership fixtures. No DLL calls or native qualification."""
import ctypes as C
from dataclasses import replace
import struct
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch
from civ6_host.runtime import loaded_cache_profiles as profile
from civ6_host.runtime import loaded_cache_publication as owner_module
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256
from civ6_host.runtime.cache_facade_profiles import facade_abi
from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
from civ6_host.runtime.native.native_checkpoint_postload_facades import NativeFacadeBackend
from test_cache_facade_profiles import XP1FixtureBackend

class LoadedCacheTests(unittest.TestCase):
    def fixture(self):
        f=XP1FixtureBackend();a=profile.loaded_cache_abi(XP1_CORE_SHA256)
        for slot,target in ((8,a.service_ensure_rva),(0x80,a.service_owner_rva),(0xA8,a.service_publish_rva)):
            f.q(f.core_base+a.service_vtable_rva+slot,f.core_base+target)
        f.put(f.game+0x2A4,b'\1');f.put(f.owner+0x38,b'\1');f.q(f.owner+0x58,0x99000)
        f.output=struct.pack('<iii',74,46,3404)+bytes(range(12))+struct.pack('<I',0xFECDA581)
        f.put(f.member+0x28,f.output)
        facades=f.acquire();facades._copy_cache_outputs()
        return f,a,facades

    def validate(self,f,a,facades,copied=None):
        return profile.validate_copy(f.core_base,f.outer,f.read,a,facades,
            f.output if copied is None else copied,expected_game=f.game,expected_dimensions=(74,46))

    def test_canonical_engine_modes_and_distinct_map_member(self):
        base=profile.loaded_cache_abi(BASE_CORE_SHA256);xp1=profile.loaded_cache_abi(XP1_CORE_SHA256)
        self.assertEqual((base.map_view_offset,xp1.map_view_offset),(0x1770,0xA8B0))
        profile.require_mode(base,'public');profile.require_mode(xp1,'candidate')
        for abi,mode in ((xp1,'public'),(base,'candidate'),(xp1,'unknown')):
            with self.assertRaises(ValueError):profile.require_mode(abi,mode)
        with self.assertRaises(ValueError):profile.loaded_cache_abi('0'*64)
        with self.assertRaises(ValueError):profile.require_abi(replace(xp1))

    def test_all_retained_bytes_and_virtual_slots_verified(self):
        proof=profile.source();memory={};base=0x180000000
        for body in proof['bodies'].values():
            for f in profile._body(body)['fragments']:
                for i in f['instructions']:
                    memory.update((int(i['va'],16)+n,v) for n,v in enumerate(bytes.fromhex(i['bytes'])))
        for r in proof['slots']:
            memory.update((base+r['vtable_rva']+r['slot']+n,v) for n,v in enumerate(struct.pack('<Q',base+r['target_rva'])))
        read=lambda p,n:bytes(memory[p+i] for i in range(n))
        profile.verify_xp1_live(base,read,proof)
        late=profile._body(proof['bodies']['visibility_tail'])['fragments'][-1]['instructions'][-1]
        address=int(late['va'],16);memory[address]^=1
        with self.assertRaisesRegex(ValueError,'instructions'):profile.verify_xp1_live(base,read,proof)
        memory[address]^=1
        row=proof['slots'][0];memory[base+row['vtable_rva']+row['slot']]^=1
        with self.assertRaisesRegex(ValueError,'virtual'):profile.verify_xp1_live(base,read,proof)

    def test_real_copy_layout_preserves_tail_bits_without_enabling_gate(self):
        f,a,facades=self.fixture();state=self.validate(f,a,facades)
        self.assertEqual(state['view'],f.member);self.assertEqual(state['dimensions'],(74,46,3404))
        self.assertEqual(struct.unpack_from('<I',f.output,24)[0],0xFECDA581)
        self.assertEqual(f.gates,[])

    def test_visibility_partial_or_empty_is_refused(self):
        f,a,facades=self.fixture()
        for address,raw in ((f.owner+0x38,b'\0'),(f.owner+0x58,b'\0'*8),(f.game+0x2A4,b'\0')):
            prior=f.read(address,len(raw));f.put(address,raw)
            with self.assertRaises(ValueError):self.validate(f,a,facades)
            f.put(address,prior)

    def test_replaced_game_member_and_wrapper_refused(self):
        f,a,facades=self.fixture()
        for address in (f.core_base+a.game_global_rva,f.owner+a.map_view_offset,facades.game_facade+16):
            prior=f.read(address,8);f.q(address,0)
            with self.assertRaises((ValueError,KeyError)):self.validate(f,a,facades)
            f.put(address,prior)
        self.assertEqual(f.gates,[])

    def test_dimension_short_and_unknown_tail_copies_refused(self):
        f,a,facades=self.fixture()
        for copy in (f.output[:27],bytearray(f.output),struct.pack('<i',75)+f.output[4:],f.output[:27]+bytes([f.output[27]^1])):
            with self.assertRaises(ValueError):self.validate(f,a,facades,copy)

    def test_base_uses_existing_map_layout_and_public_mode(self):
        f,_,facades=self.fixture();a=profile.loaded_cache_abi(BASE_CORE_SHA256)
        facades.abi=facade_abi(BASE_CORE_SHA256)
        for address,value in ((f.outer,f.core_base+a.outer_vtable_rva),(f.core_base+a.service_global_rva,f.service),
            (f.service,f.core_base+a.service_vtable_rva),(f.core_base+a.game_global_rva,f.game),
            (f.owner,f.core_base+a.cache_owner_vtable_rva),(f.owner+a.map_view_offset,f.member),
            (f.member,f.core_base+a.map_view_vtable_rva)):
            f.q(address,value)
        for slot,target in ((8,a.service_ensure_rva),(0x80,a.service_owner_rva),(0xA8,a.service_publish_rva)):
            f.q(f.core_base+a.service_vtable_rva+slot,f.core_base+target)
        self.assertEqual(self.validate(f,a,facades)['view'],f.member)

    def test_candidate_refresh_reuses_native_order_without_public_gate(self):
        f=XP1FixtureBackend();facades=f.acquire();calls=[]
        original=f.call
        def call(target,*args):
            calls.append(target-f.core_base)
            if target-f.core_base==f.abi.publish_rva:
                self.assertEqual(args,(facades.game_facade,1));return None
            return original(target,*args)
        candidate=NS(copy_returned=Mock())
        f.call=call;f.require_loaded_publication=Mock(return_value=candidate)
        copied=facades.refresh(public_gate=False)
        self.assertEqual(copied.output,f.output)
        self.assertEqual(calls,[f.abi.publish_rva,f.abi.copy_rva,
            f.abi.targets[(f.abi.cache_service_vtable_rva,0xB0)],f.abi.targets[(f.abi.cache_service_vtable_rva,0xC0)]])
        self.assertEqual(f.gates,[]);candidate.copy_returned.assert_called_once_with(f,facades)
        with self.assertRaises(ValueError):facades.refresh()

    def test_foreign_capability_refused_before_native_call(self):
        f=XP1FixtureBackend();b=NativeCacheFacadeBackend(NS(_handle=f.core_base),Mock(),
            context_alive=lambda:True,read=f.read,core_sha256=XP1_CORE_SHA256,publication_owner=object())
        with patch.object(C,'WINFUNCTYPE',create=True) as native:
            with self.assertRaisesRegex(ValueError,'Foreign'):b.call(f.core_base+f.abi.publish_rva,0x71000,1)
            native.assert_not_called()
        with self.assertRaises(ValueError):b.set_public_cache_gate(True)

    def test_unowned_xp1_typed_publish_remains_refused(self):
        f=XP1FixtureBackend();b=NativeCacheFacadeBackend(NS(_handle=f.core_base),Mock(),
            context_alive=lambda:True,read=f.read,core_sha256=XP1_CORE_SHA256)
        with patch.object(C,'WINFUNCTYPE',create=True) as native:
            with self.assertRaises(ValueError):b.call(f.core_base+f.abi.publish_rva,0x71000,1)
            native.assert_not_called()

    def test_candidate_native_signature_flag_and_single_attempt(self):
        f=XP1FixtureBackend();lease=object.__new__(owner_module.LoadedCachePublication)
        b=NativeCacheFacadeBackend(NS(_handle=f.core_base),Mock(),context_alive=lambda:True,
            read=f.read,core_sha256=XP1_CORE_SHA256,publication_owner=lease)
        lease.entered=lease.returned=lease.copied=False
        lease.require=Mock(return_value=NS(game_facade=0x71000));lease.check_backend=Mock();lease.poison=Mock()
        lease.before_backend_call=Mock();lease.after_backend_call=Mock()
        native=Mock()
        with patch.object(C,'WINFUNCTYPE',create=True,return_value=lambda target:native) as factory:
            b.call(f.core_base+f.abi.publish_rva,0x71000,1)
            factory.assert_called_once_with(None,C.c_void_p,C.c_uint8)
            native.assert_called_once_with(0x71000,1)
            with self.assertRaises(RuntimeError):b.call(f.core_base+f.abi.publish_rva,0x71000,1)
            self.assertEqual(native.call_count,1)
        self.assertTrue(lease.returned)

    def test_candidate_failure_quarantines_instead_of_cleanup(self):
        f=XP1FixtureBackend();lease=object.__new__(owner_module.LoadedCachePublication)
        lease.owner=NS(poisoned=False);lease.prefix=NS(quarantined=False);lease.poisoned=False
        lease.check_backend=Mock()
        lease.before_backend_call=Mock();lease.after_backend_call=Mock()
        b=NativeCacheFacadeBackend(NS(_handle=f.core_base),Mock(),context_alive=lambda:True,
            read=f.read,core_sha256=XP1_CORE_SHA256,publication_owner=lease)
        with patch.object(b,'_call',side_effect=RuntimeError('uncertain native effect')):
            with self.assertRaises(RuntimeError):b.call(f.core_base+f.abi.copy_rva,0x72000,bytearray(32))
        self.assertTrue(lease.poisoned);self.assertTrue(lease.owner.poisoned);self.assertTrue(lease.prefix.quarantined)

    def test_candidate_binding_stores_actual_copy_and_keeps_public_closed(self):
        f,a,facades=self.fixture();p=NS(_facades=facades,native_cache_gate=False,
            full_facade_initialization_reproduced=False,cache_map_snapshot=None)
        callbacks=Mock();lease=NS(copied=True,require=Mock())
        b=object.__new__(NativeFacadeBackend)
        b.owner=NS(core=NS(_handle=f.core_base),context=f.outer,runtime=NS(read=f.read),
            bound_identity={'game':f.game},prefix=NS(deferred_events=callbacks))
        b.publisher=p;b.cache_abi=a;b.publication_mode='candidate';b.publication_owner=lease
        b.load_result={'readback':{'width':74,'height':46}}
        b.bind_cache(f.output)
        self.assertEqual(p.cache_map_snapshot,f.output)
        self.assertFalse(p.native_cache_gate);self.assertFalse(p.full_facade_initialization_reproduced)
        self.assertEqual(callbacks.mock_calls,[])
        lease.copied=False
        with self.assertRaises(RuntimeError):b.bind_cache(f.output)

    def test_xp1_publisher_cannot_use_base_dynamic_publication_or_cleanup(self):
        read=Mock(side_effect=AssertionError('must not read or invoke'))
        p=NativePlayerViewPublisher(NS(_handle=0x180000000),0x1000,Mock(),read=read,core_sha256=XP1_CORE_SHA256)
        with self.assertRaises(ValueError):p.publish()
        with self.assertRaises(RuntimeError):p.read_retained_game_value()
        p._loaded_cache_candidate_owner=object.__new__(owner_module.LoadedCachePublication)
        with self.assertRaisesRegex(ValueError,'wrapper release'):p.close()
        read.assert_not_called()

    def test_candidate_owner_rejects_unrelated_backend(self):
        with self.assertRaises(ValueError):owner_module.LoadedCachePublication(NS())

    def ownership_fixture(self):
        from civ6_host.runtime.native.native_checkpoint_load import NativeLoadBackend
        from civ6_host.runtime.saved_load_services import SavedLoadServices
        from civ6_host.runtime.deferred_service import DeferredService
        from civ6_host.runtime.saved_load_profiles import profile_for_sha
        f,a,facades=self.fixture()
        host=NS(vtable=(C.c_void_p*100)(),aux_vtable=(C.c_void_p*100)(),logger_vtable=(C.c_void_p*32)())
        for table in (host.vtable,host.aux_vtable,host.logger_vtable):
            for i in range(len(table)):table[i]=0x200000+i*8
        host.object=(C.c_void_p*2)(C.addressof(host.vtable),1);host.pointer=C.addressof(host.object)
        host.aux_object=(C.c_void_p*2)(C.addressof(host.aux_vtable),1)
        host.logger_object=(C.c_void_p*2)(C.addressof(host.logger_vtable),1)
        host._slot_bindings={}
        for slot in (0x10,0x28,0x40):
            host.logger_vtable[slot//8]=0x100000+slot
            host._slot_bindings[(C.addressof(host.logger_vtable),slot)]=(0x100000+slot,lambda:None)
        for rva,ptr in ((0x9F2640,host.pointer),(0x9F2648,C.addressof(host.aux_object)),(0x9F2650,C.addressof(host.logger_object))):
            f.q(f.core_base+rva,ptr)
        b=object.__new__(NativeLoadBackend);b.core=NS(_handle=f.core_base);b.context=f.outer;b.host=host
        b.load_abi=profile_for_sha(XP1_CORE_SHA256);b.poisoned=b.destroyed=False;b.busy=True
        b.thread=(123,threading.get_ident());b.runtime=NS(thread=lambda:b.thread,read=f.read)
        b.inputs=NS(game=b'data');b.reader=NS(transport=NS(closed=True,cursor=4))
        b.bound_identity={'game':f.game};b.stage='observed-awaiting-post160'
        b.owner=NS(require_context=Mock())
        p=object.__new__(SavedLoadServices);b.prefix=p
        p.backend=b;p.host=host;p.core=b.core;p.context=b.context
        p.closed=p.quarantined=False;p.game_child=987;p.configuration_readback_verified=True
        # The native export owner is deliberately distinct from DiagnosticHost.
        p.runtime=NS(host=NS(native_exports=True),service_owner=host,registry=NS(validate=Mock()))
        host._saved_load_services=p
        d=object.__new__(DeferredService);p.deferred_events=d;d.host=host
        host._deferred_service_owner=d;d.thread=threading.get_ident();d.addresses={}
        d.closed=d.quarantined=d._deferred_drain_poisoned=False
        attempt=object.__new__(NativeFacadeBackend);attempt.owner=b;attempt.cache_abi=a
        attempt.publication_mode='candidate';attempt.attempted=True;attempt.publisher=None
        return f,attempt

    def test_owner_uses_real_service_link_and_keeps_native_exports_distinct(self):
        f,attempt=self.ownership_fixture();p=attempt.owner.prefix
        self.assertIsNot(p.runtime.host,p.host)
        lease=owner_module.LoadedCachePublication(attempt);lease._check()
        p.runtime.service_owner=object()
        with self.assertRaises((ValueError,RuntimeError)):lease._check()
        with self.assertRaises(ValueError):owner_module.LoadedCachePublication(attempt)

    def test_owner_detects_reader_reuse_and_callback_or_global_replacement(self):
        f,attempt=self.ownership_fixture();b=attempt.owner
        lease=owner_module.LoadedCachePublication(attempt)
        b.reader.transport.cursor=3
        with self.assertRaises(RuntimeError):lease._check()
        b.reader.transport.cursor=4
        b.host.logger_vtable[2]=0xBAD
        with self.assertRaises(RuntimeError):lease._check()
        b.host.logger_vtable[2]=0x100010
        f.q(f.core_base+0x9F2648,b.host.pointer)
        with self.assertRaises(ValueError):lease._check()

    def test_owner_requires_known_logger_callbacks_without_installing_fallback(self):
        _,attempt=self.ownership_fixture();h=attempt.owner.host
        address,call=h._slot_bindings[(C.addressof(h.logger_vtable),0x40)]
        call._native_unavailable=('logger',0x40)
        with self.assertRaisesRegex(ValueError,'logger'):owner_module.LoadedCachePublication(attempt)

    def test_saved_load_admission_is_not_broadened(self):
        from civ6_host.runtime.saved_load_profiles import profile_for_sha,require_saved_load_admission
        with self.assertRaises(ValueError):require_saved_load_admission(profile_for_sha(XP1_CORE_SHA256))

if __name__=='__main__':unittest.main()

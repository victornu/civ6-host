"""Selected turn primitives with real saved/host/FIFO owners; no DLL execution."""
import ctypes as C
from dataclasses import replace
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_turn_profile as profiles
from civ6_host.runtime import xp2_turn_source as source
from civ6_host.runtime import xp2_turn_event_profile as climate
from civ6_host.runtime import xp1_host_thread_gate as thread_gate
from civ6_host.runtime import xp1_host_slot78 as slot78
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import select
from civ6_host.runtime.native import native_action_transport as calls, native_forced_endturn as forced
from civ6_host.runtime.native import native_host
from civ6_host.runtime.native.native_host_thread_gate import HostThreadGate, PROFILE
from civ6_host.runtime.xp1_loaded_lifetime import LoadedLifetime
import test_xp1_turn_transport as old_turn
import test_xp2_action_transport as action_fixture


class Memory(action_fixture.Memory):
    def __init__(self):
        super().__init__()
        self.profile=source.ABI;self.value=0;self.turn_proof=source.source()
        for b in self.turn_proof['functions'].values():
            for f in b['fragments']:
                self.put(self.base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        for vt,slots in self.turn_proof['tables'].values():
            for slot,target in slots.items():self.put(self.base+vt+int(slot),struct.pack('<Q',self.base+target))

    def allocate(self,size):return self.own(C.create_string_buffer(size))

    def factory(self,result,*args):
        fallback=super().factory(result,*args)
        def bind(address):
            if not callable(address) and address-self.base in (
                    self.profile.tree_ctor_rva,self.profile.tree_dtor_rva,
                    self.profile.vector_ctor_rva,self.profile.vector_dtor_rva,self.profile.reason_converter_rva):
                fn=old_turn.Memory.factory(self,result,*args)(address)
                if address-self.base in (self.profile.tree_dtor_rva,self.profile.vector_dtor_rva):
                    def destroy(ptr):
                        fn(ptr)
                        if getattr(self,'damage_destructor_canary',False):
                            C.memset(ptr+(96 if address-self.base==self.profile.tree_dtor_rva else 72),0,1)
                    return destroy
                return fn
            return fallback(address)
        return bind

    def virtual(self,core,pointer,slot,rva,result,*args):
        p=self.profile
        if rva in (p.tree_lookup_rva,p.vector_lookup_rva,p.string_setter_rva):
            return old_turn.Memory.virtual(self,core,pointer,slot,rva,result,*args)
        if rva in (p.request_rva,p.unready_wrapper_rva):
            def request(context,action,player,*parameters):
                self.calls.append(('request',slot,rva,context,action,player))
                if rva==p.request_rva:
                    payload=struct.pack('<III',0xD7C02786,player,1913349224 if self.value else 0xB6FA1284)
                    if getattr(self,'damage_request_canary',False):
                        C.memset(parameters[0]+(72 if self.value else 96),0,1)
                else:
                    mode=getattr(self,'unready_mode','queued')
                    if mode=='none':return
                    payload=struct.pack('<II',0xE8A26B84,player) if mode=='queued' else b'unknown-native-fixture'
                # The native-call fixture enters the actual saved transport callback.
                self.transport.capture(self.transport.host.pointer,self.make_archive(payload))
            return request
        return super().virtual(core,pointer,slot,rva,result,*args)


class Fixture(action_fixture.Fixture):
    def __init__(self):
        with patch.object(action_fixture,'Memory',Memory):super().__init__()
        self.backend.core._civ6_host_execution_image = select(
            'xp2-gamecore-current-092abfbb', core_path=self.backend.core._name)
        self.backend.busy=True
        self.backend._saved_load_candidate=True
        for slot in (0x58,0x60,0x78):
            self.host._bind(self.host.vtable,slot,None,[C.c_void_p],self.host._unsupported('host',slot))
        self.kernel.GetCurrentThreadId=Mock(return_value=511)
        self.stack.enter_context(patch.object(forced,'virtual',side_effect=self.memory.virtual))
        self.stack.enter_context(patch.object(native_host,'virtual',side_effect=self.memory.virtual))

    def install(self):
        t=super().install();self.memory.transport=t;return t


class XP2TurnServicesTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_source_comparison_complete_tails_slots_and_pins(self):
        m=Memory();p=source.source()
        self.assertEqual(len(p['functions']),26)
        self.assertEqual(sum(r['normalized_equal'] for r in p['comparisons'].values()),23)
        self.assertGreater(p['comparisons']['tree_lookup']['complete_xp1_instruction_count'],
                           p['comparisons']['tree_lookup']['retained_xp1_instruction_count'])
        self.assertEqual(p['shared_parameter_bodies']['tree_lookup'],'0x99f5c0')
        profiles.verify_live(m.base,m.context,m.read,core_sha256=XP2_CORE_SHA256)
        m.put(m.base+0xB8AA80,struct.pack('<Q',0x300000))
        for family in ('thread','slot78'):
            source.verify_live(m.base,m.read,family=family,host_pointer=0x300000)
        self.assertLessEqual(max(n for _,n in m.reads),4096)
        for name,body in p['functions'].items():
            tail=body['fragments'][-1];at=m.base+int(tail['start_rva'],16)+tail['length']-1
            family='thread' if name.startswith('thread_') else 'slot78' if name.startswith('slot78_') else 'turn'
            with self.subTest(body=name):
                m.bytes[at]^=1
                with self.assertRaisesRegex(ValueError,'differs'):
                    source.verify_live(m.base,m.read,family=family,context=m.context,host_pointer=0x300000)
                m.bytes[at]^=1
        for vt,slots in p['tables'].values():
            for slot in slots:
                at=m.base+vt+int(slot);m.bytes[at]^=1
                with self.assertRaisesRegex(ValueError,'slot'):
                    profiles.verify_live(m.base,m.context,m.read,core_sha256=XP2_CORE_SHA256)
                m.bytes[at]^=1
        execution_image=select('xp2-gamecore-current-092abfbb',
            core_path=p['image']['path'])
        pins=source.source_dependencies(execution_image=execution_image)
        for path,digest in pins.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        for mod in (profiles,thread_gate,slot78):
            self.assertEqual(mod.source_dependencies(core_sha256=XP2_CORE_SHA256,
                execution_image=execution_image),pins)
            with self.assertRaises(ValueError):mod.source_dependencies(core_sha256='unknown')
        self.assertEqual(pins[execution_image.path], execution_image.image_sha256)
        self.assertNotIn(str(Path(source.source()['comparison_image']['path']).resolve()),pins)
        self.assertNotIn(str(Path(native_host.__file__).resolve()),pins)
        self.assertTrue(any('actual-core-092-integration\\before\\2026-11-06T0920'
                            in path and path.endswith('native_host.py') for path in pins))
        self.assertTrue(climate.source_dependencies(execution_image=execution_image))
        self.assertEqual(climate.event_profile(core_sha256=XP2_CORE_SHA256,
            execution_image=execution_image).source_sha256, climate.SCOPE_SOURCE[1])
        self.assertIs(profiles.turn_profile(XP2_CORE_SHA256),source.ABI)
        with self.assertRaises(ValueError):profiles.require_profile(replace(source.ABI),XP2_CORE_SHA256)

    def test_current_owner_requires_the_retained_execution_profile_and_sdk_transition(self):
        f=self.fixture();backend=f.backend
        source.require_prepared_owner(backend)
        selected=backend.core._civ6_host_execution_image
        self.assertEqual(selected.image_sha256,
                         '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f')
        self.assertEqual(selected.reference_core_sha256,XP2_CORE_SHA256)
        del backend.core._civ6_host_execution_image
        with self.assertRaisesRegex(ValueError,'exact reference Core image'):
            source.require_prepared_owner(backend)

    def test_unprofiled_legacy_owner_requires_exact_reference_core_bytes(self):
        f=self.fixture();backend=f.backend
        del backend.core._civ6_host_execution_image
        with self.assertRaisesRegex(ValueError,'exact reference Core image'):
            source.require_prepared_owner(backend)

    def test_unprofiled_reference_core_path_keeps_legacy_owner_route(self):
        from tempfile import TemporaryDirectory
        f=self.fixture();backend=f.backend
        del backend.core._civ6_host_execution_image
        with TemporaryDirectory() as temp:
            path=Path(temp)/'GameCore_XP2_FinalRelease.dll'
            path.write_bytes(b'reference-image-fixture-bytes')
            backend.core._name=str(path)
            with patch('hashlib.file_digest',return_value=NS(hexdigest=lambda:XP2_CORE_SHA256)):
                source.require_prepared_owner(backend)

    def test_legacy_turn_image_pin_does_not_alias_the_installed_current_core(self):
        with self.assertRaisesRegex(ValueError,'turn/service dependency differs'):
            source.source_dependencies()

    def test_actual_saved_requests_parameter_types_fifo_and_canary(self):
        f=self.fixture();t=f.install();m=f.memory
        for forced_request in (False,True):
            t.request_end_turn(0,player_ids=(0,),user_forced=forced_request)
        self.assertEqual(t.pending,[struct.pack('<III',0xD7C02786,0,0xB6FA1284),
                                   struct.pack('<III',0xD7C02786,0,1913349224)])
        self.assertIn(('dtor',source.ABI.tree_dtor_rva),m.calls)
        self.assertIn(('dtor',source.ABI.vector_dtor_rva),m.calls)
        self.assertTrue(any(r[:3]==('virtual',0x108,source.ABI.string_setter_rva) for r in m.calls))
        with self.assertRaises(ValueError):t.request_end_turn(1,player_ids=(0,))
        with self.assertRaises(ValueError):t.request_end_turn(0,player_ids=(0,),user_forced=1)
        self.assertEqual(len(t.pending),2)
        with self.assertRaisesRegex(ValueError,'continuation'):t.deliver_one()
        calls.NativeActionTransport.deliver_one(t);calls.NativeActionTransport.deliver_one(t)
        t.require_empty_native_queue()
        self.assertEqual(m.assertion,(m.context,0xFFFFFFFF,0))
        # Real Destroy token is still required before callback restoration.
        token=LoadedLifetime.__new__(LoadedLifetime);token.owner=f.backend;token.phase='services';token.destroy_returned=True
        f.backend._loaded_lifetime=token
        with self.assertRaisesRegex(ValueError,'before actual'):t.close()
        f.backend.destroyed=True;t.close()
        self.assertEqual(f.host.vtable[0x70//8],f.previous[0])

    def test_canaries_and_body_mutation_never_clear_uncertain_work(self):
        for forced_request,damage in ((False,'damage_request_canary'),(True,'damage_request_canary'),
                                      (False,'damage_destructor_canary'),(True,'damage_destructor_canary')):
            with self.subTest(forced=forced_request,damage=damage):
                f=self.fixture();t=f.install();m=f.memory;setattr(m,damage,True)
                try:
                    with self.assertRaises(RuntimeError):t.request_end_turn(0,player_ids=(0,),user_forced=forced_request)
                    self.assertEqual(len(t.pending),1)
                    self.assertIn(('dtor',source.ABI.vector_dtor_rva if forced_request else source.ABI.tree_dtor_rva),m.calls)
                finally:f.close()
        f=self.fixture();t=f.install();m=f.memory
        m.bytes[m.base+source.ABI.reason_converter_rva+80]^=1
        with self.assertRaisesRegex(ValueError,'differs'):t.request_end_turn(0,player_ids=(0,),user_forced=True)
        self.assertEqual(t.pending,[])

    def test_unready_keeps_prior_archive_and_refuses_unknown_payload(self):
        f=self.fixture();t=f.install();m=f.memory
        t.capture(f.host.pointer,m.make_archive(b'earlier'))
        self.assertTrue(t.request_unready_turn(0,player_ids=(0,))['queued'])
        self.assertEqual(t.pending,[b'earlier',struct.pack('<II',0xE8A26B84,0)])
        m.unready_mode='none'
        self.assertFalse(t.request_unready_turn(0,player_ids=(0,))['queued'])
        m.unready_mode='invalid'
        with self.assertRaisesRegex(RuntimeError,'unexpected native archive'):t.request_unready_turn(0,player_ids=(0,))
        self.assertEqual(t.pending[-1],b'unknown-native-fixture')
        with self.assertRaises(ValueError):
            old_turn.turn_requests.request_unready_turn(t,0,player_ids=(0,),profile=profiles.XP1)

    def test_completion_validates_real_pending_archive_player_and_phase(self):
        f=self.fixture();t=f.install();m=f.memory
        flags=b'\1\1\0\0';m.put(m.base+source.ABI.processor_flags_rva,flags)
        for payload in (b'',struct.pack('<II',0x1BDB4F5C,1),struct.pack('<III',0xD7C02786,0,0)):
            t.pending[:]=[payload] if payload else []
            with self.assertRaises((RuntimeError,ValueError)):t.validate_completed_round_echo(0,player_ids=(0,))
            self.assertEqual(t.pending,[payload] if payload else [])
        t.pending.clear();payload=struct.pack('<II',0x1BDB4F5C,0)
        t.capture(f.host.pointer,m.make_archive(payload))
        self.assertEqual(t.validate_completed_round_echo(0,player_ids=(0,)),flags)
        for wrong in (b'\0'*4,b'\1\0\0\0',b'\1\1\1\0'):
            m.put(m.base+source.ABI.processor_flags_rva,wrong)
            with self.assertRaisesRegex(RuntimeError,'Late'):t.deliver_completed_round_echo(0,player_ids=(0,))
            self.assertEqual(t.pending,[payload])
        m.put(m.base+source.ABI.processor_flags_rva,flags)
        with self.assertRaisesRegex(ValueError,'continuation'):t.deliver_completed_round_echo(0,player_ids=(0,))
        self.assertEqual(t.pending,[payload])
        # Exercise shared primitive feedback without granting a session token.
        primitive=calls.NativeActionTransport.__new__(calls.NativeActionTransport)
        primitive.__dict__.update(t.__dict__)
        primitive.deliver_completed_round_echo(0,player_ids=(0,))
        self.assertEqual(t.pending,[])
        self.assertEqual(m.read(m.base+source.ABI.processor_flags_rva,4),flags)
        self.assertEqual(m.assertion,(m.context,0xFFFFFFFF,0))

    def test_real_thread_and_slot78_services_keep_actual_owner_and_native_abi(self):
        f=self.fixture();b=f.backend;h=f.host
        gate=thread_gate.install(b);receipt=slot78.install(b)
        self.assertIs(gate,b._xp1_thread_gate);self.assertEqual(gate.source_sha256,source.SOURCE[1])
        self.assertEqual(receipt['core_sha256'],XP2_CORE_SHA256)
        callbacks={slot:h._slot_bindings[C.addressof(h.vtable),slot][1] for slot in (0x58,0x60,0x78)}
        self.assertTrue(callbacks[0x60](h.pointer))
        f.kernel.GetCurrentThreadId.return_value=733
        self.assertFalse(callbacks[0x60](h.pointer));self.assertFalse(callbacks[0x58](h.pointer))
        self.assertFalse(gate.gate.activity_object_present);self.assertEqual(gate.gate.activity_count,0)
        for key in (0x4FC6296A,0x715C87D1):self.assertEqual(callbacks[0x78](h.pointer,key),0)
        for slot,fn in callbacks.items():
            with self.assertRaises(ValueError):fn(h.pointer+8,*((0,) if slot==0x78 else ()))
        for install in (thread_gate.install,slot78.install):
            with self.assertRaises(ValueError):install(b)
        with self.assertRaises(ValueError):HostThreadGate(511,PROFILE,activity_object_present=True)

    def test_host_services_refuse_foreign_engine_source_phase_and_rebinding(self):
        f=self.fixture();b=f.backend;m=f.memory;h=f.host
        for attr,value in (('busy',False),('prefix',object()),('poisoned',True),('stage','loaded')):
            old=getattr(b,attr);setattr(b,attr,value)
            for install in (thread_gate.install,slot78.install):
                with self.assertRaises((ValueError,RuntimeError)):install(b)
            setattr(b,attr,old)
        original=b.configuration_abi;b.configuration_abi=NS(core_sha256=XP1_CORE_SHA256)
        for install in (thread_gate.install,slot78.install):
            with self.assertRaises(ValueError):install(b)
        b.configuration_abi=original
        m.put(m.base+0xB8AA80,struct.pack('<Q',h.pointer+8))
        for install in (thread_gate.install,slot78.install):
            with self.assertRaisesRegex(ValueError,'owner'):install(b)
        m.put(m.base+0xB8AA80,struct.pack('<Q',h.pointer))
        for rva,install in ((0x59C20,thread_gate.install),(0x49E02,slot78.install)):
            m.bytes[m.base+rva]^=1
            with self.assertRaisesRegex(ValueError,'differs'):install(b)
            m.bytes[m.base+rva]^=1
        key=(C.addressof(h.vtable),0x78);before=h._slot_bindings[key]
        h._slot_bindings[key]=(before[0],lambda this,key:0)
        with self.assertRaisesRegex(ValueError,'callback'):slot78.install(b)
        self.assertFalse(hasattr(b,'_xp1_slot78'));self.assertFalse(hasattr(b,'_xp1_thread_gate'))

    def test_actual_composed_services_audit_checks_final_bindings_and_foreign_owner(self):
        f=self.fixture();b=f.backend;h=f.host;s=f.services
        thread_gate.install(b);slot78.install(b)
        s.closed=s.quarantined=False;b._xp1_commands_requested=True
        # Other already-qualified families are represented by retained callback
        # bindings, never invoked or semantically admitted by this table audit.
        def unavailable_fixture(*args):raise AssertionError('Unrelated fixture callback invoked')
        for interface,(name,slots) in slot78.REQUIRED.items():
            if not hasattr(h,name):setattr(h,name,(C.c_void_p*64)())
            table=getattr(h,name)
            for slot in slots:
                if interface=='host' and slot in (0x58,0x60,0x78):continue
                h._bind(table,slot,None,[C.c_void_p],unavailable_fixture)
        # The XP2 final audit also requires the explicitly installed optional
        # platform getter. Its real source/selector/installer has separate tests.
        h._bind(h.vtable,0x20,C.c_void_p,[C.c_void_p],unavailable_fixture)
        scalar_fn=C.CFUNCTYPE(None)(lambda:None);scalar_ptr=C.cast(scalar_fn,C.c_void_p).value
        s.scalars=h._scalar_service_owner=NS(host=h,closed=False,address=scalar_ptr,function=scalar_fn)
        h.aux_vtable[0xA0//8]=scalar_ptr
        bindings=[]
        for slot in (0xA8,0xB0):
            fn=C.CFUNCTYPE(None)(lambda:None);ptr=C.cast(fn,C.c_void_p).value
            bindings.append((slot,ptr,None,fn));h.aux_vtable[slot//8]=ptr
        s.maps=h._map_service_owner=NS(host=h,closed=False,bindings=bindings)
        result=slot78.require_composed_callbacks(b,s)
        self.assertEqual(result['core_sha256'],XP2_CORE_SHA256)
        self.assertFalse(result['semantic_qualification_inferred'])
        for slot in (0x20,0x58,0x60,0x78):
            key=(C.addressof(h.vtable),slot);previous=h._slot_bindings[key]
            h._bind(h.vtable,slot,None,[C.c_void_p],h._unsupported('host',slot))
            with self.assertRaisesRegex(ValueError,'unavailable'):slot78.require_composed_callbacks(b,s)
            h.vtable[slot//8]=previous[0];h._slot_bindings[key]=previous
        s.core=object()
        with self.assertRaisesRegex(ValueError,'foreign service'):slot78.require_composed_callbacks(b,s)
        s.core=b.core;h.aux_vtable[0xA8//8]+=8
        with self.assertRaisesRegex(ValueError,'map callback replaced'):slot78.require_composed_callbacks(b,s)


if __name__=='__main__':unittest.main(verbosity=2)

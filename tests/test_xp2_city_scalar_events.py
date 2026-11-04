"""Shared EXE city/scalar codec on actual expansion A0/FIFO owners; no DLL calls."""
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import a0_city_scalar_events as events
from civ6_host.runtime import city_scalar_event_profiles as profiles
from civ6_host.runtime import a0_family_source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
from test_deferred_service import Host


def fields(pointer,*,selector=0xffffffff,value=0xdeadbeef):
    scalar=lambda tag,n:struct.pack('<H6xQII',tag,n,0,0)
    return {0xa1e5a149:scalar(3,selector),0xd6fcf3e4:scalar(2,value),
            0x23739f42:struct.pack('<H6xQII',0x400,pointer,8,0x21000001)}


class Fixture:
    def __init__(self,test,core_sha256):
        self.stack=ExitStack();test.addCleanup(self.stack.close)
        self.reads=[];self.pointer=0x90123000;self.blob=struct.pack('<HHI',7,0xbeef,0x8000abcd)
        self.emitted=[];self.host=Host();self.original=list(self.host.vtable)
        self.bindings=dict(self.host._slot_bindings)
        self.core=NS(_handle=0x180000000)
        for name in ('cache_update_profiles.verify_dispatch_live','cache_update_profiles.verify_notification_live',
                     'event_argument_source.verify_host_live','event_argument_source.verify_reader_live'):
            self.stack.enter_context(patch('civ6_host.runtime.'+name,return_value={}))
        self.deferred=DeferredService(self.host,self.core,0x700000,core_sha256=core_sha256,
            read=self.read,emit=self.emit,optional_preprocessor=None,queue_metadata_service=None)
        self.arguments=EventArgumentService(self.host,self.core,0x700000,self.deferred,
            core_sha256=core_sha256,read=self.read,emit=self.emit,
            normalizer_transform=None,dynamic_registrations=())
        with patch.object(a0_family_source,'family_profile',return_value=test.shared_profile):
            self.owner=self.arguments.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
                pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE),entity_listener_count=0)

    def read(self,address,size):
        self.reads.append((address,size))
        if (address,size)!=(self.pointer,8):raise AssertionError('City/scalar codec made an unexpected Core read')
        return self.blob

    def emit(self,stage,**details):self.emitted.append((stage,details))

    def send(self,kind,values=None):
        with patch.object(self.arguments.reader,'fields',return_value=fields(self.pointer) if values is None else values):
            return self.arguments.dispatch(self.host.pointer,kind,0x881000)


class CityScalarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.shared_profile=a0_family_source.family_profile()

    def fixture(self,engine=XP2_CORE_SHA256,*,enable=True):
        f=Fixture(self,engine)
        if enable:events.enable(f.owner)
        return f

    def test_exact_source_membership_canonical_profiles_and_shared_receiver(self):
        p=profiles.source(core_sha256=XP2_CORE_SHA256)
        self.assertEqual(p['validation']['complete_retained_body_bytes'],12705)
        self.assertFalse(p['core_query_contract']['native_queries'])
        self.assertFalse(p['core_query_contract']['producer_reachability_qualified'])
        pins=profiles.source_dependencies(core_sha256=XP2_CORE_SHA256)
        self.assertIn(profiles.XP2_SOURCE[1],pins.values())
        self.assertIn(profiles.SOURCE[1],profiles.source_dependencies().values())
        self.assertNotIn(profiles.XP2_SOURCE[1],profiles.source_dependencies().values())
        for kind,record in profiles.NEW_KINDS.items():
            xp1=profiles.record_profile(kind);xp2=profiles.record_profile(kind,XP2_CORE_SHA256)
            self.assertEqual((xp1.record_type,xp2.record_type),(record,record))
            self.assertEqual(xp2.receiver_sha256,xp1.receiver_sha256)
            self.assertEqual(xp2.source_sha256,profiles.XP2_SOURCE[1])
            self.assertIs(profiles.require_record_profile(xp2),xp2)
            with self.assertRaises(ValueError):profiles.require_record_profile(replace(xp2))
        for engine in ('unknown','0'*64):
            with self.assertRaises(ValueError):profiles.source_dependencies(core_sha256=engine)
            with self.assertRaises(ValueError):profiles.record_profile(0x0242e68c,engine)

    def test_both_engines_three_records_exact_bytes_borrowed_copy_fifo_and_restore(self):
        for engine in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            with self.subTest(engine=engine):
                f=self.fixture(engine);d=f.deferred;expected=[]
                d.host_notification_counter=2;d.host_metadata_counter=9
                for sequence,(kind,record_type) in enumerate(profiles.NEW_KINDS.items(),1):
                    self.assertEqual(f.send(kind),0)
                    record=d.pending[-1];expected.append(record)
                    self.assertEqual(struct.unpack_from('<IIII',record),(112,record_type,sequence,0))
                    self.assertEqual(struct.unpack_from('<I',record,80)[0],sequence)
                    self.assertEqual(struct.unpack_from('<HHII',record,88),(7,2,0x8000abcd,0xdeadbeef))
                    self.assertEqual(record[84:88]+record[100:104],b'\0'*8)
                self.assertEqual(f.reads,[(f.pointer,8)]*3)
                f.blob=b'\xff'*8
                self.assertEqual(d.pending,expected)
                self.assertEqual((d.host_notification_counter,d.host_metadata_counter),(2,9))
                d.host_notification_counter=d.host_metadata_counter=0
                self.assertEqual(d.drain(),3);self.assertEqual(d.pending,[])
                self.assertEqual(d.consumed_digest.hexdigest(),hashlib.sha256(b''.join(expected)).hexdigest())
                f.arguments.close();d.close()
                self.assertEqual(list(f.host.vtable),f.original)
                self.assertEqual(f.host._slot_bindings,f.bindings)
                self.assertEqual([r['core_sha256'] for stage,r in f.emitted
                    if stage=='native_deferred_host_event_enqueued'],[engine]*3)

    def test_enable_refuses_nonidle_foreign_engine_and_duplicate(self):
        changes=(lambda f:setattr(f.deferred,'cache_core_sha256','unknown'),
            lambda f:setattr(f.arguments.reader,'core_sha256',XP1_CORE_SHA256),
            lambda f:f.deferred.pending.append(b'pending'),
            lambda f:setattr(f.arguments,'depth',1),
            lambda f:setattr(f.deferred,'host_notification_counter',1),
            lambda f:setattr(f.host,'_a0_family_owner',object()))
        for change in changes:
            f=self.fixture(enable=False);change(f)
            with self.assertRaises((ValueError,RuntimeError)):events.enable(f.owner)
            self.assertIsNone(f.owner.city_scalar_event_profile)
        f=self.fixture()
        with self.assertRaises(ValueError):events.enable(f.owner)

    def test_dispatch_refuses_engine_context_core_and_profile_replacement_before_read(self):
        changes=(lambda f:setattr(f.deferred,'cache_core_sha256',XP1_CORE_SHA256),
            lambda f:setattr(f.deferred,'context',0x777),
            lambda f:setattr(f.deferred,'core',NS(_handle=f.core._handle)),
            lambda f:setattr(f.owner,'_city_scalar_records',dict(f.owner._city_scalar_records)),
            lambda f:setattr(f.owner,'city_scalar_event_profile',replace(f.owner.city_scalar_event_profile)))
        for change in changes:
            f=self.fixture();change(f)
            with self.assertRaises((ValueError,RuntimeError)):f.send(0x0242e68c)
            self.assertEqual(f.reads,[]);self.assertEqual(f.deferred.pending,[])

    def test_unknown_kind_malformed_fields_and_bound_are_fatal_without_record(self):
        mutations=(lambda v:v.pop(0xd6fcf3e4),
            lambda v:v.update({0x11111111:b'\0'*24}),
            lambda v:v.update({0xd6fcf3e4:struct.pack('<H6xQII',3,7,0,0)}),
            lambda v:v.update({0x23739f42:struct.pack('<H6xQII',0x400,0,8,0x21000001)}))
        for change in mutations:
            f=self.fixture();v=fields(f.pointer);change(v)
            with self.assertRaises(ValueError):f.send(0x0242e68c,v)
            self.assertTrue(f.owner.quarantined);self.assertEqual(f.deferred.pending,[])
        f=self.fixture()
        with self.assertRaises((ValueError,RuntimeError)):f.send(0xdead1234)
        self.assertEqual(f.deferred.pending,[])
        f=self.fixture();f.deferred.limit=0
        with self.assertRaises(RuntimeError):f.send(0x0242e68c)
        self.assertEqual(f.reads,[]);self.assertTrue(f.owner.quarantined)

    def test_listener_change_preserves_pending_head_and_poisoned_drain(self):
        f=self.fixture();f.send(0x312df0f6);head=f.deferred.pending[0]
        f.owner.empty_receiver_state['subscriber_count']=1
        with self.assertRaises((ValueError,RuntimeError)):f.deferred.drain()
        self.assertIs(f.deferred.pending[0],head)
        self.assertEqual(f.deferred.consumed_count,0)
        self.assertTrue(f.deferred._deferred_drain_poisoned)

    def test_real_saved_load_host_controller_arguments_and_fifo_compose(self):
        import test_xp2_loaded_lifetime as fixture_module
        from civ6_host.runtime.native.native_host import DiagnosticHost
        from civ6_host.runtime.saved_load_services import SavedLoadServices
        fixture=fixture_module.RawLifetimeTests();self.addCleanup(fixture.doCleanups)
        backend=fixture.graph();services=backend.prefix;owner=services.event_arguments.consumer
        self.assertIs(type(backend.host),DiagnosticHost)
        self.assertIs(type(services),SavedLoadServices)
        events.enable(owner)
        descriptor=0x991234;fixture.f.put(descriptor,struct.pack('<HHI',1,2,65536))
        for kind in profiles.NEW_KINDS:
            with patch.object(services.event_arguments.reader,'fields',return_value=fields(descriptor)):
                self.assertEqual(services.event_arguments.dispatch(backend.host.pointer,kind,0x992000),0)
        self.assertEqual(services.deferred_events.drain(),3)
        self.assertEqual(services.deferred_events.consumed_count,3)
        self.assertIs(owner._city_scalar_binding.core,backend.core)
        self.assertIs(owner._city_scalar_binding.host,backend.host)


if __name__=='__main__':unittest.main()

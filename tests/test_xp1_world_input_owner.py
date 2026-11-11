"""One real saved owner, continuation, transport, publisher and A0/FIFO.

All game/Lua machine calls and process memory are explicit fixtures. Existing
owner guards and shared Python pipelines execute; no GameCore is loaded.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import struct
import sys
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1];LAB=HOST.parent/'civ6-rl-lab'
sys.path.insert(0,str(HOST/'tests'))
import test_xp1_turn_a0 as existing
from civ6_host.runtime import xp1_world_input as adapter
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import ACTIVE, READY
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
from civ6_host.runtime.native import native_player_view as view_calls
from civ6_host.runtime.native import native_action_transport as action_calls
from civ6_host.runtime.native import native_player_observation as observation_calls
from civ6_host.runtime.native import native_world_click as click
from civ6_host.runtime import action_transport_profiles, saved_load_job_observer as job


class Fixture(existing.Fixture):
    def __init__(self):
        existing.base_fixture.PROFILE=existing.base_fixture.a0_family_source.family_profile()
        with patch.object(existing.Memory,'base',0x180000000):
            super().__init__();self.memory.base=0x180000000;self.enable();self.activate()
        self.stack=ExitStack();self.regions=[];self.allocations=[];self.machine=[]
        import pefile
        from civ6_host.runtime.xp1_world_input_profile import verify_source
        self.pe=pefile.PE(verify_source()['image']['path'],fast_load=True)
        self.raw_read=self.memory.read
        self.memory.read=self.read
        self.owner.read=self.arguments.reader.read=self.read
        old=self.backend;b=OfficialLoadBackend.__new__(OfficialLoadBackend);b.__dict__.update(old.__dict__)
        self.backend=b;t=self.token;old_prefix=b.prefix
        p=SavedLoadServices.__new__(SavedLoadServices);p.__dict__.update(old_prefix.__dict__)
        b.prefix=p;p.backend=b;p.host=b.host;p.closed=p.quarantined=False
        b._saved_load_candidate=b._xp1_commands_requested=True
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        b.captured_bundle=PreparedBundle(REFERENCE,b.inputs,8,Path(verify_source()['image']['path']),{}, {}, {},
            dict(engine=dict(gamecore_sha256=b.load_abi.core_sha256)))
        p.core_sha256=b.load_abi.core_sha256
        # __new__ fixture: keep the constructor's explicit cache profile.
        self.deferred.cache_core_sha256=b.load_abi.core_sha256
        b.thread=(threading.get_ident(),1357);b.runtime=NS(thread=lambda:b.thread,read=self.read)
        b.raw_load_result={};b.loaded_readback=dict(width=8,height=8)
        t.owner=b;t.prefix=p;t.sequence=0;t.publication_count=0;t.publishing=False
        t.observation=dict(player_id=0,turn=8,width=8,height=8,units=[dict(id=17,x=0,y=0)])
        self.observation=deepcopy(t.observation);self.goal=None;self.route='request'
        self.move_on_drain = True
        self.goal_on_drain = 10
        for obj in (t.view,t.publication,t.lease,t.lease.attempt):obj.owner=b
        t.lease.prefix=p;t.lease.inputs=b.inputs
        self.host._saved_load_services=p;self.owner._foundation_backend=b
        p.runtime.registry._check=lambda:None
        p.runtime.evaluate_text=self.evaluate
        p.emit=b.emit=self.emit
        old_publisher=t.publisher
        publisher=NativePlayerViewPublisher.__new__(NativePlayerViewPublisher)
        publisher.__dict__.update(old_publisher.__dict__)
        publisher.read=self.read;publisher.emit=self.emit
        publisher.initialization_profile='public-cache-facade';publisher._owner_thread_id=threading.get_ident()
        t.publisher=p.view_publisher=t.lease.publisher=t.lease.attempt.publisher=publisher
        t.lease.backend.publication_owner=t.lease
        self._control_services(p)
        actions=SavedActionTransport.__new__(SavedActionTransport)
        actions.services=p;actions.backend=b;actions.closed=False
        actions.host=b.host;actions.core=b.core;actions.context=b.context;actions.read=self.read;actions.emit=self.emit
        actions.transport_abi=action_transport_profiles.verify_xp1(b.core._handle,b.context,self.read)
        actions.pending=[];actions.address=0x701070;self.host.vtable[0x70//8]=actions.address
        t.transport=p.actions=actions
        t.lease.tables=((self.host.vtable,tuple(self.host.vtable)),)
        self.sentinel=b.core._handle+actions.transport_abi.receive_queue_rva
        self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
        self.memory.put(b.core._handle+actions.transport_abi.processor_flags_rva,bytes(4))
        self.memory.put(b.core._handle+actions.transport_abi.optional_queue_flag_rva,b'\0')
        b.jobs=self.jobs
        saved=SavedLoadOwner.__new__(SavedLoadOwner)
        saved.thread=threading.get_ident();saved.backend=saved._backend=b
        saved._engine_sha256=b.load_abi.core_sha256;b._saved_stage_owner=saved
        saved.prefix=p;saved.core=b.core;saved.host=b.host;saved.context=b.context;saved.inputs=b.inputs
        saved.receipt=b.raw_load_result;saved.phase='commands';saved.poisoned=False;saved._running=True
        saved.requested={'unit_commands_candidate':True};saved.emit=self.emit
        saved.facade=saved.post=None;saved.publication=t.publication;saved.player_view=t.view;saved.continuation=t
        b.saved_load_publication_attempt=t.publication
        self.saved=saved;self.set_active(False)
        self.payload=b'explicit-native-archive-fixture'
        self.stack.enter_context(patch.object(C,'WINFUNCTYPE',self.factory))
        allocate=C.create_string_buffer
        def owned_buffer(*args):
            result=allocate(*args);self.allocations.append(result)
            self.regions.append((C.addressof(result),C.addressof(result)+C.sizeof(result)))
            return result
        self.stack.enter_context(patch.object(C,'create_string_buffer',owned_buffer))
        self.stack.enter_context(patch.object(action_calls,'virtual',self.virtual))
        self.stack.enter_context(patch.object(view_calls,'virtual',self.virtual))
        self.stack.enter_context(patch.object(observation_calls,'observe_player',self.observe_native))

    def _control_services(self,p):
        from civ6_host.runtime.control_input_service import ControlInputService
        from civ6_host.runtime.script_event_service import ScriptEventService
        from civ6_host.runtime.script_context_service import ScriptContextService
        from civ6_host.runtime.script_event_maps import MapArgumentFactory
        control=ControlInputService.__new__(ControlInputService)
        control.host=self.host;control.deferred=self.deferred;control.thread=threading.get_ident()
        control.closed=control.quarantined=False;control.addresses={};control.local_player_id=0
        control.turn_begin_state=object();control.code=NS(_check=lambda:None)
        self.host._control_input_owner=control;self.host.configured_local_player_id=0
        self.deferred.turn_begin_state=control.turn_begin_state
        self.owner.controller_owner=control;self.owner.turn_begin_state=control.turn_begin_state
        control._a0_event_owner=self.owner;p.control_inputs=control;p.event_arguments=self.arguments
        events=ScriptEventService.__new__(ScriptEventService)
        events.thread=threading.get_ident();events.closed=False;events.host=self.host;events.runtime=p.runtime
        events.dispatch_depth=0;events.script_arguments=NS(live_count=0)
        self.host._script_event_owner=events;p.events=events
        contexts=ScriptContextService.__new__(ScriptContextService)
        contexts.runtime=p.runtime;contexts.host=self.host;contexts.closed=contexts.quarantined=False
        contexts.registry=NS(paths=(),wire_paths=());contexts.paths=contexts.wire_paths=()
        contexts.receiver=31;contexts.depth=contexts.lock_depth=0
        self.host._script_context_service=contexts;p.contexts=contexts
        maps=MapArgumentFactory.__new__(MapArgumentFactory)
        maps.thread=threading.get_ident();maps.closed=maps.quarantined=False;maps.live={};p.map_arguments=maps

    def set_active(self,value):
        self.backend.busy=value;self.backend.stage=ACTIVE if value else READY
        self.saved._check_active() if value else self.saved._check_query()

    def read(self,address,size):
        for start,raw in self.memory.blocks.items():
            if start<=address and address+size<=start+len(raw):return raw[address-start:address-start+size]
        if any(lo<=address and address+size<=hi for lo,hi in self.regions):return C.string_at(address,size)
        rva=address-self.memory.base
        if 0<=rva and rva+size<=self.pe.OPTIONAL_HEADER.SizeOfImage:
            raw=self.pe.get_data(rva,size)
            if len(raw)==size:return raw
        return self.raw_read(address,size)

    def jobs(self):
        if not self.backend.busy or self.backend.snapshot_phase not in ('before','after'):
            raise AssertionError('Snapshot outside the actual active backend')
        return dict(schema=job.SCHEMA,profile=job.PROFILE,source_proof_sha256=job.SOURCE_HASH_BY_PROFILE[2],
            core_identity=dict(profile=2,sha256=self.backend.load_abi.core_sha256),
            stable_read=True,memory_modified=False,concurrent_scheduler_supported=False,
            native_introspection_only=True,native_methods_called=True,spawn_active=0,registry_lock_raw=0,
            pending_items=0,slots=[dict(handle=i,occupied=False,count=0,items=[]) for i in range(1,65)],
            groups=[],submission_sequence=0)

    def evaluate(self,child,source,name,**kwargs):
        if child is not self.token.ui_child:raise AssertionError('Wrong Lua child')
        if name==b'@world_input_own_units':return b'[{"unit_id":17,"ignore_moves":false}]'
        if name==b'@explicit_own_queued_orders':
            return json.dumps(dict(player_id=0,turn=8,width=8,height=8,
                units=[dict(unit_id=17,plot_id=self.goal)])).encode()
        if name==b'@explicit_own_queued_destination':return b'none' if self.goal is None else str(self.goal).encode()
        if name==b'@official_world_click':
            status=self.route
            if status=='request':
                self.token.transport.pending.append(self.payload)
                self.emit('native_command_archive_queued',archive_hex=self.payload.hex(),bytes=len(self.payload),delivery_pending=True)
            params=['MOVE_TO','19','x:101=2;y:102=1;modifiers:103=16400'] if status=='request' else ['-','-','-']
            return ','.join([status,'0','8','17','10','8','8',*params,'-','-',click._SOURCE_HASH]).encode()
        raise AssertionError('Unexpected Lua native read '+str(name))

    def observe_native(self,runtime,child,pid):
        if runtime is not self.token.runtime or child is not self.token.ui_child or pid!=0:
            raise AssertionError('Wrong player observation boundary')
        return deepcopy(self.observation)

    def factory(self,result,*args):
        a=self.token.transport.transport_abi;base=self.memory.base
        def bind(address):
            if address==base+a.view_ctor_rva:
                def ctor(ptr,data,size):
                    self.machine.append(('view_ctor',size));self.input_payload=C.string_at(data,size)
                    C.memmove(ptr,struct.pack('<Q',base+a.view_vtable_rva),8);return ptr
                return ctor
            if address==base+a.view_dtor_rva:return lambda ptr:self.machine.append(('view_dtor',))
            raise AssertionError('Unexpected native function '+hex(address-base))
        return bind

    def virtual(self,core,pointer,slot,rva,result,*args):
        a=self.token.transport.transport_abi;cache=self.token.publisher.cache_abi
        if core is not self.backend.core:raise AssertionError('Foreign Core')
        if rva==a.receive_rva:
            def receive(ctx,label,stream):
                self.machine.append(('receive',label));node,data=0x78000000,0x78001000
                self.memory.put(data,self.input_payload)
                self.memory.put(node,struct.pack('<QQI4xQQQ8x',self.sentinel,self.sentinel,label,
                    data,data+len(self.input_payload),data+len(self.input_payload)))
                self.memory.put(self.sentinel,struct.pack('<QQ',node,node))
            return receive
        if rva==a.drain_rva:
            def drain(ctx):
                self.machine.append(('drain',));self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
                from civ6_host.runtime.native import native_event_15c35863 as event
                fields=event.encode_fields(event.EventFields(0,19,0x78002000))
                self.memory.put(0x78002000,struct.pack('<HHI',0,1,17))
                self.owner.dispatch(event.KIND,fields,0)
                self.goal = self.goal_on_drain
                if self.move_on_drain:
                    self.observation['units'][0].update(x=2,y=1)
            return drain
        if rva==cache.service_ensure_rva:return lambda service:self.machine.append(('ensure',))
        if rva==cache.service_owner_rva:return lambda service:0x33000000
        if rva==0x4be760:return lambda ctx,descriptor,flag:self.machine.append(('publish',flag))
        raise AssertionError('Unexpected native virtual '+hex(rva))

    def close(self):self.stack.close();self.pe.close()


class WorldOwnerTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def select(self,f):
        result=adapter.read(f.saved,f.token.observation)
        self.assertEqual(result['actions'],[dict(kind='world_select_unit',unit_id=17)])
        f.set_active(True)
        result=adapter.apply(f.saved,dict(kind='world_select_unit',unit_id=17),f.token.observation)
        self.assertEqual(result['status'],'completed');self.assertFalse(result['receipt']['archive_delivered'])
        self.assertEqual(f.token.publication_count,0)
        f.token.sequence+=1;f.set_active(False)

    def test_same_owner_selection_move_real_transport_publisher_and_fifo(self):
        f=self.fixture();self.select(f)
        result=adapter.read(f.saved,f.token.observation)
        self.assertEqual(len(result['actions']),66)
        self.assertEqual(result['queued_orders']['units'],[dict(unit_id=17,plot_id=None)])
        f.set_active(True);action=dict(kind='world_plot_click',unit_id=17,plot_id=10,x=2,y=1)
        result=adapter.apply(f.saved,action,f.token.observation)
        self.assertEqual(result['status'],'completed');self.assertIsNone(result['refusal_code'])
        self.assertEqual(result['receipt']['archive_hex'],f.payload.hex())
        self.assertTrue(result['receipt']['archive_delivered']);self.assertEqual(f.token.publication_count,1)
        self.assertEqual(f.deferred.consumed_count,1);self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.token.transport.pending,[]);f.token.transport.require_empty_native_queue()
        self.assertEqual(result['receipt']['queued_destination_after'],dict(unit_present=True,plot_id=10))
        self.assertEqual([v for v in f.machine if v[0]=='publish'],[('publish',1)])
        self.assertIsNone(f.token._xp1_world_input_catalogue)
        f.token.observation=result['observation'];f.token.sequence+=1;f.set_active(False)
        self.assertEqual(adapter.read(f.saved,f.token.observation)['queued_orders']['units'],[dict(unit_id=17,plot_id=10)])

    def test_unsupported_is_refused_and_official_noop_completed_without_archive(self):
        for route,status in (('unsupported','refused'),('noop','completed')):
            with self.subTest(route=route):
                f=self.fixture();self.select(f);adapter.read(f.saved,f.token.observation);f.route=route
                f.set_active(True);action=dict(kind='world_plot_click',unit_id=17,plot_id=10,x=2,y=1)
                result=adapter.apply(f.saved,action,f.token.observation)
                self.assertEqual(result['status'],status)
                self.assertEqual(result['refusal_code'],'native_world_input_branch_unqualified' if status=='refused' else None)
                self.assertEqual(f.machine,[]);self.assertEqual(f.token.publication_count,0)
                self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
                self.assertEqual(result['observation'],f.token.observation)
                self.assertFalse(result['receipt']['archive_delivered'])
                f.close()

    def test_delivered_move_without_effect_requires_the_matching_native_queue(self):
        for goal, status in ((None, 'refused'), (9, 'refused'), (10, 'completed')):
            with self.subTest(goal=goal):
                f = self.fixture()
                self.select(f)
                adapter.read(f.saved, f.token.observation)
                f.move_on_drain = False
                f.goal_on_drain = goal
                f.set_active(True)
                action = dict(kind='world_plot_click', unit_id=17, plot_id=10, x=2, y=1)
                result = adapter.apply(f.saved, action, f.token.observation)
                self.assertEqual(result['status'], status)
                self.assertEqual(result['refusal_code'],
                                 'native_world_move_effect_unobserved' if status == 'refused' else None)
                self.assertTrue(result['receipt']['archive_delivered'])
                self.assertEqual(result['receipt']['queued_destination_after'], dict(unit_present=True, plot_id=goal))
                self.assertEqual(result['observation'], f.token.observation)
                self.assertEqual(f.token.publication_count, 1)
                f.close()

    def test_stale_episode_sequence_owner_and_cached_action_refused_before_native(self):
        for change in ('sequence','episode','owner','catalogue','action'):
            with self.subTest(change=change):
                f=self.fixture();adapter.read(f.saved,f.token.observation);f.set_active(True)
                action=dict(kind='world_select_unit',unit_id=17)
                if change=='sequence':f.token.sequence+=1
                elif change=='episode':
                    from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
                    from uuid import uuid4
                    value=str(uuid4());f.token.identity=DiagnosticEpisodeIdentity(value,'native-'+value)
                elif change=='owner':f.saved._backend=object()
                elif change=='catalogue':f.token.explicit_world_input['selected_unit_id']=17
                else:action['unit_id']=True
                with self.assertRaises((ValueError,RuntimeError)):
                    adapter.apply(f.saved,action,f.token.observation)
                self.assertEqual(f.machine,[]);self.assertEqual(f.token.transport.pending,[])
                f.close()

if __name__=='__main__':unittest.main()

"""Composed XP2 Save pipeline: real guards/owners, no GameCore execution.

Memory, OS/native calls and Lua execution are explicit fixture boundaries. The
serialized configuration and Game bytes are retained genuine streams, replayed
through the real bounded writer callbacks. This does not qualify native Save or
the fresh native Load of the resulting pair.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_xp2_turn_notifications as xp2_notifications
import test_xp2_cache_publication as xp2_cache
from test_xp1_world_input_owner import Fixture as XP1OwnerFixture, HOST, LAB
from civ6_host.runtime import xp1_session_checkpoint as checkpoint
from civ6_host.runtime import xp1_checkpoint_profile as save_profile
from civ6_host.runtime import xp1_load_capability as capability
from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime import action_transport_profiles
from civ6_host.runtime.configuration_profiles import configuration_abi, XP2_CORE_SHA256
from civ6_host.runtime.saved_load_profiles import profile_for_sha
from civ6_host.runtime.xp2_bundle_inputs import XP2_LAN_PROFILE, REFERENCE
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.xp1_continuation import READY, ACTIVE
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native.native_official_bundle import PreparedBundle
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.native.native_script_threads import ThreadRegistry, ScriptContext
from civ6_host.runtime.native.native_controller_code import NativeControllerCode
from civ6_host.runtime.native.native_events import NativeEventRecorder
from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.native import native_checkpoint_provider as provider
from civ6_host.runtime.native import native_checkpoint_stream as streams
from civ6_host.runtime.native.native_session_checkpoint import run_sequence

NATIVE_CALLBACK=C.WINFUNCTYPE
ABI=configuration_abi(XP2_CORE_SHA256)
INPUT_CONFIGURATION=(HOST/'work/xp2-bundle-inputs/configuration.bin',
    'e9f5cf20b75932169b5b1c8bdd800ce349a0cea99c755cc1ab1d099c64eaf116')
CONFIGURATION=(LAB/'work/native-xp2-configuration/run-20261102T092527Z-1fca62ada8ba/configuration-output.bin',
    '3075d816739ee63a86362e3fb46796394dd405d30f44b928baf4c9f1393958ef')
GAME=(LAB/'work/official-capture/xp2-gs-lan-rows-20261102-04/save-capture/48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430/section-02-00011980-gamecore_stream_candidate.raw',
    '66dd00e4e6f88e2ea2b87318a7b833ebeeed15f545ef050ccf6931f5c24cf3ee')


def retained(row):
    raw=row[0].read_bytes()
    if hashlib.sha256(raw).hexdigest()!=row[1]:raise ValueError('Retained fixture stream changed')
    return raw


class Fixture:
    """Extend the existing exact XP2 A0/cache/FIFO graph with real Save owners."""
    def __init__(self):
        self.stack=ExitStack();self.regions=[];self.allocations=[];self.machine=[];self.events=[]
        self.scope_seen=[];self.status=0;self.failure=None;self.human_active=True
        self.graph_case=xp2_notifications.XP2ComposedNotifications();self.stack.callback(self.graph_case.doCleanups)
        # The earlier cache-only fixture used a sub-64K outer pointer; Save's
        # exact native-memory guard deliberately refuses that address range.
        with patch.object(xp2_cache.XP1FixtureBackend,'outer',0x64000000):g=self.graph_case.graph()
        self.graph=g;self.memory=g.memory;self.owner=g.owner
        self.deferred=g.event.deferred;self.arguments=g.event.arguments;self.host=g.backend.host
        self.raw_read=self.memory.read
        from civ6_host.runtime.xp2_checkpoint_source import verify_source
        import pefile
        self.pe=pefile.PE(verify_source()[0]['image']['path'],fast_load=True)
        self.stack.callback(self.pe.close)
        allocate=C.create_string_buffer
        def owned_buffer(*args):
            result=allocate(*args);self.allocations.append(result)
            self.regions.append((C.addressof(result),C.addressof(result)+C.sizeof(result)))
            return result
        self.stack.enter_context(patch.object(C,'create_string_buffer',owned_buffer))
        self.memory.read=self.read;self.owner.read=self.arguments.reader.read=self.read
        old=g.backend;b=OfficialLoadBackend.__new__(OfficialLoadBackend);b.__dict__.update(old.__dict__)
        self.backend=b;t=self.token=g.continuation;p=self.prefix=g.prefix
        self.assert_type(p,SavedLoadServices)
        b.prefix=p;p.backend=b;p.core_sha256=XP2_CORE_SHA256;p.closed=p.quarantined=False
        b.profile=b.load_abi=profile_for_sha(XP2_CORE_SHA256);b.configuration_abi=ABI
        b.thread=(threading.get_ident(),1357);b.runtime=NS(thread=lambda:b.thread,read=self.read)
        b.core._name=verify_source()[0]['image']['path']
        b._saved_load_candidate=b._xp1_commands_requested=b._xp2_postload_requested=True
        b.inputs.profile=XP2_LAN_PROFILE;b.inputs.official_bundle=REFERENCE;b.inputs.checkpoint=None
        b.inputs.configuration=retained(INPUT_CONFIGURATION);b.inputs.game=retained(GAME)
        self.configuration=retained(CONFIGURATION);self.game=retained(GAME)
        b.reader.transport.cursor=len(b.inputs.game)
        b.captured_bundle=PreparedBundle(REFERENCE,b.inputs,1,Path(b.core._name),{}, {}, {},
            dict(engine=dict(gamecore_sha256=XP2_CORE_SHA256)))
        b.raw_load_result={};b.loaded_readback=dict(width=44,height=26,turn=1)
        b.streams=[];b.snapshot_phase='idle'
        t.owner=b;t.prefix=p;t.sequence=t.publication_count=0;t.publishing=False
        for obj in (t.view,t.publication,t.lease,t.lease.attempt):obj.owner=b
        t.lease.prefix=p;t.lease.inputs=b.inputs;self.host._saved_load_services=p
        self.owner._foundation_backend=b
        p.emit=b.emit=self.emit
        self.observation=dict(schema='civ6rl-player-observation-v1',player_id=0,turn=1,width=44,height=26,
            plots=[],visible_enemy_units=[],cities=[],units=[dict(id=17,type=1,x=0,y=0,damage=0,moves=2,max_moves=2,owner=0)],
            economy=dict(science=1,culture=1,gold=20,faith=0))
        t.observation=deepcopy(self.observation);self.decisions=dict(player_id=0,turn=1)
        t.world_input_prompts={};t.world_input_selections={0:17};t.explicit_placements={}
        self._script_runtime()
        XP1OwnerFixture._control_services(self,p)
        code=NativeControllerCode.__new__(NativeControllerCode)
        code.closed=code.poisoned=False;code.owner=threading.get_ident()
        p.control_inputs.code=code
        self._transport()
        inner=int.from_bytes(self.read(b.context+8,8),'little')
        self.memory.put(inner+0x50,struct.pack('<QQ',0x66001000,0x66002000))
        self.memory.q(self.memory.game,b.core._handle+b.load_abi.game_vtable_rva)
        self._configuration(inner)
        b.bound_identity=b.topology(game_required=True)
        self._native_save_owners(inner)
        self._scheduler()
        t.lease.script_runtime=p.runtime
        t.lease.tables=((self.host.vtable,tuple(self.host.vtable)),
            (self.host.aux_vtable,tuple(self.host.aux_vtable)),(self.host.logger_vtable,tuple(self.host.logger_vtable)))
        t.lease.bindings=dict(self.host._slot_bindings)
        t.publisher.read=self.read;t.lease.backend.read=self.read
        saved=SavedLoadOwner.__new__(SavedLoadOwner);self.saved=saved
        saved.thread=threading.get_ident();saved.backend=saved._backend=b;saved._engine_sha256=XP2_CORE_SHA256
        b._saved_stage_owner=saved;saved.prefix=p;saved.core=b.core;saved.host=b.host;saved.context=b.context;saved.inputs=b.inputs
        saved.receipt=b.raw_load_result;saved.phase='commands';saved.poisoned=saved._running=False
        saved.requested=dict(unit_commands_candidate=True,post160_candidate=True);saved.emit=self.emit
        saved.facade=saved.post=None;saved.publication=t.publication;saved.player_view=t.view;saved.continuation=t
        b.saved_load_publication_attempt=t.publication
        from civ6_host.runtime.lan_load import _LAN_MODE,_SIMULTANEOUS_PHASE
        saved.network_reference=dict(capture_manifest_sha256=REFERENCE[1],
            state=dict(player_id=0,observer_id=0,game_mode_u32=_LAN_MODE,turn_phase_u32=_SIMULTANEOUS_PHASE),
            major_player_ids=(0,1),human_player_ids=(0,))
        b.stage=READY;b.busy=False
        # The graph receipt belonged to its original configuration fixture.
        del b._xp1_capability_sources
        capability._bind_source_receipt(b)
        self.stack.enter_context(patch.object(C,'WINFUNCTYPE',self.factory))
        self.stack.enter_context(patch.object(streams,'LocalMemory',return_value=NS(read=self.read)))
        self.stack.enter_context(patch.object(provider,'_Runtime',return_value=self))
        self.output=LAB/'work/xp2-checkpoint-composition-tests'/str(uuid4());self.output.mkdir(parents=True)
        fixture_path=self.output/'fixture.json';fixture_path.write_text('{"fixture_only":true}',encoding='utf8')
        self.closure=dict(input_profile='xp2-lan',checkpoint_on_close=True,
            official_bundle=dict(path=REFERENCE[0],sha256=REFERENCE[1]),fixture=str(fixture_path),
            database_profile='offline-owner-composition')
        self.closure_path=self.output/'closure.json';self.closure_path.write_text(json.dumps(self.closure),encoding='utf8')
        saved._check('commands',requested='unit_commands_candidate');t.check(active=False)

    @staticmethod
    def assert_type(obj,kind):
        if type(obj) is not kind:raise TypeError('Fixture must retain actual '+kind.__name__)

    def emit(self,name,**value):self.events.append(dict(event=name,**value))

    def _script_runtime(self):
        p=self.prefix;t=self.token
        registry=ThreadRegistry.__new__(ThreadRegistry);registry.root=0x61000000
        registry.owner=threading.get_ident();registry.closed=False;registry._claims={};registry.lua={'gettop':lambda ptr:0}
        ui,game=ScriptContext(0x61001000),ScriptContext(0x61002000)
        registry.contexts={c.pointer:c for c in (ui,game)}
        runtime=NativeScriptRuntime.__new__(NativeScriptRuntime)
        runtime.registry=registry;runtime.root=registry.root;runtime.lua=registry.lua;runtime.closed=False
        runtime.service_owner=self.host;runtime.emit=self.emit
        def evaluate(pointer,source,length,name,out,capacity,written):
            name=C.string_at(name)
            if name==b'@lan_session_humans':
                assert pointer==game.pointer;raw=b'0=1|1=0'
            elif name==b'@lan_turn_activity':
                assert pointer==ui.pointer
                raw=b'1|0|0|0,1,1,0;1,0,0,0' if self.human_active else b'1|0|0|0,0,0,0;1,0,0,0'
            elif name==b'@native_player_observation':
                assert pointer==ui.pointer;raw=json.dumps(self.observation).encode()
            else:raise AssertionError('Unmodelled native Lua call '+str(name))
            assert len(raw)<=capacity;C.memmove(out,raw,len(raw))
            C.cast(written,C.POINTER(C.c_size_t))[0]=len(raw);return 0
        runtime.host=NS(LAB_ScriptEvaluateText=NATIVE_CALLBACK(C.c_int,C.c_void_p,C.c_char_p,C.c_size_t,
            C.c_char_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t))(evaluate))
        p.runtime=t.runtime=runtime;p.ui_child=t.ui_child=ui;p.game_child=t.game_child=game

    def _transport(self):
        b=self.backend;p=self.prefix;t=self.token
        actions=SavedActionTransport.__new__(SavedActionTransport)
        actions.services=p;actions.backend=b;actions.closed=False
        actions.host=b.host;actions.core=b.core;actions.context=b.context;actions.read=self.read;actions.emit=self.emit
        actions.transport_abi=action_transport_profiles.transport_profile(XP2_CORE_SHA256,b.core,b.context,self.read)
        actions.pending=[];actions.address=0x701070;self.host.vtable[0x70//8]=actions.address
        actions.recorder=NativeEventRecorder.__new__(NativeEventRecorder);self.host.event_recorder=actions.recorder
        self.stack.enter_context(patch.object(NativeEventRecorder,'_installed',actions.recorder))
        p.actions=t.transport=actions
        a=actions.transport_abi;self.sentinel=b.core._handle+a.receive_queue_rva
        self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
        self.memory.put(b.core._handle+a.processor_flags_rva,bytes(4))
        self.memory.put(b.core._handle+a.optional_queue_flag_rva,b'\0')

    def _configuration(self,inner):
        b=self.backend;base=b.core._handle
        o=app.NativeApplicationConfiguration.__new__(app.NativeApplicationConfiguration)
        o._configuration_abi=ABI;o.base=base;o.context=b.context;o.closed=False;o.call=None;o.emit=self.emit
        o.new_game_entered=False;o.read=self.read;o.source_provider=0x65000000
        o.storage=C.create_string_buffer(app.STORAGE_SIZE+32);o.pointer=C.addressof(o.storage)+16
        C.memmove(C.addressof(o.storage),app._GUARD,16);C.memmove(o.pointer+app.STORAGE_SIZE,app._GUARD,16)
        C.memmove(o.pointer,struct.pack('<Q',base+ABI.vtable_rva),8)
        self.providers={};proof=app.verify_source(core_sha256=XP2_CORE_SHA256)
        keys=(0x871d5b63,0x7dd11279,*(r['hash'] for r in proof['player_keys']))
        self.memory.put(base+ABI.root_key_rva,struct.pack('<I',keys[0]));self.memory.put(base+ABI.map_key_rva,struct.pack('<I',keys[1]))
        for index,key in enumerate(keys[2:]):self.memory.put(base+ABI.player_key_table_rva+index*0x44,struct.pack('<I',key))
        for which,pointer in enumerate((o.source_provider,o.pointer)):
            if which==0:self.memory.put(pointer,struct.pack('<Q',base+ABI.vtable_rva)+bytes(0x50))
            mapping={}
            for index,key in enumerate(keys):
                child=0x68000000+which*0x100000+index*0x100;variant=0x6a000000+which*0x100000+index*0x20
                self.memory.put(child,struct.pack('<Q',base+ABI.vtable_rva)+bytes(0x50))
                self.memory.put(variant,struct.pack('<H6xQ4xI',10,child,0x05000000));mapping[key]=variant
            self.providers[pointer]=mapping
        self.memory.put(inner+0xe00,struct.pack('<Q',o.source_provider))
        b.owner=b.host.application_configuration=b.core._civ6rl_application_configuration=o
        self.token.lease.configuration_owner=o

    def _native_save_owners(self,inner):
        base=self.backend.core._handle;game=int.from_bytes(self.read(inner+0x60,8),'little')
        self.rules,self.delegate,self.registry,self.notifications=0x6b000000,0x6b001000,0x6b002000,0x6b003000
        for address,value in ((base+0xb8b298,self.rules),(self.rules,base+0x9c1240),
            (base+0xb8e298,self.delegate),(self.delegate,base+0x9f31f0),
            (game+8,self.registry),(game+0x10,self.registry+0x120),(self.registry,self.notifications),
            (self.notifications,base+0xa45e48)):
            self.memory.q(address,value)
        self.memory.put(self.delegate+8,struct.pack('<I',17));self.memory.put(base+0xb60cd0,bytes(4))

    def _scheduler(self):
        b=self.backend;observer=jobs.SavedLoadJobObserver.__new__(jobs.SavedLoadJobObserver)
        hostbase=0x70000000;addresses={name:hostbase+0x1000+i*0x1000 for i,name in enumerate(jobs.ADDRESS_NAMES)}
        self.memory.put(hostbase+0x3c,struct.pack('<I',0x80));self.memory.put(hostbase+0x80,b'PE\0\0')
        self.memory.put(hostbase+0x80+24+56,struct.pack('<I',0x10000))
        table=addresses['slots'];self.memory.put(table,b''.join(struct.pack('<QQQB7x',0,table+i*32,table+(i+1)*32 if i<63 else 0,0) for i in range(64)))
        for name,address in addresses.items():
            if name=='slots':continue
            value=table if name=='free_head' else b.thread[1] if name=='runtime_thread' else 0
            self.memory.put(address,struct.pack('<I' if name in ('runtime_thread','spawn_active') else '<Q',value))
        words=(*jobs.LAYOUT_PREFIX,*addresses.values(),b.core._handle,3,0x536b00,0xf0,*jobs.LAYOUT_TAIL)
        def layout(out,count):
            assert count==28;self.scope_seen.append((b.stage,b.busy,b._xp1_capability_source_scope is b._xp1_capability_sources))
            for i,value in enumerate(words):out[i]=value
            return 0
        observer.backend=b;observer.busy=False;observer.last_snapshots={};observer.layout=layout
        observer.core=jobs._verify_core(b)
        observer.identity=dict(host_base=hostbase,os_thread_id=b.thread[1],executable_path=str(Path(__file__).resolve()))
        observer.build=dict(host_sha256='0'*64,fixture_only=True)
        observer.api=NS(main_module=lambda:hostbase,current_thread_id=lambda:b.thread[1],module_filename=lambda base:__file__)
        observer.layout_words=words;b.jobs=observer

    def read(self,address,size):
        if all(address+i in self.memory.memory for i in range(size)):return bytes(self.memory.memory[address+i] for i in range(size))
        if any(lo<=address and address+size<=hi for lo,hi in self.regions):return C.string_at(address,size)
        rva=address-self.memory.core_base
        if 0<=rva and rva+size<=self.pe.OPTIONAL_HEADER.SizeOfImage:
            raw=self.pe.get_data(rva,size)
            if len(raw)==size:return raw
        return self.raw_read(address,size)

    def factory(self,result,*args):
        def bind(target):
            if callable(target):return NATIVE_CALLBACK(result,*args)(target)
            b=self.backend;base=b.core._handle;abi=save_profile.save_abi(XP2_CORE_SHA256)
            if target==base+ABI.lookup_rva:return lambda pointer,key:self.providers.get(pointer,{}).get(key)
            if target==base+abi.initialized_rva:return lambda context:True
            if target==base+b.load_abi.game_initialized_rva:return lambda game:1
            if target==base+abi.outer_save_rva:
                def save(context,stream):
                    self.saved._check_active();assert b._xp1_capability_source_scope is b._xp1_capability_sources
                    self.machine.append(('save',));self.write_stream(stream,self.game)
                    if self.failure=='rules_drift':self.memory.put(self.delegate+8,struct.pack('<I',18))
                    if self.failure=='notifications_drift':
                        other=self.notifications+0x1000;self.memory.q(other,base+0xa45e48);self.memory.q(self.registry,other)
                    return self.status
                return save
            raise AssertionError('Unmodelled machine target '+hex(target-base))
        return bind

    def thread(self):return self.backend.runtime.thread()
    def image(self,base,proof):
        assert base==self.backend.core._handle and proof['images']['core']['sha256']==XP2_CORE_SHA256
        return proof['images']['core']['path']
    def invoke(self,address,pointer,stream,mode):
        assert mode=='writer' and pointer==self.backend.owner.pointer
        assert address==self.backend.core._handle+dict(ABI.codec_slots)[0x1f0]
        self.saved._check_active();self.machine.append(('configuration',));self.write_stream(stream,self.configuration)
    def write_stream(self,pointer,data):
        table=C.c_void_p.from_address(pointer).value
        write=NATIVE_CALLBACK(C.c_int32,C.c_void_p,C.c_void_p,C.c_uint64)(C.c_void_p.from_address(table+0x28).value)
        storage=C.create_string_buffer(data);assert write(pointer,C.addressof(storage),len(data))==0
    def consume_queue_notification(self):
        from civ6_host.runtime.native import native_event_92492f56 as event
        scalar=xp2_notifications.private_tests.fixture.scalar
        address=0x6c000000;self.memory.put(address,struct.pack('<HHI',0,2,5))
        fields={event.SELECTOR_KEY:scalar(3,0),
            event.DESCRIPTOR_KEY:struct.pack('<H6xQII',1024,address,8,553648129),
            event.D6_KEY:scalar(2,101),event.A1FBC_KEY:scalar(2,0)}
        b=self.backend
        with self.saved._attempt():
            b.stage,b.busy=ACTIVE,True
            with capability.capability_source_scope(b,'continuation'):
                assert self.owner.dispatch(event.EVENT_KIND,fields,0)==0
                assert len(self.deferred.pending)==1
                assert struct.unpack_from('<I',self.deferred.pending[0],4)[0]==98
                assert self.deferred.drain()==1
            b.stage,b.busy=READY,False;self.saved._finish('commands')
    def save(self):return checkpoint.save(self.saved,self.token.observation,self.decisions,self.closure,self.closure_path,5)
    def close(self):self.stack.close()


class XP2CheckpointCompositionTests(unittest.TestCase):
    def setUp(self):provider._STATES.clear();self.addCleanup(provider._STATES.clear)
    def fixture(self):
        f=Fixture.__new__(Fixture);self.addCleanup(f.close);f.__init__();return f

    def test_real_owner_codec_save_stream_publish_and_unchanged_boundary(self):
        f=self.fixture();before=deepcopy(f.token.observation);identity=(f.token.identity,f.token.sequence,f.token.publication_count)
        f.consume_queue_notification();self.assertEqual((f.deferred._sequence,f.deferred.consumed_count),(1,1))
        self.assertEqual(f.deferred.pending,[])
        result=f.save();b=f.backend
        self.assertEqual(f.machine,[('configuration',),('save',)])
        self.assertEqual((f.saved.phase,f.saved._running,b.stage,b.busy),('commands',False,READY,False))
        self.assertIsNone(b._xp1_capability_source_scope)
        self.assertTrue(f.scope_seen);self.assertTrue(all(row==(ACTIVE,True,True) for row in f.scope_seen))
        self.assertEqual(f.token.observation,before);self.assertEqual((f.token.identity,f.token.sequence,f.token.publication_count),identity)
        self.assertEqual(len(b.streams),1);self.assertTrue(b.streams[0].transport.closed)
        receipt=json.loads((f.output/'checkpoint-result-5.json').read_bytes())
        self.assertEqual(receipt['jobs_before'],receipt['jobs_after']);self.assertEqual(receipt['control_before'],receipt['control_after'])
        self.assertEqual(receipt['jobs_before']['core_identity']['profile'],3)
        m=json.loads((LAB/result['manifest']['path']).read_bytes())
        self.assertEqual(m['core_sha256'],XP2_CORE_SHA256);self.assertEqual(m['input_profile'],XP2_LAN_PROFILE.name)
        self.assertEqual(m['configuration_receipt']['proof_sha256'],ABI.codec_proof_sha256)
        self.assertEqual((LAB/m['components']['application_configuration']['path']).read_bytes(),f.configuration)
        self.assertEqual((LAB/m['components']['gamecore']['path']).read_bytes(),f.game)
        self.assertFalse(m['native_load_of_new_pair_validated']);self.assertEqual(m['host_world_selection'],17)
        save_identity=b.session_checkpoint_attempt.save_identity
        self.assertEqual((save_identity['xp2_rules'],save_identity['xp2_rules_delegate'],save_identity['xp2_notifications']),
            (f.rules,f.delegate,f.notifications));self.assertEqual(save_identity['xp2_rules_scalar'],17)
        with self.assertRaises(ValueError):f.save()
        with self.assertRaisesRegex(RuntimeError,'cannot be retried'):run_sequence(b.session_checkpoint_attempt,f.emit)

    def test_pending_foreign_reentrant_and_missing_owner_refuse_before_stream(self):
        for fault,message in (('pending','pending host/native work'),('native_pending','pending host/native work'),
            ('fifo_pending','fully consumed deferred queue'),('foreign','lost its original live backend graph'),
            ('reentrant','incomplete, active'),('rules','native rules owner differs'),('notifications','native Notifications owner')):
            with self.subTest(fault=fault):
                f=self.fixture()
                if fault=='pending':f.token.transport.pending.append(b'pending')
                elif fault=='native_pending':f.memory.q(f.sentinel,f.sentinel+0x100)
                elif fault=='fifo_pending':f.deferred.pending.append(bytes(112));f.deferred._sequence+=1
                elif fault=='foreign':f.saved._backend=object()
                elif fault=='reentrant':f.saved._running=True
                elif fault=='rules':f.memory.q(f.backend.core._handle+0xb8b298,0)
                else:f.memory.q(f.registry,0)
                with self.assertRaisesRegex((ValueError,RuntimeError),message):f.save()
                self.assertEqual(f.machine,[]);self.assertEqual(f.backend.streams,[])
                self.assertFalse((f.output/'checkpoint-result-5.json').exists())
                f.close()

    def test_native_rules_and_notifications_replacement_poison_and_close_stream(self):
        for fault in ('rules_drift','notifications_drift'):
            with self.subTest(fault=fault):
                f=self.fixture();f.failure=fault
                with self.assertRaisesRegex(RuntimeError,'changed retained identity'):f.save()
                self.assertTrue(f.saved.poisoned);self.assertTrue(f.backend.poisoned);self.assertTrue(f.prefix.quarantined)
                self.assertEqual(f.machine,[('configuration',),('save',)])
                self.assertTrue(f.backend.streams[0].transport.closed)
                self.assertIsNone(f.backend._xp1_capability_source_scope)
                self.assertFalse((f.output/'checkpoint-result-5.json').exists());f.close()


if __name__=='__main__':unittest.main()

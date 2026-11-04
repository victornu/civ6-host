"""Composed saved-session Save fixtures; no DLL or game process executes.

Retain SavedLoadOwner, SavedContinuation, source scope, human boundary, actual
control services, scheduler walker, provider codec, run_sequence and publish.
Only native memory, OS identities, Lua evaluation and machine calls are fixtures.
"""
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

from test_xp1_world_input_owner import Fixture as OwnerFixture, LAB
from civ6_host.runtime import xp1_session_checkpoint as checkpoint
from civ6_host.runtime import xp1_checkpoint_profile as save_profile
from civ6_host.runtime import xp1_load_capability as capability
from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime.configuration_profiles import configuration_abi, XP1_CORE_SHA256
from civ6_host.runtime.saved_load_profiles import profile_for_sha
from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.native import native_player_observation as observations
from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.native import native_checkpoint_provider as provider
from civ6_host.runtime.native import native_checkpoint_stream as streams
from civ6_host.runtime.native.native_session_checkpoint import run_sequence

NATIVE_CALLBACK=C.WINFUNCTYPE
OBSERVE=observations.observe_player
ABI=configuration_abi(XP1_CORE_SHA256)
CONFIGURATION=b'configuration-stream-fixture-not-native-format'
GAME=b'\x05\0\0\0game-stream-fixture-not-native-format'


class Fixture(OwnerFixture):
    def __init__(self):
        super().__init__()
        b=self.backend;p=b.prefix;t=self.token
        self.saved._running=False
        b.profile=b.load_abi=profile_for_sha(XP1_CORE_SHA256)
        b.inputs.profile=XP1_LAN_PROFILE;b.inputs.official_bundle=REFERENCE
        b.inputs.checkpoint=None;b.inputs.configuration=b'input-configuration-fixture'
        b.captured_bundle=NS(reference=REFERENCE,inputs=b.inputs)
        b.streams=[];b.snapshot_phase='idle'
        self.saved.network_reference=dict(capture_manifest_sha256=REFERENCE[1],
            state=dict(player_id=0,observer_id=0,game_mode_u32=3,turn_phase_u32=0),
            major_player_ids=(0,1),human_player_ids=(0,))
        from civ6_host.runtime.lan_load import _LAN_MODE,_SIMULTANEOUS_PHASE
        self.saved.network_reference['state'].update(game_mode_u32=_LAN_MODE,turn_phase_u32=_SIMULTANEOUS_PHASE)
        t.world_input_prompts={};t.world_input_selections={0:17};t.explicit_placements={}
        self.observation=dict(schema='civ6rl-player-observation-v1',player_id=0,turn=8,width=8,height=8,
            plots=[],visible_enemy_units=[],cities=[],units=[dict(id=17,type=1,x=0,y=0,damage=0,moves=2,max_moves=2,owner=0)],
            economy=dict(science=1,culture=1,gold=20,faith=0))
        t.observation=deepcopy(self.observation)
        self.decisions=dict(player_id=0,turn=8)
        self.status=0;self.human_active=True;self.failure=None;self.scope_seen=[]
        inner=int.from_bytes(self.read(b.context+8,8),'little')
        self.memory.put(inner,struct.pack('<Q',b.core._handle+b.load_abi.inner_vtable_rva))
        self.memory.put(inner+0x50,struct.pack('<QQ',0x66001000,0x66002000))
        game=int.from_bytes(self.read(inner+0x60,8),'little')
        self.memory.put(game,struct.pack('<Q',b.core._handle+b.load_abi.game_vtable_rva))
        self._configuration(inner)
        b.bound_identity=b.topology(game_required=True)
        self._scheduler()
        # All source/ownership validators execute. Only this OS-memory reader
        # and the native stream invocation are replaced by fixture functions.
        self.stack.enter_context(patch.object(streams,'LocalMemory',return_value=NS(read=self.read)))
        self.stack.enter_context(patch.object(provider,'_Runtime',return_value=self))
        self.stack.enter_context(patch.object(observations,'observe_player',OBSERVE))
        capability._bind_source_receipt(b)
        self.output=LAB/'work/xp1-checkpoint-owner-tests'/str(uuid4())
        self.output.mkdir(parents=True)
        self.fixture_path=self.output/'fixture.json'
        self.fixture_path.write_text('{"fixture_only":true}',encoding='utf8')
        self.closure=dict(input_profile='xp1-lan',checkpoint_on_close=True,
            official_bundle=dict(path=REFERENCE[0],sha256=REFERENCE[1]),
            fixture=str(self.fixture_path),database_profile='synthetic-owner-composition')
        self.closure_path=self.output/'closure.json'
        self.closure_path.write_text(json.dumps(self.closure),encoding='utf8')

    def _configuration(self,inner):
        b=self.backend;base=b.core._handle
        o=app.NativeApplicationConfiguration.__new__(app.NativeApplicationConfiguration)
        o._configuration_abi=ABI;o.base=base;o.context=b.context;o.closed=False;o.call=None;o.emit=None
        o.new_game_entered=False;o.read=self.read;o.source_provider=0x65000000
        o.storage=C.create_string_buffer(app.STORAGE_SIZE+32);o.pointer=C.addressof(o.storage)+16
        C.memmove(C.addressof(o.storage),app._GUARD,16)
        C.memmove(o.pointer+app.STORAGE_SIZE,app._GUARD,16)
        C.memmove(o.pointer,struct.pack('<Q',base+ABI.vtable_rva),8)
        self.providers={};proof=app.verify_source(core_sha256=XP1_CORE_SHA256)
        keys=(0x871d5b63,0x7dd11279,*(r['hash'] for r in proof['player_keys']))
        self.memory.put(base+ABI.root_key_rva,struct.pack('<I',keys[0]))
        self.memory.put(base+ABI.map_key_rva,struct.pack('<I',keys[1]))
        for index,key in enumerate(keys[2:]):self.memory.put(base+ABI.player_key_table_rva+index*0x44,struct.pack('<I',key))
        for which,pointer in enumerate((o.source_provider,o.pointer)):
            if which==0:self.memory.put(pointer,struct.pack('<Q',base+ABI.vtable_rva)+bytes(0x50))
            mapping={}
            for index,key in enumerate(keys):
                child=0x68000000+which*0x100000+index*0x100
                variant=0x6a000000+which*0x100000+index*0x20
                self.memory.put(child,struct.pack('<Q',base+ABI.vtable_rva)+bytes(0x50))
                self.memory.put(variant,struct.pack('<H6xQ4xI',10,child,0x05000000));mapping[key]=variant
            self.providers[pointer]=mapping
        self.memory.put(inner+0xd80+0x80,struct.pack('<Q',o.source_provider))
        b.owner=b.host.application_configuration=b.core._civ6rl_application_configuration=o
        self.token.lease.configuration_owner=o

    def _scheduler(self):
        """Actual observer/walker, with native introspection represented by bytes."""
        b=self.backend;observer=jobs.SavedLoadJobObserver.__new__(jobs.SavedLoadJobObserver)
        hostbase=0x70000000;addresses={name:hostbase+0x1000+i*0x1000 for i,name in enumerate(jobs.ADDRESS_NAMES)}
        self.memory.put(hostbase+0x3c,struct.pack('<I',0x80));self.memory.put(hostbase+0x80,b'PE\0\0')
        self.memory.put(hostbase+0x80+24+56,struct.pack('<I',0x10000))
        table=addresses['slots']
        self.memory.put(table,b''.join(struct.pack('<QQQB7x',0,table+i*32,table+(i+1)*32 if i<63 else 0,0) for i in range(64)))
        for name,address in addresses.items():
            if name=='slots':continue
            value=table if name=='free_head' else b.thread[1] if name=='runtime_thread' else 0
            self.memory.put(address,struct.pack('<I' if name in ('runtime_thread','spawn_active') else '<Q',value))
        words=(1,8,64,32,56,32,4848501265015980593,*addresses.values(),b.core._handle,2,0x465110,0xf0,0x1f00000000,0,8,16,24,40,48,16,24)
        def layout(out,count):
            assert count==28
            self.scope_seen.append((b.stage,b.busy,b._xp1_capability_source_scope is b._xp1_capability_sources))
            if self.failure=='jobs_after' and b.snapshot_phase=='after':raise RuntimeError('fixture scheduler changed')
            for i,value in enumerate(words):out[i]=value
            return 0
        observer.backend=b;observer.busy=False;observer.last_snapshots={};observer.layout=layout
        observer.core=dict(base=b.core._handle,sha256=XP1_CORE_SHA256,profile=2)
        observer.identity=dict(host_base=hostbase,os_thread_id=b.thread[1],executable_path=str(Path(__file__).resolve()))
        observer.build=dict(host_sha256='0'*64,fixture_only=True)
        observer.api=NS(main_module=lambda:hostbase,current_thread_id=lambda:b.thread[1],module_filename=lambda base:__file__)
        observer.layout_words=words;b.jobs=observer

    def evaluate(self,child,source,name,**kwargs):
        if name==b'@lan_session_humans':
            assert child is self.token.game_child;return b'0=1|1=0'
        assert child is self.token.ui_child
        if name==b'@lan_turn_activity':return b'8|0|0|0,1,1,0;1,0,0,0' if self.human_active else b'8|0|0|0,0,0,0;1,0,0,0'
        if name==b'@native_player_observation':return json.dumps(self.observation).encode()
        raise AssertionError('Unmodelled Lua call '+str(name))

    def factory(self,result,*args):
        def bind(target):
            if callable(target):return NATIVE_CALLBACK(result,*args)(target)
            base=self.backend.core._handle
            if target==base+ABI.lookup_rva:
                assert (result,args)==(C.c_void_p,(C.c_void_p,C.c_uint32))
                return lambda pointer,key:self.providers.get(pointer,{}).get(key)
            if target==base+save_profile.XP1.initialized_rva:return lambda context:True
            if target==base+self.backend.load_abi.game_initialized_rva:return lambda game:1
            if target==base+save_profile.XP1.outer_save_rva:
                def save(context,stream):
                    self.saved._check_active();assert self.backend._xp1_capability_source_scope is self.backend._xp1_capability_sources
                    self.machine.append(('save',));self.write_stream(stream,GAME)
                    if self.failure=='public_drift':self.observation['economy']['gold']+=1
                    return self.status
                return save
            raise AssertionError('Unmodelled machine target '+hex(target-base))
        return bind

    def thread(self):return self.backend.runtime.thread()
    def image(self,base,proof):
        assert base==self.backend.core._handle and proof['images']['core']['sha256']==XP1_CORE_SHA256
        return proof['images']['core']['path']
    def invoke(self,address,pointer,stream,mode):
        assert mode=='writer' and pointer==self.backend.owner.pointer
        assert address==self.backend.core._handle+dict(ABI.codec_slots)[0x1f0]
        self.saved._check_active();self.machine.append(('configuration',));self.write_stream(stream,CONFIGURATION)
    def write_stream(self,pointer,data):
        table=C.c_void_p.from_address(pointer).value
        write=NATIVE_CALLBACK(C.c_int32,C.c_void_p,C.c_void_p,C.c_uint64)(C.c_void_p.from_address(table+0x28).value)
        storage=C.create_string_buffer(data)
        assert write(pointer,C.addressof(storage),len(data))==0

    def save(self):return checkpoint.save(self.saved,self.token.observation,self.decisions,self.closure,self.closure_path,5)


class SessionCheckpointOwnerTests(unittest.TestCase):
    def setUp(self):provider._STATES.clear();self.addCleanup(provider._STATES.clear)
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_complete_shared_sequence_scope_public_boundary_codec_publish_and_ready(self):
        f=self.fixture();before=deepcopy(f.token.observation);result=f.save()
        self.assertEqual(f.machine,[('configuration',),('save',)])
        self.assertEqual(f.saved.phase,'commands');self.assertFalse(f.saved._running)
        self.assertFalse(f.backend.busy);self.assertEqual(f.backend.stage,'xp1-continuation-ready')
        self.assertIsNone(f.backend._xp1_capability_source_scope)
        self.assertTrue(f.scope_seen);self.assertTrue(all(row==('xp1-continuation-active',True,True) for row in f.scope_seen))
        self.assertEqual(f.token.observation,before);self.assertEqual((f.token.sequence,f.token.publication_count),(0,0))
        self.assertEqual(len(f.backend.streams),1);self.assertTrue(f.backend.streams[0].transport.closed)
        manifest=json.loads((LAB/result['manifest']['path']).read_bytes())
        self.assertEqual(manifest['core_sha256'],XP1_CORE_SHA256)
        self.assertEqual(manifest['input_profile'],XP1_LAN_PROFILE.name)
        self.assertEqual(manifest['host_world_selection'],17)
        self.assertEqual(manifest['configuration_receipt']['proof_sha256'],ABI.codec_proof_sha256)
        self.assertEqual((LAB/manifest['components']['application_configuration']['path']).read_bytes(),CONFIGURATION)
        self.assertEqual((LAB/manifest['components']['gamecore']['path']).read_bytes(),GAME)
        self.assertFalse(manifest['native_load_of_new_pair_validated'])
        self.assertTrue((f.output/'checkpoint-result-5.json').is_file())
        with self.assertRaises(ValueError):f.save()
        with self.assertRaisesRegex(RuntimeError,'cannot be retried'):
            run_sequence(f.backend.session_checkpoint_attempt,f.emit)
        self.assertEqual(f.machine,[('configuration',),('save',)])

    def test_foreign_owners_unready_boundary_and_open_queues_refuse_before_stream(self):
        for fault in ('publisher','episode','source_receipt','inactive','pending','prompt'):
            with self.subTest(fault=fault):
                f=self.fixture()
                if fault=='publisher':f.backend.prefix.view_publisher=object()
                elif fault=='episode':f.token.identity=object()
                elif fault=='source_receipt':f.backend._xp1_capability_sources=object()
                elif fault=='inactive':f.human_active=False
                elif fault=='pending':f.token.transport.pending.append(b'pending')
                else:f.token.world_input_prompts[0]=object()
                with self.assertRaises((ValueError,RuntimeError,AttributeError)):f.save()
                self.assertEqual(f.machine,[]);self.assertEqual(f.backend.streams,[])

    def test_status_public_drift_or_final_jobs_failure_poison_and_close_stream(self):
        for fault in ('status','public_drift','jobs_after'):
            with self.subTest(fault=fault):
                f=self.fixture()
                if fault=='status':f.status=False # Boolean zero is not native int32 success.
                else:f.failure=fault
                with self.assertRaises((ValueError,RuntimeError)):f.save()
                self.assertEqual(f.saved.phase,'poisoned');self.assertTrue(f.saved.poisoned)
                self.assertTrue(f.backend.poisoned);self.assertTrue(f.backend.prefix.quarantined)
                self.assertIsNone(f.backend._xp1_capability_source_scope)
                self.assertEqual(f.machine,[('configuration',),('save',)])
                self.assertTrue(f.backend.streams[0].transport.closed)
                self.assertFalse((f.output/'checkpoint-result-5.json').exists())
                with self.assertRaises(RuntimeError):f.save()


if __name__=='__main__':unittest.main()

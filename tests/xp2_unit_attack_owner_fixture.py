"""Real XP2 saved owner/continuation/transport/cache/FIFO; machine calls are fixtures."""
from contextlib import ExitStack
from copy import deepcopy
import ctypes as C
import json
from pathlib import Path
import struct
import threading
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch

import sys
from civ6_host.runtime.paths import resource_root
sys.path.append(str(resource_root()/'tools'))
from test_xp1_unit_attack_owner import Fixture as XP1AttackFixture
from test_xp1_world_input_owner import Fixture as WorldFixture
from test_xp2_turn_notifications import XP2ComposedNotifications
from test_session_capabilities import observation
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.xp1_continuation import READY, ACTIVE
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native import native_action_transport as action_calls
from civ6_host.runtime.native import native_player_view as view_calls
from civ6_host.runtime.native import native_saved_combat as shared
from civ6_host.runtime.native import native_player_observation as observation_calls


class Fixture:
    def __init__(self):
        self.stack=ExitStack();g=XP2ComposedNotifications().graph();self.graph=g
        self.memory=g.memory;self.memory.base=self.memory.core_base
        self.host=g.backend.host;self.owner=g.owner;self.arguments=g.event.arguments
        self.deferred=g.event.deferred;self.token=g.continuation
        self.machine=[];self.emitted=[];self.regions=[];self.allocations=[]
        self.payload=b'explicit-xp2-attack-fixture';self.goal=None
        self.attacks_left=1;self.no_effect=False;self.fail_after_receive=False
        self.selected_operation='RANGE_ATTACK';self.city_target=False;self.city_damage=0
        from extract_phase31_next_export import pefile
        from civ6_host.runtime import xp2_unit_attack_source as source
        self.pe=pefile.PE(source.verify_source()['image']['path'],fast_load=True)
        old=g.backend;b=OfficialLoadBackend.__new__(OfficialLoadBackend);b.__dict__.update(old.__dict__)
        b.core._name=source.verify_source()['image']['path']
        self.backend=g.backend=b;p=g.prefix;t=self.token
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
        b.captured_bundle=PreparedBundle(REFERENCE,b.inputs,8,Path(b.core._name),{}, {}, {},
            dict(engine=dict(gamecore_sha256=XP2_CORE_SHA256)))
        # The fixture rebases a verified composed graph onto its exact actual
        # OfficialLoadBackend type; derive a fresh receipt for that real owner.
        del b._xp1_capability_sources
        from civ6_host.runtime.xp1_load_capability import _bind_source_receipt
        _bind_source_receipt(b)
        b.jobs=self.jobs
        p.backend=b;t.owner=b
        for child in (t.publication,t.view,t.lease,t.lease.attempt):child.owner=b
        self.owner._foundation_backend=b
        b.raw_load_result={};b._xp2_postload_requested=True
        b.runtime.read=self.read
        self.owner.read=self.arguments.reader.read=self.read
        # Existing graph owns the XP2 cache/configuration; read falls back only
        # to exact on-disk image bytes for code and vtable fixtures.
        t.publisher.read=self.read;t.publisher.emit=self.emit
        t.publisher._owner_thread_id=threading.get_ident()
        p.runtime.evaluate_text=self.evaluate;p.runtime.registry._check=lambda:None
        p.core_sha256=XP2_CORE_SHA256;p.emit=b.emit=t.emit=self.emit
        self.host._saved_load_services=p
        WorldFixture._control_services(self,p)
        actions=SavedActionTransport.__new__(SavedActionTransport)
        actions.services=p;actions.backend=b;actions.closed=False
        actions.host=self.host;actions.core=b.core;actions.context=b.context;actions.read=self.read;actions.emit=self.emit
        from civ6_host.runtime.action_transport_profiles import transport_profile
        actions.transport_abi=transport_profile(XP2_CORE_SHA256,b.core,b.context,self.read)
        actions.pending=[];actions.address=0x701070;self.host.vtable[0x70//8]=actions.address
        from civ6_host.runtime.native.native_events import NativeEventRecorder
        actions.recorder=NativeEventRecorder.__new__(NativeEventRecorder)
        self.host.event_recorder=actions.recorder
        self.stack.enter_context(patch.object(NativeEventRecorder,'_installed',actions.recorder))
        t.transport=p.actions=actions
        t.lease.tables=tuple((table,tuple(table)) for table in (self.host.vtable,self.host.aux_vtable,self.host.logger_vtable))
        self.sentinel=b.core._handle+actions.transport_abi.receive_queue_rva
        self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
        self.memory.put(b.core._handle+actions.transport_abi.processor_flags_rva,bytes(4))
        self.memory.put(b.core._handle+actions.transport_abi.optional_queue_flag_rva,b'\0')
        # Independent source-selected UI receipt, no XP1 callback identity reuse.
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        t.unit_source=verify_live(b.core._handle,self.read,core_sha256=XP2_CORE_SHA256)
        t.sequence=t.publication_count=0;t.publishing=False
        t.explicit_combat_units=t.explicit_combat_cities=t._xp1_unit_attack_catalogue=None
        obs=observation();obs['turn']=8;obs['width']=74;obs['height']=46
        obs['units'][0].update(x=0,y=0,type=1)
        obs['plots']=[dict(index=1,x=1,y=0,visible=True,revealed=True,owner=1,
            terrain_type=0,feature_type=-1,water=False,impassable=False)]
        obs['visible_enemy_units']=[dict(owner=1,id=27,type=2,x=1,y=0,damage=0,visible=True)]
        self.observation=deepcopy(obs);t.observation=deepcopy(obs)
        saved=SavedLoadOwner.__new__(SavedLoadOwner)
        saved.thread=threading.get_ident();saved.backend=saved._backend=b
        saved._engine_sha256=XP2_CORE_SHA256;b._saved_stage_owner=saved
        saved.prefix=p;saved.core=b.core;saved.host=self.host;saved.context=b.context;saved.inputs=b.inputs
        saved.receipt=b.raw_load_result;saved.phase='commands';saved.poisoned=False;saved._running=True
        saved.requested=dict(unit_commands_candidate=True,post160_candidate=True);saved.emit=self.emit
        saved.facade=saved.post=None;saved.publication=t.publication;saved.player_view=t.view;saved.continuation=t
        b.saved_load_publication_attempt=t.publication
        self.saved=saved
        allocate=C.create_string_buffer
        def buffer(*args):
            result=allocate(*args);self.allocations.append(result)
            self.regions.append((C.addressof(result),C.addressof(result)+C.sizeof(result)))
            return result
        self.stack.enter_context(patch.object(C,'create_string_buffer',buffer))
        self.stack.enter_context(patch.object(C,'WINFUNCTYPE',self.factory))
        self.stack.enter_context(patch.object(action_calls,'virtual',self.virtual))
        self.stack.enter_context(patch.object(view_calls,'virtual',self.virtual))
        self.stack.enter_context(patch.object(shared,'observe_player',self.observe_native))
        self.stack.enter_context(patch.object(observation_calls,'observe_player',self.observe_native))
        self.set_active(False)

    def read(self,address,size):
        if all(address+i in self.memory.memory for i in range(size)):
            return self.memory.read(address,size)
        if any(lo<=address and address+size<=hi for lo,hi in self.regions):return C.string_at(address,size)
        rva=address-self.memory.core_base
        if 0<=rva and rva+size<=self.pe.OPTIONAL_HEADER.SizeOfImage:
            return self.pe.get_data(rva,size)
        return self.memory.read(address,size)

    def emit(self,stage,**payload):self.emitted.append((stage,deepcopy(payload)))
    set_active=WorldFixture.set_active
    units=XP1AttackFixture.units
    observe_native=WorldFixture.observe_native
    factory=WorldFixture.factory

    def jobs(self):
        from civ6_host.runtime import saved_load_job_observer as job
        value=WorldFixture.jobs(self)
        value['source_proof_sha256']=job.SOURCE_HASH_BY_PROFILE[3]
        value['core_identity']['profile']=3
        return value

    def evaluate(self,child,source,name,**kw):
        if child is not self.token.ui_child:raise AssertionError('XP2 attack query uses foreign UI child')
        if name==b'@explicit_combat_catalog':
            rows=[] if self.city_target else [dict(unit_id=17,operation=self.selected_operation,target_owner=1,target_id=27,x=1,y=0)]
            return json.dumps(dict(schema='civ6rl-combat-candidates-v1',player_id=0,turn=8,width=74,height=46,candidates=rows)).encode()
        if name==b'@explicit_visible_city_targets':
            cities=[] if not self.city_target else [dict(owner=1,city_id=77,district_id=78,plot_id=1,x=1,y=0,
                garrison_damage=self.city_damage,garrison_max=200,outer_damage=0,outer_max=100,defense_strength=20.5)]
            rows=[] if not self.city_target or b'if false then' in source else [dict(unit_id=17,operation='RANGE_ATTACK',input_route='dedicated_ranged',target_owner=1,target_id=77,x=1,y=0)]
            return json.dumps(dict(player_id=0,turn=8,width=74,height=46,cities=cities,candidates=rows)).encode()
        if name==b'@explicit_visible_combat_diplomacy':return b'[{"owner":1,"at_war":true}]'
        if name==b'@explicit_combat_units':return json.dumps(dict(player_id=0,turn=8,units=self.units())).encode()
        if name==b'@explicit_unit_attack_request':
            self.token.transport.pending.append(self.payload)
            self.emit('native_command_archive_queued',archive_hex=self.payload.hex(),bytes=len(self.payload),delivery_pending=True)
            return b'submitted'
        if name==b'@explicit_own_queued_orders':
            return json.dumps(dict(player_id=0,turn=8,width=74,height=46,units=[dict(unit_id=17,plot_id=self.goal)])).encode()
        if name==b'@explicit_own_queued_destination':return b'none' if self.goal is None else str(self.goal).encode()
        raise AssertionError('Unexpected XP2 attack Lua operation '+repr(name))

    def virtual(self,core,pointer,slot,rva,result,*args):
        if core is not self.backend.core:raise AssertionError('Foreign XP2 Core')
        if rva==self.token.transport.transport_abi.drain_rva:
            def drain(ctx):
                self.machine.append(('drain',))
                if self.fail_after_receive:raise RuntimeError('fixture native XP2 combat did not return')
                self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
                # The existing complete deferred FIFO owns this real record;
                # native event generation is the machine fixture boundary.
                from civ6_host.runtime.native import native_event_15c35863 as event
                self.memory.put(0x78002000,struct.pack('<HHI',0,1,17))
                self.owner.dispatch(event.KIND,event.encode_fields(event.EventFields(0,19,0x78002000)),0)
                if not self.no_effect:
                    self.observation['units'][0]['moves']=1;self.attacks_left=0
                    if self.city_target:self.city_damage=20
                    else:self.observation['visible_enemy_units'][0]['damage']=20
            return drain
        cache=self.token.publisher.cache_abi
        if rva==cache.service_owner_rva:return lambda service:self.memory.owner
        if rva==0x591930:return lambda ctx,descriptor,flag:self.machine.append(('publish',flag))
        return WorldFixture.virtual(self,core,pointer,slot,rva,result,*args)

    def prepare(self):
        from civ6_host.runtime.xp1_unit_attacks import read
        self.saved._running=True;self.set_active(False)
        return read(self.saved,self.token.observation)

    def install_maps(self):
        """Compose the actual A8/B0 service and adapter on this saved owner.

        The exported C/HKS bridge is a function-pointer fixture. Its Python
        callback, native map decoder, owned buffer and child guards are real.
        """
        from civ6_host.runtime.script_map_service import MapService
        from test_xp2_aux_maps import memory,add_map,retained,evaluate
        fields={7:retained.scalar(3,1)};mem=memory({});pointer=0xd00000
        add_map(mem,pointer,fields)
        from civ6_host.runtime.aux_map_profiles import profile_for_sha
        struct.pack_into('<Q',mem.parts[pointer],0,self.backend.core._handle+profile_for_sha(XP2_CORE_SHA256).vtable_rva)
        for address,raw in mem.parts.items():
            if pointer<=address<pointer+0x10000:self.memory.put(address,raw)
        runtime=self.token.runtime;registry=runtime.registry;child=self.token.ui_child;state=0x720000
        registry.contexts={state:child,0x720100:self.token.game_child}
        registry.validate=lambda value:next(key for key,row in registry.contexts.items() if row is value)
        self.host.emit=self.emit
        installed={};results=[]
        def install(owner,callback):installed['callback']=callback;return 1
        runtime.host.LAB_AuxMapInstall=Mock(side_effect=install)
        runtime.host.LAB_AuxMapTransportVersion=Mock(return_value=2)
        def push(aux,hks,map_pointer,names):
            output=C.c_void_p();count=C.c_uint32()
            ok=installed['callback'](aux,hks,map_pointer,names,C.pointer(output),C.pointer(count))
            results.append((ok,evaluate(C.string_at(output.value,count.value*16)) if ok else None))
        callback_type=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_void_p,C.c_uint8)
        runtime.host.LAB_AuxPushMap=callback_type(push)
        runtime.host.LAB_AuxPushOptionalMap=callback_type(push)
        p=self.token.prefix;p.maps=MapService(self.host,runtime,self.backend.core,
            core_sha256=XP2_CORE_SHA256,read=self.read)
        self.token.lease.tables=tuple((table,tuple(table)) for table in
            (self.host.vtable,self.host.aux_vtable,self.host.logger_vtable))
        def invoke(hks=state):
            target=C.cast(self.host.aux_vtable[0xa8//8],callback_type)
            target(C.addressof(self.host.aux_object),hks,pointer,0)
            return results[-1]
        return p.maps,invoke

    def execute_attack(self):
        choice=self.prepare()['actions'][0]
        self.saved._running=False
        self.last_transition=self.saved.execute(choice)
        return self.last_transition['effect']

    def close(self):
        self.stack.close();self.pe.close()

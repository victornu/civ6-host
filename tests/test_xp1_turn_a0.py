"""Actual A0 owner/borrow/dispatcher/FIFO tests; no engine process.

Native machine calls and application/configuration queries are explicit fixture
boundaries. Shared query bodies, encoders, owner guards and consumption execute.
"""
import ast
from contextlib import ExitStack
import ctypes as C
import inspect
import threading
from pathlib import Path
import struct
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOST/'work/xp1-action-integration/transport-tests'))
import test_found_unit_a0 as base_fixture
from test_xp1_turn_units import Memory
from civ6_host.runtime import a0_foundation_events as events
from civ6_host.runtime import turn_unit_event_profile as profile
from civ6_host.runtime import xp1_visibility_cache_gate as cache
from civ6_host.runtime.xp1_continuation import SavedContinuation, ACTIVE
from civ6_host.runtime.a0_family_service import A0FamilyService
from civ6_host.runtime.native.native_episode_identity import initialize_episode
from civ6_host.runtime.native import native_host_events as shared
from civ6_host.runtime.native import native_app_ownership as app_mode
from civ6_host.runtime.native import native_event_a625c726 as improvement
from civ6_host.runtime.native import native_unit_created_event as created

scalar=base_fixture.scalar


class Fixture(base_fixture.Fixture):
    def __init__(self):
        super().__init__()
        self.memory=Memory(profile.TABLES);self.native_calls=[]
        self.owner.read=self.arguments.reader.read=self.memory.read
        self.deferred.base=self.deferred.core._handle=self.memory.base
        self.deferred.context=self.memory.objects['outer']
        self.host.filters=NS(entries={0xc50d66d6:[(0xf0548bb7,1)]})
        self.host.configured_player_identity_hashes={1:0x1234}
        self.app=NS(require_context=self.require_context)
        self.deferred.core._civ6rl_application_configuration=self.app
        self.backend=NS(check_thread=lambda:None,stage='prepared',prefix=None,_xp1_commands_requested=True,
            load_abi=NS(core_sha256=profile.XP1_CORE_SHA256),host=self.host,
            core=self.deferred.core,context=self.deferred.context,owner=self.app)
        foundation=NS(record_types_by_kind={},record_sizes={})
        self.owner.foundation_event_profile=self.owner._foundation_event_profile=foundation
        self.owner._foundation_backend=self.backend
        self.memory.put(self.memory.objects['unit']+8,(0x30000000).to_bytes(8,'little'))
        for address,text in ((0x600000,b'UNIT_A\0'),(0x600100,b'UNIT_B\0'),(0x600200,b'CIV_A\0')):
            self.memory.put(address,text)
        self.pointer_cursor=0x70000000
    def require_context(self,base,context):
        if (base,context)!=(self.memory.base,self.deferred.context):raise AssertionError('application context changed')
    def enable(self):
        with patch.object(profile,'bind_owner',return_value='offline-code-guard-boundary'):
            return events.enable_turn_units(self.owner,self.backend)
    def activate(self):
        # Build the exact retained object graph consumed by SavedContinuation.check.
        b=self.backend;t=SavedContinuation.__new__(SavedContinuation)
        prefix=NS();runtime=NS(registry=NS(validate=lambda child:None),service_owner=b.host);ui=object();game=object()
        publisher=NS();transport=NS(backend=b)
        from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
        from civ6_host.runtime import cache_facade_profiles as cp
        from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi
        lease=LoadedCachePublication.__new__(LoadedCachePublication)
        lease.owner=b;lease.prefix=prefix;lease.publication_finished=True
        publication=NS(owner=b,lease=lease,completed=True)
        view=NS(owner=b,publication=publication,completed=True)
        prefix.runtime=runtime;prefix.ui_child=ui;prefix.game_child=game
        prefix.actions=transport;prefix.view_publisher=publisher
        prefix.core=b.core;prefix.context=b.context;prefix.deferred_events=self.deferred
        prefix.configuration_readback_verified=True;prefix.check=self.arguments._check
        b.prefix=prefix;b.destroyed=b.poisoned=False;b.busy=True;b.stage=ACTIVE
        b.runtime=NS(read=self.memory.read);b.inputs=NS(game=b'loaded')
        b.reader=NS(transport=NS(closed=True,cursor=len(b.inputs.game)))
        b.host._saved_load_services=prefix;b.host._slot_bindings={}
        b.host.pointer=0x50000000;b.host.aux_object=C.c_void_p();b.host.logger_object=C.c_void_p()
        for rva,pointer in ((0x9f2640,b.host.pointer),(0x9f2648,C.addressof(b.host.aux_object)),
                            (0x9f2650,C.addressof(b.host.logger_object))):
            self.memory.put(self.memory.base+rva,struct.pack('<Q',pointer))
        # Native loaded-cache bytes are explicit fixtures; all lease and cache
        # ownership validators remain the real implementations.
        a=loaded_cache_abi(profile.XP1_CORE_SHA256);layout=cp.source()['profile'];own=layout['ownership']
        inner,service,owner,live_game,member=(0x31000000,0x32000000,0x33000000,0x34000000,0x35000000)
        q=lambda address,value:self.memory.put(address,struct.pack('<Q',value))
        base=self.memory.base
        for address,value in ((b.context+8,inner),(base+0x9f2620,inner),(inner,base+0x8d7168),
                (inner+0x1a68,service),(base+a.service_global_rva,service),(service,base+a.service_vtable_rva),
                (service+8,owner),(owner,base+a.cache_owner_vtable_rva),(owner+0x20,service),
                (inner+0x60,live_game),(base+a.game_global_rva,live_game),
                (owner+own['owner_cache_member_offset'],member),(member,base+own['cache_member_vtable_rva']),
                (member+own['cache_member_owner_offset'],owner),(owner+0x58,0x36000000),
                (owner+a.map_view_offset,member)):
            q(address,value)
        for slot,target in ((8,a.service_ensure_rva),(0x80,a.service_owner_rva),(0xa8,a.service_publish_rva)):
            q(base+a.service_vtable_rva+slot,base+target)
        self.memory.put(owner+0x38,b'\1');self.memory.put(live_game+0x2a4,b'\1')
        copied=struct.pack('<iii',8,8,64)+bytes(16);self.memory.put(member+0x28,copied)
        identity=cp.context_state(base,b.context,self.memory.read);b.bound_identity=identity
        b.loaded_readback=dict(width=8,height=8)
        facade_backend=NS(core_base=base,publication_owner=lease,context_alive=lambda:True)
        facades=NS(backend=facade_backend,_closed=False,outer=b.context,abi=cp.facade_abi(profile.XP1_CORE_SHA256))
        for i,(field,vt,identity_key) in enumerate((('game_facade','game_facade_vtable_rva','owner'),
                ('cache_service','cache_service_vtable_rva','member'),('system_facade','system_facade_vtable_rva','system_member'),
                ('cache_b0_result','cache_b0_result_vtable_rva','b0_result_owner'),
                ('cache_c0_result','cache_c0_result_vtable_rva','c0_result_owner'))):
            ptr=0x40000000+i*0x1000;setattr(facades,field,ptr)
            self.memory.put(ptr,struct.pack('<QQQI',base+layout[vt],0,identity[identity_key],1)+bytes(4))
        publisher.cache_abi=a;publisher._closed=False;publisher.context=b.context;publisher.core=b.core
        publisher.native_cache_gate=publisher.full_facade_initialization_reproduced=False
        publisher._facades=facades;publisher.cache_map_snapshot=copied
        lease.core=b.core;lease.core_sha256=profile.XP1_CORE_SHA256
        lease.host=b.host;lease.script_runtime=runtime;lease.configuration_owner=self.app
        lease.thread=threading.get_ident();lease.inputs=b.inputs;lease.identity=identity;lease.publisher=publisher
        lease.backend=facade_backend;lease.entered=lease.returned=lease.copied=True;lease.poisoned=False
        lease.attempt=NS(owner=b,publication_mode='candidate',cache_abi=a,publisher=publisher)
        lease.tables=((b.host.vtable,tuple(b.host.vtable)),);lease.bindings={}
        b._xp1_continuation=t;b._xp1_player_view=view
        publisher._xp1_continuation=t;lease.continuation=t;lease.publication_attempt=publication
        t.owner=b;t.prefix=prefix;t.runtime=runtime;t.ui_child=ui;t.game_child=game
        t.transport=transport;t.publisher=publisher;t.view=view;t.publication=publication;t.lease=lease
        t.poisoned=False;t.identity=initialize_episode(prefix);t.check(active=True)
        self.token=t
    def make_blob(self,raw,tag=0):
        pointer=self.pointer_cursor;self.pointer_cursor+=0x100
        self.memory.put(pointer,raw)
        value=bytearray(24);struct.pack_into('<H',value,0,tag)
        struct.pack_into('<QII',value,8,pointer,8,553648129);return bytes(value)
    def event_fields(self,kind):
        descriptor=self.make_blob(struct.pack('<HHI',1,1,9),1024)
        if kind==0xc50d66d6:
            return {0xa1e5a149:scalar(3,0),0xd6fcf3e4:scalar(4,0x3fc00000),0xf0548bb7:descriptor}
        position=self.make_blob(struct.pack('<ii',3,4),13 if kind==0xb8515a41 else 0)
        if kind==0xb8515a41:
            return {0xa1e5a149:scalar(3,0),0xd6fcf3e4:scalar(2,0),0xf0548bb7:descriptor,
                0x8c468e3c:position,0xa1fbc372:scalar(2,8),0x15808e44:scalar(3,0),0x6e3a8f43:scalar(1,0)}
        if kind==0x6e7ef927:
            return {0xa1e5a149:scalar(3,0),0xf0548bb7:descriptor,0x8c468e3c:position}
        return {0xa1e5a149:scalar(3,0),0xd6fcf3e4:scalar(2,0),0x8c468e3c:position}
    def native_factory(self,result,*argtypes):
        by_rva={target:(name,slot) for name,(_,slots) in profile.TABLES.items() for slot,target in slots.items()}
        def bind(address):
            rva=address-self.memory.base
            if rva==0x839d30:return lambda:0x710000
            if rva==0x836b10:return lambda ptr:self.native_calls.append(('string-free',ptr))
            if rva not in by_rva:raise AssertionError(f'Unselected native call {rva:#x}')
            table,slot=by_rva[rva]
            def call(pointer,*args):
                if pointer!=self.memory.objects[table]:raise AssertionError('wrong native facade')
                self.native_calls.append((table,slot,args))
                return self.native(table,slot,*args)
            return call
        return bind
    def native(self,table,slot,*args):
        obj=self.memory.objects
        if slot==8 or (table=='unit' and slot==16):return None
        values={('outer',0xb8):obj['player'],('player',0x110):obj['units'],('units',0x10):obj['unit'],
            ('unit',0x28):1,('outer',0x100):obj['data'],('data',0x368):0x600000,
            ('unit',0x50):2,('data',0x260):0x600100,('player',0x18):3,
            ('data',0x308):0x600200,('unit',0x58):9,('unit',0x88):1,('player',0x28):2,
            ('outer',0x90):obj['game'],('game',0x128):1,('outer',0xa8):obj['map'],
            ('map',0x40):obj['plot'],('plot',0x60):obj['component'],('component',0x10):6,
            ('component',0x18):1,('component',0x30):8,('plot',0x30):10,
            ('plot',0xc8):1,('plot',0xc0):2,('plot',0xe0):1}
        if (table,slot)==('unit',0xb8):
            address,flags=args
            if flags!=0:raise AssertionError('snapshot flags changed')
            C.memmove(address+28,struct.pack('<I',998),4);return None
        if table=='plot' and slot in (0x178,0x180):
            address,flags=args;raw=bytearray(24)
            if slot==0x178:struct.pack_into('<I',raw,4,44);raw[20]=2
            else:struct.pack_into('<h',raw,4,-5)
            C.memmove(address,bytes(raw),24);return None
        return values[table,slot]
    def boundaries(self):
        stack=ExitStack()
        def mode_boundary(application,*,candidate_backend=None):
            if application is not self.app or candidate_backend is not self.backend:raise AssertionError('wrong mode owner')
            return 123
        def configuration_boundary(*args,**kwargs):
            if kwargs['core_sha256']!=profile.XP1_CORE_SHA256:raise AssertionError('Base helper used')
            return 12
        stack.enter_context(patch.object(C,'WINFUNCTYPE',self.native_factory))
        stack.enter_context(patch.object(app_mode,'read_application_mode',mode_boundary))
        stack.enter_context(patch.object(improvement,'query_secondary_value',configuration_boundary))
        stack.enter_context(patch.object(improvement,'read_player_civilization_type_id',configuration_boundary))
        return stack


class TurnA0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):base_fixture.PROFILE=base_fixture.a0_family_source.family_profile()
    def fixture(self):
        f=Fixture();f.enable();f.activate();return f

    def test_all_five_branches_real_owner_queries_fifo_consumption_and_close(self):
        f=self.fixture();self.assertIs(type(f.owner),A0FamilyService)
        expected=[]
        with f.boundaries():
            for kind in (0xc50d66d6,0x6e7ef927,0xa625c726,0xb8515a41,0xe5b20b82):
                self.assertEqual(f.owner.dispatch(kind,f.event_fields(kind),0),0)
                expected.append(profile.KINDS[kind])
                self.assertIsNone(f.owner._foundation_borrow);self.assertIsNone(f.owner.active_kind)
                self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(0,0))
        self.assertEqual([struct.unpack_from('<I',r,4)[0] for r in f.deferred.pending],expected)
        self.assertEqual(f.owner.entity_event_count,1)
        self.assertEqual(f.deferred.drain(),5);self.assertEqual(f.deferred.consumed_count,5)
        self.assertEqual(f.owner.entity_event_count,1)  # telemetry survives drains
        f.owner.close();self.assertTrue(f.owner.closed);self.assertIsNone(f.host._a0_family_owner)
        with self.assertRaises((ValueError,RuntimeError)):f.owner.dispatch(0xc50d66d6,f.event_fields(0xc50d66d6),0)
        fresh=Fixture();fresh.enable();self.assertEqual(fresh.owner.entity_event_count,0)

    def test_counter_is_telemetry_not_queue_admission_and_no_advance_on_failure(self):
        f=self.fixture();f.owner.entity_event_count=10**12
        with f.boundaries():f.owner.dispatch(0xc50d66d6,f.event_fields(0xc50d66d6),0)
        self.assertEqual(f.owner.entity_event_count,10**12+1)
        f.deferred.drain();f.deferred.limit=0
        with f.boundaries(),self.assertRaisesRegex(ValueError,'queue bound'):
            f.owner.dispatch(0xc50d66d6,f.event_fields(0xc50d66d6),0)
        self.assertEqual(f.owner.entity_event_count,10**12+1);self.assertEqual(f.deferred._sequence,1)
        self.assertTrue(f.owner.quarantined);self.assertIsNone(f.owner._foundation_borrow)

    def test_unknown_listeners_filter_visual_profile_and_foreign_borrow_refused(self):
        changes={
            'listeners':(0xc50d66d6,lambda f:setattr(f.owner,'entity_listener_count',1)),
            'filter':(0xc50d66d6,lambda f:f.host.filters.entries.__setitem__(0xc50d66d6,[])),
            'visual':(0xb8515a41,lambda f:setattr(f.owner,'visual_profile','unqualified')),
            'borrow':(0xb8515a41,lambda f:setattr(f.backend,'_xp1_continuation',object())),
        }
        for name,(kind,change) in changes.items():
            with self.subTest(name=name):
                f=self.fixture();change(f)
                with f.boundaries(),self.assertRaises((ValueError,RuntimeError)):
                    f.owner.dispatch(kind,f.event_fields(kind),0)
                self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.owner.entity_event_count,0)
                self.assertIsNone(f.owner._foundation_borrow)

    def test_enable_once_does_not_reset_preexisting_counter_or_profile(self):
        for attribute,value in (('entity_event_count',19),('visual_profile','old')):
            f=Fixture();setattr(f.owner,attribute,value)
            with patch.object(profile,'bind_owner') as bind,self.assertRaisesRegex(ValueError,'already exists'):
                events.enable_turn_units(f.owner,f.backend)
            bind.assert_not_called();self.assertEqual(getattr(f.owner,attribute),value)
            self.assertIsNone(f.owner.turn_unit_event_profile)
        f=Fixture();f.enable();f.owner.entity_event_count=8
        with self.assertRaises(ValueError):f.enable()
        self.assertEqual(f.owner.entity_event_count,8)

    def test_borrowed_base_and_dispatch_attribute_inventory(self):
        f=self.fixture()
        for attr in ('base','core','context','host','turn_unit_backend','turn_unit_core_sha256'):
            with self.assertRaises((ValueError,RuntimeError)):getattr(f.owner,attr)
        tree=ast.parse(inspect.getsource(shared.SharedHostEventDispatch))
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields')
        names=set()
        for n in ast.walk(fn):
            if not (isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and ast.unparse(n.test.left)=='kind'):continue
            right=n.test.comparators[0]
            kind=right.value if isinstance(right,ast.Constant) else 0xc50d66d6 if ast.unparse(right)=='ENTITY_EVENT_KIND' else None
            if kind not in profile.KINDS:continue
            names.update(v.attr for v in ast.walk(n) if isinstance(v,ast.Attribute)
                         and isinstance(v.value,ast.Name) and v.value.id=='self')
        self.assertEqual(names,{'_sequence','core','context','host','base','read','_enqueue','emit',
             'pending','limit','empty_receiver_state','visual_profile','entity_event_count','entity_listener_count'})


if __name__=='__main__':unittest.main()

"""Exact source and real XP2 saved-owner/FIFO/controller composition; no DLL."""
import ast
from contextlib import contextmanager
import ctypes as C
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import threading
from types import SimpleNamespace as NS,ModuleType
import unittest
from unittest.mock import patch
from civ6_host.runtime import xp2_natural_wonder_source as source,a0_natural_wonder as adapter
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256 as XP2,_copy
from civ6_host.runtime.native import native_36c9b2b4 as shared,native_wonder_application as effects
from xp2_unit_attack_owner_fixture import Fixture as SavedFixture
from test_xp1_turn_a0 import scalar

class Fixture(SavedFixture):
    def __init__(self):
        super().__init__();self.calls=[];self.live_value=self.retained_value=17
        from civ6_host.runtime.native.native_host import DiagnosticHost
        self.host._check=DiagnosticHost._check.__get__(self.host)
        self.comparison_game=0xd20000;self.argument=0xd00000
        from civ6_host.runtime.native.native_controller_code import NativeControllerCode
        from civ6_host.runtime.native.native_controller_state import NativeControllerTurnState
        code=NativeControllerCode.__new__(NativeControllerCode)
        code.closed=code.poisoned=code.busy=False;code.owner=threading.get_ident();code.objects=set()
        code.memory=C.create_string_buffer(16384);code.pointer=C.addressof(code.memory)
        # Only native allocation/call/memory are fixtures. The actual code-owner,
        # flag object, NativeControllerTurnState, TurnBegin and Host120 run.
        def constructor(pointer):C.memset(pointer,0,1200);return pointer
        code.constructor=constructor;code.getter=lambda p:C.c_uint8.from_address(p+13).value
        code.setter=lambda p,v:setattr(C.c_uint8.from_address(p+13),'value',v)
        code.kernel=NS(DeleteCriticalSection=lambda p:None)
        self.code=code;self.state=NativeControllerTurnState(code,self.emit)
        self.state.controller_initialized=True
        control=self.owner.controller_owner;control.code=code;control.turn_begin_state=self.state;control.emit=self.emit
        self.owner.turn_begin_state=self.deferred.turn_begin_state=self.state
        self.owner.controller_owner=None;control._a0_event_owner=None
        self.owner.enable_controller_events(control)
        self.control=control
        self.owner.emit=self.arguments.emit=self.deferred.emit=self.emit
        from civ6_host.runtime.event_argument_service import EventArgumentReader
        from civ6_host.runtime.event_argument_source import reader_abi
        iterator=reader_abi(XP2).successor_rva
        def iterator_factory(result,*types):
            def bind(address):
                if address!=self.backend.core._handle+iterator:raise AssertionError('Foreign native iterator')
                return lambda node:self.successors[node]
            return bind
        with patch.object(C,'WINFUNCTYPE',iterator_factory):
            self.arguments.reader=EventArgumentReader(self.backend.core,core_sha256=XP2,read=self.read)
        self.owner.read=self.backend.runtime.read=self.arguments.reader.read
        self.memory.q(self.comparison_game,self.memory.core_base+0xa10ee8)
        old=self.backend.stage;prefix=self.backend.prefix
        self.backend.stage='prepared';self.backend.prefix=None
        from civ6_host.runtime.a0_foundation_events import enable
        enable(self.owner,self.backend);adapter.enable(self.owner,self.backend)
        self.backend.stage=old;self.backend.prefix=prefix
        self.token.lease.tables=tuple((table,tuple(table)) for table in
            (self.host.vtable,self.host.aux_vtable,self.host.logger_vtable))
        self.token.lease.bindings=dict(self.host._slot_bindings)
        self.fields={0xa1e5a149:scalar(3,0),0x8c468e3c:struct.pack('<H6xQII',13,0xd10000,8,0x21000001),
            0xd6fcf3e4:scalar(2,22),0xa1fbc372:scalar(2,1),
            0x5b55a347:struct.pack('<H6xQII',1024,0xdead0000,8,0x21000001),0xf06a2af2:scalar(2,0)}
        self.memory.put(0xd10000,struct.pack('<ii',37,12))
        self.install_argument(self.fields)
        fallback=self.factory
        def factory(result,*types):
            def bind(address):
                rva=address-self.backend.core._handle
                if rva in (0x5901a0,0x597560,0x596dd0,0x597a90,0x99f5c0,0x59b590):
                    def invoke(*args):
                        self.calls.append((rva,args))
                        if rva==0x5901a0:return self.comparison_game
                        if rva==0x597560:return self.live_value
                        if rva==0x597a90:return self.retained_value
                        if rva==0x596dd0:return None
                        if rva==0x99f5c0:
                            if args!=(self.argument,0x5b55a347):raise AssertionError('Original map not borrowed')
                            return 0xdead0000  # discarded; never dereferenced
                        if rva==0x59b590:
                            C.memmove(args[1],struct.pack('<ii',36,12),8);return 1234
                    return invoke
                return fallback(result,*types)(address)
            return bind
        self.stack.enter_context(patch.object(C,'WINFUNCTYPE',factory))

    def install_argument(self,fields):
        header=bytearray(88);struct.pack_into('<Q',header,0,self.backend.core._handle+0xabf080)
        nodes=[self.argument+0x100+i*0x100 for i in range(len(fields))]
        struct.pack_into('<Q',header,56,nodes[0] if nodes else self.argument+48)
        struct.pack_into('<I',header,80,len(fields));self.memory.put(self.argument,header)
        for node,(key,value) in zip(nodes,fields.items()):
            self.memory.put(node+32,struct.pack('<I4x',key)+value)
        self.successors=dict(zip(nodes,nodes[1:]+[self.argument+48]))

    def invoke(self,fields=None,*,kind=source.KIND):
        if fields is not None:self.install_argument(fields)
        self.set_active(True)
        from civ6_host.runtime.xp1_load_capability import capability_source_scope
        with capability_source_scope(self.backend,'continuation'):
            return self.arguments.dispatch(self.host.pointer,kind,self.argument)

    def turn_begin(self,turn=9):
        self.install_argument({0xa1e5a149:scalar(3,0),0xd6fcf3e4:scalar(2,turn)})
        self.set_active(True)
        from civ6_host.runtime.xp1_load_capability import capability_source_scope
        with capability_source_scope(self.backend,'continuation'):
            return self.arguments.dispatch(self.host.pointer,0x21535587,self.argument)

    def close(self):
        if hasattr(self,'state'):self.state.close()
        super().close()

class SourceTests(unittest.TestCase):
    def test_independent_image_correspondence_registration_and_lifecycle(self):
        from extract_phase31_next_export import pefile
        p=source.source();pe=pefile.PE(p['images']['xp2']['path'],fast_load=True)
        self.addCleanup(pe.close);base=pe.OPTIONAL_HEADER.ImageBase
        source.verify_live(base,lambda a,n:pe.get_data(a-base,n))
        self.assertEqual(len(p['functions']),30)
        self.assertEqual(tuple(p['literal_occurrence_rvas']),('0x35c379',))
        # Independent actual PE slot bytes, consumed width in EXE, and leaf.
        self.assertEqual(struct.unpack('<Q',pe.get_data(0xa10ee8+0xc8,8))[0],base+0x597560)
        self.assertEqual(pe.get_data(0x597560,5),b'\xe9\x8b\x58\xac\xff')
        self.assertEqual(pe.get_data(0x5cdf0,7),b'\x8b\x05\x3a\xe4\xb2\x00\xc3')
        self.assertEqual(p['contract']['game_comparison_return'],'int32')
        self.assertIn(source.SOURCE[1],source.source_dependencies().values())
        for changed in (0x5fc152,0x35c379,0x5fd6a9,0x5cdf6,0xa10ee8+0xc8,0xabf080+0x60):
            def read(a,n):
                start=a-base;raw=bytearray(pe.get_data(start,n))
                if start<=changed<start+n:raw[changed-start]^=1
                return bytes(raw)
            with self.subTest(changed=hex(changed)),self.assertRaises(ValueError):source.verify_live(base,read)

    def test_strict_shape_and_profile_refusals(self):
        p=source.source();original=source._source
        for key in ('core','record','dispatch','slot'):
            value=_copy(p)
            if key=='core':value['images']['xp2']['sha256']='0'*64
            elif key=='record':value['records']['0x78']=128
            elif key=='dispatch':value['contract']['core_internal_dispatch_before_host']=False
            else:value['comparison_abi']['read_value']=0x597a90
            with self.subTest(key=key),patch.object(source,'_source',side_effect=lambda ref:value if ref==source.SOURCE else original(ref)):
                with self.assertRaises(ValueError):
                    source.comparison_abi() if key=='slot' else source.source()

class ComposedTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_wonder_completion_keeps_effect_between_ae_and_af_on_the_shared_owner(self):
        from civ6_host.runtime.native import native_event_e66012a7 as completion
        from civ6_host.runtime.xp2_wonder_completion import KIND

        f=self.fixture()
        f.memory.put(0xd30000,struct.pack('<HHI',2,2,3))
        fields={0xa1e5a149:scalar(3,0xccb6d5be),0xd6fcf3e4:scalar(2,409),
                0xa1fbc372:scalar(2,100),
                0x23739f42:struct.pack('<H6xQII',1024,0xd30000,8,0x21000001),
                0x8c468e3c:struct.pack('<H6xQII',0,0xd10000,8,0x21000001)}
        queries=[]

        @contextmanager
        def plot(*args,**kwargs):
            queries.append('plot')
            yield dict(owner=2,city_id=3,district_id=0x80003,flag148=1)

        @contextmanager
        def district(*args,**kwargs):
            queries.append('district')
            yield dict(type_index=1,type_hash=0x62f1b509)

        with patch.object(completion.snapshot,'plot_snapshot',plot), \
                patch.object(completion,'_district_type_hash',district):
            self.assertEqual(f.invoke(fields,kind=KIND),0)
        self.assertEqual(queries,['plot','plot','plot','district'])
        self.assertEqual([struct.unpack_from('<II',r,4) for r in f.deferred.pending],
                         [(169,1),(166,2),(174,3),(175,4)])
        self.assertEqual([rva for rva,_ in f.calls],
                         [0x597a90,0x5901a0,0x597560,0x597a90,0x596dd0])
        order=[v.get('queue_type',stage) for stage,v in f.emitted if v.get('dispatch_kind')==hex(KIND)
               and stage in ('native_deferred_host_event_enqueued','native_wonder_application_effects_applied')]
        self.assertEqual(order,['0xa9','0xa6','0xae','native_wonder_application_effects_applied','0xaf'])
        self.assertEqual(f.control.controller_flag(f.host.pointer),1)
        self.assertEqual(f.state.service_flags,0x40)
        self.assertEqual(f.deferred.drain(),4)
        with self.assertRaisesRegex(ValueError,'transient controller/UI'):
            adapter.require_checkpoint_quiescent(f.backend)
        self.assertEqual(f.turn_begin(),0)
        self.assertEqual(f.deferred.drain(),1)
        adapter.require_checkpoint_quiescent(f.backend)

    def test_actual_saved_owner_a0_reader_pair_fifo_host120_readback_and_normal_turn_begin(self):
        f=self.fixture()
        from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
        self.assertIs(type(f.saved),SavedLoadOwner)
        self.assertEqual(f.control.controller_flag(f.host.pointer),0)
        # A preceding real family record establishes one FIFO and sequence.
        from civ6_host.runtime.native import native_event_15c35863 as existing
        f.memory.put(0xd30000,struct.pack('<HHI',0,1,17))
        f.owner.dispatch(existing.KIND,existing.encode_fields(existing.EventFields(0,19,0xd30000)),0)
        self.assertEqual(f.invoke(),0)
        self.assertEqual([struct.unpack_from('<I',r,4)[0] for r in f.deferred.pending],[67,120,121])
        a,b=f.deferred.pending[-2:]
        self.assertEqual([struct.unpack_from('<I',r,8)[0] for r in (a,b)],[2,3])
        for r in (a,b):
            self.assertEqual(struct.unpack_from('<II',r,16),(1234,0xffffffff))
            self.assertEqual(struct.unpack_from('<I',r,72)[0],6)
            self.assertEqual(r[84:92],struct.pack('<ii',37,12))
            self.assertEqual(struct.unpack_from('<I',r,92)[0],22);self.assertEqual(r[96],1)
        self.assertEqual([rva for rva,_ in f.calls],[0x5901a0,0x597560,0x597a90,0x596dd0,0x99f5c0,0x59b590])
        self.assertEqual(f.control.controller_flag(f.host.pointer),1)
        self.assertEqual(f.state.service_flags,0x40)
        self.assertEqual(f.deferred.drain(),3)
        self.assertEqual(f.control.controller_flag(f.host.pointer),1)
        self.assertEqual(f.state.service_flags,0x40)
        self.assertEqual(f.prepare()['actions'][0]['kind'],'unit_attack')
        from civ6_host.runtime.network_checkpoint import validate_boundary
        with self.assertRaisesRegex(ValueError,'transient controller/UI'):
            validate_boundary(f.backend)
        self.assertEqual(f.turn_begin(),0)  # actual shared A0 branch, no state reset fixture
        self.assertEqual(f.control.controller_flag(f.host.pointer),0)
        self.assertEqual(f.state.service_flags,0)
        self.assertEqual(f.state.turn_values_by_thread,{0:[9]})
        with self.assertRaisesRegex(ValueError,'FIFO'):
            adapter.require_checkpoint_quiescent(f.backend)
        self.assertEqual(f.deferred.drain(),1)
        adapter.require_checkpoint_quiescent(f.backend)
        self.assertEqual(f.prepare()['actions'][0]['kind'],'unit_attack')
        self.assertIsNone(f.owner._foundation_borrow)
        self.assertEqual((f.owner.host_notification_counter,f.owner.host_metadata_counter),(0,0))

    def test_nonmatching_signed_game_comparison_and_counter_neutral_pair(self):
        f=self.fixture();f.live_value=-1;f.retained_value=17
        f.deferred.host_notification_counter=7;f.deferred.host_metadata_counter=3
        self.assertEqual(f.invoke(),0)
        self.assertEqual((f.owner.host_notification_counter,f.owner.host_metadata_counter),(7,3))
        self.assertEqual(f.control.controller_flag(f.host.pointer),0)
        self.assertEqual(f.state.service_flags,0x40)
        f.deferred.host_notification_counter=f.deferred.host_metadata_counter=0
        self.assertEqual(f.deferred.drain(),2)
        with self.assertRaisesRegex(ValueError,'transient controller/UI'):
            adapter.require_checkpoint_quiescent(f.backend)

    def test_wrong_live_vtable_refuses_quarantines_and_logs_only_copied_headers(self):
        f=self.fixture();f.memory.q(f.comparison_game,f.memory.core_base+0x79ecd8)
        with self.assertRaisesRegex(ValueError,'facade identity'):f.invoke()
        self.assertTrue(f.owner.quarantined);self.assertTrue(f.arguments.quarantined)
        self.assertTrue(f.owner._36c9_poisoned);self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.state.service_flags,0);self.assertEqual(f.control.controller_flag(f.host.pointer),0)
        rows=[v for stage,v in f.emitted if stage=='native_host_event_failed_copied_headers']
        self.assertEqual(len(rows),1);self.assertEqual(set(rows[0]['fields']),{hex(k) for k in f.fields})
        self.assertEqual(rows[0]['core_sha256'],XP2);self.assertFalse(rows[0]['pointer_payloads_retained'])
        self.assertFalse(rows[0]['result_substituted'])

    def test_malformed_selector_refuses_before_any_query(self):
        f=self.fixture();fields=dict(f.fields);fields[0xa1e5a149]=scalar(3,1)
        with self.assertRaisesRegex(ValueError,'selector'):f.invoke(fields)
        self.assertEqual(f.calls,[]);self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.state.service_flags,0)

def load_tests(loader,tests,pattern):
    # Run only touched Base shared effect/producer regressions through extracted
    # imports. Their native seams remain fixtures; no historical code imported.
    from civ6_host.runtime.paths import resource_root
    for name in ('test_native_wonder_application','test_native_36c9b2b4'):
        path=resource_root()/'tests'/f'{name}.py';module=ModuleType('retained_'+name);module.__file__=str(path)
        raw=path.read_text().replace('from civ6rl import','from civ6_host.runtime.native import').replace('from civ6rl.','from civ6_host.runtime.native.')
        exec(compile(raw,str(path),'exec'),module.__dict__);tests.addTests(loader.loadTestsFromModule(module))
    return tests

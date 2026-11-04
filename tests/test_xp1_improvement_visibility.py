"""Full F391 shared producer on the saved owner and FIFO; machine-only fixtures."""
import ast
import ctypes as C
import inspect
import struct
from types import MethodType
import unittest
from test_xp1_placement_events import Fixture as PlacementFixture
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import improvement_visibility_profile as source
from civ6_host.runtime import turn_unit_event_profile as units
from civ6_host.runtime.native import native_event_f391d7b3 as event
from civ6_host.runtime.native import native_host_events as shared
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_host_slot_e8 import SPECIAL_CODE


class Fixture(PlacementFixture):
    def __init__(self):
        super().__init__();self.component_owner=0;self.failure=None
        self.objects['component']=0x76500000
        self.memory.put(self.objects['component'],struct.pack('<Q',self.memory.base+units.TABLES['component'][0]))
        self.map_owner=0x76501000
        self.memory.put(self.objects['map'],struct.pack('<QQ',self.memory.base+self.abi.table('map'),self.map_owner))
        self.memory.put(self.map_owner+40,struct.pack('<i',8));self.memory.put(self.map_owner+48,struct.pack('<i',64))
        self.host._check=MethodType(DiagnosticHost._check,self.host)

    def factory(self,result,*args):
        fallback=super().factory(result,*args)
        def bind(target):
            if callable(target):return fallback(target)
            base=self.backend.core._handle
            names=('plot_component','release_component','snapshot180','snapshot178','component10','component18','component30','plotc8','plotc0','plote0')
            for name in names:
                table,slot=units.OPERATIONS[name]
                if target==base+units.TABLES[table][1][slot]:return lambda *values:self.improvement_native(name,*values)
            if target==base+self.abi.rva('optional_position'):return lambda *values:self.improvement_native('optional_position',*values)
            return fallback(target)
        return bind

    def improvement_native(self,name,pointer,*args):
        self.calls.append((name,pointer,*args));o=self.objects
        if name=='plot_component':assert pointer==o['plot'];return self.acquire('component')
        if name=='release_component':assert pointer==o['component'] and self.live['component']==1;self.live['component']-=1;return None
        if name.startswith('snapshot'):
            assert pointer==o['plot'] and args[1]==0
            raw=bytearray(24)
            if name=='snapshot178':struct.pack_into('<I',raw,4,65536);raw[20]=0
            else:struct.pack_into('<h',raw,4,-1)
            C.memmove(args[0],bytes(raw),24);return None
        if name.startswith('component'):
            assert pointer==o['component']
            if name=='component18':
                if self.failure=='reentry':self.deferred.host_notification(self.host.pointer,SPECIAL_CODE)
                return self.component_owner
            return 11 if name=='component10' else 12
        if name in ('plotc8','plotc0','plote0'):assert pointer==o['plot'];return 1
        if name=='optional_position':
            assert pointer==o['map'] and args[1]==10
            assert self.live['map']==1 and not any(v for k,v in self.live.items() if k!='map')
            out=args[0];C.memmove(out,struct.pack('<ii',2,1),8)
            if self.failure=='optional_output':return out+1
            return out
        raise AssertionError(name)

    def emit(self,stage,**details):
        if stage=='native_deferred_host_event_enqueued' and details.get('dispatch_kind')==hex(source.EVENT_KIND):
            assert not any(self.live.values())
            self.calls.append(('f391_enqueued',))
        return super().emit(stage,**details)

    def fields(self,*,extended=False,tag=0,index=10):
        r={event.POSITION_KEY:self.make_blob(struct.pack('<ii',3,4),tag),
           event.SELECTOR_KEY:scalar(3,0xa5eea1c0),event.VALUE_KEY:scalar(2,2)}
        if extended:r.update({event.INDEX_KEY:scalar(2,index),event.SCALAR_KEY:scalar(2,9),
          event.PLAYER_KEY:scalar(2,0),event.PAIR_KEY:self.make_blob(struct.pack('<HHI',0,1,17),1024)})
        return r


class ImprovementVisibilityTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_full_basic_and_extended_branches_real_native_queries_and_order(self):
        for extended,tag,index,owner in ((False,0,10,0),(True,0,10,0),(True,13,10,0),(True,13,0xffffffff,-1)):
            with self.subTest(extended=extended,tag=tag,index=index,owner=owner):
                f=self.fixture();f.component_owner=owner
                self.assertEqual(f.owner.dispatch(source.EVENT_KIND,f.fields(extended=extended,tag=tag,index=index),0),0)
                self.assertEqual(len(f.deferred.pending),1);record=f.deferred.pending[0]
                self.assertEqual(struct.unpack_from('<II',record),(160,145));self.assertFalse(any(f.live.values()))
                positive=extended and index<0x80000000
                self.assertEqual(sum(x[0]=='optional_position' for x in f.calls),int(positive))
                self.assertEqual(record[140:148],struct.pack('<ii',2,1) if positive else struct.pack('<ii',-9999,-9999))
                self.assertEqual(sum(x[0]=='civilization' for x in f.calls),int(owner!=-1))
                if owner==-1:self.assertEqual(struct.unpack_from('<II',record,116),(0xffffffff,0xffffffff))
                else:self.assertEqual(struct.unpack_from('<II',record,116),(0x1776,f.civilization))
                self.assertFalse(f.owner._f391_producing);self.assertFalse(f.owner._f391_poisoned)
                self.assertIsNone(f.owner._foundation_borrow)
                self.assertEqual(f.deferred.drain(),1);self.assertEqual(f.deferred.pending,[])

    def test_notification_scope_commits_only_after_enqueue_and_uses_real_e8_f0(self):
        f=self.fixture();f.deferred.host_notification(f.host.pointer,SPECIAL_CODE)
        self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(1,0))
        for flag in (32,64):
            f.owner.dispatch(source.EVENT_KIND,f.fields(extended=True,tag=13),0)
            self.assertEqual(struct.unpack_from('<I',f.deferred.pending[-1],72)[0],flag)
            self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(1,1))
        f.deferred.host_notification_end(f.host.pointer,SPECIAL_CODE)
        self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(0,0))
        self.assertEqual(f.deferred.drain(),2)

    def test_failed_optional_and_reentry_preserve_metadata_release_and_poison(self):
        for failure in ('optional_output','reentry'):
            with self.subTest(failure=failure):
                f=self.fixture();f.deferred.host_notification(f.host.pointer,SPECIAL_CODE);f.failure=failure
                with self.assertRaises((ValueError,RuntimeError)):
                    f.owner.dispatch(source.EVENT_KIND,f.fields(extended=True,tag=13),0)
                self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(1,0))
                self.assertEqual(f.deferred.pending,[]);self.assertFalse(any(f.live.values()))
                self.assertTrue(f.owner._f391_poisoned);self.assertFalse(f.owner._f391_producing)
                self.assertTrue(f.owner.quarantined);self.assertIsNone(f.owner._foundation_borrow)
                for call,args in ((f.deferred.host_notification,(f.host.pointer,SPECIAL_CODE)),
                                  (f.deferred.host_notification_end,(f.host.pointer,SPECIAL_CODE)),
                                  (f.deferred.cache_update,(f.host.pointer,0,0))):
                    with self.assertRaisesRegex(RuntimeError,'F391'):call(*args)
                self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(1,0))

    def test_source_engine_propagation_and_actual_owner_attribute_inventory(self):
        f=self.fixture();source.bind_owner(f.backend,f.backend.core,f.read)
        with self.assertRaises(ValueError):source.bind_owner(f.backend,object(),f.read)
        tree=ast.parse(inspect.getsource(shared))
        fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields')
        branch=next(n for n in ast.walk(fn) if isinstance(n,ast.If) and ast.unparse(n.test)==f'kind == {source.EVENT_KIND}')
        attrs={n.attr for n in ast.walk(branch) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='self'}
        self.assertEqual(attrs,{'host_metadata_counter','host_notification_counter','pending','limit','_sequence','entity_listener_count',
            'empty_receiver_state','read','_f391_producing','_f391_poisoned','core','context','host','_enqueue','emit'})
        produce=ast.parse(inspect.getsource(event))
        methods={n.name:n for n in produce.body if isinstance(n,ast.FunctionDef)}
        for name in ('produce_record','produce_scoped_record'):
            self.assertIn('core_sha256',[a.arg for a in methods[name].args.kwonlyargs])
            for call in (n for n in ast.walk(methods[name]) if isinstance(n,ast.Call) and ast.unparse(n.func) in
                         ('shared.query_native_values','query_optional_position','produce_record')):
                self.assertEqual([ast.unparse(k.value) for k in call.keywords if k.arg=='core_sha256'],['core_sha256'])


if __name__=='__main__':unittest.main()

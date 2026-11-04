"""Shared FIFO/feedback ownership; native XP1 execution has a separate receipt."""
import ast
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import struct
import types
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import cache_update_profiles as p
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_host_events import DeferredHostQueue,NativeDeferredHostEvents
from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload
from civ6_host.runtime.paths import resource_root


class Host:
    _bind=DiagnosticHost._bind
    def __init__(self):
        self.vtable=(C.c_void_p*64)();self.functions=[];self.emit=Mock();self.pointer=123
        for s in (0xB0,0xE8,0xF0):self._bind(self.vtable,s,None,[C.c_void_p],lambda _:None)
    def _check(self,ptr):
        if ptr!=self.pointer:raise ValueError('Foreign receiver')
    def _fatal(self,*a,**k):raise AssertionError((a,k))


class DeferredServiceTests(unittest.TestCase):
    def fixture(self,**kwargs):
        h=Host();before=list(h.vtable);bindings=dict(h._slot_bindings)
        for name in ('verify_dispatch_live','verify_notification_live'):
            m=patch('civ6_host.runtime.cache_update_profiles.'+name,return_value={})
            m.start();self.addCleanup(m.stop)
        s=DeferredService(h,types.SimpleNamespace(_handle=1000),2000,
            core_sha256=XP1_CORE_SHA256,read=Mock(),emit=Mock(),limit=3,
            optional_preprocessor=None,queue_metadata_service=None,**kwargs)
        return h,s,before,bindings

    def test_fifo_callback_feedback_and_exactly_once_consumption(self):
        h,s,before,bindings=self.fixture();seen=[]
        s.cache_update(h.pointer,7,(0xFFFFFFFF<<32)|3)
        s.cache_update(h.pointer,8,(2<<32)|4)
        originals=list(s.pending)
        def dispatch(base,context,payload,**kwargs):
            self.assertEqual((base,context),(1000,2000))
            self.assertEqual(kwargs['core_sha256'],XP1_CORE_SHA256)
            seen.append(struct.unpack('<5I',payload))
            self.assertEqual(s.consumed_count,len(seen)-1)
            if len(seen)==1:
                s.cache_update(h.pointer,9,(6<<32)|5);originals.append(s.pending[-1])
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',side_effect=dispatch):
            self.assertEqual(s.drain(),3);self.assertEqual(s.drain(),0)
        self.assertEqual(seen,[(1,7,0,3,0xFFFFFFFF),(2,8,0,4,2),(3,9,0,5,6)])
        self.assertEqual(s.consumed_bytes,336)
        self.assertEqual(s.consumed_digest.hexdigest(),hashlib.sha256(b''.join(originals)).hexdigest())
        timings = [call.kwargs for call in s.emit.call_args_list
                   if call.args == ('native_deferred_drain_timing',)]
        timing, = timings
        row, = timing['records']
        self.assertEqual((row['record_type'], row['count']), (0x113, 3))
        self.assertGreaterEqual(row['seconds'], 0)
        self.assertIs(timing['includes_callbacks_and_trace_emission'], True)
        s.close();s.close()
        self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)
        with self.assertRaisesRegex(RuntimeError,'closed'):s.cache_update(h.pointer,1,2)

    def test_uncertain_native_failure_retains_head_and_forbids_replay(self):
        h,s,_,_=self.fixture();s.cache_update(h.pointer,7,8);head=s.pending[0]
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',side_effect=OSError('native return uncertain')) as call:
            with self.assertRaises(OSError):s.drain()
            with self.assertRaisesRegex(RuntimeError,'poisoned'):s.drain()
            self.assertEqual(call.call_count,1)
        self.assertEqual(s.pending,[head]);self.assertEqual(s.consumed_count,0)
        with self.assertRaisesRegex(RuntimeError,'poisoned'):s.close()

    def test_nested_notification_scopes_preserve_both_counters(self):
        h,s,_,_=self.fixture();code=0x5A9A0329
        s.host_notification(h.pointer,code);s.host_notification(h.pointer,code)
        self.assertEqual((s.host_notification_counter,s.host_metadata_counter),(2,0))
        with self.assertRaisesRegex(RuntimeError,'open scope'):s.close()
        s.host_notification_end(h.pointer,code)
        self.assertEqual((s.host_notification_counter,s.host_metadata_counter),(1,1))
        s.host_notification_end(h.pointer,17)
        self.assertEqual((s.host_notification_counter,s.host_metadata_counter),(1,1))
        s.host_notification_end(h.pointer,code);s.host_notification_end(h.pointer,code)
        self.assertEqual((s.host_notification_counter,s.host_metadata_counter),(0,0));s.close()

    def test_pending_queue_wrong_owner_and_thread_refuse(self):
        h,s,_,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'Foreign'):s.cache_update(999,1,2)
        s.cache_update(h.pointer,1,2)
        with self.assertRaisesRegex(RuntimeError,'pending'):s.close()
        with patch('civ6_host.runtime.deferred_service.threading.get_ident',return_value=-1):
            with self.assertRaisesRegex(ValueError,'thread'):s.drain()
        h.vtable[0xB0//8]=1
        with self.assertRaisesRegex(RuntimeError,'replaced'):s.drain()

    def test_reentrant_drain_poisoned_without_second_native_call(self):
        h,s,_,_=self.fixture();s.cache_update(h.pointer,1,2)
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',side_effect=lambda *a,**k:s.drain()) as call:
            with self.assertRaisesRegex(RuntimeError,'Reentrant'):s.drain()
            self.assertEqual(call.call_count,1)
        self.assertTrue(s._deferred_drain_poisoned);self.assertEqual(len(s.pending),1)

    def test_unknown_record_is_retained_not_silently_skipped(self):
        h,s,_,_=self.fixture();s.cache_update(h.pointer,1,2)
        bad=bytearray(s.pending[0]);bad[4:8]=(0x777).to_bytes(4,'little');s.pending[0]=bytes(bad)
        with self.assertRaisesRegex(ValueError,'no decoder'):s.drain()
        self.assertEqual(s.pending,[bytes(bad)]);self.assertEqual(s.consumed_count,0)

    def test_controller_borrow_prevents_early_deferred_close(self):
        h,s,_,_=self.fixture();h._control_input_owner=types.SimpleNamespace(deferred=s)
        with self.assertRaisesRegex(RuntimeError,'borrows'):s.close()
        h._control_input_owner=None;s.close()

    def test_event_argument_borrow_prevents_early_deferred_close(self):
        h,s,_,_=self.fixture();h._event_argument_owner=types.SimpleNamespace(deferred=s)
        with self.assertRaisesRegex(RuntimeError,'borrows'):s.close()
        h._event_argument_owner=None;s.close()

    def test_queue_methods_are_shared_not_a_reimplemented_transport(self):
        for name in ('_enqueue','cache_update','host_notification','host_notification_end'):
            self.assertIs(getattr(NativeDeferredHostEvents,name),getattr(DeferredHostQueue,name))
            self.assertIs(getattr(DeferredService,name),getattr(DeferredHostQueue,name))
        old=ast.parse((resource_root()/'civ6rl/native_host_events.py').read_text(encoding='utf-8'))
        new=ast.parse(Path(__import__(DeferredHostQueue.__module__,fromlist=['x']).__file__).read_text(encoding='utf-8'))
        def methods(tree,cls):
            c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
            return {n.name:n for n in c.body if isinstance(n,ast.FunctionDef)}
        a=methods(old,'NativeDeferredHostEvents');b=methods(new,'DeferredHostQueue')
        for name in ('_enqueue','cache_update','host_notification','host_notification_end'):
            # The extractor changes only project import namespaces.
            original=ast.parse(ast.unparse(a[name]).replace('civ6rl.','civ6_host.runtime.native.'))
            class Imports(ast.NodeTransformer):
                def visit_ImportFrom(self,n):
                    module='civ6_host.runtime.native.'+n.module if n.level==1 else n.module
                    return [ast.ImportFrom(module=module,names=[a],level=0) for a in n.names]
            original=Imports().visit(original)
            self.assertEqual(ast.dump(original),ast.dump(ast.parse(ast.unparse(b[name]))))


class RegistryTests(unittest.TestCase):
    def fixture(self):
        base=0x200000000;mem={}
        def put(addr,data):mem.update({addr+i:v for i,v in enumerate(data)})
        def read(addr,n):return bytes(mem[addr+i] for i in range(n))
        put(base+0x9CDDB0,struct.pack('<QII',0x1000,1,1))
        put(0x1000,struct.pack('<QQ',0x2000,0x9999))
        node=bytearray(48);struct.pack_into('<I',node,0,7)
        struct.pack_into('<QQQ',node,8,0x3000,0x3040,0x3040)
        struct.pack_into('<Q',node,40,0x9999);put(0x2000,node)
        put(0x3000,struct.pack('<8Q',1,2,3,4,0,0,0,0))
        return base,read,put,mem

    def test_absent_key_differs_from_active_subscribers(self):
        base,read,_,_=self.fixture();r=p.registry_snapshot(base,read,7)
        self.assertEqual(r['subscribers'],((1,2,3,4),(0,0,0,0)))
        self.assertEqual(r['receiver_count'],1)
        missing=p.registry_snapshot(base,read,8)
        self.assertIsNone(missing['node']);self.assertEqual(missing['entry_count'],1)

    def test_invalid_vector_cycles_and_uninitialized_registry_refuse(self):
        base,read,put,_=self.fixture();put(0x2000+40,struct.pack('<Q',0x2000))
        with self.assertRaisesRegex(ValueError,'cyclic'):p.registry_snapshot(base,read,8)
        put(0x2000+16,struct.pack('<Q',0x3041))
        with self.assertRaisesRegex(ValueError,'malformed'):p.registry_snapshot(base,read,7)
        put(base+0x9CDDB8,bytes(4))
        with self.assertRaisesRegex(ValueError,'uninitialized'):p.registry_snapshot(base,read,7)

    def test_registry_changed_during_snapshot_refuses(self):
        base,read,put,_=self.fixture();calls=0
        def unstable(addr,n):
            nonlocal calls
            if addr==base+0x9CDDB0:
                calls+=1
                if calls==2:put(addr+12,struct.pack('<I',2))
            return read(addr,n)
        with self.assertRaisesRegex(ValueError,'changed'):p.registry_snapshot(base,unstable,7)

    def test_source_live_body_outer_slot_and_xp1_payload_are_bound_together(self):
        base,read,put,mem=self.fixture();ctx=0x5000;calls=[]
        for name in ('outer_dispatch','keyed_dispatch','keyed_register','notification_begin','notification_end','notification_vector_insert'):
            for frag in p.body(name)['fragments']:
                for i in frag['instructions']:put(base+int(i['va'],16)-0x180000000,bytes.fromhex(i['bytes']))
        put(ctx,struct.pack('<Q',base+0x8A8DF0))
        put(base+0x8A8DF0+0x198,struct.pack('<Q',base+0x4BE750))
        put(base+0x9F2640,struct.pack('<Q',123))
        p.verify_notification_live(base,read,host_pointer=123)
        payload=struct.pack('<5I',1,7,0,0xFFFFFFFF,0x80000001)
        result=dispatch_cache_update_payload(base,ctx,payload,core_sha256=XP1_CORE_SHA256,
            read_memory=read,invoke=lambda *a:calls.append(a))
        self.assertEqual(result,(7,0,0xFFFFFFFF,0x80000001))
        self.assertEqual(calls[0][0],base+0x4BE750)
        mem[base+0x70620]^=1
        with self.assertRaisesRegex(ValueError,'instruction differs'):
            dispatch_cache_update_payload(base,ctx,payload,core_sha256=XP1_CORE_SHA256,read_memory=read,invoke=lambda *a:calls.append(a))
        self.assertEqual(len(calls),1)
        self.assertEqual(p.dispatch_abi(XP2_CORE_SHA256),p.DispatchABI(0xA101E8,0x591920))
        with self.assertRaises(ValueError):p.dispatch_abi('unknown')


def load_tests(loader,tests,pattern):
    # Execute retained Base regressions with namespace migration only.
    for name in ('test_native_deferred_drain','test_native_cache_update_dispatch','test_native_cache_update_event','test_native_host_slot_e8','test_native_host_slot_f0'):
        path=resource_root()/'tests'/(name+'.py')
        text=path.read_text(encoding='utf-8').replace('civ6rl.','civ6_host.runtime.native.')
        module=types.ModuleType('retained_'+name);module.__file__=str(path)
        exec(compile(text,str(path),'exec'),module.__dict__)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests

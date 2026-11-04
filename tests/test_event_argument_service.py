"""Shared tree transport and strict source-qualified A0 consumer ownership."""
import ctypes as C
import struct
from types import SimpleNamespace as NS,ModuleType
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native.native_event_argument_tree import read_event_fields,EventArgumentTreeError
from test_deferred_service import Host


def variant(tag,value=0):
    raw=bytearray(24);struct.pack_into('<H',raw,0,tag);struct.pack_into('<I',raw,8,value);return bytes(raw)


class EventArgumentServiceTests(unittest.TestCase):
    def fixture(self):
        h=Host();core=NS(_handle=1000);before=list(h.vtable);bindings=dict(h._slot_bindings)
        d=NS(host=h,core=core,context=2000,_check=Mock(),pending=[],_draining_empty_receivers=False,
             host_notification_counter=0,host_metadata_counter=0)
        reader=NS(fields=Mock(return_value={0xA1E5A149:variant(3),0xD6FCF3E4:variant(2,0xFFFFFFFF)}),
                  close=Mock(),core_sha256=XP1_CORE_SHA256)
        for target,value in (('civ6_host.runtime.event_argument_source.verify_host_live',Mock(return_value={})),
                             ('civ6_host.runtime.event_argument_service.EventArgumentReader',Mock(return_value=reader))):
            m=patch(target,value);m.start();self.addCleanup(m.stop)
        s=EventArgumentService(h,core,2000,d,core_sha256=XP1_CORE_SHA256,read=Mock(),emit=Mock(),
            normalizer_transform=None,dynamic_registrations=())
        return h,d,s,reader,before,bindings

    def test_absent_callback_is_source_validated_and_has_no_queue_or_game_effect(self):
        h,d,s,reader,before,bindings=self.fixture()
        self.assertEqual(s.dispatch(h.pointer,0x237DDDA8,3000),0)
        self.assertEqual(d.pending,[]);reader.fields.assert_called_once_with(3000)
        data=s.emit.call_args.kwargs
        self.assertFalse(data['callback_registered']);self.assertTrue(data['core_internal_dispatch_preserved'])
        self.assertEqual(data['fields']['0xd6fcf3e4'],variant(2,0xFFFFFFFF).hex())
        self.assertEqual(s.count,1)
        s.close();s.close();reader.close.assert_called_once()
        self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)

    def test_registered_callback_and_unknown_shape_fail_instead_of_success(self):
        h,d,s,reader,_,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'registered EXE callback'):s.dispatch(h.pointer,0x52E2805C,3000)
        self.assertTrue(s.quarantined);self.assertEqual(s.count,0)
        self.assertEqual(s.emit.call_args.args, ('native_host_event_failed_copied_headers',))
        self.assertFalse(s.emit.call_args.kwargs['result_substituted'])
        with self.assertRaisesRegex(RuntimeError,'quarantined'):s.close()
        # Independent fixture for unknown scalar selector, not recovery/replay.
        h,d,s,reader,_,_=self.fixture();reader.fields.return_value={0xA1E5A149:variant(3,1)}
        with self.assertRaisesRegex(ValueError,'scalar variant'):s.dispatch(h.pointer,0x237DDDA8,3000)

    def test_foreign_thread_active_consumer_and_borrowed_scope_refuse(self):
        h,d,s,reader,_,_=self.fixture()
        with patch('civ6_host.runtime.event_argument_service.threading.get_ident',return_value=-1):
            with self.assertRaisesRegex(ValueError,'thread'):s.dispatch(h.pointer,0x237DDDA8,3000)
        s.depth=1
        with self.assertRaisesRegex(RuntimeError,'active consumers'):s.close()
        s.depth=0;d.host_metadata_counter=1
        with self.assertRaisesRegex(RuntimeError,'active consumers'):s.close()
        d.host_metadata_counter=0;s.close()

    def test_recursive_dispatch_is_not_replayed_and_poisoned(self):
        h,d,s,reader,_,_=self.fixture()
        reader.fields.side_effect=lambda _:s.dispatch(h.pointer,0x237DDDA8,3000)
        with self.assertRaisesRegex(RuntimeError,'Reentrant'):s.dispatch(h.pointer,0x237DDDA8,3000)
        self.assertTrue(s.quarantined);self.assertEqual(s.depth,0);self.assertEqual(reader.fields.call_count,1)

    def test_status_borrow_prevents_releasing_its_reader(self):
        h,d,s,reader,_,_=self.fixture();h._status_message_owner=NS(arguments=s)
        with self.assertRaisesRegex(RuntimeError,'borrows'):s.close()
        reader.close.assert_not_called();h._status_message_owner=None;s.close()


class ExpansionTreeTests(unittest.TestCase):
    def test_guard_uses_owned_session_and_preserves_native_suppression(self):
        from civ6_host.runtime.event_argument_source import guard_state
        base,context,inner,session=0x200000000,0x1000,0x2000,0x6000;mem={}
        def put(addr,data):mem.update({addr+i:b for i,b in enumerate(data)})
        def read(addr,n):return bytes(mem[addr+i] for i in range(n))
        for addr,value in ((context+8,inner),(base+0x9F2620,inner),
                           (inner+0x1A60,session),(base+0x9F70A8,session)):
            put(addr,struct.pack('<Q',value))
        for addr,value in ((session,0),(inner+0x1A70,0),(base+0x9D3F71,1),
                           (base+0x9D3F72,1),(base+0x9CDDA0,1)):
            put(addr,bytes([value]))
        before=dict(mem);self.assertTrue(guard_state(base,context,read)['a0_open'])
        self.assertEqual(before,mem)
        for addr in (session,inner+0x1A70):
            put(addr,b'\x01');self.assertFalse(guard_state(base,context,read)['a0_open']);put(addr,b'\x00')
        put(inner+0x1A60,struct.pack('<Q',0))
        with self.assertRaisesRegex(ValueError,'Session owner'):guard_state(base,context,read)

    def fixture(self,count=3):
        from civ6_host.runtime import event_argument_source as p
        base=0x200000000;arg=0x1000;mem={}
        def put(addr,data):mem.update({addr+i:b for i,b in enumerate(data)})
        def read(addr,n):return bytes(mem[addr+i] for i in range(n))
        for name in ('iterator_next','get_count'):
            for f in p.body(name)['fragments']:
                for i in f['instructions']:put(base+int(i['va'],16)-0x180000000,bytes.fromhex(i['bytes']))
        put(base+0x93F590+0x1D8,struct.pack('<Q',base+0x7FCAA0))
        put(arg,struct.pack('<Q',base+0x93F590));put(arg+0x50,struct.pack('<I',count))
        put(arg+0x38,struct.pack('<Q',0x2000 if count else arg+0x30));links={}
        for n in range(count):
            node=0x2000+n*0x100;put(node+0x20,struct.pack('<I',n+1));put(node+0x28,variant(2,0xFFFFFFFF-n))
            links[node]=node+0x100 if n<count-1 else arg+0x30
        return base,arg,read,put,links,mem

    def test_xp1_shared_reader_keeps_uint_bits_and_checks_live_successor(self):
        base,arg,read,put,links,mem=self.fixture(6)
        fields=read_event_fields(arg,base,read,links.__getitem__,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(len(fields),6);self.assertEqual(fields[1],variant(2,0xFFFFFFFF))
        mem[base+0x83AFA0]^=1
        with self.assertRaisesRegex(ValueError,'instruction'):
            read_event_fields(arg,base,read,links.__getitem__,core_sha256=XP1_CORE_SHA256)

    def test_foreign_map_engine_and_count_refuse(self):
        base,arg,read,put,links,_=self.fixture()
        put(arg,struct.pack('<Q',base+0x81CFA0))
        with self.assertRaisesRegex(EventArgumentTreeError,'unverified_vtable'):
            read_event_fields(arg,base,read,links.__getitem__,core_sha256=XP1_CORE_SHA256)
        with self.assertRaises(ValueError):read_event_fields(arg,base,read,links.__getitem__,core_sha256='unknown')


def load_tests(loader,tests,pattern):
    for name in ('test_native_event_argument_tree','test_native_absent_scalar_a0'):
        path=resource_root()/'tests'/(name+'.py');module=ModuleType('retained_'+name);module.__file__=str(path)
        source=path.read_text(encoding='utf-8').replace('civ6rl.','civ6_host.runtime.native.')
        exec(compile(source,str(path),'exec'),module.__dict__)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests

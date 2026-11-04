"""C0 uses the real-getter boundary and the existing ordered queue consumer."""
import ctypes as C
import struct
from types import SimpleNamespace as NS,ModuleType
import unittest
from unittest.mock import Mock,patch
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.status_message_service import StatusMessageService
from civ6_host.runtime.native.native_host_slot_c0 import TEXT_KEY
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.retained_game_service import RetainedGameLease
from civ6_host.runtime.native.native_retained_game_getter import read_retained_game_value
from test_deferred_service import Host

PROFILE=dict(observer_registered=False,state_pointer_nonnull=True,pre_hook=None,post_hook=None,subscriber_count=0,state_flags=0)


class StatusMessageServiceTests(unittest.TestCase):
    def fixture(self):
        h=Host();core=NS(_handle=1000)
        for target in ('cache_update_profiles.verify_dispatch_live','cache_update_profiles.verify_notification_live',
                       'retained_game_source.verify_status_live'):
            p=patch('civ6_host.runtime.'+target,return_value={});p.start();self.addCleanup(p.stop)
        d=DeferredService(h,core,2000,core_sha256=XP1_CORE_SHA256,read=Mock(),emit=Mock(),
            optional_preprocessor=None,queue_metadata_service=None)
        data=b'Status\xc3\xa9\0';raw=struct.pack('<H6sQII',5,b'\0'*6,0x9000,0,1)
        a=NS(host=h,deferred=d,_check=Mock(),reader=NS(fields=Mock(return_value={TEXT_KEY:raw})))
        read=lambda addr,n:data[addr-0x9000:addr-0x9000+n]
        game=NS(value=Mock(return_value=-1),check=Mock(),close=Mock())
        p=patch('civ6_host.runtime.status_message_service.RetainedGameLease',return_value=game);p.start();self.addCleanup(p.stop)
        before=list(h.vtable);bindings=dict(h._slot_bindings)
        s=StatusMessageService(h,core,2000,a,core_sha256=XP1_CORE_SHA256,read=read,emit=Mock(),
            context_alive=Mock(return_value=True),receiver_state=PROFILE,writer_metadata_service=None,per_thread_hook=None)
        return h,d,a,s,game,before,bindings,data

    def test_true_getter_precedes_map_and_target_mismatch_does_not_read_null(self):
        h,d,a,s,g,*_=self.fixture()
        self.assertEqual(s.dispatch(h.pointer,17,0xFFFFFFFE,0),0)
        g.value.assert_called_once();a.reader.fields.assert_not_called();self.assertEqual(d.pending,[])
        self.assertEqual(s.emit.call_args.kwargs['branch'],'target_differs')
        s.close();d.close()

    def test_source_consumer_copies_text_and_commits_through_shared_queue(self):
        h,d,a,s,g,before,bindings,data=self.fixture()
        s.dispatch(h.pointer,0xFFFFFFFF,0xFFFFFFFF,1234)
        record=d.pending[0];self.assertEqual(record[84:84+len(data)],data)
        self.assertEqual(struct.unpack_from('<I',record,64)[0],0)
        self.assertEqual(struct.unpack_from('<I',record,72)[0],2)
        self.assertEqual(struct.unpack_from('<II',record,1108),(103780558,0xFFFFFFFF))
        with self.assertRaisesRegex(RuntimeError,'active consumers'):s.close()
        self.assertEqual(d.drain(),1);self.assertEqual(d.consumed_count,1);self.assertEqual(d.pending,[])
        self.assertFalse(hasattr(d,'unit_panel_event_state'))
        s.close();g.close.assert_called_once();self.assertEqual(list(h.vtable),before)
        self.assertEqual(h._slot_bindings,bindings);self.assertFalse(hasattr(d,'empty_receiver_state'))
        d.close()

    def test_cache_feedback_and_status_share_one_sequence_without_hidden_flush(self):
        h,d,a,s,g,*_=self.fixture()
        d.cache_update(h.pointer,7,(4<<32)|3)
        s.dispatch(h.pointer,17,0xFFFFFFFF,1234)
        self.assertEqual([int.from_bytes(r[8:12],'little') for r in d.pending],[1,2])
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload') as dispatch:
            self.assertEqual(d.drain(),2);self.assertEqual(dispatch.call_count,1)
        s.close();d.close()

    def test_producer_failure_after_enqueue_is_quarantined_and_never_replayed(self):
        h,d,a,s,g,*_=self.fixture();s.emit.side_effect=RuntimeError('ledger failure')
        with self.assertRaisesRegex(RuntimeError,'ledger failure'):s.dispatch(h.pointer,17,0xFFFFFFFF,1234)
        self.assertTrue(s.quarantined);self.assertEqual(len(d.pending),1)
        with self.assertRaisesRegex(RuntimeError,'poisoned'):s.dispatch(h.pointer,17,0xFFFFFFFF,1234)
        self.assertEqual(len(d.pending),1)

    def test_registered_receivers_and_optional_hooks_do_not_become_empty(self):
        h,d,a,s,g,*_=self.fixture();s.close()
        args=dict(core_sha256=XP1_CORE_SHA256,read=Mock(),emit=Mock(),context_alive=Mock(),
                  receiver_state=dict(PROFILE,subscriber_count=1),writer_metadata_service=None,per_thread_hook=None)
        with self.assertRaises(ValueError):StatusMessageService(h,d.core,d.context,a,**args)
        args.update(receiver_state=PROFILE,per_thread_hook=1)
        with self.assertRaises(ValueError):StatusMessageService(h,d.core,d.context,a,**args)
        d.close()

    def test_borrower_and_changed_receiver_prevent_unsafe_close(self):
        h,d,a,s,g,*_=self.fixture()
        with self.assertRaisesRegex(RuntimeError,'borrows'):d.close()
        d.empty_receiver_state['subscriber_count']=1
        with self.assertRaisesRegex(RuntimeError,'profile changed'):s.dispatch(h.pointer,17,0xFFFFFFFF,1234)
        d.empty_receiver_state=dict(PROFILE);s.close();d.close()


class RetainedGameIdentityTests(unittest.TestCase):
    def fixture(self):
        from civ6_host.runtime import retained_game_source as p
        base,context,inner,service,owner,game,facade=0x200000000,0x1000,0x2000,0x5000,0x6000,0x12000,0x13000
        mem={}
        def put(addr,raw):mem.update({addr+i:b for i,b in enumerate(raw)})
        def read(addr,n):return bytes(mem[addr+i] for i in range(n))
        for addr,val in ((context,base+0x8A8DF0),(context+8,inner),(base+0x9F2620,inner),
                         (inner,base+0x8D7168),(inner+0x1A68,service),(base+0x9F22E0,service),
                         (service,base+0x8D7238),(service+8,owner),(owner,base+0x867788),(owner+32,service),
                         (inner+96,game),(base+0x9F2628,game),(facade,base+0x8A9A88),(facade+8,0),
                         (facade+16,owner),(base+0x8A9A88+0x128,base+0x4C3B30)):
            put(addr,struct.pack('<Q',val))
        for f in p.body('getter')['fragments']:
            for i in f['instructions']:put(base+int(i['va'],16)-0x180000000,bytes.fromhex(i['bytes']))
        lease=RetainedGameLease.__new__(RetainedGameLease)
        lease.core_base,lease.context,lease.read=base,context,read
        lease.core_sha256,lease.abi=XP1_CORE_SHA256,p.getter_abi(XP1_CORE_SHA256)
        lease.thread=__import__('threading').get_ident();lease._alive=lambda:True
        lease._closed=lease.quarantined=False;lease.game_facade=facade;lease.backend=lease
        lease.identity=p.context_state(base,context,read)
        return p,lease,put,mem

    def test_xp1_calls_exact_signed_getter_not_host_local_identity(self):
        p,lease,put,mem=self.fixture();lease.check();invoke=Mock(return_value=-1)
        self.assertEqual(read_retained_game_value(lease,lease.read,invoke=invoke,core_sha256=XP1_CORE_SHA256),-1)
        invoke.assert_called_once_with(lease.core_base+0x4C3B30,lease.game_facade)
        mem[lease.core_base+0x4C3B30]^=1
        with self.assertRaisesRegex(ValueError,'code differs'):
            read_retained_game_value(lease,lease.read,invoke=invoke,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(invoke.call_count,1)

    def test_stale_owner_after_clear_and_live_object_branch_are_refused(self):
        p,lease,put,mem=self.fixture()
        put(lease.identity['service']+8,struct.pack('<Q',0))
        with self.assertRaisesRegex(ValueError,'cache owner'):lease.value()
        put(lease.identity['service']+8,struct.pack('<Q',lease.identity['owner']))
        put(lease.game_facade+8,struct.pack('<Q',lease.identity['game']))
        with self.assertRaisesRegex(ValueError,'real native cache'):lease.value()
        lease._alive=lambda:False
        with self.assertRaisesRegex(RuntimeError,'closed'):lease.close()


def load_tests(loader,tests,pattern):
    for name in ('test_native_retained_game_getter','test_native_host_slot_c0'):
        p=resource_root()/'tests'/(name+'.py');m=ModuleType('retained_'+name);m.__file__=str(p)
        source=p.read_text(encoding='utf-8').replace('civ6rl.','civ6_host.runtime.native.').replace('from civ6rl import','from civ6_host.runtime.native import')
        # Historical evidence schemas are data, not module imports.
        source=source.replace('civ6_host.runtime.native.native_host_slot_c0.static.v1','civ6rl.native_host_slot_c0.static.v1')
        if name=='test_native_retained_game_getter':
            # Extraction makes the publisher's previously implicit Base choice
            # explicit. Keep the historical test file/hash untouched.
            old='read.assert_called_once_with(publisher._facades, publisher.read)'
            if source.count(old)!=1:raise ValueError('Retained publisher test seam changed')
            source=source.replace(old,"read.assert_called_once_with(publisher._facades, publisher.read, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')")
        exec(compile(source,str(p),'exec'),m.__dict__)
        tests.addTests(loader.loadTestsFromModule(m))
    return tests

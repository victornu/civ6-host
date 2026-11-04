"""Actual shared lease, query owner and FIFO; native memory/calls are fixtures."""
import ctypes as C
import struct
import unittest
from unittest.mock import Mock,patch
from civ6_host.runtime import xp2_player_query_source as source
from civ6_host.runtime import player_notification_profiles as profiles
from civ6_host.runtime.saved_load_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.native import native_player_notifications as notifications
from civ6_host.runtime.native.native_core_lock import NativeCoreLock
from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
from civ6_host.runtime.player_notification_service import PlayerNotificationService
from civ6_host.runtime.status_message_service import StatusMessageService
import test_player_notification_profiles as shared
import test_xp2_preload_services as preload
from test_event_argument_service import variant


class XP2Fixture(shared.NotificationFixture):
    base=0x300000000
    def __init__(self,**kw):super().__init__(core_sha256=XP2_CORE_SHA256,**kw)


class XP2PlayerNotificationTests(unittest.TestCase):
    def test_static_complete_profiles_and_aslr_body_slot_lock_checks(self):
        p=source.source();self.assertEqual(len(p['bodies']),20)
        self.assertTrue(source.source_dependencies())
        f=XP2Fixture()
        for b in p['bodies'].values():
            for part in b['fragments']:f.put_bytes(f.base+int(part['start_rva'],16),bytes.fromhex(part['raw_hex']))
        f.put(f.base+0xb8aa80,0x1234)
        source.verify_live(f.base,f.read,host_pointer=0x1234)
        with self.assertRaisesRegex(ValueError,'HOST lock'):
            source.verify_live(f.base,f.read,host_pointer=0x5678)
        f.put_bytes(f.base+0x5a0157,b'\x90')
        with self.assertRaisesRegex(ValueError,'native body'):
            source.verify_live(f.base,f.read,host_pointer=0x1234)

    def test_positive_query_order_full_unsigned_values_and_engine_specific_member(self):
        f=XP2Fixture()
        with f.lease(0xffffffff) as values:
            self.assertEqual(values,{'getter_10_uint32':0xffffffff,'getter_18_uint32':0x80000001})
            f.events.append(('consume',))
        self.assertEqual([x[0] for x in f.events],['get_player','get_component','getter_18','getter_10','consume','release_component','release_player'])
        f=XP2Fixture();f.put(f.player_live+0x560,f.component_live);f.put(f.player_live+0x780,0)
        with self.assertRaisesRegex(ValueError,'foreign or missing owner'):
            with f.lease(0):self.fail('XP1 offset accepted for XP2')
        self.assertEqual([x[0] for x in f.events][-2:],['release_component','release_player'])

    def test_native_null_and_corrupt_slots_preserve_release_contract(self):
        f=XP2Fixture(player_present=False)
        with f.lease(65) as value:self.assertIsNone(value)
        self.assertEqual(f.events,[('get_player',f.manager,65)])
        f=XP2Fixture(component_present=False)
        with f.lease(0) as value:self.assertIsNone(value)
        self.assertEqual([x[0] for x in f.events],['get_player','get_component','release_player'])
        f=XP2Fixture();a=f.constants
        f.put(f.base+a['COMPONENT_VTABLE_RVA']+a['COMPONENT_GETTER_10_SLOT'],0xdeadbeef)
        with self.assertRaisesRegex(ValueError,'vtable slot'):
            with f.lease(0):pass
        self.assertEqual([x[0] for x in f.events],['get_player','get_component','release_player'])


class XP2ComposedNotificationTests(unittest.TestCase):
    memory=preload.XP2PreloadServices.memory
    compose=preload.XP2PreloadServices.compose
    tree=preload.XP2PreloadServices.tree

    def test_treasury_event_uses_actual_query_and_shared_fifo_before_release(self):
        h,d,ctl,a=self.compose()
        consumer=a.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
            pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE),entity_listener_count=0)
        f=XP2Fixture()
        lock=NativeCoreLock.__new__(NativeCoreLock);lock.host=h
        lock.calls={name:Mock(return_value=0 if name=='owned' else 1) for name in ('owned','acquire','release','try_acquire')}
        for slot,name,result in ((0x30,'owned',C.c_bool),(0x38,'release',None),(0x40,'acquire',None),(0x48,'try_acquire',C.c_bool)):
            h._bind(h.vtable,slot,result,[C.c_void_p],getattr(lock,name))
        # The service's context check is the native boundary; its selected ABI,
        # generated query algorithm, producer and deferred queue are all real.
        with patch.object(profiles,'verify_query_live',return_value={'identity':{'game':3}}) as verify, \
             patch.object(profiles,'context_identity',return_value={'game':3}), \
             patch.object(notifications,'_native_calls',return_value=f.calls):
            f.put(self.context,f.base+f.constants['PLAYER_MANAGER_VTABLE_RVA'])
            o=PlayerNotificationService(h,d.core,d.context,core_sha256=XP2_CORE_SHA256,read=f.read,context_alive=lambda:True,core_lock=lock)
            self.assertEqual(verify.call_args.kwargs['core_sha256'],XP2_CORE_SHA256)
            consumer.enable_player_queries(o)
            real_enqueue=d._enqueue
            def enqueue(record):
                self.assertEqual(o.depth,1)
                self.assertNotIn('release_component',[x[0] for x in f.events])
                f.events.append(('enqueue',));return real_enqueue(record)
            d._enqueue=enqueue
            pointer,a.reader.next_node=self.tree({0xa1e5a149:variant(3),0xd6fcf3e4:variant(2,7)})
            self.assertEqual(a.dispatch(h.pointer,0x20f2116e,pointer),0)
            self.assertEqual([x[0] for x in f.events],['get_player','get_component','getter_18','getter_10','enqueue','release_component','release_player'])
            self.assertEqual(struct.unpack_from('<II',d.pending[0],88),(0xffffffff,0x80000001))
            self.assertEqual(d.drain(),1)
            a.close();o.close();ctl.close();d.close()

    def test_status_queries_native_boundary_before_copying_into_same_fifo(self):
        h,d,ctl,a=self.compose()
        data=b'XP2 status\0';self.put(0x9000,data)
        from civ6_host.runtime.native.native_host_slot_c0 import TEXT_KEY
        raw=struct.pack('<H6sQII',5,b'\0'*6,0x9000,0,1)
        ptr,a.reader.next_node=self.tree({TEXT_KEY:raw})
        game=Mock();game.value.return_value=-1
        with patch('civ6_host.runtime.retained_game_source.verify_status_live',return_value={}) as verify, \
             patch('civ6_host.runtime.status_message_service.RetainedGameLease',return_value=game):
            s=StatusMessageService(h,d.core,d.context,a,core_sha256=XP2_CORE_SHA256,read=self.read,emit=Mock(),
                context_alive=lambda:True,receiver_state=dict(EMPTY_RECEIVER_STATE),writer_metadata_service=None,per_thread_hook=None)
            self.assertEqual(verify.call_args.kwargs['core_sha256'],XP2_CORE_SHA256)
            s.dispatch(h.pointer,17,0xffffffff,ptr)
            self.assertEqual(d.pending[0][84:84+len(data)],data)
            self.assertEqual(d.drain(),1);s.close();game.close.assert_called_once()
        a.close();ctl.close();d.close()


if __name__=='__main__':unittest.main()

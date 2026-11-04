"""Lease ownership and A0 ordering with fixtures; no native gameplay claims."""
from contextlib import contextmanager
import ctypes as C
import struct
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native.native_core_lock import NativeCoreLock
from civ6_host.runtime.player_notification_service import PlayerNotificationService
import test_a0_family_service as fixtures


class PlayerNotificationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.profile=family_profile()

    def fixture(self):
        h,d,a,c,r,before,bindings=fixtures.A0FamilyServiceTests.fixture(self)
        lock=NativeCoreLock.__new__(NativeCoreLock);lock.host=h
        lock.calls={name:Mock(return_value=0 if name=='owned' else 1)
                    for name in ('owned','acquire','release','try_acquire')}
        for slot,name,result in ((0x30,'owned',C.c_bool),(0x38,'release',None),
                                  (0x40,'acquire',None),(0x48,'try_acquire',C.c_bool)):
            h._bind(h.vtable,slot,result,[C.c_void_p],getattr(lock,name))
        for target in ('verify_query_live','context_identity'):
            value={'identity':{'game':3}} if target=='verify_query_live' else {'game':3}
            p=patch('civ6_host.runtime.player_notification_profiles.'+target,return_value=value)
            p.start();self.addCleanup(p.stop)
        owner=PlayerNotificationService(h,d.core,d.context,core_sha256=XP1_CORE_SHA256,
            read=r.read,context_alive=lambda:True,core_lock=lock)
        return h,d,a,c,r,owner,lock

    def mock_query(self,values,order):
        @contextmanager
        def query(base,context,index,**kwargs):
            order.append(('query',index,kwargs['core_sha256']))
            try:yield values
            finally:order.append(('released',))
        p=patch('civ6_host.runtime.player_notification_service.query_player_notification_values',side_effect=query)
        p.start();self.addCleanup(p.stop)

    def send(self,h,a,r,index):
        return fixtures.A0FamilyServiceTests.send(self,h,a,r,0x20F2116E,(index,))

    def test_event_enqueues_inside_lease_and_owner_closes_after_borrower(self):
        h,d,a,c,r,o,lock=self.fixture();order=[]
        self.mock_query({'getter_10_uint32':0xFFFFFFFF,'getter_18_uint32':0xAABBCCDD},order)
        c.enable_player_queries(o)
        with self.assertRaisesRegex(RuntimeError,'borrowers'):o.close()
        native_enqueue=d._enqueue
        def enqueue(record):
            self.assertEqual(o.depth,1);self.assertNotIn(('released',),order)
            order.append(('enqueue',));return native_enqueue(record)
        d._enqueue=enqueue
        self.assertEqual(self.send(h,a,r,7),0)
        self.assertEqual([x[0] for x in order],['query','enqueue','released'])
        self.assertEqual(struct.unpack_from('<II',d.pending[0],88),(0xFFFFFFFF,0xAABBCCDD))
        self.assertEqual(d.drain(),1);a.close();o.close();d.close()
        self.assertIsNone(o._a0_event_owner);self.assertTrue(o.closed)

    def test_native_null_does_not_create_a_record_or_change_sequence(self):
        h,d,a,c,r,o,lock=self.fixture();order=[];self.mock_query(None,order)
        c.enable_player_queries(o)
        for index in (0,64,65,0xFFFFFFFF):self.assertEqual(self.send(h,a,r,index),0)
        self.assertFalse(d.pending);self.assertEqual(d._sequence,0)
        self.assertEqual([x[1] for x in order if x[0]=='query'],[0,64,65,0xFFFFFFFF])
        a.close();o.close();d.close()

    def test_failure_keeps_native_release_order_and_quarantines(self):
        h,d,a,c,r,o,lock=self.fixture();order=[]
        self.mock_query({'getter_10_uint32':1,'getter_18_uint32':2},order)
        c.enable_player_queries(o);d.limit=0
        with self.assertRaises(ValueError):self.send(h,a,r,0)
        self.assertEqual([x[0] for x in order],['query','released'])
        self.assertTrue(o.quarantined and c.quarantined and a.quarantined)
        with self.assertRaises(RuntimeError):o.close()

    def test_lock_replacement_prevents_query(self):
        h,d,a,c,r,o,lock=self.fixture();order=[];self.mock_query(None,order)
        h.vtable[0x40//8]+=8
        with self.assertRaisesRegex(RuntimeError,'lock changed'):
            with o.query(0):pass
        self.assertFalse(order);self.assertTrue(o.quarantined)

    def test_active_and_reentrant_leases_are_refused(self):
        h,d,a,c,r,o,lock=self.fixture();order=[];self.mock_query(None,order)
        with o.query(1):
            with self.assertRaisesRegex(RuntimeError,'active'):o.close()
            with self.assertRaisesRegex(RuntimeError,'Reentrant'):
                with o.query(2):pass
        self.assertFalse(o.quarantined);o.close()

    def test_foreign_or_duplicate_event_owner_is_refused(self):
        h,d,a,c,r,o,lock=self.fixture()
        real=o.context;o.context+=1
        with self.assertRaises(ValueError):c.enable_player_queries(o)
        o.context=real;c.enable_player_queries(o)
        with self.assertRaises(ValueError):c.enable_player_queries(o)
        a.close();o.close();d.close()

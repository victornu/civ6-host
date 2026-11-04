"""XP1 reward notification on the real saved owner, A0 producer and FIFO.

Only native memory/calls are fixtures. No reward is calculated here and no
GameCore is loaded. The descriptor belongs to the Core during the callback.
"""
import struct
import unittest

from test_xp1_placement_events import Fixture
from test_goody_hut_reward import raw_fields
from civ6_host.runtime import goody_hut_reward as shared
from civ6_host.runtime import xp1_goody_hut_profile as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256


class GoodyHutEventsTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_unit_city_borrow_copied_once_real_fifo_with_nonzero_scopes(self):
        f=self.fixture();f.deferred.host_notification_counter=2;f.deferred.host_metadata_counter=3
        native_read=f.owner.read;borrow_reads=[]
        def read(pointer,size):
            if pointer==0x1000:borrow_reads.append((pointer,size))
            return native_read(pointer,size)
        f.owner.read=read
        for sequence,city in enumerate((False,True),1):
            blob=struct.pack('<HHI',5,2 if city else 1,131073)
            f.memory.put(0x1000,blob)
            before=len(borrow_reads)
            self.assertEqual(f.owner.dispatch(shared.EVENT_KIND,raw_fields(city),0),0)
            self.assertEqual(borrow_reads[before:],[(0x1000,8)])
            record=f.deferred.pending[-1]
            self.assertEqual(struct.unpack_from('<4I',record),(112,259,sequence,0))
            self.assertEqual(struct.unpack_from('<I',record,72)[0],4)
            self.assertEqual(struct.unpack_from('<HHI',record,24),
                             (0xffff,0,0xffffffff) if city else (5,1,131073))
            self.assertEqual(struct.unpack_from('<HHI',record,88),
                             (0xffff,1,0xffffffff) if city else (5,1,131073))
            self.assertEqual(struct.unpack_from('<2I',record,96),(0xc04b8e18,0x030ace7b))
            self.assertEqual((f.owner.host_notification_counter,f.owner.host_metadata_counter),(2,3))
            self.assertEqual(f.calls,[])
            # The owner must not release this Core-owned descriptor, nor retain
            # its pointer: invalidate it before consuming the owned queue copy.
            self.assertEqual(f.memory.blocks.pop(0x1000),blob)
        before=len(borrow_reads)
        self.assertEqual(f.deferred.drain(),2);self.assertEqual(f.deferred.drain(),0)
        self.assertEqual(len(borrow_reads),before)
        self.assertEqual(f.deferred.consumed_count,2);self.assertEqual(f.deferred.consumed_bytes,224)
        self.assertEqual(f.deferred.pending,[]);self.assertIsNone(f.owner._foundation_borrow)
        receipts=[r for stage,r in f.emitted if stage=='native_deferred_host_event_enqueued'
                  and r.get('dispatch_kind')==hex(shared.EVENT_KIND)]
        self.assertEqual([r['source_descriptor'] for r in receipts],['unit','city'])
        for r in receipts:
            self.assertEqual(r['core_proof_sha256'],profile.SOURCE[1])
            self.assertEqual(r['source_proof_sha256'],shared.EXE_PROOF_SHA256)
            self.assertFalse(r['reward_calculated_by_host']);self.assertFalse(r['native_internal_dispatch_repeated'])
            self.assertFalse(r['undefined_value_is_native_default']);self.assertFalse(r['payload_exposed_to_learner'])

    def test_malformed_borrow_and_receiver_refused_on_composed_owner(self):
        cases=('wrong_kind','short_borrow','wrong_flags','subscriber')
        for case in cases:
            with self.subTest(case=case):
                f=self.fixture();fields=raw_fields()
                f.memory.put(0x1000,struct.pack('<HHI',5,2 if case=='wrong_kind' else 1,131073))
                if case=='short_borrow':
                    # Replace this native read only, keeping the exact owner,
                    # source/boundary checks and all other native memory reads.
                    previous=f.owner.read
                    f.owner.read=lambda p,n,old=previous:bytes(7) if (p,n)==(0x1000,8) else old(p,n)
                if case=='wrong_flags':fields[shared.UNIT_KEY]=struct.pack('<HHIQII',0x400,0,1,0x1000,8,0)
                if case=='subscriber':f.owner.empty_receiver_state['subscriber_count']=1
                expected=RuntimeError if case=='subscriber' else ValueError
                with self.assertRaises(expected):f.owner.dispatch(shared.EVENT_KIND,fields,0)
                self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.deferred._sequence,0)
                self.assertIsNone(f.owner._foundation_borrow);self.assertEqual(f.calls,[])

    def test_selected_source_live_owner_and_unknown_engine_guards(self):
        f=self.fixture();self.assertEqual(profile.bind_owner(f.backend,f.backend.core,f.read),profile.SOURCE[1])
        with self.assertRaisesRegex(ValueError,'foreign native owner'):profile.bind_owner(f.backend,object(),f.read)
        p=profile.verify_source();row=p['functions']['0x518a80']['instructions'][0]
        address=f.memory.base+int(row['va'],16)-0x180000000
        raw=bytes.fromhex(row['bytes']);f.memory.put(address,bytes([raw[0]^1])+raw[1:])
        with self.assertRaisesRegex(ValueError,'live source changed'):profile.bind_owner(f.backend,f.backend.core,f.read)
        with self.assertRaisesRegex(ValueError,'Unqualified'):shared.verify_source(core_sha256='0'*64)
        selected,_=shared.verify_source(core_sha256=XP1_CORE_SHA256)
        self.assertIs(selected,p)
        # Default Base callers keep their historical evidence; XP1 is explicit.
        base,_=shared.verify_source();self.assertEqual(base['schema'],'civ6-host.event-c08-core-source.v1')


if __name__=='__main__':unittest.main()

"""Private-ring/A0 integration fixtures; no native GameCore execution."""
from dataclasses import replace
from pathlib import Path
import struct,sys,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'work/xp1-action-integration/transport-tests'))
import test_found_unit_a0 as fixture
from civ6_host.runtime import a0_private_notifications as events
from civ6_host.runtime import xp1_private_notification_profile as profile
from civ6_host.runtime.native.native_private_ring_consumer import BANK_CAPACITY


def fields54(descriptor=17,value=36871):
    return {0xa1e5a149:fixture.scalar(3,0),0xa1fbc372:fixture.scalar(2,value),
            0xd6fcf3e4:fixture.scalar(2,descriptor)}
def fields57(value=1):return {0xa1e5a149:fixture.scalar(3,0),0xd6fcf3e4:fixture.scalar(2,value)}


class PrivateNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.PROFILE=fixture.a0_family_source.family_profile()
        cls.proof=profile.verify_source()

    def fixture(self):
        f=fixture.Fixture();f.deferred.cache_core_sha256=profile.XP1_CORE_SHA256
        with patch.object(profile,'verify_live',return_value={'offline_native_code_boundary':True}) as verify:
            events.enable(f.owner)
            verify.assert_called_once_with(f.deferred.core._handle,f.owner.read,core_sha256=profile.XP1_CORE_SHA256)
        return f

    def test_source_closure_and_relocated_producer_bytes(self):
        base=0x25000000000;memory={}
        for body in self.proof['functions'].values():
            for fragment in body.get('fragments') or (body,):
                for row in fragment['instructions']:
                    address=base+int(row['va'],16)-0x180000000
                    memory.update({address+i:b for i,b in enumerate(bytes.fromhex(row['bytes']))})
        read=lambda address,size:bytes(memory[address+i] for i in range(size))
        result=profile.verify_live(base,read)
        self.assertFalse(result['native_execution'])
        self.assertIn(profile.SOURCE[1],profile.source_dependencies().values())
        memory[base+0x519650]^=1
        with self.assertRaisesRegex(ValueError,'code differs'):profile.verify_live(base,read)
        with self.assertRaises(ValueError):profile.verify_live(base,read,core_sha256='unknown')

    def test_retained_base_dual_bytes_real_fifo_and_private_drain_order(self):
        for interval in self.proof['base_intervals']:
            with self.subTest(interval=interval['label']):
                f=self.fixture();owner=f.owner;ring=events.get_ring(owner)
                first,second=(r['event'] for r in interval['records'])
                expected54=bytes.fromhex(first['record_hex']);descriptor,value=struct.unpack_from('<II',expected54,16)
                expected57=bytes.fromhex(second['private_record_hex']);turn=struct.unpack_from('<I',expected57,16)[0]
                f.deferred.host_notification_counter=2;f.deferred.host_metadata_counter=9
                self.assertEqual(owner.dispatch(0x1be52206,fields54(descriptor,value),0),0)
                self.assertEqual(owner.dispatch(0x66ade3b3,fields57(turn),0),0)
                self.assertEqual(ring.bank_prefix(0),expected54+expected57)
                expected_standard=bytearray.fromhex(second['record_hex'])
                struct.pack_into('<I',expected_standard,8,1);struct.pack_into('<I',expected_standard,80,1)
                self.assertEqual(f.deferred.pending,[bytes(expected_standard)])
                self.assertEqual((f.deferred.host_notification_counter,f.deferred.host_metadata_counter),(2,9))
                with self.assertRaisesRegex(ValueError,'standard FIFO'):events.drain(owner)
                self.assertEqual(f.deferred.drain(),1)
                self.assertEqual(ring.selector,1);self.assertEqual(ring.cursors,(256,0))
                names=[r[0] for r in f.emitted]
                self.assertLess(names.index('native_deferred_empty_record_consumed'),names.index('native_private_empty_drain_completed'))
                report=next(r[1] for r in f.emitted if r[0]=='native_private_empty_drain_completed')
                self.assertEqual(report['counts_by_type'],{'0x54':1,'0x57':1})
                self.assertEqual(f.reads,[])
                self.assertEqual(events.check_close(owner)['bank_cursors'],[256,0])

    def test_rotation_preserves_unwritten_bytes_and_close_refuses_live_records(self):
        f=self.fixture();ring=events.get_ring(f.owner)
        ring._banks[0][100]=0xA7  # Explicit fixture for stale, producer-unwritten bytes.
        f.owner.dispatch(0x1be52206,fields54(),0)
        with self.assertRaisesRegex(RuntimeError,'unconsumed'):events.check_close(f.owner)
        f.deferred.drain();f.owner.dispatch(0x1be52206,fields54(22,33),0);f.deferred.drain()
        f.owner.dispatch(0x1be52206,fields54(44,55),0)
        self.assertEqual(ring.bank_prefix(0)[100],0xA7)
        self.assertEqual(struct.unpack_from('<II',ring.bank_prefix(0),16),(44,55))
        f.deferred.drain();self.assertEqual(events.check_close(f.owner)['flush_count'],3)

    def test_registered_private_listener_refused_without_fake_consumption(self):
        f=self.fixture();ring=events.get_ring(f.owner)
        f.owner.dispatch(0x1be52206,fields54(),0)
        rows=dict(ring._table_state);row=rows[0x54];raw=bytearray(row.list_bytes)
        struct.pack_into('<I',raw,32,1);rows[0x54]=replace(row,list_bytes=bytes(raw));ring._table_state=rows
        with self.assertRaisesRegex(ValueError,'listeners'):f.deferred.drain()
        self.assertTrue(ring.poisoned);self.assertTrue(f.deferred._deferred_drain_poisoned)
        self.assertEqual(ring.cursors,(128,0));self.assertEqual(ring.selector,1)
        self.assertFalse(any(n=='native_private_empty_drain_completed' for n,_ in f.emitted))
        with self.assertRaises((ValueError,RuntimeError)):events.check_close(f.owner)

    def test_full_private_ring_keeps_dual_standard_record_and_poisoned_owner(self):
        f=self.fixture();ring=events.get_ring(f.owner);ring._cursors[0]=BANK_CAPACITY
        with self.assertRaisesRegex(ValueError,'full'):f.owner.dispatch(0x66ade3b3,fields57(),0)
        self.assertTrue(f.owner.quarantined);self.assertEqual(len(f.deferred.pending),1)
        self.assertEqual(struct.unpack_from('<I',f.deferred.pending[0],4)[0],5)
        self.assertEqual(ring.cursors,(BANK_CAPACITY,0));self.assertEqual(ring.selector,0)
        self.assertFalse(any(n=='native_turn_complete_dual_records_retained' for n,_ in f.emitted))

    def test_foreign_profile_duplicate_and_malformed_fields_fail_closed(self):
        f=self.fixture()
        with patch.object(profile,'verify_live') as verify,self.assertRaises(ValueError):events.enable(f.owner)
        verify.assert_not_called()
        f.owner.private_notification_profile=object()
        with self.assertRaises((ValueError,RuntimeError)):events.get_ring(f.owner)
        g=self.fixture();fields=fields54();fields[0xd6fcf3e4]=fixture.scalar(3,7)
        with self.assertRaises(ValueError):g.owner.dispatch(0x1be52206,fields,0)
        self.assertTrue(g.owner.quarantined);self.assertEqual(g.owner.private_progress_ring.cursors,(0,0))

if __name__=='__main__':unittest.main()

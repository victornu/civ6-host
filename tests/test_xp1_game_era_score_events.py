"""Changed history→score dependency on the actual saved owner and FIFO."""
import struct
import unittest
from test_xp1_placement_events import Fixture
from test_xp1_game_history_events import fields
from civ6_host.runtime import game_history_event_profile as history
from civ6_host.runtime import game_era_score_event_profile as score
from civ6_host.runtime import a0_game_history_events as shared
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record


class EraScoreTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_history_then_score_same_owner_and_fifo_exact_order(self):
        f=self.fixture();f.deferred.host_notification_counter=1;f.deferred.host_metadata_counter=3
        self.assertEqual(f.owner.dispatch(history.HISTORY_KIND,fields(0,19),0),0)
        self.assertEqual(f.owner.dispatch(score.EVENT_KIND,fields(0,1),0),0)
        self.assertEqual(len(f.deferred.pending),2)
        for sequence,(record_type,flag,a,b) in enumerate(((0x105,0,0,19),(0x10a,6,0,1)),1):
            record=f.deferred.pending[sequence-1]
            self.assertEqual(struct.unpack_from('<4I',record),(96,record_type,sequence,0))
            self.assertEqual(struct.unpack_from('<I',record,72)[0],flag)
            self.assertEqual(struct.unpack_from('<3I',record,80),(sequence,a,b))
        self.assertEqual(f.calls,[])
        self.assertEqual((f.owner.host_notification_counter,f.owner.host_metadata_counter),(1,3))
        self.assertEqual(f.deferred.drain(),2);self.assertEqual(f.deferred.consumed_count,2)
        self.assertEqual(f.deferred.drain(),0);self.assertIsNone(f.owner._foundation_borrow)
        emitted=[row for stage,row in f.emitted if stage=='native_deferred_host_event_enqueued'
                 and row.get('dispatch_kind')==hex(score.EVENT_KIND)]
        self.assertEqual(len(emitted),1);self.assertEqual(emitted[0]['source_proof_sha256'],score.SOURCE[1])
        # The native notification ID is not an A0 callback, and must stay out.
        self.assertFalse(f.owner.handles_kind(0x0c19b649))

    def test_score_exact_source_switch_table_fields_and_receiver_refusals(self):
        p=score.verify_source();old,_=history.verify_source()
        changed={'instructions':[dict(row) for row in p['functions']['exe']['0x14b8d0']['instructions']]}
        target=next(row for row in changed['instructions'] if tuple(row.get('rip_targets',()))==('0x1412c6804',))
        target['rip_targets']=['0x1412c6808']
        with self.assertRaisesRegex(ValueError,'RIP target changed'):
            score._verify_rip_targets(changed,old['neighbors'][0]['functions']['0x147200'],
                hook_relocation=(('0x1412c9980',),('0x1412c9aa0',)))
        f=self.fixture();score.bind_owner(f.backend,f.backend.core,f.read)
        with self.assertRaisesRegex(ValueError,'foreign native owner'):score.bind_owner(f.backend,object(),f.read)
        f.memory.put(f.memory.base+0x190388,bytes(68))
        with self.assertRaisesRegex(ValueError,'switch table changed'):score.bind_owner(f.backend,f.backend.core,f.read)
        record=shared.encode(score.EVENT_KIND,fields(0,1),1,normalizer_transform_present=False,
            optional_callback_present=False,queue_metadata_service=None)
        state={**f.owner.empty_receiver_state,'subscriber_count':1}
        with self.assertRaisesRegex(ValueError,'subscriber'):validate_empty_profile_record(record,**state)
        malformed=fields();del malformed[0xa1fbc372]
        with self.assertRaisesRegex(ValueError,'argument keys'):f.owner.dispatch(score.EVENT_KIND,malformed,0)
        self.assertTrue(f.owner.quarantined);self.assertEqual(f.deferred.pending,[])
        self.assertEqual(f.deferred._sequence,0);self.assertIsNone(f.owner._foundation_borrow)


if __name__=='__main__':unittest.main()

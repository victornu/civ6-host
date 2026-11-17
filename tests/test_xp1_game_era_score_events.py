"""Changed history→score dependency on the actual saved owner and FIFO."""
import struct
import unittest
from dataclasses import replace
from pathlib import Path
from test_xp1_placement_events import Fixture
from test_xp1_game_history_events import fields
from civ6_host.runtime import game_history_event_profile as history
from civ6_host.runtime import game_era_score_event_profile as score
from civ6_host.runtime import a0_game_history_events as shared
from civ6_host.runtime.execution_images import _XP1_PROFILE
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

    def test_installed_short_shape_on_saved_owner_and_fifo(self):
        f = self.fixture()
        f.backend.core._civ6_host_execution_image = _XP1_PROFILE
        short = fields(71, 0xffffffff)
        del short[0xa1fbc372]
        self.assertEqual(f.owner.dispatch(score.EVENT_KIND, short, 0), 0)
        self.assertEqual(f.owner.dispatch(score.EVENT_KIND, fields(73, 9), 0), 0)
        self.assertEqual(set(short), score.SHORT_KEYS)
        for sequence, (a, b) in enumerate(((71, 0), (73, 9)), 1):
            record = f.deferred.pending[sequence - 1]
            self.assertEqual(struct.unpack_from('<4I', record), (96, 0x10a, sequence, 0))
            self.assertEqual(struct.unpack_from('<I', record, 72)[0], 6)
            self.assertEqual(struct.unpack_from('<3I', record, 80), (sequence, a, b))
        self.assertEqual(f.deferred.drain(), 2)
        self.assertEqual(f.calls, [])
        rows = [row for stage, row in f.emitted if stage == 'native_deferred_host_event_enqueued'
                and row.get('dispatch_kind') == hex(score.EVENT_KIND)]
        self.assertEqual([row['source_proof_sha256'] for row in rows],
                         [score.INSTALLED_SHORT_SOURCE[1], score.SOURCE[1]])

    def test_installed_short_profile_keys_tags_flags_selector_and_core_bytes(self):
        f = self.fixture()
        from extract_phase31_next_export import pefile

        proof = score._installed_short_source()
        pins = score.installed_short_source_dependencies(_XP1_PROFILE)
        self.assertEqual(pins[str(Path(proof['executable']['path']).resolve())],
                         proof['executable']['sha256'])
        self.assertIn(score.INSTALLED_SHORT_SOURCE[1], pins.values())
        f.backend.core._civ6_host_execution_image = _XP1_PROFILE
        pe = pefile.PE(_XP1_PROFILE.path, fast_load=True)
        self.addCleanup(pe.close)
        short_spans = {f.memory.base + row['rva']: (row['rva'], row['bytes'])
                       for row in proof['core'].values()}

        def read(address, size):
            span = short_spans.get(address)
            return pe.get_data(*span) if span is not None and span[1] == size else f.read(address, size)

        score.bind_owner(f.backend, f.backend.core, read)
        changed_address, (_, changed_size) = next(iter(short_spans.items()))

        def changed_read(address, size):
            raw = read(address, size)
            if (address, size) == (changed_address, changed_size):
                return bytes([raw[0] ^ 1]) + raw[1:]
            return raw

        with self.assertRaisesRegex(ValueError, 'short era-score native source changed'):
            score.bind_owner(f.backend, f.backend.core, changed_read)

        sample = {key: raw for key, raw in fields(7, 99).items() if key in score.SHORT_KEYS}

        def encode(raw, image):
            return shared.encode(score.EVENT_KIND, raw, 1, normalizer_transform_present=False,
                                 optional_callback_present=False, queue_metadata_service=None,
                                 execution_image=image)

        for image in (None, replace(_XP1_PROFILE)):
            with self.subTest(image=image):
                with self.assertRaisesRegex(ValueError, 'argument keys'):
                    encode(sample, image)

        def update(raw, offset, value):
            changed = bytearray(raw)
            struct.pack_into('<I', changed, offset, value)
            return bytes(changed)

        for key, offset, value in ((score.SELECTOR_KEY, 0, 2), (score.SELECTOR_KEY, 8, 1),
                                   (score.VALUE_KEY, 0, 3), (score.VALUE_KEY, 20, 1)):
            malformed = {**sample, key: update(sample[key], offset, value)}
            with self.subTest(key=key, offset=offset):
                with self.assertRaises(ValueError):
                    encode(malformed, _XP1_PROFILE)
        with self.assertRaisesRegex(ValueError, 'argument keys'):
            encode({**sample, 42: sample[score.VALUE_KEY]}, _XP1_PROFILE)


if __name__=='__main__':unittest.main()

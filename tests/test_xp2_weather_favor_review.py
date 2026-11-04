"""Offline semantic review of retained XP2 records; never amend acceptance."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

import qualify_xp1_configuration as q
import review_xp1_session as review
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.stdout_transport_profiles import session_records
from civ6_host.runtime import xp2_turn_event_profile as weather


HOST=Path(__file__).resolve().parents[1]
RUN=resource_root()/'work/xp2-client-sessions/run-aaf5be223aac4d2cae611caf076b15c9'
ARCHIVE=HOST/'work/xp2-session-integration/native-session08/executed-sources.zip'


class XP2WeatherFavorReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure=json.loads((RUN/'closure.json').read_bytes())
        cls.report=json.loads((RUN/'supervisor.json').read_bytes())
        cls.original_pins={name:review.pin(RUN/name)['sha256'] for name in (
            'events.jsonl','client-acceptance.json','supervisor.json','loaded-lifetime-result.json')}
        cls.records=list(session_records(RUN,report=cls.report))
        events=q.saved_load_events(RUN/'events.jsonl',allow_multiple_commands=True,allow_turn_updates=True,
            stdout_transport=cls.closure['stdout_transport'],stdout_native_records=cls.report['stdout_native_records'],
            stdout_limit_bytes=cls.closure['stdout_limit_bytes'])[1]
        cls.intervals=events['_transition_intervals']
        cls.result=review.review_xp2_weather_favor(RUN,cls.closure,cls.report,ARCHIVE,cls.intervals)
        cls.storm=next(i for i,(_,_,e) in enumerate(cls.records)
                       if e['stage']=='native_xp2_climate_event_enqueued' and e['dispatch_kind']=='0x13b135e4')
        cls.random=next(i for i,(_,_,e) in enumerate(cls.records)
                        if e['stage']=='native_xp2_climate_event_enqueued' and e['dispatch_kind']=='0xe869c8ff')
        cls.favor=next(i for i,(_,_,e) in enumerate(cls.records) if e['stage']=='native_xp2_turn_event_enqueued')
        cls.consumed=next(i for i,(_,_,e) in enumerate(cls.records)
                          if e['stage']=='native_deferred_empty_record_consumed' and e['sequence']==471)

    @classmethod
    def tearDownClass(cls):
        assert cls.original_pins=={name:review.pin(RUN/name)['sha256'] for name in cls.original_pins}

    def reject(self, change):
        rows=copy.deepcopy(self.records);change(rows)
        with self.assertRaises(ValueError):review._xp2_weather_favor_records(rows,self.intervals)

    @staticmethod
    def word(rows, index, offset, value, *, record=0, fmt='<I'):
        event=rows[index][2];raw=bytearray.fromhex(event['record_hex'][record])
        struct.pack_into(fmt,raw,offset,value);event['record_hex'][record]=raw.hex()

    def test_retained08_records_keep_actual_values_and_limited_evidence(self):
        r=self.result;self.assertEqual(r['record_count'],5);self.assertEqual(r['array_record_count'],1)
        self.assertEqual([x['sequence'] for x in r['records']],[471,473,474,475,476])
        self.assertEqual([x['record_type'] for x in r['records']],[0x138,0x136,0x137,0x142,0x142])
        self.assertTrue(all(x['protocol_sequence']==6 and x['enqueued_line']<x['consumed_line']<6305
                            for x in r['records']))
        storm=r['records'][0]
        self.assertEqual(storm['copied_plot_indices'],[11,55,12,10,54])
        self.assertEqual(storm['copied_service_words'],[15,4])
        self.assertEqual(storm['array_copy_sha256'],'0eb5b5e2e1b4245f048548ec9e794b65c1e91ab6bcdcd6ccd73dbfab37002578')
        self.assertEqual([x['values'] for x in r['records'][-2:]],[[0,0,0xffffffff],[1,0,0xffffffff]])
        self.assertIs(r['native_pointer_dereferenced_during_review'],False)
        self.assertIs(r['array_bytes_reobserved_during_review'],False)
        self.assertIs(r['public_visibility_qualified'],False)
        self.assertEqual(r['transcript']['sha256'],'808142be2a86d06c63280beb08effbd78fc4a75d4bf8b16e383e4a49b5c46c8b')
        acceptance=json.loads((RUN/'client-acceptance.json').read_bytes())
        self.assertNotIn('status',r)
        self.assertEqual(acceptance['status'],'refused')
        with self.assertRaisesRegex(ValueError,'Acceptance group did not complete'):
            review.review(RUN/'client-acceptance.json',ARCHIVE)

    def test_source_profiles_and_archive_must_match_original_execution(self):
        for key in (next(k for k in self.closure['pins'] if k.endswith(weather.SOURCE[0].replace('/','\\'))),
                    str((HOST/'src/civ6_host/runtime/a0_xp2_turn_events.py').resolve())):
            with self.subTest(key=key):
                changed=copy.deepcopy(self.closure);changed['pins'][key]='0'*64
                with self.assertRaises(ValueError):
                    review.review_xp2_weather_favor(RUN,changed,self.report,ARCHIVE,self.intervals)
        changed=copy.deepcopy(self.closure);changed['input_profile']='xp1-lan'
        with self.assertRaises(ValueError):
            review.review_xp2_weather_favor(RUN,changed,self.report,ARCHIVE,self.intervals)
        # A modified copy is evidence corruption, never a replacement archive.
        with tempfile.TemporaryDirectory() as tmp:
            altered=Path(tmp)/'altered.zip'
            with zipfile.ZipFile(ARCHIVE) as original,zipfile.ZipFile(altered,'w') as saved:
                for name in self.result['executed_sources']:
                    raw=original.read(name)
                    saved.writestr(name,raw+b'\n' if name.endswith('/a0_xp2_turn_events.py') else raw)
            with self.assertRaisesRegex(ValueError,'implementation differs'):
                review.review_xp2_weather_favor(RUN,self.closure,self.report,altered,self.intervals)

    def test_header_type_size_both_sequences_flags_and_index_are_joined(self):
        for offset,value in ((0,112),(4,0x13b),(8,472),(12,1),(16,11),(20,0),(24,0),(64,1),(72,0),(76,1),(80,472)):
            with self.subTest(offset=offset):
                self.reject(lambda rows:self.word(rows,self.storm,offset,value))
        self.reject(lambda rows:rows[self.storm][2].update(record_sequences=[472]))
        self.reject(lambda rows:rows[self.random][2]['record_sequences'].reverse())
        self.reject(lambda rows:rows[self.random][2]['record_hex'].reverse())

    def test_source_scope_and_native_query_receipts_are_required(self):
        for key,value in (('source_proof_sha256','0'*64),('dispatch_kind','0x68e7d3da'),
                          ('public_visibility_qualified',True),('information_scope','public'),
                          ('eligible_for_training',True),('native_dispatch_return',1),
                          ('native_queries_executed',False),('undefined_record_ranges',[])):
            with self.subTest(key=key):self.reject(lambda rows:rows[self.storm][2].update({key:value}))
        self.reject(lambda rows:rows[self.random][2].update(native_position_index=12))
        self.reject(lambda rows:self.word(rows,self.random,88,16,record=1))
        self.reject(lambda rows:self.word(rows,self.random,92,1))
        self.reject(lambda rows:rows[self.favor][2].update(native_queries_executed=True))

    def test_array_copies_count_service_words_and_ownership_policy(self):
        for offset,value,fmt in ((88,0,'<I'),(108,6,'<I'),(112,0,'<Q'),(120,1,'<I')):
            with self.subTest(offset=offset):self.reject(lambda rows:self.word(rows,self.storm,offset,value,fmt=fmt))
        self.reject(lambda rows:rows[self.storm][2]['copied_plot_positions'].pop())
        self.reject(lambda rows:rows[self.storm][2]['copied_plot_positions'].__setitem__(0,'00'))
        self.reject(lambda rows:rows[self.storm][2]['copied_plot_indices'].__setitem__(0,-1))
        self.reject(lambda rows:rows[self.storm][2].update(copied_service_words=[4,15]))
        self.reject(lambda rows:rows[self.storm][2].update(storage_release_policy='released-before-consumption'))

    def test_missing_duplicate_and_out_of_order_producer_or_consumer(self):
        self.reject(lambda rows:rows.pop(self.storm))
        self.reject(lambda rows:rows.pop(self.consumed))
        self.reject(lambda rows:rows.insert(self.storm,copy.deepcopy(rows[self.storm])))
        self.reject(lambda rows:rows.insert(self.consumed,copy.deepcopy(rows[self.consumed])))
        def reorder(rows):
            # Move Storm after the unrelated cache dispatch for sequence 472.
            rows[self.consumed],rows[self.consumed+2]=rows[self.consumed+2],rows[self.consumed]
        self.reject(reorder)

    def test_consumer_type_size_receiver_and_empty_profile_match(self):
        for key,value in (('record_type',0x13b),('record_size',112),('sequence',472),
                          ('handler_va','0x1400d6250'),('gameplay_event_name','GameCoreEvent::DroughtAddedToMap'),
                          ('native_handler_has_no_gameplay_callback_in_this_profile',False),
                          ('native_profiling_reproduced',True),('eligible_for_training',True)):
            with self.subTest(key=key):self.reject(lambda rows:rows[self.consumed][2].update({key:value}))

    def test_owned_array_cannot_escape_its_completed_transition(self):
        def move_consume(rows):
            _,raw,event=rows[self.consumed];rows[self.consumed]=(6305,raw,event)
        self.reject(move_consume)
        with self.assertRaisesRegex(ValueError,'outside one completed native transition'):
            review._xp2_weather_favor_records(self.records,[])


if __name__=='__main__':unittest.main()

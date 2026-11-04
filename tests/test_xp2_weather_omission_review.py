"""Offline omission review: synthetic intervals and untouched partial native15."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import qualify_xp1_configuration as q
import review_xp1_session as review
from civ6_host.runtime import xp2_weather_lifecycle as lifecycle
from civ6_host.runtime import xp2_turn_event_profile as weather
from civ6_host.runtime.a0_family_source import _path
from civ6_host.runtime.native.native_cache_update_event import encode_cache_update_producer
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.stdout_transport_profiles import session_records

HOST=Path(__file__).resolve().parents[1]
RUN=resource_root()/'work/xp2-client-sessions/run-238b3fd00084405d83dbe5944ba5a7fc'
ARCHIVE=HOST/'work/xp2-session-integration/native-session15/executed-sources.zip'


def omission(kind, sequence=1):
    values=lifecycle.LifecycleFields(kind,0,7,None if kind==lifecycle.STORM_REMOVED else 2,
        (5,3),(54,53,9,8) if kind==lifecycle.STORM_CHANGED else None)
    return dict(stage='native_xp2_weather_presentation_omitted',dispatch_kind=hex(kind),
        source_proof_sha256=lifecycle.SOURCE[1],dispatch_scope_sha256=weather.SCOPE_SOURCE[1],
        policy=lifecycle.POLICY,administrative_arguments=values.to_admin(),
        information_scope='administrative-unfiltered',public_visibility_qualified=False,
        native_queries_executed=False,native_gameplay_written=False,presentation_arrays_allocated=False,
        records_enqueued=0,fifo_sequence_before=sequence,fifo_sequence_after=sequence,
        preceding_pending_records_preserved=True,native_dispatch_return=0,eligible_for_training=False)


def fixture():
    """Explicit test data; never persisted as execution or acceptance evidence."""
    record=encode_cache_update_producer(1,lifecycle.STORM_CHANGED,(1<<32)|0x768ba93d,0,
                                         host_callback_pair=None)
    events=[dict(stage='native_cache_update_enqueued',record_hex=record.hex()),
            omission(lifecycle.STORM_CHANGED),omission(lifecycle.STORM_REMOVED),
            omission(lifecycle.DROUGHT_REMOVED),dict(stage='native_cache_update_dispatched',sequence=1)]
    rows=[(i+1,b'',event) for i,event in enumerate(events)]
    intervals=[dict(first_line=0,last_line=6,protocol_sequence=1,phase='turn_update',
                    event=dict(stage='xp1_saved_turn_update_returned',protocol_sequence=1))]
    return rows,intervals


class WeatherOmissionReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure=json.loads((RUN/'closure.json').read_bytes())
        cls.report=json.loads((RUN/'supervisor.json').read_bytes())
        cls.records=list(session_records(RUN,report=cls.report))
        cls.actual=next(event for _,_,event in cls.records
                        if event['stage']=='native_xp2_weather_presentation_omitted')
        cls.pins={str(p):review.pin(p)['sha256'] for p in
            (RUN/'events.jsonl',RUN/'client-acceptance.json',RUN/'closure.json',RUN/'supervisor.json',ARCHIVE)}

    @classmethod
    def tearDownClass(cls):
        assert cls.pins=={name:review.pin(name)['sha256'] for name in cls.pins}

    def test_synthetic_completed_intervals_join_three_omissions_without_fifo_records(self):
        rows,intervals=fixture()
        r=review._xp2_weather_favor_records(rows,intervals,lifecycle_omissions=True)
        self.assertEqual((r['record_count'],r['array_record_count'],r['presentation_omission_count']),(0,0,3))
        self.assertEqual([row['omission_ordinal'] for row in r['presentation_omissions']],[1,2,3])
        self.assertTrue(all(row['fifo_sequence']==1 and row['preceding_pending_sequences']==[1]
                            and row['protocol_sequence']==1 for row in r['presentation_omissions']))
        self.assertFalse(r['native_pointer_dereferenced_during_review'])
        self.assertNotIn('status',r)
        # No cache update is invented when native internal dispatch produced none.
        rows=[(1,b'',omission(lifecycle.STORM_CHANGED,0))]
        rows[0][2]['administrative_arguments']['input_plot_indices']=[]
        r=review._xp2_weather_favor_records(rows,intervals,lifecycle_omissions=True)
        self.assertEqual(r['presentation_omissions'][0]['preceding_pending_sequences'],[])
        with self.assertRaisesRegex(ValueError,'executed lifecycle source'):
            review._xp2_weather_favor_records(rows,intervals)

    def test_source_policy_copy_widths_and_pointer_injection_are_rejected(self):
        event=omission(lifecycle.STORM_CHANGED)
        mutations=[lambda e,k=k,v=v:e.update({k:v}) for k,v in (
            ('source_proof_sha256','0'*64),('dispatch_scope_sha256','0'*64),('policy','generic-noop'),
            ('dispatch_kind','0x13b135e4'),('records_enqueued',1),('records_enqueued',False),
            ('fifo_sequence_after',2),('fifo_sequence_before',True),('native_queries_executed',True),
            ('native_gameplay_written',True),('presentation_arrays_allocated',True),
            ('preceding_pending_records_preserved',False),('native_dispatch_return',False),
            ('public_visibility_qualified',True),('eligible_for_training',True),('record_hex',[]))]
        mutations.extend(lambda e,k=k,v=v:e['administrative_arguments'].update({k:v}) for k,v in (
            ('selector',True),('identifier',-1),('status',2**32),('status_key','0xf36f4928'),
            ('input_position',[2**31,3]),('input_position',[5,False]),('input_position',[5]),
            ('input_plot_indices',[2**32]),('input_plot_indices',[False]),
            ('input_plot_indices',[1]*65537),('input_plot_indices',None),
            ('field_tags',{'0xa1e5a149':3}),('pointer_payloads_copied',False),
            ('borrowed_pointer_addresses_retained',True),('raw_fields',{'pointer':12345})))
        for mutate in mutations:
            value=copy.deepcopy(event);mutate(value)
            with self.assertRaises(ValueError):review._xp2_weather_omission_payload(value)
        removed=omission(lifecycle.STORM_REMOVED)
        removed['administrative_arguments']['status']=0
        with self.assertRaises(ValueError):review._xp2_weather_omission_payload(removed)
        drought=omission(lifecycle.DROUGHT_REMOVED)
        drought['administrative_arguments']['input_plot_indices']=[]
        with self.assertRaises(ValueError):review._xp2_weather_omission_payload(drought)

    def test_fifo_order_missing_or_double_consumption_and_incomplete_intervals_refuse(self):
        mutations=(
            lambda rows,ints:rows.pop(0),
            lambda rows,ints:rows.pop(),
            lambda rows,ints:rows.append((6,b'',dict(stage='native_cache_update_dispatched',sequence=1))),
            lambda rows,ints:rows.insert(1,copy.deepcopy(rows[1])),
            lambda rows,ints:rows[-1][2].update(sequence=2),
            lambda rows,ints:rows[1][2].update(fifo_sequence_before=2,fifo_sequence_after=2),
            lambda rows,ints:ints.clear(),
            lambda rows,ints:ints[0].update(last_line=5),
            lambda rows,ints:ints[0]['event'].update(stage='before_xp1_saved_turn_update'),
            lambda rows,ints:ints[0]['event'].update(protocol_sequence=2),
        )
        for mutate in mutations:
            rows,intervals=fixture();mutate(rows,intervals)
            with self.assertRaises(ValueError):
                review._xp2_weather_favor_records(rows,intervals,lifecycle_omissions=True)
        rows,intervals=fixture()
        rows[0],rows[1]=(1,b'',rows[1][2]),(2,b'',rows[0][2])
        with self.assertRaisesRegex(ValueError,'preceding FIFO state'):
            review._xp2_weather_favor_records(rows,intervals,lifecycle_omissions=True)

    def test_retained15_payload_is_valid_but_never_a_completed_interval(self):
        value=review._xp2_weather_omission_payload(self.actual)
        self.assertEqual(value['fifo_sequence'],1067)
        self.assertEqual(value['administrative_arguments']['input_position'],[5,3])
        self.assertEqual(value['administrative_arguments']['input_plot_indices'],[54,53,9,8,51,95,138,137])
        self.assertNotIn('protocol_sequence',value)
        with self.assertRaisesRegex(ValueError,'Incomplete shared command interval'):
            q.saved_load_events(RUN/'events.jsonl',allow_multiple_commands=True,allow_turn_updates=True,
                stdout_transport=self.closure['stdout_transport'],
                stdout_native_records=self.report['stdout_native_records'],
                stdout_limit_bytes=self.closure['stdout_limit_bytes'])
        # Authenticating the original source archive does not complete run15.
        with self.assertRaisesRegex(ValueError,'outside one completed native transition'):
            review.review_xp2_weather_favor(RUN,self.closure,self.report,ARCHIVE,[])
        acceptance=json.loads((RUN/'client-acceptance.json').read_bytes())
        self.assertEqual(acceptance['status'],'refused')
        with self.assertRaisesRegex(ValueError,'Acceptance group did not complete'):
            review.review(RUN/'client-acceptance.json',ARCHIVE)

    def test_lifecycle_source_scope_and_executed_producer_are_all_required(self):
        for key in (str(_path(lifecycle.SOURCE[0]).resolve()),str(_path(weather.SCOPE_SOURCE[0]).resolve()),
                    str((HOST/'src/civ6_host/runtime/xp2_weather_lifecycle.py').resolve()),
                    str((HOST/'src/civ6_host/runtime/a0_family_service.py').resolve())):
            changed=copy.deepcopy(self.closure);changed['pins'][key]='0'*64
            with self.assertRaisesRegex(ValueError,'differs from executed|implementation differs'):
                review.review_xp2_weather_favor(RUN,changed,self.report,ARCHIVE,[])
        changed=copy.deepcopy(self.closure)
        del changed['pins'][str(_path(lifecycle.SOURCE[0]).resolve())]
        del changed['pins'][str(_path(weather.SCOPE_SOURCE[0]).resolve())]
        with self.assertRaisesRegex(ValueError,'implementation differs'):
            review.review_xp2_weather_favor(RUN,changed,self.report,ARCHIVE,[])
        with tempfile.TemporaryDirectory() as directory:
            altered=Path(directory)/'altered.zip'
            name='src/civ6_host/runtime/xp2_weather_lifecycle.py'
            with zipfile.ZipFile(ARCHIVE) as original,zipfile.ZipFile(altered,'w') as target:
                for item in original.namelist():
                    if item!=name:target.writestr(item,original.read(item))
            with self.assertRaisesRegex(ValueError,'implementation differs'):
                review.review_xp2_weather_favor(RUN,self.closure,self.report,altered,[])


if __name__=='__main__':unittest.main()

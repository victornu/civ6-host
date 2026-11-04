"""Offline feature omission review; synthetic intervals never imply native completion."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import qualify_xp1_configuration as q
import review_xp1_session as review
from civ6_host.runtime import xp2_feature_reveal_source as feature
from civ6_host.runtime import xp2_turn_event_profile as weather
from civ6_host.runtime.a0_family_source import _path
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_cache_update_event import encode_cache_update_producer
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.stdout_transport_profiles import session_records

HOST=q.REPO
FIXTURE=HOST/'work/xp2-session-integration/reviewer-feature-patch/offline-v2-source-fixture'
ARCHIVE=FIXTURE/'frozen-sources.zip'
RETAINED_ARCHIVE=HOST/'work/xp2-session-integration/native-session16/executed-sources.zip'
LEGACY=HOST/'work/xp2-session-integration/native-session08/executed-sources.zip'
RUN=resource_root()/'work/xp2-client-sessions/run-0bdee76300ec4e0b8312345d68d8f27b'
MODULE='civ6_host.runtime.xp2_feature_reveal_source'


def installation():
    return dict(stage='native_empty_presentation_family_installed',core_sha256=XP2_CORE_SHA256,
        source_module=MODULE,source_proof_sha256=feature.SOURCE[1],
        dispatch_kinds=[hex(k) for k in sorted(feature.KINDS)],policy=feature.POLICY,
        synthetic_records=False,unknown_service_fallback=False)


def omission(kind,sequence=1):
    return dict(stage='native_empty_presentation_callback_omitted',dispatch_kind=hex(kind),
        source_module=MODULE,source_proof_sha256=feature.SOURCE[1],policy=feature.POLICY,
        administrative_arguments=feature.FeatureRevealFields(kind,0,(-5,3),0xffffffff).to_admin(),
        information_scope='administrative-unfiltered',public_visibility_qualified=False,
        native_queries_executed=False,native_gameplay_written=False,presentation_arrays_allocated=False,
        records_enqueued=0,fifo_sequence_before=sequence,fifo_sequence_after=sequence,
        preceding_pending_records_preserved=True,native_dispatch_return=0,eligible_for_training=False)


def fixture():
    record=encode_cache_update_producer(1,feature.FLOODPLAIN_REVEALED,(1<<32)|0x768ba93d,0,
                                      host_callback_pair=None)
    events=[installation(),dict(stage='native_cache_update_enqueued',record_hex=record.hex()),
        *(omission(k) for k in sorted(feature.KINDS)),
        dict(stage='native_cache_update_dispatched',sequence=1)]
    rows=[(i+1,b'',event) for i,event in enumerate(events)]
    intervals=[dict(first_line=2,last_line=7,protocol_sequence=3,phase='turn_update',
        event=dict(stage='xp1_saved_turn_update_returned',protocol_sequence=3))]
    return rows,intervals


class FeatureOmissionPayloadTests(unittest.TestCase):
    def test_three_exact_families_copy_only_admin_values(self):
        for kind in feature.KINDS:
            event=omission(kind)
            value=review._xp2_empty_presentation_omission_payload(event)
            self.assertEqual(value['administrative_arguments'],event['administrative_arguments'])
            self.assertEqual(value['records_enqueued'],0)
            self.assertFalse(value['native_queries_executed'])
            self.assertFalse(value['native_gameplay_written'])
            self.assertNotIn('protocol_sequence',value)
            value['administrative_arguments']['coordinate'][0]=123
            self.assertEqual(event['administrative_arguments']['coordinate'],[-5,3])

    def test_source_scope_exact_shape_widths_and_pointer_injection_refused(self):
        mutations=[lambda e,k=k,v=v:e.update({k:v}) for k,v in (
            ('source_module','civ6_host.runtime.xp2_weather_lifecycle'),
            ('source_proof_sha256','0'*64),('source_proof_sha256',feature.HISTORICAL_SOURCE[1]),
            ('policy','generic-noop'),('dispatch_kind','0x13b135e4'),
            ('dispatch_kind',hex(feature.FLOODPLAIN_REVEALED).upper()),('records_enqueued',1),
            ('records_enqueued',False),('fifo_sequence_before',True),('fifo_sequence_before',-1),
            ('fifo_sequence_before',0x7fffffff),('fifo_sequence_after',2),('fifo_sequence_after',True),
            ('native_queries_executed',True),('native_gameplay_written',True),
            ('presentation_arrays_allocated',True),('preceding_pending_records_preserved',False),
            ('native_dispatch_return',False),('native_dispatch_return',1),
            ('information_scope','public'),('public_visibility_qualified',True),
            ('eligible_for_training',True),('record_hex',[]),('pointer',12345))]
        mutations.extend(lambda e,k=k,v=v:e['administrative_arguments'].update({k:v}) for k,v in (
            ('kind',hex(feature.VOLCANO_REVEALED)),('event_name','GameCoreEvent::VolcanoRevealed'),
            ('selector',True),('selector',1),('value_key','0xa1e5a149'),('value',True),
            ('value',-1),('value',2**32),('coordinate',[2**31,3]),('coordinate',[-2**31-1,3]),
            ('coordinate',[False,3]),('coordinate',[5]),('coordinate',(5,3)),
            ('field_tags',{'0xa1e5a149':3,'0x8c468e3c':False,'0xd6fcf3e4':2}),
            ('field_tags',{}),('borrowed_position_payload_copied',False),
            ('borrowed_pointer_retained',True),('raw_fields',{'pointer':12345})))
        mutations.extend((lambda e:e.pop('source_module'),
                          lambda e:e['administrative_arguments'].pop('coordinate')))
        for mutate in mutations:
            event=omission(feature.FLOODPLAIN_REVEALED);mutate(event)
            with self.assertRaises(ValueError):review._xp2_empty_presentation_omission_payload(event)

    def test_installation_is_exact_and_fixed_not_protocol_selected(self):
        self.assertEqual(review._xp2_empty_presentation_installation(installation()),installation())
        for key,value in (('core_sha256','0'*64),('source_module','other'),
            ('source_proof_sha256','0'*64),('source_proof_sha256',feature.HISTORICAL_SOURCE[1]),
            ('dispatch_kinds',[hex(feature.FLOODPLAIN_REVEALED)]),
            ('dispatch_kinds',list(reversed(installation()['dispatch_kinds']))),('policy','noop'),
            ('synthetic_records',0),('unknown_service_fallback',True),('pointer',12345)):
            event=installation();event[key]=value
            with self.assertRaises(ValueError):review._xp2_empty_presentation_installation(event)


class FeatureOmissionIntervalTests(unittest.TestCase):
    def review(self,rows,intervals):
        return review._xp2_weather_favor_records(rows,intervals,empty_presentation_omissions=True)

    def test_completed_interval_preserves_fifo_and_weather_namespace(self):
        rows,intervals=fixture();r=self.review(rows,intervals)
        self.assertEqual((r['record_count'],r['presentation_omission_count'],
                          r['empty_presentation_omission_count']),(0,0,3))
        self.assertEqual([x['dispatch_kind'] for x in r['empty_presentation_omissions']],
                         [hex(k) for k in sorted(feature.KINDS)])
        self.assertTrue(all(x['fifo_sequence']==1 and x['preceding_pending_sequences']==[1]
            and x['protocol_sequence']==3 for x in r['empty_presentation_omissions']))
        self.assertFalse(r['native_pointer_dereferenced_during_review'])
        self.assertNotIn('status',r)
        rows=[(1,b'',installation()),(2,b'',omission(feature.VOLCANO_REVEALED,0))]
        intervals[0].update(first_line=1,last_line=3)
        self.assertEqual(self.review(rows,intervals)['empty_presentation_omissions'][0]
                         ['preceding_pending_sequences'],[])
        with self.assertRaisesRegex(ValueError,'executed empty presentation source'):
            review._xp2_weather_favor_records(rows,intervals)

    def test_installation_fifo_and_completed_native_return_all_required(self):
        mutations=(lambda rows,ints:rows.pop(0),lambda rows,ints:rows.pop(),
            lambda rows,ints:rows.insert(1,copy.deepcopy(rows[0])),
            lambda rows,ints:rows[0][2].update(source_module='other'),
            lambda rows,ints:rows[2][2].update(fifo_sequence_before=2,fifo_sequence_after=2),
            lambda rows,ints:rows[-1][2].update(sequence=2),
            lambda rows,ints:rows.append((7,b'',dict(stage='native_cache_update_dispatched',sequence=1))),
            lambda rows,ints:ints.clear(),lambda rows,ints:ints[0].update(last_line=6),
            lambda rows,ints:ints[0].update(phase='load'),
            lambda rows,ints:ints[0]['event'].update(stage='before_xp1_saved_turn_update'),
            lambda rows,ints:ints[0]['event'].update(protocol_sequence=4),
            lambda rows,ints:ints[0].update(protocol_sequence=True))
        for mutate in mutations:
            rows,intervals=fixture();mutate(rows,intervals)
            with self.assertRaises(ValueError):self.review(rows,intervals)
        rows,intervals=fixture()
        rows[1],rows[2]=(2,b'',rows[2][2]),(3,b'',rows[1][2])
        intervals[0]['first_line']=1
        with self.assertRaisesRegex(ValueError,'preceding FIFO state'):self.review(rows,intervals)
        rows,intervals=fixture();rows[0],rows[2]=(1,b'',rows[2][2]),(3,b'',rows[0][2])
        with self.assertRaises(ValueError):self.review(rows,intervals)


class FeatureOmissionClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure=json.loads((FIXTURE/'offline-fixture.json').read_bytes())
        assert cls.closure['schema']=='civ6-host.xp2-feature-omission.offline-source-fixture.v1'
        assert cls.closure['native_execution'] is False
        assert cls.closure['synthetic_intervals'] is True
        assert cls.closure['positive_native_execution_claim'] is False
        assert cls.closure['source_profile']==dict(path=feature.SOURCE[0],sha256=feature.SOURCE[1])
        assert cls.closure['archive']['sha256']==review.pin(ARCHIVE)['sha256']
        cls.immutable={str(p):review.pin(p)['sha256'] for p in (
            FIXTURE/'offline-fixture.json',ARCHIVE,LEGACY,RETAINED_ARCHIVE,
            *(RUN/name for name in ('closure.json','events.jsonl','supervisor.json','client-acceptance.json')))}
        # Validate immutable dependencies once; fault cases reuse those exact
        # identities so the matrix does not reread large private source captures.
        cls.weather_dependencies=weather.source_dependencies()
        cls.feature_dependencies=feature.source_dependencies()
        cls.real_pin=staticmethod(review.pin)
        cls.cached_pins={}

    @classmethod
    def cached_pin(cls,path):
        key=str(Path(path).resolve())
        if key not in cls.cached_pins:cls.cached_pins[key]=cls.real_pin(path)
        return cls.cached_pins[key]

    @classmethod
    def tearDownClass(cls):
        assert cls.immutable=={p:review.pin(p)['sha256'] for p in cls.immutable}

    def review(self,closure=None,archive=ARCHIVE):
        rows,intervals=fixture()
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp);(run/'events.jsonl').write_text('synthetic offline fixture\n')
            with mock.patch('civ6_host.runtime.stdout_transport_profiles.session_records',return_value=rows), \
                mock.patch.object(weather,'source_dependencies',side_effect=lambda:dict(self.weather_dependencies)), \
                mock.patch.object(feature,'source_dependencies',side_effect=lambda:dict(self.feature_dependencies)), \
                mock.patch.object(review,'pin',side_effect=self.cached_pin):
                return review.review_xp2_weather_favor(run,closure or self.closure,{},archive,intervals)

    def test_frozen_offline_source_closure_authenticates_only_synthetic_intervals(self):
        r=self.review()
        self.assertEqual(r['executed_empty_presentation_contract'],feature.SOURCE[1])
        self.assertEqual(r['empty_presentation_omission_count'],3)
        self.assertEqual(r['source_profiles'][str(_path(feature.SOURCE[0]).resolve())],feature.SOURCE[1])
        self.assertNotIn('status',r)
        self.assertNotIn(str((HOST/'tools/review_xp1_session.py').resolve()),self.closure['pins'])

    def test_native16_refusal_is_never_reinterpreted_as_execution_of_v2(self):
        closure=json.loads((RUN/'closure.json').read_bytes())
        acceptance=json.loads((RUN/'client-acceptance.json').read_bytes())
        report=json.loads((RUN/'supervisor.json').read_bytes())
        records=list(session_records(RUN,report=report))
        self.assertEqual(acceptance['status'],'refused')
        self.assertFalse(any(event['stage']=='native_empty_presentation_callback_omitted'
                             for _,_,event in records))
        installed=next(event for _,_,event in records
                       if event['stage']=='native_empty_presentation_family_installed')
        self.assertEqual(installed['source_proof_sha256'],feature.HISTORICAL_SOURCE[1])
        with self.assertRaisesRegex(ValueError,'installation differs'):
            review._xp2_empty_presentation_installation(installed)
        with self.assertRaisesRegex(ValueError,'source profile differs from executed closure'):
            review.review_xp2_weather_favor(RUN,closure,report,RETAINED_ARCHIVE,[])
        # The existing weather value copy remains independently reviewable;
        # this validates no incomplete transition or session acceptance.
        weather_event=next(event for _,_,event in records
                          if event['stage']=='native_xp2_weather_presentation_omitted')
        self.assertEqual(review._xp2_weather_omission_payload(weather_event)['records_enqueued'],0)

    def test_source_registry_borrow_installation_and_argument_reader_pins_required(self):
        modules=('empty_presentation_events','xp2_feature_reveal_source','a0_family_service',
            'a0_family_source','a0_foundation_events','xp1_continuation','event_argument_service',
            'event_argument_source','deferred_service','xp1_saved_load_composition',
            'xp1_session_inputs','configuration_profiles','native/native_host_event_registry',
            'native/native_absent_unit_scalar_family','native/native_event_argument_tree',
            'native/native_host_events','native/native_deferred_empty_profile')
        paths=[str((HOST/('src/civ6_host/runtime/'+m+'.py')).resolve()) for m in modules]
        paths.extend(str(_path(pair[0]).resolve()) for pair in
                     (feature.SOURCE,feature.PRODUCER_SOURCE,feature.RECEIVER_SOURCE))
        for path in paths:
            for delete in (False,True):
                changed=copy.deepcopy(self.closure)
                if delete:del changed['pins'][path]
                else:changed['pins'][path]='0'*64
                with self.subTest(path=path,delete=delete),self.assertRaises(ValueError):self.review(changed)
        changed=copy.deepcopy(self.closure)
        for path in (str(_path(feature.SOURCE[0]).resolve()),
            *(str((HOST/('src/civ6_host/runtime/'+m+'.py')).resolve())
              for m in ('empty_presentation_events','xp2_feature_reveal_source'))):
            del changed['pins'][path]
        with self.assertRaisesRegex(ValueError,'executed empty presentation source'):self.review(changed)

    def test_archive_bytes_required_and_matching_unreviewed_hash_never_admitted(self):
        name='src/civ6_host/runtime/empty_presentation_events.py'
        for omitted in (True,False):
            with tempfile.TemporaryDirectory() as temp:
                altered=Path(temp)/'altered.zip';changed=copy.deepcopy(self.closure)
                with zipfile.ZipFile(ARCHIVE) as original,zipfile.ZipFile(altered,'w') as target:
                    for member in original.namelist():
                        raw=original.read(member)
                        if member==name:
                            if omitted:continue
                            raw+=b'\n'
                            changed['pins'][str((HOST/name).resolve())]=hashlib.sha256(raw).hexdigest()
                        target.writestr(member,raw)
                with self.assertRaisesRegex(ValueError,'implementation differs'):self.review(changed,altered)

    def test_legacy_shared_compatibility_never_admits_another_archive_hash(self):
        legacy_run=resource_root()/'work/xp2-client-sessions/run-aaf5be223aac4d2cae611caf076b15c9'
        closure=json.loads((legacy_run/'closure.json').read_bytes())
        name='src/civ6_host/runtime/native/native_host_events.py'
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp);(run/'events.jsonl').write_text('synthetic offline fixture\n')
            altered=run/'altered.zip'
            with zipfile.ZipFile(LEGACY) as original,zipfile.ZipFile(altered,'w') as target:
                for member in original.namelist():
                    raw=original.read(member)
                    if member==name:
                        raw+=b'\n'
                        closure['pins'][str((HOST/name).resolve())]=hashlib.sha256(raw).hexdigest()
                    target.writestr(member,raw)
            with mock.patch('civ6_host.runtime.stdout_transport_profiles.session_records',return_value=[]):
                with self.assertRaisesRegex(ValueError,'implementation differs'):
                    review.review_xp2_weather_favor(run,closure,{},altered,[])

    def test_legacy08_shared_module_diff_is_only_combat_admin_keyword(self):
        name='src/civ6_host/runtime/native/native_host_events.py'
        with zipfile.ZipFile(LEGACY) as archive:old=archive.read(name)
        self.assertEqual(hashlib.sha256(old).hexdigest(),
            'fad6ceb4725d288778b7d9b663774b77bbf87576c812c539e0f3ea1e08e5e34d')
        before=ast.parse(old);after=ast.parse((HOST/name).read_bytes());removed=0
        for node in ast.walk(after):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='emit':
                for keyword in list(node.keywords):
                    value=keyword.value
                    if (keyword.arg is None and isinstance(value,ast.Call)
                        and isinstance(value.func,ast.Attribute)
                        and isinstance(value.func.value,ast.Name) and value.func.value.id=='_combat_source'
                        and value.func.attr=='administrative_snapshot_policy'):
                        self.assertEqual(node.args[0].value,'native_combat_record_enqueued')
                        self.assertEqual(ast.dump(value),ast.dump(ast.parse(
                            '_combat_source.administrative_snapshot_policy(_core_sha256)',mode='eval').body))
                        node.keywords.remove(keyword);removed+=1
        self.assertEqual(removed,1)
        self.assertEqual(ast.dump(before,include_attributes=False),ast.dump(after,include_attributes=False))


if __name__=='__main__':unittest.main()

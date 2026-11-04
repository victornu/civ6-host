"""Exact F8 dual diagnostics: one enqueue and one authenticated native post-hook."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zipfile

import qualify_xp1_configuration as q
import review_xp1_session as review
from civ6_host.runtime import xp2_combat_event_source as combat
from civ6_host.runtime import xp2_feature_reveal_source as feature
from civ6_host.runtime import xp2_turn_event_profile as weather
from civ6_host.runtime.a0_family_source import _path
from civ6_host.runtime.combat_map_profiles import RECEIVER_SOURCE
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_combat_receiver import PADDING_POLICY,PROOF_SHA256
from civ6_host.runtime.native.native_event_8256dbe1 import CombatFields,encode_record
from civ6_host.runtime.paths import resource_root

RUN=resource_root()/'work/xp2-client-sessions/run-adfc769de8fb46fe9755d3e5136e48f7'
ARCHIVE=q.REPO/'work/xp2-session-integration/native-session17/executed-sources.zip'


def fixture():
    """Constructed offline data; never a receipt of a native execution."""
    descriptors=(struct.pack('<HHI',3,1,131074),struct.pack('<HHI',63,1,524295),
                 struct.pack('<HHI',0xffff,0,0xffffffff),struct.pack('<HHI',0xffff,0,0xffffffff))
    raw=encode_record(1,1,CombatFields(descriptors,0,0),(False,False),padding_bytes=bytes(8),
        normalizer_transform_present=False,per_thread_hook_present=False,writer_metadata_callback_present=False)
    generic=dict(stage='native_deferred_host_event_enqueued',dispatch_kind='0x8256dbe1',
        queue_type='0xf8',record_hex=raw.hex(),pending_count=1,consumer_validated=False,
        eligible_for_training=False,native_dispatch_return=0)
    detailed={key:value for key,value in generic.items() if key!='consumer_validated'}
    detailed.update(stage='native_combat_record_enqueued',token=1,source_proof_sha256=combat.SOURCE[1],
        owned_root_field_count=len(combat.source()['root_fields']),native_deep_copy_executed=True,
        owned_map_retained_until_post_hook=True,padding_policy=PADDING_POLICY,
        query_inputs=[3,63],query_results=[False,False],registry_live_maps=1,callback_completed=True,
        **combat.administrative_snapshot_policy(XP2_CORE_SHA256))
    post=dict(stage='native_combat_post_hook_consumed',sequence=1,owned_map_core_sha256=XP2_CORE_SHA256,
        record_type=248,record_size=128,token=1,post_hook_reproduced=True,native_map_destructor_returned=True,
        registry_live_maps=0,source_proof_sha256=PROOF_SHA256,subscribers_invoked=0,
        full_exe_frame_schedule_reproduced=False,eligible_for_training=False)
    rows=[(1,b'',generic),(2,b'',detailed),(3,b'',post)]
    intervals=[dict(first_line=0,last_line=4,protocol_sequence=1,phase='turn_update',
        event=dict(stage='xp1_saved_turn_update_returned',protocol_sequence=1))]
    return rows,intervals


class CombatDiagnosticPairTests(unittest.TestCase):
    @staticmethod
    def review(rows,intervals):
        return review._xp2_weather_favor_records(rows,intervals,combat_diagnostic_receipts=True)

    def test_exact_adjacent_receipts_count_one_fifo_record_and_keep_post_hook(self):
        rows,intervals=fixture();result=self.review(rows,intervals)
        self.assertEqual((result['record_count'],result['combat_diagnostic_record_count'],
                          result['combat_post_hook_count']),(0,1,1))
        row=result['combat_diagnostic_records'][0]
        self.assertEqual((row['sequence'],row['token'],row['enqueued_line'],row['diagnostic_line'],
                          row['consumed_line']),(1,1,1,2,3))
        self.assertTrue(row['post_hook_reproduced'])
        self.assertTrue(row['native_map_destructor_returned'])
        self.assertFalse(row['administrative_snapshot_complete'])
        self.assertFalse(result['native_pointer_dereferenced_during_review'])
        self.assertNotIn('status',result)
        with self.assertRaisesRegex(ValueError,'executed adjacent producer'):
            review._xp2_weather_favor_records(rows,intervals)

    def test_copy_kind_size_sequence_token_and_all_diagnostic_metadata_are_exact(self):
        mutations=[lambda rows,ints,k=k,v=v:rows[1][2].update({k:v}) for k,v in (
            ('dispatch_kind','0x8256dbe2'),('queue_type','0xf7'),('token',2),('token',True),
            ('pending_count',2),('pending_count',True),('source_proof_sha256','0'*64),
            ('owned_root_field_count',17),('owned_root_field_count',True),('native_deep_copy_executed',False),
            ('owned_map_retained_until_post_hook',False),('padding_policy','other'),
            ('query_inputs',[63,3]),('query_inputs',[True,63]),('query_results',[True,False]),
            ('query_results',[0,False]),('registry_live_maps',2),('registry_live_maps',True),
            ('callback_completed',False),('eligible_for_training',True),('native_dispatch_return',False),
            ('administrative_snapshot_complete',True),('native_modifier_lists_preserved',False),
            ('modifier_values_decoded',True),('administrative_snapshot_policy','other'),('pointer',12345))]
        mutations.extend(lambda rows,ints,k=k,v=v:rows[0][2].update({k:v}) for k,v in (
            ('dispatch_kind','0x8256dbe2'),('queue_type','0xf7'),('pending_count',2),
            ('consumer_validated',True),('eligible_for_training',True),('native_dispatch_return',False),
            ('token',1)))
        def change_word(rows,offset,value,both):
            for index in ((0,1) if both else (1,)):
                raw=bytearray.fromhex(rows[index][2]['record_hex']);struct.pack_into('<I',raw,offset,value)
                rows[index][2]['record_hex']=raw.hex()
        mutations.extend(lambda rows,ints,at=at,value=value,both=both:change_word(rows,at,value,both)
                         for at,value,both in ((0,124,True),(4,247,True),(8,2,True),(12,1,True),
                            (80,2,True),(84,1,True),(120,2,True),(124,1,True),(120,2,False)))
        mutations.extend((lambda rows,ints:rows[1][2].pop('source_proof_sha256'),
                          lambda rows,ints:rows[0][2].pop('consumer_validated')))
        for mutate in mutations:
            rows,intervals=fixture();mutate(rows,intervals)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.review(rows,intervals)

    def test_missing_repeated_nonadjacent_and_other_duplicate_records_are_refused(self):
        mutations=(lambda rows,ints:rows.pop(0),lambda rows,ints:rows.pop(1),
            lambda rows,ints:rows.insert(1,(2,b'',dict(stage='unrelated'))),
            lambda rows,ints:rows.insert(1,(2,b'',copy.deepcopy(rows[0][2]))),
            lambda rows,ints:rows.insert(2,(3,b'',copy.deepcopy(rows[1][2]))),
            lambda rows,ints:rows.__setitem__(1,(3,b'',rows[1][2])))
        for mutate in mutations:
            rows,intervals=fixture();mutate(rows,intervals)
            with self.assertRaises(ValueError):self.review(rows,intervals)

    def test_post_hook_token_release_metadata_order_and_completed_return_are_required(self):
        mutations=[lambda rows,ints,k=k,v=v:rows[2][2].update({k:v}) for k,v in (
            ('sequence',2),('sequence',True),('record_type',247),('record_size',124),('token',2),
            ('owned_map_core_sha256','0'*64),('post_hook_reproduced',False),
            ('native_map_destructor_returned',False),('registry_live_maps',1),
            ('registry_live_maps',False),('source_proof_sha256','0'*64),('subscribers_invoked',False),
            ('subscribers_invoked',1),('full_exe_frame_schedule_reproduced',True),
            ('eligible_for_training',True),('pointer',12345))]
        mutations.extend((lambda rows,ints:rows.pop(),
            lambda rows,ints:rows.append((4,b'',copy.deepcopy(rows[-1][2]))),
            lambda rows,ints:rows[-1][2].update(stage='native_deferred_empty_record_consumed'),
            lambda rows,ints:ints.clear(),lambda rows,ints:ints[0].update(last_line=3),
            lambda rows,ints:ints[0].update(first_line=1),
            lambda rows,ints:ints[0]['event'].update(stage='before_xp1_saved_turn_update'),
            lambda rows,ints:ints[0]['event'].update(protocol_sequence=2)))
        for mutate in mutations:
            rows,intervals=fixture();mutate(rows,intervals)
            with self.assertRaises(ValueError):self.review(rows,intervals)


class CombatDiagnosticSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure=json.loads((RUN/'closure.json').read_bytes())
        cls.immutable={str(p):review.pin(p)['sha256'] for p in (
            ARCHIVE,*(RUN/name for name in ('closure.json','events.jsonl','supervisor.json','client-acceptance.json')))}
        cls.dependencies={module:module.source_dependencies() for module in (weather,feature,combat)}
        cls.real_pin=staticmethod(review.pin);cls.cached_pins={}

    @classmethod
    def tearDownClass(cls):
        assert cls.immutable=={path:review.pin(path)['sha256'] for path in cls.immutable}

    @classmethod
    def cached_pin(cls,path):
        key=str(Path(path).resolve())
        if key not in cls.cached_pins:cls.cached_pins[key]=cls.real_pin(path)
        return cls.cached_pins[key]

    def review(self,closure=None,archive=ARCHIVE):
        rows,intervals=fixture()
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'events.jsonl').write_text('explicit synthetic offline fixture\n')
            with mock.patch('civ6_host.runtime.stdout_transport_profiles.session_records',return_value=rows), \
                mock.patch.object(weather,'source_dependencies',side_effect=lambda:dict(self.dependencies[weather])), \
                mock.patch.object(feature,'source_dependencies',side_effect=lambda:dict(self.dependencies[feature])), \
                mock.patch.object(combat,'source_dependencies',side_effect=lambda:dict(self.dependencies[combat])), \
                mock.patch.object(review,'pin',side_effect=self.cached_pin):
                # This direct fixture isolates F8 accounting, while the archive
                # still proves the actual composed producer and borrower bytes.
                from test_xp2_feature_omission_review import installation
                rows[:]=[(1,b'',installation()),*((line+1,raw,event) for line,raw,event in rows)]
                intervals[0].update(first_line=1,last_line=5)
                return review.review_xp2_weather_favor(run,closure or self.closure,{},archive,intervals)

    def test_current_executed_archive_proves_the_exact_emission_and_release_path(self):
        result=self.review()
        self.assertEqual(result['combat_diagnostic_record_count'],1)
        self.assertEqual(result['combat_post_hook_count'],1)
        self.assertEqual(result['executed_combat_diagnostic_contract'],combat.SOURCE[1])
        self.assertNotIn('status',result)

    def test_all_combat_source_and_producer_receiver_module_pins_are_required(self):
        modules=('native/native_host_events','xp1_combat_profile','xp2_combat_event_source',
            'combat_map_profiles','combat_event_profile','a0_combat_events','deferred_service',
            'native/native_event_8256dbe1','native/native_combat_argument_snapshot',
            'native/native_combat_map_owner','native/native_combat_receiver')
        paths=[str((q.REPO/('src/civ6_host/runtime/'+module+'.py')).resolve()) for module in modules]
        paths.extend(str(_path(pair[0]).resolve()) for pair in (combat.SOURCE,RECEIVER_SOURCE))
        for path in paths:
            closure=copy.deepcopy(self.closure);closure['pins'][path]='0'*64
            with self.subTest(path=path),self.assertRaises(ValueError):self.review(closure)

    def test_changed_archived_emission_is_not_accepted_with_a_matching_forged_closure(self):
        name='src/civ6_host/runtime/native/native_host_events.py'
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'changed.zip';closure=copy.deepcopy(self.closure)
            with zipfile.ZipFile(ARCHIVE) as original,zipfile.ZipFile(archive,'w') as changed:
                for member in original.namelist():
                    raw=original.read(member)
                    if member==name:
                        raw+=b'\n'
                        import hashlib
                        closure['pins'][str((q.REPO/name).resolve())]=hashlib.sha256(raw).hexdigest()
                    changed.writestr(member,raw)
            with self.assertRaisesRegex(ValueError,'implementation differs'):self.review(closure,archive)


if __name__=='__main__':unittest.main()

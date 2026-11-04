"""Synthetic paired files exercise the real ancestry/registration validators.

Only the original capture reader and configuration parser are fixture seams;
no native Save/Load result is claimed by these tests.
"""
from contextlib import ExitStack
from dataclasses import replace
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import network_checkpoint as cp, xp1_saved_load as saved
from civ6_host.runtime.xp1_session_checkpoint import expected_readback
from civ6_host.runtime.native import native_official_bundle as official
from civ6_host.runtime.native.native_official_load import OfficialInputs
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, BASE_CORE_SHA256


class CheckpointLineageTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(
            prefix='xp1-checkpoint-lineage-', dir=cp._root()/'work')))
        self.config, self.game = b'configuration-fixture', b'\x05\0\0\0game-fixture'
        self.maps = (('MAP_SIZE',23),)
        self.o = dict(turn=2,width=74,height=46,player_id=0,economy=dict(gold=10),
                      cities=[],units=[dict(id=1,type=2,x=3,y=4,damage=0,moves=1)])
        for name,value in [('CONFIGURATION_BYTES',len(self.config)),
                ('CONFIGURATION_SHA256',hashlib.sha256(self.config).hexdigest()),
                ('GAME_BYTES',len(self.game)),('GAME_SHA256',hashlib.sha256(self.game).hexdigest())]:
            self.stack.enter_context(patch.object(saved,name,value))
        self.stack.enter_context(patch.object(official,'parse_configuration',return_value=(self.config,self.maps)))
        validators={key:'a'*64 for key in official._PREPARED_BUNDLE_VALIDATOR_PATHS}
        self.stack.enter_context(patch.object(official,'_prepared_bundle_validator_digests',return_value=validators))
        self.stack.enter_context(patch('civ6_host.runtime.xp1_bundle_inputs.reader_validator_digests',return_value={'source':'b'*64}))
        inputs=OfficialInputs(self.config,self.game,self.maps,saved.XP1_LAN_PROFILE,official_bundle=saved.REFERENCE)
        self.original=official.PreparedBundle(saved.REFERENCE,inputs,1,Path('XP1.dll'),{},
            {'source':'c'*64},dict(turn=1,width=74,height=46,player_id=0),
            dict(engine=dict(gamecore_sha256=XP1_CORE_SHA256)))
        official._remember_prepared_bundle(self.original,'xp1-lan',validators,
            _token=official._PARENT_ADMISSION_TOKEN,_input_only=True)
        self.stack.enter_context(patch.object(saved,'consume_input_handoff',return_value=self.original))
        # Stream equivalence has separate real codec coverage; here the join is
        # under test and bytes remain distinct, hash-bound native-pair fixtures.
        self.stack.enter_context(patch('civ6_host.runtime.native.official_configuration.compare_provider_roundtrip'))
        producer=self.root/'producer'; producer.mkdir()
        pair=producer/'checkpoint'; pair.mkdir()
        db=producer/'private.sqlite'; db.write_bytes(b'private-db-fixture')
        fixture=producer/'fixture.json'
        self.write(fixture,dict(databases=dict(game=dict(path=str(db),sha256=self.sha(db.read_bytes())))))
        closure=producer/'closure.json'
        self.write(closure,dict(input_profile='xp1-lan',checkpoint_on_close=True,
            official_bundle=dict(zip(('path','sha256'),saved.REFERENCE)),
            database_profile=official.DATABASE_PROFILE,fixture=str(fixture),prepared_capture={'fixture':True}))
        self.write(producer/'supervisor.json',dict(reaped=True,exit_code=90,timed_out=False,error=None,
                                                  source_unchanged={'fixture':True}))
        components={}
        for key,raw in [('gamecore',self.game+b'saved'),('application_configuration',self.config+b'saved')]:
            p=pair/(key+'.raw'); p.write_bytes(raw); components[key]=cp.reference(p)
        self.m=dict(schema=cp.SCHEMA,input_profile=saved.XP1_LAN_PROFILE.name,core_sha256=XP1_CORE_SHA256,
            native_save_status=0,stream_closed=True,jobs_quiescent_unchanged=True,
            full_civ6save_container=False,lineage_depth=0,parent_checkpoint=None,
            observed_game_turn=2,player_id=0,observation=self.o,decisions=dict(turn=2,player_id=0),
            network_boundary=dict(session=dict(turn=2)),
            source_official_bundle=dict(zip(('path','sha256'),saved.REFERENCE)),components=components,
            input_components_sha256=dict(gamecore=self.sha(self.game),application_configuration=self.sha(self.config)),
            session_closure=cp.reference(closure),fixture=cp.reference(fixture),source_proofs=[],
            database_profile=official.DATABASE_PROFILE)
        self.manifest_path=pair/'checkpoint.json'; self.ref=self.write_manifest()
        consumer=self.root/'consumer'; consumer.mkdir()
        copied=consumer/'private.sqlite'; copied.write_bytes(db.read_bytes())
        current=consumer/'fixture.json'
        self.write(current,dict(databases=dict(game=dict(path=str(copied),sha256=self.sha(copied.read_bytes())))))
        self.closure=dict(input_profile='xp1-lan', database_profile=official.DATABASE_PROFILE,
            official_bundle=self.m['source_official_bundle'], initial_turn=2,
            network_checkpoint=self.ref, fixture=str(current))

    @staticmethod
    def sha(raw): return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def write(path,value): path.write_text(json.dumps(value),encoding='utf-8')

    def write_manifest(self):
        self.write(self.manifest_path,self.m)
        return cp.reference(self.manifest_path)

    def test_exact_pair_resumes_through_real_registration_and_keeps_original_capture(self):
        m=cp.manifest(self.ref,official_bundle=saved.REFERENCE)
        resumed=cp.resume_bundle(self.original,self.closure)
        self.assertEqual(resumed.expected_readback,expected_readback(self.o))
        self.assertEqual(resumed.inputs.checkpoint,cp.normalize(self.ref))
        self.assertIs(saved.validate_candidate_inputs(resumed.inputs,resumed),saved.XP1_LAN_PROFILE)
        self.assertIsNone(self.original.inputs.checkpoint)
        self.assertEqual(m['input_components_sha256']['gamecore'],self.sha(self.game))
        self.assertEqual(resumed.reference,self.original.reference)
        # Deliberately bypass the frozen dataclass to exercise fingerprint
        # rejection as well as the ordinary immutable-input boundary.
        object.__setattr__(resumed.inputs,'checkpoint',(resumed.inputs.checkpoint[0],'f'*64))
        with self.assertRaisesRegex(ValueError,'contents changed'):
            saved.validate_candidate_inputs(resumed.inputs,resumed)

    def test_unregistered_copy_cannot_claim_the_same_checkpoint(self):
        resumed=cp.resume_bundle(self.original,self.closure)
        copied=replace(resumed)
        with self.assertRaisesRegex(ValueError,'parent-admitted'):
            saved.validate_candidate_inputs(copied.inputs,copied)

    def test_resumed_validation_reuses_one_fully_checked_manifest_without_caching(self):
        resumed=cp.resume_bundle(self.original,self.closure)
        original_manifest=cp.manifest
        with patch.object(cp,'manifest',wraps=original_manifest) as checked:
            self.assertIs(saved.validate_candidate_inputs(resumed.inputs,resumed),saved.XP1_LAN_PROFILE)
            self.assertEqual(checked.call_count,1)
        # A later call must reread the provenance, even for the identical owner.
        producer=self.root/'producer'/'supervisor.json'
        value=json.loads(producer.read_bytes());value['reaped']=False;self.write(producer,value)
        with patch.object(cp,'manifest',wraps=original_manifest) as checked:
            with self.assertRaisesRegex(ValueError,'did not finish'):
                saved.validate_candidate_inputs(resumed.inputs,resumed)
            self.assertEqual(checked.call_count,1)

    def test_validated_manifest_is_returned_only_for_the_matching_component_bytes(self):
        resumed=cp.resume_bundle(self.original,self.closure)
        m=cp.validate_inputs(resumed.inputs)
        self.assertEqual(m['observation'],self.o)
        with self.assertRaisesRegex(ValueError,'component differs'):
            cp.validate_inputs(replace(resumed.inputs,game=resumed.inputs.game+b'changed'))

    def test_native_roster_join_uses_restored_turn_instead_of_original_capture_turn(self):
        resumed=cp.resume_bundle(self.original,self.closure)
        backend=SimpleNamespace(inputs=resumed.inputs,captured_bundle=resumed,
                                host=SimpleNamespace(configured_local_player_id=0))
        humans=b'0=1|1=0|2=0|3=0|4=0|5=0'
        receipt=saved.validate_loaded_roster(backend,b'2|74|46|0|1|2|3|4|5',humans)
        self.assertEqual(receipt['human_player_ids'],[0])
        with self.assertRaisesRegex(ValueError,'roster/map/turn differs'):
            saved.validate_loaded_roster(backend,b'1|74|46|0|1|2|3|4|5',humans)

    def test_engine_profile_and_producer_closure_must_agree(self):
        self.m['core_sha256']=BASE_CORE_SHA256
        with self.assertRaisesRegex(ValueError,'provenance'):
            cp.manifest(self.write_manifest(),official_bundle=saved.REFERENCE)
        self.m['core_sha256']=XP1_CORE_SHA256
        closure=cp._path(self.m['session_closure']['path'])
        value=json.loads(closure.read_bytes()); value['input_profile']='lan'; self.write(closure,value)
        self.m['session_closure']=cp.reference(closure)
        with self.assertRaisesRegex(ValueError,'closure differs'):
            cp.manifest(self.write_manifest(),official_bundle=saved.REFERENCE)

    def test_original_bytes_closed_worker_and_distinct_private_databases_are_required(self):
        for field,value in [('reaped',False),('exit_code',125),('source_unchanged',{'fixture':False})]:
            p=self.root/'producer'/'supervisor.json'; original=json.loads(p.read_bytes())
            changed=deepcopy(original); changed[field]=value; self.write(p,changed)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'did not finish'):
                cp.manifest(self.ref,official_bundle=saved.REFERENCE)
            self.write(p,original)
        same=dict(self.closure,fixture=str(cp._path(self.m['fixture']['path'])))
        with self.assertRaisesRegex(ValueError,'distinct, identical'):
            cp.resume_bundle(self.original,same)
        self.m['input_components_sha256']['gamecore']='f'*64
        with self.assertRaisesRegex(ValueError,'lineage root differs'):
            cp.manifest(self.write_manifest(),official_bundle=saved.REFERENCE)


if __name__=='__main__': unittest.main()

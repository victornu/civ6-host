"""Private XP2 source/lineage candidate checks; no Save or DLL execution.

The binder uses PE-file-backed fixture memory. The lineage tests exercise real
Python validators/registration with retained native streams and explicit
producer/capture fixtures; they do not fabricate an executed Save or reload.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes as C
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_checkpoint_profile as selected
from civ6_host.runtime import xp2_checkpoint_source as source
from civ6_host.runtime import xp2_bundle_inputs as inputs_profile
from civ6_host.runtime import network_checkpoint as cp
from civ6_host.runtime import captured_saved_load as captured
from civ6_host.runtime import xp1_session_checkpoint as session_checkpoint
from civ6_host.runtime.native import native_official_bundle as official
from civ6_host.runtime.native import native_session_resume as resume
from civ6_host.runtime.native import network_session
from civ6_host.runtime.native.native_official_load import OfficialInputs
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_profiles import profile_for_sha
from civ6_host.runtime.saved_load_services import SavedLoadServices

CHECKOUT=Path(__file__).resolve().parents[1]
HOST=CHECKOUT.parents[2] if CHECKOUT.name=='candidate' else CHECKOUT
CANDIDATE=HOST/'work/xp2-checkpoint-preparation/candidate'
LAB=resource_root()
BASE=0x180000000
CORE=inputs_profile.XP2_CORE_SHA256
GAME_STREAM=LAB/'work/official-capture/xp2-gs-lan-rows-20261102-04/save-capture/48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430/section-02-00011980-gamecore_stream_candidate.raw'


class BinderMemory:
    """Explicit source bytes and native-object identities, without process reads."""
    def __init__(self):
        import pefile
        p=source.verify_source()[0]
        self.pe=pefile.PE(p['image']['path'],fast_load=True);self.raw=Path(p['image']['path']).read_bytes()
        self.blocks={};self.context=0x61000000;self.inner=0x61000100;self.game=0x61000200
        self.q(self.context,BASE+0xa101e8);self.q(self.context+8,self.inner)
        self.q(self.inner,BASE+0xa44f70);self.q(self.inner+0x60,self.game)
        self.q(BASE+0xb8aa68,self.game)
        for global_rva,instance,vt in ((0xb8b298,0x61000400,0x9c1240),(0xb8e298,0x61000500,0x9f31f0)):
            self.q(BASE+global_rva,instance);self.q(instance,BASE+vt)
        self.put(0x61000508,struct.pack('<I',7))
        self.q(self.game+8,0x61000600);self.q(self.game+0x10,0x61000720)
        self.put(BASE+0xb60cd0,struct.pack('<I',0));self.q(0x61000600,0x61000800)
        self.q(0x61000800,BASE+0xa45e48)
    def put(self,address,raw):self.blocks[address]=raw
    def q(self,address,value):self.put(address,struct.pack('<Q',value))
    def read(self,address,size):
        for begin,raw in reversed(tuple(self.blocks.items())):
            if begin<=address and address+size<=begin+len(raw):return raw[address-begin:address-begin+size]
        if BASE<=address<BASE+self.pe.OPTIONAL_HEADER.SizeOfImage:
            offset=self.pe.get_offset_from_rva(address-BASE);return self.raw[offset:offset+size]
        raise AssertionError('Unspecified fixture memory '+hex(address))


class SourceCandidateTests(unittest.TestCase):
    def fixture(self):
        memory=BinderMemory();session=SavedLoadServices.__new__(SavedLoadServices)
        session.core=NS(_handle=BASE);session.context=memory.context
        session.backend=NS(prefix=session,core=session.core,context=session.context,
            load_abi=profile_for_sha(CORE),check_thread=lambda:None)
        return memory,session

    def test_exact_source_selected_independent_exe_contract_and_existing_provider(self):
        p,s,r=source.verify_source();abi=selected.save_abi(CORE)
        self.assertEqual(abi.outer_save_rva,p['tables']['outer']['slots']['0x168'])
        self.assertEqual(abi.inner_save_rva,p['tables']['inner']['slots']['0x78'])
        self.assertIn('EXE 0x14016d42f',p['slot_authority']['save'])
        self.assertEqual(selected.provider_proof(CORE),'46ddfc453e1bf0d9de7cd5509173ebad3e25cf4d208906e08701d2ab790e8387')
        pins=selected.source_dependencies(core_sha256=CORE)
        for ref in (source.SOURCE,source.SUPPLEMENT,source.RULES):self.assertIn(ref[1],pins.values())
        with self.assertRaises(ValueError):source.verify_source(selected.XP1_CORE_SHA256)

    def test_actual_selected_source_binder_checks_all_native_direct_interfaces(self):
        memory,session=self.fixture();before=deepcopy(memory.blocks)
        with patch.object(SavedLoadServices,'check',autospec=True):
            p=source.bind_source(session,memory.read,core_sha256=CORE)
        self.assertEqual(set(p['core_functions']),{'save_outer','inner_save'})
        self.assertTrue(all('va' in r for b in p['core_functions'].values() for r in b['instructions']))
        self.assertEqual(memory.blocks,before)
        self.assertEqual(p['native_owner_identity']['xp2_rules_scalar'],7)
        memory.q(BASE+0xb8b298,0x61000900);memory.q(0x61000900,BASE+0x9c1240)
        with patch.object(SavedLoadServices,'check',autospec=True):
            after=source.bind_source(session,memory.read,core_sha256=CORE)
        self.assertNotEqual(p['native_owner_identity'],after['native_owner_identity'])

    def test_wrong_slot_version_native_owner_registry_and_code_refuse_read_only(self):
        faults=('slot','version','rules','delegate','notifications','registry','game','body')
        for fault in faults:
            memory,session=self.fixture()
            if fault=='slot':memory.q(BASE+0xa44f70+0x78,BASE+selected.XP1.inner_save_rva)
            elif fault=='version':memory.put(BASE+0x9bfbb8,b'\x04\0\0\0')
            elif fault=='rules':memory.q(0x61000400,BASE+0xa45160)
            elif fault=='delegate':memory.q(0x61000500,BASE+0x9c1240)
            elif fault=='notifications':memory.q(0x61000800,BASE+0xa45160)
            elif fault=='registry':memory.put(BASE+0xb60cd0,struct.pack('<I',1))
            elif fault=='game':memory.q(BASE+0xb8aa68,0x61000900)
            else:memory.put(BASE+0x472c0,b'\xcc'*5)
            before=deepcopy(memory.blocks)
            with self.subTest(fault=fault),patch.object(SavedLoadServices,'check',autospec=True):
                with self.assertRaises(ValueError):source.bind_source(session,memory.read,core_sha256=CORE)
            self.assertEqual(memory.blocks,before)

    def test_original_xp2_pair_still_requires_exact_original_turn_and_components(self):
        # Original-capture admission does not use the resumed branch.
        rawconfig=(HOST/'work/xp2-bundle-inputs/configuration.bin').read_bytes()
        rawgame=GAME_STREAM.read_bytes()
        inputs_profile.validate_components(rawconfig,rawgame)
        with self.assertRaises(ValueError):inputs_profile.validate_components(rawconfig,rawgame+b'changed')
        self.assertEqual(cp._profile_engine(inputs_profile.XP2_LAN_PROFILE.name),CORE)
        self.assertEqual(cp._capture_mode(inputs_profile.XP2_LAN_PROFILE.name),'xp2-lan')
        with self.assertRaises(ValueError):cp._profile_engine('unknown')

    def test_generated_shared_binder_retains_selected_extra_owner_identity(self):
        from civ6_host.runtime.native import native_checkpoint_diagnostic as diagnostic
        memory,session=self.fixture();calls=[]
        def factory(result,*args):
            def bind(address):
                def invoke(*values):
                    calls.append(address)
                    if address==BASE+0x590660:return True
                    raise AssertionError('No Save is executed by the source/binder fixture')
                return invoke
            return bind
        with patch.object(SavedLoadServices,'check',autospec=True),patch.object(C,'WINFUNCTYPE',factory):
            call,identity=diagnostic.bind_save(session,NS(read=memory.read),core_sha256=CORE)
        self.assertTrue(callable(call));self.assertEqual(calls,[BASE+0x590660])
        self.assertEqual(identity['xp2_notifications'],0x61000800)
        self.assertEqual(identity['xp2_rules_scalar'],7)


class PreparedReaderCandidateTests(unittest.TestCase):
    def fixture(self):
        from civ6_host.runtime import capture_admission as admission
        path=LAB/'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'
        manifest=json.loads(path.read_bytes());producer=manifest['validation_identity']
        consumer=admission.validation_identity()
        accepted=admission.admit_producer(producer,consumer)
        reference=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return admission,producer,consumer,accepted,manifest,reference

    def test_exact_prepared_package_retains_producer_and_original_branch_review(self):
        admission,producer,consumer,accepted,manifest,reference=self.fixture()
        transitions=admission._check_xp2_prepared_reader(producer,consumer,accepted,manifest,reference)
        joins = {join['module']: join for join in transitions[0]['reviewed_input_transitions']}
        self.assertEqual(set(joins), {'runtime/xp2_bundle_inputs.py', 'runtime/capture_script_paths.py'})
        relocated = joins['runtime/capture_script_paths.py']
        self.assertEqual(relocated['transition'], 'xp2_script_proof_physical_path_relocation_v1')
        self.assertTrue(relocated['logical_reference_preserved'])
        self.assertTrue(relocated['proof_bytes_rechecked'])
        self.assertFalse(relocated['producer_identity_substituted'])
        key = 'runtime/xp2_bundle_inputs.py'
        pair = joins[key]
        proof=CANDIDATE/'evidence/input-reader-source-review-v2.json'
        self.assertEqual(hashlib.sha256(proof.read_bytes()).hexdigest(),pair['source_review_sha256'])
        self.assertEqual(pair['producer_sha256'],producer['runtime_sources'][key])
        self.assertEqual(pair['consumer_sha256'],consumer['runtime_sources'][key])
        self.assertTrue(pair['original_capture_branch_unchanged'])
        self.assertFalse(pair['producer_identity_substituted'])
        self.assertFalse(transitions[0]['native_session_admitted'])
        # Raw bundle parsing remains byte-identical for XP1 and XP2.
        key='runtime/native/native_official_bundle.py'
        self.assertEqual(consumer['runtime_sources'][key],producer['runtime_sources'][key])

    def test_unknown_validator_versions_and_wrong_package_do_not_inherit_transition(self):
        admission,producer,consumer,accepted,manifest,reference=self.fixture()
        for side,key in (('producer','runtime/xp2_bundle_inputs.py'),
                         ('producer','runtime/native/official_save.py'),
                         ('consumer','runtime/xp2_bundle_inputs.py')):
            a,b=deepcopy(producer),deepcopy(consumer)
            (a if side=='producer' else b)['runtime_sources'][key]='f'*64
            with self.subTest(side=side,key=key),self.assertRaises(ValueError):
                admission._check_xp2_prepared_reader(a,b,accepted,manifest,reference)
        with self.assertRaises(ValueError):
            admission._check_xp2_prepared_reader(producer,consumer,accepted,manifest,dict(reference,sha256='f'*64))

    def test_normal_noncheckpoint_xp2_closure_delegates_the_same_raw_guard(self):
        closure=dict(input_profile='xp2-lan',database_profile=official.DATABASE_PROFILE,
            official_bundle=dict(zip(('path','sha256'),inputs_profile.REFERENCE)),
            initial_turn=1,checkpoint_on_close=False)
        captured.validate_closure_profile(closure)
        with patch.object(official,'validate_closure_profile',wraps=official.validate_closure_profile) as guard:
            captured.validate_closure_profile(closure)
        guard.assert_called_once_with(closure)
        changed=dict(closure,checkpoint_on_close=True)
        captured.validate_closure_profile(changed)
        with self.assertRaises(ValueError):
            captured.validate_closure_profile(dict(changed,resume_checkpoint={'foreign':'Base'}))


class LineageCandidateTests(unittest.TestCase):
    """Real manifest joins with explicit capture/closed-producer fixtures."""
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=CANDIDATE,prefix='checkpoint-fixture-')))
        (self.root/'work').mkdir()
        self.stack.enter_context(patch.object(cp,'_root',return_value=self.root))
        self.stack.enter_context(patch.object(resume,'ROOT',self.root))
        self.configuration=(HOST/'work/xp2-bundle-inputs/configuration.bin').read_bytes()
        self.serialized=(LAB/'work/native-xp2-configuration/run-20261102T092527Z-1fca62ada8ba/configuration-output.bin').read_bytes()
        self.game=GAME_STREAM.read_bytes()
        _,maps=official.parse_configuration(self.configuration,'LAN')
        self.inputs=OfficialInputs(self.configuration,self.game,maps,inputs_profile.XP2_LAN_PROFILE,
                                  official_bundle=inputs_profile.REFERENCE)
        self.producer=self.root/'work/producer';self.producer.mkdir()
        self.fixture=self.producer/'fixture.json'
        databases={}
        for name in ('configuration','gameplay','localization'):
            path=self.producer/(name+'.fixture');path.write_bytes(name.encode('ascii'))
            databases[name]=dict(path=str(path),sha256=self.sha(path.read_bytes()),size_bytes=path.stat().st_size)
        self.write(self.fixture,dict(databases=databases))
        self.original=official.PreparedBundle(inputs_profile.REFERENCE,self.inputs,1,Path(source.verify_source()[0]['image']['path']),
            dict(databases=deepcopy(databases)),{},dict(turn=1,width=44,height=26,player_id=0),
            dict(engine=dict(gamecore_sha256=CORE),gameplay_scripts=dict(selected_and_active_empty=False,
                selected_path_count=1,active_count=1,source_records=1,source_files=1)))
        official._remember_prepared_bundle(self.original,'xp2-lan',official._prepared_bundle_validator_digests(),
            _token=official._PARENT_ADMISSION_TOKEN,_input_only=True)
        self.stack.enter_context(patch.object(inputs_profile,'consume_input_handoff',return_value=self.original))
        self.close=self.stack.enter_context(patch.object(network_session,'xp1_loaded_close_evidence',return_value={'fixture_only':True}))
        self.components={};self.virtual_components={}
        pair=self.producer/'checkpoint';pair.mkdir()
        # Retained genuine native streams are supplied in memory by the fixture
        # file reader. No synthetic serialized stream or native result is saved.
        for key,raw in (('gamecore',self.game),('application_configuration',self.serialized)):
            path=pair/(key+'.raw');relative=path.relative_to(self.root).as_posix()
            self.components[key]=dict(path=relative,sha256=self.sha(raw),bytes=len(raw))
            self.virtual_components[relative]=raw
        actual_checked=cp._checked
        def fixture_checked(row):
            if row['path'] in self.virtual_components:
                raw=self.virtual_components[row['path']]
                if len(raw)!=row['bytes'] or self.sha(raw)!=row['sha256']:raise ValueError('Fixture component hash differs')
                return raw
            if row['path'] in {source.SOURCE[0],source.SUPPLEMENT[0],source.RULES[0]}:
                raw=(LAB/row['path']).read_bytes()
                if self.sha(raw)!=row['sha256'] or len(raw)!=row['bytes']:
                    raise ValueError('Static source fixture pin differs')
                return raw
            return actual_checked(row)
        self.stack.enter_context(patch.object(cp,'_checked',side_effect=fixture_checked))
        closure=self.producer/'closure.json'
        self.write(closure,dict(input_profile='xp2-lan',checkpoint_on_close=True,
            official_bundle=dict(zip(('path','sha256'),inputs_profile.REFERENCE)),
            database_profile=official.DATABASE_PROFILE,fixture=str(self.fixture),prepared_capture={'fixture_only':True},pins={}))
        self.write(self.producer/'supervisor.json',dict(reaped=True,exit_code=90,timed_out=False,error=None,
            source_unchanged={'fixture_only':True}))
        self.observation=dict(turn=2,width=44,height=26,player_id=0,economy=dict(gold=10),cities=[],units=[])
        self.m=dict(schema=cp.SCHEMA,input_profile=inputs_profile.XP2_LAN_PROFILE.name,core_sha256=CORE,
            native_save_status=0,stream_closed=True,jobs_quiescent_unchanged=True,full_civ6save_container=False,
            lineage_depth=0,parent_checkpoint=None,observed_game_turn=2,player_id=0,observation=self.observation,
            decisions=dict(turn=2,player_id=0),network_boundary=dict(session=dict(turn=2)),
            source_official_bundle=dict(zip(('path','sha256'),inputs_profile.REFERENCE)),components=self.components,
            input_components_sha256=dict(gamecore=self.sha(self.game),application_configuration=self.sha(self.configuration)),
            session_closure=cp.reference(closure),fixture=cp.reference(self.fixture),
            source_proofs=[dict(path=ref[0],sha256=ref[1],bytes=(LAB/ref[0]).stat().st_size)
                           for ref in (source.SOURCE,source.SUPPLEMENT,source.RULES)],
            game_version_prefix='05000000',configuration_receipt=dict(operation='serialize',core_sha256=CORE,
                proof_sha256=selected.provider_proof(CORE),sha256=self.sha(self.serialized),bytes=len(self.serialized),
                identity_checked_before_after=True,native_return_interpreted=False),
            database_profile=official.DATABASE_PROFILE)
        self.manifest_path=pair/'checkpoint.json';self.reference=self.write_manifest()
        consumer=self.root/'work/consumer';consumer.mkdir()
        new={}
        for key,row in databases.items():
            path=consumer/(key+'.fixture');path.write_bytes(Path(row['path']).read_bytes())
            new[key]=dict(row,path=str(path))
        self.new_fixture=consumer/'fixture.json';self.write(self.new_fixture,dict(databases=new))
        self.closure=dict(input_profile='xp2-lan', database_profile=official.DATABASE_PROFILE,
            official_bundle=self.m['source_official_bundle'], initial_turn=2,
            network_checkpoint=self.reference, fixture=str(self.new_fixture))

    @staticmethod
    def sha(raw):return hashlib.sha256(raw).hexdigest()
    @staticmethod
    def write(path,value):path.write_text(json.dumps(value),encoding='utf-8')
    def write_manifest(self):self.write(self.manifest_path,self.m);return cp.reference(self.manifest_path)

    def child(self,*,reuse_databases=False):
        producer=self.root/'work/child';producer.mkdir();pair=producer/'checkpoint';pair.mkdir()
        fixture=json.loads(self.fixture.read_bytes())
        if not reuse_databases:
            for key,row in fixture['databases'].items():
                path=producer/(key+'.fixture');path.write_bytes(Path(row['path']).read_bytes())
                row['path']=str(path)
        fixture_path=producer/'fixture.json';self.write(fixture_path,fixture)
        closure=json.loads(cp._checked(self.m['session_closure']))
        closure.update(fixture=str(fixture_path),network_checkpoint={k:self.reference[k] for k in ('path','sha256')})
        closure_path=producer/'closure.json';self.write(closure_path,closure)
        self.write(producer/'supervisor.json',dict(reaped=True,exit_code=90,timed_out=False,error=None,source_unchanged={'fixture_only':True}))
        child=deepcopy(self.m)
        child.update(lineage_depth=1,parent_checkpoint=self.reference,
            input_components_sha256={key:row['sha256'] for key,row in self.m['components'].items()},
            session_closure=cp.reference(closure_path),fixture=cp.reference(fixture_path))
        child['components']={}
        for key,row in self.m['components'].items():
            path=(pair/(key+'.raw')).relative_to(self.root).as_posix()
            child['components'][key]=dict(row,path=path)
            self.virtual_components[path]=self.virtual_components[row['path']]
        target=pair/'checkpoint.json';self.write(target,child)
        return child,target,cp.reference(target)

    def test_exact_derived_pair_registered_same_capture_and_selected_normalization(self):
        resumed=cp.resume_bundle(self.original,self.closure)
        self.assertIs(inputs_profile.validate_candidate_inputs(resumed.inputs,resumed),inputs_profile.XP2_LAN_PROFILE)
        self.assertEqual(resumed.initial_turn,2)
        self.assertEqual(resumed.inputs.configuration,self.serialized)
        self.assertEqual(resumed.inputs.game,self.game)
        self.assertEqual(resumed.content_profile,self.original.content_profile)
        self.assertEqual(resumed.dependencies,self.original.dependencies)
        self.assertEqual(resumed.fixture,self.original.fixture)
        self.assertIsNone(self.original.inputs.checkpoint)
        self.assertTrue(self.close.called)
        self.assertEqual(self.close.call_args.kwargs['core_sha256'],CORE)
        with self.assertRaises(ValueError):inputs_profile.validate_candidate_inputs(replace(resumed.inputs,game=b'foreign'),resumed)
        with self.assertRaises(ValueError):inputs_profile.validate_candidate_inputs(resumed.inputs,replace(resumed))

    def test_native_close_authentication_refusal_is_not_replaced_by_success_flags(self):
        self.close.side_effect=ValueError('fixture source/close refusal')
        with self.assertRaisesRegex(ValueError,'source/close refusal'):cp.manifest(self.reference)

    def test_wrong_engine_profile_origin_and_root_components_refuse(self):
        for key,value in (('core_sha256',selected.XP1_CORE_SHA256),('input_profile','unknown'),
                          ('input_components_sha256',dict(gamecore='f'*64,application_configuration=self.sha(self.configuration)))):
            original=self.m[key];self.m[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):cp.manifest(self.write_manifest())
            self.m[key]=original

    def test_source_database_identity_and_distinct_private_copies_refuse(self):
        old=self.m['fixture'];value=json.loads(self.fixture.read_bytes())
        value['databases']['gameplay']['sha256']='f'*64;self.write(self.fixture,value)
        self.m['fixture']=cp.reference(self.fixture)
        with self.assertRaises(ValueError):cp.manifest(self.write_manifest())
        # Restore this fixture before exercising independent copy ownership.
        value['databases']['gameplay']['sha256']=self.sha(Path(value['databases']['gameplay']['path']).read_bytes())
        self.write(self.fixture,value);self.m['fixture']=cp.reference(self.fixture);self.reference=self.write_manifest()
        with self.assertRaisesRegex(ValueError,'distinct, identical'):
            cp.resume_bundle(self.original,dict(self.closure,network_checkpoint=self.reference,fixture=str(self.fixture)))

    def test_resume_roster_uses_actual_derived_turn_and_keeps_capture_map_and_humans(self):
        resumed=cp.resume_bundle(self.original,self.closure)
        backend=NS(inputs=resumed.inputs,captured_bundle=resumed,host=NS(configured_local_player_id=0))
        self.assertEqual(captured.validate_loaded_roster(backend,b'2|44|26|0|1',b'0=1|1=0')['human_player_ids'],[0])
        for roster,humans in ((b'1|44|26|0|1',b'0=1|1=0'),(b'2|45|26|0|1',b'0=1|1=0'),(b'2|44|26|0|1',b'0=1|1=1')):
            with self.assertRaises(ValueError):captured.validate_loaded_roster(backend,roster,humans)

    def test_resume_refuses_closure_turn_engine_and_capture_before_pair_admission(self):
        for changed, message in (
            (dict(initial_turn=3), 'closure turn differs'),
            (dict(input_profile='xp1-lan'), 'prepared engine or capture'),
            (dict(official_bundle=dict(self.closure['official_bundle'], sha256='f'*64)),
             'prepared engine or capture'),
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, message):
                cp.resume_bundle(self.original, dict(self.closure, **changed))

    def test_provider_change_outside_proved_xp2_representation_refuses(self):
        self.virtual_components[self.components['application_configuration']['path']]=self.serialized[:-1]+bytes([self.serialized[-1]^1])
        raw=self.virtual_components[self.components['application_configuration']['path']]
        self.components['application_configuration'].update(sha256=self.sha(raw),bytes=len(raw));self.reference=self.write_manifest()
        self.m['configuration_receipt']['sha256']=self.sha(raw);self.reference=self.write_manifest()
        with self.assertRaises(ValueError):cp.resume_bundle(self.original,dict(self.closure,network_checkpoint=self.reference))

    def test_child_uses_immediate_pair_and_keeps_exact_original_capture(self):
        child,path,reference=self.child()
        result=cp.manifest(reference,official_bundle=inputs_profile.REFERENCE)
        self.assertEqual(result['lineage_depth'],1)
        self.assertEqual(result['parent_checkpoint'],self.reference)
        self.assertEqual(result['input_components_sha256'],{k:v['sha256'] for k,v in self.m['components'].items()})
        with patch.object(cp, '_validate_lineage', wraps=cp._validate_lineage) as validate_lineage, \
             patch.object(cp, '_checked', wraps=cp._checked) as checked:
            resumed=cp.resume_bundle(self.original,dict(self.closure,network_checkpoint=reference))
        validate_lineage.assert_called_once()
        reads = [call.args[0]['path'] for call in checked.call_args_list]
        for row in (*child['components'].values(), child['fixture']):
            self.assertEqual(reads.count(row['path']), 1)
        self.assertEqual(resumed.inputs.checkpoint,cp.normalize(reference))
        self.assertEqual(resumed.reference,inputs_profile.REFERENCE)
        modified = replace(resumed.inputs, game=resumed.inputs.game[:-1]
                           + bytes([resumed.inputs.game[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, 'component differs'):
            cp.validate_inputs(modified)

    def test_configure_and_validate_expansion_closure_in_one_pass(self):
        closure = dict(pins={}, input_profile='xp2-lan',
                       database_profile=official.DATABASE_PROFILE,
                       official_bundle=self.m['source_official_bundle'])
        ref = cp.normalize(self.reference)
        with patch.object(cp, '_validate_lineage', wraps=cp._validate_lineage) as lineage:
            cp.configure_closure(closure, ref, validate_fields=True)
        lineage.assert_called_once()
        self.assertEqual(closure['pins'][ref[0]], ref[1])
        cp.validate_closure(closure)
        invalid = dict(closure, pins={}, checkpoint_on_close=1)
        with self.assertRaisesRegex(ValueError, 'Unsupported LAN checkpoint closure'):
            cp.configure_closure(invalid, ref, validate_fields=True)
        self.assertEqual(invalid['pins'], {})

    def test_child_reusing_parent_databases_and_wrong_immediate_pair_refuse(self):
        child,path,reference=self.child(reuse_databases=True)
        with self.assertRaisesRegex(ValueError,'ancestry changed or reused'):cp.manifest(reference)
        # A source-valid root hash must not substitute for the immediate B pair.
        fixture=json.loads(cp._checked(child['fixture']))
        for key,row in fixture['databases'].items():
            file=path.parent.parent/(key+'.fixture');file.write_bytes(Path(row['path']).read_bytes());row['path']=str(file)
        fixture_path=cp._path(child['fixture']['path']);self.write(fixture_path,fixture)
        child['fixture']=cp.reference(fixture_path)
        child['input_components_sha256']['application_configuration']=self.sha(self.configuration)
        self.write(path,child)
        with self.assertRaisesRegex(ValueError,'ancestry components differ'):cp.manifest(cp.reference(path))

    def test_missing_save_proofs_foreign_producer_version_and_codec_receipt_refuse(self):
        cases=(('source_proofs',[]),('game_version_prefix','04000000'),
               ('configuration_receipt',dict(self.m['configuration_receipt'],proof_sha256='f'*64)),
               ('lineage_depth',65))
        for key,value in cases:
            original=self.m[key];self.m[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):cp.manifest(self.write_manifest())
            self.m[key]=original
        self.m['session_closure']=dict(self.m['session_closure'],path='work/elsewhere/closure.json')
        with self.assertRaises((ValueError,FileNotFoundError)):cp.manifest(self.write_manifest())

    def test_xp2_host_tracking_restores_on_continuation_after_boundary_check(self):
        metadata=dict(self.m,host_placement_tracking=[],host_world_selection=23)
        owner=NS(inputs=NS(profile=inputs_profile.XP2_LAN_PROFILE,checkpoint=('fixture','a'*64),
            official_bundle=inputs_profile.REFERENCE),continuation=NS())
        with (patch.object(cp,'manifest',return_value=metadata) as read_manifest,
              patch.object(session_checkpoint,'boundary',return_value=metadata['network_boundary']),
              patch.object(cp,'_compare_decisions') as compare):
            compare_initial = cp.prepare_owner(owner,self.observation)
            compare_initial(self.observation, metadata['decisions'])
            read_manifest.assert_called_once()
            compare.assert_called_once_with(owner, metadata, self.observation, metadata['decisions'])
        self.assertEqual(owner.continuation.explicit_placements,{})
        self.assertEqual(owner.continuation.world_input_selections,{0:23})
        self.assertFalse(hasattr(owner,'world_input_selections'))
        del owner.continuation.world_input_selections
        with patch.object(cp,'manifest',return_value=metadata),patch.object(session_checkpoint,'boundary',return_value={'wrong':True}):
            with self.assertRaises(ValueError):cp.prepare_owner(owner,self.observation)
        self.assertFalse(hasattr(owner.continuation,'world_input_selections'))


class AdministrativeBoundaryTests(unittest.TestCase):
    def test_saved_boundary_selects_xp2_timer_and_refuses_ai_or_prompt_work(self):
        from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
        from unittest.mock import Mock
        saved=object.__new__(SavedLoadOwner);saved._running=True
        saved.backend=NS(busy=True,load_abi=profile_for_sha(CORE),control=Mock())
        saved.continuation=NS(world_input_prompts={},transport=NS(require_empty_native_queue=Mock()))
        state=dict(human_player_ids=[0],active_human_player_ids=[0],local_player_id=0,turn=3)
        activity=dict(rows=[dict(player_id=0,active=True,active_complete=True,can_unready=False),
                            dict(player_id=1,active=False)])
        with patch.object(SavedLoadOwner,'_check_active'), \
                patch('civ6_host.runtime.xp1_session_view._reference',return_value=({},(0,1))), \
                patch('civ6_host.runtime.xp1_session_view._read_state',return_value=(state,activity)), \
                patch('civ6_host.runtime.network_timer.read',return_value=False) as timer:
            session_checkpoint.boundary(saved)
            timer.assert_called_once_with(saved.backend,core_sha256=CORE)
            activity['rows'][1]['active']=True
            with self.assertRaises(ValueError):session_checkpoint.boundary(saved)
            activity['rows'][1]['active']=False;saved.continuation.world_input_prompts={0:object()}
            with self.assertRaises(ValueError):session_checkpoint.boundary(saved)


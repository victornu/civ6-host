"""XP2 Post160 source/owner fixtures. No native DLL is loaded or executed."""
import ast
import ctypes as C
from dataclasses import replace
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_postload_candidate as candidate,postload160_source as shared
from civ6_host.runtime import xp2_postload_source as source,xp2_bundle_inputs as inputs
from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
from civ6_host.runtime.native import native_official_postload as official
from civ6_host.runtime.native import native_checkpoint_postload160 as native
from civ6_host.runtime.native import native_official_bundle as bundle_reader
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native.native_official_load import OfficialInputs
from civ6_host.runtime.paths import resource_root


class XP2Post160SourceTests(unittest.TestCase):
    def memory(self):
        proof=source.source();base=0x200000000;cells={}
        bodies=dict(proof['functions']['xp2']);bodies.update(source.active_source()['functions'])
        for body in bodies.values():
            for f in body['fragments']:
                for row in f['instructions']:
                    raw=bytes.fromhex(row['bytes']);cells[base+int(row['rva'],16),len(raw)]=raw
        for row in proof['tables']['xp2'].values():
            cells[base+row['vtable_rva']+row['slot'],8]=struct.pack('<Q',base+row['target_rva'])
        for address,literal in proof['literals'].items():
            cells[base+int(address,16)-0x180000000,literal['bytes']]=literal['text'].encode()+b'\0'
        return proof,base,cells

    def test_exact_route_complete_active_inventory_and_public_refusal(self):
        p=source.source();active=source.active_source();abi=shared.profile_for_sha(source.XP2_CORE_SHA256)
        self.assertEqual((abi.outer_vtable_rva,abi.target_rva,abi.inner_vtable_rva,abi.inner_target_rva),
                         (0xa101e8,0x590780,0xa44f70,0x463a0))
        self.assertEqual((p['functions']['xp2']['transition']['fragment_count'],
                          p['functions']['xp2']['transition']['bytes']),(7,469))
        self.assertEqual(len(active['functions']),57)
        self.assertEqual(sum(e['common_record_types'] is None for e in active['contract']['events']),13)
        self.assertFalse(active['contract']['pending_zero_only_gate'])
        self.assertFalse(active['contract']['native_active_player_qualification'])
        with self.assertRaisesRegex(ValueError,'XP2 outer'):shared.require_runtime_admission(abi)
        with self.assertRaisesRegex(ValueError,'canonical'):shared.require_runtime_admission(replace(abi))
        with self.assertRaisesRegex(ValueError,'Exact XP1'):shared.xp1_source(source.XP2_CORE_SHA256)
        self.assertIs(shared.expansion_source(source.XP2_CORE_SHA256),p)

    def test_live_complete_bodies_virtual_slots_and_literals_without_native_calls(self):
        p,base,cells=self.memory()
        read=lambda a,n:cells[a,n]
        shared.verify_expansion_live(base,read,p,core_sha256=source.XP2_CORE_SHA256)
        targets=[]
        for body in (p['functions']['xp2']['transition'],source.active_source()['functions']['visibility_change']):
            row=body['fragments'][-1]['instructions'][-1]
            targets.append((base+int(row['rva'],16),len(bytes.fromhex(row['bytes']))))
        targets.extend((base+r['vtable_rva']+r['slot'],8) for r in p['tables']['xp2'].values())
        targets.extend((base+int(a,16)-0x180000000,r['bytes']) for a,r in p['literals'].items())
        for key in targets:
            with self.subTest(key=key):
                old=cells[key];cells[key]=bytes([old[0]^1])+old[1:]
                with self.assertRaisesRegex(ValueError,'differs'):
                    shared.verify_expansion_live(base,read,p,core_sha256=source.XP2_CORE_SHA256)
                cells[key]=old
        with self.assertRaises(ValueError):source.verify_live(base,read,p,core_sha256=shared.XP1_CORE_SHA256)

    def test_all_private_source_and_retained_interval_pins_are_closed(self):
        pins=source.source_dependencies()
        self.assertIn(source.SOURCE[1],pins.values());self.assertIn(source.ACTIVE_SOURCE[1],pins.values())
        self.assertIn(source.source()['retained_interval']['events']['sha256'],pins.values())
        self.assertFalse(source.source()['retained_interval']['xp2_behavior_proven'])

    def test_unique_extraction_hook_selects_engine_source_without_writing_generated_files(self):
        import extraction_postload160 as previous
        import extraction_xp1_postload_candidate as hook
        path=resource_root()/'civ6rl/native_checkpoint_postload160.py'
        raw=path.read_text(encoding='utf-8').replace('from civ6rl import ',
            'from civ6_host.runtime.native import ')
        raw=ast.unparse(ast.parse(raw))+'\n'
        before=previous.parameterize('civ6rl.native_checkpoint_postload160',raw)
        after=hook.parameterize('civ6rl.native_checkpoint_postload160',before)
        self.assertIn('return expansion_source(core_sha256)',after)
        self.assertIn('return verify_expansion_live(base, read, proof, core_sha256=core_sha256)',after)
        tree=ast.parse(after)
        verify=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_source')
        namespace={};exec(compile(ast.Module(body=[verify],type_ignores=[]),'<fixture-hook>','exec'),namespace)
        self.assertIs(namespace['verify_source'](core_sha256=source.XP2_CORE_SHA256),source.source())
        self.assertIs(namespace['verify_source'](core_sha256=shared.XP1_CORE_SHA256),shared.xp1_source())
        with self.assertRaisesRegex(ValueError,'boundary changed'):
            hook.parameterize('civ6rl.native_checkpoint_postload160',before.replace('return xp1_source(core_sha256)','return wrong()'))


class XP2Post160CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Actual captured streams and their unpatched strict input validator.
        # The expensive whole-capture/DB reader has its own qualification tests;
        # this owner fixture is not registered as a parent-admitted bundle.
        from civ6_host.runtime.native.official_application_configuration import extract_application_configuration
        folder=resource_root()/'work/official-capture/xp2-gs-lan-rows-20261102-04/save-capture'/\
            '48b816c0af186d477f412c10bba40d22f1281d57341d4c5644e95a0e2ce0a430'
        configuration,_=extract_application_configuration((folder/'source.Civ6Save').read_bytes())
        _,maps=bundle_reader.parse_configuration(configuration,'LAN')
        game=(folder/'section-02-00011980-gamecore_stream_candidate.raw').read_bytes()
        pair=OfficialInputs(configuration,game,maps,profile=inputs.XP2_LAN_PROFILE,official_bundle=inputs.REFERENCE)
        cls.bundle=bundle_reader.PreparedBundle(inputs.REFERENCE,pair,1,Path('fixture-no-engine.dll'),{},{},
            dict(turn=1,width=44,height=26,player_id=0),
            dict(engine={'gamecore_sha256':source.XP2_CORE_SHA256},gameplay_scripts=dict(
                selected_and_active_empty=False,selected_path_count=1,active_count=1,source_records=1,source_files=1)))
        inputs.validate_candidate_inputs(pair,cls.bundle)

    def graph(self):
        b=OfficialLoadBackend.__new__(OfficialLoadBackend)
        b.stage='facades-candidate-observed';b.busy=False;b.check_thread=Mock();b.control=Mock()
        b.poisoned=b.destroyed=False;b._saved_load_candidate=True
        b.load_abi=NS(core_sha256=source.XP2_CORE_SHA256)
        b.captured_bundle=self.bundle;b.inputs=self.bundle.inputs
        b.loaded_readback=dict(self.bundle.expected_readback);b.loaded_roster=b'1|44|26|0|1'
        b.prefix=NS(quarantined=False,view_publisher=None)
        b.thread=(1,2);b.runtime=NS(thread=Mock(return_value=b.thread),read=Mock())
        b.core=NS(_handle=0x200000000);b.context=0x300000000;b.snapshot_phase='idle';b.emit=Mock()
        a=official.OfficialFacadeBackend.__new__(official.OfficialFacadeBackend)
        a.owner=b;a.publication_mode='candidate';a.attempted=True
        a.publisher=NS(native_cache_gate=False,full_facade_initialization_reproduced=False)
        b.prefix.view_publisher=a.publisher
        lease=LoadedCachePublication.__new__(LoadedCachePublication)
        lease.owner=b;lease.prefix=b.prefix;lease.attempt=a;lease.publisher=a.publisher;lease.stage='raw-loaded'
        lease.entered=lease.returned=lease.copied=True;lease.poisoned=False;lease._check_state=Mock()
        a.publication_owner=lease
        with patch.object(native,'verify_source',side_effect=lambda **kw:shared.expansion_source(kw['core_sha256'])):
            post=official.OfficialPost160Backend(b,a,{},postload_mode='candidate')
        post._facade_attempt=a
        return b,a,lease,post

    def test_captured_pair_owns_one_shared_candidate_and_public_route_stays_closed(self):
        b,a,lease,post=self.graph()
        self.assertEqual(post.expected_major_ids,(0,1));self.assertIs(b._xp1_post160_attempt,post)
        self.assertIs(post._candidate_cache_lease,lease)
        self.assertIs(post.post160_abi,shared.profile_for_sha(source.XP2_CORE_SHA256))
        with self.assertRaisesRegex(ValueError,'XP2 outer'):official.OfficialPost160Backend(b,a,{})
        with self.assertRaisesRegex(ValueError,'first exact'):
            official.OfficialPost160Backend(b,a,{},postload_mode='candidate')

    def test_wrong_roster_readback_engine_and_owner_are_refused(self):
        b,a,lease,post=self.graph()
        for raw in (b'2|44|26|0|1',b'1|74|46|0|1',b'1|44|26|0|2'):
            b.loaded_roster=raw
            with self.assertRaisesRegex(ValueError,'roster/turn/map'):candidate.expected_major_ids(b)
        b.loaded_roster=b'1|44|26|0|1';b.loaded_readback=dict(b.loaded_readback,turn=2)
        with self.assertRaisesRegex(ValueError,'captured loaded readback'):candidate.expected_major_ids(b)
        b.loaded_readback=dict(self.bundle.expected_readback);b.inputs=object()
        with self.assertRaisesRegex(ValueError,'captured input pair'):candidate.expected_major_ids(b)
        b.inputs=self.bundle.inputs;b.load_abi=NS(core_sha256=shared.XP1_CORE_SHA256)
        with self.assertRaises(ValueError):candidate.expected_major_ids(b)

    def test_shared_native_call_uses_xp2_target_void_abi_and_unmodified_raw_state(self):
        b,a,lease,post=self.graph();lease.begin_post160(post);b.snapshot_phase='before'
        values=dict(current=2,pending=7,requested=1,remaining=0,player_or_target=1,stop_limit_or_parameter=0xffffffff)
        fields=post.proof['contract']['state_globals'];after=dict(values,pending=0,current=1)
        def read(address,size):
            for key,rva in fields.items():
                if b.core._handle+rva==address:return values[key].to_bytes(size,'little')
            raise AssertionError(address)
        b.runtime.read=read
        call=Mock(side_effect=lambda *_:values.update(after));binder=Mock(return_value=call)
        with patch.object(candidate,'_aux90'),patch.object(native,'check_live_post160') as live,\
             patch.object(C,'WINFUNCTYPE',return_value=binder) as signature:
            self.assertIsNone(post.call_post160_once())
            signature.assert_called_once_with(None,C.c_void_p,C.c_uint8)
            binder.assert_called_once_with(b.core._handle+0x590780);call.assert_called_once_with(b.context,1)
            self.assertEqual(live.call_args.kwargs['core_sha256'],source.XP2_CORE_SHA256)
            self.assertEqual(post.candidate_diagnostics['branch_inferred_from_native_prestate'],'requested_raw_state_differs')
            self.assertEqual(post.candidate_diagnostics['source_sha256'],source.SOURCE[1])
            self.assertFalse(post.candidate_diagnostics['state_modified_by_host'])
            self.assertFalse(post.candidate_diagnostics['transitive_player_aux_effects_qualified'])
            self.assertEqual(b.emit.call_args_list[0].args[0],'xp2_post160_transition_before')
            with self.assertRaisesRegex(ValueError,'one exclusive'):post.call_post160_once()

    def test_missing_aux_and_failed_source_revoke_no_native_ownership(self):
        b,a,lease,post=self.graph()
        with self.assertRaisesRegex(ValueError,'actual installed AUX90'):candidate._aux90(post)
        with patch.object(candidate,'_completed_cache'),patch.object(native,'check_live_post160',side_effect=ValueError('fixture changed')):
            with self.assertRaisesRegex(ValueError,'fixture changed'):candidate.enter(post)
        self.assertFalse(b.busy);self.assertFalse(hasattr(lease,'post160_attempt'))


if __name__=='__main__':unittest.main()

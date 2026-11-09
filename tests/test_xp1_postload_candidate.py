import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch
from civ6_host.runtime import xp1_postload_candidate as candidate,postload160_source as source
from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
from civ6_host.runtime.saved_load_job_observer import SavedLoadJobObserver
from civ6_host.runtime.native import native_official_postload as official
from civ6_host.runtime.native import native_checkpoint_postload160 as native
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend


class Post160CandidateTests(unittest.TestCase):
    def graph(self):
        b=OfficialLoadBackend.__new__(OfficialLoadBackend)
        b.stage='facades-candidate-observed';b.busy=False;b.check_thread=Mock();b.control=Mock()
        b.poisoned=b.destroyed=False;b._saved_load_candidate=True
        b.load_abi=NS(core_sha256=source.XP1_CORE_SHA256)
        b.inputs=object();b.loaded_readback={'turn':1,'width':74,'height':46}
        b.captured_bundle=NS(inputs=b.inputs,reference=candidate.REFERENCE,expected_readback=b.loaded_readback,initial_turn=1)
        b.loaded_roster=b'1|74|46|0|1|2|3|4|5'
        b.prefix=NS(quarantined=False,view_publisher=None)
        b.thread=(1,2);b.runtime=NS(thread=Mock(return_value=b.thread),read=Mock())
        b.core=NS(_handle=0x200000000);b.context=0x300000000;b.snapshot_phase='idle'
        a=official.OfficialFacadeBackend.__new__(official.OfficialFacadeBackend)
        a.owner=b;a.publication_mode='candidate';a.attempted=True
        a.publisher=NS(native_cache_gate=False,full_facade_initialization_reproduced=False)
        b.prefix.view_publisher=a.publisher
        lease=LoadedCachePublication.__new__(LoadedCachePublication)
        lease.owner=b;lease.prefix=b.prefix;lease.attempt=a;lease.publisher=a.publisher;lease.stage='raw-loaded'
        lease.entered=lease.returned=lease.copied=True;lease.poisoned=False;lease._check_state=Mock()
        a.publication_owner=lease
        with patch.object(candidate,'validate_candidate_inputs'),patch.object(native,'verify_source',return_value=source.xp1_source()):
            post=official.OfficialPost160Backend(b,a,{},postload_mode='candidate')
        post._facade_attempt=a
        return b,a,lease,post

    def test_public_gate_and_canonical_profile_defaults_remain_closed(self):
        b,a,lease,post=self.graph()
        self.assertEqual(post.expected_major_ids,tuple(range(6)))
        self.assertIs(post.post160_abi,source.profile_for_sha(source.XP1_CORE_SHA256))
        with self.assertRaisesRegex(ValueError,'XP1 outer'):
            official.OfficialPost160Backend(b,a,{})
        with self.assertRaisesRegex(ValueError,'first exact'):
            official.OfficialPost160Backend(b,a,{},postload_mode='candidate')
        self.assertIs(a.publisher.native_cache_gate,False)
        self.assertIs(a.publisher.full_facade_initialization_reproduced,False)

    def test_completed_lease_has_one_explicit_post160_transition(self):
        b,a,lease,post=self.graph()
        lease.begin_post160(post)
        self.assertEqual(b.stage,candidate.ACTIVE_STAGE);self.assertTrue(b.busy)
        self.assertIs(b._saved_load_job_cache_owner,lease)
        lease._check_state.assert_any_call('facades-candidate-observed',False)
        lease._check_state.assert_any_call(candidate.ACTIVE_STAGE,True)
        with self.assertRaisesRegex(ValueError,'reuse'):
            lease.begin_post160(post)
        lease.finish_post160(post)
        self.assertFalse(hasattr(b,'_saved_load_job_cache_owner'))
        with self.assertRaisesRegex(ValueError,'completed candidate'):
            lease._check()
        self.assertIs(a.publisher.native_cache_gate,False)

    def test_job_observer_requires_exact_post160_lease_not_stage_label(self):
        b,a,lease,post=self.graph();observer=SavedLoadJobObserver.__new__(SavedLoadJobObserver);observer.backend=b
        b.stage=candidate.ACTIVE_STAGE;b.busy=True;b.snapshot_phase='before'
        self.assertFalse(observer._exclusive())
        b.stage='facades-candidate-observed';b.busy=False;lease.begin_post160(post)
        self.assertTrue(observer._exclusive())
        b._xp1_post160_attempt=object();self.assertFalse(observer._exclusive())
        b._xp1_post160_attempt=post;b.stage='raw-loaded';self.assertFalse(observer._exclusive())

    def test_missing_aux90_refuses_without_native_binding(self):
        b,a,lease,post=self.graph()
        with self.assertRaisesRegex(ValueError,'actual installed AUX90'):
            candidate._aux90(post)

    def test_exact_roster_and_candidate_copy_scope_required(self):
        b,a,lease,post=self.graph()
        with patch.object(candidate,'validate_candidate_inputs'):
            for raw in (b'1|74|46|0|1',b'2|74|46|0|1|2|3|4|5',b'1|74|46|0|1|2|3|4|6'):
                b.loaded_roster=raw
                with self.assertRaisesRegex(ValueError,'six-major'):candidate.expected_major_ids(b)
        # A caller-crafted result equal to a genuine result is still not its receipt.
        b,a,lease,post=self.graph();a.completed_result=dict(post.facade_result)
        with patch.object(official,'validate_owner',return_value=b.inputs):
            with self.assertRaisesRegex(ValueError,'actual retained'):candidate._completed_cache(post)

    def test_shared_native_call_keeps_void_abi_and_records_raw_state(self):
        b,a,lease,post=self.graph();lease.begin_post160(post);b.snapshot_phase='before'
        fields=post.proof['contract']['state_globals']
        values={'current':2,'pending':0,'requested':1,'remaining':0xffffffff,
                'player_or_target':5,'stop_limit_or_parameter':0xffffffff}
        memory={b.core._handle+fields[k]:v.to_bytes(1 if k in ('current','pending','requested') else 4,'little') for k,v in values.items()}
        b.runtime.read=lambda address,size:memory[address][:size];b.emit=Mock()
        call=Mock(return_value=0xdeadbeef);binder=Mock(return_value=call)
        with patch.object(candidate,'_aux90'),patch.object(native,'check_live_post160'), \
             patch.object(C,'WINFUNCTYPE',return_value=binder) as signature:
            self.assertIsNone(post.call_post160_once())
            signature.assert_called_once_with(None,C.c_void_p,C.c_uint8)
            binder.assert_called_once_with(b.core._handle+0x4bd5c0);call.assert_called_once_with(b.context,1)
            self.assertEqual(post.candidate_diagnostics['before'],values)
            self.assertEqual(post.candidate_diagnostics['branch_inferred_from_native_prestate'],'pending_zero_no_transition')
            self.assertFalse(post.candidate_diagnostics['transitive_player_aux_effects_qualified'])
            with self.assertRaisesRegex(ValueError,'one exclusive'):post.call_post160_once()
            call.assert_called_once()

    def test_raw_byte_equality_and_active_branch_are_not_boolean_guesses(self):
        b,a,lease,post=self.graph();b.emit=Mock()
        state={'current':2,'pending':7,'requested':1,'remaining':0,'player_or_target':5,'stop_limit_or_parameter':0xffffffff}
        post.transition_before=state
        with patch.object(candidate,'check_active'),patch.object(candidate,'transition_state',return_value=dict(state,pending=0,current=1)):
            candidate.after_call(post)
        self.assertEqual(post.candidate_diagnostics['branch_inferred_from_native_prestate'],'requested_raw_state_differs')
        self.assertFalse(post.candidate_diagnostics['non_player_branch_state_checked'])
        state=dict(state,requested=2);post.transition_before=state
        with patch.object(candidate,'check_active'),patch.object(candidate,'transition_state',return_value=dict(state,pending=0)):
            candidate.after_call(post)
        self.assertTrue(post.candidate_diagnostics['non_player_branch_state_checked'])
        with patch.object(candidate,'check_active'),patch.object(candidate,'transition_state',return_value=state):
            with self.assertRaisesRegex(ValueError,'non-Player branch'):candidate.after_call(post)

    def test_poison_revokes_candidate_lease_without_loaded_destroy(self):
        b,a,lease,post=self.graph();lease.begin_post160(post)
        with patch('civ6_host.runtime.xp1_load_capability.finish_cache_source_scope',side_effect=ValueError('source changed')):
            with self.assertRaisesRegex(ValueError,'source changed'):post.poison()
        self.assertTrue(b.poisoned);self.assertTrue(b.prefix.quarantined)
        self.assertEqual(b.stage,'poisoned');self.assertFalse(b.busy)
        self.assertFalse(hasattr(b,'_saved_load_job_cache_owner'));self.assertFalse(b.destroyed)


class CheckpointTurnReadbackTests(unittest.TestCase):
    """Use the existing real candidate/ancestry admission with paired fixtures.

    The original stream parser/content are fixtures; candidate validation,
    checkpoint manifest joins, registration and expected_major_ids are real.
    No native or full checkpoint cycle is replayed.
    """
    def fixture(self, turn=2):
        from test_xp1_checkpoint_lineage import CheckpointLineageTests, cp
        from copy import deepcopy
        f=CheckpointLineageTests();f.setUp();self.addCleanup(f.doCleanups)
        if turn==1:
            bundle=f.original
        else:
            f.m['observed_game_turn']=f.o['turn']=f.m['decisions']['turn']=turn
            f.m['network_boundary']['session']['turn']=turn
            f.closure['initial_turn']=turn
            f.closure['network_checkpoint']=f.write_manifest()
            bundle=cp.resume_bundle(f.original,f.closure)
        owner=NS(inputs=bundle.inputs,captured_bundle=bundle,
            loaded_readback=deepcopy(bundle.expected_readback),
            loaded_roster=f'{turn}|74|46|0|1|2|3|4|5'.encode())
        return owner

    def test_original_t1_and_validated_checkpoint_t2_plus_use_exact_bundle_turn(self):
        for turn in (1,2,18,100000):
            with self.subTest(turn=turn):
                owner=self.fixture(turn)
                self.assertEqual(candidate.expected_major_ids(owner),tuple(range(6)))
                self.assertEqual(owner.captured_bundle.initial_turn,turn)
                self.assertIs(owner.inputs,owner.captured_bundle.inputs)

    def test_wrong_turn_roster_map_readback_and_input_owner_are_still_refused(self):
        owner=self.fixture(2)
        good=owner.loaded_roster
        for raw in (b'1|74|46|0|1|2|3|4|5',b'3|74|46|0|1|2|3|4|5',
                    b'2|73|46|0|1|2|3|4|5',b'2|74|45|0|1|2|3|4|5',
                    b'2|74|46|0|1|2|3|4',b'2|74|46|0|1|2|3|4|6'):
            with self.subTest(roster=raw):
                owner.loaded_roster=raw
                with self.assertRaisesRegex(ValueError,'roster/turn/map'):
                    candidate.expected_major_ids(owner)
        owner.loaded_roster=good
        owner.loaded_readback['turn']=1
        with self.assertRaisesRegex(ValueError,'captured loaded readback'):
            candidate.expected_major_ids(owner)
        owner.loaded_readback['turn']=2
        owner.inputs=object()
        with self.assertRaisesRegex(ValueError,'captured input pair'):
            candidate.expected_major_ids(owner)

    def test_declared_turn_requires_exact_bounded_integer_before_roster_comparison(self):
        owner=self.fixture(2);bundle=owner.captured_bundle
        for value in (True,False,2.0,'2',0,100001):
            with self.subTest(value=value):
                object.__setattr__(bundle,'initial_turn',value)
                try:
                    with self.assertRaisesRegex(ValueError,'captured input pair'):
                        candidate.expected_major_ids(owner)
                finally:
                    object.__setattr__(bundle,'initial_turn',2)
        self.assertEqual(candidate.expected_major_ids(owner),tuple(range(6)))

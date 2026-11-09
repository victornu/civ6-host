"""Owned v38 composition; native query and process creation are fixture seams."""
from copy import deepcopy
from pathlib import Path
import sys
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

INSTALLED_HOST = Path(__file__).resolve().parents[1]
STAGED = Path(__file__).resolve().parents[2].name in ('integration', 'private-targets')
if STAGED:
    INTEGRATION = Path(__file__).resolve().parents[2]
    REVIEW = INTEGRATION.parent
    HOST = REVIEW.parents[2].parent / 'civ6-host'
else:
    HOST = INSTALLED_HOST
    REVIEW = Path(os.environ['CIV6_HOST_RESOURCE_ROOT']) / 'work/trade-common-client/congress-review-staging'
    INTEGRATION = REVIEW / 'integration'
sys.path.insert(0, str(HOST / 'src'))
sys.path.insert(0, str(HOST / 'tests'))
sys.path.append(str(REVIEW / 'ack-runtime/files/tests'))
import civ6_host.runtime, civ6_host.runtime.native, civ6_host.runtime.workers, civ6_host.contracts
if STAGED:
    civ6_host.runtime.__path__.insert(0, str(REVIEW / 'ack-runtime/files/src/civ6_host/runtime'))
    civ6_host.runtime.__path__.insert(0, str(REVIEW / 'default-state/targets/files/src/civ6_host/runtime'))
    civ6_host.runtime.__path__.insert(0, str(INTEGRATION / 'files/src/civ6_host/runtime'))
    civ6_host.runtime.native.__path__.insert(0, str(INTEGRATION / 'files/src/civ6_host/runtime/native'))
    civ6_host.runtime.workers.__path__.insert(0, str(INTEGRATION / 'files/src/civ6_host/runtime/workers'))
    civ6_host.contracts.__path__.insert(0, str(REVIEW / 'api/files/src/civ6_host/contracts'))
from civ6_host.runtime import xp2_world_congress_review as review
from civ6_host.runtime import xp2_world_congress as congress
from civ6_host.runtime import xp2_congress_cycle as cycle
from civ6_host.runtime.native import native_world_congress_review as reader
from civ6_host.contracts import world_congress_review as contract
import test_xp2_congress_cycle as cycle_tests
from test_world_congress_contract import catalogue


class ReviewIntegrationTests(unittest.TestCase):
    def graph(self):
        g = cycle_tests.CycleTests().graph()
        g.saved.world_congress_diagnostic = True
        g.saved.world_congress_review_diagnostic = True
        g.backend._xp2_world_congress_review_requested = True
        public = catalogue('ordinary')
        private = dict(popup=dict(capability=True, current_era=4, initial_era=3, has_emergency_proposals=True))
        c = g.continuation
        record = congress._Catalogue(g.saved,g.backend,c,g.prefix,c.identity,c.sequence,
            deepcopy(c.observation),deepcopy(public),private)
        c._xp2_world_congress_catalogue = record
        c.explicit_world_congress = deepcopy(public)
        g.public, g.record = public, record
        return g

    def result(self, g):
        return dict(schema=contract.SCHEMA,player_id=0,turn=61,sequence=3,
            turn_segment=g.public['turn_segment'],history_kind='last_results',resolutions=[],discussions=[])

    def envelope(self, public):
        return dict(public=public, private={**{k:public[k] for k in ('player_id','turn','sequence','turn_segment')},'resolutions':[]})

    def call(self, g, *, public=True):
        with cycle_tests.CycleTests().quiescent_control(g) as control:
            value=review.catalogue(g.saved,g.continuation.observation,sequence=3,
                congress=g.public if public else None)
        g.control_reads=control.call_count
        return value

    def test_real_owner_record_and_queue_checks_surround_native_projection(self):
        g=self.graph(); result=self.result(g)
        with cycle_tests.CycleTests().mode(g,active=False):
            cycle.observe_catalogue(g.saved,g.public)
            with patch.object(reader,'query',return_value=self.envelope(result)) as query:
                value=self.call(g)
        self.assertEqual(value,dict(world_congress_review=result,world_congress_review_status='available'))
        self.assertGreaterEqual(g.control_reads,2)
        self.assertIs(query.call_args.kwargs['backend'],g.backend)
        self.assertEqual(query.call_args.kwargs['admission'],dict(public=g.record.public,private=g.record.private))
        value['world_congress_review']['resolutions'].append('mutation')
        self.assertEqual(result['resolutions'],[])

    def test_waiting_and_closed_ui_do_not_read_native_or_create_cycle_permit(self):
        g=self.graph()
        with cycle_tests.CycleTests().mode(g,active=False), patch.object(reader,'query') as query:
            value=self.call(g,public=False)
            self.assertEqual(value['world_congress_review_status'],'waiting_or_closed')
            query.assert_not_called()
        g=self.graph();g.public['paused']=g.record.public['paused']=True
        g.public['offers']['confirm_proposals']=g.record.public['offers']['confirm_proposals']=False
        g.continuation.explicit_world_congress=deepcopy(g.public)
        with cycle_tests.CycleTests().mode(g,active=False), patch.object(cycle,'prepare_review_readback') as prepare:
            # The real query returns None before attaching/reading its environment.
            value=self.call(g)
            self.assertEqual(value['world_congress_review_status'],'review_ui_unavailable')
            prepare.assert_not_called()

    def test_stale_record_foreign_revision_and_pending_work_refuse_before_query(self):
        for change in (lambda g:setattr(g.continuation,'sequence',1),
                       lambda g:g.continuation.explicit_world_congress.update(favor=0),
                       lambda g:g.prefix.actions.pending.append(b'pending')):
            g=self.graph();change(g)
            with cycle_tests.CycleTests().mode(g,active=False),patch.object(reader,'query') as query:
                with self.assertRaises((ValueError,RuntimeError)):self.call(g)
                query.assert_not_called()

    def test_native_readback_crossing_owner_or_segment_is_rejected_before_cycle_observation(self):
        for change in ('revision','segment'):
            g=self.graph();result=self.result(g)
            def native(*args,**kwargs):
                if change=='revision':g.continuation.sequence+=1
                else:result['turn_segment']+=1
                return self.envelope(result)
            with cycle_tests.CycleTests().mode(g,active=False):
                cycle.observe_catalogue(g.saved,g.public)
                with patch.object(reader,'query',side_effect=native),patch.object(cycle,'observe_review') as observe:
                    with self.assertRaises(ValueError):self.call(g)
                    observe.assert_not_called()

    def test_optional_private_permit_is_used_only_after_valid_public_readback(self):
        g=self.graph();result=self.result(g);permit=object();order=[]
        def prepare(saved):order.append('prepare');return permit
        def native(*a,**kw):order.append('native');return self.envelope(result)
        def observe(saved,value,*,permit,administrative):
            self.assertEqual(administrative,self.envelope(result)['private'])
            order.append('observe');congress._check(saved,g.record,active=False)
            self.assertEqual(value,result)
        with cycle_tests.CycleTests().mode(g,active=False),patch.object(cycle,'prepare_review_readback',side_effect=prepare), \
                patch.object(reader,'query',side_effect=native),patch.object(cycle,'observe_review',side_effect=observe) as observed:
            self.call(g)
            self.assertIs(observed.call_args.kwargs['permit'],permit)
        self.assertEqual(order,['prepare','native','observe'])

    def test_exact_boolean_and_prepared_flags_have_no_legacy_implicit_enable(self):
        for field,value in (('world_congress_review_diagnostic',1),('world_congress_review_diagnostic',False),
                            ('world_congress_diagnostic',False)):
            g=self.graph();setattr(g.saved,field,value)
            with cycle_tests.CycleTests().mode(g,active=False),patch.object(reader,'query') as query:
                with self.assertRaises(ValueError):self.call(g)
                query.assert_not_called()
        g=cycle_tests.CycleTests().graph(enabled=False)
        self.assertFalse(cycle.enabled(g.backend))
        self.assertFalse(getattr(g.backend,'_xp2_world_congress_review_requested',False))

    def test_late_control_read_owner_change_is_rejected_after_cycle_observation(self):
        g=self.graph();result=self.result(g);calls=[]
        def control(**kwargs):
            calls.append(kwargs)
            if len(calls)==3:g.continuation.sequence+=1
            return dict(pending_count=0)
        with cycle_tests.CycleTests().mode(g,active=False),patch.object(g.backend,'control',side_effect=control), \
                patch.object(cycle,'prepare_review_readback',return_value=object()), \
                patch.object(reader,'query',return_value=self.envelope(result)),patch.object(cycle,'observe_review'):
            with self.assertRaises(ValueError):
                review.catalogue(g.saved,g.continuation.observation,sequence=3,congress=g.public)
        self.assertEqual(len(calls),3)

    def test_source_closure_includes_projection_environment_and_cycle_proof(self):
        from civ6_host.runtime.execution_images import known_path,select
        profile='xp2-gamecore-current-092abfbb';image=select(profile,core_path=known_path(profile))
        pins=review.source_dependencies(execution_image=image)
        self.assertIn(reader.SOURCE[1],pins.values())
        self.assertIn(reader.PRIVATE_SOURCE[1],pins.values())
        self.assertIn(cycle.SOURCE[1],pins.values())
        self.assertTrue(any('congress-review-staging/environment/review_environment.py' in p.replace('\\','/') for p in pins))

    def test_parent_and_worker_reject_non_boolean_or_missing_parent_group(self):
        from civ6_host.runtime.native.network_session import NativeNetworkSession
        from civ6_host.runtime.workers import network_worker
        bundle=dict(path='fixture',sha256='0'*64)
        for flag in (None,1,'true',True):
            with self.assertRaisesRegex(ValueError,'Congress review'):
                NativeNetworkSession(official_bundle=bundle,world_congress_review_diagnostic=flag)
            with self.assertRaisesRegex(ValueError,'Congress review'):
                network_worker._open_xp1(dict(input_profile='xp2-lan',raw_only_candidate=True,world_congress_review_diagnostic=flag),
                    'not-read.json',None,None)

    def test_configure_requested_uses_boolean_preload_flag(self):
        from civ6_host.runtime import captured_saved_load
        selected=NS(family='xp2-lan',core_sha256=captured_saved_load.XP2_CORE_SHA256)
        for flag in (False,True):
            backend=NS(captured_bundle=NS(inputs=NS(configuration=b'fixture')),inputs=None,
                load_abi=NS(core_sha256=captured_saved_load.XP2_CORE_SHA256))
            closure=dict(input_profile='xp2-lan',raw_only_candidate=True,post160_candidate=True,
                publish_cache_candidate=True,observe_player_candidate=True,close_loaded_candidate=True,
                world_congress_diagnostic=True,world_congress_review_diagnostic=flag)
            # Input capture/profile admission is independently source-tested;
            # this fixture supplies only its already-validated result.
            with patch.object(captured_saved_load,'select_load_closure',return_value=selected), \
                    patch.object(captured_saved_load,'validate_candidate_inputs'), \
                    patch('civ6_host.runtime.captured_session_profile.for_backend',return_value=NS(human_ids=(0,))), \
                    patch('civ6_host.runtime.session_configuration.read_saved_roster',return_value={'taken_slot_ids':[0]}):
                captured_saved_load.configure_requested(backend,closure)
            self.assertIs(backend._xp2_world_congress_review_requested,flag)
        with self.assertRaisesRegex(ValueError,'Congress review'):
            captured_saved_load.configure_requested(NS(),dict(world_congress_review_diagnostic=1))


if __name__=='__main__':unittest.main()

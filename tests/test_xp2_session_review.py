"""Retained XP1/XP2 receipt replay and explicit XP2 session fixtures; no native calls."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import qualify_xp1_configuration as q
import review_xp1_session as review
import test_xp1_session_turn_review as turn_fixtures
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.captured_session_profile import for_family
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime import xp2_action_transport_source as unit_source
from civ6_host.runtime import xp1_action_job_ledger as job_ledger
from civ6_host.runtime.stdout_transport_profiles import selected_profile

HOST=Path(__file__).resolve().parents[1]
XP2_RUN=resource_root()/'work/native-xp2-saved-load/run-20261102T123739Z-2187ab257657'
XP1_REVIEW=HOST/'work/xp1-turn-integration/native-session06/native-review.json'


def read(path):return json.loads(path.read_bytes())


class ExpansionSessionReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view=read(XP2_RUN/'player-view-result.json')
        cls.loaded=cls.view['jobs_after']
        cls.selected=q.saved_load_review_profile(XP2_CORE_SHA256)
        candidate=for_family('xp2-lan').candidate
        references=(candidate.reference,cls.selected['job']['source'],
                    cls.selected['unit_source'],cls.selected['turn_ui_source'])
        pins={str((resource_root()/name).resolve()):sha for name,sha in references}
        pins[cls.loaded['core_identity']['path']]=XP2_CORE_SHA256
        pins[cls.loaded['source_build']['executable_path']]=cls.loaded['host_sha256']
        cls.closure=dict(schema='civ6-host.session.closure.v1',input_profile='xp2-lan',pins=pins,
            official_bundle=dict(path=candidate.reference[0],sha256=candidate.reference[1]),
            close_loaded_candidate=True,lifetime_seconds=420,
            stdout_transport=selected_profile(XP2_CORE_SHA256,cls.loaded['host_sha256']))
        cls.report=dict(reaped=True,job_assigned=True,exit_code=90,error=None,timed_out=False,
            normal_destroy_called=True,timeout_seconds=420,memory_limit_bytes=512*1024**2,
            stdout_limit_bytes=64*1024**2,source_unchanged={p:True for p in pins})

    def turn(self,*,update=False):
        # Only payload rows are constructed here. Real parsers, source selection,
        # snapshot/job reconciliation and echo decoder remain active.
        fixture=turn_fixtures.TurnReceipts();fixture.setUp()
        result=copy.deepcopy(fixture.result);interval=copy.deepcopy(fixture.interval)
        observation=copy.deepcopy(self.view['observation'])
        result.update(observation_before=observation,observation_after=copy.deepcopy(observation),
            jobs_before=copy.deepcopy(self.loaded),jobs_after=copy.deepcopy(self.loaded),
            unit_source=dict(source_sha256=unit_source.SOURCE[1],core_sha256=XP2_CORE_SHA256,
                             callbacks=dict(unit_source.CALLBACKS)))
        previous=dict(fixture.previous,observation=copy.deepcopy(observation))
        gate=interval['commands'][0];gate.update(core_sha256=XP2_CORE_SHA256,
            source_sha256=self.selected['turn_ui_source'][1])
        if update:
            result.update(action=None,effect=None,game_update_called=True)
            result['observation_after']['turn']+=1
            interval['commands']=[dict(stage='before_native_game_update',outer_slot='0x90',game_slot='0x30'),
                dict(stage='native_game_update_returned',eligible_for_training=False)]
        return result,interval,previous

    def test_exact_closure_engine_source_hash_and_build_joins(self):
        selected=review.review_session_identity(self.closure)
        review.review_session_job_identity(self.closure,self.loaded,selected)
        self.assertEqual(selected['job']['execute_rva'],0x536B00)
        for change in (
                lambda c:c.update(input_profile='xp1-lan'),
                lambda c:c['official_bundle'].update(sha256='0'*64),
                lambda c:c['pins'].pop(str((resource_root()/self.selected['unit_source'][0]).resolve())),
                lambda c:c['stdout_transport'].update(core_sha256=XP1_CORE_SHA256)):
            altered=copy.deepcopy(self.closure);change(altered)
            with self.assertRaises(ValueError):review.review_session_identity(altered)
        altered=copy.deepcopy(self.closure)
        altered['pins'][self.loaded['source_build']['executable_path']]='0'*64
        with self.assertRaisesRegex(ValueError,'executed closure'):
            review.review_session_job_identity(altered,self.loaded,selected)

    def test_core_and_job_abi_mutations_are_refused(self):
        for key,value in (('sha256',XP1_CORE_SHA256),('profile',2),('execute_rva',0x465110),
                          ('vtable_rva',0x8A4870),('source_sha256','0'*64),('completed_offset',0xF1)):
            snapshot=copy.deepcopy(self.loaded);snapshot['core_identity'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'foreign Core'):
                q.saved_load_validate_engine(snapshot,XP2_CORE_SHA256)
        snapshot=copy.deepcopy(self.loaded);snapshot.pop('core_identity')
        with self.assertRaises(ValueError):
            q.saved_load_validate_engine(snapshot,XP2_CORE_SHA256,allow_legacy_transition=True)

    def test_client_and_probe_supervision_remain_separate(self):
        q.saved_load_validate_supervision(self.report,self.closure['pins'],lifetime_seconds=420,session=True)
        probe=dict(status='passed',exit_code=0,process_reaped=True,job_contained=True,
            wall_limit_seconds=180,memory_limit_bytes=768*1024**2,game_executable_launched=False,
            error=None,source_unchanged=self.report['source_unchanged'])
        q.saved_load_validate_supervision(probe,self.closure['pins'],lifetime_seconds=180,xp2_raw=True)
        for report,options in ((probe,dict(lifetime_seconds=420,session=True)),
                               (self.report,dict(lifetime_seconds=180,xp2_raw=True)),
                               (self.report,dict(lifetime_seconds=420,session=True,xp2_raw=True)),
                               (dict(self.report,exit_code=89),dict(lifetime_seconds=420,session=True))):
            with self.assertRaises(ValueError):q.saved_load_validate_supervision(report,self.closure['pins'],**options)

    def test_shared_transition_turn_echo_and_poll_use_selected_sources(self):
        for update in (False,True):
            result,interval,previous=self.turn(update=update)
            continuity=q.saved_load_validate_transition(result,interval,previous,update=update,core_sha256=XP2_CORE_SHA256)
            with patch.object(job_ledger,'reconcile_action_jobs',wraps=job_ledger.reconcile_action_jobs) as reconcile:
                actual=q.saved_load_validate_turn(result,interval,self.loaded,update=update,core_sha256=XP2_CORE_SHA256)
            self.assertEqual(reconcile.call_args.kwargs['victory_execute_rva'],0x536B00)
            self.assertTrue(actual['jobs']['ledger_events_match_snapshot'])
            self.assertEqual(continuity['sequence'],result['sequence'])
        result,interval,previous=self.turn()
        interval['commands'][0]['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'UI gate'):
            q.saved_load_validate_turn(result,interval,self.loaded,update=False,core_sha256=XP2_CORE_SHA256)
        result['unit_source']['core_sha256']=XP1_CORE_SHA256
        with self.assertRaisesRegex(ValueError,'foreign Core'):
            q.saved_load_validate_transition(result,interval,previous,update=False,core_sha256=XP2_CORE_SHA256)

    def test_xp2_command_and_update_reconcile_on_session_supervision(self):
        for update in (False,True):
            result,interval,previous=self.turn(update=update)
            phase='turn_update' if update else 'unit_commands'
            interval.update(stdout_sha256='a'*64,interval_sha256='b'*64,interval_bytes=1,stdout_lines=30)
            interval['begin']['line']=20;interval['returned']['line']=30
            events={phase+'_job_interval':interval}
            prior=dict(ledger_provenance_authenticated=True,stdout_sha256='a'*64,last_line=10,final_jobs=self.loaded)
            actual=q.saved_load_reconcile_later(self.report,self.closure['pins'],{},result,events,prior,
                phase=phase,lifetime_seconds=420,previous_transition=previous,
                core_sha256=XP2_CORE_SHA256,session_supervision=True)
            self.assertTrue(actual['schema'].startswith('civ6-host.xp2-'))
            self.assertEqual(actual['final_jobs'],self.loaded)
            with self.assertRaisesRegex(ValueError,'Unqualified XP2 continuation'):
                q.saved_load_reconcile_later(self.report,self.closure['pins'],{},result,events,prior,
                    phase=phase,lifetime_seconds=420,previous_transition=previous,core_sha256=XP2_CORE_SHA256)

    def test_found_research_civic_production_select_xp2_job_and_unit_contracts(self):
        retained=read(XP1_REVIEW);run=Path(retained['runs'][0]['run'])
        for command in retained['runs'][0]['ledger']['commands'][:4]:
            result=read(Path(command['receipt']['path']))
            interval=q.saved_load_events(run/'events.jsonl',allow_turn_updates=True,
                require_interval='unit_commands',command_sequence=command['protocol_sequence'])[1]['unit_commands_job_interval']
            # Reuse actual payload/observation examples, with an explicitly
            # constructed XP2 owner and zero-job interval. This tests selection,
            # not the claim that these XP1 actions were executed by XP2.
            result.update(jobs_before=copy.deepcopy(self.loaded),jobs_after=copy.deepcopy(self.loaded),
                unit_source=dict(source_sha256=unit_source.SOURCE[1],core_sha256=XP2_CORE_SHA256,
                                 callbacks=dict(unit_source.CALLBACKS)))
            interval['jobs']=[]
            validate=q.saved_load_validate_unit_commands if result['action']['kind']=='found_city' else q.saved_load_validate_choices
            with patch.object(job_ledger,'reconcile_action_jobs',wraps=job_ledger.reconcile_action_jobs) as reconcile:
                receipt=validate(result,interval,self.loaded,transition={},core_sha256=XP2_CORE_SHA256)
            self.assertTrue(receipt['jobs']['ledger_events_match_snapshot'])
            self.assertEqual(reconcile.call_args.kwargs['victory_execute_rva'],0x536B00)

    def test_retained_xp2_prefix_receipts_use_session_mode_without_relabeling_originals(self):
        raw_original=read(XP2_RUN/'raw-load-result.json')
        raw=dict(raw_load_receipt=raw_original['receipt'],readback=raw_original['readback'])
        events=q.saved_load_events(XP2_RUN/'stdout.jsonl',require_load_interval=True)[1]
        load=q.saved_load_reconcile_jobs(self.report,self.closure['pins'],raw,events['load_job_interval'],
            lifetime_seconds=420,core_sha256=XP2_CORE_SHA256,session_supervision=True)
        events=q.saved_load_events(XP2_RUN/'stdout.jsonl',require_post160_interval=True)[1]
        post=read(XP2_RUN/'post160-result.json')
        prior=q.saved_load_reconcile_post160(self.report,self.closure['pins'],raw,post,events,load,
            lifetime_seconds=420,core_sha256=XP2_CORE_SHA256,session_supervision=True)
        for phase,filename in (('publication','publication-result.json'),('player_view','player-view-result.json')):
            events=q.saved_load_events(XP2_RUN/'stdout.jsonl',require_interval=phase)[1]
            prior=q.saved_load_reconcile_later(self.report,self.closure['pins'],raw,read(XP2_RUN/filename),events,prior,
                phase=phase,lifetime_seconds=420,core_sha256=XP2_CORE_SHA256,session_supervision=True)
        self.assertTrue(prior['phase_receipt']['native_ui_observation_returned'])
        self.assertEqual(raw_original,read(XP2_RUN/'raw-load-result.json'))

    def test_xp2_continuation_close_adds_strict_owner_receipt_checks(self):
        closed=read(XP2_RUN/'loaded-lifetime-result.json')
        # The retained native run is publication/UI only. These extra fields are
        # a fixture of the new continuation receipt, never a retrospective claim.
        closed.update(continuation_closed=True,command_transport_closed=True,
            command_source_sha256=unit_source.SOURCE[1],continuation_source_pin_count=188,
            postload_candidate_only=False)
        events=q.saved_load_events(XP2_RUN/'stdout.jsonl',require_interval='lifetime')[1]
        events['xp2_loaded_lifetime_closed']=dict(closed,stage='xp2_loaded_lifetime_closed')
        receipt=q.saved_load_validate_lifetime(closed,events['lifetime_job_interval'],self.loaded,events,
            xp2_loaded=True,continuation=True)
        self.assertTrue(receipt['native_destroy_authenticated'])
        for key,value in (('continuation_closed',False),('command_transport_closed',False),
                          ('command_source_sha256','0'*64),('postload_candidate_only',True)):
            altered=dict(closed,**{key:value})
            with self.assertRaisesRegex(ValueError,'command owner cleanup'):
                q.saved_load_validate_lifetime(altered,events['lifetime_job_interval'],self.loaded,events,
                    xp2_loaded=True,continuation=True)

    def test_retained_xp1_full_turn_cycle_and_reset_still_authenticate(self):
        retained=read(XP1_REVIEW)
        actual=review.review(retained['acceptance']['path'],retained['executed_sources_archive']['path'])
        self.assertEqual(actual['status'],retained['status'])
        self.assertEqual({k:actual['qualified_turn_interval'][k] for k in retained['qualified_turn_interval']},
                         retained['qualified_turn_interval'])
        self.assertEqual(actual['qualified_turn_interval']['submitted_without_confirmed_effect'],0)
        self.assertEqual(actual['core_sha256'],XP1_CORE_SHA256)
        self.assertEqual(len(actual['runs']),2)

    def test_actual_failed_xp2_found_attempt_cannot_become_a_completed_cycle(self):
        run=resource_root()/'work/xp2-client-sessions/run-36e8a973e861497a9ad667b49dafe318'
        self.assertEqual(read(run/'supervisor.json')['exit_code'],78)
        with self.assertRaisesRegex(ValueError,'Acceptance group did not complete'):
            review.review(run/'client-acceptance.json',run/'unused-archive.zip')


if __name__=='__main__':unittest.main()

"""Stopped-process XP2 raw Load/close review with real shared ledger validators."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qualify_xp1_configuration as q
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime import saved_load_job_observer as jobs
from civ6_host.runtime.job_registry_snapshot import validate_empty_transition_data
from civ6_host.runtime.xp1_loaded_lifetime import validate_jobs_shutdown
from civ6_host.runtime.xp2_loaded_lifetime_source import SOURCE as LIFETIME_SOURCE


class XP2SavedLoadSupervision(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.run=Path(self.temp.name)
        self.source=self.run/'fixture-source.py';self.source.write_bytes(b'fixture source\n')
        self.pins={str(self.source):q.digest(self.source.read_bytes())}
        self.sources=dict(runtime=self.pins,dependencies=self.pins,saved_load=True,
            qualifier=q.digest(Path(q.__file__).read_bytes()),
            native_host=dict(path=str(self.source),sha256=self.pins[str(self.source)]),
            native_build=dict(path=str(self.source),sha256=self.pins[str(self.source)]))
        self.write('executed-source-pins.json',self.sources)
        (self.run/'executed-sources.zip').write_bytes(b'fixture archive')
        self.report=dict(status='passed',exit_code=0,process_reaped=True,job_contained=True,
            wall_limit_seconds=120,memory_limit_bytes=768*1024**2,game_executable_launched=False,
            source_archive_sha256=q.digest((self.run/'executed-sources.zip').read_bytes()))
        host_sha=self.pins[str(self.source)]
        core=dict(profile=3,sha256=XP2_CORE_SHA256,source_sha256=jobs.XP2_SOURCE[1],
                  host_component_sha=jobs.XP2_HOST_COMPONENT_SHA)
        self.before=dict(schema=jobs.SCHEMA,profile=jobs.PROFILE,source_proof_sha256=jobs.XP2_SOURCE[1],
            stable_read=True,memory_modified=False,concurrent_scheduler_supported=False,
            native_introspection_only=True,native_methods_called=True,spawn_active=0,
            registry_lock_raw=0,pending_items=0,submission_sequence=0,groups=[],
            slots=[dict(handle=i,occupied=False,count=0,items=[]) for i in range(1,65)],
            core_identity=core,source_build={'host_sha256':host_sha},host_sha256=host_sha,
            current_executable=dict(executable_path=str(self.source),host_base=0x10000,os_thread_id=7),
            owner_thread_id=7)
        self.after=copy.deepcopy(self.before);self.after['slots'][0]['occupied']=True
        candidate=dict(validate_empty_transition_data(self.before,self.after),
            schema='civ6_host.saved_load_empty_jobs_transition.v1',source_proof_sha256=jobs.XP2_SOURCE[1],
            source_build=self.after['source_build'],core_identity=core,
            source_host_component_sha256=jobs.XP2_HOST_COMPONENT_SHA)
        self.receipt=dict(status=0,bytes_consumed=12,game_initialized=1,jobs_identical=False,
            jobs_structural_candidate=candidate,scheduler_ledger_reconciliation_pending=True)
        self.readback=dict(turn=1,width=44,height=26,player_id=0,gold=0,city_count=0,units=[])
        self.raw=dict(receipt=self.receipt,readback=self.readback,roster='1|44|26|0|1',
                      postload_completed=False,public_session_admitted=False,strategic_training_ready=False)
        self.group=dict(status='native_xp2_captured_raw_load_readback_and_close_passed',
            readback=self.readback,roster=self.raw['roster'],core_sha256=XP2_CORE_SHA256,
            game_load_called=True,saved_game_loaded=True,context_destroyed=True,
            postload_completed=False,public_session_admitted=False,strategic_training_ready=False)
        transition=validate_jobs_shutdown(self.after,self.before)
        self.closed=dict(native_unload_called=True,native_destroy_called=True,context_destroyed=True,
            cache_wrappers_released=False,services_closed=True,configuration_closed=True,lua_closed=True,
            core_lock_closed=True,database_shutdown=True,unknown_host_callbacks_refused=True,
            public_loaded_lifetime_admitted=False,cleanup_inferred_from_process_exit=False,
            source_sha256=LIFETIME_SOURCE[1],jobs_before=self.after,jobs_unloaded=self.before,
            jobs_transition=transition,jobs_identical=False,
            performance_closed=dict(native_destructor_returned=True,guards_intact=True,outer_storage_freed_by_native=False),
            steps=['loaded_notifications_consumed','native_unload','native_destroy','shared_services_closed',
                'native_performance_map_destroyed','native_configuration_destroyed','native_lua_closed',
                'native_core_lock_closed','database_shutdown'],raw_load_only=True,post160_called=False,
            cache_wrappers_present=False,loaded_notifications_consumed=2,unloaded_notifications_consumed=1)
        self.rows=[dict(stage='before_official_gamecore_load',game_bytes=12),
            dict(stage='job_list_created',export='EXP_JobManager_CreateJobList',handle=1),
            dict(stage='official_gamecore_load_returned',status=0,bytes_consumed=12,validation_completed=False,
                 jobs_before=self.before,jobs_after=self.after),
            dict(stage='official_gamecore_load_observed',result=self.receipt,
                readback=dict(observed=self.readback,comparison=dict(matched=True,compared=self.readback),
                    major_player_ids=[0,1],human_player_ids=[0],human_status_native_verified=True,
                    privileged_diagnostic=True,learner_observation=False)),
            dict(stage='before_xp2_raw_loaded_close',game_load_called=True),
            dict(stage='xp2_loaded_notifications_consumed',count=2,game_alive=True,
                 post160_called=False,cache_wrappers_present=False),
            dict(stage='before_xp2_loaded_wrapper_release',source_sha256=LIFETIME_SOURCE[1],jobs_before=self.after),
            dict(stage='before_xp2_loaded_unload',source_sha256=LIFETIME_SOURCE[1]),
            dict(stage='job_list_freed',export='EXP_JobManager_FreeJobList',handle=1,canonical_handle=1,queued_jobs=0),
            dict(stage='xp2_loaded_unload_returned',source_sha256=LIFETIME_SOURCE[1],void_return_ignored=True,
                 game_object_null=True,cache_service_null=True,rules_manager_null=True,
                 jobs_unloaded=self.before,jobs_transition=transition),
            dict(stage='xp2_unloaded_notifications_consumed',count=1,cache_feedback_executed=False),
            dict(stage='before_xp2_loaded_destroy',source_sha256=LIFETIME_SOURCE[1]),
            dict(stage='xp2_loaded_destroy_returned',source_sha256=LIFETIME_SOURCE[1],void_return_ignored=True,
                 context_storage_read_after_destroy=False,native_globals_detached=True),
            dict(stage='xp2_loaded_lifetime_closed',**self.closed),
            dict(stage='xp2_saved_load_group_completed',status=self.group['status'])]
        self.persist()

    def write(self,name,value):
        path=self.run/name;path.write_text(json.dumps(value),encoding='utf-8')
        return dict(path=str(path),sha256=q.digest(path.read_bytes()))

    def persist(self):
        self.write('raw-load-result.json',self.raw)
        self.write('loaded-lifetime-result.json',self.closed)
        self.report['completion_receipt']=self.write('xp2-saved-load-group.json',self.group)
        (self.run/'stdout.jsonl').write_bytes(b''.join(json.dumps(row).encode()+b'\n' for row in self.rows))

    def evaluate(self):
        with patch.object(q,'xp2_saved_load_source_dependencies',return_value=self.pins):
            return q.evaluate_xp2_saved_load(self.run,self.sources,self.report)

    def test_complete_raw_load_and_close_reuse_real_reconciliations(self):
        original=copy.deepcopy(self.raw)
        result=self.evaluate()
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['phases'],dict(load='authenticated',lifetime='authenticated'))
        self.assertTrue(result['reconciliations']['load']['reconciliation']['ledger_reconciled'])
        self.assertEqual(result['reconciliations']['lifetime']['removed_empty_handles'],[1])
        self.assertFalse(result['public_session_admitted']);self.assertFalse(result['postload_completed'])
        self.assertEqual(self.raw,original)

    def test_changed_source_is_diagnosed_after_worker_stop(self):
        self.source.write_bytes(b'changed')
        result=self.evaluate()
        self.assertFalse(result['passed']);self.assertFalse(result['source_unchanged'][str(self.source)])

    def test_failed_or_uncontained_worker_never_promoted(self):
        for update in (dict(status='failed',exit_code=1),dict(process_reaped=False),dict(job_contained=False),
                       dict(wall_limit_seconds=121),dict(memory_limit_bytes=512*1024**2)):
            original=dict(self.report);self.report.update(update)
            with self.subTest(update=update):self.assertFalse(self.evaluate()['passed'])
            self.report=original

    def test_missing_lifetime_receipt_is_absent(self):
        (self.run/'loaded-lifetime-result.json').unlink()
        result=self.evaluate();self.assertFalse(result['passed']);self.assertEqual(result['phases']['lifetime'],'absent')

    def test_load_snapshot_and_ledger_must_agree(self):
        self.rows=[row for row in self.rows if row['stage']!='job_list_created'];self.persist()
        result=self.evaluate();self.assertFalse(result['passed']);self.assertIn('ledger does not match',result['errors'][0])

    def test_unload_release_ledger_must_agree(self):
        self.rows=[row for row in self.rows if row['stage']!='job_list_freed'];self.persist()
        result=self.evaluate();self.assertFalse(result['passed']);self.assertEqual(result['phases']['load'],'authenticated')
        self.assertIn('release ledger',result['errors'][0])

    def test_refused_callback_and_non_json_stdout_fail_closed(self):
        original=copy.deepcopy(self.rows)
        self.rows.insert(4,dict(stage='unsupported_host_contract'));self.persist()
        self.assertFalse(self.evaluate()['passed'])
        self.rows=original;self.persist()
        with (self.run/'stdout.jsonl').open('ab') as out:out.write(b'unqualified native text\n')
        self.assertFalse(self.evaluate()['passed'])

    def test_changed_readback_or_return_order_refused(self):
        self.group['readback']=dict(self.readback,gold=999);self.persist()
        self.assertFalse(self.evaluate()['passed'])
        self.group['readback']=self.readback
        self.rows[-2],self.rows[-1]=self.rows[-1],self.rows[-2];self.persist()
        self.assertFalse(self.evaluate()['passed'])

    def test_real_dependency_graph_includes_selected_profiles(self):
        pins=q.xp2_saved_load_source_dependencies()
        for suffix in ('xp2-preload-services/source-profile-v1.json','xp2-prepare-services/source-profile-v1.json',
                       'xp2-job-static/xp2-job-source-profile-v2.json','xp2-load-options-capabilities/source-profile-v1.json',
                       'xp2-script-services/xp2-borrowed-services-connection-type.json',
                       'xp2-script-api/source-profile-v1.json'):
            self.assertTrue(any(name.replace('\\','/').endswith(suffix) for name in pins),suffix)
        self.assertTrue(any(sha==LIFETIME_SOURCE[1] for sha in pins.values()))


if __name__=='__main__':unittest.main()

"""Pure transcript tests; AST-extract existing pure ledger functions, no DLL imports."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
QUALIFIER_SOURCE=REPO/'tools/qualify_xp1_configuration.py'
LIFETIME_SOURCE_PATH=REPO/'src/civ6_host/runtime/xp1_loaded_lifetime.py'


def pure_functions():
    ns=dict(Path=Path,json=json,hashlib=hashlib,jobs=SimpleNamespace(UINT64_MAX=(1<<64)-1))
    jobs=ast.parse((REPO/'src/civ6_host/runtime/native/native_checkpoint_postload_jobs.py').read_text(encoding='utf-8'))
    names={'NOOP_WAIT','NOOP_NULL_FREE','CREATE_LIST','EVENT_KEYS'}
    nodes=[n for n in jobs.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))
           or (isinstance(n,ast.FunctionDef) and n.name in ('_exact_int','_ledger_event'))]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<existing pure event contract>','exec'),ns)
    observer=ast.parse((REPO/'src/civ6_host/runtime/saved_load_job_observer.py').read_text(encoding='utf-8'))
    nodes=[n for n in observer.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('SOURCE','XP2_SOURCE','BASE_SCHEDULER_SOURCE','SOURCE_HASH_BY_PROFILE','SCHEMA','PROFILE') for t in n.targets))
           or (isinstance(n,ast.FunctionDef) and n.name in ('reconcile_ledger','require_quiescent'))]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<existing pure reconciliation>','exec'),ns)
    from civ6_host.runtime.stdout_transport_profiles import iter_records
    ns['iter_records']=iter_records
    lifetime=ast.parse(LIFETIME_SOURCE_PATH.read_text(encoding='utf-8'))
    definition=next(n for n in lifetime.body if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='SOURCE' for t in n.targets))
    ns['LIFETIME_SOURCE']=ast.literal_eval(definition.value)
    validator=next(n for n in lifetime.body if isinstance(n,ast.FunctionDef) and n.name=='validate_jobs_shutdown')
    validator.body=[n for n in validator.body if not isinstance(n,ast.ImportFrom)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[validator],type_ignores=[])),
                 '<pure native lifetime transition>','exec'),ns)
    tool=ast.parse(QUALIFIER_SOURCE.read_text(encoding='utf-8'))
    addition=ast.Module(body=[n for n in tool.body if isinstance(n,ast.FunctionDef)
        and n.name in ('saved_load_events','saved_load_validate_supervision','saved_load_reconcile_jobs','saved_load_reconcile_post160',
                       'saved_load_reconcile_later','saved_load_validate_publication','saved_load_validate_lifetime')],type_ignores=[])
    for fn in addition.body:
        if isinstance(fn,ast.FunctionDef):
            fn.body=[n for n in fn.body if not isinstance(n,ast.ImportFrom)]
    exec(compile(ast.fix_missing_locations(addition),'<staged transcript authentication>','exec'),ns)
    return ns


class LoadLedgerTranscript(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'events.jsonl'
        self.ns=pure_functions()
        self.begin=dict(stage='before_official_gamecore_load',game_bytes=12)
        self.returned=dict(stage='official_gamecore_load_returned',status=0,bytes_consumed=12,validation_completed=False)
        self.create=dict(stage='job_list_created',export='EXP_JobManager_CreateJobList',handle=1)
        self.observed=dict(stage='xp1_saved_raw_load_observed',receipt={})
        self.pins={'actual-source':'a'*64}
        self.report=dict(reaped=True,job_assigned=True,exit_code=90,error=None,timed_out=False,
                         timeout_seconds=45,memory_limit_bytes=512*1024*1024,stdout_limit_bytes=64*1024*1024,
                         source_unchanged={'actual-source':True})
        self.raw=dict(raw_load_receipt=dict(status=0,bytes_consumed=12,scheduler_ledger_reconciliation_pending=True,
            jobs_structural_candidate=dict(schema='civ6_host.saved_load_empty_jobs_transition.v1',
                source_proof_sha256=self.ns['SOURCE'][1],ledger_reconciled=False,
                snapshot_structural_candidate=True,created_empty_handles_candidate=[1])))

    def parse(self,rows):
        self.path.write_bytes(b''.join(json.dumps(row).encode()+b'\n' for row in rows))
        return self.ns['saved_load_events'](self.path,require_load_interval=True)[1]

    def reconcile(self,rows=None,report=None):
        events=self.parse(rows or [self.begin,self.create,self.returned,self.observed])
        return self.ns['saved_load_reconcile_jobs'](report or self.report,self.pins,self.raw,events['load_job_interval'])

    def test_exact_interval_reconciles_without_mutating_raw_receipt(self):
        before=copy.deepcopy(self.raw)
        receipt=self.reconcile()
        self.assertTrue(receipt['reconciliation']['ledger_reconciled'])
        self.assertTrue(receipt['ledger_provenance_authenticated'])
        self.assertEqual(receipt['first_line'],1)
        self.assertEqual(receipt['last_line'],3)
        self.assertEqual(receipt['stdout_sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(self.raw,before)
        self.assertTrue(self.raw['raw_load_receipt']['scheduler_ledger_reconciliation_pending'])

    def test_missing_begin_or_return_is_refused(self):
        for rows in ([self.create,self.returned,self.observed],[self.begin,self.create]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.parse(rows)

    def test_explicit_60s_supervision_must_match_its_selected_bound(self):
        events=self.parse([self.begin,self.create,self.returned,self.observed])
        report=dict(self.report,timeout_seconds=60)
        reconcile=self.ns['saved_load_reconcile_jobs']
        receipt=reconcile(report,self.pins,self.raw,events['load_job_interval'],lifetime_seconds=60)
        self.assertTrue(receipt['ledger_provenance_authenticated'])
        for timeout in (45,61,True):
            with self.subTest(timeout=timeout),self.assertRaises(ValueError):
                reconcile(report,self.pins,self.raw,events['load_job_interval'],lifetime_seconds=timeout)

    def test_120s_diagnostic_does_not_admit_a_mismatched_or_unbounded_report(self):
        events=self.parse([self.begin,self.create,self.returned,self.observed])
        report=dict(self.report,timeout_seconds=120)
        reconcile=self.ns['saved_load_reconcile_jobs']
        receipt=reconcile(report,self.pins,self.raw,events['load_job_interval'],lifetime_seconds=120)
        self.assertTrue(receipt['ledger_provenance_authenticated'])
        for timeout in (60,121,3600):
            with self.subTest(timeout=timeout),self.assertRaises(ValueError):
                reconcile(report,self.pins,self.raw,events['load_job_interval'],lifetime_seconds=timeout)

    def test_duplicate_begin_or_return_is_refused(self):
        for rows in ([self.begin,self.begin,self.returned],[self.begin,self.returned,self.returned]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.parse(rows)

    def test_reversed_markers_and_early_raw_receipt_are_refused(self):
        for rows in ([self.returned,self.begin],[self.begin,self.observed,self.returned]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):self.parse(rows)

    def test_unexpected_job_operation_reaches_existing_refusal(self):
        unknown=dict(stage='native_job_queued',export='EXP_JobManager_PushJobOntoList',handle=1)
        with self.assertRaisesRegex(ValueError,'unknown/non-admitted job export'):
            self.reconcile([self.begin,self.create,unknown,self.returned,self.observed])

    def test_outside_interval_job_does_not_explain_snapshot_change(self):
        with self.assertRaisesRegex(ValueError,'does not match'):
            self.reconcile([self.create,self.begin,self.returned,self.observed])

    def test_changed_pin_incomplete_pinset_or_failed_supervision_refuses(self):
        for update in (dict(source_unchanged={'actual-source':False}),dict(source_unchanged={}),
                       dict(reaped=False),dict(job_assigned=False),dict(timed_out=True),dict(error='pipe_reader_failed')):
            with self.subTest(update=update),self.assertRaises(ValueError):
                self.reconcile(report=dict(self.report,**update))

    def test_raw_receipt_must_match_marker_byte_count(self):
        with self.assertRaisesRegex(ValueError,'differs from its checked raw receipt'):
            self.reconcile([dict(self.begin,game_bytes=13),self.create,self.returned,self.observed])

    def test_duplicate_result_and_truncated_stdout_remain_refused(self):
        with self.assertRaisesRegex(ValueError,'Repeated saved Load result'):
            self.parse([self.begin,self.create,self.returned,self.observed,self.observed])
        self.path.write_bytes(json.dumps(self.begin).encode())
        with self.assertRaisesRegex(ValueError,'Incomplete or oversized native stdout physical line'):
            self.ns['saved_load_events'](self.path,require_load_interval=True)

    def post_case(self):
        core=dict(profile=2,sha256='test-core');build=dict(host_sha256='test-host')
        self.raw['raw_load_receipt']['jobs_structural_candidate'].update(core_identity=core,source_build=build)
        self.raw['readback']=dict(turn=1,width=74,height=46)
        snapshot=dict(schema=self.ns['SCHEMA'],profile=self.ns['PROFILE'],source_proof_sha256=self.ns['SOURCE'][1],
            stable_read=True,memory_modified=False,concurrent_scheduler_supported=False,
            native_introspection_only=True,native_methods_called=True,spawn_active=0,registry_lock_raw=0,
            pending_items=0,submission_sequence=0,groups=[],core_identity=core,source_build=build,
            slots=[dict(handle=i,occupied=i==1,count=0,items=[]) for i in range(1,65)])
        native=dict(stage='native_checkpoint_postload_160_returned',native_return=None,jobs_identical=True,
                    validation_completed=False,jobs_before=snapshot,jobs_after=copy.deepcopy(snapshot))
        result=dict(post160_called=True,call_returned=True,immediate_jobs_unchanged=True,
            postreadback_jobs_unchanged=True,owners_retained=True,post190_called=False,
            game_update_called=False,context_destroyed=False,full_exe_load_lifecycle_reproduced=False,
            reset_validated=False,continuation_validated=False,eligible_for_training=False,
            readback=dict(current_game_turn=1,width=74,height=46,major_player_ids=list(range(6)),
                scope='privileged diagnostic; no learner observation',game_update_called=False))
        rows=[self.begin,self.create,self.returned,self.observed,
              dict(stage='xp1_saved_cache_observed',receipt={}),
              dict(stage='before_xp1_saved_post160_sequence'),native,
              dict(stage='xp1_saved_post160_sequence_returned',receipt={})]
        return rows,result

    def post_reconcile(self,rows,result):
        load_events=self.parse(rows)
        ledger=self.ns['saved_load_reconcile_jobs'](self.report,self.pins,self.raw,load_events['load_job_interval'])
        events=self.ns['saved_load_events'](self.path,require_post160_interval=True)[1]
        return self.ns['saved_load_reconcile_post160'](self.report,self.pins,self.raw,result,events,ledger,lifetime_seconds=45)

    def test_post160_has_its_own_completed_interval_without_public_admission(self):
        rows,result=self.post_case();receipt=self.post_reconcile(rows,result)
        self.assertTrue(receipt['ledger_provenance_authenticated'])
        self.assertFalse(receipt['public_runtime_admitted'])
        self.assertEqual(receipt['first_line'],6);self.assertEqual(receipt['last_line'],8)
        self.assertEqual(receipt['final_jobs'],rows[6]['jobs_after'])
        self.assertEqual(receipt['final_jobs']['schema'],self.ns['SCHEMA'])
        self.assertNotEqual(receipt['final_jobs'],self.raw['raw_load_receipt']['jobs_structural_candidate'])

    def test_completed_load_remains_authenticatable_after_later_strict_refusal(self):
        rows,_=self.post_case();rows=rows[:6]+[dict(stage='unsupported_host_contract',slot='0x90')]
        self.report['exit_code']=78
        events=self.parse(rows)
        ledger=self.ns['saved_load_reconcile_jobs'](self.report,self.pins,self.raw,events['load_job_interval'])
        self.assertTrue(ledger['ledger_provenance_authenticated'])
        with self.assertRaisesRegex(ValueError,'Incomplete native post160'):
            self.ns['saved_load_events'](self.path,require_post160_interval=True)

    def test_post160_refuses_missing_cache_or_outside_native_return(self):
        rows,result=self.post_case()
        for altered in (rows[:4]+rows[5:],rows[:5]+[rows[6],rows[5],rows[7]],rows[:-1]):
            with self.subTest(altered=altered),self.assertRaises(ValueError):self.post_reconcile(altered,result)

    def test_post160_cannot_hide_a_job_create_behind_equal_snapshots(self):
        rows,result=self.post_case();rows.insert(6,dict(self.create,handle=2))
        with self.assertRaisesRegex(ValueError,'scheduler interval'):self.post_reconcile(rows,result)

    def test_post160_rejects_pending_jobs_changed_core_or_changed_roster(self):
        rows,result=self.post_case()
        for mutation in ('pending','core','roster','return'):
            changed=copy.deepcopy(rows);value=copy.deepcopy(result)
            if mutation=='pending':changed[6]['jobs_before']['pending_items']=1
            elif mutation=='core':
                changed[6]['jobs_before']['core_identity']=dict(profile=2,sha256='other')
                changed[6]['jobs_after']['core_identity']=dict(profile=2,sha256='other')
            elif mutation=='roster':value['readback']['major_player_ids']=[0,1]
            else:changed[6]['native_return']=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.post_reconcile(changed,value)

    def continuation_case(self):
        rows,post=self.post_case();snap=rows[6]['jobs_before']
        snap.update(current_executable={'host_base':1,'executable_path':'test-host','os_thread_id':7},
                    host_sha256='test-host',owner_thread_id=7)
        rows[6]['jobs_after']=copy.deepcopy(snap)
        publication=dict(post190_called=True,native_return_ignored=True,public_runtime_admitted=False,
            public_player_observation=False,game_update_called=False,context_destroyed=False,
            jobs_before=copy.deepcopy(snap),jobs_after=copy.deepcopy(snap),jobs_final=copy.deepcopy(snap),
            readback=copy.deepcopy(post['readback']),cache_dimensions=[74,46,3404])
        rows.extend((dict(stage='before_xp1_saved_cache_publication'),
                     dict(stage='xp1_saved_cache_publication_returned',receipt={})))
        after=copy.deepcopy(snap);after['slots'][0]['occupied']=False
        transition=self.ns['validate_jobs_shutdown'](snap,after)
        lifetime=dict(native_unload_called=True,native_destroy_called=True,context_destroyed=True,
            cache_wrappers_released=True,services_closed=True,configuration_closed=True,lua_closed=True,
            core_lock_closed=True,database_shutdown=True,unknown_host_callbacks_refused=True,
            public_loaded_lifetime_admitted=False,cleanup_inferred_from_process_exit=False,
            source_sha256=self.ns['LIFETIME_SOURCE'][1],jobs_before=copy.deepcopy(snap),jobs_unloaded=after,
            jobs_transition=transition,jobs_identical=False,
            performance_closed=dict(native_destructor_returned=True,guards_intact=True,
                values_before_close=[],outer_storage_freed_by_native=False),
            steps=['native_cache_wrappers_released','native_unload','native_destroy','shared_services_closed',
                'native_performance_map_destroyed','native_configuration_destroyed','native_lua_closed',
                'native_core_lock_closed','database_shutdown'])
        rows.extend((dict(stage='before_xp1_saved_loaded_close',completed_phase='publication'),
            dict(stage='before_xp1_loaded_wrapper_release',source_sha256=lifetime['source_sha256'],jobs_before=copy.deepcopy(snap)),
            dict(stage='xp1_loaded_wrappers_released',owners=['prefix.cache_facades','publisher._facades','status.game'],
                 native_release_calls_completed=True,unknown_status_after_release_refused=True),
            dict(stage='before_xp1_loaded_unload',source_sha256=lifetime['source_sha256'],target_rva='0x4be690'),
            dict(stage='job_list_freed',export='EXP_JobManager_FreeJobList',handle=1,canonical_handle=1,queued_jobs=0),
            dict(stage='xp1_loaded_unload_returned',source_sha256=lifetime['source_sha256'],void_return_ignored=True,
                 game_object_null=True,cache_service_null=True,rules_manager_null=True,jobs_unloaded=copy.deepcopy(after),jobs_transition=transition),
            dict(stage='before_xp1_loaded_destroy',source_sha256=lifetime['source_sha256']),
            dict(stage='xp1_loaded_destroy_returned',source_sha256=lifetime['source_sha256'],void_return_ignored=True,
                 context_storage_read_after_destroy=False,native_globals_detached=True),
            dict(stage='xp1_loaded_lifetime_closed',**copy.deepcopy(lifetime)),
            dict(stage='xp1_saved_loaded_close_returned',receipt={})))
        return rows,post,publication,lifetime

    def reconcile_continuation(self,rows,post,publication,lifetime,phase='lifetime'):
        earlier=self.post_reconcile(rows,post)
        events=self.ns['saved_load_events'](self.path,require_interval='publication')[1]
        publish=self.ns['saved_load_reconcile_later'](self.report,self.pins,self.raw,publication,events,
            earlier,phase='publication',lifetime_seconds=45)
        if phase=='publication':return publish
        events=self.ns['saved_load_events'](self.path,require_interval='lifetime')[1]
        return self.ns['saved_load_reconcile_later'](self.report,self.pins,self.raw,lifetime,events,
            publish,phase='lifetime',lifetime_seconds=45)

    def test_combined_private_publication_and_native_lifetime_authenticated(self):
        rows,post,publish,lifetime=self.continuation_case();before=copy.deepcopy((post,publish,lifetime))
        publication_ledger=self.reconcile_continuation(rows,post,publish,lifetime,phase='publication')
        self.assertEqual(publication_ledger['final_jobs'],publish['jobs_final'])
        result=self.reconcile_continuation(rows,post,publish,lifetime)
        self.assertTrue(result['phase_receipt']['native_destroy_authenticated'])
        self.assertEqual(result['phase_receipt']['removed_empty_handles'],[1])
        self.assertEqual(result['final_jobs'],lifetime['jobs_unloaded'])
        self.assertNotEqual(result['final_jobs'],lifetime['jobs_before'])
        self.assertFalse(result['public_runtime_admitted'])
        self.assertFalse(result['phase_receipt']['post_destroy_snapshot_taken'])
        self.assertEqual((post,publish,lifetime),before)
        self.assertFalse(post['context_destroyed']);self.assertFalse(publish['context_destroyed'])

    def continuation_join_case(self,phase):
        """Exercise phase joins; UI/action bodies are explicit offline fixtures."""
        rows,post,publish,lifetime=self.continuation_case()
        rows[10:10]=[dict(stage='before_xp1_saved_player_view'),
                     dict(stage='xp1_saved_player_view_returned',receipt={}),
                     dict(stage='before_xp1_saved_unit_commands'),
                     dict(stage='xp1_saved_unit_commands_returned',receipt={})]
        snapshot=publish['jobs_after']
        results={'publication':publish,'lifetime':lifetime}
        for name in ('player_view','unit_commands'):
            results[name]=dict(jobs_before=copy.deepcopy(snapshot),jobs_after=copy.deepcopy(snapshot))
            self.ns['saved_load_validate_'+name]=lambda *args:dict(offline_phase_body_fixture=True)
        results['unit_commands']['action']={'kind':'found_city'}
        previous=self.post_reconcile(rows,post)
        for name in ('publication','player_view','unit_commands','lifetime'):
            events=self.ns['saved_load_events'](self.path,require_interval=name)[1]
            if name==phase:return results[name],events,previous
            previous=self.ns['saved_load_reconcile_later'](self.report,self.pins,self.raw,
                results[name],events,previous,phase=name,lifetime_seconds=45)
        raise AssertionError('Unknown test phase')

    def test_each_phase_rejects_unexplained_slot_sequence_or_thread_change(self):
        for phase in ('publication','player_view','unit_commands','lifetime'):
            for mutation in ('slot','sequence','thread'):
                result,events,previous=self.continuation_join_case(phase)
                if mutation=='slot':result['jobs_before']['slots'][1]['occupied']=True
                elif mutation=='sequence':result['jobs_before']['submission_sequence']+=1
                else:
                    result['jobs_before']['owner_thread_id']=8
                    result['jobs_before']['current_executable']['os_thread_id']=8
                with self.subTest(phase=phase,mutation=mutation),self.assertRaisesRegex(ValueError,
                        'Loaded continuation scheduler snapshot differs from its authenticated prior phase'):
                    self.ns['saved_load_reconcile_later'](self.report,self.pins,self.raw,result,events,
                        previous,phase=phase,lifetime_seconds=45)

    def test_transition_summary_or_legacy_action_field_cannot_replace_prior_snapshot(self):
        for phase in ('publication','player_view','unit_commands','lifetime'):
            for mutation in ('summary','missing'):
                result,events,previous=self.continuation_join_case(phase)
                previous['post_action_jobs']=copy.deepcopy(result['jobs_before'])
                if mutation=='summary':
                    previous['final_jobs']=copy.deepcopy(self.raw['raw_load_receipt']['jobs_structural_candidate'])
                else:previous.pop('final_jobs')
                with self.subTest(phase=phase,mutation=mutation),self.assertRaisesRegex(ValueError,
                        'Loaded continuation scheduler snapshot differs from its authenticated prior phase'):
                    self.ns['saved_load_reconcile_later'](self.report,self.pins,self.raw,result,events,
                        previous,phase=phase,lifetime_seconds=45)

    def test_action_join_passes_actual_prior_snapshot_and_exports_actual_after(self):
        result,events,previous=self.continuation_join_case('unit_commands')
        # This tests only transport of an already validated action snapshot,
        # not execution/reconciliation of the fixture's scheduler operation.
        result['jobs_after']['submission_sequence']=3
        seen=[]
        def phase_validator(value,interval,prior):
            seen.append(prior)
            return dict(offline_phase_body_fixture=True)
        self.ns['saved_load_validate_unit_commands']=phase_validator
        receipt=self.ns['saved_load_reconcile_later'](self.report,self.pins,self.raw,result,events,
            previous,phase='unit_commands',lifetime_seconds=45)
        self.assertEqual(seen,[previous['final_jobs']])
        self.assertEqual(seen[0]['schema'],self.ns['SCHEMA'])
        self.assertEqual(receipt['final_jobs'],result['jobs_after'])
        self.assertEqual(receipt['post_action_jobs'],result['jobs_after'])
        self.assertNotEqual(receipt['final_jobs'],previous['final_jobs'])
        self.assertFalse(receipt['public_runtime_admitted'])

    def test_later_failure_does_not_erase_completed_load_post160_or_publication(self):
        rows,post,publish,lifetime=self.continuation_case()
        rows=rows[:14]+[dict(stage='unsupported_host_contract',slot='0xc0')]
        self.report['exit_code']=78
        result=self.reconcile_continuation(rows,post,publish,lifetime,phase='publication')
        self.assertTrue(result['ledger_provenance_authenticated'])
        with self.assertRaisesRegex(ValueError,'Incomplete native lifetime'):
            self.ns['saved_load_events'](self.path,require_interval='lifetime')

    def test_publication_cannot_claim_human_view_or_hide_scheduler_work(self):
        rows,post,publish,lifetime=self.continuation_case()
        for mutation in ('public','dimensions','changed','create'):
            r,p=copy.deepcopy(rows),copy.deepcopy(publish)
            if mutation=='public':p['public_player_observation']=True
            elif mutation=='dimensions':p['cache_dimensions'][0]=75
            elif mutation=='changed':p['jobs_final']['core_identity']['sha256']='different'
            else:r.insert(9,dict(self.create,handle=2))
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.reconcile_continuation(r,post,p,lifetime,phase='publication')

    def test_destroy_success_requires_ordered_native_markers_not_exit_or_flags(self):
        rows,post,publish,lifetime=self.continuation_case()
        for mutation in ('missing','reversed','duplicated','source','freed_context','native_globals'):
            r=copy.deepcopy(rows)
            if mutation=='missing':r=[x for x in r if x['stage']!='xp1_loaded_destroy_returned']
            elif mutation=='reversed':r[16],r[17]=r[17],r[16]
            elif mutation=='duplicated':r.insert(18,copy.deepcopy(r[17]))
            elif mutation=='source':r[17]['source_sha256']='x'
            elif mutation=='freed_context':r[17]['context_storage_read_after_destroy']=True
            else:r[17]['native_globals_detached']=False
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.reconcile_continuation(r,post,publish,lifetime)

    def test_cleanup_report_cannot_skip_borrowed_services_or_change_step_order(self):
        rows,post,publish,lifetime=self.continuation_case()
        for mutation in ('lua','options','order','inference'):
            value=copy.deepcopy(lifetime)
            if mutation=='lua':value['lua_closed']=False
            elif mutation=='options':value['performance_closed']['guards_intact']=False
            elif mutation=='order':value['steps'][1],value['steps'][2]=value['steps'][2],value['steps'][1]
            else:value['cleanup_inferred_from_process_exit']=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.reconcile_continuation(rows,post,publish,value)

    def test_removed_slot_requires_exact_native_free_ledger(self):
        rows,post,publish,lifetime=self.continuation_case()
        for mutation in ('missing','double','wrong_canonical','queued','after_unload'):
            r=copy.deepcopy(rows)
            if mutation=='missing':del r[14]
            elif mutation=='double':r.insert(15,copy.deepcopy(r[14]))
            elif mutation=='wrong_canonical':r[14]['canonical_handle']=2
            elif mutation=='queued':r[14]['queued_jobs']=1
            else:r[14],r[15]=r[15],r[14]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                self.reconcile_continuation(r,post,publish,lifetime)
        rows[14]['handle']=(1<<32)+1
        self.assertTrue(self.reconcile_continuation(rows,post,publish,lifetime)['phase_receipt']['native_destroy_authenticated'])

    def test_empty_group_destruction_and_ignored_free_are_exact_noops(self):
        rows,post,publish,lifetime=self.continuation_case()
        extra=[dict(stage='empty_job_set_destroyed',export='EXP_JobManager_DestroyJobSet',
                    first_argument_raw=0x1000,member0=0,member8=0,contract='two_null_members_only'),
               dict(stage='job_list_free_ignored',export='EXP_JobManager_FreeJobList',handle=1,reason='inactive')]
        rows[18:18]=extra
        self.assertEqual(self.reconcile_continuation(rows,post,publish,lifetime)['phase_receipt']['noop_records'],2)
        rows[19]['reason']='out_of_range'
        with self.assertRaisesRegex(ValueError,'Ignored native release'):
            self.reconcile_continuation(rows,post,publish,lifetime)

    def test_group_removal_is_count_reconciled_not_invented_pointer_evidence(self):
        rows,post,publish,lifetime=self.continuation_case()
        group=dict(pointer=0x2000,owner=0x3000,pending=0)
        for snapshot in (rows[6]['jobs_before'],rows[6]['jobs_after'],publish['jobs_before'],publish['jobs_after'],
                         publish['jobs_final'],lifetime['jobs_before'],rows[11]['jobs_before']):
            snapshot['groups']=[copy.deepcopy(group)]
        life_transition=self.ns['validate_jobs_shutdown'](lifetime['jobs_before'],lifetime['jobs_unloaded'])
        lifetime['jobs_transition']=life_transition;rows[15]['jobs_transition']=copy.deepcopy(life_transition)
        rows[18]=dict(stage='xp1_loaded_lifetime_closed',**copy.deepcopy(lifetime))
        rows.insert(15,dict(stage='native_job_set_destroyed',pending_jobs=0,profile='diagnostic_serial_native_callbacks'))
        receipt=self.reconcile_continuation(rows,post,publish,lifetime)['phase_receipt']
        self.assertEqual(receipt['removed_group_count'],1)
        self.assertIn('not pointer',receipt['group_identity_limit'])
        rows[15]['pending_jobs']=1
        with self.assertRaisesRegex(ValueError,'owned native job group'):
            self.reconcile_continuation(rows,post,publish,lifetime)

    def test_invalid_native_interval_selection_refuses(self):
        rows,post,publish,lifetime=self.continuation_case();self.parse(rows)
        for kwargs in ({'require_interval':'unknown'}, {'require_load_interval':True,'require_interval':'publication'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.ns['saved_load_events'](self.path,**kwargs)


if __name__=='__main__':unittest.main()

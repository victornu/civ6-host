"""Stopped-process observation receipts using the real shared parser and ledgers."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import qualify_xp1_configuration as q
import test_xp2_saved_load_supervision as raw_fixtures
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


class XP2ObservationSupervision(unittest.TestCase):
    write=raw_fixtures.XP2SavedLoadSupervision.write
    persist=raw_fixtures.XP2SavedLoadSupervision.persist
    evaluate=raw_fixtures.XP2SavedLoadSupervision.evaluate

    def setUp(self):
        raw_fixtures.XP2SavedLoadSupervision.setUp(self)
        from civ6_host.runtime.xp2_ui_binding_source import SOURCE,UI_THUNK_RVA
        self.sources.update(postload160=True,observe_player=True,wall_limit_seconds=180,memory_limit_bytes=768*1024**2)
        self.report['wall_limit_seconds']=180
        host=q.resource_root()/q.XP2_UI_HOST[0];build=host.with_name('build.json')
        self.sources['native_host']=dict(path=str(host),sha256=q.XP2_UI_HOST[1])
        self.sources['native_build']=dict(path=str(build),sha256=q.digest(build.read_bytes()))
        for snapshot in (self.before,self.after):
            snapshot['host_sha256']=q.XP2_UI_HOST[1]
            snapshot['source_build']['host_sha256']=q.XP2_UI_HOST[1]
        self.write('executed-source-pins.json',self.sources)
        self.group.update(status='native_xp2_captured_player_observation_and_close_passed',
            postload_completed=True,player_observed=True)
        expected=dict(current_game_turn=1,width=44,height=26,major_player_ids=[0,1],
            scope='privileged diagnostic; no learner observation',game_update_called=False)
        self.post=dict(post160_called=True,call_returned=True,immediate_jobs_unchanged=True,
            postreadback_jobs_unchanged=True,owners_retained=True,post190_called=False,
            game_update_called=False,context_destroyed=False,full_exe_load_lifecycle_reproduced=False,
            reset_validated=False,continuation_validated=False,eligible_for_training=False,readback=expected)
        self.publication=dict(post190_called=True,native_return_ignored=True,public_runtime_admitted=False,
            public_player_observation=False,game_update_called=False,context_destroyed=False,
            jobs_before=self.after,jobs_after=self.after,jobs_final=self.after,
            readback=expected,cache_dimensions=[44,26,1144])
        binding=dict(native_ui_registration_returned=True,outer_protected_status=0,
            distinct_managed_children=True,complete_registration_verified=False,gameplay_api_copied=False,
            source_sha256=SOURCE[1],core_sha256=XP2_CORE_SHA256,method_rva=hex(UI_THUNK_RVA),
            profile_id=2,native_host_sha256=q.XP2_UI_HOST[1])
        self.view=dict(binding=binding,observation=dict(schema='civ6rl-player-observation-v1',
            player_id=0,turn=1,width=44,height=26,plots=[],units=[],cities=[],visible_enemy_units=[],
            economy=dict(science=0,culture=0,gold=0,faith=0)),jobs_before=self.after,jobs_after=self.after,
            player_id=0,source_sha256=SOURCE[1],core_sha256=XP2_CORE_SHA256,
            public_runtime_admitted=False,complete_player_observation=False,visibility_parity_qualified=False,
            game_update_called=False,gameplay_api_copied=False,gameplay_visibility_unchanged=True,
            explored_memory_included=False)
        self.closed.update(cache_wrappers_released=True,raw_load_only=False,post160_called=True,
            ui_child_released=True,ui_child_release_order='after_native_destroy_before_game_child_and_runtime_close')
        self.closed['steps'][0]='native_cache_wrappers_released'
        self.closed['steps'][6:6]=['saved_ui_child_released','game_child_released']
        close_rows=[r for r in self.rows[6:-1] if r['stage']!='xp2_unloaded_notifications_consumed']
        close_rows.insert(1,dict(stage='xp2_loaded_wrappers_released',
            owners=['prefix.cache_facades','publisher._facades','status.game'],
            native_release_calls_completed=True,unknown_status_after_release_refused=True))
        close_rows[-1]=dict(stage='xp2_loaded_lifetime_closed',**self.closed)
        self.rows=self.rows[:4]+[
            dict(stage='xp1_saved_raw_load_observed',receipt={}),
            dict(stage='xp1_saved_cache_observed',receipt=self.write('cache-result.json',
                dict(candidate_native_cache_only=True,public_cache_gate_enabled=False))),
            dict(stage='before_xp1_saved_post160_sequence'),
            dict(stage='native_checkpoint_postload_160_returned',native_return=None,jobs_identical=True,
                validation_completed=False,jobs_before=self.after,jobs_after=self.after),
            dict(stage='xp1_saved_post160_sequence_returned',receipt={}),
            dict(stage='before_xp1_saved_cache_publication'),
            dict(stage='xp1_saved_cache_publication_returned',receipt={}),
            dict(stage='before_xp1_saved_player_view'),
            dict(stage='before_xp1_ui_api_bind',core_sha256=XP2_CORE_SHA256,
                source_sha256=SOURCE[1],method_rva=hex(UI_THUNK_RVA),native_host_sha256=q.XP2_UI_HOST[1]),
            dict(stage='xp1_ui_api_bind_returned',**binding),
            dict(stage='xp1_saved_player_view_returned',receipt={}),
            dict(stage='before_xp1_saved_loaded_close',completed_phase='player_view'),
            *close_rows,dict(stage='xp1_saved_loaded_close_returned',receipt={}),
            dict(stage='xp2_saved_load_group_completed',status=self.group['status'])]
        self.refresh()

    def refresh(self):
        self.persist()
        refs={'xp1_saved_raw_load_observed':self.write('raw-load-result.json',self.raw),
            'xp1_saved_post160_sequence_returned':self.write('post160-result.json',self.post),
            'xp1_saved_cache_publication_returned':self.write('publication-result.json',self.publication),
            'xp1_saved_player_view_returned':self.write('player-view-result.json',self.view),
            'xp1_saved_loaded_close_returned':self.write('loaded-lifetime-result.json',self.closed)}
        for row in self.rows:
            if row['stage'] in refs:row['receipt']=refs[row['stage']]
            if row['stage']=='xp2_loaded_lifetime_closed':row.update(self.closed)
        self.persist()

    def test_full_load_publication_observation_and_ui_close(self):
        result=self.evaluate();self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['phases']['player_view'],'authenticated')
        self.assertEqual(result['status'],'authenticated_load_player_observation_and_close')
        observed=result['reconciliations']['player_view']['phase_receipt']
        self.assertTrue(observed['captured_own_readback_matched'])
        self.assertEqual(observed['compared'],self.readback)
        self.assertFalse(result['public_session_admitted'])

    def test_changed_own_readback_refuses_without_replacing_observation(self):
        self.view['observation']['economy']['gold']=99;before=copy.deepcopy(self.view)
        self.refresh();result=self.evaluate()
        self.assertFalse(result['passed']);self.assertIn('own-player fields',result['errors'][0])
        self.assertEqual(self.view,before)

    def test_extra_unit_missing_unit_and_city_count_are_compared(self):
        for rows in ([dict(owner=0,id=7,type=1,x=2,y=3,damage=0,moves=2,max_moves=2)],[]):
            self.readback['units']=[dict(id=7,type=1,x=2,y=3,damage=0,moves=1)]
            self.view['observation']['units']=rows
            self.refresh();self.assertFalse(self.evaluate()['passed'])

    def test_binding_source_engine_method_and_receipt_hash_are_exact(self):
        original=copy.deepcopy(self.view)
        for key,value in (('source_sha256','0'*64),('core_sha256','0'*64),('method_rva','0x4cbe50')):
            self.view=copy.deepcopy(original);self.view['binding'][key]=value;self.refresh()
            self.assertFalse(self.evaluate()['passed'])
        self.view=original;self.refresh();(self.run/'player-view-result.json').write_bytes(b'{}')
        self.assertFalse(self.evaluate()['passed'])

    def test_same_jobs_and_roster_are_required(self):
        self.view['jobs_after']=copy.deepcopy(self.after);self.view['jobs_after']['submission_sequence']=1
        self.refresh();self.assertFalse(self.evaluate()['passed'])
        self.view['jobs_after']=self.after;self.post['readback']=dict(self.post['readback'],major_player_ids=list(range(6)))
        self.refresh();self.assertFalse(self.evaluate()['passed'])

    def test_missing_ui_return_and_close_before_observation_refuse(self):
        original=copy.deepcopy(self.rows)
        self.rows=[r for r in self.rows if r['stage']!='xp1_ui_api_bind_returned'];self.refresh()
        self.assertFalse(self.evaluate()['passed'])
        self.rows=original
        first=next(i for i,r in enumerate(self.rows) if r['stage']=='before_xp1_saved_loaded_close')
        self.rows[first-1],self.rows[first]=self.rows[first],self.rows[first-1]
        self.refresh();self.assertFalse(self.evaluate()['passed'])

    def test_ui_child_must_close_before_game_child_and_runtime(self):
        self.closed['ui_child_released']=False;self.refresh();self.assertFalse(self.evaluate()['passed'])
        self.closed['ui_child_released']=True
        self.closed['steps'][6],self.closed['steps'][7]=self.closed['steps'][7],self.closed['steps'][6]
        self.refresh();self.assertFalse(self.evaluate()['passed'])

    def test_unrequested_observation_and_failed_worker_never_promoted(self):
        self.sources.pop('observe_player');self.write('executed-source-pins.json',self.sources)
        self.assertFalse(self.evaluate()['passed'])
        self.sources['observe_player']=True;self.write('executed-source-pins.json',self.sources)
        self.report.update(status='failed',exit_code=1)
        self.assertFalse(self.evaluate()['passed'])

    def test_observation_budget_is_exact_and_cannot_extend_raw_or_postload(self):
        for changed in (dict(wall_limit_seconds=120),dict(wall_limit_seconds=181),
                        dict(memory_limit_bytes=1024*1024**2)):
            original=dict(self.report);self.report.update(changed)
            self.assertFalse(self.evaluate()['passed']);self.report=original
        self.sources['wall_limit_seconds']=120;self.write('executed-source-pins.json',self.sources)
        self.assertFalse(self.evaluate()['passed'])

    def test_actual_selected_dependencies_include_ui_binder_and_registered_build(self):
        from civ6_host.runtime.xp2_ui_binding_source import SOURCE,UI_COMPONENT_SHA
        pins=q.xp2_saved_load_source_dependencies(postload160=True,observe_player=True)
        self.assertIn(SOURCE[1],pins.values())
        self.assertTrue(any(name.endswith('script_core_ui_binding_profiles.inc') and sha==UI_COMPONENT_SHA
                            for name,sha in pins.items()))
        self.assertIn(str(q.resource_root()/q.XP2_UI_HOST[0]).replace('civ6rl-native-python.exe','build.json'),pins)
        for scope in (dict(observe_player=True),dict(postload160=1),dict(postload160=True,observe_player=1)):
            with self.assertRaises(ValueError):q.xp2_saved_load_source_dependencies(**scope)

    def test_cli_dependencies_and_unknown_native_flags_fail_before_launch(self):
        for argv in (['--observe-player'],['--saved-load','--observe-player'],
            ['--saved-load','--postload160','--observe-player','--unit-command','found_city']):
            with self.subTest(argv=argv),patch('subprocess.Popen') as launch:
                with self.assertRaises(ValueError):q.xp2_configuration_main(argv)
                launch.assert_not_called()

if __name__=='__main__':unittest.main()

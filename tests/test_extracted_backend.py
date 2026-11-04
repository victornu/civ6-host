"""Grouped extracted-runtime qualification; native case is explicitly opt-in."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest

REPO=Path(__file__).resolve().parents[1]


class ExtractedRuntimeTests(unittest.TestCase):
    def test_packaged_graph_contains_no_lab_or_learner_imports(self):
        manifest=json.loads((REPO/'src/civ6_host/runtime/source-map.json').read_text())
        self.assertGreater(len(manifest['sources']),0)
        for row in manifest['sources']:
            path=REPO/row['destination'];raw=path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['destination_sha256'])
            for n in ast.walk(ast.parse(raw)):
                names=([x.name for x in n.names] if isinstance(n,ast.Import) else
                       [n.module or ''] if isinstance(n,ast.ImportFrom) and not n.level else [])
                self.assertFalse(any(x.split('.')[0] in ('civ6rl','tools','torch') for x in names),row['module'])
                if isinstance(n,ast.Call):
                    function=ast.unparse(n.func)
                    self.assertFalse(function.endswith(('spec_from_file_location','exec_module','SourceFileLoader','run_path')),row['module'])
                    if function in ('__import__','importlib.import_module'):
                        self.assertIsInstance(n.args[0],ast.Constant)
                        self.assertFalse(n.args[0].value.split('.')[0] in ('civ6rl','tools','torch'),row['module'])

    def test_private_file_execution_is_rejected_in_isolated_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'historical.py'
            source.write_text("raise AssertionError('historical source executed')\n")
            code='''
import sys,os,importlib.util
sys.path.insert(0,sys.argv[1])
os.environ['CIV6_HOST_RESOURCE_ROOT']=sys.argv[2]
from civ6_host.runtime.import_boundary import enable
enable()
from civ6_host.runtime import windows_process
for name in ('civ6rl','tools','torch'):
    try:__import__(name)
    except ImportError:pass
    else:raise AssertionError('forbidden import succeeded')
spec=importlib.util.spec_from_file_location('innocent_alias',sys.argv[3])
module=importlib.util.module_from_spec(spec)
try:spec.loader.exec_module(module)
except RuntimeError as exc:assert 'Private resources are data' in str(exc)
else:raise AssertionError('historical execution was not rejected')
print('private execution and forbidden imports rejected')
'''
            result=subprocess.run([sys.executable,'-I','-B','-c',code,str(REPO/'src'),str(root),str(source)],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_city_observation_uses_installed_collector(self):
        source=REPO/'src/civ6_host/runtime/native/native_city_range_attack.py'
        tree=ast.parse(source.read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='collect_player_observation')
        imports=[n for n in ast.walk(fn) if isinstance(n,ast.ImportFrom)]
        self.assertEqual([(n.module,[a.name for a in n.names]) for n in imports],
            [('civ6_host.runtime.native.native_player_observation',['observe_player'])])
        # Check the extracted boundary delegates the exact caller arguments.
        from types import ModuleType
        from unittest.mock import patch
        m=ModuleType(imports[0].module);calls=[]
        m.observe_player=lambda *args:calls.append(args) or {'player_id':args[-1]}
        namespace={'_pid':lambda pid:None}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),namespace)
        with patch.dict(sys.modules,{m.__name__:m}):
            result=namespace['collect_player_observation']('runtime','child',3)
        self.assertEqual(calls,[('runtime','child',3)])
        self.assertEqual(result,{'player_id':3})

    def test_extracted_decision_wrappers_preserve_player_windows_and_native_guards(self):
        """Exercise the generated wrappers; native effects are explicit fixtures."""
        from types import SimpleNamespace
        from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
        from civ6_host.runtime.decision_context import store_for
        path=REPO/'src/civ6_host/runtime/native/native_saved_actions.py'
        tree=ast.parse(path.read_text())
        wrappers=[n for n in tree.body if isinstance(n,ast.FunctionDef)
                  and n.name in ('read_decisions','apply_choice')]
        self.assertEqual(len(wrappers),2)
        identity=DiagnosticEpisodeIdentity('00000000-0000-4000-8000-000000000001',
                                         'native-00000000-0000-4000-8000-000000000001')
        events=[]; calls=[]
        owner=SimpleNamespace(prefix=SimpleNamespace(_diagnostic_episode_identity=identity),
                              allowed={0,1},emit=lambda stage,**row:events.append((stage,row)))
        def boundary(owner,*,player_id,player_ids):
            if player_id not in owner.allowed:raise RuntimeError('native actor admission refused')
            return owner.prefix
        def read(owner,sequence,rounds,*,player_id,player_ids,**kw):
            owner.explicit_observation={'player_id':player_id,'turn':5}
            owner.explicit_decision_player_id=player_id
            owner.explicit_decision_candidates=[{'player':player_id,'sequence':sequence}]
            if player_id==0:owner.explicit_world_input={'player_id':0}
            return owner.explicit_observation,{'decision_id':f'{sequence:064x}','sequence':sequence}
        def apply(owner,action,turn,*,player_id,player_ids):
            self.assertEqual(owner.explicit_decision_player_id,player_id)
            self.assertEqual(owner.explicit_decision_candidates[0]['player'],player_id)
            calls.append(player_id)
            if action=='fail':raise RuntimeError('uncertain native command')
            return ('native-result',player_id)
        namespace={'boundary':boundary,'_read_decisions_without_context':read,
                   '_apply_choice_without_context':apply}
        exec(compile(ast.Module(body=wrappers,type_ignores=[]),str(path),'exec'),namespace)
        read_wrapped=namespace['read_decisions']; apply_wrapped=namespace['apply_choice']
        for pid in (0,1):read_wrapped(owner,pid+1,0,player_id=pid,player_ids=(0,1))
        self.assertFalse(hasattr(owner,'explicit_world_input'),'Optional p0 alias leaked into p1 read')
        self.assertEqual(store_for(owner).snapshot_count,2)
        owner.allowed={1}
        with self.assertRaisesRegex(RuntimeError,'admission refused'):
            apply_wrapped(owner,'ok',5,player_id=0,player_ids=(0,1))
        self.assertEqual(calls,[])
        self.assertEqual(store_for(owner).snapshot_count,2)
        owner.allowed={0,1}
        self.assertEqual(apply_wrapped(owner,'ok',5,player_id=0,player_ids=(0,1)),('native-result',0))
        self.assertEqual(store_for(owner).snapshot_count,1)
        self.assertEqual(owner.explicit_decision_player_id,1)
        self.assertFalse(hasattr(owner,'explicit_world_input'))
        with self.assertRaisesRegex(RuntimeError,'scope is stale'):
            apply_wrapped(owner,'ok',4,player_id=1,player_ids=(0,1))
        self.assertEqual(store_for(owner).snapshot_count,1)
        with self.assertRaisesRegex(RuntimeError,'uncertain native command'):
            apply_wrapped(owner,'fail',5,player_id=1,player_ids=(0,1))
        self.assertEqual(store_for(owner).snapshot_count,0)
        self.assertEqual(calls,[0,1])

    @unittest.skipUnless(os.environ.get('CIV6_HOST_RUN_NATIVE')=='1','explicit native opt-in')
    def test_installed_runtime_matches_retained_native_roundtrip(self):
        resources=Path(os.environ['CIV6_HOST_RESOURCE_ROOT']).resolve()
        installed=Path(os.environ['CIV6_HOST_TEST_INSTALL']).resolve()
        sys.path.insert(0,str(installed))
        from civ6_host import HotseatClient
        from civ6_host.runtime.backend import LocalHotseatBackend
        import civ6_host.runtime.backend as module
        self.assertTrue(Path(module.__file__).resolve().is_relative_to(installed))
        output=os.environ.get('CIV6_HOST_TEST_OUTPUT')
        out=Path(output).resolve() if output else resources/'work/host-backend-extraction'
        self.assertTrue(out.is_relative_to(resources/'work'))
        out.mkdir(exist_ok=True)
        prepared_raw=os.environ.get('CIV6_HOST_TEST_PREPARED_CAPTURE')
        prepared=None if prepared_raw is None else json.loads(prepared_raw)
        resource_raw=os.environ.get('CIV6_HOST_TEST_PRIVATE_RESOURCES')
        private_resources=None if resource_raw is None else json.loads(resource_raw)
        public_views=os.environ.get('CIV6_HOST_TEST_PUBLIC_VIEWS')=='1'
        decision_context=os.environ.get('CIV6_HOST_TEST_DECISION_CONTEXT')=='1'
        reference_root=Path(os.environ.get('CIV6_HOST_TEST_REFERENCE_ROOT',str(resources))).resolve()
        def record(path):
            return {'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        report={'status':'running','installed_runtime':True,'training_started':False,
                'full_game_launched':False,'simultaneous_qualified':False,'standalone_resource_bundle_ready':False}
        if prepared is not None:report['prepared_capture']=prepared
        if private_resources is not None:report['private_resources']=private_resources
        backend=client=None;started=time.perf_counter()
        try:
            witness=json.loads((reference_root/'evidence/host-client-extraction.json').read_text())
            ref=witness['native_validation']['proof'];path=reference_root/ref['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),ref['sha256'])
            old=json.loads(path.read_text())
            log=reference_root/old['native_run']/'events.jsonl'
            reference=[]
            with log.open('rb') as stream:
                for line in stream:
                    try:row=json.loads(line)
                    except ValueError:continue
                    if row.get('stage')=='official_session_response':reference.append(row)
            self.assertEqual([x['operation'] for x in reference],['reset','observe','act','close'])
            self.assertTrue(all(r['episode_id']==old['episode_id'] for r in reference))
            report['reference_events']=record(log)
            report['reference_delivery']=record(reference_root/'evidence/host-client-extraction.json')
            backend=LocalHotseatBackend(resources=resources,run_root=out/'native-runs',
                prepared_capture=prepared,
                private_resources=private_resources,
                public_view_players=[0,1] if public_views else None,
                round_limit=2,lifetime_seconds=600,stdout_limit_mib=256,
                episode_budget=dict(schema='civ6rl.bounded_episode_budget.v1',max_decisions=8,
                    max_updates=1,max_rounds=2,wall_seconds=600,request_seconds=60),
                official_bundle=dict(path='work/official-capture/hotseat4-20261027-file09/manifest.json',
                    sha256='35234a1ff8420992b27753acd443313b35f5074b84318c08008cec5f9adc3b3a'),
                ui_profile='base-standard-hotseat-capture09-ui-v1',
                multiturn_movement_diagnostic=True,movement_information_diagnostic=True,
                unit_order_cancel_diagnostic=True,world_input_diagnostic=True,
                privileged_critic_diagnostic=False)
            report['constructor_seconds']=time.perf_counter()-started
            client=HotseatClient(backend)
            views=[client.reset()]
            report['initial_response_seconds']=time.perf_counter()-started
            player_views=[]
            def read_extra_views():
                if not public_views:return
                primary=client.player_view(0)
                other=client.player_view(1)
                self.assertEqual(primary['observation'],client.view()['observation'])
                self.assertEqual(other['sequence'],client.view()['sequence'])
                self.assertTrue(all(x['owner']==1 for x in other['observation']['units']))
                self.assertTrue(other['observation']['units'])
                self.assertNotEqual(other['observation']['plots'],primary['observation']['plots'])
                self.assertEqual(other['player_turn'],dict(active=False,turn_active_complete=False))
                player_views.append(dict(sequence=other['sequence'],player_ids=[0,1],
                    primary_observation_equal=True,other_view_distinct=True,
                    other_player_own_units=len(other['observation']['units']),
                    other_player_visible_plots=len(other['observation']['plots']),
                    other_player_turn=other['player_turn']))
            read_extra_views()
            views.append(client.observe())
            read_extra_views()
            decisions=views[-1]['decisions']
            expected=reference[2]['applied_action']
            choices=[r for r in decisions['candidates'] if r['action']==expected]
            self.assertEqual(len(choices),1,'Retained human action must be available, no substitution')
            views.append(client.act(decisions['decision_id'],choices[0]['candidate_id']))
            read_extra_views()
            views.append(client.close())
            if public_views:
                with self.assertRaises(RuntimeError):client.player_view(1)
                report['public_player_views']=player_views
                files=list((backend.run/'public-player-views').iterdir())
                self.assertEqual(len(files),2,'Only latest public boundary files retained')
                report['public_view_latest_files']=[record(p) for p in files]
            def stable_catalog(value):
                value=copy.deepcopy(value)
                if value is not None:
                    for key in ('episode_id','game_generation','decision_id'):value.pop(key,None)
                return value
            report['comparisons']=[]
            for observed,previous in zip(views,reference):
                self.assertEqual(observed['observation'],previous['observation'])
                self.assertEqual(stable_catalog(observed['decisions']),stable_catalog(previous['decisions']))
                self.assertEqual(observed['applied_action'],previous['applied_action'])
                self.assertEqual(observed['outcome'],{k:previous['outcome'][k] for k in ('terminated','truncated','reason')})
                report['comparisons'].append({'operation':previous['operation'],'public_observation_equal':True,
                    'catalogue_equal_except_episode_identity':True,'applied_action_equal':True,'outcome_equal':True})
            self.assertTrue(backend.report['reaped'])
            self.assertEqual(backend.report['exit_code'],90)
            self.assertTrue(all(backend.report['source_unchanged'].values()))
            if decision_context:
                context_events=[]
                with (backend.run/'events.jsonl').open('rb') as stream:
                    for line in stream:
                        if b'decision_context_' not in line:continue
                        row=json.loads(line)
                        if row.get('stage') in ('decision_context_captured',
                                'decision_context_activated','decision_context_invalidated'):
                            context_events.append(row)
                captured=[r for r in context_events if r['stage']=='decision_context_captured']
                activated=[r for r in context_events if r['stage']=='decision_context_activated']
                consumed=[r for r in context_events if r['stage']=='decision_context_invalidated'
                          and r['reason']=='command_consumed']
                self.assertGreaterEqual(len(captured),3)
                self.assertEqual(len(activated),1)
                self.assertEqual(len(consumed),1)
                self.assertLess(context_events.index(activated[0]),context_events.index(consumed[0]))
                for row in context_events:
                    self.assertEqual(row['episode_id'],views[0]['episode_id'])
                    self.assertEqual(row['game_generation'],'native-'+views[0]['episode_id'])
                    self.assertEqual(row['player_id'],0)
                    self.assertEqual(row['turn'],views[0]['observation']['turn'])
                    self.assertIn(row['snapshot_count'],(0,1))
                    self.assertGreaterEqual(row['accounted_bytes'],0)
                    self.assertNotIn('observation',row)
                    self.assertNotIn('candidates',row)
                self.assertEqual(activated[0]['decision_id'],decisions['decision_id'])
                self.assertEqual(activated[0]['sequence'],views[1]['sequence'])
                event_fields=('stage','episode_id','game_generation','player_id','turn',
                              'decision_id','sequence','snapshot_count','accounted_bytes','reason')
                report['decision_context']={
                    'installed_path_exercised':True,
                    'snapshot_players':[0],
                    'other_player_views_did_not_create_or_replace_decisions':public_views,
                    'native_commands':len(activated),
                    'events':[{key:row[key] for key in event_fields if key in row}
                              for row in context_events],
                    'simultaneous_commands_qualified':False}
            self.assertFalse(any(x.split('.')[0] in ('civ6rl','tools','torch') for x in sys.modules))
            installed_keys=[k for k in backend.report['source_unchanged'] if str(installed) in k]
            self.assertGreater(len(installed_keys),400)
            closure_path=backend.run/'closure.json'
            if not closure_path.is_file():
                closure_path=next(backend.run.glob('*closure*.json'))
            closure=json.loads(closure_path.read_text())
            if prepared is not None:
                self.assertEqual(closure['prepared_capture'],prepared)
                self.assertEqual(closure['pins'][prepared['path']],prepared['sha256'])
                self.assertNotIn('parent_localization_validation',closure)
            if private_resources is not None:
                self.assertEqual(closure['private_resources'],private_resources)
                self.assertEqual(closure['pins'][private_resources['path']],private_resources['sha256'])
                # The production boundary must make the original proof root
                # unavailable after configuration, without renaming user data.
                with self.assertRaisesRegex(RuntimeError,'Historical resource read forbidden'):
                    (reference_root/'AGENTS.md').read_bytes()
                report['historical_resource_reads_forbidden']=True
            report['closure']=record(closure_path)
            report['closure_pin_entries']=len(closure['pins'])
            report.update(status='installed_backend_native_parity_verified',native_actions=1,
                installed_source_pins=len(installed_keys),
                backend_module=backend._session.__class__.__module__,
                installed_backend_file=record(Path(module.__file__)),
                source_map=record(installed/'civ6_host/runtime/source-map.json'),
                native_run=str(backend.run),supervisor=record(backend.run/'supervisor.json'),
                reset_timings_seconds=backend.report['reset_timings_seconds'],
                sampled_memory_peaks=backend.report['sampled_memory_peaks'],
                worker_reaped=True,lab_and_torch_imports_absent=True)
        except BaseException as exc:
            report.update(status='failed',error=repr(exc))
            raise
        finally:
            if client is not None:client.abort()
            elif backend is not None:backend.abort('extracted_runtime_test_failed')
            report['wall_seconds']=time.perf_counter()-started
            if backend is not None:
                report['backend_finished']=backend.finished
                if backend.report is not None and backend.run is not None:
                    report['supervisor']=record(backend.run/'supervisor.json')
            (out/'native-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({k:v for k,v in report.items() if k in ('status','error','wall_seconds','native_actions','worker_reaped')}),flush=True)


if __name__=='__main__':unittest.main()

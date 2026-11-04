"""Actual AST-adapted capture/provider plumbing with retained pure fixtures.

No GameCore, GUI, process observation or network call is made by these tests.
The caller-supplied CWD observer reports the synthetic fixture identity only.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import native as native_package
import civ6_host.runtime as runtime_package
from extraction_capture_script_paths import MODULES, parameterize


HOST=Path(__file__).resolve().parents[1]
PENDING=HOST/'work/xp2-official-capture-preparation/pending'
PROVIDER=HOST/'src/civ6_host/runtime/native/native_gameplay_source_capture.py'
COLLECTOR=HOST/'src/civ6_host/runtime/workers/capture_phase1_bundle994.py'


def load_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def adapted(name,path):
    raw=path.read_text(encoding='utf-8')
    # The same test runs before central extraction and on its final generated
    # output; never apply an extraction hook twice to a generated module.
    if 'script_path_context' not in raw:raw=parameterize(name,raw)
    module=ModuleType('_script_paths_integration_'+name.replace('.','_'))
    module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


class CaptureScriptPathIntegrationTests(unittest.TestCase):
    def setUp(self):
        active=HOST/'src/civ6_host/runtime/capture_script_paths.py'
        source=active if active.is_file() else PENDING/'capture_script_paths.py'
        fixture_source=HOST/'tests/test_capture_script_paths.py'
        if not source.is_file() or not fixture_source.is_file():
            self.skipTest('Private retained path-adapter fixtures absent')
        self.paths=load_file('_script_paths_integration_api',source)
        self.enterContext(patch.dict(sys.modules,{'capture_script_paths':self.paths,
            'civ6_host.runtime.capture_script_paths':self.paths}))
        self.enterContext(patch.object(runtime_package,'capture_script_paths',self.paths,create=True))
        fixtures=load_file('_script_paths_retained_fixtures',fixture_source)
        self.fixture=fixtures.CaptureScriptPathsTests()
        self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        f=self.fixture
        self.wrapper=dict(witness=dict(path=str(f.witness_path),bytes=f.witness_path.stat().st_size,
            sha256=__import__('hashlib').sha256(f.witness_path.read_bytes()).hexdigest()),process=dict(f.process))
        self.provider=adapted(MODULES[1],PROVIDER)
        self.enterContext(patch.dict(sys.modules,{
            'civ6_host.runtime.native.native_gameplay_source_capture':self.provider}))
        self.enterContext(patch.object(native_package,'native_gameplay_source_capture',self.provider,create=True))
        self.collector=adapted(MODULES[0],COLLECTOR)
        self.reader=Mock(side_effect=lambda identity:dict(process=dict(identity),cwd=str(f.cwd)))

    def capture_sources(self,name='captured',**extra):
        options=dict(roots=[self.fixture.game],deadline=time.monotonic()+10,
            script_path_context=self.wrapper,script_path_cwd_reader=self.reader)
        options.update(extra)
        output=self.fixture.root/name
        report=self.provider.capture_selected_sources([self.fixture.selected_name],output,**options)
        return report,output

    def test_real_provider_preserves_raw_name_and_separate_mapping_live_and_offline(self):
        report,output=self.capture_sources()
        self.assertEqual(report['selected_paths'],[self.fixture.selected_name])
        row=report['records'][0]
        self.assertEqual(row['source_path'],self.fixture.selected_name)
        self.assertEqual(row['resolved_path'],str(self.fixture.source.resolve()))
        self.assertEqual(report['path_resolution']['context'],self.wrapper)
        self.assertFalse(report['path_resolution']['load_admitted'])
        self.provider.recheck_selected_sources(report,output,deadline=time.monotonic()+10,
            script_path_context=self.wrapper,script_path_cwd_reader=self.reader)
        calls=self.reader.call_count
        with patch.object(self.paths,'load_context',side_effect=AssertionError('Old PID observed')):
            self.provider.recheck_selected_sources(report,output,deadline=time.monotonic()+10)
        self.assertEqual(self.reader.call_count,calls)
        forged=deepcopy(report);forged['records'][0]['resolved_path']=str(self.fixture.root/'same-name.lua')
        with self.assertRaises(ValueError):
            self.provider.recheck_selected_sources(forged,output,deadline=time.monotonic()+10)
        (output/row['copy']).write_bytes(b'changed retained copy')
        with self.assertRaises(ValueError):
            self.provider.recheck_selected_sources(report,output,deadline=time.monotonic()+10)

    def test_default_absolute_empty_and_relative_refusal_remain_explicit(self):
        p=self.provider;f=self.fixture
        with patch.object(self.paths,'load_context',side_effect=AssertionError('Opt-in context loaded')):
            absolute=p.capture_selected_sources([str(f.source)],f.root/'absolute',
                roots=[f.game],deadline=time.monotonic()+10)
            empty=p.capture_selected_sources([],f.root/'empty',roots=[],deadline=time.monotonic()+10)
            self.assertNotIn('path_resolution',absolute)
            self.assertNotIn('resolved_path',absolute['records'][0])
            self.assertEqual(empty['records'],[])
            with self.assertRaisesRegex(ValueError,'absolute resolved'):
                p.capture_selected_sources([f.selected_name],f.root/'unresolved',
                    roots=[f.game],deadline=time.monotonic()+10)
        with self.assertRaisesRegex(ValueError,'explicit script-path context'):
            p.capture_selected_sources([],f.root/'observer-only',roots=[],deadline=time.monotonic()+10,
                script_path_cwd_reader=self.reader)

    def prepare_collector(self):
        f=self.fixture;c=self.collector
        snapshot=dict(identity=dict(f.process))
        backend=SimpleNamespace(snapshot_process=lambda pid,deadline:deepcopy(snapshot))
        paths=dict(inbox=f.root/'Civ6RLInbox.lua',log=f.root/'Lua.log',save_directory=f.root,
            save=f.root/'Civ6RLLab_fixture.Civ6Save',output=f.root/'collector',
            installed_mod=f.root,exports={})
        for name,value in (('_paths',lambda **kw:paths),('_bridge_pins',lambda *a:{}),
            ('_tool_pins',lambda *a:{}),('_identity',lambda before,pid:before['identity']),
            ('_sole_process',lambda *a:[]),('_log_witness',lambda *a:{})):
            self.enterContext(patch.object(c,name,value))
        options=dict(pid=f.process['pid'],inbox=paths['inbox'],log=paths['log'],
            save_directory=f.root,name='Civ6RLLab_fixture',output=paths['output'],
            backend=backend,script_roots=[f.game],script_path_context=self.wrapper)
        return options,paths

    def test_preflight_checks_exact_process_roots_and_pins_without_calling_observer(self):
        options,_=self.prepare_collector();c=self.collector
        result=c.preflight(**options,script_path_cwd_reader=self.reader)
        self.assertEqual(result['script_path_resolution']['context'],self.wrapper)
        self.assertEqual(result['game_commands_sent'],0);self.reader.assert_not_called()
        wrong=deepcopy(self.wrapper);wrong['process']['creation_filetime']+=1
        with self.assertRaisesRegex(ValueError,'actual capture process'):
            c.preflight(**(options|dict(script_path_context=wrong)))
        for roots in ([],[self.fixture.cwd]):
            with self.subTest(roots=roots),self.assertRaises(ValueError):
                c.preflight(**(options|dict(script_roots=roots)))
        wrong=deepcopy(self.wrapper);wrong['witness']['sha256']='0'*64
        with self.assertRaises(ValueError):c.preflight(**(options|dict(script_path_context=wrong)))

    def test_capture_compares_selection_cwd_and_roots_before_any_database_read(self):
        c=self.collector;options,paths=self.prepare_collector()
        observation=dict(type='observation',player_id=0,turn=1,request_id='d'*32,sequence=1,
            observation=dict(units=[],cities=[],economy=dict(science=0,culture=0,gold=0,faith=0),
                             can_end_turn=True,blocker=0))
        client=SimpleNamespace(session='e'*32,timeout=1,connect=lambda:None,
            observe=lambda:deepcopy(observation),close=Mock())
        factory=lambda *a,**kw:client
        database=self.enterContext(patch.object(c,'capture_bundle',side_effect=RuntimeError('fixture DB boundary')))
        selection=self.enterContext(patch.object(c,'_capture_runtime_selections',return_value=dict(
            semantic=dict(selected_paths=['different-raw-selected-name.lua']))))
        kwargs=dict(expected_player_id=0,expected_turn=1,client_factory=factory,
                    script_path_cwd_reader=self.reader)
        with self.assertRaisesRegex(ValueError,'Raw selected script order'):
            c.capture(**options,**kwargs)
        database.assert_not_called();self.assertTrue(self.reader.called)
        # Each refusal owns a fresh capture output; no fixture overwrites one.
        paths['output']=self.fixture.root/'bad-cwd'
        self.reader.side_effect=lambda identity:dict(process=dict(identity),cwd=str(self.fixture.game))
        with self.assertRaises(ValueError):c.capture(**options,**kwargs)
        database.assert_not_called()
        paths['output']=self.fixture.root/'bad-roots'
        with self.assertRaises(ValueError):c.capture(**(options|dict(script_roots=[self.fixture.cwd])),**kwargs)
        database.assert_not_called()
        paths['output']=self.fixture.root/'bounded-source'
        with patch.object(self.provider,'MAX_FILE_BYTES',0),self.assertRaises(ValueError):
            c.capture(**options,**kwargs)
        database.assert_not_called()
        paths['output']=self.fixture.root/'valid-through-db'
        self.reader.side_effect=lambda identity:dict(process=dict(identity),cwd=str(self.fixture.cwd))
        selection.return_value=dict(semantic=dict(selected_paths=[self.fixture.selected_name]))
        with self.assertRaisesRegex(RuntimeError,'fixture DB boundary'):c.capture(**options,**kwargs)
        self.assertEqual(database.call_count,1)

    def test_cli_forwards_only_the_explicit_pinned_wrapper(self):
        c=self.collector
        with patch.object(c,'preflight',return_value=dict(status='fixture')) as preflight,patch('builtins.print'):
            result=c.main(['preflight','--pid',str(self.fixture.process['pid']),
                '--inbox','Civ6RLInbox.lua','--log','Lua.log','--save-directory','saves',
                '--output','capture','--name','Civ6RLLab_fixture',
                '--script-path-context',json.dumps(self.wrapper)])
        self.assertEqual(result,0)
        self.assertEqual(preflight.call_args.kwargs['script_path_context'],self.wrapper)

    def test_hook_refuses_changed_seams_and_double_application(self):
        from civ6_host.runtime.provenance import historical_source_file
        for name,relative in ((MODULES[0],'tools/capture_phase1_bundle994.py'),
                              (MODULES[1],'civ6rl/native_gameplay_source_capture.py')):
            raw=Path(historical_source_file(relative)).read_text(encoding='utf-8')
            transformed=parameterize(name,raw)
            compile(transformed,relative,'exec')
            with self.assertRaises(ValueError):parameterize(name,transformed)
        self.assertEqual(parameterize('unrelated.module','unchanged'),'unchanged')


if __name__=='__main__':unittest.main()

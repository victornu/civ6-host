"""Strict source/receipt fixtures for the selected BBG numeric display path."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import player_display_toppanel as display
from civ6_host.runtime.information_store import InformationStore
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.player_display import NativeTopPanelIssuer, PublicDisplayCache


class BBGPlayerDisplayTests(unittest.TestCase):
    CURRENT_CAPTURE=json.dumps({'path':'work/official-capture/bbg751-world-A-ui/manifest.json',
        'sha256':'0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d'})

    def current_capture_env(self):
        from civ6_host.runtime.xp2_bbg_inputs import CAPTURE_ENV
        return patch.dict(os.environ,{CAPTURE_ENV:self.CURRENT_CAPTURE})

    def historical_profile(self):
        return json.loads((self.root/display.BBG_PROFILE_RELATIVE).read_bytes())

    @classmethod
    def setUpClass(cls):
        cls.root=resource_root()
        cls.native_run=cls.root/'work/xp2-client-sessions/run-cf89b10843a744fd9296c7708ff755cd'
        manifest=next(cls.native_run.glob('native-init-fixtures-*/worker-00/manifest.json'))
        cls.manifest=json.loads(manifest.read_bytes())
        with (cls.native_run/'events.jsonl').open(encoding='utf-8') as stream:
            cls.frame=next(json.loads(line) for line in stream
                if json.loads(line).get('stage')=='official_session_response')

    def event(self):
        frame=self.frame
        # Explicit receipt fixture, not a native formatter witness.
        return dict(stage=display.STAGE,**{k:frame[k] for k in ('episode_id','game_generation','sequence')},
            player_id=frame['observation']['player_id'],turn=frame['observation']['turn'],
            source_sha256=display.BBG_SOURCE_SHA256,actor_channel=False,locale='fr_FR',
            provider_id=display.PROVIDER_ID,provider_sha256=display.BBG_PROVIDER_SHA256,
            raw_observation_sha256=display.digest(frame['observation']),
            response_binding_sha256=display.digest(frame),
            formatter_input_f64le=display._bits(display._inputs(frame)),
            top_panel_text=dict(science='+7,6',culture='+6,9',gold='381',faith='0,9'))

    def test_v8_is_explicit_and_v7_bytes_and_refusal_are_preserved(self):
        self.assertEqual(display.selected_source(),display.SOURCE_SHA256)
        self.assertEqual(display.selected_source(display.BBG_SOURCE_SHA256),display.BBG_SOURCE_SHA256)
        self.assertEqual(sha256((self.root/display.PROFILE_RELATIVE).read_bytes()).hexdigest(),display.SOURCE_SHA256)
        with self.assertRaisesRegex(ValueError,'dependency changed'):
            display.verify_source()
        with self.assertRaisesRegex(ValueError,'dependency changed'):
            display.verify_source(display.BBG_SOURCE_SHA256)
        source=self.historical_profile()
        self.assertEqual(source['initialized_localization']['input_profile'],'xp2-lan')
        self.assertFalse(source['initialized_localization']['bootstrap_metadata_except_private_icu_path']['dictionary_flag'])
        for bad in ('0'*64,True,1,{},''):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                display.selected_source(bad)

    def test_exact_runtime_class_matches_qualified_bbg_constructor(self):
        from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
        from civ6_host.runtime.xp2_bbg_nested_events import BBGNestedScriptRuntime, SOURCE
        self.assertIs(display._runtime_class(display.SOURCE_SHA256),NativeScriptRuntime)
        self.assertIs(display._runtime_class(display.BBG_V8_SOURCE_SHA256),NativeScriptRuntime)
        self.assertIs(display._runtime_class(display.BBG_SOURCE_SHA256),BBGNestedScriptRuntime)
        class UnqualifiedSubclass(BBGNestedScriptRuntime):pass
        self.assertIsNot(display._runtime_class(display.BBG_SOURCE_SHA256),UnqualifiedSubclass)
        source=self.historical_profile()
        deps={row['path']:row['sha256'] for row in source['source_dependencies']}
        for name in ('runtime/xp2_bbg_nested_events.py','runtime/xp1_saved_load_composition.py'):
            self.assertRegex(deps[name],r'^[0-9a-f]{64}$')
        self.assertTrue(any(row['path'].replace('\\','/')==SOURCE[0]
                            and row['sha256']==SOURCE[1] for row in source['admission_dependencies']))

    def test_exact_initialized_bundle_and_private_resources_are_required(self):
        source=self.historical_profile()
        host=SimpleNamespace(manifest=deepcopy(self.manifest),localization_connection=42)
        identity=display._initialized_locale(host,source)
        self.assertEqual(identity,(display.digest(self.manifest),42))
        mutations=(
            lambda m:m['localization_bootstrap'].update(dictionary_flag=True),
            lambda m:m['localization_bootstrap'].update(dictionary_flag=0),
            lambda m:m['localization_bootstrap'].update(locale='en_US'),
            lambda m:m.update(input_profile='lan'),
            lambda m:m['official_bundle'].update(sha256='0'*64),
            lambda m:m['databases']['localization'].update(sha256='0'*64),
            lambda m:m['localization_bootstrap']['icu_data'].update(path=str(self.root/'AGENTS.md')),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):
                bad=deepcopy(self.manifest);mutate(bad)
                display._initialized_locale(SimpleNamespace(manifest=bad,localization_connection=42),source)
        with self.assertRaises(ValueError):
            display._initialized_locale(SimpleNamespace(manifest=self.manifest,localization_connection=None),source)

    def test_closure_source_scope_and_every_pin_are_required(self):
        from civ6_host.runtime.execution_images import identity,known_path,select
        from civ6_host.runtime.xp2_bbg_inputs import registered_reference
        image=select(display.CURRENT_EXECUTION_PROFILE_ID,
                     core_path=known_path(display.CURRENT_EXECUTION_PROFILE_ID))
        with self.current_capture_env():
            closure=dict(input_profile='xp2-lan',official_bundle=registered_reference(),
                         execution_image=identity(image),pins={})
            display.pin_display_closure(closure,display.CURRENT_SOURCE_SHA256)
            display.require_display_closure(closure)
        bad=deepcopy(closure);bad['pins'].pop(next(iter(bad['pins'])))
        with self.assertRaises(ValueError):display.require_display_closure(bad)
        bad=deepcopy(closure);bad['public_display_source']=display.SOURCE_SHA256
        with self.assertRaises(ValueError):display.require_display_closure(bad)
        bad=deepcopy(closure);bad['official_bundle']={'path':'unselected','sha256':'0'*64}
        with self.current_capture_env(),self.assertRaises(ValueError):
            display.require_display_closure(bad)

    def test_current_formatter_is_explicit_and_bound_to_registered_image_capture(self):
        from civ6_host.runtime.execution_images import identity,known_path,select
        from civ6_host.runtime.xp2_bbg_inputs import registered_reference
        image=select(display.CURRENT_EXECUTION_PROFILE_ID,
                     core_path=known_path(display.CURRENT_EXECUTION_PROFILE_ID))
        self.assertEqual(display.selected_source(),display.SOURCE_SHA256)
        self.assertEqual(display.selected_source(display.CURRENT_SOURCE_SHA256),
                         display.CURRENT_SOURCE_SHA256)
        with self.current_capture_env():
            profile=display.verify_source(display.CURRENT_SOURCE_SHA256,execution_image=image)
        self.assertTrue(profile['static_only'])
        self.assertFalse(profile['native_execution'])
        self.assertFalse(profile['live_bridge_qualified'])
        self.assertEqual(profile['patterns'],self.historical_profile()['patterns'])
        with self.current_capture_env():
            closure=dict(input_profile='xp2-lan',official_bundle=registered_reference(),
                         execution_image=identity(image),pins={})
            display.pin_display_closure(closure,display.CURRENT_SOURCE_SHA256)
            display.require_display_closure(closure)
        bad=deepcopy(closure);bad.pop('execution_image')
        with self.current_capture_env(),self.assertRaisesRegex(ValueError,'explicit execution-image'):
            display.require_display_closure(bad)
        bad=deepcopy(closure);bad['official_bundle']={'path':'wrong','sha256':'0'*64}
        with self.current_capture_env(),self.assertRaises(ValueError):display.require_display_closure(bad)

    def test_current_initialized_locale_uses_bundle_fixture_not_historical_world(self):
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        from civ6_host.runtime.execution_images import known_path,select
        from civ6_host.runtime.xp2_bbg_inputs import registered_reference
        local=self.root/'work/host-prepared-captures/bbg751-world-A-current'
        package=json.loads((local/'manifest.json').read_bytes())
        with self.current_capture_env():reference=registered_reference()
        database=local/package['files']['database_localization']['path']
        icu=local/package['localization_bootstrap']['icu_data']['path']
        dbrow={'path':str(database),'sha256':package['files']['database_localization']['sha256'],
               'size_bytes':package['files']['database_localization']['bytes']}
        fixture=dict(input_profile='xp2-lan',official_bundle={'path':reference[0],
            'sha256':reference[1]},localization_bootstrap=deepcopy(package['localization_bootstrap']),
            databases={'localization':dbrow})
        bundle=PreparedBundle(reference,None,1,Path('current-core'),fixture,{}, {}, {})
        bootstrap=deepcopy(fixture['localization_bootstrap'])
        bootstrap['icu_data']['path']=str(icu)
        database_row=dict(path=str(database),sha256=dbrow['sha256'],size_bytes=dbrow['size_bytes'],
                          source_path=str(database),source_manifest_entry=deepcopy(dbrow))
        host=SimpleNamespace(manifest={'official_bundle':fixture['official_bundle'],
            'input_profile':'xp2-lan','localization_bootstrap':bootstrap,
            'databases':{'localization':database_row}},localization_connection=7)
        image=select(display.CURRENT_EXECUTION_PROFILE_ID,core_path=known_path(display.CURRENT_EXECUTION_PROFILE_ID))
        with self.current_capture_env():
            source=display.verify_source(display.CURRENT_SOURCE_SHA256,execution_image=image)
            self.assertEqual(display._initialized_locale(host,source,bundle)[1],7)
        bad=deepcopy(host.manifest);bad['official_bundle']={'path':'old','sha256':'0'*64}
        with self.assertRaises(ValueError):
            display._initialized_locale(SimpleNamespace(manifest=bad,localization_connection=7),source,bundle)
        bad=deepcopy(host.manifest);bad['localization_bootstrap']['dictionary_flag']=not bootstrap['dictionary_flag']
        with self.assertRaises(ValueError):
            display._initialized_locale(SimpleNamespace(manifest=bad,localization_connection=7),source,bundle)

    def test_store_consumer_and_cache_bind_native_receipt_to_exact_response(self):
        event=self.event();frame=deepcopy(self.frame)
        original=deepcopy(frame)
        display.validate_readback(event,frame,source_sha256=display.BBG_SOURCE_SHA256)
        store=InformationStore({'display':display.BBG_SOURCE_SHA256})
        issuer=NativeTopPanelIssuer(store);cache=PublicDisplayCache(issuer)
        store.ingest(event);store.ingest(frame)
        receipt=issuer.capture(frame,'fr_FR')
        public=cache.prepare(frame,'fr_FR',receipt)
        self.assertEqual(public['observation']['economy'],dict(science=7.6,culture=6.9,gold=381,faith=0.9))
        self.assertEqual(public['decisions'],frame['decisions'])
        self.assertEqual(frame,original)
        with self.assertRaises(ValueError):issuer.capture(frame,'fr_FR')
        with self.assertRaises(ValueError):display.validate_readback(event,frame)
        for field,value in (('sequence',frame['sequence']+1),('game_generation',frame['game_generation']+'-foreign')):
            bad=deepcopy(frame);bad[field]=value
            with self.assertRaises(ValueError):display.validate_readback(event,bad,source_sha256=display.BBG_SOURCE_SHA256)
        bad=deepcopy(event);bad['provider_sha256']=display.PROVIDER_SHA256
        with self.assertRaises(ValueError):display.validate_readback(bad,frame,source_sha256=display.BBG_SOURCE_SHA256)


if __name__=='__main__':unittest.main()

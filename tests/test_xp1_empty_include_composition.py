"""Pure composition and real empty-registry refusal checks; no native calls."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_saved_load_composition as composition
from civ6_host.runtime.native import native_official_bundle as bundle_module
from civ6_host.runtime.native import native_havok as havok_module
from civ6_host.runtime.native import native_script_runtime as runtime_module
from civ6_host.runtime.native import native_core_lock as lock_module
from civ6_host.runtime import saved_load_services as services_module
from civ6_host.runtime import xp1_saved_load_logger as logger_module
from civ6_host.runtime import xp1_load_capability as capability_module
from civ6_host.runtime import xp1_load_options as options_module
from civ6_host.runtime.script_context_service import ScriptContextService
from civ6_host.runtime.native.native_gameplay_script_registry import NativeGameplayScriptRegistry
from civ6_host.runtime.configuration_profiles import configuration_abi, XP1_CORE_SHA256


class EmptyIncludeCompositionTests(unittest.TestCase):
    def fixture(self):
        directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(directory.cleanup)
        root = Path(directory.name).resolve()
        (root/'HavokScript_FinalRelease.dll').write_bytes(b'offline-placeholder')
        profile = dict(selected_path_count=0, active_count=0, source_records=0,
                       source_files=0, selected_and_active_empty=True)
        fixture = dict(localization_bootstrap={}, databases={'localization': {'sha256': 'a'*64}})
        bundle = NS(reference=('manifest', 'b'*64), fixture=fixture,
                    content_profile={'gameplay_scripts': profile})
        host = NS(manifest=deepcopy(fixture), localization_initialized=True,
                  dll_directory=root, execution_lock=None)
        backend = NS(check_thread=Mock(), _saved_load_candidate=True, stage='prepared',
            prefix=None, game_flag=Mock(return_value=0), inputs=NS(map_values=(('MAP_SIZE',1),),configuration=b'fixture-config'),
            configuration_abi=configuration_abi(XP1_CORE_SHA256),
            captured_bundle=bundle, fixture=root/'fixture.json', host=host,
            emit=Mock(), context=1, core=object())
        child = object()
        runtime = NS(bind_core_services=Mock(), acquire=Mock(return_value=child),
            attach_standard_libraries=Mock(), namespaces=NS(register=Mock()),
            bind_native_game_api=Mock(), attach_game_events=Mock(),
            set_include_sources=Mock(side_effect=AssertionError('empty include snapshot must not be configured')),
            attach_include=Mock(side_effect=AssertionError('empty include loader must not be installed')))
        consumer = NS(enable_controller_events=Mock(), enable_notification_scopes=Mock(),
                      enable_player_queries=Mock())
        arguments = NS(install_consumers=Mock(return_value=consumer))
        services = NS(events=NS(), install_application_mirror=Mock(),
            install_deferred_events=Mock(return_value=NS()), install_control_inputs=Mock(return_value=NS()),
            install_event_arguments=Mock(return_value=arguments), install_status_messages=Mock(),
            install_cache_facades=Mock(), install_player_queries=Mock(return_value=NS()),
            install_postload_aux90_null=Mock())
        kernel = NS(GetModuleHandleW=Mock(return_value=100))
        scripts = dict(selected_paths=[], records=[], files={})
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(composition, 'validate_candidate_inputs'))
        stack.enter_context(patch.object(composition, 'validate_private_bootstrap'))
        stack.enter_context(patch.object(bundle_module, 'validate_fixture'))
        stack.enter_context(patch.object(bundle_module, '_manifest', return_value=(bundle.reference, {'selected_gameplay_sources': {'manifest': {}}})))
        read = stack.enter_context(patch.object(bundle_module, '_file', side_effect=lambda *a,**k:json.dumps(scripts).encode()))
        stack.enter_context(patch.object(havok_module, 'HAVOK_SHA256', hashlib.sha256(b'offline-placeholder').hexdigest()))
        dll = stack.enter_context(patch.object(composition.C, 'WinDLL', side_effect=lambda name,**kwargs:kernel if name=='kernel32' else object()))
        ctor = stack.enter_context(patch.object(runtime_module, 'NativeScriptRuntime', return_value=runtime))
        stack.enter_context(patch.object(lock_module, 'NativeCoreLock', return_value=object()))
        logger = stack.enter_context(patch.object(logger_module, 'install_saved_load_logger'))
        capability = stack.enter_context(patch.object(capability_module, 'install_saved_load_capabilities'))
        options = stack.enter_context(patch.object(options_module, 'install_saved_load_options'))
        compose = stack.enter_context(patch.object(services_module, 'SavedLoadServices', return_value=services))
        return NS(backend=backend, runtime=runtime, child=child, services=services,
                  compose=compose, constructor=ctor, dll=dll, scripts=scripts, read=read, logger=logger, capability=capability, options=options)

    def test_empty_capture_preserves_libraries_api_events_and_refuses_bootstrap(self):
        f = self.fixture()
        self.assertIs(composition.compose_saved_load_services(f.backend), f.services)
        f.runtime.bind_core_services.assert_called_once_with(f.backend.host,f.backend.context)
        f.logger.assert_called_once_with(f.backend)
        f.capability.assert_called_once_with(f.backend)
        f.options.assert_called_once_with(f.backend)
        f.runtime.attach_standard_libraries.assert_called_once_with(f.child)
        f.runtime.bind_native_game_api.assert_called_once()
        f.runtime.attach_game_events.assert_called_once_with(f.child)
        f.runtime.set_include_sources.assert_not_called()
        f.runtime.attach_include.assert_not_called()
        f.services.install_postload_aux90_null.assert_called_once()
        registry = f.compose.call_args.args[3]
        self.assertEqual(registry.count(), 0)
        self.assertEqual(registry.paths, ())
        with self.assertRaisesRegex(ValueError, 'cannot create a script context'):
            f.compose.call_args.kwargs['bootstrap'](object(), b'unexpected')

    def test_nonempty_or_malformed_active_capture_refuses_before_runtime(self):
        f = self.fixture()
        profile = f.backend.captured_bundle.content_profile['gameplay_scripts']
        for field, value in (('active_count',1), ('active_count',False),
                             ('selected_path_count',1), ('selected_and_active_empty',False),
                             ('source_records',1), ('source_files',1)):
            original = profile[field]; profile[field] = value
            with self.assertRaisesRegex(ValueError, 'empty selected and active'):
                composition.compose_saved_load_services(f.backend)
            profile[field] = original
        f.constructor.assert_not_called(); f.dll.assert_not_called()

    def test_missing_or_nonempty_captured_sources_refuse_before_runtime(self):
        f = self.fixture()
        for field, value in (('selected_paths',['script.lua']), ('records',[{}]),
                             ('files',{'script.lua':{}}), ('records',None)):
            original = f.scripts[field]; f.scripts[field] = value
            with self.assertRaisesRegex(ValueError, 'empty selected and active'):
                composition.compose_saved_load_services(f.backend)
            f.scripts[field] = original
        f.constructor.assert_not_called(); f.dll.assert_not_called()

    def test_real_empty_context_service_rejects_acquire_and_load_without_bootstrap(self):
        service = ScriptContextService.__new__(ScriptContextService)
        service.registry = NativeGameplayScriptRegistry((), selected_scripts=())
        self.addCleanup(service.registry.close)
        service.paths, service.sources = (), {}
        service.wire_paths, service.wire_sources = (), {}
        service.receiver = 123
        service.closed = service.quarantined = False
        service.host = NS(_script_context_service=service)
        service.runtime = NS(registry=NS(_check=Mock()), execute=Mock())
        service.bootstrap, service.lifetime = Mock(), NS(acquire=Mock())
        self.assertEqual(service.script_count(123), 0)
        self.assertIsNone(service.script_path(123, 0))
        for name in (b'', b'Unexpected'):
            with self.assertRaisesRegex(ValueError, 'Unqualified script context'):
                service.acquire(123, name, 0)
        raw = 'Unexpected.lua'.encode('utf-16-le') + b'\0\0'
        service.read = lambda address,size: raw[address-1000:address-1000+size]
        with self.assertRaisesRegex(ValueError, 'Unresolved or unselected'):
            service.load(123, 999, 1000)
        service.bootstrap.assert_not_called()
        service.lifetime.acquire.assert_not_called()
        service.runtime.execute.assert_not_called()

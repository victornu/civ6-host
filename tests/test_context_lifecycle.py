"""Shared lifecycle dispatch/ownership tests; native execution is separate."""
import ctypes as C
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native import native_host as host
from civ6_host.runtime.native import native_checkpoint_configuration_only as config
from civ6_host.runtime.native import native_checkpoint_load as load
from civ6_host.runtime.native import native_core_context_profiles as profiles
from civ6_host.runtime.native import native_xp1_context_init as xp_init
from civ6_host.runtime.native import native_xp1_teardown_adapter as xp_close
from civ6_host.runtime.native import native_probe


def profile():
    return profiles.NativeCoreContextProfile('xp1','context',Path('xp1.dll'),XP1_CORE_SHA256,
        1,2,3,b'abc',4,b'def',Path('.').resolve(),{})


class ContextLifecycleTests(unittest.TestCase):
    def test_unknown_or_forged_profile_refuses_before_database_calls(self):
        core=SimpleNamespace(_name='xp1.dll')
        for value in (object(),replace(profile(),mode='init'),replace(profile(),ruleset='xp2')):
            with patch.object(host.C,'WinDLL') as dll:
                with self.assertRaises(ValueError):
                    host.initialize_context(core,1,'manifest','.',lambda *a,**k:None,context_profile=value)
                dll.assert_not_called()
        with patch.object(profiles,'profile_for_core',return_value=replace(profile(),destroy_context_rva=99)), \
             patch.object(host.C,'WinDLL') as dll:
            with self.assertRaisesRegex(ValueError,'differs'):
                host.initialize_context(core,1,'manifest','.',Mock(),context_profile=profile())
            dll.assert_not_called()

    def test_xp1_lifecycle_preserves_init_teardown_order_and_no_base_services(self):
        selected=profile();events=[];core=SimpleNamespace(_name='xp1.dll',_handle=100)
        database=SimpleNamespace()
        setattr(database,'?Initialize@Database@@YA_NXZ',Mock(return_value=True))
        setattr(database,'?Shutdown@Database@@YA_NXZ',Mock(return_value=True))
        adapter=SimpleNamespace(log_writers=SimpleNamespace(enable_native_sink=Mock(),close=Mock()))
        manifest={'databases':{'configuration':{'path':'config.db','sha256':host.DATABASE_SHA256},
                               'gameplay':{'path':'game.db','sha256':host.DATABASE_SHA256}}}
        def make_host(*args):
            self.assertIsNone(args[3])
            events.append('host')
            return adapter
        def initialize(*args,**kwargs):
            self.assertIs(core._diagnostic_host,adapter)
            self.assertFalse(hasattr(adapter,'event_recorder'))
            events.append('init')
            return {'installed_inputs':'diagnostic'}
        def teardown(*args,**kwargs):
            self.assertEqual(args[3],{'installed_inputs':'diagnostic'})
            events.append('teardown')
            return {'installed':True}
        with patch.object(profiles,'profile_for_core',return_value=selected), \
             patch.object(host,'validate_fixture',return_value=manifest), \
             patch.object(host,'sha256',return_value=host.DATABASE_SHA256), \
             patch.object(host.C,'WinDLL',return_value=database), \
             patch.object(host,'DiagnosticHost',side_effect=make_host), \
             patch.object(host,'virtual',side_effect=AssertionError('Base virtual dispatch')), \
             patch.object(xp_init,'initialize_xp1_context',side_effect=initialize), \
             patch.object(xp_close,'install_xp1_teardown_callbacks',side_effect=teardown), \
             patch.object(native_probe,'Windows',return_value=SimpleNamespace(modules=lambda:[])):
            actual=host.initialize_context(core,1,'manifest','.',Mock(),context_profile=selected)
            self.assertIs(actual,adapter)
            self.assertEqual(events,['host','init','teardown'])
            self.assertTrue(host.finish_database(actual,Mock()))
            self.assertTrue(adapter.log_writers.close.called)

    def test_backend_forwards_engine_to_init_and_clone(self):
        backend=config._NativeBackend.__new__(config._NativeBackend)
        backend.core=SimpleNamespace();backend.context=1;backend.fixture='manifest'
        backend.dll_directory='shared';backend.profile=profile();backend.emit=Mock()
        adapter=SimpleNamespace();owner=SimpleNamespace()
        with patch.object(config,'initialize_context',return_value=adapter) as init, \
             patch.object(config,'NativeApplicationConfiguration',return_value=owner) as clone:
            backend.initialize();backend.clone()
            init.assert_called_once_with(backend.core,1,'manifest','shared',backend.emit,context_profile=backend.profile)
            clone.assert_called_once_with(backend.core,1,emit=backend.emit,core_sha256=XP1_CORE_SHA256)
            self.assertIs(adapter.application_configuration,owner)
            self.assertIs(backend.core._civ6rl_application_configuration,owner)

    def test_restore_does_not_substitute_base_sidecar_for_xp1(self):
        backend=config._NativeBackend.__new__(config._NativeBackend)
        backend.profile=profile();backend.core=object();backend.context=1;backend.owner=object()
        with patch.object(config.provider,'restore_provider') as restore:
            with self.assertRaisesRegex(ValueError,'explicit input digest'):backend.restore(b'data')
            restore.assert_not_called()
            backend.restore(b'data',expected_sha256='1'*64)
            self.assertEqual(restore.call_args.kwargs['expected_sha256'],'1'*64)
            backend.profile=replace(profile(),ruleset='base')
            backend.restore(b'data')
            self.assertEqual(restore.call_args.kwargs['expected_sha256'],config.SIDECAR_SHA)

    def test_destroy_refuses_missing_teardown_or_live_provider(self):
        backend=config._NativeBackend.__new__(config._NativeBackend)
        backend.profile=profile();backend.owner=None;backend.host=SimpleNamespace()
        backend.destroy=Mock();backend.emit=Mock();backend.context=1
        with self.assertRaisesRegex(ValueError,'verified teardown'):backend.destroy_context()
        backend.host.context_teardown_receipt={'installed':True}
        backend.owner=SimpleNamespace(closed=False)
        with self.assertRaisesRegex(ValueError,'provider closed'):backend.destroy_context()
        backend.destroy.assert_not_called()
        backend.owner.closed=True;backend.destroy_context()
        backend.destroy.assert_called_once_with(1)
        self.assertTrue(backend.destroyed)

    def test_saved_game_admission_remains_separate(self):
        with patch.object(config._NativeBackend,'__init__') as parent:
            with self.assertRaisesRegex(ValueError,'Expansion saved Load is not admitted'):
                load.NativeLoadBackend(None,None,None,None,profile(),{},None)
            parent.assert_not_called()


if __name__=='__main__':unittest.main()

"""Engine selection only; Lua native registration has a separate live gate."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.native import native_host, native_probe, native_xp1_script_bindings


class ScriptEngineDispatchTests(unittest.TestCase):
    def runtime(self):
        return SimpleNamespace(root=11,registry=SimpleNamespace(validate=Mock(return_value=22)),
            host=SimpleNamespace(LAB_ScriptCoreBindingsInstall=Mock(return_value=0)),
            lua={'gettop':lambda pointer:0},_status=Mock(),emit=Mock())

    def test_base_default_retains_its_binding_signature_and_target(self):
        runtime=self.runtime();core=SimpleNamespace(_handle=0x1000)
        with patch.object(native_host,'virtual',return_value=Mock(return_value=0x2000)) as virtual:
            result=NativeScriptRuntime.bind_native_game_api(runtime,'child',33,core)
            self.assertIsNone(result)
            self.assertEqual(virtual.call_args.args[2:4],(0x68,0x42E180))
            runtime.host.LAB_ScriptCoreBindingsInstall.assert_called_once_with(11,22,0x2000,0x1000)
            self.assertEqual(runtime.emit.call_args.kwargs['method_rva'],'0x43bce0')

    def test_xp1_uses_existing_source_checked_binder(self):
        runtime=self.runtime();core=object();runtime.host.LAB_XP1ScriptCoreBindingsInstall=Mock()
        modules=['core','hks'];receipt={'returned':True,'complete_api_verified':False}
        with patch.object(native_probe,'Windows',return_value=SimpleNamespace(modules=lambda:modules)), \
             patch.object(native_xp1_script_bindings,'bind_xp1_game_api',return_value=receipt) as binder, \
             patch.object(native_host,'virtual') as virtual:
            result=NativeScriptRuntime.bind_native_game_api(runtime,'child',33,core,core_sha256=XP1_CORE_SHA256)
            self.assertIs(result,receipt)
            binder.assert_called_once_with(runtime,'child',33,core,
                project_root=resource_root(),module_paths=modules)
            virtual.assert_not_called()
            runtime.host.LAB_ScriptCoreBindingsInstall.assert_not_called()

    def test_xp1_missing_export_and_unknown_engine_refuse_before_native_calls(self):
        for engine in (XP1_CORE_SHA256,XP2_CORE_SHA256,'0'*64,None):
            runtime=self.runtime()
            with patch.object(native_host,'virtual') as virtual, \
                 patch.object(native_xp1_script_bindings,'bind_xp1_game_api') as binder, \
                 patch.object(native_probe,'Windows') as windows:
                with self.assertRaises(ValueError):
                    NativeScriptRuntime.bind_native_game_api(runtime,'child',33,object(),core_sha256=engine)
                virtual.assert_not_called();binder.assert_not_called();windows.assert_not_called()
                runtime.registry.validate.assert_not_called()

    def test_explicit_base_and_default_follow_same_call_path(self):
        calls=[]
        for kwargs in ({},{'core_sha256':BASE_CORE_SHA256}):
            runtime=self.runtime();core=SimpleNamespace(_handle=0x1000)
            with patch.object(native_host,'virtual',return_value=lambda context:0x2000):
                NativeScriptRuntime.bind_native_game_api(runtime,'child',33,core,**kwargs)
            calls.append((runtime.host.LAB_ScriptCoreBindingsInstall.call_args,runtime.emit.call_args))
        self.assertEqual(*calls)


if __name__=='__main__':unittest.main()

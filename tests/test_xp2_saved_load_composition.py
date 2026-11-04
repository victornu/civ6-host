"""Exact WorldCongress selection through the real saved-service owner graph.

Only native allocation/runtime/source-preflight boundaries are replaced. The
SavedLoadServices, script/scalar/map/event/context, deferred/controller/A0 owners,
capture selection, shared control snapshot and callback tables remain real.
No source bytes or game execution are represented by the fixture callbacks.
"""
from contextlib import ExitStack
from copy import deepcopy
import ctypes as C
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import captured_saved_load, xp1_saved_load_composition as composition
from civ6_host.runtime import xp2_bundle_inputs as inputs
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.control_input_service import ControlInputService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.a0_family_service import A0FamilyService
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.native.native_gameplay_script_registry import NativeGameplayScriptRegistry
from civ6_host.runtime import core_script_services, xp2_saved_script_services
import test_xp2_saved_script_services as script_fixtures
import test_xp2_preload_services as preload_fixtures
from test_xp2_saved_script_services import _Lifetime, _Notification
from test_control_input_service import Code


class XP2SavedLoadComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=inputs.consume_input_handoff(dict(
            path=str(resource_root()/'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'),
            sha256='6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020'))

    def fixture(self):
        f=script_fixtures.XP2SavedScriptServicesTests.fixture(self)
        _,root,_,_,order,host,runtime,backend,_,factory=f
        preload_fixtures.XP2PreloadServices.memory(self)
        host.pointer=123
        host.vtable=(C.c_void_p*64)()
        host._unsupported=DiagnosticHost._unsupported.__get__(host)
        host.configure_local_player_id=DiagnosticHost.configure_local_player_id.__get__(host)
        def check(receiver):
            if receiver!=host.pointer:raise ValueError('Foreign receiver')
        host._check=check
        for table,name in ((host.vtable,'host'),(host.aux_vtable,'auxiliary')):
            for slot in range(0,len(table)*8,8):
                host._bind(table,slot,None,[C.c_void_p],host._unsupported(name,slot))
        before=dict(host._slot_bindings)
        host.manifest=deepcopy(self.bundle.fixture)
        host.localization_initialized=True;host.execution_lock=None;host.dll_directory=root
        (root/'HavokScript_FinalRelease.dll').write_bytes(b'bounded-offline-HKS-placeholder')
        host.application_configuration=backend.owner=NS()
        backend.core=NS(_handle=self.base,_name=str(root/'GameCore_XP2_FinalRelease.dll'));backend.context=self.context
        backend.runtime.read=self.read
        backend.captured_bundle=self.bundle;backend.inputs=self.bundle.inputs
        backend._saved_load_candidate=True;backend.stage='prepared';backend.prefix=None
        backend.fixture=root/'fixture.json';backend.check_thread=Mock();backend.game_flag=Mock(return_value=0)
        runtime.children.clear();runtime.registry.contexts.clear()
        acquire=runtime.acquire
        def acquire_bound():
            core_script_services.check_bound(runtime,backend.context,backend.core)
            return acquire()
        runtime.acquire=Mock(wraps=acquire_bound)
        runtime.database_bound=runtime.configuration_bound=runtime.locale_bound=False
        runtime.service_owner=None;runtime.lua={'gettop':lambda _pointer:0}
        def status(_root,value,_label):
            if value!=0:raise RuntimeError('fixture native binding failed')
        runtime._status=status;runtime.emit=Mock()
        for name in ('LAB_ParameterDatabaseBind','LAB_DBConfigurationBorrow','LAB_LocaleBind'):
            setattr(runtime.host,name,Mock(return_value=0))
        for field,name,address in (('database','DatabaseDLL_FinalRelease.dll',0x30000000),
                                   ('localization_library','Localization_FinalRelease.dll',0x31000000)):
            path=root/name;path.write_bytes(b'fixture DLL identity')
            setattr(host,field,NS(_name=str(path),_handle=address))
        def bind_core(native_host,context,*,core_library=None,core_sha256=None):
            if native_host is not host or context!=backend.context or core_library is not backend.core or core_sha256!=composition.XP2_CORE_SHA256:
                raise ValueError('XP2 composition requires explicit profiled borrowed services')
            return NativeScriptRuntime.bind_core_services(runtime,native_host,context,
                core_library=core_library,core_sha256=core_sha256)
        runtime.bind_core_services=Mock(wraps=bind_core)
        runtime.bind_native_game_api=Mock(wraps=NativeScriptRuntime.bind_native_game_api.__get__(runtime))
        kernel=NS(GetModuleHandleW=Mock(return_value=100));executable=object();havok=object();lock=object()
        def dll(name,**kwargs):
            if name=='kernel32':return kernel
            if name=='':
                self.assertEqual(kwargs,{'handle':100});return executable
            self.assertEqual(name,str(root/'HavokScript_FinalRelease.dll'));return havok
        stack=ExitStack();self.addCleanup(stack.close)
        def stub(name,**kwargs):return stack.enter_context(patch(name,**kwargs))
        # Inputs and selected script reader use their real captured artifacts.
        stub('civ6_host.runtime.native.native_official_bundle.validate_fixture')
        stub('civ6_host.runtime.xp1_saved_load_composition.validate_private_bootstrap')
        stub('civ6_host.runtime.native.native_havok.HAVOK_SHA256',new=hashlib.sha256(b'bounded-offline-HKS-placeholder').hexdigest())
        native_dll=Mock(side_effect=dll)
        # Do not replace ctypes.WinDLL globally: source path verification needs
        # the real read-only Windows file-attribute API while composing.
        stub('civ6_host.runtime.xp1_saved_load_composition.C',
             new=NS(WinDLL=native_dll,c_wchar_p=C.c_wchar_p,c_void_p=C.c_void_p,addressof=C.addressof))
        runtime_ctor=stub('civ6_host.runtime.native.native_script_runtime.NativeScriptRuntime',return_value=runtime)
        lock_ctor=stub('civ6_host.runtime.native.native_core_lock.NativeCoreLock',return_value=lock)
        installers={name:stub('civ6_host.runtime.'+module+'.'+name) for module,name in (
            ('xp1_saved_load_logger','install_saved_load_logger'),
            ('xp1_load_capability','install_saved_load_capabilities'),
            ('xp1_load_options','install_saved_load_options'))}
        def mirror_boundary(host,core,context,emit,*,core_sha256):
            from civ6_host.runtime.application_mirror_profiles import mirror_abi
            abi=mirror_abi(core_sha256)
            self.assertEqual(abi.configuration.core_sha256,composition.XP2_CORE_SHA256)
            return NS(abi=abi)
        mirror=stub('civ6_host.runtime.native.native_application_mirror.NativePlayerApplicationMirror',side_effect=mirror_boundary)
        # Keep prepare/commit/check_bound and both service consumers real. Only
        # the process/module/native memory boundaries use fixture values.
        selected=NS(ruleset='xp2',core_sha256=composition.XP2_CORE_SHA256,shared_dependency_directory=root)
        stub('civ6_host.runtime.native.native_core_context_profiles.profile_for_core',return_value=selected)
        stub('civ6_host.runtime.native.native_core_context_profiles.validate_loaded_modules')
        stub('civ6_host.runtime.native.native_probe.Windows',return_value=NS(modules=lambda:[]))
        stub('civ6_host.runtime.native.native_setup.local_reader',return_value=backend.runtime.read)
        stub('civ6_host.runtime.profile_script_binding._current_executable',return_value=root/'fixture-host.exe')
        stub('civ6_host.runtime.profile_script_binding.verify_source_build',return_value={'host_sha256':'fixture'})
        inspect_services=stub('civ6_host.runtime.core_script_services._inspect',return_value=(self.inner,0x32000000,0x33000000))
        def register_api(actual_runtime,child,context,core,*,core_sha256):
            self.assertIs(actual_runtime,runtime);runtime.registry.validate(child)
            self.assertEqual(core_sha256,composition.XP2_CORE_SHA256)
            return core_script_services.check_bound(runtime,context,core)
        profile_bind=stub('civ6_host.runtime.profile_script_binding.bind_game_api',side_effect=register_api)
        verify=stub('civ6_host.runtime.xp2_saved_script_services.verify_services',wraps=xp2_saved_script_services.verify_services)
        stub('civ6_host.runtime.xp2_saved_script_services.verify_live',return_value={'events':{'fixture_preflight':True}})
        stub('civ6_host.runtime.script_event_state.ActiveEventStates',return_value=NS(accepts=Mock(return_value=False),close=Mock()))
        stub('civ6_host.runtime.saved_load_services.MapArgumentFactory',return_value=factory)
        stub('civ6_host.runtime.native.native_aux_map_adapter.NativeAuxMapAdapter.install',autospec=True,
             side_effect=lambda adapter:setattr(adapter,'_installed',True))
        stub('civ6_host.runtime.script_event_mutable_map.MutableMapResultDispatcher',return_value=NS(poisoned=False,close=Mock()))
        stub('civ6_host.runtime.script_context_service.RetainedScriptContexts',new=_Lifetime)
        stub('civ6_host.runtime.script_context_service.NativeContextNotification',new=_Notification)
        stub('civ6_host.runtime.control_input_service.NativeControllerCode',new=Code)
        stub('civ6_host.runtime.native.native_controller_state.NativeControllerCode',new=Code)
        # Any accidental widening must fail even before installing a callback.
        excluded={name:stub('civ6_host.runtime.saved_load_services.SavedLoadServices.'+name,
                           side_effect=AssertionError('XP2 excluded owner '+name)) for name in (
            'install_status_messages','install_cache_facades','install_player_queries','install_postload_aux90_null')}
        return NS(backend=backend,host=host,runtime=runtime,order=order,before=before,installers=installers,
                  runtime_ctor=runtime_ctor,lock_ctor=lock_ctor,lock=lock,mirror=mirror,verify=verify,
                  native_dll=native_dll,havok=havok,executable=executable,excluded=excluded,
                  profile_bind=profile_bind,inspect_services=inspect_services)

    def test_exact_worldcongress_same_runtime_child_and_shared_fifo_graph(self):
        f=self.fixture();b=f.backend
        services=composition.compose_saved_load_services(b)
        self.assertIs(type(services),SavedLoadServices)
        child=services.game_child
        self.assertEqual(f.runtime.acquire.call_count,1)
        self.assertIs(f.runtime.registry.contexts[child.pointer],child)
        self.assertIs(services.game_child,child);self.assertIs(services.runtime,f.runtime)
        self.assertIs(services.backend,b);self.assertIs(services.host,f.host)
        self.assertIs(f.host._saved_load_services,services);self.assertIs(f.host.execution_lock,f.lock)
        f.runtime_ctor.assert_called_once_with(f.havok,f.executable,services.emit)
        f.runtime.bind_core_services.assert_called_once_with(f.host,b.context,
            core_library=b.core,core_sha256=composition.XP2_CORE_SHA256)
        f.runtime.bind_native_game_api.assert_called_once_with(child,b.context,b.core,core_sha256=composition.XP2_CORE_SHA256)
        f.profile_bind.assert_called_once_with(f.runtime,child,b.context,b.core,core_sha256=composition.XP2_CORE_SHA256)
        lease=core_script_services.check_bound(f.runtime,b.context,b.core)
        self.assertIs(type(lease),core_script_services.BorrowedCoreServices)
        self.assertIs(lease.owner,f.host);self.assertIs(lease.core,b.core);self.assertIs(lease.runtime,f.runtime)
        self.assertEqual((lease.configuration,lease.gameplay),(0x32000000,0x33000000))
        f.runtime.host.LAB_ParameterDatabaseBind.assert_called_once_with(f.runtime.root,f.host.database._handle,lease.gameplay)
        f.runtime.host.LAB_DBConfigurationBorrow.assert_called_once_with(f.runtime.root,f.host.database._handle,lease.configuration)
        f.runtime.host.LAB_LocaleBind.assert_called_once_with(f.runtime.root,f.host.localization_library._handle)
        f.runtime.attach_standard_libraries.assert_called_once_with(child)
        f.runtime.attach_game_events.assert_called_once_with(child)
        self.assertEqual(f.runtime.namespaces.register.call_args_list,
                         [unittest.mock.call(child,name) for name in ('DB','GameInfo','GlobalParameters','Path','Locale')])
        f.lock_ctor.assert_called_once_with(f.host,f.executable)
        f.verify.assert_called_once_with(b,f.runtime,b.runtime.read)
        f.mirror.assert_called_once_with(f.host,b.core,b.context,services.emit,core_sha256=composition.XP2_CORE_SHA256)
        for installer in f.installers.values():installer.assert_called_once_with(b)
        self.assertIs(type(services.contexts.registry),NativeGameplayScriptRegistry)
        self.assertEqual(services.contexts.wire_paths,inputs.SELECTED_PATHS)
        self.assertEqual(len(services.contexts.sources),1)
        path=services.contexts.wire_sources[inputs.SELECTED_PATHS[0]]
        self.assertEqual(hashlib.sha256(services.contexts.sources[path]).hexdigest(),inputs.SCRIPT_SHA256)
        self.assertTrue(b._saved_script_dependencies)
        for owner in (services.scalars,services.maps,services.events,services.contexts):
            self.assertIs(owner.runtime,f.runtime)
        deferred,control,arguments=services.deferred_events,services.control_inputs,services.event_arguments
        self.assertIs(type(deferred),DeferredService);self.assertIs(type(control),ControlInputService)
        self.assertIs(type(arguments),EventArgumentService);self.assertIs(type(arguments.consumer),A0FamilyService)
        self.assertIs(control.deferred,deferred);self.assertIs(arguments.deferred,deferred)
        self.assertIs(arguments.consumer.deferred,deferred);self.assertIs(arguments.consumer.pending,deferred.pending)
        self.assertIs(arguments.consumer.controller_owner,control)
        self.assertIs(control.turn_begin_state,deferred.turn_begin_state)
        self.assertIs(arguments.consumer.turn_begin_state,deferred.turn_begin_state)
        self.assertEqual(control.local_player_id,0)
        for table,slot,result,args in (
            (f.host.vtable,0xA0,C.c_int32,(C.c_void_p,C.c_uint32,C.c_void_p)),
            (f.host.vtable,0xB0,C.c_int32,(C.c_void_p,C.c_uint32,C.c_uint64)),
            (f.host.vtable,0xD0,C.c_uint32,(C.c_void_p,)),
            (f.host.vtable,0xE8,None,(C.c_void_p,C.c_uint32)),
            (f.host.vtable,0xF0,None,(C.c_void_p,C.c_uint32)),
            (f.host.vtable,0x120,C.c_uint8,(C.c_void_p,)),
            (f.host.aux_vtable,0x00,C.c_void_p,(C.c_void_p,C.c_char_p,C.c_uint8)),
            (f.host.aux_vtable,0x18,C.c_uint8,(C.c_void_p,C.c_void_p,C.c_void_p))):
            address=table[slot//8]
            function=next(fn for fn in f.host.functions if C.cast(fn,C.c_void_p).value==address)
            self.assertIs(function.restype,result)
            self.assertEqual(function.argtypes,args)
        self.assertIsNone(services.backend.prefix)
        captured_saved_load.attach_services(b,services)
        self.assertIs(b.prefix,services);self.assertEqual(b.stage,'prefix-installed')
        snapshot=captured_saved_load.control_snapshot(b,empty=True)
        self.assertEqual(snapshot['pending_count'],0);self.assertFalse(snapshot['actions_admitted'])
        deferred.cache_update(f.host.pointer,7,9)
        self.assertEqual(captured_saved_load.control_snapshot(b,empty=False)['pending_count'],1)
        with self.assertRaisesRegex(RuntimeError,'fully consumed'):
            captured_saved_load.control_snapshot(b,empty=True)

    def test_selected_context_loads_real_snapshot_on_same_runtime_and_refuses_unknown(self):
        f=self.fixture();services=composition.compose_saved_load_services(f.backend);ctx=services.contexts
        self.assertEqual(ctx.script_count(ctx.receiver),1)
        with self.assertRaisesRegex(ValueError,'context name'):
            ctx.acquire(ctx.receiver,b'MissingScript',0)
        pointer=ctx.acquire(ctx.receiver,b'WorldCongress',0)
        child=ctx.lifetime._contexts[pointer]
        self.assertIs(ctx.lifetime.runtime,f.runtime)
        f.runtime.attach_native_game_api.assert_called_once_with(child)
        # The game API is registered once on the original service child.
        self.assertEqual(f.runtime.bind_native_game_api.call_count,1)
        address=0x8000;self.put(address,inputs.SELECTED_PATHS[0].encode('utf-16-le')+b'\0\0')
        self.assertEqual(ctx.load(ctx.receiver,pointer,address),1)
        call=f.runtime.execute.call_args
        self.assertIs(call.args[0],child)
        self.assertEqual(hashlib.sha256(call.args[1]).hexdigest(),inputs.SCRIPT_SHA256)
        self.assertEqual(call.args[2],inputs.SELECTED_PATHS[0].encode())
        with self.assertRaisesRegex(ValueError,'fresh owned context'):ctx.load(ctx.receiver,pointer,address)
        ctx.release(ctx.receiver,pointer)
        self.assertEqual(ctx.names,{})
        self.assertFalse(f.runtime.attach_include.called)

    def test_unadmitted_slots_remain_exact_refusals_and_foreign_graph_rejected(self):
        f=self.fixture();services=composition.compose_saved_load_services(f.backend)
        for method in f.excluded.values():method.assert_not_called()
        for table,interface,slots in ((f.host.vtable,'host',(0x78,0xC0,0x160)),
                                      (f.host.aux_vtable,'auxiliary',(0x90,))):
            for slot in slots:
                key=(C.addressof(table),slot)
                self.assertEqual(f.host._slot_bindings[key],f.before[key])
                self.assertEqual(table[slot//8],f.before[key][0])
                callback=f.host._slot_bindings[key][1]
                self.assertEqual(callback._native_unavailable,(interface,slot))
                with self.assertRaises(AssertionError):callback(f.host.pointer)
        self.assertEqual(services.composition_scope,dict(engine='xp2',phase='initial-saved-load-candidate',
            postload_160=False,cache_publication=False,commands=False,application_mirror=True,public_session_admitted=False))
        self.assertEqual(services.application_mirror.abi.configuration.core_sha256,composition.XP2_CORE_SHA256)
        captured_saved_load.attach_services(f.backend,services)
        original=services.control_inputs.deferred;services.control_inputs.deferred=object()
        with self.assertRaisesRegex(ValueError,'real deferred'):
            captured_saved_load.control_snapshot(f.backend,empty=True)
        services.control_inputs.deferred=original
        with self.assertRaisesRegex(ValueError,'action/interrupted-turn'):
            captured_saved_load.control_snapshot(f.backend,empty=True,allow_diplomacy=True)

    def test_command_request_refused_before_native_runtime_creation(self):
        f=self.fixture();f.backend._xp1_commands_requested=True
        with self.assertRaisesRegex(ValueError,'command composition'):
            composition.compose_saved_load_services(f.backend)
        f.runtime_ctor.assert_not_called();f.native_dll.assert_not_called()
        self.assertFalse(hasattr(f.backend,'_xp1_service_roots'))

    def test_missing_or_foreign_borrowed_lease_is_refused_by_real_consumers(self):
        f=self.fixture();b=f.backend
        with self.assertRaisesRegex(ValueError,'explicit profiled'):
            f.runtime.bind_core_services(f.host,b.context)
        f.runtime.host.LAB_ParameterDatabaseBind.assert_not_called()
        services=composition.compose_saved_load_services(b)
        lease=f.runtime._profile_borrowed_services
        f.runtime._profile_borrowed_services=None
        for consume in (lambda:f.runtime.bind_native_game_api(services.game_child,b.context,b.core,
                                core_sha256=composition.XP2_CORE_SHA256),
                        lambda:xp2_saved_script_services.verify_services(b,f.runtime,b.runtime.read)):
            with self.assertRaisesRegex(ValueError,'ownership or lifetime'):consume()
        f.runtime._profile_borrowed_services=lease
        with self.assertRaisesRegex(ValueError,'ownership or lifetime'):
            core_script_services.check_bound(f.runtime,b.context,NS(_handle=b.core._handle))

    def test_failed_database_binding_does_not_publish_lease_or_create_child(self):
        f=self.fixture();f.runtime.host.LAB_DBConfigurationBorrow.return_value=1
        with self.assertRaisesRegex(RuntimeError,'native binding failed'):
            composition.compose_saved_load_services(f.backend)
        self.assertIsNone(getattr(f.runtime,'_profile_borrowed_services',None))
        f.runtime.acquire.assert_not_called();f.profile_bind.assert_not_called()


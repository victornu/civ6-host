"""XP2 saved script service composition with native entrypoints stubbed.

These fixtures exercise the shared callback owners and lifecycle wiring. The
XP2 source verifier is stubbed only at the orchestration boundary; this module
does not claim a native XP2 source or saved-Load qualification.
"""
import ctypes as C
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, configuration_abi
from civ6_host.runtime.native.native_aux_map_adapter import SnapshotCallback
from civ6_host.runtime.native.native_gameplay_script_registry import (
    GameplayScriptEntry,
    NativeGameplayScriptRegistry,
)
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.script_map_service import MapService
from civ6_host.runtime.script_context_service import bootstrap_cached_context, script_name

from test_script_event_service import Host


class _ContextRuntime:
    """Small child registry/runtime that preserves real context service checks."""

    def __init__(self, game_child, order):
        self.order = order
        self.closed = False
        self.context_owner = None
        self.notification_service = None
        self.root = 0x9000
        self.children = {game_child.pointer: game_child}
        self.registry = NS(
            _check=Mock(),
            validate=self.validate,
            contexts={},
        )
        self._next = 0xA000
        self.execute = Mock(side_effect=lambda *args: self.order.append("execute"))
        self.attach_standard_libraries = Mock(side_effect=lambda child: self.order.append("stdlibs"))
        self.attach_game_events = Mock(side_effect=lambda child: self.order.append("game_events"))
        self.attach_include = Mock(side_effect=lambda child: self.order.append("include"))
        self.attach_native_game_api = Mock(side_effect=lambda child: self.order.append("native_game_api"))
        self.bind_native_game_api = Mock(side_effect=AssertionError("must reuse the registered Core cache"))
        self.namespaces = NS(register=Mock(side_effect=lambda child, name: self.order.append("namespace:" + name)))

    def validate(self, child):
        if self.children.get(getattr(child, "pointer", None)) is not child:
            raise ValueError("foreign script child")
        return child.pointer

    def acquire(self):
        child = NS(pointer=self._next, active=True)
        self._next += 0x100
        self.children[child.pointer] = child
        self.registry.contexts[child.pointer] = child
        return child


class _Lifetime:
    def __init__(self, runtime, *, project_root):
        self.runtime = runtime
        self._contexts = {}
        self.closed = False
        runtime.context_owner = self

    @property
    def handles(self):
        return tuple(self._contexts)

    def acquire(self):
        child = self.runtime.acquire()
        self._contexts[child.pointer] = child
        return child

    def release(self, pointer):
        child = self._contexts.pop(pointer)
        self.runtime.registry.contexts.pop(pointer, None)
        self.runtime.children.pop(pointer, None)
        child.active = False

    def close(self):
        if self._contexts:
            raise RuntimeError("release retained children first")
        self.runtime.context_owner = None
        self.closed = True
        self.runtime.order.append("context_lifetime")


class _Notification:
    def __init__(self, runtime, host, *, project_root):
        self.runtime = runtime
        runtime.notification_service = self

    def close(self):
        self.runtime.notification_service = None
        self.runtime.order.append("notification")


class XP2SavedScriptServicesTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        source = root / "WorldCongress.lua"
        source.write_bytes(b"return true\n")
        registry = NativeGameplayScriptRegistry(
            [root], selected_scripts=[GameplayScriptEntry(root, source.name)]
        )
        self.addCleanup(registry.close)

        order = []
        host = Host()
        host.pointer = 0x5000
        # AUX68 must replace a concrete, explicitly unavailable receiver slot.
        unavailable = lambda *_args: None
        unavailable._native_unavailable = ("auxiliary", 0x68)
        host._bind(host.aux_vtable, 0x68, None, [C.c_void_p], unavailable)

        def native_callback(restype, args, callback):
            return C.CFUNCTYPE(restype, *args)(callback)

        native_host = NS(
            LAB_AuxPushVariant=native_callback(None, (C.c_void_p,) * 3, lambda *_: None),
            LAB_AuxPushMap=native_callback(None, (C.c_void_p,) * 3 + (C.c_uint8,), lambda *_: None),
            LAB_AuxPushOptionalMap=native_callback(None, (C.c_void_p,) * 3 + (C.c_uint8,), lambda *_: None),
            LAB_AuxMapTransportVersion=native_callback(C.c_int, (), lambda: 2),
            LAB_AuxMapInstall=native_callback(
                C.c_int,
                (C.c_void_p, SnapshotCallback),
                lambda owner, callback: (order.append("map_install" if owner else "map_uninstall") or 1),
            ),
            LAB_GameEventsMapArgumentVersion=native_callback(C.c_int, (), lambda: 1),
            LAB_GameEventsDispatchMapsResult=native_callback(C.c_int, (), lambda: 1),
        )
        game_child = NS(pointer=0x7000, active=True)
        runtime = _ContextRuntime(game_child, order)
        runtime.registry.root=runtime.root
        runtime.host = native_host
        runtime.service_owner = host
        runtime.database_bound = runtime.configuration_bound = runtime.locale_bound = True
        core = NS(_handle=0x10000000)

        def read(address, size):
            cells = {
                (0x1008, 8): (0x2000).to_bytes(8, "little"),
                (0x2060, 8): bytes(8),
                (0x10000000 + 0x63DA20, 8): bytes.fromhex('0fb681a4020000c3'),
            }
            if (address, size) not in cells:
                raise ValueError((address, size))
            return cells[address, size]

        backend_runtime = NS(read=read)
        backend = NS(
            core=core,
            context=0x1000,
            host=host,
            emit=Mock(),
            destroyed=False,
            runtime=backend_runtime,
            configuration_abi=configuration_abi(XP2_CORE_SHA256),
            load_abi=configuration_abi(XP2_CORE_SHA256),
        )
        factory = NS(live={}, check=Mock(), close=lambda: order.append("map_arguments"))
        return temp, root, source, registry, order, host, runtime, backend, game_child, factory

    def compose(self, fixture, *, bootstrap=None, verifier=None):
        _temp, _root, source, registry, order, host, runtime, backend, child, factory = fixture

        class Dispatcher:
            poisoned = False

            def __init__(self, *_args, **_kwargs):
                order.append("mutable_dispatcher")

            def close(self):
                order.append("mutable_result")

        def adapter_install(adapter):
            adapter._installed = True
            order.append("map_adapter_install")

        source_check = verifier or {"events": {"source_sha256": "fixture"}}
        manager = patch("civ6_host.runtime.xp2_saved_script_services.verify_services",
                        side_effect=source_check if isinstance(source_check, BaseException) else None,
                        return_value=None if isinstance(source_check, BaseException) else source_check)
        with manager, \
             patch('civ6_host.runtime.script_event_state.ActiveEventStates',
                   return_value=NS(accepts=Mock(return_value=False),close=lambda:order.append('event_states'))), \
             patch("civ6_host.runtime.saved_load_services.MapArgumentFactory", return_value=factory), \
             patch("civ6_host.runtime.native.native_aux_map_adapter.NativeAuxMapAdapter.install",
                   autospec=True, side_effect=adapter_install), \
             patch("civ6_host.runtime.script_event_mutable_map.MutableMapResultDispatcher", Dispatcher), \
             patch("civ6_host.runtime.script_context_service.RetainedScriptContexts", _Lifetime), \
             patch("civ6_host.runtime.script_context_service.NativeContextNotification", _Notification):
            # `script_hashes` exactly covers the selected nonempty registry.
            return SavedLoadServices(
                backend, runtime, child, registry,
                core_sha256=XP2_CORE_SHA256,
                script_hashes={source: hashlib.sha256(source.read_bytes()).hexdigest()},
                bootstrap=bootstrap,
                saved_map_values=(("MAP_SIZE", 10),),
                saved_config_sha="a" * 64,
            )

    def test_xp2_composition_installs_real_shared_callbacks_and_default_cached_bootstrap(self):
        fixture = self.fixture()
        (_temp, _root, source, _registry, order, host, runtime, backend, child, factory) = fixture
        before_slots = tuple(host.aux_vtable)
        services = self.compose(fixture)

        self.assertEqual(services.source_receipts["events"]["source_sha256"], "fixture")
        self.assertEqual(services.maps.adapter.core_sha256, XP2_CORE_SHA256)
        self.assertTrue(services.maps.adapter.allow_nested_maps)
        self.assertEqual(host.aux_vtable[0xA0 // 8], C.cast(runtime.host.LAB_AuxPushVariant, C.c_void_p).value)
        self.assertEqual(host.aux_vtable[0xA8 // 8], C.cast(runtime.host.LAB_AuxPushMap, C.c_void_p).value)
        self.assertEqual(host.aux_vtable[0xB0 // 8], C.cast(runtime.host.LAB_AuxPushOptionalMap, C.c_void_p).value)
        self.assertTrue(services.events.aux68_installed)
        self.assertEqual(host.aux_vtable[0x68 // 8], services.events.installed[0x68])
        self.assertEqual(host.aux_vtable[0x60 // 8], services.events.installed[0x60])
        self.assertEqual(host.aux_vtable[0x80 // 8], services.events.installed[0x80])
        self.assertEqual(host.aux_vtable[0x00 // 8], services.contexts.installed[0x00])
        self.assertEqual(len(services.contexts.paths), 1)
        self.assertEqual(services.contexts.paths[0], source)

        pointer = services.contexts.acquire(services.contexts.receiver,
                                            script_name(source), 0)
        context_child = services.contexts.lifetime._contexts[pointer]
        services.contexts.release(services.contexts.receiver, pointer)
        self.assertEqual(order[:4], ["map_adapter_install", "mutable_dispatcher",
                                     "stdlibs", "game_events"])
        self.assertEqual(order[4:9], ["namespace:DB", "namespace:GameInfo",
                                      "namespace:GlobalParameters", "namespace:Path",
                                      "namespace:Locale"])
        self.assertEqual(order[9:11], ["native_game_api", "execute"])
        self.assertEqual(sum(x.startswith("namespace:") for x in order), 5)
        runtime.attach_native_game_api.assert_called_once_with(context_child)
        runtime.bind_native_game_api.assert_not_called()
        self.assertIs(host._saved_load_services, services)

        services.close()
        self.assertEqual(order[-6:], ["notification", "context_lifetime", "mutable_result",
                                      "map_arguments", "map_uninstall", "event_states"])
        self.assertIsNone(host._saved_load_services)
        self.assertEqual(tuple(host.aux_vtable), before_slots)

    def test_xp2_source_preflight_failure_leaves_all_callback_tables_uninstalled(self):
        fixture = self.fixture()
        _temp, _root, _source, _registry, order, host, _runtime, _backend, _child, _factory = fixture
        slots = tuple(host.aux_vtable)
        bindings = dict(host._slot_bindings)
        with self.assertRaisesRegex(ValueError, "source preflight"):
            self.compose(fixture, verifier=ValueError("source preflight"))
        self.assertEqual(tuple(host.aux_vtable), slots)
        self.assertEqual(host._slot_bindings, bindings)
        self.assertIsNone(getattr(host, "_saved_load_services", None))
        self.assertIsNone(getattr(host, "_scalar_service_owner", None))
        self.assertIsNone(getattr(host, "_map_service_owner", None))
        self.assertIsNone(getattr(host, "_script_event_owner", None))
        self.assertEqual(order, [])

    def test_cached_bootstrap_rejects_bad_names_and_foreign_children_before_native_calls(self):
        order = []
        child = NS(pointer=0x1000)
        runtime = _ContextRuntime(child, order)
        runtime.attach_native_game_api = Mock()
        for name, include in ((None, False), (b"", False), (b"bad\x00name", False),
                              (b"x" * 260, False), (b"WorldCongress", 1)):
            with self.subTest(name=name, include=include):
                with self.assertRaises(ValueError):
                    bootstrap_cached_context(runtime, child, name, include=include)
        foreign = NS(pointer=0x9999)
        with self.assertRaisesRegex(ValueError, "foreign"):
            bootstrap_cached_context(runtime, foreign, b"WorldCongress")
        self.assertEqual(order, [])
        runtime.attach_native_game_api.assert_not_called()

    def test_cached_bootstrap_reuses_registered_core_cache_and_include_is_explicit(self):
        order = []
        child = NS(pointer=0x1000)
        runtime = _ContextRuntime(child, order)
        bootstrap_cached_context(runtime, child, b"WorldCongress", include=True)
        self.assertEqual(order[:3], ["stdlibs", "game_events", "include"])
        self.assertEqual(sum(item.startswith("namespace:") for item in order), 5)
        self.assertEqual(order[8:], ["native_game_api", "execute"])
        runtime.attach_native_game_api.assert_called_once_with(child)
        runtime.bind_native_game_api.assert_not_called()

    def test_map_service_keeps_nested_maps_opt_in_and_rejects_nonboolean_before_install(self):
        fixture=self.fixture()
        _temp,_root,_source,_registry,_order,host,runtime,backend,_child,_factory=fixture
        slots=tuple(host.aux_vtable)
        with self.assertRaisesRegex(ValueError,'Boolean'):
            MapService(host,runtime,backend.core,core_sha256=XP2_CORE_SHA256,
                       read=backend.runtime.read,allow_nested_maps=1)
        self.assertEqual(tuple(host.aux_vtable),slots)
        def installed(adapter):adapter._installed=True
        with patch('civ6_host.runtime.native.native_aux_map_adapter.NativeAuxMapAdapter.install',
                   autospec=True,side_effect=installed):
            owner=MapService(host,runtime,backend.core,core_sha256=XP2_CORE_SHA256,read=backend.runtime.read)
        self.assertFalse(owner.adapter.allow_nested_maps)
        owner.close();self.assertEqual(tuple(host.aux_vtable),slots)


if __name__ == "__main__":
    unittest.main(verbosity=2)

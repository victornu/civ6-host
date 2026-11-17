"""Offline shared builders and actual saved owners/FIFO; no GameCore execution."""
from copy import deepcopy
import ctypes as C
from hashlib import sha256
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_pantheon as adapter, xp1_pantheon_source as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_pantheon_actions as builders
from civ6_host.runtime.native import native_saved_pantheon as shared
from civ6_host.runtime.native import native_player_operation_request as request
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_action_transport import SavedActionTransport
from civ6_host.runtime.deferred_service import DeferredService
import test_xp1_world_input_owner as composed


class Fixture(composed.Fixture):
    """Reuse the established real saved owner, queue and publisher fixture."""
    def __init__(self):
        super().__init__()
        self.backend.core._civ6_host_execution_image = _XP1_PROFILE
        self.pantheon = -1
        self.can_start = True
        self.choice = dict(kind='pantheon', index=4, hash=2147483648)
        self.payload = struct.pack('<I', 3294486831) + b'fixture-only-native-archive'
        self.maps = {}
        self.lookup_owned = []
        p = self.backend.prefix
        # Real native Lua owner deliberately has no .read attribute. Memory
        # belongs to backend.runtime, as in the actual composed saved owner.
        runtime = NativeScriptRuntime.__new__(NativeScriptRuntime)
        runtime.__dict__.update(p.runtime.__dict__)
        runtime.evaluate_text = self.evaluate
        p.runtime = self.token.runtime = runtime
        self.token.lease.script_runtime = runtime
        p.events.runtime = p.contexts.runtime = runtime
        self.stack.enter_context(patch.object(shared, 'observe_player', self.observe_native))

    def evaluate(self, child, code, name, **kwargs):
        if child is not self.token.ui_child:
            raise AssertionError('Foreign UI child')
        if name == b'@native_pantheon_guards':
            from lupa.lua51 import LuaRuntime
            return LuaRuntime(encoding=None).execute(code)
        if name == b'@native_pantheon_turn':
            return b'8'
        if name in (b'@explicit_pantheon_catalog', b'@native_pantheon_catalog'):
            if self.pantheon >= 0:
                return b'not_due,0,8,already_has_pantheon'
            return b'catalog,0,8,2524039121,2756389127,2888817673,2550048198,1,4:2147483648'
        if name == b'@native_pantheon_revalidation':
            return b'valid,0,8,4,2147483648,2524039121,2756389127,2888817673,2550048198'
        if name == b'@native_pantheon_effect':
            return b'verified,0,8,4,2147483648,4' if self.pantheon == 4 else b'pending,0,8,4,2147483648,4294967295'
        raise AssertionError('Unexpected native Lua boundary: ' + repr(name))

    def factory(self, result, *args):
        from civ6_host.runtime.xp1_research_profile import player_operation_abi
        abi = player_operation_abi(XP1_CORE_SHA256, request._METHODS)
        methods = {rva: name for name, (rva, _, _) in abi.methods.items()}
        parent = super().factory(result, *args)

        def bind(address):
            name = methods.get(address-self.memory.base)
            if name is None:
                return parent(address)
            def call(*values):
                self.machine.append((name,))
                if name in ('parameter_ctor', 'reason_ctor'):
                    ptr = values[0]
                    vtable = abi.parameters if name == 'parameter_ctor' else abi.reasons
                    C.memmove(ptr, struct.pack('<Q', self.memory.base+vtable), 8)
                    self.maps[ptr] = {}
                    return ptr
                if name in ('parameter_dtor', 'reason_dtor'):
                    self.maps.pop(values[0])
                    return
                if name == 'lookup':
                    return self.maps[values[0]].get(values[1], 0)
                if name == 'set_u32':
                    ptr, key, value = values
                    raw = struct.pack('<H6xI4xQ', 2, value, 0)
                    obj = C.create_string_buffer(raw, 24)
                    self.lookup_owned.append(obj)
                    self.maps[ptr][key] = C.addressof(obj)
                    return C.addressof(obj)
                if name == 'can_start':
                    if values[1:3] != (0, 2524039121) or values[4] is not False:
                        raise AssertionError('Native CanStart arguments changed')
                    return int(self.can_start)
                if name == 'request':
                    self.token.transport.pending.append(self.payload)
                    return
                raise AssertionError(name)
            return call
        return bind

    def virtual(self, core, pointer, slot, rva, result, *args):
        a = self.token.transport.transport_abi
        if rva == a.drain_rva:
            def drain(ctx):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                self.pantheon = 4
            return drain
        return super().virtual(core, pointer, slot, rva, result, *args)


class PantheonTests(unittest.TestCase):
    def fixture(self):
        f = Fixture()
        self.addCleanup(f.close)
        return f

    def test_source_and_exact_installed_owner_profile(self):
        proof, central = source.verify_source()
        self.assertEqual(len(proof['bindings']), 6)
        self.assertEqual(central['factory']['direct_calls_scanned_in_exact_text_section'], 6)
        pins = source.source_dependencies(_XP1_PROFILE)
        for path, digest in pins.items():
            self.assertEqual(sha256(Path(path).read_bytes()).hexdigest(), digest)
        with self.assertRaises(ValueError):
            source.source_dependencies(None)
        with self.assertRaises(ValueError):
            builders.catalog_source(0, 8, core_sha256='unknown')
        f = self.fixture()
        self.assertIs(type(f.backend.prefix), SavedLoadServices)
        self.assertIs(type(f.backend.prefix.runtime), NativeScriptRuntime)
        self.assertFalse(hasattr(f.backend.prefix.runtime, 'read'))
        source.bind_prefix(f.backend.prefix)
        f.backend.core._civ6_host_execution_image = None
        with self.assertRaises(ValueError):
            source.bind_prefix(f.backend.prefix)

    def test_lua_builders_preserve_base_semantics_with_explicit_xp1_proof(self):
        from lupa.lua51 import LuaRuntime
        self.assertEqual(builders.catalog_source(0, 8),
            builders.catalog_source(0, 8, core_sha256=XP1_CORE_SHA256))
        for selected in (builders._ROUTE_IMAGES['core'], XP1_CORE_SHA256):
            self.assertEqual(LuaRuntime(encoding=None).execute(builders.guard_case(core_sha256=selected)),
                b'pantheon-guards-ok')

    def test_catalogue_is_native_format_and_owner_and_caller_fields_are_strict(self):
        f = self.fixture()
        value = adapter.catalogue(f.saved, f.token.observation)
        self.assertEqual(value['status'], 'catalog')
        self.assertEqual(value['choices'], [dict(index=4, hash=2147483648)])
        self.assertEqual(adapter.actions(value), [f.choice])
        value['choices'].clear()
        self.assertEqual(f.saved.explicit_pantheon['choices'], [dict(index=4, hash=2147483648)])
        with self.assertRaises(ValueError):
            adapter.catalogue(f.saved, dict(f.token.observation, player_id=True))
        f.saved._backend = object()
        with self.assertRaises(ValueError):
            adapter.catalogue(f.saved, f.token.observation)

    def test_shared_selected_transport_real_owners_and_fifo_and_native_refusal(self):
        # Source action admission is tested separately; this tests the selected
        # common orchestration directly against only replaced machine calls.
        for allowed in (True, False):
            with self.subTest(can_start=allowed):
                f = self.fixture()
                self.assertIs(type(f.token.transport), SavedActionTransport)
                self.assertIs(type(f.deferred), DeferredService)
                adapter.catalogue(f.saved, f.token.observation)
                f.set_active(True)
                f.can_start = allowed
                if allowed:
                    result = shared.inspect_choice(f.backend.prefix, 0, selected_index=4,
                        core_sha256=XP1_CORE_SHA256, read=f.backend.runtime.read)
                    self.assertTrue(result['confirmed'])
                    self.assertEqual(f.pantheon, 4)
                    self.assertEqual(f.token.publication_count, 1)
                else:
                    with self.assertRaises(shared.NativePantheonRefused):
                        shared.inspect_choice(f.backend.prefix, 0, selected_index=4,
                            core_sha256=XP1_CORE_SHA256, read=f.backend.runtime.read)
                    self.assertEqual(f.pantheon, -1)
                    self.assertEqual(f.token.publication_count, 0)
                    self.assertNotIn(('request',), f.machine)
                self.assertEqual(f.token.transport.pending, [])
                self.assertEqual(f.deferred.pending, [])
                f.token.transport.require_empty_native_queue()
                f.close()

    def test_explicit_facade_refuses_unqualified_source_and_implicit_choice(self):
        f = self.fixture()
        f.set_active(True)
        with self.assertRaises(ValueError):
            f.backend.prefix.inspect_pantheon_choice(0, selected_index=True)
        with patch.object(source, 'ACTION_SOURCE', None):
            with self.assertRaisesRegex(ValueError, 'dependencies'):
                f.backend.prefix.inspect_pantheon_choice(0, selected_index=4)
            self.assertEqual(f.machine, [])
        result = f.backend.prefix.inspect_pantheon_choice(0, selected_index=4)
        self.assertTrue(result['confirmed'])

    def test_public_apply_rechecks_then_confirms_or_reports_native_refusal(self):
        for allowed in (True, False):
            with self.subTest(can_start=allowed):
                f = self.fixture()
                adapter.catalogue(f.saved, f.token.observation)
                f.set_active(True)
                f.can_start = allowed
                result = adapter.apply(f.saved, f.choice, f.token.observation)
                self.assertEqual(result['status'], 'completed' if allowed else 'refused')
                self.assertEqual(result['observation'], f.token.observation)
                self.assertEqual(f.pantheon, 4 if allowed else -1)
                self.assertEqual(f.token.transport.pending, [])
                self.assertEqual(f.deferred.pending, [])
                if not allowed:
                    self.assertEqual(result['refusal_code'], 'native_pantheon_can_start_false')
                    self.assertNotIn(('request',), f.machine)
                f.close()


if __name__ == '__main__':
    unittest.main()

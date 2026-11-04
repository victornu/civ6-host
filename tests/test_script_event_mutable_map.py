"""Fixture-only AUX68 lifecycle, packing and protected-error contracts."""
import ctypes as C
import struct
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_script_event_service import Host
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_script_arguments import BooleanArgument
from civ6_host.runtime.script_event_maps import ParameterMapArgument
from civ6_host.runtime import script_event_mutable_map as mutable
from civ6_host.runtime.script_event_service import ScriptEventService


EMPTY = struct.pack('<IIQ', 1, 0, 0)
_OWNED_EMPTY = object()
SEED = (struct.pack('<IIQ', 1, 0, 1) + struct.pack('<IIQ', 7, 4, 0)
        + b'keep\0'.ljust(16, b'\0')
        + struct.pack('<IIQ', 2, 0, 0x4008000000000000) + struct.pack('<IIQ', 5, 0, 0))


class MutableMapTests(unittest.TestCase):
    def fixture(self, *, install=True):
        host = Host()
        unsupported = DiagnosticHost._unsupported(host, 'auxiliary', 0x68)
        host._bind(host.aux_vtable, 0x68, C.c_uint8, [C.c_void_p], unsupported)
        before, functions = dict(host._slot_bindings), tuple(host.functions)
        abi = SimpleNamespace(core_sha256=XP2_CORE_SHA256)
        core = SimpleNamespace(_handle=0x200000000)
        factory = Mock(base=core._handle, abi=abi)
        factory.snapshot.return_value = SimpleNamespace(transport=SEED)
        state = dict(top=0, status=0, valid=1, truth=0, refused=0, phase=3,
                     error=b'deliberate HKS error', error_type=4)
        retained = []

        def native(*args):
            state['native_arguments'] = args
            state['native_maps'] = tuple(
                C.string_at(args[4][index].ops, args[4][index].count * 16)
                for index in range(args[5]))
            for index, key, kind in ((11, 'valid', C.c_uint8), (12, 'truth', C.c_uint8),
                                     (13, 'refused', C.c_uint32), (14, 'phase', C.c_uint32)):
                C.cast(args[index], C.POINTER(kind))[0] = state[key]
            state['top'] = state.get('returned_top',
                int(state['status'] != 0 and state['status'] not in (-1960, -1601, -1602)))
            return state['status']

        def tolstring(root, index, length):
            C.cast(length, C.POINTER(C.c_size_t))[0] = len(state['error'])
            buffer = C.create_string_buffer(state['error'])
            retained.append(buffer)
            return C.addressof(buffer)

        exports = SimpleNamespace(
            LAB_GameEventsMapArgumentVersion=Mock(return_value=1),
            LAB_AuxMapTransportVersion=Mock(return_value=2),
            LAB_GameEventsDispatchMapsResult=Mock(),
            LAB_GameEventsMutableMapVersion=Mock(return_value=1),
            LAB_GameEventsDispatchMutableMapResult=Mock(side_effect=native))
        registry = SimpleNamespace(root=0x10000, _check=Mock())
        runtime = SimpleNamespace(root=registry.root, registry=registry, host=exports,
                                  service_owner=host,
                                  lua={'gettop': lambda root: state['top'],
                                       'settop': lambda root, top: state.update(top=top),
                                       'type': lambda root, index: state['error_type'],
                                       'tolstring': tolstring})
        verifier = Mock(return_value={'fixture_only': True, 'native_execution': False})
        profile = SimpleNamespace(verify_runtime=verifier)
        self.enterContext(patch.dict(sys.modules, {'civ6_host.runtime.xp2_mutable_map_profile': profile}))
        self.enterContext(patch.object(mutable, 'configuration_abi', return_value=abi))
        service = ScriptEventService(host, runtime, map_factory=factory)
        read = Mock()
        if install:
            service.install_mutable_map_result(core, core_sha256=XP2_CORE_SHA256, read=read)
        return SimpleNamespace(host=host, runtime=runtime, factory=factory, core=core,
                               state=state, service=service, verifier=verifier, read=read,
                               previous=before, functions=functions, exports=exports,
                               owner=C.addressof(host.aux_object), destination=0x50000)

    def call(self, fixture, arguments=_OWNED_EMPTY, name=b'AnySourceQualifiedEvent'):
        owned = arguments is _OWNED_EMPTY
        if owned:
            arguments = fixture.service.script_arguments._create(fixture.owner)
        try:
            return fixture.service.game_event_mutable_map(
                fixture.owner, name, arguments, fixture.destination)
        finally:
            if owned:
                fixture.service.script_arguments._release(fixture.owner, arguments)

    def test_explicit_install_restores_slot_bindings_and_callback_roots(self):
        f = self.fixture(install=False)
        self.assertEqual(ScriptEventService.SLOTS, (0x40, 0x48, 0x60, 0x80))
        self.assertEqual(f.host._slot_bindings[C.addressof(f.host.aux_vtable), 0x68],
                         f.previous[C.addressof(f.host.aux_vtable), 0x68])
        f.service.install_mutable_map_result(f.core, core_sha256=XP2_CORE_SHA256, read=f.read)
        f.verifier.assert_called_once_with(f.runtime, f.core, f.read)
        with self.assertRaisesRegex(ValueError, 'installed'):
            f.service.install_mutable_map_result(f.core, core_sha256=XP2_CORE_SHA256, read=f.read)
        f.service.close()
        self.assertEqual(f.host._slot_bindings, f.previous)
        self.assertEqual(tuple(f.host.functions), f.functions)
        with self.assertRaisesRegex(ValueError, 'closed'):
            f.service.mutable_map_dispatcher.dispatch(b'Event', (), f.destination)

    def test_owned_empty_arguments_and_false_truthiness_return_native_validity(self):
        f = self.fixture()
        self.assertIs(self.call(f), True)
        self.assertIs(self.call(f, name=b'AnotherGenericEvent'), True)
        args = f.state['native_arguments']
        self.assertIsNone(args[2]); self.assertEqual(args[3], 0)
        self.assertIsNone(args[4]); self.assertEqual(args[5], 0)
        self.assertEqual(C.string_at(args[6], args[7] * 16), SEED)
        self.assertEqual(args[8:11], (f.destination, f.core._handle, 2))
        f.factory.snapshot.assert_called_with(f.destination, names=True)
        f.factory.assert_not_called()  # The borrowed result map is not cloned.
        event = f.host.emit.call_args.kwargs
        self.assertTrue(event['result_non_nil']); self.assertFalse(event['result_truthiness'])
        f.state.update(valid=0, truth=0)
        self.assertIs(self.call(f), False)
        f.service.close()

    def test_source_qualified_null_provider_packs_zero_arguments_and_keeps_seed(self):
        for pointer in (None, 0):
            with self.subTest(pointer=pointer):
                f = self.fixture()
                self.assertIs(self.call(f, pointer), True)
                args = f.state['native_arguments']
                self.assertIsNone(args[2]); self.assertEqual(args[3], 0)
                self.assertEqual(C.string_at(args[6], args[7] * 16), SEED)
                self.assertFalse(f.service.aux68_poisoned)
                f.service.close()

    def test_owned_payload_uses_shared_typed_and_map_packing(self):
        f = self.fixture()
        value = ParameterMapArgument.__new__(ParameterMapArgument)
        value.factory = f.factory
        value.snapshot = Mock(return_value=SimpleNamespace(transport=EMPTY))
        value.close = Mock()
        payload = f.service.script_arguments._create(f.owner)
        f.service.script_arguments._get_live(payload).values[:] = [0xffffffff, BooleanArgument(255), value]
        self.assertIs(self.call(f, payload), True)
        args = f.state['native_arguments']
        self.assertEqual([(item.kind, item.value) for item in args[2]],
                         [(0, 0xffffffff), (1, 255), (2, 0)])
        self.assertEqual(args[3], 3); self.assertEqual(args[5], 1)
        self.assertEqual(f.state['native_maps'], (EMPTY,))
        value.snapshot.assert_called_once()
        with self.assertRaisesRegex(ValueError, 'live payload'):
            f.service.close()
        f.service.script_arguments._release(f.owner, payload)
        value.close.assert_called_once()
        f.service.close()

    def test_seed_and_argument_maps_share_one_operation_budget(self):
        value = ParameterMapArgument.__new__(ParameterMapArgument)
        value.snapshot = Mock(return_value=SimpleNamespace(transport=EMPTY))
        with patch.object(mutable, 'MAX_OPS', 1):
            with self.assertRaisesRegex(ValueError, 'Aggregate'):
                mutable.pack_mutable_map((value,), EMPTY)
        packed, maps, seed, count, buffers = mutable.pack_mutable_map((), EMPTY)
        self.assertEqual((len(packed), len(maps), count, len(buffers)), (0, 0, 1, 1))
        self.assertEqual(C.string_at(seed, 16), EMPTY)

    def test_positive_hks_error_before_call_returns_native_invalid_and_pops_error(self):
        f = self.fixture()
        f.state.update(status=2, valid=0, phase=1, error=b'x' * 5000)
        self.assertIs(self.call(f), False)
        self.assertEqual(f.state['top'], 0)
        events = [call for call in f.host.emit.call_args_list
                  if call.args == ('native_game_event_mutable_map_protected_error',)]
        self.assertEqual(len(events[0].kwargs['error']), 4096)
        self.assertEqual(events[0].kwargs['error_bytes'], 5000)
        self.assertTrue(events[0].kwargs['error_truncated'])
        self.assertFalse(f.service.aux68_poisoned)
        f.service.close()

    def test_positive_hks_error_during_conversion_preserves_stored_validity(self):
        f = self.fixture()
        f.state.update(status=2, valid=1, truth=0, phase=2)
        self.assertIs(self.call(f), True)
        self.assertEqual(f.state['top'], 0)
        self.assertFalse(f.host.emit.call_args.kwargs['protected_call_success'])
        self.assertEqual(f.host.emit.call_args.kwargs['phase'], 2)
        f.state.update(status=0, phase=3)
        self.assertIs(self.call(f), True)
        f.service.close()

    def test_negative_hks_status_preserves_native_validity_before_and_after_call(self):
        for phase, valid in ((1, 0), (2, 1)):
            with self.subTest(phase=phase):
                f = self.fixture()
                f.state.update(status=-100, phase=phase, valid=valid)
                self.assertIs(self.call(f), bool(valid))
                self.assertEqual(f.state['top'], 0)
                error = f.host.emit.call_args_list[-2].kwargs
                self.assertEqual(error['native_status'], -100)
                self.assertEqual(error['error'], 'deliberate HKS error')
                self.assertFalse(f.service.aux68_poisoned)
                f.service.close()

    def test_negative_hks_status_with_bridge_refusal_copies_reason_and_quarantines(self):
        f = self.fixture()
        f.state.update(status=-100, refused=1, phase=2,
                       error=b'Mutable map bridge refused: cycle ' + b'x' * 5000)
        with self.assertRaisesRegex(RuntimeError, 'native refusal.*cycle') as raised:
            self.call(f)
        error = f.host.emit.call_args.kwargs
        self.assertEqual(error['native_status'], -100)
        self.assertEqual(len(error['error']), 4096)
        self.assertTrue(error['error_truncated'])
        self.assertIn(error['error'], str(raised.exception))
        self.assertEqual(f.state['top'], 0)
        self.assertTrue(f.service.aux68_poisoned)
        self.assertTrue(f.service.mutable_map_dispatcher.poisoned)

    def test_lock_leave_refusal_copies_protected_error_and_stays_hard_refusal(self):
        f = self.fixture()
        f.state.update(status=-1602, returned_top=1, phase=2, error=b'protected error before lock failure')
        with self.assertRaisesRegex(RuntimeError, 'native refusal.*protected error before lock failure'):
            self.call(f)
        self.assertEqual(f.state['top'], 0)
        self.assertTrue(f.service.aux68_poisoned)
        self.assertEqual(f.host.emit.call_args.kwargs['native_status'], -1602)

    def test_hks_error_requires_preconversion_phase_and_exactly_one_stack_value(self):
        for phase, top in ((0, 1), (3, 1), (1, 0), (2, 2)):
            with self.subTest(phase=phase, top=top):
                f = self.fixture()
                f.state.update(status=-100, valid=0, phase=phase, returned_top=top)
                with self.assertRaisesRegex(RuntimeError, 'inconsistent|invalid root stack'):
                    self.call(f)
                self.assertEqual(f.state['top'], 0)
                self.assertTrue(f.service.aux68_poisoned)

    def test_nonstring_hks_error_is_logged_and_popped(self):
        f = self.fixture()
        f.state.update(status=2, valid=0, phase=1, error_type=5)
        self.assertIs(self.call(f), False)
        self.assertEqual(f.state['top'], 0)
        error = f.host.emit.call_args_list[-2].kwargs
        self.assertEqual((error['error'], error['error_type']), ('', 5))
        f.service.close()

    def test_native_guard_and_conversion_refusals_quarantine_even_when_valid(self):
        for status, refused in ((-1960, 0), (-1601, 0), (-1602, 0), (2, 1), (0, 1)):
            with self.subTest(status=status, refused=refused):
                f = self.fixture()
                f.state.update(status=status, refused=refused, phase=2)
                with self.assertRaisesRegex(RuntimeError, 'refusal'):
                    self.call(f)
                self.assertTrue(f.service.aux68_poisoned)
                self.assertTrue(f.service.mutable_map_dispatcher.poisoned)
                self.assertEqual(f.service.dispatch_depth, 0)
                self.assertEqual(f.state['top'], 0)
                with self.assertRaisesRegex(ValueError, 'dispatch or live payload'):
                    f.service.close()

    def test_bound_callback_routes_python_failure_to_host_fatal(self):
        f = self.fixture()
        f.state.update(status=-1960)
        f.host._fatal = Mock()  # Actual host terminates; no return byte is defined here.
        callback = C.WINFUNCTYPE(C.c_uint8, C.c_void_p, C.c_char_p, C.c_void_p, C.c_void_p)(
            f.host.aux_vtable[0x68 // 8])
        payload = f.service.script_arguments._create(f.owner)
        # The deliberately returning fatal double makes ctypes report an
        # undefined return conversion. Capture that expected fixture artifact;
        # it is not an API return and is never interpreted as success.
        with patch('sys.unraisablehook') as unraisable:
            callback(f.owner, b'GenericEvent', payload, f.destination)
        unraisable.assert_called_once()
        self.assertIs(unraisable.call_args.args[0].exc_type,TypeError)
        f.service.script_arguments._release(f.owner, payload)
        f.host._fatal.assert_called_once()
        self.assertEqual(f.host._fatal.call_args.kwargs['slot'], '0x68')
        self.assertTrue(f.service.aux68_poisoned)

    def test_install_refuses_existing_owner_unknown_version_and_wrong_factory(self):
        f = self.fixture(install=False)
        table = C.addressof(f.host.aux_vtable)
        original = f.host._slot_bindings[table, 0x68]
        f.host._slot_bindings[table, 0x68] = (original[0], lambda _: None)
        with self.assertRaisesRegex(ValueError, 'another callback owner'):
            f.service.install_mutable_map_result(f.core, core_sha256=XP2_CORE_SHA256, read=f.read)
        f.host._slot_bindings[table, 0x68] = original
        f.exports.LAB_GameEventsMutableMapVersion.return_value = 9
        with self.assertRaisesRegex(ValueError, 'version'):
            f.service.install_mutable_map_result(f.core, core_sha256=XP2_CORE_SHA256, read=f.read)
        f.exports.LAB_GameEventsMutableMapVersion.return_value = 1
        f.factory.base += 0x1000
        with self.assertRaisesRegex(ValueError, 'ABI or Core base'):
            f.service.install_mutable_map_result(f.core, core_sha256=XP2_CORE_SHA256, read=f.read)
        self.assertNotIn(0x68, f.service.installed)
        f.service.close()

    def test_install_requires_explicit_source_profile_factory_owner_and_empty_root(self):
        for mode in ('sha', 'factory', 'owner', 'registry', 'stack', 'depth', 'poison'):
            with self.subTest(mode=mode):
                f = self.fixture(install=False)
                sha = XP2_CORE_SHA256
                if mode == 'sha': sha = 'unqualified'
                elif mode == 'factory': f.service.map_factory = None
                elif mode == 'owner': f.runtime.service_owner = object()
                elif mode == 'registry': f.runtime.registry.root += 8
                elif mode == 'stack': f.state['top'] = 1
                elif mode == 'depth': f.service.dispatch_depth = 1
                elif mode == 'poison': f.service.aux90_poisoned = True
                with self.assertRaises((ValueError, RuntimeError)):
                    f.service.install_mutable_map_result(f.core, core_sha256=sha, read=f.read)
                self.assertNotIn(0x68, f.service.installed)

    def test_source_verification_failure_leaves_aux68_unmodified(self):
        f = self.fixture(install=False)
        f.verifier.side_effect = ValueError('fixture source mismatch')
        with self.assertRaisesRegex(ValueError, 'source mismatch'):
            f.service.install_mutable_map_result(f.core, core_sha256=XP2_CORE_SHA256, read=f.read)
        self.assertNotIn(0x68, f.service.previous)
        self.assertNotIn(0x68, f.service.installed)
        f.service.close()

    def test_foreign_payload_receiver_and_reentry_poison_without_native_call(self):
        for mode in ('receiver', 'payload', 'depth'):
            with self.subTest(mode=mode):
                f = self.fixture()
                owner, payload = f.owner, None
                if mode == 'receiver': owner = 123
                elif mode == 'payload': payload = 456
                else: f.service.dispatch_depth = 1
                with self.assertRaises((ValueError, RuntimeError)):
                    f.service.game_event_mutable_map(owner, b'Event', payload, f.destination)
                self.assertTrue(f.service.aux68_poisoned)
                f.exports.LAB_GameEventsDispatchMutableMapResult.assert_not_called()

    def test_dispatch_runtime_factory_and_root_lifetimes_are_pinned(self):
        for mode in ('core', 'factory', 'owner', 'registry', 'root', 'stack'):
            with self.subTest(mode=mode):
                f = self.fixture()
                if mode == 'core': f.core._handle += 8
                elif mode == 'factory': f.factory.abi = object()
                elif mode == 'owner': f.runtime.service_owner = object()
                elif mode == 'registry': f.runtime.registry = SimpleNamespace(_check=Mock())
                elif mode == 'root': f.runtime.root += 8
                else: f.state['top'] = 1
                with self.assertRaises((ValueError, RuntimeError)):
                    self.call(f)
                f.exports.LAB_GameEventsDispatchMutableMapResult.assert_not_called()

    def test_wrong_thread_dispatch_is_quarantined(self):
        f = self.fixture(); errors = []
        def call():
            try:
                f.service.game_event_mutable_map(f.owner, b'Event', None, f.destination)
            except ValueError as error:
                errors.append(error)
        thread = threading.Thread(target=call); thread.start(); thread.join()
        self.assertEqual(len(errors), 1)
        self.assertTrue(f.service.aux68_poisoned)
        f.exports.LAB_GameEventsDispatchMutableMapResult.assert_not_called()


if __name__ == '__main__':
    unittest.main()

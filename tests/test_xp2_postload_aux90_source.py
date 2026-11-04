"""Offline source/owner tests for the XP2 AUX90 wrapper; never loads GameCore."""
import ctypes as C
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.script_event_service import ScriptEventService
from civ6_host.runtime import xp2_postload_aux90_source as source


class _Host:
    _bind = DiagnosticHost._bind
    _unsupported = DiagnosticHost._unsupported

    def __init__(self):
        self.aux_vtable = (C.c_void_p * 32)()
        self.aux_object = (C.c_void_p * 2)(C.addressof(self.aux_vtable), 1)
        self.pointer = 0x90000
        self.functions = []
        self.emit = Mock()
        for slot in (*ScriptEventService.SLOTS, 0x90):
            self._bind(self.aux_vtable, slot, None, [C.c_void_p],
                       self._unsupported('auxiliary', slot))


class XP2Aux90SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = source.source()
        cls.body = cls.proof['functions']['xp2']['aux_scope']
        cls.raw = bytes.fromhex(cls.body['raw_hex'])

    def test_profile_and_all_source_dependencies_are_pinned(self):
        pins = source.source_dependencies()
        self.assertIn(source.SOURCE[1], {d for d in pins.values()})
        self.assertGreaterEqual(len(pins), 2)
        self.assertEqual(self.proof['contract']['callback']['auxiliary_slot'], 0x90)
        self.assertEqual(tuple(self.proof['contract']['callback']['events']),
                         ('AutoPlayStart', 'AutoPlayEnd'))
        self.assertFalse(self.proof['contract']['post160_runtime_admitted'])

    def test_live_wrapper_and_core_host_global_are_checked_exactly(self):
        base = 0x200000000
        host_pointer = 0x90000
        auxiliary_pointer = 0xA0000

        def read(address, size):
            if (address, size) == (base + source.AUX_SCOPE_RVA, source.AUX_SCOPE_LENGTH):
                return self.raw
            if (address, size) == (base + source.HOST_GLOBAL_RVA, 8):
                return host_pointer.to_bytes(8, 'little')
            if (address, size) == (base + source.AUX_GLOBAL_RVA, 8):
                return auxiliary_pointer.to_bytes(8, 'little')
            raise AssertionError((hex(address), size))

        receipt = source.verify_xp2_live(base, read, host_pointer=host_pointer,
                                         auxiliary_pointer=auxiliary_pointer,
                                         proof=self.proof)
        self.assertEqual(receipt['wrapper_sha256'], source.AUX_SCOPE_SHA256)
        self.assertFalse(receipt['saved_game_load_admitted'])

        with self.assertRaisesRegex(ValueError, 'host-global'):
            source.verify_xp2_live(base, read, host_pointer=host_pointer + 8,
                                   auxiliary_pointer=auxiliary_pointer)
        with self.assertRaisesRegex(ValueError, 'auxiliary-global'):
            source.verify_xp2_live(base, read, host_pointer=host_pointer,
                                   auxiliary_pointer=auxiliary_pointer + 8)

        def altered(address, size):
            value = read(address, size)
            if address == base + source.AUX_SCOPE_RVA:
                return value[:-1] + bytes([value[-1] ^ 1])
            return value

        with self.assertRaisesRegex(ValueError, 'live wrapper bytes'):
            source.verify_xp2_live(base, altered, host_pointer=host_pointer,
                                   auxiliary_pointer=auxiliary_pointer)

    def test_install_dispatch_and_revalidation_use_the_actual_xp2_owner(self):
        host = _Host()
        base = 0x200000000
        address = 0xA0000
        name = b'AutoPlayEnd'
        runtime_host = SimpleNamespace(LAB_Aux90DispatchCategoryNull=Mock())
        runtime = SimpleNamespace(
            host=runtime_host, service_owner=host, registry=SimpleNamespace(_check=Mock()),
            dispatch_aux_event_category_null=Mock(return_value='call_returned'),
            dispatch_game_event_result=Mock(return_value=(True, 0)))
        service = ScriptEventService(host, runtime)

        def read(pointer, size):
            if (pointer, size) == (base + source.AUX_SCOPE_RVA, source.AUX_SCOPE_LENGTH):
                return self.raw
            if (pointer, size) == (base + source.HOST_GLOBAL_RVA, 8):
                return host.pointer.to_bytes(8, 'little')
            if (pointer, size) == (base + source.AUX_GLOBAL_RVA, 8):
                return C.addressof(host.aux_object).to_bytes(8, 'little')
            if size == 1 and address <= pointer <= address + len(name):
                return (name + b'\0')[pointer-address:pointer-address+1]
            raise AssertionError((hex(pointer), size))

        table = C.addressof(host.aux_vtable)
        previous_aux90 = (host.aux_vtable[0x90//8], host._slot_bindings.get((table, 0x90)))
        service.install_postload_aux90_null(SimpleNamespace(_handle=base),
                                              core_sha256=source.XP2_CORE_SHA256,
                                              read=read)
        receipt = service.validate_postload_aux90(
            SimpleNamespace(_handle=base), core_sha256=source.XP2_CORE_SHA256, read=read)
        self.assertEqual(receipt['source_proof']['core_sha256'], source.XP2_CORE_SHA256)
        self.assertTrue(receipt['dependencies'])
        self.assertIs(service.dispatch_postload_aux90_null(
            C.addressof(host.aux_object), 1, address, None), True)
        runtime.dispatch_aux_event_category_null.assert_called_once_with(name, category=2)
        self.assertEqual(service.dispatch_depth, 0)
        service.close()
        self.assertEqual(host.aux_vtable[0x90//8], previous_aux90[0])
        self.assertEqual(host._slot_bindings.get((table, 0x90)), previous_aux90[1])

    def test_source_and_global_failure_happen_before_callback_binding(self):
        for bad_read in (
            lambda address, size: b'X' * size,
            lambda address, size: (0x90100).to_bytes(8, 'little') if address >= 0x200000000 + source.HOST_GLOBAL_RVA else self.raw,
            lambda address, size: (0x90100).to_bytes(8, 'little') if address == 0x200000000 + source.AUX_GLOBAL_RVA else (0x90000).to_bytes(8, 'little') if address == 0x200000000 + source.HOST_GLOBAL_RVA else self.raw,
        ):
            host = _Host()
            runtime = SimpleNamespace(host=SimpleNamespace(LAB_Aux90DispatchCategoryNull=Mock()),
                service_owner=host, registry=SimpleNamespace(_check=Mock()),
                dispatch_game_event_result=Mock())
            service = ScriptEventService(host, runtime)
            before = dict(host._slot_bindings)
            function_count = len(host.functions)
            with self.assertRaises(ValueError):
                service.install_postload_aux90_null(SimpleNamespace(_handle=0x200000000),
                    core_sha256=source.XP2_CORE_SHA256, read=bad_read)
            self.assertEqual(host._slot_bindings, before)
            self.assertEqual(len(host.functions), function_count)
            self.assertNotIn('aux90_installed', service.__dict__)


if __name__ == '__main__':
    unittest.main()

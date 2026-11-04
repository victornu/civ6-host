"""Grouped cache-facade ABI regressions; all call results use offline fixtures.

The Base cases are retained verbatim with only their import namespace mapped to
the installed host. XP1 instruction/owner fixtures exercise the actual validators,
but copied source bytes and mock calls are not evidence of native execution.
"""
from __future__ import annotations

import ast
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import cache_facade_profiles as profiles
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256
from civ6_host.runtime.native import native_ui_cache_facades as facades_module
from civ6_host.runtime.native import native_ui_cache_backend as backend_module
from civ6_host.runtime.paths import resource_root


def retained_base_tests():
    path = resource_root() / 'tests/test_native_ui_cache_facades.py'
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'civ6rl.native_ui_cache_facades':
            node.module = 'civ6_host.runtime.native.native_ui_cache_facades'
    namespace = {'__name__': '_retained_base_cache_facade_tests', '__file__': str(path)}
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace['TestNativeUiCacheFacades']


RetainedBaseFacadeTests = retained_base_tests()


class XP1FixtureBackend:
    """Byte-addressed fake memory and calls; no ctypes/native dispatch."""
    core_base = 0x180000000
    outer = 0x1000
    inner, service, owner, member, game = 0x10000, 0x20000, 0x30000, 0x50000, 0x60000

    def __init__(self, *, overrun=False):
        self.abi = profiles.facade_abi(XP1_CORE_SHA256)
        self.memory = {}
        self.calls, self.gates = [], []
        self.alive, self.overrun = True, overrun
        self.b0_results, self.c0_results = [0x74000, 0x74100], [0x75000, 0x75100]
        self.output = bytes(range(24)) + struct.pack('<I', 0xA5C30017)
        self.retained = None
        p = profiles.source()['profile']
        for name in p['live_body_sources']:
            body, address_field = profiles.body(name)
            for fragment in body['fragments']:
                for instruction in fragment['instructions']:
                    address = instruction[address_field]
                    address = int(address, 16) if isinstance(address, str) else address
                    rva = address - 0x180000000 if address_field == 'va' else address
                    self.put(self.core_base + rva, bytes.fromhex(instruction['bytes']))
        for row in p['targets']:
            self.q(self.core_base + row['vtable_rva'] + row['slot'], self.core_base + row['target_rva'])
        for address, value in (
            (self.outer, self.core_base + p['outer_vtable_rva']), (self.outer + 8, self.inner),
            (self.inner, self.core_base + 0x8D7168), (self.core_base + 0x9F2620, self.inner),
            (self.inner + 0x1A68, self.service), (self.core_base + 0x9F22E0, self.service),
            (self.service, self.core_base + 0x8D7238), (self.service + 8, self.owner),
            (self.owner, self.core_base + 0x867788), (self.owner + 0x20, self.service),
            (self.inner + 0x60, self.game), (self.core_base + 0x9F2628, self.game),
            (self.owner + p['ownership']['owner_cache_member_offset'], self.member),
            (self.member, self.core_base + p['ownership']['cache_member_vtable_rva']),
            (self.member + p['ownership']['cache_member_owner_offset'], self.owner),
        ):
            self.q(address, value)
        self.identity = profiles.context_state(self.core_base, self.outer, self.read)
        for pointer, vtable, owner in (
            (0x71000, self.abi.game_facade_vtable_rva, self.owner),
            (0x72000, self.abi.cache_service_vtable_rva, self.member),
            (0x73000, self.abi.system_facade_vtable_rva, self.identity['system_member']),
            *((ptr, self.abi.cache_b0_result_vtable_rva, self.identity['b0_result_owner']) for ptr in self.b0_results),
            *((ptr, self.abi.cache_c0_result_vtable_rva, self.identity['c0_result_owner']) for ptr in self.c0_results),
        ):
            self.put(pointer, struct.pack('<QQQI', self.core_base + vtable, 0, owner, 1) + b'\xCD' * 4)

    def put(self, address, raw):
        self.memory.update((address + index, byte) for index, byte in enumerate(raw))

    def q(self, address, value):
        self.put(address, struct.pack('<Q', value))

    def read(self, address, size):
        return bytes(self.memory[address + offset] for offset in range(size))

    def read_qword(self, address):
        return struct.unpack('<Q', self.read(address, 8))[0]

    def context_alive(self):
        return self.alive

    def set_public_cache_gate(self, enabled):
        self.gates.append(enabled)
        self.calls.append(('gate', enabled))

    def target(self, vtable, slot):
        return self.core_base + self.abi.targets[(vtable, slot)]

    def call(self, target, *args):
        a = self.abi
        self.calls.append((target, *args))
        if target == self.target(a.outer_vtable_rva, 0xA0):
            return 0x71000
        if target == self.target(a.outer_vtable_rva, 0xB0):
            return 0x72000
        if target == self.target(a.outer_vtable_rva, 0xD0):
            return 0x73000
        if target == self.target(a.cache_service_vtable_rva, 0xE8):
            receiver, output = args
            assert receiver == 0x72000 and len(output) == 32
            output[:28] = self.output
            if self.overrun:
                output[28] ^= 0xFF
            return struct.unpack_from('<I', self.output, 24)[0]
        if target == self.target(a.cache_service_vtable_rva, 0xB0):
            return self.b0_results.pop(0)
        if target == self.target(a.cache_service_vtable_rva, 0xC0):
            return self.c0_results.pop(0)
        if target - self.core_base in a.release_rvas:
            if self.retained is not None:
                if args[0] == 0x74000:
                    assert self.retained.cache_b0_result == 0x74100
                if args[0] == 0x75000:
                    assert self.retained.cache_c0_result == 0x75100
            return None
        raise AssertionError(f'Unexpected mocked facade target {target:#x}')

    def acquire(self):
        result = facades_module.NativeUiCacheFacades(self, self.outer, core_sha256=XP1_CORE_SHA256)
        self.retained = result
        return result


class CacheFacadeProfileTests(unittest.TestCase):
    def test_explicit_engine_profile_and_immutable_target_table(self):
        base = profiles.facade_abi(BASE_CORE_SHA256)
        xp1 = profiles.facade_abi(XP1_CORE_SHA256)
        self.assertTrue(base.full_refresh_admitted)
        self.assertFalse(xp1.full_refresh_admitted)
        self.assertEqual(len(xp1.targets), 13)
        self.assertNotEqual(base.outer_vtable_rva, xp1.outer_vtable_rva)
        with self.assertRaises(TypeError):
            xp1.targets[(0, 0)] = 0
        with self.assertRaisesRegex(ValueError, 'Unqualified'):
            profiles.facade_abi('0' * 64)

    def test_static_source_closure_and_body_address_domains(self):
        source = profiles.source()
        self.assertFalse(source['validation']['native_execution'])
        self.assertFalse(source['profile']['full_refresh_admitted'])
        profiles.verify_pinned_files(profiles.source_pins())
        profiles.verify_extracted_sources(source['source_pins'].values())
        fields = set()
        for name in source['profile']['live_body_sources']:
            body, field = profiles.body(name)
            fields.add(field)
            instructions = [i for fragment in body['fragments'] for i in fragment['instructions']]
            self.assertTrue(instructions, name)
            self.assertTrue(all(i[field] and bytes.fromhex(i['bytes']) for i in instructions), name)
        self.assertEqual(fields, {'va', 'rva'})

    def test_xp1_copy_reuses_result_replacement_and_release_order_without_publication(self):
        backend = XP1FixtureBackend()
        retained = backend.acquire()
        profiles.check_facades(retained, backend.identity, backend.read)
        first = retained._copy_cache_outputs()
        profiles.check_facades(retained, backend.identity, backend.read)
        second = retained._copy_cache_outputs()
        self.assertEqual((first.output, second.output), (backend.output, backend.output))
        self.assertEqual(first.copied_value, 0xA5C30017)
        self.assertEqual((retained.cache_b0_result, retained.cache_c0_result), (0x74100, 0x75100))
        self.assertEqual(backend.gates, [])
        self.assertNotIn(backend.core_base + backend.abi.publish_rva, [row[0] for row in backend.calls])
        retained.close()
        self.assertEqual(backend.gates, [False])
        releases = [row[1] for row in backend.calls if type(row[0]) is int and
                    row[0] - backend.core_base in backend.abi.release_rvas]
        self.assertEqual(releases, [0x74000, 0x75000, 0x74100, 0x75100, 0x71000, 0x72000, 0x73000])
        before = len(backend.calls)
        retained.close()
        self.assertEqual(len(backend.calls), before)
        self.assertTrue(retained._closed)
        self.assertEqual(retained.outer, 0)

    def test_xp1_refresh_refuses_before_any_call_or_public_gate(self):
        backend = XP1FixtureBackend()
        retained = backend.acquire()
        count = len(backend.calls)
        with self.assertRaises((RuntimeError, ValueError)):
            retained.refresh()
        self.assertEqual(len(backend.calls), count)
        self.assertFalse(backend.gates)
        retained.close()

    def test_xp1_backend_refuses_publish_and_unknown_targets_before_ctypes(self):
        core = SimpleNamespace(_handle=0x180000000)
        backend = backend_module.NativeCacheFacadeBackend(core, lambda enabled: None,
            context_alive=lambda: True, read=lambda address, size: b'\0' * size, core_sha256=XP1_CORE_SHA256)
        with patch.object(backend_module.C, 'WINFUNCTYPE', side_effect=AssertionError('native call forbidden')) as native:
            with self.assertRaises((RuntimeError, ValueError)):
                backend.call(core._handle + backend.abi.publish_rva, 0x71000, 1)
            with self.assertRaisesRegex(ValueError, 'Unverified'):
                backend.call(core._handle + 0x1234, 0x71000)
            native.assert_not_called()

    def test_copy_canary_failure_stops_before_result_factories(self):
        backend = XP1FixtureBackend(overrun=True)
        retained = backend.acquire()
        with self.assertRaisesRegex(BufferError, 'past its proven'):
            retained._copy_cache_outputs()
        self.assertEqual((retained.cache_b0_result, retained.cache_c0_result), (0, 0))
        self.assertEqual(backend.b0_results, [0x74000, 0x74100])
        self.assertFalse(backend.gates)

    def test_live_instruction_change_refuses_before_acquisition(self):
        backend = XP1FixtureBackend()
        name = next(iter(profiles.source()['profile']['live_body_sources']))
        body, field = profiles.body(name)
        instruction = body['fragments'][0]['instructions'][0]
        address = instruction[field]
        address = int(address, 16) if type(address) is str else address
        address = backend.core_base + (address - 0x180000000 if field == 'va' else address)
        backend.memory[address] ^= 1
        with self.assertRaisesRegex(ValueError, 'instructions differ'):
            backend.acquire()
        self.assertFalse(backend.calls)

    def test_live_slot_change_refuses_before_acquisition(self):
        backend = XP1FixtureBackend()
        backend.q(backend.core_base + backend.abi.outer_vtable_rva + 0xD0, 0)
        with self.assertRaisesRegex(ValueError, 'virtual target differs'):
            backend.acquire()
        self.assertFalse(backend.calls)

    def test_owner_change_refuses_before_acquisition(self):
        backend = XP1FixtureBackend()
        backend.q(backend.member + 0x20, backend.owner + 8)
        with self.assertRaisesRegex(ValueError, 'missing, foreign or replaced'):
            backend.acquire()
        self.assertFalse(backend.calls)

    def test_result_reference_owner_and_branch_are_validated(self):
        backend = XP1FixtureBackend()
        retained = backend.acquire()
        retained._copy_cache_outputs()
        pointer = retained.cache_b0_result
        original = backend.read(pointer, 32)
        for offset, raw in ((8, struct.pack('<Q', backend.game)),
                            (16, struct.pack('<Q', backend.identity['c0_result_owner'])),
                            (24, struct.pack('<I', 2))):
            with self.subTest(offset=offset):
                backend.put(pointer, original)
                backend.put(pointer + offset, raw)
                with self.assertRaisesRegex(ValueError, 'branch/owner/reference count differs'):
                    profiles.check_facades(retained, backend.identity, backend.read)

    def test_dead_context_prevents_copy_and_release_calls(self):
        backend = XP1FixtureBackend()
        retained = backend.acquire()
        count = len(backend.calls)
        backend.alive = False
        with self.assertRaisesRegex(RuntimeError, 'not alive'):
            retained._copy_cache_outputs()
        with self.assertRaisesRegex(RuntimeError, 'not alive'):
            retained.close()
        self.assertEqual(len(backend.calls), count)


if __name__ == '__main__':
    unittest.main()

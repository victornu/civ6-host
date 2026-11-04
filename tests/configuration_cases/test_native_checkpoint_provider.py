"""Pure guards and local Win64 callback ABI tests. Never loads GameCore.

The fake source supplies pinned instruction bytes and synthetic object headers;
only Win64Stream callbacks run, against Python-owned local buffers. Failure
cases after entry run in subprocesses because production intentionally exits.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from civ6_host.runtime.native import native_checkpoint_provider as d

PAYLOAD = b'local ABI transport fixture: no native provider serialization'
BUDGET = dict(max_bytes=4096, max_calls=32)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Fixture:
    def __init__(self, proof):
        self.base, self.context, self.inner = 0x180000000, 0x10000000, 0x11000000
        self.a, self.b_children, self.a_children = 0x12000000, 0x20000000, 0x21000000
        self.bytes, self.calls = {}, []
        self.thread_id = (threading.get_ident(), 777)
        self.fault = None
        self.owner = object.__new__(d.NativeApplicationConfiguration)
        o = self.owner
        from civ6_host.runtime.configuration_profiles import configuration_abi
        o._configuration_abi = configuration_abi(d.CORE_SHA256)
        o.base, o.context, o.closed, o.call = self.base, self.context, False, None
        o.new_game_entered, o.source_provider = False, self.a
        o.storage = C.create_string_buffer(d.application.STORAGE_SIZE + 32)
        o.pointer = C.addressof(o.storage) + 16
        C.memmove(C.addressof(o.storage), d.application._GUARD, 16)
        C.memmove(o.pointer + d.application.STORAGE_SIZE, d.application._GUARD, 16)
        C.memmove(o.pointer, struct.pack('<Q', self.base + d.VTABLE_RVA), 8)
        self.core = SimpleNamespace(_handle=self.base, _civ6rl_application_configuration=o)
        self.putq(self.context, self.base + 0x79E020)
        self.putq(self.context + 8, self.inner)
        self.putq(self.inner, self.base + 0x7C7078)
        self.putq(self.inner + 0xD80 + 0x80, self.a)
        self.putq(self.inner + 0x60, 0)
        for pointer in (self.a, *(self.a_children + i * 0x100 for i in range(66)),
                        *(self.b_children + i * 0x100 for i in range(66))):
            self.put(pointer, struct.pack('<Q', self.base + d.VTABLE_RVA) + bytes(0x50))
        for slot, rva in (d.METHODS | d.DEPENDENCY_SLOTS).items():
            self.putq(self.base + d.VTABLE_RVA + slot, self.base + rva)
        for ins in d._instructions(proof['captures']['core']):
            self.put(self.base + int(ins['va'], 16) - d.CORE_BASE, bytes.fromhex(ins['bytes']))
        app_proof = d.application.verify_source()
        for name in d.application._LIVE:
            for fragment in app_proof['core_functions'][name]['fragments']:
                for ins in fragment['instructions']:
                    self.put(self.base + int(ins['va'], 16) - d.CORE_BASE, bytes.fromhex(ins['bytes']))
        self.memory = d.LocalMemory()
        o.read = self.read

    def put(self, address, raw):
        self.bytes.update((address + n, byte) for n, byte in enumerate(raw))

    def putq(self, address, value):
        self.put(address, struct.pack('<Q', value))

    def read(self, address, length):
        if all(address + n in self.bytes for n in range(length)):
            return bytes(self.bytes[address + n] for n in range(length))
        return self.memory.read(address, length)

    def thread(self):
        # Model real thread binding while retaining deterministic fake OS ID.
        return (threading.get_ident(), self.thread_id[1])

    def image(self, base, proof):
        assert base == self.base
        self.image_checked = True
        return proof['images']['core']['path']

    def snapshot(self, base, pointer, read, *, core_sha256=d.CORE_SHA256):
        assert core_sha256 == d.CORE_SHA256
        assert base == self.base
        if pointer == self.owner.pointer:
            start = self.b_children
        elif pointer == self.a:
            start = self.a_children
        else:
            raise ValueError('Unknown fake provider')
        return {'descriptor': pointer, 'normalized': start, 'map_normalized': start + 0x100,
                'players': tuple(start + i * 0x100 for i in range(2, 66))}

    def invoke(self, address, pointer, stream, mode):
        self.calls.append((address, pointer, mode))
        assert pointer == self.owner.pointer
        assert address == self.base + d.METHODS[0x1F0 if mode == 'writer' else 0x1E8]
        if self.fault == 'invoke':
            raise RuntimeError('entered fake method error')
        if self.fault == 'reenter':
            d.serialize_provider(self.core, self.context, self.owner, **BUDGET)
        table = C.c_void_p.from_address(stream).value
        if mode == 'writer':
            write = C.WINFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p, C.c_uint64)(
                C.c_void_p.from_address(table + 0x28).value)
            for chunk in (PAYLOAD[:4], PAYLOAD[4:]):
                storage = C.create_string_buffer(chunk)
                if write(stream, C.addressof(storage), len(chunk)) != 0:
                    raise AssertionError('Local writer ABI result differs')
        else:
            read = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint64)(
                C.c_void_p.from_address(table + 0x30).value)
            sync = C.WINFUNCTYPE(None, C.c_void_p)(C.c_void_p.from_address(table + 0x40).value)
            length = len(PAYLOAD) + (1 if self.fault == 'short' else 0)
            if self.fault == 'partial':
                length -= 1
            request = C.create_string_buffer(struct.pack('<5Q', d.UINT64_MAX, length, 16, 0, 0))
            target = C.create_string_buffer(length)
            read(stream, C.addressof(request), C.addressof(target), length)
            sync(stream)
            self.restored_bytes = target.raw
        if self.fault == 'header':
            C.memmove(self.owner.pointer + 0x50, struct.pack('<I', 99), 4)
        elif self.fault == 'A':
            self.a_children += 0x100000
        elif self.fault == 'canary':
            C.memmove(self.owner.pointer - 1, b'\0', 1)
        return 0xDEADBEEF  # Deliberately ignored, never a provider status.


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = d.verify_source()

    def setUp(self):
        d._STATES.clear()
        self.fixture = Fixture(self.proof)
        self.patches = [patch.object(d, '_Runtime', return_value=self.fixture),
                        patch.object(d.application, 'provider_snapshot', self.fixture.snapshot)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(d._STATES.clear)

    def serialize(self, **limits):
        f = self.fixture
        return d.serialize_provider(f.core, f.context, f.owner, **(BUDGET | limits))

    def restore(self, raw=PAYLOAD, sha=None, **limits):
        f = self.fixture
        return d.restore_provider(f.core, f.context, f.owner, raw,
                                  expected_sha256=digest(raw) if sha is None else sha,
                                  **(BUDGET | limits))

    def test_actual_pins_and_distinct_third_argument_contract(self):
        self.assertEqual(self.proof['schema'], 'civ6rl.native_checkpoint_configuration_stream.static.v3')
        self.assertIn('optional void*', self.proof['registration_and_callers']['provider_wrappers']['read']['core_third_argument'])
        with patch.object(d, 'PROOF_SHA256', '0' * 64):
            with self.assertRaises((RuntimeError, FileNotFoundError)):
                d.verify_source()

    def test_serialize_uses_native_path_and_ignores_status_keeps_stream_closed_alive(self):
        raw, receipt = self.serialize()
        self.assertEqual(raw, PAYLOAD)
        self.assertEqual(receipt['sha256'], digest(PAYLOAD))
        self.assertFalse(receipt['native_return_interpreted'])
        self.assertFalse(receipt['all_property_values_compared'])
        self.assertEqual(receipt['writer_flags32'], 0)
        state = d._STATES[id(self.fixture.owner)]
        self.assertIs(state.owner, self.fixture.owner)
        self.assertTrue(state.streams[0].transport.closed)
        self.assertEqual(len(self.fixture.calls), 1)

    def test_restore_consumes_and_is_single_use_even_after_save(self):
        receipt = self.restore()
        self.assertEqual(self.fixture.restored_bytes, PAYLOAD)
        self.assertIsNone(receipt['reader_optional_pointer'])
        self.assertFalse(receipt['native_method_result_observed'])
        with self.assertRaisesRegex(ValueError, 'unused owned B'):
            self.restore()
        self.serialize()
        with self.assertRaises(ValueError):
            self.restore()

    def test_seal_forbids_restore_but_not_save(self):
        f = self.fixture
        d.seal_restoration(f.core, f.context, f.owner, **BUDGET)
        with self.assertRaisesRegex(ValueError, 'unused owned B'):
            self.restore()
        self.serialize()

    def test_live_game_and_newgame_flag_refuse_before_stream_or_mutation(self):
        f = self.fixture
        f.putq(f.inner + 0x60, 0x50000000)
        with self.assertRaisesRegex(ValueError, 'unused owned B'):
            self.restore()
        self.assertFalse(f.calls)
        f.putq(f.inner + 0x60, 0)
        f.owner.new_game_entered = True
        with self.assertRaises(ValueError):
            self.restore()
        self.assertFalse(f.calls)

    def test_bad_input_hash_type_and_bounds_refuse_before_native_entry(self):
        for raw, sha in ((PAYLOAD, '0'*64), (b'123', digest(b'123')),
                         (bytearray(PAYLOAD), digest(PAYLOAD)), (PAYLOAD, digest(PAYLOAD).upper())):
            with self.subTest(raw=type(raw), sha=sha):
                with self.assertRaises(ValueError):
                    self.restore(raw, sha)
        self.assertFalse(self.fixture.calls)

    def test_limits_rechecked_on_existing_session_not_bool_int_equality(self):
        self.serialize()
        for limits in ({'max_bytes': True}, {'max_calls': True}, {'max_calls': 32.0},
                       {'max_bytes': 0}, {'max_calls': -1}, {'max_bytes': 4097}):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.serialize(**limits)
        self.assertEqual(len(self.fixture.calls), 1)

    def test_wrong_owner_context_and_injected_call_rejected(self):
        f = self.fixture
        with self.assertRaises(ValueError):
            d.serialize_provider(f.core, True, f.owner, **BUDGET)
        with self.assertRaises(ValueError):
            d.serialize_provider(f.core, f.context + 8, f.owner, **BUDGET)
        f.owner.call = lambda: None
        with self.assertRaises(ValueError):
            self.serialize()
        f.owner.call = None
        f.core._civ6rl_application_configuration = object()
        with self.assertRaises(ValueError):
            self.serialize()
        self.assertFalse(f.calls)

    def test_A_alias_vtable_and_guard_rejected(self):
        f = self.fixture
        f.putq(f.inner + 0xD80 + 0x80, f.owner.pointer)
        with self.assertRaisesRegex(ValueError, 'never A or Game'):
            self.serialize()
        f.putq(f.inner + 0xD80 + 0x80, f.a)
        f.putq(f.base + d.VTABLE_RVA + 0x1E8, f.base + 0x746210)
        with self.assertRaisesRegex(ValueError, 'slot differs'):
            self.serialize()
        f.putq(f.base + d.VTABLE_RVA + 0x1E8, f.base + 0x7502D0)
        C.memmove(f.owner.pointer - 1, b'\0', 1)
        with self.assertRaisesRegex(RuntimeError, 'storage'):
            self.serialize()
        self.assertFalse(f.calls)

    def test_live_code_rechecked_between_calls(self):
        self.serialize()
        self.fixture.put(self.fixture.base + 0x7502D0, b'\x90')
        with self.assertRaisesRegex(ValueError, 'instruction mismatch'):
            self.serialize()
        self.assertEqual(len(self.fixture.calls), 1)

    def test_cross_thread_refused_without_native_call(self):
        self.serialize()
        errors = []
        def other_thread():
            try:
                self.serialize()
            except Exception as e:
                errors.append(e)
        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertIn('different bound thread', str(errors[0]))
        self.assertEqual(len(self.fixture.calls), 1)

    def test_failure_after_stream_construction_before_entry_closes_stream(self):
        state = d._session(self.fixture.core, self.fixture.context, self.fixture.owner, **BUDGET)
        original = state._validate_owner
        count = 0
        def guarded(restoring):
            nonlocal count
            count += 1
            if count == 3:
                raise RuntimeError('preentry failure')
            return original(restoring)
        with patch.object(state, '_validate_owner', guarded), self.assertRaisesRegex(RuntimeError, 'preentry'):
            self.serialize()
        self.assertEqual(len(state.streams), 1)
        self.assertTrue(state.streams[0].transport.closed)
        self.assertFalse(state.poisoned)
        self.assertFalse(self.fixture.calls)


class LocalAbiAndImageTests(unittest.TestCase):
    def test_real_invoke_prototypes_on_local_callbacks(self):
        runtime = object.__new__(d._Runtime)
        calls = []
        writer_type = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint32)
        reader_type = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p)
        writer = writer_type(lambda p, s, flags: calls.append(('writer', p, s, flags)))
        reader = reader_type(lambda p, s, optional: calls.append(('reader', p, s, optional)))
        self.assertIsNone(runtime.invoke(C.cast(writer, C.c_void_p).value, 0x1234, 0x5678, 'writer'))
        self.assertIsNone(runtime.invoke(C.cast(reader, C.c_void_p).value, 0x1234, 0x5678, 'reader'))
        self.assertEqual(calls, [('writer', 0x1234, 0x5678, 0), ('reader', 0x1234, 0x5678, None)])

    def test_actual_module_path_and_file_hash_both_required(self):
        # Existing source files stand in for module files; neither is loaded.
        first, second = Path(d.__file__), Path(__file__)
        runtime = object.__new__(d._Runtime)
        returned = [first]
        def get_path(base, target, limit):
            target.value = str(returned[0])
            return len(target.value)
        runtime.kernel = SimpleNamespace(GetModuleFileNameW=get_path)
        proof = {'images': {'core': {'path': str(first), 'sha256': d.CORE_SHA256}}}
        with patch.object(Path, 'resolve', side_effect=AssertionError('No metadata canonicalization needed')), \
                patch.object(d, '_sha', return_value=d.CORE_SHA256):
            self.assertEqual(runtime.image(0x1000, proof), os.path.abspath(str(first)))
            returned[0] = second
            with self.assertRaisesRegex(ValueError, 'path differs'):
                runtime.image(0x1000, proof)
        returned[0] = first
        with patch.object(d, '_sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runtime.image(0x1000, proof)
        for rejected in (Path('relative.dll'),first.parent/'..'/first.name):
            returned[0]=rejected
            with self.subTest(path=str(rejected)),self.assertRaisesRegex(ValueError,'traversal-free'):
                runtime.image(0x1000,proof)
        returned[0]=first
        with patch.object(Path,'read_bytes',side_effect=PermissionError('read denied')):
            with self.assertRaises(PermissionError):runtime.image(0x1000,proof)

    def test_entered_failures_exit_and_never_return_as_success(self):
        for fault, expected in (('invoke', 87), ('reenter', 87), ('header', 87),
                                ('A', 87), ('canary', 87), ('partial', 87), ('short', 86)):
            with self.subTest(fault=fault):
                result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                                         '--fatal-case', fault], cwd=ROOT,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, timeout=40)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn('RETURNED_SUCCESS', result.stdout)
                self.assertIn('fatal', result.stderr)


def fatal_case(name):
    fixture = Fixture(d.verify_source())
    fixture.fault = name
    with patch.object(d, '_Runtime', return_value=fixture), \
            patch.object(d.application, 'provider_snapshot', fixture.snapshot):
        if name in ('short', 'partial', 'A'):
            d.restore_provider(fixture.core, fixture.context, fixture.owner, PAYLOAD,
                               expected_sha256=digest(PAYLOAD), **BUDGET)
        else:
            d.serialize_provider(fixture.core, fixture.context, fixture.owner, **BUDGET)
    print('RETURNED_SUCCESS', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--fatal-case':
        fatal_case(sys.argv[2])
    else:
        unittest.main(verbosity=2)

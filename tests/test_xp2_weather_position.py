"""Offline native seam checks; no engine image is loaded or executed."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from civ6_host.runtime import xp2_weather_position as adapter
from civ6_host.runtime.configuration_profiles import _source
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256


class Fixture:
    base = 0x210000000
    context, inner, game = 0x11000, 0x12000, 0x13000
    facade, owner = 0x14000, 0x15000

    def __init__(self, *, cached=False):
        self.memory = {}
        self.calls = []
        self.core = SimpleNamespace(_handle=self.base)
        p = adapter.source()
        for fn in p['functions'].values():
            for body in [fn['body']] + [tail['body'] for tail in fn['out_of_line_tail_jumps']]:
                for row in adapter._rows(body):
                    self.put(self.base+int(row['rva'], 16), bytes.fromhex(row['bytes']))
        for row in p['slots'].values():
            self.qword(self.base+row['table_rva']+row['offset'], self.base+row['target_rva'])
        self.put(self.context, struct.pack('<QQ', self.base+0xA101E8, self.inner))
        self.qword(self.inner+0x60, self.game)
        self.qword(self.game+0x248, self.owner)
        self.put(self.facade, struct.pack('<QQQI4x', self.base+0xA11698,
                                          0 if cached else self.owner,
                                          self.owner if cached else 0, 1))
        # 80 columns / 40 rows / 3200 plot count, with horizontal wrapping.
        self.put(self.owner+0x28, struct.pack('<iii', 80, 40, 3200)+bytes(12)+b'\x01\x00')
        self.alive = True
        self.backend = SimpleNamespace(core_base=self.base, read=self.read,
            context_alive=lambda: self.alive, abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256))
        self.facades = SimpleNamespace(backend=self.backend, cache_service=self.facade)
        self.position_api = {'call_position_index': self.position_index}
        self.index_api = {'get_map': self.get_map, 'lookup_index': self.lookup,
                          'release_map': self.release}

    def put(self, address, raw):
        self.memory.update({address+i: byte for i, byte in enumerate(raw)})

    def qword(self, address, value):
        self.put(address, struct.pack('<Q', value))

    def read(self, address, size):
        return bytes(self.memory[address+i] for i in range(size))

    def get_map(self, context):
        self.calls.append(('get', context))
        return self.facade

    def lookup(self, facade, output, index):
        self.calls.append(('lookup', facade, index))
        # Predetermined native response, deliberately unrelated to Python map math.
        C.memmove(output, struct.pack('<ii', 37, 19), 8)
        return output

    def release(self, facade):
        self.calls.append(('release', facade))

    def position_index(self, target, service, output):
        self.calls.append(('position', target, service, C.string_at(output, 8)))
        C.memmove(output, struct.pack('<ii', 79, 6), 8)
        return 0xF1234567


class XP2WeatherPositionTests(unittest.TestCase):
    def test_source_slots_match_independent_exe_callers_and_native_bodies(self):
        p = adapter.source()
        source = _source((p['references']['foundation_facades']['path'],
                          p['references']['foundation_facades']['sha256']))
        self.assertEqual(source['operations']['outer_map']['target_rva'], '0x590300')
        self.assertEqual(source['operations']['optional_position']['target_rva'], '0x59b440')
        native = {row['rva']: row['text'] for row in adapter._rows(p['functions']['index_to_position']['body'])}
        self.assertEqual(native['0x59b451'], 'cmp r8d, dword ptr [r10 + 0x30]')
        self.assertEqual(native['0x59b45b'], 'idiv dword ptr [r10 + 0x28]')
        self.assertEqual(native['0x59b45f'], 'mov dword ptr [r9 + 4], eax')
        self.assertEqual(native['0x59b466'], 'mov dword ptr [r9], edx')
        calls = {row['va']: row['bytes'] for row in adapter._rows(p['callers']['exe_14d550']['capture'])}
        self.assertEqual(calls['0x14014d70a'], '41ff9090000000')
        self.assertEqual(calls['0x14014d711'], '894507')
        normalize = [row['text'] for row in adapter._rows(p['functions']['position_index']['body'])]
        self.assertIn('call 0x18059b2f0', normalize)
        self.assertIn('mov qword ptr [rbx], r8', normalize)
        self.assertIn('mov rax, qword ptr [rdi + 0x10]', normalize)
        for path, sha in adapter.source_dependencies().items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), sha)

    def test_position_query_preserves_exact_eax_and_native_normalization(self):
        for cached in (False, True):
            with self.subTest(cached=cached):
                f = Fixture(cached=cached)
                result = adapter.query_native_position_index(f.core, f.facades, (-1, 6),
                                                            native_api=f.position_api)
                self.assertEqual(result, adapter.PositionIndexResult(0xF1234567, 79, 6))
                self.assertEqual(result.position_bytes, struct.pack('<ii', 79, 6))
                self.assertEqual(f.calls, [('position', f.base+0x59B590, f.facade,
                                           struct.pack('<ii', -1, 6))])

    def test_index_query_acquires_live_map_copies_native_pair_then_releases(self):
        f = Fixture()
        result = adapter.query_native_index_to_position(f.core, f.context, 123,
                                                        read=f.read, native_api=f.index_api)
        self.assertEqual(result, struct.pack('<ii', 37, 19))
        self.assertEqual(f.calls, [('get', f.context), ('lookup', f.facade, 123),
                                   ('release', f.facade)])

    def test_invalid_signed_indices_refused_before_acquire(self):
        for index in (True, -1, 0x80000000, 0xFFFFFFFF, 1.0):
            f = Fixture()
            with self.subTest(index=index), self.assertRaises(ValueError):
                adapter.query_native_index_to_position(f.core, f.context, index,
                                                        read=f.read, native_api=f.index_api)
            self.assertEqual(f.calls, [])

    def test_native_bounds_and_invalid_dimensions_release_without_lookup(self):
        for dims, index in [((80, 40, 3200), 3200), ((0, 40, 3200), 0),
                            ((80, 40, -1), 0), ((80, 0, 3200), 0)]:
            f = Fixture()
            f.put(f.owner+0x28, struct.pack('<iii', *dims))
            with self.subTest(dims=dims, index=index), self.assertRaises(ValueError):
                adapter.query_native_index_to_position(f.core, f.context, index,
                                                        read=f.read, native_api=f.index_api)
            self.assertEqual(f.calls, [('get', f.context), ('release', f.facade)])

    def test_cached_or_wrong_owner_map_refused_and_released(self):
        for cached in (False, True):
            f = Fixture(cached=cached)
            if not cached:
                f.qword(f.facade+8, 0xDEADBEEF)
            with self.subTest(cached=cached), self.assertRaises(ValueError):
                adapter.query_native_index_to_position(f.core, f.context, 123,
                                                        read=f.read, native_api=f.index_api)
            self.assertEqual(f.calls, [('get', f.context), ('release', f.facade)])

    def test_canaries_return_pointer_and_query_failure_release_map(self):
        for fail in ('canary', 'pointer', 'exception'):
            f = Fixture()
            def lookup(facade, output, index):
                if fail == 'canary':
                    C.memmove(output+8, b'!', 1)
                    return output
                if fail == 'pointer':
                    return output+8
                raise LookupError('native fixture error')
            f.index_api['lookup_index'] = lookup
            with self.subTest(fail=fail), self.assertRaises((BufferError, ValueError, LookupError)):
                adapter.query_native_index_to_position(f.core, f.context, 123,
                                                        read=f.read, native_api=f.index_api)
            self.assertEqual(f.calls[-1], ('release', f.facade))

    def test_identity_or_dimensions_mutating_during_query_refused(self):
        for mutate in ('owner', 'width'):
            f = Fixture()
            def lookup(facade, output, index):
                f.lookup(facade, output, index)
                if mutate == 'owner':
                    f.qword(f.game+0x248, 0x19000)
                else:
                    f.put(f.owner+0x28, struct.pack('<i', 79))
                return output
            f.index_api['lookup_index'] = lookup
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                adapter.query_native_index_to_position(f.core, f.context, 123,
                                                        read=f.read, native_api=f.index_api)
            self.assertEqual(f.calls[-1], ('release', f.facade))

    def test_b0_owner_engine_and_lifetime_are_required(self):
        for fail in ('engine', 'alive', 'base'):
            f = Fixture()
            if fail == 'engine':
                f.backend.abi.core_sha256 = '0'*64
            elif fail == 'alive':
                f.alive = False
            else:
                f.backend.core_base += 0x1000
            with self.subTest(fail=fail), self.assertRaises(ValueError):
                adapter.query_native_position_index(f.core, f.facades, (0, 0),
                                                    native_api=f.position_api)
            self.assertEqual(f.calls, [])

    def test_b0_native_output_and_lifetime_fail_closed(self):
        for fail in ('canary', 'eax', 'lifetime'):
            f = Fixture()
            def query(target, receiver, output):
                if fail == 'canary':
                    C.memmove(output-1, b'!', 1)
                elif fail == 'lifetime':
                    f.alive = False
                return -1 if fail == 'eax' else 0
            with self.subTest(fail=fail), self.assertRaises((ValueError, RuntimeError, BufferError)):
                adapter.query_native_position_index(f.core, f.facades, (0, 0),
                    native_api={'call_position_index': query})

    def test_changed_native_slot_or_bytes_refused_before_any_call(self):
        for fail in ('slot', 'bytes'):
            f = Fixture()
            if fail == 'slot':
                f.qword(f.base+0xA11698+0x68, f.base+0x59B590)
            else:
                f.put(f.base+0x59B2F0, b'\x90')
            with self.subTest(fail=fail), self.assertRaises(ValueError):
                adapter.query_native_index_to_position(f.core, f.context, 123,
                                                        read=f.read, native_api=f.index_api)
            self.assertEqual(f.calls, [])

    def test_short_checked_read_and_extra_native_seam_are_refused(self):
        f = Fixture()
        with self.assertRaises(ValueError):
            adapter.query_native_index_to_position(f.core, f.context, 123,
                read=lambda address, length: f.read(address, length)[:-1], native_api=f.index_api)
        with self.assertRaises(ValueError):
            adapter.query_native_index_to_position(f.core, f.context, 123,
                read=f.read, native_api=dict(f.index_api, unknown=lambda: None))
        self.assertEqual(f.calls, [])


if __name__ == '__main__':
    unittest.main()

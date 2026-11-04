import ctypes as C
import struct
from types import SimpleNamespace
import unittest

from civ6_host.runtime.native import native_configuration_finalization as m


class NativeDouble:
    def __init__(self, base=0x270000000):
        self.base = base
        self.context = base + 0x2000000
        self.inner = self.context + 0x1000
        self.setup = self.inner + 0xD80
        self.descriptor = self.context + 0x4000
        self.normalized = self.context + 0x5000
        self.map_normalized = self.context + 0x6000
        self.memory = {}
        self.calls = []
        self.preparations = []
        self.initialized = True
        self.returns = {}
        self.after = None
        self.put(self.context, struct.pack('<QQ', base + m.OUTER_VTABLE, self.inner))
        self.qword(self.inner, base + m.INNER_VTABLE)
        self.qword(self.inner + 0x50, self.context + 0x7000)
        self.qword(self.inner + 0x58, self.context + 0x8000)
        self.put(self.setup + 0x80, struct.pack('<QQ', self.descriptor, self.normalized))
        self.put(self.setup + 0xC28, struct.pack('<QQ', self.descriptor, self.map_normalized))
        begin = self.setup + 0xB8
        self.put(self.setup + 0x90, struct.pack('<QQQ', begin, begin + 64 * 32, begin + 64 * 32))
        for obj in (self.descriptor, self.normalized, self.map_normalized):
            self.qword(obj, base + m.CONFIG_VTABLE)
        for slot, rva in ((0x38, 0x42E3A0), *m.PREPARATION):
            self.qword(base + m.OUTER_VTABLE + slot, base + rva)
        for slot, rva in ((0x58, m.LOOKUP_RVA), (0x130, 0x7465A0), (0x178, 0x7450A0)):
            self.qword(base + m.CONFIG_VTABLE + slot, base + rva)
        self.put(base + 0x8BCC58, struct.pack('<I', m.GAME_ROOT_KEY))
        self.put(base + 0x8BCD08, struct.pack('<I', 0xABC00000))
        self.variants = {}
        self.variant(m.GAME_ROOT_KEY, self.normalized)
        self.variant(0xABC00000, self.map_normalized)
        for index in range(64):
            pointer = self.context + 0x10000 + index * 0x100
            self.qword(pointer, base + m.CONFIG_VTABLE)
            self.put(begin + index * 32, struct.pack('<IIQQQ', index, 0xDEADBEEF,
                                                   self.descriptor, pointer, self.setup))
            key = 0xABC00100 + index
            self.put(base + 0x8BCD50 + index * 0x44, struct.pack('<I', key))
            self.variant(key, pointer)
        proof = m.verify_source()
        for name in m._LIVE_BODIES:
            for fragment in proof['core_functions'][name]['fragments']:
                for ins in fragment['instructions']:
                    self.put(base + int(ins['va'], 16) - 0x180000000, bytes.fromhex(ins['bytes']))

    def put(self, address, raw):
        self.memory.update((address + index, byte) for index, byte in enumerate(raw))

    def qword(self, address, value):
        self.put(address, struct.pack('<Q', value))

    def variant(self, key, pointer):
        address = self.context + 0x30000 + len(self.variants) * 0x20
        self.variants[key] = address
        self.put(address, struct.pack('<HHIQ', 0xA, 0x1357, 0xFEDCBA98, pointer))

    def read(self, address, size):
        try:
            return bytes(self.memory[address + offset] for offset in range(size))
        except KeyError as error:
            raise AssertionError(f'Unprovided read {address:#x}/{size}') from error

    def call(self, address, result, args, receiver, *values):
        self.calls.append((address - self.base, result, args, receiver, values))
        if address == self.base + 0x42E3A0:
            assert (result, args, receiver, values) == (C.c_bool, (), self.context, ())
            return self.initialized
        if address == self.base + m.LOOKUP_RVA:
            assert (result, args, receiver) == (C.c_void_p, (C.c_uint32,), self.descriptor)
            return self.variants.get(values[0])
        slot = next(slot for slot, rva in m.PREPARATION if address == self.base + rva)
        assert (result, args, receiver, values) == (C.c_bool, (C.c_void_p,), self.context, (self.descriptor,))
        self.preparations.append(slot)
        if self.after:
            self.after(slot)
        return self.returns.get(slot, True)

    def run(self, **kwargs):
        args = dict(before_new_game=True, configuration_ready=True,
                    read=self.read, call=self.call)
        args.update(kwargs)
        return m.finalize_setup(SimpleNamespace(_handle=self.base), self.context, **args)


class ConfigurationFinalizationTests(unittest.TestCase):
    def test_source_complete_and_distinct_preparation(self):
        p = m.verify_source()
        self.assertEqual(p['validation']['instruction_occurrences_rechecked'], 3371)
        self.assertEqual(tuple(p['contract']['source_order']), (0x140, 0x148, 0x150))
        self.assertEqual(p['core_functions']['configuration_lookup']['reachable_byte_count'], 69)
        self.assertIn('already true before NewGame', p['contract']['initialized_guard'])

    def test_exact_calls_relocated_and_borrowed_descriptor(self):
        for base in (0x180000000, 0x7FFA00000000):
            with self.subTest(base=base):
                fake = NativeDouble(base)
                events = []
                result = fake.run(emit=lambda stage, **kw: events.append((stage, kw)))
                self.assertEqual(fake.preparations, [0x140, 0x148, 0x150])
                self.assertTrue(result['all_returned_true'])
                self.assertEqual(result['player_record_count'], 64)
                self.assertFalse(result['native_new_game_called'])
                self.assertEqual([e[1]['slot'] for e in events], fake.preparations)
                self.assertEqual([row['return_value'] for row in result['call_results']], [True] * 3)

    def test_explicit_protocol_guards_before_reads_or_calls(self):
        for name in ('before_new_game', 'configuration_ready'):
            for value in (False, None, 1, 'true'):
                with self.subTest(name=name, value=value):
                    fake = NativeDouble()
                    with self.assertRaises(ValueError):
                        fake.run(**{name: value})
                    self.assertEqual(fake.calls, [])

    def test_initialized_false_is_not_newgame_guard(self):
        fake = NativeDouble()
        fake.initialized = False
        with self.assertRaisesRegex(ValueError, 'Init must have completed'):
            fake.run()
        self.assertEqual(fake.preparations, [])

    def test_complete_setup_required_before_preparation(self):
        for kind in ('config', 'map', 'player', 'db', 'vector', 'slot', 'code'):
            with self.subTest(kind=kind):
                fake = NativeDouble()
                address = {'config': fake.setup + 0x80, 'map': fake.setup + 0xC30,
                           'player': fake.setup + 0xB8 + 63 * 32 + 0x10,
                           'db': fake.inner + 0x58, 'vector': fake.setup + 0x98,
                           'slot': fake.base + m.OUTER_VTABLE + 0x150,
                           'code': fake.base + 0x42F310}[kind]
                fake.qword(address, 0)
                with self.assertRaises(ValueError):
                    fake.run()
                self.assertEqual(fake.preparations, [])

    def test_exact_linkage_and_tag_not_flags_or_padding(self):
        for kind in ('absent', 'tag', 'pointer', 'map', 'player', 'rootkey'):
            with self.subTest(kind=kind):
                fake = NativeDouble()
                address = fake.variants[m.GAME_ROOT_KEY]
                if kind == 'absent':
                    del fake.variants[m.GAME_ROOT_KEY]
                elif kind == 'tag':
                    fake.put(address, b'\x0b\x00')
                elif kind == 'pointer':
                    fake.qword(address + 8, fake.map_normalized)
                elif kind in ('map', 'player'):
                    key = 0xABC00000 if kind == 'map' else 0xABC00100 + 63
                    fake.qword(fake.variants[key] + 8, fake.normalized)
                else:
                    fake.put(fake.base + 0x8BCC58, b'\x00' * 4)
                with self.assertRaises(ValueError):
                    fake.run()
                self.assertEqual(fake.preparations, [])

    def test_false_result_kept_and_later_calls_not_run(self):
        fake = NativeDouble()
        fake.returns[0x148] = False
        with self.assertRaises(m.FinalizationError) as caught:
            fake.run()
        self.assertEqual(fake.preparations, [0x140, 0x148])
        self.assertEqual([v['return_value'] for v in caught.exception.call_results], [True, False])
        self.assertTrue(caught.exception.native_effects_may_have_occurred)

    def test_identity_changed_after_native_call_refused_without_rollback(self):
        fake = NativeDouble()
        fake.after = lambda slot: fake.qword(fake.variants[m.GAME_ROOT_KEY] + 8, fake.map_normalized)
        with self.assertRaises(m.FinalizationError) as caught:
            fake.run()
        self.assertEqual(fake.preparations, [0x140])
        self.assertTrue(caught.exception.call_results[0]['return_value'])

    def test_short_checked_read_refuses_without_mutation(self):
        fake = NativeDouble()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            fake.run(read=lambda address, size: fake.read(address, size)[:-1])
        self.assertEqual(fake.preparations, [])

    def test_exception_during_first_call_does_not_claim_no_effect(self):
        fake = NativeDouble()
        def fail(slot):
            raise RuntimeError('A real native callback refused')
        fake.after = fail
        with self.assertRaises(m.FinalizationError) as caught:
            fake.run()
        self.assertEqual(caught.exception.call_results, ())
        self.assertEqual(caught.exception.attempted_slots, (0x140,))
        self.assertTrue(caught.exception.native_effects_may_have_occurred)
        self.assertEqual(fake.preparations, [0x140])


if __name__ == '__main__':
    unittest.main()

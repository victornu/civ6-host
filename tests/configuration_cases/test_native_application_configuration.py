import ctypes as C
import importlib
import struct
import unittest
from types import SimpleNamespace

from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.native import native_configuration_finalization as setup


# Import the fixture module, rather than copying its fixture class into this
# module's globals. unittest discovery should execute each test module once.
base_fixture = importlib.import_module('configuration_cases.test_native_configuration_finalization')


class ApplicationDouble(base_fixture.NativeDouble):
    """Extend the existing Core setup fixture with a separately owned provider."""

    def __init__(self, *, corrupt_clone_guard=False):
        super().__init__()
        self.application_calls = []
        self.providers = {}
        self.corrupt_clone_guard = corrupt_clone_guard
        self.variant_serial = 0
        self.storage_ranges = []
        proof = app.verify_source()
        self.root_key = setup.GAME_ROOT_KEY
        self.map_key = struct.unpack('<I', self.read(self.base + 0x8BCD08, 4))[0]
        self.player_keys = tuple(row['hash'] for row in proof['player_keys'])
        self.qword(self.base + app.VTABLE + 0x1D0, self.base + app.ASSIGN)

        # The old finalization fixture uses synthetic player keys. Replace
        # them with the exact pinned application PLAYER_i hashes and native
        # tag-A map variants required by provider_snapshot().
        self.variants.clear()
        self.providers[self.descriptor] = {}
        pairs = ((self.root_key, self.normalized), (self.map_key, self.map_normalized))
        pairs += tuple(zip(self.player_keys, self.player_pointers()))
        for key, pointer in pairs:
            self.providers[self.descriptor][key] = self._variant(key, pointer)
        self.put(self.base + 0x8BCD08, struct.pack('<I', self.map_key))
        for index, key in enumerate(self.player_keys):
            self.put(self.base + 0x8BCD50 + index * 0x44, struct.pack('<I', key))

        # Make every captured instruction that the application and existing
        # setup adapters verify readable at its relocated live address.
        app_proof = app.verify_source()
        for name in app._LIVE:
            for fragment in app_proof['core_functions'][name]['fragments']:
                for ins in fragment['instructions']:
                    self.put(self.base + int(ins['va'], 16) - 0x180000000,
                             bytes.fromhex(ins['bytes']))
        final_proof = setup.verify_source()
        setup._live_code(final_proof, self.base, self.read)

    def player_pointers(self):
        begin = self.setup + 0xB8
        return tuple(struct.unpack_from('<Q', self.read(begin + i * 0x20, 0x20), 16)[0]
                     for i in range(64))

    def _variant(self, key, pointer):
        address = self.context + 0x50000 + self.variant_serial * 0x20
        self.variant_serial += 1
        self.variants[key] = address
        self.put(address, struct.pack('<H6xQ4xI', 0xA, pointer, 0x05000000))
        return address

    def read(self, address, size):
        # Constructor storage is a ctypes buffer, while fixture/source memory
        # lives in the byte map inherited from NativeDouble.
        if address not in self.memory and any(start <= address and address + size <= end
                                               for start, end in self.storage_ranges):
            return C.string_at(address, size)
        return super().read(address, size)

    def call(self, address, result, args, receiver, *values):
        self.application_calls.append((address - self.base, result, args, receiver, values))
        if address == self.base + 0x42E3A0:
            assert (result, args, receiver, values) == (C.c_bool, (), self.context, ())
            return True
        if address == self.base + setup.LOOKUP_RVA:
            assert result is C.c_void_p and args == (C.c_uint32,)
            mapping = self.providers.get(receiver)
            return None if mapping is None else mapping.get(values[0])
        if address == self.base + app.CTOR:
            assert result is C.c_void_p and not args
            self.storage_ranges.append((receiver, receiver + app.STORAGE_SIZE))
            self.qword(receiver, self.base + app.VTABLE)
            self.providers[receiver] = {}
            return receiver
        if address == self.base + app.ASSIGN:
            assert result is C.c_void_p and args == (C.c_void_p,)
            source = self.providers[values[0]]
            copied = {}
            for index, (key, source_node) in enumerate(source.items()):
                clone_pointer = self.context + 0x100000 + len(self.providers) * 0x10000 + index * 0x100
                self.qword(clone_pointer, self.base + app.VTABLE)
                clone_node = self._variant(key, clone_pointer)
                copied[key] = clone_node
            self.last_clone_pointers = tuple(
                struct.unpack_from('<Q', self.read(node, 24), 8)[0]
                for node in copied.values())
            self.providers[receiver] = copied
            if self.corrupt_clone_guard:
                C.c_uint8.from_address(receiver + app.STORAGE_SIZE).value = 0
            return receiver
        if address == self.base + app.DTOR:
            assert result is None and not args
            self.providers.pop(receiver, None)
            return None
        if address in (self.base + 0x42F390, self.base + 0x42F350, self.base + 0x42F310):
            assert (result, args, receiver) == (C.c_bool, (C.c_void_p,), self.context)
            self.preparations.append(address - self.base)
            self.application_calls.append(('prepared_descriptor', values[0]))
            return True
        return super().call(address, result, args, receiver, *values)

    def clone(self):
        return app.NativeApplicationConfiguration(
            SimpleNamespace(_handle=self.base), self.context, read=self.read, call=self.call)


class NativeApplicationConfigurationTests(unittest.TestCase):
    def test_proof_and_pinned_keys(self):
        proof = app.verify_source()
        self.assertEqual(proof['contract']['owned_map_flags'], 0x05000000)
        self.assertEqual(len(proof['player_keys']), 64)
        self.assertEqual(len({row['hash'] for row in proof['player_keys']}), 64)

    def test_copy_has_distinct_root_map_and_player_submaps(self):
        fake = ApplicationDouble()
        source = app.provider_snapshot(fake.base, fake.descriptor, fake.read, fake.call)
        clone = fake.clone()
        try:
            copied = clone.snapshot()
            self.assertEqual(len(copied['players']), 64)
            self.assertEqual(clone.source_provider, fake.descriptor)
            self.assertNotEqual(copied['descriptor'], source['descriptor'])
            self.assertNotEqual(copied['normalized'], source['normalized'])
            self.assertNotEqual(copied['map_normalized'], source['map_normalized'])
            self.assertTrue(set(copied['players']).isdisjoint(source['players']))
            self.assertEqual(app.provider_snapshot(fake.base, fake.descriptor, fake.read, fake.call), source)
            self.assertTrue(any(call[0] == app.CTOR for call in fake.application_calls))
            self.assertIn((app.ASSIGN, C.c_void_p, (C.c_void_p,), clone.pointer,
                           (fake.descriptor,)), fake.application_calls)
        finally:
            clone.close()

    def test_wrong_player_key_refuses_before_copy(self):
        fake = ApplicationDouble()
        address = fake.base + 0x8BCD50 + 7 * 0x44
        fake.put(address, b'\x01\x00\x00\x00')
        with self.assertRaisesRegex(ValueError, 'no source tag-A submap'):
            fake.clone()
        self.assertFalse(any(call[0] == app.CTOR for call in fake.application_calls))
        self.assertFalse(any(call[0] == app.ASSIGN for call in fake.application_calls))

    def test_corrupted_canary_is_detected_after_native_copy(self):
        fake = ApplicationDouble(corrupt_clone_guard=True)
        with self.assertRaisesRegex(RuntimeError, 'storage'):
            fake.clone()
        self.assertTrue(any(call[0] == app.ASSIGN for call in fake.application_calls))

    def test_context_identity_and_double_close_are_rejected(self):
        fake = ApplicationDouble()
        clone = fake.clone()
        clone.require_context(fake.base, fake.context)
        with self.assertRaisesRegex(ValueError, 'another native context'):
            clone.require_context(fake.base, fake.context + 1)
        clone.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            clone.close()

    def test_post_clone_python_error_destroys_verified_provider_once(self):
        fake = ApplicationDouble()
        def fail(*args, **kwargs):
            raise RuntimeError('deliberate emitter failure')
        with self.assertRaisesRegex(RuntimeError, 'emitter failure') as caught:
            app.NativeApplicationConfiguration(SimpleNamespace(_handle=fake.base), fake.context,
                read=fake.read, call=fake.call, emit=fail)
        self.assertTrue(caught.exception.native_configuration_owner.closed)
        self.assertEqual(sum(call[0] == app.DTOR for call in fake.application_calls), 1)

    def test_post_newgame_topology_reacquires_core_and_rejects_application_alias(self):
        fake = ApplicationDouble()
        clone = fake.clone()
        with self.assertRaisesRegex(ValueError, 'after entering'):
            clone.verify_core_copy_topology()
        clone.new_game_entered = True
        self.assertEqual(clone.verify_core_copy_topology()['core_player_records_reacquired'], 64)
        copied_root = clone.snapshot()['normalized']
        native_root_node = fake.providers[fake.descriptor][fake.root_key]
        fake.qword(native_root_node + 8, copied_root)
        fake.qword(fake.setup + 0x88, copied_root)
        with self.assertRaisesRegex(ValueError, 'share an owned submap'):
            clone.verify_core_copy_topology()
        # Restore the memory double's source to avoid an aliased teardown.
        fake.qword(native_root_node + 8, fake.normalized)
        fake.qword(fake.setup + 0x88, fake.normalized)
        clone.close()

    def test_finalize_prepares_clone_in_order_without_mutating_source(self):
        fake = ApplicationDouble()
        clone = fake.clone()
        source_before = app.provider_snapshot(fake.base, fake.descriptor, fake.read, fake.call)
        source_bytes = fake.read(source_before['players'][0], 8)
        try:
            result = setup.finalize_setup(
                SimpleNamespace(_handle=fake.base), fake.context,
                before_new_game=True, configuration_ready=True,
                read=fake.read, call=fake.call, application_configuration=clone)
            self.assertTrue(result['all_returned_true'])
            self.assertEqual(fake.preparations, [0x42F390, 0x42F350, 0x42F310])
            prepared = [row[1] for row in fake.application_calls if row[0] == 'prepared_descriptor']
            self.assertEqual(prepared, [clone.pointer] * 3)
            self.assertEqual(app.provider_snapshot(fake.base, fake.descriptor, fake.read, fake.call),
                             source_before)
            self.assertEqual(fake.read(source_before['players'][0], 8), source_bytes)
            self.assertTrue(clone.new_game_entered is False)
        finally:
            clone.close()


if __name__ == '__main__':
    unittest.main()

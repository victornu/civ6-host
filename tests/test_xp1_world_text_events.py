"""XP1 world-text transport on the composed saved owner; no engine runs."""
import struct
import unittest

from test_xp1_combat_events import Fixture
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import xp1_world_text_profile as profile
from civ6_host.runtime.native import native_event_45b517d6 as event


class WorldTextTests(unittest.TestCase):
    def fixture(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        return fixture

    def fields(self, fixture, *, city=False, text=b'Native message\0'):
        position = fixture.make_blob(struct.pack('<ii', 3, 4), 0)
        descriptor = fixture.make_blob(struct.pack('<HHI', 3, 2 if city else 1, 65536), 1024)
        pointer = fixture.pointer_cursor
        fixture.pointer_cursor += max(0x100, len(text))
        fixture.memory.put(pointer, text)
        string = struct.pack('<H6xQII', 5, pointer, len(text), 0x01000001)
        return {event.POSITION_KEY: position, event.SELECTOR_KEY: scalar(3, 7),
                event.CITY_DESCRIPTOR_KEY if city else event.DESCRIPTOR_KEY: descriptor,
                event.TEXT_KEY: string}

    def test_unit_and_city_copy_before_actual_fifo_drain(self):
        f = self.fixture()
        all_fields = [self.fields(f), self.fields(f, city=True)]
        calls = list(f.calls)
        for fields in all_fields:
            self.assertEqual(f.owner.dispatch(event.EVENT_KIND, fields, 0), 0)
        records = tuple(f.deferred.pending)
        self.assertEqual(len(records), 2)
        for record, city in zip(records, (False, True)):
            self.assertEqual(struct.unpack_from('<II', record), (368, 250))
            self.assertEqual(struct.unpack_from('<I', record, 20)[0], 4 * 8 + 3)
            self.assertEqual(struct.unpack_from('<HHI', record, 56 if city else 24),
                             (3, 2 if city else 1, 65536))
            self.assertEqual(record[100:356], b'Native message\0' + bytes(241))
        # Borrowed native data must not be read again by the deferred consumer.
        for fields in all_fields:
            for key, raw in fields.items():
                if key == event.SELECTOR_KEY:
                    continue
                pointer = struct.unpack_from('<Q', raw, 8)[0]
                f.memory.put(pointer, b'\xff' * (15 if key == event.TEXT_KEY else 8))
        self.assertEqual(f.deferred.drain(), 2)
        self.assertEqual(f.deferred.pending, [])
        self.assertEqual(f.calls, calls)
        self.assertIsNone(f.owner._foundation_borrow)

    def test_native_strncpy_bound(self):
        f = self.fixture()
        self.assertEqual(f.owner.dispatch(event.EVENT_KIND, self.fields(f, text=b'x' * 300 + b'\0'), 0), 0)
        self.assertEqual(f.deferred.pending[0][100:356], b'x' * 256)
        self.assertEqual((f.owner.host_notification_counter, f.owner.host_metadata_counter), (0, 0))
        self.assertEqual(f.deferred.drain(), 1)

    def test_unqualified_notification_scope_is_not_silently_cleared(self):
        f = self.fixture()
        f.deferred.host_notification_counter = 3
        f.deferred.host_metadata_counter = 2
        with self.assertRaisesRegex(ValueError, 'Nonzero native notification metadata scope'):
            f.owner.dispatch(event.EVENT_KIND, self.fields(f), 0)
        self.assertEqual((f.owner.host_notification_counter, f.owner.host_metadata_counter), (3, 2))
        self.assertEqual(f.deferred.pending, [])
        self.assertTrue(f.owner.quarantined)

    def test_missing_or_stale_real_cache_refused_without_gate_off_substitution(self):
        for state in ('missing', 'stale', 'closed'):
            with self.subTest(state=state):
                f = self.fixture()
                if state == 'missing':
                    f.token.publisher.cache_map_snapshot = None
                elif state == 'stale':
                    f.token.publisher.cache_map_snapshot = struct.pack('<iii', 9, 8, 72) + bytes(16)
                else:
                    f.token.lease.poisoned = True
                with self.assertRaises((ValueError, RuntimeError)):
                    f.owner.dispatch(event.EVENT_KIND, self.fields(f), 0)
                self.assertEqual(f.deferred.pending, [])
                self.assertTrue(f.owner.quarantined)
                self.assertIsNone(f.owner._foundation_borrow)

    def test_null_text_and_wrong_descriptor_envelope_refused(self):
        for state in ('null', 'empty_envelope', 'descriptor'):
            with self.subTest(state=state):
                f = self.fixture()
                fields = self.fields(f)
                key = event.DESCRIPTOR_KEY if state == 'descriptor' else event.TEXT_KEY
                raw = bytearray(fields[key])
                if state == 'null':
                    struct.pack_into('<Q', raw, 8, 0)
                elif state == 'empty_envelope':
                    struct.pack_into('<I', raw, 20, 0x01000000)
                else:
                    struct.pack_into('<I', raw, 16, 16)
                fields[key] = bytes(raw)
                with self.assertRaises(ValueError):
                    f.owner.dispatch(event.EVENT_KIND, fields, 0)
                self.assertEqual(f.deferred.pending, [])
                self.assertTrue(f.owner.quarantined)

    def test_live_source_and_synchronous_cache_owner_enforced(self):
        f = self.fixture()
        self.assertEqual(profile.bind_owner(f.backend, f.backend.core, f.read), profile.event_profile())
        with self.assertRaises(ValueError):
            profile.bind_owner(f.backend, object(), f.read)
        with self.assertRaises((ValueError, RuntimeError)):
            profile.cache_snapshot(f.owner)
        with self.assertRaisesRegex(ValueError, 'live instructions'):
            profile.bind_owner(f.backend, f.backend.core, lambda address, size: bytes(size))


if __name__ == '__main__':
    unittest.main()

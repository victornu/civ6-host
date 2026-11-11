"""XP1 district removal uses native queries and the retained exact EXE codec."""
import ctypes as C
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from civ6_host.runtime import a0_district_removed as event
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from test_a0_family_service import A0FamilyServiceTests, PROFILE
source_data = event.source()

def fields():
    return event.codec.EventFields(0, 65536, struct.pack('<ii', 28, 18), 28, 18, 0, 0, 0, struct.pack('<HHI', 0, 3, 65536))

def memory_fixture(*, null_player=False, null_item=False, tables=None):
    base = 6442450944
    memory = {}
    calls = []
    for label, (table, slots) in (event.TABLES if tables is None else tables).items():
        pointer = {'outer': 20480, 'player': 24576, 'collection': 28672, 'item': 32768}[label]
        memory[pointer] = struct.pack('<QQQI', base + table, 589824 + pointer, 0, 1)
        for slot, rva in slots:
            memory[base + table + slot] = struct.pack('<Q', base + rva)

    def read(address, size):
        for start, raw in memory.items():
            if start <= address and address + size <= start + len(raw):
                return raw[address - start:address - start + size]
        raise ValueError('fixture read outside allocated bytes')

    def op(name, result=None):

        def call(*args):
            calls.append((name, args))
            return result
        return call
    api = {name: op(name) for name in event.ENTRIES}
    api.update(get_player=op('get_player', None if null_player else 24576), player_collection=op('player_collection', 28672), collection_index=op('collection_index', None if null_item else 32768), item_raw=op('item_raw', 5))

    def variant(item, out):
        calls.append(('item_variant', (item,)))
        C.memmove(out, struct.pack('<HHI', 0, 2, 22), 8)
        return out
    api['item_variant'] = variant
    return (NS(_handle=base), read, api, calls, memory)

class DistrictTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        A0FamilyServiceTests.setUpClass()

    def setUp(self):
        self.fields = fields()

    def lease(self, fixture, diagnostic=None, **kw):
        core, read, api, _, _ = fixture
        return event.record_lease(19, core, 20480, self.fields, read=read, native_api=api, empty_receiver_state=kw.pop('empty_receiver_state', dict(PROFILE)), query_diagnostic={} if diagnostic is None else diagnostic, **kw)

    def test_source_hash_profile_and_body_dependency_closure(self):
        p = event.source()
        profile = event.event_profile()
        self.assertEqual(profile.record_types_by_kind, {4260438819: frozenset((160,))})
        self.assertEqual(profile.record_sizes, {160: 128})
        self.assertEqual(len(event.source_dependencies()), 6)
        self.assertTrue(p['profile']['unload_flag_cleared_before_player_teardown'])

    def test_positive_native_query_and_exact_existing_codec_with_lease(self):
        f = memory_fixture()
        diagnostic = {}
        with self.lease(f, diagnostic) as record:
            self.assertEqual(record, event.codec.encode_record(19, self.fields, event.codec.NativeValues(struct.pack('<HHI', 0, 2, 22), 5), **event.PROFILE))
            self.assertNotIn('release_item', [r[0] for r in f[3]])
            f[3].append(('enqueue', ()))
        self.assertEqual([r[0] for r in f[3]], ['get_player', 'player_collection', 'collection_index', 'release_collection', 'release_player', 'item_variant', 'item_raw', 'enqueue', 'release_item'])
        self.assertTrue(diagnostic['native_item_queries_executed'])
        self.assertFalse(diagnostic['native_null_result_observed'])

    def test_actual_native_null_player_and_item_are_distinct_from_substitution(self):
        for null_player, reason in ((True, 'player-null'), (False, 'item-null')):
            with self.subTest(reason=reason):
                f = memory_fixture(null_player=null_player, null_item=not null_player)
                d = {}
                with self.lease(f, d) as record:
                    self.assertEqual(record[104:120], bytes(8) + bytes.fromhex('ffff0000ffffffff'))
                self.assertEqual(d['read_skipped_reason'], reason)
                self.assertTrue(d['native_player_query_executed'])
                self.assertFalse(d['native_item_queries_executed'])
                self.assertEqual(f[3][0], ('get_player', (20480, 0)))
                self.assertNotIn('item_raw', [r[0] for r in f[3]])
                self.assertNotIn('release_item', [r[0] for r in f[3]])

    def test_missing_item_cannot_publish_to_nonempty_receiver(self):
        for name, value in (('subscriber_count', 1), ('observer_registered', True), ('state_flags', 1), ('state_pointer_nonnull', False), ('pre_hook', 1), ('post_hook', 1)):
            state = dict(PROFILE)
            state[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                with self.lease(memory_fixture(null_player=True), empty_receiver_state=state):
                    pass

    def test_unknown_cached_or_shared_facades_refuse_without_fabricated_record(self):
        for offset, value, reason in ((0, 123, 'facade'), (8, 0, 'live'), (16, 999, 'live'), (24, 2, 'live')):
            f = memory_fixture()
            raw = bytearray(f[4][32768])
            struct.pack_into('<I' if offset == 24 else '<Q', raw, offset, value)
            f[4][32768] = bytes(raw)
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, reason):
                with self.lease(f):
                    self.fail('invalid item yielded a record')
            self.assertNotIn('item_raw', [r[0] for r in f[3]])

    def test_null_collection_refuses_balancing_known_player(self):
        f = memory_fixture()
        f[2]['player_collection'] = lambda _: None
        with self.assertRaisesRegex(ValueError, 'Missing district'):
            with self.lease(f):
                pass
        self.assertEqual(f[3][-1][0], 'release_player')
        self.assertNotIn('collection_index', [r[0] for r in f[3]])

    def test_enqueue_failure_releases_valid_item(self):
        f = memory_fixture()
        with self.assertRaisesRegex(RuntimeError, 'sink'):
            with self.lease(f):
                raise RuntimeError('sink')
        self.assertEqual(f[3][-1][0], 'release_item')

    def test_native_query_failure_releases_valid_item(self):
        f = memory_fixture()

        def fail(_):
            raise RuntimeError('native query failure')
        f[2]['item_raw'] = fail
        with self.assertRaisesRegex(RuntimeError, 'native query'):
            with self.lease(f):
                pass
        self.assertEqual(f[3][-1][0], 'release_item')

    def test_source_live_verification_covers_instructions_and_vtable_targets(self):
        base = 140668768878592
        reads = {}
        for body in source_data['functions'].values():
            for f in event._body(body)['fragments']:
                for row in f['instructions']:
                    reads[base + int(row['va'], 16) - 6442450944] = bytes.fromhex(row['bytes'])
        for table, slots in event.TABLES.values():
            for slot, rva in slots:
                reads[base + table + slot] = struct.pack('<Q', base + rva)
        reads[20480] = struct.pack('<Q', base + event.TABLES['outer'][0])
        read = lambda p, n: reads[p][:n]
        event.verify_live(base, 20480, read, core_sha256=XP1_CORE_SHA256)
        pointer = base + event.ENTRIES['get_player']
        reads[pointer] = bytes(len(reads[pointer]))
        with self.assertRaisesRegex(ValueError, 'native body'):
            event.verify_live(base, 20480, read, core_sha256=XP1_CORE_SHA256)

    def service(self):
        fixture = A0FamilyServiceTests()
        fixture.profile = fixture.__class__.profile
        self.addCleanup(fixture.doCleanups)
        return fixture.fixture()

    def test_same_a0_fifo_produces_and_consumes_exact_native_null_record(self):
        h, d, a, c, r, _, _ = self.service()
        f = memory_fixture(null_player=True)
        d.core = f[0]
        d.context = 20480
        c.read = f[1]
        with patch.object(event, 'verify_live', return_value={}):
            c.enable_district_events()
        self.assertTrue(c.handles_kind(event.codec.EVENT_KIND))
        self.assertTrue(c.handles_record(160))
        with patch.object(event.codec, 'decode_fields', return_value=self.fields), patch.object(event, '_api', return_value=f[2]):
            self.assertEqual(a.dispatch(h.pointer, event.codec.EVENT_KIND, 4660), 0)
        self.assertEqual(len(d.pending), 1)
        self.assertEqual(d.pending[0][104:120], bytes(8) + bytes.fromhex('ffff0000ffffffff'))
        self.assertEqual(d.drain(), 1)
        self.assertEqual(d.pending, [])
        a.close()
        d.close()

    def test_admission_pending_duplicate_profile_and_failure_quarantine(self):
        h, d, a, c, r, _, _ = self.service()
        r.fields.return_value = {}
        with patch.object(event, 'verify_live', return_value={}):
            c.enable_district_events()
        with self.assertRaisesRegex(ValueError, 'idle'):
            c.enable_district_events()
        with patch.object(event, 'dispatch', side_effect=RuntimeError('query refused')):
            with self.assertRaisesRegex(RuntimeError, 'query refused'):
                a.dispatch(h.pointer, event.codec.EVENT_KIND, 1)
        self.assertTrue(a.quarantined)
        self.assertTrue(c.quarantined)
        self.assertEqual(d.pending, [])

    def test_nonzero_counter_does_not_silently_reset_or_skip_native_event(self):
        h, d, a, c, r, _, _ = self.service()
        r.fields.return_value = {}
        with patch.object(event, 'verify_live', return_value={}):
            c.enable_district_events()
        d.host_notification_counter = 1
        with self.assertRaisesRegex(ValueError, 'scope'):
            a.dispatch(h.pointer, event.codec.EVENT_KIND, 1)
        self.assertEqual(d.host_notification_counter, 1)
        self.assertEqual(d.pending, [])

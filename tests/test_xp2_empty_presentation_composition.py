"""Feature-reveal callbacks compose with the real XP2 A0 owner and FIFO."""
import struct
import unittest
from types import MappingProxyType
from unittest.mock import patch

from civ6_host.runtime import a0_foundation_events as foundation
from civ6_host.runtime import a0_xp2_turn_events as turn_events
from civ6_host.runtime import empty_presentation_events as presentation
from civ6_host.runtime import xp2_feature_reveal_source as feature
from civ6_host.runtime import xp2_favor_event_profile as favor
from civ6_host.runtime import xp2_turn_event_profile as turn_source
from civ6_host.runtime import xp2_weather_lifecycle as lifecycle
from test_xp1_turn_a0 import scalar


class EmptyPresentationCompositionTests(unittest.TestCase):
    def graph(self):
        original = foundation.enable_turn_units

        def install(owner, backend):
            memory = owner.read.__self__
            for body in turn_source.source()['functions'].values():
                if body['image'] == 'xp2':
                    for va, raw in turn_source.fragments(body):
                        memory.put(memory.core_base + va - 0x180000000, raw)
            for rva, raw in favor.core_fragments():
                memory.put(memory.core_base + rva, raw)
            for rva, raw in lifecycle.core_fragments():
                memory.put(memory.core_base + rva, raw)
            for rva, raw in feature._core_fragments():
                memory.put(memory.core_base + rva, raw)
            for table, offset, target in feature._OWNERSHIP_SLOTS.values():
                memory.q(memory.core_base + table + offset, memory.core_base + target)
            memory.q(memory.core_base + 0xB90770, memory.core_base + 0xABEFF8)
            owner.arguments.reader.core_sha256 = backend.load_abi.core_sha256
            original(owner, backend)
            turn_events.enable(owner, backend)
            presentation.enable(owner, backend, feature)

        with patch.object(foundation, 'enable_turn_units', install):
            from test_xp2_turn_notifications import XP2ComposedNotifications
            return XP2ComposedNotifications().graph()

    def fields(self, graph, kind, index):
        address = 0xD31000 + index * 0x100
        x, y = 17 + index, -4 - index
        graph.memory.put(address, struct.pack('<ii', x, y))
        return {
            feature.SELECTOR_KEY: scalar(3, 0),
            # The native constructor owns one copied eight-byte element. Its
            # stored flags differ from the emitter's allocation request flags.
            feature.POSITION_KEY: struct.pack('<H6xQII', 0, address, 8, 0x21000001),
            feature.VALUE_KEY: scalar(2, 100 + index),
        }, (x, y), 100 + index

    def test_three_callbacks_preserve_pending_cache_update_and_copy_arguments(self):
        import threading
        from types import SimpleNamespace as NS
        from civ6_host.runtime.event_argument_service import EventArgumentReader
        from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload
        from civ6_host.runtime.native.native_host import DiagnosticHost
        from test_xp2_preload_services import XP2PreloadServices

        g = self.graph()
        d, host, memory = g.event.deferred, g.backend.host, g.memory
        host._check = DiagnosticHost._check.__get__(host)
        for name in ('cache_outer198', 'cache_keyed_dispatch', 'b0_snapshot_emitter',
                     'iterator_next', 'get_count'):
            from civ6_host.runtime import xp2_preload_source as preload
            for fragment in preload.body(name)['fragments']:
                memory.put(memory.core_base + int(fragment['start_rva'], 16),
                           bytes.fromhex(fragment['raw_hex']))
        memory.q(memory.core_base + 0xA101E8 + 0x198, memory.core_base + 0x591920)
        memory.q(memory.core_base + 0xABF080 + 0x1D8, memory.core_base + 0x84E260)
        memory.put(memory.core_base + 0xB61E10, struct.pack('<QII', 0xDC0000, 1, 1))
        memory.put(0xDC0000, struct.pack('<QQ', 0xDC0100, 0xDC0999))
        node = bytearray(48)
        struct.pack_into('<I', node, 0, lifecycle.STORM_CHANGED)
        struct.pack_into('<QQQ', node, 8, 0xDC1000, 0xDC1020, 0xDC1020)
        struct.pack_into('<Q', node, 40, 0xDC0999)
        memory.put(0xDC0100, node)
        memory.put(0xDC1000, struct.pack('<QQQQ', 0, 0, 0xDD1000, 0xDD2000))
        d.base, d.read, d.cache_update_callback_pair = memory.core_base, memory.read, None
        reader = EventArgumentReader.__new__(EventArgumentReader)
        reader.core, reader.base = g.backend.core, memory.core_base
        reader.core_sha256, reader.read = g.backend.load_abi.core_sha256, memory.read
        reader.thread, reader.closed = threading.get_ident(), False
        g.event.arguments.reader = reader

        self.assertEqual(d.cache_update(host.pointer, lifecycle.STORM_CHANGED,
                                        (1 << 32) | 0x768BA93D), 0)
        pending = d.pending[0]
        self.assertEqual(struct.unpack_from('<I', pending, 4)[0], 0x113)
        self.assertEqual(d._sequence, 1)
        tree = XP2PreloadServices()
        tree.base, tree.put = memory.core_base, memory.put
        snapshots = []
        kinds = (feature.FLOODPLAIN_REVEALED, feature.VOLCANO_REVEALED,
                 feature.GEOTHERMAL_FISSURE_REVEALED)
        original_dispatch_fields = g.owner._dispatch_fields
        with patch.object(g.owner, '_dispatch_fields',
                          side_effect=AssertionError('gameplay/query dispatcher used')):
            for index, kind in enumerate(kinds):
                self.assertTrue(g.owner.handles_kind(kind))
                raw_fields, coordinate, value = self.fields(g, kind, index)
                argument, reader.next_node = tree.tree(raw_fields)
                self.assertEqual(g.event.arguments.dispatch(host.pointer, kind, argument), 0)
                snapshots.append((coordinate, value))
                self.assertEqual(d._sequence, 1)
                self.assertEqual(d.consumed_count, 0)
                self.assertEqual(len(d.pending), 1)
                self.assertIs(d.pending[0], pending)
                self.assertEqual(g.owner._climate_records, {})
                self.assertIsNone(g.owner._foundation_borrow)
        self.assertIsNotNone(original_dispatch_fields)
        self.assertEqual(g.event.arguments.count, 3)
        omitted = [record for stage, record in g.event.emitted
                   if stage == 'native_empty_presentation_callback_omitted']
        self.assertEqual([int(record['dispatch_kind'], 16) for record in omitted], list(kinds))
        self.assertEqual([record['administrative_arguments']['coordinate'] for record in omitted],
                         [list(pair) for pair, _ in snapshots])
        self.assertEqual([record['administrative_arguments']['value'] for record in omitted],
                         [value for _, value in snapshots])
        self.assertTrue(all(record['native_queries_executed'] is False
                            and record['native_gameplay_written'] is False
                            and record['records_enqueued'] == 0 for record in omitted))

        # The receipt contains owned scalar copies, never the borrowed pointer.
        for index in range(len(kinds)):
            address = 0xD31000 + index * 0x100
            memory.put(address, b'\xff' * 8)
        self.assertEqual([record['administrative_arguments']['coordinate'] for record in omitted],
                         [list(pair) for pair, _ in snapshots])

        seen = []
        def invoke(target, receiver, args):
            self.assertEqual((target, receiver), (memory.core_base + 0x591920, g.backend.context))
            seen.append(tuple(args))
        def dispatch(*args, **kwargs):
            return dispatch_cache_update_payload(*args, **kwargs, invoke=invoke)
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',
                   side_effect=dispatch):
            self.assertEqual(d.drain(), 1)
            self.assertEqual(d.drain(), 0)
        self.assertEqual(seen, [(lifecycle.STORM_CHANGED, 0, 0x768BA93D, 1)])
        self.assertEqual((d._sequence, d.consumed_count, d.pending), (1, 1, []))
        g.owner.close()
        self.assertTrue(g.owner.closed)

    def test_unknown_hooks_source_subscriber_and_registry_mutations_refuse(self):
        cases = (
            ('hook', lambda g: setattr(g.owner, 'per_thread_hook_present', True)),
            ('source', lambda g: setattr(g.backend, '_xp2_feature_reveal_source_identity', None)),
            ('subscriber', lambda g: g.owner.empty_receiver_state.__setitem__('subscriber_count', 1)),
            ('registry', lambda g: setattr(g.owner, 'presentation_sources', MappingProxyType({}))),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                g = self.graph()
                kind = feature.FLOODPLAIN_REVEALED
                mutate(g)
                with self.assertRaises((ValueError, RuntimeError)):
                    g.owner.dispatch(kind, self.fields(g, kind, 0)[0], 0)
                self.assertEqual(g.event.emitted[-1][0], 'native_empty_presentation_family_installed')
                self.assertEqual((g.owner._sequence, g.owner.pending, g.owner._climate_records),
                                 (0, [], {}))
                self.assertIsNone(g.owner._foundation_borrow)

        g = self.graph()
        self.assertFalse(g.owner.handles_kind(0xDEADBEEF))
        with self.assertRaisesRegex(ValueError, 'unknown family'):
            g.owner.dispatch(0xDEADBEEF, {}, 0)


if __name__ == '__main__':
    unittest.main()

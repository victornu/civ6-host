"""Whole XP2 A0/FIFO group with only native calls/memory replaced by fixtures."""
import ctypes as C
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import a0_foundation_events as foundation
from civ6_host.runtime import a0_xp2_turn_events as events
from civ6_host.runtime import xp2_turn_event_profile as source
from civ6_host.runtime import xp2_turn_event_records as codec
from civ6_host.runtime import xp2_weather_position as position
from civ6_host.runtime import xp2_storm_query as query
from civ6_host.runtime import xp2_descriptor53_query as drought
from civ6_host.runtime import xp2_favor_event_profile as favor
from civ6_host.runtime import xp2_weather_lifecycle as lifecycle
from test_xp1_turn_a0 import scalar
from test_xp2_turn_notifications import XP2ComposedNotifications


class ClimateCompositionTests(unittest.TestCase):
    def graph(self):
        original = foundation.enable_turn_units

        def install(owner, backend):
            memory = owner.read.__self__
            for body in source.source()['functions'].values():
                if body['image'] == 'xp2':
                    for va, raw in source.fragments(body):
                        memory.put(memory.core_base + va - 0x180000000, raw)
            for rva, raw in favor.core_fragments():
                memory.put(memory.core_base + rva, raw)
            for rva, raw in lifecycle.core_fragments():
                memory.put(memory.core_base + rva, raw)
            for rva, raw in codec.terrain_core_fragments():
                memory.put(memory.core_base + rva, raw)
            owner.arguments.reader.core_sha256 = backend.load_abi.core_sha256
            original(owner, backend)
            events.enable(owner, backend)

        with patch.object(foundation, 'enable_turn_units', install):
            return XP2ComposedNotifications().graph()

    def fields(self, graph, kind):
        fields = {codec.SELECTOR_KEY: scalar(3, 0)}
        if kind == source.FAVOR_KIND:
            fields.update({codec.VALUE_KEY: scalar(2, 1),
                           0xa1fbc372: scalar(2, 2), 0x38f292c8: scalar(2, 3)})
            return fields
        if kind == codec.CLIMATE_KIND:
            fields[codec.CLIMATE_DATA_KEY] = scalar(5, 0)
            return fields
        address = 0xd11000
        graph.memory.put(address, struct.pack('<ii', 5, 7))
        fields[codec.POSITION_KEY] = struct.pack('<H6xQII', 13, address, 8, 0x21000001)
        vector_kind = kind in (source.STORM_KIND, source.DESCRIPTOR53_KIND)
        fields[codec.IDENTIFIER_KEY] = scalar(3 if vector_kind else 2, 29)
        fields[codec.VALUE_KEY if vector_kind else codec.EVENT_KEY] = scalar(2, 31)
        return fields

    def test_whole_family_retains_and_consumes_shared_fifo_in_order(self):
        g = self.graph()
        storm = query.StormQueryResult(items=(51, 72),
            positions=(struct.pack('<ii', 3, 4), struct.pack('<ii', 8, 9)), position=(11, 13))
        with patch.object(query, 'query_storm_objects', return_value=storm) as call_storm, \
             patch.object(drought, 'query_descriptor53_objects', return_value=query.StormQueryResult(
                 items=storm.items, positions=storm.positions, position=None)) as call_descriptor53, \
             patch.object(position, 'query_native_position_index',
                          return_value=position.PositionIndexResult(313, 99, 101)) as call_position:
            for kind in (source.FAVOR_KIND, source.STORM_KIND, source.DESCRIPTOR53_KIND, codec.CLIMATE_KIND,
                         codec.STARTED_KIND, codec.OCCURRED_KIND):
                self.assertEqual(g.owner.dispatch(kind, self.fields(g, kind), 0), 0)
        self.assertEqual(call_storm.call_count, 1)
        self.assertEqual(call_descriptor53.call_count, 1)
        self.assertEqual(call_position.call_count, 2)
        self.assertEqual(len(g.owner.pending), 7)
        self.assertEqual([struct.unpack_from('<I', row, 4)[0] for row in g.owner.pending],
                         [0x142, 0x138, 0x13b, 0x145, 0x135, 0x136, 0x137])
        self.assertEqual(struct.unpack_from('<4I', g.owner.pending[0], 80), (1, 1, 2, 3))
        retained = g.owner._climate_records[2]
        self.assertEqual(C.string_at(struct.unpack_from('<Q', retained.record, 112)[0], 16),
                         b''.join(storm.positions))
        self.assertEqual(struct.unpack_from('<ii', retained.record, 100), (13, 11))
        retained53 = g.owner._climate_records[3]
        self.assertEqual(struct.unpack_from('<HHII', retained53.record, 88), (0xffff, 0x53, 29, 31))
        self.assertEqual(struct.unpack_from('<I', retained53.record, 100)[0], 2)
        self.assertEqual(C.string_at(struct.unpack_from('<Q', retained53.record, 104)[0], 16),
                         b''.join(storm.positions))
        for row in g.owner.pending[4:]:
            self.assertEqual(struct.unpack_from('<I', row, 16)[0], 313)
            self.assertEqual(struct.unpack_from('<ii', row, 100), (5, 7))
        self.assertEqual(g.event.deferred.drain(), 7)
        self.assertEqual(g.owner._climate_records, {})
        self.assertIsNone(g.owner._foundation_borrow)
        self.assertEqual((g.owner.host_notification_counter, g.owner.host_metadata_counter), (0, 0))
        g.owner.close()

    def test_zero_vector_or_unwritten_coordinates_are_refused_not_fabricated(self):
        fields = codec.StormFields(source.STORM_KIND, 0, 31, 29, (5, 7), ())
        for result in (query.StormQueryResult(items=(), positions=(), position=(1, 2)),
                       query.StormQueryResult(items=(1,), positions=(b'\0' * 8,), position=None)):
            with self.assertRaisesRegex(ValueError, 'undefined'):
                events._storm_record(1, fields, result)

    def test_mutated_array_does_not_commit_or_lose_owned_fifo_head(self):
        g = self.graph()
        storm = query.StormQueryResult(items=(51,), positions=(struct.pack('<ii', 3, 4),),
                                      position=(11, 13))
        with patch.object(query, 'query_storm_objects', return_value=storm):
            g.owner.dispatch(source.STORM_KIND, self.fields(g, source.STORM_KIND), 0)
        entry = g.owner._climate_records[1]
        C.memset(C.addressof(entry.storage), 0x22, 1)
        with self.assertRaisesRegex(ValueError, 'array changed'):
            g.event.deferred.drain()
        self.assertIs(g.owner.pending[0], entry.record)
        self.assertIs(g.owner._climate_records[1], entry)
        self.assertEqual(g.event.deferred.consumed_count, 0)

    def test_foreign_record_is_not_consumed(self):
        g = self.graph()
        g.owner.dispatch(codec.CLIMATE_KIND, self.fields(g, codec.CLIMATE_KIND), 0)
        row = g.owner.pending[0]
        g.event.deferred._draining_empty_receivers = True
        try:
            with self.assertRaisesRegex(ValueError, 'exact owned'):
                events.consume(g.owner, bytes(bytearray(row)), 1)
        finally:
            g.event.deferred._draining_empty_receivers = False
        self.assertEqual(g.event.deferred.drain(), 1)
        g.owner.close()

    def test_foreign_cached_map_is_refused_before_position_query(self):
        g = self.graph()
        facades = g.continuation.publisher._facades
        cached_at = facades.cache_service + 16
        old = g.memory.read(cached_at, 8)
        g.memory.put(cached_at, struct.pack('<Q', int.from_bytes(old, 'little') + 8))
        with patch.object(position, 'query_native_position_index') as call:
            with self.assertRaises((ValueError, RuntimeError)):
                g.owner.dispatch(codec.STARTED_KIND, self.fields(g, codec.STARTED_KIND), 0)
            call.assert_not_called()
        self.assertEqual(g.owner.pending, [])
        self.assertEqual(g.owner._climate_records, {})
        self.assertIsNone(g.owner._foundation_borrow)

    def lifecycle_fields(self, graph, kind, **options):
        from test_xp2_weather_lifecycle import inputs
        fields, memory, _, _ = inputs(kind, **options)
        for address, raw in memory.items():
            graph.memory.put(address, raw)
        return fields

    def test_three_lifecycle_omissions_preserve_real_pending_cache_feedback(self):
        import threading
        from types import SimpleNamespace as NS
        from civ6_host.runtime import xp2_preload_source as preload
        from civ6_host.runtime.event_argument_service import EventArgumentReader
        from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload
        from civ6_host.runtime.native.native_host import DiagnosticHost
        from test_xp2_preload_services import XP2PreloadServices
        g = self.graph()
        d, h, memory = g.event.deferred, g.backend.host, g.memory
        h._check = DiagnosticHost._check.__get__(h)
        # Supply only the additional native memory needed by the real argument
        # reader and CacheUpdate dispatcher; do not replace their source guards.
        for name in ('cache_outer198', 'cache_keyed_dispatch', 'b0_snapshot_emitter',
                     'iterator_next', 'get_count'):
            for fragment in preload.body(name)['fragments']:
                memory.put(memory.core_base + int(fragment['start_rva'], 16),
                           bytes.fromhex(fragment['raw_hex']))
        memory.q(memory.core_base + 0xA101E8 + 0x198, memory.core_base + 0x591920)
        memory.q(memory.core_base + 0xABF080 + 0x1D8, memory.core_base + 0x84E260)
        memory.put(memory.core_base + 0xB61E10, struct.pack('<QII', 0xdc0000, 1, 1))
        memory.put(0xdc0000, struct.pack('<QQ', 0xdc0100, 0xdc0999))
        node = bytearray(48)
        struct.pack_into('<I', node, 0, lifecycle.STORM_CHANGED)
        struct.pack_into('<QQQ', node, 8, 0xdc1000, 0xdc1020, 0xdc1020)
        struct.pack_into('<Q', node, 40, 0xdc0999)
        memory.put(0xdc0100, node)
        memory.put(0xdc1000, struct.pack('<QQQQ', 0, 0, 0xdd1000, 0xdd2000))
        d.base, d.read, d.cache_update_callback_pair = memory.core_base, memory.read, None
        reader = EventArgumentReader.__new__(EventArgumentReader)
        reader.core, reader.base = g.backend.core, memory.core_base
        reader.core_sha256, reader.read = g.backend.load_abi.core_sha256, memory.read
        reader.thread, reader.closed = threading.get_ident(), False
        g.event.arguments.reader = reader
        tree = NS(base=memory.core_base, put=memory.put)
        self.assertEqual(d.cache_update(h.pointer, lifecycle.STORM_CHANGED,
                                       (1 << 32) | 0x768ba93d), 0)
        preceding = d.pending[0]
        self.assertEqual(struct.unpack_from('<I', preceding, 4)[0], 0x113)
        with patch.object(query, 'query_storm_objects', side_effect=AssertionError('presentation query')) as storm, \
             patch.object(drought, 'query_descriptor53_objects', side_effect=AssertionError('presentation query')) as dry, \
             patch.object(position, 'query_native_position_index', side_effect=AssertionError('presentation query')) as pos, \
             patch.object(position, 'query_native_index_to_position', side_effect=AssertionError('presentation conversion')) as convert:
            for kind in (lifecycle.STORM_CHANGED, lifecycle.STORM_REMOVED, lifecycle.DROUGHT_REMOVED):
                self.assertTrue(g.owner.handles_kind(kind))
                self.assertEqual(g.owner.climate_event_profile.record_types_by_kind[kind], frozenset())
                argument, reader.next_node = XP2PreloadServices.tree(tree, self.lifecycle_fields(g, kind))
                self.assertEqual(g.event.arguments.dispatch(h.pointer, kind, argument), 0)
                self.assertEqual((d._sequence, d.consumed_count, len(d.pending)), (1, 0, 1))
                self.assertIs(d.pending[0], preceding)
                self.assertEqual(g.owner._climate_records, {})
                self.assertIsNone(g.owner._foundation_borrow)
            for call in (storm, dry, pos, convert):
                call.assert_not_called()
        self.assertEqual(g.event.arguments.count, 3)
        omitted = [r for stage, r in g.event.emitted if stage == 'native_xp2_weather_presentation_omitted']
        self.assertEqual([r['dispatch_kind'] for r in omitted],
                         [hex(lifecycle.STORM_CHANGED), hex(lifecycle.STORM_REMOVED), hex(lifecycle.DROUGHT_REMOVED)])
        self.assertTrue(all(r['source_proof_sha256'] == lifecycle.SOURCE[1]
                            and r['records_enqueued'] == 0 for r in omitted))
        memory.put(0x100000, b'\xff' * 8)
        memory.put(0x200000, b'\xff' * 8)
        self.assertEqual(omitted[0]['administrative_arguments']['input_plot_indices'], [19, 27])
        self.assertEqual(omitted[0]['administrative_arguments']['input_position'], [5, 3])
        seen = []
        def invoke(target, receiver, args):
            self.assertEqual((target, receiver), (memory.core_base + 0x591920, g.backend.context))
            seen.append(tuple(args))
        def dispatch(*args, **kwargs):
            return dispatch_cache_update_payload(*args, **kwargs, invoke=invoke)
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload', side_effect=dispatch):
            self.assertEqual(d.drain(), 1)
            self.assertEqual(d.drain(), 0)
        self.assertEqual(seen, [(lifecycle.STORM_CHANGED, 0, 0x768ba93d, 1)])
        self.assertEqual((d._sequence, d.consumed_count, d.pending), (1, 1, []))
        g.owner.close()
        self.assertTrue(g.owner.closed)

    def test_lifecycle_empty_vector_omits_without_allocating_or_using_fifo_sequence(self):
        g = self.graph()
        self.assertEqual(g.owner.dispatch(lifecycle.STORM_CHANGED,
            self.lifecycle_fields(g, lifecycle.STORM_CHANGED, indices=()), 0), 0)
        self.assertEqual((g.owner._sequence, g.owner.pending, g.owner._climate_records), (0, [], {}))
        receipt = g.event.emitted[-1][1]
        self.assertEqual(receipt['administrative_arguments']['input_plot_indices'], [])
        self.assertFalse(receipt['presentation_arrays_allocated'])
        self.assertFalse(receipt['native_queries_executed'])
        # A subsequent historical climate record starts at1 and retains its
        # original source identity; omission has not fabricated a FIFO gap.
        g.owner.dispatch(codec.CLIMATE_KIND, self.fields(g, codec.CLIMATE_KIND), 0)
        self.assertEqual(g.owner._sequence, 1)
        self.assertEqual(g.event.emitted[-1][1]['source_proof_sha256'], source.SOURCE[1])
        self.assertEqual(g.event.deferred.drain(), 1)
        g.owner.close()

    def test_lifecycle_real_owner_hooks_receivers_source_and_unknown_kind_refuse(self):
        changes = (
            lambda g: setattr(g.owner, 'per_thread_hook_present', True),
            lambda g: setattr(g.owner, 'writer_metadata_callback_present', True),
            lambda g: g.owner.empty_receiver_state.__setitem__('subscriber_count', 1),
            lambda g: setattr(g.owner, 'normalizer_transform_present', True),
            lambda g: setattr(g.backend, '_xp2_weather_lifecycle_source_identity', None),
        )
        for change in changes:
            g = self.graph()
            change(g)
            with self.assertRaises((ValueError, RuntimeError)):
                g.owner.dispatch(lifecycle.STORM_CHANGED, self.lifecycle_fields(g, lifecycle.STORM_CHANGED), 0)
            self.assertFalse(any(stage == 'native_xp2_weather_presentation_omitted' for stage, _ in g.event.emitted))
            self.assertEqual((g.owner._sequence, g.owner.pending, g.owner._climate_records), (0, [], {}))
            self.assertIsNone(g.owner._foundation_borrow)
        g = self.graph()
        self.assertFalse(g.owner.handles_kind(0xdeadbeef))
        with self.assertRaisesRegex(ValueError, 'unknown family'):
            g.owner.dispatch(0xdeadbeef, {}, 0)


if __name__ == '__main__':
    unittest.main()

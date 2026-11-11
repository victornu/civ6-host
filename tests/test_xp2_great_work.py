"""Exercise the shared native plot query and A0 FIFO on the current profile."""

import ctypes
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import a0_foundation_events as foundation, xp2_great_work
from civ6_host.runtime import foundation_event_profile, xp2_feature_events as feature
from civ6_host.runtime import xp1_load_capability as capability
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.native import native_event_great_work as codec
import test_xp2_improvement_event_source as plot_fixtures
from test_xp2_turn_notifications import pending_civilization_render


class GreatWorkTransportTests(unittest.TestCase):
    def graph(self):
        name = 'xp2-gamecore-current-092abfbb'
        image = select(name, core_path=known_path(name))
        fixtures = plot_fixtures.ImprovementQueriesTests()
        self.addCleanup(fixtures.doCleanups)
        pillage = foundation_event_profile.pillage_source
        owner_fixture = plot_fixtures.composed.XP2ComposedNotifications
        original_graph = owner_fixture.graph

        def current_graph(fixture):
            graph = original_graph(fixture)
            graph.backend.core._civ6_host_execution_image = image
            return graph

        with (patch.object(foundation_event_profile, 'pillage_source',
                           lambda **_: pillage(execution_image=image)),
              patch.object(owner_fixture, 'graph', current_graph)):
            graph = fixtures.graph()
        backend = graph.backend
        graph.memory.q(graph.objects['plot'] + 8, 0xba0000)
        for rva, raw in xp2_great_work.core_fragments():
            graph.memory.put(graph.memory.core_base + rva, raw)
        for rva, raw in feature.core_fragments():
            graph.memory.put(graph.memory.core_base + rva, raw)
        for table, slot, target in (feature._PLOT_CHILD, feature._CHILD_RELEASE, feature._CHILD_VALUE):
            graph.memory.q(graph.memory.core_base + table + slot, graph.memory.core_base + target)
        for rva, body in pillage(execution_image=image)['core_producer'].items():
            graph.memory.put(graph.memory.core_base + int(rva, 16), bytes.fromhex(body['raw_hex']))
        stage, prefix = backend.stage, backend.prefix
        backend.stage, backend.prefix = 'prepared', None
        try:
            foundation.enable(graph.owner, backend)
        finally:
            backend.stage, backend.prefix = stage, prefix
        return graph

    def fields(self, graph, descriptor_type=1):
        coordinates, descriptor = 0xa30000, 0xa31000
        graph.memory.put(coordinates, struct.pack('<ii', 3, 4))
        graph.memory.put(descriptor, struct.pack('<HHI', 1, descriptor_type, 65543))
        return {
            0x8c468e3c: struct.pack('<H6xQII', 0, coordinates, 8, 0x21000001),
            0xa1e5a149: struct.pack('<H6xI12x', 3, 0),
            0xa1fbc372: struct.pack('<H6xI12x', 2, 0),
            0xd6fcf3e4: struct.pack('<H6xI12x', 2, 1),
            0xf0548bb7: struct.pack('<H6xQII', 1024, descriptor, 8, 0x21000001),
        }

    def test_current_engine_uses_existing_plot_query_and_drains_record(self):
        g = self.graph()
        self.assertTrue(g.owner.handles_kind(codec.EVENT_KIND))
        with (pending_civilization_render(), patch.object(ctypes, 'WINFUNCTYPE', g.factory),
              capability.capability_source_scope(g.backend, 'continuation')):
            self.assertEqual(g.owner.dispatch(codec.EVENT_KIND, self.fields(g), 0), 0)
        record, = g.owner.pending
        self.assertEqual(struct.unpack_from('<IIII', record), (160, 220, 1, 0))
        self.assertEqual(struct.unpack_from('<ii', record, 88), (3, 4))
        self.assertEqual(struct.unpack_from('<HHI', record, 96), (2, 2, 44))
        self.assertEqual(struct.unpack_from('<HHI', record, 144), (1, 1, 65543))
        calls = [name for name, _ in g.calls]
        self.assertEqual(calls[-5:], ['outer_map', 'get_plot', 'release_map',
                                     'plot_snapshot178', 'release_plot'])
        self.assertFalse(any(g.live.values()))
        self.assertEqual(g.event.deferred.drain(), 1)
        self.assertEqual((g.event.deferred.consumed_count, g.owner.pending), (1, []))

    def test_unqualified_component_type_refuses_before_plot_query(self):
        g = self.graph()
        with (pending_civilization_render(), patch.object(ctypes, 'WINFUNCTYPE', g.factory),
              capability.capability_source_scope(g.backend, 'continuation'),
              self.assertRaisesRegex(ValueError, 'component type differs')):
            g.owner.dispatch(codec.EVENT_KIND, self.fields(g, descriptor_type=2), 0)
        self.assertEqual(g.owner.pending, [])
        self.assertNotIn('outer_map', [name for name, _ in g.calls])

    def test_current_feature_family_reads_native_facades_and_drains_in_order(self):
        g = self.graph()
        base, child = g.memory.core_base, 0xba1000
        g.memory.q(child, base + feature._CHILD_VALUE[0])
        address = 0xa30000
        g.memory.put(address, struct.pack('<ii', 3, 4))
        fields = {
            0x8c468e3c: struct.pack('<H6xQII', 0, address, 8, 0x21000001),
            0xa1e5a149: struct.pack('<H6xI12x', 3, 0),
            0xd6fcf3e4: struct.pack('<H6xI12x', 2, 30),
        }
        calls = []

        def factory(result, *types):
            fallback = g.factory(result, *types)

            def bind(target):
                if target == base + 0x5a11b0:
                    self.assertIs(result, ctypes.c_void_p)
                    def acquire(plot):
                        self.assertEqual(plot, g.objects['plot'])
                        self.assertEqual((g.live['map'], g.live['plot']), (0, 1))
                        calls.append('acquire')
                        return child
                    return acquire
                if target == base + 0x59b970:
                    self.assertIs(result, ctypes.c_int32)
                    def get_value(pointer):
                        self.assertEqual(pointer, child)
                        calls.append('read')
                        return -42
                    return get_value
                if target == base + 0x59b950:
                    self.assertIsNone(result)
                    def release(pointer):
                        self.assertEqual(pointer, child)
                        self.assertEqual(g.owner.pending, [])
                        calls.append('release')
                    return release
                return fallback(target)
            return bind

        with (pending_civilization_render(), patch.object(ctypes, 'WINFUNCTYPE', factory),
              capability.capability_source_scope(g.backend, 'continuation')):
            for kind in (feature.ADDED, feature.CHANGED, feature.VISIBILITY):
                self.assertTrue(g.owner.handles_kind(kind))
                self.assertEqual(g.owner.dispatch(kind, fields, 0), 0)
        self.assertEqual(calls, ['acquire', 'read', 'release'])
        self.assertFalse(any(g.live.values()))
        added, changed, visibility = g.owner.pending
        self.assertEqual([struct.unpack_from('<III', r) for r in g.owner.pending],
                         [(112, 116, 1), (96, 117, 2), (128, 118, 3)])
        self.assertEqual(struct.unpack_from('<iiIiB', added, 84), (3, 4, 30, -42, 0))
        self.assertEqual(struct.unpack_from('<iiI', changed, 84), (3, 4, 30))
        self.assertEqual(struct.unpack_from('<iiI', visibility, 88), (3, 4, 30))
        self.assertEqual([name for name, _ in g.calls][-9:], [
            'outer_map', 'get_plot', 'release_map', 'release_plot',
            'outer_map', 'get_plot', 'release_map', 'plot_snapshot180', 'release_plot'])
        self.assertEqual(g.event.deferred.drain(), 3)
        self.assertEqual((g.event.deferred.consumed_count, g.owner.pending), (3, []))


if __name__ == '__main__':
    unittest.main()

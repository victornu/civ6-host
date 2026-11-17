"""Current park visibility on the existing saved A0 owner and query facade."""

import ctypes
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_national_park_visibility as parks
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.foundation_facade_profiles import query_abi
from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp1_load_capability import capability_source_scope
import test_xp2_great_work as fixtures
from test_xp2_turn_notifications import pending_civilization_render
from test_xp1_turn_a0 import scalar


class NationalParkVisibilityTests(unittest.TestCase):
    def graph(self):
        fixture = fixtures.GreatWorkTransportTests()
        self.addCleanup(fixture.doCleanups)
        graph = fixture.graph()
        for rva, raw in parks.core_fragments():
            graph.memory.put(graph.memory.core_base + rva, raw)
        return graph

    def fields(self, graph, visibility, index=None):
        def blob(address, tag, raw):
            graph.memory.put(address, raw)
            return struct.pack('<H6xQII', tag, address, 8, 0x21000001)

        fields = {
            parks.SELECTOR: scalar(3, 0),
            parks.PARK: blob(0xA61000, 1024, struct.pack('<HHI', 6, 0x48, 70)),
            parks.POSITION: blob(0xA62000, 13, struct.pack('<ii', 4, 9)),
            parks.VISIBILITY: scalar(2, visibility),
        }
        if index is not None:
            fields.update({
                parks.PAIR: blob(0xA63000, 1024, struct.pack('<HHI', 6, 1, 80)),
                parks.INDEX: scalar(2, index),
                parks.VALUE: scalar(2, 0x80000007),
                parks.PLAYER: scalar(2, 1),
            })
        return fields

    def test_source_and_installed_receiver(self):
        self.assertIn(parks.SOURCE[1], parks.source_dependencies().values())
        self.assertIsNone(resolve_empty_receiver_row(parks.RECORD_TYPE))
        row = resolve_empty_receiver_row(parks.RECORD_TYPE, execution_image=_PROFILE)
        self.assertEqual(row['event_name'], 'GameCoreEvent::NationalParkVisibilityChanged')
        self.assertEqual(row['handler_va'], '0x1400db450')

    def test_both_producers_drain_in_order_with_one_owned_native_map_lookup(self):
        graph = self.graph()
        owner, backend, memory = graph.owner, graph.backend, graph.memory
        self.assertEqual(owner.foundation_event_profile.record_types_by_kind[parks.KIND], {0xF6})
        abi = query_abi(parks.XP2_CORE_SHA256, resource_root())
        original = graph.factory
        map_owner = 0xBA2000
        memory.q(graph.objects['map'] + 8, map_owner)
        memory.put(map_owner + 40, struct.pack('<i', 74))
        memory.put(map_owner + 48, struct.pack('<i', 3404))
        lookup_addr = memory.core_base + abi.rva('optional_position')

        def factory(result, *types):
            def bind(target):
                if target != lookup_addr:
                    return original(result, *types)(target)

                def lookup(facade, output, index):
                    self.assertEqual(facade, graph.objects['map'])
                    self.assertEqual(graph.live['map'], 1)
                    graph.calls.append(('optional_position', index))
                    ctypes.memmove(output, struct.pack('<ii', 3, 5), 8)
                    return output

                return lookup

            return bind

        with (pending_civilization_render(), patch.object(ctypes, 'WINFUNCTYPE', factory),
              capability_source_scope(backend, 'continuation')):
            self.assertEqual(owner.dispatch(parks.KIND, self.fields(graph, 2), 0), 0)
            owner.deferred.host_notification_counter = 1
            self.assertEqual(owner.dispatch(parks.KIND, self.fields(graph, 0, 0xFFFFFFFF), 0), 0)
            self.assertEqual(owner.host_metadata_counter, 1)
            self.assertEqual(owner.dispatch(parks.KIND, self.fields(graph, 1, 373), 0), 0)
            self.assertEqual(owner.host_metadata_counter, 1)
        calls = [name for name, _ in graph.calls if name in ('outer_map', 'optional_position', 'release_map')]
        self.assertEqual(calls, ['outer_map', 'optional_position', 'release_map'])
        self.assertEqual(graph.live['map'], 0)
        self.assertEqual(len(owner.pending), 3)
        for sequence, (record, flag, visibility) in enumerate(zip(owner.pending, (0, 32, 64), (2, 0, 1)), 1):
            self.assertEqual(struct.unpack_from('<IIII', record), (128, 0xF6, sequence, 0))
            self.assertEqual(struct.unpack_from('<I', record, 72)[0], flag)
            self.assertEqual(struct.unpack_from('<I4xi', record, 80), (sequence, visibility))
            self.assertEqual(struct.unpack_from('<iiI', record, 92),
                             (3, 5, 0x80000007) if sequence == 3 else (-9999, -9999, 0))
            self.assertEqual(struct.unpack_from('<HHI', record, 104),
                             (0xFFFF, 0, 0xFFFFFFFF) if sequence == 1 else (6, 1, 80))
            self.assertEqual(struct.unpack_from('<HHIii', record, 112), (6, 0x48, 70, 4, 9))
        owner.deferred.host_notification_counter = owner.deferred.host_metadata_counter = 0
        self.assertEqual(graph.event.deferred.drain(), 3)
        self.assertEqual((graph.event.deferred.consumed_count, owner.pending), (3, []))

    def test_invalid_type_or_changed_core_cannot_produce_a_record(self):
        for fault, message in (('tag', 'blob envelope'), ('source', 'live producer differs')):
            graph = self.graph()
            fields = self.fields(graph, 1)
            if fault == 'tag':
                fields[parks.PARK] = scalar(2, 2)
            else:
                rva, raw = next(parks.core_fragments())
                graph.memory.put(graph.memory.core_base + rva, bytes([raw[0] ^ 1]))
            with (self.subTest(fault=fault), pending_civilization_render(),
                  capability_source_scope(graph.backend, 'continuation'),
                  self.assertRaisesRegex(ValueError, message)):
                graph.owner.dispatch(parks.KIND, fields, 0)
            self.assertEqual(graph.owner.pending, [])
            self.assertFalse(any(graph.live.values()))


if __name__ == '__main__':
    unittest.main()

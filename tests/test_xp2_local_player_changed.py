"""Current XP2 notification scope through the shared A0 owner, with fixture memory."""

import threading
import unittest
from unittest.mock import patch

from civ6_host.runtime import a0_notification_scope_source as scopes
from civ6_host.runtime import xp1_diplomacy_meet_source as meeting
from civ6_host.runtime import xp2_local_player_changed as source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_unary_event_family import decode_queue_record
from test_xp1_turn_a0 import scalar
import test_xp2_congress_presentation as fixtures
import test_xp2_preload_services as preload_fixtures


class LocalPlayerChangedTests(unittest.TestCase):
    def fields(self, player=1, selector=0, player_tag=2):
        return {
            0xA1E5A149: scalar(3, selector),
            0xD6FCF3E4: scalar(player_tag, player),
        }

    def graph(self, *, corrupt=False, admitted=True):
        graph = fixtures.CongressPresentationTests().graph()
        memory = graph.memory
        for rva, raw in source.core_fragments():
            memory.put(memory.core_base + rva, raw)
            if corrupt:
                memory.put(memory.core_base + rva, bytes([raw[0] ^ 1]))
        scripts = {'stock': source.STOCK_SCRIPT} if admitted else {'stock': 'unrecognized'}
        with patch.object(meeting, 'verify_live'), patch.object(scopes, 'verify_research_changed_live'):
            graph.owner.enable_notification_scopes(script_hashes=scripts)
        return graph

    def test_installed_wire_is_the_local_player_receiver(self):
        proof = source.source()
        self.assertIn(source.SOURCE[1], source.source_dependencies().values())
        route = proof['wire']
        self.assertEqual((route['current_callback'], route['record_type']), ('0x148d90', 274))
        self.assertEqual(proof['correction']['wrong_record_type'], 270)
        image = fixtures.CongressPresentationTests().execution()
        for number, name in ((274, 'LocalPlayerChanged'), (270, 'PlayerOperationComplete')):
            row = resolve_empty_receiver_row(number, execution_image=image)
            self.assertEqual(row['event_name'], 'GameCoreEvent::' + name)
        row = resolve_empty_receiver_row(274, execution_image=image)
        self.assertEqual(row['handler_va'], '0x1400d4970')
        self.assertEqual(row['source_sha256'], source.SOURCE[1])

    def test_qualification_requires_the_exact_ordered_script_set(self):
        stock, mod = source.STOCK_SCRIPT, source.BBG_SCRIPT
        self.assertTrue(source.supports_script_hashes({'stock': stock}))
        self.assertTrue(source.supports_script_hashes({'stock': stock, 'bbg': mod}))
        for hashes in ({}, {'bbg': mod}, {'bbg': mod, 'stock': stock},
                       {'stock': stock, 'bbg': mod, 'other': stock}):
            self.assertFalse(source.supports_script_hashes(hashes))

    def test_scoped_callback_keeps_existing_codec_and_drains_in_fifo_order(self):
        from civ6_host.runtime import xp2_preload_source as preload

        graph = self.graph()
        owner, memory = graph.owner, graph.memory
        host = graph.backend.host
        host._check = DiagnosticHost._check.__get__(host)
        for name in ('iterator_next', 'get_count'):
            for fragment in preload.body(name)['fragments']:
                memory.put(memory.core_base + int(fragment['start_rva'], 16),
                           bytes.fromhex(fragment['raw_hex']))
        memory.q(memory.core_base + 0xABF080 + 0x1D8, memory.core_base + 0x84E260)
        reader = EventArgumentReader.__new__(EventArgumentReader)
        reader.core, reader.base = graph.backend.core, memory.core_base
        reader.core_sha256, reader.read = XP2_CORE_SHA256, memory.read
        reader.thread, reader.closed = threading.get_ident(), False
        graph.event.arguments.reader = reader
        tree = preload_fixtures.XP2PreloadServices()
        tree.base, tree.put = memory.core_base, memory.put
        self.assertTrue(owner.handles_kind(source.KIND))
        self.assertEqual(owner.notification_scope_profile.records[source.KIND], source.RECORD)
        players = (0, 1, 0xFFFFFFFF)
        for index, player in enumerate(players):
            if index == 1:
                owner.deferred.host_notification_counter = 3
                owner.deferred.host_metadata_counter = 2
            pointer, reader.next_node = tree.tree(self.fields(player))
            self.assertEqual(graph.event.arguments.dispatch(host.pointer, source.KIND, pointer), 0)
        self.assertEqual(owner._sequence, 3)
        self.assertEqual((owner.host_notification_counter, owner.host_metadata_counter), (3, 2))
        self.assertEqual(len(owner.pending), 3)
        self.assertEqual([(row.sequence, row.value) for row in
                         (decode_queue_record(source.KIND, raw) for raw in owner.pending)],
                         list(enumerate(players, 1)))
        self.assertIsNone(owner._foundation_borrow)
        owner.deferred.host_notification_counter = owner.deferred.host_metadata_counter = 0
        self.assertEqual(owner.deferred.drain_empty_receivers(), 3)
        self.assertEqual(owner.pending, [])
        self.assertEqual(owner.deferred.consumed_count, 3)

    def test_changed_live_bytes_and_unqualified_open_scope_refuse(self):
        with self.assertRaisesRegex(ValueError, 'live Core source differs'):
            self.graph(corrupt=True)
        graph = self.graph(admitted=False)
        graph.owner.deferred.host_notification_counter = 1
        with self.assertRaisesRegex(ValueError, 'requires separate source admission'):
            graph.owner.dispatch(source.KIND, self.fields(), 0)
        self.assertEqual(graph.owner.pending, [])

    def test_invalid_arguments_and_occupied_receiver_refuse(self):
        for fields in (self.fields(selector=1), self.fields(player_tag=3),
                       {**self.fields(), 5: scalar(2, 1)}):
            graph = self.graph()
            graph.owner.deferred.host_notification_counter = 1
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                graph.owner.dispatch(source.KIND, fields, 0)
            self.assertEqual(graph.owner.pending, [])
        graph = self.graph()
        for profile in (graph.owner.empty_receiver_state, graph.owner._receiver_profile):
            profile['subscriber_count'] = 1
        with self.assertRaises((ValueError, RuntimeError)):
            graph.owner.dispatch(source.KIND, self.fields(), 0)
        self.assertEqual(graph.owner.pending, [])
        self.assertIsNone(graph.owner._foundation_borrow)


if __name__ == '__main__':
    unittest.main()

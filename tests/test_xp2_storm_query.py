from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault('CIV6_HOST_RESOURCE_ROOT', str(_REPO / 'civ6-rl-lab'))

from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime import xp2_storm_query as storm
from civ6_host.runtime.xp2_foundation_query_source import source as facade_source


class _Core:
    def __init__(self, base):
        self._handle = base


class _Memory:
    def __init__(self):
        self.bytes = {}

    def put(self, address, data):
        for offset, value in enumerate(data):
            self.bytes[address + offset] = value

    def read(self, address, size):
        try:
            return bytes(self.bytes[address + offset] for offset in range(size))
        except KeyError as exc:
            raise ValueError(f'unmapped fixture read {address:#x}+{size:#x}') from exc

    def qword(self, address, value):
        self.put(address, struct.pack('<Q', value))


class _Graph:
    def __init__(self):
        self.base = 0x7FF640000000
        self.context = self.base + 0x200000
        self.game = self.base + 0x201000
        self.service = self.base + 0x202000
        self.data = self.base + 0x210000
        self.memory = _Memory()
        self.core = _Core(self.base)
        self.order = []
        self.pair_written = 1
        self.item_values = (11, 29)
        self.pair_value = (0xFFFFFFFE, 5)
        self._install_sources_and_tables()
        self.native_calls = {
            'get_game': self.get_game,
            'release_game': self.release_game,
            'get_service': self.get_service,
            'query_values': self.query_values,
            'query_pair': self.query_pair,
            'release_service': self.release_service,
            'free_vector': self.free_vector,
        }

    def _install_body(self, body):
        if body.get('fragments'):
            for fragment in body['fragments']:
                self.memory.put(self.base + int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex']))
        else:
            for row in body['instructions']:
                self.memory.put(self.base + int(row['rva'], 16), bytes.fromhex(row['bytes']))

    def _install_sources_and_tables(self):
        facades = facade_source()
        for body in facades['functions'].values():
            self._install_body(body)
        for row in facades['tables'].values():
            table = self.base + int(row['vtable_rva'], 16)
            for slot, target in row['slots'].items():
                self.memory.qword(table + int(slot, 16), self.base + int(target, 16))
        parent = storm.load_pinned_json(storm._path(storm.PARENT_SOURCE[0]), storm.PARENT_SOURCE[1])
        profile = storm.source()
        for row in parent['functions'].values():
            self._install_body(row['body'])
        for row in profile['functions'].values():
            self._install_body(row['body'])
        self.memory.put(self.base + storm.SERVICE_IID_RVA, storm.SERVICE_IID)

        outer_table = 0xA101E8
        game_table = storm.GAME_VTABLE_RVA
        wrapper_table = storm.SERVICE_WRAPPER_VTABLE_RVA
        self.memory.qword(self.context, self.base + outer_table)
        self.memory.qword(self.game, self.base + game_table)
        self.memory.qword(self.service, self.base + wrapper_table)
        self.memory.qword(self.base + game_table + storm.GAME_SERVICE_SLOT,
                          self.base + storm.GAME_SERVICE_FACTORY_RVA)
        self.memory.qword(self.base + wrapper_table + storm.SERVICE_LIST_SLOT,
                          self.base + storm.SERVICE_LIST_RVA)
        self.memory.qword(self.base + wrapper_table + storm.SERVICE_PAIR_SLOT,
                          self.base + storm.SERVICE_PAIR_RVA)
        self.memory.qword(self.base + wrapper_table + storm.SERVICE_WRAPPER_RELEASE_SLOT,
                          self.base + storm.SERVICE_WRAPPER_RELEASE_RVA)

    @staticmethod
    def assertEqual(actual, expected):
        if actual != expected:
            raise AssertionError(f'{actual!r} != {expected!r}')

    def get_game(self, target, context):
        self.order.append(('get_game', target, context))
        self.assert_target(target, 'outer_game')
        return self.game

    def release_game(self, target, game):
        self.order.append(('release_game', target, game))
        self.assert_target(target, 'release_game')

    def get_service(self, target, game, iid_pointer):
        self.order.append(('get_service', target, game))
        self.assertEqual(target, self.base + storm.GAME_SERVICE_FACTORY_RVA)
        self.assertEqual(game, self.game)
        self.assertEqual(C.string_at(iid_pointer, 16), storm.SERVICE_IID)
        return self.service

    def query_values(self, target, service, key_pointer, vector_pointer):
        self.order.append(('query_values', target, service))
        self.assertEqual(target, self.base + storm.SERVICE_LIST_RVA)
        self.assertEqual(service, self.service)
        self.assertEqual(C.string_at(key_pointer, 8), b'\x02\x00\x03\x00\x04\x00\x00\x00')
        vector = C.cast(vector_pointer, C.POINTER(storm._Vector)).contents
        if self.item_values:
            raw = struct.pack('<' + 'I' * len(self.item_values), *self.item_values)
            self.memory.put(self.data, raw)
            vector.begin = self.data
            vector.end = self.data + len(raw)
            vector.capacity = self.data + len(raw)

    def query_pair(self, target, service, key_pointer, output_pointer):
        self.order.append(('query_pair', target, service))
        self.assertEqual(target, self.base + storm.SERVICE_PAIR_RVA)
        self.assertEqual(service, self.service)
        if self.pair_written:
            C.cast(output_pointer, C.POINTER(C.c_uint32 * 2)).contents[:] = self.pair_value
        return self.pair_written

    def free_vector(self, target, descriptor, begin, capacity_bytes):
        self.order.append(('free_vector', target, begin, capacity_bytes))
        self.assertEqual(target, self.base + storm.VECTOR_FREE_RVA)
        self.assertEqual(begin, self.data)

    def release_service(self, target, service):
        self.order.append(('release_service', target, service))
        self.assertEqual(target, self.base + storm.SERVICE_WRAPPER_RELEASE_RVA)

    def assert_target(self, target, operation):
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        abi = query_abi(XP2_CORE_SHA256, None)
        self.assertEqual(target, self.base + abi.rva(operation))


class XP2StormQueryTests(unittest.TestCase):
    def test_positive_vector_converts_before_pair_and_cleans_owned_objects(self):
        graph = _Graph()
        keys = []

        def position_query(core, context, value, *, read):
            self.assertIs(core, graph.core)
            self.assertEqual(context, graph.context)
            self.assertIs(read.__self__, graph.memory)
            keys.append(value)
            graph.order.append(('position', value))
            return struct.pack('<II', value + 100, value + 200)

        result = storm.query_storm_objects(
            graph.core, graph.context, b'\x02\x00\x03\x00\x04\x00\x00\x00',
            read=graph.memory.read, native_calls=graph.native_calls,
            index_to_position=position_query)
        self.assertEqual(result.items, (11, 29))
        self.assertEqual(result.positions,
                         (struct.pack('<II', 111, 211), struct.pack('<II', 129, 229)))
        self.assertEqual(result.position, (0xFFFFFFFE, 5))
        self.assertEqual(keys, [11, 29])
        self.assertEqual([row[0] for row in graph.order],
                         ['get_game', 'get_service', 'query_values', 'position', 'position',
                          'query_pair', 'free_vector', 'release_service', 'release_game'])

    def test_empty_vector_still_calls_pair_and_false_is_explicitly_undefined(self):
        graph = _Graph()
        graph.item_values = ()
        graph.pair_written = 0
        result = storm.query_storm_objects(
            graph.core, graph.context, b'\x02\x00\x03\x00\x04\x00\x00\x00',
            read=graph.memory.read, native_calls=graph.native_calls,
            index_to_position=lambda *args, **kwargs: self.fail('no index exists'))
        self.assertEqual(result.items, ())
        self.assertEqual(result.positions, ())
        self.assertIsNone(result.position)
        self.assertIn('query_pair', [row[0] for row in graph.order])
        self.assertNotIn('free_vector', [row[0] for row in graph.order])
        self.assertEqual([row[0] for row in graph.order][-2:], ['release_service', 'release_game'])

    def test_rejects_unqualified_inputs_and_source_failure_before_native_calls(self):
        graph = _Graph()
        args = (graph.core, graph.context, b'\x00' * 8)
        with self.assertRaises(ValueError):
            storm.query_storm_objects(*args, read=graph.memory.read,
                                      native_calls=graph.native_calls, core_sha256='0' * 64)
        with self.assertRaises(ValueError):
            storm.query_storm_objects(graph.core, graph.context, b'bad',
                                      read=graph.memory.read, native_calls=graph.native_calls)
        self.assertEqual(graph.order, [])
        with patch.object(storm, 'source_dependencies', side_effect=RuntimeError('source changed')):
            with self.assertRaisesRegex(RuntimeError, 'source changed'):
                storm.query_storm_objects(*args, read=graph.memory.read,
                                          native_calls=graph.native_calls)
        self.assertEqual(graph.order, [])

    def test_wrong_outer_vtable_fails_before_acquiring_game(self):
        graph = _Graph()
        graph.memory.qword(graph.context, graph.base + 0xA10EE8)
        with self.assertRaisesRegex(ValueError, 'outer interface'):
            storm.query_storm_objects(
                graph.core, graph.context, b'\x00' * 8,
                read=graph.memory.read, native_calls=graph.native_calls,
                index_to_position=lambda *args, **kwargs: b'\x00' * 8)
        self.assertEqual(graph.order, [])


if __name__ == '__main__':
    unittest.main()

"""XP2 combat source and real composed FIFO; only machine memory/calls are fixtures."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_combat_event_source as source
from civ6_host.runtime import a0_combat_events as admission
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256 as XP2, XP1_CORE_SHA256 as XP1
from civ6_host.runtime.event_argument_service import EventArgumentReader
from civ6_host.runtime.native import native_event_8256dbe1 as combat, native_event_a479f83f as experience
from civ6_host.runtime.native import native_event_45b517d6 as world, native_unit_promotion_query as promotion
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.paths import resource_root
from test_xp1_turn_a0 import scalar
import test_xp2_placement_composition as placement_composition


class Fixture:
    def __init__(self):
        self.graph, _, _, _ = placement_composition.XP2PlacementCompositionTests().graph()
        g = self.graph
        self.owner, self.backend, self.deferred, self.memory = g.owner, g.backend, g.event.deferred, g.memory
        # The reused sparse native-memory fixture creates DeferredService via
        # __new__; mirror its constructor's two initially uninstalled owners.
        self.deferred.combat_map_registry = self.deferred.combat_receiver = None
        self.base = self.backend.core._handle
        self.deferred.base = self.base
        sys.path.insert(0, str(resource_root() / 'tools'))
        from extract_phase31_next_export import pefile
        self.pe = pefile.PE(source.source()['image']['path'], fast_load=True)
        self.calls, self.maps, self.closed_maps, self.next_nodes, self.map_fields = [], set(), set(), {}, {}
        self.allocations = []
        self.cursor, self.fail_at = 0x7c000000, None
        self.query_result, self.promotion_index = 1, 23
        self.service, self.result_variant, self.result_value = 0x79500000, 0x79500100, 0x79500200
        self.memory.put(self.service, struct.pack('<QI', self.base + 0xa12a00, 1))
        self.memory.put(self.base + 0xb8e140, struct.pack('<Q', 0x79600000))
        self.memory.put(0x79600000 + 0x2dac, struct.pack('<i', 63))
        self.original_read = self.memory.read
        self.owner.read = self.deferred.read = self.backend.runtime.read = self.read
        self.memory.read = self.read
        g.continuation.publisher.read = self.read
        g.continuation.publisher._facades.backend.read = self.read
        self.backend.host._check = DiagnosticHost._check.__get__(self.backend.host)
        previous = self.backend.stage, self.backend.prefix, self.backend.busy
        self.backend.stage, self.backend.prefix, self.backend.busy = 'prepared', None, False
        try:
            admission.enable(self.owner, self.backend)
        finally:
            self.backend.stage, self.backend.prefix, self.backend.busy = previous
        with patch.object(C, 'WINFUNCTYPE', self.factory):
            self.graph.event.arguments.reader = EventArgumentReader(self.backend.core, core_sha256=XP2, read=self.read)

    def read(self, address, size):
        if any(pointer <= address and address + size <= pointer + 88 for pointer in self.maps):
            return C.string_at(address, size)
        if self.base <= address and address + size <= self.base + self.pe.OPTIONAL_HEADER.SizeOfImage:
            raw = self.pe.get_data(address - self.base, size)
            return bytes(self.memory.memory[address + i] if address + i in self.memory.memory
                         else raw[i] for i in range(size))
        return self.original_read(address, size)

    def allocate(self, raw):
        pointer = self.cursor
        self.cursor += max(0x100, (len(raw) + 0xff) & ~0xff)
        self.memory.put(pointer, raw)
        self.allocations.append((pointer, len(raw)))
        return pointer

    def blob(self, raw, tag=1024):
        return struct.pack('<H6xQII', tag, self.allocate(raw), len(raw), 0x21000001)

    def add_map(self, fields, pointer=None):
        pointer = self.allocate(bytes(88)) if pointer is None else pointer
        sentinel = pointer + 0x30
        nodes = [self.allocate(bytes(64)) for _ in fields]
        header = bytearray(88)
        struct.pack_into('<Q', header, 0, self.base + 0xabf080)
        struct.pack_into('<QQ', header, 0x30, sentinel, nodes[0] if nodes else sentinel)
        struct.pack_into('<I', header, 0x50, len(fields))
        if pointer in self.maps:
            C.memmove(pointer, bytes(header), 88)
        else:
            self.memory.put(pointer, header)
        for i, ((key, value), node) in enumerate(zip(fields.items(), nodes)):
            raw = bytearray(64)
            struct.pack_into('<I', raw, 0x20, key); raw[0x28:] = value
            self.memory.put(node, raw)
            self.next_nodes[node] = nodes[i + 1] if i + 1 < len(nodes) else sentinel
        self.map_fields[pointer] = dict(fields)
        return pointer

    def list_variant(self, texts):
        elements = b''.join(struct.pack('<H6xQII', 5, self.allocate(text), 1, 0x21000000 | len(text))
                            for text in texts)
        begin = self.allocate(elements)
        raw = bytearray(72); struct.pack_into('<Q', raw, 0, self.base + 0xabfb80)
        struct.pack_into('<QQQ', raw, 40, begin, begin + len(elements), begin + len(elements))
        return struct.pack('<H6xQII', 11, self.allocate(raw), 0, 0x11000000)

    def clone_variant(self, raw):
        value = bytearray(raw); tag = struct.unpack_from('<H', raw)[0]
        pointer, width, flags = struct.unpack_from('<QII', raw, 8)
        if tag == 10:
            pointer = self.add_map({key: self.clone_variant(v) for key, v in self.map_fields[pointer].items()})
        elif tag == 11 and pointer:
            begin, end = struct.unpack('<QQ', self.read(pointer + 40, 16))
            elements = b''.join(self.clone_variant(self.read(p, 24)) for p in range(begin, end, 24))
            copied_begin = self.allocate(elements)
            copied = bytearray(self.read(pointer, 72))
            struct.pack_into('<QQQ', copied, 40, copied_begin, copied_begin + len(elements), copied_begin + len(elements))
            pointer = self.allocate(copied)
        elif flags & 0x20000000 and pointer:
            pointer = self.allocate(self.read(pointer, width * (flags & 0xffffff)))
        struct.pack_into('<Q', value, 8, pointer)
        return bytes(value)

    def factory(self, result, *types):
        def bind(target):
            rva = target - self.base
            if rva == 0x994d90:
                return lambda node: self.next_nodes[node]
            methods = {0x99e4b0: 'ctor', 0x99e6c0: 'assign', 0x99e5d0: 'dtor',
                       0x5976c0: 'predicate', 0x5904c0: 'service', 0x8972d0: 'outer_release',
                       0x5a2a40: 'query', 0x5a2a70: 'service_release', 0x99f5c0: 'lookup'}
            if rva not in methods:
                return self.graph.factory(result, *types)(target)
            def invoke(receiver, *args):
                name = methods[rva]; self.calls.append((name, receiver, *args))
                if name == self.fail_at:
                    raise RuntimeError('fixture native ' + name + ' failure')
                if name == 'ctor':
                    assert result is C.c_void_p and types == (C.c_void_p,)
                    self.maps.add(receiver); self.add_map({}, receiver); return receiver
                if name == 'assign':
                    assert result is C.c_void_p and types == (C.c_void_p, C.c_void_p)
                    self.add_map({k: self.clone_variant(v) for k, v in self.map_fields[args[0]].items()}, receiver)
                    return receiver
                if name == 'dtor':
                    assert result is None and receiver in self.maps and receiver not in self.closed_maps
                    self.closed_maps.add(receiver); return None
                if name == 'predicate':
                    assert result is C.c_uint8 and types == (C.c_void_p, C.c_int32)
                    assert receiver == self.graph.continuation.publisher._facades.game_facade
                    state = struct.unpack('<Q', self.read(self.base + 0xb8e140, 8))[0]
                    selected_owner = struct.unpack('<i', self.read(state + 0x2dac, 4))[0]
                    return int(args[0] == selected_owner or selected_owner == 1000)
                if name == 'service':
                    assert receiver == self.backend.context; return self.service
                if name == 'outer_release':
                    assert receiver == self.backend.context; return None
                if name == 'query':
                    descriptor, command, parameters, flag, output = args
                    assert receiver == self.service and (command, flag) == (0xb4edd43f, 1)
                    assert C.string_at(descriptor, 8) == struct.pack('<HHI', 3, 1, 17)
                    assert struct.unpack_from('<I', self.deferred.pending[-1], 4)[0] == 74
                    assert parameters in self.maps and output in self.maps
                    return self.query_result
                if name == 'lookup':
                    assert args == (0x315247e7,)
                    self.memory.put(self.result_variant, struct.pack('<H6xQII', 2, self.result_value, 0, 0x20000001))
                    self.memory.put(self.result_value, struct.pack('<I', self.promotion_index))
                    return self.result_variant
                if name == 'service_release':
                    assert receiver == self.service; return None
                raise AssertionError(name)
            return invoke
        return bind

    def combat_fields(self, modifiers=False):
        fields = {int(row['key'], 16): scalar(row['variant_tag'], 0) for row in source.source()['root_fields']}
        from civ6_host.runtime.native.native_combat_argument_snapshot import CHILD_KEYS
        for index, key in enumerate(CHILD_KEYS):
            values = {key: scalar(2, 0) for key in combat.CHILD_SCALAR_KEYS}
            values[0x57c6ed30] = self.blob(struct.pack('<HHI', (3, 63, 4, 5)[index], 1, 17 + index))
            values[0x95f2cf6e] = self.blob(struct.pack('<ii', index, index + 1), 13)
            if modifiers and index == 0:
                for modifier in source.source()['contract']['modifier_list_keys']:
                    values[modifier] = self.list_variant((b'Native terrain bonus\0', b'Native combat modifier\0'))
            fields[key] = struct.pack('<H6xQII', 10, self.add_map(values), 0, 0x05000000)
        return fields

    def dispatch(self, kind, fields):
        with patch.object(C, 'WINFUNCTYPE', self.factory):
            return self.graph.event.arguments.dispatch(self.backend.host.pointer, kind, self.add_map(fields))

    def drain(self):
        with patch.object(C, 'WINFUNCTYPE', self.factory):
            return self.deferred.drain()

    def close(self):
        self.pe.close()
        if not self.owner.quarantined and not self.deferred.pending:
            self.owner.close()


class XP2CombatEventTests(unittest.TestCase):
    def fixture(self):
        f = Fixture(); self.addCleanup(f.close); return f

    def test_source_methods_live_guards_and_known_optional_modifier_shape(self):
        p = source.source()
        self.assertEqual(len(p['functions']), 34)
        for path, digest in source.source_dependencies().items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)
        layout = source.promotion_layout(XP2, promotion.METHODS, promotion.SLOTS)
        self.assertEqual(layout.methods['query'][0], 0x5a2a40)
        self.assertEqual(len(source.promotion_proof(XP2, {})['core_functions']['service_release']['fragments'][0]['instructions']), 9)
        with self.assertRaises(ValueError): source.verify_source(XP1)
        mandatory = {k: scalar(2, 0) for k in combat.CHILD_SCALAR_KEYS}
        mandatory.update({0x57c6ed30: bytes(24), 0x95f2cf6e: bytes(24)})
        for modifier in p['contract']['modifier_list_keys']:
            source.validate_child_fields(XP2, {**mandatory, modifier: struct.pack('<H6xQII', 11, 123, 0, 0x11000000)}, combat.CHILD_SCALAR_KEYS)
        for key, tag in ((0x46421e43, 10), (0x12345678, 11)):
            with self.assertRaises(ValueError):
                source.validate_child_fields(XP2, {**mandatory, key: struct.pack('<H6xQII', tag, 123, 0, 0x11000000)}, combat.CHILD_SCALAR_KEYS)

    def test_full_map_with_modifier_lists_retained_until_real_fifo_posthook(self):
        f = self.fixture(); fields = f.combat_fields(modifiers=True)
        borrowed = list(f.allocations)
        self.assertEqual(f.dispatch(0x8256dbe1, fields), 0)
        record = f.deferred.pending[0]
        self.assertEqual(struct.unpack_from('<IIII', record), (128, 248, 1, 0))
        self.assertEqual(struct.unpack_from('<I', record, 72)[0], 0x12)
        registry = f.owner.combat_map_registry; owned = registry.lookup(1)
        self.assertEqual(owned.core_sha256, XP2)
        child = struct.unpack_from('<Q', f.map_fields[owned.pointer][0x55592f25], 8)[0]
        lists = {k: v for k, v in f.map_fields[child].items() if k in source.source()['contract']['modifier_list_keys']}
        self.assertEqual(len(lists), 10)
        for pointer, size in borrowed:
            f.memory.put(pointer, b'\xff' * size)
        list_ptr = struct.unpack_from('<Q', lists[0x46421e43], 8)[0]
        begin = struct.unpack('<Q', f.read(list_ptr + 40, 8))[0]
        text_ptr = struct.unpack_from('<Q', f.read(begin, 24), 8)[0]
        self.assertEqual(f.read(text_ptr, 21), b'Native terrain bonus\0')
        self.assertFalse(owned.closed)
        receipts = [v for k, v in f.graph.event.emitted if k == 'native_combat_record_enqueued']
        self.assertEqual(receipts[-1]['source_proof_sha256'], source.SOURCE[1])
        self.assertFalse(receipts[-1]['administrative_snapshot_complete'])
        self.assertFalse(receipts[-1]['modifier_values_decoded'])
        self.assertEqual(f.drain(), 1); self.assertEqual(f.drain(), 0)
        self.assertTrue(owned.closed); self.assertEqual(registry.entries, {})
        self.assertEqual([c[0] for c in f.calls], ['ctor', 'assign', 'predicate', 'predicate', 'dtor'])
        self.assertIsNone(f.owner._foundation_borrow)

    def test_experience_query_then_promotion_and_world_text_share_ordered_fifo(self):
        f = self.fixture()
        fields = {experience.SELECTOR_KEY: scalar(3, 0),
                  experience.DESCRIPTOR_KEY: f.blob(struct.pack('<HHI', 3, 1, 17))}
        self.assertEqual(f.dispatch(0xa479f83f, fields), 0)
        text = b'Native message\0'
        world_fields = {world.SELECTOR_KEY: scalar(3, 0),
            world.DESCRIPTOR_KEY: f.blob(struct.pack('<HHI', 3, 1, 17)),
            world.POSITION_KEY: f.blob(struct.pack('<ii', 3, 4), 0),
            world.TEXT_KEY: struct.pack('<H6xQII', 5, f.allocate(text), 1, 0x21000000 | len(text))}
        self.assertEqual(f.dispatch(0x45b517d6, world_fields), 0)
        self.assertEqual([struct.unpack_from('<II', r, 4) for r in f.deferred.pending], [(74, 1), (79, 2), (250, 3)])
        self.assertEqual(struct.unpack_from('<I', f.deferred.pending[1], 96)[0], 23)
        self.assertEqual(f.deferred.pending[2][100:115], text)
        self.assertEqual([c[0] for c in f.calls], ['service', 'outer_release', 'ctor', 'ctor', 'query', 'lookup', 'dtor', 'dtor', 'service_release'])
        self.assertEqual(f.drain(), 3); self.assertEqual(f.drain(), 0)

    def test_changed_query_slot_and_failed_posthook_do_not_commit(self):
        f = self.fixture()
        f.memory.put(f.base + 0xa10ee8 + 0x130, struct.pack('<Q', f.base + 0x4c3ed0))
        with self.assertRaisesRegex(ValueError, 'virtual slot'):
            f.dispatch(0x8256dbe1, f.combat_fields())
        self.assertEqual(f.deferred.pending, [])
        self.assertTrue(f.owner.quarantined)
        self.assertFalse(any(row[0] in ('predicate', 'dtor') for row in f.calls))
        f = self.fixture(); self.assertEqual(f.dispatch(0x8256dbe1, f.combat_fields()), 0)
        head = f.deferred.pending[0]; owner = f.owner.combat_map_registry.lookup(1)
        f.fail_at = 'dtor'
        with self.assertRaisesRegex(RuntimeError, 'dtor failure'): f.drain()
        self.assertIs(f.deferred.pending[0], head); self.assertEqual(f.deferred.consumed_count, 0)
        self.assertFalse(owner.closed); self.assertTrue(f.owner.combat_map_registry.poisoned)
        with self.assertRaisesRegex(RuntimeError, 'poisoned'): f.drain()
        self.assertEqual(sum(row[0] == 'dtor' for row in f.calls), 1)


if __name__ == '__main__':
    unittest.main()

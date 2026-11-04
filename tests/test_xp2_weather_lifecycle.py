"""Pinned lifecycle source and bounded copied inputs; no engine execution."""
import json
import struct
from types import SimpleNamespace as NS
import unittest

from civ6_host.runtime import xp2_weather_lifecycle as source
from civ6_host.runtime.a0_family_source import _path
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


def scalar(tag, value):
    return struct.pack('<IIQII', tag, 0, value, 0, 0)


def inputs(kind, *, indices=(19, 27), position=(5, 3)):
    memory = {0x100000: struct.pack('<ii', *position),
              0x200000: struct.pack('<' + str(len(indices)) + 'I', *indices)}
    fields = {source.SELECTOR: scalar(2 if kind == source.STORM_CHANGED else 3, 0),
              source.IDENTIFIER: scalar(3, 7),
              source.POSITION: struct.pack('<IIQII', 13, 0, 0x100000, 8, 0x21000001)}
    if kind == source.STORM_CHANGED:
        fields[source.STATUS] = scalar(2, 2)
        fields[source.INPUT_INDICES] = struct.pack('<IIQII', 2, 0,
            0x200000 if indices else 0, 4, 0x21000000 | len(indices) if indices else 0x20000000)
    elif kind == source.DROUGHT_REMOVED:
        fields[source.DROUGHT_STATUS] = scalar(2, 1)
    calls = []
    def read(address, count):
        calls.append((address, count))
        for base, raw in memory.items():
            if base <= address and address + count <= base + len(raw):
                return raw[address-base:address-base+count]
        raise ValueError('outside fixture memory')
    return fields, memory, read, calls


class WeatherLifecycleSourceTests(unittest.TestCase):
    def test_exact_update_expiry_receivers_and_independent_source_correspondence(self):
        p = source.source()
        self.assertEqual(source.KINDS, {0x21e62149, 0xfee911d7, 0xa5168c8e})
        self.assertEqual({r['event_name'] for r in p['receiver_rows'].values()},
                         {'GameCoreEvent::StormChanged', 'GameCoreEvent::StormRemovedFromMap',
                          'GameCoreEvent::DroughtRemovedFromMap'})
        self.assertFalse(p['omission']['synthetic_records'])
        self.assertEqual(p['omission']['fifo_sequence_increment'], 0)
        self.assertFalse(p['omission']['cache_update_presence_required_per_callback'])
        pins = source.source_dependencies()
        self.assertIn(source.SOURCE[1], pins.values())
        self.assertIn('21180213a91f5292da14fac2cf37ecb21a76bdd26a75b7ecccc7921b355aa844', pins.values())
        for mutate in (
            lambda d: d['routes']['0x21e62149']['fields'].__setitem__('0xa1e5a149', 3),
            lambda d: d['routes']['0xfee911d7'].__setitem__('return_consumed', True),
            lambda d: d['omission'].__setitem__('fifo_sequence_increment', 1),
            lambda d: d['receiver_rows']['0x13a'].__setitem__('handler_rva', '0xd6190'),
        ):
            changed = json.loads(_path(source.SOURCE[0]).read_text())
            mutate(changed)
            with self.assertRaises(ValueError):
                source._verify(changed)

    def test_full_live_producer_binding_rejects_wrong_engine_and_changed_bytes(self):
        values = {}
        base = 0x30000000
        def put(address, raw):
            values.update({address+i: byte for i, byte in enumerate(raw)})
        calls = []
        def read(address, count):
            calls.append((address, count))
            return bytes(values[address+i] for i in range(count))
        for rva, raw in source.core_fragments():
            put(base+rva, raw)
        core = NS(_handle=base)
        backend = NS(core=core, load_abi=NS(core_sha256=XP2_CORE_SHA256), check_thread=lambda: None)
        self.assertEqual(source.bind_owner(backend, core, read), source.SOURCE[1])
        self.assertTrue(calls)
        self.assertLessEqual(max(count for _, count in calls), 4096)
        self.assertEqual(sum(count for _, count in calls), 9933)
        values[base+0x1c05de] ^= 1
        with self.assertRaisesRegex(ValueError, 'live producer'):
            source.bind_owner(backend, core, read)
        backend.load_abi.core_sha256 = XP1_CORE_SHA256
        with self.assertRaisesRegex(ValueError, 'exact XP2'):
            source.bind_owner(backend, core, read)

    def test_copied_administrative_values_outlive_borrow_without_pointer_headers(self):
        for kind in source.KINDS:
            fields, memory, read, calls = inputs(kind, indices=tuple(range(1300)))
            decoded = source.decode_fields(kind, fields, read)
            before = decoded.to_admin()
            memory.clear()
            fields.clear()
            self.assertEqual(decoded.to_admin(), before)
            self.assertEqual(before['identifier'], 7)
            self.assertEqual(before['input_position'], [5, 3])
            self.assertFalse(before['borrowed_pointer_addresses_retained'])
            self.assertLessEqual(max(size for _, size in calls), 4096)
            if kind == source.STORM_CHANGED:
                self.assertEqual(before['input_plot_indices'], list(range(1300)))
                self.assertEqual(calls, [(0x100000, 8), (0x200000, 4096), (0x201000, 1104)])
            else:
                self.assertIsNone(before['input_plot_indices'])
                self.assertEqual(calls, [(0x100000, 8)])
        fields, _, read, calls = inputs(source.STORM_CHANGED, indices=())
        self.assertEqual(source.decode_fields(source.STORM_CHANGED, fields, read).input_plot_indices, ())
        self.assertEqual(calls, [(0x100000, 8)])

    def test_unqualified_shapes_short_payloads_and_unbounded_vectors_refuse(self):
        for key, raw in (
            (source.SELECTOR, scalar(3, 0)),
            (source.POSITION, struct.pack('<IIQII', 13, 0, 0, 8, 0x21000001)),
            (source.INPUT_INDICES, struct.pack('<IIQII', 2, 0, 0x200000, 8, 0x21000002)),
            (source.INPUT_INDICES, struct.pack('<IIQII', 2, 0, 0x200000, 4, 0x21010001)),
            (source.INPUT_INDICES, struct.pack('<IIQII', 2, 0, 0x200000, 4, 0x20000000)),
        ):
            fields, _, read, _ = inputs(source.STORM_CHANGED)
            fields[key] = raw
            with self.assertRaises(ValueError):
                source.decode_fields(source.STORM_CHANGED, fields, read)
        fields, _, _, _ = inputs(source.STORM_CHANGED)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            source.decode_fields(source.STORM_CHANGED, fields, lambda *_: b'')
        with self.assertRaisesRegex(ValueError, 'shape'):
            source.decode_fields(0x12345678, fields, lambda *_: b'')
        with self.assertRaisesRegex(ValueError, 'real A0'):
            source.validate_empty_owner(NS())


if __name__ == '__main__':
    unittest.main()

"""XP2-selected shared logger state and atomic ownership checks; no DLL runs."""
import ctypes as C
import json
import unittest
from unittest.mock import patch
from civ6_host.runtime import xp1_saved_load_logger as m
from civ6_host.runtime.configuration_profiles import _copy
from test_xp1_saved_load_logger import backend as xp1_backend


def backend():
    b, calls, mem = xp1_backend()
    b.profile.core_sha256 = m.XP2_CORE_SHA256
    proof = m._checked_source(m.XP2_CORE_SHA256)
    supplement = m._checked_xp2_supplement()
    mem.clear()
    base = b.core._handle
    mem.update({base + int(r['rva'], 16): bytes.fromhex(r['bytes'])
                for r in proof['live_windows'].values()})
    for fragment in supplement['bodies']['xp2_level_roundtrip']['body']['fragments']:
        mem[base + int(fragment['start_rva'], 16)] = bytes.fromhex(fragment['raw_hex'])
    mem[base + 0xB8AA90] = C.addressof(b.host.logger_object).to_bytes(8, 'little')
    b.runtime.read = lambda address, size: mem.get(address, b'')[:size]
    for slot in (*m.XP2_EXTRA_SLOTS, 0x48):
        callback = b.host._unsupported('logger', slot)
        b.host._slot_bindings[C.addressof(b.host.logger_vtable), slot] = (
            b.host.logger_vtable[slot // 8], callback)
    return b, calls, mem


class XP2Logger(unittest.TestCase):
    def test_selected_group_preserves_channel_flags_levels_and_sink(self):
        b, calls, _ = backend()
        h = b.host
        before = json.dumps(h.log_channels)
        table = tuple(h.logger_vtable)
        sink = h.log_writers.active_sink
        receipt = m.install_saved_load_logger(b)
        self.assertEqual([r[0] for r in calls], list(m.SLOTS + m.XP2_EXTRA_SLOTS))
        self.assertEqual(receipt['core_sha256'], m.XP2_CORE_SHA256)
        self.assertEqual(receipt['source_sha256'], m.XP2_SOURCE[1])
        self.assertEqual(receipt['supplement_source_sha256'], m.XP2_SUPPLEMENT[1])
        self.assertFalse(receipt['native_load_success_claimed'])
        self.assertEqual(before, json.dumps(h.log_channels))
        self.assertIs(h.log_writers.active_sink, sink)
        self.assertFalse(hasattr(b, '_xp1_load_logger_activation'))
        for i, pointer in enumerate(table):
            if i * 8 not in m.SLOTS + m.XP2_EXTRA_SLOTS:
                self.assertEqual(h.logger_vtable[i], pointer)
        # Existing EXE channel semantics keep the whole DWORD and byte values.
        level = next(r[3] for r in calls if r[0] == 0x38)
        self.assertEqual(level(C.addressof(h.logger_object), 0xC95E0BC4), 0xA1B2C3D4)
        enabled = next(r[3] for r in calls if r[0] == 0x10)
        self.assertEqual(enabled(C.addressof(h.logger_object), 123), 0)
        with self.assertRaises(ValueError):
            m.install_saved_load_logger(b)
        self.assertEqual(len(calls), len(m.SLOTS + m.XP2_EXTRA_SLOTS))

    def test_wrong_engine_global_code_or_callback_owner_refuses_atomically(self):
        for mutation in ('xp1_global', 'caller', 'owner', 'sink', 'prepared'):
            with self.subTest(mutation=mutation):
                b, calls, mem = backend()
                if mutation == 'xp1_global':
                    value = mem.pop(b.core._handle + 0xB8AA90)
                    mem[b.core._handle + 0x9F2650] = value
                elif mutation == 'caller':
                    key = min(mem); raw = mem[key]
                    mem[key] = bytes([raw[0] ^ 1]) + raw[1:]
                elif mutation == 'owner':
                    key = C.addressof(b.host.logger_vtable), 0x50
                    pointer, _ = b.host._slot_bindings[key]
                    b.host._slot_bindings[key] = pointer, lambda: None
                elif mutation == 'sink':
                    b.host.log_writers.active_sink = None
                else:
                    b.stage = 'initialized'
                with self.assertRaises(ValueError):
                    m.install_saved_load_logger(b)
                self.assertEqual(calls, [])

    def test_xp2_slot30_updates_shared_level_state_with_official_creation_rules(self):
        b, calls, _ = backend()
        h = b.host
        before = dict(h.log_channels[0xC95E0BC4])
        m.install_saved_load_logger(b)
        callback = next(row[3] for row in calls if row[0] == 0x30)
        this = C.addressof(h.logger_object)
        callback(this, 0xC95E0BC4, 0xFEDCBA98)
        self.assertEqual(h.log_channels[0xC95E0BC4]['level'], 0xFEDCBA98)
        for key in ('filename', 'flags', 'enabled'):
            self.assertEqual(h.log_channels[0xC95E0BC4][key], before[key])
        callback(this, 0x12345678, 0)
        self.assertNotIn(0x12345678, h.log_channels)
        callback(this, 0x12345678, 0x80000001)
        self.assertEqual(h.log_channels[0x12345678],
                         {'filename': None, 'flags': 0, 'enabled': 1, 'level': 0x80000001})
        with self.assertRaises(ValueError):
            callback(this + 8, 0xC95E0BC4, 1)

    def test_xp2_source_inventory_keeps_distinct_slot48_out_of_failed_call_chain(self):
        proof = m._checked_xp2_supplement()
        self.assertEqual(proof['contracts']['0x30']['channel'], 'uint32 in EDX')
        self.assertEqual(proof['contracts']['0x30']['level'], 'uint32 in R8D')
        self.assertTrue(proof['xp2_logger_interface_slot_callers']['0x48'])
        failed = [row['rva'] for row in proof['xp2_logger_interface_slot_callers']['0x30']]
        self.assertIn('0x4316e3', failed)
        self.assertNotIn(0x48, m.XP2_EXTRA_SLOTS)
        self.assertEqual(proof['contracts']['0x48']['limits'][-1],
                         'The failing XP2 call chain uses +0x38/+0x30; it does not call +0x48.')

    def test_xp2_slot48_stays_fail_closed_until_its_hash_and_header_contract_is_closed(self):
        b, calls, _ = backend()
        h = b.host
        table = C.addressof(h.logger_vtable)
        pointer = h.logger_vtable[0x48 // 8]
        unsupported = h._slot_bindings[table, 0x48][1]
        m.install_saved_load_logger(b)
        self.assertNotIn(0x48, [row[0] for row in calls])
        self.assertEqual(h.logger_vtable[0x48 // 8], pointer)
        with self.assertRaisesRegex(ValueError, 'unimplemented native service'):
            unsupported(C.addressof(h.logger_object))

    def test_exact_source_contract_and_complete_body_required(self):
        original = m._source
        source = _copy(m._checked_source(m.XP2_CORE_SHA256))
        for mutation in ('engine', 'abi', 'fragment', 'assertion'):
            with self.subTest(mutation=mutation):
                changed = _copy(source)
                if mutation == 'engine':
                    changed['image_sha256'] = m.XP1_CORE_SHA256
                elif mutation == 'abi':
                    changed['contracts']['0x38'] = 'bool'
                elif mutation == 'fragment':
                    changed['bodies']['optional_writer']['body']['fragments'][0]['instructions'].pop()
                else:
                    changed['assertions'][0]['text'] = 'ret'
                with patch.object(m, '_source', side_effect=lambda ref:
                                  changed if ref == m.XP2_SOURCE else original(ref)):
                    with self.assertRaises(ValueError):
                        m._checked_source(m.XP2_CORE_SHA256)
        pins = m.source_dependencies(m.XP2_CORE_SHA256)
        self.assertIn(m.XP2_SOURCE[1], pins.values())
        self.assertIn(m.XP2_SUPPLEMENT[1], pins.values())
        self.assertIn(m.SOURCE[1], pins.values())

    def test_supplement_rejects_changed_slot30_body_contract_or_caller(self):
        original = m._source
        source = _copy(m._checked_xp2_supplement())
        for mutation in ('contract', 'body', 'caller'):
            with self.subTest(mutation=mutation):
                changed = _copy(source)
                if mutation == 'contract':
                    changed['contracts']['0x30']['level'] = 'uint8 in R8B'
                elif mutation == 'body':
                    changed['bodies']['exe_logger_set_level_slot_30']['fragments'][0]['instructions'].pop()
                else:
                    changed['callsite_assertions'][1]['text'] = 'ret'
                with patch.object(m, '_source', side_effect=lambda ref:
                                  changed if ref == m.XP2_SUPPLEMENT else original(ref)):
                    with self.assertRaises(ValueError):
                        m._checked_xp2_supplement()


if __name__ == '__main__':
    unittest.main()

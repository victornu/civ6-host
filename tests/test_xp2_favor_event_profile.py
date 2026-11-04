"""Favor transport source, existing scalar encoder and actual composed FIFO."""
import copy
import json
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_favor_event_profile as favor
from civ6_host.runtime.a0_family_source import _path, verify_pinned_files
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
import test_xp2_climate_composition as composition


def scalar(tag, value):
    return struct.pack('<IIQII', tag, 0, value & 0xffffffff, 0, 0)


class FavorTests(unittest.TestCase):
    def fields(self):
        return {favor.SELECTOR_KEY: scalar(3, 0),
                favor.VALUE_KEYS[0]: scalar(2, 7),
                favor.VALUE_KEYS[1]: scalar(2, 0x80000001),
                favor.VALUE_KEYS[2]: scalar(2, 0xffffffff)}

    def encode(self, fields=None, sequence=1, **options):
        guards = dict(empty_receiver_state=dict(favor.EMPTY_RECEIVER_STATE),
                      normalizer_transform_present=False, per_thread_hook_present=False,
                      writer_metadata_callback_present=False)
        guards.update(options)
        return favor.encode(favor.EVENT_KIND, self.fields() if fields is None else fields,
                            sequence, **guards)

    def test_real_dependencies_and_official_favor_receiver(self):
        pins = favor.source_dependencies()
        verify_pinned_files(pins)
        self.assertEqual(len(pins), 5)
        self.assertIn(favor.SOURCE[1], pins.values())
        self.assertEqual(favor.receiver_row(0x142)['event_name'], 'GameCoreEvent::FavorChanged')
        self.assertEqual(favor.receiver_row(0x142)['handler_va'], '0x1400d6550')
        self.assertIsNone(favor.receiver_row(0x143))
        self.assertEqual(dict(favor.event_profile(core_sha256=XP2_CORE_SHA256).record_sizes), {0x142: 96})
        self.assertEqual(favor.source_dependencies(core_sha256=XP1_CORE_SHA256), {})
        with self.assertRaises(ValueError):
            favor.event_profile(core_sha256=XP1_CORE_SHA256)
        with self.assertRaises(ValueError):
            favor.source_dependencies(core_sha256='unknown')

    def test_actual_producer_call_and_setters_determine_shape(self):
        p = favor.source()
        producer = favor._text(p['functions']['xp2_26c410'], 0x180000000)
        self.assertEqual(producer[0x26c4aa], 'mov qword ptr [rsp + 0x20], 0x68e7d3da')
        self.assertEqual(producer[0x26c4d5], 'jmp 0x1805fc680')
        builder = favor._text(p['functions']['xp2_5fc680'], 0x180000000)
        self.assertEqual(builder[0x5fc6d5], 'call 0x1809a0000')
        self.assertEqual([builder[rva] for rva in (0x5fc6e7, 0x5fc6f9, 0x5fc70b)],
                         ['call 0x18099fee0']*3)
        self.assertEqual(tuple((f['key'], f['tag']) for f in p['fields']),
                         (('0xa1e5a149', 3), ('0xd6fcf3e4', 2),
                          ('0xa1fbc372', 2), ('0x38f292c8', 2)))
        self.assertEqual(p['inventory']['direct_siblings_in_producer'], ())
        self.assertTrue(p['contract']['core_internal_dispatch_precedes_a0'])
        self.assertFalse(p['contract']['callback_queries_core'])

    def test_mapping_mutations_fail_even_without_the_file_hash_gate(self):
        original = json.loads(_path(favor.SOURCE[0]).read_text())
        refs = {key: favor._source((r['path'], r['sha256']))
                for key, r in original['references'].items()}
        for change in ('tag', 'builder', 'writer', 'name'):
            p = copy.deepcopy(original)
            if change == 'tag':
                p['fields'][2]['tag'] = 3
            elif change == 'name':
                p['receiver']['event_name'] = 'GameCoreEvent::EmergencyAvailable'
            else:
                function, address = ('xp2_5fc680', '0x1805fc6f9') if change == 'builder' else (
                    'exe_126570', '0x140126618')
                next(r for r in favor._rows(p['functions'][function]) if r['va'] == address)['text'] = 'nop'
            with self.subTest(change=change), self.assertRaises(ValueError):
                favor._validate_contract(p, refs['parameter_primitives'], refs['normalizer'],
                                         refs['receiver_dispatch'])

    def test_source_byte_mutation_is_refused(self):
        p = json.loads(_path(favor.SOURCE[0]).read_text())
        p['functions']['exe_146600']['capture']['fragments'][0]['instructions'][-1]['bytes'] = '90'
        favor.source.cache_clear()
        try:
            with patch.object(favor, '_source', return_value=p), self.assertRaisesRegex(ValueError, 'fragment'):
                favor.source()
        finally:
            favor.source.cache_clear()

    def test_shared_encoder_preserves_all_three_dwords_and_native_header(self):
        record = self.encode(sequence=0xffffffff)
        self.assertEqual(len(record), 96)
        self.assertEqual(struct.unpack_from('<4I', record), (96, 0x142, 0xffffffff, 0))
        self.assertEqual(struct.unpack_from('<2I', record, 16), (0xffffffff, 0xffffffff))
        for offset in (24, 32, 40, 48, 56):
            self.assertEqual(struct.unpack_from('<HHI', record, offset), (0xffff, 0, 0xffffffff))
        self.assertEqual(record[64:80], bytes(16))
        self.assertEqual(struct.unpack_from('<4I', record, 80),
                         (0xffffffff, 7, 0x80000001, 0xffffffff))

    def test_missing_extra_wrong_tags_flags_selectors_and_sequence_refuse(self):
        fields = self.fields()
        for key in fields:
            changed = {**fields, key: scalar(2 if key == favor.SELECTOR_KEY else 3, 0)}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.encode(changed)
        malformed = [dict(list(fields.items())[1:]), {**fields, 0x123: scalar(2, 9)},
                     {**fields, favor.SELECTOR_KEY: scalar(3, 1)},
                     {**fields, favor.VALUE_KEYS[0]: bytes(8)}]
        flag = bytearray(fields[favor.VALUE_KEYS[0]])
        struct.pack_into('<I', flag, 20, 1)
        malformed.append({**fields, favor.VALUE_KEYS[0]: bytes(flag)})
        for changed in malformed:
            with self.assertRaises(ValueError):
                self.encode(changed)
        for sequence in (0, -1, True, 0x100000000):
            with self.assertRaises(ValueError):
                self.encode(sequence=sequence)
        for kind in (True, 0x68e7d3db):
            with self.assertRaises(ValueError):
                favor.registration_metadata(kind)

    def test_optional_services_and_receiver_state_remain_mandatory(self):
        for name in ('normalizer_transform_present', 'per_thread_hook_present',
                     'writer_metadata_callback_present'):
            for value in (True, None, 0):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    self.encode(**{name: value})
        for name, value in (('subscriber_count', 1), ('subscriber_count', False),
                            ('pre_hook', 1), ('post_hook', 1), ('observer_registered', True),
                            ('state_pointer_nonnull', False), ('state_flags', 1)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.encode(empty_receiver_state={**favor.EMPTY_RECEIVER_STATE, name: value})

    def test_actual_composed_owner_fifo_preserves_scope_and_consumes_once(self):
        g = composition.ClimateCompositionTests().graph()
        before = (g.owner.host_notification_counter, g.owner.host_metadata_counter)
        self.assertEqual(g.owner.dispatch(favor.EVENT_KIND, self.fields(), 0), 0)
        self.assertEqual(g.owner.pending, [self.encode()])
        self.assertEqual((g.owner.host_notification_counter, g.owner.host_metadata_counter), before)
        self.assertIsNone(g.owner._foundation_borrow)
        self.assertEqual(g.event.deferred.drain(), 1)
        self.assertEqual(g.event.deferred.drain(), 0)
        self.assertEqual(g.owner.pending, [])
        self.assertEqual(g.event.deferred.consumed_count, 1)
        g.owner.close()

    def test_composed_live_source_guard_and_original_backend_owner(self):
        g = composition.ClimateCompositionTests().graph()
        self.assertEqual(favor.bind_owner(g.backend, g.backend.core, g.memory.read), favor.SOURCE[1])
        with self.assertRaisesRegex(ValueError, 'owner'):
            favor.bind_owner(g.backend, object(), g.memory.read)
        rva, raw = list(favor.core_fragments())[-1]
        address = g.backend.core._handle + rva + len(raw)-1
        old = g.memory.read(address, 1)
        g.memory.put(address, bytes([old[0]^1]))
        try:
            with self.assertRaisesRegex(ValueError, 'live producer'):
                favor.bind_owner(g.backend, g.backend.core, g.memory.read)
        finally:
            g.memory.put(address, old)
        self.assertEqual(favor.bind_owner(g.backend, g.backend.core, g.memory.read), favor.SOURCE[1])
        g.owner.close()


if __name__ == '__main__':
    unittest.main()

"""Offline source/codec tests; native queries and queue admission remain external."""
import json
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_turn_event_records as records
from civ6_host.runtime import xp2_turn_event_profile as family
from civ6_host.runtime.a0_family_source import _path, verify_pinned_files


def scalar(tag, value):
    return struct.pack('<IIQII', tag, 0, value & 0xffffffff, 0, 0)


class XP2TurnEventRecordsTests(unittest.TestCase):
    def fields(self, kind, *, position=(11, 17), identifier=23, selector=5):
        envelope = struct.pack('<IIQII', 13, 0, 0x12345000, 8, 0x21000001)
        raw = {records.SELECTOR_KEY: scalar(3, selector)}
        if kind == records.CLIMATE_KIND:
            raw[records.CLIMATE_DATA_KEY] = struct.pack('<IIQII', 5, 0, 0x54321000, 1, 0x21000005)
        else:
            raw[records.POSITION_KEY] = envelope
            descriptor_event = kind in (records.STORM_KIND, records.DROUGHT_KIND)
            raw[records.VALUE_KEY if descriptor_event else records.EVENT_KEY] = scalar(2, 31)
            if identifier is not None:
                # Actual constructor call315F/3167 (and3618/3620) is5FD7A0,
                # whose5FD7AB write is tag3. RandomStarted39A8 uses5FD780/tag2.
                raw[records.IDENTIFIER_KEY] = scalar(3 if descriptor_event else 2, identifier)
        reads = []

        def read(pointer, size):
            self.assertEqual((pointer, size), (0x12345000, 8))
            reads.append((pointer, size))
            return struct.pack('<ii', *position)

        decoded = records.decode_fields(kind, raw, read)
        self.assertEqual(len(reads), 0 if kind == records.CLIMATE_KIND else 1)
        return decoded, raw

    def encode(self, fields, sequence=1, **overrides):
        options = dict(position_index=97 if records.requires_position_query(fields) else None,
            empty_receiver_state=dict(records.EMPTY_RECEIVER_STATE),
            normalizer_transform_present=False, per_thread_hook_present=False,
            writer_metadata_callback_present=False,
            undefined_payload_policy=None if fields.kind == records.CLIMATE_KIND
                else records.UNDEFINED_PAYLOAD_POLICY)
        options.update(overrides)
        return records.encode_records(fields.kind, sequence, fields, **options)

    def test_random_occurrence_uses_the_terrain_emitter_scalar(self):
        witness = records.terrain_occurred_source()['refusal']['fields']
        fields = {int(key, 16): bytes.fromhex(raw) for key, raw in witness.items()}
        fields[records.TERRAIN_OCCURRED_VALUE_KEY] = struct.pack('<H6xI12x', 2, 5)
        kind = records.OCCURRED_KIND
        decoded = records.decode_fields(kind, fields, lambda ptr, size: struct.pack('<ii', 39, 11))
        encoded = records.encode_records(kind, 4, decoded, position_index=10,
            empty_receiver_state=dict(records.EMPTY_RECEIVER_STATE),
            normalizer_transform_present=False, per_thread_hook_present=False,
            writer_metadata_callback_present=False,
            undefined_payload_policy=records.UNDEFINED_PAYLOAD_POLICY)
        self.assertEqual([struct.unpack_from('<Iii', row, 96) for row in encoded],
                         [(5, 39, 11), (5, 39, 11)])

    def test_short_terrain_callback_keeps_exe_default_for_absent_lookup(self):
        witness = records.terrain_short_source()['witness']['fields']
        fields = {int(key, 16): bytes.fromhex(value) for key, value in witness.items()}
        row = records.encode_terrain(fields, 3, lambda ptr, size: struct.pack('<ii', 39, 11))
        self.assertEqual(struct.unpack_from('<IiiIIII', row, 80),
                         (3, 39, 11, 0x1c8fa8d7, 0, 2, 0))
        del fields[0xf36f4928]
        with self.assertRaisesRegex(ValueError, 'emitter fields'):
            records.encode_terrain(fields, 3, None)

    def test_terrain_callback_copies_coordinates_and_only_consumed_fields(self):
        witness = records.terrain_source()['native_fields']['fields']
        fields = {int(key, 16): bytes.fromhex(raw) for key, raw in witness.items()}
        address = struct.unpack_from('<Q', fields[records.POSITION_KEY], 8)[0]
        reads = []

        def read(pointer, count):
            reads.append((pointer, count))
            return struct.pack('<ii', 39, 11)

        row = records.encode_terrain(fields, 3, read)
        self.assertEqual(reads, [(address, 8)])
        self.assertEqual(struct.unpack_from('<4I', row), (112, 0x97, 3, 0))
        self.assertEqual(struct.unpack_from('<IiiIIII', row, 80),
                         (3, 39, 11, 0x1c8fa8d7, 1, 2, 0))
        with self.assertRaisesRegex(ValueError, 'envelope'):
            records.encode_terrain({**fields, records.POSITION_KEY: bytes(24)}, 3, read)
        self.assertEqual(len(reads), 1)

    def test_all_receiver_rows_are_pinned_and_share_the_exact_empty_dispatcher(self):
        p = records.receiver_source()
        self.assertEqual(set(records.receiver_rows()), {0x135, 0x136, 0x137, 0x138, 0x13b, 0x145})
        self.assertIsNone(records.receiver_row(0x999))
        for kind, row in records.receiver_rows().items():
            self.assertEqual(row['record_sizes'], {128 if kind == 0x138 else 96 if kind == 0x145 else 112})
            self.assertEqual(row['source_sha256'], records.RECEIVER_SOURCE[1])
        self.assertEqual(p['effects']['empty_path_payload_reads'], 0)
        self.assertFalse(p['effects']['record_deallocator_in_empty_path'])
        self.assertEqual(p['effects']['payload_offset'], 80)
        pins = records.source_dependencies()
        verify_pinned_files(pins)
        self.assertIn(records.RECEIVER_SOURCE[1], pins.values())
        self.assertIn(family.SOURCE[1], pins.values())
        self.assertIn(records.TYPED_EMITTER_SOURCE[1], pins.values())
        self.assertEqual(records.receiver_row(0x13b)['event_name'], 'GameCoreEvent::DroughtAddedToMap')

    def test_nine_actual_callers_select_tags_and_correct_the_second_event_kind(self):
        producer = family.source()
        actual = records._rva_rows(producer['functions']['xp2_1c2aa0'])
        self.assertEqual(actual[0x1c315f]['text'], 'mov edx, 0x57c6ed')
        self.assertEqual(actual[0x1c3167]['text'], 'call 0x1805fd7a0')
        self.assertEqual(records._rva_rows(producer['functions']['xp2_5fd7a0'])[0x5fd7ab]['text'],
                         'mov dword ptr [rcx + 8], 3')
        self.assertEqual(actual[0x1c359c]['text'], 'mov qword ptr [rbp + 0x30], 0x7f2abd3')
        self.assertEqual(actual[0x1c3625]['text'], 'mov rcx, qword ptr [rbp + 0x30]')
        self.assertEqual(actual[0x1c39a8]['text'], 'call 0x1805fd780')
        self.assertEqual(records._rva_rows(producer['functions']['xp2_5fd780'])[0x5fd78b]['text'],
                         'mov dword ptr [rcx + 8], 2')
        typed = records.typed_emitter_source()
        expected = ((0x1c2d5f, records.CLIMATE_KIND, None),
                    (0x1c3179, records.STORM_KIND, 3),
                    (0x1c3206, records.OCCURRED_KIND, None),
                    (0x1c3632, records.DROUGHT_KIND, 3),
                    (0x1c36bf, records.OCCURRED_KIND, None),
                    (0x1c3963, 0xec289c5b, 2),
                    (0x1c39e7, records.STARTED_KIND, 2),
                    (0x1c3bd1, 0xd548fc58, 2),
                    (0x1c3c55, records.OCCURRED_KIND, 2))
        self.assertEqual(tuple((int(r['call_rva'], 16), int(r['kind'], 16),
            next((f['tag'] for f in r['fields'] if int(f['key'], 16) == records.IDENTIFIER_KEY), None))
            for r in typed['routes']), expected)
        climate = records.field_shapes(records.CLIMATE_KIND)[0]
        self.assertEqual(dict(climate), {records.SELECTOR_KEY: 3, records.CLIMATE_DATA_KEY: 5})
        for kind in (records.STORM_KIND, records.DROUGHT_KIND):
            self.assertEqual(dict(records.field_shapes(kind)[0]),
                {records.SELECTOR_KEY: 3, records.IDENTIFIER_KEY: 3,
                 records.VALUE_KEY: 2, records.POSITION_KEY: 13})

    def test_typed_mapping_mutations_fail_against_actual_calls_not_only_file_hash(self):
        typed = json.loads(_path(records.TYPED_EMITTER_SOURCE[0]).read_text())
        ref = typed['references']['parameter_primitives']
        primitives = records._source((ref['path'], ref['sha256']))
        for mutation in ('tag', 'constructor', 'kind', 'argument'):
            changed = json.loads(json.dumps(typed))
            storm_id = changed['routes'][1]['fields'][2]
            if mutation == 'tag':
                storm_id['tag'] = 2
            elif mutation == 'constructor':
                storm_id.update(constructor_rva='0x5fd780', tag=2)
            elif mutation == 'kind':
                changed['routes'][3]['kind'] = '0x13b135e4'
            else:
                storm_id['emitter_argument'] = 'r9'
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'Typed emitter'):
                records._verify_typed_routes(changed, family.source(), primitives)

    def test_source_authority_is_callback_instruction_and_order_not_kind_name(self):
        p = family.source()
        callbacks = {key: [i['text'] for f in p['functions'][key]['capture']['fragments']
                           for i in f['instructions']]
                     for key in ('exe_142d30', 'exe_14d550', 'exe_14d290')}
        self.assertIn('mov edx, 0xa1e5a149', callbacks['exe_142d30'])
        self.assertNotIn('call 0x1400f14c0', callbacks['exe_142d30'])
        for key, call in (('exe_14d550', 'call 0x140124ab0'),
                          ('exe_14d290', 'call 0x140124cc0')):
            text = callbacks[key]
            self.assertEqual(text.count('call qword ptr [r8 + 0x90]'), 1)
            self.assertLess(text.index('call qword ptr [r8 + 0x90]'), text.index(call))
            self.assertIn('mov eax, dword ptr [rdi + 4]', text)
            self.assertIn('mov edx, 0x892b274a', text)
        self.assertLess(callbacks['exe_14d290'].index('call 0x140124cc0'),
                        callbacks['exe_14d290'].index('call 0x140124ed0'))
        # The field copied at payload+C is genuinely unwritten in the callers.
        self.assertFalse(any(s.startswith('mov dword ptr [rbp - 0xd],')
                             for s in callbacks['exe_14d550']))
        self.assertFalse(any(s.startswith('mov dword ptr [rbp - 0x3d],')
                             for s in callbacks['exe_14d290']))

    def test_changed_receiver_bytes_are_refused_without_touching_private_capture(self):
        changed = json.loads(_path(records.RECEIVER_SOURCE[0]).read_text())
        body = changed['functions']['0xdc0d0']['capture']['fragments'][0]
        body['instructions'][-1]['bytes'] = '90'
        original = records._source

        def selected(ref):
            return changed if ref == records.RECEIVER_SOURCE else original(ref)

        records.receiver_source.cache_clear()
        try:
            with patch.object(records, '_source', selected):
                with self.assertRaisesRegex(ValueError, 'instruction bytes'):
                    records.receiver_source()
        finally:
            records.receiver_source.cache_clear()

    def test_climate_reuses_scalar_writer_and_preserves_ignored_original_variant(self):
        fields, raw = self.fields(records.CLIMATE_KIND, selector=0xfedcba98)
        record, = self.encode(fields, 7)
        self.assertEqual(struct.unpack_from('<4I', record), (96, 0x145, 7, 0))
        self.assertEqual(struct.unpack_from('<2I', record, 80), (7, 0xfedcba98))
        self.assertEqual(record[88:], bytes(8))
        self.assertEqual(dict(fields.raw_fields), raw)
        self.assertEqual(records.registration_metadata(fields.kind)['undefined_record_ranges'], ())
        self.assertEqual(record, bytes(records.make_header(96, 0x145, 7, 0)[:80])
                         + struct.pack('<II', 7, 0xfedcba98) + bytes(8))

    def test_started_writes_exact_metadata_and_keeps_original_coordinates(self):
        fields, _ = self.fields(records.STARTED_KIND)
        record, = self.encode(fields, 9, position_index=0x87654321)
        self.assertEqual(struct.unpack_from('<6I', record),
                         (112, 0x135, 9, 0, 0x87654321, 0xffffffff))
        self.assertEqual(struct.unpack_from('<QI', record, 64), (0, 6))
        self.assertEqual(struct.unpack_from('<7I', record, 80), (9, 23, 5, 0, 0, 11, 17))
        for at in (24, 32, 40, 48, 56):
            self.assertEqual(struct.unpack_from('<HHI', record, at), (0xffff, 0, 0xffffffff))
        self.assertEqual(record[76:80] + record[108:], bytes(8))

    def test_occurred_two_records_keep_order_same_data_and_one_external_query(self):
        fields, _ = self.fields(records.OCCURRED_KIND, identifier=None, selector=0xffffffff)
        pair = self.encode(fields, 0xfffffffe)
        self.assertEqual([struct.unpack_from('<3I', r) for r in pair],
                         [(112, 0x136, 0xfffffffe), (112, 0x137, 0xffffffff)])
        self.assertEqual(pair[0][84:], pair[1][84:])
        self.assertEqual(struct.unpack_from('<2I', pair[0], 84), (0xffffffff, 0xffffffff))
        self.assertEqual(records.registration_metadata(fields.kind)['writer_rvas'],
                         (0x124cc0, 0x124ed0))
        # The existing queue accepts the two records with its unchanged sequence algorithm.
        from civ6_host.runtime.native.native_host_events import DeferredHostQueue
        queue = DeferredHostQueue()
        queue.pending, queue.limit, queue._sequence = [], 2, 0xfffffffd
        for record in pair:
            queue._enqueue(record)
        self.assertEqual(tuple(queue.pending), pair)
        self.assertEqual(queue._sequence, 0xffffffff)

    def test_position_query_is_required_only_for_exact_signed_native_branch(self):
        for position, required in (((-9998, -9998), True), ((-9999, 3), False),
                                   ((3, -10000), False), ((-0x80000000, 0), False)):
            with self.subTest(position=position):
                fields, _ = self.fields(records.STARTED_KIND, position=position)
                self.assertIs(records.requires_position_query(fields), required)
                if required:
                    with self.assertRaisesRegex(ValueError, 'native position query result'):
                        self.encode(fields, position_index=None)
                else:
                    result, = self.encode(fields)
                    self.assertEqual(struct.unpack_from('<I', result, 16)[0], 0xffffffff)
                    self.assertEqual(struct.unpack_from('<ii', result, 100), position)
                    with self.assertRaisesRegex(ValueError, 'uncalled branch'):
                        self.encode(fields, position_index=0)

    def test_no_unknown_meaningful_field_or_missing_required_identifier_is_admitted(self):
        _, raw = self.fields(records.STARTED_KIND)
        for altered in ({k: v for k, v in raw.items() if k != records.IDENTIFIER_KEY},
                        {**raw, 0x892b274a: scalar(2, 17)},
                        {**raw, 0x12345678: scalar(2, 0)}):
            with self.assertRaisesRegex(ValueError, 'field shape'):
                records.decode_fields(records.STARTED_KIND, altered, lambda *_: bytes(8))
        for kind in (0x13b135e4, 0xec289c5b, 0xd548fc58, True):
            with self.assertRaisesRegex(ValueError, 'codec kind'):
                records.registration_metadata(kind)

    def test_position_scalar_and_short_read_mutations_are_refused(self):
        _, raw = self.fields(records.STARTED_KIND)
        for key, value in ((records.SELECTOR_KEY, scalar(2, 0)),
                           (records.EVENT_KEY, scalar(3, 0)),
                           (records.IDENTIFIER_KEY, scalar(2, 0)[:23]),
                           (records.POSITION_KEY, struct.pack('<IIQII', 0, 0, 1, 8, 0x21000001)),
                           (records.POSITION_KEY, struct.pack('<IIQII', 13, 0, 1, 7, 0x21000001)),
                           (records.POSITION_KEY, struct.pack('<IIQII', 13, 0, 1, 8, 0x20000001))):
            with self.subTest(key=key, value=value.hex()), self.assertRaises(ValueError):
                records.decode_fields(records.STARTED_KIND, {**raw, key: value}, lambda *_: bytes(8))
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            records.decode_fields(records.STARTED_KIND, raw, lambda *_: bytes(7))

    def test_undefined_word_policy_cannot_admit_listeners_or_native_services(self):
        fields, _ = self.fields(records.STARTED_KIND)
        for option, value in (('undefined_payload_policy', None),
                              ('normalizer_transform_present', True),
                              ('per_thread_hook_present', True),
                              ('writer_metadata_callback_present', True)):
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.encode(fields, **{option: value})
        for key, value in (('observer_registered', True), ('subscriber_count', 1),
                           ('pre_hook', 1), ('post_hook', 1), ('state_flags', 2),
                           ('subscriber_count', False)):
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'empty receiver'):
                self.encode(fields, empty_receiver_state={**records.EMPTY_RECEIVER_STATE, key: value})

    def test_sequence_query_and_mismatched_kind_are_refused_before_returning_records(self):
        fields, _ = self.fields(records.OCCURRED_KIND)
        for sequence in (0, True, -1, 0xffffffff, 0x100000000):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                self.encode(fields, sequence)
        for value in (True, -1, 0x100000000, (97, 11, 17)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.encode(fields, position_index=value)
        with self.assertRaisesRegex(ValueError, 'another callback'):
            records.encode_records(records.STARTED_KIND, 1, fields,
                empty_receiver_state=dict(records.EMPTY_RECEIVER_STATE),
                normalizer_transform_present=False, per_thread_hook_present=False,
                writer_metadata_callback_present=False)

    def test_storm_decodes_original_inputs_but_no_storm_encoder_is_admitted(self):
        fields, raw = self.fields(records.STORM_KIND)
        self.assertIs(type(fields), records.StormFields)
        self.assertEqual((fields.selector, fields.value, fields.identifier, fields.position),
                         (5, 31, 23, (11, 17)))
        self.assertEqual(dict(fields.raw_fields), raw)
        with self.assertRaisesRegex(ValueError, 'identifier tag'):
            records.decode_fields(records.STORM_KIND,
                {**raw, records.IDENTIFIER_KEY: scalar(2, 23)}, lambda *_: bytes(8))
        with self.assertRaises(ValueError):
            records.requires_position_query(fields)
        with self.assertRaises(ValueError):
            records.decode_fields(records.STORM_KIND,
                {k: v for k, v in raw.items() if k != records.VALUE_KEY}, lambda *_: bytes(8))
        header = records.make_header(128, 0x138, 3, 4)
        self.assertEqual(struct.unpack_from('<4I', header), (128, 0x138, 3, 0))
        self.assertEqual(struct.unpack_from('<I', header, 72)[0], 4)
        self.assertEqual(header[80:], bytes(48))
        for arguments in ((128, 0x138, 3, 6), (112, 0x138, 3, 4), (128, 0x138, 0, 4)):
            with self.assertRaises(ValueError):
                records.make_header(*arguments)

    def test_drought_shares_typed_inputs_and_has_a_distinct_receiver_header(self):
        fields, raw = self.fields(records.DROUGHT_KIND)
        self.assertIs(type(fields), records.StormFields)
        self.assertEqual(fields.kind, 0x07f2abd3)
        self.assertEqual(struct.unpack_from('<H', raw[records.IDENTIFIER_KEY])[0], 3)
        header = records.make_header(112, 0x13b, 9, 4)
        self.assertEqual(struct.unpack_from('<4I', header), (112, 0x13b, 9, 0))
        self.assertEqual(struct.unpack_from('<I', header, 72)[0], 4)
        self.assertEqual(header[80:], bytes(32))

    def test_climate_text_keeps_native_null_and_owned_envelopes_without_reading(self):
        _, raw = self.fields(records.CLIMATE_KIND)
        for text in (scalar(5, 0), struct.pack('<IIQII', 5, 0, 0x12340000, 1, 0x21000009)):
            def no_read(*_):
                self.fail('Ignored climate string must not be dereferenced')
            fields = records.decode_fields(records.CLIMATE_KIND,
                {**raw, records.CLIMATE_DATA_KEY: text}, no_read)
            self.assertEqual(dict(fields.raw_fields)[records.CLIMATE_DATA_KEY], text)
        with self.assertRaisesRegex(ValueError, 'text tag'):
            records.decode_fields(records.CLIMATE_KIND,
                {**raw, records.CLIMATE_DATA_KEY: scalar(2, 0)}, lambda *_: bytes(8))


if __name__ == '__main__':
    unittest.main()

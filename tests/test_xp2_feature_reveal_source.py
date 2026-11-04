"""Source and borrowed-field checks for the XP2 feature-reveal A0 family."""
import struct
from types import SimpleNamespace as NS
import unittest

from civ6_host.runtime import xp2_feature_reveal_source as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


def scalar(tag, value):
    return struct.pack('<IIQII', tag, 0, value, 0, 0)


def arguments(kind, *, coordinate=(23, 41)):
    payload_address = 0x700000
    payload = struct.pack('<ii', *coordinate)
    fields = {
        source.SELECTOR_KEY: scalar(3, 0),
        source.POSITION_KEY: struct.pack('<IIQII', 0, 0, payload_address, 8, 0x21000001),
        source.VALUE_KEY: scalar(2, 5),
    }
    reads = []

    def read(address, count):
        reads.append((address, count))
        if address == payload_address and count == 8:
            return payload
        raise ValueError('read outside borrowed fixture')

    return fields, read, reads


class FeatureRevealSourceTests(unittest.TestCase):
    def test_exact_three_receiver_routes_and_closed_parent_sources(self):
        profile = source.source()
        self.assertEqual(source.KINDS, {0xEE846031, 0x7D35CA0C, 0x8BED8EC4})
        self.assertEqual(source.CALLBACKS, {
            0xEE846031: 0x1470B0, 0x7D35CA0C: 0x159660, 0x8BED8EC4: 0x147490})
        self.assertEqual({profile['typed_input_contract']['kind_values'][i]
                          for i in range(3)}, {hex(kind) for kind in source.KINDS})
        self.assertTrue(all(source.EVENT_NAMES[kind].endswith('Revealed') for kind in source.KINDS))
        self.assertEqual(source.POLICY, 'source-qualified-empty-presentation-zero-records')
        pins = source.source_dependencies()
        self.assertIn(source.SOURCE[1], pins.values())
        self.assertIn(source.PRODUCER_SOURCE[1], pins.values())
        self.assertIn(source.RECEIVER_SOURCE[1], pins.values())
        self.assertIn(source.HISTORICAL_SOURCE[1], pins.values())

    def test_stored_header_is_derived_from_official_allocator_and_emitter_bytes(self):
        # Independent correspondence to the official constructor, rather than
        # checking a decoder fixture against another proposed header literal.
        profile = source.source()
        producer = source._source(source.PRODUCER_SOURCE)
        emitter = {int(row['rva'], 16): bytes.fromhex(row['bytes']) for row in
                   source._rows(producer['functions']['xp2_core']['host_a0_emitter'])}
        count = struct.unpack('<I', emitter[0x5FAB88][-4:])[0]
        size = struct.unpack('<I', emitter[0x5FAB98][-4:])[0]
        input_flags = struct.unpack('<I', emitter[0x5FAB7D][-4:])[0]
        allocator = {int(row['rva'], 16): bytes.fromhex(row['bytes']) for row in
                     source._rows(profile['functions']['xp2_pair_allocator'])}
        # OR EBX, imm32 receives the original R8D element count. RDI is the
        # header payload address, so its +0xC store is variant+0x14.
        self.assertEqual(allocator[0x9A1640], bytes.fromhex('418bd8'))
        self.assertEqual(allocator[0x9A1662][:2], bytes.fromhex('81cb'))
        self.assertEqual(allocator[0x9A166B], bytes.fromhex('895f0c'))
        mask = struct.unpack('<I', allocator[0x9A1662][2:])[0]
        self.assertEqual((input_flags, size, count), (0x01000000, 8, 1))
        self.assertEqual(mask | count, 0x21000001)
        self.assertNotEqual(mask | count, input_flags)
        self.assertEqual(source._text(profile['functions']['xp2_pair_variant_constructor'])[0x99DC54],
                         'call qword ptr [rax + 0x10]')
        self.assertEqual(source._text(profile['functions']['xp2_event_argument_pair_setter'])[0x9A0AD7],
                         'call 0x1809a12f0')
        self.assertEqual(source._text(profile['functions']['xp2_variant_move'])[0x9A12FA],
                         'movups xmmword ptr [rcx + 8], xmm0')

    def test_bound_prepared_xp2_owner_checks_every_captured_core_fragment_and_slot(self):
        base = 0x30000000
        memory = {}
        for rva, raw in source._core_fragments():
            memory.update({base + rva + i: value for i, value in enumerate(raw)})
        for table, offset, target in source._OWNERSHIP_SLOTS.values():
            memory.update({base + table + offset + i: value
                           for i, value in enumerate(struct.pack('<Q', base + target))})
        memory.update({base + 0xB90770 + i: value
                       for i, value in enumerate(struct.pack('<Q', base + 0xABEFF8))})
        reads = []

        def read(address, count):
            reads.append((address, count))
            return bytes(memory[address + i] for i in range(count))

        core = NS(_handle=base)
        backend = NS(core=core, load_abi=NS(core_sha256=XP2_CORE_SHA256), stage='prepared',
                     poisoned=False, destroyed=False, check_thread=lambda: None)
        self.assertEqual(source.bind_owner(backend, core, read), source.SOURCE[1])
        self.assertTrue(reads)
        self.assertLessEqual(max(count for _, count in reads), 4096)
        self.assertEqual(getattr(backend, '_xp2_feature_reveal_source_identity'),
                         (id(core), base, XP2_CORE_SHA256, source.SOURCE[1]))

        for rva in (0x9A0890, 0x99DC00, 0x9A1620, 0x9A12F0, 0x9A1560, 0x90DE):
            with self.subTest(changed_body=hex(rva)):
                memory[base + rva] ^= 1
                with self.assertRaisesRegex(ValueError, 'live Core source'):
                    source.bind_owner(backend, core, read)
                memory[base + rva] ^= 1
        for table, offset, _ in source._OWNERSHIP_SLOTS.values():
            address = base + table + offset
            memory[address] ^= 1
            with self.assertRaisesRegex(ValueError, 'virtual slot'):
                source.bind_owner(backend, core, read)
            memory[address] ^= 1
        memory[base + 0xB90770] ^= 1
        with self.assertRaisesRegex(ValueError, 'allocator live identity'):
            source.bind_owner(backend, core, read)
        memory[base + 0xB90770] ^= 1
        backend.load_abi.core_sha256 = XP1_CORE_SHA256
        with self.assertRaisesRegex(ValueError, 'exact prepared XP2'):
            source.bind_owner(backend, core, read)

    def test_decoder_copies_borrowed_coordinate_bytes_and_retains_no_pointer(self):
        for kind in source.KINDS:
            fields, read, reads = arguments(kind, coordinate=(-3, 17))
            decoded = source.decode_fields(kind, fields, read)
            self.assertEqual(decoded.position, (-3, 17))
            self.assertEqual(decoded.selector, 0)
            self.assertEqual(decoded.value, 5)
            self.assertEqual(reads, [(0x700000, 8)])
            admin = decoded.to_admin()
            self.assertEqual(admin['coordinate'], [-3, 17])
            self.assertEqual(admin['event_name'], source.EVENT_NAMES[kind])
            self.assertTrue(admin['borrowed_position_payload_copied'])
            self.assertFalse(admin['borrowed_pointer_retained'])
            fields.clear()
            self.assertEqual(decoded.to_admin(), admin)

    def test_copied_value_survives_event_map_payload_mutation_and_release(self):
        payload = bytearray(struct.pack('<ii', -7, 28))
        fields, _, _ = arguments(source.FLOODPLAIN_REVEALED)
        reads = []

        def read(pointer, count):
            reads.append((pointer, count))
            return bytes(payload)

        decoded = source.decode_fields(source.FLOODPLAIN_REVEALED, fields, read)
        payload[:] = struct.pack('<ii', 81, -12)
        fields.clear()
        payload.clear()  # The source map may now destroy its owned allocation.
        self.assertEqual(decoded.position, (-7, 28))
        self.assertEqual(decoded.to_admin()['coordinate'], [-7, 28])
        self.assertEqual(reads, [(0x700000, 8)])
        self.assertEqual(set(vars(decoded)), {'kind', 'selector', 'position', 'value'})

    def test_unknown_keys_bad_tags_flags_and_short_borrowed_payload_refuse(self):
        for kind in source.KINDS:
            fields, read, _ = arguments(kind)
            bad = dict(fields)
            bad[source.SELECTOR_KEY] = scalar(2, 0)
            with self.assertRaisesRegex(ValueError, 'selector scalar'):
                source.decode_fields(kind, bad, read)
            bad = dict(fields)
            bad[source.SELECTOR_KEY] = scalar(3, 1)
            with self.assertRaisesRegex(ValueError, 'selector differs'):
                source.decode_fields(kind, bad, read)
            bad = dict(fields)
            bad[source.VALUE_KEY] = scalar(3, 5)
            with self.assertRaisesRegex(ValueError, 'value scalar'):
                source.decode_fields(kind, bad, read)
            for flags in (0x01000000, 0x01000001, 0x20000001, 0x21000000, 0x21000002):
                bad = dict(fields)
                bad[source.POSITION_KEY] = struct.pack('<IIQII', 0, 0, 0x700000, 8, flags)
                with self.assertRaisesRegex(ValueError, f'coordinate variant.*flags={flags:#010x}'):
                    source.decode_fields(kind, bad, read)
            bad = dict(fields)
            bad[0x12345678] = bad.pop(source.VALUE_KEY)
            with self.assertRaisesRegex(ValueError, 'keys differ'):
                source.decode_fields(kind, bad, read)
            with self.assertRaisesRegex(ValueError, 'copy is incomplete'):
                source.decode_fields(kind, fields, lambda *_: b'1234567')

    def test_header_refusal_reports_safe_shape_without_pointer_or_payload_read(self):
        fields, read, reads = arguments(source.FLOODPLAIN_REVEALED)
        fields[source.POSITION_KEY] = struct.pack('<IIQII', 1024, 0, 0xAABBCCDDEEFF, 16, 0x21000001)
        with self.assertRaises(ValueError) as raised:
            source.decode_fields(source.FLOODPLAIN_REVEALED, fields, read)
        self.assertEqual(str(raised.exception), 'Feature-reveal borrowed coordinate variant differs: '
                         'tag=1024, element_size=16, flags=0x21000001')
        self.assertEqual(reads, [])

    def test_empty_validation_rejects_non_owner_without_any_fallback(self):
        with self.assertRaisesRegex(ValueError, 'actual A0 owner'):
            source.validate_empty_owner(NS())


if __name__ == '__main__':
    unittest.main()

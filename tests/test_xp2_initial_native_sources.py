"""Independent current-PE and bounded native-reader seam tests for initial diplomacy."""
from dataclasses import replace
import hashlib
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pefile

from civ6_host.runtime import diplomacy_overview
from civ6_host.runtime import xp2_initial_query_source as queries
from civ6_host.runtime import xp2_initial_statement_factory as factories
from civ6_host.runtime import xp2_diplomacy_overview_source as overview_source
from civ6_host.runtime.execution_images import known_path, select


PROFILE_ID = 'xp2-gamecore-current-092abfbb'
IMAGE = select(PROFILE_ID, core_path=known_path(PROFILE_ID))
BASE = 0x180000000
CONFIG = 0x300000000
VARIANT = 0x300001000
BUCKETS = 0x300010000
SENTINEL = 0x300020000
NODE = 0x300030000
OTHER = 0x300031000
BUCKET_COUNT = 67


class MappedMemory:
    """Independent mapped PE bytes plus explicit synthetic native objects."""
    def __init__(self, image):
        self.image = bytearray(image)
        self.blocks = {}
        self.reads = []

    def read(self, pointer, size):
        self.reads.append((pointer, size))
        if pointer in self.blocks:
            value = self.blocks[pointer]
            return value[:size]
        offset = pointer - BASE
        if 0 <= offset <= len(self.image) - size:
            return bytes(self.image[offset:offset+size])
        raise ValueError(f'Unmapped fixture read: {pointer:#x}+{size}')


class XP2InitialNativeSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = known_path(PROFILE_ID).read_bytes()
        if hashlib.sha256(raw).hexdigest() != IMAGE.image_sha256:
            raise ValueError('Installed XP2 PE changed after profile selection')
        pe = pefile.PE(data=raw)
        cls.image = pe.get_memory_mapped_image()
        pe.close()

    def mapped(self):
        return MappedMemory(self.image)

    @staticmethod
    def binding_rows(proof):
        return proof['public_major_api_registrations']['registrations']

    def test_selected_player_namespace_registrations_match_actual_xp2_pe(self):
        proof = queries.source(execution_image=IMAGE)
        actual = {(row['name'], row['registrar_rva'], row['callback_rva'])
                  for row in self.binding_rows(proof)}
        expected = {
            ('GetID', '0x6a8c90', '0x6a9be0'),
            ('IsMajor', '0x6a8c90', '0x6aa640'),
            ('HasMet', '0x6ae510', '0x6b01b0'),
            ('GetAliveMajors', '0x6b1d20', '0x6b25b0'),
        }
        self.assertTrue(expected <= actual)
        self.assertEqual(IMAGE.id, PROFILE_ID)
        self.assertEqual(proof['images']['actual_xp2']['sha256'], IMAGE.image_sha256)
        # The duplicate bindings remain distinct; the selected methods have sibling namespace evidence.
        self.assertGreater(sum(row['name'] == 'GetID' for row in self.binding_rows(proof)), 1)
        self.assertGreater(sum(row['name'] == 'HasMet' for row in self.binding_rows(proof)), 1)
        player_get_id = next(row for row in self.binding_rows(proof)
                             if (row['name'], row['registrar_rva'], row['callback_rva'])
                             == ('GetID', '0x6a8c90', '0x6a9be0'))
        self.assertIn('IsMajor', player_get_id['namespace_evidence_sibling_methods'])
        self.assertIn('GetDiplomacy', player_get_id['namespace_evidence_sibling_methods'])
        diplomacy_has_met = next(row for row in self.binding_rows(proof)
                                  if (row['name'], row['registrar_rva']) == ('HasMet', '0x6ae510'))
        self.assertIn('GetMetTurn', diplomacy_has_met['namespace_evidence_sibling_methods'])
        manager_majors = next(row for row in self.binding_rows(proof)
                              if (row['name'], row['registrar_rva']) == ('GetAliveMajors', '0x6b1d20'))
        self.assertIn('GetAliveMinors', manager_majors['namespace_evidence_sibling_methods'])

    def test_verify_live_matches_actual_image_and_rejects_changed_code_name_and_getter_slot(self):
        memory = self.mapped()
        proof = queries.verify_live(BASE, memory.read, execution_image=IMAGE)
        self.assertEqual(proof['images']['actual_xp2']['sha256'], IMAGE.image_sha256)

        selected = proof['public_major_api_registrations']['registrations']
        cases = []
        callback = proof['public_major_api_registrations']['callback_bodies']['0x6aa640']
        callback_fragment = callback['fragments'][0]
        cases.append(('callback', int(callback_fragment['start_rva'], 16)))
        registrar = proof['public_major_api_registrations']['registrar_bodies']['0x6a8c90']
        registrar_fragment = registrar['fragments'][0]
        cases.append(('registrar', int(registrar_fragment['start_rva'], 16)))
        getter = proof['pause']['current_xp2_provider_getter']['actual_body']
        getter_fragment = getter['fragments'][0]
        cases.append(('getter', int(getter_fragment['start_rva'], 16)))
        for label, rva in cases:
            with self.subTest(kind=label):
                damaged = self.mapped()
                damaged.image[rva] ^= 1
                with self.assertRaisesRegex(ValueError, 'binding changed'):
                    queries.verify_live(BASE, damaged.read, execution_image=IMAGE)

        name_row = next(row for row in selected if row['name'] == 'IsMajor'
                        and row['registrar_rva'] == '0x6a8c90')
        damaged_name = self.mapped()
        name_va = BASE + int(name_row['name_rva'], 16)
        damaged_name.blocks[name_va] = b'IsMinor\0'
        with self.assertRaisesRegex(ValueError, 'registered method name changed'):
            queries.verify_live(BASE, damaged_name.read, execution_image=IMAGE)

        damaged_vtable = self.mapped()
        damaged_vtable.blocks[BASE + 0xabf080 + 0x68] = struct.pack('<Q', BASE + 0x99f680 + 8)
        with self.assertRaisesRegex(ValueError, 'virtual target changed'):
            queries.verify_live(BASE, damaged_vtable.read, execution_image=IMAGE)

    def test_foreign_execution_profile_is_refused(self):
        foreign = replace(IMAGE, id='foreign-xp2-profile')
        with self.assertRaisesRegex(ValueError, 'registered immutable identity'):
            queries.source(execution_image=foreign)

    def registry(self, request_name, *, node_key=None, factory_rva=None, cycle=False):
        proof = factories.source(execution_image=IMAGE)
        memory = self.mapped()
        memory.blocks[BASE + 0xb635c0] = struct.pack('<Q', BUCKETS)
        memory.blocks[BASE + 0xb635c8] = struct.pack('<I', BUCKET_COUNT)
        memory.blocks[BUCKETS + BUCKET_COUNT * 8] = struct.pack('<Q', SENTINEL)
        target = proof['requests'][request_name]
        key = int(target['statement_hash'], 16)
        if node_key is None:
            node_key = key if target['expected_registration'] else 123
        bucket = BUCKETS + (key % BUCKET_COUNT) * 8
        memory.blocks[bucket] = struct.pack('<Q', NODE)
        memory.blocks[NODE] = struct.pack('<I', node_key)
        if factory_rva is None:
            factory_rva = target.get('factory_rva', '0x189d10')
        memory.blocks[NODE + 8] = struct.pack('<Q', BASE + int(factory_rva, 16))
        memory.blocks[NODE + 16] = struct.pack('<Q', NODE if cycle else SENTINEL)
        return memory, proof

    def test_every_request_name_uses_its_exact_registered_factory_or_expected_absence(self):
        proof = factories.source(execution_image=IMAGE)
        mappings = overview_source.REQUEST_STATEMENT_TYPES
        self.assertEqual(set(proof['requests']), set(mappings.values()))
        self.assertEqual(len(mappings), 20)
        registered = [name for name, row in proof['requests'].items()
                      if row['expected_registration']]
        self.assertEqual(len(registered), 19)
        self.assertEqual([name for name, row in proof['requests'].items()
                          if not row['expected_registration']], ['DECLARE_GOLDEN_WAR'])
        self.assertEqual(mappings['CHOICE_DECLARE_GOLDEN_AGE_WAR'], 'DECLARE_GOLDEN_WAR')
        self.assertNotIn('DECLARE_GOLDEN_AGE_WAR', proof['requests'])

        for name in mappings.values():
            with self.subTest(name=name):
                memory, selected = self.registry(name)
                result = factories.verify_request(BASE, memory.read, name,
                                                  execution_image=IMAGE)
                target = selected['requests'][name]
                self.assertFalse(result['native_memory_modified'])
                self.assertFalse(result['native_request_invoked'])
                self.assertEqual(result['observed_registration'], target['expected_registration'])
                if target['expected_registration']:
                    self.assertEqual(result['factory_rva'], target['factory_rva'])
                else:
                    self.assertNotIn('factory_rva', result)

    def test_factory_code_virtual_target_wrong_mapping_and_missing_key_are_refused(self):
        for tamper, pattern in (
            ('factory_code', 'native code changed'),
            ('factory_vtable', 'virtual targets changed'),
        ):
            with self.subTest(tamper=tamper):
                memory, proof = self.registry('DECLARE_FORMAL_WAR')
                row = proof['requests']['DECLARE_FORMAL_WAR']
                offset = int(row['factory_rva'], 16) if tamper == 'factory_code' else int(row['vtable_rva'], 16) + 0x10
                memory.image[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    factories.verify_request(BASE, memory.read, 'DECLARE_FORMAL_WAR',
                                             execution_image=IMAGE)

        memory, proof = self.registry('DECLARE_FORMAL_WAR', node_key=123)
        memory.blocks[NODE + 16] = struct.pack('<Q', SENTINEL)
        with self.assertRaisesRegex(ValueError, 'factory is missing'):
            factories.verify_request(BASE, memory.read, 'DECLARE_FORMAL_WAR',
                                     execution_image=IMAGE)

    def test_registry_cycle_unexpected_golden_registration_and_unknown_deal_are_refused(self):
        memory, _ = self.registry('DECLARE_FORMAL_WAR', node_key=123, cycle=True)
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            factories.verify_request(BASE, memory.read, 'DECLARE_FORMAL_WAR',
                                     execution_image=IMAGE)

        golden_proof = factories.source(execution_image=IMAGE)
        golden_key = int(golden_proof['requests']['DECLARE_GOLDEN_WAR']['statement_hash'], 16)
        memory, _ = self.registry('DECLARE_GOLDEN_WAR', node_key=golden_key)
        with self.assertRaisesRegex(ValueError, 'unexpected registered native factory'):
            factories.verify_request(BASE, memory.read, 'DECLARE_GOLDEN_WAR',
                                     execution_image=IMAGE)

        memory, _ = self.registry('DECLARE_FORMAL_WAR')
        memory.reads.clear()
        with self.assertRaisesRegex(ValueError, 'Unqualified initial statement request name'):
            factories.verify_request(BASE, memory.read, 'MAKE_DEAL', execution_image=IMAGE)
        self.assertEqual(memory.reads, [])

    @staticmethod
    def variant(tag, payload=0, flags=0):
        raw = bytearray(24)
        struct.pack_into('<H', raw, 0, tag)
        struct.pack_into('<Q', raw, 8, payload)
        struct.pack_into('<I', raw, 20, flags)
        return bytes(raw)

    def pause_backend(self, variant, *, call_result=VARIANT, change_snapshot=False,
                      short_variant=False, bad_provider=False):
        memory = self.mapped()
        query_proof = queries.source(execution_image=IMAGE)
        getter = query_proof['pause']['current_xp2_provider_getter']
        vtable_rva = int(getter['vtable_rva_from_retained_xp2_profile'], 16)
        memory.blocks[CONFIG] = struct.pack('<Q', BASE + (vtable_rva + 8 if bad_provider else vtable_rva))
        value = variant[:-1] if short_variant else variant
        memory.blocks[VARIANT] = value

        calls = []

        def call(target, result_type, arg_types, receiver, *args):
            calls.append((target, result_type, arg_types, receiver, args))
            return call_result

        class App:
            def __init__(self):
                self.snapshot_count = 0

            def require_context(self, base, context):
                if (base, context) != (BASE, 'ctx'):
                    raise ValueError('Wrong application context')

            def snapshot(self):
                self.snapshot_count += 1
                extra = self.snapshot_count if change_snapshot else 0
                return {'normalized': CONFIG, 'revision': extra}

        app = App()
        events = []
        core = SimpleNamespace(_handle=BASE, _civ6_host_execution_image=IMAGE)
        backend = SimpleNamespace(
            core=core, owner=app, context='ctx',
            runtime=SimpleNamespace(read=memory.read, call=call),
            check_thread=lambda: None,
            emit=lambda *args, **kwargs: events.append((args, kwargs)))
        return backend, memory, calls, events

    def test_pause_reader_uses_xp2_value_getter_and_exact_typed_conversion(self):
        cases = (
            (self.variant(1, 1), True),
            (self.variant(5, 1), True),
            (self.variant(2, 1), True),
            (self.variant(3, 0), False),
            (self.variant(20, 1), True),
            (self.variant(21, 0), False),
            (self.variant(1, 1, 1 << 29), False),
            (self.variant(65535, 1), False),
        )
        for raw, expected in cases:
            with self.subTest(tag=struct.unpack_from('<H', raw)[0], expected=expected):
                backend, memory, calls, events = self.pause_backend(raw)
                with patch.object(diplomacy_overview, 'read_pause', side_effect=AssertionError('Base pause reader called')) as base_reader:
                    self.assertIs(queries.read_pause(backend), expected)
                base_reader.assert_not_called()
                self.assertEqual(len(calls), 1)
                target, result_type, arg_types, receiver, args = calls[0]
                self.assertEqual(target, BASE + 0x99f680)
                self.assertEqual(receiver, CONFIG)
                self.assertEqual(args, (2261104600,))
                self.assertIn((CONFIG, 8), memory.reads)
                self.assertEqual(events[-1][0][0], 'xp2_initial_diplomacy_pause_read')

    def test_pause_reader_preserves_missing_short_variant_and_provider_change_errors(self):
        backend, _, _, _ = self.pause_backend(self.variant(1, 1), call_result=0)
        with self.assertRaisesRegex(RuntimeError, 'getter returned null'):
            queries.read_pause(backend)

        backend, _, _, _ = self.pause_backend(self.variant(1, 1), short_variant=True)
        with self.assertRaisesRegex(ValueError, 'Incomplete world-configuration memory copy'):
            queries.read_pause(backend)

        backend, _, _, _ = self.pause_backend(self.variant(1, 1), change_snapshot=True)
        with self.assertRaisesRegex(RuntimeError, 'provider changed during XP2 pause read'):
            queries.read_pause(backend)

        backend, _, _, _ = self.pause_backend(self.variant(1, 1), bad_provider=True)
        with self.assertRaisesRegex(ValueError, 'provider differs'):
            queries.read_pause(backend)

    def test_pause_converter_rejects_non_bytes_and_wrong_variant_size(self):
        for raw in (None, bytearray(24), b'\0' * 23, b'\0' * 25):
            with self.subTest(raw=type(raw).__name__, size=len(raw) if raw is not None else None):
                with self.assertRaisesRegex(ValueError, 'exact native variant'):
                    diplomacy_overview.paused_from_variant(raw)


if __name__ == '__main__':
    unittest.main()

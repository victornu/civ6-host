"""XP2 history/era A0 composition over the existing saved continuation/FIFO."""
import struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import a0_foundation_events as foundation
from civ6_host.runtime import a0_game_history_events as events
from civ6_host.runtime import foundation_event_profile as project
from civ6_host.runtime import xp2_history_event_profile as source
from civ6_host.runtime import xp2_wonder_completion
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_xp1_turn_a0 import scalar
from test_xp2_turn_notifications import XP2ComposedNotifications


def _install_history_with_turn_units(owner, backend, original):
    """Populate the test memory from the retained source, then use real enables."""
    p = source.source()
    memory = owner.read.__self__
    for body in source._bodies(p):
        for fragment in body['fragments']:
            memory.put(memory.core_base + int(fragment['start_rva'], 16),
                       bytes.fromhex(fragment['raw_hex']))
    producer = source.turn21_source()[0]['producer']
    memory.put(memory.core_base + int(producer['start_rva'], 16), bytes.fromhex(producer['raw_hex']))
    for rva, raw in source.turn21_scalar_core_fragments():
        memory.put(memory.core_base + rva, raw)
    for rva, raw in source.descriptor_core_fragments():
        memory.put(memory.core_base + rva, raw)
    for rva, raw in source.age_core_fragments():
        memory.put(memory.core_base + rva, raw)
    for rva, raw in source.property_core_fragments():
        memory.put(memory.core_base + rva, raw)
    for body in xp2_wonder_completion.source()[1]['functions'].values():
        for fragment in body['fragments']:
            memory.put(memory.core_base + int(fragment['start_rva'], 16),
                       bytes.fromhex(fragment['raw_hex']))
    # This saved-owner fixture predates the XP2 reader identity field; bind it
    # to the exact ABI already carried by the real backend.
    owner.arguments.reader.core_sha256 = backend.load_abi.core_sha256
    original(owner, backend)
    with patch('civ6_host.runtime.foundation_facade_profiles.verify_xp1_once'), patch(
            'civ6_host.runtime.xp2_wmd_fallout_visibility.verify_live'):
        foundation.enable(owner, backend)
    foundation.enable_history_events(owner, backend)


class XP2GameHistoryTests(unittest.TestCase):
    def graph(self):
        original = foundation.enable_turn_units

        def enable_both(owner, backend):
            return _install_history_with_turn_units(owner, backend, original)

        with patch.object(foundation, 'enable_turn_units', enable_both):
            graph = XP2ComposedNotifications().graph()
        self.addCleanup(graph.owner.close)
        return graph

    @staticmethod
    def fields(value_a=17, value_b=29):
        return {
            0xA1E5A149: scalar(3, 0),
            0xD6FCF3E4: scalar(2, value_a),
            0xA1FBC372: scalar(2, value_b),
        }

    def test_score_short_shape_uses_pinned_common_normalizer_zero(self):
        short = {0xA1E5A149: scalar(3, 0), 0xD6FCF3E4: scalar(2, 41)}
        self.assertEqual(source.decode_score_fields(short), (0, 41, 0))
        self.assertEqual(source.decode_score_fields(self.fields(41, 0)), (0, 41, 0))
        with self.assertRaisesRegex(ValueError, 'retained emitter shape'):
            source.decode_score_fields({**short, 0x12345678: scalar(2, 0)})
        with self.assertRaisesRegex(ValueError, 'selector-zero'):
            source.decode_score_fields({0xA1E5A149: scalar(3, 1), 0xD6FCF3E4: scalar(2, 41)})
        invalid = self.fields(41, 0)
        invalid[0xA1FBC372] = scalar(3, 0)
        with self.assertRaisesRegex(ValueError, 'value B'):
            source.decode_score_fields(invalid)

    def test_default_xp1_encoder_stays_on_its_existing_three_key_branch(self):
        record = events.encode(
            source.HISTORY_KIND, self.fields(11, 13), 1,
            normalizer_transform_present=False,
            optional_callback_present=False,
            queue_metadata_service=None)
        self.assertEqual(struct.unpack_from('<4I', record), (96, 0x105, 1, 0))
        self.assertEqual(struct.unpack_from('<3I', record, 80), (1, 11, 13))

    def test_prepared_xp2_owner_dispatches_turn21_events_through_shared_fifo(self):
        graph = self.graph()
        owner = graph.owner
        self.assertEqual(graph.backend.load_abi.core_sha256, XP2_CORE_SHA256)
        self.assertIs(owner.history_event_profile, owner._history_event_profile)
        self.assertEqual(set(owner.history_event_profile.record_types_by_kind),
                         {source.HISTORY_KIND, source.ERA_KIND, source.ERA_SCORE_KIND,
                          source.TURN21_KIND, source.PROPERTY_KIND, 0x8C6B2399,
                          *source.DESCRIPTOR_EVENTS, *source.AGE_EVENTS})
        self.assertEqual(owner.foundation_event_profile.record_types_by_kind[project.PROJECT_KIND],
                         frozenset((96, 99, 100)))
        self.assertIsNone(owner.placement_event_profile)
        emissions = (
            (source.HISTORY_KIND, self.fields(3, 4), 0x105, 0),
            (source.ERA_KIND, self.fields(5, 6), 0x104, 6),
            (source.ERA_SCORE_KIND,
             {0xA1E5A149: scalar(3, 0), 0xD6FCF3E4: scalar(2, 41)},
             0x10A, 6),
            (source.ERA_SCORE_KIND, self.fields(43, 47), 0x10A, 6),
            (source.TURN21_KIND, self.fields(0, 10), 0x10B, 6),
            (0x8C6B2399, {**self.fields(1, 5), 0x38F292C8: scalar(2, 30)}, 0xE2, 0),
            (0x69356374, self.fields(1, 5), 0xDE, 0),
            (0xA7E78C7A, {0xA1E5A149: bytes.fromhex('03000000524f4d4500000000000000000000000000000000'),
                          0xD6FCF3E4: scalar(2, 0)}, 0x108, 6),
            (0x2C333AC8, {0xA1E5A149: scalar(3, 0),
                          0xD6FCF3E4: scalar(2, 1)}, 0x107, 4),
            (source.PROPERTY_KIND, {0xA1E5A149: scalar(3, 0),
                                    0xD6FCF3E4: scalar(2, 0xBBAABBCC)}, 0x106, 0),
        )
        for sequence, (kind, fields, record_type, flag) in enumerate(emissions, 1):
            with self.subTest(kind=hex(kind), sequence=sequence):
                self.assertEqual(owner.dispatch(kind, fields, 0), 0)
                self.assertEqual(len(graph.event.deferred.pending), 1)
                record = graph.event.deferred.pending[0]
                self.assertEqual(struct.unpack_from('<4I', record),
                                 (96, record_type, sequence, 0))
                self.assertEqual(struct.unpack_from('<I', record, 72)[0], flag)
                expected_b = fields.get(0xA1FBC372, bytes(24))[8:12]
                expected_b = int.from_bytes(expected_b, 'little') if isinstance(expected_b, bytes) else expected_b
                expected_a = 0 if record_type == 0x106 else int.from_bytes(fields[0xD6FCF3E4][8:12], 'little')
                self.assertEqual(struct.unpack_from('<3I', record, 80), (sequence, expected_a, expected_b))
                self.assertEqual(struct.unpack_from('<I', record, 92)[0],
                                 30 if record_type == 0xE2 else 0)
                self.assertEqual(graph.event.deferred.drain(), 1)
                self.assertIsNone(owner._foundation_borrow)
                self.assertIsNone(owner.active_kind)
        memory = owner.read.__self__
        pointer = memory.core_base + 0x123000
        memory.put(pointer, struct.pack('<HHI', 1, 99, 77))
        variant = struct.pack('<H6xQII', 1024, pointer, 8, 0x21000001)
        fields = {**self.fields(1, 5), 0x23739F42: variant}
        for sequence, (kind, record_type) in enumerate(
                ((source.TURN21_DESCRIPTOR_KIND, 0xdf), (source.TURN26_DESCRIPTOR_KIND, 0xe3)), len(emissions) + 1):
            with self.subTest(kind=hex(kind)):
                self.assertEqual(owner.dispatch(kind, fields, 0), 0)
                record, = graph.event.deferred.pending
                self.assertEqual(struct.unpack_from('<4I', record), (112, record_type, sequence, 0))
                self.assertEqual(struct.unpack_from('<IIHHIII', record, 80),
                                 (sequence, 0, 1, 2, 77, 1, 5))
                self.assertEqual(graph.event.deferred.drain(), 1)
        self.assertEqual(owner.entity_event_count, 0)
        self.assertEqual(graph.calls, [])

    def test_source_pins_include_exact_missing_second_proof_but_not_xp1_admission(self):
        pins = source.source_dependencies(core_sha256=XP2_CORE_SHA256)
        self.assertIn(source.SOURCE[1], pins.values())
        self.assertIn(source.PROPERTY_SOURCE[1], pins.values())
        self.assertIn('82542c6f053560b0dbd0b9a8ad522d45d65cb88aa5abf7d410d2cb73651cda72',
                      pins.values())
        self.assertEqual(source.source_dependencies(core_sha256=XP1_CORE_SHA256), {})
        self.assertEqual(source.event_profile(core_sha256=XP2_CORE_SHA256).record_types_by_kind[
            source.ERA_SCORE_KIND], frozenset((0x10A,)))
        from civ6_host.runtime import game_history_event_profile as shared_history
        from civ6_host.runtime import game_era_score_event_profile as shared_score
        for kind, expected in (
                (source.HISTORY_KIND, shared_history.EVENTS[source.HISTORY_KIND]),
                (source.ERA_KIND, shared_history.EVENTS[source.ERA_KIND]),
                (source.ERA_SCORE_KIND, shared_score.SPEC)):
            actual, proof = events._selected(kind, XP2_CORE_SHA256)
            self.assertEqual(actual, expected)
            self.assertEqual(proof, source.SOURCE[1])

    def test_xp2_building_pillage_reuses_snapshot_and_empty_receiver(self):
        from contextlib import contextmanager
        from civ6_host.runtime.native import native_event_e660_building_pillaged as event

        graph = self.graph()
        owner = graph.owner
        witness = project.pillage_source()['refusal_headers']['fields']
        fields = {int(key, 16): bytes.fromhex(value) for key, value in witness.items()}
        for key, value in ((0x23739f42, struct.pack('<HHI', 0, 2, 65536)),
                           (0x8c468e3c, struct.pack('<ii', 39, 13))):
            ptr = struct.unpack_from('<Q', fields[key], 8)[0]
            graph.memory.put(ptr, value)

        @contextmanager
        def snapshot(core, context, args, *, read, native_api, core_sha256):
            self.assertIs(core, graph.backend.core)
            self.assertEqual(core_sha256, XP2_CORE_SHA256)
            self.assertEqual((args['x'], args['y']), (39, 13))
            yield dict(owner=0, district_id=42, flag148=1)
            self.assertEqual(len(owner.pending), 1)

        with patch.object(event.snapshot, 'plot_snapshot', snapshot):
            self.assertEqual(owner.dispatch(event.EVENT_KIND, fields, 0), 0)
        record, = owner.pending
        self.assertEqual(struct.unpack_from('<4I', record), (128, 0xaa, 1, 0))
        self.assertEqual(struct.unpack_from('<hHI', record, 104), (0, 3, 42))
        self.assertEqual(owner.deferred.drain(), 1)

    def test_project_reads_retained_game_after_first_record_and_drains_all_three(self):
        graph = self.graph()
        owner = graph.owner
        pointer = graph.memory.core_base + 0x124000
        graph.memory.put(pointer, struct.pack('<HHI', 1, 2, 77))
        fields = {**self.fields(3, 12), 0x38F292C8: scalar(2, 0xffffffff),
                  0x23739F42: struct.pack('<H6xQII', 1024, pointer, 8, 0x21000001)}

        def getter(facades, read, *, core_sha256):
            self.assertIs(facades, graph.continuation.publisher._facades)
            self.assertEqual(read, owner.read)
            self.assertEqual(core_sha256, XP2_CORE_SHA256)
            self.assertEqual([struct.unpack_from('<I', r, 4)[0] for r in owner.pending], [96])
            return 1

        with patch('civ6_host.runtime.native.native_retained_game_getter.read_retained_game_value',
                   side_effect=getter) as retained:
            self.assertEqual(owner.dispatch(project.PROJECT_KIND, fields, 0), 0)
        retained.assert_called_once()
        self.assertEqual([struct.unpack_from('<3I', row) for row in owner.pending],
                         [(112, 96, 1), (128, 99, 2), (128, 100, 3)])
        self.assertEqual([struct.unpack_from('<I', row, 72)[0] for row in owner.pending[1:]],
                         [22, 22])
        self.assertEqual(graph.event.deferred.drain(), 3)


if __name__ == '__main__':
    unittest.main()

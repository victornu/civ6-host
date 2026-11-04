"""XP2 selects only the source-bound combat ownership/query layouts."""
import struct
import unittest

from civ6_host.runtime import combat_event_profile as combat_events
from civ6_host.runtime import combat_map_profiles as combat_maps
from civ6_host.runtime import xp1_combat_profile as shared_combat
from civ6_host.runtime import xp1_world_text_profile as shared_world_text
from civ6_host.runtime import xp2_combat_event_source as xp2_source
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256 as XP2
from civ6_host.runtime.native.native_unit_promotion_query import METHODS, SLOTS
from test_xp1_turn_a0 import scalar


class XP2CombatSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = xp2_source.verify_source(XP2)

    def test_predicate_and_promotion_selectors_match_retained_xp2_source(self):
        p = self.source
        predicate = p['predicate']
        retained = (1, 2, 3, 4)
        selected = shared_combat.predicate_selection(XP2, retained, {})
        self.assertEqual(selected[:4], (predicate['game_table'], predicate['target'],
                                        predicate['state_getter'], predicate['state_global']))
        body = selected[4]['core_captures']['game_owner_predicate']
        self.assertEqual(body, xp2_source._body(p['functions']['predicate']))
        self.assertEqual(selected[4]['leaves']['core_game_state_getter']['raw_hex'],
                         ''.join(bytes.fromhex(row['bytes']).hex() for row in xp2_source.rows(
                             p['functions']['state_getter'])))

        layout = shared_combat.promotion_layout(XP2, METHODS, SLOTS)
        promotion = p['promotion']
        self.assertEqual(layout.map_table, promotion['map_table'])
        self.assertEqual(layout.outer_table, promotion['outer_table'])
        self.assertEqual(layout.service_table, promotion['service_table'])
        self.assertEqual(tuple(layout.slots), tuple(map(tuple, promotion['slots'])))
        for name, (_, result, arguments) in METHODS.items():
            self.assertEqual(layout.methods[name],
                             (promotion['methods'][name], result, arguments))
        proof = shared_combat.promotion_proof(XP2, {})['core_functions']
        for name, source_name in (
                ('outer_e0', 'promotion_outer_e0'), ('outer_release', 'promotion_outer_release'),
                ('map_constructor', 'promotion_map_constructor'), ('map_destructor', 'promotion_map_destructor'),
                ('map_lookup', 'promotion_map_lookup'), ('service_query', 'promotion_service_query'),
                ('service_release', 'promotion_service_release')):
            self.assertEqual(int(proof[name]['start_va'], 16),
                             int(p['functions'][source_name]['rva'], 16) + 0x180000000)

    def test_map_owner_uses_xp2_configuration_abi_and_rebased_source_bytes(self):
        abi = combat_maps.profile_for_sha(XP2)
        self.assertEqual(abi.core_sha256, XP2)
        self.assertEqual((abi.vtable_rva, abi.constructor_rva, abi.assign_rva,
                          abi.destructor_rva), (0xABF080, 0x99E4B0, 0x99E6C0, 0x99E5D0))
        proof = combat_maps.owner_source(XP2)
        self.assertEqual(proof, xp2_source.map_owner_source(core_sha256=XP2))
        self.assertEqual(proof['core_sha256'], XP2)

        base = 0x180000000
        memory = {}
        def put(address, data):
            for offset, byte in enumerate(data):
                memory[address + offset] = byte
        def read(address, size):
            return bytes(memory[address + offset] for offset in range(size))
        for rva, raw in xp2_source.core_fragments():
            put(base + rva, raw)
        put(base + 0xABF080 + 0x1D0, struct.pack('<Q', base + 0x99E6C0))
        put(base + 0xABF080 + 0x178, struct.pack('<Q', base + 0x99E9D0))
        put(base + 0xABFB80, struct.pack('<Q', base + 0x9A7840))
        self.assertIsNone(combat_maps.verify_live(base, read, core_sha256=XP2))
        self.assertEqual(combat_maps.source_dependencies(XP2), xp2_source.source_dependencies())
        put(base + 0xABF080 + 0x1D0, struct.pack('<Q', base + 0x99F5C0))
        with self.assertRaisesRegex(ValueError, 'virtual primitive'):
            combat_maps.verify_live(base, read, core_sha256=XP2)

    def test_combat_and_world_text_profiles_are_engine_selected(self):
        xp2_profile = combat_events.event_profile(XP2)
        self.assertEqual(set(xp2_profile.record_types_by_kind), set(xp2_source.KINDS))
        self.assertEqual(xp2_profile.source_sha256, xp2_source.SOURCE[1])
        world = shared_world_text.event_profile(XP2)
        world_source = xp2_source.world_text_source()
        self.assertEqual(world.record_types_by_kind, {world_source['event_kind']: frozenset((world_source['record_type'],))})
        self.assertEqual(world.record_sizes, {world_source['record_type']: world_source['record_size']})
        self.assertEqual(world.source_sha256, xp2_source.SOURCE[1])
        self.assertEqual(set(combat_events.event_profile().record_types_by_kind),
                         {0x8256DBE1, 0xA479F83F, 0x45B517D6})
        self.assertEqual(shared_world_text.event_profile().source_sha256, shared_world_text.SOURCE[1])
        self.assertEqual(combat_events.source_dependencies(XP2), xp2_source.source_dependencies())

    def test_unknown_engine_and_mismatched_operation_sets_stay_refused(self):
        for select in (
            lambda: shared_combat.predicate_selection('0' * 64, (1, 2, 3, 4), {}),
            lambda: shared_combat.promotion_layout('0' * 64, METHODS, SLOTS),
            lambda: shared_combat.promotion_proof('0' * 64, {}),
            lambda: combat_maps.profile_for_sha('0' * 64),
            lambda: shared_world_text.event_profile('0' * 64),
            lambda: combat_events.event_profile('0' * 64),
        ):
            with self.assertRaises(ValueError):
                select()
        with self.assertRaisesRegex(ValueError, 'operation set'):
            shared_combat.promotion_layout(XP2, {}, SLOTS)

    def test_child_field_and_administrative_policy_wrappers_select_engine(self):
        from civ6_host.runtime.native.native_event_8256dbe1 import CHILD_SCALAR_KEYS
        from civ6_host.runtime.native.native_combat_argument_snapshot import CHILD_BLOBS
        xp1_values = {key: scalar(2, 1) for key in CHILD_SCALAR_KEYS}
        for key, tag in CHILD_BLOBS.items():
            xp1_values[key] = struct.pack('<H6xQII', tag, 0x123400, 8, 553648129)
        self.assertIsNone(shared_combat.validate_child_fields(XP1, xp1_values, CHILD_SCALAR_KEYS))
        with self.assertRaises(ValueError):
            shared_combat.validate_child_fields(XP1, {**xp1_values, 0x1234: b''}, CHILD_SCALAR_KEYS)
        self.assertEqual(shared_combat.administrative_snapshot_policy(BASE), {})
        self.assertEqual(shared_combat.administrative_snapshot_policy(XP1), {})

        xp2_values = {key: scalar(2, 1) for key in xp2_source._CHILD_SCALARS}
        xp2_values.update({0x57C6ED30: b'opaque-owned-descriptor',
                           0x95F2CF6E: b'opaque-owned-descriptor'})
        self.assertIsNone(shared_combat.validate_child_fields(XP2, xp2_values,
                                                               xp2_source._CHILD_SCALARS))
        with self.assertRaises(ValueError):
            shared_combat.validate_child_fields(XP2, xp2_values, ())
        policy = shared_combat.administrative_snapshot_policy(XP2)
        self.assertEqual(policy, xp2_source.administrative_snapshot_policy(XP2))
        self.assertFalse(policy['administrative_snapshot_complete'])

    def test_base_and_xp1_defaults_remain_separate(self):
        retained = (10, 20, 30, 40)
        self.assertEqual(shared_combat.predicate_selection(BASE, retained, {'proof': 1}),
                         (*retained, {'proof': 1}))
        base_layout = shared_combat.promotion_layout(BASE, METHODS, SLOTS)
        self.assertIs(base_layout.methods, METHODS)
        self.assertEqual((base_layout.map_table, base_layout.outer_table, base_layout.service_table),
                         (0x81CFA0, 0x79E020, 0x7A01A8))
        self.assertEqual(shared_combat.source_sha(XP1, 'retained'), shared_combat.SOURCE[1])
        self.assertEqual(combat_events.event_profile().source_sha256, shared_combat.SOURCE[1])


if __name__ == '__main__':
    unittest.main()

from copy import deepcopy
from struct import pack
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn, policies
from civ6_host.runtime import xp1_government_policy_source as source
from civ6_host.runtime import xp1_session_view, xp2_dedications, xp2_government, xp2_policies
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue


class RiseAndFallGovernmentTests(unittest.TestCase):
    def test_action_candidates_are_additive_to_a_retained_dedications_checkpoint(self):
        observation, original = expansion_catalogue()
        actor, turn = observation['player_id'], observation['turn']
        dedication = xp2_dedications.parse_state(f'{actor}|{turn}|0|normal|0'.encode(), actor, turn)
        with patch.object(xp2_dedications, 'catalogue', return_value=dedication):
            xp1_session_view._add_dedications(None, observation, original, actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        seal(original)
        slots = [dict(slot=0, prior_index=-1, options=[
            dict(index=7, hash=17, native_hash=17, policy_type='POLICY_TEST')])]
        public_policies = dict(player_id=actor, turn=turn, reason='available', slots=slots)
        public_government = dict(player_id=actor, turn=turn, current_index=0, can_change=True,
            changed=False, civic_completed=True, considered=False, consideration_blocker=True,
            choices=[dict(index=0, hash=2, unlocked=True, can_change=False, anarchy_turns=0),
                     dict(index=1, hash=3, unlocked=True, can_change=True, anarchy_turns=0),
                     dict(index=2, hash=4, unlocked=True, can_change=True, anarchy_turns=3)])
        current = deepcopy(original)
        current['schema'] = network_turn.XP1_GOVERNMENT_SCHEMA_BY_BASE[original['schema']]
        with (patch.object(xp2_policies, 'read', return_value=public_policies),
              patch.object(xp2_government, 'read', return_value=public_government)):
            xp1_session_view._add_xp1_government_policies(None, observation, current,
                acting=True, actions_closed=False)
        seal(current)
        indexed = {row['action']['kind']: row for row in current['candidates']}
        self.assertEqual(indexed['government']['action'], dict(kind='government', index=1, hash=3))
        self.assertEqual(indexed['retain_government']['action'], dict(kind='retain_government', index=0))
        selected = network_turn.select_capability(current, dict(decision_id=current['decision_id'],
            candidate_id=indexed['policies']['candidate_id'], parameters=dict(assignments=[17])))
        self.assertEqual(selected, dict(kind='policies', candidate=policies.choose(slots, [17], actor, turn)))
        self.assertEqual(current['families']['policies']['unqualified'],
            ['paid_policy_unlock', 'active_policy_relocation', 'unchanged_policy_confirmation'])
        projected, changes = network_turn.checkpoint_catalogue(
            current, original, observation, core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected, original)
        self.assertEqual(changes['added_public_fields'], ['government', 'policies'])
        with self.assertRaisesRegex(ValueError, 'requires Rise and Fall'):
            network_turn.checkpoint_catalogue(current, original, observation, core_sha256=XP2_CORE_SHA256)

    def test_waiting_state_does_not_run_the_native_query(self):
        decisions = dict(candidates=[], families={})
        with (patch.object(xp2_policies, 'read') as read_policies,
              patch.object(xp2_government, 'read') as read_government):
            xp1_session_view._add_xp1_government_policies(None, {}, decisions,
                acting=False, actions_closed=False)
        read_policies.assert_not_called()
        read_government.assert_not_called()
        self.assertIsNone(decisions['policies'])
        self.assertEqual(decisions['families']['government']['status'], 'unqualified')

    def test_live_binding_rejects_foreign_owner_and_changed_packet_vtable(self):
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.xp1_saved_load import REFERENCE

        proof = source.verify_source()
        base = 0x180000000
        memory = {(base + row['rva'], row['bytes']): bytes.fromhex(row['raw_hex'])
                  for row in proof['core_bodies']}
        packet = proof['packet']
        address = base + packet['vtable_rva']
        for row in packet['vtable_targets']:
            memory[(address + 8 * row['slot'], 8)] = (base + row['target_rva']).to_bytes(8, 'little')
        calls = []
        def read(pointer, size):
            calls.append((pointer, size))
            return memory[(pointer, size)]

        backend = SimpleNamespace(check_thread=lambda: None, load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            runtime=SimpleNamespace(read=read), captured_bundle=SimpleNamespace(reference=REFERENCE),
            core=SimpleNamespace(_handle=base, _civ6_host_execution_image=_XP1_PROFILE))
        saved = SimpleNamespace(backend=backend, xp1_government=False)
        with self.assertRaisesRegex(ValueError, 'exact Rise and Fall saved owner'):
            source.bind_owner(saved)
        self.assertEqual(calls, [])
        saved.xp1_government = True
        source.bind_owner(saved)
        previous = list(calls)
        source.bind_owner(saved)
        self.assertEqual(calls, previous)
        del backend._xp1_government_policy_source
        memory[(address + 8 * 4, 8)] = bytes(8)
        with self.assertRaisesRegex(ValueError, 'packet vtable differs'):
            source.bind_owner(saved)

    def test_policy_archive_must_match_the_selected_slot_hash_pairs(self):
        choice = dict(status='candidate', player_id=3, turn=25, slot_count=2,
                      assignments=[[0, -1], [1, 23]])
        header = (0xe57882af, 3, 3, 0xffffffff, 0xffffffff, 2)
        for rows in ((0xffffffff, 0, 23, 1), (23, 1, 0xffffffff, 0)):
            source.validate_policy_archive(pack('<13I', *header, 0, 1, 2, *rows), choice)
        for bad in ((0, 0, 2, 23, 1, 0xffffffff, 0),
                    (0, 1, 2, 23, 0, 0xffffffff, 1),
                    (0, 1, 1, 23, 1, 0xffffffff, 0)):
            with self.assertRaisesRegex(ValueError, 'differs from selected slots'):
                source.validate_policy_archive(pack('<13I', *header, *bad), choice)
        with self.assertRaisesRegex(ValueError, 'header changed'):
            source.validate_policy_archive(pack('>13I', *header, 0, 1, 2, 23, 1, 0xffffffff, 0), choice)


if __name__ == '__main__':
    unittest.main()

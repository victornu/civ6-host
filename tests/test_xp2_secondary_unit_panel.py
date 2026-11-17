"""Borrowed aircraft and construction choices through the LAN owner."""

from copy import deepcopy
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import network_turn as turns
from civ6_host.runtime import network_checkpoint, network_timer, player_views
from civ6_host.runtime import xp1_session_checkpoint, xp2_lan_unit_commands
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from test_xp2_human_perspective import PerspectiveFixture
from test_xp2_lan_war_confirmation import WarFixture


class SecondaryPanelFixture(PerspectiveFixture):
    def __init__(self):
        super().__init__()
        self.enable_turn_fixture()
        self.enable_research_fixture()
        self.enable_world_fixture()
        self.saved._xp2_build_route_core = self.backend.core
        self.saved._xp2_air_operations_core = self.backend.core
        self.turn_rows[2] = (0, 0, 0)
        self.strategic_allowed = False
        self.queued_panel_command = None
        self.railroad_built = False
        self.rebased = False
        self.archive_actor = 1

    def evaluate(self, child, source, name, **options):
        labels = {
            b'@public_build_route_catalogue', b'@build_route_index', b'@build_route_request',
            b'@build_route_effect', b'@public_air_operations', b'@air_operation_index',
            b'@air_operation_request',
        }
        if name not in labels:
            return super().evaluate(child, source, name, **options)
        assert child is self.token.ui_child and self.player == 1 and b'local pid, turn = 1, 8\n' in source
        if name == b'@public_build_route_catalogue':
            return b'1|8' if self.railroad_built or self.rebased else b'1|8\n28|3|3|0|ROUTE_RAILROAD'
        if name == b'@public_air_operations':
            return b'1|8' if self.rebased else b'1|8\nREBASE|28|4|4|0'
        if name == b'@build_route_index':
            return b'25'
        if name == b'@air_operation_index':
            return b'26'
        if name == b'@build_route_effect':
            return b'4|4'
        if name == b'@build_route_request':
            assert b"=28,3,3,0,25,'ROUTE_RAILROAD'" in source
            self.queued_panel_command = 'route'
            self.token.transport.pending.append(pack('<IHH5I', 0x8c0f3f36, self.archive_actor,
                                                    1, 28, 25, 0xffffffff, 0, 0))
            return b'-1'
        assert name == b'@air_operation_request' and b'= 28,4,4,0,26' in source
        self.queued_panel_command = 'air'
        self.token.transport.pending.append(pack('<IHH8I', 0x8c0f3f36, self.archive_actor,
                                                1, 28, 26, 0xffffffff, 0, 1, 4, 0, 0))
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.queued_panel_command is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            assert self.player == 1
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            if self.queued_panel_command == 'route':
                self.railroad_built = True
            else:
                self.rebased = True
                self.observations[1]['units'][0]['x'] = 4
            self.queued_panel_command = None

        return drain


class SecondaryUnitPanelTests(TestCase):
    def test_borrowed_park_request_uses_its_own_archive_and_checkpoint_scope(self):
        from civ6_host.contracts.national_parks import DESIGNATE
        from civ6_host.runtime import expansion_city_growth

        class ParkFixture(SecondaryPanelFixture):
            def evaluate(self, child, source, name, **options):
                if not name.startswith(b'@park_designation_'):
                    return super().evaluate(child, source, name, **options)
                assert child is self.token.ui_child and self.player == 1 and b'local pid,turn=1,8' in source
                if name == b'@park_designation_choices':
                    return b'' if self.designated else b'28|3|0'
                if name == b'@park_designation_index':
                    return b'25'
                if name == b'@park_designation_effect':
                    return b'true' if self.designated else b'false'
                assert name == b'@park_designation_request' and b'local chosen,x,y,opcode=28,3,0,25' in source
                self.queued_panel_command = 'park'
                self.token.transport.pending.append(pack('<IHH5I', 0x8c0f3f36, 1, 1, 28, 25, 0xffffffff, 0, 0))
                return b'requested'

            def virtual(self, core, pointer, slot, rva, result, *args):
                if rva != self.token.transport.transport_abi.drain_rva or self.queued_panel_command != 'park':
                    return super().virtual(core, pointer, slot, rva, result, *args)

                def drain(_):
                    assert self.player == 1
                    self.machine.append(('drain',))
                    self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
                    self.designated = True
                    self.queued_panel_command = None

                return drain

        f = ParkFixture()
        self.addCleanup(f.close)
        f.designated = False
        f.saved._xp2_designate_park = object()
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=f.token.identity,
                                   session=dict(turn=8), catalogue=None)
        protocol.selected = lambda request: turns.select_capability(protocol.catalogue, request['selection'])
        with (patch.object(network_timer, 'read', return_value=False),
              patch.object(expansion_city_growth, '_owner', return_value=f.saved._xp2_designate_park)):
            _, protocol.session, observation, choices, _ = xp2_lan_unit_commands.read_reply(
                f.saved, protocol, dict(sequence=1, player_id=1, operation='observe'), (0, 1))
            turns.validate_catalogue(choices, protocol.identity, 1, 8, player_id=1, observation=observation)
            protocol.catalogue = choices
            candidate, = choices['families'][DESIGNATE]['candidate_ids']
            request = dict(sequence=2, player_id=1, operation='act',
                           selection=dict(decision_id=choices['decision_id'], candidate_id=candidate))
            _, protocol.session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(
                f.saved, protocol, request, (0, 1))
            self.assertEqual(receipt['status'], 'completed')
            self.assertTrue(f.designated)
            self.assertEqual(f.player, 0)
            self.assertEqual(choices['families'][DESIGNATE]['candidate_ids'], [])
            boundary = xp1_session_checkpoint.boundary(f.saved)
            args = (f.saved, boundary, (0, 1))
            current = player_views.checkpoint_view_digests(*args, decision_players=(1,))
            previous = player_views.checkpoint_view_digests(*args, decision_players=(1,),
                                                           unit_panel_families=('air_operation', 'build_route'))
            self.assertIn(DESIGNATE, current['unit_panel_families'])
            self.assertNotIn(DESIGNATE, previous['unit_panel_families'])

    def test_borrowed_commands_and_resume_restore_exact_seat(self):
        f = SecondaryPanelFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        original = deepcopy(f.observations[0])
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogue=None)
        protocol.selected = lambda request: turns.select_capability(protocol.catalogue, request['selection'])

        def reply(sequence, kind=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if kind is None else 'act')
            if kind is not None:
                selected, = protocol.catalogue['families'][kind]['candidate_ids']
                request['selection'] = dict(decision_id=protocol.catalogue['decision_id'], candidate_id=selected)
            _, protocol.session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.catalogue = choices
            self.assertEqual(f.player, 0)
            self.assertEqual(f.observations[0], original)
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            observation, choices, _ = reply(1)
            self.assertEqual(choices['families']['build_route']['status'], 'queried_complete')
            self.assertEqual(choices['families']['air_operation']['status'], 'queried_partial')
            reply(2, 'build_route')
            observation, choices, receipt = reply(3, 'air_operation')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['units'][0]['x'], 4)
            self.assertTrue(f.railroad_built)
            self.assertEqual(sum(row[0] == 'receive' for row in f.machine), 2)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['unit_panel_families'], ['air_operation', 'build_route'])
            previous = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                           unit_panel_families=())
            self.assertNotIn('unit_panel_families', previous)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=previous)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            self.assertEqual(network_checkpoint._checkpoint_view_scope(state), ((0, 1), (1,)))
            bad = deepcopy(state)
            bad['checkpoint_public_views']['unit_panel_families'].reverse()
            with self.assertRaisesRegex(ValueError, 'secondary UnitPanel scope'):
                network_checkpoint._checkpoint_view_scope(bad)

    def test_foreign_archive_stops_before_native_receive(self):
        from civ6_host.runtime.xp2_human_perspective import read_network_boundary

        f = SecondaryPanelFixture()
        self.addCleanup(f.close)
        f.archive_actor = 0
        action = dict(kind='build_route', unit_id=28, plot_id=3, x=3, y=0, route_type='ROUTE_RAILROAD')
        with self.assertRaisesRegex(ValueError, 'differs from its actor'):
            read_network_boundary(f.saved, 1, action)
        self.assertFalse(f.railroad_built)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

    def test_secondary_air_strike_opens_existing_war_modal_without_attack(self):
        class AirWarFixture(WarFixture):
            def evaluate(self, child, source, name, **options):
                if name not in (b'@public_air_operations', b'@air_operation_index', b'@air_operation_request'):
                    return super().evaluate(child, source, name, **options)
                assert self.player == 1 and child is self.token.ui_child
                if name == b'@public_air_operations':
                    return b'1|8\nAIR_ATTACK|28|4|4|0'
                if name == b'@air_operation_index':
                    return b'27'
                assert b'= 28,4,4,0,27' in source
                return f"war|2|{self.prompt['war_type']}".encode('ascii')

        f = AirWarFixture()
        self.addCleanup(f.close)
        f.saved._xp2_air_operations_core = f.backend.core
        _, choices, _ = f.reply(1)
        attack, = [row['action'] for row in choices['candidates']
                   if row['action']['kind'] == 'air_operation']
        _, modal, result = f.reply(2, attack)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(modal['world_input']['war_prompt'], f.prompt)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))
        f.request_war.assert_not_called()
        cancel, = [row['action'] for row in modal['candidates'] if not row['action']['accept']]
        _, choices, result = f.reply(3, cancel)
        self.assertEqual(result['status'], 'completed')
        self.assertIn('air_operation', choices['families'])
        self.assertEqual(f.player, 0)
        self.assertFalse(f.at_war)
        f.request_war.assert_not_called()

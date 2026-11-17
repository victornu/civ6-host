"""Formations across the authenticated secondary LAN command boundary."""

import json
from struct import pack
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import unit_formations as contract
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
from civ6_host.runtime import xp2_unit_formations as formations
from civ6_host.runtime.native.native_saved_trade import literal
from test_xp2_lan_trade import TradeFixture


ENTER = dict(kind=contract.KIND, command='enter', unit_id=28, partner_id=30)
EXIT = dict(kind=contract.KIND, command='exit', unit_id=28, partner_id=None)


class FormationFixture(TradeFixture):
    def __init__(self):
        super().__init__(stock=True)
        self.saved.unit_formations = True
        self.token.explicit_unit_formations = {'primary': 'retained'}
        self.units = self.observations[1]['units']
        self.units.append(dict(self.units[0], id=30, type=13))
        self.joined = False
        self.partner_owner = 1
        self.remaining = 1.5
        self.apply_formation = True
        self.formation_pending = None
        self.stack.enter_context(patch.object(formations, 'REFERENCE', self.backend.captured_bundle.reference))

    def evaluate(self, child, source, tag, **options):
        if tag == b'@explicit_unit_orders' and self.player == 1:
            wire = super().evaluate(child, source, tag, **options)
            roster, separator, orders = wire.partition(b'\nA|')
            return roster + b'\nU|30|0|0|1' + separator + orders
        if tag not in (b'@stock_unit_formations', b'@stock_unit_formation_request'):
            return super().evaluate(child, source, tag, **options)
        assert child is self.token.ui_child and self.player == 1 and b'local pid,turn=1,8' in source
        action = EXIT if self.joined else ENTER
        if tag == b'@stock_unit_formations':
            wire_action = dict(action, partner_id=-1) if action is EXIT else action
            rows = [dict(unit_id=u['id'], count=2 if self.joined else 1, moves=self.remaining,
                         max_moves=2, formation_id=1234 if self.joined else -1) for u in self.units]
            return json.dumps(dict(schema=contract.SCHEMA, player_id=1, turn=8,
                                   units=rows, offers=[wire_action])).encode()
        expected_lua = dict(action, partner_id=-1) if action is EXIT else action
        assert f'local selected={literal(expected_lua)}'.encode() in source
        self.formation_pending = action
        if action is ENTER:
            archive = pack('<IHH4IHH2I', 0x493830af, 1, 1, 28, 3, 0, 1, self.partner_owner, 1, 30, 0)
        else:
            archive = pack('<IHH3I', 0x493830af, 1, 1, 28, 4, 0)
        self.token.transport.pending.append(archive)
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.formation_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            if self.apply_formation:
                self.joined = self.formation_pending is ENTER
            self.formation_pending = None
        return drain


class SecondaryFormationTests(TestCase):
    def fixture(self):
        f = FormationFixture()
        self.addCleanup(f.close)
        return f

    def test_join_and_leave_publish_the_owned_roster_and_preserve_checkpoint_scope(self):
        f = self.fixture()
        observation, choices, _ = f.reply(1)
        self.assertEqual(contract.actions(project('unit_formations', observation, choices)), [ENTER])
        f.remaining = 1
        _, _, receipt = f.reply(2, ENTER)
        self.assertEqual(receipt['reason'], 'native_unit_formation_choice_changed')
        self.assertFalse(f.joined)

        observation, choices, receipt = f.reply(3, ENTER)
        self.assertEqual(receipt['status'], 'completed')
        state = project('unit_formations', observation, choices)
        self.assertEqual([unit['count'] for unit in state['units']], [2, 2])
        self.assertTrue(all('formation_id' not in unit for unit in state['units']))
        self.assertEqual(contract.actions(state), [EXIT])

        boundary = xp1_session_checkpoint.boundary(f.saved)
        current = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,))
        old = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,),
                                                   formation_enabled=False)
        self.assertIs(current['formation_enabled'], True)
        self.assertNotIn('formation_enabled', old)
        self.assertIs(old['trade_enabled'], True)
        state = dict(observation=f.token.observation, decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary)
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (current, old):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))

        f.apply_formation = False
        _, _, receipt = f.reply(4, EXIT)
        self.assertEqual(receipt['reason'], 'native_unit_formation_effect_unobserved')
        self.assertTrue(f.joined)
        f.apply_formation = True
        observation, choices, receipt = f.reply(5, EXIT)
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual([row['count'] for row in choices['unit_formations']['units']], [1, 1])
        self.assertEqual(f.player, 0)
        self.assertEqual(f.token.explicit_unit_formations, {'primary': 'retained'})

    def test_rejects_the_foreign_partner_in_the_native_archive(self):
        f = self.fixture()
        f.reply(1)
        f.partner_owner = 0
        with self.assertRaisesRegex(RuntimeError, 'Formation archive differs'):
            f.reply(2, ENTER)
        self.assertFalse(f.joined)
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

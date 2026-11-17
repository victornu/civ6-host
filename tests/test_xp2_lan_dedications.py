"""Stock dedication selection through the registered secondary LAN actor."""

from struct import pack
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import dedications, network_turn
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
from civ6_host.runtime import xp2_dedications, xp2_lan_unit_commands
from civ6_host.runtime.native import native_player_operation_request as operation
from test_xp2_lan_formations import FormationFixture


class DedicationFixture(FormationFixture):
    def __init__(self):
        super().__init__()
        self.saved.stock_dedications = True
        self.strategic_allowed = False
        self.saved._dedication_binding = self.backend.core, self.saved.prefix, 1
        self.token.explicit_dedications = {'primary': 'retained'}
        self.choices = ['SCIENTIFIC', 'CULTURAL', 'INFRASTRUCTURE', 'RELIGIOUS']
        self.active_dedications = []
        self.dedication_requests = []
        self.queued = []
        self.foreign_second_archive = False
        self.stack.enter_context(patch.object(xp2_dedications, 'REFERENCE', self.backend.captured_bundle.reference))
        self.stack.enter_context(patch.object(operation, 'request_player_operation', side_effect=self.submit))

    def evaluate(self, child, source, tag, **options):
        if tag != b'@xp2_dedication_player_cache':
            return super().evaluate(child, source, tag, **options)
        assert child is self.token.ui_child and self.player == 1
        assert b'local pid, turn, startTurn = 1, 8, 1' in source
        remaining = 3 - len(self.active_dedications)
        rows = [f'1|8|1|heroic|{remaining}']
        if remaining:
            rows.extend(f'choice|{index}|COMMEMORATION_{name}' for index, name in enumerate(self.choices))
        rows.extend(f'active|{index}|COMMEMORATION_{self.choices[index]}' for index in self.active_dedications)
        return '\n'.join(rows).encode()

    def submit(self, core, context, player, command, parameters, *, core_sha256, dedication_permit):
        assert core is self.backend.core and context == self.backend.context and self.player == player == 1
        assert xp2_dedications.authorize_request(dedication_permit, core, context, player, command,
            parameters, core_sha256=core_sha256, submit=True, allow_empty=False) == 'COMMEMORATE'
        index = parameters[xp2_dedications.PARAMETER]
        sender = 0 if self.foreign_second_archive and len(self.dedication_requests) == 1 else player
        self.dedication_requests.append(index)
        self.queued.append(index)
        archive = pack('<7IHH10xI', 0xc45de12f, sender, 0x9e4ddfd9, 2,
                       0x80000001, 1, 0x6a475e64, 0, 2, index)
        self.token.transport.pending.append(archive)
        return dict(request_invoked=True, can_start=None)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or not self.queued:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            self.active_dedications.append(self.queued.pop(0))
        return drain

    def confirm(self, sequence, indices):
        request = dict(operation='act', player_id=1, sequence=sequence, selection=dict(
            decision_id=self.protocol.catalogues[1]['decision_id'],
            candidate_id=network_turn.digest(dedications.CANDIDATE), parameters={'indices': indices}))
        _, session, observation, choices, result = xp2_lan_unit_commands.read_reply(
            self.saved, self.protocol, request, (0, 1))
        network_turn.validate_catalogue(choices, self.token.identity, sequence, 8,
                                        player_id=1, observation=observation)
        self.protocol.session = session
        self.protocol.catalogues[1], self.protocol.observations[1] = choices, observation
        return observation, choices, result


class SecondaryDedicationTests(TestCase):
    def fixture(self):
        f = DedicationFixture()
        self.addCleanup(f.close)
        return f

    def test_heroic_selection_preserves_order_and_checkpoint_scope(self):
        f = self.fixture()
        observation, choices, _ = f.reply(1)
        self.assertIsNone(choices['unit_orders'])
        self.assertEqual(project('dedications', observation, choices)['remaining'], 3)
        with self.assertRaisesRegex(ValueError, 'offered choices or native count'):
            f.confirm(2, [0])
        self.assertEqual(f.dedication_requests, [])

        f.choices[0] = 'SCIENTIFIC_ALTERNATE'
        _, _, receipt = f.confirm(2, [3, 0, 2])
        self.assertEqual(receipt['reason'], 'native_dedication_choices_changed')
        self.assertEqual(f.dedication_requests, [])
        observation, choices, receipt = f.confirm(3, [3, 0, 2])
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(f.dedication_requests, [3, 0, 2])
        state = project('dedications', observation, choices)
        self.assertEqual(state['remaining'], 0)
        self.assertEqual([row['index'] for row in state['active']], [3, 0, 2])
        self.assertEqual(f.player, 0)
        self.assertEqual(f.token.explicit_dedications, {'primary': 'retained'})

        boundary = xp1_session_checkpoint.boundary(f.saved)
        current = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,))
        old = player_views.checkpoint_view_digests(f.saved, boundary, (0, 1), decision_players=(1,),
                                                   dedication_enabled=False)
        self.assertIs(current['dedication_enabled'], True)
        self.assertNotIn('dedication_enabled', old)
        self.assertIs(old['formation_enabled'], True)
        state = dict(observation=f.token.observation, decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary)
        f.saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (current, old):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(f.saved, f.token.observation)))

    def test_foreign_second_archive_is_refused_before_delivering_the_first(self):
        f = self.fixture()
        f.reply(1)
        f.foreign_second_archive = True
        with self.assertRaisesRegex(RuntimeError, 'Dedication archive differs'):
            f.confirm(2, [3, 0, 2])
        self.assertEqual(f.dedication_requests, [3, 0])
        self.assertEqual(f.active_dedications, [])
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

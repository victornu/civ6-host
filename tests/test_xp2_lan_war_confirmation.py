"""Exercise the LAN API on a composed borrowed-seat fixture."""

import json
import struct
import unittest
from unittest.mock import Mock, patch
from zlib import crc32

from civ6_host.contracts import network_turn as turns
from civ6_host.runtime import network_timer, xp2_lan_unit_commands, xp2_world_configuration
from civ6_host.runtime import xp2_world_war_display as display
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native import native_player_operation_request as operations
from civ6_host.runtime.native import native_world_click as click
from civ6_host.runtime.network_protocol import NetworkProtocol
from test_world_war_decisions import PIN, PROMPT, make_catalogue
from test_xp2_human_perspective import PerspectiveFixture


class WarFixture(PerspectiveFixture):
    operation, attacker_key, defender_key = 0xb6e469af, 0x0483191c, 0x6f25158b

    def __init__(self, *, defender=2):
        super().__init__()
        self.enable_turn_fixture()
        self.enable_research_fixture()
        self.enable_production_fixture()
        self.enable_world_fixture()
        self.turn_rows[2] = (0, 0, 0)
        self.saved.war_source_sha256 = PIN
        self.defender = defender
        self.prompt = dict(PROMPT, attacking_player=1, defending_player=defender)
        self.at_war, self.queued, self.major, self.sender = False, False, False, 1
        self.stack.enter_context(patch.object(display, 'verify_source', return_value={'source_sha256': PIN}))
        self.stack.enter_context(patch.object(display, 'read', side_effect=self.render))
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        self.stack.enter_context(patch.object(xp2_world_configuration, 'read', return_value={}))
        self.stack.enter_context(patch.object(xp2_world_configuration, 'lua_bindings', return_value=b''))
        self.request_war = self.stack.enter_context(patch.object(
            operations, 'request_player_operation', side_effect=self.submit))
        self.protocol = NetworkProtocol(self.token.identity, 'a' * 32, initial_turn=8,
                                        core_sha256=XP2_CORE_SHA256, war_source_sha256=PIN)
        self.protocol.session = {'turn': 8}

    def render(self, owner, observation, prompt):
        assert self.player == observation['player_id'] == 1 and owner.active and prompt == self.prompt
        return dict(make_catalogue()['world_input']['war_display'], player_id=1, turn=8,
            defender_player_ids=[self.defender],
            targets=[dict(player_id=self.defender, display_name='Target', icon_name='ICON')])

    def evaluate(self, child, source, name, **options):
        if name == b'@xp2_war_modal_own_units':
            assert self.player == 1
            name = b'@world_input_own_units'
        if name == b'@xp2_war_target_kind':
            assert self.player == 1 and child is self.token.ui_child
            assert f'CanDeclareWar({self.defender})'.encode() in source
            return b'true' if self.major else b'false'
        if name == b'@xp2_explicit_war_state':
            assert self.player == 1 and child is self.token.ui_child and b'IsAtWarWith' in source
            return json.dumps(dict(player_id=1, turn=8, defender_player_id=self.defender, at_war=self.at_war,
                operation=self.operation, player_one_key=self.attacker_key,
                player_two_key=self.defender_key)).encode()
        if name == b'@xp2_official_world_war_response':
            assert self.player == 1 and child is self.token.ui_child
            declaration = source.split(b'local pid,expectedTurn,defender,warType,accept=', 1)[1]
            route = 'minor_route' if declaration.splitlines()[0].endswith(b',true') else 'declined'
            return f'{route},1,8,{self.defender},{PROMPT["war_type"]},-,-,{click._war_source_hash()}'.encode()
        return super().evaluate(child, source, name, **options)

    def evaluate_world_click(self, source, observation):
        assert self.player == 1 and observation['player_id'] == 1
        assert b"if unqualified then\n assert(requestCount==1" in source
        width, height = observation['width'], observation['height']
        return (f'war_prompt,1,8,28,4,{width},{height},-,-,-,{self.defender},'
                f'{PROMPT["war_type"]},{click._SOURCE_HASH}').encode()

    def submit(self, core, context, player, operation, parameters, *, core_sha256):
        assert core is self.backend.core and context is self.backend.context
        assert (self.player, player, operation, core_sha256) == (1, 1, self.operation, XP2_CORE_SHA256)
        assert parameters == {self.attacker_key: 1, self.defender_key: 2}
        header = struct.pack('<6I', 0xc45de12f, self.sender, operation, 2, 0x80000001, 2)
        fields = b''.join(struct.pack('<IHH10xI', key, 0, 2, value)
                          for key, value in parameters.items())
        self.token.transport.pending.append(header + fields)
        self.queued = True
        return dict(can_start=True, request_invoked=True)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva == self.token.transport.transport_abi.drain_rva and self.queued:
            def drain(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                self.queued, self.at_war = False, True
            return drain
        return super().virtual(core, pointer, slot, rva, result, *args)

    def reply(self, revision, action=None):
        request = dict(sequence=revision, player_id=1, operation='observe' if action is None else 'act')
        if action is not None:
            request['selection'] = dict(decision_id=self.protocol.catalogues[1]['decision_id'],
                                        candidate_id=turns.digest(action))
        _, session, observation, choices, result = xp2_lan_unit_commands.read_reply(
            self.saved, self.protocol, request, (0, 1))
        turns.validate_catalogue(choices, self.token.identity, revision, 8,
            player_id=1, observation=observation, expected_war_source_sha256=PIN)
        self.protocol.session = session
        self.protocol.catalogues[1], self.protocol.observations[1] = choices, observation
        return observation, choices, result

    def open_modal(self, revision=1):
        self.reply(revision)
        self.reply(revision + 1, dict(kind='world_select_unit', unit_id=28))
        return self.reply(revision + 2, dict(kind='world_plot_click', unit_id=28, plot_id=4, x=4, y=0))


class MajorWarFixture(WarFixture):
    def __init__(self, *, defender=2):
        super().__init__(defender=defender)
        from civ6_host.runtime import xp2_diplomacy_display_source, xp2_statement_factory, xp2_statement_source
        from civ6_host.runtime.native import native_diplomacy_configuration, native_diplomacy_display986
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        from civ6_host.runtime.native.native_diplomacy_statement import NAMES, StatementReceiver

        self.major = True
        self.session_open = False
        self.dialogue_message = None
        self.statement = dict(event_sequence=73, automatic_response=False, fields=dict.fromkeys(NAMES, 0))
        self.statement['fields'].update(SessionID=9, FromPlayer=self.defender, ToPlayer=1,
            StatementType=xp2_statement_factory.REQUEST_HASH, StatementSubType=crc32(b'NONE') ^ 0xffffffff)
        self.owner.statement_event_profile = self.owner._statement_event_profile = xp2_statement_source.PROFILE
        self.owner._statement_producing = self.owner._statement_poisoned = False
        self.deferred.diplomacy_statement_receiver = self.deferred
        self.deferred.statement_consumer = StatementReceiver()
        self.deferred.combat_map_registry = CombatMapRegistry(limit=64, core_sha256=XP2_CORE_SHA256)
        xp2_world_configuration.read.return_value = dict(is_any_multiplayer=True,
                                                         players={self.defender: {'is_human': False}})
        self.stack.enter_context(patch.object(xp2_statement_factory, 'verify_request', return_value={}))
        self.stack.enter_context(patch.object(xp2_diplomacy_display_source, 'verify_live'))
        self.stack.enter_context(patch.object(native_diplomacy_configuration, 'read',
                                              return_value={2: {'leader': 'LEADER_TEST'}, 0: {'human': False}}))
        self.stack.enter_context(patch.object(native_diplomacy_display986, 'read', return_value=dict(
            schema=native_diplomacy_display986.SCHEMA, speaker_leader='LEADER_TEST',
            statement_text='War', reason_text='', selections=[
                dict(key='CHOICE_EXIT', text='Close', disabled=False, tooltip=None)])))
        self.backend.diplomacy_database_namespace_attached = True

    def evaluate(self, child, source, name, **options):
        if name == b'@xp2_official_world_war_response' and source.splitlines()[0].endswith(b',true'):
            assert self.player == 1
            fields = ((0xbaef29be, 3, self.statement['fields']['StatementType']), (0x9c594aff, 2, 1),
                      (0x18383f56, 2, self.defender), (0x7f30e862, 3, 9))
            archive = struct.pack('<4I', 0xa4172391, 1, 9, len(fields)) + b''.join(
                struct.pack('<II8xI', key, tag, value) for key, tag, value in fields)
            self.token.transport.pending.append(archive)
            self.dialogue_message = 'open'
            return (f'session_request,1,8,{self.defender},{PROMPT["war_type"]},DECLARE_SURPRISE_WAR,+,'
                    f'{click._war_source_hash()}').encode()
        if name in (b'@xp2_world_war_pending_session', b'@xp2_saved_pending_dialogue'):
            assert self.player == 1 and self.session_open
            return b'1|9|2|1|1|DECLARE_SURPRISE_WAR|NONE|'
        if name == b'@official_diplomacy_choices':
            assert self.player == 1 and self.session_open
            row = dict(key='CHOICE_EXIT', sort=0, text='Close', disabled=False,
                       tooltip=None, diplomatic_action_type=None)
            return json.dumps(dict(identity='1|9|2|1|1|DECLARE_SURPRISE_WAR|NONE|',
                                   statement_text='War', mood=0, selections=[row])).encode()
        if name == b'@explicit_native_diplomacy_response':
            assert self.player == 1 and self.session_open and b'CloseSession(9)' in source
            self.token.transport.pending.append(struct.pack('<6I', 0x08a6cf5f, 9, 0x1baabc8b, 1, 0, 0))
            self.dialogue_message = 'close'
            return b'accepted'
        if name == b'@xp2_surprise_war_exit_effect':
            assert self.player == 1 and not self.session_open and self.at_war
            return b'closed_at_war'
        return super().evaluate(child, source, name, **options)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.dialogue_message is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            assert self.player == 1
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            self.session_open = self.dialogue_message == 'open'
            self.at_war = True
            if self.session_open:
                self.deferred.pending_diplomacy_statements.append(self.statement)
            self.dialogue_message = None

        return drain


class HumanWarFixture(MajorWarFixture):
    def __init__(self, *, closing_player=1):
        super().__init__(defender=0)
        self.closing_player = closing_player
        xp2_world_configuration.read.return_value['players'][0]['is_human'] = True

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.dialogue_message is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            assert self.player == 1
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            if self.dialogue_message == 'open':
                self.session_open = True
                fields = ((0x9c594aff, 2, 1), (0x18383f56, 2, 0), (0x0a653b30, 2, 0x4396d725))
                followup = struct.pack('<4I', 0xa797ad1c, 1, 0, len(fields)) + b''.join(
                    struct.pack('<II8xI', key, tag, value) for key, tag, value in fields)
                closer = struct.pack('<6I', 0x08a6cf5f, 9, 0x1baabc8b, self.closing_player, 0, 0)
                self.token.transport.pending.extend((followup, closer))
                self.dialogue_message = 'apply'
            elif self.dialogue_message == 'apply':
                self.at_war = True
                self.dialogue_message = 'close'
            else:
                assert self.dialogue_message == 'close'
                self.session_open = False
                self.dialogue_message = None

        return drain


class SecondaryWarTests(unittest.TestCase):
    def fixture(self):
        fixture = WarFixture()
        self.addCleanup(fixture.close)
        return fixture

    def test_secondary_public_modal_declines_and_confirms_with_own_sender(self):
        fixture = self.fixture()
        observation, modal, click_result = fixture.open_modal()
        self.assertEqual(click_result['status'], 'completed')
        self.assertEqual(modal['world_input']['war_prompt'], fixture.prompt)
        cancel, confirm = [row['action'] for row in modal['candidates']]
        self.assertEqual((cancel['accept'], confirm['accept']), (False, True))
        cancelled, ordinary, result = fixture.reply(4, cancel)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(cancelled, observation)
        self.assertIn('families', ordinary)
        fixture.request_war.assert_not_called()
        self.assertFalse(fixture.at_war)
        self.assertEqual(sum(row[0] == 'receive' for row in fixture.machine), 0)

        fixture.open_modal(5)
        _, ordinary, result = fixture.reply(8, confirm)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(fixture.token.world_input_prompts, {1: None})
        self.assertIn('families', ordinary)
        self.assertTrue(fixture.at_war)
        self.assertEqual(sum(row[0] == 'receive' for row in fixture.machine), 1)
        self.assertEqual(fixture.player, 0)
        self.assertEqual(fixture.token.observation, fixture.observations[0])

    def test_secondary_major_accept_refuses_before_request_and_keeps_choices(self):
        fixture = self.fixture()
        _, modal, _ = fixture.open_modal()
        fixture.major = True
        confirm = modal['candidates'][1]['action']
        _, pending, result = fixture.reply(4, confirm)
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['reason'], 'xp2_war_major_continuation_unqualified')
        self.assertEqual(pending['world_input'], modal['world_input'])
        fixture.request_war.assert_not_called()

    def test_secondary_major_uses_native_public_dialogue_then_restores_both_views(self):
        fixture = MajorWarFixture()
        self.addCleanup(fixture.close)
        _, modal, _ = fixture.open_modal()
        _, dialogue, receipt = fixture.reply(4, modal['candidates'][1]['action'])
        self.assertEqual(receipt['status'], 'completed')
        self.assertTrue(fixture.session_open)
        self.assertTrue(turns.is_diplomacy_decisions(dialogue))
        self.assertEqual((dialogue['player_id'], dialogue['dialogue']['session_id']), (1, 9))
        self.assertNotIn('statement', dialogue)
        self.assertEqual(fixture.saved.read_xp2_human_view(0)['observation'], fixture.observations[0])
        self.assertEqual(fixture.saved.read_xp2_human_view(1)['observation'], fixture.observations[1])
        self.assertEqual(fixture.player, 0)
        fixture.protocol.decisions = dialogue
        request = dict(schema=fixture.protocol.schema, nonce=fixture.protocol.nonce,
            episode_id=fixture.token.identity.episode_id, game_generation=fixture.token.identity.game_generation,
            sequence=fixture.protocol.sequence + 1, player_id=0, operation='poll')
        with self.assertRaisesRegex(ValueError, 'pending diplomacy dialogue'):
            fixture.protocol.validate(request)
        self.assertEqual(fixture.protocol.validate(dict(request, player_id=1, operation='observe')), 'observe')
        from civ6_host import ProtocolError, SessionClient

        client_backend = Mock(controllable_player_ids=(0, 1), session_operations_player_id=0)
        client = SessionClient(client_backend)
        client._session = fixture.protocol.session
        client._closed = False
        client._reply = dict(decisions=dialogue, outcome={'terminated': False, 'truncated': False})
        with self.assertRaisesRegex(ProtocolError, 'pending diplomacy dialogue'):
            client.observe(0)
        client_backend.request.assert_not_called()
        with (self.assertRaisesRegex(ProtocolError, 'pending diplomacy dialogue'), client):
            pass
        client_backend.abort.assert_called_once_with('session_client_abort')

        _, held, _ = fixture.reply(5)
        self.assertEqual(held['dialogue'], dialogue['dialogue'])
        close, = [row['action'] for row in held['candidates']]
        _, ordinary, receipt = fixture.reply(6, close)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=close))
        self.assertFalse(fixture.session_open)
        self.assertTrue(fixture.at_war)
        self.assertIsNone(fixture.saved._xp2_borrowed_war)
        self.assertEqual(fixture.deferred.pending_diplomacy_statements, [])
        self.assertIn('families', ordinary)
        self.assertEqual(fixture.player, 0)
        self.assertEqual(sum(row[0] == 'receive' for row in fixture.machine), 2)

    def test_secondary_human_target_keeps_the_world_prompt_before_native_request(self):
        fixture = MajorWarFixture()
        self.addCleanup(fixture.close)
        xp2_world_configuration.read.return_value['players'][2]['is_human'] = True
        _, modal, _ = fixture.open_modal()
        _, pending, receipt = fixture.reply(4, modal['candidates'][1]['action'])
        self.assertEqual(receipt['reason'], 'xp2_war_major_continuation_unqualified')
        self.assertEqual(pending['world_input'], modal['world_input'])
        self.assertFalse(fixture.session_open)
        self.assertFalse(any(row[0] == 'receive' for row in fixture.machine))

    def test_secondary_human_target_finishes_the_core_generated_close_without_a_choice(self):
        fixture = HumanWarFixture()
        self.addCleanup(fixture.close)
        _, modal, _ = fixture.open_modal()
        _, ordinary, receipt = fixture.reply(4, modal['candidates'][1]['action'])
        self.assertEqual(receipt['status'], 'completed')
        self.assertIn('families', ordinary)
        self.assertTrue(fixture.at_war)
        self.assertFalse(fixture.session_open)
        self.assertEqual(fixture.player, 0)
        self.assertEqual(fixture.token.world_input_prompts, {1: None})
        self.assertEqual(fixture.deferred.pending_diplomacy_statements, [])
        self.assertEqual(sum(row[0] == 'receive' for row in fixture.machine), 3)
        result, = [event for stage, event in fixture.emitted if stage == 'xp2_world_war_response_effect']
        self.assertTrue(result['native_automatic_close'])
        self.assertFalse(result['automatic_choices_applied'])
        self.assertFalse(result['native_war_state_before']['at_war'])

    def test_human_war_refuses_the_foreign_auto_close_archive(self):
        fixture = HumanWarFixture(closing_player=0)
        self.addCleanup(fixture.close)
        _, modal, _ = fixture.open_modal()
        with self.assertRaisesRegex(RuntimeError, 'exit archive differs'):
            fixture.reply(4, modal['candidates'][1]['action'])
        self.assertTrue(fixture.saved.poisoned)
        self.assertTrue(fixture.session_open)
        self.assertEqual(sum(row[0] == 'receive' for row in fixture.machine), 2)

    def test_foreign_archive_is_rejected_before_delivery(self):
        fixture = self.fixture()
        _, modal, _ = fixture.open_modal()
        fixture.sender = 0
        with self.assertRaisesRegex(RuntimeError, 'archive differs from native sender'):
            fixture.reply(4, modal['candidates'][1]['action'])
        self.assertEqual(sum(row[0] == 'receive' for row in fixture.machine), 0)
        self.assertFalse(fixture.at_war)

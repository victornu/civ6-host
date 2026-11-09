"""Synthetic LAN transcript for the distinct XP2 war-modal route.

The native outcome and public views are fixtures; this covers client/protocol
identity and selection handling only, not engine admission or war application.
"""
import copy
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from civ6_host.contracts import network_turn, xp2_war_confirmation
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.native.native_victory_episode import POLICY_ID
from civ6_host.runtime.network_protocol import NetworkProtocol, SCHEMA, validate_network_response
from civ6_host.runtime.xp1_session_result import result_provenance
from civ6_host.session_client import ProtocolError, SessionClient


PIN = 'b' * 64
TURN = 47


def seal(value):
    value['decision_id'] = network_turn.digest(
        {key: item for key, item in value.items() if key != 'decision_id'})
    return value


def observation(player=0):
    return dict(schema='civ6rl-player-observation-v1', player_id=player, turn=TURN,
        width=3, height=2, plots=[], visible_enemy_units=[], cities=[],
        units=[dict(id=101, type=1, x=0, y=0, damage=0, moves=2,
                    max_moves=2, owner=player)],
        economy=dict(science=1, culture=1, gold=20, faith=0))


def normal_catalogue(identity, sequence):
    controls = dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=0,
        turn=TURN, active=True, active_complete=True, can_unready=False,
        timer_elapsed=None)
    return seal(dict(schema=network_turn.CAPABILITY_SCHEMA,
        episode_id=identity.episode_id, game_generation=identity.game_generation,
        sequence=sequence, player_id=0, turn=TURN, turn_controls=controls,
        candidates=[], families=dict(
            found_city=dict(status='queried_complete', candidate_ids=[]),
            other_human_actions=dict(status='unqualified', reason='fixture_scope_only')),
        family_inventory_complete=False, complete_action_space=False))


def modal_catalogue(identity, sequence):
    prompt = dict(attacking_player=0, defending_player=2, war_type=1133958949)
    world_input = dict(schema='civ6rl.world_input.v3', player_id=0, turn=TURN,
        width=3, height=2, units=[dict(unit_id=101, ignore_moves=False)],
        selected_unit_id=101, war_prompt=prompt,
        war_display=dict(schema='civ6-host.xp2-world-war-display.v1',
            player_id=0, turn=TURN, defender_player_ids=[2], war_type=prompt['war_type'],
            targets=[dict(player_id=2, display_name='Target', icon_name='ICON')],
            message='Declare war?', consequences='Fixture consequences',
            buttons=[dict(accept=False, text='Cancel'), dict(accept=True, text='Confirm')],
            static_text=dict(title='War', warmonger_heading='Warmonger'),
            source_sha256=PIN))
    candidates = [dict(candidate_id=network_turn.digest(action), action=action)
                  for action in xp2_war_confirmation.actions(prompt, 0)]
    return seal(dict(schema=network_turn.WORLD_WAR_DECISIONS_SCHEMA,
        episode_id=identity.episode_id, game_generation=identity.game_generation,
        sequence=sequence, player_id=0, turn=TURN,
        turn_controls=dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=0,
            turn=TURN, active=True, active_complete=True, can_unready=False,
            timer_elapsed=None),
        complete_action_space=False, world_input=world_input, candidates=candidates))


class WarTranscriptBackend:
    def __init__(self, *, protocol_pin=PIN):
        self.protocol_pin = protocol_pin
        self.calls = []
        self.aborts = []

    def _response(self, operation, sequence, *, decisions, requested=None):
        identity = self.identity
        native = dict(schema='civ6rl.native_victory_episode.observation.v1',
            episode_id=identity.episode_id, game_generation=identity.game_generation,
            policy_id=POLICY_ID, player_id=0,
            observation_only=True, eligible_for_training=False, exposed_to_learner=False,
            global_engine_terminal=None, engine_halted=None,
            episode_terminated=False, winner_present=False, current_game_turn=TURN,
            **result_provenance(self.protocol.core_sha256))
        result = outcome(native, 0, self.protocol.limit, closed=operation == 'close')
        obs = None if decisions is None else observation()
        return dict(stage='official_session_response', schema=SCHEMA,
            nonce=self.protocol.nonce, episode_id=identity.episode_id,
            game_generation=identity.game_generation, sequence=sequence,
            operation=operation, observation=obs, rounds=0, outcome=result,
            automatic_choices_applied=False, action_interface_complete=False,
            strategic_training_ready=False, decisions=decisions,
            applied_action=requested if operation == 'act' else None,
            session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS',
                turn=TURN, local_player_id=0, human_player_ids=[0],
                active_human_player_ids=[0]),
            command_result=dict(status='completed' if operation == 'act' else 'none',
                reason=None, requested_action=requested if operation == 'act' else None))

    def reset(self):
        episode = str(uuid4())
        self.identity = DiagnosticEpisodeIdentity(episode, 'native-' + episode)
        self.protocol = NetworkProtocol(self.identity, 'c' * 32, initial_turn=TURN,
            war_source_sha256=self.protocol_pin)
        response = self._response('reset', 0, decisions=normal_catalogue(self.identity, 0))
        validate_network_response(response, self.protocol, 'reset')
        self.protocol.accept_response(response)
        return response

    def request(self, request):
        self.calls.append(copy.deepcopy(request))
        operation = self.protocol.validate(request)
        selected = self.protocol.selected(request) if operation == 'act' else None
        if operation == 'observe':
            decisions = modal_catalogue(self.identity, request['sequence'])
        elif operation == 'act':
            decisions = normal_catalogue(self.identity, request['sequence'])
        else:
            decisions = self.protocol.catalogues[request['player_id']]
        response = self._response(operation, request['sequence'],
            decisions=decisions, requested=selected)
        validate_network_response(response, self.protocol, operation, request=request)
        self.protocol.commit_reply(request, response)
        self.protocol.accept_response(response)
        return response

    def abort(self, reason):
        self.aborts.append(reason)


class WorldWarSessionFlowTests(unittest.TestCase):
    def test_normal_modal_decline_or_accept_normal_transcript(self):
        for accept in (False, True):
            with self.subTest(accept=accept):
                backend = WarTranscriptBackend()
                client = SessionClient(backend, war_source_sha256=PIN)
                first = client.reset()
                self.assertEqual(first['decisions']['schema'], network_turn.CAPABILITY_SCHEMA)
                modal_view = client.observe(0)
                self.assertEqual(modal_view['decisions']['schema'],
                                 network_turn.WORLD_WAR_DECISIONS_SCHEMA)
                row = modal_view['decisions']['candidates'][int(accept)]
                normal_view = client.act(0, modal_view['decisions']['decision_id'],
                                         row['candidate_id'])
                self.assertEqual(normal_view['decisions']['schema'], network_turn.CAPABILITY_SCHEMA)
                expected = {'kind': 'world_war_response', 'accept': accept}
                self.assertEqual(backend.calls[-1]['selection'], dict(
                    decision_id=modal_view['decisions']['decision_id'],
                    candidate_id=row['candidate_id']))
                self.assertEqual(client.command_result['requested_action'], expected)
                self.assertEqual(normal_view['applied_action'], expected)

    def test_absent_or_wrong_source_pin_refuses_modal(self):
        for client_pin, protocol_pin in ((None, PIN), ('d' * 64, PIN), (PIN, None)):
            with self.subTest(client_pin=client_pin, protocol_pin=protocol_pin):
                backend = WarTranscriptBackend(protocol_pin=protocol_pin)
                client = SessionClient(backend, war_source_sha256=client_pin)
                client.reset()
                with self.assertRaises(ValueError):
                    client.observe(0)
                self.assertTrue(backend.aborts)

    def test_client_rejects_stale_candidate_and_extra_parameters_locally(self):
        backend = WarTranscriptBackend()
        client = SessionClient(backend, war_source_sha256=PIN)
        client.reset()
        view = client.observe(0)
        decisions = view['decisions']
        with self.assertRaisesRegex(ProtocolError, 'Stale decision'):
            client.act(0, 'stale-decision', decisions['candidates'][0]['candidate_id'])
        with self.assertRaisesRegex(ProtocolError, 'Candidate is absent'):
            client.act(0, decisions['decision_id'], 'stale-candidate')
        for bad_parameters in ({'accept': True}, {'unexpected': 1}):
            with self.subTest(parameters=bad_parameters), self.assertRaisesRegex(
                    ProtocolError, 'no additional parameters'):
                client.act(0, decisions['decision_id'],
                           decisions['candidates'][0]['candidate_id'], bad_parameters)
        self.assertEqual(len(backend.calls), 1)

    def test_protocol_rejects_extra_selection_fields_and_invalid_pin(self):
        with self.assertRaisesRegex(ValueError, 'lowercase SHA-256'):
            episode = str(uuid4())
            NetworkProtocol(DiagnosticEpisodeIdentity(episode, 'native-' + episode), 'x' * 32,
                            war_source_sha256='A' * 64)
        backend = WarTranscriptBackend()
        client = SessionClient(backend, war_source_sha256=PIN)
        client.reset()
        view = client.observe(0)
        request = dict(schema=SCHEMA, nonce=backend.protocol.nonce,
            episode_id=backend.identity.episode_id,
            game_generation=backend.identity.game_generation,
            sequence=backend.protocol.sequence + 1, operation='act', player_id=0,
            selection=dict(decision_id=view['decisions']['decision_id'],
                candidate_id=view['decisions']['candidates'][0]['candidate_id'],
                parameters={'accept': False}))
        with self.assertRaisesRegex(ValueError, 'Malformed or stale world-war modal'):
            backend.protocol.selected(request)
        request['selection'] = dict(decision_id=view['decisions']['decision_id'],
                                    candidate_id='stale-candidate')
        with self.assertRaisesRegex(ValueError, 'absent from the current modal'):
            backend.protocol.selected(request)


if __name__ == '__main__':
    unittest.main()

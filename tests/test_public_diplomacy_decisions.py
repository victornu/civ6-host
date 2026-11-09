import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from civ6_host.contracts import diplomacy_decisions as public_diplomacy
from civ6_host.contracts import network_turn
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.native.native_victory_episode import POLICY_ID, PROOF_SHA256
from civ6_host.runtime.native.native_episode_facts import PROOF_SHA256 as FACTS_SHA
from civ6_host.runtime.network_protocol import SCHEMA as NETWORK_SCHEMA
from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
from civ6_host.session_client import SCHEMA as SESSION_SCHEMA, SessionClient
from civ6_host.client import _digest


def observation(player=0, turn=10):
    return dict(schema='civ6rl-player-observation-v1', player_id=player,
        turn=turn, width=1, height=1, plots=[], units=[], visible_enemy_units=[],
        cities=[], economy=dict(science=0, culture=0, gold=0, faith=0))


def player_map(obs):
    return dict(schema='civ6rl.saved_player_map933.v1', player_id=obs['player_id'],
        turn=obs['turn'], width=obs['width'], height=obs['height'], plots=[],
        visible_observation_id=_digest(obs), source='official_plot_tooltip_revealed_live_getters',
        historical_memory_proven=False, graphical_differential_proven=False,
        complete_player_observation=False)


def controls(player=0, *, active=False):
    return dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=player, turn=10,
        active=active, active_complete=False, can_unready=False, timer_elapsed=False)


def private_catalogue(identity, sequence, obs, choices=None):
    choices = choices or [dict(key='CHOICE_EXIT', disabled=False)]
    statement_sequence = 12
    session_id = 7
    dialogue = dict(session_id=session_id, statement_sequence=statement_sequence,
        from_player=1, to_player=0)
    candidates = []
    for row in choices:
        if row['disabled']:
            continue
        action = dict(kind='diplomacy_response', session_id=session_id,
            statement_sequence=statement_sequence, choice=row['key'])
        candidates.append(dict(candidate_id=public_diplomacy.digest(action), action=action))
    native_choices = [dict(key=row['key'], sort=index, text=row['key'], tooltip=None,
        diplomatic_action_type=None, disabled=row['disabled'])
        for index, row in enumerate(choices)]
    return dict(schema=public_diplomacy.BASE_SCHEMA, episode_id=identity.episode_id,
        game_generation=identity.game_generation, sequence=sequence, player_id=obs['player_id'],
        turn=obs['turn'], origin_turn=obs['turn'], player_map=player_map(obs),
        statement=dict(event_sequence=statement_sequence, fields=dict(AiReason=123, OpaquePayload='secret')),
        data=dict(session=dict(player_id=0, **dialogue), selections=native_choices,
                  raw_ai_reason=123, opaque_payload='secret'),
        candidates=candidates, unsupported=['existing_unqualified_family'],
        complete_action_space=False, source_sha256='private-source', ui_support_sha256='private-ui')


def public_catalogue(identity, sequence=0, *, obs=None, controls_value=None,
                     choices=None, display=None, closed=False):
    obs = obs or observation()
    return public_diplomacy.build(identity, sequence, obs,
        controls_value or controls(obs['player_id']),
        private_catalogue(identity, sequence, obs, choices),
        public_display=display,
        display_source_sha256=(public_diplomacy.PUBLIC_DISPLAY_SOURCE_SHA256
                               if display is not None else None),
        actions_closed=closed)


def public_display(choices):
    return dict(schema='civ6rl.diplomacy_public_display986.v2',
        speaker_leader='LEADER_TEST', statement_text='The treaty is refused.',
        reason_text='', selections=[dict(key=row['key'], text=row['key'],
            disabled=row['disabled'], tooltip=None) for row in choices])


class PublicDiplomacyContractTests(unittest.TestCase):
    def setUp(self):
        episode = str(uuid4())
        self.identity = DiagnosticEpisodeIdentity(episode, 'native-' + episode)
        self.obs = observation()

    def test_build_redacts_private_fields_and_validates_public_display(self):
        choices = [dict(key='CHOICE_POSITIVE', disabled=False),
                   dict(key='CHOICE_EXIT', disabled=True)]
        value = public_catalogue(self.identity, choices=choices,
                                 display=public_display(choices))
        self.assertEqual(value['schema'], public_diplomacy.SCHEMA)
        self.assertEqual(value['choices'], choices)
        self.assertEqual(value['public_display_source_sha256'],
                         public_diplomacy.PUBLIC_DISPLAY_SOURCE_SHA256)
        for private in ('statement', 'data', 'source_sha256', 'ui_support_sha256'):
            self.assertNotIn(private, value)
        self.assertNotIn(public_diplomacy.PUBLIC_DISPLAY_GAP, value['unsupported'])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs)

    def test_missing_display_requires_explicit_gap_marker(self):
        value = public_catalogue(self.identity)
        self.assertIsNone(value['public_display'])
        self.assertIsNone(value['public_display_source_sha256'])
        self.assertIn(public_diplomacy.PUBLIC_DISPLAY_GAP, value['unsupported'])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs)

    def test_closed_catalogue_has_no_candidates(self):
        value = public_catalogue(self.identity, closed=True)
        self.assertEqual(value['candidates'], [])
        network_turn.validate_catalogue(value, self.identity, 0, 10, player_id=0,
            observation=self.obs, actions_closed=True)

    def test_validator_rejects_private_fields_stale_identity_and_wrong_source(self):
        original = public_catalogue(self.identity, display=public_display(
            [dict(key='CHOICE_EXIT', disabled=False)]))
        cases = []
        extra = copy.deepcopy(original); extra['statement'] = {'AiReason': 8}; cases.append(extra)
        stale = copy.deepcopy(original); stale['dialogue']['session_id'] += 1
        stale['decision_id'] = public_diplomacy.digest({k:v for k,v in stale.items() if k!='decision_id'}); cases.append(stale)
        wrong_statement = copy.deepcopy(original); wrong_statement['statement_source_sha256'] = 'f' * 64
        wrong_statement['decision_id'] = public_diplomacy.digest({k:v for k,v in wrong_statement.items() if k!='decision_id'}); cases.append(wrong_statement)
        wrong_display = copy.deepcopy(original); wrong_display['public_display_source_sha256'] = 'f' * 64
        wrong_display['decision_id'] = public_diplomacy.digest({k:v for k,v in wrong_display.items() if k!='decision_id'}); cases.append(wrong_display)
        changed_display = copy.deepcopy(original); changed_display['public_display']['selections'][0]['key'] = 'CHOICE_POSITIVE'
        changed_display['decision_id'] = public_diplomacy.digest({k:v for k,v in changed_display.items() if k!='decision_id'}); cases.append(changed_display)
        wrong_choice = copy.deepcopy(original); wrong_choice['candidates'][0]['action']['choice'] = 'CHOICE_POSITIVE'
        wrong_choice['candidates'][0]['candidate_id'] = public_diplomacy.digest(wrong_choice['candidates'][0]['action'])
        wrong_choice['decision_id'] = public_diplomacy.digest({k:v for k,v in wrong_choice.items() if k!='decision_id'}); cases.append(wrong_choice)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    network_turn.validate_catalogue(value, self.identity, 0, 10,
                        player_id=0, observation=self.obs)
        with self.assertRaisesRegex(ValueError, 'sequence'):
            network_turn.validate_catalogue(original, self.identity, 1, 10,
                player_id=0, observation=self.obs)
        missing_gap = public_catalogue(self.identity)
        missing_gap['unsupported'].remove(public_diplomacy.PUBLIC_DISPLAY_GAP)
        missing_gap['decision_id'] = public_diplomacy.digest(
            {k:v for k,v in missing_gap.items() if k!='decision_id'})
        with self.assertRaisesRegex(ValueError, 'marked unqualified'):
            network_turn.validate_catalogue(missing_gap, self.identity, 0, 10,
                player_id=0, observation=self.obs)

    def test_public_reply_composes_with_network_protocol_and_inactive_act(self):
        protocol, response = self._network_fixture()
        with patch('civ6_host.runtime.network_protocol.player_map.validate'):
            validate_network_response(response, protocol, 'reset')
            protocol.accept_response(response)
            action = protocol.catalogues[0]['candidates'][0]['action']
            request = dict(schema=NETWORK_SCHEMA, nonce=protocol.nonce,
                episode_id=self.identity.episode_id,
                game_generation=self.identity.game_generation, sequence=1,
                operation='act', player_id=0,
                selection=dict(decision_id=protocol.catalogues[0]['decision_id'],
                    candidate_id=protocol.catalogues[0]['candidates'][0]['candidate_id']))
            self.assertEqual(protocol.validate(request), 'act')
            self.assertEqual(protocol.selected(request), action)
            reply = self._network_reply(protocol, 'act', 1, status='refused', selected=action)
            validate_network_response(reply, protocol, 'act', request=request)

    def _network_fixture(self):
        protocol = NetworkProtocol(self.identity, 'a' * 32, initial_turn=10)
        return protocol, self._network_reply(protocol, 'reset', 0)

    def _network_reply(self, protocol, operation, sequence, *, status='none', selected=None):
        obs = dict(player_id=0, turn=10)
        decisions = public_catalogue(self.identity, sequence, obs=self.obs,
            controls_value=controls(active=False))
        native = dict(schema='civ6rl.native_victory_episode.observation.v1',
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            policy_id=POLICY_ID, source_proof_sha256=PROOF_SHA256,
            facts_source_proof_sha256=FACTS_SHA, player_id=0,
            observation_only=True, eligible_for_training=False, exposed_to_learner=False,
            global_engine_terminal=None, engine_halted=None, episode_terminated=False,
            winner_present=False, current_game_turn=10)
        requested = selected if operation == 'act' else None
        return dict(stage='official_session_response', schema=NETWORK_SCHEMA,
            nonce=protocol.nonce, episode_id=self.identity.episode_id,
            game_generation=self.identity.game_generation, sequence=sequence,
            operation=operation, observation=obs, rounds=0,
            outcome=outcome(native, 0, protocol.limit), automatic_choices_applied=False,
            action_interface_complete=False, strategic_training_ready=False,
            decisions=decisions, applied_action=None, session=dict(game_mode='LAN',
                turn_phase='TURNPHASE_SIMULTANEOUS', turn=10, local_player_id=0,
                human_player_ids=[0], active_human_player_ids=[]),
            command_result=dict(status=status, reason=None, requested_action=requested))

    def test_session_client_reset_and_inactive_dialogue_response(self):
        class Backend:
            def __init__(self):
                self.episode = None
                self.nonce = None
                self.sequence = 0
                self.aborts = []

            def _reply(self, operation, sequence, action=None):
                current = SimpleNamespace(episode_id=self.episode,
                    game_generation='native-' + self.episode)
                return self_owner._client_reply(self, current, operation, sequence, action)

            def reset(self):
                self.episode = str(uuid4()); self.nonce = uuid4().hex
                return self._reply('reset', 0)

            def request(self, request):
                self.sequence = request['sequence']
                prior = client._views[request['player_id']]['decisions']
                action = next(row['action'] for row in prior['candidates']
                    if row['candidate_id'] == request['selection']['candidate_id'])
                return self._reply('act', self.sequence, action)

            def abort(self, reason):
                self.aborts.append(reason)

        self_owner = self
        backend = Backend()
        client = SessionClient(backend)
        initial = client.reset()
        action = initial['decisions']['candidates'][0]['action']
        result = client.act(0, initial['decisions']['decision_id'],
                            initial['decisions']['candidates'][0]['candidate_id'])
        self.assertEqual(result['decisions']['schema'], public_diplomacy.SCHEMA)
        self.assertEqual(backend.aborts, [])

    def _client_reply(self, backend, identity, operation, sequence, action=None):
        obs = observation()
        decisions = public_catalogue(identity, sequence, obs=obs,
            controls_value=controls(active=False))
        return dict(stage='official_session_response', schema=SESSION_SCHEMA,
            nonce=backend.nonce, episode_id=backend.episode,
            game_generation='native-' + backend.episode, sequence=sequence,
            operation=operation, observation=obs, rounds=0,
            outcome=dict(terminated=False, truncated=False, reason=None),
            automatic_choices_applied=False, action_interface_complete=False,
            strategic_training_ready=False, decisions=decisions, applied_action=None,
            session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=10,
                local_player_id=0, human_player_ids=[0], active_human_player_ids=[]),
            command_result=dict(status='refused' if action else 'none', reason=None,
                requested_action=action))

    def test_remote_client_validates_public_dialogue_without_native_resources(self):
        backend=SimpleNamespace(episode=self.identity.episode_id,nonce='a'*32)
        reply=self._client_reply(backend,self.identity,'reset',0)
        environment=dict(os.environ)
        for key in tuple(environment):
            if key.startswith(('CIV6_HOST_','CIV6RL_')):environment.pop(key)
        environment['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        code='''import json,sys
from civ6_host.session_client import SessionClient
class Backend:
 def reset(self):return json.load(sys.stdin)
 def abort(self,reason):raise AssertionError(reason)
view=SessionClient(Backend()).reset()
assert view['decisions']['schema']=='civ6-host.network-diplomacy-decisions.v1'
assert not any(name.startswith('civ6_host.runtime') for name in sys.modules)
'''
        result=subprocess.run([sys.executable,'-P','-c',code],env=environment,
            input=json.dumps(reply),text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()

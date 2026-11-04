import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.native.native_victory_episode import POLICY_ID, PROOF_SHA256
from civ6_host.runtime.native.native_episode_facts import PROOF_SHA256 as FACTS_SHA
from civ6_host.runtime.network_protocol import CLOSURE_SCHEMA, SCHEMA, NetworkProtocol
from civ6_host.runtime.network_protocol import validate_network_response
from civ6_host.contracts import network_turn


class NetworkProtocolTests(unittest.TestCase):
    def setUp(self):
        episode = str(uuid4())
        self.identity = DiagnosticEpisodeIdentity(episode, 'native-' + episode)
        self.protocol = NetworkProtocol(self.identity, 'a' * 32, initial_turn=10)
        self._patchers = [
            patch('civ6_host.runtime.network_protocol.validate_decisions'),
            patch('civ6_host.runtime.network_protocol._public_contracts'),
            patch('civ6_host.runtime.network_protocol.player_map.validate'),
        ]
        # The catalogue fixture exercises transport identity and choice routing;
        # it deliberately does not claim native catalogue qualification.
        self._patchers[0].start()
        self._public_contracts = self._patchers[1].start()
        self._patchers[2].start()
        self.addCleanup(self._stop_patches)

    def _stop_patches(self):
        for patcher in self._patchers:
            patcher.stop()

    def _native(self, *, turn=10, player=0):
        return dict(schema='civ6rl.native_victory_episode.observation.v1',
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            policy_id=POLICY_ID, source_proof_sha256=PROOF_SHA256,
            facts_source_proof_sha256=FACTS_SHA, player_id=player,
            observation_only=True, eligible_for_training=False, exposed_to_learner=False,
            global_engine_terminal=None, engine_halted=None,
            episode_terminated=False, winner_present=False, current_game_turn=turn)

    def _controls(self, player, *, active=True, active_complete=True,
                  can_unready=False, timer_elapsed=False):
        return dict(schema=network_turn.TURN_CONTROLS_SCHEMA, player_id=player,
            turn=10, active=active, active_complete=active_complete,
            can_unready=can_unready, timer_elapsed=timer_elapsed)

    def _catalogue(self, player, sequence, *, kind='move', controls=None):
        action = {'kind': kind, 'unit_id': player}
        base = dict(schema='fixture-only', episode_id=self.identity.episode_id,
            game_generation=self.identity.game_generation, sequence=sequence,
            player_id=player, turn=10, player_map={},
            candidates=[dict(candidate_id=f'candidate-{player}', action=action)],
            unsupported=[], complete_action_space=False)
        base['decision_id'] = network_turn.digest(base)
        wrapper = {key: value for key, value in base.items() if key != 'decision_id'}
        wrapper.update(schema=network_turn.SCHEMA, base_schema=base['schema'],
                       turn_controls=controls or self._controls(player))
        wrapper['decision_id'] = network_turn.digest(wrapper)
        return wrapper

    def _waiting_catalogue(self, player, sequence, *, controls):
        candidates = []
        if network_turn.unready_action_available(controls):
            action = {'kind': 'unready_turn'}
            candidates.append(dict(candidate_id=network_turn.digest(action), action=action))
        value = dict(schema=network_turn.SCHEMA, base_schema=None,
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            sequence=sequence, player_id=player, turn=10, player_map={},
            candidates=candidates, turn_controls=controls, unsupported=[],
            complete_action_space=False)
        value['decision_id'] = network_turn.digest(value)
        return value

    def _reply(self, operation, sequence, player, *, status='none', selected=None,
               turn=10, session_turn=None, controls=None, active_humans=None,
               waiting=False):
        session_turn = turn if session_turn is None else session_turn
        native = self._native(turn=session_turn, player=player)
        rounds = session_turn - self.protocol.initial_turn
        result = outcome(native, rounds, self.protocol.limit)
        if operation == 'close':
            decisions = None
        elif waiting:
            decisions = self._waiting_catalogue(player, sequence,
                controls=controls or self._controls(player, active=False,
                    active_complete=False, can_unready=False))
        else:
            decisions = self._catalogue(player, sequence, controls=controls)
        observation = dict(player_id=player, turn=session_turn) if decisions is not None else None
        requested = selected if operation == 'act' else None
        applied = selected if operation == 'act' and status == 'completed' else None
        return dict(stage='official_session_response', schema=SCHEMA, nonce=self.protocol.nonce,
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            sequence=sequence, operation=operation, observation=observation, rounds=rounds,
            outcome=result, automatic_choices_applied=False, action_interface_complete=False,
            strategic_training_ready=False, decisions=decisions, applied_action=applied,
            session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=session_turn,
                local_player_id=0, human_player_ids=[0, 1],
                active_human_player_ids=active_humans or [0, 1]),
            command_result=dict(status=status, reason=None, requested_action=requested))

    def _accept_initial(self):
        response = self._reply('reset', 0, 0)
        validate_network_response(response, self.protocol, 'reset')
        self.protocol.accept_response(response)
        return response

    def _request(self, operation, sequence, player, selection=None):
        request = dict(schema=SCHEMA, nonce=self.protocol.nonce,
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            sequence=sequence, operation=operation, player_id=player)
        if selection is not None:
            request['selection'] = selection
        return request

    def test_same_turn_observation_keeps_other_players_catalogue(self):
        self._accept_initial()
        response_b = self._reply('observe', 1, 1)
        request_b = self._request('observe', 1, 1)
        validate_network_response(response_b, self.protocol, 'observe', request=request_b)
        self.protocol.commit_reply(request_b, response_b)
        self.protocol.accept_response(response_b)

        request_a = self._request('act', 2, 0,
            dict(decision_id=self.protocol.catalogues[0]['decision_id'],
                 candidate_id=self.protocol.catalogues[0]['candidates'][0]['candidate_id']))
        self.assertEqual(self.protocol.validate(request_a), 'act')
        selected = {'kind': 'move', 'unit_id': 0}
        response_a = self._reply('act', 2, 0, status='completed', selected=selected)
        validate_network_response(response_a, self.protocol, 'act', request=request_a)
        self.protocol.commit_reply(request_a, response_a)
        self.protocol.accept_response(response_a)
        self.assertEqual(self.protocol.catalogues[1]['decision_id'],
                         network_turn.digest({key: value for key, value in
                             self.protocol.catalogues[1].items() if key != 'decision_id'}))

    def test_initial_diplomacy_uses_wrapper_offer_not_legacy_action_substitution(self):
        from test_diplomacy_overview_contract import fixture
        from civ6_host.contracts.diplomacy_overview import candidates
        response = self._reply('reset',0,0)
        data = fixture();data['turn']=10
        catalogue=response['decisions'];catalogue['diplomacy_overview']=data
        action=candidates(data)[0]
        catalogue['candidates'].append(dict(candidate_id=network_turn.digest(action),action=action))
        catalogue['decision_id']=network_turn.digest({k:v for k,v in catalogue.items() if k!='decision_id'})
        validate_network_response(response,self.protocol,'reset')
        self.protocol.accept_response(response)
        request=self._request('act',1,0,dict(decision_id=catalogue['decision_id'],
                                            candidate_id=network_turn.digest(action)))
        self.assertEqual(self.protocol.selected(request),action)
        request['selection']['parameters']={}
        with self.assertRaises(ValueError):self.protocol.selected(request)

    def test_actor_and_active_human_guards(self):
        self._accept_initial()
        with self.assertRaises(ValueError):
            self.protocol.validate(self._request('observe', 1, 2))
        response = self._reply('observe', 1, 1)
        request = self._request('observe', 1, 1)
        validate_network_response(response, self.protocol, 'observe', request=request)
        self.protocol.accept_response(response)
        self.protocol.session['active_human_player_ids'] = [0]
        with self.assertRaises(ValueError):
            self.protocol.validate(self._request('act', 1, 1,
                dict(decision_id=self.protocol.catalogues[1]['decision_id'],
                     candidate_id=self.protocol.catalogues[1]['candidates'][0]['candidate_id'])))

    def test_action_reply_must_echo_selection_and_applied_action(self):
        self._accept_initial()
        request = self._request('act', 1, 0,
            dict(decision_id=self.protocol.catalogues[0]['decision_id'],
                 candidate_id=self.protocol.catalogues[0]['candidates'][0]['candidate_id']))
        response = self._reply('act', 1, 0, status='completed',
                               selected={'kind': 'move', 'unit_id': 9})
        with self.assertRaises(ValueError):
            validate_network_response(response, self.protocol, 'act', request=request)
        for field in ('requested_action', 'applied_action'):
            with self.subTest(field=field):
                response = self._reply('act', 1, 0, status='completed',
                                       selected={'kind': 'move', 'unit_id': 0})
                altered = {'kind': 'move', 'unit_id': False}
                if field == 'requested_action':
                    response['command_result'][field] = altered
                else:
                    response[field] = altered
                with self.assertRaisesRegex(ValueError, 'action differs'):
                    validate_network_response(response, self.protocol, 'act', request=request)

    def test_policy_action_uses_action_protocol_expansion(self):
        self._accept_initial()
        catalogue = self._catalogue(0, 0, kind='policies')
        legacy = network_turn.validate_catalogue(catalogue, self.identity, 0, 10,
            player_id=0)
        legacy['candidates'][0]['action'] = {'kind': 'policies', 'slots': []}
        legacy['candidates'][0]['candidate_id'] = network_turn.digest(
            legacy['candidates'][0]['action'])
        legacy['decision_id'] = network_turn.digest({key: value for key, value in
            legacy.items() if key != 'decision_id'})
        catalogue = {key: value for key, value in legacy.items() if key != 'decision_id'}
        catalogue.update(base_schema=legacy['schema'], schema=network_turn.SCHEMA,
                         turn_controls=self._controls(0))
        catalogue['decision_id'] = network_turn.digest(catalogue)
        self.protocol.catalogues[0] = catalogue
        request = self._request('act', 1, 0,
            dict(decision_id=catalogue['decision_id'],
                 candidate_id=catalogue['candidates'][0]['candidate_id'],
                 parameters={'assignments': {'0': 7}}))
        with patch('civ6_host.runtime.native.native_action_session.policies.choose',
                   return_value={'kind': 'policies', 'candidate': {'assignments': {'0': 7}}}):
            self.assertEqual(self.protocol.selected(request),
                {'kind': 'policies', 'candidate': {'kind': 'policies',
                    'candidate': {'assignments': {'0': 7}}}})

    def test_schema_constants_and_exact_request_fields(self):
        self.assertEqual(SCHEMA, 'civ6-host.session.v1')
        self.assertEqual(CLOSURE_SCHEMA, 'civ6-host.session.closure.v1')
        self._accept_initial()
        malformed = self._request('observe', 1, 0)
        malformed['ignored'] = True
        with self.assertRaises(ValueError):
            self.protocol.validate(malformed)

    def test_reset_is_only_the_initial_sequence_zero_response(self):
        response = self._reply('reset', 0, 0)
        validate_network_response(response, self.protocol, 'reset')
        with self.assertRaises(ValueError):
            validate_network_response(response, self.protocol, 'reset',
                request=self._request('observe', 1, 0))
        self.protocol.accept_response(response)
        self.assertEqual(self.protocol.sequence, 0)

    def test_failed_reply_validation_preserves_cached_actor_catalogue(self):
        self._accept_initial()
        request = self._request('act', 1, 0,
            dict(decision_id=self.protocol.catalogues[0]['decision_id'],
                 candidate_id=self.protocol.catalogues[0]['candidates'][0]['candidate_id']))
        response = self._reply('act', 1, 0, status='completed',
                               selected={'kind': 'move', 'unit_id': 99})
        with self.assertRaises(ValueError):
            self.protocol.commit_reply(request, response)
        self.assertEqual(self.protocol.sequence, 0)
        self.assertEqual(self.protocol.catalogues[0]['decision_id'],
                         network_turn.digest({key: value for key, value in
                             self.protocol.catalogues[0].items() if key != 'decision_id'}))

    def test_inactive_human_can_only_submit_available_unready(self):
        self._accept_initial()
        controls = self._controls(1, active=False, active_complete=False,
                                  can_unready=True, timer_elapsed=False)
        response = self._reply('observe', 1, 1, controls=controls,
                               active_humans=[0], waiting=True)
        request = self._request('observe', 1, 1)
        validate_network_response(response, self.protocol, 'observe', request=request)
        self.protocol.commit_reply(request, response)
        self.protocol.accept_response(response)

        catalogue = self.protocol.catalogues[1]
        unready = catalogue['candidates'][0]
        action_request = self._request('act', 2, 1, dict(
            decision_id=catalogue['decision_id'], candidate_id=unready['candidate_id']))
        self.assertEqual(self.protocol.validate(action_request), 'act')
        self.assertEqual(self.protocol.selected(action_request), {'kind': 'unready_turn'})

    def test_unready_requires_can_unready_and_nonelapsed_timer(self):
        controls = self._controls(1, active=False, active_complete=False,
                                  can_unready=False, timer_elapsed=False)
        catalogue = self._waiting_catalogue(1, 0, controls=controls)
        self.assertIsNone(network_turn.validate_catalogue(catalogue, self.identity, 0, 10,
            player_id=1))

        bad = dict(catalogue)
        action = {'kind': 'unready_turn'}
        bad['candidates'] = [dict(candidate_id=network_turn.digest(action), action=action)]
        bad['decision_id'] = network_turn.digest({key: value for key, value in
            bad.items() if key != 'decision_id'})
        with self.assertRaises(ValueError):
            network_turn.validate_catalogue(bad, self.identity, 0, 10, player_id=1)

        elapsed = self._controls(1, active=False, active_complete=False,
                                 can_unready=True, timer_elapsed=True)
        self.assertFalse(network_turn.unready_action_available(elapsed))

    def test_network_catalogue_digest_is_checked(self):
        catalogue = self._catalogue(0, 0)
        catalogue['turn_controls']['active_complete'] = False
        with self.assertRaises(ValueError):
            network_turn.validate_catalogue(catalogue, self.identity, 0, 10,
                player_id=0)

    def test_active_catalogue_cannot_smuggle_unready(self):
        catalogue = self._catalogue(0, 0)
        action = {'kind': 'unready_turn'}
        catalogue['candidates'].append(dict(candidate_id=network_turn.digest(action), action=action))
        catalogue['decision_id'] = network_turn.digest({k:v for k,v in catalogue.items() if k != 'decision_id'})
        with self.assertRaises(ValueError):
            network_turn.validate_catalogue(catalogue, self.identity, 0, 10, player_id=0)

    def test_response_activity_must_match_session(self):
        response = self._reply('reset', 0, 0)
        response['session']['active_human_player_ids'] = [1]
        with self.assertRaisesRegex(ValueError, 'activity differs'):
            validate_network_response(response, self.protocol, 'reset')

    def test_result_actor_is_bound_even_without_a_board(self):
        self._accept_initial()
        request=self._request('poll',1,0)
        response=self._reply('poll',1,0)
        native=response['outcome']['native_victory']
        native.update(episode_terminated=True,winner_present=True,team_id=0,
            is_alive=True,was_ever_alive=True,winning_team=1,victory_type=3,
            winner_matches_player_team=False)
        response['outcome']=outcome(native,0,self.protocol.limit)
        response['observation']=response['decisions']=None
        validate_network_response(response,self.protocol,'poll',request=request)
        native['player_id']=1
        with self.assertRaisesRegex(ValueError,'Native victory identity'):
            validate_network_response(response,self.protocol,'poll',request=request)

    def test_terminal_reply_removes_catalogues_and_allows_only_close(self):
        self._accept_initial()
        request=self._request('poll',1,0)
        response=self._reply('poll',1,0)
        native=response['outcome']['native_victory']
        native.update(episode_terminated=True,winner_present=True,team_id=0,
            is_alive=True,was_ever_alive=True,winning_team=0,victory_type=0,
            winner_matches_player_team=True)
        response['outcome']=outcome(native,0,self.protocol.limit)
        response['observation']=response['decisions']=None
        self.protocol.commit_reply(request,response)
        self.protocol.accept_response(response)
        self.assertTrue(self.protocol.ended)
        self.assertEqual(self.protocol.catalogues,{})
        with self.assertRaisesRegex(ValueError,'Session ended'):
            self.protocol.validate(self._request('observe',2,0))
        close = self._request('close',2,0)
        self.assertEqual(self.protocol.validate(close),'close')
        closed = self._reply('close',2,0)
        closed['outcome'] = outcome(closed['outcome']['native_victory'], 0,
                                    self.protocol.limit, closed=True)
        with self.assertRaisesRegex(ValueError, 'Official result disappeared'):
            validate_network_response(closed, self.protocol, 'close', request=close)

    def test_global_winner_can_coexist_with_refused_action_without_applied_claim(self):
        self._accept_initial()
        catalogue=self.protocol.catalogues[0]
        selected=catalogue['candidates'][0]
        request=self._request('act',1,0,dict(decision_id=catalogue['decision_id'],
            candidate_id=selected['candidate_id']))
        response=self._reply('act',1,0,status='refused',selected=selected['action'])
        native=response['outcome']['native_victory']
        native.update(episode_terminated=True,winner_present=True,team_id=0,
            is_alive=True,was_ever_alive=True,winning_team=1,victory_type=3,
            winner_matches_player_team=False)
        response['outcome']=outcome(native,0,self.protocol.limit)
        response['observation']=response['decisions']=None
        validate_network_response(response,self.protocol,'act',request=request)
        response['applied_action']=selected['action']
        with self.assertRaisesRegex(ValueError,'Host claimed an action'):
            validate_network_response(response,self.protocol,'act',request=request)


if __name__ == '__main__':
    unittest.main()

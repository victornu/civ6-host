"""Synthetic v33 wire tests over a retained public v31 native replay."""
from copy import deepcopy
import unittest

from civ6_host.contracts import diplomacy_overview, information, network_turn

XP2_CORE = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
UNQUALIFIED_INITIAL = ['deal_screens_and_non_direct_initial_choices']


class InitialDiplomacyCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_governor_capabilities import GovernorCapabilityTests
        GovernorCapabilityTests.setUpClass()
        cls.fixture_class = GovernorCapabilityTests

    def _fixture(self):
        return self.fixture_class('test_v31_still_valid_without_governors_and_v32_requires_active_query')

    def _overview(self, *, player_id=0, turn=8, paused=False, rows=None):
        return dict(schema=diplomacy_overview.SCHEMA, player_id=player_id, turn=turn,
                    capability=True, paused=paused,
                    targets=[dict(player_id=2, selections=list(rows or ()))],
                    complete_action_space=False)

    def _active_v33(self, rows=None, *, sequence=None):
        fixture = self._fixture()
        value, observation, _ = fixture.v32()
        value['schema'] = network_turn.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA
        if sequence is not None:
            value['sequence'] = sequence
        overview = self._overview(player_id=value['player_id'], turn=value['turn'], rows=rows or [
            self._selection('CHOICE_DECLARE_FORMAL_WAR'),
            self._selection('CHOICE_MAKE_DEAL', supported=False),
            self._selection('CHOICE_DECLARE_FRIENDSHIP', disabled=True),
            self._selection('CHOICE_DENOUNCE'),
        ])
        value['diplomacy_overview'] = overview
        actions = diplomacy_overview.candidates(overview)
        action_rows = [dict(action=action, candidate_id=network_turn.digest(action))
                       for action in actions]
        value['candidates'].extend(action_rows)
        value['families']['diplomacy_initiate'] = dict(
            status='queried_partial', candidate_ids=[row['candidate_id'] for row in action_rows],
            unqualified=list(UNQUALIFIED_INITIAL))
        value.pop('decision_id')
        value['decision_id'] = network_turn.digest(value)
        return value, observation

    @staticmethod
    def _selection(key, *, disabled=False, supported=True):
        return dict(key=key, disabled=disabled, supported=supported,
                    text='LOC_' + key, tooltip=None, diplomatic_action_type=None)

    def _validate(self, value, observation, *, actions_closed=False):
        fixture = self._fixture()
        return fixture.validate(value, observation, actions_closed=actions_closed)

    def _redigest(self, value):
        value.pop('decision_id', None)
        value['decision_id'] = network_turn.digest(value)

    def test_v33_preserves_v32_governor_superset_and_ordered_diplomacy_offers(self):
        value, observation = self._active_v33()
        self._validate(value, observation)
        self.assertIn('governors', value)
        self.assertIsNotNone(value['governors'])
        self.assertEqual(value['families']['diplomacy_initiate']['status'], 'queried_partial')
        self.assertEqual(value['families']['diplomacy_initiate']['unqualified'], UNQUALIFIED_INITIAL)
        overview = value['diplomacy_overview']
        rows = overview['targets'][0]['selections']
        self.assertEqual([row['key'] for row in rows], [
            'CHOICE_DECLARE_FORMAL_WAR', 'CHOICE_MAKE_DEAL',
            'CHOICE_DECLARE_FRIENDSHIP', 'CHOICE_DENOUNCE'])
        self.assertEqual([row['action'] for row in value['candidates']
                          if row['action']['kind'] == 'diplomacy_initiate'], [
            dict(kind='diplomacy_initiate', target_player_id=2,
                 choice='CHOICE_DECLARE_FORMAL_WAR'),
            dict(kind='diplomacy_initiate', target_player_id=2,
                 choice='CHOICE_DENOUNCE'),
        ])
        expected_ids = [network_turn.digest(row['action']) for row in value['candidates']
                        if row['action']['kind'] == 'diplomacy_initiate']
        self.assertEqual(value['families']['diplomacy_initiate']['candidate_ids'], expected_ids)
        self.assertFalse(rows[1]['supported'])
        self.assertTrue(rows[2]['disabled'])

    def test_wrong_participant_turn_extra_ai_payload_and_action_shape_are_rejected(self):
        value, observation = self._active_v33()
        for field, wrong in (('player_id', 3), ('turn', value['turn'] + 1)):
            bad = deepcopy(value)
            bad['diplomacy_overview'][field] = wrong
            self._redigest(bad)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self._validate(bad, observation)

        bad = deepcopy(value)
        bad['diplomacy_overview']['ai_payload'] = {'hidden': 'raw'}
        self._redigest(bad)
        with self.assertRaises(ValueError):
            self._validate(bad, observation)
        bad = deepcopy(value)
        bad['diplomacy_overview']['targets'][0]['selections'][0]['ai_payload'] = {'raw': 1}
        self._redigest(bad)
        with self.assertRaises(ValueError):
            self._validate(bad, observation)

        valid = dict(kind='diplomacy_initiate', target_player_id=2,
                     choice='CHOICE_DECLARE_FORMAL_WAR')
        self.assertEqual(diplomacy_overview.validate_action(valid), valid)
        for malformed in (dict(valid, private='raw'),
                          dict(kind='diplomacy_initiate', target_player_id=64,
                               choice='CHOICE_DECLARE_FORMAL_WAR')):
            with self.subTest(action=malformed), self.assertRaises(ValueError):
                diplomacy_overview.validate_action(malformed)

    def test_missing_extra_or_wrong_digest_candidate_and_wrong_family_gap_fail(self):
        value, observation = self._active_v33()
        candidate_indices = [i for i, row in enumerate(value['candidates'])
                             if row['action']['kind'] == 'diplomacy_initiate']
        missing = deepcopy(value)
        del missing['candidates'][candidate_indices[0]]
        missing['families']['diplomacy_initiate']['candidate_ids'].pop(0)
        self._redigest(missing)
        with self.assertRaises(ValueError):
            self._validate(missing, observation)

        extra = deepcopy(value)
        action = dict(kind='diplomacy_initiate', target_player_id=2,
                      choice='CHOICE_MAKE_DEAL')
        row = dict(action=action, candidate_id=network_turn.digest(action))
        extra['candidates'].append(row)
        extra['families']['diplomacy_initiate']['candidate_ids'].append(row['candidate_id'])
        self._redigest(extra)
        with self.assertRaises(ValueError):
            self._validate(extra, observation)

        forged_id = deepcopy(value)
        next(row for row in forged_id['candidates']
             if row['action']['kind'] == 'diplomacy_initiate')['candidate_id'] = '0' * 64
        self._redigest(forged_id)
        with self.assertRaises(ValueError):
            self._validate(forged_id, observation)

        wrong_gap = deepcopy(value)
        wrong_gap['families']['diplomacy_initiate']['unqualified'] = ['something_else']
        self._redigest(wrong_gap)
        with self.assertRaises(ValueError):
            self._validate(wrong_gap, observation)

    def test_governor_fields_remain_mandatory_in_v33(self):
        value, observation = self._active_v33()
        missing = deepcopy(value)
        missing.pop('governors')
        self._redigest(missing)
        with self.assertRaises(ValueError):
            self._validate(missing, observation)
        unavailable = deepcopy(value)
        unavailable['governors'] = None
        self._redigest(unavailable)
        with self.assertRaises(ValueError):
            self._validate(unavailable, observation)

    def test_waiting_and_closed_v33_require_null_overview_and_unqualified_family(self):
        fixture = self._fixture()
        for state, closed in (('waiting', False), ('close', True)):
            value, observation, _ = fixture.v32(state, available=False)
            value['schema'] = network_turn.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA
            value['diplomacy_overview'] = None
            value['families']['diplomacy_initiate'] = dict(
                status='unqualified', reason='native_query_unavailable')
            self._redigest(value)
            with self.subTest(state=state):
                self._validate(value, observation, actions_closed=closed)
                bad = deepcopy(value)
                bad['diplomacy_overview'] = self._overview(rows=[])
                self._redigest(bad)
                with self.assertRaises(ValueError):
                    self._validate(bad, observation, actions_closed=closed)

    def test_diplomacy_information_projection_returns_validated_public_clone(self):
        value, observation = self._active_v33()
        overview = value['diplomacy_overview']
        original = deepcopy(overview)
        projected = information.project('diplomacy', observation, value)
        self.assertEqual(projected, overview)
        self.assertIsNot(projected, overview)
        projected['targets'][0]['selections'].clear()
        self.assertEqual(overview, original)
        for changed in (
                dict(overview, player_id=overview['player_id'] + 1),
                dict(overview, turn=overview['turn'] + 1),
                dict(overview, raw_ai={'secret': 1})):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                information.project('diplomacy', observation,
                                    dict(value, diplomacy_overview=changed))

    def test_v33_checkpoint_projection_strips_only_new_layers_with_xp2_core(self):
        current, observation = self._active_v33()
        saved, _ = self._fixture().v31()
        original_current, original_saved = deepcopy(current), deepcopy(saved)
        projected, transition = network_turn.checkpoint_catalogue(
            current, saved, observation, core_sha256=XP2_CORE)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['source_schema'], saved['schema'])
        self.assertEqual(transition['target_schema'], network_turn.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA)
        self.assertEqual(transition['added_public_fields'], ['governors', 'diplomacy_overview'])
        self.assertEqual(transition['added_action_families'], [
            'appoint_governor', 'promote_governor', 'assign_governor',
            'consider_governor_titles', 'diplomacy_initiate'])
        self.assertEqual(current, original_current)
        self.assertEqual(saved, original_saved)

    def test_checkpoint_projection_refuses_wrong_core_and_does_not_claim_native_v33(self):
        current, observation = self._active_v33()
        saved, _ = self._fixture().v31()
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(current, saved, observation, core_sha256='0' * 64)
        self.assertEqual(current['schema'], 'civ6-host.network-capability-decisions.v33')
        self.assertEqual(current['diplomacy_overview']['schema'], 'civ6-host.diplomacy-overview.v1')

    def test_client_information_and_protocol_selection_keep_public_diplomacy_boundary(self):
        from uuid import uuid4
        from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
        from civ6_host.runtime.native.native_saved_session_protocol import outcome
        from civ6_host.runtime.native.native_victory_episode import POLICY_ID, PROOF_SHA256
        from civ6_host.runtime.native.native_episode_facts import PROOF_SHA256 as FACTS_SHA
        from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
        from civ6_host.session_client import SessionClient
        from civ6_host.client import ProtocolError

        first, observation = self._active_v33(sequence=0)
        episode = first['episode_id']
        generation = first['game_generation']
        nonce = uuid4().hex
        action_row = next(row for row in first['candidates']
                          if row['action'].get('kind') == 'diplomacy_initiate')
        action = action_row['action']

        def response(operation, sequence, decisions, requested=None):
            native = dict(schema='civ6rl.native_victory_episode.observation.v1',
                episode_id=episode, game_generation=generation,
                policy_id=POLICY_ID, source_proof_sha256=PROOF_SHA256,
                facts_source_proof_sha256=FACTS_SHA, player_id=0,
                observation_only=True, eligible_for_training=False,
                exposed_to_learner=False, global_engine_terminal=None,
                engine_halted=None, episode_terminated=False, winner_present=False,
                current_game_turn=observation['turn'])
            return dict(stage='official_session_response', schema='civ6-host.session.v1',
                nonce=nonce, episode_id=episode, game_generation=generation,
                sequence=sequence, operation=operation, observation=observation,
                rounds=0, outcome=outcome(native, 0, 8),
                automatic_choices_applied=False, action_interface_complete=False,
                strategic_training_ready=False, decisions=decisions, applied_action=None,
                session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS',
                    turn=observation['turn'], local_player_id=0, human_player_ids=[0],
                    active_human_player_ids=[0]),
                command_result=dict(status='none' if requested is None else 'refused',
                    reason=None, requested_action=requested))

        class Backend:
            def __init__(self):
                self.requests = []

            def reset(self):
                return response('reset', 0, deepcopy(first))

            def request(self, request):
                self.requests.append(deepcopy(request))
                if request['operation'] != 'act':
                    raise AssertionError('Unexpected fake-backend operation')
                return response('act', request['sequence'],
                                self_owner._active_v33(sequence=request['sequence'])[0],
                                action)

            def abort(self, reason):
                raise AssertionError('Client aborted the fake transport: ' + reason)

        self_owner = self
        backend = Backend()
        client = SessionClient(backend)
        initial = client.reset()
        self.assertEqual(initial['decisions']['schema'],
                         network_turn.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA)
        self.assertEqual(client.view()['decisions']['candidates'], first['candidates'])

        for unsupported_key in ('CHOICE_MAKE_DEAL', 'CHOICE_DECLARE_FRIENDSHIP'):
            unsupported_action = dict(kind='diplomacy_initiate', target_player_id=2,
                                      choice=unsupported_key)
            self.assertEqual(diplomacy_overview.validate_action(unsupported_action),
                             unsupported_action)
            with self.subTest(choice=unsupported_key), self.assertRaises(ProtocolError):
                client.act(0, first['decision_id'], network_turn.digest(unsupported_action))
        for disabled_key in ('CHOICE_DECLARE_FRIENDSHIP',):
            disabled_action = dict(kind='diplomacy_initiate', target_player_id=2,
                                   choice=disabled_key)
            with self.subTest(choice=disabled_key), self.assertRaises(ProtocolError):
                client.act(0, first['decision_id'], network_turn.digest(disabled_action))
        self.assertEqual(backend.requests, [])

        identity = DiagnosticEpisodeIdentity(episode, generation)
        protocol = NetworkProtocol(identity, nonce, initial_turn=observation['turn'])
        reset_response = response('reset', 0, deepcopy(first))
        validate_network_response(reset_response, protocol, 'reset')
        protocol.accept_response(reset_response)
        request = dict(schema=protocol.schema, nonce=nonce, episode_id=episode,
            game_generation=generation, sequence=1, operation='act', player_id=0,
            selection=dict(decision_id=first['decision_id'],
                           candidate_id=action_row['candidate_id']))
        self.assertEqual(protocol.validate(request), 'act')
        self.assertEqual(protocol.selected(request), action)
        act_response = response('act', 1,
            self._active_v33(sequence=1)[0], requested=action)
        validate_network_response(act_response, protocol, 'act', request=request)
        protocol.commit_reply(request, act_response)

        result = client.act(0, first['decision_id'], action_row['candidate_id'])
        self.assertEqual(result['decisions']['schema'],
                         network_turn.CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA)
        self.assertEqual(backend.requests[0]['selection'],
                         dict(decision_id=first['decision_id'],
                              candidate_id=action_row['candidate_id']))
        projected = client.information('diplomacy')
        self.assertEqual(projected['group'], 'diplomacy')
        self.assertEqual(projected['data'], result['decisions']['diplomacy_overview'])


if __name__ == '__main__':
    unittest.main()

"""Offline wire fixtures only: no native query, action or XP1 admission."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from civ6_host.contracts import network_turn as contract
from civ6_host.session_client import InformationUnavailable, SessionClient
from civ6_host.runtime.network_protocol import NetworkProtocol, SCHEMA, validate_network_response
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome
from civ6_host.runtime.native.native_victory_episode import POLICY_ID, PROOF_SHA256
from civ6_host.runtime.native.native_episode_facts import PROOF_SHA256 as FACTS_SHA


def seal(value):
    value['decision_id'] = contract.digest({k: v for k, v in value.items() if k != 'decision_id'})
    return value


def observation(player=0):
    return dict(schema='civ6rl-player-observation-v1', player_id=player, turn=1,
        width=8, height=8, plots=[], visible_enemy_units=[], cities=[],
        units=[dict(id=17+player, type=1, x=3, y=4, damage=0, moves=2, max_moves=2, owner=player)],
        economy=dict(science=1, culture=1, gold=20, faith=0))


def catalogue(identity, sequence=0, player=0, *, queried=True, choices=True):
    action = dict(kind='found_city', unit_id=17+player, x=3, y=4)
    rows = [dict(candidate_id=contract.digest(action), action=action)] if queried and choices else []
    family = (dict(status='queried_complete', candidate_ids=[r['candidate_id'] for r in rows])
              if queried else dict(status='unqualified', reason='native_family_not_qualified'))
    return seal(dict(schema=contract.CAPABILITY_SCHEMA,
        episode_id=identity.episode_id, game_generation=identity.game_generation,
        sequence=sequence, player_id=player, turn=1,
        turn_controls=dict(schema=contract.TURN_CONTROLS_SCHEMA, player_id=player, turn=1,
            active=True, active_complete=True, can_unready=False, timer_elapsed=None),
        candidates=rows, families=dict(found_city=family,
            other_human_actions=dict(status='unqualified', reason='not_an_exhaustive_inventory')),
        family_inventory_complete=False, complete_action_space=False))


class CapabilityBackend:
    """Synthetic responses routed through the real existing protocol/client."""
    def __init__(self):
        self.calls, self.aborts = [], []
        self.status = 'completed'
        self.fault = None

    def _reply(self, operation, sequence, player, requested=None):
        native = dict(schema='civ6rl.native_victory_episode.observation.v1',
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            policy_id=POLICY_ID, source_proof_sha256=PROOF_SHA256,
            facts_source_proof_sha256=FACTS_SHA, player_id=player,
            observation_only=True, eligible_for_training=False, exposed_to_learner=False,
            global_engine_terminal=None, engine_halted=None, episode_terminated=False,
            winner_present=False, current_game_turn=1)
        result = outcome(native, 0, self.protocol.limit, closed=operation == 'close')
        obs = observation(player)
        if player in self.consumed:
            obs['units'] = []
            obs['cities'] = [dict(id=65536, x=3, y=4, owner=player, population=1,
                yields=dict(food=2, production=1, gold=1, science=1, culture=1, faith=0))]
        decisions = catalogue(self.identity, sequence, player, choices=player not in self.consumed)
        if operation == 'close':
            obs = decisions = None
        return dict(stage='official_session_response', schema=SCHEMA, nonce=self.protocol.nonce,
            episode_id=self.identity.episode_id, game_generation=self.identity.game_generation,
            sequence=sequence, operation=operation, observation=obs, decisions=decisions,
            rounds=0, outcome=result, automatic_choices_applied=False,
            action_interface_complete=False, strategic_training_ready=False,
            session=dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=1,
                local_player_id=0, human_player_ids=[0, 1], active_human_player_ids=[0, 1]),
            command_result=dict(status=self.status if operation == 'act' else 'none',
                reason='fixture_refusal' if operation == 'act' and self.status == 'refused' else None,
                requested_action=requested),
            applied_action=requested if operation == 'act' and self.status == 'completed' else None)

    def reset(self):
        episode = str(uuid4())
        self.identity = DiagnosticEpisodeIdentity(episode, 'native-'+episode)
        self.protocol = NetworkProtocol(self.identity, uuid4().hex, initial_turn=1)
        self.consumed = set()
        response = self._reply('reset', 0, 0)
        validate_network_response(response, self.protocol, 'reset')
        self.protocol.accept_response(response)
        return response

    def request(self, request):
        self.calls.append(copy.deepcopy(request))
        operation = self.protocol.validate(request)
        action = self.protocol.selected(request) if operation == 'act' else None
        if action is not None and self.status == 'completed':
            self.consumed.add(request['player_id'])
        response = self._reply(operation, request['sequence'], request['player_id'], action)
        validate_network_response(response, self.protocol, operation, request=request)
        self.protocol.commit_reply(request, response)
        self.protocol.accept_response(response)
        # Deliberately corrupt only the wire returned to the portable client.
        if self.fault is not None:
            self.fault(response)
        return response

    def abort(self, reason):
        self.aborts.append(reason)


class CapabilityContractTests(unittest.TestCase):
    def setUp(self):
        episode = str(uuid4())
        self.identity = DiagnosticEpisodeIdentity(episode, 'native-'+episode)

    def validate(self, value, *, obs=None, closed=False):
        return contract.validate_catalogue(value, self.identity, 0, 1, player_id=0,
            actions_closed=closed, observation=observation() if obs is None else obs)

    def test_complete_family_zero_result_differs_from_unqualified(self):
        queried = catalogue(self.identity, choices=False)
        missing = catalogue(self.identity, queried=False)
        self.validate(queried); self.validate(missing)
        self.assertEqual(queried['candidates'], missing['candidates'])
        self.assertNotEqual(queried['families'], missing['families'])
        self.assertNotEqual(queried['decision_id'], missing['decision_id'])
        self.assertEqual(contract.LATEST_SCHEMA, contract.PRODUCTION_SCHEMA)
        self.assertNotIn(contract.CAPABILITY_SCHEMA, contract.MAP_SCHEMAS)
        for extra in ('player_map', 'base_schema', 'production', 'private_state'):
            value = catalogue(self.identity)
            value[extra] = {} if extra != 'base_schema' else None
            with self.subTest(extra=extra), self.assertRaises(ValueError):self.validate(seal(value))

    def test_unqualified_family_never_substitutes_empty_or_positive_query(self):
        for alteration in ('empty_ids', 'offered', 'unknown_query', 'missing_status', 'empty_inventory'):
            value = catalogue(self.identity, queried=False)
            if alteration == 'empty_ids':value['families']['found_city']['candidate_ids'] = []
            elif alteration == 'offered':value['candidates'] = catalogue(self.identity)['candidates']
            elif alteration == 'unknown_query':value['families']['not_implemented'] = dict(status='queried_complete', candidate_ids=[])
            elif alteration == 'missing_status':value['families']['found_city'] = dict(candidate_ids=[])
            else:value['families'] = {}
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):self.validate(seal(value))

    def test_exact_family_candidate_coverage_and_digests(self):
        for alteration in ('drop_id', 'extra_id', 'duplicate_id', 'duplicate_candidate', 'rename_id', 'stale_digest'):
            value = catalogue(self.identity)
            ids = value['families']['found_city']['candidate_ids']
            if alteration == 'drop_id':ids.clear()
            elif alteration == 'extra_id':ids.append('f'*64)
            elif alteration == 'duplicate_id':ids.append(ids[0])
            elif alteration == 'duplicate_candidate':value['candidates'].append(copy.deepcopy(value['candidates'][0]))
            elif alteration == 'rename_id':value['candidates'][0]['candidate_id'] = ids[0] = 'f'*64
            else:value['families']['other_human_actions']['reason'] = 'tampered'
            if alteration != 'stale_digest':seal(value)
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):self.validate(value)

    def test_identity_and_completeness_require_exact_types(self):
        mutations = [('sequence',True), ('player_id',False), ('turn',True),
            ('episode_id',str(uuid4())), ('game_generation','native-foreign'),
            ('family_inventory_complete',True), ('family_inventory_complete',0),
            ('complete_action_space',True), ('complete_action_space',0)]
        for field, replacement in mutations:
            value = catalogue(self.identity);value[field] = replacement
            with self.subTest(field=field,replacement=replacement), self.assertRaises(ValueError):
                self.validate(seal(value))
        for key in ('active', 'active_complete', 'can_unready'):
            value = catalogue(self.identity);value['turn_controls'][key] = 1
            with self.subTest(key=key), self.assertRaises(ValueError):self.validate(seal(value))

    def test_foundation_shapes_and_owned_unit_position_are_checked(self):
        for alteration in ('boolean_id','wide_id','negative_x','wide_y','foreign_unit','wrong_position','extra_field','unknown_kind'):
            value = catalogue(self.identity);action = value['candidates'][0]['action']
            if alteration == 'boolean_id':action['unit_id'] = True
            elif alteration == 'wide_id':action['unit_id'] = 1<<32
            elif alteration == 'negative_x':action['x'] = -1
            elif alteration == 'wide_y':action['y'] = 65536
            elif alteration == 'foreign_unit':action['unit_id'] = 88
            elif alteration == 'wrong_position':action['x'] = 2
            elif alteration == 'extra_field':action['owner'] = 0
            else:action['kind'] = 'move'
            cid = contract.digest(action)
            value['candidates'][0]['candidate_id'] = cid
            value['families']['found_city']['candidate_ids'] = [cid]
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):self.validate(seal(value))
        foreign = observation();foreign['units'][0]['owner'] = 1
        with self.assertRaises(ValueError):self.validate(catalogue(self.identity),obs=foreign)
        duplicate = observation();duplicate['units'].append(copy.deepcopy(duplicate['units'][0]))
        with self.assertRaisesRegex(ValueError,'Ambiguous'):self.validate(catalogue(self.identity),obs=duplicate)
        leaked = observation();leaked['enemy_gold'] = 999
        with self.assertRaises(ValueError):self.validate(catalogue(self.identity),obs=leaked)

    def test_waiting_cannot_claim_query_complete_when_native_reader_asserts(self):
        # found_city_catalog_source asserts strategic-command permission and
        # alive/active/active-complete before enumeration. A failed precondition
        # cannot become a successful empty query. ActiveComplete is readiness,
        # not evidence that the player has finished the turn.
        for controls in (dict(active=False),dict(active_complete=False),dict(can_unready=True)):
            for choices in (False,True):
                value = catalogue(self.identity, choices=choices);value['turn_controls'].update(controls)
                with self.subTest(controls=controls,choices=choices), self.assertRaises(ValueError):
                    self.validate(seal(value))
            missing = catalogue(self.identity, queried=False);missing['turn_controls'].update(controls)
            self.validate(seal(missing))
        with self.assertRaises(ValueError):self.validate(catalogue(self.identity),closed=True)
        self.validate(catalogue(self.identity,queried=False),closed=True)


class CapabilitySessionTests(unittest.TestCase):
    def setUp(self):
        self.backend = CapabilityBackend()
        self.client = SessionClient(self.backend, allow_administrative=True)
        self.first = self.client.reset()

    def test_same_protocol_routes_explicit_choice_without_legacy_or_fake_map(self):
        decisions = self.first['decisions']
        # This is the existing protocol validator; legacy routes must not run.
        with patch('civ6_host.runtime.network_protocol.validate_decisions', side_effect=AssertionError('legacy route')), \
             patch('civ6_host.runtime.network_protocol.player_map.validate', side_effect=AssertionError('fake map')):
            second = self.client.observe(1)
            current = self.client.act(0, decisions['decision_id'], decisions['candidates'][0]['candidate_id'])
        self.assertEqual(current['sequence'], 2)
        self.assertEqual(current['applied_action'], decisions['candidates'][0]['action'])
        self.assertEqual(current['decisions']['families']['found_city'],dict(status='queried_complete',candidate_ids=[]))
        self.assertEqual(self.client.view(1)['decisions']['decision_id'], second['decisions']['decision_id'])
        self.assertNotIn('player_map', current['decisions'])
        self.assertNotIn('native_victory', current['outcome'])
        self.assertNotIn('command_result', current)
        self.assertFalse(self.backend.protocol.last_outcome['strategic_training_ready'])
        for group in ('economy','production','growth','unit_work'):
            for channel in ('public','administrative'):
                with self.subTest(group=group,channel=channel),self.assertRaises(InformationUnavailable):
                    self.client.information(group,player_id=0,channel=channel)
        self.client.close(0)

    def test_client_rejects_mutated_family_or_hidden_observation_on_wire(self):
        def corrupt_family(response):
            response['decisions']['families']['found_city'] = dict(status='unqualified',reason='fixture')
            seal(response['decisions'])
        def corrupt_observation(response):
            response['observation']['units'][0]['owner'] = 1
        for fault in (corrupt_family, corrupt_observation):
            self.client.reset();self.backend.fault = fault
            with self.subTest(fault=fault.__name__),self.assertRaises(ValueError):self.client.observe(0)
            self.assertTrue(self.backend.aborts)
        self.backend.fault = None

    def test_unavailable_and_stale_selection_cannot_be_submitted(self):
        decisions = self.first['decisions']
        selected = dict(decision_id=decisions['decision_id'],candidate_id=decisions['candidates'][0]['candidate_id'])
        request = dict(schema=SCHEMA,nonce=self.backend.protocol.nonce,
            episode_id=self.backend.identity.episode_id,game_generation=self.backend.identity.game_generation,
            sequence=1,operation='act',player_id=0,selection=selected)
        for mutation in ('stale','absent','parameters'):
            changed = copy.deepcopy(request)
            if mutation == 'stale':changed['selection']['decision_id'] = 'f'*64
            elif mutation == 'absent':changed['selection']['candidate_id'] = 'f'*64
            else:changed['selection']['parameters'] = {}
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.backend.protocol.validate(changed)
        self.assertEqual(self.backend.calls,[])

    def test_capability_reply_cannot_weaken_native_outcome_or_turn_identity(self):
        for mutation in ('missing_native','changed_source','fake_termination','wrong_turn','false_complete'):
            backend = CapabilityBackend();backend.reset()
            reply = backend._reply('reset',0,0)
            if mutation == 'missing_native':reply['outcome'].pop('native_victory')
            elif mutation == 'changed_source':reply['outcome']['native_victory']['source_proof_sha256'] = 'f'*64
            elif mutation == 'fake_termination':reply['outcome']['terminated'] = True
            elif mutation == 'wrong_turn':reply['session']['turn'] = 2
            else:reply['action_interface_complete'] = True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                validate_network_response(reply,backend.protocol,'reset')

    def test_refused_action_is_not_applied_and_reset_changes_native_identity(self):
        self.backend.status = 'refused'
        decisions = self.first['decisions']
        value = self.client.act(0,decisions['decision_id'],decisions['candidates'][0]['candidate_id'])
        self.assertIsNone(value['applied_action'])
        self.assertEqual(self.client.command_result['status'],'refused')
        old = value['episode_id']
        self.assertNotEqual(self.client.reset()['episode_id'],old)


if __name__ == '__main__':
    unittest.main()

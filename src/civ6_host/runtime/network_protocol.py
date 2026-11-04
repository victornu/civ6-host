"""Transport and actor protocol for the captured simultaneous LAN session.

This protocol retains one native decision catalogue per human player. The
global sequence orders RPC transport; it does not make another player's
same-turn catalogue stale.
"""
from __future__ import annotations

import copy
from uuid import UUID

from civ6_host.client import _ENVELOPE, _digest, _public_contracts
from civ6_host.runtime.native.native_action_session import ActionProtocol
from civ6_host.runtime.native.native_action_session import validate_decisions
from civ6_host.runtime.native import native_diplomacy_choices as diplomacy
from civ6_host.runtime.native import native_saved_player_map as player_map
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import outcome as classify_outcome
from civ6_host.contracts import network_turn as network_turn_contract
from civ6_host.contracts.session_result import project_terminal_result, require_same_terminal_result

SCHEMA = 'civ6-host.session.v1'
CLOSURE_SCHEMA = 'civ6-host.session.closure.v1'
OPERATIONS = frozenset(('observe', 'act', 'poll', 'close'))
_IDENTITY_FIELDS = {'schema', 'nonce', 'episode_id', 'game_generation', 'sequence', 'operation'}
_SESSION_FIELDS = {'game_mode', 'turn_phase', 'turn', 'local_player_id',
                   'human_player_ids', 'active_human_player_ids'}
_COMMAND_FIELDS = {'status', 'reason', 'requested_action'}
_STATUS = frozenset(('none', 'completed', 'refused', 'submitted', 'pending'))
_RESPONSE_FIELDS = set(_ENVELOPE) | {'session', 'command_result'}


def _player_id(value):
    if type(value) is not int or not 0 <= value < 64:
        raise ValueError('player_id must be an integer in [0, 63]')
    return value


def _player_list(value, label):
    if (type(value) is not list
            or any(type(item) is not int or not 0 <= item < 64 for item in value)
            or len(value) != len(set(value))):
        raise ValueError('Invalid ' + label)
    return list(value)


def _validate_session(value):
    if type(value) is not dict or set(value) != _SESSION_FIELDS:
        raise ValueError('Unexpected LAN session-state fields')
    if value['game_mode'] != 'LAN' or type(value['game_mode']) is not str:
        raise ValueError('Session is not the captured LAN mode')
    if (value['turn_phase'] != 'TURNPHASE_SIMULTANEOUS'
            or type(value['turn_phase']) is not str):
        raise ValueError('Session is not in simultaneous turn phase')
    if type(value['turn']) is not int or value['turn'] < 0:
        raise ValueError('Invalid LAN session turn')
    local = _player_id(value['local_player_id'])
    humans = _player_list(value['human_player_ids'], 'human player IDs')
    active = _player_list(value['active_human_player_ids'], 'active human player IDs')
    if local not in humans or not set(active).issubset(humans):
        raise ValueError('LAN session players do not match the captured human roster')
    return copy.deepcopy(value)


def _validate_command(value):
    if type(value) is not dict or set(value) != _COMMAND_FIELDS:
        raise ValueError('Unexpected command-result fields')
    if type(value['status']) is not str or value['status'] not in _STATUS:
        raise ValueError('Unknown command-result status')
    if value['reason'] is not None and type(value['reason']) is not str:
        raise ValueError('Invalid command-result reason')
    if value['requested_action'] is not None and type(value['requested_action']) is not dict:
        raise ValueError('Invalid requested action')
    return copy.deepcopy(value)


class NetworkProtocol(ActionProtocol):
    """ActionProtocol with explicit LAN actors and same-turn catalogues."""

    schema = SCHEMA
    closure_schema = CLOSURE_SCHEMA

    def __init__(self, identity, nonce, round_limit=8, *, initial_turn=1,
                 core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        if type(identity) is not DiagnosticEpisodeIdentity:
            raise ValueError('Native episode identity required')
        if type(initial_turn) is not int or not 0 <= initial_turn <= 100000:
            raise ValueError('Invalid captured initial turn')
        super().__init__(identity, nonce, round_limit=round_limit)
        from .xp1_session_result import result_provenance
        self._result_provenance = result_provenance(core_sha256)
        self.core_sha256 = core_sha256
        self.initial_turn = initial_turn
        self.catalogues = {}
        self.session = None
        self.last_outcome = None

    def validate(self, request):
        if type(request) is not dict:
            raise ValueError('Malformed LAN session command')
        operation = request.get('operation')
        expected = set(_IDENTITY_FIELDS) | {'player_id'}
        if operation == 'act':
            expected.add('selection')
        if set(request) != expected:
            raise ValueError('Malformed LAN session command fields')
        if (request['schema'] != self.schema or request['nonce'] != self.nonce
                or request['episode_id'] != self.identity.episode_id
                or request['game_generation'] != self.identity.game_generation):
            raise ValueError('Stale or foreign LAN episode command')
        if (type(request['sequence']) is not int
                or request['sequence'] != self.sequence + 1
                or request['sequence'] > self.max_commands or self.closed):
            raise ValueError('Out-of-order or closed LAN session command')
        if type(operation) is not str or operation not in OPERATIONS:
            raise ValueError('Unsupported LAN session operation')
        player_id = _player_id(request['player_id'])
        if self.session is None:
            raise ValueError('LAN session metadata is not initialized')
        if player_id not in self.session['human_player_ids']:
            raise ValueError('Requested actor is not a captured human player')
        if operation == 'act':
            selected = self.selected(request)
            native_forced=network_turn_contract.offered_forced_turn(self.catalogues[player_id],selected)
            if (player_id not in self.session['active_human_player_ids']
                    and selected.get('kind') not in ('unready_turn', 'diplomacy_response')
                    and not native_forced):
                raise ValueError('Inactive actor requires an offered Unready, forced turn or dialogue response')
        if self.ended and operation != 'close':
            raise ValueError('Session ended; reset required')
        return operation

    def selected(self, request):
        """Resolve from this actor's cached catalogue, even after another RPC."""
        if type(request) is not dict:
            raise ValueError('Malformed LAN action request')
        player_id = _player_id(request.get('player_id'))
        catalogue = self.catalogues.get(player_id)
        if catalogue is None or self.session is None:
            raise ValueError('No current decision catalogue for this actor')
        if (catalogue['episode_id'] != self.identity.episode_id
                or catalogue['game_generation'] != self.identity.game_generation
                or catalogue['turn'] != self.session['turn']):
            raise ValueError('Actor catalogue is stale for the current native turn')
        legacy = network_turn_contract.validate_catalogue(
            catalogue, self.identity, catalogue['sequence'], catalogue['turn'],
            player_id=player_id, actions_closed=self.ended)
        if network_turn_contract.is_capability_catalogue(catalogue):
            return network_turn_contract.select_capability(catalogue, request.get('selection'))
        if legacy is None:
            selection = request.get('selection')
            if (type(selection) is not dict
                    or set(selection) != {'decision_id', 'candidate_id'}
                    or selection['decision_id'] != catalogue['decision_id']):
                raise ValueError('Malformed or stale Unready selection')
            matches = [row['action'] for row in catalogue['candidates']
                       if row['candidate_id'] == selection['candidate_id']]
            if len(matches) != 1:
                raise ValueError('Unready is absent from the native turn-control catalogue')
            return matches[0]
        selection = request.get('selection')
        if (type(selection) is not dict
                or selection.get('decision_id') != catalogue['decision_id']):
            raise ValueError('Stale network decision catalogue')
        initial = [row['action'] for row in catalogue['candidates']
                   if row['candidate_id'] == selection.get('candidate_id')
                   and row['action'].get('kind') == 'diplomacy_initiate']
        if initial:
            if len(initial) != 1 or set(selection) != {'decision_id', 'candidate_id'}:
                raise ValueError('Malformed initial diplomacy selection')
            return copy.deepcopy(initial[0])
        proxy = copy.copy(self)
        proxy.decisions = legacy
        base_request = dict(request)
        base_request['selection'] = dict(selection)
        base_request['selection']['decision_id'] = legacy['decision_id']
        return ActionProtocol.selected(proxy, base_request)

    def commit_reply(self, request, response):
        """Commit only after the matching reply has passed validation."""
        operation = self.validate(request)
        validate_network_response(response, self, operation, request=request)
        self.sequence = request['sequence']
        self.rounds = response['session']['turn'] - self.initial_turn
        self.closed = operation == 'close'
        self.ended = bool(response['outcome']['terminated'] or response['outcome']['truncated'])

    def accept_response(self, response):
        """Cache a validated catalogue and the session state it describes."""
        session = _validate_session(response['session'])
        if self.session is not None:
            if (session['local_player_id'] != self.session['local_player_id']
                    or session['human_player_ids'] != self.session['human_player_ids']):
                raise ValueError('LAN human roster changed within an episode')
            if session['turn'] < self.session['turn']:
                raise ValueError('LAN turn moved backwards')
        if self.session is None or session['turn'] != self.session['turn']:
            self.catalogues = {}
        self.session = session
        self.sequence = response['sequence']
        self.rounds = session['turn'] - self.initial_turn
        self.last_outcome = copy.deepcopy(response['outcome'])
        self.ended = bool(response['outcome']['terminated'] or response['outcome']['truncated'])
        self.closed = response['operation'] == 'close'
        observation, decisions = response['observation'], response['decisions']
        if self.ended:
            self.catalogues = {}
        elif observation is not None and decisions is not None:
            self.catalogues[observation['player_id']] = copy.deepcopy(decisions)
            self.decisions = copy.deepcopy(decisions)

    def commit(self, request, *, native_terminated=False, turn_completed=None):
        """Reject the legacy counter-only commit; network needs its reply turn."""
        raise ValueError('NetworkProtocol requires commit_reply(request, response)')


def validate_network_response(response, protocol, operation, *, request=None):
    """Validate a legacy response envelope plus the LAN session and receipt."""
    if type(operation) is not str or operation not in OPERATIONS | {'reset'}:
        raise ValueError('Unsupported LAN response operation')
    if type(response) is not dict or set(response) != _RESPONSE_FIELDS:
        raise ValueError('Malformed LAN session response envelope')
    if (response['stage'] != 'official_session_response'
            or response['schema'] != protocol.schema or response['operation'] != operation
            or response['automatic_choices_applied'] is not False
            or response['action_interface_complete'] is not False
            or response['strategic_training_ready'] is not False):
        raise ValueError('Unsupported or automatic LAN session response')
    if (response['nonce'] != protocol.nonce
            or response['episode_id'] != protocol.identity.episode_id
            or response['game_generation'] != protocol.identity.game_generation):
        raise ValueError('Foreign LAN episode response')
    if request is None:
        if operation != 'reset' or protocol.sequence != 0 or response['sequence'] != 0:
            raise ValueError('Reset response must be the initial sequence-zero reply')
        requested_player = None
    else:
        if operation == 'reset':
            raise ValueError('Reset is a response only, not a LAN request operation')
        protocol.validate(request)
        if request['operation'] != operation:
            raise ValueError('LAN request and response operations differ')
        if any(response[key] != request[key] for key in
               ('nonce', 'episode_id', 'game_generation', 'sequence')):
            raise ValueError('Foreign or out-of-order LAN response')
        requested_player = request['player_id']
    if type(response['sequence']) is not int or response['sequence'] < 0:
        raise ValueError('Invalid global LAN RPC sequence')
    session = _validate_session(response['session'])
    if protocol.session is not None:
        if (session['local_player_id'] != protocol.session['local_player_id']
                or session['human_player_ids'] != protocol.session['human_player_ids']
                or session['turn'] < protocol.session['turn']):
            raise ValueError('LAN session identity/turn changed unexpectedly')
    if (type(response['rounds']) is not int
            or response['rounds'] != session['turn'] - protocol.initial_turn):
        raise ValueError('LAN rounds do not equal captured turn distance')

    result = response['outcome']
    if (type(result) is not dict or type(result.get('terminated')) is not bool
            or type(result.get('truncated')) is not bool
            or result['terminated'] and result['truncated']):
        raise ValueError('Invalid LAN outcome')
    native = result.get('native_victory')
    from civ6_host.runtime.native.native_victory_episode import POLICY_ID
    from civ6_host.runtime.xp1_session_result import result_provenance, BASE_CORE_SHA256
    expected_provenance = result_provenance(protocol.core_sha256)
    if protocol._result_provenance != expected_provenance:
        raise ValueError('Selected result-source identity changed within session')
    if (type(native) is not dict or native.get('episode_id') != protocol.identity.episode_id
            or native.get('game_generation') != protocol.identity.game_generation
            or native.get('policy_id') != POLICY_ID
            or any(type(native.get(key)) is not type(value) or native[key] != value
                   for key,value in expected_provenance.items())
            or protocol.core_sha256 == BASE_CORE_SHA256 and any(key in native for key in
                ('result_source_profile','core_sha256','native_write_before_notification_qualified',
                 'native_terminal_transition_qualified'))
            or type(native.get('player_id')) is not int
            or native['player_id'] != (session['local_player_id'] if requested_player is None else requested_player)
            or native.get('observation_only') is not True
            or native.get('eligible_for_training') is not False
            or native.get('exposed_to_learner') is not False
            or native.get('global_engine_terminal') is not None
            or native.get('engine_halted') is not None):
        raise ValueError('Native victory identity or private-scope flags differ')
    expected_outcome = classify_outcome(native, response['rounds'], protocol.limit,
        closed=operation == 'close', maximum=protocol.max_round_limit)
    if result != expected_outcome:
        raise ValueError('LAN outcome classification differs')
    if native.get('current_game_turn') != session['turn']:
        raise ValueError('Native outcome and LAN session turn differ')
    project_terminal_result(result, episode_id=protocol.identity.episode_id,
        game_generation=protocol.identity.game_generation,
        player_id=native['player_id'], turn=session['turn'])
    require_same_terminal_result(protocol.last_outcome, result)

    command = _validate_command(response['command_result'])
    if operation != 'act':
        if command['status'] != 'none' or command['requested_action'] is not None:
            raise ValueError('Non-action RPC returned an action result')
    else:
        if command['status'] == 'none':
            raise ValueError('Action RPC returned no command status')
        selected = protocol.selected(request)
        if _digest(command['requested_action']) != _digest(selected):
            raise ValueError('Requested action differs from the actor catalogue choice')
        # A global result can arrive with a refused/pending local command.
        # Keep both facts; the applied-action check never upgrades its status.

    observation, decisions = response['observation'], response['decisions']
    ended = result['terminated'] or result['truncated']
    if observation is None or decisions is None:
        if not ended or observation is not None or decisions is not None:
            raise ValueError('Live LAN reply needs both observation and decisions')
    else:
        if type(observation) is not dict or type(decisions) is not dict:
            raise ValueError('Malformed LAN actor perspective')
        player_id = _player_id(observation.get('player_id'))
        turn = observation.get('turn')
        if type(turn) is not int or turn != session['turn']:
            raise ValueError('Observation is outside the native LAN turn')
        if player_id not in session['human_player_ids']:
            raise ValueError('Observation is not for a captured human player')
        if requested_player is not None and player_id != requested_player:
            raise ValueError('Response returned another requested actor')
        if request is None and player_id != session['local_player_id']:
            raise ValueError('Initial view is not the configured local human')
        legacy_decisions = network_turn_contract.validate_catalogue(
            decisions, protocol.identity, response['sequence'], turn,
            player_id=player_id, actions_closed=ended, observation=observation)
        if decisions['turn_controls']['active'] != (player_id in session['active_human_player_ids']):
            raise ValueError('Actor activity differs from native session state')
        if network_turn_contract.is_capability_catalogue(decisions):
            # The common validator checked the explicit family queries and
            # own-unit observation. This schema declares no revealed map or
            # legacy information groups; none are substituted with empty data.
            pass
        elif legacy_decisions is None:
            player_map.validate(decisions['player_map'], player_id, turn,
                                visible=observation)
        else:
            validate_decisions(legacy_decisions, protocol.identity, response['sequence'], turn,
                               player_id=player_id, actions_closed=ended,
                               map_coordinates=decisions['schema'] in network_turn_contract.MAP_SCHEMAS)
            if not diplomacy.is_catalog(legacy_decisions):
                player_map.validate(legacy_decisions['player_map'], player_id, turn,
                                    visible=observation)
                _public_contracts(legacy_decisions, observation, ended)
            if decisions['schema'] in network_turn_contract.WORK_SCHEMAS and not diplomacy.is_catalog(legacy_decisions):
                from civ6_host.contracts.unit_work_state import validate as validate_work_state
                validate_work_state(decisions['unit_work_state'],player_id,turn,
                    observation=observation,work_catalog=decisions['unit_work'])
                if decisions['schema'] in network_turn_contract.INFO_SCHEMAS:
                    from civ6_host.contracts.unit_work_info import validate as validate_work_info
                    validate_work_info(decisions['unit_work_info'],player_id,turn,
                        observation=observation,work_catalog=decisions['unit_work'])
                if decisions['schema'] in network_turn_contract.GROWTH_SCHEMAS:
                    from civ6_host.contracts.city_growth import validate as validate_growth
                    validate_growth(decisions['city_growth'],player_id,turn,observation=observation)
    applied = response['applied_action']
    if operation != 'act' or command['status'] != 'completed':
        if applied is not None:
            raise ValueError('Host claimed an action outside a completed action RPC')
    elif _digest(applied) != _digest(selected):
        raise ValueError('Applied action differs from the requested actor choice')
    return response

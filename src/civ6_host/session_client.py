"""Public client for explicit actors in a captured LAN session.

The client preserves each actor's last validated catalogue while sequencing
all backend RPCs globally. It does not schedule actors or resolve turns.
"""
from __future__ import annotations

import copy
import re
import threading
from types import SimpleNamespace
from uuid import UUID

from .client import InformationUnavailable, ProtocolError, _ENVELOPE, _digest, _public_contracts
from .contracts import network_turn
from .contracts import policies
from .contracts.session_result import project_terminal_result, require_same_terminal_result

SCHEMA = 'civ6-host.session.v1'
_RESPONSE_FIELDS = _ENVELOPE | {'session', 'command_result'}
_SESSION_FIELDS = {'game_mode', 'turn_phase', 'turn', 'local_player_id',
                   'human_player_ids', 'active_human_player_ids'}
_COMMAND_FIELDS = {'status', 'reason', 'requested_action'}
_STATUSES = {'none', 'completed', 'refused', 'submitted', 'pending'}


def _player_id(value):
    if type(value) is not int or not 0 <= value < 64:
        raise ProtocolError('player_id must be an integer in [0, 63]')
    return value


def _id_list(value, label):
    if type(value) is not list or any(type(item) is not int or not 0 <= item < 64 for item in value):
        raise ProtocolError('Invalid ' + label)
    if len(set(value)) != len(value):
        raise ProtocolError('Duplicate IDs in ' + label)
    return list(value)


def _validate_session(value):
    if type(value) is not dict or set(value) != _SESSION_FIELDS:
        raise ProtocolError('Unexpected LAN session-state fields')
    if (type(value['game_mode']) is not str or value['game_mode'] != 'LAN'
            or type(value['turn_phase']) is not str or value['turn_phase'] != 'TURNPHASE_SIMULTANEOUS'):
        raise ProtocolError('Host session is not the admitted simultaneous LAN mode')
    if type(value['turn']) is not int or value['turn'] < 0:
        raise ProtocolError('Invalid LAN session turn')
    local = _player_id(value['local_player_id'])
    humans = _id_list(value['human_player_ids'], 'human player IDs')
    active = _id_list(value['active_human_player_ids'], 'active human player IDs')
    if local not in humans or not set(active).issubset(humans):
        raise ProtocolError('LAN local/active players differ from the human roster')
    return copy.deepcopy(value)


def _validate_command(value, observation=None):
    if type(value) is not dict or set(value) != _COMMAND_FIELDS:
        raise ProtocolError('Unexpected command-result fields')
    if type(value['status']) is not str or value['status'] not in _STATUSES:
        raise ProtocolError('Unknown command-result status')
    if value['reason'] is not None and type(value['reason']) is not str:
        raise ProtocolError('Invalid command-result reason')
    if value['requested_action'] is not None and type(value['requested_action']) is not dict:
        raise ProtocolError('Invalid requested action')
    if (value['requested_action'] is not None and value['requested_action'].get('kind')
            in ('spy_travel', 'spy_mission', 'spy_cancel', 'spy_escape')):
        from .contracts import espionage
        if type(observation) is not dict:
            raise ProtocolError('Espionage receipt lacks its decision observation')
        try:
            espionage.validate_action(value['requested_action'],
                                      observation['width'], observation['height'])
        except (ValueError, KeyError, TypeError) as exc:
            raise ProtocolError('Invalid requested espionage action: ' + str(exc)) from exc
    if (value['requested_action'] is not None and value['requested_action'].get('kind')
            in ('spy_renew', 'spy_completion_dismiss')):
        from .contracts import spy_completion
        if type(observation) is not dict:
            raise ProtocolError('Spy completion receipt lacks its decision observation')
        try:
            spy_completion.validate_action(value['requested_action'],
                                           observation['width'], observation['height'])
        except (ValueError, KeyError, TypeError) as exc:
            raise ProtocolError('Invalid requested spy completion action: ' + str(exc)) from exc
    if (value['requested_action'] is not None
            and (type(value['requested_action'].get('kind')) is str and value['requested_action'].get('kind').startswith('congress_'))):
        from .contracts import world_congress
        try:
            world_congress.validate_action(value['requested_action'])
        except ValueError as exc:
            raise ProtocolError('Invalid requested Congress action: ' + str(exc)) from exc
    return copy.deepcopy(value)


class SessionClient:
    """Explicit-actor client for the exact public LAN session contract."""

    turn_mode = 'simultaneous'

    def __init__(self, backend, *, allow_administrative=False, war_source_sha256=None):
        if type(allow_administrative) is not bool:
            raise ValueError('allow_administrative must be an exact Boolean')
        if (war_source_sha256 is not None
                and (type(war_source_sha256) is not str
                     or re.fullmatch('[0-9a-f]{64}', war_source_sha256) is None)):
            raise ValueError('war_source_sha256 must be a lowercase SHA-256 digest or None')
        self._backend = backend
        self._allow_administrative = allow_administrative
        self._war_source_sha256 = war_source_sha256
        self._owner = threading.get_ident()
        self._reply = None
        self._closed = True
        self._session = None
        self._episode_local_player = None
        self._views = {}
        self._display_views = {}
        self._command_receipts = {}
        self._last_player_id = None

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('Use this session client from its owning thread')

    def _abort_failed(self):
        self._closed = True
        self._backend.abort('session_client_exchange_failed')

    def _accept(self, response, operation, *, request=None, prior_view=None,
                requested_player=None):
        if type(response) is not dict or set(response) != _RESPONSE_FIELDS:
            raise ProtocolError('Unexpected host session envelope fields')
        if (response['stage'] != 'official_session_response' or response['schema'] != SCHEMA
                or response['operation'] != operation
                or response['automatic_choices_applied'] is not False
                or response['action_interface_complete'] is not False
                or response['strategic_training_ready'] is not False):
            raise ProtocolError('Unsupported or automatic LAN host response')
        episode, generation, nonce = (response[k] for k in ('episode_id', 'game_generation', 'nonce'))
        if (type(episode) is not str or str(UUID(episode)) != episode
                or generation != 'native-' + episode or type(nonce) is not str or len(nonce) != 32
                or any(c not in '0123456789abcdef' for c in nonce)):
            raise ProtocolError('Invalid native session identity')
        if type(response['sequence']) is not int or response['sequence'] < 0:
            raise ProtocolError('Invalid global RPC sequence')
        if operation == 'reset':
            if response['sequence'] != 0:
                raise ProtocolError('Reset must start global RPC sequence zero')
            if self._reply is not None and (self._reply['episode_id'] == episode
                                            or self._reply['nonce'] == nonce):
                raise ProtocolError('Reset reused an existing native identity')
        elif request is None or any(response[k] != request[k] for k in
                ('nonce', 'episode_id', 'game_generation', 'sequence')):
            raise ProtocolError('Foreign or out-of-order global RPC response')

        session = _validate_session(response['session'])
        command = _validate_command(response['command_result'],
                                    None if prior_view is None else prior_view['observation'])
        if operation != 'reset':
            if session['local_player_id'] != self._episode_local_player:
                raise ProtocolError('LAN session changed its local player identity')
            if session['human_player_ids'] != self._session['human_player_ids']:
                raise ProtocolError('LAN session changed its human roster')
            if session['turn'] < self._session['turn']:
                raise ProtocolError('LAN session moved backwards in time')
        if operation != 'act' and command['status'] != 'none':
            raise ProtocolError('Non-action RPC returned an action status')
        if operation != 'act' and command['requested_action'] is not None:
            raise ProtocolError('Non-action RPC reported a requested action')
        if operation == 'act' and command['status'] == 'none':
            raise ProtocolError('Action RPC returned no command status')

        result = response['outcome']
        if (type(result) is not dict or type(result.get('terminated')) is not bool
                or type(result.get('truncated')) is not bool
                or 'reason' not in result
                or result['terminated'] and result['truncated']):
            raise ProtocolError('Invalid session outcome')
        if result.get('reason') is not None and type(result.get('reason')) is not str:
            raise ProtocolError('Invalid session outcome reason')
        if result['terminated']:
            try:
                project_terminal_result(result, episode_id=episode, game_generation=generation,
                    player_id=session['local_player_id'] if requested_player is None else requested_player,
                    turn=session['turn'])
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        if operation != 'reset':
            try:
                require_same_terminal_result(self._reply['outcome'], result)
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        # Command completion and the global winner are independent. Another
        # player may win while this actor's command is refused or pending.
        # The applied_action check below must still forbid invented success.
        observation, decisions = response['observation'], response['decisions']
        if (observation is None) != (decisions is None):
            raise ProtocolError('LAN response contains only half of the actor view')
        if observation is None or decisions is None:
            if result['terminated'] is not True and result['truncated'] is not True:
                raise ProtocolError('Live LAN response lost its player view')
        else:
            if (type(observation) is not dict or type(decisions) is not dict
                    or type(observation.get('player_id')) is not int
                    or type(observation.get('turn')) is not int
                    or not 0 <= observation['player_id'] < 64 or observation['turn'] < 0):
                raise ProtocolError('Invalid LAN actor perspective')
            pid = observation['player_id']
            if pid not in session['human_player_ids'] or observation['turn'] != session['turn']:
                raise ProtocolError('Reply observation is outside the native human/session boundary')
            if operation == 'reset' and pid != session['local_player_id']:
                raise ProtocolError('Reset view is not the configured local human')
            if requested_player is not None and pid != requested_player:
                raise ProtocolError('Host returned another actor for an explicit player request')
            expected = dict(episode_id=episode, game_generation=generation,
                            sequence=response['sequence'], player_id=pid, turn=observation['turn'])
            if any(type(decisions.get(k)) is not type(v) or decisions[k] != v for k, v in expected.items()):
                raise ProtocolError('Decision catalogue and actor boundary differ')
            if decisions.get('decision_id') != _digest({k: v for k, v in decisions.items() if k != 'decision_id'}):
                raise ProtocolError('Decision catalogue digest differs')
            candidates = decisions.get('candidates')
            if type(candidates) is not list:
                raise ProtocolError('Candidate list missing')
            ids = []
            for row in candidates:
                if (type(row) is not dict or type(row.get('candidate_id')) is not str
                        or type(row.get('action')) is not dict):
                    raise ProtocolError('Malformed native candidate')
                ids.append(row['candidate_id'])
            ended = result['terminated'] or result['truncated']
            if len(set(ids)) != len(ids) or (ended and candidates):
                raise ProtocolError('Duplicate or closed native choices')
            if (decisions.get('schema') in network_turn.SUPPORTED_SCHEMAS
                    or network_turn.is_world_war_decisions(decisions)
                    or network_turn.is_diplomacy_decisions(decisions)):
                network_turn.validate_catalogue(decisions,
                    SimpleNamespace(episode_id=episode, game_generation=generation),
                    response['sequence'], observation['turn'], player_id=pid,
                    actions_closed=ended, observation=observation,
                    expected_war_source_sha256=self._war_source_sha256)
                if decisions['turn_controls']['active'] != (pid in session['active_human_player_ids']):
                    raise ProtocolError('Actor activity differs from native session state')
                if network_turn.is_diplomacy_decisions(decisions):
                    from .player_view import validate_player_map
                    validate_player_map(decisions['player_map'],observation)
            if not (network_turn.is_world_war_decisions(decisions)
                    or network_turn.is_diplomacy_decisions(decisions)):
                _public_contracts(decisions, observation, ended)
            if (decisions.get('schema') in network_turn.WORK_SCHEMAS
                    and decisions.get('unit_work_state') is not None):
                from .contracts.unit_work_state import validate as validate_work_state
                validate_work_state(decisions['unit_work_state'],pid,observation['turn'],
                    observation=observation,work_catalog=decisions.get('unit_work'))
            if decisions.get('schema') in network_turn.INFO_SCHEMAS and decisions.get('unit_work_info') is not None:
                from .contracts.unit_work_info import validate as validate_work_info
                validate_work_info(decisions['unit_work_info'],pid,observation['turn'],
                    observation=observation,work_catalog=decisions.get('unit_work'))
            if decisions.get('schema') in network_turn.GROWTH_SCHEMAS and decisions.get('city_growth') is not None:
                from .contracts.city_growth import validate as validate_growth
                validate_growth(decisions['city_growth'],pid,observation['turn'],observation=observation)

        requested_action = command['requested_action']
        if operation == 'act':
            if prior_view is None:
                raise ProtocolError('Action reply has no cached actor catalogue')
            chosen = next(row['action'] for row in prior_view['decisions']['candidates']
                          if row['candidate_id'] == request['selection']['candidate_id'])
            if chosen.get('kind') == 'policies':
                candidate = policies.choose(chosen['slots'], request['selection']['parameters']['assignments'],
                                            requested_player, prior_view['decisions']['turn'],
                                            allow_relocation=(prior_view['decisions'].get('schema') in
                                                network_turn.POLICY_RELOCATION_CAPABILITY_SCHEMAS),
                                            allow_unchanged=(prior_view['decisions'].get('schema') in
                                                network_turn.POLICY_RECONFIRM_CAPABILITY_SCHEMAS))
                if _digest(requested_action) != _digest(dict(kind='policies', candidate=candidate)):
                    raise ProtocolError('Policy choice was substituted')
            elif (type(chosen.get('kind')) is str and chosen.get('kind').startswith('congress_')):
                from .contracts import world_congress
                selected = world_congress.choose(prior_view['decisions']['world_congress'],
                    chosen, request['selection'].get('parameters'))
                if _digest(requested_action) != _digest(selected):
                    raise ProtocolError('Congress choice was substituted')
            elif _digest(requested_action) != _digest(chosen):
                raise ProtocolError('Requested action differs from the selected actor choice')

        applied = response['applied_action']
        if operation != 'act' or command['status'] != 'completed':
            if applied is not None:
                raise ProtocolError('Host claimed an action outside a completed action RPC')
        elif _digest(applied) != _digest(requested_action):
            raise ProtocolError('Applied action differs from the requested action')

        turn_changed = self._session is not None and session['turn'] != self._session['turn']
        if operation == 'reset':
            self._episode_local_player = session['local_player_id']
            self._command_receipts.clear()
        elif operation == 'act':
            self._command_receipts[requested_player] = dict(
                schema='civ6-host.command-receipt.v1', episode_id=episode,
                game_generation=generation, player_id=requested_player,
                sequence=response['sequence'], decision_turn=prior_view['decisions']['turn'],
                response_turn=session['turn'], selection=copy.deepcopy(request['selection']),
                command_result=copy.deepcopy(command))
        if operation == 'reset' or turn_changed:
            self._views = {}
            self._display_views.clear()
            self._last_player_id = None
        self._reply = copy.deepcopy(response)
        self._session = session
        if result['terminated'] or result['truncated']:
            # A terminal reply can legitimately have no board. Never return a
            # stale live catalogue, including one cached for another human.
            pid = session['local_player_id'] if requested_player is None else requested_player
            self._views = {pid: copy.deepcopy(response)}
            self._last_player_id = pid
        elif observation is not None:
            self._views[observation['player_id']] = copy.deepcopy(response)
            self._last_player_id = observation['player_id']
        elif operation == 'close' and self._last_player_id is not None:
            self._views[self._last_player_id] = copy.deepcopy(response)
        self._closed = operation == 'close'
        return self.view()

    def reset(self):
        self._check_owner()
        try:
            return self._accept(self._backend.reset(), 'reset')
        except BaseException:
            self._abort_failed()
            raise

    def _send(self, operation, player_id, selection=None, prior_view=None):
        self._check_owner()
        pid = _player_id(player_id)
        if self._reply is None or self._closed:
            raise RuntimeError('No usable LAN session; reset required')
        if operation != 'close' and any(self._reply['outcome'][k] for k in ('terminated', 'truncated')):
            raise RuntimeError('Session ended; close or reset required')
        if pid not in self._session['human_player_ids']:
            raise ProtocolError('Requested actor is not a captured human player')
        if operation == 'act' and pid not in self._session['active_human_player_ids']:
            offers = prior_view['decisions']['candidates'] if prior_view else []
            chosen = [row['action'] for row in offers
                      if row['candidate_id'] == selection['candidate_id']]
            controls = prior_view['decisions'].get('turn_controls') if prior_view else None
            unready = (chosen == [{'kind': 'unready_turn'}] and controls is not None
                       and network_turn.unready_action_available(controls))
            dialogue = (prior_view is not None
                        and prior_view['decisions'].get('base_schema') in network_turn.DIALOGUE_SCHEMAS
                        and len(chosen) == 1 and chosen[0].get('kind') == 'diplomacy_response')
            forced = (prior_view is not None and len(chosen)==1
                      and network_turn.offered_forced_turn(prior_view['decisions'],chosen[0]))
            if not (unready or dialogue or forced):
                raise ProtocolError('Inactive actor requires an offered Unready, forced turn or dialogue response')
        request = {k: self._reply[k] for k in ('schema', 'nonce', 'episode_id', 'game_generation')}
        request.update(sequence=self._reply['sequence'] + 1, operation=operation, player_id=pid)
        if selection is not None:
            request['selection'] = copy.deepcopy(selection)
        try:
            return self._accept(self._backend.request(request), operation, request=request,
                                prior_view=prior_view, requested_player=pid)
        except BaseException:
            self._abort_failed()
            raise

    def observe(self, player_id):
        return self._send('observe', player_id)

    def poll(self, player_id):
        return self._send('poll', player_id)

    def view(self, player_id=None):
        self._check_owner()
        if player_id is None:
            player_id = self._last_player_id
        if player_id is None:
            raise RuntimeError('No cached actor view; reset or observe first')
        player_id = _player_id(player_id)
        if player_id not in self._views:
            raise RuntimeError('No cached actor view; reset or observe first')
        self._last_player_id = player_id
        return self._actor_view(self._views[player_id])

    def information(self, group, *, player_id=None, channel='public'):
        """Query a typed information group at an already observed boundary.

        This performs no RPC or gameplay action. Call observe/poll to obtain a
        new native boundary. Same-turn cached views keep their original sequence;
        they are not silently relabelled after another player's command.

        Administrative access requires explicit construction-time opt-in. It is
        a client API guard, not authentication against a caller who controls the
        Python process or a remote transport's authorization mechanism.
        """
        self._check_owner()
        from .contracts.information import PUBLIC_GROUPS, envelope, project, required_fields
        if type(group) is not str or (group not in PUBLIC_GROUPS
                and not (group == 'turn_horizon' and channel == 'administrative')):
            raise ValueError('Unsupported information group')
        if type(channel) is not str or channel not in ('public', 'administrative'):
            raise ValueError('Unsupported information channel')
        if channel == 'administrative' and not self._allow_administrative:
            raise PermissionError('Administrative information was not enabled for this client')
        if self._reply is None or self._closed:
            raise InformationUnavailable('Reset and observe an active session first')
        if any(self._reply['outcome'][key] for key in ('terminated', 'truncated')):
            raise InformationUnavailable('Session ended; historical live information is not returned')
        pid = self._last_player_id if player_id is None else _player_id(player_id)
        if pid is None or pid not in self._views:
            raise InformationUnavailable('Observe this player before querying information')
        response = self._views[pid]
        observation, decisions = response['observation'], response['decisions']
        if (observation is None or decisions is None
                or any(response[key] != self._reply[key]
                       for key in ('episode_id', 'game_generation'))
                or observation['turn'] != self._session['turn']):
            raise InformationUnavailable('Cached information is from another episode or turn')
        required = set() if group == 'turn_horizon' else set(required_fields(group, decisions.get('schema')))
        if group == 'economy' and channel == 'administrative':
            required.add('research_progress')
        if any(field not in decisions or decisions[field] is None for field in required):
            if (decisions.get('schema') in network_turn.NATIVE_COMMAND_PERMISSIONS_SCHEMAS
                    and not decisions['native_command_permissions']['allow_strategic']
                    and group in ('production', 'combat')):
                raise InformationUnavailable(group + ' information is unavailable: '
                    + network_turn.NATIVE_STRATEGIC_READER_UNAVAILABLE)
            raise InformationUnavailable(group + ' information is unavailable at this waiting/modal boundary')
        if group=='combat':
            if decisions.get('schema') not in network_turn.PUBLIC_COMBAT_CAPABILITY_SCHEMAS:
                raise InformationUnavailable('This historical catalogue lacks the qualified combat projection')
        if group == 'production':
            from .contracts.production_inputs import CURRENT_SCHEMA
            if (decisions.get('schema') in network_turn.CURRENT_PRODUCTION_CAPABILITY_SCHEMAS
                    and channel == 'administrative'):
                raise InformationUnavailable('Administrative production is unavailable for this profile')
            production = decisions.get('production_current', decisions.get('production'))
            if production is None or production.get('schema') != CURRENT_SCHEMA:
                raise InformationUnavailable('This historical catalogue lacks the qualified production projection')
        try:
            if channel == 'public':
                if group == 'display':
                    if getattr(self._backend, '_display_projection_enabled', False) is not True:
                        raise InformationUnavailable('Display information requires the selected XP2 diagnostic')
                    from .contracts.information import project_cached_display
                    data = project_cached_display(self._actor_view(response))
                else:
                    data = project(group, observation, decisions)
            elif group == 'economy':
                from .contracts.economy_inputs import administrative
                data = administrative(observation, decisions)
            elif group in ('production', 'growth', 'combat', 'turn_horizon'):
                reader = getattr(self._backend, 'read_administrative', None)
                if reader is None:
                    raise InformationUnavailable('Backend administrative information capture is not available')
                reader_input = copy.deepcopy(response)
                data = reader(group, reader_input)
                if _digest(reader_input) != _digest(response):
                    raise ProtocolError('Administrative reader mutated its native response input')
                if data is None:
                    raise InformationUnavailable('No administrative readback at this exact cached boundary')
                from .contracts.information import validate_administrative
                data = validate_administrative(group, data, response)
            else:
                raise InformationUnavailable('Administrative channel is not qualified for ' + group)
        except (ValueError, KeyError, TypeError) as exc:
            raise ProtocolError('Invalid native ' + group + ' information: ' + str(exc)) from exc
        source_fields = {
            'display': (),
            'turn_horizon': (),
            'economy': ('treasury','yield_display','research_info','research_progress'),
            'production': ('production','production_info','production_current'),
            'growth': ('city_growth',),
            'strategic_resources': ('strategic_resources',),
            'diplomacy': ('diplomacy_overview',),
            'trade': ('trade_routes', 'trade_origins'),
            'espionage': ('espionage',),
            'spy_completion': ('spy_completion',),
            'world_congress': ('world_congress',),
            'world_congress_review': ('world_congress_review',),
            'native_command_permissions': ('native_command_permissions',),
            'world_congress_active_effects': ('world_congress_active_effects',),
            'combat': ('unit_attacks','queued_orders'),
            'unit_work': ('unit_work_state','unit_work_info','unit_work'),
        }[group]
        # Some native subcatalogues (notably unit_work) are versioned by their
        # enclosing decision catalogue, not by a fabricated nested schema.
        sources = {key: decisions[key]['schema'] for key in source_fields
                   if isinstance(decisions.get(key), dict) and 'schema' in decisions[key]}
        if group == 'display':
            sources['display_projection'] = data['schema']
        if 'schema' in decisions:
            sources['decision_catalogue'] = decisions['schema']
        return envelope(response, group, channel, data, sources)

    def _actor_view(self, response):
        if (getattr(self._backend, '_display_projection_enabled', False) is not True
                or response['observation'] is None):
            return self._legacy_actor_view(response)
        if response['outcome']['terminated']:
            # The display formatter only owns live observations. Preserve the
            # public result without exposing the unformatted precision.
            return dict(self._legacy_actor_view(response), observation=None, decisions=None)
        from .contracts import player_display
        # Existing private native v1 cache is retained for legality, Save and
        # provenance. Only this detached versioned public envelope changes.
        private_digest = _digest(response)
        pid = response['observation']['player_id']
        prior = self._display_views.get(pid)
        if prior is not None and prior[0] == private_digest:
            return copy.deepcopy(prior[1])
        reader = getattr(self._backend, '_read_player_display_projection', None)
        if reader is None:
            raise InformationUnavailable('No source-bound CityPanel/TopPanel display receipt at this response')
        reader_input = copy.deepcopy(response)
        projected = reader(reader_input)
        if _digest(reader_input) != private_digest:
            raise ProtocolError('Display reader mutated its native response input')
        projected = player_display.validate_public(projected)
        player_display.validate_relation(response['observation'], projected)
        if (any(projected[k] != response[k] for k in ('episode_id','game_generation','sequence'))
                or projected['observation']['player_id'] != pid
                or projected['observation']['turn'] != response['observation']['turn']
                or _digest(projected['decisions']) != _digest(response['decisions'])
                or _digest(projected['applied_action']) != _digest(response['applied_action'])
                or projected['outcome'] != {k:response['outcome'][k] for k in ('terminated','truncated','reason')}):
            raise ProtocolError('Display projection differs from the cached native response')
        self._display_views[pid] = (private_digest, copy.deepcopy(projected))
        return copy.deepcopy(projected)

    @staticmethod
    def _legacy_actor_view(response):
        result = response['outcome']
        public_outcome = {key: result[key] for key in ('terminated', 'truncated', 'reason')}
        if result['terminated']:
            public_outcome['result'] = project_terminal_result(result,
                episode_id=response['episode_id'], game_generation=response['game_generation'],
                player_id=result['native_victory']['player_id'], turn=response['session']['turn'])
        return copy.deepcopy(dict(episode_id=response['episode_id'],
            game_generation=response['game_generation'], sequence=response['sequence'],
            turn_mode='simultaneous', observation=response['observation'],
            decisions=response['decisions'], applied_action=response['applied_action'],
            outcome=public_outcome))

    def act(self, player_id, decision_id, candidate_id, parameters=None):
        self._check_owner()
        pid = _player_id(player_id)
        if self._reply is None or self._closed:
            raise RuntimeError('Reset before choosing an action')
        if any(self._reply['outcome'][key] for key in ('terminated', 'truncated')):
            raise RuntimeError('Session ended; close or reset required')
        prior_view = self._views.get(pid)
        if prior_view is None:
            raise ProtocolError('No cached catalogue for this actor')
        decisions = prior_view['decisions']
        if type(decision_id) is not str or decisions['decision_id'] != decision_id:
            raise ProtocolError('Stale decision catalogue for this actor')
        matches = [row for row in decisions['candidates'] if row['candidate_id'] == candidate_id]
        if len(matches) != 1:
            raise ProtocolError('Candidate is absent from this actor catalogue')
        action = matches[0]['action']
        if action.get('kind') == 'policies':
            if type(parameters) is not dict or set(parameters) != {'assignments'}:
                raise ProtocolError('Explicit policy assignments required')
            try:
                policies.choose(action['slots'], parameters['assignments'], pid, decisions['turn'],
                    allow_relocation=(decisions.get('schema') in
                        network_turn.POLICY_RELOCATION_CAPABILITY_SCHEMAS),
                    allow_unchanged=(decisions.get('schema') in
                        network_turn.POLICY_RECONFIRM_CAPABILITY_SCHEMAS))
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        elif (type(action.get('kind')) is str and action.get('kind').startswith('congress_')):
            from .contracts import world_congress
            try:
                world_congress.choose(decisions['world_congress'], action, parameters)
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        elif parameters is not None:
            raise ProtocolError('This action accepts no additional parameters')
        selection = dict(decision_id=decision_id, candidate_id=candidate_id)
        if parameters is not None:
            selection['parameters'] = parameters
        return self._send('act', pid, selection, prior_view=prior_view)

    def congress_ballot_draft(self, player_id, parameters):
        """Prepare an unsent complete ballot from this actor's cached view."""
        self._check_owner()
        pid = _player_id(player_id)
        view = self._views.get(pid)
        if self._closed or view is None:
            raise ProtocolError('No current Congress view for this actor')
        from .contracts import world_congress
        value = view['decisions'].get('world_congress')
        if value is None:
            raise InformationUnavailable('Public Congress information is unavailable')
        try:
            return world_congress.ballot_draft(value, parameters)
        except ValueError as exc:
            raise ProtocolError(str(exc)) from exc

    @property
    def session_state(self):
        self._check_owner()
        if self._session is None:
            raise RuntimeError('Reset before reading administrative session state')
        return copy.deepcopy(self._session)

    @property
    def command_result(self):
        """Detached administrative receipt; intentionally excluded from actor views."""
        self._check_owner()
        if self._reply is None:
            raise RuntimeError('Reset before reading the command result')
        return copy.deepcopy(self._reply['command_result'])

    def last_command_receipt(self, player_id):
        """Return this human's latest validated action receipt in the episode."""
        self._check_owner()
        pid = _player_id(player_id)
        if self._session is None:
            raise RuntimeError('Reset before reading a command receipt')
        if pid not in self._session['human_player_ids']:
            raise ProtocolError('Requested actor is not a captured human player')
        return copy.deepcopy(self._command_receipts.get(pid))

    def close(self, player_id=None):
        self._check_owner()
        if self._closed:
            return None
        if player_id is None:
            player_id = self._last_player_id
        if player_id is None:
            player_id = self._session['local_player_id']
        return self._send('close', player_id)

    def abort(self):
        self._check_owner()
        self._closed = True
        self._backend.abort('session_client_abort')

    def __enter__(self):
        return self

    def __exit__(self, kind, exc, traceback):
        self.close() if kind is None else self.abort()

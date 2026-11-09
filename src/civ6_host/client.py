"""Client for the existing explicit-choice hotseat wire contract.

The backend owns native validation, provenance, resource bounds and process
cleanup. It must implement reset/request/abort; the retained NativeHotseatActionSession
is one such backend. This module does not load the DLL, choose actions or
implement simultaneous scheduling. No learner or lab imports are required.

The existing host envelope remains unchanged. Internal victory evidence and
reactivation receipts never enter the returned player view. Public contracts
are validated here as well as by the current native backend.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from typing import Protocol
from uuid import UUID

from .contracts import plot_display990, policies, production_info988, research_info983, yield_display982
from .player_view import validate_player_view

SCHEMA = "civ6rl.hotseat_action_session923.v1"
_ENVELOPE = frozenset(("stage", "schema", "nonce", "episode_id", "game_generation", "sequence",
    "operation", "observation", "rounds", "outcome", "automatic_choices_applied",
    "action_interface_complete", "strategic_training_ready", "decisions", "applied_action"))


class ProtocolError(ValueError):
    """A malformed/foreign reply or a stale local choice; not a game victory."""


class InformationUnavailable(RuntimeError):
    """The requested information is not present at this cached native boundary."""


class SessionBackend(Protocol):
    """Trusted, bounded native provider. Refusals are raised, never substituted."""
    def reset(self) -> dict: ...
    def request(self, request: dict) -> dict: ...
    def abort(self, reason: str = "parent_abort") -> None: ...
    def read_player_view(self, reply: dict, player_id: int) -> dict: ...


def _digest(value):
    # Preserve native_saved_actions.digest's canonical representation.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def _public_contracts(decisions, observation, ended):
    pid, turn = observation["player_id"], observation["turn"]
    if "yield_display" in decisions:
        yield_display982.validate(decisions["yield_display"], pid, turn, observation)
    if "production_info" in decisions:
        from .contracts.production_inputs import validate as validate_production
        validate_production(decisions["production_info"], pid, turn,
            candidates=decisions["candidates"], observation=observation, ended=ended)
    if decisions.get('production',{}).get('schema')=='civ6-host.current-production.v1':
        from .contracts.production_inputs import validate_current
        validate_current(decisions['production'],pid,turn,observation=observation,
                         queues=decisions.get('production_queues'))
    if "research_info" in decisions:
        research_info983.validate(decisions["research_info"], pid, turn,
            research=decisions["research"], candidates=None if ended else decisions["candidates"])
    if "plot_info" in decisions:
        plot_display990.validate_and_index(decisions["plot_info"], pid, turn, decisions["player_map"])
    if ('trade_routes' in decisions or 'trade_origins' in decisions
            or any(row['action'].get('kind') in ('make_trade_route', 'change_trade_origin')
                   for row in decisions['candidates'])):
        from .contracts.trade import validate_decisions as validate_trade_decisions
        validate_trade_decisions(decisions, observation, actions_closed=ended)
    if ('espionage' in decisions
            or any(row['action'].get('kind') in ('spy_travel', 'spy_mission', 'spy_cancel', 'spy_escape')
                   for row in decisions['candidates'])):
        from .contracts import espionage, network_turn
        if decisions.get('schema') not in network_turn.ESPIONAGE_CAPABILITY_SCHEMAS:
            raise ValueError('Espionage requires its explicit capability revision')
        catalogue = decisions.get('espionage')
        if catalogue is not None:
            espionage.compare_own(catalogue, observation)
        offered = [row['action'] for row in decisions['candidates']
                   if row['action'].get('kind') in espionage.ACTION_FIELDS]
        if offered != ([] if ended else espionage.actions(catalogue)):
            raise ValueError('Espionage choices differ from the native catalogue')
    if ('spy_completion' in decisions
            or any(row['action'].get('kind') in ('spy_renew', 'spy_completion_dismiss')
                   for row in decisions['candidates'])):
        from .contracts import spy_completion, network_turn
        if decisions.get('schema') not in network_turn.SPY_COMPLETION_CAPABILITY_SCHEMAS:
            raise ValueError('Spy completion requires its explicit capability revision')
        catalogue = decisions.get('spy_completion')
        if catalogue is not None:
            spy_completion.compare_own(catalogue, observation)
        offered = [row['action'] for row in decisions['candidates']
                   if row['action'].get('kind') in spy_completion.ACTION_FIELDS]
        if offered != ([] if ended else spy_completion.actions(catalogue)):
            raise ValueError('Spy completion choices differ from the native catalogue')

    if ('world_congress' in decisions
            or any((type(row['action'].get('kind')) is str and row['action'].get('kind').startswith('congress_'))
                   for row in decisions['candidates'])):
        from .contracts import world_congress, network_turn
        if decisions.get('schema') not in network_turn.WORLD_CONGRESS_CAPABILITY_SCHEMAS:
            raise ValueError('Congress requires its explicit capability revision')
        catalogue = decisions.get('world_congress')
        if catalogue is not None:
            world_congress.compare_own(catalogue, observation, decisions['sequence'])
        offered = [row['action'] for row in decisions['candidates']
                   if row['action'].get('kind') in world_congress.CANDIDATE_FIELDS]
        if offered != ([] if ended else world_congress.actions(catalogue)):
            raise ValueError('Congress choices differ from the source catalogue')


class HotseatClient:
    """Explicit client of the current hotseat profile, not a universal Civ6 env.

    Each public view is detached. Choose from that view with its decision_id;
    the client neither filters choices strategically nor inserts fallback actions.
    A response failure makes the session unusable until reset; no action retry
    occurs because its native application may already have happened.
    """
    turn_mode = "hotseat"

    def __init__(self, backend: SessionBackend):
        self._backend = backend
        self._reply = None
        self._closed = True
        self._owner = threading.get_ident()

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("Use this hotseat client from its owning thread")

    def _accept(self, response, operation, *, request=None):
        if type(response) is not dict or set(response) not in (_ENVELOPE, _ENVELOPE | {"turn_reactivation"}):
            raise ProtocolError("Unexpected host envelope fields")
        if (response["stage"] != "official_session_response" or response["schema"] != SCHEMA
                or response["operation"] != operation or response["automatic_choices_applied"] is not False
                or response["action_interface_complete"] is not False
                or response["strategic_training_ready"] is not False):
            raise ProtocolError("Unsupported or automatic host response")
        episode, generation, nonce = (response[k] for k in ("episode_id", "game_generation", "nonce"))
        if (type(episode) is not str or str(UUID(episode)) != episode
                or generation != "native-" + episode or type(nonce) is not str or len(nonce) != 32
                or any(c not in "0123456789abcdef" for c in nonce)):
            raise ProtocolError("Invalid native session identity")
        if type(response["sequence"]) is not int or response["sequence"] < 0:
            raise ProtocolError("Invalid response sequence")
        if operation == "reset":
            if response["sequence"] != 0:
                raise ProtocolError("Reset must start a new sequence")
            if self._reply is not None and self._reply["episode_id"] == episode:
                raise ProtocolError("Reset reused an existing episode")
        elif request is None or any(response[k] != request[k] for k in
                ("nonce", "episode_id", "game_generation", "sequence")):
            raise ProtocolError("Foreign or out-of-order host response")
        result = response["outcome"]
        if (type(result) is not dict or type(result.get("terminated")) is not bool
                or type(result.get("truncated")) is not bool
                or result["terminated"] and result["truncated"]):
            raise ProtocolError("Invalid terminal/truncation outcome")
        observation, decisions = response["observation"], response["decisions"]
        if observation is None or decisions is None:
            if result["terminated"] is not True:
                raise ProtocolError("Non-terminal reply lost its player state")
        else:
            if (type(observation) is not dict or type(decisions) is not dict
                    or type(observation.get("player_id")) is not int
                    or type(observation.get("turn")) is not int
                    or not 0 <= observation["player_id"] < 64 or observation["turn"] < 0):
                raise ProtocolError("Invalid player perspective")
            expected = dict(episode_id=episode, game_generation=generation, sequence=response["sequence"],
                            player_id=observation["player_id"], turn=observation["turn"])
            if any(type(decisions.get(k)) is not type(v) or decisions[k] != v for k,v in expected.items()):
                raise ProtocolError("Decision catalogue and player boundary differ")
            if decisions.get("decision_id") != _digest({k:v for k,v in decisions.items() if k != "decision_id"}):
                raise ProtocolError("Decision catalogue digest differs")
            candidates = decisions.get("candidates")
            if type(candidates) is not list:
                raise ProtocolError("Candidate list missing")
            ids = []
            for row in candidates:
                if (type(row) is not dict or type(row.get("candidate_id")) is not str
                        or type(row.get("action")) is not dict):
                    raise ProtocolError("Malformed native candidate")
                ids.append(row["candidate_id"])
            if len(set(ids)) != len(ids) or ((result["terminated"] or result["truncated"]) and candidates):
                raise ProtocolError("Duplicate or closed native choices")
            _public_contracts(decisions, observation, result["terminated"] or result["truncated"])
        if operation != "act" and response["applied_action"] is not None:
            raise ProtocolError("Host applied an unsolicited action")
        if operation == "act":
            prior = self._reply["decisions"]
            chosen = next(r["action"] for r in prior["candidates"]
                          if r["candidate_id"] == request["selection"]["candidate_id"])
            applied = response["applied_action"]
            if chosen.get("kind") == "policies":
                candidate = policies.choose(chosen["slots"], request["selection"]["parameters"]["assignments"],
                                            prior["player_id"], prior["turn"])
                if _digest(applied) != _digest(dict(kind="policies", candidate=candidate)):
                    raise ProtocolError("Policy choice was substituted")
            elif (type(chosen.get("kind")) is str and chosen.get("kind").startswith("congress_")):
                from .contracts import world_congress
                selected = world_congress.choose(prior["world_congress"], chosen,
                    request["selection"].get("parameters"))
                if _digest(applied) != _digest(selected):
                    raise ProtocolError("Congress choice was substituted")
            elif _digest(applied) != _digest(chosen):
                raise ProtocolError("Applied action differs from caller choice")
        self._reply = copy.deepcopy(response)
        self._closed = operation == "close"
        return self.view()

    def _abort_failed(self):
        self._closed = True
        self._backend.abort("host_client_exchange_failed")

    def reset(self):
        self._check_owner()
        try:
            return self._accept(self._backend.reset(), "reset")
        except BaseException:
            self._abort_failed()
            raise

    def view(self):
        self._check_owner()
        if self._reply is None:
            raise RuntimeError("Reset before requesting a player view")
        r = self._reply
        result = r["outcome"]
        # Do not return raw native_victory evidence, nonce, private sidecars or
        # host callback information as actor inputs.
        return copy.deepcopy(dict(episode_id=r["episode_id"], game_generation=r["game_generation"],
            sequence=r["sequence"], turn_mode=self.turn_mode, observation=r["observation"],
            decisions=r["decisions"], applied_action=r["applied_action"],
            outcome={k:result[k] for k in ("terminated", "truncated", "reason")}))

    def _send(self, operation, selection=None):
        self._check_owner()
        if self._reply is None or self._closed:
            raise RuntimeError("No usable live client session; reset required")
        if operation != "close" and any(self._reply["outcome"][k] for k in ("terminated", "truncated")):
            raise RuntimeError("Episode ended; close or reset required")
        request = {k:self._reply[k] for k in ("schema", "nonce", "episode_id", "game_generation")}
        request.update(sequence=self._reply["sequence"]+1, operation=operation)
        if selection is not None:
            request["selection"] = copy.deepcopy(selection)
        try:
            return self._accept(self._backend.request(request), operation, request=request)
        except BaseException:
            self._abort_failed()
            raise

    def observe(self):
        return self._send("observe")

    def information(self, group, *, player_id=None, channel='public'):
        """Read trade information for the current actor from the accepted reply."""
        self._check_owner()
        from .contracts.information import envelope, project, required_fields
        if group != 'trade' or channel != 'public':
            raise ValueError('Hotseat supports the public trade information group')
        if player_id is not None and (type(player_id) is not int or not 0 <= player_id < 64):
            raise ValueError('player_id must be an integer in [0, 63]')
        response = self._reply
        if (response is None or self._closed
                or any(response['outcome'][key] for key in ('terminated', 'truncated'))):
            raise InformationUnavailable('Reset and observe an active hotseat session first')
        observation, decisions = response['observation'], response['decisions']
        if player_id is not None and player_id != observation['player_id']:
            raise InformationUnavailable('Trade information requires this player to be the current actor')
        if any(decisions.get(field) is None for field in required_fields(group)):
            raise InformationUnavailable('Trade information is unavailable at this hotseat boundary')
        data = project(group, observation, decisions)
        sources = {'decision_catalogue': decisions['schema']} if 'schema' in decisions else {}
        return envelope(response, group, channel, data, sources)

    def player_view(self, player_id):
        """Read one backend-authorized public perspective without changing choices."""
        self._check_owner()
        if type(player_id) is not int or not 0 <= player_id < 64:
            raise ValueError("player_id must be an integer in [0, 63]")
        if self._reply is None or self._closed:
            raise RuntimeError("Reset before requesting a public player view")
        if any(self._reply["outcome"][key] for key in ("terminated", "truncated")):
            raise RuntimeError("Episode ended; public player view is unavailable")
        try:
            original_reply = self._reply
            reply_snapshot = copy.deepcopy(original_reply)
            value = self._backend.read_player_view(original_reply, player_id)
            if original_reply != reply_snapshot:
                self._reply = reply_snapshot
                raise ProtocolError("Backend mutated the current action reply while reading a player view")
            try:
                return validate_player_view(value, episode_id=self._reply["episode_id"],
                    game_generation=self._reply["game_generation"], sequence=self._reply["sequence"],
                    player_id=player_id, turn=self._reply["observation"]["turn"])
            except (ValueError, TypeError, OverflowError) as exc:
                raise ProtocolError(str(exc)) from exc
        except BaseException:
            self._abort_failed()
            raise

    def act(self, decision_id, candidate_id, *, parameters=None):
        self._check_owner()
        if self._reply is None or self._closed:
            raise RuntimeError("Reset before choosing an action")
        decisions = self._reply["decisions"]
        if type(decisions) is not dict or decisions["decision_id"] != decision_id:
            raise ProtocolError("Stale decision catalogue")
        matches = [r for r in decisions["candidates"] if r["candidate_id"] == candidate_id]
        if len(matches) != 1:
            raise ProtocolError("Candidate is not in the current native catalogue")
        action = matches[0]["action"]
        if action.get("kind") == "policies":
            if type(parameters) is not dict or set(parameters) != {"assignments"}:
                raise ProtocolError("Explicit policy assignments required")
            try:
                policies.choose(action["slots"], parameters["assignments"],
                                decisions["player_id"], decisions["turn"])
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        elif (type(action.get("kind")) is str and action.get("kind").startswith("congress_")):
            from .contracts import world_congress
            try:
                world_congress.choose(decisions["world_congress"], action, parameters)
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        elif parameters is not None:
            raise ProtocolError("This action accepts no additional parameters")
        selection = dict(decision_id=decision_id, candidate_id=candidate_id)
        if parameters is not None:
            selection["parameters"] = parameters
        return self._send("act", selection)

    def close(self):
        self._check_owner()
        return None if self._closed else self._send("close")

    def abort(self):
        self._check_owner()
        self._closed = True
        self._backend.abort("host_client_abort")

    def __enter__(self):
        return self

    def __exit__(self, kind, exc, traceback):
        self.close() if kind is None else self.abort()

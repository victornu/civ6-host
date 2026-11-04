"""Bounded per-player snapshots for the existing explicit-choice adapters.

This stores only the owner aliases consumed by ``native_saved_actions`` and
its adapters. It does not admit a turn mode, validate an action, or change the
existing hotseat/perspective checks in those callers.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import sys
from typing import Any, Iterator
from uuid import UUID


DECISION_FIELDS = (
    "explicit_observation",
    "explicit_decision_player_id",
    "explicit_decision_candidates",
    "explicit_combat_units",
    "explicit_combat_cities",
    "explicit_government",
    "explicit_pantheon",
    "explicit_promotions",
    "explicit_unit_orders",
    "explicit_unit_upgrades",
    "explicit_production_snapshot",
    "explicit_production_queues",
    "explicit_city_shots",
    "explicit_district_shots",
    "explicit_trade_routes",
    "explicit_trade_origins",
    "explicit_envoys",
    "explicit_envoy_panel",
    "explicit_great_people",
    "explicit_religion",
    "explicit_captured_city",
    "explicit_world_input",
)
_MISSING = object()
MAX_ROSTER = 64
MAX_PLAYER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_VALUE_NODES = 250_000
MAX_VALUE_DEPTH = 256


def _validate_scope(episode_id: str, game_generation: str, roster: tuple[int, ...],
                    player_id: int, turn: int) -> tuple[str, str, tuple[int, ...], int]:
    if (type(episode_id) is not str or type(game_generation) is not str):
        raise ValueError("Decision context needs an episode identity")
    try:
        canonical_episode = str(UUID(episode_id))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Decision context episode ID is not canonical") from exc
    if episode_id != canonical_episode or game_generation != "native-" + episode_id:
        raise ValueError("Decision context episode generation does not match")
    if (type(roster) is not tuple or not 1 <= len(roster) <= MAX_ROSTER
            or any(type(pid) is not int or not 0 <= pid <= 63 for pid in roster)
            or len(set(roster)) != len(roster)):
        raise ValueError("Decision context roster is invalid")
    if type(player_id) is not int or player_id not in roster:
        raise ValueError("Decision context player is outside the roster")
    if type(turn) is not int or not 0 <= turn <= 2 ** 31 - 1:
        raise ValueError("Decision context turn is invalid")
    return episode_id, game_generation, roster, turn


def _bounded_size(root: Any) -> int:
    """Estimate retained size before copying; reject cycles and opaque values."""
    pending = [(root, 0, False)]
    active: set[int] = set()
    done: set[int] = set()
    total = 0
    nodes = 0
    while pending:
        value, depth, exiting = pending.pop()
        ident = id(value)
        if exiting:
            active.remove(ident)
            done.add(ident)
            continue
        if ident in active:
            raise ValueError("Decision context contains a cycle")
        if ident in done:
            continue
        if depth > MAX_VALUE_DEPTH:
            raise ValueError("Decision context exceeds its nesting-depth bound")
        nodes += 1
        if nodes > MAX_VALUE_NODES:
            raise ValueError("Decision context exceeds its object-count bound")
        children = ()
        if value is None or type(value) in (bool, int, float):
            total += sys.getsizeof(value)
        elif type(value) is str:
            total += sys.getsizeof(value)
        elif type(value) is bytes:
            total += sys.getsizeof(value)
        elif type(value) is dict:
            container_size = sys.getsizeof(value)
            child_count = 2 * len(value)
            if child_count > MAX_VALUE_NODES - nodes - len(pending):
                raise ValueError("Decision context exceeds its object-count bound")
            if total + container_size > MAX_PLAYER_BYTES:
                raise ValueError("Decision context exceeds its per-player byte bound")
            total += container_size
            children = tuple(value.keys()) + tuple(value.values())
        elif type(value) in (list, tuple, set, frozenset):
            container_size = sys.getsizeof(value)
            if len(value) > MAX_VALUE_NODES - nodes - len(pending):
                raise ValueError("Decision context exceeds its object-count bound")
            if total + container_size > MAX_PLAYER_BYTES:
                raise ValueError("Decision context exceeds its per-player byte bound")
            total += container_size
            children = tuple(value)
        else:
            raise TypeError("Decision context contains an unsupported value: "
                            + type(value).__name__)
        if total > MAX_PLAYER_BYTES:
            raise ValueError("Decision context exceeds its per-player byte bound")
        active.add(ident)
        pending.append((value, depth, True))
        pending.extend((child, depth + 1, False) for child in reversed(children))
    return total


class DecisionContextStore:
    """One bounded decision cache, normally attached to one session owner."""

    def __init__(self) -> None:
        self._scope: tuple[str, str, tuple[int, ...], int] | None = None
        self._records: dict[int, tuple[dict[str, Any], int, str, int]] = {}
        self._bytes = 0

    @property
    def snapshot_count(self) -> int:
        return len(self._records)

    @property
    def accounted_bytes(self) -> int:
        return self._bytes

    def _emit(self, owner: Any, event: str, *, reason: str, player_id: int | None,
              scope: tuple[str, str, tuple[int, ...], int] | None,
              decision_id: str | None = None, sequence: int | None = None) -> None:
        emit = getattr(owner, "emit", None)
        if not callable(emit):
            return
        effective = scope or self._scope
        payload: dict[str, Any] = {
            "reason": reason,
            "player_id": player_id,
            "snapshot_count": len(self._records),
            "accounted_bytes": self._bytes,
        }
        if decision_id is not None:
            payload["decision_id"] = decision_id
        if sequence is not None:
            payload["sequence"] = sequence
        if effective is not None:
            episode_id, game_generation, roster, turn = effective
            payload.update(episode_id=episode_id, game_generation=game_generation,
                           roster=list(roster), turn=turn)
        emit(event, **payload)

    def _clear(self) -> None:
        self._records.clear()
        self._bytes = 0

    def _ensure_scope(self, owner: Any, scope: tuple[str, str, tuple[int, ...], int],
                      reason: str) -> None:
        if self._scope != scope:
            if self._records:
                self._clear()
                self._emit(owner, "decision_context_invalidated", reason=reason,
                           player_id=None, scope=self._scope)
            self._scope = scope

    def invalidate_player(self, owner: Any, player_id: int, *, reason: str) -> None:
        record = self._records.pop(player_id, None)
        if record is not None:
            self._bytes -= record[1]
            self._emit(owner, "decision_context_invalidated", reason=reason,
                       player_id=player_id, scope=self._scope)

    def invalidate_all(self, owner: Any, *, reason: str) -> None:
        if self._records:
            self._clear()
            self._emit(owner, "decision_context_invalidated", reason=reason,
                       player_id=None, scope=self._scope)

    def capture(self, owner: Any, *, episode_id: str, game_generation: str,
                roster: tuple[int, ...], player_id: int, turn: int,
                decision_id: str, sequence: int) -> None:
        scope = _validate_scope(episode_id, game_generation, roster, player_id, turn)
        if (type(decision_id) is not str or len(decision_id) != 64
                or any(char not in "0123456789abcdef" for char in decision_id)
                or type(sequence) is not int or not 0 <= sequence <= 2 ** 31 - 1):
            raise ValueError("Decision context needs its exact read sequence and digest")
        if getattr(owner, "explicit_decision_player_id", None) != player_id:
            raise RuntimeError("Decision aliases belong to another player")
        observation = getattr(owner, "explicit_observation", None)
        if (type(observation) is not dict or observation.get("player_id") != player_id
                or type(observation.get("turn")) is not int
                or observation.get("turn") != turn):
            raise RuntimeError("Decision observation does not match its player/turn")

        state = {name: getattr(owner, name)
                 for name in DECISION_FIELDS if hasattr(owner, name)}
        size = _bounded_size(state)
        if size > MAX_PLAYER_BYTES:
            raise ValueError("Decision context exceeds its per-player byte bound")
        # Copy the whole bundle once: shared aliases stay shared in the saved
        # context and the copy happens only after byte/node/depth admission.
        state = copy.deepcopy(state)
        previous = self._records.get(player_id) if self._scope == scope else None
        previous_size = 0 if previous is None else previous[1]
        accounted_bytes = self._bytes if self._scope == scope else 0
        if accounted_bytes - previous_size + size > MAX_TOTAL_BYTES:
            raise ValueError("Decision context cache exceeds its total byte bound")
        # Only a fully validated native read can advance the store's scope.
        self._ensure_scope(owner, scope, "episode_roster_or_turn_changed")
        self._bytes -= previous_size
        self._records[player_id] = (state, size, decision_id, sequence)
        self._bytes += size
        self._emit(owner, "decision_context_captured", reason="read_decisions",
                   player_id=player_id, scope=scope,
                   decision_id=decision_id, sequence=sequence)

    @contextmanager
    def activate(self, owner: Any, *, episode_id: str, game_generation: str,
                 roster: tuple[int, ...], player_id: int, turn: int) -> Iterator[None]:
        scope = _validate_scope(episode_id, game_generation, roster, player_id, turn)
        if self._scope != scope:
            raise RuntimeError("Requested decision context scope is stale")
        record = self._records.get(player_id)
        if record is None:
            raise RuntimeError("No current decision snapshot for this player")
        state, _size, decision_id, sequence = record
        activation_state = copy.deepcopy(state)
        baseline = {name: getattr(owner, name, _MISSING) for name in DECISION_FIELDS}
        self._emit(owner, "decision_context_activated", reason="apply_choice",
                   player_id=player_id, scope=scope,
                   decision_id=decision_id, sequence=sequence)
        try:
            for name in DECISION_FIELDS:
                if name in activation_state:
                    setattr(owner, name, activation_state[name])
                elif hasattr(owner, name):
                    delattr(owner, name)
            yield
        finally:
            for name, value in baseline.items():
                if value is _MISSING:
                    if hasattr(owner, name):
                        delattr(owner, name)
                else:
                    setattr(owner, name, value)


def store_for(owner: Any) -> DecisionContextStore:
    store = getattr(owner, "_decision_context_store", None)
    if store is None:
        store = DecisionContextStore()
        setattr(owner, "_decision_context_store", store)
    if type(store) is not DecisionContextStore:
        raise RuntimeError("Session decision-context state was replaced")
    return store

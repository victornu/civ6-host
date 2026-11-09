"""Validation for an additional player-scoped public view.

This contract carries no decisions or native-private fields. It checks the
view identity and joins the revealed map to the exact visible observation.
"""
from __future__ import annotations

import hashlib
import json
import math
import copy

SCHEMA = "civ6-host.player-view.v1"
OBSERVATION_SCHEMA = "civ6rl-player-observation-v1"
PLAYER_MAP_SCHEMA = "civ6rl.saved_player_map933.v1"
MAX_PLAYERS = 64
MAX_PLOTS = 16384
MAX_ROWS = 4096
VIEW_FIELDS = {"schema", "episode_id", "game_generation", "sequence", "player_id", "turn",
               "observation", "player_map", "player_turn"}
OBSERVATION_FIELDS = {"schema", "player_id", "turn", "width", "height", "plots", "units",
                      "visible_enemy_units", "cities", "economy"}
MAP_FIELDS = {"schema", "player_id", "turn", "width", "height", "plots",
              "visible_observation_id", "source", "historical_memory_proven",
              "graphical_differential_proven", "complete_player_observation"}
PLOT_FIELDS = {"index", "x", "y", "revealed", "terrain_type", "feature_type", "owner",
               "water", "impassable"}
RESOURCE_FIELDS = {"resource_type", "resource_count"}
OBS_PLOT_FIELDS = PLOT_FIELDS | {"visible"}
UNIT_FIELDS = {"id", "type", "x", "y", "damage", "moves", "max_moves", "owner"}
ENEMY_FIELDS = {"owner", "id", "type", "x", "y", "damage", "visible"}
CITY_FIELDS = {"id", "x", "y", "population", "owner", "yields"}
YIELD_FIELDS = {"food", "production", "gold", "science", "culture", "faith"}
ECONOMY_FIELDS = {"science", "culture", "gold", "faith"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _int(value, label: str, low: int, high: int) -> int:
    _require(type(value) is int and low <= value <= high, f"invalid {label}")
    return value


def _number(value, label: str) -> None:
    _require(type(value) in (int, float) and math.isfinite(value), f"invalid {label}")


def _digest(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_observation(value, player_id: int, turn: int) -> tuple[int, int]:
    _require(type(value) is dict and set(value) == OBSERVATION_FIELDS,
             "public observation has unknown or missing fields")
    _require(value["schema"] == OBSERVATION_SCHEMA
             and type(value["player_id"]) is int and value["player_id"] == player_id
             and type(value["turn"]) is int and value["turn"] == turn,
             "public observation identity differs")
    width = _int(value["width"], "observation width", 1, MAX_PLOTS)
    height = _int(value["height"], "observation height", 1, MAX_PLOTS)
    _require(width * height <= MAX_PLOTS, "public observation map exceeds bound")
    plots = value["plots"]
    _require(type(plots) is list and len(plots) <= width * height,
             "invalid public observation plots")
    seen = set()
    for row in plots:
        _require(type(row) is dict and set(row) in (OBS_PLOT_FIELDS, OBS_PLOT_FIELDS | RESOURCE_FIELDS),
                 "public observation plot fields differ")
        index = _int(row["index"], "observation plot index", 0, width * height - 1)
        x = _int(row["x"], "observation plot x", 0, width - 1)
        y = _int(row["y"], "observation plot y", 0, height - 1)
        _require(index == y * width + x and index not in seen,
                 "public observation plot geometry differs")
        seen.add(index)
        _require(row["visible"] is True and row["revealed"] is True,
                 "observation contains a non-visible plot")
        for name in ("terrain_type", "feature_type"):
            _int(row[name], "observation " + name, -(1 << 31), (1 << 31) - 1)
        _int(row["owner"], "observation plot owner", -1, MAX_PLAYERS - 1)
        _require(type(row["water"]) is bool and type(row["impassable"]) is bool,
                 "observation plot flags must be Boolean")
        if RESOURCE_FIELDS <= row.keys():
            _int(row["resource_type"], "visible resource type", 0, (1 << 31) - 1)
            _int(row["resource_count"], "visible resource count", 0, (1 << 31) - 1)
    for key in ("units", "visible_enemy_units", "cities"):
        _require(type(value[key]) is list and len(value[key]) <= MAX_ROWS,
                 f"public observation {key} is malformed or oversized")
    for row in value["units"]:
        _require(type(row) is dict and set(row) == UNIT_FIELDS, "owned unit fields differ")
        _require(type(row["owner"]) is int and row["owner"] == player_id,
                 "foreign unit in own-unit view")
        for key in ("id", "type", "x", "y", "moves", "max_moves", "owner"):
            _int(row[key], "owned unit " + key, 0, (1 << 31) - 1)
        _require(row["id"] >= 0 and row["type"] >= 0
                 and row["x"] < width and row["y"] < height,
                 "owned unit identity or position differs")
        _number(row["damage"], "owned unit damage")
    for row in value["visible_enemy_units"]:
        _require(type(row) is dict and set(row) == ENEMY_FIELDS
                 and type(row["owner"]) is int and row["owner"] != player_id
                 and row["visible"] is True, "enemy unit is not visibly scoped")
        for key in ("owner", "id", "type", "x", "y"):
            _int(row[key], "visible enemy " + key, 0, (1 << 31) - 1)
        _require(row["owner"] < MAX_PLAYERS and row["id"] >= 0 and row["type"] >= 0
                 and row["x"] < width and row["y"] < height,
                 "visible enemy identity or position differs")
        _number(row["damage"], "visible enemy damage")
    for row in value["cities"]:
        _require(type(row) is dict and set(row) == CITY_FIELDS
                 and type(row["owner"]) is int and row["owner"] == player_id
                 and type(row["yields"]) is dict and set(row["yields"]) == YIELD_FIELDS,
                 "city view is not player-scoped")
        for key in ("id", "x", "y", "population", "owner"):
            _int(row[key], "city " + key, 0, (1 << 31) - 1)
        _require(row["id"] >= 0 and row["population"] >= 0
                 and row["x"] < width and row["y"] < height,
                 "city identity or position differs")
        for name, amount in row["yields"].items():
            _number(amount, "city yield " + name)
    economy = value["economy"]
    _require(type(economy) is dict and set(economy) == ECONOMY_FIELDS,
             "public economy fields differ")
    for name, amount in economy.items():
        _number(amount, "economy " + name)
    return width, height


def _validate_map(value, observation: dict, player_id: int, turn: int,
                  width: int, height: int) -> None:
    _require(type(value) is dict and set(value) == MAP_FIELDS
             and value["schema"] == PLAYER_MAP_SCHEMA,
             "player map schema or fields differ")
    _require(type(value["player_id"]) is int and value["player_id"] == player_id
             and type(value["turn"]) is int and value["turn"] == turn,
             "player map identity differs")
    _require(type(value["width"]) is int and value["width"] == width
             and type(value["height"]) is int and value["height"] == height,
             "player map dimensions differ")
    _require(value["source"] == "official_plot_tooltip_revealed_live_getters"
             and all(value[k] is False for k in
                     ("historical_memory_proven", "graphical_differential_proven",
                      "complete_player_observation")),
             "player map qualification flags differ")
    pin = value["visible_observation_id"]
    _require(type(pin) is str and len(pin) == 64
             and all(ch in "0123456789abcdef" for ch in pin)
             and pin == _digest(observation), "player map observation pin differs")
    rows = value["plots"]
    _require(type(rows) is list and len(rows) <= width * height,
             "player map plots are malformed or oversized")
    seen = set()
    visible_rows = []
    for row in rows:
        _require(type(row) is dict and set(row) in
                 (PLOT_FIELDS | {"visible"}, PLOT_FIELDS | RESOURCE_FIELDS | {"visible"}),
                 "player map plot fields differ")
        index = _int(row["index"], "map plot index", 0, width * height - 1)
        x = _int(row["x"], "map plot x", 0, width - 1)
        y = _int(row["y"], "map plot y", 0, height - 1)
        _require(index == y * width + x and index not in seen,
                 "player map plot geometry differs")
        seen.add(index)
        _require(type(row["visible"]) is bool and row["revealed"] is True,
                 "player map visibility differs")
        for name in ("terrain_type", "feature_type"):
            _int(row[name], "map plot " + name, -(1 << 31), (1 << 31) - 1)
        _int(row["owner"], "map plot owner", -1, MAX_PLAYERS - 1)
        _require(type(row["water"]) is bool and type(row["impassable"]) is bool,
                 "map plot flags must be Boolean")
        if RESOURCE_FIELDS <= row.keys():
            _int(row["resource_type"], "map resource type", 0, (1 << 31) - 1)
            _int(row["resource_count"], "map resource count", 0, (1 << 31) - 1)
        if row["visible"]:
            visible_rows.append(dict(row))
    observed_by_index = {row["index"]: row for row in observation["plots"]}
    displayed_by_index = {row["index"]: row for row in visible_rows}
    _require(observed_by_index == displayed_by_index,
             "player map visible rows differ from the observation")


def validate_player_map(value, observation):
    """Validate a public revealed map without loading the native backend."""
    _require(type(observation) is dict, 'public map needs its visible observation')
    pid,turn=observation.get('player_id'),observation.get('turn')
    _int(pid,'player id',0,MAX_PLAYERS-1)
    _int(turn,'turn',0,(1<<63)-1)
    width,height=_validate_observation(observation,pid,turn)
    _validate_map(value,observation,pid,turn,width,height)
    return value


def validate_player_view(value, *, episode_id: str, game_generation: str,
                         sequence: int, player_id: int, turn: int) -> dict:
    """Validate and detach a player view against the current hotseat boundary."""
    _require(type(value) is dict and set(value) == VIEW_FIELDS
             and value["schema"] == SCHEMA, "player view schema or fields differ")
    _require(value["episode_id"] == episode_id
             and type(value["episode_id"]) is str
             and value["game_generation"] == game_generation
             and type(value["game_generation"]) is str
             and type(value["sequence"]) is int and value["sequence"] == sequence
             and type(value["player_id"]) is int and value["player_id"] == player_id
             and type(value["turn"]) is int and value["turn"] == turn,
             "player view identity differs from current session")
    _int(player_id, "player id", 0, MAX_PLAYERS - 1)
    _int(turn, "turn", 0, (1 << 63) - 1)
    _int(sequence, "sequence", 0, (1 << 63) - 1)
    player_turn = value["player_turn"]
    _require(type(player_turn) is dict and set(player_turn) == {"active", "turn_active_complete"}
             and type(player_turn["active"]) is bool
             and type(player_turn["turn_active_complete"]) is bool,
             "player turn flags must be exact Booleans")
    width, height = _validate_observation(value["observation"], player_id, turn)
    _validate_map(value["player_map"], value["observation"], player_id, turn, width, height)
    return copy.deepcopy(value)


__all__ = ["SCHEMA", "validate_player_view"]

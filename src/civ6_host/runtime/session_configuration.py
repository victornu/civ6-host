"""Inspect saved session settings without loading a game or applying defaults.

This is control-plane metadata, not an actor observation or a runtime admission.
In particular a saved turn-phase token never proves multiple active players.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from .capture_package import read_package
from .native.native_game_configuration import game_configuration_hash
from .native.official_configuration import read_provider

SCHEMA = "civ6-host.saved-session-configuration.v1"
# EXE IsNetworkMultiplayer (callback 10c100, helper 102310) compares these
# exact hashes. This classifies a saved value; it does not admit a session.
_NETWORK_MODES = {"NETWORKMULTIPLAYER": 0x07CD5E0A, "INTERNET": 0x453F23E2,
                  "CROSSPLAY": 0xE75806E8, "LAN": 0x0138409A}
_KNOWN_MODES = {game_configuration_hash(name): name
                for name in ("HOTSEAT", "SINGLEPLAYER", *_NETWORK_MODES)}
if any(game_configuration_hash(name) != value for name, value in _NETWORK_MODES.items()):
    raise RuntimeError("Saved network-mode token hashes differ from the source predicate")
_INTERPRETATION = {
    "exe_sha256": "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63",
    "network_predicate_rva": "0x102310",
    "network_predicate_body_sha256": "5d3eed59526059b4b44b24549278ce1c2caac807c2a6bd4af5f1a071233850e6",
    "game_mode_key_initializer_rva": "0x5430",
    "native_predicate_executed": False,
}
_PARAMETERS = {
    "turn_phase": ("TurnPhaseType", "TURN_PHASE_TYPE", "TurnPhases", "TurnPhaseType"),
    "turn_timer": ("TurnTimerType", "TURN_TIMER_TYPE", "TurnTimers", "TurnTimerType"),
}
_TURN_LIMIT_MODES = {game_configuration_hash(name): name for name in
                     ("TURNLIMIT_GAMESPEED", "TURNLIMIT_CUSTOM", "TURNLIMIT_NONE")}
_SIMULTANEOUS_PHASE = game_configuration_hash("TURNPHASE_SIMULTANEOUS")


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scalar(value, name):
    if value is None:
        return {"present": False, "value": None, "variant_tag": None}
    if (value.tag not in (2, 3) or value.extra != 0 or value.flags != 0
            or value.size != 0 or len(value.payload) != 4):
        raise ValueError("Saved session setting is not a supported integer/hash: " + name)
    return {"present": True, "value": value.scalar(), "variant_tag": value.tag}


def read_saved_settings(configuration: bytes):
    """Read the exact GAME_ROOT provider; preserve absent/unknown values."""
    return _saved_settings(_saved_providers(configuration))


def _saved_providers(configuration):
    values, end = read_provider(configuration)
    if end != len(configuration):
        raise ValueError("Saved configuration contains trailing bytes")
    return values


def _saved_settings(values):
    game = next((v for v in values if v.key == game_configuration_hash("GAME_ROOT")), None)
    if game is None or (game.tag, game.extra, game.flags, game.size) != (10, 0, 0x05000000, 0):
        raise ValueError("Saved configuration lacks its exact GAME_ROOT provider")
    fields = {v.key: v for v in game.children}
    mode = _scalar(fields.get(game_configuration_hash("GAME_MODE")), "GAME_MODE")
    if not mode["present"] or mode["variant_tag"] != 3:
        raise ValueError("Saved GAME_MODE must be an explicit native hash")
    mode["name"] = _KNOWN_MODES.get(mode["value"])
    mode["recognized"] = mode["name"] is not None
    mode["network_mode_token"] = mode["value"] in _NETWORK_MODES.values()
    result = {"game_mode": mode}
    for role, (_, key, _, _) in _PARAMETERS.items():
        result[role] = _scalar(fields.get(game_configuration_hash(key)), key)
    horizon = {}
    for role, key in (("limit_mode", "GAME_TURN_LIMIT"), ("max_turns", "GAME_MAX_TURNS"),
                      ("start_turn", "GAME_START_TURN"), ("game_speed", "GAME_SPEED_TYPE")):
        horizon[role] = _scalar(fields.get(game_configuration_hash(key)), key)
    horizon["limit_mode"]["token"] = _TURN_LIMIT_MODES.get(horizon["limit_mode"]["value"])
    score = fields.get(game_configuration_hash("VICTORY_SCORE"))
    if score is not None and ((score.tag, score.extra, score.flags, score.size) != (1, 0, 0, 0)
                              or score.scalar() not in (0, 1)):
        raise ValueError("Saved score victory flag is not Boolean")
    horizon["score_victory_enabled"] = None if score is None else bool(score.scalar())
    result["turn_horizon"] = horizon
    return result


def _saved_slot_rows(providers):
    slot_key = game_configuration_hash("SLOT_STATUS")
    player_key = game_configuration_hash("PLAYER_ID")
    seen_ids = set()
    for provider in providers:
        fields = {child.key: child for child in provider.children}
        status = fields.get(slot_key)
        if status is None:
            continue
        if (provider.tag, provider.extra, provider.flags, provider.size) != (10, 0, 0x05000000, 0):
            raise ValueError("Saved slot status belongs to an unsupported provider")
        row = _scalar(status, "SLOT_STATUS")
        if row["variant_tag"] != 2:
            raise ValueError("Saved slot status must be an integer")
        player = _scalar(fields.get(player_key), "PLAYER_ID")
        player_id = player["value"]
        if (player["variant_tag"] != 2 or not 0 <= player_id < 64
                or player_id in seen_ids
                or provider.key != game_configuration_hash(f"PLAYER_{player_id}")):
            raise ValueError("Saved slot does not identify its exact player provider")
        seen_ids.add(player_id)
        yield player_id, row["value"], fields


def _saved_slots(providers):
    # The retained application configuration getter identifies SS_TAKEN as 3.
    # This records saved slots, with no inference about connected/active humans.
    counts = {}
    taken_ids = []
    for player_id, value, _ in _saved_slot_rows(providers):
        counts[value] = counts.get(value, 0) + 1
        if value == 3:
            taken_ids.append(player_id)
    return {"slot_status_counts": dict(sorted(counts.items())),
            "taken_slot_count": len(taken_ids), "taken_slot_ids": sorted(taken_ids),
            "live_roster_observed": False}


def read_saved_roster(configuration: bytes):
    """Read declared occupied seats from the exact serialized configuration."""
    return _saved_slots(_saved_providers(configuration))


def read_saved_major_roster(configuration: bytes):
    """Read occupied major seats from the saved provider, before any native calls."""
    from .native.native_ui_enums_cases import NATIVE_UI_ENUMS_EXPECTED
    statuses = NATIVE_UI_ENUMS_EXPECTED["SlotStatus"]
    levels = NATIVE_UI_ENUMS_EXPECTED["CivilizationLevelTypes"]
    known_levels = {value & 0xffffffff for value in levels.values()}
    full_civilization = levels["CIVILIZATION_LEVEL_FULL_CIV"]
    active = (statuses["SS_COMPUTER"], statuses["SS_TAKEN"])
    level_key = game_configuration_hash("CIVILIZATION_LEVEL_TYPE_ID")
    majors, taken = [], []
    for player_id, status, fields in _saved_slot_rows(_saved_providers(configuration)):
        if status not in statuses.values():
            # Both retained expansion providers and the XP2 reserialized
            # provider use 5 on unused city-state slots outside GetAliveMajors.
            if (status == 5 and _scalar(fields.get(level_key), "CIVILIZATION_LEVEL_TYPE_ID")["value"]
                    == levels["CIVILIZATION_LEVEL_CITY_STATE"] & 0xffffffff):
                continue
            raise ValueError("Unknown saved slot status")
        if status not in active:
            continue
        level = _scalar(fields.get(level_key), "CIVILIZATION_LEVEL_TYPE_ID")
        if level["value"] not in known_levels or level["value"] == 0xffffffff:
            raise ValueError("Occupied saved slot has no recognized civilization level")
        if level["value"] == full_civilization:
            majors.append(player_id)
        elif status == statuses["SS_TAKEN"]:
            raise ValueError("Taken saved seat does not belong to a major civilization")
        if status == statuses["SS_TAKEN"]:
            taken.append(player_id)
    if not majors:
        raise ValueError("Saved configuration has no occupied major seats")
    return tuple(sorted(majors)), tuple(sorted(taken))


def _multiplayer_candidate(settings, roster):
    mode = settings["game_mode"]
    phase = settings["turn_phase"]
    blockers = []
    if not mode["network_mode_token"]:
        blockers.append("saved_mode_is_not_network")
    elif mode["name"] != "LAN":
        blockers.append("saved_network_mode_is_not_lan")
    if not phase["present"] or phase["value"] != _SIMULTANEOUS_PHASE:
        blockers.append("saved_simultaneous_phase_absent")
    if roster["taken_slot_count"] < 2:
        blockers.append("fewer_than_two_saved_taken_slots")
    return {"matches_lan_multihuman_settings": not blockers, "settings_blockers": blockers,
            "live_roster_observed": False, "native_commands_qualified": False}


def _domain(connection, specification):
    parameter, key, table, token_column = specification
    # Table/column identifiers are internal constants, never caller SQL.
    columns = ("ParameterId,Domain,Hash,DefaultValue,ConfigurationGroup,ConfigurationId,"
               "SupportsSinglePlayer,SupportsHotSeat,SupportsPlayByCloud,ChangeableAfterGameStart")
    rows = connection.execute("SELECT " + columns + " FROM Parameters WHERE ParameterId=?",
                              (parameter,)).fetchmany(2)
    if len(rows) != 1:
        raise ValueError("Session parameter must have one definition: " + parameter)
    row = rows[0]
    if row[2] != 1 or row[4:6] != ("Game", key) or type(row[1]) is not str:
        raise ValueError("Session parameter domain/hash contract differs: " + parameter)
    names = [r[0] for r in connection.execute(
        "SELECT " + token_column + " FROM " + table + " WHERE Domain=? ORDER BY SortIndex," + token_column,
        (row[1],)).fetchmany(257)]
    if not names or len(names) > 256 or len(set(names)) != len(names):
        raise ValueError("Session domain is empty, duplicated or oversized: " + row[1])
    tokens = {game_configuration_hash(name): name for name in names}
    if len(tokens) != len(names):
        raise ValueError("Session domain hash collision: " + row[1])
    if any(type(value) is not int or value not in (0, 1) for value in row[6:10]):
        raise ValueError("Session parameter availability flags are not Boolean: " + parameter)
    return {"parameter": parameter, "configuration_id": key, "domain": row[1],
            "available_tokens": names, "setup_default": row[3],
            "supports_singleplayer": bool(row[6]), "supports_hotseat": bool(row[7]),
            "supports_play_by_cloud": bool(row[8]), "changeable_after_start": bool(row[9])}, tokens


def inspect_prepared_capture(reference, *, candidate_profile=None):
    """Inspect hash-verified saved settings using this capture's final DB.

    Reuses package verification, not the GameCore loader or a reconstructed
    settings database. No configuration is rewritten and no absent property is
    filled with a setup default. No game binary is loaded.
    """
    manifest, _, files = read_package(reference, _candidate_profile=candidate_profile)
    source = files["configuration_stream"]
    config_pin = manifest["files"]["configuration_stream"]
    if config_pin["bytes"] > 4 * 1024 * 1024:
        raise ValueError("Configuration exceeds the provider inspection limit")
    with source.open("rb") as stream:
        configuration = stream.read(4 * 1024 * 1024 + 1)
    if len(configuration) != config_pin["bytes"] or hashlib.sha256(configuration).hexdigest() != config_pin["sha256"]:
        raise ValueError("Configuration changed after prepared package verification")
    providers = _saved_providers(configuration)
    saved = _saved_settings(providers)
    database = files["database_configuration"]
    # Immutable read-only URI: never create sidecars or recover a journal.
    with sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
        for role, specification in _PARAMETERS.items():
            definition, tokens = _domain(connection, specification)
            saved[role].update(token=tokens.get(saved[role]["value"]), definition=definition,
                               recognized=saved[role]["value"] in tokens)
    if _sha(database) != manifest["files"]["database_configuration"]["sha256"]:
        raise ValueError("Configuration database changed during session inspection")
    mode = saved["game_mode"]["name"]
    # This describes which existing profile can be considered, not successful
    # admission or behavior. A network phase on a HOTSEAT save is not a session.
    from .capture_profiles import CAPTURE_MODES
    expected_mode = "LAN" if candidate_profile is not None else CAPTURE_MODES.get(manifest["input_profile"])
    if expected_mode is not None and mode != expected_mode:
        raise ValueError("Prepared profile and saved GAME_MODE disagree")
    roster = _saved_slots(providers)
    return {"schema": SCHEMA, "prepared_capture": dict(reference),
            "origin": manifest["origin"], "engine_sha256": manifest["engine"]["sha256"],
            "configuration_sha256": config_pin["sha256"],
            "configuration_database_sha256": manifest["files"]["database_configuration"]["sha256"],
            "input_profile": manifest["input_profile"], "saved": saved,
            "saved_roster": roster, "saved_multiplayer_candidate": _multiplayer_candidate(saved, roster),
            "interpretation_profile": dict(_INTERPRETATION),
            "saved_values_not_defaulted": True, "configuration_modified": False,
            "mode_behavior_inferred": False, "gamecore_loaded": False,
            "runtime_admitted": False, "active_players_observed": False,
            "simultaneous_qualified": False, "actor_input": False}


def inspect_official_save(reference):
    """Read declared session settings and content from an exact official save."""
    from .native.official_application_configuration import extract_application_configuration
    from .native.official_save import MAX_SAVE_BYTES

    if (type(reference) is not dict or set(reference) != {"path", "sha256"}
            or type(reference["path"]) is not str or not Path(reference["path"]).is_absolute()):
        raise ValueError("Official save inspection requires an absolute path and SHA-256")
    with Path(reference["path"]).open("rb") as stream:
        raw = stream.read(MAX_SAVE_BYTES + 1)
    if not 8 <= len(raw) <= MAX_SAVE_BYTES or hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("Official save exceeds its bound or differs from its SHA-256")
    configuration, receipt = extract_application_configuration(raw)
    providers = _saved_providers(configuration)
    content = receipt["content_declaration"]
    saved, roster = _saved_settings(providers), _saved_slots(providers)
    return {"schema": "civ6-host.official-save-session-configuration.v1",
            "save_sha256": receipt["save_sha256"], "configuration_sha256": receipt["sha256"],
            "gamecore_payload_sha256": receipt["gamecore_payload_sha256"],
            "saved": saved, "saved_roster": roster,
            "saved_multiplayer_candidate": _multiplayer_candidate(saved, roster),
            "declared_content": content["identity"],
            "declared_mod_metadata": content["declared_mods"],
            "interpretation_profile": dict(_INTERPRETATION),
            "gamecore_loaded": False, "runtime_admitted": False, "actor_input": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    input_kind = parser.add_mutually_exclusive_group(required=True)
    input_kind.add_argument("--prepared-capture", type=Path)
    input_kind.add_argument("--official-save", type=Path)
    parser.add_argument("--candidate-profile", choices=("xp1-lan", "xp2-lan"),
                        help="Inspect the exact retained expansion capture")
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    if args.official_save is not None:
        if args.candidate_profile is not None:
            parser.error("--candidate-profile requires --prepared-capture")
        result = inspect_official_save({"path": str(args.official_save.resolve()), "sha256": args.sha256})
    else:
        result = inspect_prepared_capture({"path": str(args.prepared_capture.resolve()), "sha256": args.sha256},
                                          candidate_profile=args.candidate_profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Public player-view boundary checks; fixtures contain no native runtime."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from civ6_host import HotseatClient, ProtocolError
from civ6_host.client import SCHEMA
from civ6_host.player_view import SCHEMA as PLAYER_VIEW_SCHEMA


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def public_observation(player_id, turn):
    plot = {"index": 0, "x": 0, "y": 0, "visible": True, "revealed": True,
            "terrain_type": 0, "feature_type": -1, "owner": player_id,
            "water": False, "impassable": False}
    return {"schema": "civ6rl-player-observation-v1", "player_id": player_id,
            "turn": turn, "width": 2, "height": 1, "plots": [plot],
            "units": [], "visible_enemy_units": [], "cities": [],
            "economy": {"science": 0.0, "culture": 0.0, "gold": 0.0, "faith": 0.0}}


def make_player_view(reply, player_id):
    observation = public_observation(player_id, reply["observation"]["turn"])
    map_plot = {key: value for key, value in observation["plots"][0].items()
                if key != "visible"}
    fog_plot = {"index": 1, "x": 1, "y": 0, "revealed": True, "terrain_type": 1,
        "feature_type": -1, "owner": -1, "water": False, "impassable": False,
        "visible": False}
    player_map = {"schema": "civ6rl.saved_player_map933.v1", "player_id": player_id,
        "turn": observation["turn"], "width": 2, "height": 1,
        "plots": [dict(map_plot, visible=True), fog_plot],
        "visible_observation_id": digest(observation),
        "source": "official_plot_tooltip_revealed_live_getters",
        "historical_memory_proven": False, "graphical_differential_proven": False,
        "complete_player_observation": False}
    return {"schema": PLAYER_VIEW_SCHEMA, "episode_id": reply["episode_id"],
        "game_generation": reply["game_generation"], "sequence": reply["sequence"],
        "player_id": player_id, "turn": observation["turn"], "observation": observation,
        "player_map": player_map, "player_turn": {"active": True, "turn_active_complete": False}}


class Backend:
    def __init__(self):
        self.aborts = []
        self.reads = []
        self.bad = None

    def reset(self):
        self.episode = str(uuid4())
        decisions = {"episode_id": self.episode, "game_generation": "native-" + self.episode,
            "sequence": 0, "player_id": 0, "turn": 3, "candidates": [],
            "complete_action_space": False}
        decisions["decision_id"] = digest(decisions)
        self.reply = {"stage": "official_session_response", "schema": SCHEMA,
            "nonce": "a" * 32, "episode_id": self.episode, "game_generation": "native-" + self.episode,
            "sequence": 0, "operation": "reset", "observation": {"player_id": 0, "turn": 3},
            "rounds": 2, "outcome": {"terminated": False, "truncated": False, "reason": None},
            "automatic_choices_applied": False, "action_interface_complete": False,
            "strategic_training_ready": False, "decisions": decisions,
            "applied_action": None}
        return copy.deepcopy(self.reply)

    def request(self, request):
        raise AssertionError("player_view must not issue a command")

    def read_player_view(self, reply, player_id):
        self.reads.append((copy.deepcopy(reply), player_id))
        if self.bad == "raise":
            raise OSError("view unavailable")
        value = make_player_view(reply, player_id)
        if self.bad == "stale":
            value["sequence"] += 1
        elif self.bad == "cross-player":
            value["observation"]["player_id"] = (player_id + 1) % 64
        elif self.bad == "cross-map":
            value["player_map"]["width"] = 3
        elif self.bad == "stale-map-pin":
            value["player_map"]["visible_observation_id"] = "0" * 64
        elif self.bad == "hidden-plot":
            value["player_map"]["plots"][0]["visible"] = False
        elif self.bad == "malformed-fog-row":
            value["player_map"]["plots"][1]["water"] = 1
        elif self.bad == "injected-action":
            value["actions"] = []
        elif self.bad == "wrong-turn-type":
            value["player_turn"]["active"] = 1
        elif self.bad == "mutate-reply":
            reply["decisions"]["decision_id"] = "changed"
        return value

    def abort(self, reason):
        self.aborts.append(reason)


class PlayerViewTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.client = HotseatClient(self.backend)
        self.reset_view = self.client.reset()

    def test_returns_detached_joined_view_without_changing_action_view(self):
        before = self.client.view()
        result = self.client.player_view(2)
        self.assertEqual(result["player_id"], 2)
        self.assertEqual(result["player_map"]["visible_observation_id"], digest(result["observation"]))
        result["observation"]["player_id"] = 12
        self.assertEqual(self.client.view(), before)
        self.assertEqual(len(self.backend.reads), 1)
        self.assertEqual(self.backend.reads[0][1], 2)

    def test_stale_cross_player_and_injected_views_abort(self):
        for fault in ("stale", "cross-player", "cross-map", "stale-map-pin",
                      "hidden-plot", "malformed-fog-row", "injected-action",
                      "wrong-turn-type", "mutate-reply"):
            with self.subTest(fault=fault):
                backend = Backend()
                client = HotseatClient(backend)
                client.reset()
                backend.bad = fault
                with self.assertRaises(ProtocolError):
                    client.player_view(2)
                self.assertTrue(backend.aborts)
                with self.assertRaises(RuntimeError):
                    client.observe()

    def test_read_failure_aborts_and_never_requests_an_action(self):
        self.backend.bad = "raise"
        with self.assertRaises(OSError):
            self.client.player_view(1)
        self.assertEqual(len(self.backend.reads), 1)
        self.assertTrue(self.backend.aborts)

    def test_uninitialized_terminal_and_invalid_player_refuse_before_read(self):
        backend = Backend()
        client = HotseatClient(backend)
        with self.assertRaises(RuntimeError):
            client.player_view(0)
        self.assertEqual(backend.reads, [])
        for bad_id in (True, -1, 64):
            with self.subTest(player_id=bad_id), self.assertRaises(ValueError):
                self.client.player_view(bad_id)
        self.client._reply["outcome"]["terminated"] = True
        with self.assertRaises(RuntimeError):
            self.client.player_view(0)
        self.assertEqual(self.backend.reads, [])


if __name__ == "__main__":
    unittest.main()

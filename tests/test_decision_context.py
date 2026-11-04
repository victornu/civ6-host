import unittest

from civ6_host.runtime.decision_context import DecisionContextStore
from civ6_host.runtime.decision_context import MAX_PLAYER_BYTES
from civ6_host.runtime.decision_context import MAX_VALUE_NODES


EPISODE = "00000000-0000-4000-8000-000000000001"
GENERATION = "native-" + EPISODE
ROSTER = (0, 1, 2, 3)


class _Owner:
    def __init__(self):
        self.events = []

    def emit(self, name, **payload):
        self.events.append((name, payload))


def _set_decision(owner, player_id, turn, sequence, marker):
    owner.explicit_observation = {"player_id": player_id, "turn": turn,
                                  "marker": marker}
    owner.explicit_decision_player_id = player_id
    owner.explicit_decision_candidates = [{"candidate_id": marker,
                                           "action": {"kind": "wait"}}]
    owner.explicit_combat_units = []
    owner.explicit_combat_cities = []
    owner.explicit_government = {"marker": marker}
    owner.explicit_pantheon = None
    owner.explicit_promotions = []
    owner.explicit_unit_orders = []
    owner.explicit_unit_upgrades = []
    owner.explicit_production_snapshot = {"turn": turn}
    owner.explicit_production_queues = []
    owner.explicit_city_shots = []
    owner.explicit_district_shots = []
    owner.explicit_trade_routes = []
    owner.explicit_trade_origins = []
    owner.explicit_envoys = {"marker": marker}
    owner.explicit_envoy_panel = []
    owner.explicit_great_people = []
    owner.explicit_religion = None
    owner.explicit_captured_city = {"marker": marker}
    owner.explicit_world_input = None
    if not hasattr(owner, "explicit_placements"):
        owner.explicit_placements = {}
    return {"sequence": sequence, "decision_id": f"{sequence:064x}"}


class DecisionContextTests(unittest.TestCase):
    def setUp(self):
        self.owner = _Owner()
        self.store = DecisionContextStore()

    def capture(self, player_id, marker, sequence, turn=5):
        decision = _set_decision(self.owner, player_id, turn, sequence, marker)
        self.store.capture(self.owner, episode_id=EPISODE,
                           game_generation=GENERATION, roster=ROSTER,
                           player_id=player_id, turn=turn,
                           decision_id=decision["decision_id"],
                           sequence=sequence)

    def test_snapshots_are_isolated_and_activation_restores_aliases(self):
        self.capture(0, "p0", 10)
        self.capture(1, "p1", 11)
        self.assertEqual(self.store.snapshot_count, 2)
        # Simulate an episode-wide placement ledger update after both decision
        # snapshots were captured. It must not be replaced by p0's snapshot.
        self.owner.explicit_placements[(1, 8, 9)] = {"later": True}
        baseline_placements = dict(self.owner.explicit_placements)

        with self.store.activate(self.owner, episode_id=EPISODE,
                                  game_generation=GENERATION, roster=ROSTER,
                                  player_id=0, turn=5):
            self.assertEqual(self.owner.explicit_decision_player_id, 0)
            self.assertEqual(self.owner.explicit_observation["marker"], "p0")
            self.assertEqual(self.owner.explicit_decision_candidates[0]["candidate_id"], "p0")
            self.assertTrue(self.owner.explicit_placements[(1, 8, 9)]["later"])
            self.owner.explicit_placements[(0, 2, 3)] = {"committed": True}

        # Per-decision aliases revert to the caller's p1 state; shared
        # placement tracking keeps the mutation made by the adapter.
        self.assertEqual(self.owner.explicit_decision_player_id, 1)
        self.assertEqual(self.owner.explicit_observation["marker"], "p1")
        self.assertEqual(self.owner.explicit_placements,
                         baseline_placements | {(0, 2, 3): {"committed": True}})
        self.assertTrue(self.owner.explicit_placements[(0, 2, 3)]["committed"])
        self.assertEqual(self.store.snapshot_count, 2)

        activated = [payload for name, payload in self.owner.events
                     if name == "decision_context_activated"]
        self.assertEqual((activated[0]["player_id"], activated[0]["sequence"]), (0, 10))
        self.assertEqual(activated[0]["decision_id"], f"{10:064x}")

    def test_replacement_and_consumed_player_invalidation(self):
        self.capture(0, "old", 1)
        self.capture(1, "other", 2)
        self.capture(0, "replacement", 3)
        self.assertEqual(self.store.snapshot_count, 2)
        with self.store.activate(self.owner, episode_id=EPISODE,
                                 game_generation=GENERATION, roster=ROSTER,
                                 player_id=0, turn=5):
            self.assertEqual(self.owner.explicit_observation["marker"], "replacement")
            self.store.invalidate_player(self.owner, 0, reason="command_consumed")
        self.assertEqual(self.store.snapshot_count, 1)
        with self.store.activate(self.owner, episode_id=EPISODE,
                                 game_generation=GENERATION, roster=ROSTER,
                                 player_id=1, turn=5):
            self.assertEqual(self.owner.explicit_decision_player_id, 1)
            self.store.invalidate_all(self.owner, reason="command_failed_uncertain")
        self.assertEqual(self.store.snapshot_count, 0)
        with self.assertRaisesRegex(RuntimeError, "No current decision snapshot"):
            with self.store.activate(self.owner, episode_id=EPISODE,
                                     game_generation=GENERATION, roster=ROSTER,
                                     player_id=1, turn=5):
                self.fail("invalidated player context was activated")
        invalidations = [payload for name, payload in self.owner.events
                         if name == "decision_context_invalidated"]
        self.assertEqual(invalidations[0]["reason"], "command_consumed")
        self.assertEqual(invalidations[0]["player_id"], 0)
        self.assertEqual(invalidations[0]["snapshot_count"], 1)
        self.assertEqual(invalidations[-1]["reason"], "command_failed_uncertain")
        self.assertEqual(invalidations[-1]["snapshot_count"], 0)

    def test_episode_roster_or_turn_change_discards_old_snapshots(self):
        self.capture(0, "p0", 1)
        self.capture(1, "p1", 2)
        decision = _set_decision(self.owner, 0, 6, 3, "new-turn")
        self.store.capture(self.owner, episode_id=EPISODE,
                           game_generation=GENERATION, roster=ROSTER,
                           player_id=0, turn=6,
                           decision_id=decision["decision_id"], sequence=3)
        self.assertEqual(self.store.snapshot_count, 1)
        self.assertTrue(any(name == "decision_context_invalidated"
                            and payload["reason"] == "episode_roster_or_turn_changed"
                            for name, payload in self.owner.events))
        with self.assertRaisesRegex(RuntimeError, "scope is stale"):
            with self.store.activate(self.owner, episode_id=EPISODE,
                                     game_generation=GENERATION, roster=ROSTER,
                                     player_id=0, turn=5):
                self.fail("old-turn context was activated")
        self.assertEqual(self.store.snapshot_count, 1)

    def test_failed_activation_restores_aliases_and_keeps_placements(self):
        self.capture(0, "p0", 1)
        before = self.owner.explicit_observation
        with self.assertRaisesRegex(RuntimeError, "adapter failure"):
            with self.store.activate(self.owner, episode_id=EPISODE,
                                     game_generation=GENERATION, roster=ROSTER,
                                     player_id=0, turn=5):
                self.owner.explicit_observation = {"temporary": True}
                self.owner.explicit_placements[(0, 3, 4)] = {"committed": True}
                raise RuntimeError("adapter failure")
        self.assertIs(self.owner.explicit_observation, before)
        self.assertTrue(self.owner.explicit_placements[(0, 3, 4)]["committed"])

    def test_bounds_and_identity_validation(self):
        self.capture(0, "p0", 1)
        with self.assertRaisesRegex(ValueError, "roster"):
            self.store.capture(self.owner, episode_id=EPISODE,
                               game_generation=GENERATION,
                               roster=tuple(range(65)), player_id=0,
                               turn=5, decision_id=f"{2:064x}", sequence=2)
        owner = _Owner()
        _set_decision(owner, 0, 5, 2, "x" * (MAX_PLAYER_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "byte bound"):
            self.store.capture(owner, episode_id=EPISODE,
                               game_generation=GENERATION, roster=ROSTER,
                               player_id=0, turn=5,
                               decision_id=f"{2:064x}", sequence=2)
        with self.assertRaisesRegex(ValueError, "digest"):
            self.store.capture(self.owner, episode_id=EPISODE,
                               game_generation=GENERATION, roster=ROSTER,
                               player_id=0, turn=5, decision_id="short", sequence=2)
        decision = _set_decision(self.owner, 0, 2 ** 31 - 1, 4, "last-int32-turn")
        self.store.capture(self.owner, episode_id=EPISODE,
                           game_generation=GENERATION, roster=ROSTER,
                           player_id=0, turn=2 ** 31 - 1,
                           decision_id=decision["decision_id"], sequence=4)
        with self.assertRaisesRegex(ValueError, "turn"):
            with self.store.activate(self.owner, episode_id=EPISODE,
                                     game_generation=GENERATION, roster=ROSTER,
                                     player_id=0, turn=2 ** 31):
                self.fail("out-of-range turn activated")

    def test_world_input_is_optional_per_player_and_cycles_refuse_before_copy(self):
        decision = _set_decision(self.owner, 0, 5, 1, "p0")
        self.owner.explicit_world_input = {"player_id": 0, "turn": 5}
        self.store.capture(self.owner, episode_id=EPISODE,
                           game_generation=GENERATION, roster=ROSTER,
                           player_id=0, turn=5,
                           decision_id=decision["decision_id"], sequence=1)
        decision = _set_decision(self.owner, 1, 5, 2, "p1")
        del self.owner.explicit_world_input
        self.store.capture(self.owner, episode_id=EPISODE,
                           game_generation=GENERATION, roster=ROSTER,
                           player_id=1, turn=5,
                           decision_id=decision["decision_id"], sequence=2)
        with self.store.activate(self.owner, episode_id=EPISODE,
                                 game_generation=GENERATION, roster=ROSTER,
                                 player_id=0, turn=5):
            self.assertEqual(self.owner.explicit_world_input["player_id"], 0)
        self.assertFalse(hasattr(self.owner, "explicit_world_input"))
        with self.store.activate(self.owner, episode_id=EPISODE,
                                 game_generation=GENERATION, roster=ROSTER,
                                 player_id=1, turn=5):
            self.assertFalse(hasattr(self.owner, "explicit_world_input"))

        cyclic = _Owner()
        _set_decision(cyclic, 0, 5, 3, "cycle")
        cycle = []
        cycle.append(cycle)
        cyclic.explicit_decision_candidates = cycle
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.store.capture(cyclic, episode_id=EPISODE,
                               game_generation=GENERATION, roster=ROSTER,
                               player_id=0, turn=5,
                               decision_id=f"{3:064x}", sequence=3)

        oversized = _Owner()
        _set_decision(oversized, 0, 5, 4, "large-container")
        oversized.explicit_decision_candidates = [None] * (MAX_VALUE_NODES + 1)
        with self.assertRaisesRegex(ValueError, "object-count bound"):
            self.store.capture(oversized, episode_id=EPISODE,
                               game_generation=GENERATION, roster=ROSTER,
                               player_id=0, turn=5,
                               decision_id=f"{4:064x}", sequence=4)


if __name__ == "__main__":
    unittest.main()

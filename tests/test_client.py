"""Client transport/identity tests: no game or neural-network runtime."""
import ast
import copy
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from civ6_host import HotseatClient, ProtocolError
from civ6_host.client import SCHEMA, _digest
from civ6_host.contracts import policies


class Backend:
    def __init__(self):
        self.calls = []
        self.aborts = []
        self.tamper = None

    def reset(self):
        self.episode = str(uuid4())
        self.seq = 0
        self.player = 0
        self.turn = 1
        self.current = self.reply("reset")
        return copy.deepcopy(self.current)

    def reply(self, operation, applied=None):
        identity = dict(episode_id=self.episode, game_generation="native-"+self.episode, sequence=self.seq)
        observation = dict(player_id=self.player, turn=self.turn, cities=[], units=[])
        decisions = dict(**identity, player_id=self.player, turn=self.turn, candidates=[
            dict(candidate_id="choice-1", action=dict(kind="end_turn")),
            dict(candidate_id="choice-2", action=dict(kind="policies", slots=[
                dict(slot=0, prior_index=-1, options=[
                    dict(index=2, hash=4294967295, native_hash=-1, policy_type="POLICY_FIXTURE")
                ])
            ]))],
            complete_action_space=False)
        if operation == "close":
            decisions["candidates"] = []
        decisions["decision_id"] = _digest(decisions)
        return dict(stage="official_session_response", schema=SCHEMA, nonce="a"*32,
            **identity, operation=operation, observation=observation, decisions=decisions,
            rounds=self.turn-1, outcome=dict(terminated=False, truncated=operation=="close",
                reason="requested_close" if operation=="close" else None,
                native_victory={"internal_fixture_marker": "not_player_input"}),
            automatic_choices_applied=False, action_interface_complete=False,
            strategic_training_ready=False, applied_action=applied)

    def request(self, request):
        self.calls.append(copy.deepcopy(request))
        if self.tamper == "lost":
            raise TimeoutError("application unknown")
        applied = None
        if request["operation"] == "act":
            applied = next(r["action"] for r in self.current["decisions"]["candidates"]
                           if r["candidate_id"] == request["selection"]["candidate_id"])
            if applied["kind"] == "end_turn":
                # Synthetic fixture only, deliberately skips player 1: client
                # must accept the backend's actor, not invent a modulo order.
                self.player = 2
            else:
                applied = dict(kind="policies", candidate=policies.choose(
                    applied["slots"], request["selection"]["parameters"]["assignments"],
                    self.player, self.turn))
        self.seq += 1
        self.current = self.reply(request["operation"], applied)
        result = copy.deepcopy(self.current)
        if self.tamper == "sequence":
            result["sequence"] += 1
        if self.tamper == "action":
            result["applied_action"] = dict(kind="skip_unit", unit_id=1)
        if self.tamper == "private":
            result["privileged"] = {"enemy_gold": 5}
        if self.tamper == "policy":
            result["applied_action"]["candidate"]["assignments"] = [[0, 7]]
        return result

    def abort(self, reason):
        self.aborts.append(reason)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.client = HotseatClient(self.backend)
        self.initial = self.client.reset()

    def test_native_actor_is_observed_not_computed_and_views_are_detached(self):
        dec = self.initial["decisions"]
        self.initial["observation"]["player_id"] = 50
        result = self.client.act(dec["decision_id"], "choice-1")
        self.assertEqual(result["observation"]["player_id"], 2)
        self.assertEqual(result["observation"]["turn"], 1)
        self.assertNotIn("nonce", result)
        self.assertNotIn("native_victory", result["outcome"])
        self.assertEqual(len(result["decisions"]["candidates"]), 2)

    def test_stale_and_absent_choices_refuse_before_sending(self):
        dec = self.initial["decisions"]
        self.client.observe()
        with self.assertRaises(ProtocolError):
            self.client.act(dec["decision_id"], "choice-1")
        with self.assertRaises(ProtocolError):
            self.client.act(self.client.view()["decisions"]["decision_id"], "absent")
        self.assertEqual(len(self.backend.calls), 1)

    def test_policy_parameters_forward_exactly_without_choosing_assignments(self):
        dec = self.initial["decisions"]
        with self.assertRaises(ProtocolError):
            self.client.act(dec["decision_id"], "choice-2")
        params = {"assignments": [4294967295]}
        self.client.act(dec["decision_id"], "choice-2", parameters=params)
        self.assertEqual(self.backend.calls[-1]["selection"]["parameters"], params)
        self.backend.tamper = "policy"
        dec = self.client.view()["decisions"]
        with self.assertRaisesRegex(ProtocolError, "Policy choice was substituted"):
            self.client.act(dec["decision_id"], "choice-2", parameters=params)

    def test_invalid_or_uncertain_reply_aborts_and_never_retries(self):
        for fault in ("sequence", "action", "private", "lost"):
            with self.subTest(fault=fault):
                self.client.reset()
                self.backend.tamper = fault
                before = len(self.backend.calls)
                dec = self.client.view()["decisions"]
                with self.assertRaises((ProtocolError, TimeoutError)):
                    self.client.act(dec["decision_id"], "choice-1")
                with self.assertRaises(RuntimeError):
                    self.client.observe()
                self.assertEqual(len(self.backend.calls), before+1)
                self.assertTrue(self.backend.aborts)
                self.backend.tamper = None

    def test_close_and_reset_have_distinct_identities(self):
        closed = self.client.close()
        self.assertTrue(closed["outcome"]["truncated"])
        self.assertIsNone(self.client.close())
        reset = self.client.reset()
        self.assertNotEqual(reset["episode_id"], self.initial["episode_id"])
        self.assertEqual(reset["sequence"], 0)

    def test_alien_turn_mode_and_extra_sidecar_are_not_accepted(self):
        bad = self.backend.reset()
        bad["schema"] = "civ6rl.simultaneous.v1"
        with self.assertRaises(ProtocolError):
            self.client._accept(bad, "reset")

    def test_package_uses_only_stdlib_and_its_own_contracts(self):
        root = Path(__file__).resolve().parents[1]/"src/civ6_host"
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [x.name.split('.')[0] for x in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    names = [(node.module or '').split('.')[0]]
                else:
                    continue
                self.assertTrue(all(x in sys.stdlib_module_names or x=="civ6_host" for x in names),
                                (path.name,names))


if __name__ == "__main__":
    unittest.main()

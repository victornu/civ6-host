"""Client transport/identity tests: no game or neural-network runtime."""
import ast
import copy
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from civ6_host import HotseatClient, InformationUnavailable, ProtocolError
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

    def test_hotseat_occupation_hides_unoffered_owners_and_forwards_exact_native_choice(self):
        action = dict(kind="resolve_captured_city", city_id=9, directive="LIBERATE_PREVIOUS_OWNER")

        class OccupationBackend(Backend):
            def reply(self, operation, applied=None):
                result = super().reply(operation, applied)
                observation = result["observation"]
                city = dict(city_id=9, x=2, y=3, original_owner=5, previous_owner=4, conquered_from=6)
                occupation = dict(player_id=self.player, turn=self.turn, city=None, directives=[])
                if operation == "reset":
                    occupation.update(city=city, directives=["LIBERATE_PREVIOUS_OWNER"])
                    observation["cities"] = [dict(id=9, x=2, y=3, owner=self.player)]
                decisions = result["decisions"]
                decisions["captured_city"] = occupation
                decisions["candidates"] = ([dict(candidate_id=_digest(action), action=action)]
                                           if operation == "reset" else [])
                del decisions["decision_id"]
                decisions["decision_id"] = _digest(decisions)
                return result

            def request(self, request):
                self.calls.append(copy.deepcopy(request))
                self.seq += 1
                self.current = self.reply(request["operation"], action)
                return copy.deepcopy(self.current)

        backend = OccupationBackend()
        client = HotseatClient(backend)
        view = client.reset()
        decisions = view["decisions"]
        wire_id = backend.current["decisions"]["decision_id"]
        public_city = dict(city_id=9, x=2, y=3, liberation_recipients={"LIBERATE_PREVIOUS_OWNER": 4})
        self.assertEqual(decisions["captured_city"]["city"], public_city)
        self.assertNotEqual(decisions["decision_id"], wire_id)
        self.assertEqual(decisions["decision_id"], _digest({
            key: value for key, value in decisions.items() if key != "decision_id"}))
        information = client.information("captured_city")
        self.assertEqual(information["native_decision_id"], decisions["decision_id"])
        self.assertEqual(information["data"], decisions["captured_city"])
        information["data"]["city"].clear()
        self.assertEqual(client.information("captured_city")["data"]["city"], public_city)
        with self.assertRaises(InformationUnavailable):
            client.information("captured_city", player_id=4)
        with self.assertRaises(ProtocolError):
            client.act(wire_id, _digest(action))
        self.assertEqual(backend.calls, [])
        result = client.act(decisions["decision_id"], _digest(action))
        self.assertEqual(result["applied_action"], action)
        self.assertEqual(backend.calls[0]["selection"],
                         dict(decision_id=wire_id, candidate_id=_digest(action)))
        self.assertIsNone(client.information("captured_city")["data"]["city"])

    def test_hotseat_combat_uses_display_precision_and_preserves_the_native_choice(self):
        attack = dict(kind="unit_attack", unit_id=7, operation="RANGE_ATTACK",
                      input_route="dedicated_ranged", plot_id=3, x=3, y=0)

        class CombatBackend(Backend):
            visible = True

            def reply(self, operation, applied=None):
                result = super().reply(operation, applied)
                obs, dec = result["observation"], result["decisions"]
                unit = dict(id=7, type=9, owner=self.player, x=2, y=0, damage=0, moves=1)
                obs.update(width=6, height=1, units=[unit], visible_enemy_units=[],
                           plots=[dict(index=3, visible=self.visible)])
                dec.update(
                    schema="civ6rl.saved_decisions999.v1",
                    combat_units=[dict(unit_id=7, unit_type=9, x=2, y=0, damage=0,
                                       moves=1, attacks_remaining=int(operation=="reset"))],
                    combat_relationships=[dict(owner=1, at_war=True)],
                    combat_cities=[dict(owner=1, city_id=13, district_id=15, plot_id=3, x=3, y=0,
                                        garrison_damage=0 if operation=="reset" else 20,
                                        garrison_max=200, outer_damage=0, outer_max=0,
                                        defense_strength=20.03125)],
                    queued_orders=dict(player_id=self.player, turn=self.turn, width=6,
                                       height=1, units=[dict(unit_id=7, plot_id=None)]),
                    candidates=([dict(candidate_id=_digest(attack), action=attack)]
                                if operation=="reset" else []))
                del dec["decision_id"]
                dec["decision_id"] = _digest(dec)
                return result

            def request(self, request):
                self.calls.append(copy.deepcopy(request))
                self.seq += 1
                self.current = self.reply(request["operation"], attack)
                return copy.deepcopy(self.current)

        backend = CombatBackend()
        client = HotseatClient(backend)
        view = client.reset()
        wire_id = backend.current["decisions"]["decision_id"]
        public_id = view["decisions"]["decision_id"]
        self.assertNotEqual(wire_id, public_id)
        combat = client.information("combat")
        city, = combat["data"]["unit_attacks"]["cities"]
        self.assertEqual(city["defense_strength"], 20)
        self.assertIs(type(city["defense_strength"]), int)
        self.assertEqual(view["decisions"]["combat_cities"], [city])
        self.assertEqual(combat["data"]["unit_attacks"]["offers"], [attack])
        self.assertEqual(combat["native_decision_id"], public_id)
        combat["data"]["unit_attacks"]["offers"].clear()
        self.assertEqual(client.information("combat")["data"]["unit_attacks"]["offers"], [attack])
        with self.assertRaises(InformationUnavailable):
            client.information("combat", player_id=1)
        self.assertEqual(backend.calls, [])
        after = client.act(public_id, _digest(attack))
        self.assertEqual(backend.calls[0]["selection"]["decision_id"], wire_id)
        self.assertEqual(after["applied_action"], attack)
        self.assertEqual(client.information("combat")["data"]["unit_attacks"]["cities"][0]["garrison_damage"], 20)
        backend.visible = False
        with self.assertRaisesRegex(ProtocolError, "visible player observation"):
            client.reset()

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

"""The diagnostic reports a disagreement without changing the action menu."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_foundation_legality as foundation, execution_images


class FoundationLegalityTests(unittest.TestCase):
    def test_result_is_bound_to_the_public_unit_and_plot(self):
        units = [dict(id=17, x=3, y=4)]
        [row] = foundation.parse(b"17,3,4,0,0,1,1,LOC_UNIT_FOUNDING_TEST", units)
        self.assertFalse(row["official_query"])
        self.assertTrue(row["visibility_query"])
        self.assertEqual(row["reason_keys"], ["LOC_UNIT_FOUNDING_TEST"])
        with self.assertRaisesRegex(ValueError, "observed-unit subset"):
            foundation.parse(b"17,3,5,0,0,1,-1,", units)
        with self.assertRaisesRegex(ValueError, "admitted schema"):
            foundation.parse(b"17,3,4,0,0,1,1,not-a-localization-key", units)

    def test_result_is_an_ordered_subset_of_observed_units(self):
        units = [dict(id=11, x=1, y=2), dict(id=17, x=3, y=4), dict(id=19, x=5, y=6)]
        [row] = foundation.parse(b"17,3,4,0,1,1,0,", units)
        self.assertEqual(row["unit_id"], 17)
        self.assertEqual(foundation.parse(b"", units), [])
        with self.assertRaisesRegex(ValueError, "ordered observed-unit subset"):
            foundation.parse(b"17,3,4,0,1,1,0,;11,1,2,0,1,1,0,", units)
        with self.assertRaisesRegex(ValueError, "ordered observed-unit subset"):
            foundation.parse(b"20,1,2,0,1,1,0,", units)

    def test_official_query_does_not_replace_the_menu(self):
        response = dict(
            episode_id="episode", game_generation="generation", sequence=4,
            observation=dict(player_id=0, turn=21, units=[dict(id=11, type=4, x=1, y=2),
                                                           dict(id=17, type=37, x=3, y=4)]),
            decisions=dict(turn_controls=dict(active=True, active_complete=True), candidates=[]),
        )
        original = deepcopy(response)
        def evaluate(_child, source, _label, *, capacity):
            self.assertIn(b"OperationResultsTypes.ALL", source)
            self.assertIn(b"GameInfo.Units[unit:GetType()]", source)
            self.assertIn(b"info.UnitType=='UNIT_SETTLER'", source)
            self.assertNotIn(b"type==0", source)
            self.assertEqual(capacity, 32768)
            return b"17,3,4,0,1,1,0,"

        owner = SimpleNamespace(
            continuation=SimpleNamespace(check=lambda **_: None,
                transport=SimpleNamespace(require_empty_native_queue=lambda: None)),
            prefix=SimpleNamespace(runtime=SimpleNamespace(evaluate_text=evaluate), ui_child=None),
        )
        received = []
        foundation.emit_readback(owner, response, lambda name, **data: received.append((name, data)))
        [(name, data)] = received
        self.assertEqual(name, "xp2_bbg_foundation_legality_readback")
        self.assertFalse(data["actor_channel"])
        self.assertFalse(data["units"][0]["menu_query"])
        self.assertTrue(data["units"][0]["official_query"])
        self.assertEqual(response, original)

    def test_pin_sources_propagates_only_the_explicit_execution_image(self):
        execution_image = object()
        proof = {"installed_lua": {"file": "UnitPanel.lua", "sha256": "a" * 64,
                                    "references": [{"text": foundation._OFFICIAL_CALL}]}}
        with patch.object(foundation, "load_pinned_json", return_value=proof), \
             patch.object(foundation, "source_dependencies", return_value={"core.dll": "b" * 64}) as deps, \
             patch.object(foundation, "saved_load_pin") as pin:
            pins = {}
            foundation.pin_sources(pins, execution_image=execution_image)
        deps.assert_called_once_with(foundation.resource_root(),
                                     core_sha256=foundation.XP2_CORE_SHA256,
                                     execution_image=execution_image)
        pin.assert_any_call(pins, "core.dll", "b" * 64)

    def test_source_dependencies_use_registered_current_image_translation(self):
        from civ6_host.runtime.unit_operation_ui_profile import source_dependencies
        profile = execution_images.select(
            "xp2-gamecore-current-092abfbb", core_path=execution_images._GAMECORE_PATH)
        pins = source_dependencies(core_sha256=foundation.XP2_CORE_SHA256,
                                   execution_image=profile)
        self.assertEqual(pins[profile.path], profile.image_sha256)
        self.assertNotEqual(pins[profile.path], foundation.XP2_CORE_SHA256)

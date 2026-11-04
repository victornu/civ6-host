"""Golden-contract extraction checks; intentionally no game or learner imports."""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from civ6_host.contracts import plot_display990 as plot
from civ6_host.contracts import production_info988 as production
from civ6_host.contracts import research_info983 as research
from civ6_host.contracts import yield_display982 as yields


class ExtractedContractTests(unittest.TestCase):
    def test_plot_display_acceptance_and_exact_map_join(self):
        value = {
            "schema": plot.SCHEMA, "player_id": 0, "turn": 2, "width": 1, "height": 1,
            "yields_enabled": True, "source_sha256": plot.SOURCE_SHA256,
            "capability_source_sha256": plot.CAPABILITY_SOURCE_SHA256,
            "plots": [{"plot_id": 0, "improvement": None, "district": None,
                       "worked": None, "plot_yields": [], "specialist_yields": [], "district_yields": []}],
        }
        pmap = {"schema": "civ6rl.saved_player_map933.v1", "player_id": 0, "turn": 2,
                "width": 1, "height": 1,
                "plots": [{"index": 0, "x": 0, "y": 0, "revealed": True,
                           "visible": True, "impassable": False, "owner": -1}]}
        self.assertEqual(plot.validate_and_index(value, 0, 2, pmap), {0: value["plots"][0]})
        altered = dict(pmap, turn=3)
        with self.assertRaises(ValueError):
            plot.validate_and_index(value, 0, 2, altered)

    def test_production_acceptance_and_source_pin_refusal(self):
        value = {"schema": production.SCHEMA, "player_id": 0, "turn": 2,
                 "source_sha256": production.PROOF_SHA256, "ui_sha256": production.PANEL_SHA256,
                 "tooltip_sha256": production.TOOLTIP_SHA256, "rows": []}
        self.assertIs(production.validate(value, 0, 2, candidates=[], observation={
            "player_id": 0, "turn": 2, "cities": []}), value)
        bad = dict(value, ui_sha256="0" * 64)
        with self.assertRaises(ValueError):
            production.validate(bad, 0, 2)

    def test_research_acceptance_and_candidate_coverage_refusal(self):
        topic = {"selected": None, "selected_info": None, "choices": []}
        value = {"schema": research.SCHEMA, "player_id": 0, "turn": 2,
                 "technology": topic, "civic": topic}
        self.assertEqual(research.validate(value, 0, 2), {
            "schema": research.SCHEMA, "player_id": 0, "turn": 2,
            "technology": {"selected": None, "selected_info": None, "choices": []},
            "civic": {"selected": None, "selected_info": None, "choices": []},
        })
        with self.assertRaises(ValueError):
            research.validate(value, 0, 2, candidates=[
                {"candidate_id": "x", "action": {"kind": "research", "index": 1, "hash": 2}}
            ])

    def test_yield_acceptance_and_locale_or_numeric_refusal(self):
        row = {"schema": yields.SCHEMA, "player_id": 0, "turn": 2,
               "raw": {"science": 1.0, "culture": 2.0, "faith": 0.0, "faith_yield": 3.0},
               "public_display": {"science": "1.0", "culture": "2.0", "faith": "0.0", "faith_yield": "3.0"},
               "cities": []}
        self.assertEqual(yields.validate(row, 0, 2), row)
        bad = {**row, "public_display": {**row["public_display"], "science": "1e999"}}
        with self.assertRaises(ValueError):
            yields.validate(bad, 0, 2)

    def test_contract_modules_have_only_stdlib_imports(self):
        forbidden = {"torch", "civ6rl", "numpy"}
        for path in (ROOT / "src" / "civ6_host" / "contracts").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module.split(".")[0])
            self.assertFalse(forbidden.intersection(imports), path.name)


if __name__ == "__main__":
    unittest.main()

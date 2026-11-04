"""Read-only resource planning tests; synthetic files only, no GameCore."""
import ast
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from civ6_host.runtime.resources import (
    ResourcePlanError,
    _parse_json_object,
    plan_private_resources,
)


def write_json(path, value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), len(data)


class ResourcePlanTests(unittest.TestCase):
    def fixture(self, pins=None, exit_code=0):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        lab, game = base / "lab", base / "game"
        run = lab / "work" / "runs" / "test"
        run.mkdir(parents=True)
        game.mkdir()
        local = lab / "work" / "bundle" / "data.sqlite"
        local.parent.mkdir(parents=True)
        local.write_bytes(b"private synthetic data")
        external = game / "Base" / "GameCore.dll"
        external.parent.mkdir()
        external.write_bytes(b"external file")
        hashes = pins if pins is not None else {
            "work/bundle/data.sqlite": hashlib.sha256(local.read_bytes()).hexdigest(),
            str(external): hashlib.sha256(external.read_bytes()).hexdigest(),
        }
        official_sha, _ = write_json(lab / "work" / "bundle" / "official.json", {"proof": "bundle proof"})
        closure = run / "closure.json"
        closure_sha, _ = write_json(closure, {"schema": "test.v1", "pins": hashes,
            "official_bundle": {"path": "work/bundle/official.json", "sha256": official_sha}})
        events = run / "events.jsonl"
        events_sha, events_size = write_json(events, {"event": "synthetic"})
        supervisor = run / "supervisor.json"
        supervisor_sha, supervisor_size = write_json(supervisor, {
            "exit_code": exit_code, "reaped": True, "timed_out": False, "error": None,
            "termination_inferred_from_process_exit": False,
            "source_unchanged": {"native.py": True}})
        validation = lab / "work" / "native-validation.json"
        validation_data = {
            "native_run": str(run),
            "supervisor": {"path": str(supervisor), "sha256": supervisor_sha,
                           "bytes": supervisor_size},
            "reference_events": {"path": str(events), "sha256": events_sha,
                                 "bytes": events_size}}
        if exit_code == 90:
            validation_data.update({
                "status": "installed_backend_native_parity_verified",
                "backend_finished": True,
                "worker_reaped": True,
                "comparisons": [{
                    "operation": "close",
                    "public_observation_equal": True,
                    "catalogue_equal_except_episode_identity": True,
                    "applied_action_equal": True,
                    "outcome_equal": True,
                }],
            })
        validation_sha, _ = write_json(validation, validation_data)
        return locals()

    def plan(self, f, include_external=True):
        return plan_private_resources(validation_path=f["validation"],
            expected_validation_sha256=f["validation_sha"],
            expected_supervisor_sha256=f["supervisor_sha"],
            expected_closure_sha256=f["closure_sha"], lab_root=f["lab"],
            external_roots={"game_installation": f["game"]} if include_external else {})

    def test_verifies_local_and_external_pins_without_copying(self):
        f = self.fixture()
        plan = self.plan(f)
        self.assertEqual("verified_plan", plan["status"])
        self.assertEqual(2, plan["run"]["unique_canonical_files_verified"])
        self.assertEqual(1, plan["pin_scope_counts"]["lab_local"])
        self.assertEqual(1, plan["pin_scope_counts"]["external:game_installation"])
        self.assertFalse(plan["copy_performed"])
        self.assertFalse(plan["lab_python_executed"])

    def test_closure_digest_is_an_explicit_trust_anchor(self):
        f = self.fixture()
        with self.assertRaisesRegex(ResourcePlanError, "closure digest"):
            plan_private_resources(validation_path=f["validation"],
                expected_validation_sha256=f["validation_sha"],
                expected_supervisor_sha256=f["supervisor_sha"],
                expected_closure_sha256="0" * 64, lab_root=f["lab"],
                external_roots={"game_installation": f["game"]})

    def test_accepts_exit_90_only_with_verified_requested_close(self):
        f = self.fixture(exit_code=90)
        plan = self.plan(f)
        self.assertEqual("verified_plan", plan["status"])
        self.assertTrue(plan["proofs"]["controlled_worker_close_exit"])

        f = self.fixture(exit_code=90)
        validation = json.loads(f["validation"].read_text(encoding="utf-8"))
        validation["comparisons"] = []
        f["validation_sha"], _ = write_json(f["validation"], validation)
        plan = self.plan(f)
        self.assertEqual("blocked", plan["status"])
        self.assertFalse(plan["proofs"]["controlled_worker_close_exit"])

    def test_proof_json_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(ResourcePlanError, "duplicate JSON key"):
            _parse_json_object(b'{"pins": {}, "pins": {}}', "synthetic proof")

    def test_parent_traversal_and_unclassified_external_paths_block(self):
        f = self.fixture(pins={"../escape.bin": "a" * 64,
                               str(Path(tempfile.gettempdir()) / "outside.bin"): "b" * 64})
        plan = self.plan(f, include_external=False)
        self.assertEqual("blocked", plan["status"])
        self.assertEqual(1, plan["blocker_counts"]["invalid_pin_path"])
        self.assertEqual(1, plan["blocker_counts"]["unclassified_external"])

    def test_symlink_redirection_is_refused(self):
        f = self.fixture(pins={})
        link = f["lab"] / "work" / "bundle" / "redirect.bin"
        try:
            link.symlink_to(f["external"])
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        f["closure_sha"], _ = write_json(f["closure"], {"schema": "test.v1",
            "pins": {"work/bundle/redirect.bin": hashlib.sha256(f["external"].read_bytes()).hexdigest()}})
        plan = self.plan(f)
        self.assertEqual("blocked", plan["status"])
        self.assertEqual(1, plan["blocker_counts"]["symlink_escape"])

    def test_mutated_pin_and_conflicting_aliases_block(self):
        f = self.fixture()
        f["local"].write_bytes(b"changed")
        plan = self.plan(f)
        self.assertGreaterEqual(plan["blocker_counts"].get("pin_hash_mismatch", 0), 1)

        f = self.fixture(pins={})
        digest = hashlib.sha256(f["local"].read_bytes()).hexdigest()
        f["closure_sha"], _ = write_json(f["closure"], {"schema": "test.v1", "pins": {
            "work/bundle/data.sqlite": digest, str(f["local"]): "b" * 64}})
        plan = self.plan(f)
        self.assertEqual(1, plan["blocker_counts"]["conflicting_alias_hashes"])

    def test_module_is_stdlib_only_and_does_not_execute_lab_python(self):
        path = ROOT / "src" / "civ6_host" / "runtime" / "resources.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"civ6rl", "torch", "numpy", "subprocess"}.intersection(imports))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id in {"exec", "eval", "compile"} for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()

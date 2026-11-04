"""Synthetic private-capture package tests; never load GameCore."""
import hashlib
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from civ6_host.runtime.capture_package import (
    CapturePackageError,
    export_capture,
    read_package,
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class CapturePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "admitted"
        self.source.mkdir()
        self.dest_parent = self.base / "packages"
        self.dest_parent.mkdir()
        self.origin_bytes = json.dumps({"schema": "synthetic.capture.v1", "capture": 3},
            sort_keys=True, separators=(",", ":")).encode()
        self.origin_relative = "captures/origin/manifest.json"
        self.origin = self.source / "captures" / "origin" / "manifest.json"
        self.origin.parent.mkdir(parents=True)
        self.origin.write_bytes(self.origin_bytes)
        config = b"configuration stream"
        game = b"gamecore stream"
        dbs = {}
        for role in ("configuration", "gameplay", "localization"):
            path = self.source / f"{role}.sqlite"
            raw = f"sqlite fixture {role}".encode()
            path.write_bytes(raw)
            dbs[role] = {"path": str(path), "sha256": digest(raw), "size_bytes": len(raw)}
        icu = self.source / "icu.dat"
        icu_bytes = b"icu bytes"
        icu.write_bytes(icu_bytes)
        engine = self.source / "GameCore.dll"
        engine_bytes = b"external-engine-witness"
        engine.write_bytes(engine_bytes)
        engine_sha = digest(engine_bytes)
        profile = SimpleNamespace(mode_name="HOTSEAT", config_sha="c" * 64,
            game_sha="d" * 64, config_start=0, config_end=5, game_bytes=17)
        inputs = SimpleNamespace(configuration=config, game=game, profile=profile,
            map_values=(("start", None), ("world_age", 2), ("RANDOM_SEED", 42), ("MAP_SIZE", 4)))
        self.bundle = SimpleNamespace(
            reference=(self.origin_relative, digest(self.origin_bytes)),
            inputs=inputs,
            initial_turn=1,
            engine_path=engine,
            fixture={"input_profile": "hotseat-four", "databases": dbs,
                "localization_bootstrap": {"locale": "en_US", "dictionary_flag": False,
                    "icu_data": {"path": str(icu), "sha256": digest(icu_bytes)},
                    "official_export": {"sha256": "a" * 64}}},
            dependencies={str(engine.resolve()): engine_sha,
                str(self.origin.resolve()): digest(self.origin_bytes)},
            expected_readback={"turn": 1, "width": 4, "height": 3, "player_id": 0,
                "gold": 10, "city_count": 1, "units": []},
            content_profile={"schema": "civ6rl.official_content_profile.v1",
                "engine": {"gamecore_sha256": engine_sha},
                "localization_bootstrap": {"locale": "en_US", "dictionary_flag": False,
                    "icu_sha256": digest(icu_bytes)}},
        )
        self.destination = self.dest_parent / "capture-package"

    def export(self):
        return export_capture(self.bundle, self.destination,
            source_manifest_bytes=self.origin_bytes,
            validation_identity={"validation_sha256": "b" * 64, "source": "test fixture"})

    def test_exports_and_reads_verified_compact_package(self):
        reference = self.export()
        manifest, root, files = read_package(reference)
        self.assertEqual(self.destination, root)
        self.assertEqual("civ6-host.prepared-capture.v1", manifest["schema"])
        self.assertEqual(self.origin_relative, manifest["origin"]["path"])
        self.assertEqual(digest(self.origin_bytes), manifest["origin_manifest_sha256"])
        self.assertEqual(self.origin_bytes, files["origin_manifest"].read_bytes())
        self.assertEqual("icu.dat", manifest["localization_bootstrap"]["icu_data"]["path"])
        self.assertEqual(len(b"icu bytes"), manifest["localization_bootstrap"]["icu_data"]["bytes"])
        self.assertEqual({"locale", "dictionary_flag", "icu_data", "official_export"},
                         set(manifest["localization_bootstrap"]))
        self.assertEqual("b" * 64, manifest["validation_identity"]["validation_sha256"])
        self.assertEqual(str(self.bundle.engine_path), manifest["engine"]["path"])
        self.assertFalse((root / "GameCore.dll").exists())

    def test_lan_capture_keeps_its_mode_and_exact_streams(self):
        from civ6_host.runtime.capture_profiles import LAN_PROFILE
        from civ6_host.runtime.session_configuration import read_saved_settings
        from test_session_configuration import configuration
        self.bundle.fixture["input_profile"] = "lan"
        self.bundle.inputs.profile = LAN_PROFILE
        self.bundle.inputs.configuration = configuration("LAN", "TURNPHASE_SIMULTANEOUS")
        reference = self.export()
        manifest, _, files = read_package(reference)
        self.assertEqual(manifest["input_profile"], "lan")
        self.assertEqual(files["configuration_stream"].read_bytes(), self.bundle.inputs.configuration)
        self.assertEqual(files["gamecore_stream"].read_bytes(), self.bundle.inputs.game)
        saved = read_saved_settings(files["configuration_stream"].read_bytes())
        self.assertEqual(saved["game_mode"]["name"], "LAN")
        self.assertTrue(saved["game_mode"]["network_mode_token"])
        self.assertNotIn("native_session_admitted", manifest)

    def test_lan_label_cannot_replace_hotseat_loader_profile(self):
        self.bundle.fixture["input_profile"] = "lan"
        with self.assertRaisesRegex(CapturePackageError, "loader profile"):
            self.export()

    def test_network_family_does_not_admit_unknown_modes(self):
        from civ6_host.runtime.capture_profiles import profile_for_capture
        for name in ("internet", "LAN", "unknown", None):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "Unsupported official capture"):
                    profile_for_capture(name)

    def test_destination_is_never_overwritten(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep.txt"
        sentinel.write_text("untouched", encoding="utf-8")
        with self.assertRaisesRegex(CapturePackageError, "already exists"):
            self.export()
        self.assertEqual("untouched", sentinel.read_text(encoding="utf-8"))

    def test_changed_source_database_is_refused(self):
        Path(self.bundle.fixture["databases"]["gameplay"]["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(CapturePackageError, "hash or size differs"):
            self.export()
        self.assertTrue(self.destination.is_dir())
        self.assertFalse((self.destination / "manifest.json").exists())

    def test_package_file_tampering_is_refused(self):
        reference = self.export()
        (self.destination / "configuration.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(CapturePackageError, "package file differs"):
            read_package(reference)

    def test_external_engine_tampering_is_refused(self):
        reference = self.export()
        self.bundle.engine_path.write_bytes(b"changed engine")
        with self.assertRaisesRegex(CapturePackageError, "external engine changed"):
            read_package(reference)

    def test_source_manifest_bytes_must_match_origin_reference(self):
        with self.assertRaisesRegex(CapturePackageError, "provided source manifest bytes"):
            export_capture(self.bundle, self.destination,
                source_manifest_bytes=b'{"different":true}', validation_identity={})
        self.assertFalse(self.destination.exists())

    def test_reader_rejects_manifest_path_escape_even_with_new_reference_hash(self):
        reference = self.export()
        manifest_path = Path(reference["path"])
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        manifest["files"]["gamecore_stream"]["path"] = "../outside.bin"
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"
        manifest_path.write_bytes(raw)
        altered_reference = {"path": str(manifest_path), "sha256": digest(raw)}
        with self.assertRaisesRegex(CapturePackageError, "unexpected relative path"):
            read_package(altered_reference)

    def test_module_has_no_laboratory_or_native_execution_dependency(self):
        path = ROOT / "src" / "civ6_host" / "runtime" / "capture_package.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"civ6rl", "torch", "numpy", "subprocess"}.intersection(imports))


if __name__ == "__main__":
    unittest.main()

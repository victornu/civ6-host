from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from civ6_host.runtime.native import native_official_bundle as bundle_reader
from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA


class OfficialBundleContentProfileVersionTests(unittest.TestCase):
    def _base_inputs(self, executable_sha):
        process = {
            "exe_sha256": executable_sha,
            "gamecore_module": {"sha256": "2" * 64},
        }
        databases = {
            name: {"sha256": str(index) * 64, "size_bytes": index + 10}
            for index, name in enumerate(("configuration", "gameplay", "localization"), 1)
        }
        localization = {
            "locale": "en_US", "dictionary_flag": False,
            "icu_data": {"sha256": "4" * 64},
        }
        gameplay_selection = {"selected_paths": []}
        active_state = {"active_count": 0, "selected_and_active_empty": True}
        script_manifest = {"records": [], "files": {}}
        return process, databases, localization, gameplay_selection, active_state, script_manifest

    def test_v1_profile_keeps_legacy_configured_vector_and_shape(self):
        values = self._base_inputs("1" * 64)
        resolved = {
            "configured_mod_handles": [11], "active_mod_handles": [12],
            "ordered_component_handles": [13],
        }
        profile = bundle_reader.build_content_profile(
            process=values[0], databases=values[1], localization_bootstrap=values[2],
            resolved_content=resolved, gameplay_selection=values[3],
            active_state=values[4], script_manifest=values[5])
        self.assertEqual(profile["schema"], "civ6rl.official_content_profile.v1")
        self.assertEqual(profile["resolved_content_vectors"], resolved)
        self.assertNotIn("opaque_manager_headers", profile)

    def test_v2_profile_contains_two_vectors_and_raw_opaque_header_only(self):
        values = self._base_inputs(CURRENT_EXE_SHA)
        resolved = {
            "manager_address": "0x1000", "provider_address": "0x2000",
            "active_mod_handles": [111, 112, 158, 166],
            "ordered_component_handles": [1569, 1527, 1530],
            "vector_headers_hex": {
                "active_mod_handles": "90" * 24,
                "ordered_component_handles": "20" * 24,
            },
            "opaque_manager_headers": {"manager_plus_0x1d8": "70" * 24},
        }
        profile = bundle_reader.build_content_profile(
            process=values[0], databases=values[1], localization_bootstrap=values[2],
            resolved_content=resolved, gameplay_selection=values[3],
            active_state=values[4], script_manifest=values[5])
        self.assertEqual(profile["schema"], "civ6rl.official_content_profile.v2")
        self.assertEqual(set(profile["resolved_content_vectors"]), {
            "active_mod_handles", "ordered_component_handles"})
        self.assertEqual(profile["opaque_manager_headers"], resolved["opaque_manager_headers"])
        self.assertNotIn("configured_mod_handles", profile["resolved_content_vectors"])
        self.assertIs(profile["cross_capture_equivalence_supported"], False)

        malformed = dict(resolved)
        malformed["opaque_manager_headers"] = {"manager_plus_0x1d8": "70" * 23}
        with self.assertRaisesRegex(ValueError, "opaque current resolved-content manager header"):
            bundle_reader.build_content_profile(
                process=values[0], databases=values[1], localization_bootstrap=values[2],
                resolved_content=malformed, gameplay_selection=values[3],
                active_state=values[4], script_manifest=values[5])
        unsupported = dict(resolved, configured_mod_handles=[])
        with self.assertRaisesRegex(ValueError, "v2 contract"):
            bundle_reader.build_content_profile(
                process=values[0], databases=values[1], localization_bootstrap=values[2],
                resolved_content=unsupported, gameplay_selection=values[3],
                active_state=values[4], script_manifest=values[5])

    def test_world_a_current_capture_content_semantics_has_v2_fields(self):
        root = bundle_reader.ROOT
        manifest_path = root / "work/official-capture/bbg751-world-A-ui/manifest.json"
        raw = manifest_path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d")
        selections_path = manifest_path.parent / "runtime-selections-before.json"
        selections = json.loads(selections_path.read_bytes())
        snapshot = selections["content929"]["snapshot"]
        self.assertEqual(snapshot["schema"], "civ6rl.resolved_content929.memory_snapshot.v2")
        for name in ("active_mod_handles", "ordered_component_handles"):
            self.assertIsInstance(snapshot[name], list)
        self.assertNotIn("configured_mod_handles", snapshot)
        self.assertEqual(set(snapshot["opaque_manager_headers"]), {"manager_plus_0x1d8"})
        self.assertIs(snapshot["opaque_manager_fields_interpreted"], False)

        from civ6_host.runtime.workers.capture_phase1_bundle994 import _content_semantics, _join_native_report
        captured_process = json.loads(raw)["preflight"]["process"]
        _join_native_report(selections["content929"], captured_process,
                            "civ6rl.official_resolved_content929.capture.v2")
        with self.assertRaisesRegex(ValueError, "Unexpected runtime selection report"):
            _join_native_report(selections["content929"], captured_process,
                                "civ6rl.official_resolved_content929.capture.v1")
        semantic = _content_semantics(snapshot, captured_process)
        self.assertEqual(set(semantic["active_mod_handles"]), {111, 112, 158, 166})
        self.assertEqual(semantic["ordered_component_handles"], snapshot["ordered_component_handles"])
        self.assertEqual(semantic["opaque_manager_headers"], snapshot["opaque_manager_headers"])
        self.assertEqual(set(semantic["vector_headers_hex"]), {
            "active_mod_handles", "ordered_component_handles"})
        self.assertNotIn("configured_mod_handles", semantic)


if __name__ == "__main__":
    unittest.main()

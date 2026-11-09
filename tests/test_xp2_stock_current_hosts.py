"""Stock XP2 current-image source-build selection; no GameCore load."""
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from civ6_host.runtime import capture_admission, xp1_session_inputs, xp2_session_inputs
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.source_build_identity import CURRENT_STRINGS_HOST_REFERENCE
from civ6_host.runtime import source_build_identity
from civ6_host.runtime import xp2_bundle_inputs as xp2
from civ6_host.runtime.execution_images import known_path, select


PACKAGE = {
    "path": str(resource_root() / "work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json"),
    "sha256": "6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020",
}
IMAGE = select("xp2-gamecore-current-092abfbb",
               core_path=known_path("xp2-gamecore-current-092abfbb"))
CURRENT_HOST = (str((resource_root() / CURRENT_STRINGS_HOST_REFERENCE[0]).resolve()),
                CURRENT_STRINGS_HOST_REFERENCE[1])


class XP2StockCurrentHostTests(unittest.TestCase):
    def test_both_dependency_and_executable_paths_select_the_same_verified_host(self):
        with patch.object(capture_admission, "configured_reference", return_value=PACKAGE), \
             patch.object(source_build_identity, "verify_source_build",
                          wraps=source_build_identity.verify_source_build) as verify:
            dependencies = xp2_session_inputs.xp2_saved_load_source_dependencies(
                postload160=True, observe_player=True, official_bundle=xp2.REFERENCE,
                execution_image=IMAGE)
            pins = {}
            executable = xp1_session_inputs.saved_load_build_pins(
                pins, ui=True, core_sha256=XP2_CORE_SHA256,
                official_bundle=xp2.REFERENCE, execution_image=IMAGE)

        self.assertEqual(executable, resource_root() / CURRENT_STRINGS_HOST_REFERENCE[0])
        self.assertTrue(dependencies)
        self.assertEqual(CURRENT_HOST[1], hashlib.sha256(Path(CURRENT_HOST[0]).read_bytes()).hexdigest())
        self.assertEqual(CURRENT_HOST[1], pins[CURRENT_HOST[0]])
        self.assertEqual([Path(CURRENT_HOST[0]), Path(CURRENT_HOST[0])],
                         [Path(call.args[0]).resolve() for call in verify.call_args_list])

    def test_current_host_selection_rejects_another_origin_before_source_build(self):
        wrong_origin = ("work/official-capture/other/manifest.json", "0" * 64)
        with patch.object(capture_admission, "configured_reference", return_value=PACKAGE):
            with self.assertRaisesRegex(ValueError, "exact retained stock XP2 package and origin"):
                xp2_session_inputs.xp2_saved_load_source_dependencies(
                    postload160=True, observe_player=True, official_bundle=wrong_origin,
                    execution_image=IMAGE)
            with self.assertRaisesRegex(ValueError, "exact retained stock XP2 package and origin"):
                xp1_session_inputs.saved_load_build_pins(
                    {}, ui=True, core_sha256=XP2_CORE_SHA256,
                    official_bundle=wrong_origin, execution_image=IMAGE)


if __name__ == "__main__":
    unittest.main()

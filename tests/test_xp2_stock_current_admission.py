"""Exact stock XP2 input admission for the registered current Core; no game launch."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import capture_admission, capture_candidates, capture_package
from civ6_host.runtime import xp2_bundle_inputs as xp2
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.paths import resource_root


LAB = resource_root()
PACKAGE = {
    "path": str(LAB / "work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json"),
    "sha256": "6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020",
}
IMAGE = select("xp2-gamecore-current-092abfbb",
               core_path=known_path("xp2-gamecore-current-092abfbb"))


class XP2StockCurrentAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.package_root, cls.files = capture_package.read_package(
            PACKAGE, _candidate_profile="xp2-lan", execution_image=IMAGE)

    def test_real_retained_package_preserves_capture_core_and_checks_current_image(self):
        self.assertEqual(xp2.REFERENCE[1], self.manifest["origin"]["sha256"])
        self.assertEqual(IMAGE.reference_core_sha256, self.manifest["engine"]["sha256"])
        self.assertEqual(IMAGE.reference_core_sha256,
                         self.manifest["content_profile"]["engine"]["gamecore_sha256"])
        self.assertEqual(IMAGE.image_sha256, capture_package._hash_file(Path(IMAGE.path))[0])
        self.assertEqual(IMAGE.path, self.manifest["engine"]["path"])
        with self.assertRaisesRegex(capture_package.CapturePackageError,
                                    "external engine changed since package export"):
            capture_package.read_package(PACKAGE, _candidate_profile="xp2-lan")

    def test_current_engine_path_refuses_other_package_origin_and_image(self):
        candidate = capture_candidates.select_private_candidate(candidate_profile="xp2-lan")
        engine = self.manifest["engine"]
        content = self.manifest["content_profile"]
        engine_path = Path(engine["path"])
        with tempfile.TemporaryDirectory() as temporary:
            wrong_package_path = Path(temporary) / "manifest.json"
            wrong_package_path.write_text("{}", encoding="ascii")
            wrong_ref = dict(PACKAGE, path=str(wrong_package_path))
            with self.assertRaisesRegex(capture_package.CapturePackageError,
                                       "exact retained stock XP2 package"):
                capture_package._check_stock_current_engine(
                    wrong_ref, self.manifest["origin"], candidate, engine,
                    content, engine_path, IMAGE)
        wrong_origin = dict(self.manifest["origin"], sha256="0" * 64)
        with self.assertRaisesRegex(capture_package.CapturePackageError,
                                   "exact retained stock XP2 package"):
            capture_package._check_stock_current_engine(
                PACKAGE, wrong_origin, candidate, engine, content, engine_path, IMAGE)
        with self.assertRaises(ValueError):
            capture_package._check_stock_current_engine(
                PACKAGE, self.manifest["origin"], candidate, engine, content,
                engine_path, object())

    def test_current_engine_bytes_are_rehashed_after_profile_verification(self):
        candidate = capture_candidates.select_private_candidate(candidate_profile="xp2-lan")
        engine = self.manifest["engine"]
        path = Path(engine["path"])
        with patch("civ6_host.runtime.execution_images.verify"), \
             patch.object(capture_package, "_hash_file", return_value=("0" * 64, 1)):
            with self.assertRaisesRegex(capture_package.CapturePackageError,
                                       "selected current XP2 engine bytes"):
                capture_package._check_stock_current_engine(
                    PACKAGE, self.manifest["origin"], candidate, engine,
                    self.manifest["content_profile"], path, IMAGE)

    def test_handoff_requires_explicit_image_once_stock_association_exists(self):
        association = (PACKAGE, xp2.REFERENCE, {
            "profile_id": IMAGE.id, "image_sha256": IMAGE.image_sha256,
            "reference_core_sha256": IMAGE.reference_core_sha256, "path": IMAGE.path,
        }, IMAGE, {"mode": "retained_preparation_producer"})
        with patch.object(capture_admission, "_STOCK_XP2_EXECUTION_ASSOCIATION", association):
            with self.assertRaisesRegex(ValueError, "explicitly repeat its selected image"):
                capture_admission.require_explicit_stock_execution(PACKAGE, None)
            self.assertIsNone(capture_admission.require_explicit_stock_execution(PACKAGE, IMAGE))

    def test_input_dispatch_forwards_only_an_explicit_stock_xp2_image(self):
        bundle = SimpleNamespace(inputs=object())
        candidate = SimpleNamespace(reference=xp2.REFERENCE, family="xp2-lan",
                                    validate_inputs=lambda _inputs, _bundle: None)
        with patch.object(capture_admission, "configure"), \
             patch.object(capture_candidates, "select_private_candidate", return_value=candidate), \
             patch.object(capture_admission, "try_bundle", return_value=bundle) as admission:
            result = capture_candidates.consume_input_handoff(
                "xp2-lan", PACKAGE, official_bundle=xp2.REFERENCE,
                execution_image=IMAGE)
        self.assertIs(result, bundle)
        self.assertEqual(admission.call_args.kwargs["execution_image"], IMAGE)

        wrong = SimpleNamespace(reference=("work/other.json", "0" * 64), family="xp1-lan",
                                validate_inputs=lambda *_args: None)
        with patch.object(capture_admission, "configure"), \
             patch.object(capture_candidates, "select_private_candidate", return_value=wrong), \
             patch.object(capture_admission, "try_bundle") as rejected:
            with self.assertRaisesRegex(ValueError, "exact stock XP2 capture"):
                capture_candidates.consume_input_handoff(
                    "xp1-lan", PACKAGE, official_bundle=wrong.reference,
                    execution_image=IMAGE)
        rejected.assert_not_called()

    def test_failed_stock_validation_does_not_register_association(self):
        with patch.object(capture_admission, "_STOCK_XP2_EXECUTION_ASSOCIATION", None), \
             patch.object(capture_admission, "_load", side_effect=ValueError("invalid package")):
            with self.assertRaisesRegex(ValueError, "invalid package"):
                capture_admission.try_bundle(xp2.REFERENCE, input_profile="xp2-lan",
                    _candidate_profile="xp2-lan", execution_image=IMAGE)
            self.assertIsNone(capture_admission._STOCK_XP2_EXECUTION_ASSOCIATION)

    def test_localization_uses_only_the_frozen_same_capture_image(self):
        source_capture = json.loads(
            (LAB / xp2.REFERENCE[0]).read_text(encoding="utf-8"))
        association = (PACKAGE, xp2.REFERENCE, {
            "profile_id": IMAGE.id, "image_sha256": IMAGE.image_sha256,
            "reference_core_sha256": IMAGE.reference_core_sha256, "path": IMAGE.path,
        }, IMAGE, {"mode": "retained_preparation_producer"})
        loaded = (PACKAGE, self.manifest, self.package_root, self.files, source_capture)
        with patch.object(capture_admission, "_STOCK_XP2_EXECUTION_ASSOCIATION", association), \
             patch.object(capture_admission, "configured_reference", return_value=PACKAGE), \
             patch.object(capture_admission, "_load", return_value=loaded) as load, \
             patch.object(capture_admission, "_files",
                          return_value=capture_admission._files(self.manifest, self.package_root)), \
             patch.object(capture_admission, "_check_localization", return_value={"locale": "fr_FR"}):
            result = capture_admission.try_localization(
                source_capture, {}, reference=xp2.REFERENCE)
        self.assertEqual(result[0]["sha256"], self.manifest["files"]["database_localization"]["sha256"])
        self.assertEqual(load.call_args.kwargs["execution_image"], IMAGE)
        self.assertEqual(load.call_args.kwargs["_candidate_profile"], "xp2-lan")

    def test_default_loader_still_runs_the_legacy_xp2_reader_gate(self):
        producer_manifest = self.manifest
        producer_identity = producer_manifest["validation_identity"]
        consumer_identity = dict(producer_identity, runtime_sources={})
        with patch.object(capture_admission, "configured_reference", return_value=PACKAGE), \
             patch.object(capture_admission, "validation_identity", return_value=consumer_identity), \
             patch.object(capture_package, "read_package",
                          return_value=(producer_manifest, self.package_root, self.files)), \
             patch.object(capture_admission, "admit_producer", return_value={"mode": "retained"}), \
             patch.object(capture_admission, "_check_xp2_prepared_reader",
                          side_effect=ValueError("legacy reader gate")) as gate:
            with self.assertRaisesRegex(ValueError, "legacy reader gate"):
                capture_admission._load(_candidate_profile="xp2-lan")
        gate.assert_called_once()

    def test_explicit_current_load_keeps_producer_identity_and_uses_full_stock_reader(self):
        with patch.dict(os.environ, {capture_admission.ENV: json.dumps(PACKAGE)}), \
             patch.object(capture_admission, "_SETTING", capture_admission._UNSET), \
             patch.object(capture_admission, "_check_xp2_prepared_reader",
                          side_effect=AssertionError("legacy parser gate must not run")) as gate:
            loaded = capture_admission._load(
                _candidate_profile="xp2-lan", execution_image=IMAGE)
        gate.assert_not_called()
        self.assertEqual(PACKAGE, loaded[0])
        self.assertEqual("fb8f64fccfaab86e947eb3f9263a149854bf0a2e7f50cc52fc5ecc6f218993bd",
                         capture_admission._sha(json.dumps(
                             loaded[1]["validation_identity"], sort_keys=True,
                             separators=(",", ":")).encode()))
        self.assertEqual(IMAGE.reference_core_sha256,
                         loaded[4]["preflight"]["process"]["gamecore_module"]["sha256"])


if __name__ == "__main__":
    unittest.main()

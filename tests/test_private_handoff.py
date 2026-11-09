"""Private transfer integrity, path containment and historical timestamps."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("private_handoff", Path(__file__).parents[1] / "tools/private_handoff.py")
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


class HandoffTests(unittest.TestCase):
    def test_round_trip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "source.json"
            payload = '{"épreuve": true}'.encode("utf-8")
            source.write_bytes(payload)
            os.utime(source, ns=(1700000000123456700, 1700000000123456700))
            expected_time = source.stat().st_mtime_ns
            selection = root / "selection.json"
            selection.write_text(json.dumps({"files": [{"source": str(source),
                "path": "work/nested/proof.json", "sha256": hashlib.sha256(payload).hexdigest()}]}), encoding="utf-8")
            archive = root / "private.zip"
            handoff.pack(selection, archive)
            self.assertTrue(handoff.unpack(archive)["hashes_verified"])
            destination = root / "unpacked"
            result = handoff.unpack(archive, destination)
            self.assertFalse(result["native_readiness_verified"])
            copied = destination / "work/nested/proof.json"
            self.assertEqual(copied.read_bytes(), payload)
            self.assertEqual(copied.stat().st_mtime_ns, expected_time)
            with self.assertRaises(ValueError):
                handoff.unpack(archive, destination)

    def test_unsafe_names_and_bad_digest_are_refused(self):
        for name in ("../escape", "C:/escape", "work/a:stream", "work/CON", "valid.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                archive = root / "private.zip"
                manifest = dict(schema=handoff.SCHEMA, private=True, files=[dict(
                    path=name, sha256="0" * 64, bytes=1, mtime_ns=0)])
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr(name, b"x")
                    output.writestr(handoff.MANIFEST, json.dumps(manifest))
                with self.assertRaises(ValueError):
                    handoff.unpack(archive)


if __name__ == "__main__":
    unittest.main()

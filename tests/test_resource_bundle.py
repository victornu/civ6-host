"""Synthetic tests for explicit private resource set export and verification."""
import ast
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from civ6_host.runtime.resource_bundle import (
    ResourceBundleError,
    export_resources,
    read_resources,
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ResourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "old-root"
        self.source.mkdir()
        self.destination = self.base / "new-root"
        self.data = {
            "databases/configuration.sqlite": b"config sqlite contents",
            "databases/gameplay.sqlite": b"gameplay sqlite contents",
            "work/icu/icu.dat": bytes(range(256)) * 7,
        }
        self.pins = {}
        for relative, raw in self.data.items():
            path = self.source / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.pins[relative] = sha(raw)

    def export(self):
        return export_resources(source_root=self.source, destination=self.destination,
                                files=self.pins)

    def test_exports_preserved_layout_and_verifies_hashes(self):
        reference = self.export()
        verified = read_resources(reference, resource_root=self.destination)
        self.assertEqual("civ6-host.private-resources.v1", verified["schema"])
        self.assertEqual(str(self.source.resolve()), verified["source_root"])
        for relative, raw in self.data.items():
            path = self.destination / Path(relative)
            self.assertEqual(relative, path.relative_to(self.destination).as_posix())
            self.assertEqual(raw, path.read_bytes())
        self.assertEqual(self.destination / "private-resources.json", Path(reference["path"]))

    def test_source_hash_mismatch_does_not_write_valid_manifest(self):
        (self.source / "databases" / "gameplay.sqlite").write_bytes(b"changed")
        with self.assertRaisesRegex(ResourceBundleError, "source hash differs"):
            self.export()
        self.assertTrue(self.destination.is_dir())
        self.assertFalse((self.destination / "private-resources.json").exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ResourceBundleError, "already exists"):
            self.export()
        self.assertEqual("keep", sentinel.read_text(encoding="utf-8"))

    def test_windows_aliases_and_file_directory_collisions_are_rejected(self):
        digest = "a" * 64
        cases = (
            {"Assets/Icon.dat": digest, "assets/icon.dat": digest},
            {"Assets/a.dat": digest, "assets/b.dat": digest},
            {"cache": digest, "cache/item.bin": digest},
        )
        for pins in cases:
            with self.subTest(pins=pins), self.assertRaises(ResourceBundleError):
                export_resources(source_root=self.source,
                    destination=self.base / f"bad-{len(pins)}-{len(str(pins))}", files=pins)

    def test_absolute_traversal_and_nonportable_paths_are_rejected(self):
        digest = "a" * 64
        for path in ("../escape", str(self.source / "databases" / "configuration.sqlite"),
                     "C:/private/file.bin", "dir\\file.bin", "NUL.txt", "name."):
            with self.subTest(path=path), self.assertRaises(ResourceBundleError):
                export_resources(source_root=self.source,
                    destination=self.base / f"bad-{abs(hash(path))}", files={path: digest})

    def test_reader_detects_copy_and_manifest_reference_tampering(self):
        reference = self.export()
        target = self.destination / "databases" / "configuration.sqlite"
        target.write_bytes(b"tampered")
        with self.assertRaisesRegex(ResourceBundleError, "hash or size differs"):
            read_resources(reference, resource_root=self.destination)
        with self.assertRaisesRegex(ResourceBundleError, "digest differs"):
            read_resources({**reference, "sha256": "0" * 64}, resource_root=self.destination)

    def test_reader_rejects_resource_root_mismatch(self):
        reference = self.export()
        other = self.base / "other-root"
        other.mkdir()
        with self.assertRaisesRegex(ResourceBundleError, "resource root"):
            read_resources(reference, resource_root=other)

    def test_source_and_package_symlink_redirections_are_refused(self):
        source_link = self.source / "redirected.bin"
        try:
            source_link.symlink_to(self.source / "databases" / "configuration.sqlite")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaisesRegex(ResourceBundleError, "canonical in-root"):
            export_resources(source_root=self.source, destination=self.destination,
                files={"redirected.bin": self.pins["databases/configuration.sqlite"]})
        source_link.unlink()

        reference = self.export()
        packaged_link = self.destination / "work" / "icu" / "icu.dat"
        packaged_link.unlink()
        try:
            packaged_link.symlink_to(self.source / "work" / "icu" / "icu.dat")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaisesRegex(ResourceBundleError, "escapes root or is a symlink"):
            read_resources(reference, resource_root=self.destination)

    def test_module_has_no_native_or_lab_execution_dependencies(self):
        path = ROOT / "src" / "civ6_host" / "runtime" / "resource_bundle.py"
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

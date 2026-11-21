"""Offline tests for tools/steam_update_watch.py.

Everything here is synthetic: a fake appmanifest, fake game binaries in a
temporary directory, and a throwaway git repository. No Steam, no GameCore, no
game launch, nothing under C:\\civ6-private.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_PATH = REPO_ROOT / "tools" / "steam_update_watch.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("steam_update_watch", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["steam_update_watch"] = module
    spec.loader.exec_module(module)
    return module


watch = _load_tool()


ACF = """\"AppState\"
{{
	\"appid\"		\"289070\"
	\"Universe\"		\"1\"
	\"name\"		\"Sid Meier's Civilization VI\"
	\"StateFlags\"		\"4\"
	\"buildid\"		\"{buildid}\"
	\"BytesToDownload\"		\"{to_download}\"
	\"BytesDownloaded\"		\"{downloaded}\"
	\"UpdateResult\"		\"{result}\"
}}
"""


def acf_text(*, buildid="26595377", to_download=0, downloaded=0, result=0) -> str:
    return ACF.format(buildid=buildid, to_download=to_download, downloaded=downloaded, result=result)


def sha_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_game(root: Path, contents: dict[str, bytes]) -> Path:
    common = root / watch.COMMON_DIR
    for relative, data in contents.items():
        path = common / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return common


def write_manifest(root: Path, text: str) -> Path:
    path = root / "steamapps" / watch.MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class AppManifestTests(unittest.TestCase):
    def test_parse_reads_the_flat_update_fields(self):
        values = watch.parse_appmanifest(acf_text(buildid="42", to_download=7, result=0))
        self.assertEqual(values["appid"], "289070")
        self.assertEqual(values["buildid"], "42")
        self.assertEqual(watch.manifest_state(values).buildid, "42")
        self.assertEqual(watch.manifest_state(values).bytes_to_download, 7)
        self.assertFalse(watch.manifest_state(values).settled)

    def test_missing_fields_count_as_unsettled(self):
        state = watch.manifest_state({})
        self.assertEqual(state.buildid, "")
        self.assertFalse(state.settled)

    def test_update_finished_detection_stops_after_two_stable_reads(self):
        polls = [
            {"buildid": "26595377", "BytesToDownload": "900", "UpdateResult": "0"},
            {"buildid": "26595377", "BytesToDownload": "0", "UpdateResult": "0"},
            {"buildid": "26595377", "BytesToDownload": "0", "UpdateResult": "0"},
            {"buildid": "26595377", "BytesToDownload": "0", "UpdateResult": "0"},
        ]
        reads = mock.Mock(side_effect=polls)
        sleeps = mock.Mock()
        ticks = iter(range(0, 10_000, 1))
        result = watch.wait_for_update(
            reads,
            interval_seconds=1,
            max_wait_minutes=5,
            clock=lambda: float(next(ticks)),
            sleeper=sleeps,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.polls, 3)
        self.assertEqual(result.state.buildid, "26595377")
        self.assertEqual(reads.call_count, 3)

    def test_a_finished_update_with_a_moving_buildid_keeps_polling(self):
        polls = [
            {"buildid": "1", "BytesToDownload": "0", "UpdateResult": "0"},
            {"buildid": "2", "BytesToDownload": "0", "UpdateResult": "0"},
            {"buildid": "2", "BytesToDownload": "0", "UpdateResult": "0"},
        ]
        ticks = iter(range(0, 10_000))
        result = watch.wait_for_update(
            mock.Mock(side_effect=polls),
            interval_seconds=1,
            max_wait_minutes=5,
            clock=lambda: float(next(ticks)),
            sleeper=lambda _: None,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.polls, 3)
        self.assertEqual(result.state.buildid, "2")

    def test_an_update_that_never_settles_times_out(self):
        reads = mock.Mock(return_value={"buildid": "7", "BytesToDownload": "12", "UpdateResult": "0"})
        ticks = iter(range(0, 10_000))
        result = watch.wait_for_update(
            reads,
            interval_seconds=1,
            max_wait_minutes=0.05,
            clock=lambda: float(next(ticks)),
            sleeper=lambda _: None,
        )
        self.assertFalse(result.ok)
        self.assertIn("still working", result.reason)

    def test_update_result_failure_is_not_settled(self):
        reads = mock.Mock(return_value={"buildid": "9", "BytesToDownload": "0", "UpdateResult": "2"})
        ticks = iter(range(0, 10_000))
        result = watch.wait_for_update(
            reads,
            interval_seconds=1,
            max_wait_minutes=0.05,
            clock=lambda: float(next(ticks)),
            sleeper=lambda _: None,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.state.update_result, 2)


class HashComparisonTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _pins(self, pins: dict[str, tuple[str, int | None]]):
        module = mock.Mock()
        module._PROFILE = mock.Mock(id="xp2-gamecore-current-aaaaaaaa")
        module._CURRENT_CORE_SHA256 = pins["xp2_core"][0]
        module._CURRENT_CORE_SIZE_BYTES = pins["xp2_core"][1]
        module._XP1_PROFILE = mock.Mock(
            id="xp1-gamecore-current-bbbbbbbb",
            image_sha256=pins["xp1_core"][0],
            image_size_bytes=pins["xp1_core"][1],
        )
        module._BASE_PROFILE = mock.Mock(
            id="base-gamecore-current-cccccccc",
            image_sha256=pins["base_core"][0],
            image_size_bytes=pins["base_core"][1],
        )
        return module

    def _install(self, contents=None):
        data = {
            watch.XP2_CORE: b"xp2-image",
            watch.XP1_CORE: b"xp1-image",
            watch.BASE_CORE: b"base-image",
            watch.GAME_EXE: b"exe",
        }
        if contents:
            data.update(contents)
        return write_game(self.root, data)

    def test_a_matching_image_reports_no_changes(self):
        self._install()
        actual = watch.identify_installed(self.root)
        module = self._pins({
            "xp2_core": (actual["xp2_core"].sha256, actual["xp2_core"].size_bytes),
            "xp1_core": (actual["xp1_core"].sha256, actual["xp1_core"].size_bytes),
            "base_core": (actual["base_core"].sha256, actual["base_core"].size_bytes),
        })
        rows = watch.compare(watch.pinned_files(module), actual)
        self.assertFalse(any(row.changed for row in rows))
        report = watch.format_report(None, rows, watch.Admission("xp2-gamecore-current-aaaaaaaa", True, "ok"))
        self.assertIn("No pin changes needed.", report)

    def test_a_replaced_core_is_detected_with_old_and_new_identity(self):
        self._install()
        actual = watch.identify_installed(self.root)
        stale = "0" * 64
        module = self._pins({
            "xp2_core": (stale, 12),
            "xp1_core": (actual["xp1_core"].sha256, actual["xp1_core"].size_bytes),
            "base_core": (actual["base_core"].sha256, actual["base_core"].size_bytes),
        })
        rows = watch.compare(watch.pinned_files(module), actual)
        changed = [row for row in rows if row.changed]
        self.assertEqual([row.name for row in changed], ["xp2_core"])
        self.assertEqual(changed[0].old_sha256, stale)
        self.assertEqual(changed[0].old_size, 12)
        self.assertEqual(changed[0].new_sha256, actual["xp2_core"].sha256)
        self.assertEqual(changed[0].new_size, actual["xp2_core"].size_bytes)

    def test_a_size_only_change_is_detected(self):
        self._install()
        actual = watch.identify_installed(self.root)
        module = self._pins({
            "xp2_core": (actual["xp2_core"].sha256, actual["xp2_core"].size_bytes + 1),
            "xp1_core": (actual["xp1_core"].sha256, actual["xp1_core"].size_bytes),
            "base_core": (actual["base_core"].sha256, actual["base_core"].size_bytes),
        })
        rows = {row.name: row for row in watch.compare(watch.pinned_files(module), actual)}
        self.assertTrue(rows["xp2_core"].changed)

    def test_an_unreadable_binary_is_reported_not_crashing(self):
        write_game(self.root, {watch.XP2_CORE: b"xp2-image"})
        actual = watch.identify_installed(self.root)
        self.assertTrue(actual["xp1_core"].error)
        self.assertTrue(actual["xp1_core"].error.startswith("FileNotFoundError"))

    def test_admission_uses_the_registered_profile(self):
        self._install()
        actual = watch.identify_installed(self.root)
        module = self._pins({
            "xp2_core": (actual["xp2_core"].sha256, actual["xp2_core"].size_bytes),
            "xp1_core": (actual["xp1_core"].sha256, actual["xp1_core"].size_bytes),
            "base_core": (actual["base_core"].sha256, actual["base_core"].size_bytes),
        })
        module.select.return_value = module._PROFILE
        module._PROFILE.image_sha256 = actual["xp2_core"].sha256
        module._PROFILE.image_size_bytes = actual["xp2_core"].size_bytes
        result = watch.admission(actual, module)
        self.assertTrue(result.admitted)
        self.assertEqual(result.profile_id, "xp2-gamecore-current-aaaaaaaa")

    def test_admission_refuses_a_different_image(self):
        self._install()
        actual = watch.identify_installed(self.root)
        module = self._pins({
            "xp2_core": ("f" * 64, 1),
            "xp1_core": (actual["xp1_core"].sha256, 1),
            "base_core": (actual["base_core"].sha256, 1),
        })
        module.select.return_value = module._PROFILE
        module._PROFILE.image_sha256 = "f" * 64
        module._PROFILE.image_size_bytes = 1
        result = watch.admission(actual, module)
        self.assertFalse(result.admitted)
        self.assertIn("not the pinned image", result.detail)


class PlanEditTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "src" / "civ6_host" / "runtime").mkdir(parents=True)
        (self.root / "src" / "civ6_host" / "runtime" / "execution_images.py").write_text(
            "_CURRENT_CORE_SHA256 = '" + "a" * 64 + "'\n"
            "_CURRENT_CORE_SIZE_BYTES = 100\n"
            "PROFILE = 'xp2-gamecore-current-aaaaaaaa'\n",
            encoding="utf-8",
        )
        evidence = self.root / "src" / "civ6_host" / "runtime" / "xp2_dedications.py"
        evidence.write_text("PROOF = '" + "a" * 64 + "'\n", encoding="utf-8")

    def test_plan_edits_skips_captured_evidence_modules(self):
        edits = watch.plan_edits(
            self.root,
            old_sha256="a" * 64,
            new_sha256="b" * 64,
            old_size=100,
            new_size=200,
            old_profile_id="xp2-gamecore-current-aaaaaaaa",
            new_profile_id="xp2-gamecore-current-bbbbbbbb",
        )
        by_file = {(edit.relative, edit.old): edit for edit in edits}
        images = "src/civ6_host/runtime/execution_images.py"
        self.assertIn((images, "a" * 64), by_file)
        self.assertIn((images, "100"), by_file)
        self.assertIn((images, "xp2-gamecore-current-aaaaaaaa"), by_file)
        self.assertNotIn(("src/civ6_host/runtime/xp2_dedications.py", "a" * 64), by_file)

    def test_apply_edits_preserves_crlf_line_endings(self):
        target = self.root / "src" / "civ6_host" / "runtime" / "execution_images.py"
        target.write_bytes(
            b"_CURRENT_CORE_SHA256 = '" + b"a" * 64 + b"'\r\n_CURRENT_CORE_SIZE_BYTES = 100\r\n"
        )
        edits = watch.plan_edits(
            self.root,
            old_sha256="a" * 64,
            new_sha256="b" * 64,
            old_size=100,
            new_size=200,
            old_profile_id="",
            new_profile_id="",
        )
        applied = watch.apply_edits(self.root, edits)
        self.assertTrue(applied)
        data = target.read_bytes()
        self.assertIn(b"b" * 64, data)
        self.assertIn(b"200", data)
        self.assertEqual(data.count(b"\r\n"), 2)


GIT = shutil.which("git")


@unittest.skipUnless(GIT, "git is required for the --apply test")
class ApplyBranchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_pin.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        (self.root / "src" / "civ6_host" / "runtime").mkdir(parents=True)
        self.pin_file = self.root / "src" / "civ6_host" / "runtime" / "execution_images.py"
        self.pin_file.write_text(
            "_CURRENT_CORE_SHA256 = '" + "a" * 64 + "'\n"
            "_CURRENT_CORE_SIZE_BYTES = 100\n"
            "PROFILE = 'xp2-gamecore-current-aaaaaaaa'\n",
            encoding="utf-8",
        )
        self._git("init")
        self._git("config", "user.email", "tester@example.invalid")
        self._git("config", "user.name", "Tester")
        self._git("config", "commit.gpgsign", "false")
        self._git("add", "-A")
        self._git("commit", "-m", "base")

    def _git(self, *args):
        completed = subprocess.run(
            (GIT, *args), cwd=str(self.root), capture_output=True, text=True
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def test_apply_creates_the_branch_and_commits_with_the_trailer(self):
        result = watch.apply_reanchor(
            self.root,
            old_sha256="a" * 64,
            new_sha256="b" * 64,
            old_size=100,
            new_size=200,
            old_profile_id="xp2-gamecore-current-aaaaaaaa",
            new_profile_id="xp2-gamecore-current-bbbbbbbb",
            tests=["tests/test_pin.py"],
            run_tests=lambda repo, files: (0, "1 passed"),
        )
        self.assertTrue(result.committed, result.detail)
        self.assertEqual(result.branch, "feat/reanchor-xp2-bbbbbbbb")
        self.assertIn("feat/reanchor-xp2-bbbbbbbb", self._git("branch", "--show-current"))
        text = self.pin_file.read_text(encoding="utf-8")
        self.assertIn("b" * 64, text)
        self.assertIn("200", text)
        self.assertIn("xp2-gamecore-current-bbbbbbbb", text)
        message = self._git("log", "-1", "--pretty=%B")
        self.assertIn("Generated by Mistral Vibe.", message)
        self.assertIn("Co-Authored-By: Mistral Vibe <vibe@mistral.ai>", message)
        self.assertIn("re-derived", message)

    def test_failing_tests_leave_the_edits_uncommitted(self):
        head = self._git("rev-parse", "HEAD").strip()
        result = watch.apply_reanchor(
            self.root,
            old_sha256="a" * 64,
            new_sha256="b" * 64,
            old_size=100,
            new_size=200,
            old_profile_id="xp2-gamecore-current-aaaaaaaa",
            new_profile_id="xp2-gamecore-current-bbbbbbbb",
            tests=["tests/test_pin.py"],
            run_tests=lambda repo, files: (1, "1 failed"),
        )
        self.assertFalse(result.committed)
        self.assertIn("offline tests failed", result.detail)
        self.assertEqual(self._git("rev-parse", "HEAD").strip(), head)

    def test_uncommitted_work_blocks_apply(self):
        (self.root / "scratch.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            watch.apply_reanchor(
                self.root,
                old_sha256="a" * 64,
                new_sha256="b" * 64,
                old_size=100,
                new_size=200,
                old_profile_id="xp2-gamecore-current-aaaaaaaa",
                new_profile_id="xp2-gamecore-current-bbbbbbbb",
                run_tests=lambda repo, files: (0, ""),
            )


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_once_reports_the_pin_mapping_for_a_replaced_image(self):
        write_manifest(self.root, acf_text())
        write_game(self.root, {
            watch.XP2_CORE: b"new-xp2",
            watch.XP1_CORE: b"xp1",
            watch.BASE_CORE: b"base",
            watch.GAME_EXE: b"exe",
        })
        module = mock.Mock()
        module._PROFILE = mock.Mock(id="xp2-gamecore-current-aaaaaaaa")
        module._CURRENT_CORE_SHA256 = "0" * 64
        module._CURRENT_CORE_SIZE_BYTES = 1
        module._XP1_PROFILE = mock.Mock(id="xp1", image_sha256="", image_size_bytes=None)
        module._BASE_PROFILE = mock.Mock(id="base", image_sha256="", image_size_bytes=None)
        module.select.return_value = module._PROFILE
        module._PROFILE.image_sha256 = "0" * 64
        module._PROFILE.image_size_bytes = 1
        buffer = []
        with mock.patch.object(watch, "_import_execution_images", return_value=module), \
                mock.patch.object(watch, "plan_edits", return_value=[]), \
                mock.patch("builtins.print", lambda *parts, **kw: buffer.append(" ".join(str(p) for p in parts))):
            code = watch.main([
                "--once",
                "--steam-root", str(self.root),
                "--repo-root", str(self.root),
            ])
        output = "\n".join(buffer)
        self.assertEqual(code, 1)
        self.assertIn("xp2_core", output)
        self.assertIn(sha_of(b"new-xp2")[:12], output)
        self.assertIn("does NOT admit", output)
        self.assertIn("Dry run only", output)


if __name__ == "__main__":
    unittest.main()

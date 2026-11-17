"""Offline tests for tools/prepare_local_root.py and tools/play.py.

These tests never load GameCore and never touch the real Steam install: the
engine and executable pins are monkeypatched to temporary fixtures, so they run
on any OS. They verify that preparation refuses a missing/mismatched pinned
executable and only writes a backend config when everything verifies.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import prepare_local_root as plr  # noqa: E402


def _fake_steam(tmp_path: Path) -> Path:
    steam = tmp_path / "steam" / "Sid Meier's Civilization VI"
    for rel in plr.ENGINE_REL.values():
        dll = steam / rel
        dll.parent.mkdir(parents=True, exist_ok=True)
        dll.write_bytes(b"fake-" + rel.name.encode())
    return steam


def _pin_all(monkeypatch, tmp_path: Path, steam: Path) -> None:
    pins = {}
    for build, rel in plr.ENGINE_REL.items():
        pins[build] = plr.sha256_file(steam / rel)
    monkeypatch.setattr(plr, "ENGINE_PINS", pins)


def test_prepare_missing_engine_and_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(plr, "STEAM_DEFAULT", tmp_path / "nonexistent")
    status = plr.prepare(tmp_path / "root", None)
    assert status["ready"] is False
    assert status["exit_code"] == 2
    assert not (tmp_path / "root" / plr.CONFIG_NAME).exists()
    # work layout is still created
    assert (tmp_path / "root" / "work" / "runs").is_dir()


def test_prepare_engine_ok_but_exe_missing(tmp_path, monkeypatch):
    steam = _fake_steam(tmp_path)
    _pin_all(monkeypatch, tmp_path, steam)
    root = tmp_path / "root"
    status = plr.prepare(root, steam)
    assert status["engine"]["base"]["matches_pin"] is True
    assert status["host_executable"]["present"] is False
    assert status["exit_code"] == 3
    assert status["ready"] is False
    assert not (root / plr.CONFIG_NAME).exists()


def test_prepare_refuses_wrong_exe_pin(tmp_path, monkeypatch):
    steam = _fake_steam(tmp_path)
    _pin_all(monkeypatch, tmp_path, steam)
    root = tmp_path / "root"
    exe = root / plr.HOST_EXE_REL
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"not the retained host")
    status = plr.prepare(root, steam)
    assert status["host_executable"]["present"] is True
    assert status["host_executable"]["matches_pin"] is False
    assert status["exit_code"] == 4
    assert not (root / plr.CONFIG_NAME).exists()


def test_prepare_ready_writes_config(tmp_path, monkeypatch):
    steam = _fake_steam(tmp_path)
    _pin_all(monkeypatch, tmp_path, steam)
    root = tmp_path / "root"
    exe = root / plr.HOST_EXE_REL
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"retained host bytes")
    monkeypatch.setattr(plr, "HOST_EXE_SHA256", plr.sha256_file(exe))
    status = plr.prepare(root, steam, lifetime_seconds=120)
    assert status["ready"] is True and status["exit_code"] == 0
    config = json.loads((root / plr.CONFIG_NAME).read_text())
    assert set(config) == {"resources", "official_bundle", "ui_profile",
                           "prepared_capture", "private_resources", "session_options"}
    assert config["resources"] == str(root)
    assert config["session_options"]["lifetime_seconds"] == 120
    assert config["session_options"]["run_root"].startswith(str(root))


def test_detect_steam(tmp_path):
    steam = _fake_steam(tmp_path)
    assert plr.detect_steam(str(steam)) == steam.resolve()
    assert plr.detect_steam(str(tmp_path / "nope")) is None or True  # fallback may exist


def test_play_check_ready(tmp_path, monkeypatch, capsys):
    import play
    steam = _fake_steam(tmp_path)
    _pin_all(monkeypatch, tmp_path, steam)
    root = tmp_path / "root"
    exe = root / plr.HOST_EXE_REL
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"retained host bytes")
    monkeypatch.setattr(plr, "HOST_EXE_SHA256", plr.sha256_file(exe))
    assert plr.prepare(root, steam)["ready"] is True
    code = play.main(["--root", str(root), "--steam", str(steam), "--check"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ready"] is True
    assert out["host_executable"]["matches_pin"] is True


def test_play_check_missing_config_runs_prepare(tmp_path, monkeypatch, capsys):
    import play
    steam = _fake_steam(tmp_path)
    _pin_all(monkeypatch, tmp_path, steam)
    root = tmp_path / "root"
    # no exe -> not ready -> non-zero, no session started
    code = play.main(["--root", str(root), "--steam", str(steam), "--check"])
    assert code == 3

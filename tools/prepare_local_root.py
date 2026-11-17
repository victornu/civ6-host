#!/usr/bin/env python3
"""Prepare a local private resource root for real native Civ6 sessions.

Creates the expected ``work/`` layout under ``--root``, detects and verifies
the Steam installation's GameCore binaries against the host's SHA-256 pins,
and checks the retained native host executable
(``work/native-script-services-host41/civ6rl-native-python.exe``).

The executable pin is never bypassed: a present executable whose SHA-256
differs from the retained reference is refused. When it is absent, this tool
reports exactly what is missing and how to obtain it (reproducible build with
the pinned toolchain via ``tools/build_native_host.py``, or your own retained
build copied locally from the machine that produced it).

On success it writes ``<root>/backend-config.json`` ready for
``tools/play.py`` / ``examples/basic_client.py``.

Exit codes: 0 ready, 2 engine missing/mismatched, 3 host executable missing,
4 host executable pin mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STEAM_DEFAULT = Path(
    "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI")
BASE_DLL_REL = Path("Base/Binaries/Win64Steam/GameCore_Base_FinalRelease.dll")
XP1_DLL_REL = Path("DLC/Expansion1/Binaries/Win64/GameCore_XP1_FinalRelease.dll")
XP2_DLL_REL = Path("DLC/Expansion2/Binaries/Win64/GameCore_XP2_FinalRelease.dll")

# Pins from civ6_host.runtime.saved_load_profiles / stdout_transport_profiles.
ENGINE_PINS = {
    "base": "d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3",
    "xp1": "259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83",
    "xp2": "324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c",
}
ENGINE_REL = {"base": BASE_DLL_REL, "xp1": XP1_DLL_REL, "xp2": XP2_DLL_REL}

HOST_EXE_REL = Path("work/native-script-services-host41/civ6rl-native-python.exe")
HOST_EXE_SHA256 = ("2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334")

CONFIG_NAME = "backend-config.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detect_steam(explicit: str | None) -> Path | None:
    candidates = [Path(explicit)] if explicit else []
    candidates.append(Path(os.environ.get("CIV6_STEAM_INSTALL", "")) if os.environ.get("CIV6_STEAM_INSTALL") else None)
    candidates.append(STEAM_DEFAULT)
    for candidate in candidates:
        if candidate and (candidate / BASE_DLL_REL).is_file():
            return candidate.resolve()
    return None


def verify_engine(steam: Path) -> dict:
    report = {}
    for build, rel in ENGINE_REL.items():
        dll = steam / rel
        if not dll.is_file():
            report[build] = {"present": False}
            continue
        digest = sha256_file(dll)
        report[build] = {"present": True, "sha256": digest, "matches_pin": digest == ENGINE_PINS[build]}
    return report


def prepare(root: Path, steam: Path | None, *, lifetime_seconds: int = 180) -> dict:
    root = root.resolve()
    if not root.is_absolute():
        raise ValueError("--root must be an absolute path")
    if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= 180:
        raise ValueError("lifetime_seconds must be an integer in [1, 180]")
    host_dir = root / HOST_EXE_REL.parent
    runs_dir = root / "work" / "runs"
    host_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    engine = verify_engine(steam) if steam is not None else None
    engine_ok = engine is not None and engine["base"]["present"] and engine["base"]["matches_pin"]

    exe = root / HOST_EXE_REL
    if not exe.is_file():
        host = {"present": False, "expected_sha256": HOST_EXE_SHA256,
                "note": ("Build it reproducibly with: python tools/build_native_host.py "
                         "--output-dir <root>/work/native-script-services-host41 "
                         "(requires the pinned MSVC 14.33.31629, WinSDK 10.0.19041.0, "
                         "Python 3.12), or copy your retained build from the machine "
                         "that produced it. The pin is verified, never bypassed.")}
        ready = False
        exit_code = 2 if not engine_ok else 3
    else:
        digest = sha256_file(exe)
        if digest != HOST_EXE_SHA256:
            host = {"present": True, "sha256": digest, "expected_sha256": HOST_EXE_SHA256,
                    "matches_pin": False}
            ready = False
            exit_code = 4
        else:
            host = {"present": True, "sha256": digest, "matches_pin": True}
            ready = engine_ok
            exit_code = 0 if ready else 2

    status = {"root": str(root), "steam": str(steam) if steam else None,
              "engine": engine, "host_executable": host, "ready": ready,
              "exit_code": exit_code}
    if ready:
        config = {
            "resources": str(root),
            "official_bundle": None,
            "ui_profile": None,
            "prepared_capture": None,
            "private_resources": None,
            "session_options": {"run_root": str(runs_dir / "play"),
                                "lifetime_seconds": lifetime_seconds},
        }
        (root / CONFIG_NAME).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        status["config"] = str(root / CONFIG_NAME)
    return status


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True,
                        help="local private resource root to create/verify (e.g. C:\\civ6-private)")
    parser.add_argument("--steam", default=None,
                        help="Civilization VI install dir (default: standard Steam path, CIV6_STEAM_INSTALL override)")
    parser.add_argument("--lifetime", type=int, default=180,
                        help="session lifetime seconds written into the config (1..180)")
    args = parser.parse_args(argv)
    steam = detect_steam(args.steam)
    status = prepare(args.root, steam, lifetime_seconds=args.lifetime)
    print(json.dumps(status, indent=2))
    return status["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())

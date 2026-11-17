#!/usr/bin/env python3
"""One-command play CLI over a prepared local resource root.

    python tools/prepare_local_root.py --root C:\\civ6-private
    python tools/play.py --root C:\\civ6-private            # interactive JSON-lines
    python tools/play.py --root C:\\civ6-private --check    # readiness only

Commands are JSON lines on stdin, one JSON response per line on stdout:

    {"op": "reset"}
    {"op": "observe"}
    {"op": "act", "decision_id": "...", "candidate_id": "..."[, "parameters": {...}]}
    {"op": "close"}

The real backend needs Windows, the verified Steam GameCore binaries and the
pinned retained host executable under ``<root>/work/native-script-services-host41/``
(see tools/prepare_local_root.py). Nothing is copied or decompiled; the host
verifies every pin in place before loading anything native.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "tools"))

from prepare_local_root import CONFIG_NAME, detect_steam, prepare  # noqa: E402
import basic_client  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True,
                        help="prepared local private resource root")
    parser.add_argument("--config", type=Path, default=None,
                        help="backend config (default: <root>/backend-config.json)")
    parser.add_argument("--mode", choices=("hotseat", "lan"), default="hotseat")
    parser.add_argument("--steam", default=None, help="Civ6 install dir override")
    parser.add_argument("--check", action="store_true",
                        help="only verify readiness; do not start a session")
    parser.add_argument("--backend-script", default=None, metavar="MODULE:CLASS",
                        help="use a caller-supplied backend class instead of the native backend "
                             "(e.g. civ6rl.env.scripted:ScriptedHotseatBackend for a clearly-labeled "
                             "SYNTHETIC dry run; no native code is loaded)")
    parser.add_argument("--backend-opts", default=None,
                        help="JSON object of keyword args for --backend-script")
    args = parser.parse_args(argv)

    if args.backend_script:
        import importlib
        module, _, cls = args.backend_script.partition(":")
        if not module or not cls:
            print("--backend-script must be MODULE:CLASS", file=sys.stderr)
            return 2
        backend_cls = getattr(importlib.import_module(module), cls)
        opts = json.loads(args.backend_opts) if args.backend_opts else {}
        if type(opts) is not dict:
            print("--backend-opts must be a JSON object", file=sys.stderr)
            return 2
        backend = backend_cls(**opts)
        if args.check:
            print(json.dumps({"mode": "scripted-synthetic", "backend": args.backend_script,
                              "synthetic": True, "ready": True}, indent=2))
            return 0
        from civ6_host import HotseatClient
        client = HotseatClient(backend)
        try:
            return basic_client.serve(client, args.mode, sys.stdin)
        finally:
            client.abort()

    root = args.root.resolve()
    config_path = args.config or (root / CONFIG_NAME)
    if not config_path.is_file():
        steam = detect_steam(args.steam)
        status = prepare(root, steam)
        print(json.dumps(status, indent=2), file=sys.stderr)
        if not status["ready"]:
            return status["exit_code"]
        config_path = root / CONFIG_NAME

    if args.check:
        config = basic_client.load_backend_config(config_path)
        steam = detect_steam(args.steam)
        from prepare_local_root import verify_engine, HOST_EXE_REL, HOST_EXE_SHA256, sha256_file
        exe = root / HOST_EXE_REL
        status = {"config": str(config_path), "resources": config["resources"],
                  "steam": str(steam) if steam else None,
                  "engine": verify_engine(steam) if steam else None,
                  "host_executable": ({"present": True, "matches_pin": sha256_file(exe) == HOST_EXE_SHA256}
                                      if exe.is_file() else {"present": False}),
                  "ready": True}
        print(json.dumps(status, indent=2))
        return 0

    config = basic_client.load_backend_config(config_path)
    backend = basic_client.build_backend(config, args.mode)
    client = basic_client.build_client(backend, args.mode)
    try:
        return basic_client.serve(client, args.mode, sys.stdin)
    finally:
        client.abort()


if __name__ == "__main__":
    raise SystemExit(main())

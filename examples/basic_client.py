"""Minimal working example for the civ6-host client API.

This example is runnable from a source checkout or an installed
``civ6-host-client`` wheel: the imports below only need the pure-stdlib
client package. Executing a session additionally requires the separate
``civ6-host-runtime`` wheel, Windows, and a qualified private resource
directory (see docs/backend.md and docs/runtime-paths.md). This example
never prepares a world, chooses an action, or fabricates a backend: it
reads caller-supplied commands and forwards them to the real client.

Protocol
--------
Commands are JSON lines on stdin; responses are one JSON line each on
stdout. Every line is an object with an ``op`` field:

    {"op": "reset"}
    {"op": "observe"}                                   # hotseat; LAN adds "player_id"
    {"op": "act", "decision_id": "...", "candidate_id": "...",
     "parameters": {...}}                               # "parameters" optional
    {"op": "close"}

For ``--mode lan`` the actor-taking operations also require
``"player_id"`` (observe/act/close), e.g. ``{"op": "observe", "player_id": 0}``.

Successful replies are ``{"ok": true, "op": ..., "response": {...}}`` where
``response`` is the detached public view returned by the client. Failures
are ``{"ok": false, "op": ..., "error": {"type": ..., "message": ...}}``.
A protocol failure makes the session unusable until reset: this driver
then aborts the backend and exits non-zero instead of retrying, because
the native action may already have been applied.

Backend configuration
---------------------
``--config`` points to a JSON file with exactly these keys (see
``examples/local_session.py`` for the full launcher):

    {
      "resources":         "/abs/path/to/private/resource/root",
      "official_bundle":   "/abs/path/to/official_bundle",
      "ui_profile":        "/abs/path/to/ui_profile",     # hotseat only; null for LAN
      "prepared_capture":  "/abs/path/to/prepared_capture" | null,
      "private_resources": "/abs/path/to/relocated/resources" | null,
      "session_options":   {"input_profile": "lan", ...}   # forwarded as **options
    }

``build_backend()`` below shows how that dict maps onto
``LocalHotseatBackend`` / ``NetworkBackend``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# The client package is pure stdlib and imports anywhere. Allow running
# straight from a source checkout without installing the wheel first.
try:
    from civ6_host import HotseatClient, InformationUnavailable, ProtocolError, SessionClient
except ImportError:  # pragma: no cover - source-checkout convenience
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from civ6_host import HotseatClient, InformationUnavailable, ProtocolError, SessionClient


# Keys every backend configuration file must contain. `session_options` is
# forwarded unchanged as native session **options and must not repeat any
# of the resource keys above.
REQUIRED_CONFIG_KEYS = frozenset(
    {"resources", "official_bundle", "ui_profile", "prepared_capture",
     "private_resources", "session_options"}
)


def load_backend_config(path: Path) -> dict:
    """Read and structurally validate the JSON backend configuration."""
    config = json.loads(path.read_text(encoding="utf-8"))
    if type(config) is not dict or set(config) != REQUIRED_CONFIG_KEYS:
        raise ValueError(
            "config must contain exactly: " + ", ".join(sorted(REQUIRED_CONFIG_KEYS))
        )
    if type(config["session_options"]) is not dict:
        raise ValueError("session_options must be an object")
    if set(config["session_options"]) & (REQUIRED_CONFIG_KEYS - {"session_options"}):
        raise ValueError("session_options cannot override resource identities")
    return config


def build_backend(config: dict, mode: str = "hotseat"):
    """Construct the backend named by ``mode`` from a validated config dict.

    The runtime import is deferred so that this module stays importable
    without the runtime wheel or a configured resource root. Constructing
    the backend itself requires Windows and the private resources; it sets
    CIV6_HOST_RESOURCE_ROOT from ``config["resources"]`` (see
    docs/runtime-paths.md).
    """
    from civ6_host.runtime.backend import LocalHotseatBackend, NetworkBackend

    backend_config = {k: v for k, v in config.items() if k != "session_options"}
    options = config["session_options"]
    if mode == "lan":
        if backend_config.pop("ui_profile") is not None:
            raise ValueError("LAN mode must not reuse a hotseat ui_profile")
        return NetworkBackend(**backend_config, **options)
    if mode == "hotseat":
        return LocalHotseatBackend(**backend_config, **options)
    raise ValueError("mode must be 'hotseat' or 'lan'")


def build_client(backend, mode: str = "hotseat"):
    """Wrap a backend in the matching public client."""
    if mode == "lan":
        return SessionClient(backend)
    if mode == "hotseat":
        return HotseatClient(backend)
    raise ValueError("mode must be 'hotseat' or 'lan'")


def run_command(client, mode: str, command: dict) -> dict:
    """Dispatch one JSON-line command and return the client's response.

    This is the whole command protocol: ``op`` selects the client method,
    everything else is forwarded explicitly. The client validates the
    host reply and returns a detached public view; nothing is retried.
    """
    if type(command) is not dict:
        raise ValueError("command must be a JSON object")
    op = command.get("op")
    extra = set(command) - {"op"}

    if mode == "lan":
        # LAN commands are per-actor; reset takes no actor.
        if op == "reset" and extra == set():
            return client.reset()
        if op == "close" and extra <= {"player_id"}:
            return client.close(command.get("player_id"))
        if op in ("observe", "poll") and extra == {"player_id"}:
            return getattr(client, op)(command["player_id"])
        if op == "act" and extra in (
            {"player_id", "decision_id", "candidate_id"},
            {"player_id", "decision_id", "candidate_id", "parameters"},
        ):
            return client.act(
                command["player_id"],
                command["decision_id"],
                command["candidate_id"],
                command.get("parameters"),
            )
        raise ValueError(
            "LAN ops: reset; close[player_id]; observe/poll with player_id; "
            "act with player_id, decision_id, candidate_id[, parameters]"
        )

    # Hotseat commands act on the local player.
    if op in ("reset", "observe", "close") and extra == set():
        return getattr(client, op)()
    if op == "player_view" and extra == {"player_id"}:
        return client.player_view(command["player_id"])
    if op == "act" and extra in (
        {"decision_id", "candidate_id"},
        {"decision_id", "candidate_id", "parameters"},
    ):
        return client.act(
            command["decision_id"],
            command["candidate_id"],
            parameters=command.get("parameters"),
        )
    raise ValueError(
        "hotseat ops: reset, observe, close; player_view with player_id; "
        "act with decision_id, candidate_id[, parameters]"
    )


def _error_line(op, exc: BaseException) -> dict:
    return {"ok": False, "op": op, "error": {"type": type(exc).__name__, "message": str(exc)}}


def serve(client, mode: str, lines) -> int:
    """Read JSON-line commands and print one JSON response per line."""
    status = 0
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        op = None
        try:
            command = json.loads(raw)
            op = command.get("op") if type(command) is dict else None
            response = run_command(client, mode, command)
        except ProtocolError as exc:
            # The exchange is uncertain: the native action may already have
            # been applied, so never retry. Abort and stop the driver.
            print(json.dumps(_error_line(op, exc), ensure_ascii=False,
                             separators=(",", ":")), flush=True)
            client.abort()
            return 2
        except (ValueError, RuntimeError, PermissionError, InformationUnavailable) as exc:
            # Local misuse (stale catalogue, no live session, bad op, ...):
            # report and keep serving; the session may still be usable.
            print(json.dumps(_error_line(op, exc), ensure_ascii=False,
                             separators=(",", ":")), flush=True)
            status = 1
            continue
        print(json.dumps({"ok": True, "op": op, "response": response},
                         ensure_ascii=False, separators=(",", ":")), flush=True)
        if op == "close":
            return status
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True,
                        help="JSON backend configuration (see module docstring)")
    parser.add_argument("--mode", choices=("hotseat", "lan"), default="hotseat")
    args = parser.parse_args()

    config = load_backend_config(args.config)
    backend = build_backend(config, args.mode)
    client = build_client(backend, args.mode)
    try:
        return serve(client, args.mode, sys.stdin)
    finally:
        # close() on an already-closed client is a no-op; abort() is always
        # safe and releases the native child if anything is still live.
        client.abort()


if __name__ == "__main__":
    raise SystemExit(main())

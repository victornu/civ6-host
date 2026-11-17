# Playing a real Civ6 game through the host

This runs the **official Windows GameCore in place** from your Steam install,
driven by the public client over JSON lines. Nothing is copied, decompiled or
published: every binary is SHA-256-verified in place against the retained pins
before anything native is loaded.

## What you need

1. **Civ6 installed via Steam** (Base, and optionally the XP1/XP2 DLCs). The
   host pins the exact GameCore builds:
   - `Base\Binaries\Win64Steam\GameCore_Base_FinalRelease.dll`
     SHA-256 `d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3`
   - `DLC\Expansion1\Binaries\Win64\GameCore_XP1_FinalRelease.dll`
     SHA-256 `259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83`
   - `DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll`
     SHA-256 `324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c`
2. **The retained native host executable**
   `work/native-script-services-host41/civ6rl-native-python.exe`
   (116,224 bytes, SHA-256
   `2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334`)
   under your local private root. Obtain it by either:
   - building it reproducibly (see below), or
   - copying **your own** retained build from the machine that produced it.
   A present-but-different executable is refused; the pin is never bypassed.
3. **Python 3.12** to run the client (the embedded host interpreter is 3.12;
   the session sets `CIV6RL_PYTHON_HOME` from the launching interpreter).

## Reproducible build of the host executable

Requires Windows x64, admin for the toolchain, MSVC `14.33.31629`
(VS 2022 17.3.6 Build Tools component `VC.Tools.x86.x64`), Windows SDK
`10.0.19041.0` (component `Windows10SDK.19041`) and Python 3.12 with headers:

```powershell
winget install --id Microsoft.VisualStudio.2022.BuildTools --version 17.3.6
# add components VC.Tools.x86.x64 and Windows10SDK.19041 via vs_installer modify
python tools/build_native_host.py --output-dir C:\civ6-private\work\native-script-services-host41
```

Run the builder with the Python 3.12 interpreter. The builder canonicalizes
only the declared PE timestamp fields and then requires the whole file to
match the retained SHA-256; any other bytes are refused.

## Run

With GNU make (e.g. GnuWin32 on Windows: `"/c/Program Files (x86)/GnuWin32/bin/make.exe"`):

```powershell
make -C civ6-host setup          # pinned toolchain: Python 3.12, VS 2022 17.3.6, WinSDK 19041
make -C civ6-host build-host     # compile civ6rl-native-python.exe (byte-pin enforced by builder)
make -C civ6-host install-host   # place exe+build.json+inputs under the root
make -C civ6-host prepare        # verify engine+exe pins, write backend-config.json
make -C civ6-host check          # readiness report
make -C civ6-host play           # play: JSON lines on stdin
make -C civ6-host test           # offline test suites (any OS)
```

Override the private root / Steam path with `ROOT=... STEAM=...`.
Without make, the same steps are plain commands:

```powershell
# 1. prepare + verify the local root (engine pins, host exe pin), writes backend-config.json
python tools/prepare_local_root.py --root C:\civ6-private

# 2. play: JSON lines on stdin, one JSON response per line on stdout
python tools/play.py --root C:\civ6-private
```

Commands (hotseat):

```json
{"op": "reset"}
{"op": "observe"}
{"op": "act", "decision_id": "<from view>", "candidate_id": "<from view>"}
{"op": "close"}
```

Each response is `{"ok": true, "op": ..., "response": <detached public view>}`
where the view contains `observation`, `decisions.candidates` (the legal menu
with `decision_id`), and `outcome`. Pick a `candidate_id` from the current
view and send it back as the next `act`. A protocol failure aborts the session
(no silent retries — the native action may already have been applied).

`tools/play.py --check` prints the readiness report without starting a session.
`examples/basic_client.py --config C:\civ6-private\backend-config.json` is the
equivalent raw driver. `--mode lan` uses `SessionClient` with per-player
commands and still requires the retained captured bundle (not the fresh-game
path).

## Scope limits (unchanged)

Fresh single-player hotseat is the qualified path here. Simultaneous
two-human play, full action coverage, all profiles and complete information
groups remain unqualified (see README). The scripted synthetic backend in
`civ6rl.env.scripted` works everywhere for dry runs but is not a native game.

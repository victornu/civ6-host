# Native executable build

`native/` contains the 19 original project source snapshots that produced the retained Base host executable. The XP1 profile in `native/profiles/xp1/` adds two variant source files and references 18 shared files, without duplicating them. These sources implement executable-owned platform exports and embed Python. The official GameCore, game data and proprietary headers are not included. Each source manifest records hashes and the original build provenance.

Base remains the default and retains its existing Base/hotseat qualification and scoped serial native-job scheduling. XP1 reproduces the existing native Lua API binding prototype. Its additional export lets the official XP1 engine register its Lua callbacks; it does not reproduce those gameplay callbacks in host code. Building this variant does not establish complete extension or simultaneous-multiplayer support.

## Build locally

Prerequisites for this retained reproducible profile:

- Windows x64, Python 3.12 with its development headers/import library.
- Installed MSVC `14.33.31629` and Windows SDK `10.0.19041.0`.
- A new empty output directory outside `native/`.

From the repository root:

```powershell
python tools/build_native_host.py --output-dir .local-build/native-host
```

To reproduce the separate XP1 executable:

```powershell
python tools/build_native_host.py --profile xp1 --output-dir .local-build/native-host-xp1
```

The Rise and Fall saved-session route uses the separate `xp1-ui` build.
Run the builder from this source checkout with `--profile xp1-ui` and a
new `work/native-host-xp1-ui-build01` directory under the private resource
root. Keep the executable, `build.json`, and `inputs/` in their original
locations. The saved-session verifier accepts the rebuilt 121,344-byte
executable with SHA-256
`949949ddca0ec61a55e3368bf062f46fcdb4b2f7dc52f25a49acc4758664224f`
and its 21 exact staged source files without reading the original source
checkout. The historical build remains supported. With the private official
capture and runtime proofs supplied separately, the locally rebuilt host
loaded the retained Rise and Fall LAN save, returned its initial observation
to the Python client, and closed cleanly. See [private resource setup](resource-bundle.md).

To build the executable used by the qualified Gathering Storm LAN route:

```powershell
python tools/build_native_host.py --profile xp2-ui --output-dir .local-build/native-host-xp2-ui
Get-FileHash .local-build/native-host-xp2-ui/civ6rl-native-python.exe -Algorithm SHA256
```

With the retained toolchain, this built the same 127,488 executable bytes as
the LAN qualification, with SHA-256
`a3d977a4aa09d3f4f88a393f59e32f5a34d12d79db48606c39c4b9e09994f799`.
To supply this build to the Gathering Storm saved-session runtime, build
directly into `work/native-host-xp2-ui-build01` below the private resource root.
Keep `build.json`, `inputs/` and the executable in place. The local receipt
uses absolute paths. The runtime checks the exact executable digest, the source
manifest identity and the complete set of 30 staged source hashes. It pins the
local receipt and staged files for parent and worker. Existing qualified
historical receipts remain supported. Other capture and runtime proof resources
are still required for a LAN session.

The builder stages the files named by the selected manifest into one private
compile directory. `path` identifies a reviewed source in the repository;
optional `build_path` preserves its compiler include name. Shared includes are
checked as part of the complete dependency closure. Paths outside the source or
staging boundary, duplicate destinations and unlisted includes are refused.

The builder verifies the entire transitive local include closure, snapshots it, and invokes the compiler in a hidden process bounded to 60 seconds and 1 GiB per process. It preserves the raw compiler executable, compiler log and build receipt. It does not load GameCore or launch the game.

`--profile xp2-mutable-map` composes the existing XP2 API binder with the explicit
mutable GameEvents bridge. Its manifest aliases the unchanged scalar dispatcher
and adds two original project includes. This is a source build with its own
identity; it does not inherit saved-game compatibility from a reference profile.
The locally qualified provider/HKS ABI group is described in [backend setup](backend.md).

`--profile xp2-script-contexts` adds scoped listener-state checks to that source
composition. It retains the Call/TestAll and scalar converters under explicit
include aliases; the map converter changes only its state/protection guards.
Its build identity and ABI qualification are separate from the preceding build.
Neither profile admits an XP2 saved game by its source manifest alone.

## Exact compatibility, including provenance

The existing adapters identify the qualified executable by SHA-256. A newly linked PE records a new date even when its code and data are identical. The builder normalizes only the timestamp fields identified structurally in the COFF header, export directory and debug directory. Their original and canonical values are recorded. It then requires the **entire executable** to match the retained SHA-256:

`2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334`

The XP1 profile independently requires its retained executable SHA-256:

`962ff8ca95ffed4fbaf40f0a0c37c47dd7d9c27b0bfc25beb4ae5dc76a2cfd0c`

No instruction, pointer, import, export address or other data is patched to force compatibility. Any remaining difference is refused, and raw output remains available for diagnosis. The canonical PE date is not a claim about when the new build happened: the build receipt identifies this as a reproducible artifact with normalized metadata.

The extracted sources have reproduced the exact 116,224-byte reference executable. Its Python interpreter and representative executable-owned exports were checked in a bounded process without loading GameCore. Byte identity preserves the existing native executable evidence; no new gameplay episode is needed to qualify unchanged executable bytes.

The XP1 profile has reproduced its exact 116,736-byte reference executable using
the same builder and containment. Its main source differs by one include; the
additional protected binding wrapper checks the XP1 interface, vtable and target
before invoking the official registration routine. The rebuild did not execute
GameCore. A subsequent [shared service qualification](xp1-services.md) used the
byte-identical executable for XP1 Prepare, Lua registration, borrowed services and
clean destruction. Its explicit NULL-Tuner diagnostic does not admit saved Load;
complete gameplay services and official input bundles still require qualification.

The output keeps the historical executable filename and `CIV6RL_PYTHON_HOME` setting for compatibility. The launcher must supply the matching Python installation and its DLL search path. The currently extracted runtime still expects this executable through its private resource layout; the resource-package migration remains separate. This document does not claim that the complete host is deployable from the game installation alone.

Selecting a build profile does not change a session's engine admission. In
particular, do not substitute the XP1 executable into a Base session whose
resource manifest pins the Base executable, or interpret a successful XP1 build
as authorization to bypass the saved-Load refusal.

## Current source development

`--profile xp1-current` builds the explicit `native/source-current.json` source
snapshot. Its shared AUX+A0 converter also handles UTF-16 values, following the
official converter's 1,024-byte destination, complete-codepoint truncation and
isolated-surrogate behavior. Source scanning has an explicit resource bound.
Its current map transport advertises version 2 through
`LAB_AuxMapTransportVersion`, allowing an explicit nil value in nested tables.
The adapter uses legacy version 1 when that export is absent and refuses an
unknown advertised version before installing a callback. The current A8 include
is shared; the original include is retained separately for old profiles.
The `base` and `xp1` retained profiles reference the preserved old A0 include
under `native/profiles/retained/`, retaining their original executable identity.

The current builder normalizes timestamp metadata to zero and returns
`source_build_unqualified`, with `compatibility_admitted: false`. A new compile
cannot inherit a retained executable's qualification. The separate native
configuration/Lua receipt qualifies the current executable for its stated
service cycle only; it does not substitute it into Base sessions or admit XP1
saved-game loading. Reuse of the compiler, source closure checks, limits and
process cleanup is identical across these profiles.

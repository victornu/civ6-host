# Extracted local backend

The `civ6-host-runtime` distribution runs the extracted Python adapters for the official Windows GameCore. `civ6-host-client` owns the public client and its validators. Neither distribution imports the learner or PyTorch. The historical installed live round-trip is qualified for Base/hotseat. Separately, a source-runtime Base LAN cycle and its client actions were qualified on the retained one-human/five-AI capture. The new wheel qualification installs the client and runtime packages in isolated workspace targets, runs information-query tests, and replays retained native replies through the installed client and event store. It did not run a new live installed LAN session or make new native calls. Simultaneous turns, the complete action space, DLC and mods remain unqualified.

## Installation boundary

The source runtime also accepts the exact captured `input_profile="xp2-lan"`
bundle and its prepared inputs through the same `NetworkBackend`/`SessionClient`.
Its qualified groups cover loading and cleanup, limited player observations,
initial choices and turns, world/unit inputs, queue edits, one offered district
placement/resumption, two native Save/Load pairs at turn 2, and one offered
melee attack with independent reset at turn 5. See the
[current scope](../README.md) and [checkpoint API](client.md#administrative-lan-save-and-resume).
The current v18 client and runtime wheels also ran this exact capture from a
relocated private root with a locally rebuilt host. The installed client founded
a city, ordered a Scout, read its production progress at turns 1 and 2, saved
the native component pair, and closed cleanly. The original lab read guard was
active. Private evidence is `evidence/host-xp2-installed-v18-relocated.json`.
Full public information, other XP2 action routes and two-human simultaneous
play remain unfinished. The migration notes below retain their stage-specific limits.

The current source runtime additionally accepts `input_profile="xp1-lan"` on
`NetworkBackend`, with the exact retained XP1 `official_bundle` and its explicit
`prepared_capture`. The same `SessionClient` performs reset, observation,
explicit foundation/research/civic/current-production choices and close. Native
close followed by a new-process reset was qualified on that capture. A subsequent
group also qualified forced EndTurn, 16 explicit native updates and the local
human becoming active at turn 2, followed by native close and a fresh reset.
Use `lifetime_seconds=120` for this instrumented
scope; the memory limit remains 512 MiB with the existing resource reserve.
This does not enable arbitrary XP1 captures, full action/observation
coverage or the Base administrative information groups. Unsupported choices
are explicit. `poll` now calls one native update on the retained XP1 owner.
Normal EndTurn and Unready execution remain unwitnessed in this capture.
Use a short private `run_root`: the current native executable's log API still
rejects paths beyond the Windows path limit. The qualified group uses the
shortened `work/xp1t` root. Existing wheels predate
this source integration; it is not a new installed-package qualification.

The existing acceptance entry point can exercise this bounded scope using an
explicit local backend configuration:

```text
python tools/accept_session.py --config <private-xp1-backend.json> --capability-cycle --choice-group
python tools/accept_session.py --config <private-xp1-backend.json> --capability-cycle --turn-group
```

It chooses only actual native offers, checks the resulting public entities,
closes, resets into a new process and compares the initial observation/choices.
This is a host capability check, not training or a full-game acceptance.

The runtime requires Windows x64 and Python 3.12. Build the client at the repository root and the runtime from `distributions/runtime`. Install both distributions into the same environment. The client alone remains portable and has no external Python dependencies.

The runtime's save framing adapter draws on `pydt/civ6-save-parser` at commit
`caa569f9eb3f17498562e5b56281d29605c282eb`. Its MIT notice is included in the
runtime wheel. [Upstream source and notice](https://github.com/pydt/civ6-save-parser/tree/caa569f9eb3f17498562e5b56281d29605c282eb)

Official capture tools may additionally use the runtime's `capture` extra
(`psutil==7.1.0` on Windows) to observe the running application's working
directory. The headless backend and portable client do not require it. Relative
gameplay-script names need an explicit pinned selection/path-service witness;
finding a similarly named Lua file is insufficient. Original selected names
and resolved disk paths must remain separate. A captured path association does
not qualify script execution or expansion gameplay.

The latest Gathering Storm attempt completed repeated Gameplay/Configuration
reads, then the collector's physical-memory guard stopped it during Localization
capture. The official application subsequently exited normally through its UI;
the bridge and inbox were restored. Its input bundle is incomplete. This does
not establish a GameCore crash, a complete expansion Load, or a simulation
throughput measurement. No identical long capture should be retried before
the capture's memory growth is investigated.

The low-level script runtime now has an explicit source-selected XP2 game-API
registration branch. It reuses the existing owned Lua root/child and protected
registration mechanism, calls the official Core binder, and verifies the exact
engine, native host build, code bytes, dispatch slots and pre-registration owner.
The four objects lazily created by Core are left to Core; an absent external
registration owner is refused before entering the binder. Only compilation,
artifact inspection and offline composition have passed. No XP2 registration,
saved Load or complete Lua API is admitted by this addition. Base/XP1 branches
retain their previous method bodies.

The candidate native build uses the explicit source profile:

```text
python tools/build_native_host.py --profile xp2-script-api --output-dir <private-build-directory>
```

Its executable identity and build receipt must be explicitly reviewed and
registered before the runtime accepts it; an arbitrary rebuild is refused.
Private source evidence remains outside the distributable tree. The XP2
event-service composition and native connection/registration lifetime still need
qualification before a bounded native registration/Load trial. Existing public
session profiles continue to refuse XP2 rather than substitute XP1 or Base.

For an already initialized XP2 context, the low-level runtime now explicitly
selects `bind_core_services(host, context, core_library=core,
core_sha256=<exact XP2 hash>)`. It verifies the actual shared libraries, Core's
CreateConnection import, Init code and completion flag, context globals and
connection identities before reusing the existing gameplay/configuration/locale
bindings. The same context must supply the later game-API registration. Plain
availability flags cannot replace this association. Unbind invalidates it before
clearing locale, configuration and gameplay bindings; the host does not release
Core-owned connections. Calls without the new keywords preserve the historical
Base/XP1 path. This composition has passed offline fixtures only; it is not a
qualified XP2 session or a teardown proof for the Core context itself.

The shared read-only ParameterMap/A8 decoder also selects an explicit XP2
profile. Exact constructor, vtable, tree and Variant/list sources establish the
layout; the existing decoder algorithm is retained. `NativeAuxMapAdapter`
accepts an explicit `allow_nested_maps=True` with native transport V2; its
default remains false. The existing `MapArgumentFactory` can select XP2's
source-checked copy ABI. Offline composition exercised nested maps/lists,
per-map names, UTF-16, stability refusals and callback buffer ownership.
A later bounded native ABI group exercised this reader and actual XP2 owned
copies together with `ScriptEventService.install_mutable_map_result(core,
core_sha256=..., read=...)`. The explicit `xp2-mutable-map` native build appends
the caller's seeded table to the shared GameEvents dispatcher and writes that
same table back with official Core setters. The Lua return only controls
validity/truthiness; it is not the output table. Nested tables use official
owned-child construction and replacement/destruction. String registration uses
the Core registrar, and non-string keys/numbers retain the sourced conversion.
The type-2 route merges fields; removing a Lua entry does not erase an existing
native field. List-root output (discriminator 3) is outside this adapter.

The service owns AUX68 explicitly, restores its previous binding on close, and
refuses foreign providers, ownership changes, cycles and resource bounds.
Protected Lua errors, including the observed HKS status `-100`, are copied and
popped separately from host refusals. Native return validity can survive an
error after Call, as in the original wrapper; partial conversion is not rolled
back. The native group covered nil/false/no-listener returns, seeded nested
replacement, typed scalar/map arguments, native copy/release, NULL argument
packs and recovery after a Lua error, closing with zero live HKS allocations.

Evidence: `evidence/host-xp2-mutable-map.json` in the private resource lab. This
qualifies an HKS/provider ABI group against constructed fixtures. It does not
qualify the complete World Congress script, XP2 context/DB integration, saved
Load, gameplay, or production throughput. The exact official input bundle and
full XP2 lifetime validation remain pending.

The existing `SavedLoadServices` graph now also has an explicit XP2 preflight;
there is no second XP2 service owner implementation. It checks the canonical
configuration ABI, the same borrowed database lease, exact configuration Lua
callbacks/publication, host globals, manager field and dispatch code. It enables
nested map transport and owns the mutable AUX68 service before installing the
selected script contexts. A nonempty registry is retained. Passing
`bootstrap=None` for XP2 uses the existing registered Core cache in each fresh
script child; it does not repeat the native API registration or invent an API.
Includes require a separately provided resolved source snapshot.

This composition passed an offline group covering actual Python callback owners
with native calls stubbed, source/live-byte fixtures, ownership refusals and
the affected XP1 regressions. Evidence:
`evidence/host-xp2-saved-script-composition.json`. It has not been exercised on a
real initialized XP2 context or saved game. XP2 public session admission remains
closed.

The explicit native profile `xp2-script-contexts` now scopes the temporary HKS
states used by GameEvents Call/TestAll. The retained listener algorithms are
wrapped around their actual protected calls. A0/A8 accept a temporary state
only in its matching live root and OS thread; positive ownership is not cached.
`MapService(allow_event_states=True)` authenticates the native components before
using this query and treats a snapshot failure as a worker failure, rather than
letting GameEvents catch it and skip a gameplay listener. Ordinary Lua listener
errors retain the original behavior. The XP2 shared graph enables this mode.

A native HKS/XP2-provider group exercised scalar/map returns in ordinary and
nested listeners, expiry after return/error, foreign pointers/roots and a
different OS thread, then clean teardown. The prior eight mutable-map checks
also passed on this new native composition. Evidence:
`evidence/host-script-event-states.json`. This is still an ABI interaction group,
without an official game context or script bundle. Other temporary states
outside the sourced GameEvents call sites remain unqualified and refused.

This is a local migration build, not yet a self-contained community release. A [private resource package](resource-bundle.md) supplies the locally built native Python host executable, official capture bundles, dependencies and evidence under a separate directory. The retained relative layout and proof identities are preserved; the original laboratory is not read during the qualified relocated execution. The executable can be reproduced using the [extracted native build](native-build.md). The latest package inventory found host Python payloads and no game binaries, database/save assets, capture/trace files or learner/PyTorch dependency in the wheels. This path and byte audit is not a comprehensive content, credential, provenance or legal-release review. A separately installed game alone does not yet supply the complete prepared resources expected by this version.

### Local offline wheel qualification

Build the client from the repository root and the runtime from its own project
directory. The qualification used Python 3.12.14, `--no-deps`, and
`--no-build-isolation`; it downloaded no build dependencies. Install into a
fresh workspace target rather than the active environment:

```powershell
$pythonExe = (Get-Command python -CommandType Application).Source
$wheelDir = 'work\package-information-qualification\dist'
& $pythonExe -m pip wheel --no-deps --no-build-isolation --wheel-dir $wheelDir .
Push-Location distributions\runtime
try {
    & $pythonExe -m pip wheel --no-deps --no-build-isolation --wheel-dir ..\..\work\package-information-qualification\dist .
} finally {
    Pop-Location
}
& $pythonExe -m pip install --no-deps --target work\package-information-qualification\installed `
    work\package-information-qualification\dist\civ6_host_client-0.1.0a1-py3-none-any.whl `
    work\package-information-qualification\dist\civ6_host_runtime-0.1.0a1-py3-none-any.whl
```

From the repository root, run
`python tools/review_wheel_payload.py --source-root . <client-wheel> <runtime-wheel>`
to compare every packaged Python file and the runtime source map against the
checkout. The check also compares the runtime's third-party notice and verifies
each wheel's RECORD. Review source provenance separately before publication.

The client wheel excludes `civ6_host.runtime`; a separate client-only target
also imported the public client and contracts without loading runtime modules.
The combined isolated target passed 35 focused economy, information-group,
event-store, stream and `SessionClient` information tests. The retained native
replay exercised 54 recorded commands and 36 available queries across all four
groups; waiting/modal boundaries reported information unavailable. No native
process or new GameCore call was made. See
[`work/package-information-qualification/qualification.json`](../work/package-information-qualification/qualification.json),
the [retained replay summary](../work/package-information-qualification/retained-information-replay.json),
and the [install-note candidate](../work/package-information-qualification/INSTALL-NOTE-CANDIDATE.md)
for wheel hashes, package inventory, and replay evidence. This confirms local
packaging and client/store projection only; it adds no live installed LAN
qualification.

A subsequent offline build reproduced both current wheels byte for byte from
two separately staged copies of the source. Use Python 3.12.14, pip 26.2.2,
setuptools 84.1.0, wheel 0.48.0 and `SOURCE_DATE_EPOCH=1793692800` to reproduce
that comparison. Stage `src`, the root `pyproject.toml` and
`distributions/runtime` without build directories, egg metadata or bytecode.
Set `PIP_NO_INDEX=1` and use the wheel commands above. The clean installed
target imported both packages without importing the lab or PyTorch. The
private receipt `evidence/host-wheel-reproducibility-current.json` records
the two archive hashes, entry counts and dependency declarations. This check
covers the Python wheels and their contents. Native resource preparation and
review of source provenance remain separate release requirements.

The wheels containing the exact command receipt checks and detached information
readers were also rebuilt from two fresh trees. Both hashes matched, the wheel
payload and RECORD checks passed, and a fresh combined install verified all
418 mapped sources. The [local build receipt](../work/release-wheel-review-siwjdklw/review.json)
identifies these particular artifacts. This check ran without GameCore.

A later offline build of the client wheel also replayed all 22 recorded
commands and their authenticated responses from the Gathering Storm
turn-48-to-51 session. The installed client reconstructed each command and
matched it to the recorded request. The replay used a client-only installation
and did not execute GameCore or exercise a native victory. The private receipt
is `evidence/host-xp2-turn48-to51-installed-client-replay.json`.

The runtime source archive stages the shared Python runtime and its source
map inside the archive. To build it with the local toolchain, run
`python -c "from runtime_build import build_sdist; print(build_sdist('dist'))"`
from `distributions/runtime`. Set the same `SOURCE_DATE_EPOCH` for both builds
to reproduce the source archive. Extract the archive into a fresh workspace
directory and run the offline `pip wheel` command from its project root.
That route reproduced the direct wheel byte for byte. The native build sources
remain in the repository, and private resources supply the game and capture
files. See the [local archive receipt](../work/release-wheel-review-siwjdklw/normalized-unpacked-review.json).

The launcher provides that directory explicitly. It is never added to `sys.path`. The actual worker runs from the installed package. A runtime import guard rejects `civ6rl`, the old `tools` namespace and `torch` in both the supervisor and worker. A Python audit hook also rejects execution of Python files from private resources, including loading them under another module name. These are checks against accidental migration regressions, not a sandbox for hostile Python. The resource root is immutable for the process; use a new process for another root.

```python
from civ6_host import HotseatClient
from civ6_host.runtime.backend import LocalHotseatBackend

# All values below are supplied by the caller's qualified local configuration.
backend = LocalHotseatBackend(
    resources=private_resource_directory,  # existing absolute directory
    official_bundle={"path": bundle_relative_path, "sha256": bundle_sha256},
    prepared_capture=prepared_capture_reference,  # {absolute path, sha256}, or None for original admission
    private_resources=private_resource_reference,  # {absolute path, sha256} for relocated inputs
    ui_profile=qualified_ui_profile,
    run_root=private_run_directory,
    **qualified_session_options,
)
client = HotseatClient(backend)
try:
    view = client.reset()
    # The caller selects from view["decisions"]["candidates"]. The host does
    # not choose a policy, reward, fallback action or strategic restriction.
    candidate = caller_choose(view)
    view = client.act(view["decisions"]["decision_id"], candidate["candidate_id"])
    result = client.close()
finally:
    client.abort()
```

This example is an API sketch using caller-provided configuration, not a runnable default scenario. Existing explicit session options retain their historical names and semantics during extraction. Unsupported options, profiles and missing resources fail rather than substitute a different setup. The native supervisor retains process duration/memory limits, private database copies, source checks and cleanup. Uncertain action completion is not retried automatically.

The optional [prepared capture](capture-package.md) is produced by full original admission and consumed by the same Load path. It avoids revalidating thousands of raw export fragments at every reset, while retaining runtime-file hashes, exact capture/code identity, official-save checks and private database copies. Relocated input mode requires both this capture and the explicit private resource manifest; original admission remains available separately.

## Provenance and compatibility

`tools/extract_runtime.py` extracts the existing execution graph; it does not reimplement rules. `src/civ6_host/runtime/source-map.json` records every original/destination source hash and the transformations applied. The original laboratory sources remain untouched.

Historical receipts refer to the original source bytes. `provenance.py` resolves those bytes as proof data and verifies them separately from the installed code. It also pins the actual installed Python sources and source map in each native run. Reading an old producer hash must never be reported as executing that producer's old code. The resource resolver maps original paths to verified copies without rewriting those receipts. Prepared-capture producer compatibility is registered explicitly; unknown producers or changed original validators are refused.

The extraction removes legacy CLI launchers and the embedded diagnostic neural selector from the explicit-choice execution path. The city ranged-attack observation helper imports the installed collector rather than executing its historical source file. Literal checkpoint transport imports also resolve to installed modules. Public observation continuity validation and the existing wire budget parser remain, without reward calculations, PPO or learner execution. Public schema identifiers remain unchanged to preserve existing clients and receipts.

## Acceptance scope

The grouped extraction check uses an installed wheel in an isolated Python process. It compares public reset/observe/action/close responses with the retained native trace, excluding only per-episode identity fields. It also verifies native process cleanup and unchanged historical plus installed sources. The comparison does not require rerunning the old backend or a training episode.

A passing round-trip qualifies that extraction boundary on its named official Base/hotseat capture. The relocated acceptance also forbids reads of the old lab and checks that parent and worker pin the same private resource manifest. It is not evidence of full-game coverage, production throughput, simultaneous multiplayer, portable capture preparation or new strategic learning. Broader profile qualification remains necessary; the native executable build has been extracted and reproduced byte-for-byte.

`examples/local_session.py --config <private-config.json>` exposes the same client through newline-delimited JSON commands: `{"op":"reset"}`, `{"op":"observe"}`, `{"op":"act","decision_id":"...","candidate_id":"..."}`, and `{"op":"close"}`. IDs must come from the returned catalogue. The supplied configuration names exact resources, capture, UI profile and bounded session options; no game world, action or model is selected automatically. The private configuration and captured data are not distributed in this repository.

For an offered `policies` action, include `"parameters":{"assignments":[...]}`
in the action command. Supply one unsigned hash from the corresponding
slot's options, in slot order. Both LAN and hotseat use this input format.

## Saved-Load engine profiles

The existing `NativeLoadBackend` uses `runtime.saved_load_profiles` for its
outer/inner/Game vtables, Prepare, configuration-copy, Load and initialized-getter
addresses. Selection uses the exact GameCore SHA-256. Unknown engines fail;
there is no fallback to Base and no choice based only on the DLL filename.

The Base path retains its native signatures, executable-byte checks, five live
virtual-target checks, provider ownership checks, stream bounds and job/control
guards. Configuration ownership, Init and teardown now have a shared Base/XP1
path described below. Remaining expansion profiles still require their own
service qualification. This is integration into the existing loader, not a second Load route.

These profiles originally described statically verified targets only. The exact
XP1 capture now has the independently qualified shared client cycle described in
[XP1 services](xp1-services.md); unknown captures and XP2 remain refused.
Source similarity does not qualify providers, host services or serialized data. In particular, outer `+0x120`
and the inner Load compatibility check at `+0xC8` are distinct paths; matching
wrapper instructions does not prove the semantics of their callees.

The initial grouped offline validation checked profile targets against pinned binary
evidence, unchanged Base call signatures/targets, identity/refusal guards and
synthetic memory. No expansion save was loaded in that initial group;
subsequent XP1 native qualification is described in the linked service history.
The previously installed wheels predate these source
changes. Admission of an XP saved game still requires the remaining services, an exactly
associated official save/final-database/content/script bundle, and native Load
and continuation evidence. XML/SQL imports and NewGame are not reconstructed.

The source-only `xp2_configuration_profile` describes the provider keys,
64-record vector and separate embedded provider lifetime using retained binary
evidence. The common configuration owner and codec selectors now accept its
canonical, source-verified profile; the configuration-copy wrapper and relink
helpers also have a selected XP2 source profile. These connections are checked
offline. They do not qualify native XP2 provider construction, configuration
restoration or saved-game Load. Unknown profiles still fail.

### Configuration ownership and codecs

`runtime.configuration_profiles` binds the existing native configuration owner,
indexed context snapshots and bounded stream session to an explicit engine.
Base defaults, entry order, native signatures, stream limits, fatal-on-uncertain-
mutation behavior and restoration sealing are retained. No serialized configuration
is reconstructed in Python. An owner remains tied to one engine and context.

The XP1 implementation uses the retained clone/destructor evidence and
complete pinned reader/writer/helper bodies. The same algorithm checks its root,
map and 64 player objects and refuses aliasing. The shared provider code has
passed synthetic-memory, mocked-call and local Win64-stream callback checks,
then a bounded native group using the shared product backend. That group calls
XP1 Init, clones the configuration, writes and reads uint/hash/UTF-16 diagnostic
values in root/map/player objects, serializes and restores 1,514 identical bytes,
refuses restore after sealing, closes the owner, destroys the context and shuts
down Database. It uses retained diagnostic databases, not an official saved game.

`native_host.initialize_context(..., context_profile=...)` preserves the Base
default and explicitly admits the source-bound XP1 context profile. XP1 uses its
own verified callback allowlist and installs its teardown callbacks after Init;
it never installs the Base event recorder or pre-Init aligned-free callback.
The common configuration backend selects the engine's provider and inner table,
uses the shared dependency directory and requires an explicit digest for XP1
configuration restoration. Context destruction refuses a live owned provider or
a missing XP1 teardown installation. Unknown engines and profiles still fail.

The qualification reuses the retained isolated supervisor with a 45-second limit,
512-MiB private-memory cap and 2-GiB free-memory reserve. The successful common
cycle took 2.81 seconds and sampled approximately 50.4 MiB of private memory.
These figures measure configuration setup and teardown, **not game simulation
throughput or parallel capacity**. No renderer, full game executable or learner
was started.

XP2's source-verified ownership and configuration-copy profiles do not remove
saved-game admission checks. Native configuration lifecycle and the remaining
Load services and preparation prefix must be qualified together with the exact
official saved inputs before admitting that path. The final databases and complete
official save/content/script bundle remain a separate requirement; the old Init
diagnostic databases do not constitute it.

## Inspect the saved turn settings before launching

The runtime also exposes a read-only control-plane operation:

```python
from civ6_host.runtime.session_configuration import inspect_prepared_capture

settings = inspect_prepared_capture({"path": absolute_manifest_path, "sha256": manifest_sha256})
```

Its CLI is `python -m civ6_host.runtime.session_configuration --prepared-capture <manifest.json> --sha256 <digest>`. It verifies the existing prepared package and reads its serialized `GAME_ROOT` and final configuration database. It does not load the GameCore, mutate a save or provide actor inputs. Saved `GAME_MODE`, `TURN_PHASE_TYPE` and `TURN_TIMER_TYPE` are reported separately. Missing saved values remain missing; setup defaults are descriptions, never substituted into the save.

With the private resource root configured, use `python -m civ6_host.runtime.session_configuration --official-save <game.Civ6Save> --sha256 <digest>` to inspect an original save before preparing a capture. This reports the saved mode, raw phase and timer values, declared ruleset and mod identities. The `saved_roster` field counts serialized slot statuses and slots marked `SS_TAKEN`, without exposing player names. The capture's final configuration database is needed to interpret phase and timer domains. The live roster, mod activation and simultaneous command execution require runtime evidence.

For the retained expansion captures, use `--prepared-capture <manifest.json>`
with `--sha256 <digest>` and an explicit `--candidate-profile xp1-lan` or
`--candidate-profile xp2-lan`. This verifies the exact capture and reads phase
and timer tokens against its own final database. The option is scoped to
inspection and does not select or open a runtime session.

The pinned EXE's `IsNetworkMultiplayer` predicate recognizes `NETWORKMULTIPLAYER`, `INTERNET`, `CROSSPLAY` and `LAN`. This classification is distinct from the saved turn-phase token, and neither proves multiple actionable players or admission of a network session. Unknown mode values remain explicit raw hashes. Phase/timer token definitions come from the capture's final database rather than a separately reconstructed table.

On the retained Capture09 package, this installed operation reads `HOTSEAT`, no saved turn-phase property, and `TURNTIMER_NONE`. The same database lists simultaneous/dynamic choices for network setup; it excludes hotseat from that parameter. The current `HotseatClient` remains hotseat-only. A simultaneous backend still requires native perspective/identity routing, turn progression and command-conflict qualification.

## Additional human perspectives

The experimental `public_view_players=[0, 1]` backend option requests separate public views at each live accepted boundary of the retained four-human Base session. After reset, `client.player_view(1)` reads that player's latest observation, revealed map and turn-activity flags. `client.observe()` refreshes these views. The JSON-line example accepts `{"op":"player_view","player_id":1}`; enable the corresponding option in its private `session_options` first.

The response uses `civ6-host.player-view.v1`, joined to the episode, generation, sequence, player and turn. The observation/map hash and visible plot rows must agree. It contains no command catalogue, host diagnostics or privileged critic data. The existing current actor's choices remain in `client.view()`. Inactive-player views do not authorize inactive-player actions, and callers must route each view only to its own player policy.

Collection calls Core's automatic perspective-update routine used during native turn activation, retaining its notification path, with pinned code and live human-status checks. The Lua `PlayerManager.SetLocalPlayerAndObserver` setter is excluded because it also transfers human/AI control. It checks native turn/activity/configuration state, drains supported callbacks, restores the original local player and observer, and compares the original public observation. Unknown callbacks or uncertain restoration fail the session. It never advances the game to obtain a view.

Only the latest per-player files are retained, bounded to 8 MiB each, and the client refuses stale or unconfigured players and closed episodes. This interface does not establish simultaneous command scheduling, a complete observation space or graphical parity for every player's view. The existing revealed-map limits remain explicit in the response.

The LAN `SessionClient` keeps a separate catalogue per actor within a turn.
When a native reply advances the turn, earlier actor views and catalogues expire.
Observe each actor again before issuing their next command. Every explicit
player request requires a response for that actor whenever a view is present.

The installed native acceptance on Capture09 passed for player0/player1 at reset, observe and after the retained player0 city-founding action. All four old reset/observe/act/close replies matched the retained reference, with only episode identities excluded. Six public collections preserved human slot statuses, activity flags, turn and original perspective; two latest-view files remained. The worker exited and all 1,101 pinned source/resource entries stayed unchanged. This is a narrow host capability test, not a learning episode or evidence that simultaneous multiplayer is ready.

## Player-scoped decision contexts

The extracted `read_decisions` and `apply_choice` now share a bounded context
store indexed by player within the native episode, generation, roster and turn.
Reading one player's catalogue does not overwrite another player's retained
decision. Immediately around an action, the store activates that player's
snapshot for the existing native adapters, then restores the caller's aliases.
Episode-wide placement tracking stays live outside those snapshots.

A successful command consumes only its actor's snapshot. A stale activation is
refused without discarding other windows; an uncertain adapter failure clears
all retained snapshots. A newly captured native turn, roster or episode replaces
the previous scope. Captures are copied only after checking object, depth and
byte limits: 16 MiB per player and 128 MiB total accounted Python object size.
Oversized data fails explicitly instead of truncating the catalogue. This is
not a bound on the GameCore's own process memory, which is enforced separately.

The existing client API and public responses are unchanged. The current native
profile/actor/perspective admission, candidate membership, observation continuity
and action-specific revalidation still apply. This refactor does not admit
commands for inactive players or implement simultaneous scheduling. The compact
`decision_context_*` events belong to private host diagnostics; they contain
identity, counts and sizes, not additional actor observations or critic inputs.

Installed acceptance on Capture09 exercised capture, activation and consumption
of player0's exact published decision while collecting player0/player1 public
views. Reset/observe/action/close retained the previous public outputs. The
largest accounted snapshot was 70,848 bytes. The single native check took about
70 seconds including startup/instrumentation, not a production-throughput
benchmark. Two-player retained windows, stale-scope refusals and shared-ledger
preservation were checked on components; native simultaneous commands still
require their own admission.

The runtime's `verification` extra supplies the pinned PE reader for the
offline tests that inspect the installed GameCore image. Install
`civ6-host-runtime[verification]` from the local wheel and a wheelhouse
containing its dependencies. The source tests still need the private resource
root and the exact official binaries referenced by their proofs.

Run `python tools/review_wheel_payload.py <client-wheel> <runtime-wheel>` from
the repository root before a local distribution review. The check reads each
member, rejects unexpected paths and binary payloads, and scans for several
common credential markers. It also checks each member's SHA-256 and size
against the wheel's `RECORD` file. It reports the exact artifact hashes for
the review.
Source provenance and legal review remain separate.

### Source archive for local review

Run `python tools/review_source_payload.py --archive work/civ6-host-source-review.zip`
from the checkout. The archive can rebuild the two wheels and the native
host profiles. It includes the sample client, build documentation, the
third-party parser notice and a `SOURCE-REVIEW.json` inventory of exact bytes
and SHA-256 digests. The exporter validates native include manifests and
installed Python destination hashes. Use a fresh archive path for each export.

The archive excludes private resources and research records, game files,
compiled artifacts, internal validation fixtures and the learner. Some setup
notes refer to privately retained receipts. The game installation and private
input preparation are still required for a native session. The archive is a
local candidate for provenance and license review.

The LAN client and runtime both reject a reply that retracts a confirmed
victory or changes its turn, winning team or victory type within the same
episode. The check compares the shared result only. Player-specific fields
are validated separately, and a fresh reset can start a new episode.

The private LAN journal's `native_lan_update_timing` event includes
`guarded_host_callbacks` for the update thread. It reports outer callback
wall time by function and vtable offset. Nested callbacks are counted
separately and their elapsed time stays with the outer call. A callback can
invoke native code, so this is wall time in a callback, not Python CPU time.
Other native entry paths are outside this measurement. If both monitoring
slots are occupied, the timing report marks attribution unavailable.

During each Gathering Storm LAN update, the argument reader shares a
single source-proof scope on the owning thread. Each argument map still
checks the live iterator/count code, count slot, and stable borrowed
bytes. The static source is revalidated before publication. The native
three-turn comparison kept all 25 public responses and the recorded
event order while reducing the measured gameplay window from 78.15 to
68.63 seconds. This result covers one instrumented worker and capture.

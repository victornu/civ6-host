# Gathering Storm captured inputs

The retained official LAN capture from 2 November 2026 contains one human
player and one AI at turn 1. It uses the Gathering Storm engine and the
experimental observation bridge. It does not qualify a competitive mod profile
or two-human simultaneous play.

For a competitive capture, `tools/check_bbg_capture_selection.py` checks the
hash-pinned export before any attempted Load. Use the runtime import path and
its configured private resource root, pass the capture manifest with
`--sha256`, and optionally nominate the precise captured save with
`--expected-save-sha256`. The check reads the saved declaration, verifies
the observed ordered source selection across the save, and checks the copied
configuration and gameplay databases against the recorded export identities.
It also revalidates both official active Localization exports, including the
save boundary and the materialized SQLite identity, through the existing
bundle reader. All three final database digests appear in the result.
The manifest and its Localization and save witnesses must resolve to the same
capture tree through the configured resource resolver.
The BBG 7.5.1 candidate requires its declared UUID, Workshop ID and title,
plus the main script selected from that Workshop package. The check joins
the source path witness to the capture process and rechecks original and
copied bytes. Each selected gameplay entry from that package must match its
declared path, size and digest. The game's observed order and settings decide
which optional scripts are selected. Included files, UI scripts and native
execution still require separate checks. The retained XP2
LAN capture verifies all three databases and has no BBG selection. Its exit
code of 1 indicates that no BBG candidate was found after successful screening.

`tools/capture_script_path_witness.py` builds the existing capture994 path
witness from a pinned `runtime-selections` report and the current read-only
XP2 process observer. Pass `--script-root` for each exact approved game or
Workshop package directory and `--output` for a new witness file. Use the
pinned `psutil` 7.1.0 process-inspection dependency. Pass the returned pin and
the selection report's process identity to the existing `capture()` via
`script_path_context={"witness": pin, "process": identity}` and use the same
`script_roots`. This supports the verified relative native path contract and
refuses escapes, path aliases and roots absent from the request. A mixed
official/Workshop source list was first validated offline. The 4 November
local BBG 7.5.1 duel then provided a native selection of WorldCongress followed
by the drive-qualified Workshop path for `scripts/bbg_script.lua`. The
headless Gameplay database owner restored the official debug export to
memory and read a base Knight cost of 200. The original save contains the
`P_CAPITALS` property initialized by BBG Lua. The active Localization
database for this capture still needs an export, and the current XP2
admission accepts the retained stock capture and its single WorldCongress
script. The BBG game has not entered headless Load. See the
[local PoC evidence](../../civ6-rl-lab/evidence/host-bbg751-local-poc.json).

The later source-runtime witnesses now qualify loading this exact bundle,
limited observations and input families, initial turn progression, one district
placement/resumption, and a two-Save/two-reload cycle at turn 2. See the
[current scope](../README.md) and [Save/Load API](client.md#administrative-lan-save-and-resume).
The sections below preserve the individual migration stages and their historical
limits. They do not establish a complete game, full observation parity or
compatibility with other captures/content.

The official game produced the save. The existing application-configuration
reader derives its provider from the source-pinned serialized preamble; no
configuration is reconstructed from XML or guessed save offsets. The gameplay
and configuration exports matched all captured main-table values. Localization
was exported from the active connection without committing, rolling back or
replacing its transaction. Repeated table reads agreed on both sides of the
save request. The selected disk source is WorldCongress.lua, with its exact
ordered path and same-process working-directory witness preserved privately.

`native_official_bundle.read_bundle(reference, input_profile="xp2-lan")` uses
the existing complete capture reader. The XP2 scope is an explicit private
input family: exact capture, executable, engine, configuration, game stream,
selected source and retained active-list checks. Unknown captures and changed
inputs are refused. Base and Rise and Fall keep their existing scope guards.
An input-only bundle cannot be reused as a publicly admitted native session.
The grouped offline acceptance passed 37 cases, including the full raw capture
reader, exact configuration/game hashes, source-copy mutation refusals and the
unchanged public Base/XP1 boundaries. It ran in a 512-MiB job, with roughly
148 MiB peak private memory; this is verification cost, not simulation speed.

Offline consumption uses an explicitly pinned snapshot of the producer source
bytes. The retained profile keeps its original paths and hashes; the reader
checks the archive/copies and carries their dependencies. It does not require
leaving the temporary capture transport installed. Live capture retains strict
checks against its actual installed sources. No recorded producer profile is
rewritten as the new consumer version.

Prepared packages remain bound to their reader version. This input delivery
does not grant compatibility to older XP1 packages: the retained older package
requires fresh preparation from its existing official raw capture before use
with the current source runtime. The earlier native XP1 receipts and their
original runtime versions remain valid, separate evidence. No broad version
exception or new official-game capture is needed for that preparation.

This work does not prove that the selected disk bytes were the historical
in-memory script bytes, that every gameplay dependency has been implemented,
or that the save, databases and script state form an atomic snapshot. Native
XP2 Load, script registration/execution, readback and teardown must be qualified
together before exposing a playable Gathering Storm session. The capture's
one-human LAN mode does not establish two-human simultaneous behavior.

The save, databases, official script and raw receipts remain in the private
research lab. They are not part of a distributable host package. The official
game was closed normally after capture; only the project's two temporary mod
files were restored to their exact backups and its bridge was disabled again.

The selected-script registry now separates the exact native path strings from
their approved physical files. `script_wire_paths.registry_from_capture()`
reuses the captured-source/CWD validators and provides the original ordered
names, private copied files and hashes. It does not scan assets or interpret
relative wire names as filesystem commands. Duplicate native records stay in
order; an ambiguous native name mapping to two different files is refused.

The common implementation was exercised by the real XP1 script manager using
three selected fixture records and two distinct sources. The native loader,
Lua buffer names, protected-error source paths, listener effects, replacement,
Clear and Destroy agreed. The actual XP2 WorldCongress capture was bound and
hashed offline. This does not establish native XP2 manager execution or running
WorldCongress in a loaded Gathering Storm game. Private evidence:
`host-script-wire-paths.json`.

The explicit XP2 captured owner now reaches the same `_NativeBackend`
configuration lifecycle used by Base and XP1. Its engine-specific source
profile selects Init, SetHost, both path callbacks, database logger registration
and enablement, the complete ordered filter list and native teardown. Unknown
callbacks remain fatal refusals. The static inventory includes final jumps as
well as direct calls; the first incomplete 15-call inventory and its refused
native attempt are retained separately.

A bounded native process consumed the existing prepared package, made fresh
private database/ICU copies, opened both native connections, initialized the
context, restored and serialized the captured provider, released its owner,
destroyed the context and shut down Database. All three database hashes stayed
unchanged. The process peaked near 150 MiB private memory; this is configuration
qualification cost, not memory per loaded game or simulation throughput.
The changed common Init mechanics also passed the existing XP1 native
configuration group. This delivery makes no new public saved-session admission.

The two serialized streams have equal length and differ at two empty-string
flag bytes. The retained general provider reader consumed all 984 values and
found no other changes. The subsequent XP2 source proof closes the exact
reader/writer branch: tag 5, extra word 0, size 1 and zero inline payload lose
the `0x20000000` marker on read. The writer then serializes flags zero and the
unchanged remaining fields. `configuration_roundtrip.compare_provider_roundtrip`
requires an explicit engine hash, verifies that engine's proof, then reuses the
existing complete-stream comparison algorithm. Unknown engines or any other
byte changes are refused. The input decoder and prepared package remain unchanged.

This offline review consumed the retained native input/output and original
completed process receipts. It did not execute the DLL again or relabel the
historical sources. The earlier Base-only classification stays preserved as
earlier evidence. Raw-byte equality is still false; this proves only the exact
representation relation. Neither that comparison nor successful Init is a
saved Game Load, World Congress execution or whole-game restoration. Private
delivery: `evidence/host-xp2-provider-equivalence.json`.

The common DeferredService, ControlInputService and EventArgumentService now
select the XP2 source contracts without copying their algorithms. The cache
registry uses the XP2 globals and its actual subscriber pairs; the host never
substitutes an empty native registry. A0 reading verifies the complete 68-byte
successor, including the parent branch after the first return. Controller D0
uses an explicit local player; its flag shares the existing EXE controller state.

The composed fixture validation substitutes only memory and native calls. It
checks complete argument copies, FIFO feedback, shared controller state,
notification lifetime, cleanup and rejection of unknown events. Historical
Base/XP1 tests for the changed shared services passed in the same group. No XP2
saved-Load, actual event reachability or loaded teardown is inferred. Prepare,
capability/option callbacks, saved-Load logger, job ownership and loaded lifetime
must be assembled with the selected World Congress script before the grouped
native qualification. Private evidence: `evidence/host-xp2-preload-services.json`.

An earlier composed native group passed Prepare and official Lua binding
and entered the actual saved Load. It stopped at logger slot 0x30, returning to
XP2 RVA 0x4316E6; the unknown callback was not acknowledged. The two earlier
assembly refusals, the corrected explicit borrowed-service binding and the
ASLR-correct job vtable checks are retained with their executed source archives.
The application mirror was then an explicit pending XP2 capability. In that raw
diagnostic only, HOST130 remained its original fatal refusal, as did unadmitted
postload/publication/command callbacks. This is not a public session or a completed
Load. Source selection, clean loaded closure, readback and full game continuation
remained separate claims. See private `evidence/host-xp2-load-composition.json`.

The subsequent grouped witness now completes native raw Load, executes the exact
selected WorldCongress source, compares limited own-player state to the capture,
then runs Unload/Destroy and closes services, configuration, Lua, lock and Database.
Its executed sources and job ledgers were authenticated after process exit. The
worker exited normally within its 120-second/768-MiB bounds: 74.82 seconds,
291,504,128 bytes peak private memory. This is an instrumented startup/teardown
measurement, not turn throughput or parallel capacity. Source-selected mirror,
logger and DistrictRemoved notification handling are included. Private evidence:
`evidence/host-xp2-loaded-cycle.json`; the preceding Load-success/Unload-failure
is retained in `evidence/host-xp2-raw-load.json`.

That raw group does not call Post160, publish public caches, execute player actions,
advance turns or prove full-state equivalence. Those shared session adapters are
the next integration group. The already completed raw Load and clean lifetime
are retained prerequisites, not missing capabilities to reconstruct.

The following grouped witness reuses that same loaded owner and completes native
cache population, Post160, cache publication and all loaded cleanup. The parent
authenticates each receipt, executed source archive and ordered job ledger after
normal process exit. It observed the pending-zero Post160 branch, the 44x26 map
cache and consumption of the EmergenciesUpdated notification. The process took
94.42 seconds and peaked at 357,249,024 private bytes under the existing bounds.
Two earlier attempts that returned from publication but failed Python lifetime
guards remain preserved; neither is relabeled as successful closure.

Evidence: `evidence/host-xp2-postload-cycle.json`. This proves the internal loaded
cycle for the captured state, not player observation, commands, turns, general
visibility-transition support or a playable XP2 public session. The next group
binds the official UI APIs in a separate owned Lua child and reuses the existing
player-scoped collector; it does not reconstruct native gameplay getters.

That observation group now passes in the same loaded owner: source-selected
official UI registration, a separate managed child, player/observer checks,
the shared native collector and full cleanup. The native read contains 28 visible
plots and two own units. The existing retained-capture comparator was reused
without changing its historical source: all ten recorded neighboring plots,
own units and the zero-city economy match both official before/after observations.
This comparison does not extend the official sample or establish complete
visibility, resource visibility, absent-city behavior or all UI registrations.

The process exited 0 in 108.98 seconds, with 356,573,184 peak private bytes. All
ordered phases and source identities were authenticated after exit, including UI
child release after native Destroy and before Game child/runtime release. The
earlier UI attempt stopped before binding because source inspection exceeded a
bounded-reader request; its failed receipt is retained. The correction checks
all original bytes in chunks without increasing the memory-reader limit.
Evidence: `evidence/host-xp2-player-observation.json`. Gameplay commands, choices,
turn progression and public XP2 session admission remain separate work.

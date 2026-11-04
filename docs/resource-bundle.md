# Explicit private resource bundle

`civ6_host.runtime.resource_bundle` copies only the caller-selected relative files. It preserves their POSIX relative paths and bytes, streams each source through SHA-256 during copy, and records the original absolute `source_root` plus `{path, sha256, bytes}` records in `private-resources.json` (`civ6-host.private-resources.v1`). The manifest is written last. The returned reference contains the absolute manifest path and its SHA-256.

`read_resources(reference, resource_root=...)` requires the reference to name that root's `private-resources.json`. It verifies the manifest digest, schema, portable relative paths, sizes, hashes, and canonical in-root regular-file paths, then returns the verified manifest. Consumers resolve each recorded relative path beneath the explicit `resource_root`.

The exporter does not discover files, execute Python or native code, resolve external game dependencies, or rewrite source manifests. It refuses existing destinations, Windows case/alias and file/directory collisions, traversal, absolute paths, symlinks and redirected files. Failed exports leave their partial destination without a valid manifest reference; retry with a new destination.

Callers must select and hash every desired input before export. This utility does not imply that a selected set is a complete runtime resource closure.

The runtime command accepts a UTF-8 JSON object whose keys are relative POSIX
paths and whose values are expected SHA-256 digests. Use explicit absolute roots.

```powershell
python -m civ6_host.runtime.resource_bundle export --source-root C:\private\source --destination C:\private\prepared --selection C:\private\selected-files.json
python -m civ6_host.runtime.resource_bundle verify --resources C:\private\prepared --sha256 <digest-from-export>
```

Export prints the reference consumed by the backend. Verify checks that reference
and every selected file, then prints the count and total size. Verification is
file-only and can be run before any native session. The selection is supplied by
the operator and does not attest that all inputs needed by a profile are present.

## Runtime resolution

Pass the returned reference to `LocalHotseatBackend(private_resources=...)`, set `resources` to the new package directory and supply its prepared capture reference. The backend configures this choice before importing native adapters. Parent and worker pin the same resource manifest. The original root and the new root must be disjoint; there is no fallback to the original directory.

`resource_resolution.resolve_path` maps filesystem `Path` references beneath the original root to the same selected relative file or its parent directory under the package. Installed adapters use this helper at explicit Path construction and file-access boundaries. Other object types, live output paths and external game-installation paths retain their existing behavior. Missing selections and redirected paths fail. An audit hook also refuses opening or enumerating the old root after configuration, including accidentally unconverted accesses. This is a regression boundary, not a hostile-code sandbox.

Historical capture receipts keep their exact original JSON bytes. Two file-reference producers used by the retained response-writer validator preserve the original logical `path` only for copies whose current byte count and hash match the resource manifest; live output references retain their actual locations. Export also preserves each source modification time because those historical receipts record it. Their current copied bytes and mtime are still checked by the original validators. Resource selection and path conversion do not bypass capture validation or fabricate a capture acknowledgement.

The package is private local input, separate from both public product repositories. It may contain official saves/databases, original proof sources and local traces. The engine and official installation remain external dependencies. A successful named native round-trip proves that path's resource isolation only; it does not establish additional turn modes, extensions, action coverage or a general community installer.

For the exact retained Gathering Storm LAN capture, the relocated session checks
installed code and validates each historical source it uses. The full archive
audit is available through `verify_installation(audit_historical=True)`.
The installed client loaded that capture, founded a city, wrote a native
checkpoint and closed cleanly with 100 historical files omitted. The selection
retains the response-transport sources used by worker Localization validation.
This qualification covers that session and action, with private evidence in
`host-xp2-reduced-archive-native-cycle.json`. Other captured profiles and later
action families may require different sources.

The v18 relocated install used 1,192 explicitly hashed private files and a
local XP2 host build. The selection included nested files read by source
validators during both preparation and closure construction. A previous
working selection and a native run's pin map alone had omitted seven such
files. The original lab read guard stayed active during the successful
installed run. See `host-xp2-installed-v18-relocated.json` for the selection
and the retained refusals. This remains a preparation for the exact retained
capture with locally supplied official files.

The XP2 foundation-event and session-view dependency owners now declare those
seven nested sources. The relocated parent includes their SHA-256 digests in
the worker launch closure. The check stops before worker launch and keeps the
previous installed native run as the gameplay witness. See
`host-xp2-relocated-source-pin-closure.json` in the private lab.

The v21 qualification reused the authenticated v18 selection and added five
private dependencies from the installed runtime's launch pins. The normal
resource exporter materialized all 1,197 selected files in a new directory.
The XP2 host was rebuilt from the source review archive inside that directory.
The installed client loaded the retained capture, founded a city on turn 1,
read its native unit and tile purchase offers, saved and closed. The original
resource root remained guarded. Use a qualification report destination outside
that original root. This workflow still requires the authenticated v18 selection
and the exact official capture. Private evidence is recorded in
`host-xp2-installed-v21-relocated-native.json`.

A fresh installed process in the same resource directory then resumed the
turn-1 checkpoint and restored its complete public observation and v21
catalogue under a new episode identity. It chose research, a civic and Scout
production, ordered the Warrior to wait, then submitted the offered normal
end turn. The native turn reactivated the player on turn 2 and the Scout's
production advanced from 0 to 4. The session saved a successor checkpoint
and closed cleanly, with distinct worker databases and a verified original
capture. Private evidence is recorded in
`host-xp2-installed-v21-relocated-resume-native.json`.

The v22 lineage test relocates 27 existing checkpoints with their producer
closures, exact teardown transcripts and private database copies. The reader
uses relocated paths for file access and retains the original path keys inside
authenticated receipts. The package also preserves the exact project host
build and its historical build receipt, which the checkpoint proof still pins.
The installed client restored turn 48 and an acquired promotion, saved a new
checkpoint in the relocated root, and closed normally. The reader separately
authenticated the resulting 28-checkpoint chain with original-root access
guarded. The selected package occupied 3.42 GiB for this retained lineage.
Private evidence: `host-xp2-installed-v22-relocated-lineage.json`.

## Private expansion input handoff

The XP2 capture selection preflight accepts a caller-selected capture994
manifest under the private `work` directory and its expected SHA-256. It checks
the installed EXE and GameCore identities, the bracketing observations and Save
acknowledgement, and the native configuration and GameCore sections of that
Save. The turn and map come from the selected capture. Run it before preparing
runtime resources:

```powershell
python -m civ6_host.runtime.xp2_capture_selection --capture work/capture/manifest.json --sha256 <capture-manifest-digest>
```

Supply both `--localization-sources <producer-manifest>` and
`--localization-sources-sha256 <producer-manifest-digest>` to also review the
final inputs. Use the retained producer snapshot from the actual capture.
The review replays the configuration and gameplay journals on each side of
the Save, joins their ordered requests to the captured bridge exchanges,
compares the exported SQLite contents, and checks Localization/ICU and the
ordered WorldCongress source against the captured process. It supports the
reviewed stock XP2 LAN capture profile and its existing journal formats.

With full producer provenance, add `--prepare-private <fresh-worker-directory>`
to stage the selected capture under private `work`. The existing worker
copier supplies the three SQLite databases and a private ICU file. The same
worker directory receives the verified configuration and GameCore streams
and the ordered WorldCongress source. The receipt gives the fixture reference
and initial readback expected from the official capture, including its map
dimensions, occupied major slots and declared taken seats. The XP2 loaded
roster check compares the native query to those saved inputs. Taken seats
describe the save and require separate native checks for current activity.

The staged files are an offline preparation result. A selected capture
still needs admission through the native session launcher and qualification
in GameCore. Existing retained capture and replay paths keep their identities.

Current XP2 network launches bind the original prepared configuration and
GameCore stream hashes, map dimensions and declared seats in the worker
closure. The worker rederives this data from the exact verified package
before it can open the GameCore DLL. Checkpoint replacement is verified
separately after this origin check.

The compact `capture_package` format is separate from the resource relocation
package above. It stores the authenticated configuration/GameCore streams,
three final databases, ICU and the original capture manifest. An explicit
private candidate selection admits input preparation only; public capture modes
and native saved-Load admission are unchanged.

Gathering Storm uses the exact retained `xp2-lan` capture. Its parent API is
`xp2_bundle_inputs.prepare_input_handoff(destination, bundle=None)`. It reuses an
already parent-admitted raw bundle when supplied, or validates the retained raw
capture once, then writes a new private package. A new process calls
`xp2_bundle_inputs.consume_input_handoff(reference)` to rehash its compact
inputs, original save/provider, script witnesses and selection. It does not
replay the raw table capture or reconstruct configuration. The existing private
database copier and ICU copier remain responsible for per-process isolation.

XP2 accepts an identical runtime producer/consumer identity, or the one qualified
prepared package through an explicit input-only compatibility record. That
record requires the exact package/capture hashes and unchanged bytes for all
24 selected input-decoder modules. Native callback development can then reuse
the inputs; a changed decoder still requires raw revalidation. The original
producer identity is retained, and this grants no native-session or trajectory
compatibility. Unknown families, combined
legacy/explicit candidate flags, changed components, changed source witnesses,
default/public admission of an expansion package and checkpoint substitution
are refused. The existing XP1 flag remains supported for its own private scope.
This handoff does not load a GameCore DLL or establish a playable XP2 session.

The retained XP2 handoff was prepared from the complete raw capture and consumed
in a fresh, bounded process on 2 November. Compact-input verification took
1.08 seconds; the total including private database/ICU copies and their
validation was 4.15 seconds. Guards made any raw table replay fail during that
consumer check. The 39-case group and both isolated workers completed cleanly.
These are input-preparation measurements, not engine turns or parallel-game
throughput. Private evidence: `host-xp2-input-handoff.json` in the research lab.
The later script-path delivery consumed the same original package under the
explicit unchanged-decoder record, again without raw replay. Its receipt keeps
both producer identity and changed runtime module names.

## Retained local qualification

The relocated Rise and Fall LAN session used a private selection of 951 files
plus the locally rebuilt `xp1-ui` executable and its build inputs. Configure
`NetworkBackend` with `input_profile="xp1-lan"`, the exact official bundle
reference, the prepared capture's absolute path under the relocated root,
and the exported `private_resources` reference. Use a short private run root
under the relocated root's `work` directory. Build the executable directly
in the location given in [native build setup](native-build.md).

The retained one-human/one-AI capture reached the initial Python observation
in 72.8 seconds and closed with an authenticated native teardown. The worker
peaked at 329 MiB private memory. The original laboratory read guard was active.
This evidence covers the isolated load/observe/close path and the specific
capture. The private receipt is `evidence/host-xp1-relocated-rebuilt-host-native-reset.json`.
An independent action group using the same relocated setup founded a city,
selected research and a civic, and selected warrior production through the
Python client. All four commands completed and the process closed cleanly.
This group stayed on turn 1 and does not qualify turn throughput.
The same setup also accepted the offered forced end-turn command and reached
turn 2 after 16 explicit updates, then closed cleanly. That single instrumented
transition took 102.3 seconds, separate from the 72.5-second reset.

On 28 October 2026 the installed consumer completed reset, observe, an explicitly selected `found_city` action and close on the retained Base four-human hotseat capture. Public responses matched the retained reference apart from episode identity fields. The old laboratory read guard was active, the worker was reaped after its controlled close, installed source pins were retained, and no lab or Torch imports were allowed. The private package contained 1,419 files (850,557,997 bytes); it is a conservative dependency selection, not a minimized production asset set.

The qualified prepared capture retained its original producer manifest, hash and validation identity. The new consumer's own installed bytes were pinned separately. The run took 77.8 seconds including startup, validation and teardown; it does not establish throughput, cross-machine installation or any extra game capability. Source-selection failures and the earlier bounded preparation failures remain in the private lab evidence rather than being overwritten.

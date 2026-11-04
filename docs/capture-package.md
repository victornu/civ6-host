# Prepared capture package

`civ6_host.runtime.capture_package` exports a `PreparedBundle` that has already passed `native_official_bundle.read_bundle`. It does not read or admit an official bundle itself and does not launch native code. The caller supplies the exact source-manifest bytes and a JSON validation identity.

The exporter writes a new private directory only. It refuses an existing destination, verifies each admitted source while copying it in bounded chunks, and writes `manifest.json` last. The manifest is `civ6-host.prepared-capture.v1`; it includes the original capture reference exactly as held by the bundle (often lab-relative), the source-manifest hash, input profile, turn/readback/content/map identities, validation identity, external engine reference, localization bootstrap and seven file records. A relative origin reference is resolved only through the admitted bundle's absolute dependency pins; no cwd lookup is used. The official source manifest is copied byte-for-byte. The ICU path is rewritten to `icu.dat`; all other localization-bootstrap fields and the captured ICU digest are retained, with its verified byte count recorded. Place `destination` under `resource_root()/work` for the current native-localization workspace check.

The package contains configuration and GameCore streams, three worker databases, ICU data and the origin manifest. It does not contain the engine DLL, source save, or code. The engine remains an external exact-path/hash dependency. `read_package(reference)` verifies the package-manifest digest, fixed relative file paths, all local file sizes and hashes, the copied origin manifest, and the external engine. It returns `(manifest, root, verified_files)` only after all checks pass.

This package removes the need to rediscover these copied inputs through the historical lab layout. The existing loader still needs the original save reference for official validation. The package does not make the entire host independently deployable and does not establish DLC or full-game fidelity.

The format has bounded inputs: 16 MiB per JSON manifest, 2 GiB per file and 4 GiB total packaged file bytes. Exports require a new destination whose parent already exists. Failed exports leave their partial directory for inspection and return no package reference; retry with a different destination. Successful exports are never rewritten in place.

Run a read-only check with the manifest hash retained at preparation:

```powershell
python -m civ6_host.runtime.verify_capture --manifest 'C:\private\prepared\manifest.json' --sha256 '<digest-from-preparation>'
```

For a private expansion package, add its explicit `--candidate-profile xp1-lan`
or `--candidate-profile xp2-lan`. The command checks the seven packaged files
and the installed GameCore pinned in the manifest. It reports file verification
only. Runtime admission separately checks the producer identity and original
capture dependencies.

## Admission and use

The installed runtime provides `python -m civ6_host.runtime.capture_admission` with explicit `--resources`, `--official-bundle`, `--sha256`, `--input-profile` and `--destination` arguments. Run preparation in its own bounded process with `CIV6_HOST_PREPARED_CAPTURE` unset. It calls the complete original capture admission, verifies the installed source mapping, and binds the output to both the producer runtime sources and the original validators. A prepared package cannot be used to admit another package. Source identity is never rewritten to the consumer's version.

A reader normally requires the same identity. An explicitly registered earlier producer may also be read when its exact identity digest is known and all original validator-source hashes remain equal. The current compatibility entry records the retained producer wheel and its native qualification hash. The package keeps that producer identity; the current consumer code is separately pinned in the worker closure, and the worker receipt records which admission mode was used. Unknown producers or changed original validators require a new preparation. This separates an immutable prepared artifact from the code consuming it without silently upgrading either.

Pass the emitted `{path, sha256}` reference as `prepared_capture` to `LocalHotseatBackend`, together with the unchanged original `official_bundle` reference and its qualified `ui_profile`. This selects compact inputs in the existing `read_bundle`, Localization and worker-closure path. It does not select another GameCore loader. Configuration is fixed for the process; switching packages or reverting to raw capture loading requires a fresh process.

Each runtime admission checks the package manifest, all seven payload files and the external engine; it also verifies the original save/configuration/GameCore section and the retained small capture witnesses. The parent and worker pin the exact package. Prepared admission and the legacy parent Localization handoff cannot be mixed. Unknown profiles, mismatched origins, changed bytes and nonempty gameplay-script packages are refused.

The compact route currently retains historical manifest, source-save, selection, observation, script-selection and Localization-materialization references, plus the host's other ABI/proof dependencies. It therefore reduces capture traversal without yet removing the historical resource root. This intermediate format is private; official saves, streams, databases, ICU data and captured manifests must not enter the public source repository.

## LAN capture preparation

`--input-profile lan` now uses that same full capture validation and compact
package route. It requires the actual saved `GAME_MODE=LAN`, the pinned Base
engine and the original association of save, final databases and selected
gameplay sources. The capture-only profile has no historical fixture fallback.
The source save and captured stream hashes remain the input identity; a mode
descriptor is not a replacement for those hashes. INTERNET/CROSSPLAY captures
are not admitted by this change.

This admits inputs for preparation and saved-settings inspection only. The
native worker/session, AppOwnership network branch, roster/control, command
ordering and Ready/Unready lifecycle require separate admission. Do not pass a
LAN package to `LocalHotseatBackend` or treat successful package verification as
a playable simultaneous session. Unknown services continue to fail explicitly.

## Expansion script-list capture preparation

The source runtime now reuses the same bounded read-only active-list collector
for the three hash-pinned Base/XP1/XP2 engines. It is reached by the existing
`capture_phase1_bundle994` producer; there is no separate expansion database
importer or capture pipeline. The original Base source and response identities
are preserved. Unknown engines retain `unsupported_gamecore` with no state.

XP layouts are bound to private static proofs of the context constructors,
saved-Load dispatch, manager getter, list constructor/traversal/append/removal,
Game type and initialization getters. The runtime checks actual loaded code
bytes, dispatch pointers, object identities, initialized/loading flags and a
repeated read journal before reporting a header. It reads no nonempty records.
An empty current selection and empty active header constitute only an absence
witness; a nonempty list remains `nonempty_profile_unqualified`. Neither state
proves successful script execution, a particular save's load completion or an
atomic snapshot. The count is at manager `+0x20`, head at `+0x24` and tail at
`+0x28`; the tail is not a count.

The optional `core_sha256` argument of the extracted
`native_gameplay_empty.read_gameplay_state` and `source_profile` selects the
layout. Base is the unchanged default. Full official capture selects from the
actual module hash, and preserves process/selection/header joins. Its source
closure now records the actual installed Python files and source map in addition
to historical producer sources; historical identities are not rewritten.

This addition is source-runtime preparation, checked with synthetic memory and
the retained Base reader tests, plus a file-only producer pin check. No XP live
process was read or loaded for this delivery. The installed information-query
wheels predate this addition. The private proof identified by
`runtime/gameplay_active_profiles.py` must be available through the explicit
resource root. The Base-only prepared-bundle and native Load admission guards
remain unchanged. Exact official XP captures, script activation/dependencies and
expansion saved-game loading are the next separate qualifications.

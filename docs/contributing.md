# Contributing

## Source and local runtime are separate

The public source checkout contains the Python client, host adapters, docs,
examples and tests. It does not contain the private, hash-pinned game/runtime
inputs needed to run the native host. Contributors can review and improve source,
contracts, documentation and offline tests without private captures. Do not
upload the whole working directory or private workspace to GitHub; publish only
the intended source files.

The repository preserves exact source bytes with `.gitattributes`. Do not
normalize line endings in pinned native sources: source manifests authenticate
their complete contents, and automatic Windows CRLF conversion changes hashes.

The native runtime requires Windows x64, Python 3.12 x64, an installed
Civilization VI GameCore, and the exact private resources/configuration for the
selected profile. Install a local game and prepare the private resource bundle
and backend configuration separately. Use the matching selected profile and
hashes: a profile-qualified resource set does not imply compatibility with a
different GameCore build. Historical host41 build receipts describe a different
build: their 19 snapshots are directly in the receipt folder and the original
`inputs/` directory is absent. Do not fabricate that directory or edit the
historical receipt. The current XP2 build is distinct and requires its exact
matching profile and inputs.

## Install from a source checkout

From the repository root, install the portable client, then the Windows runtime
into the same Python 3.12 x64 environment. Quote paths containing spaces in
PowerShell:

```powershell
& "C:\Path With Spaces\Python312\python.exe" -m pip install -e .
& "C:\Path With Spaces\Python312\python.exe" -m pip install -e distributions\runtime
```

The project metadata allows Python 3.10+ for the client; the native runtime is
restricted to Python 3.12. The runtime install alone is not proof that private
resources are present or that the native host is ready. The resource-bundle
verifier checks the selected files and their bytes against hashes; it does not
qualify GameCore identity, ABI compatibility, or native readiness.

Set `CIV6_HOST_RESOURCE_ROOT` before importing the runtime, pointing it at the
private resource root that matches the chosen profile. Then run the existing
example with an explicit private configuration:

```powershell
$env:CIV6_HOST_RESOURCE_ROOT = "D:\Private Civ6 Resources"
& "C:\Path With Spaces\Python312\python.exe" examples\local_session.py --mode lan --config "D:\Private Configs\backend.json"
```

Use `--mode hotseat` for a configuration prepared for hotseat. The example does
not prepare a game or select choices; it acts only through the supplied
configuration. Do not commit private configurations, resource bundles,
captures, saves, credentials or local installation paths. To check the example
interface without native resources, run:

```powershell
python examples\local_session.py --help
```

## Receive the private contributor archive

The optional `tools/private_handoff.py` utility streams an explicitly selected
archive and checks every member's SHA-256. It never downloads files or starts
the game. Extract into a **new** directory; it refuses to overwrite an existing
installation and preserves exact file modification times required by historical
receipts. Keep this archive and its manifests private.

```powershell
python tools\private_handoff.py verify --archive "D:\Private Transfer\civ6-private.zip"
python tools\private_handoff.py extract --archive "D:\Private Transfer\civ6-private.zip" --destination "C:\civ6-private"
```

Follow the archive's `CONTRIBUTOR-README.txt` to select its resource root and
matching profile. A successful extraction proves transport integrity, not a
new native qualification or compatibility with every installed game version.
Do not rewrite historical hashes to make a different runtime pass.

This checkout has no Makefile: `make prepare` and `make play` commands from a
contributor's branch must be reviewed against that branch's exact revision.
Use the Python entry points documented here when working from this checkout.

## Scope and contributions

Capabilities are profile- and scenario-specific. Existing qualifications cover
only the groups and captures described in the README and API docs; they do not
mean full-game equivalence, complete action coverage, arbitrary mod/capture
support, or general multiplayer readiness. Keep new claims scoped to the exact
profile and evidence. Source and offline-test contributions are welcome without
private captures; native claims require matching, hash-pinned inputs and a
reviewable qualification.

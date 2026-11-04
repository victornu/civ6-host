# Private resource planning

civ6_host.runtime.resources verifies a native-validation.json proof, the supervisor it names, the run's sibling closure.json, and the files in that closure's pin map. Hashes are streamed, roots are explicit, and canonical resolution rejects parent traversal and symlinks that escape their declared root. The tool parses data only: it does not execute laboratory Python or copy resources. Worker exit 90 is accepted only when the validation proof records a successful close parity comparison and the supervisor records a reaped, non-timeout worker with unchanged source pins; all other nonzero exits remain blockers.

The validation proof pins the supervisor hash but does not itself pin the sibling closure. Callers must therefore supply three trust anchors: the validation SHA-256, supervisor SHA-256, and closure SHA-256. Supply the lab root and an explicit --external-root NAME=ABSOLUTE_PATH for each permitted outside root. Any other absolute path is a blocker.

Example:

    python -m civ6_host.runtime.resources --validation work/host-backend-extraction/native-validation.json --validation-sha256 <validation-sha256> --supervisor-sha256 <supervisor-sha256> --closure-sha256 <closure-sha256> --lab-root C:\private\civ6-rl-lab --external-root game_installation="C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI" --output C:\private\civ6-rl-lab\work\host-resource-extraction\plan.json

The current closure pin map mixes historical source witnesses, evidence, temporary fixture copies, old session outputs, installed host-code witnesses, installed-game files, and a user-installed mod path. The planner reports role, root and absolute-path prefix counts with unique verified byte totals, but leaves package_ready and resource_selection_complete false: a consumer/use manifest must select runtime inputs separately from proof and provenance. Proof JSON is recorded as proof data; the event stream remains referenced in the lab and is not copied.

This delivery creates no resource package. A separate reviewed relocation manifest must map historical absolute pin keys to package-relative paths while keeping the original closure, supervisor, and validation hashes immutable.

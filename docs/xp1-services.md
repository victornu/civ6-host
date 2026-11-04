# XP1 shared native services

## Current delivery — offered melee attack, native damage and independent reset

The existing Python `SessionClient` loaded the prepared T13 checkpoint, selected
its actual `unit_attack` candidate and submitted `MOVE_TO` through the official
enemy-flag route. Native before/after readbacks showed attacker damage 0→17,
visible target damage 0→40, movement 2→0 and remaining attacks 1→0. This is an
immediate combat effect, not an inference from a queued destination or lifecycle
event. No automatic CANCEL or hidden-target choice was supplied.

The first lifetime closed through native Unload/Destroy. A separate process then
loaded the same checkpoint and restored the qualified public state and offers,
with new episode identity, before closing cleanly. The grouped reviewer verified
both native ledgers against the exact executed v11 sources. Evidence:
`evidence/host-xp1-unit-attacks.json` in the private lab.

The new T13 checkpoint `2babbefa…` now has normal Load/reset evidence. The older
native31 T13 checkpoint remains distinct and refused by the normal Load path;
its additive parser review was never substituted for this new execution.

Scope: one visible adjacent-unit melee attack in this captured XP1 session.
Ranged, city, naval/air/religious, war-confirmation and hidden/empty-target routes
remain separate gaps. Historical Base readiness behavior is unchanged by this
XP1 correction. The two instrumented native lifetimes took 221.59 and 214.63 s,
with sampled private peaks of about 406–407 MiB; these include startup and checks
and do not measure production simulation throughput. No learner was used.

The same model-independent API used here is available to custom models:
read `view['decisions']['candidates']`, submit an offered candidate with
`client.act(player_id, decision_id, candidate_id)`, then read
`client.command_result` and the returned observation. Feature selection and
strategy remain outside the host. The generic `examples/local_session.py`
already exposes these operations and needs no attack-specific runner.

## Previous delivery — typed public and administrative combat inputs

The v10 source client exposes own combat-unit state, currently visible city
defenses and the partial native attack catalogue through `information('combat')`.
It applies the official displayed rounding to city defense strength. The raw
fraction remains in the native request/effect checks and a separately opted-in
administrative group with exact episode/generation/player/sequence/turn joins.
The diagnostic v9 checkpoint is compared using that fresh raw witness; it is
not rewritten as a rounded trajectory.

One real client queried both channels, forced EndTurn, made 16 explicit updates,
observed the human active and completely ready at turn 12, saved and closed
through native Unload/Destroy. The existing reviewer authenticated Load, command,
update, Save and lifetime ledgers. Evidence:
`evidence/host-xp1-combat-information.json`. This positively qualifies the named
information queries and that continuation, not a unit attack or a fresh reset
of the new checkpoint. No enemy/attack offer was reached in this group.

The successful native lifetime took 327.48 s (358.14 s including parent work),
with sampled private peak 430,358,528 bytes. The child bound is now explicitly
420 s for XP1 diagnostics; memory remains 512 MiB and Base remains 180 s.
Original 300 s receipts keep their original limits. The larger bound follows
the measured startup (~176 s to the initial reply), full update interval and
required shutdown margin; it is not a production-throughput measurement.

Prior preparer mistakes and incomplete attempts are retained: parent-wall-clock
cutoffs caused same-turn saves; then Save was requested before the human was
ready; then the 300 s limit interrupted close after readiness. The preparer now
uses the native deadline, waits for active/active-complete and stops on a
lifetime without action/turn progress. A focused orchestration test covers this
boundary. Subsequent source v11 integration and the native group above establish
the scoped positive attack/reset. The visible-city collector optimization is now
integrated; it does not broaden the qualified target-visibility scope.

## Previous delivery — native placement inventory across Save, Load and reset

Capability v8 adds `placement_inventory`, separate from the v7 `host_tracked`
progress field. The collector reads official native plot, city, district and
building queries on visible own-city plots. It does not consult host tracking
or infer completion from production progress. The old records and schemas are
preserved; historical checkpoint comparisons have an explicit version transition.

The common client placed a Holy Site at turn 11, switched to Settler production,
saved and closed. A second process loaded that exact pair, returned the same
native inventory and legal resume offer, and resumed the same district. A third
process restored the saved state and all qualified public choices. The actual
district ID was 131073, distinct from its city ID 65536. The first grouped native
attempt and its receipt review passed; no turn or training episode was added.
Evidence: `evidence/host-xp1-placement-inventory.json`.

Native lifetimes took 165.88, 157.37 and 154.91 seconds; total instrumented client
time was 536.99 seconds. Sampled private peaks were 431,783,936, 424,124,416 and
428,675,072 bytes. Each stayed within the unchanged 512 MiB / 300 s envelope,
closed through Unload/Destroy and was reaped with unchanged pinned sources.
These measurements are lifecycle instrumentation costs, not production throughput.

Native tracking is preserved in the authentic checkpoint. The reader's lack of
tracking input is established by source/fixture checks, not by claiming this
native Load had empty tracking. The positive witness is an unfinished Holy Site
with zero retained production; other categories, completion and positive-progress
intervals still require native witnesses. The v8 sources still require an updated
installed-package qualification. The next implementation group is explicit XP1
unit-attack inputs and actions through the same client.

## Previous delivery — district placement, replacement, resumption and reset

Capability v7 exposes the official placement offers and the native resumption
of districts placed through the current session. The exact XP1 capture was
continued naturally to turn 11, where three Holy Site plots became available;
no research, production or map state was fabricated to unlock them.

Through the common Python client, the native group placed the district on plot
2115, switched production to a Settler, and resumed the same unfinished district.
The placement remained present during replacement and resumption. Native
Unload/Destroy followed, and a fresh process restored the initial public state,
choices and placement tracking. All three commands were authenticated against
their native request/effect receipts. Evidence:
`evidence/host-xp1-production-placement.json`.

The group took 332.09 seconds including preparation; native processes took
152.72 and 147.72 seconds, with sampled private peaks of 427,630,592 and
427,409,408 bytes. These are instrumented lifecycle costs, not production
throughput. No turn or additional Save was performed by the action group.

Retained production was zero. Positive accumulated progress, completion,
wonder/building placements and all pre-existing untracked placements remain
unqualified. This source delivery requires an updated installed-package check;
it does not qualify complete XP1 games, XP2/mods or multi-human simultaneous play.

## Previous delivery — production queue through the shared client

Capability v6 adds the existing public queue v2 rows and the native offers for
append, remove and swap. A full queue uses the official replacement of its
eighth slot. The same BUILD serializer, native receiver, A0 events, FIFO and
publisher serve Base and XP1. One additional XP1 GetAt source profile and the
captured human queue-tab route select the shared adapter; no diagnostic flag
bypasses that admission. A stale queue is refused before submission.

The native client group founded a city, filled its queue from zero to eight,
swapped two distinct entries, replaced the eighth entry with a different offered
item and removed an entry. Every permutation was read back from Core. Eleven
queue operations and one foundation, no GameUpdate or automatic choices; two
Unload/Destroy lifetimes and a new-process reset restored the original public
state and choices. The previous checkpoint delivery remains independently valid.
Evidence: `evidence/host-xp1-production-queue.json`.

The group took 127.94 seconds including preparation; native workers took 70.94
and 43.04 seconds with sampled private peaks of 320,020,480 and 316,059,648 bytes.
These are instrumented lifecycle measurements, not production throughput.
Append remains partial for placement-required items and explicit nonstandard
formations. Production accumulation/completion over turns, new placements,
complete gameplay and multiple-human simultaneous behavior are still unqualified.
The UI capture proves the observed control route, not the source identity of
live UI bytecode. Gathering Storm copy/relink is integrated offline only.

## Continuation evidence — combat and improvement transport through turn 10

The captured session now continues from its retained turn-5 checkpoint through
active turns 6 and 7, with native Save/Unload/Destroy at both boundaries and
public observations and currently qualified choices equal after reload. The
shared combat transport uses the XP1 argument-map copy/destructor, owner predicate
and experience/promotion queries; the engine still computes combat and rewards.
Four combat records were consumed and their owned maps destroyed in the two clean
lifetimes. A fifth combat record was produced in the third process before a
separate, unqualified ImprovementChanged callback stopped it; that record's normal
cleanup is not claimed. All five experience queries returned the native
no-promotion branch. No WorldText or positive-promotion witness was obtained.

Evidence: `evidence/host-xp1-placement-attempt23.json`. A subsequent group continued
the same game from turn 7 through turn 10, with three clean saved lifetimes. Six
ImprovementChanged records and three more combat records were consumed; the
native combat copies were destroyed. Public reloads at turns 7, 8 and 9 matched,
and the turn-10 checkpoint was retained. This group ended at its preparation
budget without an unsupported native callback. Evidence:
`evidence/host-xp1-placement-attempt24.json`.

These are internal native continuation witnesses, not qualification of public
attack/build-improvement commands or district placement. No district offer was
observed yet. RouteChanged's shared query is connected and checked offline; its
native witness remains pending. Unsupported child lists, notification scopes and combat cleanup during
Unload remain explicit refusals. The run does not establish hidden-state/RNG
equivalence, complete gameplay, other content profiles or strategic readiness.

## Previous delivery — shared native Save, resume and checkpoint reset

The existing administrative checkpoint API now uses the actual retained XP1
owner and the shared configuration serializer, native Save stream, manifest and
Load path. The original official capture remains the engine/content authority;
the new component pair and its closed producer are verified separately. Each
resumed process receives distinct database and ICU copies. The original capture
and previous Base/XP1 evidence are preserved.

The client fortified and selected unit 131073, saved and closed. A second process
restored the public observation, complete currently qualified v5 catalogue and
selection, then executed the actually offered CANCEL and deselected. A third
process reset to the same saved boundary. All three completed native
Unload/Destroy and were reaped with unchanged pinned inputs. Four client inputs,
one native Save, two checkpoint Loads, no GameUpdate or automatic choice.

Evidence: `evidence/host-xp1-checkpoint.json`. Workers took 56.48, 105.89 and
101.56 seconds; sampled private peaks were 328,179,712, 417,697,792 and
411,680,768 bytes. Total including preparation was 291.42 seconds. These
instrumented lifecycle measurements are not production throughput.

An earlier attempt stopped before Load because the XP1 prelude still pinned
the configuration module before its XP2-only selector additions. The original
proof remains immutable; a full structural comparison proves its Base/XP1
branches unchanged, and the selected mirror check now runs before process
creation. A separate exact source transition retains the prepared capture's
original producer identity after two non-parsing checkpoint joins changed.

Only this untimed, active, one-human capture and qualified public fields were
compared. Arbitrary states, hidden-state/RNG equivalence, other gameplay scripts,
full expansion games and multiple-human simultaneous play remain unqualified.
The generic restored-turn join is tested offline beyond turn 1; this native
checkpoint group itself stayed at turn 1. XP2 configuration owners/codecs are
integrated and tested offline, with no XP2 Load or gameplay claim.

## Previous delivery — public unit orders and actual queue cancellation

Capability v5 joins the shared order catalogue, Lua request, native command
transport, A0/FIFO and publication to the retained saved owner. It exposes native
own activity, readiness, fortification turns and legal offers for the six reviewed
parameterless orders. XP1's official UnitPanel replacement delegates to the Base
UnitPanel; both files and the expansion metadata are pinned. Other unit orders
and the spy cancellation dialogue remain explicitly unqualified.

The public client fortified unit 131073, used the actually offered CANCEL to leave
fortification, selected it, clicked (45,26), observed queued destination 1969,
cancelled that nonempty destination and deselected. Native Unload/Destroy and a
fresh reset restored all current public states. Six client inputs delivered four
native archives, with no foundation or GameUpdate. The two workers took 53.60 s
and 43.10 s; sampled private peaks were 319,373,312 and 323,624,960 bytes. Total
including parent preparation was 110.26 s. These are instrumented lifecycle costs,
not production throughput.

Evidence: `evidence/host-xp1-unit-orders.json`. The interrupted first attempt
executed FORTIFY but the parent rejected its CANCEL offer. The second delivered
that reply, then the harness incorrectly required unavailable WAKE. Both failed
attempts, their sources and actual native effects are preserved. The successful
group uses the real offered release command; it does not modify native legality.
No healing order was offered for this selected unit. Healing over turns, complete
combat/movement, XP2, competitive content and multiple-human play remain gaps.

## Previous delivery — public world-input group

Capability v4 now joins the same saved owner to public own-unit selection,
full-grid clicks and native queued destinations. The existing official Lua route,
native command transport, publication and event FIFO remain the implementation.
Unsupported branches return a refusal, not a completed gameplay action.

The grouped native cycle selected unit 131073, moved from (42,29) to (42,28)
with moves 2 to 1, clicked its current tile (official no-op), deselected, closed
through Unload/Destroy and restored the exact initial boundary in another
process. There were four client inputs and one actual native command archive;
no foundation or GameUpdate was used by this acceptance group. The worker
durations were 51.55 s and 42.37 s, with sampled private peaks of 319,647,744 and
312,107,008 bytes. The total including parent preparation was 107.24 s.
These are instrumented lifecycle measurements, not production throughput.

Evidence: `evidence/host-xp1-world-input.json`. All queued destinations in this
witness were empty; the subsequent v5 group above separately qualifies a
nonempty queued destination and cancellation. Operation branches beyond MOVE_TO,
war confirmation, entry effects, unseen-target noninterference and complete
movement/combat remain unqualified. The prior captured turn cycle and
Base long continuations/results remain separate preserved qualifications.

## Previous delivery — captured native turn cycle

The latest addition qualifies a repeated forced-turn request while the captured
human is already inactive. Both portable client and server honor the same native
v3 offer. Actual native delivery with unchanged public controls is reported as
`submitted`, `native_turn_controls_unchanged`, with `applied_action=null`.
The transcript does not infer an acknowledgement or a global no-op. The existing
cycle then reached active turn 2 and closed/reset natively. Six explicit requests
and 16 updates completed; the two workers took 117.82 s and 43.89 s, with sampled
private peaks of 320,425,984 and 317,702,144 bytes. These remain instrumented
lifecycle timings, not production throughput. Evidence:
`evidence/host-xp1-repeated-turn.json`. The initial retry was stopped by the
portable client's old inactive-player guard before transmission; it is preserved
as a failed attempt, followed by the corrected client/server check and native cycle.

The prior first-turn delivery below remains preserved with its original proof.

The common client now executes a complete captured first-turn cycle: native
Load, foundation/research/civic/production choices, forced EndTurn, 16 explicit
GameUpdate calls, local human active at turn 2, native Unload/Destroy, then an
independent process restoring the initial observations, choices and turn gates.
Both workers exited 90 and were reaped. The full transcript, each request/update
and both lifecycle ledgers were authenticated without another engine execution.

Capability v3 exposes the source-selected human turn controls. The official
ActionPanel decision tree was also compared on 48 Lua fixture scenarios; these
are distinct from the native turn witness. Normal EndTurn and Unready were not
executed in this capture. Unready genuinely became unavailable once its sole
human finished. No network acknowledgement or other human action is invented.

The implementation reuses shared turn transport, update/publication, notification
ring and event producers. After identifying missing producer state and callbacks
revoked by XP1 initialization, the final composition now inspects 54 retained
callbacks before Load. This inspection does not qualify their semantics merely
from pointer presence. All ABI/source checks and unknown-service refusals remain.

Instrumented worker durations were 115.28 s and 42.38 s; sampled private peaks
were 322,912,256 and 318,914,560 bytes. These include startup and instrumentation,
not production throughput. Five failed attempts are preserved, with the harness,
path-length, owner-state and callback-admission causes. The run root was shortened
after reproducing the native executable's Win32 log-path limit without GameCore.

Private evidence: `evidence/host-xp1-turn-integration.json`. Complete XP1 gameplay,
long interactions/results, XP2, competitive mods, multiple-human simultaneity and
community packaging remain required. No full-fidelity or training claim is made.

## Previous delivery — shared initial choice group

The same client/session now exposes native research and civic choices plus
ordinary current-production replacement. Seven explicit commands completed in
one retained XP1 process: foundation, research selection, current civic request,
research replacement, and unit/building/unit production. The civic in this
official first-turn capture is already selected and is its only legal choice;
the native request was submitted and verified, but a different civic was not
witnessed. No choice is made by the host.

The `network-capability-decisions.v2` contract retains exact current selections
and identifies production as a partial query with its missing families. Raw
progress/cost precision is kept out of this public current-choice projection.
The original v1 contract and Base catalogues remain supported. Base and XP1 now
share the ordinary production replacement helper; the existing request,
legality, queue readback and native publication algorithms are reused.

Both processes closed through native Unload/Destroy. The fresh process restored
the initial public state and choices with a new episode/generation and private
bases. They took 60.45 s and 42.17 s with sampled private peaks of 304,898,048
and 304,730,112 bytes. These instrumented whole-session durations are not turn
throughput. Every command interval and the lifetime chain was independently
authenticated against the full retained transcript. Three failed attempts remain
preserved: two Python integration defects, then an incorrect harness assumption
about the sole initial civic. They are not counted as successful cycles.

Private evidence: `evidence/host-xp1-choice-integration.json`. This does not admit
XP1 turns, complete gameplay, a changed civic selection, or an RL campaign. The
next group is already inventoried: the shared turn transport profile is prepared;
seven callbacks in private notifications, units and improvements, plus UI turn
gates, remain before its first native turn check. No repeated unchanged
Load/foundation qualification is needed. Wheels still predate these changes.

## Previous delivery — native founder/close/reset cycle

The source runtime now exposes the exact retained XP1 capture through the same
`NetworkBackend`, `NativeNetworkSession`, `SessionClient` and network worker as
Base. A native run returned the actual local human/activity predicates, timer
projection, player observation, outcome getters and complete legal-founder
query. The client explicitly selected the offered settler; the DLL created its
city and the refreshed view showed one fewer unit and one more city. The host
then called native Unload/Destroy before sending its close reply. A fresh
process restored the same initial observation and founder catalogue with a new
episode/generation and private databases, then closed natively as well.

The two workers completed in 56.79 s and 41.72 s, with sampled private-memory
peaks of 302,292,992 and 304,967,680 bytes. All 954 pins per process remained
unchanged, both exited 90 and were reaped. These times include Load, source
verification, instrumentation and teardown; they are not turn throughput.
The existing verifier authenticates the ordered Load, postload, publication,
observation, command and lifetime intervals from these same transcripts.
Private evidence: `evidence/host-xp1-session-integration.json`.

This admits the named capability on one exact source-runtime capture. Other
action families remain explicitly unqualified, and XP1 `poll` refuses because
its native turn pump is not joined yet. No winner-bearing transition, complete
player information, same-save official command differential, multiplayer
scheduling parity, arbitrary capture/content support or complete expansion game
is claimed. Release wheels predate this integration.

The qualified Load/cache/postload/publication/UI/command/lifetime sequence now
lives in `SavedLoadOwner`, used by the existing qualifier. It retains the same
native objects and refuses phase changes, foreign owners, unrequested features
and retries after uncertain native effects. The source/build checks and private
input preparation also live in the runtime. The qualifier retains measurement,
evidence files and process supervision; it no longer owns a second copy of the
native orchestration.

The process-launch tail of the existing Base supervisor is now shared separately
from input preparation. Its algorithm is unchanged: assign the memory-limited
job before the handshake, validate the initial reply and use the existing
failure/reaper path. An explicit initial protocol hook selects XP1 result
provenance; the shared pipe, bounded reader and reaper remain unchanged.

The common session client/protocol now recognizes an explicitly partial
capability catalogue. A completed family query with no legal choices differs
from an unqualified family; the latter has no invented empty result. Existing
catalogues remain compatible. XP1 reads select the source-verified status and
unit bindings; result provenance distinguishes getter observation from an
unqualified terminal write/notification transition. No absent family or result
is replaced by constants. The earlier foundation proof below remains preserved.

## Shared command transport — first completed XP1 foundation

The existing transport now selects exact Base/XP1 addresses for native archive
copying, receive/drain and the Game facade. The same official saved owner retains
its distinct UI child, explicit command owner, recurring publication capability
and loaded lifetime. Base turn requests remain explicitly refused on XP1 until
their own source contracts are joined. No automatic action selection was added.

On the official XP1 save, native legality accepts the selected settler at
(43,29). The official UI request emits a 28-byte command; the original receive
method copies the identical bytes into its native queue. Drain now executes the
real UnitActivityChanged, feature/plot and civilization queries, District
snapshots, building-related Plot snapshots and the production codec. The latest
interval includes 287 plot-neighbor records. Drain completes, consumes unit
65536 and creates city 65536 with population 1 at (43,29), still on turn 1.
The separate native UI observation changes from two units/no city to one unit/
one city. The shared event recorder writes actual send/receive payloads.
The same worker unloads and destroys the game, releases the owned job group and
closes its services. It used 310,652,928 bytes sampled private memory in 54.86 s,
with all 946 pins unchanged, exit 90 and process reaped. These include startup,
instrumentation and teardown; they are not simulation throughput.

The unit activity matching-selector branch has run natively. The rest of the
common group reuses 35 profiled operations on nine facade types and the shared
EXE codecs/FIFO. Its 19 event kinds and 20 record types are installed, with
fixture checks for query ownership and counter transitions. This is not proof
that every kind has run in XP1. The two Plot visibility/resource wrappers were
added after XP1 emitted a notification absent from eight retained Base action
intervals. Those intervals remain a dependency inventory, not independent worlds
or a prediction of the complete XP1 event sequence. The application getter now
uses the retained XP1 body at `845600` and has returned in the native interval.
The reachable-helper audit found no remaining unselected Base native access in
the installed group. Event `0242e68c` is explicitly rejected by the old unary
shape classifier. Its real contract instead matches the existing city/scalar
codec. Three additional loyalty-related profiles (`0242e68c`, `312df0f6`,
`cf61eb26`) now reuse that codec and the source-checked empty receivers F1/F2/F3.
Only `0242e68c` was observed in this native interval; the other two have source
and fixture evidence. Notification counters remain intact; no unknown event is
silently discarded.

The original parent report rejected a valid command because it compared a full
scheduler snapshot with the raw Load transition summary. The parent now carries
the exact authenticated snapshot between phases and rejects mismatches. The
retained transcript was revalidated without another native execution: only the
parent qualifier changed, its executed version is archived, and the original
failed report remains immutable. The reviewed receipt authenticates Load,
postload, publication, observation, command/effect and native teardown separately.

Private evidence: `evidence/host-xp1-action-transport-progress.json`. Earlier
Load/player-view/shutdown qualifications remain intact. Public XP1 client
admission, complete actions/observations/turns/results/reset and other content
profiles remain pending. There is no same-save official command comparison yet,
no scheduling-equivalence claim and no admission of all human actions. The
earlier refused workers did not guess native cleanup. This completed command
does not replace their historical receipts or the earlier Base capabilities.

## Separate native player observation — 1 November

The official XP1 UI registration now runs in a distinct managed child of the
existing Lua root. It receives the original game/UI pair; no privileged gameplay
namespace is copied into the UI. The existing shared player collector reads this
child and verifies native local player/observer 0. Host admission gates remain
closed. Its outer registration return is not interpreted as proof that all
protected native subregistrations succeeded.

The same bounded session completes Load, caches, +160, +190, player observation
and ordered native shutdown. It returns 31 visible plots, two owned units, no
cities and four economy fields. Owned units, economy and the ten recorded plot
rows match the retained official capture exactly. The official capture samples
neighboring plots and is not atomic; this comparison does not establish complete
visibility, hidden-resource, fog-memory or observer-reference parity.

All 761 source/input pins remained unchanged. The worker completed in 39.81 s,
with 311,406,592 bytes sampled private peak (about 297 MiB), under 120 s/512 MiB.
UI and game children were released; native Lua reported zero live blocks after
135,898 allocations and frees. Separate Load/postload/publication/player-view/
lifetime intervals were authenticated. This remains instrumented startup and
lifecycle cost, not turns per second.

The explicit `xp1-ui` build adds one UI export while preserving Base, the prior
XP1 game binder and scheduler source. Earlier executables/receipts are retained;
the qualifier selects this build only with `--observe-player`. The changed
Python/ownership group passed 47 offline checks, followed by one focused check
after correcting a Base-only attribute assumption. The failed attempt is kept.

Private evidence: `evidence/host-xp1-player-view.json`. Next: reuse the common
command/continuation route with XP1, then admit a shared client session only when
its requested operations and observations qualify. Commands, Update, turns,
results/reset, cities/enemy interactions, installed packaging and other content
profiles remain unqualified here. The historical sections below retain their
original scope and pending statements.

## Native publication and loaded teardown — 1 November

The exact official XP1 capture now completes the shared Load/cache/+160/+190
sequence and ordered shutdown in one bounded worker. The native refresh queues
`EmergenciesUpdated` through the existing FIFO; its copied record is consumed
once. The map, turn and major-player roster remain unchanged. Both public cache
gates stay closed: this is a private candidate, not a public player session.

Shutdown releases three retained wrappers, invokes native Unload, consumes 37
already qualified A0 records, then calls native Destroy and closes the shared
services, Performance map, configuration, Lua, lock and database. The 14 district
notifications use the actual XP1 Player lookup; its native return is NULL during
Unload. The existing Base codec handles that branch. Positive item lookups remain
fixture-tested only. Detached record consumers check their exact lifetime owner
without querying freed Game/cache storage; CacheUpdate feedback and the closed
C0 route are explicitly refused at that boundary.

The parent authenticates publication and teardown separately, including the
native empty-job-list removal. All 736 source/input pins remain unchanged. The
worker completes in 38.99 seconds, with 302,272,512 bytes sampled private peak,
under 120 seconds/512 MiB; process exit follows verified native destruction.
This is instrumented startup and lifecycle cost, not turn throughput. The group
has 115 passing offline checks plus a focused receiver-boundary check. Earlier
failed attempts are retained with their actual source versions.

Private evidence: `evidence/host-xp1-publication-lifetime.json`. Public UI namespace
binding, observations/actions, Update, turns/results/reset, installed-package
refresh and other expansion/mod profiles remain to qualify. The next integration
reuses the existing shared Lua/client path. Earlier Base qualifications remain
unchanged; neither full Civ6 fidelity nor strategic training readiness is claimed.

## Combined saved Load and postload+160 — 31 October

The shared loader, native cache publication and existing postload+160 sequence
now execute together on the official XP1 capture. One bounded attempt completed
in 105.73 seconds, with 302,174,208 bytes sampled private peak, under 120 seconds
and 512 MiB. All 650 pinned inputs/sources stayed unchanged; the parent separately
authenticated the Load and postload job intervals. The child was stopped and
reaped after the result, without attempting an unqualified loaded Destroy.

The native state was pending=0, current=requested=0 before and after +160. This
qualifies the observed no-transition branch, not active Player/AutoPlay effects.
The exact six-player roster, turn 1 and 74×46 map survived the call; no scheduler
work appeared. The void-like return was ignored. No state was forced by the host.

The candidate borrows the completed cache owner's lease once and keeps both
public cache gates closed. Public XP1 admission, +190 publication, Update,
actions/turns/results/reset and loaded lifetime remain unqualified. Private
readback is not a player observation. The next delivery reuses the shared
publication/continuation pipeline; it does not repeat Load as a missing feature.
Private evidence: `evidence/host-xp1-postload-integration.json`.

The earlier sections below retain their original scope and pending statements;
this receipt supersedes only their missing combined Load/cache/+160 observation.

## Official saved-input integration — 30 October

The existing backend now completes the official GameCore Load from the exact
captured XP1 databases, configuration and 6,215,867-byte Game stream. Native
status is zero and the entire stream is consumed. Readback matches turn 1,
74×46 map, player 0, gold 5, no cities and the two captured units. Native cache
copy/publication also succeeds within the explicit candidate boundary. Public
XP1 sessions remain closed pending postload and lifetime qualification.

The prepared package preserves its original preparation identity. Native-only
wiring changes rehash the prepared files and unchanged input parsers instead of
repeating the 46,159-entry raw dependency validation. Historical Base and XP1
diagnostic input pins remain unchanged.

The observed empty gameplay selection retains the standard library's explicit
include error; no fake source file or successful empty loader is installed.
Seven existing logger callbacks are activated together after Prepare using
their EXE contracts and XP1 caller evidence. The actual Load now registers
GameEffects.log and reads its level through that shared registry.

The shared content-capability service completes 1,564 queries: 92 capabilities
for 17 active IDs (0–14, 62, 63), with all 64 configuration providers retained.
Immutable source metadata is retained within its verified owner; live native
values remain queried. The existing native Performance map owns the official
Startup-recorded 5/5/5 values; actual unit/trade consumers read 5 through its
strict interface. The startup log is temporally associated with the captured
process, not an atomic map dump; automatic hardware derivation is not reproduced.

The successful worker finished in 103.40 seconds with 304,877,568 bytes sampled
private peak under explicit 120-second/512-MiB bounds. Earlier 45/60-second
attempts timed out during continuing startup/Load and remain preserved. The
parent verifies all 620 source/input pins and authenticates the native Load job
ledger: one empty list was created, no work remained outstanding. Raw Load and
job snapshots consumed 62.56 seconds and 3,287,984 stream calls. These include
Python transport and verification costs; no simulation throughput or exact cost
attribution is claimed.

Postload+160, loaded-game destruction, continuation/actions/results/reset and
public session admission remain unqualified. The worker was stopped and reaped
without guessing loaded destruction. Civ6 remains closed; no training started.
Private evidence: `evidence/host-xp1-saved-load-integration.json`.

The sections below retain earlier qualifications and their original limits;
their earlier pending raw-Load/cache statements are superseded by this result.

## Postload event transport — 30 October

The shared event owner now dispatches XP1's category-2 NULL-argument
AutoPlayStart/AutoPlayEnd callbacks through real HKS. The official wrapper owns
its conditional execution-lock release/reacquire; the adapter does not simulate
that sequence. The new executable preserves the previous notification component
and records an exact build/source association; earlier executable pins remain.

One bounded native group passed in 9.71 seconds (sampled private peak
189,677,568 bytes, 45-second/512-MiB limit, child reaped). It exercised 16 wrapper
calls, seven protected Lua errors, five direct C refusals and the legacy
category-1 entry. The Lua registry identity, stack, script lock and four observed
AutoPlay globals were restored/unchanged. These were explicit diagnostic Lua
tables, not official gameplay listeners. Unknown service calls remain fatal.

The 44 retained offline checks were not repeated. One targeted source-build
association check was added after an initial refusal before the group ran.
Private receipt: `evidence/host-xp1-postload-events.json`.

This qualifies the event transport, not the outer+160 transition or a loaded
XP1 game. The captured Load, real scheduler, populated caches, gameplay listeners
and loaded-game destruction still need their combined native qualification.


## Official captured inputs and nested notifications — 30 October

The shared raw reader accepts the exact XP1 LAN capture after checking its save, configuration, database, Localization, content and before/after identities. This is input admission only; native saved-Load and prepared-cache admission remain closed.

The XP1 DB witness reader uses a bounded 16-MiB manifest allowance, matching the
existing materializer. The actual two manifests are 4,244,500 and 4,244,499 bytes;
the old 4-MiB limit refused them. A targeted retained-file check covers accepted
bytes and rejected oversized/hash-altered files. Base keeps its existing bound.
Full raw XP1 input validation then completed in 196.81 seconds.

The official reference is a turn-one Rise and Fall LAN game with one human,
five AI majors and nine city-states (Small Pangaea, Online). The same process
produced the save and matching final databases. The capture completed in
3,494 seconds; this includes live reference export and is not a headless speed
measurement. The game is closed and both temporary mod toggles are restored.
No official assets are included in the distributable host.

`A0FamilyService.enable_notification_scopes()` now explicitly enables nine
source-bound event kinds on the existing queue owner. Unknown kinds, controller
and player-query events in those scopes remain refused. The service preserves
uint32 counters, record flags, sequence/append invariants, FIFO and quarantine;
scope exit does not implicitly drain the queue. ResourceRemoved retains only
the source-qualified two-field variant in nonzero scopes.

The 89-case offline group passed. One bounded native group executed three kinds
(map yields, civic boost, tech boost) across three nested-scope states, using
real native argument maps, constructors/setters/destructors and Core scope
callbacks. All nine records retained flags 0/4, exact payloads and FIFO order;
guards, owners and callback restoration passed. Duration 17.40 s; sampled
private peak 243,920,896 bytes under 45 s/512 MiB, with the child reaped.
The six pointer-shaped kinds and N=0/M>0 have source/offline coverage only.
This does not qualify natural publication in a loaded game or public visibility.

Private receipts: `evidence/host-xp1-official-capture.json` and
`evidence/host-xp1-notification-scopes.json`. The source-derived postload +160
candidate retains its loaded-cache prerequisites; AUX90 transport is qualified
above. Earlier prepared-service and Base proofs below
remain valid within their recorded scopes; the capture dependency is now
available rather than absent.

## Player/Treasury notification lease

`SavedLoadServices.install_player_queries(core_lock=...)` requires the existing
`NativeCoreLock` bound to this host. `consumer.enable_player_queries(owner)`
connects the owner to the existing A0 TreasuryChanged branch (`20F2116E`, C1).
Base still uses the original query arguments and call sequence. XP1 selects
its 15 source-pinned constants through the same context manager and typed
native calls, rather than a separate implementation of the producer.

The official Player lookup receives the complete uint32 argument. A real NULL
result remains NULL and produces no C1 record. On the positive path, the native
getter at +18 executes before +10, both returning their output pointer and
uint32 values. The caller enqueues while the Player/component leases remain
live; the component releases before Player. Native Player construction/release
acquires/releases the host execution lock. Treasury arithmetic remains wholly
native, including the aggregate calculation behind +10.

XP1's Treasury member is Player+560, versus +4F0 in Base. A wrapper pointer alone
does not prove the member is valid. Before getters, the adapter requires the
native live branch, a NULL cache branch, initial reference count one, and a
nonnull component live pointer equal to the actual Player member. The original
bounded reader is preserved with reads of eight bytes or fewer. The owner is
bound to one native thread/context/host lock and refuses replaced callbacks,
reentrancy, early close and replay after uncertain effects.

The source proof verifies 3,306 instructions and twelve vtable pairs. Ninety-six
relevant offline cases passed, covering positive copied values, enqueue before
release, NULLs, bit preservation, invalid owners/slots and failure cleanup.
Those positive cases are fixtures, not evidence of a loaded XP1 player.

The native group called official XP1 wrappers for seven uint32 values and
observed every actual outer+B8 call. The real prepared Game was uninitialized;
all seven calls returned NULL before loaded-player table access, and no C1
record was manufactured. Guards/registry were unchanged, the execution lock
was unowned afterward, callbacks were restored and Core/Lua cleanup completed.
The run took 10.48 seconds with 241,332,224 sampled private bytes, within the
45-second/512-MiB bounds. This is service qualification, not turn throughput.

Receipt: `evidence/host-xp1-player-notifications.json`. Positive getter effects,
native positive enqueue/release, public visibility and full saved-game loading
remain pending on an exactly associated official expansion bundle. The uint32
transport probe does not claim execution of the later loaded index-table guard.

## Shared cache-facade lifetime

`SavedLoadServices.install_cache_facades()` acquires the official outer A0/B0/D0
facades using the existing `NativeUiCacheFacades` and typed backend. The same
copy, result replacement and release sequence now selects explicit Base/XP1
ABI profiles. Base defaults are preserved. XP1 checks the actual context,
global service, cache owner, member and reference-counted wrapper identities;
it neither constructs a second Game nor synthesizes cached values. A replaced
owner or uncertain native effect quarantines the service.

`copy_cached_metadata()` calls the official E8 copier and acquires/replaces B0/C0
result references. It preserves the native 28-byte output and returned DWORD.
This is internal prepared metadata, not a public player observation. The native
constructor initializes only two bytes of the final DWORD; the remaining bytes
are copied as returned rather than normalized. Canary checks bound the write.
The retained Game getter borrows the same Game facade. All wrappers close before
the borrowed Core owner; the borrowed root is never released by this service.

Full XP1 `refresh()` and the typed backend publication call both explicitly
refuse. The publication body requires loaded Game services whose complete
dependencies are not yet qualified. A nonzero Game initialization flag alone
does not prove those services exist. This guard is not a replacement for a
future loaded-game publication implementation.

One bounded native group acquired all five wrappers, copied the actual source
bytes twice, replaced both result references, read the real Game getter and
released seven references including the replaced results. The three initial
wrapper addresses and all borrowed owner identities were verified. The public
gate stayed closed; Core Destroy and Lua cleanup completed. The run took 17.52
seconds with 184,004,608 sampled private bytes under 45 seconds/512 MiB. These
are instrumented service costs, not game-turn throughput. Thirty-seven relevant
offline tests passed, with two identity guards rechecked after their final edit.
The immutable runtime archive contains 551 pinned files.

Receipt: `evidence/host-xp1-cache-facades.json`. The prepared native DWORD happened
to be zero and the retained getter returned -1; neither is supplied as a fallback
or labeled as a player identity. Populated Player/cache queries, their A0 event
branches, the exact official expansion bundle and complete saved Load remain
separate qualification work. This delivery does not establish XP1 gameplay,
XP2/mod compatibility or readiness for strategic training.

## Shared controller effects in A0 events

After installing the ordinary A0 consumer, call
`consumer.enable_controller_events(control_inputs)` with the existing
`ControlInputService` from the same service owner. This explicitly adds
TurnBegin (`21535587`, record 4) and PlayerTurnActivated (`8953F126`, record 15).
It borrows exactly the controller already shared by HOST120 and the deferred
queue. Installation neither constructs a second controller nor resets its state.
Pending work, a foreign/replaced owner and duplicate installation are refused.
The controller cannot close while the event consumer still borrows it.

Both branches reuse the existing dispatcher. TurnBegin resets the original
native controller flag and clears manager bit 6 before enqueue, then records
the turn value after enqueue. PlayerTurnActivated enqueues first, then resets
the same native flag; it preserves manager state and turn telemetry. The
source-scoped manager/telemetry adapter remains distinct from the native
controller object. Its 32,768-value diagnostic limit refuses overflow before
mutation. It is not a game turn limit or a reproduction of the complete EXE
telemetry ring, bank rotation, scheduler or clocks. The source allocator's
saturation branch is recorded rather than replaced with simulated success.

The `a0_control` native group used official XP1 wrappers for four alternating
events. Observations around the unchanged enqueue confirmed the different
effect orders, lazy construction, one native object and the same flag returned
by HOST120. Original setter calls supplied a diagnostic nonzero flag between
events; no Game field or Core registry was patched. FIFO consumption, unchanged
Session/Load guards, callback restoration, controller/code release, native
Destroy and Lua cleanup passed. The group took 9.65 seconds with 237,244,416
sampled private bytes under 45 seconds/512 MiB. Eighty-six relevant offline
cases passed; the preceding 73-scalar-case native group was not repeated.

Receipt: `evidence/host-xp1-a0-controller.json`. The record-15 UnitPanel metadata
observer remains internal: this does not admit XP1 player actions or visibility.
The probe used prepared services with the two actual Core subscriber entries
absent. Natural event publication, a complete loaded XP1 game and the full
controller/simultaneous scheduler still require their own qualification.

## Shared A0 event families

The argument owner exposes `install_consumers(receiver_state=...,
pre_turn_immediate_state=..., entity_listener_count=0)`. Both receiver profiles
are explicit source-qualified states. The installed owner reuses the existing
Base dispatcher and its two pure producer helpers; it does not construct the
Base host, provide guessed Core addresses or duplicate event codecs.

The pinned dependency closure admits 156 keys, 76 source branches and 143 record
types. Every branch sharing an admitted key must be independent of native-query
ABIs. The queue, sequence and actual notification counters belong to the shared
deferred owner. This first group requires both counters to be exactly zero;
nonzero scopes are refused, never reset. Native Game/Player/cache queries,
controller transitions and private ring paths remain separately unqualified.
Product-only additions outside the reviewed source manifest are not inherited
implicitly. Receiver/listener/registry changes fail rather than discarding work.

Pointed-to data is consumed synchronously while the argument map remains valid;
the existing codecs retain all shape and lifetime checks. The pre-turn immediate
receiver has a separate explicit profile and does not consume its future queued
record. The original empty presentation consumer retains validation before
commit, ordered consumption and quarantine after uncertain failures. These
records are internal transport, not automatically player-visible observations.

The bounded `a0` native group called the official two/three-field XP1 wrappers
for 73 cases across 48 scalar keys. All cases preserved native unsigned values,
boolean conversion and the source default for a missing second field. All 73
records were consumed in sequence; the Core registry and Session/Load guards
were unchanged. A0 was restored, the consumer closed, and native Destroy/Lua
cleanup completed with zero live Lua blocks. The group took 11.29 seconds with
234,942,464 sampled private bytes, under the unchanged 45-second/512-MiB bounds.
The 146 relevant offline cases passed in two groups; the initial fixture-loader
failure and first native journal-limit failure remain recorded. The latter was
not replayed: a fresh process used a 512-entry diagnostic ledger instead of the
old 256-entry Init ledger, retaining the 512-KiB byte limit.

Evidence: `evidence/host-xp1-a0-families.json`. The remaining 108 admitted keys
have source-level reuse admission, not native shape-by-shape qualification.
Natural loaded-game publication, interactions with populated caches, a complete
XP1 saved Load, XP2 and mod compatibility are still unqualified. These timings
are service qualification costs, not game-turn throughput.

## Retained Game getter and C0 status notifications

`SavedLoadServices.install_status_messages(...)` requires the shared argument
owner and an explicit source-qualified empty presentation receiver profile.
It acquires one real Game facade through the official outer +A0 factory. The
facade borrows the cache owned by Core's service; no cache field is synthesized,
published or patched. The shared retained getter calls the native +128 slot
and preserves its signed DWORD. Identity is rechecked against the current Core
service on each use. A cleared/replaced service or expired context refuses.

The existing C0 consumer compares that getter before reading the argument map.
For a matching target it copies the native UTF-8 text while it is still valid,
then enqueues the source-defined record. The FIFO's existing empty presentation
consumer is shared with Base and preserves validation and commit order. This
status-only profile admits StatusMessage and existing CacheUpdate; the separately
installed A0 owner adds its source-qualified families. Unknown record kinds
remain refused. Nonempty presentation subscribers and optional hooks are not
silently ignored. This internal record does not establish public visibility.

The `status` group exercised the real factory/getter, a mismatched target with
a NULL argument, then both official C0 wrappers with a real Localization::String.
Two records preserved text, defaults and explicit unsigned fields; both were
consumed in sequence. Callback restoration, native facade Release, Core Destroy
and Lua cleanup completed. The prepared cache returned its native -1 value;
this is not an inferred local player. The passing isolated group took 9.04 s,
sampled 232,345,600 private bytes and stayed within 45 s/512 MiB. Ninety-seven
grouped offline cases passed. A first group stopped on a diagnostic telemetry
name collision after native publication; it was quarantined, never resumed, and
replaced by a fresh process after reusing the existing telemetry adapter.
Evidence: `evidence/host-xp1-status-messages.json`.

The lease closes before its borrowed cache is destroyed. Its use during a loaded
game still needs the loaded-Game lifecycle and population boundary; this receipt
does not admit all Load/Destroy interleavings, public cache observations, natural
gameplay messages, complete XP1 saved Load, XP2 or mod compatibility.

## Borrowed event maps and absent scalar callbacks

`SavedLoadServices.install_event_arguments(normalizer_transform=None,
dynamic_registrations=())` borrows the existing deferred owner and installs A0.
It reuses the Base tree traversal, now selecting a hash-bound XP1 ABI, and the
existing EXE absent-scalar consumer. Only its verified one/two/three scalar
shapes are admitted when the event is absent from the fixed EXE registry.
Without the optional A0 family owner above, registered callbacks fail explicitly.
Other shapes and unknown transformations remain refused.
Core's preceding internal event dispatch is preserved; no generic success stub
or blanket suppression during Load is installed.

The reader copies 24-byte variant headers synchronously while the native map
exists. Pointer-bearing values remain borrowed; this is not a deep copy of
strings or nested maps. Per-event consumers must handle those lifetimes.
The field budget is a resource limit, not a native gameplay rule. The owner
checks thread, recursion and callback identity, quarantines uncertain failures,
and closes before the deferred owner after pending work/scopes are empty.

One bounded `arguments` group read a seven-field native map, then called official
XP1 two/three-field wrappers. Both temporary maps reached A0 with exact scalar
bits, including 0x80000000 and 0xffffffff. Their guards stayed unchanged;
Prepare had created the real Session. Callback restoration, reader close,
native Destroy and Lua cleanup completed. The group took 8.85 seconds with
202,489,856 sampled private bytes; 94 grouped offline cases passed.
Private evidence: `evidence/host-xp1-event-arguments.json`.

C0 uses the retained getter described above. Registered A0 consumers now have the
grouped boundary above; natural loaded-game event effects and the exact official
expansion bundle remain unqualified. This is service transport, not an XP1 game
or throughput benchmark.

## Explicit local identity and the shared native controller

`SavedLoadServices.install_control_inputs(local_player_id=...)` composes the
existing HOST D0 local-ID callback and the original EXE controller code already
used by Base. It requires the same deferred owner and an explicit identity;
it does not select the first human or install a default player 0. The controller
getter is extracted into a shared mixin without changing the Base body. The
original constructor, clock/critical-section dependencies and unsigned-byte
getter/setter remain owned by `NativeControllerCode`/`NativeControllerTurnState`.

No second controller state, scalar-zero projection or new scheduler is added.
The controller is created lazily on its first getter call. Turn-event adapters
must use this same state. Callback ownership, native thread, pending events and
notification scopes constrain close. Control inputs close before the borrowed
deferred service; the object closes before its code and unwind registrations.
Failed native reads poison the owner instead of silently resetting it.

The source-qualified XP1 Load branch calls D0 except where native world-builder
or hotseat rules bypass it. The host supplies application identity only; the
Core still validates player mapping and decides selection. HOST120's PlayerID
argument is ignored by the original EXE getter. Its XP1 Game/Player caller needs
a live Game and is deliberately not invoked on a merely prepared context.

The `control` stage of the existing qualifier exercised D0/120 through native
function pointers in the composed XP1 service owner. Explicit identity 7 was
returned unchanged. Exactly one original controller was constructed; original
getter results were 0/1/165/0 after diagnostic setter calls, without recreation
or dependence on EDX. Both callbacks were restored and controller storage/code
released before the prepared-context teardown. Native Destroy and Lua shutdown
completed; 118,652 Lua allocations/frees and zero live blocks were reported.
The group took 10.07 seconds, sampled 197,275,648 private bytes, and remained in
the 45-second/512-MiB job. Sixty-seven grouped offline cases passed. Receipt:
`evidence/host-xp1-control-inputs.json`.

This does not prove that player 7 exists in a real save, full controller/scheduler
lifecycle, native turn-event updates, timer/reactivation behavior or simultaneous
play. No loaded-Game memory was patched and no full executable was launched.
The original Base prepared-load route is still separately scoped; this service
does not silently broaden its fixed-capture assumptions. Full XP1 Load still
needs the remaining event/reader/lifecycle boundary and exact official inputs.

## CacheUpdate feedback and notification scopes

`SavedLoadServices.install_deferred_events()` installs the shared HOST B0/E8/F0
service. The extractor moves the existing Base FIFO producers, counters and
CacheUpdate consumer into one shared mixin; Base retains the same algorithms.
XP1 selects its own source-bound outer dispatch and native subscriber registry.
The service does not install a fake empty registry or discard feedback as a
presentation event. Optional EXE preprocessing/queue-metadata services must be
explicitly absent under this profile; non-NULL alternatives are refused.

Records remain pending until the native consumer returns. A callback may enqueue
later records; recursive drains, replaced callbacks, foreign threads, malformed
records and unknown kinds refuse. An uncertain native failure poisons the queue
and forbids replay. Close requires no pending work or open notification scope,
then restores callback pointers and their ownership metadata. The composed
owner's existing loaded-Game teardown guard remains in force.

One `--stage deferred` group in the existing qualifier registered a diagnostic
subscriber through the official XP1 registrar, then delivered three records via
outer +198. The first callback queued the third record. The native subscriber
received exact unsigned DWORD values in FIFO order, and no record replayed.
Official notification Begin/End wrappers produced nested depths 0/1/2/1/0 and
the shared EXE counters, including the native empty-stack no-callback path.
The callback slots were restored, context Destroy completed and the diagnostic
registry entry was absent afterward without manually clearing the registry.
Diagnostic callback storage was retained through process exit.

This group passed in 10.38 seconds in the existing 45-second/512-MiB isolated job;
46 grouped offline cases passed, including retained Base regressions. No full
game was launched. Private receipt: `evidence/host-xp1-deferred-services.json`.

The diagnostic feeds packed scalar identifiers through HOST B0; it does **not**
create gameplay snapshots or prove their release. Natural publishers, loaded
Game subscribers/scheduling/destruction, other A0/C0/controller event families,
the complete script bootstrap and an exact official expansion bundle remain
outside this admission. Static A0/C0 Load suppression is not permission for a
host blanket drop. Full XP1 saved Load is still explicitly refused. These times
are service qualification costs, not actual-game throughput measurements.

## Application configuration notifications through the saved-service owner

`SavedLoadServices.install_application_mirror()` now retains the existing
application mirror for the XP1 configuration owner. The extraction shares the
Base snapshot, prelude, variant copy and dispatch algorithms using explicit
engine profiles; it introduces no second provider clone. The fresh player
record path uses the already-qualified indexed configuration reader. Base
defaults and historical receipts remain intact.

The XP1 selector `LAST_TURN_PHASE_TYPE`, temporary argument map, property lookup,
variant assignment, allocation and prelude primitives are source-bound. Missing
arguments and missing provider properties have distinct native semantics. The
implementation preserves the closed NULL-observer profile, type/ownership
guards, owner thread, stable snapshots and fatal failure policy. It restores
HOST130 and its slot metadata on close, refusing unconsumed player notifications.

One `--stage application` group in the existing qualifier called the official
XP1 publisher three times through the composed owner. With no destination cell,
the first publication left B unchanged. Two subsequent publications copied the
native phase value into an existing B cell without a player journal. The first
prelude made 194 expected insertions, including 64 owned MAP_PINS maps; the next
two made no new insertions or allocations. Callback restoration, context Destroy
and Lua shutdown completed; Lua reported zero live blocks.

The group passed in 33.12 seconds, with 186,376,192 bytes sampled private memory
and 186,421,248 bytes peak commit. The isolated 45-second/512-MiB job and 2-GiB
reserve remained in force. Seventy-one offline cases passed, including retained
Base behavior on the extracted implementation. No full game was launched.
Private receipt: `evidence/host-xp1-application-mirror.json`.

This duration includes deep validation and is **not a gameplay throughput
measurement**. These were explicit publisher calls, not a natural phase change
inside a loaded XP1 game. Player notification publication/journal consumption,
active observers, opaque recursive values, full EXE bootstrap and loaded-Game
shutdown remain outside the native group. The shared GAME path still admits
only the source-qualified phase property and requires a present source cell.
Core CacheUpdate/deferred dispatch and an exact official expansion input bundle
remain necessary before actual saved Load admission.

## Native-owned map event arguments

The shared service now optionally admits payload+10 for XP1 kind2 tree maps.
It delegates value copying to the official constructor/assignment/destructor,
retains guarded outer storage until payload release, and preserves the borrowed
name resolver. It does not snapshot named keys at append. At dispatch, the
existing bounded A8 decoder supplies the existing protected C map pusher.
The C transport has an explicit new export; scalar-only exports retain their
ABI and reject map tags. Older executable profiles still point to their retained
event transport source and executable identity.

Nested maps use the same tree reader and emitter, their own current resolver,
shared budgets and cycle/depth guards. This is explicit V2 admission; the legacy
default still refuses nested-map tags. Copy preflight additionally bounds native
`size * count` buffer extents, which differ from the A8 display width. Native
process/job limits remain necessary. Unknown map kinds, variant representations
and reserved array-key maps still refuse rather than substitute a result.

The `event_maps` stage of the existing qualifier executed four official XP1
Call/TestAll wrappers, with Core ownership initially free and held. Each payload
mixed an integer, a copied configuration tree, a boolean and an empty map. All
66 child configuration maps were distinct from the source. A native setter
then changed the source player's value from 0 to 19 before dispatch; Lua still
received the copied zero, together with the nested values and Unicode strings.
The empty map remained a table. Eight map copies were released with their
payloads, slots restored, and the factory closed without live owners.

One isolated native worker passed in 7.94 seconds, with a sampled private/peak
commit maximum of 159,809,536 bytes, exit zero and complete teardown. Lua closed
with zero live blocks; originals and private input databases stayed unchanged.
The 45-second/512-MiB limits and 2-GiB reserve were retained. Fifty-six grouped
offline cases passed after correcting a local-variable collision in the new
recursive emitter. One later targeted compatibility check preserves scalar
evidence from single-pass iterables; its tuple normalization does not change the
native payload path, which already supplies tuples. Executed and final source
identities are recorded separately; no unchanged native rerun was made.

These were real wrappers with diagnostic listeners and configuration data,
**not natural gameplay events or saved-game loading**. Runtime mutation of the
borrowed resolver and a null nested-map source were not tested natively. Source
shows that native copying materializes a null map child as an empty owned map;
direct A8 on a null child instead yields nil. The decoder preserves that
distinction and does not replace the native copy. Full Load, exact official
inputs and gameplay/content qualification remain outstanding. Private receipt:
`evidence/host-xp1-script-map-arguments.json`.

## Shared synchronous GameEvents

`ScriptEventService` owns AUX40/48/60/80 and composes the retained argument
factory and protected HKS dispatcher. The extraction moves the original
Call/TestAll method bodies into a shared mixin; the Base prefix inherits the
same methods. Creating this service does not construct a map or run the large
NewGame diagnostic prefix. It enforces one owner/thread, refuses closure with
live payloads or an active dispatch, and restores previous slots, callback
metadata and callback roots on close. Unsupported payload methods still refuse.

The existing qualifier adds `--stage events`. It verifies the installed XP1
image, source-bound wrapper bytes and host/AUX globals, then invokes official
wrappers 20CD0/20DF0 with explicit diagnostic listener names. These wrappers
need the live host, arguments and HKS runtime, but no manufactured game entities.
The existing native Core lock is retained through context destruction.

Twenty native wrapper calls cover nil, false, true and numeric zero results,
signed DWORDs and mixed boolean/integer arguments. The raw boolean byte 255
becomes true; numeric zero stays a number. Both Call and TestAll are exercised
with the Core lock initially free and owned. All Lua dispatches observed the
lock released, and the original ownership was restored on return. Call clears
the output for nil; TestAll preserves its initial byte 0xA5. False is distinct
from nil. Every payload was released and all four AUX slots restored.

The successful worker completed in 7.04 seconds, with 151,994,368 sampled private
bytes and 154,042,368 peak commit bytes. It exited zero, was reaped, and closed
the Lua runtime with zero live blocks before closing the Core lock and databases.
The 45-second/512-MiB/private-input containment was unchanged. A prior worker
stopped at the first callback because the diagnostic ledger reserved the same
`event_name` keyword as the callback payload. Only the qualifier's telemetry
adapter was corrected: lifecycle and gameplay names are now retained separately.
That failed run and its exact sources remain recorded; no uncertain process was
reused. Fourteen grouped offline cases and one targeted telemetry regression pass.

**Limits:** this is a native wrapper/service diagnostic with synthetic listeners,
not a natural gameplay event or a loaded expansion game. The source inventory
identifies XP1 publishers that append a ParameterMap through payload+10; the
later group above adds that explicit kind2 profile. Other argument types, complete gameplay scripts,
the remaining Load prefix and an exact official XP1 input bundle still need
qualification. No public observation/action admission or learner changed.
Private evidence: `evidence/host-xp1-script-events.json`.

## Shared A8/B0 parameter maps

The existing bounded qualifier adds `--stage maps`. The common map snapshotter
selects the exact Base/XP1 provider layout; no independent XP1 decoder is copied.
The original Base engine and transport version remain defaults. XP2 and unknown
profiles refuse. Before XP1 callback installation, loaded function bytes and
provider slots are compared with the pinned static proof.

`MapService` owns the A8/B0 bindings without constructing the old NewGame prefix.
It restores prior callbacks and removes the snapshot callback before teardown.
The current C export negotiates transport version 2, adding nil values and the
same source-derived UTF-16 projection used by the scalar service. Older hosts
retain version 1; extended values are never silently sent to them. Existing tree
validation, checked reads, snapshot stability and resource limits remain.

A single native group passed in 7.86 seconds with sampled peak private memory
156,499,968 bytes and zero remaining Lua heap blocks. The real official
`Game.GetProperties()` callback reached A8 with names enabled on its prepared
empty services map. Four filled native configuration maps then passed the
existing protected C diagnostic. This second path verifies copied real provider
values through the transport, not another GameCore callback. Optional B0 returns
nil for native count zero and a table for a native count of one whose value is
nil. This distinction follows the original native count, not Lua cardinality.
Forty-two grouped offline cases cover the changed decoder, source/version
refusals and the retained Base decoder behavior; no unchanged Base game reran.

The evidence is `evidence/host-xp1-parameter-maps.json` in private resources.
Nonempty native name resolution, broader XP1 gameplay arrays/lists/descriptors,
remaining Load script/event services and the exact official bundle are still
unqualified. This group did not load a Game save, qualify public observations,
or measure game throughput. The current executable is not automatically
substituted into retained Base sessions.


## Retained group: official configuration Lua readback

The shared bounded qualifier now accepts `--stage values`. It restores B,
prepares XP1, applies the existing B-to-A copy, then calls the official
`GameConfiguration.GetValue` and `MapConfiguration.GetValue` callbacks through
the native AUX+A0 service. A small owned scalar-service binding is independent
of the large NewGame diagnostic prefix; its previous callback is restored before
teardown. The source-bound GetValue caller bodies and provider dispatch are
checked in the loaded XP1 module before these calls.

Eleven cases and 22 Lua assertions passed: signed integer/hash values, UTF-16,
string and signed numeric keys, missing keys, empty strings, paired/isolated
surrogates, and the official converter's complete-codepoint prefix at its
1,023-byte payload limit. The official setter normalizes an empty UTF-16 string
to a null tagged payload, observed as Lua nil. PlayerConfigurations has named
instance getters, not a generic GetValue; no such method is invented here.

The new shared C conversion is compiled in the separate `xp1-current` source
profile. The retained Base/XP1 profiles preserve their exact source/executable
bytes. One first attempt stopped before Lua because the qualifier incorrectly
required non-null storage for an empty string; static setter analysis corrected
the expectation. Both isolated attempts were reaped. The successful cycle took
7.63 seconds, with sampled peak private memory 154,484,736 bytes, 141 events and
zero live Lua heap blocks after destruction. Ten grouped offline checks passed.

This remains a configuration/service qualification on candidate databases with
explicit synthetic properties. Extended conversion cases intentionally modify
private configuration A. It is not a loaded XP1 saved game, public player
observation qualification, simulation throughput or full expansion readiness.
A8/B0 map marshalling, remaining Load/event callbacks, gameplay Tuner absence and
an exactly associated official save/content/script bundle remain to qualify.
Evidence is retained privately as `evidence/host-xp1-configuration-lua.json`.


The common runtime now selects the retained XP1 Lua API binder by exact GameCore
hash. It verifies the actual engine, code, interface and registration owner before
calling the official protected registration routine. Base keeps its prior targets;
XP2, unknown images and an executable without the XP1 export are refused.

The shared context-only Prepare path composes the existing type registry,
archive access/registration and localization adapters. It does not reconstruct
game rules, create a map or admit an expansion to the saved-game backend.

One bounded native execution has qualified this group:

- Common XP1 Init, Prepare and official Lua API registration.
- Actual borrowed database and localization calls through Lua.
- Fifteen archive registrations/removals and ten type registrations/removals.
- Script service unbinding, context destruction, Lua heap closure with zero live
  blocks, localization shutdown and database shutdown.

That execution took 7.55 seconds; sampled private memory peaked at 149,626,880
bytes and recorded peak commit at 151,797,760 bytes. The child had a 45-second,
512-MiB limit, a kill-on-close Windows Job and private input copies. These are
**service diagnostic costs**, not game throughput or parallel-instance capacity.

The existing qualification entry point selects this group explicitly:

```powershell
python tools/qualify_xp1_configuration.py --stage scripts
```

It needs the documented private resource layout and matching game installation.
The configuration stage remains separate; the scripts stage does not repeat its
typed-value roundtrip. No full-game executable or learner is started.

The diagnostic explicitly returns NULL for the named `GameCore_Tuner` request.
The engine's acquisition and local cleanup paths are source-proven to guard this
value. Native Prepare/Destroy completion is now observed for this case. Whether
Tuner absence is safe throughout Load and gameplay remains unproved. Ordinary
preparation still refuses this absence unless the diagnostic is explicitly
selected; saved Load admission remains unchanged and refuses XP1.

The original supervisor rejected an additional native empty-job telemetry line,
although its child completed successfully. The existing strict telemetry parser
from the retained Prepare runner was reused to validate both records. The original
report, executed source fingerprint and corrected review are retained separately;
the engine was not run again to fix this reader. Unknown telemetry, nonempty job
members, duplicate JSON keys and extra records are refused.

Remaining work includes the complete Load prefix and gameplay script services,
an exactly associated official save/configuration/final-database/content bundle,
and native gameplay qualification. The diagnostic neither proves expansion
compatibility nor full game fidelity. The existing Base game receipts are intact.

## Applying restored configuration

The shared `NativeLoadBackend.copy_b_to_a` method now carries the selected engine
through both the provider snapshot and the indexed player snapshot. For XP1 it
checks the source-bound copy/reindex bodies in the loaded module before dispatch.
The native call retains its original two-pointer, void-return ABI; it does not
set the NewGame flag or translate the configuration in Python.

A subsequent bounded native group used the existing qualifier's `copy` stage:

```powershell
python tools/qualify_xp1_configuration.py --stage copy
```

It restored and sealed owned configuration B, prepared XP1, invoked the shared
copy method, and verified A before releasing B and destroying the context.
All 64 player records pointed to the copied configuration, and its 66 child maps
were distinct from B. Five explicit values spanning root, map, player 0 and player
63 survived the copy, including unsigned integers, a hashed integer and UTF-16
text. This is sampled value verification, not a comparison of every property.

The single native group completed in 7.76 seconds, with peak private/commit memory
of 156,053,504 bytes, exit 0, original inputs unchanged and complete teardown.
The existing 45-second/512-MiB containment was retained. The Base native call and
its semantics are unchanged; its existing gameplay qualification was preserved.

The diagnostic uses the existing XP1 typed reader for post-copy values. It does
not claim a complete Lua configuration interface or construct an admitted XP1
saved-game backend. Tuner absence is still diagnostic-only. Official saved Load,
gameplay script services and exact input-bundle association remain unqualified.
# Shared saved-Load composition

`SavedLoadServices` composes the existing owners for scalar/map conversion,
native copied event maps, synchronous GameEvents and selected script contexts.
It borrows the initialized runtime, API child and Core DB ownership; it does not
start another VM/DB or run the NewGame prefix's diagnostic suites. Configuration
readback is extracted from the existing `OfficialPrefix` into a shared mixin;
the Base path inherits the same method body. Attaching the services checks the
engine, native owner and prepared phase. Missing deferred/action machinery is
not represented by synthetic empty queues.

A bounded native group restored B, called the existing loader's B-to-A copy,
read the copied named property through `MapConfiguration.GetValue`, and loaded
two fixture scripts through XP1's real manager. Their calls used A0/A8 and a
native map payload through the official event wrapper with all services live.
Replacement, listeners, payload release, callback restoration and Lua heap
closure passed. Runtime: 8.25 s; sampled peak private memory: 178,462,720 bytes.
The 26 grouped offline checks cover shared ownership, phase/engine refusal,
retained consumers, loaded-Game early-close refusal and unchanged Base readback.
Private receipt: `evidence/host-xp1-saved-load-services.json`.

This is composition before full Game Load. HOST130/application state and the
deferred-event boundary remain to be integrated for XP1. Ordinary preparation's
Tuner admission and exact official bundle association remain separate gates.
An initialized Game may still call host/script services during Destroy: the
new owner refuses premature close, but loaded-game shutdown is not qualified by
the empty prepared Game's teardown. Neither complete script bootstrap nor full
gameplay/extension compatibility follows from this receipt.

# Selected gameplay script contexts

`ScriptContextService` owns the saved-game script-loader callback family and
borrows the existing Lua runtime. It takes the explicit ordered registry, exact
file hashes, a bounded reader and an explicit bootstrap callback. Duplicate
entries remain ordered: the native manager decides replacement by normalized
name. The host does not substitute a constant `Map Script` name or infer active
scripts from installed content.

The XP1 manager created during Init has executed its real load method on three
entries representing two diagnostic Lua files. It replaced the first context,
notified all three successful loads, retained two isolated environments and
executed their listeners through an official XP1 event wrapper. Its real clear
method released both children; subsequent collection removed their listeners.
The Core retained ownership of the manager allocation through Destroy. Native
heap closure and callback restoration passed in a 7.24-second bounded worker.

The common owner reuses the earlier context lifetime and notification adapters.
The current executable includes only the authored productive notification C
prefix, excluding the private differential oracle. The retained Base and XP1
build profiles remain unchanged. Grouped checks cover 28 cases; a first native
attempt stopped because the qualifier passed a null event payload. Only that
qualifier call changed before the successful attempt; the product implementation
was unchanged. Private receipt: `evidence/host-xp1-script-contexts.json`.

This is not a full expansion game. Official bundle association, complete script
bootstrap, deferred services and full saved-Load composition remain outstanding.
The service accepts already-resolved absolute paths; it does not implement the
EXE's redirection mechanism. Missing files and Lua errors remain strict host
refusals, explicitly differing from the EXE's log-and-continue path. Unknown
callbacks are not admitted. Contexts must be released by their native consumer
before closing the shared service. Current release wheels predate this work.


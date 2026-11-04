# civ6-host

Model-independent Python API and headless host for the official Civilization VI GameCore.

**Development status.** Local qualification covers scoped Base, Rise and Fall
and Gathering Storm sessions. The installed Windows client and runtime have
resumed a Gathering Storm v21 checkpoint, played a native turn and saved again.
The v22 source runtime completed a native unit promotion and saved the result.
The installed v22 runtime resumed that checkpoint and saved it again using
the authenticated local private resources.
The host uses the official engine and exact captured inputs. Full games across
all profiles, complete gameplay coverage and two-human simultaneous play remain
open.

The Gathering Storm candidate now loads the entire captured saved Game component,
executes the selected official WorldCongress script, matches the captured limited
own-player readback, and completes native Unload/Destroy and all service cleanup.
The bounded headless process exited normally after 74.82 s with a 278 MiB private
memory peak. These instrumented startup/cleanup measurements are not game throughput.
The XP2 configuration mirror, logger and DistrictRemoved teardown consumer use
explicit source profiles. Private evidence: `evidence/host-xp2-loaded-cycle.json`.
Earlier assembly refusals remain preserved in their original evidence.

The subsequent group also completes cache population, Post160, native cache
publication and clean Unload/Destroy in the same loaded instance. Its authenticated
process exited normally in 94.42 s with a 341 MiB private-memory peak. Post160
observed the pending-zero branch; active visibility branches remain separately
unqualified. Evidence:
`evidence/host-xp2-postload-cycle.json`. This startup measurement is not turn throughput.

The next witness binds the official XP2 UI APIs in a distinct owned Lua child,
reads the existing player-scoped observation and closes the same loaded instance
cleanly. It observes 28 currently visible plots and two own units; the recorded
official ten-plot sample, own units and zero-city economy match. Complete visibility,
resource visibility and all public fields are not thereby qualified. The bounded
instrumented cycle took 108.98 s and peaked at 340 MiB private memory. Evidence:
`evidence/host-xp2-player-observation.json`.

The common Python client now completes the initial XP2 action/turn/close/reset
group: founding, research, civic, current production, forced end turn, six native
updates to turn 2, clean close, and a fresh process restoring the same initial
public observation and choices. Both processes exit normally. Storm, random-event
and FavorChanged records are joined to their ordered, unique FIFO consumption;
their raw data remains administrative, not automatically player-visible.
The instrumented group took 351.25 s overall, with private-memory peaks of
352 and 359 MiB. These are qualification costs, not sustained game throughput.
Private evidence: `evidence/host-xp2-turn-cycle.json`.

The next XP2 group also exposes the existing v5 world/unit catalogue through the
common client. Six native commands fortify a warrior, release it, select it,
issue MOVE_TO, cancel its still-pending destination, and deselect it. Native
readbacks show movement from (38,14) to (39,13), movement points consumed, and the
nonempty destination cleared by CANCEL. Both lifetimes close cleanly and an
independent reset restores the same initial state and choices. The instrumented
group took 285.92 s overall, with private-memory peaks of 364 and 365 MiB.
Private evidence: `evidence/host-xp2-world-unit-inputs.json`.

The XP2 v6 queue catalogue and edits are now qualified in the same client. A
group of twelve native commands founds a city and performs eleven queue edits:
append from empty to eight entries, observable swap, replacement of the eighth
entry at capacity, and removal. Public queue states match the native effects;
both sessions close cleanly and a fresh reset restores the initial choices and
queues. The instrumented group took 347.46 s overall, with private-memory peaks
of 359 and 367 MiB. Evidence: `evidence/host-xp2-production-queue.json`.

The XP2 v8 placement group now qualifies an offered Holy Site placement at turn
10, replacement by Settler production, and resumption of that same unfinished
district. The native inventory reports its real district ID and plot. Both
processes complete native cleanup; the fresh reset restores the original turn-1
capture, not a turn-10 checkpoint. The instrumented group took 801.94 s, with
private-memory peaks of 386 and 389 MiB. Immutable source-validation caching
preserves content hashes and live checks; matching observation intervals were
about 1.76 times faster, with 67 unchanged observation/control snapshots.
This is not a production-throughput or parallelism benchmark. Evidence:
`evidence/host-xp2-production-placement.json` in the private lab.

The common client now also saves the native XP2 Game/configuration pair, closes,
loads it in a fresh process, executes a deselection, saves a child pair, reloads
that child and executes an offered civic. All three lifetimes close cleanly.
The qualified public state, semantic choices and selection survive both Loads
at turn 2. The instrumented group took 690.19 s, with private-memory peaks of
385, 468 and 462 MiB under a 512 MiB per-process limit. This covers two exact
component pairs, not arbitrary states, complete hidden-state equality or a
full official save container. Evidence: `evidence/host-xp2-native-checkpoint.json`
in the private lab. The read-only review reused retained native traces.

The XP2 v11 client now qualifies one offered melee `MOVE_TO` attack through
the official `enemy_flag` route at turn 5. The native attacker took 44 damage,
the visible target took 20, and the attacker's movement and attack points were
consumed. Two independent lifetimes closed normally; reset restored the same
prepared checkpoint, qualified public state and choices. The earlier continuous
preparation traversed natural-wonder discovery, advanced to turn 5 and produced
the native checkpoint. Evidence: `evidence/host-xp2-combat-inputs.json` and
`evidence/host-xp2-unit-attacks.json` in the private lab. Two combat information
queries were live; the reset query was validated in a read-only client replay.
The 530.50-second instrumented attack/reset group peaked at 466 MiB private
memory. A separate v18 client witness produces a Slinger at turn 44, executes
the offered dedicated ranged attack, and records 38 damage to a visible unit.
It saves the resulting checkpoint and closes normally. City assault and other
unexercised routes remain unqualified. Evidence: `evidence/host-xp2-ranged-unit-attack.json`.

These witnesses cover the captured XP2 LAN save with one human and one AI.
Other orders, broader movement/combat, other placements, long continuations,
victories and two-human simultaneous play remain unqualified in XP2. A separate
v18 witness executes an offered `HEAL` and observes native healing for one
Warrior on friendly land at end turn. Evidence: `evidence/host-xp2-unit-heal-turn.json`.
Queue append choices remain partial for placement-required items and nonstandard
formations; this edit group proves no production progress or completion over turns.
Production choices are explicitly partial. Nonzero observation display precision
and missing research/production estimates remain documented gaps; raw getter
precision is not thereby qualified as human-visible precision. District
completion, positive retained progress and checkpoint reload with an untracked
placement remain unqualified. Drought, climate and random-start branches have source
and offline checks but were not reached here; empty weather vectors remain
explicitly refused. Earlier attempts and their refusals are preserved.

The shared configuration backend now initializes the Gathering Storm engine
against the retained official captured databases, restores and serializes its
application configuration, and destroys the context cleanly. A bounded native
witness verified both connections, the 16 event declarations, all ten registrar
removals, database shutdown and unchanged private files. The serialized provider
has two empty-string flag changes now explained by the XP2 reader/writer code.
The engine-selected comparator consumes all 984 retained values, accepts only
that exact representation transition, and refuses other changes; raw-byte
equality remains false. This review reused the retained native bytes without
another DLL run. That earlier configuration-only run executed no Prepare,
saved Game Load or XP2 gameplay. This prerequisite is not a playable Gathering Storm session.
Private evidence: `evidence/host-xp2-configuration-lifecycle.json`.
Representation proof: `evidence/host-xp2-provider-equivalence.json`.

The existing deferred queue, controller and complete event-map reader also now
select explicit XP2 source profiles. A composed fixture group verifies their
shared ownership, source checks, complete field reads, FIFO feedback, notification
scopes and strict unknown-event refusal. They now participate in the native raw
Load/close group above; broader event reachability remains unqualified. Private evidence:
`evidence/host-xp2-preload-services.json`.

The low-level Gathering Storm script service now supports source-selected
mutable GameEvents maps. A bounded native HKS/XP2-provider group exercised
seeded tables, typed arguments, owned copies, nested replacements and protected
errors with clean teardown. It used constructed Lua fixtures, without a game
context or official World Congress script. The later loaded-cycle group above
adds real XP2 WorldCongress initialization; gameplay continuation remains
unqualified. Evidence: `evidence/host-xp2-mutable-map.json` in the private lab.

The v11 source client has executed an actually offered XP1 melee attack through
the official enemy-flag route. Native readbacks showed 17 damage to the attacker,
40 damage to the visible target, and consumed movement/attack points. Two native
lifetimes closed cleanly; an independent reset restored the prepared turn-13
public state and attack choices. The new checkpoint supports normal native Load.
Evidence: `evidence/host-xp1-unit-attacks.json` in the private lab.
Ranged attacks, city assaults and other unexercised routes remain unqualified.
This source-tree qualification is not a complete combat or host release.

The source v10 client now exposes typed XP1 combat information, with ordinary
display precision in the public channel and explicit opt-in raw city precision
in a separate administrative channel. A native witness queried both channels,
loaded the retained v9 checkpoint, returned the human ready at turn 12, saved
and closed cleanly. That earlier group did not witness a positive attack effect.
Evidence: `evidence/host-xp1-combat-information.json` in the private lab.

Capability v8 adds a native inventory of placed constructions on currently
visible plots belonging to the player's cities. The reader is independent of
host placement history. A grouped XP1 witness placed a Holy Site, switched
production, saved, loaded the saved state in a fresh process, resumed the
district and reset to the same checkpoint. The native inventory and qualified
public choices survived both Loads; all three lifetimes closed cleanly.
Only that unfinished district is positively witnessed. Wonders, completion,
positive production progress and a native Load with empty host tracking remain
unqualified. Evidence: `evidence/host-xp1-placement-inventory.json`.

The captured Rise and Fall session also exposes ordered production queues through
the common Python client: append, remove, swap, and replacement of the last slot
when all eight slots are occupied. An actual native group filled the queue,
swapped distinct items, replaced the eighth item and removed an item, then closed
and reset in a second process. Explicit corps/army production remains unqualified;
it is not silently substituted with ordinary units.
Evidence: `evidence/host-xp1-production-queue.json` in the private research lab.

The v7 source client also exposes native district placement and resumption. From
a naturally prepared turn-11 checkpoint, the client placed a Holy Site, switched
production to a Settler, resumed the same unfinished district, closed and reset
in a fresh process. Native effects and restored public observations/choices were
authenticated. Retained progress was zero: positive accumulated progress,
completion, wonder placements and the inventory of pre-existing untracked
placements remain unqualified. Evidence: `evidence/host-xp1-production-placement.json`.

The captured Rise and Fall session supports administrative native Save and
checkpoint resume through the common Python client. A grouped witness fortified
and selected a unit, saved, closed, reloaded, executed the offered cancellation,
closed, then reset to the same checkpoint in a third process. Qualified public
observations, choices and selection matched after both reloads. This establishes
one captured checkpoint cycle, not arbitrary-state or full hidden-state parity.
Gathering Storm configuration ownership/codecs and native configuration copy/relink
are connected; the native raw Load/close group above is now qualified, while
gameplay through the public API remains unqualified.
A new official Gathering Storm capture now retains a newly requested save,
its serialized configuration, all three final databases, ICU/settings and the
ordered World Congress script selection from the same identified game process.
Repeated reads agreed before and after the save. This supplies a scoped input
candidate, not a transactional snapshot. The
private `xp2-lan` reader has validated those complete captured inputs separately
from Base/XP1 admission; the later loaded-cycle evidence qualifies this exact raw Load;
see [Gathering Storm inputs](docs/xp2-capture-inputs.md).

The captured Rise and Fall session now also exposes own-unit selection, every
map click coordinate and native queued destinations. A public-client group
selected a unit, moved it through the official click route, verified position
and movement points, exercised an official no-op, deselected, closed and reset.
Non-MOVE_TO click branches and war confirmation remain explicit refusals;
complete movement/combat is unqualified.

The v5 unit-order delivery also exposes native own-unit activity, readiness,
fortification turns and reviewed parameterless order offers. A captured XP1
group fortified a unit, released it using the actually offered CANCEL command,
queued a distant movement, cancelled that nonempty destination, closed and reset.
WAKE was not available in that state and was not invented. HEAL and
RELIGIOUS_HEAL were unavailable for the selected unit; healing over turns and
unwitnessed order branches remain separate qualification gaps.

## Repository boundary

- **civ6-host:** loading, native sessions, player-scoped observations, explicit
  gameplay commands, events/results, save/resume, reset, cleanup and separate
  administrative information. It does not select a strategy or reward.
- **civ6-agent:** feature selection and normalization, CNN/entity/LSTM encoders,
  actor/critic, curriculum, self-play scheduling and learning. Its development
  is currently deferred while the host is completed.

Windows runs the native engine. The portable client can be imported on macOS;
this is not a macOS GameCore implementation. The Mac is reserved for future
learning work. No learner or PyTorch dependency is included in this repository.

## Packages

| Package | Role | Current requirement |
| --- | --- | --- |
| `civ6-host-client` | Session clients and information/action contracts | Python 3.10+, standard library |
| `civ6-host-runtime` | Local native adapters and bounded worker supervisor | Windows x64, Python 3.12, matching client |

Build and installation instructions are in [backend setup](docs/backend.md).
The information-query delivery was built offline and installed into fresh local
targets as two wheels. Installed-client queries and the optional administrative
store were checked against retained native replies without executing GameCore.
That packaging check does not qualify a new live installed LAN run.
The shared reader accepts the exact XP1 LAN capture with its associated saved
inputs. Native Load now consumes its full stream, verifies the captured state
and populates candidate caches. The shared postload+160 no-transition branch,
native +190 refresh and ordered loaded teardown now complete together on this
capture. A separate official XP1 UI child now returns the shared player
observation, with a retained official subset comparison and clean teardown.
The source runtime now runs an initial XP1 choice group through the shared
public client: foundation, research selection/replacement, an explicit native
civic request, and unit/building/unit production replacements. The same session
returns refreshed native choices, closes through Unload/Destroy and restores the
initial state in a new process. This covers one exact captured state. Production
placements/queue editing and complete XP1 observations/actions/turn progression
were unqualified in that initial choice delivery. A subsequent captured cycle
now executes forced EndTurn and 16 explicit native updates, returns the local
human active at turn 2, closes natively and restores the exact initial state in
a fresh process. Normal EndTurn and Unready were not executed in that witness;
Unready was actually unavailable after the sole human ended the turn. Complete
XP1 gameplay and longer continuations remain unqualified.
The client also now accepts the official forced-turn offer while the human is
already inactive. A second native request with unchanged public turn controls
returns `submitted` and no applied action, rather than crashing or claiming an
effect. This was exercised through the public client, followed by the next
active turn, native close and fresh reset. It proves neither a network
acknowledgement nor absence of all hidden effects.
The shared command transport now serializes an explicit native XP1 unit order
and verifies its copy into the Core receive queue. Real XP1 unit-parameter,
map, civilization, District, Building and production callbacks now run through
shared adapters. The first explicit XP1 foundation command now completes:
the selected settler is consumed, the new city appears in the refreshed player
observation, and native Unload/Destroy complete. Loyalty notifications reuse the
source-checked city/scalar event family. This qualifies that command on the
retained save. Its public client integration is now qualified separately; a
complete playable expansion session remains pending.

XP1 currently has shared native configuration, Lua, callback, controller, cache-facade
and Player/Treasury services, plus an exact official saved-Load/cache receipt.
The captured first-turn cycle does not admit a complete expansion game. The precise remaining
boundaries are maintained in [XP1 services](docs/xp1-services.md). Latest source
changes still require an updated installed-package qualification.

The runtime also needs the exact installed game and a separately prepared
[private resource package](docs/resource-bundle.md). Wheels contain host code;
they do not supply official game DLLs, databases, saves or captures. Community
resource preparation and redistribution review remain unfinished.

## API and information boundary

[SessionClient](docs/client.md#captured-lan-session-client) accepts explicit
choices from the current native catalogue. The host does not remove a choice
because it seems strategically weak. Unimplemented services and unsupported
profiles fail explicitly; a catalogue is not proof that every human action has
been exposed.

A state is identified by episode, generation, player, turn and sequence. Several
commands can occur within the same turn. The simultaneous mode cannot be
replaced by hotseat semantics.

The typed [information channels](docs/client.md#typed-information-channels)
provide `economy`, `production`, `growth` and `unit_work` through
`SessionClient.information(group)`. The scoped XP1 v10 source delivery adds
`combat` with its separate optional administrative readback. These methods query the current cached response;
`observe`/`poll` refresh it. Explicit opt-in administrative queries preserve
additional economic, production and growth precision with matching provenance.
They are separate from the public queries. The older full `view()` still has
mixed diagnostic fields and is **not a globally player-only input dictionary**.

## Qualified scope and remaining gaps

| Area | Retained evidence | Still to qualify |
| --- | --- | --- |
| Loading and lifecycle | Installed Base/hotseat round-trip; source Base LAN loading, turns and resets; captured XP1 shared-client Load and fresh reset; installed XP2 LAN Load and clean close with relocated private resources | General community preparation, broader expansion continuations and additional capture profiles |
| Explicit gameplay | Native Base choices including map movement, plot purchase, production/citizen controls, builder work and initial diplomacy; XP1 foundation/research/civic/current-production choices, forced EndTurn, world inputs, fortification and cancellation of a nonempty movement queue | Complete XP1 action families, parameters and interactions; native normal/Unready request witnesses |
| Persistence/results | LAN checkpoint save/reload; installed XP2 foundation, save and reload with matching public observation and choices; XP2 LAN with one human and one AI resumed at turn 19, saved at turn 21, then reloaded and saved at turn 22 with clean shutdowns; retained native victory/loss evidence | Complete LAN terminal/reset cycle |
| Multiplayer | One-human/five-AI Base LAN; separate player perspectives on hotseat. The retained Base, XP1 and XP2 LAN capture saves each declare one taken slot. | An exact capture with two live humans, then simultaneous interleaving, conflicts, readiness and timers |
| Information | Four named Base public groups; separate optional administrative snapshots; partial XP1 player observation, choices and native turn availability through the common client | Complete gameplay information and XP1 public precision review |
| Distribution | Separate reproducible client/runtime wheels; native XP2 installed checkpoint reload using an explicitly prepared private resource set | Independent resource preparation and release review |
| Content | Exact Base, XP1 and XP2 capture profiles; selected World Congress script executed on the XP2 route | Complete expansion games, broader DLC/script execution and exact BBG/BSS profiles |
| Performance | Single-worker and two-worker XP2 turn measurements with isolated database copies. An installed worker also advanced three consecutive forced turns in one instrumented LAN session with one human and one AI, at a median of 69.3 s per turn after 235.9 s of startup and a 463 MiB private-memory peak. | Sustained production throughput and maximum parallel capacity |

The retained native checks do not establish 100% fidelity, full-game readiness
or readiness for a strategic learning campaign. [Earlier capability receipts and
limits](README-history-20261030.md) remain preserved; the current API and
qualification details are in [client documentation](docs/client.md) and
[backend documentation](docs/backend.md).

## Development and validation

Shared contracts are integrated by complete families. Pure client/data changes
use retained native replies. Changed native calls require bounded native checks;
interaction and long-game checks run at their corresponding milestone.
Unchanged successful checks are not routinely repeated. Native workers use
private database copies and explicit time/memory limits.

The extracted runtime keeps [source provenance](docs/backend.md#provenance-and-compatibility).
The [native builder](docs/native-build.md) reproduces the retained Base executable
and the separate XP1 Lua-binding executable from reviewed shared sources. The
XP1 build remains a prerequisite for extension integration, not a qualified
expansion game session.
Generated adapters are updated through `tools/extract_runtime.py`; historical
lab sources and receipts retain their original hashes. See
[native build](docs/native-build.md), [capture preparation](docs/capture-package.md)
and [resource boundaries](docs/resources.md).

Public release requires reviewed source allowlisting, third-party notices,
a license decision and independently reproducible installation. No publication
has been authorized or performed.
Use the [local source review archive](docs/backend.md#source-archive-for-local-review)
to inspect the build inputs separately from the private resources.

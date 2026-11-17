# Extracted client: current scope

## Congress v37–v39: scoped ballot cycle qualified

The selected current XP2 session can opt into `world_congress_diagnostic=True`
alongside the existing `espionage_diagnostic=True` query chain. This adds
`information('world_congress', player_id=pid)` and four explicit choices:
`congress_open`, `congress_confirm_ballot`, `congress_confirm_proposals`, and
`congress_close`. Reading information never opens a review or acknowledges it.

Ballot parameters contain `resolutions` (each with `resolution_hash`, `option`
1 or 2, the offered `target_index`, and positive `votes`) and `discussions`
(each with `discussion_index` and nonzero signed `votes`). Supply every editable
item. Proposal parameters contain the complete selected `proposal_indices` list.
All values must come from the current catalogue. `congress_ballot_draft(pid,
parameters)` validates an unsent local form; submit it through the existing
`act(pid, decision_id, candidate_id, parameters=parameters)` call.

The API validates the complete form before the first native request. Its packets
are ordered without another model decision between them; they are not an atomic
transaction. Partial delivery is retained and prevents further decisions.
`favor` is the form budget, captured on opening the proposals review;
`current_favor` is the player's current native amount. The v37 Congress predicate
removes the source-disabled government, policy and governor choices during a
session while preserving their observations. It does not change historical v36.

The existing `examples/local_session.py` also accepts LAN `information` commands
with `group`/`player_id` and `congress_ballot_draft` with `player_id`/`parameters`.
It never selects votes itself. Ordinary native catalogues through T61, the
Congress phase transition and the active three-resolution form are recorded on
the selected GS + BBG profile. The client now receives the result of a complete
ordered native batch: three resolution votes, submit and end-turn. The existing
transport consumes the exact native completion echo before the next update,
then publishes once. The initial command remains `pending`. Subsequent native
updates emit Finished and reach turn 62. Public Review now preserves the raw
signed result fields, including the observed foreign option -1; it never
normalizes that value into a submitted vote. Exact own-vote/cycle matching,
quiescent journal retirement, Save and normal Destroy succeed. A fresh process
reloads identical public observations and catalogues with rebound session identity,
then saves and closes normally. This qualifies the recorded three-resolution B/1
ballot, not all targets, vote counts or mechanical resolution effects. Requests
without an accepted-result readback remain `pending`. Save refuses an open review
or an unresolved confirmation journal. Other results, preferences, emergency details,
participant roster, active effects and timeout/reopening retain explicit gaps.

The additional explicit `world_congress_review_diagnostic=True` option selects
v38; it requires the Congress option above. The cached public group
`information('world_congress_review', player_id=pid)` reports the last results
only when the official results UI admits them. During live voting this channel
does not read foreign ballots. `decisions.world_congress_review_status` separates
`available`, `waiting_or_closed` and `review_ui_unavailable`; unavailability is
not an invented empty history. The historical v37 interface stays unchanged.

The optional cycle observer joins actual native Stage/Finished events, submitted
forms and subsequent public results. It does not invent individual packet ACKs.
Save may retire a delivered confirmation only at an ordinary, quiescent boundary
with the required matching result, or the source-qualified zero-choice automatic
phase. Default-only votes require the same exact result without claiming whether
submission or native default filling produced it. Hidden player targets are
matched through a separate own-vote administrative sidecar; hidden identity does
not enter the public catalogue. Unknown midphase loads, ambiguous discussion
identities and unresolved proposal submissions retain explicit refusal paths.
For ordinary proposals and closing, an administrative reader compares the exact
own-proposal tuple delta and native LOOKED marker before and after the complete
batch. A marker already equal to this turn is reported as already satisfied,
not a new write. Only exact observed state and complete delivery can retire this
ordinary journal; neither a historical Review nor a Finished event is invented.
Detailed target identities stay administrative. Native proposal effects remain
unqualified. The completed ballot and its post-result Save/reload are recorded
in the private lab evidence `evidence/host-xp2-congress-ballot-cycle-native.json`.

On the current stock XP2 capture, the client also restored the same regular
T81 voting form from an authenticated checkpoint. Its ballot sent two
resolution votes. The native Finished callback and exact Review matched
in the resumed process, permitting a clean Save at the ordinary T86 boundary.
The checkpoint records the completed Temple and the native 200-faith
Apostle quote. An independent process restored the exact T86 observations
and choices before the Holy Site defense interval.
Private evidence `evidence/host-xp2-stock-t81-congress-midphase-t86-temple-save-native.json`.
Independent reload evidence `evidence/host-xp2-stock-t86-holy-site-defense-t89-save-native.json`.

In the next stock XP2 processes, the client reloaded T89, fired four offered
Slinger attacks and saved the vacated but pillaged Holy Site at T93. It
reloaded T93, resumed the district repair and used the offered forced turn
command. GameCore reported the district repaired at T94 and saved that
state. The Apostle quote was absent. Private evidence
`evidence/host-xp2-stock-holy-site-ranged-combat-t93-save-native.json` and
`evidence/host-xp2-stock-holy-site-repair-t94-save-native.json`.

On that stock Gathering Storm capture, the client saved the repaired
Shrine and the Temple in production at T95. An independent process
restored the previous observations and choices, then replayed the retained
commands through T106. The host received and drained the same
`GameCoreEvent::CultureChanged` notification that previously stopped it.
GameCore published T107, saved it and destroyed its native context normally.
A fresh process restored the T107 observations and choices exactly. The
enemy-flag and world-plot gestures both submitted `MOVE_TO` for a Great
General on the turn-107 state. In both cases the public command receipt
reported a refusal. The world-plot request produced neither a visible change
nor a queued destination. The unit selection preceding it completed. Both
processes saved and closed normally. The Holy Site was still occupied.
Private evidence `evidence/host-xp2-stock-culture-changed-turn-crossing-native.json`,
`evidence/host-xp2-stock-holy-site-enemy-flag-refusal-t107-native.json` and
`evidence/host-xp2-stock-t107-holy-site-world-click-native.json`.

The subsequent stock continuation used an armored unit's offered movement
and a Slinger shot that increased the occupier's damage from 8 to 15.
The Holy Site was clear at T109 and repaired at T110. The T110–T111
transition enqueued and consumed two `GreatWorkMoved` notifications on
the existing empty-subscriber FIFO using the pinned current XP2 images.
The host saved normally at T111 with the armored unit on the Holy Site
and a Shrine repair underway. Independent reload and the Temple/Apostle
continuation followed. Private evidence
`evidence/host-xp2-stock-great-work-moved-turn-crossing-native.json`.

The fresh T111 session restored the same observations and legal choices.
The Shrine was repaired at T112 and the Temple at T113. The native
200-faith Apostle quote returned. Team 1 won at T116 with the local player
on team 0. The ordinary `poll()` reply carried `official_native_victory`
with null observation and decisions. The history writer and platform
achievement sink use their source-qualified nullable native branches.
The diagnostic driver aborted after receiving that reply because it
tried to read the null observation. A subsequent replay closed the terminal
session normally and reset the same Python client from the T111 checkpoint
with a fresh episode identity.
Private evidence
`evidence/host-xp2-stock-native-terminal-response-t116.json` and
`evidence/host-xp2-stock-terminal-close-reset-native.json`.

An alternative stock continuation from T95 exercised a forced end-turn
after which GameCore reactivated the player at T98. The public receipt
reported submission and the saved boundary retained the armored unit's
melee offer. A fresh process restored that offer, executed the attack and
observed the armored unit occupying the Holy Site. After the repairs the
T108 purchase spent exactly 200 faith and produced an Apostle with three
charges. The T109 save preserves the native `spread_religion`,
`evangelize_belief` and `launch_inquisition` offers. Two independent
processes restored this boundary and exercised the two Apostle operations.
Private evidence `evidence/host-xp2-stock-armor-and-apostle-t109-save-native.json`.

The current Review opt-in also publishes v39 `native_command_permissions`.
Native strategic/tactical permissions remain distinct from player activity and
turn completion. When a reader requires strategic permission, its group is
explicitly unavailable while that permission is false; no empty catalogue or
inactive player is invented. Independent observations and Congress remain
readable. The public trade group uses `civ6-host.trade-inputs.v2` to retain routes
when its separate origin reader is unavailable. These reader limits are API
coverage gaps, not a claim that every related human screen is unavailable.

Private evidence: `evidence/host-xp2-congress-client-preparation.json` in the lab.

The v40 extension adds `information('world_congress_active_effects', player_id=pid)`
to the same Review opt-in. It exposes the ordinary Current Effects panel:
active resolution descriptions, visible targets and official durations, plus
proposal cards with their displayed crisis goals and rewards. It remains
separate from historical vote results and does not acknowledge consultation.
The same scoped native configuration reader is reused; unmet target IDs stay
masked. No graphics, emergency navigation or new action is added. A native T62
read through the client returns three active resolutions, a meeting counter of
19 displayed as 20 remaining turns, and an actually empty proposal list. The
v39 observation and saved catalogue fields remain identical; v40 adds only the
two documented fields. Save and normal Destroy succeed. Nonempty proposal cards
remain source/software qualified only. Private lab evidence:
`evidence/host-xp2-congress-active-effects-native.json`.

On a captured simultaneous XP2 LAN game, the same groups can be read for an
authorized secondary human with `secondary_unit_commands=True` and that
player in `public_view_players`. The host reads the secondary player's own
form during their perspective interval. The Review opt-in also enables their
last results and current effects in the official display phase. A secondary
ballot can be selected when the host observed the native start of its cycle.
The command remains pending after delivery. Observing the same player's
finished results lets the host compare the native votes before admitting Save.
Ordinary Congress proposals use a player-owned popup and the native proposals
currently offered to that player. Closing or confirming the popup sends the
official consultation acknowledgement. Confirmation checks that player's
proposal state and consultation marker before reporting completion.
Save/Load can preserve an unsubmitted secondary ballot when its native cycle
and borrowed view were captured. The two public views and the actor's native
choice mapping are compared before that ballot becomes actionable again.
During a session the Congress phase also removes government, policy and governor
edits from that player's choices. Those public panels remain readable.
The public catalogue comparison after Load retains the scope recorded at Save.
Secondary routing and checkpoint comparison have software coverage. Native
Congress evidence covers the primary player.

The repaired Steam installation has an explicit trial selection on
`NativeNetworkSession`: `execution_image_profile="xp2-gamecore-current-092abfbb"`.
It verifies the actual Core and three shared libraries and selects the derived
BBG host with the current Havok export addresses. Omitting this option preserves
the historical selection; a changed DLL is never inferred as compatible.

To resume a v1 checkpoint created under the reference image, also select
`checkpoint_compatibility="xp2-reference-abi-to-selected-runtime.v1"`.
Its creation identity remains unchanged. A newly written v2 checkpoint records
the actual image, ABI reference and exact execution selection separately. A v2
resume must match that selection. These administrative choices do not alter
actor observations or choose any gameplay action. Static admission authorizes
the bounded native trial only; its gameplay and lifecycle still require native
qualification on this build.

The opt-in `war_source_sha256` must be supplied independently to both the
native session and `SessionClient`. A pending official WorldInput prompt is
published as `civ6-host.network-world-war-decisions.v1`, with the two explicit
`world_war_response` choices (`accept=False` or `True`). Forced end-turn cannot
bypass it. On the selected current Core, the GS + BBG 7.5.1 witness cancels and
then declares war against Hattusa, reads the native war-state change, saves and
closes. Missing receiver profiles refuse before RequestSession. The client
selects each diplomatic response explicitly. Private evidence:
`evidence/host-xp2-war-confirmation-native.json` in the local lab.

The major-player response API uses a separate public modal,
`civ6-host.network-diplomacy-decisions.v1`, rather than exporting the private
legacy statement catalogue. `dialogue` carries session/statement identifiers
needed by the command interface and public participant IDs. `choices` preserves
native menu order and disabled state; `candidates` contains its executable
responses. `public_display` contains rendered speaker/text/menu information,
bound to an independent renderer source profile. A missing display is explicit
and unqualified. Raw AI reasons, raw moods and opaque statement payloads are
excluded. Administrative/native receipts remain separate. Consumers select their
own features; these identifiers and text are not a model architecture decision.

Public modal replies, including inactive-player responses, are validated by the
common client without importing the native backend or requiring local game
resources. At T57 on the current GS + BBG 7.5.1 profile, the client accepts a
major-player surprise-war prompt, reads the native public dialogue and selects
`CHOICE_EXIT`. The continued session reports the native war state and saves
before teardown. This witness covers an explicit world-input declaration from
one human against an AI. Private evidence:
`evidence/host-xp2-major-war-t57-native-continuation.json` in the local lab.
An independent process restores the observation, selection, war relationship
and legal choices. The previously blocked `world_plot_click` then moves the
unit across the border without reopening the war prompt. Save records the new
position on the same turn. Private reload evidence:
`evidence/host-xp2-major-war-t57-native-reload.json`.

The surprise-war route also verifies the selected native factory
registry entry, constructor bytes and virtual targets before RequestSession.
Unknown names, a foreign factory or corrupt registry are refused. The T57
witness exercises the selected surprise-war factory on the live registry.
The remaining registry entries still require their own native witnesses. The
local qualifier's `--world-war-target-major` requires a verified saved major
roster and a public target before starting a native worker.

The existing `world_select_unit` / `world_plot_click` route now admits the
source-qualified XP2 `SWAP_UNITS` branch. In the retained BBG 7.5.1 session,
an owned Warrior selected at (14,11) clicks the other owned Warrior at (15,11).
The official helper chooses `SWAP_UNITS`; exactly one native archive is delivered
and both unit positions exchange. Native remaining movement becomes 1 and 0,
respectively. The same session saves and destroys normally. No additional
strategic action filtering, synthetic movement or guessed opcode is introduced.
The resulting turn-25 checkpoint is saved but has not been reopened. This does
not admit XP1 swaps, arbitrary swap eligibility, other WorldInput branches or
XP2 war confirmations. The legacy partial-family gap labels remain conservative
pending the larger WorldInput contract extension. Private evidence:
`evidence/host-bbg751-unit-swap-native.json`.

The opt-in `governors_diagnostic=True` XP2 session publishes a v32
`decisions.governors` catalogue: obtained/spent titles, consideration state,
eligible/appointed governors, public status, promotion rows and assignment
targets. The common candidate API exposes `appoint_governor`,
`promote_governor`, `assign_governor` and `consider_governor_titles`.
Requests carry the selected database index plus its checked type hash; city
destinations retain both owner and city ID. The engine decides legality and
effects. Hidden promotion labels do not by themselves remove a clickable action.

All four gestures executed at turn 47 in the exact retained Gathering Storm +
BBG 7.5.1 profile, followed by native Save/Destroy. A subsequent fresh native
session reloads that saved catalogue identically and advances three forced
turns. Governor index 0 (`GOVERNOR_THE_DEFENDER`) remains assigned to the same
own city with the same owned promotions; `turns_on_site` progresses from 0 to 3
and the engine reports `established=true` at turn 50. The session saves and
destroys normally. The new turn-50 pair is not reopened. Other governors,
foreign assignments, neutralization and broader lifecycle interactions remain
unqualified. Private evidence: `evidence/host-bbg751-governor-establishment-native.json`.
Sessions without this explicit option preserve the v31 interface.

The installed Rise and Fall LAN profile exposes the same governor fields and
four action kinds in `v11.captured-city.v4`. Its assignment chooser uses the
native current-governor identity and offers own cities and eligible met
city-states. At turn 17 the client appointed the Defender, assigned him to
the player's city, selected an offered promotion and marked the titles considered.
A separate ordinary process restored the governor, assignment, promotion,
title state and all 3,448 public choices. Both workers closed normally.
The validation scenario granted two titles through the native tuner operation.
The appointment cleared the consideration marker in a separate native witness.
The same public session resumed the turn-17 checkpoint and submitted three
offered forced ends of turn. GameCore advanced `turns_on_site` from 0 to 3 and
reported the Defender established at turn 20. The session saved and closed.
A fresh process restored the established governor in the same city with the
same promotions, public observation and all 36 public choices.

In a separate turn-17 branch the client appointed Amani and assigned her to
an already-met city-state. The native target and an owned city shared the
same numeric city ID. The command retained the destination owner and the
native readback confirmed the assignment. A fresh process restored her
destination, the public observation and all 3,458 public choices. The fixture
granted two governor titles and used the existing contact. The client then
submitted five offered forced ends of turn. At turn 22 the GameCore reported
Amani established and raised the player's envoy count in her assigned city-state
from one to three. A fresh process restored her assignment, the envoy count,
the same public observation and all 39 public choices. Reassignment and
neutralization effects still require qualification on this profile. The lab
retains separate receipts for
`host-xp1-installed-governor-save-reload-native.json` and
`host-xp1-installed-governor-establishment-save-reload-native.json`,
`host-xp1-installed-governor-city-state-save-reload-native.json` and
`host-xp1-installed-amani-influence-save-reload-native.json`.

The installed Rise and Fall LAN profile adds
`information("city_state_envoys", player_id=pid)` in catalogue
`v11.captured-city.v5`. Each row identifies a met, living city-state that can
receive influence and gives the observing player's own envoy count. The count
comes from the same native getter used by the City States panel. The group is
read-only and belongs to the cached player, turn and decision sequence.
Waiting boundaries return `InformationUnavailable`. A v4 checkpoint can
reopen through v5 when its historical observation and choices match exactly.

The same installed Rise and Fall LAN profile adds `decisions.envoys` in
`v11.captured-city.v6`, with the player's reserve, consideration state, and
the known city-states eligible to receive influence. It offers `retain_envoys`
when the native consideration blocker is pending and `send_envoy` for each
target approved by the engine. The T22 witness started with two tokens granted
through the official test command. Retaining kept both and cleared the blocker.
Sending spent one and raised the player's count in the selected city-state
from three to four. An ordinary independent reload restored the reserve,
counts, public observation and all 41 choices. A separate checkpoint saved
before consideration restored the reserve, both send choices, the pending
retention choice and all 42 public choices. On this image the native archive
omits the consideration flag. The host restores it with the native setter
only when the remaining envoy catalogue matches the authenticated checkpoint.
The restored retention choice cleared the blocker and kept both tokens.
Private lab receipts are `host-xp1-installed-envoy-choices-save-reload-native.json`
and `host-xp1-envoy-pending-checkpoint-save-reload-native.json`.

The installed Rise and Fall LAN profile adds
`information("city_state_levies", player_id=pid)` in `v11.captured-city.v7`.
It exposes the official cost and duration for met city-states, the active
levy status for the observing player, and the engine-approved
`levy_city_state_military` choices. On the T22 witness, the host quoted
100 gold for 15 turns, charged exactly 100 gold, and transferred control
of five units. A fresh ordinary process restored the observation and all
46 public choices. The private test setup used the official treasury
command to make the levy affordable. Per-unit time remaining and return of
control at expiry have separate lifecycle evidence. Private lab receipt:
`host-xp1-city-state-levy-save-reload-native.json`.

The subsequent `v11.captured-city.v8` catalogue adds
`information("unit_levies", player_id=pid)`. It returns the unit's current
owner, unit ID, the original owner when the official flag identifies it, and
the number of turns remaining. The rows are limited to the current own and
visible unit roster. Both the official unit-property path and the native
city-state counter path feed the same flag calculation. A waiting boundary
has no unit levy information. A v7 checkpoint can reopen with v8 when its
existing observation and choices compare exactly. On the retained LAN
lineage, the five units counted down from 15 turns at T22 to two at T35.
An independent process restored the same observation and choices at T33.
After the T35 save, the units had one turn of control remaining at T36.
GameCore returned all five to their original city-state at T37. The client
observed all five as foreign units and the levy flags cleared. GameCore
saved the T37 state and completed Unload and Destroy. A fresh process
restored the exact public observation and all 46 choices, including the
five visible returned units. Private lab receipts
`host-xp1-unit-levy-t35-save-native.json` and
`host-xp1-unit-levy-expiry-reload-native.json`.

On the installed Gathering Storm LAN image, pass `city_state_levies=True`
to `NetworkBackend` to expose both levy information groups and the same
`levy_city_state_military` action. The catalogue appends
`.military-levies.v1` to the underlying Gathering Storm schema. The
city-state panel reports the official eligibility, cost, duration and
active status. Unit flags follow the current public roster.

In the BBG 7.5.1 T52 witness, the client selected a native offer for
70 gold. GameCore charged the quoted amount and transferred three units
from city-state 2 for 15 turns. A new process reopened the save and
restored the exact public observation, choices and three unit flags.
Both processes closed normally. Expiry and gameplay with other mods
remain open. Private lab receipt
`host-xp2-bbg-military-levy-save-reload-native.json`.

In stock Gathering Storm, a T69 client chose Mysticism and sent an envoy
to city-state 4. At T70 it sent the envoy earned from that civic and the
native levy became available. GameCore charged the quoted 202 gold and
transferred three units for 15 turns. A new process restored the exact
observation, choices and three unit flags. The native archive omits the
envoy consideration bit. The host restores it with the official setter
when an authenticated checkpoint has an empty reserve and the other
influence fields match. Both workers closed normally. Natural expiry
remains open. Private lab receipt
`host-xp2-stock-military-levy-save-reload-native.json`.

The current-image v34 route with `governors_diagnostic=True` and
`trade_diagnostic=True` also supports Amani's BBG 7.5.1 city-state bonus in a
one-human LAN witness. The common client appoints and assigns her at T47 and
opens a route to her city-state at T48. At T52 the official script activates
the bonus and the origin city's public food and production increase. A new
process reloads the T52 checkpoint with the same public observation and active
route. Reassigning her to an owned city removes the bonus while the route
stays active. Both sessions save and close normally. Private lab evidence is in
`evidence/host-xp2-bbg-amani-native.json` and
`evidence/host-xp2-bbg-amani-reassignment-native.json`.

The XP2 v31 extension adds `decisions.envoys`: the player's token
reserve, consideration/blocker state, and known living city-state targets with
their native receive/send predicates and received counts. `send_envoy` submits
one selected target through the explicit XP2 player-operation ABI; `retain_envoys`
acknowledges the native consideration state without spending a token. A null
catalogue means unavailable during waiting/closure, not a known empty query.
The common client retains candidate identities and native ordering. Non-blocking
panel review and the full city-state/diplomacy interface remain separate scope.
On the retained Gathering Storm + BBG 7.5.1 lineage, the common client has
executed both actions: retention preserves the reserve and clears the native
consideration blocker; sending spends one token and increases the selected
city-state's count. The native engine produced the tokens while advancing from
turn 45 to 47 after an offered civic selection; no token injection was used.
Five scripted decision frames also pass the frozen recurrent actor with all
candidates intact. Save and normal destruction succeeded. The subsequent v32
governor session reopened this envoy state with its reserve, received count and
consideration state unchanged. Neither a complete diplomacy API nor a strategic
training scope is established by this qualification.

`civ6-host-client` is a Python standard-library client and public-contract package.
It has no PyTorch or lab import. The separately installed `civ6-host-runtime`
provides `LocalHotseatBackend` on Windows; see [backend setup](backend.md).
That runtime now executes the extracted `NativeHotseatActionSession`, not Python
from the old laboratory. Its local Base/hotseat round-trip is qualified with a
separate private resource package. General community setup, complete action
coverage, DLC and simultaneous commands remain unfinished.

For simultaneous play, the retained Internet saves provide three candidates
that declare exactly two occupied seats and a simultaneous turn phase. Each
declares Workshop content, and none matches a retained official capture with
the associated final databases and scripts. The saved seat count describes
configuration only. Qualification requires a live two-human roster and
separate player views, followed by interleaved commands, a contested action,
readiness transitions and the native turn boundary.

The read-only `civ6_host.runtime.session_configuration` command reports
`saved_multiplayer_candidate` for a hash-pinned official save or prepared
capture. It checks saved LAN mode, the explicit simultaneous phase and at
least two taken seats. A match is a capture candidate. The report leaves
live roster and native command qualification false.

The backend supplies bounded, source-validated `reset()`, `request(dict)` and
`abort(reason)` operations. The public client and contract can be used on
Windows/macOS; this does not make the Windows GameCore run on macOS or provide
a qualified remote transport by itself.

```python
from civ6_host import HotseatClient

# Supply a qualified backend. It owns the native child, private DBs and bounds.
client = HotseatClient(backend)
view = client.reset()
choices = view['decisions']
# Your controller chooses one of these candidate IDs; no fallback is inserted.
view = client.act(choices['decision_id'], chosen_candidate_id)
client.close()
```

Policy assignments are explicit: `parameters={'assignments': assignments}`.
Other actions retain their native candidate parameters. The host validates the
actual action and policy expansion. The client preserves every offered candidate;
it does not pretend the current catalogue covers all Civ6 actions.

The current wire schema is `civ6rl.hotseat_action_session923.v1`. Its historical
identity, sequence and catalogue digest semantics are preserved. Only the
hotseat profile is implemented here. This client's stale-catalogue rejection
must not become an invented rule for the future simultaneous protocol.

With `public_view_players=[0, 1]` configured on the backend, a live client also
offers `client.player_view(1)`: the selected human's public observation, revealed
map and own native activity flags at the latest accepted boundary. These views
were qualified for all four players at the first turn of Capture09 on the
installed Base profile. They contain no action catalogue
or privileged critic data, and do not authorize commands for an inactive player.
Refresh with `client.observe()`; see [perspective scope](backend.md#additional-human-perspectives).
Each player's controller must receive only its own view.

In the installed Gathering Storm LAN profile, enable `public_view_players`
and the existing `diplomacy_overview_diagnostic` setting to receive
`diplomatic_wars` in the `civ6-host.player-view.v2` view. Each row contains
`player_id` and `at_war` for a living major civilization the selected player
has met. The GameCore reads the flag in the selected player's perspective,
including for a human opponent. Other profiles retain the v1 view. To refresh
the defending player's state after a command, read `player_view(defender_id)`
at the new boundary. The relation contains no notifications or diplomatic
choices.

On the exact installed Base Capture09 profile, configure `LocalHotseatBackend`
with `checkpoint_on_close=True` and call `client.close()`. The administrative
`backend.checkpoint` reference becomes available after supervised close. It
identifies the private manifest for the native GameCore and configuration
streams. The player view carries neither the reference nor the raw streams.
Create another backend with the same capture, execution image and UI options
and pass `resume_from=backend.checkpoint`. Then
`HotseatClient(new_backend).reset()` returns the resumed public view with a new
episode identity. Set `checkpoint_on_close=True` on the new backend to write a
child checkpoint linked to the pair it resumed.

The native test restored player 0, passed control to player 1 and wrote a child
checkpoint. A fresh backend returned player 1's same observation and 21 choices.
Player 0's city remained visible in their own view, and player 1 founded a city
after the reload. This test covers the first handoff at turn one and one
checkpoint link. Resuming with players 2 or 3 active remains untested.


Returned views contain the player observation, offered choices, applied action,
episode/sequence identity and public termination/truncation classification.
They omit raw internal victory evidence, callback receipts, nonce and privileged
training sidecars. Full source, ABI and action validation remain the backend's
responsibility; this is not an untrusted remote-server authentication layer.

An uncertain exchange aborts the backend and requires reset. It is never retried
automatically: the action may already have been applied. A local stale/absent
choice is refused before sending. Reset must create a distinct native episode.

The installed local runtime is delivered for the stated retained scope. A remote
server transport, simultaneous session and independently prepared complete
community installation are not yet qualified.
# Captured LAN session client

The client recognizes `civ6-host.network-capability-decisions.v1`, `.v2` and `.v3`
during extension integration. These are partial family contracts, not admission
of a full XP1 session. Each `families` entry states `queried_complete` with the
exact IDs returned, or `unqualified` with a reason and no choice list. Version 2
also admits `queried_partial`, which must list its unqualified choices. The
ordinary production group uses this status for placements, wonders, formations,
purchases and queue editing. Research/civic queries enumerate direct exclusive
selections; they do not claim coverage of every research queue operation.
A completed query may legitimately return zero choices. The catalogue declares
`complete_action_space=false` and `family_inventory_complete=false`; it does not
pretend to enumerate every missing Civ6 feature. Missing information queries
remain unavailable rather than becoming zero-valued data. Session identity,
action selection and native outcome validation still use the common protocol.

Version 3 retains the choice-state contract and adds `turn_availability` for
`end_turn`, `force_end_turn` and `unready_turn`. Each value is `true`, `false`,
or `null` for an unqualified UI branch. A corresponding family and its exact
candidate IDs must agree. Waiting does not suppress native turn controls.
Forced EndTurn follows the source-checked Shift+Enter handler; strategic choices
are not removed because another action would appear preferable. The captured
XP1 cycle has executed forced EndTurn and `poll` through the next active turn,
then closed and reset; normal/Unready execution remains separately unqualified.

The portable client and server share the same v3 exception for a forced-turn
offer while the local player is inactive. If the official request is serialized,
received and dispatched but the sampled turn controls remain unchanged, that
qualified XP1 path returns `command_result.status="submitted"`,
`reason="native_turn_controls_unchanged"`, and `applied_action=null`.
This is evidence of delivery, not a network acknowledgement, a completed
gameplay effect, or proof that all game state stayed unchanged. The caller can
continue to observe or explicitly poll; the host does not invent another update.
Other unresolved requests retain their strict failure behavior.

Version 4 adds `world_input` and `queued_orders`. The first contains the owned
unit roster, `ignore_moves`, selected unit ID, map geometry and no admitted war
prompt. The second exposes each owned unit's native queued destination or null.
Both fields are null at waiting/closed boundaries, with the corresponding
families explicitly unqualified. They are available through the same
`client.view()["decisions"]` response; no learner or model chooses them.

The caller selects `world_select_unit`, `world_plot_click`, or
`world_deselect_unit` by candidate ID. Every grid coordinate is offered for a
selected eligible own unit, regardless of visibility or remaining movement.
The existing transport budget separates up to 4,096 ordinary actions from up
to 16,384 map coordinates. `world_plot_click` is `queried_partial`: current XP1
non-MOVE_TO and war-confirmation branches return `refused`, reason
`native_world_input_branch_unqualified`, and no applied action. This is a host
coverage limit, not native illegality or a strategic decision.

For expansion LAN sessions, a delivered `MOVE_TO` with unchanged player
observations and no matching native queued destination returns `refused`
with reason `native_world_move_effect_unobserved`. The delivery archive
remains in the administrative receipt. UI-only no-ops retain their
existing completion status.

The captured native group moved unit 131073 from (42,29) to (42,28), with movement
points changing from 2 to 1. Clicking its current plot produced an official
no-op with no archive. Selection/deselection, refreshed own queue information,
native close and a fresh reset were also authenticated. All queued destinations
in this witness were null; a nonempty queue/cancellation and broader movement,
combat or unseen-target behavior are not established by this group.

Version 5 retains those fields and adds `unit_orders`: own-unit `activity_type`
(signed native 32-bit value), `fortify_turns`, `ready`, and the native offers with
their `legal` Boolean. A `unit_order` action identifies `unit_id`, `route`,
`item_type` and `hash`. Reviewed routes are command WAKE/CANCEL and operation
SLEEP/FORTIFY/HEAL/RELIGIOUS_HEAL. Only legal native offers become selectable
candidates; the host does not infer availability from readiness or moves. The
family remains partial, with other orders and spy cancellation explicitly
unqualified. Waiting/closed boundaries return null, not an invented empty query.

Gathering Storm v19 adds the native `UNITOPERATION_SKIP_TURN` offer with the
same action shape. It acts on one unit. The retained witness leaves the unit's
four moves intact, clears its ready flag on turn 44 and restores readiness on
turn 45. The v18 checkpoint produced after the Slinger attack was the input.
Its public observation and historical offers were preserved on reload.

Gathering Storm v20 adds `plot_purchases` to the same decision catalogue. Each
owned city's ordinary tile purchase panel contributes its native target and
quote with `command_legal` and `can_afford`. Only offers with both flags set are
selectable. A `purchase` action carries `city_id`, `plot_id`, `x`, `y`,
`currency="YIELD_GOLD"` and the original `price_token`. Pass its candidate ID
with the current decision ID to `SessionClient.act`. The host requeries the
offer before delivery and confirms native ownership by the selected city.
Waiting or closed sessions return null for this query. The partial purchase
family lists unit, building, district, faith and placement-filtered purchases
as gaps in this profile.

Gathering Storm v21 also provides `city_purchases`. Each owned city contributes
its visible standard-unit and building offers from the gold purchase panel.
Those offers use the same `command_legal` and `can_afford` flags as tile offers.
A unit or building `purchase` identifies its `city_id`, `category`, `index`,
`hash`, `item_type`, `currency` and `price_token`. The host requotes the
selection, then confirms the new owned unit or building possession after native
delivery. Separate turn-56 resumes confirmed a Scout for 60 gold and a Barracks
for 180 gold. District, faith, corps, army and placement-filtered purchases
remain explicitly unqualified in this catalogue.

Use `SessionClient.information("purchase_quotes", player_id=pid)` to read the
current player's exact tile and city quotes together with their decision ID.
Tile quotes use gold. Unit and building quotes use the currencies the current
profile supports, with separate native legality and affordability flags. Older
tile-only profiles omit `city_purchases`. A queried city with no offers has an
empty `offers` list. The read uses the cached observation and raises
`InformationUnavailable` if the current boundary has no purchase catalogue.

The development v22 Gathering Storm catalogue adds `unit_promotions`. It
reports native experience points and acquired promotion indices for each
owned unit, plus the offers returned by the game's promotion query. Each
`promote_unit` candidate identifies its `unit_id`, native selector `index`,
definition `hash` and `item_type`. Submission rechecks the current offers and
passes the selector index to GameCore. The host verifies acquisition before
reporting success. Waiting or closed sessions return null for this query.
Loading an older checkpoint compares its historical fields separately from
the new family. The v22 source runtime resumed a v20 checkpoint, advanced
from turn 45 to 48, and gained 12 XP for a Slinger across three ranged attacks.
The player applied the offered `PROMOTION_VOLLEY` at 15 XP. The engine's
`UnitPromoted` notification was consumed, the client read the acquired
promotion, and the host saved and destroyed the session normally. The v22
wheel pair installed outside the source checkout restored the same turn,
observation and catalogue in a fresh process, kept promotion index 14 acquired
and saved a successor. A subsequent installed process used the relocated
private resources and 27 retained checkpoints, again restoring the acquired
promotion and saving a successor. Private evidence:
`evidence/host-xp2-native-unit-promotion.json`,
`evidence/host-xp2-installed-v22-promotion-resume.json` and
`evidence/host-xp2-installed-v22-relocated-lineage.json`.

The development v23 Gathering Storm catalogue adds `unit_upgrades` for owned
units. A visible offer gives the native target type, gold quote, and strategic
resource type and quantity when the official panel shows one. Offers that are
visible but disabled stay in the catalogue, and only legal offers have an
`upgrade_unit` candidate ID. The host requotes the choice before using the
official command and checks that the engine replaces the selected unit with
the quoted type. Waiting or closed sessions return null. On a v22 restore,
the new family is excluded only from the comparison with the saved catalogue.
The original checkpoint data and identity are kept.

The v23 source runtime restored a v22 save, performed the offered Slinger to
Archer upgrade for 30 gold on turn 50, and saved the new unit with its 15 XP
and Volley promotion. The isolated v23 wheel installation restored that
observation and catalogue in a new episode with the original private
resources, then saved a successor. In a separate native turn-60 session,
a Warrior was upgraded to a Roman Legion for 75 gold and five iron. The
official stockpile getter returned six iron before delivery and one afterward.
Native Save and Destroy completed. The stockpile readback belongs to the
diagnostic receipt and the new turn-60 checkpoint awaits restoration.
Private evidence:
`evidence/host-xp2-native-unit-upgrade.json` and
`evidence/host-xp2-installed-v23-unit-upgrade-resume.json`, plus
`evidence/host-xp2-strategic-upgrade-native.json`.

Gathering Storm v24 adds the public `strategic_resources` group to the same
decision boundary. Read it with
`client.information("strategic_resources", player_id=player_id)`. It returns
the player's visible positive-capacity TopPanel rows, including stockpile,
capacity, reserve, accumulation and consumption. The source and demand
breakdowns follow the corresponding tooltip conditions. A disabled panel
returns `panel_enabled=False` with an empty list. An enabled panel can also
have no eligible rows.

The group does not use the viewport width or icon layout. It covers the
ordinary positive-capacity rows, including when those rows move into the
overflow tooltip. Historical checkpoints retain their original contract.
A v24 readback projects out this one new field only for comparison against
the saved version. The source runtime restored the turn-60 Legion, read one
iron with capacity 25 and extraction of two per turn, then saved the v24
catalogue. The installed client replayed that public response. Private
evidence: `evidence/host-xp2-public-strategic-resources-native.json`.

Gathering Storm v25 adds `policies` to the common `SessionClient` catalogue.
At a qualified acting boundary it reports the player's native free-change
window, current slot indices and available cards for each slot. An available
changed assignment is one factorized `policies` candidate. The API does not
enumerate combinations or select cards for the caller. Submit one unsigned
policy hash per slot, in the published slot order:

```python
menu = view['decisions']
candidate = next(row for row in menu['candidates']
                 if row['action']['kind'] == 'policies')
# Choose the hashes from candidate['action']['slots']; fill every slot once.
view = client.act(view['observation']['player_id'], menu['decision_id'],
                  candidate['candidate_id'],
                  parameters={'assignments': chosen_unsigned_hashes})
```

The runtime requeries native availability, submits `RequestPolicyChanges`,
delivers its native message and checks every resulting `GetSlotPolicy` index
before reporting completion. The v25 catalogue retains v24 fields and declares
the two remaining gaps: `paid_policy_unlock` and `active_policy_relocation`.
Inactive or closed decision boundaries publish no policy query. A card's mod
identifier is preserved, including names that do not begin with `POLICY_`.

The local BBG 7.5.1 witness assigns Discipline and God King at turn 21, reads
indices 0 and 2, saves and restores the same public state and semantic menu in
a fresh process, and closes both lifetimes normally. A new session resets its
sequence to zero. This covers that free two-slot assignment, not every policy,
government, paid unlock or mod interaction. Private evidence:
`evidence/host-bbg751-native-policy-assignment.json`.

The v26 catalogue also publishes `policy_unlock` at a qualified
acting boundary. Its fields are `player_id`, `turn`, `cost`, `currency`,
`reason` and `can_unlock`. The selected currency is `YIELD_GOLD` or
`YIELD_FAITH`; full native wallet precision stays in administrative evidence.
When the official UI gate and native `CanStartPlayerOperation` both allow it,
the distinct candidate is `{'kind': 'policy_unlock', 'cost': ..., 'currency': ...}`.
It takes no extra client parameters. The implementation submits the exact
registered operation with an owned empty native parameter map, then requires
both a zero unlock cost and the matching native currency debit before completion.

The BBG 7.5.1 control resumes the prior free assignment at turn 21, selects
Craftsmanship, then State Workforce after Craftsmanship completes. At turn 23,
the native operation debits 55 gold and opens free replacement. The caller then
selects Survey and Urban Planning. The source-qualified CivicsUnlocked event
is retained and consumed in the existing FIFO. A separate process reloads the
saved result with the same public state and choices; both lifetimes close
normally. The six actions also pass through the existing recurrent actor and
collector using the exact native receipts. Private evidence:
`evidence/host-bbg751-native-policy-unlock.json`.

This qualifies that gold-funded action in one single-human LAN lineage.
Faith-funded execution, active-card relocation, general government changes,
official multi-turn comparison and multi-human scheduling remain separate
qualifications. The historical zero-cost controls and explicit callback refusal
remain preserved. This delivery establishes no new PPO campaign or playing gain.

The v27 catalogue adds `government` at an acting XP2 boundary. Its fields are
`player_id`, `turn`, `current_index`, `can_change`, `changed`, `civic_completed`,
`considered`, `consideration_blocker` and `choices`. Every government row retains
its `index`, unsigned `hash`, `unlocked`, `can_change` and `anarchy_turns` values,
including locked and predicted-anarchy choices. Waiting/closed views return null.

The `government` family is explicitly `queried_partial`, with
`unqualified: ['anarchy_transition']`. Direct non-anarchy changes use the official
global and per-target UI gates and expose `{'kind':'government','index':...,'hash':...}`.
The separate `{'kind':'retain_government','index':...}` acknowledges the existing
government only when its consideration blocker is present. Neither action takes
additional parameters. A request is not reported complete until native readback
confirms adoption or consideration; the latter must remove that specific blocker.

In the retained BBG 7.5.1 LAN world, the native continuation reaches turn44,
adopts Classical Republic, refreshes four policy slots and assigns four cards.
The separate consideration action then keeps government3 and clears its blocker.
Both saved results reload with equal public observations and choices. All five
bounded native lifetimes close normally. The 31 scripted native decisions also
pass the unchanged actor dimensions and the existing learner interval validator;
this is not a new curriculum episode or PPO campaign. Other government effects,
anarchy, active-card relocation, official comparisons and multi-human scheduling
remain separate qualifications. Private evidence:
`evidence/host-bbg751-native-government.json`.

The v28 catalogue extends the same changed-assignment `policies` action to active-card
relocation. `policies` is `queried_complete` at a queried acting boundary;
v25/v26/v27 retain their earlier relocation gap and selection rules. Parameters
stay `assignments`, one unsigned policy hash per slot. Cards currently active in
another slot use the pinned official screen's row-type rule and actual native
slot types; inactive cards still require native `CanSlotPolicy`. The existing
request clears all slots before additions, and native slot readback verifies
the result. The catalogue offers confirmation only if a complete, changed,
unique assignment exists, including alternating swaps and cycles.

The bounded BBG 7.5.1 witness swaps two already active economic cards at turn45:
slot indices change from `[2,3,0,1]` to `[3,2,0,1]`. Native Save and an independent
process reload preserve the same observation and choices. Both lifetimes close
normally under 512 MiB. Twelve replies replay through `SessionClient`; the two
ready decision frames pass the unchanged v15 actor encoder, frozen scoring and the retained interval
validator. This is scripted native execution and model I/O qualification, not
a new learning campaign or autonomous actor-selected relocation. Other slot
types, policy interactions, official comparisons and independent worlds remain
separate qualifications. Private evidence:
`evidence/host-bbg751-native-policy-relocation.json`.

The UI round-trip that removes and restores a card before confirming the same
final assignment remains excluded by the historical changed-only v28 contract.
The v29 contract admits that complete unique assignment without changing the
`assignments` parameter. Older versions retain their previous semantics.

The bounded BBG 7.5.1 witness confirms the same four cards at turn45. Native
`PolicyChangeMade` changes from false to true while slot indices stay
`[2,3,0,1]`; matching slots alone would not prove confirmation. Native Save and
a fresh process reload preserve the observation and choices. Both native
lifetimes close normally under 512 MiB. Twelve client replies replay successfully;
two ready decision frames pass frozen actor scoring, and two native intervals
pass the existing rollout validator. This adds no PPO update or autonomous
actor-selection witness. The two reference checkpoints preserve learned state
through explicit source-only transitions. Private delivery evidence:
`evidence/host-bbg751-native-policy-reconfirmation.json`. It closes the scoped
gap recorded in `evidence/host-policy-unchanged-confirmation-gap.json`;
other policy interactions and general gameplay coverage remain separate.

The v30 catalogue adds city unit/building purchases with `YIELD_FAITH`. An item
may have separate gold and faith quotes and candidate IDs; the published native
legality and affordability flags select candidates. Unaffordable quotes remain
catalogue data. Tile purchases still require gold. Earlier catalogue versions
retain their gold-only city-purchase contract. Checkpoint comparison removes
only the new faith offers from a validated comparison copy when matching an
earlier schema; the live catalogue keeps them.

The XP2 adapter reuses the pinned official purchase command, cost and wallet
APIs, re-quotes the selected currency and dispatches the exact action through
the shared provider. This group verifies source correspondence, contract,
dispatch fixtures and model inputs. It does not include a positive native XP2
faith-purchase witness. The purchase family stays `queried_partial` and lists
`faith_purchase_native_effect` explicitly alongside the other remaining routes.
No complete purchase coverage or strategic-training admission follows.
Private evidence: `evidence/host-xp2-faith-purchases-api.json`.

The subsequent native v30 readback resumes the registered BBG 7.5.1 turn45
checkpoint with its original query-control options, matches its observation
and historical decision fields, saves and closes normally. Fourteen city
purchase quotes are present, all gold; no faith offer exists at that boundary.
The actual view passes the frozen actor with all 91 candidate IDs preserved.
No gameplay action or turn was executed, and the newly saved v30 checkpoint
has not been reopened. This qualifies that native query/lifecycle scope, not
a positive faith purchase or production simulation throughput. City-query
activation remains a separate explicit admission. Private evidence:
`evidence/host-bbg751-v30-native-query.json`.

The XP2 update's immutable cache-source proof is now shared through its
synchronous FIFO drain and cache publication. Full dependency verification
remains at entry and exit; each record still checks live context ownership,
locks, callback slots, record layout and sequence. The event-reader scope and
guarded-callback timing remain limited to the actual GameCore update. This
changes neither the API schema nor the available actions or observations.
The retained v27 comparison matches eleven public replies across four actions
and six native updates, from turn23 to the active player at turn24, then saves
and closes normally. This is an instrumented single-world regression and timing
comparison, not a sustained production benchmark or a new training admission.
Private evidence: `evidence/host-bbg751-update-publication-throughput.json`.

The current captured XP1 group executed FORTIFY then the offered CANCEL to leave
fortification. It selected the same unit, clicked (45,26), observed native queued
destination 1969, and cleared it with another CANCEL. Deselection, native close
and a fresh reset restored the initial observation, choices, world/queue and
order states. Six public inputs delivered four native archives. WAKE and healing
orders were not executed in this witness; it proves neither healing over turns
nor complete unit gameplay. The first two interrupted attempts are retained:
an inherited parent admission gate rejected CANCEL offers, then the test wrongly
required WAKE instead of using the natively offered release command.

The Gathering Storm v18 witness resumes a wounded Warrior and executes its
offered `UNITOPERATION_HEAL`. The order changes activity and fortification
while damage stays at 33. Forced end turn reduces damage to 18 before later
damage events and turn-40 reactivation. The retained same-seed route without
the order also heals 15 HP. The host saves the final state and closes normally.
This witness covers friendly land and one turn. Evidence:
`evidence/host-xp2-unit-heal-turn.json` in the private lab.

Version 6 adds `production_queues`: one existing public-v2 queue row per owned
city, with ordered entries, formation display markers and native offers.
`queue_append` uses an explicit `append` or `replace_tail` mode; `queue_remove`
uses `position`; `queue_swap` uses `source_position` and `destination_position`.
The caller selects these candidates through the same `SessionClient.act` API.
Positions and the complete published queue are revalidated before native BUILD
submission. Waiting or closed boundaries return null, never a fabricated empty
queue. Append remains explicitly partial for placement-required items and
nonstandard formations; remove and swap enumerate their native offers.

The captured XP1 group filled an empty queue to eight entries, visibly swapped
distinct entries, replaced the last slot, removed an entry, closed and reset
in a fresh process. It establishes these gestures and their current public
readback; production completion/accumulation and interactions over turns need
separate qualification. This does not fabricate the Base production information
groups for XP1: only the fields actually queried are exposed.

Version 7 adds native `placement_offers` for `production_placement` and
`production_resume`, plus `placements` with the explicit `host_tracked` scope.
These progress rows describe placements remembered by the host; they are not
an inventory of every construction loaded from a saved game.

Version 8 adds a separate `placement_inventory` envelope with `schema`, `scope`,
`player_id`, `turn` and `rows`. Its `native_visible_own_city` scope contains native
district or placed-building identities on currently visible plots belonging to
the player's cities. Rows expose `city_id`, `category`, `index`, `hash`,
`item_type`, `plot_id`, `x`, `y`, `complete` and `district_id` (null for buildings).
Completion comes from the native district/building query; no placement date or
completion threshold is inferred. City centers and internal districts are
outside this construction-placement scope.

The reader does not use host placement tracking or action offers to discover
these rows. An empty list means the native read found none in its declared
scope; a null envelope means unavailable. It can read while actions are closed
or the player is waiting. Resume legality still comes independently from the
official `placement_offers`; this inventory grants no additional actions.
Older v5/v6/v7 checkpoints retain their original bytes and schemas, with an
explicit comparison of their historical fields against the current catalogue.
The grouped native v8 witness saved an unfinished Holy Site, reloaded and resumed
it, then reset in a third process. Inventory and qualified choices matched after
both Loads. Tracking was preserved by the checkpoint, although it is not an input
to this reader. Zero retained progress was witnessed; completed constructions,
wonders and a native empty-tracking Load remain unqualified. Evidence:
`evidence/host-xp1-placement-inventory.json` in the private research lab.

The development combat catalogue adds `unit_attacks`: own-unit moves/damage and
attacks remaining, visible city defenses, public war relationships and exact
native plot-order offers. `unit_attack` names its unit, operation, input route
and target plot/coordinates. It never selects the defender. The family remains
explicitly partial for war confirmation, air and other unqualified input routes.
Source/fixture integration and native queries alone do not qualify an attack.

Version 9 is retained as a diagnostic format: its city defense strength includes
native fractional precision. Version 10 applies the official displayed rounding,
`floor(raw + 0.5)`, and preserves raw values separately. The portable
`client.information('combat')` projection uses the displayed precision.
Base hotseat uses the same public `combat` group on its supported decision
catalogues. The group retains the current player's queued orders, visible
city defenses and exact offered attacks. Its decision ID is the same one
returned by the player view. Select the exact candidate with `act()`.
On an explicitly enabled XP1 or XP2 administrative backend,
`SessionClient(backend, allow_administrative=True)` followed by
`client.information('combat', channel='administrative')` can additionally return the
source-pinned raw city readback, joined to the same episode, generation, player,
sequence and turn. This does not enable unqualified expansion production/growth admin
groups. Native requests and their internal verification retain the raw state;
public offers and stale-state guards do not incorporate the hidden fractions.

Loading a diagnostic v9 checkpoint under v10 requires an exact fresh raw
readback for historical comparison. Its saved bytes are preserved. The first
native contact preparation retained real exploration but reached no attack and
advanced no turn; that historical attempt remains in
`evidence/host-xp1-unit-attacks-attempt26.json`.

The later v11 witnesses qualify one offered melee enemy-flag attack on the
exact XP1 profile and one on the exact XP2 profile. The XP2 group prepares a
turn-5 native checkpoint, executes the offered `unit_attack`, reads the actual
damage and consumed action points, closes, and resets to the same checkpoint
in a fresh process. `information()` requires an active client; query it before
`close()`. Two XP2 information reads were live, with the reset read validated
through a read-only replay. Evidence: `evidence/host-xp2-unit-attacks.json`.

The Gathering Storm v18 client also exercised the dedicated `RANGE_ATTACK`
route. A Slinger ordered at turn 43 fired on a visible enemy at turn 44.
The target's damage increased from 20 to 58. The Slinger stayed on its plot,
used its attack and movement, and the offer disappeared. The host saved the
public result and closed normally. The new checkpoint has not been reloaded.
Evidence: `evidence/host-xp2-ranged-unit-attack.json` in the private lab.
Other attack routes and complete combat remain unqualified.

On the current Gathering Storm image, the dedicated ranged route can return
`command_result.status == 'submitted'` with reason
`native_ranged_attack_order_added`. The native archive and the isolated
`UnitOperationAdded` event identify the selected order. The immediate public
observation has no verified combat effect and `applied_action` is null.
The client can continue with the new catalogue. Use later observations to
track the unit and target.

On the installed Gathering Storm + BBG 7.5.1 profile, an offered
`unit_attack` with `operation='RANGE_ATTACK'` and
`input_route='dedicated_ranged'` hit a visible, unwalled city at turn 42.
The public `unit_attacks.cities` row for the same target gained 18 garrison
damage. The Archer stayed on its tile and spent its remaining attack.
The subsequent close with checkpoint enabled was refused while BBG trade
feedback was pending. The attack receipt and the save outcome are separate.
Evidence: `evidence/host-xp2-bbg-city-ranged-hit-native.json` in the private lab.

In the recorded continuation, an explicit end turn and native polls advanced
to turn 43. BBG removed the ended city-state trade route from its gameplay
property before the next checkpoint. Save and close succeeded, and a fresh
client loaded the same public observation and choices. The city had already
healed during the turn transition, so this witness covers saving and loading
the next turn. Evidence: `evidence/host-xp2-bbg-city-hit-post-turn-save-reload.json`.

From that turn-43 checkpoint, the separate `input_route='world_plot'`
ranged offer also executed against the same city. This time the checkpoint
was written before ending the turn. A fresh process restored all 18 points
of garrison damage and the Archer's spent attack in the public combat view,
with the same observation and choices. Evidence:
`evidence/host-xp2-bbg-world-plot-city-hit-save-reload.json`.

In the same profile, an offered `MOVE_TO` attack via `world_plot` against
the city added 16 garrison damage at turn 45. The Warrior took 55 damage
in the same command. A second melee attack at turn 46 added 12 damage and
removed the Warrior from the own-unit roster. The private native
`UnitKilledInCombat` record independently identifies the Warrior and
defending district. City ownership stayed unchanged in both attacks.
Evidence: `evidence/host-xp2-bbg-city-melee-retaliation-native.json`.

The installed Rise and Fall LAN profile offers occupation under
`civ6-host.network-capability-decisions.v11.captured-city.v1`. At turn 16,
the ordinary client submitted an offered `MOVE_TO` assault via
`world_plot` against an unwalled city. GameCore transferred the city,
offered `KEEP` and `RAZE`, and executed the selected `KEEP` through
`resolve_captured_city`. A separate ordinary worker reloaded the native
save and restored the owned city, empty occupation menu and all 3,451
choices under a fresh session identity. The private fixture placed the
assailants through GameCore. The witness is retained in
`evidence/host-xp1-installed-city-keep-save-reload-native.json`.

An independent assault from the same turn-16 starting checkpoint used the
offered `RAZE` directive. GameCore confirmed that the visible city tile
was empty. A separate ordinary worker restored the empty tile, the empty
occupation menu and all 3,438 choices under a fresh session identity.
The witness is retained in
`evidence/host-xp1-installed-city-raze-save-reload-native.json`.

The same Rise and Fall LAN profile also offered `LIBERATE_FOUNDER` after
the client captured a Free City while at peace with its founder. GameCore
returned the city to player 1. A separate ordinary worker restored the
returned city, empty occupation menu and all 3,437 public choices. The
private test fixture created the city, transferred it to Free Cities and
placed the assailants. Evidence is retained in
`evidence/host-xp1-installed-city-liberate-founder-save-reload-native.json`.

At turn 17 the same profile offered `LIBERATE_PREVIOUS_OWNER` after the
Python client recaptured a city from player 1. GameCore returned the city to
player 2 and cleared the pending choice. An ordinary worker reloaded the
returned city and all 3,442 public choices under a fresh session identity.
The private fixture prepared the first conquest and placed the assailants.
The four occupation directives now have native save-and-reload evidence on
distinct prepared scenarios in this profile. Evidence is retained in
`evidence/host-xp1-installed-city-liberate-previous-owner-save-reload-native.json`.
The pending occupation choice also has a native persistence witness. An
ordinary worker reloaded the menu at turn 17, offered the same previous owner,
accepted the explicit selection for player 2 and wrote a distinct child
checkpoint. That witness is
`evidence/host-xp1-installed-previous-owner-pending-save-load-native.json`.
A third ordinary worker reloaded that child at turn 17. It returned the city
in player 2's ownership, the empty occupation menu, the same public
observation and all 3,443 choices under a fresh identity. It closed the native
context normally. The run exercised the installed Rise and Fall LAN profile
with one controllable human and a prepared conquest scenario.
Evidence is retained in
`evidence/host-xp1-installed-previous-owner-liberation-chain-public-reload-native.json`.

For both expansions, the host checks the captured command archive against
the acting player, selected city and exact directive before delivering it
to GameCore. The same check applies to the secondary LAN seat.

Use `information("captured_city")` on an observed hotseat or LAN player
to read the current occupation choice. The response identifies the cached
player, turn, sequence and decision. It includes the city coordinates and
the recipients of the offered liberation choices. An available query with
no pending city returns `city: null` and an empty list of directives.
A boundary without this information raises `InformationUnavailable`.
Use the decision and candidate IDs from the player view when calling
`act()`. The hotseat client keeps native occupation history inside the
transport and uses a decision ID derived from the public catalogue.

The current GS + BBG 7.5.1 v42 catalogue adds `captured_city` and the
`resolve_captured_city` family. An available query can report no pending
city. An unavailable query returns null. Choose an offered directive with
`act()` using its normal decision and candidate IDs. The query carries
only the city and recipients of offered liberation choices. The host
checks the same native pending city and directive again before issuing
the original city command. A completed receipt means the decision left
the native pending selector. KEEP also requires the city in the player's
own-city observation. RAZE requires the native Gameplay lookup to find
the selected city before delivery and an empty tile after it. Both
liberation directives require native readback of the offered recipient as
owner of the selected city tile. The readback checks the action's target
without exposing other gameplay state.

All four captured-city directives have native witnesses on this profile.
The RAZE witness confirmed a visible tile without a city and identical
public state after Save and reload. The liberation witness returned a
visible city to its founder, saved the resulting native state, and
restored the same visible city and player decisions in a second process.
The previous-owner witness starts from a captured city in a private
scenario prepared with native occupation and peace services. The stock
menu offered player 2 as the recipient. The common client selected that
candidate and GameCore transferred the city. An independent reload
restored the same visible city and complete public catalogue with no
occupation decision pending. The assailant was placed for these tests.
The founder scenario used the official Free Cities test operation.

On the registered current Gathering Storm capture without BBG, the
`standard_trade=True` session exposes the same captured-city fields and
candidate selection under the `standard-trade-captured-city.v1` through
`.v4` catalogue schemas. Each schema preserves the groups of its
corresponding `standard-trade` version. An earlier checkpoint can migrate
when the engine reports no pending capture and its existing decisions
compare exactly. A pending capture requires a checkpoint that already
records that choice.

The standard v4 witness restored the original turn-72 observation and all
135 previous choices, queried an empty pending-capture list in GameCore,
and saved the extended catalogue. A separate worker restored that new
checkpoint with the same observation and decisions. This witness has no
pending city to resolve.
Evidence: `evidence/host-xp2-stock-captured-city-catalogue-native.json`
and `evidence/host-xp2-stock-capture-checkpoint-reload-native.json`.

A second standard v4 witness used three offered `MOVE_TO` assaults via
`world_plot` to capture an existing city at turn 72. GameCore offered
KEEP and RAZE. The client chose KEEP, the pending choice cleared, and
the city stayed in the own-city observation. A fresh worker reloaded
the new checkpoint with the same city, observation, and 186 choices.
The private fixture placed the assailants. The assaults and occupation
choice went through the ordinary client.
Evidence: `evidence/host-xp2-stock-city-keep-save-reload-native.json`.

The alternative RAZE branch confirmed an empty target tile in GameCore
and in the player's view. A fresh worker restored the empty visible
tile, the same observation, and all 135 choices.
Evidence: `evidence/host-xp2-stock-city-raze-save-reload-native.json`.

The stock founder branch used the official Free Cities test operation
to prepare the city history. The client captured the city and selected
LIBERATE_FOUNDER with player 3 as the offered recipient. GameCore
confirmed the transfer and a fresh worker restored the same visible
city, observation, and 133 choices.
Evidence: `evidence/host-xp2-stock-city-founder-save-reload-native.json`.

The stock previous-owner scenario prepared a private support city and
occupation history. At turn 73 the public client recaptured the city
and selected LIBERATE_PREVIOUS_OWNER. GameCore transferred the city to
player 3. An independent worker reloaded the resulting checkpoint without
the test setup and returned the same visible city, observation and 1,295
choices. Both workers closed their native contexts normally.
Evidence: `evidence/host-xp2-stock-city-previous-owner-save-reload-native.json`.
Local evidence:

- evidence/host-xp2-bbg-city-keep-save-reload-native.json
- evidence/host-xp2-capture-registered-callbacks-native.json
- evidence/host-xp2-bbg-liberation-founder-native.json
- evidence/host-xp2-bbg-liberation-founder-save-reload-native.json
- evidence/host-xp2-bbg-liberation-previous-owner-save-reload-native.json

Rise and Fall includes optional city queries in its existing v11-based
decision catalogues when explicitly configured with
`city_focus_diagnostic=True` and `city_management_diagnostic=True`.
Gathering Storm supports those options from v14. The client exposes
`city_focus_catalogs` and `citizen_catalogs` when these options are selected. Select a
`city_focus` or `city_citizen` candidate with the usual `act()` call.
The Gathering Storm witness founded a city, cycled its production priority
through favored, disfavored and neutral, locked and unlocked one worked plot,
and closed normally. The witness starts from the original capture. Native
specialist clicks, v12 Save and reset, and Rise and Fall execution remain
pending. Historical v11 checkpoints retain their original catalogue contract.
When enabling these city queries on a saved v11-based session, the restore
comparison still requires the saved observation and all previously available
decisions to match. The returned catalogue includes the newly queried groups.

On the installed Rise and Fall image `xp1-gamecore-current-63c17d9`, these
options now prepare the same city decision and command adapters. The parent
and worker require the exact current DLL and its city-control source pins.
The installed DLL's 42 function fragments and five registered bindings have
been checked against the retained sources. Native city-control execution and
Save on this image remain to be verified.

The exact BBG 7.5.1 Gathering Storm bundle also accepts these city query options
in the v30 catalogue and public display-v2 view. Enabling a previously unqueried
family on resume adds only its observed fields and candidates. Checkpoint
comparison uses a detached projection of previously known fields; existing
focus/citizen data, every other decision and the live catalogue remain intact.
The transition is explicitly recorded with its query opt-ins. Query options do
not authorize changing saved gameplay state.

BBG city availability uses its own captured multiplayer/tutorial/control witness
and the inherited official handlers. The numerical API queries owned native
cities and MANAGE targets; selecting a graphical city panel is presentation
navigation. Each command still requires a current offered candidate and native
revalidation. A turn-45 BBG witness executed production focus and locked one
worked plot, then saved and closed normally; its 125 candidates were retained
by the recurrent actor consumer. Saved-state re-opening is tracked separately.
The resulting checkpoint was then reopened in a second native process: the
production-favored flag and the worked-plot lock were preserved, and all
previously published decision fields matched. Both processes saved and closed
normally. Private proof: `evidence/host-bbg751-city-controls-native.json`.
The retained stock XP2 specialist witness does not imply that this BBG group
assigned a specialist. Complete gameplay and multi-human scheduling remain
separate qualifications.

The Gathering Storm LAN backend uses v14 for city and district ranged attacks. The
`city_shots` catalogue contains the owned shooters and native target plots
while the player can act. Select `city_range_attack` with the usual candidate
ID and read the detached receipt through `client.command_result`. The engine
selects the defender on the target plot. The turn 38 witness applied 18 damage,
removed the used shot from the catalogue, and restored the resulting
observation and action catalogue from a checkpoint in a fresh process.
Both sessions closed normally. The separate `district_shots` catalogue offers
`district_range_attack` for eligible districts. At turn 43 the completed
Encampment offered three targets. One selected shot applied 20 damage, was
removed from the catalogue, and was recorded in the checkpoint before normal
close. A fresh process restored the same observation and action catalogue,
including the 20 damage and the used shot's unavailability, then closed normally.
Earlier checkpoints compare their historical fields before adding either catalogue.

Version 2 adds `choice_state`: native current technology/civic indices (or null)
and each owned city's current production identity, formation and queue count.
It does not expose unqualified raw cost/progress precision or invent missing
display estimates. Unavailable acting boundaries return no choice state.

The exact XP1 capture completed a seven-command native client cycle: foundation,
research selection/replacement, the already selected civic's actual native
request, and unit/building/unit production replacement, followed by native close
and an independent reset. `input_profile="xp1-lan"` selects its exact source
bindings on `NetworkBackend`. That earlier choice-only delivery did not admit
turn pumping; the subsequent captured turn cycle is described above. Complete
expansion gameplay and other action families remain unqualified.

The source runtime also exposes `civ6_host.SessionClient` with
`civ6_host.runtime.backend.NetworkBackend`, using `civ6-host.session.v1`.
It reuses the existing bounded process supervisor, official loader and action
adapters. The qualified local scope is one exact Base LAN capture containing
one human and five AI: reset, public choices for player0, native founding,
research, civic, production and unit-skip choices, EndTurn, explicit updates to
the next active turn, controlled close and replacement reset to the saved turn.

```python
client = SessionClient(backend)
view = client.reset()
player_id = view['observation']['player_id']
# The caller chooses candidate_id from view['decisions']['candidates'].
view = client.act(player_id, view['decisions']['decision_id'], candidate_id)
receipt = client.command_result
view = client.observe(player_id)
client.close()
```

`observe(player_id)` reads the public boundary. `poll(player_id)` performs one
native GameUpdate and returns the resulting public view; it does not loop until
a turn ends or choose human actions. During a waiting phase, the versioned
`civ6-host.network-decisions.v3` catalogue exposes native turn controls and marks
the remaining human-interface gaps explicitly. `timer_elapsed: null` means
unknown, not false. The official no-timer branch is read from the current native
application provider and returns false. Other timer modes remain unknown.
Unready cannot be offered with an unknown timer. Administrative
`session_state` and `command_result` are separate properties and never inserted
into the actor view. A receipt distinguishes completed, refused and in-flight
commands; only completed commands can have an `applied_action`. Native execution
in flight is not yet qualified for this capture.

`last_command_receipt(player_id)` retains that player's latest validated action
reply until another action by the same player or a reset. It includes the
episode, generation, RPC sequence, decision turn, response turn and selection.
Later observations and polls do not update the receipt or imply that a
submitted command completed.

For Gathering Storm, `information("turn_horizon", channel="administrative")`
returns the exact native `Game.GetGameEndTurn()` readback at reset. Enable
`administrative_information=True` on the backend and
`allow_administrative=True` on the client. Read it before replacing the reset
view with another observation or command. This receipt reports the engine
value, with its source and boundary, and does not establish a winner.

RPCs have one global sequence, while decision catalogues are cached per player.
Observing another actor does not by itself invalidate a same-turn catalogue;
native availability is rechecked before submission. Command receipts must
match the selected action in canonical JSON, including the types of its
parameters. Fixture tests cover that
protocol behavior, but there is no two-human native witness yet. The current
capture does not authorize control of its five AI players or additional human
perspectives. EndTurn completion reports the observed readiness effect, not an
inferred network acknowledgement or completed game turn. The catalogue now also
offers `{"kind": "force_end_turn"}` at the qualified active decision boundary.
This follows Shift+Enter's separate `UserForced` route: it does not resolve
normal blockers or choose research, production or unit orders for the caller.
The captured content/tutorial gate is checked separately from native activity.
The legacy `forced_endturn_diagnostic` bypass is not required or accepted by LAN.
Unready, active timer behavior, waiting/modal gestures and two-human conflicts still
need qualification. The client does not hide these gaps or replace the network
scheduler with hotseat.

The LAN worker now retains a received default-handler diplomacy statement
instead of automatically answering it or reissuing EndTurn. The existing
`diplomacy_response` choices travel through this same client, including while
the local human is inactive; `poll` leaves an unanswered statement in place.
Replies use the native session identity, official Lua selections and existing
native response transport. The dialogue catalogue contains no unrelated unit
or turn commands. Trade/deal handlers and queued-session EXIT remain explicit
refusals. A native request/refusal/EXIT cycle is now witnessed below. Delivery
while the human is inactive and other response paths remain covered only by
component tests or earlier non-LAN scopes. The exploration's GoodyHutReward
notification still uses the existing queue and verified receiver; Core reward
gameplay is unchanged.

The existing `examples/local_session.py --mode lan --config ...` provides JSON
commands for this client. Its configuration requires `ui_profile: null` and the
exact official/prepared capture references. This is diagnostic scope, not an
admitted strategic RL environment, general multiplayer release or DLC claim.

The v2 catalogue adds `diplomacy_overview` at an active, nonmodal boundary.
It contains only living major players already met by the requesting human,
and selections extracted and filtered by the unchanged official support Lua.
The host supplies lexical copies of the live application configuration getters
(leader, initiator human status and `GAME_PAUSED`), without replacing native
globals or inferring pause from turn activity. Unknown or incomplete reads fail.

Supported direct requests are offered as `diplomacy_initiate` candidates with
`target_player_id` and `choice`. The caller selects their ID through the same
`SessionClient.act` method. Availability is refreshed before the original UI
dispatcher emits its native RequestSession command. A completed request means
delivery; it does not mean friendship, delegation or other terms were accepted.
Any received statement still requires a separate explicit response. The v2
overview lists deal and demand screen options with `supported: false`. Later
versions of the overview expose the qualified candidates described below.

The client still reads historical v1 catalogues, but refuses an overview or
initial-request extension under that old schema. Existing v1 receipts are not
reinterpreted as v2 evidence. The component tests use fixtures; native admission
of a real initial request and its dialogue must be reported separately.

On the retained Base LAN capture, the client requested an offered delegation
to met player 4 at turn 14. The GameCore returned `AI_REFUSE_DEAL` / `NEGATIVE`;
the modal public catalogue exposed EXIT. The caller selected EXIT, and the
normal catalogue returned at the same turn with no synthetic GameUpdate,
EndTurn or automatic answer. Completion of the request **does not mean the
delegation was accepted**. The existing DB namespace factory now attaches the
borrowed gameplay connection before initial overview reads, as it already did
for received-dialogue reads. No second gameplay database is created.

This acceptance completed 46 commands in 138.9 seconds including startup and
full diagnostics, with 343 MiB peak sampled private memory. The worker was
reaped under 512 MiB / 180 s bounds and an explicit 128 MiB trace allowance.
The source runtime and public views are recorded in the private research-lab
receipt `evidence/host-lan-diplomacy-cycle.json`. A subsequent gameplay action,
POSITIVE answer, accepted delegation, queued-session EXIT, paused-game behavior
or native normal destruction was not exercised by this run. The earlier
empty-overview and failure receipts remain historical evidence.

The LAN source backend keeps a 64 MiB trace budget by default. A caller may
explicitly set `stdout_limit_mib` up to the existing shared supervisor ceiling
of 256 MiB; this changes only the bounded log allowance. The LAN lifetime still
cannot exceed 180 seconds and the native process memory limit remains 512 MiB.
No trace filtering, hidden retries or native-rule changes accompany that option.

### Public terminal results

The worker already reads the official winning team and victory type. The client
now replaces cached live catalogues when a terminal reply has no observation,
including on an initial reset of an already terminal episode. It exposes an
allowlisted result under `view["outcome"]["result"]`:

```python
if view["outcome"]["terminated"]:
    result = view["outcome"]["result"]
    # schema: civ6-host.player-result.v1
    # player_id, turn, team_id, status (won/lost), winning_team,
    # victory_type (native numeric value), is_alive
    client.close()
    view = client.reset()
```

The result is bound to the requested player, episode, generation and current
turn. Losing to another team's official victory does not require the player to
be dead. Official global results clear cached human catalogues. A terminal view
can have a null board.

Before an official winner is present, a formerly alive actor whose native
`IsAlive` flag is false receives `outcome["player_status"]` with schema
`civ6-host.player-status.v1`, the actor and turn, and flags `is_alive` and
`was_ever_alive`. The reply has null observation and decisions, and only this
actor's catalogue is invalidated. Other living actors can continue. A later
native view of the actor restored to play replaces the status with a fresh
catalogue. This transport lifecycle is exercised with software fixtures.
Native elimination and revival in a simultaneous match still require a witness.
An eliminated actor can close the session even with `checkpoint_on_close=True`.
The worker records the reason for skipping the checkpoint and uses the normal
native teardown. The backend returns no checkpoint for that close.

For Rise and Fall and Gathering Storm LAN, the status reader can use the
native neutral observer context when the captured local player still matches
and GameCore reports that player as formerly alive and now inactive. This
context reads the player's result facts and the roster's turn-activity flags.
The client still receives a null board and catalogue. A different local
player or another player's observer perspective is refused. Native mode
switch and the resulting game update remain to be qualified.

A global result and a local command receipt are independent. A refused or still
pending command can accompany a newly observed winner; its status is preserved
and `applied_action` remains null. Raw diagnostic facts, source metadata and any
extra private fields remain excluded from the actor view. Non-terminal public
payloads retain their existing shape. The session wire remains v1; the added
terminal result has its own versioned schema.

The terminal client fixtures retain their original Base and LAN coverage.
A stock Gathering Storm LAN run with one human also reaches an official loss
at T116. `close()` returns the same result and tears down the native worker.
With `checkpoint_on_close=True`, the terminal boundary emits
`native_checkpoint_skipped` with reason `official_native_victory` and
`backend.checkpoint` is `None`.

Calling `reset()` on the same client starts a new worker from the configured
T111 checkpoint. The initial public observation and current choices match
the earlier reset. The new episode starts without a previous result or command
receipt. Closing this live session produces a checkpoint. The native witness
covers one local human seat. See
`evidence/host-xp2-stock-terminal-close-reset-native.json` in the local lab.

### Administrative LAN save and resume

The source runtime supports `checkpoint_on_close=True` on the retained Base LAN
and exact XP1/XP2 LAN captures at a quiescent, active player 0 boundary. Closing
invokes the existing native Save and configuration serializer. The completed
process must be reaped successfully before the backend
exposes its checkpoint reference. This is a control-plane operation, outside the
actor's action catalogue.

The Gathering Storm route can admit multiple registered humans at an untimed,
quiescent boundary with every human active and fully initialized. A pending turn
or another active nonhuman seat blocks the Save. The checkpoint records the
secondary seats' native turn controls, and loading checks them against the
restored roster before accepting the session. Checkpoints with explicit
`public_view_players` also record private digests of the selected seats' public
observations and revealed maps. Resume re-reads those views
and refuses a mismatch in either. With `secondary_unit_commands=True`, it
also compares the public decision catalogue of each routed secondary seat.
This comparison keeps the producing run's action options and refreshes the
episode, sequence and decision identifiers for the new session. This path has
software coverage.
The native Save and Load of an official two-human LAN world remain unverified.

```python
backend = NetworkBackend(**dict(config, checkpoint_on_close=True))
client = SessionClient(backend)
view = client.reset()
# Caller explicitly chooses actions from view["decisions"].
client.close(0)
checkpoint = backend.checkpoint

# If the session has already reported an official victory, close still tears
# down the session and backend.checkpoint returns None.

resumed_backend = NetworkBackend(**dict(config, checkpoint=checkpoint, checkpoint_on_close=False))
resumed = SessionClient(resumed_backend)
restored_view = resumed.reset()
# Use the new episode, decision and candidate identifiers.
```

The original official capture remains the authority for engine, final databases,
content and scripts. A checkpoint adds a paired native GameCore/configuration
stream, parent ancestry, public boundary and host-side selection/placement state.
Each process receives distinct private database copies. Reopening checks the
public observation and semantic decision catalogue against the saved boundary;
only episode/generation/sequence/decision identity is renewed. Missing or changed
dependencies and incomplete producers fail explicitly. Keep the referenced
private checkpoint ancestors, databases and receipts; ancestry is bounded to 64.

For XP1 and XP2, backend construction verifies the requested checkpoint head
and its engine and capture identity. `reset()` authenticates the entire ancestry
before starting the worker. An invalid ancestor is therefore reported by `reset()`.

The Base grouped source-runtime acceptance created two successive checkpoints at
turn 2, reloaded each, preserved selected/deselected unit state, and executed a
native civic choice after the second reload. Both observation/catalogue pairs
matched; all three bounded processes were reaped. The group took 185.3 seconds
including three loads, two Saves, copies, hashes and diagnostics; peak sampled
private memory was 340 MiB in an individual worker. This is not throughput.

The XP1 group saved a fortified unit and explicit selection at turn 1. It
reopened the pair, verified the qualified public observation and v5 catalogue,
executed the offered CANCEL and deselected, closed, then reopened the same pair
again through `reset()`. All three processes completed native teardown.
The 291.42-second group peaked at 417,697,792 sampled private bytes in one
worker. This includes copies, ancestry/source verification and diagnostics;
it is not a production-speed benchmark. XP1 reuses the same API and requires
its exact `prepared_capture` in the configuration. Its original capture,
checkpoint ancestors and producer receipts must remain available.

The XP2 group saved two successive native Game/configuration pairs at turn 2,
loaded each in a fresh process and executed an offered action after each Load.
Selection survived the first Load and deselection survived the second. Qualified
public observations and semantic choices matched; all three lifetimes completed
native teardown. The 690.19-second instrumented group peaked at 468 MiB sampled
private memory under a 512 MiB per-process bound. This is not throughput.
Evidence: `evidence/host-xp2-native-checkpoint.json` in the private lab. This
witness contains no placed construction; it does not establish placement
inventory persistence or arbitrary-state Save/Load.

Scope remains the exact captured profiles: one human/five native AI for the
earlier Base/XP1 witnesses, one human/one AI for XP2, no timer and no pending
dialogue or war modal. Waiting, timed, multi-human and terminal checkpoints remain unqualified.
The saved components are not a complete `.Civ6Save` container; official EXE
reopening and full hidden-state equality are not claimed. Single's historical
checkpoint admission remains separate. Each expansion witness qualifies only its
captured checkpoint group; arbitrary-state, other DLC/mod and training
qualification do not follow from these cycles.

### Rise and Fall city assault

On the installed Rise and Fall LAN profile, an offered `unit_attack` with
`operation="MOVE_TO"` and `input_route="world_plot"` can target a visible
enemy city. Select its candidate using the current decision identifier.
The next response exposes the city damage in `decisions["unit_attacks"]`.

At turn 16, the client completed one such attack against an unwalled city
prepared in a private scenario. GameCore applied 45 damage to the city and
24 retaliation damage to the warrior. A fresh worker reloaded the native
checkpoint without the scenario setup and restored the same observation
and all 3,433 choices. Both workers completed native Unload and Destroy.
The local receipt is
`evidence/host-xp1-installed-city-melee-assault-save-reload-native.json`.

The same Rise and Fall LAN profile also offered `unit_attack` with
`operation="RANGE_ATTACK"` and `input_route="dedicated_ranged"` against that
unwalled city. The private scenario placed a Slinger through the native
`UnitManager.InitUnit` method. The ordinary Python client selected the offered
candidate. GameCore increased visible city damage from 45 to 70 and consumed
the Slinger’s movement. A fresh ordinary worker restored the 70 damage, the
exact public observation and all 3,437 choices from the saved state. Both
workers completed native Unload and Destroy. The local receipt is
`evidence/host-xp1-installed-ranged-city-attack-save-reload-native.json`.

The installed Rise and Fall LAN profile adds `city_shots` in
`civ6-host.network-capability-decisions.v11.captured-city.v2`. Select an
offered `city_range_attack` candidate with the usual decision and candidate IDs.
The engine chooses the defender on the target plot. At turn 17, a fortified
city applied 1 damage to a visible enemy unit and the shot disappeared from the
catalogue. An ordinary worker restored the damage, the spent shot and all
3,445 public choices from the native checkpoint. Both workers closed normally.
The private validation scenario prepared the walls and target through GameCore.
The receipt is `evidence/host-xp1-installed-fortified-city-shot-save-reload-native.json`.

Version `v11.captured-city.v3` adds `district_shots` for eligible non-center
districts. Select an offered `district_range_attack` using the current decision
and candidate IDs. At turn 17 a completed Encampment applied 1 damage to a
visible enemy unit. A fresh ordinary worker restored the damage, the spent
district shot, the public observation and all 3,448 public choices. Both
workers closed normally. The validation scenario prepared the Encampment
and target through GameCore. Older Rise and Fall checkpoints compare their
recorded fields before exposing the new catalogue.
The receipt is `evidence/host-xp1-installed-fortified-district-shot-save-reload-native.json`.

### City controls on the retained Base LAN profile

`SessionClient` now returns the existing public `city_focus_catalogs`,
`citizen_catalogs` and `production_queues` within the network decision envelope.
The caller chooses the offered candidate ID exactly as for other actions:
`city_focus`, `city_citizen`, `queue_append`, `queue_swap`, or `queue_remove`.
The host refreshes native availability before dispatching the selected command;
it does not choose a governor assignment or production item for the caller.

LAN admission is separate from the old Hotseat UI receipts. It pins the shipped
normal city-panel route, the tutorial scenario's ruleset/import conditions,
the Bridge-only content declaration and the before/after captured controls.
Selecting an owned city and returning to normal selection are interface
gestures without a simulation command. They are not prerequisites requiring
the headless client to reproduce a rendered selected-city panel. Current
actor/activity, ownership, yield flags, citizen targets and production legality
are still read and checked by the existing adapters. Unknown content or an
unavailable/unknown control witness fails admission; no diagnostic flag is used.
Plot purchasing and the legacy Hotseat forced-turn gate are not enabled by
this change. LAN forced turns retain their separate network route.

The retained native witness is a single newly founded city at turn 1: three
production-focus clicks, one tile lock/unlock pair, two unit queue appends,
one swap and one removal. Those choices and public effects passed through the
client. This does not qualify occupied cities, specialist slots, full queues,
later economy interactions, other content, or two-human concurrency. Historical
Hotseat evidence remains independent; no whole-game or 100% fidelity claim is
made from this scope. `tools/accept_session.py --city-controls --config ...`
reuses the existing bounded acceptance path, not a new runtime or learner.

### Map actions on the retained Base LAN profile

The source integration adds separately admitted LAN access to the existing
`world_select_unit`, `world_plot_click`, `world_deselect_unit`, ordinary
`unit_order` CANCEL, and plot `purchase` actions. The map-click surface offers
every grid coordinate for the selected own unit; hidden terrain/path legality
does not prune its candidate set. The shipped normal movement helper and native
command checks decide the request and effect. This is a semantic selection/order
API, not certification of every physical input mode or rendered feedback.

Plot access reads the shipped gold-capability predicate from the loaded native
table. Native targets, prices, affordability and ownership checks are reused.
Legacy diagnostic switches remain false for the source-admitted LAN path;
ordinary CANCEL does not cover the separate spy mission dialog. Existing
war-prompt handling remains explicit, with broader LAN interactions unqualified.

The grouped command is `tools/accept_session.py --map-controls --config ...
--stdout-limit-mib 128`. It requires a witnessed queued destination, a selected
CANCEL clearing it, and a real affordable plot purchase. The corrected native
acceptance completed all of these through the client: destination 879 was
queued then cleared by CANCEL, selection was explicitly cleared, four native
forced turns accumulated enough gold, and plot 877 was bought for 25 gold.
Native ownership was confirmed and the balance changed from 26 to 1 at turn 5.
Ten choices and 71 public views were retained. The run took 67.8 seconds with
317 MiB peak sampled private memory; the worker was reaped under the unchanged
512 MiB / 180-second / 2 GiB reserve policy. All 1,087 source pins were unchanged.
This is one exact Base LAN capture, not complete strategic-training admission.

Parent response validation recognizes the exact source/bundle admission while
preserving the old diagnostic rule for other profiles. A pending war
confirmation also excludes the LAN wrapper's fast turn and diplomacy routes;
that modal regression remains fixture-checked, not natively qualified by the
non-war map acceptance. Failed attempts and resource refusals are preserved
separately rather than counted as successful native commands.

Network catalogue v3 introduced the expanded
map-coordinate budget. At most 16,384 world-click coordinates can accompany the
existing 4,096 ordinary choices; both budgets remain enforced, and exact world
candidate validation still requires every coordinate. No path or hidden state
prunes this list. The LAN event reader admits lines up to 16 MiB while retaining
the total trace, process-memory and time limits. Legacy Hotseat event lines stay
at 1 MiB. The client still reads v1/v2 with their old action budgets; earlier
native receipts are not reclassified as v3. A fixture with all 16,384 map cells
passes through the actual stream reader. This verifies capacity and compatibility,
not native gameplay on a map of that size or an unlimited late-game action space.

### National parks on the revealed map

Enable `expansion_national_parks=True` on a pinned Rise and Fall, Gathering
Storm or Boston BBG 7.5.1 LAN capture. `information("national_parks")` reads
park tiles through the same native reveal gate and name getters as the
official tooltip. Each row carries the plot ID, the already-localized park
name when present, and its current visibility. Revealed tiles in fog can
carry their tooltip labels. Unrevealed tiles are excluded before the park
getters run. This read uses the current player perspective and the same
episode and decision boundary as the rest of the public observation. The
bindings and visibility contract are verified offline. Live readback and
native switching between simultaneous human players are pending.

Enable `xp2_designate_park=True` on the admitted stock Gathering Storm or
BBG 7.5.1 LAN profile to receive `designate_national_park` candidates through
the current decision catalogue. Each candidate names the owned unit and
its current tile. The host reruns the official UnitPanel legality checks
and sends the native operation without extra parameters. Completion requires
a new park at the unit's original location. Delivery without that readback
is `submitted`. The option also applies to authorized secondary LAN seats
when their command routing is enabled. Source and software checks cover the
new path. A live park creation and restart still require a native witness.

### World Rankings score

Enable `world_score=True` on an exact installed expansion LAN profile and
read `client.information('world_score')` from its current public view. The
group contains team and player totals, the categories displayed by the score
tab, and the native turn limit. Player IDs appear for the local player and
met civilizations. Other rows keep their visible scores and an anonymous ID.
Team IDs and individual identities behind anonymous rows are not returned.

With secondary LAN routing enabled on an admitted Gathering Storm capture,
call `observe(pid)` and `information('world_score', player_id=pid)` for that
seat. The same native score tab uses the selected seat's known civilizations,
including at a waiting boundary. A simultaneous checkpoint records whether it
compared the secondary score view. Earlier checkpoints retain their original
comparison scope.

Source and software checks cover installed Rise and Fall, Gathering Storm,
and the exact BBG 7.5.1 score-panel replacement. The BBG-specific domination
panel and other victory tabs are separate, and live score reads on these
profiles still require native acceptance.

### Own-unit work state and native builder effects

The installed stock Rise and Fall LAN profile accepts `xp1_unit_work=True`.
The existing decision catalogue then includes the work choices for the
unit's current tile. Use `information('unit_work')` for own-unit charges,
movement, visible tile state and the official offer details. Submit an
available `build_improvement` or `terrain_operation` through `act()`.
Reopening an older checkpoint with this option requires all previously
recorded observations and choices to match. Local source and client tests
cover this addition. Native execution and Save/Load of these actions on
Rise and Fall remain to be verified.

For a retained Rise and Fall checkpoint with a charged builder, the existing
acceptance driver accepts `--unit-work --restored-builder UNIT_ID PLOT_ID`.
It uses an openly visible owned tile, checks the native improvement and
charge change, saves, and requires the same public state and choices in a
second headless process. Both processes must close cleanly.

Network schema v4 introduced the additive
`decisions.unit_work_state` field has schema `civ6-host.unit-work-state.v1` and
the current player, turn and own-unit rows: `unit_id`, `plot_id`, `charges`,
and `moves_token`. It reads native getters for exactly the own units in the
public observation, including units with no movement left. Non-builder units
also appear with their native charge count. No opponent/private state is added.
Waiting or diplomacy-modal catalogues explicitly carry `null`; reading the
field in those phases is not yet admitted.

Existing `build_improvement` and `terrain_operation` candidate IDs still use
the native availability/request adapters. Their offered position, charges and
movement are checked against the new public state. The existing public
`plot_info.plots` returns the resulting improvement, pillage state and yields.
The host does not choose a target or improvement for the caller.

`tools/accept_session.py --unit-work --config ... --stdout-limit-mib 128` now
reuses the bounded client acceptance path. One retained Base LAN continuation
loaded the existing turn-2 checkpoint, produced a builder in four native turns,
moved to public owned plot 952, built a farm and removed it the next turn.
All nine commands completed. The client saw charges 3 → 2 even with movement
at zero, and food yield 2 → 3 → 2. Removal retained two charges. The worker was
reaped under 512 MiB / 180 seconds; the group took 116 seconds with a sampled
private peak of 371.5 MiB. These timings include loading/instrumentation.

This witnesses native client inputs and effects, while the existing
`terrain_work_tutorial_and_ui_mod_hooks` gap remains explicit for full interface
parity. The processing guard has since been connected as described below;
legal native offers alone were not used to infer it. Harvesting, feature removal, repairs, final-charge consumption and
other profiles were not qualified by this run. No training is admitted by it.

The client still accepts v1/v2/v3 without changing their saved data. Reloading
an existing v3 checkpoint into v4 explicitly compares all historical fields,
validates the added own-unit state, and records a catalogue transition. It does
not claim byte equality for the additional field. The retained native resume
confirmed unchanged old observation/decision fields; new v4 checkpoints retain
the new field for subsequent exact comparisons.

### UnitPanel processing guard

The existing FIFO consumer now observes the verified PlayerTurnActivated and
PlayerTurnDeactivated payloads. The official ring/descriptor/subscriber/Lua
marshalling chain proves the signed player argument at record offset `0x54`
and activation Boolean at `0x58`. Only an event matching the local viewpoint
changes its guard; initial `true` and activation/deactivation assignments match
the shipped UnitPanel source. This is an interface-state projection, not a
native turn-flag setter or replacement gameplay rule.

For the exact Base LAN content admission, the terrain-work catalogue and
pre-dispatch boundary use this guard. Pending events or a missing content/source
admission refuse access. Historical profiles do not inherit this LAN admission.
The actor receives no other player's event data. The normal wire schema stays
v4; private event receipts retain the source hash.

A retained trace replay checked 160 consumed player events, ten local
transitions and eleven active work boundaries. One new bounded native turn
cycle verified the integrated consumer closing and reopening the gate, with
checkpoint continuation intact. It took 64.6 seconds including loading and
diagnostics, with 357.6 MiB sampled private peak; the worker was reaped. This
cycle does not repeat a positive builder operation under the new guard.
Compound manual selection is qualified by the later group below. Other
UnitPanel controls, other content and complete human-interface equivalence
remain unqualified. The full terrain UI gap must not be removed on the
strength of the processing guard alone.

### Compound terrain selection and final builder charge

For the admitted Base LAN profile, a terrain request naming an own unit means
"select this unit, then perform this offered operation". The runtime checks
the processing guard and native offer before changing selection, reuses the
normal own-unit selection adapter, then sends exactly one native operation.
The client does not need to infer or issue a hidden second gameplay action.
Its `world_input.selected_unit_id` reflects that manual logical selection.
This is not an assertion that the graphical EXE's head-selected pointer or
automatic next-unit cycling is reproduced. No replacement unit is chosen
automatically when the requested unit disappears.

The grouped acceptance deliberately selected a warrior before asking a
builder to construct/remove a farm. Both requests selected the builder and
executed the requested native operation. A turn-7 checkpoint with two charges
was then reloaded into a fresh process: public observation, selection and
available choices matched. Further native construction consumed the charges
2 → 1 → unit removed at turn 10. The removed unit was absent from the public
observation, work state and candidate list, and selection was cleared.

All 17 commands completed; both sequential workers were reaped below their
512 MiB / 180-second bounds. Total instrumented time was 256.0 seconds, with
385.8 MiB sampled peak private memory in an individual worker. The retained
turn-7 checkpoint can be reused without repeating builder production.
`--unit-work --consume-builder` extends the existing acceptance entrypoint;
it does not introduce another runtime or learner. The delivery receipt is
`host-terrain-selection-consumption.json` in the local laboratory evidence.
Harvesting, feature removal, repairs, automatic cycling, other content and
strategic-training admission are not established by this group.

### Native terrain information and harvest/feature removal

Catalogue v5 introduced
`decisions.unit_work_info` (`civ6-host.unit-work-info.v1`), retained in v6. Every visible work
offer has the same exact action and `legal` value as `unit_work`, plus:

- `action_name`: localized native override, or `null` when none is displayed;
- `feature`: native feature index and localized name, or `null`;
- `descriptions`: localized `ADDITIONAL_DESCRIPTION` lines;
- `failure_reasons`: localized reasons displayed for disabled offers only.

Disabled offers remain information; they do not become executable candidates.
The existing native availability calls supply the results, without an extra
query per offer or a Python yield formula. This is the dynamic UnitPanel
information, not the entire formatted graphical tooltip or every UI control.

`targets` covers exactly the public own units, including those with zero
movement. Each row contains `unit_id`, `plot_id`, native `improvement`/`route`
indices and their `improvement_pillaged`/`route_pillaged` flags. Target identity
and current visibility are joined against the public observation. It includes
no enemy units, hidden resources or unseen tiles. Waiting/modal phases carry
an explicit `null` for this information.

The prepared turn-7 builder checkpoint was resumed through the existing Load
path. The v4 → v5 transition compared every historical field and separately
validated the added information; old checkpoint bytes were not changed.
The client then chose Pottery and Mining, harvested wheat, moved to owned
woods and removed that feature. Native descriptions announced 10 food and 11
production. Resource/feature disappearance, charges 2 → 1 → unit removed, the
monument leaving its production queue and city culture yield increasing by 2
were observed. The food-stock increment and production overflow were not
independently compared, so exact bonus accounting is not claimed.

The subsequent city-growth group below closes the food-stock credit gap;
production overflow remains unqualified.

`tools/accept_session.py --terrain-work --config ... --stdout-limit-mib 128`
uses that prepared checkpoint and the existing client. Nine commands and 55
public views reached turn 10 in 138.0 seconds, including loading and diagnostics,
with 374.7 MiB sampled private peak under 512 MiB / 180 seconds. The single
worker was reaped. No builder production was repeated or state fabricated.
No pillaged target exists in this witness: positive REPAIR/REPAIR_ROUTE effects
remain pending, along with broader profiles and complete interface coverage.

### Own-city growth display

Catalogue v6 introduced the field retained in v7:
`decisions.city_growth` (`civ6-host.city-growth.v1`). For each current own city
it exposes population, occupation, housing, amenities, happiness and the
official growth-panel display: remaining food, food yield/consumption/surplus,
growth modifiers, turns until growth or loss, starvation state and status icon.
Display strings are localized by the installed native formatter. They preserve
the official panel's rounding and zero-growth behavior.

Only the installed, hash-pinned presentation functions are evaluated, in a
local lexical scope with explicit display sinks. Native getters supply the
values; the host does not implement growth rules. Exact food stock, threshold
and raw sentinel countdowns are separated into administrative trace events.
They are not public observation fields, actor inputs or a qualified critic
sidecar. City IDs, ownership and population must match the public observation.
Waiting/modal views carry `null`, without stale city data.

The retained v4 checkpoint was loaded without changing its bytes. Compatibility
projection checks all historical fields and separately validates each added
v5/v6 field. The existing acceptance runner's `--growth-harvest` group then
chose research, advanced one turn and harvested the prepared wheat. At turn 8,
native food stock increased by exactly 10 and the display changed from 11.3
to 1.3 remaining food. The public surplus also changed when the wheat was
removed; the host does not retain a stale pre-harvest yield. This is a native
input/effect witness on one Base LAN profile, not full graphical UI parity.

This grouped check took 85.2 seconds (three commands, 19 public views), including
load and diagnostics, with 371.8 MiB private peak under the 512 MiB/180-second
worker bounds. The worker was reaped; all 1,142 source pins were unchanged.
No builder production or unrelated terrain work was repeated. The local receipt
is `evidence/host-lan-city-growth.json`; this measurement is not production
throughput or training admission.

With `expansion_city_growth=True`, the same public `information("growth")`
call is wired for the pinned Rise and Fall, Gathering Storm and Boston
Gathering Storm + BBG 7.5.1 LAN captures. The expansion panel returns
`civ6-host.city-growth.v2` and adds `display.OccupationLabel`. Its
`display.OccupationMultiplier` shows the loyalty-related penalty from the
official panel. The housing, amenities, food display and countdown remain
scoped to the player's own cities. The expansion adapter exposes only that
public projection. The installed bindings and panel behavior are checked
offline. Live readback on these captures is pending.

The separate option `expansion_city_loyalty=True` exposes the public
`information("city_loyalty")` group on the same three pinned captures. The
group reads the player's own cities and reports current and maximum loyalty,
change per turn, loyalty level, displayed conversion countdown, potential new
owner and the visible pressure breakdown. The panel's decimal precision and
order of pressure rows are preserved. Its source bindings and client contract
are checked offline. Live readback is pending.

### Production inputs and diagnostic separation (v7)

The source LAN runtime emits `civ6-host.network-decisions.v7`. Production actions
and their candidate IDs remain unchanged. Two fields have new explicit public
schemas:

- `production` uses `civ6-host.current-production.v1`: own `cities`, each with
  `city_id`, `state` (`empty`, `current` or `completed`) and an optional `item`.
  The item contains its content identity, localized `name`, displayed `formation`,
  `progress`, `cost`, `turns_left` and `never_completes`. A native -1 countdown is
  represented by `turns_left=null`, `never_completes=true` (the panel shows 999+).
- `production_info` uses `civ6-host.production-info.v1`: source pins, perspective
  and candidate identity plus the existing `public` cost/progress/turn fields.
  The old `raw` object is forbidden by this schema.

Current-item progress/cost are numeric fields displayed by the official
ProductionHelper. When the queue is empty, that helper can show the previous
completed item. The host preserves CitySupport's use of the *current* unit
formation modifier even in that branch: when none of its three formation
branches matches, it leaves cost at zero and the name without a suffix. The
contract marks that case `formation="unsuffixed"`, not as a standard unit.
This branch was observed for the previously completed builder in the retained
checkpoint. Other formation labels are `single`, `corps`, `army`; non-units use
`null`. No cost formula or production rule is reimplemented.

V6 and earlier transported diagnostic production rows alongside their public
projection. Those historical wire versions are preserved for compatibility;
they must not be presented as an entirely player-only input boundary. V7 keeps
the original native snapshots in administrative events joined to episode,
generation, player, sequence and turn. Legacy checkpoint readback compares
these actual native values against the old fields, and separately checks the
new public projection. It neither invents missing raw values nor rewrites saves.

The native grouped witness used the existing turn-7 builder checkpoint. The
client chose Mining, selected a Monument, appended a Scout, moved the builder
to woods and advanced explicit turns. At turn 10 the Monument showed 27/30;
one native removal completed it and the queue head became the Scout at 0/15
without a turn change. The actual stock carried into later production was
not separately measured, and no internal overflow counter is exposed.

The same delivery corrected the Locale bridge's extra C-terminator assumption.
The official formatter's explicit byte length now reaches HKS `PushLString`.
Four displayed keys were compared byte-for-byte with direct native String
reads; the existing numeric formatting/refusal checks also passed. No localized
text is reconstructed in Python. The older native host executable and earlier
Locale module are preserved.

The local receipt `evidence/host-lan-production-inputs.json` records eight
commands and 54 public views over 127.5 seconds, including load and diagnostic
overhead. The worker remained under its 512 MiB/180-second bounds and was reaped;
all 1,156 pinned sources were unchanged. This source-runtime Base LAN delivery
does not admit two-human simultaneous play, other content profiles, full UI
parity or strategic training. Public/diagnostic separation for other historical
field groups remains a separate requirement.

# Typed information channels

The source `SessionClient` exposes model-independent numerical information:

```python
from civ6_host import SessionClient, InformationUnavailable

session = SessionClient(backend, allow_administrative=True)
session.reset()
public = session.information("economy", player_id=0)
administrative = session.information(
    "economy", player_id=0, channel="administrative"
)
```

The same query supports named public groups. Each reuses its existing source-bound
reader and contract; none selects features for a particular model:

| Group | Public data | Administrative data |
| --- | --- | --- |
| `economy` | Numerical treasury/yields and research choices | Original selected-player economic and research snapshots |
| `production` | Current/previous production, displayed quotes and canonical queue catalogues | Original production snapshot and quote readback |
| `growth` | Qualified own-city growth information | Original food stock, threshold and growth/starvation counters |
| `unit_work` | Own-unit charges/movement and qualified action/terrain information | Not qualified; explicit `InformationUnavailable` |

Gathering Storm LAN catalogue v18 exposes `information("production")` as
`civ6-host.production-inputs.v2` at active decision boundaries. It returns
`current.cities` and `queues`. The current or previous item includes its
official displayed name, cost, progress, formation and turns remaining.
An empty city has an explicit state. Candidate price quotes and the
administrative production group remain unavailable for this profile.

The terrain offer and current-item progress measure different native values.
In the retained Gathering Storm chop, the offer and the native map message
both show 14 production. The queue processes the grant together with its
stored production carry, and the current item advances from 0 to 22.
The progress change includes production already carried by the city.

Gathering Storm LAN decision catalogues v17 and v18 expose
`information("unit_work")` as `civ6-host.unit-work-inputs.v3` during an
active decision boundary. Its `state.units` gives each own unit's charges
and movement, including units with zero movement. It includes the improvement
and route indices and pillage flags for each visible plot occupied by one of
those units. The native index `-1` means absence. The separate `catalogue`
contains current work offers and can be empty even when a unit retains
charges. The `info.offers` rows match the catalogue and carry UnitPanel
details returned by the same native availability query. Descriptions
are localized in the session language. Disabled offers can include
failure reasons when the engine supplies them. These strings preserve
the engine's markup and are separate from action legality. Waiting
boundaries report the group as unavailable. Historical v16 catalogues
still return group v2. The Base information format keeps its original schema.

Production and growth administrative reads additionally require
`NetworkBackend(..., administrative_information=True)`. This enables a parent-side
store of the **existing** native events; no new GameCore getter or gameplay call
is made. `SessionClient(..., allow_administrative=True)` enables client access.
Disabled backend capture raises `PermissionError`; absent evidence at the exact
response raises `InformationUnavailable`. Raw snapshots are never reconstructed
from displayed values.

The store retains only the latest matching group/player readback, has a default
32 MiB serialized-payload budget plus per-snapshot structure bounds, and uses a
lock across the pipe-reader and caller threads. That is not a claim of 32 MiB
resident memory. Events are joined before delivering their response to the
caller, with exact episode/generation/player/sequence/turn, source pin and public
projection checks. Initial readbacks preceding the reset response are preserved;
old-episode, waiting and ended views cannot obtain stale snapshots. Nothing is
rescanned from a growing journal for each query.

`backend` is the existing configured LAN backend. No learner or PyTorch is
required. Administrative access defaults to disabled; requesting it without
explicit opt-in raises `PermissionError`. This is a client API guard against
accidental channel mixing, not authentication against code that controls the
Python process or authorization for a future remote server.

The envelope `civ6-host.information.v1` contains `group`, `channel`, `episode_id`,
`game_generation`, `player_id`, `sequence`, `turn`, `native_decision_id`,
`source_contracts` and `data`. The identifiers bind both channels to the same
recorded boundary. A query performs no RPC and does not advance the game. Use
`observe` or `poll` to refresh. A cached same-turn perspective keeps its original
sequence after another player's request; it is never relabelled as a fresh read.
Missing perspectives, a previous turn, waiting/modal boundaries lacking the
group, and closed/ended sessions raise `InformationUnavailable`. No zeros,
guessed values or stale fallback are substituted.

The `economy` public data schema is `civ6-host.economy-inputs.v1`:

- `treasury`: displayed integer gold balance, income, signed expense and net
  income as numbers. These independently formatted components need not add up
  exactly after display rounding. Native arithmetic is checked before projection.
- `global_yields`: science, culture, faith balance and faith yield at their
  qualified public display precision.
- `cities`: own-city identifiers and the six displayed yields.
- `research`: selected technology/civic, selected-item information and all
  offered research choices, including native indices/hashes, costs, boosts and
  displayed turns remaining. `turns_left: null` represents the native display's
  unavailable estimate. `turns_capped: true` means the displayed value is 999;
  it does not distinguish exactly 999 from a larger native estimate.

Public numbers are parsed from the already qualified native English/French
display values. This does not reimplement yield/research rules, normalize model
features or prescribe strategies. Numerical observations and action identities
remain independent of any particular network architecture.

The administrative data schema `civ6-host.economy-administrative.v1` carries
`actor_channel: false` and preserves the native `economy`, `city_yields`,
`treasury`, `yield_display`, `research_info` and `research_progress` snapshots.
It retains precision, source display text and raw turn counts omitted from the
public projection. This group describes the selected player's existing readers;
it is not an omniscient whole-world or complete privileged-critic API. Numeric
research progress remains administrative pending qualification of its public
precision; this does not assert that research progress is wholly hidden in Civ6.

With the XP2 display projection enabled, a terminal reply returns the public
result with null observation and decisions. The native formatter serves live
views only, so terminal replies do not expose the raw board precision.

The source runtime now supports an explicit launch-time `public_display_source`
alongside `public_display_diagnostic=True`. The omitted source retains the stock
v7 contract. `runtime.player_display_toppanel.BBG_SOURCE_SHA256` selects the
separate fr_FR candidate for the exact recovered BBG 7.5.1 bundle. It does not
select a formatter on an action request or accept an arbitrary source file.
Unknown sources, a mismatched bundle/bootstrap, changed dependencies, foreign
owners and cross-response formatter receipts are refused. The v7 file and its
historical refusal remain unchanged.

This optional path formats four already-read values through the official
Localization library and projects the six CityPanel yields. It adds no yield,
purchase or turn rule. `SessionClient.view()` returns its explicit display-v2
envelope; `information('display')` returns the same cached public values. The
private raw response remains the authority for native commands and checkpoint
comparison. The BBG candidate's native qualification is tracked separately;
selecting it is not a statement of complete public-information parity.

The historical `view()`/transport and saved checkpoints remain unchanged. Their
full nested dictionaries still contain some diagnostic getter values and must
not be treated as an entirely player-only model input. The typed query qualifies
this information group, not global information parity. Neither this API guard
nor the retained Base/one-human LAN evidence proves multi-human, expansion or
complete gameplay compatibility. The installed distribution predates this source
addition until a later packaging qualification.

The existing acceptance tool can verify information projections against a pinned
retained native receipt without starting the engine:

```text
python tools/accept_session.py --replay-information <native-receipt.json> --information-group all --replay-output <private-report.json>
```

It verifies retained file hashes, replays the recorded requests and replies
through `SessionClient`, checks both channels and keeps unavailable boundaries
explicit. This is retained-native client replay, not evidence of a new native
call or a new gameplay interaction.

### XP2 initial diplomacy

On BBG 7.5.1, the opt-in `civ6-host.network-capability-decisions.v33` adds
`decisions.diplomacy_overview` and `diplomacy_initiate` candidates. It preserves
the preceding v32 governor fields. The current scope is the explicit
`xp2-gamecore-current-092abfbb` execution image and exact recovered GS + BBG 7.5.1
bundle; launch requires `governors_diagnostic=True`,
`diplomacy_overview_diagnostic=True` and the selected war receiver source pin.

The exact unmodded Gathering Storm LAN capture also supports
`diplomacy_overview_diagnostic=True` with `standard_trade=True` and the same
current image and war receiver source pin. This opt-in keeps the stock decision
schema and its trade, Congress and other enabled groups. The public overview
includes met major targets, visible AI relationships, grievances and the
official selection rows. The stock mapping includes `CHOICE_DENOUNCE`
and `CHOICE_MAKE_PEACE` when enabled by the engine. Major peace uses the
same explicit draft and confirmation API as BBG. On the native T89
checkpoint, Python opened the draft with two locked treaty terms,
confirmed the AI's acceptance, read the end of the war and saved the
result. A separate GameCore process reopened that checkpoint with the same
public observation and choices. On the same stock lineage, Python then
selected the offered denunciation, closed its native dialogue explicitly
and observed the new relationship with 21 turns remaining at T89. A separate
process recovered the same observation and choices, advanced to T90 and saved
the relationship with 20 turns remaining. Full expiry on this stock lineage
has yet to be observed.

The stock overview also exposes major agreements, demands and current
open-borders rights. The client opens an offered negotiation with
`CHOICE_MAKE_DEAL` or `CHOICE_MAKE_DEMAND` and operates the existing public
draft and confirmation choices. At T90, the stock witness adds tobacco
to a native draft and receives an unfavorable inspection. The engine
offers no submission for that draft. In the demand screen, the client
requests one horse, submits the demand, receives the native refusal and
closes the dialogue. An independent process restores the same state and
choices with no outstanding deal. A continuation starts the offered route
to Kabul and switches both cities to gold focus. The treasury reaches 15
gold at T96 across native saves and independent reloads. The AI's inspection
rejects the tested gold and horse terms, and the client submits the offered
equalization command on the gold-only draft. GameCore returns an empty
adjusted draft without a confirmation choice. The native save retains all
15 gold.

A separate stock branch starts from the post-peace save before the
denunciation. At T93 the AI rejects a request for a horse against nine gold.
The client removes that term, confirms the accepted gift, and verifies the
nine-gold debit and the native deal-enacted event before saving. A fresh process
restores the same public observations and choices, with zero gold and no
replayed transfer.

The stock negotiation overview v2 also offers
`CHOICE_DECLARE_FRIENDSHIP` for a met AI when the official menu enables it.
The common client submits the request and presents the native dialogue.
At T93 Barbarossa refused the request. The client selected `CHOICE_EXIT` and
saved with the same relationship and the friendship request still offered.
Existing v1 negotiation checkpoints preserve their earlier catalogue during
comparison. Acceptance and human-to-human requests await native qualification.
The AI's public answer is also available as `decisions["friendship_response"]`
in the v12 diplomacy modal. The values are `accepted` and `rejected`.
This field is present for an AI reply shown to the requesting player. The
client can read the outcome directly and select the same `CHOICE_EXIT` candidate.

Stock negotiation overview v3 adds initial promise requests for spying,
nearby settlement, religious conversion, and artifact excavation. The API
offers these choices for a met AI only when the official menu enables them.
The native warning uses the ordinary diplomacy response modal, with an explicit
choice to close it. Earlier negotiation overview versions remain readable.
On the unmodded T96 witness, Barbarossa rejects the conversion request.
The displayed grievance balance changes from -33 to -8, favor remains 224, and
the conversion request is removed from the menu. The host saves this state.
The other three requests have source and fixture coverage.

Stock negotiation overview v4 adds `active_promises` to met AI targets. This
list contains the active promise types read through the same getter as the
official relationship panel. An empty list means the panel reports no active
promise. The field is null for human counterparts, whose promise readback is
outside this profile's current scope.

The v13 diplomacy modal publishes the type of an incoming warning as
`promise_request`. For the four promise types above, its `choices` retain the
official order and disabled flags. The client selects an enabled
`CHOICE_POSITIVE`, `CHOICE_NEGATIVE`, or `CHOICE_IGNORE` through the standard
`act` method. Each sends its own official response. The incoming path has
source and fixture verification. A native incoming witness remains pending.

After the normal reset/observation call, the public query uses the accepted
boundary without another RPC:

```python
overview = client.information('diplomacy')['data']
offered = [row for row in view['decisions']['candidates']
           if row['action']['kind'] == 'diplomacy_initiate']
# The caller explicitly selects one offered row, if any.
if offered:
    selected = offered[0]
    view = client.act(overview['player_id'], view['decisions']['decision_id'],
                      selected['candidate_id'])
```

An action contains
`kind`, `target_player_id` and `choice`. Availability comes from the native
living-major roster, `IsMajor`, `HasMet`, and the selected official GREETING
extraction/filtering. Native row order and disabled state are preserved.
Unsupported deal/alliance rows remain in the overview with `supported=False`;
only enabled, supported rows become executable candidates. The capability
reports `complete_action_space=False`. Unknown or unavailable choices fail
explicitly. No target is inferred from hidden positions or its numeric ID.

The command requeries availability, checks the selected native factory and calls
the official initial-statement dispatcher. A native `RequestSession=False`
returns a refusal without inventing an archive. A pending dialogue exposes the
separate explicit-response contract; the host does not select its response.
The selected official golden-war literal is preserved even though it differs
from the Core's registration. No corrective alias is inserted.

Native qualification of direct initial diplomacy covers the T25 public query,
matching input observation, Save v2 and Unload/Destroy. The catalogue was empty.
A separate T57 witness sends the offered `CHOICE_DIPLOMATIC_DELEGATION` through
`diplomacy_initiate`. The command's completion records delivery to GameCore.
The resulting public dialogue reports the AI's refusal and offers
`CHOICE_EXIT`. The client selects it explicitly and can see that gold and
delegation availability are preserved when the session saves. A fresh process
reopens that checkpoint with the same observation and catalogue. The client
then selects `CHOICE_DENOUNCE` as the confirmed denunciation, closes the native
dialogue explicitly and saves. GameCore withdraws denunciation, friendship and
delegation for that target and reports peace. Delegation acceptance, the expiry
of denunciation and other direct requests still need native qualification.
Private evidence is recorded in
`evidence/host-xp2-direct-diplomatic-delegation-t57-native.json` and
`evidence/host-xp2-direct-denounce-t57-native.json`.

In `civ6-host.diplomacy-overview.v2` and later,
`information("diplomacy")` includes the public state of met majors. Each met major target has a
`relationship` field. For an AI target it contains the public state key,
signed grievances and the countdown shown in the selected official panel.
`expiration` is null when the panel has no countdown. A denunciation
countdown also identifies the displayed denouncer. Human targets use a null
`relationship` in this profile. The v2 field adds no choices. The checkpoint
comparator verifies all stored v1 observation and choice fields when loading
a prior save. A T57 native run reads denunciation, −25 grievances and 21 turns
remaining, then saves. Friendship and alliance countdowns have fixture coverage.
Private evidence is recorded in
`evidence/host-xp2-public-diplomatic-relationships-t57-native.json`.

Two native continuations restore the v2 catalogue exactly and read the
denunciation countdown on each turn from T57 through T69, including the
compulsory Congress ballot at T61. The observed countdown decreases from 21
to 9 and the formal-war choice becomes available at T62. GameCore reports an
official loss for the observed player at T70. This witness leaves expiration
and clean terminal teardown unverified. Private evidence is recorded in
`evidence/host-xp2-public-diplomatic-countdown-after-congress-native.json`.

On the selected Gathering Storm and BBG 7.5.1 profile, the v3 overview adds
`city_state_peace`. When military commands are enabled, it reports whether
each met city-state is at war with the observing player and whether the native
city-state panel permits making peace. The client can submit the offered
`diplomacy_initiate` candidate with choice `CHOICE_MAKE_PEACE` using its
current decision and candidate IDs. The host rechecks the offer at submission
and confirms completion by reading the target's native war state. Negotiated
peace with a major civilization uses the separate deal screen.

The T57 native witness reads a met city-state at war whose peace button is
disabled, confirms that the action catalogue omits the command, and saves the
new overview. A later continuation offers the command at T63. The same
Python client delivers it to GameCore, observes peace and reads the catalogue
again with the choice withdrawn. This qualifies the city-state command and
its observed effect on the retained BBG capture. The T63 native Save succeeds
after matching the result of the resumed Congress ballot. A fresh GameCore
process restores the saved consideration flag for the unblocked two-envoy
reserve without refreshing notifications. The public observation and decision
catalogue match exactly after identity rebinding. The resumed client then sends
one envoy to the same city-state, observes the reserve drop from two to one and
the city-state count rise from zero to one, and saves again with peace intact.
Private evidence is recorded in
`evidence/host-xp2-bbg-city-state-peace-exact-resume-and-envoy-native.json`.

The v4 overview adds `major_deals`, in the same order as the met major targets.
Each row reports the native pending-deal flag and the player's recurring gold
and resource terms shown in the official report. Terms include direction,
amount and remaining turns. Resource terms carry the native resource index.
Older checkpoints retain their saved observations and choices on comparison.
A native T63 witness observes one met counterpart with no pending deal and
no recurring terms. Nonempty terms and pending offers have software coverage.
Private evidence is recorded in
`evidence/host-xp2-public-major-deals-readback-native.json`.

The v5 overview adds `major_deals[].counterparty_is_human` and offers
`CHOICE_MAKE_DEAL` for a met, living AI major when the official choice is
enabled and the pair has no pending deal. Use that candidate through `act`.
The reply's `decisions.deal_draft` reports the counterparty, the native item
count (zero in this supported path), and the native pending flag. The modal
offers `CHOICE_EXIT` when the session can close. The T63 witness on the installed
Gathering Storm with BBG 7.5.1 creates and cancels this draft through the native
session, then saves successfully. Private evidence is recorded in
`evidence/host-xp2-major-deal-draft-open-close-native.json`.

The v3 deal modal adds `decisions.deal_gold` for the local player's lump-sum
gold. It reports the amount in the draft, the available maximum, and the AI
response to the latest inspection or proposal. Select `CHOICE_SET_DEAL_GOLD`
through `act` with `parameters={"amount": 17}` to request 17 gold. Zero requests
removal when a gold item exists. A nonempty valid edit invokes the official
inspection. The edit receipt and the AI response describe different steps.

The native T63 witness changes an empty draft to 17 gold, receives the AI's
negative inspection response, and cancels the draft. The player's treasury is
unchanged and the successor saves successfully. At T57, the client observes a
positive inspection of 90 gold. When `deal_gold.finalize` is `"accept"`, select
`CHOICE_FINALIZE_DEAL` through `act`. GameCore debits the selected amount before
the API returns a completed command. A settled draft offers its native exit.
The T57 witness closes the negotiation and saves the new balance. An independent
reload restores the same public state and choices. The client then adds and
removes 3 gold in a new draft, closes it, and saves with the same treasury.
Private evidence is recorded in
`evidence/host-xp2-deal-gold-draft-rejection-native.json`,
`evidence/host-xp2-deal-gold-transfer-native.json` and
`evidence/host-xp2-deal-gold-transfer-reload-native.json`.

The v4 modal keeps `deal_gold` and adds `decisions.deal_recurring_gold` with
`amount`, `max_amount` and the native `duration` in turns. Select
`CHOICE_SET_DEAL_GOLD_PER_TURN` through `act` with `parameters={"amount": 5}`
to request 5 gold per turn. Zero removes the selected recurring term.
Both outgoing gold terms can coexist in the same draft, and the finalization
choice applies to the whole draft. After confirmation and exit, read the
active recurring transfer in `information("diplomacy")` under
`major_deals[].terms`. The immediate treasury debit is the lump-sum term.
On the installed Gathering Storm + BBG 7.5.1 LAN build, a fresh process
restored the turn-57 deal and advanced through the native scheduler until the
local player became active on turn 58. At that boundary the deal reported 29
remaining turns and player gold rose by 5 less than on the pre-deal control
branch. Both branches saved at turn 58.
The v5 modal adds `deal_requested_gold` and `deal_requested_recurring_gold`
to a draft the local player opens with a met AI major. These fields quote the
gold the counterpart can give. Select `CHOICE_SET_REQUESTED_DEAL_GOLD` for a
one-time request or `CHOICE_SET_REQUESTED_DEAL_GOLD_PER_TURN` for a recurring
request, with the same `parameters={"amount": n}` binding. Both inventories
remain available in one draft. An amount of zero removes just the selected
request. Confirmation checks the net one-time treasury
change and the exact outgoing and incoming recurring terms in the public report.
The installed Gathering Storm + BBG 7.5.1 LAN witness received 8 gold against
7 gold per turn and then paid 90 gold for 1 gold per turn. Each agreement was
confirmed by GameCore, and both active recurring terms appear in the saved
public catalogue. An independent process restored both terms, removed each
kind of requested gold in a new draft, and closed that draft with both active
terms intact. At player activation on turn 58, both terms had 29 turns left
and the treasury had gained 6 less gold than the pre-deal control branch.
Other deal terms, received offers and human counterparties remain explicit
coverage gaps.

The v6 deal modal also exposes `deal_resources`, with the resource index and
type, inventory direction, native quantity limit, availability and any draft
quantity and duration. Select `CHOICE_SET_DEAL_RESOURCE` or
`CHOICE_SET_REQUESTED_DEAL_RESOURCE` through `act` with
`parameters={"resource_index": 31, "amount": 1}`. Quantity zero removes the
matching draft item. Resource edits use the pinned `SetValueType` companion
for each new resource item. The catalogue reports
`native_deal_resource_type_write_unavailable` on hosts missing that companion.
The installed Gathering Storm + BBG 7.5.1 LAN witness confirmed one unit of
Truffles for 30 turns in exchange for 14 gold and 3 gold per turn. The public
diplomacy report contains both recurring terms. Horses and Iron quotes were
also observed. Their transfers and the opposite resource direction have
separate qualification remaining.

Resource duration follows `DiplomacyDealView_Expansion2.lua` and the loaded
`Resource_Consumption.Accumulate` flag. Accumulating resources use duration
zero and settle against the native stockpile. Other resources use a 30-turn
term in the diplomacy report. The installed LAN witness edited and removed
one-time Iron and Horses drafts after the AI refused both offers. Their
accepted stock transfer still requires a native witness.

The v7 deal modal adds `deal_equalize` and offers
`CHOICE_EQUALIZE_DEAL` when the qualified AI deal is eligible for negotiation.
Pass the candidate ID to `act` without parameters. An `adjusted` response
replaces the displayed terms with GameCore's adjusted draft. An adjusted draft
can be empty or lack a confirmation candidate. Confirm it through
`CHOICE_FINALIZE_DEAL` when the new revision offers that candidate.
An `equalize_failed` response makes negotiation unavailable until
the draft changes. For an outgoing gift it also removes the confirmation
choice, as the installed deal panel does. The host checks the exact reply
and supports counteroffers composed of the admitted gold and resource terms.

In the installed Gathering Storm + BBG 7.5.1 LAN witness, the client requested
one unit of Truffles, obtained native terms of 22 gold and 2 gold per turn for
30 turns, and confirmed them explicitly. An independent process restored both
active terms and the treasury. It also observed an empty adjusted draft and a
native negotiation failure, then observed negotiation become available after
editing the failed draft. At turn 59 the original agreement had 29 turns left.

On this installed Gathering Storm profile, `information("diplomacy")`
uses the v6 overview. Each met major player's `major_deals` row exposes
`open_borders.outgoing` for passage you grant and `open_borders.incoming`
for passage you receive. The v8 deal modal adds `deal_open_borders`, with
GameCore's available duration and current draft duration for each direction.
Use `CHOICE_OFFER_OPEN_BORDERS`, `CHOICE_REQUEST_OPEN_BORDERS`,
`CHOICE_REMOVE_OFFERED_OPEN_BORDERS`, or
`CHOICE_REMOVE_REQUESTED_OPEN_BORDERS` when offered. These choices take no
parameters. Review the resulting terms before selecting `CHOICE_FINALIZE_DEAL`.

The Gathering Storm + BBG 7.5.1 LAN witness added and removed both draft terms,
then confirmed one reciprocal agreement. GameCore quoted both terms at
20 turns, and both passage rights appeared in the public report and checkpoint.
An independent process restored the agreement and moved the selected unit
from (20, 11) to the neighboring player's tile at (21, 11). The same click
from the save before the agreement opened the war confirmation. The client
declined it, and the unit remained on its original tile. Both paths saved
and closed normally.

The v7 overview offers `CHOICE_MAKE_DEMAND` for a met AI major when
GameCore shows the choice and there is no pending deal. The v9 demand modal
exposes `deal_demand` and the requested gold, gold per turn, and supported
resource terms. Edit those terms using the requested-side choices. Select
`CHOICE_FINALIZE_DEAL` to submit when `deal_gold.finalize` is `"demand"`.
For a rejected demand, read `deal_gold.response` and select `CHOICE_EXIT`.
City, great-work and captive terms remain outside this API profile.

The Gathering Storm + BBG 7.5.1 witness opened the demand, added and removed
Truffles, then requested one gold. GameCore refused the demand. The client
showed the refusal, kept the treasury and active trade terms, and saved and
closed normally. A second witness requested one gold per turn after moving
two units through the open border. GameCore accepted and applied one agreement
for 30 turns when the host delivered the accepted transaction. The client read
29 turns remaining at T60 and saved that state. A fresh GameCore process
restored the same player observation and choices. After the client advanced
to T61, the same agreement appeared once with 28 turns remaining. That state
was saved before normal teardown. The host verifies the terms after delivery
before returning a completed result.

The v8 overview can expose `CHOICE_MAKE_PEACE` for a met AI major with no
pending deal when the official greeting menu enables it. This opens the
official deal draft. The modal reports the two locked treaty terms as
`deal_peace`, including their durations. The v11 route requests the official
opening inspection and reports the native reply. It reuses the deal choices
for supported gold, resource, and open-borders terms. Confirmation through
`CHOICE_FINALIZE_DEAL` requires accepted or adjusted terms that match both
working deals. `CHOICE_EXIT` cancels an unsigned draft when the native
session can close. Historical v10 replies carry the opening-only schema.

The Gathering Storm + BBG 7.5.1 LAN witness kept the peace choice disabled
from T57 through T64. GameCore enabled it at T65. The client opened a native
draft, read two locked agreement items, cancelled it, and confirmed the same
war state before saving and closing. Both items reported a native draft
duration of zero. The witness covers opening and cancellation.

A second T65 session received the AI's positive inspection with no payment.
The client selected `CHOICE_FINALIZE_DEAL`, read the settled dialogue with
zero live draft items, and closed it. GameCore reported the end of war and
saved the resulting state. A fresh process restored identical public
observations and decisions. After advancing to T66, it reported the AI's
denunciation and the two civilizations were still at peace.

## Trade information

On a supported Base hotseat session, `client.information("trade")` reads the
current player's two native trade catalogues from the cached decision. The
result includes outgoing routes, offered destinations with their native paths
and yield quotes, and the offered changes of origin. It carries the same
episode, turn, sequence and decision ID as `client.view()` and makes no engine
call. A different player's trade catalogue requires their own acting boundary.

Submit `make_trade_route` and `change_trade_origin` through `act` using their
candidate IDs from `view()["decisions"]`. The client checks that these commands
match the native catalogues. The same read contract is available on
`SessionClient` for the local Gathering Storm and BBG 7.5.1 profile. Set
`trade_diagnostic=True` on the current-image `NetworkBackend` with its
source-qualified governor and initial-diplomacy options. The v34 catalogue
publishes `trade_routes` and `trade_origins` for the acting player. While
waiting or after closure, these fields are unavailable.

The T50–T52 native witness changes a Trader's origin, starts a route to a
city-state and reads back both the active route and the official BBG
`CS_TRADERS` change before saving and closing. The BBG property readback
is kept in the host receipt. The public client receives the trade catalogue.
A fresh process reloads the same observation and both catalogues with the route active.
The retained route then expires natively at T63. At T64 the active route is
absent and the BBG script has removed the city-state from `CS_TRADERS`. The
client chooses the offered route with the same Trader and confirms both the
new active route and the restored BBG property. Save, Unload and Destroy
complete normally. The renewed checkpoint is available for the next reload.
The witness covers one route and one human LAN seat. Other route-ending cases
remain open.
Private lab receipt: `evidence/host-xp2-bbg-route-expiry-renewal-native.json`.

The v41 contract adds `client.information("trade_overview")` for the two
source-selected GS + BBG 7.5.1 captures. It carries the active count and capacity,
outgoing and incoming routes, and city pairs visible in Available Routes, with both
displayed yield quotes. Incoming rows omit foreign Trader IDs. The v40 choices
and candidate IDs are preserved. A disabled view or an unproven unlock state
returns an explicit unavailable status. At T9 the native reader reports an
unproven unlock. At T16 the client reads capacity 1 and one slot to produce a
Trader, then reloads that observation and its decisions exactly. The continuation
buys a Trader, sees Washington → Rapa Nui in Available Routes and submits the
offered route. At T19 the same pair and Trader appear in the active tab, with
the displayed origin yield of 3 gold. Save, Unload and Destroy complete normally.
Private lab receipt: `evidence/host-xp2-bbg-world-a-positive-trade-native.json`.

World A now selects the same BBG yield helper in the chooser's catalogue,
request freshness check and post-command readback. The software fixture checks
both displayed directions for the local established Amani and the unchanged
result for a foreign governor. A native T19 reload with this helper preserves the
public observation and v41 decision catalogue. Early Empire grants a title, and
the client appoints and assigns Amani to Rapa Nui at T24. At T29 the engine
establishes Amani and the Washington–Rapa Nui route displays 2 extra food and
2 extra production at both ends. The 3 gold at Washington remains part of the
displayed quote. The native Save completes and the supervisor verifies Unload
and Destroy. The run consumes FeatureAddedToMap, FeatureChanged and
FeatureVisibilityChanged in the same ordered queue.
See the private lab receipt `evidence/host-xp2-bbg-world-a-amani-trade-native.json`.

The T29 checkpoint reloads with identical public observations and decisions.
At T35 the original Trader is idle and both views show the offered route with
the trading post, the same yield tooltips and 2 food and 2 production at both
ends. Washington also shows 4 gold, including the 1 gold path bonus. The client
submits the offered repeat route. The native operation restores the active
row, BBG's city property records the destination again, and the engine saves
the T35 checkpoint before Unload and Destroy. This witness contains no incoming
route. See `evidence/host-xp2-bbg-world-a-amani-renewal-native.json` in the lab.

The Boston T62 checkpoint reloads with its observation and all v40 decision
fields intact. The v41 player frame includes Hattusa → Boston with both
display quotes and omits the foreign Trader ID. The supervisor verifies Save,
Unload and Destroy. The source-selected display preserves signed values from
the official helper. The trade hook now also keeps an already-unlocked panel
available if capacity falls to zero within the same session. That edge case is
covered by a fixture.
Private lab receipt: `evidence/host-xp2-bbg-incoming-trade-native.json`.

On the current World A capture, the ordered `CivicCompleted` notification
for the local player checks outgoing capacity while handling Foreign Trade
at T16. The native read returns 1 and opens the panel before the first
public T16 decision. The preceding T15 decision has the panel locked.
Save, Unload and Destroy complete normally. A civic completion between
two decisions in one turn and a reload of the new checkpoint still
require separate witnesses.
Private lab receipt: `evidence/host-xp2-bbg-trade-civic-hook-native.json`.

The new v41 checkpoint also reloads with the same observations and choices.
The incoming route remains visible at T63 and T64. At T65 the GameCore logs
`Route Ended (Expired)` for Hattusa → Boston and the matching row disappears
from the player's Python frame. The reciprocal outgoing route had expired
separately. The session saves at T65 and verifies Unload and Destroy.
Private lab receipt: `evidence/host-xp2-bbg-incoming-trade-expiry-native.json`.

### Rise and Fall trade

On the exact installed Rise and Fall LAN capture, `xp1_trade=True` adds
`information("trade", player_id=pid)` and the native route and origin
choices under `v11.captured-city.v10`. The public catalogue uses the same
stock TradeSupport logic as the official chooser. A waiting player has
neither trade catalogue.

The native witness selected Foreign Trade at T22 and ordered a Trader at
T23. At T25 the chooser offered four destinations with their paths and
yields. The client selected `make_trade_route` for Saragossa, and the
GameCore returned the new active route and saved it. A fresh process
restored the route, the player observation and the same native choices.
On a separate two-city checkpoint, the T19 chooser offered the other
owned city. The client submitted `change_trade_origin`, the same Trader
arrived in that city with zero movement remaining, and GameCore saved.
A fresh process restored the exact observation and decision catalogue.
Private lab receipts `host-xp1-stock-trade-route-save-reload-native.json`
and `host-xp1-stock-trade-origin-save-reload-native.json`.

Selecting `xp1_trade_overview=True` also exposes the stock panel through
`information("trade_overview", player_id=pid)` under `v11.captured-city.v11`.
A retained T25 save restores the old observation and decision fields and
publishes capacity 1, one active route and the route yield of three gold.
The incoming tab returned an empty list in this save. The native receipt
is `host-xp1-stock-trade-overview-active-native.json`.
From the retained T22 save, the panel is unavailable before the player
selects Foreign Trade. At T23 the owned CivicCompleted notification
enables the panel before the first playable view, with capacity 1 and
one Trader production slot. The native receipt is
`host-xp1-stock-trade-overview-unlock-native.json`.

### Rise and Fall government and policy choices

On the same stock Rise and Fall LAN capture, `xp1_government=True` adds
`decisions["government"]` and `decisions["policies"]`. The flag can be used
with or without the trade groups. The policy candidate takes one unsigned
policy hash per slot in `parameters={"assignments": [...]}`.

At T22 the official Core returned two empty slots and three options per
slot. The Python client submitted Discipline and God King. Core applied
both, reduced the open slot count to zero, saved, and restored the exact
observation and decisions in a fresh process. The native receipt is
`host-xp1-stock-free-policy-save-reload-native.json`. Government options
were read at T22. An actual change or retention needs a separate native
witness. Paid unlocks, active card relocation, unchanged confirmation and
anarchy remain outside the qualified scope.

### Rise and Fall tile purchases

On the stock Rise and Fall LAN capture, `xp1_plot_purchase=True` adds
`decisions["plot_purchases"]` and the legal, affordable ordinary gold
purchase choices. It composes with the trade and government flags. The
caller submits the candidate for its city and tile at the quoted price.

The native T22 witness bought tile (43, 26) for Paris after the free
policy assignment. The treasury decreased from 938.25 to 898.25, the
tile gained the requested owner and city, and the acquired tile left
the offers. A new process restored the exact observation and decisions,
including the policies already in place. The native receipt is
`host-xp1-stock-plot-purchase-save-reload-native.json`. Purchases of city
items, faith and placement-filtered acquisition remain separate.

### Rise and Fall gold unit and building purchases

With `xp1_plot_purchase=True` and `xp1_city_purchase=True`, the same client
also reads `decisions["city_purchases"]` and can select an ordinary gold
unit or building. Each offer retains the quoted price, the native command
legality flag and the affordability flag. A request must match the
fresh offer, native archive, effect and treasury debit.

In the retained game the client bought a Scout for 60 gold at T22. The
player selected Pottery and advanced the turn. At T23 the client bought
a Granary for 130 gold and the engine confirmed possession in Paris.
An independent process restored the public observation and all previously
saved decisions exactly. The native receipt is
`host-xp1-stock-building-unit-purchase-save-reload-native.json`.

The opt-in `xp1_city_buildings=True` adds the read-only player group
`information("city_buildings", player_id=pid)` and the corresponding
decision field. Each entry carries its owned city, visible owned plot,
building index and hash, completion and pillage status. Several buildings
can share a plot. At T23, a fresh GameCore process restored Paris with the
Granary complete and intact, the purchased Scout, and 706.59765625 gold.
The native receipt is `host-xp1-owned-city-buildings-after-purchase-native.json`.

On the same Rise and Fall profile, `city_buildings` includes the player's
Great Work slots, compatible destinations, theme progress, displayed yields,
and combined tourism. The reader follows the inherited base overview selected
by Rise and Fall. The local human seat can select `move_great_work` from its
active choices. The host validates the archive, consumes the move notification,
and checks both slots before returning completion. At T43, the client activated
Bhasa and moved his work from the Amphitheater to an empty Palace slot. An
independent GameCore process restored that slot, the public observation and
the saved decision catalogue. At T44, the client activated Bhasa again and
swapped his two works between the Amphitheater and the Palace. An independent
GameCore process restored both works in their exchanged slots with the same
public observation and choices. The private receipts are
`evidence/host-xp1-great-work-empty-slot-save-reload-native.json` and
`evidence/host-xp1-great-work-occupied-slot-swap-save-reload-native.json`.
Earlier building checkpoints compare their original choices.

The exact stock Gathering Storm LAN profile on the current installed image
accepts `xp2_city_buildings=True` and exposes the same public information
group. A new process restored T94 with the same prior observations and
choices, and read six building rows. Both the Shrine and the Temple were
complete and pillaged while their Holy Site had already been repaired.
The native choice list offered production of the Shrine. Private receipt
`evidence/host-xp2-stock-city-buildings-t94-native.json`.

On the pinned stock and BBG 7.5.1 profiles, `information("city_buildings")` includes
`great_work_slots` for completed buildings in the player's own cities.
Each row identifies the building, slot type and Great Work, or carries a null
work for an empty slot. For occupied slots, `move_unlocked` reports the
official artwork age and artifact museum checks. The same response lists
the permitted slot pairs in `great_work_move_targets`, with a `source` and a
`destination` identified by city, building and slot. The installed game
rules check slot compatibility, both sides of a swap and museum restrictions.
The rules also check whether the official Great Works view is enabled.
The captured game databases set the artwork lock to 10 turns in stock
Gathering Storm and 2 turns in BBG 7.5.1. The host reads the active game's rule.
The current decision catalogue includes `move_great_work` when the acting
player can issue those orders. Each choice binds the two slots, the source
work index and the destination work index when occupied. Pass its candidate
ID and decision ID to `act`. The host authenticates the emitted GameCore
archive and checks the resulting work placements before returning completion.
Source and fixture checks cover moves and exchanges on both profiles.
At T111, the stock profile returned an empty Palace slot and an empty Temple
relic slot, with zero move choices. The GameCore saved this state and closed
normally. The private receipt is
`evidence/host-xp2-stock-great-work-slots-empty-t111-native.json`.
At T111, a stock witness activated Karel Čapek, moved his first work into
an empty Palace slot and restored it in a new GameCore process. The same
saved continuation reached T112, activated him again and exchanged his
two works between occupied Palace and Amphitheater slots. The new save
restored both exchanged works, the public observation and the saved
decision catalogue in a separate process. The private receipts are
`evidence/host-xp2-stock-great-writer-work-move-reload-native.json` and
`evidence/host-xp2-stock-occupied-great-work-swap-save-reload-native.json`.
Native move/save/reload qualification remains pending on BBG 7.5.1.

The same panel reports `great_work_building_bonuses` for each building with
slots. The theme is `null` when the game shows no label, `progress` with the
displayed matching and total slot counts, or `themed` when the building has
the bonus. Each row includes the positive yields from those works and the
combined tourism shown by the official panel. Older checkpoints compare
their original observations and action choices. The native bonus readback
remains to be qualified.

The same option is available on the pinned Boston Gathering Storm + BBG 7.5.1
LAN capture and current installed image. It uses the same official city panel
bindings and remains player-scoped. Older checkpoints remain comparable with
the option enabled, including checkpoints with Great Person commands. Native
BBG readback is pending.

### Rise and Fall unit promotions

The stock Rise and Fall LAN capture accepts `xp1_promotions=True`. The
`unit_promotions` decision field contains the own-unit experience, acquired
promotion indices and current native offers. Call `act` with the selected
`promote_unit` candidate ID.

At T19 the local Warrior had two offers. The client selected Battlecry
and GameCore acquired it, reduced damage from 56 to 6 and left zero
movement. Save and a new process restored the exact unit, experience,
promotion and decision catalogue. The native receipt is
`host-xp1-stock-unit-promotion-save-reload-native.json`.

The cached player group `information("unit_promotions", player_id=pid)`
returns the same roster and offers with the observed decision identity.
On a session that publishes upgrade quotes, `information("unit_upgrades", player_id=pid)`
also returns visible quotes the engine has marked illegal. Only offered
candidates can be submitted through `act`.

### Rise and Fall unit upgrades

The stock Rise and Fall LAN capture accepts `xp1_unit_upgrades=True`.
The client exposes the owned unit, target unit type, gold quote and
legality through `unit_upgrades`. Rise and Fall's resource-access
prerequisites stay in the native eligibility check. The stockpile-cost
fields are null for this profile.

At T26 GameCore offered the Slinger-to-Archer upgrade for 20 gold. The
Python client selected it, the engine replaced the unit on the same
tile and the treasury fell from 636.640625 to 616.640625. An independent
process restored the Archer, balance, public observation and choices.
This verifies the Slinger upgrade on this capture. Resource-gated
upgrade variants still require native evidence. Private lab receipt
`host-xp1-stock-unit-upgrade-save-reload-native.json`.

### Gathering Storm without BBG

The exact retained stock Gathering Storm LAN profile accepts
`standard_trade=True` with its current engine and official capture. The
decision schema is `civ6-host.network-capability-decisions.standard-trade.v1`.
The `trade` and `trade_overview` groups refer to the same native decision.
The stock adapter uses the stock yield helper and keeps foreign Trader IDs
out of incoming rows. Unsupported reader states are reported explicitly.

The T44 witness restores Rome's public observation, reads capacity 1 and
executes the offered 90-gold Trader purchase. Native readback and the new
checkpoint contain the Trader and the new balance of 86 gold. Unload and
Destroy complete normally. A fresh process reloads the same schema,
observations and decisions. The T49 checkpoint retains the Trader, the
Settler and its prospective escort. Private lab receipt
`evidence/host-xp2-standard-trade-panel-purchase-native.json`.

For this stock capture, `unit_formations=True` adds the v2 decision schema
and `client.information("unit_formations")`. The public group lists each
owned unit's formation count and movement values. The engine supplies the
partner choices. The caller chooses a `unit_formation` candidate with
`command` equal to `enter` or `exit`. Exit has a null `partner_id`.
The native formation identity stays inside the host and is used to verify
that the chosen pair joined the same formation. The v1 stock checkpoint
can resume into this opt-in schema with its existing choices unchanged.

The retained native witness joins a Warrior and a Settler, separates them,
joins them again, and moves both units with one command on each of two
turns. A second run saves at T50 with both units still linked at (37, 13)
and completes native Unload and Destroy. A fresh process restores the v2
observation and decision catalogue exactly, including the formation.
The continued session uses the offered defensive attacks and founds Ostia
at T52. See the private lab receipts
`evidence/host-xp2-stock-unit-formations-save-native.json`,
`evidence/host-xp2-stock-formations-v2-resume-defence-native.json` and
`evidence/host-xp2-stock-ostia-foundation-native.json`.

In this capture the Trader chooser offers Rome → Ostia while the available
routes tab lists two departures from Ostia. The stock panel queries city
pairs and the chooser checks the selected Trader's native operation. Use
the exact candidate in the decision catalogue to request a route. The
available routes tab is a separate public view.

The T52 settlement checkpoint restores the same observation and decision
catalogue. The offered `make_trade_route` command starts Rome → Ostia.
Both public groups read the same active route and the native route count
increases from zero to one. The stock quote and active row display one
food, one production and one gold for Rome. The T52 checkpoint includes
the active route and native Unload and Destroy complete normally.
Private lab receipt `evidence/host-xp2-stock-rome-ostia-native.json`.

Reloading the active-route checkpoint preserves the public observation
and catalogue. Both groups retain Rome → Ostia through T56. At T57
the route disappears from both groups and the Trader leaves Rome's
roster. The native trade log records `Route Ended (Plundered)` for
that city pair. Its reason remains in private diagnostics. The
session saves at T57 and completes native Unload and Destroy.
Private lab receipt `evidence/host-xp2-stock-rome-ostia-lifecycle-native.json`.

From the checkpoint before departure, the offered `change_trade_origin`
command moves the same Trader from Rome to Ostia and uses its movement
on T52. On T53 the public chooser offers Ostia → Kabul. The requested
route is active in both public views through T61. After resolving the
policy notification and the optional achievement service, the GameCore
consumed the named obsolescence record and published T61. It delivered
the subsequent forced turn request without an observable transition.
The recorded primary blocker at that checkpoint was a dedication.
Private lab receipt
`evidence/host-xp2-stock-ostia-kabul-continuation-native.json`.

### Era dedications

The installed Rise and Fall LAN capture exposes the same public
`dedications` group and `confirm_dedications` candidate under
`v11.captured-city.v9`. A v8 checkpoint can reopen with v9 when the
historical public state and choices match. At T31 the client read four
choices, confirmed the scientific dedication and observed it active
with zero selections remaining. GameCore saved the state and closed
normally. A fresh process restored the same observation and choices,
including the active dedication. Multi-selection ages remain to be
qualified. Private lab receipt `host-xp1-dedications-save-reload-native.json`.

The opt-in `stock_dedications=True` extends the existing stock formation
profile with a public `dedications` group. The group contains the acting
player’s era, age, remaining selection count, offered type indices and
active dedications. The decision carries one `confirm_dedications`
candidate when the popup offers selections. Pass `{'indices': [...]}`
to `SessionClient.act` with exactly the required number of distinct,
offered indices in the desired order. The command reports completion
after the native archives are delivered and the player cache confirms
the active dedications and the consumed selection count. This profile
currently targets the pinned stock Gathering Storm capture and engine.
On the retained T52 checkpoint the client read four Dark Age offers,
confirmed `COMMEMORATION_SCIENTIFIC` through one native operation
archive, and observed it active with zero selections remaining. The
session saved at T52 and completed native Unload and Destroy. A new
process reloaded the checkpoint with the same public observation and
catalogue. It opened Ostia → Kabul at T53 and confirmed the next era
dedication at T61. The T61 save retains the active route and dedication.
Multi-selection ages still need native qualification. Private lab receipts
`evidence/host-xp2-stock-dedications-confirmation-native.json` and
`evidence/host-xp2-stock-dedications-reload-trade-native.json`.

With `world_congress_diagnostic=True` and
`world_congress_review_diagnostic=True`, the stock dedication profile
adds the Congress catalogue, public review, active resolutions and
native command permissions under `standard-trade.v4`. A v3 stock
checkpoint can load through this profile when its observation and
previously recorded decision fields still match.

On the retained stock world, choosing Military Tradition and issuing
the offered forced turn request opened regular Congress at T61. The
native strategic and tactical command permissions were both false.
The shared client transmitted two B/1 votes and the native submission.
Play resumed at T62, both permissions were true and the review contained
both exact own votes. The native record leaves vote origin indeterminate
and carries no completion echo. The active resolutions were public and
Ostia → Kabul remained active. The host saved and closed at T62. Other
stock Congress forms still require qualification. Private lab receipt
`evidence/host-xp2-stock-congress-integration-native.json`.

A new native process reloaded the T62 checkpoint with the same public
observation and v4 catalogue. The GameCore trade log records Ostia →
Kabul expiring at the close of T68. On T69 both public trade views
agree that the route has ended and the Trader is idle. The native
catalogue offers a domestic route to Rome. A renewed route to Kabul
was unavailable on that decision. Trade Treaty B sets the
`InternationalMajors` flag. The current native start predicate checks
the corresponding counter when either end of an international route
is a full civilization. Its existing-route removal instead visits
other full civilizations. A route to a city-state can therefore
survive activation and be blocked when the Trader tries to start it
again. The live counter and first failing predicate for the T69
offer still require direct evidence. The host saves and closes at
T69. Private lab receipts
`evidence/host-xp2-stock-post-congress-trade-expiry-native.json` and
`evidence/host-xp2-stock-trade-treaty-major-minor-source.json`.

An alternate branch from the same T61 checkpoint changes only the
Trade Treaty vote in the ballot. The native review and active-effects
views confirm option A. The existing route expires at the close of
T68. On T69 the client sees the idle Trader and the offered repeat
route to Kabul, then selects it. Both public views and the native
trade log confirm the new route with the same Trader. The worker
saves and closes at T69. The new checkpoint has yet to be reloaded.
The earlier B branch was saved and reloaded at T62. Private lab
receipt `evidence/host-xp2-stock-trade-treaty-a-native.json`.

Reloading the earlier T69 checkpoint from the B branch preserves the domestic offer. The
common client starts Ostia → Rome and both public views publish
the route. On T72 the native log records plunder. Both views lose
the route and the public unit roster loses the Trader. The catalogue
offers a replacement at either city for 90 gold. The worker saves
and closes at T72. This witness exercises loss after native combat.
Private lab receipt `evidence/host-xp2-stock-ostia-rome-plunder-native.json`.

The same T72 checkpoint reloads with identical player observations
and choices. Two attacks damage the visible enemy. The third is a
`MOVE_TO` attack that the current Gathering Storm image consumes
without an observable change. The command result is `refused` with
reason `native_attack_consumed_without_observable_effect`. The
following purchase creates an idle Trader at Ostia and costs 90 gold.
Both trade views have no active route. The worker saves and closes
at T72. The new checkpoint has yet to be reloaded. Private lab
receipt `evidence/host-xp2-stock-plunder-recovery-native.json`.

The native XP2 archive omits the per-turn envoy consideration flag.
On the installed current XP2 image, resume restores an outstanding
consideration from the authenticated checkpoint through the original
influence setter. GameCore recomputes the blocker. The host then compares
the entire observation and catalogue, including the restored
`retain_envoys` candidate. The previously refused stock T51 checkpoint and
the GS + BBG 7.5.1 T57 checkpoint both pass this exact comparison. The stock
client can select the restored candidate and keep its tokens.
See the private lab receipt `evidence/host-xp2-envoy-checkpoint-restore-native.json`.

## Espionage information and orders

The current-image GS + BBG 7.5.1 session accepts `espionage_diagnostic=True`
alongside its existing `trade_diagnostic=True` options. Its v35 decision
catalogue adds `espionage`; previous v34 fields and historical checkpoints
retain their meaning. This remains a partially qualified API capability.

`client.information("espionage")["data"]` exposes the acting player's spies,
capacity, known captives, spies travelling off-map, completed mission history
and current offers. Enemy captives have `level=None`, because that rank is not
shown in the corresponding official screen. Probability fields contain the
rounded aggregate percentages shown by the game; `-1` means not displayed.
The query uses the cached player boundary and performs no additional RPC.
The information is unavailable while waiting or after closing the session.

The common `client.act(player_id, decision_id, candidate_id)` path accepts
`spy_travel`, `spy_mission`, `spy_cancel` and `spy_escape` choices from that
catalogue. Orders are revalidated through the native UI API. Offensive mission
start has no coordinate parameters in the underlying native request; counterspy
and travel orders use their offered target coordinates. Escape routes require
the local player's actual escape notification and next escaping spy identity.
The host never chooses a route or mission automatically.

Native archive delivery, order application and mission completion are distinct.
A command is `completed` only when the order's native state change is read back;
that status does not mean the multi-turn mission has finished. An unconfirmed
order is `pending`, and a choice that has become unavailable is `refused`.
Repeat from a mission-completion popup remains explicitly unqualified as
`spy_completion_repeat_pending_identity`; historical missions are not treated
as pending popups. The family's `queried_partial` status and global
`complete_action_space=False` preserve this limitation.

Software fixtures cover all four order types and channel boundaries. Native
spy order execution and completed-mission effects require their own recorded
witnesses; the presence of candidates or a successful empty query is not that
qualification.

The retained T31 native checkpoint has now exercised this v35 query through
`SessionClient`: spy capacity is zero and all spy lists/offers are empty. The
native BBG spy listener loads, the previous promotion and public observation
survive reload, and Save plus Unload/Destroy complete. Peak private memory was
429.7 MiB under the 512 MiB limit. This verifies the empty query and lifecycle,
with no positive spy order or completed mission. The private local receipt is
`evidence/host-xp2-espionage-client.json` in the lab.

### Completion choices

The current source adds v36 with a separate cached public group,
`client.information("spy_completion")`. A current completion comes from the
owned native `SpyMissionCompleted` event. It is never inferred from recent
history. The caller can choose `spy_renew` when the official predicates allow
it, or `spy_completion_dismiss`. Renewal uses the historical plot coordinates,
even when the spy currently occupies another plot, and adds no movement-point
or strategic filter.

Dismissal changes local presentation state and issues no native simulation
request. A renewal enqueues the native order and closes that completion before
the archive is applied, matching the official callback. Closing displays at
most one newest queued completion. A suppressed counterspy result does not
cause the host to drain older records automatically. BBG gameplay effects run
only from the original native event, once per delivered occurrence.

This v36 addition has source and grouped software checks; the previous native
empty-query witness remains v35. Positive completion/renewal events, interaction
with interface-mode changes and notification reactivation still need native
qualification. The API keeps those gaps explicit. Checkpoint creation refuses
a pending completion or its queue until an explicit dismissal clears it;
restoring that presentation lifetime is not yet qualified. This does not block
checkpoints with no pending completions or weaken their previous native proofs.

### Installed BBG listener authority

Native UI callbacks retain their event owner, which can differ from the local
player. Their internal EXECUTE_SCRIPT requests use the official GameCore gate;
a request producing no archive is recorded as filtered, with unchanged native
readbacks, and is never called successful delivery. Public client actions keep
their local ownership checks. Spy callbacks retain the installed Lua's explicit
local-player filter. These private callback receipts are not actor inputs.

The current T52–T56 native interval confirms the foreign-governor filtered case
and local governor delivery. It then stopped on the promotion owner's former
local restriction. The grouped promotion/trade correction passed 67 software
checks after that run; the run does not qualify those corrected foreign cases.
No checkpoint or route expiry was observed in this interval. Private lab proof:
`evidence/host-xp2-bbg-listener-authority-native.json`.

## Rise and Fall faith purchases

The installed stock `xp1-lan` backend accepts `xp1_faith_purchase=True`
together with `xp1_city_purchase=True` and `xp1_plot_purchase=True`.
The existing `city_purchases` catalogue then retains gold and faith offers
as separate choices, including visible but unaffordable offers. Command
candidates require the native legality and affordability checks. Select the
returned candidate through `SessionClient.act()`; its `purchase` action carries
the currency and exact quoted price. The host rechecks the quote immediately
before requesting the official command and verifies the item and wallet change.

This adds `.faith.v1` after the stock city-purchase schema. Older checkpoints
retain their original comparison fields through an explicit projection; their
contents are not rewritten. Tile purchases still use gold. Unit formations,
district purchases and other listed catalogue gaps remain separate.

The XP1 adapter is source-checked and integrated. A native T37–T40 continuation
completed the Holy Site, bought the offered Shrine for exactly 140 gold, and
saved the resulting state. Its faith catalogue remained empty, including after
the Shrine purchase. No positive faith purchase or faith debit is qualified by
that interval. The city has majority-religion index -1; that observation alone
does not establish which prerequisite is missing or require founding a religion.
Do not infer support for other rulesets or mods from this integration.

## Rise and Fall production information

The installed stock XP1 modern catalogue branches include an additive
`.production-info.v1` schema. `SessionClient.information('production')`
returns `civ6-host.production-inputs.v3` with `current`, `queues` and `quotes`
from the same accepted player observation and decision revision. Current items
carry their official progress, cost, name and remaining turns; quotes follow
the shipped production-panel visibility rules for the offered production items.
Raw verification getter values remain in the private diagnostic trace.

The reader uses the existing native XP1 production bindings. It adds no cost
or completion-time formula. Waiting boundaries explicitly leave these fields
unavailable. Older checkpoint comparisons remove only the added fields through
a versioned projection; they preserve previous choices, including faith purchases.
The native T37–T40 interval now verifies these public values through the Python
client: the resumed Holy Site advances from 0 to 18 to 28 invested production
against its native cost of 29, then becomes explicitly `completed`. Native
remaining turns are retained even for a completed item; consume the `state`
field as well as its item fields. The final native checkpoint is saved and the
engine closes normally. A separate ordinary process reloads the final state
with exactly the same public observation, semantic catalogue and new production
and city-religion fields, then closes normally. The two processes remain below
512 MiB (375 MiB maximum peak commit), with every monitored source unchanged.

The same exact installed XP1 profile also publishes
`SessionClient.information('city_religion')` as `civ6-host.city-religion.v1`.
It contains the native signed majority-religion index for each owned city,
joined to the observation's complete own-city set and revision. The official
city UI excludes `-1` from its dominant-religion entry. Other indices are
preserved without inferring names, beliefs, followers or pressure. Those fields
and religious choices remain separate work. The same native interval returns
index -1 for the owned city through the public client at each decision boundary.
It qualifies that readback, not a positive religious conversion. Historical
engine profiles keep their previous schema and do not call these new readers.

Private lab evidence:
`evidence/host-xp1-public-production-religion-save-reload-native.json`.
This is stock XP1 on a retained fixture-derived state: an earlier levy diagnostic
granted gold to an ancestor. This interval adds no grant and is not a witness of
an entirely unassisted game history or strategic training readiness.

## Rise and Fall explicit pantheon choice

On the exact installed stock XP1 LAN profile, `xp1_pantheon=True` enables the
versioned `pantheon` family and `SessionClient.information('pantheon')` at the
same decision revision. The native query supplies all currently offered belief
indices and hashes, or its explicit `already_has_pantheon` / `cannot_create`
state. Select a normal catalogue candidate with `SessionClient.act`; the host
requeries the choice, requests the native operation, and confirms the acquired
belief from the published native view. A native CanStart refusal remains a
refusal, without submitting an archive. Waiting or closed boundaries are
unqueried, not empty catalogues. Older checkpoints compare their previous fields
through the explicit additive `.pantheon.v1` projection.

The retained stock XP1 T40 interval now qualifies this client path: 20 native
offers were exposed, belief index 0/hash 1202591333 was selected explicitly,
the native readback confirmed acquisition, and faith fell from 71.3203125 to
59.3203125. The final state was saved and closed normally. An independent
process reloaded exactly the observation, semantic catalogue and pantheon query,
with `not_due/already_has_pantheon`, then closed normally without a gameplay
order. Both qualified processes stayed below 512 MiB; peak commit was 380 MiB.

Closing preserves the existing reduced terminal v11 catalogue; it does not
append optional active-choice groups after their preceding fields disappear.
Private evidence: `evidence/host-xp1-pantheon-save-reload-native.json`.
This qualifies one selected belief on the exact installed stock XP1 profile,
not all belief effects, religion founding or faith purchases. The retained
ancestor includes the earlier diagnostic gold grant described above. These
instrumented acceptance runs are not a production-throughput benchmark.

## Rise and Fall belief addition

The exact installed XP1 LAN profile now has an explicit
`xp1_religion_beliefs=True` group. It can be selected independently of
`xp1_pantheon`. `SessionClient.information('religion_beliefs')` contains the
player's own founded-religion state and the native `ADD_BELIEF` choices;
candidate actions keep their native index, hash and class. Actor-facing data
omits diagnostic/proof metadata. A founded religion with no unspent belief is
distinct from no founded religion, and from an unqueried waiting/closed state.
The native founding-unit flag is retained even when it remains true after
consumption; it is not reinterpreted as a unit-count estimate.

Public contracts, the shared saved-owner adapters and the session route are
integrated. The native T40 readback now returns the same public boundary as the
client: no founded religion, no holy city, zero earned beliefs and no offered
ADD_BELIEF choice. Its additive checkpoint projection preserves the previous
observation and choices, and Save/close complete normally. This is a readback
witness; no gameplay order was sent in that initial readback interval.
Private evidence: `evidence/host-xp1-religion-beliefs-readback-native.json`.
The subsequent T40–41 client interval selected follower belief 24 and worship
belief 33 through native `ADD_BELIEF`. Both appeared in the founded religion,
and an independent process recovered the exact final public state and choices.
Evidence: `evidence/host-xp1-religious-chain-save-reload-native.json`.
The current reader supports an absent holy city or
one still owned by the acting player, and refuses other ownership states.
Prophet activation, religion founding, custom names and the displayed pantheon
faith threshold are outside this delivered group. No numeric faith threshold
is substituted for the official getter.

## Rise and Fall predefined religion foundation

`xp1_religion_founding=True` adds
`SessionClient.information('religion_founding')` and explicit `found_religion`
candidate actions on the exact installed XP1 LAN profile. The option works
independently of the pantheon and belief-addition groups. Each candidate keeps
the native religion index and hash; availability comes from the native state
and the official screen filters. Applying an offered choice rechecks that state,
submits the official operation, then verifies the founded religion and holy
city. A native refusal is returned without an action archive or a fake success.

The family remains `queried_partial`: custom religion names are not yet
qualified. Selecting a predefined religion does not silently allocate beliefs.
Waiting/closed boundaries remain unqueried, and the previous terminal catalogue
is preserved. The integrated runtime, public contract and composed session pass
19 offline checks. Native foundation of predefined religion 1/hash 35560851
and its independent Save/Reload are now verified in the T40–41 religious
chain. This does not qualify custom names or all religion effects.
Private evidence: `evidence/host-xp1-religion-founding-api-integration.json`.
Native evidence: `evidence/host-xp1-religious-chain-save-reload-native.json`.

## Rise and Fall current Great People information

`xp1_great_people=True` enables `SessionClient.information('great_people')`
on the exact installed stock XP1 LAN profile. It returns the current native
timeline, the acting player's points by class, current recruitment/rejection
flags and gold/faith patronage quotes. Native fixed-point precision is retained.
The identity of an unmet claimant is masked according to the official popup;
no other player's point balance is queried. This group covers the current
timeline and own points, not the past timeline or every field of the screen.

The information option preserves all previously exposed actions. Recruitment,
rejection and patronage commands are not enabled merely by enabling this reader.
An unavailable waiting/closed read is distinct from a queried empty timeline.
The shared client, native owner reader and session routes pass 17 offline
checks. The native T40–41 chain and independent reload now verify the public
readback at each command boundary and exact persistence of its final state.
Private evidence: `evidence/host-xp1-great-people-information-api-integration.json`.
Native evidence: `evidence/host-xp1-religious-chain-save-reload-native.json`.

## Rise and Fall Great Prophet activation

`xp1_prophet_activation=True` exposes `information('prophet_activation')` and
`activate_prophet` candidates carrying the own unit ID and its current native
coordinates. This uses the official `UNITOPERATION_FOUND_RELIGION` operation;
it does not invent a Great Person identifier or choose a founding city in Python.
The adapter requires the selected unit's removal and the native owned founding
site, then republishes the player's observation. A native CanStart refusal
submits no archive. Stale identities and inconsistent effects are errors.

Activation does not choose a religion or beliefs automatically. It composes
with the optional foundation, belief and Great People groups and preserves
their earlier checkpoints and terminal behavior. The runtime/public/session
checks pass. The T41 client interval activated own Prophet 917513 on the
owned Holy Site at (43,28); GameCore consumed the unit, set founding city
65536 and earned two beliefs. The resulting founded religion and selected
beliefs survived independent Save/Reload.
Private evidence: `evidence/host-xp1-prophet-activation-api-integration.json`.
Native evidence: `evidence/host-xp1-religious-chain-save-reload-native.json`.

## Rise and Fall recruitment and patronage

With the Great People reader enabled, `xp1_great_people_actions=True` adds the
explicit `recruit_great_person` and `patronize_great_person` candidates. They
carry the native individual index and current quoted cost; patronage also
selects `YIELD_GOLD` or `YIELD_FAITH`. Every offer exposed by the native reader
is retained. This option adds commands to the existing `great_people` data,
without duplicating that information or introducing a model-specific filter.

Execution rechecks the published offer, submits and verifies the exact native
operation archive, then requires attribution of that individual to the actor,
the own class-count increment, the newly created own unit and the patronage
debit when applicable. Only action/status/reason crosses the command-response
boundary; the internal attribution receipt stays outside actor data. The
reader, commands, Prophet activation and religion choices can share a session.
The command/runtime/public/session checks pass. Native gold patronage of
individual 117 debited exactly 650 gold and created the player's Prophet;
the subsequent activation/foundation/beliefs state survived Save/Reload.
Normal recruitment of Boudica (individual 56) now costs the quoted 30 points,
changes the own balance from 37 to 7 and creates the owned General. An
independent reload preserves the result and its public activation availability.
Faith patronage still needs its positive native witness. Rejection and
activation of other classes are separate commands.
Private evidence: `evidence/host-xp1-great-people-actions-api-integration.json`.
Native evidence: `evidence/host-xp1-religious-chain-save-reload-native.json`.
Recruitment evidence: `evidence/host-xp1-great-person-recruitment-save-reload-native.json`.
This chain descends from the earlier diagnostic gold grant; it adds no grant
and is not an unassisted-history or strategic-training qualification.

## Rise and Fall Great Person rejection

`xp1_great_people_reject=True`, together with the Great People reader and
commands, adds `reject_great_person` to the explicit native choices. The
candidate carries the current individual index and exact rejection cost.
The native quote remains signed; the host does not clamp or replace it with
a strategic rule. The existing two-command schema remains unchanged when
this option is disabled. `information('great_people')` supplies the same data.

The request revalidates the reservation and quote, submits the official
rejection operation and verifies the actor's point balance and reservation
loss. GameCore handles reassignment and its notifications. A native refusal
produces no archive and returns an explicit refused result. Internal effect
receipts remain outside player observations. Waiting and closed views stay
unqueried, and the additional schema has an explicit checkpoint projection.

The installed runtime, public interface and composed session pass 33 grouped
checks. In the T41–42 native client interval, an offered Encampment project
made Boudica (individual 56) available. Explicit rejection cost 6 points,
changed the own balance from 37 to 31 and removed the actor's reservation.
The state was saved and closed normally; an independent process recovered
the exact observation, semantic choices and public information without sending
a gameplay command. This qualifies that selected stock XP1 rejection.
Private evidence: `evidence/host-xp1-great-people-rejection-save-reload-native.json`.

## Rise and Fall custom religion names

On the retained installed stock XP1 French profile,
`xp1_religion_custom_names=True` additionally requires
`xp1_religion_founding=True`. The group
`SessionClient.information('religion_custom_names')` exposes the offered custom
icons, native naming capability, localized default and placeholder, and the
actor's `own_custom_name`. A missing name and an empty name remain distinct.

Choose an offered `found_custom_religion` template through `SessionClient.act`
with `parameters={'name': text}` when renaming is enabled. The text is kept
exactly; the host neither trims nor normalizes it. The source-qualified input
path permits 1–32 Unicode scalar values, excluding NUL and all-ASCII-space
names. The official native Localization formatter supplies the uppercase
comparison used by the official screen. Without renaming, the server chooses
the offered localized default and accepts no caller override; the manual
32-character limit is not imposed on that programmatic default.

An invalid placeholder produces `religion_custom_name_invalid` before any
GameCore request. This is distinguished from a native CanStart refusal.
Successful execution must read back the exact selected religion and name from
GameCore. Older predefined choices and checkpoints retain their own schema.
The 43 installed grouped checks pass. A native client interval rejected the
official placeholder before submitting an operation, then founded custom icon
13 with the exact name `RL Économie 🧭` and selected beliefs 24 and 33.
The saved T41 state was reloaded independently with the same player observation,
semantic choices, name and beliefs, without another gameplay command. Both
processes closed normally below 512 MiB. This qualifies that stock XP1 French
case, not other locales, every string or unverified long programmatic defaults.

Private integration evidence: `evidence/host-xp1-custom-religion-api-integration.json`.
Native evidence: `evidence/host-xp1-custom-religion-save-reload-native.json`.

## Expansion Great Person activation

Use `xp1_great_person_activation=True` for Rise and Fall or
`xp2_great_person_activation=True` for the supported stock and BBG 7.5.1
Gathering Storm captures. The option adds the public
`information('great_person_activation')` group and explicit
`activate_great_person` choices. This option is independent of recruitment,
patronage and Prophet activation. The group exposes owned Great Person IDs,
individual/class indices, native charges, positions, and the native visible
and available flags. Every choice with both flags is retained.

In Gathering Storm, the activation group can share a decision catalogue with
Congress or Dedication choices. These choices retain their original parameter
validation and use the current decision ID. Congress read-only gates also
apply to the combined catalogue.

With Gathering Storm's secondary LAN commands enabled, each admitted human
seat gets its own activation catalogue. The host revalidates the selected
unit and command while that player's perspective is active, then restores
the original perspective. The saved public-view receipt records this scope
for reload comparison. This route is covered by software fixtures and
awaits a native two-human capture.

The operation uses the official UnitCommand for Great Person activation, with
an empty parameter archive. Candidate coordinates identify the offered state;
they are not invented command parameters. The request revalidates the offer
and preserves a real native refusal without submitting an archive.

A processed command is not automatically a confirmed effect. `completed`
requires the unit's disappearance, consumed charges, or a newly created Great
Work event attributed to that exact unit and command interval, with the city
coordinates checked against the receiving owned city. No strategic
benefit is required. A processed command without these confirmations returns
`submitted` with reason
`native_great_person_activation_processed_effect_unconfirmed` and no applied
action. The FIFO is drained, the current observation remains readable and the
client may choose another action; the host neither fabricates pending work
nor automatically retries. Detailed source/event receipts remain private.

The installed runtime, public interface, composed owner/client and preceding
custom-name contracts passed 47 grouped checks. A native reset identified an
extra assertion against an enum alias absent from the official table. The
corrected catalogue uses the official row hash directly, like UnitPanel;
its targeted test uses the pinned official database and rejects a wrong hash.
The Rise and Fall T42 recruitment exposed Boudica (unit 983049, one charge)
with visible=true and available=false. Exact Save/Reload preserves that state.
Later Rise and Fall commands activated Bhasa and created works that could be
moved to an empty slot or swapped with another work. Both moves were saved and
reopened independently. The native checks use specific characters and captures.
In the stock Gathering Storm turn-111 witness, the client activated Karel
Čapek, moved the resulting work from the Amphitheater to an empty Palace
slot, and saved the resulting inventory. A separate ordinary host process
reopened the save and verified the same public player state and work inventory.
The T112 continuation activated Čapek again, exchanged his two works between
occupied slots and restored their exchanged positions in another process.
BBG 7.5.1 has an installed-source check for this interface with native effect
qualification pending.
Private evidence: `evidence/host-xp1-great-person-activation-api-integration.json`.
Correction: `evidence/host-xp1-great-person-command-hash-repair.json`.
Native evidence: `evidence/host-xp1-great-person-recruitment-save-reload-native.json`.
Great Work moves: `evidence/host-xp1-great-work-empty-slot-save-reload-native.json`
and `evidence/host-xp1-great-work-occupied-slot-swap-save-reload-native.json`.
Gathering Storm integration: `evidence/host-xp2-great-person-activation-api-integration.json`.
Gathering Storm witness: `evidence/host-xp2-stock-great-writer-activation-work-move-native.json`.
Independent reopen: `evidence/host-xp2-stock-great-writer-work-move-reload-native.json`.
Occupied-slot exchange and reopen are recorded in
`evidence/host-xp2-stock-occupied-great-work-swap-save-reload-native.json`.

## Gathering Storm alert and automatic exploration

The opt-in `xp2_extra_unit_orders=True` adds `UNITOPERATION_ALERT` and
`UNITOPERATION_AUTOMATE_EXPLORE` to the existing `unit_order` family on the
admitted current stock and BBG 7.5.1 LAN captures. Select the offered candidate
with `SessionClient.act(player, decision_id, candidate_id)`, as for rest/wake.
The native UnitPanel visibility and legality checks determine each offer.
Exploration stays inside GameCore; the host supplies no route or exploration rule.

`decisions["unit_orders"]["extensions"]` explicitly identifies these additions.
The existing own-unit activity, fortification and readiness fields remain in
`unit_orders["units"]`. The comparison against a checkpoint without the
extension removes only the declared new offers and metadata; every historical
observation and choice must still match. Secondary human seats use the same
shared reader and native command transport before restoring the original view.
Delivery alone does not establish completion of these additional orders:
an unchanged own-unit state reports `submitted`.

The exact installed descriptors and captured operation definitions are retained
in `evidence/host-xp2-extra-unit-orders-source.json`. Native execution,
subsequent alert/exploration behaviour and Save/Load remain to be qualified.

## Gathering Storm rock bands

The option `xp2_rock_bands=True` enables the current stock and BBG 7.5.1
Gathering Storm LAN captures. The primary player and authorized secondary
human players share the same reader and concert command.

`SessionClient.information("rock_bands", player_id=player)` returns the
player's rock bands with their unit IDs, current coordinates, level and
album sales. The `visible` and `available` flags follow the official
UnitPanel checks for a concert on the band's current plot. Levels and
album sales retain their native signed integer values.

Select the offered `perform_rock_concert` candidate and submit it with
`SessionClient.act(player, decision_id, candidate_id)`. The host rechecks
the unit, position, turn, readiness and native legality, then verifies the
parameterless operation archive before delivery. A completed command
includes `command_result["concert"]`, with the acting player, turn, unit,
position, result ID and tourism produced. These are the fields used by
the official multiplayer result popup for the owning player.

Completion requires the corresponding native `PostTourismBomb` callback.
A delivered archive awaiting that callback has status `submitted`. The
presentation adapter checks its owned empty receivers and hooks while
retaining the callback arguments in administrative diagnostics. The
public concert result is bound to the exact requesting actor, unit and
pre-command turn in both the worker protocol and the Python client. These
checks use the prior decision observation, so a band's disappearance during
the concert does not remove the identity needed to validate its own result.

The installed binary bindings, both captured databases, Lua 5.1 calls,
Python client, complete network-response validation, secondary-seat transport
and source-qualified callback composition have software coverage. The grouped
acceptance runs 40 checks, including existing simultaneous-turn, park and
Great Person paths. Native concert execution and its
Save/Reload cycle remain to be qualified. The private source and delivery
receipts are `evidence/host-xp2-rock-bands-source-v2.json` and
`evidence/host-xp2-rock-bands-software.json`.

## Gathering Storm archaeology

With `xp2_archaeology=True` on the admitted stock or BBG 7.5.1 LAN capture,
`SessionClient.information('archaeology')` reads the active player's
Choose Artifact popup state. `pending` is null when the native popup has
no artifact. Otherwise the result identifies the owned archaeologist, the
native artifact type, the displayed era and the displayed origins in button
order. A single origin still requires confirmation in the game.

Set `xp2_archaeology_commands=True` alongside the reader to use the offered
archaeology commands through `SessionClient.act()`. The `excavate_artifact`
candidate identifies an owned archaeologist and its current tile. The host
uses the official Unit Panel's visibility and availability checks and confirms
completion when the unit has a newly pending artifact.

The `choose_artifact_origin` candidate selects an origin from the current
popup. The host checks that the same artifact is pending and verifies the native
request archive. Completion requires the pending state to clear and the engine
to produce a matching Great Work creation event for the selected archaeologist,
artifact, and receiving city. Both commands report `submitted` when a request
was delivered and the expected change is still unconfirmed. The internal
artifact index stays out of public replies.

With secondary LAN routing enabled, an authorized second human can read the
same popup and submit both commands for its own archaeologist. Each seat has
its own pending artifact identity, which is checked again before the origin
request. Secondary checkpoint comparisons preserve the archaeology scope used
when saving.

With `xp2_city_buildings=True` as well, `information("archaeology")` adds
`museum_artifacts` under archaeology schema v2. It gives the era and origin
player of each artifact in the player's own Great Work slots. Each entry
identifies its city, building, slot and Great Work index. An unavailable native
origin is `null`. The host checks the city owner and revalidates the slot
before querying the origin. This read adds no action and has software coverage.

Both routes have software coverage. Live GameCore execution, placement of the
created artifact and its persistence across Save and Load remain to be verified.

## Gathering Storm Great People information

On the admitted stock and Boston BBG 7.5.1 captures, set `xp2_great_people=True` to read
`SessionClient.information('great_people')` for the active player. The result
includes the current timeline, the player's points by class, recruitment and
rejection flags, and gold and faith patronage prices. The `read_only` field
tracks the Congress and strategic-command boundaries. At those boundaries,
prices and native flags remain visible and every `available` flag is false.

Set `xp2_great_people_actions=True` alongside the reader to expose
`recruit_great_person`, `reject_great_person` and `patronize_great_person`
when the native panel offers them. The host rechecks the offer and the
GameCore's command gate, then verifies the resulting grant or rejection.

On BBG 7.5.1, at turn 74 the native gold patronage offer for John the Baptist cost 305.
The client selected the offer, verified the exact debit and the new Prophet,
and saved the resulting state. An independent session restored the same public
observation and choices. Recruitment, rejection and faith patronage still need
positive native witnesses on this profile.

The stock route selects its own official gameplay database and the stock
Great People popup chain. The stock command route has software coverage,
including the composed secondary-seat gold patronage and checkpoint checks.

Local evidence is recorded in `evidence/host-xp2-bbg-great-people-reader-t74-native.json`.
The patronage witness is `evidence/host-xp2-bbg-prophet-gold-patronage-save-native.json`.
The stock source is `evidence/host-xp2-stock-great-people-source.json`.

## Gathering Storm pantheon and religion choices

The independent option `xp2_pantheon=True` adds
`SessionClient.information('pantheon')` with schema `civ6-host.pantheon.v2`.
It contains the actor's actual native `pantheon_index` (`-1` means none) and
the existing numerical choice catalogue. The index is read explicitly; it is
not inferred from an empty action list. Select an offered `pantheon` candidate
with `SessionClient.act()`. The XP1 v1 contract remains unchanged.

The independent session options `xp2_prophet_activation=True`,
`xp2_religion_founding=True` and `xp2_religion_beliefs=True` expose
`information('prophet_activation')`, `information('religion_founding')` and
`information('religion_beliefs')`. Select the corresponding `activate_prophet`,
`found_religion` or `add_belief` candidate with `SessionClient.act()`.
Each choice is explicit: the host does not move a Prophet, choose a religion or
select beliefs automatically. The numerical founding action selects a predefined
religion. Custom naming and other Great Person actions have separate admission.

These options select the exact current XP2 image and retained stock/BBG 7.5.1
captures. They can be enabled individually and combined with
`xp2_religious_unit_operations` and `xp2_pantheon`. The public groups contain the acting player's
religious state and the native choices for the current decision revision.
Closed decision windows retain an unavailable group rather than fabricated
choices. For an already founded religion on the admitted XP2 profile, the
reader follows ReligionScreen's city lookup when the descriptor leaves the
player's city set. The public `holy_city` descriptor then uses the ordinary
absence sentinel. If the lookup still finds a city, the actor's `own` state
also carries `holy_city_display_label`, the localized title shown by
ReligionScreen. Its numeric owner, identifier, and location stay outside this
field. The founded religion and its belief choices remain available in
either case. The software checks cover both branches. Qualification on an
actual native city loss or transfer is pending.

XP2 pantheon, named religion and belief selection follow the official UI's
direct PlayerOperation requests after their respective choice revalidation.
They do not call the generic CanStart method: a direct request receipt records
that distinction and is not proof of an effect. Completion still requires the
native archive and independent resulting state. Prophet activation remains a
UnitOperation with its native availability predicate.

The first native interval loaded T73 exactly, read the public religious groups
and moved the Prophet onto the completed Holy Site. No activation was offered.
The pre-existing state did not yet expose GetPantheon, so its specific rejection
reason is not established. Save succeeded; Close then failed in historical
dependency verification at the memory bound. The added pantheon interface and
bounded verification repair pass 32 installed, grouped checks with the private
import boundary enabled before test imports. The corrected stock T73 interval
then offered 22 pantheons and executed the selected index 0: the own index
changed from -1 to 0 and faith from 82 to 70. Save and normal Unload/Destroy
completed under 512 MiB. An independent process now reloads that checkpoint with
identical public observations, decision catalogue and all five religious groups,
then closes normally without an action or another turn. Native refusal text
identifies an invalid founding location for the Prophet. A subsequent native
inventory read identifies the Holy Site as completed but pillaged. That run
failed during another group's dependency hashing before returning a public
client frame. After correcting the dependency hash allocations, the same
checkpoint returns the pillage flag through the client and accepts the offered
repair into production. A subsequent T74 continuation observes the repaired
Holy Site, activates the Prophet, founds predefined religion 1 and confirms
beliefs 22 and 32 in the client. GameCore saves the complete checkpoint and
closes normally under 512 MiB. An independent process restores the exact
public observation, catalogue and religious groups at T74 before closing
without further gameplay commands.
Historical XP1 religion cycles retain their existing qualification.
Private native evidence: `evidence/host-xp2-religious-chain-frontier-native.json`.
Pantheon and repaired close: `evidence/host-xp2-stock-pantheon-save-native.json`.
Independent reload: `evidence/host-xp2-stock-pantheon-cycle-native.json`.
T74 repair and foundation: `evidence/host-xp2-stock-religion-t74-native-effects.json`.
Complete stock T74 Save and independent reload:
`evidence/host-xp2-stock-religion-t74-save-reload-cycle.json`.

The Boston BBG 7.5.1 session restored the post-patronage checkpoint, kept the
Holy Site clear, and selected `activate_prophet`, `found_religion`, and two
`add_belief` candidates at T76. The client confirmed the founding city,
religion, follower belief and worship belief. It also observed five followers
and 1,400 lifetime pressure for that religion through
`information('city_religion')`. The worker saved and closed normally.
Independent reload of this post-founding checkpoint remains pending.
Private native evidence: `evidence/host-xp2-bbg-religion-founding-save-t76-native.json`.

## Gathering Storm district pillage state

The exact current XP2 image selects `civ6-host.placement-inventory.v2` in
`frame['decisions']['placement_inventory']`. Every visible owned district row
adds a Boolean `pillaged`, independently of `complete`. Building rows carry
`pillaged: null`: their damage state has not been qualified by this reader.
No new action is inferred from the field. Repair must still be an actually
offered production choice, submitted through the existing client.

Historical v1 checkpoints retain every preceding field and action through an
explicit projection that removes only `pillaged`. A v2-to-v2 comparison remains
strict. XP1 and older images keep their previous reader and contract.

The current stock T73 client reads the owned Holy Site as pillaged and the
Encampment as intact. The client submits the offered `production_resume` for
the Holy Site. GameCore puts it at the head of the queue and preserves its 25
production points. The Holy Site remains pillaged in that reply. The next
turn processes the contact and city-state quest notifications and publishes
the same district with `pillaged: false` at T74. Independent reload confirms
the same inventory in the saved T74 state.
Private evidence: `evidence/host-xp2-stock-religion-t74-save-reload-cycle.json`.

## Gathering Storm own-city religion details

On the exact current XP2 image with its retained stock or BBG 7.5.1 capture,
`xp2_city_religion_details=True` adds
`SessionClient.information('city_religion')` using `civ6-host.city-religion.v2`.
The fields match the XP1 contract below: each owned city's majority, religious
followers, pressure per turn and accumulated pressure, rounded as in the
official city display. Unrounded native pressure and hidden foreign cities
remain outside this public group.

The option is independent of religious actions. It preserves their catalogue
and remains readable while the player waits, including when strategic commands
are unavailable. Closed sessions keep the existing reduced terminal catalogue.
An explicit older-checkpoint projection removes only the newly added group and
composes with the district-pillage projection. Checkpoints already carrying the
group continue to compare it exactly.

The stock client reads both owned cities at T73 with no religion. At T74
after foundation, Rome has majority index 1, three followers, zero displayed
pressure per turn and 800 accumulated pressure. The older checkpoint's
observation and choices match after the two explicit additive projections.
An independent stock v2 reload matches the city details exactly. The same
native readback on BBG remains pending.
Private evidence: `evidence/host-xp2-stock-religion-t74-save-reload-cycle.json`.

## Gathering Storm religious unit operations

`xp2_religious_unit_operations=True` adds the same player-scoped
`information('religious_unit_operations')` group and explicit `spread_religion`,
`evangelize_belief`, `launch_inquisition` and `remove_heresy` choices on the
exact retained stock and BBG 7.5.1 captures using the current XP2 image.
This option is independent of the XP1 flag and other optional action families.
Native availability owns the mask; an operation processed without a confirmed
effect is reported as submitted, not completed.

On the current stock Gathering Storm capture, the client started the Shrine at
turn 74 and bought the offered Missionary for 70 faith on turn 75. At turn 76,
the offered `spread_religion` completed with three to two charges, movement
from four to zero, and Rome's displayed accumulated pressure from 800 to 1,000.
Save and an independent exact reload preserve the player observation, choices,
charges and city religious pressure.

Private native evidence `evidence/host-xp2-stock-missionary-spread-save-reload-cycle.json`.

From the same stock T109 Apostle save, `evangelize_belief` consumed
the Apostle and raised earned beliefs from two to three. The client selected
an offered founder belief and GameCore retained it. A separate process used
`launch_inquisition` from that save, consumed the Apostle and verified the
new Inquisition flag and 70-faith Inquisitor quote. Both branches saved and
closed normally. Reload of the evangelical result and BBG execution remain
pending. Private native evidence
`evidence/host-xp2-stock-apostle-evangelization-belief-t109-save-native.json`
and `evidence/host-xp2-stock-apostle-inquisition-t109-save-native.json`.

The exact Inquisition reload led to an offered T112 purchase for 70 faith.
At T113, `remove_heresy` consumed one charge and changed the same holy
city’s accumulated pressures from 38 to 10 for the foreign religion and
from 925 to 1,075 for the actor’s religion. A fresh native process restored
the T113 observation, choices, and two remaining charges exactly and
closed normally. Private native evidence
`evidence/host-xp2-stock-inquisitor-purification-save-reload-cycle.json`.

## Rise and Fall religious unit operations

`xp1_religious_unit_operations=True` adds
`information('religious_unit_operations')` and four explicit choices:
`spread_religion`, `evangelize_belief`, `launch_inquisition`, and `remove_heresy`.
The flag is independent of the other religious and Great Person API groups.
Information includes the actor's native Inquisition flag and every owned unit's
position, movement, religion and spread charges. Operations suppressed by the
official UnitPanel movement/visibility checks are absent; availability is read
from GameCore for the visible operations. The host does not invent a negative
native result for an unqueried operation.

Actions identify the owned unit and offered position, and submit the official
operation with no parameters. The native archive ordinal is checked against
the GameInfo ordinal: both loaders read the same pinned database in row order.
This is not a rowid-minus-one rule or a hardcoded ordinal per operation.

`completed` requires the exact operation's native receipt and an independent
effect: consumed unit/charge, a newly earned belief, or the own Inquisition
flag changing, as appropriate. An accepted operation whose effect is not
confirmed remains `submitted` with an explicit reason and a usable session.
A consumed spread charge does not claim a city conversion or follower gain.
Evangelization reads its own native belief counter directly; it does not depend
on the ownership of the holy city. No gameplay rule is calculated in Python.

The stock XP1 native client has bought a Missionary for 70 faith at T42,
advanced to T43, selected the offered spread operation, and observed charges
fall from three to two with movement consumed. The result is saved and the
native context closes normally. An independent process now reloads the owned
unit, two remaining charges, economy, observation and historical choices exactly,
with the explicitly added city-details projection below. The other three
operations remain unqualified natively. A composed-session repair carries
the selected faith permission through both command preflight checks; the native
requote, city ownership and currency guards remain in place.
Private evidence: `evidence/host-xp1-missionary-spread-save-native.json`.
Reload: `evidence/host-xp1-missionary-spread-reload-city-details-native.json`.

## Rise and Fall own-city religion details

On the exact installed stock XP1 profile, `xp1_city_religion_details=True`
upgrades `information('city_religion')` to `civ6-host.city-religion.v2`.
Each owned city retains its majority and adds `religions`, with `religion_index`,
`followers`, `pressure_per_turn`, and `lifetime_pressure`. The native readers
and the shipped UI's rounding supply these values. Raw unrounded pressure,
outward pressure and conversion forecasts are not exposed by this group.

The default remains v1. The explicit checkpoint projection removes only the
new details, retaining every previous majority, observation and action choice.
Waiting players retain the same own-city information; terminal catalogues keep
their existing reduced shape. Twelve grouped source, public-client and composed
session checks pass. The independent T43 native reload reads two followers,
zero pressure per turn and 600 accumulated pressure for the owned city, through
the public client at the same decision revision. It executes no gameplay command
or additional turn and closes normally below 512 MiB. These fields were first
queried after reload; persistence of a new v2 API checkpoint is not claimed.
There is no before/after pressure comparison or city-conversion claim.
Private evidence: `evidence/host-xp1-missionary-spread-reload-city-details-native.json`.

### Attack, deploy and rebase with aircraft

Enable `xp2_air_operations=True` on the retained Gathering Storm standard or
BBG 7.5.1 LAN profile. Native highlighted destinations that pass the game's
click-time check appear as `air_operation` choices with operation
`AIR_ATTACK`, `DEPLOY` or `REBASE`, the own unit ID and destination plot.
The host rechecks the selected choice and verifies the exact native archive before
delivery. Completion requires a newly observed position at the destination
for movement or a consumed native attack for a strike. An unconfirmed effect
reports `submitted`.

An attack that would start a war returns `pending` and opens the existing
explicit war confirmation choices. Selecting the attack in that case issues
no archive. Confirmation follows the game's declaration-only popup.
Construct the local client with
`SessionClient(backend, war_source_sha256=backend.war_source_sha256)`
so it can validate the modal against the source selected during backend setup.
Other click destinations and live GameCore execution remain to be verified.

### Build a road or railroad

Enable `xp2_build_route=True` on the retained Gathering Storm standard or
BBG 7.5.1 LAN profile. A `build_route` choice identifies an own unit, its
current plot, and the route type returned by the official Unit Panel query.
The captured rules determine the prerequisites and the route type.
At execution the host checks the same offer and delivers the game's
parameterless operation. `completed` requires the tile to change to the
offered route type. This route has software coverage. Live execution and
Save/Load remain to be verified.

For an admitted secondary human seat, the same options route these choices
through the LAN perspective switch. The host reads the seat's own units,
checks that the native archive names that seat, then restores the original
perspective. Secondary checkpoint receipts record the exact enabled families.
The simultaneous routing and checkpoint comparison have software coverage.
On the current XP2 image, the secondary seat can confirm surprise war against
an AI major and select the resulting `diplomacy_response` Close candidate.
While the dialogue is open, use `player_view()` for other seats. Complete the
dialogue before submitting their commands, polling the turn, or saving.
For a registered human defender, the native sequence closes the declarer's
session automatically and the ordinary choices return after confirmation.
The human-versus-human branch awaits a native two-human test.

### Make peace with a city-state from the second seat

The retained Gathering Storm diplomacy profiles with and without BBG 7.5.1
expose the secondary human's city-state panel in `decisions["city_state_peace"]`.
It shows met city-states from that seat's official panel and whether peace is
available. When the native panel allows it, select the
`diplomacy_initiate` candidate with choice `CHOICE_MAKE_PEACE` and the
listed target. Use the usual decision and candidate IDs.

The host rechecks the current panel and verifies the sender and target before
delivering the native player operation. Completion requires the city-state
panel to report peace. The host then restores the original perspective.
Checkpoint comparison uses the panel only when the receipt includes its scope,
so older secondary checkpoint digests remain comparable.

On stock Gathering Storm, the primary seat gets the same panel in
`decisions["diplomacy_overview"]["city_state_peace"]`. The stock overview
keeps the separate offers to negotiate peace with major civilizations and
the active promises already in the previous version. The checkpoint comparison
for that previous version removes the added city-state panel and its choices.

The primary-seat command and resume were verified with the GameCore under
BBG 7.5.1. The stock paths and the secondary BBG seat have composed software
coverage and await native execution.


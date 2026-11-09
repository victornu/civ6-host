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
closes. This qualifies that city-state interval; major-player dialogue remains
separately pending native qualification. Missing receiver profiles refuse before
RequestSession. No diplomatic answer is chosen automatically. Private evidence:
`evidence/host-xp2-war-confirmation-native.json` in the local lab.

The prepared major-player response API uses a separate public modal,
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
resources. This is a client dependency check, not a Mac throughput measurement.
The reader and response route have grouped source/software validation; their
native major-war effects must still be demonstrated on the selected content.

The prepared surprise-war route also verifies the selected native factory
registry entry, constructor bytes and virtual targets before RequestSession.
Unknown names, a foreign factory or corrupt registry are refused. Its current
source/software checks read the installed PE with substituted registry memory;
they do not qualify a live major-player exchange. The 21 registration keys found
for the shared native war class are not 21 delivered API actions. The existing
local qualifier's `--world-war-target-major` requires a verified saved major
roster and a public target before starting any native worker.

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
were qualified for players 0 and 1 on Capture09. They contain no action catalogue
or privileged critic data, and do not authorize commands for an inactive player.
Refresh with `client.observe()`; see [perspective scope](backend.md#additional-human-perspectives).
Each player's controller must receive only its own view.

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

The Rise and Fall backend selects v12 when explicitly configured with
`city_focus_diagnostic=True` and `city_management_diagnostic=True`.
Gathering Storm retains those options in v14. The client exposes
`city_focus_catalogs` and `citizen_catalogs` when these options are selected. Select a
`city_focus` or `city_citizen` candidate with the usual `act()` call.
The Gathering Storm witness founded a city, cycled its production priority
through favored, disfavored and neutral, locked and unlocked one worked plot,
and closed normally. The witness starts from the original capture. Native
specialist clicks, v12 Save and reset, and Rise and Fall execution remain
pending. Historical v11 checkpoints retain their original catalogue contract.

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
Any received statement still requires a separate explicit response. Deal and
demand screen options remain visible with `supported: false`, with no executable
candidate. The overview and complete diplomacy action space remain distinct.

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
be dead. Neither truncation nor absence of a winner fabricates a defeat; an
eliminated player before a global winner is a separate, unqualified lifecycle.
No new final board is fabricated when the native reply lacks one. Other cached
human catalogues are removed rather than returned as still playable.

A global result and a local command receipt are independent. A refused or still
pending command can accompany a newly observed winner; its status is preserved
and `applied_action` remains null. Raw diagnostic facts, source metadata and any
extra private fields remain excluded from the actor view. Non-terminal public
payloads retain their existing shape. The session wire remains v1; the added
terminal result has its own versioned schema.

This client boundary is validated on terminal fixtures and by projection of the
retained native turn-142 cultural-loss facts. Twenty-six recorded LAN responses
also replayed through the client/runtime validators without changed public
payloads. These are offline checks, not a newly played LAN victory. Actual LAN
terminal-to-reset qualification remains pending. The historical native victory
and reset proofs are retained with their original profiles.

For terminal close, open the session with `checkpoint_on_close=False`.
Checkpoint-on-close at a terminal boundary remains explicitly refused; the host
does not silently skip a requested Save. An explicit `abort()` releases a
session without attempting to save it.

### Administrative LAN save and resume

The source runtime supports `checkpoint_on_close=True` on the retained Base LAN
and exact XP1/XP2 LAN captures at a quiescent, active player0 boundary. Closing invokes the existing
native Save and configuration serializer; it does not replay the game from the
beginning. The completed process must be reaped successfully before the backend
exposes its checkpoint reference. This is a control-plane operation, outside the
actor's action catalogue.

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

### Own-unit work state and native builder effects

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

The opt-in `civ6-host.network-capability-decisions.v33` adds
`decisions.diplomacy_overview` and `diplomacy_initiate` candidates. It preserves
the preceding v32 governor fields. The current scope is the explicit
`xp2-gamecore-current-092abfbb` execution image and exact recovered GS + BBG 7.5.1
bundle; launch requires `governors_diagnostic=True`,
`diplomacy_overview_diagnostic=True` and the selected war receiver source pin.
Other profiles are refused rather than silently selecting another engine.

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

Native qualification currently covers the T25 public query, matching input
observation, Save v2 and Unload/Destroy. That witness has no living already-met
major targets. Positive initial requests, major dialogue display/responses and
the live request-registry guard have software/source checks, without a native
positive witness in this delivery. The twenty compiled mappings do not mean
twenty qualified native actions. No learner changes or training occurred.

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
Expiry, reissuing an expired route, Amani's modifier and visibility across
other target and map conditions remain separate qualification cases.

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


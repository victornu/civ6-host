"""Explicit qualified-action allowlist for the host bridge.

This module is pure data plus one pure filter: no I/O, no runtime imports, no
private lab access. It restates, in one place, which decision families the
retained Gathering Storm + BBG 7.5.1 capture (``bbg751-world-A``) has actually
qualified, so a bridge layer can *mask* everything else instead of guessing.

Two structural facts motivate the allowlist:

* The wire refuses ``complete_action_space=true`` (see ``client.py``). A bridge
  may therefore never claim to enumerate the whole Civ6 action space.
* The qualified native surface is a short, receipted list (README and
  ``docs/client.md``). Anything outside it is unqualified evidence, not a
  smaller-but-equally-safe feature.

The receipt names below are private-lab artefacts (``evidence/host-*.json``);
they are recorded as documentation strings only and are never read here.
"""

UNKNOWN_KIND = 'unknown_kind'

#: Kind names this module admits without a per-family receipt claim: the wire
#: gates them through ``turn_availability`` instead (v3). ``unready_turn`` is
#: listed here because it stays unqualified on the retained capture.
TURN_KINDS = frozenset(('end_turn', 'force_end_turn', 'unready_turn'))

#: The null branch the retained capture actually exercised: all three turn
#: controls are ``None``, so forced EndTurn is the qualified turn path.
NEUTRAL_TURN_AVAILABILITY = {kind: None for kind in TURN_KINDS}

_OPENING = 'evidence/host-current-bbg751-world-a-opening.json'
_BUILDER = 'evidence/host-current-bbg751-world-a-builder.json'


def _family(contract, kinds, evidence, note=''):
    return dict(contract=contract, kinds=frozenset(kinds),
                evidence=tuple(evidence), note=note)


#: Family name -> {contract module, decision kinds, evidence receipt(s)}.
#:
#: Exactly the surface named in the README qualified list for the retained
#: GS + BBG 7.5.1 world. Family names follow that list ("builder start",
#: "farm build", "checkpoint save/resume"), the decision kinds are the wire
#: names the contract modules validate.
QUALIFIED_FAMILIES = {
    'found_city': _family(
        'civ6_host.contracts.capability_choices', ('found_city',), (_OPENING,),
        'Found a city at the offered own-unit plot.'),
    'research': _family(
        'civ6_host.contracts.capability_choices', ('research',), (_OPENING,),
        'Direct exclusive research selection only; research queues are unqualified.'),
    'civic': _family(
        'civ6_host.contracts.capability_choices', ('civic',), (_OPENING,),
        'Direct exclusive civic selection only.'),
    'builder_production': _family(
        'civ6_host.contracts.capability_choices', ('production',), (_BUILDER,),
        'Start a Builder (and a queued Slinger) from the offered production row.'),
    'farm_build': _family(
        'civ6_host.contracts.unit_work', ('build_improvement',), (_BUILDER,),
        'Offered Farm build by a charged Builder; adjacent improvements stay partial.'),
    'city_focus': _family(
        'civ6_host.contracts.capability_city_controls', ('city_focus',), (_OPENING,),
        'Change the production focus of an owned city.'),
    'city_citizen_lock': _family(
        'civ6_host.contracts.capability_city_controls', ('city_citizen',), (_OPENING,),
        'Lock one offered citizen plot of an owned city.'),
    'production_queue_edit': _family(
        'civ6_host.contracts.production_queue',
        ('queue_append', 'queue_remove', 'queue_swap'),
        ('evidence/host-xp2-production-queue.json',),
        'Append, remove and swap on the public queue; other queue edits are unqualified.'),
    'holy_site_placement': _family(
        'civ6_host.contracts.placement',
        ('production_placement', 'production_resume'),
        ('evidence/host-xp2-production-placement.json',),
        'One offered Holy Site placement and resumption; hidden targets stay partial.'),
    'unit_attack': _family(
        'civ6_host.contracts.capability_unit_attacks', ('unit_attack',),
        ('evidence/host-xp2-unit-attacks.json', 'evidence/host-xp2-ranged-unit-attack.json'),
        'Melee MOVE_TO at T5 and ranged attack at T44. Route-level exclusions '
        '(war confirmation, air, non-adjacent flag melee, coastal raid/swap) stay in '
        'the contract\'s UNQUALIFIED_UNIT_ATTACKS.'),
    'unit_order_heal': _family(
        'civ6_host.contracts.capability_unit_orders', ('unit_order',),
        ('evidence/host-xp2-unit-heal-turn.json',),
        'HEAL among the parameterless operations; other commands/operations stay partial.'),
    'swap_units': _family(
        'civ6_host.contracts.capability_world_input', ('world_plot_click',),
        ('evidence/host-bbg751-unit-swap-native.json',),
        'SWAP_UNITS at T25 through the XP2 world-click route (MOVE_TO is its '
        'always-qualified sibling). Non-MOVE_TO branches and war prompts stay '
        'unqualified per UNQUALIFIED_WORLD_CLICK.'),
    'war_confirmation': _family(
        'civ6_host.contracts.war_confirmation', ('world_war_response',),
        ('evidence/host-xp2-war-confirmation-native.json',),
        'DeclareWarPopup on the city-state Hattusa: cancel, reopen and accept.'),
    'surprise_war': _family(
        'civ6_host.contracts.diplomacy_overview', ('declare_war_minor',),
        ('evidence/host-xp2-major-war-t57-native-continuation.json',
         'evidence/host-xp2-major-war-t57-native-reload.json'),
        'Surprise war at T57 and its continuation/reload.'),
    'initial_diplomacy': _family(
        'civ6_host.contracts.diplomacy_overview', ('diplomacy_initiate',),
        ('evidence/host-xp2-initial-diplomacy-native.json',
         'evidence/host-xp2-direct-denounce-t57-native.json',
         'evidence/host-xp2-direct-diplomatic-delegation-t57-native.json'),
        'v33 initial diplomacy: delegation and denounce initiates.'),
    'world_congress_ballot': _family(
        'civ6_host.contracts.world_congress',
        ('congress_open', 'congress_confirm_ballot',
         'congress_confirm_proposals', 'congress_close'),
        ('evidence/host-xp2-congress-ballot-cycle-native.json',),
        'One recorded ballot cycle (v37-39); other Congress outcomes stay unqualified.'),
    'force_end_turn': _family(
        'civ6_host.contracts.network_turn', ('force_end_turn',),
        ('evidence/host-xp2-turn-cycle.json',
         'evidence/host-xp2-stock-holy-site-repair-t94-save-native.json'),
        'The qualified turn path when end_turn is null; normal end_turn execution is '
        'not receipted on the retained capture.'),
    'terminal_response': _family(
        'civ6_host.contracts.session_result', (), 
        ('evidence/host-xp2-stock-native-terminal-response-t116.json',),
        'Session-level terminal response at T116; it offers no decision kind.'),
    'checkpoint_save_resume': _family(
        'civ6_host.contracts.network_turn', (),
        ('evidence/host-xp2-native-checkpoint.json',),
        'Save/resume of the native Game/configuration pair; a session operation, '
        'so it adds no decision kind.'),
    'espionage_diagnostic': _family(
        'civ6_host.contracts.espionage', (),
        ('evidence/host-xp2-espionage-client.json',),
        'Diagnostic v35 query only (zero spies, empty offers). No positive spy '
        'order or completed mission is qualified, so no spy_* kind is admitted.'),
}

#: Family names documented as unqualified on the retained capture. They are not
#: in :data:`QUALIFIED_FAMILIES` and any candidate of these kinds is masked.
UNQUALIFIED_KINDS = frozenset((
    'air_operation',
    'perform_rock_concert',
    'unready_turn',
    'policy_unlock',
    'promote_unit',
    'upgrade_unit',
    'governor_assign',
    'spy_mission',
    'make_trade_route',
))

UNQUALIFIED_NOTE = (
    'This allowlist is an admission list, not an action-space enumeration: the '
    'wire structurally refuses complete_action_space=true (client.py), and the '
    'qualified surface is exactly the receipted families above. Everything else '
    'is masked, including air operations, rock concerts, unready/normal turn '
    'execution, unqualified unit-work and attack routes, spy orders, trade '
    'routes, promotions, upgrades, governors and policy changes. Masking a '
    'family removes its candidates; it never substitutes another action and '
    'never re-enables a branch the native wire declined. Receipts are private '
    'lab files and are recorded here as names only.'
)

_KIND_FAMILIES = {}
for _name, _entry in QUALIFIED_FAMILIES.items():
    for _kind in _entry['kinds']:
        _KIND_FAMILIES.setdefault(_kind, []).append(_name)
KIND_FAMILIES = {kind: tuple(names) for kind, names in _KIND_FAMILIES.items()}
del _KIND_FAMILIES, _name, _entry, _kind


def families_for_kind(kind):
    """Qualified family names claiming ``kind``; empty when it is masked."""
    return KIND_FAMILIES.get(kind, ())


def is_qualified_kind(kind):
    """True when a qualified family claims this decision kind.

    Turn kinds are gated by the wire's ``turn_availability`` rather than by a
    family claim, so ``end_turn`` is not "qualified" here even when the flag
    admits it; use :func:`turn_branch_allows` for those.
    """
    return kind in KIND_FAMILIES


def turn_branch_allows(kind, availability=None):
    """Whether the wire's ``turn_availability`` admits this turn candidate.

    ``end_turn`` follows its own flag. ``force_end_turn`` is the qualified path
    when the flag is absent: the retained capture serves ``end_turn=None``, and
    the null end_turn branch is answered by forced EndTurn
    (``docs/client.md``). ``unready_turn`` is never admitted.
    """
    if kind not in TURN_KINDS:
        raise ValueError('Not a turn kind: ' + repr(kind))
    flags = NEUTRAL_TURN_AVAILABILITY if availability is None else availability
    if kind == 'force_end_turn':
        available = flags.get('force_end_turn')
        return available is True or (
            available is None and flags.get('end_turn') is None)
    if kind == 'end_turn':
        return flags.get('end_turn') is True
    return False


def _admits(kind, availability):
    if kind in TURN_KINDS:
        return turn_branch_allows(kind, availability)
    return kind in KIND_FAMILIES


def mask_unqualified(decisions):
    """Split a decisions frame into allowed candidates and masked families.

    ``decisions`` is a portable decision frame: ``candidates`` holds
    ``{'candidate_id', 'action'}`` rows and ``turn_availability`` (v3) holds
    ``end_turn``/``force_end_turn``/``unready_turn``.

    Returns ``(allowed_candidate_ids, masked_family_names)``: the candidate IDs
    admitted in frame order, and a sorted tuple of the family names that were
    dropped. A masked name is the wire family name of the refused candidate,
    which is its ``action['kind']`` for action families (and
    :data:`UNKNOWN_KIND` for a row without one).

    The frame is read only; nothing here validates native identity, digests or
    legality, and a masked family is reported, never replaced.
    """
    if type(decisions) is not dict:
        raise ValueError('Decisions frame must be a mapping')
    rows = decisions.get('candidates')
    if rows is None:
        rows = ()
    if type(rows) not in (list, tuple):
        raise ValueError('Decisions candidates must be a list')
    availability = decisions.get('turn_availability')
    if availability is not None:
        if type(availability) is not dict:
            raise ValueError('Turn availability must be a mapping or null')
        unknown = set(availability) - TURN_KINDS
        if unknown:
            raise ValueError('Unknown turn availability field: '
                             + ', '.join(sorted(unknown)))
        if any(flag is not None and type(flag) is not bool
               for flag in availability.values()):
            raise ValueError('Turn availability must be true, false or null')
    allowed, masked, seen = [], set(), set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError('Malformed decision candidate')
        candidate_id = row.get('candidate_id')
        if type(candidate_id) is not str or not candidate_id:
            raise ValueError('Decision candidate lacks its identity')
        action = row.get('action')
        kind = action.get('kind') if type(action) is dict else None
        name = kind if type(kind) is str and kind else UNKNOWN_KIND
        if _admits(name, availability):
            if candidate_id not in seen:
                seen.add(candidate_id)
                allowed.append(candidate_id)
        else:
            masked.add(name)
    return allowed, tuple(sorted(masked))

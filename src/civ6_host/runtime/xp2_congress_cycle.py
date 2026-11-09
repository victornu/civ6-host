"""Private, non-restorable Congress chronology and ballot result observations.

No event is synthesized and no gameplay getter runs inside a callback. Exact
observed ballots may retire at a quiescent boundary, without a transport ACK.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
import json
import hashlib

from civ6_host.contracts import world_congress as contract
from .xp1_world_input import _owner
from .xp2_congress_presentation import STAGE1, STAGE2, STAGE3, FINISHED

SOURCE = ('work/trade-common-client/congress-review-staging/ack-source/congress-review-ack-source.json',
          '65ca664343d6136c1ed33dba21790b9cede9d83c97459284c8387c26c3a57b68')
MAX_EVENTS, MAX_CONFIRMATIONS = 4096, 64
PROFILE = 'xp2-congress-cycle-review-observation-v1'
_VOTING = {'regular': STAGE1, 'special': STAGE2}
_READBACK_SEAL = object()


@dataclass(frozen=True)
class _Binding:
    backend: object
    core: object
    presentation_identity: tuple
    profile: str = PROFILE


def enable(backend):
    """Explicit prepared-owner profile admission; never implied by v37."""
    from .xp2_congress_presentation import _execution
    backend.check_thread()
    _execution(backend.core)
    identity = getattr(backend, '_xp2_congress_presentation_source_identity', None)
    if (backend.stage != 'prepared' or backend.prefix is not None or backend.poisoned
            or backend.destroyed or identity is None
            or hasattr(backend, '_xp2_congress_cycle_profile')):
        raise ValueError('Congress cycle observer requires its explicit prepared presentation owner')
    source_dependencies()
    backend._xp2_congress_cycle_profile = _Binding(backend, backend.core, identity)
    return PROFILE


def enabled(backend):
    binding = getattr(backend, '_xp2_congress_cycle_profile', None)
    if binding is None:
        return False
    if (type(binding) is not _Binding or binding.backend is not backend
            or binding.core is not backend.core or binding.profile != PROFILE
            or binding.presentation_identity != getattr(backend, '_xp2_congress_presentation_source_identity', None)):
        raise ValueError('Congress cycle profile was replaced or belongs to another owner')
    return True


@lru_cache(maxsize=1)
def source_dependencies():
    from .configuration_profiles import _source
    from .a0_family_source import _path, verify_pinned_files
    p = _source(SOURCE)
    if (p['schema'] != 'civ6-host.xp2-congress-review-storage-source.static.v1'
            or p['scope']['static_only'] is not True
            or p['scope']['journal_settlement_qualified'] is not False
            or p['images']['core']['sha256'] !=
            '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'):
        raise ValueError('Congress cycle storage/order source changed')
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    pins.update({str(_path(r['path']).resolve()): r['sha256'] for r in p['parents'].values()})
    pins.update({r['path']: r['sha256'] for r in p['images'].values()})
    verify_pinned_files(pins)
    return pins


@dataclass
class _Cycle:
    occurrence: int
    entry_known: bool
    phase_events: dict = field(default_factory=dict)
    finished: int | None = None
    ambiguous: bool = False


@dataclass
class _Confirmation:
    owner: object
    legacy: dict
    action: dict
    catalogue: dict
    expected: dict | None
    cycle: _Cycle | None
    armed_at: int
    planned: tuple
    archive_identity: tuple
    partial: bool
    delivered: int = 0
    result: dict | None = None
    retirement: object = None
    empty_form: dict | None = None
    proposal: object = None
    proposal_observation: object = None


@dataclass
class _State:
    backend: object
    continuation: object
    prefix: object
    identity: object
    episode: str
    generation: str
    events: list = field(default_factory=list)
    cycles: list = field(default_factory=list)
    current: _Cycle | None = None
    last_catalogue: dict | None = None
    last_revision: int | None = None
    last_event_count: int = 0
    confirmations: list = field(default_factory=list)
    readback_permit: object = None
    observed_review: object = None
    retirements: list = field(default_factory=list)


@dataclass(frozen=True)
class _ReadbackPermit:
    seal: object
    owner: _State
    cycle: _Cycle
    revision: int
    event_count: int
    observation: dict
    catalogue: dict


@dataclass(frozen=True)
class _ObservedReview:
    seal: object
    permit: _ReadbackPermit
    payload: str
    administrative: str | None = None


@dataclass(frozen=True)
class _Retirement:
    owner: _State
    entries: tuple
    payload: str
    sha256: str


@dataclass(frozen=True)
class _ProposalBatch:
    seal: object
    owner: _State
    revision: int
    event_count: int
    action: str
    catalogue: str
    plan: str
    private: str
    selections: tuple
    before: object


@dataclass(frozen=True)
class _ProposalObservation:
    seal: object
    owner: _State
    entry: _Confirmation
    batch: _ProposalBatch
    after: object
    report: str


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _state(b, c, p, identity):
    if not enabled(b):
        raise ValueError('Congress result observer profile is not admitted')
    state = getattr(c, '_xp2_congress_cycles', None)
    if state is None:
        state = _State(b, c, p, identity, identity.episode_id, identity.game_generation)
        c._xp2_congress_cycles = state
    if (type(state) is not _State or state.backend is not b or state.continuation is not c
            or state.prefix is not p or state.identity is not identity
            or state.episode != identity.episode_id or state.generation != identity.game_generation
            or b._xp1_continuation is not c or c.owner is not b or c.prefix is not p
            or c.identity is not identity):
        raise ValueError('Congress cycle owner or generation changed; no restoration is qualified')
    return state


def _live(saved, *, active):
    return _state(*_owner(saved, active=active))


def _new_cycle(state, known):
    if len(state.cycles) >= MAX_EVENTS:
        raise RuntimeError('Congress cycle chronology bound exhausted')
    cycle = _Cycle(len(state.cycles) + 1, known)
    state.cycles.append(cycle)
    state.current = cycle
    return cycle


def record_callback(owner, fields):
    """Only called inside the real, already validated synchronous A0 borrow."""
    from .a0_foundation_events import require_borrow
    from .xp2_congress_presentation import CongressFields, validate_empty_owner
    token = require_borrow(owner)
    validate_empty_owner(owner)
    if not enabled(token.owner):
        return
    if type(fields) is not CongressFields or fields.kind != owner.active_kind:
        raise ValueError('Congress cycle callback was not decoded by the source owner')
    state = _state(token.owner, token, token.prefix, token.identity)
    if len(state.events) >= MAX_EVENTS:
        raise RuntimeError('Congress callback chronology bound exhausted')
    serial = len(state.events) + 1
    # This ordinal is host bookkeeping, never a native event or session ID.
    state.events.append((fields.kind, fields.value))
    cycle = state.current
    if fields.kind in (STAGE1, STAGE2):
        if cycle is None or cycle.finished is not None:
            prior = state.last_catalogue
            cycle = _new_cycle(state, prior is not None and prior['stage'] == 'ordinary')
        elif fields.kind == STAGE1 and STAGE2 in cycle.phase_events:
            cycle.ambiguous = True  # No inferred reset without a Finished boundary.
        cycle.phase_events[fields.kind] = serial
    elif fields.kind == FINISHED:
        if cycle is not None:
            if cycle.finished is not None:
                cycle.ambiguous = True
            else:
                cycle.finished = serial
    # Stage3 is recorded but neither starts nor completes an occurrence.


def observe_catalogue(saved, public):
    source_dependencies()
    contract.validate_catalogue(public, public['player_id'], public['turn'], public['sequence'])
    state = _live(saved, active=False)
    if (public['player_id'], public['turn']) != (
            state.continuation.observation['player_id'], state.continuation.observation['turn']):
        raise ValueError('Congress cycle catalogue has a foreign player/turn')
    if public['stage'] in _VOTING and (state.current is None or state.current.finished is not None):
        # First read in a loaded/otherwise unobserved active phase is unknown.
        _new_cycle(state, False)
    state.last_catalogue = deepcopy(public)
    state.last_revision = state.continuation.sequence
    state.last_event_count = len(state.events)
    state.readback_permit = None
    state.observed_review = None


def _target(value, player_type):
    if type(value) is not dict:
        return None
    if player_type:
        pid = value.get('player_id')
        if type(pid) is not int or not 0 <= pid <= 63 or value.get('value') != str(pid):
            return None
        return ('player', pid)
    raw = value.get('value')
    return ('value', raw) if type(raw) is str else None


def _discussion_key(row):
    target = row.get('target')
    pid = target.get('player_id') if type(target) is dict else None
    if type(row.get('type_name')) is not str or type(pid) is not int or not 0 <= pid <= 63:
        return None
    return row['type_name'], pid


def _private_form_targets(public, private):
    if private is None:
        return {}
    rows = private.get('resolution_targets') if type(private) is dict else None
    offered = {r['resolution_hash']: r for r in public['resolutions'] or []
               if r['target_type'] == 'PlayerType'}
    if type(rows) is not list or len(rows) != len(offered):
        raise ValueError('Congress private target map differs from its complete own form')
    result = {}
    for row in rows:
        if (type(row) is not dict or set(row) != {
                'resolution_hash', 'resolution_type', 'target_type', 'targets'}
                or type(row['resolution_hash']) is not int or row['resolution_hash'] not in offered
                or row['resolution_hash'] in result):
            raise ValueError('Congress private resolution target identity is absent or duplicated')
        form = offered[row['resolution_hash']]
        targets = row['targets']
        if (row['resolution_type'] != form['resolution_type'] or row['target_type'] != 'PlayerType'
                or type(targets) is not list or len(targets) != len(form['targets'])
                or any(type(pid) is not int or not -0x80000000 <= pid <= 0x7fffffff for pid in targets)
                or any(t['player_id'] is not None and t['player_id'] != pid
                       for t, pid in zip(form['targets'], targets))):
            raise ValueError('Congress private targets differ from public target order or visible identity')
        result[row['resolution_hash']] = targets
    return result


def _expected(public, action, private=None):
    if action['kind'] != 'congress_confirm_ballot':
        return None
    private_targets = _private_form_targets(public, private)
    resolutions = {r['resolution_hash']: r for r in public['resolutions'] or []}
    discussions = {r['index']: r for r in public['discussions'] or []}
    counts = Counter(_discussion_key(r) for r in public['discussions'] or [])
    resolution_counts = Counter(r['resolution_type'] for r in public['resolutions'] or [])
    expected = dict(player_id=public['player_id'], resolutions=[], discussions=[], ambiguities=[])
    for choice in action['resolutions']:
        row = resolutions[choice['resolution_hash']]
        if resolution_counts[row['resolution_type']] != 1:
            expected['ambiguities'].append('ambiguous_resolution_type')
        target = _target(row['targets'][choice['target_index']], row['target_type'] == 'PlayerType')
        if row['resolution_hash'] in private_targets:
            pid = private_targets[row['resolution_hash']][choice['target_index']]
            # This is the source's signed native target value, including its
            # explicit -1 sentinel; it is never a public player identity.
            target = ('player', pid)
        if target is None:
            expected['ambiguities'].append('hidden_or_unsupported_resolution_target')
        expected['resolutions'].append(dict(type=row['resolution_type'], target_type=row['target_type'],
            option=choice['option'], votes=choice['votes'], target=target))
    for choice in action['discussions']:
        key = _discussion_key(discussions[choice['discussion_index']])
        if key is None or counts[key] != 1:
            expected['ambiguities'].append('hidden_or_ambiguous_discussion_identity_without_sender')
        expected['discussions'].append(dict(key=key, votes=choice['votes']))
    return expected


def _proposal_boundary(state):
    b, c, p = state.backend, state.continuation, state.prefix
    if (c.publishing or p.actions.pending or p.deferred_events.pending
            or p.deferred_events._draining_empty_receivers):
        raise ValueError('Congress proposal readback requires an empty owned batch boundary')
    c.transport.require_empty_native_queue()
    b.control(empty=True)


def prepare_proposal_confirmation(saved, public, action, planned, *, private):
    """Capture own state before the first Request, while its FIFO is empty."""
    from .xp2_world_congress import _check
    from .native import native_saved_world_congress as native
    from . import xp2_congress_proposal_effect as effect
    state = _live(saved, active=True)
    record = getattr(state.continuation, '_xp2_world_congress_catalogue', None)
    _check(saved, record, active=True)
    if private is not record.private:
        raise ValueError('Congress proposal batch has a foreign private catalogue')
    if any(public[key] != record.public[key] for key in
           ('player_id', 'turn', 'sequence', 'turn_segment', 'stage')):
        raise ValueError('Congress proposal batch crossed its current catalogue scope')
    if (action['kind'] not in ('congress_confirm_proposals', 'congress_close')
            or public['stage'] != 'ordinary' or public['in_session'] is not False
            or public['presentation'] != 'available_proposals'):
        raise ValueError('Congress own-proposal effect requires the ordinary owned review')
    canonical = contract.operation_plan(public, action)
    required = list(canonical['operations'])
    if canonical['following_ui_action'] == 'ClosePopup':
        required.append(dict(kind='congress_looked_at_available', sequence=public['sequence']))
    if (planned['following_ui_action'] != canonical['following_ui_action']
            or Counter(map(_json, planned['operations'])) != Counter(map(_json, required))
            or not planned['operations']
            or planned['operations'][-1]['kind'] != 'congress_looked_at_available'):
        raise ValueError('Congress own-proposal batch differs from the complete UI plan')
    selections = []
    for operation in planned['operations']:
        if operation['kind'] == 'congress_discussion_selection':
            _, parameters = native.request_parameters(operation, private)
            target = parameters[private['enums']['PARAM_OTHER_PLAYER']]
            if target >= 0x80000000:
                target -= 0x100000000
            selections.append((target, parameters[private['enums']['PARAM_DISCUSSION_TYPE']]))
        elif operation['kind'] != 'congress_looked_at_available':
            raise ValueError('Congress ordinary batch contains another action family')
    _proposal_boundary(state)
    snapshot = effect.read(saved, type_keys=tuple(dict.fromkeys(k for _, k in selections)), active=True)
    _check(saved, record, active=True)
    _proposal_boundary(state)
    return _ProposalBatch(_READBACK_SEAL, state, state.continuation.sequence, len(state.events),
        _json(action), _json(public), _json(planned), _json(private), tuple(selections), snapshot)


def begin_confirmation(saved, public, action, planned, legacy, *, private=None, proposal=None):
    """Retain every scope before delivery; partial batches never replace history."""
    state = _live(saved, active=True)
    guard(saved, active=True)
    source_dependencies()
    if private is not None:
        from .xp2_world_congress import _check
        record = getattr(state.continuation, '_xp2_world_congress_catalogue', None)
        _check(saved, record, active=True)
        if private is not record.private:
            raise ValueError('Congress private target map is not its exact current catalogue owner')
    ordinary = action['kind'] in ('congress_confirm_proposals', 'congress_close')
    if ordinary:
        if (type(proposal) is not _ProposalBatch or proposal.seal is not _READBACK_SEAL
                or proposal.owner is not state or proposal.revision != state.continuation.sequence
                or proposal.event_count != len(state.events) or proposal.action != _json(action)
                or proposal.catalogue != _json(public) or proposal.plan != _json(planned)
                or proposal.private != _json(private)):
            raise ValueError('Congress proposal state was not captured before this exact batch')
    elif proposal is not None:
        raise ValueError('Congress ballot cannot borrow an ordinary proposal snapshot')
    canonical = (contract.empty_phase_plan(public) if action['kind'] == 'automatic_congress_empty_phase'
                 else contract.operation_plan(public, action))
    if action['kind'] == 'automatic_congress_empty_phase' and action != dict(
            kind='automatic_congress_empty_phase', sequence=public['sequence']):
        raise ValueError('Congress empty transition differs from its exact form sequence')
    required = list(canonical['operations'])
    if canonical['following_ui_action'] == 'ClosePopup':
        required.append(dict(kind='congress_looked_at_available', sequence=public['sequence']))
    key = lambda row: json.dumps(row, sort_keys=True, separators=(',', ':'))
    if (planned['following_ui_action'] != canonical['following_ui_action']
            or Counter(map(key, planned['operations'])) != Counter(map(key, required))):
        raise ValueError('Congress cycle plan differs from the complete validated form')
    if len(state.confirmations) >= MAX_CONFIRMATIONS:
        raise RuntimeError('Congress unresolved confirmation bound exhausted')
    if state.continuation._xp2_world_congress_confirmation is not legacy:
        raise ValueError('Congress cycle requires the exact current delivery journal')
    if legacy['action'] != action or type(legacy['partial_submission']) is not bool:
        raise ValueError('Congress confirmation identity differs')
    operations = tuple(row['kind'] for row in planned['operations'])
    if planned['following_ui_action'] == 'ACTION_ENDTURN':
        operations += ('end_turn',)
    archive_identity = tuple((r['operation'], r['archive_sha256']) for r in legacy['journal'])
    emitted = tuple(k for k, _ in archive_identity)
    partial = legacy['partial_submission']
    if (any(type(digest) is not str or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest) for _, digest in archive_identity)
            or any(r['delivered'] is not False for r in legacy['journal'])
            or (partial and emitted != operations[:len(emitted)])
            or (not partial and emitted != operations)):
        raise ValueError('Congress prepared archive order or delivery differs')
    cycle = state.current
    if cycle is not None and (cycle.finished is not None
            or _VOTING.get(public['stage']) not in cycle.phase_events):
        cycle = None
    scope = {key: public[key] for key in ('player_id', 'turn', 'sequence', 'turn_segment', 'stage')}
    entry = _Confirmation(state, legacy, deepcopy(action), scope,
        _expected(public, action, private), cycle, len(state.events), operations, archive_identity, partial)
    if action['kind'] == 'automatic_congress_empty_phase':
        entry.empty_form = deepcopy(public)
    entry.proposal = proposal
    state.confirmations.append(entry)
    return entry


def _check_confirmation(state, entry, *, next_delivery=False):
    if (type(entry) is not _Confirmation or entry.owner is not state
            or not any(item is entry for item in state.confirmations)
            or entry.legacy['action'] != entry.action
            or entry.legacy['partial_submission'] is not entry.partial
            or tuple((r['operation'], r['archive_sha256']) for r in entry.legacy['journal'])
               != entry.archive_identity
            or any(type(r['delivered']) is not bool
                   or r['delivered'] is not (i < entry.delivered or (next_delivery and i == entry.delivered))
                   for i, r in enumerate(entry.legacy['journal']))):
        raise ValueError('Congress retained confirmation was mutated or is foreign')


def record_delivery(saved, entry, index):
    state = _live(saved, active=True)
    _check_confirmation(state, entry, next_delivery=True)
    if (type(index) is not int or index != entry.delivered or index >= len(entry.archive_identity)
            or entry.legacy['journal'][index]['delivered'] is not True
            or any(r['delivered'] is not (i <= index) for i, r in enumerate(entry.legacy['journal']))):
        raise ValueError('Congress delivery progress is not its exact ordered journal')
    entry.delivered += 1


def finish_proposal_confirmation(saved, entry):
    """Observe the final own state after the entire issued batch, without ACKs."""
    from . import xp2_congress_proposal_effect as effect
    from .xp2_world_congress_popup import check_checkpoint as check_popup
    state = _live(saved, active=True)
    _check_confirmation(state, entry)
    batch = entry.proposal
    if (type(batch) is not _ProposalBatch or batch.owner is not state
            or batch.seal is not _READBACK_SEAL or entry.proposal_observation is not None
            or batch.revision != state.continuation.sequence
            or entry.delivered != len(entry.archive_identity)):
        raise ValueError('Congress own-proposal observation lacks its ordered delivered batch')
    _proposal_boundary(state)
    after = effect.read(saved, type_keys=tuple(dict.fromkeys(k for _, k in batch.selections)), active=True)
    report = effect.compare(saved, batch.before, after,
        selections=[dict(target=t, type_key=k) for t, k in batch.selections], looked=True, active=True)
    if (type(report.get('own_state_matches')) is not bool
            or report.get('transport_acknowledged') is not False
            or report.get('congress_completion_claimed') is not False):
        raise ValueError('Congress own-proposal reader claimed an unqualified acknowledgement')
    _proposal_boundary(state)
    if not entry.partial:
        check_popup(saved)
    proof = _ProposalObservation(_READBACK_SEAL, state, entry, batch, after, _json(report))
    saved.emit('congress_own_proposal_state_observed', action=deepcopy(entry.action),
        native_journal=deepcopy(entry.legacy['journal']), partial_submission=entry.partial,
        report=deepcopy(report))
    entry.proposal_observation = proof
    entry.result = _proposal_result(state, entry)
    return deepcopy(entry.result)


def _proposal_result(state, entry):
    _check_confirmation(state, entry)
    if entry.partial or entry.delivered != len(entry.planned):
        return _unresolved('partial_or_incomplete_archive_delivery')
    proof = entry.proposal_observation
    if (type(proof) is not _ProposalObservation or proof.seal is not _READBACK_SEAL
            or proof.owner is not state or proof.entry is not entry or proof.batch is not entry.proposal
            or proof.batch.action != _json(entry.action)):
        return _unresolved('own_proposal_state_not_observed')
    report = json.loads(proof.report)
    if report['own_state_matches'] is not True:
        return _unresolved('own_proposal_delta_or_looked_marker_not_observed')
    return dict(result_status='exact_own_proposal_batch_state_observed',
        looked_effect=report['looked_effect'], transport_acknowledged=False,
        confirmation_resolved=False, checkpoint_release_qualified=False)


def _unresolved(reason):
    return dict(result_status='unresolved', reason=reason, transport_acknowledged=False,
                confirmation_resolved=False, checkpoint_release_qualified=False)


def match_ballot(expected, review, *, administrative=None):
    """Pure matcher of a validated public review; never identifies a cycle itself."""
    if expected is None:
        return _unresolved('not_a_ballot')
    if type(review.get('player_id')) is not int or review['player_id'] != expected['player_id']:
        return _unresolved('foreign_review_player')
    if expected['ambiguities']:
        return _unresolved(expected['ambiguities'][0])
    if administrative is not None:
        # Reuse the source reader's pure envelope parser. It binds the sidecar
        # to this exact public scope and ONLY the querying player's votes.
        from .native import native_world_congress_review as reader
        envelope = reader.parse_envelope(_json(dict(public=review, private=administrative)).encode(),
            review['player_id'], review['turn'], review['sequence'])
        administrative = envelope['private']
    pid, witnesses = expected['player_id'], 0
    for selected in expected['resolutions']:
        rows = [r for r in review['resolutions'] if r['resolution_type'] == selected['type']]
        if len(rows) != 1:
            return _unresolved('missing_or_duplicate_resolution')
        row = rows[0]
        votes = [v for v in row['votes'] if v['voter']['player_id'] == pid]
        if len(votes) != 1:
            return _unresolved('missing_or_duplicate_local_resolution_vote')
        vote = votes[0]
        target = _target(vote['target'], row['target_type'] == 'PlayerType')
        if row['target_type'] == 'PlayerType' and administrative is not None:
            own_rows = [r for r in administrative['resolutions']
                        if r['resolution_type'] == selected['type']]
            if len(own_rows) != 1:
                return _unresolved('missing_or_duplicate_private_own_resolution_vote')
            own = own_rows[0]
            if own['option'] != vote['option'] or own['votes'] != vote['votes']:
                return _unresolved('private_own_vote_differs_from_public_projection')
            pid_target = own['target_player_id']
            target = ('player', pid_target)
        if (type(vote['option']) is not int or type(vote['votes']) is not int
                or row['target_type'] != selected['target_type']
                or vote['option'] != selected['option'] or vote['votes'] != selected['votes']
                or target != selected['target']):
            return _unresolved('resolution_vote_or_target_mismatch')
        witnesses += selected['option'] == 2 or selected['votes'] > 1
    for selected in expected['discussions']:
        rows = [r for r in review['discussions'] if _discussion_key(r) == selected['key']]
        if len(rows) != 1:
            return _unresolved('missing_or_ambiguous_discussion_without_sender')
        votes = [v for v in rows[0]['votes'] if v['voter']['player_id'] == pid]
        if len(votes) != 1 or type(votes[0]['votes']) is not int or votes[0]['votes'] != selected['votes']:
            return _unresolved('discussion_signed_vote_mismatch')
        witnesses += abs(selected['votes']) > 1
    # The source writes automatic A/1 into the same finalized rows read by
    # Review. Exact equality proves reached ballot state, not which request or
    # automatic fill produced it. Causality is not required for retirement.
    return dict(result_status='exact_ballot_matches', nondefault_witnesses=witnesses,
                vote_origin='submitted_or_automatic_fill_indeterminate',
                transport_acknowledged=False, confirmation_resolved=False,
                checkpoint_release_qualified=False)


def _cycle_reason(state, entry):
    _check_confirmation(state, entry)
    if entry.partial or entry.delivered != len(entry.planned):
        return 'partial_or_incomplete_archive_delivery'
    cycle = entry.cycle
    if cycle is None or not cycle.entry_known:
        return 'cycle_entry_not_observed'
    if cycle is not state.current or cycle.ambiguous:
        return 'cycle_superseded_or_ambiguous'
    if cycle.finished is None or cycle.finished <= entry.armed_at:
        return 'finished_not_observed_after_confirmation'
    return None


def _match_current(state, entry, review, administrative=None):
    reason = _cycle_reason(state, entry)
    if reason is not None:
        return _unresolved(reason)
    if (review['player_id'] != entry.catalogue['player_id']
            or review['turn'] < entry.catalogue['turn']):
        return _unresolved('foreign_or_earlier_review_observation')
    result = match_ballot(entry.expected, review, administrative=administrative)
    if result['result_status'] == 'exact_ballot_matches':
        result['result_status'] = 'exact_current_cycle_ballot_result_observed'
    return result


def _result_reports(state, entries, review, administrative=None):
    reports = [(_proposal_result(state, entry) if entry.proposal is not None else
                _match_current(state, entry, review, administrative) if review is not None
                else _unresolved('ballot_review_not_observed')) for entry in entries]
    for index, entry in enumerate(entries):
        if entry.action['kind'] != 'automatic_congress_empty_phase':
            continue
        reason = _cycle_reason(state, entry)
        if reason is not None:
            reports[index] = _unresolved(reason)
            continue
        form = entry.empty_form
        plan = contract.empty_phase_plan(form)
        if ({key: form[key] for key in entry.catalogue} != entry.catalogue
                or entry.action != dict(kind='automatic_congress_empty_phase', sequence=form['sequence'])
                or entry.planned != tuple(row['kind'] for row in plan['operations']) + ('end_turn',)
                or plan['following_ui_action'] != 'ACTION_ENDTURN'
                or not 0 < entry.cycle.phase_events.get(_VOTING[form['stage']], 0) <= entry.armed_at):
            raise ValueError('Congress empty transition lost its source form or phase chronology')
        reports[index] = dict(result_status='exact_current_cycle_empty_phase_finished_observed',
            source_empty_phase=True, transport_acknowledged=False,
            confirmation_resolved=False, checkpoint_release_qualified=False)
    return reports


def prepare_review_readback(saved):
    """Gate a later actual GetReview; never read current/private voting data.

    Root must additionally apply the official UI/public-reader admission.
    This permit describes only the pending confirmation's native chronology.
    """
    state = _live(saved, active=False)
    current = state.last_catalogue
    if current is None or state.last_revision != state.continuation.sequence:
        raise ValueError('Congress review requires its current catalogue revision and scope')
    eligible = [entry for entry in state.confirmations if entry.retirement is None
                and _cycle_reason(state, entry) is None
                and entry.expected is not None and entry.catalogue['player_id'] == current['player_id']]
    if (not eligible or current['stage'] in ('regular', 'special', 'resolving')
            or state.last_event_count < state.current.finished):
        return None
    permit = _ReadbackPermit(_READBACK_SEAL, state, state.current, state.continuation.sequence,
        len(state.events), deepcopy(state.continuation.observation), deepcopy(current))
    state.readback_permit = permit
    return permit


def observe_review(saved, review, *, permit, administrative=None):
    """Conditional integration hook; caller must obtain the actual native review.

    The reader is imported only here. Missing/unqualified reader never falls
    back to an empty review. No native query, event, or checkpoint state is made.
    """
    state = _live(saved, active=False)
    current = state.last_catalogue
    if current is None or state.last_revision != state.continuation.sequence:
        raise ValueError('Congress review requires its current catalogue revision and scope')
    if (type(permit) is not _ReadbackPermit or permit.seal is not _READBACK_SEAL
            or state.readback_permit is not permit or permit.owner is not state
            or permit.cycle is not state.current or permit.event_count != len(state.events)
            or permit.revision != state.continuation.sequence
            or permit.observation != state.continuation.observation or permit.catalogue != current):
        raise ValueError('Congress review readback permit is absent, stale or foreign')
    from .native import native_world_congress_review as reader
    if administrative is None:
        actual = reader.parse(json.dumps(review, allow_nan=False).encode(),
                              current['player_id'], current['turn'], current['sequence'])
    else:
        envelope = reader.parse_envelope(_json(dict(public=review, private=administrative)).encode(),
            current['player_id'], current['turn'], current['sequence'])
        actual, administrative = envelope['public'], envelope['private']
    if (actual['turn_segment'] != current['turn_segment']
            or (current['player_id'], current['turn']) != (
                state.continuation.observation['player_id'], state.continuation.observation['turn'])):
        raise ValueError('Congress review crossed its current observation')
    entries = [entry for entry in state.confirmations if entry.retirement is None]
    reports = _result_reports(state, entries, actual, administrative)
    for entry, report in zip(entries, reports):
        entry.result = deepcopy(report)
    state.readback_permit = None
    state.observed_review = _ObservedReview(_READBACK_SEAL, permit, _json(actual),
        None if administrative is None else _json(administrative))
    return deepcopy(reports)


def guard(saved, *, active):
    state = _live(saved, active=active)
    for entry in state.confirmations:
        _check_confirmation(state, entry)
        if entry.partial or entry.delivered != len(entry.archive_identity):
            raise ValueError('Congress partial or interrupted delivery blocks model decisions; no replay')


def _checkpoint_state(saved):
    active = saved.backend.busy
    if type(active) is not bool:
        raise ValueError('Congress checkpoint needs its exact active/ready owner')
    return _live(saved, active=active)


def _check_retirements(state):
    for entry in state.confirmations:
        _check_confirmation(state, entry)
        retirement = entry.retirement
        if retirement is not None and (type(retirement) is not _Retirement
                or retirement.owner is not state
                or not any(item is retirement for item in state.retirements)
                or not any(item is entry for item in retirement.entries)):
            raise ValueError('Congress retired confirmation lost its administrative evidence')
    for retirement in state.retirements:
        if (type(retirement) is not _Retirement or retirement.owner is not state
                or hashlib.sha256(retirement.payload.encode()).hexdigest() != retirement.sha256
                or any(entry.retirement is not retirement for entry in retirement.entries)):
            raise ValueError('Congress retirement evidence was replaced or mutated')


def retire_observed_confirmations(saved):
    """Retire fully observed ballots, retaining immutable administrative evidence.

    This permits the existing native Save qualification to run; it does not
    claim that Save/reload or any individual request ACK is already qualified.
    """
    state = _checkpoint_state(saved)
    _check_retirements(state)
    entries = tuple(e for e in state.confirmations if e.retirement is None)
    if not entries:
        return None
    from .xp2_world_congress import _check
    from .xp2_world_congress_popup import check_checkpoint as check_popup
    c, b, p = state.continuation, state.backend, state.prefix
    record = getattr(c, '_xp2_world_congress_catalogue', None)
    _check(saved, record, active=b.busy)
    current = state.last_catalogue
    if (current is None or current != record.public or state.last_revision != c.sequence
            or current['stage'] != 'ordinary' or current['in_session'] is not False
            or current['presentation'] != 'closed'):
        raise ValueError('Congress retirement requires its current ordinary closed catalogue')
    check_popup(saved)
    observed = state.observed_review
    review = None
    administrative = None
    event_count = len(state.events)
    if any(entry.action['kind'] == 'congress_confirm_ballot' for entry in entries):
        if type(observed) is not _ObservedReview or observed.seal is not _READBACK_SEAL:
            raise ValueError('Congress confirmation lacks an actual observed Review result')
        permit = observed.permit
        if (permit.owner is not state or permit.cycle is not state.current
                or permit.revision != c.sequence or permit.event_count != event_count
                or permit.observation != c.observation or permit.catalogue != current):
            raise ValueError('Congress retirement Review scope or chronology is stale')
        review = json.loads(observed.payload)
        if observed.administrative is not None:
            administrative = json.loads(observed.administrative)
    reports = _result_reports(state, entries, review, administrative)
    accepted = {'exact_current_cycle_ballot_result_observed',
                'exact_current_cycle_empty_phase_finished_observed',
                'exact_own_proposal_batch_state_observed'}
    if any(r['result_status'] not in accepted for r in reports):
        raise ValueError('Congress confirmation result is partial, ambiguous or not exactly observed')
    needs_finished = any(entry.proposal is None for entry in entries)
    if needs_finished and state.last_event_count < state.current.finished:
        raise ValueError('Congress ordinary catalogue predates its actual Finished callback')
    if c._xp2_world_congress_confirmation is not entries[-1].legacy:
        raise ValueError('Congress pending delivery journal is not the exact retiring journal')
    # Do not drain, replay, publish, poll or synthesize a request to reach this
    # boundary. The existing queues and feedback must already be quiescent.
    if (c.publishing or p.actions.pending or p.deferred_events.pending
            or p.deferred_events._draining_empty_receivers):
        raise ValueError('Congress retirement requires empty command and presentation queues')
    c.transport.require_empty_native_queue()
    control = b.control(empty=True)
    if c.trade_feedback is not None:
        c.trade_feedback.check_checkpoint()
    # These are read-only checks, but revalidate after them before committing.
    _check(saved, record, active=b.busy)
    if event_count != len(state.events):
        raise ValueError('Congress callback arrived during retirement admission')
    for entry in entries:
        _check_confirmation(state, entry)
    receipt = dict(schema='civ6-host.congress-observed-ballot-retirement.v1', profile=PROFILE,
        source_sha256=SOURCE[1], episode_id=state.episode, game_generation=state.generation,
        revision=c.sequence, player_id=current['player_id'], turn=current['turn'],
        turn_segment=current['turn_segment'],
        cycle_occurrence=state.current.occurrence if needs_finished else None,
        entry_known=True if needs_finished else None,
        finished_event=state.current.finished if needs_finished else None,
        callback_chronology=deepcopy(state.events), control=deepcopy(control),
        review_sha256=None if review is None else hashlib.sha256(observed.payload.encode()).hexdigest(),
        review=review,
        review_administrative=administrative,
        confirmations=[dict(action=deepcopy(e.action), scope=deepcopy(e.catalogue),
            expected_ballot=deepcopy(e.expected),
            empty_phase_form=deepcopy(e.empty_form),
            own_proposal_readback=(json.loads(e.proposal_observation.report)
                if e.proposal_observation is not None else None),
            archives=[dict(operation=k, archive_sha256=d, delivered=True)
                      for k,d in e.archive_identity], result=deepcopy(r))
                      for e,r in zip(entries,reports)],
        pending_confirmation_retired=True, transport_acknowledged=False,
        checkpoint_admission_eligible=True, native_save_reload_qualified=False,
        simulation_request_issued=False, replay_permitted=False)
    payload = _json(receipt)
    retirement = _Retirement(state, entries, payload, hashlib.sha256(payload.encode()).hexdigest())
    # A failed administrative write must leave the entire pending state intact.
    saved.emit('congress_observed_ballots_retired', receipt=deepcopy(receipt),
               receipt_sha256=retirement.sha256)
    state.retirements.append(retirement)
    for entry in entries:
        entry.retirement = retirement
    c._xp2_world_congress_confirmation = None
    state.observed_review = None
    return deepcopy(receipt)


def check_checkpoint(saved):
    state = _checkpoint_state(saved)
    _check_retirements(state)
    if any(entry.retirement is None for entry in state.confirmations):
        return retire_observed_confirmations(saved)
    return None

"""Congress actions under the authorized secondary LAN perspective."""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from struct import Struct

from civ6_host.contracts import world_congress, world_congress_active_effects, world_congress_review
from civ6_host.contracts.network_turn import digest

from . import xp2_congress_cycle, xp2_congress_proposal_effect, xp2_congress_review_configuration
from . import xp2_world_congress_popup, xp2_world_congress_review
from .native import native_saved_world_congress, native_world_congress_active_effects, native_world_congress_review
from .configuration_profiles import XP2_CORE_SHA256
from .xp1_session_view import _borrowed_xp2_reference
from .xp1_world_input import _owner
from .xp2_world_congress_source import request_permit, source_dependencies, verify_live

BALLOT = 'congress_confirm_ballot'
ACTIONS = world_congress.CANDIDATE_FIELDS
_HEADER = Struct('<5I')
_COUNT = Struct('<I')
_PARAMETER = Struct('<IHH10sI')
_END_TURN = Struct('<III')


@dataclass(frozen=True)
class _Form:
    cycle: object
    stage_event: int | None
    public: dict
    private: dict


@dataclass(frozen=True)
class _Popup:
    scope: tuple
    starting_favor: float


@dataclass(frozen=True)
class _Ballot:
    form: _Form
    armed_at: int
    expected: dict
    archives: tuple


@dataclass
class CheckpointRead:
    """Private comparison parameters and evidence for one borrowed read."""
    expected: dict | None = None
    ballot: dict | None = None


@dataclass(frozen=True)
class _RestoredBallot:
    checkpoint: tuple
    cycle: object
    turn: int
    turn_segment: int
    stage: str


def _ballots(continuation, player):
    return getattr(continuation, '_xp2_lan_congress_ballots', {}).get(player, ())


def _scope(public):
    return tuple(public[key] for key in ('player_id', 'turn', 'turn_segment', 'stage'))


def _popup(continuation, public):
    popups = getattr(continuation, '_xp2_lan_congress_popups', {})
    pid = public['player_id']
    entry = popups.get(pid)
    if entry is not None and entry.scope != _scope(public):
        del popups[pid]
        return None
    return entry


def _offers(continuation, public, private, cycle, stage_event):
    pid = public['player_id']
    popup = _popup(continuation, public)
    if public['stage'] == 'ordinary':
        if pid in getattr(continuation, '_xp2_lan_congress_unresolved_proposals', {}):
            return
        presentation = xp2_world_congress_popup.presentation_state(public, private,
            starting_favor=None if popup is None else popup.starting_favor)
        public['presentation'] = presentation['presentation']
        if popup is not None:
            public['favor'] = popup.starting_favor
        public['offers'].update(open=presentation['open'], close=presentation['close'],
            confirm_proposals=public['local_alive'] and public['turn_active'] and presentation['confirm_proposals'])
    elif (stage_event is not None and public['local_alive'] and public['turn_active'] and not public['paused']
            and public['in_session'] and world_congress._has_ballot_choices(public)):
        public['offers']['confirm_ballot'] = not any(
            row.form.cycle is cycle and _scope(row.form.public) == _scope(public)
            for row in _ballots(continuation, pid))


def _stage(saved, backend, continuation, prefix, identity, public):
    if not xp2_congress_cycle.enabled(backend):
        return None, None
    state = xp2_congress_cycle._state(backend, continuation, prefix, identity)
    cycle = state.current
    if cycle is None or cycle.ambiguous or cycle.finished is not None:
        return state, None
    event = cycle.phase_events.get(xp2_congress_cycle._VOTING.get(public['stage']))
    if cycle.entry_known:
        return state, event
    restored = getattr(continuation, '_xp2_lan_congress_restored', {}).get(public['player_id'])
    if (restored is not None and restored.cycle is cycle
            and restored.checkpoint == saved.inputs.checkpoint):
        if event is not None:
            return state, event
        if (public['turn'], public['turn_segment'], public['stage']) == (
                restored.turn, restored.turn_segment, restored.stage):
            return state, 0
    return state, None


def _ballot_checkpoint(public, private):
    return dict(turn=public['turn'], turn_segment=public['turn_segment'], stage=public['stage'],
                private_sha256=digest(private))


def bind_checkpoint(saved, ballots):
    """Admit previously verified, unsubmitted forms without replaying callbacks."""
    if not ballots:
        return
    reference = saved.inputs.checkpoint
    if type(reference) is not tuple or len(reference) != 2:
        raise ValueError('Secondary Congress admission requires its exact native checkpoint')
    saved._check('commands', requested='unit_commands_candidate')
    with saved._attempt():
        state = xp2_congress_cycle._live(saved, active=False)
        c = state.continuation
        cycle = state.current
        if (state.events or state.confirmations or hasattr(c, '_xp2_lan_congress_restored')
                or (cycle is not None and (cycle.entry_known or cycle.finished is not None
                                          or cycle.ambiguous or cycle.phase_events))):
            raise ValueError('Secondary Congress restore crossed native cycle chronology')
        if cycle is None:
            cycle = xp2_congress_cycle._new_cycle(state, False)
        c._xp2_lan_congress_restored = {
            pid: _RestoredBallot(reference, cycle, row['turn'], row['turn_segment'], row['stage'])
            for pid, row in ballots.items()}
        saved._finish('commands')


def mode(saved, requested=None):
    catalogue = getattr(saved, 'world_congress_diagnostic', False)
    results = getattr(saved, 'world_congress_review_diagnostic', False)
    if type(catalogue) is not bool or type(results) is not bool or (results and not catalogue):
        raise ValueError('Borrowed Congress requires the saved Congress flags')
    enabled = 'review' if results else 'catalogue' if catalogue else 'off'
    if requested is None:
        return enabled
    if requested == 'off' or requested == enabled or (requested == 'catalogue' and enabled == 'review'):
        return requested
    raise ValueError('Borrowed Congress scope exceeds the saved owner')


def _native_form(saved, observation, sequence):
    pid, turn = observation['player_id'], observation['turn']
    b, c, p, identity = _owner(saved, active=True)
    _borrowed_xp2_reference(saved, pid)
    if turn != c.observation['turn']:
        raise ValueError('Borrowed Congress differs from the current turn')
    revision = c.sequence
    image = getattr(b.core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=image)
    verify_live(saved)
    xp2_world_congress_review._empty(b, c, p)
    envelope = native_saved_world_congress.query(p, pid, turn, sequence, b)
    public = envelope['public']
    world_congress.compare_own(public, observation, sequence)
    if public['presentation'] != 'closed' or world_congress.actions(public):
        raise ValueError('Borrowed Congress cannot carry offers owned by another popup')
    xp2_world_congress_review._empty(b, c, p)
    actual = _owner(saved, active=True)
    if (c.sequence != revision or c.observation['turn'] != turn
            or any(current is not expected for current, expected in zip(actual, (b, c, p, identity)))):
        raise RuntimeError('Borrowed Congress crossed its exact owner or revision')
    return b, c, p, identity, envelope


def read(saved, observation, sequence, *, include_results, can_choose=False, checkpoint=None):
    """Read the native form and retire only this player's observed ballot results."""
    if include_results:
        xp2_world_congress_review._flags(saved)
    b, c, p, identity, envelope = _native_form(saved, observation, sequence)
    revision = c.sequence
    public = envelope['public']
    pid, turn = public['player_id'], public['turn']
    state, stage_event = _stage(saved, b, c, p, identity, public)
    event_count = len(state.events) if state is not None else None
    pending = _ballots(c, pid)
    value = {'world_congress': public}
    if include_results:
        xp2_world_congress_review.source_dependencies(
            execution_image=getattr(b.core, '_civ6_host_execution_image', None))
        eligible = tuple(row for row in pending if public['stage'] == 'ordinary'
            and state is not None and row.form.cycle is state.current and not state.current.ambiguous
            and state.current.finished is not None and state.current.finished > row.armed_at
            and turn >= row.form.public['turn'])
        options = dict(backend=b, environment=xp2_congress_review_configuration, admission=envelope)
        result = native_world_congress_review.query(p, pid, turn, sequence,
            **({'administrative': True} if eligible else {}), **options)
        review = result['public'] if result is not None and eligible else result
        effects = native_world_congress_review.query(p, pid, turn, sequence,
            projection=native_world_congress_active_effects, **options)
        review_status = 'review_ui_unavailable' if review is None else 'available'
        effects_status = 'active_effects_ui_unavailable' if effects is None else 'available'
        world_congress_review.validate_group(review, review_status, public, pid, turn, sequence)
        world_congress_active_effects.validate_group(effects, effects_status, public, pid, turn, sequence)
        value.update(world_congress_review=review, world_congress_review_status=review_status,
                     world_congress_active_effects=effects, world_congress_active_effects_status=effects_status)

    xp2_world_congress_review._empty(b, c, p)
    actual = _owner(saved, active=True)
    if (c.sequence != revision or c.observation['turn'] != turn
            or any(current is not expected for current, expected in zip(actual, (b, c, p, identity)))
            or (state is not None and len(state.events) != event_count)):
        raise RuntimeError('Borrowed Congress crossed its exact owner or revision')
    if include_results and review is not None:
        for row in eligible:
            matched = xp2_congress_cycle.match_ballot(row.expected, review, administrative=result['private'])
            if matched['result_status'] == 'exact_ballot_matches':
                saved.emit('secondary_congress_ballot_result_observed', player_id=pid, turn=turn,
                    phase_scope=_scope(row.form.public), finished_event=state.current.finished,
                    archives=row.archives, result=matched)
                pending = tuple(entry for entry in pending if entry is not row)
                c._xp2_lan_congress_ballots[pid] = pending
    _popup(c, public)
    if include_results and can_choose:
        cycle = state.current if state is not None else None
        if checkpoint is not None and checkpoint.expected is not None:
            if (state is None or state.events or state.confirmations
                    or _ballot_checkpoint(public, envelope['private']) != checkpoint.expected):
                raise ValueError('Restored secondary Congress ballot phase or native choices differ')
            stage_event = 0
        _offers(c, public, envelope['private'], cycle, stage_event)
        if checkpoint is not None:
            if public['offers']['confirm_ballot']:
                checkpoint.ballot = _ballot_checkpoint(public, envelope['private'])
            if checkpoint.expected is not None and checkpoint.ballot != checkpoint.expected:
                raise ValueError('Restored secondary Congress ballot is no longer available')
        else:
            forms = getattr(c, '_xp2_lan_congress_forms', None)
            if forms is None:
                forms = c._xp2_lan_congress_forms = {}
            forms.pop(pid, None)
            if world_congress.actions(public):
                forms[pid] = _Form(cycle, stage_event, deepcopy(public), deepcopy(envelope['private']))
    elif checkpoint is not None and checkpoint.expected is not None:
        raise ValueError('Restored secondary Congress ballot lost its acting boundary')
    return value


def verify_archive(payload, player, operation, parameters):
    """Verify the observed XP2 PlayerOperation layout and actor before delivery."""
    flags = 0x80000001 if parameters else 0
    offset = _HEADER.size + (_COUNT.size if parameters else 0)
    if (type(payload) is not bytes or len(payload) != offset + _PARAMETER.size * len(parameters)
            or _HEADER.unpack_from(payload) != (0xc45de12f, player, operation, 2, flags)
            or (parameters and _COUNT.unpack_from(payload, _HEADER.size)[0] != len(parameters))):
        raise RuntimeError('Borrowed Congress archive differs from the acting player or operation')
    decoded = {}
    for key, size, tag, flags, value in _PARAMETER.iter_unpack(payload[offset:]):
        if size != 0 or tag != 2 or flags != bytes(10) or key in decoded:
            raise RuntimeError('Borrowed Congress archive has a non-numeric or repeated parameter')
        decoded[key] = value
    if decoded != parameters:
        raise RuntimeError('Borrowed Congress archive parameters differ from the ballot')


def submit(saved, action, observation, *, published, available):
    """Execute one owned Congress gesture against its freshly verified form."""
    from .native.native_player_operation_request import request_player_operation
    from .xp2_human_perspective import verify_turn_completion_player
    from .xp2_world_congress import MAX_ARCHIVES

    refusal = dict(status='refused', reason='native_secondary_congress_form_changed', requested_action=action)
    if not available:
        return refusal
    b, c, p, identity, envelope = _native_form(saved, observation, action['sequence'])
    pid = observation['player_id']
    form = getattr(c, '_xp2_lan_congress_forms', {}).get(pid)
    current = envelope['public']
    state, stage_event = _stage(saved, b, c, p, identity, current)
    if form is None or form.public != published:
        return refusal
    cycle = state.current if state is not None else None
    ballot = action['kind'] == BALLOT
    if ballot and (stage_event is None or form.stage_event != stage_event or form.cycle is not cycle):
        return refusal
    _offers(c, current, envelope['private'], cycle, stage_event)
    if current != form.public or envelope['private'] != form.private:
        return refusal
    plan = world_congress.operation_plan(current, action)
    if plan['following_ui_action'] == 'OpenAvailableProposals':
        if not hasattr(c, '_xp2_lan_congress_popups'):
            c._xp2_lan_congress_popups = {}
        c._xp2_lan_congress_popups[pid] = _Popup(_scope(current), current['favor'])
        del c._xp2_lan_congress_forms[pid]
        return dict(status='completed', reason=None, requested_action=action)
    operations = native_saved_world_congress.ordered_plan(plan['operations'], form.private)
    if plan['following_ui_action'] == 'ClosePopup':
        operations.append(dict(kind='congress_looked_at_available', sequence=current['sequence']))
    if len(operations) + int(ballot) > MAX_ARCHIVES or (ballot
            and len(_ballots(c, pid)) >= xp2_congress_cycle.MAX_CONFIRMATIONS):
        return dict(refusal, reason='secondary_congress_batch_bound')
    expected = xp2_congress_cycle._expected(current, action, private=form.private) if ballot else None
    verify_turn_completion_player(saved, pid)
    packets = []
    selections = []
    enums = form.private['enums']
    for row in operations:
        operation, parameters = native_saved_world_congress.request_parameters(row, form.private)
        permit = request_permit(saved, row['kind'], operation, parameters, enums, borrowed_player=pid)
        packets.append((row['kind'], operation, parameters, permit))
        if row['kind'] == 'congress_discussion_selection':
            target = parameters[enums['PARAM_OTHER_PLAYER']]
            if target >= 0x80000000:
                target -= 0x100000000
            selections.append(dict(target=target, type_key=parameters[enums['PARAM_DISCUSSION_TYPE']]))
    if not ballot:
        if not packets or packets[-1][0] != 'congress_looked_at_available' or _popup(c, current) is None:
            raise ValueError('Borrowed Congress proposal batch requires its owned popup')
        type_keys = tuple(dict.fromkeys(row['type_key'] for row in selections))
        before = xp2_congress_proposal_effect.read(saved, type_keys=type_keys, borrowed_player=pid)
        xp2_world_congress_review._empty(b, c, p)
    for kind, operation, parameters, permit in packets:
        if kind == 'congress_looked_at_available':
            del c._xp2_lan_congress_popups[pid]
        earlier = tuple(p.actions.pending)
        native = request_player_operation(b.core, b.context, pid, operation, parameters,
            core_sha256=XP2_CORE_SHA256, allow_empty=not parameters, congress_permit=permit)
        if not native['request_invoked'] or tuple(p.actions.pending[:-1]) != earlier or not p.actions.pending:
            raise RuntimeError('Borrowed Congress batch was interrupted before complete delivery')
        verify_archive(p.actions.pending[-1], pid, operation, parameters)
    if ballot:
        p.actions.request_end_turn(pid, player_ids=saved.network_reference['major_player_ids'])
    archives = tuple(p.actions.pending)
    if len(archives) != len(packets) + int(ballot) or (ballot
            and archives[-1] != _END_TURN.pack(0xd7c02786, pid, 0xb6fa1284)):
        raise RuntimeError('Borrowed Congress final archive differs from its native plan')
    for payload, (_, operation, parameters, _) in zip(archives, packets):
        verify_archive(payload, pid, operation, parameters)
    kinds = [row[0] for row in packets] + (['end_turn'] if ballot else [])
    journal = tuple((kind, sha256(payload).hexdigest()) for kind, payload in zip(kinds, archives, strict=True))
    if ballot:
        if not hasattr(c, '_xp2_lan_congress_ballots'):
            c._xp2_lan_congress_ballots = {}
        c._xp2_lan_congress_ballots[pid] = (*_ballots(c, pid), _Ballot(form, len(state.events), expected, journal))
    del c._xp2_lan_congress_forms[pid]
    publications = c.publication_count
    for payload in archives:
        if not p.actions.pending or p.actions.pending[0] != payload:
            raise RuntimeError('Borrowed Congress native FIFO order changed')
        p.actions.deliver_one()
        p.deferred_events.drain_empty_receivers()
        if c.trade_feedback is not None:
            c.flush_trade_feedback()
        if p.deferred_events.pending:
            raise RuntimeError('Borrowed Congress delivery left deferred native events')
    if p.actions.pending:
        if not ballot:
            raise RuntimeError('Borrowed Congress proposal batch produced an unexpected archive')
        p.actions.deliver_completed_round_echo(pid, player_ids=saved.network_reference['major_player_ids'])
        p.deferred_events.drain_empty_receivers()
        if c.trade_feedback is not None:
            c.flush_trade_feedback()
    p.view_publisher.publish()
    xp2_world_congress_review._empty(b, c, p)
    if c.publication_count != publications + 1:
        raise RuntimeError('Borrowed Congress delivery did not publish exactly once')
    if not ballot:
        after = xp2_congress_proposal_effect.read(saved, type_keys=type_keys, borrowed_player=pid)
        result = xp2_congress_proposal_effect.compare(saved, before, after, selections=selections, borrowed_player=pid)
        xp2_world_congress_review._empty(b, c, p)
        if (type(result.get('own_state_matches')) is not bool
                or result.get('transport_acknowledged') is not False
                or result.get('congress_completion_claimed') is not False):
            raise RuntimeError('Borrowed Congress proposal readback lacks a valid own-state result')
        if not result['own_state_matches']:
            if not hasattr(c, '_xp2_lan_congress_unresolved_proposals'):
                c._xp2_lan_congress_unresolved_proposals = {}
            c._xp2_lan_congress_unresolved_proposals[pid] = journal
        saved.emit('secondary_congress_proposal_result', player_id=pid, action=deepcopy(action),
                   archives=journal, own_state_matches=result['own_state_matches'], looked_effect=result['looked_effect'])
        return dict(status='completed' if result['own_state_matches'] else 'pending',
            reason=None if result['own_state_matches'] else 'native_secondary_congress_proposal_unresolved',
            requested_action=action)
    saved.emit('secondary_congress_ballot_delivered', player_id=pid, action=deepcopy(action),
               archives=journal, native_result_observed=False)
    return dict(status='pending', reason='native_secondary_congress_result_pending', requested_action=action)


def check_checkpoint(saved):
    c = saved.continuation
    if any(getattr(c, '_xp2_lan_congress_ballots', {}).values()):
        raise ValueError('Observe the pending secondary Congress result before saving the session')
    if getattr(c, '_xp2_lan_congress_unresolved_proposals', {}):
        raise ValueError('Secondary Congress proposal effects remain unverified')
    popups = getattr(c, '_xp2_lan_congress_popups', {})
    if any(popup.scope[1] == c.observation['turn'] for popup in popups.values()):
        raise ValueError('Close the secondary Congress popup before saving the session')

"""Owned Congress readback and complete human confirmation boundaries.

All selections and aggregate costs are validated before the first request.
Native packets are not atomic; journals never claim ballot acceptance.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib

from civ6_host.contracts import world_congress as contract
from .xp1_world_input import _owner
from .xp2_world_congress_source import EMPTY, OPERATIONS, request_permit, source_dependencies, verify_live

MAX_ARCHIVES = 64


def review_source_dependencies(*, execution_image=None):
    from .xp2_congress_cycle import source_dependencies as cycle_dependencies
    from .xp2_congress_proposal_effect import source_dependencies as proposal_dependencies
    return {**source_dependencies(execution_image=execution_image), **cycle_dependencies(),
            **proposal_dependencies(execution_image=execution_image)}


@dataclass(frozen=True)
class _Catalogue:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    continuation_sequence: int
    observation: dict
    public: dict
    private: dict


def _invalidate(c):
    c._xp2_world_congress_catalogue = None
    c.explicit_world_congress = None


def _check(saved, record, *, active):
    b, c, p, identity = _owner(saved, active=active)
    if (type(record) is not _Catalogue or record.saved is not saved or record.backend is not b
            or record.continuation is not c or record.prefix is not p or record.identity is not identity
            or record.continuation_sequence != c.sequence or record.observation != c.observation
            or c._xp2_world_congress_catalogue is not record
            or c.explicit_world_congress != record.public):
        raise ValueError('Congress catalogue is stale, mutated or belongs to another owner')
    return b, c, p, identity


def _scope(public):
    return (public['player_id'], public['turn'], public['turn_segment'], public['stage'])


def _public(saved, envelope):
    from .xp2_world_congress_popup import catalogue_state, budget_limit
    c = saved.continuation
    public = deepcopy(envelope['public'])
    journal = getattr(c, '_xp2_world_congress_confirmation', None)
    locked = (journal is not None and journal['scope'] == _scope(public)
              and journal['action']['kind'] in ('congress_confirm_ballot', 'automatic_congress_empty_phase'))
    ready = public['local_alive'] and public['turn_active'] and not public['paused'] and not locked
    choices = bool(public['resolutions'] or any(not row['disabled'] and not
        (row['no_upvote'] and row['no_downvote']) for row in (public['discussions'] or [])))
    public['favor'] = budget_limit(saved, public)
    popup = catalogue_state(saved, public, envelope['private'])
    public['presentation'] = popup['presentation']
    public['offers'] = dict(open=popup['open'],
        confirm_ballot=ready and choices and public['in_session'] and public['stage'] in ('regular', 'special'),
        confirm_proposals=ready and popup['confirm_proposals'], close=popup['close'])
    contract.validate_catalogue(public, public['player_id'], public['turn'], public['sequence'])
    return public


def _admit(public, action):
    contract.validate_action(action)
    candidate = {key: action[key] for key in contract.CANDIDATE_FIELDS[action['kind']]}
    fields = contract.PARAMETER_FIELDS.get(action['kind'])
    parameters = {key: action[key] for key in fields} if fields is not None else None
    if contract.choose(public, candidate, parameters) != action:
        raise ValueError('Congress confirmation differs from its public selection domain')
    return contract.operation_plan(public, action)


def catalogue(saved, observation, *, sequence):
    from .native import native_saved_world_congress as native
    b, c, p, identity = _owner(saved, active=False)
    check_model_admission(saved)
    if observation != c.observation:
        raise ValueError('Congress query requires the current player observation')
    source_dependencies(execution_image=getattr(b.core, '_civ6_host_execution_image', None))
    verify_live(saved)
    _invalidate(c)
    before, revision = deepcopy(observation), c.sequence
    c.transport.require_empty_native_queue(); b.control(empty=True)
    envelope = native.query(p, before['player_id'], before['turn'], sequence, b)
    public = _public(saved, envelope)
    contract.compare_own(public, before, sequence)
    actual = _owner(saved, active=False)
    if (any(a is not z for a, z in zip(actual, (b, c, p, identity)))
            or c.sequence != revision or c.observation != before):
        raise ValueError('Congress query crossed its exact owner or revision')
    c.transport.require_empty_native_queue(); b.control(empty=True)
    from . import xp2_congress_cycle as cycles
    if cycles.enabled(b):
        cycles.observe_catalogue(saved, public)
    record = _Catalogue(saved, b, c, p, identity, revision, before,
                        deepcopy(public), deepcopy(envelope['private']))
    c.explicit_world_congress = deepcopy(public)
    c._xp2_world_congress_catalogue = record
    return deepcopy(public)


def apply(saved, action, before):
    return _apply(saved, action, before, automatic=False)


def advance_empty_phase(saved, before):
    """Owned SetPhase no-choices transition, never an actor action or query."""
    _, c, _, _ = _owner(saved, active=True)
    record = getattr(c, '_xp2_world_congress_catalogue', None)
    _check(saved, record, active=True)
    marker = dict(kind='automatic_congress_empty_phase', sequence=record.public['sequence'])
    return _apply(saved, marker, before, automatic=True)


def prepare_empty_phase(saved, *, sequence):
    """Pure ready-owner query for the private post-action/poll transition."""
    value = catalogue(saved, saved.continuation.observation, sequence=sequence)
    previous = getattr(saved.continuation, '_xp2_world_congress_confirmation', None)
    if previous is not None and previous['scope'] == _scope(value):
        return False
    try:
        contract.empty_phase_plan(value)
    except ValueError:
        return False
    return True


def guard_other_action(saved, action):
    """No replay after partial delivery; preserve owned review on voluntary EndTurn."""
    check_model_admission(saved)
    from civ6_host.contracts.network_turn import congress_action_read_only, CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA
    current = getattr(saved.continuation, 'explicit_world_congress', None)
    if current is not None and congress_action_read_only(
            dict(schema=CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA, world_congress=current), action['kind']):
        raise ValueError('Congress session makes this human interface read-only')
    if action['kind'] in ('end_turn', 'force_end_turn'):
        from .xp2_world_congress_popup import check_checkpoint as check_popup
        check_popup(saved)


def _apply(saved, action, before, *, automatic):
    from .native import native_saved_world_congress as native
    from .native.native_player_operation_request import request_player_operation
    from .native.native_player_observation import observe_player
    from .configuration_profiles import XP2_CORE_SHA256
    _, c, _, _ = _owner(saved, active=True)
    check_model_admission(saved)
    record = getattr(c, '_xp2_world_congress_catalogue', None)
    b, c, p, _ = _check(saved, record, active=True)
    if before != record.observation:
        raise ValueError('Congress confirmation has a foreign observation')
    if automatic:
        contract.empty_phase_plan(record.public)
    else:
        _admit(record.public, action)
    c.transport.require_empty_native_queue(); b.control(empty=True)
    envelope = native.query(p, before['player_id'], before['turn'], record.public['sequence'], b)
    _check(saved, record, active=True)
    current = _public(saved, envelope)
    if _scope(current) != _scope(record.public):
        raise ValueError('Congress turn segment changed before confirmation')

    def refused(code):
        _invalidate(c)
        return dict(status='refused', refusal_code=code,
            observation=observe_player(p.runtime, p.ui_child, before['player_id']),
            receipt=dict(action=deepcopy(action), native_archive_delivered=False,
                         native_effect_readback=False, native_journal=[]))

    try:
        planned = contract.empty_phase_plan(current) if automatic else _admit(current, action)
    except ValueError:
        return refused('native_congress_confirmation_unavailable')
    if envelope['private'] != record.private:
        raise ValueError('Congress opaque choice mapping changed before confirmation')
    from . import xp2_world_congress_popup as popup
    if planned['following_ui_action'] == 'OpenAvailableProposals':
        receipt = popup.apply_open(saved, current, envelope['private'])
        receipt.update(action=deepcopy(action), local_presentation_completed=True)
        _invalidate(c)
        return dict(status='completed', refusal_code=None, observation=deepcopy(before), receipt=receipt)
    plan = native.ordered_plan(planned['operations'], envelope['private'])
    end_turn = planned['following_ui_action'] == 'ACTION_ENDTURN'
    close_permit = None
    close_receipt = None
    if planned['following_ui_action'] == 'ClosePopup':
        close_permit = popup.prepare_close(saved, current, envelope['private'], confirmation=True)
        plan.append(dict(kind='congress_looked_at_available', sequence=current['sequence']))
    elif action['kind'] == 'congress_close':
        close_permit = popup.prepare_close(saved, current, envelope['private'])
    if len(plan) + int(end_turn) > MAX_ARCHIVES:
        return refused('congress_confirmation_exceeds_native_fifo_bound')
    # All parameter maps and source permits precede the first native call.
    packets = []
    for operation_action in plan:
        operation, parameters = native.request_parameters(operation_action, envelope['private'])
        permit = request_permit(saved, operation_action['kind'], operation, parameters,
                                envelope['private']['enums'])
        packets.append((operation_action, operation, parameters, permit))
    publications = c.publication_count
    from . import xp2_congress_cycle as cycles
    proposal = (cycles.prepare_proposal_confirmation(saved, current, action,
        dict(planned, operations=plan), private=record.private)
        if cycles.enabled(b) and action['kind'] in ('congress_confirm_proposals', 'congress_close')
        else None)
    journal = []
    interrupted = None
    for operation_action, operation, parameters, permit in packets:
        if operation_action['kind'] == 'congress_looked_at_available':
            close_receipt = popup.commit_close(saved, close_permit)
        earlier = tuple(p.actions.pending)
        result = request_player_operation(b.core, b.context, before['player_id'], operation, parameters,
            core_sha256=XP2_CORE_SHA256, allow_empty=OPERATIONS[operation_action['kind']] in EMPTY,
            congress_permit=permit)
        if tuple(p.actions.pending[:len(earlier)]) != earlier:
            raise RuntimeError('Congress request changed an earlier native archive')
        emitted = p.actions.pending[len(earlier):]
        if not result['request_invoked'] or len(emitted) != 1:
            if emitted:
                raise RuntimeError('Congress request emitted an unexpected archive count')
            interrupted = 'native_congress_request_not_queued'
            break
        journal.append(dict(operation=operation_action['kind'], archive_sha256=hashlib.sha256(emitted[0]).hexdigest(),
                            delivered=False, native_request=result))
    if interrupted is None and end_turn:
        # OnAccept's final ACTION_ENDTURN uses the existing selected transport.
        p.actions.request_end_turn(before['player_id'], player_ids=saved.network_reference['major_player_ids'])
        if len(p.actions.pending) != len(journal) + 1:
            raise RuntimeError('Congress end-turn did not enqueue exactly one final archive')
        journal.append(dict(operation='end_turn', archive_sha256=hashlib.sha256(p.actions.pending[-1]).hexdigest(),
                            delivered=False, native_request=None))
    if not journal:
        result = refused(interrupted or 'native_congress_confirmation_not_queued')
        if close_receipt is not None:
            result['receipt'].update(close_receipt)
        return result
    c._xp2_world_congress_confirmation = dict(scope=_scope(current), action=deepcopy(action),
        journal=journal, partial_submission=interrupted is not None)
    cycle_entry = (cycles.begin_confirmation(saved, current, action,
        dict(planned, operations=plan), c._xp2_world_congress_confirmation,
        private=record.private, proposal=proposal) if cycles.enabled(b) else None)
    feedback = []
    for archive_index, entry in enumerate(journal):
        if not p.actions.pending or hashlib.sha256(p.actions.pending[0]).hexdigest() != entry['archive_sha256']:
            raise RuntimeError('Congress native FIFO order changed')
        p.actions.deliver_one(); entry['delivered'] = True
        if cycle_entry is not None:
            cycles.record_delivery(saved, cycle_entry, archive_index)
        p.deferred_events.drain_empty_receivers()
        if c.trade_feedback is not None:
            feedback.append(deepcopy(c.flush_trade_feedback()))
        if p.deferred_events.pending:
            raise RuntimeError('Congress feedback left native events pending')
    # The retained bulletin witness emits this generic completion immediately
    # after its final END_TURN. The transport admits only the captured local
    # eight-byte archive in flags 1,1,0,0, before any subsequent GameUpdate.
    # It verifies the same flags and an empty FIFO after native delivery.
    if p.actions.pending:
        if interrupted is not None or not end_turn or journal[-1]['operation'] != 'end_turn':
            raise RuntimeError('Congress batch reached an unqualified native completion sequence')
        p.actions.deliver_completed_round_echo(before['player_id'],
            player_ids=saved.network_reference['major_player_ids'])
        p.deferred_events.drain_empty_receivers()
        if c.trade_feedback is not None:
            feedback.append(deepcopy(c.flush_trade_feedback()))
        if p.actions.pending or p.deferred_events.pending:
            raise RuntimeError('Congress completion echo left pending native work')
    p.view_publisher.publish()
    c.transport.require_empty_native_queue(); b.control(empty=True)
    observed = observe_player(p.runtime, p.ui_child, before['player_id'])
    if c.publication_count != publications + 1:
        raise RuntimeError('Congress confirmation did not publish exactly once')
    proposal_result = (cycles.finish_proposal_confirmation(saved, cycle_entry)
                       if proposal is not None else None)
    receipt = dict(action=deepcopy(action), native_archive_delivered=True,
        native_journal=deepcopy(journal), native_effect_readback=False,
        congress_completion_claimed=False, ballot_atomic=False,
        end_turn_request_delivered=bool(journal[-1]['operation'] == 'end_turn'),
        partial_submission=interrupted is not None, interruption=interrupted,
        gameplay_feedback=feedback, local_presentation=close_receipt)
    if proposal_result is not None:
        receipt['own_proposal_result'] = proposal_result
    saved.emit('official_explicit_congress_confirmation_delivered', receipt=deepcopy(receipt),
               observation_before=deepcopy(before), observation_after=deepcopy(observed))
    _invalidate(c)
    return dict(status='pending', refusal_code=interrupted, observation=observed, receipt=receipt)


def check_model_admission(saved):
    from .xp2_congress_cycle import enabled, guard
    if enabled(saved.backend):
        guard(saved, active=saved.backend.busy)
    journal = getattr(saved.continuation, '_xp2_world_congress_confirmation', None)
    if journal is not None and journal['partial_submission']:
        raise ValueError('Congress partial native submission blocks further model decisions; no replay is qualified')


def check_checkpoint(saved):
    from .xp2_world_congress_popup import check_checkpoint as check_popup
    check_popup(saved)
    from .xp2_congress_cycle import enabled, check_checkpoint as check_cycles
    if enabled(saved.backend):
        check_cycles(saved)
    if getattr(saved.continuation, '_xp2_world_congress_confirmation', None) is not None:
        raise ValueError('Congress confirmation journal has no qualified checkpoint restoration')


def read_only_screens(value):
    contract.validate_catalogue(value, value['player_id'], value['turn'], value['sequence'])
    return ('governors', 'government', 'great_people') if value['in_session'] else ()

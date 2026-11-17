"""Own the source-qualified completion occurrences for one native UI session.

The official popup appends while occupied and pops one newest occurrence on
close.  This state is separate from simulation and from the BBG completion
callback.  Native mission history never creates an occurrence here.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib

_LIMIT = 1024


class CompletionQueue:
    def __init__(self, continuation, *, player_id=None):
        if player_id is not None and (type(player_id) is not int or not 0 <= player_id < 64):
            raise ValueError('Invalid native completion queue player')
        self.continuation = continuation
        self.prefix = continuation.prefix
        self.identity = continuation.identity
        self.player_id = player_id
        self.current = None
        self.pending = []
        self.last_native_sequence = 0

    def _check(self):
        c = self.continuation
        if c.prefix is not self.prefix or c.identity is not self.identity:
            raise ValueError('Spy completion queue lost its native session owner')
        c.check(active=c.owner.busy)
        return c.observation['player_id'] if self.player_id is None else self.player_id

    def _display(self, occurrence):
        from .native.native_spy_completion import display_state
        player = self._check()
        options = {'event_seat': True} if self.player_id is not None else {}
        state = display_state(self.prefix, player, occurrence['mission_id'],
                              occurrence['event_sequence'], **options)
        if state not in ('shown', 'missing', 'suppressed'):
            raise ValueError('Unknown native completion display result')
        if state == 'shown':
            self.current = deepcopy(occurrence)
        self.continuation.owner.emit('xp2_spy_completion_display', player_id=player,
            occurrence=deepcopy(occurrence), state=state,
            simulation_request_issued=False)

    def receive(self, sequence, player, mission):
        local = self._check()
        if (type(sequence) is not int or not self.last_native_sequence < sequence <= 0xffffffff
                or type(player) is not int or not 0 <= player < 64
                or type(mission) is not int or not 0 <= mission <= 0x7fffffff):
            raise ValueError('Malformed or repeated native spy completion occurrence')
        self.last_native_sequence = sequence
        if player != local:
            return
        occurrence = dict(event_sequence=sequence, mission_id=mission)
        if self.current is not None:
            if len(self.pending) >= _LIMIT:
                raise RuntimeError('Native spy completion queue exceeded its bound')
            self.pending.append(occurrence)
        else:
            self._display(occurrence)

    def close(self, occurrence):
        self._check()
        if self.current is None or occurrence != self.current:
            raise ValueError('Spy completion dismissal is stale or foreign')
        self.current = None
        # Deliberately one pop, including when the selected record is missing or
        # suppressed.  Looping over old records would change the official UI.
        if self.pending:
            self._display(self.pending.pop())

    def visible(self):
        self._check()
        return deepcopy(self.current)

    def check_checkpoint(self):
        self._check()
        if self.current is not None or self.pending:
            raise ValueError('Pending spy completion UI state needs explicit dismissal before checkpoint')


def borrowed_enabled(saved, requested=None):
    feedback = getattr(saved.continuation, 'trade_feedback', None)
    enabled = bool(getattr(feedback, 'secondary_spy_completions', {}))
    if requested is None:
        return enabled
    if type(requested) is not bool or (requested and not enabled):
        raise ValueError('Borrowed spy completion requires its authenticated session queues')
    return requested


def queue(saved, *, player_id=None):
    c = saved.continuation
    feedback = getattr(c, 'trade_feedback', None)
    if player_id is None:
        value = getattr(feedback, 'spy_completions', None)
        expected = c.observation['player_id']
    else:
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, player_id)
        value = getattr(feedback, 'secondary_spy_completions', {}).get(player_id)
        expected = player_id
    if type(value) is not CompletionQueue or value.continuation is not c:
        raise ValueError('Selected session has no owned native spy completion queue')
    if value._check() != expected:
        raise ValueError('Completion queue belongs to another player')
    return value


@dataclass(frozen=True)
class _Catalogue:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    sequence: int
    observation: dict
    occurrence: object
    value: dict
    waiting: bool


def catalogue(saved, observation, *, waiting=False):
    from civ6_host.contracts import spy_completion as contract
    from .native import native_spy_completion as native
    from .xp1_world_input import _owner
    from .xp2_espionage import source_dependencies
    b, c, p, identity = _owner(saved, active=False)
    if observation != c.observation:
        raise ValueError('Completion query requires the current native observation')
    source_dependencies(execution_image=getattr(b.core, '_civ6_host_execution_image', None))
    state = queue(saved)
    occurrence, before, sequence = state.visible(), deepcopy(observation), c.sequence
    c._xp2_spy_completion_catalogue = None
    c.explicit_spy_completion = None
    if waiting and occurrence is None:
        return None
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    value = native.catalog(p, before['turn'], before['player_id'], occurrence)
    contract.compare_own(value, before)
    actual = _owner(saved, active=False)
    if (any(x is not y for x, y in zip(actual, (b, c, p, identity)))
            or state.visible() != occurrence or c.sequence != sequence or c.observation != before):
        raise ValueError('Completion query crossed its native owner or occurrence')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    if waiting and value['current'] is None:
        return None
    c._xp2_spy_completion_catalogue = _Catalogue(
        saved, b, c, p, identity, sequence, before, deepcopy(occurrence), deepcopy(value), waiting)
    c.explicit_spy_completion = deepcopy(value)
    return value


def _current(saved, action, before):
    from civ6_host.contracts import spy_completion as contract
    from .xp1_world_input import _owner
    b, c, p, identity = _owner(saved, active=True)
    r = getattr(c, '_xp2_spy_completion_catalogue', None)
    state = queue(saved)
    if (type(r) is not _Catalogue or r.saved is not saved or r.backend is not b
            or r.continuation is not c or r.prefix is not p or r.identity is not identity
            or r.sequence != c.sequence or r.observation != c.observation
            or r.observation != before or r.occurrence != state.visible()
            or r.value != c.explicit_spy_completion or action not in contract.actions(r.value)):
        raise ValueError('Spy completion choice is stale or foreign')
    return b, c, p, state, r


def apply(saved, action, before):
    _, c, _, state, record = _current(saved, action, before)
    previous = c.explicit_espionage if action['kind'] == 'spy_renew' and not record.waiting else None
    return _apply(saved, action, before, state, record.occurrence, record.value,
                  previous=previous)


def _read_borrowed(saved, observation, *, waiting=False):
    from civ6_host.contracts import spy_completion as contract
    from .native import native_spy_completion as native
    from .xp1_world_input import _owner

    pid, turn = observation['player_id'], observation['turn']
    state = queue(saved, player_id=pid)
    backend, token, prefix, _ = _owner(saved, active=True)
    occurrence = state.visible()
    if waiting and occurrence is None:
        return state, occurrence, None
    token.transport.require_empty_native_queue()
    backend.control(empty=True)
    value = native.catalog(prefix, turn, pid, occurrence)
    contract.compare_own(value, observation)
    if state.visible() != occurrence:
        raise RuntimeError('Borrowed completion query changed its event occurrence')
    token.transport.require_empty_native_queue()
    backend.control(empty=True)
    if waiting and value['current'] is None:
        return state, occurrence, None
    return state, occurrence, value


def borrowed_catalogue(saved, observation, *, waiting=False):
    return _read_borrowed(saved, observation, waiting=waiting)[2]


def apply_borrowed(saved, action, before, *, expected, available, waiting=False):
    from civ6_host.contracts import spy_completion as contract
    from .xp2_espionage import borrowed_catalogue as spy_roster

    refusal = dict(status='refused', reason='native_spy_completion_unavailable', requested_action=action)
    if not available or expected is None:
        return refusal, None
    contract.compare_own(expected, before)
    state, occurrence, current = _read_borrowed(saved, before, waiting=waiting)
    if action not in contract.actions(expected) or action not in contract.actions(current):
        return refusal, None
    previous = spy_roster(saved, before) if action['kind'] == 'spy_renew' and not waiting else None
    result = _apply(saved, action, before, state, occurrence, current, previous=previous, borrowed=True)
    status = result['status']
    if status == 'refused':
        if result['observation'] != before:
            raise RuntimeError('Refused spy renewal changed the player observation')
        return dict(refusal, reason=result['refusal_code']), None
    reason = None if status == 'completed' else 'native_spy_effect_unresolved'
    return dict(status='completed' if status == 'completed' else 'submitted',
                reason=reason, requested_action=action), result['observation']


def _apply(saved, action, before, state, occurrence, catalogue, *, previous=None, borrowed=False):
    from civ6_host.contracts import espionage as spy_contract
    from .native import native_spy_completion as native, native_saved_espionage as spies
    from .native.native_player_observation import observe_player
    from .xp1_world_input import _owner

    b, c, p, _ = _owner(saved, active=True)
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    if action['kind'] == 'spy_completion_dismiss':
        state.close(occurrence)
        if not borrowed:
            c._xp2_spy_completion_catalogue = None
            c.explicit_spy_completion = None
        receipt = dict(action=deepcopy(action), local_presentation_completed=True,
            simulation_request_issued=False, native_archive_delivered=False,
            native_effect_readback=False, mission_completion_claimed=False)
        saved.emit('official_spy_completion_dismissed', **receipt)
        return dict(status='completed', refusal_code=None, observation=deepcopy(before), receipt=receipt)

    pid, turn = before['player_id'], before['turn']
    prior_order = None
    if previous is None:
        prior_order = native.renewal_unit_state(p, action, pid, turn)
        if prior_order['operation'] is None:
            raise RuntimeError('Spy renewal lost its observed own unit')
    else:
        previous = deepcopy(previous)
        spy_contract.compare_own(previous, before)
    count = c.publication_count
    raw = p.runtime.evaluate_text(p.ui_child, native.request_source(action, catalogue),
                                  b'@xp2_spy_completion_request', capacity=1048576)
    if raw == b'refused':
        c.transport.require_empty_native_queue()
        b.control(empty=True)
        return dict(status='refused', refusal_code='native_spy_renewal_unavailable',
            observation=observe_player(p.runtime, p.ui_child, before['player_id']),
            receipt=dict(action=deepcopy(action), native_archive_delivered=False,
                         native_effect_readback=False))
    if raw != b'submitted' or len(p.actions.pending) != 1:
        raise RuntimeError('Native spy renewal did not enqueue exactly one action')
    if borrowed:
        from .xp2_espionage import verify_borrowed_archive

        verify_borrowed_archive(p.actions.pending[0], before['player_id'], action)
    archive_sha256 = hashlib.sha256(p.actions.pending[0]).hexdigest()
    # The official callback enqueues RequestOperation and then closes the
    # popup unconditionally, before eventual application of the archive.
    state.close(occurrence)
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    feedback = c.flush_trade_feedback()
    if p.deferred_events.pending:
        raise RuntimeError('Spy renewal left unconsumed native events')
    p.view_publisher.publish()
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    after = observe_player(p.runtime, p.ui_child, before['player_id'])
    if (after['player_id'], after['turn']) != (before['player_id'], before['turn']):
        raise RuntimeError('Spy renewal crossed its player or turn boundary')
    refreshed, observed_order = None, None
    if prior_order is None:
        refreshed = spies.catalog(p, after['turn'], player_id=after['player_id'])
        spy_contract.compare_own(refreshed, after)
        effect = native.read_effect(p, action, previous, refreshed)
    else:
        observed_order = native.renewal_unit_state(p, action, pid, turn)
        if (observed_order['expected_operation'] != prior_order['expected_operation']
                or (observed_order['operation'] is not None) != any(
                    row['id'] == action['unit_id'] and row['owner'] == pid for row in after['units'])):
            raise RuntimeError('Spy renewal unit state differs from its observation')
        applied = observed_order['operation'] == prior_order['expected_operation'] and observed_order != prior_order
        effect = dict(applied=applied, pending=not applied)
    if (type(effect) is not dict or set(effect) != {'applied', 'pending'}
            or any(type(v) is not bool for v in effect.values())
            or effect['applied'] == effect['pending'] or c.publication_count != count + 1):
        raise RuntimeError('Unknown native spy renewal readback')
    if not borrowed:
        c._xp2_spy_completion_catalogue = None
        c.explicit_spy_completion = None
        c._xp2_espionage_catalogue = None
        c.explicit_espionage = None
    receipt = dict(action=deepcopy(action), native_archive_sha256=archive_sha256,
        native_archive_delivered=True, native_effect_readback=effect['applied'],
        native_order_pending=effect['pending'], local_presentation_completed=True,
        mission_completion_claimed=False, automatic_choices_applied=False,
        gameplay_feedback=feedback, espionage_after=deepcopy(refreshed))
    if observed_order is not None:
        receipt.update(renewal_order_before=prior_order, renewal_order_after=observed_order)
    saved.emit('official_explicit_spy_renewal_order', receipt=deepcopy(receipt),
        observation_before=deepcopy(before), observation_after=deepcopy(after))
    return dict(status='completed' if effect['applied'] else 'pending',
                refusal_code=None, observation=after, receipt=receipt)

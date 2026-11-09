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
    def __init__(self, continuation):
        self.continuation = continuation
        self.prefix = continuation.prefix
        self.identity = continuation.identity
        self.current = None
        self.pending = []
        self.last_native_sequence = 0

    def _check(self):
        c = self.continuation
        if c.prefix is not self.prefix or c.identity is not self.identity:
            raise ValueError('Spy completion queue lost its native session owner')
        c.check(active=c.owner.busy)
        return c.observation['player_id']

    def _display(self, occurrence):
        from .native.native_spy_completion import display_state
        player = self._check()
        state = display_state(self.prefix, player, occurrence['mission_id'],
                              occurrence['event_sequence'])
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


def queue(saved):
    c = saved.continuation
    value = getattr(getattr(c, 'trade_feedback', None), 'spy_completions', None)
    if type(value) is not CompletionQueue or value.continuation is not c:
        raise ValueError('Selected session has no owned native spy completion queue')
    value._check()
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


def catalogue(saved, observation):
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
    c._xp2_spy_completion_catalogue = _Catalogue(
        saved, b, c, p, identity, sequence, before, deepcopy(occurrence), deepcopy(value))
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
    from civ6_host.contracts import espionage as spy_contract
    from .native import native_spy_completion as native, native_saved_espionage as spies
    from .native.native_player_observation import observe_player
    b, c, p, state, record = _current(saved, action, before)
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    if action['kind'] == 'spy_completion_dismiss':
        state.close(record.occurrence)
        c._xp2_spy_completion_catalogue = None
        c.explicit_spy_completion = None
        receipt = dict(action=deepcopy(action), local_presentation_completed=True,
            simulation_request_issued=False, native_archive_delivered=False,
            native_effect_readback=False, mission_completion_claimed=False)
        saved.emit('official_spy_completion_dismissed', **receipt)
        return dict(status='completed', refusal_code=None, observation=deepcopy(before), receipt=receipt)

    previous = deepcopy(c.explicit_espionage)
    spy_contract.compare_own(previous, before)
    count = c.publication_count
    raw = p.runtime.evaluate_text(p.ui_child, native.request_source(action, record.value),
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
    archive_sha256 = hashlib.sha256(p.actions.pending[0]).hexdigest()
    # The official callback enqueues RequestOperation and then closes the
    # popup unconditionally, before eventual application of the archive.
    state.close(record.occurrence)
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    feedback = c.flush_trade_feedback()
    if p.deferred_events.pending:
        raise RuntimeError('Spy renewal left unconsumed native events')
    p.view_publisher.publish()
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    after = observe_player(p.runtime, p.ui_child, before['player_id'])
    refreshed = spies.catalog(p, after['turn'], player_id=after['player_id'])
    spy_contract.compare_own(refreshed, after)
    effect = native.read_effect(p, action, previous, refreshed)
    if (type(effect) is not dict or set(effect) != {'applied', 'pending'}
            or any(type(v) is not bool for v in effect.values())
            or effect['applied'] == effect['pending'] or c.publication_count != count + 1):
        raise RuntimeError('Unknown native spy renewal readback')
    c._xp2_spy_completion_catalogue = None
    c.explicit_spy_completion = None
    c._xp2_espionage_catalogue = None
    c.explicit_espionage = None
    receipt = dict(action=deepcopy(action), native_archive_sha256=archive_sha256,
        native_archive_delivered=True, native_effect_readback=effect['applied'],
        native_order_pending=effect['pending'], local_presentation_completed=True,
        mission_completion_claimed=False, automatic_choices_applied=False,
        gameplay_feedback=feedback, espionage_after=deepcopy(refreshed))
    saved.emit('official_explicit_spy_renewal_order', receipt=deepcopy(receipt),
        observation_before=deepcopy(before), observation_after=deepcopy(after))
    return dict(status='completed' if effect['applied'] else 'pending',
                refusal_code=None, observation=after, receipt=receipt)

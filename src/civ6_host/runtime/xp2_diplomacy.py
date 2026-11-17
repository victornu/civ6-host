"""Explicit diplomacy continuation for the retained XP2 SavedLoad owner.

This is a saved-session continuation, not a LAN owner or GameCore update stage.
It reuses the native statement codec and explicit menu/response adapter while
keeping the saved owner's own command boundary and identity checks.
"""
from copy import deepcopy
from contextlib import contextmanager
import hashlib

from .configuration_profiles import XP2_CORE_SHA256


def _check(saved):
    from .xp1_saved_load_owner import SavedLoadOwner
    from .xp1_continuation import SavedContinuation
    if type(saved) is not SavedLoadOwner:
        raise TypeError('XP2 diplomacy requires the retained SavedLoadOwner')
    saved._check('commands', requested='unit_commands_candidate')
    backend, continuation = saved.backend, saved.continuation
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(continuation) is not SavedContinuation
            or continuation.owner is not backend
            or getattr(backend, '_xp1_continuation', None) is not continuation
            or backend.stage != 'xp1-continuation-ready' or backend.busy
            or backend.poisoned or backend.destroyed):
        raise RuntimeError('Diplomacy requires the exact quiescent XP2 saved continuation')
    continuation.check(active=False)
    deferred = saved.prefix.deferred_events
    ledger = getattr(deferred, 'pending_diplomacy_statements', None)
    if (type(ledger) is not list
            or getattr(deferred, 'diplomacy_statement_receiver', None) is not deferred):
        raise RuntimeError('XP2 type-132 diplomacy receiver and statement ledger are not wired')
    if (saved.prefix.actions is not continuation.transport
            or continuation.transport.backend is not backend):
        raise RuntimeError('Diplomacy lost the exact saved command transport')
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True, allow_diplomacy=True)
    return backend, continuation, deferred, ledger


def _pending(saved, backend, continuation, statement, *, player_id=None):
    from .native import native_pending_diplomacy as pending
    from .native.native_diplomacy_choices import official_source, VIEW_SHA
    from .native.native_plot_display990 import _UI, CAPABILITY_SOURCE_SHA256
    from .resource_resolution import resolve_path
    pid = continuation.observation['player_id'] if player_id is None else player_id
    official_source('DiplomacyActionView.lua', VIEW_SHA)
    capability = resolve_path(_UI / 'Scripts/GameCapabilities.lua').read_bytes()
    if hashlib.sha256(capability).hexdigest() != CAPABILITY_SOURCE_SHA256:
        raise ValueError('Official diplomacy capability source changed')
    code = (b"assert(GameInfo and GameInfo.GameCapabilities,'Capabilities absent')\n"
            b"assert(GameInfo.GameCapabilities['CAPABILITY_DIPLOMACY']~=nil,"
            b"'Diplomacy capability unavailable')\n" + pending.source(statement, pid))
    raw = saved.prefix.runtime.evaluate_text(saved.prefix.ui_child, code,
        b'@xp2_saved_pending_dialogue', capacity=2048)
    session = pending.parse(raw, statement, pid)
    if session['is_open'] is not True:
        raise RuntimeError('XP2 statement session is no longer open')
    return pending.DiplomacyChoicePending(deepcopy(statement), session)


class _SavedDialogueContext:
    def __init__(self, saved, state):
        self.saved, self.state = saved, state
        self.public_display = None
        self.public_display_source_sha256 = None

    @property
    def pending(self):
        return self.state.pending

    def validate(self, backend):
        current, continuation, deferred, ledger = _check(self.saved)
        if (current is not backend or getattr(self.saved, '_xp2_diplomacy', None) is not self
                or self.state.origin != 'xp2_saved_load'
                or self.state.steps is not None or self.state.finished or self.state.executing
                or self.state.pending is None
                or self.state.turn != continuation.observation['turn']
                or self.state.pending.session['player_id'] != continuation.observation['player_id']
                or not ledger or ledger[0] != self.state.pending.statement):
            raise RuntimeError('XP2 saved diplomacy continuation is stale or foreign')
        return self.state

    def begin_response(self, backend):
        current, continuation, _, ledger = _check(self.saved)
        if current is not backend or not ledger or ledger[0] != self.state.pending.statement:
            raise RuntimeError('Saved response lost its exact pending statement')
        self.saved._running = True
        backend.stage = 'xp1-continuation-active'
        backend.busy = True
        try:
            self.saved._check_active()
        except BaseException:
            self.saved._poison()
            raise

    def end_response(self, backend):
        saved = self.saved
        try:
            if backend is not saved.backend or backend.stage != 'xp1-continuation-active':
                raise RuntimeError('Saved response returned through another native stage')
            backend.busy = True
            saved.continuation.check(active=True)
            backend.busy = False
            backend.stage = 'xp1-continuation-ready'
            saved._running = False
            saved._check('commands', requested='unit_commands_candidate')
        except BaseException:
            saved._poison()
            raise

    def poison(self, backend):
        if backend is self.saved.backend:
            self.saved._poison()

    def resume(self, backend):
        current, continuation, deferred, ledger = _check(self.saved)
        if (current is not backend or getattr(self.saved, '_xp2_diplomacy', None) is not self
                or self.state.origin != 'xp2_saved_load' or self.state.steps is not None
                or self.state.finished or self.state.executing or self.state.pending is None
                or self.state.turn != continuation.observation['turn']
                or self.state.pending.session['player_id'] != continuation.observation['player_id']
                or self.state.pending.statement in ledger or len(ledger) > 1):
            raise RuntimeError('XP2 response did not consume exactly its retained statement')
        saved = self.saved
        from .native.native_player_observation import observe_player
        observation = observe_player(saved.prefix.runtime, saved.prefix.ui_child,
                                     self.state.pending.session['player_id'])
        if (observation.get('player_id') != self.state.pending.session['player_id']
                or observation.get('turn') != self.state.turn):
            raise RuntimeError('Diplomacy response crossed the saved actor or turn')
        ledger = saved.prefix.deferred_events.pending_diplomacy_statements
        if ledger:
            self.state.pending = _pending(saved, backend, saved.continuation, ledger[0])
        else:
            self.state.pending = None
            self.state.finished = True
            saved._xp2_diplomacy = None
            backend._xp2_saved_diplomacy = None
        saved.continuation.observation = deepcopy(observation)
        saved.continuation.explicit_diplomacy = None
        backend.explicit_diplomacy = None
        backend.control(empty=True, allow_diplomacy=bool(ledger))
        return observation


class PublicViewDialogue:
    """Keep the first seat's surprise-war dialogue intact while reading views."""

    def __init__(self, saved):
        self.saved = saved
        self.backend = saved.backend
        self.context = getattr(saved, '_xp2_diplomacy', None)
        if type(self.context) is not _SavedDialogueContext or self.context.saved is not saved:
            raise RuntimeError('XP2 public view requires the exact retained dialogue')
        self.state = self.context.validate(self.backend)
        self.pending = self.state.pending
        if (self.pending.session['statement_type'] != 'DECLARE_SURPRISE_WAR'
                or getattr(saved, '_xp2_requested_deal', None) is not None):
            raise ValueError('XP2 public views need a qualified pending-dialogue type')
        self.ledger = saved.prefix.deferred_events.pending_diplomacy_statements
        self.entry = self.ledger[0]
        self.statement = deepcopy(self.pending.statement)
        self.session = deepcopy(self.pending.session)

    def check_ledger(self):
        saved, context = self.saved, self.context
        ledger = saved.prefix.deferred_events.pending_diplomacy_statements
        if (saved.backend is not self.backend or getattr(saved, '_xp2_diplomacy', None) is not context
                or getattr(self.backend, '_xp2_saved_diplomacy', None) is not context
                or context.state is not self.state or self.state.pending is not self.pending
                or self.pending.statement != self.statement or self.pending.session != self.session
                or ledger is not self.ledger or ledger != [self.statement]
                or ledger[0] is not self.entry):
            raise RuntimeError('XP2 public perspective changed the retained dialogue')
        self.backend.control(empty=True, allow_diplomacy=True)

    def check_open(self):
        # Call from the original seat. The official Lua reader checks the
        # live actor, observer, participants, session ID and statement keys.
        self.check_ledger()
        current = _pending(self.saved, self.backend, self.saved.continuation, self.statement)
        if current.session != self.session:
            raise RuntimeError('XP2 public perspective did not restore the original dialogue')


class BorrowedWarDialogue:
    """Hold an explicit surprise-war statement for the secondary LAN actor."""

    def __init__(self, saved, session, turn):
        from .native.native_turn_continuation import TurnContinuation

        saved._check_active()
        self.saved = saved
        self.backend = saved.backend
        self.player_id = session['player_id']
        self.turn = turn
        self.ledger = saved.prefix.deferred_events.pending_diplomacy_statements
        self.entry, = self.ledger
        pending = _pending(saved, self.backend, saved.continuation, self.entry,
                           player_id=self.player_id)
        if pending.session != session or session['statement_type'] != 'DECLARE_SURPRISE_WAR':
            raise RuntimeError('Borrowed war cannot retain another native dialogue')
        self.state = TurnContinuation(None, turn, pending=pending, origin='xp2_saved_load')
        self.public_display = self.public_display_source_sha256 = None

    @property
    def pending(self):
        return self.state.pending

    def check_ledger(self):
        saved = self.saved
        if (saved.backend is not self.backend or getattr(saved, '_xp2_borrowed_war', None) is not self
                or saved.continuation.observation['turn'] != self.turn or self.state.finished
                or saved.prefix.deferred_events.pending_diplomacy_statements is not self.ledger
                or self.ledger != [self.pending.statement] or self.ledger[0] is not self.entry):
            raise RuntimeError('Borrowed war lost its retained native statement')
        saved.continuation.transport.require_empty_native_queue()
        self.backend.control(empty=True, allow_diplomacy=True)

    def check_open(self):
        self.check_ledger()
        current = _pending(self.saved, self.backend, self.saved.continuation, self.entry,
                           player_id=self.player_id)
        if current.session != self.pending.session:
            raise RuntimeError('Borrowed war lost its open native session')

    def validate(self, backend):
        self.saved._check_active()
        if backend is not self.backend:
            raise RuntimeError('Borrowed diplomacy belongs to another backend')
        self.check_ledger()
        return self.state

    begin_response = validate

    def end_response(self, backend):
        self.saved._check_active()
        if (backend is not self.backend or self.ledger
                or self.saved.prefix.deferred_events.pending_diplomacy_statements is not self.ledger):
            raise RuntimeError('Borrowed surprise-war exit produced an unexpected statement')

    def poison(self, backend):
        self.saved._poison()

    def resume(self, backend):
        self.end_response(backend)
        from .native.native_player_observation import observe_player

        prefix = self.saved.prefix
        observation = observe_player(prefix.runtime, prefix.ui_child, self.player_id)
        if (observation['player_id'], observation['turn']) != (self.player_id, self.turn):
            raise RuntimeError('Borrowed war response crossed its actor or turn')
        backend.control(empty=True)
        self.state.finished = True
        self.state.pending = None
        self.saved._xp2_borrowed_war = None
        return observation

    @contextmanager
    def _explicit_cache(self):
        backend = self.backend
        previous_observation = getattr(backend, 'explicit_observation', None)
        previous_diplomacy = getattr(backend, 'explicit_diplomacy', None)
        try:
            yield
        finally:
            backend.explicit_observation = previous_observation
            backend.explicit_diplomacy = previous_diplomacy

    def read(self, sequence, before):
        with self._explicit_cache():
            observed, choices = _read_public(self.saved, sequence, self)
        if observed != before or any(row['action']['choice'] != 'CHOICE_EXIT' for row in choices['candidates']):
            raise RuntimeError('Borrowed surprise-war menu differs from the supported native response')
        return choices, self.public_display, self.public_display_source_sha256

    def respond(self, action, before, published):
        from .native import native_diplomacy_choices

        refusal = dict(status='refused', requested_action=action, reason='native_diplomacy_response_changed')
        if published is None or action['choice'] != 'CHOICE_EXIT':
            return refusal, None
        with self._explicit_cache():
            observed, current = native_diplomacy_choices.read(self.backend, published['sequence'],
                                                              saved_context=self)
            if observed != before or action not in [row['action'] for row in current['candidates']]:
                return refusal, None
            after = native_diplomacy_choices.apply(self.backend, action, saved_context=self)
        return dict(status='completed', requested_action=action, reason=None), after


def retain(saved):
    """Retain only a delivered, open type-132 statement on the XP2 owner."""
    backend, continuation, deferred, ledger = _check(saved)
    existing = getattr(saved, '_xp2_diplomacy', None)
    if existing is not None:
        existing.validate(backend)
        return True
    if not ledger:
        return False
    if len(ledger) != 1:
        raise RuntimeError('Saved diplomacy requires one native pending statement')
    from .native.native_turn_continuation import TurnContinuation
    item = _pending(saved, backend, continuation, ledger[0])
    state = TurnContinuation(None, continuation.observation['turn'], pending=item,
        origin='xp2_saved_load', return_stage='xp1-continuation-ready')
    saved._xp2_diplomacy = _SavedDialogueContext(saved, state)
    backend._xp2_saved_diplomacy = saved._xp2_diplomacy
    saved._xp2_diplomacy.validate(backend)
    saved.emit('xp2_saved_diplomacy_retained', player_id=item.session['player_id'],
        turn=state.turn, statement_sequence=item.statement['event_sequence'],
        session=item.session, game_update_called=False, automatic_response=False,
        strategic_training_ready=False)
    if getattr(saved, '_xp2_major_peace', False):
        from .xp2_deal_draft import inspect_initial_peace
        inspect_initial_peace(saved)
    return True


def read(saved, sequence):
    backend, continuation, _, _ = _check(saved)
    context = getattr(saved, '_xp2_diplomacy', None)
    if type(context) is not _SavedDialogueContext or context.saved is not saved:
        raise RuntimeError('No retained XP2 SavedLoad diplomacy statement')
    context.validate(backend)
    context.public_display=None
    context.public_display_source_sha256=None
    if getattr(saved, '_xp2_requested_deal', None) is not None:
        from .xp2_deal_draft import read as read_draft
        return read_draft(saved, sequence)
    return _read_public(saved, sequence, context)


def _read_public(saved, sequence, context):
    backend = saved.backend
    from .xp2_diplomacy_display_source import verify_live,SOURCE
    image=getattr(backend.core,'_civ6_host_execution_image',None)
    verify_live(backend.core._handle,backend.runtime.read,execution_image=image)
    from .native.native_diplomacy_choices import read as read_choices
    observation,catalogue=read_choices(backend, sequence, saved_context=context)
    from .native.native_diplomacy_configuration import read as read_configuration
    from .native.native_diplomacy_display986 import read as read_display
    configuration=read_configuration(backend,catalogue['statement'],core_sha256=XP2_CORE_SHA256)
    display=read_display(backend,catalogue['statement'],catalogue['data'],configuration,
                         sequence,saved_context=context)
    context.validate(backend)
    context.public_display=deepcopy(display)
    context.public_display_source_sha256=SOURCE[1]
    return observation,catalogue


def respond(saved, action, before):
    backend, continuation, _, _ = _check(saved)
    context = getattr(saved, '_xp2_diplomacy', None)
    if type(context) is not _SavedDialogueContext or context.saved is not saved:
        raise RuntimeError('No retained XP2 SavedLoad diplomacy statement')
    context.validate(backend)
    if type(before) is not dict or before != continuation.observation:
        raise ValueError('Diplomacy response requires the exact current saved observation')
    if getattr(saved, '_xp2_requested_deal', None) is not None:
        from . import xp2_deal_draft as draft
        return draft.close(saved, action) if action['choice'] == 'CHOICE_EXIT' else draft.apply_gold(saved, action)
    from .native.native_diplomacy_choices import apply
    after = apply(backend, action, saved_context=context)
    saved.emit('xp2_saved_diplomacy_response_observed', action=deepcopy(action),
        observation=deepcopy(after), native_success=True, native_command_delivered=True,
        game_update_called=False, automatic_response=False, strategic_training_ready=False)
    return dict(status='completed', reason=None, requested_action=deepcopy(action),
        observation=deepcopy(after), pending_statement_retained=context.pending is not None,
        game_update_called=False, automatic_response=False)

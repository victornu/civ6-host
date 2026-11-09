"""Explicit diplomacy continuation for the retained XP2 SavedLoad owner.

This is a saved-session continuation, not a LAN owner or GameCore update stage.
It reuses the native statement codec and explicit menu/response adapter while
keeping the saved owner's own command boundary and identity checks.
"""
from copy import deepcopy
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


def _pending(saved, backend, continuation, statement):
    from .native import native_pending_diplomacy as pending
    from .native.native_diplomacy_choices import official_source, VIEW_SHA
    from .native.native_plot_display990 import _UI, CAPABILITY_SOURCE_SHA256
    from .resource_resolution import resolve_path
    pid = continuation.observation['player_id']
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
    return True


def read(saved, sequence):
    backend, continuation, _, _ = _check(saved)
    context = getattr(saved, '_xp2_diplomacy', None)
    if type(context) is not _SavedDialogueContext or context.saved is not saved:
        raise RuntimeError('No retained XP2 SavedLoad diplomacy statement')
    context.validate(backend)
    context.public_display=None
    context.public_display_source_sha256=None
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
    from .native.native_diplomacy_choices import apply
    after = apply(backend, action, saved_context=context)
    saved.emit('xp2_saved_diplomacy_response_observed', action=deepcopy(action),
        observation=deepcopy(after), native_success=True, native_command_delivered=True,
        game_update_called=False, automatic_response=False, strategic_training_ready=False)
    return dict(status='completed', reason=None, requested_action=deepcopy(action),
        observation=deepcopy(after), pending_statement_retained=context.pending is not None,
        game_update_called=False, automatic_response=False)

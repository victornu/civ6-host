"""Retain native LAN statements for the existing explicit diplomacy adapter.

This suspends the client's update pump, never the DLL inside a callback. No
response, readiness flag, turn completion or network acknowledgement is invented.
Only the captured local human and the existing default-handler choices are used.
"""
from __future__ import annotations

import copy
import hashlib


def _boundary(owner):
    from .capture_profiles import LAN_PROFILE
    from .network_owner import STAGE, require_actor
    owner.check_thread()
    if (owner.inputs.profile is not LAN_PROFILE or owner.stage != STAGE
            or owner.busy or owner.poisoned or owner.destroyed):
        raise RuntimeError('LAN dialogue requires a quiescent admitted owner')
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('LAN dialogue native identity changed')
    ref = owner.network_reference
    pid = ref['state']['player_id']
    state = require_actor(owner, pid, ref['major_player_ids'], require_active=False)
    owner.control(empty=True, allow_diplomacy=True)
    return pid, state


def _pending(owner, statement, player_id):
    from .native import native_pending_diplomacy as pending
    from .native.native_diplomacy_choices import official_source, VIEW_SHA
    from .native.native_plot_display990 import _UI, CAPABILITY_SOURCE_SHA256
    from .resource_resolution import resolve_path
    # OnDiplomacyStatement is a common UI path, gated by local participation
    # and CAPABILITY_DIPLOMACY, not by IsTurnActive. Read that capability from
    # this loaded game's database; an absent table is not an enabled default.
    official_source('DiplomacyActionView.lua', VIEW_SHA)
    capability = resolve_path(_UI / 'Scripts/GameCapabilities.lua').read_bytes()
    if hashlib.sha256(capability).hexdigest() != CAPABILITY_SOURCE_SHA256:
        raise ValueError('Official capability source changed')
    code = (b"assert(GameInfo and GameInfo.GameCapabilities,'Capabilities absent')\n"
            b"assert(GameInfo.GameCapabilities['CAPABILITY_DIPLOMACY']~=nil,"
            b"'Diplomacy capability unavailable')\n" + pending.source(statement, player_id))
    p = owner.prefix
    raw = p.runtime.evaluate_text(p.ui_child, code, b'@lan_pending_dialogue', capacity=2048)
    session = pending.parse(raw, statement, player_id)
    if not session['is_open']:
        raise RuntimeError('LAN statement session is no longer open')
    return pending.DiplomacyChoicePending(copy.deepcopy(statement), session)


def validate(owner):
    from .native.native_turn_continuation import TurnContinuation
    from .network_owner import STAGE
    pid, state = _boundary(owner)
    c = getattr(owner, 'turn_continuation', None)
    if (type(c) is not TurnContinuation or c.origin != 'network'
            or c.steps is not None or c.return_stage != STAGE
            or c.executing or c.finished or c.pending is None
            or c.pending.session['player_id'] != pid
            or state['turn'] != c.turn):
        raise RuntimeError('No retained local LAN dialogue')
    ledger = owner.prefix.deferred_events.pending_diplomacy_statements
    if not ledger or ledger[0] != c.pending.statement:
        raise RuntimeError('LAN statement is no longer first in the native ledger')
    return c


def retain(owner):
    """Publish only a real, pending statement. Never generate one for a test."""
    from .native.native_turn_continuation import TurnContinuation
    from .network_owner import STAGE
    ledger = owner.prefix.deferred_events.pending_diplomacy_statements
    c = getattr(owner, 'turn_continuation', None)
    if c is not None:
        validate(owner)
        return True
    if not ledger:
        return False
    pid, state = _boundary(owner)
    item = _pending(owner, ledger[0], pid)
    owner.turn_continuation = TurnContinuation(None, state['turn'], pending=item,
        origin='network', return_stage=STAGE)
    validate(owner)
    owner.emit('official_lan_dialogue_retained', turn=state['turn'], player_id=pid,
        statement_sequence=item.statement['event_sequence'], session=item.session,
        automatic_response=False, game_update_called=False,
        strategic_training_ready=False)
    return True


def resume(owner):
    """Finish the answered statement; leave any followup for an explicit choice."""
    from .native.native_turn_continuation import TurnContinuation
    from .native.native_player_observation import observe_player
    from .network_owner import STAGE
    pid, state = _boundary(owner)
    c = getattr(owner, 'turn_continuation', None)
    if (type(c) is not TurnContinuation or c.origin != 'network'
            or c.steps is not None or c.return_stage != STAGE or c.pending is None
            or c.executing or c.finished or c.pending.session['player_id'] != pid
            or state['turn'] != c.turn):
        raise RuntimeError('No answered LAN dialogue to resume')
    ledger = owner.prefix.deferred_events.pending_diplomacy_statements
    if c.pending.statement in ledger:
        raise RuntimeError('Cannot resume before the native statement was answered')
    if ledger:
        c.pending = _pending(owner, ledger[0], pid)
        validate(owner)
        return None
    p = owner.prefix
    after = observe_player(p.runtime, p.ui_child, pid)
    if after['player_id'] != pid or after['turn'] != c.turn:
        raise RuntimeError('LAN response changed the native player/turn')
    c.pending = None
    c.finished = True
    owner.turn_continuation = None
    owner.control(empty=True)
    owner.emit('official_lan_dialogue_resolved', turn=c.turn, player_id=pid,
        automatic_response=False, game_update_called=False,
        end_turn_reissued=False, strategic_training_ready=False)
    return after


def control(owner):
    if getattr(owner, 'turn_continuation', None) is not None:
        validate(owner)
    else:
        owner.control(empty=True)


def attach_database(owner):
    """Reuse the pending-dialogue DB namespace on the same bound connection.

    Native diplomacy_choices.read uses this same owner marker and registration.
    An initial overview can be opened before any pending statement exists.
    """
    p = owner.prefix
    if p.runtime.database_bound is not True:
        raise RuntimeError('Official gameplay database is not bound')
    if not getattr(owner, 'diplomacy_database_namespace_attached', False):
        p.runtime.namespaces.register(p.ui_child, 'DB')
        owner.diplomacy_database_namespace_attached = True
        owner.emit('native_diplomacy_database_namespace_attached',
            borrowed_gameplay_connection=True, new_database_connection=False,
            strategic_training_ready=False)


def read_overview(owner, player_id, turn):
    """Read the official initial selections for already-met living majors."""
    from . import diplomacy_overview as overview
    pid, state = _boundary(owner)
    if (pid != player_id or state['turn'] != turn
            or getattr(owner, 'turn_continuation', None) is not None
            or pid not in state['active_human_player_ids']):
        raise ValueError('Diplomacy overview requires the admitted active boundary')
    if getattr(owner, 'world_input_prompts', {}).get(pid) is not None:
        raise ValueError('A pending war prompt requires its explicit response')
    p = owner.prefix
    attach_database(owner)
    configuration = overview.read_configuration(owner, pid)
    raw = p.runtime.evaluate_text(p.ui_child,
                                 overview.source(pid, turn, configuration=configuration),
                                 b'@lan_diplomacy_overview', capacity=262144)
    result = overview.parse(raw, pid, turn)
    owner.control(empty=True)
    return result


def initiate(owner, action, player_id, turn):
    """Revalidate and deliver one human-selected official session request."""
    from . import diplomacy_overview as overview
    from .native.native_diplomacy_choices import deliver_statement_request
    if getattr(owner, 'world_input_prompts', {}).get(player_id) is not None:
        return dict(status='refused', reason='native_world_prompt_choice_required',
                    requested_action=action)
    current = read_overview(owner, player_id, turn)
    if action not in overview.candidates(current):
        return dict(status='refused', reason='native_availability_changed',
                    requested_action=action)
    p = owner.prefix
    owner.control(empty=True)
    if p.actions.pending:
        raise RuntimeError('Initial diplomacy overlaps pending native commands')
    configuration = overview.read_configuration(owner, player_id)
    code = overview.request_source(player_id, turn,
        action['target_player_id'], action['choice'], configuration=configuration)
    owner.busy = True
    try:
        raw = p.runtime.evaluate_text(p.ui_child, code,
                                     b'@lan_initial_diplomacy_request', capacity=1024)
        if raw != b'requested':
            raise RuntimeError('Official initial diplomacy request was not emitted')
        deliver_statement_request(p.actions)
        p.deferred_events.drain_empty_receivers()
        p.view_publisher.publish()
    except BaseException:
        owner.poisoned = True
        owner.stage = 'poisoned'
        raise
    finally:
        owner.busy = False
    pending = retain(owner)
    control(owner)
    owner.emit('official_lan_initial_diplomacy_delivered', player_id=player_id,
        turn=turn, action=action, pending_statement=pending,
        request_delivered=True, diplomatic_terms_accepted=None,
        automatic_response=False, game_update_called=False,
        strategic_training_ready=False)
    return dict(status='completed', reason=None, requested_action=action)

"""Retain the exact native update position while a player answers a statement.

Only Python execution is suspended. Native flags, completion archives, turn
counts and the GameCore state are never reconstructed from a saved phase.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from civ6_host.runtime.native.native_pending_diplomacy import DiplomacyChoicePending
STAGE = 'official-turn-awaiting-explicit-diplomacy'
ACTION_STAGE = 'official-action-awaiting-explicit-diplomacy'
ACTION_RETURN_STAGES = ('official-public-observed-awaiting-controlled-stop', 'official-turn-observed-awaiting-controlled-stop')

@dataclass
class TurnContinuation:
    steps: object
    turn: int
    pending: object = None
    executing: bool = False
    finished: bool = False
    origin: str = 'end_turn'
    return_stage: str | None = None

def validate(owner):
    if getattr(getattr(owner, 'turn_continuation', None), 'origin', None) == 'network':
        from civ6_host.runtime.network_dialogue import validate as network_validate
        return network_validate(owner)
    owner.check_thread()
    c = getattr(owner, 'turn_continuation', None)
    expected_stage = STAGE if type(c) is TurnContinuation and c.origin == 'end_turn' else ACTION_STAGE
    if type(c) is not TurnContinuation or c.origin not in ('end_turn', 'world_input') or c.finished or c.executing or (c.pending is None) or (c.origin == 'end_turn' and c.steps is None) or (c.origin == 'world_input' and c.steps is not None) or (c.origin == 'world_input' and c.return_stage not in ACTION_RETURN_STAGES) or (owner.stage != expected_stage) or owner.busy or owner.poisoned or owner.destroyed:
        raise RuntimeError('No retained, quiescent interrupted turn')
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Interrupted native Game identity changed')
    if c.origin == 'end_turn':
        owner.control(empty=True, allow_diplomacy=True, pending_round_actor=0)
    else:
        owner.control(empty=True, allow_diplomacy=True)
    return c

def _advance(owner, c, *, allow_pause, first):
    if c.executing or c.finished:
        raise RuntimeError('Turn continuation reentry')
    c.executing = True
    if not first:
        owner.busy = True
    try:
        try:
            pending = next(c.steps)
        except StopIteration as done:
            c.finished = True
            owner.turn_continuation = None
            return done.value
        if type(pending) is not DiplomacyChoicePending:
            raise RuntimeError('Unknown turn suspension')
        if not allow_pause:
            raise pending
        c.pending = pending
        owner.busy = False
        owner.stage = STAGE
        owner.emit('official_turn_paused_for_explicit_choice', turn=c.turn, session=pending.session, end_turn_reissued=False, round_completed=False, automatic_choices_applied=False, strategic_training_ready=False)
        return None
    except BaseException:
        owner.busy = False
        owner.poisoned = True
        owner.stage = 'poisoned'
        raise
    finally:
        c.executing = False

def begin(owner, steps, *, turn, allow_pause):
    if getattr(owner, 'turn_continuation', None) is not None:
        raise RuntimeError('Cannot start a second EndTurn')
    c = TurnContinuation(steps, turn)
    owner.turn_continuation = c
    return _advance(owner, c, allow_pause=allow_pause, first=True)

def begin_action_dialogue(owner, turn, player_id=0):
    """Retain an action-created native dialogue without manufacturing EndTurn."""
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_official_load import HOTSEAT_PROFILE
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_pending_diplomacy import source
    from civ6_host.runtime.native.native_pending_diplomacy import parse
    from civ6_host.runtime.native.native_pending_diplomacy import DiplomacyChoicePending
    from civ6_host.runtime.native.native_player_observation import observe_player
    if type(turn) is not int or type(player_id) is not int or player_id != 0:
        raise ValueError('Action diplomacy currently requires single-player actor 0')
    inputs = getattr(owner, 'inputs', None)
    profile = getattr(inputs, 'profile', None)
    if profile in (HOTSEAT_PROFILE, HOTSEAT_FOUR_PROFILE):
        raise ValueError('Action-created diplomacy is unsupported in Hotseat: active-player stage is not qualified')
    if profile is not SINGLE_PROFILE:
        raise ValueError('Action-created diplomacy requires the qualified Single profile')
    if owner.stage not in ACTION_RETURN_STAGES:
        raise RuntimeError('Action dialogue requires a resumable player decision boundary')
    return_stage = owner.stage
    if getattr(owner, 'turn_continuation', None) is not None:
        raise RuntimeError('Cannot start action dialogue inside another retained continuation')
    owner.check_thread()
    if owner.busy or owner.poisoned or owner.destroyed:
        raise RuntimeError('Action dialogue requires an idle native owner')
    if owner.topology(game_required=True) != owner.bound_identity or owner.game_flag() != 1:
        raise RuntimeError('Action dialogue native Game identity changed')
    p = owner.prefix
    ledger = p.deferred_events.pending_diplomacy_statements
    if type(ledger) is not list or len(ledger) != 1:
        raise RuntimeError('Action dialogue requires exactly one pending native statement')
    if p.actions.pending:
        raise RuntimeError('Action dialogue overlaps a native action archive')
    statement = ledger[0]
    raw = p.runtime.evaluate_text(p.ui_child, source(statement, player_id), b'@action_dialogue_pending_session', capacity=2048)
    session = parse(raw, statement, player_id)
    if session['is_open'] is not True:
        raise RuntimeError('Action dialogue native session is not open')
    observation = observe_player(p.runtime, p.ui_child, player_id)
    if type(observation) is not dict or observation.get('player_id') != player_id or type(observation.get('player_id')) is not int or (observation.get('turn') != turn) or (type(observation.get('turn')) is not int):
        raise RuntimeError('Action dialogue actor or turn changed')
    owner.control(empty=True, allow_diplomacy=True)
    c = TurnContinuation(None, turn, pending=DiplomacyChoicePending(statement, session), origin='world_input', return_stage=return_stage)
    owner.turn_continuation = c
    owner.stage = ACTION_STAGE
    owner.explicit_observation = observation
    owner.emit('official_action_paused_for_explicit_choice', turn=turn, player_id=player_id, session=session, origin='world_input', end_turn_reissued=False, round_completed=False, automatic_choices_applied=False, strategic_training_ready=False)
    return observation

def resume(owner):
    if getattr(getattr(owner, 'turn_continuation', None), 'origin', None) == 'network':
        from civ6_host.runtime.network_dialogue import resume as network_resume
        return network_resume(owner)
    c = validate(owner)
    if c.pending.statement in owner.prefix.deferred_events.pending_diplomacy_statements:
        raise RuntimeError('Cannot resume before answering the published statement')
    if c.origin == 'world_input':
        from civ6_host.runtime.native.native_pending_diplomacy import source
        from civ6_host.runtime.native.native_pending_diplomacy import parse
        from civ6_host.runtime.native.native_pending_diplomacy import DiplomacyChoicePending
        from civ6_host.runtime.native.native_player_observation import observe_player
        try:
            ledger = owner.prefix.deferred_events.pending_diplomacy_statements
            if ledger:
                if len(ledger) != 1:
                    raise RuntimeError('Action dialogue followups exceeded one retained statement')
                statement = ledger[0]
                raw = owner.prefix.runtime.evaluate_text(owner.prefix.ui_child, source(statement, 0), b'@action_dialogue_followup_session', capacity=2048)
                session = parse(raw, statement, 0)
                if session['is_open'] is not True:
                    raise RuntimeError('Action dialogue followup session is not open')
                c.pending = DiplomacyChoicePending(statement, session)
                owner.stage = ACTION_STAGE
                owner.control(empty=True, allow_diplomacy=True)
                return None
            after = observe_player(owner.prefix.runtime, owner.prefix.ui_child, 0)
            if after.get('player_id') != 0 or after.get('turn') != c.turn:
                raise RuntimeError('Action dialogue response changed actor or turn')
            c.pending = None
            c.finished = True
            owner.turn_continuation = None
            owner.stage = c.return_stage
            owner.explicit_observation = after
            owner.control(empty=True)
            return after
        except BaseException:
            owner.poisoned = True
            owner.stage = 'poisoned'
            raise
    c.pending = None
    return _advance(owner, c, allow_pause=True, first=False)

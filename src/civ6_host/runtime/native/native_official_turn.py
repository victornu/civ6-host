"""First-turn continuation of the frozen official Single save, diagnostic only.

Use the retained Core and existing native requests, decision gates and updates.
Never writes processor flags or replaces a native completion archive.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime.native.native_official_postload import validate_owner
from dataclasses import dataclass

@dataclass(frozen=True)
class _HumanTurnReactivated:
    state: dict
    updates: int
    receipt: dict
OBSERVER_SOURCE = b"\nlocal function one(label,...)\n assert(select('#',...)==1,'Saved solo invalid '..label..' arity')\n return ...\nend\nlocal player=one('local player',Game.GetLocalPlayer())\nlocal observer=one('local observer',Game.GetLocalObserver())\nassert(type(player)=='number' and type(observer)=='number' and\n       player==0 and observer==0,'Saved solo local player/observer changed')\nreturn '0|0'\n"

def check_state(state, *, turn, human_active):
    if type(turn) is not int or not 0 <= turn <= 2147483647 or type(human_active) is not bool:
        raise ValueError('Invalid saved solo phase')
    if type(state) is not dict or type(state.get('current_game_turn')) is not int or state['current_game_turn'] != turn or (type(state.get('local_player')) is not int) or (state['local_player'] != 0) or (type(state.get('players')) is not list) or (len(state['players']) != 2):
        raise RuntimeError('Saved solo turn or perspective changed unexpectedly')
    for pid, row in enumerate(state['players']):
        if type(row) is not dict or type(row.get('player_id')) is not int or row['player_id'] != pid or (type(row.get('active')) is not bool) or (type(row.get('complete')) is not bool):
            raise RuntimeError('Saved solo player state is malformed')
    if state['players'][0]['active'] is not human_active:
        raise RuntimeError('Saved solo human activity differs from this phase')
    if human_active and state['players'][1]['active']:
        raise RuntimeError('Saved sequential solo has two active majors')
    if not human_active and state['players'][0]['complete']:
        raise RuntimeError('Ended human turn still claims begin-turn readiness')
    return state

def pump_saved_single(prefix, *, turn, max_updates=128):
    steps = _pump_saved_single_steps(prefix, turn=turn, max_updates=max_updates)
    try:
        pending = next(steps)
    except StopIteration as done:
        return done.value
    raise pending

def _pending_choices(prefix):
    from civ6_host.runtime.native.native_pending_diplomacy import require_no_unhandled_statements
    from civ6_host.runtime.native.native_pending_diplomacy import DiplomacyChoicePending
    while True:
        try:
            require_no_unhandled_statements(prefix)
        except DiplomacyChoicePending as pending:
            yield pending
        else:
            return

def _pump_saved_single_steps(prefix, *, turn, max_updates=128, reactivation=None, reactivation_count=None):
    """Let native automatic actors finish, then deliver their captured completion."""
    from civ6_host.runtime.native.native_ai_round_pump import verify_source_evidence
    verify_source_evidence()
    if type(turn) is not int or not 0 <= turn <= 2147483647 or type(max_updates) is not int or (not 0 <= max_updates <= 128):
        raise ValueError('Invalid saved solo update bound')
    if reactivation is not None:
        from civ6_host.runtime.native.native_host_turn_reactivation import HostTurnReactivation
        if type(reactivation) is not HostTurnReactivation or reactivation.prefix is not prefix or type(reactivation_count) is not int or (not 0 <= reactivation_count <= reactivation.completed_count):
            raise ValueError('Native turn reactivation needs its exact callback and request boundary')
    elif reactivation_count is not None:
        raise ValueError('Reactivation boundary without native callback')
    for updates in range(max_updates + 1):
        yield from _pending_choices(prefix)
        if prefix.deferred_events.pending:
            raise RuntimeError('Solo update requires drained deferred notifications')
        echo = bool(prefix.actions.pending)
        if echo:
            prefix.actions.validate_completed_round_echo(0)
        else:
            flags = prefix.actions.read(prefix.core._handle + 9156608, 4)
            if flags != b'\x00' * 4:
                raise RuntimeError('Unexplained solo processor phase without native completion')
        state = prefix.inspect_player_view()
        if prefix.runtime.evaluate_text(prefix.ui_child, OBSERVER_SOURCE, b'@official_single_wait_perspective') != b'0|0':
            raise RuntimeError('Saved solo observer changed')
        if reactivation is not None and type(state) is dict and (type(state.get('players')) is list) and (len(state['players']) == 2) and (state['players'][0].get('active') is True):
            state = check_state(state, turn=turn, human_active=True)
            receipt = reactivation.receipt_after(reactivation_count, player_id=0)
            if echo or receipt is None or state['players'][0]['complete'] is not True:
                raise RuntimeError('Human reactivation lacks a fresh callback and ready same-turn boundary')
            prefix.emit('official_single_human_reactivated', state=state, callback_receipt=receipt, additional_public_updates=updates, round_completed=False, end_turn_reissued=False, native_flags_written=False, strategic_training_ready=False)
            return _HumanTurnReactivated(state, updates, dict(receipt, turn=turn))
        state = check_state(state, turn=turn, human_active=False)
        if echo:
            if any((row['active'] or row['complete'] for row in state['players'])):
                raise RuntimeError('Native round completion arrived before majors ended')
            prefix.actions.validate_completed_round_echo(0)
            prefix.emit('official_single_completion_observed', state=state, additional_public_updates=updates, archive_hex=prefix.actions.pending[0].hex(), native_flags_written=False, archive_fabricated=False, strategic_training_ready=False)
            prefix.actions.deliver_completed_round_echo(0)
            prefix.deferred_events.drain_empty_receivers()
            return updates
        if updates == max_updates:
            raise RuntimeError('Saved solo native completion exceeded bounded updates')
        if prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Solo readback unexpectedly enqueued work')
        prefix.emit('before_official_single_wait_update', turn=turn, update_number=updates + 1, update_bound=max_updates, strategic_training_ready=False)
        prefix.actions.update_game_once()
        prefix.deferred_events.drain_empty_receivers()
        prefix.view_publisher.publish()

def run_first_turn(owner, *, experimental_fresh_controller=False, native_controller=False):
    return _run_turn(owner, turn=1, experimental_fresh_controller=experimental_fresh_controller, native_controller=native_controller)

def run_next_turn(owner, *, turn):
    if type(turn) is not int or not 2 <= turn <= 8 or getattr(owner, 'official_next_turn', None) != turn or (getattr(owner, 'native_controller_code', None) is None):
        raise RuntimeError('Following saved turn needs the retained native controller and exact next turn')
    return _run_turn(owner, turn=turn, native_controller=True)

def run_explicit_turn(owner, *, turn, user_forced=False):
    """Advance only after caller actions; never resolve a player choice here."""
    from civ6_host.runtime.native.native_saved_session_protocol import MAX_EXPLICIT_ROUNDS
    if type(user_forced) is not bool:
        raise ValueError('Exact forced turn flag required')
    if user_forced and getattr(owner, 'forced_endturn_diagnostic', False) is not True:
        raise RuntimeError('UserForced is not enabled outside the explicit diagnostic')
    limit = getattr(owner, 'explicit_round_limit', 8)
    initial = getattr(owner, 'explicit_initial_turn', 1)
    if type(limit) is not int or not 1 <= limit <= MAX_EXPLICIT_ROUNDS or type(initial) is not int or (not 1 <= initial <= 2147483647 - MAX_EXPLICIT_ROUNDS) or (type(turn) is not int) or (not initial <= turn < initial + limit) or (turn > initial and (getattr(owner, 'official_next_turn', None) != turn or getattr(owner, 'native_controller_code', None) is None)):
        raise RuntimeError('Explicit saved turn requires its exact retained native phase')
    if user_forced:
        return _run_turn(owner, turn=turn, native_controller=True, resolve_decisions=False, user_forced=True)
    return _run_turn(owner, turn=turn, native_controller=True, resolve_decisions=False)

def _run_turn(owner, *, turn, experimental_fresh_controller=False, native_controller=False, resolve_decisions=True, user_forced=False):
    from civ6_host.runtime.native.native_turn_continuation import begin
    return begin(owner, _turn_steps(owner, turn=turn, experimental_fresh_controller=experimental_fresh_controller, native_controller=native_controller, resolve_decisions=resolve_decisions, user_forced=user_forced), turn=turn, allow_pause=not resolve_decisions and getattr(owner, 'explicit_diplomacy_enabled', False) is True)

def _turn_steps(owner, *, turn, experimental_fresh_controller=False, native_controller=False, resolve_decisions=True, user_forced=False):
    if type(user_forced) is not bool:
        raise ValueError('Exact forced turn flag required')
    if user_forced and (resolve_decisions or getattr(owner, 'forced_endturn_diagnostic', False) is not True):
        raise RuntimeError('UserForced requires an explicit diagnostic without automatic decisions')
    first = turn == (1 if resolve_decisions else getattr(owner, 'explicit_initial_turn', 1))
    if not resolve_decisions and getattr(owner, 'official_turn_attempted', False):
        first = False
    inputs = validate_owner(owner, stage='official-public-observed-awaiting-controlled-stop' if first else 'official-turn-observed-awaiting-controlled-stop')
    if inputs.profile is not official.SINGLE_PROFILE or (first and getattr(owner, 'official_turn_attempted', False)):
        raise RuntimeError('Solo turn requires its first attempt on the exact saved baseline')
    if type(experimental_fresh_controller) is not bool or type(native_controller) is not bool or (experimental_fresh_controller and native_controller):
        raise ValueError('Select at most one exact Boolean controller diagnostic option')
    owner.official_turn_attempted = True
    owner.busy = True
    try:
        from civ6_host.runtime.native.native_player_observation import observe_player
        from civ6_host.runtime.native.native_turn_decisions import blocker_source
        from civ6_host.runtime.native.native_turn_decisions import parse_blockers
        from civ6_host.runtime.native.native_endturn_gate import gate_source
        from civ6_host.runtime.native.native_endturn_gate import parse_gate
        from civ6_host.runtime.native.native_checkpoint_resume_round import _require_zero_blockers
        from civ6_host.runtime.native.native_checkpoint_resume_round import _require_manual_gate
        prefix = owner.prefix
        controller = prefix.deferred_events.turn_begin_state
        if first and (not native_controller) and (controller.controller_initialized is not False or controller.controller_byte_0d is not None or controller.turn_values_by_thread or (controller.service_flags != 0)):
            raise RuntimeError('Saved solo requires its fresh host controller projection')
        prefix.deferred_events.fresh_controller_projection_enabled = experimental_fresh_controller
        if native_controller:
            from civ6_host.runtime.native.native_controller_state import prepare_session_controller
            prepare_session_controller(owner)
        initial = observe_player(prefix.runtime, prefix.ui_child, 0)
        if initial['turn'] != turn:
            raise RuntimeError('Saved solo turn changed before EndTurn')
        if not resolve_decisions and initial != getattr(owner, 'explicit_observation', None):
            raise RuntimeError('Explicit EndTurn differs from its published decision state')
        if resolve_decisions and (len(initial['cities']) != 1 or (initial['cities'][0]['x'], initial['cities'][0]['y']) != (17, 8) or (first and (len(initial['units']) != 1 or initial['units'][0]['id'] != 131073))):
            raise RuntimeError('Saved solo continuation lacks its observed native city action')
        before_jobs = owner.jobs_snapshot('before')
        owner.emit('before_official_saved_turn', observation=initial, jobs_before=before_jobs, game_mode_preserved='SINGLEPLAYER', same_save_database_proven=False, source_native_transition_compared=False, strategic_training_ready=False)
        state = check_state(prefix.inspect_player_view(), turn=turn, human_active=True)
        prefix.inspect_turn_readiness(state, 0)
        if resolve_decisions:
            if first and prefix.development_players or (not first and prefix.development_players != {0}):
                raise RuntimeError('Fresh saved solo decision bookkeeping is not empty')
            prefix.development_players.add(0)
            prefix.inspect_development_decisions(0)
        else:
            owner.emit('official_explicit_turn_no_automatic_choices', turn=turn, player_id=0, automatic_choices_applied=False, strategic_training_ready=False)
        check_state(prefix.inspect_player_view(), turn=turn, human_active=True)
        blockers = parse_blockers(prefix.runtime.evaluate_text(prefix.ui_child, blocker_source(0), b'@official_single_final_blockers'), 0, turn)
        gate = None
        if not user_forced:
            gate = parse_gate(prefix.runtime.evaluate_text(prefix.ui_child, gate_source(0), b'@official_single_final_gate'), 0, turn)
            _require_zero_blockers(blockers, 0, turn)
            _require_manual_gate(gate, 0, turn)
        owner.control(empty=True)
        owner.emit('official_saved_decisions_verified', blockers=blockers, gate=gate, forced_endturn=user_forced, tutorial_gate_qualified=False if user_forced else None, automatic_choices_applied=resolve_decisions, strategic_training_ready=False)
        owner.explicit_turn_reactivation = None
        reactivation = getattr(owner, 'host_turn_reactivation', None) if not resolve_decisions else None
        reactivation_count = reactivation.completed_count if reactivation is not None else None
        if user_forced:
            prefix.actions.request_end_turn(0, user_forced=True)
        else:
            prefix.actions.request_end_turn(0)
        prefix.actions.deliver_one()
        prefix.deferred_events.drain_empty_receivers()
        prefix.view_publisher.publish()
        updates = (yield from _pump_saved_single_steps(prefix, turn=turn, **dict(reactivation=reactivation, reactivation_count=reactivation_count) if reactivation is not None else {}))
        if isinstance(updates, _HumanTurnReactivated):
            owner.control(empty=True)
            after_jobs = owner.jobs_snapshot('after')
            observed = observe_player(prefix.runtime, prefix.ui_child, 0)
            if observed['turn'] != turn:
                raise RuntimeError('Reactivated player observation crossed the native turn')
            owner.emit('official_saved_turn_reactivated', state=updates.state, observation=observed, callback_receipt=updates.receipt, jobs_before=before_jobs, jobs_after=after_jobs, ai_wait_updates=updates.updates, round_completed=False, end_turn_reissued=False, automatic_choices_applied=False, strategic_training_ready=False)
            owner.explicit_turn_reactivation = updates.receipt
            owner.busy = False
            owner.stage = 'official-turn-observed-awaiting-controlled-stop'
            owner.official_next_turn = turn
            return observed
        prefix.actions.update_game_once()
        prefix.deferred_events.drain_empty_receivers()
        prefix.view_publisher.publish()
        yield from _pending_choices(prefix)
        state = check_state(prefix.inspect_player_view(), turn=turn + 1, human_active=True)
        state = check_state(prefix.inspect_turn_readiness(state, 0), turn=turn + 1, human_active=True)
        if state['players'][0]['complete'] is not True:
            raise RuntimeError('Saved solo next turn is not decision-ready')
        owner.control(empty=True)
        after_jobs = owner.jobs_snapshot('after')
        observed = observe_player(prefix.runtime, prefix.ui_child, 0)
        if observed['turn'] != turn + 1 or (resolve_decisions and len(observed['cities']) != 1):
            raise RuntimeError('Saved solo next-turn public observation is inconsistent')
        owner.emit('official_saved_turn_observed', state=state, observation=observed, jobs_before=before_jobs, jobs_after=after_jobs, ai_wait_updates=updates, next_turn_decision_ready=True, experimental_fresh_controller=experimental_fresh_controller, native_controller_constructor_getter=native_controller, scheduler_ledger_postrun_required=True, native_flags_written=False, same_save_native_transition_compared=False, strategic_training_ready=False)
        owner.busy = False
        owner.stage = 'official-turn-observed-awaiting-controlled-stop'
        owner.official_next_turn = turn + 1
        return observed
    except BaseException:
        owner.busy = False
        owner.poisoned = True
        owner.stage = 'poisoned'
        raise

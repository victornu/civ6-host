"""Replay an existing official four-human transcript through the saved Core.

Only the caller-recorded actions are admitted. Native turn ownership,
readiness, legality and completion are observed, never assigned by this host.
This diagnostic does not establish the complete action space or save/DB parity.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass
from civ6_host.runtime.native.native_diagnostic_roster import validate_player
from civ6_host.runtime.native.native_ui_profile import FORCE_TURN_DELIVERY_PATH
from civ6_host.runtime.native.native_ui_profile import FORCE_TURN_DELIVERY_SHA256
from civ6_host.runtime.native.native_ui_profile import gate_admitted
PLAYERS = (0, 1, 2, 3)
REFERENCE = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_hotseat.py')))).resolve().parents[1] / 'evidence/phase2-hotseat-resets/run.json'
REFERENCE_SHA = 'c118f991ba5421bc016a3426f8269dbf08133737d7f93969738b0ce77900ec2d'

@dataclass(frozen=True)
class _HotseatHumanReactivated:
    state: dict
    updates: int
    receipt: dict

def reference_transcript():
    raw = _resolve_resource_path(REFERENCE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA:
        raise ValueError('Official four-player transcript changed')
    result = json.loads(raw)
    if result['status'] != 'completed' or result['trajectory_differences'] != [dict(actor=p, differences=[]) for p in range(5)] or len(result['episodes']) != 2 or any((e['baseline_differences'] for e in result['episodes'])):
        raise ValueError('Official reset reference did not complete identically')
    episode = result['episodes'][0]
    actions = [{k: v for k, v in row['action'].items() if k != 'request_id'} for row in episode['actions']]
    expected = []
    for pid in PLAYERS:
        expected.extend([dict(kind='skip_turn', player_id=pid, turn=3, unit_id=131073), dict(kind='end_player_turn', player_id=pid, turn=3)])
    if actions != expected or len(episode['visits']) != 4:
        raise ValueError('Recorded explicit four-player action sequence differs')
    return (episode, actions)

def check_state(state, *, turn, local, active):
    validate_player(local, PLAYERS)
    if active is not None:
        validate_player(active, PLAYERS)
    if type(turn) is not int or not 0 <= turn <= 100000 or type(state) is not dict or (type(state.get('current_game_turn')) is not int) or (state['current_game_turn'] != turn) or (type(state.get('local_player')) is not int) or (state['local_player'] != local) or (type(state.get('players')) is not list) or (len(state['players']) != 4):
        raise RuntimeError('Four-human turn or native perspective changed unexpectedly')
    for pid, row in enumerate(state['players']):
        if type(row) is not dict or type(row.get('player_id')) is not int or row['player_id'] != pid or (type(row.get('active')) is not bool) or (type(row.get('complete')) is not bool) or (row['active'] is not (pid == active)) or (pid != active and row['complete']):
            raise RuntimeError('Four-human roster or activity differs from the native handoff')
    return state

def compare_reference(observation, reference):
    """Common own-state fields only; no claim about unrepresented observations."""
    bridge = reference['observation']

    def entities(rows, fields):
        return sorted(({key: r[key] for key in fields} for r in rows), key=lambda r: r['id'])
    units = ('id', 'type', 'x', 'y', 'damage', 'moves')
    cities = ('id', 'x', 'y', 'population')
    actual = dict(player_id=observation['player_id'], turn=observation['turn'], width=observation['width'], height=observation['height'], gold=observation['economy']['gold'], cities=entities(observation['cities'], cities), units=entities(observation['units'], units))
    expected = dict(player_id=reference['player_id'], turn=reference['turn'], width=bridge['map']['width'], height=bridge['map']['height'], gold=bridge['economy']['gold'], cities=entities(bridge['cities'], cities), units=entities(bridge['units'], units))
    differences = {k: dict(expected=expected[k], actual=actual[k]) for k in actual if actual[k] != expected[k]}
    return dict(matched=not differences, differences=differences, actual=actual, reference_sha256=REFERENCE_SHA, complete_observation_parity=False)

def _publish(prefix):
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()

def _state(prefix, turn, local, active):
    return check_state(prefix.inspect_player_view(player_ids=PLAYERS), turn=turn, local=local, active=active)

def _published_outcome(prefix, state):
    """Read the actual actor before imposing a nonterminal handoff shape.

    The existing reader accepts an eliminated current player and requires
    drained published state. No scheduled actor, readiness flag or lack of a
    winner is substituted for the official native result.
    """
    from civ6_host.runtime.native.native_victory_diagnostic import observe_after_round_echo
    observe_after_round_echo(prefix, state['local_player'], state['current_game_turn'])

def _ready(prefix, turn, pid, *, stop_on_victory=False):
    for updates in range(9):
        state = prefix.inspect_player_view(player_ids=PLAYERS)
        if stop_on_victory:
            _published_outcome(prefix, state)
        check_state(state, turn=turn, local=pid, active=pid)
        if state['players'][pid]['complete']:
            prefix.emit('official_hotseat_ready', state=state, additional_public_updates=updates, native_flags_written=False, strategic_training_ready=False)
            return state
        if updates == 8:
            raise RuntimeError('Four-human readiness exceeded eight native updates')
        if prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Pending work before four-human readiness update')
        prefix.actions.update_game_once()
        _publish(prefix)

def _finish_round(prefix, turn, *, stop_on_victory=False):
    from civ6_host.runtime.native.native_ai_round_pump import verify_source_evidence
    verify_source_evidence()
    for updates in range(129):
        if prefix.deferred_events.pending:
            raise RuntimeError('Undrained four-human events')
        if prefix.actions.pending:
            prefix.actions.validate_completed_round_echo(3, player_ids=PLAYERS)
            _state(prefix, turn, 3, None)
            prefix.actions.deliver_completed_round_echo(3, player_ids=PLAYERS)
            prefix.deferred_events.drain_empty_receivers()
            if stop_on_victory:
                from civ6_host.runtime.native.native_victory_diagnostic import observe_after_round_echo
                prefix.view_publisher.publish()
                observe_after_round_echo(prefix, 3, turn)
            prefix.actions.update_game_once()
            _publish(prefix)
            return _ready(prefix, turn + 1, 0, stop_on_victory=stop_on_victory)
        if stop_on_victory:
            _published_outcome(prefix, prefix.inspect_player_view(player_ids=PLAYERS))
        if prefix.actions.read(prefix.core._handle + 9156608, 4) != bytes(4):
            raise RuntimeError('Unexplained native phase before four-human completion')
        _state(prefix, turn, 3, None)
        if updates == 128:
            raise RuntimeError('Four-human completion exceeded bounded updates')
        if prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Four-human completion readback enqueued unexpected work')
        prefix.actions.update_game_once()
        _publish(prefix)

def prepare_interactive(owner):
    """Retain the loaded four-human context at its first actual decision phase."""
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_official_postload import validate_owner
    from civ6_host.runtime.native.native_official_postload import compare_public_own_fields
    from civ6_host.runtime.native.native_controller_code import NativeControllerCode
    from civ6_host.runtime.native.native_controller_state import NativeControllerTurnState
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native.native_victory_diagnostic import NativeVictoryReached
    inputs = validate_owner(owner, stage='post160-observed-awaiting-controlled-stop')
    if inputs.profile is not HOTSEAT_FOUR_PROFILE or getattr(owner, 'hotseat_round_attempted', False):
        raise RuntimeError('Interactive hotseat requires the exact untouched official four-human save')
    owner.hotseat_round_attempted = True
    owner.busy = True
    try:
        p = owner.prefix
        c = p.deferred_events.turn_begin_state
        if c.controller_initialized is not False or c.controller_byte_0d is not None or c.turn_values_by_thread or (c.service_flags != 0):
            raise RuntimeError('Interactive hotseat controller is not fresh')
        p.deferred_events.fresh_controller_projection_enabled = False
        owner.native_controller_code = NativeControllerCode()
        p.deferred_events.turn_begin_state = NativeControllerTurnState(owner.native_controller_code, owner.emit)
        turn = 3
        if inputs.official_bundle is not None:
            bundle = getattr(owner, 'captured_bundle', None)
            if bundle is None or bundle.inputs is not inputs or owner.loaded_readback['turn'] != bundle.initial_turn:
                raise ValueError('Captured Hotseat initial boundary differs')
            turn = bundle.initial_turn
        p.view_publisher.publish()
        _ready(p, turn, 0, stop_on_victory=True)
        observation = observe_player(p.runtime, p.ui_child, 0)
        compare_public_own_fields(observation, owner.loaded_readback)
        owner.control(empty=True)
        owner.hotseat_actor = 0
        owner.hotseat_turn = turn
        owner.stage = 'official-hotseat-decision-ready'
        owner.busy = False
        owner.emit('official_hotseat_interactive_ready', observation=observation, player_ids=list(PLAYERS), automatic_choices_applied=False, strategic_training_ready=False)
        return observation
    except NativeVictoryReached:
        owner.busy = False
        owner.stage = 'official-hotseat-terminal'
        raise
    except BaseException:
        owner.busy = False
        owner.poisoned = True
        owner.stage = 'poisoned'
        raise

def _advance_after_end_turn(prefix, turn, player_id, *, reactivation=None, reactivation_count=None):
    """Follow native ownership, including nonconsecutive living human slots.

    Reuse the pinned public update and pre-update echo route. No life flags,
    guessed successor, replacement archive or automatic game choice is used.
    The fixed recorded replay keeps its separate historical assertions.
    """
    from civ6_host.runtime.native.native_ai_round_pump import verify_source_evidence
    verify_source_evidence()
    validate_player(player_id, PLAYERS)
    if type(turn) is not int or not 0 <= turn < 100000:
        raise ValueError('Invalid handoff turn')
    if reactivation is not None:
        from civ6_host.runtime.native.native_host_turn_reactivation import HostTurnReactivation
        if type(reactivation) is not HostTurnReactivation or reactivation.prefix is not prefix or type(reactivation_count) is not int or (not 0 <= reactivation_count <= reactivation.completed_count):
            raise ValueError('Hotseat reactivation needs its exact callback and request boundary')
    elif reactivation_count is not None:
        raise ValueError('Reactivation boundary without native callback')
    echoed = False
    for updates in range(129):
        if prefix.deferred_events.pending:
            raise RuntimeError('Undrained handoff events')
        state = prefix.inspect_player_view(player_ids=PLAYERS)
        if reactivation is not None:
            receipt = reactivation.receipt_after(reactivation_count, player_id=player_id)
            if receipt is not None:
                if prefix.actions.pending:
                    raise RuntimeError('Fresh same-turn reactivation cannot include a round echo')
                _published_outcome(prefix, state)
                check_state(state, turn=turn, local=player_id, active=player_id)
                ready = _ready(prefix, turn, player_id, stop_on_victory=True)
                if prefix.actions.pending or prefix.deferred_events.pending:
                    raise RuntimeError('Reactivated Hotseat readiness left queued native work')
                confirmed = reactivation.receipt_after(reactivation_count, player_id=player_id)
                if confirmed != receipt:
                    raise RuntimeError('Hotseat reactivation callback changed during readiness')
                ready = _state(prefix, turn, player_id, player_id)
                if ready['players'][player_id]['complete'] is not True:
                    raise RuntimeError('Reactivated Hotseat actor is not decision-ready')
                result = dict(confirmed, turn=turn)
                prefix.emit('official_hotseat_human_reactivated', state=ready, callback_receipt=result, player_id=player_id, turn=turn, additional_public_updates=updates, round_completed=False, end_turn_reissued=False, native_flags_written=False, strategic_training_ready=False)
                return _HotseatHumanReactivated(ready, updates, result)
        if prefix.actions.pending:
            if echoed:
                raise RuntimeError('Duplicate native completed-round echo')
            prefix.actions.validate_completed_round_echo(player_id, player_ids=PLAYERS)
            check_state(state, turn=turn, local=player_id, active=None)
            prefix.actions.deliver_completed_round_echo(player_id, player_ids=PLAYERS)
            _publish(prefix)
            _published_outcome(prefix, state)
            echoed = True
        else:
            _published_outcome(prefix, state)
            actors = [r.get('player_id') for r in state.get('players', []) if r.get('active') is True]
            if len(actors) == 1:
                actor = actors[0]
                actual_turn = state.get('current_game_turn')
                check_state(state, turn=actual_turn, local=actor, active=actor)
                if actual_turn != turn + int(echoed) or (actual_turn == turn and actor == player_id):
                    raise RuntimeError('Native actor/turn changed outside the witnessed handoff route')
                ready = _ready(prefix, actual_turn, actor, stop_on_victory=True)
                prefix.emit('official_hotseat_native_handoff', from_player=player_id, from_turn=turn, state=ready, completed_round_echo=echoed, additional_public_updates=updates, successor_inferred=False, native_flags_written=False, strategic_training_ready=False)
                return ready
            check_state(state, turn=turn, local=player_id, active=None)
            if echoed:
                raise RuntimeError('No native next actor after completed-round update')
            if prefix.actions.read(prefix.core._handle + 9156608, 4) != bytes(4):
                raise RuntimeError('Unexplained native handoff phase without completion archive')
        if updates == 128:
            raise RuntimeError('Native handoff exceeded bounded updates')
        if prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Handoff readback enqueued unexpected work')
        prefix.actions.update_game_once()
        _publish(prefix)

def run_explicit_actor_turn(owner, *, turn, player_id, user_forced=False):
    """End this actor's turn; UserForced requires diagnostic or UI-profile admission."""
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_official_postload import validate_owner
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native.native_turn_decisions import blocker_source
    from civ6_host.runtime.native.native_turn_decisions import parse_blockers
    from civ6_host.runtime.native.native_endturn_gate import gate_source
    from civ6_host.runtime.native.native_endturn_gate import parse_gate
    from civ6_host.runtime.native.native_checkpoint_resume_round import _require_zero_blockers
    from civ6_host.runtime.native.native_checkpoint_resume_round import _require_manual_gate
    from civ6_host.runtime.native.native_victory_diagnostic import NativeVictoryReached
    validate_player(player_id, PLAYERS)
    if type(user_forced) is not bool:
        raise ValueError('Exact forced turn flag required')
    force_ui_admitted = user_forced and gate_admitted(owner, 'force_end_turn')
    if user_forced and getattr(owner, 'forced_endturn_diagnostic', False) is not True and (not force_ui_admitted):
        raise RuntimeError('UserForced is not enabled outside the explicit diagnostic')
    inputs = validate_owner(owner, stage='official-hotseat-decision-ready')
    if inputs.profile is not HOTSEAT_FOUR_PROFILE or owner.hotseat_actor != player_id or type(turn) is not int or (owner.hotseat_turn != turn) or (getattr(owner, 'native_controller_code', None) is None):
        raise RuntimeError('Explicit hotseat EndTurn lacks its retained current actor')
    owner.busy = True
    try:
        p = owner.prefix
        before = observe_player(p.runtime, p.ui_child, player_id)
        if before['turn'] != turn or before != getattr(owner, 'explicit_observation', None):
            raise RuntimeError('Hotseat decision changed before EndTurn')
        _state(p, turn, player_id, player_id)
        blockers = parse_blockers(p.runtime.evaluate_text(p.ui_child, blocker_source(player_id, player_ids=PLAYERS), b'@explicit_hotseat_blockers'), player_id, turn, player_ids=PLAYERS)
        gate = None
        if not user_forced:
            gate = parse_gate(p.runtime.evaluate_text(p.ui_child, gate_source(player_id, player_ids=PLAYERS), b'@explicit_hotseat_gate'), player_id, turn, player_ids=PLAYERS)
            _require_zero_blockers(blockers, player_id, turn)
            _require_manual_gate(gate, player_id, turn)
        owner.control(empty=True)
        owner.explicit_turn_reactivation = None
        reactivation = getattr(owner, 'host_turn_reactivation', None)
        reactivation_count = reactivation.completed_count if reactivation is not None else None
        owner.emit('official_hotseat_explicit_turn_verified', player_id=player_id, turn=turn, blockers=blockers, gate=gate, automatic_choices_applied=False, user_forced=user_forced, tutorial_gate_qualified=bool(force_ui_admitted) if user_forced else None, forced_turn_availability_source={'path': FORCE_TURN_DELIVERY_PATH, 'sha256': FORCE_TURN_DELIVERY_SHA256} if force_ui_admitted else None)
        if user_forced:
            p.actions.request_end_turn(player_id, player_ids=PLAYERS, user_forced=True)
        else:
            p.actions.request_end_turn(player_id, player_ids=PLAYERS)
        p.actions.deliver_one()
        _publish(p)
        state = _advance_after_end_turn(p, turn, player_id, **dict(reactivation=reactivation, reactivation_count=reactivation_count) if reactivation is not None else {})
        if isinstance(state, _HotseatHumanReactivated):
            owner.control(empty=True)
            after = observe_player(p.runtime, p.ui_child, player_id)
            if after['player_id'] != player_id or after['turn'] != turn:
                raise RuntimeError('Reactivated Hotseat observation crossed actor or turn')
            owner.hotseat_actor = player_id
            owner.hotseat_turn = turn
            owner.explicit_turn_reactivation = state.receipt
            owner.busy = False
            owner.stage = 'official-hotseat-decision-ready'
            owner.emit('official_hotseat_turn_reactivated', state=state.state, observation=after, callback_receipt=state.receipt, ai_wait_updates=state.updates, round_completed=False, end_turn_reissued=False, automatic_choices_applied=False, strategic_training_ready=False)
            return after
        after = observe_player(p.runtime, p.ui_child, state['local_player'])
        owner.control(empty=True)
        owner.hotseat_actor = state['local_player']
        owner.hotseat_turn = state['current_game_turn']
        owner.busy = False
        owner.emit('official_hotseat_explicit_actor_advanced', from_player=player_id, from_turn=turn, state=state, observation=after, host_identity_changed=False, player_switch_memory_written=False, automatic_choices_applied=False, strategic_training_ready=False)
        return after
    except NativeVictoryReached:
        owner.busy = False
        owner.stage = 'official-hotseat-terminal'
        raise
    except BaseException:
        owner.busy = False
        owner.poisoned = True
        owner.stage = 'poisoned'
        raise

def replay_official_round(owner):
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_official_postload import validate_owner
    from civ6_host.runtime.native.native_official_postload import compare_public_own_fields
    from civ6_host.runtime.native.native_controller_code import NativeControllerCode
    from civ6_host.runtime.native.native_controller_state import NativeControllerTurnState
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native.native_turn_decisions import blocker_source
    from civ6_host.runtime.native.native_turn_decisions import parse_blockers
    from civ6_host.runtime.native.native_endturn_gate import gate_source
    from civ6_host.runtime.native.native_endturn_gate import parse_gate
    from civ6_host.runtime.native.native_checkpoint_resume_round import _require_zero_blockers
    from civ6_host.runtime.native.native_checkpoint_resume_round import _require_manual_gate
    from civ6_host.runtime.native import native_unit_skip as skip
    episode, actions = reference_transcript()
    inputs = validate_owner(owner, stage='post160-observed-awaiting-controlled-stop')
    if inputs.profile is not HOTSEAT_FOUR_PROFILE or getattr(owner, 'hotseat_round_attempted', False):
        raise RuntimeError('Four-human replay requires the exact untouched official profile')
    owner.hotseat_round_attempted = True
    owner.busy = True
    try:
        p = owner.prefix
        c = p.deferred_events.turn_begin_state
        if c.controller_initialized is not False or c.controller_byte_0d is not None or c.turn_values_by_thread or (c.service_flags != 0):
            raise RuntimeError('Four-human replay requires a fresh native controller owner')
        p.deferred_events.fresh_controller_projection_enabled = False
        owner.native_controller_code = NativeControllerCode()
        p.deferred_events.turn_begin_state = NativeControllerTurnState(owner.native_controller_code, owner.emit)
        p.view_publisher.publish()
        before = owner.jobs_snapshot('before')
        owner.emit('before_official_hotseat_replay', actions=actions, reference_sha256=REFERENCE_SHA, jobs_before=before, automatic_choices_applied=False, strategic_training_ready=False)
        comparisons = []
        for pid in PLAYERS:
            _ready(p, 3, pid)
            observation = observe_player(p.runtime, p.ui_child, pid)
            if pid == 0:
                compare_public_own_fields(observation, owner.loaded_readback)
            comparison = compare_reference(observation, episode['visits'][pid])
            comparisons.append(comparison)
            owner.emit('official_hotseat_player_observed', player_id=pid, observation=observation, comparison=comparison, host_identity_changed=False, complete_player_observation=False)
            if not comparison['matched']:
                raise RuntimeError('Official before-action own-state subset differs')
            action = actions[pid * 2]
            uid = action['unit_id']
            owner.control(empty=True)
            owner.emit('official_hotseat_explicit_action', action=action)
            raw = p.runtime.evaluate_text(p.ui_child, skip.request_source(pid, uid, player_ids=PLAYERS), b'@official_four_skip')
            if raw != b'submitted' or len(p.actions.pending) != 1:
                raise RuntimeError('Four-human skip did not submit exactly one native archive')
            p.actions.deliver_one()
            _publish(p)
            effect = skip.parse_effect(p.runtime.evaluate_text(p.ui_child, skip.effect_source(pid, uid, player_ids=PLAYERS), b'@official_four_skip_effect'), uid)
            if effect['ready'] is not False or effect['first_ready_id'] == uid:
                raise RuntimeError('Four-human native skip effect missing')
            owner.emit('official_hotseat_skip_effect', player_id=pid, unit_id=uid, effect=effect)
            blockers = parse_blockers(p.runtime.evaluate_text(p.ui_child, blocker_source(pid, player_ids=PLAYERS), b'@official_four_blockers'), pid, 3, player_ids=PLAYERS)
            gate = parse_gate(p.runtime.evaluate_text(p.ui_child, gate_source(pid, player_ids=PLAYERS), b'@official_four_gate'), pid, 3, player_ids=PLAYERS)
            _require_zero_blockers(blockers, pid, 3)
            _require_manual_gate(gate, pid, 3)
            owner.control(empty=True)
            owner.emit('official_hotseat_explicit_action', action=actions[pid * 2 + 1], blockers=blockers, gate=gate)
            p.actions.request_end_turn(pid, player_ids=PLAYERS)
            p.actions.deliver_one()
            _publish(p)
            if pid < 3:
                state = _state(p, 3, pid + 1, pid + 1)
                owner.emit('official_hotseat_native_handoff', state=state, from_player=pid, to_player=pid + 1, host_identity_changed=False, player_switch_memory_written=False)
        final_state = _finish_round(p, 3)
        final = observe_player(p.runtime, p.ui_child, 0)
        final_comparison = compare_reference(final, episode['final'])
        owner.control(empty=True)
        owner.emit('official_hotseat_round_observed', state=final_state, observation=final, comparisons=comparisons, final_comparison=final_comparison, jobs_before=before, jobs_after=owner.jobs_snapshot('after'), explicit_actions_count=8, all_four_player_perspectives_observed=True, automatic_choices_applied=False, scheduler_ledger_postrun_required=True, save_database_binding_proven=False, strategic_training_ready=False)
        if not final_comparison['matched']:
            raise RuntimeError('Official round result own-state subset differs')
        owner.busy = False
        owner.stage = 'official-hotseat-round-observed-awaiting-controlled-stop'
        return final
    except BaseException:
        owner.busy = False
        owner.poisoned = True
        owner.stage = 'poisoned'
        raise

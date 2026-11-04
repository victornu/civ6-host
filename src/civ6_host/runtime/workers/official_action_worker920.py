from pathlib import Path as _BootstrapPath
import sys as _bootstrap_sys
_bootstrap_sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[3]))
from civ6_host.runtime.import_boundary import enable as _host_only_imports
_host_only_imports()
'Native saved-game worker accepting caller choices, never diagnostic policies.'
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import json, sys
import time
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/official_action_worker920.py')))).resolve().parents[1]

def action_completes_round(action, *, dialogue_origin=None, turn_reactivated=False):
    """Only EndTurn-owned dialogue responses can complete a native round."""
    if type(turn_reactivated) is not bool:
        raise ValueError('Exact turn-reactivation flag required')
    if action is None or turn_reactivated:
        return False
    kind = action.get('kind') if type(action) is dict else None
    if kind in ('end_turn', 'force_end_turn'):
        return True
    return kind == 'diplomacy_response' and dialogue_origin == 'end_turn'

def collect_reply_privileged987(owner, protocol, observation, decisions, closure, path):
    """Read a sidecar without advancing a retained native dialogue boundary."""
    import copy
    from civ6_host.runtime.native.native_privileged_snapshot977 import collect_privileged_snapshot
    from civ6_host.runtime.native import native_diplomacy_choices as diplomacy
    from civ6_host.runtime.native.native_turn_continuation import validate
    from civ6_host.runtime.native.native_saved_actions import snapshot
    retained = getattr(owner, 'turn_continuation', None)
    if retained is None:
        if diplomacy.is_catalog(decisions):
            raise RuntimeError('Diplomatic sidecar lacks its retained native continuation')
        return collect_privileged_snapshot(owner.prefix, player_id=decisions['player_id'], sequence=protocol.sequence, turn=observation['turn'], closure=closure, closure_path=path)
    if decisions.get('schema') != diplomacy.CURRENT_SCHEMA:
        raise RuntimeError('Privileged dialogue boundary requires the current public catalogue')
    current = validate(owner)
    diplomacy.validate_catalog(decisions, protocol.identity, protocol.sequence, observation['turn'], player_id=decisions['player_id'], actions_closed=protocol.ended or protocol.closed)
    from civ6_host.runtime.native.native_saved_yield_display982 import validate as validate_yield
    validate_yield(decisions['yield_display'], decisions['player_id'], observation['turn'], observation)
    pending = current.pending
    steps = current.steps
    turn = current.turn
    ledger = owner.prefix.deferred_events.pending_diplomacy_statements
    if current is not retained or not ledger or ledger[0] != pending.statement or (pending.statement != decisions['statement']) or (pending.session != decisions['data']['session']) or (current.turn != decisions['origin_turn']):
        raise RuntimeError('Published dialogue does not join its retained native continuation')
    saved = copy.deepcopy(dict(statement=pending.statement, session=pending.session, ledger=ledger, observation=observation, decisions=decisions))
    before = copy.deepcopy(snapshot(owner, 'before'))
    sidecar = collect_privileged_snapshot(owner.prefix, player_id=decisions['player_id'], sequence=protocol.sequence, turn=observation['turn'], closure=closure, closure_path=path)
    after = snapshot(owner, 'after')
    checked = validate(owner)
    if checked is not current or checked.pending is not pending or checked.steps is not steps or (checked.turn != turn) or (owner.prefix.deferred_events.pending_diplomacy_statements is not ledger) or (before != after) or (saved != dict(statement=pending.statement, session=pending.session, ledger=ledger, observation=observation, decisions=decisions)):
        raise RuntimeError('Privileged read changed the retained diplomatic boundary')
    expected = dict(episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=decisions['player_id'], sequence=protocol.sequence, turn=observation['turn'])
    if any((sidecar.get(key) != value for key, value in expected.items())):
        raise RuntimeError('Privileged diplomatic sidecar identity differs from the public response')
    return sidecar

def main(path):
    from civ6_host.runtime.native.native_probe import Windows
    from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
    win = Windows()
    win.kernel.SetErrorMode(1 | 2 | 32768)
    if sys.stdin.buffer.readline(16) != b'go\n':
        return 2

    def emit(stage, **fields):
        print(json.dumps(dict(stage=stage, **fields)), flush=True)
    try:
        closure = json.loads(_resolve_resource_path(_resolve_resource_path(Path(path))).read_bytes())
        from civ6_host.runtime.native.native_saved_session import validate_episode_budget_closure
        from civ6_host.runtime.native.native_saved_session import stdout_limit_ceiling
        episode_budget = validate_episode_budget_closure(closure)
        stdout_ceiling = stdout_limit_ceiling(episode_budget)
        maximum_lifetime = 600 if episode_budget is not None else 180
        if closure.get('schema') != 'civ6rl.action_session920.closure.v1' or closure['input_profile'] != 'single' or type(closure.get('lifetime_seconds')) is not int or (not 1 <= closure['lifetime_seconds'] <= maximum_lifetime) or (type(closure.get('stdout_limit_bytes')) is not int) or (not 1048576 <= closure['stdout_limit_bytes'] <= stdout_ceiling) or (type(closure['rounds']) is not int) or (not 1 <= closure['rounds'] <= 1024):
            raise ValueError('Unsupported explicit saved-game profile')
        from civ6_host.runtime.native.native_official_bundle import validate_closure_profile
        validate_closure_profile(closure)
        privileged_critic_diagnostic = closure.get('privileged_critic_diagnostic', False)
        if type(privileged_critic_diagnostic) is not bool:
            raise ValueError('Exact privileged critic diagnostic flag required')
        from civ6_host.runtime.native.native_session_checkpoint import validate_option
        checkpoint_on_close = validate_option(closure)
        from civ6_host.runtime.workers.run_official_postload909 import open_official_backend
        from civ6_host.runtime.native.native_official_postload import observe_saved_player
        from civ6_host.runtime.native.native_episode_identity import require_episode
        from civ6_host.runtime.native.native_action_session import ActionProtocol
        from civ6_host.runtime.native.native_action_session import SCHEMA
        from civ6_host.runtime.native.native_saved_session_protocol import outcome
        from civ6_host.runtime.native.native_saved_actions import read_decisions
        from civ6_host.runtime.native.native_saved_actions import apply_choice
        from civ6_host.runtime.native.native_victory_diagnostic import observe_after_round_echo
        from civ6_host.runtime.native.native_victory_diagnostic import NativeVictoryReached
        phase_started = time.perf_counter()
        owner = open_official_backend(closure, emit, win)
        emit('native_reset_timing', phase='worker_backend_open_inclusive_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='inclusive; contains child verification, DLL/context and load stage events', strategic_training_ready=False)
        phase_started = time.perf_counter()
        initial = observe_saved_player(owner)
        if owner.inputs.official_bundle is not None and initial['turn'] != closure['initial_turn']:
            raise ValueError('Loaded captured Single turn differs')
        emit('native_reset_timing', phase='initial_published_observation_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
        if owner.inputs.checkpoint is not None:
            from civ6_host.runtime.native.native_session_resume import prepare_owner
            prepare_owner(owner, initial)
        forced = closure.get('forced_endturn_diagnostic', False)
        if type(forced) is not bool:
            raise ValueError('Exact forced diagnostic flag required')
        owner.forced_endturn_diagnostic = forced
        queue_diagnostic = closure.get('production_queue_diagnostic', False)
        if type(queue_diagnostic) is not bool:
            raise ValueError('Exact production queue diagnostic flag required')
        owner.production_queue_diagnostic = queue_diagnostic
        movement_diagnostic = closure.get('multiturn_movement_diagnostic', False)
        if type(movement_diagnostic) is not bool:
            raise ValueError('Exact multi-turn diagnostic flag required')
        owner.multiturn_movement_diagnostic = movement_diagnostic
        movement_information = closure.get('movement_information_diagnostic', False)
        if type(movement_information) is not bool:
            raise ValueError('Exact movement information flag required')
        owner.movement_information_diagnostic = movement_information
        cancel_orders = closure.get('unit_order_cancel_diagnostic', False)
        if type(cancel_orders) is not bool:
            raise ValueError('Exact unit cancel flag required')
        owner.unit_order_cancel_diagnostic = cancel_orders
        world_input = closure.get('world_input_diagnostic', False)
        if type(world_input) is not bool:
            raise ValueError('Exact world input flag required')
        owner.world_input_diagnostic = world_input
        if movement_diagnostic:
            emit('multiturn_movement_diagnostic_scope', profile='visible_multi_turn', fog_routes_qualified=False, complete_human_actions=False, strategic_training_ready=False)
        focus_diagnostic = closure.get('city_focus_diagnostic', False)
        if type(focus_diagnostic) is not bool:
            raise ValueError('Exact city-focus diagnostic flag required')
        owner.city_focus_diagnostic = focus_diagnostic
        management_diagnostic = closure.get('city_management_diagnostic', False)
        if type(management_diagnostic) is not bool or (management_diagnostic and (not focus_diagnostic)):
            raise ValueError('Exact complete city-management diagnostic flag required')
        owner.city_management_diagnostic = management_diagnostic
        if management_diagnostic:
            emit('city_management_diagnostic_scope', tutorial_gate_qualified=False, automatic_choices_applied=False, strategic_training_ready=False)
        if focus_diagnostic:
            emit('city_focus_diagnostic_scope1000', tutorial_gate_qualified=False, automatic_choices_applied=False, strategic_training_ready=False)
        if queue_diagnostic:
            emit('production_queue_diagnostic_scope', tutorial_gate_qualified=False, automatic_choices_applied=False, strategic_training_ready=False)
        if forced:
            emit('forced_endturn_diagnostic_scope', native_reason='UserForced', official_keyboard_effect_parity_proven=False, tutorial_gate_qualified=False, automatic_choices_applied=False, strategic_training_ready=False)
        owner.explicit_initial_turn = initial['turn']
        protocol = ActionProtocol(require_episode(owner.prefix), closure['nonce'], round_limit=closure['rounds'])
        owner.explicit_round_limit = protocol.limit
        owner.explicit_diplomacy_enabled = True
        if world_input:
            from civ6_host.runtime.native.native_controller_state import prepare_session_controller
            prepare_session_controller(owner)
        from civ6_host.runtime.native.native_host_turn_reactivation import install as install_host_turn_reactivation
        install_host_turn_reactivation(owner)

        def read_outcome(turn):
            if getattr(owner, 'turn_continuation', None) is not None:
                from civ6_host.runtime.native.native_turn_continuation import validate
                validate(owner)
            else:
                owner.control(empty=True)
            try:
                return observe_after_round_echo(owner.prefix, 0, turn)
            except NativeVictoryReached as exc:
                return exc.result
        phase_started = time.perf_counter()
        native = read_outcome(initial['turn'])
        protocol.ended = native['episode_terminated']
        emit('native_reset_timing', phase='initial_outcome_observation_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
        phase_started = time.perf_counter()
        observation, decisions = read_decisions(owner, 0, 0, round_limit=protocol.limit)
        emit('native_reset_timing', phase='initial_read_decisions_inclusive_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='inclusive; contains decision observation and catalogue events', strategic_training_ready=False)
        if owner.inputs.checkpoint is not None:
            from civ6_host.runtime.native.native_session_resume import compare_loaded_decisions
            compare_loaded_decisions(owner, observation, decisions)
        if 'movement_ui_probe' in closure:
            from civ6_host.runtime.native.native_movement_ui import inspect as inspect_movement_ui
            inspect_movement_ui(owner, closure['movement_ui_probe'], observation)
        protocol.decisions = decisions

        def reply(operation, action):
            if privileged_critic_diagnostic:
                if observation is None or native.get('episode_terminated') is True:
                    emit('privileged_critic_snapshot_skipped977', episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=None, sequence=protocol.sequence, turn=None, reason='terminal_or_missing_observation')
                else:
                    sidecar = collect_reply_privileged987(owner, protocol, observation, decisions, closure, path)
                    emit('privileged_critic_snapshot977', **sidecar)
            fields = dict(schema=SCHEMA, nonce=protocol.nonce, episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, sequence=protocol.sequence, operation=operation, observation=observation, rounds=protocol.rounds, outcome=outcome(native, protocol.rounds, protocol.limit, closed=protocol.closed, maximum=protocol.max_round_limit), decisions=decisions, applied_action=action, automatic_choices_applied=False, action_interface_complete=False, strategic_training_ready=False)
            receipt = getattr(owner, 'explicit_turn_reactivation', None)
            if receipt is not None:
                fields['turn_reactivation'] = receipt
            emit('official_session_response', **fields)
        reply('reset', None)
        for _ in range(protocol.max_commands):
            line = sys.stdin.buffer.readline(4097)
            if not line or len(line) > 4096 or (not line.endswith(b'\n')):
                raise ValueError('Missing or oversized explicit command')
            request = json.loads(line)
            operation = protocol.validate(request)
            action = protocol.selected(request) if operation == 'act' else None
            dialogue_origin = getattr(getattr(owner, 'turn_continuation', None), 'origin', None) if action is not None and action.get('kind') == 'diplomacy_response' else None
            owner.explicit_turn_reactivation = None
            try:
                if action is not None:
                    observation = apply_choice(owner, action, protocol.decisions['turn'])
                native = read_outcome(observation['turn'])
            except NativeVictoryReached as exc:
                native = exc.result
                observation = None
            if operation == 'close' and checkpoint_on_close:
                if native['episode_terminated']:
                    raise ValueError('Terminal checkpoint not yet qualified')
                from civ6_host.runtime.native.native_session_checkpoint import save_checkpoint
                save_checkpoint(owner, observation, decisions, closure, _resolve_resource_path(Path(path)))
                unchanged_observation, unchanged_decisions = read_decisions(owner, protocol.sequence, protocol.rounds, round_limit=protocol.limit)
                if unchanged_observation != observation or unchanged_decisions != decisions:
                    raise RuntimeError('Native Save changed the published observation or decision catalogue')
                emit('official_session_checkpoint_readback_unchanged', sequence=protocol.sequence, turn=observation['turn'], strategic_training_ready=False)
            turn_completed = action_completes_round(action, dialogue_origin=dialogue_origin, turn_reactivated=getattr(owner, 'explicit_turn_reactivation', None) is not None) and getattr(owner, 'turn_continuation', None) is None
            protocol.commit(request, native_terminated=native['episode_terminated'], turn_completed=turn_completed)
            if native['episode_terminated']:
                decisions = None
            else:
                observation, decisions = read_decisions(owner, protocol.sequence, protocol.rounds, closed=protocol.closed, round_limit=protocol.limit)
            protocol.decisions = decisions
            reply(operation, action)
            if operation == 'close':
                emit('official_session_controlled_stop', normal_destroy_called=False, strategic_training_ready=False)
                terminate_worker(90)
        raise ValueError('Explicit session command budget exhausted')
    except BaseException as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        emit('official_session_refused', error=repr(exc), cleanup_guessed=False, strategic_training_ready=False)
        terminate_worker(89)
if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Expected private closure path')
    raise SystemExit(main(sys.argv[1]))

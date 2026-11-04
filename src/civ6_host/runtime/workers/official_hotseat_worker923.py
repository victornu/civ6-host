from pathlib import Path as _BootstrapPath
import sys as _bootstrap_sys
_bootstrap_sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[3]))
from civ6_host.runtime.import_boundary import enable as _host_only_imports
_host_only_imports()
'Bounded four-human native worker; every game choice comes from the caller.'
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import json, sys
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/official_hotseat_worker923.py')))).resolve().parents[1]

def worker_lifetime_ceiling(episode_budget):
    if episode_budget is None:
        return 180
    from civ6_host.runtime.native.legacy_budget import MAX_EPISODE_SECONDS
    return MAX_EPISODE_SECONDS

def reject_hotseat_action_dialogue(owner):
    retained = getattr(owner, 'turn_continuation', None)
    if getattr(retained, 'origin', None) == 'world_input':
        raise RuntimeError('Hotseat world-input diplomacy is unsupported: active-player continuation is not qualified')

def collect_reply_privileged998(owner, protocol, observation, decisions, closure, path):
    """Reuse the pinned private reader at the current Hotseat public boundary."""
    import copy
    from civ6_host.runtime.native.native_hotseat_session import HotseatActionProtocol
    from civ6_host.runtime.native.native_official_hotseat import PLAYERS
    from civ6_host.runtime.native.native_saved_actions import boundary
    from civ6_host.runtime.native.native_saved_actions import snapshot
    from civ6_host.runtime.native.native_privileged_snapshot977 import collect_privileged_snapshot
    if type(protocol) is not HotseatActionProtocol or closure.get('privileged_critic_diagnostic') is not True:
        raise ValueError('Exact Hotseat protocol and privileged diagnostic opt-in required')
    if type(observation) is not dict or type(decisions) is not dict:
        raise RuntimeError('Hotseat sidecar requires its current public observation and catalogue')
    pid = protocol.player_id
    turn = protocol.initial_turn + protocol.rounds
    expected = dict(episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=pid, sequence=protocol.sequence, turn=turn)
    if any((decisions.get(key) != value or type(decisions.get(key)) is not type(value) for key, value in expected.items())) or type(observation.get('player_id')) is not int or observation['player_id'] != pid or (type(observation.get('turn')) is not int) or (observation['turn'] != turn) or (protocol.decisions != decisions) or (getattr(owner, 'turn_continuation', None) is not None):
        raise RuntimeError('Hotseat sidecar public boundary differs from the current native actor')
    prefix = boundary(owner, player_id=pid, player_ids=PLAYERS)
    if owner.hotseat_turn != turn or getattr(owner, 'explicit_decision_player_id', None) != pid or getattr(owner, 'explicit_observation', None) != observation or (getattr(owner, 'explicit_decision_candidates', None) != decisions.get('candidates')):
        raise RuntimeError('Hotseat sidecar lacks the retained published decision')
    saved = copy.deepcopy((observation, decisions, expected))
    before = copy.deepcopy(snapshot(owner, 'before'))
    sidecar = collect_privileged_snapshot(prefix, player_id=pid, sequence=protocol.sequence, turn=turn, closure=closure, closure_path=path)
    owner.control(empty=True)
    after = snapshot(owner, 'after')
    current = dict(episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=protocol.player_id, sequence=protocol.sequence, turn=protocol.initial_turn + protocol.rounds)
    if boundary(owner, player_id=pid, player_ids=PLAYERS) is not prefix or before != after or saved != (observation, decisions, current) or (protocol.decisions != decisions) or (owner.hotseat_turn != turn) or (getattr(owner, 'turn_continuation', None) is not None) or (owner.explicit_decision_player_id != pid) or (owner.explicit_observation != observation) or (owner.explicit_decision_candidates != decisions['candidates']):
        raise RuntimeError('Privileged read changed the retained Hotseat boundary')
    if type(sidecar) is not dict or any((sidecar.get(key) != value or type(sidecar.get(key)) is not type(value) for key, value in expected.items())):
        raise RuntimeError('Privileged Hotseat sidecar identity differs from the public response')
    return sidecar

def emit_reply_privileged998(emit, owner, protocol, observation, decisions, native, closure, path):
    """Emit a separate training-only event; never enrich the actor response."""
    enabled = closure.get('privileged_critic_diagnostic', False)
    if type(enabled) is not bool:
        raise ValueError('Exact privileged critic diagnostic flag required')
    if not enabled:
        return
    if observation is None or native.get('episode_terminated') is True:
        emit('privileged_critic_snapshot_skipped977', episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=None, sequence=protocol.sequence, turn=None, reason='terminal_or_missing_observation')
        return
    emit('privileged_critic_snapshot977', **collect_reply_privileged998(owner, protocol, observation, decisions, closure, path))

def collect_reply_public(owner, protocol, observation, decisions, native, closure, path):
    """Separate owned public objective views at an already published boundary.

    No action, viewpoint setter or game update is performed for collection.
    Terminal observations remain narrow witnesses; they never replace the
    absent actor observation or invent an eliminated-player result.
    """
    import copy
    from civ6_host.runtime.native.native_hotseat_session import HotseatActionProtocol
    from civ6_host.runtime.native.native_official_hotseat import PLAYERS
    from civ6_host.runtime.native.native_saved_actions import boundary
    from civ6_host.runtime.native.native_saved_actions import snapshot
    from civ6_host.runtime.native.native_official_postload import validate_owner
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_public_objective_witness import collect
    from civ6_host.runtime.native.native_public_objective_witness import validate_players
    from civ6_host.runtime.native.native_public_objective_witness import BOUNDARY_SCHEMA
    from civ6_host.runtime.native.native_public_objective_witness import validate_boundary
    from civ6_host.runtime.native.native_public_objective_witness import sources_from_closure
    if type(protocol) is not HotseatActionProtocol:
        raise ValueError('Exact Hotseat public witness protocol required')
    players = validate_players(closure.get('public_objective_players'))
    if not players:
        raise ValueError('Public objective witness opt-in required')
    pid = protocol.player_id
    turn = protocol.initial_turn + protocol.rounds
    expected = dict(episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=pid, current_game_turn=turn)
    if type(native) is not dict or type(native.get('episode_terminated')) is not bool or any((type(native.get(k)) is not type(v) or native[k] != v for k, v in expected.items())) or (getattr(owner, 'turn_continuation', None) is not None):
        raise RuntimeError('Public objective native boundary identity differs')
    terminal = native['episode_terminated']
    if terminal:
        if observation is not None or decisions is not None or protocol.decisions is not None:
            raise RuntimeError('Terminal public witness retains an actor decision')
        if owner.stage not in ('official-hotseat-decision-ready', 'official-hotseat-terminal'):
            raise RuntimeError('Terminal public witness owner is not at a completed boundary')
        inputs = validate_owner(owner, stage=owner.stage)
        if inputs.profile is not HOTSEAT_FOUR_PROFILE or type(owner.loaded_roster) is not bytes:
            raise RuntimeError('Terminal public witness profile differs')
        if tuple(map(int, owner.loaded_roster.decode('ascii').split('|')))[3:] != PLAYERS:
            raise RuntimeError('Terminal public witness loaded roster differs')
        prefix = owner.prefix
    else:
        prefix = boundary(owner, player_id=pid, player_ids=PLAYERS)
        public_expected = dict(episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, player_id=pid, sequence=protocol.sequence, turn=turn)
        if type(observation) is not dict or type(decisions) is not dict or protocol.decisions != decisions or any((type(decisions.get(key)) is not type(value) or decisions[key] != value for key, value in public_expected.items())) or (type(observation.get('player_id')) is not int) or (observation['player_id'] != pid) or (type(observation.get('turn')) is not int) or (observation['turn'] != turn) or (owner.hotseat_turn != turn) or (owner.explicit_decision_player_id != pid) or (owner.explicit_observation != observation) or (owner.explicit_decision_candidates != decisions.get('candidates')):
            raise RuntimeError('Public witness lacks the retained active decision')

    def retained():
        return tuple((getattr(owner, name, None) for name in ('hotseat_actor', 'hotseat_turn', 'explicit_decision_player_id', 'explicit_observation', 'explicit_decision_candidates')))
    saved = copy.deepcopy((observation, decisions, native, protocol.__dict__, owner.stage, retained()))
    control = copy.deepcopy(owner.control(empty=True))
    before = copy.deepcopy(snapshot(owner, 'before'))
    witnesses = [collect(prefix, player_id=player, sequence=protocol.sequence, turn=turn, active_player_id=pid, closure=closure, closure_path=path) for player in players]
    if owner.control(empty=True) != control or snapshot(owner, 'after') != before or saved != (observation, decisions, native, protocol.__dict__, owner.stage, retained()) or (owner.prefix is not prefix) or (getattr(owner, 'turn_continuation', None) is not None):
        raise RuntimeError('Public objective read changed the retained native boundary')
    if terminal:
        validate_owner(owner, stage=owner.stage)
    elif boundary(owner, player_id=pid, player_ids=PLAYERS) is not prefix:
        raise RuntimeError('Public objective owner identity changed')
    response = dict(nonce=protocol.nonce, episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, sequence=protocol.sequence, observation=observation, outcome={'native_victory': native})
    result = dict(schema=BOUNDARY_SCHEMA, nonce=protocol.nonce, episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, sequence=protocol.sequence, turn=turn, active_player_id=pid, public_witnesses=witnesses)
    validate_boundary(result, response=response, players=players, sources=sources_from_closure(closure), nonce=protocol.nonce)
    return result

def emit_reply_public(emit, owner, protocol, observation, decisions, native, closure, path):
    """Write a distinct bounded file and manifest, never enrich actor response."""
    import hashlib
    from civ6_host.runtime.native.native_public_objective_witness import validate_players
    from civ6_host.runtime.native.native_public_objective_witness import boundary_path
    from civ6_host.runtime.native.native_public_objective_witness import MAX_BOUNDARY_BYTES
    if not validate_players(closure.get('public_objective_players')):
        return
    result = collect_reply_public(owner, protocol, observation, decisions, native, closure, path)
    target = boundary_path(_resolve_resource_path(Path(path)).parent, protocol.sequence)
    target.parent.mkdir(exist_ok=True)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError('Public witness path is redirected')
    raw = (json.dumps(result, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    if len(raw) > MAX_BOUNDARY_BYTES:
        raise ValueError('Public objective boundary byte bound exceeded')
    with _resolve_resource_path(target).open('xb') as stream:
        stream.write(raw)
    emit('public_objective_witnesses', nonce=protocol.nonce, episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, sequence=protocol.sequence, file=target.relative_to(_resolve_resource_path(Path(path)).parent).as_posix(), sha256=hashlib.sha256(raw).hexdigest())

def diagnostic_action_options(closure, *, forced_endturn_diagnostic=False):
    """Exact closure opt-ins, with the retained worker924 caller route.

    Older worker924 closures omit the forced flag. Its explicit True argument
    remains sufficient, but cannot override a newer explicit False closure.
    """
    if type(closure) is not dict or type(forced_endturn_diagnostic) is not bool:
        raise ValueError('Exact forced diagnostic flag required')
    forced = closure.get('forced_endturn_diagnostic', False)
    queue = closure.get('production_queue_diagnostic', False)
    if type(forced) is not bool:
        raise ValueError('Exact forced diagnostic flag required')
    if type(queue) is not bool:
        raise ValueError('Exact production queue diagnostic flag required')
    if forced_endturn_diagnostic and 'forced_endturn_diagnostic' in closure and (not forced):
        raise ValueError('Legacy forced diagnostic conflicts with explicit disabled closure')
    return dict(forced_endturn_diagnostic=forced or forced_endturn_diagnostic, production_queue_diagnostic=queue)

def ui_profile_admission(closure):
    """Recheck the administrative profile before loading a native episode."""
    if 'ui_profile_admission' not in closure:
        return None
    from civ6_host.runtime.native.native_ui_profile import admit
    recorded = closure['ui_profile_admission']
    if type(recorded) is not dict:
        raise ValueError('Exact UI profile receipt required')
    if any((closure.get(key, False) for key in ('city_management_diagnostic', 'city_focus_diagnostic', 'production_queue_diagnostic'))):
        raise ValueError('UI profile conflicts with diagnostic city/queue overrides')
    reference = closure.get('official_bundle')
    if type(reference) is not dict or set(reference) != {'path', 'sha256'}:
        raise ValueError('UI profile requires its official bundle reference')
    fresh = admit(recorded.get('profile_id'), official_bundle=(reference['path'], reference['sha256']), input_profile=closure.get('input_profile'))
    if fresh != recorded:
        raise ValueError('Worker UI admission differs from parent receipt')
    return fresh

def main(path, *, forced_endturn_diagnostic=False, unit_work_diagnostic=False):
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
        maximum_lifetime = worker_lifetime_ceiling(episode_budget)
        action_options = diagnostic_action_options(closure, forced_endturn_diagnostic=forced_endturn_diagnostic)
        if type(unit_work_diagnostic) is not bool:
            raise ValueError('Exact unit work diagnostic flag required')
        from civ6_host.runtime.native.native_public_objective_witness import validate_players
        validate_players(closure.get('public_objective_players'))
        if type(closure.get('privileged_critic_diagnostic', False)) is not bool:
            raise ValueError('Exact privileged critic diagnostic flag required')
        if closure.get('schema') != 'civ6rl.hotseat_action_session923.closure.v1' or closure.get('input_profile') != 'hotseat-four' or closure.get('native_controller') is not True or (closure.get('experimental_fresh_controller') is not False) or (type(closure.get('lifetime_seconds')) is not int) or (not 1 <= closure['lifetime_seconds'] <= maximum_lifetime) or (type(closure.get('stdout_limit_bytes')) is not int) or (not 1048576 <= closure['stdout_limit_bytes'] <= stdout_ceiling) or (type(closure.get('rounds')) is not int) or (not 1 <= closure['rounds'] <= 1024):
            raise ValueError('Unsupported explicit hotseat profile or bounds')
        from civ6_host.runtime.native.native_official_bundle import validate_closure_profile
        validate_closure_profile(closure)
        admitted_ui = ui_profile_admission(closure)
        from civ6_host.runtime.workers.run_official_postload909 import open_official_backend
        from civ6_host.runtime.native.native_official_hotseat import prepare_interactive
        from civ6_host.runtime.native.native_official_hotseat import PLAYERS
        from civ6_host.runtime.native.native_episode_identity import require_episode
        from civ6_host.runtime.native.native_hotseat_session import HotseatActionProtocol
        from civ6_host.runtime.native.native_hotseat_session import SCHEMA
        from civ6_host.runtime.native.native_saved_session_protocol import outcome
        from civ6_host.runtime.native.native_saved_actions import read_decisions
        from civ6_host.runtime.native.native_saved_actions import apply_choice
        from civ6_host.runtime.native.native_victory_diagnostic import observe_after_round_echo
        from civ6_host.runtime.native.native_victory_diagnostic import NativeVictoryReached
        owner = open_official_backend(closure, emit, win)
        owner.ui_profile_admission = admitted_ui
        owner.explicit_turn_reactivation = None
        if admitted_ui is not None:
            emit('official_ui_profile_admission', admission=admitted_ui, actor_input=False, automatic_choices_applied=False, strategic_training_ready=False)
        initial_terminal = None
        try:
            observation = prepare_interactive(owner)
        except NativeVictoryReached as exc:
            initial_terminal = exc.result
            observation = None
        if initial_terminal is None:
            from civ6_host.runtime.native.native_host_turn_reactivation import install as install_host_turn_reactivation
            install_host_turn_reactivation(owner)
        forced_endturn_diagnostic = action_options['forced_endturn_diagnostic']
        owner.forced_endturn_diagnostic = forced_endturn_diagnostic
        owner.production_queue_diagnostic = action_options['production_queue_diagnostic']
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
        owner.unit_work_diagnostic = unit_work_diagnostic
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
        if unit_work_diagnostic:
            emit('unit_work_diagnostic_scope', native_positive_execution_qualified=False, tutorial_and_ui_mod_hooks_qualified=False, strategic_training_ready=False)
        if forced_endturn_diagnostic:
            emit('forced_endturn_diagnostic_scope', native_reason='UserForced', official_keyboard_effect_parity_proven=False, tutorial_gate_qualified=False, production_stack_effect_verified=False, strategic_training_ready=False)
        if owner.production_queue_diagnostic:
            emit('production_queue_diagnostic_scope', tutorial_gate_qualified=False, automatic_choices_applied=False, strategic_training_ready=False)
        protocol = HotseatActionProtocol(require_episode(owner.prefix), closure['nonce'], round_limit=closure['rounds'])
        if owner.inputs.official_bundle is not None:
            protocol.initial_turn = closure['initial_turn']
            if observation is not None and observation['turn'] != protocol.initial_turn:
                raise ValueError('Loaded captured Hotseat turn differs')
        owner.explicit_round_limit = protocol.limit

        def read_outcome(obs):
            reject_hotseat_action_dialogue(owner)
            owner.control(empty=True)
            try:
                return observe_after_round_echo(owner.prefix, obs['player_id'], obs['turn'])
            except NativeVictoryReached as exc:
                return exc.result
        native = initial_terminal if initial_terminal is not None else read_outcome(observation)
        protocol.ended = native['episode_terminated']
        if protocol.ended:
            observation = None
            decisions = None
        else:
            observation, decisions = read_decisions(owner, 0, 0, round_limit=protocol.limit, player_id=0, player_ids=PLAYERS)
        protocol.decisions = decisions

        def reply(operation, action):
            emit_reply_privileged998(emit, owner, protocol, observation, decisions, native, closure, path)
            emit_reply_public(emit, owner, protocol, observation, decisions, native, closure, path)
            from civ6_host.runtime.player_views import publish_player_views
            publish_player_views(emit, owner, protocol, observation, closure, path)
            fields = dict(schema=SCHEMA, nonce=protocol.nonce, episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation, sequence=protocol.sequence, operation=operation, observation=observation, rounds=protocol.rounds, outcome=outcome(native, protocol.rounds, protocol.limit, closed=protocol.closed, maximum=protocol.max_round_limit), decisions=decisions, applied_action=action, automatic_choices_applied=False, action_interface_complete=False, strategic_training_ready=False)
            receipt = getattr(owner, 'explicit_turn_reactivation', None)
            if receipt is not None:
                fields['turn_reactivation'] = receipt
            emit('official_session_response', **fields)
        reply('reset', None)
        for _ in range(protocol.max_commands):
            line = sys.stdin.buffer.readline(4097)
            if not line or len(line) > 4096 or (not line.endswith(b'\n')):
                raise ValueError('Missing or oversized explicit hotseat command')
            request = json.loads(line)
            operation = protocol.validate(request)
            action = protocol.selected(request) if operation == 'act' else None
            owner.explicit_turn_reactivation = None
            if not native['episode_terminated']:
                try:
                    if action is not None:
                        observation = apply_choice(owner, action, protocol.decisions['turn'], player_id=protocol.player_id, player_ids=PLAYERS)
                    native = read_outcome(observation)
                except NativeVictoryReached as exc:
                    native = exc.result
                    observation = None
            protocol.commit(request, native_terminated=native['episode_terminated'], native=native, turn_reactivation=getattr(owner, 'explicit_turn_reactivation', None))
            if native['episode_terminated']:
                decisions = None
            else:
                observation, decisions = read_decisions(owner, protocol.sequence, protocol.rounds, closed=protocol.closed, round_limit=protocol.limit, player_id=protocol.player_id, player_ids=PLAYERS)
            protocol.decisions = decisions
            reply(operation, action)
            if operation == 'close':
                emit('official_session_controlled_stop', normal_destroy_called=False, strategic_training_ready=False)
                return terminate_worker(90)
        raise ValueError('Explicit hotseat command budget exhausted')
    except BaseException as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        emit('official_session_refused', error=repr(exc), cleanup_guessed=False, strategic_training_ready=False)
        terminate_worker(89)
if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Expected private closure path')
    raise SystemExit(main(sys.argv[1]))

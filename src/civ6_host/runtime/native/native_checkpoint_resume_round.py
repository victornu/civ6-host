"""Narrow, injected protocol for one loaded-checkpoint native turn.

The retained adapter supplies every native operation. No game rule is simulated.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
ACTION_PROFILE = 'develop-round'
PRODUCTION_POLICY = 'native-development'
EXPECTED_START_TURN = 2
EXPECTED_END_TURN = 3

def _state(state, *, turn: int, local: int, active: int | None, complete: bool | None):
    if type(state) is not dict or set(state) != {'current_game_turn', 'local_player', 'players'}:
        raise ValueError('Resume state is not the exact player-turn observation')
    if type(state['current_game_turn']) is not int or state['current_game_turn'] != turn:
        raise ValueError('Resume turn differs from the selected one-round profile')
    if type(state['local_player']) is not int or state['local_player'] != local:
        raise ValueError('Resume local player differs from the native handoff')
    players = state['players']
    if type(players) is not list or len(players) != 2:
        raise ValueError('Resume requires the observed two-player roster')
    expected = []
    for pid in (0, 1):
        is_active = pid == active if active is not None else False
        is_complete = pid == active and complete is True if active is not None else False
        expected.append({'player_id': pid, 'active': is_active, 'complete': is_complete})
    if players != expected:
        raise ValueError('Resume player active/complete flags differ from the expected phase')
    for row in players:
        if type(row) is not dict or set(row) != {'player_id', 'active', 'complete'} or type(row['player_id']) is not int or (type(row['active']) is not bool) or (type(row['complete']) is not bool):
            raise ValueError('Resume player phase fields are malformed')
    return state

def _final_publication_state(state, *, turn: int):
    """Validate the exact final published phase, returning its completion bit.

    A completed UI phase is only a candidate for terminal handling here; the
    caller must immediately run the official victory reader and refuse to
    continue if that reader does not confirm a native result.
    """
    if type(state) is not dict or set(state) != {'current_game_turn', 'local_player', 'players'}:
        raise ValueError('Final resume state is not the exact player-turn observation')
    if type(state['current_game_turn']) is not int or state['current_game_turn'] != turn:
        raise ValueError('Final resume turn differs from the selected one-round profile')
    if type(state['local_player']) is not int or state['local_player'] != 0:
        raise ValueError('Final resume local player differs from the native handoff')
    players = state['players']
    if type(players) is not list or len(players) != 2:
        raise ValueError('Final resume requires the observed two-player roster')
    for pid, row in enumerate(players):
        if type(row) is not dict or set(row) != {'player_id', 'active', 'complete'} or type(row['player_id']) is not int or (row['player_id'] != pid) or (type(row['active']) is not bool) or (type(row['complete']) is not bool):
            raise ValueError('Final resume player phase fields are malformed')
    if players[0]['active'] is not True or players[1]['active'] is not False or players[1]['complete'] is not False:
        raise ValueError('Final resume player phase differs from the expected player-0 boundary')
    if players[0]['complete'] not in (False, True):
        raise ValueError('Final resume completion flag is malformed')
    return players[0]['complete']

def _require_source_pinned_terminal(terminal, *, turn: int):
    from civ6_host.runtime.native import native_episode_facts as facts
    from civ6_host.runtime.native import native_victory_episode as victory
    native = terminal.get('terminal_result') if type(terminal) is dict else None
    if type(terminal) is not dict or terminal.get('terminal_result_observed') is not True or type(native) is not dict or (native.get('schema') != 'civ6rl.native_victory_episode.observation.v1') or (native.get('player_id') != 0) or (type(native.get('player_id')) is not int) or (native.get('current_game_turn') != turn) or (type(native.get('current_game_turn')) is not int) or (native.get('winner_present') is not True) or (type(native.get('winning_team')) is not int) or (type(native.get('victory_type')) is not int) or (native.get('episode_terminated') is not True) or (native.get('new_termination') is not True) or (native.get('termination_reason') != 'official_native_victory') or (native.get('first_result_observed_turn') != turn) or (type(native.get('first_result_observed_turn')) is not int) or (native.get('absent_to_present_observed') is not True) or (native.get('result_present_on_first_observation') is not False) or (native.get('source_proof_sha256') != victory.PROOF_SHA256) or (native.get('facts_source_proof_sha256') != facts.PROOF_SHA256) or (native.get('observation_only') is not True) or (native.get('eligible_for_training') is not False) or (native.get('exposed_to_learner') is not False):
        raise RuntimeError('Completed phase lacks source-pinned official victory evidence')

def _require_zero_blockers(blockers, player_id: int, turn: int):
    if type(player_id) is not int or type(turn) is not int or type(blockers) is not dict or (type(blockers.get('player_id')) is not int) or (blockers.get('player_id') != player_id) or (type(blockers.get('turn')) is not int) or (blockers.get('turn') != turn) or (blockers.get('has_primary_blocker') is not False) or (type(blockers.get('all')) is not list) or (blockers.get('all') != []):
        raise RuntimeError('Native notification blockers remain; refusing END_TURN')

def _require_manual_gate(gate, player_id: int, turn: int):
    if type(player_id) is not int or type(turn) is not int or type(gate) is not dict or (type(gate.get('player_id')) is not int) or (gate.get('player_id') != player_id) or (type(gate.get('turn')) is not int) or (gate.get('turn') != turn) or (gate.get('manual_endturn_decision_branch_verified') is not True):
        raise RuntimeError('Source-pinned manual EndTurn branch refused; refusing END_TURN')

def _before_endturn(ports, state, player_id: int):
    turn = state['current_game_turn']
    if ports.queues_empty() is not True:
        raise RuntimeError('Native command/deferred queues are not empty')
    _require_zero_blockers(ports.read_blockers(player_id, turn), player_id, turn)
    _require_manual_gate(ports.manual_endturn_gate(player_id, turn), player_id, turn)
    if ports.queues_empty() is not True:
        raise RuntimeError('Gate read unexpectedly left pending work')

def _decide_then_reobserve(ports, state, player_id: int):
    turn = state['current_game_turn']
    ready = ports.readiness(state, player_id)
    _state(ready, turn=turn, local=player_id, active=player_id, complete=True)
    if ports.local_observer() != player_id:
        raise RuntimeError('Turn-readiness update changed the native observer')
    terminal = _observe_victory_boundary(ports, ready, f'after-player-{player_id}-readiness', state)
    if terminal is not None:
        return terminal
    ports.resolve_development(player_id, action_profile=ACTION_PROFILE, production_policy=PRODUCTION_POLICY, policy_chosen_by='python-diagnostic')
    fresh = ports.observe()
    _state(fresh, turn=turn, local=player_id, active=player_id, complete=True)
    if ports.local_observer() != player_id:
        raise RuntimeError('Fresh post-choice observation changed the native observer')
    terminal = _observe_victory_boundary(ports, fresh, f'after-player-{player_id}-decision-phase', state)
    if terminal is not None:
        return terminal
    _before_endturn(ports, fresh, player_id)
    return fresh

def _observe_victory_boundary(ports, state, phase, before, transition=None):
    """Read the official current result at one published, quiescent boundary."""
    if ports.queues_empty() is not True:
        raise RuntimeError('Native queues are not empty at the victory observation boundary')
    reader = getattr(ports, 'observe_victory_boundary', None)
    if not callable(reader):
        raise RuntimeError('Required official victory-boundary reader is unavailable')
    try:
        result = reader(state['local_player'], state['current_game_turn'], phase)
    except BaseException as error:
        from civ6_host.runtime.native.native_victory_diagnostic import NativeVictoryReached
        if type(error) is not NativeVictoryReached:
            raise
        if ports.queues_empty() is not True:
            raise RuntimeError('Native victory result left queued work') from error
        return {'terminal_result_observed': True, 'terminal_phase': phase, 'terminal_result': error.result, 'before': before, 'after': state, 'native_turn_transition': transition, 'round_completed': transition is not None, 'action_profile': ACTION_PROFILE, 'production_policy': PRODUCTION_POLICY, 'policy_selected_by': 'python-diagnostic', 'native_flags_written': False, 'full_exe_scheduler_reproduced': False, 'complete_game': False, 'eligible_for_training': False, 'training_ready': False, 'learner_transport': False, 'post_terminal_update_called': False}
    if ports.queues_empty() is not True:
        raise RuntimeError('Victory observation read left queued native work')
    if type(result) is not dict or type(result.get('episode_terminated')) is not bool:
        raise RuntimeError('Official victory reader returned a malformed result')
    if result['episode_terminated'] is True:
        raise RuntimeError('Terminal victory policy returned without its required stop exception')
    return None

def run_one_round(ports, *, start_turn=2, _late_round_chain=False, _previctory_readiness=False):
    """Run an injected 2→3, retained 115/118/121/150/182 one-round profile; never synthesize a native action.

    Required port methods are exercised in the tests. The retained native adapter
    binds them to the already retained loaded owner/prefix/publisher.
    """
    if type(_late_round_chain) is not bool:
        raise ValueError('Late-chain selector must be an exact bool')
    if type(_previctory_readiness) is not bool:
        raise ValueError('Previctory readiness selector must be an exact bool')
    if _late_round_chain:
        if _previctory_readiness:
            raise ValueError('Previctory readiness cannot be combined with late-round chaining')
        initial = getattr(ports, 'late_round_initial_turn', lambda: None)()
        if type(initial) is not int or initial not in (115, 118, 150) or type(start_turn) is not int or (not initial <= start_turn < initial + 32) or (getattr(ports, 'late_round_mode', lambda: False)() is not True):
            raise ValueError('Late-round chain requires a selected115/118/150 initial turn and at most32 rounds')
    elif type(start_turn) is not int or start_turn not in (2, 12, 115, 118, 121, 150, 182):
        raise ValueError('Only exact start turns 2, 115, 118, 121, 150 and 182 are admitted outside the bounded late-chain mode')
    if _previctory_readiness and start_turn != 12:
        raise ValueError('The bounded previctory readiness update is only admitted for turn 12→13')
    end_turn = start_turn + 1
    if ports.load_phase() != 'post160-observed-awaiting-controlled-stop':
        raise RuntimeError('Resume requires the validated Load+facades+160 phase')
    if ports.prefix_action_profile() != 'initial-view':
        raise RuntimeError('Loaded prefix must retain its load-only initial-view profile')
    if ports.configuration_readback_verified() is not True:
        raise RuntimeError('Loaded configuration readback is not verified')
    if ports.publisher_ready() is not True:
        raise RuntimeError('Retained public cache publisher/facades are unavailable')
    selected = ports.select_python_policy(ACTION_PROFILE, PRODUCTION_POLICY)
    if selected != (ACTION_PROFILE, PRODUCTION_POLICY):
        raise RuntimeError('Resume action profile is not the fixed Python diagnostic policy')
    if ports.native_flags_written() is not False:
        raise RuntimeError('This orchestration must not write native decision flags')
    publisher = ports.publisher()
    if publisher is None or not callable(getattr(publisher, 'publish', None)):
        raise RuntimeError('The retained publisher object is unavailable')

    def publish_same():
        if ports.publisher() is not publisher:
            raise RuntimeError('The retained player-view publisher identity changed')
        publisher.publish()
        if ports.publisher() is not publisher:
            raise RuntimeError('Publication replaced the retained player-view publisher')

    def deliver_request(pid):
        if type(pid) is not int or pid not in (0, 1):
            raise RuntimeError('END_TURN player must be an exact configured player id')
        ports.request_endturn(pid)
        if ports.pending_actions() != 1:
            raise RuntimeError('END_TURN did not create exactly one native command')
        ports.deliver_one()
        if ports.pending_actions() != 0:
            raise RuntimeError('Native command delivery left an unexpected archive')
        ports.drain()
        if ports.queues_empty() is not True:
            raise RuntimeError('Native action delivery left deferred work')
    publish_same()
    initial = ports.observe()
    _state(initial, turn=start_turn, local=0, active=0, complete=False)
    if ports.local_observer() != 0:
        raise RuntimeError('Loaded observer is not player 0')
    terminal = _observe_victory_boundary(ports, initial, 'after-load-initial-publication', initial)
    if terminal is not None:
        return terminal
    p0 = _decide_then_reobserve(ports, initial, 0)
    if type(p0) is dict and p0.get('terminal_result_observed') is True:
        return p0
    deliver_request(0)
    publish_same()
    handoff = ports.observe()
    _state(handoff, turn=start_turn, local=1, active=1, complete=False)
    if ports.local_observer() != 1:
        raise RuntimeError('Native handoff did not switch observer to player 1')
    terminal = _observe_victory_boundary(ports, handoff, 'after-player-0-endturn-handoff', handoff)
    if terminal is not None:
        return terminal
    p1 = _decide_then_reobserve(ports, handoff, 1)
    if type(p1) is dict and p1.get('terminal_result_observed') is True:
        return p1
    deliver_request(1)
    publish_same()
    ended = ports.wait_for_completed_round_echo(start_turn)
    _state(ended, turn=start_turn, local=1, active=None, complete=None)
    if ports.local_observer() != 1:
        raise RuntimeError('AI wait changed the observed native perspective')
    if ports.pending_actions() != 1 or ports.completed_round_echo_valid(1, start_turn) is not True:
        raise RuntimeError('AI completion is not backed by one validated native echo')
    ports.deliver_completed_round_echo(1)
    if ports.pending_actions() != 0:
        raise RuntimeError('Native completion echo delivery left an archive')
    ports.drain()
    if ports.queues_empty() is not True:
        raise RuntimeError('Completion echo left deferred work')
    publish_same()
    terminal = _observe_victory_boundary(ports, ended, 'after-completed-echo-before-next-update', initial)
    if terminal is not None:
        return terminal
    ports.update_game_once()
    ports.drain()
    if ports.queues_empty() is not True:
        raise RuntimeError('Final native update left deferred work')
    publish_same()
    final = ports.observe()
    terminal_candidate = _final_publication_state(final, turn=end_turn)
    if ports.local_observer() != 0:
        raise RuntimeError('Completed round did not return to player 0 observer')
    terminal = _observe_victory_boundary(ports, final, 'after-final-update-publication', initial, transition=[start_turn, end_turn])
    if terminal_candidate is True or (_previctory_readiness and terminal is not None):
        _require_source_pinned_terminal(terminal, turn=end_turn)
    if terminal is not None:
        return terminal
    if _previctory_readiness:
        if terminal_candidate is True:
            raise RuntimeError('Previctory readiness cannot follow a complete final phase')
        ports.update_game_once()
        ports.drain()
        if ports.queues_empty() is not True:
            raise RuntimeError('Previctory readiness update left deferred work')
        publish_same()
        ready = ports.observe()
        _state(ready, turn=end_turn, local=0, active=0, complete=True)
        if ports.local_observer() != 0:
            raise RuntimeError('Previctory readiness update changed the native observer')
        terminal = _observe_victory_boundary(ports, ready, 'after-next-turn-readiness-update', initial, transition=[start_turn, end_turn])
        if terminal is None:
            raise RuntimeError('Previctory readiness update produced no official terminal result')
        _require_source_pinned_terminal(terminal, turn=end_turn)
        return terminal
    if ports.queues_empty() is not True:
        raise RuntimeError('Resume finished with queued native work')
    return {'before': initial, 'after': final, 'native_turn_transition': [start_turn, end_turn], 'terminal_result_observed': False, 'action_profile': ACTION_PROFILE, 'production_policy': PRODUCTION_POLICY, 'policy_selected_by': 'python-diagnostic', 'native_flags_written': False, 'full_exe_scheduler_reproduced': False, 'complete_game': False, 'training_ready': False, 'learner_transport': False}

"""Persistent LAN worker over the shared official loader and action adapters."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
from civ6_host.runtime.import_boundary import enable as _enable
_enable()

import json
import os
import sys
from time import perf_counter


def _save_before_close(owner, protocol, closure, path, request, expansion, emit):
    if protocol.last_outcome['terminated']:
        # The checkpoint writer requires a live decision boundary.
        emit('native_checkpoint_skipped', reason='official_native_victory',
             sequence=request['sequence'])
        return
    pid = request['player_id']
    if expansion:
        from civ6_host.runtime import xp1_session_checkpoint, xp1_session_view
        _, observation, decisions = xp1_session_view.read(owner, pid, protocol.sequence)
        xp1_session_checkpoint.save(owner, observation, decisions, closure, path, request['sequence'])
    else:
        from civ6_host.runtime import network_checkpoint, network_owner
        observation, decisions = network_owner.read(owner, protocol.sequence, protocol.rounds,
            round_limit=protocol.limit, player_id=pid)
        network_checkpoint.save(owner, observation, decisions, closure, path)


def _open_xp1(closure, path, emit, win):
    """Use the retained saved-Load graph, not another worker or scheduler."""
    started = perf_counter()
    from civ6_host.runtime.xp1_session_inputs import (
        SAVED_LOAD_CLOSURE_ENV, digest, saved_load_build_pins, _write_once)
    from civ6_host.runtime.provenance import verify_installation
    from civ6_host.runtime.captured_saved_load import select_load_closure
    selected=select_load_closure(closure)
    raw = _Path(path).read_bytes()
    if digest(raw) != os.environ.get(SAVED_LOAD_CLOSURE_ENV):
        raise ValueError('XP1 private session closure changed')
    from civ6_host.runtime.capture_admission import XP2_LAUNCH_FIELD
    if selected.family == 'xp2-lan' and XP2_LAUNCH_FIELD not in closure:
        raise ValueError('XP2 worker requires its prepared launch binding')
    from civ6_host.runtime.session_limits import standard_lifetime_limit
    if (type(closure.get('lifetime_seconds')) is not int
            or not 1 <= closure['lifetime_seconds'] <= standard_lifetime_limit(closure.get('input_profile'))
            or closure.get('resume_checkpoint') is not None
            or 'unit_command' in closure
            or any(closure.get(name) is not True for name in (
                'raw_only_candidate', 'post160_candidate', 'publish_cache_candidate',
                'close_loaded_candidate', 'observe_player_candidate', 'unit_commands_candidate'))
            or any(closure.get(name, False) is not False for name in (
                'forced_endturn_diagnostic', 'production_queue_diagnostic',
                'multiturn_movement_diagnostic', 'movement_information_diagnostic',
                'unit_order_cancel_diagnostic', 'world_input_diagnostic'))):
        raise ValueError('XP1 network session has an unsupported capability request')
    from civ6_host.runtime.expansion_city_controls import requested
    city_flags=requested(closure)
    verify_installation()
    if _Path(sys.executable).resolve() != saved_load_build_pins({}, ui=True,
            core_sha256=selected.core_sha256):
        raise ValueError('XP1 session requires its exact native UI executable')
    from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
    from civ6_host.runtime.xp1_session_admission import bind
    emit('native_reset_timing', phase='saved_worker_admission_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    started = perf_counter()
    saved = SavedLoadOwner.open(closure, emit, win)
    run = _Path(path).resolve().parent
    emit('xp1_saved_raw_load_observed', receipt=_write_once(run/'raw-load-result.json', saved.raw_result))
    emit('native_reset_timing', phase='saved_raw_load_inclusive_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='inclusive; contains native Load phases')
    for method, filename, stage in (
            ('populate_caches', 'cache-result.json', 'xp1_saved_cache_observed'),
            ('postload', 'post160-result.json', 'xp1_saved_post160_sequence_returned'),
            ('publish', 'publication-result.json', 'xp1_saved_cache_publication_returned'),
            ('observe_initial', 'player-view-result.json', 'xp1_saved_player_view_returned')):
        before_stage = {'postload':'before_xp1_saved_post160_sequence',
                        'publish':'before_xp1_saved_cache_publication',
                        'observe_initial':'before_xp1_saved_player_view'}.get(method)
        if before_stage:
            emit(before_stage, public_runtime_admitted=False)
        started = perf_counter()
        result = getattr(saved, method)()
        emit(stage, receipt=_write_once(run/filename, result))
        emit('native_reset_timing', phase='saved_' + method + '_seconds',
             elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    started = perf_counter()
    saved.begin_commands()
    from civ6_host.runtime.expansion_city_controls import enable
    if city_flags[0]:enable(saved,closure)
    bind(saved)
    compare_initial = None
    if saved.inputs.checkpoint is not None:
        from civ6_host.runtime.network_checkpoint import prepare_owner
        compare_initial = prepare_owner(saved, saved.continuation.observation)
    emit('native_reset_timing', phase='saved_command_and_checkpoint_binding_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    return saved, compare_initial


def _execute_xp1(saved, action, player_id, sequence, path):
    """Requery the native family immediately before the retained command call."""
    from civ6_host.runtime.xp1_session_view import read
    from civ6_host.runtime.xp1_session_inputs import _write_once
    from copy import deepcopy
    placement_action = action['kind'] in ('production_placement','production_resume')
    production_action = action['kind'] == 'production' or placement_action
    prior_production = (deepcopy(saved.continuation.explicit_production_snapshot)
                        if production_action else None)
    prior_placements = deepcopy(saved.continuation.explicit_placements) if placement_action else None
    queue_action = action['kind'] in ('queue_append', 'queue_remove', 'queue_swap')
    prior_queues = deepcopy(saved.continuation.explicit_production_queues) if queue_action else None
    city_action=action['kind'] in ('city_focus','city_citizen')
    if city_action:
        from civ6_host.runtime.expansion_city_controls import catalogue_snapshot
        prior_city=catalogue_snapshot(saved)
    shot_action = action['kind'] in ('city_range_attack', 'district_range_attack')
    prior_shot = ((deepcopy(saved.continuation.explicit_ranged_shots[action['kind']]),
                   deepcopy(saved.continuation.explicit_city_shot_defenses))
                  if shot_action else None)
    attack_action = action['kind']=='unit_attack'
    from civ6_host.contracts.capability_unit_attacks import project_cities
    shape=saved.continuation.observation
    prior_combat = ((deepcopy(saved.continuation.explicit_combat_units),
                     project_cities(saved.continuation.explicit_combat_cities,shape['width'],shape['height']))
                    if attack_action else None)
    from civ6_host.contracts.capability_world_input import WORLD_KINDS
    prior_world=(deepcopy(saved.continuation.explicit_world_input) if action['kind'] in WORLD_KINDS else None)
    _, observed, decisions = read(saved, player_id, sequence)
    if action not in [row['action'] for row in decisions['candidates']]:
        return dict(status='refused', reason='native_action_no_longer_available',
                    requested_action=action)
    if (production_action
            and prior_production != saved.continuation.explicit_production_snapshot):
        return dict(status='refused', reason='native_production_state_changed', requested_action=action)
    if placement_action and prior_placements != saved.continuation.explicit_placements:
        return dict(status='refused',reason='native_placement_state_changed',requested_action=action)
    if action['kind'] in WORLD_KINDS and prior_world!=saved.continuation.explicit_world_input:
        return dict(status='refused',reason='native_world_input_state_changed',requested_action=action)
    if queue_action and prior_queues != saved.continuation.explicit_production_queues:
        return dict(status='refused',reason='native_production_queue_state_changed',requested_action=action)
    if attack_action and prior_combat != (saved.continuation.explicit_combat_units,
             project_cities(saved.continuation.explicit_combat_cities,observed['width'],observed['height'])):
        return dict(status='refused',reason='native_combat_state_changed',requested_action=action)
    if shot_action and prior_shot != (saved.continuation.explicit_ranged_shots[action['kind']],
                                      saved.continuation.explicit_city_shot_defenses):
        return dict(status='refused', reason='native_ranged_shot_state_changed', requested_action=action)
    if city_action and prior_city!=catalogue_snapshot(saved):
        return dict(status='refused',reason='native_city_control_state_changed',requested_action=action)
    # The command adapter retains its own current public before-state. A query
    # cannot move the world; detect unexpected advancement before dispatch.
    if saved.continuation.observation != observed:
        raise RuntimeError('XP1 command before-state changed outside the retained continuation')
    saved.emit('before_xp1_saved_unit_commands', protocol_sequence=sequence+1,
               public_runtime_admitted=False)
    result = saved.execute(action)
    if result['action'] != action:
        raise RuntimeError('XP1 native command receipt identifies another choice')
    saved.emit('xp1_saved_unit_commands_returned',
        protocol_sequence=sequence+1,
        receipt=_write_once(_Path(path).resolve().parent/
            ('command-result-' + str(sequence+1) + '.json'), result))
    if action['kind'] in ('end_turn','force_end_turn','unready_turn'):
        if result['effect']['requested_action']!=action:
            raise RuntimeError('XP1 turn effect identifies another request')
        return result['effect']
    if action['kind'] in WORLD_KINDS:
        effect=result['effect']
        if effect['status'] not in ('completed','refused'):
            raise RuntimeError('XP1 world-input result has an unqualified status')
        return dict(status=effect['status'],reason=effect['refusal_code'],requested_action=action)
    if action['kind']=='unit_order':
        effect=result['effect']
        if effect['status']!='completed' or effect['receipt']['action']!=action:
            raise RuntimeError('XP1 unit-order result has no matching native delivery')
        return dict(status='completed',reason=None,requested_action=action)
    if queue_action or placement_action or attack_action or action['kind'] in ('city_focus','city_citizen'):
        effect=result['effect']
        if effect['status']!='completed' or effect['receipt']['action']!=action:
            raise RuntimeError('XP1 production queue has no matching native effect')
        return dict(status='completed',reason=None,requested_action=action)
    return dict(status='completed', reason=None, requested_action=action)


def _advance_xp1(saved,sequence,path):
    from civ6_host.runtime.xp1_session_inputs import _write_once
    saved.emit('before_xp1_saved_turn_update',protocol_sequence=sequence+1)
    result=saved.advance()
    if result['action'] is not None or result['game_update_called'] is not True:
        raise RuntimeError('XP1 poll did not return the explicit native update receipt')
    saved.emit('xp1_saved_turn_update_returned',protocol_sequence=sequence+1,
        receipt=_write_once(_Path(path).resolve().parent/('update-result-'+str(sequence+1)+'.json'),result))


def main(path):
    from civ6_host.runtime.native.native_probe import Windows
    from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
    win = Windows()
    win.kernel.SetErrorMode(1 | 2 | 32768)
    if sys.stdin.buffer.readline(16) != b'go\n':
        return 2

    trace_records = 0
    trace_seconds = 0.0

    def emit(stage, **fields):
        nonlocal trace_records, trace_seconds
        started = perf_counter()
        print(json.dumps(dict(stage=stage, **fields)), flush=True)
        trace_records += 1
        trace_seconds += perf_counter() - started

    try:
        from civ6_host.runtime.resource_resolution import resolve_path
        from civ6_host.runtime.network_protocol import (
            NetworkProtocol, SCHEMA, CLOSURE_SCHEMA, validate_network_response)
        from civ6_host.runtime.native.native_saved_session import (
            validate_episode_budget_closure, stdout_limit_ceiling)
        closure = json.loads(resolve_path(_Path(path)).read_bytes())
        budget = validate_episode_budget_closure(closure)
        xp1 = closure.get('input_profile') in ('xp1-lan','xp2-lan')
        from civ6_host.runtime.session_limits import standard_lifetime_limit
        if (closure.get('schema') != CLOSURE_SCHEMA or closure.get('input_profile') not in ('lan', 'xp1-lan','xp2-lan')
                or type(closure.get('lifetime_seconds')) is not int
                or not 1 <= closure['lifetime_seconds'] <= (600 if budget else standard_lifetime_limit(closure.get('input_profile')))
                or type(closure.get('stdout_limit_bytes')) is not int
                or not 1048576 <= closure['stdout_limit_bytes'] <= stdout_limit_ceiling(budget)
                or type(closure.get('rounds')) is not int
                or not 1 <= closure['rounds'] <= NetworkProtocol.max_round_limit
                or closure.get('privileged_critic_diagnostic', False) is not False
                or type(closure.get('checkpoint_on_close', False)) is not bool
                or closure.get('official_bundle') is None):
            raise ValueError('Unsupported bounded LAN closure')
        if not xp1:
            from civ6_host.runtime.captured_saved_load import validate_closure_profile
            validate_closure_profile(closure)
        display_formatter = None
        if 'public_display_source' in closure:
            from civ6_host.runtime.player_display_toppanel import (
                OwnedNativeTopPanelFormatter, require_display_closure)
            require_display_closure(closure)
        from civ6_host.runtime.workers.run_official_postload909 import open_official_backend
        from civ6_host.runtime.native.native_official_postload import observe_saved_player
        from civ6_host.runtime.native.native_episode_identity import require_episode
        from civ6_host.runtime.native.native_saved_session_protocol import outcome
        from civ6_host.runtime.native.native_victory_diagnostic import (
            observe_after_round_echo, NativeVictoryReached)
        from civ6_host.runtime import network_owner

        compare_initial = None
        if xp1:
            from civ6_host.runtime import xp1_session_view, xp1_session_result
            owner, compare_initial = _open_xp1(closure, path, emit, win)
            local_player = owner.network_reference['state']['player_id']
            protocol = NetworkProtocol(require_episode(owner.prefix), closure['nonce'],
                round_limit=closure['rounds'], initial_turn=closure['initial_turn'],
                core_sha256=owner.backend.load_abi.core_sha256)
        else:
            owner = open_official_backend(closure, emit, win)
            initial = observe_saved_player(owner)
            session, compare_initial = network_owner.prepare(owner, initial)
            local_player = session['local_player_id']
            protocol = NetworkProtocol(require_episode(owner.prefix), closure['nonce'],
                round_limit=closure['rounds'], initial_turn=closure['initial_turn'])
            owner.explicit_initial_turn = initial['turn']
            owner.explicit_round_limit = protocol.limit
            for flag in ('forced_endturn_diagnostic', 'production_queue_diagnostic',
                         'multiturn_movement_diagnostic', 'movement_information_diagnostic',
                         'unit_order_cancel_diagnostic', 'world_input_diagnostic',
                         'city_focus_diagnostic', 'city_management_diagnostic'):
                value = closure.get(flag, False)
                if type(value) is not bool:
                    raise ValueError('Exact diagnostic option required: ' + flag)
                setattr(owner, flag, value)
            if owner.city_management_diagnostic and not owner.city_focus_diagnostic:
                raise ValueError('City management requires the complete focus group')

        if 'public_display_source' in closure:
            display_formatter = OwnedNativeTopPanelFormatter(owner, protocol)

        def reply(operation, player_id, sequence, command, request=None,
                  command_seconds=None, trace_before=None):
            started = perf_counter()
            if xp1:
                native = xp1_session_result.read(owner, player_id=player_id)
                rounds = native['current_game_turn'] - protocol.initial_turn
            else:
                session = network_owner.state(owner)
                from civ6_host.runtime.network_dialogue import control
                control(owner)
                try:
                    native = observe_after_round_echo(owner.prefix, player_id, session['turn'])
                except NativeVictoryReached as exc:
                    native = exc.result
                rounds = session['turn'] - protocol.initial_turn
            result = outcome(native, rounds, protocol.limit,
                closed=operation == 'close', maximum=protocol.max_round_limit)
            if native['episode_terminated']:
                observation, decisions = None, None
                if xp1:
                    session = xp1_session_view.state(owner)
            elif xp1:
                session, observation, decisions = xp1_session_view.read(owner, player_id, sequence,
                    actions_closed=result['terminated'] or result['truncated'],
                    specialist_diagnostic=operation!='close')
            else:
                observation, decisions = network_owner.read(owner, sequence, rounds,
                    closed=result['terminated'] or result['truncated'],
                    round_limit=protocol.limit, player_id=player_id)
            view_seconds = perf_counter() - started
            started = perf_counter()
            response = dict(stage='official_session_response', schema=SCHEMA,
                nonce=protocol.nonce, episode_id=protocol.identity.episode_id,
                game_generation=protocol.identity.game_generation, sequence=sequence,
                operation=operation, observation=observation, rounds=rounds,
                outcome=result, decisions=decisions, command_result=command,
                session=session, applied_action=command['requested_action']
                    if command['status'] == 'completed' else None,
                automatic_choices_applied=False, action_interface_complete=False,
                strategic_training_ready=False)
            validate_network_response(response, protocol, operation, request=request)
            if operation == 'reset' and owner.inputs.checkpoint is not None:
                if compare_initial is None:
                    raise RuntimeError('Missing checkpoint comparator for restored decision boundary')
                compare_initial(observation, decisions)
            if operation == 'reset' and closure['input_profile'] == 'xp2-lan':
                from civ6_host.runtime.xp2_end_turn_readback import SOURCE, read
                end_turn = read(owner, player_id, session['turn'])
                emit('xp2_saved_end_turn_observed', episode_id=protocol.identity.episode_id,
                     game_generation=protocol.identity.game_generation, sequence=sequence,
                     player_id=player_id, turn=session['turn'], end_turn=end_turn,
                     source_sha256=SOURCE[1], actor_channel=False)
            if display_formatter is not None and observation is not None and not result['terminated']:
                from civ6_host.runtime.player_display_toppanel import emit_display_readback
                emit_display_readback(display_formatter, owner, response, request, emit)
            if operation == 'close' and xp1:
                from civ6_host.runtime.xp1_session_inputs import _write_once
                emit('before_xp1_saved_loaded_close', completed_phase='unit_commands',
                     public_runtime_admitted=False)
                closed = owner.close()
                emit('xp1_saved_loaded_close_returned',
                    receipt=_write_once(_Path(path).resolve().parent/'loaded-lifetime-result.json', closed))
                # Reply describes the final state read before Destroy. No native
                # reader is called after it, and no success precedes teardown.
            if request is not None:
                protocol.commit_reply(request, response)
            protocol.accept_response(response)
            payload = json.dumps(response)
            if xp1 and operation == 'reset':
                emit('native_reset_timing', phase='saved_initial_response_seconds',
                     elapsed_seconds=view_seconds + (perf_counter() - started),
                     timing_scope='non-overlapping stage; includes observation and checkpoint comparison')
            if command_seconds is not None:
                records_before, seconds_before = trace_before
                emit('native_lan_response_timing', operation=operation, sequence=sequence,
                     command_seconds=command_seconds, view_seconds=view_seconds,
                     response_seconds=perf_counter() - started,
                     worker_trace_records=trace_records - records_before,
                     worker_trace_emit_seconds=trace_seconds - seconds_before,
                     worker_trace_emit_included_in_stage_times=True)
            print(payload, flush=True)

        none = dict(status='none', reason=None, requested_action=None)
        reply('reset', local_player, 0, none)
        compare_initial = None
        for _ in range(protocol.max_commands):
            line = sys.stdin.buffer.readline(4097)
            if not line or len(line) > 4096 or not line.endswith(b'\n'):
                raise ValueError('Missing or oversized LAN command')
            request = json.loads(line)
            operation = protocol.validate(request)
            pid = request['player_id']
            command = none
            trace_before = trace_records, trace_seconds
            started = perf_counter()
            if operation == 'act':
                if xp1:
                    command = _execute_xp1(owner, protocol.selected(request), pid,
                                          protocol.sequence, path)
                else:
                    command = network_owner.execute(owner, protocol.selected(request),
                        player_id=pid, sequence=protocol.sequence,
                        rounds=protocol.rounds, round_limit=protocol.limit)
            elif operation == 'poll':
                if xp1:
                    _advance_xp1(owner,protocol.sequence,path)
                else:
                    from civ6_host.runtime.network_turns import advance
                    advance(owner)
            elif operation == 'close' and closure.get('checkpoint_on_close', False):
                _save_before_close(owner, protocol, closure, path, request, xp1, emit)
            reply(operation, pid, request['sequence'], command, request,
                  command_seconds=perf_counter() - started if operation in ('act', 'poll') else None,
                  trace_before=trace_before)
            if operation == 'close':
                emit('official_session_controlled_stop', normal_destroy_called=xp1,
                     strategic_training_ready=False)
                terminate_worker(90)
        raise ValueError('Bounded LAN command budget exhausted')
    except BaseException as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        emit('official_session_refused', error=repr(exc), cleanup_guessed=False,
             strategic_training_ready=False)
        terminate_worker(89)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Expected private closure path')
    raise SystemExit(main(sys.argv[1]))

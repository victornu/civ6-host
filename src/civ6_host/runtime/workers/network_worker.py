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
from contextlib import nullcontext


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
    from civ6_host.runtime.xp2_world_war import source_pin
    war_source_sha256 = source_pin(closure.get('war_source_sha256'), selected.family)
    governors_diagnostic = closure.get('governors_diagnostic', False)
    initial_diplomacy = closure.get('diplomacy_overview_diagnostic', False)
    trade_diagnostic = closure.get('trade_diagnostic', False)
    standard_trade = closure.get('standard_trade', False)
    unit_formations = closure.get('unit_formations', False)
    stock_dedications = closure.get('stock_dedications', False)
    espionage_diagnostic = closure.get('espionage_diagnostic', False)
    world_congress_diagnostic = closure.get('world_congress_diagnostic', False)
    world_congress_review_diagnostic = closure.get('world_congress_review_diagnostic', False)
    trade_overview_ui_selected = closure.get('trade_overview_ui_selected', False)
    if (type(initial_diplomacy) is not bool or initial_diplomacy and (
            selected.family != 'xp2-lan' or governors_diagnostic is not True
            or war_source_sha256 is None or 'execution_image' not in closure)):
        raise ValueError('Initial diplomacy requires the exact current XP2 v33 closure')
    if type(trade_diagnostic) is not bool or trade_diagnostic and not initial_diplomacy:
        raise ValueError('Trade requires the complete current XP2 v33 closure')
    if (type(standard_trade) is not bool or standard_trade and (
            selected.family != 'xp2-lan' or trade_diagnostic or governors_diagnostic
            or 'execution_image' not in closure)):
        raise ValueError('Standard trade requires the exact stock XP2 closure')
    if type(unit_formations) is not bool or unit_formations and not standard_trade:
        raise ValueError('Unit formations require the exact stock XP2 closure')
    if type(stock_dedications) is not bool or stock_dedications and not unit_formations:
        raise ValueError('Dedications require the exact stock XP2 v2 closure')
    if type(espionage_diagnostic) is not bool or espionage_diagnostic and not trade_diagnostic:
        raise ValueError('Espionage requires the complete current XP2 trade closure')
    if (type(world_congress_diagnostic) is not bool or world_congress_diagnostic and not (
            espionage_diagnostic or stock_dedications and world_congress_review_diagnostic is True)):
        raise ValueError('World Congress requires the complete XP2 BBG or stock review closure')
    if (type(world_congress_review_diagnostic) is not bool
            or world_congress_review_diagnostic and world_congress_diagnostic is not True):
        raise ValueError('Congress review requires its exact Boolean Congress closure')
    if type(governors_diagnostic) is not bool:
        raise ValueError('Exact governors diagnostic option required')
    if governors_diagnostic:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        if selected.family != 'xp2-lan' or selected.core_sha256 != XP2_CORE_SHA256:
            raise ValueError('Governors diagnostic requires the XP2 LAN core')
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
    execution_options = {}
    if 'execution_image' in closure:
        from civ6_host.runtime.execution_images import from_identity
        execution_options['execution_image'] = from_identity(closure['execution_image'])
    if trade_diagnostic:
        from civ6_host.runtime import xp2_bbg_trade_feedback, xp2_trade
        from civ6_host.runtime.resource_resolution import resolve_path
        from civ6_host.runtime.captured_session_profile import require_bbg_capture
        require_bbg_capture(selected.reference, **execution_options)
        for module in (xp2_trade, xp2_bbg_trade_feedback):
            for source, expected in module.source_dependencies(**execution_options).items():
                if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                    raise ValueError('Trade source is outside the worker closure')
    if standard_trade:
        from civ6_host.runtime import xp2_trade
        from civ6_host.runtime.resource_resolution import resolve_path
        dependencies = xp2_trade.standard_source_dependencies(selected.reference,
            core_sha256=selected.core_sha256, **execution_options)
        for source, expected in dependencies.items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Standard trade source is outside the worker closure')
    if unit_formations:
        from civ6_host.runtime import xp2_unit_formations
        dependencies = xp2_unit_formations.source_dependencies(selected.reference, **execution_options)
        for source, expected in dependencies.items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Unit formation source is outside the worker closure')
    if stock_dedications:
        from civ6_host.runtime import xp2_dedications
        dependencies = xp2_dedications.source_dependencies(selected.reference, **execution_options)
        for source, expected in dependencies.items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Dedication source is outside the worker closure')
    if espionage_diagnostic:
        from civ6_host.runtime import xp2_espionage
        from civ6_host.runtime.resource_resolution import resolve_path
        for source, expected in xp2_espionage.source_dependencies(**execution_options).items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Espionage source is outside the worker closure')
    if world_congress_diagnostic:
        from civ6_host.runtime.xp2_world_congress_source import source_dependencies
        from civ6_host.runtime.resource_resolution import resolve_path
        for source, expected in source_dependencies(**execution_options).items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Congress source is outside the worker closure')
    if world_congress_review_diagnostic:
        from civ6_host.runtime.xp2_world_congress_review import source_dependencies
        from civ6_host.runtime.resource_resolution import resolve_path
        for source, expected in source_dependencies(**execution_options).items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Congress review source is outside the worker closure')
    if type(trade_overview_ui_selected) is not bool or trade_overview_ui_selected and not world_congress_review_diagnostic:
        raise ValueError('Trade overview requires the exact complete XP2 public decision closure')
    if trade_overview_ui_selected:
        from civ6_host.runtime import xp2_trade_overview
        for source, expected in xp2_trade_overview.source_dependencies(
                selected.reference, execution_options.get('execution_image')).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Trade overview source is outside the worker closure')
    from civ6_host.runtime import xp2_captured_city
    stock_captured_city = standard_trade and xp2_captured_city.supports_stock(
        selected.reference, execution_options.get('execution_image'))
    captured_city_enabled = stock_captured_city or (trade_diagnostic and trade_overview_ui_selected)
    if captured_city_enabled:
        for source, expected in xp2_captured_city.source_dependencies(
                **execution_options, stock=stock_captured_city).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Captured-city source is outside the worker closure')
    if _Path(sys.executable).resolve() != saved_load_build_pins({}, ui=True,
            core_sha256=selected.core_sha256, official_bundle=selected.reference, **execution_options):
        raise ValueError('XP1 session requires its exact native UI executable')
    from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
    from civ6_host.runtime.xp1_session_admission import bind
    emit('native_reset_timing', phase='saved_worker_admission_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    started = perf_counter()
    saved = SavedLoadOwner.open(closure, emit, win)
    saved.governors_diagnostic = governors_diagnostic
    saved.diplomacy_overview_diagnostic = initial_diplomacy
    saved.trade_diagnostic = trade_diagnostic
    saved.standard_trade = standard_trade
    saved.unit_formations = unit_formations
    saved.stock_dedications = stock_dedications
    saved.espionage_diagnostic = espionage_diagnostic
    saved.world_congress_diagnostic = world_congress_diagnostic
    saved.world_congress_review_diagnostic = world_congress_review_diagnostic
    saved.trade_overview_ui_selected = trade_overview_ui_selected
    saved.war_source_sha256 = war_source_sha256
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
    if trade_diagnostic:
        xp2_bbg_trade_feedback.bind(saved)
    if captured_city_enabled:
        xp2_captured_city.bind(saved)
    if trade_overview_ui_selected or standard_trade:
        from civ6_host.runtime.xp2_trade_overview import bind_civic_hook
        bind_civic_hook(saved)
    compare_initial = None
    if saved.inputs.checkpoint is not None:
        from civ6_host.runtime.network_checkpoint import prepare_owner
        compare_initial = prepare_owner(saved, saved.continuation.observation)
    emit('native_reset_timing', phase='saved_command_and_checkpoint_binding_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    return saved, compare_initial


def _emit_native_load_profile(owner, protocol, player_id, emit):
    """Emit a captured Load profile only after the actual episode exists."""
    captured = getattr(owner.backend, '_command_load_profile', None)
    if captured is None:
        return False
    failed = False
    try:
        expected = protocol.identity
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        if (owner.continuation is None
                or type(owner.continuation) is not SavedContinuation
                or owner.continuation.identity is not expected
                or type(captured) is not dict
                or set(captured) != {'profiler', 'wall_seconds', 'callback_failed', 'core_identity'}
                or captured['callback_failed'] is not False):
            raise RuntimeError('Captured native Load profile is not bound to a successful episode')
        from civ6_host.runtime.command_profiling import CommandProfiler
        profiler = CommandProfiler(enabled=True, emit=emit, identity=expected)
        profiler.emit_captured(captured['profiler'], phase='load', operation='reset',
            sequence=0, player_id=player_id, wall_seconds=captured['wall_seconds'],
            core_identity=captured['core_identity'])
        return True
    except BaseException:
        failed = True
        raise
    finally:
        try:
            delattr(owner.backend, '_command_load_profile')
        except BaseException:
            if not failed:
                raise


def _execute_xp1(saved, action, player_id, sequence, path):
    """Requery the native family immediately before the retained command call."""
    context = getattr(saved, '_xp2_diplomacy', None)
    if context is not None:
        if action.get('kind') != 'diplomacy_response':
            return dict(status='refused', reason='xp2_diplomacy_response_pending',
                        requested_action=action)
        from civ6_host.runtime.xp2_diplomacy import respond
        effect = respond(saved, action, saved.continuation.observation)
        if (type(effect) is not dict or effect.get('requested_action') != action
                or effect.get('status') not in ('completed', 'refused')):
            raise RuntimeError('Saved diplomacy response returned another action or status')
        reason = effect.get('reason')
        if effect['status'] == 'refused' and reason is None:
            reason = effect.get('refusal_code')
        if reason is not None and type(reason) is not str:
            raise RuntimeError('Saved diplomacy response returned an invalid refusal reason')
        return dict(status=effect['status'], reason=reason, requested_action=action)
    if action.get('kind') == 'diplomacy_response':
        return dict(status='refused', reason='xp2_diplomacy_context_not_retained',
                    requested_action=action)
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from civ6_host.runtime.xp1_session_view import read, read_turn_preflight
    from civ6_host.runtime.xp1_session_inputs import _write_once
    from copy import deepcopy
    turn_action = action['kind'] in ('end_turn', 'force_end_turn', 'unready_turn')
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
    occupation_action = action['kind'] == 'resolve_captured_city'
    prior_occupation = (deepcopy(saved.continuation.explicit_captured_city)
                        if occupation_action else None)
    if attack_action:
        from civ6_host.contracts.capability_unit_attacks import project_cities
        shape = saved.continuation.observation
        prior_combat = (deepcopy(saved.continuation.explicit_combat_units),
                        project_cities(saved.continuation.explicit_combat_cities, shape['width'], shape['height']))
    from civ6_host.contracts.capability_world_input import WORLD_KINDS
    world_action = action['kind'] in WORLD_KINDS or action['kind'] == 'world_war_response'
    prior_world=(deepcopy(saved.continuation.explicit_world_input) if world_action else None)
    if (turn_action and saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
            and saved.continuation.world_input_prompts.get(player_id) is None):
        observed, available = read_turn_preflight(saved, player_id, action['kind'])
        available = available and action == {'kind': action['kind']}
    else:
        _, observed, decisions = read(saved, player_id, sequence)
        from civ6_host.contracts.world_congress import ACTION_FIELDS as CONGRESS_ACTION_FIELDS
        if action['kind'] in CONGRESS_ACTION_FIELDS:
            from civ6_host.runtime.xp2_world_congress import _admit
            try:
                _admit(decisions.get('world_congress'), action)
                available = True
            except (ValueError, TypeError):
                available = False
        elif action['kind'] == 'policies':
            from civ6_host.contracts.policies import choose, PolicyAssignmentUnavailable
            from civ6_host.contracts import network_turn as policy_contract
            policy_catalogue = decisions.get('policies')
            available = False
            if policy_catalogue is not None and policy_catalogue['reason'] == 'available':
                try:
                    chosen = choose(policy_catalogue['slots'],
                        [value & 0xffffffff for _, value in action['candidate']['assignments']],
                        player_id, observed['turn'], allow_relocation=(decisions['schema'] in
                            policy_contract.POLICY_RELOCATION_CAPABILITY_SCHEMAS),
                        allow_unchanged=(decisions['schema'] in policy_contract.POLICY_RECONFIRM_CAPABILITY_SCHEMAS))
                    available = chosen == action['candidate']
                except PolicyAssignmentUnavailable:
                    pass
        elif action['kind'] == 'confirm_dedications':
            from civ6_host.contracts import dedications, network_turn
            try:
                available = network_turn.select_capability(decisions, {
                    'decision_id': decisions['decision_id'],
                    'candidate_id': network_turn.digest(dedications.CANDIDATE),
                    'parameters': {'indices': action['indices']},
                }) == action
            except ValueError:
                available = False
        else:
            available = any(row['action'] == action for row in decisions['candidates'])
    if not available:
        return dict(status='refused', reason='native_action_no_longer_available',
                    requested_action=action)
    if (production_action
            and prior_production != saved.continuation.explicit_production_snapshot):
        return dict(status='refused', reason='native_production_state_changed', requested_action=action)
    if placement_action and prior_placements != saved.continuation.explicit_placements:
        return dict(status='refused',reason='native_placement_state_changed',requested_action=action)
    if world_action and prior_world!=saved.continuation.explicit_world_input:
        return dict(status='refused',reason='native_world_input_state_changed',requested_action=action)
    if queue_action and prior_queues != saved.continuation.explicit_production_queues:
        return dict(status='refused',reason='native_production_queue_state_changed',requested_action=action)
    if attack_action and prior_combat != (saved.continuation.explicit_combat_units,
             project_cities(saved.continuation.explicit_combat_cities,observed['width'],observed['height'])):
        return dict(status='refused',reason='native_combat_state_changed',requested_action=action)
    if occupation_action and prior_occupation != saved.continuation.explicit_captured_city:
        return dict(status='refused', reason='native_captured_city_state_changed', requested_action=action)
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
    retained = _retain_xp2_diplomacy_if_ready(saved)
    if action['kind'] == 'world_war_response' and result['effect'].get('status') == 'completed':
        if result['effect'].get('pending_statement_retained') is not True and retained:
            result['effect']['pending_statement_retained'] = True
    saved.emit('xp1_saved_unit_commands_returned',
        protocol_sequence=sequence+1,
        receipt=_write_once(_Path(path).resolve().parent/
            ('command-result-' + str(sequence+1) + '.json'), result))
    if getattr(saved, 'world_congress_diagnostic', False):
        effect = result.get('effect')
        partial = (type(effect) is dict and type(effect.get('receipt')) is dict
                   and effect['receipt'].get('partial_submission') is True)
        if partial:
            raise RuntimeError('Congress partial native journal retained; further model decisions refused')
        automatic = saved.advance_congress_empty(sequence + 1)
        if automatic is not None:
            saved.emit('xp2_congress_automatic_phase_returned', protocol_sequence=sequence+1,
                receipt=_write_once(_Path(path).resolve().parent/
                    ('congress-automatic-result-'+str(sequence+1)+'.json'), automatic))
    from civ6_host.contracts.world_congress import ACTION_FIELDS as CONGRESS_ACTION_FIELDS
    if action['kind'] in CONGRESS_ACTION_FIELDS:
        effect = result['effect']
        receipt = effect.get('receipt') if type(effect) is dict else None
        if (type(receipt) is not dict or receipt.get('action') != action
                or effect.get('status') not in ('completed', 'refused', 'pending')):
            raise RuntimeError('Congress confirmation returned a foreign result')
        if effect['status'] == 'completed' and (action['kind'] != 'congress_open'
                or receipt.get('local_presentation_completed') is not True
                or receipt.get('simulation_request_issued') is not False):
            raise RuntimeError('Congress native application has no qualified completion readback')
        if effect['status'] == 'pending' and receipt.get('native_archive_delivered') is not True:
            raise RuntimeError('Congress pending result lacks its native journal')
        return dict(status=effect['status'], reason=effect.get('refusal_code'), requested_action=action)
    if turn_action:
        if result['effect']['requested_action']!=action:
            raise RuntimeError('XP1 turn effect identifies another request')
        return result['effect']
    if action['kind'] == 'spy_completion_dismiss':
        effect = result['effect']
        receipt = effect.get('receipt') if type(effect) is dict else None
        if (type(receipt) is not dict or effect.get('status') != 'completed'
                or receipt.get('action') != action
                or receipt.get('local_presentation_completed') is not True
                or receipt.get('simulation_request_issued') is not False
                or receipt.get('native_archive_delivered') is not False):
            raise RuntimeError('Spy completion dismissal lacks its exact local presentation receipt')
        return dict(status='completed', reason=None, requested_action=action)
    from civ6_host.contracts.espionage import ACTION_FIELDS as ESPIONAGE_ACTION_FIELDS
    if action['kind'] in ESPIONAGE_ACTION_FIELDS or action['kind'] == 'spy_renew':
        effect = result['effect']
        statuses = (('completed', 'refused', 'pending') if action['kind'] == 'spy_renew'
                    else ('completed', 'refused', 'submitted', 'pending'))
        if (type(effect) is not dict
                or effect.get('status') not in statuses
                or type(effect.get('receipt')) is not dict
                or effect['receipt'].get('action') != action):
            raise RuntimeError('XP2 espionage did not return the requested native receipt')
        if effect['status'] != 'refused' and effect['receipt'].get('native_archive_delivered') is not True:
            raise RuntimeError('XP2 espionage accepted a choice without native archive delivery')
        if effect['status'] == 'completed' and effect['receipt'].get('native_effect_readback') is not True:
            raise RuntimeError('XP2 espionage completion lacks native effect readback')
        reason = effect.get('refusal_code')
        if reason is not None and type(reason) is not str:
            raise RuntimeError('XP2 espionage returned an invalid refusal reason')
        return dict(status=effect['status'], reason=reason, requested_action=action)
    from civ6_host.runtime.xp1_continuation import TRADE_KINDS
    if action['kind'] in TRADE_KINDS:
        effect = result['effect']
        if (effect['status'] != 'completed' or effect['receipt']['action'] != action
                or effect['receipt']['native_effect_readback'] is not True):
            raise RuntimeError('XP2 trade did not return the requested native effect')
        return dict(status='completed', reason=None, requested_action=action)
    if world_action or action['kind'] == 'diplomacy_initiate':
        effect=result['effect']
        if effect['status'] not in ('completed','refused'):
            raise RuntimeError('XP1 world-input result has an unqualified status')
        return dict(status=effect['status'],reason=effect['refusal_code'],requested_action=action)
    if action['kind'] == 'unit_formation':
        effect = result['effect']
        receipt = effect['receipt']
        if (effect['status'] not in ('completed', 'refused') or receipt['action'] != action
                or receipt['native_archive_delivered'] is not True
                or receipt['native_effect_readback'] is not (effect['status'] == 'completed')):
            raise RuntimeError('Formation result lacks the requested native readback')
        return dict(status=effect['status'], reason=effect['refusal_code'], requested_action=action)
    if action['kind'] == 'confirm_dedications':
        effect = result['effect']
        receipt = effect['receipt']
        if (effect['status'] != 'completed' or receipt['action'] != action
                or receipt['native_archive_delivered'] is not True
                or receipt['native_effect_readback'] is not True
                or len(receipt['native_archive_sha256']) != len(action['indices'])):
            raise RuntimeError('Dedication confirmation lacks exact native archive and effect readback')
        return dict(status='completed', reason=None, requested_action=action)
    if action['kind']=='unit_order':
        effect=result['effect']
        if effect['status']!='completed' or effect['receipt']['action']!=action:
            raise RuntimeError('XP1 unit-order result has no matching native delivery')
        return dict(status='completed',reason=None,requested_action=action)
    if attack_action:
        from civ6_host.runtime.xp2_unit_attack_source import (
            CURRENT_XP2_NO_EFFECT, CURRENT_XP2_RANGE_SUBMITTED,
        )
        effect=result['effect']
        reason=effect.get('refusal_code')
        if (effect['receipt']['action'] != action or
                (effect['status'], reason) not in (
                    ('completed', None), ('refused', CURRENT_XP2_NO_EFFECT),
                    ('submitted', CURRENT_XP2_RANGE_SUBMITTED))):
            raise RuntimeError('Attack result lacks the requested native disposition')
        return dict(status=effect['status'],reason=reason,requested_action=action)
    if occupation_action:
        effect = result['effect']
        if effect['status'] != 'completed' or effect['action'] != action:
            raise RuntimeError('Captured-city choice has no matching native effect')
        return dict(status='completed', reason=None, requested_action=action)
    if queue_action or placement_action or action['kind'] in ('city_focus','city_citizen'):
        effect=result['effect']
        if effect['status']!='completed' or effect['receipt']['action']!=action:
            raise RuntimeError('XP1 production queue has no matching native effect')
        return dict(status='completed',reason=None,requested_action=action)
    return dict(status='completed', reason=None, requested_action=action)


def _retain_xp2_diplomacy_if_ready(saved):
    """Join a delivered type-132 statement only after the owner is quiescent."""
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    if saved.backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        return False
    deferred = saved.prefix.deferred_events
    ledger = getattr(deferred, 'pending_diplomacy_statements', None)
    if type(ledger) is not list or not ledger:
        return False
    if getattr(deferred, 'diplomacy_statement_receiver', None) is not deferred:
        raise RuntimeError('Delivered XP2 diplomacy statement has no exact retained receiver')
    if saved.backend.busy or saved.backend.stage != 'xp1-continuation-ready':
        raise RuntimeError('XP2 diplomacy cannot be retained during an active transition')
    from civ6_host.runtime.xp2_diplomacy import retain
    return retain(saved)


def _advance_xp1(saved,sequence,path):
    from civ6_host.runtime.xp1_session_inputs import _write_once
    saved.emit('before_xp1_saved_turn_update',protocol_sequence=sequence+1)
    result=saved.advance()
    if result['action'] is not None or result['game_update_called'] is not True:
        raise RuntimeError('XP1 poll did not return the explicit native update receipt')
    saved.emit('xp1_saved_turn_update_returned',protocol_sequence=sequence+1,
        receipt=_write_once(_Path(path).resolve().parent/('update-result-'+str(sequence+1)+'.json'),result))


def _poll_xp1(saved, sequence, path):
    """Keep the shared LAN poll from advancing through a retained modal."""
    if getattr(saved, '_xp2_diplomacy', None) is not None:
        return False
    _advance_xp1(saved, sequence, path)
    if getattr(saved, 'world_congress_diagnostic', False):
        automatic = saved.advance_congress_empty(sequence + 1)
        if automatic is not None:
            from civ6_host.runtime.xp1_session_inputs import _write_once
            saved.emit('xp2_congress_automatic_phase_returned', protocol_sequence=sequence+1,
                receipt=_write_once(_Path(path).resolve().parent/
                    ('congress-automatic-result-'+str(sequence+1)+'.json'), automatic))
    return True


def _read_xp1_outcome(saved, player_id):
    """Read a fresh outcome, allowing only the exact retained modal context."""
    from civ6_host.runtime.xp1_session_result import read
    context = getattr(saved, '_xp2_diplomacy', None)
    if context is None:
        return read(saved, player_id=player_id)
    return read(saved, player_id=player_id, allow_diplomacy=True)


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
                or type(closure.get('privileged_critic_diagnostic', False)) is not bool
                or type(closure.get('foundation_legality_diagnostic', False)) is not bool
                or type(closure.get('governors_diagnostic', False)) is not bool
                or type(closure.get('diplomacy_overview_diagnostic', False)) is not bool
                or type(closure.get('trade_diagnostic', False)) is not bool
                or type(closure.get('standard_trade', False)) is not bool
                or type(closure.get('unit_formations', False)) is not bool
                or type(closure.get('stock_dedications', False)) is not bool
                or type(closure.get('espionage_diagnostic', False)) is not bool
                or type(closure.get('world_congress_diagnostic', False)) is not bool
                or type(closure.get('world_congress_review_diagnostic', False)) is not bool
                or type(closure.get('trade_overview_ui_selected', False)) is not bool
                or type(closure.get('command_profile_diagnostic', False)) is not bool
                or type(closure.get('checkpoint_on_close', False)) is not bool
                or closure.get('official_bundle') is None):
            raise ValueError('Unsupported bounded LAN closure')
        if closure.get('command_profile_diagnostic', False) and (
                closure['input_profile'] != 'xp2-lan' or 'execution_image' not in closure):
            raise ValueError('Command profiling requires the explicit XP2 image')
        foundation_legality = None
        if closure.get('foundation_legality_diagnostic', False) or closure.get('governors_diagnostic', False):
            from civ6_host.runtime.captured_session_profile import require_bbg_capture
            from civ6_host.runtime.execution_images import from_identity
            family_image = (from_identity(closure['execution_image']) if 'execution_image' in closure else None)
            if closure['input_profile'] != 'xp2-lan':
                raise ValueError('BBG family diagnostics require the XP2 input profile')
            require_bbg_capture(closure['official_bundle'], execution_image=family_image)
        if closure.get('foundation_legality_diagnostic', False):
            from civ6_host.runtime.xp2_foundation_legality import emit_readback as foundation_legality
        if closure.get('diplomacy_overview_diagnostic', False) and (
                closure['input_profile'] != 'xp2-lan'
                or closure.get('governors_diagnostic') is not True
                or 'execution_image' not in closure
                or closure.get('war_source_sha256') is None):
            raise ValueError('Initial diplomacy cannot fall back to another session profile')
        if closure.get('trade_diagnostic', False) and not closure.get('diplomacy_overview_diagnostic', False):
            raise ValueError('Trade cannot fall back to another session profile')
        if closure.get('world_congress_diagnostic', False) and not (
                closure.get('espionage_diagnostic', False) or
                closure.get('stock_dedications', False) and closure.get('world_congress_review_diagnostic', False)):
            raise ValueError('Congress requires the complete XP2 BBG or stock review chain')
        if closure.get('world_congress_review_diagnostic', False) and closure.get('world_congress_diagnostic') is not True:
            raise ValueError('Congress review requires the explicit Congress chain')
        if closure.get('trade_overview_ui_selected', False) and (
                closure['input_profile'] != 'xp2-lan' or closure.get('world_congress_review_diagnostic') is not True):
            raise ValueError('Trade overview requires the explicit current XP2 public query chain')
        if closure.get('espionage_diagnostic', False) and not closure.get('trade_diagnostic', False):
            raise ValueError('Espionage cannot fall back to another session profile')
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
                core_sha256=owner.backend.load_abi.core_sha256,
                war_source_sha256=closure.get('war_source_sha256'))
            _emit_native_load_profile(owner, protocol, local_player, emit)
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
            display_formatter = OwnedNativeTopPanelFormatter(owner, protocol,
                source_sha256=closure['public_display_source'])

        critic = None
        if closure.get('privileged_critic_diagnostic', False):
            from civ6_host.runtime.xp2_bbg_critic import CriticReadback
            critic = CriticReadback(closure, path)

        def reply(operation, player_id, sequence, command, request=None,
                  command_seconds=None, trace_before=None):
            started = perf_counter()
            if xp1:
                native = _read_xp1_outcome(owner, player_id)
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
            if critic is not None and not (result['terminated'] or result['truncated']):
                critic.emit_ready(owner, response, emit)
            if foundation_legality is not None and not (result['terminated'] or result['truncated']):
                foundation_legality(owner, response, emit)
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

        profiler = None
        if closure.get('command_profile_diagnostic', False):
            from civ6_host.runtime.command_profiling import CommandProfiler
            profiler = CommandProfiler(enabled=True, emit=emit,
                identity=dict(episode_id=protocol.identity.episode_id,
                              game_generation=protocol.identity.game_generation))
        none = dict(status='none', reason=None, requested_action=None)
        reply('reset', local_player, 0, none)
        # Private administrative spy fixture hook v2.
        # Restore/compare the untouched checkpoint first. No protocol action is
        # added: the next ordinary observe receives the new native revision.
        if 'private_spy_fixture' in closure:
            import hashlib as fixture_hashlib
            from civ6_host.runtime import private_spy_fixture
            fixture_spec = closure['private_spy_fixture']
            fixture_path = _Path(private_spy_fixture.__file__).resolve()
            fixture_sha = fixture_hashlib.sha256(fixture_path.read_bytes()).hexdigest()
            if (not xp1 or closure['input_profile'] != 'xp2-lan'
                    or fixture_spec['module'] != private_spy_fixture.__name__
                    or fixture_path != _Path(fixture_spec['module_file']).resolve()
                    or fixture_sha != fixture_spec['module_sha256']
                    or closure['pins'].get(str(fixture_path)) != fixture_sha):
                raise ValueError('Unpinned private spy fixture')
            private_spy_fixture.install_fixture(owner, closure, emit)
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
            with (profiler.measure('command', operation, request['sequence'], pid)
                  if profiler is not None else nullcontext()):
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
                        _poll_xp1(owner,protocol.sequence,path)
                    else:
                        from civ6_host.runtime.network_turns import advance
                        advance(owner)
                elif operation == 'close' and closure.get('checkpoint_on_close', False):
                    _save_before_close(owner, protocol, closure, path, request, xp1, emit)
            command_seconds = perf_counter() - started
            with (profiler.measure('response', operation, request['sequence'], pid)
                  if profiler is not None else nullcontext()):
                reply(operation, pid, request['sequence'], command, request,
                      command_seconds=command_seconds if operation in ('act', 'poll') else None,
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

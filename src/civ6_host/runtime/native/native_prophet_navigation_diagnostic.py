"""One explicit diagnostic movement towards an own completed Holy Site.

The target is a heuristic, never a claim about native founding legality. The
existing public MOVE_TO pipeline re-catalogues, revalidates, delivers, publishes
and verifies the exact selected movement. Activation is a separate operation.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_prophet_navigation as navigation
from civ6_host.runtime.native import native_unit_movement as movement

def move_prophet_towards_district(host, player_id):
    if host.ui_child is None or host.actions.pending or host.deferred_events.pending:
        raise RuntimeError('Prophet navigation requires a published view and drained queues')
    state = host.inspect_own_religion_snapshot(player_id)
    turn = state['current_game_turn']
    if state['player_id'] != player_id:
        raise ValueError('Prophet navigation perspective mismatch')
    if state['religion_type_created'] != -1 or not state['has_religious_founding_unit']:
        return None
    roster = navigation.parse_prophet_roster(host.runtime.evaluate_text(host.ui_child, navigation.prophet_roster_source(player_id, turn), b'@native_prophet_navigation_roster', capacity=65536), player_id, turn)
    targets = navigation.parse_target_catalog(host.runtime.evaluate_text(host.ui_child, navigation.target_catalog_source(player_id, turn, ('DISTRICT_HOLY_SITE',)), b'@native_prophet_navigation_targets', capacity=navigation.MAX_BYTES), player_id, turn)
    if (roster['width'], roster['height']) != (targets['width'], targets['height']):
        raise ValueError('Prophet and district maps disagree')
    host.emit('native_prophet_navigation_candidates_observed', player_id=player_id, current_game_turn=turn, own_prophets=roster['units'], own_targets=targets['targets'], target_policy='explicit-diagnostic-own-completed-holy-site', complete_movement_or_founding_space=False, founding_legality_established=False, eligible_for_training=False)
    if not roster['units'] or not targets['targets']:
        return None
    if len(roster['units']) * len(targets['targets']) > 128:
        raise RuntimeError('Diagnostic prophet routing exceeds 128 explicit target pairs')
    catalog = movement.parse_candidates(host.runtime.evaluate_text(host.ui_child, movement.candidate_source(player_id, turn), b'@native_prophet_navigation_moves', capacity=524288), player_id, turn)
    proposals = []
    for unit in roster['units']:
        uid = unit['unit_id']
        choices = [c for c in catalog['choices'] if c['unit_id'] == uid]
        if not choices:
            continue
        if any(((c['source_plot_id'], c['source_x'], c['source_y']) != (unit['plot_id'], unit['x'], unit['y']) for c in choices)):
            raise ValueError('Prophet roster and movement catalog disagree')
        for target in targets['targets']:
            if unit['plot_id'] == target['plot_id']:
                continue
            distances = navigation.parse_distances(host.runtime.evaluate_text(host.ui_child, navigation.distance_source(player_id, turn, target, catalog, uid), b'@native_prophet_navigation_distances', capacity=65536), catalog, target, uid)
            if not any((d < distances['start_distance'] for d in distances['destination_distances'].values())):
                continue
            proposal = navigation.choose_navigation_step(catalog, target, distances, uid)
            proposals.append((distances['start_distance'], proposal['distance_after'], target['plot_id'], uid, target, proposal))
    if not proposals:
        host.emit('native_prophet_navigation_unavailable', player_id=player_id, current_game_turn=turn, reason='no-admitted-native-step-approaches-selected-district', founding_legality_established=False, action_substituted=False, eligible_for_training=False)
        return None
    _, _, _, uid, target, selected = min(proposals, key=lambda p: p[:4])
    choice = selected['choice']
    host.emit('native_prophet_navigation_selected', player_id=player_id, current_game_turn=turn, target=target, unit_id=uid, source_plot_id=choice['source_plot_id'], destination_plot_id=choice['destination_plot_id'], distance_before=selected['distance_before'], distance_after=selected['distance_after'], explicit_diagnostic_policy=True, founding_legality_established=False, eligible_for_training=False)
    effect = host.inspect_unit_movement(player_id, unit_id=uid, destination_plot_id=choice['destination_plot_id'], require_candidate=True, resolve_friendly_blockage=False)
    if type(effect) is not dict or effect.get('found') is not True or effect.get('at_destination') is not True or ((effect.get('player_id'), effect.get('turn'), effect.get('unit_id'), effect.get('x'), effect.get('y')) != (player_id, turn, uid, choice['destination_x'], choice['destination_y'])) or (type(effect.get('moves_remaining')) not in (int, float)) or (not 0 <= effect['moves_remaining'] < choice['moves_remaining']):
        raise RuntimeError('Selected prophet movement effect was not established')
    host.emit('native_prophet_navigation_effect_verified', player_id=player_id, current_game_turn=turn, effect=effect, target=target, reached_selected_district=choice['destination_plot_id'] == target['plot_id'], founding_legality_established=False, requires_fresh_native_activation_check=True, native_rules_used=True, eligible_for_training=False)
    return effect

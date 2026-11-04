"""Compose public religious actions with independent, freshly published effects.

These routines run only inside the bounded native diagnostic. Their explicit
first-candidate policy is not a learner and does not define native legality.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from civ6_host.runtime.native import native_prophet_activation as prophet
from civ6_host.runtime.native import native_religion_founding as founding
from civ6_host.runtime.native import native_religion_beliefs as beliefs
from civ6_host.runtime.native.native_player_operation_request import request_player_operation

def _ready(host):
    if host.ui_child is None or host.actions.pending or host.deferred_events.pending:
        raise RuntimeError('Religious action requires a published view and drained queues')

def _guard(host, key, source, name, expected):
    if not getattr(host, key, False):
        marker = host.runtime.evaluate_text(host.ui_child, source(), name)
        if marker != expected:
            raise RuntimeError('Native HKS religious action guards failed')
        setattr(host, key, True)
        host.emit('native_hks_religious_action_guards_verified', guard=name.decode('ascii'), native_gameplay_mutated=False, eligible_for_training=False)

def activate_prophet(host, player_id, *, selected_unit_id=None):
    """Activate one native-eligible prophet, retaining any other pending choices."""
    _ready(host)
    _guard(host, '_prophet_activation_guards_verified', prophet.guard_case, b'@native_prophet_guards', b'prophet-activation-guards-ok')
    before = host.inspect_own_religion_snapshot(player_id)
    turn = before['current_game_turn']
    if before['religion_type_created'] != -1 or not before['has_religious_founding_unit']:
        if selected_unit_id is not None:
            raise RuntimeError('Explicit prophet activation is not available in the current state')
        return None
    catalog = prophet.parse_catalog(host.runtime.evaluate_text(host.ui_child, prophet.catalog_source(player_id, turn), b'@native_prophet_catalog', capacity=prophet.MAX_WIRE), player_id, turn)
    host.emit('native_prophet_activation_catalog_observed', catalog=catalog, complete_unit_action_space=False, eligible_for_training=False)
    if not catalog['candidates']:
        if selected_unit_id is not None:
            raise RuntimeError('Explicit prophet is not currently eligible for activation')
        host.emit('native_prophet_activation_not_available', player_id=player_id, current_game_turn=turn, native_legality_used=True, movement_not_substituted=True, eligible_for_training=False)
        return None
    explicit = selected_unit_id is not None
    uid = selected_unit_id if explicit else catalog['candidates'][0]['unit_id']
    choice = prophet.choose(catalog, uid)
    effect_source = prophet.effect_source(choice, before)
    prophet.parse_revalidated(host.runtime.evaluate_text(host.ui_child, prophet.revalidate_source(choice), b'@native_prophet_revalidation'), choice)
    host.emit('native_prophet_activation_selected', choice=choice, policy='explicit' if explicit else 'first-native-candidate', eligible_for_training=False)
    submitted = prophet.parse_request(host.runtime.evaluate_text(host.ui_child, prophet.request_source(choice), b'@native_prophet_request'), choice)
    if not submitted['request_submitted'] or len(host.actions.pending) != 1:
        raise RuntimeError('Prophet activation did not serialize exactly one native command')
    host.actions.deliver_one()
    host.deferred_events.drain_empty_receivers()
    host.view_publisher.publish()
    effect = prophet.parse_effect(host.runtime.evaluate_text(host.ui_child, effect_source, b'@native_prophet_effect'), choice, before)
    after = host.inspect_own_religion_snapshot(player_id)
    if after['player_id'] != player_id or after['current_game_turn'] != turn or after['holy_city'] != effect['founding_site'] or (after['num_beliefs_earned'] != effect['beliefs_earned_after']) or (after['religion_type_created'] != -1):
        raise RuntimeError('Fresh own religion snapshot differs from activation readback')
    host.emit('native_prophet_activation_effect_verified', player_id=player_id, current_game_turn=turn, choice=choice, before=before, after=after, effect=effect, native_rules_used=True, eligible_for_training=False)
    return effect

def found_religion(host, player_id, *, selected_index=None):
    """Name the activated prophet's religion via the scalar public operation."""
    _ready(host)
    _guard(host, '_religion_founding_guards_verified', founding.guard_case, b'@native_religion_founding_guards', b'native-religion-founding-guard-ok')
    before = host.inspect_own_religion_snapshot(player_id)
    turn = before['current_game_turn']
    if before['religion_type_created'] != -1 or before['holy_city'] == {'player': -1, 'type': 2, 'id': -1}:
        if selected_index is not None:
            raise RuntimeError('Explicit religion foundation is not due')
        return None
    catalog = founding.parse_catalog(host.runtime.evaluate_text(host.ui_child, founding.catalog_source(player_id, turn), b'@native_religion_founding_catalog', capacity=founding.MAX_RESPONSE), player_id, turn)
    host.emit('native_religion_founding_catalog_observed', catalog=catalog, custom_names_admitted=False, eligible_for_training=False)
    if not catalog['candidates']:
        raise RuntimeError('Religion foundation has no admitted predefined-name candidate')
    explicit = selected_index is not None
    index = selected_index if explicit else catalog['candidates'][0]['index']
    choice = founding.choose(catalog, index)
    effect_source = founding.effect_source(choice, before)
    checked = founding.parse_revalidated(host.runtime.evaluate_text(host.ui_child, founding.revalidate_source(choice), b'@native_religion_founding_revalidation'), choice)
    host.emit('native_religion_founding_selected', choice=choice, policy='explicit' if explicit else 'first-native-predefined-name', eligible_for_training=False)
    result = request_player_operation(host.core, host.context, player_id, checked['operation'], checked['parameters'])
    host.emit('native_player_operation_request_returned', kind='found-religion', **result)
    if not result['can_start'] or not result['request_invoked']:
        raise RuntimeError('Native CanStartPlayerOperation refused religion foundation')
    if len(host.actions.pending) != 1 or host.actions.pending[0][:4] != struct.pack('<I', 3294486831):
        raise RuntimeError('Religion request did not emit exactly one native operation archive')
    host.actions.deliver_one()
    host.deferred_events.drain_empty_receivers()
    host.view_publisher.publish()
    effect = founding.parse_effect(host.runtime.evaluate_text(host.ui_child, effect_source, b'@native_religion_founding_effect'), choice, before)
    after = host.inspect_own_religion_snapshot(player_id)
    if after['player_id'] != player_id or after['current_game_turn'] != turn or after['religion_type_created'] != choice['religion_index'] or (after['holy_city'] != choice['founding_site']):
        raise RuntimeError('Fresh own religion snapshot differs from founding readback')
    host.emit('native_religion_founding_effect_verified', player_id=player_id, current_game_turn=turn, choice=choice, before=before, after=after, effect=effect, native_rules_used=True, eligible_for_training=False)
    return effect

def add_belief(host, player_id, *, selected_index=None):
    """Add exactly one chosen belief, then verify old and new native membership."""
    _ready(host)
    _guard(host, '_religion_belief_guards_verified', beliefs.guard_case, b'@native_religion_belief_guards', b'native-add-belief-guard-ok')
    before = host.inspect_own_religion_snapshot(player_id)
    turn = before['current_game_turn']
    if before['religion_type_created'] == -1:
        if selected_index is not None:
            raise RuntimeError('Explicit religious belief requires a founded religion')
        return None
    catalog = beliefs.parse_catalog(host.runtime.evaluate_text(host.ui_child, beliefs.catalog_source(player_id, turn), b'@native_religion_belief_catalog', capacity=beliefs.MAX_RESPONSE), player_id, turn)
    host.emit('native_religion_belief_catalog_observed', catalog=catalog, eligible_for_training=False)
    if catalog['status'] == 'not_due':
        if selected_index is not None:
            raise RuntimeError('Explicit religious belief has no native available slot')
        return None
    explicit = selected_index is not None
    index = selected_index if explicit else catalog['candidates'][0]['index']
    choice = beliefs.choose(catalog, index)
    effect_source = beliefs.effect_source(choice, before)
    checked = beliefs.parse_revalidated(host.runtime.evaluate_text(host.ui_child, beliefs.revalidate_source(choice), b'@native_religion_belief_revalidation'), choice)
    host.emit('native_religion_belief_selected', choice=choice, policy='explicit' if explicit else 'first-native-candidate', eligible_for_training=False)
    result = request_player_operation(host.core, host.context, player_id, checked['operation'], checked['parameters'])
    host.emit('native_player_operation_request_returned', kind='add-belief', **result)
    if not result['can_start'] or not result['request_invoked']:
        raise RuntimeError('Native CanStartPlayerOperation refused belief selection')
    if len(host.actions.pending) != 1 or host.actions.pending[0][:4] != struct.pack('<I', 3294486831):
        raise RuntimeError('Belief request did not emit exactly one native operation archive')
    host.actions.deliver_one()
    host.deferred_events.drain_empty_receivers()
    host.view_publisher.publish()
    effect = beliefs.parse_effect(host.runtime.evaluate_text(host.ui_child, effect_source, b'@native_religion_belief_effect'), choice, before)
    after = host.inspect_own_religion_snapshot(player_id)
    expected_own = {'religion_index': choice['religion_index'], 'founder': player_id, 'belief_indices': list(effect['belief_indices'])}
    if after['player_id'] != player_id or after['current_game_turn'] != turn or after['religion_type_created'] != choice['religion_index'] or (after['num_beliefs_earned'] != effect['num_beliefs_earned']) or (after['own_religion'] != expected_own):
        raise RuntimeError('Fresh own religion snapshot differs from belief readback')
    host.emit('native_religion_belief_effect_verified', player_id=player_id, current_game_turn=turn, choice=choice, before=before, after=after, effect=effect, native_rules_used=True, eligible_for_training=False)
    return effect

def develop_religion(host, player_id):
    """Diagnostic choices only; never bypass a native blocking decision."""
    if activate_prophet(host, player_id) is None:
        from civ6_host.runtime.native.native_prophet_navigation_diagnostic import move_prophet_towards_district
        moved = move_prophet_towards_district(host, player_id)
        if moved is not None:
            activate_prophet(host, player_id)
    found_religion(host, player_id)
    for _ in range(16):
        if add_belief(host, player_id) is None:
            break
    else:
        raise RuntimeError('Religion diagnostic exceeded 16 verified belief additions in one phase')

"""Visible plot attacks on a borrowed Gathering Storm human seat."""

from functools import partial
from struct import pack
from types import SimpleNamespace

from civ6_host.contracts import capability_unit_attacks as attacks
from .configuration_profiles import XP2_CORE_SHA256


_MODIFIERS = {
    ('MOVE_TO', 'enemy_flag'): 16,
    ('MOVE_TO', 'world_plot'): 16400,
    ('RANGE_ATTACK', 'enemy_flag'): 16,
    ('RANGE_ATTACK', 'dedicated_ranged'): 0,
    ('RANGE_ATTACK', 'world_plot'): 0,
}


def enabled(saved):
    return getattr(saved, '_xp2_lan_unit_attacks_enabled', False) is True


def require_archive(payload, player_id, action, *, operation_index):
    attacks.validate_action(action)
    if (type(player_id) is not int or not 0 <= player_id < 64
            or type(operation_index) is not int or not 0 <= operation_index <= 2047):
        raise ValueError('Borrowed attack requires a native player and operation index')
    modifiers = _MODIFIERS[action['operation'], action['input_route']]
    expected = pack('<IHH9I', 0x8c0f3f36, player_id, 1, action['unit_id'], operation_index,
                    0xffffffff, 0, 1, action['x'], action['y'], modifiers, 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Borrowed attack archive differs from its actor, unit, route or destination')


def _operation_index(prefix, observation, action):
    pid, turn, operation = observation['player_id'], observation['turn'], action['operation']
    source = f"""
assert(Game.GetLocalPlayer()=={pid} and Game.GetLocalObserver()=={pid}
   and Game.GetCurrentGameTurn()=={turn},'borrowed attack perspective changed')
local op=GameInfo.UnitOperations['UNITOPERATION_{operation}']
assert(op and op.Hash==UnitOperationTypes.{operation} and type(op.Index)=='number'
   and op.Index % 1 == 0 and op.Index >= 0 and op.Index <= 2047,'invalid attack operation index')
assert(UnitOperationMoveModifiers.NONE==0 and UnitOperationMoveModifiers.ATTACK==16
   and UnitOperationMoveModifiers.MOVE_IGNORE_UNEXPLORED_DESTINATION==16384,
   'borrowed attack modifiers changed')
return string.format('%.0f',op.Index)
"""
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source.encode('ascii'),
                                      b'@xp2_borrowed_attack_index', capacity=16)
    if type(raw) is not bytes or not raw.isdigit() or not 1 <= len(raw) <= 4:
        raise ValueError('Invalid borrowed native attack operation index')
    index = int(raw)
    if not 0 <= index <= 2047 or str(index).encode('ascii') != raw:
        raise ValueError('Noncanonical borrowed native attack operation index')
    return index


def read(saved, observation, *, queued_orders):
    from .native import native_saved_combat as combat
    from .xp1_session_view import _borrowed_xp2_reference
    from .xp1_unit_attack_profile import bind_owner, verify_public_precision_source

    b, token, prefix = saved.backend, saved.continuation, saved.prefix
    pid, turn = observation['player_id'], observation['turn']
    _borrowed_xp2_reference(saved, pid)
    bind_owner(b, b.core, b.runtime.read)
    verify_public_precision_source(XP2_CORE_SHA256)
    token.transport.require_empty_native_queue()
    b.control(empty=True)
    options = dict(player_id=pid, core_sha256=XP2_CORE_SHA256)
    native = combat.catalog(prefix, turn, observation, **options)
    state = dict(player_id=pid, turn=turn, width=native['width'], height=native['height'],
        units=combat.unit_state(prefix, turn, observation, **options), relationships=native['relationships'],
        cities=native['cities'], offers=combat.orders(native, player_id=pid))
    public = attacks.project_public(state, observation=observation, queued_orders=queued_orders)
    token.transport.require_empty_native_queue()
    b.control(empty=True)
    return state, public


def apply(saved, action, observation, combat_state, *, expected):
    from .native import native_saved_combat as combat
    from .xp2_unit_attack_source import (
        CURRENT_XP2_LIFECYCLE, CURRENT_XP2_NO_EFFECT, CURRENT_XP2_RANGE_ADDED,
        CURRENT_XP2_RANGE_SUBMITTED, current_lifecycle_image,
    )

    refused = dict(status='refused', requested_action=action)
    if combat_state is None or action not in combat_state[1]['offers']:
        return dict(refused, reason='native_unit_attack_unavailable'), None
    state, public = combat_state
    if public != expected:
        return dict(refused, reason='native_combat_state_changed'), None
    receipts = {}

    def emit(stage, **payload):
        if stage in receipts or stage not in ('official_explicit_unit_attack_readback',
                                              'official_explicit_unit_attack_effect'):
            raise RuntimeError('Unexpected borrowed attack receipt')
        receipts[stage] = payload
        saved.emit(stage, **payload)

    pid, turn = observation['player_id'], observation['turn']
    b, token, prefix = saved.backend, saved.continuation, saved.prefix
    index = _operation_index(prefix, observation, action)
    lifecycle = (dict(live_core=b.core, live_read=b.runtime.read)
                 if current_lifecycle_image(getattr(b.core, '_civ6_host_execution_image', None)) else {})
    owner = SimpleNamespace(emit=emit, explicit_combat_units=state['units'],
                            explicit_combat_cities=state['cities'])
    count = token.publication_count
    with token.transport.require_xp2_single_archive(
            partial(require_archive, player_id=pid, action=action, operation_index=index)):
        after = combat.apply(owner, prefix, action, turn, observation,
                             player_id=pid, core_sha256=XP2_CORE_SHA256, **lifecycle)
    for stage in ('official_explicit_unit_attack_readback', 'official_explicit_unit_attack_effect'):
        row = receipts[stage]
        if (row['action'] != action or row['observation_before'] != observation
                or row['observation_after'] != after or row['native_defender_selection'] is not True):
            raise RuntimeError('Borrowed attack receipt differs from its native observation')
    receipt = receipts['official_explicit_unit_attack_effect']
    effect = receipt['effect']
    if receipt['automatic_choices_applied'] is not False or token.publication_count != count + 1:
        raise RuntimeError('Borrowed attack crossed its explicit publication boundary')
    status, reason = 'completed', None
    if effect['observable_native_change'] is False:
        cycle = effect['operation_lifecycle']
        source = cycle['current_xp2_source_sha256']
        if source == CURRENT_XP2_RANGE_ADDED[1] and cycle['status'] == 'RANGE_ATTACK_added':
            status, reason = 'submitted', CURRENT_XP2_RANGE_SUBMITTED
        elif source == CURRENT_XP2_LIFECYCLE[1]:
            status, reason = 'refused', CURRENT_XP2_NO_EFFECT
        else:
            raise RuntimeError('Borrowed attack lacks a qualified native operation lifecycle')
    elif not effect['immediate_state_change'] and effect['queued_move_to_selected_plot']:
        status, reason = 'submitted', 'native_combat_resolution_pending'

    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(prefix.runtime, prefix.ui_child, pid)
        if status == 'refused' and after != observation:
            status, reason = 'submitted', 'native_combat_resolution_pending'
    token.transport.require_empty_native_queue()
    return dict(status=status, reason=reason, requested_action=action), after

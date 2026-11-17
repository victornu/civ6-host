"""Owned city-state influence and military requests for a borrowed LAN seat."""

from civ6_host.contracts import city_state_levies, diplomacy_overview, envoys, network_turn
from . import xp1_city_state_levies as levies
from . import xp2_city_state_peace as peace
from . import xp2_envoys as influence


FIELDS = {'send_envoy': 'envoys', 'retain_envoys': 'envoys', city_state_levies.ACTION: 'city_state_levies'}


def enabled(saved):
    return getattr(saved, '_xp2_lan_city_states_enabled', False) is True


def peace_scope(saved, requested=None):
    from . import xp2_bbg_inputs, xp2_bundle_inputs

    available = False
    if enabled(saved) and getattr(saved, 'diplomacy_overview_diagnostic', False) is True:
        reference = saved.inputs.official_bundle
        if getattr(saved, 'standard_trade', False) is True:
            available = reference == xp2_bundle_inputs.REFERENCE
        else:
            available = (getattr(saved, 'governors_diagnostic', False) is True
                         and xp2_bbg_inputs.is_reference(reference))
    if requested is None:
        return available
    if type(requested) is not bool or (requested and not available):
        raise ValueError('Borrowed peace requires an admitted Gathering Storm diplomacy profile')
    return requested


def read_peace(saved, observation, *, available):
    if not available:
        return None
    from .xp1_session_view import _borrowed_xp2_reference

    pid, turn = observation['player_id'], observation['turn']
    _borrowed_xp2_reference(saved, pid)
    token = saved.continuation
    token.transport.require_empty_native_queue()
    result = peace.panel(saved.prefix, pid, turn)
    token.transport.require_empty_native_queue()
    return result


def apply_peace(saved, action, observation, *, expected, available):
    refused = dict(status='refused', requested_action=action)
    current = read_peace(saved, observation, available=available)
    if current is None:
        return dict(refused, reason='native_city_state_peace_unavailable'), None
    if current != expected:
        return dict(refused, reason='native_city_state_peace_changed'), None
    pid, turn = observation['player_id'], observation['turn']
    token = saved.continuation
    publication_before = token.publication_count
    result = peace.apply_panel(saved, saved.backend, saved.prefix, action, pid, turn, current)
    reply = dict(status=result['status'], requested_action=action, reason=result['refusal_code'])
    if result['status'] == 'refused':
        return reply, None
    if token.publication_count != publication_before + 1:
        raise RuntimeError('Borrowed city-state peace did not publish its native effect')
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
    from .native.native_player_observation import observe_player

    token.transport.require_empty_native_queue()
    prefix = saved.prefix
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    if (after['player_id'], after['turn']) != (pid, turn):
        raise RuntimeError('Borrowed city-state peace crossed the current player or turn')
    return reply, after


def is_peace(action):
    return action['kind'] == 'diplomacy_initiate' and action.get('choice') == diplomacy_overview.MAKE_PEACE


def validate_action(action):
    if action['kind'] == city_state_levies.ACTION:
        city_state_levies.validate_action(action)
    else:
        envoys.validate_action(action)


def read(saved, observation, state, *, strategic_allowed, restore_envoys=None):
    if not enabled(saved):
        return {}
    pid = observation['player_id']
    controls = next(row for row in state['rows'] if row['player_id'] == pid)
    if network_turn.is_waiting(controls):
        return {}
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, pid)
    token = saved.continuation
    token.transport.require_empty_native_queue()
    result = {}
    if strategic_allowed:
        current = influence.snapshot(saved, observation, active=True)
        result['envoys'] = influence.restore_borrowed_consideration(saved, observation, current, restore_envoys)
    if getattr(saved, 'xp2_city_state_levies_enabled', False):
        result['city_state_levies'] = levies.snapshot(saved, observation, active=True)
        result['unit_levies'] = levies.unit_flags(saved, observation, active=True)
    token.transport.require_empty_native_queue()
    return result


def apply(saved, action, observation, states, *, expected):
    is_levy = action['kind'] == city_state_levies.ACTION
    provider = levies if is_levy else influence
    contract = city_state_levies if is_levy else envoys
    state = states.get(FIELDS[action['kind']])
    refused = dict(status='refused', requested_action=action)
    if state is None:
        return dict(refused, reason='native_city_state_choice_unavailable'), None
    if state != expected:
        return dict(refused, reason='native_city_state_choice_changed'), None
    if action not in contract.actions(state):
        return dict(refused, reason='native_city_state_choice_unavailable'), None
    token = saved.continuation
    token.transport.require_empty_native_queue()
    count = token.publication_count
    after = provider.apply(saved, action, observation, borrowed=state)['observation']
    if token.publication_count != count + 1:
        raise RuntimeError('Borrowed city-state choice did not publish its native effect')
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(saved.prefix.runtime, saved.prefix.ui_child, observation['player_id'])
    token.transport.require_empty_native_queue()
    return dict(status='completed', reason=None, requested_action=action), after

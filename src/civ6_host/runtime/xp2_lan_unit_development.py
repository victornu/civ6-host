"""Borrowed XP2 human promotion menus and native upgrade quotes."""

from hashlib import sha256
from struct import pack

from civ6_host.contracts import unit_promotions, unit_upgrades
from . import xp2_promotions, xp2_unit_upgrades


FIELDS = {'promote_unit': 'unit_promotions', 'upgrade_unit': 'unit_upgrades'}


def enabled(saved):
    return getattr(saved, '_xp2_lan_unit_development_enabled', False) is True


def validate_archive(payload, actor, action):
    if type(actor) is not int or not 0 <= actor < 64:
        raise ValueError('Borrowed unit command requires a native human seat')
    if action['kind'] == 'promote_unit':
        unit_promotions.validate_action(action)
        expected = pack('<IHH6I', 0x493830af, actor, 1, action['unit_id'], 13, 0, 1, 0, action['hash'])
    else:
        from .native.native_saved_unit_upgrade import validate_action
        validate_action(action)  # The native sender receives the original gold/type quote.
        expected = pack('<IHH7I', 0x493830af, actor, 1, action['unit_id'], 15, 0, 1,
                        0xffffd8f1, 0xffffd8f1, 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Borrowed unit command archive differs from its actor, unit or operation')
    return sha256(payload).hexdigest()


def read(saved, observation, state, *, strategic_allowed):
    from .xp1_session_view import _borrowed_xp2_reference

    pid = observation['player_id']
    actor = next(row for row in state['rows'] if row['player_id'] == pid)
    if not enabled(saved) or not actor['active'] or not actor['active_complete'] or actor['can_unready']:
        return {}
    _borrowed_xp2_reference(saved, pid)
    transport = saved.continuation.transport
    transport.require_empty_native_queue()
    result = {'promote_unit': xp2_promotions.snapshot(saved, observation, active=True)}
    if strategic_allowed:
        result['upgrade_unit'] = xp2_unit_upgrades.snapshot(saved, observation, active=True)
    transport.require_empty_native_queue()
    return result


def apply(saved, action, observation, states, *, expected_state):
    kind = action['kind']
    state = states.get(kind)
    refused = dict(status='refused', requested_action=action)
    if state is None:
        return dict(refused, reason='native_unit_development_unavailable'), None
    public = state[1]
    if public != expected_state:
        return dict(refused, reason='native_unit_development_state_changed'), None
    offers = public['offers'] if kind == 'promote_unit' else unit_upgrades.actions(public)
    if action not in offers:
        return dict(refused, reason='native_unit_development_unavailable'), None

    continuation = saved.continuation
    count = continuation.publication_count
    if kind == 'promote_unit':
        after = xp2_promotions.apply(saved, action, observation, borrowed_state=state[0],
                                     archive_validator=validate_archive)
    else:
        after = xp2_unit_upgrades.apply(saved, action, observation, borrowed_state=state,
                                        archive_validator=validate_archive)
    feedback = continuation.trade_feedback
    if feedback is not None and feedback.events:
        delivered = continuation.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(saved.prefix.runtime, saved.prefix.ui_child, observation['player_id'])
    if continuation.publication_count != count + 1:
        raise RuntimeError('Borrowed unit command did not publish its native effect')
    continuation.transport.require_empty_native_queue()
    return dict(status='completed', reason=None, requested_action=action), after

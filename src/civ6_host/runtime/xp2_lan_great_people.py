"""Explicit Great People choices while an authenticated LAN seat is borrowed."""

from civ6_host.contracts import great_people_actions, network_turn
from . import xp1_great_people as reader
from . import xp1_great_people_commands as commands


KINDS = great_people_actions.KINDS
validate_action = great_people_actions.validate_action


def mode(saved, requested=None):
    current = 'off'
    if getattr(saved, 'xp2_great_people', False) is True:
        current = 'actions' if getattr(saved, 'xp2_great_people_actions', False) is True else 'read'
    if requested is None:
        return current
    if requested not in ('off', 'read', 'actions') or (
            requested != 'off' and (current == 'off' or requested == 'actions' and current != 'actions')):
        raise ValueError('Borrowed Great People need their admitted reader and command scope')
    return requested


def read(saved, observation, activity, *, scope):
    row = next(row for row in activity['rows'] if row['player_id'] == observation['player_id'])
    if scope == 'off' or network_turn.is_waiting(row):
        return None
    return reader.read(saved, observation, xp2=True, borrowed=True)


def apply(saved, action, observation, activity, *, published, scope):
    refused = dict(status='refused', requested_action=action)
    player_id = observation['player_id']
    row = next(row for row in activity['rows'] if row['player_id'] == player_id)
    if scope != 'actions' or network_turn.is_waiting(row) or published is None:
        return dict(refused, reason='native_great_person_offer_changed'), None
    from .xp2_great_people_source import bind

    bind(saved, borrowed_player=player_id)
    token = saved.continuation
    publications = token.publication_count
    result = commands.apply(saved, action, observation, borrowed_catalogue=published)
    if result['status'] == 'refused':
        return dict(refused, reason=result['refusal_code']), None
    if (result['status'] != 'completed' or result['action'] != action
            or token.publication_count != publications + 1):
        raise RuntimeError('Borrowed Great Person request did not confirm its published action')
    feedback = token.trade_feedback
    after = result['observation']
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        prefix = saved.prefix
        after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    return dict(status='completed', reason=None, requested_action=action), after

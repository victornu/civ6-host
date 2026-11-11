"""Player-visible formations and native partner choices from the unit panel."""

from .action_budget import ORDINARY_ACTION_LIMIT
from .trade import _list, _number, _shape, uint

SCHEMA = 'civ6-host.unit-formations.v1'
KIND = 'unit_formation'
FIELDS = frozenset(('kind', 'unit_id', 'command', 'partner_id'))


def validate_action(action):
    _shape(action, 'kind unit_id command partner_id')
    unit_id = uint(action['unit_id'], 'formation unit')
    if action['kind'] != KIND or action['command'] not in ('enter', 'exit'):
        raise ValueError('Invalid formation command')
    if action['command'] == 'enter':
        if uint(action['partner_id'], 'formation partner') == unit_id:
            raise ValueError('A unit cannot form with itself')
    elif action['partner_id'] is not None:
        raise ValueError('Leaving a formation takes no partner')
    return action


def actions(value):
    return [] if value is None else value['offers']


def validate(value, pid, turn, *, observation=None):
    _shape(value, 'schema player_id turn units offers')
    if (value['schema'] != SCHEMA or uint(value['player_id'], 'formation player', 63) != pid
            or uint(value['turn'], 'formation turn', 0x7fffffff) != turn):
        raise ValueError('Foreign formation query')
    units = {}
    for row in _list(value['units'], ORDINARY_ACTION_LIMIT):
        _shape(row, 'unit_id count moves max_moves')
        unit_id = uint(row['unit_id'], 'formation unit')
        uint(row['count'], 'formation count', ORDINARY_ACTION_LIMIT)
        _number(row['moves'])
        _number(row['max_moves'])
        if unit_id in units:
            raise ValueError('Duplicate formation unit')
        units[unit_id] = row
    if list(units) != sorted(units):
        raise ValueError('Unordered formation units')
    if observation is not None:
        if ((observation['player_id'], observation['turn']) != (pid, turn)
                or sorted(u['id'] for u in observation['units']) != list(units)
                or any(u['owner'] != pid for u in observation['units'])):
            raise ValueError('Formation roster differs from the player view')
    seen = set()
    for action in _list(value['offers'], ORDINARY_ACTION_LIMIT):
        validate_action(action)
        actor, partner = action['unit_id'], action['partner_id']
        key = actor, action['command'], partner
        if actor not in units or (partner is not None and partner not in units) or key in seen:
            raise ValueError('Foreign or duplicate formation offer')
        seen.add(key)
    return value

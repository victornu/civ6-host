"""Player-owned unit promotion state and exact native choices."""
import re

from .action_budget import ORDINARY_ACTION_LIMIT

FIELDS = frozenset(('kind', 'unit_id', 'index', 'hash', 'item_type'))


def _uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


def validate_action(action):
    if (type(action) is not dict or set(action) != FIELDS or action['kind'] != 'promote_unit'
            or any(not _uint(action[key]) for key in ('unit_id', 'index', 'hash'))
            or type(action['item_type']) is not str
            or not re.fullmatch('PROMOTION_[A-Z0-9_]{1,100}', action['item_type'])):
        raise ValueError('Invalid promotion action')
    return action


def validate_catalogue(value, player_id, turn, *, observation=None):
    if (type(value) is not dict or set(value) != {'player_id', 'turn', 'units', 'offers'}
            or not _uint(value['player_id'], 63) or value['player_id'] != player_id
            or not _uint(value['turn'], 0x7fffffff) or value['turn'] != turn
            or any(type(value[key]) is not list or len(value[key]) > ORDINARY_ACTION_LIMIT
                   for key in ('units', 'offers'))):
        raise ValueError('Invalid promotion catalogue boundary')
    acquired = {}
    for unit in value['units']:
        if (type(unit) is not dict or set(unit) != {'unit_id', 'experience_points', 'promotions'}
                or not _uint(unit['unit_id']) or unit['unit_id'] in acquired
                or not _uint(unit['experience_points'], 0x7fffffff)
                or type(unit['promotions']) is not list or len(unit['promotions']) > ORDINARY_ACTION_LIMIT
                or any(not _uint(index) for index in unit['promotions'])
                or unit['promotions'] != sorted(set(unit['promotions']))):
            raise ValueError('Invalid owned promotion state')
        acquired[unit['unit_id']] = set(unit['promotions'])
    if list(acquired) != sorted(acquired):
        raise ValueError('Unordered promotion roster')
    if observation is not None and (
            (observation['player_id'], observation['turn']) != (player_id, turn)
            or list(acquired) != sorted(unit['id'] for unit in observation['units'])
            or any(unit['owner'] != player_id for unit in observation['units'])):
        raise ValueError('Promotion roster differs from the own-unit observation')
    offered = set()
    for action in value['offers']:
        validate_action(action)
        unit_id, index = action['unit_id'], action['index']
        key = (unit_id, index)
        if unit_id not in acquired or index in acquired[unit_id] or key in offered:
            raise ValueError('Foreign, duplicate or acquired promotion offer')
        offered.add(key)
    return value

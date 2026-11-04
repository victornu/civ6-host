"""Portable public state and offers for native parameterless unit orders.

The catalogue is a partial family. Legality is the recorded native Boolean;
readiness, activity and fortification values never add a strategic filter.
"""
from .action_budget import ORDINARY_ACTION_LIMIT

ACTION_FIELDS = {'unit_order': frozenset(('kind', 'unit_id', 'route', 'item_type', 'hash'))}
SKIP_TURN = 'UNITOPERATION_SKIP_TURN'
NAMES = {
    'command': ('UNITCOMMAND_WAKE', 'UNITCOMMAND_CANCEL'),
    'operation': ('UNITOPERATION_SLEEP', 'UNITOPERATION_FORTIFY',
                  'UNITOPERATION_HEAL', 'UNITOPERATION_RELIGIOUS_HEAL', SKIP_TURN),
}
UNQUALIFIED_UNIT_ORDERS = ('other_unit_commands_and_operations', 'spy_cancel_dialogue')


def _uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


def validate_action(action):
    if (type(action) is not dict or set(action) != ACTION_FIELDS['unit_order']
            or action['kind'] != 'unit_order' or not _uint(action['unit_id'])
            or not _uint(action['hash']) or type(action['route']) is not str
            or action['route'] not in NAMES or type(action['item_type']) is not str
            or action['item_type'] not in NAMES[action['route']]):
        raise ValueError('Invalid parameterless unit-order action')
    return action


def _key(action):
    return (action['unit_id'], action['route'], action['item_type'], action['hash'])


def validate_catalog(value, pid, turn, *, observation=None, unavailable=False, allow_skip=True):
    if (type(unavailable) is not bool or not _uint(pid, 63)
            or not _uint(turn, 0x7fffffff)):
        raise ValueError('Invalid unit-order query boundary')
    if unavailable:
        if value is not None:
            raise ValueError('Unavailable unit orders must be null')
        return value
    if (type(value) is not dict or set(value) != {'player_id', 'turn', 'units', 'offers'}
            or type(value['player_id']) is not int or value['player_id'] != pid
            or type(value['turn']) is not int or value['turn'] != turn
            or any(type(value[k]) is not list or len(value[k]) > ORDINARY_ACTION_LIMIT
                   for k in ('units', 'offers'))):
        raise ValueError('Invalid public unit-order catalogue')
    ids = []
    for row in value['units']:
        if (type(row) is not dict or set(row) != {'unit_id', 'activity_type', 'fortify_turns', 'ready'}
                or not _uint(row['unit_id']) or not _uint(row['fortify_turns'], 0x7fffffff)
                or type(row['activity_type']) is not int
                or not -0x80000000 <= row['activity_type'] <= 0x7fffffff
                or type(row['ready']) is not bool):
            raise ValueError('Invalid public unit-order activity/readiness')
        ids.append(row['unit_id'])
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unsorted unit-order roster')
    if observation is not None:
        if ((observation['player_id'], observation['turn']) != (pid, turn)
                or ids != sorted(unit['id'] for unit in observation['units'])
                or any(unit['owner'] != pid for unit in observation['units'])):
            raise ValueError('Unit-order roster differs from the public own-unit observation')
    own = set(ids)
    seen = set()
    for row in value['offers']:
        if (type(row) is not dict or set(row) != {'action', 'legal'}
                or type(row['legal']) is not bool):
            raise ValueError('Invalid native unit-order offer')
        action = validate_action(row['action'])
        if action['item_type'] == SKIP_TURN and not allow_skip:
            raise ValueError('Skip-turn order requires the v19 catalogue')
        key = _key(action)
        if action['unit_id'] not in own or key in seen:
            raise ValueError('Foreign or duplicate native unit-order offer')
        seen.add(key)
    return value


def actions(value):
    validate_catalog(value, value['player_id'], value['turn'])
    return [row['action'] for row in value['offers'] if row['legal']]


def validate_candidates(value, candidates):
    actual = [row['action'] for row in candidates if row['action']['kind'] == 'unit_order']
    expected = [] if value is None else actions(value)
    if (len(actual) != len(expected)
            or {_key(action) for action in actual} != {_key(action) for action in expected}):
        raise ValueError('Unit-order choices differ from exact legal native offers')

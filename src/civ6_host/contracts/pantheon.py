"""Pure public pantheon contract, preserving the native catalogue wire fields.

This validates an already queried catalogue. It makes no availability decision,
chooses no belief and requires neither GameCore nor the private source proofs.
"""
from .production_queue import _uint

KIND = 'pantheon'
FIELDS = frozenset(('kind', 'index', 'hash'))
MAX_CHOICES = 4096
_IDENTITY = {'status', 'player_id', 'current_game_turn'}
STATE_SCHEMA = 'civ6-host.pantheon.v2'


def validate(value, player_id, turn):
    _uint(player_id, 'pantheon player', 63)
    _uint(turn, 'pantheon turn')
    if (type(value) is not dict or type(value.get('player_id')) is not int
            or type(value.get('current_game_turn')) is not int
            or (value['player_id'], value['current_game_turn']) != (player_id, turn)):
        raise ValueError('Malformed or foreign pantheon catalogue')
    if value.get('status') == 'not_due':
        if (set(value) != _IDENTITY | {'reason'}
                or value['reason'] not in ('already_has_pantheon', 'cannot_create')):
            raise ValueError('Malformed pantheon not-due state')
        return value
    if (value.get('status') != 'catalog'
            or set(value) != _IDENTITY | {'operation', 'parameter_key', 'insert_key',
                                         'exclusive_value', 'choices'}
            or type(value['choices']) is not list or len(value['choices']) > MAX_CHOICES):
        raise ValueError('Malformed pantheon choices')
    for key in ('operation', 'parameter_key', 'insert_key', 'exclusive_value'):
        _uint(value[key], 'pantheon ' + key)
    if value['parameter_key'] == value['insert_key']:
        raise ValueError('Pantheon native parameter keys collide')
    previous = -1
    hashes = set()
    for choice in value['choices']:
        if type(choice) is not dict or set(choice) != {'index', 'hash'}:
            raise ValueError('Malformed pantheon belief identity')
        index = _uint(choice['index'], 'pantheon index', 0x7fffffff)
        row_hash = _uint(choice['hash'], 'pantheon hash')
        if index <= previous or row_hash in hashes:
            raise ValueError('Unordered or ambiguous pantheon choices')
        previous = index
        hashes.add(row_hash)
    return value


def actions(value):
    if value is None:
        return []
    validate(value, value['player_id'], value['current_game_turn'])
    if value['status'] == 'not_due':
        return []
    return [dict(kind=KIND, **row) for row in value['choices']]


def validate_action(value):
    if type(value) is not dict or set(value) != FIELDS or value['kind'] != KIND:
        raise ValueError('Malformed pantheon action')
    _uint(value['index'], 'pantheon index', 0x7fffffff)
    _uint(value['hash'], 'pantheon hash')
    return value


def validate_state(value, player_id, turn):
    """Own native index plus the unchanged choice catalogue, explicitly v2."""
    _uint(player_id, 'pantheon player', 63)
    _uint(turn, 'pantheon turn')
    if (type(value) is not dict
            or set(value) != {'schema', 'player_id', 'turn', 'pantheon_index', 'catalogue'}
            or value['schema'] != STATE_SCHEMA
            or type(value['player_id']) is not int or type(value['turn']) is not int
            or (value['player_id'], value['turn']) != (player_id, turn)
            or type(value['pantheon_index']) is not int
            or not -1 <= value['pantheon_index'] <= 0x7fffffff):
        raise ValueError('Malformed or foreign public pantheon state')
    catalogue = validate(value['catalogue'], player_id, turn)
    already = catalogue['status'] == 'not_due' and catalogue['reason'] == 'already_has_pantheon'
    if already != (value['pantheon_index'] >= 0):
        raise ValueError('Native pantheon index differs from the catalogue reason')
    return value


def state_actions(value):
    if value is None:
        return []
    validate_state(value, value['player_id'], value['turn'])
    return actions(value['catalogue'])

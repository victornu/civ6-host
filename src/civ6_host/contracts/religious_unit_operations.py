"""Own religious-unit information and the original visible operation choices.

Native UI queries own eligibility, charges and religion. This contract checks
their representation and identity without selecting a city or computing rules.
"""
from copy import deepcopy
from math import isfinite
from .religion_beliefs import _int, _keys

SCHEMA = 'civ6-host.religious-unit-operations.v1'
KINDS = ('spread_religion', 'evangelize_belief', 'launch_inquisition', 'remove_heresy')
FIELDS = {'kind', 'unit_id', 'x', 'y'}
UNIT_FIELDS = {'unit_id', 'x', 'y', 'moves_remaining', 'religion_type',
               'spread_charges', 'operations'}


def validate_action(action):
    _keys(action, FIELDS)
    if action['kind'] not in KINDS:
        raise ValueError('Unexpected religious unit operation')
    _int(action['unit_id'], 0, 0xffffffff)
    _int(action['x'], -(2**31))
    _int(action['y'], -(2**31))
    return action


def _moves(value):
    if (type(value) not in (int, float) or not -(2**31) <= value*256 <= 2**31-1
            or not isfinite(value)
            or int(value*256) != value*256):
        raise ValueError('Religious unit movement must preserve its native Q8 value')
    return value


def validate(value, player_id, turn, *, observation=None):
    _int(player_id, 0, 63)
    _int(turn, 0, 0xffffffff)
    _keys(value, {'schema', 'player_id', 'turn', 'inquisition_started', 'units'})
    if (value['schema'] != SCHEMA or _int(value['player_id'], 0, 63) != player_id
            or _int(value['turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign religious unit boundary')
    if type(value['inquisition_started']) is not bool:
        raise ValueError('Inquisition state must be the native actor Boolean')
    observed = None
    if observation is not None:
        if (type(observation) is not dict or _int(observation.get('player_id'), 0, 63) != player_id
                or _int(observation.get('turn'), 0, 0xffffffff) != turn
                or type(observation.get('units')) is not list):
            raise ValueError('Religious units require their own observation')
        width, height = _int(observation.get('width'), 1), _int(observation.get('height'), 1)
        observed = {}
        for unit in observation['units']:
            if type(unit) is not dict:
                raise ValueError('Malformed public own unit')
            _int(unit.get('id'), 0, 0xffffffff)
            if _int(unit.get('owner'), 0, 63) != player_id or unit['id'] in observed:
                raise ValueError('Foreign or duplicate public own unit')
            _int(unit.get('x'), 0, width-1)
            _int(unit.get('y'), 0, height-1)
            _moves(unit.get('moves'))
            observed[unit['id']] = unit
    rows = value['units']
    if type(rows) is not list or len(rows) > 4096:
        raise ValueError('Malformed religious unit roster')
    ids = []
    for row in rows:
        _keys(row, UNIT_FIELDS)
        validate_action(dict(kind=KINDS[0], unit_id=row['unit_id'], x=row['x'], y=row['y']))
        _moves(row['moves_remaining'])
        _int(row['religion_type'], -(2**31))
        _int(row['spread_charges'], -(2**31))
        operations = row['operations']
        if type(operations) is not list or len(operations) > len(KINDS):
            raise ValueError('Malformed visible religious operation set')
        names = []
        for operation in operations:
            _keys(operation, {'operation', 'visible', 'available'})
            if (operation['operation'] not in KINDS or operation['visible'] is not True
                    or type(operation['available']) is not bool):
                raise ValueError('Only actually queried visible native operations belong here')
            names.append(operation['operation'])
        if names != [kind for kind in KINDS if kind in names]:
            raise ValueError('Duplicate or unordered religious operations')
        if operations and row['moves_remaining'] <= 0:
            raise ValueError('Religious operation contradicts the original UI movement gate')
        if observed is not None:
            unit = observed.get(row['unit_id'])
            if (unit is None or (row['x'], row['y']) != (unit['x'], unit['y'])
                    or row['moves_remaining'] != unit['moves']):
                raise ValueError('Religious unit differs from its own public observation')
        ids.append(row['unit_id'])
    if ids != sorted(set(ids)) or observed is not None and ids != sorted(observed):
        raise ValueError('Religious roster must retain every own unit exactly once')
    return value


def project(value, player_id, turn, *, observation=None):
    """Copy native public data without adding or removing any native choice."""
    _keys(value, {'player_id', 'current_game_turn', 'inquisition_started', 'units'})
    if (_int(value['player_id'], 0, 63) != player_id
            or _int(value['current_game_turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign native religious unit catalogue')
    result = dict(schema=SCHEMA, player_id=player_id, turn=turn,
                  inquisition_started=value['inquisition_started'], units=deepcopy(value['units']))
    return validate(result, player_id, turn, observation=observation)


def actions(value):
    if value is None:
        return []
    validate(value, value['player_id'], value['turn'])
    return [dict(kind=op['operation'], unit_id=row['unit_id'], x=row['x'], y=row['y'])
            for row in value['units'] for op in row['operations'] if op['available']]

"""Own Great Person command state and exact official activation offers.

This is UNITCOMMAND_ACTIVATE_GREAT_PERSON, distinct from the Prophet founding
operation. Native visibility and availability supply choices. No class,
movement, charge or strategic-effect rule is reimplemented here.
"""
from copy import deepcopy
from .religion_beliefs import _int, _keys

SCHEMA = 'civ6-host.great-person-activation.v1'
KIND = 'activate_great_person'
OPERATION = 0x165502d8
FIELDS = {'kind', 'unit_id', 'x', 'y'}
UNIT_FIELDS = {'unit_id', 'x', 'y', 'individual_index', 'class_index',
               'charges', 'visible', 'available'}


def validate_action(action):
    _keys(action, FIELDS)
    if action['kind'] != KIND:
        raise ValueError('Unexpected Great Person activation action')
    _int(action['unit_id'], 0, 0xffffffff)
    _int(action['x'], -(2**31))
    _int(action['y'], -(2**31))
    return action


def validate(value, player_id, turn, *, observation=None):
    _int(player_id, 0, 63)
    _int(turn, 0, 0xffffffff)
    _keys(value, {'schema', 'player_id', 'turn', 'operation', 'units'})
    if (value['schema'] != SCHEMA or _int(value['player_id'], 0, 63) != player_id
            or _int(value['turn'], 0, 0xffffffff) != turn
            or _int(value['operation'], 0, 0xffffffff) != OPERATION):
        raise ValueError('Foreign Great Person activation boundary or command')
    observed = None
    if observation is not None:
        if (type(observation) is not dict or _int(observation.get('player_id'), 0, 63) != player_id
                or _int(observation.get('turn'), 0, 0xffffffff) != turn
                or type(observation.get('units')) is not list):
            raise ValueError('Great Person activation requires its own-unit observation')
        width, height = _int(observation.get('width'), 1), _int(observation.get('height'), 1)
        observed = {}
        for unit in observation['units']:
            if type(unit) is not dict:
                raise ValueError('Malformed public own-unit row')
            _int(unit.get('id'), 0, 0xffffffff)
            if _int(unit.get('owner'), 0, 63) != player_id or unit['id'] in observed:
                raise ValueError('Foreign or duplicate public own-unit row')
            _int(unit.get('x'), 0, width-1)
            _int(unit.get('y'), 0, height-1)
            observed[unit['id']] = unit
    rows = value['units']
    if type(rows) is not list or len(rows) > 4096:
        raise ValueError('Malformed Great Person activation roster')
    ids = []
    for row in rows:
        _keys(row, UNIT_FIELDS)
        validate_action(dict(kind=KIND, unit_id=row['unit_id'], x=row['x'], y=row['y']))
        _int(row['individual_index'])
        _int(row['class_index'])
        _int(row['charges'], -(2**31))
        if type(row['visible']) is not bool or type(row['available']) is not bool:
            raise ValueError('Great Person activation flags must be native booleans')
        if observed is not None:
            unit = observed.get(row['unit_id'])
            if unit is None or (row['x'], row['y']) != (unit['x'], unit['y']):
                raise ValueError('Great Person activation differs from the public own unit')
        ids.append(row['unit_id'])
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unordered Great Person activation units')
    return value


def project(value, player_id, turn, *, observation=None):
    """Detach the native public scalar roster; no eligibility recalculation."""
    _keys(value, {'player_id', 'current_game_turn', 'operation', 'units'})
    if (_int(value['player_id'], 0, 63) != player_id
            or _int(value['current_game_turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign native Great Person activation catalogue')
    result = dict(schema=SCHEMA, player_id=player_id, turn=turn,
                  operation=value['operation'], units=deepcopy(value['units']))
    return validate(result, player_id, turn, observation=observation)


def actions(value):
    if value is None:
        return []
    validate(value, value['player_id'], value['turn'])
    return [dict(kind=KIND, unit_id=row['unit_id'], x=row['x'], y=row['y'])
            for row in value['units'] if row['visible'] and row['available']]

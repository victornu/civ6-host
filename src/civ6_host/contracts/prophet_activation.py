"""Explicit native Great Prophet activation; no named religion or navigation.

Own religion uses the existing public projection. Candidates retain the native
unit identifier and location, without a Great Person index or derived city.
"""
from .religion_beliefs import _int, _keys, _own, project_snapshot

SCHEMA = 'civ6-host.prophet-activation.v1'
KIND = 'activate_prophet'
FIELDS = {'kind', 'unit_id', 'x', 'y'}


def validate_action(action):
    _keys(action, FIELDS)
    if action['kind'] != KIND:
        raise ValueError('Unexpected Prophet activation action')
    _int(action['unit_id'], 0, 0xffffffff)
    _int(action['x'], -(2**31))
    _int(action['y'], -(2**31))
    return action


def _activation(value, own, pid, turn, observation):
    if (own['religion_type_created'] != -1 or not own['has_religious_founding_unit']
            or own['holy_city_present']):
        if value is not None:
            raise ValueError('Prophet activation lacks its unactivated native state')
        return
    _keys(value, {'status', 'player_id', 'current_game_turn', 'operation',
                  'prophet_type_index', 'candidates'})
    if (value['status'] not in ('catalog', 'not_due')
            or _int(value['player_id'], 0, 63) != pid
            or _int(value['current_game_turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign or stale Prophet activation catalogue')
    _int(value['operation'], 0, 0xffffffff)
    _int(value['prophet_type_index'])
    rows = value['candidates']
    if (type(rows) is not list or len(rows) > 4096
            or bool(rows) != (value['status'] == 'catalog')):
        raise ValueError('Malformed native Prophet activation candidates')
    units = None
    if observation is not None:
        observed = observation.get('units')
        if type(observed) is not list:
            raise ValueError('Prophet activation requires the public own-unit set')
        units = {}
        for unit in observed:
            if type(unit) is not dict:
                raise ValueError('Malformed public own-unit row')
            _int(unit.get('id'), 0, 0xffffffff)
            _int(unit.get('owner'), 0, 63)
            _int(unit.get('x'), -(2**31))
            _int(unit.get('y'), -(2**31))
            if unit['owner'] != pid or unit['id'] in units:
                raise ValueError('Foreign or duplicate public own-unit row')
            units[unit['id']] = unit
    ids = []
    for row in rows:
        _keys(row, {'unit_id', 'x', 'y'})
        validate_action(dict(kind=KIND, **row))
        ids.append(row['unit_id'])
        if units is not None:
            unit = units.get(row['unit_id'])
            if unit is None or (unit['x'], unit['y']) != (row['x'], row['y']):
                raise ValueError('Prophet activation differs from the public own unit')
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unordered Prophet activation choices')


def validate(value, player_id, turn, *, observation=None):
    _int(player_id, 0, 63)
    _int(turn, 0, 0xffffffff)
    _keys(value, {'schema', 'player_id', 'turn', 'own', 'activation'})
    if (value['schema'] != SCHEMA or _int(value['player_id'], 0, 63) != player_id
            or _int(value['turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign public Prophet activation boundary')
    if observation is not None:
        if (type(observation) is not dict or type(observation.get('turn')) is not int
                or observation['turn'] != turn):
            raise ValueError('Stale public Prophet observation')
    _own(value['own'], player_id, observation)
    _activation(value['activation'], value['own'], player_id, turn, observation)
    return value


def actions(value):
    if value is None or value['activation'] is None:
        return []
    return [dict(kind=KIND, **row) for row in value['activation']['candidates']]

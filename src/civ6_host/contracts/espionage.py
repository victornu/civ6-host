"""Portable player-scoped espionage state and explicit spy choices.

Mission coordinates identify the offered target.  They remain part of a start
choice even though that native operation accepts no coordinate parameters.
"""

import re

SCHEMA = 'civ6-host.espionage.v1'
_MAX_I32 = 0x7fffffff
_MIN_I32 = -0x80000000
_MAX_U32 = 0xffffffff
_MAX_ROWS = 4096
_MAX_TEXT_BYTES = 32768
_CATALOGUE_FIELDS = frozenset((
    'schema', 'player_id', 'turn', 'width', 'height', 'capacity',
    'spies', 'captured', 'off_map', 'history', 'offers',
))
_SPY_FIELDS = frozenset((
    'unit_id', 'name', 'level', 'x', 'y', 'operation', 'turns_remaining',
))
_CAPTURED_FIELDS = frozenset(('owner', 'captor', 'name_index', 'name', 'level'))
_OFF_MAP_FIELDS = frozenset(('name', 'level', 'return_turn', 'x', 'y'))
_HISTORY_FIELDS = frozenset((
    'name', 'level', 'operation', 'completion_turn', 'initial_result',
    'escape_result', 'city_name', 'plot_id', 'loot_info',
))
_OFFER_FIELDS = frozenset((
    'action', 'turns', 'success_percent', 'failure_percent',
    'captured_or_killed_percent',
))
ACTION_FIELDS = {
    'spy_travel': frozenset(('kind', 'unit_id', 'city_owner', 'city_id', 'x', 'y')),
    'spy_mission': frozenset((
        'kind', 'unit_id', 'operation_type', 'operation_hash', 'mode',
        'x', 'y', 'plot_id',
    )),
    'spy_cancel': frozenset(('kind', 'unit_id')),
    'spy_escape': frozenset(('kind', 'unit_id', 'district_index')),
}


def _shape(value, fields, label):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Malformed espionage ' + label)


def _integer(value, label, minimum=0, maximum=_MAX_I32):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid espionage ' + label)
    return value


def _text(value, label):
    if type(value) is not str or len(value.encode('utf8')) > _MAX_TEXT_BYTES:
        raise ValueError('Invalid espionage ' + label)


def _rows(value, label, maximum=_MAX_ROWS):
    if type(value) is not list or len(value) > maximum:
        raise ValueError('Unbounded or malformed espionage ' + label)
    return value


def _dimensions(width, height):
    _integer(width, 'width', 1, 16384)
    _integer(height, 'height', 1, 16384)


def _coordinates(value, width, height):
    _integer(value['x'], 'x', 0, width - 1)
    _integer(value['y'], 'y', 0, height - 1)


def _unique(identity, seen, label):
    if identity in seen:
        raise ValueError('Duplicate espionage ' + label)
    seen.add(identity)


def validate_action(action, width=None, height=None):
    """Validate one exact action envelope; native legality stays with its offer.

    Without map dimensions, only transport coordinate/plot bounds are checked.
    Catalogue validation supplies the map and binds its linear plot identity.
    """
    has_map = width is not None or height is not None
    if has_map:
        _dimensions(width, height)
    else:
        width = height = 16384
    kind = action.get('kind') if type(action) is dict else None
    if type(kind) is not str or kind not in ACTION_FIELDS:
        raise ValueError('Unknown or malformed espionage action')
    _shape(action, ACTION_FIELDS[kind], 'action')
    _integer(action['unit_id'], 'unit identity', 0, _MAX_U32)
    if kind == 'spy_travel':
        _integer(action['city_owner'], 'city owner', 0, 63)
        _integer(action['city_id'], 'city identity', 0, _MAX_U32)
        _coordinates(action, width, height)
    elif kind == 'spy_mission':
        operation_type = action['operation_type']
        if (type(operation_type) is not str
                or not re.fullmatch(r'UNITOPERATION_[A-Z0-9_]{1,100}', operation_type)
                or type(action['mode']) is not str
                or action['mode'] not in ('start', 'counterspy', 'renew')):
            raise ValueError('Invalid espionage mission type or mode')
        _integer(action['operation_hash'], 'operation hash', 0, _MAX_U32)
        _coordinates(action, width, height)
        _integer(action['plot_id'], 'target plot', 0,
                 width * height - 1 if has_map else 16383)
        if has_map and action['plot_id'] != action['y'] * width + action['x']:
            raise ValueError('Espionage target plot differs from its coordinates')
    elif kind == 'spy_escape':
        _integer(action['district_index'], 'escape district')
    return action


def validate_catalogue(value, pid, turn):
    """Validate public state, provenance, and bounded, distinct own-spy choices."""
    _integer(pid, 'player', 0, 63)
    _integer(turn, 'turn')
    _shape(value, _CATALOGUE_FIELDS, 'catalogue')
    if (type(value['schema']) is not str or value['schema'] != SCHEMA
            or type(value['player_id']) is not int or value['player_id'] != pid
            or type(value['turn']) is not int or value['turn'] != turn):
        raise ValueError('Foreign or malformed espionage catalogue')
    width, height = value['width'], value['height']
    _dimensions(width, height)
    if width * height > 16384:
        raise ValueError('Espionage map exceeds its bounded area')
    _integer(value['capacity'], 'capacity')

    spies = set()
    for row in _rows(value['spies'], 'roster'):
        _shape(row, _SPY_FIELDS, 'spy')
        _integer(row['unit_id'], 'unit identity', 0, _MAX_U32)
        _text(row['name'], 'spy name')
        _integer(row['level'], 'spy level')
        _coordinates(row, width, height)
        _integer(row['operation'], 'operation index', -1)
        _integer(row['turns_remaining'], 'remaining turns', _MIN_I32)
        _unique(row['unit_id'], spies, 'spy identity')

    captured = set()
    for row in _rows(value['captured'], 'captured roster'):
        _shape(row, _CAPTURED_FIELDS, 'captured spy')
        _integer(row['owner'], 'captured owner', 0, 63)
        _integer(row['captor'], 'captor', 0, 63)
        _integer(row['name_index'], 'captured name index')
        _text(row['name'], 'captured spy name')
        if pid not in (row['owner'], row['captor']):
            raise ValueError('Foreign espionage prisoner information')
        if row['owner'] == pid:
            _integer(row['level'], 'captured own spy level')
        elif row['level'] is not None:
            raise ValueError('Enemy captured spy level is not public information')
        _unique((row['owner'], row['name_index']), captured, 'captured spy identity')

    off_map = set()
    for row in _rows(value['off_map'], 'off-map roster'):
        _shape(row, _OFF_MAP_FIELDS, 'off-map spy')
        _text(row['name'], 'off-map spy name')
        _integer(row['level'], 'off-map spy level')
        _integer(row['return_turn'], 'return turn', _MIN_I32)
        if row['return_turn'] == -1:
            raise ValueError('Espionage off-map spy has no visible return turn')
        _coordinates(row, width, height)
        _unique(tuple(row[key] for key in sorted(_OFF_MAP_FIELDS)), off_map, 'off-map spy')

    history = set()
    for row in _rows(value['history'], 'history', 10):
        _shape(row, _HISTORY_FIELDS, 'history row')
        _text(row['name'], 'history spy name')
        _text(row['city_name'], 'history city name')
        for key in _HISTORY_FIELDS - {'name', 'city_name', 'plot_id'}:
            _integer(row[key], 'history ' + key, _MIN_I32)
        _integer(row['plot_id'], 'history plot', -1, width * height - 1)
        _unique(tuple(row[key] for key in sorted(_HISTORY_FIELDS)), history, 'history row')

    offered = set()
    for row in _rows(value['offers'], 'offers'):
        _shape(row, _OFFER_FIELDS, 'offer')
        action = validate_action(row['action'], width, height)
        if action['unit_id'] not in spies:
            raise ValueError('Espionage action does not refer to an own spy')
        _integer(row['turns'], 'offer turns', -1)
        for key in ('success_percent', 'failure_percent', 'captured_or_killed_percent'):
            _integer(row[key], key, -1, 100)
        _unique(tuple(sorted(action.items())), offered, 'offered action')
    return value


def actions(value):
    """Project every offered choice in native order without sharing action dicts."""
    if value is None:
        return []
    _shape(value, _CATALOGUE_FIELDS, 'catalogue')
    validate_catalogue(value, value['player_id'], value['turn'])
    return [dict(row['action']) for row in value['offers']]


def compare_own(value, observation):
    """Bind the roster and all choices to matching player-owned observed units."""
    if (type(observation) is not dict
            or not {'player_id', 'turn', 'width', 'height', 'units'} <= set(observation)):
        raise ValueError('Malformed espionage observation')
    validate_catalogue(value, observation['player_id'], observation['turn'])
    _dimensions(observation['width'], observation['height'])
    if (value['width'], value['height']) != (observation['width'], observation['height']):
        raise ValueError('Espionage map differs from the own observation')
    units = {}
    for unit in _rows(observation['units'], 'observed units'):
        if (type(unit) is not dict
                or not {'id', 'owner', 'x', 'y'} <= set(unit)):
            raise ValueError('Malformed espionage observed unit')
        _integer(unit['id'], 'observed unit identity', 0, _MAX_U32)
        _integer(unit['owner'], 'observed unit owner', 0, 63)
        _coordinates(unit, value['width'], value['height'])
        if unit['id'] in units:
            raise ValueError('Duplicate espionage observed unit identity')
        units[unit['id']] = unit
    for spy in value['spies']:
        unit = units.get(spy['unit_id'])
        if (unit is None or unit['owner'] != value['player_id']
                or (unit['x'], unit['y']) != (spy['x'], spy['y'])):
            raise ValueError('Espionage roster differs from the own observation')
    return value

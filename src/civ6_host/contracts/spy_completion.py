"""Portable public spy completion and explicitly offered popup choices.

An event identity distinguishes the current completion from historical results.
This contract validates retained offers; it does not establish native legality
or infer that a mission can be renewed from history alone.
"""
import re

SCHEMA = 'civ6-host.spy-completion.v1'
_MAX_I32 = 0x7fffffff
_MIN_I32 = -0x80000000
_MAX_U32 = 0xffffffff
_MAX_TEXT_BYTES = 32768
_CATALOGUE_FIELDS = frozenset((
    'schema', 'player_id', 'turn', 'width', 'height', 'current', 'offers',
))
_CURRENT_FIELDS = frozenset((
    'event_sequence', 'mission_id', 'name', 'level', 'operation',
    'completion_turn', 'initial_result', 'escape_result', 'city_name',
    'plot_id', 'loot_info',
))
_OFFER_FIELDS = frozenset((
    'action', 'turns', 'success_percent', 'failure_percent',
    'captured_or_killed_percent',
))
ACTION_FIELDS = {
    'spy_renew': frozenset((
        'kind', 'unit_id', 'event_sequence', 'mission_id', 'operation_type',
        'operation_hash', 'x', 'y', 'plot_id',
    )),
    'spy_completion_dismiss': frozenset(('kind', 'event_sequence', 'mission_id')),
}


def _shape(value, fields, label):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Malformed spy completion ' + label)


def _integer(value, label, minimum=0, maximum=_MAX_I32):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid spy completion ' + label)


def _text(value, label):
    if type(value) is not str or len(value.encode('utf8')) > _MAX_TEXT_BYTES:
        raise ValueError('Invalid spy completion ' + label)


def _dimensions(width, height):
    _integer(width, 'width', 1, 16384)
    _integer(height, 'height', 1, 16384)


def _identity(value):
    _integer(value['event_sequence'], 'event sequence', 0, _MAX_U32)
    _integer(value['mission_id'], 'mission identity')


def validate_action(action, width=None, height=None):
    """Validate exact transport fields, optionally against a known map."""
    has_map = width is not None or height is not None
    if has_map:
        _dimensions(width, height)
    else:
        width = height = 16384
    kind = action.get('kind') if type(action) is dict else None
    if type(kind) is not str or kind not in ACTION_FIELDS:
        raise ValueError('Unknown or malformed spy completion action')
    _shape(action, ACTION_FIELDS[kind], 'action')
    _identity(action)
    if kind == 'spy_renew':
        _integer(action['unit_id'], 'unit identity', 0, _MAX_U32)
        if (type(action['operation_type']) is not str
                or not re.fullmatch(r'UNITOPERATION_[A-Z0-9_]{1,100}', action['operation_type'])):
            raise ValueError('Invalid spy completion operation type')
        _integer(action['operation_hash'], 'operation hash', 0, _MAX_U32)
        _integer(action['x'], 'target x', 0, width - 1)
        _integer(action['y'], 'target y', 0, height - 1)
        _integer(action['plot_id'], 'target plot', 0,
                 width * height - 1 if has_map else 16383)
        if has_map and action['plot_id'] != action['y'] * width + action['x']:
            raise ValueError('Spy completion target plot differs from its coordinates')
    return action


def validate_catalogue(value, pid, turn):
    """Bind a single public completion and its exact explicit choices."""
    _integer(pid, 'player', 0, 63)
    _integer(turn, 'turn')
    _shape(value, _CATALOGUE_FIELDS, 'catalogue')
    if (type(value['schema']) is not str or value['schema'] != SCHEMA
            or type(value['player_id']) is not int or value['player_id'] != pid
            or type(value['turn']) is not int or value['turn'] != turn):
        raise ValueError('Foreign or malformed spy completion catalogue')
    width, height = value['width'], value['height']
    _dimensions(width, height)
    if width * height > 16384:
        raise ValueError('Spy completion map exceeds its bounded area')
    if type(value['offers']) is not list or len(value['offers']) > 2:
        raise ValueError('Unbounded or malformed spy completion offers')
    current = value['current']
    if current is None:
        if value['offers']:
            raise ValueError('Spy completion choices lack their current event')
        return value
    _shape(current, _CURRENT_FIELDS, 'current event')
    _identity(current)
    for key in ('name', 'city_name'):
        _text(current[key], key)
    for key in _CURRENT_FIELDS - {'event_sequence', 'mission_id', 'name', 'city_name', 'plot_id'}:
        _integer(current[key], key, _MIN_I32)
    _integer(current['plot_id'], 'historical plot', -1, width * height - 1)
    counts = {kind: 0 for kind in ACTION_FIELDS}
    for row in value['offers']:
        _shape(row, _OFFER_FIELDS, 'offer')
        action = validate_action(row['action'], width, height)
        if any(action[key] != current[key] for key in ('event_sequence', 'mission_id')):
            raise ValueError('Spy completion choice belongs to another event')
        if action['kind'] == 'spy_renew' and action['plot_id'] != current['plot_id']:
            raise ValueError('Spy renewal target differs from the completed mission')
        counts[action['kind']] += 1
        _integer(row['turns'], 'offer turns', -1)
        for key in ('success_percent', 'failure_percent', 'captured_or_killed_percent'):
            _integer(row[key], key, -1, 100)
    if counts['spy_completion_dismiss'] != 1 or counts['spy_renew'] > 1:
        raise ValueError('Spy completion requires one dismissal and at most one renewal')
    return value


def actions(value):
    """Copy every offered action in order, without deriving another choice."""
    if value is None:
        return []
    _shape(value, _CATALOGUE_FIELDS, 'catalogue')
    validate_catalogue(value, value['player_id'], value['turn'])
    return [dict(row['action']) for row in value['offers']]


def compare_own(value, observation):
    """Bind renewal to the observed own unit without restricting its movement."""
    if (type(observation) is not dict
            or not {'player_id', 'turn', 'width', 'height', 'units'} <= set(observation)):
        raise ValueError('Malformed spy completion observation')
    validate_catalogue(value, observation['player_id'], observation['turn'])
    _dimensions(observation['width'], observation['height'])
    if (value['width'], value['height']) != (observation['width'], observation['height']):
        raise ValueError('Spy completion map differs from the own observation')
    if type(observation['units']) is not list or len(observation['units']) > 4096:
        raise ValueError('Unbounded or malformed spy completion own units')
    units = {}
    for unit in observation['units']:
        if type(unit) is not dict or not {'id', 'owner'} <= set(unit):
            raise ValueError('Malformed spy completion observed unit')
        _integer(unit['id'], 'observed unit identity', 0, _MAX_U32)
        _integer(unit['owner'], 'observed unit owner', 0, 63)
        if unit['id'] in units:
            raise ValueError('Duplicate spy completion observed unit identity')
        units[unit['id']] = unit
    for action in actions(value):
        if action['kind'] != 'spy_renew':
            continue
        unit = units.get(action['unit_id'])
        if unit is None or unit['owner'] != value['player_id']:
            raise ValueError('Spy renewal does not refer to an observed own unit')
        if 'name' in unit:
            _text(unit['name'], 'observed unit name')
            if unit['name'] != value['current']['name']:
                raise ValueError('Spy renewal name differs from the completed mission')
    return value


__all__ = ['SCHEMA', 'ACTION_FIELDS', 'validate_action', 'validate_catalogue', 'actions', 'compare_own']

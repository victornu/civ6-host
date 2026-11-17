"""Public current Great People timeline and own points, not the whole popup.

The native reader supplies visibility, eligibility flags and quotes. This
portable contract checks data shape/precision only and admits no commands.
Past timelines and other players' points are outside this query's scope.
"""
from copy import deepcopy
import re

SCHEMA = 'civ6-host.great-people.v1'
SCHEMA_V2 = 'civ6-host.great-people.v2'
SCOPE = ('current_timeline', 'own_points')
MAX_TIMELINE = 4096
MAX_CLASSES = 64
INT_MAX = 0x7fffffff
CURRENCIES = ('YIELD_GOLD', 'YIELD_FAITH')


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('Great People fields differ from the public contract')


def _int(value, low=0, high=INT_MAX, *, optional=False):
    if optional and value is None:
        return
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Great People integer is outside its native domain')


def _bool(value):
    if type(value) is not bool:
        raise ValueError('Great People flags require native booleans')


def _points(value):
    if (type(value) not in (int, float) or not -8388608 <= value < 8388608
            or int(value * 256) != value * 256):
        raise ValueError('Great People points exceed native fixed-point precision')


def _key(value, prefix):
    if type(value) is not str or len(value) > 120 or re.fullmatch(prefix+r'[A-Z0-9_]+', value) is None:
        raise ValueError('Malformed Great People type key')


def _timeline(row, classes):
    _keys(row, {'individual_index', 'item_type', 'class_index', 'era_index', 'claimed',
                'claimant_player_id', 'recruitment', 'rejection', 'patronage'})
    _int(row['individual_index'], optional=True)
    _int(row['class_index'], optional=True)
    _int(row['era_index'], optional=True)
    _int(row['claimant_player_id'], 0, 63, optional=True)
    _bool(row['claimed'])
    if (row['class_index'] is not None and row['class_index'] not in classes
            or not row['claimed'] and row['claimant_player_id'] is not None):
        raise ValueError('Great People timeline identity is inconsistent')
    if row['individual_index'] is None:
        if any(row[key] is not None for key in ('item_type', 'recruitment', 'rejection', 'patronage')):
            raise ValueError('Great People placeholder contains individual data')
        return
    _key(row['item_type'], 'GREAT_PERSON_INDIVIDUAL_')
    for name, native, minimum in (('recruitment', 'native_can_recruit', 0),
                                  ('rejection', 'native_can_reject', -(2**31))):
        value = row[name]
        _keys(value, {'cost', native, 'available'})
        _int(value['cost'], minimum, optional=True)
        _bool(value[native])
        _bool(value['available'])
    _keys(row['patronage'], CURRENCIES)
    for value in row['patronage'].values():
        _keys(value, {'cost', 'native_can_patronize', 'visible', 'available', 'no_patronage'})
        _int(value['cost'], -(2**31), optional=True)
        for key in ('native_can_patronize', 'visible', 'available', 'no_patronage'):
            _bool(value[key])


def validate(value, player_id, turn, *, observation=None):
    _int(player_id, 0, 63)
    _int(turn)
    fields = {'schema', 'player_id', 'turn', 'capabilities', 'no_patronage', 'own_points', 'timeline'}
    xp2 = type(value) is dict and value.get('schema') == SCHEMA_V2
    _keys(value, fields | {'read_only'} if xp2 else fields)
    if xp2:
        _bool(value['read_only'])
    read_only = xp2 and value['read_only']
    _int(value['player_id'], 0, 63)
    _int(value['turn'])
    if value['schema'] not in (SCHEMA, SCHEMA_V2) or value['player_id'] != player_id or value['turn'] != turn:
        raise ValueError('Foreign or stale Great People query')
    if observation is not None:
        if (type(observation) is not dict or type(observation.get('player_id')) is not int
                or type(observation.get('turn')) is not int
                or observation['player_id'] != player_id or observation['turn'] != turn):
            raise ValueError('Great People query differs from its actor observation')
    _keys(value['capabilities'], ('recruit', 'reject', *CURRENCIES))
    _keys(value['no_patronage'], CURRENCIES)
    for flags in (value['capabilities'], value['no_patronage']):
        for flag in flags.values():
            _bool(flag)
    points = value['own_points']
    if type(points) is not list or not 0 < len(points) <= MAX_CLASSES:
        raise ValueError('Great People query omitted or exceeded own point classes')
    classes = []
    for row in points:
        _keys(row, {'class_index', 'class_type', 'max_instances', 'instances_earned',
                    'points_total', 'points_per_turn'})
        _int(row['class_index'])
        _key(row['class_type'], 'GREAT_PERSON_CLASS_')
        _int(row['max_instances'], optional=True)
        _int(row['instances_earned'])
        _points(row['points_total'])
        _points(row['points_per_turn'])
        classes.append(row['class_index'])
    if classes != sorted(set(classes)):
        raise ValueError('Duplicate or unordered own Great People classes')
    timeline = value['timeline']
    if type(timeline) is not list or len(timeline) > MAX_TIMELINE:
        raise ValueError('Great People timeline exceeds its bound')
    individuals = set()
    for row in timeline:
        _timeline(row, classes)
        individual = row['individual_index']
        if individual is not None:
            if read_only and any(offer['available'] for offer in
                    (row['recruitment'], row['rejection'], *row['patronage'].values())):
                raise ValueError('Read-only Great People panel includes an available choice')
            if individual in individuals:
                raise ValueError('Duplicate current Great People individual')
            individuals.add(individual)
    return value


def project(value, player_id, turn, *, observation=None):
    """Copy only the exact already-public reader result; infer no UI rules."""
    return deepcopy(validate(value, player_id, turn, observation=observation))

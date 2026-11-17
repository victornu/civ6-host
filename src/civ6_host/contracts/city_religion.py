"""Versioned religious information for the acting player's own cities.

Version one preserves native majority indices. Version two adds the active
religion rows and numerical values displayed by the original city religion UI.
Native Lua performs its pressure rounding; this contract never recomputes it.
"""
from .production_queue import _uint


SCHEMA = 'civ6-host.city-religion.v1'
DETAILS_SCHEMA = 'civ6-host.city-religion.v2'
MAX_CITIES = 4096
MAX_RELIGIONS = 4096


def _validate_majority(value, player_id, turn, *, observation=None):
    _uint(player_id, 'city religion player', 63)
    _uint(turn, 'city religion turn', 0x7fffffff)
    if (type(value) is not dict or set(value) != {'schema','player_id','turn','cities'}
            or value['schema'] != SCHEMA or type(value['player_id']) is not int
            or type(value['turn']) is not int or (value['player_id'],value['turn']) != (player_id,turn)
            or type(value['cities']) is not list or len(value['cities']) > MAX_CITIES):
        raise ValueError('Malformed or foreign city religion state')
    own_cities = None
    if observation is not None:
        if (type(observation.get('player_id')) is not int or type(observation.get('turn')) is not int
                or (observation['player_id'],observation['turn']) != (player_id,turn)
                or type(observation.get('cities')) is not list or len(observation['cities']) > MAX_CITIES):
            raise ValueError('City religion observation belongs to another boundary')
        own_cities = set()
        for city in observation['cities']:
            if type(city) is not dict or type(city.get('owner')) is not int or city['owner'] != player_id:
                raise ValueError('City religion requires only own observed cities')
            cid = _uint(city['id'], 'observed religion city')
            if cid in own_cities:
                raise ValueError('Duplicate observed religion city')
            own_cities.add(cid)
    seen = set()
    previous = -1
    for row in value['cities']:
        if type(row) is not dict or set(row) != {'city_id','majority_religion'}:
            raise ValueError('Malformed city religion row')
        cid = _uint(row['city_id'], 'religion city')
        religion = row['majority_religion']
        if type(religion) is not int or not -0x80000000 <= religion <= 0x7fffffff:
            raise ValueError('City majority religion is not a native signed index')
        if cid <= previous:
            raise ValueError('Duplicate or unordered city religion rows')
        previous = cid
        seen.add(cid)
    if own_cities is not None and seen != own_cities:
        raise ValueError('City religion state differs from the exact own city set')
    return value


def _majority(value):
    return dict(schema=SCHEMA, player_id=value['player_id'], turn=value['turn'],
                cities=[dict(city_id=row['city_id'], majority_religion=row['majority_religion'])
                        for row in value['cities']])


def validate_details(value, player_id, turn, *, observation=None):
    if (type(value) is not dict or set(value) != {'schema','player_id','turn','cities'}
            or value['schema'] != DETAILS_SCHEMA or type(value['cities']) is not list
            or len(value['cities']) > MAX_CITIES):
        raise ValueError('Malformed city religion details')
    for city in value['cities']:
        if (type(city) is not dict or set(city) != {'city_id','majority_religion','religions'}
                or type(city['religions']) is not list or len(city['religions']) > MAX_RELIGIONS):
            raise ValueError('Malformed city religion detail row')
        previous = -1
        for religion in city['religions']:
            if (type(religion) is not dict or set(religion) !=
                    {'religion_index','followers','pressure_per_turn','lifetime_pressure'}):
                raise ValueError('Malformed active city religion row')
            index = _uint(religion['religion_index'], 'active religion index', 0x7fffffff)
            followers = religion['followers']
            if type(followers) is not int or not -0x80000000 <= followers <= 0x7fffffff:
                raise ValueError('City followers must preserve the native signed count')
            for key in ('pressure_per_turn','lifetime_pressure'):
                pressure = religion[key]
                if type(pressure) is not int or not -8388608 <= pressure <= 8388608:
                    raise ValueError('City pressure must be the original UI rounded native value')
            if index <= previous:
                raise ValueError('Duplicate or unordered active city religions')
            previous = index
    _validate_majority(_majority(value), player_id, turn, observation=observation)
    return value


def validate(value, player_id, turn, *, observation=None):
    if type(value) is dict and value.get('schema') == DETAILS_SCHEMA:
        return validate_details(value, player_id, turn, observation=observation)
    return _validate_majority(value, player_id, turn, observation=observation)


def project_majority(value, player_id, turn, *, observation=None):
    """Return only the proven historical fields, retaining every own city."""
    validate(value, player_id, turn, observation=observation)
    return _majority(value)

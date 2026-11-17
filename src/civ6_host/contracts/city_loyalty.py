"""Public contents of the expansion city loyalty panel."""

import math

SCHEMA = 'civ6-host.city-loyalty.v1'
MAX_CITIES = 4096
MAX_SOURCES = 128
MAX_TEXT_BYTES = 4096
_ROW_FIELDS = {
    'city_id', 'current', 'maximum', 'per_turn', 'level', 'level_name', 'per_turn_status',
    'trend', 'conversion_turns', 'potential_new_owner', 'sources',
}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e9


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _text(value):
    return type(value) is str and '\0' not in value and 0 < len(value.encode('utf-8')) <= MAX_TEXT_BYTES


def validate(value, player_id, turn, *, observation=None):
    if (type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'cities'}
            or value['schema'] != SCHEMA
            or not _integer(value['player_id'], 0, 63) or value['player_id'] != player_id
            or not _integer(value['turn'], 0, 2**31 - 1) or value['turn'] != turn
            or type(value['cities']) is not list or len(value['cities']) > MAX_CITIES):
        raise ValueError('Invalid city loyalty boundary')
    previous = -1
    observed = set()
    for row in value['cities']:
        if (type(row) is not dict or set(row) != _ROW_FIELDS
                or not _integer(row['city_id'], previous + 1, 2**32 - 1)
                or not all(_number(row[key]) for key in ('current', 'maximum', 'per_turn'))
                or row['maximum'] <= 0 or not _integer(row['level'], 0, 2**31 - 1)
                or not all(_text(row[key]) for key in ('level_name', 'per_turn_status'))
                or row['trend'] not in ('stable', 'gaining', 'losing')
                or (row['potential_new_owner'] is not None
                    and not _integer(row['potential_new_owner'], 0, 63))
                or type(row['sources']) is not list or len(row['sources']) > MAX_SOURCES):
            raise ValueError('Invalid city loyalty row')
        countdown = row['conversion_turns']
        if (row['trend'] == 'stable' and countdown is not None
                or row['trend'] == 'gaining' and countdown is not None and not _integer(countdown, 1, 2**31 - 1)
                or row['trend'] == 'losing' and not _integer(countdown, -2**31, 2**31 - 1)):
            raise ValueError('Invalid displayed loyalty conversion countdown')
        for source in row['sources']:
            if (type(source) is not dict or set(source) != {'name', 'change', 'negative'}
                    or not _text(source['name']) or not _number(source['change'])
                    or type(source['negative']) is not bool
                    or (source['change'] != 0 and (source['change'] < 0) != source['negative'])):
                raise ValueError('Invalid displayed loyalty pressure')
        previous = row['city_id']
        observed.add(previous)
    if observation is not None:
        if (observation['player_id'], observation['turn']) != (player_id, turn):
            raise ValueError('Foreign loyalty observation')
        expected = {city['id'] for city in observation['cities'] if city['owner'] == player_id}
        if observed != expected:
            raise ValueError('City loyalty roster differs from own observed cities')
    return value

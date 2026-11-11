"""Public, player-scoped era dedication choices and confirmation."""
from copy import deepcopy
import re


SCHEMA = 'civ6-host.dedications.v1'
KIND = 'confirm_dedications'
CANDIDATE = {'kind': KIND}
AGES = ('normal', 'dark', 'golden', 'heroic')
_ROW_FIELDS = {'index', 'type'}
_STATE_FIELDS = {'schema', 'player_id', 'turn', 'era_index', 'age', 'remaining',
                 'choices', 'active'}
_SYMBOL = re.compile(r'[A-Z0-9_]+', re.ASCII)
MAX_CHOICES = 1024


def _index(value):
    return type(value) is int and 0 <= value < 2**31


def validate_state(value, player_id, turn):
    if (type(value) is not dict or set(value) != _STATE_FIELDS or value['schema'] != SCHEMA
            or type(player_id) is not int or not 0 <= player_id < 64
            or not _index(turn) or type(value['player_id']) is not int
            or type(value['turn']) is not int or (value['player_id'], value['turn']) != (player_id, turn)
            or not _index(value['era_index']) or value['age'] not in AGES
            or not _index(value['remaining'])):
        raise ValueError('Invalid public dedication state or player boundary')
    for key in ('choices', 'active'):
        rows = value[key]
        if type(rows) is not list or len(rows) > MAX_CHOICES:
            raise ValueError('Invalid native dedication list')
        indices, symbols = set(), set()
        for row in rows:
            if (type(row) is not dict or set(row) != _ROW_FIELDS or not _index(row['index'])
                    or type(row['type']) is not str or _SYMBOL.fullmatch(row['type']) is None
                    or key == 'choices' and (row['index'] in indices or row['type'] in symbols)):
                raise ValueError('Invalid or duplicate native dedication definition')
            indices.add(row['index'])
            symbols.add(row['type'])
    if not value['remaining'] <= len(value['choices']) or bool(value['choices']) != bool(value['remaining']):
        raise ValueError('Native dedication selection count differs from the popup choices')
    return value


def candidates(value):
    return [dict(CANDIDATE)] if value is not None and value['remaining'] else []


def validate_action(action):
    if (type(action) is not dict or set(action) != {'kind', 'indices'} or action['kind'] != KIND
            or type(action['indices']) is not list or not 1 <= len(action['indices']) <= MAX_CHOICES
            or any(not _index(index) for index in action['indices'])
            or len(set(action['indices'])) != len(action['indices'])):
        raise ValueError('Invalid ordered dedication confirmation')
    return action


def choose(value, candidate, parameters):
    if (candidate not in candidates(value) or type(parameters) is not dict
            or set(parameters) != {'indices'}):
        raise ValueError('Dedication confirmation requires the native choices and ordered indices')
    action = validate_action(dict(kind=KIND, indices=parameters['indices']))
    if (len(action['indices']) != value['remaining']
            or not set(action['indices']) <= {row['index'] for row in value['choices']}):
        raise ValueError('Dedication selections differ from the offered choices or native count')
    return deepcopy(action)

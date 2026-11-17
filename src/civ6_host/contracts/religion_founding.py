"""Public predefined religion foundation choices, without custom native names.

Availability is collected by native adapters. This validates their public wire
shape and reuses the own-religion projection; it does not decide gameplay rules.
"""
from .religion_beliefs import _int, _keys, _own, project_snapshot

SCHEMA = 'civ6-host.religion-founding.v1'
KIND = 'found_religion'
FIELDS = {'kind', 'index', 'hash'}
UNQUALIFIED = ('custom_religion_names',)


def validate_action(action):
    _keys(action, FIELDS)
    if action['kind'] != KIND:
        raise ValueError('Unexpected religion foundation action')
    _int(action['index'])
    _int(action['hash'], 0, 0xffffffff)
    return action


def _foundation(value, own, pid, turn):
    if own['religion_type_created'] != -1 or not own['holy_city_present']:
        if value is not None:
            raise ValueError('Religion foundation choices lack their native context')
        return
    _keys(value, {'status', 'player_id', 'current_game_turn', 'num_beliefs_earned',
        'founding_site', 'own_religion_count', 'operation', 'religion_parameter',
        'insert_parameter', 'exclusive_value', 'candidates'})
    if (value['status'] not in ('catalog', 'not_due')
            or _int(value['player_id'], 0, 63) != pid
            or _int(value['current_game_turn'], 0, 0xffffffff) != turn
            or _int(value['num_beliefs_earned'], 1) != own['num_beliefs_earned']
            or _int(value['own_religion_count'], 0, 4096) != 0):
        raise ValueError('Foreign or inconsistent religion foundation catalogue')
    site = value['founding_site']
    _keys(site, {'player', 'type', 'id'})
    _int(site['player'], 0, 63)
    _int(site['type'], 0, 65535)
    _int(site['id'])
    if site != own['holy_city']:
        raise ValueError('Religion foundation site differs from own native state')
    for key in ('operation', 'religion_parameter', 'insert_parameter', 'exclusive_value'):
        _int(value[key], 0, 0xffffffff)
    if value['religion_parameter'] == value['insert_parameter']:
        raise ValueError('Religion foundation parameter keys collide')
    rows = value['candidates']
    if (type(rows) is not list or len(rows) > 4096
            or bool(rows) != (value['status'] == 'catalog')):
        raise ValueError('Malformed native religion foundation candidates')
    indices, hashes = [], []
    for row in rows:
        _keys(row, {'index', 'hash'})
        validate_action(dict(kind=KIND, **row))
        indices.append(row['index'])
        hashes.append(row['hash'])
    if indices != sorted(set(indices)) or len(set(hashes)) != len(hashes):
        raise ValueError('Duplicate or unordered religion foundation choices')


def validate(value, player_id, turn, *, observation=None):
    _int(player_id, 0, 63)
    _int(turn, 0, 0xffffffff)
    _keys(value, {'schema', 'player_id', 'turn', 'own', 'foundation'})
    if (value['schema'] != SCHEMA or _int(value['player_id'], 0, 63) != player_id
            or _int(value['turn'], 0, 0xffffffff) != turn):
        raise ValueError('Foreign public religion foundation boundary')
    if observation is not None:
        if (type(observation) is not dict or type(observation.get('turn')) is not int
                or observation['turn'] != turn):
            raise ValueError('Stale public religion observation')
    _own(value['own'], player_id, observation)
    _foundation(value['foundation'], value['own'], player_id, turn)
    return value


def actions(value):
    if value is None or value['foundation'] is None:
        return []
    return [dict(kind=KIND, **row) for row in value['foundation']['candidates']]

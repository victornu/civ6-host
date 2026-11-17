"""Public own envoy counts for known living city-states."""

SCHEMA = 'civ6-host.city-state-envoys.v1'


def _integer(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def validate(value, player_id, turn):
    if (not _integer(player_id, 63) or not _integer(turn, 0x7fffffff)
            or type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'city_states'}
            or value['schema'] != SCHEMA or not _integer(value['player_id'], 63)
            or value['player_id'] != player_id or not _integer(value['turn'], 0x7fffffff)
            or value['turn'] != turn or type(value['city_states']) is not list
            or len(value['city_states']) > 63):
        raise ValueError('Malformed or foreign city-state envoy information')
    previous = -1
    for row in value['city_states']:
        if (type(row) is not dict or set(row) != {'player_id', 'own_envoys'}
                or not _integer(row['player_id'], 63) or row['player_id'] == player_id
                or row['player_id'] <= previous or not _integer(row['own_envoys'], 0x7fffffff)):
            raise ValueError('Malformed or out-of-order city-state envoy row')
        previous = row['player_id']
    return value

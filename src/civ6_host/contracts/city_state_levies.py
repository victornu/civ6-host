"""Player-visible military levy choices for known city-states."""

SCHEMA = 'civ6-host.city-state-levies.v1'
UNIT_SCHEMA = 'civ6-host.unit-levies.v1'
ACTION = 'levy_city_state_military'
ACTION_FIELDS = frozenset(('kind', 'target_player_id'))
_FIELDS = {'schema', 'player_id', 'turn', 'military_enabled', 'city_states'}
_ROW_FIELDS = {'player_id', 'can_levy', 'gold_cost', 'turn_limit', 'own_levy_active'}
_UNIT_ROW_FIELDS = {'owner', 'unit_id', 'original_owner', 'turns_remaining'}
MAX_UNITS = 8192


def _integer(value, limit):
    return type(value) is int and 0 <= value <= limit


def validate(value, player_id, turn):
    if (not _integer(player_id, 63) or not _integer(turn, 0x7fffffff)
            or type(value) is not dict or set(value) != _FIELDS
            or value['schema'] != SCHEMA
            or not _integer(value['player_id'], 63) or value['player_id'] != player_id
            or not _integer(value['turn'], 0x7fffffff) or value['turn'] != turn
            or type(value['military_enabled']) is not bool
            or type(value['city_states']) is not list or len(value['city_states']) > 63
            or not value['military_enabled'] and value['city_states']):
        raise ValueError('Malformed or foreign city-state levy catalogue')
    previous = -1
    for row in value['city_states']:
        if (type(row) is not dict or set(row) != _ROW_FIELDS
                or not _integer(row['player_id'], 63) or row['player_id'] == player_id
                or row['player_id'] <= previous or type(row['can_levy']) is not bool
                or type(row['own_levy_active']) is not bool):
            raise ValueError('Malformed or duplicate city-state levy row')
        if row['own_levy_active']:
            if row['can_levy'] or row['gold_cost'] is not None or row['turn_limit'] is not None:
                raise ValueError('An active own levy cannot expose a second levy offer')
        elif not _integer(row['gold_cost'], 0x7fffffff) or not _integer(row['turn_limit'], 0x7fffffff):
            raise ValueError('Invalid displayed city-state levy cost or duration')
        previous = row['player_id']
    return value


def actions(value):
    if value is None:
        return []
    validate(value, value['player_id'], value['turn'])
    return [{'kind': ACTION, 'target_player_id': row['player_id']}
            for row in value['city_states'] if row['can_levy']]


def validate_action(action):
    if (type(action) is not dict or set(action) != ACTION_FIELDS or action['kind'] != ACTION
            or not _integer(action['target_player_id'], 63)):
        raise ValueError('Invalid city-state levy action')
    return action


def validate_unit_flags(value, player_id, turn, *, observation=None):
    if (not _integer(player_id, 63) or not _integer(turn, 0x7fffffff)
            or type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'units'}
            or value['schema'] != UNIT_SCHEMA or not _integer(value['player_id'], 63)
            or value['player_id'] != player_id or not _integer(value['turn'], 0x7fffffff)
            or value['turn'] != turn or type(value['units']) is not list
            or len(value['units']) > MAX_UNITS):
        raise ValueError('Malformed or foreign unit levy flags')
    visible = None
    if observation is not None:
        if (observation['player_id'], observation['turn']) != (player_id, turn):
            raise ValueError('Unit levy flags require the same observation boundary')
        visible = {(row['owner'], row['id']) for row in observation['units']}
        visible.update((row['owner'], row['id']) for row in observation['visible_enemy_units']
                       if row['visible'] is True)
    previous = (-1, -1)
    for row in value['units']:
        if (type(row) is not dict or set(row) != _UNIT_ROW_FIELDS
                or not _integer(row['owner'], 63) or not _integer(row['unit_id'], 0xffffffff)
                or not _integer(row['turns_remaining'], 0x7fffffff)):
            raise ValueError('Malformed unit levy flag')
        original_owner = row['original_owner']
        if original_owner is not None and (
                not _integer(original_owner, 63) or original_owner == row['owner']):
            raise ValueError('Unit levy flag has an invalid original owner')
        key = row['owner'], row['unit_id']
        if key <= previous or (visible is not None and key not in visible):
            raise ValueError('Unit levy flag is unordered, duplicated or outside the public roster')
        previous = key
    return value

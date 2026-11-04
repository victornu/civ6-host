"""Player-visible Gathering Storm upgrade quotes and executable choices."""
from .action_budget import ORDINARY_ACTION_LIMIT

COMMAND = 0xd34b69c0
BASE_FIELDS = frozenset(('unit_id', 'hash', 'target_type', 'cost'))
RESOURCE_FIELDS = frozenset(('resource_type', 'resource_cost'))
FIELDS = BASE_FIELDS | RESOURCE_FIELDS | {'kind'}


def _uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


def _validate_quote(row):
    target, cost = row['target_type'], row['cost']
    resource, quantity = row['resource_type'], row['resource_cost']
    if (not _uint(row['unit_id']) or type(row['hash']) is not int or row['hash'] != COMMAND
            or target is not None and not _uint(target)
            or cost is not None and not _uint(cost, 0x7fffffff)
            or (resource is None) != (quantity is None)
            or resource is not None and (not _uint(resource, 0x7fffffff)
                                         or not _uint(quantity, 0x7fffffff))
            or target is None and (cost is not None or resource is not None)):
        raise ValueError('Invalid native upgrade quote')


def validate_action(action):
    if (type(action) is not dict or set(action) != FIELDS or action['kind'] != 'upgrade_unit'
            or action['target_type'] is None or action['cost'] is None):
        raise ValueError('Invalid upgrade action')
    _validate_quote(action)
    return action


def validate_catalogue(value, player_id, turn, *, observation=None):
    if (type(value) is not dict or set(value) != {'player_id', 'turn', 'offers'}
            or not _uint(value['player_id'], 63) or value['player_id'] != player_id
            or not _uint(value['turn'], 0x7fffffff) or value['turn'] != turn
            or type(value['offers']) is not list or len(value['offers']) > ORDINARY_ACTION_LIMIT):
        raise ValueError('Invalid upgrade catalogue boundary')
    owned = None
    if observation is not None:
        if (observation['player_id'], observation['turn']) != (player_id, turn):
            raise ValueError('Foreign upgrade observation')
        owned = {unit['id'] for unit in observation['units'] if unit['owner'] == player_id}
    ids = []
    for row in value['offers']:
        if (type(row) is not dict or set(row) != BASE_FIELDS | RESOURCE_FIELDS | {'legal'}
                or type(row['legal']) is not bool
                or row['legal'] and (row['target_type'] is None or row['cost'] is None)):
            raise ValueError('Invalid upgrade offer')
        _validate_quote(row)
        if owned is not None and row['unit_id'] not in owned:
            raise ValueError('Foreign upgrade unit')
        ids.append(row['unit_id'])
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unordered upgrade offers')
    return value


def actions(value):
    return [dict(kind='upgrade_unit', **{key: item for key, item in row.items() if key != 'legal'})
            for row in value['offers'] if row['legal']]

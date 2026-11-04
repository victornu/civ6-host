"""Own-player Gathering Storm TopPanel resource data."""
import re

SCHEMA = 'civ6-host.strategic-resources.v1'
LIMIT = 128
INT32_MAX = 0x7fffffff
FIELDS = ('resource_type', 'item_type', 'stockpile', 'capacity', 'reserved',
          'accumulation', 'consumption', 'extraction', 'city_state_import',
          'bonus', 'unit_demand', 'power_demand')


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def validate(value, player_id, turn):
    if (type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'panel_enabled', 'resources'}
            or value['schema'] != SCHEMA
            or not _integer(value['player_id'], 0, 63) or value['player_id'] != player_id
            or not _integer(value['turn'], 0, INT32_MAX) or value['turn'] != turn
            or type(value['panel_enabled']) is not bool
            or type(value['resources']) is not list or len(value['resources']) > LIMIT
            or not value['panel_enabled'] and value['resources']):
        raise ValueError('Invalid strategic resource boundary')
    ids, names = [], set()
    for row in value['resources']:
        if (type(row) is not dict or set(row) != set(FIELDS)
                or not _integer(row['resource_type'], 0, INT32_MAX)
                or type(row['item_type']) is not str
                or not re.fullmatch(r'RESOURCE_[A-Z0-9_]{1,100}', row['item_type'])
                or row['item_type'] in names
                or not _integer(row['capacity'], 1, INT32_MAX)
                or any(not _integer(row[key], -INT32_MAX-1, INT32_MAX) for key in ('stockpile', 'reserved'))
                or not _integer(row['accumulation'], -3*(INT32_MAX+1), 3*INT32_MAX)
                or not _integer(row['consumption'], -2*(INT32_MAX+1), 2*INT32_MAX)
                or not any(row[key] > 0 for key in ('stockpile', 'accumulation', 'consumption'))
                or any(row[key] is not None and not _integer(row[key], 1, INT32_MAX) for key in FIELDS[7:])
                or row['consumption'] <= 0 and (row['unit_demand'] is not None or row['power_demand'] is not None)):
            raise ValueError('Invalid public strategic resource row')
        ids.append(row['resource_type'])
        names.add(row['item_type'])
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unordered strategic resources')
    return value

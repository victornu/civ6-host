"""Park labels on the same revealed plots as the official map tooltip."""

from .action_budget import MAP_CELL_LIMIT

SCHEMA = 'civ6-host.national-parks.v1'
MAX_NAME_BYTES = 4096
DESIGNATE = 'designate_national_park'
DESIGNATION_FIELDS = frozenset(('kind', 'unit_id', 'x', 'y'))


def validate_designation(action, observation=None):
    if (type(action) is not dict or set(action) != DESIGNATION_FIELDS or action['kind'] != DESIGNATE
            or type(action['unit_id']) is not int or not 0 <= action['unit_id'] < 2**32
            or any(type(action[key]) is not int or not 0 <= action[key] < 2**31 for key in ('x', 'y'))):
        raise ValueError('Invalid national park designation')
    if observation is not None and sum(
            (unit['owner'], unit['id'], unit['x'], unit['y']) ==
            (observation['player_id'], action['unit_id'], action['x'], action['y'])
            for unit in observation['units']) != 1:
        raise ValueError('Park designation requires an observed own unit at that position')
    return action


def validate_designations(actions, observation=None):
    if type(actions) is not list or len(actions) > 4096:
        raise ValueError('Malformed park designation choices')
    units = [validate_designation(action, observation)['unit_id'] for action in actions]
    if units != sorted(set(units)):
        raise ValueError('Park designation units are unordered or repeated')


def validate(value, player_id, turn, *, observation=None):
    if (type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'width', 'height', 'plots'}
            or value['schema'] != SCHEMA or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn
            or any(type(value[key]) is not int or value[key] < 1 for key in ('width', 'height'))
            or value['width'] * value['height'] > MAP_CELL_LIMIT
            or type(value['plots']) is not list or len(value['plots']) > value['width'] * value['height']):
        raise ValueError('Invalid national park boundary')
    available = None
    if observation is not None:
        if any(observation[key] != value[key] for key in ('player_id', 'turn', 'width', 'height')):
            raise ValueError('Foreign national park observation')
        available = {row['index']: row for row in observation['plots']}
    previous = -1
    for row in value['plots']:
        if (type(row) is not dict or set(row) != {'plot_id', 'name', 'visible'}
                or type(row['plot_id']) is not int
                or not previous < row['plot_id'] < value['width'] * value['height']
                or type(row['visible']) is not bool):
            raise ValueError('Invalid national park plot')
        name = row['name']
        if name is not None and (type(name) is not str or '\0' in name
                                 or not 0 < len(name.encode('utf-8')) <= MAX_NAME_BYTES):
            raise ValueError('Invalid national park label')
        previous = row['plot_id']
        if available is not None:
            plot = available.get(previous)
            if ((plot is not None and plot['revealed'] is not True)
                    or row['visible'] != (plot is not None and plot['visible'] is True)):
                raise ValueError('National park differs from the public map boundary')
    return value

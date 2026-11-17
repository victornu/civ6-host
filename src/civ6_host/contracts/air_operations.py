"""Public plot commands offered by the native air-unit interface."""

from .action_budget import MAP_CELL_LIMIT


KIND = 'air_operation'
ATTACK = 'AIR_ATTACK'
OPERATIONS = (ATTACK, 'DEPLOY', 'REBASE')
FIELDS = {'kind', 'operation', 'unit_id', 'plot_id', 'x', 'y'}


def validate(action, observation=None):
    if (type(action) is not dict or action.keys() != FIELDS or action['kind'] != KIND
            or action['operation'] not in OPERATIONS
            or type(action['unit_id']) is not int or not 0 <= action['unit_id'] <= 0xffffffff
            or any(type(action[key]) is not int or not 0 <= action[key] < MAP_CELL_LIMIT
                   for key in ('plot_id', 'x', 'y'))):
        raise ValueError('Invalid air operation')
    if observation is not None:
        width, height = observation['width'], observation['height']
        if (action['x'] >= width or action['y'] >= height
                or action['plot_id'] != action['y'] * width + action['x']
                or not any((unit['owner'], unit['id']) == (observation['player_id'], action['unit_id'])
                           for unit in observation['units'])):
            raise ValueError('Air operation requires its own unit and exact map coordinates')
    return action

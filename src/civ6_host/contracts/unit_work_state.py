"""Public own-unit charges and movement, including exhausted units."""
import math
import re

SCHEMA = 'civ6-host.unit-work-state.v1'
PLOT_SCHEMA = 'civ6-host.unit-work-state.v2'
_UNIT_FIELDS = {'unit_id', 'plot_id', 'charges', 'moves_token'}
_PLOT_FIELDS = {'improvement', 'improvement_pillaged', 'route', 'route_pillaged'}
_NUMBER = re.compile(r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')


def validate(value, player_id, turn, *, observation=None, work_catalog=None, include_plot=False):
    if (type(value) is not dict or set(value) != {'schema','player_id','turn','units'}
            or value['schema'] != (PLOT_SCHEMA if include_plot else SCHEMA)
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn
            or type(value['units']) is not list or len(value['units']) > 4096):
        raise ValueError('Invalid public unit-work state')
    units = {}
    plots = {}
    for row in value['units']:
        if type(row) is not dict or set(row) != (_UNIT_FIELDS | (_PLOT_FIELDS if include_plot else set())):
            raise ValueError('Unexpected unit-work state fields')
        for key in ('unit_id','plot_id','charges'):
            if type(row[key]) is not int or not 0 <= row[key] < 2**32:
                raise ValueError('Invalid unit-work ' + key)
        token = row['moves_token']
        if (type(token) is not str or len(token) > 32 or not _NUMBER.fullmatch(token)
                or not math.isfinite(float(token)) or not 0 <= float(token) <= 2**31):
            raise ValueError('Invalid unit-work movement')
        if row['unit_id'] in units:
            raise ValueError('Duplicate own unit-work state')
        units[row['unit_id']] = row
        if include_plot:
            for key in ('improvement', 'route'):
                if (type(row[key]) is not int or not -1 <= row[key] < 2**31
                        or type(row[key + '_pillaged']) is not bool):
                    raise ValueError('Invalid unit-work plot ' + key)
            plot = {key: row[key] for key in _PLOT_FIELDS}
            if plots.setdefault(row['plot_id'], plot) != plot:
                raise ValueError('Different work states for one plot')
    if observation is not None:
        if observation['player_id'] != player_id or observation['turn'] != turn:
            raise ValueError('Unit-work observation identity differs')
        own = {row['id']:row for row in observation['units']}
        if len(own) != len(observation['units']) or set(own) != set(units):
            raise ValueError('Unit-work state does not cover exactly the observed own units')
        visible_plots = ({p['index'] for p in observation['plots'] if p['visible'] is True}
                         if include_plot else set())
        for uid,row in own.items():
            state = units[uid]
            if (row['owner'] != player_id
                    or state['plot_id'] != row['y'] * observation['width'] + row['x']
                    or float(state['moves_token']) != row['moves']):
                raise ValueError('Unit-work position/movement differs from public observation')
            if include_plot and state['plot_id'] not in visible_plots:
                raise ValueError('Unit-work plot is outside the player visibility')
    if work_catalog is not None:
        if work_catalog['player_id'] != player_id or work_catalog['turn'] != turn:
            raise ValueError('Unit-work catalogue identity differs')
        for row in work_catalog['offers']:
            action = row['action']; state = units.get(action['unit_id'])
            if state is None or any(action[k] != state[k] for k in ('plot_id','charges','moves_token')):
                raise ValueError('Unit-work action refers to another charge/movement state')
    return value

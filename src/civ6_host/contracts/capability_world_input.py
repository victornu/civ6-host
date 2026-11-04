"""Portable explicit unit selection, grid input and own queued destinations.

These checks authenticate shape and public identity, not native effects or
legality. A grid click is an input route; its unqualified native branches remain
explicit in the enclosing capability family.
"""
from .action_budget import MAP_CELL_LIMIT, ORDINARY_ACTION_LIMIT

SCHEMA = 'civ6rl.world_input.v1'
ACTION_FIELDS = {
    'world_select_unit': frozenset(('kind', 'unit_id')),
    'world_deselect_unit': frozenset(('kind',)),
    'world_plot_click': frozenset(('kind', 'unit_id', 'plot_id', 'x', 'y')),
}
WORLD_KINDS = frozenset(ACTION_FIELDS)
UNQUALIFIED_WORLD_CLICK = ('non_MOVE_TO_operations', 'war_confirmation')


def _uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


def _geometry(width, height):
    if (not _uint(width, 512) or not width or not _uint(height, 512)
            or not height or width * height > MAP_CELL_LIMIT):
        raise ValueError('Invalid public world-input geometry')


def validate_action(action, *, width=None, height=None):
    if (type(action) is not dict or type(action.get('kind')) is not str
            or action['kind'] not in ACTION_FIELDS
            or set(action) != ACTION_FIELDS[action['kind']]):
        raise ValueError('Invalid explicit world-input action shape')
    if action['kind'] != 'world_deselect_unit' and not _uint(action['unit_id']):
        raise ValueError('Invalid explicit world-input own unit')
    if (width is None) != (height is None):
        raise ValueError('World-input geometry must be supplied together')
    if width is not None:
        _geometry(width, height)
    if action['kind'] == 'world_plot_click':
        if (not _uint(action['plot_id'], MAP_CELL_LIMIT-1)
                or not _uint(action['x'], 511) or not _uint(action['y'], 511)):
            raise ValueError('Invalid explicit world-input coordinates')
        if width is not None and (action['x'] >= width or action['y'] >= height
                or action['plot_id'] != action['y'] * width + action['x']):
            raise ValueError('World-input coordinates differ from the public grid')
    return action


def _boundary(value, pid, turn, *, observation=None):
    if (not _uint(pid, 63) or not _uint(turn)
            or any(type(value[k]) is not int for k in ('player_id', 'turn', 'width', 'height'))
            or (value['player_id'], value['turn']) != (pid, turn)):
        raise ValueError('Foreign world-input boundary')
    _geometry(value['width'], value['height'])
    if observation is not None:
        # The containing catalogue validates the complete public observation.
        if (observation['player_id'], observation['turn'], observation['width'], observation['height']) != (
                pid, turn, value['width'], value['height']):
            raise ValueError('World-input geometry differs from its public observation')


def validate_state(value, pid, turn, *, observation=None, unavailable=False):
    if type(unavailable) is not bool:
        raise ValueError('World-input availability must be explicit')
    if unavailable:
        if value is not None:
            raise ValueError('Unavailable world input must be null')
        return value
    fields = {'schema', 'player_id', 'turn', 'width', 'height', 'units',
              'selected_unit_id', 'war_prompt'}
    if (type(value) is not dict or set(value) != fields or value['schema'] != SCHEMA
            or value['war_prompt'] is not None or type(value['units']) is not list
            or len(value['units']) > ORDINARY_ACTION_LIMIT):
        raise ValueError('Invalid or unqualified public world-input state')
    _boundary(value, pid, turn, observation=observation)
    ids, selectable = [], []
    for row in value['units']:
        if (type(row) is not dict or set(row) != {'unit_id', 'ignore_moves'}
                or not _uint(row['unit_id']) or type(row['ignore_moves']) is not bool):
            raise ValueError('Invalid own world-input unit')
        ids.append(row['unit_id'])
        if not row['ignore_moves']:
            selectable.append(row['unit_id'])
    if (ids != sorted(set(ids)) or observation is not None
            and ids != sorted(u['id'] for u in observation['units'])):
        raise ValueError('World-input roster differs from own units')
    selected = value['selected_unit_id']
    if selected is not None and (not _uint(selected) or selected not in selectable):
        raise ValueError('World-input selection differs from selectable own units')
    return value


def validate_queued_orders(value, pid, turn, *, observation=None, world_input=None,
                           unavailable=False):
    if type(unavailable) is not bool:
        raise ValueError('Queued-order availability must be explicit')
    if unavailable:
        if value is not None:
            raise ValueError('Unavailable queued orders must be null')
        return value
    if (type(value) is not dict or set(value) != {'player_id', 'turn', 'width', 'height', 'units'}
            or type(value['units']) is not list or len(value['units']) > ORDINARY_ACTION_LIMIT):
        raise ValueError('Invalid public own queued orders')
    _boundary(value, pid, turn, observation=observation)
    ids = []
    for row in value['units']:
        if (type(row) is not dict or set(row) != {'unit_id', 'plot_id'}
                or not _uint(row['unit_id']) or row['plot_id'] is not None
                and not _uint(row['plot_id'], value['width'] * value['height'] - 1)):
            raise ValueError('Invalid own queued destination')
        ids.append(row['unit_id'])
    if (ids != sorted(set(ids)) or observation is not None
            and ids != sorted(u['id'] for u in observation['units'])):
        raise ValueError('Queued-order roster differs from own units')
    if world_input is not None:
        validate_state(world_input, pid, turn, observation=observation)
        if ((value['width'], value['height']) != (world_input['width'], world_input['height'])
                or ids != [u['unit_id'] for u in world_input['units']]):
            raise ValueError('Queued orders differ from the world-input boundary')
    return value


def actions(state):
    """All grid coordinates, without visibility, path or moves-remaining masks."""
    validate_state(state, state['player_id'], state['turn'])
    result = [dict(kind='world_select_unit', unit_id=row['unit_id'])
              for row in state['units'] if not row['ignore_moves']]
    selected = state['selected_unit_id']
    if selected is not None:
        result.append(dict(kind='world_deselect_unit'))
        result.extend(dict(kind='world_plot_click', unit_id=selected,
            plot_id=i, x=i % state['width'], y=i // state['width'])
            for i in range(state['width'] * state['height']))
    return result


def validate_candidates(state, candidates):
    actual = [row['action'] for row in candidates if row['action']['kind'] in ACTION_FIELDS]
    expected = [] if state is None else actions(state)
    key = lambda action: tuple(sorted(action.items()))
    if (len(actual) != len(expected)
            or {key(action) for action in actual} != {key(action) for action in expected}):
        raise ValueError('World-input choices differ from exact own-unit/full-grid input')

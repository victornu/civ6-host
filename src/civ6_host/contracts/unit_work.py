"""Portable native unit-work actions and catalogue validation."""
import math
import re

OPS = ('HARVEST_RESOURCE', 'REMOVE_FEATURE', 'REMOVE_IMPROVEMENT', 'REPAIR', 'REPAIR_ROUTE')
COMMON_FIELDS = {'kind', 'unit_id', 'x', 'y', 'plot_id', 'charges', 'moves_token'}
BUILD_FIELDS = COMMON_FIELDS | {'index', 'hash', 'item_type', 'selector'}
ADJACENT_FIELDS = BUILD_FIELDS | {'source_x', 'source_y', 'source_plot_id'}
OP_FIELDS = COMMON_FIELDS | {'operation', 'hash'}
NETWORK_ACTION_FIELDS = {'build_improvement': BUILD_FIELDS, 'terrain_operation': OP_FIELDS}
ADJACENT_KIND = 'build_improvement_adjacent'
BUILD_ROUTE = 'build_route'
ROUTE_FIELDS = {'kind', 'unit_id', 'plot_id', 'x', 'y', 'route_type'}
ADJACENT_NETWORK_ACTION_FIELDS = {**NETWORK_ACTION_FIELDS, ADJACENT_KIND: ADJACENT_FIELDS}
NETWORK_GAPS = {
    'build_improvement': ('adjacent_improvements',),
    'terrain_operation': ('additional_terrain_operation_routes',),
}

def network_gaps(*, adjacent):
    if not adjacent:
        return NETWORK_GAPS
    return dict(NETWORK_GAPS, build_improvement=(), build_improvement_adjacent=())


def network_families(catalogue, rows, *, adjacent, unavailable_reason):
    result = {}
    for kind, gaps in network_gaps(adjacent=adjacent).items():
        if catalogue is None:
            result[kind] = dict(status='unqualified', reason=unavailable_reason)
        else:
            ids = [row['candidate_id'] for row in rows if row['action']['kind'] == kind]
            result[kind] = (dict(status='queried_partial', unqualified=list(gaps), candidate_ids=ids)
                            if gaps else dict(status='queried_complete', candidate_ids=ids))
    return result


def uint(v, name, maximum=4294967295):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError('Invalid unit work ' + name)
    return v


def validate_route(action, observation=None):
    if (type(action) is not dict or action.keys() != ROUTE_FIELDS or action['kind'] != BUILD_ROUTE
            or type(action['route_type']) is not str
            or re.fullmatch(r'ROUTE_[A-Z0-9_]{1,100}', action['route_type']) is None):
        raise ValueError('Invalid route construction choice')
    uint(action['unit_id'], 'route constructor')
    for key in ('plot_id', 'x', 'y'):
        uint(action[key], key, 16383)
    if observation is not None:
        x, y = action['x'], action['y']
        if (x >= observation['width'] or y >= observation['height']
                or action['plot_id'] != y * observation['width'] + x
                or not any((unit['owner'], unit['id'], unit['x'], unit['y']) ==
                           (observation['player_id'], action['unit_id'], x, y)
                           for unit in observation['units'])):
            raise ValueError('Route construction requires its own unit and current tile')
    return action

def moves(token):
    if type(token) is not str or len(token) > 32 or (not re.fullmatch('[0-9]+(?:\\.[0-9]+)?(?:e[+-]?[0-9]+)?', token)):
        raise ValueError('Malformed unit work movement')
    n = float(token)
    if not math.isfinite(n) or not 0 < n <= 2 ** 31:
        raise ValueError('Unbounded unit work movement')
    return n

def validate_action(a):
    if type(a) is not dict or a.get('kind') not in (
        'build_improvement', 'build_improvement_adjacent', 'terrain_operation'
    ):
        raise ValueError('Invalid unit work action')
    adjacent = a['kind'] == 'build_improvement_adjacent'
    build = a['kind'] != 'terrain_operation'
    fields = ADJACENT_FIELDS if adjacent else BUILD_FIELDS if build else OP_FIELDS
    if set(a) != fields:
        raise ValueError('Invalid unit work fields')
    for k in ('unit_id', 'x', 'y', 'plot_id', 'charges', 'hash'):
        uint(a[k], k)
    moves(a['moves_token'])
    if adjacent:
        for k in ('source_x', 'source_y', 'source_plot_id'):
            uint(a[k], k)
        if (a['source_plot_id'] == a['plot_id']
                or (a['source_x'], a['source_y']) == (a['x'], a['y'])):
            raise ValueError('Adjacent work requires a distinct source and target')
    if build:
        uint(a['index'], 'index')
        uint(a['selector'], 'selector')
        if type(a['item_type']) is not str or not re.fullmatch('IMPROVEMENT_[A-Z0-9_]{1,100}', a['item_type']):
            raise ValueError('Invalid improvement type')
    elif a['operation'] not in OPS:
        raise ValueError('Unsupported terrain operation')
    return a

def wire(a):
    validate_action(a)
    parts = [a[k] for k in ('unit_id', 'x', 'y', 'plot_id', 'charges', 'moves_token')]
    if a['kind'] == 'build_improvement_adjacent':
        parts = ['A', *parts, *[a[k] for k in (
            'index', 'hash', 'item_type', 'selector', 'source_x', 'source_y', 'source_plot_id'
        )]]
    elif a['kind'] == 'build_improvement':
        parts = ['I', *parts, *[a[k] for k in ('index', 'hash', 'item_type', 'selector')]]
    else:
        parts = ['O', *parts, a['operation'], a['hash']]
    return '|'.join(map(str, parts))

def validate_catalog(value, pid, turn):
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'enabled', 'offers'} or type(value['player_id']) is not int or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Foreign unit work catalogue')
    if type(value['offers']) is not list or len(value['offers']) > 4096:
        raise ValueError('Unbounded unit work offers')
    if type(value['enabled']) is not bool or (not value['enabled'] and value['offers']):
        raise ValueError('Disabled unit work has offers')
    seen = set()
    for row in value['offers']:
        if type(row) is not dict or set(row) != {'action', 'legal'} or type(row['legal']) is not bool:
            raise ValueError('Malformed unit work legality')
        key = wire(row['action'])
        if key in seen:
            raise ValueError('Duplicate unit work offer')
        seen.add(key)
    return value

def actions(value):
    return [r['action'] for r in value['offers'] if r['legal']]


def validate_network_catalog(value, player_id, turn, *, observation=None, adjacent=False):
    """Bind native work offers to the public actor and visible plots."""
    validate_catalog(value, player_id, turn)
    if not value['enabled']:
        raise ValueError('Unavailable unit work must be represented by null')
    units = ({u['id']: u for u in observation['units']}
             if observation is not None else None)
    plots = ({p['index']: p for p in observation['plots']}
             if observation is not None else None)
    for offer in value['offers']:
        action = offer['action']
        fields = ADJACENT_NETWORK_ACTION_FIELDS if adjacent else NETWORK_ACTION_FIELDS
        if action['kind'] not in fields:
            raise ValueError('Unqualified unit-work route in the network catalogue')
        if units is None:
            continue
        unit = units.get(action['unit_id'])
        plot = plots.get(action['plot_id'])
        source = plots.get(action.get('source_plot_id', action['plot_id']))
        source_xy = (action.get('source_x', action['x']), action.get('source_y', action['y']))
        if (unit is None or plot is None or plot['visible'] is not True
                or source is None or source['visible'] is not True
                or unit['owner'] != player_id
                or (unit['x'], unit['y']) != source_xy
                or (source['x'], source['y']) != source_xy
                or (plot['x'], plot['y']) != (action['x'], action['y'])):
            raise ValueError('Unit-work offer differs from its visible source or target')
    return value


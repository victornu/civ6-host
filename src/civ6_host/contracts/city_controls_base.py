"""Generated Base city contract selection; no native imports or I/O."""
from types import SimpleNamespace
focus_SCHEMA = 'civ6rl.native_city_focus1000.v1'
focus_YIELDS = ('YIELD_FOOD', 'YIELD_PRODUCTION', 'YIELD_GOLD', 'YIELD_SCIENCE', 'YIELD_CULTURE', 'YIELD_FAITH')
focus_FIELDS = {'kind', 'city_id', 'yield_type', 'yield_index', 'favored', 'disfavored'}

def focus_uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid city focus ' + label)
    return value

def focus_validate_action(action):
    if type(action) is not dict or set(action) != focus_FIELDS or action['kind'] != 'city_focus':
        raise ValueError('Malformed city focus action')
    focus_uint(action['city_id'], 'city')
    focus_uint(action['yield_index'], 'yield index', 2147483647)
    if action['yield_type'] not in focus_YIELDS or type(action['yield_type']) is not str:
        raise ValueError('Unsupported city focus yield')
    if any((type(action[key]) is not bool for key in ('favored', 'disfavored'))):
        raise ValueError('City focus states must be Boolean')
    return action

def focus_validate_catalog(value, pid, turn):
    focus_uint(pid, 'player', 63)
    focus_uint(turn, 'turn', 2147483647)
    if type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'city_id', 'yields'} or value['schema'] != focus_SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Foreign city focus catalogue')
    focus_uint(value['city_id'], 'city')
    if type(value['yields']) is not list or len(value['yields']) != len(focus_YIELDS):
        raise ValueError('City focus catalogue requires exactly six yields')
    indices = set()
    for name, row in zip(focus_YIELDS, value['yields']):
        if type(row) is not dict or set(row) != {'yield_type', 'index', 'favored', 'disfavored'} or row['yield_type'] != name:
            raise ValueError('City focus yield order or fields differ')
        index = focus_uint(row['index'], 'yield index', 2147483647)
        if index in indices or any((type(row[key]) is not bool for key in ('favored', 'disfavored'))):
            raise ValueError('Duplicate yield index or malformed city focus states')
        indices.add(index)
    return value

def focus_actions(value):
    focus_validate_catalog(value, value['player_id'], value['turn'])
    return [dict(kind='city_focus', city_id=value['city_id'], yield_type=row['yield_type'], yield_index=row['index'], favored=row['favored'], disfavored=row['disfavored']) for row in value['yields']]
focus = SimpleNamespace(SCHEMA=focus_SCHEMA, YIELDS=focus_YIELDS, FIELDS=focus_FIELDS, uint=focus_uint, validate_action=focus_validate_action, validate_catalog=focus_validate_catalog, actions=focus_actions)
citizens_SCHEMA = 'civ6rl.native_city_citizens.v1'
citizens_PLOT_FIELDS = {'plot_id', 'x', 'y', 'occupied', 'locked', 'workers', 'capacity'}
citizens_FIELDS = citizens_PLOT_FIELDS | {'kind', 'city_id'}
citizens_MAX_PLOTS = 16384

def citizens_uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid citizen management ' + label)
    return value

def citizens__validate_plot(row):
    if type(row) is not dict or set(row) != citizens_PLOT_FIELDS:
        raise ValueError('Malformed citizen display row')
    for key in ('plot_id', 'x', 'y'):
        citizens_uint(row[key], key, citizens_MAX_PLOTS - 1)
    if any((type(row[key]) is not bool for key in ('occupied', 'locked'))):
        raise ValueError('Citizen occupancy and lock must be Boolean')
    workers, capacity = (row['workers'], row['capacity'])
    if workers is None or capacity is None:
        if workers is not None or capacity is not None:
            raise ValueError('Citizen meter values must be known together')
    else:
        citizens_uint(workers, 'workers', 2147483647)
        citizens_uint(capacity, 'capacity', 2147483647)
        if capacity <= 1 or row['occupied'] != (workers >= 1):
            raise ValueError('Citizen meter disagrees with the official display')
    return row

def citizens_validate_action(action):
    if type(action) is not dict or set(action) != citizens_FIELDS or action['kind'] != 'city_citizen':
        raise ValueError('Malformed citizen management action')
    citizens_uint(action['city_id'], 'city')
    citizens__validate_plot({key: action[key] for key in citizens_PLOT_FIELDS})
    return action

def citizens_validate_catalog(value, pid, turn):
    citizens_uint(pid, 'player', 63)
    citizens_uint(turn, 'turn', 2147483647)
    if type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'city_id', 'plots'} or value['schema'] != citizens_SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Foreign citizen catalogue')
    citizens_uint(value['city_id'], 'city')
    if type(value['plots']) is not list or len(value['plots']) > citizens_MAX_PLOTS:
        raise ValueError('Unbounded citizen catalogue')
    ids, coordinates = ([], set())
    for row in value['plots']:
        citizens__validate_plot(row)
        ids.append(row['plot_id'])
        coordinates.add((row['x'], row['y']))
    if ids != sorted(set(ids)) or len(coordinates) != len(ids):
        raise ValueError('Duplicate or unordered citizen plots')
    return value

def citizens_actions(value):
    citizens_validate_catalog(value, value['player_id'], value['turn'])
    return [dict(kind='city_citizen', city_id=value['city_id'], **row) for row in value['plots']]
citizens = SimpleNamespace(SCHEMA=citizens_SCHEMA, PLOT_FIELDS=citizens_PLOT_FIELDS, FIELDS=citizens_FIELDS, MAX_PLOTS=citizens_MAX_PLOTS, uint=citizens_uint, _validate_plot=citizens__validate_plot, validate_action=citizens_validate_action, validate_catalog=citizens_validate_catalog, actions=citizens_actions)

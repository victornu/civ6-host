"""Join the existing visible observation and official revealed-plot reader.

The result follows the shipped plot tooltip's reveal/resource predicates.
It is a current tooltip view, not a reconstructed history of the fog of war.
No units, foreign production queues or extra global state are added here.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy, hashlib, json
from civ6_host.runtime.native.native_player_observation import parse_player_observation
from civ6_host.runtime.native.native_revealed_plot_observation import parse_revealed_plot_observation
from civ6_host.runtime.native.native_revealed_plot_observation import observe_revealed_plots
SCHEMA = 'civ6rl.saved_player_map933.v1'
FIELDS = {'schema', 'player_id', 'turn', 'width', 'height', 'plots', 'visible_observation_id', 'source', 'historical_memory_proven', 'graphical_differential_proven', 'complete_player_observation'}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def _validate_visible(value):
    if type(value) is not dict:
        raise ValueError('Missing visible player observation')
    return parse_player_observation(json.dumps(value, allow_nan=False), value.get('player_id'))

def validate(value, player_id, turn, *, visible=None):
    if type(value) is not dict or set(value) != FIELDS or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != player_id) or (type(value['turn']) is not int) or (value['turn'] != turn) or (value['source'] != 'official_plot_tooltip_revealed_live_getters') or any((value[k] is not False for k in ('historical_memory_proven', 'graphical_differential_proven', 'complete_player_observation'))):
        raise ValueError('Foreign or malformed saved player map')
    pin = value['visible_observation_id']
    if type(pin) is not str or len(pin) != 64 or any((c not in '0123456789abcdef' for c in pin)):
        raise ValueError('Invalid visible observation identity')
    if type(value['plots']) is not list or len(value['plots']) > 16384:
        raise ValueError('Unbounded player map')
    native_rows = []
    for row in value['plots']:
        if type(row) is not dict or type(row.get('visible')) is not bool:
            raise ValueError('Player map visibility must be Boolean')
        native_rows.append({k: v for k, v in row.items() if k != 'visible'})
    revealed = parse_revealed_plot_observation(json.dumps(dict(schema='civ6rl-revealed-plot-observation-v1', player_id=player_id, observer_id=player_id, turn=turn, width=value['width'], height=value['height'], plots=native_rows), allow_nan=False), player_id)
    for row in revealed['plots']:
        if row['index'] != row['x'] + row['y'] * revealed['width']:
            raise ValueError('Player map geometry differs')
    if visible is not None:
        observation = _validate_visible(visible)
        if observation['player_id'] != player_id or observation['turn'] != turn or observation['width'] != value['width'] or (observation['height'] != value['height']) or (digest(observation) != pin):
            raise ValueError('Player map belongs to another visible observation')
        observed = {r['index']: r for r in observation['plots']}
        displayed = {r['index']: r for r in value['plots'] if r['visible']}
        if observed != displayed:
            raise ValueError('Player map and visible plot fields disagree')
    return value

def combine(visible, revealed):
    observation = _validate_visible(visible)
    pid = observation['player_id']
    turn = observation['turn']
    source = parse_revealed_plot_observation(json.dumps(revealed, allow_nan=False), pid)
    if any((source[k] != observation[k] for k in ('turn', 'width', 'height'))):
        raise ValueError('Revealed and visible observations crossed boundaries')
    indices = {p['index'] for p in observation['plots']}
    result = dict(schema=SCHEMA, player_id=pid, turn=turn, width=source['width'], height=source['height'], plots=[dict(copy.deepcopy(p), visible=p['index'] in indices) for p in source['plots']], visible_observation_id=digest(observation), source='official_plot_tooltip_revealed_live_getters', historical_memory_proven=False, graphical_differential_proven=False, complete_player_observation=False)
    return validate(result, pid, turn, visible=observation)

def observe(prefix, visible):
    observation = _validate_visible(visible)
    revealed = observe_revealed_plots(prefix.runtime, prefix.ui_child, observation['player_id'])
    return combine(observation, revealed)

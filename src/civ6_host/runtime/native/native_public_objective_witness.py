"""Narrow owner-public objective witnesses, separate from every actor input.

The official UI getters accept an explicit player userdata. This reader never
changes the local player, enumerates opponents, or substitutes empty state for
an unavailable player. The surrounding worker proves an idle published boundary.
Static getter qualification does not by itself qualify an exercise or cache
freshness for nonactive players; a grouped native witness remains necessary.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
import hashlib
import json
from pathlib import Path
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_public_objective_witness.py')))).resolve().parents[1]
PROOF = ROOT / 'work/public-objective-witness/source.json'
SOURCE_SHA = '16b8b2e2c3bec1e06593184fc93e807be3b3ba4d4a23bea77c3c34e31d254a37'
CORE_SHA = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
SCHEMA = 'civ6rl.public_skill_witness.v1'
BOUNDARY_SCHEMA = 'civ6rl.public_objective_boundary.v1'
PAYLOAD_SCHEMA = 'civ6rl.public_objective_payload.v1'
MAX_BYTES = 2 * 1024 * 1024
MAX_BOUNDARY_BYTES = 8 * 1024 * 1024

def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate public witness JSON key')
        value[key] = item
    return value

def _loads(raw):
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=lambda token: (_ for _ in ()).throw(ValueError('nonfinite ' + token)))

def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid ' + label)
    return value

def validate_players(value):
    """Explicit tracked roster; default None/[] disables all extra reads."""
    if value is None:
        return []
    if type(value) is not list or any((type(pid) is not int or pid not in (0, 1, 2, 3) for pid in value)) or value != sorted(set(value)):
        raise ValueError('public_objective_players must be a sorted unique Hotseat player list')
    return list(value)

def verify_source():
    raw = _resolve_resource_path(PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Public witness source proof changed')
    value = _loads(raw)
    if value.get('core', {}).get('sha256') != CORE_SHA:
        raise ValueError('Public witness Core source differs')
    return value

def _source_for(player_id, turn, active_player_id):
    _integer(player_id, 0, 63, 'witness player')
    _integer(turn, 0, 1000000, 'witness turn')
    _integer(active_player_id, 0, 63, 'active player')
    return 'local pid=__PID__\nlocal function context()\n  return Game.GetLocalPlayer(),Game.GetLocalObserver(),Game.GetCurrentGameTurn()\nend\nlocal lp0,ob0,t0=context()\nassert(lp0==__ACTIVE__ and ob0==__ACTIVE__ and t0==__TURN__,\'public witness context mismatch\')\nlocal player=Players[pid]\nassert(player~=nil,\'tracked public player unavailable\')\nlocal function integer(v,label)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge and v%1==0,\'invalid \'..label)\n  return string.format(\'%.0f\',v)\nend\nlocal function number(v,label)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge,\'invalid \'..label)\n  return string.format(\'%.17g\',v)\nend\nlocal width,height=Map.GetGridSize()\nassert(width>=1 and height>=1 and width*height<=16384,\'public map size outside bound\')\nlocal cities,units={},{}\nfor _,city in player:GetCities():Members() do\n  assert(city:GetOwner()==pid,\'foreign city in public witness\')\n  assert(#cities<4096,\'public city row limit exceeded\')\n  cities[#cities+1]=\'{"id":\'..integer(city:GetID(),\'city id\')..\',"owner":\'..integer(pid,\'owner\')..\n    \',"x":\'..integer(city:GetX(),\'city x\')..\',"y":\'..integer(city:GetY(),\'city y\')..\'}\'\nend\nfor _,unit in player:GetUnits():Members() do\n  assert(unit:GetOwner()==pid,\'foreign unit in public witness\')\n  assert(#units<4096,\'public unit row limit exceeded\')\n  units[#units+1]=\'{"id":\'..integer(unit:GetID(),\'unit id\')..\',"owner":\'..integer(pid,\'owner\')..\n    \',"x":\'..integer(unit:GetX(),\'unit x\')..\',"y":\'..integer(unit:GetY(),\'unit y\')..\n    \',"type":\'..integer(unit:GetType(),\'unit type\')..\'}\'\nend\nlocal gold=player:GetTreasury():GetGoldBalance()\nlocal lp1,ob1,t1=context()\nassert(lp0==lp1 and ob0==ob1 and t0==t1,\'public witness context changed\')\nreturn \'{"schema":"civ6rl.public_objective_payload.v1","local_player_before":\'..integer(lp0,\'local\')..\n \',"observer_before":\'..integer(ob0,\'observer\')..\',"turn_before":\'..integer(t0,\'turn\')..\n \',"local_player_after":\'..integer(lp1,\'local\')..\',"observer_after":\'..integer(ob1,\'observer\')..\n \',"turn_after":\'..integer(t1,\'turn\')..\',"observation":{"schema":"civ6rl-public-skill-observation-v1",\'..\n \'"player_id":\'..integer(pid,\'player\')..\',"turn":\'..integer(t0,\'turn\')..\n \',"width":\'..integer(width,\'width\')..\',"height":\'..integer(height,\'height\')..\n \',"cities":[\'..table.concat(cities,\',\')..\'],"units":[\'..table.concat(units,\',\')..\n \'],"economy":{"gold":\'..number(gold,\'gold\')..\'}}}\'\n'.replace('__PID__', str(player_id)).replace('__TURN__', str(turn)).replace('__ACTIVE__', str(active_player_id)).encode('ascii')

def parse_payload(payload, *, player_id, turn, active_player_id):
    from civ6_host.runtime.native.public_continuity import project_public_observation
    _source_for(player_id, turn, active_player_id)
    if type(payload) is str:
        payload = payload.encode('utf-8')
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_BYTES:
        raise ValueError('Public witness payload byte bound')
    value = _loads(payload)
    context = {'local_player_before': active_player_id, 'local_player_after': active_player_id, 'observer_before': active_player_id, 'observer_after': active_player_id, 'turn_before': turn, 'turn_after': turn}
    if type(value) is not dict or set(value) != {'schema', 'observation', *context} or value['schema'] != PAYLOAD_SCHEMA:
        raise ValueError('Public witness payload schema differs')
    if any((type(value[key]) is not int or value[key] != expected for key, expected in context.items())):
        raise ValueError('Public witness context guard differs')
    if type(value['observation']) is not dict or value['observation'].get('schema') != 'civ6rl-public-skill-observation-v1':
        raise ValueError('Public witness requires only the narrow observation schema')
    observation = project_public_observation(value['observation'])
    if observation['schema'] != 'civ6rl-public-skill-observation-v1' or (observation['player_id'], observation['turn']) != (player_id, turn):
        raise ValueError('Public witness observation identity differs')
    for key in ('cities', 'units'):
        observation[key].sort(key=lambda row: row['id'])
    return observation

def source_pins():
    """Additional closure files; all flat native modules are already pinned."""
    from civ6_host.runtime.native import public_continuity as skill_task991
    verify_source()
    paths = [_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_public_objective_witness.py')))).resolve(), PROOF, _resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(skill_task991)))).resolve()]
    return {str(path.relative_to(ROOT)): hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() for path in paths}

def sources_from_closure(closure):
    from civ6_host.runtime.native.public_continuity import validate_public_sources
    transport = closure.get('stdout_transport', {})
    source = str(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_public_objective_witness.py')))).resolve().relative_to(ROOT))
    result = dict(gamecore_sha256=transport.get('core_sha256'), host_sha256=transport.get('host_sha256'), collector_source_sha256=closure.get('pins', {}).get(source))
    validate_public_sources(result)
    if result['gamecore_sha256'] != CORE_SHA:
        raise ValueError('Public witness requires the pinned Base Core')
    return result

def collect(prefix, *, player_id, sequence, turn, active_player_id, closure, closure_path):
    """One requested owner's public state, no perspective mutation or action."""
    from civ6_host.runtime.native.native_episode_identity import require_episode
    from civ6_host.runtime.native.public_continuity import validate_public_witness
    _integer(sequence, 0, 2147483647, 'witness sequence')
    if type(closure) is not dict or player_id not in validate_players(closure.get('public_objective_players')):
        raise ValueError('Public objective witness opt-in missing for requested player')
    identity = require_episode(prefix)
    pins = source_pins()
    if any((closure.get('pins', {}).get(path) != pin for path, pin in pins.items())):
        raise ValueError('Public objective source is not pinned in closure')
    sources = sources_from_closure(closure)
    path = _resolve_resource_path(Path(closure_path))
    before = _resolve_resource_path(path).read_bytes()
    if _loads(before) != closure:
        raise ValueError('Public objective closure differs from file')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _source_for(player_id, turn, active_player_id), b'@public_objective_witness', capacity=MAX_BYTES)
    observation = parse_payload(raw, player_id=player_id, turn=turn, active_player_id=active_player_id)
    if source_pins() != pins or _resolve_resource_path(path).read_bytes() != before or require_episode(prefix) != identity:
        raise RuntimeError('Public objective source, closure or episode changed during read')
    result = dict(schema=SCHEMA, episode_id=identity.episode_id, game_generation=identity.game_generation, player_id=player_id, sequence=sequence, sources=sources, observation=observation)
    return validate_public_witness(result, sources=sources, episode_id=identity.episode_id, game_generation=identity.game_generation, player_id=player_id, sequence=sequence)

def boundary_path(run, sequence):
    _integer(sequence, 0, 2147483647, 'boundary sequence')
    return _resolve_resource_path(Path(run)) / 'public-objective' / ('sequence-%08d.json' % sequence)

def validate_boundary(value, *, response, players, sources, nonce):
    from civ6_host.runtime.native.public_continuity import validate_public_witness
    from civ6_host.runtime.native.public_continuity import project_public_observation
    from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
    players = validate_players(players)
    if not players:
        raise ValueError('Public objective tracking is disabled')
    if type(response) is not dict or response.get('nonce') != nonce:
        raise ValueError('Public boundary response nonce differs')
    identity = DiagnosticEpisodeIdentity(response['episode_id'], response['game_generation'])
    sequence = _integer(response['sequence'], 0, 2147483647, 'response sequence')
    native = response['outcome']['native_victory']
    turn = _integer(native['current_game_turn'], 0, 1000000, 'boundary turn')
    active = _integer(native['player_id'], 0, 63, 'boundary active player')
    expected = dict(schema=BOUNDARY_SCHEMA, nonce=nonce, episode_id=identity.episode_id, game_generation=identity.game_generation, sequence=sequence, turn=turn, active_player_id=active)
    if type(value) is not dict or set(value) != {*expected, 'public_witnesses'} or any((type(value[key]) is not type(wanted) or value[key] != wanted for key, wanted in expected.items())):
        raise ValueError('Public objective boundary identity differs')
    rows = value['public_witnesses']
    if type(rows) is not list or len(rows) != len(players):
        raise ValueError('Public objective tracked roster differs')
    result = {}
    for pid, row in zip(players, rows):
        checked = validate_public_witness(row, sources=sources, episode_id=identity.episode_id, game_generation=identity.game_generation, player_id=pid, sequence=sequence)
        if checked['observation']['turn'] != turn:
            raise ValueError('Public objective turn differs')
        result[pid] = checked
    observation = response.get('observation')
    if observation is not None and active in result:
        projected = project_public_observation(observation)
        for key in ('cities', 'units'):
            projected[key].sort(key=lambda row: row['id'])
        if projected != result[active]['observation']:
            raise ValueError('Active public objective projection differs')
    elif observation is None and native.get('episode_terminated') is not True:
        raise ValueError('Missing public observation outside native terminal')
    return copy.deepcopy(result)

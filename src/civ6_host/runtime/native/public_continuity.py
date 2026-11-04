from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
import json
import math
import re
PUBLIC_WITNESS_SCHEMA = 'civ6rl.public_skill_witness.v1'
PUBLIC_OBSERVATION_SCHEMA = 'civ6rl-public-skill-observation-v1'
_PUBLIC_SOURCES = {'gamecore_sha256', 'host_sha256', 'collector_source_sha256'}

def project_public_observation(value):
    """Minimal owned-state reward view; never a replacement for actor observations."""
    _require(type(value) is dict and value.get('schema') in ('civ6rl-player-observation-v1', PUBLIC_OBSERVATION_SCHEMA), 'unsupported public objective observation')
    if value['schema'] == 'civ6rl-player-observation-v1':
        from civ6_host.runtime.native.native_player_observation import parse_player_observation
        parse_player_observation(json.dumps(value, allow_nan=False), value.get('player_id'))
        result = {key: copy.deepcopy(value[key]) for key in ('player_id', 'turn', 'width', 'height')}
        result.update(schema=PUBLIC_OBSERVATION_SCHEMA, cities=[{key: row[key] for key in ('id', 'owner', 'x', 'y')} for row in value['cities']], units=[{key: row[key] for key in ('id', 'owner', 'x', 'y', 'type')} for row in value['units']], economy={'gold': value['economy']['gold']})
    else:
        result = copy.deepcopy(value)
    _require(set(result) == {'schema', 'player_id', 'turn', 'width', 'height', 'cities', 'units', 'economy'}, 'public objective observation fields differ')
    pid = _int(result['player_id'], 0, 63, 'public objective player')
    _int(result['turn'], 0, 1000000, 'public objective turn')
    width = _int(result['width'], 1, 16384, 'public objective width')
    height = _int(result['height'], 1, 16384, 'public objective height')
    _require(width * height <= 16384, 'public objective map exceeds bound')
    for name in ('cities', 'units'):
        rows = result[name]
        _require(type(rows) is list and len(rows) <= 4096, 'invalid public owned entities')
        ids = set()
        coordinates = set()
        fields = {'id', 'owner', 'x', 'y'} | ({'type'} if name == 'units' else set())
        for row in rows:
            _require(type(row) is dict and set(row) == fields, 'public owned entity fields differ')
            _require(type(row['owner']) is int and row['owner'] == pid, 'foreign entity in public objective observation')
            ident = _int(row['id'], 0, 4294967295, 'public entity id')
            _require(ident not in ids, 'duplicate public owned entity')
            ids.add(ident)
            point = (_int(row['x'], 0, width - 1, 'public entity x'), _int(row['y'], 0, height - 1, 'public entity y'))
            if name == 'cities':
                _require(point not in coordinates, 'duplicate public city coordinates')
                coordinates.add(point)
            else:
                _int(row['type'], 0, 2147483647, 'public unit type index')
    economy = result['economy']
    _require(type(economy) is dict and set(economy) == {'gold'}, 'public objective economy fields differ')
    gold = economy['gold']
    _require(type(gold) in (int, float) and math.isfinite(gold) and (abs(gold) <= 1000000000000.0), 'invalid public objective gold')
    return result

def validate_public_sources(sources):
    """Check declared producer pins; this does not authenticate native execution."""
    _require(type(sources) is dict and set(sources) == _PUBLIC_SOURCES, 'public continuity source fields differ')
    _require(all((type(v) is str and re.fullmatch('[0-9a-f]{64}', v) for v in sources.values())), 'invalid public continuity source digest')
    return copy.deepcopy(sources)

def validate_public_witness(value, *, sources, episode_id, game_generation, player_id, sequence):
    """Bind one public view to an actual global receipt boundary, outside actor inputs."""
    validate_public_sources(sources)
    fields = {'schema', 'episode_id', 'game_generation', 'player_id', 'sequence', 'sources', 'observation'}
    _require(type(value) is dict and set(value) == fields and (value['schema'] == PUBLIC_WITNESS_SCHEMA), 'public continuity witness fields/schema differ')
    for key, expected in (('episode_id', episode_id), ('game_generation', game_generation), ('player_id', player_id), ('sequence', sequence)):
        _require(type(value[key]) is type(expected) and value[key] == expected, 'public continuity witness ' + key + ' differs')
    _require(type(episode_id) is str and bool(episode_id) and (type(game_generation) is str) and bool(game_generation), 'public continuity episode identity missing')
    _int(player_id, 0, 63, 'public witness player')
    _int(sequence, 0, 2147483647, 'public witness sequence')
    _require(value['sources'] == sources, 'public continuity witness sources differ')
    _require(type(value['observation']) is dict and value['observation'].get('schema') == PUBLIC_OBSERVATION_SCHEMA, 'public continuity requires its narrow observation schema')
    observation = project_public_observation(value['observation'])
    _require(observation['player_id'] == player_id, 'public continuity observation is foreign')
    return copy.deepcopy(value)

def _require(condition, message):
    if not condition:
        raise ValueError(message)

def _int(value, low, high, label):
    _require(type(value) is int and low <= value <= high, 'invalid ' + label)
    return value

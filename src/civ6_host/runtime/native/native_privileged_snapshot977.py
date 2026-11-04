"""Opt-in privileged native snapshot for a training-only critic sidecar.

This data is deliberately not an agent observation or an action catalogue.
It is emitted as a separately identified diagnostic record.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
from pathlib import Path
from typing import Any
SCHEMA = 'civ6rl.native_privileged_critic_snapshot977.v1'
MAX_UNITS = 4096
MAX_BYTES = 2 * 1024 * 1024
_MAX_PLAYER_ID = 63

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate snapshot JSON key')
        result[key] = value
    return result

def _source(pid: int, turn: int) -> bytes:
    return 'local pid=__PID__\nlocal function context()\n  assert(Game and type(Game.GetLocalPlayer)==\'function\' and type(Game.GetLocalObserver)==\'function\' and\n         type(Game.GetCurrentGameTurn)==\'function\',\'native context getters unavailable\')\n  return Game.GetLocalPlayer(),Game.GetLocalObserver(),Game.GetCurrentGameTurn()\nend\nlocal lp0,ob0,t0=context()\nassert(lp0==pid and ob0==pid,\'privileged snapshot perspective mismatch\')\nassert(t0==__TURN__,\'privileged snapshot turn mismatch\')\nassert(Players~=nil,\'player table unavailable\')\nlocal function integer(v,label)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge and v%1==0,\n         \'invalid integer: \'..label)\n  return string.format(\'%.0f\',v)\nend\nlocal function number(v,label)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge,\n         \'invalid number: \'..label)\n  return string.format(\'%.17g\',v)\nend\nlocal players,units={},{}\nlocal count=0\nfor p=0,63 do\n  local player=Players[p]\n  if player~=nil then\n    assert(type(player.IsAlive)==\'function\',\'IsAlive getter unavailable\')\n    local alive=player:IsAlive()\n    assert(type(alive)==\'boolean\',\'IsAlive result type\')\n    if alive then\n      assert(type(player.GetUnits)==\'function\' and type(player.GetTreasury)==\'function\',\n             \'player units/treasury getter unavailable\')\n      local collection=player:GetUnits()\n      assert(collection~=nil and type(collection.Members)==\'function\',\'unit Members getter unavailable\')\n      local treasury=player:GetTreasury()\n      assert(treasury~=nil and type(treasury.GetGoldBalance)==\'function\',\'gold getter unavailable\')\n      local gold=treasury:GetGoldBalance()\n      players[#players+1]=\'{"player_id":\'..integer(p,\'player_id\')..\',"gold":\'..number(gold,\'gold\')..\'}\'\n      for _,unit in collection:Members() do\n        count=count+1\n        assert(count<=4096,\'privileged unit bound exceeded\')\n        assert(unit~=nil and type(unit.GetID)==\'function\' and type(unit.GetOwner)==\'function\' and\n               type(unit.GetType)==\'function\' and type(unit.GetX)==\'function\' and type(unit.GetY)==\'function\',\n               \'unit getter unavailable\')\n        local owner=unit:GetOwner()\n        assert(owner==p,\'unit ownership changed during enumeration\')\n        units[#units+1]=\'{"id":\'..integer(unit:GetID(),\'unit id\')..\',"owner":\'..integer(owner,\'owner\')..\n          \',"type":\'..integer(unit:GetType(),\'unit type\')..\',"x":\'..integer(unit:GetX(),\'x\')..\n          \',"y":\'..integer(unit:GetY(),\'y\')..\'}\'\n      end\n    end\n  end\nend\nlocal lp1,ob1,t1=context()\nassert(lp1==lp0 and ob1==ob0 and t1==t0 and lp1==pid and ob1==pid and t1==__TURN__,\n       \'native context changed during privileged snapshot\')\nreturn \'{"schema":"civ6rl-native-privileged-payload977-v1","local_player_before":\'..integer(lp0,\'local player\')..\n  \',"observer_before":\'..integer(ob0,\'observer\')..\',"turn_before":\'..integer(t0,\'turn\')..\n  \',"local_player_after":\'..integer(lp1,\'local player\')..\',"observer_after":\'..integer(ob1,\'observer\')..\n  \',"turn_after":\'..integer(t1,\'turn\')..\',"players":[\'..table.concat(players,\',\')..\n  \'],"units":[\'..table.concat(units,\',\')..\']}\'\n'.replace('__PID__', str(pid)).replace('__TURN__', str(turn)).encode('ascii')

def _source_for(pid: int, turn: int) -> bytes:
    if type(pid) is not int or not 0 <= pid <= _MAX_PLAYER_ID or type(turn) is not int or (turn < 0):
        raise ValueError('invalid native snapshot context')
    return _source(pid, turn)

def parse_payload(payload: bytes | str, *, player_id: int, turn: int) -> dict[str, Any]:
    if type(payload) is bytes:
        if not payload or len(payload) > MAX_BYTES:
            raise ValueError('snapshot payload outside byte bound')
        raw = payload.decode('utf-8', 'strict')
    elif type(payload) is str:
        if not payload or len(payload.encode('utf-8')) > MAX_BYTES:
            raise ValueError('snapshot payload outside byte bound')
        raw = payload
    else:
        raise TypeError('payload must be bytes or str')
    try:
        data = json.loads(raw, object_pairs_hook=_unique, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('invalid privileged snapshot payload') from exc
    expected = {'schema', 'local_player_before', 'observer_before', 'turn_before', 'local_player_after', 'observer_after', 'turn_after', 'players', 'units'}
    if type(data) is not dict or set(data) != expected or data['schema'] != 'civ6rl-native-privileged-payload977-v1':
        raise ValueError('snapshot payload schema mismatch')
    for k in ('local_player_before', 'observer_before', 'turn_before', 'local_player_after', 'observer_after', 'turn_after'):
        if type(data[k]) is not int:
            raise ValueError('snapshot context must be integer')
    if data['local_player_before'] != player_id or data['local_player_after'] != player_id or data['observer_before'] != player_id or (data['observer_after'] != player_id) or (data['turn_before'] != turn) or (data['turn_after'] != turn):
        raise ValueError('snapshot context guard mismatch')
    if type(data['players']) is not list or type(data['units']) is not list or len(data['units']) > MAX_UNITS:
        raise ValueError('snapshot rows outside bounds')
    player_ids, unit_keys = (set(), set())
    for row in data['players']:
        if type(row) is not dict or set(row) != {'player_id', 'gold'} or type(row['player_id']) is not int or (not 0 <= row['player_id'] <= 63):
            raise ValueError('invalid snapshot player row')
        if row['player_id'] in player_ids or type(row['gold']) not in (int, float) or (not math.isfinite(row['gold'])):
            raise ValueError('duplicate player or invalid gold')
        player_ids.add(row['player_id'])
    if player_id not in player_ids:
        raise ValueError('active player is not alive in snapshot')
    for row in data['units']:
        if type(row) is not dict or set(row) != {'id', 'owner', 'type', 'x', 'y'}:
            raise ValueError('invalid snapshot unit row')
        if any((type(row[k]) is not int for k in ('id', 'owner', 'type', 'x', 'y'))):
            raise ValueError('snapshot unit fields must be integers')
        if row['owner'] not in player_ids or not 0 <= row['id'] <= 4294967295 or (not 0 <= row['type'] <= 4294967295) or any((not -1 <= row[k] <= 2147483647 for k in ('x', 'y'))) or ((row['owner'], row['id']) in unit_keys):
            raise ValueError('invalid or duplicate snapshot unit identity')
        unit_keys.add((row['owner'], row['id']))
    data['players'].sort(key=lambda row: row['player_id'])
    data['units'].sort(key=lambda row: (row['owner'], row['id']))
    return data

def collect_privileged_snapshot(prefix: Any, *, player_id: int, sequence: int, turn: int, closure: dict[str, Any], closure_path: str | Path) -> dict[str, Any]:
    """Collect and identify one bounded private snapshot on the owner's UI child."""
    from civ6_host.runtime.native.native_episode_identity import require_episode
    if type(closure) is not dict or closure.get('privileged_critic_diagnostic') is not True:
        raise ValueError('privileged critic diagnostic opt-in is required')
    if type(player_id) is not int or not 0 <= player_id <= _MAX_PLAYER_ID:
        raise ValueError('invalid active player id')
    if type(sequence) is not int or sequence < 0 or type(turn) is not int or (turn < 0):
        raise ValueError('invalid sequence or turn')
    identity = require_episode(prefix)
    transport = closure.get('stdout_transport') if type(closure) is dict else None
    if type(transport) is not dict:
        raise ValueError('closure stdout identity unavailable')
    hashes = {k: transport.get(k) for k in ('core_sha256', 'host_sha256')}
    if any((type(v) is not str or len(v) != 64 or any((c not in '0123456789abcdef' for c in v)) for v in hashes.values())):
        raise ValueError('closure Core/Host identity invalid')
    source_path = _resolve_resource_path(Path(_historical_source_file('civ6rl/native_privileged_snapshot977.py')))
    source_hash_before = hashlib.sha256(_resolve_resource_path(source_path).read_bytes()).hexdigest()
    closure_bytes = _resolve_resource_path(_resolve_resource_path(Path(closure_path))).read_bytes()
    if json.loads(closure_bytes, object_pairs_hook=_unique) != closure:
        raise ValueError('snapshot closure file differs from supplied identity')
    root = _resolve_resource_path(source_path).resolve().parent.parent
    relative_source = str(_resolve_resource_path(source_path).resolve().relative_to(root))
    if closure.get('pins', {}).get(relative_source) != source_hash_before:
        raise ValueError('collector source is not pinned by closure')
    closure_hash = hashlib.sha256(closure_bytes).hexdigest()
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _source_for(player_id, turn), b'@privileged_critic_snapshot977', capacity=MAX_BYTES)
    payload = parse_payload(raw, player_id=player_id, turn=turn)
    source_hash_after = hashlib.sha256(_resolve_resource_path(source_path).read_bytes()).hexdigest()
    if source_hash_after != source_hash_before:
        raise RuntimeError('collector source changed during snapshot')
    if require_episode(prefix) != identity or _resolve_resource_path(_resolve_resource_path(Path(closure_path))).read_bytes() != closure_bytes:
        raise RuntimeError('episode or closure changed during privileged snapshot')
    return dict(schema=SCHEMA, episode_id=identity.episode_id, game_generation=identity.game_generation, player_id=player_id, sequence=sequence, turn=turn, core_sha256=hashes['core_sha256'], host_sha256=hashes['host_sha256'], closure_sha256=closure_hash, collector_source_sha256=source_hash_before, snapshot=payload)

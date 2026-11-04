"""Bounded, local-player-only production snapshots from native UI wrappers.

The Lua source reports current queue state and category-specific native values.
It does not infer costs, turn estimates, completion, or production math.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PRODUCTION_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_production_observation.py')))).resolve().parents[1]
PROOF_SHA256 = 'aa71d6689507aa11cba4ad4de2d49faf6606a5a8b3a955b4f596a58630afa088'
PROOF_PATH = _ROOT / 'evidence/native-city-production-observation' / f'{PROOF_SHA256}.json'
_ASSETS = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_PANEL_SHA256 = '1527d2fd8b2c82d38c228ba2dd75153b3c0bf721c934d1f7cc9cc9ddf98d337f'
_CITY_SUPPORT_SHA256 = '49ebe90ccff94545c86758ae1d50c24fa61914b28be1e3a35729286ca22475f1'
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_OWN_OBSERVATION_SOURCE_SHA256 = 'ba765cbecf31d5def0f09061ee5f7860c826502fff9de7990403caf95f29fcfc'
_OWN_OBSERVATION_CONTRACT_SHA256 = '54e4a29378e5d06dbddf1d6bccfefdd438e0ae770730597b133b4abacae851f5'
_OWN_ROSTER_PROOF_SHA256 = 'b17f02188182e066e6b2fb6e518d3fe3d4b4b663047cfd031ed0b4d98bf8addb'
_MAX_CITIES = 256
_MAX_UNITS = 4096
_MAX_PAYLOAD = 65536

def verify_source(*, core_sha256=_PRODUCTION_BASE_CORE_SHA256) -> None:
    if core_sha256 != _PRODUCTION_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_profile import verify_source as selected_source
        return selected_source(core_sha256)
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise RuntimeError('Pinned city-production source proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_city_production_observation.static.v1' or proof.get('images', {}).get('core', {}).get('sha256') != _CORE_SHA256 or proof.get('callbacks', {}).get('GetProductionYield', {}).get('va') != '0x180513c30' or (proof.get('callbacks', {}).get('GetTurnsLeft', {}).get('va') != '0x180513db0') or (proof.get('callbacks', {}).get('GetUnitProgress', {}).get('va') != '0x180514060'):
        raise RuntimeError('Unexpected native city-production API proof')
    if hashlib.sha256(_resolve_resource_path(_ASSETS / 'Panels/ProductionPanel.lua').read_bytes()).hexdigest() != _PANEL_SHA256:
        raise RuntimeError('Installed ProductionPanel.lua changed')
    if _CITY_SUPPORT_SHA256:
        if hashlib.sha256(_resolve_resource_path(_ASSETS / 'CitySupport.lua').read_bytes()).hexdigest() != _CITY_SUPPORT_SHA256:
            raise RuntimeError('Installed CitySupport.lua changed')

def verify_own_entity_source() -> None:
    """Pin the proven own-unit/city getter source used by the companion roster."""
    source = _ROOT / 'civ6rl/native_player_observation.py'
    contract = _ROOT / 'evidence/native-player-observation-contract.json'
    if hashlib.sha256(_resolve_resource_path(source).read_bytes()).hexdigest() != _OWN_OBSERVATION_SOURCE_SHA256:
        raise RuntimeError('Pinned own-entity observation source changed')
    if hashlib.sha256(_resolve_resource_path(contract).read_bytes()).hexdigest() != _OWN_OBSERVATION_CONTRACT_SHA256:
        raise RuntimeError('Pinned own-entity observation contract changed')
    roster_proof = _ROOT / 'evidence/native-owned-roster-observation' / f'{_OWN_ROSTER_PROOF_SHA256}.json'
    if hashlib.sha256(_resolve_resource_path(roster_proof).read_bytes()).hexdigest() != _OWN_ROSTER_PROOF_SHA256:
        raise RuntimeError('Pinned own-roster observation proof changed')
    proof = json.loads(_resolve_resource_path(contract).read_bytes())
    captures = json.dumps(proof.get('bindings', {}), sort_keys=True)
    source_text = _resolve_resource_path(source).read_text(encoding='utf-8')
    if any((name not in captures for name in ('GetUnits', 'GetCities', 'GetType'))) or 'city:GetPopulation()' not in source_text:
        raise RuntimeError('Own-entity binding contract no longer includes required getters')

def _player_id(player_id: int) -> bytes:
    if type(player_id) is not int or not 0 <= player_id <= 63:
        raise ValueError('player_id must be an exact player slot in [0,63]')
    return str(player_id).encode('ascii')

def production_snapshot_source(player_id: int, *, core_sha256=_PRODUCTION_BASE_CORE_SHA256) -> bytes:
    """Lua chunk returning a bounded current-production snapshot for one local player."""
    pid = _player_id(player_id)
    verify_source(core_sha256=core_sha256)
    return b'local pid=' + pid + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is not the requested player')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive(),'requested local player unavailable')\nassert(GameInfo and GameInfo.Units and GameInfo.Buildings and GameInfo.Districts and GameInfo.Projects,\n       'production definitions unavailable')\nlocal function i32(v,label)\n  assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n         'invalid native signed integer '..label)\n  return string.format('%.0f',v)\nend\nlocal function u32(v,label)\n  assert(type(v)=='number' and v==math.floor(v) and v>=0 and v<=4294967295,\n         'invalid native uint32 '..label)\n  return string.format('%.0f',v)\nend\nlocal cities={}\nlocal seen={}\nlocal count=0\nfor _,city in player:GetCities():Members() do\n  count=count+1\n  assert(count<=" + str(_MAX_CITIES).encode() + b",'too many own cities for diagnostic bound')\n  assert(city and city:GetOwner()==pid,'foreign or invalid city in own collection')\n  local id=city:GetID()\n  assert(type(id)=='number' and id==math.floor(id) and id>=0 and id<=4294967295,\n         'invalid city ID')\n  assert(not seen[id],'duplicate city ID in own collection')\n  seen[id]=true\n  cities[#cities+1]=city\nend\ntable.sort(cities,function(a,b) return a:GetID()<b:GetID() end)\nlocal rows={}\nfor _,city in ipairs(cities) do\n  local queue=city:GetBuildQueue()\n  assert(queue,'native city build queue unavailable')\n  local size=queue:GetSize()\n  assert(type(size)=='number' and size==math.floor(size) and size>=0 and size<=65535,\n         'invalid production queue size')\n  local current=i32(queue:GetCurrentProductionTypeHash(),'current production hash')\n  local previous=i32(queue:GetPreviousProductionTypeHash(),'previous production hash')\n  local nativeYield=i32(queue:GetProductionYield(),'production yield')\n  local hasProgress=queue:HasProductionProgress()\n  assert(type(hasProgress)=='boolean','HasProductionProgress did not return boolean')\n  local turns=i32(queue:GetTurnsLeft(),'current production turns left')\n  local kind,index,cost,progress,formation='N',-1,-1,-1,-1\n  local hash=tonumber(current)\n  if hash~=0 then\n    local matches={}\n    for _,entry in ipairs({\n      {'U',GameInfo.Units,'GetUnitProgress','GetUnitCost'},\n      {'B',GameInfo.Buildings,'GetBuildingProgress','GetBuildingCost'},\n      {'D',GameInfo.Districts,'GetDistrictProgress','GetDistrictCost'},\n      {'P',GameInfo.Projects,'GetProjectProgress','GetProjectCost'},\n    }) do\n      local row=entry[2][hash]\n      if row~=nil then\n        assert(row.Hash==hash,'GameInfo hash lookup returned a different item')\n        matches[#matches+1]={kind=entry[1],row=row,progress=entry[3],cost=entry[4]}\n      end\n    end\n    assert(#matches==1,'current production hash is unknown or ambiguous')\n    local selected=matches[1]; local row=selected.row\n    assert(type(row.Index)=='number' and row.Index==math.floor(row.Index) and row.Index>=0,\n           'current production definition has invalid index')\n    kind=selected.kind; index=row.Index\n    if kind=='U' then\n      assert(MilitaryFormationTypes,'military formation enum unavailable for current unit')\n      formation=queue:GetCurrentProductionTypeModifier()\n      assert(type(formation)=='number' and formation==math.floor(formation),\n             'invalid current unit formation')\n      if formation==MilitaryFormationTypes.STANDARD_FORMATION then\n        cost=queue:GetUnitCost(index)\n      elseif formation==MilitaryFormationTypes.CORPS_FORMATION then\n        cost=queue:GetUnitCorpsCost(index)\n      elseif formation==MilitaryFormationTypes.ARMY_FORMATION then\n        cost=queue:GetUnitArmyCost(index)\n      else\n        error('unsupported current unit formation; refusing estimated cost')\n      end\n    else\n      cost=queue[selected.cost](queue,index)\n    end\n    progress=queue[selected.progress](queue,index)\n    cost=i32(cost,'current item cost'); progress=i32(progress,'current item progress')\n  else\n    -- Zero is the UI's no-current-item sentinel; queue size is reported independently.\n  end\n  local fields={'C',u32(city:GetID(),'city ID'),u32(city:GetOwner(),'city owner'),\n    u32(size,'queue size'),current,previous,nativeYield,hasProgress and '1' or '0',turns,\n    kind,i32(index,'item index'),cost,progress,i32(formation,'formation')}\n  rows[#rows+1]=table.concat(fields,',')\nend\nlocal header=table.concat({'P1',u32(pid,'player ID'),u32(Game.GetCurrentGameTurn(),'game turn'),u32(#rows,'city count')},'|')\nrows[#rows+1]=header\nreturn table.concat(rows,'\\n')\n"

def _integer(text: str, lo: int, hi: int, label: str) -> int:
    if not text or text.strip() != text or (text.startswith('0') and text != '0') or text.startswith('-0'):
        raise ValueError(f'noncanonical {label}')
    try:
        value = int(text, 10)
    except ValueError as exc:
        raise ValueError(f'invalid {label}') from exc
    if str(value) != text or not lo <= value <= hi:
        raise ValueError(f'out-of-range {label}')
    return value

def parse_production_snapshot(payload: bytes, expected_player: int) -> dict:
    """Strictly parse the bounded Lua snapshot; values remain reported values."""
    pid = _player_id(expected_player)
    if type(payload) is not bytes or not 0 < len(payload) <= _MAX_PAYLOAD:
        raise ValueError('production snapshot must be nonempty bytes <=64 KiB')
    try:
        text = payload.decode('ascii')
    except UnicodeDecodeError as exc:
        raise ValueError('production snapshot must be ASCII') from exc
    lines = text.split('\n')
    if not lines or any((not line for line in lines)):
        raise ValueError('empty production snapshot line')
    header = lines[-1].split('|')
    if len(header) != 4 or header[0] != 'P1':
        raise ValueError('invalid production snapshot header')
    parsed_pid = _integer(header[1], 0, 63, 'player ID')
    turn = _integer(header[2], 0, 4294967295, 'game turn')
    count = _integer(header[3], 0, _MAX_CITIES, 'city count')
    if parsed_pid != int(pid) or count != len(lines) - 1:
        raise ValueError('snapshot player/count mismatch')
    cities = []
    previous_id = -1
    for line in lines[:-1]:
        f = line.split(',')
        if len(f) != 14 or f[0] != 'C':
            raise ValueError('invalid city production row')
        city_id = _integer(f[1], 0, 4294967295, 'city ID')
        owner = _integer(f[2], 0, 63, 'city owner')
        size = _integer(f[3], 0, 65535, 'queue size')
        current_hash = _integer(f[4], -2147483648, 2147483647, 'current production hash')
        previous_hash = _integer(f[5], -2147483648, 2147483647, 'previous production hash')
        production_yield = _integer(f[6], -2147483648, 2147483647, 'production yield')
        if f[7] not in ('0', '1'):
            raise ValueError('invalid progress flag')
        turns = _integer(f[8], -2147483648, 2147483647, 'turns left')
        kind = f[9]
        if kind not in ('N', 'U', 'B', 'D', 'P'):
            raise ValueError('invalid production kind')
        index = _integer(f[10], -1, 4294967295, 'item index')
        cost = _integer(f[11], -1, 2147483647, 'item cost')
        progress = _integer(f[12], -1, 2147483647, 'item progress')
        formation = _integer(f[13], -1, 2147483647, 'formation')
        if owner != parsed_pid or city_id <= previous_id:
            raise ValueError('cities are foreign, duplicated, or unsorted')
        if current_hash == 0:
            if kind != 'N' or (index, cost, progress, formation) != (-1, -1, -1, -1):
                raise ValueError('no-production row has inconsistent item fields')
        elif kind == 'N' or min(index, cost, progress) < 0:
            raise ValueError('active production row lacks its native item state')
        elif kind == 'U' and formation < 0:
            raise ValueError('unit production row lacks current formation')
        elif kind != 'U' and formation != -1:
            raise ValueError('non-unit row unexpectedly contains a formation')
        cities.append({'city_id': city_id, 'owner_id': owner, 'queue_size': size, 'current_production_hash': current_hash, 'previous_production_hash': previous_hash, 'production_yield': production_yield, 'has_production_progress': f[7] == '1', 'turns_left': turns, 'kind': kind, 'item_index': None if kind == 'N' else index, 'cost': None if kind == 'N' else cost, 'progress': None if kind == 'N' else progress, 'formation': formation if kind == 'U' else None})
        previous_id = city_id
    return {'player_id': parsed_pid, 'game_turn': turn, 'cities': cities}

def own_entity_snapshot_source(player_id: int) -> bytes:
    """Build a local-player-only unit/city roster for before/after diagnostics.

    The roster reports own units' native ID, type and position, plus own cities'
    ID, position and population. It does not read foreign entities or infer
    that a newly observed unit came from a particular production item.
    """
    pid = _player_id(player_id)
    verify_own_entity_source()
    return b'local pid=' + str(player_id).encode('ascii') + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'roster perspective is not the requested local player')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive(),'requested local player unavailable')\nlocal function i32(v,label)\n  assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n         'invalid signed integer '..label)\n  return string.format('%.0f',v)\nend\nlocal function u32(v,label)\n  assert(type(v)=='number' and v==math.floor(v) and v>=0 and v<=4294967295,\n         'invalid unsigned integer '..label)\n  return string.format('%.0f',v)\nend\nlocal units,unitSeen={},{}\nlocal unitCount=0\nfor _,unit in player:GetUnits():Members() do\n  unitCount=unitCount+1\n  assert(unitCount<=" + str(_MAX_UNITS).encode() + b",'too many own units for roster bound')\n  assert(unit and unit:GetOwner()==pid,'foreign or invalid unit in own collection')\n  local id=unit:GetID()\n  assert(type(id)=='number' and id==math.floor(id) and id>=0 and id<=4294967295,\n         'invalid own unit ID')\n  assert(not unitSeen[id],'duplicate own unit ID')\n  unitSeen[id]=true\n  units[#units+1]={object=unit,id=id}\nend\ntable.sort(units,function(a,b) return a.id<b.id end)\nlocal cities,citySeen={},{}\nlocal cityCount=0\nfor _,city in player:GetCities():Members() do\n  cityCount=cityCount+1\n  assert(cityCount<=" + str(_MAX_CITIES).encode() + b",'too many own cities for roster bound')\n  assert(city and city:GetOwner()==pid,'foreign or invalid city in own collection')\n  local id=city:GetID()\n  assert(type(id)=='number' and id==math.floor(id) and id>=0 and id<=4294967295,\n         'invalid own city ID')\n  assert(not citySeen[id],'duplicate own city ID')\n  citySeen[id]=true\n  cities[#cities+1]={object=city,id=id}\nend\ntable.sort(cities,function(a,b) return a.id<b.id end)\nlocal rows={}\nfor _,entry in ipairs(units) do\n  local unit=entry.object\n  rows[#rows+1]=table.concat({'U',u32(entry.id,'unit ID'),u32(unit:GetOwner(),'unit owner'),\n    i32(unit:GetType(),'unit type'),i32(unit:GetX(),'unit X'),i32(unit:GetY(),'unit Y')},',')\nend\nfor _,entry in ipairs(cities) do\n  local city=entry.object\n  rows[#rows+1]=table.concat({'C',u32(entry.id,'city ID'),u32(city:GetOwner(),'city owner'),\n    i32(city:GetX(),'city X'),i32(city:GetY(),'city Y'),u32(city:GetPopulation(),'city population')},',')\nend\nrows[#rows+1]=table.concat({'R1',u32(pid,'player ID'),u32(Game.GetCurrentGameTurn(),'game turn'),\n  u32(#units,'unit count'),u32(#cities,'city count')},'|')\nreturn table.concat(rows,'\\n')\n"

def parse_own_entity_snapshot(payload: bytes, expected_player: int) -> dict:
    """Strictly parse a bounded own-unit/own-city roster."""
    pid = _player_id(expected_player)
    if type(payload) is not bytes or not 0 < len(payload) <= 256 * 1024:
        raise ValueError('own-entity snapshot must be nonempty bytes <=256 KiB')
    try:
        text = payload.decode('ascii')
    except UnicodeDecodeError as exc:
        raise ValueError('own-entity snapshot must be ASCII') from exc
    lines = text.split('\n')
    if not lines or any((not line for line in lines)):
        raise ValueError('empty own-entity snapshot line')
    h = lines[-1].split('|')
    if len(h) != 5 or h[0] != 'R1':
        raise ValueError('invalid own-entity snapshot header')
    parsed_pid = _integer(h[1], 0, 63, 'player ID')
    turn = _integer(h[2], 0, 4294967295, 'game turn')
    unit_count = _integer(h[3], 0, _MAX_UNITS, 'unit count')
    city_count = _integer(h[4], 0, _MAX_CITIES, 'city count')
    if parsed_pid != int(pid) or unit_count + city_count != len(lines) - 1:
        raise ValueError('own-entity snapshot scope or count mismatch')
    units, cities = ([], [])
    previous_unit = previous_city = -1
    saw_city = False
    for line in lines[:-1]:
        f = line.split(',')
        if f[0] == 'U' and len(f) == 6 and (not saw_city):
            unit_id = _integer(f[1], 0, 4294967295, 'unit ID')
            owner = _integer(f[2], 0, 63, 'unit owner')
            kind = _integer(f[3], -2147483648, 2147483647, 'unit type')
            x = _integer(f[4], -2147483648, 2147483647, 'unit X')
            y = _integer(f[5], -2147483648, 2147483647, 'unit Y')
            if owner != parsed_pid or unit_id <= previous_unit:
                raise ValueError('unit is foreign, duplicated, or unsorted')
            units.append({'unit_id': unit_id, 'owner_id': owner, 'type': kind, 'x': x, 'y': y})
            previous_unit = unit_id
        elif f[0] == 'C' and len(f) == 6:
            saw_city = True
            city_id = _integer(f[1], 0, 4294967295, 'city ID')
            owner = _integer(f[2], 0, 63, 'city owner')
            x = _integer(f[3], -2147483648, 2147483647, 'city X')
            y = _integer(f[4], -2147483648, 2147483647, 'city Y')
            population = _integer(f[5], 0, 4294967295, 'city population')
            if owner != parsed_pid or city_id <= previous_city:
                raise ValueError('city is foreign, duplicated, or unsorted')
            cities.append({'city_id': city_id, 'owner_id': owner, 'x': x, 'y': y, 'population': population})
            previous_city = city_id
        else:
            raise ValueError('invalid or out-of-order own-entity row')
    if len(units) != unit_count or len(cities) != city_count or len(units) + len(cities) != len(lines) - 1:
        raise ValueError('own-entity rows do not match declared counts')
    return {'player_id': parsed_pid, 'game_turn': turn, 'units': units, 'cities': cities}

def diff_production_observations(before_production: dict, after_production: dict, before_roster: dict, after_roster: dict) -> dict:
    """Compare bounded snapshots without attributing unit creation to production."""
    groups = (before_production, after_production, before_roster, after_roster)
    if any((not isinstance(item, dict) for item in groups)):
        raise ValueError('production diff requires four parsed snapshots')
    player = before_production.get('player_id')
    if type(player) is not int or any((item.get('player_id') != player for item in groups)) or before_production.get('game_turn') != before_roster.get('game_turn') or (after_production.get('game_turn') != after_roster.get('game_turn')) or (type(before_production.get('game_turn')) is not int) or (type(after_production.get('game_turn')) is not int) or (after_production['game_turn'] < before_production['game_turn']):
        raise ValueError('snapshots must share one player and aligned nondecreasing turns')

    def unique(items, key, label):
        if not isinstance(items, list):
            raise ValueError(f'{label} rows must be a list')
        indexed = {}
        for row in items:
            if not isinstance(row, dict) or type(row.get(key)) is not int or type(row.get('owner_id')) is not int or (row[key] in indexed):
                raise ValueError(f'{label} rows must have unique integer IDs')
            if row.get('owner_id') != player:
                raise ValueError(f'{label} row belongs to another player')
            indexed[row[key]] = row
        return indexed
    old_units = unique(before_roster.get('units'), 'unit_id', 'unit')
    new_units = unique(after_roster.get('units'), 'unit_id', 'unit')
    old_unit_ids, new_unit_ids = (set(old_units), set(new_units))
    added = [new_units[i] for i in sorted(new_unit_ids - old_unit_ids)]
    removed = [old_units[i] for i in sorted(old_unit_ids - new_unit_ids)]
    changed_units = []
    for unit_id in sorted(old_unit_ids & new_unit_ids):
        if old_units[unit_id] != new_units[unit_id]:
            changed_units.append({'before': old_units[unit_id], 'after': new_units[unit_id]})
    old_roster_cities = unique(before_roster.get('cities'), 'city_id', 'own city')
    new_roster_cities = unique(after_roster.get('cities'), 'city_id', 'own city')
    old_city_ids, new_city_ids = (set(old_roster_cities), set(new_roster_cities))
    added_cities = [new_roster_cities[i] for i in sorted(new_city_ids - old_city_ids)]
    removed_cities = [old_roster_cities[i] for i in sorted(old_city_ids - new_city_ids)]
    changed_cities = []
    for city_id in sorted(old_city_ids & new_city_ids):
        if old_roster_cities[city_id] != new_roster_cities[city_id]:
            changed_cities.append({'before': old_roster_cities[city_id], 'after': new_roster_cities[city_id]})
    old_cities = unique(before_production.get('cities'), 'city_id', 'city production')
    new_cities = unique(after_production.get('cities'), 'city_id', 'city production')
    city_changes = []
    compared = ('current_production_hash', 'previous_production_hash', 'queue_size', 'has_production_progress', 'turns_left', 'cost', 'progress', 'kind', 'item_index', 'formation')
    for city_id in sorted(set(old_cities) & set(new_cities)):
        old, new = (old_cities[city_id], new_cities[city_id])
        changed = {name: {'before': old.get(name), 'after': new.get(name)} for name in compared if old.get(name) != new.get(name)}
        if changed:
            city_changes.append({'city_id': city_id, 'changes': changed})
    return {'player_id': player, 'before_turn': before_production['game_turn'], 'after_turn': after_production['game_turn'], 'own_units_added': added, 'own_units_removed': removed, 'own_units_changed': changed_units, 'own_cities_added': added_cities, 'own_cities_removed': removed_cities, 'own_cities_changed': changed_cities, 'city_production_changes': city_changes, 'interpretation': 'Observed differences only; no unit-to-production attribution or per-turn production estimate.'}

def own_entity_guard_case_source() -> bytes:
    """HKS test source with local doubles and a foreign-unit rejection case."""
    prefix = b'local Game={GetLocalPlayer=function() return 0 end,GetCurrentGameTurn=function() return 7 end}\nlocal u1={GetOwner=function() return 0 end,GetID=function() return 5 end,GetType=function() return 21 end,\n GetX=function() return 27 end,GetY=function() return 18 end}\nlocal u2={GetOwner=function() return 0 end,GetID=function() return 9 end,GetType=function() return 0 end,\n GetX=function() return 28 end,GetY=function() return 18 end}\nlocal city={GetOwner=function() return 0 end,GetID=function() return 3 end,GetX=function() return 28 end,\n GetY=function() return 18 end,GetPopulation=function() return 1 end}\nlocal function collection(values)\n return {Members=function()\n   local i=0\n   return function() i=i+1; if values[i]~=nil then return i,values[i] end end\n end}\nend\nlocal player={IsAlive=function() return true end,GetUnits=function() return collection({u1,u2}) end,\n GetCities=function() return collection({city}) end}\nlocal Players={[0]=player}\nlocal result=(function()\n'
    suffix = b"\nend)()\nassert(result=='U,5,0,21,27,18\\nU,9,0,0,28,18\\nC,3,0,28,18,1\\nR1|0|7|2|1')\nu2.GetOwner=function() return 1 end\nlocal ok=pcall(function() return (function()\n" + own_entity_snapshot_source(0) + b"\nend)() end)\nassert(not ok,'foreign unit was not refused')\nreturn 'own-roster-guards-ok'\n"
    return prefix + own_entity_snapshot_source(0) + suffix

def guard_case_source() -> bytes:
    """HKS-only source guard using local doubles; it invokes no native action."""
    prefix = b'local Game={GetLocalPlayer=function() return 0 end,GetCurrentGameTurn=function() return 7 end}\nlocal queue={GetSize=function() return 1 end,GetCurrentProductionTypeHash=function() return 19 end,\n GetPreviousProductionTypeHash=function() return 0 end,GetProductionYield=function() return 3 end,\n HasProductionProgress=function() return true end,GetTurnsLeft=function() return 4 end,\n GetCurrentProductionTypeModifier=function() return 10 end,GetUnitCost=function(_,i) assert(i==2);return 40 end,\n GetUnitProgress=function(_,i) assert(i==2);return 12 end}\nlocal city={GetOwner=function() return 0 end,GetID=function() return 5 end,GetBuildQueue=function() return queue end}\nlocal function members() local once=false;return function() if not once then once=true;return 1,city end end end\nlocal p={IsAlive=function() return true end,GetCities=function() return {Members=members} end}\nlocal Players={[0]=p};local GameInfo={Units={[19]={Hash=19,Index=2}},Buildings={},Districts={},Projects={}}\nlocal MilitaryFormationTypes={STANDARD_FORMATION=10,CORPS_FORMATION=11,ARMY_FORMATION=12}\nlocal result=(function()\n'
    suffix = b"\nend)()\nassert(result=='C,5,0,1,19,0,3,1,4,U,2,40,12,10\\nP1|0|7|1')\nlocal oldOwner=city.GetOwner;city.GetOwner=function() return 1 end\nlocal ok=pcall(function() return (function()\n" + production_snapshot_source(0) + b"\nend)() end)\nassert(not ok,'foreign city was not refused')\nreturn 'city-production-guards-ok'\n"
    return prefix + production_snapshot_source(0) + suffix

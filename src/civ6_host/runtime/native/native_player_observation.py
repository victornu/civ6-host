"""Player-scoped, visibility-gated native observation witness.

This is a diagnostic boundary, not a learner transport. It gathers only one
requested player's own entities/economy and currently visible map cells and
foreign units, then returns a bounded JSON string through evaluate_text.
Unrevealed cells are omitted; explored-but-not-visible memory is not rebuilt.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
import math
from typing import Any
_MAX_PLAYER_ID = 63
_MAX_PLOTS = 16384
_MAX_ROWS = 4096
_RESULT_CAPACITY = 2 * 1024 * 1024

def _player_id(value: int) -> int:
    if type(value) is not int or not 0 <= value <= _MAX_PLAYER_ID:
        raise ValueError('player_id must be an integer in [0, 63]')
    return value

def build_player_observation_source(player_id: int) -> bytes:
    """Build a Lua chunk that returns JSON for exactly one player's view.

    Visibility checks precede reads of plot state and enemy-unit fields. Own
    player units/cities are allowed in full; foreign units are admitted only
    after ``IsVisible`` and ``IsUnitVisible`` both return true.
    """
    player_id = _player_id(player_id)
    lua = 'local pid = __PLAYER_ID__\nassert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n       \'observation perspective differs from requested player\')\nassert(type(Game.GetLocalObserver)==\'function\' and Game.GetLocalObserver()==pid,\n       \'observation observer differs from requested player\')\nlocal player = Players[pid]\nlocal visibility = PlayersVisibility and PlayersVisibility[pid]\nassert(player ~= nil and visibility ~= nil, "player observation context unavailable")\nlocal playerResources = player:GetResources()\nassert(playerResources ~= nil and type(playerResources.IsResourceVisible) == \'function\',\n       \'player resource-visibility API unavailable\')\nassert(GameInfo ~= nil and GameInfo.Resources ~= nil, \'resource metadata unavailable\')\nfor _, method in ipairs({\'IsVisible\', \'IsRevealed\', \'IsUnitVisible\'}) do\n  assert(type(visibility[method]) == \'function\', \'visibility API unavailable: \' .. method)\nend\nassert(Units ~= nil and type(Units.GetUnitsInPlotLayerID) == "function" and\n       MapLayers ~= nil and MapLayers.ANY ~= nil, "visible-unit enumeration API unavailable")\nassert(Map ~= nil and type(Map.GetGridSize) == "function" and\n       type(Map.GetPlotCount) == "function" and type(Map.GetPlotByIndex) == "function",\n       "map API unavailable")\nlocal function number(v)\n  assert(type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge,\n         "observation contains non-finite number")\n  return string.format("%.17g", v)\nend\nlocal function boolean(v)\n  assert(type(v) == "boolean", "observation contains non-boolean")\n  return v and "true" or "false"\nend\nlocal function row(fields)\n  return "{" .. table.concat(fields, ",") .. "}"\nend\nlocal function array(rows)\n  return "[" .. table.concat(rows, ",") .. "]"\nend\nlocal w, h = Map.GetGridSize()\nlocal plotCount = Map.GetPlotCount()\nassert(w > 0 and h > 0 and w * h == plotCount and plotCount <= 16384,\n       "map outside diagnostic bounds: " .. tostring(w) .. "x" .. tostring(h) .. ", count=" .. tostring(plotCount))\nlocal plots, ownUnits, visibleEnemies, cities = {}, {}, {}, {}\nlocal seenEnemies = {}\nfor index = 0, plotCount - 1 do\n  -- Plot handle lookup is used only to obtain its public coordinates. No plot\n  -- state is read until this player\'s visibility predicate admits the cell.\n  local plot = Map.GetPlotByIndex(index)\n  assert(plot ~= nil, "missing plot handle")\n  local x, y = plot:GetX(), plot:GetY()\n  local visible = visibility:IsVisible(x, y)\n  local revealed = visibility:IsRevealed(index)\n  if visible then\n    assert(revealed, "visible plot not marked revealed")\n    local fields = {\n      \'"index":\' .. number(index), \'"x":\' .. number(x), \'"y":\' .. number(y),\n      \'"visible":true\', \'"revealed":true\',\n      \'"terrain_type":\' .. number(plot:GetTerrainType()),\n      \'"feature_type":\' .. number(plot:GetFeatureType()),\n      \'"owner":\' .. number(plot:GetOwner()),\n      \'"water":\' .. boolean(plot:IsWater()),\n      \'"impassable":\' .. boolean(plot:IsImpassable())\n    }\n    assert(type(plot.GetResourceType) == \'function\' and type(plot.GetResourceCount) == \'function\',\n           \'plot resource getters unavailable\')\n    local resourceType = plot:GetResourceType()\n    assert(type(resourceType) == \'number\' and resourceType % 1 == 0 and resourceType >= -1,\n           \'invalid plot resource type\')\n    if resourceType >= 0 then\n      local resource = GameInfo.Resources[resourceType]\n      assert(resource ~= nil and type(resource.Hash) == \'number\', \'resource metadata row unavailable\')\n      if playerResources:IsResourceVisible(resource.Hash) then\n        local resourceCount = plot:GetResourceCount()\n        assert(type(resourceCount) == \'number\' and resourceCount % 1 == 0 and resourceCount >= 0,\n               \'invalid visible resource count\')\n        fields[#fields + 1] = \'"resource_type":\' .. number(resourceType)\n        fields[#fields + 1] = \'"resource_count":\' .. number(resourceCount)\n      end\n    end\n    plots[#plots + 1] = row(fields)\n    local found = Units.GetUnitsInPlotLayerID(x, y, MapLayers.ANY)\n    if found ~= nil then\n      for _, unit in pairs(found) do\n          -- Do not inspect owner, identity, type, position, or health until\n          -- native per-player unit visibility has admitted the object.\n          if visibility:IsUnitVisible(unit) and not unit:IsDelayedDeath() then\n            local owner, id = unit:GetOwner(), unit:GetID()\n            if owner ~= pid then\n              local key = tostring(owner) .. ":" .. tostring(id)\n              if not seenEnemies[key] then\n                seenEnemies[key] = true\n                visibleEnemies[#visibleEnemies + 1] = row({\n                  \'"owner":\' .. number(owner), \'"id":\' .. number(id),\n                  \'"type":\' .. number(unit:GetType()), \'"x":\' .. number(unit:GetX()),\n                  \'"y":\' .. number(unit:GetY()), \'"damage":\' .. number(unit:GetDamage()),\n                  \'"visible":true\'\n                })\n              end\n            end\n          end\n      end\n    end\n  end\nend\nfor _, unit in player:GetUnits():Members() do\n  ownUnits[#ownUnits + 1] = row({\n    \'"id":\' .. number(unit:GetID()), \'"type":\' .. number(unit:GetType()),\n    \'"x":\' .. number(unit:GetX()), \'"y":\' .. number(unit:GetY()),\n    \'"damage":\' .. number(unit:GetDamage()),\n    \'"moves":\' .. number(unit:GetMovesRemaining()),\n    \'"max_moves":\' .. number(unit:GetMaxMoves()), \'"owner":\' .. number(pid)\n  })\nend\nfor _, city in player:GetCities():Members() do\n  local yields = {\n    food=city:GetYield(YieldTypes.FOOD), production=city:GetYield(YieldTypes.PRODUCTION),\n    gold=city:GetYield(YieldTypes.GOLD), science=city:GetYield(YieldTypes.SCIENCE),\n    culture=city:GetYield(YieldTypes.CULTURE), faith=city:GetYield(YieldTypes.FAITH)\n  }\n  cities[#cities + 1] = row({\n    \'"id":\' .. number(city:GetID()), \'"x":\' .. number(city:GetX()),\n    \'"y":\' .. number(city:GetY()), \'"population":\' .. number(city:GetPopulation()),\n    \'"owner":\' .. number(pid),\n    \'"yields":\' .. row({\n      \'"food":\' .. number(yields.food), \'"production":\' .. number(yields.production),\n      \'"gold":\' .. number(yields.gold), \'"science":\' .. number(yields.science),\n      \'"culture":\' .. number(yields.culture), \'"faith":\' .. number(yields.faith)\n    })\n  })\nend\nlocal economy = {\n  science=player:GetTechs():GetScienceYield(),\n  culture=player:GetCulture():GetCultureYield(),\n  gold=player:GetTreasury():GetGoldBalance(),\n  faith=player:GetReligion():GetFaithBalance()\n}\nassert(#plots <= plotCount and #ownUnits <= 4096 and #visibleEnemies <= plotCount * 8 and #cities <= 4096,\n       "observation row bound exceeded")\nlocal function sortById(a, b)\n  local x = tonumber(a:match(\'"id":([%-0-9%.eE]+)\'))\n  local y = tonumber(b:match(\'"id":([%-0-9%.eE]+)\'))\n  return x < y\nend\nlocal function sortByOwnerAndId(a, b)\n  local ao = tonumber(a:match(\'"owner":([%-0-9%.eE]+)\'))\n  local bo = tonumber(b:match(\'"owner":([%-0-9%.eE]+)\'))\n  if ao ~= bo then return ao < bo end\n  return sortById(a, b)\nend\ntable.sort(ownUnits, sortById)\ntable.sort(visibleEnemies, sortByOwnerAndId)\ntable.sort(cities, sortById)\nlocal out = \'{"schema":"civ6rl-player-observation-v1","player_id":\' .. number(pid) ..\n  \',"turn":\' .. number(Game.GetCurrentGameTurn()) ..\n  \',"width":\' .. number(w) .. \',"height":\' .. number(h) ..\n  \',"plots":\' .. array(plots) .. \',"units":\' .. array(ownUnits) ..\n  \',"visible_enemy_units":\' .. array(visibleEnemies) .. \',"cities":\' .. array(cities) ..\n  \',"economy":\' .. row({\n    \'"science":\' .. number(economy.science), \'"culture":\' .. number(economy.culture),\n    \'"gold":\' .. number(economy.gold), \'"faith":\' .. number(economy.faith)\n  }) .. \'}\'\nreturn out\n'.replace('__PLAYER_ID__', str(player_id))
    return lua.encode('ascii')

def build_visibility_guard_case(player_id: int=0) -> bytes:
    """Return an HKS Lua case with forbidden-field sentinels.

    The real collector is run against small doubles: the hidden plot's detail
    getters and invisible enemy's identity/state getters throw and increment a
    counter. The chunk asserts zero forbidden accesses and checks that the
    visible plot and admitted enemy appear in the collector's JSON result.
    """
    collector = build_player_observation_source(player_id).decode('ascii')
    return 'local forbidden = 0\nlocal function blocked() forbidden = forbidden + 1; error("forbidden observation read") end\nlocal function plot(x, y, hidden, resourceType, resourceCount)\n  local p = {x=x, y=y, resourceType=resourceType, resourceCount=resourceCount}\n  function p:GetX() return self.x end\n  function p:GetY() return self.y end\n  local function detail(name, value)\n    p[name] = function() if hidden then return blocked() end; return value end\n  end\n  detail("GetTerrainType", 11); detail("GetFeatureType", -1)\n  detail("GetOwner", 0); detail("IsWater", false); detail("IsImpassable", false)\n  function p:GetResourceType() if hidden then return blocked() end; return self.resourceType end\n  function p:GetResourceCount()\n    if hidden or self.resourceType == 3 then return blocked() end\n    return self.resourceCount\n  end\n  return p\nend\nlocal visiblePlot, lockedPlot, hiddenPlot = plot(0, 0, false, 2, 3),\n  plot(1, 0, false, 3, 14), plot(2, 0, true, 4, 9)\nlocal concealed = {allowed=false}\nlocal admitted = {allowed=true}\nlocal function enemy(allowed, id)\n  local u = {allowed=allowed}\n  function u:IsDelayedDeath() return false end\n  function u:GetOwner() if not allowed then return blocked() end; return 1 end\n  function u:GetID() if not allowed then return blocked() end; return id end\n  function u:GetType() if not allowed then return blocked() end; return 21 end\n  function u:GetX() if not allowed then return blocked() end; return 0 end\n  function u:GetY() if not allowed then return blocked() end; return 0 end\n  function u:GetDamage() if not allowed then return blocked() end; return 0 end\n  return u\nend\nconcealed, admitted = enemy(false, 99), enemy(true, 100)\nlocal saved = {Players=Players, PlayersVisibility=PlayersVisibility, Map=Map,\n  MapLayers=MapLayers, Units=Units, YieldTypes=YieldTypes, Game=Game, GameInfo=GameInfo}\nlocal function emptyCollection() return {Members=function() return function() return nil end end} end\nPlayers = {[__PLAYER_ID__]={\n  GetUnits=function() return emptyCollection() end,\n  GetCities=function() return emptyCollection() end,\n  GetResources=function() return {IsResourceVisible=function(_, hash) return hash == 2201 end} end,\n  GetTechs=function() return {GetScienceYield=function() return 0 end} end,\n  GetCulture=function() return {GetCultureYield=function() return 0 end} end,\n  GetTreasury=function() return {GetGoldBalance=function() return 0 end} end,\n  GetReligion=function() return {GetFaithBalance=function() return 0 end} end}}\nPlayersVisibility = {[__PLAYER_ID__]={\n  IsVisible=function(_, x, y) return y == 0 and x < 2 end,\n  IsRevealed=function(_, i) return i < 2 end,\n  IsUnitVisible=function(_, u) return u.allowed end}}\nMap = {GetGridSize=function() return 3, 1 end, GetPlotCount=function() return 3 end,\n  GetPlotByIndex=function(i) return ({visiblePlot, lockedPlot, hiddenPlot})[i + 1] end}\nGameInfo = {Resources={[2]={Hash=2201}, [3]={Hash=3301}, [4]={Hash=4401}}}\nMapLayers = {ANY=0}\nUnits = {GetUnitsInPlotLayerID=function(x, y, _)\n  if x == 0 and y == 0 then return {concealed, admitted} end\n  return {}\nend}\nYieldTypes = {FOOD=0, PRODUCTION=1, GOLD=2, SCIENCE=3, CULTURE=4, FAITH=5}\nGame = {GetCurrentGameTurn=function() return 1 end,\n        GetLocalPlayer=function() return __PLAYER_ID__ end,\n        GetLocalObserver=function() return __PLAYER_ID__ end}\nlocal ok, result = pcall(function()\n__COLLECTOR__\nend)\nGame.GetLocalPlayer=function() return (__PLAYER_ID__+1)%64 end\nlocal wrongOK, wrongError = pcall(function()\n__COLLECTOR__\nend)\nGame.GetLocalPlayer=function() return __PLAYER_ID__ end\nGame.GetLocalObserver=function() return (__PLAYER_ID__+1)%64 end\nlocal observerOK, observerError = pcall(function()\n__COLLECTOR__\nend)\nPlayers, PlayersVisibility, Map, MapLayers, Units, YieldTypes, Game, GameInfo =\n  saved.Players, saved.PlayersVisibility, saved.Map, saved.MapLayers,\n  saved.Units, saved.YieldTypes, saved.Game, saved.GameInfo\nassert(ok, tostring(result))\nassert(not wrongOK and tostring(wrongError):find(\'observation perspective differs\',1,true),\n       \'foreign UI perspective was accepted\')\nassert(not observerOK and tostring(observerError):find(\'observation observer differs\',1,true),\n       \'foreign observer perspective was accepted\')\nassert(forbidden == 0, "hidden plot or invisible unit getter was accessed")\nassert(result:find(\'"terrain_type":11\', 1, true), "visible plot missing")\nassert(result:find(\'"resource_type":2\', 1, true) and\n       result:find(\'"resource_count":3\', 1, true), "visible resource missing")\nassert(not result:find(\'"resource_type":3\', 1, true) and\n       not result:find(\'"resource_count":14\', 1, true), "tech-hidden resource leaked")\nassert(result:find(\'"id":100\', 1, true), "visible enemy missing")\nassert(not result:find(\'"id":99\', 1, true), "invisible enemy leaked")\nreturn result\n'.replace('__PLAYER_ID__', str(_player_id(player_id))).replace('__COLLECTOR__', collector).encode('ascii')

def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate observation key: {key}')
        out[key] = value
    return out

def _finite_number(value: Any, field: str) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{field} must be a finite JSON number')
    return value

def _integer_number(value: Any, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f'{field} must be an integer')
    return value

def _exact_keys(value: Any, expected: set[str], field: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f'{field} has unexpected or missing fields')
    return value

def parse_player_observation(payload: bytes | str, player_id: int) -> dict[str, Any]:
    """Parse and enforce the diagnostic visibility/ownership boundary."""
    player_id = _player_id(player_id)
    if type(payload) is bytes:
        if not payload or len(payload) > _RESULT_CAPACITY:
            raise ValueError('observation payload outside byte bound')
        text = payload.decode('utf-8', 'strict')
    elif type(payload) is str:
        if not payload or len(payload.encode('utf-8')) > _RESULT_CAPACITY:
            raise ValueError('observation payload outside byte bound')
        text = payload
    else:
        raise TypeError('payload must be bytes or str')
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('invalid observation JSON') from exc
    top = _exact_keys(data, {'schema', 'player_id', 'turn', 'width', 'height', 'plots', 'units', 'visible_enemy_units', 'cities', 'economy'}, 'root')
    if top['schema'] != 'civ6rl-player-observation-v1' or top['player_id'] != player_id:
        raise ValueError('observation schema or player scope mismatch')
    for key in ('player_id', 'turn', 'width', 'height'):
        _integer_number(top[key], key)
    if top['player_id'] != player_id or any((top[k] < 0 for k in ('turn', 'width', 'height'))) or top['width'] * top['height'] > _MAX_PLOTS:
        raise ValueError('observation dimensions outside bounds')
    if type(top['plots']) is not list or len(top['plots']) > _MAX_PLOTS or any((type(top[k]) is not list or len(top[k]) > _MAX_ROWS for k in ('units', 'visible_enemy_units', 'cities'))):
        raise ValueError('observation rows outside bounds')
    plot_base_keys = {'index', 'x', 'y', 'visible', 'revealed', 'terrain_type', 'feature_type', 'owner', 'water', 'impassable'}
    plot_resource_keys = {'resource_type', 'resource_count'}
    plot_indices: set[int] = set()
    for row in top['plots']:
        if type(row) is not dict or set(row) not in (plot_base_keys, plot_base_keys | plot_resource_keys):
            raise ValueError('plot has unexpected or missing fields')
        if row['visible'] is not True or row['revealed'] is not True:
            raise ValueError('non-visible or unrevealed plot data rejected')
        for key in ('index', 'x', 'y', 'terrain_type', 'feature_type', 'owner'):
            _integer_number(row[key], 'plot.' + key)
        if not 0 <= row['index'] < top['width'] * top['height']:
            raise ValueError('plot index outside map bounds')
        if not (0 <= row['x'] < top['width'] and 0 <= row['y'] < top['height']):
            raise ValueError('plot coordinates outside map bounds')
        if row['owner'] < -1 or row['owner'] > _MAX_PLAYER_ID:
            raise ValueError('plot owner outside bounds')
        if row['index'] in plot_indices:
            raise ValueError('duplicate plot index')
        plot_indices.add(row['index'])
        if type(row['water']) is not bool or type(row['impassable']) is not bool:
            raise ValueError('plot flags must be Boolean')
        if plot_resource_keys <= row.keys():
            if _integer_number(row['resource_type'], 'plot.resource_type') < 0:
                raise ValueError('plot.resource_type outside bounds')
            if _integer_number(row['resource_count'], 'plot.resource_count') < 0:
                raise ValueError('plot.resource_count outside bounds')
    own_keys = {'id', 'type', 'x', 'y', 'damage', 'moves', 'max_moves', 'owner'}
    for row in top['units']:
        row = _exact_keys(row, own_keys, 'owned unit')
        _integer_number(row['owner'], 'unit.owner')
        if row['owner'] != player_id:
            raise ValueError('foreign unit in owned-unit list')
        for key in ('id', 'type', 'x', 'y', 'moves', 'max_moves'):
            _integer_number(row[key], 'unit.' + key)
        if row['id'] < 0 or not (0 <= row['x'] < top['width'] and 0 <= row['y'] < top['height']):
            raise ValueError('owned unit identity or position outside bounds')
        _finite_number(row['damage'], 'unit.damage')
    enemy_keys = {'owner', 'id', 'type', 'x', 'y', 'damage', 'visible'}
    for row in top['visible_enemy_units']:
        row = _exact_keys(row, enemy_keys, 'visible enemy unit')
        _integer_number(row['owner'], 'visible_enemy_unit.owner')
        if row['owner'] == player_id or row['visible'] is not True:
            raise ValueError('enemy unit lacks visibility or is owned by requested player')
        for key in ('id', 'type', 'x', 'y'):
            _integer_number(row[key], 'visible_enemy_unit.' + key)
        if not 0 <= row['owner'] <= _MAX_PLAYER_ID or row['id'] < 0 or (not (0 <= row['x'] < top['width'] and 0 <= row['y'] < top['height'])):
            raise ValueError('visible enemy identity or position outside bounds')
        _finite_number(row['damage'], 'visible_enemy_unit.damage')
    city_keys = {'id', 'x', 'y', 'population', 'owner', 'yields'}
    yield_keys = {'food', 'production', 'gold', 'science', 'culture', 'faith'}
    for row in top['cities']:
        row = _exact_keys(row, city_keys, 'owned city')
        _integer_number(row['owner'], 'city.owner')
        if row['owner'] != player_id:
            raise ValueError('foreign city in owned-city list')
        for key in ('id', 'x', 'y', 'population'):
            _integer_number(row[key], 'city.' + key)
        if row['id'] < 0 or row['population'] < 0 or (not (0 <= row['x'] < top['width'] and 0 <= row['y'] < top['height'])):
            raise ValueError('owned city identity or position outside bounds')
        yields = _exact_keys(row['yields'], yield_keys, 'city.yields')
        for key, value in yields.items():
            _finite_number(value, 'city.yields.' + key)
    economy = _exact_keys(top['economy'], {'science', 'culture', 'gold', 'faith'}, 'economy')
    for key, value in economy.items():
        _finite_number(value, 'economy.' + key)
    return data

def observe_player(runtime: Any, child: Any, player_id: int, *, capacity: int=_RESULT_CAPACITY) -> dict[str, Any]:
    """Run the bounded diagnostic collector through NativeScriptRuntime.evaluate_text."""
    player_id = _player_id(player_id)
    if type(capacity) is not int or not 0 < capacity <= _RESULT_CAPACITY:
        raise ValueError('capacity outside admitted observation bound')
    source = build_player_observation_source(player_id)
    payload = runtime.evaluate_text(child, source, b'@native_player_observation', capacity=capacity)
    return parse_player_observation(payload, player_id)

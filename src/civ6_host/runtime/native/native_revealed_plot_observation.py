"""Strict diagnostic snapshot of plots admitted by the local player's reveal map.

This intentionally does not reconstruct remembered plot state: after the
IsRevealed gate it reads the same live Plot getters used by the official
tooltip. Resource type/count are exported only after IsResourceVisible.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
import math
from pathlib import Path
from typing import Any
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_MAX_PLAYER_ID = 63
_MAX_PLOTS = 16384
_RESULT_CAPACITY = 2 * 1024 * 1024
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_revealed_plot_observation.py')))).resolve().parents[1]
_PROOF_SHA256 = 'cf39cfa0a7da833afc381cd2c2607cd0518182c70d93b895df7918bc8d14d276'
_PROOF_PATH = _ROOT / 'evidence/native-revealed-plot-observation' / f'{_PROOF_SHA256}.json'

def verify_source_evidence() -> Any:
    return load_pinned_json(_PROOF_PATH, _PROOF_SHA256)

def _player_id(value: int) -> int:
    if type(value) is not int or not 0 <= value <= _MAX_PLAYER_ID:
        raise ValueError('player_id must be an integer in [0, 63]')
    return value

def build_revealed_plot_observation_source(player_id: int) -> bytes:
    """Build bounded Lua that reads detail only after the local reveal gate."""
    verify_source_evidence()
    player_id = _player_id(player_id)
    lua = 'local pid=__PLAYER_ID__\nassert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n       \'plot observer perspective differs from requested player\')\nassert(type(Game.GetLocalObserver)==\'function\' and Game.GetLocalObserver()==pid,\n       \'plot observer is not the requested player\')\nlocal player=Players and Players[pid]\nlocal visibility=PlayersVisibility and PlayersVisibility[pid]\nassert(player~=nil and visibility~=nil and type(visibility.IsRevealed)==\'function\',\n       \'player reveal API unavailable\')\nlocal resources=player:GetResources()\nassert(resources~=nil and type(resources.IsResourceVisible)==\'function\',\n       \'player resource-visibility API unavailable\')\nassert(GameInfo~=nil and GameInfo.Resources~=nil,\'resource metadata unavailable\')\nassert(Map~=nil and type(Map.GetGridSize)==\'function\' and\n       type(Map.GetPlotCount)==\'function\' and type(Map.GetPlotByIndex)==\'function\',\n       \'map API unavailable\')\nlocal function n(v)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge and v%1==0,\n         \'plot snapshot contains invalid integer\')\n  return string.format(\'%.17g\',v)\nend\nlocal function b(v)\n  assert(type(v)==\'boolean\',\'plot flag is not Boolean\')\n  return v and \'true\' or \'false\'\nend\nlocal w,h=Map.GetGridSize()\nlocal count=Map.GetPlotCount()\nassert(type(w)==\'number\' and type(h)==\'number\' and type(count)==\'number\' and\n       w>0 and h>0 and w*h==count and count<=16384,\n       \'map outside revealed-plot diagnostic bounds\')\nlocal rows={}\nfor index=0,count-1 do\n  -- Handle and geometry lookup precede the reveal decision; no other plot\n  -- getter is called unless the player\'s IsRevealed(index) admits this plot.\n  local plot=Map.GetPlotByIndex(index)\n  assert(plot~=nil,\'missing plot handle\')\n  local x,y=plot:GetX(),plot:GetY()\n  if visibility:IsRevealed(index) then\n    local owner=plot:GetOwner()\n    assert(owner>=-1 and owner<=63 and x>=0 and x<w and y>=0 and y<h,\n           \'revealed plot identity outside bounds\')\n    local terrain=plot:GetTerrainType()\n    local feature=plot:GetFeatureType()\n    local water=plot:IsWater()\n    local impassable=plot:IsImpassable()\n    local fields={\'"index":\'..n(index),\'"x":\'..n(x),\'"y":\'..n(y),\n      \'"revealed":true\',\'"owner":\'..n(owner),\'"terrain_type":\'..n(terrain),\n      \'"feature_type":\'..n(feature),\'"water":\'..b(water),\n      \'"impassable":\'..b(impassable)}\n    assert(type(plot.GetResourceType)==\'function\' and\n           type(plot.GetResourceCount)==\'function\',\'plot resource getters unavailable\')\n    local resourceType=plot:GetResourceType()\n    assert(type(resourceType)==\'number\' and resourceType%1==0 and resourceType>=-1,\n           \'invalid plot resource type\')\n    if resourceType>=0 then\n      local resource=GameInfo.Resources[resourceType]\n      assert(resource~=nil and type(resource.Hash)==\'number\',\n             \'resource metadata row unavailable\')\n      if resources:IsResourceVisible(resource.Hash) then\n        local resourceCount=plot:GetResourceCount()\n        assert(type(resourceCount)==\'number\' and resourceCount%1==0 and resourceCount>=0,\n               \'invalid visible resource count\')\n        fields[#fields+1]=\'"resource_type":\'..n(resourceType)\n        fields[#fields+1]=\'"resource_count":\'..n(resourceCount)\n      end\n    end\n    rows[#rows+1]=\'{\'..table.concat(fields,\',\')..\'}\'\n  end\nend\nlocal out=\'{"schema":"civ6rl-revealed-plot-observation-v1","player_id":\'..n(pid)..\n  \',"observer_id":\'..n(Game.GetLocalObserver())..\',"turn":\'..n(Game.GetCurrentGameTurn())..\n  \',"width":\'..n(w)..\',"height":\'..n(h)..\',"plots":[\'..table.concat(rows,\',\')..\']}\'\nassert(#out<=2097152,\'revealed plot snapshot exceeds diagnostic result bound\')\nreturn out\n'.replace('__PLAYER_ID__', str(player_id))
    return lua.encode('ascii')

def build_revealed_plot_guard_case(player_id: int=0) -> bytes:
    """HKS sentinel case: revealed-but-not-visible is admitted; hidden reads fail."""
    verify_source_evidence()
    collector = build_revealed_plot_observation_source(player_id).decode('ascii')
    prefix = 'local pid=__PLAYER_ID__\nlocal forbidden=0\nlocal function blocked() forbidden=forbidden+1; error(\'forbidden plot read\') end\nlocal function mkplot(i,revealed,resourceType,resourceVisible)\n  local p={i=i,revealed=revealed,resourceType=resourceType,resourceVisible=resourceVisible}\n  function p:GetX() return self.i end\n  function p:GetY() return 0 end\n  local function detail(name,value)\n    p[name]=function(self) if not self.revealed then return blocked() end; return value end\n  end\n  detail(\'GetOwner\',0); detail(\'GetTerrainType\',11+i); detail(\'GetFeatureType\',-1)\n  detail(\'IsWater\',false); detail(\'IsImpassable\',false)\n  function p:GetResourceType() if not self.revealed then return blocked() end; return self.resourceType end\n  function p:GetResourceCount()\n    if not self.revealed or not self.resourceVisible then return blocked() end\n    return 3\n  end\n  return p\nend\nlocal p0,p1,p2=mkplot(0,false,2,false),mkplot(1,true,3,false),mkplot(2,true,2,true)\nlocal saved={Players=Players,PlayersVisibility=PlayersVisibility,Map=Map,\n  Game=Game,GameInfo=GameInfo}\nlocal resourceCalls={}\nPlayers={[pid]={GetResources=function() return {IsResourceVisible=function(_,hash)\n  resourceCalls[#resourceCalls+1]=hash; return hash==2201 end} end}}\nPlayersVisibility={[pid]={IsRevealed=function(_,index) return index~=0 end}}\nMap={GetGridSize=function() return 3,1 end,GetPlotCount=function() return 3 end,\n  GetPlotByIndex=function(i) return ({p0,p1,p2})[i+1] end}\nGameInfo={Resources={[2]={Hash=2201},[3]={Hash=3301}}}\nGame={GetLocalPlayer=function() return pid end,GetLocalObserver=function() return pid end,\n  GetCurrentGameTurn=function() return 4 end}\nlocal ok,result=pcall(function()\n__COLLECTOR__\nend)\nlocal wrongLocal=Game.GetLocalPlayer\nGame.GetLocalPlayer=function() return (pid+1)%64 end\nlocal localOK=pcall(function() __COLLECTOR__ end)\nGame.GetLocalPlayer=wrongLocal\nlocal wrongObserver=Game.GetLocalObserver\nGame.GetLocalObserver=function() return (pid+1)%64 end\nlocal observerOK=pcall(function() __COLLECTOR__ end)\nGame.GetLocalObserver=wrongObserver\nGame.GetLocalObserver=nil\nlocal missingObserverOK=pcall(function() __COLLECTOR__ end)\nGame.GetLocalObserver=wrongObserver\nPlayers,PlayersVisibility,Map,Game,GameInfo=saved.Players,saved.PlayersVisibility,\n  saved.Map,saved.Game,saved.GameInfo\nassert(ok,tostring(result))\nassert(not localOK,\'foreign local player accepted\')\nassert(not observerOK,\'foreign local observer accepted\')\nassert(not missingObserverOK,\'missing local observer API accepted\')\nassert(forbidden==0,\'unrevealed plot detail or hidden resource count was read\')\nassert(result:find(\'"index":1\',1,true) and result:find(\'"index":2\',1,true),\n       \'revealed plots missing\')\nassert(not result:find(\'"index":0\',1,true),\'unrevealed plot leaked\')\nlocal row1=result:match(\'({[^{}]*"index":1[^{}]*})\')\nassert(row1~=nil and not row1:find(\'resource_type\',1,true) and\n       not row1:find(\'resource_count\',1,true),\'tech-hidden resource leaked\')\nassert(result:find(\'"resource_count":3\',1,true),\'visible resource missing\')\nassert(#resourceCalls==2 and resourceCalls[1]==3301 and resourceCalls[2]==2201,\n       \'resource disclosure predicate was not checked for each revealed resource\')\nassert(not result:find(\'visible_enemy_units\',1,true),\'collector added unit data\')\nreturn result\n'.replace('__PLAYER_ID__', str(player_id)).replace('__COLLECTOR__', collector)
    return prefix.encode('ascii')

def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result

def parse_revealed_plot_observation(payload: bytes | str, player_id: int) -> dict[str, Any]:
    verify_source_evidence()
    player_id = _player_id(player_id)
    if type(payload) is bytes:
        if not payload or len(payload) > _RESULT_CAPACITY:
            raise ValueError('payload outside byte bound')
        text = payload.decode('utf-8', 'strict')
    elif type(payload) is str:
        if not payload or len(payload.encode('utf-8')) > _RESULT_CAPACITY:
            raise ValueError('payload outside byte bound')
        text = payload
    else:
        raise TypeError('payload must be bytes or str')
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('invalid revealed-plot JSON') from exc
    keys = {'schema', 'player_id', 'observer_id', 'turn', 'width', 'height', 'plots'}
    if type(data) is not dict or set(data) != keys:
        raise ValueError('unexpected observation fields')
    if data['schema'] != 'civ6rl-revealed-plot-observation-v1':
        raise ValueError('unexpected observation schema')
    for key in ('player_id', 'observer_id', 'turn', 'width', 'height'):
        if type(data[key]) is not int:
            raise ValueError(f'{key} must be an integer')
    if data['player_id'] != player_id or data['observer_id'] != player_id or data['turn'] < 0 or (data['width'] <= 0) or (data['height'] <= 0) or (data['width'] * data['height'] > _MAX_PLOTS):
        raise ValueError('observation perspective or dimensions invalid')
    if type(data['plots']) is not list or len(data['plots']) > _MAX_PLOTS:
        raise ValueError('plot list outside bound')
    basic = {'index', 'x', 'y', 'revealed', 'owner', 'terrain_type', 'feature_type', 'water', 'impassable'}
    resource = {'resource_type', 'resource_count'}
    seen: set[int] = set()
    for row in data['plots']:
        if type(row) is not dict or set(row) not in (basic, basic | resource):
            raise ValueError('plot row fields invalid')
        if row['revealed'] is not True:
            raise ValueError('unrevealed plot data rejected')
        for key in ('index', 'x', 'y', 'owner', 'terrain_type', 'feature_type'):
            if type(row[key]) is not int:
                raise ValueError(f'plot {key} must be an integer')
        if not 0 <= row['index'] < data['width'] * data['height'] or not 0 <= row['x'] < data['width'] or (not 0 <= row['y'] < data['height']) or (row['owner'] < -1) or (row['owner'] > _MAX_PLAYER_ID) or (row['index'] in seen):
            raise ValueError('plot identity outside bounds or duplicated')
        seen.add(row['index'])
        if type(row['water']) is not bool or type(row['impassable']) is not bool:
            raise ValueError('plot flags must be Boolean')
        if resource <= row.keys():
            if type(row['resource_type']) is not int or row['resource_type'] < 0:
                raise ValueError('resource type invalid')
            if type(row['resource_count']) is not int or row['resource_count'] < 0:
                raise ValueError('resource count invalid')
    return data

def observe_revealed_plots(runtime: Any, child: Any, player_id: int, *, capacity: int=_RESULT_CAPACITY) -> dict[str, Any]:
    player_id = _player_id(player_id)
    verify_source_evidence()
    if type(capacity) is not int or not 0 < capacity <= _RESULT_CAPACITY:
        raise ValueError('capacity outside admitted bound')
    source = build_revealed_plot_observation_source(player_id)
    payload = runtime.evaluate_text(child, source, b'@native_revealed_plot_observation', capacity=capacity)
    return parse_revealed_plot_observation(payload, player_id)

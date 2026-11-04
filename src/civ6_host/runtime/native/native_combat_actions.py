"""Native legality candidates for attacks on currently visible enemy units.

This is an action-selection boundary, not a combat simulator. It uses the
official UnitManager legality predicate and request route; it never predicts
damage, target effects, or whether MOVE_TO with ATTACK resolves as combat.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _UNIT_ATTACK_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
from pathlib import Path
from typing import Any
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_combat_actions.py')))).resolve().parents[1]
_PROOF_SHA256 = '9f0a1734d2cfb80fdc9b1c399270859c7de0e7b3ec5a8cabffbef02dd8c09d1f'
_PROOF_PATH = _ROOT / 'evidence/native-combat-action-api' / f'{_PROOF_SHA256}.json'
_MAX_PLAYER = 63
_MAX_UNITS = 4096
_MAX_PLOTS = 16384
_MAX_PAIR_WORK = 100000
_RESULT_CAPACITY = 2 * 1024 * 1024
_OPERATIONS = {'RANGE_ATTACK', 'MOVE_TO'}

def verify_source_evidence(*, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256) -> Any:
    if core_sha256 != _UNIT_ATTACK_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_unit_attack_profile import verify_source as selected_source
        return selected_source(core_sha256)
    proof = load_pinned_json(_PROOF_PATH, _PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_combat_action_api.static.v1' or proof.get('source_evidence', {}).get('native_unit_operation_api', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        raise RuntimeError('Pinned combat action API evidence identity changed')
    registrations = proof['source_evidence']['native_unit_operation_api']['registrations']
    expected = {'CanStartOperation': '0x180547840', 'RequestOperation': '0x18054a600', 'GetOperationTargets': '0x1805492f0'}
    if {key: registrations.get(key, {}).get('callback_va') for key in expected} != expected:
        raise RuntimeError('Pinned UnitManager callback registration changed')
    return proof

def _player_id(value: int) -> int:
    if type(value) is not int or not 0 <= value <= _MAX_PLAYER:
        raise ValueError('player_id must be an integer in [0, 63]')
    return value

def _uint(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be an unsigned 32-bit integer')
    return value

def candidate_source(player_id: int, expected_turn: int, *, ranged_modifier: bool=True, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256) -> bytes:
    """Return JSON Lua code listing source-legality-approved visible UNIT targets."""
    from civ6_host.runtime.xp1_unit_attack_profile import selected_readiness_source
    verify_source_evidence(core_sha256=core_sha256)
    if type(ranged_modifier) is not bool:
        raise ValueError('Exact ranged input variant required')
    pid = _player_id(player_id)
    turn = _uint(expected_turn, 'expected turn')
    return selected_readiness_source('local pid,expectedTurn=__PID__,__TURN__\nlocal rangedModifier=__RANGED_MODIFIER__\nassert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n       \'combat candidate perspective mismatch\')\nassert(type(Game.GetCurrentGameTurn)==\'function\' and Game.GetCurrentGameTurn()==expectedTurn,\n       \'combat candidate is stale\')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,\'combat player is not ready\')\nassert(UnitManager and type(UnitManager.CanStartOperation)==\'function\' and\n       type(UnitManager.GetOperationTargets)==\'function\',\n       \'native unit combat legality API unavailable\')\nassert(Map and type(Map.GetGridSize)==\'function\' and type(Map.GetPlotCount)==\'function\' and\n       type(Map.GetPlotByIndex)==\'function\' and type(Map.GetAdjacentPlot)==\'function\',\n       \'native combat map API unavailable\')\nassert(Units and type(Units.GetUnitsInPlotLayerID)==\'function\' and MapLayers and\n       MapLayers.ANY~=nil and PlayersVisibility and PlayersVisibility[pid],\n       \'visible enemy enumeration API unavailable\')\nlocal visibility=PlayersVisibility[pid]\nassert(type(visibility.IsVisible)==\'function\' and type(visibility.IsRevealed)==\'function\' and\n       type(visibility.IsUnitVisible)==\'function\',\'combat visibility API unavailable\')\nassert(UnitOperationTypes and UnitOperationTypes.RANGE_ATTACK~=nil and\n       UnitOperationTypes.MOVE_TO~=nil and UnitOperationTypes.PARAM_X~=nil and\n       UnitOperationTypes.PARAM_Y~=nil and UnitOperationTypes.PARAM_MODIFIERS~=nil and\n       UnitOperationMoveModifiers and UnitOperationMoveModifiers.ATTACK~=nil and\n       UnitOperationResults and UnitOperationResults.PLOTS~=nil and\n       UnitOperationResults.MODIFIERS~=nil and DirectionTypes and\n       UnitOperationResults.MODIFIER_IS_TARGET~=nil,\n       \'combat operation enums unavailable\')\nlocal width,height=Map.GetGridSize()\nlocal plotCount=Map.GetPlotCount()\nassert(type(width)==\'number\' and width>0 and width%1==0 and\n       type(height)==\'number\' and height>0 and height%1==0 and\n       type(plotCount)==\'number\' and plotCount==width*height and\n       plotCount<=16384,\'map outside combat bounds\')\nlocal function u32(v,label)\n assert(type(v)==\'number\' and v%1==0 and v>=0 and v<=4294967295,\n        \'invalid \'..label)\n return v\nend\nlocal function visiblePlot(index)\n if type(index)~=\'number\' or index%1~=0 or index<0 or index>=plotCount then return nil end\n local plot=Map.GetPlotByIndex(index)\n if plot==nil then return nil end\n local x,y=plot:GetX(),plot:GetY()\n if type(x)~=\'number\' or x%1~=0 or x<0 or x>=width or\n    type(y)~=\'number\' or y%1~=0 or y<0 or y>=height then return nil end\n if not visibility:IsVisible(x,y) or not visibility:IsRevealed(index) then return nil end\n return plot,x,y\nend\nlocal enemyCache={}\nlocal function visibleEnemies(index,x,y)\n if enemyCache[index]~=nil then return enemyCache[index] end\n -- This API is never called for unrevealed or currently invisible plots.\n local found=Units.GetUnitsInPlotLayerID(x,y,MapLayers.ANY)\n local enemies={}\n if found~=nil then\n  assert(type(found)==\'table\',\'plot unit list is not a table\')\n  local targetCount=0\n  for _,unit in pairs(found) do\n   targetCount=targetCount+1\n   assert(targetCount<=4096,\'units per visible plot exceed combat bound\')\n   -- Do not read owner, ID, or other enemy fields before the native unit gate.\n   if visibility:IsUnitVisible(unit) then\n    local owner=unit:GetOwner()\n    if type(owner)==\'number\' and owner%1==0 and owner>=0 and owner<=63 and owner~=pid then\n     enemies[#enemies+1]={owner=owner,id=u32(unit:GetID(),\'visible enemy ID\')}\n    end\n   end\n  end\n end\n enemyCache[index]=enemies\n return enemies\nend\nlocal directions={DirectionTypes.DIRECTION_NORTHEAST,DirectionTypes.DIRECTION_EAST,\n DirectionTypes.DIRECTION_SOUTHEAST,DirectionTypes.DIRECTION_SOUTHWEST,\n DirectionTypes.DIRECTION_WEST,DirectionTypes.DIRECTION_NORTHWEST}\nfor _,direction in ipairs(directions) do\n assert(type(direction)==\'number\' and direction%1==0,\'invalid direction enum\')\nend\nlocal candidates,seen,rangeLegal={},{},{}\nlocal work,targetWork,unitCount=0,0,0\nlocal attackModifier=UnitOperationMoveModifiers.ATTACK\nlocal function checkTarget(unit,unitID,owner,targetID,x,y,operation)\n work=work+1\n assert(work<=100000,\'combat candidate pair-work limit exceeded\')\n local pairKey=unitID..\':\'..owner..\':\'..targetID\n if operation==\'MOVE_TO\' and rangeLegal[pairKey] then return end\n local operationType=operation==\'RANGE_ATTACK\' and UnitOperationTypes.RANGE_ATTACK or\n                     UnitOperationTypes.MOVE_TO\n local parameters={[UnitOperationTypes.PARAM_X]=x,[UnitOperationTypes.PARAM_Y]=y}\n -- The enemy-flag click passes ATTACK to both operations; dedicated ranged\n -- targeting passes only X/Y. Preserve both actual UI routes explicitly.\n if operation==\'MOVE_TO\' or rangedModifier then parameters[UnitOperationTypes.PARAM_MODIFIERS]=attackModifier end\n if UnitManager.CanStartOperation(unit,operationType,nil,parameters)==true then\n  local key=unitID..\':\'..operation..\':\'..owner..\':\'..targetID\n  if not seen[key] then\n   seen[key]=true\n   candidates[#candidates+1]={unit_id=unitID,operation=operation,\n     target_owner=owner,target_id=targetID,x=x,y=y}\n  end\n  if operation==\'RANGE_ATTACK\' then rangeLegal[pairKey]=true end\n end\nend\nfor _,unit in player:GetUnits():Members() do\n unitCount=unitCount+1\n assert(unitCount<=4096,\'own unit enumeration exceeds combat bound\')\n assert(unit:GetOwner()==pid,\'foreign unit in local player unit collection\')\n local unitID=u32(unit:GetID(),\'own unit ID\')\n if unit:IsReadyToSelect()==true then\n  -- The native target query marks actual RANGE_ATTACK targets. Plot indices\n  -- are not expanded into plot/unit data until the visibility gates pass.\n  local targetResult=UnitManager.GetOperationTargets(unit,UnitOperationTypes.RANGE_ATTACK)\n  if targetResult~=nil then\n   assert(type(targetResult)==\'table\',\'ranged target query result is not a table\')\n   local plots=targetResult[UnitOperationResults.PLOTS]\n   local modifiers=targetResult[UnitOperationResults.MODIFIERS]\n   if plots~=nil or modifiers~=nil then\n    assert(type(plots)==\'table\' and type(modifiers)==\'table\',\n           \'ranged target query is incomplete\')\n    for i,modifier in ipairs(modifiers) do\n     targetWork=targetWork+1\n     assert(targetWork<=100000,\'combat target-query limit exceeded\')\n     if modifier==UnitOperationResults.MODIFIER_IS_TARGET then\n      local index=plots[i]\n      local plot,x,y=visiblePlot(index)\n      if plot~=nil then\n       for _,enemy in ipairs(visibleEnemies(index,x,y)) do\n        checkTarget(unit,unitID,enemy.owner,enemy.id,x,y,\'RANGE_ATTACK\')\n       end\n      end\n     end\n    end\n   end\n  end\n  -- Adjacent enemy tiles are the only MOVE_TO+ATTACK candidates exposed as\n  -- a melee-capable UI fallback. The operation is still labeled MOVE_TO.\n  local x0,y0=unit:GetX(),unit:GetY()\n  assert(type(x0)==\'number\' and x0%1==0 and x0>=0 and x0<width and\n         type(y0)==\'number\' and y0%1==0 and y0>=0 and y0<height,\n         \'own unit coordinates outside map\')\n  for _,direction in ipairs(directions) do\n   targetWork=targetWork+1\n   assert(targetWork<=100000,\'combat target-query limit exceeded\')\n   local adjacent=Map.GetAdjacentPlot(x0,y0,direction)\n   if adjacent~=nil then\n    local index=adjacent:GetIndex()\n    local _,x,y=visiblePlot(index)\n    if x~=nil then\n     for _,enemy in ipairs(visibleEnemies(index,x,y)) do\n      checkTarget(unit,unitID,enemy.owner,enemy.id,x,y,\'MOVE_TO\')\n     end\n    end\n   end\n  end\n end\nend\ntable.sort(candidates,function(a,b)\n if a.unit_id~=b.unit_id then return a.unit_id<b.unit_id end\n if a.operation~=b.operation then return a.operation<b.operation end\n if a.target_owner~=b.target_owner then return a.target_owner<b.target_owner end\n return a.target_id<b.target_id\nend)\nlocal function num(n) return string.format(\'%.0f\',n) end\nlocal rows={}\nfor _,c in ipairs(candidates) do\n rows[#rows+1]=\'{"unit_id":\'..num(c.unit_id)..\',"operation":"\'..c.operation..\n  \'","target_owner":\'..num(c.target_owner)..\',"target_id":\'..num(c.target_id)..\n  \',"x":\'..num(c.x)..\',"y":\'..num(c.y)..\'}\'\nend\nlocal out=\'{"schema":"civ6rl-combat-candidates-v1","player_id":\'..num(pid)..\n \',"turn":\'..num(expectedTurn)..\',"width":\'..num(width)..\',"height":\'..num(height)..\n \',"candidates":[\'..table.concat(rows,\',\')..\']}\'\nassert(#out<=2097152,\'combat candidate response exceeds bound\')\nreturn out\n'.replace('__PID__', str(pid)).replace('__TURN__', str(turn)).replace('__RANGED_MODIFIER__', 'true' if ranged_modifier else 'false').encode('ascii'), core_sha256, 'unit_candidates')

def _candidate(value: dict[str, Any], player_id: int, width: int, height: int) -> dict[str, Any]:
    keys = {'unit_id', 'operation', 'target_owner', 'target_id', 'x', 'y'}
    if type(value) is not dict or set(value) != keys:
        raise ValueError('candidate fields are invalid')
    if type(value['operation']) is not str or value['operation'] not in _OPERATIONS:
        raise ValueError('unsupported combat operation')
    for key in ('unit_id', 'target_owner', 'target_id', 'x', 'y'):
        _uint(value[key], key)
    if value['target_owner'] == player_id or value['target_owner'] > _MAX_PLAYER:
        raise ValueError('candidate target is not foreign to the requested player')
    if value['x'] >= width or value['y'] >= height:
        raise ValueError('candidate coordinates outside map')
    return value

def parse_candidates(payload: bytes | str, player_id: int, expected_turn: int, *, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256) -> dict[str, Any]:
    verify_source_evidence(core_sha256=core_sha256)
    pid = _player_id(player_id)
    turn = _uint(expected_turn, 'expected turn')
    if type(payload) is bytes:
        if not payload or len(payload) > _RESULT_CAPACITY:
            raise ValueError('candidate response outside byte bound')
        text = payload.decode('utf-8', 'strict')
    elif type(payload) is str:
        if not payload or len(payload.encode('utf-8')) > _RESULT_CAPACITY:
            raise ValueError('candidate response outside byte bound')
        text = payload
    else:
        raise TypeError('candidate payload must be bytes or str')
    try:
        data = json.loads(text, object_pairs_hook=_pairs_no_duplicates, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('invalid candidate JSON') from exc
    if type(data) is not dict or set(data) != {'schema', 'player_id', 'turn', 'width', 'height', 'candidates'}:
        raise ValueError('candidate response fields mismatch')
    if data['schema'] != 'civ6rl-combat-candidates-v1' or type(data['player_id']) is not int or type(data['turn']) is not int or (data['player_id'] != pid) or (data['turn'] != turn):
        raise ValueError('candidate schema, player, or turn mismatch')
    width, height = (data['width'], data['height'])
    if type(width) is not int or type(height) is not int or width <= 0 or (height <= 0) or (width * height > _MAX_PLOTS):
        raise ValueError('candidate map dimensions invalid')
    if type(data['candidates']) is not list or len(data['candidates']) > _MAX_PAIR_WORK:
        raise ValueError('candidate list outside bound')
    parsed = []
    seen = set()
    for raw in data['candidates']:
        item = _candidate(raw, pid, width, height)
        key = tuple((item[k] for k in ('unit_id', 'operation', 'target_owner', 'target_id', 'x', 'y')))
        if key in seen:
            raise ValueError('duplicate combat candidate')
        seen.add(key)
        parsed.append(item)
    data['candidates'] = parsed
    return data

def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result

def request_source(player_id: int, expected_turn: int, candidate: dict[str, Any], *, width: int, height: int, ranged_modifier: bool=True, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256) -> bytes:
    """Build official UI operation submission with immediate ownership/visibility/legality rechecks."""
    from civ6_host.runtime.xp1_unit_attack_profile import selected_readiness_source
    verify_source_evidence(core_sha256=core_sha256)
    if type(ranged_modifier) is not bool:
        raise ValueError('Exact ranged input variant required')
    pid = _player_id(player_id)
    turn = _uint(expected_turn, 'expected turn')
    if type(width) is not int or type(height) is not int or width <= 0 or (height <= 0) or (width * height > _MAX_PLOTS):
        raise ValueError('map dimensions outside bound')
    item = _candidate(candidate, pid, width, height)
    unit_id = item['unit_id']
    target_owner = item['target_owner']
    target_id = item['target_id']
    operation = item['operation']
    x = item['x']
    y = item['y']
    op_name = 'RANGE_ATTACK' if operation == 'RANGE_ATTACK' else 'MOVE_TO'
    lua = "local pid,expectedTurn,unitID,targetOwner,targetID,x,y,width,height=__PID__,__TURN__,__UID__,__OWNER__,__TID__,__X__,__Y__,__WIDTH__,__HEIGHT__\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetCurrentGameTurn()==expectedTurn,\n       'combat request perspective or turn changed')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,'combat player is no longer ready')\nlocal vm=PlayersVisibility and PlayersVisibility[pid]\nassert(vm and type(vm.IsVisible)=='function' and type(vm.IsRevealed)=='function' and\n       type(vm.IsUnitVisible)=='function','combat visibility API unavailable')\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function' and\n       type(UnitManager.RequestOperation)=='function' and\n       Units and type(Units.GetUnitsInPlotLayerID)=='function' and\n       MapLayers and MapLayers.ANY~=nil and Map and\n       type(Map.GetPlotIndex)=='function' and type(Map.GetPlotByIndex)=='function' and\n       type(Map.GetGridSize)=='function' and type(Map.GetPlotCount)=='function' and\n       type(Map.GetAdjacentPlot)=='function' and DirectionTypes,\n       'combat request API unavailable')\nlocal unit=nil\nlocal count=0\nfor _,u in player:GetUnits():Members() do\n count=count+1; assert(count<=4096,'own unit scan bound exceeded')\n assert(u:GetOwner()==pid,'foreign unit in own collection')\n if u:GetID()==unitID then assert(unit==nil,'duplicate own unit ID'); unit=u end\nend\nassert(unit~=nil and unit:IsReadyToSelect()==true,'own combat unit is no longer ready')\nassert(type(width)=='number' and type(height)=='number' and\n       x>=0 and x<width and y>=0 and y<height,'target outside map')\nlocal actualWidth,actualHeight=Map.GetGridSize()\nassert(actualWidth==width and actualHeight==height and\n       Map.GetPlotCount()==width*height,'combat map changed since candidate selection')\nlocal index=Map.GetPlotIndex(x,y)\nassert(type(index)=='number' and index%1==0 and index>=0 and index<width*height,\n       'target plot is invalid')\nlocal plot=Map.GetPlotByIndex(index)\nassert(plot~=nil and plot:GetX()==x and plot:GetY()==y,'target plot coordinates changed')\nassert(vm:IsVisible(x,y) and vm:IsRevealed(index),'enemy target tile is no longer visible')\nlocal found=Units.GetUnitsInPlotLayerID(x,y,MapLayers.ANY)\nassert(type(found)=='table','target units unavailable')\nlocal target=nil\nlocal targetCount=0\nfor _,u in pairs(found) do\n targetCount=targetCount+1; assert(targetCount<=4096,'target unit scan bound exceeded')\n if vm:IsUnitVisible(u) then\n  local owner=u:GetOwner()\n  if owner==targetOwner and owner~=pid and u:GetID()==targetID then\n   assert(target==nil,'duplicate visible target identity'); target=u\n  end\n end\nend\nassert(target~=nil,'visible enemy target changed')\nif '__OP__'=='MOVE_TO' then\n local directions={DirectionTypes.DIRECTION_NORTHEAST,DirectionTypes.DIRECTION_EAST,\n  DirectionTypes.DIRECTION_SOUTHEAST,DirectionTypes.DIRECTION_SOUTHWEST,\n  DirectionTypes.DIRECTION_WEST,DirectionTypes.DIRECTION_NORTHWEST}\n local adjacent=false\n for _,direction in ipairs(directions) do\n  local nextPlot=Map.GetAdjacentPlot(unit:GetX(),unit:GetY(),direction)\n  if nextPlot~=nil and nextPlot:GetIndex()==index then adjacent=true; break end\n end\n assert(adjacent,'MOVE_TO combat fallback target is no longer adjacent')\nend\nlocal operation=UnitOperationTypes.__OP__\nlocal parameters={[UnitOperationTypes.PARAM_X]=x,[UnitOperationTypes.PARAM_Y]=y}\nif '__OP__'=='MOVE_TO' or __RANGED_MODIFIER__ then parameters[UnitOperationTypes.PARAM_MODIFIERS]=UnitOperationMoveModifiers.ATTACK end\nassert(UnitManager.CanStartOperation(unit,operation,nil,parameters)==true,\n       'native combat legality check rejected request')\nUnitManager.RequestOperation(unit,operation,parameters)\nreturn 'submitted'\n".replace('__PID__', str(pid)).replace('__TURN__', str(turn)).replace('__UID__', str(unit_id)).replace('__OWNER__', str(target_owner)).replace('__TID__', str(target_id)).replace('__X__', str(x)).replace('__Y__', str(y)).replace('__WIDTH__', str(width)).replace('__HEIGHT__', str(height)).replace('__OP__', op_name).replace('__RANGED_MODIFIER__', 'true' if ranged_modifier else 'false')
    return selected_readiness_source(lua.encode('ascii'), core_sha256, 'unit_request')

def build_guard_case(*, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256) -> bytes:
    """HKS-double contract for hidden target filtering and legal request rechecks."""
    verify_source_evidence(core_sha256=core_sha256)
    collector = candidate_source(0, 7, core_sha256=core_sha256).decode('ascii')
    request = request_source(0, 7, {'unit_id': 17, 'operation': 'RANGE_ATTACK', 'target_owner': 1, 'target_id': 9, 'x': 1, 'y': 0}, width=3, height=2, core_sha256=core_sha256).decode('ascii')
    prefix = "local saved={Game=Game,Players=Players,PlayersVisibility=PlayersVisibility,Map=Map,\n Units=Units,MapLayers=MapLayers,UnitManager=UnitManager,UnitOperationTypes=UnitOperationTypes,\n UnitOperationMoveModifiers=UnitOperationMoveModifiers,UnitOperationResults=UnitOperationResults,\n DirectionTypes=DirectionTypes}\nlocal forbidden=0\nlocal function blocked() forbidden=forbidden+1; error('hidden target getter was touched') end\nlocal actor={GetOwner=function() return 0 end,GetID=function() return 17 end,\n GetX=function() return 0 end,GetY=function() return 0 end,IsReadyToSelect=function() return true end}\nlocal enemy={GetOwner=function() return 1 end,GetID=function() return 9 end}\nlocal hidden={GetOwner=function() return blocked() end,GetID=function() return blocked() end}\nlocal function members()\n local used=false\n return function() if not used then used=true; return 1,actor end end\nend\nlocal player={IsAlive=function() return true end,IsTurnActive=function() return true end,\n IsTurnActiveComplete=function() return true end,\n GetUnits=function() return {Members=members} end}\nGame={GetLocalPlayer=function() return 0 end,GetCurrentGameTurn=function() return 7 end}\nPlayers={[0]=player}\nPlayersVisibility={[0]={IsVisible=function(_,x,y) return x==1 and y==0 end,\n IsRevealed=function(_,i) return i==1 end,\n IsUnitVisible=function(_,u) return u~=hidden end}}\nlocal p0={GetX=function() return 0 end,GetY=function() return 0 end}\nlocal p1={GetX=function() return 1 end,GetY=function() return 0 end,GetIndex=function() return 1 end}\nlocal p2={GetX=function() return 2 end,GetY=function() return 0 end,GetIndex=function() return 2 end}\nMap={GetGridSize=function() return 3,2 end,GetPlotCount=function() return 6 end,\n GetPlotByIndex=function(i) return ({p0,p1,p2,p0,p1,p2})[i+1] end,\n GetAdjacentPlot=function(x,y,d) if x==0 and y==0 and d==DirectionTypes.DIRECTION_EAST then return p1 end end,\n GetPlotIndex=function(x,y) return y*3+x end}\nUnits={GetUnitsInPlotLayerID=function(x,y,l)\n if x==2 then error('hidden plot units enumerated') end\n if x==1 and y==0 then return {enemy,hidden} end\n return {}\nend}\nMapLayers={ANY=0}\nUnitOperationTypes={RANGE_ATTACK='RANGE_ATTACK',MOVE_TO='MOVE_TO',PARAM_X='x',PARAM_Y='y',PARAM_MODIFIERS='m'}\nUnitOperationMoveModifiers={ATTACK=1}\nUnitOperationResults={PLOTS='plots',MODIFIERS='mods',MODIFIER_IS_TARGET='target'}\nDirectionTypes={DIRECTION_NORTHEAST=0,DIRECTION_EAST=1,DIRECTION_SOUTHEAST=2,\n DIRECTION_SOUTHWEST=3,DIRECTION_WEST=4,DIRECTION_NORTHWEST=5}\nlocal submitted=0\nUnitManager={GetOperationTargets=function() return {plots={1,2},mods={'target','target'}} end,\n CanStartOperation=function(u,op,nilArg,params) return u==actor and params.x==1 and params.y==0 end,\n RequestOperation=function(u,op,params) assert(u==actor and op=='RANGE_ATTACK' and params.x==1); submitted=submitted+1 end}\nlocal ok,result=pcall(function()\n__COLLECTOR__\nend)\nlocal requestOK,requestResult=pcall(function()\n__REQUEST__\nend)\nGame,Players,PlayersVisibility,Map,Units,MapLayers,UnitManager,UnitOperationTypes,\n UnitOperationMoveModifiers,UnitOperationResults,DirectionTypes=saved.Game,saved.Players,\n saved.PlayersVisibility,saved.Map,saved.Units,saved.MapLayers,saved.UnitManager,\n saved.UnitOperationTypes,saved.UnitOperationMoveModifiers,saved.UnitOperationResults,saved.DirectionTypes\nassert(ok,tostring(result)); assert(requestOK,tostring(requestResult))\nassert(forbidden==0,'hidden target identity getter was touched')\nassert(submitted==1,'request path did not submit exactly once')\nreturn result..'|'..requestResult\n".replace('__COLLECTOR__', collector).replace('__REQUEST__', request)
    return prefix.encode('ascii')

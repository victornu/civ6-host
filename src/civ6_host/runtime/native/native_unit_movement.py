"""Bounded one-turn MOVE_TO actions through the shipped UI operation route.

The catalog intersects the native reachable-plot query with a native path
whose every step remains within one turn. The default profile keeps visible,
empty, non-city, no-improvement, non-foreign destinations without a war
transition. The explicit improved-tile profile additionally admits official
improvement rows whose RemoveOnEntry, Goody and BarbarianCamp flags are false.
An independent explicit profile admits visible empty owned cities, joining the
city's native owner and location rather than inferring ownership from its plot.
An explicit multi-turn profile can enumerate complete native paths across turns
while applying the same visible, empty, non-city, no-entry-effect, non-foreign
transit checks. Combat, swaps, hidden paths, entry rewards/prompts and incomplete
or reconstructed paths remain outside these profiles; native pathfinding and
legality still decide each move.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
import re
from pathlib import Path
from civ6_host.runtime.native.native_unit_actions import _identifier
from civ6_host.runtime.native.native_unit_skip import verify_source as verify_unit_operation_route
from civ6_host.runtime.native.native_reachable_movement import verify_source_evidence as verify_reachable_source
from civ6_host.runtime.native.native_move_path_contract import verify_source_evidence as verify_move_path_source
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_movement.py')))).resolve().parents[1]
_PROOF = _ROOT / 'evidence/native-unit-movement-ui-source.json'
_PROOF_SHA256 = 'f1b3d97cce5a2e3d77933464b89c5465d267d5fc5ee9ac6e1cc5666803d56f26'
_UI_ROOT = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_UI_HASHES = {'Civ6Common.lua': '6e422dfed29d6e40507b14e234fc84c7647f450200df17dc2383e952a67a371f', 'WorldInput.lua': '05be449b00f0fc7bed30d23543e31b43f619650ede2da061131f1967b6d32fa8', 'UnitFlagManager.lua': '26f056a54b9c0f8410af4d05721ab9584740f35906424974fed58e984cced0ea'}
_CHOICE_FIELDS = ('unit_id', 'source_plot_id', 'source_x', 'source_y', 'destination_plot_id', 'destination_x', 'destination_y')
_MAX_PLOT_INDEX = 16383
_PREVIEW_MAX_BYTES = 8 * 1024 * 1024
_DECIMAL = re.compile(b'(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\\Z')
_IMPROVEMENT_SOURCE_ROOT = _UI_ROOT.parent / 'Gameplay' / 'Data'
_IMPROVEMENT_SOURCE_HASHES = {'Schema/01_GameplaySchema.sql': 'd56906e7f67c09193b431843432bc21d62e86c32f3f46c14eae9dedbe69084e0', 'Improvements.xml': '23312be5bfaf582e68c00df7b6974f035bccd6cccf06d3beecafb15013378800'}

def verified_improvement_sources() -> dict[Path, str]:
    """Pin the official metadata contract, not an estimated movement rule.

The installed schema declares these three fields as non-null Booleans; the
official camp/hut rows mark entry effects. Effective values are read from the
current native GameInfo table, never reconstructed from these source defaults.
This does not establish compatibility with arbitrary DLC/mod gameplay scripts.
"""
    result = {_IMPROVEMENT_SOURCE_ROOT / name: pin for name, pin in _IMPROVEMENT_SOURCE_HASHES.items()}
    for path, pin in result.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != pin:
            raise RuntimeError('Pinned improvement entry metadata source changed: ' + path.name)
    return result

def _check_improvement_option(value: bool) -> None:
    if type(value) is not bool:
        raise ValueError('allow_improvements must be an explicit Boolean')
    if value:
        verified_improvement_sources()

def _check_city_option(value: bool) -> None:
    if type(value) is not bool:
        raise ValueError('allow_own_cities must be an explicit Boolean')

def _check_multiturn_option(value: bool) -> None:
    if type(value) is not bool:
        raise ValueError('allow_multiturn must be an explicit Boolean')

def verify_source() -> None:
    verify_unit_operation_route()
    verify_reachable_source()
    verify_move_path_source()
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA256:
        raise RuntimeError('Pinned unit-movement UI proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_unit_movement_ui_sources.static.v1':
        raise RuntimeError('Unexpected unit-movement source proof')
    for name, expected in _UI_HASHES.items():
        relative = proof.get('files', {}).get(_source_key(name), {}).get('relative_path')
        observed = proof.get('files', {}).get(_source_key(name), {}).get('sha256')
        if relative != name or observed != expected:
            raise RuntimeError('Pinned UI movement source identity changed')
        current = hashlib.sha256(_resolve_resource_path(_UI_ROOT / relative).read_bytes()).hexdigest()
        if current != expected:
            raise RuntimeError(f'Installed {name} changed')
    excerpt_text = '\n'.join((e.get('text', '') for e in proof.get('excerpts', {}).values()))
    required = ('tParameters[UnitOperationTypes.PARAM_X] = plotX;', 'tParameters[UnitOperationTypes.PARAM_Y] = plotY;', 'UnitOperationMoveModifiers.ATTACK + UnitOperationMoveModifiers.MOVE_IGNORE_UNEXPLORED_DESTINATION', 'UnitManager.RequestOperation(kUnit, UnitOperationTypes.MOVE_TO, tParameters)', 'UnitManager.GetMoveToPathEx( kUnit, endPlotId )', 'Map.GetAdjacentPlot')
    if any((token not in excerpt_text for token in required)):
        raise RuntimeError('Pinned MOVE_TO request/path source is incomplete')

def _source_key(filename: str) -> str:
    return {'Civ6Common.lua': 'civ6_common', 'WorldInput.lua': 'world_input', 'UnitFlagManager.lua': 'unit_flag_manager'}[filename]

def _player_id(value: int) -> bytes:
    return _identifier(value, 'player ID', 63)

def _u32(value: int, label: str) -> bytes:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'Invalid {label}')
    return str(value).encode('ascii')

def _coords(value: int, label: str) -> bytes:
    if type(value) is not int or not 0 <= value <= 65535:
        raise ValueError(f'Invalid {label}')
    return str(value).encode('ascii')

def _lua_context(player_id: bytes, expected_turn: bytes, *, allow_improvements: bool=False, allow_own_cities: bool=False) -> bytes:
    source = b'local pid,expectedTurn=' + player_id + b',' + expected_turn + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n       'native UI observer is another player')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n       'movement choice is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and\n       Game.IsAllowStrategicCommands(pid)==true,'strategic commands are unavailable')\nlocal p=Players and Players[pid]\nassert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,\n       'requested player is not ready')\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function' and\n       type(UnitManager.RequestOperation)=='function' and\n       type(UnitManager.GetMoveToPathEx)=='function' and\n       type(UnitManager.GetReachableMovement)=='function', 'native unit movement API unavailable')\nassert(Map and type(Map.GetPlotIndex)=='function' and\n       type(Map.GetPlotByIndex)=='function' and type(Map.GetGridSize)=='function' and\n       type(Map.GetPlotCount)=='function', 'native map movement API unavailable')\nassert(DirectionTypes and PlayersVisibility and PlayersVisibility[pid] and\n       Units and type(Units.GetUnitsInPlotLayerID)=='function' and MapLayers and\n       MapLayers.ANY~=nil and Cities and type(Cities.GetCityInPlot)=='function' and\n       CombatManager and type(CombatManager.IsAttackChangeWarState)=='function',\n       'safe movement destination filters unavailable')\nassert(UnitOperationTypes and UnitOperationTypes.MOVE_TO~=nil and\n       UnitOperationTypes.PARAM_X~=nil and UnitOperationTypes.PARAM_Y~=nil and\n       UnitOperationTypes.PARAM_MODIFIERS~=nil and UnitOperationMoveModifiers and\n       UnitOperationMoveModifiers.ATTACK~=nil and\n       UnitOperationMoveModifiers.MOVE_IGNORE_UNEXPLORED_DESTINATION~=nil,\n       'source MOVE_TO parameter enums unavailable')\nlocal visibility=PlayersVisibility[pid]\nassert(type(visibility.IsVisible)=='function' and type(visibility.IsRevealed)=='function' and\n       type(visibility.IsUnitVisible)=='function', 'player visibility API unavailable')\nlocal width,height=Map.GetGridSize()\nlocal plotCount=Map.GetPlotCount()\nassert(type(width)=='number' and type(height)=='number' and type(plotCount)=='number' and\n       width>0 and height>0 and width==math.floor(width) and height==math.floor(height) and\n       width*height==plotCount and plotCount<=16384,\n       'map outside movement bounds')\nlocal moveFlags=UnitOperationMoveModifiers.ATTACK+\n                UnitOperationMoveModifiers.MOVE_IGNORE_UNEXPLORED_DESTINATION\nassert(type(moveFlags)=='number' and moveFlags==math.floor(moveFlags),\n       'invalid source movement modifier')\nlocal function integer(n,label,max)\n assert(type(n)=='number' and n==math.floor(n) and n>=0 and n<=max,\n        'invalid '..label)\n return n\nend\nlocal function point(x,y)\n assert(type(x)=='number' and x==math.floor(x) and x>=0 and x<width and\n        type(y)=='number' and y==math.floor(y) and y>=0 and y<height,\n        'unit or target coordinates outside map')\nend\nlocal function denseArray(value,maxItems,label)\n assert(type(value)=='table','native '..label..' is not a table')\n local count=0\n for key in pairs(value) do\n   assert(type(key)=='number' and key==math.floor(key) and key>=1 and key<=maxItems,\n          'native '..label..' has an invalid array key')\n   count=count+1\n   assert(count<=maxItems,'native '..label..' exceeds its bound')\n end\n for index=1,count do assert(value[index]~=nil,'native '..label..' is sparse') end\n return count\nend\nlocal function reachableSet(unit)\n local plots=UnitManager.GetReachableMovement(unit)\n if plots==nil then return nil end\n local count=denseArray(plots,plotCount,'reachable plot list')\n local set={}\n for i=1,count do\n   local index=integer(plots[i],'reachable plot',plotCount-1)\n   assert(not set[index],'native reachable plots contain a duplicate')\n   set[index]=true\n end\n return set\nend\nlocal function visiblePlot(index)\n local plot=Map.GetPlotByIndex(index)\n if plot==nil then return nil end\n local x,y=plot:GetX(),plot:GetY()\n point(x,y)\n assert(integer(Map.GetPlotIndex(x,y),'visible plot index',plotCount-1)==index,\n        'visible plot coordinates disagree with native index')\n if not visibility:IsVisible(x,y) or not visibility:IsRevealed(index) then return nil end\n return plot,x,y\nend\nlocal function pathIsSingleTurn(unit,sourceIndex,destinationIndex)\n local info=UnitManager.GetMoveToPathEx(unit,destinationIndex)\n if info==nil then return false end\n assert(type(info)=='table','native movement path has an invalid shape')\n local plots=info.plots\n local turns=info.turns\n assert(plots~=nil and turns~=nil,'native movement path is missing a required array')\n local n=denseArray(plots,plotCount,'path plots')\n local tn=denseArray(turns,plotCount,'path turns')\n if n==0 and tn==0 then return false end\n assert(n==tn,'native movement path arrays have different sizes')\n if n<2 then return false end\n -- Native preview can expose an incomplete route. It is not an admitted move;\n -- never append the requested endpoint as the UI may do for display only.\n if plots[1]~=sourceIndex or plots[n]~=destinationIndex then return false end\n local seen={}\n local visible={}\n local pathPlots,pathTurns={},{}\n for i=1,n do\n   local index=integer(plots[i],'path plot',plotCount-1)\n   assert(not seen[index],'native movement path repeats a plot')\n   seen[index]=true\n   local turn=turns[i]\n   assert(type(turn)=='number' and turn==math.floor(turn) and turn>=0 and turn<=plotCount,\n          'native movement path has an invalid turn value')\n   if turn~=1 then return false end\n   local plot,x,y=visiblePlot(index)\n   if plot==nil then return false end\n   visible[i]={plot=plot,x=x,y=y,index=index}\n   pathPlots[i]=index\n   pathTurns[i]=turn\n end\n for i=2,n-1 do\n   local step=visible[i]\n   local plot=step.plot\n   local owner=plot:GetOwner()\n   if owner~=-1 and owner~=pid then return false end\n   if type(plot.GetImprovementType)~='function' or plot:GetImprovementType()~=-1 then return false end\n   if Cities.GetCityInPlot(step.x,step.y)~=nil then return false end\n   local found=Units.GetUnitsInPlotLayerID(step.x,step.y,MapLayers.ANY)\n   if found~=nil then\n     assert(type(found)=='table','visible path unit list is not a table')\n     local count=0\n     for _,other in pairs(found) do\n       count=count+1; assert(count<=4096,'path unit stack exceeds bound')\n       if not visibility:IsUnitVisible(other) then return false end\n       if other:GetOwner()~=pid then return false end\n     end\n   end\n end\n return pathPlots,pathTurns\nend\nlocal function targetIsSafe(unit,sourceIndex,targetIndex,reachable,expectedX,expectedY)\n if reachable==nil or not reachable[targetIndex] then return false end\n local pathPlots,pathTurns=pathIsSingleTurn(unit,sourceIndex,targetIndex)\n if not pathPlots then return false end\n local target,tx,ty=visiblePlot(targetIndex)\n if target==nil or target:GetIndex()~=targetIndex then return false end\n if expectedX~=nil and (tx~=expectedX or ty~=expectedY) then return false end\n local owner=target:GetOwner()\n if owner~=-1 and owner~=pid then return false end\n if type(target.GetImprovementType)~='function' or target:GetImprovementType()~=-1 then return false end\n if Cities.GetCityInPlot(tx,ty)~=nil then return false end\n local found=Units.GetUnitsInPlotLayerID(tx,ty,MapLayers.ANY)\n if found~=nil then\n   assert(type(found)=='table','visible plot unit list is not a table')\n   for _,other in pairs(found) do\n     if not visibility:IsUnitVisible(other) then return false end\n     return false\n   end\n end\n local war=CombatManager.IsAttackChangeWarState(unit:GetComponentID(),tx,ty)\n if war~=nil then\n   assert(type(war)=='table','war-state query returned unsupported value')\n   if #war>0 then return false end\n end\n local params={[UnitOperationTypes.PARAM_X]=tx,[UnitOperationTypes.PARAM_Y]=ty,\n               [UnitOperationTypes.PARAM_MODIFIERS]=moveFlags}\n if UnitManager.CanStartOperation(unit,UnitOperationTypes.MOVE_TO,nil,params)==true then\n   return pathPlots,pathTurns\n end\n return false\nend\nlocal function unitEligible(unit)\n local moves=unit:GetMovesRemaining()\n if type(moves)~='number' or moves~=moves or moves==math.huge or moves==-math.huge or moves<=0 then\n   return false\n end\n local row=GameInfo and GameInfo.Units and GameInfo.Units[integer(unit:GetUnitType(),'unit type',2147483647)]\n assert(row~=nil,'unit movement metadata unavailable')\n local function optionalFlag(value,label)\n   assert(value==nil or type(value)=='boolean','invalid '..label)\n   return value==true\n end\n if optionalFlag(row.IgnoreMoves,'IgnoreMoves') or optionalFlag(row.Spy,'Spy') or\n    optionalFlag(row.MakeTradeRoute,'MakeTradeRoute') then return false end\n assert(type(unit.HasMovedIntoZOC)=='function','native unit ZOC query unavailable')\n local zoc=unit:HasMovedIntoZOC()\n assert(type(zoc)=='boolean','invalid native unit ZOC result')\n return not zoc\nend\nlocal function ownUnit(pid,uid)\n local selected=nil\n local count=0\n for _,unit in p:GetUnits():Members() do\n   count=count+1\n   assert(count<=4096,'own unit enumeration exceeds bound')\n   if unit:GetID()==uid then\n     assert(selected==nil and unit:GetOwner()==pid,'duplicate or foreign unit ID')\n     selected=unit\n   end\n end\n return selected\nend\nlocal function dec(n) return string.format('%.0f',n) end\n"
    if not allow_improvements:
        return _own_city_context(source) if allow_own_cities else source
    helper = b"local function ordinaryImprovement(plot)\n assert(type(plot.GetImprovementType)=='function','visible improvement getter unavailable')\n local index=plot:GetImprovementType()\n assert(type(index)=='number' and index==math.floor(index) and index>=-1 and index<=2147483647,\n        'invalid visible improvement index')\n if index==-1 then return true end\n assert(GameInfo and GameInfo.Improvements,'native improvement metadata unavailable')\n local row=GameInfo.Improvements[index]\n assert(row~=nil and row.Index==index,'native improvement identity differs')\n assert(type(row.ImprovementType)=='string' and #row.ImprovementType<=112 and\n        string.match(row.ImprovementType,'^IMPROVEMENT_[A-Z0-9_]+$'),\n        'invalid native improvement type')\n -- The flags describe entry effects, independently of names or buildability.\n -- Do not infer absent metadata is false or special-case the name FARM.\n assert(type(row.RemoveOnEntry)=='boolean' and type(row.Goody)=='boolean' and\n        type(row.BarbarianCamp)=='boolean','native improvement entry flags unavailable')\n return not row.RemoveOnEntry and not row.Goody and not row.BarbarianCamp\nend\n"
    anchor = b'local function pathIsSingleTurn(unit,sourceIndex,destinationIndex)'
    if source.count(anchor) != 1:
        raise RuntimeError('Historical movement path helper changed')
    source = source.replace(anchor, helper + anchor)
    for variable in (b'plot', b'target'):
        old = b'if type(' + variable + b".GetImprovementType)~='function' or " + variable + b':GetImprovementType()~=-1 then return false end'
        if source.count(old) != 1:
            raise RuntimeError('Historical improvement filter changed')
        source = source.replace(old, b'if not ordinaryImprovement(' + variable + b') then return false end')
    return _own_city_context(source) if allow_own_cities else source

def _own_city_context(source: bytes) -> bytes:
    """Add only visible owned-city entry; native path/legality remain decisive."""
    helper = b"local function visibleCityIdentity(x,y,index)\n local city=Cities.GetCityInPlot(x,y)\n if city==nil then return nil end\n assert(type(city.GetOwner)=='function' and type(city.GetID)=='function' and\n        type(city.GetX)=='function' and type(city.GetY)=='function',\n        'visible city identity API unavailable')\n local owner=integer(city:GetOwner(),'visible city owner',63)\n local id=integer(city:GetID(),'visible city ID',4294967295)\n local cx,cy=city:GetX(),city:GetY()\n point(cx,cy)\n assert(cx==x and cy==y and Map.GetPlotIndex(cx,cy)==index,\n        'visible city location differs from its native plot')\n return {id=id,owner=owner,x=cx,y=cy,plot_id=index}\nend\nlocal function ownCityAt(x,y,index)\n local city=visibleCityIdentity(x,y,index)\n if city~=nil and city.owner~=pid then return false end\n return city\nend\n"
    replacements = ((b'local function pathIsSingleTurn(unit,sourceIndex,destinationIndex)', helper + b'local function pathIsSingleTurn(unit,sourceIndex,destinationIndex)'), (b'if Cities.GetCityInPlot(step.x,step.y)~=nil then return false end', b'local city=ownCityAt(step.x,step.y,step.index)\n   if city==false then return false end'), (b'if not visibility:IsUnitVisible(other) then return false end\n       if other:GetOwner()~=pid then return false end', b'if not visibility:IsUnitVisible(other) then return false end\n       if city~=nil then return false end\n       if other:GetOwner()~=pid then return false end'), (b'if Cities.GetCityInPlot(tx,ty)~=nil then return false end', b'if ownCityAt(tx,ty,targetIndex)==false then return false end'))
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError('Historical movement city filter changed')
        source = source.replace(old, new)
    return source

def _multiturn_source(source: bytes, *, catalog: bool=False, request: bool=False) -> bytes:
    """Build the opt-in native-path profile while keeping the legacy source intact."""
    start = b'local function pathIsSingleTurn(unit,sourceIndex,destinationIndex)'
    end = b'local function targetIsSafe(unit,sourceIndex,targetIndex,reachable,expectedX,expectedY)'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Historical movement path helper changed')
    before, tail = source.split(start, 1)
    path_body, target_tail = tail.split(end, 1)
    path = start + path_body
    path = path.replace(start, b'local function pathIsMultiTurn(unit,sourceIndex,destinationIndex)', 1)
    path = path.replace(b' local seen={}\n local visible={}', b' local seen={}\n local visible={}\n local previousTurn=0', 1)
    path = path.replace(b'   if turn~=1 then return false end', b'   if turn<1 or turn<previousTurn then return false end\n   previousTurn=turn', 1)
    if path.count(b'previousTurn=turn') != 1:
        raise RuntimeError('Could not construct multi-turn path validator')
    target = end + target_tail
    old_guard = b'if reachable==nil or not reachable[targetIndex] then return false end'
    if target.count(old_guard) != 1:
        raise RuntimeError('Historical movement reachability guard changed')
    target = target.replace(old_guard, b'if reachable~=false and (reachable==nil or not reachable[targetIndex]) then return false end', 1)
    target = target.replace(b'pathIsSingleTurn(unit,sourceIndex,targetIndex)', b'pathIsMultiTurn(unit,sourceIndex,targetIndex)', 1)
    target = target.replace(end, b'local function targetIsSafeMultiTurn(unit,sourceIndex,targetIndex,reachable,expectedX,expectedY)', 1)
    path_check = b' local pathPlots,pathTurns=pathIsMultiTurn(unit,sourceIndex,targetIndex)\n if not pathPlots then return false end\n'
    if target.count(path_check) != 1:
        raise RuntimeError('Historical movement path admission changed')
    target = target.replace(path_check, b'', 1)
    legality_anchor = b' local params={[UnitOperationTypes.PARAM_X]=tx,[UnitOperationTypes.PARAM_Y]=ty,\n               [UnitOperationTypes.PARAM_MODIFIERS]=moveFlags}'
    if target.count(legality_anchor) != 1:
        raise RuntimeError('Historical movement legality boundary changed')
    target = target.replace(legality_anchor, b' local pathPlots,pathTurns=pathIsMultiTurn(unit,sourceIndex,targetIndex)\n if not pathPlots then return false end\n' + legality_anchor, 1)
    source = before + path + target
    reachable_requirement = b" and\n       type(UnitManager.GetReachableMovement)=='function'"
    if source.count(reachable_requirement) != 1:
        raise RuntimeError('Historical reachable movement API guard changed')
    source = source.replace(reachable_requirement, b'', 1)
    reachable_start = b'local function reachableSet(unit)'
    visible_start = b'local function visiblePlot(index)'
    if source.count(reachable_start) != 1 or source.count(visible_start) != 1:
        raise RuntimeError('Historical reachable plot helper changed')
    before_reachable, remaining = source.split(reachable_start, 1)
    _, after_reachable = remaining.split(visible_start, 1)
    source = before_reachable + visible_start + after_reachable
    if catalog:
        old = b'   local reachable=reachableSet(unit)\n   if reachable~=nil then\n     for destinationIndex in pairs(reachable) do'
        new = b'   local reachable=false\n   do\n     for destinationIndex=0,plotCount-1 do'
        if source.count(old) != 1:
            raise RuntimeError('Historical movement candidate loop changed')
        source = source.replace(old, new, 1)
        old_call = b'targetIsSafe(unit,sourceIndex,destinationIndex,reachable)'
        if source.count(old_call) != 1:
            raise RuntimeError('Historical movement candidate safety call changed')
        source = source.replace(old_call, b'targetIsSafeMultiTurn(unit,sourceIndex,destinationIndex,reachable)', 1)
    elif request:
        old = b"local reachable=reachableSet(unit)\nassert(reachable~=nil and reachable[destinationIndex],\n       'destination is no longer in native reachable movement')"
        if source.count(old) != 1:
            raise RuntimeError('Historical movement request reachability changed')
        source = source.replace(old, b'local reachable=false', 1)
        old_call = b'targetIsSafe(unit,sourceIndex,destinationIndex,reachable,tx,ty)'
        if source.count(old_call) != 1:
            raise RuntimeError('Historical movement request safety call changed')
        source = source.replace(old_call, b'targetIsSafeMultiTurn(unit,sourceIndex,destinationIndex,reachable,tx,ty)', 1)
    return source

def _preview_catalog_source(source: bytes) -> bytes:
    """Keep each already-validated native path beside its candidate row."""
    replacements = ((b'local choices,seen={},{}', b'local choices,seen,routes={},{},{}'), (b'       if destinationIndex~=sourceIndex and targetIsSafe(unit,sourceIndex,destinationIndex,reachable) then', b'       if destinationIndex~=sourceIndex then\n         local pathPlots,pathTurns=targetIsSafe(unit,sourceIndex,destinationIndex,reachable)\n         if pathPlots then'), (b'       if destinationIndex~=sourceIndex and targetIsSafeMultiTurn(unit,sourceIndex,destinationIndex,reachable) then', b'       if destinationIndex~=sourceIndex then\n         local pathPlots,pathTurns=targetIsSafeMultiTurn(unit,sourceIndex,destinationIndex,reachable)\n         if pathPlots then'), (b'         choices[#choices+1]={uid=uid,sourceIndex=sourceIndex,sx=ux,sy=uy,\n                              destinationIndex=targetIndex,tx=tx,ty=ty,moves=moves}\n', b"         choices[#choices+1]={uid=uid,sourceIndex=sourceIndex,sx=ux,sy=uy,\n                              destinationIndex=targetIndex,tx=tx,ty=ty,moves=moves}\n         assert(pathPlots~=nil and pathTurns~=nil and #pathPlots==#pathTurns,\n                'native movement preview disappeared during catalog construction')\n         routes[#routes+1]={uid=uid,sourceIndex=sourceIndex,destinationIndex=targetIndex,\n                            plots=pathPlots,turns=pathTurns}\n"), (b"         assert(#choices<=4096,'legal movement catalog exceeds bound')\n       end\n     end\n", b"         assert(#choices<=4096,'legal movement catalog exceeds bound')\n       end\n       end\n     end\n"), (b"return table.concat(fields,';')\n", b"table.sort(routes,function(a,b)\n if a.uid~=b.uid then return a.uid<b.uid end\n return a.destinationIndex<b.destinationIndex\nend)\nfields[#fields+1]=table.concat({'P',dec(width),dec(height),dec(#routes)},',')\nfor _,route in ipairs(routes) do\n local routeFields={'R',dec(route.uid),dec(route.sourceIndex),dec(route.destinationIndex),dec(#route.plots)}\n for i=1,#route.plots do\n   routeFields[#routeFields+1]=dec(route.plots[i])\n   routeFields[#routeFields+1]=dec(route.turns[i])\n end\n fields[#fields+1]=table.concat(routeFields,',')\nend\nlocal result=table.concat(fields,';')\nassert(#result<=8388608,'public movement preview exceeds bounded payload')\nreturn result\n"))
    safety_indexes = (1, 2)
    if sum((source.count(replacements[index][0]) for index in safety_indexes)) != 1:
        raise RuntimeError('Native movement preview safety anchor changed')
    for index, (old, new) in enumerate(replacements):
        if index in safety_indexes and source.count(old) == 0:
            continue
        if source.count(old) != 1:
            raise RuntimeError('Native movement preview source anchor changed')
        source = source.replace(old, new, 1)
    return source

def candidate_source(player_id: int, expected_turn: int, *, allow_improvements: bool=False, allow_own_cities: bool=False, allow_multiturn: bool=False, include_preview: bool=False) -> bytes:
    pid = _player_id(player_id)
    turn = _u32(expected_turn, 'expected turn')
    if type(include_preview) is not bool:
        raise ValueError('include_preview must be an explicit Boolean')
    verify_source()
    _check_improvement_option(allow_improvements)
    _check_city_option(allow_own_cities)
    _check_multiturn_option(allow_multiturn)
    source = _lua_context(pid, turn, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities) + b"local choices,seen={},{}\nlocal count,work=0,0\nfor _,unit in p:GetUnits():Members() do\n count=count+1\n assert(count<=4096,'own unit enumeration exceeds bound')\n assert(unit:GetOwner()==pid,'foreign unit in own collection')\n local uid=integer(unit:GetID(),'unit ID',4294967295)\n local ux,uy=unit:GetX(),unit:GetY()\n point(ux,uy)\n local sourceIndex=integer(Map.GetPlotIndex(ux,uy),'source plot',plotCount-1)\n assert(unit:GetPlotId()==sourceIndex,'unit location APIs disagree')\n local moves=unit:GetMovesRemaining()\n assert(type(moves)=='number' and moves==moves and moves~=math.huge and moves~=-math.huge and moves>=0,\n        'invalid remaining movement')\n if unitEligible(unit) then\n   local reachable=reachableSet(unit)\n   if reachable~=nil then\n     for destinationIndex in pairs(reachable) do\n       work=work+1\n       assert(work<=100000,'reachable movement work budget exceeded')\n       if destinationIndex~=sourceIndex and targetIsSafe(unit,sourceIndex,destinationIndex,reachable) then\n         local target,tx,ty=visiblePlot(destinationIndex)\n         assert(target~=nil,'visible target changed during catalog construction')\n         local targetIndex=integer(target:GetIndex(),'destination plot',plotCount-1)\n         assert(targetIndex==destinationIndex,'destination index disagrees with native path')\n         choices[#choices+1]={uid=uid,sourceIndex=sourceIndex,sx=ux,sy=uy,\n                              destinationIndex=targetIndex,tx=tx,ty=ty,moves=moves}\n         local key=tostring(uid)..':'..tostring(targetIndex)\n         assert(not seen[key],'duplicate native movement candidate')\n         seen[key]=true\n         assert(#choices<=4096,'legal movement catalog exceeds bound')\n       end\n     end\n   end\n end\nend\ntable.sort(choices,function(a,b)\n if a.uid~=b.uid then return a.uid<b.uid end\n return a.destinationIndex<b.destinationIndex\nend)\nlocal fields={table.concat({dec(pid),dec(expectedTurn),dec(#choices)},',')}\nfor _,choice in ipairs(choices) do\n fields[#fields+1]=table.concat({dec(choice.uid),dec(choice.sourceIndex),dec(choice.sx),dec(choice.sy),\n  dec(choice.destinationIndex),dec(choice.tx),dec(choice.ty),string.format('%.17g',choice.moves)},',')\nend\nreturn table.concat(fields,';')\n"
    if allow_multiturn:
        source = _multiturn_source(source, catalog=True)
    return _preview_catalog_source(source) if include_preview else source

def _parse_movement(value: bytes, *, allow_zero: bool=False) -> tuple[bytes, float]:
    if type(value) is not bytes or not _DECIMAL.fullmatch(value):
        raise ValueError('Invalid remaining movement token')
    number = float(value)
    if not math.isfinite(number) or number < 0 or (number == 0 and (not allow_zero)):
        raise ValueError('Movement must be finite and positive for a move')
    return (value, number)

def parse_candidates(payload: bytes, expected_player: int, expected_turn: int | None=None, *, include_preview: bool=False) -> dict | tuple[dict, dict]:
    if type(include_preview) is not bool:
        raise ValueError('include_preview must be an explicit Boolean')
    if include_preview:
        return _parse_candidates_with_preview(payload, expected_player, expected_turn)
    pid = int(_player_id(expected_player))
    if type(payload) is not bytes or len(payload) > 524288:
        raise ValueError('Invalid movement catalog response')
    rows = payload.split(b';')
    header = rows[0].split(b',')
    if len(header) != 3:
        raise ValueError('Malformed movement catalog header')
    actual_pid = _parse_uint(header[0], 'player ID', 63)
    turn = _parse_uint(header[1], 'game turn')
    count = _parse_uint(header[2], 'choice count', 4096)
    if actual_pid != pid or (expected_turn is not None and turn != _parse_uint(_u32(expected_turn, 'expected turn'), 'expected turn')):
        raise ValueError('Movement catalog is stale or for another player')
    if len(rows) != count + 1:
        raise ValueError('Movement catalog count does not match records')
    choices = []
    previous = None
    seen = set()
    for row in rows[1:]:
        fields = row.split(b',')
        if len(fields) != 8:
            raise ValueError('Malformed movement choice record')
        values = tuple((_parse_uint(v, label, _MAX_PLOT_INDEX if label in ('source plot', 'destination plot') else 4294967295) for v, label in zip(fields[:7], ('unit ID', 'source plot', 'source x', 'source y', 'destination plot', 'destination x', 'destination y'))))
        uid, source_plot, sx, sy, dest_plot, dx, dy = values
        if sx > 65535 or sy > 65535 or dx > 65535 or (dy > 65535):
            raise ValueError('Movement coordinates are outside bounds')
        movement_token, movement = _parse_movement(fields[7])
        key = (uid, dest_plot)
        if key in seen or (previous is not None and key <= previous):
            raise ValueError('Movement catalog is duplicate or unsorted')
        if source_plot == dest_plot or (sx == dx and sy == dy):
            raise ValueError('Movement destination equals its source')
        seen.add(key)
        previous = key
        choices.append({'unit_id': uid, 'source_plot_id': source_plot, 'source_x': sx, 'source_y': sy, 'destination_plot_id': dest_plot, 'destination_x': dx, 'destination_y': dy, 'moves_token': movement_token, 'moves_remaining': movement})
    return {'status': 'catalog', 'player_id': pid, 'current_game_turn': turn, 'choices': tuple(choices)}

def _parse_candidates_with_preview(payload: bytes, expected_player: int, expected_turn: int | None) -> tuple[dict, dict]:
    if type(payload) is not bytes or len(payload) > _PREVIEW_MAX_BYTES:
        raise ValueError('Invalid bounded movement-preview response')
    rows = payload.split(b';')
    if not rows:
        raise ValueError('Missing movement-preview header')
    header = rows[0].split(b',')
    if len(header) != 3:
        raise ValueError('Malformed movement catalog header')
    player_id = _parse_uint(header[0], 'player ID', 63)
    turn = _parse_uint(header[1], 'game turn')
    candidate_count = _parse_uint(header[2], 'choice count', 4096)
    if len(rows) < candidate_count + 2:
        raise ValueError('Movement-preview trailer is missing')
    catalog = parse_candidates(b';'.join(rows[:candidate_count + 1]), expected_player, expected_turn)
    trailer = rows[candidate_count + 1].split(b',')
    if len(trailer) != 4 or trailer[0] != b'P':
        raise ValueError('Malformed movement-preview dimensions')
    width = _parse_uint(trailer[1], 'map width', _MAX_PLOT_INDEX + 1)
    height = _parse_uint(trailer[2], 'map height', _MAX_PLOT_INDEX + 1)
    route_count = _parse_uint(trailer[3], 'route count', 4096)
    if width == 0 or height == 0 or width * height > _MAX_PLOT_INDEX + 1 or (len(rows) != candidate_count + route_count + 2) or (route_count != candidate_count):
        raise ValueError('Movement-preview dimensions or route count differ')
    routes = []
    previous = None
    seen = set()
    max_plot_count = width * height
    for row in rows[candidate_count + 2:]:
        fields = row.split(b',')
        if len(fields) < 9 or fields[0] != b'R':
            raise ValueError('Malformed native movement route')
        unit_id = _parse_uint(fields[1], 'route unit ID', 4294967295)
        source_plot = _parse_uint(fields[2], 'route source plot', max_plot_count - 1)
        destination_plot = _parse_uint(fields[3], 'route destination plot', max_plot_count - 1)
        path_count = _parse_uint(fields[4], 'route path length', max_plot_count)
        if path_count < 2 or len(fields) != 5 + 2 * path_count:
            raise ValueError('Native movement route is incomplete or malformed')
        plot_ids = []
        turns = []
        for index in range(path_count):
            plot_id = _parse_uint(fields[5 + 2 * index], 'route plot', max_plot_count - 1)
            native_turn = _parse_uint(fields[6 + 2 * index], 'route turn', 4294967295)
            if native_turn < 1 or (turns and native_turn < turns[-1]):
                raise ValueError('Native movement route turns are invalid or decreasing')
            if plot_id in plot_ids:
                raise ValueError('Native movement route repeats a plot')
            plot_ids.append(plot_id)
            turns.append(native_turn)
        key = (unit_id, destination_plot)
        if source_plot == destination_plot or plot_ids[0] != source_plot or plot_ids[-1] != destination_plot or (key in seen) or (previous is not None and key <= previous):
            raise ValueError('Native movement route identity or endpoints differ')
        seen.add(key)
        previous = key
        routes.append(dict(unit_id=unit_id, source_plot_id=source_plot, destination_plot_id=destination_plot, plot_ids=plot_ids, turns=turns))
    candidate_keys = {(item['unit_id'], item['destination_plot_id']): item['source_plot_id'] for item in catalog['choices']}
    route_keys = {(item['unit_id'], item['destination_plot_id']): item['source_plot_id'] for item in routes}
    if route_keys != candidate_keys:
        raise ValueError('Native preview roster differs from exact movement candidates')
    preview = dict(schema='civ6rl.public_movement_preview.v1', player_id=player_id, turn=turn, width=width, height=height, routes=routes)
    return (catalog, preview)

def choose(catalog: dict, unit_id: int, destination_plot_id: int) -> dict:
    required = {'status', 'player_id', 'current_game_turn', 'choices'}
    if type(catalog) is not dict or set(catalog) != required or catalog.get('status') != 'catalog' or (type(catalog.get('choices')) is not tuple) or (len(catalog['choices']) > 4096):
        raise ValueError('Invalid movement catalog')
    _player_id(catalog['player_id'])
    _u32(catalog['current_game_turn'], 'game turn')
    previous = None
    seen = set()
    item_keys = set(_CHOICE_FIELDS) | {'moves_token', 'moves_remaining'}
    for item in catalog['choices']:
        if type(item) is not dict or set(item) != item_keys:
            raise ValueError('Invalid movement catalog entry')
        for field in ('unit_id', 'source_plot_id', 'destination_plot_id'):
            _u32(item[field], field)
        for field in ('source_x', 'source_y', 'destination_x', 'destination_y'):
            _coords(item[field], field)
        _parse_movement(item['moves_token'])
        key = (item['unit_id'], item['destination_plot_id'])
        if key in seen or (previous is not None and key <= previous):
            raise ValueError('Movement catalog is unordered or ambiguous')
        seen.add(key)
        previous = key
    uid = int(_u32(unit_id, 'unit ID'))
    plot = int(_u32(destination_plot_id, 'destination plot'))
    matches = [item for item in catalog['choices'] if item.get('unit_id') == uid and item.get('destination_plot_id') == plot]
    if len(matches) != 1:
        raise ValueError('Move is absent or ambiguous in the current catalog')
    choice = {'player_id': catalog['player_id'], 'current_game_turn': catalog['current_game_turn'], **matches[0]}
    _validate_choice(choice)
    return choice

def _validate_choice(choice: dict) -> None:
    required = {'player_id', 'current_game_turn', *_CHOICE_FIELDS, 'moves_token', 'moves_remaining'}
    if type(choice) is not dict or set(choice) != required:
        raise ValueError('Invalid movement choice')
    _player_id(choice['player_id'])
    _u32(choice['current_game_turn'], 'game turn')
    for field in _CHOICE_FIELDS:
        _u32(choice[field], field)
    if choice['source_plot_id'] > _MAX_PLOT_INDEX or choice['destination_plot_id'] > _MAX_PLOT_INDEX:
        raise ValueError('Plot index is outside the bounded map range')
    for field in ('source_x', 'source_y', 'destination_x', 'destination_y'):
        _coords(choice[field], field)
    token, number = _parse_movement(choice['moves_token'])
    if type(choice['moves_remaining']) not in (float, int) or choice['moves_remaining'] != number:
        raise ValueError('Movement amount does not match its exact source token')
    if choice['source_plot_id'] == choice['destination_plot_id']:
        raise ValueError('Source and destination plots must differ')

def request_source(choice: dict, *, allow_improvements: bool=False, allow_own_cities: bool=False, allow_multiturn: bool=False) -> bytes:
    """Recheck the exact unit, position, movement, path, and UI legality, then request MOVE_TO."""
    _validate_choice(choice)
    verify_source()
    _check_improvement_option(allow_improvements)
    _check_city_option(allow_own_cities)
    _check_multiturn_option(allow_multiturn)
    pid = _player_id(choice['player_id'])
    turn = _u32(choice['current_game_turn'], 'game turn')
    encoded = (choice['unit_id'], choice['source_plot_id'], choice['source_x'], choice['source_y'], choice['destination_plot_id'], choice['destination_x'], choice['destination_y'])
    literals = b','.join((_u32(value, 'movement request field') for value in encoded))
    source = _lua_context(pid, turn, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities) + b'local uid,sourceIndex,sx,sy,destinationIndex,tx,ty=' + literals + b'\nlocal expectedMoves=' + choice['moves_token'] + b"\nassert(expectedMoves>0,'move has no remaining movement')\nlocal unit=ownUnit(pid,uid)\nassert(unit~=nil and unit:GetOwner()==pid,'requested own unit unavailable')\nassert(unit:GetX()==sx and unit:GetY()==sy and unit:GetPlotId()==sourceIndex,\n       'unit moved since candidate selection')\nassert(unitEligible(unit),'unit is no longer eligible to move')\nlocal moves=unit:GetMovesRemaining()\nassert(type(moves)=='number' and moves==expectedMoves and moves>0,\n       'remaining movement changed since candidate selection')\nlocal reachable=reachableSet(unit)\nassert(reachable~=nil and reachable[destinationIndex],\n       'destination is no longer in native reachable movement')\nlocal pathPlots,pathTurns=targetIsSafe(unit,sourceIndex,destinationIndex,reachable,tx,ty)\nassert(pathPlots~=nil and pathPlots~=false and pathTurns~=nil,\n       'destination or path is unsafe or no longer a one-turn legal path')\nlocal params={[UnitOperationTypes.PARAM_X]=tx,[UnitOperationTypes.PARAM_Y]=ty,\n              [UnitOperationTypes.PARAM_MODIFIERS]=moveFlags}\nassert(UnitManager.CanStartOperation(unit,UnitOperationTypes.MOVE_TO,nil,params)==true,\n       'native MOVE_TO legality check rejected the request')\nUnitManager.RequestOperation(unit,UnitOperationTypes.MOVE_TO,params)\nlocal serialized={}\nfor i=1,#pathPlots do serialized[i]=table.concat({dec(pathPlots[i]),dec(pathTurns[i])},',') end\nreturn table.concat({'submitted',dec(pid),dec(expectedTurn),dec(uid),dec(destinationIndex)},',')..';'..\n       table.concat(serialized,';')\n"
    return _multiturn_source(source, request=True) if allow_multiturn else source

def inspection_source(choice: dict, *, allow_improvements: bool=True, allow_own_cities: bool=False, allow_multiturn: bool=False) -> bytes:
    """Read exact visible path/improvement metadata before an explicit move.

This diagnostic chunk shares the request's complete fresh-choice validation
prefix but contains no RequestOperation. Its output is a bounded evidence
sidecar, not a new observation channel for the actor.
"""
    _check_multiturn_option(allow_multiturn)
    request = request_source(choice, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities, allow_multiturn=allow_multiturn)
    marker = b'UnitManager.RequestOperation(unit,UnitOperationTypes.MOVE_TO,params)\n'
    if request.count(marker) != 1:
        raise RuntimeError('Movement request mutation boundary changed')
    prefix = request.split(marker, 1)[0]
    source = prefix + b'local inspectionRows={}\nlocal function quote(text)\n assert(type(text)==\'string\' and #text<=112 and string.match(text,\'^IMPROVEMENT_[A-Z0-9_]+$\'),\n        \'invalid inspected improvement name\')\n return \'"\'..text..\'"\'\nend\nfor i,index in ipairs(pathPlots) do\n local plot,x,y=visiblePlot(index)\n assert(plot and plot:GetIndex()==index,\'inspected path visibility or identity changed\')\n local owner=plot:GetOwner()\n assert(type(owner)==\'number\' and owner==math.floor(owner) and owner>=-1 and owner<=63,\n        \'invalid inspected plot owner\')\n assert(i==1 or owner==-1 or owner==pid,\'inspected entered plot became foreign\')\n assert(type(plot.GetImprovementType)==\'function\',\'inspected improvement getter unavailable\')\n local improvement=plot:GetImprovementType()\n assert(type(improvement)==\'number\' and improvement==math.floor(improvement) and\n        improvement>=-1 and improvement<=2147483647,\'invalid inspected improvement index\')\n local name,remove,goody,camp=\'null\',\'null\',\'null\',\'null\'\n if improvement~=-1 then\n  assert(GameInfo and GameInfo.Improvements,\'inspected improvement metadata unavailable\')\n  local row=GameInfo.Improvements[improvement]\n  assert(row~=nil and row.Index==improvement,\'inspected improvement metadata identity differs\')\n  name=quote(row.ImprovementType)\n  assert(type(row.RemoveOnEntry)==\'boolean\' and type(row.Goody)==\'boolean\' and\n         type(row.BarbarianCamp)==\'boolean\',\'inspected improvement entry flags unavailable\')\n  assert(i==1 or (not row.RemoveOnEntry and not row.Goody and not row.BarbarianCamp),\n         \'inspected entered improvement changed to an entry effect\')\n  remove=tostring(row.RemoveOnEntry);goody=tostring(row.Goody);camp=tostring(row.BarbarianCamp)\n end\n inspectionRows[#inspectionRows+1]=\'{"plot_id":\'..dec(index)..\',"turn":\'..dec(pathTurns[i])..\n  \',"owner":\'..dec(owner)..\',"improvement_index":\'..dec(improvement)..\',"improvement_type":\'..name..\n  \',"remove_on_entry":\'..remove..\',"goody":\'..goody..\',"barbarian_camp":\'..camp..\'}\'\nend\nreturn \'{"schema":"civ6rl.native_movement_inspection989.v1","player_id":\'..dec(pid)..\n \',"turn":\'..dec(expectedTurn)..\',"unit_id":\'..dec(uid)..\',"source_plot_id":\'..dec(sourceIndex)..\n \',"destination_plot_id":\'..dec(destinationIndex)..\',"allow_improvements":' + (b'true' if allow_improvements else b'false') + b',"path":[\'..table.concat(inspectionRows,\',\')..\']}\'\n'
    if not allow_own_cities:
        return source
    city_inspection = b' local city=visibleCityIdentity(x,y,index)\n local cityJSON=\'null\'\n if city~=nil then\n  assert(i==1 or city.owner==pid,\'inspected entered city became foreign\')\n  local found=Units.GetUnitsInPlotLayerID(x,y,MapLayers.ANY)\n  local count=0\n  if found~=nil then\n   assert(type(found)==\'table\',\'inspected city units have an invalid shape\')\n   for _,other in pairs(found) do\n    assert(visibility:IsUnitVisible(other),\'inspected city contains a hidden unit\')\n    count=count+1; assert(count<=4096,\'inspected city unit count exceeds bound\')\n   end\n  end\n  assert(i==1 or count==0,\'inspected entered city is occupied\')\n  cityJSON=\'{"id":\'..dec(city.id)..\',"owner":\'..dec(city.owner)..\',"x":\'..dec(city.x)..\n   \',"y":\'..dec(city.y)..\',"plot_id":\'..dec(city.plot_id)..\',"unit_count":\'..dec(count)..\'}\'\n end\n'
    replacements = ((b' inspectionRows[#inspectionRows+1]=', city_inspection + b' inspectionRows[#inspectionRows+1]='), (b"..camp..'}'", b'..camp..\',"x":\'..dec(x)..\',"y":\'..dec(y)..\',"city":\'..cityJSON..\'}\''), (b'civ6rl.native_movement_inspection989.v1', b'civ6rl.native_movement_inspection999.v1'), (b',"path":[', b',"allow_own_cities":true,"path":['))
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError('Historical movement inspection changed')
        source = source.replace(old, new)
    return source

def parse_inspection(payload: bytes, choice: dict, *, allow_improvements: bool=True, allow_own_cities: bool=False, allow_multiturn: bool=False) -> dict:
    """Validate a <=512 KiB pre-request native evidence sidecar for this choice."""
    _validate_choice(choice)
    if type(allow_improvements) is not bool:
        raise ValueError('allow_improvements must be an explicit Boolean')
    _check_city_option(allow_own_cities)
    _check_multiturn_option(allow_multiturn)
    if type(payload) is not bytes or not 0 < len(payload) <= 524288:
        raise ValueError('Invalid movement inspection payload')
    value = json.loads(payload)
    fields = {'schema', 'player_id', 'turn', 'unit_id', 'source_plot_id', 'destination_plot_id', 'allow_improvements', 'path'}
    schema = 'civ6rl.native_movement_inspection989.v1'
    if allow_own_cities:
        schema = 'civ6rl.native_movement_inspection999.v1'
        fields.add('allow_own_cities')
    if type(value) is not dict or set(value) != fields or value['schema'] != schema:
        raise ValueError('Invalid movement inspection schema or fields')
    if allow_own_cities and value['allow_own_cities'] is not True:
        raise ValueError('Movement city inspection profile differs')
    identities = {'player_id': choice['player_id'], 'turn': choice['current_game_turn'], 'unit_id': choice['unit_id'], 'source_plot_id': choice['source_plot_id'], 'destination_plot_id': choice['destination_plot_id']}
    if any((type(value[name]) is not int or value[name] != expected for name, expected in identities.items())):
        raise ValueError('Movement inspection identity differs from choice')
    if type(value['allow_improvements']) is not bool or value['allow_improvements'] != allow_improvements:
        raise ValueError('Movement inspection profile differs')
    path = value['path']
    if type(path) is not list or not 2 <= len(path) <= _MAX_PLOT_INDEX + 1:
        raise ValueError('Movement inspection path exceeds bounds')
    row_fields = {'plot_id', 'turn', 'owner', 'improvement_index', 'improvement_type', 'remove_on_entry', 'goody', 'barbarian_camp'}
    if allow_own_cities:
        row_fields.update(('x', 'y', 'city'))
    seen = set()
    for position, row in enumerate(path):
        if type(row) is not dict or set(row) != row_fields:
            raise ValueError('Malformed movement inspection row')
        for name, minimum, maximum in (('plot_id', 0, _MAX_PLOT_INDEX), ('turn', 1, _MAX_PLOT_INDEX + 1 if allow_multiturn else 1), ('owner', -1, 63), ('improvement_index', -1, 2147483647)):
            if type(row[name]) is not int or not minimum <= row[name] <= maximum:
                raise ValueError('Invalid movement inspection integer: ' + name)
        if row['plot_id'] in seen:
            raise ValueError('Movement inspection repeats a plot')
        seen.add(row['plot_id'])
        if position and row['turn'] < path[position - 1]['turn']:
            raise ValueError('Movement inspection path turns decrease')
        if allow_own_cities:
            for key in ('x', 'y'):
                if type(row[key]) is not int or not 0 <= row[key] <= 65535:
                    raise ValueError('Invalid inspected path coordinates')
            city = row['city']
            if city is not None:
                if type(city) is not dict or set(city) != {'id', 'owner', 'x', 'y', 'plot_id', 'unit_count'}:
                    raise ValueError('Invalid inspected city fields')
                for key, bound in (('id', 4294967295), ('owner', 63), ('x', 65535), ('y', 65535), ('plot_id', _MAX_PLOT_INDEX), ('unit_count', 4096)):
                    if type(city[key]) is not int or not 0 <= city[key] <= bound:
                        raise ValueError('Invalid inspected city integer: ' + key)
                if any((city[key] != row[key] for key in ('x', 'y', 'plot_id'))):
                    raise ValueError('Inspected city location differs from its path plot')
                if position > 0 and (city['owner'] != choice['player_id'] or city['unit_count'] != 0):
                    raise ValueError('Inspected entered city is foreign or occupied')
        flags = [row[name] for name in ('remove_on_entry', 'goody', 'barbarian_camp')]
        if row['improvement_index'] == -1:
            if row['improvement_type'] is not None or any((flag is not None for flag in flags)):
                raise ValueError('Empty inspected plot contains improvement metadata')
        elif type(row['improvement_type']) is not str or re.fullmatch('IMPROVEMENT_[A-Z0-9_]{1,100}', row['improvement_type']) is None or any((type(flag) is not bool for flag in flags)):
            raise ValueError('Invalid inspected improvement metadata')
        if position > 0:
            if row['owner'] not in (-1, choice['player_id']):
                raise ValueError('Movement inspection enters foreign territory')
            if row['improvement_index'] != -1 and (not allow_improvements or any(flags)):
                raise ValueError('Movement inspection enters an unqualified improvement')
    if path[0]['plot_id'] != choice['source_plot_id'] or path[-1]['plot_id'] != choice['destination_plot_id']:
        raise ValueError('Movement inspection path does not match choice endpoints')
    if allow_own_cities and ((path[0]['x'], path[0]['y']) != (choice['source_x'], choice['source_y']) or (path[-1]['x'], path[-1]['y']) != (choice['destination_x'], choice['destination_y'])):
        raise ValueError('Movement city inspection coordinates differ from choice endpoints')
    return value

def parse_request_result(payload: bytes, choice: dict, *, allow_multiturn: bool=False) -> dict:
    _validate_choice(choice)
    _check_multiturn_option(allow_multiturn)
    if type(payload) is not bytes or not payload or len(payload) > 524288:
        raise ValueError('Invalid movement request response')
    rows = payload.split(b';')
    fields = rows[0].split(b',')
    if len(fields) != 5 or fields[0] != b'submitted':
        raise ValueError('MOVE_TO request was not submitted')
    actual = tuple((_parse_uint(x, label) for x, label in zip(fields[1:], ('player ID', 'game turn', 'unit ID', 'destination plot'))))
    expected = (choice['player_id'], choice['current_game_turn'], choice['unit_id'], choice['destination_plot_id'])
    if actual != expected:
        raise ValueError('MOVE_TO submission response does not match choice')
    if not 3 <= len(rows) <= _MAX_PLOT_INDEX + 2:
        raise ValueError('Native path length is outside bounds')
    plot_ids = []
    turns = []
    seen = set()
    for row in rows[1:]:
        pair = row.split(b',')
        if len(pair) != 2:
            raise ValueError('Malformed native path record')
        plot_id = _parse_uint(pair[0], 'path plot', _MAX_PLOT_INDEX)
        turn = _parse_uint(pair[1], 'path turn', _MAX_PLOT_INDEX + 1)
        if plot_id in seen:
            raise ValueError('Native path repeats a plot')
        if turn < 1 or (turn < turns[-1] if turns else False):
            raise ValueError('Native path turns are invalid or decrease')
        seen.add(plot_id)
        plot_ids.append(plot_id)
        turns.append(turn)
    if plot_ids[0] != choice['source_plot_id'] or plot_ids[-1] != choice['destination_plot_id'] or (not allow_multiturn and any((value != 1 for value in turns))):
        raise ValueError('Native path does not match the movement choice')
    return {'submitted': True, 'applied': False, 'choice': choice, 'native_path': {'plot_ids': tuple(plot_ids), 'turns': tuple(turns)}}

def effect_source(choice: dict) -> bytes:
    """Observe unit position after the host drains movement events; never infers application."""
    _validate_choice(choice)
    verify_source()
    pid = _player_id(choice['player_id'])
    uid = _u32(choice['unit_id'], 'unit ID')
    turn = _u32(choice['current_game_turn'], 'game turn')
    return b'local pid,uid,expectedTurn=' + pid + b',' + uid + b',' + turn + b"\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n       Game.GetCurrentGameTurn()==expectedTurn,\n       'movement effect observation is stale or for another player')\nassert(type(Game.IsAllowStrategicCommands)=='function' and\n       Game.IsAllowStrategicCommands(pid)==true,'strategic commands are unavailable')\nlocal p=Players and Players[pid]\nassert(p and p:IsAlive()==true,'requested player unavailable')\nlocal unit=nil\nlocal count=0\nfor _,candidate in p:GetUnits():Members() do\n count=count+1; assert(count<=4096,'own unit enumeration exceeds bound')\n assert(candidate:GetOwner()==pid,'foreign unit in own unit collection')\n if candidate:GetID()==uid then assert(unit==nil,'duplicate unit id'); unit=candidate end\nend\nif unit==nil then return table.concat({'missing',string.format('%d',pid),string.format('%d',expectedTurn),string.format('%d',uid)},',') end\nlocal x,y=unit:GetX(),unit:GetY()\nlocal moves=unit:GetMovesRemaining()\nassert(type(moves)=='number' and moves==moves and moves~=math.huge and moves~=-math.huge and moves>=0,\n       'invalid remaining movement')\nreturn table.concat({'unit',string.format('%d',pid),string.format('%d',expectedTurn),\n string.format('%d',uid),string.format('%d',x),string.format('%d',y),\n string.format('%.17g',moves)},',')\n"

def guard_case() -> bytes:
    """Exercise a multi-plot one-turn path and fail-closed movement hazards."""
    candidate = candidate_source(0, 7)
    selected = {'player_id': 0, 'current_game_turn': 7, 'unit_id': 17, 'source_plot_id': 22, 'source_x': 2, 'source_y': 2, 'destination_plot_id': 23, 'destination_x': 3, 'destination_y': 2, 'moves_token': b'2', 'moves_remaining': 2.0}
    request = request_source(selected)
    return b"local originalTable,originalDirections,originalVisibility,originalLayers=\n table,DirectionTypes,PlayersVisibility,MapLayers\nlocal function globalsUnchanged()\n return table==originalTable and DirectionTypes==originalDirections and\n        PlayersVisibility==originalVisibility and MapLayers==originalLayers\nend\nlocal table=setmetatable({}, {__index=originalTable})\nlocal S={pid=0,observer=0,turn=7,strategic=true,alive=true,active=true,complete=true,\n ready=true,x=2,y=2,moves=2,owner=0,targetOwner=-1,improvement=-1,city=false,reachable={23},\n pathKind='good',war=false,legal=true,exists=true,submitted=0,hiddenIndex=nil,\n hiddenUnit=false,transit=false,transitOwner=0,hiddenDetailReads=0,hiddenUnitOwnerReads=0,zoc=false}\nlocal unit={GetID=function()return 17 end,GetOwner=function()return S.owner end,\n GetX=function()return S.x end,GetY=function()return S.y end,GetPlotId=function()return S.y*10+S.x end,\n GetMovesRemaining=function()return S.moves end,GetUnitType=function()return 0 end,\n IsReadyToSelect=function()error('MOVE_TO must not query selection readiness') end,\n GetComponentID=function()return 1700 end,\n HasMovedIntoZOC=function()return S.zoc end}\nlocal function members()local yielded=false;return function()\n if not yielded and S.exists then yielded=true;return 1,unit end end end\nlocal player={IsAlive=function()return S.alive end,IsTurnActive=function()return S.active end,\n IsTurnActiveComplete=function()return S.complete end,GetUnits=function()return {Members=members}end}\nlocal Players={[0]=player}\nlocal Game={GetLocalPlayer=function()return S.pid end,GetLocalObserver=function()return S.observer end,\n GetCurrentGameTurn=function()return S.turn end,\n IsAllowStrategicCommands=function(pid)assert(pid==0);return S.strategic end}\nlocal DirectionTypes={DIRECTION_NORTHEAST=0,DIRECTION_EAST=1,DIRECTION_SOUTHEAST=2,\n DIRECTION_SOUTHWEST=3,DIRECTION_WEST=4,DIRECTION_NORTHWEST=5}\nlocal vis={IsVisible=function(_,x,y)return S.hiddenIndex~=y*10+x end,\n IsRevealed=function(_,index)return S.hiddenIndex~=index end,\n IsUnitVisible=function()return not S.hiddenUnit end}\nlocal PlayersVisibility={[0]=vis}\nlocal function plot(index,x,y,isTarget)\n return {GetIndex=function()return index end,GetX=function()return x end,GetY=function()return y end,\n  GetOwner=function()if S.hiddenIndex==index then S.hiddenDetailReads=S.hiddenDetailReads+1 end\n   return isTarget and S.targetOwner or -1 end,\n  GetImprovementType=function()if S.hiddenIndex==index then S.hiddenDetailReads=S.hiddenDetailReads+1 end\n   return isTarget and S.improvement or -1 end}\nend\nlocal plots={[22]=plot(22,2,2),[12]=plot(12,2,1),[23]=plot(23,3,2,true)}\nlocal Map={GetGridSize=function()return 10,10 end,GetPlotCount=function()return 100 end,\n GetPlotIndex=function(x,y)return y*10+x end,GetPlotByIndex=function(index)return plots[index]end}\nlocal UnitOperationTypes={MOVE_TO=40,PARAM_X=1,PARAM_Y=2,PARAM_MODIFIERS=3}\nlocal UnitOperationMoveModifiers={ATTACK=1,MOVE_IGNORE_UNEXPLORED_DESTINATION=2}\nlocal pathInfo={plots={22,12,23},turns={1,1,1}}\nlocal UnitManager={GetReachableMovement=function(u)assert(u==unit);return S.reachable end,\n GetMoveToPathEx=function(u,destination)\n  assert(u==unit)\n  if S.pathKind=='nil' then return nil end\n  if S.pathKind=='empty' then return {plots={},turns={}} end\n  if S.pathKind=='sparse' then return {plots={[1]=22,[3]=23},turns={[1]=1,[3]=1}} end\n  if S.pathKind=='multi' then return {plots={22,12,23},turns={1,2,1}} end\n if S.pathKind=='wrong_end' then return {plots={22,12,24},turns={1,1,1}} end\n if S.pathKind=='missing_turns' then return {plots={22,12,23}} end\n  return pathInfo\n end,\n CanStartOperation=function(u,op,third,params)\n  assert(u==unit and op==UnitOperationTypes.MOVE_TO and third==nil)\n  assert(params[UnitOperationTypes.PARAM_X]==3 and params[UnitOperationTypes.PARAM_Y]==2 and\n         params[UnitOperationTypes.PARAM_MODIFIERS]==3)\n  return S.legal\n end,\n RequestOperation=function(u,op,params)\n  assert(u==unit and op==UnitOperationTypes.MOVE_TO and S.legal and S.moves==2)\n  assert(params[1]==3 and params[2]==2 and params[3]==3)\n  S.submitted=S.submitted+1\n end}\nlocal other={GetOwner=function()S.hiddenUnitOwnerReads=S.hiddenUnitOwnerReads+1;return S.transitOwner end}\nlocal Units={GetUnitsInPlotLayerID=function(x,y)\n if x==2 and y==1 and S.transit then return {other} end\n return nil end}\nlocal Cities={GetCityInPlot=function()if S.city then return {} end end}\nlocal CombatManager={IsAttackChangeWarState=function()return S.war and {1} or nil end}\nlocal GameInfo={Units={[0]={IgnoreMoves=false,Spy=false,MakeTradeRoute=false}}}\nlocal MapLayers={ANY=0}\nlocal function catalog()\n" + candidate + b'\nend\nlocal function request()\n' + request + b"\nend\nassert(catalog()=='0,7,1;17,22,2,2,23,3,2,2')\nS.pathKind='nil';assert(catalog()=='0,7,0');S.pathKind='good'\nS.pathKind='empty';assert(catalog()=='0,7,0');S.pathKind='good'\nS.pathKind='multi';assert(catalog()=='0,7,0');S.pathKind='good'\nS.pathKind='sparse';assert(not pcall(catalog));S.pathKind='good'\n S.pathKind='wrong_end';assert(catalog()=='0,7,0' and not pcall(request));S.pathKind='good'\nS.pathKind='missing_turns';assert(not pcall(catalog));S.pathKind='good'\nS.reachable={};assert(catalog()=='0,7,0');S.reachable={23}\nS.reachable=nil;assert(catalog()=='0,7,0');S.reachable={23}\nS.reachable={[1]=23,[3]=24};assert(not pcall(catalog));S.reachable={23}\nS.reachable={23,23};assert(not pcall(catalog));S.reachable={23}\nS.reachable={100};assert(not pcall(catalog));S.reachable={23}\nS.hiddenIndex=12;S.hiddenDetailReads=0;assert(catalog()=='0,7,0' and S.hiddenDetailReads==0);S.hiddenIndex=nil\nS.transit=true;S.transitOwner=0;assert(catalog()=='0,7,1;17,22,2,2,23,3,2,2')\nS.transitOwner=1;assert(catalog()=='0,7,0');S.transitOwner=0\nS.hiddenUnit=true;S.hiddenUnitOwnerReads=0;assert(catalog()=='0,7,0' and S.hiddenUnitOwnerReads==0)\nS.hiddenUnit=false;S.transit=false\nS.city=true;assert(catalog()=='0,7,0');S.city=false\nS.improvement=4;assert(catalog()=='0,7,0');S.improvement=-1\nS.targetOwner=1;assert(catalog()=='0,7,0');S.targetOwner=-1\nS.war=true;assert(catalog()=='0,7,0');S.war=false\nS.legal=false;assert(catalog()=='0,7,0' and not pcall(request) and S.submitted==0);S.legal=true\nS.turn=8;assert(not pcall(request) and S.submitted==0);S.turn=7\nS.observer=1;assert(not pcall(catalog) and not pcall(request) and S.submitted==0);S.observer=0\nS.strategic=false;assert(not pcall(catalog) and not pcall(request) and S.submitted==0);S.strategic=true\nS.x=3;assert(not pcall(request) and S.submitted==0);S.x=2\nS.moves=1.5;assert(not pcall(request) and S.submitted==0);S.moves=2\nS.ready=false;assert(catalog()=='0,7,1;17,22,2,2,23,3,2,2')\nassert(request()=='submitted,0,7,17,23;22,1;12,1;23,1' and S.submitted==1)\nS.legal=false;assert(catalog()=='0,7,0' and not pcall(request) and S.submitted==1);S.legal=true\nS.ready=true;S.submitted=0\nS.active=false;assert(not pcall(request) and S.submitted==0);S.active=true\nS.complete=false;assert(not pcall(request) and S.submitted==0);S.complete=true\nS.owner=1;assert(not pcall(catalog) and not pcall(request) and S.submitted==0);S.owner=0\nGameInfo.Units[0].IgnoreMoves=true;assert(catalog()=='0,7,0');GameInfo.Units[0].IgnoreMoves=false\nGameInfo.Units[0].Spy=true;assert(catalog()=='0,7,0');GameInfo.Units[0].Spy=false\nGameInfo.Units[0].MakeTradeRoute=true;assert(catalog()=='0,7,0');GameInfo.Units[0].MakeTradeRoute=false\nS.zoc=true;assert(catalog()=='0,7,0');S.zoc=false\nS.exists=false;assert(catalog()=='0,7,0' and not pcall(request) and S.submitted==0);S.exists=true\nS.reachable={};assert(not pcall(request) and S.submitted==0);S.reachable={23}\nlocal response=request()\nassert(response=='submitted,0,7,17,23;22,1;12,1;23,1' and S.submitted==1)\nassert(globalsUnchanged(),'movement guard mutated game-child globals')\nreturn 'unit-movement-guards-ok'\n"

def parse_effect(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 128:
        raise ValueError('Invalid movement effect response')
    fields = payload.split(b',')
    if len(fields) == 4 and fields[0] == b'missing':
        actual = tuple((_parse_uint(x, label) for x, label in zip(fields[1:], ('player ID', 'game turn', 'unit ID'))))
        if actual != (choice['player_id'], choice['current_game_turn'], choice['unit_id']):
            raise ValueError('Missing-unit response does not match choice')
        return {'found': False, 'at_destination': False, 'moves_remaining': None}
    if len(fields) != 7 or fields[0] != b'unit':
        raise ValueError('Malformed movement effect response')
    actual = tuple((_parse_uint(x, label) for x, label in zip(fields[1:6], ('player ID', 'game turn', 'unit ID', 'x', 'y'))))
    if actual[:3] != (choice['player_id'], choice['current_game_turn'], choice['unit_id']):
        raise ValueError('Movement effect response is stale or mismatched')
    _coords(actual[3], 'observed x')
    _coords(actual[4], 'observed y')
    _, moves = _parse_movement(fields[6], allow_zero=True)
    return {'found': True, 'player_id': actual[0], 'turn': actual[1], 'unit_id': actual[2], 'x': actual[3], 'y': actual[4], 'at_destination': (actual[3], actual[4]) == (choice['destination_x'], choice['destination_y']), 'moves_remaining': moves}

def _parse_uint(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((c < 48 or c > 57 for c in token)) or (len(token) > 1 and token[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'{label} is out of range')
    return value

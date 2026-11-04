"""Endpoint-only adapter for the official WorldInput move click route.

This records the real UI RequestOperation callback. It does not claim the
request was delivered or applied; the native worker owns that receipt.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _WORLD_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import re
from pathlib import Path
from civ6_host.runtime.native.native_movement_ui_source import functions_source
from civ6_host.runtime.native.native_movement_ui_source import verified_files as _movement_verified_files
_PLAYER_MAX = 63
_U32_MAX = 4294967295
_PLOT_COUNT_MAX = 16384
_LIMIT = 4096
_STATUS = {'request', 'war_prompt', 'noop'}
_SOURCE_HASH = hashlib.sha256(functions_source()).hexdigest()
_WAR_POPUP = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\Popups\\DeclareWarPopup.lua"))
_WAR_POPUP_HASH = 'f95b880edb5ee6deb5244b0d82429d8541de93f3cf1c8840bf09fd4deaadd208'
_WAR_DECLARATION = re.compile('^function\\s+([A-Za-z_][A-Za-z_0-9]*)\\s*\\(')

def verified_files() -> dict[Path, str]:
    result = _movement_verified_files()
    if hashlib.sha256(_resolve_resource_path(_WAR_POPUP).read_bytes()).hexdigest() != _WAR_POPUP_HASH:
        raise RuntimeError('Pinned official war confirmation popup changed')
    result[_WAR_POPUP] = _WAR_POPUP_HASH
    return result

def _war_function(name: str) -> bytes:
    raw = _resolve_resource_path(_WAR_POPUP).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _WAR_POPUP_HASH:
        raise RuntimeError('Pinned official war confirmation popup changed')
    lines = raw.decode('utf-8-sig').splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith(f'function {name}(')]
    if len(starts) != 1:
        raise RuntimeError('Official war confirmation function anchor changed: ' + name)
    first = starts[0]
    end = next((i for i in range(first + 1, len(lines)) if _WAR_DECLARATION.match(lines[i])), len(lines))
    selected = lines[first:end]
    while selected and (not selected[-1].strip() or selected[-1].lstrip().startswith('--')):
        selected.pop()
    body = ''.join(selected).rstrip() + '\n'
    if not body.rstrip().endswith('end'):
        raise RuntimeError('Official war confirmation function is incomplete: ' + name)
    body = re.sub('^function ' + re.escape(name) + '\\(', 'local function ' + name + '(', body, count=1)
    return body.encode('utf-8')

def _war_source_hash() -> str:
    return hashlib.sha256(_war_function('CanDeclareWar') + b'\n' + _war_function('DeclareWar')).hexdigest()

def _integer(value, name: str, maximum: int=_U32_MAX) -> int:
    if type(value) is not int or value < 0 or value > maximum:
        raise ValueError(f'invalid {name}')
    return value

def _war_integer(value):
    if type(value) is not int or not -(1 << 31) <= value <= _U32_MAX:
        raise ValueError('invalid war type')
    return value

def request_source(player_id: int, expected_turn: int, own_unit_id: int, destination_plot_id: int, *, core_sha256=_WORLD_BASE_CORE_SHA256) -> bytes:
    """Build source that calls official MoveUnitToPlot and captures its request."""
    from civ6_host.runtime.xp1_world_input_profile import adapt_request_source
    verified_files()
    pid = _integer(player_id, 'player ID', _PLAYER_MAX)
    turn = _integer(expected_turn, 'game turn')
    uid = _integer(own_unit_id, 'unit ID')
    dest = _integer(destination_plot_id, 'destination plot', _PLOT_COUNT_MAX - 1)
    definitions = functions_source()
    args = b','.join((str(v).encode('ascii') for v in (pid, turn, uid, dest)))
    return adapt_request_source(b'local pid,expectedTurn,uid,destinationIndex=' + args + b"\nlocal function dec(n)\n assert(type(n)=='number' and n==math.floor(n) and n>=-2147483648 and n<=4294967295,'invalid movement receipt integer')\n return string.format('%.0f',n)\nend\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,'movement UI perspective mismatch')\nassert(Game.GetCurrentGameTurn()==expectedTurn,'movement choice is stale')\nassert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands are unavailable')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,'requested player is not ready')\nassert(type(GameInfo)=='table' and GameInfo.Units and Map and\n       type(Map.GetGridSize)=='function' and type(Map.GetPlotCount)=='function' and\n       type(Map.GetPlotByIndex)=='function' and UnitManager and\n       type(UnitManager.RequestOperation)=='function','official movement UI APIs unavailable')\nlocal width,height=Map.GetGridSize()\nlocal plotCount=Map.GetPlotCount()\nassert(type(width)=='number' and width==math.floor(width) and width>0 and width<=512 and\n       type(height)=='number' and height==math.floor(height) and height>0 and height<=512 and\n       type(plotCount)=='number' and plotCount==width*height and plotCount<=" + str(_PLOT_COUNT_MAX).encode() + b",\n       'invalid public map dimensions')\nassert(destinationIndex<plotCount,'destination outside public map dimensions')\nlocal target=Map.GetPlotByIndex(destinationIndex)\nassert(target~=nil and target:GetIndex()==destinationIndex,'destination plot index unavailable')\nlocal targetX,targetY=target:GetX(),target:GetY()\nassert(targetX==destinationIndex%width and targetY==math.floor(destinationIndex/width),\n       'destination coordinates disagree with public dimensions')\nlocal unit=nil\nlocal count=0\nlocal units=player:GetUnits()\nassert(units and type(units.Members)=='function','own unit collection unavailable')\nfor _,candidate in units:Members() do\n count=count+1; assert(count<=4096,'own unit collection exceeds bound')\n if candidate:GetID()==uid then\n   assert(unit==nil and candidate:GetOwner()==pid,'ambiguous or foreign unit identity')\n   unit=candidate\n end\nend\nassert(unit~=nil and unit:GetOwner()==pid,'requested own unit unavailable')\nlocal unitRow=GameInfo.Units[unit:GetUnitType()]\nassert(unitRow~=nil and (unitRow.IgnoreMoves==nil or type(unitRow.IgnoreMoves)=='boolean'),\n       'official IgnoreMoves metadata unavailable')\nassert(unitRow.IgnoreMoves~=true,'WorldInput does not offer movement for IgnoreMoves units')\nlocal sourcePlot=unit:GetPlotId()\nlocal sourceX,sourceY=unit:GetX(),unit:GetY()\nassert(type(sourcePlot)=='number' and sourcePlot==math.floor(sourcePlot) and sourcePlot>=0 and sourcePlot<plotCount and\n       type(sourceX)=='number' and sourceX==math.floor(sourceX) and sourceX>=0 and sourceX<width and\n       type(sourceY)=='number' and sourceY==math.floor(sourceY) and sourceY>=0 and sourceY<height and\n       sourcePlot==sourceY*width+sourceX,'own unit position is invalid')\nlocal requestCount=0\nlocal requestFields=nil\nlocal warPrompt=nil\nlocal nativeUnitManager=UnitManager\nlocal nativeRequest=nativeUnitManager.RequestOperation\nlocal UnitManager=setmetatable({RequestOperation=function(requestUnit,operation,parameters)\n requestCount=requestCount+1\n assert(requestCount==1,'official click issued more than one request')\n assert(requestUnit==unit and type(operation)=='number' and operation==math.floor(operation),\n        'invalid official operation request')\n local operationName=nil\n if operation==UnitOperationTypes.MOVE_TO then operationName='MOVE_TO'\n elseif operation==UnitOperationTypes.RANGE_ATTACK then operationName='RANGE_ATTACK'\n elseif operation==UnitOperationTypes.COASTAL_RAID then operationName='COASTAL_RAID'\n elseif operation==UnitOperationTypes.SWAP_UNITS then operationName='SWAP_UNITS'\n elseif operation==UnitOperationTypes.AIR_ATTACK then operationName='AIR_ATTACK'\n elseif operation==UnitOperationTypes.DEPLOY then operationName='DEPLOY' end\n assert(operationName~=nil and operation>=-2147483648 and operation<=4294967295,\n        'unknown official operation enum')\n local fields={}\n if parameters~=nil then\n   assert(type(parameters)=='table','official request parameters are not a table')\n   local known={[UnitOperationTypes.PARAM_X]='x',[UnitOperationTypes.PARAM_Y]='y',\n                [UnitOperationTypes.PARAM_MODIFIERS]='modifiers'}\n   for key,value in pairs(parameters) do\n     assert(type(key)=='number' and key==math.floor(key) and key>=-2147483648 and key<=4294967295 and\n            type(value)=='number' and value==math.floor(value) and value>=-2147483648 and value<=4294967295,\n            'unsupported official request parameter')\n     assert(known[key]~=nil,'unknown official request parameter key')\n     fields[#fields+1]={key=key,value=value,name=known[key]}\n     assert(#fields<=16,'official request parameter count exceeds bound')\n   end\n   table.sort(fields,function(a,b)return a.key<b.key end)\n end\n local rows={}\n for i,row in ipairs(fields) do rows[i]=row.name..':'..dec(row.key)..'='..dec(row.value) end\n requestFields={operation=operation,operationName=operationName,parameters=table.concat(rows,';')}\n return nativeRequest(requestUnit,operation,parameters)\nend},{__index=nativeUnitManager})\nlocal nativeLuaEvents=LuaEvents\nlocal LuaEvents=setmetatable({Civ6Common_ConfirmWarDialog=function(attackingPlayer,defendingPlayer,warType)\n assert(attackingPlayer==pid and type(defendingPlayer)=='number' and defendingPlayer==math.floor(defendingPlayer) and\n        defendingPlayer>=0 and defendingPlayer<=63 and defendingPlayer~=-1 and\n        type(warType)=='number' and warType==math.floor(warType) and warType>=-2147483648 and warType<=4294967295 and\n        WarTypes and warType==WarTypes.SURPRISE_WAR,\n        'invalid official war confirmation prompt')\n assert(warPrompt==nil and requestCount==0,'ambiguous official war confirmation prompt')\n warPrompt={defender=defendingPlayer,warType=warType}\nend},{__index=nativeLuaEvents})\n" + definitions + b"\nlocal function outcome(status,operation,parameters,defender,warType)\n local fields={status,dec(pid),dec(expectedTurn),dec(uid),dec(destinationIndex),dec(width),dec(height)}\n fields[#fields+1]=operation and operation.name or '-'\n fields[#fields+1]=operation and dec(operation.code) or '-'\n fields[#fields+1]=parameters or '-'\n fields[#fields+1]=defender~=nil and dec(defender) or '-'\n fields[#fields+1]=warType~=nil and dec(warType) or '-'\n fields[#fields+1]=" + b"'" + _SOURCE_HASH.encode() + b"'" + b"\n return table.concat(fields,',')\nend\nlocal ok,err=pcall(function() MoveUnitToPlot(unit,targetX,targetY) end)\nassert(ok,err)\nif warPrompt~=nil then\n assert(requestCount==0,'war prompt also issued a native request')\n return outcome('war_prompt',nil,nil,warPrompt.defender,warPrompt.warType)\nend\nif requestCount==0 then return outcome('noop',nil,nil,nil,nil) end\n return outcome('request',{name=requestFields.operationName,code=requestFields.operation},requestFields.parameters,nil,nil)\n", core_sha256)

def parse_request_result(payload: bytes, player_id: int, expected_turn: int, own_unit_id: int, destination_plot_id: int, *, core_sha256=_WORLD_BASE_CORE_SHA256) -> dict:
    from civ6_host.runtime.xp1_world_input_profile import selected_statuses
    if not isinstance(payload, bytes) or not payload or len(payload) > _LIMIT:
        raise ValueError('invalid world click result size')
    try:
        fields = payload.decode('ascii').split(',')
    except UnicodeDecodeError as exc:
        raise ValueError('world click result is not ASCII') from exc
    if len(fields) != 13 or fields[0] not in selected_statuses(_STATUS, core_sha256):
        raise ValueError('malformed world click result')
    pid = _integer(player_id, 'player ID', _PLAYER_MAX)
    turn = _integer(expected_turn, 'game turn')
    uid = _integer(own_unit_id, 'unit ID')
    dest = _integer(destination_plot_id, 'destination plot', _PLOT_COUNT_MAX - 1)
    expected = (pid, turn, uid, dest)
    actual = tuple((_parse_uint(fields[i], _U32_MAX) for i in range(1, 5)))
    if actual != expected:
        raise ValueError('world click result identity does not match request')
    width = _parse_uint(fields[5], 512)
    height = _parse_uint(fields[6], 512)
    if width < 1 or height < 1 or dest >= width * height:
        raise ValueError('invalid world click result dimensions')
    source_hash = fields[12]
    if source_hash != _SOURCE_HASH:
        raise ValueError('world click source digest changed')
    status = fields[0]
    if status == 'request':
        operation_name = fields[7]
        if operation_name not in {'MOVE_TO', 'RANGE_ATTACK', 'COASTAL_RAID', 'SWAP_UNITS', 'AIR_ATTACK', 'DEPLOY'}:
            raise ValueError('unknown native operation name')
        operation = _parse_int32(fields[8])
        params = _parse_params(fields[9])
        if fields[10] != '-' or fields[11] != '-' or (not params):
            raise ValueError('invalid native request receipt fields')
        named = {name: value for name, key, value in params}
        if set(named) != {'x', 'y', 'modifiers'} or named['x'] != dest % width or named['y'] != dest // width:
            raise ValueError('native request parameters do not target the public destination')
        return {'status': status, 'player_id': pid, 'turn': turn, 'unit_id': uid, 'destination_plot_id': dest, 'width': width, 'height': height, 'operation_name': operation_name, 'operation': operation, 'parameters': params, 'source_sha256': source_hash, 'native_callback_invoked': True}
    if fields[7] != '-' or fields[8] != '-' or fields[9] != '-':
        raise ValueError('non-request result contains operation data')
    if status == 'war_prompt':
        defender = _parse_uint(fields[10], 63)
        war_type = _parse_int32(fields[11])
        return {'status': status, 'player_id': pid, 'turn': turn, 'unit_id': uid, 'destination_plot_id': dest, 'width': width, 'height': height, 'defender_player_id': defender, 'war_type': war_type, 'source_sha256': source_hash, 'native_callback_invoked': False}
    if fields[10] != '-' or fields[11] != '-':
        raise ValueError('invalid no-op result fields')
    return {'status': status, 'player_id': pid, 'turn': turn, 'unit_id': uid, 'destination_plot_id': dest, 'width': width, 'height': height, 'source_sha256': source_hash, 'native_callback_invoked': False}

def war_response_source(player_id: int, expected_turn: int, defender_player_id: int, war_type: int, accept: bool) -> bytes:
    """Build an explicit decline or official surprise-war confirmation request."""
    verified_files()
    if type(accept) is not bool:
        raise ValueError('accept must be an explicit Boolean')
    pid = _integer(player_id, 'player ID', _PLAYER_MAX)
    turn = _integer(expected_turn, 'game turn')
    defender = _integer(defender_player_id, 'defender player ID', _PLAYER_MAX)
    war = _war_integer(war_type)
    if defender == pid:
        raise ValueError('war defender must differ from attacker')
    popup_hash = _war_source_hash()
    definitions = _war_function('CanDeclareWar') + b'\n' + _war_function('DeclareWar')
    return b'local pid,expectedTurn,defender,warType,accept=' + b','.join((str(pid).encode(), str(turn).encode(), str(defender).encode(), str(war).encode(), b'true' if accept else b'false')) + b"\nlocal function dec(n)\n assert(type(n)=='number' and n==math.floor(n) and n>=-2147483648 and n<=4294967295,'invalid war receipt integer')\n return string.format('%.0f',n)\nend\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n       Game.GetCurrentGameTurn()==expectedTurn and Game.IsAllowStrategicCommands(pid)==true,\n       'war response perspective or turn changed')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,'requested player is not ready')\nassert(WarTypes and warType==WarTypes.SURPRISE_WAR,'only the official surprise-war prompt is supported')\nlocal nativeDiplomacy=DiplomacyManager\nlocal sessionCount=0\nlocal sessionName=nil\nlocal DiplomacyManager=setmetatable({RequestSession=function(attacker,target,session)\n assert(sessionCount==0 and attacker==pid and target==defender and\n        session=='DECLARE_SURPRISE_WAR','unexpected official diplomacy session request')\n sessionCount=sessionCount+1;sessionName=session\n return nativeDiplomacy.RequestSession(attacker,target,session)\nend},{__index=nativeDiplomacy})\n" + definitions + b"\nif not accept then\n return table.concat({'declined',dec(pid),dec(expectedTurn),dec(defender),dec(warType),'-','-', " + b"'" + popup_hash.encode() + b"'" + b"},',')\nend\nlocal isMajor=CanDeclareWar(defender)\nassert(type(isMajor)=='boolean','official war target classification unavailable')\nif not isMajor then\n return table.concat({'minor_route',dec(pid),dec(expectedTurn),dec(defender),dec(warType),'-','-', " + b"'" + popup_hash.encode() + b"'" + b"},',')\nend\nassert(nativeDiplomacy and type(nativeDiplomacy.RequestSession)=='function',\n       'official DiplomacyManager.RequestSession is unavailable')\nDeclareWar(pid,defender,warType)\nassert(sessionCount==1 and sessionName=='DECLARE_SURPRISE_WAR',\n       'official surprise-war session callback was not invoked exactly once')\nreturn table.concat({'session_request',dec(pid),dec(expectedTurn),dec(defender),dec(warType),\n                     sessionName,'+', " + b"'" + popup_hash.encode() + b"'" + b"},',')\n"

def parse_war_response_result(payload: bytes, player_id: int, expected_turn: int, defender_player_id: int, war_type: int, accept: bool) -> dict:
    if type(accept) is not bool or not isinstance(payload, bytes) or (not payload) or (len(payload) > _LIMIT):
        raise ValueError('invalid war response result')
    try:
        fields = payload.decode('ascii').split(',')
    except UnicodeDecodeError as exc:
        raise ValueError('war response result is not ASCII') from exc
    if len(fields) != 8 or fields[0] not in {'declined', 'session_request', 'minor_route'}:
        raise ValueError('malformed war response result')
    expected = (_integer(player_id, 'player ID', _PLAYER_MAX), _integer(expected_turn, 'game turn'), _integer(defender_player_id, 'defender player ID', _PLAYER_MAX), _war_integer(war_type))
    actual = tuple((_parse_uint(fields[i], _U32_MAX) for i in range(1, 4))) + (_parse_int32(fields[4]),)
    if actual != expected or expected[0] == expected[2]:
        raise ValueError('war response identity mismatch')
    if fields[7] != _war_source_hash():
        raise ValueError('war popup source digest changed')
    if accept and fields[0] == 'minor_route':
        if fields[5] != '-' or fields[6] != '-':
            raise ValueError('minor war route unexpectedly issued native request')
        return {'status': 'minor_route', 'player_id': expected[0], 'turn': expected[1], 'defender_player_id': expected[2], 'war_type': expected[3], 'native_callback_invoked': False, 'source_sha256': fields[7]}
    if accept:
        if fields[0] != 'session_request' or fields[5] != 'DECLARE_SURPRISE_WAR' or fields[6] != '+':
            raise ValueError('accepted war response lacks the official session request')
        return {'status': 'session_request', 'player_id': expected[0], 'turn': expected[1], 'defender_player_id': expected[2], 'war_type': expected[3], 'session': 'DECLARE_SURPRISE_WAR', 'native_callback_invoked': True, 'source_sha256': fields[7]}
    if fields[0] != 'declined' or fields[5] != '-' or fields[6] != '-':
        raise ValueError('declined war response unexpectedly issued a native call')
    return {'status': 'declined', 'player_id': expected[0], 'turn': expected[1], 'defender_player_id': expected[2], 'war_type': expected[3], 'native_callback_invoked': False, 'source_sha256': fields[7]}

def _parse_uint(text: str, maximum: int) -> int:
    if not text or not text.isascii() or (not text.isdecimal()) or (len(text) > 1 and text[0] == '0'):
        raise ValueError('invalid unsigned integer in world click result')
    value = int(text)
    if value > maximum:
        raise ValueError('world click integer exceeds bound')
    return value

def _parse_int32(text: str) -> int:
    if not text or not text.isascii() or (not re.fullmatch('(?:0|[1-9][0-9]*|-[1-9][0-9]*)', text)):
        raise ValueError('invalid signed integer in world click result')
    value = int(text)
    if value < -2147483648 or value > 4294967295:
        raise ValueError('world click integer exceeds 32-bit native enum bounds')
    return value

def _parse_params(text: str) -> tuple[tuple[str, int, int], ...]:
    if not text or len(text) > 512:
        raise ValueError('invalid request parameter list')
    result = []
    previous = None
    names = {'x', 'y', 'modifiers'}
    seen_names = set()
    for pair in text.split(';'):
        named, sep, value_text = pair.partition('=')
        name, colon, key_text = named.partition(':')
        if not sep or not colon or name not in names or (name in seen_names):
            raise ValueError('invalid request parameter pair')
        key = _parse_int32(key_text)
        value = _parse_int32(value_text)
        if previous is not None and key <= previous:
            raise ValueError('request parameter keys are not unique and sorted')
        previous = key
        seen_names.add(name)
        result.append((name, key, value))
        if len(result) > 16:
            raise ValueError('too many request parameters')
    return tuple(result)

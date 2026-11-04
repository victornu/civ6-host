"""Public, native-legal Great Prophet activation with separate effect readback.

This operation activates/consumes the unit and stores a founding-site
descriptor. It does not found or select a named religion.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_prophet_activation.py')))).resolve().parents[1]
PROOF_SHA256 = 'c5f6dd96698059bf7fc4b8c4bf765d4876857f1963d1772657c67866f32609e0'
PROOF = ROOT / 'evidence/native-religion-founding-actions' / f'{PROOF_SHA256}.json'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
OPERATION_HASH = 3341805819
MAX_UNITS = 4096
MAX_WIRE = 65536
UI_ROOT = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
GAMEPLAY_SCHEMA = UI_ROOT.parent / 'Gameplay/Data/Schema/01_GameplaySchema.sql'
GAMEPLAY_SCHEMA_SHA256 = 'd56906e7f67c09193b431843432bc21d62e86c32f3f46c14eae9dedbe69084e0'
UI_PINS = {UI_ROOT / 'Panels/UnitPanel.lua': '6d029bfa8f7119c18ee88956ef775f7d05a57aae9d2ffe3be60c256c7a8d5b6e', UI_ROOT.parent / 'Gameplay/Data/UnitOperations.xml': '00c3c77e74f571471299564c4f6c1a277c9f09d650420dbb01314c27ba8b698f', UI_ROOT.parent / 'Gameplay/Data/Units.xml': 'f7d9d5e7658c6024e131722d957ad13b9665b34a7ffdb374b095a502bc3a6ebe', GAMEPLAY_SCHEMA: GAMEPLAY_SCHEMA_SHA256}

def verify_source() -> None:
    proof = load_pinned_json(PROOF, PROOF_SHA256)
    operation = proof.get('unit_operation', {})
    if proof.get('schema') != 'civ6rl.native_religion_founding_actions.static.v1' or proof.get('exe_sha256') != EXE_SHA256 or proof.get('core_sha256') != CORE_SHA256 or (operation.get('type') != 'UNITOPERATION_FOUND_RELIGION') or (operation.get('hash_u32') != '0xc72fe8fb') or (operation.get('signed_hash') != -953161477) or ('UnitManager.RequestOperation(ownedUnit, operationRow.Hash)' not in operation.get('request', '')):
        raise RuntimeError('Pinned prophet activation proof changed')
    for path, expected in UI_PINS.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Installed source changed: {path.name}')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _s32(value: int, label: str) -> int:
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError(f'Invalid {label}')
    return value

def _parse_uint(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((c < 48 or c > 57 for c in token)) or (len(token) > 1 and token[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'Out-of-range {label}')
    return value

def _parse_s32(token: bytes, label: str) -> int:
    if not token or token.startswith(b'+') or token == b'-0':
        raise ValueError(f'Invalid {label}')
    digits = token[1:] if token.startswith(b'-') else token
    if not digits or any((c < 48 or c > 57 for c in digits)) or (len(digits) > 1 and digits.startswith(b'0')):
        raise ValueError(f'Invalid {label}')
    return _s32(int(token), label)

def _prefix(player_id: int, turn: int) -> bytes:
    pid, expected_turn = (_uint(player_id, 'player ID', 63), _uint(turn, 'game turn'))
    verify_source()
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(expected_turn).encode() + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n 'prophet player perspective mismatch')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n 'prophet observer mismatch')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n 'prophet decision is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and\n Game.IsAllowStrategicCommands(pid)==true,'strategic commands are not allowed')\nlocal player=Players and Players[pid]\nassert(player and type(player.GetID)=='function' and player:GetID()==pid and\n player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'prophet player is not ready')\nlocal op=GameInfo and GameInfo.UnitOperations and\n GameInfo.UnitOperations['UNITOPERATION_FOUND_RELIGION']\nlocal prophet=GameInfo and GameInfo.Units and GameInfo.Units['UNIT_GREAT_PROPHET']\nassert(op and op.OperationType=='UNITOPERATION_FOUND_RELIGION' and type(op.Hash)=='number' and\n op.Hash==math.floor(op.Hash),'native founding operation unavailable')\nassert(prophet and prophet.UnitType=='UNIT_GREAT_PROPHET' and\n type(prophet.Index)=='number' and prophet.Index==math.floor(prophet.Index) and\n prophet.Index>=0 and prophet.Index<=2147483647,\n 'native prophet definition unavailable')\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function',\n 'native UnitManager legality API unavailable')\nlocal opbits=op.Hash<0 and op.Hash+4294967296 or op.Hash\nassert(opbits==3341805819,'founding operation hash differs from pinned source')\nlocal function context()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n  Game.GetCurrentGameTurn()==expectedTurn,'prophet context changed')\n local current=Players and Players[pid]\n assert(Game.IsAllowStrategicCommands(pid)==true and current and\n  type(current.GetID)=='function' and current:GetID()==pid and player:GetID()==pid and\n  player:IsAlive()==true and player:IsTurnActive()==true and\n  player:IsTurnActiveComplete()==true,'prophet player no longer ready')\nend\nlocal function units()\n local result,seen={},{}\n local collection=player:GetUnits()\n assert(collection and type(collection.Members)=='function','own units unavailable')\n local count=0\n for _,u in collection:Members() do\n  count=count+1; assert(count<=" + str(MAX_UNITS).encode() + b",'own units exceed bound')\n  assert(u and type(u.GetOwner)=='function' and type(u.GetID)=='function' and\n   type(u.GetType)=='function','invalid own unit')\n  assert(u:GetOwner()==pid,'foreign unit in own roster')\n  local id=u:GetID()\n  assert(type(id)=='number' and id==math.floor(id) and id>=0 and id<=4294967295,\n   'invalid own unit ID')\n  assert(not seen[id],'duplicate own unit ID')\n  seen[id]=true; result[id]=u\n end\n return result\nend\ncontext()\n"

def catalog_source(player_id: int, expected_turn: int) -> bytes:
    return _prefix(player_id, expected_turn) + b"\nlocal found,seen={},{}\nfor id,u in pairs(units()) do\n if u:GetType()==prophet.Index then\n  local moves=u:GetMovesRemaining()\n  assert(type(moves)=='number' and moves==math.floor(moves),'invalid prophet moves')\n  if moves>0 and UnitManager.CanStartOperation(u,op.Hash,nil,false)==true then\n   local x,y=u:GetX(),u:GetY()\n   assert(type(x)=='number' and x==math.floor(x) and x>=-2147483648 and x<2147483648 and\n    type(y)=='number' and y==math.floor(y) and y>=-2147483648 and y<2147483648,\n    'invalid prophet location')\n   assert(not seen[id],'duplicate eligible prophet')\n   seen[id]=true;found[#found+1]={id=id,x=x,y=y}\n  end\n end\nend\ntable.sort(found,function(a,b) return a.id<b.id end)\ncontext()\nlocal function d(n) return string.format('%.0f',n) end\nlocal out={'catalog',d(pid),d(expectedTurn),d(opbits),d(prophet.Index),d(#found)}\nfor _,v in ipairs(found) do out[#out+1]=d(v.id)..':'..d(v.x)..':'..d(v.y) end\nreturn table.concat(out,',')\n"

def parse_catalog(payload: bytes, player_id: int, expected_turn: int) -> dict:
    pid, turn = (_uint(player_id, 'player ID', 63), _uint(expected_turn, 'game turn'))
    if type(payload) is not bytes or len(payload) > MAX_WIRE:
        raise ValueError('Invalid prophet catalog')
    fields = payload.split(b',')
    if len(fields) < 6 or fields[0] != b'catalog':
        raise ValueError('Malformed prophet catalog')
    actual = (_parse_uint(fields[1], 'player ID', 63), _parse_uint(fields[2], 'turn'), _parse_uint(fields[3], 'operation'), _parse_uint(fields[4], 'prophet type', 2147483647))
    count = _parse_uint(fields[5], 'candidate count', MAX_UNITS)
    if actual != (pid, turn, OPERATION_HASH, actual[3]) or count != len(fields) - 6:
        raise ValueError('Stale, mismatched, or malformed prophet catalog')
    choices, previous = ([], -1)
    for field in fields[6:]:
        parts = field.split(b':')
        if len(parts) != 3:
            raise ValueError('Malformed prophet candidate')
        uid = _parse_uint(parts[0], 'unit ID')
        x, y = (_parse_s32(parts[1], 'x'), _parse_s32(parts[2], 'y'))
        if uid <= previous:
            raise ValueError('Prophet candidates are duplicated or unordered')
        previous = uid
        choices.append({'unit_id': uid, 'x': x, 'y': y})
    return {'status': 'catalog' if count else 'not_due', 'player_id': pid, 'current_game_turn': turn, 'operation': OPERATION_HASH, 'prophet_type_index': actual[3], 'candidates': tuple(choices)}

def choose(catalog: dict, unit_id: int) -> dict:
    keys = {'status', 'player_id', 'current_game_turn', 'operation', 'prophet_type_index', 'candidates'}
    if type(catalog) is not dict or set(catalog) != keys or catalog.get('status') != 'catalog':
        raise ValueError('No eligible prophet catalog')
    pid = _uint(catalog['player_id'], 'player ID', 63)
    turn = _uint(catalog['current_game_turn'], 'turn')
    if _uint(catalog['operation'], 'operation') != OPERATION_HASH:
        raise ValueError('Unexpected operation')
    index = _uint(catalog['prophet_type_index'], 'prophet type index', 2147483647)
    entries = catalog['candidates']
    if type(entries) is not tuple or not 0 < len(entries) <= MAX_UNITS:
        raise ValueError('Invalid prophet candidate list')
    previous = -1
    for entry in entries:
        if type(entry) is not dict or set(entry) != {'unit_id', 'x', 'y'}:
            raise ValueError('Malformed prophet candidate')
        uid = _uint(entry['unit_id'], 'unit ID')
        _s32(entry['x'], 'x')
        _s32(entry['y'], 'y')
        if uid <= previous:
            raise ValueError('Unordered or duplicate prophet candidates')
        previous = uid
    selected = _uint(unit_id, 'selected unit ID')
    matches = [entry for entry in entries if entry['unit_id'] == selected]
    if len(matches) != 1:
        raise ValueError('Selected prophet is absent or ambiguous')
    return {'player_id': pid, 'current_game_turn': turn, 'operation': OPERATION_HASH, 'prophet_type_index': index, 'unit_id': selected, 'x': matches[0]['x'], 'y': matches[0]['y']}

def _validate_choice(choice: dict) -> None:
    keys = {'player_id', 'current_game_turn', 'operation', 'prophet_type_index', 'unit_id', 'x', 'y'}
    if type(choice) is not dict or set(choice) != keys:
        raise ValueError('Malformed prophet choice')
    _uint(choice['player_id'], 'player ID', 63)
    _uint(choice['current_game_turn'], 'turn')
    if _uint(choice['operation'], 'operation') != OPERATION_HASH:
        raise ValueError('Unexpected operation')
    _uint(choice['prophet_type_index'], 'prophet type index', 2147483647)
    _uint(choice['unit_id'], 'unit ID')
    _s32(choice['x'], 'x')
    _s32(choice['y'], 'y')

def _choice_source(choice: dict, submit: bool) -> bytes:
    _validate_choice(choice)
    prefix = _prefix(choice['player_id'], choice['current_game_turn'])
    vals = (choice['unit_id'], choice['prophet_type_index'], choice['x'], choice['y'])
    source = b'local uid,expectedType,expectedX,expectedY=' + b','.join((str(v).encode() for v in vals)) + b"\nlocal own=units()\nlocal u=own[uid]\nassert(expectedType==prophet.Index and u~=nil and u:GetType()==expectedType and\n u:GetX()==expectedX and u:GetY()==expectedY,\n 'selected prophet identity/location changed')\nlocal moves=u:GetMovesRemaining()\nassert(type(moves)=='number' and moves==math.floor(moves) and moves>0,\n 'selected prophet has no movement')\nassert(UnitManager.CanStartOperation(u,op.Hash,nil,false)==true,\n 'native founding legality rejected action')\ncontext()\n"
    if submit:
        source += b"assert(type(UnitManager.RequestOperation)=='function',\n 'native UnitManager request API unavailable')\nUnitManager.RequestOperation(u,op.Hash)\nlocal status='submitted'\n"
    else:
        source += b"local status='valid'\n"
    return prefix + source + b"local function d(n) return string.format('%.0f',n) end\nreturn table.concat({status,d(pid),d(expectedTurn),d(uid),d(expectedX),d(expectedY),d(opbits)},',')\n"

def revalidate_source(choice: dict) -> bytes:
    return _choice_source(choice, False)

def request_source(choice: dict) -> bytes:
    return _choice_source(choice, True)

def _parse_choice_result(payload: bytes, choice: dict, expected_status: bytes) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 256:
        raise ValueError('Invalid prophet response')
    fields = payload.split(b',')
    if len(fields) != 7 or fields[0] != expected_status:
        raise ValueError('Malformed prophet response')
    actual = (_parse_uint(fields[1], 'player'), _parse_uint(fields[2], 'turn'), _parse_uint(fields[3], 'unit'), _parse_s32(fields[4], 'x'), _parse_s32(fields[5], 'y'), _parse_uint(fields[6], 'operation'))
    expected = (choice['player_id'], choice['current_game_turn'], choice['unit_id'], choice['x'], choice['y'], OPERATION_HASH)
    if actual != expected:
        raise ValueError('Prophet response differs from selected choice')
    return {'status': expected_status.decode('ascii'), 'choice': choice, 'request_submitted': expected_status == b'submitted', 'effect_verified': False}

def parse_revalidated(payload: bytes, choice: dict) -> dict:
    return _parse_choice_result(payload, choice, b'valid')

def parse_request(payload: bytes, choice: dict) -> dict:
    return _parse_choice_result(payload, choice, b'submitted')

def effect_source(choice: dict, before: dict) -> bytes:
    _validate_choice(choice)
    required = {'player_id', 'current_game_turn', 'holy_city', 'num_beliefs_earned', 'has_religious_founding_unit', 'religion_type_created'}
    if type(before) is not dict or not required <= set(before):
        raise ValueError('Missing pre-activation religion snapshot')
    if before['player_id'] != choice['player_id'] or before['current_game_turn'] != choice['current_game_turn']:
        raise ValueError('Stale or foreign pre-activation snapshot')
    old = before['holy_city']
    if type(old) is not dict or set(old) != {'player', 'type', 'id'}:
        raise ValueError('Malformed prior site descriptor')
    old_owner, old_type, old_id = (_s32(old[k], f'prior site {k}') for k in ('player', 'type', 'id'))
    old_earned = _uint(before['num_beliefs_earned'], 'prior earned beliefs', 2147483647)
    if before['has_religious_founding_unit'] is not True or before['religion_type_created'] != -1 or (old_owner, old_type, old_id) != (-1, 2, -1):
        raise ValueError('Snapshot is not an unactivated Great Prophet state')
    prefix = _prefix(choice['player_id'], choice['current_game_turn'])
    source = b'local uid,oldOwner,oldType,oldID,oldEarned=' + b','.join((str(v).encode() for v in (choice['unit_id'], old_owner, old_type, old_id, old_earned))) + b"\nassert(units()[uid]==nil,'prophet remains; activation not verified')\nassert(type(player.GetCities)=='function' and type(player.GetReligion)=='function',\n 'activation readback unavailable')\nlocal cities,collection={},player:GetCities()\nassert(collection and type(collection.Members)=='function','own cities unavailable')\nlocal count=0\nfor _,c in collection:Members() do\n count=count+1;assert(count<=256,'own city collection exceeds bound')\n assert(c:GetOwner()==pid,'foreign city in own collection')\n local id=c:GetID()\n assert(type(id)=='number' and id==math.floor(id) and id>=0 and id<=2147483647,\n  'invalid own city ID')\n assert(cities[id]==nil,'duplicate own city ID');cities[id]=true\nend\nlocal religion=player:GetReligion()\nassert(religion and type(religion.GetHolyCityID)=='function' and\n type(religion.GetNumBeliefsEarned)=='function','religion readback unavailable')\nlocal site=religion:GetHolyCityID()\nassert(type(site)=='table','founding site unavailable')\nlocal owner,kind,id=site.player,site.type,site.id\nassert(type(owner)=='number' and owner==math.floor(owner) and\n type(kind)=='number' and kind==math.floor(kind) and\n type(id)=='number' and id==math.floor(id),'malformed founding site')\nassert(owner==pid and kind==2 and id>=0 and cities[id]==true,\n 'founding site is not a current own city')\nassert(not (owner==oldOwner and kind==oldType and id==oldID),\n 'founding-site descriptor did not change')\nlocal earned=religion:GetNumBeliefsEarned()\nassert(type(earned)=='number' and earned==math.floor(earned) and\n earned>=0 and earned<=2147483647,'invalid earned-belief count')\ncontext()\nlocal function d(n) return string.format('%.0f',n) end\nreturn table.concat({'effect',d(pid),d(expectedTurn),d(uid),d(owner),d(kind),d(id),\n d(oldEarned),d(earned)},',')\n"
    return prefix + source

def parse_effect(payload: bytes, choice: dict, before: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 512:
        raise ValueError('Invalid prophet effect response')
    fields = payload.split(b',')
    if len(fields) != 9 or fields[0] != b'effect':
        raise ValueError('Malformed prophet effect response')
    vals = tuple((_parse_uint(x, 'effect value') for x in fields[1:]))
    if vals[:3] != (choice['player_id'], choice['current_game_turn'], choice['unit_id']):
        raise ValueError('Stale or mismatched prophet effect')
    if type(before) is not dict or before.get('player_id') != choice['player_id'] or before.get('current_game_turn') != choice['current_game_turn'] or (before.get('has_religious_founding_unit') is not True) or (before.get('religion_type_created') != -1):
        raise ValueError('Stale or non-activation precondition snapshot')
    old = before.get('holy_city', {})
    old_tuple = (old.get('player'), old.get('type'), old.get('id'))
    earned_before = before.get('num_beliefs_earned') if type(before) is dict else None
    if any((type(v) is not int for v in (*old_tuple, earned_before))):
        raise ValueError('Malformed pre-activation snapshot')
    if old_tuple != (-1, 2, -1):
        raise ValueError('Prior founding-site descriptor is not empty')
    if vals[6] != earned_before:
        raise ValueError('Prophet effect has different prior earned-belief count')
    owner, kind, city_id, earned_after = (vals[3], vals[4], vals[5], vals[7])
    if owner != choice['player_id'] or kind != 2 or city_id > 2147483647 or ((owner, kind, city_id) == old_tuple) or (earned_after > 2147483647):
        raise ValueError('No new own founding-site effect was observed')
    return {'activation_verified': True, 'unit_consumed': True, 'founding_site': {'player': owner, 'type': kind, 'id': city_id}, 'beliefs_earned_before': earned_before, 'beliefs_earned_after': earned_after, 'named_religion_founded': False, 'religion_creation_verified': False, 'source_proof_sha256': PROOF_SHA256}

def guard_case() -> bytes:
    """Exercise actual generated chunks without exposing or changing native state."""
    catalog = parse_catalog(b'catalog,0,50,3341805819,6,1,17:8:9', 0, 50)
    choice = choose(catalog, 17)
    before = {'player_id': 0, 'current_game_turn': 50, 'holy_city': {'player': -1, 'type': 2, 'id': -1}, 'num_beliefs_earned': 0, 'has_religious_founding_unit': True, 'religion_type_created': -1}
    chunks = b'\n'.join((b'local function ' + name + b'()\n' + source + b'\nend' for name, source in ((b'catalog', catalog_source(0, 50)), (b'revalidate', revalidate_source(choice)), (b'request', request_source(choice)), (b'effect', effect_source(choice, before)))))
    return b"local saved={Game=Game,Players=Players,GameInfo=GameInfo,UnitManager=UnitManager}\nlocal ok,result=pcall(function()\n local S={pid=0,observer=0,turn=50,strategic=true,alive=true,active=true,complete=true,\n  owner=0,id=17,kind=6,x=8,y=9,moves=2,legal=true,present=true,requests=0,\n  cityOwner=0,cityID=99,siteOwner=0,siteType=2,siteID=99,earned=2,playerID=0}\n Game={GetLocalPlayer=function() return S.pid end,GetLocalObserver=function() return S.observer end,\n  GetCurrentGameTurn=function() return S.turn end,\n  IsAllowStrategicCommands=function(pid) assert(pid==0);return S.strategic end}\n GameInfo={UnitOperations={UNITOPERATION_FOUND_RELIGION={OperationType='UNITOPERATION_FOUND_RELIGION',Hash=-953161477}},\n  Units={UNIT_GREAT_PROPHET={UnitType='UNIT_GREAT_PROPHET',Index=6}}}\n local unit={GetOwner=function() return S.owner end,GetID=function() return S.id end,\n  GetType=function() return S.kind end,GetX=function() return S.x end,GetY=function() return S.y end,\n  GetMovesRemaining=function() return S.moves end}\n local city={GetOwner=function() return S.cityOwner end,GetID=function() return S.cityID end}\n local function members(obj,present) local n=0;return function()\n  n=n+1;if n==1 and present then return 1,obj end end end\n local religion={GetHolyCityID=function() return {player=S.siteOwner,type=S.siteType,id=S.siteID} end,\n  GetNumBeliefsEarned=function() return S.earned end}\n local player={GetID=function() return S.playerID end,IsAlive=function() return S.alive end,\n  IsTurnActive=function() return S.active end,IsTurnActiveComplete=function() return S.complete end,\n  GetUnits=function() return {Members=function() return members(unit,S.present) end} end,\n  GetCities=function() return {Members=function() return members(city,true) end} end,\n  GetReligion=function() local fresh={};for k,v in pairs(religion) do fresh[k]=v end;return fresh end}\n Players=setmetatable({},{__index=function(_,pid)\n  assert(pid==0);local fresh={};for k,v in pairs(player) do fresh[k]=v end;return fresh end})\n UnitManager={CanStartOperation=function(u,hash,args,visible)\n  assert(u==unit and hash==-953161477 and args==nil and visible==false);return S.legal end,\n  RequestOperation=function(u,hash) assert(u==unit and hash==-953161477);S.requests=S.requests+1 end}\n" + chunks + b"\n assert(GameInfo.UnitOperations.UNITOPERATION_FOUND_RELIGION.Type==nil,\n  'UnitOperations must use its actual schema rather than a Types row')\n assert(catalog()=='catalog,0,50,3341805819,6,1,17:8:9')\n assert(revalidate()=='valid,0,50,17,8,9,3341805819')\n assert(request()=='submitted,0,50,17,8,9,3341805819' and S.requests==1)\n S.present=false;assert(effect()=='effect,0,50,17,0,2,99,0,2');S.present=true\n assert(not pcall(effect),'consumed prophet must be absent')\n local cases={{'pid',1},{'observer',1},{'turn',51},{'strategic',false},{'alive',false},\n  {'active',false},{'complete',false},{'playerID',1},{'owner',1}}\n for _,case in ipairs(cases) do local key,value=case[1],case[2];local old=S[key];S[key]=value\n  assert(not pcall(catalog) and not pcall(revalidate) and not pcall(request) and not pcall(effect),key)\n  S[key]=old\n end\n for _,case in ipairs({{'id',18},{'kind',7},{'x',9},{'y',10},{'moves',0},{'legal',false},{'present',false}}) do\n  local key,value=case[1],case[2];local old=S[key];S[key]=value\n  assert(not pcall(revalidate) and not pcall(request),key);S[key]=old\n end\n S.moves=0;assert(catalog()=='catalog,0,50,3341805819,6,0');S.moves=2\n S.legal=false;assert(catalog()=='catalog,0,50,3341805819,6,0');S.legal=true\n S.present=false\n for _,case in ipairs({{'cityOwner',1},{'siteOwner',1},{'siteType',1},{'siteID',100},{'earned',-1}}) do\n  local key,value=case[1],case[2];local old=S[key];S[key]=value\n  assert(not pcall(effect),key);S[key]=old\n end\n S.present=true\n local definition=GameInfo.UnitOperations.UNITOPERATION_FOUND_RELIGION\n for _,case in ipairs({{'OperationType',nil},{'OperationType','UNITOPERATION_FOUND_CITY'},\n  {'Hash',nil},{'Hash','-953161477'},{'Hash',false},{'Hash',0},{'Hash',-953161476.5}}) do\n  local key,value=case[1],case[2];local old=definition[key];definition[key]=value\n  definition.Type='UNITOPERATION_FOUND_RELIGION'\n  assert(not pcall(catalog) and not pcall(revalidate) and not pcall(request),key)\n  definition[key]=old;definition.Type=nil\n end\n GameInfo.Units.UNIT_GREAT_PROPHET.Index=7\n assert(not pcall(revalidate) and not pcall(request),'changed prophet definition')\n assert(S.requests==1,'rejected request leaked a mutation')\n return 'prophet-activation-guards-ok'\nend)\nGame,Players,GameInfo,UnitManager=saved.Game,saved.Players,saved.GameInfo,saved.UnitManager\nassert(ok,result)\nreturn result\n"
__all__ = ['PROOF_SHA256', 'verify_source', 'guard_case', 'catalog_source', 'parse_catalog', 'choose', 'revalidate_source', 'parse_revalidated', 'request_source', 'parse_request', 'effect_source', 'parse_effect']

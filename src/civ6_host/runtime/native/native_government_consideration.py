"""Explicitly mark the current government as considered for one blocker.

This is not a government selection/change. It invokes the native consideration
setter only for the currently active local player when the exact end-turn
blocker is present, then verifies the actual getter. No request archive or
gameplay effect is inferred from the setter's void return.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_government_consideration.py')))).resolve().parents[1]
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_UI_PATH = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\Screens\\GovernmentScreen.lua"))
_UI_SHA256 = '6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'
_BLOCKER_VALUE = 1472003650
_MAX_BLOCKERS = 128
_MAX_RESPONSE = 256
PINNED_EVIDENCE_SHA256 = '47c931dfceda95006c40373234f41bc0b0a5fb93084ddee13eee84d8be897c86'
_PROOF = _ROOT / 'evidence/native-government-consideration' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source() -> None:
    if PINNED_EVIDENCE_SHA256 == 'PENDING':
        raise RuntimeError('Government consideration source proof is not pinned yet')
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if _UI_SHA256 != hashlib.sha256(_resolve_resource_path(_UI_PATH).read_bytes()).hexdigest() or proof.get('schema') != 'civ6rl.native_government_consideration.static.v1' or proof.get('core_sha256') != _CORE_SHA256 or (proof.get('exe_sha256') != _EXE_SHA256) or (proof.get('enum', {}).get('name', {}).get('text') != 'ENDTURN_BLOCKING_CONSIDER_GOVERNMENT_CHANGE') or (proof.get('enum', {}).get('signed32_value') != _BLOCKER_VALUE) or (proof.get('bindings', {}).get('SetGovernmentChangeConsidered', {}).get('callback_va') != '0x1805357e0') or (proof.get('bindings', {}).get('GovernmentChangeConsidered', {}).get('callback_va') != '0x180534c20') or (proof.get('bindings', {}).get('GetCurrentGovernment', {}).get('callback_va') != '0x180533f60'):
        raise RuntimeError('Pinned Government consideration source identity changed')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _player_id(value: int) -> int:
    return _uint(value, 'player ID', 63)

def _turn(value: int) -> int:
    return _uint(value, 'game turn', 100000)

def _government(value: int) -> int:
    if type(value) is not int or not -1 <= value <= 2147483647:
        raise ValueError('Invalid current government index')
    return value

def _common_source(player_id: int, expected_turn: int, expected_government: int | None=None) -> bytes:
    pid, turn = (_player_id(player_id), _turn(expected_turn))
    gov = None if expected_government is None else _government(expected_government)
    gov_arg = b'nil' if gov is None else str(gov).encode('ascii')
    return b'local pid,expectedTurn,expectedGovernment=' + str(pid).encode() + b',' + str(turn).encode() + b',' + gov_arg + b'\nlocal blockerValue=' + str(_BLOCKER_VALUE).encode() + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n 'government consideration perspective mismatch')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n 'government consideration observer mismatch')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n 'government consideration turn is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and Game.IsAllowStrategicCommands(pid)==true,\n 'strategic commands are not allowed')\nlocal player=Players and Players[pid]\nassert(player and type(player.IsAlive)=='function' and player:IsAlive()==true and\n type(player.IsTurnActive)=='function' and player:IsTurnActive()==true and\n type(player.IsTurnActiveComplete)=='function' and player:IsTurnActiveComplete()==true,\n 'government consideration player is not ready')\nlocal culture=player:GetCulture()\nassert(culture and type(culture.GetCurrentGovernment)=='function' and\n type(culture.GovernmentChangeConsidered)=='function' and\n type(culture.SetGovernmentChangeConsidered)=='function',\n 'government consideration Culture API unavailable')\nassert(NotificationManager and type(NotificationManager.GetAllEndTurnBlocking)=='function' and\n EndTurnBlockingTypes and EndTurnBlockingTypes.ENDTURN_BLOCKING_CONSIDER_GOVERNMENT_CHANGE==blockerValue,\n 'native government blocker API/value unavailable')\nlocal function currentGovernment()\n local value=culture:GetCurrentGovernment()\n assert(type(value)=='number' and value==math.floor(value) and\n value>=-1 and value<=2147483647,'invalid current-government index')\n return value\nend\nlocal function considered()\n local value=culture:GovernmentChangeConsidered()\n assert(type(value)=='boolean','invalid GovernmentChangeConsidered result')\n return value\nend\nlocal function blockerPresent()\n local all=NotificationManager.GetAllEndTurnBlocking(pid)\n assert(type(all)=='table' and #all<=" + str(_MAX_BLOCKERS).encode() + b",\n 'invalid/bounded end-turn blocker list required')\n local found=false\n for _,value in ipairs(all) do\n  assert(type(value)=='number' and value==math.floor(value),'invalid blocker value')\n  if value==blockerValue then found=true end\n end\n return found\nend\nlocal function assertContext()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n  Game.GetCurrentGameTurn()==expectedTurn and Game.IsAllowStrategicCommands(pid)==true,\n  'government consideration context changed')\n assert(player:IsAlive()==true and player:IsTurnActive()==true and\n  player:IsTurnActiveComplete()==true,'government consideration readiness changed')\nend\nassertContext()\nlocal gov=currentGovernment()\nlocal wasConsidered=considered()\nlocal hasBlocker=blockerPresent()\nassertContext()\nassert(currentGovernment()==gov and considered()==wasConsidered,\n 'government consideration state changed while reading')\nif expectedGovernment~=nil then\n assert(gov==expectedGovernment,'current government differs from snapshot')\nend\n"

def readback_source(player_id: int, expected_turn: int) -> bytes:
    """Read current local government state and presence of the exact blocker."""
    verify_source()
    return _common_source(player_id, expected_turn) + b"\nlocal function dec(n) return string.format('%.0f',n) end\nreturn table.concat({'readback',dec(pid),dec(expectedTurn),dec(gov),\n wasConsidered and '1' or '0',hasBlocker and '1' or '0'},'|')\n"

def _parse_response(payload: bytes, label: str) -> list[bytes]:
    if type(payload) is not bytes or len(payload) > _MAX_RESPONSE:
        raise ValueError(f'Invalid {label} response')
    try:
        fields = payload.decode('ascii').split('|')
    except UnicodeDecodeError as exc:
        raise ValueError(f'Non-ASCII {label} response') from exc
    if any((not token for token in fields)):
        raise ValueError(f'Malformed {label} response')
    return [token.encode('ascii') for token in fields]

def _parse_int(token: bytes, label: str, *, signed: bool=False) -> int:
    try:
        text = token.decode('ascii')
        if not text or text.startswith('+') or text.strip() != text:
            raise ValueError
        if text.startswith('-'):
            if not signed or len(text) == 1 or (len(text) > 2 and text[1] == '0'):
                raise ValueError
            digits = text[1:]
        else:
            digits = text
            if len(digits) > 1 and digits[0] == '0':
                raise ValueError
        if not digits.isdecimal():
            raise ValueError
        return int(text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f'Invalid {label}') from exc

def parse_readback(payload: bytes, player_id: int, expected_turn: int) -> dict:
    pid, turn = (_player_id(player_id), _turn(expected_turn))
    fields = _parse_response(payload, 'government readback')
    if len(fields) != 6 or fields[0] != b'readback':
        raise ValueError('Malformed government readback')
    actual_pid = _parse_int(fields[1], 'player ID')
    actual_turn = _parse_int(fields[2], 'turn')
    gov = _parse_int(fields[3], 'government index', signed=True)
    considered = _parse_int(fields[4], 'considered flag')
    blocker = _parse_int(fields[5], 'blocker flag')
    if actual_pid != pid or actual_turn != turn or (not -1 <= gov <= 2147483647):
        raise ValueError('Government readback is stale or belongs to another player')
    if considered not in (0, 1) or blocker not in (0, 1):
        raise ValueError('Government readback boolean is invalid')
    return {'player_id': pid, 'current_game_turn': turn, 'government_index': gov, 'considered': bool(considered), 'consideration_blocker_present': bool(blocker)}

def request_source(player_id: int, expected_turn: int, expected_government: int) -> bytes:
    """Mark considered only with the exact blocker and unchanged current state."""
    verify_source()
    gov = _government(expected_government)
    if gov == -1:
        raise ValueError('No current government to acknowledge in this profile')
    return _common_source(player_id, expected_turn, gov) + b"\nassert(not wasConsidered,'government blocker was already considered')\nassert(hasBlocker,'consider-government blocker is absent')\n-- This is the source-defined acknowledgement operation, not a government change.\nculture:SetGovernmentChangeConsidered(true)\nassertContext()\nlocal govAfter=currentGovernment()\nlocal consideredAfter=considered()\nlocal blockerAfter=blockerPresent()\nassert(govAfter==gov and consideredAfter==true,\n 'native consideration setter did not produce the requested readback')\nassertContext()\nreturn table.concat({'considered',string.format('%.0f',pid),\n string.format('%.0f',expectedTurn),string.format('%.0f',govAfter),\n '1',blockerAfter and '1' or '0'},'|')\n"

def parse_request_result(payload: bytes, player_id: int, expected_turn: int, expected_government: int) -> dict:
    pid, turn = (_player_id(player_id), _turn(expected_turn))
    gov = _government(expected_government)
    if gov < 0:
        raise ValueError('No current government in supported profile')
    fields = _parse_response(payload, 'government consideration')
    if len(fields) != 6 or fields[0] != b'considered':
        raise ValueError('Malformed government consideration response')
    actual = (_parse_int(fields[1], 'player ID'), _parse_int(fields[2], 'turn'), _parse_int(fields[3], 'government index', signed=True), _parse_int(fields[4], 'considered flag'), _parse_int(fields[5], 'blocker flag'))
    if actual != (pid, turn, gov, 1, actual[4]) or actual[4] not in (0, 1):
        raise ValueError('Government consideration readback is stale, mismatched, or invalid')
    return {'player_id': pid, 'current_game_turn': turn, 'government_index': gov, 'consideration_marked': True, 'consideration_blocker_present_after': bool(actual[4]), 'government_changed': False}

def guard_case() -> bytes:
    """HKS Lua-double checks of eligibility, blocker and setter readback only."""
    verify_source()
    readback = readback_source(0, 5)
    request = request_source(0, 5, 3)
    return b'local saved={Game=Game,Players=Players,NotificationManager=NotificationManager,\n EndTurnBlockingTypes=EndTurnBlockingTypes}\nlocal ok,result=pcall(function()\n local S={pid=0,observer=0,turn=5,alive=true,active=true,complete=true,\n strategic=true,gov=3,considered=false,blockers={1472003650},setterWorks=true,\n setterChangesGovernment=false,missingSetter=false,missingGetter=false,missingBlocker=false}\n Game={GetLocalPlayer=function() return S.pid end,GetLocalObserver=function() return S.observer end,\n  GetCurrentGameTurn=function() return S.turn end,\n  IsAllowStrategicCommands=function(pid) assert(pid==0); return S.strategic end}\n local culture={GetCurrentGovernment=function() return S.gov end,\n  GovernmentChangeConsidered=function() if S.missingGetter then return nil end; return S.considered end,\n  SetGovernmentChangeConsidered=function(_,value)\n   assert(value==true)\n   if S.setterWorks then S.considered=true; S.blockers={} end\n   if S.setterChangesGovernment then S.gov=4 end\n  end}\n local player={IsAlive=function() return S.alive end,IsTurnActive=function() return S.active end,\n  IsTurnActiveComplete=function() return S.complete end,GetCulture=function() return culture end}\n Players={[0]=player,[1]=player}\n NotificationManager={GetAllEndTurnBlocking=function(pid)\n  assert(not S.missingBlocker and pid==0); return S.blockers end}\n EndTurnBlockingTypes={ENDTURN_BLOCKING_CONSIDER_GOVERNMENT_CHANGE=1472003650}\n local function read()\n' + readback + b'\n end\n local function act()\n' + request + b"\n end\n assert(read()=='readback|0|5|3|0|1')\n assert(act()=='considered|0|5|3|1|0')\n assert(read()=='readback|0|5|3|1|0')\n S.pid=1; assert(not pcall(read) and not pcall(act)); S.pid=0\n S.observer=1; assert(not pcall(read) and not pcall(act)); S.observer=0\n S.turn=6; assert(not pcall(read) and not pcall(act)); S.turn=5\n S.gov=4; assert(not pcall(act)); S.gov=3\n S.considered=true; assert(not pcall(act)); S.considered=false\n S.blockers={}; assert(not pcall(act)); S.blockers={1472003650}\n S.alive=false; assert(not pcall(read) and not pcall(act)); S.alive=true\n S.active=false; assert(not pcall(read) and not pcall(act)); S.active=true\n S.complete=false; assert(not pcall(read) and not pcall(act)); S.complete=true\n S.strategic=false; assert(not pcall(read) and not pcall(act)); S.strategic=true\n S.setterWorks=false; assert(not pcall(act)); S.setterWorks=true; S.considered=false\n S.setterChangesGovernment=true; assert(not pcall(act)); S.setterChangesGovernment=false; S.gov=3; S.considered=false; S.blockers={1472003650}\n S.missingGetter=true; assert(not pcall(read) and not pcall(act)); S.missingGetter=false\n S.missingBlocker=true; assert(not pcall(read) and not pcall(act)); S.missingBlocker=false\n culture.SetGovernmentChangeConsidered=nil; assert(not pcall(act))\n return 'government-consideration-guards-ok'\nend)\nGame,Players,NotificationManager,EndTurnBlockingTypes=saved.Game,saved.Players,\n saved.NotificationManager,saved.EndTurnBlockingTypes\nassert(ok,result)\nreturn result\n"

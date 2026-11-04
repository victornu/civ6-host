"""Source-backed candidate/effect observations for human research and civics.

This module never submits an operation. It uses the installed chooser's
CanResearch/CanProgress filters to select one deterministic candidate and
serializes the exact PlayerOperations enum values supplied by Lua.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_research_actions.py')))).resolve().parents[1]
_ASSETS = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_PROOF_PATH = _ROOT / 'evidence/native-player-operation-route.json'
_PROOF_SHA256 = '6ba4b94fd024f320012303beca763601857afeff633b7008c394ac52bee0f1d2'
_SOURCE_HASHES = {'research': ('Choosers/ResearchChooser.lua', '752342e2cb75a2cc2905147005e6128c9d7a6a800c70235de6bcc21ed32092b5'), 'civic': ('Choosers/CivicsChooser.lua', '6ea1764d954bd147653b04e43f1b4825055f7f2a915968571b150f525b04fb20')}
_IMAGE_SHA256 = {'exe': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}

def verify_source(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> None:
    """Verify the exact installed chooser files and pinned route evidence."""
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.xp1_research_profile import verify_source as verify_selected_source
        return verify_selected_source(core_sha256)
    proof_raw = _resolve_resource_path(_PROOF_PATH).read_bytes()
    if hashlib.sha256(proof_raw).hexdigest() != _PROOF_SHA256:
        raise RuntimeError('Pinned player-operation route proof changed')
    proof = json.loads(proof_raw)
    if proof.get('schema') != 'civ6rl.native_player_operation_route.v3' or proof.get('images', {}).get('exe', {}).get('sha256') != _IMAGE_SHA256['exe'] or proof.get('images', {}).get('core', {}).get('sha256') != _IMAGE_SHA256['core']:
        raise RuntimeError('Unexpected player-operation route image identity')
    for kind, (relative, expected) in _SOURCE_HASHES.items():
        raw = _resolve_resource_path(_ASSETS / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError(f'Installed {kind} chooser source changed')
        proof_name = 'research_chooser' if kind == 'research' else 'civics_chooser'
        if proof.get('lua_sources', {}).get(proof_name, {}).get('sha256') != expected:
            raise RuntimeError(f'Pinned {kind} source hash is absent from route proof')

def _uint(value: int, label: str) -> bytes:
    if type(value) is not int or value < 0 or value > (4294967295 if label != 'player ID' else 63):
        raise ValueError(f'Invalid {label}')
    return str(value).encode('ascii')

def _player_id(value: int) -> bytes:
    return _uint(value, 'player ID')

def _kind(value: str) -> bytes:
    if type(value) is not str or value not in ('research', 'civic'):
        raise ValueError('kind must be research or civic')
    return value.encode('ascii')

def _candidate_prefix(player_id: int, kind: str, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    pid = _player_id(player_id)
    kind_b = _kind(kind)
    verify_source(core_sha256=core_sha256)
    member = b'Technologies' if kind == 'research' else b'Civics'
    can_method = b'CanResearch' if kind == 'research' else b'CanProgress'
    manager = b'GetTechs' if kind == 'research' else b'GetCulture'
    op_field = b'RESEARCH' if kind == 'research' else b'PROGRESS_CIVIC'
    param_field = b'PARAM_TECH_TYPE' if kind == 'research' else b'PARAM_CIVIC_TYPE'
    return b'local kind="' + kind_b + b'"\nlocal pid=' + pid + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and\n       Game.GetLocalPlayer()==pid,'native UI perspective is another player')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and\n       player:IsTurnActiveComplete(),\n       'requested player is not active')\nassert(PlayerOperations and PlayerOperations." + op_field + b'~=nil and\n       PlayerOperations.' + param_field + b"~=nil and\n       PlayerOperations.PARAM_INSERT_MODE~=nil and\n       PlayerOperations.VALUE_EXCLUSIVE~=nil,\n       'source PlayerOperations enums unavailable')\nlocal manager=player:" + manager + b'()\nassert(manager and type(manager.' + can_method + b")=='function',\n       'native candidate filter unavailable')\nlocal function u32(value,label)\n  assert(type(value)=='number' and value==math.floor(value),\n         'invalid numeric '..label)\n  assert(value>=0 and value<=4294967295,'invalid uint32 '..label)\n  return value\nend\nlocal function signedBits(value,label)\n  assert(type(value)=='number' and value==math.floor(value),\n         'invalid numeric '..label)\n  assert(value>=-2147483648 and value<=2147483647,\n         'native signed integer out of range '..label)\n  if value<0 then\n    value=value+4294967296\n  end\n  return value\nend\nlocal selected=nil\nlocal count=0\nfor row in GameInfo." + member + b"() do\n  count=count+1\n  assert(count<=8192,'GameInfo enumeration exceeds diagnostic bound')\n  assert(row and row.Index~=nil and row.Hash~=nil,\n         'incomplete native GameInfo row')\n  local index=u32(row.Index,'row index')\n  local hash=signedBits(row.Hash,'row hash')\n  if manager:" + can_method + b"(index)==true then\n    if selected==nil or index<selected.index then\n      selected={index=index,hash=hash}\n    elseif index==selected.index then\n      assert(hash==selected.hash,'duplicate eligible index with conflicting hash')\n    end\n  end\nend\nif selected==nil then return 'none,'..kind..','..pid..','..u32(Game.GetCurrentGameTurn(),'turn') end\nlocal operation=signedBits(PlayerOperations." + op_field + b",'operation enum')\nlocal parameter_key=signedBits(PlayerOperations." + param_field + b",'parameter enum')\nlocal insert_key=signedBits(PlayerOperations.PARAM_INSERT_MODE,'insert enum')\nlocal exclusive=signedBits(PlayerOperations.VALUE_EXCLUSIVE,'exclusive enum')\nlocal function dec(n) return string.format('%.0f',n) end\nreturn table.concat({kind,dec(pid),dec(u32(Game.GetCurrentGameTurn(),'turn')),\n  dec(selected.index),dec(selected.hash),dec(operation),dec(parameter_key),\n  dec(insert_key),dec(exclusive)},',')\n"

def candidate_source(player_id: int, kind: str='research', *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Return the smallest legal GameInfo index and shipped exclusive params."""
    return _candidate_prefix(player_id, kind, core_sha256=core_sha256)

def _parse_uint(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((byte < 48 or byte > 57 for byte in token)):
        raise ValueError(f'Invalid {label}')
    if len(token) > 1 and token[0] == 48:
        raise ValueError(f'Noncanonical {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'{label} is out of range')
    return value

def parse_candidate(payload: bytes, expected_player: int, kind: str='research', expected_turn: int | None=None) -> dict | None:
    """Strictly parse a candidate or the typed `none` response.

    For selected rows, `parameters` is the native integer-key map suitable for
    the operation serializer: `{PARAM_*: Hash, PARAM_INSERT_MODE: VALUE_EXCLUSIVE}`.
    """
    pid = int(_player_id(expected_player))
    kind_b = _kind(kind)
    if type(payload) is not bytes or len(payload) > 160:
        raise ValueError('Invalid research candidate response bytes')
    fields = payload.split(b',')
    if len(fields) == 4 and fields[0] == b'none':
        if fields[1] != kind_b or _parse_uint(fields[2], 'player ID', 63) != pid:
            raise ValueError('Candidate response has wrong kind or player')
        turn = _parse_uint(fields[3], 'game turn')
        if expected_turn is not None and turn != _parse_uint(_uint(expected_turn, 'expected turn'), 'expected turn'):
            raise ValueError('Candidate response is stale')
        return None
    if len(fields) != 9 or fields[0] != kind_b:
        raise ValueError('Malformed research candidate response')
    actual_pid = _parse_uint(fields[1], 'player ID', 63)
    turn = _parse_uint(fields[2], 'game turn')
    index = _parse_uint(fields[3], 'selected index')
    row_hash = _parse_uint(fields[4], 'selected hash')
    operation = _parse_uint(fields[5], 'operation enum')
    parameter_key = _parse_uint(fields[6], 'parameter key enum')
    insert_key = _parse_uint(fields[7], 'insert key enum')
    exclusive = _parse_uint(fields[8], 'exclusive enum')
    if actual_pid != pid:
        raise ValueError('Candidate belongs to another player')
    if expected_turn is not None and turn != _parse_uint(_uint(expected_turn, 'expected turn'), 'expected turn'):
        raise ValueError('Candidate response is stale')
    if parameter_key == insert_key:
        raise ValueError('Candidate enum keys collide')
    return {'kind': kind, 'player_id': actual_pid, 'current_game_turn': turn, 'selected_index': index, 'selected_hash': row_hash, 'operation': operation, 'parameters': {parameter_key: row_hash, insert_key: exclusive}, 'parameter_key': parameter_key, 'insert_key': insert_key, 'exclusive_value': exclusive}

def effect_source(player_id: int, kind: str, expected_index: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Read back current research/civic selection; this does not mutate state."""
    pid = _player_id(player_id)
    index = _uint(expected_index, 'selected index')
    kind_b = _kind(kind)
    verify_source(core_sha256=core_sha256)
    getter = b'GetResearchingTech' if kind == 'research' else b'GetProgressingCivic'
    manager = b'GetTechs' if kind == 'research' else b'GetCulture'
    return b'local kind="' + kind_b + b'"\nlocal pid=' + pid + b'\nlocal expected=' + index + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and\n       Game.GetLocalPlayer()==pid,'native UI perspective is another player')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive(),'requested player unavailable')\nlocal manager=player:" + manager + b'()\nassert(manager and type(manager.' + getter + b")=='function',\n       'native effect getter unavailable')\nlocal value=manager:" + getter + b"()\nassert(type(value)=='number' and value==math.floor(value),\n       'invalid native effect index')\nassert(value>=-1 and value<=4294967295,'native effect index outside range')\nlocal function u32(value,label)\n  assert(type(value)=='number' and value==math.floor(value) and\n         value>=0 and value<=4294967295,'invalid '..label)\n  return string.format('%.0f',value)\nend\nlocal turn=Game.GetCurrentGameTurn()\nreturn table.concat({kind,u32(pid,'player'),u32(turn,'turn'),\n  value<0 and '-1' or u32(value,'effect index'),u32(expected,'expected index')},',')\n"

def parse_effect(payload: bytes, expected_player: int, kind: str, expected_index: int, expected_turn: int | None=None) -> dict:
    """Parse post-action current index and report exact index match."""
    pid = int(_player_id(expected_player))
    kind_b = _kind(kind)
    expected = int(_uint(expected_index, 'selected index'))
    if type(payload) is not bytes or len(payload) > 128:
        raise ValueError('Invalid research effect response bytes')
    fields = payload.split(b',')
    if len(fields) != 5 or fields[0] != kind_b:
        raise ValueError('Malformed research effect response')
    actual_pid = _parse_uint(fields[1], 'player ID', 63)
    turn = _parse_uint(fields[2], 'game turn')
    if actual_pid != pid:
        raise ValueError('Effect belongs to another player')
    if expected_turn is not None and turn != _parse_uint(_uint(expected_turn, 'expected turn'), 'expected turn'):
        raise ValueError('Effect response is from another game turn')
    if fields[3] == b'-1':
        observed = None
    else:
        observed = _parse_uint(fields[3], 'observed index')
    reported_expected = _parse_uint(fields[4], 'expected index')
    if reported_expected != expected:
        raise ValueError('Effect response references another candidate')
    return {'kind': kind, 'player_id': actual_pid, 'current_game_turn': turn, 'selected_index': expected, 'observed_index': observed, 'confirmed': observed == expected}

def guard_case(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Run candidate/effect sources against Lua doubles, without submission."""
    research = candidate_source(0, 'research', core_sha256=core_sha256)
    civic = candidate_source(0, 'civic', core_sha256=core_sha256)
    research_effect = effect_source(0, 'research', 3, core_sha256=core_sha256)
    civic_effect = effect_source(0, 'civic', 2, core_sha256=core_sha256)
    return b"local state={localID=0,turn=7,alive=true,active=true,complete=true,submits=0,\n researchCurrent=3,civicCurrent=2, researchLegal={[1]=true,[3]=true},\n civicLegal={[2]=true,[4]=true}}\nlocal techRows={{Index=3,Hash=-2147483648},{Index=1,Hash=-1},{Index=5,Hash=99}}\nlocal civicRows={{Index=4,Hash=-200},{Index=2,Hash=2147483647}}\nlocal function iterator(rows)\n local i=0\n return function() i=i+1; return rows[i] end\nend\nlocal Game={GetLocalPlayer=function() return state.localID end,\n GetCurrentGameTurn=function() return state.turn end}\nlocal techs={CanResearch=function(_,i) return state.researchLegal[i]==true end,\n GetResearchingTech=function() return state.researchCurrent end}\nlocal culture={CanProgress=function(_,i) return state.civicLegal[i]==true end,\n GetProgressingCivic=function() return state.civicCurrent end}\nlocal player={IsAlive=function() return state.alive end,\n IsTurnActive=function() return state.active end,\n IsTurnActiveComplete=function() return state.complete end,\n GetTechs=function() return techs end,GetCulture=function() return culture end}\nlocal Players={[0]=player}\nlocal GameInfo={Technologies=function() return iterator(techRows) end,\n Civics=function() return iterator(civicRows) end}\nlocal PlayerOperations={RESEARCH=-101,PROGRESS_CIVIC=-102,\n PARAM_TECH_TYPE=-103,PARAM_CIVIC_TYPE=-104,PARAM_INSERT_MODE=-105,\n VALUE_EXCLUSIVE=-106}\nlocal UI={RequestPlayerOperation=function() state.submits=state.submits+1;error('must not submit') end}\nlocal function research_candidate()\n" + research + b'end\nlocal function civic_candidate()\n' + civic + b'end\nlocal function research_effect()\n' + research_effect + b'end\nlocal function civic_effect()\n' + civic_effect + b"end\nlocal a=research_candidate()\nlocal b=civic_candidate()\nassert(a=='research,0,7,1,4294967295,4294967195,4294967193,4294967191,4294967190')\nassert(b=='civic,0,7,2,2147483647,4294967194,4294967192,4294967191,4294967190')\nassert(research_effect()=='research,0,7,3,3')\nassert(civic_effect()=='civic,0,7,2,2' and state.submits==0)\nstate.researchLegal={}; assert(research_candidate()=='none,research,0,7')\nstate.researchLegal={[1]=true,[3]=true}\ntechRows[1].Hash=2147483648\nassert(not pcall(research_candidate) and state.submits==0)\ntechRows[1].Hash=-2147483648\nPlayerOperations.RESEARCH=2147483648\nassert(not pcall(research_candidate) and state.submits==0)\nPlayerOperations.RESEARCH=-101\nstate.localID=1; assert(not pcall(research_candidate) and not pcall(civic_candidate))\nstate.localID=0; state.active=false; assert(not pcall(research_candidate))\nstate.active=true; state.complete=false; assert(not pcall(research_candidate))\nstate.complete=true; state.alive=false; assert(not pcall(civic_candidate))\nstate.alive=true; state.turn=8\nassert(research_candidate():match('^research,0,8,') and state.submits==0)\nreturn 'research-civic-guards-ok'\n"

"""Bounded native UI request for a unit's SKIP_TURN operation.

The Lua source uses the UI-context UnitManager and rechecks player ownership,
turn state, readiness, and native legality immediately before submission.
Submission is not evidence that the game applied the request.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from civ6_host.runtime.native.native_unit_actions import _identifier
_PROOF_SHA256 = '69454efb375425864b82bdb703eeb1e233c6e8107d30e334ab25226ccab3c2e6'
_IMAGE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_unit_skip.py')))).resolve().parents[1] / 'evidence/native-unit-action-route.json'

def verify_source() -> None:
    """Verify the pinned UI UnitManager route used by this request."""
    raw = _resolve_resource_path(_PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA256:
        raise RuntimeError('Unit skip source proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_unit_action_route.v1' or proof.get('image', {}).get('sha256') != _IMAGE_SHA256:
        raise RuntimeError('Unexpected unit action source identity')
    contracts = proof.get('contracts', {})
    if '547840' not in contracts.get('legality', '') or '54A600' not in contracts.get('request', ''):
        raise RuntimeError('Pinned UnitManager route is incomplete')
_DEFAULT_PLAYER_IDS = (0, 1)
_FOUR_HOTSEAT_PLAYER_IDS = (0, 1, 2, 3)

def _validated_player_ids(player_ids) -> tuple[int, ...]:
    from civ6_host.runtime.network_owner import roster
    return roster(player_ids)

def _player_id(value: int, *, player_ids: tuple[int, ...]=_DEFAULT_PLAYER_IDS) -> bytes:
    allowed = _validated_player_ids(player_ids)
    if type(value) is not int or value not in allowed:
        raise ValueError('player ID is outside the explicitly admitted roster')
    return _identifier(value, 'player ID', 63)

def _parse_uint32(token: bytes, label: str) -> int:
    if not token or any((byte < 48 or byte > 57 for byte in token)):
        raise ValueError(f'Invalid {label}')
    if len(token) > 1 and token[0] == 48:
        raise ValueError(f'Noncanonical {label}')
    value = int(token)
    if value > 4294967295:
        raise ValueError(f'{label} is outside uint32')
    return value

def parse_candidate(payload: bytes, expected_player: int, *, player_ids: tuple[int, ...]=_DEFAULT_PLAYER_IDS) -> tuple[int, int] | None:
    """Parse ``none`` or the canonical ``owner,unit_id`` response."""
    allowed = _validated_player_ids(player_ids)
    expected = _player_id(expected_player, player_ids=allowed)
    if type(payload) is not bytes or len(payload) > 64:
        raise ValueError('Invalid candidate response bytes')
    if payload == b'none':
        return None
    fields = payload.split(b',')
    if len(fields) != 2:
        raise ValueError('Malformed candidate response')
    owner = _parse_uint32(fields[0], 'candidate owner')
    unit_id = _parse_uint32(fields[1], 'candidate unit ID')
    if owner not in allowed or owner != int(expected):
        raise ValueError('Candidate owner does not match requested player')
    return (owner, unit_id)

def parse_effect(payload: bytes, expected_unit: int) -> dict[str, int | bool | None]:
    """Parse the post-request readiness observation, bound to ``expected_unit``.

    Lua returns ``missing,<first-ready-id|none>`` or
    ``<unit-id>,<true|false>,<first-ready-id|none>``.
    """
    expected = _identifier(expected_unit, 'unit ID', 4294967295)
    if type(payload) is not bytes or len(payload) > 64:
        raise ValueError('Invalid effect response bytes')
    fields = payload.split(b',')
    if len(fields) == 2 and fields[0] == b'missing':
        ready = None
        first = fields[1]
    elif len(fields) == 3:
        observed = _parse_uint32(fields[0], 'observed unit ID')
        if observed != int(expected):
            raise ValueError('Effect response is for another unit')
        if fields[1] == b'true':
            ready = True
        elif fields[1] == b'false':
            ready = False
        else:
            raise ValueError('Invalid readiness value')
        first = fields[2]
    else:
        raise ValueError('Malformed effect response')
    first_ready_id = None if first == b'none' else _parse_uint32(first, 'first-ready unit ID')
    return {'ready': ready, 'first_ready_id': first_ready_id}

def candidate_source(player_id: int, *, player_ids: tuple[int, ...]=_DEFAULT_PLAYER_IDS) -> bytes:
    """Return the smallest ready own-unit ID currently legal to skip."""
    roster = _validated_player_ids(player_ids)
    pid = _player_id(player_id, player_ids=roster)
    verify_source()
    return b'local pid=' + pid + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function',\n       'native unit operation legality API unavailable')\nlocal p=Players and Players[pid]\nassert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),\n       'requested player is not ready')\nlocal candidate=nil\nlocal count=0\nfor _,u in p:GetUnits():Members() do\n  count=count+1\n  assert(count<=4096,'unit enumeration exceeds diagnostic bound')\n  assert(u:GetOwner()==pid,'foreign unit in own-unit collection')\n  if u:IsReadyToSelect()==true and\n     UnitManager.CanStartOperation(u,'UNITOPERATION_SKIP_TURN',nil,false)==true then\n    local id=u:GetID()\n    assert(type(id)=='number' and id%1==0 and id>=0 and id<=4294967295,\n           'invalid native unit ID')\n    if candidate==nil or id<candidate then candidate=id end\n  end\nend\nif candidate==nil then return 'none' end\nreturn string.format('%d,%d',pid,candidate)\n"

def request_source(player_id: int, unit_id: int, *, player_ids: tuple[int, ...]=_DEFAULT_PLAYER_IDS) -> bytes:
    """Re-resolve and revalidate a unit before submitting SKIP_TURN."""
    roster = _validated_player_ids(player_ids)
    pid = _player_id(player_id, player_ids=roster)
    uid = _identifier(unit_id, 'unit ID', 4294967295)
    verify_source()
    return b'local pid,uid=' + pid + b',' + uid + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nlocal p=Players and Players[pid]\nassert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),\n       'requested player is not ready')\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function' and\n       type(UnitManager.RequestOperation)=='function',\n       'native unit operation API unavailable')\nlocal selected=nil\nlocal count=0\nfor _,u in p:GetUnits():Members() do\n  count=count+1\n  assert(count<=4096,'unit enumeration exceeds diagnostic bound')\n  if u:GetID()==uid then\n    assert(selected==nil and u:GetOwner()==pid,'ambiguous or foreign unit')\n    selected=u\n  end\nend\nassert(selected~=nil,'requested own unit unavailable')\nassert(selected:IsReadyToSelect()==true,'requested unit is not ready to select')\nassert(UnitManager.CanStartOperation(selected,'UNITOPERATION_SKIP_TURN',nil,false)==true,\n       'native skip-turn legality check rejected request')\nUnitManager.RequestOperation(selected,'UNITOPERATION_SKIP_TURN')\nreturn 'submitted'\n"

def effect_source(player_id: int, unit_id: int, *, player_ids: tuple[int, ...]=_DEFAULT_PLAYER_IDS) -> bytes:
    """Observe current readiness and first ready own-unit ID after a request."""
    roster = _validated_player_ids(player_ids)
    pid = _player_id(player_id, player_ids=roster)
    uid = _identifier(unit_id, 'unit ID', 4294967295)
    verify_source()
    return b'local pid,uid=' + pid + b',' + uid + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nlocal p=Players and Players[pid]\nassert(p and p:IsAlive(),'requested player unavailable for effect observation')\nlocal selected=nil\nlocal count=0\nfor _,u in p:GetUnits():Members() do\n  count=count+1\n  assert(count<=4096,'unit enumeration exceeds diagnostic bound')\n  assert(u:GetOwner()==pid,'foreign unit in own-unit collection')\n  if u:GetID()==uid then\n    assert(selected==nil,'duplicate own unit ID')\n    selected=u\n  end\nend\nlocal ready='missing'\nif selected~=nil then\n  local value=selected:IsReadyToSelect()\n  assert(type(value)=='boolean','invalid native unit readiness result')\n  ready=string.format('%d',uid)..','..(value and 'true' or 'false')\nend\nlocal first=p:GetUnits():GetFirstReadyUnit()\nlocal firstID='none'\nif first~=nil then\n  assert(first:GetOwner()==pid,'foreign first-ready unit')\n  local id=first:GetID()\n  assert(type(id)=='number' and id%1==0 and id>=0 and id<=4294967295,\n         'invalid first-ready unit ID')\n  firstID=string.format('%d',id)\nend\nif ready=='missing' then return 'missing,'..firstID end\nreturn ready..','..firstID\n"

def action_guard_case() -> bytes:
    """Adversarial Lua doubles for stale, foreign, unready, and illegal cases."""
    return b"local State={localID=0,alive=true,active=true,complete=true,\n legal=true,ready=true,exists=true,owner=0,submitted=0,multiple=true}\nlocal u={GetID=function() return 17 end,GetOwner=function() return State.owner end,\n IsReadyToSelect=function() return State.ready end}\nlocal u2={GetID=function() return 9 end,GetOwner=function() return 0 end,\n IsReadyToSelect=function() return State.ready end}\nlocal function members()\n local index=0\n return function()\n  index=index+1\n  if State.exists and State.multiple then\n   if index==1 then return 1,u end\n   if index==2 then return 2,u2 end\n  elseif State.exists and index==1 then return 1,u end\n end\nend\nlocal units={Members=members,GetFirstReadyUnit=function() return State.exists and u or nil end}\nlocal p={IsAlive=function() return State.alive end,\n IsTurnActive=function() return State.active end,\n IsTurnActiveComplete=function() return State.complete end,\n GetUnits=function() return units end}\nlocal Game={GetLocalPlayer=function() return State.localID end}\nlocal Players={[0]=p,[1]=p}\nlocal UnitManager={CanStartOperation=function(unit,op,params,details)\n assert((unit==u or unit==u2) and op=='UNITOPERATION_SKIP_TURN' and params==nil and details==false)\n return State.legal\nend,RequestOperation=function(unit,op)\n assert(unit==u and op=='UNITOPERATION_SKIP_TURN')\n assert(State.localID==0 and State.alive and State.active and State.complete and\n        State.exists and State.owner==0 and State.ready and State.legal)\n State.submitted=State.submitted+1\nend}\nlocal function candidate()\n" + candidate_source(0) + b'end\nlocal function request()\n' + request_source(0, 17) + b'end\nlocal function effect()\n' + effect_source(0, 17) + b"end\nassert(candidate()=='0,9' and State.submitted==0)\nassert(effect()=='17,true,17')\nState.multiple=false\nState.legal=false; assert(candidate()=='none' and not pcall(request) and State.submitted==0)\nState.legal=true; State.ready=false; assert(candidate()=='none' and not pcall(request) and State.submitted==0)\nState.ready=true; State.active=false; assert(not pcall(request) and State.submitted==0)\nState.active=true; State.complete=false; assert(not pcall(request) and State.submitted==0)\nState.complete=true; State.alive=false; assert(not pcall(request) and State.submitted==0)\nState.alive=true; State.localID=1; assert(not pcall(request) and State.submitted==0)\nState.localID=0; State.owner=1; assert(not pcall(candidate) and not pcall(request) and State.submitted==0)\nState.owner=0; State.exists=false; assert(candidate()=='none' and not pcall(request) and State.submitted==0)\nState.exists=true; State.owner=0; State.ready=true; State.legal=true\nassert(request()=='submitted' and State.submitted==1)\nState.exists=false; assert(effect()=='missing,none')\nreturn 'unit-skip-guards-ok'\n"

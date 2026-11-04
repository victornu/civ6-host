"""Public UI city production requests, with native legality rechecked.

Only submission is represented here. The caller must deliver the serialized
command, process native cache updates, and verify its outcome separately.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import re
from civ6_host.runtime.native.native_unit_actions import _identifier
PROOF_SHA256 = '4a7d68af86ee98e433ccf845abb13343f91a75244a7403f9c11c09179f64ce63'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_actions.py')))).resolve().parents[1] / 'evidence/native-city-action-route' / f'{PROOF_SHA256}.json'

def verify_source():
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise RuntimeError('City action source proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_city_action_route.v1' or proof['image']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        raise RuntimeError('Unexpected city action source identity')

def _preamble(player_id, unit_type):
    player = _identifier(player_id, 'player ID', 63)
    if type(unit_type) is not str or not re.fullmatch('UNIT_[A-Z0-9_]{1,100}', unit_type):
        raise ValueError('Invalid native unit type key')
    verify_source()
    return b'local pid=' + player + b"\nassert(Game.GetLocalPlayer()==pid,'native UI perspective is another player')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and\n       player:IsTurnActiveComplete(),'requested player is not ready')\nassert(CityManager and type(CityManager.CanStartOperation)=='function' and\n       type(CityManager.RequestOperation)=='function','native city operation API unavailable')\nassert(CityOperationTypes and CityOperationTypes.BUILD and\n       CityOperationTypes.PARAM_UNIT_TYPE and CityOperationTypes.PARAM_INSERT_MODE and\n       CityOperationTypes.PARAM_QUEUE_DESTINATION_LOCATION and CityOperationTypes.VALUE_REPLACE_AT,\n       'native city operation enums unavailable')\nlocal row=GameInfo.Units[" + b"'" + unit_type.encode('ascii') + b"'" + b"]\nassert(row and type(row.Hash)=='number' and type(row.Index)=='number',\n       'native unit definition unavailable')\nlocal parameters={}\nparameters[CityOperationTypes.PARAM_UNIT_TYPE]=row.Hash\nparameters[CityOperationTypes.PARAM_INSERT_MODE]=CityOperationTypes.VALUE_REPLACE_AT\nparameters[CityOperationTypes.PARAM_QUEUE_DESTINATION_LOCATION]=0\n"

def unit_production_candidate_source(player_id, unit_type='UNIT_WARRIOR'):
    return _preamble(player_id, unit_type) + b"local selected=nil\nlocal count=0\nfor _,city in player:GetCities():Members() do\n count=count+1\n assert(count<=4096,'native city enumeration exceeds diagnostic bound')\n assert(city:GetOwner()==pid,'foreign city in own collection')\n if city:GetBuildQueue():GetSize()==0 and\n    CityManager.CanStartOperation(city,CityOperationTypes.BUILD,parameters,false) then\n  if selected==nil or city:GetID()<selected:GetID() then selected=city end\n end\nend\nif selected==nil then return 'none' end\nreturn string.format('%d,%d,%d,%d',pid,selected:GetID(),row.Index,row.Hash)\n"

def request_unit_production_source(player_id, city_id, unit_type='UNIT_WARRIOR'):
    city = _identifier(city_id, 'city ID', 4294967295)
    return _preamble(player_id, unit_type) + b"local selected=nil\nlocal count=0\nfor _,city in player:GetCities():Members() do\n count=count+1\n assert(count<=4096,'native city enumeration exceeds diagnostic bound')\n if city:GetID()==" + city + b" then\n  assert(selected==nil and city:GetOwner()==pid,'ambiguous or foreign city')\n  selected=city\n end\nend\nassert(selected~=nil,'requested own city unavailable')\nassert(selected:GetBuildQueue():GetSize()==0,'diagnostic requires empty production queue')\nassert(CityManager.CanStartOperation(selected,CityOperationTypes.BUILD,parameters,false),\n       'native unit production legality rejected request')\nCityManager.RequestOperation(selected,CityOperationTypes.BUILD,parameters)\nreturn 'submitted'\n"

def action_guard_case():
    """Exercise actual Lua request source against stale and foreign sentinels."""
    return b'local active,ready,exists,legal=true,true,true,true\nlocal owner,localID,size,submits=0,0,0,0\nlocal Game={GetLocalPlayer=function() return localID end}\nlocal GameInfo={Units={UNIT_WARRIOR={Hash=19,Index=2}}}\nlocal queue={GetSize=function() return size end}\nlocal city={GetID=function() return 5 end,GetOwner=function() return owner end,\n GetBuildQueue=function() return queue end}\nlocal p={IsAlive=function() return true end,IsTurnActive=function() return active end,\n IsTurnActiveComplete=function() return ready end,GetCities=function()\n return {Members=function() local used=false;return function()\n if not used and exists then used=true;return 1,city end end end} end}\nlocal Players={[0]=p}\nlocal CityOperationTypes={BUILD=7,PARAM_UNIT_TYPE=11,PARAM_INSERT_MODE=12,\n PARAM_QUEUE_DESTINATION_LOCATION=13,VALUE_REPLACE_AT=14}\nlocal function check(c,operation,args)\n assert(c==city and operation==7 and args[11]==19 and args[12]==14 and args[13]==0)\nend\nlocal CityManager={CanStartOperation=function(c,operation,args,details)\n check(c,operation,args);assert(details==false);return legal end,\n RequestOperation=function(c,operation,args)\n check(c,operation,args);assert(legal and ready and active and exists and size==0 and owner==0 and localID==0)\n submits=submits+1 end}\nlocal function candidate()\n' + unit_production_candidate_source(0) + b'end\nlocal function request()\n' + request_unit_production_source(0, 5) + b"end\nassert(candidate()=='0,5,2,19' and submits==0)\nlegal=false;assert(candidate()=='none' and not pcall(request) and submits==0);legal=true\nready=false;assert(not pcall(request) and submits==0);ready=true\nactive=false;assert(not pcall(request) and submits==0);active=true\nsize=1;assert(candidate()=='none' and not pcall(request) and submits==0);size=0\nexists=false;assert(not pcall(request) and submits==0);exists=true\nowner=1;assert(not pcall(request) and submits==0);owner=0\nlocalID=1;assert(not pcall(request) and submits==0);localID=0\nassert(request()=='submitted' and submits==1)\nreturn 'city-action-guards-ok'\n"

"""Own-unit native movement ranges, following SelectedUnit.RealizeMoveRadius.

This collector issues no operation and reads no enemy unit or plot details.
Reachable membership remains distinct from request legality and move effects.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
import math
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_reachable_movement.py')))).resolve().parents[1]
PROOF_SHA256 = '78dc75ae52baeae6c90b54dd6331f8511b42bad65996e36b72bbb739c68c3f18'
_PROOF = _ROOT / 'evidence/native-reachable-movement' / (PROOF_SHA256 + '.json')
MAX_RESULT_BYTES = 2 * 1024 * 1024
_STATUSES = {'queried', 'native_nil', 'no_moves', 'ignore_moves', 'spy_or_trader', 'zoc'}

def verify_source_evidence():
    p = load_pinned_json(_PROOF, PROOF_SHA256)
    if p.get('schema') != 'civ6rl.native_reachable_movement.static.v1' or p['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or p['registrations']['GetReachableMovement']['callback_va'] != '0x180549510':
        raise RuntimeError('Native reachable movement source identity changed')
    return p

def _integer(value, label, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid ' + label)
    return value

def candidate_source(player_id: int, expected_turn: int) -> bytes:
    verify_source_evidence()
    pid = _integer(player_id, 'player ID', 63)
    turn = _integer(expected_turn, 'turn', 4294967295)
    return 'local pid,expectedTurn=__PID__,__TURN__\nassert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n       \'reachable movement player perspective mismatch\')\nassert(type(Game.GetLocalObserver)==\'function\' and Game.GetLocalObserver()==pid,\n       \'reachable movement observer perspective mismatch\')\nassert(type(Game.GetCurrentGameTurn)==\'function\' and Game.GetCurrentGameTurn()==expectedTurn,\n       \'reachable movement turn is stale\')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,\'reachable movement player not ready\')\nassert(UnitManager and type(UnitManager.GetReachableMovement)==\'function\' and\n       GameInfo and GameInfo.Units,\'native movement range API unavailable\')\nassert(Map and type(Map.GetGridSize)==\'function\' and type(Map.GetPlotCount)==\'function\' and\n       type(Map.GetPlotIndex)==\'function\',\'native map geometry API unavailable\')\nlocal function uint(v,label,max)\n assert(type(v)==\'number\' and v%1==0 and v>=0 and v<=max,\'invalid \'..label)\n return v\nend\nlocal function n(v) return string.format(\'%.17g\',v) end\nlocal width,height=Map.GetGridSize()\nuint(width,\'width\',16384);uint(height,\'height\',16384)\nlocal plotCount=uint(Map.GetPlotCount(),\'plot count\',16384)\nassert(width>0 and height>0 and width*height==plotCount,\'invalid movement map shape\')\nlocal function optionalFlag(v,label)\n assert(v==nil or type(v)==\'boolean\',\'invalid \'..label)\n return v==true\nend\nlocal rows,ids={},{}\nlocal work=0\nfor _,unit in player:GetUnits():Members() do\n assert(#rows<4096,\'reachable unit bound exceeded\')\n local owner=uint(unit:GetOwner(),\'own unit owner\',63)\n assert(owner==pid,\'foreign unit in own collection\')\n local id=uint(unit:GetID(),\'own unit ID\',4294967295)\n assert(not ids[id],\'duplicate own unit ID\');ids[id]=true\n local x,y=uint(unit:GetX(),\'own unit x\',width-1),uint(unit:GetY(),\'own unit y\',height-1)\n local current=uint(Map.GetPlotIndex(x,y),\'current plot\',plotCount-1)\n local moves=unit:GetMovesRemaining()\n assert(type(moves)==\'number\' and moves==moves and moves>=0 and moves<=1000000,\n        \'invalid own unit movement\')\n local info=GameInfo.Units[uint(unit:GetUnitType(),\'unit type\',2147483647)]\n assert(info~=nil,\'own unit metadata missing\')\n local ignore=optionalFlag(info.IgnoreMoves,\'IgnoreMoves\')\n local spy=optionalFlag(info.Spy,\'Spy\')\n local trader=optionalFlag(info.MakeTradeRoute,\'MakeTradeRoute\')\n local status,plots=\'queried\',{}\n if ignore then status=\'ignore_moves\'\n elseif moves==0 then status=\'no_moves\'\n elseif spy or trader then status=\'spy_or_trader\'\n else\n  local zoc=unit:HasMovedIntoZOC()\n  assert(type(zoc)==\'boolean\',\'invalid own unit ZOC state\')\n  if zoc then status=\'zoc\'\n  else\n   -- No second argument: the public native wrapper selects its default1.\n   -- Native zero Lua results is kept distinct from an empty returned table.\n   local result=UnitManager.GetReachableMovement(unit)\n   if result==nil then status=\'native_nil\'\n   else\n    assert(type(result)==\'table\',\'native reachable result is not a table\')\n    local count,seen=0,{}\n    for key,index in pairs(result) do\n     uint(key,\'reachable array key\',16384);assert(key>=1,\'invalid reachable key\')\n     uint(index,\'reachable plot ID\',plotCount-1)\n     assert(not seen[index],\'duplicate reachable plot ID\');seen[index]=true\n     count=count+1\n    end\n    assert(count<=plotCount,\'reachable list exceeds map\')\n    work=work+count;assert(work<=100000,\'reachable total work bound exceeded\')\n    for i=1,count do\n     assert(result[i]~=nil,\'native reachable array is sparse\')\n     plots[i]=n(result[i])\n    end\n   end\n  end\n end\n rows[#rows+1]={id=id,text=\'{"unit_id":\'..n(id)..\',"owner":\'..n(owner)..\n  \',"current_plot_id":\'..n(current)..\',"moves_remaining":\'..n(moves)..\n  \',"status":"\'..status..\'","plot_ids":[\'..table.concat(plots,\',\')..\']}\'}\nend\ntable.sort(rows,function(a,b)return a.id<b.id end)\nlocal serialized={};for i,row in ipairs(rows)do serialized[i]=row.text end\nlocal result=\'{"schema":"native-reachable-movement-v1","player_id":\'..n(pid)..\n \',"observer_id":\'..n(Game.GetLocalObserver())..\',"turn":\'..n(Game.GetCurrentGameTurn())..\n \',"width":\'..n(width)..\',"height":\'..n(height)..\',"native_default_turns":1,\'..\n \'"aux_a8_used":false,"units":[\'..table.concat(serialized,\',\')..\']}\'\nassert(#result<=2097152,\'reachable movement result exceeds bound\')\nreturn result\n'.replace('__PID__', str(pid)).replace('__TURN__', str(turn)).encode('ascii')

def parse_reachable(payload: bytes, player_id: int, expected_turn: int) -> dict:
    _integer(player_id, 'player ID', 63)
    _integer(expected_turn, 'turn', 4294967295)
    if type(payload) is not bytes or not payload or len(payload) > MAX_RESULT_BYTES:
        raise ValueError('Invalid reachable movement result length')

    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('Duplicate reachable JSON key')
            result[k] = v
        return result

    def reject_constant(value):
        raise ValueError('Nonfinite reachable JSON value')
    try:
        out = json.loads(payload.decode('ascii'), object_pairs_hook=pairs, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid reachable JSON') from exc
    expected = {'schema', 'player_id', 'observer_id', 'turn', 'width', 'height', 'native_default_turns', 'aux_a8_used', 'units'}
    if type(out) is not dict or set(out) != expected or out['schema'] != 'native-reachable-movement-v1':
        raise ValueError('Invalid reachable result schema')
    for key, value in (('player_id', player_id), ('observer_id', player_id), ('turn', expected_turn), ('native_default_turns', 1)):
        if type(out[key]) is not int or out[key] != value:
            raise ValueError('Reachable perspective/turn mismatch')
    if out['aux_a8_used'] is not False:
        raise ValueError('Reachable query does not validate AUX+A8')
    w = _integer(out['width'], 'width', 16384)
    h = _integer(out['height'], 'height', 16384)
    if not w or not h or w * h > 16384:
        raise ValueError('Invalid reachable map shape')
    if type(out['units']) is not list or len(out['units']) > 4096:
        raise ValueError('Invalid reachable unit list')
    previous = -1
    work = 0
    for row in out['units']:
        if type(row) is not dict or set(row) != {'unit_id', 'owner', 'current_plot_id', 'moves_remaining', 'status', 'plot_ids'}:
            raise ValueError('Invalid reachable unit row')
        uid = _integer(row['unit_id'], 'unit ID', 4294967295)
        if uid <= previous:
            raise ValueError('Reachable unit IDs must be unique and ordered')
        previous = uid
        if type(row['owner']) is not int or row['owner'] != player_id:
            raise ValueError('Foreign reachable unit')
        _integer(row['current_plot_id'], 'current plot', w * h - 1)
        moves = row['moves_remaining']
        if type(moves) not in (int, float) or not math.isfinite(moves) or (not 0 <= moves <= 1000000.0):
            raise ValueError('Invalid reachable movement value')
        status = row['status']
        if type(status) is not str or status not in _STATUSES:
            raise ValueError('Unknown reachable unit status')
        plots = row['plot_ids']
        if type(plots) is not list or len(plots) > w * h:
            raise ValueError('Invalid reachable plot list')
        for index in plots:
            _integer(index, 'reachable plot', w * h - 1)
        if len(set(plots)) != len(plots):
            raise ValueError('Duplicate reachable plot')
        if status != 'queried' and plots:
            raise ValueError('Skipped/nil query has synthetic plots')
        if status in ('queried', 'native_nil', 'zoc', 'spy_or_trader') and moves <= 0:
            raise ValueError('Inconsistent reachable query eligibility')
        if status == 'no_moves' and moves != 0:
            raise ValueError('Inconsistent no-moves status')
        work += len(plots)
    if work > 100000:
        raise ValueError('Reachable total work exceeds bound')
    return out

def guard_case() -> bytes:
    """Lexically isolated Lua doubles for execution by tests or root's HKS."""
    collector = candidate_source(0, 7).decode('ascii')
    return 'local S={localID=0,observer=0,turn=7,queries=0,result={1,3,4},zoc=false}\nlocal unit={GetOwner=function()return 0 end,GetID=function()return 17 end,\n GetX=function()return 1 end,GetY=function()return 0 end,\n GetMovesRemaining=function()return 2 end,GetUnitType=function()return 0 end,\n HasMovedIntoZOC=function()return S.zoc end}\nlocal Game={GetLocalPlayer=function()return S.localID end,GetLocalObserver=function()return S.observer end,\n GetCurrentGameTurn=function()return S.turn end}\nlocal player={IsAlive=function()return true end,IsTurnActive=function()return true end,\n IsTurnActiveComplete=function()return true end,GetUnits=function()return {Members=function()\n local once=false;return function()if not once then once=true;return 1,unit end end end} end}\nlocal Players={[0]=player}\nlocal GameInfo={Units={[0]={IgnoreMoves=false,Spy=false,MakeTradeRoute=false}}}\nlocal Map={GetGridSize=function()return 5,1 end,GetPlotCount=function()return 5 end,\n GetPlotIndex=function(x,y)return x+y*5 end}\nlocal UnitManager={GetReachableMovement=function(u,...)\n assert(u==unit and select(\'#\',...)==0);S.queries=S.queries+1;return S.result end}\nlocal function collect()\n__COLLECTOR__\nend\nassert(string.find(collect(),\'"plot_ids":%[1,3,4%]\'))\nlocal calls=S.queries;S.observer=1;assert(not pcall(collect));assert(S.queries==calls);S.observer=0\nS.localID=1;assert(not pcall(collect));assert(S.queries==calls);S.localID=0\nS.turn=8;assert(not pcall(collect));assert(S.queries==calls);S.turn=7\nS.zoc=true;assert(string.find(collect(),\'"status":"zoc"\'));assert(S.queries==calls);S.zoc=false\nS.result=nil;assert(string.find(collect(),\'"status":"native_nil"\'))\nS.result={[1]=1,[3]=2};assert(not pcall(collect))\nS.result={1,1};assert(not pcall(collect))\nS.result={5};assert(not pcall(collect))\nreturn \'reachable-movement-guards-ok\'\n'.replace('__COLLECTOR__', collector).encode('ascii')

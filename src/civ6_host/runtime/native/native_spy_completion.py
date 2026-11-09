"""Native reads and one-use renewal choices for an owned completion occurrence.

The owner supplies only its currently shown native event occurrence. This module
does not enumerate history to invent popups, restore a UI lifetime, replay BBG
events, or activate notifications. Display admission is deliberately valid while
the local player's turn is inactive. Dismissal belongs to the owner's UI state.
"""
from __future__ import annotations

import json

from civ6_host.contracts import espionage, spy_completion
from civ6_host.runtime.native.native_saved_espionage import verify_source
from civ6_host.runtime.native.native_saved_trade import COMMON_LUA, literal
from civ6_host.runtime.native.native_saved_unit_orders import uint

LIMIT = 1048576


def _occurrence(value):
    if value is None:
        return None
    if type(value) is not dict or set(value) != {'event_sequence', 'mission_id'}:
        raise ValueError('Malformed spy completion occurrence')
    uint(value['event_sequence'], 'completion event sequence', 0xffffffff)
    uint(value['mission_id'], 'completion mission identity', 0x7fffffff)
    return dict(value)


def _decode(raw, limit=LIMIT):
    if type(raw) is not bytes or len(raw) > limit:
        raise ValueError('Unbounded spy completion wire')

    def unique(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError('Duplicate spy completion JSON key')
            out[key] = value
        return out

    return json.loads(raw, object_pairs_hook=unique)


def display_source(player_id, mission_id, event_sequence):
    """Admission happens on opening, not while adding a pending occurrence."""
    uint(player_id, 'player', 63)
    _occurrence({'event_sequence': event_sequence, 'mission_id': mission_id})
    verify_source()
    return f'''
local pid,missionID,eventSequence={player_id},{mission_id},{event_sequence}
assert(Game.GetLocalPlayer()==pid,'completion event perspective changed')
local player=Players[pid];assert(player,'completion event player absent')
local diplomacy=player:GetDiplomacy();assert(diplomacy,'completion diplomacy absent')
local mission=diplomacy:GetMission(pid,missionID)
if mission==0 then return 'missing' end
assert(type(mission)=='table','completion mission has malformed native value')
local operation=GameInfo.UnitOperations[mission.Operation]
assert(operation,'completion operation absent')
if operation.Hash==UnitOperationTypes.SPY_COUNTERSPY then
 local active=player:IsTurnActive();assert(type(active)=='boolean','completion turn-active predicate malformed')
 if not active then return 'suppressed' end
end
assert(Game.GetLocalPlayer()==pid,'completion event perspective changed')
return 'shown'
'''.encode()


def display_state(prefix, player_id, mission_id, event_sequence):
    raw = prefix.runtime.evaluate_text(
        prefix.ui_child, display_source(player_id, mission_id, event_sequence),
        b'@spy_completion_display', capacity=32,
    )
    if raw not in (b'shown', b'missing', b'suppressed'):
        raise ValueError('Malformed spy completion display receipt')
    return raw.decode('ascii')


def _callback_common():
    # Reuse the serializer and bounded map checks, but remove trade's turn-ready
    # test. The actual completion popup has no active/moves/alive gate for renew.
    inherited = "local p=Players[pid];assert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),'trade actor not ready');return p"
    if COMMON_LUA.count(inherited) != 1:
        raise RuntimeError('Shared serializer readiness boundary changed')
    return ('local json_null={}\n' + COMMON_LUA.replace(
        inherited, "local p=Players[pid];assert(p,'completion player absent');return p",
    ).replace(' and Game.GetLocalObserver()==pid', '').replace('trade', 'spy completion').replace(
        "if type(v)=='string'then",
        "if v==json_null then return 'null'\n elseif type(v)=='string'then",
    ))


LUA = _callback_common() + r'''
local function hash(v)return int(v,'operation hash',-2147483648,4294967295)%4294967296 end
local function missionRow(m)
 return {event_sequence=occurrence.event_sequence,mission_id=occurrence.mission_id,
  name=text(m.Name),level=int(m.LevelAfter,'mission level',-2147483648,2147483647),
  operation=int(m.Operation,'mission operation',-2147483648,2147483647),
  completion_turn=int(m.CompletionTurn,'completion turn',-2147483648,2147483647),
  initial_result=int(m.InitialResult,'initial result',-2147483648,2147483647),
  escape_result=int(m.EscapeResult,'escape result',-2147483648,2147483647),
  city_name=text(m.CityName),plot_id=int(m.PlotIndex,'mission plot',-1,width*height-1),
  loot_info=int(m.LootInfo,'mission loot',-2147483648,2147483647)}
end
local function successChance(operation,unit,target)
 if operation.Hash==UnitOperationTypes.SPY_COUNTERSPY then return -1 end
 local probabilities=UnitManager.GetResultProbability(operation.Index,unit,target)
 assert(type(probabilities)=='table','renew probability table absent')
 if probabilities.ESPIONAGE_SUCCESS_UNDETECTED==nil then return -1 end
 local success=finite(probabilities.ESPIONAGE_SUCCESS_UNDETECTED)
 assert(success>=0 and success<=1,'renew success probability malformed')
 if probabilities.ESPIONAGE_SUCCESS_MUST_ESCAPE~=nil then
  local escape=finite(probabilities.ESPIONAGE_SUCCESS_MUST_ESCAPE)
  assert(escape>=0 and escape<=1,'renew escape probability malformed');success=success+escape
 end
 return int(math.floor(success*100+0.5),'renew success percent',0,100)
end
local function snapshot()
 local p=ready()
 local out={schema='civ6-host.spy-completion.v1',player_id=pid,turn=turn,width=width,height=height,current=json_null,offers=array()}
 if occurrence==nil then return out,nil end
 local mission=p:GetDiplomacy():GetMission(pid,occurrence.mission_id)
 if mission==0 then return out,nil end
 assert(type(mission)=='table','completion mission malformed')
 out.current=missionRow(mission)
 local op=GameInfo.UnitOperations[mission.Operation];assert(op,'completion operation absent')
 local selected=nil
 if op.Hash==UnitOperationTypes.SPY_LISTENING_POST or op.Hash==UnitOperationTypes.SPY_COUNTERSPY then
  local unit=nil;local count=0
  for _,candidate in p:GetUnits():Members()do
   count=count+1;assert(count<=4096,'unbounded own unit roster')
   assert(candidate:GetOwner()==pid,'foreign completion unit')
   local definition=GameInfo.Units[candidate:GetUnitType()];assert(definition,'unit definition absent')
   if definition.Spy and candidate:GetName()==mission.Name then unit=candidate end
  end
  if unit then
   local target=Map.GetPlotByIndex(mission.PlotIndex);assert(target,'renew target plot absent')
   local city=Cities.GetPlotPurchaseCity(target);assert(city,'renew purchase city absent')
   local cityPlot=Map.GetPlot(city:GetX(),city:GetY());assert(cityPlot,'renew city plot absent')
   local details=true
   if op.Hash==UnitOperationTypes.SPY_COUNTERSPY then
    local district=GameInfo.Districts[target:GetDistrictType()]
    assert(district and type(district.Name)=='string','renew counterspy district absent')
   else
    local detail=text(UnitManager.GetOperationDetailText(op.Index,unit,cityPlot))
    if detail=='' then detail=text(Locale.Lookup('LOC_SPYMISSIONDETAILS_'..op.OperationType))end
    details=detail~=''
   end
   if details then
    local allowed=UnitManager.CanStartOperation(unit,op.Hash,cityPlot,false,true)
    if boolean(allowed,'renew legality')then
     local action={kind='spy_renew',unit_id=int(unit:GetID(),'renew unit',0,4294967295),
      event_sequence=occurrence.event_sequence,mission_id=occurrence.mission_id,
      operation_type=text(op.OperationType),operation_hash=hash(op.Hash),
      x=int(target:GetX(),'renew x',0,width-1),y=int(target:GetY(),'renew y',0,height-1),plot_id=int(target:GetIndex(),'renew plot',0,width*height-1)}
     out.offers[#out.offers+1]={action=action,turns=int(UnitManager.GetTimeToComplete(op.Index,unit),'renew duration',0,2147483647),
      success_percent=successChance(op,unit,target),failure_percent=-1,captured_or_killed_percent=-1}
     selected={action=action,unit=unit,operation=op.Hash,city=cityPlot,
      params={[UnitOperationTypes.PARAM_X]=action.x,[UnitOperationTypes.PARAM_Y]=action.y}}
    end
   end
  end
 end
 out.offers[#out.offers+1]={action={kind='spy_completion_dismiss',event_sequence=occurrence.event_sequence,mission_id=occurrence.mission_id},
  turns=-1,success_percent=-1,failure_percent=-1,captured_or_killed_percent=-1}
 ready();return out,selected
end
'''


def source(turn, player_id, occurrence):
    uint(turn, 'turn', 0x7fffffff)
    uint(player_id, 'player', 63)
    value = _occurrence(occurrence)
    verify_source()
    argument = 'nil' if value is None else literal(value)
    return f'local pid,turn={player_id},{turn}\nlocal occurrence={argument}\n'.encode() + LUA.encode()


def parse(raw, turn, player_id, occurrence):
    value = spy_completion.validate_catalogue(_decode(raw), player_id, turn)
    expected = _occurrence(occurrence)
    current = value['current']
    if current is not None:
        actual = {key: current[key] for key in ('event_sequence', 'mission_id')}
        if actual != expected:
            raise ValueError('Spy completion response differs from the owned occurrence')
    return value


def catalog(prefix, turn, player_id, occurrence):
    raw = prefix.runtime.evaluate_text(
        prefix.ui_child, source(turn, player_id, occurrence) + b'\nlocal out=snapshot();return encode(out)',
        b'@spy_completion_catalog', capacity=LIMIT + 1,
    )
    return parse(raw, turn, player_id, occurrence)


def request_source(action, catalogue):
    spy_completion.validate_catalogue(catalogue, catalogue['player_id'], catalogue['turn'])
    spy_completion.validate_action(action, catalogue['width'], catalogue['height'])
    if action['kind'] != 'spy_renew':
        raise ValueError('Spy completion dismissal is a local UI action, not a native archive')
    if action not in spy_completion.actions(catalogue):
        raise ValueError('Renewal outside the current completion offers')
    occurrence = {key: catalogue['current'][key] for key in ('event_sequence', 'mission_id')}
    return source(catalogue['turn'], catalogue['player_id'], occurrence) + f'''
local action={literal(action)}
local observed,selected=snapshot()
if not selected or not same(selected.action,action)then return 'refused' end
ready()
UnitManager.RequestOperation(selected.unit,selected.operation,selected.params)
return 'submitted'
'''.encode()


def effect_source(action, before, after):
    """Before/after are public espionage catalogues with live spy observations."""
    pid, turn = before['player_id'], before['turn']
    espionage.validate_catalogue(before, pid, turn)
    espionage.validate_catalogue(after, pid, turn)
    spy_completion.validate_action(action, before['width'], before['height'])
    if action['kind'] != 'spy_renew':
        raise ValueError('Only renewal has a native completion effect')
    old = next((row for row in before['spies'] if row['unit_id'] == action['unit_id']), None)
    if old is None:
        raise ValueError('Renewal effect lacks a prior own spy')
    # No completion occurrence is reopened or queried by the effect readback.
    return source(turn, pid, None) + f'''
local action,old={literal(action)},{literal(old)}
local definition=GameInfo.UnitOperations[action.operation_type]
assert(definition and hash(definition.Hash)==action.operation_hash,'renew operation identity changed')
local unit=player:GetUnits():FindID(action.unit_id)
local applied=false
if unit~=nil then
 assert(unit:GetOwner()==pid and GameInfo.Units[unit:GetUnitType()].Spy,'renew effect unit is not an own spy')
 local operation=int(unit:GetSpyOperation(),'renew effect operation',-1,2147483647)
 local remaining=0
 if operation~=-1 then remaining=math.max(0,int(unit:GetSpyOperationEndTurn(),'renew effect end',-2147483648,2147483647)-turn)end
 applied=operation==definition.Index and (old.operation~=operation or old.turns_remaining~=remaining)
end
ready();return encode({{player_id=pid,turn=turn,event_sequence=action.event_sequence,mission_id=action.mission_id,
 unit_id=action.unit_id,operation=definition.Index,applied=applied}})
'''.encode()


def read_effect(prefix, action, before, after):
    """Confirm a native transition using the regular espionage before/after state."""
    raw = prefix.runtime.evaluate_text(
        prefix.ui_child, effect_source(action, before, after), b'@spy_completion_effect', capacity=4097,
    )
    result = _decode(raw, 4096)
    expected = {'player_id': before['player_id'], 'turn': before['turn'],
                'event_sequence': action['event_sequence'], 'mission_id': action['mission_id'],
                'unit_id': action['unit_id']}
    if (type(result) is not dict or set(result) != set(expected) | {'operation', 'applied'}
            or any(type(result[key]) is not int or result[key] != val for key, val in expected.items())
            or type(result['operation']) is not int or not 0 <= result['operation'] <= 0x7fffffff
            or type(result['applied']) is not bool):
        raise ValueError('Malformed renewal effect receipt')
    # Bind the independent native read to the public after-catalogue as well.
    current = next((row for row in after['spies'] if row['unit_id'] == action['unit_id']), None)
    applied = result['applied'] and current is not None and current['operation'] == result['operation']
    return {'applied': applied, 'pending': not applied}

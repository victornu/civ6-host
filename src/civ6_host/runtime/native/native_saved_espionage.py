"""Player-scoped XP2 espionage queries and official request signatures.

Renewal is deliberately unsupported: history does not prove a live completion
popup. Escape requires a live, local notification before reading the next spy;
an unresolved escape blocker without that notification is an explicit refusal.
The installed Lua files qualify the information boundary, not native execution.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from civ6_host.contracts.espionage import (
    SCHEMA, actions, validate_action, validate_catalogue,
)
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.native.native_saved_trade import COMMON_LUA, literal
from civ6_host.runtime.native.native_saved_unit_orders import uint

LIMIT = 1048576
GAME_ROOT = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization VI")
BBG_ROOT = Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/289070/2865001760')
_GAME_PINS = {
    'Base/Assets/UI/Choosers/EspionageChooser.lua': 'b071f096a84a8de0d74f07343f30263ec9897e5d1694548ae7058d3ff7d1d9d7',
    'Base/Assets/UI/PartialScreens/EspionageOverview.lua': 'ecdfce6f13206066475a7f605ae7c8ef18a293a340e3c6072de4cfdfd82d461b',
    'Base/Assets/UI/Popups/EspionagePopup.lua': 'b35c4d8399e6ff72faf3cc965a8c9aa08ff6c25fc3e5006c0069ec962cbda7db',
    'Base/Assets/UI/Popups/EspionageEscape.lua': '1ec7b20f8ed942a311aa1770411041bc5986a0d80aff9bd766347771d38d98f6',
    'Base/Assets/UI/EspionageSupport.lua': '41bafc4baa56eebcecee1a4326bb32c8315870cf9d183e6af0389e4351ae531d',
    'Base/Assets/UI/Panels/UnitPanel.lua': '6d029bfa8f7119c18ee88956ef775f7d05a57aae9d2ffe3be60c256c7a8d5b6e',
    'Base/Assets/UI/Panels/NotificationPanel.lua': '7349e5fbe8e9e5999648791af0b96f3fc470aa6e8cd66309e32f01918b8c80c2',
    'Base/Assets/UI/ActionPanel.lua': '1a290b0e33c24c5b78515b58447768a6ecc3382387e0fdf6928b10f408875da3',
    'DLC/Expansion2/UI/Replacements/EspionageChooser_Expansion1.lua': 'bacf7896d03d557491d36a7e4316acafd4e80f98665c8e6dd86a4661ef27d2bf',
    'DLC/Expansion2/UI/Replacements/EspionageOverview_Expansion1.lua': '026506c550983a6ed28a35df8d7a5b8281a3cfefb5a894575ab21e0a7b3330c8',
    'DLC/Expansion2/UI/Replacements/UnitPanel_Expansion1.lua': '863e04803f1eee1d94466a87cd0d93a149ce25ee5c952ef7b3fc31ab48370924',
    'DLC/Expansion2/UI/Replacements/UnitPanel_Expansion2.lua': 'c4e930f6bffead7b5c1c92658fe89c8daae162c41e489be6a64bb2636212a81d',
}
_BBG_PINS = {
    'BetterBalancedGame.modinfo': 'f4f918bd18a7189d9f8ee64a4123952e72bded754e5154d7521d25f90bf305a5',
    'ui/replacements/unitpanel_bbg.lua': '8693e6708c30e5630eec62b12a8b6249ccb0f6a7c8be801132e2645ad00e308b',
}


def verify_source():
    """Verify and return the exact installed UI dependency map."""
    result = {}
    for namespace, root, pins in (('game', GAME_ROOT, _GAME_PINS), ('bbg', BBG_ROOT, _BBG_PINS)):
        for name, digest in pins.items():
            path = resolve_path(root / name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Installed espionage UI source changed: ' + name)
            result[namespace + '/' + name] = {'path': str(path), 'sha256': digest}
    return result


# Reuse the owned bounded JSON serializer, equality and readiness primitives.
# Error labels change only; no official Lua bodies are copied into this module.
LUA = 'local json_null={}\n' + COMMON_LUA.replace('trade', 'espionage').replace(
    "if type(v)=='string'then", "if v==json_null then return 'null'\n elseif type(v)=='string'then",
) + r'''
local function push(rows,value)
 assert(#rows<4096,'espionage row limit exceeded');rows[#rows+1]=value
end
local function hash(v)return int(v,'operation hash',-2147483648,4294967295)%4294967296 end
local function xy(plot)return {[UnitOperationTypes.PARAM_X]=plot:GetX(),[UnitOperationTypes.PARAM_Y]=plot:GetY()} end
local function ownSpy(id)
 local u=player:GetUnits():FindID(id)
 if u then
  assert(u:GetOwner()==pid and GameInfo.Units[u:GetUnitType()].Spy,'foreign/non-spy unit')
 end
 return u
end
local function escapingSpy()
 local kinds={NotificationTypes.SPY_CHOOSE_ESCAPE_ROUTE,NotificationTypes.SPY_CHOOSE_DRAGNET_PRIORITY}
 assert(kinds[1] and kinds[2],'escape notification enums absent')
 local active=false
 for _,kind in ipairs(kinds)do
  local n=NotificationManager.FindType(kind,pid)
  if n~=nil then
   assert(n:GetPlayerID()==pid and n:GetType()==kind,'foreign escape notification')
   if not boolean(n:IsDismissed(),'notification dismissed')then active=true end
  end
 end
 local blocks=NotificationManager.GetAllEndTurnBlocking(pid);dense(blocks,128)
 local escapeBlock=EndTurnBlockingTypes.ENDTURN_BLOCKING_SPY_CHOOSE_ESCAPE_ROUTE
 local dragnetBlock=EndTurnBlockingTypes.ENDTURN_BLOCKING_SPY_CHOOSE_DRAGNET_PRIORITY
 assert(type(escapeBlock)=='number' and type(dragnetBlock)=='number','escape blockers absent')
 for _,block in ipairs(blocks)do
  int(block,'blocker',-2147483648,4294967295)
  assert(active or (block~=escapeBlock and block~=dragnetBlock),
   'escape blocker lacks a qualified active local notification')
 end
 if not active then return nil end
 -- The UI reads this only after a local notification, never by guessing a sentinel.
 local id=int(player:GetDiplomacy():GetNextEscapingSpyID(),'escaping spy',0,4294967295)
 local u=ownSpy(id);assert(u,'active escape notification has no own spy');return u
end
local function probabilities(op,u,target)
 if op.Hash==UnitOperationTypes.SPY_COUNTERSPY then return -1,-1,-1 end
 local r=UnitManager.GetResultProbability(op.Index,u,target)
 assert(type(r)=='table','mission probabilities absent')
 if r.ESPIONAGE_SUCCESS_UNDETECTED==nil then return -1,-1,-1 end
 local function probability(key)
  local v=r[key];if v==nil then return 0 end
  finite(v);assert(v>=0 and v<=1,'invalid mission probability');return v
 end
 local success=math.floor(100*(probability('ESPIONAGE_SUCCESS_UNDETECTED')+probability('ESPIONAGE_SUCCESS_MUST_ESCAPE'))+0.5)
 int(success,'success percent',0,100)
 if success==100 then return success,-1,-1 end
 local failure=math.floor(100*(probability('ESPIONAGE_FAIL_UNDETECTED')+probability('ESPIONAGE_FAIL_MUST_ESCAPE'))+0.5)
 int(failure,'failure percent',0,100)
 local lost=100-success-failure;int(lost,'lost percent',0,100)
 return success,failure,lost
end
local function snapshot()
 local p=ready();local diplomacy=p:GetDiplomacy()
 local out={schema='civ6-host.espionage.v1',player_id=pid,turn=turn,width=width,height=height,
  capacity=int(diplomacy:GetSpyCapacity(),'capacity',0,2147483647),spies=array(),captured=array(),off_map=array(),history=array(),offers=array()}
 local choices,units,seen={}, {}, {}
 local function offer(action,unit,operation,params,turns,target,op,city)
  local s,f,k=-1,-1,-1;if op then s,f,k=probabilities(op,unit,target)end
  push(out.offers,{action=action,turns=int(turns,'duration',-1,2147483647),success_percent=s,failure_percent=f,captured_or_killed_percent=k})
  push(choices,{action=action,unit=unit,operation=operation,params=params,target=target,city=city})
 end
 for _,u in p:GetUnits():Members()do
  local id=int(u:GetID(),'unit identity',0,4294967295)
  assert(u:GetOwner()==pid and not seen[id],'foreign/duplicate own unit');seen[id]=true
  local def=GameInfo.Units[u:GetUnitType()];assert(def,'unit definition absent')
  if def.Spy then
   local op=int(u:GetSpyOperation(),'operation',-1,2147483647)
   local remaining=0;if op~=-1 then remaining=math.max(0,int(u:GetSpyOperationEndTurn(),'operation end',-2147483648,2147483647)-turn)end
   push(out.spies,{unit_id=id,name=text(u:GetName()),level=int(u:GetExperience():GetLevel(),'level',0,2147483647),
    x=int(u:GetX(),'spy x',0,width-1),y=int(u:GetY(),'spy y',0,height-1),operation=op,turns_remaining=remaining})
   push(units,u)
  end
 end
 local players=Game.GetPlayers();dense(players,64);local playerSeen={}
 for _,other in ipairs(players)do
  local otherID=int(other:GetID(),'other player',0,63)
  assert(not playerSeen[otherID],'duplicate player');playerSeen[otherID]=true
  local d=other:GetDiplomacy();local count=int(d:GetNumSpiesCaptured(),'captured count',0,4096)
  for n=0,count-1 do
   local r=d:GetNthCapturedSpy(otherID,n)
   if r and (r.OwningPlayer==pid or otherID==pid) then
    local level=json_null;if r.OwningPlayer==pid then level=int(r.Level,'level',0,2147483647)end
    push(out.captured,{owner=int(r.OwningPlayer,'captured owner',0,63),captor=otherID,name_index=int(r.NameIndex,'name index',0,2147483647),name=text(r.Name),level=level})
   end
  end
 end
 local offCount=int(diplomacy:GetNumSpiesOffMap(),'off-map count',0,4096)
 for n=0,offCount-1 do
  local r=diplomacy:GetNthOffMapSpy(pid,n)
  if r and r.ReturnTurn~=-1 then
   push(out.off_map,{name=text(r.Name),level=int(r.Level,'level',0,2147483647),return_turn=int(r.ReturnTurn,'return turn',-2147483648,2147483647),
    x=int(r.XLocation,'off-map x',0,width-1),y=int(r.YLocation,'off-map y',0,height-1)})
  end
 end
 local history=diplomacy:GetRecentMissions(pid,10,0)
 if history~=nil then
  assert(type(history)=='table','history table absent');local count=0
  for _,r in pairs(history)do
   count=count+1;assert(count<=10,'unbounded mission history')
   local unresolved=(r.InitialResult==EspionageResultTypes.SUCCESS_MUST_ESCAPE or r.InitialResult==EspionageResultTypes.FAIL_MUST_ESCAPE)
    and r.EscapeResult==EspionageResultTypes.NO_RESULT
   if not unresolved then
    push(out.history,{name=text(r.Name),level=int(r.LevelAfter,'history level',-2147483648,2147483647),operation=int(r.Operation,'history operation',-2147483648,2147483647),
     completion_turn=int(r.CompletionTurn,'completion turn',-2147483648,2147483647),initial_result=int(r.InitialResult,'initial result',-2147483648,2147483647),
     escape_result=int(r.EscapeResult,'escape result',-2147483648,2147483647),city_name=text(r.CityName),plot_id=int(r.PlotIndex,'history plot',-1,width*height-1),
     loot_info=int(r.LootInfo,'loot info',-2147483648,2147483647)})
   end
  end
 end
 local escaping=escapingSpy()
 if escaping then
  local plot=Map.GetPlot(escaping:GetX(),escaping:GetY());local city=Cities.GetPlotPurchaseCity(plot)
  assert(city,'escaping spy city absent')
  for _,kind in ipairs({'DISTRICT_AERODROME','DISTRICT_HARBOR','DISTRICT_COMMERCIAL_HUB','DISTRICT_CITY_CENTER'})do
   local def=GameInfo.Districts[kind];assert(def,'escape district definition absent')
   if kind=='DISTRICT_CITY_CENTER' or boolean(city:GetDistricts():HasDistrict(def.Index,true,true),'escape district')then
    local params={[PlayerOperations.PARAM_DISTRICT_TYPE]=def.Index}
    offer({kind='spy_escape',unit_id=escaping:GetID(),district_index=int(def.Index,'district',0,2147483647)},escaping,PlayerOperations.SET_ESCAPE_ROUTE,params,def.TravelTime)
   end
  end
 end
 for _,u in ipairs(units)do
  local id=u:GetID()
  if boolean(UnitManager.CanStartCommand(u,UnitCommandTypes.CANCEL,true),'cancel visible')then
   -- The official spy-specific button queries this boolean but does not disable
   -- its callback with it. Application/refusal is measured after native delivery.
   boolean(UnitManager.CanStartCommand(u,UnitCommandTypes.CANCEL,false,true),'cancel now')
   offer({kind='spy_cancel',unit_id=id},u,UnitCommandTypes.CANCEL,nil,-1)
  end
  if u:GetMovesRemaining()>0 then
   local ownPlot=Map.GetPlot(u:GetX(),u:GetY());local currentCity=Cities.GetPlotPurchaseCity(ownPlot)
   local travel=GameInfo.UnitOperations['UNITOPERATION_SPY_TRAVEL_NEW_CITY'];assert(travel,'travel definition absent')
   if travel.VisibleInUI and boolean(UnitManager.CanStartOperation(u,travel.Hash,nil,true),'travel visible')
    and boolean(UnitManager.CanStartOperation(u,travel.Hash,nil,false,OperationResultsTypes.NO_TARGETS),'travel now')then
    for _,other in ipairs(players)do
     local state=int(other:GetDiplomaticAI():GetDiplomaticStateIndex(pid),'diplomatic state',-1,2147483647)
     if state~=-1 then
      local def=GameInfo.DiplomaticStates[state];assert(def,'diplomatic state definition absent')
      if def.StateType~='DIPLO_STATE_ALLIED' and not other:IsFreeCities()
       and (other:GetID()==pid or other:GetTeam()==-1 or p:GetTeam()==-1 or other:GetTeam()~=p:GetTeam())then
       for _,city in other:GetCities():Members()do
        assert(city:GetOwner()==other:GetID(),'foreign destination city')
        if boolean(PlayersVisibility[pid]:IsRevealed(city:GetX(),city:GetY()),'city revealed')then
         local sameOwn=city:GetOwner()==pid and currentCity and currentCity:GetOwner()==pid and currentCity:GetID()==city:GetID()
         if not sameOwn then
          local target=Map.GetPlot(city:GetX(),city:GetY());local params=xy(target)
          if boolean(UnitManager.CanStartOperation(u,travel.Hash,target,params),'travel destination')then
           offer({kind='spy_travel',unit_id=id,city_owner=city:GetOwner(),city_id=int(city:GetID(),'city identity',0,4294967295),x=target:GetX(),y=target:GetY()},
            u,travel.Hash,params,UnitManager.GetTravelTime(u,city)+UnitManager.GetEstablishInCityTime(u,city),target,nil,city)
          end
         end
        end
       end
      end
     end
    end
   end
   if currentCity then
    local cityPlot=Map.GetPlot(currentCity:GetX(),currentCity:GetY());local own=currentCity:GetOwner()==pid
    for op in GameInfo.UnitOperations()do
     local counter=op.OperationType=='UNITOPERATION_SPY_COUNTERSPY'
     if (own and counter) or (not own and op.CategoryInUI=='OFFENSIVESPY')then
      local visible
      if counter then visible=UnitManager.CanStartOperation(u,op.Hash,nil,true)
      else visible=UnitManager.CanStartOperation(u,op.Hash,nil,false,false)end
      if boolean(visible,'mission chooser')then
       local can,r=UnitManager.CanStartOperation(u,op.Hash,cityPlot,false,true)
       if boolean(can,'mission now')then
        local targets={};local plots=r and r[UnitOperationResults.PLOTS]
        if plots~=nil then
         dense(plots,4096)
         for _,index in ipairs(plots)do
          int(index,'mission plot',0,width*height-1);local target=Map.GetPlotByIndex(index)
          if target then push(targets,target)end
         end
        end
        if counter then assert(plots,'counterspy targets missing')
        elseif #targets==0 then targets={cityPlot}end
        for _,target in ipairs(targets)do
         local params=nil;if counter then params=xy(target)end
         local action={kind='spy_mission',unit_id=id,operation_type=text(op.OperationType),operation_hash=hash(op.Hash),
          mode=counter and 'counterspy' or 'start',x=target:GetX(),y=target:GetY(),plot_id=target:GetIndex()}
         offer(action,u,op.Hash,params,UnitManager.GetTimeToComplete(op.Index,u),target,op,cityPlot)
        end
       end
      end
     end
    end
   end
  end
 end
 ready();return out,choices
end
'''


def source(turn, player_id=0):
    uint(turn, 'turn', 2147483647)
    uint(player_id, 'player', 63)
    verify_source()
    return f'local pid,turn={player_id},{turn}\n'.encode() + LUA.encode()


def parse(raw, turn, player_id=0):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded espionage wire')

    def unique(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('Duplicate espionage JSON key')
            result[key] = value
        return result

    return validate_catalogue(json.loads(raw, object_pairs_hook=unique), player_id, turn)


def catalog(prefix, turn, player_id=0):
    raw = prefix.runtime.evaluate_text(
        prefix.ui_child, source(turn, player_id) + b'\nlocal result=snapshot();return encode(result)',
        b'@explicit_espionage_catalog', capacity=LIMIT + 1,
    )
    return parse(raw, turn, player_id)


def _validate_requested(action, catalogue):
    validate_catalogue(catalogue, catalogue['player_id'], catalogue['turn'])
    validate_action(action, catalogue['width'], catalogue['height'])
    if action.get('mode') == 'renew':
        raise ValueError('Espionage renewal requires qualified completion notification identity')
    if action not in actions(catalogue):
        raise ValueError('Espionage action outside native offers')


def request_source(action, catalogue):
    _validate_requested(action, catalogue)
    return source(catalogue['turn'], catalogue['player_id']) + f'''
local selected={literal(action)}
local observed,choices=snapshot();local found=nil
for _,choice in ipairs(choices)do
 if same(choice.action,selected)then assert(not found,'duplicate espionage choice');found=choice end
end
if not found then return 'refused' end
ready()
if selected.kind=='spy_cancel' then
 UnitManager.RequestCommand(found.unit,UnitCommandTypes.CANCEL)
elseif selected.kind=='spy_escape' then
 local current=escapingSpy();if not current or current:GetID()~=selected.unit_id then return 'refused' end
 UI.RequestPlayerOperation(pid,PlayerOperations.SET_ESCAPE_ROUTE,found.params)
elseif selected.kind=='spy_travel' then
 if not boolean(UnitManager.CanStartOperation(found.unit,found.operation,found.target,found.params),'travel request')then return 'refused' end
 UnitManager.RequestOperation(found.unit,found.operation,found.params)
else
 if not boolean(UnitManager.CanStartOperation(found.unit,found.operation,found.city,false,true),'mission request')then return 'refused' end
 if selected.mode=='counterspy' then UnitManager.RequestOperation(found.unit,found.operation,found.params)
 else UnitManager.RequestOperation(found.unit,found.operation)end
end
return 'submitted'
'''.encode()


def effect_source(action, before):
    """Read exact postconditions; false means unconfirmed, not simulated success."""
    _validate_requested(action, before)
    old_spy = next(row for row in before['spies'] if row['unit_id'] == action['unit_id'])
    return source(before['turn'], before['player_id']) + f'''
local selected,old={literal(action)},{literal(old_spy)}
local state=snapshot();local confirmed=false;local expected=-1
local current=nil;for _,row in ipairs(state.spies)do if row.unit_id==selected.unit_id then current=row end end
if selected.kind=='spy_mission' then
 local def=GameInfo.UnitOperations[selected.operation_type]
 assert(def and hash(def.Hash)==selected.operation_hash,'mission definition changed');expected=def.Index
 confirmed=current~=nil and current.operation==expected and
  (old.operation~=expected or current.turns_remaining~=old.turns_remaining)
elseif selected.kind=='spy_cancel' then confirmed=old.operation~=-1 and current~=nil and current.operation==-1
elseif selected.kind=='spy_travel' then
 local count=0
 for _,row in ipairs(state.off_map)do
  if row.name==old.name and row.x==selected.x and row.y==selected.y and row.return_turn~=-1 then count=count+1 end
 end
 confirmed=current==nil and count==1
elseif selected.kind=='spy_escape' then
 local escaping=escapingSpy();confirmed=escaping==nil or escaping:GetID()~=selected.unit_id
end
ready();return encode({{schema='civ6-host.espionage-effect.v1',player_id=pid,turn=turn,
 kind=selected.kind,unit_id=selected.unit_id,confirmed=confirmed,expected_operation=expected}})
'''.encode()


def read_effect(prefix, action, before_catalogue, refreshed_catalogue):
    """Separate request delivery from a native state transition after publication."""
    pid, turn = before_catalogue['player_id'], before_catalogue['turn']
    validate_catalogue(refreshed_catalogue, pid, turn)
    raw = prefix.runtime.evaluate_text(
        prefix.ui_child, effect_source(action, before_catalogue),
        b'@explicit_espionage_effect', capacity=4097,
    )
    if type(raw) is not bytes or len(raw) > 4096:
        raise ValueError('Invalid espionage effect wire')
    result = json.loads(raw)
    fields = {'schema', 'player_id', 'turn', 'kind', 'unit_id', 'confirmed', 'expected_operation'}
    if (type(result) is not dict or set(result) != fields
            or result['schema'] != 'civ6-host.espionage-effect.v1'
            or type(result['player_id']) is not int or result['player_id'] != pid
            or type(result['turn']) is not int or result['turn'] != turn
            or result['kind'] != action['kind']
            or type(result['unit_id']) is not int or result['unit_id'] != action['unit_id']
            or type(result['confirmed']) is not bool
            or type(result['expected_operation']) is not int
            or not -1 <= result['expected_operation'] <= 2147483647):
        raise ValueError('Malformed espionage effect receipt')
    return {'applied': result['confirmed'], 'pending': not result['confirmed']}

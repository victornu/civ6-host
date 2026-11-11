"""Trade overview query for an explicitly selected UI profile.

The selection must be admitted by the saved-session owner before this query is
wired into its decision boundary. Installing BBG alone does not select its UI.
"""
from hashlib import sha256
from pathlib import Path
import re

from civ6_host.contracts import trade_overview
from civ6_host.contracts.trade import uint
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.resources import _parse_json_object
from .native_saved_trade import COMMON_LUA, LIMIT
from .native_source_cache import load_pinned_json

_STATIC = ('work/trade-common-client/xp2-bbg-player-trade-overview-source.json',
           'be013a3d634734a6038dbc6aa4f367c7972b4802359feb4b3c26954dacd63677')
_SELECTION = ('work/trade-common-client/xp2-bbg-trade-ui-selected-witness.json',
              '9e3d182046c8ed8acac127cfb812b3ddd5bfe48a15cc61735cfccd4dbae61d10')
_STOCK = ('work/official-capture/bbg751-world-A-trade-ui-association/stock-trade-ui-capture-selection.json',
          '3513eee4298b47fc1cf4d79aa4aed9e0752a1c9d6e434ff915782753596e227e')
_ROUND_SHA256 = '8c49e8f9a28f73c5da9e4258f813d5d0ff66863fd02cb0ca43cb397a1711c93b'
_HOOKS_SHA256 = '9da7a774361a23dab2a6883e85a9888b3a47487d627bdee43657718c41de0409'
_CAPABILITIES_SHA256 = '0e81de39aa32033e4b3ed0660e72f6ca63f3f3bec28ec35d3b61ef780f1ceb0c'
_HELPER_NAMES = 'GetIdleTradeUnits, GetYieldsForRoute, GetReligiousPressureForCity'

CIVIC_CAPACITY_LUA = b"""
assert(Game.GetLocalPlayer()==0,'trade civic perspective changed')
local player=assert(Players[0],'local trade civic player unavailable')
local turn=Game.GetCurrentGameTurn()
local capacity=player:GetTrade():GetOutgoingRouteCapacity()
assert(type(turn)=='number' and turn%1==0 and turn>=0 and turn<=2147483647,
       'trade civic turn is out of bounds')
assert(type(capacity)=='number' and capacity%1==0 and capacity>=0 and capacity<=2147483647,
       'trade civic capacity is out of bounds')
return tostring(turn)..':'..tostring(capacity)
"""


def parse_civic_capacity(raw):
    if type(raw) is not bytes or re.fullmatch(rb'[0-9]{1,10}:[0-9]{1,10}', raw) is None:
        raise ValueError('Malformed trade civic capacity readback')
    turn, capacity = map(int, raw.split(b':'))
    return (uint(turn, 'trade civic turn', 2**31 - 1),
            uint(capacity, 'trade civic capacity', 2**31 - 1))


def stock_capture_source():
    stock = load_pinned_json(resolve_path(resource_root() / _STOCK[0]), _STOCK[1])
    if stock['schema'] != 'civ6-host.stock-expansion-trade-ui-capture-selection.v1':
        raise ValueError('Unknown standard trade overview source')
    return stock


def _installed_sources(profile=trade_overview.PROFILE):
    root = resource_root()
    if profile == trade_overview.STOCK_PROFILE:
        stock = stock_capture_source()
        panel = stock['stock_panel']
        files = {'stock_overview': panel, 'stock_support': stock['stock_helper']}
    elif profile == trade_overview.PROFILE:
        static = load_pinned_json(resolve_path(root / _STATIC[0]), _STATIC[1])
        selection = load_pinned_json(resolve_path(root / _SELECTION[0]), _SELECTION[1])
        if (static['schema'] != 'civ6-host.xp2-bbg-player-trade-overview-source.v1'
                or selection['schema'] != 'civ6-host.xp2-bbg-trade-ui-selected-witness.v1'
                or selection['static_inventory']['sha256'] != _STATIC[1]):
            raise ValueError('Unknown BBG trade overview source')
        inputs = static['inputs']
        panel = inputs['stock_overview']
        files = {name: inputs[name] for name in ('modinfo', 'bbg_support', 'bbg_base_overview', 'bbg_overview')}
    else:
        raise ValueError('Unknown trade overview display profile')
    ui = Path(panel['path']).parent
    return {name: (resolve_path(Path(row['path'])), row['sha256']) for name, row in files.items()} | {
                'round': (resolve_path(ui / 'SupportFunctions.lua'), _ROUND_SHA256),
                'hooks': (resolve_path(ui / 'PartialScreenHooks.lua'), _HOOKS_SHA256),
                'capabilities': (resolve_path(ui / 'Scripts/GameCapabilities.lua'), _CAPABILITIES_SHA256)}


def source_dependencies(profile=trade_overview.PROFILE):
    """Return pins for parent/worker provenance of the selected query."""
    root = resource_root()
    sources = _installed_sources(profile)
    evidence = (_STOCK,) if profile == trade_overview.STOCK_PROFILE else (_STATIC, _SELECTION)
    dependencies = {str(resolve_path(root / path)): digest for path, digest in evidence}
    for path, digest in sources.values():
        _pinned_bytes(path, digest)
        dependencies[str(path)] = digest
    return dependencies


def _pinned_bytes(path, digest):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError('Official trade overview source changed: ' + str(path))
    return raw


def _untyped_lua(text):
    def arguments(match):
        return re.sub(r':(?:number|table|boolean|string)\b', '', match[0])

    text = re.sub(r'(?m)^(?:local )?function \w+\([^\n]*\)', arguments, text)
    return re.sub(r'(?m)^(\s*local\s+\w+):(?:number|table|boolean|string)\b', r'\1', text)


def _trade_support(path, digest):
    helper = _pinned_bytes(path, digest).decode('utf-8-sig')
    header, _, body = helper.partition('\n')
    if header.rstrip('\r') != 'print("TradeSupport BBG overide loaded")':
        raise ValueError('BBG TradeSupport entry point changed')
    return _untyped_lua('local ' + _HELPER_NAMES + '\n' + body + '\n')


def bbg_support_source():
    return _trade_support(*_installed_sources()['bbg_support']).encode('utf-8')


def _official_helpers(profile):
    sources = _installed_sources(profile)
    if profile == trade_overview.STOCK_PROFILE:
        body = _pinned_bytes(*sources['stock_support']).decode('utf-8-sig')
        trade_support = _untyped_lua('local ' + _HELPER_NAMES + '\n' + body + '\n')
    else:
        trade_support = _trade_support(*sources['bbg_support'])
    support = _pinned_bytes(*sources['round']).decode('utf-8-sig').replace('\r\n', '\n')
    start = support.index('function Round(')
    end = support.index('\nend', start) + len('\nend')
    round_source = support[start:end]
    capabilities = _pinned_bytes(*sources['capabilities']).decode('utf-8-sig').replace('\r\n', '\n')
    start = capabilities.index('function HasCapability(')
    end = capabilities.index('\nend', start) + len('\nend')
    return trade_support + _untyped_lua('local ' + round_source + '\nlocal ' + capabilities[start:end] + '\n')


LUA = r'''
local function quoteFor(origin,destination,reverse)
 local quote=GetYieldsForRoute(origin,destination,reverse)
 local values=array()
 dense(quote.kYieldValues,64)
 for _,amount in ipairs(quote.kYieldValues) do
  values[#values+1]=Round(finite(amount),1)
 end
 local religion=int(quote.MajorityReligion,'religion',-1,2147483647)
 local pressure=finite(quote.ReligionPressure)
 if religion>0 and pressure>0 then
  pressure=Round(pressure,1)
 else
  religion,pressure=-1,-1
 end
 return {values=values,majority_religion=religion,religion_pressure=pressure,
  path_bonus=boolean(quote.HasPathBonus,'path bonus'),tooltip=text(quote.TooltipText)}
end

local function row(origin,destination,originPlayer)
 local originOwner=origin:GetOwner()
 assert(originPlayer:GetID()==originOwner,'foreign trade origin object')
 return {
  origin_owner=int(originOwner,'origin owner',0,63),
  origin_city=int(origin:GetID(),'origin city',0,4294967295),
  destination_owner=int(destination:GetOwner(),'destination owner',0,63),
  destination_city=int(destination:GetID(),'destination city',0,4294967295),
  origin_name=text(origin:GetName()),destination_name=text(destination:GetName()),
  distance=int(Map.GetPlotDistance(origin:GetX(),origin:GetY(),destination:GetX(),destination:GetY()),
   'distance',0,16384),
  has_post=boolean(destination:GetTrade():HasActiveTradingPost(originPlayer),'overview trading post'),
  origin_yields=quoteFor(origin,destination,false),
  destination_yields=quoteFor(origin,destination,true),
 }
end

local function add(rows,value)
 assert(#rows<4096,'trade overview rows exceed bound')
 rows[#rows+1]=value
end

local function routeOrder(a,b)
 if a.origin_owner~=b.origin_owner then return a.origin_owner<b.origin_owner end
 if a.origin_city~=b.origin_city then return a.origin_city<b.origin_city end
 if a.destination_owner~=b.destination_owner then return a.destination_owner<b.destination_owner end
 if a.destination_city~=b.destination_city then return a.destination_city<b.destination_city end
 return (a.unit_id or -1)<(b.unit_id or -1)
end

local function unavailable(status)
 ready()
 return encode({status=status,player_id=pid,turn=turn,sequence=sequence})
end

local function snapshot()
 local p=ready();assert(p:GetID()==pid,'foreign trade overview player')
 if stock then
  local congress=assert(Game.GetWorldCongress(),'standard trade Congress interface unavailable')
  if boolean(congress:IsInSession(),'standard trade Congress phase') then
   return unavailable('ui_boundary_unavailable')
  end
 end
 if not HasCapability('CAPABILITY_TRADE_VIEW') then return unavailable('trade_view_disabled') end
 local trade=p:GetTrade()
 local capacity=int(trade:GetOutgoingRouteCapacity(),'capacity',0,2147483647)
 -- The official hook stays unlocked even after outgoing capacity falls to zero.
 if not unlocked and (not check_capacity or capacity==0) then
  return unavailable('unlock_history_unavailable')
 end
 local active=int(trade:GetNumOutgoingRoutes(),'active count',0,2147483647)
 local spare=math.max(0,capacity-active)
 local idle=array()
 if spare>0 then
  local offered=GetIdleTradeUnits(pid)
  dense(offered,4096)
  for i=1,math.min(spare,#offered) do
   local unit=offered[i]
   assert(unit:GetOwner()==pid,'foreign idle trader')
   idle[#idle+1]=int(unit:GetID(),'idle trader',0,4294967295)
  end
 end
 local result={schema=schema,profile=profile,player_id=pid,turn=turn,sequence=sequence,
  active_count=active,capacity=capacity,idle_trader_ids=idle,produce_trader_slots=spare-#idle,
  own_routes=array(),incoming_routes=array(),available_routes=array()}
 local ownCities=p:GetCities()
 local manager=assert(Game.GetTradeManager(),'trade overview manager missing')
 for _,origin in ownCities:Members() do
  assert(origin:GetOwner()==pid,'foreign city in trade overview origin roster')
  local outgoing=origin:GetTrade():GetOutgoingRoutes()
  dense(outgoing,4096)
  for _,route in ipairs(outgoing) do
   assert(route.OriginCityPlayer==pid and route.OriginCityID==origin:GetID(),'own route origin differs')
   local receiver=assert(Players[route.DestinationCityPlayer],'own route receiver unavailable')
   local dest=assert(receiver:GetCities():FindID(route.DestinationCityID),'own route destination unavailable')
   assert(dest:GetOwner()==route.DestinationCityPlayer and dest:GetID()==route.DestinationCityID,
    'own route destination differs')
   local item=row(origin,dest,p)
   item.unit_id=int(route.TraderUnitID,'active trader',0,4294967295)
   add(result.own_routes,item)
  end
 end
 local players=Game.GetPlayers()
 dense(players,64)
 for _,other in ipairs(players) do
  local otherID=int(other:GetID(),'player',0,63)
  for _,city in other:GetCities():Members() do
   local cityID=city:GetID()
   assert(city:GetOwner()==otherID,'foreign city in trade overview destination roster')
   if otherID~=pid then
    local outgoing=city:GetTrade():GetOutgoingRoutes()
    dense(outgoing,4096)
    for _,route in ipairs(outgoing) do
     if route.DestinationCityPlayer==pid then
      assert(route.OriginCityPlayer==otherID and route.OriginCityID==cityID,'incoming route origin differs')
      local dest=assert(ownCities:FindID(route.DestinationCityID),'incoming route destination unavailable')
      assert(dest:GetOwner()==pid and dest:GetID()==route.DestinationCityID,'incoming route destination differs')
      add(result.incoming_routes,row(city,dest,other))
     end
    end
   end
   for originID,origin in ownCities:Members() do
    -- The standard view looks up the ID and skips a missing city.
    if stock then origin=ownCities:FindID(originID) end
    if origin~=nil then
     assert(origin:GetOwner()==pid,'foreign available route origin')
     if boolean(manager:CanStartRoute(pid,origin:GetID(),otherID,cityID,true),'available route') then
      add(result.available_routes,row(origin,city,p))
     end
    elseif not stock then
     error('missing BBG available route origin')
    end
   end
  end
 end
 for _,field in ipairs({'own_routes','incoming_routes','available_routes'}) do
  table.sort(result[field],routeOrder)
 end
 ready()
 return encode(result)
end
return snapshot()
'''


def source(player_id, turn, sequence, *, check_capacity, unlocked=False, profile=trade_overview.PROFILE):
    """Build a protected, read-only Lua query for the selected display variant."""
    uint(player_id, 'overview player', 63)
    uint(turn, 'overview turn', 2**31 - 1)
    uint(sequence, 'overview sequence', 2**31 - 1)
    if type(check_capacity) is not bool or type(unlocked) is not bool:
        raise ValueError('Trade overview unlock admission must be Boolean')
    helpers = _official_helpers(profile)
    stock = profile == trade_overview.STOCK_PROFILE
    return (f'local pid,turn,sequence={player_id},{turn},{sequence}\n'
            f'local schema,profile="{trade_overview.SCHEMA}","{profile}"\n'
            f'local stock={str(stock).lower()}\n'
            f'local check_capacity={str(check_capacity).lower()}\n'
            f'local unlocked={str(unlocked).lower()}\n'
            + helpers + COMMON_LUA + LUA).encode('utf-8')


def parse(raw, player_id, turn, sequence, *, profile=trade_overview.PROFILE):
    if profile not in trade_overview.PROFILES:
        raise ValueError('Unknown trade overview display profile')
    if type(raw) is not bytes or not 0 < len(raw) <= LIMIT:
        raise ValueError('Unbounded trade overview wire')
    value = _parse_json_object(raw, 'Trade overview')
    if 'status' in value:
        status = value['status']
        statuses = trade_overview.NATIVE_UNAVAILABLE
        if profile == trade_overview.STOCK_PROFILE:
            statuses = statuses | {'ui_boundary_unavailable'}
        if (set(value) != {'status', 'player_id', 'turn', 'sequence'}
                or type(status) is not str or status not in statuses
                or uint(value['player_id'], 'overview player', 63) != player_id
                or uint(value['turn'], 'overview turn', 2**31 - 1) != turn
                or uint(value['sequence'], 'overview sequence', 2**31 - 1) != sequence):
            raise ValueError('Foreign trade overview availability')
        return None, status
    return trade_overview.validate(value, player_id, turn, sequence, profile=profile), 'available'

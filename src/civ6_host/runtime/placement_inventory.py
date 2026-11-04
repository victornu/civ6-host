"""Native placements on currently visible plots belonging to own cities.

This is a read-only UI collector. It never consults host placement history,
production legality, a progress threshold, or an inferred placement date.
"""
from .configuration_profiles import XP1_CORE_SHA256
from .placement_inventory_profile import verify_source
from ..contracts.placement_inventory import SCHEMA, SCOPE, MAX_ROWS, validate
from ..contracts.production_queue import _uint, _type_name

_MAX_PLOTS=MAX_ROWS//2
_MAX_CITIES=4096


def _inputs(player_id,turn,observation):
    _uint(player_id,'inventory player',63);_uint(turn,'inventory turn',2147483647)
    if (type(observation) is not dict or type(observation.get('player_id')) is not int
            or observation['player_id']!=player_id or type(observation.get('turn')) is not int
            or observation['turn']!=turn):
        raise ValueError('Placement inventory observation belongs to another boundary')
    width,height=observation['width'],observation['height']
    _uint(width,'inventory map width',_MAX_PLOTS);_uint(height,'inventory map height',_MAX_PLOTS)
    if width==0 or height==0 or width*height>_MAX_PLOTS:
        raise ValueError('Placement inventory dimensions exceed the qualified map bound')
    plots,cities=observation['plots'],observation['cities']
    if type(plots) is not list or len(plots)>_MAX_PLOTS or type(cities) is not list or len(cities)>_MAX_CITIES:
        raise ValueError('Placement inventory input exceeds its explicit bound')
    seen=set();plot_rows=[]
    for row in plots:
        if type(row) is not dict or row.get('visible') is not True or row.get('revealed') is not True:
            raise ValueError('Placement inventory requires currently visible input plots')
        index,x,y=row['index'],row['x'],row['y']
        _uint(index,'visible plot',width*height-1);_uint(x,'visible x',width-1);_uint(y,'visible y',height-1)
        if (index!=y*width+x or index in seen or type(row['owner']) is not int
                or not -1<=row['owner']<=63):
            raise ValueError('Placement inventory visible plot identity is invalid')
        seen.add(index);plot_rows.append((index,x,y,row['owner']))
    city_ids=set()
    for row in cities:
        if type(row) is not dict or type(row.get('owner')) is not int or row['owner']!=player_id:
            raise ValueError('Placement inventory requires own observed cities')
        cid=_uint(row['id'],'inventory city')
        if cid in city_ids:raise ValueError('Duplicate own city in placement inventory input')
        city_ids.add(cid)
    return width,height,sorted(plot_rows),sorted(city_ids)


_OWN_CITY_LUA=r'''
local function uint(v,label,max)
 assert(type(v)=='number' and v%1==0 and v>=0 and v<=max,'invalid '..label)
 return v
end
local function nativeIndex(v,label)
 assert(type(v)=='number' and v%1==0 and v>=-1 and v<=2147483647,'invalid '..label)
 return v
end
local function bits(v)
 assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=2147483647,'invalid type Hash')
 return v<0 and v+4294967296 or v
end
local function flag(v,label)
 assert(v==nil or type(v)=='boolean','invalid '..label)
 return v==true
end
local function n(v) return string.format('%.0f',v) end
local function ready()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,'inventory perspective changed')
 assert(Game.GetCurrentGameTurn()==expectedTurn,'inventory turn changed')
 local w,h=Map.GetGridSize()
 assert(w==width and h==height and Map.GetPlotCount()==width*height,'inventory map changed')
end
ready()
local player=Players[pid]
assert(player,'inventory player unavailable')
local expectedCities,ownCities={},{}
for _,id in ipairs(cityIDs) do expectedCities[id]=true end
local function ownCityIdentity(city)
 assert(city and city:GetOwner()==pid,'inventory city belongs to another player')
 local id=uint(city:GetID(),'city ID',4294967295)
 assert(expectedCities[id],'inventory own city changed')
 return id
end
local cityCount=0
for _,city in player:GetCities():Members() do
 cityCount=cityCount+1;assert(cityCount<=4096,'inventory city bound exceeded')
 local id=ownCityIdentity(city)
 assert(not ownCities[id],'duplicate native inventory city');ownCities[id]=city
end
assert(cityCount==#cityIDs,'inventory native own city set changed')
'''


_LUA=_OWN_CITY_LUA+r'''
local visibility=PlayersVisibility[pid]
assert(visibility,'inventory visibility unavailable')
local function visible(input)
 assert(visibility:IsVisible(input[2],input[3])==true,'inventory plot became hidden')
 assert(visibility:IsRevealed(input[1])==true,'inventory plot became unrevealed')
end
local function metadata(category,index)
 local field=category=='district' and 'DistrictType' or 'BuildingType'
 local prefix=category=='district' and 'DISTRICT_' or 'BUILDING_'
 local entries=category=='district' and GameInfo.Districts or GameInfo.Buildings
 local row=entries[index]
 assert(row and uint(row.Index,'native type index',2147483647)==index,'inventory metadata index changed')
 local name=row[field]
 assert(type(name)=='string' and #name<=#prefix+100 and string.match(name,'^'..prefix..'[A-Z0-9_]+$'),
        'invalid inventory type name')
 return row,bits(row.Hash),name
end
local rows={}
local function add(cityID,category,index,hash,name,input,complete,districtID)
 assert(type(complete)=='boolean','invalid inventory native completion Boolean')
 assert(#rows<32768,'inventory row bound exceeded')
 rows[#rows+1]={cityID,category,index,hash,name,input[1],input[2],input[3],complete,districtID}
end
for _,input in ipairs(visiblePlots) do
 -- Visibility gates precede even the lookup of the live Plot userdata.
 visible(input)
 local plot=Map.GetPlotByIndex(input[1])
 assert(plot and plot:GetIndex()==input[1] and plot:GetX()==input[2] and plot:GetY()==input[3],
        'inventory plot identity changed')
 local owner=plot:GetOwner()
 assert(type(owner)=='number' and owner%1==0 and owner==input[4],'inventory plot owner changed')
 if owner==pid then
  local purchaseCity=Cities.GetPlotPurchaseCity(plot)
  -- An owned plot with no purchase city is outside the declared own-city scope.
  if purchaseCity~=nil then
   local cityID=ownCityIdentity(purchaseCity)
   local city=ownCities[cityID]
   assert(city and ownCityIdentity(city)==cityID,'inventory city disappeared')
   local districtType=nativeIndex(plot:GetDistrictType(),'district plot type')
   local wonderType=nativeIndex(plot:GetWonderType(),'building plot type')
   if districtType>=0 then
    local row,hash,name=metadata('district',districtType)
    local required=flag(row.RequiresPlacement,'district RequiresPlacement')
    local internal=flag(row.InternalOnly,'district InternalOnly')
    if required and not internal then
     local districtID=uint(plot:GetDistrictID(),'district ID',4294967295)
     local complete=city:GetDistricts():IsComplete(districtType,input[1])
     -- The native plot-specific completion query does not itself check type.
     assert(plot:GetDistrictType()==districtType and plot:GetDistrictID()==districtID,
            'inventory district identity changed during completion')
     add(cityID,'district',districtType,hash,name,input,complete,districtID)
    end
   end
   if wonderType>=0 then
    local row,hash,name=metadata('building',wonderType)
    local required=flag(row.RequiresPlacement,'building RequiresPlacement')
    local wonder=flag(row.IsWonder,'building IsWonder')
    if required or wonder then
     local complete=city:GetBuildings():HasBuilding(wonderType)
     assert(plot:GetWonderType()==wonderType,'inventory building identity changed during completion')
     add(cityID,'building',wonderType,hash,name,input,complete,nil)
    end
   end
   assert(plot:GetOwner()==pid,'inventory plot transferred during query')
   assert(ownCityIdentity(Cities.GetPlotPurchaseCity(plot))==cityID,
          'inventory purchase city changed during query')
   assert(ownCityIdentity(city)==cityID,'inventory city changed during query')
  end
 end
 visible(input)
end
ready()
table.sort(rows,function(a,b)
 if a[1]~=b[1] then return a[1]<b[1] end
 if a[2]~=b[2] then return a[2]<b[2] end
 return a[6]<b[6]
end)
local output={'placement-inventory-v1|'..n(pid)..'|'..n(expectedTurn)..'|'..n(#rows)}
for _,r in ipairs(rows) do
 output[#output+1]=table.concat({n(r[1]),r[2],n(r[3]),n(r[4]),r[5],n(r[6]),n(r[7]),n(r[8]),
                                 r[9] and '1' or '0',r[10] and n(r[10]) or '-'},'|')
end
return table.concat(output,'\n')
'''


def readback_source(player_id,turn,observation,*,core_sha256=XP1_CORE_SHA256):
    verify_source(core_sha256)
    width,height,plots,cities=_inputs(player_id,turn,observation)
    # Only checked numeric public identities enter the Lua source. No observed
    # strings, tracking dictionaries, candidate actions or hidden plots do.
    plot_literal=','.join('{'+','.join(map(str,row))+'}' for row in plots)
    city_literal=','.join(map(str,cities))
    header=(f'local pid,expectedTurn,width,height={player_id},{turn},{width},{height}\n'
            f'local visiblePlots={{{plot_literal}}}\nlocal cityIDs={{{city_literal}}}\n')
    return (header+_LUA).encode('ascii')


def _number(token,label,maximum=4294967295):
    if not token or not token.isascii() or not token.isdecimal() or (len(token)>1 and token[0]=='0'):
        raise ValueError('Invalid canonical inventory '+label)
    return _uint(int(token),label,maximum)


def parse_readback(payload,player_id,turn,observation):
    _,_,plots,_=_inputs(player_id,turn,observation)
    maximum=128+len(plots)*2*256
    if type(payload) is not bytes or len(payload)>maximum:
        raise ValueError('Placement inventory payload exceeds the input geometry bound')
    try:lines=payload.decode('ascii').split('\n')
    except UnicodeError as exc:raise ValueError('Non-ASCII placement inventory payload') from exc
    header=lines[0].split('|')
    if len(header)!=4 or header[:3]!=['placement-inventory-v1',str(player_id),str(turn)]:
        raise ValueError('Foreign placement inventory readback')
    count=_number(header[3],'row count',min(MAX_ROWS,2*len(plots)))
    if len(lines)!=count+1:raise ValueError('Truncated placement inventory readback')
    rows=[];previous=None;plot_inputs={p[0]:p for p in plots}
    for line in lines[1:]:
        fields=line.split('|')
        if len(fields)!=10 or fields[1] not in ('district','building') or fields[8] not in ('0','1'):
            raise ValueError('Invalid native placement inventory row')
        category=fields[1]
        row=dict(city_id=_number(fields[0],'city ID'),category=category,
          index=_number(fields[2],'type index',2147483647),hash=_number(fields[3],'type hash'),
          item_type=_type_name(category,fields[4]),plot_id=_number(fields[5],'plot',65535),
          x=_number(fields[6],'x',65535),y=_number(fields[7],'y',65535),complete=fields[8]=='1',
          district_id=None if fields[9]=='-' else _number(fields[9],'district ID'))
        key=(row['city_id'],category,row['plot_id'])
        if previous is not None and key<=previous:raise ValueError('Unsorted or duplicate placement inventory rows')
        previous=key
        expected=plot_inputs.get(row['plot_id'])
        if expected!=(row['plot_id'],row['x'],row['y'],player_id):
            raise ValueError('Placement inventory row differs from own visible plot input')
        rows.append(row)
    value=dict(schema=SCHEMA,scope=SCOPE,player_id=player_id,turn=turn,rows=rows)
    return validate(value,player_id,turn,observation=observation)


def read(prefix,player_id,turn,observation,*,core_sha256=XP1_CORE_SHA256):
    """Copy a fresh native inventory; caller binds its exact live source owner."""
    source=readback_source(player_id,turn,observation,core_sha256=core_sha256)
    capacity=max(4096,128+2*len(observation['plots'])*256)
    payload=prefix.runtime.evaluate_text(prefix.ui_child,source,b'@native_placement_inventory',capacity=capacity)
    return parse_readback(payload,player_id,turn,observation)

_BUILDING_PRESENCE_LUA=r'''
local building=GameInfo.Buildings[buildingType]
assert(building and building.BuildingType==buildingType,'building presence metadata changed')
local index=uint(building.Index,'building type index',2147483647)
local hash=bits(building.Hash)
local city=ownCities[cityID]
assert(city and ownCityIdentity(city)==cityID,'building presence city disappeared')
local present=city:GetBuildings():HasBuilding(index)
assert(type(present)=='boolean','invalid building presence Boolean')
assert(ownCityIdentity(city)==cityID,'building presence ownership changed')
ready()
return table.concat({'own-city-building-v1',n(pid),n(expectedTurn),n(cityID),
                     n(index),n(hash),present and '1' or '0'},'|')
'''


def read_building_presence(prefix, player_id, turn, observation, city_id, building_type, *, core_sha256):
    """Copy one own-city native HasBuilding result under the inventory owner binding."""
    from .configuration_profiles import XP2_CORE_SHA256
    if core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Own-city building presence requires the exact XP2 Core')
    verify_source(core_sha256)
    width,height,_,cities=_inputs(player_id,turn,observation)
    if _uint(city_id,'building presence city') not in cities:
        raise ValueError('Building presence requires an observed own city')
    name=_type_name('building',building_type)
    source=(f'local pid,expectedTurn,width,height={player_id},{turn},{width},{height}\n'
            f'local cityIDs={{{",".join(map(str,cities))}}}\n'
            f'local cityID,buildingType={city_id},"{name}"\n'
            +_OWN_CITY_LUA+_BUILDING_PRESENCE_LUA).encode('ascii')
    raw=prefix.runtime.evaluate_text(prefix.ui_child,source,b'@native_own_city_building',capacity=256)
    if type(raw) is not bytes or len(raw)>256:
        raise ValueError('Invalid native building presence payload')
    fields=raw.decode('ascii').split('|')
    if (len(fields)!=7 or fields[:4]!=['own-city-building-v1',str(player_id),str(turn),str(city_id)]
            or fields[6] not in ('0','1')):
        raise ValueError('Foreign native building presence payload')
    return dict(city_id=city_id,building_type=name,index=_number(fields[4],'building index',2147483647),
                hash=_number(fields[5],'building hash'),present=fields[6]=='1')

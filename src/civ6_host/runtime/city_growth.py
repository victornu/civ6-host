"""Use installed official UI functions; do not implement growth rules.

Only the public projection is returned to the session. Exact native food stock
and raw sentinel getters stay in a separate administrative trace event.
"""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from civ6_host.contracts.city_growth import SCHEMA, TEXT_FIELDS, validate

SOURCE=('work/host-simultaneous/city-management/growth-ui-lexical-source.json',
        '0dcb05574b0b1335486bcaa47d8d0754a128a94d1e3c10a265f7cb4b9de336a5')
CAPACITY=4*1024*1024


def source_files():
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    p=resolve_path(resource_root()/SOURCE[0]);raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE[1]:raise ValueError('Growth source proof changed')
    proof=json.loads(raw);pins={str(p):SOURCE[1]}
    if proof['schema']!='civ6-host.city-growth-source.v1':raise ValueError('Unknown growth source proof')
    for row in proof['sources']:
        path=resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Official city growth source changed')
        pins[str(path)]=row['sha256']
    return pins


@lru_cache(maxsize=1)
def display_source():
    files=source_files();texts={}
    for name in ('SupportFunctions.lua','Civ6Common.lua','CityPanelOverview.lua'):
        p=next(Path(p) for p in files if Path(p).name==name)
        texts[name]=p.read_text(encoding='utf-8-sig')
    chunks=[]
    for file,name in [('SupportFunctions.lua','Round'),('Civ6Common.lua','toPlusMinusString'),
                      ('CityPanelOverview.lua','UpdateCitizenGrowthStatusIcon'),('CityPanelOverview.lua','ViewPanelCitizensGrowth')]:
        text=texts[file];start=text.index('function '+name+'(');end=text.index('\nend',start)+4
        # Lexical bindings also work in the native restricted Lua context,
        # which does not support the fixture's loadstring/setfenv route.
        chunks.append('local '+text[start:end])
    text=texts['CityPanelOverview.lua']
    start=text.index('local UV_CITIZEN_STARVING_STATUS');end=text.index('\n\n',text.index('UV_CITIZEN_STARVING_STATUS[2]',start))
    chunks.insert(0,text[start:end])
    body=re.sub(r':\s*(?:number|boolean|table|string)\b','', '\n'.join(chunks))
    return body


def projection_source():
    """Local environment exposes only the presentation methods actually used."""
    names=','.join("'"+k+"'" for k in (*TEXT_FIELDS,'GrowthLongNum'))
    return ("\nlocal ui={math=math,Locale={Lookup=Locale.Lookup}}\n"
        "function ui.Locale.ToNumber(value,pattern)\n"
        " assert(type(value)=='number' and value==value and math.abs(value)<=1e12,'invalid display number')\n"
        " assert(pattern==nil or pattern=='#,###.#' or pattern=='+#,###.#;-#,###.#','unqualified display number pattern')\n"
        " return Locale.Lookup(pattern and ('{1: number '..pattern..'}') or '{1 : number}',value)\nend\n"
        "local rendered={}\nui.Controls={}\n"
        "local function text_control(name) local c={}\n"
        "function c:SetText(v) assert(type(v)=='string' or type(v)=='number','invalid growth display text');rendered[name]=v end\n"
        "function c:LocalizeAndSetText(key,...) self:SetText(Locale.Lookup(key,...)) end\nreturn c end\n"
        f"for _,key in ipairs({{{names}}}) do ui.Controls[key]=text_control(key) end\n"
        "ui.Controls.CitizensStarving={SetHide=function(self,v) assert(type(v)=='boolean');rendered.starving=not v end}\n"
        "for _,key in ipairs({'CitizenGrowthStatus2','CitizenGrowthStatusIcon2'}) do\n"
        "local name=key;ui.Controls[key]={SetColorByName=function(self,v) assert(type(v)=='string');rendered[name..'_color']=v end}\nend\n"
        "ui.Controls.CitizenGrowthStatus2.SetTextureOffsetVal=function(self,u,v) rendered.icon_u=u;rendered.icon_v=v end\n"
        "do\nlocal math,Locale,Controls=ui.math,ui.Locale,ui.Controls\n"+display_source()+
        "\nui.Round=Round;ui.ViewPanelCitizensGrowth=ViewPanelCitizensGrowth\nend\n").encode('utf-8')


def source(player_id,turn):
    if type(player_id) is not int or not 0<=player_id<64 or type(turn) is not int or not 0<=turn<2**31:
        raise ValueError('Invalid growth viewpoint')
    return f'local pid,turn={player_id},{turn}\n'.encode()+projection_source()+r'''
local function ready()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'growth perspective changed')
end
local function n(v)
 assert(type(v)=='number' and v==v and math.abs(v)<=1e12,'invalid growth amount')
 return string.format('%.17g',v)
end
local function whole(v) assert(type(v)=='number' and v%1==0,'invalid growth integer');return n(v) end
local function b(v) assert(type(v)=='boolean','invalid growth boolean');return v and '1' or '0' end
local function hex(v)
 assert(type(v)=='string' and #v<=4096 and not string.find(v,'\0',1,true),'invalid growth text')
 return (string.gsub(v,'.',function(c) return string.format('%02x',string.byte(c)) end))
end
ready();local player=assert(Players[pid]);local out={'city-growth-v1|'..whole(pid)..'|'..whole(turn)}
local cities={};local seen={}
for _,city in player:GetCities():Members() do
 local id=city:GetID();whole(id);assert(not seen[id] and city:GetOwner()==pid,'growth city ownership');seen[id]=true
 cities[#cities+1]=city;assert(#cities<=4096,'growth city bound')
end
table.sort(cities,function(a,b) return a:GetID()<b:GetID() end)
for _,city in ipairs(cities) do
 local id=whole(city:GetID());local growth=assert(city:GetGrowth())
 local food=growth:GetFood();local threshold=growth:GetGrowthThreshold();local surplus=growth:GetFoodSurplus()
 local growing=growth:GetTurnsUntilGrowth();local starving=growth:GetTurnsUntilStarvation()
 whole(growing);whole(starving);assert(growing>=-1 and starving>=-1,'unknown growth sentinel')
 local turns=0;if growing~=-1 then turns=growing elseif starving~=-1 then turns=-starving end
 local data={FoodPerTurn=math.floor(city:GetYield(YieldTypes.FOOD)*10)/10,
  FoodSurplus=ui.Round(surplus,1),GrowthThreshold=threshold-food,TurnsUntilGrowth=turns,
  Occupied=city:IsOccupied(),HappinessGrowthModifier=growth:GetHappinessGrowthModifier(),
  OtherGrowthModifiers=growth:GetOtherGrowthModifier(),HousingMultiplier=growth:GetHousingGrowthModifier(),
  OccupationMultiplier=growth:GetOccupationGrowthModifier()}
 rendered={};ui.ViewPanelCitizensGrowth(data)
 out[#out+1]=table.concat({'C',id,whole(city:GetPopulation()),b(data.Occupied),
  n(growth:GetHousing()),n(growth:GetAmenities()),n(growth:GetAmenitiesNeeded()),whole(growth:GetHappiness())},'|')
 for key,value in pairs(rendered) do
  local kind=type(value);local token
  if kind=='string' then token=hex(value) elseif kind=='boolean' then token=b(value) elseif kind=='number' then token=n(value)
  else error('unknown growth presentation value') end
  out[#out+1]=table.concat({'V',id,key,kind,token},'|')
 end
 -- Administrative readback; never put these fields in the returned public city row.
 out[#out+1]=table.concat({'R',id,n(food),n(threshold),n(surplus),whole(growing),whole(starving)},'|')
end
ready();return table.concat(out,'\n')
'''.encode()


def parse(raw,player_id,turn):
    if type(raw) is not bytes or len(raw)>CAPACITY:raise ValueError('Unbounded growth frame')
    lines=raw.decode('ascii').splitlines()
    if not lines or lines[0]!=f'city-growth-v1|{player_id}|{turn}':raise ValueError('Foreign growth frame')
    cities={};renders={};private={}
    def number(v):
        x=float(v)
        if not math.isfinite(x) or abs(x)>1e12:raise ValueError('Invalid growth amount')
        return x
    def integer(v):
        x=int(v)
        if str(x)!=v:raise ValueError('Invalid growth identity')
        return x
    def boolean(v):
        if v not in ('0','1'):raise ValueError('Invalid growth flag')
        return v=='1'
    for line in lines[1:]:
        cells=line.split('|');tag=cells[0]
        if len(cells)<2:raise ValueError('Malformed growth row')
        cid=integer(cells[1])
        if tag=='C' and len(cells)==8:
            if cid in cities or len(cities)>=4096:raise ValueError('Duplicate growth city')
            cities[cid]=dict(city_id=cid,population=integer(cells[2]),occupied=boolean(cells[3]),
                housing=number(cells[4]),amenities=number(cells[5]),amenities_needed=number(cells[6]),happiness=integer(cells[7]))
            renders[cid]={}
        elif tag=='V' and len(cells)==5 and cid in cities:
            key,kind,token=cells[2:]
            if key in renders[cid]:raise ValueError('Duplicate growth display value')
            if kind=='string':
                if len(token)>8192:raise ValueError('Unbounded growth text')
                data=bytes.fromhex(token)
                if data.hex()!=token:raise ValueError('Noncanonical growth text')
                value=data.decode('utf-8')
            elif kind=='boolean':value=boolean(token)
            elif kind=='number':
                value=number(token)
                if value.is_integer():value=int(value)
            else:raise ValueError('Unknown growth display type')
            renders[cid][key]=value
        elif tag=='R' and len(cells)==7 and cid in cities and cid not in private:
            private[cid]=dict(city_id=cid,food_stock=number(cells[2]),growth_threshold=number(cells[3]),
                food_surplus=number(cells[4]),turns_until_growth=integer(cells[5]),turns_until_starvation=integer(cells[6]))
        else:raise ValueError('Unknown growth row')
    if set(private)!=set(cities):raise ValueError('Missing private growth readback')
    rows=[]
    for cid,row in sorted(cities.items()):
        v=renders[cid]
        if set(v)!=set(TEXT_FIELDS)|{'GrowthLongNum','starving','CitizenGrowthStatus2_color','CitizenGrowthStatusIcon2_color','icon_u','icon_v'}:
            raise ValueError('Unexpected growth display output')
        if v['CitizenGrowthStatus2_color']!=v['CitizenGrowthStatusIcon2_color']:raise ValueError('Growth icon colors differ')
        row.update(display={k:v[k] for k in (*TEXT_FIELDS,'GrowthLongNum')},starving=v['starving'],
            growth_icon=dict(color=v['CitizenGrowthStatus2_color'],u=v['icon_u'],v=v['icon_v']))
        rows.append(row)
    result=validate(dict(schema=SCHEMA,player_id=player_id,turn=turn,cities=rows),player_id,turn)
    return result,[private[k] for k in sorted(private)]


def observe(owner,observation,sequence):
    pid,turn=observation['player_id'],observation['turn'];p=owner.prefix
    public,private=parse(p.runtime.evaluate_text(p.ui_child,source(pid,turn),
        b'@public_city_growth',capacity=CAPACITY+1),pid,turn)
    validate(public,pid,turn,observation=observation)
    from .native.native_episode_identity import require_episode
    identity=require_episode(p)
    owner.emit('native_city_growth_administrative_readback',episode_id=identity.episode_id,
        game_generation=identity.game_generation,player_id=pid,sequence=sequence,turn=turn,
        source_sha256=SOURCE[1],cities=private,actor_channel=False)
    return public

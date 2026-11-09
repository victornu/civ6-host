"""Official production-panel getters and separate administrative evidence."""
import copy
import hashlib
import json
from pathlib import Path
from civ6_host.contracts.production_inputs import CURRENT_SCHEMA,project_quotes,validate_current

SOURCE=('work/host-simultaneous/city-management/production-input-source.json','03a3220c61a12fb0e13773072f65b03b80a79a6befa897ac4d58ab36c16b4ec4')
CAPACITY=4*1024*1024
_XP2_CITY_SUPPORT_SHA256 = '6355e8ed18593225e9b05db74f2861b2f8382833e59569264267b96d3450e959'


def source_files(*, xp2=False, execution_image=None):
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    path=resolve_path(resource_root()/SOURCE[0]);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE[1]:raise ValueError('Production input source proof changed')
    proof=json.loads(raw);pins={str(path):SOURCE[1]}
    for row in proof['sources']:
        p=resolve_path(Path(row['path']))
        if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Official production input source changed')
        pins[str(p)]=row['sha256']
    if xp2:
        base_panel, = [Path(path) for path in pins if Path(path).name == 'CitySupport.lua']
        replacement = resolve_path(base_panel.parents[3] / 'DLC/Expansion2/UI/Replacements/CitySupport.lua')
        if hashlib.sha256(replacement.read_bytes()).hexdigest() != _XP2_CITY_SUPPORT_SHA256:
            raise ValueError('Gathering Storm CitySupport source changed')
        pins[str(replacement)] = _XP2_CITY_SUPPORT_SHA256
    elif execution_image is not None:
        raise ValueError('Execution image profile is only valid for XP2 production sources')
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(pins, execution_image=execution_image)


def source(pid,turn,*,xp2=False):
    if type(pid) is not int or not 0<=pid<64 or type(turn) is not int or not 0<=turn<2**31:raise ValueError('Invalid production viewpoint')
    if type(xp2) is not bool:raise ValueError('Invalid production display profile')
    return f'local pid,turn={pid},{turn}\nlocal xp2={str(xp2).lower()}\n'.encode()+rb'''
local function ready()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'production viewpoint changed')
end
local function i(v) assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=4294967295,'invalid production number');return string.format('%.0f',v) end
local function bits(v) i(v);return v<0 and v+4294967296 or v end
local function hex(v) assert(type(v)=='string' and #v<=4096,'invalid production name');return (string.gsub(v,'.',function(c) return string.format('%02x',string.byte(c)) end)) end
ready();local player=assert(Players[pid]);local cities={};local seen={}
for _,city in player:GetCities():Members() do
 local id=city:GetID();i(id);assert(city:GetOwner()==pid and not seen[id],'foreign or duplicate production city')
 seen[id]=true;cities[#cities+1]=city;assert(#cities<=4096,'production city bound')
end
table.sort(cities,function(a,b)return a:GetID()<b:GetID() end)
local out={'production-display-v1|'..i(pid)..'|'..i(turn)}
for _,city in ipairs(cities) do
 local q=assert(city:GetBuildQueue());local current=q:GetCurrentProductionTypeHash();local previous=q:GetPreviousProductionTypeHash()
 i(current);i(previous)
 if current==0 and previous==0 then out[#out+1]='E|'..i(city:GetID())
 else
  -- The shipped ProductionHelper displays the previous item when the queue is empty.
  local hash=current~=0 and current or previous;local matches={}
  for _,spec in ipairs({{'building',GameInfo.Buildings,'Building'},{'district',GameInfo.Districts,'District'},
                       {'unit',GameInfo.Units,'Unit'},{'project',GameInfo.Projects,'Project'}}) do
   local row=spec[2][hash]
   if row then assert(bits(row.Hash)==bits(hash),'production hash lookup differs');matches[#matches+1]={spec=spec,row=row} end
  end
  assert(#matches==1,'unknown or ambiguous displayed production')
  local match=matches[1];local row=match.row;local spec=match.spec;local category=spec[1];local prefix=spec[3]
  local itemType=row[prefix..'Type'];assert(type(itemType)=='string' and string.match(itemType,'^[A-Z0-9_]+$'),'invalid production type')
  local progress=q['Get'..prefix..'Progress'](q,row.Index)
  local cost;local modifier;local formation='-';local name=Locale.Lookup(row.Name)
  if category=='unit' then
   -- CitySupport uses the CURRENT modifier even when rendering the previous item.
   local value=q:GetCurrentProductionTypeModifier();local f=assert(MilitaryFormationTypes)
   modifier=value
   if value==f.STANDARD_FORMATION then cost=q:GetUnitCost(row.Index);formation='single'
   elseif value==f.CORPS_FORMATION then
    cost=q:GetUnitCorpsCost(row.Index);formation='corps'
    name=name..' '..Locale.Lookup(row.Domain=='DOMAIN_SEA' and 'LOC_UNITFLAG_FLEET_SUFFIX' or 'LOC_UNITFLAG_CORPS_SUFFIX')
   elseif value==f.ARMY_FORMATION then
    cost=q:GetUnitArmyCost(row.Index);formation='army'
    name=name..' '..Locale.Lookup(row.Domain=='DOMAIN_SEA' and 'LOC_UNITFLAG_ARMADA_SUFFIX' or 'LOC_UNITFLAG_ARMY_SUFFIX')
   else
    -- CitySupport initializes cost to zero and leaves the name unsuffixed
    -- when none of its three formation branches matches (including previous items).
    i(value);cost=0;formation='unsuffixed'
   end
  else cost=q['Get'..prefix..'Cost'](q,row.Index) end
  -- The Gathering Storm CitySupport replacement supplies the unit formation.
  local turns
  if xp2 and category=='unit' then turns=q:GetTurnsLeft(itemType,modifier)
  else turns=q:GetTurnsLeft(itemType) end
  out[#out+1]=table.concat({'C',i(city:GetID()),current~=0 and 'current' or 'completed',category,i(row.Index),i(bits(hash)),itemType,formation,i(progress),i(cost),i(turns),hex(name)},'|')
 end
 assert(city:GetOwner()==pid and q:GetCurrentProductionTypeHash()==current and q:GetPreviousProductionTypeHash()==previous,'production changed while reading')
end
ready();return table.concat(out,'\n')
'''


def parse(raw,pid,turn):
    if type(raw) is not bytes or len(raw)>CAPACITY:raise ValueError('Unbounded production display')
    lines=raw.decode('ascii').splitlines()
    if not lines or lines[0]!=f'production-display-v1|{pid}|{turn}':raise ValueError('Foreign production display')
    cities=[]
    def integer(v):
        n=int(v)
        if str(n)!=v:raise ValueError('Noncanonical production integer')
        return n
    for line in lines[1:]:
        c=line.split('|')
        if c[0]=='E' and len(c)==2:row=dict(city_id=integer(c[1]),state='empty',item=None)
        elif c[0]=='C' and len(c)==12:
            data=bytes.fromhex(c[11])
            if data.hex()!=c[11]:raise ValueError('Noncanonical production name')
            turns=integer(c[10])
            row=dict(city_id=integer(c[1]),state=c[2],item=dict(category=c[3],index=integer(c[4]),hash=integer(c[5]),
                item_type=c[6],formation=None if c[7]=='-' else c[7],progress=integer(c[8]),cost=integer(c[9]),
                turns_left=None if turns==-1 else turns,never_completes=turns==-1,name=data.decode('utf-8')))
        else:raise ValueError('Unknown production display row')
        cities.append(row)
    return validate_current(dict(schema=CURRENT_SCHEMA,player_id=pid,turn=turn,cities=cities),pid,turn)


def read_current(prefix, observation, queues, *, xp2=False):
    from .locale_text import attach as attach_length_locale
    attach_length_locale(prefix)
    pid, turn = observation['player_id'], observation['turn']
    current = parse(prefix.runtime.evaluate_text(prefix.ui_child, source(pid,turn,xp2=xp2),
        b'@public_production_inputs', capacity=CAPACITY+1), pid, turn)
    return validate_current(current,pid,turn,observation=observation,queues=queues)


def attach(owner,observation,decisions,sequence):
    """Keep native evidence internally; send only display values over the wire."""
    p=owner.prefix;pid,turn=observation['player_id'],observation['turn']
    current=read_current(p,observation,decisions['production_queues'])
    # read_decisions already validates its native quotes against the production
    # candidates. Closed frames retain quotes but have no selectable actions.
    quotes=project_quotes(decisions['production_info'],pid,turn,observation=observation)
    from .native.native_episode_identity import require_episode
    identity=require_episode(p)
    admin=dict(episode_id=identity.episode_id,game_generation=identity.game_generation,player_id=pid,
        sequence=sequence,turn=turn,source_sha256=SOURCE[1],actor_channel=False,
        production=copy.deepcopy(decisions['production']),production_info=copy.deepcopy(decisions['production_info']),
        public_production=copy.deepcopy(current))
    if not hasattr(owner,'production_administrative_by_player'):owner.production_administrative_by_player={}
    owner.production_administrative_by_player[pid]=admin
    owner.emit('native_production_administrative_readback',**admin)
    decisions['production']=current;decisions['production_info']=quotes

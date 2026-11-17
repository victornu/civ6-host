"""Exact stock Rise and Fall projection of the own-city building panel."""

from hashlib import sha256
from pathlib import Path

from civ6_host.contracts import city_buildings
from . import xp2_great_works_inventory as works
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .paths import resource_root
from .placement_inventory import _OWN_CITY_LUA, _inputs
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1city/xp1-installed-stock-city-building-inventory-source.json',
          '066cba5010a7dd1fb6d3530b20e57f8fb059f924b02a4562b955ac3ead808b2f')
_CALLBACKS = {
    'City.GetBuildings': 0x5a62a0, 'CityBuildings.GetBuildingsAtLocation': 0x5a8f50,
    'CityBuildings.HasBuilding': 0x5a9400, 'CityBuildings.IsPillaged': 0x5a94c0,
    'CityPlots.GetPurchasedPlots': 0x5bef60, 'Map.GetCityPlots': 0x5bd690,
}
_MAX_BYTES = 2 * 1024**2


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def verify_source():
    proof = _source(SOURCE)
    capture = proof['capture']
    if (proof['schema'] != 'civ6-host.xp1-installed-stock-city-building-inventory.static.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or (capture['path'],capture['sha256']) != REFERENCE
            or {name:row['callback']['rva'] for name,row in proof['bindings'].items()} != _CALLBACKS
            or proof['data_semantics']['identity'] != ('city_id','plot_id','building_index')):
        raise ValueError('Rise and Fall building panel source differs')
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('City building sources require the installed Rise and Fall image')
    proof = verify_source()
    steam_root = Path(image.path).parents[4]
    rows = [(resource_root()/SOURCE[0], SOURCE[1]), (Path(image.path), image.image_sha256)]
    rows.extend((steam_root/row['path'],row['sha256']) for row in proof['ui_files'].values())
    rows.extend((resource_root()/row['path'],row['sha256'])
                for row in (proof['capture'],*proof['capture_selections']))
    overview = _source(works.XP1_OVERVIEW_SOURCE)
    capture, building_reader = overview['capture'], overview['building_reader_source']
    if (capture['path'], capture['sha256']) != REFERENCE or (
            building_reader['path'], building_reader['sha256']) != SOURCE:
        raise ValueError('Rise and Fall Great Work overview belongs to another profile')
    works.theming_spans(image)
    rows.append((resource_root()/works.XP1_OVERVIEW_SOURCE[0], works.XP1_OVERVIEW_SOURCE[1]))
    rows.extend((Path(path), digest) for path,digest in works.dependencies(image).items())
    shared_source = Path(works.__file__)
    rows.append((shared_source, sha256(shared_source.read_bytes()).hexdigest()))
    pins = {str(resolve_path(path).resolve()):digest for path,digest in rows}
    verify_pinned_files(pins)
    return pins


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    if (getattr(saved,'xp1_city_buildings',False) is not True
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(backend.captured_bundle.reference,getattr(core,'_civ6_host_execution_image',None))):
        raise ValueError('Building inventory requires the exact Rise and Fall saved owner')
    lifetime = (core,prefix)
    if getattr(saved,'_xp1_city_building_lifetime',None) == lifetime:
        return
    proof = verify_source()
    spans = list(proof['native_bodies'].values())
    spans.extend(row[key] for row in proof['bindings'].values() for key in ('callback','registration'))
    for span in spans:
        raw = backend.runtime.read(core._handle+span['rva'],span['bytes'])
        if type(raw) is not bytes or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Rise and Fall city building binding differs')
    works.verify_theming_bindings(_XP1_PROFILE, core._handle, backend.runtime.read)
    saved._xp1_great_work_rules = works.rules(_XP1_PROFILE)
    saved._xp1_city_building_lifetime = lifetime


_BUILDINGS_LUA = r'''
local function boolean(value,label)
 assert(type(value)=='boolean','invalid building '..label)
 return value and '1' or '0'
end
local cityPlots=Map.GetCityPlots()
assert(cityPlots,'city plots unavailable')
local output={'city-buildings-v1|'..n(pid)..'|'..n(expectedTurn)}
local seen={}
for _,cityID in ipairs(cityIDs) do
 local city=ownCities[cityID]
 local buildings=city:GetBuildings()
 local plots=cityPlots:GetPurchasedPlots(city)
 assert(buildings and (plots==nil or type(plots)=='table'),'native building plot list unavailable')
 local visited={}
 for _,plot in pairs(plots or {}) do
  uint(plot,'purchased plot',width*height-1)
  assert(not visited[plot],'duplicate purchased plot');visited[plot]=true
  if ownVisible[plot] then
   local indices=buildings:GetBuildingsAtLocation(plot)
   assert(type(indices)=='table','native building rows unavailable')
   for _,index in ipairs(indices) do
    uint(index,'building index',2147483647)
    local definition=GameInfo.Buildings[index]
    assert(definition and definition.Index==index and type(definition.BuildingType)=='string'
           and #definition.BuildingType<=109 and definition.BuildingType:match('^BUILDING_[A-Z0-9_]+$'),
           'native building identity differs')
    local key=n(cityID)..'|'..n(plot)..'|'..n(index)
    assert(not seen[key] and #output<=maxRows,'duplicate or unbounded building rows')
    seen[key]=true
    output[#output+1]=table.concat({key,n(bits(definition.Hash)),definition.BuildingType,
         boolean(buildings:HasBuilding(index),'completion'),
         boolean(buildings:IsPillaged(index),'pillage')},'|')
   end
  end
 end
 assert(ownCityIdentity(city)==cityID,'building inventory city changed')
end
ready()
return table.concat(output,'\n')
'''


def readback_source(player_id, turn, observation):
    width,height,plots,cities = _inputs(player_id,turn,observation)
    city_ids = ','.join(map(str,cities))
    own_plots = ','.join(f'[{index}]=true' for index,_,_,owner in plots if owner==player_id)
    return (f'local pid,expectedTurn,width,height={player_id},{turn},{width},{height}\n'
            f'local cityIDs={{{city_ids}}}\nlocal ownVisible={{{own_plots}}}\n'
            f'local maxRows={city_buildings.MAX_ROWS}\n'
            +_OWN_CITY_LUA+_BUILDINGS_LUA).encode('ascii')


def parse_readback(payload, player_id, turn, observation):
    if type(payload) is not bytes or len(payload)>_MAX_BYTES:
        raise ValueError('Unbounded city building readback')
    head,*lines = payload.decode('ascii').split('\n')
    if head != f'city-buildings-v1|{player_id}|{turn}' or len(lines)>city_buildings.MAX_ROWS:
        raise ValueError('Foreign city building readback')
    rows = []
    for line in lines:
        city,plot,index,bits,name,complete,pillaged = line.split('|')
        if (any(not s.isascii() or not s.isdigit() or len(s)>10 for s in (city,plot,index,bits))
                or complete not in ('0','1') or pillaged not in ('0','1')):
            raise ValueError('Malformed city building readback')
        rows.append(dict(city_id=int(city),plot_id=int(plot),index=int(index),hash=int(bits),
                         item_type=name,complete=complete=='1',pillaged=pillaged=='1'))
    rows.sort(key=lambda row:(row['city_id'],row['plot_id'],row['index']))
    return city_buildings.validate(dict(schema=city_buildings.SCHEMA, player_id=player_id, turn=turn,
                                        rows=rows),player_id,turn,observation=observation)


def read(saved, observation, *, active=False):
    _bind(saved, active=active)
    inventory = read_inventory(saved.prefix, observation, b'@xp1_city_building_inventory')
    return works.read(saved.prefix, observation, inventory, saved._xp1_great_work_rules)


def read_inventory(prefix, observation, source_label):
    pid,turn = observation['player_id'],observation['turn']
    raw = prefix.runtime.evaluate_text(prefix.ui_child,readback_source(pid,turn,observation),
                                       source_label,capacity=_MAX_BYTES+1)
    return parse_readback(raw,pid,turn,observation)

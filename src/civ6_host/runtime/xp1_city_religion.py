"""Read-only city religion on the exact installed saved owner.

The Rise and Fall majority reader retains its original contract. The details
reader also returns follower counts and pressure as displayed by the selected
Rise and Fall or Gathering Storm religion lens.
"""
from hashlib import sha256
from pathlib import Path

from civ6_host.contracts import city_religion, network_turn
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _PROFILE, _XP1_PROFILE
from .paths import resource_root
from .placement_inventory import _OWN_CITY_LUA, _inputs
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('evidence/host-xp1-installed-stock-trade-religion-source.json',
          'eb91ba5b27052aa5af138cfb0f46bfb9213a235320729432867bf7a75622044f')
TRADE_SOURCE = ('work/trade-common-client/xp1-installed-stock-trade-operations.json',
                '4bda7665a7a6925fb19b21e9e28696caa806f4dae94603a229e1b34eb5641a27')
CITY_UI = ('Base/Assets/UI/CitySupport.lua',
           '49ebe90ccff94545c86758ae1d50c24fa61914b28be1e3a35729286ca22475f1')
# Complete four-byte accessor identified by the existing callback receipt.
CORE_BODY = {'rva':0x7a14a0, 'bytes':4,
             'sha256':'916ae10aa3fd76a4d5b25b2fb66e9df0fd04957c7ab10930268d1ed7808be689'}
_METHODS = {'City.GetReligion':0x5a6990, 'CityReligion.GetMajorityReligion':0x5adb80}
_MAX_BYTES = 128 * 1024

DETAILS_SOURCE = (
    'work/x1trade/city-religion-details-runtime-stage/9072615eb6e2e20cd727e705ed3fb7b8a7b6ce093b205e32cbd2336124fb0fae.json',
    '9072615eb6e2e20cd727e705ed3fb7b8a7b6ce093b205e32cbd2336124fb0fae',
)
_DETAILS_METHODS = {'GetReligionsInCity':'0x5adc90','GetTotalPressureOnCity':'0x5ae3c0'}
_MAX_DETAILS_BYTES = 2 * 1024 * 1024
_PRESSURE_LIMIT = 1 << 23


def verify_source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-stock-trade-religion-source.static.v1'
            or proof['image_sha256'] != _XP1_PROFILE.image_sha256
            or (proof['trade_source']['path'],proof['trade_source']['sha256']) != TRADE_SOURCE):
        raise ValueError('Rise and Fall city religion source differs')
    rows = [row for row in proof['rows'] if row['method'] in _METHODS]
    if {row['method']:int(row['callback']['rva'],16) for row in rows} != _METHODS or len(rows) != 2:
        raise ValueError('Rise and Fall city religion bindings differ')
    return rows



def verify_details_source():
    proof = _source(DETAILS_SOURCE)
    methods = {row['name']:row['callback_rva'] for row in proof['registrations']
               if row['namespace']=='CityReligion'}
    if (proof['schema'] != 'civ6-host.xp1-city-religion-details-source.static.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or proof['majority_source']['sha256'] != SOURCE[1]
            or methods != _DETAILS_METHODS or len(proof['registrations']) != len(methods)
            or proof['contract']['displayed_round'] != 'math.floor(value + 0.5)'
            or proof['contract']['encoded_pressure_bounds'] != (-_PRESSURE_LIMIT,_PRESSURE_LIMIT)
            or proof['native_execution'] is not False):
        raise ValueError('Rise and Fall city religion detail source differs')
    return proof


def supports(reference,image):
    from .xp2_city_religion_source import supports as supports_xp2
    return (image is _XP1_PROFILE and type(reference) is tuple and reference == REFERENCE
            or supports_xp2(reference,image))


def source_for(image):
    if image is _XP1_PROFILE:
        return DETAILS_SOURCE
    if image is _PROFILE:
        from .xp2_city_religion_source import SOURCE as xp2_source
        return xp2_source
    raise ValueError('City religion details require an exact installed execution image')


def source_dependencies(image, *, include_details=False, reference=None):
    if type(include_details) is not bool:
        raise ValueError('City religion detail dependencies require a Boolean')
    if image is _PROFILE:
        if not include_details:
            raise ValueError('Gathering Storm city religion requires explicit detail mode')
        from .xp2_city_religion_source import source_dependencies as xp2_dependencies
        return xp2_dependencies(image,reference=reference)
    if image is not _XP1_PROFILE or reference is not None and not supports(reference,image):
        raise ValueError('City religion sources require the exact installed Rise and Fall capture')
    verify_source()
    steam_root = Path(image.path).parents[4]
    rows = [(resource_root()/p,digest) for p,digest in (SOURCE,TRADE_SOURCE,REFERENCE)]
    rows.extend(((Path(image.path),image.image_sha256),(steam_root/CITY_UI[0],CITY_UI[1])))
    if include_details:
        proof = verify_details_source()
        rows.append((resource_root()/DETAILS_SOURCE[0],DETAILS_SOURCE[1]))
        rows.extend((steam_root/row['path'],row['sha256']) for row in proof['ui'])
    pins = {str(resolve_path(Path(path)).resolve()):digest for path,digest in rows}
    verify_pinned_files(pins)
    return pins


def _bind(saved):
    saved._check_query()
    backend,prefix = saved.backend,saved.prefix
    core = backend.core
    if (backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or backend.captured_bundle.reference != REFERENCE
            or getattr(core,'_civ6_host_execution_image',None) is not _XP1_PROFILE):
        raise ValueError('City religion requires the exact installed Rise and Fall saved owner')
    lifetime = (core,prefix)
    if getattr(saved,'_xp1_city_religion_lifetime',None) == lifetime:
        return
    spans = [CORE_BODY]
    spans.extend(row[key] for row in verify_source() for key in ('callback','registration'))
    for span in spans:
        rva = int(span['rva'],16) if type(span['rva']) is str else span['rva']
        raw = backend.runtime.read(core._handle+rva,span['bytes'])
        if type(raw) is not bytes or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Rise and Fall city religion binding differs')
    saved._xp1_city_religion_lifetime = lifetime



def _bind_details(saved):
    _bind(saved)
    backend,prefix = saved.backend,saved.prefix
    lifetime = (backend.core,prefix)
    if getattr(saved,'_xp1_city_religion_details_lifetime',None) == lifetime:
        return
    proof = verify_details_source()
    spans = [span for function in proof['functions'].values() for span in function['fragments']]
    spans.extend(row[key] for row in proof['registrations'] for key in ('registration','literal'))
    spans.extend(proof['field_literals'])
    spans.extend(proof['pressure_constants'])
    for span in spans:
        raw = backend.runtime.read(backend.core._handle+int(span['rva'],16),span['bytes'])
        if type(raw) is not bytes or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Rise and Fall city religion detail binding differs at '+span['rva'])
    saved._xp1_city_religion_details_lifetime = lifetime


_RELIGION_LUA = r'''
local output={'city-religion-v1|'..n(pid)..'|'..n(expectedTurn)}
for _,cityID in ipairs(cityIDs) do
 local city=ownCities[cityID]
 assert(ownCityIdentity(city)==cityID,'religion city changed')
 local religion=city:GetReligion()
 assert(religion,'city religion unavailable')
 local majority=religion:GetMajorityReligion()
 assert(type(majority)=='number' and majority%1==0 and majority>=-2147483648
        and majority<=2147483647,'invalid majority religion index')
 assert(ownCityIdentity(city)==cityID,'religion city changed')
 output[#output+1]=n(cityID)..'|'..n(majority)
end
ready()
return table.concat(output,'\n')
'''



_DETAILS_LUA = r'''
local function signedIndex(value, label)
 assert(type(value)=='number' and value%1==0 and value>=-2147483648
        and value<=2147483647,'invalid city religion '..label)
 return value
end
local function displayPressure(value)
 assert(type(value)=='number' and value>=-8388608 and value<=8388608,
        'invalid city religion pressure')
 -- Same zero-decimal result as the selected SupportFunctions.Round.
 return math.floor(value+0.5)
end
local output={'city-religion-v2|'..n(pid)..'|'..n(expectedTurn)}
for _,cityID in ipairs(cityIDs) do
 local city=ownCities[cityID]
 assert(ownCityIdentity(city)==cityID,'religion city changed')
 local religion=city:GetReligion()
 assert(religion,'city religion unavailable')
 local majority=signedIndex(religion:GetMajorityReligion(),'majority')
 local entries=religion:GetReligionsInCity()
 assert(type(entries)=='table','city religion rows unavailable')
 local count,maxIndex=0,0
 for k in pairs(entries) do
  uint(k,'city religion row index',4096)
  assert(k>0,'invalid city religion array key')
  count=count+1
  if k>maxIndex then maxIndex=k end
 end
 assert(count==maxIndex,'sparse city religion rows')
 local rows,seen={},{}
 for _,entry in ipairs(entries) do
  assert(type(entry)=='table','invalid city religion row')
  local index=signedIndex(entry.Religion,'index')
  if index>=0 then
   assert(not seen[index],'duplicate visible city religion')
   seen[index]=true
   local followers=signedIndex(entry.Followers,'followers')
   local incoming=displayPressure(religion:GetTotalPressureOnCity(index))
   local lifetime=displayPressure(entry.Pressure)
   rows[#rows+1]={index=index,line=table.concat({n(index),n(followers),n(incoming),n(lifetime)},'|')}
  end
 end
 table.sort(rows,function(a,b) return a.index<b.index end)
 assert(ownCityIdentity(city)==cityID,'religion city changed')
 output[#output+1]=n(cityID)..'|'..n(majority)..'|'..n(#rows)
 for _,row in ipairs(rows) do output[#output+1]=row.line end
end
ready()
return table.concat(output,'\n')
'''


def readback_source(player_id, turn, observation, *, include_details=False):
    if type(include_details) is not bool:
        raise ValueError('City religion detail mode requires a Boolean')
    width,height,_,cities = _inputs(player_id,turn,observation)
    ids = ','.join(map(str,cities))
    body = _DETAILS_LUA if include_details else _RELIGION_LUA
    return (f'local pid,expectedTurn,width,height={player_id},{turn},{width},{height}\n'
            f'local cityIDs={{{ids}}}\n'+_OWN_CITY_LUA+body).encode('ascii')


def parse_readback(payload, player_id, turn, observation):
    if type(payload) is not bytes or len(payload)>_MAX_BYTES:
        raise ValueError('Unbounded city religion readback')
    head,*lines = payload.decode('ascii').split('\n')
    if head != f'city-religion-v1|{player_id}|{turn}' or len(lines)>city_religion.MAX_CITIES:
        raise ValueError('Foreign city religion readback')
    rows = []
    for line in lines:
        city,religion = line.split('|')
        digits = religion[1:] if religion.startswith('-') else religion
        if (not city.isascii() or not city.isdigit() or len(city)>10
                or not digits.isascii() or not digits.isdigit() or len(digits)>10):
            raise ValueError('Malformed city religion readback')
        rows.append(dict(city_id=int(city),majority_religion=int(religion)))
    return city_religion.validate(dict(schema=city_religion.SCHEMA,player_id=player_id,turn=turn,
                                      cities=rows),player_id,turn,observation=observation)


def read(saved, observation):
    _bind(saved)
    pid,turn = observation['player_id'],observation['turn']
    raw = saved.prefix.runtime.evaluate_text(saved.prefix.ui_child,readback_source(pid,turn,observation),
        b'@xp1_own_city_religion',capacity=_MAX_BYTES+1)
    return parse_readback(raw,pid,turn,observation)



def _number(cell, low, high):
    if type(cell) is not bytes or not 0<len(cell)<=11:
        raise ValueError('Invalid city religion detail integer')
    value = int(cell)
    if str(value).encode('ascii') != cell or not low<=value<=high:
        raise ValueError('Invalid city religion detail integer')
    return value


def parse_details(payload, player_id, turn, observation):
    if type(payload) is not bytes or not 0<len(payload)<=_MAX_DETAILS_BYTES:
        raise ValueError('Unbounded city religion details readback')
    head,*wire = payload.split(b'\n')
    if head != f'city-religion-v2|{player_id}|{turn}'.encode('ascii'):
        raise ValueError('Foreign city religion details readback')
    rows,offset = [],0
    while offset<len(wire):
        if len(rows)>=city_religion.MAX_CITIES:
            raise ValueError('Unbounded own city religion roster')
        city,majority,total = wire[offset].split(b'|')
        count = _number(total,0,city_religion.MAX_RELIGIONS)
        offset += 1
        if offset+count>len(wire):
            raise ValueError('Truncated city religion row list')
        religions = []
        for line in wire[offset:offset+count]:
            index,followers,incoming,lifetime = line.split(b'|')
            religions.append(dict(religion_index=_number(index,0,0x7fffffff),
                followers=_number(followers,-2**31,2**31-1),
                pressure_per_turn=_number(incoming,-_PRESSURE_LIMIT,_PRESSURE_LIMIT),
                lifetime_pressure=_number(lifetime,-_PRESSURE_LIMIT,_PRESSURE_LIMIT)))
        rows.append(dict(city_id=_number(city,0,0xffffffff),
            majority_religion=_number(majority,-2**31,2**31-1),religions=religions))
        offset += count
    return city_religion.validate_details(dict(schema=city_religion.DETAILS_SCHEMA,player_id=player_id,
        turn=turn,cities=rows),player_id,turn,observation=observation)


def read_details(saved, observation, *, expected_majority=None, borrowed=False):
    backend = getattr(saved,'backend',None)
    image = getattr(getattr(backend,'core',None),'_civ6_host_execution_image',None)
    if borrowed and image is not _PROFILE:
        raise ValueError('Borrowed city religion requires the current Gathering Storm image')
    if image is _PROFILE:
        from .xp2_city_religion_source import bind_prefix
        if borrowed:
            from .xp1_session_view import _borrowed_xp2_reference
            _borrowed_xp2_reference(saved, observation['player_id'])
        else:
            saved._check_query()
        bind_prefix(saved.prefix)
        chunk_name = b'@xp2_own_city_religion_details'
    else:
        _bind_details(saved)
        chunk_name = b'@xp1_own_city_religion_details'
    pid,turn = observation['player_id'],observation['turn']
    raw = saved.prefix.runtime.evaluate_text(saved.prefix.ui_child,
        readback_source(pid,turn,observation,include_details=True),chunk_name,
        capacity=_MAX_DETAILS_BYTES+1)
    details = parse_details(raw,pid,turn,observation)
    if (expected_majority is not None and
            city_religion.project_majority(details,pid,turn,observation=observation) != expected_majority):
        raise ValueError('City religion details changed the current own majorities')
    return details


def attach(saved, observation, decisions):
    schema = network_turn.XP1_CITY_RELIGION_SCHEMA_BY_BASE.get(decisions.get('schema'))
    if (schema is None or type(decisions.get('player_id')) is not int
            or type(decisions.get('turn')) is not int
            or (decisions['player_id'],decisions['turn']) != (observation['player_id'],observation['turn'])):
        raise ValueError('City religion requires its explicit actor catalogue revision')
    state = read(saved,observation)
    decisions['schema'] = schema
    decisions['city_religion'] = state

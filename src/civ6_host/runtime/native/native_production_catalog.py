"""Production choices passing native CanProduce and operation legality checks.

Supports standard units, ordinary buildings, projects and districts without placement.
District placement, wonders, corps/armies and purchases remain explicitly outside this
adapter. Submission is not application: the caller must deliver the native
archive and verify queue size/current production using native readback.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PRODUCTION_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import re
from civ6_host.runtime.native.native_city_actions import verify_source as verify_city_route
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'b7ca555634b687e758d8009cd70ad42ad7b95c8eedf1cc504e053836c49e4d26'
CAN_PRODUCE_PROOF_SHA256 = '961e847b2e3ca0aa0ae1dad079f62d4cddf03951f554834b3f83279dbf2a30d4'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_production_catalog.py')))).resolve().parents[1]
REPLACEMENT_PROOF = _ROOT / 'work/production-replace961/source.json'
REPLACEMENT_SHA = '74c1cd44764c48df69d248d7bf766eb3cfdf0dc617d46564a49af0fc08c0b5df'
MAX_DEFINITIONS = 4096
MAX_CANDIDATES = 256
MAX_RESPONSE_BYTES = 65536
KINDS = ('unit', 'building', 'project', 'district')
TABLES = {'unit': 'Units', 'building': 'Buildings', 'project': 'Projects', 'district': 'Districts'}
TYPE_FIELDS = {'unit': 'UnitType', 'building': 'BuildingType', 'project': 'ProjectType', 'district': 'DistrictType'}
NOT_WIRED = ('district_placement', 'district_repairs_or_plot_list_alternatives', 'wonder_placement_and_wonder_production', 'other_buildings_requiring_placement', 'unit_corps_and_armies', 'purchases')

def verify_source(*, core_sha256=_PRODUCTION_BASE_CORE_SHA256):
    if core_sha256 != _PRODUCTION_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_profile import verify_source as selected_source
        return selected_source(core_sha256)
    verify_city_route()
    proof = load_pinned_json(_ROOT / 'evidence/native-production-catalog-route' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_production_catalog_route.static.v1' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        raise RuntimeError('Production catalog source identity changed')
    can_produce = load_pinned_json(_ROOT / 'evidence/native-production-can-produce' / (CAN_PRODUCE_PROOF_SHA256 + '.json'), CAN_PRODUCE_PROOF_SHA256)
    if can_produce.get('schema') != 'civ6rl.native_production_can_produce.static.v1' or can_produce['images']['core_sha256'] != proof['images']['core_sha256'] or can_produce['registration']['binder_va'] != '0x180512820' or (can_produce['registration']['public_closure']['callback_va'] != 6447770896) or (can_produce['input_proofs']['production_catalog_route']['sha256'] != PROOF_SHA256):
        raise RuntimeError('Native CanProduce binding source identity changed')
    return proof

def _uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid ' + label)
    return value

def verify_replacement_source(*, core_sha256=_PRODUCTION_BASE_CORE_SHA256):
    if core_sha256 != _PRODUCTION_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_profile import verify_source as selected_source
        return selected_source(core_sha256)
    proof = load_pinned_json(REPLACEMENT_PROOF, REPLACEMENT_SHA)
    if proof['schema'] != 'civ6rl.production_replace961.source.v1' or proof['prior']['sha256'] != PROOF_SHA256 or proof['contracts']['occupied_queue_forbidden_by_ui']:
        raise RuntimeError('Replacement route proof changed')
    ui = proof['official_ui']
    if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(ui['path']))).read_bytes()).hexdigest() != ui['sha256']:
        raise RuntimeError('Official production UI changed')
    return proof

def _type_name(kind, value):
    if kind not in KINDS or type(value) is not str or (not re.fullmatch(kind.upper() + '_[A-Z0-9_]{1,100}', value)):
        raise ValueError('Invalid production type name')
    return value
_COMMON = "\nlocal function uint(v,label,max)\n assert(type(v)=='number' and v%1==0 and v>=0 and v<=max,'invalid '..label)\n return v\nend\nlocal function bits(v,label)\n assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=2147483647,\n        'invalid signed32 '..label)\n return v<0 and v+4294967296 or v\nend\nlocal function flag(v,label)\n assert(v==nil or type(v)=='boolean','invalid '..label)\n return v==true\nend\nlocal function n(v) return string.format('%.0f',v) end\nlocal function ready()\n assert(Game and Game.GetLocalPlayer()==pid,'production player perspective mismatch')\n assert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n        'production observer perspective mismatch')\n assert(Game.GetCurrentGameTurn()==expectedTurn,'production turn is stale')\n local p=Players and Players[pid]\n assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,\n        'production player is not ready')\n return p\nend\nlocal player=ready()\nassert(CityManager and type(CityManager.CanStartOperation)=='function' and\n       type(CityManager.RequestOperation)=='function','city operation API unavailable')\nlocal city,ids,count=nil,{},0\nfor _,c in player:GetCities():Members() do\n count=count+1;assert(count<=4096,'city enumeration bound exceeded')\n local id=uint(c:GetID(),'city ID',4294967295)\n assert(c:GetOwner()==pid and not ids[id],'foreign or duplicate city');ids[id]=true\n if id==cityID then city=c end\nend\nassert(city,'own city unavailable')\nlocal queue=city:GetBuildQueue()\nassert(queue and type(queue.GetSize)=='function' and type(queue.CanProduce)=='function',\n       'city queue production legality API unavailable')\nlocal queueSize=uint(queue:GetSize(),'queue size',4096)\nlocal currentHash=replaceCurrent and queue:GetCurrentProductionTypeHash() or 0\nbits(currentHash,'current production hash')\nlocal e=CityOperationTypes\nassert(e,'city operation enums unavailable')\nlocal op=bits(e.BUILD,'BUILD')\nlocal insert=bits(e.PARAM_INSERT_MODE,'insert key')\nlocal replace=bits(e.VALUE_REPLACE_AT,'replace value')\nlocal destination=bits(e.PARAM_QUEUE_DESTINATION_LOCATION,'destination key')\nlocal keys={unit=bits(e.PARAM_UNIT_TYPE,'unit key'),building=bits(e.PARAM_BUILDING_TYPE,'building key'),\n project=bits(e.PARAM_PROJECT_TYPE,'project key'),district=bits(e.PARAM_DISTRICT_TYPE,'district key')}\nlocal enumKeys={insert,destination,keys.unit,keys.building,keys.project,keys.district}\nlocal enumSeen={}\nfor _,key in ipairs(enumKeys) do assert(not enumSeen[key],'production enum keys collide');enumSeen[key]=true end\nlocal tables={unit=GameInfo.Units,building=GameInfo.Buildings,project=GameInfo.Projects,district=GameInfo.Districts}\nlocal fields={unit='UnitType',building='BuildingType',project='ProjectType',district='DistrictType'}\nlocal enumFields={unit='PARAM_UNIT_TYPE',building='PARAM_BUILDING_TYPE',project='PARAM_PROJECT_TYPE',district='PARAM_DISTRICT_TYPE'}\nlocal prefixes={unit='UNIT_',building='BUILDING_',project='PROJECT_',district='DISTRICT_'}\nlocal function identity(row,kind)\n assert(row,'missing GameInfo production row')\n local index=uint(row.Index,'production row index',2147483647)\n local hash=bits(row.Hash,'production row hash')\n local name=row[fields[kind]]\n assert(type(name)=='string' and #name<=#prefixes[kind]+100 and\n        string.match(name,'^'..prefixes[kind]..'[A-Z0-9_]+$'),'invalid production type name')\n return index,hash,name\nend\nlocal function eligible(row,kind)\n if replaceCurrent and row.Hash==currentHash and\n    (kind~='district' or flag(row.OnePerCity,'district OnePerCity')) then return false end\n if kind=='district' then\n  return not flag(row.RequiresPlacement,'district RequiresPlacement') and\n         not flag(row.InternalOnly,'district InternalOnly')\n end\n if kind=='unit' then return not flag(row.MustPurchase,'unit MustPurchase') end\n if kind=='building' then\n  if flag(row.RequiresPlacement,'RequiresPlacement') or flag(row.IsWonder,'IsWonder') then return false end\n  if flag(row.MustPurchase,'building MustPurchase') then\n   local buildings=city:GetBuildings()\n   assert(buildings and type(buildings.IsPillaged)=='function','building repair query unavailable')\n   local pillaged=buildings:IsPillaged(row.Hash)\n   assert(type(pillaged)=='boolean','invalid pillaged result');return pillaged\n  end\n end\n return true\nend\nlocal function parameters(row,kind)\n local args={}\n args[e[enumFields[kind]]]=row.Hash\n args[e.PARAM_INSERT_MODE]=e.VALUE_REPLACE_AT\n args[e.PARAM_QUEUE_DESTINATION_LOCATION]=0\n return args\nend\nlocal function producible(row,kind)\n local input=row.Hash\n if kind=='unit' then\n  assert(MilitaryFormationTypes,'military formation enum unavailable')\n  local standard=MilitaryFormationTypes.STANDARD_MILITARY_FORMATION\n  if standard~=nil then bits(standard,'standard military formation') end\n  -- Exact ProductionPanel standard-unit CanProduce input; this is not the\n  -- hash-keyed CityManager operation parameter map used for submission.\n  -- Lua omits the field when the official enum expression evaluates to nil.\n  -- Do not substitute the differently named STANDARD_FORMATION enum.\n  input={UnitType=row.Hash,MilitaryFormationType=standard}\n end\n local visible=queue:CanProduce(input,true)\n assert(type(visible)=='boolean','invalid native CanProduce visibility result')\n if not visible then return false end\n -- Match the UI's second query, including native detail-map construction.\n -- Only its first Boolean return determines admission here.\n local enabled=queue:CanProduce(input,false,true)\n assert(type(enabled)=='boolean','invalid native CanProduce enabled result')\n return enabled\nend\nlocal function legal(row,kind)\n if not producible(row,kind) then return false end\n local value=CityManager.CanStartOperation(city,e.BUILD,parameters(row,kind),false)\n assert(type(value)=='boolean','invalid native city legality result')\n return value\nend\n"

def _preamble(player_id, city_id, expected_turn, *, replace_current=False, core_sha256=_PRODUCTION_BASE_CORE_SHA256):
    pid = _uint(player_id, 'player ID', 63)
    city = _uint(city_id, 'city ID')
    turn = _uint(expected_turn, 'turn')
    verify_source(core_sha256=core_sha256)
    if type(replace_current) is not bool:
        raise ValueError('Replacement mode must be a boolean')
    if replace_current:
        verify_replacement_source(core_sha256=core_sha256)
    return f'local pid,cityID,expectedTurn={pid},{city},{turn}\nlocal replaceCurrent={str(replace_current).lower()}\n'.encode('ascii') + _COMMON.encode('ascii')

def catalog_source(player_id: int, city_id: int, expected_turn: int, *, replace_current=False, core_sha256=_PRODUCTION_BASE_CORE_SHA256) -> bytes:
    return _preamble(player_id, city_id, expected_turn, replace_current=replace_current, core_sha256=core_sha256) + "\nlocal choices,seenHash,scanned={},{},0\nif replaceCurrent or queueSize==0 then\n for _,kind in ipairs({'unit','building','project','district'}) do\n  local seenIndex,seenType={},{}\n  for row in tables[kind]() do\n   scanned=scanned+1;assert(scanned<=4096,'production definition bound exceeded')\n   local index,hash,name=identity(row,kind)\n   assert(not seenIndex[index] and not seenHash[hash] and not seenType[name],\n          'duplicate production definition identity')\n   seenIndex[index]=true;seenHash[hash]=true;seenType[name]=true\n   if eligible(row,kind) and legal(row,kind) then\n    assert(#choices<256,'production candidate bound exceeded')\n    choices[#choices+1]={kind=kind,index=index,hash=hash,name=name}\n   end\n  end\n end\nend\nlocal rank={unit=1,building=2,project=3,district=4}\ntable.sort(choices,function(a,b)\n if a.kind~=b.kind then return rank[a.kind]<rank[b.kind] end\n return a.index<b.index\nend)\nready()\nassert(city:GetOwner()==pid and queue:GetSize()==queueSize,\n       'production context changed while enumerating')\nassert(not replaceCurrent or queue:GetCurrentProductionTypeHash()==currentHash,'current production changed while enumerating')\nlocal status=(replaceCurrent or queueSize==0) and 'catalog' or 'queue_nonempty'\nlocal out={'production-v1',n(pid),n(cityID),n(expectedTurn),status,n(scanned),n(op),\n n(insert),n(replace),n(destination),n(keys.unit),n(keys.building),n(keys.project),n(keys.district),n(#choices)}\nfor _,choice in ipairs(choices) do\n out[#out+1]=choice.kind..':'..choice.name..':'..n(choice.index)..':'..n(choice.hash)\nend\nreturn table.concat(out,'|')\n".encode('ascii')

def _token(token: bytes, label: str, maximum=4294967295):
    if not re.fullmatch(b'0|[1-9][0-9]{0,9}', token):
        raise ValueError('Invalid canonical ' + label)
    return _uint(int(token), label, maximum)

def parse_catalog(payload: bytes, player_id: int, city_id: int, expected_turn: int) -> dict:
    pid, city, turn = (_uint(player_id, 'player ID', 63), _uint(city_id, 'city ID'), _uint(expected_turn, 'turn'))
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError('Invalid production catalog payload')
    tokens = payload.split(b'|')
    if len(tokens) < 15 or tokens[0] != b'production-v1' or tokens[4] not in (b'catalog', b'queue_nonempty'):
        raise ValueError('Invalid production catalog protocol')
    if tuple((_token(tokens[i], 'identity') for i in (1, 2, 3))) != (pid, city, turn):
        raise ValueError('Foreign or stale production catalog')
    scanned = _token(tokens[5], 'definition count', MAX_DEFINITIONS)
    op, insert, replace, destination, unit, building, project, district = (_token(t, 'operation enum') for t in tokens[6:14])
    keys = {'unit': unit, 'building': building, 'project': project, 'district': district}
    if len({insert, destination, *keys.values()}) != 6:
        raise ValueError('Production parameter keys collide')
    count = _token(tokens[14], 'candidate count', MAX_CANDIDATES)
    if count != len(tokens) - 15 or count > scanned:
        raise ValueError('Invalid production catalog counts')
    status = tokens[4].decode('ascii')
    if status == 'queue_nonempty' and (count or scanned):
        raise ValueError('Nonempty queue must not claim enumerated production choices')
    choices, previous, hashes, names = ([], (-1, -1), set(), set())
    for token in tokens[15:]:
        values = token.split(b':')
        if len(values) != 4:
            raise ValueError('Malformed production candidate')
        try:
            kind, name = (values[0].decode('ascii'), values[1].decode('ascii'))
        except UnicodeDecodeError as exc:
            raise ValueError('Invalid production identity encoding') from exc
        _type_name(kind, name)
        index, row_hash = (_token(values[2], 'production index', 2147483647), _token(values[3], 'production hash'))
        order = (KINDS.index(kind), index)
        if order <= previous or row_hash in hashes or name in names:
            raise ValueError('Production catalog is unsorted or ambiguous')
        previous = order
        hashes.add(row_hash)
        names.add(name)
        choices.append({'kind': kind, 'item_type': name, 'index': index, 'hash': row_hash, 'arguments': tuple(sorted(((keys[kind], row_hash), (insert, replace), (destination, 0))))})
    return {'status': status, 'player_id': pid, 'city_id': city, 'current_game_turn': turn, 'definitions_scanned': scanned, 'operation': op, 'insert_key': insert, 'replace_value': replace, 'destination_key': destination, 'parameter_keys': keys, 'candidates': tuple(choices), 'not_wired': NOT_WIRED, 'complete_action_space': False}

def choose(catalog: dict, kind: str, index: int) -> dict:
    """Choose an explicit catalog member; no warrior or other fallback selection."""
    if type(catalog) is not dict or catalog.get('status') != 'catalog' or kind not in KINDS:
        raise ValueError('Invalid selectable production catalog')
    expected = {'status', 'player_id', 'city_id', 'current_game_turn', 'definitions_scanned', 'operation', 'insert_key', 'replace_value', 'destination_key', 'parameter_keys', 'candidates', 'not_wired', 'complete_action_space'}
    if set(catalog) != expected or catalog['not_wired'] != NOT_WIRED or catalog['complete_action_space'] is not False:
        raise ValueError('Production catalog schema changed')
    scanned = _uint(catalog['definitions_scanned'], 'definition count', MAX_DEFINITIONS)
    keys = catalog['parameter_keys']
    if type(keys) is not dict or set(keys) != set(KINDS):
        raise ValueError('Production kind keys changed')
    for value in keys.values():
        _uint(value, 'production kind parameter key')
    if len({catalog['insert_key'], catalog['destination_key'], *keys.values()}) != 6:
        raise ValueError('Production kind keys collide')
    candidates = catalog['candidates']
    if type(candidates) is not tuple or len(candidates) > min(MAX_CANDIDATES, scanned):
        raise ValueError('Invalid production candidate collection')
    previous, hashes, names = ((-1, -1), set(), set())
    for entry in candidates:
        if type(entry) is not dict or set(entry) != {'kind', 'item_type', 'index', 'hash', 'arguments'}:
            raise ValueError('Invalid production candidate schema')
        probe = {key: catalog[key] for key in ('player_id', 'city_id', 'current_game_turn', 'operation', 'insert_key', 'replace_value', 'destination_key')}
        probe.update(entry)
        if entry['kind'] not in KINDS:
            raise ValueError('Unknown production candidate kind')
        probe['parameter_key'] = keys[entry['kind']]
        _validate_choice(probe)
        order = (KINDS.index(entry['kind']), entry['index'])
        if order <= previous or entry['hash'] in hashes or entry['item_type'] in names:
            raise ValueError('Production candidates are unsorted or ambiguous')
        previous = order
        hashes.add(entry['hash'])
        names.add(entry['item_type'])
    _uint(index, 'production index', 2147483647)
    matches = [entry for entry in catalog.get('candidates', ()) if entry.get('kind') == kind and entry.get('index') == index]
    if len(matches) != 1:
        raise ValueError('Requested production is not a unique catalog member')
    choice = {key: catalog[key] for key in ('player_id', 'city_id', 'current_game_turn', 'operation', 'insert_key', 'replace_value', 'destination_key')}
    choice.update(matches[0])
    choice['parameter_key'] = catalog['parameter_keys'][kind]
    _validate_choice(choice)
    return choice

def _validate_choice(choice: dict):
    expected = {'player_id', 'city_id', 'current_game_turn', 'operation', 'insert_key', 'replace_value', 'destination_key', 'parameter_key', 'kind', 'item_type', 'index', 'hash', 'arguments'}
    if type(choice) is not dict or set(choice) != expected:
        raise ValueError('Invalid chosen production schema')
    for key in expected - {'kind', 'item_type', 'arguments'}:
        _uint(choice[key], key, 63 if key == 'player_id' else 2147483647 if key == 'index' else 4294967295)
    _type_name(choice['kind'], choice['item_type'])
    keys = (choice['parameter_key'], choice['insert_key'], choice['destination_key'])
    if len(set(keys)) != 3:
        raise ValueError('Chosen production argument keys collide')
    expected_args = tuple(sorted(((keys[0], choice['hash']), (keys[1], choice['replace_value']), (keys[2], 0))))
    args = choice['arguments']
    if type(args) is not tuple or len(args) != 3 or any((type(a) is not tuple or len(a) != 2 or any((type(v) is not int for v in a)) for a in args)) or (args != expected_args):
        raise ValueError('Chosen production argument tuple changed')

def request_source(choice: dict, *, replace_current=False, core_sha256=_PRODUCTION_BASE_CORE_SHA256) -> bytes:
    _validate_choice(choice)
    header = _preamble(choice['player_id'], choice['city_id'], choice['current_game_turn'], replace_current=replace_current, core_sha256=core_sha256)
    expected = f"local kind,name,wantedIndex,wantedHash='{choice['kind']}','{choice['item_type']}',{choice['index']},{choice['hash']}\n"
    expected += f"assert(op=={choice['operation']} and insert=={choice['insert_key']} and replace=={choice['replace_value']} and destination=={choice['destination_key']} and keys[kind]=={choice['parameter_key']},'production enums changed')\n"
    return header + expected.encode('ascii') + "\nassert(replaceCurrent or queueSize==0,'production request requires an empty queue')\nlocal row=tables[kind][name]\nlocal index,hash,rowName=identity(row,kind)\nassert(index==wantedIndex and hash==wantedHash and rowName==name,'production row identity changed')\nlocal byIndex=tables[kind][wantedIndex]\nlocal i2,h2,n2=identity(byIndex,kind)\nassert(i2==index and h2==hash and n2==name,'production index/name lookup mismatch')\nassert(eligible(row,kind),'production choice moved outside supported category')\nready()\nassert(city:GetOwner()==pid and city:GetID()==cityID and queue:GetSize()==queueSize and\n       (not replaceCurrent or queue:GetCurrentProductionTypeHash()==currentHash),\n       'production context changed before request')\nassert(legal(row,kind),'native production legality rejected request')\nready()\nassert(city:GetOwner()==pid and queue:GetSize()==queueSize and\n       (not replaceCurrent or queue:GetCurrentProductionTypeHash()==currentHash),'production context changed during legality query')\n-- RequestOperation returns no success value. Only exact one submission is claimed.\nCityManager.RequestOperation(city,e.BUILD,parameters(row,kind))\nreturn 'submitted'\n".encode('ascii')

def guard_case() -> bytes:
    """Actual collector/request chunks against Lua doubles; no gameplay claim."""
    payload = b'production-v1|0|5|4|catalog|9|7|12|90|13|11|14|15|16|5|unit:UNIT_WARRIOR:21:3920984880|unit:UNIT_SETTLER:22:99|building:BUILDING_GRANARY:0:100|project:PROJECT_TEST:0:103|district:DISTRICT_TEST:0:104'
    catalog = parse_catalog(payload, 0, 5, 4)
    chunks = ["\nlocal localID,observer,turn,owner,size=0,0,4,0,0\nlocal alive,active,complete,exists,duplicate,allowed=true,true,true,true,false,true\nlocal visible,producible=true,true\nlocal canStartCalls,canProduceCalls=0,{}\nlocal pillaged,submits,mutate=false,0,false\nlocal Game={GetLocalPlayer=function() return localID end,GetLocalObserver=function() return observer end,\n GetCurrentGameTurn=function() return turn end}\nlocal MilitaryFormationTypes={STANDARD_MILITARY_FORMATION=0,STANDARD_FORMATION=999}\nlocal unitRows={{UnitType='UNIT_WARRIOR',Index=21,Hash=-373982416},\n {UnitType='UNIT_SETTLER',Index=22,Hash=99}}\nlocal buildingRows={{BuildingType='BUILDING_GRANARY',Index=0,Hash=100},\n {BuildingType='BUILDING_WONDER',Index=1,Hash=101,IsWonder=true,RequiresPlacement=true},\n {BuildingType='BUILDING_PURCHASE',Index=2,Hash=102,MustPurchase=true},\n {BuildingType='BUILDING_PLACE',Index=3,Hash=105,RequiresPlacement=true}}\nlocal projectRows={{ProjectType='PROJECT_TEST',Index=0,Hash=103}}\nlocal districtRows={{DistrictType='DISTRICT_TEST',Index=0,Hash=104},\n {DistrictType='DISTRICT_PLACE',Index=1,Hash=106,RequiresPlacement=true}}\nlocal function info(rows,field)\n local t={}\n for _,r in ipairs(rows) do t[r[field]]=r;t[r.Index]=r end\n return setmetatable(t,{__call=function() local i=0;return function() i=i+1;return rows[i] end end})\nend\nlocal GameInfo={}\nlocal function resetInfo()\n GameInfo.Units=info(unitRows,'UnitType');GameInfo.Buildings=info(buildingRows,'BuildingType')\n GameInfo.Projects=info(projectRows,'ProjectType');GameInfo.Districts=info(districtRows,'DistrictType')\nend\nresetInfo()\nlocal queue={GetSize=function() return size end,CanProduce=function(_,input,visibility,details)\n local hash=input\n if type(input)=='table' then\n  assert(input.MilitaryFormationType==MilitaryFormationTypes.STANDARD_MILITARY_FORMATION)\n  local count=0;for _ in pairs(input) do count=count+1 end\n  local expected=MilitaryFormationTypes.STANDARD_MILITARY_FORMATION==nil and 1 or 2\n  assert(count==expected and input.UnitType~=nil);hash=input.UnitType\n end\n assert(type(hash)=='number')\n canProduceCalls[#canProduceCalls+1]={hash=hash,visibility=visibility,details=details}\n if visibility then assert(details==nil);return visible end\n assert(visibility==false and details==true)\n return producible,{}\nend}\nlocal buildings={IsPillaged=function(_,hash) assert(hash==102);return pillaged end}\nlocal city={GetID=function() return 5 end,GetOwner=function() return owner end,\n GetBuildQueue=function() return queue end,GetBuildings=function() return buildings end}\nlocal player={IsAlive=function() return alive end,IsTurnActive=function() return active end,\n IsTurnActiveComplete=function() return complete end,GetCities=function()\n return {Members=function() local i=0;return function() i=i+1\n  if exists and (i==1 or (i==2 and duplicate)) then return i,city end end end} end}\nlocal Players={[0]=player}\nlocal CityOperationTypes={BUILD=7,PARAM_INSERT_MODE=12,VALUE_REPLACE_AT=90,\n PARAM_QUEUE_DESTINATION_LOCATION=13,PARAM_UNIT_TYPE=11,PARAM_BUILDING_TYPE=14,\n PARAM_PROJECT_TYPE=15,PARAM_DISTRICT_TYPE=16}\nlocal function check(c,op,args)\n assert(c==city and op==7 and args[12]==90 and args[13]==0)\n local count,types=0,0\n for k in pairs(args) do count=count+1;if k==11 or k==14 or k==15 or k==16 then types=types+1 end end\n assert(count==3 and types==1)\nend\nlocal CityManager={CanStartOperation=function(c,op,args,details)\n canStartCalls=canStartCalls+1\n check(c,op,args);assert(details==false)\n if mutate then size=1 end\n return allowed end,RequestOperation=function(c,op,args)\n check(c,op,args);assert(localID==0 and observer==0 and turn==4 and owner==0 and size==0 and\n alive and active and complete and exists and not duplicate and allowed and visible and producible)\n submits=submits+1 end}\nlocal function collect()\n".encode('ascii'), catalog_source(0, 5, 4), b'\nend\n']
    for number, (kind, index) in enumerate((('unit', 21), ('building', 0), ('project', 0), ('district', 0)), 1):
        chunks.extend([f'local function request{number}()\n'.encode(), request_source(choose(catalog, kind, index)), b'\nend\n'])
    chunks.append(b"assert(collect()=='" + payload + b"' and submits==0)\n")
    chunks.append("\nlocal function reject() assert(not pcall(request1) and submits==0) end\nlocalID=1;assert(not pcall(collect));reject();localID=0\nobserver=1;assert(not pcall(collect));reject();observer=0\nturn=5;reject();turn=4\nalive=false;reject();alive=true\nactive=false;reject();active=true\ncomplete=false;reject();complete=true\nowner=1;reject();owner=0\nexists=false;reject();exists=true\nduplicate=true;reject();duplicate=false\nsize=1;assert(string.find(collect(),'|queue_nonempty|0|',1,true));reject();size=0\nallowed=false;assert(not string.find(collect(),'UNIT_WARRIOR',1,true));reject();allowed=true\n-- CanStartOperation alone would accept: both UI CanProduce stages must veto.\nvisible=false;canProduceCalls={};local prior=canStartCalls\nassert(not string.find(collect(),'UNIT_WARRIOR',1,true));reject()\nassert(canStartCalls==prior and submits==0)\nfor _,call in ipairs(canProduceCalls) do assert(call.visibility==true and call.details==nil) end\nvisible=true;producible=false;canProduceCalls={};prior=canStartCalls\nassert(not string.find(collect(),'UNIT_WARRIOR',1,true));reject()\nassert(canStartCalls==prior and submits==0)\nassert(canProduceCalls[1].visibility==true and canProduceCalls[2].visibility==false and canProduceCalls[2].details==true)\nproducible=true\n-- The same vetoes protect every supported category, not only units.\nfor _,request in ipairs({request2,request3,request4}) do\n visible=false;assert(not pcall(request) and submits==0);visible=true\n producible=false;assert(not pcall(request) and submits==0);producible=true\nend\nlocal savedCanProduce=queue.CanProduce\nqueue.CanProduce=function() return 1 end;reject()\nqueue.CanProduce=function(_,_,visibility) if visibility then return true end end;reject()\nqueue.CanProduce=savedCanProduce\ndistrictRows[1].InternalOnly=true\nassert(not string.find(collect(),'DISTRICT_TEST',1,true) and not pcall(request4) and submits==0)\ndistrictRows[1].InternalOnly=nil\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION=true;reject()\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION='0';reject()\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION=0.5;reject()\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION=0\nunitRows[1].Hash=-1;reject();unitRows[1].Hash=-373982416\nGameInfo.Units[21]=unitRows[2];reject();resetInfo()\nunitRows[1].MustPurchase=true;assert(not string.find(collect(),'UNIT_WARRIOR',1,true));reject();unitRows[1].MustPurchase=nil\nCityOperationTypes.PARAM_INSERT_MODE=999;reject();CityOperationTypes.PARAM_INSERT_MODE=12\nmutate=true;reject();mutate=false;size=0\npillaged=true;assert(string.find(collect(),'BUILDING_PURCHASE',1,true));pillaged=false\nassert(not string.find(collect(),'BUILDING_WONDER',1,true))\nassert(not string.find(collect(),'BUILDING_PLACE',1,true))\nassert(not string.find(collect(),'DISTRICT_PLACE',1,true))\nlocal saved=unitRows\nunitRows={}\nfor i=1,257 do unitRows[i]={UnitType='UNIT_BOUND_'..i,Index=i,Hash=10000+i} end\nresetInfo();assert(not pcall(collect),'candidate overflow must refuse rather than truncate')\nallowed=false\nfor i=258,4097 do unitRows[i]={UnitType='UNIT_BOUND_'..i,Index=i,Hash=10000+i} end\nresetInfo();assert(not pcall(collect),'definition overflow must refuse rather than truncate')\nallowed=true;unitRows=saved;resetInfo()\nunitRows[2].Hash=unitRows[1].Hash;assert(not pcall(collect));unitRows[2].Hash=99\nunitRows[1].Hash=2147483648;assert(not pcall(collect));unitRows[1].Hash=-373982416\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION=nil\nassert(string.find(collect(),'UNIT_WARRIOR',1,true))\nassert(request1()=='submitted' and submits==1)\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION=7\nassert(request1()=='submitted' and submits==2)\nMilitaryFormationTypes.STANDARD_MILITARY_FORMATION=0\nassert(request1()=='submitted' and submits==3)\nassert(request2()=='submitted' and submits==4)\nassert(request3()=='submitted' and submits==5)\nassert(request4()=='submitted' and submits==6)\nreturn 'native-production-catalog-guards-ok'\n".encode('ascii'))
    return b''.join(chunks)

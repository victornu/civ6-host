"""Bounded own-player religion readback, with no action or success inference.

Execute build_source() only through the existing protected Lua evaluator after
native cache publication. This module neither invokes that evaluator nor submits
an operation. Global religion rows are projected to the acting player's row.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.contracts.religion_beliefs import (
    HOLY_CITY_DISPLAY_LABEL, MAX_HOLY_CITY_LABEL_BYTES, holy_city_label_bytes,
)
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_religion_observation.py')))).resolve().parents[1]
PROOF_SHA256 = 'c5f6dd96698059bf7fc4b8c4bf765d4876857f1963d1772657c67866f32609e0'
BASE_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MAX_CITIES = 256
MAX_RELIGIONS = 4096
MAX_BELIEFS = 4096
MAX_RESPONSE = 65536
_PREFIX = b'religion-observation-v1'
_LABEL_PREFIX = b'religion-observation-v2'

def verify_source(core_sha256=BASE_CORE_SHA256):
    if core_sha256 != BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_religion_observation_source import verify_source as selected
        return selected(core_sha256)
    proof = load_pinned_json(ROOT / 'evidence/native-religion-founding-actions' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    expected = {'PlayerReligion.GetReligionTypeCreated': '0x18053ac00', 'PlayerReligion.HasReligiousFoundingUnit': '0x18053aca0', 'PlayerReligion.GetNumBeliefsEarned': '0x18053ab10', 'PlayerReligion.GetHolyCityID': '0x18053aad0', 'GameReligion.GetReligions': '0x180527680'}
    if proof.get('schema') != 'civ6rl.native_religion_founding_actions.static.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or any((proof.get('bindings', {}).get(name, {}).get('callback_va') != value for name, value in expected.items())) or (proof['getter_contracts']['GameReligion.GetReligions']['native_cache_row_stride'] != 56) or (proof['getter_contracts']['GameReligion.GetReligions']['fields']['Religion']['offset'] != 0) or (proof['getter_contracts']['GameReligion.GetReligions']['fields']['Founder']['offset'] != 4):
        raise RuntimeError('Native religion observation source identity changed')
    return proof

def source_hash(core_sha256=BASE_CORE_SHA256):
    if core_sha256 == BASE_CORE_SHA256:
        return PROOF_SHA256
    from civ6_host.runtime.xp1_religion_observation_source import source_hash as selected
    return selected(core_sha256)


def inspect_snapshot(prefix, player_id, *, core_sha256=BASE_CORE_SHA256):
    """Read through the actual caller's Lua owner; never submit an operation."""
    _uint(player_id, 'player ID', 63)
    verify_source(core_sha256)
    if prefix.ui_child is None or prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Religion readback requires drained queues and a current player view')
    if getattr(prefix, '_religion_observation_guard_profile', None) != core_sha256:
        marker = prefix.runtime.evaluate_text(prefix.ui_child,
            guard_case(core_sha256=core_sha256), b'@religion_observation_guards')
        if marker != b'native-religion-observation-guards-ok':
            raise RuntimeError('Native HKS religion observation guards failed')
        prefix._religion_observation_guards_verified = True
        prefix._religion_observation_guard_profile = core_sha256
        prefix.emit('native_hks_religion_observation_guards_verified',
            native_gameplay_mutated=False, eligible_for_training=False)
    turn = int(prefix.runtime.evaluate_text(prefix.ui_child,
        b'return string.format("%.0f",Game.GetCurrentGameTurn())', b'@native_religion_observation_turn'))
    result = parse_observation(prefix.runtime.evaluate_text(prefix.ui_child,
        build_source(player_id, turn, core_sha256=core_sha256),
        b'@native_own_religion_observation', capacity=MAX_RESPONSE),
        player_id, turn, core_sha256=core_sha256)
    prefix.emit('native_own_religion_observed', observation=result,
        native_gameplay_mutated=False, eligible_for_training=False)
    return result


def _uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid ' + label)
    return value

def _token(raw, label, minimum=0, maximum=2147483647):
    if not raw or len(raw) > 11:
        raise ValueError('Invalid ' + label)
    digits = raw[1:] if raw.startswith(b'-') else raw
    if not digits or any((c < 48 or c > 57 for c in digits)) or (len(digits) > 1 and digits.startswith(b'0')) or (raw == b'-0'):
        raise ValueError('Noncanonical ' + label)
    value = int(raw)
    if not minimum <= value <= maximum:
        raise ValueError('Out-of-range ' + label)
    return value

def build_source(player_id, expected_turn, *, core_sha256=BASE_CORE_SHA256):
    """Build one protected-call chunk; no getters execute in Python."""
    pid = _uint(player_id, 'player ID', 63)
    turn = _uint(expected_turn, 'expected game turn')
    verify_source(core_sha256)
    resolve_founded_city = 'true' if core_sha256 == XP2_CORE_SHA256 else 'false'
    prefix = (
        f'local pid,expectedTurn={pid},{turn}\n'
        f'local maxCities,maxReligions,maxBeliefs={MAX_CITIES},{MAX_RELIGIONS},{MAX_BELIEFS}\n'
        f'local resolveFoundedCity={resolve_founded_city}\n'
        f'local maxHolyCityLabelBytes={MAX_HOLY_CITY_LABEL_BYTES}\n'
    )
    return prefix.encode('ascii') + _READ_LUA


_READ_LUA = br"""
local function integer(value,label,low,high)
 assert(type(value)=='number' and value%1==0 and value>=low and value<=high,
        'invalid religion observation '..label)
 return value
end
local function boolean(value,label)
 assert(type(value)=='boolean','invalid religion observation '..label)
 return value
end
assert(Game and type(Game.GetLocalPlayer)=='function' and
 type(Game.GetLocalObserver)=='function' and type(Game.GetCurrentGameTurn)=='function',
 'religion observation context API unavailable')
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
 Game.GetCurrentGameTurn()==expectedTurn,'foreign or stale religion observation')
local player=Players and Players[pid]
assert(player and type(player.IsAlive)=='function' and type(player.IsTurnActive)=='function' and
 type(player.IsTurnActiveComplete)=='function','religion observation player unavailable')
local function context()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
  Game.GetCurrentGameTurn()==expectedTurn and Players[pid]==player,
  'religion observation context changed')
 assert(player:IsAlive()==true and player:IsTurnActive()==true and
  player:IsTurnActiveComplete()==true,'religion observation player is not ready')
end
context()
-- Validate the player's own city collection before obtaining religion state.
assert(type(player.GetCities)=='function','own city collection API unavailable')
local collection=player:GetCities()
assert(collection and type(collection.Members)=='function','own city collection unavailable')
local ownCities,cityCount={},0
for _,city in collection:Members() do
 cityCount=cityCount+1
 assert(cityCount<=maxCities,'own city collection exceeds observation bound')
 assert(city and type(city.GetOwner)=='function' and type(city.GetID)=='function',
        'invalid own city object')
 assert(city:GetOwner()==pid,'foreign city in own collection')
 local cityID=integer(city:GetID(),'own city ID',0,2147483647)
 assert(ownCities[cityID]==nil,'duplicate own city ID')
 ownCities[cityID]=city
end
local function citiesStillOwn()
 for id,city in pairs(ownCities) do
  assert(city:GetOwner()==pid and city:GetID()==id,'own city identity changed')
 end
end
assert(type(player.GetReligion)=='function' and type(Game.GetReligion)=='function',
 'religion observation getters unavailable')
local religion=player:GetReligion()
assert(religion and type(religion.GetReligionTypeCreated)=='function' and
 type(religion.HasReligiousFoundingUnit)=='function' and
 type(religion.GetNumBeliefsEarned)=='function' and type(religion.GetHolyCityID)=='function',
 'player religion observation API unavailable')
local created=integer(religion:GetReligionTypeCreated(),'created religion index',-1,2147483647)
local function readHolyCity()
 local descriptor=religion:GetHolyCityID()
 assert(type(descriptor)=='table','GetHolyCityID did not return a descriptor table')
 local count=0
 for key,_ in pairs(descriptor) do
  assert(key=='player' or key=='type' or key=='id','unexpected holy city descriptor field')
  count=count+1
 end
 assert(count==3,'incomplete holy city descriptor')
 local owner=integer(descriptor.player,'holy city player',-1,63)
 local kind=integer(descriptor.type,'holy city type',-32768,32767)
 local id=integer(descriptor.id,'holy city ID',-1,2147483647)
 assert(kind==2,'holy city descriptor is not a city')
 if owner==-1 or id==-1 then
  assert(owner==-1 and id==-1,'partial holy city absence sentinel')
 elseif owner~=pid or ownCities[id]==nil then
  if resolveFoundedCity and created>=0 then
   -- The XP2 ReligionScreen shows this label for the actor's founded religion.
   assert(CityManager and type(CityManager.GetCity)=='function','holy city resolver unavailable')
   local city=CityManager.GetCity(descriptor)
   local label=nil
   if city~=nil then
    assert(type(city.GetName)=='function' and Locale and type(Locale.Lookup)=='function' and
           type(Locale.ToUpper)=='function','holy city display unavailable')
    label=Locale.ToUpper(Locale.Lookup("LOC_UI_RELIGION_HOLY_CITY",city:GetName()))
    assert(type(label)=='string' and #label>0 and #label<=maxHolyCityLabelBytes and
           not label:find(string.char(0),1,true),'invalid holy city display label')
   end
   return owner,kind,id,-1,-1,label
  end
  assert(owner==pid,'holy city is not owned by the observed player')
  assert(ownCities[id]~=nil,'holy city is absent from own city collection')
 end
 return owner,kind,id,owner,id
end
local foundingUnit=boolean(religion:HasReligiousFoundingUnit(),'founding-unit presence')
local earned=integer(religion:GetNumBeliefsEarned(),'beliefs earned',0,2147483647)
local holyOwnerRaw,holyType,holyIDRaw,holyOwner,holyID,holyLabel=readHolyCity()
local global=Game.GetReligion()
assert(global and type(global.GetReligions)=='function','global religion collection unavailable')
local all=global:GetReligions()
local function denseLength(values,label,bound)
 assert(type(values)=='table','invalid '..label..' table')
 local count,highest=0,0
 for key,_ in pairs(values) do
  integer(key,label..' key',1,bound)
  count=count+1;assert(count<=bound,label..' exceeds observation bound')
  if key>highest then highest=key end
 end
 assert(count==highest,'sparse '..label..' table')
 return count
end
local count=denseLength(all,'religion list',maxReligions)
local own,ownIndex=nil,-1
for i=1,count do
 local entry=all[i]
 assert(type(entry)=='table','invalid native religion row')
 -- Do not read Religion, Beliefs, CustomName or any other foreign-row data.
 local founder=integer(entry.Founder,'religion founder',0,63)
 if founder==pid then
  assert(own==nil,'ambiguous duplicate own religion rows')
  own=entry
  ownIndex=integer(entry.Religion,'own religion index',0,2147483647)
 end
end
assert((own==nil and created==-1) or (own~=nil and created==ownIndex),
       'player/global own religion state is inconsistent')
local beliefs,seen={},{ }
if own~=nil then
 local n=denseLength(own.Beliefs,'own beliefs',maxBeliefs)
 for i=1,n do
  local value=integer(own.Beliefs[i],'own belief index',0,2147483647)
  assert(not seen[value],'duplicate own belief index')
  seen[value]=true;beliefs[i]=value
 end
end
-- The output is an observation, never an activation/founding success claim.
local function dec(value) return string.format('%.0f',value) end
local out={'religion-observation-v1',dec(pid),dec(expectedTurn),dec(created),
 foundingUnit and '1' or '0',dec(earned),dec(holyOwner),dec(holyType),dec(holyID),
 own and '1' or '0',dec(ownIndex),own and dec(pid) or '-1',dec(#beliefs)}
for i=1,#beliefs do out[#out+1]=dec(beliefs[i]) end
if holyLabel~=nil then
 out[1]='religion-observation-v2'
 out[#out+1]=(holyLabel:gsub('.',function(byte) return string.format('%02x',byte:byte()) end))
end
assert(religion:GetReligionTypeCreated()==created and
 religion:HasReligiousFoundingUnit()==foundingUnit and religion:GetNumBeliefsEarned()==earned,
 'player religion state changed during observation')
local rawOwnerAgain,typeAgain,rawIDAgain,ownerAgain,idAgain,labelAgain=readHolyCity()
assert(rawOwnerAgain==holyOwnerRaw and typeAgain==holyType and rawIDAgain==holyIDRaw and
 ownerAgain==holyOwner and idAgain==holyID and labelAgain==holyLabel,
 'holy city changed during observation')
citiesStillOwn()
context()
return table.concat(out,'|')
"""

def parse_observation(payload, player_id, expected_turn, *, core_sha256=BASE_CORE_SHA256):
    pid = _uint(player_id, 'player ID', 63)
    turn = _uint(expected_turn, 'expected game turn')
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid religion observation payload')
    tokens = payload.split(b'|')
    if len(tokens) < 13 or tokens[0] not in (_PREFIX, _LABEL_PREFIX):
        raise ValueError('Invalid religion observation protocol')
    actual_pid = _token(tokens[1], 'player ID', 0, 63)
    actual_turn = _token(tokens[2], 'game turn', 0, 4294967295)
    if (actual_pid, actual_turn) != (pid, turn):
        raise ValueError('Foreign or stale religion observation')
    created = _token(tokens[3], 'created religion', -1)
    if tokens[4] not in (b'0', b'1') or tokens[9] not in (b'0', b'1'):
        raise ValueError('Invalid religion observation Boolean')
    earned = _token(tokens[5], 'beliefs earned')
    owner = _token(tokens[6], 'holy city owner', -1, 63)
    kind = _token(tokens[7], 'holy city type', -32768, 32767)
    city_id = _token(tokens[8], 'holy city ID', -1)
    if kind != 2 or not (owner == -1 and city_id == -1 or (owner == pid and city_id >= 0)):
        raise ValueError('Foreign or malformed holy city descriptor')
    own_present = tokens[9] == b'1'
    own_index = _token(tokens[10], 'own religion index', -1)
    own_founder = _token(tokens[11], 'own religion founder', -1, 63)
    count = _token(tokens[12], 'own belief count', 0, MAX_BELIEFS)
    has_label = tokens[0] == _LABEL_PREFIX
    if len(tokens) != 13 + count + int(has_label):
        raise ValueError('Religion observation count does not match payload')
    beliefs = [_token(token, 'own belief index') for token in tokens[13:13 + count]]
    if len(set(beliefs)) != len(beliefs):
        raise ValueError('Duplicate own belief indices')
    if own_present:
        if created < 0 or own_index != created or own_founder != pid:
            raise ValueError('Inconsistent own founded-religion state')
    elif created != -1 or own_index != -1 or own_founder != -1 or beliefs:
        raise ValueError('Absent own religion contains data')
    value = {
        'player_id': pid, 'current_game_turn': turn, 'religion_type_created': created,
        'has_religious_founding_unit': tokens[4] == b'1', 'num_beliefs_earned': earned,
        'holy_city': {'player': owner, 'type': kind, 'id': city_id}, 'holy_city_present': city_id >= 0,
        'own_religion': {'religion_index': own_index, 'founder': own_founder, 'belief_indices': beliefs}
        if own_present else None,
        'observation_only': True, 'action_effect_verified': False,
        'source_proof_sha256': source_hash(core_sha256),
        'exposed_to_learner': False, 'eligible_for_training': False,
    }
    if has_label:
        if core_sha256 != XP2_CORE_SHA256 or not own_present or city_id != -1:
            raise ValueError('Holy city display label outside its native observation scope')
        token = tokens[-1]
        if not 0 < len(token) <= MAX_HOLY_CITY_LABEL_BYTES * 2:
            raise ValueError('Invalid holy city display label length')
        label = bytes.fromhex(token.decode('ascii')).decode('utf-8')
        if holy_city_label_bytes(label).hex().encode('ascii') != token:
            raise ValueError('Noncanonical holy city display label')
        value[HOLY_CITY_DISPLAY_LABEL] = label
    return value

def guard_case(*, core_sha256=BASE_CORE_SHA256):
    """Execute the real chunk against isolated Lua doubles (Lupa or protected HKS)."""
    source = build_source(0, 50, core_sha256=core_sha256).decode('ascii')
    return ("local localID,observer,turn=0,0,50\nlocal alive,active,complete=true,true,true\nlocal owner,cityID=0,65536\nlocal created,foundingUnit,earned=4,false,2\nlocal holy={player=0,type=2,id=65536}\nlocal beliefs={10,11}\nlocal religionReads,cityIDReads,foreignReads=0,0,0\nlocal duplicateCity,duplicateOwn,foreignOnly=false,false,false\nlocal sparseList,extraList,contextMutation=false,false,false\nlocal createdReads,mutateCreated=0,false\nlocal foreign=setmetatable({Founder=1},{__index=function(_,key)\n foreignReads=foreignReads+1;error('foreign religion field read: '..tostring(key)) end})\nlocal own={Founder=0,Religion=4,Beliefs=beliefs}\nlocal city={GetOwner=function() return owner end,\n GetID=function() cityIDReads=cityIDReads+1;return cityID end}\nlocal religion={\n GetReligionTypeCreated=function()\n  createdReads=createdReads+1\n  if mutateCreated and createdReads%2==0 then return created+1 end\n  return created end,\n HasReligiousFoundingUnit=function() return foundingUnit end,\n GetNumBeliefsEarned=function() return earned end,\n GetHolyCityID=function() return holy end}\nlocal player={IsAlive=function() return alive end,IsTurnActive=function() return active end,\n IsTurnActiveComplete=function() return complete end,\n GetCities=function() return {Members=function()\n  local n=0;return function()\n   n=n+1;if n==1 or (duplicateCity and n==2) then return n,city end\n  end end} end,\n GetReligion=function() religionReads=religionReads+1;return religion end}\nlocal Players={[0]=player}\nlocal Game={GetLocalPlayer=function() return localID end,\n GetLocalObserver=function() return observer end,GetCurrentGameTurn=function() return turn end,\n GetReligion=function() return {GetReligions=function()\n  if contextMutation then observer=1 end\n  if sparseList then return {[1]=foreign,[3]=own} end\n  if extraList then return {[1]=foreign,[2]=own,x=own} end\n  if duplicateOwn then return {foreign,own,own} end\n  if foreignOnly then return {foreign} end\n  return {foreign,own}\n end} end}\nlocal function forbidden() error('readback attempted an action or hidden plot query') end\nlocal UnitManager={RequestOperation=forbidden,CanStartOperation=forbidden}\nlocal UI={RequestPlayerOperation=forbidden}\nlocal Map={GetPlotByIndex=forbidden,GetPlot=forbidden}\nlocal CityManager,Locale={},{}\nlocal function observe()\n" + source + "\nend\nlocal function rejected() local ok=pcall(observe);assert(not ok,'invalid religion observation accepted') end\nlocal result=observe()\nassert(result=='religion-observation-v1|0|50|4|0|2|0|2|65536|1|4|0|2|10|11')\nassert(foreignReads==0,'foreign religion data was accessed')\nlocal before=religionReads\nlocalID=1;rejected();localID=0;observer=1;rejected();observer=0\nturn=51;rejected();turn=50;alive=false;rejected();alive=true\nactive=false;rejected();active=true;complete=false;rejected();complete=true\nassert(religionReads==before,'context rejected after religion data read')\nbefore=cityIDReads;owner=1;rejected();owner=0\nassert(cityIDReads==before,'foreign city ID read before ownership guard')\nduplicateCity=true;rejected();duplicateCity=false\nduplicateOwn=true;rejected();duplicateOwn=false\nsparseList=true;rejected();sparseList=false\nextraList=true;rejected();extraList=false\nholy={player=1,type=2,id=65536};rejected()\nholy={player=0,type=2,id=7};rejected()\nholy={player=-1,type=2,id=65536};rejected()\nholy={player=-1,type=1,id=-1};rejected()\nholy={player=0,type=2,id=65536,extra=1};rejected()\nif __XP2_FOUNDED_CITY__ then\n holy={player=0,type=2,id=7}\n CityManager.GetCity=function(descriptor) assert(descriptor==holy);return nil end\n assert(observe()=='religion-observation-v1|0|50|4|0|2|-1|2|-1|1|4|0|2|10|11')\n holy={player=1,type=2,id=7}\n CityManager.GetCity=function(descriptor) assert(descriptor==holy);return {GetName=function() return 'A' end} end\n Locale.Lookup=function(key,name) assert(key=='LOC_UI_RELIGION_HOLY_CITY');return name end\n Locale.ToUpper=function(label) return label end\n assert(observe()=='religion-observation-v2|0|50|4|0|2|-1|2|-1|1|4|0|2|10|11|41')\nend\nholy={player=0,type=2,id=65536}\nbeliefs[2]=10;rejected();beliefs[2]=11\nbeliefs[2]=nil;beliefs[3]=12;rejected();beliefs[2]=11;beliefs[3]=nil\nbeliefs[2]=-1;rejected();beliefs[2]=11\nlocal old=own.Religion;own.Religion=5;rejected();own.Religion=old\nfoundingUnit=1;rejected();foundingUnit=false\nearned=-1;rejected();earned=2\ncontextMutation=true;rejected();contextMutation=false;observer=0\ncreatedReads=0;mutateCreated=true;rejected();mutateCreated=false\nforeignOnly=true;rejected()\ncreated=-1;foundingUnit=true;earned=0;holy={player=-1,type=2,id=-1}\nassert(observe()=='religion-observation-v1|0|50|-1|1|0|-1|2|-1|0|-1|-1|0')\n-- Activation-like state remains a raw observation, not a founded religion.\nearned=2;foundingUnit=false;holy={player=0,type=2,id=65536}\nassert(observe()=='religion-observation-v1|0|50|-1|0|2|0|2|65536|0|-1|-1|0')\nassert(foreignReads==0)\nreturn 'native-religion-observation-guards-ok'\n").replace('__XP2_FOUNDED_CITY__', 'true' if core_sha256 == XP2_CORE_SHA256 else 'false').encode('ascii')

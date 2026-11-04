"""Bounded own-player religion readback, with no action or success inference.

Execute build_source() only through the existing protected Lua evaluator after
native cache publication. This module neither invokes that evaluator nor submits
an operation. Global religion rows are projected to the acting player's row.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_religion_observation.py')))).resolve().parents[1]
PROOF_SHA256 = 'c5f6dd96698059bf7fc4b8c4bf765d4876857f1963d1772657c67866f32609e0'
MAX_CITIES = 256
MAX_RELIGIONS = 4096
MAX_BELIEFS = 4096
MAX_RESPONSE = 65536
_PREFIX = b'religion-observation-v1'

def verify_source():
    proof = load_pinned_json(ROOT / 'evidence/native-religion-founding-actions' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    expected = {'PlayerReligion.GetReligionTypeCreated': '0x18053ac00', 'PlayerReligion.HasReligiousFoundingUnit': '0x18053aca0', 'PlayerReligion.GetNumBeliefsEarned': '0x18053ab10', 'PlayerReligion.GetHolyCityID': '0x18053aad0', 'GameReligion.GetReligions': '0x180527680'}
    if proof.get('schema') != 'civ6rl.native_religion_founding_actions.static.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or any((proof.get('bindings', {}).get(name, {}).get('callback_va') != value for name, value in expected.items())) or (proof['getter_contracts']['GameReligion.GetReligions']['native_cache_row_stride'] != 56) or (proof['getter_contracts']['GameReligion.GetReligions']['fields']['Religion']['offset'] != 0) or (proof['getter_contracts']['GameReligion.GetReligions']['fields']['Founder']['offset'] != 4):
        raise RuntimeError('Native religion observation source identity changed')
    return proof

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

def build_source(player_id, expected_turn):
    """Build one protected-call chunk; no getters execute in Python."""
    pid = _uint(player_id, 'player ID', 63)
    turn = _uint(expected_turn, 'expected game turn')
    verify_source()
    return f'local pid,expectedTurn={pid},{turn}\nlocal maxCities,maxReligions,maxBeliefs={MAX_CITIES},{MAX_RELIGIONS},{MAX_BELIEFS}\n'.encode('ascii') + _READ_LUA
_READ_LUA = "\nlocal function integer(value,label,low,high)\n assert(type(value)=='number' and value%1==0 and value>=low and value<=high,\n        'invalid religion observation '..label)\n return value\nend\nlocal function boolean(value,label)\n assert(type(value)=='boolean','invalid religion observation '..label)\n return value\nend\nassert(Game and type(Game.GetLocalPlayer)=='function' and\n type(Game.GetLocalObserver)=='function' and type(Game.GetCurrentGameTurn)=='function',\n 'religion observation context API unavailable')\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn,'foreign or stale religion observation')\nlocal player=Players and Players[pid]\nassert(player and type(player.IsAlive)=='function' and type(player.IsTurnActive)=='function' and\n type(player.IsTurnActiveComplete)=='function','religion observation player unavailable')\nlocal function context()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n  Game.GetCurrentGameTurn()==expectedTurn and Players[pid]==player,\n  'religion observation context changed')\n assert(player:IsAlive()==true and player:IsTurnActive()==true and\n  player:IsTurnActiveComplete()==true,'religion observation player is not ready')\nend\ncontext()\n-- Validate the player's own city collection before obtaining religion state.\nassert(type(player.GetCities)=='function','own city collection API unavailable')\nlocal collection=player:GetCities()\nassert(collection and type(collection.Members)=='function','own city collection unavailable')\nlocal ownCities,cityCount={},0\nfor _,city in collection:Members() do\n cityCount=cityCount+1\n assert(cityCount<=maxCities,'own city collection exceeds observation bound')\n assert(city and type(city.GetOwner)=='function' and type(city.GetID)=='function',\n        'invalid own city object')\n assert(city:GetOwner()==pid,'foreign city in own collection')\n local cityID=integer(city:GetID(),'own city ID',0,2147483647)\n assert(ownCities[cityID]==nil,'duplicate own city ID')\n ownCities[cityID]=city\nend\nlocal function citiesStillOwn()\n for id,city in pairs(ownCities) do\n  assert(city:GetOwner()==pid and city:GetID()==id,'own city identity changed')\n end\nend\nassert(type(player.GetReligion)=='function' and type(Game.GetReligion)=='function',\n 'religion observation getters unavailable')\nlocal religion=player:GetReligion()\nassert(religion and type(religion.GetReligionTypeCreated)=='function' and\n type(religion.HasReligiousFoundingUnit)=='function' and\n type(religion.GetNumBeliefsEarned)=='function' and type(religion.GetHolyCityID)=='function',\n 'player religion observation API unavailable')\nlocal function readHolyCity()\n local descriptor=religion:GetHolyCityID()\n assert(type(descriptor)=='table','GetHolyCityID did not return a descriptor table')\n local count=0\n for key,_ in pairs(descriptor) do\n  assert(key=='player' or key=='type' or key=='id','unexpected holy city descriptor field')\n  count=count+1\n end\n assert(count==3,'incomplete holy city descriptor')\n local owner=integer(descriptor.player,'holy city player',-1,63)\n local kind=integer(descriptor.type,'holy city type',-32768,32767)\n local id=integer(descriptor.id,'holy city ID',-1,2147483647)\n assert(kind==2,'holy city descriptor is not a city')\n if owner==-1 or id==-1 then\n  assert(owner==-1 and id==-1,'partial holy city absence sentinel')\n else\n  assert(owner==pid,'holy city is not owned by the observed player')\n  assert(ownCities[id]~=nil,'holy city is absent from own city collection')\n end\n return owner,kind,id\nend\nlocal created=integer(religion:GetReligionTypeCreated(),'created religion index',-1,2147483647)\nlocal foundingUnit=boolean(religion:HasReligiousFoundingUnit(),'founding-unit presence')\nlocal earned=integer(religion:GetNumBeliefsEarned(),'beliefs earned',0,2147483647)\nlocal holyOwner,holyType,holyID=readHolyCity()\nlocal global=Game.GetReligion()\nassert(global and type(global.GetReligions)=='function','global religion collection unavailable')\nlocal all=global:GetReligions()\nlocal function denseLength(values,label,bound)\n assert(type(values)=='table','invalid '..label..' table')\n local count,highest=0,0\n for key,_ in pairs(values) do\n  integer(key,label..' key',1,bound)\n  count=count+1;assert(count<=bound,label..' exceeds observation bound')\n  if key>highest then highest=key end\n end\n assert(count==highest,'sparse '..label..' table')\n return count\nend\nlocal count=denseLength(all,'religion list',maxReligions)\nlocal own,ownIndex=nil,-1\nfor i=1,count do\n local entry=all[i]\n assert(type(entry)=='table','invalid native religion row')\n -- Do not read Religion, Beliefs, CustomName or any other foreign-row data.\n local founder=integer(entry.Founder,'religion founder',0,63)\n if founder==pid then\n  assert(own==nil,'ambiguous duplicate own religion rows')\n  own=entry\n  ownIndex=integer(entry.Religion,'own religion index',0,2147483647)\n end\nend\nassert((own==nil and created==-1) or (own~=nil and created==ownIndex),\n       'player/global own religion state is inconsistent')\nlocal beliefs,seen={},{ }\nif own~=nil then\n local n=denseLength(own.Beliefs,'own beliefs',maxBeliefs)\n for i=1,n do\n  local value=integer(own.Beliefs[i],'own belief index',0,2147483647)\n  assert(not seen[value],'duplicate own belief index')\n  seen[value]=true;beliefs[i]=value\n end\nend\n-- The output is an observation, never an activation/founding success claim.\nlocal function dec(value) return string.format('%.0f',value) end\nlocal out={'religion-observation-v1',dec(pid),dec(expectedTurn),dec(created),\n foundingUnit and '1' or '0',dec(earned),dec(holyOwner),dec(holyType),dec(holyID),\n own and '1' or '0',dec(ownIndex),own and dec(pid) or '-1',dec(#beliefs)}\nfor i=1,#beliefs do out[#out+1]=dec(beliefs[i]) end\nassert(religion:GetReligionTypeCreated()==created and\n religion:HasReligiousFoundingUnit()==foundingUnit and religion:GetNumBeliefsEarned()==earned,\n 'player religion state changed during observation')\nlocal ownerAgain,typeAgain,idAgain=readHolyCity()\nassert(ownerAgain==holyOwner and typeAgain==holyType and idAgain==holyID,\n 'holy city changed during observation')\ncitiesStillOwn()\ncontext()\nreturn table.concat(out,'|')\n".encode('ascii')

def parse_observation(payload, player_id, expected_turn):
    pid = _uint(player_id, 'player ID', 63)
    turn = _uint(expected_turn, 'expected game turn')
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid religion observation payload')
    tokens = payload.split(b'|')
    if len(tokens) < 13 or tokens[0] != _PREFIX:
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
    if len(tokens) != 13 + count:
        raise ValueError('Religion observation count does not match payload')
    beliefs = [_token(token, 'own belief index') for token in tokens[13:]]
    if len(set(beliefs)) != len(beliefs):
        raise ValueError('Duplicate own belief indices')
    if own_present:
        if created < 0 or own_index != created or own_founder != pid:
            raise ValueError('Inconsistent own founded-religion state')
    elif created != -1 or own_index != -1 or own_founder != -1 or beliefs:
        raise ValueError('Absent own religion contains data')
    return {'player_id': pid, 'current_game_turn': turn, 'religion_type_created': created, 'has_religious_founding_unit': tokens[4] == b'1', 'num_beliefs_earned': earned, 'holy_city': {'player': owner, 'type': kind, 'id': city_id}, 'holy_city_present': city_id >= 0, 'own_religion': {'religion_index': own_index, 'founder': own_founder, 'belief_indices': beliefs} if own_present else None, 'observation_only': True, 'action_effect_verified': False, 'source_proof_sha256': PROOF_SHA256, 'exposed_to_learner': False, 'eligible_for_training': False}

def guard_case():
    """Execute the real chunk against isolated Lua doubles (Lupa or protected HKS)."""
    source = build_source(0, 50).decode('ascii')
    return ("local localID,observer,turn=0,0,50\nlocal alive,active,complete=true,true,true\nlocal owner,cityID=0,65536\nlocal created,foundingUnit,earned=4,false,2\nlocal holy={player=0,type=2,id=65536}\nlocal beliefs={10,11}\nlocal religionReads,cityIDReads,foreignReads=0,0,0\nlocal duplicateCity,duplicateOwn,foreignOnly=false,false,false\nlocal sparseList,extraList,contextMutation=false,false,false\nlocal createdReads,mutateCreated=0,false\nlocal foreign=setmetatable({Founder=1},{__index=function(_,key)\n foreignReads=foreignReads+1;error('foreign religion field read: '..tostring(key)) end})\nlocal own={Founder=0,Religion=4,Beliefs=beliefs}\nlocal city={GetOwner=function() return owner end,\n GetID=function() cityIDReads=cityIDReads+1;return cityID end}\nlocal religion={\n GetReligionTypeCreated=function()\n  createdReads=createdReads+1\n  if mutateCreated and createdReads%2==0 then return created+1 end\n  return created end,\n HasReligiousFoundingUnit=function() return foundingUnit end,\n GetNumBeliefsEarned=function() return earned end,\n GetHolyCityID=function() return holy end}\nlocal player={IsAlive=function() return alive end,IsTurnActive=function() return active end,\n IsTurnActiveComplete=function() return complete end,\n GetCities=function() return {Members=function()\n  local n=0;return function()\n   n=n+1;if n==1 or (duplicateCity and n==2) then return n,city end\n  end end} end,\n GetReligion=function() religionReads=religionReads+1;return religion end}\nlocal Players={[0]=player}\nlocal Game={GetLocalPlayer=function() return localID end,\n GetLocalObserver=function() return observer end,GetCurrentGameTurn=function() return turn end,\n GetReligion=function() return {GetReligions=function()\n  if contextMutation then observer=1 end\n  if sparseList then return {[1]=foreign,[3]=own} end\n  if extraList then return {[1]=foreign,[2]=own,x=own} end\n  if duplicateOwn then return {foreign,own,own} end\n  if foreignOnly then return {foreign} end\n  return {foreign,own}\n end} end}\nlocal function forbidden() error('readback attempted an action or hidden plot query') end\nlocal UnitManager={RequestOperation=forbidden,CanStartOperation=forbidden}\nlocal UI={RequestPlayerOperation=forbidden}\nlocal Map={GetPlotByIndex=forbidden,GetPlot=forbidden}\nlocal function observe()\n" + source + "\nend\nlocal function rejected() local ok=pcall(observe);assert(not ok,'invalid religion observation accepted') end\nlocal result=observe()\nassert(result=='religion-observation-v1|0|50|4|0|2|0|2|65536|1|4|0|2|10|11')\nassert(foreignReads==0,'foreign religion data was accessed')\nlocal before=religionReads\nlocalID=1;rejected();localID=0;observer=1;rejected();observer=0\nturn=51;rejected();turn=50;alive=false;rejected();alive=true\nactive=false;rejected();active=true;complete=false;rejected();complete=true\nassert(religionReads==before,'context rejected after religion data read')\nbefore=cityIDReads;owner=1;rejected();owner=0\nassert(cityIDReads==before,'foreign city ID read before ownership guard')\nduplicateCity=true;rejected();duplicateCity=false\nduplicateOwn=true;rejected();duplicateOwn=false\nsparseList=true;rejected();sparseList=false\nextraList=true;rejected();extraList=false\nholy={player=1,type=2,id=65536};rejected()\nholy={player=0,type=2,id=7};rejected()\nholy={player=-1,type=2,id=65536};rejected()\nholy={player=-1,type=1,id=-1};rejected()\nholy={player=0,type=2,id=65536,extra=1};rejected()\nholy={player=0,type=2,id=65536}\nbeliefs[2]=10;rejected();beliefs[2]=11\nbeliefs[2]=nil;beliefs[3]=12;rejected();beliefs[2]=11;beliefs[3]=nil\nbeliefs[2]=-1;rejected();beliefs[2]=11\nlocal old=own.Religion;own.Religion=5;rejected();own.Religion=old\nfoundingUnit=1;rejected();foundingUnit=false\nearned=-1;rejected();earned=2\ncontextMutation=true;rejected();contextMutation=false;observer=0\ncreatedReads=0;mutateCreated=true;rejected();mutateCreated=false\nforeignOnly=true;rejected()\ncreated=-1;foundingUnit=true;earned=0;holy={player=-1,type=2,id=-1}\nassert(observe()=='religion-observation-v1|0|50|-1|1|0|-1|2|-1|0|-1|-1|0')\n-- Activation-like state remains a raw observation, not a founded religion.\nearned=2;foundingUnit=false;holy={player=0,type=2,id=65536}\nassert(observe()=='religion-observation-v1|0|50|-1|0|2|0|2|65536|0|-1|-1|0')\nassert(foreignReads==0)\nreturn 'native-religion-observation-guards-ok'\n").encode('ascii')

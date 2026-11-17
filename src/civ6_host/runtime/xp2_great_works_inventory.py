"""Own Great Work slots from the installed expansion's official overview."""

from hashlib import sha256
from pathlib import Path
import re

from civ6_host.contracts import city_buildings
from .configuration_profiles import _source
from .execution_images import _PROFILE, _XP1_PROFILE
from .placement_inventory import _OWN_CITY_LUA, _inputs
from .resource_resolution import resolve_path


_BASE_OVERVIEW = ('Base/Assets/UI/GreatWorksOverview.lua',
                  '0782a00ffbad0e39a5aa4a5c10997156ad7347ff788b3f345267b61d02c9f8c5')
_XP2_OVERLAY = ('DLC/Expansion2/UI/Replacements/GreatWorksOverview_Expansion2.lua',
                '620cf37c7283408acb02da6e76daa2b5a1673ea698e39362c279f65044919024')
_CAPABILITIES = ('Base/Assets/UI/Scripts/GameCapabilities.lua',
                 '0e81de39aa32033e4b3ed0660e72f6ca63f3f3bec28ec35d3b61ef780f1ceb0c')
_LAUNCHBAR = ('Base/Assets/UI/LaunchBar.lua',
              'f61262cfc927a5b156f5eb7c0aaa1e8750f2c545db59f2ac7ec7bf8f22d8d0cf')
_FILES = (_BASE_OVERVIEW, _XP2_OVERLAY, _CAPABILITIES, _LAUNCHBAR)
_XP1_FILES = (_BASE_OVERVIEW, _CAPABILITIES, _LAUNCHBAR,
    ('DLC/Expansion1/Expansion1.modinfo', 'ed8e3ef9276d694f91e76fe8237361b457a0a6ee653cd506ca8dc4089e56db7d'),
    ('DLC/Expansion1/UI/Replacements/LaunchBar_Expansion1.lua',
     '2644d1babecdd6d322a016a32f624e4ced482205edb817383bc6be91c25eea1f'))
VIEW_CAPABILITY = 'CAPABILITY_GREAT_WORKS_VIEW'
_MAX_BYTES = 4 * 1024**2
THEME_SOURCE = ('evidence/host-xp2-great-work-theming-binding-source.json',
                'fdadf42d7de52456ed9554656ced4bdb4e27dfcdfb015f8d53095a77b2c29783')
XP1_OVERVIEW_SOURCE = ('evidence/host-xp1-great-work-overview-binding-source.json',
                       'e9a4a3556d9c5b39f2efa054449f972f6c15f73a160ce785b7731a8ba908c189')
_THEME_BINDINGS = frozenset(('GetCreatorNameFromIndex', 'IsBuildingThemedCorrectly',
    'GetBuildingYieldFromGreatWorks', 'GetBuildingTourismFromGreatWorks', 'GetGreatWorkPlayer',
    'GetAutoThemedBuilding', 'IsAutoThemedEligible'))
_XP1_VIEW_BINDINGS = (_THEME_BINDINGS - {'IsAutoThemedEligible'}) | {
    'GetNumGreatWorkSlots', 'GetGreatWorkInSlot', 'GetGreatWorkSlotType',
    'GetGreatWorkTypeFromIndex', 'GetTurnFromIndex'}


def _ui_files(image):
    if image is _XP1_PROFILE:
        return _XP1_FILES
    if image is _PROFILE:
        return _FILES
    raise ValueError('Unknown expansion Great Work overview image')


def dependencies(image):
    game = Path(image.path).parents[4]
    return {str(resolve_path(game / relative).resolve(strict=True)): digest
            for relative, digest in _ui_files(image)}


def theming_spans(image):
    ui_files = _ui_files(image)
    if image is _XP1_PROFILE:
        proof = _source(XP1_OVERVIEW_SOURCE)
        schema = 'civ6-host.xp1-great-work-overview-bindings.source.v1'
        bindings = _XP1_VIEW_BINDINGS
    else:
        proof = _source(THEME_SOURCE)
        schema = 'civ6-host.xp2-great-work-theming-bindings.source.v1'
        bindings = _THEME_BINDINGS
    if (proof['schema'] != schema
            or (proof['image_id'], proof['image_sha256']) != (image.id, image.image_sha256)
            or dict(proof['ui_files']) != dict(ui_files) or proof['bindings'].keys() != bindings):
        raise ValueError('Great Work theme bindings differ from the selected overview and engine')
    return tuple(span for binding in proof['bindings'].values() for span in binding.values())


def verify_theming_bindings(image, base, read):
    for item in theming_spans(image):
        data = read(base + item['rva'], item['size'])
        if (type(data) is not bytes or len(data) != item['size']
                or sha256(data).hexdigest() != item['sha256']):
            raise ValueError('Live Great Work theme binding differs at ' + hex(item['rva']))


def rules(image):
    paths = dependencies(image)
    sources = {}
    for (relative, _), (path, digest) in zip(_ui_files(image), paths.items(), strict=True):
        data = Path(path).read_bytes()
        if sha256(data).hexdigest() != digest:
            raise ValueError('Selected Great Works overview source changed')
        sources[relative] = data
    base, capabilities, launchbar = (sources[role[0]] for role in (_BASE_OVERVIEW, _CAPABILITIES, _LAUNCHBAR))
    expansion = sources.get(_XP2_OVERLAY[0])
    token = VIEW_CAPABILITY.encode('ascii')
    if (b'HasCapability("' + token + b'")' not in base
            or b'm_isGreatWorksUnlocked and HasCapability("' + token + b'")' not in launchbar):
        raise ValueError('Great Work view capability source differs')
    capability = re.search(rb'(?ms)^function HasCapability\([^)]*\).*?^end(?=\r?$)', capabilities)
    if capability is None:
        raise ValueError('Great Work capability predicate unavailable')
    names = (b'IsBuildingFull|CanMoveWorkAtAll|CanMoveGreatWork|GetFirstGreatWorkInBuilding|'
             b'GetGreatWorksInBuilding|IsFirstGreatWorkByArtist|GreatWorkFitsTheme')
    if expansion is not None and re.search(rb'(?m)^function (' + names + rb')\(', expansion):
        raise ValueError('Unexpected Gathering Storm Great Work helper override')
    constants = re.findall(rb'(?m)^local (?:DEFAULT_LOCK_TURNS|GREAT_WORK_ARTIFACT_TYPE):[^\r\n]+', base)
    if len(constants) != 2:
        raise ValueError('Great Work movement constants unavailable')
    theme_scope = b'local xp2Theme=true' if expansion is not None else b'local xp2Theme=false\nlocal m_LocalPlayer=player'
    pieces = [theme_scope, b'local ' + capability.group(), *constants]
    helpers = [(name, base) for name in names.split(b'|')] + [(b'GetThemeDescription', expansion or base)]
    for name, source in helpers:
        match = re.search(rb'(?ms)^function ' + name + rb'\([^)]*\).*?^end(?=\r?$)', source)
        if match is None:
            raise ValueError('Great Work overview helper unavailable')
        pieces.append(b'local ' + match.group())
    return re.sub(rb'(\w+)\s*:\s*(number|string|table)(?=\s*[,)=])', rb'\1',
                  b'\n'.join(pieces)) + b'\n'


_SLOTS = r'''
local output={'great-work-slots-v3|'..n(pid)..'|'..n(expectedTurn)}
assert(GameInfo and GameInfo.GameCapabilities,'Great Work capabilities unavailable')
if not HasCapability(viewCapability) then return output[1] end
local slots={}
local bonusRows={}
local function signed(v)
 assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,
        'Great Work output differs from native integer')
 return v
end
local function buildingBonus(cid,idx,buildings,first)
 local definition=GameInfo.Buildings[idx]
 assert(definition and definition.Index==idx,'Great Work building definition changed')
 local filled=0
 for i=first,#slots do if slots[i].work~=-1 then filled=filled+1 end end
 local total=#slots-first+1
 local description=GetThemeDescription(definition.BuildingType)
 local themed=filled>0 and buildings:IsBuildingThemedCorrectly(idx)
 assert(type(themed)=='boolean','Native Great Work theme state unavailable')
 local state,matching='none',-1
 if themed then
  state='themed'
 elseif description~=nil and (filled==0 or total>1) then
  state='progress'
  matching=filled
  if filled>0 and (not xp2Theme or player:GetCulture():IsAutoThemedEligible()~=true) then
   matching=0
   for i=first,#slots do
    local row=slots[i]
    if row.work~=-1 and GreatWorkFitsTheme(buildings,definition,row.work,row.definition) then
     matching=matching+1
    end
   end
  end
 end
 local yields={}
 for row in GameInfo.Yields() do
  local amount=signed(buildings:GetBuildingYieldFromGreatWorks(row.Index,idx))
  if amount>0 then
   assert(#yields<256,'Great Work yield count exceeds its bound')
   yields[#yields+1]=row.YieldType..':'..n(amount)
  end
 end
 table.sort(yields)
 local tourism=signed(buildings:GetBuildingTourismFromGreatWorks(false,idx))+
               signed(buildings:GetBuildingTourismFromGreatWorks(true,idx))
 return 'B|'..table.concat({n(cid),n(idx),state,n(matching),n(total),
                            n(math.max(tourism,0)),table.concat(yields,',')},'|')
end
for _,pair in ipairs(buildingPairs) do
 local cid,idx=pair[1],pair[2]
 local city=ownCities[cid]
 assert(ownCityIdentity(city)==cid,'Great Work city changed')
 local buildings=city:GetBuildings()
 assert(buildings:HasBuilding(idx)==true,'Great Work building changed')
 local count=buildings:GetNumGreatWorkSlots(idx)
 if count~=nil then
  local first=#slots+1
  uint(count,'Great Work slot count',maxRows)
  for slot=0,count-1 do
   local slotIndex=nativeIndex(buildings:GetGreatWorkSlotType(idx,slot),'Great Work slot type')
   if slotIndex<0 then break end
   local row=GameInfo.GreatWorkSlotTypes[slotIndex]
   assert(row and type(row.GreatWorkSlotType)=='string','Great Work slot definition missing')
   local work=nativeIndex(buildings:GetGreatWorkInSlot(idx,slot),'Great Work instance')
   local fields={n(cid),n(idx),n(slot),row.GreatWorkSlotType,n(work)}
   local unlocked=false
   local definition=nil
   if work~=-1 then
    definition=GameInfo.GreatWorks[buildings:GetGreatWorkTypeFromIndex(work)]
    assert(definition and type(definition.GreatWorkType)=='string'
      and type(definition.GreatWorkObjectType)=='string','Great Work definition missing')
    unlocked=CanMoveWorkAtAll(buildings,idx,slot)
    assert(type(unlocked)=='boolean','Great Work movement state missing')
    fields[6]=definition.GreatWorkType
    fields[7]=definition.GreatWorkObjectType
    fields[8]=unlocked and '1' or '0'
   end
   assert(#output<=maxRows,'Great Work inventory exceeds its bound')
   output[#output+1]='S|'..table.concat(fields,'|')
   slots[#slots+1]={address=table.concat(fields,'|',1,3),index=idx,slot=slot,
                   buildings=buildings,work=work,unlocked=unlocked,definition=definition}
  end
  if #slots>=first then bonusRows[#bonusRows+1]=buildingBonus(cid,idx,buildings,first) end
 end
end
for _,row in ipairs(bonusRows) do output[#output+1]=row end
local moves=0
for _,source in ipairs(slots) do
 if source.unlocked then
  for _,target in ipairs(slots) do
   if source~=target and (target.work==-1 or target.unlocked)
      and CanMoveGreatWork(source.buildings,source.index,source.slot,
                           target.buildings,target.index,target.slot) then
    moves=moves+1
    assert(moves<=maxRows,'Great Work move targets exceed their bound')
    output[#output+1]='M|'..source.address..'|'..target.address
   end
  end
 end
end
ready()
return table.concat(output,'\n')
'''


def read(prefix, observation, buildings, movement_rules):
    pid, turn = observation['player_id'], observation['turn']
    city_buildings.validate(buildings, pid, turn, observation=observation)
    if buildings['schema'] != city_buildings.SCHEMA:
        raise ValueError('Great Work reader requires the original city building projection')
    width, height, _, city_ids = _inputs(pid, turn, observation)
    completed = sorted({(row['city_id'],row['index']) for row in buildings['rows'] if row['complete']})
    pairs = ','.join('{%d,%d}' % pair for pair in completed)
    header = (f'local pid,expectedTurn,width,height={pid},{turn},{width},{height}\n'
              f'local cityIDs={{{",".join(map(str,city_ids))}}}\nlocal buildingPairs={{{pairs}}}\n'
              f'local maxRows={city_buildings.MAX_ROWS}\nlocal viewCapability="{VIEW_CAPABILITY}"\n')
    code = (header + _OWN_CITY_LUA).encode('ascii') + movement_rules + _SLOTS.encode('ascii')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, code, b'@xp2_public_great_work_slots',
                                       capacity=_MAX_BYTES + 1)
    if type(raw) is not bytes or len(raw) > _MAX_BYTES:
        raise ValueError('Unbounded Great Work readback')
    head, *lines = raw.decode('ascii').split('\n')
    if head != f'great-work-slots-v3|{pid}|{turn}' or len(lines) > 3 * city_buildings.MAX_ROWS:
        raise ValueError('Foreign or unbounded Great Work readback')
    slots = []
    bonuses = []
    targets = []
    for line in lines:
        kind, *fields = line.split('|')
        if kind == 'M' and len(fields) == 6:
            targets.append(dict(source=_address(fields[:3]), destination=_address(fields[3:])))
            continue
        if kind == 'B' and len(fields) == 7 and not targets:
            bonuses.append(_bonus(fields))
            continue
        if kind != 'S' or len(fields) < 5 or bonuses or targets:
            raise ValueError('Malformed Great Work readback order or row type')
        address = _address(fields[:3])
        slot_type, work_index, *work_data = fields[3:]
        work = None
        if work_index != '-1' or work_data:
            if (re.fullmatch(r'[0-9]{1,10}', work_index) is None or len(work_data) != 3
                    or work_data[2] not in ('0','1')):
                raise ValueError('Malformed Great Work instance readback')
            work = dict(index=int(work_index), type=work_data[0], object_type=work_data[1],
                        move_unlocked=work_data[2]=='1')
        slots.append(dict(address, slot_type=slot_type, work=work))
    return city_buildings.validate(dict(buildings, schema=city_buildings.GREAT_WORK_OVERVIEW_SCHEMA,
        great_work_slots=slots, great_work_move_targets=targets, great_work_moves_available=False,
        great_work_building_bonuses=bonuses), pid, turn, observation=observation)


def _address(fields):
    if len(fields) != 3 or any(re.fullmatch(r'[0-9]{1,10}', field) is None for field in fields):
        raise ValueError('Malformed Great Work slot identity')
    city, index, slot = map(int, fields)
    return dict(city_id=city, building_index=index, slot=slot)


def _bonus(fields):
    city, building, state, matching, count, tourism, raw_yields = fields
    if any(re.fullmatch(r'[0-9]{1,10}', field) is None for field in (city, building, count, tourism)):
        raise ValueError('Malformed Great Work building bonus')
    if state == 'progress' and re.fullmatch(r'[0-9]{1,10}', matching):
        theme = dict(state=state, matching=int(matching), slots=int(count))
    elif state in ('none', 'themed') and matching == '-1':
        theme = None if state == 'none' else dict(state=state)
    else:
        raise ValueError('Malformed Great Work theming row')
    yields = {}
    for encoded in raw_yields.split(',') if raw_yields else ():
        key, sep, amount = encoded.partition(':')
        if not sep or key in yields or re.fullmatch(r'[0-9]{1,10}', amount) is None:
            raise ValueError('Malformed Great Work yield row')
        yields[key] = int(amount)
    return dict(city_id=int(city), building_index=int(building), theme=theme, yields=yields, tourism=int(tourism))

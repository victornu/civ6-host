"""Bounded numerical projection of the selected official governor panels.

The caller supplies the verified, unmodified GovernorSupport module. GameCore
answers the getters; this module contains no title, promotion or establishment
formula. Its wire codec is independent of the native owner and DLL calls.
"""
from civ6_host.contracts import governors as contract

MAX_PAYLOAD = 1024 * 1024


def _context(player_id, turn):
    if (type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or not 0 <= turn <= 0x7fffffff):
        raise ValueError('Invalid governor query perspective')


def catalogue_source(player_id, turn, support_source):
    _context(player_id, turn)
    if type(support_source) is not bytes or not 0 < len(support_source) <= MAX_PAYLOAD:
        raise ValueError('Verified official GovernorSupport source is required')
    # The installed module declares functions; it does not initialize Controls
    # or register UI events. Preserve its source, including Firaxis annotations.
    prefix = support_source.removeprefix(b'\xef\xbb\xbf') + b'\n'
    context = f'local pid={player_id}; local expectedTurn={turn}\n'.encode('ascii')
    return prefix + context + _QUERY


_QUERY = b"""
local function context()
 assert(Game.GetLocalPlayer()==pid,'foreign governor perspective')
 assert(Game.GetLocalObserver()==pid,'foreign governor observer')
 assert(Game.GetCurrentGameTurn()==expectedTurn,'stale governor turn')
end
local function number(v,lo,hi)
 assert(type(v)=='number' and v==math.floor(v) and v>=lo and v<=hi,
        'governor integer outside its wire ABI')
 return string.format('%.0f',v)
end
local function i(v) return number(v,-2147483648,2147483647) end
local function u(v)
 number(v,-2147483648,4294967295)
 return number(v<0 and v+4294967296 or v,0,4294967295)
end
local function b(v)
 assert(type(v)=='boolean','governor getter did not return boolean')
 return v and '1' or '0'
end
context()
local player=assert(Players[pid],'governor player unavailable')
local manager=assert(player:GetGovernors(),'governor manager unavailable')
local points,spent=manager:GetGovernorPoints(),manager:GetGovernorPointsSpent()
local appoint,considered=manager:CanAppoint(),manager:HasTitleBeenConsidered()
local lines={table.concat({'H',i(pid),i(expectedTurn),i(points),i(spent),b(appoint),b(considered)},'|')}
local definitions={}
for definition in GameInfo.Governors() do definitions[#definitions+1]=definition end
table.sort(definitions,function(a,c) return a.Index<c.Index end)
local count=0
for _,definition in ipairs(definitions) do
 local governor=GetAppointedGovernor(pid,definition.Index)
 local canEver=manager:CanEverAppointGovernor(definition.Hash)
 if governor~=nil or canEver then
  count=count+1
  local cannotAssign=IsCannotAssign(definition)
  local hasGovernor=manager:HasGovernor(definition.Hash)
  assert(hasGovernor==(governor~=nil),'governor roster and HasGovernor disagree')
  local neutralized=governor and governor:GetNeutralizedTurns() or nil
  local assignmentOpen=governor~=nil and not cannotAssign and neutralized==0
  lines[#lines+1]=table.concat({'G',i(definition.Index),u(definition.Hash),b(governor~=nil),
   b(canEver),b(manager:CanPromoteGovernor(definition.Hash)),b(assignmentOpen),
   i(manager:GetTurnsToEstablish(definition.Hash))},'|')
  local assignedCity=nil
  if governor then
   assert(governor:GetType()==definition.Index,'governor definition/instance mismatch')
   assignedCity=governor:GetAssignedCity()
   lines[#lines+1]=table.concat({'S',i(definition.Index),i(neutralized),b(governor:IsEstablished()),
    i(governor:GetTurnsToEstablish()),i(governor:GetTurnsOnSite()),
    assignedCity and i(assignedCity:GetOwner()) or '~',
    assignedCity and i(assignedCity:GetID()) or '~',
    b(governor:IsGovernCityState()),b(governor:CanAssignToMajorCiv())},'|')
  end
  local promotions={}
  for promotionSet in GameInfo.GovernorPromotionSets() do
   if promotionSet.GovernorType==definition.GovernorType then
    promotions[#promotions+1]=assert(GameInfo.GovernorPromotions[promotionSet.GovernorPromotion],
                                   'governor promotion definition unavailable')
   end
  end
  table.sort(promotions,function(a,c) return a.Index<c.Index end)
  for _,promotion in ipairs(promotions) do
   local owned=governor~=nil and governor:HasPromotion(promotion.Hash)
   lines[#lines+1]=table.concat({'P',i(definition.Index),i(promotion.Index),u(promotion.Hash),
    b(owned),b(manager:CanEarnPromotion(definition.Hash,promotion.Hash)),
    b(IsPromotionHidden(promotion.Hash,pid,definition.Index)),
    b(promotion.BaseAbility),i(promotion.Level)},'|')
  end
  if assignmentOpen then
   local seen={}
   local function target(city,canAssign)
    local owner,id=city:GetOwner(),city:GetID()
    -- The chooser omits the selected governor's current destination. Repeated
    -- appearances of the same city in the own/major lists are the same command.
    if assignedCity and assignedCity:GetOwner()==owner and assignedCity:GetID()==id then return end
    local key=i(owner)..':'..i(id)
    if seen[key]~=nil then return end
    seen[key]=canAssign
    lines[#lines+1]=table.concat({'T',i(definition.Index),i(owner),i(id),b(canAssign)},'|')
   end
   -- Own-city rows are enabled by AddCityInstance(city) without a predicate.
   -- The actual player operation still runs native CanStart before requesting.
   for _,city in player:GetCities():Members() do target(city,true) end
   local diplomacy=assert(player:GetDiplomacy(),'governor diplomacy unavailable')
   if governor:IsGovernCityState() then
    for _,minor in ipairs(PlayerManager.GetAliveMinors()) do
     local influence=minor:GetInfluence()
     if influence~=nil and influence:CanReceiveInfluence() and diplomacy:HasMet(minor:GetID()) then
      for _,city in minor:GetCities():Members() do
       target(city,manager:CanAssignGovernor(definition.Hash,city,true))
      end
     end
    end
   end
   if governor:CanAssignToMajorCiv() then
    for _,major in ipairs(PlayerManager.GetAliveMajors()) do
     if diplomacy:HasMet(major:GetID()) then
      local capital=major:GetCities():GetCapitalCity()
      if capital then target(capital,manager:CanAssignGovernor(definition.Hash,capital,true)) end
     end
    end
   end
  end
 end
end
context()
assert(manager:GetGovernorPoints()==points and manager:GetGovernorPointsSpent()==spent
 and manager:CanAppoint()==appoint and manager:HasTitleBeenConsidered()==considered,
 'governor state changed during query')
lines[#lines+1]=table.concat({'E',i(count),i(#lines)},'|')
local result=table.concat(lines,'\\n')
assert(#result<=1048576,'governor catalogue exceeds the admitted wire size')
return result
"""


def _number(value, minimum=-0x80000000, maximum=0x7fffffff):
    if not value or not value.isascii():
        raise ValueError('Malformed governor integer')
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError('Malformed governor integer') from exc
    if str(parsed) != value or not minimum <= parsed <= maximum:
        raise ValueError('Noncanonical or out-of-range governor integer')
    return parsed


def _flag(value):
    return bool(_number(value, 0, 1))


def parse_catalogue(payload, player_id, turn):
    """Decode the bounded getter projection; never infer missing rows as zero."""
    _context(player_id, turn)
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_PAYLOAD:
        raise ValueError('Unbounded governor catalogue')
    try:
        lines = payload.decode('ascii').split('\n')
    except UnicodeDecodeError as exc:
        raise ValueError('Non-ASCII governor catalogue') from exc
    head, end = lines[0].split('|'), lines[-1].split('|')
    if (len(head) != 7 or head[0] != 'H' or len(end) != 3 or end[0] != 'E'
            or _number(head[1], 0, 63) != player_id
            or _number(head[2], 0) != turn
            or _number(end[2], 1) != len(lines) - 1):
        raise ValueError('Foreign, stale or incomplete governor catalogue')
    result = dict(player_id=player_id, current_game_turn=turn,
                  points_obtained=_number(head[3]), points_spent=_number(head[4]),
                  can_appoint=_flag(head[5]), titles_considered=_flag(head[6]), governors=[])
    by_index = {}
    for line in lines[1:-1]:
        cells = line.split('|')
        if len(cells) < 2:
            raise ValueError('Malformed governor record')
        kind, index = cells[0], _number(cells[1], 0)
        if kind == 'G' and len(cells) == 8:
            if index in by_index:
                raise ValueError('Duplicate governor record')
            row = dict(index=index, hash=_number(cells[2], 0, 0xffffffff),
                       appointed=_flag(cells[3]), can_ever_appoint=_flag(cells[4]),
                       can_promote=_flag(cells[5]), assignment_open=_flag(cells[6]),
                       turns_to_establish=_number(cells[7]), status=None,
                       promotions=[], assignment_targets=[])
            result['governors'].append(row)
            by_index[index] = row
        elif index not in by_index:
            raise ValueError('Governor detail precedes its definition')
        elif kind == 'S' and len(cells) == 10:
            row = by_index[index]
            if row['status'] is not None:
                raise ValueError('Duplicate governor status')
            owner, city = cells[6:8]
            if (owner == '~') != (city == '~'):
                raise ValueError('Partial assigned-city identity')
            assigned = (None if owner == '~' else
                        dict(owner=_number(owner, 0, 63), city_id=_number(city, 0)))
            row['status'] = dict(neutralized_turns=_number(cells[2]), established=_flag(cells[3]),
                                 turns_to_establish=_number(cells[4]), turns_on_site=_number(cells[5]),
                                 assigned_city=assigned, govern_city_state=_flag(cells[8]),
                                 can_assign_to_major_civ=_flag(cells[9]))
        elif kind == 'P' and len(cells) == 9:
            by_index[index]['promotions'].append(dict(index=_number(cells[2], 0),
                hash=_number(cells[3], 0, 0xffffffff), owned=_flag(cells[4]),
                can_earn=_flag(cells[5]), hidden=_flag(cells[6]),
                base_ability=_flag(cells[7]), level=_number(cells[8])))
        elif kind == 'T' and len(cells) == 5:
            by_index[index]['assignment_targets'].append(dict(owner=_number(cells[2], 0, 63),
                city_id=_number(cells[3], 0), can_assign=_flag(cells[4])))
        else:
            raise ValueError('Unknown or malformed governor record')
    if _number(end[1], 0) != len(result['governors']):
        raise ValueError('Governor catalogue count differs')
    return contract.validate_catalogue(result, player_id, turn)


def consideration_source(player_id, turn):
    _context(player_id, turn)
    return (f"assert(Game.GetLocalPlayer()=={player_id} and Game.GetLocalObserver()=={player_id} "
            f"and Game.GetCurrentGameTurn()=={turn},"
            "'foreign governor title consideration'); "
            f"local governors=assert(Players[{player_id}]:GetGovernors()); "
            "assert(not governors:HasTitleBeenConsidered(),'governor titles already considered'); "
            "governors:SetTitleConsidered(true); "
            "assert(governors:HasTitleBeenConsidered(),'governor title consideration failed'); "
            "return 'considered'\n").encode('ascii')

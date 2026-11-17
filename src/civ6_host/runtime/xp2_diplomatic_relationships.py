"""Read the selected XP2 diplomacy panel for met AI civilizations."""
from hashlib import sha256
import json
from pathlib import Path

from civ6_host.contracts import diplomacy_overview
from civ6_host.player_view import MAX_PLAYERS, validate_diplomatic_wars
from .resource_resolution import resolve_path


ALLIANCE_ROW_SHA256 = '34990895aecfa4330b026939fc214b8f041caa231ecdc0f69ee9b8b86e4772aa'


def source_dependencies(xp2_view_path):
    # Expansion2 includes the Expansion1 view, whose alliance row is replaced
    # by the selected Expansion2 UI file.
    path = resolve_path(Path(xp2_view_path).parent.parent / 'Additions/DiplomacyActionView_AllianceRow.lua')
    if sha256(path.read_bytes()).hexdigest() != ALLIANCE_ROW_SHA256:
        raise ValueError('Gathering Storm relationship panel source changed')
    return {str(path.resolve()): ALLIANCE_ROW_SHA256}


_READ_PANEL = r'''
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'Diplomatic relationship reader crossed its player or turn')
local actor=Players[pid]
local diplomacy=actor:GetDiplomacy()
local rows={}
local function integer(value)
 assert(type(value)=='number' and value%1==0 and value>=-2147483648 and value<2147483648,
  'Invalid public diplomatic integer')
 return tostring(value)
end
for _,targetID in ipairs(targets) do
 local target=Players[targetID]
 assert(target and target:GetID()==targetID and target:IsMajor() and diplomacy:HasMet(targetID),
  'Diplomatic relationship requires a met major')
 local human=target:IsHuman()
 assert(type(human)=='boolean','Missing player controller type for diplomacy')
 local relationship='null'
 if not human then
  local stateIndex=target:GetDiplomaticAI():GetDiplomaticStateIndex(pid)
  local state=GameInfo.DiplomaticStates[stateIndex].StateType
  assert(type(state)=='string' and state:match('^DIPLO_STATE_[A-Z0-9_]+$'),
   'Unrecognized public diplomatic state key')
  local grievances=diplomacy:GetGrievancesAgainst(targetID)
  local expiration='null'
  local kind,remaining,denouncer
  local alliance=diplomacy:GetAllianceType(targetID)
  if alliance~=-1 then
   kind='alliance'
   remaining=diplomacy:GetAllianceTurnsUntilExpiration(targetID)
  elseif state=='DIPLO_STATE_DENOUNCED' then
   local ours=diplomacy:GetDenounceTurn(targetID)
   local theirs=target:GetDiplomacy():GetDenounceTurn(pid)
   -- The selected alliance row breaks the timer tie by turn order and the
   -- displayed speaker tie by the local player's direction.
   local orderAdjustment=0
   if (theirs>=ours and targetID>pid) or (theirs<ours and pid>targetID) then
    orderAdjustment=1
   end
   denouncer=ours>=theirs and pid or targetID
   kind='denunciation'
   remaining=1+math.max(ours,theirs)+Game.GetGameDiplomacy():GetDenounceTimeLimit()-turn+orderAdjustment
  elseif state=='DIPLO_STATE_DECLARED_FRIEND' then
   kind='friendship'
   remaining=diplomacy:GetDeclaredFriendshipTurn(targetID)+Game.GetGameDiplomacy():GetDenounceTimeLimit()-turn
  end
  if kind then
   expiration='{"kind":"'..kind..'","turns_remaining":'..integer(remaining)..
    ',"denouncer_player_id":'..(denouncer==nil and 'null' or integer(denouncer))..'}'
  end
  relationship='{"state":"'..state..'","grievances":'..integer(grievances)..',"expiration":'..expiration..'}'
 end
 rows[#rows+1]='{"player_id":'..integer(targetID)..',"relationship":'..relationship..'}'
end
return '['..table.concat(rows,',')..']'
'''.encode('ascii')


def _source(overview):
    pid, turn = overview['player_id'], overview['turn']
    diplomacy_overview.validate(overview, pid, turn)
    ids = ','.join(str(row['player_id']) for row in overview['targets'])
    return f'local pid,turn,targets={pid},{turn},{{{ids}}}\n'.encode('ascii') + _READ_PANEL


def parse(overview, raw):
    pid, turn = overview['player_id'], overview['turn']
    diplomacy_overview.validate(overview, pid, turn)
    if overview['schema'] != diplomacy_overview.SCHEMA or type(raw) is not bytes or len(raw) > 32768:
        raise ValueError('Invalid XP2 public diplomatic relationship readback')
    rows = json.loads(raw)
    targets = overview['targets']
    if (type(rows) is not list or len(rows) != len(targets)
            or any(type(row) is not dict or set(row) != {'player_id', 'relationship'}
                   or type(row['player_id']) is not int or row['player_id'] != target['player_id']
                   for row, target in zip(rows, targets))):
        raise ValueError('XP2 relationships differ from the current met targets')
    public = dict(overview, schema=diplomacy_overview.RELATIONSHIPS_SCHEMA,
                  targets=[dict(target, relationship=row['relationship']) for row, target in zip(rows, targets)])
    return diplomacy_overview.validate(public, pid, turn)


def read(prefix, overview):
    raw = (prefix.runtime.evaluate_text(prefix.ui_child, _source(overview),
               b'@xp2_public_diplomatic_relationships', capacity=32768)
           if overview['targets'] else b'[]')
    return parse(overview, raw)


_READ_WARS = br'''
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'Diplomatic war reader crossed its player or turn')
local diplomacy=Players[pid]:GetDiplomacy()
local rows={}
for _,player in ipairs(PlayerManager.GetAliveMajors()) do
 local target=player:GetID()
 assert(type(target)=='number' and target%1==0 and target>=0 and target<limit and player:IsMajor(),
  'Invalid living major identity')
 if target~=pid then
  local met=diplomacy:HasMet(target)
  assert(type(met)=='boolean','Missing local contact state')
  if met then
   local atWar=diplomacy:IsAtWarWith(target)
   assert(type(atWar)=='boolean','Missing local war state')
   rows[#rows+1]={id=target,atWar=atWar}
  end
 end
end
table.sort(rows,function(a,b) return a.id<b.id end)
local result={}
for index,row in ipairs(rows) do
 result[index]='{"player_id":'..row.id..',"at_war":'..tostring(row.atWar)..'}'
end
return '['..table.concat(result,',')..']'
'''


def read_wars(prefix, player_id, turn):
    """Read only war states visible from the current UI player's own diplomacy."""
    if (type(player_id) is not int or not 0 <= player_id < MAX_PLAYERS
            or type(turn) is not int or not 0 <= turn <= (1 << 31) - 1):
        raise ValueError('Invalid XP2 diplomatic war reader identity')
    source = b'local pid,turn,limit=%d,%d,%d\n' % (player_id, turn, MAX_PLAYERS) + _READ_WARS
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@xp2_public_diplomatic_wars', capacity=4096)
    if type(raw) is not bytes or len(raw) > 4096:
        raise ValueError('Invalid XP2 diplomatic war readback')
    from .player_views import _read_json

    return validate_diplomatic_wars(_read_json(raw), player_id)

"""Data-only Current Effects proposal cards, for a separately admitted reader.

LUA uses the existing Congress serializer/helpers and qualified GameInfo and
Locale bindings. It does not query Congress,
open a popup, authorize a phase, or produce an acknowledgement. The caller must
retain its exact owner/phase admission around scope, configuration and readback.

projectProposalCards(native, pid, readEmergency, presentTarget) returns cards.
readEmergency must call the real GetSingleEmergency(target, emergencyType).
presentTarget(target, nativeName) returns the exact source-localized name and
the existing visible reference (or json_null), using scoped configuration.
Hidden raw IDs remain in scope/native arguments and are never copied to cards.
No icon is
exported: the official goal icon depends on an unqualified bPlayerisTarget.
"""
import hashlib
from pathlib import Path

SOURCE = ('work/trade-common-client/congress-active-effects-source/proposals/source.json',
          'e0e5e9abc25313e7bdf89ae298c3c91b5b3e51b8db815ec0fa49b5724ae95ac8')

LUA = r'''
local function pcInteger(value,field)
 return int(value,'proposal card '..field,-2147483648,2147483647)
end
local function pcTable(value,field)
 assert(type(value)=='table','proposal card '..field..' absent');return value
end
local function pcCategories(native)
 pcTable(native,'native proposals');local result={}
 if native.Proposals~=nil then
  for key,category in pairs(pcTable(native.Proposals,'categories'))do
   local def=GameInfo.ProposalTypes[key]
   assert(def,'proposal card category definition absent')
   local rows=pcTable(pcTable(category,'category').ProposalsOfType,'category rows')
   if next(rows)~=nil then push(result,{definition=def,sort=finite(def.Sort),rows=rows})end
  end
 end
 table.sort(result,function(a,b)return a.sort<b.sort end)
 return result
end
local function proposalCardScope(native)
 local seen={};local result={players=array(),leader_ids=array()}
 for _,category in ipairs(pcCategories(native))do
  for _,row in pairs(category.rows)do
   local target=pcInteger(pcTable(row,'row').Target,'target')
   if target>=0 and target<64 then seen[target]=true end
  end
 end
 for id=0,63 do if seen[id]then push(result.players,id);push(result.leader_ids,id)end end
 return result
end
local function pcDetails(emergency,localPlayerID)
 local e=pcTable(emergency,'emergency')
 local target=pcInteger(e.TargetID,'emergency target')
 local turns=pcInteger(e.TurnsLeft,'emergency turns')
 local kind=pcInteger(e.EmergencyType,'emergency type')
 local definition=GameInfo.Emergencies_XP2[kind]
 assert(definition,'proposal card emergency definition absent')
 local hostile=boolean(definition.Hostile,'proposal card hostile')
 local success=boolean(e.bSuccess,'proposal card success')
 local begun=boolean(e.HasBegun,'proposal card begun')
 local crisis,rewards,goals=array(),array(),array()
 local function line(output,value)push(output,text(value))end
 local function label(output,key)line(output,Locale.Lookup(key))end
 local function entries(field)return pcTable(e[field],field)end
 local function append(output,rows)
  -- These are native tables, not normalized arrays. Match the UI's ipairs:
  -- index0 is not displayed and the first missing positive key stops traversal.
  for _,value in ipairs(rows)do line(output,value)end
 end
 if next(entries('GoalsTable'))~=nil then
  label(crisis,'LOC_EMERGENCY_COMPLETE_THESE_GOALS')
  local chosen=target==localPlayerID and entries('TargetGoalsTable')or e.GoalsTable
  for _,goal in ipairs(chosen)do
   pcTable(goal,'goal');local name=text(goal.Name)
   if name~=''then
    push(goals,{name=name,completed=boolean(goal.Completed,'proposal card goal completion')})
    line(crisis,name)
   end
  end
 end
 if next(entries('ScoreSourcesTable'))~=nil then
  label(crisis,'LOC_EMERGENCY_SCORE_HOW_TO');append(crisis,e.ScoreSourcesTable)
 end
 if next(entries('BuffsText'))~=nil then
  label(crisis,hostile and 'LOC_EMERGENCY_BUFFS_EXPLANATION'or 'LOC_EMERGENCY_COMPETITION_BUFFS_EXPLANATION')
  append(crisis,e.BuffsText)
 end
 local extraBuffs=text(e.ExtraBuffs)
 if extraBuffs~=''then line(crisis,extraBuffs)end
 local first=entries('MemberRewardsTextFirst');local top=entries('MemberRewardsTextTop')
 local bottom=entries('MemberRewardsTextBottom');local extra=entries('MemberRewardsTextExtra')
 if success or turns>=0 or not begun then
  if(next(first)~=nil or next(top)~=nil or next(bottom)~=nil or next(extra)~=nil)and(success or turns>=0)then
   label(rewards,hostile and 'LOC_EMERGENCY_MEMBER_REWARDS_HOSTILE_EXPLANATION'or 'LOC_EMERGENCY_REWARD_NON_HOSTILE_DESCRIPTION')
  end
  if next(first)~=nil then
   label(rewards,hostile and 'LOC_SCORED_COMPETITION_MEMBER_TIER_TITLE'or 'LOC_SCORED_COMPETITION_GOLD_TIER_TITLE')
   append(rewards,first)
  end
  if next(top)~=nil then
   label(rewards,hostile and 'LOC_SCORED_COMPETITION_TARGET_TIER_TITLE'or 'LOC_SCORED_COMPETITION_SILVER_TIER_TITLE')
   append(rewards,top)
  end
  if next(bottom)~=nil then
   label(rewards,hostile and 'LOC_SCORED_COMPETITION_NO_TIER_TITLE_NONE'or 'LOC_SCORED_COMPETITION_BRONZE_TIER_TITLE')
   append(rewards,bottom)
  end
  if next(extra)~=nil then
   if next(bottom)~=nil or next(top)~=nil or next(first)~=nil then label(rewards,'LOC_EMERGENCY_REWARD_EXTRA_EFFECTS_DESCRIPTION')end
   append(rewards,extra)
  end
  label(rewards,next(bottom)~=nil and 'LOC_SCORED_COMPETITION_NO_TIER_TITLE_BOTTOM'or 'LOC_SCORED_COMPETITION_NO_TIER_TITLE_NONE')
 end
 local extraRewards=text(e.ExtraRewards)
 if extraRewards~=''and(success or turns>=0)then line(rewards,extraRewards)end
 if hostile then
  local targetRewards=entries('TargetRewardsText')
  if next(targetRewards)~=nil and(not success or turns>=0 or not begun)then
   label(rewards,(turns>=0 or not begun)and 'LOC_EMERGENCY_TARGET_REWARDS_EXPLANATION'or 'LOC_EMERGENCY_TARGET_HAS_WON_REWARDS')
   append(rewards,targetRewards)
  end
 end
 return {description=text(e.ShortDescriptionText),turns_left=turns,
         emergency_type=text(definition.EmergencyType),goals=goals,
         crisis_details=crisis,rewards_details=rewards}
end
local function projectProposalCards(native,localPlayerID,readEmergency,presentTarget)
 int(localPlayerID,'proposal card local player',0,63)
 assert(type(readEmergency)=='function'and type(presentTarget)=='function','proposal card native readers absent')
 local result=array()
 for _,category in ipairs(pcCategories(native))do
  local def=category.definition
  for _,row in pairs(category.rows)do
   pcTable(row,'row')
   local target=pcInteger(row.Target,'target');local kind=pcInteger(row.EmergencyType,'type')
   local name,ref=presentTarget(target,text(row.Name));name=text(name)
   if ref~=json_null then
    pcTable(ref,'visible target')
    -- A copied native target must never bypass the existing visibility mapper.
    assert(ref.player_id==json_null or ref.player_id==target,'proposal card visible target mismatch')
    ref={player_id=ref.player_id,label=text(ref.label)}
   end
   local emergency=readEmergency(target,kind)
   assert(type(emergency)=='table','proposal card GetSingleEmergency returned no matching emergency')
   assert(pcInteger(emergency.TargetID,'returned target')==target,'proposal card emergency target mismatch')
   local detail=pcDetails(emergency,localPlayerID)
   push(result,{index=#result,category_type=text(def.ProposalType),category_name=text(Locale.Lookup(def.Name)),
    type_name=text(row.TypeName),name=name,target=ref,is_new=pcInteger(row.IsNew,'new flag')~=0,
    description=detail.description,turns_left=detail.turns_left,emergency_type=detail.emergency_type,
    goals=detail.goals,crisis_details=detail.crisis_details,rewards_details=detail.rewards_details})
  end
 end
 return result
end
'''


def source_dependencies():
    """Static helper authority; the enclosing reader owns image/live admission."""
    from civ6_host.runtime.configuration_profiles import _source
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-current-effects-proposals.source.v1'
            or proof['static_only'] is not True or proof['native_execution'] is not False):
        raise ValueError('Congress proposal-card authority changed')
    result = {str(resolve_path(resource_root()/SOURCE[0]).resolve()): SOURCE[1]}
    for row in [*proof['parents'].values(), *proof['inputs'].values(), *proof['files'].values()]:
        path = resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Congress proposal-card source dependency changed')
        result[str(path.resolve())] = row['sha256']
    return result

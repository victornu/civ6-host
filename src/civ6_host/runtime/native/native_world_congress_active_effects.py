"""Current Effects resolution and proposal cards in the existing scoped UI query."""
import hashlib
import json
from pathlib import Path

from civ6_host.contracts import world_congress_active_effects as contract
from . import native_world_congress_review as shared
from . import native_congress_proposal_cards as cards
from .native_saved_trade import literal
from .native_saved_unit_orders import uint

SCHEMA=contract.SCHEMA
SOURCE=('work/trade-common-client/congress-active-effects-source/source.json',
        'bcb9c9d33e59ac02497a2b2e021e5623fd11a49938edd364279ff43196922600')
UI_SOURCE=('work/trade-common-client/congress-active-effects-source/proposals/ui-registration/source.json',
           '8aaa9c6a089cb3b2837201cbcee0691f919a54c1763b2cec8e1480186cec497f')
# The new proof independently establishes the same ordinary/button/pause gates.
# No strategic, tactical, active-turn or emergency-proposal requirement is added.
admission_allowed=shared.admission_allowed

LUA=shared._SHARED+cards.LUA+r'''
local function activeRows(native)
 assert(type(native)=='table','Congress active resolutions absent')
 local rows={}
 for _,row in pairs(native)do if type(row)=='table'then push(rows,row)end end
 return rows
end
local function readActive()
 local segment,stage=phase()
 assert(stage=='ordinary','Congress active effects UI unavailable during session')
 assert(ADMITTED_SEGMENT==nil or segment==ADMITTED_SEGMENT,'Congress active effects admission phase changed')
 local player=Players[pid];assert(player,'Congress active effects player absent')
 local diplomacy=player:GetDiplomacy();assert(diplomacy,'Congress active effects diplomacy absent')
 local wc=Game.GetWorldCongress();assert(wc,'Congress active effects API absent')
 local meeting=wc:GetMeetingStatus();assert(type(meeting)=='table','Congress meeting status absent')
 local native=wc:GetResolutions(pid)
 local proposals=wc:GetProposals(pid);assert(type(proposals)=='table','Congress active proposals absent')
 return segment,int(meeting.TurnsLeft,'active meeting turns left',-2147483648,2147483647),activeRows(native),diplomacy,proposals
end
local function targetID(row)
 assert(type(row.ChosenThing)=='string','Congress active target text absent')
 return int(tonumber(row.ChosenThing),'active target',-2147483648,2147483647)
end
local function scopeFor(rows,diplomacy,segment,proposals)
 local players,leaders={},{}
 for _,row in ipairs(rows)do
  if row.TargetType=='PlayerType'then
   local id=targetID(row)
   if id>=0 then
    int(id,'active configuration player',0,63);players[id]=true
    if id==pid or boolean(diplomacy:HasMet(id),'active met player')then leaders[id]=true end
   end
  end
 end
 local proposalScope=proposalCardScope(proposals)
 for _,id in ipairs(proposalScope.players)do players[id]=true end
 for _,id in ipairs(proposalScope.leader_ids)do leaders[id]=true end
 local result={segment=segment,players=array(),leader_ids=array()}
 for id=0,63 do
  if players[id]then result.players[#result.players+1]=id end
  if leaders[id]then result.leader_ids[#result.leader_ids+1]=id end
 end
 return result
end
local function activeScope()
 local segment,_,rows,diplomacy,proposals=readActive()
 local result=scopeFor(rows,diplomacy,segment,proposals)
 assert(phase()==segment,'Congress active effects perspective changed during scope read')
 return result
end
local function activeSnapshot(expectedScope)
 local segment,turns,rows,diplomacy,proposals=readActive()
 if expectedScope~=nil then
  assert(encode(scopeFor(rows,diplomacy,segment,proposals))==encode(expectedScope),
         'Congress active effects configuration scope changed during read')
 end
 local multiplayer=boolean(GameConfiguration.IsAnyMultiplayer(),'multiplayer')
 local function reference(id)
  local cfg=PlayerConfigurations[id];assert(cfg,'Congress active target configuration absent')
  local met=id==pid or boolean(diplomacy:HasMet(id),'active met player')
  local human=boolean(cfg:IsHuman(),'active human')
  local label=met and text(Locale.Lookup(cfg:GetLeaderName()))or text(Locale.Lookup('LOC_DIPLOPANEL_UNMET_PLAYER'))
  if multiplayer and human then label=label..' ('..text(cfg:GetPlayerName())..')'end
  return {player_id=met and id or json_null,label=text(label)}
 end
 local function target(row)
  local raw=text(row.ChosenThing)
  if row.TargetType~='PlayerType'then
   return {player_id=json_null,value=raw,label=text(Locale.Lookup(raw))}
  end
  local id=targetID(row)
  if id==-1 then return {player_id=json_null,value=json_null,label=''}end
  if id<0 then return {player_id=json_null,value=json_null,label=text(Locale.Lookup('LOC_WORLD_CONGRESS_SELECT_TARGET'))}end
  int(id,'active target player',0,63)
  local ref=reference(id)
  return {player_id=ref.player_id,value=ref.player_id~=json_null and tostring(id)or json_null,label=ref.label}
 end
 local result={schema=SCHEMA,player_id=pid,turn=turn,sequence=sequence,turn_segment=segment,
  meeting_turns_left=turns,resolutions=array(),proposals=array(),proposals_status='available'}
 for _,row in ipairs(rows)do
  int(row.Type,'active resolution Type',-2147483648,2147483647)
  local def=GameInfo.Resolutions[row.Type];assert(def,'Congress active resolution definition absent')
  push(result.resolutions,{index=#result.resolutions,resolution_type=text(def.ResolutionType),
   name=text(Locale.Lookup(def.Name)),target_type=text(row.TargetType),
   chosen_option=text(Locale.Lookup(row.ChosenOption)),chosen_label=text(row.ChosenLabel),
   chosen_target=target(row),is_new=boolean(row.IsNew,'active new flag'),turns_left=turns+1})
 end
 local function readEmergency(target,kind)
  assert(type(Game.GetEmergencyManager)=='function','Congress active emergency namespace absent')
  local manager=Game.GetEmergencyManager();assert(manager,'Congress active emergency manager absent')
  assert(type(manager.GetSingleEmergency)=='function','Congress active emergency method absent')
  return manager:GetSingleEmergency(target,kind)
 end
 local function presentTarget(target,name)
  local cfg=PlayerConfigurations[target]
  if cfg then return text(Locale.Lookup(name,cfg:GetLeaderName())),reference(target)end
  return text(Locale.Lookup(name)),json_null
 end
 result.proposals=projectProposalCards(proposals,pid,readEmergency,presentTarget)
 assert(phase()==segment,'Congress active effects perspective changed during read')
 return result
end
'''


def source(player_id,turn,sequence,*,expected_scope=None,admitted_segment=None,administrative=False):
    if administrative is not False:
        raise ValueError('Congress active effects have no administrative result projection')
    uint(player_id,'player',63);uint(turn,'turn',0x7fffffff);uint(sequence,'sequence',0xffffffff)
    if admitted_segment is not None:shared._integer(admitted_segment,0xffffffff)
    expected='nil'
    if expected_scope is not None:
        shared.validate_scope(expected_scope)
        if admitted_segment is not None and admitted_segment!=expected_scope['segment']:
            raise ValueError('Congress active effects expected and admitted phases differ')
        admitted_segment=expected_scope['segment']
        expected='{segment=%d,players=array({%s}),leader_ids=array({%s})}'%(
            expected_scope['segment'],','.join(map(str,expected_scope['players'])),','.join(map(str,expected_scope['leader_ids'])))
    return (f'local pid,turn,sequence={player_id},{turn},{sequence}\n'
            f'local SCHEMA={literal(SCHEMA)}\n'
            f'local ADMITTED_SEGMENT={admitted_segment if admitted_segment is not None else "nil"}\n').encode()+LUA.encode()+(
            '\nreturn encode(activeSnapshot('+expected+'))\n').encode()


def scope_source(player_id,turn,sequence,*,admitted_segment=None):
    chunk=source(player_id,turn,sequence,admitted_segment=admitted_segment)
    return chunk[:chunk.rindex(b'\nreturn encode(activeSnapshot(')]+b'\nreturn encode(activeScope())\n'


def parse(raw,player_id,turn,sequence):
    if type(raw) is not bytes or len(raw)>shared.LIMIT:
        raise ValueError('Unbounded Congress active effects wire')
    value=json.loads(raw,object_pairs_hook=shared._unique)
    return contract.validate_catalogue(value,player_id,turn,sequence)


def source_dependencies(*,execution_image):
    from civ6_host.runtime.configuration_profiles import _source
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    result=shared.source_dependencies(execution_image=execution_image)
    # The immutable resolution proof described its initial proposals gap. The
    # separately pinned card authority supplies that exact additional UI path.
    result.update(cards.source_dependencies())
    proof=_source(SOURCE)
    if (proof['schema']!='civ6-host.xp2-congress-active-effects.source.v1'
            or proof['static_only'] is not True or proof['native_execution'] is not False
            or proof['host_modified'] is not False
            or proof['inputs']['review_admission']['sha256']!=shared.SOURCE[1]
            or proof['native_shape']['method']!='Game.GetWorldCongress():GetResolutions(localPlayerID)'
            or proof['proposal_separation']['contract']!='proposals=null; proposals_status=summary_source_unqualified for this first resolutions-only group.'):
        raise ValueError('Congress active effects source contract differs')
    result[str(resolve_path(resource_root()/SOURCE[0]).resolve())]=SOURCE[1]
    for row in [*proof['inputs'].values(),*proof['files'].values()]:
        path=resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Congress active effects source dependency changed')
        result[str(path.resolve())]=row['sha256']
    ui=_source(UI_SOURCE)
    if (ui['schema']!='civ6-host.xp2-congress-emergency-ui-registration.source.v1'
            or ui['static_only'] is not True or ui['native_execution'] is not False or ui['host_modified'] is not False
            or ui['frozen_sources_preserved']['proposals']!=cards.SOURCE[1]
            or ui['inputs']['core']['sha256']!=proof['inputs']['core']['sha256']
            or [(r['current_body'],r['byte_identical']) for r in ui['historical_current_correspondence']]!=[
                ('0x5bdd80',True),('0x740ca0',True)]
            or ui['direct_dependency_inventory']['callback']!='0xa3170'
            or ui['direct_dependency_inventory']['other_indirect_calls']!=()):
        raise ValueError('Congress emergency UI registration source differs')
    result[str(resolve_path(resource_root()/UI_SOURCE[0]).resolve())]=UI_SOURCE[1]
    for row in ui['inputs'].values():
        path=resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Congress emergency UI dependency changed')
        result[str(path.resolve())]=row['sha256']
    return result

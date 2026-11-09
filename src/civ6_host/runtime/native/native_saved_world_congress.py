"""Bounded player UI readback and exact Congress parameter translation.

All native methods below are consumed by the pinned official Lua. The wire has
separate public and private objects; only public is admitted to client replies.
Current foreign ballots, manager internals and source identities are not read.
"""
import json

from civ6_host.contracts import world_congress as contract
from .native_saved_trade import COMMON_LUA, literal as _literal
from .native_saved_unit_orders import uint
from ..xp2_world_congress_source import OPERATIONS, PARAMETERS, enum_values

LIMIT = 2 * 1024 * 1024
# Reuse the shared bounded serializer, not trade's strategic-turn readiness.
LUA = ('local json_null={}\n' + COMMON_LUA[:COMMON_LUA.index('local function ready()')]
       + COMMON_LUA[COMMON_LUA.index('local array_tag={}'):]).replace('trade', 'congress').replace(
    "if type(v)=='string'then", "if v==json_null then return 'null'\n elseif type(v)=='string'then")
LUA += r'''
local function hash(v)return int(v,'native DWORD',-2147483648,4294967295)%4294967296 end
local function maybeBool(v,label)if v==nil then return false end;return boolean(v,label)end
local function symbol(v)
 assert(type(v)=='string'or type(v)=='number','Congress symbolic value absent')
 if type(v)=='number'then finite(v)end
 return text(tostring(v))
end
local function money(v)finite(v);assert(v>=0 and v<=2147483647,'Congress favor bound');return v end
local function push(rows,row)assert(#rows<4096,'Congress row limit');rows[#rows+1]=row end
local function ordered(rows,metadata)
 assert(type(rows)=='table','Congress native rows absent')
 local keys={}
 for k,v in pairs(rows)do
  -- The resolution caller consumes only numeric keys; proposal callers
  -- consume every pair. Count bounds do not constrain a native table key.
  if not metadata or type(k)=='number'then keys[#keys+1]=k end
  assert(#keys<=4096,'Congress native row limit')
 end
 assert(#keys<=4096,'Congress native row limit');local result={}
 for _,k in ipairs(keys)do result[#result+1]=rows[k]end
 return result,keys
end
local function phase()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
        'Congress player perspective changed')
 local segment=hash(Game.GetCurrentTurnSegment())
 local stage='ordinary'
 if segment==hash(DB.MakeHash('TURNSEG_WORLDCONGRESS_1'))then stage='regular'
 elseif segment==hash(DB.MakeHash('TURNSEG_WORLDCONGRESS_2'))then stage='special'
 elseif segment==hash(DB.MakeHash('TURNSEG_WORLDCONGRESS_RESOLUTION'))then stage='resolving'end
 return segment,stage
end
local function snapshot()
 local segment,stage=phase()
 local player=Players[pid];assert(player,'Congress player absent')
 local config=PlayerConfigurations[pid];assert(config,'Congress local configuration absent')
 local wc=Game.GetWorldCongress();assert(wc,'WorldCongress API unavailable')
 local diplomacy=player:GetDiplomacy();assert(diplomacy,'Congress diplomacy absent')
 local function reference(id)
  if id==nil then return {player_id=json_null,label=text(Locale.Lookup('LOC_DIPLOPANEL_UNMET_PLAYER'))}end
  int(id,'proposal player',-2147483648,2147483647)
  local visible=id>=0 and id<64 and (id==pid or boolean(diplomacy:HasMet(id),'met player'))
  if not visible then
   return {player_id=json_null,label=text(Locale.Lookup('LOC_DIPLOPANEL_UNMET_PLAYER'))}
  end
  local cfg=PlayerConfigurations[id];assert(cfg,'Congress visible configuration was not read')
  return {player_id=id,label=text(Locale.Lookup(cfg:GetLeaderName()))}
 end
 local function costs(raw)
  assert(type(raw)=='table','Congress native costs absent')
  local max=int(raw.MaxVotes,'MaxVotes',0,2147483647);local rows=array();local count=0
  for k,_ in pairs(raw)do if type(k)=='number'then int(k,'cost key',0,4095);count=count+1
   else assert(k=='MaxVotes','unknown Congress cost metadata')end end
  for i=0,count-1 do rows[#rows+1]=money(raw[i])end
  return {max_votes=max,costs=rows}
 end
 local active=stage=='regular'or stage=='special'
 local currentFavor=money(player:GetFavor())
 local result={schema=SCHEMA,player_id=pid,turn=turn,sequence=sequence,turn_segment=segment,
  stage=stage,paused=boolean(GameConfiguration.IsPaused(),'paused'),
  in_session=boolean(wc:IsInSession(),'in session'),local_alive=boolean(config:IsAlive(),'local alive'),
  turn_active=boolean(player:IsTurnActive(),'requested player turn active'),
  meeting=json_null,favor=currentFavor,current_favor=currentFavor,vote_cost=json_null,
  resolutions=json_null,discussions=json_null,proposals=json_null,
  presentation='closed',offers={open=false,confirm_ballot=false,confirm_proposals=false,close=false},
  unavailable=UNAVAILABLE}
 local private={enums={},discussions=array(),proposals=array(),
  order={resolutions=array(),discussions=array(),proposals=array()},
  popup={capability=GameInfo.GameCapabilities['CAPABILITY_WORLD_CONGRESS']~=nil,
   current_era=int(Game.GetEras():GetCurrentEra(),'current era',-2147483648,2147483647),
   initial_era=int(GlobalParameters.WORLD_CONGRESS_INITIAL_ERA,'Congress initial era',-2147483648,2147483647),
   has_emergency_proposals=false}}
 if ADMIN_TARGETS then private.resolution_targets=array()end
 local resolutionVotes,discussionVotes,proposalVotes={},{},{}
 for _,name in ipairs(OPERATION_NAMES)do private.enums[name]=hash(PlayerOperations[name])end
 if stage=='ordinary'then
  local meeting=wc:GetMeetingStatus();assert(type(meeting)=='table','meeting status absent')
  result.meeting={turns_left=int(meeting.TurnsLeft,'meeting turns',-2147483648,2147483647),
                  percentage=finite(meeting.Percentage)}
 end
 local defaultCosts=nil
 if stage=='regular'then defaultCosts=costs(wc:GetVotesandFavorCost(pid));result.vote_cost=defaultCosts end
 if stage=='regular'then
  result.resolutions=array()
  local nativeRows,nativeKeys=ordered(wc:GetResolutions(pid),true)
  for position,row in ipairs(nativeRows)do
   local def=GameInfo.Resolutions[row.Type];assert(def,'resolution definition absent')
   local targets=array();local rawTargets=array();dense(row.PossibleTargets,4096)
   for i,value in ipairs(row.PossibleTargets)do
    if row.TargetType=='PlayerType'then
     local id=tonumber(value);assert(id,'invalid player target');local ref=reference(id)
     if ADMIN_TARGETS then push(rawTargets,id)end
     push(targets,{index=i-1,value=ref.player_id==json_null and json_null or tostring(id),
                   label=ref.label,player_id=ref.player_id})
    else push(targets,{index=i-1,value=text(value),label=text(Locale.Lookup(value)),player_id=json_null})end
   end
   push(result.resolutions,{resolution_hash=hash(def.Hash),resolution_type=text(def.ResolutionType),
    name=text(Locale.Lookup(def.Name)),effect_a=text(Locale.Lookup(def.Effect1Description)),
    effect_b=text(Locale.Lookup(def.Effect2Description)),target_type=text(row.TargetType),targets=targets})
   if ADMIN_TARGETS and row.TargetType=='PlayerType'then
    push(private.resolution_targets,{resolution_hash=hash(def.Hash),resolution_type=text(def.ResolutionType),
     target_type='PlayerType',targets=rawTargets})
   end
   resolutionVotes[nativeKeys[position]]=hash(def.Hash)
  end
 end
 local function proposals(raw,available)
  assert(type(raw)=='table'and type(raw.Proposals)=='table','Congress proposals absent')
  local categories={}
  for key,category in pairs(raw.Proposals)do
   local def=GameInfo.ProposalTypes[key];assert(def,'proposal category absent')
   assert(#categories<4096,'Congress category limit')
   categories[#categories+1]={key=key,sort=finite(def.Sort),category=category}
  end
  table.sort(categories,function(a,b)return a.sort<b.sort end)
  local rows=array();local rawRows=available and private.proposals or private.discussions
  local targetKeys={};local targetCount=0
  for _,category in ipairs(categories)do
   local categoryCosts=nil
   if not available then
    if category.category.FavorCost~=nil then categoryCosts=costs(category.category.FavorCost)
    else
     if not defaultCosts then defaultCosts=costs(wc:GetVotesandFavorCost(pid))end
     categoryCosts=defaultCosts
    end
   end
   for _,row in ipairs(ordered(category.category.ProposalsOfType,false))do
    local sender,target=reference(row.Sender),reference(row.Target)
    local restriction=row.VotingRestriction and GameInfo.VotingBlockers[row.VotingRestriction]or nil
    assert(not row.VotingRestriction or restriction,'voting blocker absent')
    local blocker=row.ProposalBlockerType and GameInfo.ProposalBlockers[row.ProposalBlockerType]or nil
    assert(not row.ProposalBlockerType or blocker,'proposal blocker absent')
    local disabled=maybeBool(row.Disabled,'proposal disabled')
    local public={index=#rows,type_name=symbol(row.TypeName),sender=sender,target=target,
      name=text(Locale.Lookup(row.Name,target.label)),description=text(Locale.Lookup(row.Description,target.label)),
      disabled=disabled,blocker=blocker and text(Locale.Lookup(blocker.Description))or json_null}
    if available then
     if targetKeys[row.Target]==nil then targetKeys[row.Target]=targetCount;targetCount=targetCount+1 end
     public.target_key=targetKeys[row.Target];public.favor_cost=money(category.category.FavorCost)
    else
     public.vote_cost=categoryCosts
     public.no_upvote=restriction and maybeBool(restriction.NoUpvote,'no upvote')or false
     public.no_downvote=restriction and maybeBool(restriction.NoDownvote,'no downvote')or false
     -- Disabled and fully blocked rows remain observable but are not offered.
    end
    push(rows,public)
    push(rawRows,{sender=available and row.Sender==nil and json_null or int(row.Sender,'sender',-2147483648,2147483647),
                  target=int(row.Target,'target',-2147483648,2147483647),discussion_type=available and hash(row.Type)or json_null})
    local voteKey=tostring(row.TypeName)..'_'..row.Target..'_'..(row.Sender~=nil and row.Sender or 'NONE')
    local votes=available and proposalVotes or discussionVotes
    if available or(not disabled and not(public.no_upvote and public.no_downvote))then
     assert(votes[voteKey]==nil,'duplicate official proposal vote key');votes[voteKey]=public.index
    end
   end
  end
  return rows
 end
 if active then result.discussions=proposals(wc:GetProposals(pid),false)
 elseif stage=='ordinary'then result.proposals=proposals(wc:GetEmergencies(pid),true)
  private.popup.has_emergency_proposals=#result.proposals>0 end
 for _,hashValue in pairs(resolutionVotes)do push(private.order.resolutions,hashValue)end
 for _,index in pairs(discussionVotes)do push(private.order.discussions,index)end
 for _,index in pairs(proposalVotes)do push(private.order.proposals,index)end
 assert(phase()==segment,'Congress turn segment changed during read')
 return {public=result,private=private}
end
'''


def source(player_id, turn, sequence, *, administrative_targets=False):
    uint(player_id, 'player', 63); uint(turn, 'turn', 0x7fffffff); uint(sequence, 'sequence', 0xffffffff)
    if type(administrative_targets) is not bool:
        raise ValueError('Congress target projection requires an exact private Boolean')
    return (f'local pid,turn,sequence={player_id},{turn},{sequence}\n'
            f'local SCHEMA={_literal(contract.SCHEMA)}\n'
            f'local ADMIN_TARGETS={str(administrative_targets).lower()}\n'
            f'local UNAVAILABLE=nil\nlocal OPERATION_NAMES={_literal([*OPERATIONS.values(), *PARAMETERS])}\n').encode() + LUA.encode() + (
                '\nUNAVAILABLE=array(' + _literal(list(contract.UNAVAILABLE)) + ')\nreturn encode(snapshot())\n').encode()


def parse(raw, player_id, turn, sequence, *, administrative_targets=False):
    if type(administrative_targets) is not bool:
        raise ValueError('Congress target projection requires an exact private Boolean')
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded Congress UI readback')
    def unique(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('Duplicate Congress wire key')
            result[key] = value
        return result
    envelope = json.loads(raw, object_pairs_hook=unique)
    if type(envelope) is not dict or set(envelope) != {'public', 'private'}:
        raise ValueError('Invalid Congress UI envelope')
    public, private = envelope['public'], envelope['private']
    # Offers are assigned by the owner from these source-described observations
    # and its separately recorded request-delivery ledger before full validation.
    if (public.get('player_id'), public.get('turn'), public.get('sequence')) != (player_id, turn, sequence):
        raise ValueError('Congress UI readback crossed its identity')
    private_keys = {'enums', 'discussions', 'proposals', 'order', 'popup'}
    if administrative_targets: private_keys.add('resolution_targets')
    if type(private) is not dict or set(private) != private_keys:
        raise ValueError('Invalid private Congress transport mapping')
    enums = private['enums']
    if (type(enums) is not dict or set(enums) != set(OPERATIONS.values()) | set(PARAMETERS)
            or any(type(v) is not int or not 0 <= v <= 0xffffffff for v in enums.values())
            or enums != enum_values()):
        raise ValueError('Congress native enums are missing or outside DWORD bounds')
    for key in ('discussions', 'proposals'):
        rows = private[key]
        if type(rows) is not list or len(rows) != len(public[key] or []):
            raise ValueError('Congress private/public row correspondence differs')
        for row in rows:
            if (type(row) is not dict or set(row) != {'sender', 'target', 'discussion_type'}
                    or type(row['target']) is not int or not -0x80000000 <= row['target'] <= 0x7fffffff
                    or not ((key == 'proposals' and row['sender'] is None)
                            or (type(row['sender']) is int and -0x80000000 <= row['sender'] <= 0x7fffffff))
                    or not ((key == 'discussions' and row['discussion_type'] is None)
                            or (key == 'proposals' and type(row['discussion_type']) is int
                                and 0 <= row['discussion_type'] <= 0xffffffff))):
                raise ValueError('Invalid Congress private parameter row')
    contract.validate_catalogue(public, player_id, turn, sequence)
    if administrative_targets:
        expected = [r for r in public['resolutions'] or [] if r['target_type'] == 'PlayerType']
        rows = private['resolution_targets']
        if type(rows) is not list or len(rows) != len(expected):
            raise ValueError('Congress private resolution targets lost public correspondence')
        for row, actual in zip(rows, expected):
            if (type(row) is not dict or set(row) != {'resolution_hash', 'resolution_type', 'target_type', 'targets'}
                    or any(row[k] != actual[k] for k in ('resolution_hash', 'resolution_type', 'target_type'))
                    or type(row['resolution_hash']) is not int
                    or type(row['targets']) is not list or len(row['targets']) != len(actual['targets'])):
                raise ValueError('Congress private resolution identity differs')
            for target, visible in zip(row['targets'], actual['targets']):
                if (type(target) is not int or not -0x80000000 <= target <= 0x7fffffff
                        or visible['player_id'] is not None and (
                            visible['player_id'] != target or visible['value'] != str(target))):
                    raise ValueError('Congress private target differs from its visible projection')
    popup = private['popup']
    if (type(popup) is not dict or set(popup) != {'capability', 'current_era', 'initial_era', 'has_emergency_proposals'}
            or any(type(popup[k]) is not bool for k in ('capability', 'has_emergency_proposals'))
            or any(type(popup[k]) is not int or not -0x80000000 <= popup[k] <= 0x7fffffff
                   for k in ('current_era', 'initial_era'))
            or popup['has_emergency_proposals'] != bool(public['proposals'])):
        raise ValueError('Congress popup gates differ from source readback')
    expected = dict(resolutions=[r['resolution_hash'] for r in (public['resolutions'] or [])],
        discussions=[r['index'] for r in (public['discussions'] or []) if not r['disabled']
                     and not (r['no_upvote'] and r['no_downvote'])],
        proposals=[r['index'] for r in (public['proposals'] or [])])
    if type(private['order']) is not dict or set(private['order']) != set(expected):
        raise ValueError('Congress private source emission order is absent')
    for key, indices in expected.items():
        actual = private['order'][key]
        if (type(actual) is not list or any(type(v) is not int for v in actual)
                or len(actual) != len(indices) or set(actual) != set(indices)):
            raise ValueError('Congress source emission order differs from its rows')
    return envelope


def ordered_plan(plan, private):
    """Retain the private UI-keyed pairs order; actor ordering has no effect."""
    selections = {r['resolution_hash']: r for r in plan if r['kind'] == 'congress_resolution_vote'}
    discussions = {r['discussion_index']: r for r in plan if r['kind'] == 'congress_discussion_vote'}
    proposals = {r['proposal_index']: r for r in plan if r['kind'] == 'congress_discussion_selection'}
    result = [selections[k] for k in private['order']['resolutions'] if k in selections]
    result += [discussions[k] for k in private['order']['discussions'] if k in discussions]
    result += [proposals[k] for k in private['order']['proposals'] if k in proposals]
    result += [r for r in plan if r['kind'] in ('congress_submit', 'congress_looked_at_available')]
    if len(result) != len(plan):
        raise ValueError('Congress operation plan has an unknown private source-order entry')
    return result


def query(prefix, player_id, turn, sequence, backend):
    from .. import xp2_congress_configuration as environment
    from ..xp2_initial_query_source import source as initial_source
    # Validate input before either native read. This preflight copies only own
    # and already-met identities; no foreign configuration names are consulted.
    administrative_targets = getattr(backend, '_xp2_world_congress_review_requested', False)
    if type(administrative_targets) is not bool:
        raise ValueError('Congress administrative target request must be Boolean')
    chunk = source(player_id, turn, sequence, administrative_targets=administrative_targets)
    initial_source(execution_image=getattr(backend.core, '_civ6_host_execution_image', None))
    environment.attach_namespaces(prefix, backend)
    scope = (f'local pid,turn={player_id},{turn}\n' + LUA[:LUA.index('local function snapshot()')]
             + "\nlocal segment=phase();local ids=array();local player=Players[pid];assert(player,'Congress player absent')\n"
             + "local diplomacy=player:GetDiplomacy();assert(diplomacy,'Congress diplomacy absent')\n"
             + "for id=0,63 do if id==pid or boolean(diplomacy:HasMet(id),'met player')then ids[#ids+1]=id end end\n"
             + "return encode({segment=segment,players=ids})\n").encode()
    scope_raw = prefix.runtime.evaluate_text(prefix.ui_child, scope, b'@player_congress_configuration_scope', capacity=4097)
    if type(scope_raw) is not bytes or len(scope_raw) > 4096:
        raise ValueError('Unbounded Congress configuration scope')
    scoped = json.loads(scope_raw)
    if (type(scoped) is not dict or set(scoped) != {'segment', 'players'}
            or type(scoped['segment']) is not int or not 0 <= scoped['segment'] <= 0xffffffff):
        raise ValueError('Invalid Congress configuration scope')
    preamble = environment.lua_bindings(environment.read(backend, scoped['players'], local_player_id=player_id))
    raw = prefix.runtime.evaluate_text(prefix.ui_child, preamble + chunk,
        b'@player_world_congress', capacity=LIMIT + 1)
    result = parse(raw, player_id, turn, sequence, administrative_targets=administrative_targets)
    if result['public']['turn_segment'] != scoped['segment']:
        raise ValueError('Congress phase changed across configuration read')
    return result


def request_parameters(action, private):
    contract.validate_operation(action)
    kind = action['kind']; enums = private['enums']
    def pair(key, value):
        if type(value) is not int or not -0x80000000 <= value <= 0xffffffff:
            raise ValueError('Congress value is outside source DWORD representation')
        return enums[key], value % 0x100000000
    if kind == 'congress_resolution_vote':
        values = [('PARAM_RESOLUTION_TYPE', action['resolution_hash']),
                  ('PARAM_WORLD_CONGRESS_VOTES', action['votes']),
                  ('PARAM_RESOLUTION_OPTION', action['option']),
                  ('PARAM_RESOLUTION_SELECTION', action['target_index'])]
    elif kind == 'congress_discussion_vote':
        row = private['discussions'][action['discussion_index']]
        values = [('PARAM_PLAYER_ONE', row['sender']), ('PARAM_PLAYER_TWO', row['target']),
                  ('PARAM_WORLD_CONGRESS_VOTES', action['votes'])]
    elif kind == 'congress_discussion_selection':
        row = private['proposals'][action['proposal_index']]
        values = [('PARAM_OTHER_PLAYER', row['target']), ('PARAM_DISCUSSION_TYPE', row['discussion_type'])]
    else:
        values = []
    parameters = dict(pair(key, value) for key, value in values)
    if len(parameters) != len(values):
        raise ValueError('Congress native parameter enum collision')
    return enums[OPERATIONS[kind]], parameters

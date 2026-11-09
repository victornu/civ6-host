"""Player-visible last Congress results; staged independently of the API schema.

The turn/sequence identify this observation, not the historical meeting. No
request, receipt, submission acknowledgement or checkpoint decision is produced.
The caller retains the ordinary saved-owner/source verification boundary.
"""
import hashlib
import json
from pathlib import Path

from civ6_host.contracts import world_congress_review as contract
from civ6_host.runtime.native.native_saved_world_congress import LUA as _CONGRESS_LUA
from civ6_host.runtime.native.native_saved_trade import literal
from civ6_host.runtime.native.native_saved_unit_orders import uint

SCHEMA = contract.SCHEMA
LIMIT = 2 * 1024 * 1024
SHARED_PREFIX_SHA256 = '0902af1da0cf523b9ee47de7f9aca8e3919c769096718d2794a43ca593152716'
SOURCE = ('work/trade-common-client/congress-review-staging/source-v2.json', '90327c7a7c3bad45080b650f5c4b92363a3dd6ceb6e085acc802a33225ca364a')
PRIVATE_SOURCE = ('work/trade-common-client/congress-review-staging/private-targets/source.json', 'e1210095fd627420c1c094fa2bac1db38faee6f256ea3334ef24bddeacffa2a6')
NUMERIC_SOURCE = ('work/trade-common-client/congress-review-staging/option-domain-source/source.json',
                  '1b27fbe4f61fe1e5007e919b1386ed0391a79359746766d4f5f68f7c55ffdca3')
_SHARED = _CONGRESS_LUA[:_CONGRESS_LUA.index('local function snapshot()')]
if hashlib.sha256(_SHARED.encode()).hexdigest() != SHARED_PREFIX_SHA256:
    raise ValueError('Congress review shared helpers changed; requalify the prefix')

LUA = _SHARED + r'''
local function reviewInt32(value,field)
 -- GetReview uses the signed-int32 Lua setter. The official UI compares
 -- exactly to 1 and displays every other raw value on the B side.
 local kind=type(value)
 local shown=(kind=='number' or kind=='boolean' or kind=='nil')and tostring(value)or('<'..kind..'>')
 return int(value,'review '..field..' value='..shown..' type='..kind,-2147483648,2147483647)
end
local function isNew(value)
 if value==nil or value==false then return false end
 if value==true then return true end
 return int(value,'new result flag',-2147483648,2147483647)~=0
end
local function resolutionRows(native)
 assert(type(native.Resolutions)=='table','Congress review resolutions absent')
 local rows={}
 -- Review iterates table-valued rows, not the active form's numeric-key test.
 for _,row in pairs(native.Resolutions)do if type(row)=='table'then push(rows,row)end end
 return rows
end
local function categories(native)
 local result={}
 if native.Discussions~=nil then
  assert(type(native.Discussions)=='table','Congress review discussions malformed')
  for key,category in pairs(native.Discussions)do
   local def=GameInfo.ProposalTypes[key]
   if def then
    assert(type(category)=='table','Congress review category malformed')
    local rows=ordered(category.ProposalsOfType,false)
    if #rows>0 then push(result,{definition=def,sort=finite(def.Sort),rows=rows})end
   end
  end
 end
 table.sort(result,function(a,b)return a.sort<b.sort end)
 return result
end
local function scopeFor(native,diplomacy,segment)
 local players,leaders={},{}
 local function reference(value,forceLeader)
  local id=int(tonumber(value),'review configuration player',0,63)
  players[id]=true
  if forceLeader or id==pid or boolean(diplomacy:HasMet(id),'review met player')then leaders[id]=true end
 end
 local function target(row,value)
  if row.TargetType=='PlayerType'then
   local index=int(tonumber(value),'review target',-2147483648,2147483647)
   if index~=-1 then reference(row.PossibleTargets and tonumber(row.PossibleTargets[index])or index)end
  end
 end
 for _,row in ipairs(resolutionRows(native))do
  target(row,row.ChosenThing)
  for _,selection in ipairs(ordered(row.PlayerSelections,false))do
   assert(type(selection)=='table','Congress review player selection absent')
   reference(selection.PlayerID);target(row,selection.ResolutionTarget)
  end
 end
 for _,category in ipairs(categories(native))do
  for _,row in ipairs(category.rows)do
   assert(type(row)=='table','Congress review discussion absent')
   for _,selection in ipairs(ordered(row.PlayerVotes,false))do
    assert(type(selection)=='table','Congress review discussion vote absent')
    reference(selection.PlayerType)
   end
   if row.TargetPlayer~=nil then
    local id=int(row.TargetPlayer,'discussion target',-2147483648,2147483647)
    -- Configuration's indexed provider contains the 64 player slots only.
    if id>=0 and id<64 then reference(id,true)end
   end
  end
 end
 local result={segment=segment,players=array(),leader_ids=array()}
 for id=0,63 do
  if players[id]then result.players[#result.players+1]=id end
  if leaders[id]then result.leader_ids[#result.leader_ids+1]=id end
 end
 return result
end
local function readReview()
 local segment,stage=phase()
 assert(stage=='ordinary','Congress review UI unavailable during session')
 assert(ADMITTED_SEGMENT==nil or segment==ADMITTED_SEGMENT,'Congress review admission phase changed')
 local player=Players[pid];assert(player,'Congress review player absent')
 local diplomacy=player:GetDiplomacy();assert(diplomacy,'Congress review diplomacy absent')
 local wc=Game.GetWorldCongress();assert(wc,'Congress review API absent')
 local native=wc:GetReview(pid);assert(type(native)=='table','Congress review result absent')
 return segment,native,diplomacy
end
local function reviewScope()
 local segment,native,diplomacy=readReview()
 local result=scopeFor(native,diplomacy,segment)
 assert(phase()==segment,'Congress review perspective changed during scope read')
 return result
end
local function reviewSnapshot(expectedScope)
 local segment,native,diplomacy=readReview()
 if expectedScope~=nil then
  assert(encode(scopeFor(native,diplomacy,segment))==encode(expectedScope),
         'Congress review configuration scope changed during read')
 end
 local multiplayer=boolean(GameConfiguration.IsAnyMultiplayer(),'multiplayer')
 local function reference(value)
  local id=int(tonumber(value),'review player',0,63)
  local cfg=PlayerConfigurations[id];assert(cfg,'Congress review player configuration absent')
  local met=id==pid or boolean(diplomacy:HasMet(id),'review met player')
  local human=boolean(cfg:IsHuman(),'review human')
  local label=met and text(Locale.Lookup(cfg:GetLeaderName()))or text(Locale.Lookup('LOC_DIPLOPANEL_UNMET_PLAYER'))
  if multiplayer and human then label=label..' ('..text(cfg:GetPlayerName())..')'end
  return {player_id=met and id or json_null,label=text(label)},id
 end
 local function target(row,value)
  if row.TargetType=='PlayerType'then
   local index=tonumber(value);assert(index,'Congress review target absent')
   int(index,'review target',-2147483648,2147483647)
   if index==-1 then return {player_id=json_null,value=json_null,label=''}end
   local id=row.PossibleTargets and tonumber(row.PossibleTargets[index])or index
   local ref=reference(id)
   return {player_id=ref.player_id,value=ref.player_id==json_null and json_null or tostring(id),label=ref.label}
  end
  return {player_id=json_null,value=text(value),label=text(Locale.Lookup(value))}
 end
 local administrative={player_id=pid,turn=turn,sequence=sequence,turn_segment=segment,resolutions=array()}
 local result={schema=SCHEMA,player_id=pid,turn=turn,sequence=sequence,turn_segment=segment,
  history_kind='last_results',resolutions=array(),discussions=array()}
 for _,row in ipairs(resolutionRows(native))do
  assert(type(row)=='table','Congress review resolution row absent')
  local def=GameInfo.Resolutions[row.Type];assert(def,'Congress review resolution definition absent')
  local votes=array();local seen={};local a,b=0,0
  for _,selection in ipairs(ordered(row.PlayerSelections,false))do
   assert(type(selection)=='table','Congress review player selection absent')
   local ref,id=reference(selection.PlayerID)
   assert(not seen[id] and #votes<64,'duplicate or excessive resolution voters');seen[id]=true
   local option=reviewInt32(selection.OptionChosen,'OptionChosen')
   local count=reviewInt32(selection.Votes,'Votes')
   if option==1 then a=a+count else b=b+count end
   push(votes,{voter=ref,option=option,votes=count,target=target(row,selection.ResolutionTarget),
               option_label=text(selection.OptionChosenLabel)})
   if ADMINISTRATIVE and id==pid and row.TargetType=='PlayerType'then
    local index=int(tonumber(selection.ResolutionTarget),'own target',-2147483648,2147483647)
    local targetID=index==-1 and -1 or(row.PossibleTargets and tonumber(row.PossibleTargets[index])or index)
    push(administrative.resolutions,{resolution_type=text(def.ResolutionType),target_type='PlayerType',
     option=option,votes=count,target_player_id=int(targetID,'own target player',-2147483648,2147483647)})
   end
  end
  push(result.resolutions,{index=#result.resolutions,resolution_type=text(def.ResolutionType),
   name=text(Locale.Lookup(def.Name)),target_type=text(row.TargetType),
   chosen_option=text(Locale.Lookup(row.ChosenOption)),chosen_label=text(row.ChosenLabel),
   chosen_target=target(row,row.ChosenThing),
   rejected_option=#votes>0 and text(Locale.Lookup(row.RejectedOption))or json_null,
   rejected_label=#votes>0 and text(row.RejectedLabel)or json_null,
   is_new=isNew(row.IsNew),votes_a=a,votes_b=b,tied=a==b,votes=votes})
 end
 for _,category in ipairs(categories(native))do
  local def=category.definition
  for _,row in ipairs(category.rows)do
   assert(type(row)=='table','Congress review discussion absent')
   local votes=array();local seen={};local up,down=0,0
   for _,selection in ipairs(ordered(row.PlayerVotes,false))do
    assert(type(selection)=='table','Congress review discussion vote absent')
    local ref,id=reference(selection.PlayerType)
    assert(not seen[id] and #votes<64,'duplicate or excessive discussion voters');seen[id]=true
    local count=int(selection.Votes,'review signed votes',-2147483648,2147483647)
    if count>0 then up=up+count elseif count<0 then down=down-count end
    push(votes,{voter=ref,votes=count,
     reason=count==0 and id==pid and text(Locale.Lookup('LOC_WC_VOTING_BLOCKER_NOT_INVITED_TO_EMERGENCY_DESC'))or ''})
   end
   local cfg=row.TargetPlayer~=nil and PlayerConfigurations[row.TargetPlayer]or nil
   local name,description,ref
   if cfg then
    ref=reference(row.TargetPlayer)
    -- These two UI strings use the configured target leader name directly.
    name=text(Locale.Lookup(row.Name,cfg:GetLeaderName()))
    description=text(Locale.Lookup(row.Description,cfg:GetLeaderName()))
   else
    ref=json_null;name=text(Locale.Lookup(row.Name));description=text(Locale.Lookup(row.Description))
   end
   push(result.discussions,{index=#result.discussions,category_type=text(def.ProposalType),
    category_name=text(Locale.Lookup(def.Name)),type_name=symbol(row.TypeName),name=name,
    description=description,target=ref,is_new=isNew(row.IsNew),votes_up=up,votes_down=down,
    passed=up>down,votes=votes})
  end
 end
 assert(phase()==segment,'Congress review perspective changed during read')
 return result,administrative
end
'''


def source(player_id, turn, sequence, *, expected_scope=None, admitted_segment=None, administrative=False):
    if type(administrative) is not bool:
        raise ValueError('Congress administrative review requires an exact Boolean')
    uint(player_id, 'player', 63)
    uint(turn, 'turn', 0x7fffffff)
    uint(sequence, 'sequence', 0xffffffff)
    if admitted_segment is not None: _integer(admitted_segment, 0xffffffff)
    expected = 'nil'
    if expected_scope is not None:
        validate_scope(expected_scope)
        if admitted_segment is not None and admitted_segment != expected_scope['segment']:
            raise ValueError('Congress review expected and admitted phases differ')
        admitted_segment = expected_scope['segment']
        expected = '{segment=%d,players=array({%s}),leader_ids=array({%s})}' % (
            expected_scope['segment'], ','.join(map(str, expected_scope['players'])),
            ','.join(map(str, expected_scope['leader_ids'])))
    ending = (('\nlocal public,private=reviewSnapshot(' + expected + ');return encode({public=public,private=private})\n')
              if administrative else '\nreturn encode((reviewSnapshot(' + expected + ')))\n')
    return (f'local pid,turn,sequence={player_id},{turn},{sequence}\n'
            f'local SCHEMA={literal(SCHEMA)}\n'
            f'local ADMINISTRATIVE={str(administrative).lower()}\n'
            f'local ADMITTED_SEGMENT={admitted_segment if admitted_segment is not None else "nil"}\n').encode() + LUA.encode() + ending.encode()


def scope_source(player_id, turn, sequence, *, admitted_segment=None):
    # Reuse exactly the same scope traversal as the final projection guard.
    chunk = source(player_id, turn, sequence, admitted_segment=admitted_segment)
    return chunk[:chunk.rindex(b'\nreturn encode((reviewSnapshot(')] + b'\nreturn encode(reviewScope())\n'


def validate_scope(value):
    _fields(value, 'segment players leader_ids')
    _integer(value['segment'], 0xffffffff)
    for name in ('players', 'leader_ids'):
        rows = _rows(value[name], 64)
        for pid in rows: _integer(pid, 63)
        if rows != sorted(set(rows)):
            raise ValueError('Congress review scope is not unique and ordered')
    if not set(value['leader_ids']) <= set(value['players']):
        raise ValueError('Congress review leader scope exceeds referenced players')
    return value


def parse_scope(raw):
    if type(raw) is not bytes or len(raw) > 4096:
        raise ValueError('Unbounded Congress review configuration scope')
    return validate_scope(json.loads(raw, object_pairs_hook=_unique))


def _unique(rows):
    result = {}
    for key, value in rows:
        if key in result: raise ValueError('Duplicate Congress review wire key')
        result[key] = value
    return result


def _fields(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError('Congress review object fields differ')


def _integer(value, maximum=0x7fffffff, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Congress review integer outside bounds')


def _rows(value, maximum=4096):
    if type(value) is not list or len(value) > maximum:
        raise ValueError('Congress review rows outside bounds')
    return value


def parse(raw, player_id, turn, sequence):
    """Validate the independent staging projection, without asserting freshness."""
    uint(player_id, 'player', 63); uint(turn, 'turn', 0x7fffffff); uint(sequence, 'sequence', 0xffffffff)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded Congress review wire')

    value = json.loads(raw, object_pairs_hook=_unique)
    contract.validate_catalogue(value, player_id, turn, sequence)
    return value


def parse_envelope(raw, player_id, turn, sequence):
    """Validate administrative own-vote targets, never admitted to actor output."""
    uint(player_id, 'player', 63); uint(turn, 'turn', 0x7fffffff); uint(sequence, 'sequence', 0xffffffff)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded Congress administrative review wire')
    envelope = json.loads(raw, object_pairs_hook=_unique)
    _fields(envelope, 'public private')
    public, private = envelope['public'], envelope['private']
    contract.validate_catalogue(public, player_id, turn, sequence)
    _fields(private, 'player_id turn sequence turn_segment resolutions')
    for key in ('player_id', 'turn', 'sequence', 'turn_segment'):
        if type(private[key]) is not int or private[key] != public[key]:
            raise ValueError('Congress administrative result crossed its public identity')
    expected = []
    for row in public['resolutions']:
        if row['target_type'] != 'PlayerType': continue
        own = [v for v in row['votes'] if v['voter']['player_id'] == player_id]
        if len(own) > 1: raise ValueError('Congress administrative own vote is ambiguous')
        if own: expected.append((row, own[0]))
    rows = _rows(private['resolutions'])
    if len(rows) != len(expected):
        raise ValueError('Congress administrative result contains non-own or missing votes')
    for raw, (row, vote) in zip(rows, expected):
        _fields(raw, 'resolution_type target_type option votes target_player_id')
        if (raw['resolution_type'] != row['resolution_type'] or raw['target_type'] != 'PlayerType'
                or type(raw['option']) is not int or raw['option'] != vote['option']
                or type(raw['votes']) is not int or raw['votes'] != vote['votes']):
            raise ValueError('Congress administrative vote differs from its public projection')
        _integer(raw['target_player_id'], minimum=-0x80000000)
        visible = vote['target']['player_id']
        if visible is not None and raw['target_player_id'] != visible:
            raise ValueError('Congress administrative target differs from its visible identity')
    return envelope


def source_dependencies(*, execution_image):
    from civ6_host.runtime.xp2_world_congress_source import source_dependencies as shared
    from civ6_host.runtime.configuration_profiles import _source
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    result = shared(execution_image=execution_image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.congress-review-source.v2'
            or proof['shared_prefix']['sha256'] != SHARED_PREFIX_SHA256):
        raise ValueError('Congress review source proof differs')
    result[str(resolve_path(resource_root() / SOURCE[0]).resolve())] = SOURCE[1]
    for row in [proof['parent'], *proof['files'], proof['provider_implementation'], proof['topology_reference']]:
        path = resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Congress review installed caller changed')
        result[str(path.resolve())] = row['sha256']
    private_proof = _source(PRIVATE_SOURCE)
    if (private_proof['schema'] != 'civ6-host.congress-private-own-targets-source.v1'
            or private_proof['static_only'] is not True
            or private_proof['native_execution'] is not False):
        raise ValueError('Congress administrative own-target source proof differs')
    result[str(resolve_path(resource_root() / PRIVATE_SOURCE[0]).resolve())] = PRIVATE_SOURCE[1]
    for row in [*private_proof['parents'], *private_proof['files']]:
        path = resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Congress administrative own-target caller changed')
        result[str(path.resolve())] = row['sha256']
    numeric = _source(NUMERIC_SOURCE)
    if (numeric['schema'] != 'civ6-host.xp2-congress-review-signed-option-votes.source.v1'
            or numeric['scope'] != dict(static_only=True,native_execution=False,process_memory_read=False,
                                       runtime_modified=False,new_gameplay_rule=False)
            or numeric['parents']['public_review_admission']['sha256'] != SOURCE[1]
            or numeric['parents']['private_targets']['sha256'] != PRIVATE_SOURCE[1]
            or any(tuple(numeric['fields'][key]['domain']) != (-0x80000000,0x7fffffff)
                   or numeric['fields'][key]['native_lua_type'] != 'number representing signed int32 exactly'
                   for key in ('PlayerSelections.OptionChosen','PlayerSelections.Votes'))):
        raise ValueError('Congress review signed numeric source proof differs')
    result[str(resolve_path(resource_root() / NUMERIC_SOURCE[0]).resolve())] = NUMERIC_SOURCE[1]
    for row in [*numeric['parents'].values(),*numeric['images'].values(),numeric['ui']]:
        path = resolve_path(Path(row['path']))
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Congress review signed numeric source dependency changed')
        result[str(path.resolve())] = row['sha256']
    return result


def admission_allowed(envelope, player_id, turn, sequence):
    """Consume a previously validated, owner-bound active Congress envelope.

    The owner must check that exact record before and after query, with no
    intervening action. This only validates the fields this admission consumes.
    """
    if type(envelope) is not dict or set(envelope) != {'public', 'private'}:
        raise ValueError('Congress review requires the exact Congress envelope')
    public, private = envelope['public'], envelope['private']
    if type(public) is not dict or type(private) is not dict or type(private.get('popup')) is not dict:
        raise ValueError('Congress review admission is malformed')
    for key, expected in (('player_id', player_id), ('turn', turn), ('sequence', sequence)):
        if type(public.get(key)) is not int or public[key] != expected:
            raise ValueError('Congress review admission crossed observation identity')
    _integer(public.get('turn_segment'), 0xffffffff)
    if public.get('stage') not in ('ordinary', 'regular', 'special', 'resolving'):
        raise ValueError('Congress review admission stage is absent')
    popup = private['popup']
    for row, key in ((public, 'paused'), (public, 'local_alive'), (popup, 'capability')):
        if type(row.get(key)) is not bool:
            raise ValueError('Congress review admission Boolean is absent')
    for key in ('current_era', 'initial_era'): _integer(popup.get(key), minimum=-0x80000000)
    return (public['stage'] == 'ordinary' and not public['paused'] and public['local_alive']
            and popup['capability'] and popup['current_era'] >= popup['initial_era'])


def query(prefix, player_id, turn, sequence, *, backend, environment, admission, administrative=False, projection=None):
    """Read the fixed Congress projection using its source-qualified provider.

    ``environment`` is the trusted review_environment module owned by the host,
    never actor input. Scope IDs stay private. The second getter result is
    projected only while its referenced-player/leader scope and phase agree.
    Historical Review remains the default; only the fixed active-effects
    module can select the alternate public projection.
    """
    if type(administrative) is not bool:
        raise ValueError('Congress administrative review requires an exact Boolean')
    uint(player_id, 'player', 63); uint(turn, 'turn', 0x7fffffff); uint(sequence, 'sequence', 0xffffffff)
    admission_gate,scope_builder,result_builder=admission_allowed,scope_source,source
    result_parser=parse_envelope if administrative else parse
    scope_name,result_name=b'@player_congress_review_configuration_scope',b'@player_world_congress_review'
    if projection is not None:
        from . import native_world_congress_active_effects as active_effects
        if projection is not active_effects or administrative:
            raise ValueError('Congress query projection is not its fixed public active-effects reader')
        admission_gate,scope_builder,result_builder=(active_effects.admission_allowed,
            active_effects.scope_source,active_effects.source)
        result_parser=active_effects.parse
        scope_name,result_name=b'@player_congress_active_effects_configuration_scope',b'@player_world_congress_active_effects'
    if not admission_gate(admission, player_id, turn, sequence): return None
    chunk = scope_builder(player_id, turn, sequence, admitted_segment=admission['public']['turn_segment'])
    if not callable(getattr(environment, 'read', None)) or not callable(getattr(environment, 'lua_bindings', None)):
        raise ValueError('Congress review requires its qualified configuration provider')
    from civ6_host.runtime.xp2_congress_configuration import attach_namespaces
    attach_namespaces(prefix, backend)
    raw_scope = prefix.runtime.evaluate_text(prefix.ui_child, chunk,
        scope_name, capacity=4097)
    scoped = parse_scope(raw_scope)
    preamble = environment.lua_bindings(environment.read(backend, scoped['players'], leader_ids=scoped['leader_ids']))
    if type(preamble) is not bytes or not preamble or len(preamble) > LIMIT:
        raise ValueError('Congress review environment preamble is invalid')
    raw = prefix.runtime.evaluate_text(prefix.ui_child,
        preamble + result_builder(player_id, turn, sequence, expected_scope=scoped, administrative=administrative),
        result_name, capacity=LIMIT + 1)
    result = result_parser(raw, player_id, turn, sequence)
    public = result['public'] if administrative else result
    if public['turn_segment'] != scoped['segment']:
        raise ValueError('Congress review phase changed across configuration read')
    return result

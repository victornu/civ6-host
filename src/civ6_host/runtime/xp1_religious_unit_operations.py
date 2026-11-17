"""Explicit religious UnitOperations through the installed saved expansion sessions."""

from copy import deepcopy
from hashlib import sha256
from struct import Struct

from civ6_host.contracts import religious_unit_operations as contract

from . import xp1_religious_unit_operations_source as source
from .execution_images import _PROFILE
from .native import native_event_15c35863 as added
from .native.native_player_observation import observe_player


SOURCE = source.SOURCE
XP2_SOURCE = source.XP2_SOURCE
REFUSED = 'native_religious_unit_operation_can_start_false'
UNCONFIRMED = 'native_religious_unit_operation_processed_effect_unconfirmed'
OFFER_CHANGED = 'native_religious_unit_operation_offer_changed'
KINDS = contract.KINDS
_MAX_WIRE = 1024*1024
_ARCHIVE = Struct('<IHH5I')
_EVENT_HEADER = Struct('<III')
_DESCRIPTOR = Struct('<HHI')
_UNIT_FIELDS = ('unit_id','x','y','moves_remaining','religion_type','spread_charges')
_NEED_ENTITLEMENT = 'evangelize_belief'
_INQUISITION = 'launch_inquisition'
_COMMON_LUA = br"""
local function integer(v,lo,hi,label)
 assert(type(v)=='number' and v%1==0 and v>=lo and v<=hi,'invalid religious operation '..label)
 return v
end
local function boolean(v,label)
 assert(type(v)=='boolean','invalid religious operation '..label)
 return v
end
local function ready()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
        Game.GetCurrentGameTurn()==turn,'stale religious unit perspective')
 assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands unavailable')
 local player=Players[pid]
 assert(player and player:IsAlive()==true and player:IsTurnActive()==true and
        player:IsTurnActiveComplete()==true,'religious unit actor is not ready')
 return player
end
local function readUnit(unit)
 assert(unit:GetOwner()==pid,'foreign religious unit')
 local moves=unit:GetMovesRemaining()
 assert(type(moves)=='number','religious unit moves missing')
 integer(moves*256,-2147483648,2147483647,'moves')
 return {unit=unit,
  id=integer(unit:GetID(),0,4294967295,'id'),
  x=integer(unit:GetX(),0,16383,'x'),y=integer(unit:GetY(),0,16383,'y'), moves=moves,
  religion=integer(unit:GetReligionType(),-2147483648,2147483647,'religion'),
  charges=integer(unit:GetSpreadCharges(),-2147483648,2147483647,'spread charges')}
end
local function definition(kind)
 local spec=assert(operations[kind],'unbound religious operation')
 local op=assert(GameInfo.UnitOperations[spec[1]],'missing religious operation')
 local signed=integer(op.Hash,-2147483648,4294967295,'hash')
 local bits=signed<0 and signed+4294967296 or signed
 assert(bits==spec[2] and op.OperationType==spec[1] and op.InterfaceMode==nil,
        'installed religious operation changed')
 integer(op.Index,0,2047,'operation index')
 boolean(op.VisibleInUI,'operation UI visibility')
 return op
end
local function visible(unit,moves,op)
 return moves>0 and op.VisibleInUI and boolean(
  UnitManager.CanStartOperation(unit,op.Hash,nil,true),'operation visibility')
end
local function available(unit,op)
 -- Omit argument 5 to obtain the same native Boolean without the result map.
 return boolean(UnitManager.CanStartOperation(unit,op.Hash,nil,false),'operation availability')
end
"""
_CATALOG_LUA = br"""
local player=ready()
local religion=assert(player:GetReligion(),'actor religion unavailable')
local inquisition=boolean(religion:HasLaunchedInquisition(),'inquisition flag')
local defs={}
for i=1,#operations do defs[i]=definition(i) end
local rows,seen={},{}
for _,unit in player:GetUnits():Members() do
 assert(#rows<4096,'religious unit roster exceeds bound')
 local u=readUnit(unit)
 assert(not seen[u.id],'duplicate religious unit id')
 seen[u.id]=true
 local fields={
  string.format('%.0f',u.id),string.format('%.0f',u.x),string.format('%.0f',u.y),
  string.format('%.17g',u.moves),string.format('%.0f',u.religion),string.format('%.0f',u.charges)
 }
 for i,op in ipairs(defs) do
  if visible(unit,u.moves,op) then
   local allowed=available(unit,op)
   fields[#fields+1]=string.format('%.0f',i)..':'..(allowed and '1' or '0')
  end
 end
 rows[#rows+1]={id=u.id,wire=table.concat(fields,'|')}
end
table.sort(rows,function(a,b) return a.id<b.id end)
local out={inquisition and '1' or '0'}
for _,u in ipairs(rows) do out[#out+1]=u.wire end
ready()
assert(religion:HasLaunchedInquisition()==inquisition,
       'religious unit catalogue changed during observation')
return table.concat(out,'\n')
"""
_REQUEST_LUA = br"""
local player=ready()
local selected=nil
local count=0
for _,unit in player:GetUnits():Members() do
 count=count+1
 assert(count<=4096 and unit:GetOwner()==pid,'oversized or foreign religious unit roster')
 if unit:GetID()==wanted[1] then
  assert(not selected,'duplicate religious unit actor')
  selected=readUnit(unit)
 end
end
assert(selected and selected.x==wanted[2] and selected.y==wanted[3] and
       selected.moves==wanted[4] and selected.religion==wanted[5] and selected.charges==wanted[6],
       'religious unit choice changed')
local op=definition(operation)
if expected_ordinal~=nil then
 assert(op.Index==expected_ordinal,'Gathering Storm religious operation GameInfo index differs')
end
ready()
assert(visible(selected.unit,selected.moves,op),'religious unit operation no longer visible')
if not available(selected.unit,op) then return 'refused' end
UnitManager.RequestOperation(selected.unit,op.Hash)
return 'submitted|'..string.format('%.0f',op.Index)
"""


def _identity(observation):
    if type(observation) is not dict:
        raise ValueError('Religious operation requires the actor observation')
    pid,turn = observation.get('player_id'),observation.get('turn')
    if type(pid) is not int or not 0<=pid<64 or type(turn) is not int or not 0<=turn<=0xffffffff:
        raise ValueError('Invalid religious operation actor or turn')
    return pid,turn


def _preamble(pid,turn):
    _identity(dict(player_id=pid,turn=turn))
    entries = ','.join('{"%s",%d}' % source.OPERATIONS[kind][:2] for kind in KINDS)
    return f'local pid,turn={pid},{turn}\nlocal operations={{{entries}}}\n'.encode('ascii')+_COMMON_LUA


def catalog_source(pid,turn):
    return _preamble(pid,turn)+_CATALOG_LUA


def _int(cell,low,high):
    if type(cell) is not bytes or not 0<len(cell)<=11:
        raise ValueError('Invalid religious operation transport integer')
    value = int(cell)
    if str(value).encode('ascii') != cell or not low<=value<=high:
        raise ValueError('Noncanonical religious operation transport integer')
    return value


def parse_catalog(raw,pid,turn):
    _identity(dict(player_id=pid,turn=turn))
    if type(raw) is not bytes or not 0<len(raw)<=_MAX_WIRE:
        raise ValueError('Invalid bounded religious unit response')
    flag,*rows = raw.split(b'\n')
    if flag not in (b'0',b'1') or len(rows)>4096:
        raise ValueError('Invalid religious unit inquisition flag or roster bound')
    units = []
    for line in rows:
        uid,x,y,moves,rtype,charges,*operations = line.split(b'|')
        values = (_int(uid,0,0xffffffff),_int(x,0,16383),_int(y,0,16383),
            float(moves.decode('ascii')),_int(rtype,-2**31,2**31-1),_int(charges,-2**31,2**31-1))
        parsed = []
        for token in operations:
            index,available = token.split(b':')
            if available not in (b'0',b'1'):
                raise ValueError('Invalid religious operation availability Boolean')
            parsed.append(dict(operation=KINDS[_int(index,1,len(KINDS))-1],visible=True,
                               available=available==b'1'))
        row = dict(zip(_UNIT_FIELDS,values))
        row['operations'] = parsed
        units.append(row)
    result = dict(player_id=pid,current_game_turn=turn,inquisition_started=flag==b'1',units=units)
    contract.project(result,pid,turn)
    return result


def _bind(saved,*,action=False,borrowed_player=None):
    if borrowed_player is not None:
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, borrowed_player)
    elif action:
        saved._check_active()
    else:
        saved._check_query()
    prefix = saved.prefix
    image = getattr(prefix.core,'_civ6_host_execution_image',None)
    source.source_for(image)
    xp1 = getattr(saved,'xp1_religious_unit_operations',False)
    xp2 = getattr(saved,'xp2_religious_unit_operations',False)
    if (xp1 is not (image is not _PROFILE) or xp2 is not (image is _PROFILE)):
        raise ValueError('Religious unit operations need their explicit saved engine owner')
    source.bind_prefix(prefix,action=action)
    if prefix.ui_child is None or prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Religious unit operations need a published actor and drained input')
    return prefix


def _catalogue(prefix,observation):
    pid,turn = _identity(observation)
    raw = prefix.runtime.evaluate_text(prefix.ui_child,catalog_source(pid,turn),
        b'@explicit_xp1_religious_unit_operations',capacity=_MAX_WIRE)
    result = parse_catalog(raw,pid,turn)
    contract.project(result,pid,turn,observation=observation)
    return result


def catalogue(saved,observation):
    value = _catalogue(_bind(saved),observation)
    saved.explicit_religious_unit_operations = deepcopy(value)
    return value


def borrowed_catalogue(saved, observation):
    pid, turn = _identity(observation)
    value = _catalogue(_bind(saved, borrowed_player=pid), observation)
    return contract.project(value, pid, turn, observation=observation)


def actions(value):
    if value is None:
        return []
    return contract.actions(contract.project(value,value['player_id'],value['current_game_turn']))


def request_source(selected,action,pid,turn,*,expected_ordinal=None):
    contract.validate_action(action)
    if _unit_action(selected,action['kind']) != action:
        raise ValueError('Religious request differs from its exact selected unit')
    contract.project(dict(player_id=pid,current_game_turn=turn,inquisition_started=False,
                          units=[selected]),pid,turn)
    numbers = ','.join(str(selected[field]) for field in _UNIT_FIELDS)
    index = KINDS.index(action['kind'])+1
    if expected_ordinal is not None and (type(expected_ordinal) is not int or not 0<=expected_ordinal<=2047):
        raise ValueError('Invalid religious operation ordinal')
    expected = b'local expected_ordinal=nil\n' if expected_ordinal is None else f'local expected_ordinal={expected_ordinal}\n'.encode('ascii')
    return _preamble(pid,turn)+expected+f'local wanted={{{numbers}}};local operation={index}\n'.encode('ascii')+_REQUEST_LUA


def verify_archive(raw,pid,uid,expected_index):
    if type(raw) is not bytes or len(raw)!=_ARCHIVE.size:
        raise RuntimeError('Religious unit request archive must contain native empty parameters')
    kind,owner,typ,unit,index,target,flags,count = _ARCHIVE.unpack(raw)
    if ((kind,owner,typ,unit,index) != (source.ARCHIVE_KIND,pid,1,uid,expected_index)
            or not 0<=index<=2047 or (target,flags,count)!=(0xffffffff,0,0)):
        raise RuntimeError('Religious unit request archive differs from the selected native operation')
    return dict(archive_sha256=sha256(raw).hexdigest(),size_bytes=len(raw),
                operation_index=index,parameters={})


def _operation_added(records,consumed_before,pid,uid,index):
    descriptor = _DESCRIPTOR.pack(pid,1,uid)
    fields = added.encode_fields(added.EventFields(0,index,1,descriptor))
    result = []
    for seq,record in enumerate(records,consumed_before+1):
        if type(record) is not bytes or len(record)<84:
            raise RuntimeError('Malformed religious operation FIFO record')
        size,typ,actual_seq = _EVENT_HEADER.unpack_from(record)
        if (size,actual_seq) != (len(record),seq):
            raise RuntimeError('Religious operation FIFO record is out of order')
        if typ != added.RECORD_TYPE:
            continue
        expected = added.encode_queue_record(seq,fields,blob_contents=descriptor,
            padding_policy='headless-zero-initialization')
        if record == expected:
            result.append(seq)
        elif record[24:32] == descriptor or record[88:96] == descriptor:
            raise RuntimeError('Religious UnitOperationAdded identifies a different command')
    if len(result)>1:
        raise RuntimeError('Religious operation appeared more than once in the delivery FIFO')
    return result[0] if result else None


def _unit(observation,unit_id):
    matches = [u for u in observation['units'] if u['id']==unit_id]
    if len(matches)>1:
        raise RuntimeError('Duplicate religious actor in its public observation')
    return matches[0] if matches else None


def _unit_action(row,kind):
    return dict(kind=kind,unit_id=row['unit_id'],x=row['x'],y=row['y'])


def confirmation(receipt,action,before,after):
    contract.validate_action(action)
    if _identity(before)!=_identity(after):
        raise RuntimeError('Religious operation crossed player or turn')
    kind,uid = action['kind'],action['unit_id']
    archive = receipt['archive']
    digest,index = archive['archive_sha256'],archive['operation_index']
    if (type(archive) is not dict or set(archive) != {'archive_sha256','size_bytes','operation_index','parameters'}
            or type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)
            or type(archive['size_bytes']) is not int or archive['size_bytes']!=_ARCHIVE.size
            or type(archive['parameters']) is not dict or archive['parameters']
            or type(index) is not int or not 0<=index<=2047
            or type(receipt['operation_hash']) is not int or receipt['operation_hash'] != source.OPERATIONS[kind][1]):
        raise RuntimeError('Invalid religious operation archive receipt')
    start,end,seq = (receipt[key] for key in ('consumed_before','consumed_after','operation_added_sequence'))
    if (type(start) is not int or type(end) is not int or not 0<=start<=end<=0xffffffff
            or seq is not None and (type(seq) is not int or not start<seq<=end)):
        raise RuntimeError('Invalid religious operation receipt FIFO boundary')
    if (type(receipt['inquisition_started_before']) is not bool
            or type(receipt['inquisition_started_after']) is not bool):
        raise RuntimeError('Invalid religious operation inquisition receipt')
    old,new = receipt['unit_before'],receipt['unit_after']
    for row,observation,flag in ((old,before,receipt['inquisition_started_before']),
                                 (new,after,receipt['inquisition_started_after'])):
        public = _unit(observation,uid)
        if (row is None) != (public is None):
            raise RuntimeError('Religious unit receipt and actor roster differ')
        if row is not None:
            pid,turn = _identity(observation)
            subset = dict(observation,units=[public])
            contract.project(dict(player_id=pid,current_game_turn=turn,inquisition_started=flag,
                                  units=[row]),pid,turn,observation=subset)
    if old is None or _unit_action(old,kind)!=action or not any(
            op['operation']==kind and op['available'] for op in old['operations']):
        raise RuntimeError('Religious operation receipt lost the selected original unit')
    earned_before,earned_after = receipt['beliefs_earned_before'],receipt['beliefs_earned_after']
    if kind==_NEED_ENTITLEMENT:
        if any(type(v) is not int or not -2**31<=v<2**31 for v in (earned_before,earned_after)):
            raise RuntimeError('Religious receipt lost the actual belief entitlement')
        effect = new is None and earned_after==earned_before+1
    elif earned_before is not None or earned_after is not None:
        raise RuntimeError('Non-evangelization receipt carries an unrelated entitlement')
    elif kind==_INQUISITION:
        effect = not receipt['inquisition_started_before'] and receipt['inquisition_started_after']
    else:
        effect = new is None or new['spread_charges']<old['spread_charges']
    return seq is not None and effect


def _own_entitlement(prefix,pid,turn):
    # The exact installed PlayerReligion binding is checked by shared.bind_prefix.
    # Read only its signed cache scalar, including when the holy city was captured.
    query = _preamble(pid,turn)+br"""
local player=ready()
local religion=assert(player:GetReligion(),'actor religion unavailable')
local earned=integer(religion:GetNumBeliefsEarned(),-2147483648,2147483647,'beliefs earned')
ready()
return string.format('%.0f',earned)
"""
    raw = prefix.runtime.evaluate_text(prefix.ui_child,query,
        b'@explicit_xp1_religious_unit_entitlement',capacity=16)
    return _int(raw,-2**31,2**31-1)


def _selected(state,uid):
    return next((r for r in state['units'] if r['unit_id']==uid),None)


def apply(saved,action,before,*,borrowed_offer=None):
    contract.validate_action(action)
    pid,turn = _identity(before)
    borrowed = borrowed_offer is not None
    prefix = _bind(saved,action=True,borrowed_player=pid if borrowed else None)
    image = prefix.core._civ6_host_execution_image
    source_sha = source.source_for(image)[1]
    kind,uid = action['kind'],action['unit_id']
    if borrowed:
        contract.validate(borrowed_offer,pid,turn)
        retained = dict(player_id=pid,current_game_turn=turn,
                        inquisition_started=borrowed_offer['inquisition_started'],units=borrowed_offer['units'])
    else:
        retained = getattr(saved,'explicit_religious_unit_operations',None)
    if (retained is None or (retained['player_id'],retained['current_game_turn'])!=(pid,turn)
            or action not in actions(retained)):
        raise RuntimeError('Religious unit choice was not explicitly offered')
    fresh = _catalogue(prefix,before)
    prior,selected = _selected(retained,uid),_selected(fresh,uid)
    changed = (selected is None or any(selected[k]!=prior[k] for k in _UNIT_FIELDS)
               or fresh['inquisition_started'] is not retained['inquisition_started'])
    if borrowed and (changed or action not in actions(fresh)):
        return dict(status='refused',observation=deepcopy(before),action=deepcopy(action),
                    source_sha256=source_sha,refusal_code=OFFER_CHANGED)
    if changed:
        raise RuntimeError('Religious unit choice is stale')
    earned_before = _own_entitlement(prefix,pid,turn) if kind==_NEED_ENTITLEMENT else None
    expected = None
    if image is _PROFILE:
        reference = prefix.backend.captured_bundle.reference
        expected = source.xp2.expected_ordinal(reference,kind)
    reply = prefix.runtime.evaluate_text(prefix.ui_child,
        request_source(selected,action,pid,turn,expected_ordinal=expected),
        b'@explicit_xp1_religious_unit_request',capacity=32)
    if reply == b'refused':
        if prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Refused religious unit operation queued native work')
        return dict(status='refused',observation=deepcopy(before),action=deepcopy(action),
                    source_sha256=source_sha,refusal_code=REFUSED,
                    request=dict(can_start=False,request_invoked=False))
    if not reply.startswith(b'submitted|') or len(prefix.actions.pending)!=1:
        raise RuntimeError('Religious unit action did not enqueue exactly one native archive')
    index = _int(reply.split(b'|',1)[1],0,2047)
    if expected is not None and index != expected:
        raise RuntimeError('Gathering Storm religious operation GameInfo index differs')
    archive = verify_archive(prefix.actions.pending[0],pid,uid,index)
    start = prefix.deferred_events.consumed_count
    prefix.actions.deliver_one()
    records = tuple(prefix.deferred_events.pending)
    seq = _operation_added(records,start,pid,uid,index)
    prefix.deferred_events.drain_empty_receivers()
    end = prefix.deferred_events.consumed_count
    if prefix.deferred_events.pending or end-start<len(records):
        raise RuntimeError('Religious unit delivery did not consume the native FIFO')
    prefix.view_publisher.publish()
    prefix.actions.require_empty_native_queue()
    after = observe_player(prefix.runtime,prefix.ui_child,pid)
    if _identity(after)!=(pid,turn):
        raise RuntimeError('Religious unit operation crossed actor or turn')
    state = _catalogue(prefix,after)
    earned_after = _own_entitlement(prefix,pid,turn) if kind==_NEED_ENTITLEMENT else None
    receipt = dict(archive=archive,operation_hash=source.OPERATIONS[kind][1],
        operation_added_sequence=seq,consumed_before=start,consumed_after=end,
        unit_before=deepcopy(prior),unit_after=deepcopy(_selected(state,uid)),
        beliefs_earned_before=earned_before,beliefs_earned_after=earned_after,
        inquisition_started_before=fresh['inquisition_started'],inquisition_started_after=state['inquisition_started'])
    confirmed = confirmation(receipt,action,before,after)
    result = dict(status='completed' if confirmed else 'submitted',observation=after,
                  action=deepcopy(action),source_sha256=source_sha,receipt=receipt)
    if not confirmed:
        result['refusal_code'] = UNCONFIRMED
    if not borrowed:
        saved.explicit_religious_unit_operations = deepcopy(state)
    prefix.emit('official_explicit_religious_unit_operation',**result)
    return result


require_actions = source.require_actions
source_dependencies = source.source_dependencies
supports = source.supports
source_for = source.source_for

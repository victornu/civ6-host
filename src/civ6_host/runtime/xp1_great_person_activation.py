"""Explicit own-unit GP command activation on the retained saved host."""
from copy import deepcopy
from hashlib import sha256
import struct

from civ6_host.contracts import great_person_activation as contract
from . import xp1_great_person_activation_source as source
from .native.native_player_observation import observe_player
from .configuration_profiles import XP2_CORE_SHA256

SOURCE=source.SOURCE
REFUSED='native_great_person_activation_can_start_false'
UNCONFIRMED='native_great_person_activation_processed_effect_unconfirmed'
OFFER_CHANGED='native_great_person_activation_offer_changed'
UNAVAILABLE='native_great_person_activation_acting_boundary_unavailable'
LIMIT=1024*1024

_LUA=br'''
local function integer(v,label,lo,hi)
 assert(type(v)=='number' and v%1==0 and v>=lo and v<=hi,'invalid GP '..label);return v
end
local function boolean(v,label) assert(type(v)=='boolean','invalid GP '..label);return v end
local function n(v) return string.format('%.0f',v) end
local function ready()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
        'stale GP perspective')
 assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands unavailable')
 local p=Players[pid]
 assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,
        'GP player is not ready')
 return p
end
local player=ready()
local command=assert(GameInfo.UnitCommands.UNITCOMMAND_ACTIVATE_GREAT_PERSON,'GP command missing')
assert(command.Hash==374670040,'GP command hash differs')
assert(command.InterfaceMode==nil or DB.MakeHash(command.InterfaceMode)==InterfaceModeTypes.NONE,'GP command became modal')
boolean(command.VisibleInUI,'command visibility')
local function snapshot()
 local out,seen,count={},{},0
 for _,u in player:GetUnits():Members() do
  count=count+1;assert(count<=4096 and u:GetOwner()==pid,'unbounded or foreign GP roster')
  local id=integer(u:GetID(),'unit',0,4294967295)
  assert(not seen[id],'duplicate own GP unit');seen[id]=true
  local gp=u:GetGreatPerson()
  if gp then
   local individual=integer(gp:GetIndividual(),'individual',-2147483648,2147483647)
   local class=integer(gp:GetClass(),'class',-2147483648,2147483647)
   -- Non-GP units have no individual. No Prophet/class/movement rule is added.
   if individual>=0 then
    integer(class,'GP class',0,2147483647)
    assert(GameInfo.GreatPersonIndividuals[individual] and GameInfo.GreatPersonClasses[class],
           'GP identity missing from own official definitions')
    local x=integer(u:GetX(),'x',0,16383);local y=integer(u:GetY(),'y',0,16383)
    local charges=integer(gp:GetActionCharges(),'charges',-2147483648,2147483647)
    local visible=boolean(UnitManager.CanStartCommand(u,command.Hash,true),'native visibility')
    local available=boolean(UnitManager.CanStartCommand(u,command.Hash,false,true),'native availability')
    assert(command.VisibleInUI,'GP command is outside the retained visible UI definition')
    out[#out+1]={unit=u,unit_id=id,x=x,y=y,individual_index=individual,class_index=class,charges=charges,
       visible=visible,available=available,
       wire=table.concat({n(id),n(x),n(y),n(individual),n(class),n(charges),visible and '1' or '0',available and '1' or '0'},'|')}
   end
  end
 end
 table.sort(out,function(a,b)return a.unit_id<b.unit_id end);ready();return out
end
'''


def _identity(obs):
    if type(obs) is not dict:
        raise ValueError('Great Person activation requires its actor observation')
    pid,turn=obs.get('player_id'),obs.get('turn')
    if type(pid) is not int or not 0<=pid<64 or type(turn) is not int or not 0<=turn<=0xffffffff:
        raise ValueError('Great Person actor identity differs')
    return pid,turn


def _preamble(pid,turn):
    _identity(dict(player_id=pid,turn=turn))
    return f'local pid,turn={pid},{turn}\n'.encode('ascii')+_LUA


def catalog_source(pid,turn):
    return _preamble(pid,turn)+br'''
local rows={};for _,row in ipairs(snapshot()) do rows[#rows+1]=row.wire end
return table.concat(rows,'\n')
'''


def _int(raw,low,high):
    value=int(raw)
    if str(value).encode('ascii')!=raw or not low<=value<=high:
        raise ValueError('Noncanonical Great Person catalogue integer')
    return value


def parse_catalog(raw,pid,turn):
    _identity(dict(player_id=pid,turn=turn))
    if type(raw) is not bytes or len(raw)>LIMIT:
        raise ValueError('Invalid Great Person catalogue transport')
    units=[]
    for line in raw.splitlines():
        cells=line.split(b'|')
        if len(cells)!=8 or cells[6] not in (b'0',b'1') or cells[7] not in (b'0',b'1'):
            raise ValueError('Malformed Great Person unit row')
        domains=((0,0xffffffff),(0,16383),(0,16383),(0,0x7fffffff),(0,0x7fffffff),(-0x80000000,0x7fffffff))
        values=[_int(cell,*bounds) for cell,bounds in zip(cells[:6],domains)]
        row=dict(zip(('unit_id','x','y','individual_index','class_index','charges'),values))
        row.update(visible=cells[6]==b'1',available=cells[7]==b'1')
        if len(units)>=4096 or units and row['unit_id']<=units[-1]['unit_id']:
            raise ValueError('Great Person units must be bounded and uniquely ordered')
        units.append(row)
    return dict(player_id=pid,current_game_turn=turn,operation=source.COMMAND_HASH,units=units)


def selected_source(saved):
    if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256:
        from . import xp2_great_person_activation_source
        return xp2_great_person_activation_source
    return source


def enabled(saved):
    flag = ('xp2_great_person_activation' if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
            else 'xp1_great_person_activation')
    return getattr(saved, flag, False) is True


def _work_source(profile):
    if profile is source:
        from .xp1_great_work_source import UNIT_PRODUCER_SOURCE
        return UNIT_PRODUCER_SOURCE
    return profile.WORK_SOURCE


def _bind(saved, *, action=False, borrowed_player=None):
    if borrowed_player is not None:
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, borrowed_player)
    elif action:
        saved._check_active()
    else:
        saved._check_query()
    if not enabled(saved):
        raise ValueError('Great Person activation requires its explicit saved owner')
    selected_source(saved).bind_prefix(saved.prefix,action=action)
    if saved.prefix.ui_child is None or saved.prefix.actions.pending or saved.prefix.deferred_events.pending:
        raise RuntimeError('Great Person activation requires its published actor and drained queues')
    return saved.prefix


def _catalogue(prefix,observation):
    pid,turn=_identity(observation)
    raw=prefix.runtime.evaluate_text(prefix.ui_child,catalog_source(pid,turn),b'@explicit_xp1_gp_activation_catalogue',capacity=LIMIT)
    result=parse_catalog(raw,pid,turn)
    contract.project(result,pid,turn,observation=observation)
    return result


def catalogue(saved,observation):
    value=_catalogue(_bind(saved),observation)
    saved.explicit_great_person_activation=deepcopy(value)
    return value


def borrowed_enabled(saved, requested=None):
    admitted = getattr(saved, 'xp2_great_person_activation', False) is True
    if requested is None:
        return admitted
    if type(requested) is not bool or requested and not admitted:
        raise ValueError('Borrowed activation requires its admitted Gathering Storm option')
    return requested


def borrowed_state(saved, observation):
    player, turn = _identity(observation)
    prefix = _bind(saved, borrowed_player=player)
    return contract.project(_catalogue(prefix, observation), player, turn, observation=observation)


def actions(value):
    if value is None:return []
    return contract.actions(contract.project(value,value['player_id'],value['current_game_turn']))


def request_source(selected,pid,turn):
    fields=('unit_id','x','y','individual_index','class_index','charges')
    numbers=','.join(str(selected[k]) for k in fields)
    return _preamble(pid,turn)+f'''
local wanted={{{numbers}}};local chosen=nil
for _,row in ipairs(snapshot()) do
 if row.unit_id==wanted[1] then
  assert(not chosen and row.x==wanted[2] and row.y==wanted[3] and row.individual_index==wanted[4]
   and row.class_index==wanted[5] and row.charges==wanted[6],'GP choice changed');chosen=row
 end
end
assert(chosen,'own GP choice disappeared');ready()
assert(chosen.visible,'GP command is no longer visible')
if not chosen.available then return 'refused' end
UnitManager.RequestCommand(chosen.unit,command.Hash)
return 'submitted'
'''.encode('ascii')


def verify_archive(raw,pid,uid):
    if type(raw) is not bytes or len(raw)!=20:
        raise RuntimeError('Great Person command archive is not the empty-parameter UnitCommand')
    kind,owner,typ,unit,index,parameter=struct.unpack('<IHHIII',raw)
    if (kind,owner,typ,unit,parameter)!=(source.ARCHIVE_KIND,pid,1,uid,0) or index>0x7fffffff:
        raise RuntimeError('Great Person command archive lost its owned unit or empty parameters')
    # The normalized index is native registration order, not GameInfo.Index.
    # Its command identity is independently checked by the post-apply marker.
    return dict(archive_sha256=sha256(raw).hexdigest(),size_bytes=20,normalized_command_index=index,
                command_hash=source.COMMAND_HASH,parameters={})


def _post_command(prefix,pid,uid):
    from .native import native_event_fc7db95e as codec
    found=[]
    for record in prefix.deferred_events.pending:
        if type(record) is not bytes or len(record)<12:
            raise RuntimeError('Malformed post-command deferred record')
        if int.from_bytes(record[4:8],'little')!=codec.RECORD_TYPE:continue
        sequence=int.from_bytes(record[8:12],'little')
        expected=codec.encode_record(sequence,codec.EventFields(source.COMMAND_HASH,pid,uid,0,0),
            normalizer_transform_present=False,per_thread_hook_present=False,
            writer_metadata_callback_present=False,entity_listener_count=0,padding_policy=codec.PADDING_POLICY,
            empty_receiver_state=prefix.event_arguments.consumer.empty_receiver_state)
        if record==expected:found.append(sequence)
    if len(found)!=1:
        raise RuntimeError('Great Person activation lacks its exact native post-command marker')
    return found[0]


def _work_record(raw,pid,uid,cities,start,marker):
    """Recognize a newly produced, canonical unit GreatWorkCreated record."""
    from .native import native_event_great_work as codec
    # FFFFFFFF also names the qualified legacy non-unit producer. It remains
    # a legal action ID domain, but this event alone cannot disambiguate it.
    if uid==0xffffffff or type(raw) is not bytes or len(raw)!=codec.RECORD_SIZE:
        return False
    size,kind,sequence=struct.unpack_from('<III',raw)
    if (size,kind)!=(codec.RECORD_SIZE,codec.RECORD_TYPE) or not start<sequence<marker:
        return False
    if raw[144:152]!=struct.pack('<HHI',pid,1,uid):
        return False
    city_owner,city_type,city_id=struct.unpack_from('<HHI',raw,96)
    if city_owner!=pid or city_type!=2:
        return False
    # GreatWorkCreated identifies the receiving city's plot. The selected
    # Great Person can be standing in a different plot of the same city.
    x,y=struct.unpack_from('<ii',raw,88)
    if not any((city['owner'],city['id'],city['x'],city['y'])==(pid,city_id,x,y)
               for city in cities):
        return False
    fields=dict(position_bytes=raw[88:96],x=x,y=y,selector=0,
                source_value=struct.unpack_from('<I',raw,116)[0],
                descriptor_tail=struct.unpack_from('<I',raw,136)[0])
    expected=codec.encode_record(sequence,fields,raw[144:152],dict(owner=pid,city_id=city_id,district_id=0))
    return raw==expected


def confirmation(receipt,*,pid,unit_id,cities,charges_before,charges_after,unit_consumed,profile=source):
    """Validate effect evidence independently of the command's post marker."""
    start,marker=receipt.get('deferred_start_sequence'),receipt.get('post_command_sequence')
    if (type(start) is not int or type(marker) is not int or not 0<=start<marker<=0x7fffffff
            or receipt.get('completion_source_sha256')!=profile.COMPLETION_SOURCE[1]):
        raise RuntimeError('Great Person completion interval or source differs')
    records=receipt.get('great_work_records')
    if type(records) is not list or len(records)>1:
        raise RuntimeError('Great Person completion has an ambiguous Great Work receipt')
    for row in records:
        if (type(row) is not dict or set(row)!={'record_hex','record_sha256','source_sha256'}
                or row['source_sha256']!=_work_source(profile)[1]
                or type(row['record_hex']) is not str or len(row['record_hex'])!=320):
            raise RuntimeError('Great Person completion has a foreign Great Work source')
        try:raw=bytes.fromhex(row['record_hex'])
        except ValueError as error:raise RuntimeError('Malformed Great Work completion bytes') from error
        if (raw.hex()!=row['record_hex'] or sha256(raw).hexdigest()!=row['record_sha256']
                or not _work_record(raw,pid,unit_id,cities,start,marker)):
            raise RuntimeError('Great Work completion differs from this command interval or owned unit')
    if unit_consumed:return 'unit_consumed'
    if charges_after<charges_before:return 'charges_consumed'
    if records:return 'great_work_created'
    return None


def apply(saved,action,before,*,borrowed_catalogue=None):
    pid,turn=_identity(before)
    borrowed=borrowed_catalogue is not None
    prefix=_bind(saved,action=True,borrowed_player=pid if borrowed else None)
    profile=selected_source(saved)
    digest=profile.SOURCE[1]
    contract.validate_action(action)
    retained=borrowed_catalogue
    if borrowed:
        contract.validate(retained,pid,turn)
    else:
        native=getattr(saved,'explicit_great_person_activation',None)
        if native is not None and (native.get('player_id'),native.get('current_game_turn'))==(pid,turn):
            retained=contract.project(native,pid,turn)
    if retained is None or action not in contract.actions(retained):
        raise RuntimeError('Great Person choice was not explicitly offered')
    fresh=_catalogue(prefix,before)
    prior=next(row for row in retained['units'] if row['unit_id']==action['unit_id'])
    selected=next((row for row in fresh['units'] if row['unit_id']==action['unit_id']),None)
    identity=('unit_id','x','y','individual_index','class_index','charges')
    if selected is None or any(selected[k]!=prior[k] for k in identity):
        if borrowed:
            return dict(status='refused',observation=deepcopy(before),refusal_code=OFFER_CHANGED,source_sha256=digest)
        raise RuntimeError('Great Person choice is stale')
    if not selected['visible']:
        if borrowed:
            return dict(status='refused',observation=deepcopy(before),refusal_code=OFFER_CHANGED,source_sha256=digest)
        raise RuntimeError('Great Person command is no longer visible')
    if not selected['available']:
        return dict(status='refused',observation=deepcopy(before),refusal_code=REFUSED,
                    request=dict(can_start=False,request_invoked=False),source_sha256=digest)
    reply=prefix.runtime.evaluate_text(prefix.ui_child,request_source(selected,pid,turn),b'@explicit_xp1_gp_activation_request')
    if reply==b'refused':
        if prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Refused Great Person command queued effects')
        return dict(status='refused',observation=deepcopy(before),refusal_code=REFUSED,
                    request=dict(can_start=False,request_invoked=False),source_sha256=digest)
    if reply!=b'submitted' or len(prefix.actions.pending)!=1:
        raise RuntimeError('Great Person activation did not enqueue exactly one command')
    receipt=verify_archive(prefix.actions.pending[0],pid,action['unit_id'])
    start=prefix.deferred_events.consumed_count
    if prefix.deferred_events.pending:
        raise RuntimeError('Great Person request queued events before native archive delivery')
    prefix.actions.deliver_one()
    sequence=_post_command(prefix,pid,action['unit_id'])
    work_sha=_work_source(profile)[1]
    work_records=[dict(record_hex=raw.hex(),record_sha256=sha256(raw).hexdigest(),
                       source_sha256=work_sha)
                  for raw in prefix.deferred_events.pending
                  if _work_record(raw,pid,action['unit_id'],before['cities'],start,sequence)]
    prefix.deferred_events.drain_empty_receivers()
    if profile is not source:
        continuation=saved.continuation
        if continuation.trade_feedback is not None and continuation.trade_feedback.events:
            continuation.flush_trade_feedback()
    prefix.view_publisher.publish()
    prefix.actions.require_empty_native_queue()
    after=observe_player(prefix.runtime,prefix.ui_child,pid)
    if _identity(after)!=(pid,turn):
        raise RuntimeError('Great Person activation crossed actor or turn')
    end=_catalogue(prefix,after)
    survivor=next((row for row in end['units'] if row['unit_id']==action['unit_id']),None)
    observed=[row for row in after['units'] if row['id']==action['unit_id']]
    if bool(survivor)!=bool(observed) or len(observed)>1:
        raise RuntimeError('Great Person own roster and public unit readback differ')
    if survivor is not None and any(survivor[k]!=selected[k] for k in ('individual_index','class_index')):
        raise RuntimeError('Great Person survivor changed native identity')
    receipt.update(post_command_sequence=sequence,native_archive_delivered=True,native_command_processed=True,
                   unit_before=deepcopy(selected),unit_after=deepcopy(survivor),deferred_start_sequence=start,
                   great_work_records=work_records,completion_source_sha256=profile.COMPLETION_SOURCE[1])
    basis=confirmation(receipt,pid=pid,unit_id=action['unit_id'],cities=before['cities'],
                       charges_before=selected['charges'],charges_after=None if survivor is None else survivor['charges'],
                       unit_consumed=survivor is None,profile=profile)
    receipt.update(effect_confirmed=basis is not None,confirmation_basis=basis)
    result=dict(status='completed' if basis else 'submitted',reason=None if basis else UNCONFIRMED,
                observation=after,unit_id=action['unit_id'],x=action['x'],y=action['y'],
                individual_index=selected['individual_index'],class_index=selected['class_index'],
                charges_before=selected['charges'],charges_after=None if survivor is None else survivor['charges'],
                unit_consumed=survivor is None,source_sha256=digest,receipt=receipt)
    if not borrowed:
        saved.explicit_great_person_activation=deepcopy(end)
    prefix.emit('official_explicit_great_person_activation_effect',action=action,**result)
    return result


def apply_borrowed(saved, action, before, *, expected, available):
    refused = dict(status='refused', requested_action=action)
    if not available or expected is None:
        return dict(refused, reason=UNAVAILABLE), None
    player, turn = _identity(before)
    contract.validate(expected, player, turn)
    if action not in contract.actions(expected):
        return dict(refused, reason=OFFER_CHANGED), None
    continuation = saved.continuation
    publications = continuation.publication_count
    result = apply(saved, action, before, borrowed_catalogue=expected)
    if result['status'] == 'refused':
        return dict(refused, reason=result['refusal_code']), None
    after = result['observation']
    if (result['status'] not in ('completed', 'submitted') or _identity(after) != (player, turn)
            or continuation.publication_count != publications + 1):
        raise RuntimeError('Borrowed Great Person activation crossed its native publication boundary')
    return dict(status=result['status'], reason=result['reason'], requested_action=action), after


require_actions=source.require_actions
source_dependencies=source.source_dependencies
supports=source.supports

"""Owned rock bands and their parameterless official UnitPanel concert."""

from functools import partial
from hashlib import sha256
from struct import pack

from civ6_host.contracts import rock_bands as contract
from . import expansion_city_growth, xp2_rock_concert_source as concert
from .execution_images import _PROFILE
from .native.native_player_observation import observe_player

REFUSED = 'native_rock_concert_unavailable'
SUBMITTED = 'native_rock_concert_effect_unconfirmed'
_LIMIT = 512 * 1024


def source_dependencies(reference, image):
    proof=concert.source()
    if image is not _PROFILE:
        raise ValueError('Rock bands require the installed Gathering Storm image')
    capture=next((row for row in proof['captures']
                  if (row['reference']['path'],row['reference']['sha256'])==reference),None)
    if capture is None:
        raise ValueError('Rock bands require an admitted stock or BBG 7.5.1 capture')
    pins=concert.source_dependencies()
    for row in (capture['reference'],capture['database']):
        pins[str(concert.source_path(row['path']).resolve())]=row['sha256']
    return pins


def bind(saved):
    lifetime=expansion_city_growth._owner(saved)
    core=lifetime[0]
    source_dependencies(lifetime[-1],getattr(core,'_civ6_host_execution_image',None))
    proof=concert.source()
    read=saved.backend.runtime.read
    for slot,target in proof['slots']:
        if read(core._handle+slot,8)!=pack('<Q',core._handle+target):
            raise ValueError('Rock concert descriptor differs')
    spans=[row for bodies in proof['operation_bodies'].values() for row in bodies]
    for binding in proof['bindings']:
        literal=binding['name'].encode()+b'\0'
        if read(core._handle+binding['name_rva'],len(literal))!=literal:
            raise ValueError('Rock-band native getter name differs')
        spans.extend((binding['registration'],*binding['callbacks']))
    for span in spans:
        raw=read(core._handle+span['rva'],span['bytes'])
        if type(raw) is not bytes or len(raw)!=span['bytes'] or sha256(raw).hexdigest()!=span['sha256']:
            raise ValueError('Rock-band native getter or operation differs')
    saved._xp2_rock_bands=lifetime


def enabled(saved):
    return getattr(saved,'_xp2_rock_bands',None) is not None


def _bound(saved):
    if not enabled(saved) or expansion_city_growth._owner(saved)!=saved._xp2_rock_bands:
        raise ValueError('Rock bands lost their admitted owner lifetime')


_CONTEXT = br'''
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'foreign rock-band perspective')
local player=assert(Players[pid])
local op=assert(GameInfo.UnitOperations.UNITOPERATION_TOURISM_BOMB)
assert(op.Hash%4294967296==0x852ce4df and op.VisibleInUI==true and op.InterfaceMode==nil,
 'rock concert operation changed')
local function ready()
 return player:IsTurnActive()==true and player:IsTurnActiveComplete()==true
end
local function visibility(unit)
 return unit:GetMovesRemaining()>0 and UnitManager.CanStartOperation(unit,op.Hash,nil,true)
end
local function available(unit)
 return ready() and visibility(unit) and
  UnitManager.CanStartOperation(unit,op.Hash,nil,false,OperationResultsTypes.NO_TARGETS)
end
local function band(unit)
 return GameInfo.Units[unit:GetUnitType()].UnitType=='UNIT_ROCK_BAND'
end
'''
_QUERY = br'''
local rows,count={},0
for _,unit in player:GetUnits():Members() do
 count=count+1
 assert(count<=4096 and unit:GetOwner()==pid,'unbounded or foreign rock-band roster')
 if band(unit) then
  local rock=assert(unit:GetRockBand())
  local visible,allowed=visibility(unit),available(unit)
  assert(type(visible)=='boolean' and type(allowed)=='boolean','invalid concert availability')
  rows[#rows+1]=string.format('%.0f|%.0f|%.0f|%.0f|%.0f|%d|%d',
   unit:GetID(),unit:GetX(),unit:GetY(),rock:GetRockBandLevel(),rock:GetAlbumSales(),
   visible and 1 or 0,allowed and 1 or 0)
 end
end
return table.concat(rows,'\n')
'''
_REQUEST = br'''
local unit=player:GetUnits():FindID(chosen)
if unit==nil or unit:GetOwner()~=pid or unit:GetX()~=x or unit:GetY()~=y or not band(unit)
 or not available(unit) then return 'refused' end
assert(op.Index==opcode,'rock concert opcode changed')
UnitManager.RequestOperation(unit,op.Hash)
return 'requested'
'''


def _lua(observation,body,constants=b''):
    return (b'local pid,turn=%d,%d\n' % (observation['player_id'],observation['turn'])
            + constants + _CONTEXT + body)


def _integer(raw):
    value=int(raw)
    if str(value).encode()!=raw:
        raise ValueError('Invalid native rock-band integer')
    return value


def read_panel(saved,observation,*,borrowed=False):
    if borrowed:
        saved._check_active()
    else:
        saved._check_query()
    _bound(saved)
    prefix=saved.prefix
    raw=prefix.runtime.evaluate_text(prefix.ui_child,_lua(observation,_QUERY),
                                      b'@rock_band_information',capacity=_LIMIT+1)
    if type(raw) is not bytes or len(raw)>_LIMIT:
        raise ValueError('Unbounded rock-band information')
    units=[]
    for line in raw.splitlines():
        unit,x,y,level,sales,visible,allowed=map(_integer,line.split(b'|'))
        if visible not in (0,1) or allowed not in (0,1):
            raise ValueError('Invalid rock-band visibility flags')
        units.append(dict(unit_id=unit,x=x,y=y,level=level,album_sales=sales,
                          visible=bool(visible),available=bool(allowed)))
    units.sort(key=lambda row:row['unit_id'])
    panel=dict(schema=contract.SCHEMA,player_id=observation['player_id'],turn=observation['turn'],units=units)
    return contract.validate(panel,panel['player_id'],panel['turn'],observation=observation)


def read(saved,observation,*,borrowed=False):
    return contract.actions(read_panel(saved,observation,borrowed=borrowed))


def verify_archive(payload,*,actor,unit,opcode):
    if type(payload) is not bytes or payload!=pack('<IHH5I',0x8c0f3f36,actor,1,unit,opcode,0xffffffff,0,0):
        raise ValueError('Rock concert archive differs from its actor, unit or operation')


def apply(saved,action,before):
    contract.validate_action(action,before)
    saved._check_active()
    _bound(saved)
    prefix,token=saved.prefix,saved.continuation
    if token.transport is not prefix.actions:
        raise ValueError('Rock concert lost its native transport')
    owner=saved.backend.host._a0_family_owner
    binding=owner.presentation_sources.get(concert.KIND)
    if binding is None or binding.source is not concert or getattr(owner,'_xp2_requested_rock_concert',None) is not None:
        raise ValueError('Rock concert lacks its exclusive source-qualified result callback')
    actor,turn=before['player_id'],before['turn']
    unit,x,y=(action[key] for key in ('unit_id','x','y'))
    index=prefix.runtime.evaluate_text(prefix.ui_child,
        _lua(before,b"return string.format('%.0f',op.Index)"),b'@rock_concert_index',capacity=16)
    opcode=_integer(index)
    if not 0<=opcode<=2047:
        raise ValueError('Unexpected native rock concert opcode')
    constants=b'local chosen,x,y,opcode=%d,%d,%d,%d\n' % (unit,x,y,opcode)
    pending=dict(identity=(actor,unit,x,y),event=None)
    owner._xp2_requested_rock_concert=pending
    try:
        verifier=partial(verify_archive,actor=actor,unit=unit,opcode=opcode)
        with token.transport.require_xp2_single_archive(verifier,allow_no_archive=True):
            reply=prefix.runtime.evaluate_text(prefix.ui_child,_lua(before,_REQUEST,constants),
                                               b'@rock_concert_request',capacity=16)
            if reply==b'refused':
                if pending['event'] is not None:
                    raise RuntimeError('Refused concert emitted a native result')
                return dict(status='refused',refusal_code=REFUSED,observation=before)
            if reply!=b'requested' or len(token.transport.pending)!=1:
                raise RuntimeError('Rock concert did not enqueue its single native archive')
            archive=sha256(token.transport.pending[0]).hexdigest()
            token.transport.deliver_one()
        prefix.deferred_events.drain_empty_receivers()
        if token.trade_feedback is not None and token.trade_feedback.events:
            token.flush_trade_feedback()
        prefix.view_publisher.publish()
        token.transport.require_empty_native_queue()
        after=observe_player(prefix.runtime,prefix.ui_child,actor)
        if (after['player_id'],after['turn'])!=(actor,turn):
            raise RuntimeError('Rock concert crossed its actor or turn')
        confirmed=pending['event'] is not None
        receipt=dict(action=action,archive_sha256=archive,effect_observed=confirmed)
        if confirmed:
            event=pending['event']
            receipt['concert']=contract.validate_result(
                dict(schema=contract.RESULT_SCHEMA,player_id=actor,turn=turn,unit_id=unit,
                     x=x,y=y,result_id=event.result,tourism=event.tourism),actor,turn,action)
        saved.backend.emit('native_xp2_rock_concert_effect',action=action,archive_sha256=archive,
            native_result_received=confirmed,
            administrative_result=None if not confirmed else pending['event'].to_admin(),
            payload_exposed_to_learner=False)
        return dict(status='completed' if confirmed else 'submitted',
                    refusal_code=None if confirmed else SUBMITTED,observation=after,
                    receipt=receipt)
    finally:
        owner._xp2_requested_rock_concert=None


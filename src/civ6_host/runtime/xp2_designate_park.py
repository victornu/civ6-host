"""Official Gathering Storm UnitPanel operation that designates a national park."""

from functools import partial
from hashlib import sha256
from struct import pack

from civ6_host.contracts import national_parks
from . import expansion_national_parks
from .configuration_profiles import _source
from .execution_images import _PROFILE
from .native.native_player_observation import observe_player
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-designate-park-source.json',
          'cf51227854754af9353d49ddbde89ee231ca4ee703c4473df90b92d0068ea809')
REFUSED = 'native_park_designation_unavailable'
SUBMITTED = 'native_park_designation_effect_unconfirmed'
_FRAME_LIMIT = 128 * 1024

# Native descriptor facts re-derived statically for the installed XP2 image
# 4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8 (12,941,592 B,
# ImageBase 0x180000000) — rea-civ6/evidence/designate_park-rea.md §2.1-2.6 and
# designate_park-rea.json DP-02…DP-12. The staged artefact described the 324c51e9
# build and every address in it is stale here: the two .text functions moved by
# +0x40, the resolver is a 314-byte function rather than one 95-byte .pdata
# fragment, and 0xa29110 is now a different pointer table. Only the operation hash
# is unchanged. Anything the evidence does not prove stays refused.
OPERATION = 0x3D7D2377
RESOLVER_RVA = 0x668850                     # whole function, ret at 0x668989
RESOLVER_BYTES = 314
RESOLVER_SHA256 = 'b53124b6ec9fac6ef896497ac814a8e9ba2268917e07c04273ae7093ef89a38f'
RESOLVER_OPERATION_SITE = 0x668871          # mov edx, OPERATION
RESOLVER_CALLER_SITE = 0x4BEF6B             # call RESOLVER_RVA
CONSTRUCTOR_RVA = 0x668990
CONSTRUCTOR_BYTES = 122
CONSTRUCTOR_SHA256 = 'd80322a55e8f6710ae2562a1d89c59d85287eeccb28f2f8789f78e6756a55448'
CONSTRUCTOR_OPERATION_SITE = 0x6689DA       # mov dword ptr [rdx + 0xc], OPERATION
CONSTRUCTOR_CALLER_SITE = 0x750A17          # call CONSTRUCTOR_RVA
DESCRIPTOR_VTABLE = 0xA290B0                # installed by lea rax,[rip+0x3c06d6] @0x6689d3
FAMILY_STRING_RVA = 0xA29170                # ...Unit_Operations_DesignatePark.cpp
SLOTS = (                                   # ten descriptor slots the proof iterates
    (DESCRIPTOR_VTABLE + 0x00, 0x668C30),
    (DESCRIPTOR_VTABLE + 0x08, 0x683310),
    (DESCRIPTOR_VTABLE + 0x10, 0x668600),
    (DESCRIPTOR_VTABLE + 0x18, 0x9B10A0),
    (DESCRIPTOR_VTABLE + 0x20, 0x3FA100),
    (DESCRIPTOR_VTABLE + 0x28, 0x6648D0),
    (DESCRIPTOR_VTABLE + 0x30, 0x3FA100),
    (DESCRIPTOR_VTABLE + 0x38, 0x9B10A0),
    (DESCRIPTOR_VTABLE + 0x40, 0x668A10),
    (DESCRIPTOR_VTABLE + 0x48, 0x3FA100))
SPANS = (
    dict(rva=RESOLVER_RVA, bytes=RESOLVER_BYTES, sha256=RESOLVER_SHA256),
    dict(rva=CONSTRUCTOR_RVA, bytes=CONSTRUCTOR_BYTES, sha256=CONSTRUCTOR_SHA256))
_SPAN_ROWS = tuple((span['rva'], span['bytes'], span['sha256']) for span in SPANS)


def _proof(image):
    proof = _source(SOURCE)
    if (image is not _PROFILE or proof['schema'] != 'civ6-host.xp2-designate-park.source.v1'
            or proof['image_sha256'] != image.image_sha256 or proof['operation'] != OPERATION
            or proof['parameterless_unit_panel'] is not True
            or (proof['plot_getters']['path'], proof['plot_getters']['sha256']) != expansion_national_parks.SOURCE):
        raise ValueError('Park designation requires the exact installed Gathering Storm source')
    if (tuple(tuple(pair) for pair in proof['slots']) != SLOTS
            or tuple((span['rva'], span['bytes'], span['sha256']) for span in proof['spans']) != _SPAN_ROWS):
        raise ValueError('Park designation native descriptor differs from the re-derived spans and slots')
    return proof


def source_dependencies(reference, image):
    proof = _proof(image)
    capture = next((row for row in proof['captures']
                    if (row['reference']['path'], row['reference']['sha256']) == reference), None)
    if capture is None:
        raise ValueError('Park designation requires an admitted Gathering Storm capture')
    from .xp2_bbg_inputs import REFERENCE as bbg
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]), capture['reference'], capture['database'],
            *proof['ui'][0 if reference == bbg else 1:]]
    pins = expansion_national_parks.source_dependencies(reference, image)
    for row in rows:
        path = str(resolve_path(resource_root() / row['path']).resolve(strict=True))
        if pins.setdefault(path, row['sha256']) != row['sha256']:
            raise ValueError('Conflicting park designation source pin')
    return pins


def verify_live(base, read, image):
    proof = _proof(image)
    for slot, target in proof['slots']:
        if read(base + slot, 8) != pack('<Q', base + target):
            raise ValueError('Park designation native descriptor differs')
    for span in proof['spans']:
        raw = read(base + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Park designation native binding differs')


def bind(saved):
    lifetime = expansion_national_parks.expansion_city_growth._owner(saved)
    core = lifetime[0]
    image = getattr(core, '_civ6_host_execution_image', None)
    _, readers = expansion_national_parks._profile(lifetime[-1], image)
    read = saved.backend.runtime.read
    expansion_national_parks.verify_live(readers, core._handle, read)
    verify_live(core._handle, read, image)
    saved._xp2_designate_park = lifetime


def enabled(saved):
    return getattr(saved, '_xp2_designate_park', None) is not None


_CONTEXT = br'''
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'foreign park designation boundary')
local player=assert(Players[pid])
local op=assert(GameInfo.UnitOperations.UNITOPERATION_DESIGNATE_PARK)
assert(op.Hash==1031611255 and op.VisibleInUI==true and op.InterfaceMode==nil,
 'park designation operation changed')
local function ready()
 return player:IsTurnActive()==true and player:IsTurnActiveComplete()==true
end
local function legal(unit)
 if unit:GetMovesRemaining()<=0 then return false end
 local visible=UnitManager.CanStartOperation(unit, op.Hash, nil, true)
 assert(type(visible)=='boolean','invalid park designation visibility')
 if not visible then return false end
 local allowed=UnitManager.CanStartOperation(unit, op.Hash, nil, false, OperationResultsTypes.NO_TARGETS)
 assert(type(allowed)=='boolean','invalid park designation legality')
 return allowed
end
'''


_QUERY = br'''
assert(ready(),'park designation actor is waiting')
local rows,count={},0
for _,unit in player:GetUnits():Members() do
 count=count+1
 assert(count<=4096 and unit:GetOwner()==pid,'foreign or unbounded park units')
 if legal(unit) then
  rows[#rows+1]=string.format('%.0f|%.0f|%.0f',unit:GetID(),unit:GetX(),unit:GetY())
 end
end
return table.concat(rows,'\n')
'''


_REQUEST = br'''
if not ready() then return 'refused' end
local unit=player:GetUnits():FindID(chosen)
if unit==nil or unit:GetOwner()~=pid or unit:GetX()~=x or unit:GetY()~=y or not legal(unit) then
 return 'refused'
end
assert(op.Index==opcode,'park designation opcode changed')
local plot=assert(Map.GetPlot(x,y))
if plot:IsNationalPark()~=false then return 'refused' end
UnitManager.RequestOperation(unit,op.Hash)
return 'requested'
'''


def _lua(observation, body, constants=b''):
    source = b'local pid,turn=%d,%d\n' % (observation['player_id'], observation['turn'])
    return source + constants + _CONTEXT + body


def _require_bound(saved):
    if not enabled(saved) or expansion_national_parks.expansion_city_growth._owner(saved) != saved._xp2_designate_park:
        raise ValueError('Park designation lost its admitted owner lifetime')


def _number(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 10 or not raw.isdigit() or str(int(raw)).encode() != raw:
        raise ValueError('Invalid native park designation number')
    return int(raw)


def read(saved, observation, *, borrowed=False):
    if borrowed:
        saved._check_active()
    else:
        saved._check_query()
    _require_bound(saved)
    prefix = saved.prefix
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _lua(observation, _QUERY),
                                       b'@park_designation_choices', capacity=_FRAME_LIMIT+1)
    if type(raw) is not bytes or len(raw) > _FRAME_LIMIT:
        raise ValueError('Unbounded park designation catalogue')
    actions = []
    for row in raw.splitlines():
        unit, x, y = map(_number, row.split(b'|'))
        action = dict(kind=national_parks.DESIGNATE, unit_id=unit, x=x, y=y)
        actions.append(national_parks.validate_designation(action, observation))
    actions.sort(key=lambda action: action['unit_id'])
    national_parks.validate_designations(actions, observation)
    return actions


def verify_archive(payload, *, actor, unit, opcode):
    expected = pack('<IHH5I', 0x8c0f3f36, actor, 1, unit, opcode, 0xffffffff, 0, 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Park designation archive differs from its actor, unit or operation')


def apply(saved, action, before):
    national_parks.validate_designation(action, before)
    saved._check_active()
    _require_bound(saved)
    prefix, token = saved.prefix, saved.continuation
    if token.transport is not prefix.actions:
        raise ValueError('Park designation lost its command transport')
    actor, turn = before['player_id'], before['turn']
    unit, x, y = (action[key] for key in ('unit_id', 'x', 'y'))
    index = prefix.runtime.evaluate_text(prefix.ui_child,
        _lua(before, b"return string.format('%.0f',op.Index)"), b'@park_designation_index', capacity=16)
    opcode = _number(index)
    if opcode > 2047:
        raise ValueError('Unexpected native park designation opcode')
    constants = b'local chosen,x,y,opcode=%d,%d,%d,%d\n' % (unit,x,y,opcode)
    check = partial(verify_archive, actor=actor, unit=unit, opcode=opcode)
    with token.transport.require_xp2_single_archive(check, allow_no_archive=True):
        raw = prefix.runtime.evaluate_text(prefix.ui_child, _lua(before,_REQUEST,constants),
                                           b'@park_designation_request', capacity=16)
        if raw == b'refused':
            return dict(status='refused', refusal_code=REFUSED, observation=before)
        if raw != b'requested' or len(token.transport.pending) != 1:
            raise RuntimeError('Park designation did not enqueue its single native archive')
        digest = sha256(token.transport.pending[0]).hexdigest()
        token.transport.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    if token.trade_feedback is not None and token.trade_feedback.events:
        token.flush_trade_feedback()
    prefix.view_publisher.publish()
    token.transport.require_empty_native_queue()
    after = observe_player(prefix.runtime, prefix.ui_child, actor)
    if (after['player_id'], after['turn']) != (actor, turn):
        raise RuntimeError('Park designation crossed its actor or turn')
    park = prefix.runtime.evaluate_text(prefix.ui_child, _lua(after,
        b"return tostring(assert(Map.GetPlot(x,y)):IsNationalPark())", constants),
        b'@park_designation_effect', capacity=16)
    if park not in (b'true', b'false'):
        raise RuntimeError('Unexpected native park readback')
    confirmed = park == b'true'
    return dict(status='completed' if confirmed else 'submitted', refusal_code=None if confirmed else SUBMITTED,
                observation=after, receipt=dict(action=action, archive_sha256=digest, effect_observed=confirmed))

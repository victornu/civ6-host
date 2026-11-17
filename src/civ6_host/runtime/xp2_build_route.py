"""The installed Gathering Storm UnitPanel's parameterless Build Route action."""

from functools import partial
from hashlib import sha256
from struct import pack

from civ6_host.contracts import unit_work
from . import xp2_bbg_inputs, xp2_bundle_inputs
from .configuration_profiles import _source
from .execution_images import _PROFILE
from .native.native_player_observation import observe_player
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-build-route-source.json',
          '691b6bba1bd46cc5c4737ce6fdc9cd9f7943df69c8a88aa76bdcce8eefcdbb21')
REFUSED = 'native_build_route_unavailable'
SUBMITTED = 'native_build_route_effect_unconfirmed'
_LIMIT = 512 * 1024


def _proof(image):
    source = _source(SOURCE)
    if (image is not _PROFILE or source['schema'] != 'civ6-host.xp2-build-route.source.v1'
            or source['image_sha256'] != image.image_sha256 or source['operation'] != 0x06e68aef
            or source['route_result_key_native'] != 0x3b130e7b):
        raise ValueError('Build Route requires its exact installed Gathering Storm operation')
    return source


def source_dependencies(reference, image):
    proof = _proof(image)
    if reference not in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE):
        raise ValueError('Build Route requires an admitted Gathering Storm capture')
    capture, = (row for row in proof['captures'] if
                (row['reference']['path'], row['reference']['sha256']) == reference)
    ui = proof['ui'][0 if reference == xp2_bbg_inputs.REFERENCE else 1:]
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]), dict(path=image.path, sha256=image.image_sha256),
            capture['reference'], capture['database'], *ui]
    return {str(resolve_path(resource_root()/row['path']).resolve(strict=True)): row['sha256'] for row in rows}


def verify_live(base, read, image):
    proof = _proof(image)
    for slot, target in proof['slots']:
        if read(base + slot, 8) != pack('<Q', base + target):
            raise ValueError('Live Build Route descriptor differs')
    for span in proof['spans']:
        raw = read(base + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Build Route binding differs at ' + hex(span['rva']))


def bind(saved):
    backend = saved.backend
    core = backend.core
    if (core is None or saved.prefix is not backend.prefix or saved.prefix.core is not core
            or saved.continuation.owner is not backend):
        raise ValueError('Build Route requires its exact saved owner')
    verify_live(core._handle, backend.runtime.read, getattr(core, '_civ6_host_execution_image', None))
    saved._xp2_build_route_core = core


def enabled(saved):
    core = getattr(saved, '_xp2_build_route_core', None)
    return core is not None and core is saved.backend.core


_CONTEXT = br'''
local function integer(value, minimum, maximum)
    assert(type(value) == 'number' and value % 1 == 0 and value >= minimum and value <= maximum,
           'invalid route integer')
    return string.format('%.0f', value)
end
local function actor()
    assert(Game.GetLocalPlayer() == pid and Game.GetLocalObserver() == pid
           and Game.GetCurrentGameTurn() == turn, 'stale Build Route perspective')
    return assert(Players[pid])
end
local player = actor()
local function ready()
    actor()
    return player:IsTurnActive() == true and player:IsTurnActiveComplete() == true
end
local op = assert(GameInfo.UnitOperations.UNITOPERATION_BUILD_ROUTE)
assert(op.Hash == 0x06e68aef and op.VisibleInUI == true and op.InterfaceMode == nil,
       'UnitPanel Build Route definition changed')
local routeType = UnitOperationResults.ROUTE_TYPE
assert(type(routeType) == 'number' and routeType % 4294967296 == 0x3b130e7b,
       'UnitPanel Build Route result key changed')
local function offer(unit)
    local moves = unit:GetMovesRemaining()
    assert(type(moves) == 'number' and moves >= 0, 'invalid route movement')
    if moves <= 0 then return nil end
    local visible = UnitManager.CanStartOperation(unit, op.Hash, nil, true)
    assert(type(visible) == 'boolean', 'invalid route visibility')
    if not visible then return nil end
    local legal, details = UnitManager.CanStartOperation(unit, op.Hash, nil, false, OperationResultsTypes.NO_TARGETS)
    assert(type(legal) == 'boolean', 'invalid route legality')
    if not legal then return nil end
    assert(type(details) == 'table', 'native Build Route choice has no result data')
    local route = details[routeType]
    assert(type(route) == 'string' and #route <= 106 and route:match('^ROUTE_[A-Z0-9_]+$')
           and GameInfo.Routes[route], 'native Build Route choice has no route definition')
    return route
end
'''

_CATALOGUE = br'''
assert(ready(), 'route player is waiting')
local rows, count = {integer(pid,0,63) .. '|' .. integer(turn,0,2147483647)}, 0
for _, unit in player:GetUnits():Members() do
    count = count + 1
    assert(count <= 4096 and unit:GetOwner() == pid, 'foreign or unbounded route unit')
    local route = offer(unit)
    if route ~= nil then
        rows[#rows+1] = table.concat({integer(unit:GetID(),0,4294967295),
            integer(unit:GetPlotId(),0,16383), integer(unit:GetX(),0,16383),
            integer(unit:GetY(),0,16383), route}, '|')
    end
end
actor()
return table.concat(rows, '\n')
'''

_REQUEST = br'''
if not ready() then return 'refused' end
local unit = player:GetUnits():FindID(uid)
if unit == nil or unit:GetOwner() ~= pid or unit:GetPlotId() ~= plotID
   or unit:GetX() ~= x or unit:GetY() ~= y or offer(unit) ~= requested then return 'refused' end
assert(op.Index == opcode, 'Build Route operation index changed')
local plot = assert(Map.GetPlotByIndex(plotID))
assert(plot:GetX() == x and plot:GetY() == y, 'Build Route source plot changed')
local previous = integer(plot:GetRouteType(),-1,2147483647)
assert(ready(), 'Build Route submit boundary changed')
UnitManager.RequestOperation(unit, op.Hash)
return previous
'''

_AFTER = br'''
local plot = assert(Map.GetPlotByIndex(plotID))
assert(plot:GetX() == x and plot:GetY() == y, 'Build Route effect plot changed')
local index = plot:GetRouteType()
local route = GameInfo.Routes[requested]
return integer(index,-1,2147483647) .. '|' .. integer(route.Index,0,2147483647)
'''


def _lua(observation, constants, body):
    return (f"local pid, turn = {observation['player_id']}, {observation['turn']}\n".encode('ascii')
            + constants + _CONTEXT + body)


def _number(raw, minimum, maximum):
    value = int(raw)
    if str(value).encode('ascii') != raw or not minimum <= value <= maximum:
        raise ValueError('Invalid Build Route native number')
    return value


def read(saved, observation, *, borrowed=False):
    if borrowed:
        from .xp1_session_view import _borrowed_xp2_reference
        _borrowed_xp2_reference(saved, observation['player_id'])
    else:
        saved._check_query()
    if not enabled(saved):
        raise ValueError('Build Route source is not bound')
    prefix = saved.prefix
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _lua(observation, b'', _CATALOGUE),
                                       b'@public_build_route_catalogue', capacity=_LIMIT+1)
    if type(raw) is not bytes or not 0 < len(raw) <= _LIMIT:
        raise ValueError('Invalid Build Route frame size')
    header, *lines = raw.split(b'\n')
    if header != f"{observation['player_id']}|{observation['turn']}".encode('ascii') or len(lines) > 4096:
        raise ValueError('Build Route frame crossed its actor or turn')
    rows = []
    for line in lines:
        uid, plot, x, y, route = line.split(b'|')
        action = dict(kind=unit_work.BUILD_ROUTE, unit_id=_number(uid,0,0xffffffff),
                      plot_id=_number(plot,0,16383), x=_number(x,0,16383), y=_number(y,0,16383),
                      route_type=route.decode('ascii'))
        rows.append(unit_work.validate_route(action, observation))
    return sorted(rows, key=lambda action: action['unit_id'])


def verify_archive(raw, *, actor, unit, opcode):
    if type(raw) is not bytes or raw != pack('<IHH5I', 0x8c0f3f36, actor, 1, unit, opcode, 0xffffffff, 0, 0):
        raise ValueError('Build Route archive differs from its actor or parameterless operation')


def apply(saved, action, before):
    unit_work.validate_route(action, before)
    saved._check_active()
    if not enabled(saved):
        raise ValueError('Build Route source is not bound')
    prefix, token = saved.prefix, saved.continuation
    if token.transport is not prefix.actions:
        raise ValueError('Build Route lost its exact command transport')
    actor, turn = before['player_id'], before['turn']
    opcode = _number(prefix.runtime.evaluate_text(prefix.ui_child,
        _lua(before, b'', b'return integer(op.Index,0,2047)'), b'@build_route_index', capacity=16), 0, 2047)
    constants = ("local uid,plotID,x,y,opcode,requested=%d,%d,%d,%d,%d,'%s'\n" % (
        action['unit_id'], action['plot_id'], action['x'], action['y'], opcode, action['route_type'])).encode('ascii')
    check = partial(verify_archive, actor=actor, unit=action['unit_id'], opcode=opcode)
    with token.transport.require_xp2_single_archive(check, allow_no_archive=True):
        raw = prefix.runtime.evaluate_text(prefix.ui_child, _lua(before, constants, _REQUEST),
                                           b'@build_route_request', capacity=16)
        if raw == b'refused':
            return dict(status='refused', refusal_code=REFUSED, observation=before)
        prior = _number(raw,-1,2147483647)
        if len(prefix.actions.pending) != 1:
            raise RuntimeError('Build Route did not enqueue exactly one native archive')
        digest = sha256(prefix.actions.pending[0]).hexdigest()
        prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    if token.trade_feedback is not None and token.trade_feedback.events:
        token.flush_trade_feedback()
    prefix.view_publisher.publish()
    token.transport.require_empty_native_queue()
    after = observe_player(prefix.runtime, prefix.ui_child, actor)
    if (after['player_id'], after['turn']) != (actor, turn):
        raise RuntimeError('Build Route crossed its actor or turn')
    current, expected = prefix.runtime.evaluate_text(prefix.ui_child, _lua(before, constants, _AFTER),
                                                      b'@build_route_effect', capacity=32).split(b'|')
    new_route = _number(current,-1,2147483647)
    confirmed = new_route == _number(expected,0,2147483647) and new_route != prior
    return dict(status='completed' if confirmed else 'submitted', refusal_code=None if confirmed else SUBMITTED,
                observation=after, receipt=dict(action=action, archive_sha256=digest, effect_observed=confirmed))

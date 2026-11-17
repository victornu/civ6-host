"""Execute the exact parameterless UnitPanel excavation on its owned archaeologist."""

from hashlib import sha256
from struct import pack

from civ6_host.contracts import archaeology

from . import xp2_archaeology as popup
from .native.native_player_observation import observe_player


REFUSED = 'native_excavation_no_longer_available'
UNCONFIRMED = 'native_excavation_effect_unconfirmed'
_LIMIT = 128 * 1024


_ACTION = popup._CONTEXT + br'''
local operation = assert(GameInfo.UnitOperations.UNITOPERATION_EXCAVATE, 'excavation operation is absent')
assert(operation.Hash == 1548958412 and operation.VisibleInUI == true
       and operation.InterfaceMode == nil, 'excavation operation changed')
local function permitted(unit)
    local moves = unit:GetMovesRemaining()
    assert(type(moves) == 'number' and moves >= 0, 'invalid excavation movement')
    if moves == 0 then return false end
    local visible = UnitManager.CanStartOperation(unit, operation.Hash, nil, true)
    assert(type(visible) == 'boolean', 'invalid excavation visibility')
    if not visible then return false end
    local legal = UnitManager.CanStartOperation(unit, operation.Hash, nil, false, OperationResultsTypes.NO_TARGETS)
    assert(type(legal) == 'boolean', 'invalid excavation legality')
    return legal
end
local function ready()
    context()
    return player:IsTurnActive() == true and player:IsTurnActiveComplete() == true
end
'''


_CATALOGUE = _ACTION + br'''
assert(ready(), 'excavation actor is not ready')
local rows, unitCount = {}, 0
for _, unit in player:GetUnits():Members() do
    unitCount = unitCount + 1
    assert(unitCount <= 4096 and unit:GetOwner() == pid, 'unbounded or foreign excavation unit')
    if permitted(unit) then
        rows[#rows + 1] = table.concat({number(unit:GetID(), 0, 4294967295),
            number(unit:GetX(), 0, 2147483647), number(unit:GetY(), 0, 2147483647)}, '|')
    end
end
context()
return table.concat(rows, '\n')
'''


_REQUEST = _ACTION + br'''
if not ready() then return 'refused' end
local unit = player:GetUnits():FindID(chosen)
if unit == nil or unit:GetOwner() ~= pid or unit:GetX() ~= x or unit:GetY() ~= y
        or not permitted(unit) then return 'refused' end
assert(operation.Index == opcode, 'excavation operation index changed')
local index = number(unit:GetArchaeology():GetArtifactIndex(), -1, 2147483647)
assert(ready(), 'excavation boundary changed')
UnitManager.RequestOperation(unit, operation.Hash)
return index
'''


def _number(raw, high, *, accepts_absent=False):
    if accepts_absent and raw == b'-1':
        return -1
    if type(raw) is not bytes or not raw.isdigit() or int(raw) > high or str(int(raw)).encode('ascii') != raw:
        raise ValueError('Invalid native excavation number')
    return int(raw)


def read(saved, observation, *, borrowed=False):
    if borrowed:
        saved._check_active()
    else:
        saved._check_query()
    if not popup.commands_enabled(saved):
        raise ValueError('Excavation requires its admitted archaeology command source')
    prefix = saved.prefix
    source = popup.preamble(observation['player_id'], observation['turn'])
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source+_CATALOGUE,
                                       b'@public_artifact_excavations', capacity=_LIMIT+1)
    if type(raw) is not bytes or len(raw) > _LIMIT:
        raise ValueError('Native excavation offer exceeds its bound')
    rows = []
    for line in raw.splitlines():
        fields = line.split(b'|')
        if len(rows) == 4096 or len(fields) != 3:
            raise ValueError('Malformed native excavation catalogue')
        unit, x, y = (_number(value, limit) for value, limit in zip(fields, (2**32-1, 2**31-1, 2**31-1), strict=True))
        action = dict(kind=archaeology.EXCAVATE, unit_id=unit, x=x, y=y)
        rows.append(archaeology.validate_excavation(action, observation=observation))
    if len({row['unit_id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate native excavation candidate')
    return sorted(rows, key=lambda item: item['unit_id'])


def verify_archive(payload, actor, unit, index):
    expected = pack('<IHH5I', 0x8c0f3f36, actor, 1, unit, index, 0xffffffff, 0, 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Excavation archive differs from its exact actor, unit or parameterless operation')


def apply(saved, action, before):
    archaeology.validate_excavation(action, observation=before)
    saved._check_active()
    if not popup.commands_enabled(saved):
        raise ValueError('Excavation requires its source-bound saved owner')
    prefix, token = saved.prefix, saved.continuation
    if token.transport is not prefix.actions:
        raise ValueError('Excavation lost its owned command transport')
    actor, turn = before['player_id'], before['turn']
    unit, x, y = (action[key] for key in ('unit_id', 'x', 'y'))
    source = popup.preamble(actor, turn)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source+_ACTION+b'return number(operation.Index, 0, 2047)',
                                       b'@artifact_excavation_index', capacity=16)
    index = _number(raw, 2047)
    selected = f'local chosen, x, y, opcode = {unit}, {x}, {y}, {index}\n'.encode('ascii')
    def check(payload):
        verify_archive(payload, actor, unit, index)

    with token.transport.require_xp2_single_archive(check, allow_no_archive=True):
        raw = prefix.runtime.evaluate_text(prefix.ui_child, source+selected+_REQUEST,
                                           b'@artifact_excavation_request', capacity=16)
        if raw == b'refused':
            return dict(status='refused', observation=before, refusal_code=REFUSED)
        previous = _number(raw, 2**31-1, accepts_absent=True)
        if len(prefix.actions.pending) != 1:
            raise RuntimeError('Excavation did not enqueue exactly one native archive')
        digest = sha256(prefix.actions.pending[0]).hexdigest()
        prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    if token.trade_feedback is not None and token.trade_feedback.events:
        token.flush_trade_feedback()
    prefix.view_publisher.publish()
    token.transport.require_empty_native_queue()
    after = observe_player(prefix.runtime, prefix.ui_child, actor)
    if (after['player_id'], after['turn']) != (actor, turn):
        raise RuntimeError('Artifact excavation crossed its actor or turn')
    current = popup.unit_artifact_index(prefix, after, unit)
    confirmed = current is not None and current >= 0 and current != previous
    return dict(status='completed' if confirmed else 'submitted', observation=after,
                refusal_code=None if confirmed else UNCONFIRMED,
                receipt=dict(action=dict(action), native_archive_sha256=digest,
                             native_archive_delivered=True, native_pending_created=confirmed))

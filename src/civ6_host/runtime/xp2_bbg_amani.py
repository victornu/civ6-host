"""Marshal the installed BBG governor listeners without recreating their rules."""
from dataclasses import dataclass
import struct

from .xp2_bbg_trade_feedback import _between

_BRIDGE = b"""
assert(Civ6HostBBGAmani == nil, 'Existing BBG governor feedback owner')
local OnGovernorAssigned, OnGovernorChanged, GetAppointedGovernor
local requests = {}
local PlayerOperations = {EXECUTE_SCRIPT = 0xc665ad08}
local UI = {}
local function number(value, minimum, maximum)
    assert(type(value) == 'number' and value % 1 == 0 and value >= minimum
        and value <= maximum, 'Invalid BBG governor request integer')
    return value
end
function UI.RequestPlayerOperation(player, operation, p)
    assert(operation == PlayerOperations.EXECUTE_SCRIPT and type(p) == 'table'
        and p.OnStart == 'GameplaySetAmaniProperty' and p.iGovernorOwnerID == player
        and type(p.tAmani) == 'table' and #requests == 0, 'Unexpected BBG governor request')
    for k in pairs(p) do
        assert(k == 'OnStart' or k == 'iGovernorOwnerID' or k == 'tAmani',
            'Unexpected BBG governor parameter')
    end
    local t = p.tAmani
    for k in pairs(t) do
        assert(k == 'iCityID' or k == 'iMinorID' or k == 'Status', 'Unexpected BBG Amani property')
    end
    requests[1] = string.format('%d,%d,%d,%d', number(player, 0, 63),
        number(t.iCityID, 0, 2147483647), number(t.iMinorID, 0, 63), number(t.Status, -1, 1))
end
"""
_DISPATCH = b"""
local function dispatch(listener, ...)
    assert(#requests == 0, 'Pending BBG governor request')
    listener(...)
    local result = requests[1] or ''
    requests = {}
    return result
end
Civ6HostBBGAmani = {
    assigned = function(...) return dispatch(OnGovernorAssigned, ...) end,
    changed = function(...) return dispatch(OnGovernorChanged, ...) end,
}
"""


def listener_source(raw):
    """Use the installed Lua function bodies and their existing governor helpers."""
    return (_BRIDGE
            + _between(raw, b'function OnGovernorAssigned(', b'function OnTradeRouteActivityChanged(')
            + _between(raw, b'function OnGovernorChanged(', b'function OnUnitGreatPersonCreated(')
            + _between(raw, b'function GetAppointedGovernor(', b'function IDToPos(')
            + _DISPATCH)


def event_request(record, sequence):
    """Return the native event owner and its exact installed-listener invocation."""
    if (type(record) is not bytes or len(record) not in (96, 112)
            or type(sequence) is not int or not 0 < sequence <= 0xffffffff):
        raise ValueError('Invalid BBG governor record boundary')
    size, record_type, header_sequence = struct.unpack_from('<III', record)
    if size != len(record) or header_sequence != sequence or struct.unpack_from('<I', record, 80)[0] != sequence:
        raise ValueError('BBG governor record size or sequence differs')
    if (record_type, size) == (223, 112):
        name = 'assigned'
        args = struct.unpack_from('<h2xiii', record, 88)
    elif (record_type, size) == (224, 96):
        name = 'changed'
        args = struct.unpack_from('<ii', record, 84)
    else:
        raise ValueError('Unqualified BBG governor record type')
    arguments = ','.join(map(str, args))
    player = args[2] if name == 'assigned' else args[0]
    return player, f'return Civ6HostBBGAmani.{name}({arguments})'.encode('ascii')


def event_source(record, sequence):
    """Marshal an owned A0 governor record using the current EXE's Lua widths and order."""
    return event_request(record, sequence)[1]


@dataclass(frozen=True)
class AmaniRequest:
    player: int
    city: int
    city_owner: int
    status: int

    def parameters(self):
        return {b'OnStart': b'GameplaySetAmaniProperty', b'iGovernorOwnerID': self.player,
                b'tAmani': {b'iCityID': self.city, b'iMinorID': self.city_owner, b'Status': self.status}}


def parse_request(raw, player):
    if type(player) is not int or not 0 <= player < 64 or type(raw) is not bytes or len(raw) > 32:
        raise ValueError('Invalid BBG governor output boundary')
    if not raw:
        return None
    owner, city, city_owner, status = map(int, raw.split(b','))
    if (raw != f'{owner},{city},{city_owner},{status}'.encode('ascii') or owner != player
            or not 0 <= city <= 0x7fffffff or not 0 <= city_owner < 64 or status not in (-1, 0, 1)):
        raise ValueError('BBG governor request is outside the current player authority')
    return AmaniRequest(owner, city, city_owner, status)


def property_source(player):
    """Read the native BBG player property and its plot flags for the owner's cities."""
    if type(player) is not int or not 0 <= player < 64:
        raise ValueError('Invalid BBG governor property owner')
    return f"""
local owner = Players[{player}]
assert(owner ~= nil, 'Missing BBG governor property owner')
local function integer(value)
    assert(type(value) == 'number' and value % 1 == 0, 'Invalid BBG governor property integer')
    return value
end
local amani = owner:GetProperty('AMANI')
local rows = {{'absent'}}
if amani ~= nil then
    assert(type(amani) == 'table', 'Invalid BBG governor property')
    rows[1] = string.format('%d,%d,%d,%d', {player}, integer(amani.iCityID),
        integer(amani.iMinorID), integer(amani.Status))
end
local function flag(value)
    assert(value == nil or value == 1, 'Unexpected BBG plot property')
    return value == 1 and 1 or 0
end
for _, city in owner:GetCities():Members() do
    assert(#rows < 4097, 'BBG governor readback exceeds city bound')
    local plot = Map.GetPlot(city:GetX(), city:GetY())
    assert(plot ~= nil, 'Missing BBG governor city plot')
    rows[#rows + 1] = string.format('%d,%d,%d,%d,%d', integer(city:GetID()),
        integer(city:GetX()), integer(city:GetY()),
        flag(plot:GetProperty('AMANI_ESTABLISHED_CS')),
        flag(plot:GetProperty('TRADER_TO_AMANI_CS')))
end
return table.concat(rows, ';')
""".encode('ascii')


def parse_property(raw, player):
    if type(raw) is not bytes or not 0 < len(raw) <= 65536:
        raise ValueError('Invalid BBG governor property readback')
    rows = raw.split(b';')
    if len(rows) > 4097:
        raise ValueError('BBG governor readback exceeds city bound')
    amani = parse_request(b'' if rows[0] == b'absent' else rows[0], player)
    flags, positions = {}, {}
    for row in rows[1:]:
        city, x, y, established, trader = map(int, row.split(b','))
        if (row != f'{city},{x},{y},{established},{trader}'.encode('ascii') or city in flags
                or not 0 <= city <= 0x7fffffff or not 0 <= x <= 32767 or not 0 <= y <= 32767
                or established not in (0, 1) or trader not in (0, 1)):
            raise ValueError('Invalid BBG governor plot flag readback')
        flags[city] = (bool(established), bool(trader))
        positions[city] = (x, y)
    return amani, flags, positions

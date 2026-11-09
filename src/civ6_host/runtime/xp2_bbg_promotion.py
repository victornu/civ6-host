"""Bridge the installed BBG promotion listener without duplicating its XP rules."""
import hashlib
import struct

from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .paths import resource_root
from .xp2_bbg_trade_feedback import _between

KIND, RECORD_TYPE, RECORD_SIZE = 0x661109d9, 45, 112
SOURCE = ('evidence/host-xp2-bbg-promotion-ui-preparation.json',
          '7f760cf3fcdeb97dda640634a73636a4ba0de538c06006ad68817be545b568de')


def _proof(image):
    _require_image(image)
    proof = _source(SOURCE)
    event = proof['event']
    if (proof['schema'] != 'civ6-host.xp2-bbg-promotion-ui-marshalling.static.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or (event['kind'], event['record_type'], event['record_size']) != (hex(KIND), RECORD_TYPE, RECORD_SIZE)
            or tuple(event['payload_offsets']) != (88, 92, 96)
            or proof['script_effect']['operation'] != 'GameplayPromotionFixExp'):
        raise ValueError('BBG promotion source differs from its current event contract')
    return event


def source_dependencies(*, execution_image):
    _proof(execution_image)
    return {resource_root() / SOURCE[0]: SOURCE[1]}


def verify_live(image, core_base, read):
    event = _proof(image)
    for span in (event['core_producer'], event['core_emitter']):
        raw = read(core_base + int(span['rva'], 16), span['bytes'])
        if len(raw) != span['bytes'] or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live BBG promotion producer differs at ' + span['rva'])


_BRIDGE = b"""
assert(Civ6HostBBGPromotion == nil, 'Existing BBG promotion feedback owner')
local OnPromotionFixExp
local request
local PlayerOperations = {EXECUTE_SCRIPT = 0xc665ad08}
local UI = {}
function UI.RequestPlayerOperation(player, operation, params)
    assert(operation == PlayerOperations.EXECUTE_SCRIPT and request == nil
        and params.OnStart == 'GameplayPromotionFixExp' and params.iUnitPlayerID == player,
        'Unexpected BBG promotion request')
    for key in pairs(params) do
        assert(key == 'OnStart' or key == 'iUnitPlayerID' or key == 'iUnitID',
            'Unexpected BBG promotion parameter')
    end
    local unit = params.iUnitID
    assert(type(player) == 'number' and player % 1 == 0 and player >= 0 and player < 64
        and type(unit) == 'number' and unit % 1 == 0 and unit >= 0 and unit <= 2147483647,
        'Invalid BBG promotion identity')
    request = string.format('%d,%d', player, unit)
end
"""
_DISPATCH = b"""
Civ6HostBBGPromotion = function(...)
    assert(request == nil, 'Pending BBG promotion request')
    OnPromotionFixExp(...)
    local result = assert(request, 'BBG promotion listener emitted no request')
    request = nil
    return result
end
"""


def listener_source(raw):
    return (_BRIDGE
            + _between(raw, b'function OnPromotionFixExp(', b'function OnUnitAddedToMap(')
            + _DISPATCH)


def event_request(record, sequence):
    """Preserve the typed event owner and unit alongside the installed listener."""
    if (type(record) is not bytes or len(record) != RECORD_SIZE
            or type(sequence) is not int or not 0 < sequence <= 0xffffffff
            or struct.unpack_from('<III', record) != (RECORD_SIZE, RECORD_TYPE, sequence)
            or struct.unpack_from('<I', record, 80)[0] != sequence):
        raise ValueError('Invalid owned BBG promotion record')
    player, unit, promotion = struct.unpack_from('<h2xii', record, 88)
    return player, unit, f'return Civ6HostBBGPromotion({player},{unit},{promotion})'.encode('ascii')


def event_source(record, sequence):
    return event_request(record, sequence)[2]


def _owned_unit(player, unit):
    if (type(player) is not int or not 0 <= player < 64
            or type(unit) is not int or not 0 <= unit <= 0x7fffffff):
        raise ValueError('Invalid BBG promotion player or unit')


def parse_request(raw, player, *, event_unit=None):
    if type(raw) is not bytes or len(raw) > 13:
        raise ValueError('Invalid BBG promotion request')
    owner, unit = map(int, raw.split(b','))
    _owned_unit(owner, unit)
    if type(player) is not int or owner != player or raw != f'{owner},{unit}'.encode('ascii'):
        raise ValueError('BBG promotion request differs from its native event owner')
    if event_unit is not None:
        _owned_unit(player, event_unit)
        if unit != event_unit:
            raise ValueError('BBG promotion request differs from its native event unit')
    return {b'OnStart': b'GameplayPromotionFixExp', b'iUnitPlayerID': player, b'iUnitID': unit}


def experience_source(player, unit):
    _owned_unit(player, unit)
    return f"""
local unit = UnitManager.GetUnit({player}, {unit})
if unit == nil then return 'absent' end
assert(unit:GetOwner() == {player} and unit:GetID() == {unit}, 'BBG promotion readback identity')
local xp = unit:GetExperience():GetExperiencePoints()
assert(type(xp) == 'number' and xp % 1 == 0 and xp >= 0 and xp <= 2147483647,
    'BBG promotion experience exceeds XP2 integer profile')
return string.format('%d', xp)
""".encode('ascii')


def parse_experience(raw):
    if raw == b'absent':
        return None
    if type(raw) is not bytes or not 1 <= len(raw) <= 10:
        raise ValueError('Invalid BBG promotion experience readback')
    value = int(raw)
    if not 0 <= value <= 0x7fffffff or raw != str(value).encode('ascii'):
        raise ValueError('Invalid BBG promotion experience value')
    return value

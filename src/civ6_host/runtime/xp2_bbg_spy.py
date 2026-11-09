"""Transport the installed BBG SpyMissionCompleted listener to GameCore."""
import hashlib
import struct

from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .native.native_scalar_event_encoder import _decode_profile_fields, _encode_profile_record
from .paths import resource_root
from .xp2_bbg_trade_feedback import _between

KIND, RECORD_TYPE, RECORD_SIZE = 0x19087a58, 86, 96
SOURCE = ('evidence/host-xp2-bbg-spy-ui-preparation.json',
          '7feb03a36a715b072401131012e73beff1ff7be9b6fea403855b3f6f2ef2bbf8')
FIFO_SOURCE = ('evidence/host-xp2-bbg-spy-owned-fifo-source.json',
               '2c422bcc782f9a72a92e2d85dbe4259144f6e3425218d207fa93087209f74b15')
SELECTOR = 0x81c5bd7e
_SCALAR_RECORD = dict(callback_shape_group='two_value_three_key', payload_value_count=2,
                      writer_record_type=hex(RECORD_TYPE))
_RECEIVER = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None,
                 post_hook=None, subscriber_count=0, state_flags=0)


def _proof(image):
    _require_image(image)
    proof = _source(SOURCE)
    event = proof['event']
    if (proof['schema'] != 'civ6-host.xp2-bbg-spy-ui-marshalling.static.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or (event['kind'], event['record_type'], event['record_size']) != (hex(KIND), RECORD_TYPE, RECORD_SIZE)
            or tuple(event['payload_offsets']) != (84, 88)
            or tuple(proof['script_effect']['forwarded_parameters']) != ('OnStart', 'iPlayerID', 'iMissionID', 'State')):
        raise ValueError('BBG spy source differs from its current event contract')
    fifo = _source(FIFO_SOURCE)
    if (fifo['schema'] != 'civ6-host.xp2-bbg-spy-owned-fifo.static.v1'
            or fifo['preparation_sha256'] != SOURCE[1]
            or fifo['images'] != dict(core=CURRENT_CORE_SHA256, exe=CURRENT_EXE_SHA256)
            or fifo['owned_receiver'] != _RECEIVER
            or tuple(fifo['raw_fields']['selector']) != ('0xa1e5a149', 3, hex(SELECTOR))
            or tuple(fifo['raw_fields']['player']) != ('0xd6fcf3e4', 2, 80)
            or tuple(fifo['raw_fields']['mission']) != ('0xa1fbc372', 2, 84)
            or fifo['record'] != dict(type=RECORD_TYPE, size=RECORD_SIZE, sequence_offset=80,
                                      player_offset=84, mission_offset=88, metadata_descriptor_flag=0,
                                      receiver_row_rva='0x12c88d0')):
        raise ValueError('BBG spy source differs from its current FIFO contract')
    return event


def source_dependencies(*, execution_image):
    _proof(execution_image)
    return {resource_root() / path: digest for path, digest in (SOURCE, FIFO_SOURCE)}


def verify_live(image, core_base, read):
    event = _proof(image)
    for span in (*event['core_emitters'], event['common_emitter']):
        raw = read(core_base + int(span['rva'], 16), span['bytes'])
        if len(raw) != span['bytes'] or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live BBG spy producer differs at ' + span['rva'])


_BRIDGE = b"""
assert(Civ6HostBBGSpy == nil, 'Existing BBG spy feedback owner')
local OnSpyMissionCompleted
local request
local PlayerOperations = {EXECUTE_SCRIPT = 0xc665ad08}
local UI = {DataError = function(message) error(message) end}
function UI.RequestPlayerOperation(player, operation, params)
    assert(request == nil and operation == PlayerOperations.EXECUTE_SCRIPT
        and params.OnStart == 'GameplaySpyMissionCompleted' and params.iPlayerID == player,
        'Unexpected BBG spy request')
    for key in pairs(params) do
        assert(key == 'OnStart' or key == 'iPlayerID' or key == 'iMissionID' or key == 'State',
            'Unexpected BBG spy parameter')
    end
    local mission, state = params.iMissionID, params.State
    assert(type(player) == 'number' and player % 1 == 0 and player >= 0 and player < 64
        and type(mission) == 'number' and mission % 1 == 0 and mission >= 0 and mission <= 2147483647
        and (state == 0 or state == 1), 'Invalid BBG spy request')
    request = string.format('%d,%d,%d', player, mission, state)
end
"""
_DISPATCH = b"""
Civ6HostBBGSpy = function(...)
    assert(request == nil, 'Pending BBG spy request')
    OnSpyMissionCompleted(...)
    local result = request or ''
    request = nil
    return result
end
"""


def listener_source(raw):
    return (_BRIDGE
            + _between(raw, b'function OnSpyMissionCompleted(', b'function OnReligionFounded(')
            + _DISPATCH)


def event_fields(record, sequence):
    if (type(record) is not bytes or len(record) != RECORD_SIZE
            or struct.unpack_from('<IIII', record) != (RECORD_SIZE, RECORD_TYPE, sequence, 0)
            or struct.unpack_from('<I', record, 80)[0] != sequence):
        raise ValueError('Invalid owned BBG spy record')
    return struct.unpack_from('<ii', record, 84)


def encode_event(fields, sequence):
    selector, *values = _decode_profile_fields(_SCALAR_RECORD, fields)
    if selector != SELECTOR:
        raise ValueError('Unverified BBG spy selector')
    return _encode_profile_record(_SCALAR_RECORD, sequence, values)


def validate_enqueue(owner, record):
    if owner.active_kind != KIND or owner.empty_receiver_state != _RECEIVER:
        raise ValueError('BBG spy record lacks its exact source-qualified receiver')
    event_fields(record, owner._sequence + 1)


def parse_request(raw, *, local_player, event_player, mission):
    if type(raw) is not bytes or len(raw) > 15:
        raise ValueError('Invalid BBG spy request')
    if not raw:
        return None
    owner, requested_mission, state = map(int, raw.split(b','))
    if (owner != event_player or owner != local_player or not 0 <= owner < 64
            or mission != requested_mission or not 0 <= mission <= 0x7fffffff
            or state not in (0, 1) or raw != f'{owner},{mission},{state}'.encode('ascii')):
        raise ValueError('BBG spy request is outside its native event identity')
    return {b'OnStart': b'GameplaySpyMissionCompleted', b'iPlayerID': owner,
            b'iMissionID': mission, b'State': state}


def capacity_source(player):
    if type(player) is not int or not 0 <= player < 64:
        raise ValueError('Invalid BBG spy capacity player')
    return f"""
assert(Game.GetLocalPlayer() == {player}, 'Stale BBG spy perspective')
local capacity = Players[{player}]:GetDiplomacy():GetSpyCapacity()
assert(type(capacity) == 'number' and capacity % 1 == 0 and capacity >= 0 and capacity <= 2147483647,
    'BBG spy capacity exceeds XP2 integer profile')
return string.format('%d', capacity)
""".encode('ascii')


def parse_capacity(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= 10:
        raise ValueError('Invalid BBG spy capacity readback')
    value = int(raw)
    if not 0 <= value <= 0x7fffffff or raw != str(value).encode('ascii'):
        raise ValueError('Invalid BBG spy capacity value')
    return value

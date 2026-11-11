"""Stock XP2 dedications through the current player cache and native request queue."""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct

from civ6_host.contracts import dedications as contract
from .a0_policy_unlock_current import _require_image
from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .source_verification import file_sha256
from .xp1_world_input import _owner
from .xp2_bundle_inputs import REFERENCE


SOURCE = ('evidence/host-xp2-stock-t61-dedication-frontier.json',
          'e721a0b73232f8d96e7bc020ed53b6bd78a1cc14c6f76d4a40a1c6227f6ae11b')
OPERATION = 0x9e4ddfd9
PARAMETER = 0x6a475e64
BLOCKER = 0x31782ea7
_ARCHIVE_PREFIX = struct.pack('<I', 3294486831)
_LIMIT = 262144
_SEAL = object()

_QUERY = br'''
local function boundary()
  assert(Game.GetLocalPlayer() == pid and Game.GetLocalObserver() == pid
    and Game.GetCurrentGameTurn() == turn, 'foreign dedication perspective')
  local player = Players[pid]
  assert(player and player:IsAlive() == true and player:IsTurnActive() == true
    and player:IsTurnActiveComplete() == true, 'dedication player is not ready')
end
local function integer(value)
  assert(type(value) == 'number' and value >= 0 and value < 2147483648
    and value % 1 == 0, 'invalid dedication integer')
  return value
end
local function boolean(value)
  assert(type(value) == 'boolean', 'invalid dedication age flag')
  return value
end
local function append(out, kind, values)
  assert(type(values) == 'table', 'native dedication array unavailable')
  local count = 0
  for key in pairs(values) do
    assert(integer(key) >= 1 and key <= #values, 'invalid dedication array key')
    count = count + 1
    assert(count <= 1024, 'dedication array exceeds bound')
  end
  assert(count == #values, 'dedication array is not dense')
  for _, id in ipairs(values) do
    local row = GameInfo.CommemorationTypes[integer(id)]
    assert(row and type(row.CommemorationType) == 'string'
      and string.match(row.CommemorationType, '^[A-Z0-9_]+$'),
      'native dedication definition unavailable')
    out[#out+1] = string.format('%s|%d|%s', kind, integer(row.Index), row.CommemorationType)
  end
end
boundary()
local eras = assert(Game.GetEras(), 'native era cache unavailable')
local era = integer(eras:GetCurrentEra())
local remaining = integer(eras:GetPlayerNumAllowedCommemorations(pid))
local age = 'normal'
if boolean(eras:HasHeroicGoldenAge(pid)) then age = 'heroic'
elseif boolean(eras:HasGoldenAge(pid)) then age = 'golden'
elseif boolean(eras:HasDarkAge(pid)) then age = 'dark' end
if era == 0 or turn == startTurn then remaining = 0 end
local out = {string.format('%d|%d|%d|%s|%d', pid, turn, era, age, remaining)}
if remaining > 0 then append(out, 'choice', eras:GetPlayerCommemorateChoices(pid)) end
append(out, 'active', eras:GetPlayerActiveCommemorations(pid))
boundary()
return table.concat(out, '\n')
'''


def source():
    proof = _source(SOURCE)
    expected = {'COMMEMORATE': OPERATION, 'PARAM_COMMEMORATION_TYPE': PARAMETER,
                'ENDTURN_BLOCKING_COMMEMORATION_AVAILABLE': BLOCKER}
    if (proof['schema'] != 'civ6-host.xp2-stock-dedication-source.v1'
            or proof['image']['sha256'] != '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
            or {key: row['value_u32'] for key, row in proof['enums'].items()} != expected
            or proof['player_boundary']['no_generic_can_start'] is not True):
        raise ValueError('Stock XP2 dedication source identity differs')
    return proof


def source_dependencies(reference, *, execution_image):
    from . import session_configuration, xp2_turn_segment

    _require_image(execution_image)
    if reference != REFERENCE:
        raise ValueError('Dedications require the exact stock XP2 capture')
    proof = source()
    pins = {str(resolve_path(resource_root() / SOURCE[0]).resolve()): SOURCE[1]}
    for key in ('Expansion2_popup', 'Expansion2_action_panel'):
        row = proof['ui'][key]
        path = resolve_path(Path(row['path'])).resolve()
        if file_sha256(path) != row['sha256']:
            raise ValueError('Installed dedication UI source changed: ' + key)
        pins[str(path)] = row['sha256']
    for module in (__file__, contract.__file__, session_configuration.__file__):
        path = Path(module).resolve()
        pins[str(path)] = file_sha256(path)
    pins.update(xp2_turn_segment.source_dependencies(execution_image=execution_image))
    return pins


def _bound(saved, observation, *, active):
    b, c, p, identity = _owner(saved, active=active)
    if (getattr(saved, 'stock_dedications', False) is not True
            or b.load_abi.core_sha256 != XP2_CORE_SHA256 or b.captured_bundle.reference != REFERENCE
            or c.observation != observation):
        raise ValueError('Dedication query requires its exact stock XP2 player boundary')
    _require_image(getattr(b.core, '_civ6_host_execution_image', None))
    lifetime = getattr(saved, '_xp2_dedication_binding', None)
    if lifetime is None or lifetime[0] is not b.core or lifetime[1] is not p:
        from .session_configuration import read_saved_settings

        proof = source()
        rows = list(proof['paths'].values())
        for group in ('bindings', 'enums'):
            for entry in proof[group].values():
                rows.extend(row for row in entry.values() if type(row) is dict)
        for row in rows:
            raw = b.runtime.read(b.core._handle + int(row['rva'], 16), row['bytes'])
            if len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Live XP2 dedication binding differs at ' + row['rva'])
        setting = read_saved_settings(b.inputs.configuration)['turn_horizon']['start_turn']
        start_turn = setting['value']
        if (setting['present'] is not True or setting['variant_tag'] != 2
                or type(start_turn) is not int or not 0 <= start_turn < 2**31):
            raise ValueError('Dedication query requires the exact saved GAME_START_TURN integer')
        lifetime = saved._xp2_dedication_binding = b.core, p, start_turn
    return b, c, p, identity, lifetime[2]


def _decimal(raw):
    result = int(raw)
    if str(result).encode('ascii') != raw:
        raise ValueError('Noncanonical dedication integer')
    return result


def parse_state(raw, player_id, turn):
    if type(raw) is not bytes or not 0 < len(raw) < _LIMIT:
        raise ValueError('Dedication query receipt outside its bound')
    header, *lines = raw.split(b'\n')
    owner, revision_turn, era, age, remaining = header.split(b'|')
    value = dict(schema=contract.SCHEMA, player_id=_decimal(owner), turn=_decimal(revision_turn),
                 era_index=_decimal(era), age=age.decode('ascii'), remaining=_decimal(remaining),
                 choices=[], active=[])
    for line in lines:
        kind, index, symbol = line.split(b'|')
        target = {b'choice': 'choices', b'active': 'active'}.get(kind)
        if target is None:
            raise ValueError('Unknown native dedication row')
        value[target].append(dict(index=_decimal(index), type=symbol.decode('ascii')))
    return contract.validate_state(value, player_id, turn)


def _query(prefix, observation, *, start_turn):
    pid, turn = observation['player_id'], observation['turn']
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or not 0 <= turn < 2**31:
        raise ValueError('Invalid dedication query identity')
    variables = f'local pid, turn, startTurn = {pid}, {turn}, {start_turn}\n'.encode('ascii')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, variables + _QUERY,
                                       b'@xp2_dedication_player_cache', capacity=_LIMIT)
    return parse_state(raw, pid, turn)


def catalogue(saved, observation):
    b, c, p, identity, start_turn = _bound(saved, observation, active=False)
    c.explicit_dedications = None
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    state = _query(p, observation, start_turn=start_turn)
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    c.explicit_dedications = identity, c.sequence, deepcopy(observation), state
    return deepcopy(state)


@dataclass(frozen=True)
class _Permit:
    seal: object
    core: object
    context: int
    player: int
    index: int


def authorize_request(permit, core, context, player, operation, parameters, *,
                      core_sha256, submit, allow_empty):
    if (type(permit) is not _Permit or permit.seal is not _SEAL or core is not permit.core
            or context != permit.context or player != permit.player or operation != OPERATION
            or type(parameters) is not dict or parameters != {PARAMETER: permit.index}
            or core_sha256 != XP2_CORE_SHA256 or submit is not True or allow_empty is not False):
        raise ValueError('Missing exact XP2 dedication request permit')
    _require_image(getattr(core, '_civ6_host_execution_image', None))
    return 'COMMEMORATE'


def verify_effect(before, after, action):
    choices = {row['index']: row for row in before['choices']}
    expected = before['active'] + [choices[index] for index in action['indices']]
    if (before['era_index'] != after['era_index'] or before['age'] != after['age']
            or after['remaining'] != before['remaining'] - len(action['indices'])
            or after['active'] != expected):
        raise RuntimeError('Native dedication application differs from the confirmed selections')


def apply(saved, action, observation):
    from .native.native_player_observation import observe_player
    from .native.native_player_operation_request import request_player_operation
    contract.validate_action(action)
    b, c, p, identity, start_turn = _bound(saved, observation, active=True)
    record = getattr(c, 'explicit_dedications', None)
    if record is None or record[0] is not identity or record[1:3] != (c.sequence, observation):
        raise ValueError('Dedication confirmation does not belong to this decision')
    c.explicit_dedications = None
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    fresh = _query(p, observation, start_turn=start_turn)
    if fresh != record[3]:
        raise ValueError('Native dedication choices changed since the decision')
    contract.choose(fresh, contract.CANDIDATE, {'indices': action['indices']})

    count = c.publication_count
    hashes = []
    for index in action['indices']:
        permit = _Permit(_SEAL, b.core, b.context, fresh['player_id'], index)
        result = request_player_operation(b.core, b.context, fresh['player_id'], OPERATION,
            {PARAMETER: index}, core_sha256=XP2_CORE_SHA256, dedication_permit=permit)
        pending = p.actions.pending
        if (result.get('request_invoked') is not True or result.get('can_start') is not None
                or len(pending) != len(hashes) + 1 or pending[-1][:4] != _ARCHIVE_PREFIX):
            raise RuntimeError('Dedication request did not enqueue its native operation archive')
        hashes.append(sha256(pending[-1]).hexdigest())
    for expected in hashes:
        if not p.actions.pending or sha256(p.actions.pending[0]).hexdigest() != expected:
            raise RuntimeError('Native dedication request ordering changed')
        p.actions.deliver_one()
        p.deferred_events.drain_empty_receivers()
    p.view_publisher.publish()
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    observed = observe_player(p.runtime, p.ui_child, fresh['player_id'])
    after = _query(p, observed, start_turn=start_turn)
    if c.publication_count != count + 1 or (observed['player_id'], observed['turn']) != (
            fresh['player_id'], fresh['turn']):
        raise RuntimeError('Native dedication confirmation crossed its publication boundary')
    verify_effect(fresh, after, action)
    receipt = dict(action=deepcopy(action), native_archive_delivered=True,
                   native_archive_sha256=hashes, native_effect_readback=True, dedications_after=after)
    saved.emit('xp2_dedications_confirmed', **receipt)
    return dict(status='completed', observation=observed, receipt=receipt)

"""The expansion Great Works overviews' direct movement request."""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from struct import Struct

from civ6_host.contracts import city_buildings as contract
from . import xp1_city_buildings, xp2_city_buildings
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .execution_images import _PROFILE, _XP1_PROFILE
from .xp2_great_works_inventory import VIEW_CAPABILITY


_ENUMS = {
    'MOVE_GREAT_WORK': 0x291d387e,
    'PARAM_PLAYER_ONE': 0x0483191c,
    'PARAM_CITY_SRC': 0x262cb79e,
    'PARAM_CITY_DEST': 0xe5f2cf9b,
    'PARAM_BUILDING_SRC': 0x84dbad68,
    'PARAM_BUILDING_DEST': 0xb18e6fa8,
    'PARAM_GREAT_WORK_INDEX': 0xdc6e26b0,
    'PARAM_SLOT': 0x2baddf94,
}
OPERATION = _ENUMS['MOVE_GREAT_WORK']
_PARAMETERS = tuple(_ENUMS)[1:]
_HEADER = Struct('<6I')
_ENTRY = Struct('<IHH10sI')
_SEAL = object()
_NATIVE_SPANS = (
    (0x30c12a, 32, 'a4f70f9ee5b56963c5d0ec0a8a26522a199ed8114251dfa0288a81f9cba35f6b'),
    (0x30c1c0, 24, '6027372bd2204d4102e1bc9a227c4629a3b94d19fbc1c75f2c3185c1acd6ade2'),
    (0x30d02e, 157, 'ea2b9d2c18371e12497bfce14d3ff29c725e7baf2e19f02d2392e0e53704e9f5'),
    (0x30e6ed, 112, '12b14686ba09c1f6bf3059ffb73443dbf44aa9fb175011666f1d4c00c227f687'),
    (0x30e75d, 360, '9d56324989a7d59f727d61997a4018b02b04cd2085754b2a7ffa4e0b81cbc1bd'),
)


def enabled(saved):
    backend = saved.backend
    core_sha256 = backend.load_abi.core_sha256
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    if core_sha256 == XP1_CORE_SHA256:
        return (getattr(saved, 'xp1_city_buildings', False) is True
                and xp1_city_buildings.supports(backend.captured_bundle.reference, image))
    return (getattr(saved, 'xp2_city_buildings', False) is True
            and core_sha256 == XP2_CORE_SHA256
            and xp2_city_buildings.supports(backend.captured_bundle.reference, image))


def panel_with_commands(inventory, *, available):
    if inventory['schema'] not in contract.GREAT_WORK_TARGET_SCHEMAS or type(available) is not bool:
        raise ValueError('Great Work commands require the slot and target inventory')
    schema = (contract.GREAT_WORK_COMMANDS_SCHEMA if inventory['schema'] == contract.GREAT_WORK_TARGETS_SCHEMA
              else inventory['schema'])
    return dict(inventory, schema=schema, great_work_moves_available=available)


def public_panel(saved, inventory, *, can_act):
    if not enabled(saved):
        return inventory
    has_work = any(row['work'] is not None for row in inventory['great_work_slots'])
    ready = can_act and has_work and _verify_live(
        saved.backend, saved.prefix, inventory['player_id'], inventory['turn'])
    if saved.backend.load_abi.core_sha256 == XP1_CORE_SHA256:
        return dict(inventory, schema=contract.GREAT_WORK_XP1_COMMANDS_SCHEMA,
                    great_work_moves_available=ready)
    return panel_with_commands(inventory, available=ready)


def operation_parameters(player, action):
    contract.validate_great_work_action(action)
    if type(player) is not int or not 0 <= player < 64:
        raise ValueError('Invalid Great Work acting player')
    src, dest = action['source'], action['destination']
    return dict(zip((_ENUMS[name] for name in _PARAMETERS),
                    (player, src['city_id'], dest['city_id'], src['building_index'],
                     dest['building_index'], action['work_index'], dest['slot']), strict=True))


@dataclass(frozen=True)
class _Permit:
    seal: object
    core: object
    context: int
    player: int
    parameters: tuple


def authorize_request(permit, core, context, player, operation, parameters, *,
                      core_sha256, submit, allow_empty):
    image = {XP1_CORE_SHA256: _XP1_PROFILE, XP2_CORE_SHA256: _PROFILE}.get(core_sha256)
    if (type(permit) is not _Permit or permit.seal is not _SEAL or core is not permit.core
            or context != permit.context or player != permit.player or operation != OPERATION
            or image is None or getattr(core, '_civ6_host_execution_image', None) is not image
            or type(parameters) is not dict or tuple(parameters.items()) != permit.parameters
            or tuple(parameters) != tuple(_ENUMS[name] for name in _PARAMETERS)
            or parameters[_ENUMS['PARAM_PLAYER_ONE']] != player
            or submit is not True or allow_empty is not False):
        raise ValueError('Missing exact Great Work request permit')
    return 'MOVE_GREAT_WORK'


def verify_archive(payload, player, parameters):
    count = len(parameters)
    if (type(payload) is not bytes or len(payload) != _HEADER.size + count * _ENTRY.size
            or _HEADER.unpack_from(payload) != (0xc45de12f, player, OPERATION, 2, 0x80000001, count)):
        raise RuntimeError('Great Work operation archive has an unexpected header')
    actual = {}
    for key, marker, tag, reserved, value in _ENTRY.iter_unpack(payload[_HEADER.size:]):
        if marker != 0 or tag != 2 or reserved != bytes(10) or key in actual:
            raise RuntimeError('Great Work operation archive has an unexpected parameter entry')
        actual[key] = value
    if actual != parameters:
        raise RuntimeError('Great Work operation archive differs from the selected target')
    return sha256(payload).hexdigest()


def _verify_live(backend, prefix, player, turn):
    spans = _NATIVE_SPANS
    if backend.load_abi.core_sha256 == XP1_CORE_SHA256:
        from .xp1_great_work_move_source import source
        proof = source(backend.core._civ6_host_execution_image)
        spans = [(row['rva'], row['bytes'], row['sha256']) for row in proof['operation_spans'].values()]
    for rva, size, digest in spans:
        raw = backend.runtime.read(backend.core._handle + rva, size)
        if type(raw) is not bytes or len(raw) != size or sha256(raw).hexdigest() != digest:
            raise ValueError(f'Live Great Work operation differs at {rva:#x}')
    code = f'''
assert(Game.GetLocalPlayer()=={player} and Game.GetLocalObserver()=={player}
    and Game.GetCurrentGameTurn()=={turn},'Great Work perspective changed')
local player=Players[{player}]
assert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),
    'Great Work actor is not ready')
'''
    for key, value in _ENUMS.items():
        signed = value if value < 0x80000000 else value - 0x100000000
        code += f"assert(PlayerOperations.{key}=={signed},'Great Work enum changed')\n"
    code += f"""
assert(GameInfo and GameInfo.GameCapabilities,'Great Work capabilities unavailable')
if GameInfo.GameCapabilities['{VIEW_CAPABILITY}']==nil then return 'blocked' end
local allowed=Game.IsAllowStrategicCommands({player})
assert(type(allowed)=='boolean','Great Work command permission unavailable')
return allowed and 'ready' or 'blocked'
"""
    status = prefix.runtime.evaluate_text(prefix.ui_child, code.encode('ascii'),
                                          b'@expansion_great_work_command_scope', capacity=16)
    if status not in (b'ready', b'blocked'):
        raise RuntimeError('Unexpected Great Work command scope')
    return status == b'ready'


def verify_effect(before, after, action):
    def indices(panel):
        return {(row['city_id'], row['building_index'], row['slot']): (
            None if row['work'] is None else row['work']['index']) for row in panel['great_work_slots']}

    prior = indices(before)
    selection = tuple(tuple(action[field][key] for key in ('city_id', 'building_index', 'slot'))
                      for field in ('source', 'destination'))
    src, dest = selection
    if src not in prior or dest not in prior or (prior[src], prior[dest]) != (
            action['work_index'], action['target_work_index']):
        raise RuntimeError('Great Work movement lost its exact published source or destination')
    prior[src], prior[dest] = prior[dest], prior[src]
    if indices(after) != prior:
        raise RuntimeError('Great Work movement did not produce the selected move or swap')


def apply(saved, action, observation, *, borrowed=False):
    """Apply one public choice using the active saved owner and its native queue."""
    from .native.native_player_observation import observe_player
    from .native.native_player_operation_request import request_player_operation

    contract.validate_great_work_action(action)
    if not enabled(saved):
        raise ValueError('Great Work movement requires an admitted expansion owner')
    backend, continuation, prefix = saved.backend, saved.continuation, saved.prefix
    core_sha256 = backend.load_abi.core_sha256
    xp1 = core_sha256 == XP1_CORE_SHA256
    if borrowed and xp1:
        raise ValueError('Great Work movement in Rise and Fall requires the local human seat')
    read_panel = xp1_city_buildings.read if xp1 else xp2_city_buildings.read
    options = {} if xp1 else {'borrowed': borrowed}
    player, turn = observation['player_id'], observation['turn']
    if not borrowed and continuation.observation != observation:
        raise ValueError('Great Work command belongs to another player observation')
    refusal = dict(status='refused', observation=observation,
                   refusal_code='native_great_work_choice_changed')
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    before = read_panel(saved, observation, active=True, **options)
    if action not in contract.great_work_actions(panel_with_commands(before, available=True)):
        return refusal
    if not _verify_live(backend, prefix, player, turn):
        return dict(refusal, refusal_code='native_great_work_strategic_commands_blocked')
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    publications = continuation.publication_count
    parameters = operation_parameters(player, action)
    permit = _Permit(_SEAL, backend.core, backend.context, player, tuple(parameters.items()))
    result = request_player_operation(backend.core, backend.context, player, OPERATION, parameters,
        core_sha256=core_sha256, read=backend.runtime.read, great_work_permit=permit)
    if (result['request_invoked'] is not True or result['can_start'] is not None
            or len(prefix.actions.pending) != 1):
        raise RuntimeError('Great Work request did not enqueue exactly one native archive')
    digest = verify_archive(bytes(prefix.actions.pending[0]), player, parameters)
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    if continuation.trade_feedback is not None and continuation.trade_feedback.events:
        continuation.flush_trade_feedback()
    if prefix.deferred_events.pending:
        raise RuntimeError('Great Work command left deferred events unconsumed')
    prefix.view_publisher.publish()
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    observed = observe_player(prefix.runtime, prefix.ui_child, player)
    if (continuation.publication_count != publications + 1
            or (observed['player_id'], observed['turn']) != (player, turn)):
        raise RuntimeError('Great Work command crossed its native publication boundary')
    after = read_panel(saved, observed, active=True, **options)
    verify_effect(before, after, action)
    receipt = dict(action=deepcopy(action), native_archive_sha256=digest,
                   native_archive_delivered=True, native_effect_readback=True)
    stage = 'native_xp1_great_work_move_effect' if xp1 else 'native_xp2_great_work_move_effect'
    saved.emit(stage, player_id=player, turn=turn, **receipt)
    return dict(status='completed', observation=observed, receipt=receipt, refusal_code=None)

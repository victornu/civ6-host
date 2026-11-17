"""Gathering Storm air strikes, deployment and rebasing."""

from functools import partial
from hashlib import sha256
from struct import pack

from civ6_host.contracts import air_operations, war_confirmation
from . import xp2_bbg_inputs, xp2_bundle_inputs
from .configuration_profiles import _source
from .execution_images import _PROFILE
from .native.native_player_observation import observe_player
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-air-operations-source.json',
          '772a1aca6c783765ac5740e9d6a2794d8d23045dccf79eff3beaec8a930a9376')
ATTACK_SOURCE = ('evidence/host-xp2-air-attack-source.json',
                 '56a795e5320dbd32f9d3ef73e9acaf8bb8dece9fc6006b960b00a3f2a134baf9')
REFUSED = 'native_air_operation_unavailable'
SUBMITTED = 'native_air_operation_effect_unconfirmed'
WAR_PENDING = 'native_air_attack_war_confirmation_pending'
_LIMIT = 192 * 1024
_MODES = {'DEPLOY': (336935588, 'INTERFACEMODE_DEPLOY'),
          'REBASE': (-1054550409, 'INTERFACEMODE_REBASE')}


def _proof(image):
    proof = _source(SOURCE)
    if (image is not _PROFILE or proof['schema'] != 'civ6-host.xp2-air-operations.source.v1'
            or dict(proof['image']) != dict(id=image.id, sha256=image.image_sha256)
            or dict(proof['operations']) != _MODES):
        raise ValueError('Air operations require the exact Gathering Storm image')
    return proof


def _attack_proof(image):
    proof = _source(ATTACK_SOURCE)
    parent = proof['parent']
    if (image is not _PROFILE or proof['schema'] != 'civ6-host.xp2-air-attack.source.v1'
            or proof['image_sha256'] != image.image_sha256
            or (parent['path'], parent['sha256']) != SOURCE
            or proof['operation'] != (526596894, 'INTERFACEMODE_AIR_ATTACK')
            or proof['shared_coordinate_archive'] is not True
            or proof['war_only_on_native_visible_plot'] is not True
            or proof['prompt_requests_no_attack'] is not True):
        raise ValueError('Air attack source differs from the owned aircraft and war routes')
    return proof


def source_dependencies(reference, image):
    proof = _proof(image)
    attack = _attack_proof(image)
    if reference not in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE):
        raise ValueError('Air operations require the captured stock or BBG 7.5.1 rules')
    capture, = (row for row in proof['captures']
                if (row['reference']['path'], row['reference']['sha256']) == reference)
    scripts = proof['ui_files'][0 if reference == xp2_bbg_inputs.REFERENCE else 1:]
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]), dict(path=ATTACK_SOURCE[0], sha256=ATTACK_SOURCE[1]),
            dict(path=image.path, sha256=image.image_sha256), attack['popup'],
            capture['reference'], capture['database'], *scripts]
    return {str(resolve_path(resource_root()/row['path']).resolve(strict=True)): row['sha256'] for row in rows}


def verify_live(base, read, image):
    proof = _proof(image)
    attack = _attack_proof(image)
    for rva, target in (*proof['table_slots'], *attack['table_slots']):
        if read(base + rva, 8) != pack('<Q', base + target):
            raise ValueError('Live air-operation descriptor differs')
    for span in (*proof['spans'].values(), *attack['spans']):
        raw = read(base + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live air-operation source differs at ' + hex(span['rva']))


def bind(saved):
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    if (core is None or prefix is not backend.prefix or prefix.core is not core
            or getattr(saved, 'war_source_sha256', None) is None):
        raise ValueError('Air operations require their exact live owner')
    verify_live(core._handle, backend.runtime.read, getattr(core, '_civ6_host_execution_image', None))
    saved._xp2_air_operations_core = core


def enabled(saved):
    core = getattr(saved, '_xp2_air_operations_core', None)
    return core is not None and core is saved.backend.core


_BODY = br'''
local function number(value, maximum)
    assert(type(value) == 'number' and value % 1 == 0 and value >= 0 and value <= maximum,
           'invalid air operation integer')
    return string.format('%.0f', value)
end
local function active()
    assert(Game.GetLocalPlayer() == pid and Game.GetLocalObserver() == pid
           and Game.GetCurrentGameTurn() == turn, 'stale air operation perspective')
    local player = assert(Players[pid])
    return player, player:IsTurnActive() == true and player:IsTurnActiveComplete() == true
end
local player, ready = active()
local hashes = {DEPLOY=336935588, REBASE=-1054550409, AIR_ATTACK=526596894}
assert(UnitOperationTypes.PARAM_X == 0x53777b05 and UnitOperationTypes.PARAM_Y == 0x4a6c4a44,
       'air operation coordinate parameters changed')
local function operation(name)
    local row = assert(GameInfo.UnitOperations['UNITOPERATION_' .. name])
    assert(row.Hash == UnitOperationTypes[name] and row.VisibleInUI == true
           and row.InterfaceMode == 'INTERFACEMODE_' .. name, 'air operation source changed')
    assert(row.Hash == hashes[name], 'air operation hash changed')
    return row
end
local function shown(unit, op, name)
    local moves = unit:GetMovesRemaining()
    assert(type(moves) == 'number' and moves >= 0, 'invalid air unit movement')
    if moves == 0 then return {} end
    local result = UnitManager.CanStartOperation(unit, op, nil, true)
    assert(type(result) == 'boolean', 'invalid air operation visibility')
    if not result then return {} end
    local enabled = UnitManager.CanStartOperation(unit, op, nil, false, OperationResultsTypes.NO_TARGETS)
    assert(type(enabled) == 'boolean', 'invalid air operation panel availability')
    if not enabled then return {} end
    local targets = UnitManager.GetOperationTargets(unit, op)
    assert(type(targets) == 'table', 'air operation targets unavailable')
    local plots = targets[UnitOperationResults.PLOTS] or {}
    assert(type(plots) == 'table' and #plots <= Map.GetPlotCount(), 'invalid air operation targets')
    if name ~= 'AIR_ATTACK' or #plots == 0 then return plots end
    local modifiers = targets[UnitOperationResults.MODIFIERS]
    local targetType = UnitOperationResults.MODIFIER_IS_TARGET
    assert(type(modifiers) == 'table' and #modifiers == #plots and type(targetType) == 'number',
           'air attack target modifiers changed')
    local highlighted = {}
    for ix, modifier in ipairs(modifiers) do
        if modifier == targetType then highlighted[#highlighted+1] = plots[ix] end
    end
    return highlighted
end
local function destination(id)
    number(id, Map.GetPlotCount() - 1)
    local plot = assert(Map.GetPlotByIndex(id))
    assert(plot:GetIndex() == id, 'air operation destination changed')
    return {[UnitOperationTypes.PARAM_X]=plot:GetX(), [UnitOperationTypes.PARAM_Y]=plot:GetY()}
end
local function legal(unit, operation, parameters)
    local result = UnitManager.CanStartOperation(unit, operation, nil, parameters)
    assert(type(result) == 'boolean', 'invalid air operation legality')
    return result
end
local function defender(unit, parameters)
    local x, y = parameters[UnitOperationTypes.PARAM_X], parameters[UnitOperationTypes.PARAM_Y]
    local visible = PlayersVisibility[pid]:IsVisible(x, y)
    assert(type(visible) == 'boolean', 'invalid air attack visibility')
    if not visible then return nil end
    local changes = CombatManager.IsAttackChangeWarState(unit:GetComponentID(), x, y)
    if changes == nil then return nil end
    assert(type(changes) == 'table' and #changes <= 64, 'invalid air attack war changes')
    if #changes == 0 then return nil end
    number(changes[1], 63)
    assert(changes[1] ~= pid, 'air attack war target equals the actor')
    return changes[1]
end
'''

_CATALOGUE = br'''
assert(ready, 'air operation player is waiting')
local rows = {number(pid, 63) .. '|' .. number(turn, 2147483647)}
local units = 0
for _, unit in player:GetUnits():Members() do
    units = units + 1
    assert(units <= 4096 and unit:GetOwner() == pid, 'foreign or unbounded air unit')
    for _, name in ipairs({'AIR_ATTACK', 'DEPLOY', 'REBASE'}) do
        local op = operation(name).Hash
        local seen = {}
        for _, id in ipairs(shown(unit, op, name)) do
            local parameters = destination(id)
            if not seen[id] and ((name == 'AIR_ATTACK' and defender(unit, parameters) ~= nil)
                    or legal(unit, op, parameters)) then
                assert(#rows <= 4096, 'air operation choices exceed their bound')
                rows[#rows+1] = table.concat({name, number(unit:GetID(), 4294967295), number(id, 16383),
                    number(parameters[UnitOperationTypes.PARAM_X], 16383),
                    number(parameters[UnitOperationTypes.PARAM_Y], 16383)}, '|')
            end
            seen[id] = true
        end
    end
end
active()
return table.concat(rows, '\n')
'''

_REQUEST = br'''
if not ready then return 'refused' end
local unit = player:GetUnits():FindID(unitID)
if unit == nil or unit:GetOwner() ~= pid then return 'refused' end
local row = operation(name)
assert(row.Index == operationIndex, 'air operation opcode changed')
for _, id in ipairs(shown(unit, row.Hash, name)) do
    if id == plotID then
        local parameters = destination(id)
        if parameters[UnitOperationTypes.PARAM_X] ~= targetX or parameters[UnitOperationTypes.PARAM_Y] ~= targetY
                then return 'refused' end
        if name == 'AIR_ATTACK' then
            local target = defender(unit, parameters)
            if target ~= nil then
                local warType = WarTypes.SURPRISE_WAR
                assert(type(warType) == 'number' and warType % 1 == 0
                       and warType >= -2147483648 and warType <= 4294967295, 'invalid air attack war type')
                return table.concat({'war', number(target, 63), string.format('%.0f', warType)}, '|')
            end
        end
        if not legal(unit, row.Hash, parameters) then return 'refused' end
        local _, stillReady = active()
        if not stillReady then return 'refused' end
        local result = 'submitted'
        if name == 'AIR_ATTACK' then result = result .. '|' .. number(unit:GetAttacksRemaining(), 2147483647) end
        UnitManager.RequestOperation(unit, row.Hash, parameters)
        return result
    end
end
return 'refused'
'''

_ATTACKS = br'''
local unit = player:GetUnits():FindID(unitID)
if unit == nil then return 'absent' end
assert(unit:GetOwner() == pid, 'foreign air unit attack count')
return number(unit:GetAttacksRemaining(), 2147483647)
'''


def _source_for(observation, constants, body):
    return (f"local pid, turn = {observation['player_id']}, {observation['turn']}\n".encode('ascii')
            + constants + _BODY + body)


def read(saved, observation, *, borrowed=False):
    if borrowed:
        from .xp1_session_view import _borrowed_xp2_reference
        _borrowed_xp2_reference(saved, observation['player_id'])
    else:
        saved._check_query()
    if not enabled(saved):
        raise ValueError('Air operation source is not bound')
    prefix = saved.prefix
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _source_for(observation, b'', _CATALOGUE),
                                       b'@public_air_operations', capacity=_LIMIT+1)
    if type(raw) is not bytes or not 0 < len(raw) <= _LIMIT:
        raise ValueError('Invalid native air operation frame')
    header, *lines = raw.decode('ascii').split('\n')
    if header != f"{observation['player_id']}|{observation['turn']}" or len(lines) > 4096:
        raise ValueError('Air operation catalogue crossed its actor or turn')
    result = []
    for line in lines:
        name, *numbers = line.split('|')
        keys = ('unit_id', 'plot_id', 'x', 'y')
        values = tuple(int(value) for value in numbers)
        if [str(value) for value in values] != numbers or len(values) != len(keys):
            raise ValueError('Invalid air operation destination')
        action = dict(kind=air_operations.KIND, operation=name, **dict(zip(keys, values, strict=True)))
        result.append(air_operations.validate(action, observation))
    return sorted(result, key=lambda row: (row['unit_id'], row['operation'], row['plot_id']))


def require_archive(payload, *, actor, action, opcode):
    expected = pack('<IHH8I', 0x8c0f3f36, actor, 1, action['unit_id'], opcode, 0xffffffff,
                    0, 1, action['x'], action['y'], 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Air operation archive differs from its exact actor, opcode or coordinates')


def _attack_count(raw):
    if type(raw) is not bytes or not raw.isdigit() or not 0 <= int(raw) <= 2147483647:
        raise ValueError('Invalid native air attack count')
    return int(raw)


def _retain_war_prompt(saved, before, action, marker):
    actor = before['player_id']
    prompts = saved.continuation.world_input_prompts
    if (action['operation'] != air_operations.ATTACK or saved.war_source_sha256 is None
            or prompts.get(actor) is not None or saved.prefix.actions.pending):
        raise ValueError('Air attack cannot retain this war prompt')
    _, defender, war_type = marker.split(b'|')
    prompt = war_confirmation.validate_prompt(dict(
        attacking_player=actor, defending_player=int(defender), war_type=int(war_type)), actor)
    prompts[actor] = prompt
    return dict(status='pending', refusal_code=WAR_PENDING, observation=before,
                receipt=dict(action=action, war_prompt=prompt, archive_sha256=None))


def apply(saved, action, before):
    air_operations.validate(action, before)
    saved._check_active()
    if not enabled(saved):
        raise ValueError('Air operation source is not bound')
    prefix, token = saved.prefix, saved.continuation
    if token.transport is not prefix.actions:
        raise ValueError('Air operation lost its exact command transport')
    actor, turn = before['player_id'], before['turn']
    name = f"local name = '{action['operation']}'\n".encode('ascii')
    index_source = _source_for(before, name, b'return number(operation(name).Index, 2047)')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, index_source, b'@air_operation_index', capacity=16)
    if type(raw) is not bytes or not raw.isdigit() or not 0 <= int(raw) <= 2047:
        raise ValueError('Invalid native air operation index')
    opcode = int(raw)
    arguments = (action['unit_id'], action['plot_id'], action['x'], action['y'], opcode)
    constants = name + ('local unitID, plotID, targetX, targetY, operationIndex = %d,%d,%d,%d,%d\n'
                        % arguments).encode('ascii')
    command = _source_for(before, constants, _REQUEST)
    is_attack = action['operation'] == air_operations.ATTACK
    with token.transport.require_xp2_single_archive(partial(require_archive, actor=actor, action=action,
                                                           opcode=opcode), allow_no_archive=True):
        marker = prefix.runtime.evaluate_text(prefix.ui_child, command, b'@air_operation_request', capacity=32)
        if type(marker) is not bytes:
            raise RuntimeError('Air operation returned an invalid native status')
        if marker == b'refused':
            if prefix.actions.pending:
                raise RuntimeError('Refused air operation left a native archive')
            return dict(status='refused', refusal_code=REFUSED, observation=before)
        if marker.startswith(b'war|'):
            return _retain_war_prompt(saved, before, action, marker)
        attacks_before = None
        if is_attack and marker.startswith(b'submitted|'):
            attacks_before = _attack_count(marker.removeprefix(b'submitted|'))
            marker = b'submitted'
        if is_attack and attacks_before is None:
            raise RuntimeError('Air attack did not capture its native attack count')
        if marker != b'submitted' or len(prefix.actions.pending) != 1:
            raise RuntimeError('Air operation did not enqueue exactly one native archive')
        archive_sha = sha256(prefix.actions.pending[0]).hexdigest()
        prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    if token.trade_feedback is not None and token.trade_feedback.events:
        token.flush_trade_feedback()
    prefix.view_publisher.publish()
    token.transport.require_empty_native_queue()
    after = observe_player(prefix.runtime, prefix.ui_child, actor)
    if (after['player_id'], after['turn']) != (actor, turn):
        raise RuntimeError('Air operation crossed its actor or turn')
    def position(observation):
        return next(((row['x'], row['y']) for row in observation['units']
                     if (row['owner'], row['id']) == (actor, action['unit_id'])), None)

    if is_attack:
        code = _source_for(before, constants, _ATTACKS)
        raw = prefix.runtime.evaluate_text(prefix.ui_child, code, b'@air_attacks_after', capacity=16)
        confirmed = raw != b'absent' and _attack_count(raw) < attacks_before
    else:
        target = action['x'], action['y']
        confirmed = position(before) != target and position(after) == target
    return dict(status='completed' if confirmed else 'submitted',
                refusal_code=None if confirmed else SUBMITTED, observation=after,
                receipt=dict(action=action, archive_sha256=archive_sha, effect_observed=confirmed))

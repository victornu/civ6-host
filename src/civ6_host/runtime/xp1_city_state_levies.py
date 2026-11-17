"""Native expansion city-state military levy choices and effects."""

from hashlib import sha256

from civ6_host.contracts import city_state_levies as contract
from .configuration_profiles import XP2_CORE_SHA256, _source
from .native import native_envoy_actions
from .paths import resource_root
from .xp1_city_state_envoys import ACTION_SOURCE, action_source, bind_actions
from .xp1_governors_source import _path, _verify_live


SOURCE = ('evidence/host-xp1-installed-city-state-levy-source.json',
          '6f1d2e56794e870451ab6c8fc1103ba677fdd21970ddb1758f95873d333c64ac')
UNIT_SOURCE = ('evidence/host-xp1-installed-unit-levy-timers-source.json',
               '59f7d5d82dccdec2d0cce6f0011ab1fabc3535cd971502c9be866d186bbfd742')
UNIT_BINDING_SOURCE = ('evidence/host-xp1-unit-levy-lua-binding-correction.json',
                       'cab53b04e181bd683321b089e098d7a9f29b03cef1a086b64003468972c72cbd')
UNIT_CONFIGURATION_SOURCE = ('evidence/host-xp1-unit-levy-configuration-source.json',
                             '0a8ce8c27fb4d7c5529faed8da8aed4be1eb0e33c98143385f10e3f5d4a32ee7')
_UNIT_UI_SHA256 = '26f056a54b9c0f8410af4d05721ab9584740f35906424974fed58e984cced0ea'
_CAPACITY = 4096
_UNIT_CAPACITY = 384 * 1024


def source(image):
    parent = action_source(image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-city-state-levy.source.v1'
            or proof['image'] != parent['image'] or proof['official_bundle'] != parent['official_bundle']
            or (proof['parent']['path'], proof['parent']['sha256']) != ACTION_SOURCE
            or proof['ui']['sha256'] != native_envoy_actions.UI_SHA256
            or set(proof['bindings']) != {'CanLevyMilitary', 'GetLevyMilitaryCost',
                'GetLevyTurnLimit', 'GetLevyTurnCounter', 'GetSuzerain', 'HasCapability'}
            or proof['constants'] != {'operation': 0xe6e2dbb2, 'target_key': 0x0483191c,
                                      'player_archive': 3294486831}
            or proof['contract'] != dict(requires_military_capability=True,
                player_visible_met_minors=True, native_eligibility=True,
                gold_charge_uses_fixed_point_shift=8, requires_native_treasury_and_control_readback=True)):
        raise ValueError('Rise and Fall city-state levy source differs')
    return proof


def source_dependencies(image):
    proof = source(image)
    unit = unit_source(image, proof)
    unit_binding_source(unit)
    configuration = unit_configuration_source(unit)
    return {str((resource_root() / SOURCE[0]).resolve()): SOURCE[1],
            str((resource_root() / UNIT_SOURCE[0]).resolve()): UNIT_SOURCE[1],
            str((resource_root() / UNIT_BINDING_SOURCE[0]).resolve()): UNIT_BINDING_SOURCE[1],
            str((resource_root() / UNIT_CONFIGURATION_SOURCE[0]).resolve()): UNIT_CONFIGURATION_SOURCE[1],
            str(_path(proof['ui'])): proof['ui']['sha256'],
            str(_path(unit['ui'])): unit['ui']['sha256'],
            str(_path(configuration['executable'])): configuration['executable']['sha256']}


def unit_source(image, parent=None):
    parent = source(image) if parent is None else parent
    proof = _source(UNIT_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-unit-levy-timers.source.v1'
            or proof['image'] != parent['image'] or proof['official_bundle'] != parent['official_bundle']
            or (proof['parent']['path'], proof['parent']['sha256']) != SOURCE
            or proof['ui']['sha256'] != _UNIT_UI_SHA256
            or set(proof['bindings']) != {'GetCombat', 'GetOwner', 'GetOriginalOwner', 'GetProperty',
                                          'FindID', 'GetInfluence', 'IsUnitVisible'}
            or set(proof['expiry']) != {'counter_and_notification', 'return_control'}
            or proof['contract'] != dict(official_ui_flag=True, observes_only_owned_or_visible_units=True,
                property_keys=('LEVY_TURN', 'LEVY_DURATION'), city_state_counter_fallback=True,
                numeric_countdown_includes_zero=True, native_expiration_mutation_in_host=False,
                shared_notification_kind=0xf2f69b23)):
        raise ValueError('Rise and Fall unit levy flag source differs')
    return proof


def unit_configuration_source(parent):
    proof = _source(UNIT_CONFIGURATION_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-unit-levy-configuration-source.v1'
            or proof['image'] != parent['image']
            or (proof['parent']['path'], proof['parent']['sha256']) != UNIT_SOURCE
            or proof['contract'] != dict(first_index=0, count=64, original_owner_identity_from_native_unit=True,
                origin_for_units_with_visible_levy_flag_only=True, player_names_read=False,
                no_configuration_table_created=True)):
        raise ValueError('Rise and Fall levy flag configuration source differs')
    return proof


def unit_binding_source(parent):
    proof = _source(UNIT_BINDING_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-unit-levy-lua-binding-correction.source.v1'
            or proof['image'] != parent['image']
            or (proof['parent']['path'], proof['parent']['sha256']) != UNIT_SOURCE
            or proof['bindings'].keys() != parent['bindings'].keys()
            or proof['contract'] != dict(builder_precedes_public_table_assignment=True,
                following_builder_is_next_method=True, distinct_unit_and_player_registrations=True)):
        raise ValueError('Rise and Fall unit levy Lua bindings differ')
    for name, row in proof['bindings'].items():
        prior = parent['bindings'][name]
        if (row['following_callback_in_prior_evidence'] != prior['callback']
                or row['callback']['rva'] == prior['callback']['rva']
                or not row['registration']['rva'] < prior['registration']['rva']
                    < row['registration']['rva'] + row['registration']['bytes']):
            raise ValueError(f'Rise and Fall levy Lua registration differs for {name}')
    return proof


def _bind(saved, *, active):
    if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256:
        from . import xp2_city_state_levies as xp2
        proof = xp2.bind_owner(saved, active=active)
        return 'xp2', dict(proof['constants'], player_archive=xp2.PLAYER_OPERATION_ARCHIVE), xp2.OPERATION_SOURCE
    bind_actions(saved, active=active)
    core = saved.backend.core
    proof = source(core._civ6_host_execution_image)
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp1_city_state_levy_lifetime', None) != lifetime:
        spans = [span for row in proof['bindings'].values() for span in row.values()]
        spans.extend(proof['operations'].values())
        _verify_live(core._handle, saved.backend.runtime.read, spans)
        saved._xp1_city_state_levy_lifetime = lifetime
    return 'xp1', proof['constants'], SOURCE


def query_source(player_id, turn, *, require_strategic=True):
    return native_envoy_actions._common(player_id, turn, require_strategic=require_strategic) + b"""
local enabled=boolean(GameCapabilities.HasCapability("CAPABILITY_MILITARY"))
local rows={dec(pid)..":"..dec(expectedTurn)..":"..bit(enabled)}
if enabled then
 for _,visible in ipairs(visibleTargets()) do
  local target=visible.target
  local other=assert(Players[target]:GetInfluence(), 'missing city-state influence')
  local ownActive=other:GetLevyTurnCounter()>=0 and other:GetSuzerain()==pid
  local canLevy=boolean(influence:CanLevyMilitary(target))
  local cost,limit="-","-"
  if not ownActive then
   cost=dec(integer(influence:GetLevyMilitaryCost(target),2147483647))
   limit=dec(integer(other:GetLevyTurnLimit(),2147483647))
  end
  rows[#rows+1]=dec(target)..":"..bit(canLevy)..":"..cost..":"..limit..":"..bit(ownActive)
 end
end
context()
return table.concat(rows,"|")
"""


def parse(raw, player_id, turn):
    if type(raw) is not bytes or not 0 < len(raw) < _CAPACITY:
        raise ValueError('Unbounded city-state levy wire')
    header, *rows = raw.decode('ascii').split('|')
    stem = f'{player_id}:{turn}:'
    if header not in (stem + '0', stem + '1'):
        raise ValueError('Foreign city-state levy wire')
    result = dict(schema=contract.SCHEMA, player_id=player_id, turn=turn,
                  military_enabled=header.endswith(':1'), city_states=[])
    number = native_envoy_actions._number
    for row in rows:
        target, can_levy, cost, limit, active = row.split(':')
        result['city_states'].append(dict(player_id=number(target, 'levy target', 63),
            can_levy=bool(number(can_levy, 'levy eligibility', 1)),
            gold_cost=None if cost == '-' else number(cost, 'levy cost'),
            turn_limit=None if limit == '-' else number(limit, 'levy turn limit'),
            own_levy_active=bool(number(active, 'own active levy', 1))))
    return contract.validate(result, player_id, turn)


def snapshot(saved, observation, *, active=False):
    profile, _, _ = _bind(saved, active=active)
    pid, turn = observation['player_id'], observation['turn']
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child, query_source(pid, turn, require_strategic=profile == 'xp1'),
                                  f'@{profile}_city_state_levies'.encode('ascii'), capacity=_CAPACITY)
    return parse(raw, pid, turn)


def catalogue(saved, observation, *, active=False):
    result = snapshot(saved, observation, active=active)
    saved.continuation.explicit_city_state_levies = result
    return result


_UNIT_QUERY = b"""
local function checkPerspective()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
        Game.GetCurrentGameTurn()==expectedTurn,'stale unit levy perspective')
end
local function integer(v)
 assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=2147483647,
        'invalid native levy flag integer')
 return v
end
checkPerspective()
local visibility=assert(PlayersVisibility[pid],'missing unit levy visibility')
local result={string.format('%d:%d',pid,expectedTurn)}
for _,row in ipairs(roster) do
 local owner,id,x,y=row[1],row[2],row[3],row[4]
 if owner==pid or visibility:IsVisible(x,y)==true then
  local unit=assert(Players[owner]:GetUnits():FindID(id),'stale public levy unit')
  if owner==pid or visibility:IsUnitVisible(unit)==true then
   assert(unit:GetOwner()==owner and unit:GetID()==id and
          unit:GetX()==x and unit:GetY()==y,'public levy unit identity differs')
   if not unit:IsDelayedDeath() and unit:GetCombat()>0 then
    local original=integer(unit:GetOriginalOwner())
    if original~=owner then
     local start=unit:GetProperty('LEVY_TURN')
     local duration=start~=nil and unit:GetProperty('LEVY_DURATION') or nil
     local remaining=-1
     if start~=nil and duration~=nil then
      remaining=integer(start)+integer(duration)-expectedTurn
     else
      local sourcePlayer=Players[original]
      local influence=sourcePlayer and sourcePlayer:GetInfluence()
      if influence~=nil then
       local counter=integer(influence:GetLevyTurnCounter())
       if counter>=0 and influence:GetSuzerain()==owner then
        remaining=integer(influence:GetLevyTurnLimit())-counter
       end
      end
     end
     if remaining>=0 then
      -- The official PlayerConfigurations registrar fills every index 0..63.
      local named=original>=0 and original<64
      result[#result+1]=string.format('%d:%.0f:%s:%d',owner,id,named and tostring(original) or '-',
                                       integer(remaining))
     end
    end
   end
  end
 end
end
checkPerspective()
return table.concat(result,'|')
"""


def unit_query_source(observation):
    pid, turn = native_envoy_actions._context(observation['player_id'], observation['turn'])
    roster = []
    for rows, own in ((observation['units'], True), (observation['visible_enemy_units'], False)):
        for row in rows:
            owner, unit_id, x, y = (row[field] for field in ('owner', 'id', 'x', 'y'))
            if (any(type(v) is not int for v in (owner, unit_id, x, y)) or not 0 <= owner <= 63
                    or (owner == pid) != own or not 0 <= unit_id <= 0xffffffff
                    or not 0 <= x < observation['width'] or not 0 <= y < observation['height']
                    or (not own and row['visible'] is not True)):
                raise ValueError('Invalid public roster for unit levy flags')
            roster.append((owner, unit_id, x, y))
    roster.sort()
    if len(roster) > contract.MAX_UNITS or len({row[:2] for row in roster}) != len(roster):
        raise ValueError('Unbounded or duplicated public roster for unit levy flags')
    rows = ','.join('{%d,%d,%d,%d}' % row for row in roster)
    return f'local pid,expectedTurn={pid},{turn}\nlocal roster={{{rows}}}\n'.encode('ascii') + _UNIT_QUERY


def parse_unit_flags(raw, observation):
    if type(raw) is not bytes or not 0 < len(raw) < _UNIT_CAPACITY:
        raise ValueError('Unbounded unit levy flag wire')
    pid, turn = observation['player_id'], observation['turn']
    header, *rows = raw.decode('ascii').split('|')
    if header != f'{pid}:{turn}':
        raise ValueError('Foreign unit levy flag wire')
    number = native_envoy_actions._number
    units = []
    for row in rows:
        owner, unit_id, original, remaining = row.split(':')
        units.append(dict(owner=number(owner, 'unit owner', 63),
                          unit_id=number(unit_id, 'unit ID', 0xffffffff),
                          original_owner=None if original == '-' else number(original, 'original owner', 63),
                          turns_remaining=number(remaining, 'remaining levy turns')))
    value = dict(schema=contract.UNIT_SCHEMA, player_id=pid, turn=turn, units=units)
    return contract.validate_unit_flags(value, pid, turn, observation=observation)


def unit_flags(saved, observation, *, active=False):
    core, prefix = saved.backend.core, saved.prefix
    if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256:
        from .xp2_city_state_levies import bind_owner
        bind_owner(saved, active=active)
        chunk = b'@xp2_unit_levies'
    else:
        chunk = b'@xp1_unit_levies'
        proof = unit_source(core._civ6_host_execution_image)
        lifetime = (core, prefix)
        if getattr(saved, '_xp1_unit_levy_lifetime', None) != lifetime:
            configuration = unit_configuration_source(proof)
            binding = unit_binding_source(proof)
            spans = [row[field] for row in binding['bindings'].values()
                     for field in ('registration', 'callback')]
            spans.extend(proof['expiry'].values())
            spans.append(configuration['core_registrar'])
            _verify_live(core._handle, saved.backend.runtime.read, spans)
            saved._xp1_unit_levy_lifetime = lifetime
    raw = prefix.runtime.evaluate_text(prefix.ui_child, unit_query_source(observation),
                                       chunk, capacity=_UNIT_CAPACITY)
    return parse_unit_flags(raw, observation)


def _verify_effect(before, after, target, cost):
    if (after['player_id'], after['turn']) != (before['player_id'], before['turn']):
        raise RuntimeError('Native levy crossed its player or turn boundary')
    old_units = {unit['id'] for unit in before['units']}
    new_units = {unit['id'] for unit in after['units']}
    controlled = sorted(new_units - old_units)
    if (not target['own_levy_active'] or target['can_levy'] or not controlled
            or not old_units <= new_units
            or after['economy']['gold'] != before['economy']['gold'] - cost):
        raise RuntimeError('Native levy did not charge the quoted gold and transfer military control')
    return dict(target_player_id=target['player_id'], gold_spent=cost,
                controlled_unit_ids=controlled)


def apply(saved, action, before, *, borrowed=None):
    from .native.native_player_observation import observe_player
    from .native.native_player_operation_request import request_player_operation

    contract.validate_action(action)
    profile, constants, operation_source = _bind(saved, active=True)
    reader = catalogue if borrowed is None else snapshot
    expected = saved.continuation.explicit_city_state_levies if borrowed is None else borrowed
    fresh = reader(saved, before, active=True)
    if expected != fresh or action not in contract.actions(fresh):
        raise RuntimeError('Military levy is stale or no longer offered')
    target_id = action['target_player_id']
    target, = (row for row in fresh['city_states'] if row['player_id'] == target_id)
    b, p = saved.backend, saved.prefix
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Military levy requires empty owned native queues')
    request = {}
    if profile == 'xp2':
        from .xp2_city_state_levies import request_permit
        if borrowed is None:
            request['levy_permit'] = request_permit(saved, before, action, fresh)
        else:
            request['levy_permit'] = request_permit(saved, before, action, fresh, borrowed=True)
    result = request_player_operation(b.core, b.context, before['player_id'],
        constants['operation'], {constants['target_key']: target_id}, core_sha256=b.load_abi.core_sha256,
        **request)
    if profile == 'xp1' and (not result['can_start'] or not result['request_invoked']):
        raise RuntimeError('Native CanStartPlayerOperation refused the military levy')
    if profile == 'xp2' and (result.get('request_invoked') is not True
                             or result.get('native_can_start_called') is not False
                             or result.get('source_qualified_request_only') != 'LEVY_MILITARY'):
        raise RuntimeError('Military levy did not use the official direct XP2 request')
    if (len(p.actions.pending) != 1 or
            bytes(p.actions.pending[0][:4]) != constants['player_archive'].to_bytes(4, 'little')):
        raise RuntimeError('Military levy did not emit its single native operation archive')
    if borrowed is not None:
        from .xp2_city_state_levies import validate_target_archive
        validate_target_archive(p.actions.pending[0], before['player_id'], constants['operation'], target_id)
    archive_sha256 = sha256(p.actions.pending[0]).hexdigest()
    p.actions.deliver_one()
    p.deferred_events.drain()
    p.view_publisher.publish()
    after = observe_player(p.runtime, p.ui_child, before['player_id'])
    observed = reader(saved, after, active=True)
    active, = (row for row in observed['city_states'] if row['player_id'] == target_id)
    effect = _verify_effect(before, after, active, target['gold_cost'])
    if profile == 'xp2':
        flags = unit_flags(saved, after, active=True)['units']
        transferred = {row['unit_id'] for row in flags
                       if row['owner'] == after['player_id'] and row['original_owner'] == target_id}
        if transferred != set(effect['controlled_unit_ids']):
            raise RuntimeError('Native levy did not expose the quoted city-state military as levied units')
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Military levy left pending native work')
    effect.update(native_archive_sha256=archive_sha256, native_effect_readback=True)
    saved.emit(f'{profile}_city_state_levy_effect_verified', source_sha256=operation_source[1], **effect)
    return dict(observation=after, effect=effect)

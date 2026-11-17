"""The inherited Gathering Storm city-state panel's direct peace command."""

import json
from pathlib import Path

from civ6_host.contracts import diplomacy_overview as contract
from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_envoys_source import UI_SOURCE


def source_dependencies(*, stock=False):
    official = _source(UI_SOURCE)
    files = official['files']
    if (official['schema'] != 'civ6-host.xp2-envoys-ui-source.v1'
            or official['chain'] != ('xp2_wrapper', 'xp2_parent', 'base')
            or files['base']['sha256'] != 'e56c37f20ac2446f42dfe00dab5564b9989d2a76915ff99c343f31269faddb0a'
            or not stock and (files['bbg_modinfo']['citystates_replacements']
                              or files['bbg_modinfo']['citystates_ui_files'])):
        raise ValueError('Gathering Storm city-state peace panel source differs')
    pins = {str(resolve_path(resource_root() / UI_SOURCE[0]).resolve()): UI_SOURCE[1]}
    pins.update((str(resolve_path(Path(row['path'])).resolve()), row['sha256'])
                for role, row in files.items() if not stock or role != 'bbg_modinfo')
    return pins


_PERSPECTIVE = b"""
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid
 and Game.GetCurrentGameTurn()==turn,'City-state peace perspective changed')
local actor=Players[pid]
assert(actor and actor:IsAlive() and actor:IsTurnActive() and actor:IsTurnActiveComplete(),
 'City-state peace actor is not ready')
"""

_PANEL = b"""
local function boolean(value)
 assert(type(value)=='boolean','Invalid native city-state peace flag')
 return value
end
local enabled=boolean(GameCapabilities.HasCapability('CAPABILITY_MILITARY'))
local rows={}
if enabled then
 local diplomacy=actor:GetDiplomacy()
 local minors=PlayerManager.GetAliveMinors()
 assert(type(minors)=='table' and #minors<=63,'Invalid native minor player list')
 for _,minor in ipairs(minors) do
  local target=minor:GetID()
  assert(type(target)=='number' and target%1==0 and target>=0 and target<64 and target~=pid,
   'Invalid native minor player ID')
  if boolean(diplomacy:HasMet(target)) then
   local influence=minor:GetInfluence()
   if influence and boolean(influence:CanReceiveInfluence()) then
    local atWar=boolean(diplomacy:IsAtWarWith(target))
    local canMakePeace=atWar and boolean(diplomacy:CanMakePeaceWith(target))
    rows[#rows+1]={id=target,atWar=atWar,canMakePeace=canMakePeace}
   end
  end
 end
end
table.sort(rows,function(a,b) return a.id<b.id end)
local entries={}
for _,row in ipairs(rows) do
 entries[#entries+1]='{"player_id":'..row.id..',"at_war":'..tostring(row.atWar)..
  ',"can_make_peace":'..tostring(row.canMakePeace)..'}'
end
return '{"military_enabled":'..tostring(enabled)..',"targets":['..table.concat(entries,',')..']}'
"""

_OPERATION = b"""
assert(Game.IsAllowStrategicCommands(pid)==true,'Native strategic commands unavailable')
local function word(n)
 assert(type(n)=='number' and n%1==0 and n>=-2147483648 and n<=4294967295,
  'Invalid native city-state peace operation key')
 return string.format('%.0f',n%4294967296)
end
return '['..word(PlayerOperations.DIPLOMACY_MAKE_PEACE)..','..word(PlayerOperations.PARAM_PLAYER_ONE)..
 ','..word(PlayerOperations.PARAM_PLAYER_TWO)..']'
"""


def _source_at(pid, turn, body):
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or not 0 <= turn <= 0xffffffff:
        raise ValueError('Invalid city-state peace player or turn')
    return f'local pid,turn={pid},{turn}\n'.encode('ascii') + _PERSPECTIVE + body


def panel(prefix, pid, turn):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _source_at(pid, turn, _PANEL),
        b'@xp2_city_state_peace_panel', capacity=8192)
    if type(raw) is not bytes or not raw or len(raw) >= 8192:
        raise ValueError('Invalid native city-state peace panel size')
    return contract.validate_city_state_peace(json.loads(raw), pid)


def apply(saved, backend, prefix, action, overview):
    if (overview['schema'] not in contract.CITY_STATE_SCHEMAS
            or action not in contract.candidates(overview)):
        return dict(status='refused', requested_action=action, pending_statement_retained=False,
                    refusal_code='native_city_state_peace_unavailable')
    return apply_panel(saved, backend, prefix, action, overview['player_id'], overview['turn'],
                       overview['city_state_peace'])


def apply_panel(saved, backend, prefix, action, pid, turn, current):
    from .native.native_player_operation_request import request_player_operation
    from .xp2_world_war import verify_minor_archive

    refusal = dict(status='refused', requested_action=action, pending_statement_retained=False)
    if action not in contract.city_state_peace_actions(current, pid):
        return dict(refusal, refusal_code='native_city_state_peace_unavailable')
    target = action['target_player_id']
    continuation = saved.continuation
    continuation.transport.require_empty_native_queue()
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _source_at(pid, turn, _OPERATION),
        b'@xp2_city_state_peace_operation', capacity=64)
    if type(raw) is not bytes or not raw or len(raw) >= 64:
        raise ValueError('Invalid native city-state peace operation size')
    values = json.loads(raw)
    if (type(values) is not list or len(values) != 3
            or any(type(n) is not int or not 0 < n <= 0xffffffff for n in values)
            or values[1] == values[2]):
        raise ValueError('Invalid native city-state peace operation parameters')
    operation, player_one, player_two = values
    parameters = {player_one: pid, player_two: target}
    result = request_player_operation(backend.core, backend.context, pid, operation, parameters,
                                      read=backend.runtime.read, core_sha256=XP2_CORE_SHA256)
    if not result['request_invoked']:
        continuation.transport.require_empty_native_queue()
        return dict(refusal, refusal_code='native_can_start_city_state_peace_false')
    if len(prefix.actions.pending) != 1:
        raise RuntimeError('City-state peace did not produce one native player-operation archive')
    archive = bytes(prefix.actions.pending[0])
    verify_minor_archive(archive, pid, operation, parameters)
    prefix.actions.deliver_one()
    prefix.deferred_events.drain()
    prefix.view_publisher.publish()
    after = panel(prefix, pid, turn)
    row = next((row for row in after['targets'] if row['player_id'] == target), None)
    if row is None or row['at_war']:
        raise RuntimeError('City-state peace has no observed native diplomatic effect')
    saved.emit('native_xp2_city_state_peace_effect', player_id=pid, turn=turn, target_player_id=target,
               native_operation=result, archive_hex=archive.hex(), at_war_before=True, at_war_after=False,
               gameplay_effect_verified=True)
    return dict(status='completed', refusal_code=None, requested_action=action,
                pending_statement_retained=False, native_request_delivered=True)

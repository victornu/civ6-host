"""Stock XP2 unit-panel formations through the existing command archive."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from civ6_host.contracts import unit_formations as contract
from .execution_images import ExecutionImageProfile
from .native import native_saved_trade as wire
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path
from .source_verification import file_sha256
from .xp1_world_input import _owner
from .xp2_bundle_inputs import REFERENCE


SOURCE = ('evidence/host-xp2-stock-formation-source.json',
          'ec81971ac909043b08a4ef310616adc4dd57bc69fe33d60456f11809e5c15bf9')
CORE = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
LIMIT = 1024 * 1024


def source_dependencies(reference, execution_image):
    if (reference != REFERENCE or type(execution_image) is not ExecutionImageProfile
            or execution_image.image_sha256 != CORE):
        raise ValueError('Formation orders require the exact stock Gathering Storm capture and image')
    root = resource_root()
    path = resolve_path(root / SOURCE[0])
    proof = load_pinned_json(path, SOURCE[1])
    if (proof['schema'] != 'civ6-host.stock-xp2-unit-formation-source.v1'
            or proof['image']['image_sha256'] != execution_image.image_sha256
            or proof['image']['reference_core_sha256'] != execution_image.reference_core_sha256):
        raise ValueError('Formation getter source differs from the selected execution image')
    origin = proof['prior_source']
    frontier = load_pinned_json(root / origin['path'], origin['sha256'])['formation_source']
    capture = frontier['exact_capture']
    if (capture['path'], capture['sha256']) != reference or frontier['selected_unit_panel'][0] != 1609:
        raise ValueError('Formation commands differ from the exact stock unit panel')
    result = {str(path): SOURCE[1]}
    for row in (origin, capture, frontier['final_gameplay'], *frontier['installed_sources'],
                *frontier['ordered_selection'], *frontier['retained_registries']):
        selected = resolve_path(root / Path(row['path'])).resolve()
        if file_sha256(selected) != row['sha256']:
            raise ValueError('Formation source changed: ' + str(selected))
        result[str(selected)] = row['sha256']
    return result


LUA = wire.COMMON_LUA + """
local function snapshot()
 local p=ready()
 assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands unavailable')
 local commands=UnitCommandTypes
 local enter,leave=commands.ENTER_FORMATION,commands.EXIT_FORMATION
 local enter_def=GameInfo.UnitCommands.UNITCOMMAND_ENTER_FORMATION
 local leave_def=GameInfo.UnitCommands.UNITCOMMAND_EXIT_FORMATION
 assert(enter==-913294208 and leave==-50443187 and enter_def.Hash==enter and leave_def.Hash==leave
  and enter_def.VisibleInUI and leave_def.VisibleInUI,'formation definitions differ')
 local result={schema='civ6-host.unit-formations.v1',player_id=pid,turn=turn,units=array(),offers=array()}
 local choices={}
 local function offer(unit,command,partner,args)
  assert(#choices<4096,'formation choices exceed bound')
  local action={kind='unit_formation',unit_id=unit:GetID(),command=command,partner_id=partner}
  choices[#choices+1]={action=action,unit=unit,args=args}
 end
 for _,unit in p:GetUnits():Members() do
  assert(#result.units<4096 and unit:GetOwner()==pid,'foreign or unbounded formation roster')
  local id=int(unit:GetID(),'formation unit',0,4294967295)
  result.units[#result.units+1]={unit_id=id,count=int(unit:GetFormationUnitCount(),'formation count',0,4096),
   moves=finite(unit:GetFormationMovesRemaining()),max_moves=finite(unit:GetFormationMaxMoves()),
   formation_id=int(unit:GetFormationID(),'formation identity',-2147483648,2147483647)}
  local legal,targets=UnitManager.CanStartCommand(unit,enter,nil,true)
  if boolean(legal,'enter formation') and targets and targets[UnitCommandResults.UNITS] then
   local peers=targets[UnitCommandResults.UNITS]
   dense(peers,4096)
   for _,peer in ipairs(peers) do
    local player=assert(Players[peer.player],'formation partner player missing')
    local other=player:GetUnits():FindID(peer.id)
    if other then
     assert(other:GetOwner()==pid and peer.player==pid and other:GetID()==peer.id,
      'foreign formation partner is outside the admitted player roster')
     offer(unit,'enter',other:GetID(),{[commands.PARAM_UNIT_PLAYER]=other:GetOwner(),
                                     [commands.PARAM_UNIT_ID]=other:GetID()})
    end
   end
  end
  if boolean(UnitManager.CanStartCommand(unit,leave,true),'exit formation visibility')
     and boolean(UnitManager.CanStartCommand(unit,leave,false,true),'exit formation availability') then
   offer(unit,'exit',-1,nil)
  end
 end
 table.sort(result.units,function(a,b) return a.unit_id<b.unit_id end)
 table.sort(choices,function(a,b)
  a,b=a.action,b.action
  if a.unit_id~=b.unit_id then return a.unit_id<b.unit_id end
  if a.command~=b.command then return a.command<b.command end
  return a.partner_id<b.partner_id
 end)
 for _,choice in ipairs(choices) do result.offers[#result.offers+1]=choice.action end
 ready()
 return result,choices
end
"""


def source(pid, turn):
    wire.uint(pid, 'formation player', 63)
    wire.uint(turn, 'formation turn', 0x7fffffff)
    return f'local pid,turn={pid},{turn}\n'.encode('ascii') + LUA.encode('ascii')


def _native_catalogue(prefix, observation):
    pid, turn = observation['player_id'], observation['turn']
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(pid, turn) +
        b'local value=snapshot(); return encode(value)', b'@stock_unit_formations', capacity=LIMIT + 1)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded unit formation reply')
    state = json.loads(raw)
    public = deepcopy(state)
    for row in public['units']:
        identity = row.pop('formation_id')
        if type(identity) is not int or not -0x80000000 <= identity <= 0x7fffffff:
            raise ValueError('Invalid native formation identity')
    for action in public['offers']:
        if action['command'] == 'exit' and action['partner_id'] == -1:
            action['partner_id'] = None
    return state, contract.validate(public, pid, turn, observation=observation)


def _bound(saved, observation, *, active):
    owner = _owner(saved, active=active)
    b, c, _, _ = owner
    image = getattr(b.core, '_civ6_host_execution_image', None)
    if (getattr(saved, 'unit_formations', False) is not True or b.captured_bundle.reference != REFERENCE
            or type(image) is not ExecutionImageProfile or image.image_sha256 != CORE
            or c.observation != observation or observation['player_id'] != 0):
        raise ValueError('Formation query requires the exact live stock player perspective')
    return owner


def catalogue(saved, observation):
    b, c, p, identity = _bound(saved, observation, active=False)
    c.explicit_unit_formations = None
    sequence = c.sequence
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    state, public = _native_catalogue(p, observation)
    actual = _bound(saved, observation, active=False)
    if any(a is not b for a, b in zip(actual, (b, c, p, identity))) or sequence != c.sequence:
        raise ValueError('Formation catalogue crossed its native decision boundary')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    c.explicit_unit_formations = (identity, sequence, deepcopy(observation), state, public)
    return deepcopy(public)


def _request_source(action, state):
    actor = dict(action, partner_id=-1) if action['command'] == 'exit' else action
    return source(state['player_id'], state['turn']) + f"""
local observed,choices=snapshot()
assert(same(observed,{wire.literal(state)}),'formation catalogue changed')
local selected={wire.literal(actor)}
local matched=nil
for _,choice in ipairs(choices) do
 if same(choice.action,selected) then assert(not matched,'duplicate native choice'); matched=choice end
end
assert(matched,'formation choice unavailable')
if selected.command=='enter' then
 UnitManager.RequestCommand(matched.unit,UnitCommandTypes.ENTER_FORMATION,matched.args)
else
 UnitManager.RequestCommand(matched.unit,UnitCommandTypes.EXIT_FORMATION)
end
return 'submitted'
""".encode('ascii')


def _effect(action, before, after):
    old = {row['unit_id']: row for row in before['units']}
    new = {row['unit_id']: row for row in after['units']}
    unit_id, partner_id = action['unit_id'], action['partner_id']
    actor, previous = new[unit_id], old[unit_id]
    if action['command'] == 'exit':
        return previous['count'] > 1 and actor['count'] <= 1
    partner, previous_partner = new[partner_id], old[partner_id]
    return (actor['count'] > 1 and actor['count'] == partner['count']
            and actor['formation_id'] == partner['formation_id']
            and (previous['count'] <= 1 or previous_partner['count'] <= 1
                 or previous['formation_id'] != previous_partner['formation_id']))


def apply(saved, action, observation):
    contract.validate_action(action)
    b, c, p, identity = _bound(saved, observation, active=True)
    record = getattr(c, 'explicit_unit_formations', None)
    if (record is None or record[0] is not identity or record[1] != c.sequence
            or record[2] != observation or action not in contract.actions(record[4])):
        raise ValueError('Formation action was not offered at this decision')
    c.explicit_unit_formations = None
    before = record[3]
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    count = c.publication_count
    raw = p.runtime.evaluate_text(p.ui_child, _request_source(action, before),
                                  b'@stock_unit_formation_request', capacity=32)
    if raw != b'submitted' or len(p.actions.pending) != 1:
        raise RuntimeError('Formation command did not enqueue one native archive')
    digest = sha256(p.actions.pending[0]).hexdigest()
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    p.view_publisher.publish()
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    from .native.native_player_observation import observe_player
    observed = observe_player(p.runtime, p.ui_child, observation['player_id'])
    after, public = _native_catalogue(p, observed)
    if c.publication_count != count + 1:
        raise RuntimeError('Formation command publication count differs')
    applied = _effect(action, before, after)
    if not applied and (observed != observation or after['units'] != before['units']):
        raise RuntimeError('Formation command produced an inconsistent native effect')
    receipt = dict(action=deepcopy(action), native_archive_delivered=True, native_archive_sha256=digest,
                   native_effect_readback=applied, formation_after=public)
    saved.emit('official_explicit_unit_formation_effect', **receipt)
    return dict(status='completed' if applied else 'refused',
                refusal_code=None if applied else 'native_unit_formation_effect_unobserved',
                observation=observed, receipt=receipt)

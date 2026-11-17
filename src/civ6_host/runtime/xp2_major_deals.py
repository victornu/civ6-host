"""Public pending-deal state and the local player's reported transfers."""

from hashlib import sha256
import json
from pathlib import Path

from civ6_host.contracts import diplomacy_overview as contract
from . import xp2_deal_open_borders as borders
from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-public-major-deals-source.json',
          '0b40336f4813deab77d2a533422fa5ab64ef0dba3b51d3ae16348b248b23e947')
_METHODS = {'HasPendingDeal', 'GetPlayerDeals', 'FindItemsByType', 'GetValueType',
            'GetEnactedTurn', 'GetDuration', 'GetAmount'}
_CAPACITY = 131072

_PROMISE_READ = b"""
local function promiseStatus(diplomacy,target,human)
 if human then return 'null' end
 assert(type(PromiseTypes)=='table' and type(diplomacy.IsPromiseMade)=='function',
  'Native PromiseTypes or IsPromiseMade unavailable')
 local active={}
 for _,key in ipairs(promiseKeys) do
  local enum=PromiseTypes[key]
  assert(type(enum)=='number' and enum%1==0,'Native promise type unavailable')
  local made=diplomacy:IsPromiseMade(target,enum)
  assert(type(made)=='boolean','Native public promise status unavailable')
  if made then active[#active+1]='"'..key..'"' end
 end
 return '['..table.concat(active,',')..']'
end
"""


def _proof(execution_image):
    image = identity(execution_image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-major-deal-projection.static.v1'
            or proof['native_execution'] is not False
            or proof['image']['sha256'] != image['image_sha256']
            or Path(proof['image']['path']).resolve() != Path(image['path']).resolve()
            or set(proof['native_methods']) != _METHODS
            or set(proof['official_files']) != {'diplomacy', 'report', 'xp1_report', 'xp2_report',
                                               'xp2_modinfo', 'bbg_modinfo'}):
        raise ValueError('Gathering Storm public deals source differs')
    return proof


def source_dependencies(*, execution_image, stock=False):
    files = _proof(execution_image)['official_files']
    pins = {str(resolve_path(resource_root() / SOURCE[0]).resolve()): SOURCE[1]}
    for name, row in files.items():
        if stock and name == 'bbg_modinfo':
            continue
        path = resolve_path(Path(row['path'])).resolve()
        if sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Gathering Storm report or diplomacy source changed')
        pins[str(path)] = row['sha256']
    pins.update(borders.dependencies(execution_image))
    return pins


def verify_live(base, read, *, execution_image):
    proof = _proof(execution_image)
    spans = list(proof['native_queries'].values())
    for method in proof['native_methods'].values():
        spans.extend(method.values())
    for span in spans:
        raw = read(base + span['rva'], span['size'])
        if type(raw) is not bytes or len(raw) != span['size'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Gathering Storm deal query source changed')
    borders.verify(base, read, execution_image)


_PUBLIC_REPORT = b"""
local function perspective()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
  'Public deal report crossed its observing player or turn')
end
local function integer(value)
 assert(type(value)=='number' and value%1==0 and value>=-2147483648 and value<2147483648,
  'Invalid native deal number')
 return string.format('%.0f',value)
end
perspective()
local actor=Players[pid]
assert(actor and actor:GetID()==pid,'Public deal report lost its actor')
local diplomacy=actor:GetDiplomacy()
local rows={}
local count=0
local function list(value)
 if value==nil then return {} end
 assert(type(value)=='table' and #value<=termLimit,'Native deal list exceeds its bound')
 return value
end
local function terms(deal, giver, direction, kind, itemType, result)
 local items=list(deal:FindItemsByType(itemType,DealItemSubTypes.NONE,giver))
 for _,item in ipairs(items) do
  local duration=item:GetDuration()
  integer(duration)
  if duration~=0 then
   count=count+1
   assert(count<=termLimit,'Native public deal report exceeds its term bound')
   local amount=integer(item:GetAmount())
   local remaining=integer(duration-(turn-item:GetEnactedTurn()))
   local resource=kind=='resource' and integer(item:GetValueType()) or 'null'
   result[#result+1]='{"direction":"'..direction..'","kind":"'..kind..'","amount":'..amount..
    ',"remaining_turns":'..remaining..',"resource_index":'..resource..'}'
  end
 end
end
for _,target in ipairs(targets) do
 local player=Players[target]
 assert(player and player:GetID()==target and player:IsAlive() and player:IsMajor() and diplomacy:HasMet(target),
  'Public deal report requires the same met living major')
 local pending=DealManager.HasPendingDeal(pid,target)
 assert(type(pending)=='boolean','Native pending-deal status unavailable')
 local controller=''
 if draft then
  local human=player:IsHuman()
  assert(type(human)=='boolean','Native counterparty controller unavailable')
  controller=',"counterparty_is_human":'..tostring(human)
  if includePromises then
   controller=controller..',"active_promises":'..promiseStatus(diplomacy,target,human)
  end
 end
 if includeBorders then
  controller=controller..',"open_borders":'..borderRights(actor,player)
 end
 local current={}
 for _,deal in ipairs(list(DealManager.GetPlayerDeals(pid,target))) do
  terms(deal,pid,'outgoing','gold',DealItemTypes.GOLD,current)
  terms(deal,pid,'outgoing','resource',DealItemTypes.RESOURCES,current)
  terms(deal,target,'incoming','gold',DealItemTypes.GOLD,current)
  terms(deal,target,'incoming','resource',DealItemTypes.RESOURCES,current)
 end
 rows[#rows+1]='{"player_id":'..target..',"pending":'..tostring(pending)..controller..',"terms":['..
  table.concat(current,',')..']}'
end
perspective()
return '['..table.concat(rows,',')..']'
"""


def source(overview, *, draft=False, open_borders=False):
    pid, turn = overview['player_id'], overview['turn']
    contract.validate(overview, pid, turn)
    if overview['schema'] != contract.CITY_STATE_PEACE_SCHEMA:
        raise ValueError('Public deal query requires its current diplomacy target list')
    return _source_for_players(pid, turn, [row['player_id'] for row in overview['targets']], draft, open_borders)


def _source_for_players(pid, turn, targets, draft, open_borders=False, *, promise_status=False):
    ids = ','.join(map(str, targets))
    params = (f'local pid,turn,targets,termLimit,draft,includeBorders,includePromises={pid},{turn},'
              f'{{{ids}}},{contract.MAX_DEAL_TERMS},{str(draft).lower()},{str(open_borders).lower()},'
              f'{str(promise_status).lower()}\n')
    if promise_status:
        keys = ','.join(map(json.dumps, contract.PROMISE_TYPES))
        params += 'local promiseKeys={' + keys + '}\n'
    return (params.encode('ascii') + (borders.RIGHTS if open_borders else b'')
            + (_PROMISE_READ if promise_status else b'') + _PUBLIC_REPORT)


def _rows(prefix, code):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, code, b'@xp2_public_major_deals', capacity=_CAPACITY)
    if type(raw) is not bytes or not raw or len(raw) >= _CAPACITY:
        raise ValueError('Invalid public major deals response size')
    return json.loads(raw)


def counterparty_terms(prefix, player_id, turn, target):
    """Read the same player-visible deal report during a scoped confirmation."""
    if (type(turn) is not int or turn < 0 or player_id == target
            or any(type(pid) is not int or not 0 <= pid < 64 for pid in (player_id, target))):
        raise ValueError('Invalid public deal report scope')
    rows = _rows(prefix, _source_for_players(player_id, turn, [target], False))
    contract._validate_deals(rows, [{'player_id': target}], draft=False)
    return rows[0]['terms']


def read_stock_negotiation(prefix, overview):
    pid, turn = overview['player_id'], overview['turn']
    contract.validate(overview, pid, turn)
    if overview['schema'] != contract.RELATIONSHIPS_SCHEMA:
        raise ValueError('Stock negotiation requires its current major relationships')
    targets = overview['targets']
    ids = [row['player_id'] for row in targets]
    rows = (_rows(prefix, _source_for_players(pid, turn, ids, True, True, promise_status=True))
            if ids else [])
    if len(rows) != len(targets):
        raise ValueError('Stock negotiation targets changed during the native deal query')
    opening = (contract.MAKE_PEACE, contract.OPEN_DEAL, contract.OPEN_DEMAND)
    if any(type(row) is not dict or 'active_promises' not in row for row in rows):
        raise ValueError('Missing native active promises for the current major')
    promise_status = [row.pop('active_promises') for row in rows]
    schema = contract.STOCK_PROMISE_STATUS_SCHEMA
    direct_ai = contract.STOCK_DIRECT_AI_CHOICES[schema]
    value = dict(overview, schema=schema, major_deals=rows,
        targets=[dict(target, active_promises=active, selections=[
            dict(option, supported=(option['key'] == contract.DENOUNCE and option['supported']
                or option['key'] in direct_ai and option['supported']
                and not row['counterparty_is_human']
                or option['key'] in opening and not row['pending'] and not row['counterparty_is_human']))
            for option in target['selections']]) for target, row, active in zip(targets, rows, promise_status)])
    return contract.validate(value, pid, turn)


def read(prefix, overview, *, draft=False, open_borders=False, demand=False, major_peace=False):
    if open_borders and not draft:
        raise ValueError('Public open-borders report requires its draft profile')
    if demand and not open_borders:
        raise ValueError('Public demands require the current diplomacy overview')
    if major_peace and not demand:
        raise ValueError('Public major peace requires the current diplomacy overview')
    rows = _rows(prefix, source(overview, draft=draft, open_borders=open_borders)) if overview['targets'] else []
    value = dict(overview, schema=contract.MAJOR_DEALS_SCHEMA, major_deals=rows)
    if draft:
        value['schema'] = (contract.DEMAND_SCHEMA if demand else contract.OPEN_BORDERS_SCHEMA
                           if open_borders else contract.DEAL_DRAFT_SCHEMA)
        opening = (contract.OPEN_DEAL,contract.OPEN_DEMAND) if demand else (contract.OPEN_DEAL,)
        if major_peace:
            value['schema'] = contract.MAJOR_PEACE_SCHEMA
            opening += (contract.MAKE_PEACE,)
        value['targets'] = [
            dict(target, selections=[dict(s, supported=not row['pending'] and not row['counterparty_is_human'])
                                     if s['key'] in opening else s for s in target['selections']])
            for target, row in zip(overview['targets'], rows)]
        if len(value['targets']) != len(overview['targets']):
            raise ValueError('Public deal draft targets changed')
    return contract.validate(value, overview['player_id'], overview['turn'])

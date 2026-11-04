"""Project the source-qualified XP2 TopPanel resource rows."""
from pathlib import Path

from civ6_host.contracts import strategic_resources as contract
from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_unit_upgrades import _verify_binding, _verify_bodies

SOURCE = ('work/host-extensions/xp2-strategic-resources-source.json',
          '399a09d69f1b1f070f15afe6b13b60ee49eeb7fc26deda2e8c394c4bb75ce69b')
BINDINGS = {'GetResources', 'GetResourceAmount', 'GetResourceStockpileCap',
            'GetReservedResourceAmount', 'GetResourceAccumulationPerTurn', 'GetResourceImportPerTurn',
            'GetBonusResourcePerTurn', 'GetUnitResourceDemandPerTurn', 'GetPowerResourceDemandPerTurn',
            'HasCapability'}
MAX_BYTES = 32768
LUA = b"""
local function check()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
        Game.GetCurrentGameTurn()==turn,'foreign resource perspective')
end
local function integer(value)
 assert(type(value)=='number' and value%1==0 and value>=-2147483648 and
        value<=2147483647,'invalid native resource quantity')
 return value
end
local function n(value) return string.format('%.0f',value) end
local function visible(value) return value>0 and n(value) or '-' end
check()
local enabled=GameCapabilities.HasCapability('CAPABILITY_DISPLAY_TOP_PANEL_RESOURCES')
assert(type(enabled)=='boolean','invalid resource capability')
local out={'strategic-resources-v1|'..n(pid)..'|'..n(turn)..'|'..(enabled and '1' or '0')}
if enabled then
 local player=Players[pid]
 assert(player,'missing own resource player')
 local resources=player:GetResources()
 assert(resources,'missing own resource inventory')
 local offers={}
 for resource in GameInfo.Resources() do
  if resource.ResourceClassType=='RESOURCECLASS_STRATEGIC' then
   local name=resource.ResourceType
   assert(type(name)=='string' and #name<=109 and name:match('^RESOURCE_[A-Z0-9_]+$'),
          'invalid strategic resource type')
   local stock=integer(resources:GetResourceAmount(name))
   local cap=integer(resources:GetResourceStockpileCap(name))
   local reserved=integer(resources:GetReservedResourceAmount(name))
   local extraction=integer(resources:GetResourceAccumulationPerTurn(name))
   local imports=integer(resources:GetResourceImportPerTurn(name))
   local bonus=integer(resources:GetBonusResourcePerTurn(name))
   local units=integer(resources:GetUnitResourceDemandPerTurn(name))
   local power=integer(resources:GetPowerResourceDemandPerTurn(name))
   local accumulation=extraction+imports+bonus
   local consumption=units+power
   if cap>0 and (stock>0 or accumulation>0 or consumption>0) then
    local id=integer(resource.Index)
    assert(id>=0 and #offers<128,'invalid or excessive strategic resources')
    offers[#offers+1]={id=id, row=table.concat({
     n(id),name,n(stock),n(cap),n(reserved),n(accumulation),n(consumption),
     visible(extraction),visible(imports),visible(bonus),
     consumption>0 and visible(units) or '-',consumption>0 and visible(power) or '-'
    },'|')}
   end
  end
 end
 table.sort(offers,function(a,b) return a.id<b.id end)
 for _,offer in ipairs(offers) do out[#out+1]=offer.row end
end
check()
return table.concat(out,'\\n')
"""


def _proof():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-strategic-resources-source.v1'
            or proof['core']['sha256'] != XP2_CORE_SHA256 or proof['native_execution'] is not False
            or set(proof['bindings']) != BINDINGS):
        raise ValueError('XP2 strategic resource source identity differs')
    return proof


def source_dependencies():
    proof = _proof()
    return {str(resolve_path(resource_root() / SOURCE[0]).resolve()): SOURCE[1],
            str(resolve_path(Path(proof['panel']['path'])).resolve()): proof['panel']['sha256']}


def _bind(saved):
    saved._check_query()
    owner = saved.backend
    core = owner.core
    base = core._handle
    if owner.load_abi.core_sha256 != XP2_CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Strategic resources require the live XP2 owner')
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp2_strategic_resources_lifetime', None) != lifetime:
        read = owner.runtime.read
        bindings = _proof()['bindings']
        for name, binding in bindings.items():
            _verify_binding(read, base, name, binding, 'bytes_hex')
        _verify_bodies(read, base, (binding['callback'] for binding in bindings.values()))
        saved._xp2_strategic_resources_lifetime = lifetime


def _parse(raw, player_id, turn):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ValueError('Invalid native strategic resource wire')
    header, *lines = raw.decode('ascii').splitlines()
    prefix = f'strategic-resources-v1|{player_id}|{turn}|'
    if header not in (prefix + '0', prefix + '1') or len(lines) > contract.LIMIT:
        raise ValueError('Foreign or excessive strategic resource wire')
    values = []
    for line in lines:
        parts = line.split('|')
        if len(parts) != len(contract.FIELDS):
            raise ValueError('Malformed native strategic resource row')
        row = {}
        for field, token in zip(contract.FIELDS, parts, strict=True):
            if field == 'item_type':
                row[field] = token
            elif token == '-':
                row[field] = None
            else:
                row[field] = int(token)
                if str(row[field]) != token:
                    raise ValueError('Noncanonical native resource quantity')
        values.append(row)
    return contract.validate(dict(schema=contract.SCHEMA, player_id=player_id, turn=turn,
                                  panel_enabled=header[-1] == '1', resources=values), player_id, turn)


def observe(saved, observation):
    _bind(saved)
    player_id, turn = observation['player_id'], observation['turn']
    if type(player_id) is not int or not 0 <= player_id <= 63 or type(turn) is not int or turn < 0:
        raise ValueError('Invalid own strategic resource perspective')
    prefix = saved.prefix
    code = f'local pid,turn={player_id},{turn}\n'.encode() + LUA
    wire = prefix.runtime.evaluate_text(prefix.ui_child, code, b'@xp2_strategic_resources',
                                       capacity=MAX_BYTES + 1)
    return _parse(wire, player_id, turn)

"""Reuse the native upgrade command with Gathering Storm's resource quote."""
from pathlib import Path
import struct

from civ6_host.contracts import unit_upgrades as contract
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_saved_unit_upgrade as upgrades
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-unit-upgrade-source.json',
          '0296295fd69b36b98354d4f6e794154eaa84bb250fc93e7ed93598647558b01d')
RESOURCE_ROUTE = ('work/host-extensions/xp2-unit-upgrade-override-source.json',
                  '3af3870ebfcb3f5951561b2040c992a1dd529112200d146cda4978a059e8b312')
STOCKPILE_SOURCE = ('work/host-extensions/xp2-strategic-upgrade-preparation.json',
                    '9040bc66890cfc34953e3f57cb185af6f3326445ccf944e7705bb0af7391e3e9')
QUOTE_LUA = b"""
local out={'upgrades-v1|'..n(pid)..'|'..n(turn)}
for _,a in ipairs(snapshot()) do
 local resource,quantity=nil,nil
 if a.target~=nil then
  local index,amount=a.unit:GetUpgradeResourceCost()
  integer(index,'resource',-2147483648,2147483647)
  if index>=0 then
   assert(GameInfo.Resources[index]~=nil,'unknown upgrade resource')
   resource=index;quantity=integer(amount,'resource quantity',0,2147483647)
  end
 end
 out[#out+1]=a.wire..'|'..(a.legal and '1' or '0')..'|'..
  (resource and n(resource) or '-')..'|'..(quantity and n(quantity) or '-')
end
ready()
return table.concat(out,'\\n')
"""
STOCKPILE_LUA = b"""
local row=GameInfo.Resources[resource]
assert(row and row.Index==resource and row.ResourceClassType=='RESOURCECLASS_STRATEGIC',
       'invalid strategic resource')
local stock=integer(player:GetResources():GetResourceAmount(row.ResourceType),'stockpile',0,2147483647)
ready()
return table.concat({n(pid),n(turn),n(resource),n(stock)},'|')
"""


def _source():
    path = resolve_path(resource_root() / SOURCE[0])
    proof = load_pinned_json(path, SOURCE[1])
    if (proof['schema'] != 'civ6-host.xp2-unit-upgrade-source.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256 or proof['native_execution'] is not False
            or proof['command'] != contract.COMMAND or proof['unit_type_result'] != 0x3c0dec5b):
        raise ValueError('XP2 upgrade source identity differs')
    return path, proof


def source_dependencies():
    path, proof = _source()
    base = upgrades.verify_source()
    (route_path, _), (stock_path, stock) = _resource_sources()
    return {str(path.resolve()): SOURCE[1],
            str(resolve_path(upgrades.PROOF).resolve()): upgrades.PROOF_SHA,
            str(route_path.resolve()): RESOURCE_ROUTE[1],
            str(stock_path.resolve()): STOCKPILE_SOURCE[1],
            **{str(resolve_path(Path(row['path'])).resolve()): row['sha256']
               for row in [base['official_ui'], *proof['official_ui'],
                           stock['official_top_panel'], stock['actual_xp2_included_unit_panel']]}}


def _resource_sources():
    route_path = resolve_path(resource_root() / RESOURCE_ROUTE[0])
    stock_path = resolve_path(resource_root() / STOCKPILE_SOURCE[0])
    route = load_pinned_json(route_path, RESOURCE_ROUTE[1])
    stock = load_pinned_json(stock_path, STOCKPILE_SOURCE[1])
    if (route['schema'] != 'civ6-host.xp2-unit-upgrade-override-source.v1'
            or route['command'] != contract.COMMAND or route['resource_notification'] != 0x1153df52
            or stock['schema'] != 'civ6-host.xp2-strategic-upgrade-preparation.v1'
            or any(proof['core']['sha256'] != XP2_CORE_SHA256 for proof in (route, stock))):
        raise ValueError('XP2 strategic upgrade source identity differs')
    return (route_path, route), (stock_path, stock)


def _verify_bodies(read, base, bodies):
    for body in bodies:
        for fragment in body['fragments']:
            expected = bytes.fromhex(fragment['raw_hex'])
            if read(base + int(fragment['start_rva'], 16), len(expected)) != expected:
                raise ValueError('Live XP2 Lua binding body differs')


def _verify_binding(read, base, name, binding, bytes_key):
    expected = bytes.fromhex(binding[bytes_key])
    literal = name.encode('ascii') + b'\0'
    if (read(base + binding['registration_rva'], len(expected)) != expected
            or read(base + binding['name_rva'], len(literal)) != literal):
        raise ValueError('Live XP2 Lua registration differs')


def _verify_table(read, base, table):
    for offset, rva in table['slots'].items():
        if read(base + table['rva'] + int(offset), 8) != struct.pack('<Q', base + rva):
            raise ValueError('Live XP2 upgrade command vtable differs')


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    owner = saved.backend
    core = owner.core
    base = core._handle
    if owner.load_abi.core_sha256 != XP2_CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Unit upgrades require the live XP2 owner')
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp2_upgrade_lifetime', None) == lifetime:
        return
    _, proof = _source()
    read = owner.runtime.read
    _verify_bodies(read, base, proof['functions'].values())
    for name, binding in proof['bindings'].items():
        _verify_binding(read, base, name, binding, 'bytes_hex')
    _verify_table(read, base, proof['command_table'])
    (_, route), (_, stock) = _resource_sources()
    _verify_bodies(read, base, route['functions'].values())
    _verify_table(read, base, route['command_table'])
    for name in ('GetResources', 'GetResourceAmount'):
        binding = stock['bindings'][name]
        _verify_binding(read, base, name, binding, 'registration_bytes_hex')
        _verify_bodies(read, base, [binding['callback_body']])
    saved._xp2_upgrade_lifetime = lifetime


def _decode(raw, observation):
    if type(raw) is not bytes or len(raw) > upgrades.LIMIT:
        raise ValueError('Unbounded XP2 upgrade wire')
    lines = raw.splitlines()
    if not lines or len(lines) > 4097:
        raise ValueError('Invalid XP2 upgrade wire')
    base_lines, resources = lines[:1], []
    for line in lines[1:]:
        parts = line.rsplit(b'|', 2)
        if len(parts) != 3:
            raise ValueError('Invalid XP2 resource quote wire')
        base_lines.append(parts[0])
        values = tuple(None if part == b'-' else int(part) for part in parts[1:])
        if tuple(b'-' if value is None else str(value).encode('ascii') for value in values) != tuple(parts[1:]):
            raise ValueError('Noncanonical XP2 resource quote wire')
        resources.append(values)
    player_id, turn = observation['player_id'], observation['turn']
    base = upgrades.parse_catalog(b'\n'.join(base_lines), player_id, turn)
    expanded = dict(base, offers=[dict(row, resource_type=resource, resource_cost=quantity)
        for row, (resource, quantity) in zip(base['offers'], resources, strict=True)])
    return base, contract.validate_catalogue(expanded, player_id, turn, observation=observation)


def _query(saved, observation):
    prefix = saved.prefix
    source = upgrades.preamble(observation['player_id'], observation['turn']) + QUOTE_LUA
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@xp2_explicit_unit_upgrades',
                                       capacity=upgrades.LIMIT + 1)
    return _decode(raw, observation)


def catalogue(saved, observation):
    _bind(saved, active=False)
    saved.explicit_unit_upgrades, saved.xp2_unit_upgrades = _query(saved, observation)
    return saved.xp2_unit_upgrades


def _stockpile(saved, observation, resource):
    player_id, turn = observation['player_id'], observation['turn']
    prefix = saved.prefix
    source = upgrades.preamble(player_id, turn) + f'\nlocal resource={resource}\n'.encode() + STOCKPILE_LUA
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@xp2_upgrade_stockpile', capacity=128)
    header = f'{player_id}|{turn}|{resource}|'.encode()
    if type(raw) is not bytes or len(raw) > 128 or not raw.startswith(header):
        raise ValueError('Foreign XP2 stockpile boundary')
    token = raw[len(header):]
    if not token.isdigit() or len(token) > 10:
        raise ValueError('Invalid XP2 stockpile amount')
    amount = int(token)
    if amount > 0x7fffffff or str(amount).encode('ascii') != token:
        raise ValueError('Noncanonical XP2 stockpile amount')
    return amount


def apply(saved, action, observation):
    _bind(saved, active=True)
    contract.validate_action(action)
    fresh_base, fresh = _query(saved, observation)
    if (fresh_base != saved.explicit_unit_upgrades or fresh != saved.xp2_unit_upgrades
            or action not in contract.actions(fresh)):
        raise RuntimeError('XP2 upgrade quote is stale or unavailable')
    resource = action['resource_type']
    balance = None if resource is None else _stockpile(saved, observation, resource)
    base_action = {key: action[key] for key in upgrades.FIELDS}
    after = upgrades.apply(saved, saved.prefix, base_action, observation['turn'], observation,
                           player_id=observation['player_id'])
    previous_ids = {unit['id'] for unit in observation['units']}
    replacement = [unit for unit in after['units'] if unit['id'] not in previous_ids
                   and unit['owner'] == observation['player_id'] and unit['type'] == action['target_type']]
    if len(replacement) != 1 or any(unit['id'] == action['unit_id'] for unit in after['units']):
        raise RuntimeError('Native upgrade did not replace the selected unit with the quoted type')
    resource_balance = {} if balance is None else dict(
        resource_before=balance, resource_after=_stockpile(saved, after, resource),
        resource_source_sha256=STOCKPILE_SOURCE[1], resource_route_sha256=RESOURCE_ROUTE[1])
    saved.emit('official_xp2_unit_upgrade_effect', action=action, replacement=replacement[0],
               gold_before=observation['economy']['gold'], gold_after=after['economy']['gold'],
               source_sha256=SOURCE[1], **resource_balance)
    return after

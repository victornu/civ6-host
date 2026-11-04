"""Immediate official upgrade command; eligibility, prices and effects stay native."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_saved_unit_orders import uint
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_unit_upgrade.py')))).resolve().parents[1]
PROOF = ROOT / 'work/unit-upgrade960/source.json'
PROOF_SHA = 'b0c21c2f3db6e41b6d049c0a2ecbedf81a94207e7ac150f5b4fae07ad6009efd'
FIELDS = {'kind', 'unit_id', 'hash', 'target_type', 'cost'}
LIMIT = 524288

def verify_source():
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.unit_upgrade960.source.v1' or p['contracts']['rules_reimplemented'] is not False:
        raise RuntimeError('Upgrade source changed')
    ui = p['official_ui']
    if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(ui['path']))).read_bytes()).hexdigest() != ui['sha256']:
        raise RuntimeError('Official upgrade UI changed')
    return p

def validate_action(a):
    if type(a) is not dict or set(a) != FIELDS or a['kind'] != 'upgrade_unit':
        raise ValueError('Malformed unit upgrade')
    for k in ('unit_id', 'hash', 'target_type'):
        uint(a[k], k)
    uint(a['cost'], 'upgrade cost', 2147483647)
    return a

def wire(a):
    validate_action(a)
    return '|'.join((str(a[k]) for k in ('unit_id', 'hash', 'target_type', 'cost')))
LUA = "\nlocal function integer(v,label,lo,hi) assert(type(v)=='number' and v%1==0 and v>=lo and v<=hi,'invalid upgrade '..label);return v end\nlocal function bool(v,label) assert(type(v)=='boolean','invalid upgrade '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function bits(v) integer(v,'hash',-2147483648,2147483647);return v<0 and v+4294967296 or v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale upgrade perspective')\n assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands unavailable')\n local p=Players[pid];assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'upgrade player not ready');return p\nend\nlocal player=ready()\nlocal function snapshot()\n local command=GameInfo.UnitCommands.UNITCOMMAND_UPGRADE\n assert(command and command.Hash==UnitCommandTypes.UPGRADE,'upgrade command identity differs')\n assert(command.InterfaceMode==nil or DB.MakeHash(command.InterfaceMode)==InterfaceModeTypes.NONE,'upgrade is modal')\n local hash=bits(command.Hash)\n integer(UnitCommandResults.UNIT_TYPE,'result key',-2147483648,2147483647)\n local offers,seen,count={},{},0\n for _,u in player:GetUnits():Members() do\n  count=count+1;assert(count<=4096 and u:GetOwner()==pid,'unbounded or foreign upgrade unit')\n  local id=integer(u:GetID(),'unit',0,4294967295);assert(not seen[id],'duplicate upgrade unit');seen[id]=true\n  if command.VisibleInUI and bool(UnitManager.CanStartCommand(u,command.Hash,true),'visibility') then\n   local legal,results=UnitManager.CanStartCommand(u,command.Hash,false,true);bool(legal,'legality')\n   assert(results==nil or type(results)=='table','invalid upgrade results')\n   local target=results and results[UnitCommandResults.UNIT_TYPE];local cost=nil\n   if target~=nil then\n    integer(target,'target type',0,4294967295);local row=GameInfo.Units[target]\n    assert(row and row.Index==target,'unknown upgrade unit type')\n    cost=u:GetUpgradeCost();if cost~=nil then integer(cost,'cost',0,2147483647) end\n   end\n   assert(not legal or (target~=nil and cost~=nil),'legal upgrade lacks native target/price')\n   offers[#offers+1]={unit=u,id=id,hash=command.Hash,target=target,cost=cost,legal=legal,\n    wire=table.concat({n(id),n(hash),target and n(target) or '-',cost and n(cost) or '-'},'|')}\n  end\n end\n table.sort(offers,function(a,b) return a.id<b.id end);ready();return offers\nend\n"

def preamble(pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    verify_source()
    return f'local pid,turn={pid},{turn}\n'.encode() + LUA.encode()

def catalog_source(pid, turn):
    return preamble(pid, turn) + b"local out={'upgrades-v1|'..n(pid)..'|'..n(turn)};for _,a in ipairs(snapshot()) do out[#out+1]=a.wire..'|'..(a.legal and '1' or '0') end;return table.concat(out,'\\n')"

def validate_catalog(v, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'offers'} or type(v['player_id']) is not int or (v['player_id'] != pid) or (type(v['turn']) is not int) or (v['turn'] != turn):
        raise ValueError('Foreign unit upgrades')
    if type(v['offers']) is not list or len(v['offers']) > 4096:
        raise ValueError('Unbounded upgrade offers')
    ids = []
    for r in v['offers']:
        if type(r) is not dict or set(r) != {'unit_id', 'hash', 'target_type', 'cost', 'legal'} or type(r['legal']) is not bool:
            raise ValueError('Malformed upgrade offer')
        ids.append(uint(r['unit_id'], 'unit'))
        uint(r['hash'], 'hash')
        if r['target_type'] is not None:
            uint(r['target_type'], 'target type')
        if r['cost'] is not None:
            uint(r['cost'], 'cost', 2147483647)
        if r['legal'] and (r['target_type'] is None or r['cost'] is None):
            raise ValueError('Legal upgrade lacks target/price')
        if r['target_type'] is None and r['cost'] is not None:
            raise ValueError('Upgrade price without target')
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unordered upgrade offers')
    return v

def parse_catalog(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded upgrade wire')
    lines = raw.decode('ascii').splitlines()
    if not lines or lines[0] != f'upgrades-v1|{pid}|{turn}' or len(lines) > 4097:
        raise ValueError('Foreign upgrade wire')
    v = dict(player_id=pid, turn=turn, offers=[])
    for line in lines[1:]:
        vals = line.split('|')
        if len(vals) != 5 or vals[4] not in ('0', '1'):
            raise ValueError('Malformed upgrade wire')
        parsed = [None if x == '-' else int(x) for x in vals[:4]]
        if ['-' if x is None else str(x) for x in parsed] != vals[:4]:
            raise ValueError('Noncanonical upgrade wire')
        v['offers'].append(dict(zip(('unit_id', 'hash', 'target_type', 'cost'), parsed), legal=vals[4] == '1'))
    return validate_catalog(v, pid, turn)

def actions(v):
    return [dict(kind='upgrade_unit', **{k: r[k] for k in ('unit_id', 'hash', 'target_type', 'cost')}) for r in v['offers'] if r['legal']]

def catalog(prefix, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, turn), b'@explicit_unit_upgrades', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, turn)

def request_source(a, pid, turn):
    w = wire(a)
    return preamble(pid, turn) + f"\nlocal chosen=nil\nfor _,a in ipairs(snapshot()) do if a.wire=='{w}' then assert(not chosen,'duplicate upgrade selection');chosen=a end end\nassert(chosen and chosen.legal,'upgrade unavailable or stale');ready()\nUnitManager.RequestCommand(chosen.unit,chosen.hash)\nreturn 'submitted'\n".encode()

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    fresh = catalog(prefix, turn, player_id=player_id)
    if fresh != getattr(owner, 'explicit_unit_upgrades', None) or action not in actions(fresh):
        raise RuntimeError('Upgrade catalogue is stale or unavailable')
    old = [u for u in before['units'] if u['id'] == action['unit_id']]
    if len(old) != 1 or old[0]['owner'] != player_id:
        raise RuntimeError('Upgrade unit absent from own observation')
    if prefix.actions.pending:
        raise RuntimeError('Upgrade queue was not empty')
    response = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, player_id, turn), b'@explicit_unit_upgrade_request')
    if response != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Upgrade did not enqueue one native command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after['player_id'] != player_id or after['turn'] != turn:
        raise RuntimeError('Upgrade crossed actor/turn')
    owner.emit('official_explicit_unit_upgrade_effect', action=action, observation_before=before, observation_after=after, changed_units_before=[u for u in before['units'] if u not in after['units']], changed_units_after=[u for u in after['units'] if u not in before['units']], source_proof_sha256=PROOF_SHA, native_archive_delivered=True, automatic_choices_applied=False, strategic_training_ready=False)
    return after

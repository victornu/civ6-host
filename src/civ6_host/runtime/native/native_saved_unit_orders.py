"""Official parameterless rest/wake routes; all rules stay in GameCore."""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _UNIT_ORDERS_BASE_CORE_SHA256
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.contracts.capability_unit_orders import SKIP_TURN
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_unit_orders.py')))).resolve().parents[1]
PROOF = ROOT / 'work/unit-orders958/source.json'
PROOF_SHA = '8ba82b2b22f594348e10fc3708e9156eb626d317f311f8367ca6031227e0b04f'
NAMES = {'command': ('UNITCOMMAND_WAKE',), 'operation': ('UNITOPERATION_SLEEP', 'UNITOPERATION_FORTIFY', 'UNITOPERATION_HEAL', 'UNITOPERATION_RELIGIOUS_HEAL', SKIP_TURN)}
CANCEL_NAME = 'UNITCOMMAND_CANCEL'
CANCEL_PROOF = ROOT / 'work/unit-order-cancel/source.json'
CANCEL_PROOF_SHA = '31014e4b1e4342b057c6a1f96aa93a1c98023bc85e32f579750b2af0d174f497'
FIELDS = {'kind', 'unit_id', 'route', 'item_type', 'hash'}
LIMIT = 524288

def verify_source(*, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256):
    if core_sha256 != _UNIT_ORDERS_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_unit_orders_profile import verify_source as selected_source
        return selected_source(core_sha256)
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.unit_orders958.source.v1' or p['contracts']['rules_reimplemented'] is not False:
        raise RuntimeError('Unit order source changed')
    ui = p['official_ui']
    if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(ui['path']))).read_bytes()).hexdigest() != ui['sha256']:
        raise RuntimeError('Official UnitPanel changed')
    return p

def verify_cancel_source(*, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256):
    """Reuse the proven command ABI; pin the ordinary-unit UI admission."""
    if core_sha256 != _UNIT_ORDERS_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_unit_orders_profile import verify_source as selected_source
        return selected_source(core_sha256)
    verify_source(core_sha256=core_sha256)
    p = load_pinned_json(CANCEL_PROOF, CANCEL_PROOF_SHA)
    if p['schema'] != 'civ6rl.unit_order_cancel_source.v1' or p['gamecore']['source_evidence_sha256'] != PROOF_SHA or p['database']['definition']['CommandType'] != CANCEL_NAME or (p['database']['definition']['VisibleInUI'] != 1) or (p['database']['definition']['InterfaceMode'] is not None):
        raise RuntimeError('Unproven unit cancel source')
    return p

def cancel_verified_files():
    p = verify_cancel_source()
    refs = (p['database'], p['official_ui'], p['gamecore']['prior_api_source'])
    result = {}
    for r in refs:
        path = _resolve_resource_path(Path(r['path']))
        path = path if path.is_absolute() else ROOT / path
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != r['sha256']:
            raise RuntimeError('Unit cancel source changed: ' + r['path'])
        result[path] = r['sha256']
    return result

def uint(v, label, maximum=4294967295):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError('Invalid unit order ' + label)
    return v

def validate_action(a):
    if type(a) is not dict or set(a) != FIELDS or a['kind'] != 'unit_order':
        raise ValueError('Malformed unit order')
    uint(a['unit_id'], 'unit')
    uint(a['hash'], 'hash')
    if type(a['route']) is not str or a['route'] not in NAMES or a['item_type'] not in NAMES[a['route']] + ((CANCEL_NAME,) if a['route'] == 'command' else ()):
        raise ValueError('Unknown unit order')
    return a

def wire(a):
    validate_action(a)
    return '|'.join((str(a[k]) for k in ('unit_id', 'route', 'item_type', 'hash')))
LUA = "\nlocal function integer(v,label,lo,hi) assert(type(v)=='number' and v%1==0 and v>=lo and v<=hi,'invalid order '..label);return v end\nlocal function bool(v,label) assert(type(v)=='boolean','invalid order '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function bits(v) integer(v,'hash',-2147483648,2147483647);return v<0 and v+4294967296 or v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale order perspective')\n assert(Game.IsAllowStrategicCommands(pid)==true,'strategic orders unavailable')\n local p=Players[pid];assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'order player not ready');return p\nend\nlocal player=ready()\nlocal function snapshot()\n local units,offers,seen={},{},{}\n for _,u in player:GetUnits():Members() do\n  assert(#units<4096 and u:GetOwner()==pid,'unbounded or foreign own unit')\n  local id=integer(u:GetID(),'unit',0,4294967295);assert(not seen[id],'duplicate order unit');seen[id]=true\n  local activity=integer(UnitManager.GetActivityType(u),'activity',-2147483648,2147483647)\n  local fortify=integer(u:GetFortifyTurns(),'fortify turns',0,2147483647)\n  local readyToSelect=bool(u:IsReadyToSelect(),'readiness')\n  units[#units+1]={id=id,wire=table.concat({n(id),n(activity),n(fortify),readyToSelect and '1' or '0'},'|')}\n  local moves=u:GetMovesRemaining();assert(type(moves)=='number' and moves==moves and moves>=0 and moves<=2147483648,'order movement')\n  local specs={{'command','UNITCOMMAND_WAKE'},{'operation','UNITOPERATION_SLEEP'},{'operation','UNITOPERATION_FORTIFY'},{'operation','UNITOPERATION_HEAL'},{'operation','UNITOPERATION_RELIGIOUS_HEAL'}}\n  if include_cancel then\n   local row=GameInfo.Units[u:GetType()];assert(row and type(row.Spy)=='boolean','missing cancel unit type')\n   -- Espionage has a different official dialog, not this parameterless route.\n   if not row.Spy then specs[#specs+1]={'command','UNITCOMMAND_CANCEL'} end\n  end\n  for _,spec in ipairs(specs) do\n   local route,name=spec[1],spec[2]\n   local row=(route=='command' and GameInfo.UnitCommands or GameInfo.UnitOperations)[name]\n   if row and row.VisibleInUI and (route=='command' or moves>0) then\n    assert(row.InterfaceMode==nil or DB.MakeHash(row.InterfaceMode)==InterfaceModeTypes.NONE,'unit order requires interface mode')\n    local hash=bits(row.Hash);local visible,legal\n    if route=='command' then\n     visible=bool(UnitManager.CanStartCommand(u,row.Hash,true),'command visibility')\n     if visible then legal=bool(UnitManager.CanStartCommand(u,row.Hash,false,true),'command legality') end\n    else\n     visible=bool(UnitManager.CanStartOperation(u,row.Hash,nil,true),'operation visibility')\n     if visible then legal=bool(UnitManager.CanStartOperation(u,row.Hash,nil,false,OperationResultsTypes.NO_TARGETS),'operation legality') end\n    end\n    if visible then\n     assert(#offers<4096,'order offer bound')\n     offers[#offers+1]={unit=u,route=route,hash=row.Hash,legal=legal,wire=table.concat({n(id),route,name,n(hash)},'|')}\n    end\n   end\n  end\n end\n table.sort(units,function(a,b) return a.id<b.id end)\n table.sort(offers,function(a,b) return a.wire<b.wire end)\n ready();return units,offers\nend\n"

def preamble(pid, turn, *, include_cancel=False, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256):
    if type(include_cancel) is not bool:
        raise ValueError('Exact unit cancel option required')
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    verify_source(core_sha256=core_sha256)
    if include_cancel:
        verify_cancel_source(core_sha256=core_sha256)
    source = LUA
    if core_sha256 == XP2_CORE_SHA256:
        marker = '  if include_cancel then'
        assert source.count(marker) == 1
        source = source.replace(marker, f"  specs[#specs+1]={{'operation','{SKIP_TURN}'}}\n" + marker)
    return f'local pid,turn={pid},{turn}\nlocal include_cancel={str(include_cancel).lower()}\n'.encode() + source.encode()

def catalog_source(pid, turn, *, include_cancel=False, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256):
    return preamble(pid, turn, include_cancel=include_cancel, core_sha256=core_sha256) + b"local units,offers=snapshot();local out={'orders-v1|'..n(pid)..'|'..n(turn)}\nfor _,u in ipairs(units) do out[#out+1]='U|'..u.wire end\nfor _,a in ipairs(offers) do out[#out+1]='A|'..a.wire..'|'..(a.legal and '1' or '0') end\nreturn table.concat(out,'\\n')"

def validate_catalog(v, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'units', 'offers'} or type(v['player_id']) is not int or (v['player_id'] != pid) or (type(v['turn']) is not int) or (v['turn'] != turn):
        raise ValueError('Foreign unit orders')
    if any((type(v[k]) is not list or len(v[k]) > 4096 for k in ('units', 'offers'))):
        raise ValueError('Unbounded unit orders')
    ids = []
    seen = set()
    for u in v['units']:
        if type(u) is not dict or set(u) != {'unit_id', 'activity_type', 'fortify_turns', 'ready'}:
            raise ValueError('Malformed order state')
        ids.append(uint(u['unit_id'], 'unit'))
        uint(u['fortify_turns'], 'fortify turns', 2147483647)
        if type(u['activity_type']) is not int or not -2147483648 <= u['activity_type'] <= 2147483647 or type(u['ready']) is not bool:
            raise ValueError('Malformed activity/readiness')
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unsorted order units')
    for r in v['offers']:
        if type(r) is not dict or set(r) != {'action', 'legal'} or type(r['legal']) is not bool:
            raise ValueError('Malformed order offer')
        a = validate_action(r['action'])
        key = wire(a)
        if a['unit_id'] not in ids or key in seen:
            raise ValueError('Foreign or duplicate order offer')
        seen.add(key)
    return v

def parse_catalog(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded order wire')
    lines = raw.decode('ascii').splitlines()
    if not lines or lines[0] != f'orders-v1|{pid}|{turn}' or len(lines) > 8193:
        raise ValueError('Foreign order wire')
    out = dict(player_id=pid, turn=turn, units=[], offers=[])
    for line in lines[1:]:
        v = line.split('|')
        if v[0] == 'U' and len(v) == 5 and (v[4] in ('0', '1')):
            if out['offers']:
                raise ValueError('Unordered unit wire')
            vals = [int(x) for x in v[1:4]]
            if list(map(str, vals)) != v[1:4]:
                raise ValueError('Noncanonical unit wire')
            out['units'].append(dict(unit_id=vals[0], activity_type=vals[1], fortify_turns=vals[2], ready=v[4] == '1'))
        elif v[0] == 'A' and len(v) == 6 and (v[5] in ('0', '1')):
            a = dict(kind='unit_order', unit_id=int(v[1]), route=v[2], item_type=v[3], hash=int(v[4]))
            if wire(a) != '|'.join(v[1:5]):
                raise ValueError('Noncanonical order wire')
            out['offers'].append(dict(action=a, legal=v[5] == '1'))
        else:
            raise ValueError('Malformed unit order wire')
    return validate_catalog(out, pid, turn)

def catalog(prefix, turn, *, player_id=0, include_cancel=False, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, turn, include_cancel=include_cancel, core_sha256=core_sha256), b'@explicit_unit_orders', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, turn)

def actions(v):
    return [r['action'] for r in v['offers'] if r['legal']]

def request_source(a, pid, turn, *, include_cancel=False, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256):
    w = wire(a)
    return preamble(pid, turn, include_cancel=include_cancel, core_sha256=core_sha256) + f"\nlocal _,offers=snapshot();local chosen=nil\nfor _,a in ipairs(offers) do if a.wire=='{w}' then assert(not chosen,'duplicate selected order');chosen=a end end\nassert(chosen and chosen.legal,'order is stale or unavailable');ready()\nif chosen.route=='command' then UnitManager.RequestCommand(chosen.unit,chosen.hash)\nelse UnitManager.RequestOperation(chosen.unit,chosen.hash) end\nreturn 'submitted'\n".encode()

def apply(owner, prefix, action, turn, before, *, player_id=0, core_sha256=_UNIT_ORDERS_BASE_CORE_SHA256, include_cancel=None):
    from civ6_host.runtime.xp1_unit_orders_profile import selected_proof
    if include_cancel is None:
        options = dict(include_cancel=True) if _action_feature_enabled(owner, 'unit_order_cancel') is True else {}
    else:
        if type(include_cancel) is not bool:
            raise ValueError('Exact unit cancel option required')
        options = dict(include_cancel=include_cancel)
    validate_action(action)
    start = catalog(prefix, turn, player_id=player_id, **options, core_sha256=core_sha256)
    if start != getattr(owner, 'explicit_unit_orders', None) or action not in actions(start):
        raise RuntimeError('Unit order state is stale or unavailable')
    if prefix.actions.pending:
        raise RuntimeError('Unit order queue was not empty')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, player_id, turn, **options, core_sha256=core_sha256), b'@explicit_unit_order_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Unit order did not enqueue exactly one native command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    end = catalog(prefix, turn, player_id=player_id, **options, core_sha256=core_sha256)
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after['turn'] != turn or after['player_id'] != player_id:
        raise RuntimeError('Unit order crossed actor/turn')
    old = next((u for u in start['units'] if u['unit_id'] == action['unit_id']))
    selected = [u for u in end['units'] if u['unit_id'] == action['unit_id']]
    if len(selected) != 1:
        raise RuntimeError('Rest/wake unexpectedly removed own unit')
    owner.emit('official_explicit_unit_order_effect', action=action, unit_before=old, unit_after=selected[0], state_changed=old != selected[0], observation_before=before, observation_after=after, source_proof_sha256=selected_proof(PROOF_SHA, core_sha256), native_archive_delivered=True, automatic_choices_applied=False, strategic_training_ready=False, **dict(cancel_source_proof_sha256=selected_proof(CANCEL_PROOF_SHA, core_sha256)) if action['item_type'] == CANCEL_NAME else {})
    return after
from civ6_host.runtime.network_ui import feature_enabled as _action_feature_enabled

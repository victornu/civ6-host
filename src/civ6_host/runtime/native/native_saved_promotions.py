"""Explicit native unit promotions through the shipped UnitPromotionPopup route.

Only own units are observed. Eligibility, effects, experience and healing remain
inside GameCore. The native selector is an index, not the definition's hash.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import math, re
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_promotions.py')))).resolve().parents[1]
PROOF_PATH = ROOT / 'work/promotions953/source.json'
PROOF_SHA = 'cf14ebf15601166ed655f293e5cda7d7601e5afefffe684e261ea12e517cc1fb'
FIELDS = {'kind', 'unit_id', 'index', 'hash', 'item_type'}
LIMIT = 524288

def uint(v, label, maximum=4294967295):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError('Invalid promotion ' + label)
    return v

def number(token):
    if type(token) is not str or len(token) > 32 or (not re.fullmatch('[0-9]+(?:\\.[0-9]+)?(?:e[+-]?[0-9]+)?', token)):
        raise ValueError('Invalid promotion numeric token')
    n = float(token)
    if not math.isfinite(n) or not 0 <= n <= 2 ** 31:
        raise ValueError('Unbounded promotion value')
    return n

def validate_action(a):
    if type(a) is not dict or set(a) != FIELDS or a['kind'] != 'promote_unit':
        raise ValueError('Invalid promotion action')
    for k in ('unit_id', 'index', 'hash'):
        uint(a[k], k)
    if type(a['item_type']) is not str or not re.fullmatch('PROMOTION_[A-Z0-9_]{1,100}', a['item_type']):
        raise ValueError('Invalid promotion definition')
    return a

def wire(a):
    validate_action(a)
    return '|'.join((str(a[k]) for k in ('unit_id', 'index', 'hash', 'item_type')))
LUA = "\nlocal function integer(v,label,lo,hi)\n assert(type(v)=='number' and v%1==0 and v>=lo and v<=hi,'invalid promotion '..label);return v\nend\nlocal function n(v) return string.format('%.0f',v) end\nlocal function token(v) assert(type(v)=='number' and v==v and v>=0 and v<=2147483648,'invalid promotion numeric value');return string.format('%.17g',v) end\nlocal function bits(v) integer(v,'hash',-2147483648,2147483647);return v<0 and v+4294967296 or v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale promotion perspective')\n local p=Players[pid]\n assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'promotion player not ready')\n return p\nend\nlocal player=ready()\nlocal command=UnitCommandTypes.PROMOTE\ninteger(command,'command',-2147483648,2147483647)\ninteger(UnitCommandTypes.PARAM_PROMOTION_TYPE,'parameter',-2147483648,2147483647)\ninteger(UnitCommandResults.PROMOTIONS,'result key',-2147483648,2147483647)\nlocal function indices(t,label)\n assert(type(t)=='table','missing native '..label)\n local out,seen={},{}\n for _,v in pairs(t) do\n  integer(v,label,0,4294967295);assert(not seen[v] and #out<4096,'duplicate/unbounded '..label)\n  assert(GameInfo.UnitPromotions[v],'unknown native promotion');seen[v]=true;out[#out+1]=v\n end\n table.sort(out);return out\nend\nlocal function snapshot()\n local units,offers,seen={},{},{}\n for _,u in player:GetUnits():Members() do\n  assert(#units<4096 and u:GetOwner()==pid,'foreign/unbounded promotion unit')\n  local id=integer(u:GetID(),'unit',0,4294967295);assert(not seen[id],'duplicate promotion unit');seen[id]=true\n  local xp=u:GetExperience();assert(xp,'native unit experience missing')\n  local acquired=indices(xp:GetPromotions(),'acquired promotions');local list={}\n  for _,v in ipairs(acquired) do list[#list+1]=n(v) end\n  units[#units+1]={id=id,wire=table.concat({n(id),token(xp:GetExperiencePoints()),token(u:GetMovesRemaining()),n(integer(u:GetDamage(),'damage',0,2147483647)),table.concat(list,',')},'|')}\n  local can,results=UnitManager.CanStartCommand(u,command,true,true)\n  assert(type(can)=='boolean','invalid native promotion eligibility')\n  if can then\n   assert(type(results)=='table','missing promotion results')\n   local selectors=results[UnitCommandResults.PROMOTIONS]\n   if selectors~=nil then\n    for _,index in ipairs(indices(selectors,'available promotions')) do\n     local row=GameInfo.UnitPromotions[index]\n     assert(row.Index==index and type(row.UnitPromotionType)=='string' and #row.UnitPromotionType<=110 and string.match(row.UnitPromotionType,'^PROMOTION_[A-Z0-9_]+$'),'promotion identity mismatch')\n     for _,v in ipairs(acquired) do assert(v~=index,'native offered an acquired promotion') end\n     assert(#offers<4096,'unbounded promotion choices')\n     offers[#offers+1]={unit=u,index=index,wire=table.concat({n(id),n(index),n(bits(row.Hash)),row.UnitPromotionType},'|')}\n    end\n   end\n  end\n end\n table.sort(units,function(a,b) return a.id<b.id end)\n ready();return units,offers\nend\n"

def verify_source():
    p = load_pinned_json(PROOF_PATH, PROOF_SHA)
    if p['schema'] != 'civ6rl.promotions953.source.v1' or p['contracts']['rules_reimplemented'] is not False:
        raise RuntimeError('Promotion route source differs')
    return p

def preamble(pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    verify_source()
    return f'local pid,turn={pid},{turn}\n'.encode() + LUA.encode()

def catalog_source(pid, turn):
    return preamble(pid, turn) + b"local units,offers=snapshot()\nlocal out={'promotions-v1|'..n(pid)..'|'..n(turn)}\nfor _,u in ipairs(units) do out[#out+1]='U|'..u.wire end\nfor _,a in ipairs(offers) do out[#out+1]='P|'..a.wire end\nreturn table.concat(out,'\\n')\n"

def validate_catalog(v, pid, turn):
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'units', 'offers'} or type(v['player_id']) is not int or (v['player_id'] != pid) or (type(v['turn']) is not int) or (v['turn'] != turn):
        raise ValueError('Foreign promotion catalogue')
    for k in ('units', 'offers'):
        if type(v[k]) is not list or len(v[k]) > 4096:
            raise ValueError('Unbounded promotion catalogue')
    units = {}
    for u in v['units']:
        if type(u) is not dict or set(u) != {'unit_id', 'experience_token', 'moves_token', 'damage', 'promotions'}:
            raise ValueError('Malformed promotion unit')
        uid = uint(u['unit_id'], 'unit')
        uint(u['damage'], 'damage', 2147483647)
        number(u['experience_token'])
        number(u['moves_token'])
        if uid in units:
            raise ValueError('Duplicate promotion unit')
        if type(u['promotions']) is not list or len(u['promotions']) > 4096:
            raise ValueError('Unbounded acquired promotions')
        for i in u['promotions']:
            uint(i, 'acquired index')
        if u['promotions'] != sorted(set(u['promotions'])):
            raise ValueError('Duplicate/unordered acquired promotions')
        units[uid] = u
    if list(units) != sorted(units):
        raise ValueError('Unordered promotion units')
    seen = set()
    for a in v['offers']:
        validate_action(a)
        key = (a['unit_id'], a['index'])
        if key in seen or a['unit_id'] not in units or a['index'] in units[a['unit_id']]['promotions']:
            raise ValueError('Duplicate, foreign or already acquired promotion choice')
        seen.add(key)
    return v

def parse_catalog(raw, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded promotion response')
    lines = raw.decode('ascii').splitlines()
    if not lines or lines[0] != f'promotions-v1|{pid}|{turn}' or len(lines) > 8193:
        raise ValueError('Foreign promotion response')
    v = dict(player_id=pid, turn=turn, units=[], offers=[])
    for line in lines[1:]:
        p = line.split('|')
        if p[0] == 'U' and len(p) == 6:
            if v['offers']:
                raise ValueError('Unit after promotion offers')
            u = dict(unit_id=int(p[1]), experience_token=p[2], moves_token=p[3], damage=int(p[4]), promotions=[] if not p[5] else list(map(int, p[5].split(','))))
            if '|'.join(['U', str(u['unit_id']), u['experience_token'], u['moves_token'], str(u['damage']), ','.join(map(str, u['promotions']))]) != line:
                raise ValueError('Noncanonical promotion unit')
            v['units'].append(u)
        elif p[0] == 'P' and len(p) == 5:
            a = dict(kind='promote_unit', unit_id=int(p[1]), index=int(p[2]), hash=int(p[3]), item_type=p[4])
            if 'P|' + wire(a) != line:
                raise ValueError('Noncanonical promotion choice')
            v['offers'].append(a)
        else:
            raise ValueError('Malformed promotion response')
    return validate_catalog(v, pid, turn)

def catalog(prefix, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, turn), b'@explicit_promotions_catalog', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, turn)

def request_source(action, pid, turn):
    w = wire(action)
    return preamble(pid, turn) + f"\nlocal _,offers=snapshot();local chosen=nil\nfor _,a in ipairs(offers) do if a.wire=='{w}' then assert(not chosen,'duplicate promotion choice');chosen=a end end\nassert(chosen,'promotion choice changed or unavailable');ready()\nUnitManager.RequestCommand(chosen.unit,command,{{[UnitCommandTypes.PARAM_PROMOTION_TYPE]=chosen.index}})\nreturn 'submitted'\n".encode()

def apply(owner, prefix, action, turn, before, *, player_id=0, after_delivery=None):
    validate_action(action)
    start = catalog(prefix, turn, player_id=player_id)
    if action not in start['offers']:
        raise RuntimeError('Promotion no longer offered')
    if start != getattr(owner, 'explicit_promotions', None):
        raise RuntimeError('Published promotion state changed')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, player_id, turn), b'@explicit_promotion_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Promotion did not enqueue one native command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    if after_delivery is not None:
        after_delivery()
    prefix.view_publisher.publish()
    end = catalog(prefix, turn, player_id=player_id)
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    old = next((u for u in start['units'] if u['unit_id'] == action['unit_id']))
    matches = [u for u in end['units'] if u['unit_id'] == action['unit_id']]
    if len(matches) != 1 or action['index'] not in matches[0]['promotions'] or action['index'] in old['promotions']:
        raise RuntimeError('Native promotion acquisition not observed')
    if after['turn'] != turn or after['player_id'] != player_id:
        raise RuntimeError('Promotion crossed actor/turn')
    owner.emit('official_explicit_promotion_effect', action=action, unit_before=old, unit_after=matches[0], observation_before=before, observation_after=after, source_proof_sha256=PROOF_SHA, automatic_choices_applied=False, strategic_training_ready=False)
    return after

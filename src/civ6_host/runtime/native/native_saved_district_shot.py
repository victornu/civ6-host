"""Independent district shots through the same official CityManager command."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib, json
from pathlib import Path
from civ6_host.runtime.native import native_saved_city_shot as city
from civ6_host.contracts.city_ranged import (
    district_actions as actions,
    district_compare_own_cities as compare_own_cities,
    district_validate_action as validate_action,
    district_validate_catalog as validate_catalog,
    DISTRICT_FIELDS as FIELDS,
    DISTRICT_ROW_FIELDS as ROW_FIELDS,
    uint,
)
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = city.ROOT
PROOF = ROOT / 'work/district-shot964/source.json'
PROOF_SHA = '4d649261cc1ae7e918eeef095ed1bd2fc030a99ce9a2a69864e9fc2891c1e156'

def verify_source():
    city.verify_source()
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.native_district_shot_ui_route.static.v1':
        raise RuntimeError('District-shot source changed')
    for r in p['official_ui'].values():
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(r['path']))).read_bytes()).hexdigest() != r['sha256']:
            raise RuntimeError('Official district-shot UI changed')
    return p

LUA = "\nlocal function integer(v,label,max)\n assert(type(v)=='number' and v%1==0 and v>=0 and v<=max,'invalid district shot '..label);return v\nend\nlocal function boolean(v,label) assert(type(v)=='boolean','invalid district shot '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function b(v) return v and '1' or '0' end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'district shot perspective changed')\n local p=Players[pid];assert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),'district shot actor not ready')\n return p\nend\nlocal player=ready()\nlocal width,height=Map.GetGridSize()\ninteger(width,'width',16384);integer(height,'height',16384)\nassert(width>0 and height>0 and width*height==Map.GetPlotCount() and width*height<=16384,'district shot map outside bound')\nlocal command=CityCommandTypes.RANGE_ATTACK\nassert(command==-1967338303 and CityCommandResults.PLOTS==1933683541 and CityCommandResults.MODIFIER_IS_TARGET==889110605,'district shot enums changed')\nassert(type(CityCommandResults.MODIFIERS)=='number' and UnitOperationTypes.PARAM_X and UnitOperationTypes.PARAM_Y,'district shot result/coordinate keys missing')\nlocal objects,seen={},{}\nfor _,d in player:GetDistricts():Members() do\n assert(d:GetOwner()==pid,'foreign district')\n local id=integer(d:GetID(),'district',4294967295);assert(not seen[id],'duplicate district');seen[id]=true\n local x,y=integer(d:GetX(),'source x',width-1),integer(d:GetY(),'source y',height-1)\n local c=d:GetCity();assert(c and c:GetOwner()==pid,'district city absent or foreign')\n local cid=integer(c:GetID(),'city',4294967295)\n -- Banner manager handles the city-center separately, by coordinates.\n if c:GetX()~=x or c:GetY()~=y then\n  assert(#objects<4096,'district shot roster exceeds bound')\n  local idx=integer(d:GetType(),'type',2147483647)\n  local def=GameInfo.Districts[idx];assert(def and def.Index==idx,'district definition absent')\n  local air=integer(def.AirSlots,'air slots',2147483647)\n  local strength=d:GetDefenseStrength()\n  assert(type(strength)=='number' and strength==strength and math.abs(strength)<1000000,'invalid native defense strength')\n  local complete=boolean(d:IsComplete(),'completion')\n  -- Aerodrome has priority even if a mod also assigns defense strength.\n  local banner=air==0 and strength>0 and complete\n  objects[#objects+1]={id=id,cid=cid,idx=idx,x=x,y=y,complete=complete,banner=banner,district=d}\n end\nend\ntable.sort(objects,function(a,b)return a.id<b.id end)\nlocal function snapshot()\n local out={'district-shot-v1|'..n(pid)..'|'..n(turn)..'|'..n(width)..'|'..n(height)}\n local choices={}\n for _,d in ipairs(objects) do\n  local allowed=false\n  if d.banner then allowed=boolean(CityManager.CanStartCommand(d.district,command),'banner legality') end\n  out[#out+1]=table.concat({'D',n(d.id),n(d.cid),n(d.idx),n(d.x),n(d.y),b(d.complete),b(d.banner),b(allowed)},'|')\n  if allowed then\n   local results=CityManager.GetCommandTargets(d.district,command,{})\n   assert(type(results)=='table','district shot target result unavailable')\n   local plots,mods=results[CityCommandResults.PLOTS],results[CityCommandResults.MODIFIERS]\n   if plots~=nil then\n    assert(type(plots)=='table' and type(mods)=='table' and #plots<=16384 and #plots==#mods,'district shot target arrays differ')\n    local targets,used={},{}\n    for i,modifier in ipairs(mods) do\n     local id=integer(plots[i],'target index',width*height-1)\n     if modifier==CityCommandResults.MODIFIER_IS_TARGET then\n      assert(not used[id],'duplicate native target');used[id]=true\n      local p=Map.GetPlotByIndex(id);assert(p and p:GetIndex()==id,'native target plot absent')\n      local x,y=integer(p:GetX(),'target x',width-1),integer(p:GetY(),'target y',height-1)\n      assert(id==y*width+x,'native target coordinates differ')\n      local params={[UnitOperationTypes.PARAM_X]=x,[UnitOperationTypes.PARAM_Y]=y}\n      if boolean(CityManager.CanStartCommand(d.district,command,params),'target legality') then\n       targets[#targets+1]={id=id,x=x,y=y,params=params}\n      end\n     end\n    end\n    table.sort(targets,function(a,b)return a.id<b.id end)\n    for _,t in ipairs(targets) do\n     assert(#choices<4096,'district shot choices exceed bound')\n     local wire=table.concat({'T',n(d.id),n(t.id),n(t.x),n(t.y)},'|')\n     out[#out+1]=wire;choices[#choices+1]={wire=wire,district=d.district,parameters=t.params}\n    end\n   end\n  end\n end\n ready();return table.concat(out,'\\n'),choices\nend\n"

def source(pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    verify_source()
    return f'local pid,turn={pid},{turn}\n'.encode() + LUA.encode()


def wire(v):
    validate_catalog(v, v['player_id'], v['turn'])
    rows = [f"district-shot-v1|{v['player_id']}|{v['turn']}|{v['width']}|{v['height']}"]
    for d in v['districts']:
        rows.append('|'.join((str(x) for x in ('D', d['district_id'], d['city_id'], d['type_index'], d['x'], d['y'], int(d['complete']), int(d['banner_eligible']), int(d['available'])))))
        for t in d['targets']:
            rows.append(f"T|{d['district_id']}|{t}|{t % v['width']}|{t // v['width']}")
    return '\n'.join(rows)

def parse(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > 524288:
        raise ValueError('Unbounded district-shot wire')
    text = raw.decode('ascii')
    lines = text.splitlines()
    h = lines[0].split('|') if lines else []
    if len(h) != 5 or h[:3] != ['district-shot-v1', str(pid), str(turn)]:
        raise ValueError('Foreign district-shot wire')
    v = dict(player_id=pid, turn=turn, width=int(h[3]), height=int(h[4]), districts=[])
    for line in lines[1:]:
        t = line.split('|')
        if len(t) == 9 and t[0] == 'D' and all((x in ('0', '1') for x in t[6:])):
            v['districts'].append(dict(zip(('district_id', 'city_id', 'type_index', 'x', 'y'), map(int, t[1:6])), complete=t[6] == '1', banner_eligible=t[7] == '1', available=t[8] == '1', targets=[]))
        elif len(t) == 5 and t[0] == 'T' and v['districts'] and (int(t[1]) == v['districts'][-1]['district_id']):
            v['districts'][-1]['targets'].append(int(t[2]))
        else:
            raise ValueError('Malformed district-shot row')
    validate_catalog(v, pid, turn)
    if wire(v) != text:
        raise ValueError('Noncanonical district-shot wire')
    return v

def catalog(prefix, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id, turn) + b'local text=snapshot();return text', b'@explicit_district_shots', capacity=524289)
    return parse(raw, player_id, turn)


def request_source(a, v):
    validate_action(a, v['width'], v['height'])
    if a not in actions(v):
        raise ValueError('District-shot choice outside native catalogue')
    selected = f"T|{a['district_id']}|{a['plot_id']}|{a['x']}|{a['y']}"
    return source(v['player_id'], v['turn']) + f"\nlocal text,choices=snapshot();assert(text=={json.dumps(wire(v))},'district-shot catalogue stale')\nlocal found=nil;for _,d in ipairs(choices) do if d.wire=={json.dumps(selected)} then assert(not found);found=d end end\nassert(found,'district shot no longer offered');ready()\nassert(CityManager.CanStartCommand(found.district,command,found.parameters)==true,'native district shot veto')\nCityManager.RequestCommand(found.district,command,found.parameters)\nreturn 'submitted'\n".encode()

def effect(a, before, after, old, new, old_defenses, new_defenses):
    compare_own_cities(old, before)
    compare_own_cities(new, after)
    if before['player_id'] != after['player_id'] or before['turn'] != after['turn']:
        raise RuntimeError('District shot crossed perspective or turn')
    initial = [u for u in before['visible_enemy_units'] if (u['x'], u['y']) == (a['x'], a['y'])]
    ids = {(u['owner'], u['id']) for u in initial}
    final = [u for u in after['visible_enemy_units'] if (u['owner'], u['id']) in ids]
    cb = [c for c in old_defenses if c['plot_id'] == a['plot_id']]
    ca = [c for c in new_defenses if c['plot_id'] == a['plot_id']]
    sb = next((d for d in old['districts'] if d['district_id'] == a['district_id']))
    sa = next((d for d in new['districts'] if d['district_id'] == a['district_id']))
    if initial == final and cb == ca and (sb == sa):
        raise RuntimeError('District command delivered without an observable native effect')
    return dict(visible_units_before=initial, visible_units_after=final, visible_cities_before=cb, visible_cities_after=ca, shooter_before=sb, shooter_after=sa, observable_native_change=True, target_visible_damage_increased=any((a['owner'] == b['owner'] and a['id'] == b['id'] and (a['damage'] > b['damage']) for a in final for b in initial)), native_defender_selection=True, death_or_capture_inferred_from_absence=False)

def apply(owner, prefix, a, turn, before, *, player_id=0):
    return city.execute(
        owner, prefix, a, turn, before, player_id=player_id,
        expected_catalogue=getattr(owner, 'explicit_district_shots', None),
        expected_defenses=getattr(owner, 'explicit_combat_cities', None),
        validate=validate_action, read_catalogue=catalog, compare=compare_own_cities,
        offers=actions, request=request_source, verify_effect=effect,
        shooter='district', proof_sha=PROOF_SHA)

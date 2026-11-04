"""Manual city shots at native target plots; the GameCore selects the defender."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib, json, copy
from civ6_host.runtime.native import native_city_range_attack as native
from civ6_host.runtime.native import native_saved_city_targets as defenses
from civ6_host.contracts.city_ranged import (
    city_actions as actions,
    city_compare_own_cities as compare_own_cities,
    city_validate_action as validate_action,
    city_validate_catalog as validate_catalog,
    CITY_FIELDS as FIELDS,
    CITY_SHOOTER_FIELDS as SHOOTER_FIELDS,
    uint,
)
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_city_shot.py')))).resolve().parents[1]
PROOF = ROOT / 'work/city-shot963/source.json'
PROOF_SHA = 'b18344ce7d53d04f10b050608f7ae1f9f40e7a74066eec4bda4885a41bc4d8af'

def verify_source():
    native.verify_inputs()
    defenses.verify_source()
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.native_city_shot_ui_route.static.v1':
        raise RuntimeError('City-shot source changed')
    for row in p['official_ui'].values():
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(row['path']))).read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('Official city-shot UI changed')
    return p


LUA = "\nlocal function integer(v,label,max)\n assert(type(v)=='number' and v%1==0 and v>=0 and v<=max,'invalid city shot '..label);return v\nend\nlocal function boolean(v,label) assert(type(v)=='boolean','invalid city shot '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'city shot perspective changed')\n local p=Players[pid];assert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),'city shot actor not ready')\n return p\nend\nlocal player=ready()\nlocal width,height=Map.GetGridSize()\ninteger(width,'width',16384);integer(height,'height',16384)\nassert(width>0 and height>0 and width*height==Map.GetPlotCount() and width*height<=16384,'city shot map outside bound')\nlocal command=CityCommandTypes.RANGE_ATTACK\nassert(command==-1967338303 and CityCommandResults.PLOTS==1933683541 and CityCommandResults.MODIFIER_IS_TARGET==889110605,'city shot enums changed')\nassert(type(CityCommandResults.MODIFIERS)=='number' and UnitOperationTypes.PARAM_X and UnitOperationTypes.PARAM_Y,'city shot result/coordinate keys missing')\nlocal objects,seen={},{}\nfor _,c in player:GetCities():Members() do\n assert(#objects<4096 and c:GetOwner()==pid,'city shot roster unbounded or foreign')\n local id=integer(c:GetID(),'city',4294967295);assert(not seen[id],'duplicate city');seen[id]=true\n local did=integer(c:GetDistrictID(),'center district',4294967295)\n local district=player:GetDistricts():FindID(did)\n local x,y=integer(c:GetX(),'source x',width-1),integer(c:GetY(),'source y',height-1)\n assert(district and district:GetOwner()==pid and district:GetID()==did and district:GetX()==x and district:GetY()==y,'city center identity differs')\n objects[#objects+1]={id=id,did=did,x=x,y=y,city=c,district=district}\nend\ntable.sort(objects,function(a,b)return a.id<b.id end)\nlocal function snapshot()\n local out={'city-shot-v1|'..n(pid)..'|'..n(turn)..'|'..n(width)..'|'..n(height)}\n local choices={}\n for _,c in ipairs(objects) do\n  -- The banner is gated on its center district; the clicked order uses city.\n  local allowed=boolean(CityManager.CanStartCommand(c.district,command),'banner legality')\n  out[#out+1]=table.concat({'C',n(c.id),n(c.did),n(c.x),n(c.y),allowed and '1' or '0'},'|')\n  if allowed then\n   -- Banner SetInterfaceMode has no arguments. Never fabricate a mode value.\n   local results=CityManager.GetCommandTargets(c.city,command,{})\n   assert(type(results)=='table','city shot target result unavailable')\n   local plots,mods=results[CityCommandResults.PLOTS],results[CityCommandResults.MODIFIERS]\n   if plots~=nil then\n    assert(type(plots)=='table' and type(mods)=='table' and #plots<=16384 and #plots==#mods,'city shot target arrays differ')\n    local targets,used={},{}\n    for i,modifier in ipairs(mods) do\n     local id=integer(plots[i],'target index',width*height-1)\n     if modifier==CityCommandResults.MODIFIER_IS_TARGET then\n      assert(not used[id],'duplicate native target');used[id]=true\n      local p=Map.GetPlotByIndex(id);assert(p and p:GetIndex()==id,'native target plot absent')\n      local x,y=integer(p:GetX(),'target x',width-1),integer(p:GetY(),'target y',height-1)\n      assert(id==y*width+x,'native target coordinates differ')\n      local params={[UnitOperationTypes.PARAM_X]=x,[UnitOperationTypes.PARAM_Y]=y}\n      if boolean(CityManager.CanStartCommand(c.city,command,params),'target legality') then\n       targets[#targets+1]={id=id,x=x,y=y,params=params}\n      end\n     end\n    end\n    table.sort(targets,function(a,b)return a.id<b.id end)\n    for _,t in ipairs(targets) do\n     assert(#choices<4096,'city shot choices exceed bound')\n     local wire=table.concat({'T',n(c.id),n(t.id),n(t.x),n(t.y)},'|')\n     out[#out+1]=wire;choices[#choices+1]={wire=wire,city=c.city,parameters=t.params}\n    end\n   end\n  end\n end\n ready();return table.concat(out,'\\n'),choices\nend\n"

def source(pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    verify_source()
    return f'local pid,turn={pid},{turn}\n'.encode() + LUA.encode()


def wire(v):
    validate_catalog(v, v['player_id'], v['turn'])
    rows = [f"city-shot-v1|{v['player_id']}|{v['turn']}|{v['width']}|{v['height']}"]
    for c in v['cities']:
        rows.append('|'.join((str(x) for x in ('C', c['city_id'], c['district_id'], c['x'], c['y'], int(c['available'])))))
        for t in c['targets']:
            rows.append(f"T|{c['city_id']}|{t}|{t % v['width']}|{t // v['width']}")
    return '\n'.join(rows)

def parse(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > 524288:
        raise ValueError('Unbounded city-shot wire')
    text = raw.decode('ascii')
    lines = text.splitlines()
    header = lines[0].split('|') if lines else []
    if len(header) != 5 or header[:3] != ['city-shot-v1', str(pid), str(turn)]:
        raise ValueError('Foreign city-shot wire')
    v = dict(player_id=pid, turn=turn, width=int(header[3]), height=int(header[4]), cities=[])
    for line in lines[1:]:
        t = line.split('|')
        if len(t) == 6 and t[0] == 'C' and (t[5] in ('0', '1')):
            v['cities'].append(dict(city_id=int(t[1]), district_id=int(t[2]), x=int(t[3]), y=int(t[4]), available=t[5] == '1', targets=[]))
        elif len(t) == 5 and t[0] == 'T' and v['cities'] and (int(t[1]) == v['cities'][-1]['city_id']):
            v['cities'][-1]['targets'].append(int(t[2]))
        else:
            raise ValueError('Malformed city-shot row')
    validate_catalog(v, pid, turn)
    if wire(v) != text:
        raise ValueError('Noncanonical city-shot wire')
    return v

def catalog(prefix, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id, turn) + b'local text=snapshot();return text', b'@explicit_city_shots', capacity=524289)
    return parse(raw, player_id, turn)


def request_source(a, v):
    validate_action(a, v['width'], v['height'])
    if a not in actions(v):
        raise ValueError('City-shot choice outside native catalogue')
    selected = f"T|{a['city_id']}|{a['plot_id']}|{a['x']}|{a['y']}"
    return source(v['player_id'], v['turn']) + f"\nlocal text,choices=snapshot();assert(text=={json.dumps(wire(v))},'city-shot catalogue stale')\nlocal found=nil;for _,c in ipairs(choices) do if c.wire=={json.dumps(selected)} then assert(not found);found=c end end\nassert(found,'city shot no longer offered');ready()\nassert(CityManager.CanStartCommand(found.city,command,found.parameters)==true,'native city shot veto')\nCityManager.RequestCommand(found.city,command,found.parameters)\nreturn 'submitted'\n".encode()

def effect(a, before, after, old, new, old_defenses, new_defenses):
    compare_own_cities(old, before)
    compare_own_cities(new, after)
    if before['player_id'] != after['player_id'] or before['turn'] != after['turn']:
        raise RuntimeError('City shot crossed perspective or turn')
    initial = [u for u in before['visible_enemy_units'] if (u['x'], u['y']) == (a['x'], a['y'])]
    ids = {(u['owner'], u['id']) for u in initial}
    final = [u for u in after['visible_enemy_units'] if (u['owner'], u['id']) in ids]
    cities_before = [c for c in old_defenses if c['plot_id'] == a['plot_id']]
    cities_after = [c for c in new_defenses if c['plot_id'] == a['plot_id']]
    shooter_before = next((c for c in old['cities'] if c['city_id'] == a['city_id']))
    shooter_after = next((c for c in new['cities'] if c['city_id'] == a['city_id']))
    changed = initial != final or cities_before != cities_after or shooter_before != shooter_after
    if not changed:
        raise RuntimeError('City command delivered without an observable native effect')
    return dict(visible_units_before=initial, visible_units_after=final, visible_cities_before=cities_before, visible_cities_after=cities_after, shooter_before=shooter_before, shooter_after=shooter_after, observable_native_change=True, target_visible_damage_increased=any((a['owner'] == b['owner'] and a['id'] == b['id'] and (a['damage'] > b['damage']) for a in final for b in initial)), native_defender_selection=True, death_or_capture_inferred_from_absence=False)

def execute(owner, prefix, a, turn, before, *, player_id, expected_catalogue,
            expected_defenses, validate, read_catalogue, compare, offers,
            request, verify_effect, shooter, proof_sha):
    """Execute against the caller's retained player catalogue and defense snapshot."""
    validate(a, before['width'], before['height'])
    old = read_catalogue(prefix, turn, player_id=player_id)
    compare(old, before)
    if old != expected_catalogue or a not in offers(old):
        raise RuntimeError(f'Stale {shooter}-shot decision')
    old_defenses = defenses.catalog(prefix, turn, player_id=player_id, collect=False)['cities']
    if old_defenses != expected_defenses:
        raise RuntimeError('Stale visible city defenses')
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError(f'{shooter.capitalize()}-shot transports not empty')
    label = f'@explicit_{shooter}_shot_request'.encode('ascii')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request(a, old), label)
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError(f'Expected one native {shooter} command')
    archive_hash = hashlib.sha256(prefix.actions.pending[0]).hexdigest()
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError(f'{shooter.capitalize()}-shot transport did not drain')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    new = read_catalogue(prefix, turn, player_id=player_id)
    new_defenses = defenses.catalog(prefix, turn, player_id=player_id, collect=False)['cities']
    receipt = verify_effect(a, before, after, old, new, old_defenses, new_defenses)
    owner.emit(f'official_explicit_{shooter}_shot_effect', action=a, effect=receipt,
               observation_before=before, observation_after=after, catalogue_before=old,
               catalogue_after=new, native_archive_sha256=archive_hash,
               source_proof_sha256=proof_sha, automatic_choices_applied=False,
               strategic_training_ready=False)
    return after


def apply(owner, prefix, a, turn, before, *, player_id=0):
    return execute(
        owner, prefix, a, turn, before, player_id=player_id,
        expected_catalogue=getattr(owner, 'explicit_city_shots', None),
        expected_defenses=getattr(owner, 'explicit_combat_cities', None),
        validate=validate_action, read_catalogue=catalog, compare=compare_own_cities,
        offers=actions, request=request_source, verify_effect=effect,
        shooter='city', proof_sha=PROOF_SHA)

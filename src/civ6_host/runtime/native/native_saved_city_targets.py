"""Visible native city defenses and source-backed unit orders to their plots.

No defender selection, damage formula, capture rule or life-state write.
World-click coastal raid/swap/air branches are not silently mapped to MOVE_TO.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _UNIT_ATTACK_BASE_CORE_SHA256
from civ6_host.contracts.capability_unit_attacks import validate_cities
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib, json, math
from pathlib import Path
from civ6_host.runtime.native import native_combat_actions as native
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_city_targets.py')))).resolve().parents[1]
SOURCE = ROOT / 'work/city-targets936/source.json'
SOURCE_SHA = 'de6e2d9e90b5086e16c8fde11176e9905309e88ded1490d2bb2b23a5e378d722'
CITY_FIELDS = {'owner', 'city_id', 'district_id', 'plot_id', 'x', 'y', 'garrison_damage', 'garrison_max', 'outer_damage', 'outer_max', 'defense_strength'}

def verify_source(*, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    if core_sha256 != _UNIT_ATTACK_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_unit_attack_profile import verify_source as selected_source
        return selected_source(core_sha256)
    native.verify_source_evidence(core_sha256=core_sha256)
    proof = load_pinned_json(SOURCE, SOURCE_SHA)
    if proof.get('schema') != 'civ6rl.city_targets936.source.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        raise RuntimeError('City-target source identity changed')
    for row in proof['installed_sources'].values():
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(row['path']))).read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('Official city-target UI source changed')
    return proof
_LUA = "\nlocal pid,turn=__PID__,__TURN__\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'city target perspective changed')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),'city target actor not ready')\nassert(Game.IsAllowStrategicCommands(pid),'city strategic commands unavailable')\nlocal width,height=Map.GetGridSize()\nlocal count=Map.GetPlotCount()\nassert(type(width)=='number' and width%1==0 and width>0 and type(height)=='number' and height%1==0 and height>0 and\n count==width*height and count<=16384,'city target map outside bounds')\nlocal visibility=PlayersVisibility[pid]\nassert(visibility and type(visibility.IsVisible)=='function' and type(visibility.IsRevealed)=='function','city target visibility unavailable')\nassert(CityManager and type(CityManager.GetCityAt)=='function' and DefenseTypes and\n DefenseTypes.DISTRICT_GARRISON~=nil and DefenseTypes.DISTRICT_OUTER~=nil,'city defense API unavailable')\nlocal function integer(v,label,max)\n assert(type(v)=='number' and v%1==0 and v>=0 and v<=max,'invalid city '..label)\n return v\nend\nlocal function scalar(v)\n assert(type(v)=='number' and v==v and v>=0 and v~=math.huge,'invalid city defense value')\n return v\nend\nlocal cities={}\nfor index=0,count-1 do\n local plot=Map.GetPlotByIndex(index)\n assert(plot,'city map plot absent')\n local x,y=plot:GetX(),plot:GetY()\n integer(x,'x',width-1);integer(y,'y',height-1)\n assert(index==y*width+x,'city plot coordinates changed')\n if visibility:IsVisible(x,y) and visibility:IsRevealed(index) then\n  -- No city lookup or ownership/defense getter is used before these gates.\n  local city=CityManager.GetCityAt(x,y)\n  if city then\n   assert(#cities<4096,'visible city bound')\n   local owner=integer(city:GetOwner(),'owner',63)\n   local id=integer(city:GetID(),'id',4294967295)\n   local districtID=integer(city:GetDistrictID(),'district id',4294967295)\n   local district=Players[owner]:GetDistricts():FindID(districtID)\n   assert(district and city:GetX()==x and city:GetY()==y,'city center district unavailable')\n   cities[#cities+1]={owner=owner,city_id=id,district_id=districtID,plot_id=index,x=x,y=y,\n    garrison_damage=scalar(district:GetDamage(DefenseTypes.DISTRICT_GARRISON)),\n    garrison_max=scalar(district:GetMaxDamage(DefenseTypes.DISTRICT_GARRISON)),\n    outer_damage=scalar(district:GetDamage(DefenseTypes.DISTRICT_OUTER)),\n    outer_max=scalar(district:GetMaxDamage(DefenseTypes.DISTRICT_OUTER)),\n    defense_strength=scalar(district:GetDefenseStrength())}\n  end\n end\nend\nlocal offers={}\nif __COLLECT__ then\n assert(UnitManager and type(UnitManager.CanStartOperation)=='function' and CombatManager and\n  type(CombatManager.IsAttackChangeWarState)=='function','city unit order API unavailable')\n local op,mods=UnitOperationTypes,UnitOperationMoveModifiers\n for _,name in ipairs({'RANGE_ATTACK','MOVE_TO','COASTAL_RAID','SWAP_UNITS','PARAM_X','PARAM_Y','PARAM_MODIFIERS'}) do\n  assert(op[name]~=nil,'city operation enum absent: '..name)\n end\n assert(mods.NONE~=nil and mods.ATTACK~=nil and mods.MOVE_IGNORE_UNEXPLORED_DESTINATION~=nil,'city movement flags absent')\n local directions={DirectionTypes.DIRECTION_NORTHEAST,DirectionTypes.DIRECTION_EAST,DirectionTypes.DIRECTION_SOUTHEAST,\n  DirectionTypes.DIRECTION_SOUTHWEST,DirectionTypes.DIRECTION_WEST,DirectionTypes.DIRECTION_NORTHWEST}\n local function adjacent(u,c)\n  for _,d in ipairs(directions) do local p=Map.GetAdjacentPlot(u:GetX(),u:GetY(),d)\n   if p and p:GetIndex()==c.plot_id then return true end\n  end\n  return false\n end\n local function add(u,c,operation,route,params)\n  assert(#offers<4096,'city attack catalogue bound')\n  offers[#offers+1]={unit_id=u:GetID(),operation=operation,input_route=route,target_owner=c.owner,target_id=c.city_id,\n   x=c.x,y=c.y,unit=u,city=c,parameters=params}\n end\n local work,units=0,0\n for _,u in player:GetUnits():Members() do\n  units=units+1;assert(units<=4096 and u:GetOwner()==pid,'own city-attack roster invalid')\n  if u:IsReadyToSelect() then\n   integer(u:GetID(),'unit id',4294967295)\n   local row=GameInfo.Units[u:GetUnitType()];assert(row,'unit domain unavailable')\n   if row.Domain~='DOMAIN_AIR' then\n    for _,c in ipairs(cities) do\n     work=work+1;assert(work<=100000,'city pair-work bound')\n     if c.owner~=pid and player:GetDiplomacy():IsAtWarWith(c.owner) then\n      local wars=CombatManager.IsAttackChangeWarState(u:GetComponentID(),c.x,c.y)\n      assert(wars==nil or type(wars)=='table','invalid additional war result')\n      if wars==nil or next(wars)==nil then\n       local params={[op.PARAM_X]=c.x,[op.PARAM_Y]=c.y}\n       if UnitManager.CanStartOperation(u,op.RANGE_ATTACK,nil,params) then\n        add(u,c,'RANGE_ATTACK','dedicated_ranged',params)\n       end\n       params={[op.PARAM_X]=c.x,[op.PARAM_Y]=c.y,[op.PARAM_MODIFIERS]=mods.NONE}\n       if UnitManager.CanStartOperation(u,op.RANGE_ATTACK,nil,params) and\n          (u:GetRangedCombat()>u:GetCombat() or u:GetBombardCombat()>u:GetCombat()) then\n        add(u,c,'RANGE_ATTACK','world_plot',params)\n       else\n        params={[op.PARAM_X]=c.x,[op.PARAM_Y]=c.y,[op.PARAM_MODIFIERS]=mods.ATTACK+mods.MOVE_IGNORE_UNEXPLORED_DESTINATION}\n        if not UnitManager.CanStartOperation(u,op.COASTAL_RAID,nil,params) and (u:GetX()~=c.x or u:GetY()~=c.y) and\n           not UnitManager.CanStartOperation(u,op.SWAP_UNITS,nil,params) and adjacent(u,c) and\n           UnitManager.CanStartOperation(u,op.MOVE_TO,nil,params) then\n         add(u,c,'MOVE_TO','world_plot',params)\n        end\n       end\n      end\n     end\n    end\n   end\n  end\n end\nend\n__FINISH__\n"
_SERIALIZE = '\nlocal function num(v) return string.format(\'%.17g\',v) end\nlocal rows={}\nfor _,c in ipairs(cities) do\n local fields={}\n for _,key in ipairs({\'owner\',\'city_id\',\'district_id\',\'plot_id\',\'x\',\'y\',\'garrison_damage\',\'garrison_max\',\'outer_damage\',\'outer_max\',\'defense_strength\'}) do\n  fields[#fields+1]=\'"\'..key..\'":\'..num(c[key])\n end\n rows[#rows+1]=\'{\'..table.concat(fields,\',\')..\'}\'\nend\nlocal choices={}\nfor _,o in ipairs(offers) do\n choices[#choices+1]=\'{"unit_id":\'..num(o.unit_id)..\',"operation":"\'..o.operation..\'","input_route":"\'..o.input_route..\n \'","target_owner":\'..num(o.target_owner)..\',"target_id":\'..num(o.target_id)..\',"x":\'..num(o.x)..\',"y":\'..num(o.y)..\'}\'\nend\nlocal out=\'{"player_id":\'..num(pid)..\',"turn":\'..num(turn)..\',"width":\'..num(width)..\',"height":\'..num(height)..\n \',"cities":[\'..table.concat(rows,\',\')..\'],"candidates":[\'..table.concat(choices,\',\')..\']}\'\nassert(#out<=2097152,\'city target response bound\')\nreturn out\n'

def source(turn, *, player_id=0, collect=True, finish=_SERIALIZE, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256, visible_scope=None):
    from civ6_host.runtime.xp1_attack_visible_scope import source_for_scope
    from civ6_host.runtime.xp1_unit_attack_profile import selected_readiness_source
    verify_source(core_sha256=core_sha256)
    native._player_id(player_id)
    native._uint(turn, 'turn')
    if type(collect) is not bool:
        raise ValueError('Exact catalogue flag required')
    return source_for_scope(selected_readiness_source(_LUA.replace('__PID__', str(player_id)).replace('__TURN__', str(turn)).replace('__COLLECT__', 'true' if collect else 'false').replace('__FINISH__', finish).encode('ascii'), core_sha256, 'city_source'), visible_scope, turn=turn, player_id=player_id, core_sha256=core_sha256)

def parse(raw, turn, player_id):
    if type(raw) is not bytes or len(raw) > 2097152:
        raise ValueError('Unbounded native city targets')
    value = json.loads(raw, object_pairs_hook=native._pairs_no_duplicates)
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'width', 'height', 'cities', 'candidates'} or type(value['player_id']) is not int or (value['player_id'] != player_id) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Stale native city targets')
    w, h = (value['width'], value['height'])
    if type(w) is not int or type(h) is not int or min(w, h) < 1 or (w * h > 16384):
        raise ValueError('Invalid city map size')
    cities = validate_cities(value['cities'], w, h)
    if type(value['candidates']) is not list or len(value['candidates']) > 4096:
        raise ValueError('Invalid city order list')
    seen = set()
    for r in value['candidates']:
        if type(r) is not dict or set(r) != {'unit_id', 'operation', 'input_route', 'target_owner', 'target_id', 'x', 'y'}:
            raise ValueError('Invalid city attack candidate')
        native._candidate({k: v for k, v in r.items() if k != 'input_route'}, player_id, w, h)
        if r['input_route'] not in ('world_plot', 'dedicated_ranged') or (r['input_route'] == 'dedicated_ranged' and r['operation'] != 'RANGE_ATTACK'):
            raise ValueError('Invalid city attack input route')
        if not any(((c['owner'], c['city_id'], c['x'], c['y']) == (r['target_owner'], r['target_id'], r['x'], r['y']) for c in cities)):
            raise ValueError('City order has no visible city witness')
        key = tuple((r[k] for k in ('unit_id', 'operation', 'input_route', 'x', 'y')))
        if key in seen:
            raise ValueError('Duplicate city attack choice')
        seen.add(key)
    return value

def catalog(prefix, turn, *, player_id=0, collect=True, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256, visible_scope=None):
    from civ6_host.runtime.xp1_attack_visible_scope import check, checked_result
    check(visible_scope, prefix, turn, player_id, core_sha256)
    return checked_result(visible_scope, prefix, turn, player_id, core_sha256, parse(prefix.runtime.evaluate_text(prefix.ui_child, source(turn, player_id=player_id, collect=collect, core_sha256=core_sha256, visible_scope=visible_scope), b'@explicit_visible_city_targets', capacity=2097153), turn, player_id))

def request_source(turn, selected, witness, *, player_id=0, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    from civ6_host.runtime.native.native_saved_combat import validate_action
    validate_action(selected)
    validate_cities([witness])
    if (witness['x'], witness['y'], witness['plot_id']) != (selected['x'], selected['y'], selected['plot_id']):
        raise ValueError('Selected city witness coordinates differ')
    checks = ' and '.join(('o.city.' + k + '==' + repr(v) for k, v in sorted(witness.items())))
    finish = f"local chosen=nil\nfor _,o in ipairs(offers) do\n if o.unit_id=={selected['unit_id']} and o.operation=='{selected['operation']}' and\n    o.input_route=='{selected['input_route']}' and {checks} then\n  assert(chosen==nil,'duplicate revalidated city order');chosen=o\n end\nend\nassert(chosen,'visible city, ownership, defenses or native legality changed')\nUnitManager.RequestOperation(chosen.unit,UnitOperationTypes[chosen.operation],chosen.parameters)\nreturn 'submitted'\n"
    return source(turn, player_id=player_id, finish=finish, core_sha256=core_sha256)

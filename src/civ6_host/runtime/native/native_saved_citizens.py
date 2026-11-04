"""PlotInfo citizen buttons, including specialist slots, via native MANAGE.

This module projects the shipped UI display, not the raw target arrays: exact
workers/capacity appear only with the multi-citizen meter, and locks are Boolean.
It submits one click and reads back native allocation; it never implements the
governor or assumes that every legal click changes a visible value.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _CITY_CONTROL_BASE_CORE
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_ui_profile import gate_admitted
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_citizens.py')))).resolve().parents[1]
PROOF = ROOT / 'work/city-management/source.json'
SOURCE_SHA = '480119ce6c920f22c8309af1d23413af137b1e7a2dc4c482abcf6b6cf58df919'
SCHEMA = 'civ6rl.native_city_citizens.v1'
PLOT_FIELDS = {'plot_id', 'x', 'y', 'occupied', 'locked', 'workers', 'capacity'}
FIELDS = PLOT_FIELDS | {'kind', 'city_id'}
LIMIT = 1048576
MAX_PLOTS = 16384

def verify_source(*, core_sha256=_CITY_CONTROL_BASE_CORE):
    if core_sha256 != _CITY_CONTROL_BASE_CORE:
        from civ6_host.runtime.expansion_city_controls_profile import verify_source as selected
        return selected(core_sha256)
    proof = load_pinned_json(PROOF, SOURCE_SHA)
    if proof['schema'] != 'civ6rl.city_management.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['contract']['native_rules_reimplemented'] is not False:
        raise RuntimeError('Citizen management source route differs')
    return proof

def uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid citizen management ' + label)
    return value

def _validate_plot(row):
    if type(row) is not dict or set(row) != PLOT_FIELDS:
        raise ValueError('Malformed citizen display row')
    for key in ('plot_id', 'x', 'y'):
        uint(row[key], key, MAX_PLOTS - 1)
    if any((type(row[key]) is not bool for key in ('occupied', 'locked'))):
        raise ValueError('Citizen occupancy and lock must be Boolean')
    workers, capacity = (row['workers'], row['capacity'])
    if workers is None or capacity is None:
        if workers is not None or capacity is not None:
            raise ValueError('Citizen meter values must be known together')
    else:
        uint(workers, 'workers', 2147483647)
        uint(capacity, 'capacity', 2147483647)
        if capacity <= 1 or row['occupied'] != (workers >= 1):
            raise ValueError('Citizen meter disagrees with the official display')
    return row

def validate_action(action):
    if type(action) is not dict or set(action) != FIELDS or action['kind'] != 'city_citizen':
        raise ValueError('Malformed citizen management action')
    uint(action['city_id'], 'city')
    _validate_plot({key: action[key] for key in PLOT_FIELDS})
    return action

def validate_catalog(value, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'city_id', 'plots'} or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Foreign citizen catalogue')
    uint(value['city_id'], 'city')
    if type(value['plots']) is not list or len(value['plots']) > MAX_PLOTS:
        raise ValueError('Unbounded citizen catalogue')
    ids, coordinates = ([], set())
    for row in value['plots']:
        _validate_plot(row)
        ids.append(row['plot_id'])
        coordinates.add((row['x'], row['y']))
    if ids != sorted(set(ids)) or len(coordinates) != len(ids):
        raise ValueError('Duplicate or unordered citizen plots')
    return value

def actions(value):
    validate_catalog(value, value['player_id'], value['turn'])
    return [dict(kind='city_citizen', city_id=value['city_id'], **row) for row in value['plots']]

def _plot_wire(row):
    _validate_plot(row)
    return '|'.join((str(value) for value in (row['plot_id'], row['x'], row['y'], int(row['occupied']), int(row['locked']), '-' if row['workers'] is None else row['workers'], '-' if row['capacity'] is None else row['capacity'])))

def parse_catalog(raw, pid, city_id, turn):
    uint(pid, 'player', 63)
    uint(city_id, 'city')
    uint(turn, 'turn', 2147483647)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded citizen catalogue wire')
    lines = raw.decode('ascii').splitlines()
    if not lines or len(lines) > MAX_PLOTS + 1 or lines[0] != f'city-citizens-v1|{pid}|{turn}|{city_id}':
        raise ValueError('Foreign or partial citizen catalogue wire')
    plots = []
    for line in lines[1:]:
        values = line.split('|')
        if len(values) != 7 or values[3] not in ('0', '1') or values[4] not in ('0', '1') or any((not item.isdigit() or str(int(item)) != item for item in values[:3])) or any((item != '-' and (not item.isdigit() or str(int(item)) != item) for item in values[5:])):
            raise ValueError('Malformed citizen catalogue wire row')
        plots.append(dict(plot_id=int(values[0]), x=int(values[1]), y=int(values[2]), occupied=values[3] == '1', locked=values[4] == '1', workers=None if values[5] == '-' else int(values[5]), capacity=None if values[6] == '-' else int(values[6])))
    return validate_catalog(dict(schema=SCHEMA, player_id=pid, turn=turn, city_id=city_id, plots=plots), pid, turn)
COMMON = "\nlocal function integer(v,label,low,high)\n assert(type(v)=='number' and v%1==0 and v>=low and v<=high,'invalid citizen '..label);return v\nend\nlocal function n(v) return string.format('%.0f',v) end\nlocal function ready()\n assert(Game and type(Game.GetLocalPlayer)=='function' and type(Game.GetLocalObserver)=='function'\n  and type(Game.GetCurrentGameTurn)=='function','citizen perspective API missing')\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale citizen perspective')\n local p=Players and Players[pid]\n assert(p and type(p.IsAlive)=='function' and type(p.IsTurnActive)=='function'\n  and type(p.IsTurnActiveComplete)=='function' and type(p.GetCities)=='function','citizen player API missing')\n assert(p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'citizen player not ready')\n return p\nend\nlocal player=ready()\nlocal cities=player:GetCities();assert(cities and type(cities.Members)=='function','citizen cities API missing')\nlocal city,seen,count=nil,{},0\nfor _,c in cities:Members() do\n count=count+1;assert(count<=4096,'citizen city collection bound')\n assert(c and type(c.GetOwner)=='function' and type(c.GetID)=='function','citizen city API missing')\n assert(integer(c:GetOwner(),'owner',0,63)==pid,'foreign citizen city collection')\n local id=integer(c:GetID(),'city',0,4294967295)\n assert(not seen[id],'duplicate citizen city');seen[id]=true\n if id==cityID then city=c end\nend\nassert(city,'citizen city missing')\nassert(Map and type(Map.GetGridSize)=='function' and type(Map.GetPlotCount)=='function'\n and type(Map.GetPlotByIndex)=='function','citizen map API missing')\nlocal width,height=Map.GetGridSize()\ninteger(width,'width',1,16384);integer(height,'height',1,16384)\nassert(width*height<=16384 and width*height==Map.GetPlotCount(),'citizen map bound')\nassert(CityManager and type(CityManager.GetCommandTargets)=='function','citizen targets API missing')\nlocal cc,cr=CityCommandTypes,CityCommandResults\nassert(cc and cr,'citizen command enums missing')\nfor _,name in ipairs({'MANAGE','PARAM_MANAGE_CITIZEN','PARAM_X','PARAM_Y'}) do\n integer(cc[name],name,-2147483648,2147483647)\nend\nassert(cc.MANAGE==729125427 and cc.PARAM_MANAGE_CITIZEN==1041406338,'citizen command identity changed')\nassert(cc.PARAM_X~=cc.PARAM_Y and cc.PARAM_X~=cc.PARAM_MANAGE_CITIZEN\n and cc.PARAM_Y~=cc.PARAM_MANAGE_CITIZEN,'citizen command parameters collide')\nlocal keys={}\nfor _,name in ipairs({'PLOTS','CITIZENS','MAX_CITIZENS','LOCKED_CITIZENS'}) do\n local key=integer(cr[name],name,-2147483648,2147483647)\n assert(not keys[key],'citizen target result keys collide');keys[key]=true\nend\nlocal function stillReady()\n assert(ready()==player and city:GetID()==cityID and city:GetOwner()==pid,'stale citizen city identity')\nend\nlocal function snapshot()\n -- Official witness: GetInterfaceModeParameter returned this key itself.\n -- Native parser 0x180508380 selects citizen mode5 by KEY PRESENCE only,\n -- then reads X/Y. Omitting the key selects a different command branch.\n local params={};params[cc.PARAM_MANAGE_CITIZEN]=cc.PARAM_MANAGE_CITIZEN\n local result=CityManager.GetCommandTargets(city,cc.MANAGE,params)\n local out={'city-citizens-v1|'..n(pid)..'|'..n(turn)..'|'..n(cityID)}\n local rows={}\n if result~=nil then\n  assert(type(result)=='table','citizen target result must be table or nil')\n  local plots=result[cr.PLOTS]\n  if plots~=nil then\n   assert(type(plots)=='table','citizen plot array missing')\n   local workers,capacity,locked=result[cr.CITIZENS],result[cr.MAX_CITIZENS],result[cr.LOCKED_CITIZENS]\n   -- The UI touches parallel arrays only when PLOTS contains a target.\n   local ids,indices={},{}\n   for index,id in pairs(plots) do\n    integer(index,'array index',1,16384);integer(id,'plot index',0,width*height-1)\n    assert(#indices<16384 and not ids[id],'duplicate/unbounded citizen plot');ids[id]=true\n    indices[#indices+1]=index\n   end\n   if #indices>0 then\n    assert(type(workers)=='table' and type(capacity)=='table' and type(locked)=='table','citizen parallel arrays missing')\n    for _,array in ipairs({workers,capacity,locked}) do\n     local size=0\n     for index,_ in pairs(array) do\n      integer(index,'parallel array index',1,16384);size=size+1\n      assert(size<=16384 and plots[index]~=nil,'citizen parallel array keys differ')\n     end\n     assert(size==#indices,'citizen parallel array length differs')\n    end\n   end\n   for _,index in ipairs(indices) do\n    local id=plots[index]\n    local w=integer(workers[index],'workers',0,2147483647)\n    local cap=integer(capacity[index],'capacity',0,2147483647)\n    local lock=integer(locked[index],'locked',0,2147483647)\n    local p=Map.GetPlotByIndex(id)\n    assert(p and type(p.GetIndex)=='function' and type(p.GetX)=='function' and type(p.GetY)=='function','citizen target plot absent')\n    local x,y=integer(p:GetX(),'x',0,width-1),integer(p:GetY(),'y',0,height-1)\n    assert(p:GetIndex()==id and id==y*width+x,'citizen plot coordinates differ')\n    local wire=table.concat({n(id),n(x),n(y),w>=1 and '1' or '0',lock>0 and '1' or '0',\n      cap>1 and n(w) or '-',cap>1 and n(cap) or '-'},'|')\n    rows[#rows+1]={id=id,x=x,y=y,wire=wire}\n   end\n  end\n end\n table.sort(rows,function(a,b)return a.id<b.id end)\n for _,row in ipairs(rows) do out[#out+1]=row.wire end\n stillReady();return table.concat(out,'\\n'),rows\nend\n"

def preamble(pid, city_id, turn, *, core_sha256=_CITY_CONTROL_BASE_CORE):
    verify_source(core_sha256=core_sha256)
    uint(pid, 'player', 63)
    uint(city_id, 'city')
    uint(turn, 'turn', 2147483647)
    return f'local pid,cityID,turn={pid},{city_id},{turn}\n'.encode() + COMMON.encode()

def catalog_source(pid, city_id, turn, *, core_sha256=_CITY_CONTROL_BASE_CORE):
    return preamble(pid, city_id, turn, core_sha256=core_sha256) + b'local wire=snapshot();return wire\n'

def request_source(action, pid, turn, *, core_sha256=_CITY_CONTROL_BASE_CORE):
    validate_action(action)
    expected = _plot_wire({key: action[key] for key in PLOT_FIELDS})
    return preamble(pid, action['city_id'], turn, core_sha256=core_sha256) + f"\nlocal _,rows=snapshot()\nlocal selected=nil\nfor _,row in ipairs(rows) do if row.id=={action['plot_id']} then selected=row end end\nassert(selected and selected.wire=='{expected}','citizen button state changed or no longer offered')\nassert(type(CityManager.RequestCommand)=='function','citizen request API missing')\nlocal params={{}};params[cc.PARAM_MANAGE_CITIZEN]=cc.PARAM_MANAGE_CITIZEN\nparams[cc.PARAM_X]=selected.x;params[cc.PARAM_Y]=selected.y\nstillReady();CityManager.RequestCommand(city,cc.MANAGE,params)\nreturn 'submitted'\n".encode()

def _ui_enabled(value):
    if value is not True:
        raise ValueError('Citizen management requires explicit diagnostic UI enablement')

def catalog(prefix, city_id, turn, *, player_id=0, diagnostic_ui_enabled=False, core_sha256=_CITY_CONTROL_BASE_CORE):
    """Native displayed buttons; tutorial/control gates still require qualification."""
    _ui_enabled(diagnostic_ui_enabled)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, city_id, turn, core_sha256=core_sha256), b'@explicit_city_citizens_catalog', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, city_id, turn)

def apply(owner, prefix, action, turn, before, *, player_id=0, diagnostic_ui_enabled=False, core_sha256=_CITY_CONTROL_BASE_CORE):
    _ui_enabled(diagnostic_ui_enabled)
    validate_action(action)
    uint(player_id, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(before) is not dict or type(before.get('player_id')) is not int or before['player_id'] != player_id or (type(before.get('turn')) is not int) or (before['turn'] != turn):
        raise ValueError('Citizen observation has stale player or turn')
    if prefix.actions.pending:
        raise RuntimeError('Citizen click requires an empty native command queue')
    fresh = catalog(prefix, action['city_id'], turn, player_id=player_id, diagnostic_ui_enabled=True, core_sha256=core_sha256)
    if action not in actions(fresh):
        raise RuntimeError('Citizen button is no longer offered in its displayed state')
    if prefix.actions.pending:
        raise RuntimeError('Citizen catalogue unexpectedly queued a command')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, player_id, turn, core_sha256=core_sha256), b'@explicit_city_citizens_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Citizen click did not enqueue exactly one native command')
    prefix.actions.deliver_one()
    if prefix.actions.pending:
        raise RuntimeError('Citizen command queue did not drain')
    if core_sha256 == _CITY_CONTROL_BASE_CORE:
        prefix.deferred_events.drain_empty_receivers()
    else:
        prefix.deferred_events.drain()
    prefix.view_publisher.publish()
    final = catalog(prefix, action['city_id'], turn, player_id=player_id, diagnostic_ui_enabled=True, core_sha256=core_sha256)
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if type(after['player_id']) is not int or after['player_id'] != player_id or type(after['turn']) is not int or (after['turn'] != turn):
        raise RuntimeError('Citizen click crossed native perspective or turn')
    if prefix.actions.pending:
        raise RuntimeError('Citizen readback unexpectedly queued a command')
    owner.emit('official_explicit_city_citizen_effect', action=action, citizens_before=fresh, citizens_after=final, displayed_state_changed=fresh != final, observation_before=before, observation_after=after, native_commands_delivered=1, native_assignment_reimplemented=False, diagnostic_ui_enabled=not gate_admitted(owner, 'city_citizens'), ui_tutorial_gate_qualified=gate_admitted(owner, 'city_citizens'), automatic_choices_applied=False, strategic_training_ready=False)
    return after

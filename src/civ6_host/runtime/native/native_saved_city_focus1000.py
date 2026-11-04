"""Official CityPanel yield-focus clicks, using native citizen allocation.

The two public flags are retained independently. CitySupport displays favored
before ignored; even the uncommon both-true state follows the shipped click
handler rather than being normalized. No governor or legality rule is ported.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _CITY_CONTROL_BASE_CORE
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_ui_profile import gate_admitted
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_city_focus1000.py')))).resolve().parents[1]
SOURCE_SHA = '5b5436dbc98d995cd9e104277c725cc00ecb532acfea82698b18922536c4ac8f'
SCHEMA = 'civ6rl.native_city_focus1000.v1'
YIELDS = ('YIELD_FOOD', 'YIELD_PRODUCTION', 'YIELD_GOLD', 'YIELD_SCIENCE', 'YIELD_CULTURE', 'YIELD_FAITH')
FIELDS = {'kind', 'city_id', 'yield_type', 'yield_index', 'favored', 'disfavored'}
LIMIT = 4096

def verify_source(*, core_sha256=_CITY_CONTROL_BASE_CORE):
    if core_sha256 != _CITY_CONTROL_BASE_CORE:
        from civ6_host.runtime.expansion_city_controls_profile import verify_source as selected
        return selected(core_sha256)
    if not SOURCE_SHA:
        raise RuntimeError('City focus source proof is not pinned')
    proof = load_pinned_json(ROOT / 'work/city-focus1000/source.json', SOURCE_SHA)
    if proof['schema'] != 'civ6rl.city_focus1000.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['contract']['native_rules_reimplemented'] is not False:
        raise RuntimeError('City focus source route differs')
    return proof

def uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid city focus ' + label)
    return value

def validate_action(action):
    if type(action) is not dict or set(action) != FIELDS or action['kind'] != 'city_focus':
        raise ValueError('Malformed city focus action')
    uint(action['city_id'], 'city')
    uint(action['yield_index'], 'yield index', 2147483647)
    if action['yield_type'] not in YIELDS or type(action['yield_type']) is not str:
        raise ValueError('Unsupported city focus yield')
    if any((type(action[key]) is not bool for key in ('favored', 'disfavored'))):
        raise ValueError('City focus states must be Boolean')
    return action

def transition(action):
    """Ordered UI request parameters and final flags, not governor logic."""
    validate_action(action)
    favored, ignored = (action['favored'], action['disfavored'])
    if favored:
        if ignored:
            return (((1, 0),), (True, False))
        return (((0, 0), (1, 1)), (False, True))
    if ignored:
        return (((1, 0),), (False, False))
    return (((0, 1),), (True, False))
COMMON = "\nlocal function integer(v,label,low,high)\n assert(type(v)=='number' and v%1==0 and v>=low and v<=high,'invalid city focus '..label);return v\nend\nlocal function bool(v,label) assert(type(v)=='boolean','invalid city focus '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function ready()\n assert(Game and type(Game.GetLocalPlayer)=='function' and type(Game.GetLocalObserver)=='function'\n  and type(Game.GetCurrentGameTurn)=='function','city focus perspective API missing')\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale city focus perspective')\n local p=Players and Players[pid]\n assert(p and type(p.IsAlive)=='function' and type(p.IsTurnActive)=='function'\n  and type(p.IsTurnActiveComplete)=='function' and type(p.GetCities)=='function','city focus player API missing')\n assert(p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'city focus player not ready')\n return p\nend\nlocal player=ready()\nlocal cities=player:GetCities();assert(cities and type(cities.Members)=='function','city focus cities API missing')\nlocal city,seen,count=nil,{},0\nfor _,c in cities:Members() do\n count=count+1;assert(count<=4096,'city focus city collection bound')\n assert(c and type(c.GetOwner)=='function' and type(c.GetID)=='function','city focus city API missing')\n assert(integer(c:GetOwner(),'owner',0,63)==pid,'city focus foreign city collection')\n local id=integer(c:GetID(),'city',0,4294967295)\n assert(not seen[id],'duplicate city focus city');seen[id]=true\n if id==cityID then city=c end\nend\nassert(city and type(city.GetCitizens)=='function','city focus city missing')\nlocal citizens=city:GetCitizens()\nassert(citizens and type(citizens.IsFavoredYield)=='function' and type(citizens.IsDisfavoredYield)=='function','city focus citizens API missing')\nassert(GameInfo and GameInfo.Yields and YieldTypes,'city focus public yields missing')\nlocal definitions={};local yieldIndices={}\nfor _,name in ipairs({'YIELD_FOOD','YIELD_PRODUCTION','YIELD_GOLD','YIELD_SCIENCE','YIELD_CULTURE','YIELD_FAITH'}) do\n local row=GameInfo.Yields[name]\n assert(row and row.YieldType==name,'city focus yield definition missing or renamed')\n local index=integer(row.Index,'yield index',0,2147483647)\n assert(integer(YieldTypes[string.sub(name,7)],'UI yield index',0,2147483647)==index,'city focus UI yield index differs')\n assert(not yieldIndices[index],'duplicate city focus yield index');yieldIndices[index]=true\n definitions[#definitions+1]={name=name,index=index}\nend\nlocal function state(index)\n return bool(citizens:IsFavoredYield(index),'favored'),bool(citizens:IsDisfavoredYield(index),'disfavored')\nend\nlocal function stillReady()\n assert(ready()==player and city:GetID()==cityID and city:GetOwner()==pid,'stale city focus city identity')\nend\n"

def preamble(pid, city_id, turn, *, core_sha256=_CITY_CONTROL_BASE_CORE):
    verify_source(core_sha256=core_sha256)
    uint(pid, 'player', 63)
    uint(city_id, 'city')
    uint(turn, 'turn', 2147483647)
    return f'local pid,cityID,turn={pid},{city_id},{turn}\n'.encode() + COMMON.encode()

def catalog_source(pid, city_id, turn, *, core_sha256=_CITY_CONTROL_BASE_CORE):
    return preamble(pid, city_id, turn, core_sha256=core_sha256) + "\nlocal out={'city-focus1000-v1|'..n(pid)..'|'..n(turn)..'|'..n(cityID)}\nfor _,row in ipairs(definitions) do\n local favored,ignored=state(row.index)\n out[#out+1]=table.concat({row.name,n(row.index),favored and '1' or '0',ignored and '1' or '0'},'|')\nend\nstillReady();return table.concat(out,'\\n')\n".encode()

def validate_catalog(value, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'city_id', 'yields'} or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Foreign city focus catalogue')
    uint(value['city_id'], 'city')
    if type(value['yields']) is not list or len(value['yields']) != len(YIELDS):
        raise ValueError('City focus catalogue requires exactly six yields')
    indices = set()
    for name, row in zip(YIELDS, value['yields']):
        if type(row) is not dict or set(row) != {'yield_type', 'index', 'favored', 'disfavored'} or row['yield_type'] != name:
            raise ValueError('City focus yield order or fields differ')
        index = uint(row['index'], 'yield index', 2147483647)
        if index in indices or any((type(row[key]) is not bool for key in ('favored', 'disfavored'))):
            raise ValueError('Duplicate yield index or malformed city focus states')
        indices.add(index)
    return value

def parse_catalog(raw, pid, city_id, turn):
    uint(city_id, 'city')
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded city focus catalogue')
    lines = raw.decode('ascii').splitlines()
    if len(lines) != 7 or lines[0] != f'city-focus1000-v1|{pid}|{turn}|{city_id}':
        raise ValueError('Foreign or partial city focus catalogue')
    rows = []
    for line in lines[1:]:
        values = line.split('|')
        if len(values) != 4 or not values[1].isdigit() or str(int(values[1])) != values[1] or (values[2] not in ('0', '1')) or (values[3] not in ('0', '1')):
            raise ValueError('Malformed city focus row')
        rows.append(dict(yield_type=values[0], index=int(values[1]), favored=values[2] == '1', disfavored=values[3] == '1'))
    return validate_catalog(dict(schema=SCHEMA, player_id=pid, turn=turn, city_id=city_id, yields=rows), pid, turn)

def actions(value):
    validate_catalog(value, value['player_id'], value['turn'])
    return [dict(kind='city_focus', city_id=value['city_id'], yield_type=row['yield_type'], yield_index=row['index'], favored=row['favored'], disfavored=row['disfavored']) for row in value['yields']]

def request_source(action, pid, turn, *, core_sha256=_CITY_CONTROL_BASE_CORE):
    validate_action(action)
    requests, _ = transition(action)
    favored = 'true' if action['favored'] else 'false'
    ignored = 'true' if action['disfavored'] else 'false'
    code = preamble(pid, action['city_id'], turn, core_sha256=core_sha256) + f"\nlocal row=GameInfo.Yields['{action['yield_type']}']\nassert(row.Index=={action['yield_index']},'city focus yield index changed')\nlocal favored,ignored=state(row.Index)\nassert(favored=={favored} and ignored=={ignored},'city focus flags changed')\nassert(CityManager and type(CityManager.RequestCommand)=='function','city focus request API missing')\nlocal cc=CityCommandTypes;assert(cc,'city focus command types missing')\nfor _,name in ipairs({{'SET_FOCUS','PARAM_FLAGS','PARAM_YIELD_TYPE','PARAM_DATA0'}}) do\n integer(cc[name],name,-2147483648,2147483647)\nend\nassert(cc.PARAM_FLAGS~=cc.PARAM_YIELD_TYPE and cc.PARAM_FLAGS~=cc.PARAM_DATA0 and cc.PARAM_YIELD_TYPE~=cc.PARAM_DATA0,'city focus command parameters collide')\nstillReady()\n".encode()
    for flags, data in requests:
        code += f'\ndo\n local params={{}};params[cc.PARAM_FLAGS]={flags};params[cc.PARAM_YIELD_TYPE]=row.Index;params[cc.PARAM_DATA0]={data}\n CityManager.RequestCommand(city,cc.SET_FOCUS,params)\nend\n'.encode()
    return code + b"return 'submitted'\n"

def _ui_enabled(value):
    if value is not True:
        raise ValueError('City focus requires explicit diagnostic UI enablement')

def catalog(prefix, city_id, turn, *, player_id=0, diagnostic_ui_enabled=False, core_sha256=_CITY_CONTROL_BASE_CORE):
    """Opt-in diagnostic only; the tutorial UI gate is not qualified."""
    _ui_enabled(diagnostic_ui_enabled)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, city_id, turn, core_sha256=core_sha256), b'@explicit_city_focus_catalog1000', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, city_id, turn)

def apply(owner, prefix, action, turn, before, *, player_id=0, diagnostic_ui_enabled=False, core_sha256=_CITY_CONTROL_BASE_CORE):
    """Replay an explicit UI gesture, without claiming its tutorial gate proven."""
    _ui_enabled(diagnostic_ui_enabled)
    validate_action(action)
    uint(player_id, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(before) is not dict or type(before.get('player_id')) is not int or before['player_id'] != player_id or (type(before.get('turn')) is not int) or (before['turn'] != turn):
        raise ValueError('City focus observation has stale player or turn')
    if len(prefix.actions.pending) != 0:
        raise RuntimeError('City focus requires an empty native command queue')
    fresh = catalog(prefix, action['city_id'], turn, player_id=player_id, diagnostic_ui_enabled=True, core_sha256=core_sha256)
    if action not in actions(fresh):
        raise RuntimeError('City focus state is no longer offered')
    if len(prefix.actions.pending) != 0:
        raise RuntimeError('City focus catalogue unexpectedly queued a command')
    requests, final_flags = transition(action)
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, player_id, turn, core_sha256=core_sha256), b'@explicit_city_focus_request1000')
    if submitted != b'submitted' or len(prefix.actions.pending) != len(requests):
        raise RuntimeError('City focus did not enqueue the exact ordered command count')
    for remaining in range(len(requests), 0, -1):
        if len(prefix.actions.pending) != remaining:
            raise RuntimeError('City focus command queue changed during delivery')
        prefix.actions.deliver_one()
    if prefix.actions.pending:
        raise RuntimeError('City focus command queue did not drain')
    if core_sha256 == _CITY_CONTROL_BASE_CORE:
        prefix.deferred_events.drain_empty_receivers()
    else:
        prefix.deferred_events.drain()
    prefix.view_publisher.publish()
    final = catalog(prefix, action['city_id'], turn, player_id=player_id, diagnostic_ui_enabled=True, core_sha256=core_sha256)
    expected = [dict(row) for row in fresh['yields']]
    index = YIELDS.index(action['yield_type'])
    expected[index]['favored'], expected[index]['disfavored'] = final_flags
    if final['yields'] != expected or final['city_id'] != fresh['city_id']:
        raise RuntimeError('Native city focus result differs from the official UI transition')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if type(after['player_id']) is not int or after['player_id'] != player_id or type(after['turn']) is not int or (after['turn'] != turn):
        raise RuntimeError('City focus crossed native perspective or turn')
    if prefix.actions.pending:
        raise RuntimeError('City focus readback unexpectedly queued a command')
    owner.emit('official_explicit_city_focus_effect1000', action=action, ordered_commands=[dict(flags=flags, data0=data) for flags, data in requests], focus_before=fresh, focus_after=final, observation_before=before, observation_after=after, diagnostic_ui_enabled=not gate_admitted(owner, 'city_focus'), ui_tutorial_gate_qualified=gate_admitted(owner, 'city_focus'), automatic_choices_applied=False, strategic_training_ready=False)
    return after

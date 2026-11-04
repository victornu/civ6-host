"""Explicit stock RazeCity choices through the native city-command pipeline.

No direct DestroyCity/TransferCity, automatic KEEP, or fabricated native result.
This is the pinned Base UI route, not an assertion of expansion compatibility.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_captured_city.py')))).resolve().parents[1]
SOURCE_SHA = 'bd89ab8904d85676d547422f4e8b5027cdb93f0171b50915129c177565d9dbda'
DIRECTIVES = ('KEEP', 'RAZE', 'LIBERATE_FOUNDER', 'LIBERATE_PREVIOUS_OWNER')
FIELDS = {'kind', 'city_id', 'directive'}
CITY_FIELDS = ('city_id', 'x', 'y', 'original_owner', 'previous_owner', 'conquered_from')

def verify_source():
    p = load_pinned_json(ROOT / 'work/city-continuation937/capture-choice-source.json', SOURCE_SHA)
    if p['schema'] != 'civ6rl.captured_city_choice937.source.v1' or p['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or p['contract'] != dict(city_selector='Players[localPlayer]:GetCities():GetNextCapturedCity()', command='CityCommandTypes.DESTROY', parameter_key='UnitOperationTypes.PARAM_FLAGS', directives=DIRECTIVES, selection_explicit=True, rules_reimplemented=False) or (hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(p['official_ui']['path']))).read_bytes()).hexdigest() != p['official_ui']['sha256']):
        raise RuntimeError('Captured-city official source changed')

def uint(v, label, maximum=4294967295):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError('Invalid captured-city ' + label)
    return v

def validate_action(a):
    if type(a) is not dict or set(a) != FIELDS or a['kind'] != 'resolve_captured_city' or (a['directive'] not in DIRECTIVES):
        raise ValueError('Unknown captured-city action')
    uint(a['city_id'], 'id')
    return a
COMMON = "\nlocal function integer(v,name,maximum)\n assert(type(v)=='number' and v%1==0 and v>=0 and v<=maximum,'invalid captured city '..name);return v\nend\nlocal function bool(v,name) assert(type(v)=='boolean','invalid captured city '..name);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'captured-city perspective changed')\n local p=Players[pid]\n assert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),'captured-city actor not ready')\n return p\nend\nlocal player=ready()\nlocal city=player:GetCities():GetNextCapturedCity()\nlocal row=nil\nlocal choices={}\nif city then\n assert(city:GetOwner()==pid,'captured city belongs to another player')\n row={city_id=integer(city:GetID(),'id',4294967295),x=integer(city:GetX(),'x',65535),y=integer(city:GetY(),'y',65535),\n  original_owner=integer(city:GetOriginalOwner(),'original owner',63),\n  previous_owner=integer(city:GetOwnerBeforeOccupation(),'previous owner',63),\n  conquered_from=integer(city:GetJustConqueredFrom(),'conquered from',63)}\n local diplomacy=player:GetDiplomacy()\n assert(CityManager and type(CityManager.CanStartCommand)=='function' and type(CityManager.RequestCommand)=='function','city command API missing')\n assert(CityCommandTypes.DESTROY~=nil and UnitOperationTypes.PARAM_FLAGS~=nil and CityDestroyDirectives,'city directive enums missing')\n local shown={KEEP=true,RAZE=bool(city:CanRaze(),'can raze')}\n shown.LIBERATE_FOUNDER=(row.original_owner~=row.previous_owner and\n  bool(diplomacy:CanLiberateCityTo(row.original_owner),'liberate founder') and row.original_owner~=row.conquered_from)\n shown.LIBERATE_PREVIOUS_OWNER=(bool(diplomacy:CanLiberateCityTo(row.previous_owner),'liberate previous') and row.previous_owner~=row.conquered_from)\n for _,name in ipairs({'KEEP','RAZE','LIBERATE_FOUNDER','LIBERATE_PREVIOUS_OWNER'}) do\n  local value=CityDestroyDirectives[name];assert(type(value)=='number' and value%1==0,'directive missing')\n  local params={};params[UnitOperationTypes.PARAM_FLAGS]=value\n  -- Exactly the stock popup's three-argument overload and its button gates.\n  local legal=shown[name] and bool(CityManager.CanStartCommand(city,CityCommandTypes.DESTROY,params),'command legality')\n  if legal then choices[#choices+1]={directive=name,parameters=params} end\n end\nend\n"

def preamble(pid, turn):
    verify_source()
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    return f'local pid,turn={pid},{turn}\n'.encode() + COMMON.encode()

def catalog_source(pid, turn):
    return preamble(pid, turn) + b"\nlocal out={'captured-city-v1|'..n(pid)..'|'..n(turn)}\nif row then\n local fields={'city'}\n for _,key in ipairs({'city_id','x','y','original_owner','previous_owner','conquered_from'}) do fields[#fields+1]=n(row[key]) end\n out[#out+1]=table.concat(fields,'|')\n for _,choice in ipairs(choices) do out[#out+1]='choice|'..choice.directive end\nend\nready();return table.concat(out,'\\n')\n"

def validate_catalog(value, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'city', 'directives'} or type(value['player_id']) is not int or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn) or (type(value['directives']) is not list) or (len(value['directives']) > 4) or any((type(d) is not str or d not in DIRECTIVES for d in value['directives'])) or (len(set(value['directives'])) != len(value['directives'])):
        raise ValueError('Invalid captured-city catalogue')
    city = value['city']
    if city is None:
        if value['directives']:
            raise ValueError('Directive without captured city')
    else:
        if type(city) is not dict or set(city) != set(CITY_FIELDS):
            raise ValueError('Invalid captured city witness')
        for key, v in city.items():
            uint(v, key, 4294967295 if key == 'city_id' else 65535 if key in ('x', 'y') else 63)
    return value

def parse_catalog(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > 2048:
        raise ValueError('Unbounded captured-city readback')
    lines = raw.decode('ascii').splitlines()
    if not lines or lines[0] != f'captured-city-v1|{pid}|{turn}' or len(lines) > 6:
        raise ValueError('Foreign captured-city readback')
    result = dict(player_id=pid, turn=turn, city=None, directives=[])
    if len(lines) > 1:
        values = lines[1].split('|')
        if len(values) != 7 or values[0] != 'city' or any((not v.isdigit() or str(int(v)) != v for v in values[1:])):
            raise ValueError('Malformed captured-city fields')
        result['city'] = dict(zip(CITY_FIELDS, map(int, values[1:])))
        for line in lines[2:]:
            if not line.startswith('choice|'):
                raise ValueError('Malformed captured-city directive')
            result['directives'].append(line[7:])
    return validate_catalog(result, pid, turn)

def actions(value):
    validate_catalog(value, value['player_id'], value['turn'])
    return [dict(kind='resolve_captured_city', city_id=value['city']['city_id'], directive=d) for d in value['directives']]

def catalog(prefix, turn, *, player_id=0):
    return parse_catalog(prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, turn), b'@explicit_captured_city_catalog', capacity=2049), player_id, turn)

def request_source(action, expected, pid, turn):
    validate_action(action)
    validate_catalog(expected, pid, turn)
    if action not in actions(expected):
        raise ValueError('Captured-city action was not offered')
    checks = ' and '.join(('row.' + k + '==' + str(v) for k, v in expected['city'].items()))
    return preamble(pid, turn) + f"\nassert(row and {checks},'captured-city identity or history changed')\nlocal selected=nil\nfor _,choice in ipairs(choices) do if choice.directive=='{action['directive']}' then selected=choice end end\nassert(selected,'captured-city directive no longer available')\nready();CityManager.RequestCommand(city,CityCommandTypes.DESTROY,selected.parameters)\nreturn 'submitted'\n".encode()

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    old = getattr(owner, 'explicit_captured_city', None)
    fresh = catalog(prefix, turn, player_id=player_id)
    if fresh != old or action not in actions(fresh):
        raise RuntimeError('Captured city or directive changed since publication')
    result = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, fresh, player_id, turn), b'@explicit_captured_city_request')
    if result != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Expected one native captured-city command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after['player_id'] != player_id or after['turn'] != turn:
        raise RuntimeError('Captured-city command crossed perspective or turn')
    next_city = catalog(prefix, turn, player_id=player_id)
    if next_city['city'] is not None and next_city['city']['city_id'] == action['city_id']:
        raise RuntimeError('Native city choice remains pending after command')
    if action['directive'] == 'KEEP' and (not any((c['id'] == action['city_id'] for c in after['cities']))):
        raise RuntimeError('Kept city absent from native own-city observation')
    owner.emit('official_explicit_captured_city_effect', action=action, catalog_before=fresh, catalog_after=next_city, observation_before=before, observation_after=after, choice_no_longer_pending=True, disappearance_interpreted_as_razed=False, source_sha256=SOURCE_SHA, automatic_choices_applied=False, strategic_training_ready=False)
    return after

"""Native production candidate getters and the shipped tooltip projection.

No cost or turn rule is reimplemented. The unit tooltip's nil formation path
really uses a base database cost; it must not be replaced with the queue cost.
Raw queue values remain verification data, not extra actor features.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from civ6_host.runtime.native import native_city_production_observation as current
from civ6_host.contracts.production_info988 import SCHEMA
from civ6_host.contracts.production_info988 import validate
PROOF_SHA256 = current.PROOF_SHA256
PANEL_SHA256 = current._PANEL_SHA256
TOOLTIP_SHA256 = '3929f5528f4499cf675868638e98b55b40796b922dc414e9ec34ae3d044a6ce7'
KINDS = ('production', 'production_placement', 'production_resume', 'queue_append')
CAPACITY = 4 * 1024 * 1024

def verified_files():
    current.verify_source()
    files = {current.PROOF_PATH: PROOF_SHA256, current._ASSETS / 'Panels/ProductionPanel.lua': PANEL_SHA256, current._ASSETS / 'ToolTipHelper.lua': TOOLTIP_SHA256}
    for path, pin in files.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != pin:
            raise RuntimeError('Production information source changed: ' + path.name)
    return files

def specifications(actions):
    from civ6_host.runtime.native.native_production_catalog import _uint
    from civ6_host.runtime.native.native_production_catalog import _type_name
    if type(actions) is not list or len(actions) > 4096:
        raise ValueError('Production action list bound')
    values = {}
    for action in actions:
        if type(action) is not dict:
            raise ValueError('Malformed production action input')
        if action.get('kind') not in KINDS:
            continue
        row = {key: action[key] for key in ('city_id', 'category', 'index', 'hash', 'item_type')}
        _uint(row['city_id'], 'city')
        _uint(row['index'], 'index', 2147483647)
        _uint(row['hash'], 'hash')
        _type_name(row['category'], row['item_type'])
        key = tuple((row[k] for k in ('city_id', 'category', 'index', 'hash', 'item_type')))
        values[key] = row
    return [values[key] for key in sorted(values)]

def source(player_id, turn, actions):
    from civ6_host.runtime.native.native_production_catalog import _uint
    pid = _uint(player_id, 'player', 63)
    turn = _uint(turn, 'turn', 2147483647)
    rows = specifications(actions)
    specs = ','.join(('{city_id=%d,category="%s",index=%d,hash=%d,item_type="%s"}' % tuple((row[k] for k in ('city_id', 'category', 'index', 'hash', 'item_type'))) for row in rows))
    return ('local pid=%d;local expectedTurn=%d;local specs={%s}\n' % (pid, turn, specs)).encode('ascii') + b'\nlocal function integer(v)\n assert(type(v)==\'number\' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\'production value is not signed32\')\n return v\nend\nlocal function n(v)return string.format(\'%.0f\',v)end\nlocal function nullable(v)return v==nil and \'null\' or n(v)end\nlocal function bits(v)integer(v);return v<0 and v+4294967296 or v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\'production info perspective differs\')\n assert(Game.GetCurrentGameTurn()==expectedTurn,\'production info crossed a turn\')\nend\nready()\nlocal player=assert(Players[pid]);local cities={};local count=0\nfor _,city in player:GetCities():Members()do\n local id=city:GetID();assert(city:GetOwner()==pid and not cities[id],\'production info foreign/duplicate city\')\n cities[id]=city;count=count+1;assert(count<=4096,\'production city bound\')\nend\nlocal tables={unit=GameInfo.Units,building=GameInfo.Buildings,district=GameInfo.Districts,project=GameInfo.Projects}\nlocal names={unit=\'UnitType\',building=\'BuildingType\',district=\'DistrictType\',project=\'ProjectType\'}\nlocal getters={unit=\'Unit\',building=\'Building\',district=\'District\',project=\'Project\'}\nlocal out={}\nfor _,spec in ipairs(specs)do\n local city=assert(cities[spec.city_id],\'production info own city missing\')\n local queue=assert(city:GetBuildQueue())\n local item=assert(tables[spec.category][spec.index],\'production info item missing\')\n assert(item.Index==spec.index and bits(item.Hash)==spec.hash and item[names[spec.category]]==spec.item_type,\n        \'production info GameInfo identity differs\')\n local getCost=\'Get\'..getters[spec.category]..\'Cost\';local getProgress=\'Get\'..getters[spec.category]..\'Progress\'\n assert(type(queue[getCost])==\'function\' and type(queue[getProgress])==\'function\' and type(queue.GetTurnsLeft)==\'function\',\n        \'production info native getter absent\')\n local cost=integer(queue[getCost](queue,spec.index));local progress=integer(queue[getProgress](queue,spec.index))\n local turnKey=(spec.category==\'unit\' or spec.category==\'building\') and item.Hash or item[names[spec.category]]\n local turns=integer(queue:GetTurnsLeft(turnKey))\n local formation=nil;local base=nil;local baseVisible=false\n local publicCost=cost~=0 and cost or nil\n local publicProgress=(cost~=0 and progress>0) and progress or nil\n local costKind=publicCost~=nil and \'"production"\' or \'null\'\n if spec.category==\'unit\' then\n  assert(MilitaryFormationTypes,\'production formation enum absent\')\n  -- Preserve the spelling used by the shipped ProductionPanel, including nil.\n  formation=MilitaryFormationTypes.STANDARD_MILITARY_FORMATION\n  if formation~=nil then\n   integer(formation)\n   assert(formation~=MilitaryFormationTypes.CORPS_MILITARY_FORMATION and\n          formation~=MilitaryFormationTypes.ARMY_MILITARY_FORMATION,\'standard formation aliases unsupported variant\')\n  end\n  base=integer(item.Cost or 0)\n  if formation==nil then\n   baseVisible=(base~=0 and item.MustPurchase==false and item.CanTrain and GameInfo.Yields[\'YIELD_PRODUCTION\']~=nil) and true or false\n   publicCost=baseVisible and base or nil;publicProgress=nil\n   costKind=baseVisible and \'"base"\' or \'null\'\n  end\n end\n local identity=\'"city_id":\'..n(spec.city_id)..\',"category":"\'..spec.category..\'","index":\'..n(spec.index)..\n  \',"hash":\'..n(spec.hash)..\',"item_type":"\'..spec.item_type..\'"\'\n local raw=\'"raw":{"cost":\'..n(cost)..\',"progress":\'..n(progress)..\',"turns_left":\'..n(turns)..\n  \',"formation_type":\'..nullable(formation)..\',"base_cost":\'..nullable(base)..\',"base_cost_visible":\'..tostring(baseVisible)..\'}\'\n local shown=\'"public":{"cost":\'..nullable(publicCost)..\',"progress":\'..nullable(publicProgress)..\n  \',"turns_left":\'..(turns==-1 and \'null\' or n(turns))..\',"never_completes":\'..tostring(turns==-1)..\',"cost_kind":\'..costKind..\'}\'\n out[#out+1]=\'{\'..identity..\',\'..raw..\',\'..shown..\'}\'\n assert(city:GetOwner()==pid,\'production info ownership changed\')\nend\nready()\nreturn \'[\'..table.concat(out,\',\')..\']\'\n'

def observe(prefix, observation, actions):
    verified_files()
    pid, turn = (observation['player_id'], observation['turn'])
    payload = prefix.runtime.evaluate_text(prefix.ui_child, source(pid, turn, actions), b'@official_production_info988', capacity=CAPACITY)
    if type(payload) is not bytes or len(payload) > CAPACITY:
        raise RuntimeError('Production information exceeds payload bound')
    result = dict(schema=SCHEMA, player_id=pid, turn=turn, source_sha256=PROOF_SHA256, ui_sha256=PANEL_SHA256, tooltip_sha256=TOOLTIP_SHA256, rows=json.loads(payload))
    candidates = [dict(action=action, candidate_id=hashlib.sha256(json.dumps(action, sort_keys=True, separators=(',', ':')).encode()).hexdigest()) for action in actions]
    validate(result, pid, turn, candidates=candidates, observation=observation)
    return result

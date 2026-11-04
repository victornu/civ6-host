"""Own-player yields projected through the shipped UI and native formatter."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib, json, math
from civ6_host.runtime.native import native_saved_treasury980 as treasury
from civ6_host.contracts.yield_display982 import SCHEMA
from civ6_host.contracts.yield_display982 import validate
_ASSETS = treasury._ASSETS
_SOURCE_HASHES = {'TopPanel.lua': '045a0d9e08ba63ee9a151810eb49f31bc11603cff7f159e07d3419c0f008cd7b', 'CitySupport.lua': '49ebe90ccff94545c86758ae1d50c24fa61914b28be1e3a35729286ca22475f1', 'Panels/CityPanel.lua': '466471300a6c404fcdcd812e6495e4a52448aca800537354f97228e377871c4a', 'Civ6Common.lua': '6e422dfed29d6e40507b14e234fc84c7647f450200df17dc2383e952a67a371f'}
_CAPACITY = 4 * 1024 * 1024
YIELDS = ('food', 'production', 'gold', 'science', 'culture', 'faith')

def verified_files():
    from civ6_host.runtime.native.native_locale_number982 import verified_files as number_files
    files = treasury.verified_files()
    files.update({_ASSETS / path: digest for path, digest in _SOURCE_HASHES.items()})
    files.update(number_files())
    for path, digest in files.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Pinned public yield source changed: ' + path.name)
    return files

def source(player_id):
    pid = treasury._player_id(player_id)
    return b'local pid=' + pid + b'\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\'yield perspective mismatch\')\nlocal player=assert(Players[pid],\'yield player unavailable\')\nlocal turn=Game.GetCurrentGameTurn()\nlocal function number(v)\n assert(type(v)==\'number\' and v==v and math.abs(v)<=1e12,\'invalid yield numeric value\')\n return string.format(\'%.17g\',v)\nend\nlocal function whole(v)\n assert(type(v)==\'number\' and v==math.floor(v),\'invalid integer yield identity\')\n return number(v)\nend\nlocal function row(fields)return \'{\'..table.concat(fields,\',\')..\'}\'end\nlocal function values(raw)\n local fields={}\n for _,key in ipairs({\'food\',\'production\',\'gold\',\'science\',\'culture\',\'faith\'})do\n  fields[#fields+1]=\'"\'..key..\'":\'..number(raw[key])\n end\n return row(fields)\nend\nlocal cities={};local seen={}\nfor _,city in player:GetCities():Members()do\n assert(city:GetOwner()==pid,\'foreign city in own yield roster\')\n local id=city:GetID();assert(not seen[id],\'duplicate yield city\');seen[id]=true\n local raw={};local shown={}\n for _,entry in ipairs({{\'food\',YieldTypes.FOOD},{\'production\',YieldTypes.PRODUCTION},\n     {\'gold\',YieldTypes.GOLD},{\'science\',YieldTypes.SCIENCE},{\'culture\',YieldTypes.CULTURE},{\'faith\',YieldTypes.FAITH}})do\n  local v=city:GetYield(entry[2]);number(v);raw[entry[1]]=v\n  -- This is the shipped CitySupport.UpdateYieldData presentation projection.\n  shown[entry[1]]=math.floor(v*10)/10\n end\n cities[#cities+1]={id=id,json=row({\'"city_id":\'..whole(id),\'"raw":\'..values(raw),\'"shown":\'..values(shown)})}\n assert(#cities<=4096,\'yield city bound\')\nend\ntable.sort(cities,function(a,b)return a.id<b.id end)\nlocal rows={};for _,city in ipairs(cities)do rows[#rows+1]=city.json end\nlocal science=player:GetTechs():GetScienceYield()\nlocal culture=player:GetCulture():GetCultureYield()\nlocal faith=player:GetReligion():GetFaithBalance()\nlocal faithYield=player:GetReligion():GetFaithYield()\nassert(Game.GetCurrentGameTurn()==turn and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\n       \'yield observation boundary changed\')\nreturn row({\'"player_id":\'..whole(pid),\'"turn":\'..whole(turn),\n \'"raw":\'..row({\'"science":\'..number(science),\'"culture":\'..number(culture),\n                \'"faith":\'..number(faith),\'"faith_yield":\'..number(faithYield)}),\n \'"cities":[\'..table.concat(rows,\',\')..\']\'})\n'

def project(raw, library, *, number_formatter=None, lookup=None):
    """Use the native formatter; injected callables are only for unit witnesses."""
    from civ6_host.runtime.native.native_locale_number982 import format_number
    from civ6_host.runtime.native.native_locale_arguments import native_lookup
    number_formatter = number_formatter or format_number
    lookup = lookup or native_lookup
    if type(raw) is not dict or set(raw) != {'player_id', 'turn', 'raw', 'cities'}:
        raise ValueError('Invalid raw yield projection fields')
    rates = {}
    for key in ('science', 'culture', 'faith_yield'):
        value = raw['raw'][key]
        rates[key] = number_formatter(library, value) if value == 0 else lookup(library, b'{1: number +#,###.#;-#,###.#}', (value,)).decode('utf-8', 'strict')
    rates['faith'] = number_formatter(library, raw['raw']['faith'], '#,###.#')
    cities = []
    for city in raw['cities']:
        if type(city) is not dict or set(city) != {'city_id', 'raw', 'shown'}:
            raise ValueError('Invalid raw city projection fields')
        if set(city['raw']) != set(YIELDS) or set(city['shown']) != set(YIELDS):
            raise ValueError('Invalid raw city projection yields')
        displays = {}
        for key in YIELDS:
            value = city['shown'][key]
            if value != math.floor(city['raw'][key] * 10) / 10:
                raise ValueError('Native city display projection differs from source')
            displays[key] = '0' if value == 0 else number_formatter(library, value, '+#,###.#;-#,###.#')
        cities.append(dict(city_id=city['city_id'], raw=city['raw'], public_display=displays))
    result = dict(schema=SCHEMA, player_id=raw['player_id'], turn=raw['turn'], raw=raw['raw'], public_display=rates, cities=cities)
    return validate(result, raw['player_id'], raw['turn'])

def observe(prefix, observation):
    from civ6_host.runtime.native.native_locale_arguments import attach
    verified_files()
    attach(prefix)
    if not getattr(prefix, 'yield_formatter982_verified', False):
        from civ6_host.runtime.native.native_locale_number982 import format_number
        from civ6_host.runtime.native.native_locale_arguments import native_lookup
        cases = []
        library = prefix.runtime.service_owner.localization_library
        for pattern in (None, '#,###.#', '+#,###.#;-#,###.#'):
            for value in (-1.25, -0.04, 0, 0.04, 1.24, 1.25, 1234.56):
                actual = format_number(library, value, pattern)
                key = b'{1 : number}' if pattern is None else ('{1: number ' + pattern + '}').encode('ascii')
                lookup = native_lookup(library, key, (value,)).decode('utf-8', 'strict')
                if actual != lookup:
                    raise RuntimeError('Native number constructor and Lookup paths differ')
                cases.append(dict(value=value, pattern=pattern, text=actual))
        prefix.runtime.emit('native_yield_formatter982_verified', cases=cases, oracle='Official String constructor versus official Lookup; both use native formatter, no Python rounding.', official_executable_executed=False)
        prefix.yield_formatter982_verified = True
    pid = observation['player_id']
    turn = observation['turn']
    data = prefix.runtime.evaluate_text(prefix.ui_child, source(pid), b'@explicit_yield_display982', capacity=_CAPACITY)
    if type(data) is not bytes or len(data) >= _CAPACITY:
        raise ValueError('Invalid raw yield payload')
    raw = json.loads(data.decode('ascii'), object_pairs_hook=treasury._unique_object, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite yield constant')))
    result = project(raw, prefix.runtime.service_owner.localization_library)
    return validate(result, pid, turn, observation)

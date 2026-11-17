"""Own-city loyalty using the same inputs and rounding as CityPanelCulture."""

from pathlib import Path

from civ6_host.contracts import city_loyalty as contract

from . import city_growth, expansion_city_growth
from .a0_family_source import verify_pinned_files
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('evidence/host-expansion-city-loyalty-ui-source.json',
          '2fa246a6d99741e8feaf17056a21e2cf0e1279b5d302ba06a1afdd141b112855')
CAPACITY = 4 * 1024 * 1024


def _profile(reference, image):
    expansion_city_growth._profile(reference, image)
    proof = _source(SOURCE)
    origin = proof['growth_profile_source']
    if (proof['schema'] != 'civ6-host.expansion-city-loyalty-ui-source.v1'
            or (origin['path'], origin['sha256']) != expansion_city_growth.SOURCE
            or proof['bbg_panel_replaced'] is not False or proof['native_execution'] is not False):
        raise ValueError('Expansion loyalty UI source differs')
    return proof['engines'][image.id]


def source_dependencies(reference, image):
    selected = _profile(reference, image)
    pins = expansion_city_growth.source_dependencies(reference, image)
    root = resource_root()
    for name, digest in (SOURCE, *((row['path'], row['sha256']) for row in selected['files'])):
        path = str(resolve_path(root / name).resolve(strict=True))
        if pins.setdefault(path, digest) != digest:
            raise ValueError('Conflicting expansion city loyalty source pin')
    verify_pinned_files(pins)
    return pins


def bind(saved):
    lifetime = expansion_city_growth._owner(saved)
    core = lifetime[0]
    selected = _profile(lifetime[-1], getattr(core, '_civ6_host_execution_image', None))
    expansion_city_growth.verify_bindings(selected, core._handle, saved.backend.runtime.read)
    saved._expansion_city_loyalty = lifetime


def build_source(player_id, turn):
    if type(player_id) is not int or not 0 <= player_id < 64 or type(turn) is not int or not 0 <= turn < 2**31:
        raise ValueError('Invalid city loyalty viewpoint')
    panel = city_growth.display_source()
    start = panel.index('local function Round(')
    end = panel.index('\nend', start) + len('\nend')
    return (f'local pid,turn={player_id},{turn}\n{panel[start:end]}\n'
            f'local maxCities,maxSources,maxText={contract.MAX_CITIES},{contract.MAX_SOURCES},{contract.MAX_TEXT_BYTES}\n'
            ).encode('ascii') + _READ


_READ = br'''
local function context()
    assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
        'foreign or stale city loyalty observation')
end
local function number(value)
    assert(type(value)=='number' and math.abs(value)<=1e9,'invalid native loyalty fraction')
    return string.format('%.17g',value)
end
local function int(value,low,high)
    assert(type(value)=='number' and value>=low and value<=high and value==math.floor(value),
        'invalid native loyalty integer')
    return string.format('%.0f',value)
end
local function text(value)
    assert(type(value)=='string' and #value>0 and #value<=maxText and not string.find(value,'\0',1,true),
        'invalid native loyalty text')
    return (string.gsub(value,'.',function(c) return string.format('%02x',string.byte(c)) end))
end
context()
local player=assert(Players[pid])
local out={'city-loyalty-v1|'..pid..'|'..turn}
local cities,seen={},{}
for _,city in player:GetCities():Members() do
    local id=city:GetID()
    int(id,0,4294967295)
    assert(not seen[id] and city:GetOwner()==pid,'loyalty city owned by another player')
    seen[id]=true
    cities[#cities+1]=city
    assert(#cities<=maxCities,'loyalty city limit')
end
table.sort(cities,function(a,b) return a:GetID()<b:GetID() end)
local min,max=-2147483648,2147483647
local outcomes=IdentityConversionOutcome
assert(type(outcomes.GAINING_LOYALTY)=='number' and type(outcomes.LOSING_LOYALTY)=='number'
    and outcomes.GAINING_LOYALTY~=outcomes.LOSING_LOYALTY,'loyalty conversion enum unavailable')
for _,city in ipairs(cities) do
    local id=int(city:GetID(),0,4294967295)
    local identity=assert(city:GetCulturalIdentity())
    local level=identity:GetLoyaltyLevel()
    local label=assert(GameInfo.LoyaltyLevels[level]).Name
    local outcome=identity:GetConversionOutcome()
    local turns=identity:GetTurnsToConversion()
    int(outcome,min,max)
    local countdown=int(turns,min,max)
    local trend,displayed='stable','-'
    if outcome==outcomes.GAINING_LOYALTY then
        trend='gaining'
        if turns>0 then displayed=countdown end
    elseif outcome==outcomes.LOSING_LOYALTY then
        trend,displayed='losing',countdown
    end
    local owner=identity:GetPotentialTransferPlayer()
    out[#out+1]=table.concat({'C',id,number(Round(identity:GetLoyalty(),1)),number(identity:GetMaxLoyalty()),
        number(Round(identity:GetLoyaltyPerTurn(),1)),int(level,0,max),text(Locale.Lookup(label)),
        text(Locale.Lookup(identity:GetLoyaltyPerTurnStatus())),trend,displayed,int(owner,-1,63)},'|')
    local breakdown=identity:GetIdentitySourcesDetailedBreakdown()
    assert(type(breakdown)=='table' and #breakdown<=maxSources,'loyalty pressure limit')
    for _,source in ipairs(breakdown) do
        local name,value=next(source)
        assert(type(value)=='number' and math.abs(value)<=1e9,'invalid native pressure')
        if value~=0 then
            out[#out+1]=table.concat({'S',id,text(name),number(Round(value,1)),value<0 and '1' or '0'},'|')
        end
    end
end
context()
return table.concat(out,'\n')
'''


def parse(raw, player_id, turn, observation):
    if type(raw) is not bytes or len(raw) > CAPACITY:
        raise ValueError('Unbounded city loyalty frame')
    header, *lines = raw.decode('ascii').split('\n')
    if header != f'city-loyalty-v1|{player_id}|{turn}':
        raise ValueError('Foreign city loyalty frame')

    def text(token):
        decoded = bytes.fromhex(token)
        if len(decoded) > contract.MAX_TEXT_BYTES or decoded.hex() != token:
            raise ValueError('Invalid city loyalty text encoding')
        return decoded.decode('utf-8')

    rows = []
    for line in lines:
        cells = line.split('|')
        if cells[0] == 'C' and len(cells) == 11 and len(rows) < contract.MAX_CITIES:
            _, city, current, maximum, rate, level, label, status, trend, countdown, owner = cells
            rows.append(dict(city_id=int(city), current=float(current), maximum=float(maximum), per_turn=float(rate),
                level=int(level), level_name=text(label), per_turn_status=text(status), trend=trend,
                conversion_turns=None if countdown == '-' else int(countdown),
                potential_new_owner=None if owner == '-1' else int(owner), sources=[]))
        elif (cells[0] == 'S' and len(cells) == 5 and rows and int(cells[1]) == rows[-1]['city_id']
                and len(rows[-1]['sources']) < contract.MAX_SOURCES and cells[4] in ('0', '1')):
            rows[-1]['sources'].append(dict(name=text(cells[2]), change=float(cells[3]), negative=cells[4] == '1'))
        else:
            raise ValueError('Invalid city loyalty frame row')
    return contract.validate(dict(schema=contract.SCHEMA, player_id=player_id, turn=turn, cities=rows),
                             player_id, turn, observation=observation)


def read(saved, observation, *, borrowed=False):
    if borrowed:
        from .xp1_session_view import _borrowed_xp2_reference
        _borrowed_xp2_reference(saved, observation['player_id'])
    else:
        saved._check_query()
    if expansion_city_growth._owner(saved) != saved._expansion_city_loyalty:
        raise ValueError('City loyalty Lua lifetime changed')
    player_id, turn = observation['player_id'], observation['turn']
    prefix = saved.prefix
    raw = prefix.runtime.evaluate_text(prefix.ui_child, build_source(player_id, turn),
                                       b'@expansion_city_loyalty', capacity=CAPACITY + 1)
    return parse(raw, player_id, turn, observation)

"""Shared Great People popup reader with source-bound expansion owners."""

from hashlib import sha256
from pathlib import Path
import math
import re

from civ6_host.contracts.great_people import SCHEMA, SCHEMA_V2

from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .native.native_great_people_actions import _common_guards
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1trade/great-people-preparation/source-reader.json',
          'db1035a6688b3df58dc9b01b24f34c20b26603f457a4f03593b65acbd25359ac')
_MAX_RESPONSE = 2 * 1024**2
_MAX_TIMELINE = 4096
_MAX_CLASSES = 64
_INT_MAX = 0x7fffffff
_UI_COST_LIMIT = 1_000_000
_CURRENCIES = ('YIELD_GOLD', 'YIELD_FAITH')
_CALLBACKS = {
    'Game.GetGreatPeople': 0x5b6cb0, 'Player.GetGreatPeoplePoints': 0x5c55d0,
    'GreatPeople.GetTimeline': 0x5b9a00, 'GreatPeople.GetPastTimeline': 0x5b9820,
    'GreatPeople.CanRecruitPerson': 0x5b9580, 'GreatPeople.CanRejectPerson': 0x5b9600,
    'GreatPeople.GetRejectCost': 0x5b9980, 'GreatPeople.CanPatronizePerson': 0x5b9570,
    'GreatPeople.GetPatronizeCost': 0x5b98f0, 'GreatPeople.CountPeopleReceivedByPlayer': 0x5b9680,
    'GreatPeoplePoints.GetPointsTotal': 0x5cc8d0, 'GreatPeoplePoints.GetPointsPerTurn': 0x5cc8c0,
    'GreatPeoplePointsExtension.IsNoPatronageWith': 0x62c880,
    'Player.GetDiplomacy': 0x5c5340, 'PlayerDiplomacy.HasMet': 0x5cbc30,
}


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def verify_source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-great-people-reader.static.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or (proof['capture']['path'], proof['capture']['sha256']) != REFERENCE
            or proof['native_execution'] is not False
            or proof['native_actions_admitted'] is not False
            or {k: row['callback_rva'] for k, row in proof['bindings'].items()} != _CALLBACKS
            or set(proof['timeline_literals']) != {'Individual', 'Class', 'Era', 'Cost', 'Claimant', 'TurnGranted'}
            or proof['contracts']['currencies'] != {'gold': 2, 'faith': 5}
            or proof['contracts']['current_timeline_bound'] != _MAX_TIMELINE
            or proof['contracts']['class_bound'] != _MAX_CLASSES):
        raise ValueError('Rise and Fall Great People query source differs')
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Great People query requires the installed Rise and Fall execution image')
    proof = verify_source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof['parent'], proof['earlier_source'],
            proof['image'], proof['capture'], proof['observed_rules_db'], *proof['ui_sources'].values()]
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()), row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall Great People query source pins')
    verify_pinned_files(pins)
    return pins


def _bind(saved):
    saved._check_query()
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    if (getattr(saved, 'xp1_great_people', False) is not True
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(backend.captured_bundle.reference, getattr(core, '_civ6_host_execution_image', None))):
        raise ValueError('Great People query requires the exact Rise and Fall saved owner')
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Great People query requires drained queues')
    lifetime = (core, prefix)
    if getattr(saved, '_xp1_great_people_query_lifetime', None) == lifetime:
        return
    proof = verify_source()
    base, read = core._handle, backend.runtime.read
    for span in proof['core_bodies']:
        raw = bytes.fromhex(span['raw_hex'])
        if (not 0 < len(raw) <= 4096 or len(raw) != span['bytes']
                or sha256(raw).hexdigest() != span['sha256'] or read(base + span['rva'], len(raw)) != raw):
            raise ValueError('Live Rise and Fall Great People query body differs: ' + span['name'])
    for row in proof['bindings'].values():
        raw = bytes.fromhex(row['bytes_hex'])
        literal = row['name'].encode('ascii') + b'\0'
        if (sha256(raw).hexdigest() != row['registration_sha256']
                or read(base + row['registration_rva'], len(raw)) != raw
                or read(base + row['name_rva'], len(literal)) != literal):
            raise ValueError('Live Rise and Fall Great People registration differs: ' + row['name'])
    for name, row in proof['timeline_literals'].items():
        literal = name.encode('ascii') + b'\0'
        if read(base + row['rva'], len(literal)) != literal:
            raise ValueError('Live Rise and Fall Great People timeline field differs: ' + name)
    saved._xp1_great_people_query_lifetime = lifetime


_QUERY = br'''
local function flag(value)
 assert(type(value)=='boolean','invalid Great People flag')
 return value and '1' or '0'
end
local function num(value)
 assert(type(value)=='number' and value==value and value>=-2147483648 and value<=2147483647,
        'invalid Great People numeric field')
 return string.format('%.17g',value)
end
local function index(value,maximum)
 assert(type(value)=='number' and value%1==0 and value>=0 and value<=maximum,
        'invalid Great People index')
 return string.format('%.0f',value)
end
local function optionalIndex(value,maximum)
 return value==nil and '-' or index(value,maximum)
end
local function optionalPrice(value)
 if value==nil then return '-' end
 assert(type(value)=='number' and value%1==0,'invalid Great People price')
 return num(value)
end
local function key(value,prefix)
 assert(type(value)=='string' and #value<=120 and value:match('^'..prefix..'[A-Z0-9_]+$'),
        'invalid Great People type key')
 return value
end
local caps=assert(GameInfo.GameCapabilities,'missing GameCapabilities')
local function enabled(name)
 return caps['CAPABILITY_GREAT_PEOPLE_'..name]~=nil
end
local recruit,reject,gold,faith=enabled('CAN_RECRUIT'),enabled('CAN_REJECT'),
                               enabled('RECRUIT_WITH_GOLD'),enabled('RECRUIT_WITH_FAITH')
local points=assert(player:GetGreatPeoplePoints(),'missing own Great People points')
local diplomacy=assert(player:GetDiplomacy(),'missing own Great People diplomacy')
local goldIndex,faithIndex=GameInfo.Yields.YIELD_GOLD.Index,GameInfo.Yields.YIELD_FAITH.Index
assert(goldIndex==2 and faithIndex==5 and YieldTypes.GOLD==goldIndex and YieldTypes.FAITH==faithIndex,
       'Great People currency selectors differ from the official popup')
local header={'great-people-v1',index(pid,63),index(expectedTurn,2147483647),
              flag(recruit),flag(reject),flag(gold),flag(faith),
              flag(points:IsNoPatronageWith(goldIndex)),flag(points:IsNoPatronageWith(faithIndex))}
if gpReadOnly~=nil then header[#header+1]=flag(gpReadOnly) end
local out={table.concat(header,'|')}
local seenClass,classCount={},0
for class in GameInfo.GreatPersonClasses() do
 local id=class.Index
 local idToken=index(id,2147483647)
 classCount=classCount+1
 assert(classCount<=64 and not seenClass[id],'duplicate or excessive Great People classes')
 seenClass[id]=true
 out[#out+1]=table.concat({'P',idToken,key(class.GreatPersonClassType,'GREAT_PERSON_CLASS_'),
                           optionalIndex(class.MaxPlayerInstances,2147483647),
                           index(greatPeople:CountPeopleReceivedByPlayer(id,pid),2147483647),
                           num(points:GetPointsTotal(id)),num(points:GetPointsPerTurn(id))},'|')
end
local timeline=greatPeople:GetTimeline()
assert(type(timeline)=='table','missing current Great People timeline')
local seen,rows={},0
for _,entry in ipairs(timeline) do
 rows=rows+1
 assert(rows<=4096 and type(entry)=='table','invalid or excessive Great People timeline')
 local classID=entry.Class
 assert(classID==nil or seenClass[classID],'unknown Great People timeline class')
 local classToken=optionalIndex(classID,2147483647)
 local era=optionalIndex(entry.Era,2147483647)
 local claimant=entry.Claimant
 local claimantToken=optionalIndex(claimant,63)
 if claimant~=nil and claimant~=pid and flag(diplomacy:HasMet(claimant))=='0' then
  claimantToken='hidden'
 end
 local individual=entry.Individual
 if individual==nil then
  out[#out+1]=table.concat({'T',classToken,era,claimantToken},'|')
 else
  local i=index(individual,2147483647)
  local definition=GameInfo.GreatPersonIndividuals[individual]
  assert(definition and definition.Index==individual and not seen[individual],
         'missing or duplicate Great Person individual')
  assert(classID==nil or GameInfo.GreatPersonClasses[classID].GreatPersonClassType==definition.GreatPersonClassType,
         'Great Person individual class differs')
  seen[individual]=true
  local canReject=greatPeople:CanRejectPerson(pid,individual)
  local rejectCost=nil
  if canReject then rejectCost=greatPeople:GetRejectCost(pid,individual) end
  out[#out+1]=table.concat({'I',i,key(definition.GreatPersonIndividualType,'GREAT_PERSON_INDIVIDUAL_'),
    classToken,era,claimantToken,optionalIndex(entry.Cost,2147483647),
    flag(greatPeople:CanRecruitPerson(pid,individual)),flag(canReject),optionalPrice(rejectCost),
    flag(greatPeople:CanPatronizePerson(pid,individual,YieldTypes.GOLD)),
    optionalPrice(greatPeople:GetPatronizeCost(pid,individual,YieldTypes.GOLD)),
    flag(greatPeople:CanPatronizePerson(pid,individual,YieldTypes.FAITH)),
    optionalPrice(greatPeople:GetPatronizeCost(pid,individual,YieldTypes.FAITH))},'|')
 end
end
local actual=0
for k,_ in pairs(timeline) do
 assert(type(k)=='number' and k%1==0 and k>=1 and k<=rows,'non-dense Great People timeline')
 actual=actual+1
end
assert(actual==rows,'changed Great People timeline')
assertContext()
if readOnlyCheck then assert(gpReadOnly==readOnlyCheck(),'Great People permissions changed') end
return table.concat(out,'\n')
'''

_XP2_UI_GUARDS = br'''
local player=assert(Players[pid],'missing Great People player')
local function assertContext()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
        Game.GetCurrentGameTurn()==expectedTurn,'Great People perspective or turn changed')
 assert(player:IsAlive()==true and player:IsTurnActive()==true and
        player:IsTurnActiveComplete()==true,'Great People player is not ready')
end
assertContext()
local greatPeople=assert(Game.GetGreatPeople(),'native Great People API unavailable')
assert(GameInfo.GreatPersonClasses.GREAT_PERSON_CLASS_AUSTRIAN_DIPLOMAT==nil,
       'Great People visibility differs from the admitted BBG capture')
local function readOnlyCheck()
 local congress=assert(Game.GetWorldCongress(),'missing Great People Congress state')
 local inSession=congress:IsInSession()
 local strategic=Game.IsAllowStrategicCommands(pid)
 assert(type(inSession)=='boolean' and type(strategic)=='boolean','invalid Great People permissions')
 return inSession or not strategic
end
local gpReadOnly=readOnlyCheck()
'''


def _identity(player_id, turn):
    if (type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or not 0 <= turn <= _INT_MAX):
        raise ValueError('Foreign Great People query identity')
    return player_id, turn


def query_source(player_id, turn, *, xp2=False):
    _identity(player_id, turn)
    if xp2:
        identity = f'local pid,expectedTurn={player_id},{turn}\n'.encode('ascii')
        return identity + _XP2_UI_GUARDS + _QUERY
    return _common_guards(player_id, turn) + b'local gpReadOnly,readOnlyCheck\n' + _QUERY


def _number(token, *, minimum=0, maximum=_INT_MAX, optional=False):
    if optional and token == '-':
        return None
    if not re.fullmatch(r'0|-?[1-9][0-9]{0,9}', token):
        raise ValueError('Invalid Great People wire integer')
    result = int(token)
    if not minimum <= result <= maximum:
        raise ValueError('Out of range Great People wire integer')
    return result


def _fixed(token):
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,7})(?:\.[0-9]{1,8})?', token):
        raise ValueError('Invalid Great People points token')
    value = float(token)
    if not math.isfinite(value) or not -8388608 <= value < 8388608 or not (value * 256).is_integer():
        raise ValueError('Invalid fixed-point Great People value')
    return value


def _bool(token):
    return bool(_number(token, maximum=1))


def _key(token, prefix):
    if len(token) > 120 or not re.fullmatch(prefix + r'[A-Z0-9_]+', token):
        raise ValueError('Invalid Great People wire type key')
    return token


def _claimant(token):
    return dict(claimed=token != '-', claimant_player_id=None if token == 'hidden'
                else _number(token, maximum=63, optional=True))


def _named_choice(values, capabilities, disabled, *, read_only=False):
    _, individual, item_type, class_id, era, claimant, recruit, can_recruit, can_reject, reject, *patrons = values
    recruit = _number(recruit, optional=True)
    reject = _number(reject, minimum=-(2**31), optional=True)
    can_recruit, can_reject = _bool(can_recruit), _bool(can_reject)
    currencies = {}
    for currency, native, price in zip(_CURRENCIES, patrons[::2], patrons[1::2], strict=True):
        price = _number(price, minimum=-(2**31), optional=True)
        native = _bool(native)
        visible = (capabilities[currency] and not can_recruit and not can_reject
                   and price is not None and price < _UI_COST_LIMIT)
        currencies[currency] = dict(cost=price, native_can_patronize=native, visible=visible,
                                    available=not read_only and visible and native and price >= 0,
                                    no_patronage=disabled[currency])
    return dict(individual_index=_number(individual),
                item_type=_key(item_type, 'GREAT_PERSON_INDIVIDUAL_'),
                class_index=_number(class_id, optional=True), era_index=_number(era, optional=True),
                **_claimant(claimant),
                recruitment=dict(cost=recruit, native_can_recruit=can_recruit,
                                 available=not read_only and capabilities['recruit'] and can_recruit and recruit is not None),
                rejection=dict(cost=reject, native_can_reject=can_reject,
                               available=not read_only and capabilities['reject'] and can_reject and reject is not None),
                patronage=currencies)


def parse(raw, player_id, turn, *, xp2=False):
    _identity(player_id, turn)
    if type(raw) is not bytes or not 0 < len(raw) < _MAX_RESPONSE:
        raise ValueError('Great People reply exceeded its wire bounds')
    header, *rows = raw.decode('ascii').split('\n')
    identity = f'great-people-v1|{player_id}|{turn}|'
    if not header.startswith(identity) or len(rows) > _MAX_CLASSES + _MAX_TIMELINE:
        raise ValueError('Foreign or excessive Great People reply')
    flags = header[len(identity):].split('|')
    if len(flags) != (7 if xp2 else 6):
        raise ValueError('Great People reply flags differ from the engine')
    read_only = _bool(flags.pop()) if xp2 else False
    recruit, reject, gold, faith, dis_gold, dis_faith = map(_bool, flags)
    capabilities = dict(recruit=recruit, reject=reject, YIELD_GOLD=gold, YIELD_FAITH=faith)
    disabled = dict(YIELD_GOLD=dis_gold, YIELD_FAITH=dis_faith)
    points, timeline, individuals = {}, [], set()
    for row in rows:
        fields = row.split('|')
        kind = fields[0]
        if kind == 'P' and len(fields) == 7 and not timeline:
            _, class_index, class_type, maximum, granted, total, per_turn = fields
            class_index = _number(class_index)
            if class_index in points or len(points) == _MAX_CLASSES:
                raise ValueError('Duplicate or excessive Great People point rows')
            points[class_index] = dict(class_index=class_index,
                class_type=_key(class_type, 'GREAT_PERSON_CLASS_'),
                max_instances=_number(maximum, optional=True), instances_earned=_number(granted),
                points_total=_fixed(total), points_per_turn=_fixed(per_turn))
            continue
        if kind == 'T' and len(fields) == 4:
            _, class_index, era_index, claimant = fields
            result = dict(individual_index=None, item_type=None, class_index=_number(class_index, optional=True),
                          era_index=_number(era_index, optional=True),
                          **_claimant(claimant),
                          recruitment=None, rejection=None, patronage=None)
        elif kind == 'I' and len(fields) == 14:
            result = _named_choice(fields, capabilities, disabled, read_only=read_only)
            person = result['individual_index']
            if person in individuals:
                raise ValueError('Duplicate Great People individual in reply')
            individuals.add(person)
        else:
            raise ValueError('Malformed Great People reply row')
        class_index = result['class_index']
        if len(timeline) == _MAX_TIMELINE or class_index is not None and class_index not in points:
            raise ValueError('Excessive Great People timeline or unknown class')
        timeline.append(result)
    if not points:
        raise ValueError('Great People reply omitted own point classes')
    value = dict(schema=SCHEMA_V2 if xp2 else SCHEMA, player_id=player_id, turn=turn, capabilities=capabilities,
                 no_patronage=disabled, own_points=[points[i] for i in sorted(points)], timeline=timeline)
    if xp2:
        value['read_only'] = read_only
    return value


def read(saved, observation, *, xp2=False, borrowed=False):
    if type(observation) is not dict:
        raise ValueError('Great People query requires the actor observation')
    player_id, turn = _identity(observation.get('player_id'), observation.get('turn'))
    if xp2:
        from .xp2_great_people_source import bind
        if borrowed:
            bind(saved, borrowed_player=player_id)
        else:
            bind(saved)
    else:
        if borrowed:
            raise ValueError('Borrowed Great People require Gathering Storm')
        _bind(saved)
    return _evaluate(saved.prefix, player_id, turn, xp2=xp2)


def _evaluate(prefix, player_id, turn, *, xp2=False):
    """Read through the UI child after the caller verified its current lifecycle."""
    script = b'@xp2_public_great_people' if xp2 else b'@xp1_public_great_people'
    raw = prefix.runtime.evaluate_text(prefix.ui_child, query_source(player_id, turn, xp2=xp2),
                                       script, capacity=_MAX_RESPONSE)
    return parse(raw, player_id, turn, xp2=xp2)

"""Proof-gated native Great Person recruitment catalog and readback.

The native timeline exposes `entry.Individual` as an ordinal GameInfo index,
and the shipped UI passes it unchanged as the RECRUIT_GREAT_PERSON parameter.
This module validates the index and preserves its exact signed-32 value. It
never submits the operation; the caller must use public CanStart/Request and
verify a past-timeline Claimant and grant-turn readback after delivery. A
current-timeline Claimant alone is only a reservation, not completed recruitment.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_great_people_actions.py')))).resolve().parents[1]
_ASSETS = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_ROUTE_PATH = _ROOT / 'evidence/native-player-operation-route.json'
_ROUTE_SHA256 = '6ba4b94fd024f320012303beca763601857afeff633b7008c394ac52bee0f1d2'
_ROUTE_IMAGES = {'exe': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}
_ENUM_PROOF_SHA256 = '691de04309b44f0ccb600fdc421360f2bb7a35a5ac68f263bf9fa6800d507edb'
_ENUM_PROOF = _ROOT / 'evidence/native-great-person-operation.json'
_TRANSITION_PROOF_SHA256 = '068ebb75afb31c4c62379f79dd59365b8a46d008f6027083db521af7f5897c87'
_TRANSITION_PROOF = _ROOT / 'evidence/native-great-people-recruitment-transition' / f'{_TRANSITION_PROOF_SHA256}.json'
_POPUP_SHA256 = '43f0816d7f8b3419ceb87e4021e8e507cd1e450e32583436d3b0ea8362e574c6'
_CAPABILITIES_SHA256 = '0e81de39aa32033e4b3ed0660e72f6ca63f3f3bec28ec35d3b61ef780f1ceb0c'
_RECRUIT_OPERATION = 3907540154
_INDIVIDUAL_PARAMETER = 945800002
_MAX_CHOICES = 4096
_MAX_RESPONSE = 131072
PINNED_EVIDENCE_SHA256 = 'ea16507f33b0326f8748e7d0138f227f7250e55494f0fbf85462add1b81400fd'
_PROOF = _ROOT / 'evidence/native-great-people-actions' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source() -> None:
    native = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    enums = load_pinned_json(_ENUM_PROOF, _ENUM_PROOF_SHA256)
    transition = load_pinned_json(_TRANSITION_PROOF, _TRANSITION_PROOF_SHA256)
    if native.get('schema') != 'civ6rl.native_great_people_actions.static.v1' or native.get('core_sha256') != _ROUTE_IMAGES['core'] or native.get('exe_sha256') != _ROUTE_IMAGES['exe']:
        raise RuntimeError('Great Person API proof identity changed')
    expected_bindings = {'Game.GetGreatPeople': '0x180522690', 'GameGreatPeople.GetTimeline': '0x1805253e0', 'GameGreatPeople.GetPastTimeline': '0x180525200', 'GameGreatPeople.CanRecruitPerson': '0x180524f60'}
    if any((native.get('bindings', {}).get(name, {}).get('callback_va') != target for name, target in expected_bindings.items())):
        raise RuntimeError('Great Person binding callbacks changed')
    contracts = native.get('contracts', {})
    timelines = contracts.get('timelines', {})
    individual = contracts.get('individual_identity', {})
    if timelines.get('shape') is None or timelines.get('native_entry_stride') != 64 or timelines.get('numeric_fields', {}).get('Individual', {}).get('native_offset') != '0x00' or (timelines.get('numeric_fields', {}).get('Claimant', {}).get('native_offset') != '0x10') or ('ordinal/index' not in individual.get('native_evidence', '')):
        raise RuntimeError('Great Person timeline representation changed')
    if enums.get('schema') != 'civ6rl.native_great_person_operation.v1' or enums.get('constants', {}).get('RECRUIT_GREAT_PERSON', {}).get('signed_int32') != -387427142 or enums.get('constants', {}).get('PARAM_GREAT_PERSON_INDIVIDUAL_TYPE', {}).get('signed_int32') != 945800002:
        raise RuntimeError('Great Person operation constants changed')
    if transition.get('schema') != 'civ6rl.native_great_people_recruitment_transition.static.v1' or transition.get('core_sha256') != _ROUTE_IMAGES['core'] or transition.get('exe_sha256') != _ROUTE_IMAGES['exe']:
        raise RuntimeError('Great Person recruitment transition proof identity changed')
    contracts = transition.get('contracts', {})
    reservation = contracts.get('reservation', '')
    eligibility = contracts.get('eligibility_with_reservation', '')
    grant = contracts.get('grant_and_past_transition', '')
    observer = contracts.get('conservative_effect_observer', '')
    if not all((isinstance(value, str) for value in (reservation, eligibility, grant, observer))) or 'writes playerID to record+10' not in reservation or 'equal-to-player' not in eligibility or ('TurnGranted=[Game+0xC0]' not in grant) or ('GetPastTimeline' not in observer) or ('unchanged expected game turn' not in observer):
        raise RuntimeError('Great Person reservation/grant contract changed')
    raw = _resolve_resource_path(_ROUTE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _ROUTE_SHA256:
        raise RuntimeError('Pinned player-operation route proof changed')
    route = json.loads(raw)
    if route.get('schema') != 'civ6rl.native_player_operation_route.v3' or route.get('images', {}).get('exe', {}).get('sha256') != _ROUTE_IMAGES['exe'] or route.get('images', {}).get('core', {}).get('sha256') != _ROUTE_IMAGES['core']:
        raise RuntimeError('Unexpected player-operation route image identity')
    popup = _ASSETS / 'Popups' / 'GreatPeoplePopup.lua'
    caps = _ASSETS / 'Scripts' / 'GameCapabilities.lua'
    if hashlib.sha256(_resolve_resource_path(popup).read_bytes()).hexdigest() != _POPUP_SHA256:
        raise RuntimeError('Installed Great People UI source changed')
    if hashlib.sha256(_resolve_resource_path(caps).read_bytes()).hexdigest() != _CAPABILITIES_SHA256:
        raise RuntimeError('Installed GameCapabilities source changed')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _pid(value: int) -> int:
    return _uint(value, 'player ID', 63)

def _turn(value: int) -> int:
    return _uint(value, 'game turn')

def _signed(value: int, label: str) -> int:
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError(f'Invalid signed32 {label}')
    return value

def _bits(value: int, label: str) -> int:
    return _signed(value, label) & 4294967295

def _parse_uint(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((c < 48 or c > 57 for c in token)) or (len(token) > 1 and token[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'{label} is out of range')
    return value

def _common_guards(pid: int, turn: int) -> bytes:
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(turn).encode() + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n 'Great Person perspective mismatch')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n 'Great Person observer mismatch')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n 'Great Person decision is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and\n Game.IsAllowStrategicCommands(pid)==true,'strategic commands are not allowed')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'Great Person player is not ready')\nlocal greatPeople=Game.GetGreatPeople()\nassert(greatPeople and type(greatPeople.GetTimeline)=='function' and\n type(greatPeople.GetPastTimeline)=='function' and\n type(greatPeople.CanRecruitPerson)=='function','native Great People API unavailable')\nlocal function assertContext()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n  Game.GetCurrentGameTurn()==expectedTurn,'Great Person decision context changed')\n assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands no longer allowed')\n assert(player:IsAlive()==true and player:IsTurnActive()==true and\n  player:IsTurnActiveComplete()==true,'Great Person player is no longer ready')\nend\nassertContext()\n"

def _capability_lua() -> bytes:
    return b"assert(GameInfo and GameInfo.GameCapabilities and\n GameInfo.GameCapabilities['CAPABILITY_GREAT_PEOPLE_CAN_RECRUIT']~=nil,\n 'Great Person recruitment capability is unavailable')\n"

def catalog_source(player_id: int, expected_turn: int) -> bytes:
    pid, turn = (_pid(player_id), _turn(expected_turn))
    verify_source()
    return _common_guards(pid, turn) + _capability_lua() + b"local operation=PlayerOperations and PlayerOperations.RECRUIT_GREAT_PERSON\nlocal key=PlayerOperations and PlayerOperations.PARAM_GREAT_PERSON_INDIVIDUAL_TYPE\nassert(type(operation)=='number' and operation==math.floor(operation) and\n operation>=-2147483648 and operation<=2147483647,'Recruit operation enum unavailable')\nassert(type(key)=='number' and key==math.floor(key) and\n key>=-2147483648 and key<=2147483647,'Great Person parameter enum unavailable')\nlocal operationBits=operation<0 and operation+4294967296 or operation\nlocal keyBits=key<0 and key+4294967296 or key\nlocal function signedBits(v,label)\n assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n  'invalid '..label)\n return v<0 and v+4294967296 or v\nend\nlocal current=greatPeople:GetTimeline()\nassert(type(current)=='table','native Great Person timeline unavailable')\nlocal choices,seen={},{}\nlocal scanned=0\nfor _,entry in ipairs(current) do\n scanned=scanned+1\n assert(scanned<=" + str(_MAX_CHOICES).encode() + b",'Great Person timeline exceeds bound')\n assert(type(entry)=='table','malformed Great Person timeline entry')\n if entry.Individual~=nil then\n  local individual=signedBits(entry.Individual,'timeline individual')\n  assert(individual<=2147483647,'negative Great Person individual index')\n  local individualInfo=GameInfo.GreatPersonIndividuals and\n                       GameInfo.GreatPersonIndividuals[individual]\n  assert(individualInfo and individualInfo.Index==individual,\n         'timeline individual index has no matching GameInfo row')\n  assert(not seen[individual],'duplicate Great Person individual in current timeline')\n  seen[individual]=true\n  local cost=nil\n  if entry.Cost~=nil then\n   cost=signedBits(entry.Cost,'recruit cost')\n   assert(cost>=0,'negative Great Person recruit cost')\n  end\n  local canRecruit=greatPeople:CanRecruitPerson(pid,entry.Individual)\n  assert(type(canRecruit)=='boolean','CanRecruitPerson returned non-Boolean')\n  if canRecruit and cost~=nil then choices[#choices+1]={individual=individual,cost=cost} end\n end\nend\ntable.sort(choices,function(a,b) return a.individual<b.individual end)\nlocal function dec(n) return string.format('%.0f',n) end\nlocal fields={'catalog',dec(pid),dec(expectedTurn),dec(operationBits),dec(keyBits),dec(#choices)}\nfor _,item in ipairs(choices) do\n fields[#fields+1]=dec(item.individual)..':'..dec(item.cost)\nend\nassertContext()\nif #choices==0 then return 'not_due,'..dec(pid)..','..dec(expectedTurn)..',no_recruitable_person' end\nreturn table.concat(fields,',')\n"

def parse_catalog(payload: bytes, player_id: int, expected_turn: int) -> dict:
    pid, turn = (_pid(player_id), _turn(expected_turn))
    if type(payload) is not bytes or len(payload) > _MAX_RESPONSE:
        raise ValueError('Invalid Great Person catalog response')
    fields = payload.split(b',')
    if fields and fields[0] == b'not_due':
        if len(fields) != 4 or fields[3] != b'no_recruitable_person':
            raise ValueError('Malformed Great Person not-due result')
        actual_pid = _parse_uint(fields[1], 'player ID', 63)
        actual_turn = _parse_uint(fields[2], 'game turn')
        if (actual_pid, actual_turn) != (pid, turn):
            raise ValueError('Great Person not-due result is stale or misattributed')
        return {'status': 'not_due', 'reason': 'no_recruitable_person', 'player_id': pid, 'current_game_turn': turn}
    if len(fields) < 6 or fields[0] != b'catalog':
        raise ValueError('Malformed Great Person catalog')
    actual_pid = _parse_uint(fields[1], 'player ID', 63)
    actual_turn = _parse_uint(fields[2], 'game turn')
    operation = _parse_uint(fields[3], 'operation')
    parameter_key = _parse_uint(fields[4], 'individual parameter key')
    count = _parse_uint(fields[5], 'choice count', _MAX_CHOICES)
    if (actual_pid, actual_turn) != (pid, turn):
        raise ValueError('Great Person catalog is stale or misattributed')
    if operation != _RECRUIT_OPERATION or parameter_key != _INDIVIDUAL_PARAMETER:
        raise ValueError('Great Person operation or parameter key is not source-pinned')
    if count == 0:
        raise ValueError('Empty Great Person catalogs must use the not-due result')
    if count != len(fields) - 6:
        raise ValueError('Great Person catalog count differs from its entries')
    choices, seen = ([], set())
    previous = -1
    for token in fields[6:]:
        pair = token.split(b':')
        if len(pair) != 2:
            raise ValueError('Malformed Great Person individual/cost pair')
        individual = _parse_uint(pair[0], 'individual index', 2147483647)
        cost = _parse_uint(pair[1], 'recruit cost', 2147483647)
        if individual in seen or individual <= previous:
            raise ValueError('Great Person choices are duplicated or unordered')
        seen.add(individual)
        previous = individual
        choices.append({'individual': individual, 'cost': cost})
    return {'status': 'catalog', 'player_id': pid, 'current_game_turn': turn, 'operation': operation, 'parameter_key': parameter_key, 'choices': tuple(choices)}

def choose(catalog: dict, selected_individual: int) -> dict:
    keys = {'status', 'player_id', 'current_game_turn', 'operation', 'parameter_key', 'choices'}
    if type(catalog) is not dict or set(catalog) != keys or catalog.get('status') != 'catalog':
        raise ValueError('Great Person catalog is absent or invalid')
    _pid(catalog['player_id'])
    _turn(catalog['current_game_turn'])
    operation = _uint(catalog['operation'], 'operation')
    parameter_key = _uint(catalog['parameter_key'], 'parameter key')
    if operation != _RECRUIT_OPERATION or parameter_key != _INDIVIDUAL_PARAMETER:
        raise ValueError('Great Person operation or parameter key is not source-pinned')
    choices = catalog['choices']
    if type(choices) is not tuple or len(choices) > _MAX_CHOICES:
        raise ValueError('Invalid Great Person choice list')
    seen, previous = (set(), -1)
    for item in choices:
        if type(item) is not dict or set(item) != {'individual', 'cost'}:
            raise ValueError('Malformed Great Person catalog item')
        _uint(item['individual'], 'individual index', 2147483647)
        _uint(item['cost'], 'recruit cost', 2147483647)
        if item['individual'] in seen or item['individual'] <= previous:
            raise ValueError('Ambiguous Great Person catalog')
        seen.add(item['individual'])
        previous = item['individual']
    individual = _uint(selected_individual, 'selected individual')
    matches = [item for item in choices if item['individual'] == individual]
    if len(matches) != 1:
        raise ValueError('Selected Great Person is absent or ambiguous')
    return {'player_id': catalog['player_id'], 'current_game_turn': catalog['current_game_turn'], 'selected_individual': individual, 'expected_cost': matches[0]['cost'], 'operation': operation, 'parameter_key': parameter_key, 'parameters': {parameter_key: individual}}

def _validate_choice(choice: dict) -> None:
    expected_keys = {'player_id', 'current_game_turn', 'selected_individual', 'expected_cost', 'operation', 'parameter_key', 'parameters'}
    if type(choice) is not dict or set(choice) != expected_keys:
        raise ValueError('Malformed Great Person selection')
    _pid(choice['player_id'])
    _turn(choice['current_game_turn'])
    _uint(choice['selected_individual'], 'selected individual', 2147483647)
    _uint(choice['expected_cost'], 'expected cost', 2147483647)
    _uint(choice['operation'], 'operation')
    _uint(choice['parameter_key'], 'parameter key')
    if choice['operation'] != _RECRUIT_OPERATION or choice['parameter_key'] != _INDIVIDUAL_PARAMETER:
        raise ValueError('Great Person operation or parameter key is not source-pinned')
    if choice['parameters'] != {choice['parameter_key']: choice['selected_individual']}:
        raise ValueError('Great Person request map differs from the selected identity')

def revalidate_choice_source(choice: dict) -> bytes:
    _validate_choice(choice)
    verify_source()
    pid, turn = (_pid(choice['player_id']), _turn(choice['current_game_turn']))
    fields = (pid, turn, choice['selected_individual'], choice['expected_cost'], choice['operation'], choice['parameter_key'])
    return b'local pid,expectedTurn,expectedIndividual,expectedCost,expectedOperation,expectedKey=' + b','.join((str(v).encode('ascii') for v in fields)) + b'\n' + _common_guards(pid, turn) + _capability_lua() + b"\nlocal op=PlayerOperations and PlayerOperations.RECRUIT_GREAT_PERSON\nlocal key=PlayerOperations and PlayerOperations.PARAM_GREAT_PERSON_INDIVIDUAL_TYPE\nassert(type(op)=='number' and type(key)=='number','Great Person operation enums unavailable')\nlocal function bits(v)\n assert(type(v)=='number' and v==math.floor(v) and\n        v>=-2147483648 and v<=2147483647,'invalid signed enum')\n return v<0 and v+4294967296 or v\nend\nassert(bits(op)==expectedOperation and bits(key)==expectedKey,'Great Person operation/key changed')\nlocal timeline=greatPeople:GetTimeline()\nassert(type(timeline)=='table','current timeline unavailable')\nlocal found=0; local scanned=0\nfor _,entry in ipairs(timeline) do\n scanned=scanned+1; assert(scanned<=" + str(_MAX_CHOICES).encode() + b",'current timeline exceeds bound')\n assert(type(entry)=='table','malformed timeline entry')\n        if entry.Individual~=nil and bits(entry.Individual,'individual')==expectedIndividual then\n  found=found+1\n  assert(entry.Cost==expectedCost,'selected Great Person cost changed')\n  local row=GameInfo.GreatPersonIndividuals and\n            GameInfo.GreatPersonIndividuals[expectedIndividual]\n  assert(row and row.Index==expectedIndividual,\n         'selected Great Person GameInfo identity changed')\n  local can=greatPeople:CanRecruitPerson(pid,entry.Individual)\n  assert(type(can)=='boolean' and can==true,'native Great Person recruitment is no longer legal')\n end\nend\nassert(found==1,'selected Great Person missing or duplicated')\nassertContext()\nlocal function dec(n) return string.format('%.0f',n) end\nreturn table.concat({'valid',dec(pid),dec(expectedTurn),dec(expectedIndividual),dec(expectedCost),\n dec(bits(op)),dec(bits(key))},',')\n"

def parse_revalidated_choice(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 256:
        raise ValueError('Invalid Great Person revalidation response')
    fields = payload.split(b',')
    if len(fields) != 7 or fields[0] != b'valid':
        raise ValueError('Malformed Great Person revalidation response')
    actual = tuple((_parse_uint(value, 'revalidated value') for value in fields[1:]))
    expected = tuple((choice[name] for name in ('player_id', 'current_game_turn', 'selected_individual', 'expected_cost', 'operation', 'parameter_key')))
    if actual != expected:
        raise ValueError('Revalidated Great Person differs from selected entry')
    return {'valid': True, 'choice': choice, 'operation': choice['operation'], 'parameters': dict(choice['parameters'])}

def effect_source(choice: dict) -> bytes:
    _validate_choice(choice)
    verify_source()
    pid, turn = (_pid(choice['player_id']), _turn(choice['current_game_turn']))
    individual = choice['selected_individual']
    return b'local pid,expectedTurn,expectedIndividual=' + b','.join((str(v).encode('ascii') for v in (pid, turn, individual))) + b'\n' + _common_guards(pid, turn) + b"\nlocal function checkedTimeline(value,label)\n assert(type(value)=='table',label..' timeline unavailable')\n local found=0; local selected=nil; local scanned=0\n for _,entry in ipairs(value) do\n  scanned=scanned+1; assert(scanned<=" + str(_MAX_CHOICES).encode() + b",label..' timeline exceeds bound')\n  assert(type(entry)=='table',label..' timeline entry malformed')\n    if entry.Individual~=nil then\n   assert(type(entry.Individual)=='number' and entry.Individual==math.floor(entry.Individual) and\n    entry.Individual>=-2147483648 and entry.Individual<=2147483647,'invalid timeline individual')\n   local bits=entry.Individual<0 and entry.Individual+4294967296 or entry.Individual\n    if bits==expectedIndividual then\n    found=found+1\n    local claimant=4294967295\n    if entry.Claimant~=nil then\n     assert(type(entry.Claimant)=='number' and entry.Claimant==math.floor(entry.Claimant) and\n      entry.Claimant>=-1 and entry.Claimant<=2147483647,'invalid readback claimant')\n     claimant=entry.Claimant==-1 and 4294967295 or entry.Claimant\n    end\n    local turnGranted=4294967295\n    if entry.TurnGranted~=nil then\n     assert(type(entry.TurnGranted)=='number' and entry.TurnGranted==math.floor(entry.TurnGranted) and\n      entry.TurnGranted>=0 and entry.TurnGranted<=2147483647,'invalid readback grant turn')\n     turnGranted=entry.TurnGranted\n    end\n    selected={claimant=claimant,turn_granted=turnGranted}\n   end\n  end\n end\n assert(found<=1,label..' timeline duplicates selected individual')\n return found,selected\nend\nlocal nCurrent,current=checkedTimeline(greatPeople:GetTimeline(),'current')\nlocal nPast,past=checkedTimeline(greatPeople:GetPastTimeline(),'past')\nassert(nCurrent+nPast>0,'selected Great Person absent from both native timelines')\nif nCurrent==1 and nPast==1 then\n assert(current.claimant==past.claimant,\n        'current/past Great Person readbacks conflict')\nend\nlocal item=past or current\nassert(item~=nil,'selected Great Person is absent from both native timelines')\nlocal state='pending'\nif past~=nil and past.claimant==pid then\n assert(past.turn_granted==expectedTurn,'past Great Person grant turn differs from selected turn')\n state='verified'\nelseif item.claimant~=4294967295 and item.claimant~=pid then state='conflict' end\nassertContext()\nlocal function dec(n) return string.format('%.0f',n) end\nreturn table.concat({state,dec(pid),dec(expectedTurn),dec(expectedIndividual),\n dec(item.claimant),dec(nCurrent),dec(nPast),dec(past and past.turn_granted or 4294967295)},',')\n"

def parse_effect(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 256:
        raise ValueError('Invalid Great Person effect response')
    fields = payload.split(b',')
    if len(fields) != 8 or fields[0] not in (b'pending', b'verified', b'conflict'):
        raise ValueError('Malformed Great Person effect response')
    actual = tuple((_parse_uint(value, 'effect field') for value in fields[1:]))
    expected = (choice['player_id'], choice['current_game_turn'], choice['selected_individual'])
    if actual[:3] != expected:
        raise ValueError('Great Person effect is stale or misattributed')
    claimant = actual[3]
    current_present, past_present, grant_turn = actual[4:7]
    if current_present not in (0, 1) or past_present not in (0, 1):
        raise ValueError('Great Person timeline presence flags must be Boolean bits')
    if grant_turn != 4294967295 and grant_turn > 2147483647:
        raise ValueError('Great Person grant turn exceeds signed32 range')
    if not past_present and grant_turn != 4294967295:
        raise ValueError('A grant turn cannot exist without a past timeline row')
    if not current_present and (not past_present):
        raise ValueError('Selected Great Person is absent from both timelines')
    if fields[0] == b'verified':
        if not past_present or claimant != choice['player_id'] or grant_turn != choice['current_game_turn']:
            raise ValueError('Great Person verification lacks matching past Claimant/grant turn')
    elif fields[0] == b'pending':
        if past_present and claimant == choice['player_id'] or claimant not in (4294967295, choice['player_id']):
            raise ValueError('Great Person pending state contradicts readback fields')
    elif claimant in (4294967295, choice['player_id']):
        raise ValueError('Great Person conflict lacks a foreign claimant')
    if past_present and claimant == choice['player_id'] and (grant_turn != choice['current_game_turn']):
        raise ValueError('Past row claimed by this player has a missing or stale grant turn')
    if fields[0] == b'pending' and past_present and (grant_turn != 4294967295):
        raise ValueError('Past row with a grant turn cannot remain pending')
    return {'status': fields[0].decode('ascii'), 'confirmed': fields[0] == b'verified', 'player_id': actual[0], 'current_game_turn': actual[1], 'selected_individual': actual[2], 'expected_cost': choice['expected_cost'], 'observed_claimant': claimant if claimant != 4294967295 else None, 'current_present': bool(current_present), 'past_present': bool(past_present), 'observed_grant_turn': grant_turn if grant_turn != 4294967295 else None}

def guard_case() -> bytes:
    """Lua-double source guards; no native action is submitted or simulated."""
    catalog = catalog_source(0, 4)
    revalidate = revalidate_choice_source({'player_id': 0, 'current_game_turn': 4, 'selected_individual': 17, 'expected_cost': 100, 'operation': 3907540154, 'parameter_key': 945800002, 'parameters': {945800002: 17}})
    effect = effect_source({'player_id': 0, 'current_game_turn': 4, 'selected_individual': 17, 'expected_cost': 100, 'operation': 3907540154, 'parameter_key': 945800002, 'parameters': {945800002: 17}})
    return b'local ok,result=pcall(function()\nlocal Game,Players,GameInfo,PlayerOperations\nlocal S={pid=0,observer=0,turn=4,alive=true,active=true,complete=true,strategic=true,\n cap=true,canRecruit=true,duplicate=false,claimant=nil,currentPresent=true,pastPresent=false,pastClaimant=nil,\n pastTurnGranted=nil,mutateTurn=false,nilEntry=false,currentCost=100,pastCost=100}\nlocal function timeline(claimant)\n local rows={{Individual=17,Claimant=claimant,Cost=claimant~=nil and S.currentCost or 100}}\n if S.nilEntry then rows[#rows+1]={Claimant=claimant,Cost=100} end\n if S.duplicate then rows[#rows+1]={Individual=17,Claimant=claimant,Cost=100} end\n return rows\nend\nlocal gp={GetTimeline=function() return S.currentPresent and timeline(S.claimant) or {} end,\n GetPastTimeline=function()\n  if not S.pastPresent then return {} end\n  return {{Individual=17,Claimant=S.pastClaimant,TurnGranted=S.pastTurnGranted,Cost=S.pastCost}}\n end,\n CanRecruitPerson=function(self,pid,id)\n  assert(pid==0 and id==17)\n  if S.mutateTurn then S.turn=5 end\n  return S.canRecruit and (S.claimant==nil or S.claimant==pid)\n end}\nGame={GetLocalPlayer=function() return S.pid end,GetLocalObserver=function() return S.observer end,\n GetCurrentGameTurn=function() return S.turn end,\n IsAllowStrategicCommands=function(pid) assert(pid==0); return S.strategic end,\n GetGreatPeople=function() return gp end}\nPlayers={[0]={IsAlive=function() return S.alive end,IsTurnActive=function() return S.active end,\n IsTurnActiveComplete=function() return S.complete end}}\nGameInfo={GameCapabilities={CAPABILITY_GREAT_PEOPLE_CAN_RECRUIT={}},\n GreatPersonIndividuals={[17]={Index=17}}}\nPlayerOperations={RECRUIT_GREAT_PERSON=-387427142,PARAM_GREAT_PERSON_INDIVIDUAL_TYPE=945800002}\nlocal function runCatalog()\n' + catalog + b'end\nlocal function runRevalidate()\n' + revalidate + b'end\nlocal function runEffect()\n' + effect + b"end\nassert(runCatalog()=='catalog,0,4,3907540154,945800002,1,17:100')\nassert(runRevalidate()=='valid,0,4,17,100,3907540154,945800002')\nassert(runEffect()=='pending,0,4,17,4294967295,1,0,4294967295')\nS.claimant=0; assert(runEffect()=='pending,0,4,17,0,1,0,4294967295'); S.claimant=nil\nS.claimant=0; assert(runCatalog()=='catalog,0,4,3907540154,945800002,1,17:100');\n assert(runRevalidate()=='valid,0,4,17,100,3907540154,945800002'); S.claimant=nil\nS.claimant=1; assert(runEffect()=='conflict,0,4,17,1,1,0,4294967295'); S.claimant=nil\nS.claimant=1; assert(runCatalog()=='not_due,0,4,no_recruitable_person'); S.claimant=nil\nS.pastPresent=true; S.pastClaimant=0; S.pastTurnGranted=4\nassert(not pcall(runEffect)) -- contradictory current/past claimants must fail\nS.currentPresent=false\nassert(runEffect()=='verified,0,4,17,0,0,1,4'); S.pastPresent=false; S.pastClaimant=nil; S.pastTurnGranted=nil\nS.pastPresent=true; S.pastClaimant=0; assert(not pcall(runEffect)); S.pastPresent=false; S.pastClaimant=nil\nS.pastPresent=true; S.pastClaimant=nil; assert(runEffect()=='pending,0,4,17,4294967295,0,1,4294967295'); S.pastPresent=false\nS.currentPresent=true\nS.claimant=0; S.pastPresent=true; S.pastClaimant=0; S.pastTurnGranted=4; S.currentCost=300; S.pastCost=900\nassert(runEffect()=='verified,0,4,17,0,1,1,4'); S.claimant=nil; S.pastPresent=false; S.pastClaimant=nil; S.pastTurnGranted=nil; S.currentCost=100; S.pastCost=100\nS.claimant=0; S.pastPresent=true; S.pastClaimant=0; S.pastTurnGranted=3\nassert(not pcall(runEffect)); S.claimant=nil; S.pastPresent=false; S.pastClaimant=nil; S.pastTurnGranted=nil\nS.claimant=0; S.pastPresent=true; S.pastClaimant=0; S.pastTurnGranted=5\nassert(not pcall(runEffect)); S.claimant=nil; S.pastPresent=false; S.pastClaimant=nil; S.pastTurnGranted=nil\nS.nilEntry=true; assert(runCatalog()=='catalog,0,4,3907540154,945800002,1,17:100')\n assert(runEffect()=='pending,0,4,17,4294967295,1,0,4294967295'); S.nilEntry=false\nS.canRecruit=false; assert(runCatalog()=='not_due,0,4,no_recruitable_person');\n assert(not pcall(runRevalidate)); S.canRecruit=true\nS.duplicate=true; assert(not pcall(runCatalog) and not pcall(runRevalidate) and not pcall(runEffect)); S.duplicate=false\nS.pid=1; assert(not pcall(runCatalog)); S.pid=0\nS.observer=1; assert(not pcall(runCatalog)); S.observer=0\nS.turn=5; assert(not pcall(runCatalog) and not pcall(runRevalidate) and not pcall(runEffect)); S.turn=4\nS.alive=false; assert(not pcall(runCatalog)); S.alive=true\nS.active=false; assert(not pcall(runCatalog)); S.active=true\nS.complete=false; assert(not pcall(runCatalog)); S.complete=true\nS.strategic=false; assert(not pcall(runCatalog) and not pcall(runRevalidate) and not pcall(runEffect)); S.strategic=true\nGameInfo.GameCapabilities.CAPABILITY_GREAT_PEOPLE_CAN_RECRUIT=nil; assert(not pcall(runCatalog))\nGameInfo.GameCapabilities.CAPABILITY_GREAT_PEOPLE_CAN_RECRUIT={}\nS.mutateTurn=true; assert(not pcall(runCatalog)); S.mutateTurn=false; S.turn=4\nreturn 'great-people-guards-ok'\nend)\nassert(ok,result)\nreturn result\n"

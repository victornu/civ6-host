"""Source-pinned public request/readback for founding a named religion.

This is deliberately separate from Great Prophet activation and ADD_BELIEF.
It excludes religion rows requiring a custom name; no name is generated here.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_religion_founding.py')))).resolve().parents[1]
PROOF_SHA256 = 'c5f6dd96698059bf7fc4b8c4bf765d4876857f1963d1772657c67866f32609e0'
PROOF = ROOT / 'evidence/native-religion-founding-actions' / f'{PROOF_SHA256}.json'
EFFECT_PROOF_SHA256 = '3e237a09294a7faf2f0e19346d3a35f0b718651b2d9732b9670a7d1735d1d823'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
UI_ROOT = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
RELIGION_SCREEN_SHA256 = '651e758c11f9f7ca31417eaa8b8c25c42ad2a118eb03336c52e9e88a8cf3ab57'
FOUND_RELIGION = 2765815733
PARAM_RELIGION_TYPE = 581065611
PARAM_INSERT_MODE = 2888817673
VALUE_EXCLUSIVE = 2550048198
MAX_RELIGIONS = 4096
MAX_RESPONSE = 65536

def verify_source() -> None:
    proof = load_pinned_json(PROOF, PROOF_SHA256)
    effect = load_pinned_json(ROOT / 'evidence/native-religion-founding-effect' / (EFFECT_PROOF_SHA256 + '.json'), EFFECT_PROOF_SHA256)
    if effect.get('schema') != 'civ6rl.native_religion_founding_effect.static.v1' or effect.get('core_sha256') != CORE_SHA256 or effect.get('exe_sha256') != EXE_SHA256 or (effect.get('contract', {}).get('new_live_beliefs', {}).get('initial_count') != 0) or (effect.get('contract', {}).get('has_founding_unit', {}).get('must_be_false_to_found') is not False):
        raise RuntimeError('Religion-founding effect source identity changed')
    if proof.get('schema') != 'civ6rl.native_religion_founding_actions.static.v1' or proof.get('exe_sha256') != EXE_SHA256 or proof.get('core_sha256') != CORE_SHA256:
        raise RuntimeError('Religion-founding source identity changed')
    operation = proof.get('player_operation', {})
    expected_request = 'UI.RequestPlayerOperation(localPlayer, PlayerOperations.FOUND_RELIGION'
    if expected_request not in operation.get('request', ''):
        raise RuntimeError('Religion-founding request is not source-pinned')
    enums = proof.get('enums', {})
    expected = {'PlayerOperations.FOUND_RELIGION': (FOUND_RELIGION, -1529151563), 'PlayerOperations.PARAM_RELIGION_TYPE': (PARAM_RELIGION_TYPE, 581065611), 'PlayerOperations.PARAM_INSERT_MODE': (PARAM_INSERT_MODE, -1406149623), 'PlayerOperations.VALUE_EXCLUSIVE': (VALUE_EXCLUSIVE, -1744919098)}
    for name, (bits, signed) in expected.items():
        row = enums.get(name, {})
        if row.get('bits_u32') != f'0x{bits:08x}' or row.get('signed32') != signed:
            raise RuntimeError(f'Religion-founding enum changed: {name}')
    ui = UI_ROOT / 'ReligionScreen.lua'
    if hashlib.sha256(_resolve_resource_path(ui).read_bytes()).hexdigest() != RELIGION_SCREEN_SHA256:
        raise RuntimeError('Installed ReligionScreen source changed')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _signed32(value: int, label: str) -> int:
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError(f'Invalid {label}')
    return value

def _parse_uint(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((c < 48 or c > 57 for c in token)) or (len(token) > 1 and token[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'Out-of-range {label}')
    return value

def _pid_turn(player_id: int, expected_turn: int) -> tuple[int, int]:
    return (_uint(player_id, 'player ID', 63), _uint(expected_turn, 'game turn'))

def _context_prefix(player_id: int, expected_turn: int, *, require_unfounded: bool=True) -> bytes:
    pid, turn = _pid_turn(player_id, expected_turn)
    verify_source()
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(turn).encode() + b'\nlocal requireUnfounded=' + (b'true' if require_unfounded else b'false') + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n 'religion-foundation player perspective mismatch')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n 'religion-foundation observer mismatch')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n 'religion-foundation decision is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and\n Game.IsAllowStrategicCommands(pid)==true,'strategic commands are not allowed')\nlocal player=Players and Players[pid]\nassert(player and type(player.GetID)=='function' and player:GetID()==pid and\n player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'religion founder is not ready')\nassert(type(player.GetReligion)=='function','player religion API unavailable')\nlocal playerReligion=player:GetReligion()\nassert(playerReligion and type(playerReligion.GetReligionTypeCreated)=='function' and\n type(playerReligion.HasReligiousFoundingUnit)=='function' and\n type(playerReligion.GetHolyCityID)=='function' and\n type(playerReligion.GetNumBeliefsEarned)=='function','player religion readback unavailable')\nlocal created=playerReligion:GetReligionTypeCreated()\nlocal hasProphet=playerReligion:HasReligiousFoundingUnit()\nlocal earned=playerReligion:GetNumBeliefsEarned()\n assert(type(created)=='number' and created==math.floor(created) and created>=-1 and\n  created<=2147483647,'invalid created religion index')\n assert(type(hasProphet)=='boolean','invalid founding prophet state')\n assert(type(earned)=='number' and earned==math.floor(earned) and earned>=0 and earned<=2147483647,\n  'invalid earned religion belief count')\n if requireUnfounded then\n  assert(created==-1,'player already has a religion')\n  assert(earned>0,'no earned religion beliefs are available')\n end\nlocal holy=playerReligion:GetHolyCityID()\nassert(type(holy)=='table' and type(holy.player)=='number' and\n type(holy.type)=='number' and type(holy.id)=='number','founding site descriptor unavailable')\nassert(holy.player==pid and holy.type==2 and holy.id>=0 and holy.id<=2147483647,\n 'founding site is not a current own city')\nlocal cityIDs,count={},0\nlocal cityCollection=player:GetCities()\nassert(cityCollection and type(cityCollection.Members)=='function','own city collection unavailable')\nfor _,city in cityCollection:Members() do\n count=count+1;assert(count<=256,'own city collection exceeds bound')\n assert(city and city:GetOwner()==pid,'foreign city in own city collection')\n local id=city:GetID()\n assert(type(id)=='number' and id==math.floor(id) and id>=0 and id<=2147483647,\n  'invalid own city ID')\n assert(cityIDs[id]==nil,'duplicate own city ID');cityIDs[id]=true\nend\nassert(cityIDs[holy.id]==true,'founding site is not in own city collection')\nassert(Game.GetReligion and type(Game.GetReligion)=='function','global religion API unavailable')\nlocal gameReligion=Game.GetReligion()\nassert(gameReligion and type(gameReligion.GetReligions)=='function' and\n type(gameReligion.HasBeenFounded)=='function','global religion getters unavailable')\nlocal religions=gameReligion:GetReligions()\nassert(type(religions)=='table','founded religion list unavailable')\nlocal ownRows,allCount=0,0\nfor _,entry in ipairs(religions) do\n allCount=allCount+1;assert(allCount<=" + str(MAX_RELIGIONS).encode() + b",'religion list exceeds bound')\n assert(type(entry)=='table','malformed founded religion row')\n assert(type(entry.Founder)=='number' and entry.Founder==math.floor(entry.Founder) and\n  entry.Founder>=0 and entry.Founder<=63,'malformed religion founder')\n if entry.Founder==pid then ownRows=ownRows+1 end\nend\n if requireUnfounded then assert(ownRows==0,'player already has a founded religion row') end\nlocal operationBits=PlayerOperations and PlayerOperations.FOUND_RELIGION\nlocal religionKey=PlayerOperations and PlayerOperations.PARAM_RELIGION_TYPE\nlocal insertKey=PlayerOperations and PlayerOperations.PARAM_INSERT_MODE\nlocal exclusive=PlayerOperations and PlayerOperations.VALUE_EXCLUSIVE\nlocal function bits(value,label)\n assert(type(value)=='number' and value==math.floor(value) and\n  value>=-2147483648 and value<=4294967295,'invalid '..label)\n return value<0 and value+4294967296 or value\nend\noperationBits=bits(operationBits,'operation')\nreligionKey=bits(religionKey,'religion parameter')\ninsertKey=bits(insertKey,'insert parameter')\nexclusive=bits(exclusive,'exclusive value')\nassert(operationBits==" + str(FOUND_RELIGION).encode() + b' and\n religionKey==' + str(PARAM_RELIGION_TYPE).encode() + b' and\n insertKey==' + str(PARAM_INSERT_MODE).encode() + b' and\n exclusive==' + str(VALUE_EXCLUSIVE).encode() + b",'religion operation enums changed')\nlocal function context()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n  Game.GetCurrentGameTurn()==expectedTurn,'religion-foundation context changed')\n assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands are no longer allowed')\n local currentPlayer=Players and Players[pid]\n assert(currentPlayer and type(currentPlayer.GetID)=='function' and currentPlayer:GetID()==pid and\n  currentPlayer:IsAlive()==true and currentPlayer:IsTurnActive()==true and\n  currentPlayer:IsTurnActiveComplete()==true,'religion founder is no longer ready')\nend\ncontext()\n"

def catalog_source(player_id: int, expected_turn: int) -> bytes:
    return _context_prefix(player_id, expected_turn) + b"\nlocal rows,indices,hashes={}, {}, {}\nfor row in GameInfo.Religions() do\n assert(type(row)=='table','malformed religion definition')\n assert(type(row.Index)=='number' and row.Index==math.floor(row.Index) and\n  row.Index>=0 and row.Index<=2147483647,'invalid religion index')\n assert(type(row.Hash)=='number' and row.Hash==math.floor(row.Hash) and\n  row.Hash>=-2147483648 and row.Hash<=4294967295,'invalid religion hash')\n if row.Pantheon==false and not row.RequiresCustomName and\n    gameReligion:HasBeenFounded(row.Index)==false then\n  assert(not indices[row.Index],'duplicate unclaimed religion index')\n  local h=row.Hash<0 and row.Hash+4294967296 or row.Hash\n  assert(not hashes[h],'duplicate unclaimed religion hash')\n  indices[row.Index]=true;hashes[h]=true\n  rows[#rows+1]={index=row.Index,hash=h}\n end\nend\ntable.sort(rows,function(a,b) return a.index<b.index end)\ncontext()\nlocal function d(n) return string.format('%.0f',n) end\nlocal out={'catalog',d(pid),d(expectedTurn),d(earned),d(holy.player),d(holy.type),d(holy.id),\n d(ownRows),d(operationBits),d(religionKey),d(insertKey),d(exclusive),d(#rows)}\nfor _,row in ipairs(rows) do out[#out+1]=d(row.index)..':'..d(row.hash) end\nreturn table.concat(out,',')\n"

def parse_catalog(payload: bytes, player_id: int, expected_turn: int) -> dict:
    pid, turn = _pid_turn(player_id, expected_turn)
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid religion catalog payload')
    fields = payload.split(b',')
    if len(fields) < 13 or fields[0] != b'catalog':
        raise ValueError('Malformed religion catalog')
    header = tuple((_parse_uint(v, name, maxv) for v, name, maxv in ((fields[1], 'player', 63), (fields[2], 'turn', 4294967295), (fields[3], 'earned beliefs', 2147483647), (fields[4], 'site owner', 63), (fields[5], 'site type', 65535), (fields[6], 'site ID', 2147483647), (fields[7], 'own religion count', MAX_RELIGIONS), (fields[8], 'operation', 4294967295), (fields[9], 'religion key', 4294967295), (fields[10], 'insert key', 4294967295), (fields[11], 'exclusive value', 4294967295), (fields[12], 'candidate count', MAX_RELIGIONS))))
    actual_pid, actual_turn, earned, site_owner, site_type, site_id, own_count, operation, religion_key, insert_key, exclusive, count = header
    if (actual_pid, actual_turn) != (pid, turn):
        raise ValueError('Religion catalog is stale or foreign')
    if earned == 0 or site_owner != pid or site_type != 2 or (own_count != 0) or (operation != FOUND_RELIGION) or (religion_key != PARAM_RELIGION_TYPE) or (insert_key != PARAM_INSERT_MODE) or (exclusive != VALUE_EXCLUSIVE):
        raise ValueError('Religion catalog lacks required native preconditions')
    if count != len(fields) - 13:
        raise ValueError('Religion catalog count mismatch')
    candidates, seen_indices, seen_hashes, previous = ([], set(), set(), -1)
    for token in fields[13:]:
        parts = token.split(b':')
        if len(parts) != 2:
            raise ValueError('Malformed religion candidate')
        index = _parse_uint(parts[0], 'religion index', 2147483647)
        hash_value = _parse_uint(parts[1], 'religion hash')
        if index <= previous or index in seen_indices or hash_value in seen_hashes:
            raise ValueError('Religion candidates are duplicated or unordered')
        previous = index
        seen_indices.add(index)
        seen_hashes.add(hash_value)
        candidates.append({'index': index, 'hash': hash_value})
    return {'status': 'catalog' if count else 'not_due', 'player_id': pid, 'current_game_turn': turn, 'num_beliefs_earned': earned, 'founding_site': {'player': site_owner, 'type': site_type, 'id': site_id}, 'own_religion_count': own_count, 'operation': operation, 'religion_parameter': religion_key, 'insert_parameter': insert_key, 'exclusive_value': exclusive, 'candidates': tuple(candidates)}

def choose(catalog: dict, religion_index: int) -> dict:
    required = {'status', 'player_id', 'current_game_turn', 'num_beliefs_earned', 'founding_site', 'own_religion_count', 'operation', 'religion_parameter', 'insert_parameter', 'exclusive_value', 'candidates'}
    if type(catalog) is not dict or set(catalog) != required or catalog.get('status') != 'catalog':
        raise ValueError('No eligible religion catalog')
    pid, turn = _pid_turn(catalog['player_id'], catalog['current_game_turn'])
    earned = _uint(catalog['num_beliefs_earned'], 'earned beliefs', 2147483647)
    site = catalog['founding_site']
    if earned == 0 or type(site) is not dict or set(site) != {'player', 'type', 'id'} or (site.get('player') != pid) or (site.get('type') != 2) or (type(site.get('id')) is not int) or (not 0 <= site['id'] <= 2147483647) or (catalog['own_religion_count'] != 0):
        raise ValueError('Invalid religion-foundation preconditions')
    for name, expected in (('operation', FOUND_RELIGION), ('religion_parameter', PARAM_RELIGION_TYPE), ('insert_parameter', PARAM_INSERT_MODE), ('exclusive_value', VALUE_EXCLUSIVE)):
        if _uint(catalog[name], name) != expected:
            raise ValueError('Unexpected religion request enum')
    entries = catalog['candidates']
    if type(entries) is not tuple or not 0 < len(entries) <= MAX_RELIGIONS:
        raise ValueError('Invalid religion candidate list')
    previous = -1
    seen_hashes = set()
    for item in entries:
        if type(item) is not dict or set(item) != {'index', 'hash'}:
            raise ValueError('Malformed religion candidate')
        index = _uint(item['index'], 'religion index', 2147483647)
        hash_value = _uint(item['hash'], 'religion hash')
        if index <= previous or hash_value in seen_hashes:
            raise ValueError('Duplicate/unordered religion catalog')
        previous = index
        seen_hashes.add(hash_value)
    index = _uint(religion_index, 'selected religion index', 2147483647)
    matches = [item for item in entries if item['index'] == index]
    if len(matches) != 1:
        raise ValueError('Selected religion is absent or ambiguous')
    return {'player_id': pid, 'current_game_turn': turn, 'num_beliefs_earned': earned, 'founding_site': dict(site), 'religion_index': index, 'religion_hash': matches[0]['hash'], 'operation': FOUND_RELIGION, 'parameters': {PARAM_INSERT_MODE: VALUE_EXCLUSIVE, PARAM_RELIGION_TYPE: matches[0]['hash']}, 'custom_name': None}

def _validate_choice(choice: dict) -> None:
    keys = {'player_id', 'current_game_turn', 'num_beliefs_earned', 'founding_site', 'religion_index', 'religion_hash', 'operation', 'parameters', 'custom_name'}
    if type(choice) is not dict or set(choice) != keys or choice.get('custom_name') is not None:
        raise ValueError('Malformed or custom-named religion choice')
    pid, _ = _pid_turn(choice['player_id'], choice['current_game_turn'])
    _uint(choice['num_beliefs_earned'], 'earned beliefs', 2147483647)
    site = choice['founding_site']
    if type(site) is not dict or set(site) != {'player', 'type', 'id'} or site.get('player') != pid or (site.get('type') != 2) or (type(site.get('id')) is not int) or (not 0 <= site['id'] <= 2147483647):
        raise ValueError('Invalid founding site in selected religion')
    _uint(choice['religion_index'], 'religion index', 2147483647)
    _uint(choice['religion_hash'], 'religion hash')
    if _uint(choice['operation'], 'operation') != FOUND_RELIGION:
        raise ValueError('Unexpected religion operation')
    expected = {PARAM_INSERT_MODE: VALUE_EXCLUSIVE, PARAM_RELIGION_TYPE: choice['religion_hash']}
    if choice['parameters'] != expected:
        raise ValueError('Religion request parameters differ from selected row')

def request_operation(choice: dict) -> tuple[int, dict[int, int]]:
    """Return DWORDs for native_player_operation_request; makes no native call."""
    _validate_choice(choice)
    verify_source()
    return (FOUND_RELIGION, dict(choice['parameters']))

def revalidate_source(choice: dict) -> bytes:
    _validate_choice(choice)
    prefix = _context_prefix(choice['player_id'], choice['current_game_turn'])
    vals = (choice['religion_index'], choice['religion_hash'], choice['num_beliefs_earned'], choice['founding_site']['id'])
    return prefix + b'local expectedIndex,expectedHash,expectedEarned,expectedSite=' + b','.join((str(v).encode() for v in vals)) + b"\nassert(playerReligion:GetReligionTypeCreated()==-1 and\n playerReligion:GetNumBeliefsEarned()==expectedEarned,'religion state changed')\nlocal holy=playerReligion:GetHolyCityID()\nassert(holy.player==pid and holy.type==2 and holy.id==expectedSite,\n 'founding site changed')\nassert(gameReligion:HasBeenFounded(expectedIndex)==false,\n 'selected religion has already been founded')\nlocal selected=GameInfo.Religions[expectedIndex]\nassert(selected and selected.Index==expectedIndex and selected.Pantheon==false and\n not selected.RequiresCustomName,'selected religion is no longer eligible')\nlocal h=selected.Hash<0 and selected.Hash+4294967296 or selected.Hash\nassert(h==expectedHash,'selected religion hash changed')\ncontext()\nlocal function d(n) return string.format('%.0f',n) end\nreturn table.concat({'valid',d(pid),d(expectedTurn),d(expectedIndex),d(expectedHash),\n d(expectedEarned),d(expectedSite)},',')\n"

def parse_revalidated(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 256:
        raise ValueError('Invalid religion revalidation payload')
    parts = payload.split(b',')
    if len(parts) != 7 or parts[0] != b'valid':
        raise ValueError('Malformed religion revalidation response')
    actual = tuple((_parse_uint(v, 'revalidated value') for v in parts[1:]))
    expected = (choice['player_id'], choice['current_game_turn'], choice['religion_index'], choice['religion_hash'], choice['num_beliefs_earned'], choice['founding_site']['id'])
    if actual != expected:
        raise ValueError('Revalidated religion differs from selection')
    return {'valid': True, 'choice': choice, 'operation': FOUND_RELIGION, 'parameters': dict(choice['parameters'])}

def effect_source(choice: dict, before_observation: dict) -> bytes:
    _validate_choice(choice)
    required = {'player_id', 'current_game_turn', 'religion_type_created', 'has_religious_founding_unit', 'num_beliefs_earned', 'holy_city', 'own_religion'}
    if type(before_observation) is not dict or not required <= set(before_observation):
        raise ValueError('Missing pre-foundation religion observation')
    pid, turn = (choice['player_id'], choice['current_game_turn'])
    if before_observation['player_id'] != pid or before_observation['current_game_turn'] != turn or before_observation['religion_type_created'] != -1 or (type(before_observation['has_religious_founding_unit']) is not bool) or (before_observation['own_religion'] is not None):
        raise ValueError('Pre-foundation snapshot is stale or already founded')
    if before_observation['num_beliefs_earned'] != choice['num_beliefs_earned'] or before_observation['holy_city'] != choice['founding_site']:
        raise ValueError('Pre-foundation snapshot differs from selected catalog')
    prefix = _context_prefix(pid, turn, require_unfounded=False)
    index, hash_value, expected_site, earned = (choice['religion_index'], choice['religion_hash'], choice['founding_site']['id'], choice['num_beliefs_earned'])
    source = b'local expectedIndex,expectedHash,expectedSite,expectedEarned=' + b','.join((str(v).encode() for v in (index, hash_value, expected_site, earned))) + b"\nlocal holy=playerReligion:GetHolyCityID()\nassert(holy.player==pid and holy.type==2 and holy.id==expectedSite,\n 'founding site changed during religion creation')\nlocal row=GameInfo.Religions[expectedIndex]\nassert(row and row.Index==expectedIndex and row.Pantheon==false and\n not row.RequiresCustomName,'selected religion definition changed')\nlocal h=row.Hash<0 and row.Hash+4294967296 or row.Hash\nassert(h==expectedHash,'selected religion hash changed')\nassert(gameReligion:HasBeenFounded(expectedIndex)==true,\n 'native religion founded state is not published')\nassert(playerReligion:GetReligionTypeCreated()==expectedIndex,\n 'native player created-religion index is not published')\nlocal list=gameReligion:GetReligions()\nassert(type(list)=='table','founded religion list unavailable')\nlocal own,ownCount=0,nil\nfor _,entry in ipairs(list) do\n assert(type(entry)=='table','malformed religion row')\n if entry.Founder==pid then\n  own=own+1\n  assert(own==1,'ambiguous own religion rows')\n  ownCount=entry\n end\nend\nassert(own==1 and ownCount.Religion==expectedIndex,\n 'new own-Founder religion row is missing or mismatched')\nlocal beliefs=ownCount.Beliefs\nassert(type(beliefs)=='table','own religion beliefs are unavailable')\nlocal n=0\nfor k,v in pairs(beliefs) do\n assert(type(k)=='number' and k==math.floor(k) and k>=1 and\n  type(v)=='number' and v==math.floor(v) and v>=0,\n  'malformed own religion belief list')\n n=n+1;assert(n<=4096,'own belief list exceeds bound')\nend\nassert(n==0,'religion already has beliefs; ADD_BELIEF phase is not empty')\nlocal currentEarned=playerReligion:GetNumBeliefsEarned()\nassert(type(currentEarned)=='number' and currentEarned==math.floor(currentEarned) and\n currentEarned==earned and currentEarned==expectedEarned,\n 'earned-belief count changed across the isolated founding step')\ncontext()\nlocal function d(n) return string.format('%.0f',n) end\nreturn table.concat({'effect',d(pid),d(expectedTurn),d(expectedIndex),d(expectedHash),\n d(expectedSite),d(currentEarned),d(own),d(n)},',')\n"
    return prefix + source

def parse_effect(payload: bytes, choice: dict, before_observation: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 512:
        raise ValueError('Invalid religion effect payload')
    fields = payload.split(b',')
    if len(fields) != 9 or fields[0] != b'effect':
        raise ValueError('Malformed religion effect response')
    actual = tuple((_parse_uint(v, 'effect value') for v in fields[1:]))
    expected = (choice['player_id'], choice['current_game_turn'], choice['religion_index'], choice['religion_hash'], choice['founding_site']['id'], choice['num_beliefs_earned'], 1, 0)
    if actual != expected:
        raise ValueError('Religion founding effect differs from chosen entry')
    if type(before_observation) is not dict or before_observation.get('player_id') != choice['player_id'] or before_observation.get('current_game_turn') != choice['current_game_turn'] or (before_observation.get('religion_type_created') != -1) or (type(before_observation.get('has_religious_founding_unit')) is not bool) or (before_observation.get('num_beliefs_earned') != choice['num_beliefs_earned']) or (before_observation.get('holy_city') != choice['founding_site']) or (before_observation.get('own_religion') is not None):
        raise ValueError('Pre-foundation observation is stale or invalid')
    return {'religion_created': True, 'religion_index': choice['religion_index'], 'religion_hash': choice['religion_hash'], 'founder': choice['player_id'], 'founding_site': dict(choice['founding_site']), 'belief_indices': (), 'beliefs_still_to_allocate': choice['num_beliefs_earned'], 'belief_allocation_not_submitted': True, 'source_proof_sha256': PROOF_SHA256}

def guard_case() -> bytes:
    """A self-contained positive HKS/Lupa guard for the three source chunks."""
    pid, turn, index, hash_value = (0, 60, 9, 4294967295)
    catalog = catalog_source(pid, turn)
    parsed = parse_catalog(b'catalog,0,60,2,0,2,65536,0,2765815733,581065611,2888817673,2550048198,2,4:123456789,9:4294967295', pid, turn)
    choice = choose(parsed, index)
    revalidate = revalidate_source(choice)
    before = {'player_id': pid, 'current_game_turn': turn, 'religion_type_created': -1, 'has_religious_founding_unit': False, 'num_beliefs_earned': 2, 'holy_city': {'player': 0, 'type': 2, 'id': 65536}, 'own_religion': None}
    effect = effect_source(choice, before)
    return b"local Game,Players,GameInfo,PlayerOperations,UI\nlocal currentPlayer,currentObserver,currentTurn=0,0,60\nlocal alive,active,complete,strategic=true,true,true,true\nlocal created,hasProphet,earned=-1,false,2\nlocal holy={player=0,type=2,id=65536}\nlocal founded,ownRows={},{}\nlocal city={GetOwner=function() return 0 end,GetID=function() return 65536 end}\nlocal religion={GetReligionTypeCreated=function() return created end,\n HasReligiousFoundingUnit=function() return hasProphet end,\n GetNumBeliefsEarned=function() return earned end,\n GetHolyCityID=function() return holy end}\nlocal player={GetID=function() return 0 end,IsAlive=function() return alive end,IsTurnActive=function() return active end,\n IsTurnActiveComplete=function() return complete end,GetReligion=function() return religion end,\n GetCities=function() return {Members=function() local done=false;return function()\n  if not done then done=true;return 1,city end end end} end}\nPlayers={[0]=player}\nlocal rows={{Index=4,Hash=123456789,Pantheon=false,RequiresCustomName=false},\n {Index=9,Hash=4294967295,Pantheon=false,RequiresCustomName=false},\n {Index=11,Hash=5,Pantheon=true,RequiresCustomName=false},\n {Index=12,Hash=6,Pantheon=false,RequiresCustomName=true}}\nGameInfo={Religions=setmetatable({[4]=rows[1],[9]=rows[2]},\n {__call=function() local i=0;return function() i=i+1;return rows[i] end end})}\nPlayerOperations={FOUND_RELIGION=2765815733,PARAM_RELIGION_TYPE=581065611,\n PARAM_INSERT_MODE=2888817673,VALUE_EXCLUSIVE=2550048198}\nlocal globalReligion={HasBeenFounded=function(_,i) return founded[i]==true end,\n GetReligions=function() return ownRows end}\nGame={GetLocalPlayer=function() return currentPlayer end,\n GetLocalObserver=function() return currentObserver end,\n GetCurrentGameTurn=function() return currentTurn end,\n IsAllowStrategicCommands=function(p) return strategic and p==0 end,\n GetReligion=function() return globalReligion end}\nUI={RequestPlayerOperation=function() error('guard must not submit requests') end}\nlocal catalogWire=(function()\n" + catalog + b"\nend)()\nassert(catalogWire=='catalog,0,60,2,0,2,65536,0,2765815733,581065611,2888817673,2550048198,2,4:123456789,9:4294967295')\nlocal revalidated=(function()\n" + revalidate + b"\nend)()\nassert(revalidated=='valid,0,60,9,4294967295,2,65536')\ncurrentTurn=61\nassert(not pcall(function()\n (function() " + revalidate + b" end)()\nend),'stale religion choice was accepted')\ncurrentTurn=60;created=9;founded[9]=true\nownRows={{Founder=0,Religion=9,Beliefs={}}}\nlocal effectWire=(function()\n" + effect + b"\nend)()\nassert(effectWire=='effect,0,60,9,4294967295,65536,2,1,0')\nreturn 'native-religion-founding-guard-ok'\n"
__all__ = ['FOUND_RELIGION', 'PARAM_RELIGION_TYPE', 'PARAM_INSERT_MODE', 'VALUE_EXCLUSIVE', 'PROOF_SHA256', 'verify_source', 'catalog_source', 'parse_catalog', 'choose', 'request_operation', 'revalidate_source', 'parse_revalidated', 'effect_source', 'parse_effect', 'guard_case']

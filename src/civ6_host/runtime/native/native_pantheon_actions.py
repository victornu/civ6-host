"""Source-backed pantheon catalog and readback guards.

This module builds/revalidates an official FOUND_PANTHEON request shape. It
does not submit requests, and a request is never treated as acceptance. The
effect check requires the selected GameInfo row index. The pinned native
request-to-cache chain establishes that representation. Religious rules and
their effects remain in the native engine; no private setter is called here.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_pantheon_actions.py')))).resolve().parents[1]
_ASSETS = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_ROUTE_PATH = _ROOT / 'evidence/native-player-operation-route.json'
_ROUTE_SHA256 = '6ba4b94fd024f320012303beca763601857afeff633b7008c394ac52bee0f1d2'
_ROUTE_IMAGES = {'exe': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'}
_UI_SOURCES = {'Choosers/PantheonChooser.lua': '3aee2a93b819f29269da2bdfcac383cb533e43ed21033dbb1a2a90643d5cdf8a', 'ReligionScreen.lua': '651e758c11f9f7ca31417eaa8b8c25c42ad2a118eb03336c52e9e88a8cf3ab57', 'LaunchBar.lua': 'f61262cfc927a5b156f5eb7c0aaa1e8750f2c545db59f2ac7ec7bf8f22d8d0cf'}
_BELIEF_CLASS = 'BELIEF_CLASS_PANTHEON'
_MAX_CHOICES = 4096
_MAX_RESPONSE = 131072
PINNED_EVIDENCE_SHA256 = '6d0db5c53ce5d3daaa74f43abe5d480731e37c6cddb0229a922629a2a08bb73a'
_PROOF = _ROOT / 'evidence/native-pantheon-actions' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source() -> None:
    """Verify native bindings/return representation, UI and request route pins."""
    native = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    expected_callbacks = {'Game.GetReligion': '0x1805234a0', 'Player.GetReligion': '0x180531290', 'CachePlayerReligion.GetPantheon': '0x18053ab60', 'CachePlayerReligion.CanCreatePantheon': '0x18053a990', 'CacheGameReligion.IsInSomePantheon': '0x180527ba0', 'CacheGameReligion.IsInSomeReligion': '0x180527c00'}
    if native['schema'] != 'civ6rl.native_required_pantheon_decision.static.v1' or native['core_sha256'] != _ROUTE_IMAGES['core'] or native['exe_sha256'] != _ROUTE_IMAGES['exe'] or any((native['bindings'][name]['callback_va'] != value for name, value in expected_callbacks.items())) or (native['contracts']['GetPantheon']['cache_offset'] != '0x74') or (native['contracts']['GetPantheon']['absence_sentinel'] != -1) or (native['contracts']['blocker']['signed_value'] != -1679521882):
        raise RuntimeError('Native pantheon source identity changed')
    raw = _resolve_resource_path(_ROUTE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _ROUTE_SHA256:
        raise RuntimeError('Pinned player-operation route proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_player_operation_route.v3' or proof.get('images', {}).get('exe', {}).get('sha256') != _ROUTE_IMAGES['exe'] or proof.get('images', {}).get('core', {}).get('sha256') != _ROUTE_IMAGES['core']:
        raise RuntimeError('Unexpected player-operation route image identity')
    for relative, expected in _UI_SOURCES.items():
        if hashlib.sha256(_resolve_resource_path(_ASSETS / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Installed pantheon UI source changed: {relative}')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or value < 0 or value > maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _player_id(value: int) -> int:
    return _uint(value, 'player ID', 63)

def _turn(value: int) -> int:
    return _uint(value, 'expected game turn')

def _signed_bits(value: int, label: str) -> int:
    if type(value) is not int or value < -2147483648 or value > 2147483647:
        raise ValueError(f'Invalid signed 32-bit {label}')
    return value & 4294967295

def _parse_uint(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((c < 48 or c > 57 for c in token)) or (len(token) > 1 and token[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'{label} is out of range')
    return value

def _common_lua_guards(pid: int, turn: int) -> bytes:
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(turn).encode() + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n       'native observer perspective is another player')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n       'pantheon choice is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and\n       Game.IsAllowStrategicCommands(pid)==true,'strategic commands are not allowed')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,'requested player is not ready')\nlocal religion=player:GetReligion()\nassert(religion and type(religion.GetPantheon)=='function' and\n       type(religion.CanCreatePantheon)=='function','player religion API unavailable')\nlocal function assertContextStillValid()\n assert(type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid and\n        type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid and\n        type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n        'pantheon request context changed')\n assert(type(Game.IsAllowStrategicCommands)=='function' and\n        Game.IsAllowStrategicCommands(pid)==true,'strategic commands are no longer allowed')\n assert(player:IsAlive()==true and player:IsTurnActive()==true and\n        player:IsTurnActiveComplete()==true,'pantheon player is no longer ready')\nend\nassertContextStillValid()\n"

def catalog_source(player_id: int, expected_turn: int) -> bytes:
    """Return the current official pantheon catalog or an explicit not-due result."""
    pid, turn = (_player_id(player_id), _turn(expected_turn))
    verify_source()
    return _common_lua_guards(pid, turn) + b"local current=religion:GetPantheon()\nassert(type(current)=='number' and current==math.floor(current) and\n       current>=-2147483648 and current<=2147483647,'invalid pantheon state')\nlocal canCreate=religion:CanCreatePantheon()\nassert(type(canCreate)=='boolean','invalid CanCreatePantheon result')\nlocal function notDue(reason)\n local currentAgain=religion:GetPantheon()\n local canCreateAgain=religion:CanCreatePantheon()\n assert(type(currentAgain)=='number' and currentAgain==current and\n        type(canCreateAgain)=='boolean' and canCreateAgain==canCreate,\n        'pantheon due-state changed during catalog')\n assertContextStillValid()\n return 'not_due,'..pid..','..expectedTurn..','..reason\nend\nif current>=0 then return notDue('already_has_pantheon') end\nif not canCreate then return notDue('cannot_create') end\nlocal gameReligion=Game.GetReligion()\nassert(gameReligion and type(gameReligion.IsInSomePantheon)=='function' and\n       type(gameReligion.IsInSomeReligion)=='function','global religion filter unavailable')\nassert(PlayerOperations and PlayerOperations.FOUND_PANTHEON~=nil and\n       PlayerOperations.PARAM_BELIEF_TYPE~=nil and\n       PlayerOperations.PARAM_INSERT_MODE~=nil and\n       PlayerOperations.VALUE_EXCLUSIVE~=nil,'source PlayerOperations enums unavailable')\nlocal function u32(v,label)\n assert(type(v)=='number' and v==math.floor(v) and v>=0 and v<=2147483647,\n        'invalid nonnegative signed index '..label)\n return v\nend\nlocal function signedBits(v,label)\n assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n        'native signed integer out of range '..label)\n return v<0 and v+4294967296 or v\nend\nlocal operation=signedBits(PlayerOperations.FOUND_PANTHEON,'operation')\nlocal key=signedBits(PlayerOperations.PARAM_BELIEF_TYPE,'belief parameter')\nlocal insert=signedBits(PlayerOperations.PARAM_INSERT_MODE,'insert parameter')\nlocal exclusive=signedBits(PlayerOperations.VALUE_EXCLUSIVE,'exclusive mode')\nassert(key~=insert,'pantheon parameter keys collide')\nlocal choices,seenIndex,seenHash={}, {}, {}\nlocal scanned=0\nfor row in GameInfo.Beliefs() do\n scanned=scanned+1; assert(scanned<=" + str(_MAX_CHOICES).encode() + b',\n   \'GameInfo belief enumeration exceeds diagnostic bound\')\n assert(row and row.Index~=nil and row.Hash~=nil and row.BeliefClassType~=nil,\n        \'incomplete belief row\')\n local index=u32(row.Index,\'belief index\')\n local hash=signedBits(row.Hash,\'belief hash\')\n local usedPantheon=gameReligion:IsInSomePantheon(index)\n local usedReligion=gameReligion:IsInSomeReligion(index)\n assert(type(usedPantheon)==\'boolean\' and type(usedReligion)==\'boolean\',\n        \'native global belief availability is not boolean\')\n if row.BeliefClassType=="BELIEF_CLASS_PANTHEON" and\n    not usedPantheon and not usedReligion then\n   assert(not seenIndex[index] and not seenHash[hash],\n          \'duplicate eligible belief index or hash\')\n   seenIndex[index]=true; seenHash[hash]=true\n   choices[#choices+1]={index=index,hash=hash}\n end\nend\ntable.sort(choices,function(a,b) return a.index<b.index end)\nlocal function dec(n) return string.format(\'%.0f\',n) end\nlocal fields={\'catalog\',dec(pid),dec(expectedTurn),dec(operation),dec(key),\n dec(insert),dec(exclusive),dec(#choices)}\nfor _,item in ipairs(choices) do\n fields[#fields+1]=dec(item.index)..\':\'..dec(item.hash)\nend\nassert(religion:GetPantheon()==current and religion:CanCreatePantheon()==true,\n       \'pantheon due-state changed during catalog\')\nassertContextStillValid()\nreturn table.concat(fields,\',\')\n'

def parse_catalog(payload: bytes, player_id: int, expected_turn: int) -> dict:
    pid, turn = (_player_id(player_id), _turn(expected_turn))
    if type(payload) is not bytes or len(payload) > _MAX_RESPONSE:
        raise ValueError('Invalid pantheon catalog response')
    fields = payload.split(b',')
    if fields and fields[0] == b'not_due':
        if len(fields) != 4:
            raise ValueError('Malformed pantheon not-due response')
        actual_pid = _parse_uint(fields[1], 'player ID', 63)
        actual_turn = _parse_uint(fields[2], 'game turn')
        if (actual_pid, actual_turn) != (pid, turn):
            raise ValueError('Pantheon not-due response is stale or misattributed')
        if fields[3] not in (b'already_has_pantheon', b'cannot_create'):
            raise ValueError('Unknown pantheon not-due reason')
        return {'status': 'not_due', 'reason': fields[3].decode('ascii'), 'player_id': pid, 'current_game_turn': turn}
    if len(fields) < 8 or fields[0] != b'catalog':
        raise ValueError('Malformed pantheon catalog response')
    actual_pid = _parse_uint(fields[1], 'player ID', 63)
    actual_turn = _parse_uint(fields[2], 'game turn')
    operation, key, insert, exclusive = (_parse_uint(token, label) for token, label in zip(fields[3:7], ('operation', 'parameter key', 'insert key', 'exclusive value')))
    count = _parse_uint(fields[7], 'belief count', _MAX_CHOICES)
    if (actual_pid, actual_turn) != (pid, turn):
        raise ValueError('Pantheon catalog is stale or belongs to another player')
    if key == insert or count != len(fields) - 8:
        raise ValueError('Pantheon catalog count/parameter keys are invalid')
    choices, seen_indices, seen_hashes = ([], set(), set())
    previous_index = -1
    for token in fields[8:]:
        pair = token.split(b':')
        if len(pair) != 2:
            raise ValueError('Malformed belief index/hash pair')
        index = _parse_uint(pair[0], 'belief index', 2147483647)
        row_hash = _parse_uint(pair[1], 'belief hash')
        if index <= previous_index or index in seen_indices or row_hash in seen_hashes:
            raise ValueError('Pantheon choices are unordered or ambiguous')
        previous_index = index
        seen_indices.add(index)
        seen_hashes.add(row_hash)
        choices.append({'index': index, 'hash': row_hash})
    return {'status': 'catalog', 'player_id': pid, 'current_game_turn': turn, 'operation': operation, 'parameter_key': key, 'insert_key': insert, 'exclusive_value': exclusive, 'choices': tuple(choices)}

def choose(catalog: dict, selected_index: int) -> dict:
    """Select one exact indexed entry; the request value is its hash, not index."""
    keys = {'status', 'player_id', 'current_game_turn', 'operation', 'parameter_key', 'insert_key', 'exclusive_value', 'choices'}
    if type(catalog) is not dict or set(catalog) != keys or catalog.get('status') != 'catalog':
        raise ValueError('Pantheon catalog is absent or not due')
    for name in ('player_id', 'current_game_turn', 'operation', 'parameter_key', 'insert_key', 'exclusive_value'):
        _uint(catalog[name], name, 63 if name == 'player_id' else 4294967295)
    if catalog['parameter_key'] == catalog['insert_key']:
        raise ValueError('Pantheon parameter keys collide')
    choices = catalog['choices']
    if type(choices) is not tuple or len(choices) > _MAX_CHOICES:
        raise ValueError('Invalid pantheon choice list')
    previous, indices, hashes = (-1, set(), set())
    for item in choices:
        if type(item) is not dict or set(item) != {'index', 'hash'}:
            raise ValueError('Invalid pantheon catalog item')
        _uint(item['index'], 'belief index', 2147483647)
        _uint(item['hash'], 'belief hash')
        if item['index'] <= previous or item['index'] in indices or item['hash'] in hashes:
            raise ValueError('Pantheon catalog is ambiguous')
        previous = item['index']
        indices.add(item['index'])
        hashes.add(item['hash'])
    if type(selected_index) is not int or selected_index < 0 or selected_index > 2147483647:
        raise ValueError('Invalid selected pantheon index')
    matches = [entry for entry in choices if entry['index'] == selected_index]
    if len(matches) != 1:
        raise ValueError('Selected pantheon index is absent or ambiguous')
    selected = matches[0]
    return {'player_id': catalog['player_id'], 'current_game_turn': catalog['current_game_turn'], 'selected_index': selected['index'], 'selected_hash': selected['hash'], 'operation': catalog['operation'], 'parameter_key': catalog['parameter_key'], 'insert_key': catalog['insert_key'], 'exclusive_value': catalog['exclusive_value'], 'parameters': {catalog['parameter_key']: selected['hash'], catalog['insert_key']: catalog['exclusive_value']}}

def _validate_choice(choice: dict) -> None:
    keys = {'player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'operation', 'parameter_key', 'insert_key', 'exclusive_value', 'parameters'}
    if type(choice) is not dict or set(choice) != keys:
        raise ValueError('Invalid selected pantheon choice')
    for name in ('player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'operation', 'parameter_key', 'insert_key', 'exclusive_value'):
        _uint(choice[name], name, 63 if name == 'player_id' else 4294967295)
    if choice['parameter_key'] == choice['insert_key']:
        raise ValueError('Pantheon parameter keys collide')
    _uint(choice['selected_index'], 'selected belief index', 2147483647)
    expected = {choice['parameter_key']: choice['selected_hash'], choice['insert_key']: choice['exclusive_value']}
    params = choice['parameters']
    if type(params) is not dict or len(params) != 2 or any((type(k) is not int or type(v) is not int for k, v in params.items())) or (params != expected):
        raise ValueError('Pantheon request parameters are not exact')

def revalidate_choice_source(choice: dict) -> bytes:
    """Recheck catalog identity and legality immediately before caller submits."""
    _validate_choice(choice)
    verify_source()
    pid = _player_id(choice['player_id'])
    turn = _turn(choice['current_game_turn'])
    index = _uint(choice['selected_index'], 'selected index')
    row_hash = _uint(choice['selected_hash'], 'selected hash')
    fields = (pid, turn, index, row_hash, choice['operation'], choice['parameter_key'], choice['insert_key'], choice['exclusive_value'])
    values = b','.join((str(v).encode('ascii') for v in fields))
    return b'local pid,expectedTurn,expectedIndex,expectedHash,expectedOperation,expectedKey,\n expectedInsert,expectedExclusive=' + values + b'\n' + _common_lua_guards(pid, turn).split(b'\n', 1)[1] + b"\nlocal duePantheon=religion:GetPantheon()\nlocal canCreate=religion:CanCreatePantheon()\nassert(type(duePantheon)=='number' and duePantheon==math.floor(duePantheon) and\n       duePantheon>=-2147483648 and duePantheon<=2147483647 and duePantheon<0 and\n       type(canCreate)=='boolean' and canCreate==true,\n       'pantheon is no longer due')\nassert(PlayerOperations and PlayerOperations.FOUND_PANTHEON~=nil and\n PlayerOperations.PARAM_BELIEF_TYPE~=nil and PlayerOperations.PARAM_INSERT_MODE~=nil and\n PlayerOperations.VALUE_EXCLUSIVE~=nil,'source PlayerOperations enums unavailable')\nlocal function bits(v)\n assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n        'native enum/hash outside signed 32-bit range')\n return v<0 and v+4294967296 or v\nend\nlocal operation=bits(PlayerOperations.FOUND_PANTHEON)\nlocal key=bits(PlayerOperations.PARAM_BELIEF_TYPE)\nlocal insert=bits(PlayerOperations.PARAM_INSERT_MODE)\nlocal exclusive=bits(PlayerOperations.VALUE_EXCLUSIVE)\nassert(operation==expectedOperation and key==expectedKey and insert==expectedInsert and\n       exclusive==expectedExclusive and key~=insert,'pantheon operation enums changed')\nlocal gr=Game.GetReligion()\nassert(gr and type(gr.IsInSomePantheon)=='function' and type(gr.IsInSomeReligion)=='function',\n       'global religion filter unavailable')\nlocal count,found=0,0\nfor row in GameInfo.Beliefs() do\n count=count+1; assert(count<=" + str(_MAX_CHOICES).encode() + b',\n       \'belief revalidation exceeds bound\')\n if row and row.Index==expectedIndex then\n   found=found+1\n   assert(bits(row.Hash)==expectedHash and row.BeliefClassType=="BELIEF_CLASS_PANTHEON",\n          \'selected belief identity changed\')\n   assert(gr:IsInSomePantheon(expectedIndex)==false and\n          gr:IsInSomeReligion(expectedIndex)==false,\'selected belief is no longer available\')\n end\nend\nassert(found==1,\'selected belief index is missing or ambiguous\')\nassert(religion:GetPantheon()==duePantheon and religion:CanCreatePantheon()==true,\n       \'pantheon due-state changed during revalidation\')\nassertContextStillValid()\nlocal function dec(n) return string.format(\'%.0f\',n) end\nreturn table.concat({\'valid\',dec(pid),dec(expectedTurn),dec(expectedIndex),dec(expectedHash),\n dec(operation),dec(key),dec(insert),dec(exclusive)},\',\')\n'

def parse_revalidated_choice(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 256:
        raise ValueError('Invalid pantheon revalidation response')
    fields = payload.split(b',')
    if len(fields) != 9 or fields[0] != b'valid':
        raise ValueError('Malformed pantheon revalidation response')
    actual = tuple((_parse_uint(value, 'revalidated value') for value in fields[1:]))
    expected = tuple((choice[name] for name in ('player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'operation', 'parameter_key', 'insert_key', 'exclusive_value')))
    if actual != expected:
        raise ValueError('Revalidated pantheon choice differs from selection')
    return {'valid': True, 'choice': choice, 'operation': choice['operation'], 'parameters': dict(choice['parameters'])}

def effect_source(choice: dict) -> bytes:
    """Read back founded pantheon; never submits or infers acceptance from request."""
    _validate_choice(choice)
    verify_source()
    pid = _player_id(choice['player_id'])
    turn = _turn(choice['current_game_turn'])
    index = _uint(choice['selected_index'], 'selected index')
    row_hash = _uint(choice['selected_hash'], 'selected hash')
    return b'local pid,expectedTurn,expectedIndex,expectedHash=' + b','.join((str(v).encode('ascii') for v in (pid, turn, index, row_hash))) + b'\n' + _common_lua_guards(pid, turn).split(b'\n', 1)[1] + b"\nlocal actual=religion:GetPantheon()\nassert(type(actual)=='number' and actual==math.floor(actual) and\n       actual>=-2147483648 and actual<=2147483647,'invalid pantheon readback')\nlocal state='pending'\nif actual==expectedIndex then\n local found,row=0,nil\n local scanned=0\n for item in GameInfo.Beliefs() do\n   scanned=scanned+1; assert(scanned<=" + str(_MAX_CHOICES).encode() + b',\n          \'pantheon effect catalog exceeds bound\')\n   if item and item.Index==expectedIndex then found=found+1; row=item end\n end\n assert(found==1 and row and row.BeliefClassType=="BELIEF_CLASS_PANTHEON",\n        \'pantheon readback row is missing or ambiguous\')\n local hash=row.Hash\n assert(type(hash)==\'number\' and hash==math.floor(hash) and\n        hash>=-2147483648 and hash<=2147483647,\'invalid pantheon row hash\')\n local hashBits=hash<0 and hash+4294967296 or hash\n assert(hashBits==expectedHash,\'pantheon readback row/hash mismatch\')\n local gr=Game.GetReligion()\n assert(gr and type(gr.IsInSomePantheon)==\'function\',\'global pantheon reader unavailable\')\n local belongs=gr:IsInSomePantheon(expectedIndex)\n assert(type(belongs)==\'boolean\',\'invalid global pantheon readback\')\n if belongs then state=\'verified\' end\nend\nassert(religion:GetPantheon()==actual,\'pantheon readback changed during verification\')\nassertContextStillValid()\nlocal function dec(n) return string.format(\'%.0f\',n) end\nlocal observed=actual<0 and actual+4294967296 or actual\nreturn table.concat({state,dec(pid),dec(expectedTurn),dec(expectedIndex),\n dec(expectedHash),dec(observed)},\',\')\n'

def parse_effect(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 192:
        raise ValueError('Invalid pantheon effect response')
    fields = payload.split(b',')
    if len(fields) != 6 or fields[0] not in (b'pending', b'verified'):
        raise ValueError('Malformed pantheon effect response')
    actual = tuple((_parse_uint(value, 'pantheon effect field') for value in fields[1:]))
    expected = (choice['player_id'], choice['current_game_turn'], choice['selected_index'], choice['selected_hash'])
    if actual[:4] != expected:
        raise ValueError('Pantheon effect is stale or misattributed')
    observed = actual[4]
    if fields[0] == b'verified' and observed != choice['selected_index']:
        raise ValueError('Verified pantheon value does not match selection')
    return {'status': fields[0].decode('ascii'), 'confirmed': fields[0] == b'verified', 'player_id': actual[0], 'current_game_turn': actual[1], 'selected_index': actual[2], 'selected_hash': actual[3], 'observed_pantheon': observed}

def guard_case() -> bytes:
    """Lua-double guards; they apply no native action or gameplay mutation."""
    catalog = catalog_source(0, 7)
    example = parse_catalog(b'catalog,0,7,4294967195,4294967193,4294967191,4294967190,1,4:2147483648', 0, 7)
    choice = choose(example, 4)
    revalidate = revalidate_choice_source(choice)
    effect = effect_source(choice)
    body = b'local S={pid=0,observer=0,turn=7,alive=true,active=true,complete=true,\n allowStrategic=true,pantheon=-1,canCreate=true,badCanCreate=false,\n badAvailability=false,bumpTurnOnPantheon=false,usedPantheon={},usedReligion={},\n rows={{Index=4,Hash=-2147483648,BeliefClassType="BELIEF_CLASS_PANTHEON"},\n       {Index=5,Hash=77,BeliefClassType="BELIEF_CLASS_FOUNDER"}}}\nlocal function iter(rows) local i=0; return function() i=i+1; return rows[i] end end\nlocal function callable(rows) return setmetatable({}, {__call=function() return iter(rows) end}) end\nGame={GetLocalPlayer=function() return S.pid end,GetLocalObserver=function() return S.observer end,\n GetCurrentGameTurn=function() return S.turn end,\n IsAllowStrategicCommands=function(i)\n  assert(i==0,\'strategic predicate needs the requested player ID\')\n  return S.allowStrategic end,\n GetReligion=function() return {IsInSomePantheon=function(_,i) return S.usedPantheon[i] or false end,\n  IsInSomeReligion=function(_,i) if S.badAvailability then return 0 end; return S.usedReligion[i] or false end} end}\nlocal rel={GetPantheon=function()\n if S.bumpTurnOnPantheon then S.turn=S.turn+1 end\n return S.pantheon end,\n CanCreatePantheon=function() if S.badCanCreate then return 0 end; return S.canCreate end}\nlocal player={IsAlive=function() return S.alive end,IsTurnActive=function() return S.active end,\n IsTurnActiveComplete=function() return S.complete end,GetReligion=function() return rel end}\nPlayers={[0]=player}; GameInfo={Beliefs=callable(S.rows)}\nPlayerOperations={FOUND_PANTHEON=-101,PARAM_BELIEF_TYPE=-103,\n PARAM_INSERT_MODE=-105,VALUE_EXCLUSIVE=-106}\nlocal function runCatalog()\n' + catalog + b'\nend\nlocal function runRevalidate()\n' + revalidate + b'\nend\nlocal function runEffect()\n' + effect + b'\nend\nassert(runCatalog()==\'catalog,0,7,4294967195,4294967193,4294967191,4294967190,1,4:2147483648\')\nS.pantheon=9; assert(runCatalog()==\'not_due,0,7,already_has_pantheon\'); S.pantheon=-1\nS.canCreate=false; assert(runCatalog()==\'not_due,0,7,cannot_create\'); S.canCreate=true\nS.badCanCreate=true; assert(not pcall(runCatalog)); S.badCanCreate=false\nS.usedPantheon[4]=true; assert(runCatalog():match(\',0$\')); S.usedPantheon[4]=false\nS.usedReligion[4]=true; assert(runCatalog():match(\',0$\')); S.usedReligion[4]=false\nS.badAvailability=true; assert(not pcall(runCatalog)); S.badAvailability=false\nS.rows[2]={Index=4,Hash=77,BeliefClassType="BELIEF_CLASS_PANTHEON"}\nassert(not pcall(runCatalog)); S.rows[2]={Index=5,Hash=77,BeliefClassType="BELIEF_CLASS_FOUNDER"}\nassert(runRevalidate()==\'valid,0,7,4,2147483648,4294967195,4294967193,4294967191,4294967190\')\nassert(runEffect()==\'pending,0,7,4,2147483648,4294967295\')\nS.pantheon=4; S.usedPantheon[4]=true\nassert(runEffect()==\'verified,0,7,4,2147483648,4\')\nS.pantheon=-1; S.usedPantheon[4]=false\nS.usedPantheon[4]=true; assert(not pcall(runRevalidate)); S.usedPantheon[4]=false\nS.usedReligion[4]=true; assert(not pcall(runRevalidate)); S.usedReligion[4]=false\nS.turn=8; assert(not pcall(runCatalog) and not pcall(runRevalidate) and not pcall(runEffect)); S.turn=7\nS.pid=1; assert(not pcall(runCatalog)); S.pid=0\nS.observer=1; assert(not pcall(runCatalog)); S.observer=0\nS.alive=false; assert(not pcall(runCatalog)); S.alive=true\nS.active=false; assert(not pcall(runRevalidate)); S.active=true\nS.complete=false; assert(not pcall(runCatalog)); S.complete=true\nS.allowStrategic=false; assert(not pcall(runCatalog) and not pcall(runRevalidate) and not pcall(runEffect)); S.allowStrategic=true\nS.pantheon=3; S.bumpTurnOnPantheon=true; assert(not pcall(runCatalog)); S.bumpTurnOnPantheon=false; S.turn=7; S.pantheon=-1\nS.rows[1].Hash=12; assert(not pcall(runRevalidate)); S.rows[1].Hash=-2147483648\nPlayerOperations.VALUE_EXCLUSIVE=12; assert(not pcall(runRevalidate)); PlayerOperations.VALUE_EXCLUSIVE=-106\nreturn \'pantheon-guards-ok\'\n'
    return b'local saved={Game=Game,Players=Players,GameInfo=GameInfo,\n PlayerOperations=PlayerOperations}\nlocal ok,result=pcall(function()\n' + body + b'\nend)\nGame,Players,GameInfo,PlayerOperations=saved.Game,saved.Players,saved.GameInfo,saved.PlayerOperations\nassert(ok,result)\nreturn result\n'

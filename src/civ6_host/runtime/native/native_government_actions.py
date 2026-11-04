"""Source-pinned catalogue and bounded ordinary government changes.

Anarchy choices remain visible in the catalogue but this first action profile
refuses to submit them; their delayed transition needs its own readback model.
Request success means submitted only. Effect confirmation is a separate query.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import re
import struct
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_government_actions.py')))).resolve().parents[1]
PINNED_EVIDENCE_SHA256 = '9ae32cc01037ebdf5c745fdbca70740f7459215b4922f135831ea0976ca55f4e'
_PROOF = _ROOT / 'evidence/native-government-change' / f'{PINNED_EVIDENCE_SHA256}.json'
_CURRENT_GOVERNMENT_PIN = '47c931dfceda95006c40373234f41bc0b0a5fb93084ddee13eee84d8be897c86'
_CURRENT_GOVERNMENT_PROOF = _ROOT / 'evidence/native-government-consideration' / f'{_CURRENT_GOVERNMENT_PIN}.json'
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_UI_PATH = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\Screens\\GovernmentScreen.lua"))
_UI_SHA256 = '6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'
_MAX_ROWS = 256
_MAX_RESPONSE = 16384
_HASH_MAX = 4294967295
_SIGNED_MAX = 2147483647
_INDEX_MAX = 2147483647
TRANSPORT_PROOF_SHA256 = 'fd48bed2ab139ac100ea820b36570a891587f7c0cf45cc69ae82761bbd408118'
_TRANSPORT_PROOF = _ROOT / 'evidence/native-government-transport' / f'{TRANSPORT_PROOF_SHA256}.json'

def verify_source() -> None:
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    expected = {'CanChangeGovernment': '0x180533680', 'CanChangeGovernmentAtAll': '0x1805336f0', 'IsGovernmentUnlocked': '0x180534e70', 'RequestChangeGovernment': '0x1805350d0', 'GovernmentChangeMade': '0x180534c70', 'GetAnarchyTurns': '0x1805339b0'}
    if proof.get('schema') != 'civ6rl.native_government_change.static.v1' or proof.get('core_sha256') != _CORE_SHA256 or proof.get('exe_sha256') != _EXE_SHA256 or ({name: proof.get('bindings', {}).get(name, {}).get('callback_va') for name in expected} != expected) or (proof.get('packet', {}).get('type') != '0xe57882af') or (proof.get('packet', {}).get('request_values', {}).get('subtype') != 1) or ('index' not in proof.get('contract', {}).get('catalog_identity', '')) or ('CanChangeGovernment(self, selectedHash)' not in proof.get('contract', {}).get('individual_legality', '')) or ('True certifies submission' not in proof.get('contract', {}).get('request_abi', '')) or ('distinct direct/anarchy paths' not in proof.get('contract', {}).get('application', '')) or (hashlib.sha256(_resolve_resource_path(_UI_PATH).read_bytes()).hexdigest() != _UI_SHA256):
        raise RuntimeError('Pinned native government-change source identity changed')
    current_proof = load_pinned_json(_CURRENT_GOVERNMENT_PROOF, _CURRENT_GOVERNMENT_PIN)
    if current_proof.get('schema') != 'civ6rl.native_government_consideration.static.v1' or current_proof.get('core_sha256') != _CORE_SHA256 or current_proof.get('bindings', {}).get('GetCurrentGovernment', {}).get('callback_va') != '0x180533f60':
        raise RuntimeError('Pinned current-government readback identity changed')
    transport = load_pinned_json(_TRANSPORT_PROOF, TRANSPORT_PROOF_SHA256)
    if transport.get('schema') != 'civ6rl.native_government_transport.static.v1' or transport.get('core_sha256') != _CORE_SHA256 or transport.get('exe_sha256') != _EXE_SHA256 or (transport.get('parent', {}).get('sha256') != PINNED_EVIDENCE_SHA256) or (transport.get('packet', {}).get('type') != 3849880239) or (transport.get('packet', {}).get('subtype') != 1) or (transport.get('packet', {}).get('byte_length') != 28) or (transport.get('packet', {}).get('validation_only_not_synthesis') is not True) or (transport.get('vtable_slots', {}).get('outer_receive', {}).get('target_va') != '0x18042e550') or (transport.get('vtable_slots', {}).get('outer_drain', {}).get('target_va') != '0x18042e4d0'):
        raise RuntimeError('Pinned government native transport changed')

def _uint(value: int, label: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _player(value: int) -> int:
    return _uint(value, 'player ID', 63)

def _turn(value: int) -> int:
    return _uint(value, 'turn', 100000)

def _index(value: int) -> int:
    return _uint(value, 'government index', _INDEX_MAX)

def _hash(value: int) -> int:
    if type(value) is not int or not -2147483648 <= value <= _HASH_MAX:
        raise ValueError('Government hash is outside signed/unsigned DWORD range')
    return value

def _source_context(player_id: int, expected_turn: int) -> bytes:
    pid, turn = (_player(player_id), _turn(expected_turn))
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(turn).encode() + b"\nlocal function context()\n assert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n        'government player perspective mismatch')\n assert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n        'government observer perspective mismatch')\n assert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n        'government turn is stale')\n assert(type(Game.IsAllowStrategicCommands)=='function' and Game.IsAllowStrategicCommands(pid)==true,\n        'government strategic commands are not allowed')\n local player=Players and Players[pid]\n assert(player and type(player.IsAlive)=='function' and player:IsAlive()==true and\n        type(player.IsTurnActive)=='function' and player:IsTurnActive()==true and\n        type(player.IsTurnActiveComplete)=='function' and player:IsTurnActiveComplete()==true,\n        'government player is not active and ready')\n local culture=player:GetCulture()\n assert(culture and type(culture.GetCurrentGovernment)=='function' and\n        type(culture.CanChangeGovernmentAtAll)=='function' and\n        type(culture.GovernmentChangeMade)=='function' and\n        type(culture.CivicCompletedThisTurn)=='function' and\n        type(culture.IsGovernmentUnlocked)=='function' and\n        type(culture.CanChangeGovernment)=='function' and\n        type(culture.GetAnarchyTurns)=='function' and\n        type(culture.RequestChangeGovernment)=='function',\n        'government Culture API unavailable')\n local current=culture:GetCurrentGovernment()\n assert(type(current)=='number' and current%1==0 and current>=-1 and current<=2147483647,\n        'invalid current government index')\n local canAll=culture:CanChangeGovernmentAtAll()\n local changed=culture:GovernmentChangeMade()\n local civic=culture:CivicCompletedThisTurn()\n assert(type(canAll)=='boolean' and type(changed)=='boolean' and type(civic)=='boolean',\n        'government global eligibility values must be booleans')\n local strategic=Game.IsAllowStrategicCommands(pid)\n assert(strategic==true,'government strategic command gate changed')\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n        Game.GetCurrentGameTurn()==expectedTurn and player:IsAlive()==true and\n        player:IsTurnActive()==true and player:IsTurnActiveComplete()==true,\n        'government context changed while reading')\n return player,culture,current,canAll,changed,civic\nend\nlocal player,culture,current,canAll,changeMade,civicCompleted=context()\nlocal function rows()\n assert(GameInfo and GameInfo.Governments~=nil and GameInfo.Types~=nil,\n        'government catalog unavailable')\n local all,count,indices,hashes={},0,{},{}\n for row in GameInfo.Governments() do\n  count=count+1\n  assert(count<=" + str(_MAX_ROWS).encode() + b" and row and\n         type(row.Index)=='number' and row.Index%1==0 and row.Index>=0 and row.Index<=2147483647 and\n         type(row.GovernmentType)=='string' and #row.GovernmentType>0,\n         'invalid or excessive government row')\n  local typeRow=GameInfo.Types[row.GovernmentType]\n  assert(typeRow and type(typeRow.Hash)=='number' and typeRow.Hash%1==0 and\n         typeRow.Hash>=-2147483648 and typeRow.Hash<=4294967295,\n         'official government type hash is unavailable')\n  local hash=typeRow.Hash\n  local bits=hash<0 and hash+4294967296 or hash\n  assert(not indices[row.Index] and not hashes[bits],\n         'duplicate government index/hash makes catalog ambiguous')\n  indices[row.Index],hashes[bits]=true,true\n  local unlocked=culture:IsGovernmentUnlocked(hash)\n  local changeable=culture:CanChangeGovernment(hash)\n  local anarchy=culture:GetAnarchyTurns(row.Index)\n  assert(type(unlocked)=='boolean' and type(changeable)=='boolean',\n         'native government unlock/legality results must be booleans')\n  assert(type(anarchy)=='number' and anarchy%1==0 and anarchy>=0 and anarchy<=100000,\n         'native government anarchy turns are invalid')\n  -- Keep the exact signed/unsigned spelling surfaced by GameInfo.Types; use\n  -- DWORD bits only for duplicate detection, never rewrite the request value.\n  all[#all+1]={index=row.Index,hash=hash,unlocked=unlocked,\n               can_change=changeable,anarchy_turns=anarchy}\n end\n assert(count>0 and (current==-1 or indices[current]),'empty government catalog or unknown current index')\n table.sort(all,function(a,b) return a.index<b.index end)\n return all\nend\nlocal governmentRows=rows()\nlocal function contextStable()\n local p,c,g,all,changed,civic=context()\n -- Native GetCulture can return a fresh Lua wrapper for the same player.\n -- Compare the revalidated perspective and state, not wrapper identity.\n assert(g==current and all==canAll and\n        changed==changeMade and civic==civicCompleted,\n        'government state changed during catalog operation')\nend\ncontextStable()\n"

def catalog_source(player_id: int, expected_turn: int) -> bytes:
    verify_source()
    return _source_context(player_id, expected_turn) + b"\nlocal function dec(n) return string.format('%.0f',n) end\nlocal out={'catalog',dec(pid),dec(expectedTurn),dec(current),\n canAll and '1' or '0',changeMade and '1' or '0',civicCompleted and '1' or '0',\n tostring(#governmentRows)}\nfor _,r in ipairs(governmentRows) do\n out[#out+1]=table.concat({dec(r.index),dec(r.hash),r.unlocked and '1' or '0',\n  r.can_change and '1' or '0',dec(r.anarchy_turns)},':')\nend\nreturn table.concat(out,'|')\n"

def _tokens(payload: bytes, label: str) -> list[bytes]:
    if type(payload) is not bytes or len(payload) > _MAX_RESPONSE:
        raise ValueError(f'Invalid {label} wire payload')
    try:
        parts = payload.decode('ascii').split('|')
    except UnicodeDecodeError as exc:
        raise ValueError(f'Non-ASCII {label} wire payload') from exc
    if any((not part for part in parts)):
        raise ValueError(f'Malformed {label} wire payload')
    return [part.encode('ascii') for part in parts]

def _integer(token: bytes, label: str, *, signed: bool=False, maximum: int=4294967295) -> int:
    if not re.fullmatch(b'(?:0|[1-9][0-9]*|-[1-9][0-9]*)', token):
        raise ValueError(f'Invalid {label}')
    value = int(token)
    if value < (-2147483648 if signed else 0) or value > maximum:
        raise ValueError(f'{label} outside source range')
    return value

def parse_catalog(payload: bytes, player_id: int, expected_turn: int) -> dict:
    verify_source()
    pid, turn = (_player(player_id), _turn(expected_turn))
    parts = _tokens(payload, 'government catalog')
    if len(parts) < 8 or parts[0] != b'catalog':
        raise ValueError('Malformed government catalog')
    owner = _integer(parts[1], 'player ID', maximum=63)
    actual_turn = _integer(parts[2], 'turn', maximum=100000)
    current = _integer(parts[3], 'current government', signed=True, maximum=2147483647)
    flags = tuple((_integer(value, 'Boolean') for value in parts[4:7]))
    count = _integer(parts[7], 'government row count', maximum=_MAX_ROWS)
    if owner != pid or actual_turn != turn or current < -1 or any((v not in (0, 1) for v in flags)):
        raise ValueError('Government catalog is stale or has invalid state')
    if count == 0 or len(parts) != 8 + count:
        raise ValueError('Government catalog count differs from rows')
    choices, indices, hashes = ([], set(), set())
    for wire in parts[8:]:
        fields = wire.split(b':')
        if len(fields) != 5:
            raise ValueError('Malformed government row')
        index = _integer(fields[0], 'government index', maximum=2147483647)
        hash_value = _integer(fields[1], 'government hash', signed=True, maximum=4294967295)
        unlocked, can_change = (_integer(v, 'government Boolean') for v in fields[2:4])
        anarchy_turns = _integer(fields[4], 'anarchy turns', maximum=100000)
        bits = hash_value & 4294967295
        if unlocked not in (0, 1) or can_change not in (0, 1):
            raise ValueError('Invalid government flags')
        if index in indices or bits in hashes:
            raise ValueError('Ambiguous duplicate government row')
        indices.add(index)
        hashes.add(bits)
        choices.append({'index': index, 'hash': hash_value, 'unlocked': bool(unlocked), 'can_change': bool(can_change), 'anarchy_turns': anarchy_turns, 'requires_anarchy_path': anarchy_turns > 0})
    if [r['index'] for r in choices] != sorted(indices):
        raise ValueError('Government catalog is not in canonical index order')
    return {'status': 'catalog', 'player_id': pid, 'current_game_turn': turn, 'current_government_index': current, 'can_change_government_at_all': bool(flags[0]), 'government_change_made': bool(flags[1]), 'civic_completed_this_turn': bool(flags[2]), 'choices': tuple(choices)}

def choose(catalog: dict, selected_index: int) -> dict:
    if not isinstance(catalog, dict) or catalog.get('status') != 'catalog':
        raise ValueError('No government catalog to choose from')
    index = _index(selected_index)
    if catalog.get('current_government_index') == index:
        raise ValueError('Current government cannot be selected as a change')
    found = [row for row in catalog.get('choices', ()) if row.get('index') == index]
    if len(found) != 1:
        raise ValueError('Government index is absent or ambiguous')
    row = found[0]
    return {'player_id': _player(catalog.get('player_id')), 'current_game_turn': _turn(catalog.get('current_game_turn')), 'current_government_index': _index(catalog.get('current_government_index')) if catalog.get('current_government_index') != -1 else -1, 'selected_index': index, 'selected_hash': _hash(row.get('hash')), 'unlocked': row.get('unlocked'), 'can_change': row.get('can_change'), 'anarchy_turns': row.get('anarchy_turns'), 'requires_anarchy_path': row.get('requires_anarchy_path')}

def _validate_choice(choice: dict) -> dict:
    if not isinstance(choice, dict):
        raise ValueError('Invalid government choice')
    pid, turn = (_player(choice.get('player_id')), _turn(choice.get('current_game_turn')))
    current = choice.get('current_government_index')
    if type(current) is not int or not -1 <= current <= _SIGNED_MAX:
        raise ValueError('Invalid prior government index')
    index, hash_value = (_index(choice.get('selected_index')), _hash(choice.get('selected_hash')))
    unlocked, can_change = (choice.get('unlocked'), choice.get('can_change'))
    if type(unlocked) is not bool or type(can_change) is not bool:
        raise ValueError('Government eligibility flags are missing')
    anarchy = _uint(choice.get('anarchy_turns'), 'anarchy turns', 100000)
    if choice.get('requires_anarchy_path') is not (anarchy > 0):
        raise ValueError('Government anarchy path flag disagrees with native turns')
    if index == current:
        raise ValueError('Cannot request the current government')
    return {'player_id': pid, 'current_game_turn': turn, 'current_government_index': current, 'selected_index': index, 'selected_hash': hash_value, 'unlocked': unlocked, 'can_change': can_change, 'anarchy_turns': anarchy, 'requires_anarchy_path': anarchy > 0}

def revalidate_choice_source(choice: dict) -> bytes:
    verify_source()
    c = _validate_choice(choice)
    if c['requires_anarchy_path']:
        raise ValueError('Anarchy changes are visible but unsupported by this immediate-effect profile')
    return _source_context(c['player_id'], c['current_game_turn']) + b'\nlocal expectedCurrent,expectedIndex,expectedHash=' + str(c['current_government_index']).encode() + b',' + str(c['selected_index']).encode() + b',' + str(c['selected_hash']).encode() + b'\nlocal rows=governmentRows\nlocal found=nil\nfor _,r in ipairs(rows) do if r.index==expectedIndex then assert(found==nil);found=r end end\nassert(found and found.hash==expectedHash and found.unlocked==' + (b'true' if c['unlocked'] else b'false') + b' and\n found.can_change==' + (b'true' if c['can_change'] else b'false') + b" and found.anarchy_turns==0,\n 'selected government row changed or is not on ordinary path')\nassert(current==expectedCurrent and canAll==true and changeMade==false and\n (current==-1 or civicCompleted==true),'official global government-change gate is closed')\nassert(found.unlocked==true and found.can_change==true,\n 'native government unlock/CanChangeGovernment rejected selection')\ncontextStable()\nreturn table.concat({'valid',string.format('%.0f',pid),string.format('%.0f',expectedTurn),\n string.format('%.0f',current),string.format('%.0f',found.index),\n string.format('%.0f',found.hash),found.unlocked and '1' or '0',\n found.can_change and '1' or '0','0'},'|')\n"

def parse_revalidated_choice(payload: bytes, choice: dict) -> dict:
    c = _validate_choice(choice)
    if c['requires_anarchy_path'] or not c['unlocked'] or (not c['can_change']):
        raise ValueError('Selected government is not admitted by the ordinary change profile')
    fields = _tokens(payload, 'government revalidation')
    if len(fields) != 9 or fields[0] != b'valid':
        raise ValueError('Malformed government revalidation result')
    got = (_integer(fields[1], 'player ID', maximum=63), _integer(fields[2], 'turn', maximum=100000), _integer(fields[3], 'current government', signed=True, maximum=_SIGNED_MAX), _integer(fields[4], 'selected index', maximum=_INDEX_MAX), _integer(fields[5], 'selected hash', signed=True, maximum=_HASH_MAX), _integer(fields[6], 'unlock flag'), _integer(fields[7], 'legality flag'), _integer(fields[8], 'anarchy turns', maximum=100000))
    expected = (c['player_id'], c['current_game_turn'], c['current_government_index'], c['selected_index'], c['selected_hash'], 1, 1, 0)
    if got != expected:
        raise ValueError('Government choice is stale or no longer natively legal')
    return {'valid': True, 'choice': c, 'request_hash': c['selected_hash']}

def request_source(choice: dict) -> bytes:
    """Create the official Culture request; true means submitted, not applied."""
    verify_source()
    c = _validate_choice(choice)
    if c['requires_anarchy_path']:
        raise ValueError('Anarchy changes are visible but unsupported by this immediate-effect profile')
    if not c['unlocked'] or not c['can_change']:
        raise ValueError('Government choice was not natively eligible at catalog time')
    source = revalidate_choice_source(c)
    return source[:source.rfind(b'return table.concat(')] + b"\nlocal accepted=culture:RequestChangeGovernment(expectedHash)\nassert(type(accepted)=='boolean' and accepted==true,\n       'native RequestChangeGovernment did not accept the submitted request')\ncontextStable()\nreturn table.concat({'submitted',string.format('%.0f',pid),\n string.format('%.0f',expectedTurn),string.format('%.0f',current),\n string.format('%.0f',expectedIndex),string.format('%.0f',expectedHash),\n string.format('%.0f',canAll and 1 or 0)},'|')\n"

def parse_request_result(payload: bytes, choice: dict) -> dict:
    c = _validate_choice(choice)
    if c['requires_anarchy_path'] or not c['unlocked'] or (not c['can_change']):
        raise ValueError('Government choice is outside the immediate request profile')
    fields = _tokens(payload, 'government request')
    if len(fields) != 7 or fields[0] != b'submitted':
        raise ValueError('Malformed government request result')
    got = (_integer(fields[1], 'player ID', maximum=63), _integer(fields[2], 'turn', maximum=100000), _integer(fields[3], 'prior government', signed=True, maximum=_SIGNED_MAX), _integer(fields[4], 'government index', maximum=_INDEX_MAX), _integer(fields[5], 'government hash', signed=True, maximum=_HASH_MAX), _integer(fields[6], 'global change gate'))
    expected = (c['player_id'], c['current_game_turn'], c['current_government_index'], c['selected_index'], c['selected_hash'], 1)
    if got != expected:
        raise ValueError('Government request result is stale or mismatched')
    return {'submitted': True, 'choice': c, 'native_rules_used': True, 'effect_confirmed': False}

def validate_native_archive(payload: bytes, choice: dict) -> None:
    """Validate the actual captured archive before native delivery; never create it."""
    verify_source()
    c = _validate_choice(choice)
    if c['requires_anarchy_path'] or not c['unlocked'] or (not c['can_change']):
        raise ValueError('Government archive is outside the direct-change profile')
    expected = struct.pack('<7I', 3849880239, c['player_id'], 1, c['selected_index'], 4294967295, 0, 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Government archive is not the exact source-defined 28-byte request')

def effect_source(choice: dict) -> bytes:
    verify_source()
    c = _validate_choice(choice)
    if c['requires_anarchy_path']:
        raise ValueError('Anarchy effect requires its separate pending-state profile')
    return _source_context(c['player_id'], c['current_game_turn']) + b'\nlocal expectedCurrent,expectedIndex,expectedHash=' + str(c['current_government_index']).encode() + b',' + str(c['selected_index']).encode() + b',' + str(c['selected_hash']).encode() + b"\nassert(current==expectedIndex or current==expectedCurrent,\n       'native government readback is neither prior nor selected government')\nlocal target=nil\nfor _,r in ipairs(governmentRows) do if r.index==expectedIndex then assert(target==nil);target=r end end\nassert(target and target.hash==expectedHash,'selected government identity changed')\nlocal changeMadeNow=culture:GovernmentChangeMade()\nassert(type(changeMadeNow)=='boolean','government change readback is not boolean')\ncontextStable()\nreturn table.concat({'effect',string.format('%.0f',pid),string.format('%.0f',expectedTurn),\n string.format('%.0f',expectedCurrent),string.format('%.0f',expectedIndex),\n string.format('%.0f',expectedHash),string.format('%.0f',current),\n changeMadeNow and '1' or '0'},'|')\n"

def parse_effect(payload: bytes, choice: dict) -> dict:
    c = _validate_choice(choice)
    if c['requires_anarchy_path'] or not c['unlocked'] or (not c['can_change']):
        raise ValueError('Government effect is outside the immediate change profile')
    fields = _tokens(payload, 'government effect')
    if len(fields) != 8 or fields[0] != b'effect':
        raise ValueError('Malformed government effect result')
    got = (_integer(fields[1], 'player ID', maximum=63), _integer(fields[2], 'turn', maximum=100000), _integer(fields[3], 'prior government', signed=True, maximum=_SIGNED_MAX), _integer(fields[4], 'selected government', maximum=_INDEX_MAX), _integer(fields[5], 'government hash', signed=True, maximum=_HASH_MAX), _integer(fields[6], 'current government', signed=True, maximum=_SIGNED_MAX), _integer(fields[7], 'government-change-made flag'))
    if got[:5] != (c['player_id'], c['current_game_turn'], c['current_government_index'], c['selected_index'], c['selected_hash']) or got[6] not in (0, 1):
        raise ValueError('Government effect identity or Boolean is invalid')
    if got[5] not in (c['current_government_index'], c['selected_index']):
        raise ValueError('Government readback is outside the expected transition')
    confirmed = got[5] == c['selected_index'] and got[6] == 1
    return {'confirmed': confirmed, 'current_government_index': got[5], 'government_change_made': bool(got[6]), 'choice': c, 'anarchy_path': False}

def guard_case() -> bytes:
    verify_source()
    catalog = catalog_source(0, 5)
    ordinary = choose({'status': 'catalog', 'player_id': 0, 'current_game_turn': 5, 'current_government_index': 0, 'choices': ({'index': 1, 'hash': 101, 'unlocked': True, 'can_change': True, 'anarchy_turns': 0, 'requires_anarchy_path': False},)}, 1)
    revalidate = revalidate_choice_source(ordinary)
    request = request_source(ordinary)
    effect = effect_source(ordinary)
    return b"local saved={Game=Game,Players=Players,GameInfo=GameInfo}\nlocal ok,result=pcall(function()\n local S={pid=0,observer=0,turn=5,strategic=true,alive=true,active=true,complete=true,\n  current=0,all=true,made=false,civic=true,accepted=true,change=false}\n Game={GetLocalPlayer=function() return S.pid end,GetLocalObserver=function() return S.observer end,\n  GetCurrentGameTurn=function() return S.turn end,\n  IsAllowStrategicCommands=function(pid) assert(pid==0);return S.strategic end}\n local culture={GetCurrentGovernment=function() return S.current end,\n  CanChangeGovernmentAtAll=function() return S.all end,\n  GovernmentChangeMade=function() return S.made end,\n  CivicCompletedThisTurn=function() return S.civic end,\n  IsGovernmentUnlocked=function(_,hash) return hash==101 end,\n  CanChangeGovernment=function(_,hash) return hash==101 and S.change end,\n  GetAnarchyTurns=function(_,index) return index==1 and 0 or 2 end,\n  RequestChangeGovernment=function(_,hash)\n   assert(hash==101 and S.change);if S.accepted then return true end;return false\n  end}\n local player={IsAlive=function() return S.alive end,IsTurnActive=function() return S.active end,\n  IsTurnActiveComplete=function() return S.complete end,GetCulture=function()\n   local wrapper={};for k,v in pairs(culture) do wrapper[k]=v end;return wrapper end}\n Players={[0]=player}\n GameInfo={Governments=function() local i=0;return function()\n   i=i+1;if i==1 then return {Index=0,GovernmentType='GOV_A'}\n   elseif i==2 then return {Index=1,GovernmentType='GOV_B'} end end end,\n  Types={GOV_A={Hash=100},GOV_B={Hash=101}}}\n local function runCatalog()\n" + catalog + b'\n end\n local function runRevalidate()\n' + revalidate + b'\n end\n local function runRequest()\n' + request + b'\n end\n local function runEffect()\n' + effect + b"\n end\n local c=runCatalog()\n assert(c=='catalog|0|5|0|1|0|1|2|0:100:0:0:2|1:101:1:0:0')\n S.change=true\n assert(runRevalidate()=='valid|0|5|0|1|101|1|1|0')\n assert(runRequest()=='submitted|0|5|0|1|101|1')\n S.current=1;S.made=true\n assert(runEffect()=='effect|0|5|0|1|101|1|1')\n S.current=0;S.made=false\n S.pid=1;assert(not pcall(runCatalog) and not pcall(runRequest));S.pid=0\n S.observer=1;assert(not pcall(runCatalog) and not pcall(runRequest));S.observer=0\n S.turn=6;assert(not pcall(runCatalog) and not pcall(runRequest));S.turn=5\n S.alive=false;assert(not pcall(runCatalog) and not pcall(runRequest));S.alive=true\n S.active=false;assert(not pcall(runCatalog) and not pcall(runRequest));S.active=true\n S.complete=false;assert(not pcall(runCatalog) and not pcall(runRequest));S.complete=true\n S.strategic=false;assert(not pcall(runCatalog) and not pcall(runRequest));S.strategic=true\n S.all=false;assert(not pcall(runRequest));S.all=true\n S.made=true;assert(not pcall(runRequest));S.made=false\n S.change=false;assert(not pcall(runRequest));S.change=true\n S.accepted=false;assert(not pcall(runRequest));S.accepted=true\n S.current=2;assert(not pcall(runRequest));S.current=0\n S.current=0;S.made=false\n S.civic=false;assert(not pcall(runRequest));S.civic=true\n local old=GameInfo.Governments\n GameInfo.Governments=function() local i=0;return function()\n  i=i+1;if i==1 then return {Index=0,GovernmentType='GOV_A'}\n  elseif i==2 then return {Index=1,GovernmentType='GOV_B'}\n  elseif i==3 then return {Index=1,GovernmentType='GOV_B'} end end end\n assert(not pcall(runCatalog));GameInfo.Governments=old\n return 'government-action-guards-ok'\nend)\nGame,Players,GameInfo=saved.Game,saved.Players,saved.GameInfo\nassert(ok,result)\nreturn result\n"
__all__ = ['PINNED_EVIDENCE_SHA256', 'verify_source', 'catalog_source', 'parse_catalog', 'choose', 'revalidate_choice_source', 'parse_revalidated_choice', 'request_source', 'parse_request_result', 'effect_source', 'parse_effect', 'guard_case', 'validate_native_archive']

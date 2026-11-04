"""Full catalogs of currently legal research and civic choices.

This module observes choices only. A selected entry still must pass through
native CanStartPlayerOperation and RequestPlayerOperation before submission.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native.native_research_actions import _kind
from civ6_host.runtime.native.native_research_actions import _player_id
from civ6_host.runtime.native.native_research_actions import _uint
from civ6_host.runtime.native.native_research_actions import verify_source

def catalog_source(player_id: int, kind: str, expected_turn: int, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Enumerate every currently legal GameInfo choice for the local player."""
    pid = _player_id(player_id)
    kind_b = _kind(kind)
    turn = _uint(expected_turn, 'expected game turn')
    verify_source(core_sha256=core_sha256)
    table = b'Technologies' if kind == 'research' else b'Civics'
    can_method = b'CanResearch' if kind == 'research' else b'CanProgress'
    manager_method = b'GetTechs' if kind == 'research' else b'GetCulture'
    op_field = b'RESEARCH' if kind == 'research' else b'PROGRESS_CIVIC'
    param_field = b'PARAM_TECH_TYPE' if kind == 'research' else b'PARAM_CIVIC_TYPE'
    return b'local kind="' + kind_b + b'"\nlocal pid,expectedTurn=' + pid + b',' + turn + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n       'research catalog is stale')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,'requested player is not ready')\nassert(PlayerOperations and PlayerOperations." + op_field + b'~=nil and\n       PlayerOperations.' + param_field + b"~=nil and PlayerOperations.PARAM_INSERT_MODE~=nil and\n       PlayerOperations.VALUE_EXCLUSIVE~=nil,'source PlayerOperations enums unavailable')\nlocal manager=player:" + manager_method + b'()\nassert(manager and type(manager.' + can_method + b")=='function','native legality filter unavailable')\nlocal function u32(v,label)\n assert(type(v)=='number' and v==math.floor(v) and v>=0 and v<=4294967295,\n        'invalid uint32 '..label)\n return v\nend\nlocal function signedBits(v,label)\n assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n        'native signed integer out of range '..label)\n return v<0 and v+4294967296 or v\nend\nlocal operation=signedBits(PlayerOperations." + op_field + b",'operation enum')\nlocal parameterKey=signedBits(PlayerOperations." + param_field + b",'parameter enum')\nlocal insertKey=signedBits(PlayerOperations.PARAM_INSERT_MODE,'insert enum')\nlocal exclusive=signedBits(PlayerOperations.VALUE_EXCLUSIVE,'exclusive enum')\nassert(parameterKey~=insertKey,'operation parameter keys collide')\nlocal choices,seenIndex,seenHash={},{},{}\nlocal scanned=0\nfor row in GameInfo." + table + b"() do\n scanned=scanned+1\n assert(scanned<=4096,'GameInfo enumeration exceeds diagnostic bound')\n assert(row and row.Index~=nil and row.Hash~=nil,'incomplete GameInfo row')\n local index=u32(row.Index,'row index')\n local hash=signedBits(row.Hash,'row hash')\n if manager:" + can_method + b"(index)==true then\n   assert(not seenIndex[index] and not seenHash[hash],\n          'duplicate eligible index or hash')\n   seenIndex[index]=true; seenHash[hash]=true\n   choices[#choices+1]={index=index,hash=hash}\n end\nend\ntable.sort(choices,function(a,b) return a.index<b.index end)\nlocal function dec(n) return string.format('%.0f',n) end\nlocal fields={kind,dec(pid),dec(expectedTurn),dec(operation),dec(parameterKey),\n dec(insertKey),dec(exclusive),dec(#choices)}\nfor _,item in ipairs(choices) do\n fields[#fields+1]=dec(item.index)..':'..dec(item.hash)\nend\nreturn table.concat(fields,',')\n"

def _parse_u32(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((c < 48 or c > 57 for c in token)):
        raise ValueError(f'Invalid {label}')
    if len(token) > 1 and token[0] == 48:
        raise ValueError(f'Noncanonical {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'{label} is out of range')
    return value

def parse_catalog(payload: bytes, expected_player: int, kind: str, expected_turn: int) -> dict:
    pid = int(_player_id(expected_player))
    kind_b = _kind(kind)
    turn = int(_uint(expected_turn, 'expected game turn'))
    if type(payload) is not bytes or len(payload) > 131072:
        raise ValueError('Invalid research catalog response')
    fields = payload.split(b',')
    if len(fields) < 8 or fields[0] != kind_b:
        raise ValueError('Malformed research catalog response')
    actual_pid = _parse_u32(fields[1], 'player ID', 63)
    actual_turn = _parse_u32(fields[2], 'game turn')
    operation = _parse_u32(fields[3], 'operation enum')
    parameter_key = _parse_u32(fields[4], 'parameter key')
    insert_key = _parse_u32(fields[5], 'insert key')
    exclusive = _parse_u32(fields[6], 'exclusive mode')
    count = _parse_u32(fields[7], 'choice count', 4096)
    if (actual_pid, actual_turn) != (pid, turn):
        raise ValueError('Research catalog is stale or belongs to another player')
    if parameter_key == insert_key or count != len(fields) - 8:
        raise ValueError('Catalog count or operation parameter keys are invalid')
    choices = []
    seen_indices, seen_hashes = (set(), set())
    previous_index = -1
    for token in fields[8:]:
        pair = token.split(b':')
        if len(pair) != 2:
            raise ValueError('Malformed index/hash choice')
        index = _parse_u32(pair[0], 'choice index')
        row_hash = _parse_u32(pair[1], 'choice hash')
        if index <= previous_index or index in seen_indices or row_hash in seen_hashes:
            raise ValueError('Catalog choices are unsorted or ambiguous')
        previous_index = index
        seen_indices.add(index)
        seen_hashes.add(row_hash)
        choices.append({'index': index, 'hash': row_hash})
    return {'status': 'catalog', 'kind': kind, 'player_id': pid, 'current_game_turn': turn, 'operation': operation, 'parameter_key': parameter_key, 'insert_key': insert_key, 'exclusive_value': exclusive, 'choices': tuple(choices)}

def choose(catalog: dict, selected_index: int) -> dict:
    """Build exact native operation parameters for an explicit catalog choice."""
    expected_keys = {'status', 'kind', 'player_id', 'current_game_turn', 'operation', 'parameter_key', 'insert_key', 'exclusive_value', 'choices'}
    if type(catalog) is not dict or set(catalog) != expected_keys or catalog.get('status') != 'catalog' or (catalog.get('kind') not in ('research', 'civic')):
        raise ValueError('Invalid research catalog')
    for name in ('player_id', 'current_game_turn', 'operation', 'parameter_key', 'insert_key', 'exclusive_value'):
        _uint(catalog[name], name)
    if catalog['player_id'] > 63 or catalog['parameter_key'] == catalog['insert_key']:
        raise ValueError('Invalid catalog owner or parameter keys')
    choices = catalog['choices']
    if type(choices) is not tuple or len(choices) > 4096:
        raise ValueError('Invalid catalog choice list')
    previous = -1
    seen_hashes = set()
    for entry in choices:
        if type(entry) is not dict or set(entry) != {'index', 'hash'}:
            raise ValueError('Invalid catalog entry')
        _uint(entry['index'], 'choice index')
        _uint(entry['hash'], 'choice hash')
        if entry['index'] <= previous or entry['hash'] in seen_hashes:
            raise ValueError('Catalog entries are unordered or ambiguous')
        previous = entry['index']
        seen_hashes.add(entry['hash'])
    if type(selected_index) is not int or not 0 <= selected_index <= 4294967295:
        raise ValueError('Invalid selected row index')
    matches = [item for item in catalog.get('choices', ()) if type(item) is dict and item.get('index') == selected_index]
    if len(matches) != 1:
        raise ValueError('Selected index is absent or ambiguous in current legal catalog')
    item = matches[0]
    return {'kind': catalog['kind'], 'player_id': catalog['player_id'], 'current_game_turn': catalog['current_game_turn'], 'selected_index': item['index'], 'selected_hash': item['hash'], 'operation': catalog['operation'], 'parameter_key': catalog['parameter_key'], 'insert_key': catalog['insert_key'], 'exclusive_value': catalog['exclusive_value'], 'parameters': {catalog['parameter_key']: item['hash'], catalog['insert_key']: catalog['exclusive_value']}}

def _validate_choice(choice: dict) -> None:
    keys = {'kind', 'player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'operation', 'parameter_key', 'insert_key', 'exclusive_value', 'parameters'}
    if type(choice) is not dict or set(choice) != keys or choice.get('kind') not in ('research', 'civic'):
        raise ValueError('Invalid selected research choice')
    for name in ('player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'operation', 'parameter_key', 'insert_key', 'exclusive_value'):
        _uint(choice[name], name)
    if choice['player_id'] > 63 or choice['parameter_key'] == choice['insert_key']:
        raise ValueError('Invalid selected choice owner or parameter keys')
    params = choice['parameters']
    if type(params) is not dict or len(params) != 2 or any((type(k) is not int or type(v) is not int for k, v in params.items())) or (params != {choice['parameter_key']: choice['selected_hash'], choice['insert_key']: choice['exclusive_value']}):
        raise ValueError('Selected choice has invalid parameters')

def revalidate_choice_source(choice: dict, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Recheck the selected choice; no action is submitted by this chunk."""
    _validate_choice(choice)
    kind = choice['kind']
    pid = int(_player_id(choice.get('player_id')))
    turn = int(_uint(choice.get('current_game_turn'), 'expected game turn'))
    index = int(_uint(choice.get('selected_index'), 'selected index'))
    row_hash = int(_uint(choice.get('selected_hash'), 'selected hash'))
    operation = int(_uint(choice.get('operation'), 'operation enum'))
    parameter_key = int(_uint(choice.get('parameter_key'), 'parameter key'))
    insert_key = int(_uint(choice.get('insert_key'), 'insert key'))
    exclusive_value = int(_uint(choice.get('exclusive_value'), 'exclusive value'))
    parameters = choice['parameters']
    verify_source(core_sha256=core_sha256)
    table_name = b'Technologies' if kind == 'research' else b'Civics'
    method = b'CanResearch' if kind == 'research' else b'CanProgress'
    manager_name = b'GetTechs' if kind == 'research' else b'GetCulture'
    op_field = b'RESEARCH' if kind == 'research' else b'PROGRESS_CIVIC'
    param_field = b'PARAM_TECH_TYPE' if kind == 'research' else b'PARAM_CIVIC_TYPE'
    lua_values = b','.join((str(v).encode('ascii') for v in (pid, turn, index, row_hash, operation, parameter_key, insert_key, exclusive_value)))
    return b'local kind="' + kind.encode('ascii') + b'"\nlocal pid,expectedTurn,expectedIndex,expectedHash,expectedOperation,expectedKey,expectedInsert,expectedExclusive=' + lua_values + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n       'native UI perspective is another player')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n       'selected choice is stale')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n       player:IsTurnActiveComplete()==true,'requested player is not ready')\nlocal manager=player:" + manager_name + b'()\nassert(manager and type(manager.' + method + b")=='function','native choice filter unavailable')\nassert(PlayerOperations and PlayerOperations." + op_field + b'~=nil and\n       PlayerOperations.' + param_field + b"~=nil and PlayerOperations.PARAM_INSERT_MODE~=nil and\n       PlayerOperations.VALUE_EXCLUSIVE~=nil,'source PlayerOperations enums unavailable')\nlocal function bits(v)\n assert(type(v)=='number' and v==math.floor(v) and v>=-2147483648 and v<=2147483647,\n        'native signed integer outside bounds')\n return v<0 and v+4294967296 or v\nend\nassert(bits(PlayerOperations." + op_field + b")==expectedOperation,'operation enum changed')\nlocal key=bits(PlayerOperations." + param_field + b")\nlocal insert=bits(PlayerOperations.PARAM_INSERT_MODE)\nlocal exclusive=bits(PlayerOperations.VALUE_EXCLUSIVE)\nassert(key==expectedKey and insert==expectedInsert and exclusive==expectedExclusive and key~=insert,\n       'operation parameter enums changed')\nlocal found,count=0,0\nfor row in GameInfo." + table_name + b"() do\n count=count+1\n assert(count<=4096,'research revalidation catalog exceeds bound')\n if row and row.Index==expectedIndex then\n   found=found+1\n   assert(bits(row.Hash)==expectedHash,'selected row hash changed')\n end\nend\nassert(found==1 and manager:" + method + b"(expectedIndex)==true,\n       'selected technology/civic is no longer legal')\nlocal function dec(n) return string.format('%.0f',n) end\nreturn table.concat({kind,dec(pid),dec(expectedTurn),dec(expectedIndex),dec(expectedHash),\n dec(expectedOperation),dec(key),dec(insert),dec(exclusive)},',')\n"

def parse_revalidated_choice(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    pid = int(_player_id(choice.get('player_id')))
    kind = choice['kind']
    turn = int(_uint(choice.get('current_game_turn'), 'expected game turn'))
    index = int(_uint(choice.get('selected_index'), 'selected index'))
    row_hash = int(_uint(choice.get('selected_hash'), 'selected hash'))
    if type(payload) is not bytes or len(payload) > 160:
        raise ValueError('Invalid revalidation response')
    fields = payload.split(b',')
    if len(fields) != 9 or fields[0] != kind.encode('ascii'):
        raise ValueError('Malformed revalidation response')
    actual = tuple((_parse_u32(token, 'revalidated value') for token in fields[1:]))
    expected = (pid, turn, index, row_hash, choice['operation'], choice['parameter_key'], choice['insert_key'], choice['exclusive_value'])
    if actual != expected:
        raise ValueError('Revalidated choice differs from selection')
    return {'valid': True, 'choice': choice, 'operation': choice['operation'], 'parameters': dict(choice['parameters'])}

def guard_case(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3') -> bytes:
    """Lua-double catalog and stale legality checks, without submission."""
    research = catalog_source(0, 'research', 7, core_sha256=core_sha256)
    civic = catalog_source(0, 'civic', 7, core_sha256=core_sha256)
    sample = parse_catalog(b'research,0,7,4294967195,4294967193,4294967191,4294967190,2,1:4294967295,3:2147483648', 0, 'research', 7)
    revalidation = revalidate_choice_source(choose(sample, 3), core_sha256=core_sha256)
    return b'local S={pid=0,turn=7,alive=true,active=true,complete=true,\n tech={[1]=true,[3]=true},civic={[2]=true,[4]=true}}\nlocal techRows={{Index=3,Hash=-2147483648},{Index=1,Hash=-1},{Index=5,Hash=99}}\nlocal civicRows={{Index=4,Hash=-200},{Index=2,Hash=2147483647}}\nlocal function iterator(rows) local i=0; return function() i=i+1; return rows[i] end end\nlocal function callable(rows) return setmetatable({}, {__call=function() return iterator(rows) end}) end\nlocal Game={GetLocalPlayer=function() return S.pid end,GetCurrentGameTurn=function() return S.turn end}\nlocal techs={CanResearch=function(_,i) return S.tech[i]==true end}\nlocal culture={CanProgress=function(_,i) return S.civic[i]==true end}\nlocal player={IsAlive=function() return S.alive end,IsTurnActive=function() return S.active end,\n IsTurnActiveComplete=function() return S.complete end,GetTechs=function() return techs end,\n GetCulture=function() return culture end}\nlocal Players={[0]=player}\nlocal GameInfo={Technologies=callable(techRows),Civics=callable(civicRows)}\nlocal PlayerOperations={RESEARCH=-101,PROGRESS_CIVIC=-102,PARAM_TECH_TYPE=-103,\n PARAM_CIVIC_TYPE=-104,PARAM_INSERT_MODE=-105,VALUE_EXCLUSIVE=-106}\nlocal function rc()\n' + research + b'\nend\nlocal function cc()\n' + civic + b'\nend\nlocal function revalidate()\n' + revalidation + b"\nend\nassert(rc()=='research,0,7,4294967195,4294967193,4294967191,4294967190,2,1:4294967295,3:2147483648')\nassert(cc()=='civic,0,7,4294967194,4294967192,4294967191,4294967190,2,2:2147483647,4:4294967096')\nassert(revalidate()=='research,0,7,3,2147483648,4294967195,4294967193,4294967191,4294967190')\nS.tech[3]=false; assert(not pcall(revalidate)); S.tech[3]=true\ntechRows[1].Hash=42; assert(not pcall(revalidate)); techRows[1].Hash=-2147483648\nS.turn=8; assert(not pcall(rc) and not pcall(revalidate))\nS.turn=7; S.pid=1; assert(not pcall(cc))\nS.pid=0; S.alive=false; assert(not pcall(rc))\nS.alive=true; S.active=false; assert(not pcall(cc))\nS.active=true; S.complete=false; assert(not pcall(rc))\nS.complete=true; S.tech={}; assert(rc():match(',0$'))\nreturn 'research-catalog-guards-ok'\n"

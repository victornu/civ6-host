"""Source-pinned catalog/revalidation/readback for one ADD_BELIEF choice.

No request is submitted here. Candidate legality is kept in the native
GameReligion filters used by ReligionScreen; the caller must still use the
public native CanStart/RequestPlayerOperation route and drain before readback.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_religion_beliefs.py')))).resolve().parents[1]
PROOF_SHA256 = '976f1275fa303b9d30857e8e91a2b27f84dbf20061e329109c217a449e08be82'
PROOF = ROOT / 'evidence/native-add-belief-actions' / f'{PROOF_SHA256}.json'
RELIGION_PROOF_SHA256 = 'c5f6dd96698059bf7fc4b8c4bf765d4876857f1963d1772657c67866f32609e0'
PANTHEON_PROOF_SHA256 = '6d0db5c53ce5d3daaa74f43abe5d480731e37c6cddb0229a922629a2a08bb73a'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
UI_ROOT = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
RELIGION_SCREEN_SHA256 = '651e758c11f9f7ca31417eaa8b8c25c42ad2a118eb03336c52e9e88a8cf3ab57'
ADD_BELIEF = 4169305636
PARAM_BELIEF_TYPE = 2756389127
PARAM_INSERT_MODE = 2888817673
VALUE_EXCLUSIVE = 2550048198
BELIEF_CLASS_FOLLOWER = 'BELIEF_CLASS_FOLLOWER'
BELIEF_CLASS_PANTHEON = 'BELIEF_CLASS_PANTHEON'
MAX_BELIEFS = 4096
MAX_RELIGIONS = 4096
MAX_RESPONSE = 131072

def verify_source() -> None:
    proof = load_pinned_json(PROOF, PROOF_SHA256)
    religion = load_pinned_json(ROOT / 'evidence/native-religion-founding-actions' / f'{RELIGION_PROOF_SHA256}.json', RELIGION_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_add_belief_actions.static.v1' or proof.get('core_sha256') != CORE_SHA256 or proof.get('exe_sha256') != EXE_SHA256 or (religion.get('schema') != 'civ6rl.native_religion_founding_actions.static.v1') or (religion.get('core_sha256') != CORE_SHA256) or (religion.get('exe_sha256') != EXE_SHA256):
        raise RuntimeError('ADD_BELIEF source image identity changed')
    expected_source_refs = {'religion_founding': RELIGION_PROOF_SHA256, 'pantheon_filters': PANTHEON_PROOF_SHA256}
    for key, expected in expected_source_refs.items():
        if proof.get('source_references', {}).get(key, {}).get('sha256') != expected:
            raise RuntimeError('ADD_BELIEF binding proof reference changed')
    expected_enums = {'PlayerOperations.ADD_BELIEF': (ADD_BELIEF, -125661660), 'PlayerOperations.PARAM_BELIEF_TYPE': (PARAM_BELIEF_TYPE, -1538578169), 'PlayerOperations.PARAM_INSERT_MODE': (PARAM_INSERT_MODE, -1406149623), 'PlayerOperations.VALUE_EXCLUSIVE': (VALUE_EXCLUSIVE, -1744919098)}
    for name, (bits, signed) in expected_enums.items():
        row = religion.get('enums', {}).get(name, {})
        if row.get('bits_u32') != f'0x{bits:08x}' or row.get('signed32') != signed:
            raise RuntimeError(f'ADD_BELIEF PlayerOperations enum changed: {name}')
    binding = proof.get('binding', {})
    literal = binding.get('literal', {})
    if binding.get('name') != 'GameReligion.IsTooManyForReligion' or binding.get('callback_va') != '0x180527ce0' or binding.get('literal_va') != '0x1807bcbe0' or (literal.get('text') != 'IsTooManyForReligion') or (literal.get('va') != '0x1807bcbe0'):
        raise RuntimeError('ADD_BELIEF native class-limit filter binding changed')
    if hashlib.sha256(_resolve_resource_path(UI_ROOT / 'ReligionScreen.lua').read_bytes()).hexdigest() != RELIGION_SCREEN_SHA256:
        raise RuntimeError('Installed ReligionScreen source changed')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _s32(value: int, label: str) -> int:
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError(f'Invalid signed {label}')
    return value

def _parse_uint(raw: bytes, label: str, maximum: int=4294967295) -> int:
    if not raw or any((c < 48 or c > 57 for c in raw)) or (len(raw) > 1 and raw[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(raw)
    if value > maximum:
        raise ValueError(f'Out-of-range {label}')
    return value

def _parse_s32(raw: bytes, label: str) -> int:
    if not raw or raw == b'-0':
        raise ValueError(f'Invalid {label}')
    digits = raw[1:] if raw.startswith(b'-') else raw
    if not digits or any((c < 48 or c > 57 for c in digits)) or (len(digits) > 1 and digits[0] == 48):
        raise ValueError(f'Invalid {label}')
    value = int(raw)
    if not -(1 << 31) <= value < 1 << 31:
        raise ValueError(f'Out-of-range {label}')
    return value

def _pid_turn(player_id: int, expected_turn: int) -> tuple[int, int]:
    return (_uint(player_id, 'player ID', 63), _uint(expected_turn, 'game turn'))

def _context_prefix(player_id: int, expected_turn: int) -> bytes:
    pid, turn = _pid_turn(player_id, expected_turn)
    verify_source()
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(turn).encode() + b"\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n 'belief decision belongs to another player')\nassert(type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n 'belief observer mismatch')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n 'belief decision is stale')\nassert(type(Game.IsAllowStrategicCommands)=='function' and Game.IsAllowStrategicCommands(pid)==true,\n 'strategic commands are not allowed')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'religion player is not ready')\nassert(type(player.GetReligion)=='function','player religion API unavailable')\nlocal religion=player:GetReligion()\nassert(religion and type(religion.GetReligionTypeCreated)=='function' and\n type(religion.GetNumBeliefsEarned)=='function','player belief state getters unavailable')\nlocal religionIndex=religion:GetReligionTypeCreated()\nlocal earned=religion:GetNumBeliefsEarned()\nassert(type(religionIndex)=='number' and religionIndex==math.floor(religionIndex) and\n religionIndex>=0 and religionIndex<=2147483647,'player has no founded religion')\nassert(type(earned)=='number' and earned==math.floor(earned) and\n earned>=0 and earned<=2147483647,'invalid earned belief count')\nassert(type(Game.GetReligion)=='function','global religion API unavailable')\nlocal gameReligion=Game.GetReligion()\nassert(gameReligion and type(gameReligion.GetReligions)=='function' and\n type(gameReligion.IsInSomePantheon)=='function' and\n type(gameReligion.IsInSomeReligion)=='function' and\n type(gameReligion.IsTooManyForReligion)=='function',\n 'native belief availability filters are unavailable')\nlocal all=gameReligion:GetReligions()\nassert(type(all)=='table','founded religion list unavailable')\nlocal function denseLength(values,label,maximum)\n assert(type(values)=='table','invalid '..label)\n local count,highest=0,0\n for key,_ in pairs(values) do\n  assert(type(key)=='number' and key==math.floor(key) and key>=1 and key<=maximum,\n   'invalid '..label..' key')\n  count=count+1;assert(count<=maximum,label..' exceeds bound')\n  if key>highest then highest=key end\n end\n assert(count==highest,'sparse '..label)\n return count\nend\nlocal allCount=denseLength(all,'founded religion list'," + str(MAX_RELIGIONS).encode() + b")\nlocal own,ownCount=nil,0\nfor i=1,allCount do\n local row=all[i]\n assert(type(row)=='table','malformed founded religion row')\n local founder=row.Founder\n assert(type(founder)=='number' and founder==math.floor(founder) and founder>=0 and founder<=63,\n  'malformed religion founder')\n if founder==pid then\n  ownCount=ownCount+1;assert(ownCount==1,'ambiguous own religion row')\n  assert(type(row.Religion)=='number' and row.Religion==math.floor(row.Religion) and\n   row.Religion==religionIndex,'own religion index disagrees with PlayerReligion')\n  own=row\n end\nend\nassert(ownCount==1 and own~=nil,'own founded religion row is missing')\nlocal owned=own.Beliefs\nlocal ownedCount=denseLength(owned,'own religion belief list'," + str(MAX_BELIEFS).encode() + b")\nlocal ownedIndices,ownedSet={},{}\nfor i=1,ownedCount do\n local index=owned[i]\n assert(type(index)=='number' and index==math.floor(index) and index>=0 and\n  index<=2147483647 and not ownedSet[index],'invalid or duplicate own belief index')\n ownedSet[index]=true;ownedIndices[i]=index\nend\nassert(earned>=ownedCount,'equipped beliefs exceed earned beliefs')\nlocal remaining=earned-ownedCount\nlocal operation=PlayerOperations and PlayerOperations.ADD_BELIEF\nlocal beliefKey=PlayerOperations and PlayerOperations.PARAM_BELIEF_TYPE\nlocal insertKey=PlayerOperations and PlayerOperations.PARAM_INSERT_MODE\nlocal exclusive=PlayerOperations and PlayerOperations.VALUE_EXCLUSIVE\nlocal function bits(value,label)\n assert(type(value)=='number' and value==math.floor(value) and\n  value>=-2147483648 and value<=2147483647,'invalid signed '..label)\n return value<0 and value+4294967296 or value\nend\noperation=bits(operation,'operation');beliefKey=bits(beliefKey,'belief parameter')\ninsertKey=bits(insertKey,'insert parameter');exclusive=bits(exclusive,'exclusive value')\nassert(operation==" + str(ADD_BELIEF).encode() + b' and\n beliefKey==' + str(PARAM_BELIEF_TYPE).encode() + b' and\n insertKey==' + str(PARAM_INSERT_MODE).encode() + b' and\n exclusive==' + str(VALUE_EXCLUSIVE).encode() + b",'ADD_BELIEF operation enums changed')\nlocal function context()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n  Game.GetCurrentGameTurn()==expectedTurn,'belief context changed')\n assert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands are no longer allowed')\n local current=Players and Players[pid]\n assert(current and current:IsAlive()==true and current:IsTurnActive()==true and\n  current:IsTurnActiveComplete()==true,'religion player is no longer ready')\nend\ncontext()\n"

def catalog_source(player_id: int, expected_turn: int) -> bytes:
    return _context_prefix(player_id, expected_turn) + b"\nif remaining==0 then\n context();return table.concat({'not_due',string.format('%.0f',pid),\n  string.format('%.0f',expectedTurn),string.format('%.0f',religionIndex),\n  string.format('%.0f',earned),string.format('%.0f',ownedCount),'no_unspent_belief'},',')\nend\nlocal rows,seenIndex,seenHash={}, {}, {}\nlocal scanned=0\nfor row in GameInfo.Beliefs() do\n scanned=scanned+1;assert(scanned<=" + str(MAX_BELIEFS).encode() + b',\'belief catalog exceeds bound\')\n assert(type(row)==\'table\' and type(row.Index)==\'number\' and\n  row.Index==math.floor(row.Index) and row.Index>=0 and row.Index<=2147483647 and\n  type(row.Hash)==\'number\' and row.Hash==math.floor(row.Hash) and\n  row.Hash>=-2147483648 and row.Hash<=2147483647 and\n  type(row.BeliefClassType)==\'string\',\'malformed GameInfo.Beliefs row\')\n local index,hash,class=row.Index,row.Hash,row.BeliefClassType\n assert(#class>0 and #class<=64 and not string.find(class,\'[^A-Z0-9_]\'),\n  \'invalid belief class identifier\')\n local inPantheon=gameReligion:IsInSomePantheon(index)\n local inReligion=gameReligion:IsInSomeReligion(index)\n local tooMany=gameReligion:IsTooManyForReligion(index,religionIndex)\n assert(type(inPantheon)==\'boolean\' and type(inReligion)==\'boolean\' and\n  type(tooMany)==\'boolean\',\'native belief filters returned non-boolean\')\n local classAllowed=(ownedCount==0 and class=="' + BELIEF_CLASS_FOLLOWER.encode() + b'") or\n  (ownedCount>0 and class~="' + BELIEF_CLASS_PANTHEON.encode() + b'")\n if classAllowed and not inPantheon and not inReligion and not tooMany then\n  local hashBits=hash<0 and hash+4294967296 or hash\n  assert(not seenIndex[index] and not seenHash[hashBits],\'duplicate eligible belief row\')\n  seenIndex[index]=true;seenHash[hashBits]=true\n  rows[#rows+1]={index=index,hash=hashBits,class=class}\n end\nend\ntable.sort(rows,function(a,b) return a.index<b.index end)\nassert(religion:GetReligionTypeCreated()==religionIndex and\n religion:GetNumBeliefsEarned()==earned,\'religion slot state changed during catalog\')\ncontext()\nlocal function d(n) return string.format(\'%.0f\',n) end\nlocal fields={\'catalog\',d(pid),d(expectedTurn),d(religionIndex),d(earned),\n d(ownedCount),d(remaining),d(operation),d(beliefKey),d(insertKey),d(exclusive),\n d(#ownedIndices),d(#rows)}\nfor _,index in ipairs(ownedIndices) do fields[#fields+1]=\'o\'..d(index) end\nfor _,row in ipairs(rows) do fields[#fields+1]=\'c\'..d(row.index)..\':\'..d(row.hash)..\':\'..row.class end\nreturn table.concat(fields,\',\')\n'

def _class(value: object) -> str:
    if type(value) is not str or not value or len(value) > 64 or any((ch not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for ch in value)):
        raise ValueError('Invalid belief class')
    return value

def parse_catalog(payload: bytes, player_id: int, expected_turn: int) -> dict:
    pid, turn = _pid_turn(player_id, expected_turn)
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid belief catalog payload')
    fields = payload.split(b',')
    if fields and fields[0] == b'not_due':
        if len(fields) != 7:
            raise ValueError('Malformed not-due belief response')
        values = tuple((_parse_uint(v, 'not-due value') for v in fields[1:6]))
        actual_pid, actual_turn, religion_index, earned, equipped = values
        if (actual_pid, actual_turn) != (pid, turn) or religion_index > 2147483647 or earned > 2147483647 or (equipped > MAX_BELIEFS):
            raise ValueError('Invalid not-due belief counters')
        if earned != equipped:
            raise ValueError('Not-due response still has an unspent belief')
        if fields[6] != b'no_unspent_belief':
            raise ValueError('Unknown belief not-due reason')
        return {'status': 'not_due', 'reason': 'no_unspent_belief', 'player_id': pid, 'current_game_turn': turn, 'religion_index': values[2], 'num_beliefs_earned': values[3], 'equipped_count': values[4], 'candidates': (), 'equipped_beliefs': ()}
    if len(fields) < 13 or fields[0] != b'catalog':
        raise ValueError('Malformed belief catalog')
    values = tuple((_parse_uint(v, 'belief catalog field') for v in fields[1:13]))
    actual_pid, actual_turn, religion_index, earned, equipped, remaining, operation, belief_key, insert_key, exclusive, owned_count, candidate_count = values
    if (actual_pid, actual_turn) != (pid, turn) or religion_index > 2147483647:
        raise ValueError('Stale/foreign religion belief catalog')
    if earned <= equipped or remaining != earned - equipped or owned_count != equipped or (operation != ADD_BELIEF) or (belief_key != PARAM_BELIEF_TYPE) or (insert_key != PARAM_INSERT_MODE) or (exclusive != VALUE_EXCLUSIVE):
        raise ValueError('Belief catalog preconditions or enums differ')
    if len(fields) != 13 + owned_count + candidate_count:
        raise ValueError('Belief catalog item count mismatch')
    owned, candidates, seen_owned, seen_indices, seen_hashes = ([], [], set(), set(), set())
    cursor = 13
    for token in fields[cursor:cursor + owned_count]:
        if not token.startswith(b'o'):
            raise ValueError('Malformed equipped belief entry')
        index = _parse_uint(token[1:], 'equipped belief index', 2147483647)
        if index in seen_owned:
            raise ValueError('Duplicate equipped belief')
        seen_owned.add(index)
        owned.append(index)
    cursor += owned_count
    previous = -1
    for token in fields[cursor:]:
        if not token.startswith(b'c'):
            raise ValueError('Malformed belief candidate')
        parts = token[1:].split(b':')
        if len(parts) != 3:
            raise ValueError('Malformed belief candidate entry')
        index = _parse_uint(parts[0], 'belief index', 2147483647)
        hash_value = _parse_uint(parts[1], 'belief hash')
        try:
            class_name = _class(parts[2].decode('ascii'))
        except UnicodeDecodeError as exc:
            raise ValueError('Non-ASCII belief class') from exc
        if index <= previous or index in seen_indices or hash_value in seen_hashes or (index in seen_owned):
            raise ValueError('Belief candidates are duplicated or unordered')
        if equipped == 0 and class_name != BELIEF_CLASS_FOLLOWER:
            raise ValueError('Initial religion belief is not a follower-class belief')
        if equipped > 0 and class_name == BELIEF_CLASS_PANTHEON:
            raise ValueError('Pantheon-class belief is not an ADD_BELIEF candidate')
        previous = index
        seen_indices.add(index)
        seen_hashes.add(hash_value)
        candidates.append({'index': index, 'hash': hash_value, 'class': class_name})
    if not candidates:
        raise ValueError('No eligible belief candidates in due catalog')
    return {'status': 'catalog', 'player_id': pid, 'current_game_turn': turn, 'religion_index': religion_index, 'num_beliefs_earned': earned, 'equipped_count': equipped, 'remaining_slots': remaining, 'operation': operation, 'belief_parameter': belief_key, 'insert_parameter': insert_key, 'exclusive_value': exclusive, 'equipped_beliefs': tuple(owned), 'candidates': tuple(candidates)}

def choose(catalog: dict, belief_index: int) -> dict:
    keys = {'status', 'player_id', 'current_game_turn', 'religion_index', 'num_beliefs_earned', 'equipped_count', 'remaining_slots', 'operation', 'belief_parameter', 'insert_parameter', 'exclusive_value', 'equipped_beliefs', 'candidates'}
    if type(catalog) is not dict or set(catalog) != keys or catalog.get('status') != 'catalog':
        raise ValueError('No due native belief catalog')
    pid, turn = _pid_turn(catalog['player_id'], catalog['current_game_turn'])
    religion_index = _uint(catalog['religion_index'], 'religion index', 2147483647)
    earned = _uint(catalog['num_beliefs_earned'], 'earned beliefs', 2147483647)
    equipped = _uint(catalog['equipped_count'], 'equipped beliefs', MAX_BELIEFS)
    remaining = _uint(catalog['remaining_slots'], 'remaining slots', MAX_BELIEFS)
    if earned <= equipped or remaining != earned - equipped:
        raise ValueError('No unspent belief slot')
    if (catalog['operation'], catalog['belief_parameter'], catalog['insert_parameter'], catalog['exclusive_value']) != (ADD_BELIEF, PARAM_BELIEF_TYPE, PARAM_INSERT_MODE, VALUE_EXCLUSIVE):
        raise ValueError('Unexpected ADD_BELIEF enums')
    own = catalog['equipped_beliefs']
    if type(own) is not tuple or len(own) != equipped or len(set(own)) != len(own):
        raise ValueError('Malformed equipped-belief snapshot')
    for index in own:
        _uint(index, 'equipped belief index', 2147483647)
    entries = catalog['candidates']
    if type(entries) is not tuple or not 0 < len(entries) <= MAX_BELIEFS:
        raise ValueError('Invalid belief candidates')
    previous = -1
    seen_hashes = set()
    for row in entries:
        if type(row) is not dict or set(row) != {'index', 'hash', 'class'}:
            raise ValueError('Malformed belief candidate')
        index = _uint(row['index'], 'belief index', 2147483647)
        hash_value = _uint(row['hash'], 'belief hash')
        class_name = _class(row['class'])
        if index <= previous or hash_value in seen_hashes or index in own:
            raise ValueError('Duplicate/unordered belief candidates')
        if equipped == 0 and class_name != BELIEF_CLASS_FOLLOWER:
            raise ValueError('Initial religion belief must be follower class')
        if equipped > 0 and class_name == BELIEF_CLASS_PANTHEON:
            raise ValueError('Pantheon belief cannot be added to a religion')
        previous = index
        seen_hashes.add(hash_value)
    selected_index = _uint(belief_index, 'selected belief index', 2147483647)
    matches = [row for row in entries if row['index'] == selected_index]
    if len(matches) != 1:
        raise ValueError('Selected belief is absent or ambiguous')
    row = matches[0]
    return {'player_id': pid, 'current_game_turn': turn, 'religion_index': religion_index, 'num_beliefs_earned': earned, 'equipped_beliefs': own, 'belief_index': selected_index, 'belief_hash': row['hash'], 'belief_class': row['class'], 'operation': ADD_BELIEF, 'parameters': {PARAM_BELIEF_TYPE: row['hash'], PARAM_INSERT_MODE: VALUE_EXCLUSIVE}}

def _validate_choice(choice: dict) -> None:
    required = {'player_id', 'current_game_turn', 'religion_index', 'num_beliefs_earned', 'equipped_beliefs', 'belief_index', 'belief_hash', 'belief_class', 'operation', 'parameters'}
    if type(choice) is not dict or set(choice) != required:
        raise ValueError('Malformed ADD_BELIEF choice')
    _pid_turn(choice['player_id'], choice['current_game_turn'])
    _uint(choice['religion_index'], 'religion index', 2147483647)
    earned = _uint(choice['num_beliefs_earned'], 'earned beliefs', 2147483647)
    own = choice['equipped_beliefs']
    if type(own) is not tuple or len(own) >= earned or len(set(own)) != len(own):
        raise ValueError('No remaining belief slot or malformed own belief list')
    for index in own:
        _uint(index, 'own belief index', 2147483647)
    _uint(choice['belief_index'], 'belief index', 2147483647)
    _uint(choice['belief_hash'], 'belief hash')
    class_name = _class(choice['belief_class'])
    if len(own) == 0 and class_name != BELIEF_CLASS_FOLLOWER or (len(own) > 0 and class_name == BELIEF_CLASS_PANTHEON):
        raise ValueError('Belief class is not admitted by ReligionScreen')
    if _uint(choice['operation'], 'operation') != ADD_BELIEF:
        raise ValueError('Unexpected player operation')
    expected = {PARAM_BELIEF_TYPE: choice['belief_hash'], PARAM_INSERT_MODE: VALUE_EXCLUSIVE}
    if choice['parameters'] != expected:
        raise ValueError('ADD_BELIEF parameters differ from selected GameInfo row')

def request_operation(choice: dict) -> tuple[int, dict[int, int]]:
    """Return exact DWORD parameters for native_player_operation_request; no action occurs here."""
    _validate_choice(choice)
    verify_source()
    return (ADD_BELIEF, dict(choice['parameters']))

def revalidate_source(choice: dict) -> bytes:
    _validate_choice(choice)
    prefix = _context_prefix(choice['player_id'], choice['current_game_turn'])
    expected = (choice['religion_index'], choice['num_beliefs_earned'], choice['belief_index'], choice['belief_hash'], choice['belief_class'], *choice['equipped_beliefs'])
    values = b','.join((str(v).encode() for v in expected[:4]))
    owned_values = b','.join((str(v).encode() for v in expected[5:]))
    return prefix + b'local expectedReligion,expectedEarned,expectedIndex,expectedHash=' + values + b'\nlocal expectedClass="' + expected[4].encode('ascii') + b'"\nlocal expectedOwnedCount=' + str(len(choice['equipped_beliefs'])).encode() + b'\nlocal expectedOwned={' + owned_values + b"}\nassert(remaining>0 and religionIndex==expectedReligion and earned==expectedEarned and\n ownedCount==expectedOwnedCount,'belief slot or religion changed')\nfor i=1,expectedOwnedCount do\n assert(ownedIndices[i]==expectedOwned[i],'own religion beliefs changed')\nend\nlocal found,match=0,nil\nlocal scanned=0\nfor row in GameInfo.Beliefs() do\n scanned=scanned+1;assert(scanned<=" + str(MAX_BELIEFS).encode() + b',\'belief revalidation exceeds bound\')\n if row and row.Index==expectedIndex then found=found+1;match=row end\nend\nassert(found==1 and match and match.Hash>=-2147483648 and match.Hash<=2147483647,\n \'selected belief definition missing or ambiguous\')\nassert(match.BeliefClassType==expectedClass,\'selected belief class changed\')\nlocal hash=match.Hash<0 and match.Hash+4294967296 or match.Hash\nassert(hash==expectedHash,\'selected belief hash changed\')\nassert(expectedClass~="' + BELIEF_CLASS_PANTHEON.encode() + b'" and\n (ownedCount>0 or expectedClass=="' + BELIEF_CLASS_FOLLOWER.encode() + b'"),\n \'selected belief class is no longer permitted\')\nlocal p=gameReligion:IsInSomePantheon(expectedIndex)\nlocal r=gameReligion:IsInSomeReligion(expectedIndex)\nlocal t=gameReligion:IsTooManyForReligion(expectedIndex,religionIndex)\nassert(type(p)==\'boolean\' and type(r)==\'boolean\' and type(t)==\'boolean\' and\n p==false and r==false and t==false,\'native belief availability changed\')\ncontext()\nlocal function d(n) return string.format(\'%.0f\',n) end\nreturn table.concat({\'valid\',d(pid),d(expectedTurn),d(expectedReligion),d(expectedEarned),\n d(expectedIndex),d(expectedHash),d(ownedCount)},\',\')\n'

def parse_revalidated(payload: bytes, choice: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 256:
        raise ValueError('Invalid ADD_BELIEF revalidation response')
    parts = payload.split(b',')
    if len(parts) != 8 or parts[0] != b'valid':
        raise ValueError('Malformed ADD_BELIEF revalidation response')
    actual = tuple((_parse_uint(value, 'revalidated value') for value in parts[1:]))
    expected = (choice['player_id'], choice['current_game_turn'], choice['religion_index'], choice['num_beliefs_earned'], choice['belief_index'], choice['belief_hash'], len(choice['equipped_beliefs']))
    if actual != expected:
        raise ValueError('ADD_BELIEF selection differs from revalidated native state')
    operation, parameters = request_operation(choice)
    return {'valid': True, 'choice': choice, 'operation': operation, 'parameters': parameters}

def effect_source(choice: dict, before_observation: dict) -> bytes:
    _validate_choice(choice)
    required = {'player_id', 'current_game_turn', 'religion_type_created', 'num_beliefs_earned', 'own_religion'}
    if type(before_observation) is not dict or not required <= set(before_observation):
        raise ValueError('Missing pre-ADD_BELIEF observation')
    pid, turn = (choice['player_id'], choice['current_game_turn'])
    own = before_observation['own_religion']
    if before_observation['player_id'] != pid or before_observation['current_game_turn'] != turn or before_observation['religion_type_created'] != choice['religion_index'] or (before_observation['num_beliefs_earned'] != choice['num_beliefs_earned']) or (type(own) is not dict):
        raise ValueError('Stale or mismatched pre-belief snapshot')
    if set(own) != {'religion_index', 'founder', 'belief_indices'}:
        raise ValueError('Malformed own religion snapshot')
    if own['religion_index'] != choice['religion_index'] or own['founder'] != pid:
        raise ValueError('Pre-belief religion does not belong to acting player')
    old = own['belief_indices']
    if type(old) is not list or tuple(old) != choice['equipped_beliefs']:
        raise ValueError('Pre-belief equipped list differs from catalog')
    if choice['belief_index'] in old or len(old) >= choice['num_beliefs_earned']:
        raise ValueError('Belief is already equipped or no slot remains')
    prefix = _context_prefix(pid, turn)
    params = (choice['religion_index'], choice['belief_index'], choice['belief_hash'], choice['num_beliefs_earned'], *old)
    return prefix + b'local expectedReligion,expectedIndex,expectedHash,expectedEarned=' + b','.join((str(v).encode() for v in params[:4])) + b'\nlocal expectedOldCount=' + str(len(old)).encode() + b'\nlocal expectedOld={' + b','.join((str(v).encode() for v in old)) + b"}\nlocal createdNow,earnedNow=religion:GetReligionTypeCreated(),religion:GetNumBeliefsEarned()\nassert(createdNow==expectedReligion,'religion changed before belief readback')\nlocal function ownReligionRow()\n local all=gameReligion:GetReligions()\n local count=denseLength(all,'founded religion list'," + str(MAX_RELIGIONS).encode() + b")\n local own,found= nil,0\n for i=1,count do\n  local entry=all[i]\n  assert(type(entry)=='table' and type(entry.Founder)=='number' and\n   entry.Founder==math.floor(entry.Founder) and entry.Founder>=0 and entry.Founder<=63,\n   'malformed religion founder')\n  if entry.Founder==pid then found=found+1;assert(found==1,'duplicate own religion rows');own=entry end\n end\n assert(own and own.Religion==expectedReligion,'own religion row is missing or changed')\n return own\nend\nlocal row=ownReligionRow()\nlocal beliefs=row.Beliefs\nlocal count=denseLength(beliefs,'own belief list'," + str(MAX_BELIEFS).encode() + b")\nassert(count==expectedOldCount+1 and count<=earnedNow and earnedNow==expectedEarned,\n 'belief slot counters changed unexpectedly')\nlocal present,seen=0,{}\nfor i=1,count do\n local index=beliefs[i]\n assert(type(index)=='number' and index==math.floor(index) and index>=0 and\n  index<=2147483647 and not seen[index],'malformed or duplicate own belief')\n seen[index]=true\n if index==expectedIndex then present=present+1 end\nend\nassert(present==1,'selected belief is absent or duplicated')\nfor i=1,expectedOldCount do assert(seen[expectedOld[i]],'previous own belief disappeared') end\ncontext()\nlocal function d(n) return string.format('%.0f',n) end\nlocal out={'effect',d(pid),d(expectedTurn),d(expectedReligion),d(expectedIndex),\n d(expectedHash),d(expectedEarned),d(count)}\nfor i=1,count do out[#out+1]=d(beliefs[i]) end\nreturn table.concat(out,',')\n"

def parse_effect(payload: bytes, choice: dict, before_observation: dict) -> dict:
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid ADD_BELIEF effect response')
    fields = payload.split(b',')
    if len(fields) < 8 or fields[0] != b'effect':
        raise ValueError('Malformed ADD_BELIEF effect response')
    values = tuple((_parse_uint(v, 'effect field') for v in fields[1:8]))
    pid, turn, religion_index, belief_index, belief_hash, earned, count = values
    if len(fields) != 8 + count:
        raise ValueError('ADD_BELIEF effect count mismatch')
    if (pid, turn, religion_index, belief_index, belief_hash, earned) != (choice['player_id'], choice['current_game_turn'], choice['religion_index'], choice['belief_index'], choice['belief_hash'], choice['num_beliefs_earned']):
        raise ValueError('ADD_BELIEF effect differs from selected choice')
    if type(before_observation) is not dict or before_observation.get('player_id') != pid or before_observation.get('current_game_turn') != turn or (before_observation.get('religion_type_created') != religion_index) or (before_observation.get('num_beliefs_earned') != earned):
        raise ValueError('Pre-belief observation is stale')
    own = before_observation.get('own_religion')
    if type(own) is not dict or own.get('religion_index') != religion_index or own.get('founder') != pid or (type(own.get('belief_indices')) is not list) or (tuple(own['belief_indices']) != choice['equipped_beliefs']):
        raise ValueError('Pre-belief own religion state differs')
    after = tuple((_parse_uint(v, 'own belief index', 2147483647) for v in fields[8:]))
    before = choice['equipped_beliefs']
    if count != len(before) + 1 or len(set(after)) != len(after) or after.count(belief_index) != 1 or any((index not in after for index in before)):
        raise ValueError('Selected belief was not added exactly once')
    return {'belief_added': True, 'religion_index': religion_index, 'belief_index': belief_index, 'belief_hash': belief_hash, 'belief_indices': after, 'beliefs_before': before, 'num_beliefs_earned': earned, 'source_proof_sha256': PROOF_SHA256}

def guard_case() -> bytes:
    """Exercise one belief and the exhausted-slot response in HKS/Lupa."""
    catalog = catalog_source(0, 60)
    mock_catalog = b'catalog,0,60,4,1,0,1,' + str(ADD_BELIEF).encode() + b',' + str(PARAM_BELIEF_TYPE).encode() + b',' + str(PARAM_INSERT_MODE).encode() + b',' + str(VALUE_EXCLUSIVE).encode() + b',0,1,c2:4294967295:BELIEF_CLASS_FOLLOWER'
    parsed = parse_catalog(mock_catalog, 0, 60)
    choice = choose(parsed, 2)
    revalidation = revalidate_source(choice)
    before = {'player_id': 0, 'current_game_turn': 60, 'religion_type_created': 4, 'num_beliefs_earned': 1, 'own_religion': {'religion_index': 4, 'founder': 0, 'belief_indices': []}}
    effect = effect_source(choice, before)
    return b'local currentPlayer,currentObserver,currentTurn=0,0,60\nlocal alive,active,complete,strategic=true,true,true,true\nlocal created,earned=4,1\nlocal religionRows={{Founder=0,Religion=4,Beliefs={}}}\nlocal usedPantheon,usedReligion,tooMany={}, {}, {[4]=true}\nlocal definitions={{Index=1,Hash=-9,BeliefClassType="BELIEF_CLASS_FOUNDER"},\n {Index=2,Hash=-1,BeliefClassType="BELIEF_CLASS_FOLLOWER"},\n {Index=3,Hash=3,BeliefClassType="BELIEF_CLASS_PANTHEON"},\n {Index=4,Hash=4,BeliefClassType="BELIEF_CLASS_FOLLOWER"}}\nlocal religion={GetReligionTypeCreated=function() return created end,\n GetNumBeliefsEarned=function() return earned end}\nlocal player={IsAlive=function() return alive end,IsTurnActive=function() return active end,\n IsTurnActiveComplete=function() return complete end,GetReligion=function() return religion end}\nlocal gameReligion={GetReligions=function() return religionRows end,\n IsInSomePantheon=function(_,i) return usedPantheon[i] or false end,\n IsInSomeReligion=function(_,i) return usedReligion[i] or false end,\n IsTooManyForReligion=function(_,i,r) assert(r==4);return tooMany[i] or false end}\nlocal callable=setmetatable({[1]=definitions[1],[2]=definitions[2],\n [3]=definitions[3],[4]=definitions[4]}, {__call=function()\n local i=0;return function() i=i+1;return definitions[i] end end})\nlocal Players={[0]=player}\nlocal GameInfo={Beliefs=callable}\nlocal Game={GetLocalPlayer=function() return currentPlayer end,\n GetLocalObserver=function() return currentObserver end,\n GetCurrentGameTurn=function() return currentTurn end,\n IsAllowStrategicCommands=function(p) return strategic and p==0 end,\n GetReligion=function() return gameReligion end}\nlocal PlayerOperations={ADD_BELIEF=' + str(ADD_BELIEF if ADD_BELIEF < 2147483648 else ADD_BELIEF - 4294967296).encode() + b',\n PARAM_BELIEF_TYPE=' + str(PARAM_BELIEF_TYPE if PARAM_BELIEF_TYPE < 2147483648 else PARAM_BELIEF_TYPE - 4294967296).encode() + b',\n PARAM_INSERT_MODE=' + str(PARAM_INSERT_MODE if PARAM_INSERT_MODE < 2147483648 else PARAM_INSERT_MODE - 4294967296).encode() + b',\n VALUE_EXCLUSIVE=' + str(VALUE_EXCLUSIVE if VALUE_EXCLUSIVE < 2147483648 else VALUE_EXCLUSIVE - 4294967296).encode() + b"}\nlocal UI={RequestPlayerOperation=function() error('guard must not submit operation') end}\nlocal catalogWire=(function()\n" + catalog + b"\nend)()\nlocal parsed=catalogWire\nassert(parsed:find(',c2:4294967295:BELIEF_CLASS_FOLLOWER',1,true),\n 'native filters or initial follower rule produced unexpected catalog')\nassert(not parsed:find('c1:',1,true) and not parsed:find('c3:',1,true) and\n not parsed:find('c4:',1,true),'native/UI belief filters failed to exclude rows')\nlocal valid=(function()\n" + revalidation + b"\nend)()\nassert(valid=='valid,0,60,4,1,2,4294967295,0')\ncurrentTurn=61\nassert(not pcall(function() (function() " + revalidation + b" end)() end),\n 'stale belief choice accepted')\ncurrentTurn=60;religionRows[1].Beliefs={2};usedReligion[2]=true\nlocal result=(function()\n" + effect + b"\nend)()\nassert(result=='effect,0,60,4,2,4294967295,1,1,2')\nlocal exhaustedWire=(function()\n" + catalog + b"\nend)()\nassert(exhaustedWire=='not_due,0,60,4,1,1,no_unspent_belief',\n 'exhausted belief catalog must preserve its wire separators')\nreturn 'native-add-belief-guard-ok'\n"
__all__ = ['ADD_BELIEF', 'PARAM_BELIEF_TYPE', 'PARAM_INSERT_MODE', 'VALUE_EXCLUSIVE', 'PROOF_SHA256', 'verify_source', 'catalog_source', 'parse_catalog', 'choose', 'request_operation', 'revalidate_source', 'parse_revalidated', 'effect_source', 'parse_effect', 'guard_case']

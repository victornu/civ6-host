"""Complete, free policy assignments through native Culture API requests.

Existing cards may remain in their exact native slots. Every new card must pass
CanSlotPolicy; active-card relocation and paid changes remain unsupported.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_policy_actions.py')))).resolve().parents[1]
_PROOF = _ROOT / 'evidence/native-policy-change-route.json'
_PROOF_SHA256 = '714e21a765c08552b4284c21705623a0ad573622243bc821bea788e840b03645'
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_GOVERNMENT_SCREEN = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\Screens\\GovernmentScreen.lua"))
_GOVERNMENT_SCREEN_SHA256 = '6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'
_SLOT_READBACK_PROOF = _ROOT / 'evidence/native-policy-slot-readback.json'
_SLOT_READBACK_SHA256 = 'f85c5d5e629d1c79ab50968f3eb6e1b4b0ee3bc754d691e77149eac44978144e'
AVAILABILITY_EVIDENCE_SHA256 = '1d70949442f75bf6a57f80396396866188c551f7528d76962b8f8ed39a452be0'
_AVAILABILITY_PROOF = _ROOT / 'evidence/native-policy-availability' / f'{AVAILABILITY_EVIDENCE_SHA256}.json'
TRANSITIONS_EVIDENCE_SHA256 = '53039e04ddf73f2187d5394f17dd2623aca688872d2c18c453de028b64c07d91'
_TRANSITIONS_PROOF = _ROOT / 'evidence/native-policy-transitions' / f'{TRANSITIONS_EVIDENCE_SHA256}.json'

def verify_source() -> None:
    """Verify both native wrapper proof and installed free-policy UI guards."""
    raw = _resolve_resource_path(_PROOF).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROOF_SHA256:
        raise RuntimeError('Pinned policy-change route proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_policy_change_route.static.v1' or proof.get('images', {}).get('core_sha256') != _CORE_SHA256 or proof.get('registrations', {}).get('RequestPolicyChanges', {}).get('callback_va') != '0x180535260' or (proof.get('registrations', {}).get('CanSlotPolicy', {}).get('callback_va') != '0x1805337a0'):
        raise RuntimeError('Unexpected pinned policy-change source identity')
    ui_raw = _resolve_resource_path(_GOVERNMENT_SCREEN).read_bytes()
    if hashlib.sha256(ui_raw).hexdigest() != _GOVERNMENT_SCREEN_SHA256:
        raise RuntimeError('Installed GovernmentScreen.lua changed')
    ui = ui_raw.decode('utf-8-sig')
    required = ('function IsAbleToChangePolicies()', 'kPlayerCulture:CivicCompletedThisTurn() or kPlayerCulture:GetNumPolicySlotsOpen() > 0', 'Game.IsAllowStrategicCommands(m_ePlayer)', 'kPlayerCulture:PolicyChangeMade() == false', 'elseif (iPolicyUnlockCost == 0) then', 'pPlayerCulture:RequestPolicyChanges(clearList, addList)')
    if any((token not in ui for token in required)):
        raise RuntimeError('Installed GovernmentScreen policy guard changed')
    if 'local policyTypeRow' not in ui or 'local policyTypeHash\t:number = policyTypeRow.Hash' not in ui:
        raise RuntimeError('Installed GovernmentScreen policy hash source changed')
    availability = load_pinned_json(_AVAILABILITY_PROOF, AVAILABILITY_EVIDENCE_SHA256)
    if availability.get('schema') != 'civ6rl.native_policy_availability.static.v1' or availability['core_sha256'] != _CORE_SHA256 or availability['registrations']['IsPolicyUnlocked']['callback_va'] != '0x180535010' or (availability['registrations']['IsPolicyObsolete']['callback_va'] != '0x180534fa0'):
        raise RuntimeError('Pinned policy availability source changed')
    action_panel = _GOVERNMENT_SCREEN.parent.parent / 'ActionPanel.lua'
    if hashlib.sha256(_resolve_resource_path(action_panel).read_bytes()).hexdigest() != availability['ui']['action_panel']['sha256']:
        raise RuntimeError('Installed ActionPanel EndTurn gate changed')
    transition = load_pinned_json(_TRANSITIONS_PROOF, TRANSITIONS_EVIDENCE_SHA256)
    if transition.get('schema') != 'civ6rl.native_policy_transitions.static.v1' or transition.get('core_sha256') != _CORE_SHA256 or transition['government_screen']['sha256'] != _GOVERNMENT_SCREEN_SHA256 or (transition['upstream_pins']['native-policy-change-route'] != _PROOF_SHA256) or (transition['upstream_pins']['native-policy-slot-readback'] != _SLOT_READBACK_SHA256) or (transition['upstream_pins']['native-policy-availability'] != AVAILABILITY_EVIDENCE_SHA256):
        raise RuntimeError('Pinned policy transition source changed')

def verify_slot_readback_source() -> None:
    raw = _resolve_resource_path(_SLOT_READBACK_PROOF).read_bytes()
    if _SLOT_READBACK_SHA256 == 'PENDING' or hashlib.sha256(raw).hexdigest() != _SLOT_READBACK_SHA256:
        raise RuntimeError('Pinned GetSlotPolicy source proof changed')
    proof = json.loads(raw)
    contract = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_policy_slot_readback.static.v1' or proof.get('core_sha256') != _CORE_SHA256 or proof.get('registration', {}).get('callback_va') != '0x180534660' or (contract.get('return_type') != 'number') or (contract.get('return_values') != 1):
        raise RuntimeError('Unexpected GetSlotPolicy readback source')

def _uint(value: int, label: str, maximum: int=4294967295) -> bytes:
    if type(value) is not int or value < 0 or value > maximum:
        raise ValueError(f'Invalid {label}')
    return str(value).encode('ascii')

def _player_id(value: int) -> bytes:
    return _uint(value, 'player ID', 63)

def _policy_hash(value: int) -> bytes:
    if type(value) is not int or not -2147483648 <= value <= 4294967295:
        raise ValueError('Invalid policy hash')
    return str(value).encode('ascii')

def _lua_common(player: bytes, turn: bytes) -> bytes:
    return b'local pid,expectedTurn=' + player + b',' + turn + b"\nlocal function baseContext()\n  assert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid,\n         'native UI perspective is another player')\n  assert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n         'policy candidate is stale')\n  assert(type(Game.IsAllowStrategicCommands)=='function' and Game.IsAllowStrategicCommands(pid)==true,\n         'strategic commands are not allowed')\n  local p=Players and Players[pid]\n  assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,\n         'requested player is not ready')\n  local c=p:GetCulture()\n  assert(c and type(c.GetNumPolicySlots)=='function' and type(c.GetSlotPolicy)=='function',\n         'native policy slot API unavailable')\n  local n=c:GetNumPolicySlots()\n  assert(type(n)=='number' and n%1==0 and n>=0 and n<=64,'policy slot count is out of bounds')\n  return c,n\nend\nlocal function context()\n  local c,n=baseContext()\n  assert(c:PolicyChangeMade()==false,'policy changes already submitted')\n  assert(c:GetCostToUnlockPolicies()==0,'policy change is not free')\n  assert(c:CivicCompletedThisTurn()==true or c:GetNumPolicySlotsOpen()>0,\n         'UI policy-change window is closed')\n  assert(n>0,'no policy slots are available')\n  return c,n\nend\nlocal function policyRows()\n  assert(GameInfo and GameInfo.Policies~=nil,'policy catalog unavailable')\n  local rows={}\n  local count=0\n  local indices,bitsSeen={},{}\n  for row in GameInfo.Policies() do\n    count=count+1\n    assert(count<=4096 and row and type(row.Index)=='number' and row.Index%1==0 and\n           row.Index>=0 and row.Index<=4294967295 and type(row.PolicyType)=='string',\n           'invalid or excessive policy catalog')\n    local typeRow=GameInfo.Types and GameInfo.Types[row.PolicyType]\n    assert(typeRow and type(typeRow.Hash)=='number' and typeRow.Hash%1==0 and\n           typeRow.Hash>=-2147483648 and typeRow.Hash<=4294967295,\n           'policy type hash unavailable')\n    local hash=typeRow.Hash\n    local bits=hash<0 and hash+4294967296 or hash\n    assert(type(row.Hash)=='number' and row.Hash%1==0 and\n           row.Hash>=-2147483648 and row.Hash<=4294967295,\n           'policy availability hash unavailable')\n    local availabilityBits=row.Hash<0 and row.Hash+4294967296 or row.Hash\n    assert(availabilityBits==bits,'policy availability and action hashes disagree')\n    assert(not indices[row.Index] and not bitsSeen[bits],'ambiguous native policy catalog')\n    indices[row.Index]=true; bitsSeen[bits]=true\n    rows[#rows+1]={index=row.Index,hash=hash,bits=bits}\n  end\n  assert(#rows>0,'native policy catalog is empty')\n  table.sort(rows,function(a,b) return a.index<b.index end)\n  return rows\nend\nlocal function slotSnapshot(c,n,rows)\n  local byIndex={}\n  for _,row in ipairs(rows) do byIndex[row.index]=row end\n  local prior,active,any={}, {},false\n  for slot=0,n-1 do\n    local index=c:GetSlotPolicy(slot)\n    assert(type(index)=='number' and index%1==0 and index>=-1 and index<=2147483647,\n           'invalid native policy slot occupant')\n    prior[slot]=index\n    if index~=-1 then\n      local row=byIndex[index]\n      assert(row and active[row.bits]==nil,'unknown or duplicate active policy')\n      active[row.bits]=slot\n      any=true\n    end\n  end\n  return prior,active,any\nend\n"

def candidate_source(player_id: int) -> bytes:
    """Choose a complete assignment, retaining valid current cards in-place.

    Result is ``not_due,pid,turn,reason``, ``none,pid,turn``,
    ``unavailable,pid,turn,no_unlocked_policies,catalog_count``, or
    ``pid,turn,count,slot:hash,...`` for an empty baseline, or
    ``replace,pid,turn,count,slot:prior_index:hash,...`` otherwise. Unavailable or
    unchanged never grants EndTurn permission. Slot indices are zero-based.
    """
    pid = _player_id(player_id)
    verify_source()
    return _lua_common(pid, b'Game.GetCurrentGameTurn()') + b"local c,n=baseContext()\nlocal civic=c:CivicCompletedThisTurn()\nlocal open=c:GetNumPolicySlotsOpen()\nlocal changed=c:PolicyChangeMade()\nlocal cost=c:GetCostToUnlockPolicies()\nassert(type(civic)=='boolean' and type(open)=='number' and type(changed)=='boolean' and\n       type(cost)=='number','invalid native policy-window state')\nif n==0 then return 'not_due,'..pid..','..Game.GetCurrentGameTurn()..',no_policy_slots' end\nif changed==true then return 'not_due,'..pid..','..Game.GetCurrentGameTurn()..',already_changed' end\nif cost~=0 then return 'not_due,'..pid..','..Game.GetCurrentGameTurn()..',not_free' end\nif civic~=true and open<=0 then return 'not_due,'..pid..','..Game.GetCurrentGameTurn()..',window_closed' end\nassert(changed==false and (civic==true or open>0),'invalid native policy-window state')\nlocal rows=policyRows()\nlocal prior,active,hasPrior=slotSnapshot(c,n,rows)\nlocal unlockedCount=0\nfor _,row in ipairs(rows) do\n  local unlocked=c:IsPolicyUnlocked(row.hash)\n  local obsolete=c:IsPolicyObsolete(row.hash)\n  assert(type(unlocked)=='boolean' and type(obsolete)=='boolean',\n         'native policy availability must be boolean')\n  if unlocked then unlockedCount=unlockedCount+1 end\n  row.available=unlocked and not obsolete\nend\nif unlockedCount==0 then\n  return 'unavailable,'..string.format('%d',pid)..','..\n         string.format('%d',Game.GetCurrentGameTurn())..',no_unlocked_policies,'..\n         string.format('%d',#rows)\nend\nlocal legalBySlot={}\nfor slot=0,n-1 do\n  legalBySlot[slot]={}\n  -- Native CanSlotPolicy deliberately returns false for active cards. Retain\n  -- only an observed same-slot card, as GovernmentScreen does on confirmation.\n  for _,row in ipairs(rows) do\n    if row.available and prior[slot]==row.index then\n      legalBySlot[slot][1]={bits=row.bits,hash=row.hash,index=row.index}\n    end\n  end\n  for _,row in ipairs(rows) do\n    if row.available and active[row.bits]==nil then\n      local canSlot=c:CanSlotPolicy(row.hash,slot)\n      assert(type(canSlot)=='boolean','native CanSlotPolicy must be boolean')\n      if canSlot then\n        legalBySlot[slot][#legalBySlot[slot]+1]={bits=row.bits,hash=row.hash,index=row.index}\n      end\n    end\n  end\n  if #legalBySlot[slot]==0 then\n    return 'none,'..string.format('%d',pid)..','..string.format('%d',Game.GetCurrentGameTurn())\n  end\nend\nlocal hashOwner={}\nlocal hashValue={}\nlocal hashIndex={}\nlocal function assign(slot,visited)\n  for _,policy in ipairs(legalBySlot[slot]) do\n    if not visited[policy.bits] then\n      visited[policy.bits]=true\n      local owner=hashOwner[policy.bits]\n      if owner==nil or assign(owner,visited) then\n        hashOwner[policy.bits]=slot\n        hashValue[policy.bits]=policy.hash\n        hashIndex[policy.bits]=policy.index\n        return true\n      end\n    end\n  end\n  return false\nend\nfor slot=0,n-1 do\n  if not assign(slot,{}) then\n    return 'none,'..string.format('%d',pid)..','..string.format('%d',Game.GetCurrentGameTurn())\n  end\nend\nlocal assigned={}\nfor bits,slot in pairs(hashOwner) do\n  assigned[slot]={slot=slot,hash=hashValue[bits],index=hashIndex[bits]}\nend\nlocal different=false\nfor slot=0,n-1 do\n  assert(assigned[slot]~=nil,'policy assignment matching is incomplete')\n  if assigned[slot].index~=prior[slot] then different=true end\nend\nif not different then\n  return 'not_due,'..string.format('%d',pid)..','..\n         string.format('%d',Game.GetCurrentGameTurn())..',assignment_unchanged'\nend\nlocal fields={string.format('%d',pid),string.format('%d',Game.GetCurrentGameTurn()),string.format('%d',n)}\nif hasPrior then table.insert(fields,1,'replace') end\nfor slot=0,n-1 do\n  local item=assigned[slot]\n  assert(item~=nil,'policy assignment matching is incomplete')\n  if hasPrior then\n    fields[#fields+1]=string.format('%d:%d:%d',item.slot,prior[slot],item.hash)\n  else\n    fields[#fields+1]=string.format('%d:%d',item.slot,item.hash)\n  end\nend\nreturn table.concat(fields,',')\n"

def _parse_u32(token: bytes, label: str, maximum: int=4294967295) -> int:
    if not token or any((b < 48 or b > 57 for b in token)):
        raise ValueError(f'Invalid {label}')
    if len(token) > 1 and token[0] == 48:
        raise ValueError(f'Noncanonical {label}')
    value = int(token)
    if value > maximum:
        raise ValueError(f'{label} is out of range')
    return value

def _parse_policy_hash(token: bytes) -> int:
    if not token:
        raise ValueError('Invalid policy hash')
    if token[:1] == b'-':
        digits = token[1:]
        if not digits or any((b < 48 or b > 57 for b in digits)):
            raise ValueError('Invalid policy hash')
        if digits == b'0':
            raise ValueError('Noncanonical policy hash')
        if len(digits) > 1 and digits[0] == 48:
            raise ValueError('Noncanonical policy hash')
        value = -int(digits)
    else:
        if any((b < 48 or b > 57 for b in token)):
            raise ValueError('Invalid policy hash')
        if len(token) > 1 and token[0] == 48:
            raise ValueError('Noncanonical policy hash')
        value = int(token)
    if not -2147483648 <= value <= 4294967295:
        raise ValueError('Policy hash is out of range')
    return value

def parse_candidate(payload: bytes, expected_player: int, expected_turn: int | None=None) -> dict | None:
    """Strictly parse the bounded candidate text emitted by candidate_source."""
    pid = int(_player_id(expected_player))
    if type(payload) is not bytes or len(payload) > 3072:
        raise ValueError('Invalid policy candidate response')
    fields = payload.split(b',')
    if len(fields) == 5 and fields[0] == b'unavailable':
        actual_pid = _parse_u32(fields[1], 'player ID', 63)
        turn = _parse_u32(fields[2], 'game turn')
        catalog_count = _parse_u32(fields[4], 'policy catalog count', 4096)
        if actual_pid != pid or catalog_count == 0 or fields[3] != b'no_unlocked_policies' or (expected_turn is not None and turn != _parse_u32(_uint(expected_turn, 'expected turn'), 'expected turn')):
            raise ValueError('Unavailable response is stale, malformed, or for another player')
        return {'status': 'unavailable', 'player_id': actual_pid, 'turn': turn, 'reason': 'no_unlocked_policies', 'catalog_count': catalog_count}
    if len(fields) == 4 and fields[0] == b'not_due':
        actual_pid = _parse_u32(fields[1], 'player ID', 63)
        turn = _parse_u32(fields[2], 'game turn')
        if actual_pid != pid or (expected_turn is not None and turn != _parse_u32(_uint(expected_turn, 'expected turn'), 'expected turn')) or fields[3] not in (b'no_policy_slots', b'already_changed', b'not_free', b'window_closed', b'assignment_unchanged'):
            raise ValueError('Not-due response is stale, malformed, or for another player')
        return {'status': 'not_due', 'player_id': actual_pid, 'turn': turn, 'reason': fields[3].decode('ascii')}
    if len(fields) == 3 and fields[0] == b'none':
        actual_pid = _parse_u32(fields[1], 'player ID', 63)
        turn = _parse_u32(fields[2], 'game turn')
        if actual_pid != pid or (expected_turn is not None and turn != _parse_u32(_uint(expected_turn, 'expected turn'), 'expected turn')):
            raise ValueError('No-candidate response is stale or for another player')
        return {'status': 'none', 'player_id': actual_pid, 'turn': turn}
    replacement = fields[0] == b'replace'
    if replacement:
        fields = fields[1:]
    if len(fields) < 4:
        raise ValueError('Malformed policy candidate response')
    actual_pid = _parse_u32(fields[0], 'player ID', 63)
    turn = _parse_u32(fields[1], 'game turn')
    count = _parse_u32(fields[2], 'slot count', 64)
    if actual_pid != pid or (expected_turn is not None and turn != _parse_u32(_uint(expected_turn, 'expected turn'), 'expected turn')):
        raise ValueError('Policy candidate is stale or for another player')
    if count == 0 or len(fields) != 3 + count:
        raise ValueError('Candidate must cover every policy slot')
    assignments = []
    prior_indices = []
    seen_prior = set()
    used_hashes = set()
    for expected_slot, token in enumerate(fields[3:]):
        pair = token.split(b':')
        if len(pair) != (3 if replacement else 2):
            raise ValueError('Malformed slot/hash assignment')
        slot = _parse_u32(pair[0], 'slot index', 63)
        if replacement:
            prior = -1 if pair[1] == b'-1' else _parse_u32(pair[1], 'prior policy index', 2147483647)
            if prior != -1 and prior in seen_prior:
                raise ValueError('Prior active policy indices must be unique')
            if prior != -1:
                seen_prior.add(prior)
            prior_indices.append(prior)
        policy_hash = _parse_policy_hash(pair[-1])
        if slot != expected_slot or policy_hash & 4294967295 in used_hashes:
            raise ValueError('Slots must be complete and policy hashes unique')
        used_hashes.add(policy_hash & 4294967295)
        assignments.append((slot, policy_hash))
    result = {'status': 'candidate', 'player_id': actual_pid, 'turn': turn, 'slot_count': count, 'assignments': tuple(assignments)}
    if replacement:
        if not seen_prior:
            raise ValueError('Replace profile requires a nonempty prior assignment')
        result['prior_indices'] = tuple(prior_indices)
    return result

def request_source(player_id: int, candidate: dict) -> bytes:
    """Revalidate and submit the candidate through RequestPolicyChanges."""
    pid = int(_player_id(player_id))
    required = {'status', 'player_id', 'turn', 'slot_count', 'assignments'}
    if type(candidate) is not dict or set(candidate) not in (required, required | {'prior_indices'}) or candidate['status'] != 'candidate':
        raise ValueError('Candidate must be a parsed policy candidate')
    if type(candidate['player_id']) is not int or candidate['player_id'] != pid:
        raise ValueError('Candidate belongs to another player')
    turn = int(_uint(candidate['turn'], 'game turn'))
    slot_count = int(_uint(candidate['slot_count'], 'slot count', 64))
    assignments = candidate['assignments']
    if type(assignments) not in (tuple, list) or not 1 <= len(assignments) <= 64 or len(assignments) != slot_count:
        raise ValueError('Candidate must assign every policy slot')
    prior_indices = candidate.get('prior_indices', (-1,) * slot_count)
    if type(prior_indices) not in (tuple, list) or len(prior_indices) != slot_count or any((type(v) is not int or not -1 <= v <= 2147483647 for v in prior_indices)):
        raise ValueError('Invalid candidate prior policy slots')
    occupied = [v for v in prior_indices if v != -1]
    if len(set(occupied)) != len(occupied) or ('prior_indices' in candidate and (not occupied)):
        raise ValueError('Candidate prior policy slots are ambiguous or empty')
    normalized = []
    seen_hashes = set()
    for expected_slot, item in enumerate(assignments):
        if type(item) not in (tuple, list) or len(item) != 2:
            raise ValueError('Invalid policy slot assignment')
        slot = item[0]
        policy_hash = item[1]
        if type(slot) is not int or slot != expected_slot or slot > 63:
            raise ValueError('Policy slots must be complete and zero-based')
        policy_hash_bytes = _policy_hash(policy_hash)
        if policy_hash & 4294967295 in seen_hashes:
            raise ValueError('Policy hashes must be unique')
        seen_hashes.add(policy_hash & 4294967295)
        normalized.append((slot, policy_hash_bytes))
    verify_source()
    prefix = _lua_common(_player_id(pid), _uint(turn, 'game turn'))
    assignment_literals = b','.join((b'{' + str(slot).encode('ascii') + b',' + h + b'}' for slot, h in normalized))
    prior_literals = b','.join((str(index).encode('ascii') for index in prior_indices))
    return prefix + b'local c,n=context()\n    assert(n==' + str(slot_count).encode('ascii') + b",\n       'policy slot count changed since candidate selection')\nlocal rows=policyRows()\nlocal known={}\nfor _,row in ipairs(rows) do known[row.bits]=row end\nlocal prior,active=slotSnapshot(c,n,rows)\nlocal expectedPrior={" + prior_literals + b"}\nfor slot=0,n-1 do\n  assert(prior[slot]==expectedPrior[slot+1],'policy slot occupants changed since candidate selection')\nend\nlocal clearList={}\nlocal addList={}\nlocal seenSlots={}\nlocal seenHashes={}\nlocal different=false\nlocal assignments={" + assignment_literals + b"}\nfor _,item in ipairs(assignments) do\n  local slot,hash=item[1],item[2]\n  local bits=hash<0 and hash+4294967296 or hash\n  assert(slot>=0 and slot<n and not seenSlots[slot] and not seenHashes[bits],\n         'invalid or duplicate candidate assignment')\n  local row=known[bits]\n  assert(row and c:IsPolicyUnlocked(hash)==true and c:IsPolicyObsolete(hash)==false,\n         'native policy legality changed since candidate selection')\n  if prior[slot]~=row.index then\n    assert(active[bits]==nil and c:CanSlotPolicy(hash,slot)==true,\n           'new policy is active elsewhere or native slot legality rejected it')\n    different=true\n  end\n  seenSlots[slot]=true\n  seenHashes[bits]=true\n  clearList[#clearList+1]=slot\n  addList[slot]=hash\nend\nassert(#clearList==n,'candidate does not cover every policy slot')\nassert(different,'unchanged policy assignments must not submit a request')\nfor slot=0,n-1 do\n  assert(c:GetSlotPolicy(slot)==expectedPrior[slot+1],'policy slots changed during validation')\nend\nlocal accepted=c:RequestPolicyChanges(clearList,addList)\nassert(accepted==true,'native RequestPolicyChanges rejected assignment')\nreturn table.concat({'accepted',string.format('%d',pid),\n                     string.format('%d',Game.GetCurrentGameTurn()),\n                     string.format('%d',n)},',')\n"

def parse_request_result(payload: bytes, expected_player: int, expected_turn: int, expected_slots: int) -> dict:
    pid = int(_player_id(expected_player))
    turn = int(_uint(expected_turn, 'expected turn'))
    slots = int(_uint(expected_slots, 'slot count', 64))
    if type(payload) is not bytes or len(payload) > 96:
        raise ValueError('Invalid policy request result')
    fields = payload.split(b',')
    if len(fields) != 4 or fields[0] != b'accepted':
        raise ValueError('Policy request was not accepted')
    actual_pid = _parse_u32(fields[1], 'player ID', 63)
    actual_turn = _parse_u32(fields[2], 'game turn')
    actual_slots = _parse_u32(fields[3], 'slot count', 64)
    if (actual_pid, actual_turn, actual_slots) != (pid, turn, slots):
        raise ValueError('Policy request result does not match candidate')
    return {'accepted': True, 'player_id': pid, 'turn': turn, 'slot_count': slots}

def effect_source(player_id: int, candidate: dict) -> bytes:
    """Read back current slot occupants and verify their policy row indices.

    The source UI treats GetSlotPolicy's numeric result as GameInfo.Policies' row
    index. This is a read-only post-action check; it does not infer acceptance.
    """
    verify_source()
    verify_slot_readback_source()
    pid = int(_player_id(player_id))
    if type(candidate) is not dict or candidate.get('status') != 'candidate' or candidate.get('player_id') != pid or (type(candidate.get('turn')) is not int):
        raise ValueError('Expected a candidate for this player')
    turn = int(_uint(candidate['turn'], 'game turn'))
    assignments = candidate.get('assignments')
    if type(assignments) not in (tuple, list) or not 1 <= len(assignments) <= 64 or candidate.get('slot_count') != len(assignments):
        raise ValueError('Candidate assignment shape is invalid')
    expected = []
    for index, item in enumerate(assignments):
        if type(item) not in (tuple, list) or len(item) != 2 or item[0] != index:
            raise ValueError('Candidate slots are not dense and zero-based')
        expected.append((index, _policy_hash(item[1])))
    prefix = _lua_common(_player_id(pid), _uint(turn, 'game turn'))
    expected_lua = b','.join((b'{' + str(slot).encode('ascii') + b',' + policy_hash + b'}' for slot, policy_hash in expected))
    return prefix + b'local c,n=baseContext()\nassert(n==' + str(len(expected)).encode('ascii') + b",'slot count changed')\nlocal rows=policyRows()\nlocal indexByBits={}\nfor _,row in ipairs(rows) do\n  local bits=row.hash<0 and row.hash+4294967296 or row.hash\n  assert(indexByBits[bits]==nil,'policy catalog hash is ambiguous')\n  indexByBits[bits]=row.index\nend\nlocal expected={" + expected_lua + b"}\nlocal fields={'verified',string.format('%d',pid),string.format('%d',Game.GetCurrentGameTurn()),string.format('%d',n)}\nfor _,item in ipairs(expected) do\n  local slot,hash=item[1],item[2]\n  local bits=hash<0 and hash+4294967296 or hash\n  local expectedIndex=indexByBits[bits]\n  assert(expectedIndex~=nil,'expected policy no longer exists in catalog')\n  local actualIndex=c:GetSlotPolicy(slot)\n  assert(actualIndex==expectedIndex,'native policy slot does not match requested policy')\n  fields[#fields+1]=string.format('%d:%d',slot,actualIndex)\nend\nreturn table.concat(fields,',')\n"

def parse_effect(payload: bytes, expected_player: int, candidate: dict, expected_turn: int | None=None) -> dict:
    pid = int(_player_id(expected_player))
    if type(candidate) is not dict or candidate.get('status') != 'candidate' or candidate.get('player_id') != pid:
        raise ValueError('Expected candidate for effect validation')
    turn = int(_uint(candidate['turn'], 'game turn'))
    if expected_turn is not None and turn != int(_uint(expected_turn, 'expected turn')):
        raise ValueError('Candidate turn mismatch')
    assignments = candidate.get('assignments')
    count = candidate.get('slot_count')
    if type(assignments) not in (tuple, list) or type(count) is not int or len(assignments) != count:
        raise ValueError('Malformed candidate for effect validation')
    if not 1 <= count <= 64:
        raise ValueError('Candidate slot count is out of range')
    seen_hashes = set()
    for index, item in enumerate(assignments):
        if type(item) not in (tuple, list) or len(item) != 2 or type(item[0]) is not int or (item[0] != index) or (type(item[1]) is not int) or (item[1] & 4294967295 in seen_hashes):
            raise ValueError('Candidate assignments are malformed or ambiguous')
        _policy_hash(item[1])
        seen_hashes.add(item[1] & 4294967295)
    if type(payload) is not bytes or len(payload) > 1536:
        raise ValueError('Invalid policy effect response')
    fields = payload.split(b',')
    if len(fields) != 4 + count or fields[0] != b'verified':
        raise ValueError('Malformed policy effect response')
    actual_pid = _parse_u32(fields[1], 'player ID', 63)
    actual_turn = _parse_u32(fields[2], 'game turn')
    actual_count = _parse_u32(fields[3], 'slot count', 64)
    if (actual_pid, actual_turn, actual_count) != (pid, turn, count):
        raise ValueError('Policy effect response is stale or mismatched')
    readback = []
    seen_indices = set()
    for index, token in enumerate(fields[4:]):
        pair = token.split(b':')
        if len(pair) != 2:
            raise ValueError('Malformed policy slot readback')
        slot = _parse_u32(pair[0], 'slot index', 63)
        row_index = _parse_u32(pair[1], 'policy row index')
        if slot != index or row_index in seen_indices:
            raise ValueError('Unexpected policy slot readback')
        seen_indices.add(row_index)
        readback.append((slot, row_index))
    return {'verified': True, 'player_id': pid, 'turn': turn, 'readback': tuple(readback)}

def guard_case() -> bytes:
    """Exercise candidate and request Lua with strict test doubles only."""
    return b"local S={pid=0,turn=4,alive=true,active=true,complete=true,strategy=true,\n cost=0,changed=false,civic=true,open=2,filled={[-1]=true},accepted=true,\n unlocked={[101]=true,[202]=true},obsolete={},legal={[0]={101},[1]={202}},submitted=0,\n partial=false,slotcount=2}\nlocal function iterator(rows) local i=0; return function() i=i+1; return rows[i] end end\nlocal policyRows={{Index=0,Hash=101,PolicyType='POLICY_A'},{Index=1,Hash=202,PolicyType='POLICY_B'}}\nlocal culture={\n GetNumPolicySlots=function() return S.slotcount end,\n GetSlotPolicy=function(_,i)\n   if S.slots then return S.slots[i] end\n   if S.partial and i==1 then return 101 end\n   return -1\n end,\n PolicyChangeMade=function() return S.changed end,\n GetCostToUnlockPolicies=function() return S.cost end,\n CivicCompletedThisTurn=function() return S.civic end,\n GetNumPolicySlotsOpen=function() return S.open end,\n IsPolicyUnlocked=function(_,h)\n   assert(h==101 or h==202 or h==303,'availability received a row index instead of hash')\n   if S.invalidBoolean then return nil end\n   return S.unlocked[h]==true\n end,\n IsPolicyObsolete=function(_,h) return S.obsolete[h]==true end,\n CanSlotPolicy=function(_,h,slot)\n   if S.slots then\n     for _,index in pairs(S.slots) do\n       for _,row in ipairs(policyRows) do\n         if row.Index==index and row.Hash==h then return false end\n       end\n     end\n   end\n   for _,legal in ipairs(S.legal[slot] or {}) do if h==legal then return true end end\n   return false\n end,\n RequestPolicyChanges=function(_,clear,add)\n   assert(#clear==2 and clear[1]==0 and clear[2]==1 and\n          add[0]==(S.expectedFirst or 101) and add[1]==202)\n   assert(S.alive and S.active and S.complete and S.strategy and S.cost==0 and\n          not S.changed and S.civic and not S.partial)\n   S.submitted=S.submitted+1\n   return S.accepted\n end}\nlocal player={IsAlive=function() return S.alive end,IsTurnActive=function() return S.active end,\n IsTurnActiveComplete=function() return S.complete end,GetCulture=function() return culture end}\nlocal Players={[0]=player}\nlocal Game={GetLocalPlayer=function() return S.pid end,GetCurrentGameTurn=function() return S.turn end,\n IsAllowStrategicCommands=function(pid) assert(pid==S.pid); return S.strategy end}\nlocal policies=setmetatable({}, {__call=function() return iterator(policyRows) end})\nlocal GameInfo={Policies=policies,\n Types={POLICY_A={Hash=101},POLICY_B={Hash=202}}}\nlocal function candidate()\n" + candidate_source(0) + b'end\nlocal function request()\n' + request_source(0, {'status': 'candidate', 'player_id': 0, 'turn': 4, 'slot_count': 2, 'assignments': ((0, 101), (1, 202))}) + b'end\nlocal function partialRequest()\n' + request_source(0, {'status': 'candidate', 'player_id': 0, 'turn': 4, 'slot_count': 2, 'assignments': ((0, 101), (1, 202)), 'prior_indices': (0, -1)}) + b'end\nlocal function unchangedRequest()\n' + request_source(0, {'status': 'candidate', 'player_id': 0, 'turn': 4, 'slot_count': 2, 'assignments': ((0, 101), (1, 202)), 'prior_indices': (0, 1)}) + b'end\nlocal function relocateActiveRequest()\n' + request_source(0, {'status': 'candidate', 'player_id': 0, 'turn': 4, 'slot_count': 2, 'assignments': ((0, 202), (1, 101)), 'prior_indices': (0, 1)}) + b'end\nlocal function replacementRequest()\n' + request_source(0, {'status': 'candidate', 'player_id': 0, 'turn': 4, 'slot_count': 2, 'assignments': ((0, 303), (1, 202)), 'prior_indices': (0, 1)}) + b"end\nlocal value=candidate()\nassert(value=='0,4,2,0:101,1:202' and S.submitted==0)\nassert(request()=='accepted,0,4,2' and S.submitted==1)\nS.turn=5; assert(not pcall(request) and S.submitted==1)\nS.turn=4; S.pid=1; assert(not pcall(candidate) and not pcall(request) and S.submitted==1)\nS.pid=0; S.alive=false; assert(not pcall(candidate) and not pcall(request))\nS.alive=true; S.active=false; assert(not pcall(candidate) and not pcall(request))\nS.active=true; S.complete=false; assert(not pcall(candidate) and not pcall(request))\nS.complete=true; S.strategy=false; assert(not pcall(candidate) and not pcall(request))\nS.strategy=true; S.cost=1\nassert(candidate()=='not_due,0,4,not_free' and not pcall(request) and S.submitted==1)\nS.cost=0; S.changed=true\nassert(candidate()=='not_due,0,4,already_changed' and not pcall(request) and S.submitted==1)\nS.changed=false; S.civic=false; S.open=0\nassert(candidate()=='not_due,0,4,window_closed' and not pcall(request) and S.submitted==1)\nS.civic=true; S.open=2; S.partial=true\nassert(not pcall(candidate) and not pcall(request) and S.submitted==1)\nS.partial=false; S.accepted=false\nassert(not pcall(request) and S.submitted==2)\nS.accepted=true; S.civic=false; S.unlocked={}\nassert(candidate()=='unavailable,0,4,no_unlocked_policies,2' and S.submitted==2)\nassert(not pcall(request) and S.submitted==2)\nS.invalidBoolean=true; assert(not pcall(candidate)); S.invalidBoolean=false\npolicyRows[1].Hash=0; assert(not pcall(candidate)); policyRows[1].Hash=101\nS.unlocked={[101]=true,[202]=true}; S.obsolete={[101]=true,[202]=true}\nassert(candidate()=='none,0,4' and S.submitted==2)\nS.obsolete={}; S.legal={[0]={101},[1]={101}}\nassert(candidate()=='none,0,4' and S.submitted==2)\nS.legal={[0]={101},[1]={202}}\nassert(candidate()=='0,4,2,0:101,1:202' and S.submitted==2)\n-- Active cards return false from the native-style CanSlotPolicy double. They\n-- are retained only by their observed same-slot row identity.\nS.slots={[0]=0,[1]=-1}; S.open=1; S.civic=true\nassert(culture:CanSlotPolicy(101,0)==false)\nassert(candidate()=='replace,0,4,2,0:0:101,1:-1:202' and S.submitted==2)\nassert(not pcall(request) and S.submitted==2) -- legacy empty baseline is stale\nassert(partialRequest()=='accepted,0,4,2' and S.submitted==3)\nS.slots={[0]=0,[1]=1}; S.open=0; S.civic=true\nassert(candidate()=='not_due,0,4,assignment_unchanged' and S.submitted==3)\nassert(not pcall(partialRequest) and not pcall(unchangedRequest) and S.submitted==3)\nassert(not pcall(relocateActiveRequest) and S.submitted==3)\n-- Replace an obsolete occupant with a native-legal inactive card while\n-- retaining the other occupant; request acceptance still is not readback.\npolicyRows[3]={Index=2,Hash=303,PolicyType='POLICY_C'}\nGameInfo.Types.POLICY_C={Hash=303}; S.unlocked[303]=true\nS.obsolete[101]=true; S.legal[0]={303}; S.expectedFirst=303\nassert(candidate()=='replace,0,4,2,0:0:303,1:1:202' and S.submitted==3)\nassert(replacementRequest()=='accepted,0,4,2' and S.submitted==4)\nS.legal[0]={}; assert(candidate()=='none,0,4')\nassert(not pcall(replacementRequest) and S.submitted==4)\nS.legal[0]={303}; S.slots[1]=0\nassert(not pcall(candidate) and not pcall(replacementRequest) and S.submitted==4)\nS.slots[1]=1234; assert(not pcall(candidate) and S.submitted==4)\nS.slots[1]=1; policyRows[3].Index=1\nassert(not pcall(candidate) and S.submitted==4)\npolicyRows[3].Index=2; policyRows[3].Hash=202; GameInfo.Types.POLICY_C.Hash=202\nassert(not pcall(candidate) and S.submitted==4)\nreturn 'native-policy-action-guards-ok'\n"

"""Read native free policy options without choosing an assignment for the caller.

The mask is factorized by slot. The complete caller assignment must also be
unique, fill every slot and differ from the current one. Active-card relocation
and paid unlocks are explicitly outside this adapter's contract.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.contracts.policies import choose, validate_slots
from civ6_host.runtime.native import native_policy_actions as native
REASONS = ('available', 'no_policy_slots', 'already_changed', 'not_free', 'window_closed')

def catalog_source(player_id, turn):
    native.verify_source()
    native.verify_slot_readback_source()
    return native._lua_common(native._player_id(player_id), native._uint(turn, 'turn')) + b"\nassert(Game.GetLocalObserver()==pid,'policy observer differs')\nlocal c,n=baseContext()\nlocal civic,open,changed,cost=c:CivicCompletedThisTurn(),c:GetNumPolicySlotsOpen(),c:PolicyChangeMade(),c:GetCostToUnlockPolicies()\nassert(type(civic)=='boolean' and type(changed)=='boolean' and type(open)=='number' and\n open%1==0 and open>=0 and open<=n and type(cost)=='number' and cost>=0 and cost<math.huge,'invalid policy window')\nlocal reason='available'\nif n==0 then reason='no_policy_slots'\nelseif changed then reason='already_changed'\nelseif cost~=0 then reason='not_free'\nelseif not civic and open==0 then reason='window_closed' end\nlocal rows=policyRows()\nlocal prior,active=slotSnapshot(c,n,rows)\nfor _,row in ipairs(rows) do\n local info=GameInfo.Policies[row.index]\n assert(info and info.Index==row.index and type(info.PolicyType)=='string' and\n #info.PolicyType<=128 and info.PolicyType:match('^POLICY_[A-Z0-9_]+$'),'invalid policy identity')\n row.policy_type=info.PolicyType\n if reason=='available' then\n  local unlocked,obsolete=c:IsPolicyUnlocked(row.hash),c:IsPolicyObsolete(row.hash)\n  assert(type(unlocked)=='boolean' and type(obsolete)=='boolean','invalid policy availability')\n  row.available=unlocked and not obsolete\n end\nend\nlocal function dec(v) return string.format('%.0f',v) end\nlocal out={table.concat({dec(pid),dec(expectedTurn),reason,dec(n)},'|')}\nlocal relations=0\nfor slot=0,n-1 do\n local options={}\n if reason=='available' then\n  for _,row in ipairs(rows) do\n   local legal=false\n   if row.available then\n    if prior[slot]==row.index then legal=true\n    elseif active[row.bits]==nil then\n     legal=c:CanSlotPolicy(row.hash,slot)\n     assert(type(legal)=='boolean','invalid slot legality')\n    end\n   end\n   if legal then\n    relations=relations+1;assert(relations<=8192,'policy options exceed diagnostic bound')\n    options[#options+1]=table.concat({dec(row.index),dec(row.bits),dec(row.hash),row.policy_type},':')\n   end\n  end\n end\n out[#out+1]=table.concat({dec(slot),dec(prior[slot]),table.concat(options,',')},'|')\nend\nfor slot=0,n-1 do assert(c:GetSlotPolicy(slot)==prior[slot],'policy slots changed during read') end\nlocal result=table.concat(out,'\\n')\nassert(#result<=524288,'policy catalogue exceeds diagnostic bound')\nreturn result\n"

def parse_catalog(raw, player_id, turn):
    pid = int(native._player_id(player_id))
    expected = int(native._uint(turn, 'turn'))
    if type(raw) is not bytes or len(raw) > 524288:
        raise ValueError('Invalid policy catalogue size')
    lines = raw.split(b'\n')
    head = lines[0].split(b'|')
    if len(head) != 4:
        raise ValueError('Malformed policy catalogue header')
    actual = native._parse_u32(head[0], 'player ID', 63)
    seen_turn = native._parse_u32(head[1], 'turn')
    count = native._parse_u32(head[3], 'slot count', 64)
    reason = head[2].decode('ascii')
    if actual != pid or seen_turn != expected or reason not in REASONS or (len(lines) != count + 1) or ((reason == 'no_policy_slots') != (count == 0)):
        raise ValueError('Foreign or malformed policy catalogue')
    slots = []
    for line in lines[1:]:
        parts = line.split(b'|')
        if len(parts) != 3:
            raise ValueError('Malformed policy slot row')
        slot = native._parse_u32(parts[0], 'slot', 63)
        prior = -1 if parts[1] == b'-1' else native._parse_u32(parts[1], 'prior index', 2147483647)
        options = []
        for token in parts[2].split(b',') if parts[2] else []:
            row = token.split(b':')
            if len(row) != 4:
                raise ValueError('Malformed policy option')
            options.append(dict(index=native._parse_u32(row[0], 'policy index', 2147483647), hash=native._parse_u32(row[1], 'policy hash'), native_hash=native._parse_policy_hash(row[2]), policy_type=row[3].decode('ascii')))
        if reason != 'available' and options:
            raise ValueError('Closed policy window offers choices')
        slots.append(dict(slot=slot, prior_index=prior, options=options))
    return validate_catalog(dict(player_id=pid, turn=expected, reason=reason, slots=slots), pid, expected)

def validate_catalog(value, player_id, turn):
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'reason', 'slots'} or type(value['player_id']) is not int or (value['player_id'] != player_id) or (type(value['turn']) is not int) or (value['turn'] != turn) or (value['reason'] not in REASONS):
        raise ValueError('Foreign or malformed policy catalogue')
    slots = validate_slots(value['slots'])
    if (value['reason'] == 'no_policy_slots') != (len(slots) == 0) or (value['reason'] != 'available' and any((r['options'] for r in slots))):
        raise ValueError('Policy catalogue contradicts its window')
    return value

def can_change(slots):
    """Existence test only, never a returned or submitted policy assignment."""
    validate_slots(slots)
    if not slots or not any((o['index'] != r['prior_index'] for r in slots for o in r['options'])):
        return False
    assigned = {}

    def visit(i, seen):
        for option in slots[i]['options']:
            h = option['hash']
            if h in seen:
                continue
            seen.add(h)
            if h not in assigned or visit(assigned[h], seen):
                assigned[h] = i
                return True
        return False
    return all((visit(i, set()) for i in range(len(slots))))

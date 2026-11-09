"""XP2 policy relocation using the official UI's clear-all/add-all request.

CanSlotPolicy rejects a policy that is currently active, before the request has
cleared its old slot. The UI instead checks row type for dragging active cards
and submits all removals before additions. Keep native availability queries for
inactive cards and verify the actual slot contents after application.
"""
from hashlib import sha256

from .configuration_profiles import XP2_CORE_SHA256
from .native import native_policy_actions, native_policy_catalog
from .xp2_policy_controls_source import SOURCE, bind_owner as bind_controls, source

UI_SHA256 = '6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'

# Source: GovernmentScreen.IsSlotTypeLegalInRow, its two fixed flags,
# GetSlotType initialization and OnConfirmPolicies' clear-all/add-all request.
# The presence of a row is established by the actual slot being queried.
SLOT_LEGALITY = b'''
local function policyFitsAfterClear(c,row,slot)
 local policy=GameInfo.Policies[row.index]
 local slotIndex=c:GetSlotType(slot)
 assert(type(slotIndex)=='number' and slotIndex%1==0,'invalid native policy slot type')
 local target=GameInfo.GovernmentSlots[slotIndex]
 assert(policy and target,'policy or government slot type absent')
 local from,to=policy.GovernmentSlotType,target.GovernmentSlotType
 if from=='SLOT_GREAT_PERSON' then from='SLOT_WILDCARD' end
 local known={SLOT_MILITARY=true,SLOT_ECONOMIC=true,SLOT_DIPLOMATIC=true,SLOT_WILDCARD=true}
 assert(known[from] and known[to],'unqualified policy slot type')
 return from==to or to=='SLOT_WILDCARD'
end
'''


def verify_ui_source():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof = source()
    ui = resolve_path(resource_root()/proof['ui']['path']).read_bytes()
    if proof['ui']['sha256'] != UI_SHA256 or sha256(ui).hexdigest() != UI_SHA256:
        raise ValueError('Policy relocation requires the pinned official government UI')
    return proof


def source_dependencies(*, execution_image=None):
    from .xp2_policy_controls_source import source_dependencies as dependencies
    verify_ui_source()
    return dependencies(execution_image=execution_image)


def bind_owner(saved):
    bind_controls(saved)
    backend = saved.backend
    identity = backend.core._handle, SOURCE[1], UI_SHA256
    previous = getattr(backend, '_xp2_policy_relocation_source', None)
    if previous is not None:
        if previous != identity:
            raise ValueError('Policy relocation source owner changed')
        return
    verify_ui_source()
    backend._xp2_policy_relocation_source = identity


def _replace_once(script, before, after):
    if script.count(before) != 1:
        raise ValueError('Policy relocation adapter no longer matches the shared source template')
    return SLOT_LEGALITY + script.replace(before, after)


def catalog_source(player_id, turn):
    script = native_policy_catalog.catalog_source(player_id, turn, core_sha256=XP2_CORE_SHA256)
    return _replace_once(script, b'elseif active[row.bits]==nil then',
        b'''elseif active[row.bits]~=nil then
     legal=policyFitsAfterClear(c,row,slot)
    elseif active[row.bits]==nil then''')


def request_source(player_id, candidate, *, allow_unchanged=False):
    if type(allow_unchanged) is not bool:
        raise ValueError('Policy reconfirmation flag must be a boolean')
    script = native_policy_actions.request_source(player_id, candidate, core_sha256=XP2_CORE_SHA256)
    script = _replace_once(script,
        b'active[bits]==nil and c:CanSlotPolicy(hash,slot)==true',
        b'''((active[bits]~=nil and policyFitsAfterClear(c,row,slot)) or
            (active[bits]==nil and c:CanSlotPolicy(hash,slot)==true))''')
    if allow_unchanged:
        guard = b"assert(different,'unchanged policy assignments must not submit a request')"
        if script.count(guard) != 1:
            raise ValueError('Policy reconfirmation no longer matches its shared request template')
        script = script.replace(guard,
            b'-- Official UI remove/restore edits can confirm the same final assignment.')
    return script


def confirmation_state_source(player_id, turn):
    """Read the existing own-player UI window flags; no inferred application."""
    return native_policy_actions._lua_common(native_policy_actions._player_id(player_id),
        native_policy_actions._uint(turn, 'turn')) + b'''
local c,n=baseContext()
local changed,open,civic,cost=c:PolicyChangeMade(),c:GetNumPolicySlotsOpen(),
 c:CivicCompletedThisTurn(),c:GetCostToUnlockPolicies()
assert(type(changed)=='boolean' and type(civic)=='boolean' and
 type(open)=='number' and open%1==0 and open>=0 and open<=n and
 type(cost)=='number' and cost%1==0 and cost>=0 and cost<=2147483647,
 'invalid native policy confirmation state')
local function dec(v) return string.format('%.0f',v) end
return table.concat({dec(pid),dec(expectedTurn),dec(n),changed and '1' or '0',
 dec(open),civic and '1' or '0',dec(cost)},'|')
'''


def parse_confirmation_state(raw, player_id, turn):
    player_id=int(native_policy_actions._player_id(player_id))
    turn=int(native_policy_actions._uint(turn,'turn'))
    if type(raw) is not bytes or len(raw)>256:
        raise ValueError('Invalid native policy confirmation state size')
    fields=raw.split(b'|')
    if len(fields)!=7 or fields[3] not in (b'0',b'1') or fields[5] not in (b'0',b'1'):
        raise ValueError('Malformed native policy confirmation state')
    parse=native_policy_actions._parse_u32
    pid,seen_turn,n=parse(fields[0],'player ID',63),parse(fields[1],'turn'),parse(fields[2],'slots',64)
    opened=parse(fields[4],'open slots',64)
    if pid!=player_id or seen_turn!=turn or opened>n:
        raise ValueError('Foreign native policy confirmation state')
    return dict(player_id=pid,turn=seen_turn,slot_count=n,changed=fields[3]==b'1',
                open_slots=opened,civic_completed=fields[5]==b'1',
                unlock_cost=parse(fields[6],'unlock cost',0x7fffffff))

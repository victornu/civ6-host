"""Locked AGREEMENTS/ALLIANCE deal term: inventory, copy/rebuild and archive.

Seam helper for api_worker, which owns the common deal files: deal_gold._ITEM
asserts count==deal:GetItemCount() with count=resource+border+treaty only, so a
locked alliance item currently refuses the draft read; _NEGOTIATION and
copy_adjusted_source carry the same count asserts; the acceptance archive
treats every AGREEMENTS item whose subtype is not MAKE_PEACE as open-borders.
This module provides the alliance-aware inventory, counts, copy verify and
archive check without editing those common files.

Enums are taken live from the engine (DealItemTypes.AGREEMENTS,
DealAgreementTypes.ALLIANCE, DB.MakeHash("ALLIANCE_<TYPE>")) exactly as the
pinned official overlay callback uses them; no alliance numeric value is
hardcoded in Python. The proposal path to a HUMAN counterparty uses the same
official dispatcher (RequestSession MAKE_DEAL); upstream support flags for
human openings are still false (xp2_major_deals marks opening selections
unsupported when counterparty_is_human), so this source is delivered for the
api_worker wiring, not as a simulated candidate.
"""
from __future__ import annotations

import json
import struct

from . import xp2_alliances_source as facts
from . import xp2_deal_open_borders as borders

KIND = borders.KIND                 # DealItemTypes.AGREEMENTS on the wire
ITEM_BYTES = borders.ITEM_BYTES     # 56-byte AGREEMENTS item layout
KIND_OFFSET, SUBTYPE_OFFSET = 0, 20
DURATION_OFFSET, GIVER_OFFSET, RECIPIENT_OFFSET = 28, 32, 36
TAIL_OFFSET, TAIL = 44, (1, 0, 2)

ALLIANCE_TYPES = facts.ALLIANCE_TYPES

# Live-enum Lua block: AGREEMENTS/ALLIANCE values and the five value-type
# hashes are computed by the engine, mirroring the pinned overlay slice.
_ENUMS = (b"""
local AGREEMENTS=DealItemTypes.AGREEMENTS
local ALLIANCE=DealAgreementTypes.ALLIANCE
assert(type(AGREEMENTS)=='number' and AGREEMENTS%4294967296==""" + str(KIND).encode('ascii') +
    b""",'Native AGREEMENTS enum changed')
assert(type(ALLIANCE)=='number' and ALLIANCE%1==0 and ALLIANCE>=0 and ALLIANCE<4294967296,
 'Native ALLIANCE agreement subtype unavailable')
local ALLIANCE_HASH={}
for _,name in ipairs({'ALLIANCE_RESEARCH','ALLIANCE_CULTURAL','ALLIANCE_ECONOMIC','ALLIANCE_MILITARY','ALLIANCE_RELIGIOUS'}) do
 ALLIANCE_HASH[DB.MakeHash(name)]=name
end
""")

# Per-giver inventory of the locked alliance item; sets allianceCount and
# appends rows to allianceTerms. Designed to be concatenated into the common
# _items() block, where it must run before the item-count asserts.
INVENTORY = _ENUMS + b"""
local allianceCount=0
local allianceTerms={}
local function allianceInventory(giver,receiver,direction)
 local items=deal:FindItemsByType(AGREEMENTS,ALLIANCE,giver) or {}
 assert(type(items)=='table' and #items<=1,'Unexpected locked alliance items')
 for _,item in ipairs(items) do
  assert(item:IsLocked()==true,'Alliance agreement is not locked')
  local duration=item:GetDuration()
  -- Signed-32 representation only; the value itself is set by the native
  -- builder (pinned overlay adds the item, pDeal:Validate()) and consumed by
  -- the archive; never bounded from the capture DB here.
  assert(type(duration)=='number' and duration%1==0,'Invalid alliance item duration')
  local name=ALLIANCE_HASH[item:GetValueType()]
  assert(name~=nil,'Unknown alliance value type')
  allianceCount=allianceCount+1
  allianceTerms[#allianceTerms+1]='{"direction":"'..direction..'","type":"'..name..
   '","duration":'..tostring(duration)..'}'
 end
end
"""

# Alliance-aware replacements for the common count asserts: the locked
# agreement appears once in GetItemCount and in both directional counts, like
# the locked peace treaty.
TOTAL_ASSERT = b"assert(count+allianceCount==deal:GetItemCount(),'The draft contains unqualified items')\n"
DIRECTIONAL_ASSERT = (b"assert(u31(fromLocal) and u31(fromOther) and "
                      b"fromLocal+fromOther==count+treatyCount+allianceCount,\n"
                      b" 'Native deal negotiation directions differ')\n")
COPY_ASSERT = (b"assert(copied and copied:GetItemCount()==count+allianceCount,"
               b"'Native adjusted copy changed the item count')\n")


def _read(prefix, bilateral):
    body = INVENTORY + b"""
allianceInventory(me,other,'outgoing')
"""
    if bilateral:
        body += b"allianceInventory(other,me,'incoming')\n"
    body += b"""
return '{"alliance_subtype":'..tostring(ALLIANCE)..',"terms":['..table.concat(allianceTerms,',')..']}'
"""
    return prefix + body


def read_source(prefix, *, bilateral=False):
    """Eval reading the locked alliance terms of the working OUTGOING deal."""
    if type(bilateral) is not bool:
        raise ValueError('Bilateral alliance read must be boolean')
    return _read(prefix, bilateral)


def parse(raw, *, bilateral=False):
    if type(raw) is not bytes or len(raw) > 8192:
        raise ValueError('Unbounded alliance deal readback')
    value = json.loads(raw)
    if (type(value) is not dict or set(value) != {'alliance_subtype', 'terms'}
            or type(value['alliance_subtype']) is not int
            or not 0 <= value['alliance_subtype'] < (1 << 32)):
        raise ValueError('Malformed alliance deal readback')
    terms = value['terms']
    expected_directions = ('outgoing', 'incoming') if bilateral else ('outgoing',)
    if (type(terms) is not list or len(terms) > 2
            or any(type(row) is not dict or set(row) != {'direction', 'type', 'duration'}
                   or row['direction'] not in expected_directions
                   or row['type'] not in ALLIANCE_TYPES
                   or type(row['duration']) is not int
                   or not -(1 << 31) <= row['duration'] < (1 << 31)
                   for row in terms)):
        raise ValueError('Malformed alliance deal terms')
    if len({row['direction'] for row in terms}) != len(terms):
        raise ValueError('Duplicate alliance term direction')
    return value


def copy_source(prefix):
    """Alliance-aware adjusted-copy verification (mirrors copy_adjusted_source)."""
    return _read(prefix, True) + b"""
DealManager.CopyIncomingToOutgoingWorkingDeal(me,other)
assert(DealManager.AreWorkingDealsEqual(me,other)==true,'GameCore did not copy the adjusted terms')
local copied=DealManager.GetWorkingDeal(DealDirection.OUTGOING,me,other)
""" + COPY_ASSERT + b"if count>0 then copied:Validate() end\nreturn 'verified'\n"


def expected_alliance(player_id, target, alliance_type, duration):
    """Archive expectation for one outgoing locked alliance item.

    The duration comes from the native working-deal read, never from the
    capture constant ALLIANCE_DURATION (data only).
    """
    if alliance_type not in ALLIANCE_TYPES:
        raise ValueError('Unknown alliance type')
    if type(duration) is not int or not -(1 << 31) <= duration < (1 << 31):
        raise ValueError('Invalid alliance archive duration')
    return {(player_id, target): duration}


def check_archive(payload, offset, expected, alliance_subtype):
    """Verify one AGREEMENTS/ALLIANCE item in a submission/acceptance archive."""
    if len(payload) - offset < ITEM_BYTES:
        raise RuntimeError('Truncated native alliance term')
    kind, = struct.unpack_from('<I', payload, offset + KIND_OFFSET)
    subtype, = struct.unpack_from('<I', payload, offset + SUBTYPE_OFFSET)
    duration, giver, recipient = struct.unpack_from('<III', payload, offset + DURATION_OFFSET)
    tail = struct.unpack_from('<III', payload, offset + TAIL_OFFSET)
    if (kind != KIND or subtype != alliance_subtype or tail != TAIL
            or expected.pop((giver, recipient), None) % (1 << 32) != duration):
        raise RuntimeError('Native deal archives contain different alliance terms')


def request_source(pid, turn, target, key, *, configuration, execution_image, counterparty):
    """Official propose dispatch toward a HUMAN counterparty (same MAKE_DEAL).

    Mirrors xp2_alliances.request_source but asserts a human target instead of
    the AI-only guard. Upstream support flags stay false for human openings
    until api_worker wires them, so this source is not a candidate by itself.
    """
    if counterparty not in ('ai', 'human'):
        raise ValueError('Counterparty controller must be ai or human')
    if key not in facts.ALLIANCE_PROPOSALS:
        raise ValueError('Only alliance proposals have a deal working-copy path')
    from . import xp2_alliances as alliances
    source = alliances.request_source(pid, turn, target, key, configuration=configuration,
                                      execution_image=execution_image)
    guard_old = (b"assert(Players[target]:IsHuman()==false and DealManager.HasPendingDeal(pid,target)==false,\n"
                 b" 'Outgoing alliance deal requires an AI counterparty without a pending deal')\n")
    if counterparty == 'human':
        guard_new = (b"assert(Players[target]:IsHuman()==true and DealManager.HasPendingDeal(pid,target)==false,\n"
                     b" 'Outgoing human alliance deal requires a human counterparty without a pending deal')\n")
    else:
        guard_new = guard_old
    if source.count(guard_old) != 1:
        raise RuntimeError('Alliance request guard changed')
    return source.replace(guard_old, guard_new)

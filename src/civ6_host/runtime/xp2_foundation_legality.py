"""Private comparison of the two native founder-availability calls."""

import re
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .unit_operation_ui_profile import source_dependencies
from .xp1_session_inputs import saved_load_pin

PROOF = ("evidence/native-unit-action-route.json",
         "69454efb375425864b82bdb703eeb1e233c6e8107d30e334ab25226ccab3c2e6")
_OFFICIAL_CALL = "UnitOperationTypes.FOUND_CITY, nil, false, OperationResultsTypes.ALL"
_CAPACITY = 32768


def pin_sources(pins, *, execution_image=None):
    root = resource_root()
    proof = load_pinned_json(root / PROOF[0], PROOF[1])
    panel = proof["installed_lua"]
    if not any(_OFFICIAL_CALL in row["text"] for row in panel["references"]):
        raise ValueError("Official foundation operation overload changed")
    dependencies = source_dependencies(root, core_sha256=XP2_CORE_SHA256,
                                      execution_image=execution_image)
    dependencies.update({str(root / PROOF[0]): PROOF[1], panel["file"]: panel["sha256"]})
    for path, digest in dependencies.items():
        saved_load_pin(pins, path, digest)
    saved_load_pin(pins, Path(__file__))


def _source(player, turn, unit_ids):
    assert type(player) is int and 0 <= player < 64 and type(turn) is int and turn >= 0
    if not 1 <= len(unit_ids) <= 32 or any(type(uid) is not int or not 0 <= uid <= 0xffffffff for uid in unit_ids):
        raise ValueError("Foundation diagnostic needs bounded own unit IDs")
    ids = ",".join(map(str, unit_ids))
    header = f"local pid,turn={player},{turn}\nlocal ids={{{ids}}}\n".encode("ascii")
    return header + b"""
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
       'foundation diagnostic perspective changed')
local p=Players[pid]
assert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),
       'foundation diagnostic requires an active seat')
assert(UnitManager and type(UnitManager.CanStartOperation)=='function'
       and type(UnitOperationTypes.FOUND_CITY)=='number' and type(OperationResultsTypes.ALL)=='number',
       'foundation diagnostic operation unavailable')
local out={}
local function flag(value)
  assert(type(value)=='boolean','foundation query did not return Boolean legality')
  return value and 1 or 0
end
local byID={}
local seen=0
for _,unit in p:GetUnits():Members() do
  seen=seen+1; assert(seen<=4096 and unit:GetOwner()==pid,'foundation diagnostic collection differs')
  local id=unit:GetID()
  assert(byID[id]==nil,'duplicate unit in foundation diagnostic')
  byID[id]=unit
end
for _,id in ipairs(ids) do
  local unit=byID[id]
  assert(unit and unit:GetOwner()==pid and unit:GetID()==id,'foundation diagnostic unit differs')
  local info=GameInfo.Units[unit:GetType()]
  assert(info and type(info.UnitType)=='string','foundation diagnostic unit type is unavailable')
  if info.UnitType=='UNIT_SETTLER' then
    local legacy=UnitManager.CanStartOperation(unit,'UNITOPERATION_FOUND_CITY',nil,false)
    local legal,result=UnitManager.CanStartOperation(unit,UnitOperationTypes.FOUND_CITY,nil,false,OperationResultsTypes.ALL)
    local visible=UnitManager.CanStartOperation(unit,UnitOperationTypes.FOUND_CITY,nil,true)
    local count=0
    local reasons={}
    if result~=nil then
      assert(type(result)=='table','foundation result is not a table')
      for _ in pairs(result) do
        count=count+1; assert(count<=32,'foundation result field limit')
      end
      local source=UnitOperationResults and result[UnitOperationResults.FAILURE_REASONS]
      if source~=nil then
        assert(type(source)=='table' and #source<=32,'foundation failure reasons differ')
        for _,reason in ipairs(source) do
          assert(type(reason)=='string' and #reason<=160 and reason:match('^LOC_[A-Z0-9_]+$'),
                 'unexpected foundation failure reason')
          reasons[#reasons+1]=reason
        end
      end
    end
    out[#out+1]=string.format('%.0f,%d,%d,%d,%d,%d,%d,%s',
      id,unit:GetX(),unit:GetY(),flag(legacy),flag(legal),flag(visible),result==nil and -1 or count,
      table.concat(reasons,'|'))
  end
end
return table.concat(out,';')
"""


def parse(raw, units):
    if type(raw) is not bytes or len(raw) > _CAPACITY:
        raise ValueError("Invalid native foundation result size")
    records = []
    if raw == b"":
        return records
    expected = {(unit["id"], unit["x"], unit["y"]): index for index, unit in enumerate(units)}
    if len(expected) != len(units):
        raise ValueError("Observed foundation units contain duplicate identities")
    previous_index = -1
    seen = set()
    for row in raw.decode("ascii").split(";"):
        match = re.fullmatch(r"(\d+),(\d+),(\d+),([01]),([01]),([01]),(-1|\d+),(.*)", row)
        if match is None:
            raise ValueError("Invalid native foundation result")
        uid, x, y, legacy, legal, visible, count = map(int, match.groups()[:7])
        reasons = match[8].split("|") if match[8] else []
        if (not -1 <= count <= 32 or len(reasons) > 32 or (count < 1 and reasons)
                or any(not re.fullmatch(r"LOC_[A-Z0-9_]{1,156}", reason) for reason in reasons)):
            raise ValueError("Native foundation result exceeds its admitted schema")
        identity = (uid, x, y)
        unit_index = expected.get(identity)
        if unit_index is None or unit_index <= previous_index or uid in seen:
            raise ValueError("Native foundation result is not an ordered observed-unit subset")
        previous_index = unit_index
        seen.add(uid)
        records.append(dict(unit_id=uid, x=x, y=y, menu_query=bool(legacy), official_query=bool(legal),
                            visibility_query=bool(visible), result_fields=None if count < 0 else count,
                            reason_keys=reasons))
    return records


def emit_readback(owner, response, emit):
    observation, decisions = response["observation"], response["decisions"]
    controls = decisions["turn_controls"]
    if not (controls["active"] and controls["active_complete"]):
        return
    # The native GameInfo query identifies settlers from this captured ruleset;
    # do not infer UNIT_SETTLER from a numeric unit-type index on the host.
    units = sorted(observation["units"], key=lambda u: u["id"])
    if not units or len(units) > 32:
        return
    continuation, prefix = owner.continuation, owner.prefix
    continuation.check(active=False)
    continuation.transport.require_empty_native_queue()
    player, turn = observation["player_id"], observation["turn"]
    source = _source(player, turn, [unit["id"] for unit in units])
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b"@native_foundation_readback", capacity=_CAPACITY)
    continuation.check(active=False)
    continuation.transport.require_empty_native_queue()
    records = parse(raw, units)
    offered = {row["action"]["unit_id"] for row in decisions["candidates"]
               if row["action"]["kind"] == "found_city"}
    if offered != {r["unit_id"] for r in records if r["menu_query"]}:
        raise ValueError("Native foundation readback differs from the published catalogue")
    emit("xp2_bbg_foundation_legality_readback", actor_channel=False,
         episode_id=response["episode_id"], game_generation=response["game_generation"],
         sequence=response["sequence"], player_id=player, turn=turn, units=records,
         core_sha256=XP2_CORE_SHA256, source_sha256=PROOF[1])

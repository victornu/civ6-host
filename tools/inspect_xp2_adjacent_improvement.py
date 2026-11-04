"""Read adjacent improvement offers from the selected unit in an official XP2 UI."""

import argparse
import json
import re


_PROBE = """
local player = Game.GetLocalPlayer()
local unit = UI.GetHeadSelectedUnit()
assert(player >= 0 and unit and unit:GetOwner() == player)
local op = UnitOperationTypes.BUILD_IMPROVEMENT_ADJACENT
assert(type(op) == 'number')
local key = UnitOperationTypes.PARAM_IMPROVEMENT_TYPE
local available, result = UnitManager.CanStartOperation(unit, op, nil, {}, true)
local rows = {}
local choices = available and result and result[UnitOperationResults.IMPROVEMENTS] or {}
assert(#choices <= 32)
for _, selector in ipairs(choices) do
    local improvement = GameInfo.Improvements[selector]
    local eligible = UnitManager.CanStartOperation(unit, op, nil, {[key] = selector}, true)
    local targets = UnitManager.GetOperationTargets(unit, op, {[key] = improvement.Hash})
    local plots = targets[UnitOperationResults.PLOTS] or {}
    local count = 0
    for _, index in pairs(plots) do
        count = count + 1
        assert(count <= 32 and Map.IsPlot(index))
        local plot = Map.GetPlotByIndex(index)
        local x, y = plot:GetX(), plot:GetY()
        local accepted = UnitManager.CanStartOperation(unit, op, nil, {
            [UnitOperationTypes.PARAM_X] = x,
            [UnitOperationTypes.PARAM_Y] = y,
            [key] = improvement.Hash,
        })
        rows[#rows + 1] = table.concat({'xp2-adjacent-target', selector, index, x, y,
            accepted and 1 or 0}, '|')
    end
    rows[#rows + 1] = table.concat({'xp2-adjacent-offer', selector, improvement.Hash,
        eligible and 1 or 0, count}, '|')
end
table.sort(rows)
print(table.concat({'xp2-adjacent-unit', Game.GetCurrentGameTurn(), player, unit:GetID(),
    available and 1 or 0, #choices}, '|'))
for _, row in ipairs(rows) do print(row) end
"""

_UNIT = re.compile(r"xp2-adjacent-unit\|(\d{1,6})\|(\d{1,3})\|(\d{1,10})\|([01])\|(\d{1,2})")
_OFFER = re.compile(r"xp2-adjacent-offer\|(\d{1,6})\|(-?\d{1,10})\|([01])\|(\d{1,2})")
_TARGET = re.compile(r"xp2-adjacent-target\|(\d{1,6})\|(\d{1,6})\|(\d{1,4})\|(\d{1,4})\|([01])")


def parse(lines):
    header = _UNIT.fullmatch(lines[0]) if 1 <= len(lines) <= 1057 else None
    if header is None:
        raise ValueError("Expected a bounded XP2 readback for one locally selected unit")
    turn, player, unit, available, expected = map(int, header.groups())
    offers, targets = {}, {}
    for line in lines[1:]:
        offer = _OFFER.fullmatch(line)
        if offer:
            selector, improvement_hash, eligible, count = map(int, offer.groups())
            if selector in offers or count > 32:
                raise ValueError("Duplicate or oversized improvement offer")
            offers[selector] = (improvement_hash, eligible, count)
            continue
        target = _TARGET.fullmatch(line)
        if target is None:
            raise ValueError("Unexpected XP2 readback row")
        selector, plot, x, y, accepted = map(int, target.groups())
        by_plot = targets.setdefault(selector, {})
        if plot in by_plot:
            raise ValueError("Duplicate target plot")
        by_plot[plot] = dict(plot=plot, x=x, y=y, accepted=bool(accepted))
    if len(offers) != expected or expected > 32 or (expected and not available):
        raise ValueError("Incomplete or inconsistent XP2 offer list")
    if targets.keys() - offers.keys() or any(
        len(targets.get(selector, {})) != offer[2] for selector, offer in offers.items()
    ):
        raise ValueError("Incomplete or unassociated XP2 target list")
    return dict(schema="civ6-host.xp2-adjacent-improvement.readback.v1", turn=turn,
                player=player, unit=unit, operation_available=bool(available),
                offers=[dict(selector=selector, improvement_hash=offer[0], eligible=bool(offer[1]),
                             targets=list(targets.get(selector, {}).values()))
                        for selector, offer in offers.items()],
                executed_operation=False)


def inspect(client, context):
    states = client.refresh_states()
    if context not in states:
        raise ValueError("Requested Lua context is absent")
    lines = client.execute(_PROBE, context=context)
    report = parse(lines)
    if lines != client.execute(_PROBE, context=context) or states != client.refresh_states():
        raise ValueError("XP2 readback changed during inspection")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=int)
    parser.add_argument("--port", type=int, default=4318)
    args = parser.parse_args()
    from civ6_host.runtime.native.tuner import TunerClient
    with TunerClient(port=args.port, timeout=5) as client:
        print(json.dumps(inspect(client, args.context), indent=2))


if __name__ == "__main__":
    main()

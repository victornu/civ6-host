"""Inspect an already running Civ6 session through the local Tuner connection."""
import argparse
import json
import re


_PROBE = """
local shared
if type(ExposedMembers) == 'table' then
    if type(rawget) == 'function' then
        shared = rawget(ExposedMembers, 'LuaEvents')
    elseif getmetatable(ExposedMembers) == nil then
        shared = ExposedMembers.LuaEvents
    end
end
local function describe(value)
    if type(value) ~= 'table' then return type(value) end
    local meta = getmetatable(value)
    if meta ~= nil and (type(meta) ~= 'table' or type(rawget) ~= 'function'
            or rawget(meta, '__tostring') ~= nil) then
        return 'table'
    end
    local label = tostring(value)
    return string.match(label, '^table: [0-9a-fA-Fx]+$') and label or 'table'
end
assert(Game and type(Game.GetCurrentGameTurn) == 'function')
local turn = Game.GetCurrentGameTurn()
local same = '-'
if type(shared) == 'table' and type(LuaEvents) == 'table' then
    if type(rawequal) == 'function' then
        same = rawequal(shared, LuaEvents) and '1' or '0'
    elseif getmetatable(shared) == nil and getmetatable(LuaEvents) == nil then
        same = shared == LuaEvents and '1' or '0'
    end
end
local request = UI and type(UI.RequestPlayerOperation) == 'function'
local operation = PlayerOperations and PlayerOperations.EXECUTE_SCRIPT
assert(operation == nil or (type(operation) == 'number' and operation % 1 == 0
    and operation >= -2147483648 and operation <= 4294967295))
print(table.concat({'bbg-context-v3', tostring(turn), describe(ExposedMembers),
    describe(LuaEvents), describe(shared), same, type(GameEvents),
    request and '1' or '0', operation == nil and '-' or string.format('%.0f', operation)}, '|'))
"""

_TABLE = r"nil|table(?:: [0-9a-fA-Fx]{1,32})?|userdata|boolean"
_ROW = re.compile(
    rf"bbg-context-v3\|(?P<turn>[0-9]{{1,6}})\|(?P<exposed>{_TABLE})\|"
    rf"(?P<local_events>{_TABLE})\|(?P<shared_events>{_TABLE})\|(?P<same>[-01])\|"
    r"(?P<game_events>nil|table|userdata|boolean)\|(?P<request>[01])\|(?P<operation>-|-?[0-9]{1,10})")


def _compare_labels(rows, key):
    labels = [row[key] for row in rows.values()]
    if not all(label.startswith('table: ') for label in labels):
        return None
    return len(set(labels)) == 1


def inspect(client, contexts):
    if (not 2 <= len(contexts) <= 4 or any(type(index) is not int for index in contexts)
            or len(set(contexts)) != len(contexts)):
        raise ValueError('Choose two to four distinct numeric Lua contexts')
    states = client.refresh_states()
    if any(index not in states for index in contexts):
        raise ValueError('At least one requested context is absent')

    def read():
        result = {}
        for index in contexts:
            lines = client.execute(_PROBE, context=index)
            row = _ROW.fullmatch(lines[0]) if len(lines) == 1 else None
            if row is None or (row['operation'] != '-'
                    and not -(1 << 31) <= int(row['operation']) < (1 << 32)):
                raise ValueError('Unexpected BBG namespace readback')
            result[index] = row.groupdict()
        return result

    rows = read()
    if len({row['turn'] for row in rows.values()}) != 1 or rows != read():
        raise ValueError('Lua namespace readback changed during inspection')
    if client.refresh_states() != states:
        raise ValueError('Lua context roster changed during inspection')
    return dict(schema='civ6-host.bbg-context-readback.v3', turn=int(rows[contexts[0]]['turn']),
        contexts=[dict(index=i, name=states[i], exposed_members=row['exposed'].split(':')[0],
            local_lua_events=row['local_events'].split(':')[0],
            exposed_lua_events=row['shared_events'].split(':')[0],
            local_and_exposed_rawequal=None if row['same'] == '-' else row['same'] == '1',
            game_events=row['game_events'], request_player_operation_available=row['request'] == '1',
            execute_script_value=None if row['operation'] == '-' else int(row['operation']))
            for i, row in rows.items()],
        same_default_exposed_members_label=_compare_labels(rows, 'exposed'),
        same_default_exposed_lua_events_label=_compare_labels(rows, 'shared_events'),
        modifies_game_state=False, bbg_profile_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('context', nargs='+', type=int)
    parser.add_argument('--port', type=int, default=4318)
    args = parser.parse_args()
    from civ6_host.runtime.native.tuner import TunerClient
    with TunerClient(port=args.port, timeout=5) as client:
        print(json.dumps(inspect(client, args.context), indent=2))


if __name__ == '__main__':
    main()

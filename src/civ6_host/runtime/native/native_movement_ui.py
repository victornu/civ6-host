"""Capture the shipped movement preview's drawing commands, without a renderer.

This is a read-only diagnostic adapter. It is not an actor observation contract
or a replacement for a qualified graphical differential test.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
MAX_TARGETS = 16
MAX_BYTES = 2 * 1024 * 1024

def validate_targets(value):
    if type(value) is not list or not 1 <= len(value) <= MAX_TARGETS:
        raise ValueError('Movement UI probe requires one to sixteen explicit targets')
    seen = set()
    for row in value:
        if type(row) is not dict or set(row) != {'unit_id', 'plot_id'} or type(row['unit_id']) is not int or (not 0 <= row['unit_id'] <= 4294967295) or (type(row['plot_id']) is not int) or (not 0 <= row['plot_id'] < 16384):
            raise ValueError('Invalid movement UI probe target')
        key = (row['unit_id'], row['plot_id'])
        if key in seen:
            raise ValueError('Duplicate movement UI probe target')
        seen.add(key)
    return value
PREAMBLE = '\nlocal function integer(v,lo,hi)\n assert(type(v)==\'number\' and v%1==0 and v>=lo and v<=hi,\'invalid movement UI integer\');return v\nend\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,\n \'movement UI perspective changed\')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete()\n and Game.IsAllowStrategicCommands(pid),\'movement UI player not ready\')\nlocal width,height=Map.GetGridSize()\ninteger(width,1,16384);integer(height,1,16384);assert(width*height<=16384 and destination<width*height)\nlocal selected=nil\nfor _,u in player:GetUnits():Members() do\n if u:GetID()==uid then assert(selected==nil and u:GetOwner()==pid);selected=u end\nend\nassert(selected,\'movement UI unit is not owned\')\nlocal nativeTable=table\nlocal table=setmetatable({count=function(t) local n=0;for _ in pairs(t) do n=n+1 end;return n end},{__index=nativeTable})\nlocal function encode(v,depth)\n assert(depth<8,\'movement UI drawing nesting too deep\')\n local typ=type(v)\n if typ==\'number\' then integer(v,-4294967296,4294967295);return string.format(\'%.0f\',v) end\n if typ==\'boolean\' then return v and \'true\' or \'false\' end\n if typ==\'string\' then\n  assert(#v<=128 and string.match(v,\'^[A-Za-z0-9_]+$\'),\'unexpected movement UI drawing token\')\n  return \'"\'..v..\'"\'\n end\n assert(typ==\'table\',\'unsupported movement UI drawing value\')\n local n=0;for k in pairs(v) do integer(k,1,16384);n=n+1;assert(n<=16384) end\n local out={};for i=1,n do assert(v[i]~=nil,\'sparse movement UI drawing\');out[i]=encode(v[i],depth+1) end\n return \'[\'..table.concat(out,\',\')..\']\'\nend\nlocal calls={}\nlocal function record(name,...)\n assert(#calls<65536,\'movement UI drawing call bound\')\n local args={...};assert(#args==select(\'#\',...),\'nil movement UI drawing argument\')\n calls[#calls+1]=\'{"call":"\'..name..\'","arguments":\'..encode(args,0)..\'}\'\nend\nlocal function unknown(_,key) error(\'unsupported movement UI presentation API \'..tostring(key)) end\nlocal UI=setmetatable({\n IsMovementPathOn=function() return true end,\n IsGameCoreBusy=function() return false end,\n GetHeadSelectedUnit=function() return selected end,\n GetCursorPlotID=function() return destination end,\n AddNumberToPath=function(...) record(\'AddNumberToPath\',...) end,\n PlaySound=function(...) record(\'PlaySound\',...) end,\n},{__index=unknown})\nlocal activeLens=\'Default\'\nlocal UILens=setmetatable({\n IsLensActive=function(name) return activeLens==name end,\n SetActive=function(name) activeLens=name;record(\'SetActive\',name) end,\n ClearLayerHexes=function(...) record(\'ClearLayerHexes\',...) end,\n UnFocusHex=function(...) record(\'UnFocusHex\',...) end,\n FocusHex=function(...) record(\'FocusHex\',...) end,\n SetLayerHexesPath=function(...) record(\'SetLayerHexesPath\',...) end,\n SetLayerHexesArea=function(...) record(\'SetLayerHexesArea\',...) end,\n},{__index=unknown})\nlocal nativeUnitManager=UnitManager\nlocal UnitManager=setmetatable({\n RequestOperation=function() error(\'read-only movement preview attempted an operation\') end,\n RequestCommand=function() error(\'read-only movement preview attempted a command\') end,\n},{__index=nativeUnitManager})\nlocal g_MovementPath,g_Numbers,g_AttackRange=\'MovementPath\',\'Numbers\',\'AttackRange\'\nlocal m_cachedPathUnit,m_cachedPathPlotId=nil,-1\nlocal m_previousTurnsCount=0\nlocal m_isPlotFlaggedRestricted=false\nlocal m_constrainToPlotID=0\nlocal m_kTutorialUnitMoveRestrictions,m_kTutorialUnitHexRestrictions=nil,nil\nlocal lensNameBase\n'

def preview_source(player_id, turn, unit_id, plot_id):
    for v, hi in ((player_id, 63), (turn, 2147483647), (unit_id, 4294967295), (plot_id, 16383)):
        if type(v) is not int or not 0 <= v <= hi:
            raise ValueError('Invalid movement UI preview identity')
    from civ6_host.runtime.native.native_movement_ui_source import functions_source
    return f'local pid,turn,uid,destination={player_id},{turn},{unit_id},{plot_id}\n'.encode() + PREAMBLE.encode() + functions_source() + b'\nRealizeMovementPath(false)\nreturn \'{"schema":"civ6rl.movement_ui_drawing_probe.v1","player_id":\'..pid..\n \',"turn":\'..turn..\',"unit_id":\'..uid..\',"destination_plot_id":\'..destination..\n \',"width":\'..width..\',"height":\'..height..\',"calls":[\'..table.concat(calls,\',\')..\']}\'\n'

def parse_preview(raw, player_id, turn, target):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ValueError('Unbounded movement UI preview')

    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError('Duplicate movement UI field')
            out[key] = value
        return out
    v = json.loads(raw, object_pairs_hook=pairs)
    if type(v) is not dict or set(v) != {'schema', 'player_id', 'turn', 'unit_id', 'destination_plot_id', 'width', 'height', 'calls'} or v['schema'] != 'civ6rl.movement_ui_drawing_probe.v1' or any((type(v[k]) is not int for k in ('player_id', 'turn', 'unit_id', 'destination_plot_id', 'width', 'height'))) or ((v['player_id'], v['turn'], v['unit_id'], v['destination_plot_id']) != (player_id, turn, target['unit_id'], target['plot_id'])) or (not 1 <= v['width'] <= 16384) or (not 1 <= v['height'] <= 16384) or (v['width'] * v['height'] > 16384) or (not 0 <= v['destination_plot_id'] < v['width'] * v['height']) or (type(v['calls']) is not list) or (len(v['calls']) > 65536):
        raise ValueError('Invalid movement UI preview envelope')
    lenses = {'Default', 'MovementGood', 'MovementBad', 'MovementFOW', 'MovementQueue'}
    layers = {'MovementPath', 'Numbers', 'AttackRange'}

    def plot(x):
        return type(x) is int and 0 <= x < v['width'] * v['height']
    names = {'AddNumberToPath', 'PlaySound', 'SetActive', 'ClearLayerHexes', 'UnFocusHex', 'FocusHex', 'SetLayerHexesPath', 'SetLayerHexesArea'}
    for call in v['calls']:
        if type(call) is not dict or set(call) != {'call', 'arguments'} or call['call'] not in names or (type(call['arguments']) is not list):
            raise ValueError('Unknown movement UI drawing call')
        name = call['call']
        args = call['arguments']
        valid = False
        if name == 'AddNumberToPath':
            valid = len(args) == 2 and type(args[0]) is int and (0 <= args[0] <= 2147483647) and plot(args[1])
        elif name == 'PlaySound':
            valid = args == ['UI_Multi_Turn_Movement_Alert']
        elif name in ('SetActive', 'ClearLayerHexes'):
            valid = len(args) == 1 and type(args[0]) is str and (args[0] in (lenses if name == 'SetActive' else layers))
        elif name in ('FocusHex', 'UnFocusHex'):
            valid = len(args) == 2 and args[0] == 'AttackRange' and plot(args[1])
        else:
            valid = len(args) == 4 and args[0] == ('MovementPath' if name == 'SetLayerHexesPath' else 'AttackRange') and (type(args[1]) is int) and (args[1] == player_id) and (type(args[2]) is list) and (len(args[2]) <= 16384) and all((plot(x) for x in args[2])) and (type(args[3]) is list) and (len(args[3]) <= 16384)
            if valid:
                for variation in args[3]:
                    if type(variation) is not list or not variation or type(variation[0]) is not str:
                        valid = False
                        break
                    token = variation[0]
                    if token == 'EmptyVariant':
                        expected = 3
                    else:
                        prefix, sep, suffix = token.rpartition('_')
                        if not sep or prefix not in lenses - {'Default'} or suffix not in {'Origin', 'Destination', 'Counter', 'Pip', 'Minus'}:
                            valid = False
                            break
                        expected = 3 if suffix == 'Minus' else 2
                    if len(variation) != expected or not all((plot(x) for x in variation[1:])):
                        valid = False
                        break
        if not valid:
            raise ValueError('Invalid movement UI drawing arguments: ' + name)
    return v

def inspect(owner, targets, observation):
    """Separate instrumentation, never injected into the actor response."""
    validate_targets(targets)
    from civ6_host.runtime.native.native_saved_actions import snapshot
    from civ6_host.runtime.native.native_player_observation import observe_player
    p = owner.prefix
    pid = observation['player_id']
    turn = observation['turn']
    owner.control(empty=True)
    before = snapshot(owner, 'before')
    if observe_player(p.runtime, p.ui_child, pid) != observation:
        raise RuntimeError('Movement UI probe crossed public observation boundary')
    rows = []
    for target in targets:
        raw = p.runtime.evaluate_text(p.ui_child, preview_source(pid, turn, target['unit_id'], target['plot_id']), b'@official_movement_ui_drawing_probe', capacity=MAX_BYTES + 1)
        rows.append(parse_preview(raw, pid, turn, target))
    owner.control(empty=True)
    if snapshot(owner, 'after') != before or observe_player(p.runtime, p.ui_child, pid) != observation:
        raise RuntimeError('Read-only movement UI preview changed native state')
    owner.emit('official_movement_ui_drawing_probe', previews=rows, native_actions=0, public_observation_unchanged=True, scheduler_unchanged=True, tutorial_free_diagnostic=True, graphical_parity_proven=False, actor_contract_qualified=False, strategic_training_ready=False)
    return rows

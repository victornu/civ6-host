"""Explicit diagnostic choices that free an own unit's native reachable endpoint.

This is controller policy, never an action rewrite or a path/legality model.
The input catalogue already contains native-admitted, visible, empty targets.
Requests still revalidate that catalogue choice and require a native readback.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from collections import Counter
from civ6_host.runtime.native.native_unit_movement import choose

def unit_order_budget_source(player_id: int) -> bytes:
    """Count only own units to bound the diagnostic order loop; grant no action."""
    if type(player_id) is not int or player_id not in (0, 1):
        raise ValueError('Invalid diagnostic player')
    return b'local pid=' + str(player_id).encode('ascii') + b"\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\n       'unit budget perspective mismatch')\nlocal p=Players[pid]\nassert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,\n       'unit budget player not ready')\nlocal count,seen=0,{}\nfor _,u in p:GetUnits():Members() do\n assert(u:GetOwner()==pid,'foreign unit in budget observation')\n local id=u:GetID()\n assert(type(id)=='number' and id%1==0 and id>=0 and id<=4294967295 and not seen[id],\n        'invalid or duplicate budget unit')\n seen[id]=true;count=count+1\n assert(count<=1023,'unit order diagnostic roster bound exceeded')\nend\nreturn string.format('%d,%d,%d',pid,Game.GetCurrentGameTurn(),count)\n"

def parse_unit_order_budget(payload: bytes, player_id: int) -> dict:
    if type(payload) is not bytes or len(payload) > 64:
        raise ValueError('Invalid unit order budget response')
    fields = payload.split(b',')
    if len(fields) != 3 or any((not x.isdigit() or str(int(x)).encode('ascii') != x for x in fields)):
        raise ValueError('Malformed unit order budget response')
    pid, turn, count = map(int, fields)
    if type(player_id) is not int or pid != player_id or pid not in (0, 1) or (not 0 <= turn <= 4294967295) or (count > 1023):
        raise ValueError('Unit order budget outside diagnostic bounds')
    return {'player_id': pid, 'turn': turn, 'own_unit_count': count, 'action_budget': max(16, 4 * count + 4)}

def choose_relocation(catalog: dict, reachable: dict, blocked_unit_id: int) -> dict | None:
    """Choose another own unit only when no move exists for the requested unit."""
    if type(blocked_unit_id) is not int or not 0 <= blocked_unit_id <= 4294967295 or reachable.get('player_id') != catalog.get('player_id') or (reachable.get('observer_id') != catalog.get('player_id')) or (reachable.get('turn') != catalog.get('current_game_turn')):
        raise ValueError('Traffic decision has mismatched player, observer, turn or unit')
    units = {row['unit_id']: row for row in reachable['units']}
    if len(units) != len(reachable['units']):
        raise ValueError('Ambiguous own unit in traffic observation')
    if any((row['owner'] != catalog['player_id'] for row in units.values())):
        raise ValueError('Foreign unit in traffic observation')
    blocked = units.get(blocked_unit_id)
    if blocked is None or blocked['status'] != 'queried':
        return None
    if any((row['unit_id'] == blocked_unit_id for row in catalog['choices'])):
        raise ValueError('Traffic relocation cannot replace an available requested move')
    endpoints = set(blocked['plot_ids'])
    occupancy = Counter((row['current_plot_id'] for row in units.values()))
    for item in catalog['choices']:
        unit = units.get(item['unit_id'])
        if unit is None or item['source_plot_id'] != unit['current_plot_id']:
            raise ValueError('Movement catalogue and own unit locations disagree')
        if item['moves_remaining'] != unit['moves_remaining']:
            raise ValueError('Movement catalogue and own unit movement disagree')
        source = item['source_plot_id']
        if source != blocked['current_plot_id'] and source in endpoints and (occupancy[source] == 1) and (item['destination_plot_id'] not in endpoints):
            return choose(catalog, item['unit_id'], item['destination_plot_id'])
    return None

"""Read actual end-turn blockers for the current native player.

These observations do not replace the other ActionPanel checks (timer,
processing messages, ready units and city attacks) and do not authorize an
EndTurn action. No blocker is synthesized or cleared here.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
from pathlib import Path
_SHA = '2fef72283dfa9e84d87109e5f57934acf152ac323395746f669dcaf6ce48f68e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_turn_decisions.py')))).resolve().parents[1] / 'evidence/native-endturn-predicates' / f'{_SHA}.json'

def blocker_source(player_id, *, player_ids=(0, 1)):
    from civ6_host.runtime.native.native_diagnostic_roster import validate_player
    validate_player(player_id, player_ids)
    if hashlib.sha256(_resolve_resource_path(_PROOF).read_bytes()).hexdigest() != _SHA:
        raise RuntimeError('Native notification binding proof changed')
    return b'local pid=' + str(player_id).encode() + b"\nassert(Game.GetLocalPlayer()==pid,'blocker perspective differs from active player')\nlocal p=Players[pid]\nassert(p and p:IsTurnActive() and p:IsTurnActiveComplete(),'player not ready for decisions')\nassert(NotificationManager and type(NotificationManager.GetFirstEndTurnBlocking)=='function'\n and type(NotificationManager.GetAllEndTurnBlocking)=='function','native blocker getters absent')\nassert(EndTurnBlockingTypes and type(EndTurnBlockingTypes.NO_ENDTURN_BLOCKING)=='number',\n 'native blocker enum absent')\nlocal primary=NotificationManager.GetFirstEndTurnBlocking(pid)\nlocal all=NotificationManager.GetAllEndTurnBlocking(pid)\nassert(type(primary)=='number' and type(all)=='table','native blocker shape differs')\nlocal rows={}\nassert(#all<=128,'native blocker diagnostic capacity exceeded')\nfor _,value in ipairs(all) do\n assert(type(value)=='number' and value==math.floor(value),'nonintegral blocker')\n rows[#rows+1]=string.format('%.0f',value)\nend\nreturn string.format('%d|%d|%.0f|%.0f|%s',Game.GetCurrentGameTurn(),pid,primary,\n EndTurnBlockingTypes.NO_ENDTURN_BLOCKING,table.concat(rows,','))\n"

def parse_blockers(payload, player_id, expected_turn, *, player_ids=(0, 1)):
    from civ6_host.runtime.native.native_diagnostic_roster import validate_player
    validate_player(player_id, player_ids)
    if not isinstance(payload, bytes) or len(payload) > 8192:
        raise ValueError('Unbounded native blocker result')
    parts = payload.decode('ascii').split('|')
    if len(parts) != 5:
        raise ValueError('Native blocker result shape differs')
    turn, owner, primary, no_blocker = map(int, parts[:4])
    blockers = [int(x) for x in parts[4].split(',')] if parts[4] else []
    if owner != player_id or turn != expected_turn or owner not in player_ids or (not 0 <= turn <= 100000):
        raise ValueError('Native blocker perspective/turn mismatch')
    if len(blockers) > 128 or any((not -2 ** 31 <= v < 2 ** 32 for v in [primary, no_blocker, *blockers])):
        raise ValueError('Native blocker values exceed source integer bounds')
    return {'player_id': owner, 'turn': turn, 'primary': primary, 'all': blockers, 'no_blocker_value': no_blocker, 'has_primary_blocker': primary != no_blocker, 'normal_end_turn_legality_verified': False}

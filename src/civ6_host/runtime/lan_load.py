"""Read-only roster admission for the retained, exact Base LAN capture.

This module does not admit player actions, turn completion, or simultaneous
execution. It binds roster readback to the private capture994 invocation and
its before/after session receipts.
"""
from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping

from .resource_resolution import resolve_path

_INVOCATION_RELATIVE = Path('work/host-simultaneous/reference/capture-invocation.json')
_INVOCATION_SHA256 = '9e1d17bd4da44cbe362decfec7879af7c4e317282ea96b816d11babd391c9e69'
_INVOCATION_BYTES = 2649
_LAN_MODE = 20463770
_SIMULTANEOUS_PHASE = 2594944703
_NO_TIMER = 2769907115
_EXPECTED_PROCESS = (18404, 134376979317354116)


def roster_readback_source():
    """Return turn, map dimensions, and the sorted alive-major roster as a line.

    The source is intentionally generic within the bounds, but admission below
    accepts only the six-player roster in the exact retained LAN capture.
    """
    return b'''local function integer(v,lo,hi,name)
 assert(type(v)=="number" and v==math.floor(v) and v>=lo and v<=hi,"invalid "..name)
 return v
end
assert(Game and type(Game.GetCurrentGameTurn)=="function","loaded turn getter unavailable")
assert(Map and type(Map.GetGridSize)=="function","loaded map getter unavailable")
assert(PlayerManager and type(PlayerManager.GetAliveMajorIDs)=="function","loaded major roster unavailable")
local turn=integer(Game.GetCurrentGameTurn(),0,2147483647,"turn")
local w,h=Map.GetGridSize(); w=integer(w,1,16384,"width"); h=integer(h,1,16384,"height")
assert(w*h<=16384,"loaded map exceeds diagnostic bound")
local ids=PlayerManager.GetAliveMajorIDs()
assert(type(ids)=="table" and #ids>=1 and #ids<=64,"major roster outside bound")
table.sort(ids)
local rows={tostring(turn),tostring(w),tostring(h)}
local previous=-1
for i,id in ipairs(ids) do
 id=integer(id,0,63,"player id")
 assert(id>previous,"duplicate or unsorted major id")
 previous=id; rows[#rows+1]=tostring(id)
end
return table.concat(rows,"|")'''


def human_status_readback_source(player_ids):
    """Build a second bounded Lua read of IsHuman for already-read major IDs."""
    ids = _validated_ids(player_ids)
    literals = ','.join(str(value) for value in ids)
    return ('''local ids={%s}; local rows={}
for _,id in ipairs(ids) do
 local p=Players[id]
 assert(p~=nil and type(p.IsHuman)=="function","native player facade unavailable")
 local human=p:IsHuman()
 assert(type(human)=="boolean","invalid native IsHuman result")
 rows[#rows+1]=tostring(id).."="..(human and "1" or "0")
end
return table.concat(rows,"|")''' % literals).encode('ascii')


def _validated_ids(values):
    if type(values) not in (tuple, list) or not values or len(values) > 64:
        raise ValueError('LAN roster IDs are outside the native bounds')
    if any(type(value) is not int or not 0 <= value <= 63 for value in values):
        raise ValueError('LAN roster contains an invalid player ID')
    if list(values) != sorted(set(values)):
        raise ValueError('LAN roster IDs must be unique and sorted')
    return tuple(values)


def _load_json_reference(reference, *, label):
    if (not isinstance(reference, Mapping) or set(reference) != {'path', 'sha256', 'bytes'}
            or type(reference.get('path')) is not str
            or type(reference.get('sha256')) is not str
            or type(reference.get('bytes')) is not int
            or reference['bytes'] <= 0):
        raise ValueError('LAN capture is missing its pinned ' + label)
    path = resolve_path(Path(reference['path']))
    if path.stat().st_size != reference['bytes']:
        raise ValueError('LAN ' + label + ' byte count differs from the invocation receipt')
    from .native.native_source_cache import load_pinned_json
    return load_pinned_json(path, reference['sha256'])


def _capture_receipt():
    from .native.native_official_bundle import ROOT
    path = resolve_path(ROOT / _INVOCATION_RELATIVE)
    if path.stat().st_size != _INVOCATION_BYTES:
        raise ValueError('Pinned LAN capture invocation byte count differs')
    from .native.native_source_cache import load_pinned_json
    return load_pinned_json(path, _INVOCATION_SHA256)


def reference_state(captured_bundle):
    """Return the LAN session witness after binding it to this exact bundle."""
    invocation = _capture_receipt()
    process = invocation.get('process', {})
    if (invocation.get('status') != 'correlated_capture_unqualified'
            or (process.get('pid'), process.get('creation_filetime')) != _EXPECTED_PROCESS
            or invocation.get('expected_player_id') != 0
            or invocation.get('expected_turn') != 1
            or invocation.get('network_state_unchanged') is not True
            or invocation.get('training_eligible') is not False):
        raise ValueError('LAN invocation receipt is not the retained read-only capture')
    manifest = invocation.get('manifest')
    if not isinstance(manifest, Mapping) or type(manifest.get('sha256')) is not str:
        raise ValueError('LAN invocation has no exact capture manifest')
    origin_path = manifest.get('path')
    if type(origin_path) is not str or '/work/' not in origin_path.replace('\\', '/'):
        raise ValueError('LAN capture manifest path is not a retained work artifact')
    manifest_relative = 'work/' + origin_path.replace('\\', '/').split('/work/', 1)[1]
    if getattr(captured_bundle, 'reference', None) != (manifest_relative, manifest['sha256']):
        raise ValueError('LAN owner is not bound to the exact captured manifest')
    before = _load_json_reference(invocation.get('network_before'), label='before-session reference')
    after = _load_json_reference(invocation.get('network_after'), label='after-session reference')
    for item in (before, after):
        if (item.get('status') != 'read_only_reference_captured'
                or item.get('process') != process
                or item.get('game_actions_issued') != 0
                or item.get('actor_input') is not False
                or item.get('simultaneous_execution_qualified') is not False
                or item.get('inbox_restored') is not True):
            raise ValueError('LAN session receipt does not describe the exact read-only process')
    left, right = before.get('reference', {}), after.get('reference', {})
    if (left.get('state') != right.get('state')
            or left.get('observed_unchanged') is not True
            or right.get('observed_unchanged') is not True
            or left.get('atomic_snapshot') is not False
            or right.get('atomic_snapshot') is not False):
        raise ValueError('LAN before/after session states are not the retained unchanged pair')
    state = left.get('state', {})
    players = state.get('players')
    if (state.get('player_id') != 0 or state.get('turn') != 1
            or state.get('game_mode_u32') != _LAN_MODE
            or state.get('turn_phase_u32') != _SIMULTANEOUS_PHASE
            or state.get('turn_timer_u32') != _NO_TIMER
            or not isinstance(players, (tuple, list)) or len(players) != 6
            or any(not isinstance(p, Mapping) for p in players)
            or any(type(p.get('player_id')) is not int for p in players)
            or [p.get('player_id') for p in players] != list(range(6))
            or any(type(p.get('human')) is not bool for p in players)
            or [p.get('human') for p in players] != [True, False, False, False, False, False]
            or state.get('human_count') != 1):
        raise ValueError('LAN reference state differs from the exact six-major capture')
    return dict(invocation=invocation, state=state,
                major_player_ids=tuple(p['player_id'] for p in players),
                human_player_ids=(0,))


def _parse_roster(observed):
    if type(observed) is bytes:
        observed = observed.decode('ascii')
    if type(observed) is not str or len(observed) > 256:
        raise ValueError('LAN loaded roster readback is invalid')
    try:
        parts = observed.split('|')
        if len(parts) < 4:
            raise ValueError
        turn, width, height = (int(value) for value in parts[:3])
        ids = tuple(int(value) for value in parts[3:])
    except (ValueError, UnicodeError) as exc:
        raise ValueError('LAN loaded roster encoding is invalid') from exc
    ids = _validated_ids(ids)
    if not 0 <= turn <= 2147483647 or not 1 <= width <= 16384 or not 1 <= height <= 16384 or width * height > 16384:
        raise ValueError('LAN loaded turn/map values exceed diagnostic bounds')
    return turn, width, height, ids


def _parse_humans(values, expected_ids):
    expected_ids = _validated_ids(expected_ids)
    if type(values) is bytes:
        values = values.decode('ascii')
    # For the exact roster each row has an ID, '=', one flag and a separator
    # except after the final row. All 64 slots can require more than 256 bytes.
    size = sum(len(str(pid)) + 3 for pid in expected_ids) - 1
    if type(values) is not str or len(values) != size:
        raise ValueError('LAN native human-status readback is invalid')
    rows = values.split('|')
    if len(rows) != len(expected_ids):
        raise ValueError('LAN native human-status roster differs')
    humans = []
    for pid, row in zip(expected_ids, rows):
        if row not in (f'{pid}=0', f'{pid}=1'):
            raise ValueError('LAN native human-status roster differs')
        if row.endswith('1'):
            humans.append(pid)
    return tuple(humans)


def validate_loaded_roster(owner, observed, values):
    """Validate only the exact captured LAN roster and native human flags.

    ``observed`` is the first Lua query result; ``values`` is the second query
    result produced by :func:`human_status_readback_source`.
    """
    bundle = getattr(owner, 'captured_bundle', None)
    if bundle is None:
        raise ValueError('LAN owner has no exact captured bundle')
    reference = reference_state(bundle)
    invocation = reference['invocation']
    expected_ids = reference['major_player_ids']
    expected_humans = reference['human_player_ids']
    inputs = getattr(owner, 'inputs', None)
    if (inputs is None or getattr(inputs, 'official_bundle', None) != bundle.reference
            or getattr(getattr(inputs, 'profile', None), 'mode_name', None) != 'LAN'
            or (getattr(inputs, 'checkpoint', None) is None and getattr(bundle, 'initial_turn', None) != 1)):
        raise ValueError('LAN Load owner/profile/initial turn differs from the capture')
    host = getattr(owner, 'host', None)
    if getattr(host, 'configured_local_player_id', None) != 0:
        raise ValueError('LAN Load owner is not configured for captured local player 0')
    turn, width, height, ids = _parse_roster(observed)
    expected_turn = bundle.initial_turn if inputs.checkpoint is not None else 1
    if inputs.checkpoint is not None:
        from .network_checkpoint import validate_inputs
        validate_inputs(inputs)
    if turn != expected_turn or ids != expected_ids:
        raise ValueError('Loaded LAN turn or major roster differs from the capture')
    human_ids = _parse_humans(values, ids)
    if human_ids != expected_humans:
        raise ValueError('Loaded LAN native human status differs from the capture')
    return dict(turn=turn, width=width, height=height, major_player_ids=list(ids),
                human_player_ids=list(human_ids), human_status_native_verified=True,
                control_of_all_players_proven=False,
                simultaneous_execution_qualified=False,
                capture_manifest_sha256=invocation['manifest']['sha256'])

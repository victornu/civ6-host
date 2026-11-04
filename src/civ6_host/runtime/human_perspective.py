"""Collect an admitted human player's public view through the native UI API.

This diagnostic temporarily changes perspective using Core's automatic view
update, refreshes public caches, and restores the original view. The Lua
PlayerManager setter is NOT used: it also transfers human/AI control.
This is not a qualified simultaneous-turn scheduler. Unknown
native callbacks, changed turn state, or failed restoration poison the owner.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from civ6_host.runtime.paths import resource_root

_SOURCE_PINS = {
    'work/host-simultaneous/player-perspective-neutral-route.json': 'a6c99d4660fe48f9f90ee48f3bc51995b405e660b6b1250ef971f02e29bd4c3b',
    'evidence/native-local-player-perspective.json': '6d9924ed692afff7d6acd76e11619b05f95c08d613c14945461ff635495fcb52',
    'work/host-simultaneous/native-mode-getters.json': '65ba306c2d906affbe354bb828e7ba9cd9ba1de2717b0f7a7fe05b4bb18fc528',
    'work/host-simultaneous/perspective-routes.json': '210b3ee39a64dc2d36b1176762da61467b30027092b88c4a072f4c5f21511c5c',
    'evidence/native-world-configuration/62dd74236082b2da47fc5a34fd1b59276c1abc951ac7e717e053630a3660e31e.json': '62dd74236082b2da47fc5a34fd1b59276c1abc951ac7e717e053630a3660e31e',
    'evidence/native-diplomacy-configuration/84fce676a2438dd67001f44658e6ccaea00bd7dc7663bfcd8307f568214d83eb.json': '84fce676a2438dd67001f44658e6ccaea00bd7dc7663bfcd8307f568214d83eb',
}
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_CORE_IMAGE_BASE = 0x180000000
_PLAYERS = (0, 1, 2, 3)
_SLOT_TAKEN = 3


def source_pins() -> dict[str, str]:
    """Return the private static proofs required before a perspective switch."""
    return dict(_SOURCE_PINS)


def _read_proofs() -> dict[str, dict[str, Any]]:
    root = resource_root().resolve(strict=True)
    result = {}
    for relative, expected in _SOURCE_PINS.items():
        path = root / Path(relative)
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise RuntimeError(f'Perspective proof escaped or is missing: {relative}')
        raw = resolved.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise RuntimeError(f'Perspective proof hash changed: {relative}')
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f'Perspective proof is not valid JSON: {relative}') from exc
        if type(value) is not dict:
            raise RuntimeError(f'Perspective proof root is malformed: {relative}')
        result[relative] = value
    local = result['evidence/native-local-player-perspective.json']
    getters = result['work/host-simultaneous/native-mode-getters.json']
    routes = result['work/host-simultaneous/perspective-routes.json']
    if local.get('image', {}).get('sha256') != _CORE_SHA256:
        raise RuntimeError('Perspective setter proof names another Core image')
    if getters.get('perspective_setter_static_context', {}).get('core_image', {}).get('sha256') != _CORE_SHA256:
        raise RuntimeError('Perspective getter proof names another Core image')
    if routes.get('image', {}).get('sha256') != _CORE_SHA256:
        raise RuntimeError('Perspective route proof names another Core image')
    if getters.get('perspective_setter_static_context', {}).get('slot_status_and_scheduler_effect', {}).get('key_identity', {}).get('key_name') != 'SLOT_STATUS':
        raise RuntimeError('SLOT_STATUS identity proof is absent')
    if routes.get('runtime_qualified') is not False:
        raise RuntimeError('Perspective route report must remain statically qualified only')
    return result


def _instructions(body: Any):
    if type(body) is dict:
        row = body.get('va')
        encoded = body.get('bytes')
        if type(row) is str and type(encoded) is str:
            try:
                raw = bytes.fromhex(encoded)
                va = int(row, 16)
            except ValueError as exc:
                raise RuntimeError('Malformed instruction in perspective proof') from exc
            if not raw or len(raw) > 15:
                raise RuntimeError('Perspective proof contains an invalid instruction size')
            yield va, raw
        for key, value in body.items():
            if key not in ('va', 'bytes'):
                yield from _instructions(value)
    elif type(body) is list:
        for value in body:
            yield from _instructions(value)


def _live_instruction_set(proofs: dict[str, dict[str, Any]]) -> dict[int, bytes]:
    local = proofs['evidence/native-local-player-perspective.json']
    getters = proofs['work/host-simultaneous/native-mode-getters.json']
    routes = proofs['work/host-simultaneous/perspective-routes.json']
    ctx = getters['perspective_setter_static_context']
    bodies = [
        proofs['work/host-simultaneous/player-perspective-neutral-route.json']['game_getter'],
        local['functions']['automatic_local_player_update'],
        local['functions']['set_local_player_and_observer'],
        local['functions']['player_manager_set_local_player_callback'],
        local['functions']['player_manager_lua_registration'],
        ctx['old_player_helper_0x180223030'],
        ctx['new_player_helper_0x1802230e0'],
        ctx['direct_callees']['functions']['old_player_0x180112b40'],
        ctx['direct_callees']['functions']['new_player_0x180112bb0'],
        ctx['direct_callees']['functions']['old_player_0x1800536c0'],
        ctx['slot_status_and_scheduler_effect']['activation_predicate_0x1802193d0'],
        ctx['slot_status_and_scheduler_effect']['processor_state_flag_setter_0x180040f50'],
        routes['functions']['0x180112750'],
        routes['functions']['0x18010cb40'],
        routes['functions']['0x18010cb4d_valid_player_branch'],
    ]
    expected: dict[int, bytes] = {}
    for body in bodies:
        for va, raw in _instructions(body):
            prior = expected.get(va)
            if prior is not None and prior != raw:
                raise RuntimeError(f'Perspective proofs disagree at Core VA {va:#x}')
            expected[va] = raw
    if len(expected) < 100:
        raise RuntimeError('Perspective instruction proof set is incomplete')
    return expected


def verify_source(owner=None) -> dict[str, Any]:
    """Verify private source pins and, when supplied, the live Core code bytes."""
    proofs = _read_proofs()
    from civ6_host.runtime.native.native_world_configuration import verify_source as verify_world_configuration_source
    from civ6_host.runtime.native.native_diplomacy_configuration import verify_source as verify_diplomacy_configuration_source

    verify_diplomacy_configuration_source()
    verify_world_configuration_source()
    if owner is None:
        return {'source_pins': source_pins(), 'live_instruction_count': None}
    from civ6_host.runtime.provenance import verify_installation

    verify_installation()
    prefix = owner.prefix
    if prefix is None or prefix.core is None:
        raise RuntimeError('Perspective verification requires the loaded Core')
    base = prefix.core._handle
    read = prefix.actions.read
    if type(base) is not int or base <= 0 or not callable(read):
        raise RuntimeError('Perspective verification lacks the native Core reader')
    expected = _live_instruction_set(proofs)
    for va, raw in expected.items():
        address = base + va - _CORE_IMAGE_BASE
        if address <= 0 or read(address, len(raw)) != raw:
            raise RuntimeError(f'Loaded Core instruction differs from the pinned perspective proof at {va:#x}')
    return {'source_pins': source_pins(), 'live_instruction_count': len(expected)}


def _lua_snapshot_source(player_ids: tuple[int, ...]) -> bytes:
    ids = ','.join(str(pid) for pid in player_ids)
    source = f'''local ids={{{ids}}}
assert(Game and type(Game.GetCurrentGameTurn)=='function' and
       type(Game.GetLocalPlayer)=='function' and type(Game.GetLocalObserver)=='function',
       'native perspective getters unavailable')
assert(PlayerManager and type(PlayerManager.GetAliveMajorIDs)=='function',
       'native alive-major roster unavailable')
local alive=PlayerManager.GetAliveMajorIDs(); assert(type(alive)=='table' and #alive==#ids,
       'alive-major roster size changed')
local sortedAlive={{}}; for i,id in ipairs(alive) do sortedAlive[i]=id end
table.sort(sortedAlive)
local rows={{}}
for i,pid in ipairs(ids) do
  assert(sortedAlive[i]==pid,'alive-major roster changed')
  local p=Players and Players[pid]
  assert(p and type(p.IsAlive)=='function' and p:IsAlive()==true and
         type(p.IsHuman)=='function' and p:IsHuman()==true,
         'requested player is not a live human')
  assert(type(p.IsTurnActive)=='function' and type(p.IsTurnActiveComplete)=='function',
         'native player-turn getters unavailable')
  rows[i]=string.format('%d,%d,%d,%d',pid,p:IsAlive() and 1 or 0,
      p:IsTurnActive() and 1 or 0,p:IsTurnActiveComplete() and 1 or 0)
end
return string.format('%d|%d|%d|%s',Game.GetCurrentGameTurn(),Game.GetLocalPlayer(),
       Game.GetLocalObserver(),table.concat(rows,';'))
'''
    return source.encode('ascii')


def _native_view(owner, prefix, player_ids: tuple[int, ...]) -> dict[str, Any]:
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _lua_snapshot_source(player_ids), b'@human_perspective_state', capacity=512)
    if type(raw) is not bytes or len(raw) > 512:
        raise RuntimeError('Native perspective snapshot exceeded its bound')
    try:
        parts = raw.decode('ascii').split('|')
        if len(parts) != 4:
            raise ValueError
        turn, local, observer = map(int, parts[:3])
        player_rows = []
        for encoded in parts[3].split(';'):
            values = list(map(int, encoded.split(',')))
            if len(values) != 4 or any(value not in (0, 1) for value in values[1:]):
                raise ValueError
            player_rows.append({'player_id': values[0], 'alive': bool(values[1]), 'active': bool(values[2]), 'complete': bool(values[3]), 'slot_status': _SLOT_TAKEN})
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError('Native perspective snapshot is malformed') from exc
    if [row['player_id'] for row in player_rows] != list(player_ids) or any(not row['alive'] for row in player_rows):
        raise RuntimeError('Native human player roster changed')
    from civ6_host.runtime.native.native_world_configuration import read as read_world_configuration

    configuration = read_world_configuration(owner, player_ids)
    configured_players = configuration.get('players') if type(configuration) is dict else None
    if type(configured_players) is not dict or set(configured_players) != set(player_ids) or any(type(configured_players[pid]) is not dict or configured_players[pid].get('is_human') is not True for pid in player_ids):
        raise RuntimeError('Native player configuration does not identify every actor as SS_TAKEN')
    for row in player_rows:
        row['slot_status'] = 3
    return {'turn': turn, 'local_player': local, 'observer': observer, 'players': player_rows, 'configuration': configuration}


def _flags(prefix) -> tuple[int, ...]:
    raw = prefix.actions.read(prefix.core._handle + 9156608, 4)
    if type(raw) is not bytes or len(raw) != 4 or any(value not in (0, 1) for value in raw):
        raise RuntimeError('Native turn-processor flags changed representation')
    return tuple(raw)


def _require_idle(owner, prefix, baseline_control=None):
    control = owner.control(empty=True)
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Perspective routing requires empty native queues')
    if baseline_control is not None:
        if set(control) != set(baseline_control):
            raise RuntimeError('Perspective routing changed native control fields')
        for key in ('pending_count', 'notification_counter', 'metadata_counter'):
            if control.get(key) != baseline_control.get(key):
                raise RuntimeError('Perspective routing changed native pending or notification state')
        if control.get('sequence') != control.get('consumed') or control.get('consumed', -1) < baseline_control.get('consumed', 0):
            raise RuntimeError('Perspective callback left deferred work unconsumed')
    return control


def _callback_marker(prefix):
    deferred = prefix.deferred_events
    unregistered = getattr(deferred, 'unregistered_player_events', None)
    if type(unregistered) is not list:
        raise RuntimeError('Native unregistered-callback diagnostics are unavailable')
    if unregistered:
        raise RuntimeError('Native deferred queue contains an unregistered player callback')
    return tuple(unregistered)


def _emit_private(owner, *, proof, before, after, requested_player_id, phase, switched):
    owner.emit(
        'human_perspective_view_diagnostic',
        phase=phase,
        player_id=requested_player_id,
        original_local_player=before['local_player'],
        original_observer=before['observer'],
        restored_local_player=after['local_player'],
        current_observer=after['observer'],
        current_game_turn=after['turn'],
        human_slot_statuses=[row['slot_status'] for row in after['players']],
        player_activity=[{'player_id': row['player_id'], 'active': row['active'], 'complete': row['complete']} for row in after['players']],
        processor_flags=list(_flags(owner.prefix)),
        queues_empty=True,
        perspective_switched=switched,
        notification_enabled=True,
        known_deferred_events_drained=True,
        unknown_callback_observed=False,
        game_updates=0,
        actions_applied=0,
        native_perspective_neutrality_proven=False,
        source_pins=proof['source_pins'],
        loaded_core_instruction_count=proof['live_instruction_count'],
        eligible_for_training=False,
    )


def _poison(owner, reason: str) -> None:
    owner.poisoned = True
    owner.stage = 'poisoned'
    owner.busy = False
    try:
        owner.emit('human_perspective_view_refused', reason=reason, perspective_state_uncertain=True, eligible_for_training=False)
    except BaseException:
        pass


def _switch(prefix, local_player: int, observer_player: int) -> None:
    import ctypes as C
    if type(local_player) is not int or local_player not in _PLAYERS or observer_player != local_player:
        raise ValueError('Automatic perspective route requires the same live local/observer ID')
    # Actual instructions are checked in verify_source(owner). This is the
    # native turn-activation view path, retaining its notifications, not the
    # Lua setter that changes the old/new players' SLOT_STATUS.
    base = prefix.core._handle
    game = C.CFUNCTYPE(C.c_void_p)(base + 0x2218e0)()
    if not game:
        raise RuntimeError('Native perspective Game singleton is null')
    changed = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_int)(base + 0x2233a0)(game, local_player)
    if changed != 1:
        raise RuntimeError('Native automatic perspective update refused')


def _drain_and_publish(owner, prefix) -> None:
    # Only the existing admitted empty-receiver/cache-update routes are drained.
    # Any unsupported callback raises here and causes the owner to be poisoned.
    prefix.deferred_events.drain_empty_receivers()
    if prefix.deferred_events.pending or prefix.actions.pending:
        raise RuntimeError('Perspective callback left an unconsumed native event or action')
    if prefix.deferred_events.unregistered_player_events:
        raise RuntimeError('Perspective callback reached an unregistered player-event receiver')
    publisher = prefix.view_publisher
    if publisher is None or publisher._closed or publisher is not owner.prefix.view_publisher:
        raise RuntimeError('Perspective refresh lacks the retained public cache publisher')
    publisher.publish()
    _require_idle(owner, prefix)


def collect_player_view(owner, player_id: int, *, player_ids: tuple[int, ...]):
    """Collect one live human's public observation and map at the current turn.

    The only accepted owner is an admitted four-human Base session at its
    official decision-ready boundary. Perspective notifications stay enabled.
    No action or Game update is issued. Successful calls restore the initial
    local player and observer before returning.
    """
    if type(player_ids) is not tuple or player_ids != _PLAYERS:
        raise ValueError('Human perspective collection requires the exact four-player roster')
    if type(player_id) is not int or player_id not in player_ids:
        raise ValueError('Requested player is outside the live human roster')
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_official_postload import validate_owner
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native import native_saved_player_map as player_map

    inputs = validate_owner(owner, stage='official-hotseat-decision-ready')
    if inputs.profile is not HOTSEAT_FOUR_PROFILE or type(owner.loaded_roster) is not bytes:
        raise RuntimeError('Perspective collection requires the admitted Base4 human session')
    try:
        roster = tuple(map(int, owner.loaded_roster.decode('ascii').split('|')))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError('Loaded Base4 roster is malformed') from exc
    if len(roster) < 4 or roster[3:] != player_ids:
        raise RuntimeError('Loaded Base4 roster differs from the requested human roster')
    prefix = owner.prefix
    if prefix is None or type(getattr(owner, 'hotseat_actor', None)) is not int or owner.hotseat_actor not in player_ids or type(getattr(owner, 'hotseat_turn', None)) is not int:
        raise RuntimeError('Official hotseat decision identity is unavailable')
    if owner.busy or owner.poisoned or owner.destroyed:
        raise RuntimeError('Perspective collection owner is busy, poisoned or closed')

    proof = verify_source(owner)
    owner.check_thread()
    owner.busy = True
    switched = False
    switch_committed = False
    restored = False
    restore_attempted = False
    restore_verified = False
    mutation_attempted = False
    try:
        control_before = _require_idle(owner, prefix)
        callbacks_before = _callback_marker(prefix)
        flags_before = _flags(prefix)
        native_before = _native_view(owner, prefix, player_ids)
        if native_before['turn'] != owner.hotseat_turn:
            raise RuntimeError('Perspective collection turn differs from the ready owner')
        if native_before['local_player'] != owner.hotseat_actor or native_before['observer'] != owner.hotseat_actor:
            raise RuntimeError('Perspective collection did not start from the retained human actor')
        actor_rows = [row for row in native_before['players'] if row['player_id'] == owner.hotseat_actor]
        if len(actor_rows) != 1 or actor_rows[0]['active'] is not True or actor_rows[0]['complete'] is not True:
            raise RuntimeError('Owner is not at an active human decision boundary')
        if any(row['active'] for row in native_before['players'] if row['player_id'] != owner.hotseat_actor):
            raise RuntimeError('Another human is active at the decision-ready boundary')

        if player_id != native_before['local_player']:
            mutation_attempted = True
            _switch(prefix, player_id, player_id)
            switched = True
            _drain_and_publish(owner, prefix)
            target_native = _native_view(owner, prefix, player_ids)
            if target_native['turn'] != native_before['turn'] or target_native['local_player'] != player_id or target_native['observer'] != player_id:
                raise RuntimeError('Native perspective target or turn changed unexpectedly')
            if target_native['players'] != native_before['players'] or target_native['configuration'] != native_before['configuration']:
                raise RuntimeError('Perspective setter changed human slots or activity flags')
            _require_idle(owner, prefix, control_before)
            if _flags(prefix) != flags_before or _callback_marker(prefix) != callbacks_before:
                raise RuntimeError('Perspective setter changed native processor flags or queues')
            switch_committed = True
        else:
            target_native = native_before

        observation = observe_player(prefix.runtime, prefix.ui_child, player_id)
        current_player_map = player_map.observe(prefix, observation)
        after_observation = _native_view(owner, prefix, player_ids)
        if after_observation['turn'] != native_before['turn'] or after_observation['local_player'] != player_id or after_observation['observer'] != player_id:
            raise RuntimeError('Perspective or turn changed during public view collection')
        if after_observation['players'] != native_before['players'] or after_observation['configuration'] != native_before['configuration']:
            raise RuntimeError('Public view collection changed player slot or activity state')
        _require_idle(owner, prefix, control_before)
        if _flags(prefix) != flags_before or _callback_marker(prefix) != callbacks_before:
            raise RuntimeError('Public view collection changed native flags or queues')

        # Restore before releasing ownership, even if later validation fails.
        if switched:
            restore_attempted = True
            _switch(prefix, native_before['local_player'], native_before['observer'])
            _drain_and_publish(owner, prefix)
            restored = True
        final_native = _native_view(owner, prefix, player_ids)
        if final_native != native_before or _flags(prefix) != flags_before:
            raise RuntimeError('Perspective restoration did not preserve the original boundary')
        _require_idle(owner, prefix, control_before)
        if _callback_marker(prefix) != callbacks_before:
            raise RuntimeError('Perspective restoration left an unknown player callback')
        restore_verified = True
        if getattr(owner, 'hotseat_actor', None) != native_before['local_player'] or owner.stage != 'official-hotseat-decision-ready':
            raise RuntimeError('Perspective collection changed the retained decision owner')
        own_turn = next(row for row in final_native['players'] if row['player_id'] == player_id)
        result = {
            'observation': observation,
            'player_map': current_player_map,
            'player_turn': {'active': own_turn['active'], 'turn_active_complete': own_turn['complete']},
        }
        if set(result) != {'observation', 'player_map', 'player_turn'}:
            raise RuntimeError('Human perspective public result shape changed')
        _emit_private(owner, proof=proof, before=native_before, after=final_native, requested_player_id=player_id, phase='restored', switched=switched)
        return result
    except BaseException as exc:
        if switched and switch_committed and not restore_attempted:
            try:
                current = _native_view(owner, prefix, player_ids)
                if current['turn'] != native_before['turn'] or current['local_player'] != player_id or current['observer'] != player_id or current['players'] != native_before['players'] or _flags(prefix) != flags_before:
                    raise RuntimeError('Cannot safely restore after the target boundary changed')
                restore_attempted = True
                _switch(prefix, native_before['local_player'], native_before['observer'])
                _drain_and_publish(owner, prefix)
                restored = True
                restored_state = _native_view(owner, prefix, player_ids)
                if restored_state != native_before or _flags(prefix) != flags_before:
                    raise RuntimeError('Perspective error-path restoration failed verification')
                _require_idle(owner, prefix, control_before)
                if _callback_marker(prefix) != callbacks_before:
                    raise RuntimeError('Perspective error-path restore left an unknown callback')
                restore_verified = True
            except BaseException as restore_error:
                _poison(owner, f'perspective restore failed: {type(restore_error).__name__}')
        if mutation_attempted:
            outcome = 'restored_but_failed_verification' if restore_verified else 'restore_unverified'
            _poison(owner, f'perspective mutation failed ({outcome}): {type(exc).__name__}')
        raise
    finally:
        if not owner.poisoned:
            owner.busy = False


"""Explicit LAN turn requests and bounded calls to the official game update.

No player order, AI decision, readiness flag or completion message is invented.
This local command transport does not claim EXE network scheduling equivalence.
"""
from __future__ import annotations
from contextlib import nullcontext
from time import perf_counter

from .callback_timing import measure
from .configuration_profiles import BASE_CORE_SHA256, XP2_CORE_SHA256


class BaseTurnBoundary:
    """Owner-specific checks around the one shared native turn algorithm."""
    core_sha256 = BASE_CORE_SHA256

    def state(self, owner):
        from .network_owner import state
        return state(owner)

    def controls(self, owner, session, player_id):
        return controls(owner, session, player_id)

    def force_available(self, owner):
        from .network_ui import force_available
        return force_available(owner)

    def refusal(self, owner, action, before, player_id):
        if action['kind']=='unready_turn':
            if not before['can_unready'] or before['timer_elapsed'] is not False:
                return 'unready_ui_predicate_unavailable'
        else:
            if not before['active'] or not before['active_complete'] or before['can_unready']:
                return 'native_turn_state_changed'
            if action['kind']=='force_end_turn' and not self.force_available(owner):
                return 'native_forced_turn_gate_unavailable'
        return None

    def retain(self, owner):
        from .network_dialogue import retain
        return retain(owner)

    def control(self, owner):
        from .network_dialogue import control
        return control(owner)

    def verify_update(self, owner):
        from .native.native_ai_round_pump import verify_source_evidence
        verify_source_evidence()

    def turn_segment(self, owner, player_id, turn):
        return None

    def unchanged_request(self, owner, action, before, after):
        raise RuntimeError('Native turn request was delivered but its effect is unresolved')


BASE_BOUNDARY = BaseTurnBoundary()

def read_activity(owner, *, core_sha256=BASE_CORE_SHA256):
    from .lan_load import _validated_ids
    from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
    if core_sha256 == BASE_CORE_SHA256:
        from .native.native_endturn_gate import verify_source
        verify_source()
    elif core_sha256 in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        from .xp1_status_profiles import bind_owner
        backend = owner.backend
        if backend.load_abi.core_sha256!=core_sha256:
            raise ValueError('Native activity reader belongs to another engine')
        bind_owner(backend, backend.core, backend.runtime.read)
    else:
        raise ValueError('Unknown engine for native LAN activity')
    ids = _validated_ids(owner.network_reference['major_player_ids'])
    values = ','.join(map(str, ids)).encode('ascii')
    source = b'local ids={' + values + b'''}
local function bit(v) assert(type(v)=='boolean','turn predicate type'); return v and 1 or 0 end
local function integer(v,limit)
 assert(type(v)=='number' and v%1==0 and v>=0 and v<=limit,'turn activity identity')
 return v
end
local rows={}
for _,id in ipairs(ids) do
 local p=Players[id]; assert(p,'missing captured player')
 rows[#rows+1]=string.format('%d,%d,%d,%d',id,bit(p:IsTurnActive()),
   bit(p:IsTurnActiveComplete()),bit(p:CanUnreadyTurn()))
end
return string.format('%d|%d|%d|%s',integer(Game.GetCurrentGameTurn(),100000),
 integer(Game.GetLocalPlayer(),63),integer(Game.GetLocalObserver(),63),table.concat(rows,';'))
'''
    p = owner.prefix
    raw = p.runtime.evaluate_text(p.ui_child, source, b'@lan_turn_activity', capacity=4096)
    return parse_activity(raw, ids)


def parse_activity(raw, ids):
    from .lan_load import _validated_ids
    ids = _validated_ids(ids)
    if type(raw) is not bytes or not 0 < len(raw) < 4096:
        raise ValueError('Invalid native turn activity payload')
    turn, local, observer, payload = raw.decode('ascii').split('|')
    if any(not x.isdigit() or str(int(x)) != x for x in (turn, local, observer)):
        raise ValueError('Noncanonical native turn identity')
    turn, local, observer = map(int, (turn, local, observer))
    if turn > 100000 or local > 63 or observer > 63:
        raise ValueError('Native turn identity is outside the captured profile bounds')
    rows = []
    for row in payload.split(';'):
        parts = row.split(',')
        if len(parts) != 4 or any(not s.isdigit() or str(int(s)) != s for s in parts):
            raise ValueError('Malformed native activity row')
        pid, active, complete, unready = map(int, parts)
        if any(x not in (0, 1) for x in (active, complete, unready)):
            raise ValueError('Invalid native Boolean predicate')
        rows.append(dict(player_id=pid, active=bool(active), active_complete=bool(complete),
                         can_unready=bool(unready)))
    if tuple(r['player_id'] for r in rows) != ids:
        raise ValueError('Native activity does not match captured roster')
    return dict(turn=turn, local_player_id=local, observer_id=observer, rows=rows)


def controls(owner, session, player_id):
    row = owner.network_turn_rows[player_id]
    from .network_timer import read
    timer_elapsed = read(owner)
    return dict(schema='civ6-host.turn-controls.v1', player_id=player_id,
                turn=session['turn'], active=row['active'],
                active_complete=row['active_complete'], can_unready=row['can_unready'],
                timer_elapsed=timer_elapsed)


def _publish(owner):
    started = perf_counter()
    owner.prefix.deferred_events.drain_empty_receivers()
    drained = perf_counter()
    owner.prefix.view_publisher.publish()
    return drained-started, perf_counter()-drained


def _completion(owner, *, core_sha256=BASE_CORE_SHA256):
    """Consume only a captured completion in its already-proven native phase."""
    p = owner.prefix
    if not p.actions.pending:
        return
    from .native.native_game_turn_complete import decode_archive
    if len(p.actions.pending) != 1:
        raise RuntimeError('LAN update has an unqualified command sequence')
    decoded = (decode_archive(p.actions.pending[0]) if core_sha256 == BASE_CORE_SHA256
               else decode_archive(p.actions.pending[0], core_sha256=core_sha256))
    local = owner.network_reference['state']['player_id']
    if decoded['player_id'] != local:
        raise RuntimeError('Native completion does not identify the local host player')
    p.actions.deliver_completed_round_echo(local,
        player_ids=owner.network_reference['major_player_ids'])
    _publish(owner)


def submit(owner, action, player_id, *, boundary=BASE_BOUNDARY):
    if type(action) is not dict or set(action)!={'kind'} or action['kind'] not in ('end_turn','force_end_turn','unready_turn'):
        raise ValueError('Unsupported network turn request')
    before_session = boundary.state(owner)
    before = boundary.controls(owner, before_session, player_id)
    p = owner.prefix
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Turn request found undrained native work')
    refusal=boundary.refusal(owner,action,before,player_id)
    if refusal is not None:
        return dict(status='refused',reason=refusal,requested_action=action)
    before_segment = boundary.turn_segment(owner, player_id, before['turn'])
    if action['kind'] == 'unready_turn':
        emitted = p.actions.request_unready_turn(player_id,
            player_ids=owner.network_reference['major_player_ids'])
        if not emitted['queued']:
            return dict(status='refused', reason='native_unready_not_queued', requested_action=action)
    elif action['kind'] in ('end_turn', 'force_end_turn'):
        forced = action['kind'] == 'force_end_turn'
        p.actions.request_end_turn(player_id,
            player_ids=owner.network_reference['major_player_ids'], user_forced=forced)
    else:
        raise ValueError('Unsupported network turn request')
    # Use the official receive queue/dispatcher and preserve its exact archive.
    p.actions.deliver_one()
    _publish(owner)
    _completion(owner, core_sha256=boundary.core_sha256)
    after_session = boundary.state(owner)
    after = boundary.controls(owner, after_session, player_id)
    after_segment = boundary.turn_segment(owner, player_id, after['turn'])
    if (before_segment is None) != (after_segment is None):
        raise RuntimeError('Turn-segment observation scope changed during request')
    segment_changed = before_segment is not None and before_segment != after_segment
    unchanged = same_readiness(before, after) and not segment_changed
    receipt = (boundary.unchanged_request(owner, action, before, after) if unchanged
               else dict(status='completed', reason=('endturn_segment_changed' if segment_changed else None),
                         requested_action=action))
    boundary.retain(owner)
    boundary.control(owner)
    segment_trace = ({} if before_segment is None else dict(before_turn_segment=before_segment,
        after_turn_segment=after_segment, turn_segment_changed=segment_changed))
    owner.emit('official_lan_turn_request_submitted' if unchanged else 'official_lan_turn_request_effect', player_id=player_id,
        action=action, before=before, after=after,
        network_ack_inferred=False, turn_advanced=after['turn'] > before['turn'],
        strategic_training_ready=False, **segment_trace)
    return receipt


def same_readiness(before, after):
    """Compare command effects independently of the timer's own progress."""
    return all(before[key] == after[key]
               for key in ('turn', 'active', 'active_complete', 'can_unready'))


def advance(owner, *, boundary=BASE_BOUNDARY):
    """One explicit pump, without waiting for or choosing another actor."""
    started = perf_counter()
    boundary.verify_update(owner)
    p = owner.prefix
    if boundary.retain(owner):
        return
    _completion(owner, core_sha256=boundary.core_sha256)
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('LAN update cannot discard pending native work')
    reader_scope = nullcontext()
    cache_source_scope = nullcontext()
    if boundary.core_sha256 == XP2_CORE_SHA256:
        from .xp2_cache_source import update_source_scope
        from .xp2_preload_source import event_reader_scope
        reader = p.event_arguments.reader
        reader_scope = event_reader_scope(reader.base, reader.read)
        cache_source_scope = update_source_scope()
    before_update = perf_counter()
    # The FIFO consumes the same synchronous native update. Its per-record
    # Player/context checks need the same immutable source proof, while still
    # rereading live ownership, slots and locks on every call. Keep the reader
    # scope and callback timing limited to the actual GameCore update.
    with cache_source_scope:
        with measure() as callback_timing, reader_scope:
            p.actions.update_game_once()
        after_update = perf_counter()
        drain_seconds, refresh_seconds = _publish(owner)
    after_publication = perf_counter()
    _completion(owner, core_sha256=boundary.core_sha256)
    after_completion = perf_counter()
    boundary.retain(owner)
    boundary.control(owner)
    owner.emit('native_lan_update_timing',
               update_seconds=after_update-before_update,
               before_update_seconds=before_update-started,
               publication_seconds=after_publication-after_update,
               publication_fifo_drain_seconds=drain_seconds,
               publication_cache_refresh_seconds=refresh_seconds,
               completion_seconds=after_completion-after_publication,
               boundary_readback_seconds=perf_counter()-after_completion,
               guarded_host_callbacks=callback_timing.report(),
               update_includes_host_callbacks=True)

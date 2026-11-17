"""Explicit LAN turn requests and bounded calls to the official game update.

No player order, AI decision, readiness flag or completion message is invented.
This local command transport does not claim EXE network scheduling equivalence.
"""
from __future__ import annotations
from contextlib import nullcontext
from time import perf_counter

from .callback_timing import measure
from .configuration_profiles import BASE_CORE_SHA256, XP2_CORE_SHA256

_NO_CURRENT_SEGMENT = 0xffffffff


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

    def reactivation_owner(self, owner):
        return None

    def unchanged_request(self, owner, action, before, after, *, reactivated=False):
        raise RuntimeError('Native turn request was delivered but its effect is unresolved')


BASE_BOUNDARY = BaseTurnBoundary()

def read_activity(owner, *, core_sha256=BASE_CORE_SHA256, inactive_player_id=None):
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
    if inactive_player_id is not None and (
            core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256)
            or type(inactive_player_id) is not int or inactive_player_id not in ids):
        raise ValueError('Inactive LAN session metadata requires an expansion roster member')
    values = ','.join(map(str, ids)).encode('ascii')
    actor = b'nil' if inactive_player_id is None else str(inactive_player_id).encode('ascii')
    source = b'local ids={' + values + b'}\nlocal inactivePlayer=' + actor + b'''
local function bit(v) assert(type(v)=='boolean','turn predicate type'); return v and 1 or 0 end
local function integer(v,limit)
 assert(type(v)=='number' and v%1==0 and v>=0 and v<=limit,'turn activity identity')
 return v
end
local turn=integer(Game.GetCurrentGameTurn(),100000)
local localID=integer(Game.GetLocalPlayer(),63)
local observer=Game.GetLocalObserver()
if inactivePlayer~=nil then
 local neutral=PlayerTypes and type(PlayerTypes.OBSERVER)=='number' and
               observer==PlayerTypes.OBSERVER
 assert(localID==inactivePlayer and (observer==localID or neutral),'inactive LAN actor changed')
 local actor=Players[localID]
 assert(actor and actor:WasEverAlive()==true and actor:IsAlive()==false,'LAN actor is not inactive')
else
 observer=integer(observer,63)
end
local rows={}
for _,id in ipairs(ids) do
 local p=Players[id]; assert(p,'missing captured player')
 if inactivePlayer~=nil then
  rows[#rows+1]=string.format('%d,%d',id,bit(p:IsTurnActive()))
 else
  rows[#rows+1]=string.format('%d,%d,%d,%d',id,bit(p:IsTurnActive()),
    bit(p:IsTurnActiveComplete()),bit(p:CanUnreadyTurn()))
 end
end
assert(Game.GetCurrentGameTurn()==turn and Game.GetLocalPlayer()==localID and
       Game.GetLocalObserver()==observer,'LAN activity changed during collection')
if inactivePlayer~=nil then
 assert(Players[localID]:WasEverAlive()==true and Players[localID]:IsAlive()==false,
        'LAN inactive actor changed during collection')
end
return string.format('%d|%d|%s|%s',turn,localID,
 inactivePlayer~=nil and 'inactive' or string.format('%d',observer),table.concat(rows,';'))
'''
    p = owner.prefix
    raw = p.runtime.evaluate_text(p.ui_child, source, b'@lan_turn_activity', capacity=4096)
    return parse_activity(raw, ids, inactive_player_id=inactive_player_id)


def parse_activity(raw, ids, *, inactive_player_id=None):
    from .lan_load import _validated_ids
    ids = _validated_ids(ids)
    if type(raw) is not bytes or not 0 < len(raw) < 4096:
        raise ValueError('Invalid native turn activity payload')
    turn, local, observer, payload = raw.decode('ascii').split('|')
    inactive = inactive_player_id is not None
    if inactive and (type(inactive_player_id) is not int or inactive_player_id not in ids):
        raise ValueError('Invalid inactive LAN actor')
    if inactive != (observer == 'inactive'):
        raise ValueError('Native activity uses another observation mode')
    numeric = (turn, local) if inactive else (turn, local, observer)
    if any(not x.isdigit() or str(int(x)) != x for x in numeric):
        raise ValueError('Noncanonical native turn identity')
    turn, local = int(turn), int(local)
    observer = None if inactive else int(observer)
    if turn > 100000 or local > 63 or (observer is not None and observer > 63):
        raise ValueError('Native turn identity is outside the captured profile bounds')
    rows = []
    for row in payload.split(';'):
        parts = row.split(',')
        if len(parts) != (2 if inactive else 4) or any(not s.isdigit() or str(int(s)) != s for s in parts):
            raise ValueError('Malformed native activity row')
        pid, *flags = map(int, parts)
        if any(x not in (0, 1) for x in flags):
            raise ValueError('Invalid native Boolean predicate')
        item = dict(player_id=pid, active=bool(flags[0]))
        if not inactive:
            item.update(active_complete=bool(flags[1]), can_unready=bool(flags[2]))
        rows.append(item)
    if tuple(r['player_id'] for r in rows) != ids:
        raise ValueError('Native activity does not match captured roster')
    if inactive and (local != inactive_player_id or next(r['active'] for r in rows if r['player_id'] == local)):
        raise ValueError('Inactive LAN actor is foreign or active')
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


def _completion(owner, *, core_sha256=BASE_CORE_SHA256, perspective_player=None):
    """Consume only a captured completion in its already-proven native phase."""
    p = owner.prefix
    if not p.actions.pending:
        return
    from .native.native_game_turn_complete import decode_archive
    if len(p.actions.pending) != 1:
        raise RuntimeError('LAN update has an unqualified command sequence')
    decoded = (decode_archive(p.actions.pending[0]) if core_sha256 == BASE_CORE_SHA256
               else decode_archive(p.actions.pending[0], core_sha256=core_sha256))
    local = (owner.network_reference['state']['player_id'] if perspective_player is None
             else perspective_player)
    if decoded['player_id'] != local:
        raise RuntimeError('Native completion does not identify the expected local player')
    p.actions.deliver_completed_round_echo(local,
        player_ids=owner.network_reference['major_player_ids'])
    _publish(owner)


TURN_REQUESTS = frozenset(('end_turn', 'force_end_turn', 'unready_turn'))


def submit(owner, action, player_id, *, boundary=BASE_BOUNDARY, borrowed_xp2=False):
    if (type(action) is not dict or set(action) != {'kind'}
            or type(action['kind']) is not str or action['kind'] not in TURN_REQUESTS):
        raise ValueError('Unsupported network turn request')
    if type(borrowed_xp2) is not bool or (borrowed_xp2 and boundary.core_sha256 != XP2_CORE_SHA256):
        raise ValueError('A borrowed turn request requires the XP2 turn boundary')
    perspective_player = None
    if borrowed_xp2:
        from .xp2_human_perspective import verify_turn_completion_player
        verify_turn_completion_player(owner, player_id)
        perspective_player = player_id
    before_session = boundary.state(owner)
    before = boundary.controls(owner, before_session, player_id)
    p = owner.prefix
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Turn request found undrained native work')
    refusal=boundary.refusal(owner,action,before,player_id)
    if refusal is not None:
        return dict(status='refused',reason=refusal,requested_action=action)
    before_segment = boundary.turn_segment(owner, player_id, before['turn'])
    controller = (None if action['kind']=='unready_turn' else boundary.reactivation_owner(owner))
    reactivation_count = None if controller is None else controller.reactivation_count
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
    options = {'perspective_player': perspective_player} if borrowed_xp2 else {}
    _completion(owner, core_sha256=boundary.core_sha256, **options)
    after_session = boundary.state(owner)
    after = boundary.controls(owner, after_session, player_id)
    after_segment = boundary.turn_segment(owner, player_id, after['turn'])
    if (before_segment is None) != (after_segment is None):
        raise RuntimeError('Turn-segment observation scope changed during request')
    # The XP2 getter returns -1 outside a named segment. Its presence or
    # disappearance alone does not prove that this command changed readiness.
    segment_changed = (before_segment not in (None, _NO_CURRENT_SEGMENT)
                       and after_segment not in (None, _NO_CURRENT_SEGMENT)
                       and before_segment != after_segment)
    unchanged = same_readiness(before, after) and not segment_changed
    segment_trace = ({} if before_segment is None else dict(before_turn_segment=before_segment,
        after_turn_segment=after_segment, turn_segment_changed=segment_changed))
    if unchanged and before_segment is not None:
        owner.emit('official_lan_turn_request_readback_unchanged', player_id=player_id,
            action=action, before=before, after=after, **segment_trace)
    if unchanged:
        reactivated = controller is not None and controller.reactivated_since(reactivation_count,player_id)
        receipt = boundary.unchanged_request(owner,action,before,after,reactivated=reactivated)
    else:
        receipt = dict(status='completed', reason=('endturn_segment_changed' if segment_changed else None),
                       requested_action=action)
    boundary.retain(owner)
    boundary.control(owner)
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

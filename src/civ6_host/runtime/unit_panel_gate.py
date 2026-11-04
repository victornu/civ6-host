"""Source-bound UnitPanel processing gate; no gameplay state or rules.

The deferred consumer observes actual records after native queue validation.
Only the normal Base LAN UnitPanel route is admitted by network_ui. Collecting
this state does not admit Hotseat/unpause, other UI profiles or Lua subscribers.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

SOURCE = ('work/host-simultaneous/unit-work/unit-panel-event-source.json',
          '678bdcb8b089d0c6abda2517b444220c4a63087cffdb378871afce3c8f003cbf')


def source_files():
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    path = resolve_path(resource_root() / SOURCE[0])
    raw = path.read_bytes()
    if len(raw) > 16384 or hashlib.sha256(raw).hexdigest() != SOURCE[1]:
        raise ValueError('UnitPanel source proof changed')
    proof = json.loads(raw)
    if (proof['schema'] != 'civ6-host.unit-panel-event-source.v1'
            or proof['contract']['player_offset'] != 84
            or proof['contract']['player_type'] != 'signed_i32'
            or proof['contract']['first_time_offset'] != 88):
        raise ValueError('UnitPanel source contract differs')
    pins = {str(path): SOURCE[1]}
    for row in [proof['image'], *proof['sources']]:
        p = resolve_path(Path(row['path']))
        if hashlib.sha256(p.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('UnitPanel source dependency changed: ' + str(p))
        pins[str(p)] = row['sha256']
    return pins


def decode_record(record):
    """Decode the proven callback arguments, without invoking a guessed ABI."""
    if type(record) is not bytes or len(record) < 8:
        raise ValueError('Invalid deferred record for UnitPanel gate')
    size, kind = struct.unpack_from('<II', record)
    if kind not in (15, 16):
        return None
    if size != 96 or len(record) != 96:
        raise ValueError('Invalid PlayerTurn record size')
    sequence = struct.unpack_from('<I', record, 8)[0]
    if sequence == 0 or sequence != struct.unpack_from('<I', record, 80)[0]:
        raise ValueError('PlayerTurn sequence differs from payload')
    return dict(sequence=sequence, player_id=struct.unpack_from('<i', record, 84)[0],
        name='PlayerTurnActivated' if kind == 15 else 'PlayerTurnDeactivated',
        processing_allowed=kind == 15, first_time=bool(record[88]) if kind == 15 else None)


class UnitPanelEventState:
    """Mirror just the official global guard, independently for each viewpoint.

    UnitPanel initializes it true. Only a matching local-player Activated or
    Deactivated changes it on this non-Hotseat route. Other players' events
    never modify that viewpoint. No turn flags or synthesized events are used.
    """
    def __init__(self):
        self.last_sequence = 0
        self.latest = {}

    def consume(self, record):
        event = decode_record(record)
        if event is None:
            return None
        if event['sequence'] <= self.last_sequence:
            raise ValueError('UnitPanel event order repeated or reversed')
        self.last_sequence = event['sequence']
        # Game.GetLocalPlayer is an admitted 0..63 player. Signed sentinel or
        # other IDs cannot match it; do not grow an unbounded per-player map.
        if 0 <= event['player_id'] < 64:
            self.latest[event['player_id']] = event
        return event

    def view(self, player_id):
        if type(player_id) is not int or not 0 <= player_id < 64:
            raise ValueError('Invalid UnitPanel viewpoint')
        event = self.latest.get(player_id)
        return dict(player_id=player_id,
            processing_allowed=True if event is None else event['processing_allowed'],
            source='official_initial_value' if event is None else event['name'],
            event_sequence=None if event is None else event['sequence'])


def observe_consumed_record(events, record):
    """Called by the existing FIFO drain before removing a validated record."""
    if decode_record(record) is None:
        return
    tracker = getattr(events, 'unit_panel_event_state', None)
    if tracker is None:
        tracker = events.unit_panel_event_state = UnitPanelEventState()
    event = tracker.consume(record)
    events.emit('native_unit_panel_gate_event', **event,
                native_gameplay_mutated=False, source_sha256=SOURCE[1])


def gate(owner, player_id):
    from .network_ui import _admission
    admission = _admission(owner)
    if (admission is None or admission.get('unit_panel_source_sha256') != SOURCE[1]
            or admission.get('captured_tutorial_inactive') is not True):
        raise ValueError('UnitPanel gate is not admitted for this content')
    events = owner.prefix.deferred_events
    if events.pending:
        raise ValueError('UnitPanel gate requires the drained native event boundary')
    tracker = getattr(events, 'unit_panel_event_state', None)
    view = UnitPanelEventState().view(player_id) if tracker is None else tracker.view(player_id)
    if player_id != owner.network_reference['state']['player_id']:
        raise ValueError('UnitPanel viewpoint differs from the captured local player')
    return view


def catalog(owner, prefix, turn, *, player_id):
    from .capture_profiles import LAN_PROFILE
    from .native import native_saved_unit_work
    if getattr(getattr(owner, 'inputs', None), 'profile', None) is LAN_PROFILE:
        from .unit_work_info import read_catalog
        result,info=read_catalog(prefix,turn,player_id=player_id,
            processing=gate(owner,player_id)['processing_allowed'])
        if not hasattr(owner,'unit_work_information_by_player'):
            owner.unit_work_information_by_player={}
        owner.unit_work_information_by_player[player_id]=info
        return result
    return native_saved_unit_work.catalog(prefix,turn,player_id=player_id)


def require_command(owner, player_id):
    from .capture_profiles import LAN_PROFILE
    if getattr(getattr(owner, 'inputs', None), 'profile', None) is LAN_PROFILE:
        if not gate(owner,player_id)['processing_allowed']:
            raise ValueError('Official UnitPanel processing guard is closed')


def apply_terrain(owner, prefix, action, turn, before, *, player_id):
    """Explicit own-unit selection followed by the retained native operation.

    The headless interface has a manual, player-scoped logical selection.
    This composite request must leave it on the requested unit, not a previously
    selected warrior. It does not reproduce the EXE's automatic unit cycling.
    """
    from .capture_profiles import LAN_PROFILE
    from .native import native_saved_unit_work as work
    if getattr(getattr(owner,'inputs',None),'profile',None) is not LAN_PROFILE:
        return work.apply(owner,prefix,action,turn,before,player_id=player_id)
    require_command(owner,player_id)
    work.validate_action(action)
    if action not in work.actions(work.catalog(prefix,turn,player_id=player_id)):
        raise ValueError('Terrain choice changed before selecting its unit')
    from .native import native_world_input as world
    uid=action['unit_id']
    old=getattr(owner,'world_input_selections',{}).get(player_id)
    selection=dict(kind='world_select_unit',unit_id=uid)
    current=world.observe(owner,before)
    if selection not in world.actions(current) or not world.permitted(current,selection):
        raise ValueError('Terrain unit is not available through normal own-unit selection')
    if current['selected_unit_id']!=uid:
        selected=world.apply(owner,selection,turn,before)
        if selected!=before or owner.world_input_selections.get(player_id)!=uid:
            raise RuntimeError('Terrain selection changed simulation or selected another unit')
    require_command(owner,player_id)
    after=work.apply(owner,prefix,action,turn,before,player_id=player_id)
    alive=any(u['id']==uid for u in after['units'])
    if not alive:
        # UnitPanel's removal handler hides the removed unit. The explicit
        # manual-selection interface cannot retain a handle to a gone unit.
        owner.world_input_selections[player_id]=None
    selected=world.observe(owner,after)['selected_unit_id']
    if selected!=(uid if alive else None):
        raise RuntimeError('Terrain result and manual unit selection diverged')
    owner.emit('official_unit_panel_terrain_result',player_id=player_id,
        unit_id=uid,selected_before=old,selected_after=selected,
        selection_was_explicit_component=True,unit_still_present=alive,
        selection_mode='manual_logical_own_unit',automatic_next_unit_selected=False,
        native_operation_count=1,source_sha256=SOURCE[1],strategic_training_ready=False)
    return after

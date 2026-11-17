"""Caller-selected pantheon choices for an already loaded native session."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_pantheon_actions as native
from ..configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native.native_player_observation import observe_player

def _player_id(value):
    return native._player_id(value)

def _wire_catalog(value, turn, player_id=0):
    pid = _player_id(player_id)
    if type(value) is not dict:
        raise ValueError('Malformed pantheon decision state')
    if value.get('status') == 'not_due':
        if set(value) != {'status', 'reason', 'player_id', 'current_game_turn'}:
            raise ValueError('Malformed pantheon not-due state')
        reason = value['reason']
        if type(reason) is not str or type(value['player_id']) is not int or type(value['current_game_turn']) is not int:
            raise ValueError('Pantheon not-due identity/reason types changed')
        payload = ','.join(('not_due', str(value['player_id']), str(value['current_game_turn']), reason)).encode('ascii')
    elif value.get('status') == 'catalog':
        if set(value) != {'status', 'player_id', 'current_game_turn', 'operation', 'parameter_key', 'insert_key', 'exclusive_value', 'choices'}:
            raise ValueError('Malformed pantheon catalog')
        if any((type(value[k]) is not int for k in ('player_id', 'current_game_turn', 'operation', 'parameter_key', 'insert_key', 'exclusive_value'))):
            raise ValueError('Pantheon catalog identity/enum types changed')
        if type(value['choices']) is not list:
            raise ValueError('Pantheon choices must be a JSON list')
        fields = ['catalog', str(value['player_id']), str(value['current_game_turn']), str(value['operation']), str(value['parameter_key']), str(value['insert_key']), str(value['exclusive_value']), str(len(value['choices']))]
        for row in value['choices']:
            if type(row) is not dict or set(row) != {'index', 'hash'}:
                raise ValueError('Malformed pantheon choice')
            fields.append(f"{row['index']}:{row['hash']}")
        payload = ','.join(fields).encode('ascii')
    else:
        raise ValueError('Unknown pantheon catalog status')
    checked = native.parse_catalog(payload, pid, turn)
    if checked['status'] == 'catalog':
        checked['choices'] = list(checked['choices'])
    if checked != value:
        raise ValueError('Pantheon state differs from native wire contract')
    return checked

def catalog(prefix, turn, *, player_id=0, core_sha256=native._ROUTE_IMAGES['core']):
    pid = _player_id(player_id)
    payload = prefix.runtime.evaluate_text(prefix.ui_child, native.catalog_source(pid, turn, core_sha256=core_sha256), b'@explicit_pantheon_catalog', capacity=131072)
    value = native.parse_catalog(payload, pid, turn)
    if value['status'] == 'catalog':
        value['choices'] = list(value['choices'])
    return validate_catalog(value, turn, player_id=pid)

def validate_catalog(value, turn, *, player_id=0):
    pid = _player_id(player_id)
    if type(turn) is not int or turn < 0:
        raise ValueError('Invalid pantheon decision turn')
    return _wire_catalog(value, turn, pid)

def actions(value):
    if value['status'] == 'not_due':
        return []
    return [dict(kind='pantheon', index=row['index'], hash=row['hash']) for row in value['choices']]

def apply(owner, prefix, action, turn, before, *, player_id=0, core_sha256=native._ROUTE_IMAGES['core'],
          borrowed_catalogue=None):
    pid = _player_id(player_id)
    if type(action) is not dict or set(action) != {'kind', 'index', 'hash'} or action.get('kind') != 'pantheon' or (type(action.get('index')) is not int) or (type(action.get('hash')) is not int):
        raise ValueError('Malformed explicit pantheon action')
    if before is None or type(before) is not dict or before.get('player_id') != pid or (type(before.get('player_id')) is not int) or (before.get('turn') != turn) or (type(before.get('turn')) is not int):
        raise RuntimeError('Pantheon action lacks a matching before observation')
    fresh = catalog(prefix, turn, player_id=pid, core_sha256=core_sha256)
    if borrowed_catalogue is None:
        if fresh != getattr(owner, 'explicit_pantheon', None) or action not in actions(fresh):
            raise RuntimeError('Pantheon decision is stale or no longer offered')
    else:
        if core_sha256 != XP2_CORE_SHA256 or action not in actions(validate_catalog(borrowed_catalogue, turn, player_id=pid)):
            raise ValueError('Borrowed pantheon lacks the published Gathering Storm offer')
        if action not in actions(fresh):
            raise StaleBorrowedPantheon('Pantheon decision is no longer offered')
    native_catalog = dict(fresh)
    native_catalog['choices'] = tuple(fresh['choices'])
    candidate = native.choose(native_catalog, action['index'])
    if candidate['selected_hash'] != action['hash']:
        raise RuntimeError('Pantheon action hash differs from the offered native row')
    if borrowed_catalogue is None:
        receipt = prefix.inspect_pantheon_choice(pid, selected_index=action['index'])
    else:
        receipt = inspect_choice(prefix, pid, selected_index=action['index'], core_sha256=core_sha256,
                                 read=prefix.backend.runtime.read, borrowed_owner=owner)
    if type(receipt) is not dict or receipt.get('status') != 'verified' or receipt.get('confirmed') is not True or any((type(receipt.get(k)) is not int for k in ('player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'observed_pantheon'))) or (receipt.get('player_id') != pid) or (receipt.get('current_game_turn') != turn) or (receipt.get('selected_index') != action['index']) or (receipt.get('selected_hash') != action['hash']) or (receipt.get('observed_pantheon') != action['index']):
        raise RuntimeError('Native pantheon effect differs from caller selection')
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    remaining = catalog(prefix, turn, player_id=pid, core_sha256=core_sha256)
    if after.get('player_id') != pid or type(after.get('player_id')) is not int or after.get('turn') != turn or (type(after.get('turn')) is not int) or (remaining.get('status') != 'not_due') or (remaining.get('reason') != 'already_has_pantheon'):
        raise RuntimeError('Pantheon effect did not persist in the same turn')
    proof_sha256 = native.PINNED_EVIDENCE_SHA256
    if core_sha256 != native._ROUTE_IMAGES['core']:
        from civ6_host.runtime.xp1_pantheon_source import source_hash
        proof_sha256 = source_hash(core_sha256)
    owner.emit('official_explicit_pantheon_effect', action=action, before=fresh, after=remaining, receipt=receipt, observation_before=before, observation_after=after, automatic_choices_applied=False, source_proof_sha256=proof_sha256)
    return after


class StaleBorrowedPantheon(RuntimeError):
    """The offered belief is no longer legal for the borrowed player."""


class NativePantheonRefused(RuntimeError):
    """The official CanStart predicate returned false before request submission."""
    def __init__(self, request):
        super().__init__('Native CanStartPlayerOperation refused pantheon creation')
        self.request = dict(request)


def inspect_choice(prefix, player_id, *, selected_index=None,
                   core_sha256=native._ROUTE_IMAGES['core'], read=None, borrowed_owner=None):
    """Shared orchestration on either real prefix; rules stay in GameCore."""
    import struct
    from .native_player_operation_request import request_player_operation
    if prefix.ui_child is None or prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Pantheon choice requires a published UI view and drained queues')
    if getattr(prefix, '_pantheon_guard_core_sha256', None) != core_sha256:
        guards = native.guard_case(core_sha256=core_sha256)
        if prefix.runtime.evaluate_text(prefix.ui_child, guards, b'@native_pantheon_guards') != b'pantheon-guards-ok':
            raise RuntimeError('Native HKS pantheon choice guards failed')
        prefix._pantheon_guard_core_sha256 = core_sha256
        prefix.emit('native_hks_pantheon_guards_verified', scope='Protected candidate/revalidation/effect collectors against Lua doubles', native_pantheon_founded=False, eligible_for_training=False)
    turn = int(prefix.runtime.evaluate_text(prefix.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_pantheon_turn'))
    value = native.parse_catalog(prefix.runtime.evaluate_text(prefix.ui_child,
        native.catalog_source(player_id, turn, core_sha256=core_sha256),
        b'@native_pantheon_catalog', capacity=131072), player_id, turn)
    prefix.emit('native_pantheon_catalog_observed', **value, eligible_for_training=False)
    if value['status'] == 'not_due':
        if selected_index is not None:
            raise RuntimeError('Explicit pantheon choice is not currently due')
        prefix.emit('native_pantheon_choice_not_due', player_id=player_id, current_game_turn=turn,
            reason=value['reason'], request_invoked=False, endturn_gate_still_required=True, eligible_for_training=False)
        return
    if not value['choices']:
        raise RuntimeError('Native pantheon creation is due but no selectable belief exists')
    candidate = native.choose(value, value['choices'][0]['index'] if selected_index is None else selected_index)
    prefix.emit('native_pantheon_candidate', **candidate, eligible_for_training=False)
    checked = native.parse_revalidated_choice(prefix.runtime.evaluate_text(prefix.ui_child,
        native.revalidate_choice_source(candidate, core_sha256=core_sha256),
        b'@native_pantheon_revalidation'), candidate)
    if core_sha256 == XP2_CORE_SHA256:
        from ..xp2_direct_religion_source import request
        result = request(prefix,player_id,turn,checked,read=read,transport=request_player_operation,
                         borrowed_owner=borrowed_owner)
    else:
        result = request_player_operation(prefix.core, prefix.context, player_id,
            checked['operation'], checked['parameters'], read=read, core_sha256=core_sha256)
    prefix.emit('native_player_operation_request_returned', kind='pantheon', **result)
    if core_sha256 == XP2_CORE_SHA256 and (
            result['can_start'] is not None or result.get('native_can_start_called') is not False):
        raise RuntimeError('Gathering Storm pantheon receipt must match the direct UI request')
    if result['can_start'] is False:
        if result['request_invoked'] or prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Refused pantheon operation unexpectedly emitted work')
        raise NativePantheonRefused(result)
    if not result['request_invoked']:
        raise RuntimeError('Native pantheon request was not submitted after admission')
    if len(prefix.actions.pending) != 1 or prefix.actions.pending[0][:4] != struct.pack('<I', 3294486831):
        raise RuntimeError('Pantheon request did not emit exactly one native operation archive')
    if core_sha256 == XP2_CORE_SHA256:
        from ..xp2_religious_chain_source import verify_player_archive
        verify_player_archive(prefix.actions.pending[0],player_id,checked['operation'],checked['parameters'])
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    after = native.parse_effect(prefix.runtime.evaluate_text(prefix.ui_child,
        native.effect_source(candidate, core_sha256=core_sha256), b'@native_pantheon_effect'), candidate)
    if not after['confirmed']:
        raise RuntimeError(f'Native pantheon effect differs after delivery: {after!r}')
    prefix.emit('native_pantheon_effect_verified', player_id=player_id, current_game_turn=turn,
        selected_index=candidate['selected_index'], selected_hash=candidate['selected_hash'],
        after=after, native_rules_used=True, eligible_for_training=False)
    return after

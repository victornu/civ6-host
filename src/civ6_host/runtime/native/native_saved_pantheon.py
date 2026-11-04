"""Caller-selected pantheon choices for an already loaded native session."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_pantheon_actions as native
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

def catalog(prefix, turn, *, player_id=0):
    pid = _player_id(player_id)
    payload = prefix.runtime.evaluate_text(prefix.ui_child, native.catalog_source(pid, turn), b'@explicit_pantheon_catalog', capacity=131072)
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

def apply(owner, prefix, action, turn, before, *, player_id=0):
    pid = _player_id(player_id)
    if type(action) is not dict or set(action) != {'kind', 'index', 'hash'} or action.get('kind') != 'pantheon' or (type(action.get('index')) is not int) or (type(action.get('hash')) is not int):
        raise ValueError('Malformed explicit pantheon action')
    if before is None or type(before) is not dict or before.get('player_id') != pid or (type(before.get('player_id')) is not int) or (before.get('turn') != turn) or (type(before.get('turn')) is not int):
        raise RuntimeError('Pantheon action lacks a matching before observation')
    fresh = catalog(prefix, turn, player_id=pid)
    if fresh != getattr(owner, 'explicit_pantheon', None) or action not in actions(fresh):
        raise RuntimeError('Pantheon decision is stale or no longer offered')
    native_catalog = dict(fresh)
    native_catalog['choices'] = tuple(fresh['choices'])
    candidate = native.choose(native_catalog, action['index'])
    if candidate['selected_hash'] != action['hash']:
        raise RuntimeError('Pantheon action hash differs from the offered native row')
    receipt = prefix.inspect_pantheon_choice(pid, selected_index=action['index'])
    if type(receipt) is not dict or receipt.get('status') != 'verified' or receipt.get('confirmed') is not True or any((type(receipt.get(k)) is not int for k in ('player_id', 'current_game_turn', 'selected_index', 'selected_hash', 'observed_pantheon'))) or (receipt.get('player_id') != pid) or (receipt.get('current_game_turn') != turn) or (receipt.get('selected_index') != action['index']) or (receipt.get('selected_hash') != action['hash']) or (receipt.get('observed_pantheon') != action['index']):
        raise RuntimeError('Native pantheon effect differs from caller selection')
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    remaining = catalog(prefix, turn, player_id=pid)
    if after.get('player_id') != pid or type(after.get('player_id')) is not int or after.get('turn') != turn or (type(after.get('turn')) is not int) or (remaining.get('status') != 'not_due') or (remaining.get('reason') != 'already_has_pantheon'):
        raise RuntimeError('Pantheon effect did not persist in the same turn')
    owner.emit('official_explicit_pantheon_effect', action=action, before=fresh, after=remaining, receipt=receipt, observation_before=before, observation_after=after, automatic_choices_applied=False, source_proof_sha256=native.PINNED_EVIDENCE_SHA256)
    return after

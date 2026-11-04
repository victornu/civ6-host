"""Expose existing native government adapters as caller-selected decisions."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_government_actions as native
from civ6_host.runtime.native import native_government_consideration as consideration
from civ6_host.runtime.native.native_player_observation import observe_player

def _player_id(value):
    return native._player(value)

def catalog(prefix, turn, *, player_id=0):
    pid = _player_id(player_id)
    c = native.parse_catalog(prefix.runtime.evaluate_text(prefix.ui_child, native.catalog_source(pid, turn), b'@explicit_government_catalog', capacity=16384), pid, turn)
    c['choices'] = list(c['choices'])
    r = consideration.parse_readback(prefix.runtime.evaluate_text(prefix.ui_child, consideration.readback_source(pid, turn), b'@explicit_government_consideration'), pid, turn)
    result = dict(catalog=c, consideration=r)
    return validate_catalog(result, turn, player_id=pid)

def validate_catalog(value, turn, *, player_id=0):
    pid = _player_id(player_id)
    if type(value) is not dict or set(value) != {'catalog', 'consideration'}:
        raise ValueError('Malformed government decision state')
    c, r = (value['catalog'], value['consideration'])
    keys = {'status', 'player_id', 'current_game_turn', 'current_government_index', 'can_change_government_at_all', 'government_change_made', 'civic_completed_this_turn', 'choices'}
    if type(c) is not dict or set(c) != keys or c['status'] != 'catalog' or (type(c['choices']) is not list):
        raise ValueError('Malformed native government catalogue')
    flags = ('can_change_government_at_all', 'government_change_made', 'civic_completed_this_turn')
    if any((type(c[k]) is not bool for k in flags)):
        raise ValueError('Government flag type changed')
    for k in ('player_id', 'current_game_turn', 'current_government_index'):
        if type(c[k]) is not int:
            raise ValueError('Government identity must be exact integer')
    parts = ['catalog', str(c['player_id']), str(c['current_game_turn']), str(c['current_government_index']), *(str(int(c[k])) for k in flags), str(len(c['choices']))]
    for row in c['choices']:
        if type(row) is not dict or set(row) != {'index', 'hash', 'unlocked', 'can_change', 'anarchy_turns', 'requires_anarchy_path'} or any((type(row[k]) is not int for k in ('index', 'hash', 'anarchy_turns'))) or any((type(row[k]) is not bool for k in ('unlocked', 'can_change', 'requires_anarchy_path'))) or (row['requires_anarchy_path'] is not (row['anarchy_turns'] > 0)):
            raise ValueError('Malformed government choice')
        parts.append(':'.join((str(v) for v in (row['index'], row['hash'], int(row['unlocked']), int(row['can_change']), row['anarchy_turns']))))
    checked = native.parse_catalog('|'.join(parts).encode('ascii'), pid, turn)
    checked['choices'] = list(checked['choices'])
    if checked != c:
        raise ValueError('Government catalogue differs from native wire contract')
    if c['current_government_index'] != -1 and c['current_government_index'] not in {row['index'] for row in c['choices']}:
        raise ValueError('Current government absent from native rows')
    if type(r) is not dict or set(r) != {'player_id', 'current_game_turn', 'government_index', 'considered', 'consideration_blocker_present'} or any((type(r[k]) is not int for k in ('player_id', 'current_game_turn', 'government_index'))) or any((type(r[k]) is not bool for k in ('considered', 'consideration_blocker_present'))) or ((r['player_id'], r['current_game_turn'], r['government_index']) != (pid, turn, c['current_government_index'])) or (c['player_id'] != pid):
        raise ValueError('Government consideration perspective/state differs')
    return value

def actions(value):
    c, r = (value['catalog'], value['consideration'])
    result = []
    if c['can_change_government_at_all'] and (not c['government_change_made']) and (c['current_government_index'] == -1 or c['civic_completed_this_turn']):
        result.extend((dict(kind='government', index=row['index'], hash=row['hash'] & 4294967295) for row in c['choices'] if row['unlocked'] and row['can_change'] and (not row['requires_anarchy_path']) and (row['index'] != c['current_government_index'])))
    if r['consideration_blocker_present'] and (not r['considered']) and (r['government_index'] >= 0):
        result.append(dict(kind='retain_government', index=r['government_index']))
    return result

def apply(owner, prefix, action, turn, before, *, player_id=0):
    pid = _player_id(player_id)
    actor = before.get('player_id') if type(before) is dict else None
    if type(before) is not dict or type(actor) is not int or actor != pid or (type(before.get('turn')) is not int) or (before['turn'] != turn):
        raise RuntimeError('Government action lacks matching actor observation')
    fresh = catalog(prefix, turn, player_id=pid)
    if fresh != getattr(owner, 'explicit_government', None) or action not in actions(fresh):
        raise RuntimeError('Government decision is stale or no longer offered')
    if action['kind'] == 'government':
        receipt = prefix.inspect_government_choice(pid, selected_index=action['index'])
        if receipt is None or not receipt['confirmed'] or (not receipt['government_change_made']) or (receipt['current_government_index'] != action['index']) or (receipt['choice']['selected_hash'] & 4294967295 != action['hash']):
            raise RuntimeError('Native government effect differs from caller selection')
    elif action['kind'] == 'retain_government':
        receipt = prefix.inspect_government_consideration(pid)
        if receipt is None or not receipt['considered'] or receipt['consideration_blocker_present'] or (receipt['government_index'] != action['index']):
            raise RuntimeError('Native government retention not verified')
    else:
        raise ValueError('Unknown government decision')
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    observed = catalog(prefix, turn, player_id=pid)
    if after.get('player_id') != pid:
        raise RuntimeError('Government observation belongs to another player')
    if after['turn'] != turn or observed['catalog']['current_government_index'] != action['index']:
        raise RuntimeError('Government decision crossed turn or changed target')
    owner.emit('official_explicit_government_effect', action=action, before=fresh, after=observed, receipt=receipt, observation_before=before, observation_after=after, automatic_choices_applied=False, source_proof_sha256=native.PINNED_EVIDENCE_SHA256, consideration_proof_sha256=consideration.PINNED_EVIDENCE_SHA256)
    return after

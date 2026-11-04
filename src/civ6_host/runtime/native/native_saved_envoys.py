"""Caller-selected envoy send/retain choices using the existing native route."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_envoy_actions as native
from civ6_host.runtime.native.native_player_observation import observe_player
FIELDS = {'send_envoy': {'kind', 'target_player_id'}, 'retain_envoys': {'kind'}}

def validate_catalog(value, turn, *, player_id=0):
    native._context(player_id, turn)
    keys = {'player_id', 'current_game_turn', 'tokens_to_give', 'can_give_influence', 'considered', 'giving_tokens_blocker_present', 'targets'}
    if type(value) is not dict or set(value) != keys or type(value['targets']) is not list:
        raise ValueError('Malformed envoy decision catalogue')
    if native._check_catalog(value) != (player_id, turn):
        raise ValueError('Foreign envoy decision catalogue')
    for row in value['targets']:
        if type(row) is not dict or set(row) != {'target_player_id', 'can_give', 'tokens_received'}:
            raise ValueError('Malformed envoy target')
    return value

def catalog(prefix, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, native.catalog_source(player_id, turn), b'@explicit_envoy_catalog', capacity=8193)
    value = native.parse_catalog(raw, player_id, turn)
    value['targets'] = list(value['targets'])
    return validate_catalog(value, turn, player_id=player_id)

def actions(value):
    result = []
    if value['can_give_influence'] and value['tokens_to_give'] > 0:
        for row in value['targets']:
            if row['can_give']:
                result.append(dict(kind='send_envoy', target_player_id=row['target_player_id']))
    if not value['considered'] and value['giving_tokens_blocker_present']:
        result.append(dict(kind='retain_envoys'))
    return result

def validate_action(action):
    if type(action) is not dict or action.get('kind') not in FIELDS or set(action) != FIELDS[action['kind']]:
        raise ValueError('Malformed explicit envoy action')
    if action['kind'] == 'send_envoy':
        native._integer(action['target_player_id'], 'envoy target', 63)
    return action

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    native._context(player_id, turn)
    if type(before) is not dict or before.get('player_id') != player_id or before.get('turn') != turn:
        raise ValueError('Envoy action lacks actor observation')
    fresh = catalog(prefix, turn, player_id=player_id)
    if fresh != getattr(owner, 'explicit_envoys', None) or action not in actions(fresh):
        raise RuntimeError('Envoy decision is stale or unavailable')
    if action['kind'] == 'send_envoy':
        choice = native.choose(fresh, action['target_player_id'])
        receipt = prefix.inspect_envoy_choice(player_id, selected_target=action['target_player_id'])
    else:
        receipt = prefix.inspect_envoy_choice(player_id, retain=True)
    observed = catalog(prefix, turn, player_id=player_id)
    expected = native.verify_sent_effect(observed, choice) if action['kind'] == 'send_envoy' else native.verify_considered_effect(fresh, observed)
    if receipt != expected:
        raise RuntimeError('Envoy receipt differs from the observed native effect')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after.get('player_id') != player_id or after.get('turn') != turn:
        raise RuntimeError('Envoy action crossed actor/turn')
    owner.emit('official_explicit_envoy_effect', action=action, before=fresh, after=observed, receipt=receipt, observation_before=before, observation_after=after, automatic_choices_applied=False, source_proof_sha256=native.PROOF_SHA256, strategic_training_ready=False)
    return after

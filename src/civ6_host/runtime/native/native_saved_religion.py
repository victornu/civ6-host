"""Explicit religion choices, reusing the original native request/effect adapters.

The three commands remain separate. No prophet navigation, name or belief is
selected by the host. Only the acting player's religion snapshot is published.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
from civ6_host.runtime.native import native_religion_observation as observation
from civ6_host.runtime.native import native_prophet_activation as prophet
from civ6_host.runtime.native import native_religion_founding as founding
from civ6_host.runtime.native import native_religion_beliefs as beliefs
from civ6_host.runtime.native import native_religion_diagnostic as commands
from civ6_host.runtime.native.native_player_observation import observe_player
FIELDS = {'activate_prophet': {'kind', 'unit_id', 'x', 'y'}, 'found_religion': {'kind', 'index', 'hash'}, 'add_belief': {'kind', 'index', 'hash', 'class'}}

def plain(value):
    return json.loads(json.dumps(value, allow_nan=False))

def exact(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)

def integer(v):
    if type(v) is not int:
        raise ValueError('Religion field must be an integer')
    return str(v)

def boolean(v):
    if type(v) is not bool:
        raise ValueError('Religion field must be a Boolean')
    return '1' if v else '0'

def array(v):
    if type(v) is not list or len(v) > 4096:
        raise ValueError('Unbounded religion list')
    return v

def validate_observation(value, pid, turn):
    """Round-trip through the existing strict native wire parser, not new rules."""
    try:
        holy = value['holy_city']
        own = value['own_religion']
        parts = ['religion-observation-v1', integer(value['player_id']), integer(value['current_game_turn']), integer(value['religion_type_created']), boolean(value['has_religious_founding_unit']), integer(value['num_beliefs_earned']), *[integer(holy[k]) for k in ('player', 'type', 'id')], boolean(own is not None), integer(-1 if own is None else own['religion_index']), integer(-1 if own is None else own['founder'])]
        owned = [] if own is None else array(own['belief_indices'])
        parts.extend([integer(len(owned)), *[integer(v) for v in owned]])
        parsed = observation.parse_observation('|'.join(parts).encode('ascii'), pid, turn)
        if not exact(parsed, value):
            raise ValueError('Religion observation differs from native schema')
        return value
    except (KeyError, TypeError, AttributeError, UnicodeError) as exc:
        raise ValueError('Malformed own religion observation') from exc

def validate_subcatalog(name, value, pid, turn):
    """Retain native parser bounds/enums, including empty and pending catalogues."""
    try:
        entries = array(value['candidates'])
        head = ['catalog', integer(value['player_id']), integer(value['current_game_turn'])]
        if name == 'activation':
            head += [integer(value['operation']), integer(value['prophet_type_index']), integer(len(entries))]
            head += [':'.join((integer(r[k]) for k in ('unit_id', 'x', 'y'))) for r in entries]
            parser = prophet.parse_catalog
        elif name == 'foundation':
            head += [integer(value['num_beliefs_earned']), *[integer(value['founding_site'][k]) for k in ('player', 'type', 'id')], *[integer(value[k]) for k in ('own_religion_count', 'operation', 'religion_parameter', 'insert_parameter', 'exclusive_value')], integer(len(entries))]
            head += [':'.join((integer(r[k]) for k in ('index', 'hash'))) for r in entries]
            parser = founding.parse_catalog
        elif name == 'beliefs':
            owned = array(value['equipped_beliefs'])
            parser = beliefs.parse_catalog
            if value['status'] == 'not_due':
                head = ['not_due', integer(value['player_id']), integer(value['current_game_turn']), *[integer(value[k]) for k in ('religion_index', 'num_beliefs_earned', 'equipped_count')], 'no_unspent_belief']
            else:
                head += [integer(value[k]) for k in ('religion_index', 'num_beliefs_earned', 'equipped_count', 'remaining_slots', 'operation', 'belief_parameter', 'insert_parameter', 'exclusive_value')]
                head += [integer(len(owned)), integer(len(entries))] + ['o' + integer(v) for v in owned]
                head += ['c' + integer(r['index']) + ':' + integer(r['hash']) + ':' + beliefs._class(r['class']) for r in entries]
        else:
            raise ValueError('Unknown religious catalogue')
        if not exact(plain(parser(','.join(head).encode('ascii'), pid, turn)), value):
            raise ValueError('Religion catalogue differs from native schema')
        return value
    except (KeyError, TypeError, AttributeError, UnicodeError) as exc:
        raise ValueError('Malformed native religion catalogue') from exc

def applicability(own):
    unfounded = own['religion_type_created'] == -1
    return dict(activation=unfounded and own['has_religious_founding_unit'], foundation=unfounded and own['holy_city_present'], beliefs=not unfounded)

def validate_catalog(value, turn, *, player_id=0):
    if type(value) is not dict or set(value) != {'own', 'activation', 'foundation', 'beliefs'}:
        raise ValueError('Malformed explicit religion state')
    own = validate_observation(value['own'], player_id, turn)
    for name, needed in applicability(own).items():
        sub = value[name]
        if not needed:
            if sub is not None:
                raise ValueError('Religion catalogue without native precondition')
            continue
        validate_subcatalog(name, sub, player_id, turn)
        if name == 'foundation' and (sub['founding_site'] != own['holy_city'] or sub['num_beliefs_earned'] != own['num_beliefs_earned']):
            raise ValueError('Religion foundation context differs')
        if name == 'beliefs':
            if sub['religion_index'] != own['religion_type_created'] or sub['num_beliefs_earned'] != own['num_beliefs_earned'] or sub['equipped_count'] != len(own['own_religion']['belief_indices']) or (sub['status'] == 'catalog' and sub['equipped_beliefs'] != own['own_religion']['belief_indices']):
                raise ValueError('Belief catalogue differs from own religion')
    return value

def catalog(prefix, turn, *, player_id=0):
    own = prefix.inspect_own_religion_snapshot(player_id)
    validate_observation(own, player_id, turn)
    result = dict(own=own, activation=None, foundation=None, beliefs=None)
    modules = {'activation': (prophet, prophet.MAX_WIRE), 'foundation': (founding, founding.MAX_RESPONSE), 'beliefs': (beliefs, beliefs.MAX_RESPONSE)}
    for name, needed in applicability(own).items():
        if needed:
            mod, capacity = modules[name]
            raw = prefix.runtime.evaluate_text(prefix.ui_child, mod.catalog_source(player_id, turn), ('@explicit_religion_' + name).encode('ascii'), capacity=capacity)
            result[name] = plain(mod.parse_catalog(raw, player_id, turn))
    return validate_catalog(result, turn, player_id=player_id)

def actions(value):
    result = []
    for name, kind in [('activation', 'activate_prophet'), ('foundation', 'found_religion'), ('beliefs', 'add_belief')]:
        if value[name] is not None:
            result.extend((dict(kind=kind, **r) for r in value[name]['candidates']))
    return result

def validate_action(action):
    if type(action) is not dict or action.get('kind') not in FIELDS or set(action) != FIELDS[action['kind']]:
        raise ValueError('Malformed religion action')
    for k, v in action.items():
        if k == 'kind':
            continue
        if k == 'class':
            beliefs._class(v)
        elif k in ('x', 'y'):
            prophet._s32(v, k)
        else:
            prophet._uint(v, k)
    return action

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    if type(before) is not dict or before.get('player_id') != player_id or before.get('turn') != turn:
        raise ValueError('Religion action lacks actor observation')
    fresh = catalog(prefix, turn, player_id=player_id)
    if fresh != getattr(owner, 'explicit_religion', None) or action not in actions(fresh):
        raise RuntimeError('Religion choice is stale or unavailable')
    kind = action['kind']
    if kind == 'activate_prophet':
        receipt = commands.activate_prophet(prefix, player_id, selected_unit_id=action['unit_id'])
    elif kind == 'found_religion':
        receipt = commands.found_religion(prefix, player_id, selected_index=action['index'])
    else:
        receipt = commands.add_belief(prefix, player_id, selected_index=action['index'])
    if type(receipt) is not dict:
        raise RuntimeError('Explicit religion command lacks verified effect')
    after_religion = catalog(prefix, turn, player_id=player_id)
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after.get('player_id') != player_id or after.get('turn') != turn:
        raise RuntimeError('Religion action crossed actor/turn')
    own = after_religion['own']
    if kind == 'activate_prophet':
        if receipt.get('activation_verified') is not True or receipt.get('unit_consumed') is not True or own['holy_city'] != receipt.get('founding_site') or (own['num_beliefs_earned'] != receipt.get('beliefs_earned_after')) or (own['religion_type_created'] != -1) or (action['unit_id'] in {u['id'] for u in after['units']}):
            raise RuntimeError('Prophet activation readback differs')
    elif kind == 'found_religion':
        if receipt.get('religion_created') is not True or receipt.get('religion_index') != action['index'] or receipt.get('religion_hash') != action['hash'] or (own['religion_type_created'] != action['index']) or (own['own_religion'] != {'founder': player_id, 'religion_index': action['index'], 'belief_indices': []}) or (own['holy_city'] != fresh['own']['holy_city']):
            raise RuntimeError('Religion foundation readback differs')
    else:
        expected = {'religion_index': fresh['own']['religion_type_created'], 'founder': player_id, 'belief_indices': list(receipt.get('belief_indices', ()))}
        if own['own_religion'] != expected or action['index'] not in expected['belief_indices'] or own['num_beliefs_earned'] != receipt.get('num_beliefs_earned') or (set(expected['belief_indices']) != set(fresh['own']['own_religion']['belief_indices']) | {action['index']}):
            raise RuntimeError('Belief membership readback differs')
    owner.emit('official_explicit_religion_effect', action=action, receipt=receipt, religion_before=fresh, religion_after=after_religion, observation_before=before, observation_after=after, automatic_choices_applied=False, strategic_training_ready=False)
    return after

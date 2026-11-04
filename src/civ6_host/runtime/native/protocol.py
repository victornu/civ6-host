"""Version 1 bridge protocol. A requested action is NOT an executed action."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json
import math
import re
PREFIX = 'CIV6RL '
FIELDS = {'move': {'unit_id', 'x', 'y'}, 'found_city': {'unit_id'}, 'skip_turn': {'unit_id'}, 'fortify': {'unit_id'}, 'heal': {'unit_id'}, 'sleep': {'unit_id'}, 'end_turn': set(), 'end_player_turn': set(), 'research': {'tech_type'}, 'civic': {'civic_type'}, 'production': {'city_id', 'item_type'}, 'attack_melee': {'unit_id', 'target_owner_id', 'target_unit_id', 'x', 'y'}, 'policies': {'policies'}}

def integer(value):
    return isinstance(value, int) and (not isinstance(value, bool))

def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False

def check_finite_tree(value):
    if isinstance(value, (int, float)) and (not isinstance(value, bool)) and (not finite_number(value)):
        raise ValueError('all numbers must be finite')
    if isinstance(value, dict):
        for item in value.values():
            check_finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            check_finite_tree(item)

def check_numbers(mapping, fields):
    if not isinstance(mapping, dict) or any((not finite_number(mapping.get(field)) for field in fields)):
        raise ValueError(f'expected finite numeric fields: {fields}')

def validate_observation(observation):
    if not isinstance(observation, dict):
        raise ValueError('observation must be an object')
    for collection in ('units', 'cities'):
        if not isinstance(observation.get(collection), list):
            raise ValueError(f'observation.{collection} must be an array')
        seen = set()
        for entity in observation[collection]:
            if not isinstance(entity, dict):
                raise ValueError('entities must be objects')
            fields = ('id', 'x', 'y', 'type') if collection == 'units' else ('id', 'x', 'y', 'population')
            if any((not integer(entity.get(f)) or entity[f] < 0 for f in fields)):
                raise ValueError('entity IDs, coordinates and type/population must be nonnegative integers')
            if entity['id'] in seen:
                raise ValueError(f'duplicate {collection} id')
            seen.add(entity['id'])
            if collection == 'units':
                check_numbers(entity, ('moves', 'max_moves', 'damage'))
            else:
                if not isinstance(entity.get('name'), str):
                    raise ValueError('city name must be a string')
                check_numbers(entity.get('yields'), ('food', 'production', 'gold', 'science', 'culture', 'faith'))
    check_numbers(observation.get('economy'), ('science', 'culture', 'gold', 'faith'))
    if not isinstance(observation.get('can_end_turn'), bool) or not integer(observation.get('blocker')):
        raise ValueError('can_end_turn must be boolean and blocker must be integer')
    if 'options' in observation:
        options = observation['options']
        if not isinstance(options, dict):
            raise ValueError('options must be an object')
        for field, pattern in (('research', 'TECH_[A-Z0-9_]+'), ('civics', 'CIVIC_[A-Z0-9_]+')):
            values = options.get(field)
            if not isinstance(values, list) or any((not isinstance(v, str) or not re.fullmatch(pattern, v) for v in values)):
                raise ValueError(f'invalid {field} options')
        if not isinstance(options.get('production'), list):
            raise ValueError('production options must be an array')
        for city in options['production']:
            if not isinstance(city, dict) or not integer(city.get('city_id')) or city['city_id'] < 0:
                raise ValueError('invalid production city')
            items = city.get('item_types')
            if not isinstance(items, list) or any((not isinstance(v, str) or not re.fullmatch('(?:UNIT|BUILDING)_[A-Z0-9_]+', v) for v in items)):
                raise ValueError('invalid production items')
        if 'policy_slots' in options or 'policies_ready' in options:
            slots, ready = (options.get('policy_slots'), options.get('policies_ready'))
            if not isinstance(slots, list) or not isinstance(ready, bool):
                raise ValueError('policy_slots and policies_ready must be supplied together')
            if ready and (not slots or options.get('ready') is not True):
                raise ValueError('ready policies require slots and a ready native observation')
            if ready and 'government' not in observation:
                raise ValueError('ready policies require the current government assignment')
            for index, slot in enumerate(slots):
                if not isinstance(slot, dict) or set(slot) != {'slot_index', 'slot_type', 'policy_types'} or (not integer(slot['slot_index'])) or (slot['slot_index'] != index) or (not isinstance(slot['slot_type'], str)) or (not re.fullmatch('SLOT_[A-Z0-9_]+', slot['slot_type'])):
                    raise ValueError('policy slots must be exact ordered contiguous native slots')
                choices = slot['policy_types']
                if not isinstance(choices, list) or any((not isinstance(p, str) or not re.fullmatch('POLICY_[A-Z0-9_]+', p) for p in choices)) or len(set(choices)) != len(choices):
                    raise ValueError('policy slot choices must be unique POLICY_* identifiers')
    if 'government' in observation:
        government = observation['government']
        if not isinstance(government, dict) or set(government) != {'type', 'policies'} or (not isinstance(government['type'], str)) or (not re.fullmatch('GOVERNMENT_[A-Z0-9_]+', government['type'])) or (not isinstance(government['policies'], list)) or any((not isinstance(p, str) or (p != '' and (not re.fullmatch('POLICY_[A-Z0-9_]+', p))) for p in government['policies'])):
            raise ValueError('invalid observed government/policies')
        active = [p for p in government['policies'] if p]
        if len(active) != len(set(active)):
            raise ValueError('observed policies cannot occupy multiple slots')
        slots = observation.get('options', {}).get('policy_slots')
        if slots is not None and len(government['policies']) != len(slots):
            raise ValueError('observed government policies must match native slot count')

def validate_action(action):
    if not isinstance(action, dict):
        raise ValueError('action must be an object')
    kind = action.get('kind')
    if not isinstance(kind, str) or kind not in FIELDS:
        raise ValueError('unsupported action kind')
    expected = {'request_id', 'turn', 'kind'} | FIELDS[kind]
    if 'player_id' in action:
        expected.add('player_id')
    if set(action) != expected:
        raise ValueError(f'expected exactly these fields: {sorted(expected)}')
    request_id = action['request_id']
    if not isinstance(request_id, str) or not re.fullmatch('[A-Za-z0-9_.:-]{1,128}', request_id):
        raise ValueError('request_id must contain 1-128 ASCII letters, digits, _, ., :, or -')
    for field in ('turn', 'player_id', 'unit_id', 'city_id', 'target_owner_id', 'target_unit_id', 'x', 'y'):
        if field in action and (not integer(action[field]) or action[field] < 0):
            raise ValueError(f'{field} must be a nonnegative integer')
    for field, pattern in (('tech_type', 'TECH_[A-Z0-9_]+'), ('civic_type', 'CIVIC_[A-Z0-9_]+'), ('item_type', '(?:UNIT|BUILDING)_[A-Z0-9_]+')):
        if field in action and (not isinstance(action[field], str) or not re.fullmatch(pattern, action[field])):
            raise ValueError(f'invalid {field} identifier')
    if kind == 'attack_melee' and 'player_id' in action and (action['target_owner_id'] == action['player_id']):
        raise ValueError('melee target must belong to another player')
    if kind == 'policies':
        policies = action['policies']
        if not isinstance(policies, list) or not policies or any((not isinstance(p, str) or not re.fullmatch('POLICY_[A-Z0-9_]+', p) for p in policies)) or (len(set(policies)) != len(policies)):
            raise ValueError('policies must be a nonempty ordered list of unique POLICY_* identifiers')
    return action

def lua_command(action):
    """Render a bounded command for a trusted local UI console; never execute it."""
    validate_action(action)

    def lua_value(value):
        if isinstance(value, list):
            return '{' + ','.join((lua_value(item) for item in value)) + '}'
        return json.dumps(value)
    fields = ','.join((f'{key}={lua_value(value)}' for key, value in sorted(action.items())))
    return 'ExposedMembers.Civ6RL.Dispatch({' + fields + '})'

def decode_record(line):
    """Ignore unrelated log lines; reject malformed or unsupported bridge records."""
    if PREFIX not in line:
        return None
    payload = line.split(PREFIX, 1)[1].strip()
    record = json.loads(payload, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    check_finite_tree(record)
    if not isinstance(record, dict) or not integer(record.get('schema_version')) or record['schema_version'] != 1:
        raise ValueError('unsupported bridge schema')
    for field in ('sequence', 'turn', 'player_id'):
        if not integer(record.get(field)):
            raise ValueError(f'{field} must be an integer')
    if record['sequence'] < 1:
        raise ValueError('sequence must be positive')
    kind = record.get('type')
    if kind == 'observation':
        validate_observation(record.get('observation'))
        if not isinstance(record.get('event'), str):
            raise ValueError('observation requires an event string')
    elif kind == 'action_result':
        if record.get('status') not in ('requested', 'rejected', 'error'):
            raise ValueError('invalid action status')
        if not isinstance(record.get('request_id'), str) or not isinstance(record.get('reason'), str):
            raise ValueError('invalid action result')
    elif kind == 'action_transition':
        if record.get('status') not in ('confirmed', 'timeout', 'failed'):
            raise ValueError('invalid transition status')
        if not isinstance(record.get('request_id'), str) or not record['request_id'] or (not isinstance(record.get('kind'), str)) or (record['kind'] not in FIELDS) or (not isinstance(record.get('reason'), str)):
            raise ValueError('invalid action transition')
        for field in ('before_sequence', 'after_sequence'):
            if not integer(record.get(field)) or record[field] < 0:
                raise ValueError('invalid transition sequence reference')
        if record['before_sequence'] < 1 or (record['status'] == 'confirmed' and (not record['before_sequence'] < record['after_sequence'] < record['sequence'])):
            raise ValueError('confirmed transition requires ordered before/after states')
        if record['kind'] == 'end_player_turn':
            for field in ('actor_player_id', 'before_turn', 'after_turn'):
                if not integer(record.get(field)) or record[field] < 0:
                    raise ValueError('hotseat transition requires explicit actor, next player and turns')
            if not integer(record.get('next_player_id')) or record['next_player_id'] < -1:
                raise ValueError('invalid hotseat next player')
            if record['actor_player_id'] != record['player_id']:
                raise ValueError('hotseat transition actor must match its envelope')
            if record['status'] == 'confirmed' and (record['next_player_id'] < 0 or record['actor_player_id'] == record['next_player_id'] or record['after_turn'] < record['before_turn']):
                raise ValueError('confirmed hotseat transition must advance to a different player')
    elif kind == 'transport_status':
        if not isinstance(record.get('request_id'), str) or not record['request_id'] or record.get('status') not in ('ok', 'error') or (not isinstance(record.get('reason'), str)):
            raise ValueError('invalid transport status')
        if 'diagnostics' in record and (not isinstance(record['diagnostics'], dict)):
            raise ValueError('transport diagnostics must be an object')
    elif kind == 'bridge_error':
        if not isinstance(record.get('reason'), str):
            raise ValueError('bridge_error requires a reason')
    else:
        raise ValueError('unsupported record type')
    return record

def compare_observations(expected, actual, *, tolerance=1e-08):
    """Return state mismatches for future simulator differential validation.

    Call with observation payloads from the SAME scenario and synchronized step.
    Matching only this visible subset cannot establish full engine equivalence.
    """
    if not finite_number(tolerance) or tolerance < 0:
        raise ValueError('tolerance must be finite and nonnegative')
    check_finite_tree(expected)
    check_finite_tree(actual)
    mismatches = []

    def visit(left, right, path):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                if key not in left or key not in right:
                    mismatches.append({'path': f'{path}.{key}', 'issue': 'missing_field'})
                else:
                    visit(left[key], right[key], f'{path}.{key}')
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                mismatches.append({'path': path, 'issue': 'length', 'expected': len(left), 'actual': len(right)})
            for i, (a, b) in enumerate(zip(left, right)):
                visit(a, b, f'{path}[{i}]')
        elif isinstance(left, (int, float)) and (not isinstance(left, bool)) and isinstance(right, (int, float)) and (not isinstance(right, bool)):
            if not abs(left - right) <= tolerance:
                mismatches.append({'path': path, 'expected': left, 'actual': right})
        elif type(left) is not type(right) or left != right:
            mismatches.append({'path': path, 'expected': left, 'actual': right})
    visit(expected, actual, 'observation')
    return mismatches

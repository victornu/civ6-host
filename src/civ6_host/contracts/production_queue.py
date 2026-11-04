"""Shared portable queue action/catalogue/permutation contract.

Extracted unchanged from the existing Base queue adapter; native and client
consumers use these same validators. It validates shape, not availability.
"""
import copy, re
UNQUALIFIED_APPEND = ('placement_required_items', 'nonstandard_unit_formations')
KINDS = ('unit', 'building', 'project', 'district')
PUBLIC_SCHEMA = 'civ6rl.production_queue.public.v2'
FIELDS = {'queue_append': {'kind', 'city_id', 'category', 'index', 'hash', 'item_type', 'mode'}, 'queue_remove': {'kind', 'city_id', 'position'}, 'queue_swap': {'kind', 'city_id', 'source_position', 'destination_position'}}

def _uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid ' + label)
    return value

def _type_name(kind, value):
    if kind not in KINDS or type(value) is not str or (not re.fullmatch(kind.upper() + '_[A-Z0-9_]{1,100}', value)):
        raise ValueError('Invalid production type name')
    return value

def uint(v, label, maximum=4294967295):
    return _uint(v, label, maximum)

def validate_action(a):
    if type(a) is not dict or a.get('kind') not in FIELDS or set(a) != FIELDS[a['kind']]:
        raise ValueError('Malformed production queue action')
    uint(a['city_id'], 'city')
    if a['kind'] == 'queue_append':
        _type_name(a['category'], a['item_type'])
        uint(a['index'], 'index', 2147483647)
        uint(a['hash'], 'hash')
        if a['mode'] not in ('append', 'replace_tail'):
            raise ValueError('Unknown queue insertion mode')
    elif a['kind'] == 'queue_remove':
        uint(a['position'], 'queue position', 7)
    else:
        uint(a['source_position'], 'queue source', 7)
        uint(a['destination_position'], 'queue destination', 7)
        if a['source_position'] == a['destination_position']:
            raise ValueError('UI same-item click deselects, it does not swap')
    return a

def action_wire(a):
    validate_action(a)
    if a['kind'] == 'queue_append':
        return '|'.join((str(v) for v in ('A', a['category'], a['index'], a['hash'], a['item_type'], a['mode'])))
    if a['kind'] == 'queue_remove':
        return f"R|{a['position']}"
    return f"S|{a['source_position']}|{a['destination_position']}"

def validate_catalog(v, pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(v) is not dict:
        raise ValueError('Foreign queue catalogue')
    public = 'schema' in v
    keys = {'player_id', 'turn', 'city_id', 'enabled', 'entries', 'offers'}
    if public:
        keys.add('schema')
    if set(v) != keys or (public and v['schema'] != PUBLIC_SCHEMA) or type(v['player_id']) is not int or (v['player_id'] != pid) or (type(v['turn']) is not int) or (v['turn'] != turn) or (type(v['enabled']) is not bool):
        raise ValueError('Foreign queue catalogue')
    uint(v['city_id'], 'city')
    if type(v['entries']) is not list or len(v['entries']) > 8 or type(v['offers']) is not list or (len(v['offers']) > 320):
        raise ValueError('Unbounded production queue')
    for i, e in enumerate(v['entries']):
        entry_keys = {'position', 'category', 'index', 'hash', 'formation'}
        if public:
            entry_keys.add('formation_display')
        if type(e) is not dict or set(e) != entry_keys or type(e['position']) is not int or (e['position'] != i) or (e['category'] not in KINDS):
            raise ValueError('Malformed queue entry')
        uint(e['index'], 'entry index', 2147483647)
        uint(e['hash'], 'entry hash')
        if e['category'] == 'unit':
            if type(e['formation']) is not int or not -2147483648 <= e['formation'] <= 2147483647:
                raise ValueError('Invalid queue formation')
            if public:
                display = e['formation_display']
                if type(display) is not dict or set(display) != {'is_corps', 'is_army'} or any((type(display[k]) is not bool for k in ('is_corps', 'is_army'))) or (display['is_corps'] and display['is_army']):
                    raise ValueError('Invalid public queue formation markers')
        elif e['formation'] is not None:
            raise ValueError('Nonunit formation')
        elif public and e['formation_display'] is not None:
            raise ValueError('Nonunit public formation markers')
    seen = set()
    for a in v['offers']:
        validate_action(a)
        wire = action_wire(a)
        if a['city_id'] != v['city_id'] or wire in seen or (not v['enabled']):
            raise ValueError('Foreign, duplicate or disabled queue action')
        seen.add(wire)
        size = len(v['entries'])
        if a['kind'] == 'queue_append':
            if a['mode'] != ('replace_tail' if size == 8 else 'append'):
                raise ValueError('Wrong queue insertion mode')
        elif a['kind'] == 'queue_remove':
            if a['position'] >= size:
                raise ValueError('Removing a missing queue entry')
        elif max(a['source_position'], a['destination_position']) >= size:
            raise ValueError('Swapping a missing queue entry')
    return v

def catalog_wire(v):
    validate_catalog(v, v['player_id'], v['turn'])
    public = v.get('schema') == PUBLIC_SCHEMA
    version = 'queue-v2' if public else 'queue-v1'
    rows = [f"{version}|{v['player_id']}|{v['city_id']}|{v['turn']}|{int(v['enabled'])}|{len(v['entries'])}"]
    for e in v['entries']:
        cells = ['E', e['position'], e['category'], e['index'], e['hash'], '-' if e['formation'] is None else e['formation']]
        if public:
            display = e['formation_display']
            cells.extend(('-', '-') if display is None else (int(display['is_corps']), int(display['is_army'])))
        rows.append('|'.join((str(x) for x in cells)))
    rows.extend((action_wire(a) for a in v['offers']))
    return '\n'.join(rows)

def validate_all(values, pid, turn):
    if type(values) is not list or len(values) > 256:
        raise ValueError('Unbounded city queues')
    ids = []
    for v in values:
        validate_catalog(v, pid, turn)
        ids.append(v['city_id'])
    if ids != sorted(set(ids)):
        raise ValueError('Unordered or duplicate city queues')
    return values

def check_heads(values, production_snapshot):
    rows = production_snapshot.get('cities', [])
    if [q['city_id'] for q in values] != [r['city_id'] for r in rows]:
        raise ValueError('Queue and current production city rosters differ')
    for q, r in zip(values, rows):
        if len(q['entries']) != r['queue_size']:
            raise ValueError('Queue size differs from current production')
        if q['entries']:
            e = q['entries'][0]
            if (e['category'], e['index'], e['hash']) != ({'U': 'unit', 'B': 'building', 'D': 'district', 'P': 'project'}.get(r['kind']), r['item_index'], r['current_production_hash'] & 4294967295):
                raise ValueError('Queue head differs from current production')

def check_effect(a, before, after):
    """Check the documented queue permutation, not production math or legality."""
    if before.get('schema') != after.get('schema'):
        raise RuntimeError('Queue effect catalogue versions differ')
    validate_action(a)
    expected = copy.deepcopy(before['entries'])
    actual = after['entries']
    if a['kind'] == 'queue_remove':
        expected.pop(a['position'])
    elif a['kind'] == 'queue_swap':
        i, j = (a['source_position'], a['destination_position'])
        expected[i], expected[j] = (expected[j], expected[i])
    else:
        i = 7 if a['mode'] == 'replace_tail' else len(expected)
        if len(actual) != (len(expected) if a['mode'] == 'replace_tail' else len(expected) + 1):
            raise RuntimeError('Native append size differs')
        incoming = actual[i]
        if (incoming['category'], incoming['index'], incoming['hash']) != (a['category'], a['index'], a['hash']):
            raise RuntimeError('Native appended item differs')
        if a['mode'] == 'replace_tail':
            expected[i] = copy.deepcopy(incoming)
        else:
            expected.append(copy.deepcopy(incoming))
    for i, row in enumerate(expected):
        row['position'] = i
    if expected != actual:
        raise RuntimeError('Native queue order or unaffected entries differ')


def validate_public(values, pid, turn, *, observation=None, choice_state=None, unavailable=False):
    """Join the common v2 rows to own cities and the current-choice snapshot."""
    if type(unavailable) is not bool:raise ValueError('Queue availability must be Boolean')
    if unavailable:
        if values is not None:raise ValueError('Unavailable production queues must be null')
        return values
    validate_all(values,pid,turn)
    if any(row.get('schema')!=PUBLIC_SCHEMA for row in values):
        raise ValueError('Capability queues require the existing public v2 schema')
    if observation is not None:
        if ([q['city_id'] for q in values]!=sorted(c['id'] for c in observation['cities'])
                or any(c['owner']!=pid for c in observation['cities'])):
            raise ValueError('Public queues differ from the owned-city roster')
    if type(choice_state) is not dict or type(choice_state.get('production')) is not list:
        raise ValueError('Public queues lack their exact current production choices')
    rows=[dict(row,current_production_hash=row['hash']) for row in choice_state['production']]
    check_heads(values,dict(cities=rows))
    for q,r in zip(values,rows):
        if q['entries'] and q['entries'][0]['formation']!=r['formation']:
            raise ValueError('Queue head formation differs from current production')
    return values


def validate_candidates(values,candidates):
    expected=[] if values is None else [a for q in values for a in q['offers']]
    actual=[r['action'] for r in candidates if r['action']['kind'] in FIELDS]
    key=lambda a:(a['city_id'],action_wire(a))
    if sorted(actual,key=key)!=sorted(expected,key=key):
        raise ValueError('Queue candidates differ from the exact native offers')

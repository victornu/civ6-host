"""Public shape of explicit research and current-production choices.

This validates identities, not legality. Costs/progress with unqualified public
precision are deliberately kept in the administrative native receipt.
"""
import re

ACTION_FIELDS = {
    'research': frozenset(('kind', 'index', 'hash')),
    'civic': frozenset(('kind', 'index', 'hash')),
    'production': frozenset(('kind', 'city_id', 'category', 'index', 'hash', 'item_type')),
}
RESEARCH_KINDS = ('research', 'civic')
FOUND_CITY_FIELDS = frozenset(('kind', 'unit_id', 'x', 'y'))


def _uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


def validate_founder_action(action, own_units=None):
    if (type(action) is not dict or set(action) != FOUND_CITY_FIELDS
            or action['kind'] != 'found_city' or not _uint(action['unit_id'])
            or not _uint(action['x'], 65535) or not _uint(action['y'], 65535)):
        raise ValueError('Malformed foundation action')
    if own_units is not None:
        unit = own_units.get(action['unit_id'])
        if unit is None or (unit['x'], unit['y']) != (action['x'], action['y']):
            raise ValueError('Foundation action differs from its own-unit observation')


def validate_action(action, own_cities=None):
    kind = action.get('kind')
    if kind not in ACTION_FIELDS or set(action) != ACTION_FIELDS[kind]:
        raise ValueError('Unknown explicit choice action')
    if not _uint(action['index']) or not _uint(action['hash']):
        raise ValueError('Invalid native choice index/hash')
    if kind == 'production':
        category = action['category']
        if (not _uint(action['city_id']) or category not in ('unit', 'building', 'project', 'district')
                or type(action['item_type']) is not str
                or re.fullmatch(category.upper() + r'_[A-Z0-9_]{1,100}', action['item_type']) is None
                or action['index'] > 0x7fffffff
                or own_cities is not None and action['city_id'] not in own_cities):
            raise ValueError('Production choice differs from its owned city or native item')


def research_actions(state):
    """Validate current chooser indices and produce actions for every offered row."""
    if type(state) is not dict or set(state) != set(RESEARCH_KINDS):
        raise ValueError('Malformed research choices')
    actions = {}
    for kind in RESEARCH_KINDS:
        row = state[kind]
        if (type(row) is not dict or set(row) != {'current_index', 'choices'}
                or (row['current_index'] is not None and not _uint(row['current_index']))
                or type(row['choices']) is not list or len(row['choices']) > 4096):
            raise ValueError('Malformed native research chooser')
        offers, hashes, previous = [], set(), -1
        for choice in row['choices']:
            if type(choice) is not dict or set(choice) != {'index', 'hash'}:
                raise ValueError('Malformed native research choice')
            action = dict(kind=kind, **choice)
            validate_action(action)
            if choice['index'] <= previous or choice['hash'] in hashes:
                raise ValueError('Ambiguous native research choice')
            offers.append(action)
            previous = choice['index']
            hashes.add(choice['hash'])
        actions[kind] = offers
    return actions


def project_state(research, production):
    """Only current choices, exact identifiers and queue count, no hidden precision."""
    return dict(research=dict(research), production=project_production(production))


def project_production(production):
    return [dict(
        city_id=row['city_id'], queue_size=row['queue_size'], kind=row['kind'],
        item_index=row['item_index'], hash=row['current_production_hash'] & 0xffffffff,
        formation=row['formation']) for row in production['cities']]


def validate_state(state, own_cities=None, *, unavailable=False):
    if unavailable:
        if state is not None:
            raise ValueError('Unavailable choice query must not carry fabricated current choices')
        return
    if (type(state) is not dict or set(state) != {'research', 'production'}
            or type(state['research']) is not dict or set(state['research']) != {'research', 'civic'}
            or any(v is not None and not _uint(v) for v in state['research'].values())):
        raise ValueError('Invalid public current-choice state')
    validate_production_state(state['production'], own_cities)


def validate_production_state(production, own_cities=None):
    if type(production) is not list or len(production) > 256:
        raise ValueError('Invalid public current-choice state')
    ids = []
    for row in production:
        if (type(row) is not dict
                or set(row) != {'city_id', 'queue_size', 'kind', 'item_index', 'hash', 'formation'}
                or not _uint(row['city_id']) or not _uint(row['queue_size'], 65535)
                or not _uint(row['hash']) or row['kind'] not in ('N', 'U', 'B', 'D', 'P')):
            raise ValueError('Invalid public production choice')
        if row['kind'] == 'N':
            if row['hash'] != 0 or row['item_index'] is not None or row['formation'] is not None:
                raise ValueError('Empty native production choice has item data')
        elif row['hash'] == 0 or not _uint(row['item_index']):
            raise ValueError('Current production choice lacks its native item')
        if row['kind'] == 'U':
            if not _uint(row['formation'], 0x7fffffff):
                raise ValueError('Current unit choice lacks its native formation')
        elif row['formation'] is not None:
            raise ValueError('Non-unit production choice has a formation')
        ids.append(row['city_id'])
    if ids != sorted(set(ids)) or own_cities is not None and set(ids) != set(own_cities):
        raise ValueError('Current production choices differ from the owned-city observation')

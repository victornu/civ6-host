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


def _uint(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


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


def project_state(research, production):
    """Only current choices, exact identifiers and queue count, no hidden precision."""
    return dict(research=dict(research), production=[dict(
        city_id=row['city_id'], queue_size=row['queue_size'], kind=row['kind'],
        item_index=row['item_index'], hash=row['current_production_hash'] & 0xffffffff,
        formation=row['formation']) for row in production['cities']])


def validate_state(state, own_cities=None, *, unavailable=False):
    if unavailable:
        if state is not None:
            raise ValueError('Unavailable choice query must not carry fabricated current choices')
        return
    if (type(state) is not dict or set(state) != {'research', 'production'}
            or type(state['research']) is not dict or set(state['research']) != {'research', 'civic'}
            or any(v is not None and not _uint(v) for v in state['research'].values())
            or type(state['production']) is not list or len(state['production']) > 256):
        raise ValueError('Invalid public current-choice state')
    ids = []
    for row in state['production']:
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

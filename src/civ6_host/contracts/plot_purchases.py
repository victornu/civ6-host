"""Player-facing offers from the city tile and gold purchase panels."""

import re

FIELDS = frozenset(('kind', 'city_id', 'plot_id', 'x', 'y', 'currency', 'price_token'))
CITY_FIELDS = frozenset(('kind', 'city_id', 'category', 'index', 'hash', 'item_type',
                         'currency', 'price_token'))
GAPS = ('unit_purchase', 'building_purchase', 'district_purchase', 'faith_purchase',
        'placement_filtered_plot_purchase')
CITY_GAPS = ('district_purchase', 'faith_purchase', 'corps_purchase', 'army_purchase',
             'placement_filtered_plot_purchase')
CITY_FAITH_GAPS = ('district_purchase', 'corps_purchase', 'army_purchase',
                   'placement_filtered_plot_purchase', 'faith_purchase_native_effect')
LIMIT = 4096


def _validate_price(token):
    if (type(token) is not str or len(token) > 32
            or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?', token) is None
            or not 0 <= float(token) <= 2 ** 53):
        raise ValueError('Malformed native purchase quote')


def validate_action(action):
    if (type(action) is not dict or set(action) != FIELDS or action['kind'] != 'purchase'
            or action['currency'] != 'YIELD_GOLD'):
        raise ValueError('Expected an ordinary gold plot purchase')
    for field, limit in (('city_id', 0xffffffff), ('plot_id', 16383), ('x', 16383), ('y', 16383)):
        if type(action[field]) is not int or not 0 <= action[field] <= limit:
            raise ValueError('Invalid plot purchase ' + field)
    _validate_price(action['price_token'])


def validate_city_action(action, *, allow_faith=False):
    if type(allow_faith) is not bool:
        raise ValueError('Faith purchase permission must be an exact boolean')
    if (type(action) is not dict or set(action) != CITY_FIELDS or action['kind'] != 'purchase'
            or action['category'] not in ('unit', 'building')
            or action['currency'] not in (('YIELD_GOLD', 'YIELD_FAITH') if allow_faith else ('YIELD_GOLD',))):
        raise ValueError('Expected an allowed unit or building purchase')
    for field in ('city_id', 'index', 'hash'):
        if type(action[field]) is not int or not 0 <= action[field] <= 0xffffffff:
            raise ValueError('Invalid city purchase ' + field)
    name = action['item_type']
    if type(name) is not str or re.fullmatch(action['category'].upper() + r'_[A-Z0-9_]{1,100}', name) is None:
        raise ValueError('Invalid city purchase item type')
    _validate_price(action['price_token'])


def validate_purchase_action(action, *, allow_faith=False):
    if type(allow_faith) is not bool:
        raise ValueError('Faith purchase permission must be an exact boolean')
    if 'plot_id' in action:
        validate_action(action)
    else:
        validate_city_action(action, allow_faith=allow_faith)


def validate_catalogue(value, player_id, turn, *, width=None, height=None, own_cities=None,
                       city_items=False, allow_faith=False):
    if type(allow_faith) is not bool:
        raise ValueError('Faith purchase permission must be an exact boolean')
    if type(value) is not list or len(value) > LIMIT:
        raise ValueError('Malformed plot purchase catalogues')
    city_ids = []
    total = 0
    for city in value:
        if (type(city) is not dict or set(city) != {'player_id', 'turn', 'city_id', 'offers'}
                or type(city['player_id']) is not int or city['player_id'] != player_id
                or type(city['turn']) is not int or city['turn'] != turn
                or type(city['city_id']) is not int or not 0 <= city['city_id'] <= 0xffffffff
                or type(city['offers']) is not list):
            raise ValueError('Foreign plot purchase catalogue')
        city_ids.append(city['city_id'])
        total += len(city['offers'])
        if total > LIMIT:
            raise ValueError('Plot purchase offer bound exceeded')
        last_plot = -1
        seen = set()
        for offer in city['offers']:
            if (type(offer) is not dict or set(offer) != {'action', 'command_legal', 'can_afford'}
                    or type(offer['command_legal']) is not bool or type(offer['can_afford']) is not bool):
                raise ValueError('Malformed plot purchase offer')
            action = offer['action']
            if city_items:
                validate_city_action(action, allow_faith=allow_faith)
                key = ((action['category'], action['index'], action['currency'])
                       if allow_faith else (action['category'], action['index']))
                if action['city_id'] != city['city_id'] or key in seen:
                    raise ValueError('Foreign or duplicate city purchase offer')
                seen.add(key)
                continue
            validate_action(action)
            if (action['city_id'] != city['city_id'] or action['plot_id'] <= last_plot
                    or action['x'] >= width or action['y'] >= height
                    or action['plot_id'] != action['y'] * width + action['x']):
                raise ValueError('Plot purchase target identity differs')
            last_plot = action['plot_id']
    if city_ids != sorted(set(city_ids)) or (own_cities is not None and city_ids != sorted(own_cities)):
        raise ValueError('Plot purchase catalogues differ from the own-city roster')


def actions(catalogue):
    return [row['action'] for city in catalogue for row in city['offers']
            if row['command_legal'] and row['can_afford']]

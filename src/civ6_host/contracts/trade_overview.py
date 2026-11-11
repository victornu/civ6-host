"""Player-scoped data from the three trade overview tabs."""
from collections import Counter

from .trade import _list, _shape, _yields, compare_routes, uint

SCHEMA = 'civ6-host.trade-overview.v1'
PROFILE = 'gathering-storm-bbg-7.5.1'
STOCK_PROFILE = 'civilization-vi-standard'
PROFILES = (PROFILE, STOCK_PROFILE)
NATIVE_UNAVAILABLE = frozenset(('trade_view_disabled', 'unlock_history_unavailable'))
PAIR = ('origin_owner', 'origin_city', 'destination_owner', 'destination_city')
_ROW = ' '.join((*PAIR, 'origin_name', 'destination_name', 'distance',
                 'has_post', 'origin_yields', 'destination_yields'))


def validate(value, player_id, turn, sequence, *, profile=PROFILE):
    _shape(value, 'schema profile player_id turn sequence active_count capacity '
                  'idle_trader_ids produce_trader_slots own_routes incoming_routes available_routes')
    if profile not in PROFILES or value['profile'] != profile:
        raise ValueError('Trade overview returned a different display profile')
    if (value['schema'] != SCHEMA
            or uint(value['player_id'], 'overview player', 63) != player_id
            or uint(value['turn'], 'overview turn', 2**31 - 1) != turn
            or uint(value['sequence'], 'overview sequence', 2**31 - 1) != sequence):
        raise ValueError('Foreign trade overview boundary')

    active = uint(value['active_count'], 'active count', 2**31 - 1)
    capacity = uint(value['capacity'], 'capacity', 2**31 - 1)
    idle = _list(value['idle_trader_ids'])
    for unit_id in idle:
        uint(unit_id, 'idle trader')
    produce = uint(value['produce_trader_slots'], 'produce trader slots', 2**31 - 1)
    if len(set(idle)) != len(idle) or len(idle) + produce != max(0, capacity - active):
        raise ValueError('Invalid trade overview unused slots')

    for field in ('own_routes', 'incoming_routes', 'available_routes'):
        rows = _list(value[field])
        keys = []
        for row in rows:
            _shape(row, _ROW + (' unit_id' if field == 'own_routes' else ''))
            pair = tuple(uint(row[key], key, 63 if key.endswith('_owner') else 2**32 - 1)
                         for key in PAIR)
            if field == 'incoming_routes':
                if pair[0] == player_id or pair[2] != player_id:
                    raise ValueError('Incoming trade route is outside the player boundary')
            elif pair[0] != player_id:
                raise ValueError('Trade overview origin is outside the player boundary')
            key = pair
            if field == 'own_routes':
                key += (uint(row['unit_id'], 'active trader'),)
            keys.append(key)
            for name in ('origin_name', 'destination_name'):
                if type(row[name]) is not str or len(row[name].encode('utf-8')) > 32768:
                    raise ValueError('Invalid trade overview city name')
            uint(row['distance'], 'overview distance', 16384)
            if type(row['has_post']) is not bool:
                raise ValueError('Invalid trade overview post flag')
            for direction in ('origin_yields', 'destination_yields'):
                quote = row[direction]
                _yields(quote)
                if not (quote['majority_religion'] == quote['religion_pressure'] == -1
                        or (quote['majority_religion'] > 0 and quote['religion_pressure'] >= 0)):
                    raise ValueError('Invalid trade overview religion display')
        if keys != sorted(keys) or (field != 'incoming_routes' and len(set(keys)) != len(keys)):
            raise ValueError('Invalid trade overview route order or duplicate')
    return value


def compare_player(value, observation, sequence, *, profile=PROFILE):
    """Bind the panel's own cities and idle units to the accepted view."""
    pid = observation['player_id']
    validate(value, pid, observation['turn'], sequence, profile=profile)
    cities = {city['id'] for city in observation['cities']}
    units = {unit['id'] for unit in observation['units']}
    for field in ('own_routes', 'incoming_routes', 'available_routes'):
        for row in value[field]:
            for side in ('origin', 'destination'):
                if row[side + '_owner'] == pid and row[side + '_city'] not in cities:
                    raise ValueError('Trade overview refers to an absent own city')
    active_traders = {row['unit_id'] for row in value['own_routes']}
    idle = set(value['idle_trader_ids'])
    if idle & active_traders or idle - units:
        raise ValueError('Trade overview idle roster differs from own units')
    return value


def compare_own(value, observation, trade_routes, sequence, *, profile=PROFILE):
    """Join the panel to the independently checked native route catalogue."""
    compare_player(value, observation, sequence, profile=profile)
    compare_routes(trade_routes, observation)

    def routes(rows):
        return Counter(tuple(row[k] for k in (*PAIR, 'unit_id')) for row in rows)

    own = value['own_routes']
    if routes(own) != routes(trade_routes['active_routes']):
        raise ValueError('Trade overview differs from the active route catalogue')
    return value


def validate_group(value, status, decisions, observation=None, *, profile=PROFILE):
    routes = decisions['trade_routes']
    if routes is None:
        allowed = ('waiting_or_closed', 'ui_boundary_unavailable') if profile == STOCK_PROFILE else ('waiting_or_closed',)
    else:
        allowed = ('available', *NATIVE_UNAVAILABLE)
        if profile == PROFILE:
            allowed += ('ui_boundary_unavailable',)
    if type(status) is not str or status not in allowed or (value is None) != (status != 'available'):
        raise ValueError('Trade overview differs from its native availability boundary')
    if (profile == PROFILE and routes is not None
            and (status == 'ui_boundary_unavailable') != decisions['world_congress']['in_session']):
        raise ValueError('Trade overview differs from its qualified UI phase')
    if value is not None:
        if observation is None:
            validate(value, decisions['player_id'], decisions['turn'], decisions['sequence'], profile=profile)
        else:
            compare_own(value, observation, routes, decisions['sequence'], profile=profile)

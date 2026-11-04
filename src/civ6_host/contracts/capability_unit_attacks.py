"""Portable public unit-attack state and exact shared native action shapes.

Offers preserve native UI routes and point to plots, never chosen defenders.
These source-derived validators are also consumed by the native adapter.
"""
import math
from copy import deepcopy
from typing import Any
from .action_budget import MAP_CELL_LIMIT, ORDINARY_ACTION_LIMIT

_MAX_PLAYER=63
FIELDS = {'kind', 'unit_id', 'operation', 'input_route', 'plot_id', 'x', 'y'}
UNIT_FIELDS = {'unit_id', 'unit_type', 'x', 'y', 'damage', 'moves', 'attacks_remaining'}
CITY_FIELDS = {'owner', 'city_id', 'district_id', 'plot_id', 'x', 'y', 'garrison_damage', 'garrison_max', 'outer_damage', 'outer_max', 'defense_strength'}
ACTION_FIELDS={'unit_attack':frozenset(FIELDS)}
UNQUALIFIED_UNIT_ATTACKS=('war_confirmation','air_attacks','nonadjacent_enemy_flag_melee',
    'world_plot_unit_targeting','coastal_raid_and_swap','other_unit_attack_operations',
    'operation_lifecycle_only_readback','native_legal_targets_without_visible_witness')

def _player_id(value: int) -> int:
    if type(value) is not int or not 0 <= value <= _MAX_PLAYER:
        raise ValueError('player_id must be an integer in [0, 63]')
    return value

def _uint(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 4294967295:
        raise ValueError(f'{label} must be an unsigned 32-bit integer')
    return value

def validate_action(value, width=16384, height=16384):
    if type(value) is not dict or set(value) != FIELDS or value['kind'] != 'unit_attack':
        raise ValueError('Invalid native plot attack action')
    if value['operation'] not in ('MOVE_TO', 'RANGE_ATTACK'):
        raise ValueError('Unsupported native attack order')
    if value['input_route'] not in ('enemy_flag', 'dedicated_ranged', 'world_plot') or (value['input_route'] == 'dedicated_ranged' and value['operation'] != 'RANGE_ATTACK'):
        raise ValueError('Unknown UI attack input route')
    for k in ('unit_id', 'plot_id', 'x', 'y'):
        _uint(value[k], k)
    if value['plot_id'] >= 16384 or value['x'] >= width or value['y'] >= height:
        raise ValueError('Attack target outside admitted map')
    if width != 16384 and value['plot_id'] != value['y'] * width + value['x']:
        raise ValueError('Attack target coordinates disagree with plot')
    return value

def validate_units(rows):
    if type(rows) is not list or len(rows) > 4096:
        raise ValueError('Unbounded combat roster')
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != UNIT_FIELDS:
            raise ValueError('Malformed own combat state')
        for k in ('unit_id', 'unit_type', 'x', 'y', 'attacks_remaining'):
            _uint(row[k], k)
        for k in ('damage', 'moves'):
            if type(row[k]) not in (int, float) or not math.isfinite(row[k]) or row[k] < 0:
                raise ValueError('Invalid own combat scalar')
        if row['unit_id'] in seen:
            raise ValueError('Duplicate own combat unit')
        seen.add(row['unit_id'])
    return rows

def verify_observation(rows, observation):
    actual = [dict(id=r['unit_id'], type=r['unit_type'], x=r['x'], y=r['y'], damage=r['damage'], moves=r['moves']) for r in rows]
    expected = [{k: r[k] for k in ('id', 'type', 'x', 'y', 'damage', 'moves')} for r in observation['units']]
    if sorted(actual, key=lambda r: r['id']) != sorted(expected, key=lambda r: r['id']):
        raise ValueError('Combat roster differs from published own-unit observation')

def validate_relationships(rows, *, player_id=0):
    pid = _player_id(player_id)
    if type(rows) is not list or len(rows) > 63:
        raise ValueError('Invalid visible combat relationships')
    seen = set()
    for r in rows:
        if type(r) is not dict or set(r) != {'owner', 'at_war'} or type(r['owner']) is not int or (not 0 <= r['owner'] <= 63) or (r['owner'] == pid) or (type(r['at_war']) is not bool) or (r['owner'] in seen):
            raise ValueError('Malformed visible combat relationship')
        seen.add(r['owner'])
    return rows

def validate_cities(rows, width=16384, height=16384):
    if type(rows) is not list or len(rows) > 4096:
        raise ValueError('Unbounded visible city list')
    seen = set()
    for r in rows:
        if type(r) is not dict or set(r) != CITY_FIELDS:
            raise ValueError('Invalid visible city row')
        for key in ('owner', 'city_id', 'district_id', 'plot_id', 'x', 'y'):
            _uint(r[key], key)
        if r['owner'] > 63 or r['plot_id'] >= 16384 or r['x'] >= width or (r['y'] >= height) or (width != 16384 and r['plot_id'] != r['y'] * width + r['x']) or (r['plot_id'] in seen):
            raise ValueError('Invalid or duplicate visible city position')
        for key in CITY_FIELDS - {'owner', 'city_id', 'district_id', 'plot_id', 'x', 'y'}:
            if type(r[key]) not in (int, float) or not math.isfinite(r[key]) or r[key] < 0:
                raise ValueError('Invalid native city defense value')
        if r['garrison_damage'] > r['garrison_max'] or r['outer_damage'] > r['outer_max']:
            raise ValueError('City damage exceeds native maximum')
        seen.add(r['plot_id'])
    return rows


def _key(action):
    return tuple(action[k] for k in ('unit_id','operation','input_route','plot_id'))


def validate_catalog(value,pid,turn,*,observation=None,queued_orders=None,unavailable=False):
    """Join recorded native offers to public witnesses, never derive legality."""
    _player_id(pid);_uint(turn,'turn')
    if type(unavailable) is not bool:raise ValueError('Attack availability must be explicit')
    if unavailable:
        if value is not None:raise ValueError('Unavailable unit attacks must be null')
        return value
    if (type(value) is not dict or set(value)!={'player_id','turn','width','height','units','relationships','cities','offers'}
            or type(value['player_id']) is not int or value['player_id']!=pid
            or type(value['turn']) is not int or value['turn']!=turn
            or type(value['width']) is not int or type(value['height']) is not int
            or min(value['width'],value['height'])<1 or value['width']*value['height']>MAP_CELL_LIMIT
            or type(value['offers']) is not list or len(value['offers'])>ORDINARY_ACTION_LIMIT):
        raise ValueError('Invalid public unit-attack catalogue')
    width,height=value['width'],value['height']
    units=validate_units(value['units']);cities=validate_cities(value['cities'],width,height)
    relations=validate_relationships(value['relationships'],player_id=pid)
    ids=[r['unit_id'] for r in units]
    if ids!=sorted(set(ids)) or any(r['x']>=width or r['y']>=height for r in units):
        raise ValueError('Combat units are unsorted or outside the native map')
    wars={r['owner']:r['at_war'] for r in relations}
    visible=None
    if observation is not None:
        if (observation['player_id'],observation['turn'],observation['width'],observation['height'])!=(pid,turn,width,height):
            raise ValueError('Combat catalogue differs from its public boundary')
        verify_observation(units,observation)
        visible={p['index'] for p in observation['plots'] if p['visible'] is True}
        own_cities={r['id']:(r['x'],r['y']) for r in observation['cities'] if r['owner']==pid}
        for city in cities:
            if city['plot_id'] not in visible or city['owner']==pid and own_cities.get(city['city_id'])!=(city['x'],city['y']):
                raise ValueError('City combat defenses lack the same visible player observation')
        target_owners={r['owner'] for r in observation['visible_enemy_units']}|{c['owner'] for c in cities if c['owner']!=pid}
        if set(wars)!=target_owners:
            raise ValueError('Combat diplomacy differs from exactly the visible target owners')
    if queued_orders is not None:
        from .capability_world_input import validate_queued_orders
        validate_queued_orders(queued_orders,pid,turn,observation=observation)
        if ((queued_orders['width'],queued_orders['height'])!=(width,height)
                or [r['unit_id'] for r in queued_orders['units']]!=ids):
            raise ValueError('Combat and queued-order observations disagree')
    seen=set()
    for action in value['offers']:
        validate_action(action,width,height)
        key=_key(action)
        if action['unit_id'] not in ids or key in seen:
            raise ValueError('Foreign or duplicate native attack offer')
        seen.add(key)
        if visible is not None:
            witnesses=[r for r in observation['visible_enemy_units'] if (r['x'],r['y'])==(action['x'],action['y'])]
            witnesses.extend(c for c in cities if c['plot_id']==action['plot_id'] and c['owner']!=pid)
            if action['plot_id'] not in visible or not any(wars.get(r['owner']) is True for r in witnesses):
                raise ValueError('Attack offer lacks a visible target at native war')
    return value


def actions(value):
    validate_catalog(value,value['player_id'],value['turn'])
    return list(value['offers'])


def validate_candidates(value,candidates):
    actual=[r['action'] for r in candidates if r['action']['kind']=='unit_attack']
    expected=[] if value is None else actions(value)
    if len(actual)!=len(expected) or {_key(a) for a in actual}!={_key(a) for a in expected}:
        raise ValueError('Unit-attack choices differ from the exact recorded native offers')


# Source pin denotes the XP1 official UI projection, not a native legality rule.
PUBLIC_PRECISION_SHA256='5a3982beb1ec8344dca783b5ca83a49dff606e24327046984c35c575c2075d14'
_HITPOINT_FIELDS=('garrison_damage','garrison_max','outer_damage','outer_max')


def project_cities(rows,width=16384,height=16384):
    """Detach native city rows and apply the official displayed precision."""
    validate_cities(rows,width,height)
    result=deepcopy(rows)
    for row in result:
        for key in _HITPOINT_FIELDS:
            value=row[key]
            if (type(value) not in (int,float) or value!=int(value)
                    or not 0<=value<(1<<31)):
                raise ValueError('Native city hitpoints must be exact nonnegative signed32 values')
            row[key]=int(value)
        strength=row['defense_strength']
        # The callback converts packed signed32 to float32, then Lua double.
        # Its nonnegative values are multiples of 1/256 (larger float32 values
        # may have coarser precision). No decimal or centistrength conversion.
        if strength*256!=int(strength*256) or strength>(1<<23):
            raise ValueError('Native city strength is outside its qualified fixed-point domain')
        row['defense_strength']=math.floor(strength+0.5)
    return result


def validate_public_catalog(value,pid,turn,*,observation=None,queued_orders=None,unavailable=False):
    """v10 player catalogue; legacy v9/native validators remain unchanged."""
    validate_catalog(value,pid,turn,observation=observation,
                     queued_orders=queued_orders,unavailable=unavailable)
    if value is not None:
        for row in value['cities']:
            for key in (*_HITPOINT_FIELDS,'defense_strength'):
                if type(row[key]) is not int or not 0<=row[key]<(1<<31):
                    raise ValueError('Public city defenses must use displayed integer precision')
    return value


def project_public(value,*,observation=None,queued_orders=None):
    """Project precision only: preserve every native offer, route and unit."""
    validate_catalog(value,value['player_id'],value['turn'],observation=observation,
                     queued_orders=queued_orders)
    result=deepcopy(value)
    result['cities']=project_cities(value['cities'],value['width'],value['height'])
    return validate_public_catalog(result,result['player_id'],result['turn'],
                                  observation=observation,queued_orders=queued_orders)

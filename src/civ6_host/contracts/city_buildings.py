"""Public building inventory from the acting player's own city panel."""

import re

from .action_budget import MAP_CELL_LIMIT
from .production_queue import _type_name, _uint


SCHEMA = 'civ6-host.city-buildings.v1'
GREAT_WORKS_SCHEMA = 'civ6-host.city-buildings.v2'
GREAT_WORK_TARGETS_SCHEMA = 'civ6-host.city-buildings.v3'
GREAT_WORK_COMMANDS_SCHEMA = 'civ6-host.city-buildings.v4'
GREAT_WORK_OVERVIEW_SCHEMA = 'civ6-host.city-buildings.v5'
GREAT_WORK_XP1_COMMANDS_SCHEMA = 'civ6-host.city-buildings.v6'
GREAT_WORK_OVERVIEW_SCHEMAS = (GREAT_WORK_OVERVIEW_SCHEMA, GREAT_WORK_XP1_COMMANDS_SCHEMA)
GREAT_WORK_COMMAND_SCHEMAS = (GREAT_WORK_COMMANDS_SCHEMA, *GREAT_WORK_OVERVIEW_SCHEMAS)
GREAT_WORK_TARGET_SCHEMAS = (GREAT_WORK_TARGETS_SCHEMA, *GREAT_WORK_COMMAND_SCHEMAS)
GREAT_WORK_SCHEMAS = (GREAT_WORKS_SCHEMA, *GREAT_WORK_TARGET_SCHEMAS)
GREAT_WORK_MOVE = 'move_great_work'
GREAT_WORK_MOVE_FIELDS = {'kind', 'source', 'destination', 'work_index', 'target_work_index'}
MAX_ROWS = 2 * MAP_CELL_LIMIT


def validate(value, player_id, turn, *, observation=None):
    schema = value.get('schema') if type(value) is dict else None
    fields = {'schema', 'player_id', 'turn', 'rows'}
    if schema in GREAT_WORK_SCHEMAS:
        fields.add('great_work_slots')
    if schema in GREAT_WORK_TARGET_SCHEMAS:
        fields.add('great_work_move_targets')
    if schema in GREAT_WORK_COMMAND_SCHEMAS:
        fields.add('great_work_moves_available')
    if schema in GREAT_WORK_OVERVIEW_SCHEMAS:
        fields.add('great_work_building_bonuses')
    if (type(value) is not dict or set(value) != fields
            or schema not in (SCHEMA, *GREAT_WORK_SCHEMAS) or type(value['player_id']) is not int
            or type(value['turn']) is not int or (value['player_id'],value['turn']) != (player_id,turn)
            or type(value['rows']) is not list or len(value['rows']) > MAX_ROWS):
        raise ValueError('Malformed or foreign city building inventory')
    own_cities = own_plots = None
    if observation is not None:
        if (observation['player_id'],observation['turn']) != (player_id,turn):
            raise ValueError('City building observation belongs to another boundary')
        own_cities = {row['id'] for row in observation['cities'] if row['owner']==player_id}
        own_plots = {row['index'] for row in observation['plots']
                     if row['visible'] is True and row['owner']==player_id}
    previous = (-1,-1,-1)
    complete = set()
    for row in value['rows']:
        if (type(row) is not dict or set(row) != {'city_id','plot_id','index','hash','item_type','complete','pillaged'}
                or any(type(row[k]) is not bool for k in ('complete','pillaged'))):
            raise ValueError('Malformed city building row')
        city = _uint(row['city_id'],'building city')
        plot = _uint(row['plot_id'],'building plot',MAP_CELL_LIMIT-1)
        index = _uint(row['index'],'building index',0x7fffffff)
        _uint(row['hash'],'building hash')
        _type_name('building',row['item_type'])
        key = (city,plot,index)
        if key <= previous:
            raise ValueError('Duplicate or unordered city building rows')
        previous = key
        if row['complete']:
            complete.add((city, index))
        if own_cities is not None and (city not in own_cities or plot not in own_plots):
            raise ValueError('City building row refers to another city or an unavailable plot')
    if schema in GREAT_WORK_SCHEMAS:
        slots = _validate_great_work_slots(value['great_work_slots'], complete)
        if schema in GREAT_WORK_TARGET_SCHEMAS:
            _validate_great_work_targets(value['great_work_move_targets'], slots)
        if schema in GREAT_WORK_OVERVIEW_SCHEMAS:
            _validate_great_work_building_bonuses(value['great_work_building_bonuses'], slots)
    if schema in GREAT_WORK_COMMAND_SCHEMAS and type(value['great_work_moves_available']) is not bool:
        raise ValueError('Malformed Great Work command availability')
    return value


def validate_great_work_action(action):
    if (type(action) is not dict or set(action) != GREAT_WORK_MOVE_FIELDS
            or action['kind'] != GREAT_WORK_MOVE
            or _slot_address(action['source']) == _slot_address(action['destination'])):
        raise ValueError('Malformed Great Work command')
    index = _uint(action['work_index'], 'Great Work command source index', 0x7fffffff)
    if action['target_work_index'] is not None and (
            _uint(action['target_work_index'], 'Great Work command target index', 0x7fffffff) == index):
        raise ValueError('Great Work cannot occupy both slots')
    return action


def great_work_actions(panel):
    if panel['schema'] not in GREAT_WORK_COMMAND_SCHEMAS or not panel['great_work_moves_available']:
        return []
    slots = {(row['city_id'], row['building_index'], row['slot']): row['work']
             for row in panel['great_work_slots']}
    actions = []
    for move in panel['great_work_move_targets']:
        source, target = (slots[_slot_address(move[key])] for key in ('source', 'destination'))
        actions.append(dict(kind=GREAT_WORK_MOVE, source=dict(move['source']),
                            destination=dict(move['destination']), work_index=source['index'],
                            target_work_index=None if target is None else target['index']))
    return actions


def _validate_great_work_slots(slots, complete_buildings):
    if type(slots) is not list or len(slots) > MAX_ROWS:
        raise ValueError('Malformed or unbounded Great Work inventory')
    previous = (-1, -1, -1)
    works = set()
    positions = {}
    for row in slots:
        if (type(row) is not dict
                or set(row) != {'city_id', 'building_index', 'slot', 'slot_type', 'work'}):
            raise ValueError('Malformed Great Work slot')
        city = _uint(row['city_id'], 'Great Work city')
        building = _uint(row['building_index'], 'Great Work building', 0x7fffffff)
        slot = _uint(row['slot'], 'Great Work slot', MAX_ROWS - 1)
        _kind(row['slot_type'], 'GREATWORKSLOT')
        key = (city, building, slot)
        if ((city, building) not in complete_buildings or key <= previous
                or slot != (previous[2] + 1 if key[:2] == previous[:2] else 0)):
            raise ValueError('Great Work slot is foreign, duplicate or out of order')
        previous = key
        work = row['work']
        positions[key] = work
        if work is None:
            continue
        if (type(work) is not dict or set(work) != {'index', 'type', 'object_type', 'move_unlocked'}
                or type(work['move_unlocked']) is not bool):
            raise ValueError('Malformed Great Work')
        index = _uint(work['index'], 'Great Work index', 0x7fffffff)
        if index in works:
            raise ValueError('Duplicate Great Work instance')
        works.add(index)
        _kind(work['type'], 'GREATWORK')
        _kind(work['object_type'], 'GREATWORKOBJECT')
    return positions


def _validate_great_work_building_bonuses(rows, slots):
    counts = {}
    for (city, building, _), work in slots.items():
        count, filled = counts.get((city, building), (0, 0))
        counts[city, building] = (count + 1, filled + int(work is not None))
    if type(rows) is not list or len(rows) != len(counts):
        raise ValueError('Great Work bonus buildings differ from the visible slot buildings')
    for row, address in zip(rows, sorted(counts), strict=True):
        if (type(row) is not dict or set(row) != {'city_id', 'building_index', 'theme', 'yields', 'tourism'}
                or (_uint(row['city_id'], 'bonus city'),
                    _uint(row['building_index'], 'bonus building', 0x7fffffff)) != address):
            raise ValueError('Malformed or foreign Great Work bonus building')
        count, filled = counts[address]
        theme = row['theme']
        if theme is not None:
            if type(theme) is not dict or theme.get('state') not in ('themed', 'progress'):
                raise ValueError('Malformed Great Work theme')
            if theme['state'] == 'themed':
                if set(theme) != {'state'} or filled == 0:
                    raise ValueError('A themed building needs a Great Work')
            elif (set(theme) != {'state', 'matching', 'slots'}
                    or _uint(theme['slots'], 'theme slot count') != count
                    or _uint(theme['matching'], 'theme progress') > filled
                    or (count == 1 and filled != 0)):
                raise ValueError('Great Work theme progress differs from the visible slots')
        yields = row['yields']
        if type(yields) is not dict or len(yields) > 256:
            raise ValueError('Malformed Great Work yields')
        for kind, amount in yields.items():
            _kind(kind, 'YIELD')
            if not _uint(amount, 'displayed Great Work yield', 0x7fffffff):
                raise ValueError('A displayed Great Work yield must be positive')
        _uint(row['tourism'], 'displayed Great Work tourism', 0xfffffffe)


def _validate_great_work_targets(moves, slots):
    if type(moves) is not list or len(moves) > MAX_ROWS:
        raise ValueError('Malformed or unbounded Great Work targets')
    previous = None
    for row in moves:
        if type(row) is not dict or set(row) != {'source', 'destination'}:
            raise ValueError('Malformed Great Work target')
        source, destination = (_slot_address(row[field]) for field in ('source', 'destination'))
        origin = slots.get(source)
        target = slots.get(destination)
        pair = (source, destination)
        if (source == destination or origin is None or destination not in slots
                or origin['move_unlocked'] is not True
                or (target is not None and target['move_unlocked'] is not True)
                or (previous is not None and pair <= previous)):
            raise ValueError('Foreign, duplicate or locked Great Work target')
        previous = pair


def _slot_address(value):
    if type(value) is not dict or set(value) != {'city_id', 'building_index', 'slot'}:
        raise ValueError('Malformed Great Work slot address')
    return (_uint(value['city_id'], 'Great Work city'),
            _uint(value['building_index'], 'Great Work building', 0x7fffffff),
            _uint(value['slot'], 'Great Work slot', MAX_ROWS - 1))


def _kind(value, prefix):
    if type(value) is not str or re.fullmatch(prefix + '_[A-Z0-9_]{1,100}', value) is None:
        raise ValueError('Malformed Great Work type')
